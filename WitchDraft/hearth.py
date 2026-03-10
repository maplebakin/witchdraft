from __future__ import annotations

from pathlib import Path
import argparse
import json
import difflib
import importlib.util
import math
import re
import sqlite3
import sys
import threading
from datetime import datetime

from textual.app import App, ComposeResult
from textual.screen import Screen
from textual.widgets import Canvas, Static, TextArea

if importlib.util.find_spec("witchdraft") is None:
    src_dir = Path(__file__).resolve().parent / "src"
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))

from witchdraft.core.io_utils import (
    collect_index_entries as _collect_index_entries,
    created_from_mtime as _shared_created_from_mtime,
    friendly_title as _shared_friendly_title,
    iter_entry_paths as _shared_iter_entry_paths,
    move_to_compost as _shared_move_to_compost,
    parse_created as _shared_parse_created,
    parse_frontmatter as _shared_parse_frontmatter,
    parse_sequence as _shared_parse_sequence,
    slugify as _shared_slugify,
)
from witchdraft.core.scene_utils import (
    PROJECT_TYPE_BOOK as CORE_PROJECT_TYPE_BOOK,
    PROJECT_TYPE_ONE_OFF as CORE_PROJECT_TYPE_ONE_OFF,
    split_scenes as _shared_split_scenes,
)


PROJECT_TYPE_ONE_OFF = "one-off"
PROJECT_TYPE_BOOK = "book"
PROJECT_TYPES = [PROJECT_TYPE_ONE_OFF, PROJECT_TYPE_BOOK]

DRAFT_PATH = Path("current_draft.md")
DB_PATH = Path("vault.db")
COMPOST_PATH = Path("compost.md")
COMPOST_DIR = Path(".compost")
SCAN_INTERVAL_SECONDS = 300
TEXT_COLOR = "#2B2B2B"
BACKGROUND_COLOR = "#E6E5E6"
CURSOR_ACTIVE = "#BCA67A"
CURSOR_DIM = "#DED3BF"
ECHO_PANEL_BACKGROUND = "#F1F0EF"
NODE_COLOR = "#2B2B2B"
SEAM_COLOR = "#8C8B86"

# Dark mode colors
DARK_TEXT_COLOR = "#E6E5E6"
DARK_BACKGROUND_COLOR = "#2B2B2B"
DARK_CURSOR_ACTIVE = "#BCA67A"
DARK_CURSOR_DIM = "#5D5D5D"
DARK_ECHO_PANEL_BACKGROUND = "#3A3A3A"
DARK_NODE_COLOR = "#E6E5E6"
DARK_SEAM_COLOR = "#73726C"


def split_scenes(
    text: str, project_type: str = PROJECT_TYPE_ONE_OFF
) -> list[tuple[str, str]]:
    mapped_type = project_type
    if project_type == PROJECT_TYPE_BOOK:
        mapped_type = CORE_PROJECT_TYPE_BOOK
    elif project_type == PROJECT_TYPE_ONE_OFF:
        mapped_type = CORE_PROJECT_TYPE_ONE_OFF
    return _shared_split_scenes(text, project_type=mapped_type)


def constellation_view(db_path: Path) -> None:
    if not db_path.exists():
        print("vault.db not found.")
        return

    conn = sqlite3.connect(db_path)
    try:
        try:
            scenes = conn.execute(
                "SELECT id, title FROM scenes ORDER BY position"
            ).fetchall()
            if not scenes:
                print("No scenes found in vault.")
                return
            entity_rows = conn.execute(
                "SELECT id, name FROM entities WHERE type IN ('PERSON', 'GPE')"
            ).fetchall()
            if not entity_rows:
                print("No tags in vault.")
                return
            entity_names = {entity_id: name for entity_id, name in entity_rows}
            scene_entities = conn.execute(
                "SELECT scene_id, entity_id FROM scene_entities"
            ).fetchall()
        except sqlite3.OperationalError:
            print("Vault schema incomplete. Run the app to rebuild the Shadow Bible.")
            return
    finally:
        conn.close()

    if not scene_entities:
        print("No scene tags found. Run the Shadow Bible scan first.")
        return

    scene_titles = {scene_id: title for scene_id, title in scenes}
    tag_to_scenes: dict[str, set[str]] = {}

    for scene_id, entity_id in scene_entities:
        name = entity_names.get(entity_id)
        title = scene_titles.get(scene_id)
        if not name or not title:
            continue
        tag_to_scenes.setdefault(name, set()).add(title)

    for tag, titles in sorted(tag_to_scenes.items()):
        print(f"{tag}:")
        for title in sorted(titles):
            print(f"  - {title}")


def export_markdown(source_path: Path, output_path: Path) -> None:
    if not source_path.exists():
        print("current_draft.md not found.")
        return
    text = source_path.read_text(encoding="utf-8")
    cleaned = "\n".join(line.rstrip() for line in text.splitlines())
    if cleaned and not cleaned.endswith("\n"):
        cleaned += "\n"
    output_path.write_text(cleaned, encoding="utf-8")
    print(f"Markdown export saved to {output_path}")


def export_pdf(source_path: Path, output_path: Path, font_path: str | None) -> None:
    if not source_path.exists():
        print("current_draft.md not found.")
        return
    try:
        from reportlab.lib.pagesizes import LETTER
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.pdfgen import canvas
    except Exception:
        print("PDF export requires reportlab. Install with: pip install reportlab")
        return

    text = source_path.read_text(encoding="utf-8").replace("\t", "    ")
    font_name = "Times-Roman"
    font_size = 12
    if font_path:
        font_name = "GrimoireFont"
        try:
            pdfmetrics.registerFont(TTFont(font_name, font_path))
        except Exception as exc:
            print(f"Could not load font: {exc}")
            return

    page_width, page_height = LETTER
    margin = 54
    line_height = font_size + 4
    max_width = page_width - (margin * 2)

    def wrap_line(raw_line: str) -> list[str]:
        if not raw_line:
            return [""]
        words = raw_line.split(" ")
        lines: list[str] = []
        current = ""
        for word in words:
            candidate = f"{current} {word}".strip()
            if pdfmetrics.stringWidth(candidate, font_name, font_size) <= max_width:
                current = candidate
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
        return lines

    pdf = canvas.Canvas(str(output_path), pagesize=LETTER)
    pdf.setFont(font_name, font_size)
    x = margin
    y = page_height - margin

    for raw_line in text.splitlines():
        for line in wrap_line(raw_line):
            if y < margin:
                pdf.showPage()
                pdf.setFont(font_name, font_size)
                y = page_height - margin
            pdf.drawString(x, y, line)
            y -= line_height

    pdf.save()
    print(f"PDF export saved to {output_path}")


def run_export(argv: list[str]) -> None:
    parser = argparse.ArgumentParser(description="Export WitchDraft manuscript.")
    parser.add_argument(
        "--format",
        choices=["markdown", "pdf"],
        default="markdown",
        help="Output format.",
    )
    parser.add_argument("--output", required=True, help="Output file path.")
    parser.add_argument(
        "--font",
        help="Optional path to a .ttf font for PDF export.",
    )
    parser.add_argument(
        "--source",
        default=str(DRAFT_PATH),
        help="Source manuscript path.",
    )
    args = parser.parse_args(argv)

    source_path = Path(args.source)
    output_path = Path(args.output)
    if args.format == "markdown":
        export_markdown(source_path, output_path)
    else:
        export_pdf(source_path, output_path, args.font)


def _parse_created(value: object | None) -> datetime:
    return _shared_parse_created(value)


def _parse_sequence(value: object | None) -> int | None:
    return _shared_parse_sequence(value)


def _hex_to_rgb(value: str) -> tuple[int, int, int] | None:
    hex_value = value.strip().lstrip("#")
    if len(hex_value) != 6:
        return None
    try:
        r = int(hex_value[0:2], 16)
        g = int(hex_value[2:4], 16)
        b = int(hex_value[4:6], 16)
    except ValueError:
        return None
    return r, g, b


def _colorize(text: str, hex_color: str) -> str:
    rgb = _hex_to_rgb(hex_color)
    if not rgb:
        return text
    r, g, b = rgb
    return f"\x1b[38;2;{r};{g};{b}m{text}\x1b[0m"


def _load_palettes(path: Path) -> dict[str, list[str]]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    if not isinstance(data, dict):
        return {}
    palettes: dict[str, list[str]] = {}
    for name, values in data.items():
        if isinstance(name, str) and isinstance(values, list):
            palettes[name] = [str(value) for value in values if isinstance(value, str)]
    return palettes


def _friendly_title(stem: str) -> str:
    return _shared_friendly_title(stem)


def _slugify(text: str) -> str:
    return _shared_slugify(text, fallback="voice-note")


def _first_nonempty_line(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip().lstrip("#").strip()
        if stripped:
            return stripped
    return ""


def _unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    counter = 2
    while True:
        candidate = path.with_name(f"{path.stem}-{counter}{path.suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


def _parse_frontmatter(lines: list[str]) -> dict[str, object]:
    return _shared_parse_frontmatter(lines)


def _created_from_mtime(path: Path) -> str:
    return _shared_created_from_mtime(path)


def _iter_entry_paths(chapters_dir: Path) -> list[Path]:
    return _shared_iter_entry_paths(chapters_dir)


def _build_index(chapters_dir: Path, output_path: Path) -> None:
    entries = _collect_index_entries(chapters_dir, Path.cwd())

    output_path.write_text(
        json.dumps(entries, indent=2, ensure_ascii=True),
        encoding="utf-8",
    )


def _index_needs_rebuild(index_path: Path, chapters_dir: Path) -> bool:
    if not index_path.exists():
        return True
    if not chapters_dir.exists():
        return False
    try:
        index_mtime = index_path.stat().st_mtime
    except OSError:
        return True
    chapter_paths = _iter_entry_paths(chapters_dir)
    if not chapter_paths:
        return False
    latest_mtime = max(path.stat().st_mtime for path in chapter_paths)
    return latest_mtime > index_mtime


def _load_index_entries(index_path: Path, chapters_dir: Path) -> list[dict[str, object]] | None:
    if chapters_dir.exists() and _index_needs_rebuild(index_path, chapters_dir):
        _build_index(chapters_dir, index_path)

    if not index_path.exists():
        return None

    try:
        entries = json.loads(index_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        if chapters_dir.exists():
            _build_index(chapters_dir, index_path)
            try:
                entries = json.loads(index_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                return None
        else:
            return None

    if not isinstance(entries, list):
        return None

    return entries


def _move_to_compost(path: Path, compost_dir: Path) -> Path | None:
    return _shared_move_to_compost(path, compost_dir)


def list_entries(args: argparse.Namespace) -> None:
    index_path = Path("index.json")
    chapters_dir = Path("chapters")
    entries = _load_index_entries(index_path, chapters_dir)
    if entries is None:
        if not chapters_dir.exists():
            print("chapters/ not found. Cannot build index.")
        elif not index_path.exists():
            print("index.json not found and could not be built.")
        else:
            print("index.json could not be loaded.")
        return

    palette_path = Path("palettes") / "designspace.json"
    palettes = _load_palettes(palette_path) if sys.stdout.isatty() else {}

    book_name = getattr(args, "book", None)
    mood_filter = getattr(args, "mood", None)
    theme_filter = getattr(args, "theme", None)
    archetype_filter = getattr(args, "archetype", None)

    for key, value in (
        ("mood", mood_filter),
        ("theme", theme_filter),
        ("archetype", archetype_filter),
    ):
        if value:
            entries = [
                entry
                for entry in entries
                if str(entry.get(key) or "") == value
            ]
    if book_name:
        entries = [entry for entry in entries if entry.get("book") == book_name]
        sequenced = [
            entry
            for entry in entries
            if _parse_sequence(entry.get("sequence")) is not None
        ]
        unsequenced = [
            entry
            for entry in entries
            if _parse_sequence(entry.get("sequence")) is None
        ]
        sequenced.sort(key=lambda entry: _parse_sequence(entry.get("sequence")) or 0)
        unsequenced.sort(
            key=lambda entry: _parse_created(entry.get("created")),
            reverse=True,
        )
        entries = sequenced + unsequenced
    else:
        entries.sort(
            key=lambda entry: _parse_created(entry.get("created")),
            reverse=True,
        )

    if not entries:
        if book_name:
            print(f"No entries found for book: {book_name}")
        else:
            print("No entries found.")
        return

    titles = [str(entry.get("title") or "") for entry in entries]
    moods = [str(entry.get("mood") or "") for entry in entries]
    archetypes = [str(entry.get("archetype") or "") for entry in entries]
    sequences = [_parse_sequence(entry.get("sequence")) for entry in entries]

    title_width = max(len(title) for title in titles) if titles else 0
    mood_width = max(len(mood) for mood in moods) if moods else 0
    archetype_width = max(len(archetype) for archetype in archetypes) if archetypes else 0
    seq_values = [len(str(seq)) for seq in sequences if seq is not None]
    show_sequence = book_name is not None and bool(seq_values)
    seq_width = max(seq_values) if show_sequence else 0

    if book_name:
        print(f"Book: {book_name} ({len(entries)} entries)")
    else:
        print(f"{len(entries)} entries")

    for entry in entries:
        title = str(entry.get("title") or "").strip()
        mood = str(entry.get("mood") or "").strip()
        archetype = str(entry.get("archetype") or "").strip()
        path = str(entry.get("path") or "").strip()
        palette = str(entry.get("palette") or "").strip()

        title_text = title.ljust(title_width)
        if palette and palette in palettes and palettes[palette]:
            title_text = _colorize(title_text, palettes[palette][0])

        line_parts = []
        if show_sequence:
            seq = _parse_sequence(entry.get("sequence"))
            seq_text = str(seq) if seq is not None else ""
            line_parts.append(seq_text.rjust(seq_width))

        line_parts.append(title_text)
        line_parts.append(mood.ljust(mood_width))
        line_parts.append(archetype.ljust(archetype_width))
        line_parts.append(path)

        print("  ".join(part for part in line_parts if part is not None))


def ingest_voice(args: argparse.Namespace) -> None:
    inbox_dir = Path(getattr(args, "inbox", "inbox/voice"))
    chapters_dir = Path(getattr(args, "chapters", "chapters"))
    chapters_dir.mkdir(parents=True, exist_ok=True)

    if not inbox_dir.exists():
        print(f"Inbox not found: {inbox_dir}")
        return

    files = [
        path
        for path in sorted(inbox_dir.iterdir())
        if path.is_file() and path.suffix.lower() in {".txt", ".md"}
    ]

    if not files:
        print(f"No voice notes found in {inbox_dir}")
        return

    ingested = 0
    for path in files:
        raw_text = path.read_text(encoding="utf-8", errors="replace")
        has_frontmatter = raw_text.lstrip().startswith("---")

        if has_frontmatter:
            body = raw_text.rstrip() + "\n"
            destination = _unique_path(chapters_dir / f"{path.stem}.md")
            destination.write_text(body, encoding="utf-8")
        else:
            title = _first_nonempty_line(raw_text)
            if not title:
                title = _friendly_title(path.stem)

            slug = _slugify(title)
            timestamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
            base_id = f"{timestamp}--{slug}"
            entry_id = base_id
            destination = chapters_dir / f"{entry_id}.md"
            counter = 2
            while destination.exists():
                entry_id = f"{base_id}-{counter}"
                destination = chapters_dir / f"{entry_id}.md"
                counter += 1

            created = datetime.now().isoformat(timespec="seconds")
            frontmatter = "\n".join(
                [
                    "---",
                    f"id: {entry_id}",
                    f"title: {title}",
                    f"created: {created}",
                    "mood: \"\"",
                    "archetype: \"\"",
                    "theme: \"\"",
                    "palette: \"\"",
                    "tags: [voice]",
                    "book: \"\"",
                    "sequence:",
                    "---",
                ]
            )
            body_text = raw_text.strip()
            if body_text:
                body = f"{frontmatter}\n\n{body_text}\n"
            else:
                body = f"{frontmatter}\n"
            destination.write_text(body, encoding="utf-8")

        try:
            _move_to_compost(path, COMPOST_DIR)
        except OSError as exc:
            print(f"Could not move {path} to compost: {exc}")
        ingested += 1

    print(f"Ingested {ingested} voice notes into {chapters_dir}")


def parse_cli_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="WitchDraft CLI")
    subparsers = parser.add_subparsers(dest="command")
    list_parser = subparsers.add_parser("list", help="List entries from index.json")
    list_parser.add_argument("--book", help="Filter entries by book name.")
    list_parser.add_argument("--mood", help="Filter entries by mood.")
    list_parser.add_argument("--theme", help="Filter entries by theme.")
    list_parser.add_argument("--archetype", help="Filter entries by archetype.")
    ingest_parser = subparsers.add_parser(
        "ingest-voice",
        help="Ingest voice notes from inbox/voice into chapters/",
    )
    ingest_parser.add_argument(
        "--inbox",
        default="inbox/voice",
        help="Path to the voice inbox (default: inbox/voice).",
    )
    ingest_parser.add_argument(
        "--chapters",
        default="chapters",
        help="Destination chapters directory (default: chapters).",
    )
    args, _ = parser.parse_known_args(argv)
    return args


class SpiralTimeline(Canvas):
    def __init__(self, db_path: Path, **kwargs) -> None:
        super().__init__(**kwargs)
        self._db_path = db_path
        self._nodes: list[dict[str, object]] = []
        self._edges: list[tuple[int, int]] = []
        self._drag_id: int | None = None

    def on_mount(self) -> None:
        self.refresh_graph()

    def refresh_graph(self) -> None:
        self._load_graph()
        self._layout_spiral(force=True)
        self._redraw()

    def _load_graph(self) -> None:
        if not self._db_path.exists():
            self._nodes = []
            self._edges = []
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
                self._nodes = []
                self._edges = []
                return
        finally:
            conn.close()

        scene_entities: dict[int, set[int]] = {}
        for scene_id, title, _ in scenes:
            scene_entities[scene_id] = set()
        for scene_id, entity_id in rows:
            scene_entities.setdefault(scene_id, set()).add(entity_id)

        self._nodes = [
            {
                "id": scene_id,
                "title": title,
                "x": 0,
                "y": 0,
                "manual": False,
            }
            for scene_id, title, _ in scenes
        ]

        self._edges = []
        scene_ids = [node["id"] for node in self._nodes]
        for i, left_id in enumerate(scene_ids):
            left_entities = scene_entities.get(int(left_id), set())
            for right_id in scene_ids[i + 1 :]:
                right_entities = scene_entities.get(int(right_id), set())
                if len(left_entities & right_entities) >= 2:
                    self._edges.append((int(left_id), int(right_id)))

    def _layout_spiral(self, force: bool = False) -> None:
        if not self._nodes:
            return
        width = max(self.size.width, 1)
        height = max(self.size.height, 1)
        center_x = width // 2
        center_y = height // 2
        step = 0.7

        for index, node in enumerate(self._nodes):
            if node["manual"] and not force:
                node["x"] = self._clamp(int(node["x"]), 1, width - 2)
                node["y"] = self._clamp(int(node["y"]), 1, height - 2)
                continue
            t = index * step
            radius = 2 + 1.5 * t
            x = int(center_x + radius * math.cos(t))
            y = int(center_y + radius * math.sin(t))
            node["x"] = self._clamp(x, 1, width - 2)
            node["y"] = self._clamp(y, 1, height - 2)
            node["manual"] = False

    def _redraw(self) -> None:
        self._clear_canvas()
        node_map = {int(node["id"]): node for node in self._nodes}

        for left_id, right_id in self._edges:
            left = node_map.get(left_id)
            right = node_map.get(right_id)
            if not left or not right:
                continue
            self._draw_line(
                int(left["x"]),
                int(left["y"]),
                int(right["x"]),
                int(right["y"]),
                SEAM_COLOR,
            )

        for node in self._nodes:
            x = int(node["x"])
            y = int(node["y"])
            self._draw_node(x, y)
            title = str(node["title"])[:14]
            self._write_text(x + 2, y, title)

        self.refresh()

    def on_resize(self, event) -> None:
        self._layout_spiral(force=False)
        self._redraw()

    def on_mouse_down(self, event) -> None:
        node = self._find_node(event.x, event.y)
        if node:
            self._drag_id = int(node["id"])
            node["manual"] = True
            self.capture_mouse()

    def on_mouse_move(self, event) -> None:
        if self._drag_id is None:
            return
        node = self._node_by_id(self._drag_id)
        if not node:
            return
        width = max(self.size.width, 1)
        height = max(self.size.height, 1)
        node["x"] = self._clamp(event.x, 1, width - 2)
        node["y"] = self._clamp(event.y, 1, height - 2)
        self._redraw()

    def on_mouse_up(self, event) -> None:
        if self._drag_id is not None:
            self.release_mouse()
            self._drag_id = None

    def _find_node(self, x: int, y: int) -> dict[str, object] | None:
        for node in self._nodes:
            node_x = int(node["x"])
            node_y = int(node["y"])
            if abs(node_x - x) <= 1 and abs(node_y - y) <= 1:
                return node
        return None

    def _node_by_id(self, node_id: int) -> dict[str, object] | None:
        for node in self._nodes:
            if int(node["id"]) == node_id:
                return node
        return None

    def _clear_canvas(self) -> None:
        if hasattr(self, "reset"):
            self.reset()
            return
        if hasattr(self, "clear"):
            self.clear()

    def _draw_node(self, x: int, y: int) -> None:
        draw_circle = getattr(self, "draw_circle", None)
        if draw_circle is not None:
            draw_circle(x, y, 1, color=NODE_COLOR)
            return
        set_pixel = getattr(self, "set_pixel", None)
        if set_pixel is not None:
            set_pixel(x, y, NODE_COLOR)

    def _draw_line(self, x1: int, y1: int, x2: int, y2: int, color: str) -> None:
        draw_line = getattr(self, "draw_line", None)
        if draw_line is not None:
            draw_line(x1, y1, x2, y2, color=color)
            return
        set_pixel = getattr(self, "set_pixel", None)
        if set_pixel is None:
            return
        for x, y in self._line_points(x1, y1, x2, y2):
            set_pixel(x, y, color)

    def _write_text(self, x: int, y: int, text: str) -> None:
        write_text = getattr(self, "write_text", None)
        if write_text is not None:
            write_text(x, y, text, color=TEXT_COLOR)

    @staticmethod
    def _line_points(x1: int, y1: int, x2: int, y2: int) -> list[tuple[int, int]]:
        points: list[tuple[int, int]] = []
        dx = abs(x2 - x1)
        dy = abs(y2 - y1)
        x, y = x1, y1
        sx = 1 if x1 < x2 else -1
        sy = 1 if y1 < y2 else -1
        if dx > dy:
            err = dx / 2.0
            while x != x2:
                points.append((x, y))
                err -= dy
                if err < 0:
                    y += sy
                    err += dx
                x += sx
        else:
            err = dy / 2.0
            while y != y2:
                points.append((x, y))
                err -= dx
                if err < 0:
                    x += sx
                    err += dy
                y += sy
        points.append((x2, y2))
        return points

    @staticmethod
    def _clamp(value: int, minimum: int, maximum: int) -> int:
        return max(minimum, min(maximum, value))


class SpiralTimelineScreen(Screen):
    CSS = f"""
    Screen {{
        background: {BACKGROUND_COLOR};
        color: {TEXT_COLOR};
    }}

    #timeline {{
        background: {BACKGROUND_COLOR};
    }}

    #timeline-help {{
        height: 3;
        padding: 1 2;
        color: {TEXT_COLOR};
    }}
    """

    BINDINGS = [("escape", "close", "Back"), ("r", "refresh", "Refresh")]

    def compose(self) -> ComposeResult:
        yield Static("Spiral Timeline - drag nodes to rearrange scenes.", id="timeline-help")
        yield SpiralTimeline(DB_PATH, id="timeline")

    def action_close(self) -> None:
        self.app.pop_screen()

    def action_refresh(self) -> None:
        self.query_one(SpiralTimeline).refresh_graph()


class HearthApp(App):
    BINDINGS = [
        ("ctrl+t", "thesaurus", "Thesaurus"),
        ("ctrl+g", "toggle_timeline", "Timeline"),
        ("ctrl+p", "switch_project_type", "Toggle Project Type"),
        ("ctrl+m", "toggle_minimal_ui", "Minimal UI"),
        ("ctrl+d", "toggle_dark_mode", "Dark Mode"),      # ADD THIS LINE
        ("f11", "toggle_fullscreen", "Full Screen"),      # ADD THIS LINE
    ]

    CSS = f"""
    App {{
        background: {BACKGROUND_COLOR};
        color: {TEXT_COLOR};
    }}

    .dark-mode App {{
        background: {DARK_BACKGROUND_COLOR};
        color: {DARK_TEXT_COLOR};
    }}

    #hearth {{
        background: {BACKGROUND_COLOR};
        color: {TEXT_COLOR};
        border: round #B7B6B2;
        padding: 1 2;
        min-width: 80%;  /* Take majority of horizontal space */
        height: 1fr;     /* Take available vertical space */
    }}

    .dark-mode #hearth {{
        background: {DARK_BACKGROUND_COLOR};
        color: {DARK_TEXT_COLOR};
        border: round #5D5D5D;
    }}

    #echo-panel {{
        background: {ECHO_PANEL_BACKGROUND};
        color: {TEXT_COLOR};
        border: round #B7B6B2;
        dock: right;
        width: 24;       /* Reduce width from 34 to 24 */
        height: 7;
        padding: 1 2;
        display: none;
    }}

    .dark-mode #echo-panel {{
        background: {DARK_ECHO_PANEL_BACKGROUND};
        color: {DARK_TEXT_COLOR};
        border: round #5D5D5D;
    }}

    #ghost-line {{
        background: {BACKGROUND_COLOR};
        color: {CURSOR_DIM};
        dock: bottom;
        height: 1;
        padding: 0 2;
        display: none;
    }}

    .dark-mode #ghost-line {{
        background: {DARK_BACKGROUND_COLOR};
        color: {DARK_CURSOR_DIM};
    }}

    #status-line {{
        background: {BACKGROUND_COLOR};
        color: {TEXT_COLOR};
        dock: top;
        height: 1;
        padding: 0 2;
    }}

    .dark-mode #status-line {{
        background: {DARK_BACKGROUND_COLOR};
        color: {DARK_TEXT_COLOR};
    }}

    .focus-mode #hearth {{
        border: none;
        min-width: 90%;  /* Even more space in focus mode */
    }}

    .dark-mode.focus-mode #hearth {{
        border: none;
    }}

    .focus-mode #echo-panel {{
        border: none;
    }}

    .dark-mode.focus-mode #echo-panel {{
        border: none;
    }}

    .echo-visible #echo-panel {{
        display: block;
    }}

    .ghost-visible #ghost-line {{
        display: block;
    }}

    /* Add a toggle mode for minimal UI */
    .minimal-mode #hearth {{
        min-width: 100%;
        border: none;
        padding: 0;
    }}

    .dark-mode.minimal-mode #hearth {{
        min-width: 100%;
        border: none;
        padding: 0;
    }}

    .minimal-mode #echo-panel {{
        display: none;
    }}

    .minimal-mode #status-line {{
        display: none;
    }}

    /* Full-screen mode */
    .fullscreen {{
        padding: 0;
        margin: 0;
        width: 100%;
        height: 100%;
    }}

    .fullscreen #hearth {{
        min-width: 100%;
        min-height: 100%;
        border: none;
        padding: 0;
    }}

    .dark-mode.fullscreen #hearth {{
        min-width: 100%;
        min-height: 100%;
        border: none;
        padding: 0;
    }}
    """

    def __init__(self) -> None:
        super().__init__()
        self._focus_mode = False
        self._ignore_changes = False
        self._cursor_on = True
        self._nlp = None
        self._db: sqlite3.Connection | None = None
        self._db_lock = threading.Lock()
        self._echo_visible = False
        self._echo_text = ""
        self._ghost_visible = False
        self._last_text = ""
        self._scan_stop = threading.Event()
        self._scan_thread: threading.Thread | None = None
        self.project_type = PROJECT_TYPE_ONE_OFF
        self._dark_mode = False  # Track dark mode state
        self._fullscreen = False  # Track fullscreen state

    def compose(self) -> ComposeResult:
        yield Static(id="status-line")
        yield TextArea(id="hearth")
        yield Static(id="echo-panel")
        yield Static(id="ghost-line")

    def on_mount(self) -> None:
        self._text_area = self.query_one(TextArea)
        self._echo_panel = self.query_one("#echo-panel", Static)
        self._ghost_line = self.query_one("#ghost-line", Static)
        self._status_line = self.query_one("#status-line", Static)
        self._load_existing_draft()
        self._init_vault()
        self._init_spacy()
        self._text_area.focus()
        self.set_interval(1.4, self._pulse_cursor)
        self.set_interval(SCAN_INTERVAL_SECONDS, self._run_shadow_bible)
        self.update_ui_for_project_type()
        self._run_shadow_bible()
        self._start_spacy_scan_thread()

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        if self._ignore_changes:
            return
        self._hide_ghost_line()
        if not self._focus_mode:
            self._focus_mode = True
            self.add_class("focus-mode")
        self._capture_large_deletion(self._last_text, event.text_area.text)
        self._save_draft(event.text_area.text)
        self._capture_deletions(event.text_area.text)
        self._last_text = event.text_area.text
        self._update_echo_panel(event.text_area.text)

    def _load_existing_draft(self) -> None:
        if not DRAFT_PATH.exists():
            return
        self._ignore_changes = True
        self._text_area.text = DRAFT_PATH.read_text(encoding="utf-8")
        self._last_text = self._text_area.text
        self._ignore_changes = False

    def _save_draft(self, text: str) -> None:
        DRAFT_PATH.write_text(text, encoding="utf-8")

    def _capture_deletions(self, new_text: str) -> None:
        if not self._last_text:
            return
        old_words = self._split_words(self._last_text)
        new_words = self._split_words(new_text)
        if len(new_words) >= len(old_words):
            return

        deleted_words: list[str] = []
        matcher = difflib.SequenceMatcher(a=old_words, b=new_words)
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag in {"delete", "replace"}:
                deleted_words.extend(old_words[i1:i2])

        if len(deleted_words) < 5:
            return

        self._append_compost(" ".join(deleted_words))

    def _append_compost(self, deleted_text: str) -> None:
        timestamp = self._timestamp()
        entry = f"[{timestamp}]\n{deleted_text}\n\n"
        COMPOST_PATH.write_text(
            COMPOST_PATH.read_text(encoding="utf-8") + entry
            if COMPOST_PATH.exists()
            else entry,
            encoding="utf-8",
        )

    def _capture_large_deletion(self, old_text: str, new_text: str) -> None:
        if not old_text:
            return
        if len(new_text) >= len(old_text):
            return
        if (len(old_text) - len(new_text)) <= 25:
            return

        deleted_chunks: list[str] = []
        matcher = difflib.SequenceMatcher(a=old_text, b=new_text)
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag in {"delete", "replace"}:
                deleted_chunks.append(old_text[i1:i2])

        deleted_text = "".join(deleted_chunks).strip()
        if not deleted_text:
            return
        self._write_compost_file(deleted_text)

    def _write_compost_file(self, deleted_text: str) -> None:
        COMPOST_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        path = COMPOST_DIR / f"{timestamp}.md"
        counter = 1
        while path.exists():
            path = COMPOST_DIR / f"{timestamp}_{counter}.md"
            counter += 1
        path.write_text(deleted_text + "\n", encoding="utf-8")

    @staticmethod
    def _split_words(text: str) -> list[str]:
        return re.findall(r"[A-Za-z0-9']+", text)

    def _init_vault(self) -> None:
        self._db = sqlite3.connect(DB_PATH)
        self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS entities (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                type TEXT NOT NULL,
                last_seen TEXT NOT NULL,
                UNIQUE(name, type)
            )
            """
        )
        self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS scenes (
                id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                position INTEGER NOT NULL UNIQUE,
                updated_at TEXT NOT NULL
            )
            """
        )
        self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS scene_entities (
                scene_id INTEGER NOT NULL,
                entity_id INTEGER NOT NULL,
                count INTEGER NOT NULL,
                PRIMARY KEY (scene_id, entity_id),
                FOREIGN KEY(scene_id) REFERENCES scenes(id),
                FOREIGN KEY(entity_id) REFERENCES entities(id)
            )
            """
        )
        self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS traits (
                id INTEGER PRIMARY KEY,
                entity_id INTEGER NOT NULL,
                trait TEXT NOT NULL,
                recorded_at TEXT NOT NULL,
                FOREIGN KEY(entity_id) REFERENCES entities(id)
            )
            """
        )
        self._db.commit()

    def _init_spacy(self) -> None:
        try:
            import spacy
        except Exception:
            self._nlp = None
            return
        try:
            self._nlp = spacy.load("en_core_web_sm")
        except Exception:
            self._nlp = None

    def _run_shadow_bible(self) -> None:
        if self._nlp is None or self._db is None:
            return
        if not DRAFT_PATH.exists():
            return
        text = DRAFT_PATH.read_text(encoding="utf-8")
        if not text.strip():
            return
        timestamp = self._timestamp()

        scenes = split_scenes(text, project_type=self.project_type)
        if not scenes:
            return

        with self._db_lock:
            self._db.execute("DELETE FROM scene_entities")
            self._db.execute("DELETE FROM scenes")

        for position, (title, body) in enumerate(scenes, start=1):
            scene_id = self._insert_scene(title, position, timestamp)
            if not body.strip():
                continue
            doc = self._nlp(body)
            counts: dict[int, int] = {}
            for ent in doc.ents:
                if ent.label_ not in {"PERSON", "GPE"}:
                    continue
                name = ent.text.strip()
                if not name:
                    continue
                entity_id = self._upsert_entity(name, ent.label_, timestamp)
                counts[entity_id] = counts.get(entity_id, 0) + 1
                if ent.label_ == "PERSON":
                    for trait in self._extract_traits(ent):
                        self._insert_trait(entity_id, trait, timestamp)

            for entity_id, count in counts.items():
                with self._db_lock:
                    self._db.execute(
                        """
                        INSERT INTO scene_entities (scene_id, entity_id, count)
                        VALUES (?, ?, ?)
                        """,
                        (scene_id, entity_id, count),
                    )

        with self._db_lock:
            self._db.commit()

    def _upsert_entity(self, name: str, entity_type: str, timestamp: str) -> int:
        if self._db is None:
            raise RuntimeError("Vault DB is not initialized.")
        with self._db_lock:
            self._db.execute(
                """
                INSERT INTO entities (name, type, last_seen)
                VALUES (?, ?, ?)
                ON CONFLICT(name, type) DO UPDATE SET last_seen=excluded.last_seen
                """,
                (name, entity_type, timestamp),
            )
            row = self._db.execute(
                "SELECT id FROM entities WHERE name = ? AND type = ?",
                (name, entity_type),
            ).fetchone()
        return int(row[0])

    def _insert_trait(self, entity_id: int, trait: str, timestamp: str) -> None:
        if self._db is None:
            return
        if not trait:
            return
        with self._db_lock:
            self._db.execute(
                "INSERT INTO traits (entity_id, trait, recorded_at) VALUES (?, ?, ?)",
                (entity_id, trait, timestamp),
            )

    def _insert_scene(self, title: str, position: int, timestamp: str) -> int:
        if self._db is None:
            raise RuntimeError("Vault DB is not initialized.")
        with self._db_lock:
            cursor = self._db.execute(
                """
                INSERT INTO scenes (title, position, updated_at)
                VALUES (?, ?, ?)
                """,
                (title, position, timestamp),
            )
        return int(cursor.lastrowid)

    def _extract_traits(self, ent) -> list[str]:
        traits: set[str] = set()
        root = ent.root

        for child in root.children:
            if child.pos_ == "ADJ":
                traits.add(child.lemma_.lower())

        if root.head.pos_ in {"AUX", "VERB"}:
            for child in root.head.children:
                if child.pos_ == "ADJ":
                    traits.add(child.lemma_.lower())

        window_start = max(ent.start - 3, 0)
        for token in ent.doc[window_start:ent.start]:
            if token.pos_ == "ADJ":
                traits.add(token.lemma_.lower())

        return sorted(traits)

    def _update_echo_panel(self, text: str) -> None:
        name = self._detect_character_name(text)
        if not name:
            self._hide_echo_panel()
            return
        traits = self._fetch_traits(name)
        self._show_echo_panel(name, traits)

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
        if self._db is None:
            return False
        row = self._db.execute(
            "SELECT 1 FROM entities WHERE type = 'PERSON' AND lower(name) = lower(?)",
            (name,),
        ).fetchone()
        return row is not None

    def _fetch_traits(self, name: str) -> list[str]:
        if self._db is None:
            return []
        rows = self._db.execute(
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
        return [row[0] for row in rows]

    def _show_echo_panel(self, name: str, traits: list[str]) -> None:
        if traits:
            lines = [f"{name}", "Recent traits:"]
            lines.extend(f"- {trait}" for trait in traits)
        else:
            lines = [f"{name}", "Recent traits:", "- None yet"]
        self._echo_text = "\n".join(lines)
        self._echo_panel.update(self._echo_text)
        if not self._echo_visible:
            self.add_class("echo-visible")
            self._echo_visible = True

    def _hide_echo_panel(self) -> None:
        if self._echo_visible:
            self.remove_class("echo-visible")
            self._echo_visible = False
        self._echo_text = ""

    @staticmethod
    def _timestamp() -> str:
        return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

    def _pulse_cursor(self) -> None:
        self._cursor_on = not self._cursor_on
        cursor_color = CURSOR_ACTIVE if self._cursor_on else CURSOR_DIM
        self._text_area.cursor_style = f"bold {TEXT_COLOR} on {cursor_color}"

    def _start_spacy_scan_thread(self) -> None:
        if self._scan_thread and self._scan_thread.is_alive():
            return
        self._scan_stop.clear()
        self._scan_thread = threading.Thread(
            target=self._run_spacy_scan,
            name="spacy-scan",
            daemon=True,
        )
        self._scan_thread.start()

    def _run_spacy_scan(self) -> None:
        try:
            import spacy
        except Exception:
            return

        try:
            nlp = spacy.load("en_core_web_sm")
        except Exception:
            return

        conn = sqlite3.connect(DB_PATH, timeout=5)
        try:
            while not self._scan_stop.is_set():
                self._scan_once(nlp, conn)
                self._scan_stop.wait(SCAN_INTERVAL_SECONDS)
        finally:
            conn.close()

    def _scan_once(self, nlp, conn: sqlite3.Connection) -> None:
        if not DRAFT_PATH.exists():
            return
        text = DRAFT_PATH.read_text(encoding="utf-8")
        if not text.strip():
            return
        doc = nlp(text)
        timestamp = self._timestamp()

        with self._db_lock:
            for ent in doc.ents:
                if ent.label_ not in {"PERSON", "GPE"}:
                    continue
                name = ent.text.strip()
                if not name:
                    continue
                conn.execute(
                    """
                    INSERT INTO entities (name, type, last_seen)
                    VALUES (?, ?, ?)
                    ON CONFLICT(name, type) DO UPDATE SET last_seen=excluded.last_seen
                    """,
                    (name, ent.label_, timestamp),
                )
                row = conn.execute(
                    "SELECT id FROM entities WHERE name = ? AND type = ?",
                    (name, ent.label_),
                ).fetchone()
                if not row:
                    continue
                entity_id = int(row[0])
                if ent.label_ == "PERSON":
                    for trait in self._extract_surrounding_traits(ent):
                        conn.execute(
                            "INSERT INTO traits (entity_id, trait, recorded_at) VALUES (?, ?, ?)",
                            (entity_id, trait, timestamp),
                        )
            conn.commit()

    def _extract_surrounding_traits(self, ent) -> list[str]:
        doc = ent.doc
        traits: set[str] = set()
        for index in (ent.start - 1, ent.end):
            if 0 <= index < len(doc):
                token = doc[index]
                if token.pos_ == "ADJ":
                    traits.add(token.lemma_.lower())
        return sorted(traits)

    def _internal_thesaurus(self) -> str | None:
        word = self._word_under_cursor()
        if not word:
            return None
        try:
            import synnamon
        except Exception:
            return None

        try:
            synonyms = synnamon.synonyms(word)
        except Exception:
            return None
        if not synonyms:
            return None

        cleaned = [syn.strip() for syn in synonyms if syn and syn.strip()]
        if not cleaned:
            return None
        return f"{word}: [{', '.join(cleaned)}]"

    def _word_under_cursor(self) -> str | None:
        cursor = getattr(self._text_area, "cursor_location", None)
        if not cursor:
            return None
        row, col = cursor
        lines = self._text_area.text.splitlines()
        if row < 0 or row >= len(lines):
            return None
        line = lines[row]
        if not line:
            return None
        col = max(0, min(col, len(line)))

        left = line.rfind(" ", 0, col)
        right = line.find(" ", col)
        if left == -1:
            left = 0
        else:
            left += 1
        if right == -1:
            right = len(line)

        word = line[left:right].strip(".,:;!?()[]{}\"'")
        return word or None

    def _get_word_at_cursor(self) -> str:
        cursor = getattr(self._text_area, "cursor_location", None)
        if not cursor:
            return ""
        row, col = cursor
        line = self._text_area.get_line(row)
        if not line:
            return ""
        for match in re.finditer(r"\w+", line):
            if match.start() <= col < match.end():
                return match.group(0)
        return ""

    def _show_ghost_line(self, line: str) -> None:
        if not line:
            return
        self._ghost_line.update(line)
        if not self._ghost_visible:
            self.add_class("ghost-visible")
            self._ghost_visible = True

    def _hide_ghost_line(self) -> None:
        if self._ghost_visible:
            self.remove_class("ghost-visible")
            self._ghost_visible = False
        self._ghost_line.update("")

    def switch_project_type(self, new_type: str) -> None:
        if new_type in PROJECT_TYPES:
            self.project_type = new_type
            self.update_ui_for_project_type()

    def update_ui_for_project_type(self) -> None:
        """Update the UI based on the current project type."""
        status_text = f"Project Type: {self.project_type.replace('-', ' ').title()}"
        status_line = getattr(self, "_status_line", None)
        if status_line is not None:
            status_line.update(status_text)
            
        # Adjust UI based on project type
        if self.project_type == PROJECT_TYPE_BOOK:
            # For book projects, maybe we want to make the echo panel more prominent
            # when it's visible, or provide different UI cues
            pass
        else:
            # For one-off projects, keep default behavior
            pass

    def action_toggle_minimal_ui(self) -> None:
        """Toggle minimal UI mode for maximum writing space."""
        if "minimal-mode" in self.classes:
            self.remove_class("minimal-mode")
            self.notify("Normal UI mode")
        else:
            self.add_class("minimal-mode")
            self.notify("Minimal UI mode - Maximum writing space")

    def toggle_echo_panel(self) -> None:
        """Toggle visibility of the echo panel."""
        if self._echo_visible:
            self.remove_class("echo-visible")
            self._echo_visible = False
            self._echo_text = ""
            if hasattr(self, '_echo_panel'):
                self._echo_panel.update("")
        else:
            # Only show if there's content to show
            if self._echo_text:
                self.add_class("echo-visible")
                self._echo_visible = True

    def action_toggle_dark_mode(self) -> None:
        """Toggle dark/light mode."""
        if self._dark_mode:
            self.remove_class("dark-mode")
            self._dark_mode = False
            self.notify("Light mode activated")
        else:
            self.add_class("dark-mode")
            self._dark_mode = True
            self.notify("Dark mode activated")

    def action_toggle_fullscreen(self) -> None:
        """Toggle full-screen mode."""
        if self._fullscreen:
            self.remove_class("fullscreen")
            self._fullscreen = False
            self.notify("Exited full-screen")
        else:
            self.add_class("fullscreen")
            self._fullscreen = True
            self.notify("Full-screen mode")

    def action_switch_project_type(self) -> None:
        current_idx = PROJECT_TYPES.index(self.project_type)
        next_idx = (current_idx + 1) % len(PROJECT_TYPES)
        new_type = PROJECT_TYPES[next_idx]

        self.switch_project_type(new_type)
        self.notify(f"Switched to {new_type.replace('-', ' ')} mode")

    def action_thesaurus(self) -> None:
        word = self._get_word_at_cursor()
        if not word:
            self._show_ghost_line("No word at cursor.")
            return
        try:
            import nltk
            from nltk.corpus import wordnet
        except Exception:
            self._show_ghost_line("nltk.wordnet not available.")
            return

        try:
            synsets = wordnet.synsets(word)
        except LookupError:
            try:
                nltk.download("wordnet", quiet=True)
                nltk.download("omw-1.4", quiet=True)
                synsets = wordnet.synsets(word)
            except Exception:
                self._show_ghost_line("WordNet download failed.")
                return
        except Exception:
            self._show_ghost_line("WordNet lookup failed.")
            return

        synonyms: list[str] = []
        for synset in synsets:
            for lemma in synset.lemmas():
                name = lemma.name().replace("_", " ")
                if name not in synonyms:
                    synonyms.append(name)

        if not synonyms:
            self._show_ghost_line("No synonyms found.")
            return

        self._show_ghost_line(f"{word}: [{', '.join(synonyms)}]")

    def action_toggle_timeline(self) -> None:
        if isinstance(self.screen, SpiralTimelineScreen):
            self.pop_screen()
        else:
            self.push_screen(SpiralTimelineScreen())

    def on_unmount(self) -> None:
        self._scan_stop.set()
        if self._scan_thread and self._scan_thread.is_alive():
            self._scan_thread.join(timeout=2)
        if self._db is not None:
            self._db.close()


if __name__ == "__main__":
    print("WitchDraft CLI/TUI has been disabled. Use the GUI via `witchdraft`.")
    sys.exit(1)
