import sys
from PyQt6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsEllipseItem, QGraphicsTextItem, QGraphicsLineItem
from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtGui import QBrush, QPen, QColor, QFont, QPainter

class MapWidget(QGraphicsView):
    """
    HUD Táctico (Canvas Vectorial).
    Dibuja los sistemas, stargates y puentes de salto basándose en
    el diccionario de topología generado por Cartographer.
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        
        # Propiedades del View para que actúe como un mapa fluido
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setBackgroundBrush(QBrush(QColor(15, 15, 20))) # Fondo azul oscuro muy opaco (Espacio)
        
        # Variables de estado
        self.topology = {}
        self.nodes = {}       # Diccionario id: QGraphicsEllipseItem
        self.labels = {}      # Diccionario id: QGraphicsTextItem
        self.lines = []       # Aristas (Stargates/JumpBridges)
        
        # Factor de escala visual: Cuantos pixeles equivale "1.0" unidad relativa del cartógrafo
        self.SCALE_FACTOR = 80.0

    def wheelEvent(self, event):
        """Implementa el Zoom con la rueda del ratón."""
        zoomInFactor = 1.15
        zoomOutFactor = 1 / zoomInFactor

        # Prevenir hacer zoom "infinito" para no perderse
        if event.angleDelta().y() > 0:
            zoomFactor = zoomInFactor
        else:
            zoomFactor = zoomOutFactor
            
        self.scale(zoomFactor, zoomFactor)

    def draw_map(self, topology_data, center_system_id):
        """
        Recibe los datos crudos del cartógrafo y dibuja las constelaciones.
        topology_data: dict devuelto por Cartographer.get_local_map()
        """
        self.scene.clear()
        self.nodes.clear()
        self.labels.clear()
        self.lines.clear()
        self.topology = topology_data
        
        # Pinceles (Brushes) y Lápices (Pens)
        pen_stargate = QPen(QColor(80, 80, 100), 2)
        pen_jumpbridge = QPen(QColor(0, 150, 200), 2, Qt.PenStyle.DashLine)
        
        brush_neutral = QBrush(QColor(200, 200, 200))
        brush_player = QBrush(QColor(0, 255, 255)) # Cían
        
        # Primero paso: Dibujar conexiones (Aristas atrás)
        drawn_connections = set()
        for sys_id, data in self.topology.items():
            pos1 = self._get_screen_pos(data['x_rel'], data['z_rel'])
            
            # Stargates
            for n_id in data.get('stargate_connections', []):
                if n_id in self.topology: # Solo si el vecino está en la zona mapeada
                    edge = tuple(sorted((sys_id, n_id)))
                    if edge not in drawn_connections:
                        n_data = self.topology[n_id]
                        pos2 = self._get_screen_pos(n_data['x_rel'], n_data['z_rel'])
                        line = self.scene.addLine(pos1.x(), pos1.y(), pos2.x(), pos2.y(), pen_stargate)
                        line.setZValue(-1) # Enviar atrás
                        self.lines.append(line)
                        drawn_connections.add(edge)
                        
            # Jump Bridges
            for n_id in data.get('jump_bridge_connections', []):
                if n_id in self.topology:
                    edge = tuple(sorted((sys_id, n_id)))
                    if edge not in drawn_connections: # Usamos otro set si queremos permitir doble linea, por ahora simple
                        n_data = self.topology[n_id]
                        pos2 = self._get_screen_pos(n_data['x_rel'], n_data['z_rel'])
                        line = self.scene.addLine(pos1.x(), pos1.y(), pos2.x(), pos2.y(), pen_jumpbridge)
                        line.setZValue(-1)
                        self.lines.append(line)
                        drawn_connections.add(edge)

        # Segundo paso: Dibujar Nodos (Círculos flotantes)
        node_radius = 6.0
        
        font = QFont("Arial", 8, QFont.Weight.Bold)
        text_color = QColor(220, 220, 220)
        
        for sys_id, data in self.topology.items():
            pos = self._get_screen_pos(data['x_rel'], data['z_rel'])
            
            # Determinar color
            brush = brush_player if sys_id == center_system_id else brush_neutral
            
            # Crear círculo
            ellipse = self.scene.addEllipse(
                pos.x() - node_radius, pos.y() - node_radius, 
                node_radius*2, node_radius*2, 
                QPen(Qt.PenStyle.NoPen), brush
            )
            ellipse.setZValue(1)
            self.nodes[sys_id] = ellipse
            
            # Crear Etiqueta (Nombre Sistema)
            text = self.scene.addText(data['name'], font)
            text.setDefaultTextColor(text_color)
            # Centrar sobre nodo
            tr = text.boundingRect()
            text.setPos(pos.x() - (tr.width()/2), pos.y() + node_radius)
            text.setZValue(2)
            self.labels[sys_id] = text

    def update_threat(self, system_name, status):
        """
        Cambia el color de un nodo si el Intel_Tailer lo reportó como hostil.
        """
        color = QColor(255, 50, 50) if status.upper() in ["HOSTILE", "NO_VIS"] else QColor(200, 200, 200)
        
        for sys_id, data in self.topology.items():
            if data['name'].lower() == system_name.lower():
                node = self.nodes.get(sys_id)
                if node:
                    # Lo pintamos de rojo o lo devolvemos a neutro (siempre y cuando no sea cian/el jugador, por si acaso)
                    if node.brush().color() != QColor(0, 255, 255):
                        # Efecto de pulso u opacidad
                        new_brush = QBrush(color)
                        node.setBrush(new_brush)
                        # Engordar nodo para que destaque
                        radius = 9.0 if status.upper() in ["HOSTILE", "NO_VIS"] else 6.0
                        pos = self._get_screen_pos(data['x_rel'], data['z_rel'])
                        node.setRect(pos.x() - radius, pos.y() - radius, radius*2, radius*2)
                break

    def _get_screen_pos(self, x_rel, z_rel):
        """Transforma las coordenadas lógicas al plano X/Y de PyQt."""
        # En QGraphicsView el Y aumenta hacia abajo. En Cartographer la Z la usamos como 'Norte'.
        # Así que invertimos la Z.
        return QPointF(x_rel * self.SCALE_FACTOR, -z_rel * self.SCALE_FACTOR)
