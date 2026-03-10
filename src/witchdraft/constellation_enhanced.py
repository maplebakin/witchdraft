"""
WitchDraft Enhanced Constellation View

Extends the Spiral Constellation to display:
- Character/entity nodes with color palette swatches
- Thematic connections with color-coded edges
- Toggleable visualization layers
- Click-to-inspect detail popups
"""

from __future__ import annotations

import math
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, QPointF, QRectF, pyqtSignal
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QPainter,
    QPainterPath,
    QPen,
    QLinearGradient,
)
from PyQt6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsPathItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QToolTip,
    QVBoxLayout,
    QWidget,
    QFrame,
    QScrollArea,
    QGraphicsProxyWidget,
)


# =============================================================================
# COLOR CONSTANTS - Warm, Cozy Sanctuary Theme
# =============================================================================

# Base colors - warm, inviting tones
TEXT_COLOR = "#5A5550"  # Warm gray
NODE_FILL = "#E8D4A8"  # Soft warm gold
NODE_STROKE = "#C9B896"  # Warm border
SEAM_COLOR = "#D4CBBB"  # Warm taupe

# Accent color for highlights
ACCENT_COLOR = "#A8C5A2"  # Soft sage green
ACCENT_HOVER = "#97B891"  # Slightly deeper sage

# Warm sanctuary UI colors
BG_COLOR = "#F7F5F0"  # Warm off-white
PANEL_BG = "rgba(253, 252, 250, 0.95)"  # Warm white with transparency
BORDER_COLOR = "#E5E1D8"  # Warm border
BORDER_RADIUS = "12px"
BORDER_RADIUS_SM = "8px"

# Theme colors for thematic connections - softened, warmer palette
THEME_COLORS = {
    "redemption": "#8DBF7E",    # Soft sage green
    "loss": "#8A9BC4",          # Muted lavender blue
    "growth": "#8BC48A",        # Gentle leaf green
    "love": "#E8A0B4",          # Soft rose
    "betrayal": "#A08070",      # Warm brown
    "power": "#E8C078",         # Soft amber
    "fear": "#9AABB8",          # Soft blue-gray
    "hope": "#E8D878",          # Warm yellow
    "isolation": "#A8B8C0",     # Cool sage
    "vengeance": "#D09090",     # Muted rose red
    "identity": "#B898C8",      # Soft purple
    "sacrifice": "#D8A088",     # Warm coral
    "corruption": "#707880",    # Soft slate
    "innocence": "#A8D0E8",     # Soft sky blue
    "mystery": "#9888B0",       # Dusty purple
}

# Default theme color for unknown themes
DEFAULT_THEME_COLOR = "#B8B0A8"

EMOTION_COLORS = {
    "joy": "#F2C94C",
    "sadness": "#8EA6D8",
    "anger": "#D9877E",
    "fear": "#9AA3B3",
    "surprise": "#C6A3E8",
    "disgust": "#8DB58E",
    "trust": "#90C7B7",
    "anticipation": "#E0B279",
}


# =============================================================================
# DATA STRUCTURES
# =============================================================================


@dataclass
class EntityInfo:
    """Information about an entity for visualization."""
    id: int
    name: str
    entity_type: str
    palette_colors: list[str]  # List of hex colors
    themes: list[tuple[str, int]]  # (theme_name, intensity) pairs
    traits: list[str]
    archetypes: list[str]


@dataclass
class SceneInfo:
    """Information about a scene for visualization."""
    id: int
    title: str
    position: int
    entities: list[int]  # Entity IDs
    atmospheres: list[str]
    dominant_theme: Optional[str]
    top_emotion: Optional[str] = None
    emotion_intensity: int = 0


# =============================================================================
# GRAPHICS ITEMS
# =============================================================================


class ColorSwatch(QGraphicsRectItem):
    """A small color swatch for displaying palette colors."""

    def __init__(
        self,
        color: str,
        size: float = 8,
        parent: QGraphicsItem | None = None
    ) -> None:
        super().__init__(-size/2, -size/2, size, size, parent)
        self.color = color
        self.setBrush(QColor(color))
        self.setPen(QPen(QColor("#00000030"), 0.5))
        self.setAcceptedMouseButtons(Qt.MouseButton.NoButton)


class PaletteRing(QGraphicsItem):
    """A ring of color swatches around an entity node."""

    def __init__(
        self,
        colors: list[str],
        radius: float = 18,
        swatch_size: float = 6,
        parent: QGraphicsItem | None = None
    ) -> None:
        super().__init__(parent)
        self.colors = colors[:8]  # Limit to 8 colors max
        self.radius = radius
        self.swatch_size = swatch_size
        self._swatches: list[ColorSwatch] = []
        self._create_swatches()
        self.setAcceptedMouseButtons(Qt.MouseButton.NoButton)

    def _create_swatches(self) -> None:
        if not self.colors:
            return

        angle_step = 2 * math.pi / max(len(self.colors), 1)
        for i, color in enumerate(self.colors):
            angle = i * angle_step - math.pi / 2  # Start from top
            x = self.radius * math.cos(angle)
            y = self.radius * math.sin(angle)

            swatch = ColorSwatch(color, self.swatch_size, self)
            swatch.setPos(x, y)
            self._swatches.append(swatch)

    def boundingRect(self) -> QRectF:
        r = self.radius + self.swatch_size
        return QRectF(-r, -r, 2*r, 2*r)

    def paint(self, painter, option, widget=None) -> None:
        # No painting needed - children handle it
        pass


class EntityNode(QGraphicsEllipseItem):
    """An entity (character/location) node with palette visualization."""

    def __init__(
        self,
        entity: EntityInfo,
        show_palette: bool = True,
        parent: QGraphicsItem | None = None
    ) -> None:
        # Size based on entity type
        size = 20 if entity.entity_type == "PERSON" else 16
        super().__init__(-size/2, -size/2, size, size, parent)

        self.entity = entity
        self.show_palette = show_palette
        self.connected_nodes: list[EntityNode] = []
        self.theme_edges: list[ThemeEdge] = []

        # Visual setup
        self._setup_appearance()
        self._setup_label()
        if show_palette and entity.palette_colors:
            self._setup_palette_ring()

        # Interactivity
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable
            | QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )
        self.setAcceptHoverEvents(True)
        self.setZValue(3)

    def _setup_appearance(self) -> None:
        """Set up node color based on entity type and themes."""
        if self.entity.entity_type == "PERSON":
            # Use dominant theme color if available
            if self.entity.themes:
                theme_name, intensity = self.entity.themes[0]
                base_color = THEME_COLORS.get(theme_name, NODE_FILL)
                # Blend with default based on intensity
                color = self._blend_color(NODE_FILL, base_color, intensity / 5.0)
            else:
                color = NODE_FILL
            self.setBrush(QColor(color))
            pen = QPen(QColor(NODE_STROKE), 1.5)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            self.setPen(pen)
        else:
            # Locations use a soft sage tone matching the accent
            self.setBrush(QColor("#C8DEC5"))
            pen = QPen(QColor("#A8C5A2"), 1.5)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            self.setPen(pen)

    def _setup_label(self) -> None:
        """Create the name label."""
        name = self.entity.name[:15]
        if len(self.entity.name) > 15:
            name += "..."

        self.label = QGraphicsSimpleTextItem(name, self)
        self.label.setBrush(QColor(TEXT_COLOR))
        font = QFont()
        font.setPointSize(8)
        self.label.setFont(font)

        # Position below node
        label_width = self.label.boundingRect().width()
        self.label.setPos(-label_width / 2, 12)
        self.label.setAcceptedMouseButtons(Qt.MouseButton.NoButton)

    def _setup_palette_ring(self) -> None:
        """Create the palette color ring."""
        self.palette_ring = PaletteRing(
            self.entity.palette_colors,
            radius=16,
            swatch_size=5,
            parent=self
        )

    def _blend_color(self, color1: str, color2: str, ratio: float) -> str:
        """Blend two hex colors."""
        c1 = QColor(color1)
        c2 = QColor(color2)
        r = int(c1.red() * (1 - ratio) + c2.red() * ratio)
        g = int(c1.green() * (1 - ratio) + c2.green() * ratio)
        b = int(c1.blue() * (1 - ratio) + c2.blue() * ratio)
        return QColor(r, g, b).name()

    def add_theme_edge(self, edge: "ThemeEdge") -> None:
        self.theme_edges.append(edge)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            for edge in self.theme_edges:
                edge.update_path()
        return super().itemChange(change, value)

    def hoverEnterEvent(self, event) -> None:
        """Show tooltip with entity details."""
        self.setPen(QPen(QColor(ACCENT_COLOR), 2.5))  # Warm sage highlight

        # Build tooltip
        lines = [f"<b>{self.entity.name}</b> ({self.entity.entity_type})"]

        if self.entity.archetypes:
            lines.append(f"<i>Archetype: {', '.join(self.entity.archetypes)}</i>")

        if self.entity.themes:
            theme_strs = [f"{t[0]} ({t[1]})" for t in self.entity.themes[:3]]
            lines.append(f"Themes: {', '.join(theme_strs)}")

        if self.entity.traits:
            lines.append(f"Traits: {', '.join(self.entity.traits[:5])}")

        if self.entity.palette_colors:
            color_preview = " ".join(
                f'<span style="color:{c}">&#9632;</span>'
                for c in self.entity.palette_colors[:5]
            )
            lines.append(f"Palette: {color_preview}")

        tooltip = "<br>".join(lines)
        QToolTip.showText(event.screenPos(), tooltip)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event) -> None:
        self._setup_appearance()  # Reset pen
        QToolTip.hideText()
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.RightButton:
            # Right-click shows detailed popup
            self._show_detail_popup(event.screenPos())
            event.accept()
            return
        super().mousePressEvent(event)

    def _show_detail_popup(self, pos) -> None:
        """Show a detailed popup for this entity."""
        # This will be handled by the parent view
        view = self.scene().views()[0] if self.scene() and self.scene().views() else None
        if view and hasattr(view, 'show_entity_details'):
            view.show_entity_details(self.entity)


class ThemeEdge(QGraphicsPathItem):
    """A color-coded edge showing thematic connection between entities."""

    def __init__(
        self,
        start: EntityNode,
        end: EntityNode,
        theme: str,
        intensity: int = 3
    ) -> None:
        super().__init__()
        self.start = start
        self.end = end
        self.theme = theme
        self.intensity = intensity

        # Register with nodes
        self.start.add_theme_edge(self)
        self.end.add_theme_edge(self)

        # Visual setup
        color = THEME_COLORS.get(theme, DEFAULT_THEME_COLOR)
        pen = QPen(QColor(color))
        pen.setWidthF(0.8 + (intensity * 0.4))  # Width based on intensity
        pen.setStyle(Qt.PenStyle.DashLine if intensity < 3 else Qt.PenStyle.SolidLine)
        self.setPen(pen)
        self.setZValue(0)  # Behind everything
        self.setAcceptHoverEvents(True)
        self.update_path()

    def update_path(self) -> None:
        """Update the curved path between nodes."""
        start = self.start.pos()
        end = self.end.pos()
        mid = (start + end) / 2

        dx = end.x() - start.x()
        dy = end.y() - start.y()
        length = math.hypot(dx, dy) or 1.0

        # Perpendicular offset for curve
        norm = QPointF(-dy / length, dx / length)
        offset = norm * min(40.0, length / 4)
        ctrl = mid + offset

        path = QPainterPath()
        path.moveTo(start)
        path.quadTo(ctrl, end)
        self.setPath(path)

    def hoverEnterEvent(self, event) -> None:
        tooltip = f"<b>Theme:</b> {self.theme.title()}<br><b>Intensity:</b> {self.intensity}/5"
        QToolTip.showText(event.screenPos(), tooltip)
        # Highlight
        color = THEME_COLORS.get(self.theme, DEFAULT_THEME_COLOR)
        pen = QPen(QColor(color))
        pen.setWidthF(2.5)
        self.setPen(pen)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event) -> None:
        # Reset
        color = THEME_COLORS.get(self.theme, DEFAULT_THEME_COLOR)
        pen = QPen(QColor(color))
        pen.setWidthF(0.8 + (self.intensity * 0.4))
        pen.setStyle(Qt.PenStyle.DashLine if self.intensity < 3 else Qt.PenStyle.SolidLine)
        self.setPen(pen)
        QToolTip.hideText()
        super().hoverLeaveEvent(event)


class SceneNodeEnhanced(QGraphicsEllipseItem):
    """Enhanced scene node with atmosphere visualization."""

    def __init__(self, scene_info: SceneInfo) -> None:
        super().__init__(-12, -12, 24, 24)
        self.scene_info = scene_info
        self.edges: list = []

        # Color based on atmosphere/theme
        self._setup_appearance()
        self._setup_label()

        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable
            | QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )
        self.setAcceptHoverEvents(True)
        self.setZValue(2)

    def _setup_appearance(self) -> None:
        """Set appearance based on scene atmosphere."""
        if self.scene_info.dominant_theme:
            color = THEME_COLORS.get(self.scene_info.dominant_theme, NODE_FILL)
            self.setBrush(QColor(color))
        elif self.scene_info.atmospheres:
            # Map atmosphere to color
            atm = self.scene_info.atmospheres[0]
            atm_colors = {
                "ominous": "#455A64",
                "serene": "#81D4FA",
                "chaotic": "#EF5350",
                "magical": "#7E57C2",
                "decaying": "#8D6E63",
                "vibrant": "#66BB6A",
                "cold": "#90CAF9",
                "warm": "#FFCC80",
            }
            color = atm_colors.get(atm, NODE_FILL)
            self.setBrush(QColor(color))
        else:
            self.setBrush(QColor(NODE_FILL))

        self.setPen(QPen(QColor(NODE_STROKE)))

    def _setup_label(self) -> None:
        title = self.scene_info.title[:18]
        self.label = QGraphicsSimpleTextItem(title, self)
        self.label.setBrush(QColor(TEXT_COLOR))
        self.label.setPos(16, -6)
        self.label.setAcceptedMouseButtons(Qt.MouseButton.NoButton)

        if self.scene_info.top_emotion:
            emotion = self.scene_info.top_emotion.title()
            if self.scene_info.emotion_intensity > 0:
                emotion = f"{emotion} ({self.scene_info.emotion_intensity})"
            self.emotion_label = QGraphicsSimpleTextItem(emotion, self)
            self.emotion_label.setBrush(
                QColor(EMOTION_COLORS.get(self.scene_info.top_emotion, "#8F8A83"))
            )
            font = QFont()
            font.setPointSize(7)
            font.setItalic(True)
            self.emotion_label.setFont(font)
            self.emotion_label.setPos(16, 8)
            self.emotion_label.setAcceptedMouseButtons(Qt.MouseButton.NoButton)

    def add_edge(self, edge) -> None:
        self.edges.append(edge)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            for edge in self.edges:
                edge.update_path()
        return super().itemChange(change, value)

    def hoverEnterEvent(self, event) -> None:
        self.setPen(QPen(QColor(ACCENT_COLOR), 2.5))  # Warm sage highlight

        lines = [f"<b>{self.scene_info.title}</b>"]
        if self.scene_info.atmospheres:
            lines.append(f"Atmosphere: {', '.join(self.scene_info.atmospheres)}")
        if self.scene_info.dominant_theme:
            lines.append(f"Theme: {self.scene_info.dominant_theme.title()}")
        if self.scene_info.top_emotion:
            lines.append(f"Emotion: {self.scene_info.top_emotion.title()} ({self.scene_info.emotion_intensity})")
        lines.append(f"Entities: {len(self.scene_info.entities)}")

        QToolTip.showText(event.screenPos(), "<br>".join(lines))
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event) -> None:
        self.setPen(QPen(QColor(NODE_STROKE)))
        QToolTip.hideText()
        super().hoverLeaveEvent(event)


class SceneSeamEnhanced(QGraphicsPathItem):
    """Enhanced seam with shared entity information."""

    def __init__(
        self,
        start: SceneNodeEnhanced,
        end: SceneNodeEnhanced,
        shared_count: int
    ) -> None:
        super().__init__()
        self.start = start
        self.end = end
        self.shared_count = shared_count
        self.start.add_edge(self)
        self.end.add_edge(self)

        # Width based on shared entity count
        pen = QPen(QColor(SEAM_COLOR))
        pen.setWidthF(0.8 + (min(shared_count, 5) * 0.3))
        self.setPen(pen)
        self.setZValue(1)
        self.setAcceptHoverEvents(True)
        self.update_path()

    def update_path(self) -> None:
        start = self.start.pos()
        end = self.end.pos()
        mid = (start + end) / 2
        dx = end.x() - start.x()
        dy = end.y() - start.y()
        length = math.hypot(dx, dy) or 1.0
        norm = QPointF(-dy / length, dx / length)
        offset = norm * min(60.0, length / 3)
        ctrl = mid + offset
        path = QPainterPath()
        path.moveTo(start)
        path.quadTo(ctrl, end)
        self.setPath(path)

    def hoverEnterEvent(self, event) -> None:
        tooltip = f"Shared entities: {self.shared_count}"
        QToolTip.showText(event.screenPos(), tooltip)
        pen = QPen(QColor(ACCENT_COLOR))  # Warm sage highlight
        pen.setWidthF(2.5)
        self.setPen(pen)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event) -> None:
        pen = QPen(QColor(SEAM_COLOR))
        pen.setWidthF(0.8 + (min(self.shared_count, 5) * 0.3))
        self.setPen(pen)
        QToolTip.hideText()
        super().hoverLeaveEvent(event)


# =============================================================================
# LAYER TOGGLE WIDGET
# =============================================================================


class LayerTogglePanel(QFrame):
    """Panel with toggles for different visualization layers."""

    layers_changed = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("layer-toggle-panel")
        # Warm, cozy panel styling with soft shadows
        self.setStyleSheet(f"""
            #layer-toggle-panel {{
                background: {PANEL_BG};
                border: 1px solid {BORDER_COLOR};
                border-radius: {BORDER_RADIUS_SM};
                padding: 6px 8px;
            }}
            QPushButton {{
                border: 1px solid {BORDER_COLOR};
                border-radius: 6px;
                padding: 6px 12px;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #FDFCFA, stop:1 #F5F2EC);
                font-size: 11px;
                font-weight: 500;
                color: {TEXT_COLOR};
            }}
            QPushButton:checked {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {ACCENT_COLOR}, stop:1 {ACCENT_HOVER});
                color: #2D3B2D;
                border-color: #8FB089;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #FFFFFF, stop:1 #F9F7F3);
                border-color: #D5D1C8;
            }}
            QPushButton:checked:hover {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #B5D1AF, stop:1 {ACCENT_COLOR});
            }}
            QPushButton:disabled {{
                background: #F0EDE5;
                color: #9A958D;
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Scene layer (always visible, not toggleable)
        self.btn_scenes = QPushButton("Scenes")
        self.btn_scenes.setCheckable(True)
        self.btn_scenes.setChecked(True)
        self.btn_scenes.setEnabled(False)  # Always on
        layout.addWidget(self.btn_scenes)

        # Entity layer
        self.btn_entities = QPushButton("Characters")
        self.btn_entities.setCheckable(True)
        self.btn_entities.setChecked(True)
        self.btn_entities.clicked.connect(self.layers_changed.emit)
        layout.addWidget(self.btn_entities)

        # Palette layer
        self.btn_palettes = QPushButton("Palettes")
        self.btn_palettes.setCheckable(True)
        self.btn_palettes.setChecked(False)
        self.btn_palettes.clicked.connect(self.layers_changed.emit)
        layout.addWidget(self.btn_palettes)

        # Theme connections layer
        self.btn_themes = QPushButton("Themes")
        self.btn_themes.setCheckable(True)
        self.btn_themes.setChecked(True)
        self.btn_themes.clicked.connect(self.layers_changed.emit)
        layout.addWidget(self.btn_themes)

    @property
    def show_entities(self) -> bool:
        return self.btn_entities.isChecked()

    @property
    def show_palettes(self) -> bool:
        return self.btn_palettes.isChecked()

    @property
    def show_themes(self) -> bool:
        return self.btn_themes.isChecked()


class LegendPanel(QFrame):
    """Small always-visible key for reading the visualization."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("constellation-legend")
        self.setStyleSheet(f"""
            #constellation-legend {{
                background: {PANEL_BG};
                border: 1px solid {BORDER_COLOR};
                border-radius: {BORDER_RADIUS_SM};
            }}
            QLabel {{
                color: {TEXT_COLOR};
                font-size: 10px;
            }}
            QLabel#legend-title {{
                font-size: 11px;
                font-weight: 600;
                color: #4A4540;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(3)

        title = QLabel("Legend")
        title.setObjectName("legend-title")
        layout.addWidget(title)
        layout.addWidget(QLabel("Scene node: chapter/scene point"))
        layout.addWidget(QLabel("Italic tag near scene: top emotion"))
        layout.addWidget(QLabel("Dashed/Solid edge: shared theme strength"))


# =============================================================================
# ENTITY DETAIL PANEL
# =============================================================================


class EntityDetailPanel(QFrame):
    """Panel showing detailed entity information."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("entity-detail-panel")
        # Warm, inviting detail panel styling
        self.setStyleSheet(f"""
            #entity-detail-panel {{
                background: {PANEL_BG};
                border: 1px solid {BORDER_COLOR};
                border-radius: {BORDER_RADIUS};
            }}
            QLabel {{
                font-size: 11px;
                color: {TEXT_COLOR};
            }}
            #entity-name {{
                font-size: 14px;
                font-weight: 600;
                color: #4A4540;
            }}
            #section-header {{
                font-weight: 600;
                color: {ACCENT_HOVER};
                margin-top: 10px;
                padding-top: 6px;
                border-top: 1px solid #EBE7DE;
            }}
            QScrollArea {{
                background: transparent;
                border: none;
            }}
            QScrollBar:vertical {{
                background: transparent;
                width: 8px;
                margin: 2px;
            }}
            QScrollBar::handle:vertical {{
                background: rgba(180, 175, 165, 0.4);
                border-radius: 4px;
                min-height: 30px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: rgba(160, 155, 145, 0.6);
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0;
            }}
        """)
        self.setFixedWidth(220)
        self.setMaximumHeight(300)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(4)

        # Close button with warm styling
        close_btn = QPushButton("×")
        close_btn.setFixedSize(24, 24)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                border: none;
                background: transparent;
                font-size: 18px;
                font-weight: 600;
                color: #9A958D;
                border-radius: 12px;
            }}
            QPushButton:hover {{
                color: #D09090;
                background: rgba(208, 144, 144, 0.1);
            }}
        """)
        close_btn.clicked.connect(self.hide)

        header = QHBoxLayout()
        self.name_label = QLabel()
        self.name_label.setObjectName("entity-name")
        header.addWidget(self.name_label)
        header.addStretch()
        header.addWidget(close_btn)
        layout.addLayout(header)

        self.type_label = QLabel()
        layout.addWidget(self.type_label)

        # Scrollable content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        self.content_layout = QVBoxLayout(content)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(2)
        scroll.setWidget(content)
        layout.addWidget(scroll)

        # Palette display
        self.palette_container = QWidget()
        self.palette_layout = QHBoxLayout(self.palette_container)
        self.palette_layout.setContentsMargins(0, 0, 0, 0)
        self.palette_layout.setSpacing(2)

        self.hide()

    def show_entity(self, entity: EntityInfo) -> None:
        """Display entity details."""
        self.name_label.setText(entity.name)
        self.type_label.setText(f"Type: {entity.entity_type}")

        # Clear previous content
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Palette colors
        if entity.palette_colors:
            header = QLabel("Palette")
            header.setObjectName("section-header")
            self.content_layout.addWidget(header)

            palette_widget = QWidget()
            palette_layout = QHBoxLayout(palette_widget)
            palette_layout.setContentsMargins(0, 4, 0, 4)
            palette_layout.setSpacing(3)

            for color in entity.palette_colors[:8]:
                swatch = QLabel()
                swatch.setFixedSize(20, 20)
                swatch.setStyleSheet(f"""
                    background: {color};
                    border: 1px solid #00000030;
                    border-radius: 2px;
                """)
                swatch.setToolTip(color)
                palette_layout.addWidget(swatch)

            palette_layout.addStretch()
            self.content_layout.addWidget(palette_widget)

        # Archetypes
        if entity.archetypes:
            header = QLabel("Archetypes")
            header.setObjectName("section-header")
            self.content_layout.addWidget(header)
            self.content_layout.addWidget(QLabel(", ".join(entity.archetypes)))

        # Themes
        if entity.themes:
            header = QLabel("Themes")
            header.setObjectName("section-header")
            self.content_layout.addWidget(header)

            for theme, intensity in entity.themes[:5]:
                theme_widget = QWidget()
                theme_layout = QHBoxLayout(theme_widget)
                theme_layout.setContentsMargins(0, 0, 0, 0)
                theme_layout.setSpacing(4)

                color = THEME_COLORS.get(theme, DEFAULT_THEME_COLOR)
                indicator = QLabel()
                indicator.setFixedSize(10, 10)
                indicator.setStyleSheet(f"background: {color}; border-radius: 5px;")
                theme_layout.addWidget(indicator)

                theme_layout.addWidget(QLabel(f"{theme.title()} ({intensity}/5)"))
                theme_layout.addStretch()
                self.content_layout.addWidget(theme_widget)

        # Traits
        if entity.traits:
            header = QLabel("Traits")
            header.setObjectName("section-header")
            self.content_layout.addWidget(header)
            self.content_layout.addWidget(QLabel(", ".join(entity.traits[:10])))

        self.content_layout.addStretch()
        self.show()


# =============================================================================
# ENHANCED CONSTELLATION VIEW
# =============================================================================


class EnhancedConstellationView(QGraphicsView):
    """
    Enhanced constellation view with toggleable layers.

    Layers:
    - Scenes (always visible): Spiral layout of narrative scenes
    - Characters: Entity nodes positioned near their most frequent scene
    - Palettes: Color swatches around entity nodes
    - Themes: Color-coded edges showing thematic connections
    """

    def __init__(self, db_path: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._db_path = db_path
        self._setup_view()
        self._setup_ui()

        # Layer visibility
        self._show_entities = self._layer_panel.show_entities
        self._show_palettes = self._layer_panel.show_palettes
        self._show_themes = self._layer_panel.show_themes

        # Data caches
        self._scene_nodes: dict[int, SceneNodeEnhanced] = {}
        self._entity_nodes: dict[int, EntityNode] = {}
        self._theme_edges: list[ThemeEdge] = []

        self.refresh()

    def _setup_view(self) -> None:
        """Configure the QGraphicsView."""
        self.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self._gscene = QGraphicsScene(self)
        self.setScene(self._gscene)
        self._panning = False
        self._pan_start = QPointF()

        # Warm, cozy background styling
        self.setStyleSheet(f"""
            QGraphicsView {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #FAF8F4, stop:0.5 {BG_COLOR}, stop:1 #F5F2EC);
                border: none;
                border-radius: {BORDER_RADIUS_SM};
            }}
        """)
        self._gscene.setBackgroundBrush(QColor("#FAF8F4"))

    def _setup_ui(self) -> None:
        """Set up overlay UI elements."""
        # Layer toggle panel
        self._layer_panel = LayerTogglePanel(self)
        self._layer_panel.layers_changed.connect(self._on_layers_changed)
        self._layer_panel.move(10, 10)

        # Legend panel
        self._legend_panel = LegendPanel(self)
        self._legend_panel.move(10, 60)

        # Entity detail panel
        self._detail_panel = EntityDetailPanel(self)
        self._detail_panel.move(10, 120)

    def set_db_path(self, db_path: Path) -> None:
        self._db_path = db_path

    def _on_layers_changed(self) -> None:
        """Handle layer toggle changes."""
        self._show_entities = self._layer_panel.show_entities
        self._show_palettes = self._layer_panel.show_palettes
        self._show_themes = self._layer_panel.show_themes
        self._update_layer_visibility()

    def _update_layer_visibility(self) -> None:
        """Update visibility of items based on layer settings."""
        # Entity nodes
        for node in self._entity_nodes.values():
            node.setVisible(self._show_entities)
            if hasattr(node, 'palette_ring'):
                node.palette_ring.setVisible(self._show_entities and self._show_palettes)

        # Theme edges
        for edge in self._theme_edges:
            edge.setVisible(self._show_themes)

    def refresh(self) -> None:
        """Reload and redraw the constellation."""
        self._gscene.clear()
        self._scene_nodes.clear()
        self._entity_nodes.clear()
        self._theme_edges.clear()

        if not self._db_path.exists():
            self._gscene.addText("No vault.db found.")
            return

        # Load data
        scenes, entities, scene_entities, entity_themes = self._load_data()

        if not scenes:
            self._gscene.addText("No scenes to map yet.")
            return

        # Draw scene spiral
        self._draw_scene_spiral(scenes, scene_entities)

        # Draw entity nodes (initially hidden)
        self._draw_entity_nodes(entities, scenes, scene_entities)

        # Draw theme connections (initially hidden)
        self._draw_theme_connections(entities, entity_themes)

        # Apply visibility
        self._update_layer_visibility()

        # Fit scene
        self._gscene.setSceneRect(
            self._gscene.itemsBoundingRect().adjusted(-80, -80, 80, 80)
        )

    def _load_data(self):
        """Load all visualization data from database."""
        conn = sqlite3.connect(self._db_path)
        scenes = []
        entities = {}
        scene_entities = {}
        entity_themes = {}

        try:
            # Load scenes
            try:
                rows = conn.execute(
                    "SELECT id, title, position FROM scenes ORDER BY position"
                ).fetchall()
                for row in rows:
                    scenes.append(SceneInfo(
                        id=row[0],
                        title=row[1],
                        position=row[2],
                        entities=[],
                        atmospheres=[],
                        dominant_theme=None
                    ))
            except sqlite3.OperationalError:
                return [], {}, {}, {}

            # Load scene-entity relationships
            try:
                rows = conn.execute(
                    "SELECT scene_id, entity_id FROM scene_entities"
                ).fetchall()
                for scene_id, entity_id in rows:
                    scene_entities.setdefault(scene_id, set()).add(entity_id)
                    # Also update scene info
                    for scene in scenes:
                        if scene.id == scene_id:
                            scene.entities.append(entity_id)
            except sqlite3.OperationalError:
                pass

            # Load scene atmospheres
            try:
                rows = conn.execute(
                    "SELECT scene_id, atmosphere FROM scene_atmospheres"
                ).fetchall()
                for scene_id, atmosphere in rows:
                    for scene in scenes:
                        if scene.id == scene_id:
                            scene.atmospheres.append(atmosphere)
            except sqlite3.OperationalError:
                pass

            # Load scene dominant themes
            try:
                rows = conn.execute(
                    """
                    SELECT st.scene_id, t.name, st.intensity
                    FROM scene_themes st
                    JOIN themes t ON st.theme_id = t.id
                    ORDER BY st.scene_id, st.intensity DESC
                    """
                ).fetchall()
                for scene_id, theme_name, _intensity in rows:
                    for scene in scenes:
                        if scene.id == scene_id and scene.dominant_theme is None:
                            scene.dominant_theme = theme_name
                            break
            except sqlite3.OperationalError:
                pass

            # Load top scene emotion labels
            try:
                rows = conn.execute(
                    """
                    SELECT scene_id, emotion, intensity
                    FROM scene_emotions
                    ORDER BY scene_id, intensity DESC
                    """
                ).fetchall()
                for scene_id, emotion, intensity in rows:
                    for scene in scenes:
                        if scene.id == scene_id and scene.top_emotion is None:
                            scene.top_emotion = emotion
                            scene.emotion_intensity = int(intensity)
                            break
            except sqlite3.OperationalError:
                pass

            # Load entities
            try:
                rows = conn.execute(
                    "SELECT id, name, type FROM entities"
                ).fetchall()
                for row in rows:
                    entities[row[0]] = EntityInfo(
                        id=row[0],
                        name=row[1],
                        entity_type=row[2],
                        palette_colors=[],
                        themes=[],
                        traits=[],
                        archetypes=[]
                    )
            except sqlite3.OperationalError:
                pass

            # Load entity palette colors
            try:
                rows = conn.execute("""
                    SELECT ep.entity_id, pc.hex_code
                    FROM entity_palettes ep
                    JOIN palette_colors pc ON ep.palette_id = pc.palette_id
                    ORDER BY ep.entity_id, pc.position
                """).fetchall()
                for entity_id, hex_code in rows:
                    if entity_id in entities:
                        entities[entity_id].palette_colors.append(hex_code)
            except sqlite3.OperationalError:
                pass

            # Load entity color hints as fallback for palette
            try:
                rows = conn.execute("""
                    SELECT entity_id, color_family, SUM(weight) as w
                    FROM entity_color_hints
                    GROUP BY entity_id, color_family
                    ORDER BY entity_id, w DESC
                """).fetchall()
                # Map color families to hex
                COLOR_FAMILY_HEX = {
                    "red": "#E53935",
                    "blue": "#1E88E5",
                    "green": "#43A047",
                    "yellow": "#FDD835",
                    "purple": "#8E24AA",
                    "orange": "#FB8C00",
                    "black": "#212121",
                    "white": "#FAFAFA",
                    "gray": "#757575",
                    "brown": "#6D4C41",
                }
                for entity_id, color_family, _ in rows:
                    if entity_id in entities and not entities[entity_id].palette_colors:
                        hex_code = COLOR_FAMILY_HEX.get(color_family, "#9E9E9E")
                        if hex_code not in entities[entity_id].palette_colors:
                            entities[entity_id].palette_colors.append(hex_code)
            except sqlite3.OperationalError:
                pass

            # Load entity themes
            try:
                rows = conn.execute("""
                    SELECT et.entity_id, t.name, et.intensity
                    FROM entity_themes et
                    JOIN themes t ON et.theme_id = t.id
                    ORDER BY et.entity_id, et.intensity DESC
                """).fetchall()
                for entity_id, theme_name, intensity in rows:
                    if entity_id in entities:
                        entities[entity_id].themes.append((theme_name, intensity))
                        entity_themes.setdefault(entity_id, []).append((theme_name, intensity))
            except sqlite3.OperationalError:
                pass

            # Load enhanced traits
            try:
                rows = conn.execute("""
                    SELECT entity_id, trait, category
                    FROM enhanced_traits
                    ORDER BY entity_id, confidence DESC
                """).fetchall()
                for entity_id, trait, category in rows:
                    if entity_id in entities:
                        if category == "archetype" and trait not in entities[entity_id].archetypes:
                            entities[entity_id].archetypes.append(trait)
                        elif trait not in entities[entity_id].traits:
                            entities[entity_id].traits.append(trait)
            except sqlite3.OperationalError:
                pass

            # Fallback to basic traits
            try:
                rows = conn.execute(
                    "SELECT entity_id, trait FROM traits"
                ).fetchall()
                for entity_id, trait in rows:
                    if entity_id in entities and trait not in entities[entity_id].traits:
                        entities[entity_id].traits.append(trait)
            except sqlite3.OperationalError:
                pass

        finally:
            conn.close()

        return scenes, entities, scene_entities, entity_themes

    def _draw_scene_spiral(
        self,
        scenes: list[SceneInfo],
        scene_entities: dict[int, set[int]]
    ) -> None:
        """Draw scenes in spiral layout."""
        step = 0.65
        positions: dict[int, tuple[float, float]] = {}

        for index, scene in enumerate(scenes):
            t = index * step
            radius = 32 + (24 * t)
            x = radius * math.cos(t)
            y = radius * math.sin(t)
            positions[scene.id] = (x, y)

            node = SceneNodeEnhanced(scene)
            node.setPos(x, y)
            self._gscene.addItem(node)
            self._scene_nodes[scene.id] = node

        # Draw seams
        for scene in scenes:
            scene_entities.setdefault(scene.id, set())

        for left_scene in scenes:
            left_set = scene_entities.get(left_scene.id, set())
            for right_scene in scenes:
                if right_scene.id <= left_scene.id:
                    continue
                right_set = scene_entities.get(right_scene.id, set())
                overlap = len(left_set & right_set)
                if overlap < 2:
                    continue
                seam = SceneSeamEnhanced(
                    self._scene_nodes[left_scene.id],
                    self._scene_nodes[right_scene.id],
                    overlap
                )
                self._gscene.addItem(seam)

    def _draw_entity_nodes(
        self,
        entities: dict[int, EntityInfo],
        scenes: list[SceneInfo],
        scene_entities: dict[int, set[int]]
    ) -> None:
        """Draw entity nodes near their most frequent scene."""
        # Find primary scene for each entity
        entity_primary_scene: dict[int, int] = {}
        entity_scene_counts: dict[int, dict[int, int]] = {}

        for scene in scenes:
            for entity_id in scene.entities:
                entity_scene_counts.setdefault(entity_id, {})
                entity_scene_counts[entity_id][scene.id] = \
                    entity_scene_counts[entity_id].get(scene.id, 0) + 1

        for entity_id, scene_counts in entity_scene_counts.items():
            if scene_counts:
                primary = max(scene_counts, key=scene_counts.get)
                entity_primary_scene[entity_id] = primary

        # Draw entity nodes
        for entity_id, entity in entities.items():
            primary_scene = entity_primary_scene.get(entity_id)
            if not primary_scene or primary_scene not in self._scene_nodes:
                continue

            scene_node = self._scene_nodes[primary_scene]
            scene_pos = scene_node.pos()

            # Position entity nodes in a cluster around their primary scene
            # Use entity_id to create consistent offsets
            angle = (entity_id * 0.7) % (2 * math.pi)
            offset_radius = 35 + (entity_id % 3) * 10
            x = scene_pos.x() + offset_radius * math.cos(angle)
            y = scene_pos.y() + offset_radius * math.sin(angle)

            node = EntityNode(entity, show_palette=self._show_palettes)
            node.setPos(x, y)
            node.setVisible(False)  # Start hidden
            self._gscene.addItem(node)
            self._entity_nodes[entity_id] = node

    def _draw_theme_connections(
        self,
        entities: dict[int, EntityInfo],
        entity_themes: dict[int, list[tuple[str, int]]]
    ) -> None:
        """Draw thematic connections between entities."""
        # Find entities sharing themes
        theme_to_entities: dict[str, list[int]] = {}
        for entity_id, themes in entity_themes.items():
            for theme_name, intensity in themes:
                if intensity >= 1:
                    theme_to_entities.setdefault(theme_name, []).append(entity_id)

        # Draw edges between entities sharing themes
        drawn_pairs: set[tuple[int, int, str]] = set()

        for theme_name, entity_ids in theme_to_entities.items():
            if len(entity_ids) < 2:
                continue

            for i, eid1 in enumerate(entity_ids):
                for eid2 in entity_ids[i+1:]:
                    pair = (min(eid1, eid2), max(eid1, eid2), theme_name)
                    if pair in drawn_pairs:
                        continue
                    drawn_pairs.add(pair)

                    if eid1 not in self._entity_nodes or eid2 not in self._entity_nodes:
                        continue

                    # Calculate intensity as average
                    int1 = next((i for t, i in entity_themes.get(eid1, []) if t == theme_name), 3)
                    int2 = next((i for t, i in entity_themes.get(eid2, []) if t == theme_name), 3)
                    avg_intensity = (int1 + int2) // 2

                    edge = ThemeEdge(
                        self._entity_nodes[eid1],
                        self._entity_nodes[eid2],
                        theme_name,
                        avg_intensity
                    )
                    edge.setVisible(False)  # Start hidden
                    self._gscene.addItem(edge)
                    self._theme_edges.append(edge)

    def show_entity_details(self, entity: EntityInfo) -> None:
        """Show the entity detail panel."""
        self._detail_panel.show_entity(entity)

    def resizeEvent(self, event) -> None:
        """Reposition overlay panels on resize."""
        super().resizeEvent(event)
        self._layer_panel.move(10, 10)
        self._legend_panel.move(10, 56)
        # Position detail panel on right side
        self._detail_panel.move(
            self.width() - self._detail_panel.width() - 10,
            10
        )

    def wheelEvent(self, event) -> None:
        zoom = 1.15 if event.angleDelta().y() > 0 else 0.87
        self.scale(zoom, zoom)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and not self.itemAt(
            event.position().toPoint()
        ):
            self._panning = True
            self._pan_start = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._panning:
            delta = event.position() - self._pan_start
            self._pan_start = event.position()
            self.translate(delta.x(), delta.y())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if self._panning and event.button() == Qt.MouseButton.LeftButton:
            self._panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            event.accept()
            return
        super().mouseReleaseEvent(event)
