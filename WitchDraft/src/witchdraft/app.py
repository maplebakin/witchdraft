from __future__ import annotations

import importlib.util
import json
import logging
import math
import re
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from pathlib import Path

from witchdraft.design_space_bridge import (
    CharacterProfile,
    load_character_profile,
    request_design_space_palette,
)
from witchdraft.constellation_enhanced import EnhancedConstellationView
from witchdraft.db.methodology_db import MethodologyDB, local_date_string, local_now, local_timestamp
from witchdraft.db.schema import ensure_default_chapter as ensure_default_chapter_schema, ensure_vault_schema
from witchdraft.editor.annotation_manager import AnnotationManager
from witchdraft.core.io_utils import (
    parse_frontmatter,
)
from witchdraft.core.scene_utils import split_scenes
from witchdraft.services.export_service import ExportService
from witchdraft.services.nlp_service import NLPService, run_spacy_scan as run_basic_spacy_scan
from witchdraft.services.project_service import ProjectService, project_meta_path

from PyQt6.QtCore import (
    QEasingCurve,
    QEvent,
    QMimeData,
    QPoint,
    QPointF,
    QPropertyAnimation,
    QTimer,
    Qt,
    pyqtSignal,
)
from PyQt6.QtGui import (
    QAction,
    QActionGroup,
    QColor,
    QDrag,
    QFont,
    QPainter,
    QPainterPath,
    QPen,
    QShortcut,
    QTextBlockFormat,
    QTextCharFormat,
    QTextCursor,
)
from PyQt6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QDockWidget,
    QFrame,
    QFileDialog,
    QFormLayout,
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsOpacityEffect,
    QGraphicsPathItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
    QHeaderView,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QMenu,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)
from PyQt6.QtGui import QKeySequence


# =============================================================================
# DARK ACADEMIA COLOR PALETTE — WitchDraft UI Polish
# Deep backgrounds, warm ambers and golds, aged paper tones
# =============================================================================
# Backgrounds
BG_DEEP = "#1a1714"       # Main window background, title bar
BG_PANEL = "#211e1a"      # Sidebar and panel backgrounds
BG_SURFACE = "#f5f0e8"    # Hearth writing surface (aged paper)
BG_CARD = "#2a2520"       # Card/item backgrounds within panels
BG_CARD_HOVER = "#332e28" # Card hover state

# Borders and dividers
BORDER_SOFT = "#3d3730"   # Subtle panel borders and dividers

# Accents
ACCENT_GOLD = "#c9a84c"       # Primary accent — buttons, highlights, active states
ACCENT_GOLD_DIM = "#8a6f30"   # Secondary gold — dimmed accents, icons
ACCENT_GREEN = "#6b8f71"      # Secondary accent — completion states, Exhale progress

# Text colors (dark surfaces)
TEXT_PRIMARY = "#e8e0d0"      # Primary text on dark surfaces
TEXT_SECONDARY = "#9a8f7e"    # Secondary/muted text on dark surfaces
TEXT_FAINT = "#5a5248"        # Very muted text, placeholders, timestamps

# Text colors (hearth surface)
TEXT_HEARTH = "#2b2318"       # Writing text on paper surface

# Cursor and selection
CURSOR_COLOR = "#c9a84c"      # Hearth cursor (matches ACCENT_GOLD)
SELECTION_BG = "#3d3020"      # Text selection background in Hearth

# Scrollbar
SCROLLBAR = "#3d3730"         # Scrollbar track
SCROLLBAR_HANDLE = "#5a5248"  # Scrollbar handle

# Legacy color aliases for backward compatibility during transition
APP_BG = BG_DEEP
TEXT_COLOR = TEXT_PRIMARY
TITLE_BG = BG_DEEP
STATUS_BG = BG_DEEP
ACCENT = ACCENT_GOLD
ACCENT_HOVER = ACCENT_GOLD_DIM
ECHO_BG = BG_CARD
ECHO_BORDER = BORDER_SOFT
ECHO_TEXT = TEXT_PRIMARY
BORDER_COLOR = BORDER_SOFT
BORDER_RADIUS = "8px"
BORDER_RADIUS_SM = "6px"

SCAN_INTERVAL_SECONDS = 300
PROJECTS_ROOT = Path.home() / "WitchDraftProjects"
PROJECT_META = "project.json"
CHAPTERS_DIRNAME = "chapters"
TYPEWRITER_COLUMN_MAX_WIDTH = 700

# =============================================================================
# GLOBAL QSS STYLESHEET — Dark Academia theme
# Apply this on QApplication before any windows open
# =============================================================================
GLOBAL_STYLESHEET = """
QWidget {
    background-color: %(BG_DEEP)s;
    color: %(TEXT_PRIMARY)s;
    font-family: "Georgia", "Palatino Linotype", serif;
    font-size: 13px;
    border: none;
    outline: none;
}

QMainWindow {
    background-color: %(BG_DEEP)s;
}

QScrollBar:vertical {
    background: %(BG_DEEP)s;
    width: 6px;
    border: none;
}

QScrollBar::handle:vertical {
    background: %(SCROLLBAR_HANDLE)s;
    border-radius: 3px;
    min-height: 20px;
}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar:horizontal {
    background: %(BG_DEEP)s;
    height: 6px;
    border: none;
}

QScrollBar::handle:horizontal {
    background: %(SCROLLBAR_HANDLE)s;
    border-radius: 3px;
}

QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal {
    width: 0px;
}

QToolTip {
    background-color: %(BG_CARD)s;
    color: %(TEXT_PRIMARY)s;
    border: 1px solid %(BORDER_SOFT)s;
    border-radius: 4px;
    padding: 4px 8px;
    font-size: 12px;
}
""" % {
    "BG_DEEP": BG_DEEP,
    "TEXT_PRIMARY": TEXT_PRIMARY,
    "SCROLLBAR_HANDLE": SCROLLBAR_HANDLE,
    "BG_CARD": BG_CARD,
    "BORDER_SOFT": BORDER_SOFT,
}

LINE_HEIGHT_PERCENT = {
    "normal": 120,
    "relaxed": 150,
    "spacious": 180,
}
EDITOR_FONT_FAMILIES = [
    "Cormorant Garamond",
    "Georgia",
    "Courier New",
    "Fira Code",
]
DEFAULT_EDITOR_SETTINGS = {
    "font_family": "Cormorant Garamond",
    "font_size": 15,
    "line_height": "relaxed",
    "typewriter_scroll": False,
}
DEFAULT_DAILY_GOAL = 500
NOTE_HIGHLIGHT = QColor(250, 238, 154, 140)
NOTE_HIGHLIGHT_ACTIVE = QColor(246, 214, 110, 175)

# Enhanced Shadow Bible: extracts themes, emotions, color hints
# Set to False for faster basic scanning (entities + adjacent adjectives only)
ENHANCED_SHADOW_BIBLE = True

# Enhanced Constellation View: shows character palettes, themes, connections
# Set to False for the basic scene-only spiral view
ENHANCED_CONSTELLATION = True

LOGGER = logging.getLogger(__name__)
_PROJECT_SERVICE = ProjectService(DEFAULT_EDITOR_SETTINGS, DEFAULT_DAILY_GOAL)
_EXPORT_SERVICE = ExportService()
_NLP_SERVICE = NLPService(enhanced=ENHANCED_SHADOW_BIBLE)


def _init_vault(conn: sqlite3.Connection) -> None:
    ensure_vault_schema(conn)


def _split_scenes(text: str) -> list[tuple[str, str]]:
    return split_scenes(text)


def _project_meta_path(root: Path) -> Path:
    return project_meta_path(root)


def _slugify(name: str) -> str:
    return _PROJECT_SERVICE.slugify_name(name)


def _move_to_compost(path: Path, root: Path) -> Path | None:
    return _PROJECT_SERVICE.move_to_compost(path, root)


def _friendly_title(stem: str) -> str:
    return _PROJECT_SERVICE.friendly_title(stem)


def _parse_frontmatter(lines: list[str]) -> dict[str, object]:
    return _PROJECT_SERVICE.parse_frontmatter(lines)


def _upsert_frontmatter_fields(path: Path, updates: dict[str, object]) -> None:
    ProjectService.upsert_frontmatter_fields(path, updates)


def _created_from_mtime(path: Path) -> str:
    return _PROJECT_SERVICE.created_from_mtime(path)


def _iter_entry_paths(chapters_dir: Path) -> list[Path]:
    return _PROJECT_SERVICE.iter_entry_paths(chapters_dir)


def _parse_created(value: str | None) -> datetime:
    return _PROJECT_SERVICE.parse_created(value)


def _parse_sequence(value: object | None) -> int | None:
    return _PROJECT_SERVICE.parse_sequence(value)


def _build_index_entries(chapters_dir: Path, root: Path) -> list[dict[str, object]]:
    return _PROJECT_SERVICE.build_index_entries(chapters_dir, root)


def _write_index(entries: list[dict[str, object]], output_path: Path) -> None:
    _PROJECT_SERVICE.write_index(entries, output_path)


def _first_nonempty_line(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip().lstrip("#").strip()
        if stripped:
            return stripped
    return ""


def _unique_path(path: Path) -> Path:
    return _PROJECT_SERVICE.unique_path(path)


def _list_projects(root: Path) -> list[Path]:
    return _PROJECT_SERVICE.list_projects(root)


def _local_now() -> datetime:
    return local_now()


def _local_timestamp() -> str:
    return local_timestamp()


def _local_date_string() -> str:
    return local_date_string()


def _surface_nonblocking_warning(widget: QWidget | None, message: str) -> None:
    if widget is None:
        return
    window = widget.window()
    handler = getattr(window, "_show_nonblocking_warning", None)
    if callable(handler):
        handler(message)


def _load_project_meta(root: Path) -> dict:
    return _PROJECT_SERVICE.load_project_meta(root)


def _normalize_editor_settings(value: object | None) -> dict[str, object]:
    return _PROJECT_SERVICE.normalize_editor_settings(value, LINE_HEIGHT_PERCENT)


def _save_project_meta(
    root: Path,
    name: str,
    *,
    editor_settings: dict[str, object] | None = None,
    daily_goal: int | None = None,
) -> None:
    _PROJECT_SERVICE.save_project_meta(
        root,
        name,
        editor_settings=editor_settings,
        daily_goal=daily_goal,
        line_height_percent=LINE_HEIGHT_PERCENT,
    )


def _ensure_chapters_dir(root: Path) -> Path:
    return _PROJECT_SERVICE.ensure_chapters_dir(root)


def _create_project(root: Path, name: str) -> Path:
    return _PROJECT_SERVICE.create_project(root, name, line_height_percent=LINE_HEIGHT_PERCENT)


def _ensure_default_chapter(conn: sqlite3.Connection, chapters_dir: Path) -> None:
    ensure_default_chapter_schema(conn, chapters_dir)


def run_spacy_scan(text: str, db_path: Path) -> None:
    return run_basic_spacy_scan(text, db_path)


class TitleBar(QFrame):
    def __init__(self, parent: QWidget, on_project, on_map) -> None:
        super().__init__(parent)
        self._drag_pos: QPoint | None = None
        self.setObjectName("title-bar")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(8)

        self.title = QLabel("WitchDraft")
        self.title.setObjectName("title-text")
        layout.addWidget(self.title)

        self.project_label = QLabel("No Project")
        self.project_label.setObjectName("project-label")
        layout.addWidget(self.project_label)

        self.scan_status_label = QLabel("⟳ Scanning...")
        self.scan_status_label.setObjectName("scan-status-label")
        layout.addWidget(self.scan_status_label)

        layout.addStretch(1)

        self.project_button = QPushButton("Project")
        self.project_button.setObjectName("project-button")
        self.project_button.clicked.connect(on_project)
        layout.addWidget(self.project_button)

        self.map_button = QPushButton("Constellation")
        self.map_button.setObjectName("map-button")
        self.map_button.clicked.connect(on_map)
        layout.addWidget(self.map_button)

        self.actions_button = QPushButton("Actions")
        self.actions_button.setObjectName("actions-button")
        layout.addWidget(self.actions_button)

        self.min_button = QPushButton("–")
        self.min_button.setFixedWidth(32)
        self.min_button.clicked.connect(self.window().showMinimized)
        layout.addWidget(self.min_button)

        self.close_button = QPushButton("×")
        self.close_button.setFixedWidth(32)
        self.close_button.clicked.connect(self.window().close)
        layout.addWidget(self.close_button)

    def set_project_name(self, name: str) -> None:
        self.project_label.setText(name or "No Project")

    def set_scan_status(self, status: str) -> None:
        self.scan_status_label.setText(status)

    def scan_status(self) -> str:
        return self.scan_status_label.text()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = (
                event.globalPosition().toPoint()
                - self.window().frameGeometry().topLeft()
            )
            event.accept()

    def mouseMoveEvent(self, event) -> None:
        if self._drag_pos and event.buttons() & Qt.MouseButton.LeftButton:
            self.window().move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event) -> None:
        self._drag_pos = None
        event.accept()


class TypewriterShell(QWidget):
    def __init__(self, editor: QTextEdit) -> None:
        super().__init__()
        self.editor = editor
        self._focus_mode = False
        self.left_margin = QWidget()
        self.left_margin.setObjectName("left-margin")
        self.right_margin = QWidget()
        self.right_margin.setObjectName("right-margin")
        self.right_layout = QVBoxLayout(self.right_margin)
        self.right_layout.setContentsMargins(12, 16, 12, 16)
        self.right_layout.addStretch(1)

        self.echo_label = QLabel("")
        self.echo_label.setObjectName("echo-label")
        self.echo_label.setVisible(False)
        self.echo_label.setWordWrap(True)
        self.right_layout.insertWidget(0, self.echo_label, alignment=Qt.AlignmentFlag.AlignTop)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.left_margin)
        layout.addWidget(self.editor)
        layout.addWidget(self.right_margin)

        self.editor.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self.left_margin.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self.right_margin.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)

        # Apply warm, cozy margin styling with rounded inner edges
        margin_style = f"""
            QWidget#left-margin {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {APP_BG}, stop:0.7 {APP_BG}, stop:1 #FAF9F6);
                border-top-right-radius: 16px;
                border-bottom-right-radius: 16px;
            }}
            QWidget#right-margin {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #FAF9F6, stop:0.3 {APP_BG}, stop:1 {APP_BG});
                border-top-left-radius: 16px;
                border-bottom-left-radius: 16px;
            }}
        """
        self.left_margin.setStyleSheet(margin_style)
        self.right_margin.setStyleSheet(margin_style)

    def set_focus_mode(self, enabled: bool) -> None:
        self._focus_mode = enabled
        self._apply_layout()

    def _apply_layout(self) -> None:
        if self._focus_mode:
            padding = 32
            available = max(320, self.width() - (padding * 2))
            editor_width = min(TYPEWRITER_COLUMN_MAX_WIDTH, available)
            margin = max(padding, (self.width() - editor_width) // 2)
        else:
            margin = max(32, int(self.width() * 0.2))
            editor_width = max(320, self.width() - (margin * 2))

        self.left_margin.setFixedWidth(margin)
        self.right_margin.setFixedWidth(margin)
        self.editor.setFixedWidth(editor_width)

    def resizeEvent(self, event) -> None:
        self._apply_layout()
        super().resizeEvent(event)


class ProjectManagerDialog(QDialog):
    def __init__(self, projects_root: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Projects")
        self.resize(420, 360)
        self._projects_root = projects_root
        self._selected: Path | None = None

        # Dark academia dialog styling
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {BG_PANEL};
                border: 1px solid {BORDER_SOFT};
                border-radius: 10px;
            }}
            QLabel#dialog-title {{
                font-family: "Georgia", serif;
                font-size: 16px;
                color: {TEXT_PRIMARY};
                padding-bottom: 8px;
            }}
            QListWidget {{
                background-color: {BG_CARD};
                border: 1px solid {BORDER_SOFT};
                border-radius: 8px;
                padding: 6px;
                outline: none;
            }}
            QListWidget::item {{
                padding: 12px 14px;
                border-radius: 8px;
                margin: 3px 2px;
                color: {TEXT_PRIMARY};
                font-family: "Georgia", serif;
                font-size: 13px;
            }}
            QListWidget::item:selected {{
                background-color: {SELECTION_BG};
                color: {ACCENT_GOLD};
                border: 1px solid {ACCENT_GOLD_DIM};
            }}
            QListWidget::item:hover {{
                background-color: {BG_CARD_HOVER};
            }}
            QPushButton#primary {{
                background-color: {SELECTION_BG};
                color: {ACCENT_GOLD};
                border: 1px solid {ACCENT_GOLD_DIM};
                border-radius: 6px;
                padding: 8px 18px;
                font-family: "Georgia", serif;
                font-size: 13px;
            }}
            QPushButton#primary:hover {{
                background-color: #4d3e28;
                border-color: {ACCENT_GOLD};
            }}
            QPushButton#secondary {{
                background-color: transparent;
                color: {TEXT_SECONDARY};
                border: 1px solid {BORDER_SOFT};
                border-radius: 6px;
                padding: 8px 18px;
                font-family: "Georgia", serif;
                font-size: 13px;
            }}
            QPushButton#secondary:hover {{
                background-color: {BG_CARD};
                border-color: {SCROLLBAR_HANDLE};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # Title label
        title_label = QLabel("Choose Your Writing Space")
        title_label.setObjectName("dialog-title")
        layout.addWidget(title_label)

        self.list = QListWidget()
        layout.addWidget(self.list)

        button_row = QHBoxLayout()
        button_row.setSpacing(10)
        self.new_button = QPushButton("New Project")
        self.new_button.setObjectName("secondary")
        self.open_button = QPushButton("Open")
        self.open_button.setObjectName("primary")
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setObjectName("secondary")
        button_row.addWidget(self.new_button)
        button_row.addStretch(1)
        button_row.addWidget(self.open_button)
        button_row.addWidget(self.cancel_button)
        layout.addLayout(button_row)

        self.new_button.clicked.connect(self._create_project)
        self.open_button.clicked.connect(self._accept_selection)
        self.cancel_button.clicked.connect(self.reject)
        self.list.itemDoubleClicked.connect(lambda _: self._accept_selection())

        self.refresh()

    def refresh(self) -> None:
        self.list.clear()
        for project_path in _list_projects(self._projects_root):
            meta = _load_project_meta(project_path)
            item = QListWidgetItem(meta.get("name", project_path.name))
            item.setData(Qt.ItemDataRole.UserRole, str(project_path))
            self.list.addItem(item)
        if self.list.count() > 0:
            self.list.setCurrentRow(0)

    def _create_project(self) -> None:
        name, ok = QInputDialog.getText(self, "New Project", "Project name:")
        if not ok or not name.strip():
            return
        project_root = self._projects_root / _slugify(name)
        if project_root.exists():
            QMessageBox.warning(self, "Project Exists", "Project folder already exists.")
            return
        _create_project(project_root, name.strip())
        self.refresh()
        for row in range(self.list.count()):
            item = self.list.item(row)
            if item and item.text() == name.strip():
                self.list.setCurrentRow(row)
                break

    def _accept_selection(self) -> None:
        item = self.list.currentItem()
        if not item:
            return
        self._selected = Path(item.data(Qt.ItemDataRole.UserRole))
        self.accept()

    def selected_project(self) -> Path | None:
        return self._selected


class ChaptersPanel(QWidget):
    def __init__(self, on_select, on_new, on_delete) -> None:
        super().__init__()
        self.setObjectName("chapters-panel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 14, 12, 12)
        layout.setSpacing(10)
        title = QLabel("Chapters")
        title.setObjectName("panel-title")
        layout.addWidget(title)
        self.list = QListWidget()
        layout.addWidget(self.list, stretch=1)
        button_row = QHBoxLayout()
        button_row.setSpacing(8)
        self.new_button = QPushButton("New")
        self.delete_button = QPushButton("Delete")
        button_row.addWidget(self.new_button)
        button_row.addWidget(self.delete_button)
        layout.addLayout(button_row)

        self.list.itemSelectionChanged.connect(on_select)
        self.new_button.clicked.connect(on_new)
        self.delete_button.clicked.connect(on_delete)


class StorylinesPanel(QWidget):
    def __init__(self, on_toggle, on_new) -> None:
        super().__init__()
        self.setObjectName("storylines-panel")
        self._ignore = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 14, 12, 12)
        layout.setSpacing(10)
        title = QLabel("Storylines")
        title.setObjectName("panel-title")
        layout.addWidget(title)
        self.list = QListWidget()
        layout.addWidget(self.list, stretch=1)
        self.new_button = QPushButton("New")
        layout.addWidget(self.new_button)

        self.list.itemChanged.connect(on_toggle)
        self.new_button.clicked.connect(on_new)

    def set_storylines(self, storylines: list[tuple[int, str]], selected_ids: set[int]) -> None:
        self._ignore = True
        self.list.clear()
        for storyline_id, name in storylines:
            item = QListWidgetItem(name)
            item.setData(Qt.ItemDataRole.UserRole, storyline_id)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(
                Qt.CheckState.Checked
                if storyline_id in selected_ids
                else Qt.CheckState.Unchecked
            )
            self.list.addItem(item)
        self._ignore = False

    def is_ignoring(self) -> bool:
        return self._ignore


class NotesPanel(QWidget):
    def __init__(self, on_select, on_edit, on_delete) -> None:
        super().__init__()
        self.setObjectName("notes-panel")
        self._ignore = False
        self._on_select = on_select
        self._on_edit = on_edit
        self._on_delete = on_delete

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 14, 12, 12)
        layout.setSpacing(10)
        title = QLabel("Notes")
        title.setObjectName("panel-title")
        layout.addWidget(title)

        self.list = QListWidget()
        layout.addWidget(self.list, stretch=1)

        actions = QHBoxLayout()
        actions.setSpacing(6)
        self.edit_button = QPushButton("Edit")
        self.delete_button = QPushButton("Delete")
        actions.addWidget(self.edit_button)
        actions.addWidget(self.delete_button)
        layout.addLayout(actions)

        self.list.itemSelectionChanged.connect(self._on_selection_changed)
        self.list.itemDoubleClicked.connect(lambda _item: self._emit_edit())
        self.edit_button.clicked.connect(self._emit_edit)
        self.delete_button.clicked.connect(self._emit_delete)

    def set_notes(self, notes: list[dict[str, object]], selected_note_id: int | None = None) -> None:
        self._ignore = True
        self.list.clear()
        selected_row = -1
        for index, note in enumerate(notes):
            note_id = int(note.get("id", 0))
            detached = bool(note.get("detached", False))
            note_text = " ".join(str(note.get("note_text") or "").split())
            if not note_text:
                note_text = "(empty note)"
            if len(note_text) > 80:
                note_text = note_text[:77] + "..."
            label = f"Detached: {note_text}" if detached else note_text
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, note_id)
            item.setToolTip(str(note.get("note_text") or ""))
            self.list.addItem(item)
            if selected_note_id is not None and note_id == selected_note_id:
                selected_row = index

        if selected_row >= 0:
            self.list.setCurrentRow(selected_row)
        elif self.list.count() > 0:
            self.list.setCurrentRow(0)
        else:
            self.list.clearSelection()
        self._ignore = False
        self._sync_action_state()

    def selected_note_id(self) -> int | None:
        item = self.list.currentItem()
        if item is None:
            return None
        value = item.data(Qt.ItemDataRole.UserRole)
        if value is None:
            return None
        return int(value)

    def _sync_action_state(self) -> None:
        enabled = self.selected_note_id() is not None
        self.edit_button.setEnabled(enabled)
        self.delete_button.setEnabled(enabled)

    def _on_selection_changed(self) -> None:
        self._sync_action_state()
        if self._ignore:
            return
        note_id = self.selected_note_id()
        if note_id is None:
            return
        self._on_select(note_id)

    def _emit_edit(self) -> None:
        note_id = self.selected_note_id()
        if note_id is None:
            return
        self._on_edit(note_id)

    def _emit_delete(self) -> None:
        note_id = self.selected_note_id()
        if note_id is None:
            return
        self._on_delete(note_id)


class StatusBar(QWidget):
    """Custom status bar widget — quiet whisper at bottom of page."""
    
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("status-bar")
        self.setFixedHeight(28)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 4, 16, 4)
        
        self.label = QLabel("")
        self.label.setStyleSheet(f"""
            QLabel {{
                background-color: {BG_DEEP};
                color: {TEXT_FAINT};
                font-family: "Georgia", serif;
                font-size: 11px;
                border: none;
                padding: 0;
            }}
        """)
        layout.addWidget(self.label, stretch=1)
    
    def setText(self, text: str) -> None:
        self.label.setText(text)
    
    def text(self) -> str:
        return self.label.text()


class OutlinerCard(QWidget):
    """A single chapter card for the outliner panel."""
    
    def __init__(
        self,
        chapter_id: int,
        title: str,
        word_count: int,
        storyline_tags: str,
        synopsis: str,
        on_select: callable,
        on_reorder_drop: callable,
        on_synopsis_changed: callable,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._chapter_id = chapter_id
        self._on_select = on_select
        self._on_reorder_drop = on_reorder_drop
        self._on_synopsis_changed = on_synopsis_changed
        self._drag_start_pos: QPoint | None = None
        self.setAcceptDrops(True)
        
        self.setObjectName("outliner-card")
        self.setStyleSheet("""
            QWidget#outliner-card {
                background-color: #2a2520;
                border-radius: 8px;
                padding: 10px;
                margin: 2px 4px;
            }
            QWidget#outliner-card:hover {
                background-color: #332e28;
            }
            QWidget#outliner-card:selected {
                background-color: #3d3020;
                border: 1px solid #8a6f30;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)
        
        # Top row: title and word count badge
        top_layout = QHBoxLayout()
        top_layout.setSpacing(8)
        
        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("""
            QLabel {
                font-family: "Georgia", serif;
                font-size: 13px;
                color: #e8e0d0;
                font-weight: normal;
            }
        """)
        top_layout.addWidget(self.title_label, stretch=1)
        
        self.word_badge = QLabel(f"{word_count:,} words")
        self.word_badge.setStyleSheet("""
            QLabel {
                background-color: #2a2520;
                color: #5a5248;
                font-family: "Georgia", serif;
                font-size: 10px;
                border-radius: 4px;
                padding: 2px 6px;
            }
        """)
        top_layout.addWidget(self.word_badge)
        
        layout.addLayout(top_layout)
        
        # Storyline tags
        if storyline_tags:
            self.storyline_label = QLabel(storyline_tags)
            self.storyline_label.setStyleSheet("""
                QLabel {
                    font-family: "Georgia", serif;
                    font-size: 11px;
                    color: #9a8f7e;
                }
            """)
            self.storyline_label.setWordWrap(True)
            layout.addWidget(self.storyline_label)
        
        # Synopsis text edit
        self.synopsis_edit = QTextEdit()
        self.synopsis_edit.setPlaceholderText("Synopsis...")
        self.synopsis_edit.setText(synopsis)
        self.synopsis_edit.setMaximumHeight(60)
        self.synopsis_edit.setStyleSheet("""
            QTextEdit {
                background-color: #211e1a;
                color: #c8bfaf;
                font-family: "Georgia", serif;
                font-size: 12px;
                border: none;
                border-radius: 6px;
                padding: 6px 8px;
            }
            QTextEdit:focus {
                border: 1px solid #3d3730;
            }
        """)
        self.synopsis_edit.textChanged.connect(self._on_synopsis_text_changed)
        layout.addWidget(self.synopsis_edit)
    
    def chapter_id(self) -> int:
        return self._chapter_id
    
    def set_selected(self, selected: bool) -> None:
        if selected:
            self.setStyleSheet("""
                QWidget#outliner-card {
                    background-color: #3d3020;
                    border: 1px solid #8a6f30;
                    border-radius: 8px;
                    padding: 10px;
                    margin: 2px 4px;
                }
            """)
        else:
            self.setStyleSheet("""
                QWidget#outliner-card {
                    background-color: #2a2520;
                    border-radius: 8px;
                    padding: 10px;
                    margin: 2px 4px;
                }
                QWidget#outliner-card:hover {
                    background-color: #332e28;
                }
            """)
    
    def _on_synopsis_text_changed(self) -> None:
        if self._on_synopsis_changed:
            self._on_synopsis_changed(self._chapter_id, self.synopsis_edit.toPlainText())

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_pos = event.position().toPoint()
            if self._on_select:
                self._on_select(self._chapter_id)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if not (event.buttons() & Qt.MouseButton.LeftButton):
            super().mouseMoveEvent(event)
            return
        if self._drag_start_pos is None:
            super().mouseMoveEvent(event)
            return
        if (event.position().toPoint() - self._drag_start_pos).manhattanLength() < 8:
            super().mouseMoveEvent(event)
            return
        child = self.childAt(event.position().toPoint())
        if child is not None and (
            child is self.synopsis_edit
            or child is self.synopsis_edit.viewport()
            or self.synopsis_edit.isAncestorOf(child)
        ):
            super().mouseMoveEvent(event)
            return

        drag = QDrag(self)
        mime_data = QMimeData()
        mime_data.setData(
            "application/x-witchdraft-outliner-card",
            str(self._chapter_id).encode("utf-8"),
        )
        drag.setMimeData(mime_data)
        drag.exec(Qt.DropAction.MoveAction)
        self._drag_start_pos = None
        super().mouseMoveEvent(event)

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasFormat("application/x-witchdraft-outliner-card"):
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:
        if event.mimeData().hasFormat("application/x-witchdraft-outliner-card"):
            event.acceptProposedAction()
            return
        super().dragMoveEvent(event)

    def dropEvent(self, event) -> None:
        data = event.mimeData().data("application/x-witchdraft-outliner-card")
        try:
            dragged_id = int(bytes(data).decode("utf-8"))
        except (TypeError, ValueError):
            event.ignore()
            return
        after = event.position().y() >= (self.height() / 2)
        if self._on_reorder_drop:
            self._on_reorder_drop(dragged_id, self._chapter_id, after)
        event.acceptProposedAction()


class OutlinerPanel(QWidget):
    def __init__(
        self,
        on_select_chapter,
        on_add_chapter,
        on_delete_chapter,
        on_reorder,
        on_update_synopsis,
    ) -> None:
        super().__init__()
        self.setObjectName("outliner-panel")
        self._ignore = False
        self._on_select_chapter = on_select_chapter
        self._on_add_chapter = on_add_chapter
        self._on_delete_chapter = on_delete_chapter
        self._on_reorder = on_reorder
        self._on_update_synopsis = on_update_synopsis
        self._cards: list[OutlinerCard] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 12, 10, 10)
        layout.setSpacing(8)

        title = QLabel("Outliner")
        title.setObjectName("panel-title")
        layout.addWidget(title)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(6)
        self.add_button = QPushButton("Add")
        self.delete_button = QPushButton("Delete")
        toolbar.addWidget(self.add_button)
        toolbar.addWidget(self.delete_button)
        toolbar.addStretch(1)
        layout.addLayout(toolbar)

        # Scrollable card container
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: transparent;
                border: none;
            }
        """)
        
        self.cards_container = QWidget()
        self.cards_layout = QVBoxLayout(self.cards_container)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setSpacing(4)
        self.cards_layout.addStretch(1)
        
        self.scroll_area.setWidget(self.cards_container)
        layout.addWidget(self.scroll_area, stretch=1)

        self.add_button.clicked.connect(self._on_add_chapter)
        self.delete_button.clicked.connect(self._on_delete_chapter)

    def set_outline(self, chapters: list[dict[str, object]]) -> None:
        self._ignore = True
        
        # Clear existing cards
        while self.cards_layout.count() > 1:  # Keep the stretch
            item = self.cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._cards = []

        for chapter in chapters:
            chapter_id = int(chapter["chapter_id"])
            title = str(chapter.get("title") or "")
            words = int(chapter.get("word_count") or 0)
            storyline_tags = ", ".join(chapter.get("storyline_tags") or [])
            synopsis = str(chapter.get("synopsis") or "")

            card = OutlinerCard(
                chapter_id=chapter_id,
                title=title,
                word_count=words,
                storyline_tags=storyline_tags,
                synopsis=synopsis,
                on_select=self._handle_card_selected,
                on_reorder_drop=self._handle_card_drop,
                on_synopsis_changed=self._on_update_synopsis,
            )
            self._cards.append(card)
            self.cards_layout.insertWidget(len(self._cards) - 1, card)

        self._ignore = False

    def select_chapter(self, chapter_id: int | None) -> None:
        if chapter_id is None:
            return
        self._ignore = True
        for card in self._cards:
            card.set_selected(card.chapter_id() == chapter_id)
        self._ignore = False

    def _handle_card_selected(self, chapter_id: int) -> None:
        if self._ignore:
            return
        self.select_chapter(chapter_id)
        if self._on_select_chapter:
            self._on_select_chapter(chapter_id)

    def _handle_card_drop(self, dragged_id: int, target_id: int, after: bool) -> None:
        if dragged_id == target_id:
            return
        ordered_ids = [card.chapter_id() for card in self._cards]
        if dragged_id not in ordered_ids or target_id not in ordered_ids:
            return

        ordered_ids.remove(dragged_id)
        target_index = ordered_ids.index(target_id)
        if after:
            target_index += 1
        ordered_ids.insert(target_index, dragged_id)
        if self._on_reorder:
            self._on_reorder(ordered_ids)


class LibraryDialog(QDialog):
    def __init__(self, entries: list[dict[str, object]], on_open, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Library")
        self.resize(900, 540)
        self._entries = entries
        self._on_open = on_open

        # Dark academia library dialog styling
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {BG_PANEL};
                border: 1px solid {BORDER_SOFT};
                border-radius: 10px;
            }}
            QLabel#dialog-title {{
                font-family: "Georgia", serif;
                font-size: 18px;
                color: {TEXT_PRIMARY};
                padding-bottom: 8px;
            }}
            QLabel {{
                color: {TEXT_SECONDARY};
                font-family: "Georgia", serif;
            }}
            QLineEdit {{
                background-color: {BG_CARD};
                border: 1px solid {BORDER_SOFT};
                border-radius: 6px;
                padding: 8px 12px;
                color: {TEXT_PRIMARY};
                font-family: "Georgia", serif;
                font-size: 13px;
            }}
            QLineEdit:focus {{
                border-color: {ACCENT_GOLD_DIM};
            }}
            QTableWidget {{
                background-color: {BG_CARD};
                border: 1px solid {BORDER_SOFT};
                border-radius: 8px;
                gridline-color: {BORDER_SOFT};
                outline: none;
            }}
            QTableWidget::item {{
                padding: 8px;
                border-bottom: 1px solid {BORDER_SOFT};
                color: {TEXT_PRIMARY};
                font-family: "Georgia", serif;
                font-size: 13px;
            }}
            QTableWidget::item:selected {{
                background-color: {SELECTION_BG};
                color: {ACCENT_GOLD};
            }}
            QHeaderView::section {{
                background-color: {BG_CARD_HOVER};
                border: none;
                border-bottom: 1px solid {BORDER_SOFT};
                border-right: 1px solid {BORDER_SOFT};
                padding: 10px 8px;
                font-family: "Georgia", serif;
                font-size: 12px;
                font-weight: normal;
                letter-spacing: 0.1em;
                color: {TEXT_SECONDARY};
            }}
            QPushButton#primary {{
                background-color: {SELECTION_BG};
                color: {ACCENT_GOLD};
                border: 1px solid {ACCENT_GOLD_DIM};
                border-radius: 6px;
                padding: 8px 18px;
                font-family: "Georgia", serif;
                font-size: 13px;
            }}
            QPushButton#primary:hover {{
                background-color: #4d3e28;
                border-color: {ACCENT_GOLD};
            }}
            QPushButton#secondary {{
                background-color: transparent;
                color: {TEXT_SECONDARY};
                border: 1px solid {BORDER_SOFT};
                border-radius: 6px;
                padding: 8px 18px;
                font-family: "Georgia", serif;
                font-size: 13px;
            }}
            QPushButton#secondary:hover {{
                background-color: {BG_CARD};
                border-color: {SCROLLBAR_HANDLE};
            }}
            QScrollBar:vertical {{
                background-color: {BG_DEEP};
                width: 6px;
                border: none;
            }}
            QScrollBar::handle:vertical {{
                background-color: {SCROLLBAR_HANDLE};
                border-radius: 3px;
                min-height: 20px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Title
        title_label = QLabel("Your Writing Library")
        title_label.setObjectName("dialog-title")
        layout.addWidget(title_label)

        filters = QFormLayout()
        filters.setSpacing(10)
        filters.setContentsMargins(0, 0, 0, 8)
        self._book_filter = QLineEdit()
        self._book_filter.setPlaceholderText("Filter by book...")
        self._mood_filter = QLineEdit()
        self._mood_filter.setPlaceholderText("Filter by mood...")
        self._theme_filter = QLineEdit()
        self._theme_filter.setPlaceholderText("Filter by theme...")
        self._archetype_filter = QLineEdit()
        self._archetype_filter.setPlaceholderText("Filter by archetype...")
        filters.addRow("Book", self._book_filter)
        filters.addRow("Mood", self._mood_filter)
        filters.addRow("Theme", self._theme_filter)
        filters.addRow("Archetype", self._archetype_filter)
        layout.addLayout(filters)

        self._table = QTableWidget(0, 7)
        self._table.setHorizontalHeaderLabels(
            ["Title", "Mood", "Archetype", "Theme", "Book", "Sequence", "Path"]
        )
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.setShowGrid(False)
        self._table.setAlternatingRowColors(True)
        self._table.doubleClicked.connect(self._open_selected)
        layout.addWidget(self._table, stretch=1)

        button_row = QHBoxLayout()
        button_row.setSpacing(10)
        button_row.addStretch(1)
        self._open_button = QPushButton("Open Chapter")
        self._open_button.setObjectName("primary")
        self._open_button.clicked.connect(self._open_selected)
        close_button = QPushButton("Close")
        close_button.setObjectName("secondary")
        close_button.clicked.connect(self.accept)
        button_row.addWidget(self._open_button)
        button_row.addWidget(close_button)
        layout.addLayout(button_row)

        for field in (
            self._book_filter,
            self._mood_filter,
            self._theme_filter,
            self._archetype_filter,
        ):
            field.textChanged.connect(self._apply_filters)

        self._apply_filters()

    def _apply_filters(self) -> None:
        book = self._book_filter.text().strip().casefold()
        mood = self._mood_filter.text().strip().casefold()
        theme = self._theme_filter.text().strip().casefold()
        archetype = self._archetype_filter.text().strip().casefold()

        def matches(entry: dict[str, object]) -> bool:
            if book and str(entry.get("book") or "").casefold() != book:
                return False
            if mood and str(entry.get("mood") or "").casefold() != mood:
                return False
            if theme and str(entry.get("theme") or "").casefold() != theme:
                return False
            if archetype and str(entry.get("archetype") or "").casefold() != archetype:
                return False
            return True

        filtered = [entry for entry in self._entries if matches(entry)]
        self._render_table(filtered)

    def _render_table(self, entries: list[dict[str, object]]) -> None:
        self._table.setRowCount(len(entries))
        for row_index, entry in enumerate(entries):
            title_item = QTableWidgetItem(str(entry.get("title") or ""))
            path_value = str(entry.get("path") or "")
            title_item.setData(Qt.ItemDataRole.UserRole, path_value)
            self._table.setItem(row_index, 0, title_item)
            self._table.setItem(row_index, 1, QTableWidgetItem(str(entry.get("mood") or "")))
            self._table.setItem(
                row_index, 2, QTableWidgetItem(str(entry.get("archetype") or ""))
            )
            self._table.setItem(row_index, 3, QTableWidgetItem(str(entry.get("theme") or "")))
            self._table.setItem(row_index, 4, QTableWidgetItem(str(entry.get("book") or "")))
            seq = entry.get("sequence")
            self._table.setItem(row_index, 5, QTableWidgetItem("" if seq is None else str(seq)))
            self._table.setItem(row_index, 6, QTableWidgetItem(path_value))

    def _open_selected(self) -> None:
        selected = self._table.selectedItems()
        if not selected:
            return
        path_value = selected[0].data(Qt.ItemDataRole.UserRole)
        if not path_value:
            return
        self._on_open(Path(str(path_value)))


class ExhaleDialog(QDialog):
    """Dialog for setting the Exhale session word count target."""

    def __init__(
        self,
        parent: QWidget | None = None,
        default_value: int = 500,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Set Exhale")
        self.setModal(True)
        self.setFixedSize(320, 180)

        # Dark academia dialog styling
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {BG_PANEL};
                border: 1px solid {BORDER_SOFT};
                border-radius: 10px;
            }}
            QLabel#title-label {{
                font-family: "Georgia", serif;
                font-size: 13px;
                color: {TEXT_SECONDARY};
                padding: 8px;
            }}
            QLineEdit#target-input {{
                font-family: "Georgia", serif;
                font-size: 24px;
                font-weight: normal;
                background-color: {BG_CARD};
                border: 1px solid {BORDER_SOFT};
                border-radius: 6px;
                padding: 12px;
                color: {TEXT_PRIMARY};
                selection-background-color: {SELECTION_BG};
            }}
            QLineEdit#target-input:focus {{
                border-color: {ACCENT_GOLD_DIM};
            }}
            QPushButton#confirm {{
                background-color: {SELECTION_BG};
                color: {ACCENT_GOLD};
                border: 1px solid {ACCENT_GOLD_DIM};
                border-radius: 6px;
                padding: 6px 18px;
                font-family: "Georgia", serif;
                font-size: 13px;
            }}
            QPushButton#confirm:hover {{
                background-color: #4d3e28;
                border-color: {ACCENT_GOLD};
            }}
            QPushButton#cancel {{
                background-color: transparent;
                color: {TEXT_SECONDARY};
                border: 1px solid {BORDER_SOFT};
                border-radius: 6px;
                padding: 6px 18px;
                font-family: "Georgia", serif;
                font-size: 13px;
            }}
            QPushButton#cancel:hover {{
                background-color: {BG_CARD};
                border-color: {SCROLLBAR_HANDLE};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # Title label
        title_label = QLabel("Words to exhale this session:")
        title_label.setObjectName("title-label")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

        # Numeric input field
        self.target_input = QLineEdit()
        self.target_input.setObjectName("target-input")
        self.target_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.target_input.setInputMethodHints(
            Qt.InputMethodHint.ImhDigitsOnly | Qt.InputMethodHint.ImhPreferNumbers
        )
        self.target_input.setText(str(default_value))
        self.target_input.selectAll()
        layout.addWidget(self.target_input)

        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        # Style the buttons
        for btn in button_box.buttons():
            if btn.role() == QDialogButtonBox.ButtonRole.AcceptRole:
                btn.setObjectName("confirm")
                btn.setText("Set Exhale")
            else:
                btn.setObjectName("cancel")
        layout.addWidget(button_box)

    def get_target(self) -> int | None:
        """Return the target word count, or None if invalid."""
        try:
            value = int(self.target_input.text().strip())
            if value <= 0:
                return None
            return value
        except ValueError:
            return None


class SparkItemWidget(QWidget):
    """A single spark item with checkbox and text field."""

    def __init__(
        self,
        position: int,
        text: str = "",
        completed: bool = False,
        on_toggle: callable = None,
        on_text_changed: callable = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._position = position
        self._on_toggle = on_toggle
        self._on_text_changed = on_text_changed
        self._completed = completed

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(8)

        # Completion checkbox with custom styling
        self.checkbox = QPushButton()
        self.checkbox.setCheckable(True)
        self.checkbox.setChecked(completed)
        self.checkbox.setFixedSize(20, 20)
        self.checkbox.clicked.connect(self._on_checkbox_clicked)
        self._update_checkbox_style()
        layout.addWidget(self.checkbox)

        # Text field
        self.text_field = QLineEdit()
        self.text_field.setText(text)
        self.text_field.setPlaceholderText(f"Spark {position}")
        self.text_field.textChanged.connect(self._on_text_field_changed)
        self.text_field.setStyleSheet(f"""
            QLineEdit {{
                background-color: {BG_CARD};
                color: {TEXT_PRIMARY};
                border: 1px solid {BORDER_SOFT};
                border-radius: 6px;
                padding: 6px 10px;
                font-family: "Georgia", serif;
                font-size: 13px;
            }}
            QLineEdit:focus {{
                border-color: {ACCENT_GOLD_DIM};
            }}
            QLineEdit:disabled {{
                background-color: {BG_PANEL};
                color: {TEXT_FAINT};
            }}
        """)
        layout.addWidget(self.text_field)

    def _update_checkbox_style(self) -> None:
        """Update checkbox appearance based on completion state."""
        if self._completed:
            self.checkbox.setStyleSheet(f"""
                QPushButton {{
                    background-color: {ACCENT_GOLD};
                    border: 2px solid {ACCENT_GOLD};
                    border-radius: 10px;
                }}
                QPushButton:hover {{
                    background-color: {ACCENT_GOLD_DIM};
                }}
            """)
            self.text_field.setStyleSheet(f"""
                QLineEdit {{
                    background-color: {BG_PANEL};
                    border: 1px solid {BORDER_SOFT};
                    border-radius: 6px;
                    padding: 6px 10px;
                    color: {TEXT_FAINT};
                    font-family: "Georgia", serif;
                    font-size: 13px;
                }}
            """)
            self.text_field.setEnabled(False)
        else:
            self.checkbox.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;
                    border: 2px solid {TEXT_FAINT};
                    border-radius: 10px;
                }}
                QPushButton:hover {{
                    border-color: {ACCENT_GOLD};
                    background-color: rgba(201, 168, 76, 0.1);
                }}
            """)
            self.text_field.setEnabled(True)

    def _on_checkbox_clicked(self) -> None:
        self._completed = self.checkbox.isChecked()
        self._update_checkbox_style()
        if self._on_toggle:
            self._on_toggle(self._position, self._completed)

    def _on_text_field_changed(self, text: str) -> None:
        if self._on_text_changed:
            self._on_text_changed(self._position, text)

    def get_text(self) -> str:
        return self.text_field.text().strip()

    def is_completed(self) -> bool:
        return self._completed

    def set_completed(self, completed: bool, animate: bool = False) -> None:
        if self._completed == completed:
            return
        self._completed = completed
        self.checkbox.setChecked(completed)
        self._update_checkbox_style()


class SparksPanel(QWidget):
    """Dockable panel for daily Sparks intentions."""

    def __init__(
        self,
        methodology_db: MethodologyDB,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._methodology_db = methodology_db
        self._spark_items: list[SparkItemWidget] = []
        self._active_date = _local_date_string()

        self.setObjectName("sparks-panel")
        self.setStyleSheet(f"""
            QWidget#sparks-panel {{
                background-color: {BG_PANEL};
                border-right: 1px solid {BORDER_SOFT};
            }}
            QLabel#sparks-title {{
                font-family: "Georgia", serif;
                font-size: 10px;
                letter-spacing: 0.15em;
                text-transform: uppercase;
                color: {TEXT_FAINT};
                padding: 12px 12px 6px 12px;
            }}
            QLabel#progress-label {{
                font-family: "Georgia", serif;
                font-size: 11px;
                color: {TEXT_FAINT};
                padding: 8px 12px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Title
        title_label = QLabel("Sparks")
        title_label.setObjectName("sparks-title")
        layout.addWidget(title_label)

        # Spark items container
        self.spark_container = QWidget()
        self.spark_layout = QVBoxLayout(self.spark_container)
        self.spark_layout.setContentsMargins(8, 8, 8, 8)
        self.spark_layout.setSpacing(6)
        layout.addWidget(self.spark_container)

        # Progress label
        self.progress_label = QLabel("0 / 5 sparked")
        self.progress_label.setObjectName("progress-label")
        self.progress_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self.progress_label)

        self._date_timer = QTimer(self)
        self._date_timer.timeout.connect(self._refresh_for_day_rollover)
        self._date_timer.start(60_000)

        self._load_sparks()

    def refresh_sparks(self) -> None:
        self._refresh_for_day_rollover(force=True)

    def _current_date(self) -> str:
        return _local_date_string()

    def _refresh_for_day_rollover(self, force: bool = False) -> None:
        current_date = self._current_date()
        if force or current_date != self._active_date:
            self._active_date = current_date
            self._load_sparks()

    def _normalize_sparks(self, conn: sqlite3.Connection) -> None:
        self._methodology_db.normalize_sparks(conn, self._active_date)

    def _append_empty_spark(self) -> None:
        next_position = len(self._spark_items) + 1
        if next_position > 5:
            return
        spark_item = SparkItemWidget(
            position=next_position,
            text="",
            completed=False,
            on_toggle=self._on_spark_toggled,
            on_text_changed=self._on_spark_text_changed,
            parent=self,
        )
        self._spark_items.append(spark_item)
        self.spark_layout.insertWidget(self.spark_layout.count() - 1, spark_item)

    def _load_sparks(self) -> None:
        """Load today's sparks from the database."""
        self._active_date = self._current_date()
        # Clear existing items
        while self.spark_layout.count():
            item = self.spark_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self._spark_items = []

        # Load from DB
        sparks_data = self._get_todays_sparks()
        sparks_by_position = {
            position: (text, completed)
            for position, text, completed in sparks_data
            if str(text or "").strip()
        }
        filled_count = len(sparks_by_position)
        visible_count = min(5, filled_count + 1 if filled_count < 5 else 5)

        for position in range(1, visible_count + 1):
            spark_text, completed = sparks_by_position.get(position, ("", False))

            spark_item = SparkItemWidget(
                position=position,
                text=spark_text,
                completed=completed,
                on_toggle=self._on_spark_toggled,
                on_text_changed=self._on_spark_text_changed,
                parent=self,
            )
            self._spark_items.append(spark_item)
            self.spark_layout.addWidget(spark_item)

        # Add stretch to push items to top
        self.spark_layout.addStretch(1)

        self._update_progress()

    def _get_todays_sparks(self) -> list[tuple[int, str, int]]:
        """Get today's sparks from the database.
        Returns list of (position, text, completed) tuples.
        """
        self._active_date = self._current_date()
        return self._methodology_db.get_todays_sparks()

    def _save_spark(self, position: int, text: str, completed: bool) -> None:
        """Save a spark to the database."""
        self._active_date = self._current_date()
        self._methodology_db.save_spark(position, text, completed)

    def _on_spark_toggled(self, position: int, completed: bool) -> None:
        """Handle spark completion toggle."""
        spark_item = self._spark_items[position - 1]
        text = spark_item.get_text()
        self._save_spark(position, text, completed)
        self._load_sparks()
        self._update_progress()

    def _on_spark_text_changed(self, position: int, text: str) -> None:
        """Handle spark text change."""
        spark_item = self._spark_items[position - 1]
        completed = spark_item.is_completed()
        self._save_spark(position, text, completed)
        if text.strip():
            if (
                position == len(self._spark_items)
                and len(self._spark_items) < 5
            ):
                self._append_empty_spark()
        else:
            self._load_sparks()

    def _update_progress(self) -> None:
        """Update the progress indicator."""
        completed_count = sum(
            1 for item in self._spark_items if item.is_completed() and item.get_text()
        )
        self.progress_label.setText(f"{completed_count} / 5 sparked")


class CompanionCaptureBar(QWidget):
    """Slim single-line capture bar overlay for Companion Doc notes."""

    def __init__(
        self,
        parent: QWidget,
        on_save: callable,
        on_dismiss: callable,
    ) -> None:
        super().__init__(parent)
        self._on_save = on_save
        self._on_dismiss = on_dismiss

        # Set up as overlay-style widget
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        # Main container with dark academia background
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {BG_PANEL};
                border-top: 1px solid {BORDER_SOFT};
                border-radius: 8px 8px 0 0;
            }}
            QLabel#companion-label {{
                color: {ACCENT_GOLD_DIM};
                font-family: "Georgia", serif;
                font-size: 11px;
                font-style: italic;
                padding: 4px 8px;
            }}
            QLineEdit#capture-input {{
                background-color: transparent;
                color: {TEXT_PRIMARY};
                border: none;
                border-radius: 6px;
                padding: 8px 12px;
                font-family: "Georgia", serif;
                font-size: 13px;
                selection-background-color: {SELECTION_BG};
                caret-color: {ACCENT_GOLD};
            }}
            QLineEdit#capture-input:focus {{
                border: none;
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)

        # Label/icon
        label = QLabel("companion ·")
        label.setObjectName("companion-label")
        layout.addWidget(label)

        # Text input
        self.input_field = QLineEdit()
        self.input_field.setObjectName("capture-input")
        self.input_field.setPlaceholderText("Capture a thought...")
        self.input_field.returnPressed.connect(self._save_and_close)
        layout.addWidget(self.input_field, stretch=1)

        self.setFixedHeight(44)
        self.setMinimumWidth(400)
        self.setMaximumWidth(600)

    def show_at_bottom(self, editor_widget: QWidget) -> None:
        """Position the bar at the bottom of the editor."""
        editor_rect = editor_widget.rect()
        editor_global_pos = editor_widget.mapToGlobal(editor_rect.topLeft())

        bar_width = min(600, max(400, editor_rect.width() - 40))
        x = editor_global_pos.x() + 20
        y = editor_global_pos.y() + editor_rect.height() - 60

        self.setGeometry(x, y, bar_width, 44)
        self.show()
        self.input_field.setFocus()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self._dismiss_without_save()
        else:
            super().keyPressEvent(event)

    def _save_and_close(self) -> None:
        text = self.input_field.text().strip()
        if text:
            self._on_save(text)
        else:
            self._dismiss_without_save()

    def _dismiss_without_save(self) -> None:
        self._on_dismiss()

    def get_text(self) -> str:
        return self.input_field.text().strip()


class CompanionNoteItem(QWidget):
    """A single companion note item for the review panel."""

    def __init__(
        self,
        note_id: int,
        note_text: str,
        captured_at: str,
        chapter_context: str | None,
        on_dismiss: callable,
        on_copy: callable,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._note_id = note_id
        self._on_dismiss = on_dismiss
        self._on_copy = on_copy

        self.setStyleSheet(f"""
            QWidget {{
                background-color: {BG_CARD};
                border: 1px solid {BORDER_SOFT};
                border-radius: 8px;
            }}
            QLabel#note-text {{
                color: {TEXT_PRIMARY};
                font-family: "Georgia", serif;
                font-size: 12px;
                padding: 8px 10px;
            }}
            QLabel#note-meta {{
                color: {TEXT_FAINT};
                font-family: "Georgia", serif;
                font-size: 10px;
                padding: 0 10px 6px 10px;
            }}
            QPushButton {{
                background-color: transparent;
                border: 1px solid {BORDER_SOFT};
                border-radius: 6px;
                padding: 4px 10px;
                color: {TEXT_SECONDARY};
                font-family: "Georgia", serif;
                font-size: 11px;
            }}
            QPushButton:hover {{
                background-color: {BG_CARD_HOVER};
                border-color: {SCROLLBAR_HANDLE};
            }}
            QPushButton#dismiss-btn:hover {{
                background-color: rgba(107, 143, 113, 0.2);
                border-color: {ACCENT_GREEN};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        # Note text
        self.note_label = QLabel(note_text)
        self.note_label.setObjectName("note-text")
        self.note_label.setWordWrap(True)
        layout.addWidget(self.note_label)

        # Meta info (date, chapter)
        meta_parts = []
        try:
            dt = datetime.fromisoformat(captured_at.replace("Z", "+00:00"))
            meta_parts.append(dt.strftime("%Y-%m-%d %H:%M"))
        except Exception:
            meta_parts.append(captured_at[:16] if captured_at else "")
        if chapter_context:
            meta_parts.append(f"· {chapter_context}")
        meta_text = "  ".join(meta_parts)

        self.meta_label = QLabel(meta_text)
        self.meta_label.setObjectName("note-meta")
        layout.addWidget(self.meta_label)

        # Action buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(6)

        self.copy_btn = QPushButton("Copy")
        self.copy_btn.clicked.connect(lambda: self._on_copy(note_text))
        button_layout.addWidget(self.copy_btn)

        button_layout.addStretch(1)

        self.dismiss_btn = QPushButton("Dismiss")
        self.dismiss_btn.setObjectName("dismiss-btn")
        self.dismiss_btn.clicked.connect(lambda: self._on_dismiss(note_id))
        button_layout.addWidget(self.dismiss_btn)

        layout.addLayout(button_layout)


class CompanionReviewPanel(QWidget):
    """Dockable panel for reviewing Companion Doc notes."""

    def __init__(
        self,
        methodology_db: MethodologyDB,
        compost_dir: Path,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._methodology_db = methodology_db
        self._compost_dir = compost_dir

        self.setObjectName("companion-review-panel")
        self.setStyleSheet(f"""
            QWidget#companion-review-panel {{
                background-color: {BG_PANEL};
                border-right: 1px solid {BORDER_SOFT};
            }}
            QLabel#companion-title {{
                font-family: "Georgia", serif;
                font-size: 10px;
                letter-spacing: 0.15em;
                text-transform: uppercase;
                color: {TEXT_FAINT};
                padding: 12px 12px 6px 12px;
            }}
            QScrollArea {{
                background-color: transparent;
                border: none;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Title
        title_label = QLabel("Companion Doc")
        title_label.setObjectName("companion-title")
        layout.addWidget(title_label)

        # Scrollable content
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        layout.addWidget(self.scroll_area, stretch=1)

        # Container for notes
        self.notes_container = QWidget()
        self.notes_layout = QVBoxLayout(self.notes_container)
        self.notes_layout.setContentsMargins(8, 8, 8, 8)
        self.notes_layout.setSpacing(8)
        self.notes_layout.addStretch(1)
        self.scroll_area.setWidget(self.notes_container)

        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self.refresh_notes)

        self._load_notes()

    def refresh_notes(self) -> None:
        self._load_notes()

    def showEvent(self, event) -> None:
        self.refresh_notes()
        self._refresh_timer.start(2000)
        super().showEvent(event)

    def hideEvent(self, event) -> None:
        self._refresh_timer.stop()
        super().hideEvent(event)

    def _load_notes(self) -> None:
        """Load companion notes from the database."""
        # Clear existing items
        while self.notes_layout.count():
            item = self.notes_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Load from DB (non-dismissed, newest first)
        notes_data = self._get_notes()

        if not notes_data:
            empty_label = QLabel("No companion notes yet.\nPress Ctrl+Shift+C to capture a thought.")
            empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_label.setStyleSheet(f"""
                color: {TEXT_FAINT};
                font-family: "Georgia", serif;
                font-size: 12px;
                padding: 20px;
            """)
            self.notes_layout.addWidget(empty_label)
            self.notes_layout.addStretch(1)
            return

        for note in notes_data:
            note_item = CompanionNoteItem(
                note_id=int(note[0]),
                note_text=note[1],
                captured_at=note[2],
                chapter_context=note[3],
                on_dismiss=self._on_note_dismiss,
                on_copy=self._on_note_copy,
                parent=self,
            )
            self.notes_layout.insertWidget(self.notes_layout.count() - 1, note_item)

    def _get_notes(self) -> list[tuple[int, str, str, str | None]]:
        """Get non-dismissed notes from the database.
        Returns list of (id, note, captured_at, chapter_context) tuples.
        """
        return self._methodology_db.get_active_companion_notes()

    def _save_note_dismissal(self, note_id: int, note_text: str) -> None:
        """Mark a note as dismissed and write to compost."""
        dismissed_at = _local_timestamp()
        self._methodology_db.dismiss_companion_note(note_id)

        # Write to compost
        self._write_to_compost(note_text, dismissed_at)

    def _write_to_compost(self, note_text: str, timestamp: str) -> None:
        """Write dismissed note to compost directory."""
        self._compost_dir.mkdir(parents=True, exist_ok=True)

        # Create filename-safe excerpt
        excerpt = note_text[:30].replace(" ", "_").replace("/", "-")
        if not excerpt:
            excerpt = "note"

        filename = f"companion_{timestamp.replace(':', '-').replace('T', '_')}__{excerpt}.txt"
        path = self._compost_dir / filename

        # Ensure unique filename
        counter = 1
        while path.exists():
            filename = f"companion_{timestamp.replace(':', '-').replace('T', '_')}__{excerpt}_{counter}.txt"
            path = self._compost_dir / filename
            counter += 1

        path.write_text(f"Companion Doc Note\nCaptured: {timestamp}\n\n{note_text}\n", encoding="utf-8")

    def _on_note_dismiss(self, note_id: int) -> None:
        """Handle note dismissal."""
        # Get note text before dismissing
        notes_data = self._get_notes()
        note_text = ""
        for note in notes_data:
            if int(note[0]) == note_id:
                note_text = note[1]
                break

        if note_text:
            self._save_note_dismissal(note_id, note_text)
            self._load_notes()  # Refresh

    def _on_note_copy(self, note_text: str) -> None:
        """Handle note copy to clipboard."""
        clipboard = QApplication.clipboard()
        clipboard.setText(note_text)


class SceneNode(QGraphicsEllipseItem):
    def __init__(self, scene_id: int, title: str) -> None:
        # Larger, softer rounded node for organic feel
        super().__init__(-14, -14, 28, 28)
        self.scene_id = scene_id
        self.edges: list[SceneSeam] = []
        # Warm, inviting amber/honey tones
        self.setBrush(QColor("#E8D4A8"))  # Soft warm gold
        pen = QPen(QColor("#C9B896"))  # Warm border
        pen.setWidthF(1.5)
        self.setPen(pen)
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable
            | QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )
        self.setZValue(2)

        self.label = QGraphicsSimpleTextItem(title[:18], self)
        self.label.setBrush(QColor("#6B665E"))  # Warm text color
        self.label.setPos(18, -7)
        self.label.setAcceptedMouseButtons(Qt.MouseButton.NoButton)

    def add_edge(self, edge) -> None:
        self.edges.append(edge)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            for edge in self.edges:
                edge.update_path()
        return super().itemChange(change, value)


class SceneSeam(QGraphicsPathItem):
    def __init__(self, start: SceneNode, end: SceneNode) -> None:
        super().__init__()
        self.start = start
        self.end = end
        self.start.add_edge(self)
        self.end.add_edge(self)
        # Softer, warmer connection lines
        pen = QPen(QColor("#D4CBBB"))  # Warm taupe
        pen.setWidthF(1.0)  # Lighter weight for gentler appearance
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        self.setPen(pen)
        self.setZValue(1)
        self.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
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


class ConstellationView(QGraphicsView):
    def __init__(self, db_path: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._db_path = db_path
        self.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self._panning = False
        self._pan_start = QPointF()
        # Warm, cozy background for constellation view
        self.setStyleSheet(f"""
            QGraphicsView {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #FAF8F4, stop:0.5 {APP_BG}, stop:1 #F5F2EC);
                border: none;
                border-radius: {BORDER_RADIUS_SM};
            }}
        """)
        self._scene.setBackgroundBrush(QColor("#FAF8F4"))
        self.refresh()

    def set_db_path(self, db_path: Path) -> None:
        self._db_path = db_path

    def refresh(self) -> None:
        self._scene.clear()
        if not self._db_path.exists():
            self._scene.addText("No vault.db found.")
            return

        conn = sqlite3.connect(self._db_path)
        try:
            try:
                scenes = conn.execute(
                    "SELECT id, title, position FROM scenes ORDER BY position"
                ).fetchall()
                rows = conn.execute(
                    "SELECT scene_id, entity_id FROM scene_entities"
                ).fetchall()
            except sqlite3.OperationalError:
                self._scene.addText("Vault schema incomplete.")
                return
        finally:
            conn.close()

        if not scenes:
            self._scene.addText("No scenes to map yet.")
            return

        scene_entities: dict[int, set[int]] = {}
        for scene_id, _, _ in scenes:
            scene_entities[scene_id] = set()
        for scene_id, entity_id in rows:
            scene_entities.setdefault(scene_id, set()).add(entity_id)

        nodes: dict[int, tuple[float, float, str]] = {}
        step = 0.65
        for index, (scene_id, title, _) in enumerate(scenes):
            t = index * step
            radius = 32 + (24 * t)
            x = radius * math.cos(t)
            y = radius * math.sin(t)
            nodes[scene_id] = (x, y, title)

        node_items: dict[int, SceneNode] = {}
        for scene_id, (x, y, title) in nodes.items():
            node = SceneNode(scene_id, title)
            node.setPos(x, y)
            self._scene.addItem(node)
            node_items[scene_id] = node

        for left_id, left_set in scene_entities.items():
            for right_id in scene_entities:
                if right_id <= left_id:
                    continue
                overlap = len(left_set & scene_entities[right_id])
                if overlap < 2:
                    continue
                seam = SceneSeam(node_items[left_id], node_items[right_id])
                self._scene.addItem(seam)

        self._scene.setSceneRect(self._scene.itemsBoundingRect().adjusted(-60, -60, 60, 60))

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


class HearthWindow(QMainWindow):
    _scan_finished_signal = pyqtSignal(bool, str)

    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window
        )
        # Warm, sanctuary-like main window styling
        self.setStyleSheet(f"""
            QMainWindow {{
                background: {APP_BG};
                color: {TEXT_COLOR};
            }}
            QMenu {{
                background: #FDFCFA;
                border: 1px solid {BORDER_COLOR};
                border-radius: {BORDER_RADIUS_SM};
                padding: 6px 4px;
            }}
            QMenu::item {{
                padding: 8px 24px 8px 12px;
                border-radius: 6px;
                margin: 2px 4px;
            }}
            QMenu::item:selected {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {ACCENT}, stop:1 {ACCENT_HOVER});
                color: #2D3B2D;
            }}
            QMenu::separator {{
                height: 1px;
                background: {BORDER_COLOR};
                margin: 6px 8px;
            }}
            QMessageBox {{
                background: {APP_BG};
            }}
            QMessageBox QLabel {{
                color: {TEXT_COLOR};
                padding: 8px;
            }}
            QMessageBox QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #FDFCFA, stop:1 #F5F2EC);
                border: 1px solid {BORDER_COLOR};
                border-radius: {BORDER_RADIUS_SM};
                padding: 8px 20px;
                color: {TEXT_COLOR};
                font-weight: 500;
                min-width: 70px;
            }}
            QMessageBox QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #FFFFFF, stop:1 #F9F7F3);
                border-color: #D5D1C8;
            }}
            QInputDialog {{
                background: {APP_BG};
            }}
            QInputDialog QLabel {{
                color: {TEXT_COLOR};
            }}
            QInputDialog QLineEdit {{
                background: #FDFCFA;
                border: 1px solid {BORDER_COLOR};
                border-radius: 6px;
                padding: 8px 12px;
                color: {TEXT_COLOR};
            }}
            QInputDialog QLineEdit:focus {{
                border-color: {ACCENT};
            }}
            QInputDialog QTextEdit {{
                background: #FDFCFA;
                border: 1px solid {BORDER_COLOR};
                border-radius: 6px;
                padding: 8px;
                color: {TEXT_COLOR};
            }}
            QInputDialog QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #FDFCFA, stop:1 #F5F2EC);
                border: 1px solid {BORDER_COLOR};
                border-radius: {BORDER_RADIUS_SM};
                padding: 8px 20px;
                color: {TEXT_COLOR};
                font-weight: 500;
                min-width: 70px;
            }}
            QInputDialog QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #FFFFFF, stop:1 #F9F7F3);
            }}
            QToolTip {{
                background: #FDFCFA;
                color: {TEXT_COLOR};
                border: 1px solid {BORDER_COLOR};
                border-radius: 6px;
                padding: 6px 10px;
            }}
        """)
        self._scan_inflight = False
        self._executor = ThreadPoolExecutor(max_workers=1)
        self._project_root: Path | None = None
        self._db_path: Path | None = None
        self._chapters_dir: Path | None = None
        self._chapters: list[tuple[int, str, Path]] = []
        self._current_chapter_id: int | None = None
        self._current_chapter_path: Path | None = None
        self._project_name = "No Project"
        self._project_id = ""
        self._spacy_available = False
        self._scan_has_data = False
        self._editor_settings = dict(DEFAULT_EDITOR_SETTINGS)
        self._daily_goal = DEFAULT_DAILY_GOAL
        self._chapter_word_counts: dict[Path, int] = {}
        self._session_start_project_words = 0
        self._logged_writing_dates: set[str] = set()
        self._chapter_notes: list[dict[str, object]] = []
        self._active_note_id: int | None = None
        self._focus_mode = False
        self._focus_restore_state: dict[str, bool] = {}
        self._companion_capture_cursor: QTextCursor | None = None
        self._suspend_note_offset_updates = False

        # Exhale feature state
        self._exhale_target: int | None = None
        self._exhale_session_baseline: int | None = None
        self._exhale_completed = False

        # Sparks feature state
        self._sparks_panel: SparksPanel | None = None
        self._sparks_dock: QDockWidget | None = None

        # Companion Doc feature state
        self._companion_capture_bar: CompanionCaptureBar | None = None
        self._companion_review_panel: CompanionReviewPanel | None = None
        self._companion_dock: QDockWidget | None = None

        self._setup_ui()
        self._project_service = ProjectService(DEFAULT_EDITOR_SETTINGS, DEFAULT_DAILY_GOAL)
        self._export_service = ExportService()
        self._nlp_service = NLPService(enhanced=ENHANCED_SHADOW_BIBLE)
        self._methodology_db: MethodologyDB | None = None
        self._annotation_manager = AnnotationManager(
            self.editor,
            note_highlight=NOTE_HIGHLIGHT,
            active_highlight=NOTE_HIGHLIGHT_ACTIVE,
            warning_callback=self._show_nonblocking_warning,
            logger=LOGGER,
        )
        self._annotation_manager.set_notes_panel(self._notes_panel)
        self._setup_editor()
        self._ensure_project()
        self._scan_finished_signal.connect(self._on_scan_future_finished)
        self._initialize_scan_health()
        self._init_timers()

    def _setup_ui(self) -> None:
        self.title_bar = TitleBar(self, self._open_project_manager, self._toggle_constellation)
        self.status_bar = StatusBar(self)

        self.editor = QTextEdit()
        self.editor.setObjectName("hearth")
        self.editor.setFrameStyle(QFrame.Shape.NoFrame)
        # Aged paper in a dark room — warm, textured, inviting
        self.editor.setStyleSheet(f"""
            QTextEdit#hearth {{
                background-color: {BG_SURFACE};
                color: {TEXT_HEARTH};
                font-family: "Georgia", "Palatino Linotype", "Book Antiqua", serif;
                font-size: 16px;
                border: none;
                selection-background-color: {SELECTION_BG};
                selection-color: {BG_SURFACE};
            }}
        """)
        self.editor.installEventFilter(self)
        self.editor.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.editor.customContextMenuRequested.connect(self._show_editor_context_menu)

        self.shell = TypewriterShell(self.editor)

        central = QWidget()
        central.setObjectName("central-shell")
        # Rounded corners on the central shell for a softer appearance
        central.setStyleSheet(f"""
            QWidget#central-shell {{
                background: {APP_BG};
                border-radius: {BORDER_RADIUS};
            }}
        """)
        self.setCentralWidget(central)

        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_layout.addWidget(self.title_bar)
        main_layout.addWidget(self.shell, stretch=1)
        main_layout.addWidget(self.status_bar)

        self._chapters_panel = ChaptersPanel(
            self._on_chapter_selected,
            self._new_chapter,
            self._delete_chapter,
        )
        self._chapters_dock = QDockWidget("Chapters", self)
        self._chapters_dock.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea)
        self._chapters_dock.setWidget(self._chapters_panel)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self._chapters_dock)

        self._storylines_panel = StorylinesPanel(
            self._on_storyline_toggled,
            self._new_storyline,
        )
        self._storylines_dock = QDockWidget("Storylines", self)
        self._storylines_dock.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea)
        self._storylines_dock.setWidget(self._storylines_panel)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self._storylines_dock)

        self._outliner_panel = OutlinerPanel(
            self._select_chapter,
            self._new_chapter,
            self._delete_chapter,
            self._reorder_chapters_from_outliner,
            self._update_chapter_synopsis,
        )
        self._outliner_dock = QDockWidget("Outliner", self)
        self._outliner_dock.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
        self._outliner_dock.setWidget(self._outliner_panel)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._outliner_dock)

        self._notes_panel = NotesPanel(
            self._focus_note_from_panel,
            self._edit_note_from_panel,
            self._delete_note_from_panel,
        )
        self._notes_dock = QDockWidget("Notes", self)
        self._notes_dock.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
        self._notes_dock.setWidget(self._notes_panel)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._notes_dock)

        self._constellation_dock = QDockWidget("Spiral Constellation", self)
        self._constellation_dock.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
        self._constellation_dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetFloatable
            | QDockWidget.DockWidgetFeature.DockWidgetClosable
        )
        # Use enhanced view for character/palette/theme visualization
        if ENHANCED_CONSTELLATION:
            self._constellation_view = EnhancedConstellationView(Path("vault.db"), self)
        else:
            self._constellation_view = ConstellationView(Path("vault.db"), self)
        self._constellation_dock.setWidget(self._constellation_view)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._constellation_dock)
        self._constellation_dock.hide()

        # Sparks dock (daily intentions panel)
        self._sparks_dock = QDockWidget("Sparks", self)
        self._sparks_dock.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
        self._sparks_dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetFloatable
            | QDockWidget.DockWidgetFeature.DockWidgetClosable
        )
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._sparks_dock)
        self._sparks_dock.hide()

        # Companion Doc dock (review panel)
        self._companion_dock = QDockWidget("Companion Doc", self)
        self._companion_dock.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
        self._companion_dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetFloatable
            | QDockWidget.DockWidgetFeature.DockWidgetClosable
        )
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._companion_dock)
        self._companion_dock.hide()

        self._apply_styles()
        self._setup_fade_targets()

        self._actions_menu = QMenu(self)
        self._actions_menu.addAction("Library / Index", self._open_library)
        self._actions_menu.addAction("Toggle Outliner", self._toggle_outliner)
        self._actions_menu.addAction("Toggle Notes", self._toggle_notes)
        self._actions_menu.addAction("Sparks (Ctrl+Shift+S)", self._toggle_sparks)
        self._actions_menu.addAction("Companion Doc Review (Ctrl+Shift+D)", self._toggle_companion_review)
        self._actions_menu.addAction("Add Note (Ctrl+Shift+N)", self._add_inline_note_from_selection)
        self._actions_menu.addSeparator()
        self._actions_menu.addAction("Ingest Voice Notes", self._ingest_voice_notes)
        self._actions_menu.addAction("Rebuild Index.json", self._rebuild_index)
        self._actions_menu.addSeparator()
        self._actions_menu.addAction("Toggle Focus Mode (F11)", self._toggle_focus_mode)
        self._actions_menu.addSeparator()
        self._actions_menu.addAction("Set Exhale (Ctrl+Shift+E)", self._set_exhale)
        self._actions_menu.addSeparator()
        self._settings_menu = self._actions_menu.addMenu("Editor Settings")
        self._build_editor_settings_menu()
        self._actions_menu.addSeparator()
        self._actions_menu.addAction("Generate Character Palette", self._generate_character_palette)
        self._actions_menu.addAction("Export Markdown", self._export_markdown)
        self._actions_menu.addAction("Export PDF", self._export_pdf)
        self.title_bar.actions_button.setMenu(self._actions_menu)

        self._shortcut_constellation = QShortcut(
            QKeySequence("Ctrl+M"),
            self,
            activated=self._toggle_constellation,
        )
        self._shortcut_focus_mode = QShortcut(
            QKeySequence("F11"),
            self,
            activated=self._toggle_focus_mode,
        )
        self._shortcut_add_note = QShortcut(
            QKeySequence("Ctrl+Shift+N"),
            self.editor,
            activated=self._add_inline_note_from_selection,
        )
        self._shortcut_exhale = QShortcut(
            QKeySequence("Ctrl+Shift+E"),
            self,
            activated=self._set_exhale,
        )
        self._shortcut_sparks = QShortcut(
            QKeySequence("Ctrl+Shift+S"),
            self,
            activated=self._toggle_sparks,
        )
        self._shortcut_companion_capture = QShortcut(
            QKeySequence("Ctrl+Shift+C"),
            self,
            activated=self._open_companion_capture,
        )
        self._shortcut_companion_review = QShortcut(
            QKeySequence("Ctrl+Shift+D"),
            self,
            activated=self._toggle_companion_review,
        )

    def _apply_styles(self) -> None:
        # Title bar — dark academia manuscript header
        self.title_bar.setStyleSheet(
            f"""
            QFrame#title-bar {{
                background-color: {BG_DEEP};
                border-bottom: 1px solid {BORDER_SOFT};
            }}
            QLabel#title-text {{
                font-family: "Georgia", serif;
                font-style: italic;
                font-size: 15px;
                letter-spacing: 0.05em;
                color: {ACCENT_GOLD};
            }}
            QLabel#project-label {{
                font-family: "Georgia", serif;
                font-size: 13px;
                color: {TEXT_SECONDARY};
                padding-left: 8px;
            }}
            QLabel#scan-status-label {{
                font-family: "Georgia", "Courier New", monospace;
                font-size: 11px;
                color: {TEXT_FAINT};
                padding-left: 8px;
            }}
            QPushButton#project-button, QPushButton#map-button, QPushButton#actions-button {{
                background-color: transparent;
                color: {TEXT_SECONDARY};
                border: 1px solid {BORDER_SOFT};
                border-radius: 6px;
                padding: 4px 12px;
                font-family: "Georgia", serif;
                font-size: 12px;
            }}
            QPushButton#project-button:hover, QPushButton#map-button:hover, QPushButton#actions-button:hover {{
                background-color: {BG_CARD};
                color: {TEXT_PRIMARY};
                border-color: {SCROLLBAR_HANDLE};
            }}
            QPushButton#project-button:pressed, QPushButton#map-button:pressed, QPushButton#actions-button:pressed,
            QPushButton#project-button:checked, QPushButton#map-button:checked, QPushButton#actions-button:checked {{
                background-color: {SELECTION_BG};
                color: {ACCENT_GOLD};
                border-color: {ACCENT_GOLD_DIM};
            }}
            QPushButton#min-button, QPushButton#close-button {{
                background-color: transparent;
                color: {TEXT_FAINT};
                border: none;
                font-size: 14px;
                padding: 0;
            }}
            QPushButton#min-button:hover, QPushButton#close-button:hover {{
                color: {ACCENT_GOLD};
            }}
            """
        )
        # Echo label — soft margin note
        self.shell.echo_label.setStyleSheet(
            f"""
            QLabel#echo-label {{
                background-color: {BG_CARD};
                color: {TEXT_PRIMARY};
                border: 1px solid {BORDER_SOFT};
                border-radius: 8px;
                padding: 10px 12px;
                font-family: "Georgia", serif;
                font-size: 12px;
                line-height: 1.4;
            }}
            """
        )
        # Sidebar panels — soft rounded journal tabs
        panel_style = f"""
            QWidget#chapters-panel, QWidget#storylines-panel, QWidget#outliner-panel, QWidget#notes-panel {{
                background-color: {BG_PANEL};
                border-right: 1px solid {BORDER_SOFT};
                padding: 8px;
            }}
            QLabel#panel-title {{
                font-family: "Georgia", serif;
                font-size: 10px;
                font-weight: normal;
                letter-spacing: 0.15em;
                text-transform: uppercase;
                color: {TEXT_FAINT};
                padding: 12px 8px 6px 8px;
            }}
            QListWidget {{
                background-color: {BG_PANEL};
                border: none;
                outline: none;
            }}
            QListWidget::item {{
                background-color: {BG_CARD};
                border-radius: 8px;
                padding: 8px 12px;
                margin: 2px 4px;
                color: {TEXT_PRIMARY};
                font-family: "Georgia", serif;
                font-size: 13px;
                border: 1px solid transparent;
            }}
            QListWidget::item:hover {{
                background-color: {BG_CARD_HOVER};
                border-color: {BORDER_SOFT};
            }}
            QListWidget::item:selected {{
                background-color: {SELECTION_BG};
                border-color: {ACCENT_GOLD_DIM};
                color: {ACCENT_GOLD};
            }}
            QPushButton {{
                background-color: transparent;
                color: {TEXT_FAINT};
                border: 1px solid {BORDER_SOFT};
                border-radius: 6px;
                padding: 4px 10px;
                font-family: "Georgia", serif;
                font-size: 11px;
            }}
            QPushButton:hover {{
                color: {TEXT_SECONDARY};
                border-color: {SCROLLBAR_HANDLE};
            }}
            QPushButton:pressed {{
                color: {ACCENT_GOLD};
            }}
        """
        for panel in (
            self._chapters_panel,
            self._storylines_panel,
            self._outliner_panel,
            self._notes_panel,
        ):
            panel.setStyleSheet(panel_style)

        # Dock widget styling — soft headers
        dock_style = f"""
            QDockWidget {{
                background-color: {BG_PANEL};
                titlebar-close-icon: url(none);
                titlebar-normal-icon: url(none);
            }}
            QDockWidget::title {{
                padding: 10px 12px;
                background-color: {BG_CARD};
                border-bottom: 1px solid {BORDER_SOFT};
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                text-align: left;
                font-family: "Georgia", serif;
                font-size: 11px;
                font-weight: normal;
                letter-spacing: 0.1em;
                color: {TEXT_SECONDARY};
            }}
        """
        self._constellation_dock.setStyleSheet(dock_style)
        for dock in (
            self._chapters_dock,
            self._storylines_dock,
            self._outliner_dock,
            self._notes_dock,
        ):
            dock.setStyleSheet(dock_style)

    def _setup_editor(self) -> None:
        self._apply_editor_font()
        self.editor.setCursorWidth(2)
        self.editor.textChanged.connect(self._on_text_changed)
        self.editor.document().contentsChange.connect(self._on_document_contents_change)
        self._apply_line_spacing()
        self._load_draft()

    def _ensure_project(self) -> None:
        PROJECTS_ROOT.mkdir(parents=True, exist_ok=True)
        if not _list_projects(PROJECTS_ROOT):
            _create_project(PROJECTS_ROOT / "default", "Default Project")
        if not self._open_project_manager():
            QApplication.instance().quit()

    def _open_project_manager(self) -> bool:
        dialog = ProjectManagerDialog(PROJECTS_ROOT, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return False
        selected = dialog.selected_project()
        if not selected:
            return False
        self._load_project(selected)
        return True

    def _load_project(self, root: Path) -> None:
        if self._project_root and self._project_root != root:
            self._log_session_writing()

        meta = self._project_service.ensure_project_id(root, line_height_percent=LINE_HEIGHT_PERCENT)
        self._project_root = root
        self._project_name = meta.get("name", root.name)
        self._project_id = str(meta.get("project_id") or "")
        self._methodology_db = MethodologyDB(
            root / "vault.db",
            self._project_id,
            LOGGER,
            warning_callback=self._show_nonblocking_warning,
        )
        self.title_bar.set_project_name(self._project_name)
        self._editor_settings = self._project_service.normalize_editor_settings(
            meta.get("editor_settings"),
            LINE_HEIGHT_PERCENT,
        )
        try:
            self._daily_goal = max(1, int(meta.get("daily_goal", DEFAULT_DAILY_GOAL)))
        except (TypeError, ValueError):
            self._daily_goal = DEFAULT_DAILY_GOAL
        self._apply_editor_font()
        self._apply_line_spacing()
        self._sync_editor_settings_actions()

        # Reset Exhale session state on project load
        self._exhale_target = None
        self._exhale_session_baseline = None
        self._exhale_completed = False

        # Reset Sparks panel on project load
        if self._sparks_dock is not None:
            self._sparks_dock.hide()
        self._sparks_panel = None

        # Reset Companion Doc on project load
        if self._companion_dock is not None:
            self._companion_dock.hide()
        self._companion_review_panel = None
        if self._companion_capture_bar is not None:
            self._companion_capture_bar.close()

        self._chapters_dir = self._project_service.ensure_chapters_dir(root)
        self._db_path = root / "vault.db"
        conn = sqlite3.connect(self._db_path)
        try:
            ensure_vault_schema(conn)
            ensure_default_chapter_schema(conn, self._chapters_dir)
            if self._methodology_db is not None:
                self._methodology_db.migrate_project_ids(conn, root)
        finally:
            conn.close()

        self._constellation_view.set_db_path(self._db_path)
        self._load_chapters()
        self._load_storylines()
        self._load_logged_writing_dates()
        self._scan_has_data = self._has_scan_data()
        self._session_start_project_words = self._project_word_total()
        if self._chapters:
            self._select_chapter(self._chapters[0][0])

    def _build_editor_settings_menu(self) -> None:
        self._font_action_group = QActionGroup(self)
        self._font_action_group.setExclusive(True)
        self._font_actions: dict[str, QAction] = {}
        font_menu = self._settings_menu.addMenu("Font Family")
        for family in EDITOR_FONT_FAMILIES:
            action = font_menu.addAction(family)
            action.setCheckable(True)
            action.triggered.connect(
                lambda checked=False, family_name=family: self._set_font_family(family_name)
            )
            self._font_action_group.addAction(action)
            self._font_actions[family] = action

        self._settings_menu.addAction("Font Size...", self._open_font_size_dialog)
        self._settings_menu.addAction("Daily Goal...", self._set_daily_goal)
        self._settings_menu.addSeparator()

        self._line_height_action_group = QActionGroup(self)
        self._line_height_action_group.setExclusive(True)
        self._line_height_actions: dict[str, QAction] = {}
        line_height_menu = self._settings_menu.addMenu("Line Height")
        for mode, label in (
            ("normal", "Normal"),
            ("relaxed", "Relaxed"),
            ("spacious", "Spacious"),
        ):
            action = line_height_menu.addAction(label)
            action.setCheckable(True)
            action.triggered.connect(
                lambda checked=False, line_mode=mode: self._set_line_height(line_mode)
            )
            self._line_height_action_group.addAction(action)
            self._line_height_actions[mode] = action

        self._typewriter_scroll_action = self._settings_menu.addAction("Typewriter Scroll")
        self._typewriter_scroll_action.setCheckable(True)
        self._typewriter_scroll_action.toggled.connect(self._set_typewriter_scroll_enabled)
        self._sync_editor_settings_actions()

    def _sync_editor_settings_actions(self) -> None:
        font_family = str(self._editor_settings.get("font_family", ""))
        if font_family in self._font_actions:
            self._font_actions[font_family].setChecked(True)

        line_height = str(self._editor_settings.get("line_height", "relaxed"))
        if line_height in self._line_height_actions:
            self._line_height_actions[line_height].setChecked(True)

        if hasattr(self, "_typewriter_scroll_action"):
            self._typewriter_scroll_action.blockSignals(True)
            self._typewriter_scroll_action.setChecked(
                bool(self._editor_settings.get("typewriter_scroll", False))
            )
            self._typewriter_scroll_action.blockSignals(False)

    def _set_font_family(self, family: str) -> None:
        self._editor_settings["font_family"] = family
        self._apply_editor_font()
        self._persist_project_preferences()

    def _open_font_size_dialog(self) -> None:
        current_size = int(self._editor_settings.get("font_size", 15))
        dialog = QDialog(self)
        dialog.setWindowTitle("Font Size")
        layout = QVBoxLayout(dialog)
        value_label = QLabel(f"{current_size} pt")
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(12, 24)
        slider.setValue(current_size)
        slider.valueChanged.connect(lambda value: value_label.setText(f"{value} pt"))
        layout.addWidget(value_label)
        layout.addWidget(slider)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self._editor_settings["font_size"] = slider.value()
        self._apply_editor_font()
        self._persist_project_preferences()

    def _set_line_height(self, mode: str) -> None:
        if mode not in LINE_HEIGHT_PERCENT:
            return
        self._editor_settings["line_height"] = mode
        self._apply_line_spacing()
        self._persist_project_preferences()

    def _set_typewriter_scroll_enabled(self, enabled: bool) -> None:
        self._editor_settings["typewriter_scroll"] = bool(enabled)
        self._persist_project_preferences()

    def _set_daily_goal(self) -> None:
        value, ok = QInputDialog.getInt(
            self,
            "Daily Goal",
            "Target words per day:",
            value=int(self._daily_goal),
            min=1,
            max=100000,
            step=50,
        )
        if not ok:
            return
        self._daily_goal = int(value)
        self._persist_project_preferences()
        self._update_status(self.editor.toPlainText())

    def _apply_editor_font(self) -> None:
        family = str(self._editor_settings.get("font_family", DEFAULT_EDITOR_SETTINGS["font_family"]))
        size = int(self._editor_settings.get("font_size", DEFAULT_EDITOR_SETTINGS["font_size"]))
        font = QFont(family, size)
        if any(token in family.casefold() for token in ("courier", "mono", "fira code")):
            font.setStyleHint(QFont.StyleHint.Monospace)
        else:
            font.setStyleHint(QFont.StyleHint.Serif)
        self.editor.setFont(font)

    def _apply_line_spacing(self) -> None:
        line_mode = str(self._editor_settings.get("line_height", "relaxed"))
        line_height = LINE_HEIGHT_PERCENT.get(line_mode, 150)
        fmt = QTextBlockFormat()
        fmt.setLineHeight(
            line_height, QTextBlockFormat.LineHeightTypes.ProportionalHeight.value
        )
        current_cursor = self.editor.textCursor()
        original_position = current_cursor.position()
        cursor = QTextCursor(self.editor.document())
        cursor.select(QTextCursor.SelectionType.Document)
        cursor.setBlockFormat(fmt)
        current_cursor.setPosition(min(original_position, len(self.editor.toPlainText())))
        self.editor.setTextCursor(current_cursor)

    def _persist_project_preferences(self) -> None:
        if not self._project_root:
            return
        self._project_service.save_project_meta(
            self._project_root,
            self._project_name,
            editor_settings=self._editor_settings,
            daily_goal=self._daily_goal,
            line_height_percent=LINE_HEIGHT_PERCENT,
        )

    @staticmethod
    def _count_words(text: str) -> int:
        return len(re.findall(r"[A-Za-z0-9']+", text))

    def _project_word_total(self) -> int:
        return sum(self._chapter_word_counts.values())

    def _words_written_today(self) -> int:
        return max(0, self._project_word_total() - self._session_start_project_words)

    def _current_streak(self) -> int:
        dates = set(self._logged_writing_dates)
        if self._words_written_today() > 0:
            dates.add(date.today().isoformat())
        streak = 0
        current = date.today()
        while current.isoformat() in dates:
            streak += 1
            current = current - timedelta(days=1)
        return streak

    def _load_logged_writing_dates(self) -> None:
        self._logged_writing_dates = set()
        if not self._db_path:
            return
        conn = sqlite3.connect(self._db_path)
        try:
            rows = conn.execute(
                "SELECT date FROM writing_log WHERE words_written > 0"
            ).fetchall()
        finally:
            conn.close()
        self._logged_writing_dates = {str(row[0]) for row in rows if row and row[0]}

    def _log_session_writing(self) -> None:
        if not self._db_path:
            return
        written = self._words_written_today()
        if written <= 0:
            return
        today = date.today().isoformat()
        conn = sqlite3.connect(self._db_path)
        try:
            conn.execute(
                """
                INSERT INTO writing_log (date, words_written)
                VALUES (?, ?)
                ON CONFLICT(date) DO UPDATE SET
                    words_written = writing_log.words_written + excluded.words_written
                """,
                (today, written),
            )
            conn.commit()
        finally:
            conn.close()
        self._session_start_project_words = self._project_word_total()
        self._logged_writing_dates.add(today)

    def _setup_fade_targets(self) -> None:
        self._fade_targets = [
            self.title_bar.project_button,
            self.title_bar.map_button,
            self.title_bar.actions_button,
            self.title_bar.min_button,
            self.title_bar.close_button,
            self.status_bar,
        ]
        self._fade_effects: dict[QWidget, QGraphicsOpacityEffect] = {}
        for widget in self._fade_targets:
            effect = QGraphicsOpacityEffect(widget)
            effect.setOpacity(1.0)
            widget.setGraphicsEffect(effect)
            self._fade_effects[widget] = effect
        self._fade_anims: list[QPropertyAnimation] = []
        self._controls_dimmed = False

    def _init_timers(self) -> None:
        self._typing_timer = QTimer(self)
        self._typing_timer.setSingleShot(True)
        self._typing_timer.timeout.connect(self._on_typing_stopped)

        self._cursor_timer = QTimer(self)
        self._cursor_timer.timeout.connect(self._pulse_cursor)
        self._cursor_timer.start(700)
        self._cursor_wide = False

        self._scan_timer = QTimer(self)
        self._scan_timer.timeout.connect(self._trigger_scan)
        self._scan_timer.start(SCAN_INTERVAL_SECONDS * 1000)
        self._trigger_scan()

    def _initialize_scan_health(self) -> None:
        self._spacy_available = self._nlp_service.check_spacy_availability()
        self._scan_has_data = self._nlp_service.has_scan_data(self._db_path)
        if self._spacy_available:
            self._set_scan_status("⟳ Scanning...")
        else:
            self._set_scan_status("⚠ spaCy unavailable — NLP features disabled")

    @staticmethod
    def _check_spacy_availability() -> bool:
        return NLPService.check_spacy_availability()

    def _has_scan_data(self) -> bool:
        return self._nlp_service.has_scan_data(self._db_path)

    def _set_scan_status(self, status: str) -> None:
        self.title_bar.set_scan_status(status)
        if hasattr(self, "editor"):
            self._update_echo(self.editor.toPlainText())

    def _show_nonblocking_warning(self, message: str) -> None:
        LOGGER.warning(message)
        self.status_bar.setText(message)
        QTimer.singleShot(5000, lambda: self._update_status(self.editor.toPlainText()))

    def _load_draft(self) -> None:
        self._suspend_note_offset_updates = True
        try:
            self.editor.blockSignals(True)
            self.editor.setPlainText(self._project_service.load_draft(self._current_chapter_path))
            self._apply_line_spacing()
            self.editor.blockSignals(False)
            self._update_status(self.editor.toPlainText())
        finally:
            self._suspend_note_offset_updates = False

    def _save_draft(self, text: str) -> None:
        self._project_service.save_draft(self._current_chapter_path, text)
        if self._current_chapter_path:
            self._chapter_word_counts[self._current_chapter_path] = self._count_words(text)

    def _load_chapters(self) -> None:
        if not self._db_path or not self._chapters_dir:
            return
        self._chapters, self._chapter_word_counts = self._project_service.load_chapters(
            self._db_path,
            self._chapters_dir,
            self._count_words,
        )
        self._clear_chapter_notes()
        self._chapters_panel.list.clear()
        for chapter_id, title, path in self._chapters:
            item = QListWidgetItem(title)
            item.setData(Qt.ItemDataRole.UserRole, chapter_id)
            self._chapters_panel.list.addItem(item)
        self._load_outliner()
        if self._chapters_panel.list.count() > 0:
            self._chapters_panel.list.setCurrentRow(0)

    def _select_chapter(self, chapter_id: int) -> None:
        for item_index in range(self._chapters_panel.list.count()):
            item = self._chapters_panel.list.item(item_index)
            if item and item.data(Qt.ItemDataRole.UserRole) == chapter_id:
                self._chapters_panel.list.setCurrentRow(item_index)
                break
        self._outliner_panel.select_chapter(chapter_id)

        for chap_id, title, path in self._chapters:
            if chap_id == chapter_id:
                self._current_chapter_id = chap_id
                self._current_chapter_path = path
                self._load_draft()
                self._load_notes_for_current_chapter()
                self._load_storylines()
                self._update_echo(self.editor.toPlainText())
                break

    def _on_chapter_selected(self) -> None:
        item = self._chapters_panel.list.currentItem()
        if not item:
            return
        chapter_id = item.data(Qt.ItemDataRole.UserRole)
        if chapter_id == self._current_chapter_id:
            return
        self._select_chapter(int(chapter_id))

    def _new_chapter(self) -> None:
        if not self._db_path or not self._chapters_dir:
            return
        name, ok = QInputDialog.getText(self, "New Chapter", "Chapter title:")
        if not ok or not name.strip():
            return
        title = name.strip()
        chapter_id = self._project_service.create_chapter(self._db_path, self._chapters_dir, title)

        self._load_chapters()
        self._select_chapter(chapter_id)

    def _delete_chapter(self) -> None:
        item = self._chapters_panel.list.currentItem()
        if not item:
            return
        chapter_id = int(item.data(Qt.ItemDataRole.UserRole))
        if len(self._chapters) <= 1:
            QMessageBox.information(self, "Cannot Delete", "At least one chapter is required.")
            return
        confirm = QMessageBox.question(
            self,
            "Delete Chapter",
            "Delete this chapter file? It will be moved to .compost.",
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        chapter = next((c for c in self._chapters if c[0] == chapter_id), None)
        if not chapter or not self._db_path:
            return
        _, _, path = chapter
        if not self._project_root:
            QMessageBox.warning(
                self,
                "Delete Chapter",
                "Project root unavailable. Cannot move file to .compost.",
            )
            return
        try:
            self._project_service.delete_chapter(self._db_path, self._project_root, chapter_id, path)
        except OSError as exc:
            QMessageBox.warning(
                self,
                "Delete Chapter",
                f"Could not move chapter to .compost: {exc}",
            )
            return
        self._load_chapters()

    def _load_storylines(self) -> None:
        if not self._db_path:
            return
        storylines = self._fetch_storylines()
        selected = self._fetch_chapter_storylines(self._current_chapter_id)
        self._storylines_panel.set_storylines(storylines, selected)
        self._load_outliner()

    def _load_outliner(self) -> None:
        if not self._chapters:
            self._outliner_panel.set_outline([])
            return

        storyline_map: dict[int, list[str]] = {}
        if self._db_path:
            conn = sqlite3.connect(self._db_path)
            try:
                rows = conn.execute(
                    """
                    SELECT cs.chapter_id, s.name
                    FROM chapter_storylines cs
                    JOIN storylines s ON s.id = cs.storyline_id
                    ORDER BY s.name
                    """
                ).fetchall()
            finally:
                conn.close()
            for chapter_id, name in rows:
                storyline_map.setdefault(int(chapter_id), []).append(str(name))

        entries: list[dict[str, object]] = []
        for chapter_id, title, path in self._chapters:
            text = ""
            if path.exists():
                text = path.read_text(encoding="utf-8", errors="replace")
            lines = text.splitlines()
            fm = _parse_frontmatter(lines)
            synopsis = str(fm.get("synopsis") or "")
            scenes = _split_scenes(text)
            entries.append(
                {
                    "chapter_id": chapter_id,
                    "title": title,
                    "word_count": self._chapter_word_counts.get(path, 0),
                    "storyline_tags": storyline_map.get(chapter_id, []),
                    "synopsis": synopsis,
                    "scenes": scenes,
                }
            )

        self._outliner_panel.set_outline(entries)
        self._outliner_panel.select_chapter(self._current_chapter_id)

    def _fetch_storylines(self) -> list[tuple[int, str]]:
        if not self._db_path:
            return []
        conn = sqlite3.connect(self._db_path)
        try:
            rows = conn.execute(
                "SELECT id, name FROM storylines ORDER BY name"
            ).fetchall()
        finally:
            conn.close()
        return [(int(row[0]), str(row[1])) for row in rows]

    def _fetch_chapter_storylines(self, chapter_id: int | None) -> set[int]:
        if not self._db_path or chapter_id is None:
            return set()
        conn = sqlite3.connect(self._db_path)
        try:
            rows = conn.execute(
                "SELECT storyline_id FROM chapter_storylines WHERE chapter_id = ?",
                (chapter_id,),
            ).fetchall()
        finally:
            conn.close()
        return {int(row[0]) for row in rows}

    def _on_storyline_toggled(self, item: QListWidgetItem) -> None:
        if self._storylines_panel.is_ignoring():
            return
        if not self._db_path or self._current_chapter_id is None:
            return
        storyline_id = int(item.data(Qt.ItemDataRole.UserRole))
        checked = item.checkState() == Qt.CheckState.Checked
        conn = sqlite3.connect(self._db_path)
        try:
            if checked:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO chapter_storylines (chapter_id, storyline_id)
                    VALUES (?, ?)
                    """,
                    (self._current_chapter_id, storyline_id),
                )
            else:
                conn.execute(
                    """
                    DELETE FROM chapter_storylines
                    WHERE chapter_id = ? AND storyline_id = ?
                    """,
                    (self._current_chapter_id, storyline_id),
                )
            conn.commit()
        finally:
            conn.close()
        self._load_outliner()

    def _new_storyline(self) -> None:
        if not self._db_path:
            return
        name, ok = QInputDialog.getText(self, "New Storyline", "Storyline name:")
        if not ok or not name.strip():
            return
        title = name.strip()
        conn = sqlite3.connect(self._db_path)
        try:
            conn.execute(
                "INSERT OR IGNORE INTO storylines (name, created_at) VALUES (?, ?)",
                (
                    title,
                    datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
                ),
            )
            conn.commit()
        finally:
            conn.close()
        self._load_storylines()

    def _chapter_path_by_id(self, chapter_id: int) -> Path | None:
        for chap_id, _, path in self._chapters:
            if chap_id == chapter_id:
                return path
        return None

    def _update_chapter_synopsis(self, chapter_id: int, synopsis: str) -> None:
        path = self._chapter_path_by_id(chapter_id)
        if not path or not path.exists():
            return
        self._project_service.update_chapter_synopsis(path, synopsis, _upsert_frontmatter_fields)
        self._load_outliner()
        self._update_status(self.editor.toPlainText())

    def _reorder_chapters_from_outliner(self, chapter_ids: list[int]) -> None:
        if not self._db_path:
            return
        if len(chapter_ids) != len(self._chapters):
            self._load_outliner()
            return
        chapter_set = {chapter_id for chapter_id, _, _ in self._chapters}
        if chapter_set != set(chapter_ids):
            self._load_outliner()
            return

        self._project_service.reorder_chapters(
            self._db_path,
            chapter_ids,
            self._chapters,
            _upsert_frontmatter_fields,
        )

        current_id = self._current_chapter_id
        self._load_chapters()
        if current_id is not None:
            self._select_chapter(current_id)

    def _current_chapter_slug(self) -> str | None:
        return self._annotation_manager.current_chapter_slug(self._current_chapter_path)

    @staticmethod
    def _is_attached_note_range(start_pos: int, end_pos: int, doc_len: int) -> bool:
        return AnnotationManager.is_attached_note_range(start_pos, end_pos, doc_len)

    def _clear_chapter_notes(self) -> None:
        self._annotation_manager.clear_notes()
        self._chapter_notes = self._annotation_manager.chapter_notes
        self._active_note_id = self._annotation_manager.active_note_id

    def _load_notes_for_current_chapter(self) -> None:
        self._annotation_manager.load_notes(self._db_path, self._current_chapter_slug())
        self._chapter_notes = self._annotation_manager.chapter_notes
        self._active_note_id = self._annotation_manager.active_note_id

    def _refresh_note_highlights(
        self,
        active_note_id: int | None = None,
        *,
        sync_panel: bool = False,
    ) -> None:
        self._annotation_manager.active_note_id = self._active_note_id
        self._annotation_manager.refresh_highlights(active_note_id, sync_panel=sync_panel)
        self._chapter_notes = self._annotation_manager.chapter_notes
        self._active_note_id = self._annotation_manager.active_note_id

    def _show_editor_context_menu(self, pos: QPoint) -> None:
        menu = self.editor.createStandardContextMenu()
        menu.addSeparator()
        add_note_action = menu.addAction("Add Note")
        add_note_action.setEnabled(self.editor.textCursor().hasSelection())
        add_note_action.triggered.connect(self._add_inline_note_from_selection)
        menu.exec(self.editor.mapToGlobal(pos))

    def _add_inline_note_from_selection(self) -> None:
        if not self._db_path:
            return
        chapter_slug = self._current_chapter_slug()
        if not chapter_slug:
            return

        cursor = self.editor.textCursor()
        if not cursor.hasSelection():
            return
        start_pos = cursor.selectionStart()
        end_pos = cursor.selectionEnd()
        if start_pos == end_pos:
            return

        note_text, ok = QInputDialog.getMultiLineText(
            self,
            "Add Note",
            "Note text:",
            "",
        )
        if not ok:
            return
        cleaned_note = note_text.strip()
        if not cleaned_note:
            return

        note_id = self._annotation_manager.add_note(
            self._db_path,
            chapter_slug,
            start_pos,
            end_pos,
            cleaned_note,
        )

        self._load_notes_for_current_chapter()
        self._active_note_id = note_id
        self._annotation_manager.active_note_id = note_id
        self._refresh_note_highlights(active_note_id=note_id, sync_panel=True)

    def _focus_note_from_panel(self, note_id: int) -> None:
        note = self._annotation_manager.focus_note(note_id)
        self._chapter_notes = self._annotation_manager.chapter_notes
        self._active_note_id = self._annotation_manager.active_note_id
        if note is None:
            return

    def _edit_note_from_panel(self, note_id: int) -> None:
        if not self._db_path:
            return
        note = next((entry for entry in self._chapter_notes if int(entry.get("id", 0)) == note_id), None)
        if note is None:
            return

        updated_text, ok = QInputDialog.getMultiLineText(
            self,
            "Edit Note",
            "Note text:",
            str(note.get("note_text") or ""),
        )
        if not ok:
            return
        cleaned_note = updated_text.strip()
        if not cleaned_note:
            return

        self._annotation_manager.update_note_text(self._db_path, note_id, cleaned_note)

        self._load_notes_for_current_chapter()
        self._active_note_id = note_id
        self._annotation_manager.active_note_id = note_id
        self._refresh_note_highlights(active_note_id=note_id, sync_panel=True)

    def _delete_note_from_panel(self, note_id: int) -> None:
        if not self._db_path:
            return
        confirm = QMessageBox.question(
            self,
            "Delete Note",
            "Delete this note?",
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        self._annotation_manager.delete_note(self._db_path, note_id)
        self._load_notes_for_current_chapter()

    def _update_status(self, text: str) -> None:
        chapter_words = self._count_words(text)
        if self._current_chapter_path:
            self._chapter_word_counts[self._current_chapter_path] = chapter_words
        project_words = self._project_word_total()
        today_words = self._words_written_today()
        goal = max(1, int(self._daily_goal))
        streak = self._current_streak()
        chapter_name = ""
        if self._current_chapter_id is not None:
            chapter = next((c for c in self._chapters if c[0] == self._current_chapter_id), None)
            if chapter:
                chapter_name = chapter[1]
        
        # Format: "Chapter 1  ·  2 words  ·  saved just now"
        # With optional: "↑ 847 / 1000" for Exhale, "· 🜂 3d" for streak
        parts = []
        
        if chapter_name:
            parts.append(chapter_name)
        
        parts.append(f"{chapter_words:,} words")
        
        # Exhale progress (if set)
        if self._exhale_target is not None:
            exhale_words = self._current_exhale_words()
            parts.append(f"↑ {exhale_words:,} / {self._exhale_target:,}")
        
        # Streak (only if > 0)
        if streak > 0:
            parts.append(f"🜂 {streak}d")
        
        # Saved status with relative time
        parts.append("saved")
        
        self.status_bar.setText("  ·  ".join(parts))

    def _on_text_changed(self) -> None:
        text = self.editor.toPlainText()
        self._save_draft(text)
        self._update_status(text)
        self._update_echo(text)
        if self._exhale_target is not None:
            self._update_exhale_session()
            self._update_exhale_display()
        self._chapter_notes = self._annotation_manager.chapter_notes
        self._active_note_id = self._annotation_manager.active_note_id
        if self._chapter_notes:
            self._refresh_note_highlights(active_note_id=self._active_note_id)
        if bool(self._editor_settings.get("typewriter_scroll", False)):
            QTimer.singleShot(0, self._center_cursor_vertically)

    def _on_document_contents_change(
        self,
        position: int,
        chars_removed: int,
        chars_added: int,
    ) -> None:
        if self._suspend_note_offset_updates:
            return
        changed = self._annotation_manager.handle_document_change(
            self._db_path,
            self._current_chapter_slug(),
            position,
            chars_removed,
            chars_added,
        )
        self._chapter_notes = self._annotation_manager.chapter_notes
        self._active_note_id = self._annotation_manager.active_note_id
        if changed:
            self._annotation_manager.refresh_highlights(self._active_note_id, sync_panel=True)

    def _center_cursor_vertically(self) -> None:
        viewport_height = self.editor.viewport().height()
        if viewport_height <= 0:
            return
        cursor_rect = self.editor.cursorRect()
        delta = cursor_rect.center().y() - (viewport_height // 2)
        scrollbar = self.editor.verticalScrollBar()
        scrollbar.setValue(scrollbar.value() + delta)

    def eventFilter(self, obj, event) -> bool:
        if obj is self.editor and event.type() in (
            QEvent.Type.KeyPress,
            QEvent.Type.InputMethod,
        ):
            self._on_typing_started()
        return super().eventFilter(obj, event)

    def _on_typing_started(self) -> None:
        self._typing_timer.start(3000)
        if not self._controls_dimmed:
            self._fade_controls(0.1)
            self._controls_dimmed = True

    def _on_typing_stopped(self) -> None:
        self._fade_controls(1.0)
        self._controls_dimmed = False

    def _fade_controls(self, target_opacity: float) -> None:
        self._fade_anims.clear()
        for widget, effect in self._fade_effects.items():
            anim = QPropertyAnimation(effect, b"opacity", self)
            anim.setDuration(1000)
            anim.setStartValue(effect.opacity())
            anim.setEndValue(target_opacity)
            anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
            anim.start()
            self._fade_anims.append(anim)

    def _pulse_cursor(self) -> None:
        self._cursor_wide = not self._cursor_wide
        self.editor.setCursorWidth(3 if self._cursor_wide else 1)

    def _collect_index_entries(self) -> list[dict[str, object]]:
        if not self._project_root or not self._chapters_dir:
            return []
        return self._project_service.build_index_entries(self._chapters_dir, self._project_root)

    def _open_library(self) -> None:
        entries = self._collect_index_entries()
        if not entries:
            QMessageBox.information(self, "Library", "No entries found.")
            return
        dialog = LibraryDialog(entries, self._open_entry_path, self)
        dialog.exec()

    def _generate_character_palette(self) -> None:
        if not self._db_path:
            QMessageBox.information(self, "Palette", "No project database available.")
            return
        default_name = self._detect_character_name(self.editor.toPlainText()) or ""
        name, ok = QInputDialog.getText(
            self,
            "Generate Character Palette",
            "Character name:",
            text=default_name,
        )
        if not ok or not name.strip():
            return
        name = name.strip()

        description, desc_ok = QInputDialog.getMultiLineText(
            self,
            "Character Notes (optional)",
            "Add any description or notes to guide the palette:",
            "",
        )
        if not desc_ok:
            description = ""

        # Status message during palette generation
        self.status_bar.setText(f"Generating palette for {name}...")
        future = self._executor.submit(self._generate_palette_task, name, description)
        future.add_done_callback(
            lambda task: QTimer.singleShot(0, lambda: self._palette_generation_finished(task))
        )

    def _generate_palette_task(self, name: str, description: str):
        if not self._db_path:
            return {"status": "no_db", "name": name}
        profile = load_character_profile(self._db_path, name, entity_type="PERSON")
        if not profile:
            return {"status": "not_found", "name": name}
        if description.strip():
            profile.description = description.strip()
        result = request_design_space_palette(profile, retries=1)
        return {"status": "ok", "profile": profile, "result": result}

    def _palette_generation_finished(self, task) -> None:
        try:
            payload = task.result()
        except Exception as exc:
            QMessageBox.warning(self, "Palette", f"Palette generation failed: {exc}")
            return

        status = payload.get("status")
        if status == "no_db":
            QMessageBox.information(self, "Palette", "No project database available.")
            return
        if status == "not_found":
            QMessageBox.information(
                self,
                "Palette",
                f"Character '{payload.get('name')}' not found in the vault.",
            )
            return

        profile: CharacterProfile = payload["profile"]
        result = payload["result"]
        if not result.ok:
            QMessageBox.warning(
                self,
                "Palette",
                result.error or "Palette generation failed.",
            )
            return
        palette_id, palette_name = self._store_palette_result(profile, result)
        if palette_id is None:
            QMessageBox.warning(self, "Palette", "Failed to store palette in vault.")
            return

        note = ""
        if result.source == "fallback":
            note = f"\nFallback used: {result.error or 'Design Space unavailable.'}"
        colors = ", ".join(result.colors)
        QMessageBox.information(
            self,
            "Palette Saved",
            f"Saved palette '{palette_name}' for {profile.name}.\nColors: {colors}{note}",
        )

    def _store_palette_result(self, profile: CharacterProfile, result):
        if not self._db_path:
            return None, None
        conn = sqlite3.connect(self._db_path)
        try:
            row = conn.execute(
                "SELECT id FROM entities WHERE type = 'PERSON' AND lower(name) = lower(?)",
                (profile.name,),
            ).fetchone()
            if not row:
                return None, None
            entity_id = int(row[0])

            palette_name = result.name or f"{profile.name} Palette"
            palette_name = self._unique_palette_name(conn, palette_name)
            timestamp = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

            cursor = conn.execute(
                """
                INSERT INTO palettes (name, description, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                (palette_name, f"Generated via {result.source}", timestamp, timestamp),
            )
            palette_id = int(cursor.lastrowid)

            for index, color in enumerate(result.colors):
                conn.execute(
                    """
                    INSERT INTO palette_colors (palette_id, hex_code, color_name, position, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (palette_id, color, None, index, timestamp),
                )

            conn.execute(
                """
                INSERT OR IGNORE INTO entity_palettes (entity_id, palette_id, context, notes, assigned_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (entity_id, palette_id, result.source, result.error, timestamp),
            )
            conn.commit()
            return palette_id, palette_name
        finally:
            conn.close()

    def _unique_palette_name(self, conn: sqlite3.Connection, base_name: str) -> str:
        row = conn.execute(
            "SELECT 1 FROM palettes WHERE name = ?",
            (base_name,),
        ).fetchone()
        if not row:
            return base_name
        stamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        candidate = f"{base_name} {stamp}"
        counter = 2
        while conn.execute(
            "SELECT 1 FROM palettes WHERE name = ?",
            (candidate,),
        ).fetchone():
            candidate = f"{base_name} {stamp} ({counter})"
            counter += 1
        return candidate

    def _open_entry_path(self, entry_path: Path) -> None:
        if not self._project_root:
            return
        resolved = entry_path
        if not resolved.is_absolute():
            resolved = (self._project_root / resolved).resolve()
        for chap_id, _, path in self._chapters:
            if path.resolve() == resolved:
                self._select_chapter(chap_id)
                return
        QMessageBox.information(self, "Library", "Chapter not found in this project.")

    def _rebuild_index(self) -> None:
        if not self._project_root:
            return
        entries = self._collect_index_entries()
        output_path = self._project_root / "index.json"
        self._project_service.write_index(entries, output_path)
        QMessageBox.information(
            self,
            "Index Rebuilt",
            f"Saved {len(entries)} entries to {output_path}.",
        )

    def _insert_chapter_record(self, title: str, filename: str) -> int | None:
        if not self._db_path:
            return None
        return self._project_service.insert_chapter_record(self._db_path, title, filename)

    def _ingest_voice_notes(self) -> None:
        if not self._project_root or not self._chapters_dir:
            return
        default_inbox = self._project_root / "inbox" / "voice"
        inbox_dir = default_inbox
        if not inbox_dir.exists():
            selected = QFileDialog.getExistingDirectory(
                self,
                "Select Voice Inbox",
                str(self._project_root),
            )
            if not selected:
                return
            inbox_dir = Path(selected)
        if not inbox_dir.exists():
            QMessageBox.information(self, "Ingest Voice", f"Inbox not found: {inbox_dir}")
            return
        ingested = self._ingest_voice_from(inbox_dir)
        if ingested:
            self._load_chapters()
        if ingested:
            message = f"Ingested {ingested} voice note(s) from {inbox_dir}."
        else:
            message = f"No voice notes found in {inbox_dir}."
        QMessageBox.information(self, "Ingest Voice", message)

    def _ingest_voice_from(self, inbox_dir: Path) -> int:
        if not self._chapters_dir or not self._project_root:
            return 0
        assert self._db_path is not None
        return self._project_service.ingest_voice_from(
            inbox_dir,
            self._chapters_dir,
            self._project_root,
            self._db_path,
            on_move_error=lambda path, exc: QMessageBox.warning(
                self,
                "Ingest Voice",
                f"Could not move {path} to .compost: {exc}",
            ),
        )

    def _export_markdown(self) -> None:
        if not self._project_root:
            return
        default_path = self._project_root / "manuscript.md"
        target, _ = QFileDialog.getSaveFileName(
            self,
            "Export Markdown",
            str(default_path),
            "Markdown Files (*.md)",
        )
        if not target:
            return
        text = self._export_service.build_project_text(self._chapters)
        self._export_service.export_markdown_text(text, Path(target))
        QMessageBox.information(self, "Export Markdown", f"Saved to {target}.")

    def _export_pdf(self) -> None:
        if not self._project_root:
            return
        default_path = self._project_root / "manuscript.pdf"
        target, _ = QFileDialog.getSaveFileName(
            self,
            "Export PDF",
            str(default_path),
            "PDF Files (*.pdf)",
        )
        if not target:
            return
        font_path = None
        use_custom = QMessageBox.question(
            self,
            "Custom Font",
            "Use a custom .ttf font?",
        )
        if use_custom == QMessageBox.StandardButton.Yes:
            selected, _ = QFileDialog.getOpenFileName(
                self,
                "Select Font",
                str(self._project_root),
                "Font Files (*.ttf)",
            )
            if selected:
                font_path = selected
        try:
            self._export_service.export_pdf_text(
                self._export_service.build_project_text(self._chapters),
                Path(target),
                font_path,
            )
        except Exception as exc:
            QMessageBox.warning(self, "Export PDF", f"PDF export failed: {exc}")
            return
        QMessageBox.information(self, "Export PDF", f"Saved to {target}.")

    def _set_exhale(self) -> None:
        """Open the Exhale dialog to set session word count target."""
        if not self._db_path:
            QMessageBox.information(
                self, "Set Exhale", "No project database available."
            )
            return

        # Get last session's target as default
        default_target = self._get_last_exhale_target()
        if default_target is None:
            default_target = 500

        dialog = ExhaleDialog(self, default_value=default_target)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        target = dialog.get_target()
        if target is None or target <= 0:
            return

        # Set the exhale target
        self._exhale_target = target
        self._exhale_completed = False

        # Set session baseline from project totals so Exhale matches the status bar.
        if self._exhale_session_baseline is None:
            self._exhale_session_baseline = self._project_word_total()

        # Save to database
        self._save_exhale_session(target)

        # Update status bar
        self._update_exhale_display()

        QMessageBox.information(
            self,
            "Exhale Set",
            f"Session target: {target:,} words.\nWrite until you reach your exhale.",
        )

    def _get_last_exhale_target(self) -> int | None:
        """Get the target from the last exhale session."""
        if self._methodology_db is None:
            return None
        return self._methodology_db.get_last_exhale_target()

    def _save_exhale_session(self, target: int) -> None:
        """Save or update the current exhale session."""
        if self._methodology_db is None:
            return
        self._methodology_db.save_exhale_session(target, self._current_exhale_words())

    def _update_exhale_session(self) -> None:
        """Update the words_written for the current exhale session."""
        if self._methodology_db is None or self._exhale_target is None:
            return
        if self._exhale_session_baseline is None:
            return
        self._methodology_db.update_exhale_session(self._exhale_target, self._current_exhale_words())

    def _update_exhale_display(self) -> None:
        """Update the status bar with Exhale progress."""
        if self._exhale_target is None or self._exhale_session_baseline is None:
            return

        words_written = self._current_exhale_words()

        if words_written >= self._exhale_target and not self._exhale_completed:
            self._exhale_completed = True

        # The _update_status already handles exhale display via the ↑ notation
        # Just trigger a refresh
        self._update_status(self.editor.toPlainText())

    def _count_total_words(self) -> int:
        """Count total words in the current project text."""
        return self._project_word_total()

    def _current_exhale_words(self) -> int:
        if self._exhale_session_baseline is None:
            return 0
        return max(0, self._project_word_total() - self._exhale_session_baseline)

    def _build_project_text(self) -> str:
        return self._export_service.build_project_text(self._chapters)

    def _trigger_scan(self) -> None:
        if self._scan_inflight:
            return
        if not self._db_path:
            return
        if not self._spacy_available:
            self._set_scan_status("⚠ spaCy unavailable — NLP features disabled")
            return
        text = self._build_project_text()
        if not text.strip():
            return
        self._scan_inflight = True
        self._set_scan_status("⟳ Scanning...")
        future = self._executor.submit(self._nlp_service.scan, text, self._db_path)
        future.add_done_callback(self._on_scan_future_done)

    def _on_scan_future_done(self, task) -> None:
        try:
            task.result()
        except Exception as exc:
            reason = self._brief_scan_error(exc)
            self._scan_finished_signal.emit(False, reason)
            return
        completed_at = self._nlp_service.completed_at()
        self._scan_finished_signal.emit(True, completed_at)

    def _on_scan_future_finished(self, ok: bool, detail: str) -> None:
        self._scan_inflight = False
        if ok:
            self._scan_has_data = self._has_scan_data()
            self._set_scan_status(f"✓ Scan complete ({detail})")
            return
        if "spacy" in detail.casefold() or "en_core_web_sm" in detail.casefold():
            self._spacy_available = False
            self._set_scan_status("⚠ spaCy unavailable — NLP features disabled")
            return
        self._set_scan_status(f"✗ Scan failed: {detail}")

    @staticmethod
    def _brief_scan_error(exc: Exception) -> str:
        message = str(exc).strip() or exc.__class__.__name__
        compact = " ".join(message.split())
        if len(compact) > 96:
            return compact[:93] + "..."
        return compact

    def _detect_character_name(self, text: str) -> str | None:
        tail = text[-80:]
        words = re.findall(r"[A-Za-z][A-Za-z'-]*", tail)
        if not words:
            return None
        for size in (3, 2, 1):
            if len(words) < size:
                continue
            candidate = " ".join(words[-size:])
            if self._character_exists(candidate):
                return candidate
        return None

    def _character_exists(self, name: str) -> bool:
        if not self._db_path:
            return False
        conn = sqlite3.connect(self._db_path)
        try:
            row = conn.execute(
                "SELECT 1 FROM entities WHERE type = 'PERSON' AND lower(name) = lower(?)",
                (name,),
            ).fetchone()
        finally:
            conn.close()
        return row is not None

    def _fetch_traits(self, name: str) -> list[str]:
        if not self._db_path:
            return []
        conn = sqlite3.connect(self._db_path)
        try:
            rows = conn.execute(
                """
                SELECT t.trait
                FROM traits t
                JOIN entities e ON e.id = t.entity_id
                WHERE e.type = 'PERSON' AND lower(e.name) = lower(?)
                ORDER BY t.recorded_at DESC
                LIMIT 3
                """,
                (name,),
            ).fetchall()
        finally:
            conn.close()
        return [row[0] for row in rows]

    def _update_echo(self, text: str) -> None:
        scan_status = self.title_bar.scan_status().casefold()
        if not self._spacy_available or "spacy unavailable" in scan_status:
            self.shell.echo_label.setText("NLP unavailable: spaCy/model missing.")
            self.shell.echo_label.setVisible(True)
            return
        if self._scan_inflight and not self._scan_has_data:
            self.shell.echo_label.setText("NLP scan running...")
            self.shell.echo_label.setVisible(True)
            return
        if not self._scan_has_data:
            self.shell.echo_label.setText("NLP scan not yet run.")
            self.shell.echo_label.setVisible(True)
            return

        name = self._detect_character_name(text)
        if not name:
            self.shell.echo_label.setVisible(False)
            return
        traits = self._fetch_traits(name)
        if traits:
            lines = [name, "Recent traits:"] + [f"- {t}" for t in traits]
        else:
            lines = [name, "Recent traits:", "- None yet"]
        self.shell.echo_label.setText("\n".join(lines))
        self.shell.echo_label.setVisible(True)

    def _toggle_constellation(self) -> None:
        if self._constellation_dock.isVisible():
            self._constellation_dock.hide()
            return
        self._constellation_view.refresh()
        self._constellation_dock.show()
        self._constellation_dock.raise_()

    def _toggle_outliner(self) -> None:
        if self._outliner_dock.isVisible():
            self._outliner_dock.hide()
            return
        self._load_outliner()
        self._outliner_dock.show()
        self._outliner_dock.raise_()

    def _toggle_notes(self) -> None:
        if self._notes_dock.isVisible():
            self._notes_dock.hide()
            return
        self._notes_dock.show()
        self._notes_dock.raise_()

    def _toggle_sparks(self) -> None:
        """Toggle the Sparks panel visibility."""
        if self._sparks_dock.isVisible():
            self._sparks_dock.hide()
            return

        # Lazily create the Sparks panel on first show
        if self._sparks_panel is None and self._project_root and self._methodology_db is not None:
            self._sparks_panel = SparksPanel(
                self._methodology_db,
                self,
            )
            self._sparks_dock.setWidget(self._sparks_panel)

            # Add Sparks panel to fade effects for focus mode
            effect = QGraphicsOpacityEffect(self._sparks_dock)
            effect.setOpacity(1.0)
            self._sparks_dock.setGraphicsEffect(effect)
            self._fade_effects[self._sparks_dock] = effect
            self._fade_targets.append(self._sparks_dock)

        if self._sparks_panel is not None:
            self._sparks_panel.refresh_sparks()
        self._sparks_dock.show()
        self._sparks_dock.raise_()

    def _open_companion_capture(self) -> None:
        """Open the Companion Doc capture bar overlay."""
        if self._companion_capture_bar is None:
            self._companion_capture_bar = CompanionCaptureBar(
                self,
                on_save=self._save_companion_note,
                on_dismiss=self._close_companion_capture,
            )

        self._companion_capture_cursor = QTextCursor(self.editor.textCursor())
        self._companion_capture_bar.show_at_bottom(self.editor)

    def _close_companion_capture(self) -> None:
        """Close the Companion Doc capture bar."""
        if self._companion_capture_bar:
            self._companion_capture_bar.close()
        if self._companion_capture_cursor is not None:
            self.editor.setTextCursor(self._companion_capture_cursor)
            self._companion_capture_cursor = None
        self.editor.setFocus()
        self.editor.ensureCursorVisible()

    def _save_companion_note(self, note_text: str) -> None:
        """Save a companion note to the database."""
        if self._methodology_db is None:
            return

        # Get current chapter context
        chapter_context = None
        if self._current_chapter_path:
            chapter_context = self._current_chapter_path.name

        self._methodology_db.save_companion_note(note_text, chapter_context)

        if (
            self._companion_review_panel is not None
            and self._companion_dock is not None
            and self._companion_dock.isVisible()
        ):
            self._companion_review_panel.refresh_notes()

        self._close_companion_capture()

    def _toggle_companion_review(self) -> None:
        """Toggle the Companion Doc review panel."""
        if self._companion_dock.isVisible():
            self._companion_dock.hide()
            return

        # Lazily create the review panel on first show
        if self._companion_review_panel is None and self._project_root and self._methodology_db is not None:
            compost_dir = self._project_root / ".compost"
            self._companion_review_panel = CompanionReviewPanel(
                self._methodology_db,
                compost_dir,
                self,
            )
            self._companion_dock.setWidget(self._companion_review_panel)

            # Add Companion Doc panel to fade effects for focus mode
            effect = QGraphicsOpacityEffect(self._companion_dock)
            effect.setOpacity(1.0)
            self._companion_dock.setGraphicsEffect(effect)
            self._fade_effects[self._companion_dock] = effect
            self._fade_targets.append(self._companion_dock)

        if self._companion_review_panel is not None:
            self._companion_review_panel.refresh_notes()
        self._companion_dock.show()
        self._companion_dock.raise_()

    def _toggle_focus_mode(self) -> None:
        if not self._focus_mode:
            self._focus_restore_state = {
                "title_bar": self.title_bar.isVisible(),
                "status_bar": self.status_bar.isVisible(),
                "chapters_dock": self._chapters_dock.isVisible(),
                "storylines_dock": self._storylines_dock.isVisible(),
                "outliner_dock": self._outliner_dock.isVisible(),
                "notes_dock": self._notes_dock.isVisible(),
                "constellation_dock": self._constellation_dock.isVisible(),
                "echo_label": self.shell.echo_label.isVisible(),
            }
            self.title_bar.hide()
            self.status_bar.hide()
            self._chapters_dock.hide()
            self._storylines_dock.hide()
            self._outliner_dock.hide()
            self._notes_dock.hide()
            self._constellation_dock.hide()
            self.shell.echo_label.hide()
            self.shell.set_focus_mode(True)
            self._focus_mode = True
            return

        self.shell.set_focus_mode(False)
        if self._focus_restore_state.get("title_bar", True):
            self.title_bar.show()
        if self._focus_restore_state.get("status_bar", True):
            self.status_bar.show()
        if self._focus_restore_state.get("chapters_dock", True):
            self._chapters_dock.show()
        if self._focus_restore_state.get("storylines_dock", True):
            self._storylines_dock.show()
        if self._focus_restore_state.get("outliner_dock", True):
            self._outliner_dock.show()
        if self._focus_restore_state.get("notes_dock", True):
            self._notes_dock.show()
        if self._focus_restore_state.get("constellation_dock", False):
            self._constellation_dock.show()
        if self._focus_restore_state.get("echo_label", False):
            self.shell.echo_label.show()
        for effect in self._fade_effects.values():
            effect.setOpacity(1.0)
        self._controls_dimmed = False
        self._focus_mode = False

    def closeEvent(self, event) -> None:
        self._log_session_writing()
        self._executor.shutdown(wait=False, cancel_futures=True)
        super().closeEvent(event)


def main() -> None:
    app = QApplication([])
    # Apply global dark academia stylesheet before any windows open
    app.setStyleSheet(GLOBAL_STYLESHEET)
    window = HearthWindow()
    window.resize(1120, 720)
    window.show()
    app.exec()


if __name__ == "__main__":
    main()
