from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Callable


WarningCallback = Callable[[str], None] | None


def local_now() -> datetime:
    return datetime.now().astimezone().replace(microsecond=0)


def local_timestamp() -> str:
    return local_now().isoformat()


def local_date_string() -> str:
    return date.today().isoformat()


@dataclass
class MethodologyDB:
    db_path: Path
    project_id: str
    logger: logging.Logger
    warning_callback: WarningCallback = None

    def _warn(self, message: str) -> None:
        if self.warning_callback is not None:
            self.warning_callback(message)

    def migrate_project_ids(self, conn: sqlite3.Connection, project_root: Path) -> None:
        if not self.project_id:
            return
        legacy_values = {
            self.project_id,
            str(project_root),
            project_root.name,
            "",
        }
        for table_name in ("sparks", "companion_notes", "exhale_sessions"):
            rows = conn.execute(f"SELECT DISTINCT project_id FROM {table_name}").fetchall()
            values = {str(row[0] or "") for row in rows}
            if values and values.issubset(legacy_values):
                conn.execute(
                    f"UPDATE {table_name} SET project_id = ? WHERE project_id != ? OR project_id IS NULL",
                    (self.project_id, self.project_id),
                )
        conn.commit()

    def normalize_sparks(self, conn: sqlite3.Connection, spark_date: str | None = None) -> None:
        date_value = spark_date or local_date_string()
        rows = conn.execute(
            """
            SELECT id, text
            FROM sparks
            WHERE project_id = ? AND date = ?
            ORDER BY position, id
            """,
            (self.project_id, date_value),
        ).fetchall()
        kept = [row for row in rows if str(row[1] or "").strip()][:5]
        for new_position, row in enumerate(kept, start=1):
            conn.execute(
                "UPDATE sparks SET position = ? WHERE id = ?",
                (new_position, int(row[0])),
            )
        kept_ids = {int(row[0]) for row in kept}
        for row in rows:
            if int(row[0]) not in kept_ids:
                conn.execute("DELETE FROM sparks WHERE id = ?", (int(row[0]),))

    def get_todays_sparks(self) -> list[tuple[int, str, int]]:
        if not self.db_path.exists():
            return []
        spark_date = local_date_string()
        conn: sqlite3.Connection | None = None
        try:
            conn = sqlite3.connect(self.db_path)
            self.normalize_sparks(conn, spark_date)
            conn.commit()
            rows = conn.execute(
                """
                SELECT position, text, completed
                FROM sparks
                WHERE project_id = ? AND date = ?
                ORDER BY position
                """,
                (self.project_id, spark_date),
            ).fetchall()
            return [(int(row[0]), row[1], int(row[2])) for row in rows]
        except sqlite3.Error:
            self.logger.exception("Failed to load sparks for project %s", self.project_id)
            return []
        finally:
            if conn is not None:
                conn.close()

    def save_spark(self, position: int, text: str, completed: bool) -> None:
        if not self.db_path.exists():
            return
        spark_date = local_date_string()
        conn: sqlite3.Connection | None = None
        try:
            conn = sqlite3.connect(self.db_path)
            completed_at = local_timestamp() if completed else None
            normalized_text = text.strip()
            existing = conn.execute(
                """
                SELECT id FROM sparks
                WHERE project_id = ? AND date = ? AND position = ?
                """,
                (self.project_id, spark_date, position),
            ).fetchone()

            if not normalized_text:
                if existing:
                    conn.execute("DELETE FROM sparks WHERE id = ?", (int(existing[0]),))
                    self.normalize_sparks(conn, spark_date)
                conn.commit()
                return

            if existing:
                conn.execute(
                    """
                    UPDATE sparks
                    SET text = ?, completed = ?, completed_at = ?
                    WHERE project_id = ? AND date = ? AND position = ?
                    """,
                    (
                        normalized_text,
                        1 if completed else 0,
                        completed_at,
                        self.project_id,
                        spark_date,
                        position,
                    ),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO sparks (
                        project_id, date, position, text, completed, completed_at, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        self.project_id,
                        spark_date,
                        position,
                        normalized_text,
                        1 if completed else 0,
                        completed_at,
                        local_timestamp(),
                    ),
                )
            conn.commit()
        except sqlite3.Error:
            self.logger.exception("Failed to save spark %s for project %s", position, self.project_id)
            self._warn("Could not save Spark. Changes may not persist.")
        finally:
            if conn is not None:
                conn.close()

    def get_active_companion_notes(self) -> list[tuple[int, str, str, str | None]]:
        if not self.db_path.exists():
            return []
        conn: sqlite3.Connection | None = None
        try:
            conn = sqlite3.connect(self.db_path)
            rows = conn.execute(
                """
                SELECT id, note, captured_at, chapter_context
                FROM companion_notes
                WHERE project_id = ? AND dismissed = 0
                ORDER BY captured_at DESC
                """,
                (self.project_id,),
            ).fetchall()
            return [(int(row[0]), row[1], row[2], row[3]) for row in rows]
        except sqlite3.Error:
            self.logger.exception("Failed to load companion notes for project %s", self.project_id)
            return []
        finally:
            if conn is not None:
                conn.close()

    def save_companion_note(self, note_text: str, chapter_context: str | None) -> bool:
        conn: sqlite3.Connection | None = None
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute(
                """
                INSERT INTO companion_notes (project_id, note, chapter_context, captured_at)
                VALUES (?, ?, ?, ?)
                """,
                (self.project_id, note_text, chapter_context, local_timestamp()),
            )
            conn.commit()
            return True
        except sqlite3.Error:
            self.logger.exception("Failed to save companion note for project %s", self.project_id)
            self._warn("Could not save Companion Doc note. Changes may not persist.")
            return False
        finally:
            if conn is not None:
                conn.close()

    def dismiss_companion_note(self, note_id: int) -> None:
        conn: sqlite3.Connection | None = None
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute(
                """
                UPDATE companion_notes
                SET dismissed = 1, dismissed_at = ?
                WHERE id = ?
                """,
                (local_timestamp(), note_id),
            )
            conn.commit()
        finally:
            if conn is not None:
                conn.close()

    def get_last_exhale_target(self) -> int | None:
        conn: sqlite3.Connection | None = None
        try:
            conn = sqlite3.connect(self.db_path)
            row = conn.execute(
                """
                SELECT target_words FROM exhale_sessions
                WHERE project_id = ?
                ORDER BY started_at DESC LIMIT 1
                """,
                (self.project_id,),
            ).fetchone()
            return int(row[0]) if row else None
        except sqlite3.Error:
            self.logger.exception("Failed to load exhale target for project %s", self.project_id)
            return None
        finally:
            if conn is not None:
                conn.close()

    def save_exhale_session(self, target: int, words_written: int) -> None:
        conn: sqlite3.Connection | None = None
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute(
                """
                INSERT INTO exhale_sessions (
                    project_id, session_date, target_words, words_written, started_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (self.project_id, local_date_string(), target, words_written, local_timestamp()),
            )
            conn.commit()
        except sqlite3.Error:
            self.logger.exception("Failed to save exhale session for project %s", self.project_id)
            self._warn("Could not save Exhale progress. Session tracking may not persist.")
        finally:
            if conn is not None:
                conn.close()

    def update_exhale_session(self, target: int, words_written: int) -> None:
        conn: sqlite3.Connection | None = None
        try:
            conn = sqlite3.connect(self.db_path)
            completed = 1 if words_written >= target else 0
            completed_at = local_timestamp() if completed else None
            conn.execute(
                """
                UPDATE exhale_sessions
                SET words_written = ?, completed = ?, completed_at = ?
                WHERE project_id = ? AND session_date = ?
                ORDER BY started_at DESC LIMIT 1
                """,
                (words_written, completed, completed_at, self.project_id, local_date_string()),
            )
            conn.commit()
        except sqlite3.Error:
            self.logger.exception("Failed to update exhale session for project %s", self.project_id)
            self._warn("Could not update Exhale progress. Session tracking may be out of date.")
        finally:
            if conn is not None:
                conn.close()
