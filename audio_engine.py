import os
import time
import subprocess
import threading
import shutil
from collections import deque

class AudioManager:
    """
    Sistema Nervioso Acústico.
    Gestiona las alertas evitando el "spam" y priorizando por neuropsicología:
    Mismo sistema = Sirena y Alerta de Voz.
    2-4 saltos   = Alerta de Voz media.
    5-9 saltos   = Ping de radar.
    10+ saltos   = Ignorado.
    """
    def __init__(self):
        # Cola de mensajes pendientes para TTS (Text-to-Speech)
        self.message_queue = deque()
        self.is_playing = False
        
        # Historial de alertas recientes para evitar repetir lo mismo (Cooldown)
        # Formato: { "system_name": timestamp_ultimo_aviso }
        self.cooldown_cache = {}
        self.COOLDOWN_SECONDS = 30 # No repetir el mismo sistema por 30 segundos
        
        # Iniciar el hilo trabajador (Worker Thread) para el sonido
        self.worker_thread = threading.Thread(target=self._audio_worker, daemon=True)
        self.worker_thread.start()

    def process_threat(self, system_name, jumps_away, is_friendly=False):
        """
        Punto de entrada. El programa llama a esto cuando llega un reporte.
        Aplica los filtros de distancia y cooldown.
        """
        if is_friendly:
            return # A los amigos no les pitamos
            
        # Filtro de Distancia
        if jumps_away >= 10:
            return # Muy lejos, ignorar
            
        # Filtro Anti-Spam (Cooldown)
        current_time = int(time.time())
        last_played = self.cooldown_cache.get(system_name, 0)
        
        if (current_time - last_played) < self.COOLDOWN_SECONDS:
            return # Ya avisamos de esto recientemente
            
        # Actualizar caché
        self.cooldown_cache[system_name] = current_time
        
        # Clasificar la Alerta
        if jumps_away == 0:
            self._queue_alert("CRITICAL", system_name, jumps_away)
        elif 1 <= jumps_away <= 4:
            self._queue_alert("HIGH", system_name, jumps_away)
        elif 5 <= jumps_away <= 9:
            self._queue_alert("LOW", system_name, jumps_away)

    def _queue_alert(self, priority_level, system_name, jumps):
        """Añade la instrucción de audio a la cola."""
        self.message_queue.append({
            "level": priority_level,
            "system": system_name,
            "jumps": jumps
        })

    def _audio_worker(self):
        """Hilo infinito en segundo plano que consume la cola y habla con el SO Linux."""
        while True:
            if self.message_queue:
                alert = self.message_queue.popleft()
                self.is_playing = True
                self._play_alert(alert)
                self.is_playing = False
                
                # Pequeña pausa entre mensajes para que no se pisen si hay varios
                time.sleep(0.5)
            else:
                time.sleep(0.1) # Dormir si no hay nada

    def _play_alert(self, alert):
        """Determina el mensaje en español y lo envía al motor TTS."""
        level = alert["level"]
        jumps = alert["jumps"]
        
        # Mensajes cortos en español. Sólo informamos cuántos saltos de distancia.
        try:
            if level == "CRITICAL":
                # 0 saltos: máxima urgencia. Una palabra contundente.
                self._speak("Local.", speed=120, pitch=70)
                
            elif level == "HIGH":
                # 1-4 saltos: "1 salto" o "3 saltos"
                salto_word = "salto" if jumps == 1 else "saltos"
                self._speak(f"{jumps} {salto_word}.", speed=130, pitch=50)
                
            elif level == "LOW":
                # 5-9 saltos: información, tono bajo
                self._speak(f"{jumps} saltos.", speed=140, pitch=30)
                
        except Exception as e:
            print(f"Error de audio: {e}")

    def _speak(self, text, speed=130, pitch=50):
        """
        Motor TTS dual:
        - Intenta primero con espeak-ng en voz española (más nativa que spd-say).
        - espeak-ng argumentos:
            -v es       -> Voz en español
            -s WPM      -> Velocidad en palabras por minuto (100-150 = natural)
            -p PITCH    -> Tono (0-99, por defecto 50)
            -a AMP      -> Amplitud/Volumen (0-200, default 100)
        """
        cmd = [
            "espeak-ng",
            "-v", "es",         # Voz español
            "-s", str(speed),   # Velocidad: 130 WPM = ritmo de conversación normal
            "-p", str(pitch),   # Tono de voz
            "-a", "150",        # Volumen ligeramente elevado
            text
        ]
        
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


if __name__ == "__main__":
    print("=== TEST DEL MOTOR DE AUDIO ===")
    
    if shutil.which("espeak-ng") is None:
        print("\u274c No se encontró 'espeak-ng'.")
        print("Instala con: sudo dnf install espeak-ng espeak-ng-espeak-data")
    else:
        audio = AudioManager()
        
        print("\n🔊 [7 saltos] -> Debería decir: '7 saltos'")
        audio.process_threat("QA-8XZ", 7)
        time.sleep(4)
        
        print("\n⚠️ [2 saltos] -> Debería decir: '2 saltos'")
        audio.process_threat("VFK-IV", 2)
        time.sleep(4)
        
        print("\n🚨 [0 saltos - Local] -> Debería decir: 'Local'")
        audio.process_threat("Deklein", 0)
        time.sleep(4)
        
        print("\n🛡️ [Anti-Spam] Reportando Deklein otra vez -> silencio esperado")
        audio.process_threat("Deklein", 0)
        print("-> Si no se escucha nada, el cooldown funciona correctamente.")
        time.sleep(2)
        
        print("\nTest finalizado.")
