import os
import time
import json
import base64
import requests
from auth import CLIENT_ID, CLIENT_SECRET

class PlayerTracker:
    """
    Rastreador de ESI que utiliza los tokens de autenticación para obtener
    la ubicación en vivo del jugador en el universo de EVE.
    """
    ESI_BASE_URL = "https://esi.evetech.net/latest"
    OAUTH_BASE_URL = "https://login.eveonline.com/v2/oauth"

    def __init__(self, token_file="token.json"):
        self.token_file = token_file
        self.access_token = None
        self.refresh_token = None
        self.character_id = None
        self.character_name = None
        
        self._load_tokens()
        if self.access_token:
            self._verify_identity()

    def _load_tokens(self):
        """Carga los tokens del disco."""
        if not os.path.exists(self.token_file):
            print("❌ No se encontró token.json. Ejecuta auth.py primero.")
            return False
            
        try:
            with open(self.token_file, "r") as f:
                data = json.load(f)
                self.access_token = data.get("access_token")
                self.refresh_token = data.get("refresh_token")
            return True
        except Exception as e:
            print(f"Error leyendo los tokens: {e}")
            return False

    def _save_tokens(self, token_data):
        """Sobrescribe los tokens en disco tras una actualización."""
        with open(self.token_file, "w") as f:
            json.dump(token_data, f, indent=4)
        
        self.access_token = token_data.get("access_token")
        self.refresh_token = token_data.get("refresh_token", self.refresh_token)

    def _do_refresh_token(self):
        """
        Pide un nuevo access_token a EVE usando el refresh_token guardado.
        Esto se hace por detrás (background) sin abrir navegador.
        """
        if not self.refresh_token:
            print("No hay refresh_token disponible. Debes reingresar manualmete (auth.py).")
            return False
            
        auth_header = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
        headers = {
            "Authorization": f"Basic {auth_header}",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        data = {
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token
        }

        print("🔄 Renovando el Access Token expirado...")
        try:
            response = requests.post(f"{self.OAUTH_BASE_URL}/token", headers=headers, data=data)
            response.raise_for_status()
            
            token_data = response.json()
            self._save_tokens(token_data)
            print("✅ Token renovado exitosamente.")
            return True
            
        except Exception as e:
            print(f"❌ Error al renovar token silenciosamente: {e}")
            return False

    def _verify_identity(self):
        """Llama al endpoint de verificación de EVE para descifrar quién somos."""
        headers = {
            "Authorization": f"Bearer {self.access_token}"
        }
        
        try:
            # Hay dos formas en ESI, pero /verify es el estandar viejo. El actual es llamar a oauth/verify
            # O mejor aún, decodificar el JWT (access_token)
            # Para simplificar y no añadir dependencias JWT, usaremos una petición HTTP ligera a EVE.
            response = requests.get("https://login.eveonline.com/oauth/verify", headers=headers)
            
            # Si da 401 Unauthorized, nuestro token de 20 min expiró. Refrescamos y reintentamos
            if response.status_code == 401:
                if self._do_refresh_token():
                    # Reintentar con el nuevo access_token
                    return self._verify_identity()
                else:
                    return False
                    
            response.raise_for_status()
            data = response.json()
            
            self.character_id = data.get("CharacterID")
            self.character_name = data.get("CharacterName")
            print(f"Identidad Confirmada: {self.character_name} (ID: {self.character_id})")
            return True
            
        except Exception as e:
            print(f"Error verificando identidad: {e}")
            return False

    def get_current_location(self):
        """
        Pide a la API la ubicación actual del personaje.
        Retorna el ID del Sistema Solar, o None si hay error.
        """
        if not self.character_id:
            if not self._verify_identity():
                return None
                
        headers = {
            "Authorization": f"Bearer {self.access_token}"
        }
        
        url = f"{self.ESI_BASE_URL}/characters/{self.character_id}/location/"
        
        try:
            response = requests.get(url, headers=headers)
            
            # Chequear expiración de token de nuevo por si expiró justo ahora
            if response.status_code in [401, 403]:
                if self._do_refresh_token():
                    return self.get_current_location() # Reintentar recursivamente
                return None
                
            response.raise_for_status()
            data = response.json()
            
            # ESI cachea este endpoint típicamente por 5 segundos
            # No deberíamos llamarlo más de 1 vez cada 5s.
            return data.get("solar_system_id")
            
        except requests.exceptions.HTTPError as e:
            # Si el jugador no está conectado al juego (Offline), la API podría devolver un error 
            # o simplemente enviar el último sistema conocido si acaba de desloguear.
            print(f"Error HTTP obteniendo ubicación: {e}")
            return None
        except Exception as e:
            print(f"Error obteniendo ubicación: {e}")
            return None

if __name__ == "__main__":
    print("=== TEST DEL ESI TRACKER ===")
    
    # IMPORTANTE: Esto asumirá que tienes un "token.json" válido en la misma carpeta,
    # generado previamente por tu script "auth.py".
    tracker = PlayerTracker()
    
    if tracker.access_token:
        print("\n⏳ Sondeando tu ubicación actual en el espacio (Ctrl+C para parar)...")
        
        # Simulación del bucle que usaría el SMT de fondo
        last_system = None
        try:
            for i in range(5): # Probamos 5 veces para no hacer un bucle infinito aquí
                system_id = tracker.get_current_location()
                
                if system_id:
                    if system_id != last_system:
                        print(f"🚀 ¡SALTO DETECTADO! Sistema actual ID: {system_id}")
                        last_system = system_id
                    else:
                        print(f"  [Radar] Personaje detectado en {system_id}")
                else:
                    print("  [?] No se pudo obtener la posición. ¿Estás logueado en EVE?")
                    
                time.sleep(5) # Nunca menos de 5 segundos para ESI location
                
            print("\nTest de sondeado completado exitosamente.")
            
        except KeyboardInterrupt:
            print("\nTest detenido.")
    else:
        print("Test fallido: No se pudo cargar la configuración de autenticación.")
