"""
updater.py – RadLocal Auto-Updater (Delta Update System)
=========================================================
Al arrancar la app, este módulo:
  1. Descarga version.json desde GitHub
  2. Compara versión semver y hashes SHA-256 de cada archivo
  3. Descarga SOLO los archivos que cambiaron (delta update)
  4. Reinicia la app si hubo cambios

Uso:
    from updater import AutoUpdater
    updater = AutoUpdater()
    updated = updater.check_and_update()  # True si hubo actualización
"""

import os
import sys
import json
import hashlib
import shutil
import tempfile
import urllib.request
import urllib.error
from pathlib import Path

# ──────────────────────────────────────────────────────────────────────────────
# CONFIGURACIÓN – Edita estos valores con tu repositorio
# ──────────────────────────────────────────────────────────────────────────────
GITHUB_USER    = "TU_USUARIO"          # <- Cambia esto
GITHUB_REPO    = "RadLocal"            # <- Cambia esto
GITHUB_BRANCH  = "main"

# URL del manifiesto de versión (se puede alojar en GitHub Pages o raw content)
VERSION_MANIFEST_URL = (
    f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/"
    f"{GITHUB_BRANCH}/version.json"
)

# Archivos que el updater puede actualizar en caliente (NO el ejecutable principal)
# Estos son los archivos de "lógica de negocio" que cambian con frecuencia
UPDATABLE_FILES = [
    "map_widget.py",
    "cartographer.py",
    "threat_profiler.py",
    "esi_tracker.py",
    "intel_parser.py",
    "intel_tailer.py",
    "logistics.py",
    "audio_engine.py",
    "auth.py",
    "systems_cache.json",
    "esi_ids.json",
]

# Directorio de configuración del usuario
CONFIG_DIR = Path.home() / ".config" / "radlocal"
LOCAL_VERSION_FILE = CONFIG_DIR / "version.json"

# Directorio donde viven los archivos de la app (junto al ejecutable)
# En dev: directorio del script. En PyInstaller onedir: junto al .exe
def get_app_dir() -> Path:
    """Retorna el directorio base de la aplicación."""
    if getattr(sys, "frozen", False):
        # Corriendo como binario PyInstaller (onedir)
        return Path(sys.executable).parent
    else:
        # Corriendo como script Python normal
        return Path(__file__).parent


# ──────────────────────────────────────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────────────────────────────────────

def _sha256_of_file(path: Path) -> str:
    """Calcula el hash SHA-256 de un archivo local."""
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except FileNotFoundError:
        return ""


def _compare_semver(v1: str, v2: str) -> int:
    """Compara dos versiones semver. Retorna -1, 0 o 1."""
    def parts(v):
        return [int(x) for x in v.lstrip("v").split(".")]
    p1, p2 = parts(v1), parts(v2)
    for a, b in zip(p1, p2):
        if a < b: return -1
        if a > b: return 1
    if len(p1) < len(p2): return -1
    if len(p1) > len(p2): return 1
    return 0


def _fetch_json(url: str, timeout: int = 10) -> dict | None:
    """Descarga y parsea un JSON desde una URL. Retorna None en error."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "RadLocal-Updater/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, Exception):
        return None


def _download_file(url: str, dest: Path, timeout: int = 30) -> bool:
    """Descarga un archivo a dest. Retorna True si OK."""
    try:
        tmp_path = dest.with_suffix(dest.suffix + ".tmp")
        req = urllib.request.Request(url, headers={"User-Agent": "RadLocal-Updater/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp, open(tmp_path, "wb") as out:
            shutil.copyfileobj(resp, out)
        tmp_path.replace(dest)
        return True
    except Exception as e:
        print(f"[updater] ERROR descargando {url}: {e}")
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        return False


# ──────────────────────────────────────────────────────────────────────────────
# CLASE PRINCIPAL
# ──────────────────────────────────────────────────────────────────────────────

class AutoUpdater:
    """
    Sistema de auto-actualización delta para RadLocal.

    Ejemplo de version.json esperado en GitHub:
    {
        "version": "1.2.0",
        "release_notes": "Mejoras en el mapa, nueva detección por Ansiblex",
        "download_base": "https://raw.githubusercontent.com/TU_USUARIO/RadLocal/main/",
        "files": {
            "map_widget.py":   "sha256:aabbcc...",
            "systems_cache.json": "sha256:ddeeff..."
        }
    }
    """

    def __init__(self):
        self.app_dir = get_app_dir()
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        self.local_version = self._load_local_version()

    def _load_local_version(self) -> str:
        """Lee la versión instalada desde ~/.config/radlocal/version.json."""
        if LOCAL_VERSION_FILE.exists():
            try:
                data = json.loads(LOCAL_VERSION_FILE.read_text())
                return data.get("version", "0.0.0")
            except Exception:
                pass
        return "0.0.0"

    def _save_local_version(self, version: str, manifest: dict):
        """Persiste la versión instalada en el directorio de configuración."""
        data = {"version": version, "files": manifest.get("files", {})}
        LOCAL_VERSION_FILE.write_text(json.dumps(data, indent=2))

    def check_for_update(self) -> tuple[bool, dict | None]:
        """
        Consulta GitHub por una nueva versión.
        Retorna (hay_nueva_version, manifest_remoto)
        """
        print(f"[updater] Versión local: {self.local_version}")
        print(f"[updater] Consultando {VERSION_MANIFEST_URL} ...")

        remote = _fetch_json(VERSION_MANIFEST_URL)
        if not remote:
            print("[updater] No se pudo contactar el servidor de actualizaciones.")
            return False, None

        remote_version = remote.get("version", "0.0.0")
        print(f"[updater] Versión remota: {remote_version}")

        if _compare_semver(self.local_version, remote_version) < 0:
            print(f"[updater] ¡Nueva versión disponible! {self.local_version} → {remote_version}")
            return True, remote
        else:
            print("[updater] La app está al día.")
            return False, None

    def apply_update(self, manifest: dict, progress_callback=None) -> bool:
        """
        Descarga SOLO los archivos que cambiaron según el manifiesto.
        progress_callback(current, total, filename) – opcional para la UI.
        Retorna True si se actualizó al menos un archivo.
        """
        remote_files: dict = manifest.get("files", {})
        base_url: str = manifest.get("download_base", "")
        if not base_url.endswith("/"):
            base_url += "/"

        # Leer hashes locales guardados
        local_hashes = {}
        if LOCAL_VERSION_FILE.exists():
            try:
                saved = json.loads(LOCAL_VERSION_FILE.read_text())
                local_hashes = saved.get("files", {})
            except Exception:
                pass

        # Determinar qué archivos realmente cambiaron
        files_to_update = []
        for filename, remote_hash in remote_files.items():
            if filename not in UPDATABLE_FILES:
                continue
            # Comparar con hash guardado primero (rápido)
            saved_hash = local_hashes.get(filename, "")
            if saved_hash == remote_hash:
                continue
            # Verificar también el hash real del archivo en disco
            local_path = self.app_dir / filename
            disk_hash = "sha256:" + _sha256_of_file(local_path)
            if disk_hash != remote_hash:
                files_to_update.append((filename, remote_hash, base_url + filename))

        if not files_to_update:
            print("[updater] Todos los archivos ya están actualizados.")
            self._save_local_version(manifest["version"], manifest)
            return False

        print(f"[updater] Archivos a actualizar: {[f for f, _, _ in files_to_update]}")

        total = len(files_to_update)
        updated = 0
        for i, (filename, expected_hash, url) in enumerate(files_to_update):
            if progress_callback:
                progress_callback(i, total, filename)

            dest = self.app_dir / filename
            print(f"[updater] Descargando {filename} desde {url}")

            if _download_file(url, dest):
                # Verificar integridad del archivo descargado
                actual_hash = "sha256:" + _sha256_of_file(dest)
                if actual_hash == expected_hash:
                    print(f"[updater] ✓ {filename} actualizado correctamente.")
                    updated += 1
                else:
                    print(f"[updater] ✗ {filename}: hash incorrecto ({actual_hash} vs {expected_hash}). Manteniendo versión anterior.")
            else:
                print(f"[updater] ✗ Falló la descarga de {filename}.")

        if progress_callback:
            progress_callback(total, total, "Completado")

        # Guardar la nueva versión aunque algunos archivos fallaran
        self._save_local_version(manifest["version"], manifest)
        return updated > 0

    def check_and_update(self, progress_callback=None) -> bool:
        """
        Método principal: verifica y aplica actualizaciones.
        Retorna True si se actualizó algo (la app debería reiniciarse).
        """
        try:
            has_update, manifest = self.check_for_update()
            if not has_update or not manifest:
                return False
            return self.apply_update(manifest, progress_callback=progress_callback)
        except Exception as e:
            print(f"[updater] Error inesperado durante la actualización: {e}")
            return False

    def restart_app(self):
        """Reinicia el proceso actual para cargar los archivos actualizados."""
        print("[updater] Reiniciando la aplicación...")
        os.execv(sys.executable, [sys.executable] + sys.argv)


# ──────────────────────────────────────────────────────────────────────────────
# VENTANA DE PROGRESO (PyQt6) – solo si PyQt6 está disponible
# ──────────────────────────────────────────────────────────────────────────────

def run_update_with_gui(app_qt) -> bool:
    """
    Corre el chequeo de actualización mostrando una ventana de progreso Qt.
    Llama a esto ANTES de mostrar la ventana principal.
    Retorna True si hubo actualización (la app debe reiniciarse).
    """
    try:
        from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QLabel,
                                     QProgressBar, QApplication)
        from PyQt6.QtCore import Qt, QThread, pyqtSignal
    except ImportError:
        # Si PyQt6 no está disponible (no debería pasar en prod), modo silencioso
        updater = AutoUpdater()
        return updater.check_and_update()

    class UpdateWorker(QThread):
        progress = pyqtSignal(int, int, str)  # (current, total, filename)
        finished = pyqtSignal(bool)           # (hubo_actualizacion)

        def run(self):
            updater = AutoUpdater()

            def on_progress(current, total, fname):
                self.progress.emit(current, total, fname)

            result = updater.check_and_update(progress_callback=on_progress)
            self.finished.emit(result)

    class UpdateDialog(QDialog):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("RadLocal – Comprobando actualizaciones")
            self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
            self.setFixedSize(400, 120)
            self.setStyleSheet("""
                QDialog { background: #1a1a2e; border: 1px solid #0f3460; border-radius: 8px; }
                QLabel  { color: #e0e0e0; font-family: 'Segoe UI', sans-serif; font-size: 12px; }
                QProgressBar {
                    border: 1px solid #0f3460; border-radius: 4px;
                    background: #16213e; height: 16px;
                }
                QProgressBar::chunk { background: #e94560; border-radius: 3px; }
            """)

            layout = QVBoxLayout(self)
            layout.setContentsMargins(20, 20, 20, 20)
            layout.setSpacing(10)

            self.lbl_status = QLabel("Conectando con el servidor...")
            layout.addWidget(self.lbl_status)

            self.progress_bar = QProgressBar()
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(0)
            layout.addWidget(self.progress_bar)

            self.lbl_file = QLabel("")
            layout.addWidget(self.lbl_file)

            self._was_updated = False
            self.worker = UpdateWorker()
            self.worker.progress.connect(self._on_progress)
            self.worker.finished.connect(self._on_finished)
            self.worker.start()

        def _on_progress(self, current: int, total: int, fname: str):
            if total > 0:
                pct = int((current / total) * 100)
                self.progress_bar.setValue(pct)
            self.lbl_status.setText("Descargando actualizaciones...")
            self.lbl_file.setText(f"↓ {fname}")

        def _on_finished(self, was_updated: bool):
            self._was_updated = was_updated
            self.accept()

        @property
        def was_updated(self) -> bool:
            return self._was_updated

    dialog = UpdateDialog()
    # Centrar en pantalla
    if app_qt.primaryScreen():
        rect = app_qt.primaryScreen().availableGeometry()
        dialog.move(
            rect.center().x() - dialog.width() // 2,
            rect.center().y() - dialog.height() // 2,
        )
    dialog.exec()
    return dialog.was_updated


# ──────────────────────────────────────────────────────────────────────────────
# CLI de prueba rápida
# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=== RadLocal Updater – modo CLI ===")
    updater = AutoUpdater()
    updated = updater.check_and_update()
    if updated:
        print("\n✓ Actualización aplicada. Reinicia la app para usar la nueva versión.")
    else:
        print("\n✓ Sin actualizaciones. La app está al día.")
