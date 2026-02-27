import json
import os
import time
import requests

class ThreatProfiler:
    """
    Analiza a un jugador enemigo mediante ESI y zKillboard para determinar su estilo
    de juego, naves más usadas y nivel de peligrosidad (Threat Profile).
    """

    ESI_BASE_URL = "https://esi.evetech.net/latest"
    ZKILL_STATS_URL = "https://zkillboard.com/api/stats/characterID/{}/"
    USER_AGENT = "RadLocal SMT Tool / Jardy - Threat Profiling"

    # Clasificadores heurísticos (IDs de naves o nombres comunes en EVE)
    # Nota: Simplificamos buscando coincidencias en los nombres devueltos por zKillboard
    SHIPS_TACKLE = ["Sabre", "Flycatcher", "Eris", "Heretic", "Stiletto", "Malediction", "Crow", "Ares", "Broadsword", "Onyx", "Phobos", "Devoter"]
    SHIPS_BLOPS = ["Panther", "Redeemer", "Widow", "Sin", "Marshal", "Tengu", "Loki", "Legion", "Proteus"]
    SHIPS_BOMBER = ["Hound", "Nemesis", "Manticore", "Purifier"]
    SHIPS_HUNTER = ["Kikimora", "Orthrus", "Omen Navy Issue", "Osprey Navy Issue", "Vagabond", "Vedmak"]

    def __init__(self, my_alliance_id=None, cache_file="threat_cache.json"):
        """
        :param my_alliance_id: (int) ID de tu alianza para ignorar aliados.
        """
        self.my_alliance_id = my_alliance_id
        self.cache_file = cache_file
        self.cache = self._load_cache()

    def _load_cache(self):
        """Carga la caché de perfiles y elimina los que tengan más de 24 horas."""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, "r") as f:
                    cache_data = json.load(f)
                    
                    # Limpiar caché viejo (> 24 horas)
                    current_time = time.time()
                    clean_cache = {}
                    for char_name, data in cache_data.items():
                        if current_time - data.get('timestamp', 0) < 86400: # 24 horas
                            clean_cache[char_name] = data
                    return clean_cache
            except Exception as e:
                print(f"Error reading threat cache: {e}")
        return {}

    def _save_cache(self):
        with open(self.cache_file, "w") as f:
            json.dump(self.cache, f, indent=4)

    def _resolve_character_id(self, character_name):
        """Convierte un nombre en texto a su CharacterID usando ESI Universe/IDs."""
        data = [character_name]
        try:
            resp = requests.post(f"{self.ESI_BASE_URL}/universe/ids/", json=data)
            resp.raise_for_status()
            res = resp.json()
            
            if "characters" in res and len(res["characters"]) > 0:
                return res["characters"][0]["id"]
            return None
        except Exception as e:
            print(f"Error resolviendo ID para {character_name}: {e}")
            return None

    def _get_character_alliance(self, character_id):
        """Obtiene el ID de la corporación y alianza actual del personaje."""
        try:
            resp = requests.get(f"{self.ESI_BASE_URL}/characters/{character_id}/")
            resp.raise_for_status()
            data = resp.json()
            return data.get("alliance_id"), data.get("corporation_id")
        except Exception as e:
            print(f"Error obteniendo alianza de {character_id}: {e}")
            return None, None

    def _fetch_zkill_stats(self, character_id):
        """Consulta zKillboard para traer las stats de un piloto."""
        headers = {
            "User-Agent": self.USER_AGENT
        }
        url = self.ZKILL_STATS_URL.format(character_id)
        
        try:
            resp = requests.get(url, headers=headers)
            # zKill responde muy rápido o te banea si abusas.
            if resp.status_code == 429:
                print("⚠️ [RATE LIMIT] zKillboard bloqueó la petición temporalmente.")
                return None
                
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            print(f"Error obteniendo zKill stats para {character_id}: {e}")
            return None

    def _analyze_threat_profile(self, zkill_data):
        """Analiza la data de zKillboard y devuelve una etiqueta y un % de uso de la nave principal."""
        if not zkill_data or 'topLists' not in zkill_data:
            return "Desconocido", "No Data"
            
        # Buscar la lista de naves superiores
        top_ships = []
        for lst in zkill_data['topLists']:
            if lst['type'] == 'shipType':
                top_ships = lst['values']
                break
                
        if not top_ships:
            return "Desconocido", "Mínimo/Industrial"
            
        # Top 1 ship
        primary_ship = top_ships[0]
        ship_name = primary_ship['name']
        
        # Calcular roles usando heurísticas simples
        tags = []
        
        # Verificamos los 3 primeros barcos más usados
        for rank in range(min(3, len(top_ships))):
            s_name = top_ships[rank]['name']
            if s_name in self.SHIPS_TACKLE and "TACKLE" not in tags:
                tags.append("TACKLE/INTERDICTOR")
            if s_name in self.SHIPS_BLOPS and "BLOPS/DROPPER" not in tags:
                tags.append("BLOPS/DROPPER")
            if s_name in self.SHIPS_BOMBER and "BOMBER" not in tags:
                tags.append("BOMBER")
            if s_name in self.SHIPS_HUNTER and "KITE/HUNTER" not in tags:
                tags.append("KITE/HUNTER")
                
        # Clasificamos al jugador según zKill (si sus "kills" totales son bajísimas o "dangerRatio" existe)
        danger = zkill_data.get('dangerRatio', 0)
        
        threat_tag = " | ".join(tags) if tags else "General PVP"
        if danger > 80:
            threat_tag += " (Peligroso)"
            
        return ship_name, threat_tag

    def profile_player(self, character_name):
        """
        Punto principal de entrada. Analiza a un personaje y devuelve un string con su perfil.
        """
        # Chequear caché primero
        c_name = character_name.lower()
        if c_name in self.cache:
            data = self.cache[c_name]
            if data["is_friendly"]:
                return "ALIADO"
            return f"{data['top_ship']} - Perfil: {data['threat_tag']}"

        # 1. Obtener Character ID
        char_id = self._resolve_character_id(character_name)
        if not char_id:
            return "NO ENCONTRADO"
            
        # 2. Ver bando
        alliance_id, corp_id = self._get_character_alliance(char_id)
        
        # Guardar en caché si es aliado para ignorarlo siempre todo el dia
        if self.my_alliance_id and alliance_id == self.my_alliance_id:
            self.cache[c_name] = {
                "timestamp": time.time(),
                "is_friendly": True
            }
            self._save_cache()
            return "ALIADO"
            
        # 3. Consultar zKillboard
        zkill_stats = self._fetch_zkill_stats(char_id)
        if not zkill_stats:
            # Podemos haber sido limitados o el jugador no tiene kills públicas
            return "SIN HISTORIAL PVP"
            
        # 4. Inferir perfil
        top_ship, threat_tag = self._analyze_threat_profile(zkill_stats)
        
        self.cache[c_name] = {
            "timestamp": time.time(),
            "is_friendly": False,
            "top_ship": top_ship,
            "threat_tag": threat_tag
        }
        self._save_cache()
        
        return f"{top_ship} - Perfil: {threat_tag}"

if __name__ == "__main__":
    print("=== TEST DEL THREAT PROFILER ===")
    
    # Supongamos que somos de Fraternity o Pandemic Horde (Alianzas populares)
    PH_ALLIANCE_ID = 386292982
    
    profiler = ThreatProfiler(my_alliance_id=PH_ALLIANCE_ID, cache_file="test_threats.json")
    
    # Nombres de prueba (Personajes legendarios de EVE o genéricos)
    # Stunt Flores = Famoso cazador/roaming.
    # Mister Vee = FC famoso de Goons.
    # Gobbins = Líder de Pandemic Horde (Aliado en este test).
    
    test_players = ["Stunt Flores", "Mister Vee", "Gobbins"]
    
    for pilot in test_players:
        print(f"\n⏳ Analizando a: {pilot}...")
        
        # Medimos el tiempo para demostrar lo veloz que es la caché
        start_time = time.perf_counter()
        
        perfil = profiler.profile_player(pilot)
        
        elapsed = (time.perf_counter() - start_time) * 1000
        print(f"⚠️  Resultado: [{perfil}]")
        print(f"⏱️  Tiempo: {elapsed:.2f} ms")
        
        # Dormimos un segundo solo al hablar a la api para no sobrecargar el test inicial
        time.sleep(1)

    # Segunda ejecución para demostrar CACHÉ
    print("\n--- SEGUNDA EJECUCIÓN (Debería ser instantánea usando Caché) ---")
    start_time = time.perf_counter()
    perfil = profiler.profile_player("Stunt Flores")
    elapsed = (time.perf_counter() - start_time) * 1000
    print(f"⚠️  Resultado: [{perfil}]")
    print(f"⏱️  Tiempo: {elapsed:.2f} ms")
    
    if os.path.exists("test_threats.json"):
        os.remove("test_threats.json")
