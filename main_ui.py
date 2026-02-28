import sys
import os
import threading
import time
from pathlib import Path

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QListWidget, QLabel, 
                             QSplitter, QStatusBar, QDialog, QLineEdit, 
                             QFileDialog, QListWidgetItem)
from PyQt6.QtCore import Qt, QThread, pyqtSignal

# Módulos Core
from map_widget import MapWidget
from cartographer import Cartographer
from auth import EveAuth, CLIENT_ID, CLIENT_SECRET, CALLBACK_URL, SCOPES
from esi_tracker import PlayerTracker
from intel_tailer import IntelTailer
from intel_parser import IntelParser
from threat_profiler import ThreatProfiler
from config_manager import ConfigManager
from audio_engine import AudioManager

# ─── Workers de Fondo ────────────────────────────────────────────────────────

class TrackerWorker(QThread):
    locationChanged = pyqtSignal(int)
    identityConfirmed = pyqtSignal(str, int)

    def __init__(self, tracker):
        super().__init__()
        self.tracker = tracker
        self.running = True

    def run(self):
        while self.running:
            try:
                if not self.tracker.character_id:
                    self.tracker._verify_identity()
                    if self.tracker.character_name:
                        self.identityConfirmed.emit(self.tracker.character_name, self.tracker.character_id)

                system_id = self.tracker.get_current_location()
                if system_id:
                    self.locationChanged.emit(system_id)
            except Exception as e:
                print(f"[TrackerWorker] Error: {e}")
            
            time.sleep(15) # Consultar ESI cada 15s

    def stop(self):
        self.running = False


class IntelWorker(QThread):
    newIntel = pyqtSignal(str, str, str) # system, pilot, profile

    def __init__(self, log_dir, channels, known_systems):
        super().__init__()
        self.log_dir = log_dir
        self.channels = channels
        self.parser = IntelParser(known_systems=known_systems)
        self.profiler = ThreatProfiler()
        self.running = True

    def run(self):
        # Sobrescribimos el método _process_new_line del tailer para emitir señales
        class SignalTailer(IntelTailer):
            def __init__(self, log_dir, channels, parser, worker):
                super().__init__(log_dir, channels, parser)
                self.worker = worker

            def _process_new_line(self, channel, line):
                res = self.parser.parse_line(line)
                if res and res['system']:
                    # Obtener perfil de amenaza (bloqueante, pero el worker es un hilo)
                    profile = self.worker.profiler.profile_player(res['author'])
                    self.worker.newIntel.emit(res['system'], res['author'], profile)

        tailer = SignalTailer(self.log_dir, self.channels, self.parser, self)
        
        # Bucle de vigilancia manual para poder detenerlo
        tailing = True
        tailer._refresh_file_handles()
        while self.running:
            for channel, file_data in tailer.active_log_files.items():
                f = file_data["file"]
                while True:
                    line = f.readline()
                    if not line: break
                    tailer._process_new_line(channel, line)
            
            time.sleep(1)
            # Refrescar handles cada 10s aproximadamente
            if int(time.time()) % 10 == 0:
                tailer._refresh_file_handles()

    def stop(self):
        self.running = False

# ─── Diálogo de Ajustes ──────────────────────────────────────────────────────

class SettingsDialog(QDialog):
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("Ajustes de RadLocal")
        self.setMinimumWidth(400)
        
        layout = QVBoxLayout(self)
        
        # Log Dir
        layout.addWidget(QLabel("Directorio de Chatlogs de EVE:"))
        self.edit_log_dir = QLineEdit(self.config.get("log_dir"))
        btn_browse = QPushButton("Buscar...")
        btn_browse.clicked.connect(self.browse_dir)
        h_layout = QHBoxLayout()
        h_layout.addWidget(self.edit_log_dir)
        h_layout.addWidget(btn_browse)
        layout.addLayout(h_layout)
        
        # Channels
        layout.addWidget(QLabel("Canales de Intel (separados por coma):"))
        self.edit_channels = QLineEdit(", ".join(self.config.get("intel_channels")))
        layout.addWidget(self.edit_channels)
        
        # Alliance ID (Opcional)
        layout.addWidget(QLabel("Tu Alliance ID (para omitir aliados):"))
        self.edit_alliance = QLineEdit(str(self.config.get("alliance_id") or ""))
        layout.addWidget(self.edit_alliance)
        
        btn_save = QPushButton("Guardar y Reiniciar Intel")
        btn_save.clicked.connect(self.save_settings)
        layout.addWidget(btn_save)

    def browse_dir(self):
        directory = QFileDialog.getExistingDirectory(self, "Seleccionar carpeta de logs")
        if directory:
            self.edit_log_dir.setText(directory)

    def save_settings(self):
        self.config.set("log_dir", self.edit_log_dir.text())
        channels = [c.strip() for c in self.edit_channels.text().split(",") if c.strip()]
        self.config.set("intel_channels", channels)
        
        alliance_str = self.edit_alliance.text().strip()
        self.config.set("alliance_id", int(alliance_str) if alliance_str.isdigit() else None)
        
        self.accept()

# ─── Ventana Principal ────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.carto = Cartographer()
        self.audio = AudioManager()
        self.current_system_id = None
        
        # Propiedades de la Ventana
        self.setWindowTitle("RadLocal Tactical HUD v0.2.0")
        self.resize(1100, 750)
        self.setStyleSheet("background-color: #121212; color: #e0e0e0;")
        
        # Widget Central
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Barra Superior
        top_bar = QWidget()
        top_bar.setStyleSheet("background-color: #1c1c1c; border-bottom: 1px solid #333;")
        top_layout = QHBoxLayout(top_bar)
        
        self.btn_top = QPushButton("Pin 📌")
        self.btn_top.setCheckable(True)
        self.btn_top.clicked.connect(self.toggle_always_on_top)
        top_layout.addWidget(self.btn_top)
        
        btn_settings = QPushButton("⚙ Ajustes")
        btn_settings.clicked.connect(self.open_settings)
        top_layout.addWidget(btn_settings)
        
        self.lbl_char = QLabel("Personaje: Desconectado")
        top_layout.addStretch()
        top_layout.addWidget(self.lbl_char)
        
        main_layout.addWidget(top_bar)
        
        # Radar y Lista
        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.map_view = MapWidget()
        splitter.addWidget(self.map_view)
        
        intel_panel = QWidget()
        intel_layout = QVBoxLayout(intel_panel)
        self.intel_list = QListWidget()
        self.intel_list.setStyleSheet("background-color: #000; border: none;")
        intel_layout.addWidget(QLabel("<b>INTEL FEED</b>"))
        intel_layout.addWidget(self.intel_list)
        splitter.addWidget(intel_panel)
        
        splitter.setSizes([750, 350])
        main_layout.addWidget(splitter)
        
        # Barra de Estado
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Iniciando módulos tácticos...")
        
        # Iniciar Workers
        self.start_tracker()
        self.start_intel()

    def toggle_always_on_top(self, checked):
        if checked:
            self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        else:
            self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowStaysOnTopHint)
        self.show()

    def open_settings(self):
        diag = SettingsDialog(self.config, self)
        if diag.exec():
            self.status_bar.showMessage("Ajustes guardados. Reiniciando Intel...")
            self.start_intel()

    def start_tracker(self):
        tracker = PlayerTracker()
        self.tracker_thread = TrackerWorker(tracker)
        self.tracker_thread.identityConfirmed.connect(self.update_identity)
        self.tracker_thread.locationChanged.connect(self.update_location)
        self.tracker_thread.start()

    def start_intel(self):
        if hasattr(self, 'intel_thread') and self.intel_thread.isRunning():
            self.intel_thread.stop()
            self.intel_thread.wait()
            
        known_systems = [s['name'] for s in self.carto.systems.values()]
        self.intel_thread = IntelWorker(
            self.config.get("log_dir"),
            self.config.get("intel_channels"),
            known_systems
        )
        self.intel_thread.newIntel.connect(self.handle_intel)
        self.intel_thread.start()

    def update_identity(self, name, char_id):
        self.lbl_char.setText(f"Personaje: {name}")
        self.config.set("character_name", name)
        self.config.set("character_id", char_id)

    def update_location(self, system_id):
        if system_id != self.current_system_id:
            self.current_system_id = system_id
            sys_name = self.carto.get_system_name(system_id)
            self.status_bar.showMessage(f"Ubicación actual: {sys_name}")
            
            # Recalcular mapa local a 3 saltos
            topology = self.carto.get_local_map(system_id, 3)
            self.map_view.draw_map(topology, system_id)

    def handle_intel(self, system_name, pilot, profile):
        # Añadir a la lista
        item_text = f"[{system_name}] {pilot}: {profile}"
        item = QListWidgetItem(item_text)
        
        if "Peligroso" in profile:
            item.setForeground(Qt.GlobalColor.red)
        elif "ALIADO" in profile:
            item.setForeground(Qt.GlobalColor.blue)
        else:
            item.setForeground(Qt.GlobalColor.yellow)
            
        self.intel_list.insertItem(0, item) # Insertar arriba
        
        # Actualizar mapa
        self.map_view.update_threat(system_name, "HOSTILE")
        
        # Audio
        # Calcular saltos si el sistema está en nuestro radar
        jumps = self.carto.get_distance(self.current_system_id, system_name)
        if jumps is not None:
            self.audio.process_threat(system_name, jumps, "ALIADO" in profile)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    config = ConfigManager()
    
    # Autenticación inicial si es necesario
    auth = EveAuth(CLIENT_ID, CLIENT_SECRET, CALLBACK_URL, SCOPES)
    if not auth.load_token():
        # Mostrar pequeño aviso o simplemente lanzar login
        print("[Main] No se encontró token. Lanzando login...")
        auth.authenticate()
    
    window = MainWindow(config)
    window.show()
    
    sys.exit(app.exec())
