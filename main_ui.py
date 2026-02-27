import sys
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QListWidget, QLabel, QSplitter)
from PyQt6.QtCore import Qt
from map_widget import MapWidget
from cartographer import Cartographer

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # Propiedades de la Ventana
        self.setWindowTitle("RadLocal SMT Prototype")
        self.resize(1000, 700)
        
        # Modo por defecto (Ventana normal flotante en Nobara Linux)
        # Podemos añadir esto a un botón "Always on Top" después
        
        # Widget Central y Layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Top Bar (Para botones de control como Always on Top)
        top_bar = QWidget()
        top_bar.setStyleSheet("background-color: #2b2b2b;")
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(5, 5, 5, 5)
        
        # Botón "Always on Top"
        self.btn_top = QPushButton("Pin to Top (Off)")
        self.btn_top.setCheckable(True)
        self.btn_top.clicked.connect(self.toggle_always_on_top)
        top_layout.addWidget(self.btn_top)
        
        top_layout.addStretch() # Empujar a la izquierda
        
        main_layout.addWidget(top_bar)
        
        # Splitter (Divide el radar a la izquierda y el reporte a la derecha)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # 1. El HUD Táctico (Canvas)
        self.map_view = MapWidget()
        splitter.addWidget(self.map_view)
        
        # 2. Panel de Inteligencia (Lista de chat)
        intel_panel = QWidget()
        intel_layout = QVBoxLayout(intel_panel)
        intel_layout.setContentsMargins(5, 5, 5, 5)
        
        lbl_intel = QLabel("Intel Feed (Live)")
        lbl_intel.setStyleSheet("color: white; font-weight: bold;")
        intel_layout.addWidget(lbl_intel)
        
        self.intel_list = QListWidget()
        self.intel_list.setStyleSheet("background-color: #1a1a1a; color: #00ff00;")
        intel_layout.addWidget(self.intel_list)
        
        splitter.addWidget(intel_panel)
        
        # Darle más espacio al mapa que al chat (ej: 70% vs 30%)
        splitter.setSizes([700, 300])
        main_layout.addWidget(splitter)
        
    def toggle_always_on_top(self, checked):
        if checked:
            self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
            self.btn_top.setText("Pin to Top (On)")
        else:
            self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowStaysOnTopHint)
            self.btn_top.setText("Pin to Top (Off)")
            
        self.show() # Necesario tras cambiar flags de ventana
        
    def add_intel_report(self, system_name, pilot_name, threat_profile):
        """Añade un texto a la barra lateral y advierte al HUD visual."""
        text = f"[{system_name}] {pilot_name} -> {threat_profile}"
        self.intel_list.addItem(text)
        
        # Desplaar al fondo
        self.intel_list.scrollToBottom()
        
        # Pintar el sistema en rojo en el HUD
        self.map_view.update_threat(system_name, "HOSTILE")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # ─── Auto-Updater ─────────────────────────────────────────────────────────
    # Se ejecuta ANTES de mostrar la ventana principal.
    # Si hay actualización, descarga los archivos nuevos y reinicia la app.
    try:
        from updater import run_update_with_gui, AutoUpdater
        was_updated = run_update_with_gui(app)
        if was_updated:
            # Reiniciar el proceso para cargar los módulos actualizados
            AutoUpdater().restart_app()
            sys.exit(0)  # Por si restart_app() falla (no debería llegar aquí)
    except Exception as e:
        # Nunca impedir el arranque de la app por un fallo en el updater
        print(f"[main] Updater omitido por error: {e}")
    
    # Tema global oscuro
    app.setStyle("Fusion")
    palette = app.palette()
    app.setPalette(palette)
    
    window = MainWindow()
    window.show()
    
    # Simular carga de un mapa usando el Cartographer
    # Usaremos el sistema ID 30002888 de las pruebas anteriores (e.g. Deklein -> S-LHPJ)
    print("Iniciando GUI test con topología real...")
    carto = Cartographer()
    centro_id = 30002888
    topology = carto.get_local_map(centro_id, 3) # 3 saltos
    
    window.map_view.draw_map(topology, centro_id)
    
    # Simular un evento de inteligencia a los 2 segundos
    import threading
    import time
    
    def simulate_intel():
        time.sleep(2)
        # S-LHPJ tiene vecinos como OWXT-5 (30002887) u otros, la simulacion puede pintar uno
        # Buscamos cual es el primer vecino del diccionario y lo reportamos
        for k, v in topology.items():
            if k != centro_id:
                # Disparamos el reporte a traves de PyQt Invoke (thread safe) de ser en produccion, 
                # pero aqui en test simple lo llamamos directo (asumiendo que PyQt no se enfade por 1 vez)
                window.add_intel_report(v['name'], "Stunt Flores", "[Interceptor]")
                break
                
    threading.Thread(target=simulate_intel, daemon=True).start()
    
    sys.exit(app.exec())
