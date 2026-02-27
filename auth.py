import os
import json
import urllib.parse
import requests
import webbrowser
import secrets
import base64
from http.server import HTTPServer, BaseHTTPRequestHandler

# --- TUS CREDENCIALES ---
CLIENT_ID = "0ec91fd968a645329566f5fa84e0b2bc"
CLIENT_SECRET = "eat_1waSORbkHhN6TRrIgjKmH3YuxNKfQxJD8_30S6zd"
CALLBACK_URL = "http://localhost:8000/callback"
SCOPES = "esi-location.read_location.v1 esi-location.read_online.v1 esi-universe.read_structures.v1"

class EveAuthCallbackHandler(BaseHTTPRequestHandler):
    """Manejador temporal para recibir el callback de EVE Online"""
    def do_GET(self):
        # Desglosamos la URL para encontrar los parámetros
        parsed_path = urllib.parse.urlparse(self.path)
        
        if parsed_path.path == '/callback':
            query = urllib.parse.parse_qs(parsed_path.query)
            
            code = query.get('code', [None])[0]
            returned_state = query.get('state', [None])[0]

            if returned_state != self.server.auth_manager.state:
                self.send_response(403)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                self.wfile.write(b"Error de seguridad: El estado no coincide.")
                return

            if code:
                # Intercambiamos el código por el token
                success = self.server.auth_manager.exchange_code_for_token(code)
                
                self.send_response(200)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                
                if success:
                    html = """
                    <html>
                        <body style="font-family: Arial, sans-serif; padding: 20px;">
                            <h1 style="color: green;">¡Autenticación Exitosa!</h1>
                            <p>Ya puedes cerrar esta pestaña y volver a tu aplicaci&oacute;n.</p>
                        </body>
                    </html>
                    """
                else:
                    html = "<h1>Error al obtener el token</h1><p>Revisa la consola para mas detalles.</p>"
                
                self.wfile.write(html.encode('utf-8'))
                
                # Le decimos al servidor que ya puede cerrarse
                self.server.auth_manager.callback_received = True

    # Silenciamos los logs de peticiones HTTP en consola
    def log_message(self, format, *args):
        pass

class EveAuth:
    def __init__(self, client_id, client_secret, callback_url, scopes, token_file="token.json"):
        self.client_id = client_id
        self.client_secret = client_secret
        self.callback_url = callback_url
        self.scopes = scopes
        self.token_file = token_file
        self.state = secrets.token_urlsafe(16)
        self.callback_received = False
        self.token_data = None

    def load_token(self):
        """Intenta cargar un token guardado previamente."""
        if os.path.exists(self.token_file):
            try:
                with open(self.token_file, "r") as f:
                    self.token_data = json.load(f)
                return True
            except Exception as e:
                print(f"Error leyendo el token guardado: {e}")
        return False

    def exchange_code_for_token(self, code):
        """Usa el código recibido en el callback para obtener los tokens reales."""
        auth_header = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
        headers = {
            "Authorization": f"Basic {auth_header}",
            "Content-Type": "application/x-www-form-urlencoded",
            "Host": "login.eveonline.com"
        }
        data = {
            "grant_type": "authorization_code",
            "code": code
        }

        try:
            response = requests.post("https://login.eveonline.com/v2/oauth/token", headers=headers, data=data)
            response.raise_for_status()
            self.token_data = response.json()

            with open(self.token_file, "w") as f:
                json.dump(self.token_data, f, indent=4)
                
            print(f"✅ Token guardado exitosamente en '{self.token_file}'")
            return True
        except Exception as e:
            print(f"❌ Error al intercambiar token: {e}")
            return False

    def authenticate(self):
        """Punto de entrada principal. Verifica token existente o lanza login."""
        # 1. Intentamos usar un token guardado
        if self.load_token():
            print("✅ Token encontrado localmente.")
            # TODO: Aquí podrías añadir una comprobación de si expiró y usar el refresh_token
            return self.token_data

        # 2. Si no hay token, iniciamos el flujo abriendo el navegador
        params = {
            "response_type": "code",
            "redirect_uri": self.callback_url,
            "client_id": self.client_id,
            "scope": self.scopes,
            "state": self.state
        }
        auth_url = "https://login.eveonline.com/v2/oauth/authorize/?" + urllib.parse.urlencode(params)

        print("🚀 Abriendo navegador para autenticación con EVE Online...")
        webbrowser.open(auth_url)

        # 3. Levantamos un servidor local que escuchará UNA VEZ el callback
        # Extraemos el puerto de la URL
        parsed_url = urllib.parse.urlparse(self.callback_url)
        port = parsed_url.port or 8000
        
        server = HTTPServer(('localhost', port), EveAuthCallbackHandler)
        server.auth_manager = self # Pasamos la referencia a nuestra clase principal
        
        print(f"⏳ Esperando conexión en puerto {port}...")
        
        # El servidor procesará peticiones de manera bloqueante hasta que recibamos el callback
        while not self.callback_received:
            server.handle_request()
            
        print("Cerrando servidor temporal de autenticación.")
        server.server_close()
        
        return self.token_data

# ==========================================
# CÓMO USARLO EN TU PROGRAMA PRINCIPAL SMT
# ==========================================
if __name__ == '__main__':
    # Creas la instancia
    auth = EveAuth(CLIENT_ID, CLIENT_SECRET, CALLBACK_URL, SCOPES)
    
    # Intentas autenticar (esto bloqueará el script hasta que el usuario se loguee 
    # en el navegador, o retornará de inmediato si el token.json ya existía)
    token = auth.authenticate()
    
    if token:
        print("\n=== TU APP DE ESCRITORIO SMT === ")
        print("¡Listo para hacer llamadas a la API (ESI)!")
        print(f"Access Token: {token.get('access_token')[:20]}...")
    else:
        print("No se pudo autenticar. El programa principal no puede continuar.")
