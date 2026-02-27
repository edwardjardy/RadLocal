import json
import os

class JumpBridgeManager:
    """
    Gestor de conexiones Ansiblex (Jump Bridges) creadas por el usuario o su alianza.
    """
    def __init__(self, storage_file="jump_bridges.json"):
        self.storage_file = storage_file
        self.bridges = self._load()

    def _load(self):
        """Carga los puentes desde el archivo local JSON."""
        if os.path.exists(self.storage_file):
            try:
                with open(self.storage_file, 'r') as f:
                    data = json.load(f)
                    
                    # Convertir las llaves string a int para la estructura interna
                    # JSON siempre guarda las llaves de diccionario como strings
                    bridges = {}
                    for k, v in data.items():
                        bridges[int(k)] = v
                    return bridges
                    
            except Exception as e:
                print(f"Error cargando jump bridges: {e}")
        return {}

    def _save(self):
        """Guarda los puentes físicos en el archivo JSON."""
        with open(self.storage_file, 'w') as f:
            json.dump(self.bridges, f, indent=4)

    def add_bridge(self, sys_a_id, sys_b_id):
        """
        Añade un puente de salto entre dos sistemas (es bidireccional).
        """
        sys_a_id = int(sys_a_id)
        sys_b_id = int(sys_b_id)

        if sys_a_id not in self.bridges:
            self.bridges[sys_a_id] = []
        if sys_b_id not in self.bridges:
            self.bridges[sys_b_id] = []

        if sys_b_id not in self.bridges[sys_a_id]:
            self.bridges[sys_a_id].append(sys_b_id)
        
        if sys_a_id not in self.bridges[sys_b_id]:
            self.bridges[sys_b_id].append(sys_a_id)
            
        self._save()
        print(f"Puente añadido: {sys_a_id} <---> {sys_b_id}")

    def remove_bridge(self, sys_a_id, sys_b_id):
        """
        Elimina el puente de salto entre dos sistemas.
        """
        sys_a_id = int(sys_a_id)
        sys_b_id = int(sys_b_id)

        removed = False
        if sys_a_id in self.bridges and sys_b_id in self.bridges[sys_a_id]:
            self.bridges[sys_a_id].remove(sys_b_id)
            removed = True
            
        if sys_b_id in self.bridges and sys_a_id in self.bridges[sys_b_id]:
            self.bridges[sys_b_id].remove(sys_a_id)
            removed = True
            
        if removed:
            self._save()
            print(f"Puente eliminado: {sys_a_id} <---> {sys_b_id}")
        else:
            print("No existía ese puente.")

    def get_bridges(self, system_id):
        """
        Devuelve la lista de sistemas conectados por puente desde este sistema.
        """
        system_id = int(system_id)
        return self.bridges.get(system_id, [])

if __name__ == "__main__":
    # Prueba del script de Logística
    print("Iniciando Gestor de Logística...")
    jb_manager = JumpBridgeManager()
    
    # ID de ejemplo: VFK-IV (30002888) y un destino remoto como Jita (30000142)
    VFK_ID = 30002888
    JITA_ID = 30000142
    
    print("\n[+] Configurando puente falso entre Deklein y The Forge...")
    jb_manager.add_bridge(VFK_ID, JITA_ID)
    
    print("\n[?] Puentes encontrados desde VFK-IV:")
    print(jb_manager.get_bridges(VFK_ID))
    
    print("\n[-] Limpiando puente de prueba...")
    jb_manager.remove_bridge(VFK_ID, JITA_ID)
