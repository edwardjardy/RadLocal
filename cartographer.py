import os
import json
import requests
from collections import deque
from logistics import JumpBridgeManager

class Cartographer:
    """
    Módulo para generar mapas topológicos del espacio de EVE Online basados en saltos,
    ignorando las fronteras de regiones y aplanando el espacio 3D a un plano 2D (X/Z).
    Soporta conexiones personalizadas (Ansiblex Jump Bridges).
    """

    ESI_BASE_URL = "https://esi.evetech.net/latest"

    def __init__(self, cache_file="systems_cache.json", jump_bridge_manager=None):
        self.cache_file = cache_file
        self.system_cache = self._load_cache()
        self.jump_bridge_manager = jump_bridge_manager

    def _load_cache(self):
        """Carga la caché de sistemas desde el disco duro."""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, "r") as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error reading cache: {e}")
        return {}

    def _save_cache(self):
        """Guarda la caché de sistemas en disco duro."""
        with open(self.cache_file, "w") as f:
            json.dump(self.system_cache, f, indent=4)

    def _fetch_system_data(self, system_id):
        """
        Obtiene los datos de un sistema desde ESI (si no está en caché).
        Retorna: nombre, posición (x, z), lista_de_saltos_estaticos_ids
        """
        system_id_str = str(system_id)
        
        # Verificar caché primero
        if system_id_str in self.system_cache:
            return self.system_cache[system_id_str]

        print(f"  [ESI] Descargando sistema ID: {system_id}...")
        
        try:
            # Petición 1: Datos del sistema
            sys_resp = requests.get(f"{self.ESI_BASE_URL}/universe/systems/{system_id}/")
            sys_resp.raise_for_status()
            sys_data = sys_resp.json()

            name = sys_data['name']
            
            # Petición 2: Desempaquetar los stargates (Conexiones Naturales)
            stargate_connections = []
            if 'stargates' in sys_data:
                for stargate_id in sys_data['stargates']:
                    sg_resp = requests.get(f"{self.ESI_BASE_URL}/universe/stargates/{stargate_id}/")
                    if sg_resp.status_code == 200:
                        sg_data = sg_resp.json()
                        stargate_connections.append(sg_data['destination']['system_id'])

            # Aplanamos a 2D guardando solo X y Z
            pos_x = sys_data['position']['x']
            pos_z = sys_data['position']['z']
            
            cache_entry = {
                "id": system_id,
                "name": name,
                "x": pos_x,
                "z": pos_z,
                "connections": stargate_connections
            }
            
            self.system_cache[system_id_str] = cache_entry
            return cache_entry

        except Exception as e:
            print(f"Error fetching system {system_id}: {e}")
            return None

    def get_local_map(self, center_system_id, max_jumps):
        """
        Realiza una búsqueda BFS para mapear el vecindario incluyendo 
        Jump Gates artificiales si hay un gestor de logística instanciado.
        """
        print(f"Iniciando mapeo desde el sistema base {center_system_id} a un radio de {max_jumps} saltos...")
        
        local_map = {}
        queue = deque([(center_system_id, 0)])
        visited = set([center_system_id])
        
        center_data = self._fetch_system_data(center_system_id)
        if not center_data:
            print("Error: No se pudo obtener el sistema central.")
            return {}
            
        center_x = center_data['x']
        center_z = center_data['z']
        
        SCALE_FACTOR = 1e15
        cache_updated = False
        
        while queue:
            current_sys_id, current_distance = queue.popleft()
            
            sys_data = self._fetch_system_data(current_sys_id)
            if not sys_data:
                continue
                
            cache_updated = True 
                
            rel_x = (sys_data['x'] - center_x) / SCALE_FACTOR
            rel_z = (sys_data['z'] - center_z) / SCALE_FACTOR
            
            # --- INCORPORAR JUMP BRIDGES ---
            # Las conexiones normales primero
            stargate_neighbors = sys_data['connections']
            
            # Luego revisamos atajos Ansiblex (si el usuario ha configurado un Manager)
            jump_bridges = []
            if self.jump_bridge_manager:
                jump_bridges = self.jump_bridge_manager.get_bridges(current_sys_id)
                
            # Combinar para explorar (no visitar un sistema por ambos medios de ser posible)
            all_neighbors = list(set(stargate_neighbors + jump_bridges))
            
            local_map[current_sys_id] = {
                "name": sys_data['name'],
                "jumps": current_distance,
                "x_rel": rel_x,
                "z_rel": rel_z,
                "stargates": stargate_neighbors,
                "jump_bridges": jump_bridges
            }
            
            # Expandir frontera de búsqueda (BFS)
            if current_distance < max_jumps:
                for neighbor_id in all_neighbors:
                    if neighbor_id not in visited:
                        visited.add(neighbor_id)
                        queue.append((neighbor_id, current_distance + 1))

        if cache_updated:
            self._save_cache()
            
        print(f"Mapeo completado. Sistemas descubiertos: {len(local_map)}")
        return local_map

if __name__ == "__main__":
    # Prueba del script INTEGRADO
    print("="*50)
    print(" PRUEBA INTEGRADA: MAPEA VFK-IV (DEKLEIN) A JITA (THE FORGE)")
    print(" Mediante un Jump Bridge Falso.")
    print("="*50)
    
    # 1. Configurar Logística con puente falso masivo
    VFK_ID = 30002888   # Deklein
    JITA_ID = 30000142  # The Forge
    JUMPS = 2           # Solo pediremos 2 saltos a la redonda
    
    jb_manager = JumpBridgeManager(storage_file="test_jumpbridge.json")
    jb_manager.add_bridge(VFK_ID, JITA_ID)
    
    # 2. Configurar Cartógrafo pasándole el manager
    carto = Cartographer(cache_file="test_syscache.json", jump_bridge_manager=jb_manager)
    
    topology = carto.get_local_map(VFK_ID, JUMPS)
    
    print("\n--- Resultados (Sistema: [x, z relativas]) ---")
    for sys_id, data in topology.items():
        is_jita_str = " <--- ¡JITA HA APARECIDO EN DEKLEIN!" if sys_id == JITA_ID else ""
        bridges_info = f" (+ {len(data['jump_bridges'])} Puentes)" if data['jump_bridges'] else ""
        
        print(f"[{data['jumps']} saltos] {data['name']:<12}: X={data['x_rel']:>8.2f}, Z={data['z_rel']:>8.2f} (Puertas estáticas: {len(data['stargates'])}){bridges_info}{is_jita_str}")
        
    # Limpiamos los archivos de prueba
    if os.path.exists("test_jumpbridge.json"):
        os.remove("test_jumpbridge.json")
