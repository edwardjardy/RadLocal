import os
import time
import glob
from intel_parser import IntelParser

class IntelTailer:
    """
    Vigila los archivos de log de chat de EVE Online en tiempo real,
    leyendo solo los cambios nuevos para ahorrar CPU.
    """
    def __init__(self, log_dir, channels_to_watch, parser):
        """
        :param log_dir: Directorio donde EVE guarda los Chatlogs.
        :param channels_to_watch: Lista de strings con el nombre del canal a vigilar (ej ['B0SS Intel', 'Coalition_Intel']).
        :param parser: Instancia de IntelParser.
        """
        self.log_dir = os.path.expanduser(log_dir)
        self.channels_to_watch = channels_to_watch
        self.parser = parser
        
        # Diccionario para guardar el puntero de archivo (file object) de cada canal
        self.active_log_files = {}

    def _find_latest_log_for_channel(self, channel_name):
        """Busca el archivo de chatlog más reciente para un canal específico."""
        # El formato de EVE suele ser: NombreCanal_FechaHora.txt
        # Reemplazar espacios por asteriscos en caso de dudas con los nombres de archivo
        safe_name = channel_name.replace(" ", "*")
        pattern = os.path.join(self.log_dir, f"*{safe_name}*.txt")
        
        files = glob.glob(pattern)
        if not files:
            return None
            
        # Ordenar por fecha de modificación (el más reciente al final)
        files.sort(key=os.path.getmtime)
        return files[-1] # Tomar el último

    def _refresh_file_handles(self):
        """Revisa si hay nuevos archivos de log(por ej al reiniciar EVE o si cambió de día)"""
        for channel in self.channels_to_watch:
            latest_file = self._find_latest_log_for_channel(channel)
            
            if not latest_file:
                continue
                
            # Si no estábamos vigilando este canal, o si el archivo más reciente es distinto al que tenemos abierto
            if channel not in self.active_log_files or self.active_log_files[channel]["path"] != latest_file:
                print(f"[*] (Re)Enganchando al canal intel '{channel}' -> {os.path.basename(latest_file)}")
                
                # Cerrar el viejo si existía
                if channel in self.active_log_files:
                    self.active_log_files[channel]["file"].close()
                
                try:
                    # Abrir el nuevo archivo
                    f = open(latest_file, "r", encoding="utf-16", errors="replace") # EVE usa UTF-16 para logs
                    
                    # MAGIA EFFICIENTE: Saltar directamente al final del archivo. 
                    # No leemos todo el historial del día.
                    f.seek(0, os.SEEK_END)
                    
                    self.active_log_files[channel] = {
                        "path": latest_file,
                        "file": f
                    }
                except Exception as e:
                    print(f"Error abriendo log {latest_file}: {e}")

    def watch(self, interval=1.0):
        """
        Bucle infinito que vigila los archivos abiertos buscando nuevas líneas.
        :param interval: Segundos a esperar entre comprobaciones.
        """
        print(f"Comenzando vigilancia de logs en: {self.log_dir}")
        print("Buscando los siguientes canales:", self.channels_to_watch)
        
        # Refresco inicial
        self._refresh_file_handles()
        
        # Bucle para revisar si los archivos han crecido o se han creado nuevos (comprobación lenta = modulo 10 del loop)
        loop_counter = 0
        
        try:
            while True:
                loop_counter += 1
                if loop_counter % 10 == 0:
                    self._refresh_file_handles()
                    
                for channel, file_data in self.active_log_files.items():
                    f = file_data["file"]
                    
                    # Leer nuevas líneas si las hay
                    # f.readline() devuelve string vacío si no hay nada nuevo, o la línea si hay algo
                    while True:
                        line = f.readline()
                        if not line:
                            break # No hay más líneas nuevas por ahora en este fichero
                            
                        # Procesar la línea
                        self._process_new_line(channel, line)
                        
                # Dormir para no devorar la CPU
                time.sleep(interval)
                
        except KeyboardInterrupt:
            print("\nDeteniendo vigilancia de logs.")
            # Cerrar limpiamente
            for file_data in self.active_log_files.values():
                file_data["file"].close()

    def _process_new_line(self, channel, line):
        """Función interna que pasa la línea al parser y actúa sobre el resultado."""
        line = line.strip()
        if not line:
            return
            
        result = self.parser.parse_line(line)
        if result:
            sys = result['system'] or "Desconocido"
            status = result['status'].upper()
            dscan = f" | D-Scan: {result['dscan']}" if result['dscan'] else ""
            
            # Formatear salida para consola (en tu app final, aquí actualizarías el mapa o harías ping)
            color_code = "\033[93m" if status == "HOSTILE" else "\033[92m" if status == "CLEAR" else "\033[96m"
            reset_color = "\033[0m"
            
            print(f"[{time.strftime('%H:%M:%S')}] {color_code}[INTEL - {channel}] Sistema: {sys} | Estado: {status}{dscan} | Reporte: {result['author']}{reset_color}")


# Prueba rápida (standalone mode)
if __name__ == "__main__":
    import shutil
    
    # 1. Crear un entorno falso para intentar probar el script sin tener EVE instalado
    TEST_DIR = "simulated_eve_logs"
    if not os.path.exists(TEST_DIR):
        os.makedirs(TEST_DIR)
        
    fake_log_path = os.path.join(TEST_DIR, "Fake_Intel_20261012_123456.txt")
    
    # Escribir el BOM y cabecera en UTF-16
    with open(fake_log_path, "w", encoding="utf-16") as f:
        f.write("---------------------------------------------------------------\n")
        f.write("  Channel ID:      Local\n")
        f.write("  Channel Name:    Fake Intel\n")
        f.write("---------------------------------------------------------------\n")
        f.write("[ 2026.02.26 18:00:00 ] EVE System > Channel MOTD: Hello\n")
        
    # 2. Iniciar el vigía en un hilo separado o prepararlo
    print(f"\n--- Iniciando simulador de Tailer en la carpeta {TEST_DIR} ---")
    parser = IntelParser(known_systems=["vfk-iv", "jita", "1dq1-a", "9-ii"])
    tailer = IntelTailer(TEST_DIR, ["Fake Intel"], parser)
    
    print("\nEl tailer está a punto de empezar su bucle infinito.")
    print("Para probarlo, abre otra terminal y haz un 'echo' añadiendo contenido al final del archivo simulado.")
    print(f"Ejemplo: echo '[ 2026.02.26 18:10:00 ] Espia > VFK-IV nv' | iconv -f UTF-8 -t UTF-16LE >> {fake_log_path}")
    print("Pulsa Ctrl+C para salir.\n")
    
    # Iniciar la vigilancia (cuidado, bloqueará la terminal)
    # tailer.watch(interval=1.0) 
    # Lo dejamos comentado para que no bloquee los scripts automáticos, 
    # pero está listo para que el usuario o SMT lo importe e inicie su hilo.
