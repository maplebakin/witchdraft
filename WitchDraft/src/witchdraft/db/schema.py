from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from witchdraft.palette_theme_db import init_palette_theme_tables


def utc_timestamp() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def ensure_vault_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
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
    conn.execute(
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
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS chapters (
            id INTEGER PRIMARY KEY,
            title TEXT NOT NULL,
            filename TEXT NOT NULL UNIQUE,
            position INTEGER NOT NULL UNIQUE,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS storylines (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS chapter_storylines (
            chapter_id INTEGER NOT NULL,
            storyline_id INTEGER NOT NULL,
            PRIMARY KEY (chapter_id, storyline_id),
            FOREIGN KEY(chapter_id) REFERENCES chapters(id),
            FOREIGN KEY(storyline_id) REFERENCES storylines(id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS scenes (
            id INTEGER PRIMARY KEY,
            title TEXT NOT NULL,
            position INTEGER NOT NULL UNIQUE,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
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
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS scene_themes (
            scene_id INTEGER NOT NULL,
            theme_id INTEGER NOT NULL,
            intensity INTEGER NOT NULL,
            recorded_at TEXT NOT NULL,
            PRIMARY KEY (scene_id, theme_id),
            FOREIGN KEY(scene_id) REFERENCES scenes(id),
            FOREIGN KEY(theme_id) REFERENCES themes(id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS scene_emotions (
            scene_id INTEGER NOT NULL,
            emotion TEXT NOT NULL,
            intensity INTEGER NOT NULL,
            recorded_at TEXT NOT NULL,
            PRIMARY KEY (scene_id, emotion),
            FOREIGN KEY(scene_id) REFERENCES scenes(id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS writing_log (
            date TEXT PRIMARY KEY,
            words_written INTEGER NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY,
            chapter_slug TEXT NOT NULL,
            start_pos INTEGER NOT NULL,
            end_pos INTEGER NOT NULL,
            note_text TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_notes_chapter_slug
        ON notes(chapter_slug)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_scene_emotions_scene
        ON scene_emotions(scene_id)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_scene_themes_scene
        ON scene_themes(scene_id)
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS exhale_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id TEXT NOT NULL,
            session_date TEXT NOT NULL,
            target_words INTEGER NOT NULL,
            words_written INTEGER NOT NULL DEFAULT 0,
            completed INTEGER NOT NULL DEFAULT 0,
            started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            completed_at DATETIME
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS sparks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id TEXT NOT NULL,
            date TEXT NOT NULL,
            position INTEGER NOT NULL,
            text TEXT NOT NULL,
            completed INTEGER NOT NULL DEFAULT 0,
            completed_at DATETIME,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS companion_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id TEXT NOT NULL,
            note TEXT NOT NULL,
            chapter_context TEXT,
            captured_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            dismissed INTEGER NOT NULL DEFAULT 0,
            dismissed_at DATETIME
        )
        """
    )
    init_palette_theme_tables(conn)
    conn.commit()


def ensure_default_chapter(conn: sqlite3.Connection, chapters_dir: Path) -> None:
    row = conn.execute("SELECT 1 FROM chapters LIMIT 1").fetchone()
    if row:
        return
    title = "Chapter 1"
    filename = "chapter-1.md"
    path = chapters_dir / filename
    if not path.exists():
        path.write_text(f"# {title}\n\n", encoding="utf-8")
    conn.execute(
        """
        INSERT INTO chapters (title, filename, position, updated_at)
        VALUES (?, ?, ?, ?)
        """,
        (title, filename, 1, utc_timestamp()),
    )
    conn.commit()
