from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path

from witchdraft.core.io_utils import (
    collect_index_entries,
    created_from_mtime,
    friendly_title,
    iter_entry_paths,
    move_to_compost,
    parse_created,
    parse_frontmatter,
    parse_sequence,
    slugify,
)
from witchdraft.db.schema import ensure_default_chapter, ensure_vault_schema, utc_timestamp


PROJECT_META = "project.json"
CHAPTERS_DIRNAME = "chapters"


def project_meta_path(root: Path) -> Path:
    return root / PROJECT_META


def local_timestamp() -> str:
    return datetime.now().astimezone().replace(microsecond=0).isoformat()


class ProjectService:
    def __init__(self, default_editor_settings: dict[str, object], default_daily_goal: int) -> None:
        self._default_editor_settings = dict(default_editor_settings)
        self._default_daily_goal = int(default_daily_goal)

    def normalize_editor_settings(self, value: object | None, line_height_percent: dict[str, int]) -> dict[str, object]:
        settings = dict(self._default_editor_settings)
        if not isinstance(value, dict):
            return settings

        font_family = value.get("font_family")
        if isinstance(font_family, str) and font_family.strip():
            settings["font_family"] = font_family.strip()

        font_size = value.get("font_size")
        try:
            size_value = int(font_size)
        except (TypeError, ValueError):
            size_value = int(self._default_editor_settings["font_size"])
        settings["font_size"] = max(12, min(24, size_value))

        line_height = value.get("line_height")
        if isinstance(line_height, str) and line_height in line_height_percent:
            settings["line_height"] = line_height

        settings["typewriter_scroll"] = bool(value.get("typewriter_scroll"))
        return settings

    def load_project_meta(self, root: Path) -> dict:
        path = project_meta_path(root)
        if not path.exists():
            return {"name": root.name, "created_at": "", "project_id": ""}
        return json.loads(path.read_text(encoding="utf-8"))

    def save_project_meta(
        self,
        root: Path,
        name: str,
        *,
        editor_settings: dict[str, object] | None = None,
        daily_goal: int | None = None,
        line_height_percent: dict[str, int],
    ) -> dict[str, object]:
        path = project_meta_path(root)
        existing: dict[str, object] = {}
        if path.exists():
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    existing = raw
            except (json.JSONDecodeError, OSError):
                existing = {}

        created_at = existing.get("created_at")
        if not isinstance(created_at, str) or not created_at:
            created_at = local_timestamp()
        project_id = existing.get("project_id")
        if not isinstance(project_id, str) or not project_id:
            project_id = str(uuid.uuid4())

        data: dict[str, object] = {
            "name": name,
            "created_at": created_at,
            "project_id": project_id,
        }
        if editor_settings is not None:
            data["editor_settings"] = self.normalize_editor_settings(editor_settings, line_height_percent)
        elif isinstance(existing.get("editor_settings"), dict):
            data["editor_settings"] = self.normalize_editor_settings(existing["editor_settings"], line_height_percent)

        goal_value = daily_goal
        if goal_value is None:
            existing_goal = existing.get("daily_goal")
            try:
                goal_value = int(existing_goal)
            except (TypeError, ValueError):
                goal_value = self._default_daily_goal
        data["daily_goal"] = max(1, int(goal_value))
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return data

    def ensure_chapters_dir(self, root: Path) -> Path:
        chapters_dir = root / CHAPTERS_DIRNAME
        chapters_dir.mkdir(parents=True, exist_ok=True)
        return chapters_dir

    def list_projects(self, root: Path) -> list[Path]:
        if not root.exists():
            return []
        return sorted(
            [path for path in root.iterdir() if project_meta_path(path).exists()],
            key=lambda p: p.name.lower(),
        )

    def create_project(self, root: Path, name: str, *, line_height_percent: dict[str, int]) -> Path:
        root.mkdir(parents=True, exist_ok=True)
        self.save_project_meta(root, name, line_height_percent=line_height_percent)
        chapters_dir = self.ensure_chapters_dir(root)
        conn = sqlite3.connect(root / "vault.db")
        try:
            ensure_vault_schema(conn)
            ensure_default_chapter(conn, chapters_dir)
        finally:
            conn.close()
        return root

    def ensure_project_id(self, root: Path, *, line_height_percent: dict[str, int]) -> dict:
        meta = self.load_project_meta(root)
        if not str(meta.get("project_id") or "").strip():
            meta = self.save_project_meta(
                root,
                str(meta.get("name") or root.name),
                line_height_percent=line_height_percent,
            )
        return meta

    def load_draft(self, chapter_path: Path | None) -> str:
        if not chapter_path or not chapter_path.exists():
            return ""
        return chapter_path.read_text(encoding="utf-8")

    def save_draft(self, chapter_path: Path | None, text: str) -> None:
        if chapter_path is None:
            return
        chapter_path.write_text(text, encoding="utf-8")

    def load_chapters(self, db_path: Path, chapters_dir: Path, count_words) -> tuple[list[tuple[int, str, Path]], dict[Path, int]]:
        conn = sqlite3.connect(db_path)
        try:
            rows = conn.execute("SELECT id, title, filename FROM chapters ORDER BY position").fetchall()
        finally:
            conn.close()

        chapters: list[tuple[int, str, Path]] = []
        word_counts: dict[Path, int] = {}
        for chapter_id, title, filename in rows:
            path = chapters_dir / filename
            chapters.append((int(chapter_id), str(title), path))
            if path.exists():
                word_counts[path] = count_words(path.read_text(encoding="utf-8", errors="replace"))
            else:
                word_counts[path] = 0
        return chapters, word_counts

    def create_chapter(self, db_path: Path, chapters_dir: Path, title: str) -> int:
        slug = slugify(title, fallback="chapter")
        filename = f"{slug}.md"
        path = chapters_dir / filename
        counter = 1
        while path.exists():
            filename = f"{slug}-{counter}.md"
            path = chapters_dir / filename
            counter += 1
        path.write_text(f"# {title}\n\n", encoding="utf-8")

        conn = sqlite3.connect(db_path)
        try:
            row = conn.execute("SELECT MAX(position) FROM chapters").fetchone()
            position = (row[0] or 0) + 1
            cursor = conn.execute(
                """
                INSERT INTO chapters (title, filename, position, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                (title, filename, position, utc_timestamp()),
            )
            conn.commit()
            return int(cursor.lastrowid)
        finally:
            conn.close()

    def delete_chapter(self, db_path: Path, project_root: Path, chapter_id: int, chapter_path: Path) -> None:
        if chapter_path.exists():
            move_to_compost(chapter_path, project_root / ".compost")
        conn = sqlite3.connect(db_path)
        try:
            conn.execute("DELETE FROM chapters WHERE id = ?", (chapter_id,))
            conn.execute("DELETE FROM chapter_storylines WHERE chapter_id = ?", (chapter_id,))
            conn.execute("DELETE FROM notes WHERE chapter_slug = ?", (chapter_path.stem,))
            conn.commit()
        finally:
            conn.close()

    def update_chapter_synopsis(self, path: Path, synopsis: str, upsert_frontmatter_fields) -> None:
        upsert_frontmatter_fields(path, {"synopsis": synopsis})

    def reorder_chapters(
        self,
        db_path: Path,
        chapter_ids: list[int],
        chapters: list[tuple[int, str, Path]],
        upsert_frontmatter_fields,
    ) -> None:
        conn = sqlite3.connect(db_path)
        try:
            for position, chapter_id in enumerate(chapter_ids, start=1):
                conn.execute("UPDATE chapters SET position = ? WHERE id = ?", (position, chapter_id))
            conn.commit()
        finally:
            conn.close()

        path_by_id = {chapter_id: path for chapter_id, _, path in chapters}
        for position, chapter_id in enumerate(chapter_ids, start=1):
            path = path_by_id.get(chapter_id)
            if path and path.exists():
                upsert_frontmatter_fields(path, {"order": position})

    def insert_chapter_record(self, db_path: Path, title: str, filename: str) -> int | None:
        conn = sqlite3.connect(db_path)
        try:
            existing = conn.execute("SELECT id FROM chapters WHERE filename = ?", (filename,)).fetchone()
            if existing:
                return int(existing[0])
            row = conn.execute("SELECT MAX(position) FROM chapters").fetchone()
            position = (row[0] or 0) + 1
            cursor = conn.execute(
                """
                INSERT INTO chapters (title, filename, position, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                (title, filename, position, utc_timestamp()),
            )
            conn.commit()
            return int(cursor.lastrowid)
        finally:
            conn.close()

    def ingest_voice_from(
        self,
        inbox_dir: Path,
        chapters_dir: Path,
        project_root: Path,
        db_path: Path,
        *,
        on_move_error=None,
    ) -> int:
        files = [
            path
            for path in sorted(inbox_dir.iterdir())
            if path.is_file() and path.suffix.lower() in {".txt", ".md"}
        ]
        if not files:
            return 0

        ingested = 0
        for path in files:
            raw_text = path.read_text(encoding="utf-8", errors="replace")
            has_frontmatter = raw_text.lstrip().startswith("---")

            if has_frontmatter:
                body = raw_text.rstrip() + "\n"
                destination = self.unique_path(chapters_dir / f"{path.stem}.md")
                destination.write_text(body, encoding="utf-8")
                fm = parse_frontmatter(body.splitlines())
                title = str(fm.get("title") or friendly_title(destination.stem))
            else:
                title = self.first_nonempty_line(raw_text) or friendly_title(path.stem)
                slug = slugify(title, fallback="entry")
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
                body = f"{frontmatter}\n\n{body_text}\n" if body_text else f"{frontmatter}\n"
                destination.write_text(body, encoding="utf-8")

            self.insert_chapter_record(db_path, title, destination.name)
            try:
                move_to_compost(path, project_root / ".compost")
            except OSError as exc:
                if on_move_error is not None:
                    on_move_error(path, exc)
            ingested += 1

        return ingested

    def build_index_entries(self, chapters_dir: Path, root: Path) -> list[dict[str, object]]:
        return collect_index_entries(chapters_dir, root)

    def write_index(self, entries: list[dict[str, object]], output_path: Path) -> None:
        output_path.write_text(json.dumps(entries, indent=2, ensure_ascii=True), encoding="utf-8")

    @staticmethod
    def upsert_frontmatter_fields(path: Path, updates: dict[str, object]) -> None:
        text = path.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        has_frontmatter = bool(lines and lines[0].strip() == "---")
        end_index = None
        if has_frontmatter:
            for idx in range(1, len(lines)):
                if lines[idx].strip() in {"---", "..."}:
                    end_index = idx
                    break
            if end_index is None:
                has_frontmatter = False

        def serialize(value: object) -> str:
            if isinstance(value, bool):
                return "true" if value else "false"
            if isinstance(value, int):
                return str(value)
            escaped = str(value).replace('"', '\\"')
            return f"\"{escaped}\""

        if has_frontmatter:
            frontmatter_lines = lines[1:end_index]
            body_lines = lines[end_index + 1 :]
            key_positions: dict[str, int] = {}
            for idx, line in enumerate(frontmatter_lines):
                stripped = line.strip()
                if not stripped or stripped.startswith("#") or ":" not in line:
                    continue
                key = line.split(":", 1)[0].strip()
                if key:
                    key_positions[key] = idx
            for key, value in updates.items():
                rendered = f"{key}: {serialize(value)}"
                if key in key_positions:
                    frontmatter_lines[key_positions[key]] = rendered
                else:
                    frontmatter_lines.append(rendered)
            updated = ["---", *frontmatter_lines, "---", *body_lines]
        else:
            frontmatter_lines = [f"{key}: {serialize(value)}" for key, value in updates.items()]
            updated = ["---", *frontmatter_lines, "---", "", *lines]

        updated_text = "\n".join(updated)
        if text.endswith("\n"):
            updated_text += "\n"
        path.write_text(updated_text, encoding="utf-8")

    @staticmethod
    def slugify_name(name: str) -> str:
        return slugify(name, fallback="witchdraft-project")

    @staticmethod
    def move_to_compost(path: Path, root: Path) -> Path | None:
        return move_to_compost(path, root / ".compost")

    @staticmethod
    def friendly_title(stem: str) -> str:
        return friendly_title(stem)

    @staticmethod
    def parse_frontmatter(lines: list[str]) -> dict[str, object]:
        return parse_frontmatter(lines)

    @staticmethod
    def created_from_mtime(path: Path) -> str:
        return created_from_mtime(path)

    @staticmethod
    def iter_entry_paths(chapters_dir: Path) -> list[Path]:
        return iter_entry_paths(chapters_dir)

    @staticmethod
    def parse_created(value: str | None) -> datetime:
        return parse_created(value)

    @staticmethod
    def parse_sequence(value: object | None) -> int | None:
        return parse_sequence(value)

    @staticmethod
    def first_nonempty_line(text: str) -> str:
        for line in text.splitlines():
            stripped = line.strip().lstrip("#").strip()
            if stripped:
                return stripped
        return ""

    @staticmethod
    def unique_path(path: Path) -> Path:
        if not path.exists():
            return path
        counter = 2
        while True:
            candidate = path.with_name(f"{path.stem}-{counter}{path.suffix}")
            if not candidate.exists():
                return candidate
            counter += 1
