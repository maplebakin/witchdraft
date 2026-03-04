from __future__ import annotations

import importlib.util
import sqlite3
import threading
from datetime import datetime
from pathlib import Path

from witchdraft.core.scene_utils import split_scenes
from witchdraft.db.schema import ensure_vault_schema
from witchdraft.shadow_bible import run_enhanced_spacy_scan


_SPACY_LOCK = threading.Lock()
_SPACY_NLP = None


def _load_spacy():
    global _SPACY_NLP
    with _SPACY_LOCK:
        if _SPACY_NLP is None:
            import spacy

            _SPACY_NLP = spacy.load("en_core_web_sm")
    return _SPACY_NLP


def _extract_surrounding_traits(ent) -> list[str]:
    traits: set[str] = set()
    doc = ent.doc
    for index in (ent.start - 1, ent.end):
        if 0 <= index < len(doc):
            token = doc[index]
            if token.pos_ == "ADJ":
                traits.add(token.lemma_.lower())
    return sorted(traits)


def _upsert_entity(conn: sqlite3.Connection, name: str, entity_type: str, timestamp: str) -> int:
    existing = conn.execute(
        """
        SELECT id FROM entities
        WHERE lower(name) = lower(?) AND type = ?
        LIMIT 1
        """,
        (name, entity_type),
    ).fetchone()
    if existing:
        entity_id = int(existing[0])
        conn.execute("UPDATE entities SET last_seen = ? WHERE id = ?", (timestamp, entity_id))
        return entity_id

    conn.execute(
        """
        INSERT INTO entities (name, type, last_seen)
        VALUES (?, ?, ?)
        ON CONFLICT(name, type) DO UPDATE SET last_seen=excluded.last_seen
        """,
        (name, entity_type, timestamp),
    )
    row = conn.execute(
        """
        SELECT id FROM entities
        WHERE lower(name) = lower(?) AND type = ?
        LIMIT 1
        """,
        (name, entity_type),
    ).fetchone()
    return int(row[0])


def run_spacy_scan(text: str, db_path: Path) -> None:
    if not text.strip():
        return
    try:
        nlp = _load_spacy()
    except Exception as exc:
        raise RuntimeError("spaCy unavailable (install spacy + en_core_web_sm).") from exc
    timestamp = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

    conn = sqlite3.connect(db_path, timeout=5)
    try:
        ensure_vault_schema(conn)
        scenes = split_scenes(text)
        conn.execute("DELETE FROM scene_entities")
        conn.execute("DELETE FROM scenes")

        for position, (title, body) in enumerate(scenes, start=1):
            cursor = conn.execute(
                """
                INSERT INTO scenes (title, position, updated_at)
                VALUES (?, ?, ?)
                """,
                (title, position, timestamp),
            )
            scene_id = int(cursor.lastrowid)
            if not body.strip():
                continue
            doc = nlp(body)
            counts: dict[int, int] = {}
            for ent in doc.ents:
                if ent.label_ not in {"PERSON", "GPE"}:
                    continue
                name = ent.text.strip()
                if not name:
                    continue
                entity_id = _upsert_entity(conn, name, ent.label_, timestamp)
                counts[entity_id] = counts.get(entity_id, 0) + 1
                if ent.label_ == "PERSON":
                    for trait in _extract_surrounding_traits(ent):
                        conn.execute(
                            """
                            INSERT INTO traits (entity_id, trait, recorded_at)
                            VALUES (?, ?, ?)
                            """,
                            (entity_id, trait, timestamp),
                        )

            for entity_id, count in counts.items():
                conn.execute(
                    """
                    INSERT INTO scene_entities (scene_id, entity_id, count)
                    VALUES (?, ?, ?)
                    """,
                    (scene_id, entity_id, count),
                )
        conn.commit()
    finally:
        conn.close()


class NLPService:
    def __init__(self, *, enhanced: bool = True) -> None:
        self._enhanced = enhanced

    @staticmethod
    def check_spacy_availability() -> bool:
        if importlib.util.find_spec("spacy") is None:
            return False
        if importlib.util.find_spec("en_core_web_sm") is None:
            return False
        return True

    @staticmethod
    def has_scan_data(db_path: Path | None) -> bool:
        if not db_path:
            return False
        conn = sqlite3.connect(db_path)
        try:
            row = conn.execute("SELECT 1 FROM scenes LIMIT 1").fetchone()
        except sqlite3.OperationalError:
            return False
        finally:
            conn.close()
        return row is not None

    def scan(self, text: str, db_path: Path) -> None:
        scan_fn = run_enhanced_spacy_scan if self._enhanced else run_spacy_scan
        scan_fn(text, db_path)

    @staticmethod
    def completed_at() -> str:
        return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
