from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Callable

from PyQt6.QtGui import QTextCharFormat, QTextCursor
from PyQt6.QtWidgets import QTextEdit


class AnnotationManager:
    def __init__(
        self,
        editor: QTextEdit,
        *,
        note_highlight,
        active_highlight,
        warning_callback: Callable[[str], None],
        logger,
    ) -> None:
        self._editor = editor
        self._notes_panel = None
        self._warning_callback = warning_callback
        self._logger = logger
        self._note_highlight = note_highlight
        self._active_highlight = active_highlight
        self._chapter_notes: list[dict[str, object]] = []
        self._active_note_id: int | None = None

    @property
    def chapter_notes(self) -> list[dict[str, object]]:
        return self._chapter_notes

    @property
    def active_note_id(self) -> int | None:
        return self._active_note_id

    @active_note_id.setter
    def active_note_id(self, value: int | None) -> None:
        self._active_note_id = value

    def set_notes_panel(self, panel) -> None:
        self._notes_panel = panel

    @staticmethod
    def current_chapter_slug(chapter_path: Path | None) -> str | None:
        if not chapter_path:
            return None
        return chapter_path.stem

    @staticmethod
    def is_attached_note_range(start_pos: int, end_pos: int, doc_len: int) -> bool:
        return 0 <= start_pos < end_pos <= doc_len

    def clear_notes(self) -> None:
        self._chapter_notes = []
        self._active_note_id = None
        self._editor.setExtraSelections([])
        if self._notes_panel is not None:
            self._notes_panel.set_notes([])

    def load_notes(self, db_path: Path | None, chapter_slug: str | None) -> None:
        if not db_path or not chapter_slug:
            self.clear_notes()
            return

        conn = sqlite3.connect(db_path)
        try:
            rows = conn.execute(
                """
                SELECT id, start_pos, end_pos, note_text, created_at
                FROM notes
                WHERE chapter_slug = ?
                ORDER BY start_pos, created_at
                """,
                (chapter_slug,),
            ).fetchall()
        finally:
            conn.close()

        doc_len = len(self._editor.toPlainText())
        notes: list[dict[str, object]] = []
        for row in rows:
            start_pos = int(row[1])
            end_pos = int(row[2])
            notes.append(
                {
                    "id": int(row[0]),
                    "chapter_slug": chapter_slug,
                    "start_pos": start_pos,
                    "end_pos": end_pos,
                    "note_text": str(row[3] or ""),
                    "created_at": str(row[4] or ""),
                    "detached": not self.is_attached_note_range(start_pos, end_pos, doc_len),
                }
            )
        self._chapter_notes = notes
        self._active_note_id = None
        if self._notes_panel is not None:
            self._notes_panel.set_notes(self._chapter_notes)
        self.refresh_highlights()

    def add_note(self, db_path: Path, chapter_slug: str, start_pos: int, end_pos: int, note_text: str) -> int:
        created_at = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
        conn = sqlite3.connect(db_path)
        try:
            cursor = conn.execute(
                """
                INSERT INTO notes (chapter_slug, start_pos, end_pos, note_text, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (chapter_slug, int(start_pos), int(end_pos), note_text, created_at),
            )
            note_id = int(cursor.lastrowid)
            conn.commit()
            return note_id
        finally:
            conn.close()

    def update_note_text(self, db_path: Path, note_id: int, note_text: str) -> None:
        conn = sqlite3.connect(db_path)
        try:
            conn.execute("UPDATE notes SET note_text = ? WHERE id = ?", (note_text, note_id))
            conn.commit()
        finally:
            conn.close()

    def delete_note(self, db_path: Path, note_id: int) -> None:
        conn = sqlite3.connect(db_path)
        try:
            conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))
            conn.commit()
        finally:
            conn.close()

    def focus_note(self, note_id: int) -> dict[str, object] | None:
        note = next((entry for entry in self._chapter_notes if int(entry.get("id", 0)) == note_id), None)
        if note is None:
            return None
        self._active_note_id = note_id
        self.refresh_highlights(active_note_id=note_id)

        doc_len = len(self._editor.toPlainText())
        start_pos = int(note.get("start_pos", 0))
        end_pos = int(note.get("end_pos", 0))
        if not self.is_attached_note_range(start_pos, end_pos, doc_len):
            note["detached"] = True
            if self._notes_panel is not None:
                self._notes_panel.set_notes(self._chapter_notes, selected_note_id=note_id)
            return note

        cursor = QTextCursor(self._editor.document())
        cursor.setPosition(start_pos)
        cursor.setPosition(end_pos, QTextCursor.MoveMode.KeepAnchor)
        self._editor.setTextCursor(cursor)
        self._editor.ensureCursorVisible()
        return note

    def refresh_highlights(self, active_note_id: int | None = None, *, sync_panel: bool = False) -> None:
        if active_note_id is None:
            active_note_id = self._active_note_id
        note_ids = {int(note.get("id", 0)) for note in self._chapter_notes}
        if active_note_id is not None and active_note_id not in note_ids:
            active_note_id = None
        self._active_note_id = active_note_id

        selections: list[QTextEdit.ExtraSelection] = []
        doc_len = len(self._editor.toPlainText())
        detached_changed = False
        for note in self._chapter_notes:
            note_id = int(note.get("id", 0))
            start_pos = int(note.get("start_pos", 0))
            end_pos = int(note.get("end_pos", 0))
            attached = self.is_attached_note_range(start_pos, end_pos, doc_len)
            detached = not attached
            if bool(note.get("detached", False)) != detached:
                note["detached"] = detached
                detached_changed = True
            if not attached:
                continue
            cursor = QTextCursor(self._editor.document())
            cursor.setPosition(start_pos)
            cursor.setPosition(end_pos, QTextCursor.MoveMode.KeepAnchor)
            selection = QTextEdit.ExtraSelection()
            fmt = QTextCharFormat()
            fmt.setBackground(self._active_highlight if note_id == active_note_id else self._note_highlight)
            selection.cursor = cursor
            selection.format = fmt
            selections.append(selection)

        self._editor.setExtraSelections(selections)
        if (sync_panel or detached_changed) and self._notes_panel is not None:
            self._notes_panel.set_notes(self._chapter_notes, selected_note_id=active_note_id)

    def handle_document_change(
        self,
        db_path: Path | None,
        chapter_slug: str | None,
        position: int,
        chars_removed: int,
        chars_added: int,
    ) -> bool:
        if not db_path or not self._chapter_notes:
            return False
        delta = chars_added - chars_removed
        if delta == 0 and chars_removed == 0:
            return False

        changed = False
        for note in self._chapter_notes:
            start_pos = int(note.get("start_pos", 0))
            end_pos = int(note.get("end_pos", 0))
            if position <= start_pos:
                note["start_pos"] = max(0, start_pos + delta)
                note["end_pos"] = max(int(note["start_pos"]), end_pos + delta)
                changed = True
            elif position < end_pos:
                note["end_pos"] = max(start_pos, end_pos + delta)
                changed = True

        if not changed:
            return False

        conn: sqlite3.Connection | None = None
        try:
            conn = sqlite3.connect(db_path)
            conn.executemany(
                "UPDATE notes SET start_pos = ?, end_pos = ? WHERE id = ?",
                [
                    (
                        int(note.get("start_pos", 0)),
                        int(note.get("end_pos", 0)),
                        int(note.get("id", 0)),
                    )
                    for note in self._chapter_notes
                ],
            )
            conn.commit()
            return True
        except sqlite3.Error:
            self._logger.exception("Failed to update note offsets for chapter %s", chapter_slug)
            self._warning_callback("Could not update note positions. Inline annotations may be out of sync.")
            return False
        finally:
            if conn is not None:
                conn.close()
