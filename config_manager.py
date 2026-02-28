import json
import os
from pathlib import Path

class ConfigManager:
    """
    Gestiona la persistencia de ajustes del usuario en un archivo JSON.
    Ubicación: ~/.config/radlocal/settings.json
    """
    CONFIG_DIR = Path.home() / ".config" / "radlocal"
    SETTINGS_FILE = CONFIG_DIR / "settings.json"

    DEFAULT_SETTINGS = {
        "log_dir": "~/EVE/logs/Chatlogs/",
        "intel_channels": ["B0SS Intel"],
        "alliance_id": None,
        "character_id": None,
        "character_name": None
    }

    def __init__(self):
        self.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        self.settings = self._load()

    def _load(self):
        if self.SETTINGS_FILE.exists():
            try:
                with open(self.SETTINGS_FILE, "r") as f:
                    data = json.load(f)
                    # Mezclar con default para asegurar que todas las llaves existan
                    return {**self.DEFAULT_SETTINGS, **data}
            except Exception as e:
                print(f"[ConfigManager] Error cargando settings: {e}")
        return self.DEFAULT_SETTINGS.copy()

    def save(self):
        try:
            with open(self.SETTINGS_FILE, "w") as f:
                json.dump(self.settings, f, indent=4)
        except Exception as e:
            print(f"[ConfigManager] Error guardando settings: {e}")

    def get(self, key):
        return self.settings.get(key, self.DEFAULT_SETTINGS.get(key))

    def set(self, key, value):
        self.settings[key] = value
        self.save()
