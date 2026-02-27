import re

class IntelParser:
    """
    Parsea líneas crudas de los logs de chat de EVE Online
    y extrae información táctica: Sistemas, Estado (clr/nv), y D-Scans.
    """
    
    # Expresión regular para separar: [ Fecha Hora ] Autor > Mensaje
    # Ejemplo: [ 2026.04.14 17:01:23 ] Jardy > VFK-IV nv
    LOG_PATTERN = re.compile(r"^\[\s+(.*?)\s+\]\s+(.*?)\s+>\s+(.*)$")
    
    # Diferentes expresiones para D-Scan
    DSCAN_PATTERN = re.compile(r"(https?://(?:dscan\.info|adashboard\.info|evepraisal\.com|dscan\.me)/\S+)")
    
    def __init__(self, known_systems=None):
        """
        :param known_systems: Lista opcional de nombres de sistemas (ej: ['VFK-IV', 'Jita']) 
                              para forzar detecciones exactas. Solo en minúsculas para búsqueda rápida.
        """
        self.known_systems = set([s.lower() for s in known_systems]) if known_systems else set()

    def parse_line(self, raw_line):
        """
        Analiza una línea del log y devuelve un diccionario con los datos si encuentra intel.
        Devuelve None si no es una línea de chat válida.
        """
        match = self.LOG_PATTERN.match(raw_line.strip())
        if not match:
            return None
            
        timestamp, author, message = match.groups()
        
        # Limpiar mensaje extra
        msg_lower = message.lower()
        
        # Detectar estado
        status = "hostile" # Por defecto asumimos que un reporte en Intel es de un hostil
        if "clr" in msg_lower.split() or "clear" in msg_lower.split():
            status = "clear"
        elif "nv" in msg_lower.split() or "no vis" in msg_lower:
            status = "no_vis"
            
        # Detectar D-Scan
        dscan_matches = self.DSCAN_PATTERN.findall(message)
        dscan_link = dscan_matches[0] if dscan_matches else None
        
        # Detectar sistema reportado.
        # Heurística: El sistema suele ser la primera palabra, o lo validamos contra dict.
        words = message.split()
        system_name = None
        
        if self.known_systems:
            # Búsqueda exacta si tenemos la topología cargada
            for w in words:
                if w.lower() in self.known_systems:
                    # Recuperar la capitalización original del mensaje (o podríamos de la BBDD)
                    system_name = w.upper() if w.isupper() else w.title()
                    break
        else:
            # Heurística básica: Asumimos que la primera palabra que no sea intel común es el sistema
            # Ej: "VFK-IV nv" -> VFK-IV
            # Ojo: Excluimos palabras reservadas
            intel_keywords = {"clr", "clear", "nv", "no", "vis", "dscan", "spike", "local", "in", "system"}
            for w in words:
                # Quitamos puntuación pegada como asteriscos
                clean_w = w.strip("*.,:;!?")
                if clean_w.lower() not in intel_keywords and not clean_w.startswith("http"):
                    # Verificaciones adicionales: Si tiene guiones o números con letras, es muy probable un sistema (Ej: 1DQ1-A)
                    system_name = clean_w
                    break

        # Si no encontramos sistema pero sí encontramos 'clr', la alerta es inútil, 
        # sin embargo, esto sirve para depurar.
        
        return {
            "timestamp": timestamp,
            "author": author,
            "system": system_name,
            "status": status,
            "dscan": dscan_link,
            "raw_message": message
        }

if __name__ == "__main__":
    # PRUEBAS DEL PARSER
    parser = IntelParser(known_systems=["vfk-iv", "jita", "1dq1-a"])
    
    test_lines = [
        "[ 2026.02.26 22:15:00 ] Capitán Obvio > VFK-IV nv",
        "[ 2026.02.26 22:16:10 ] Explorador > Jita clr",
        "[ 2026.02.26 22:17:30 ] Spia > 1DQ1-A 50 lokis https://dscan.info/v/1234abcd",
        "[ 2026.02.26 22:18:00 ] Constructor > Hola chicos como estan?",
        "Esto no es una linea de log valida"
    ]
    
    print("=== TEST INTEL PARSER ===")
    for line in test_lines:
        res = parser.parse_line(line)
        if res:
            sys_str = res['system'] or "N/A"
            # Si el 'status' es hostile, pero en realidad era charla, el sistema detectado (como 'Hola') 
            # podría ser un falso positivo. Es normal en heurísticas si no pasas un diccionario estricto.
            print(f"[{res['status'].upper()}] Sistema: {sys_str:<10} | Link: {res['dscan']} | Mensaje original: {res['raw_message']}")
        else:
            print(f"- Línea ignorada: {line[:20]}...")
