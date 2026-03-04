"""
WitchDraft Palette & Theme Database Functions

Provides CRUD operations for the palette/theme/connection system,
following the established patterns in app.py.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional


# =============================================================================
# DATA CLASSES
# =============================================================================


@dataclass
class Palette:
    id: int
    name: str
    description: Optional[str]
    created_at: str
    updated_at: str


@dataclass
class PaletteColor:
    id: int
    palette_id: int
    hex_code: str
    color_name: Optional[str]
    position: int
    created_at: str


@dataclass
class Theme:
    id: int
    name: str
    description: Optional[str]
    created_at: str
    updated_at: str


@dataclass
class EntityPalette:
    id: int
    entity_id: int
    palette_id: int
    context: str
    notes: Optional[str]
    assigned_at: str


@dataclass
class EntityTheme:
    id: int
    entity_id: int
    theme_id: int
    intensity: int
    notes: Optional[str]
    assigned_at: str


@dataclass
class EntityConnection:
    id: int
    entity_a_id: int
    entity_b_id: int
    relationship_type: str
    description: Optional[str]
    bidirectional: bool
    created_at: str
    updated_at: str


@dataclass
class PaletteEvolution:
    id: int
    entity_id: int
    palette_id: int
    scene_id: Optional[int]
    chapter_id: Optional[int]
    context: str
    recorded_at: str


@dataclass
class ThemeEvolution:
    id: int
    entity_id: int
    theme_id: int
    intensity_before: int
    intensity_after: int
    scene_id: Optional[int]
    chapter_id: Optional[int]
    context: str
    recorded_at: str


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================


def _timestamp() -> str:
    """Generate ISO 8601 timestamp matching WitchDraft conventions."""
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def init_palette_theme_tables(conn: sqlite3.Connection) -> None:
    """
    Create all palette/theme tables if they don't exist.
    Call this after _init_vault() in app.py.
    """
    conn.execute("""
        CREATE TABLE IF NOT EXISTS palettes (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(name)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS palette_colors (
            id INTEGER PRIMARY KEY,
            palette_id INTEGER NOT NULL,
            hex_code TEXT NOT NULL,
            color_name TEXT,
            position INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(palette_id) REFERENCES palettes(id) ON DELETE CASCADE,
            UNIQUE(palette_id, position)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS themes (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(name)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS entity_palettes (
            id INTEGER PRIMARY KEY,
            entity_id INTEGER NOT NULL,
            palette_id INTEGER NOT NULL,
            context TEXT NOT NULL DEFAULT 'general',
            notes TEXT,
            assigned_at TEXT NOT NULL,
            FOREIGN KEY(entity_id) REFERENCES entities(id) ON DELETE CASCADE,
            FOREIGN KEY(palette_id) REFERENCES palettes(id) ON DELETE CASCADE,
            UNIQUE(entity_id, palette_id, context)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS entity_themes (
            id INTEGER PRIMARY KEY,
            entity_id INTEGER NOT NULL,
            theme_id INTEGER NOT NULL,
            intensity INTEGER NOT NULL DEFAULT 3 CHECK(intensity BETWEEN 1 AND 5),
            notes TEXT,
            assigned_at TEXT NOT NULL,
            FOREIGN KEY(entity_id) REFERENCES entities(id) ON DELETE CASCADE,
            FOREIGN KEY(theme_id) REFERENCES themes(id) ON DELETE CASCADE,
            UNIQUE(entity_id, theme_id)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS entity_connections (
            id INTEGER PRIMARY KEY,
            entity_a_id INTEGER NOT NULL,
            entity_b_id INTEGER NOT NULL,
            relationship_type TEXT NOT NULL,
            description TEXT,
            bidirectional INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(entity_a_id) REFERENCES entities(id) ON DELETE CASCADE,
            FOREIGN KEY(entity_b_id) REFERENCES entities(id) ON DELETE CASCADE,
            UNIQUE(entity_a_id, entity_b_id, relationship_type),
            CHECK(entity_a_id != entity_b_id)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS palette_evolution (
            id INTEGER PRIMARY KEY,
            entity_id INTEGER NOT NULL,
            palette_id INTEGER NOT NULL,
            scene_id INTEGER,
            chapter_id INTEGER,
            context TEXT NOT NULL,
            recorded_at TEXT NOT NULL,
            FOREIGN KEY(entity_id) REFERENCES entities(id) ON DELETE CASCADE,
            FOREIGN KEY(palette_id) REFERENCES palettes(id) ON DELETE CASCADE,
            FOREIGN KEY(scene_id) REFERENCES scenes(id) ON DELETE SET NULL,
            FOREIGN KEY(chapter_id) REFERENCES chapters(id) ON DELETE SET NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS theme_evolution (
            id INTEGER PRIMARY KEY,
            entity_id INTEGER NOT NULL,
            theme_id INTEGER NOT NULL,
            intensity_before INTEGER NOT NULL CHECK(intensity_before BETWEEN 1 AND 5),
            intensity_after INTEGER NOT NULL CHECK(intensity_after BETWEEN 1 AND 5),
            scene_id INTEGER,
            chapter_id INTEGER,
            context TEXT NOT NULL,
            recorded_at TEXT NOT NULL,
            FOREIGN KEY(entity_id) REFERENCES entities(id) ON DELETE CASCADE,
            FOREIGN KEY(theme_id) REFERENCES themes(id) ON DELETE CASCADE,
            FOREIGN KEY(scene_id) REFERENCES scenes(id) ON DELETE SET NULL,
            FOREIGN KEY(chapter_id) REFERENCES chapters(id) ON DELETE SET NULL
        )
    """)

    # Create indexes for query performance
    conn.execute("CREATE INDEX IF NOT EXISTS idx_palette_colors_palette ON palette_colors(palette_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_entity_palettes_entity ON entity_palettes(entity_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_entity_palettes_palette ON entity_palettes(palette_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_entity_themes_entity ON entity_themes(entity_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_entity_themes_theme ON entity_themes(theme_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_entity_connections_a ON entity_connections(entity_a_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_entity_connections_b ON entity_connections(entity_b_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_palette_evolution_entity ON palette_evolution(entity_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_theme_evolution_entity ON theme_evolution(entity_id)")
    # Note: caller is responsible for commit()


# =============================================================================
# PALETTE CRUD
# =============================================================================


def create_palette(
    conn: sqlite3.Connection,
    name: str,
    description: Optional[str] = None,
    colors: Optional[list[tuple[str, Optional[str]]]] = None,
) -> int:
    """
    Create a new palette with optional colors.

    Args:
        conn: Database connection
        name: Unique palette name
        description: Optional description
        colors: List of (hex_code, color_name) tuples in order

    Returns:
        The new palette ID
    """
    timestamp = _timestamp()
    cursor = conn.execute(
        """
        INSERT INTO palettes (name, description, created_at, updated_at)
        VALUES (?, ?, ?, ?)
        """,
        (name, description, timestamp, timestamp),
    )
    palette_id = int(cursor.lastrowid)

    if colors:
        for position, (hex_code, color_name) in enumerate(colors):
            conn.execute(
                """
                INSERT INTO palette_colors (palette_id, hex_code, color_name, position, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (palette_id, hex_code, color_name, position, timestamp),
            )

    conn.commit()
    return palette_id


def upsert_palette(
    conn: sqlite3.Connection,
    name: str,
    description: Optional[str] = None,
) -> int:
    """
    Insert or update a palette by name.

    Returns:
        The palette ID
    """
    timestamp = _timestamp()
    conn.execute(
        """
        INSERT INTO palettes (name, description, created_at, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(name) DO UPDATE SET
            description=excluded.description,
            updated_at=excluded.updated_at
        """,
        (name, description, timestamp, timestamp),
    )
    row = conn.execute(
        "SELECT id FROM palettes WHERE name = ?",
        (name,),
    ).fetchone()
    conn.commit()
    return int(row[0])


def get_palette(conn: sqlite3.Connection, palette_id: int) -> Optional[Palette]:
    """Fetch a palette by ID."""
    row = conn.execute(
        "SELECT id, name, description, created_at, updated_at FROM palettes WHERE id = ?",
        (palette_id,),
    ).fetchone()
    if row:
        return Palette(*row)
    return None


def get_palette_by_name(conn: sqlite3.Connection, name: str) -> Optional[Palette]:
    """Fetch a palette by name."""
    row = conn.execute(
        "SELECT id, name, description, created_at, updated_at FROM palettes WHERE name = ?",
        (name,),
    ).fetchone()
    if row:
        return Palette(*row)
    return None


def list_palettes(conn: sqlite3.Connection) -> list[Palette]:
    """List all palettes ordered by name."""
    rows = conn.execute(
        "SELECT id, name, description, created_at, updated_at FROM palettes ORDER BY name"
    ).fetchall()
    return [Palette(*row) for row in rows]


def delete_palette(conn: sqlite3.Connection, palette_id: int) -> None:
    """Delete a palette and its colors (cascade)."""
    conn.execute("DELETE FROM palettes WHERE id = ?", (palette_id,))
    conn.commit()


# =============================================================================
# PALETTE COLORS CRUD
# =============================================================================


def add_palette_color(
    conn: sqlite3.Connection,
    palette_id: int,
    hex_code: str,
    color_name: Optional[str] = None,
    position: Optional[int] = None,
) -> int:
    """
    Add a color to a palette.

    If position is None, appends to end of palette.
    """
    timestamp = _timestamp()

    if position is None:
        row = conn.execute(
            "SELECT COALESCE(MAX(position), -1) + 1 FROM palette_colors WHERE palette_id = ?",
            (palette_id,),
        ).fetchone()
        position = row[0]

    cursor = conn.execute(
        """
        INSERT INTO palette_colors (palette_id, hex_code, color_name, position, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (palette_id, hex_code, color_name, position, timestamp),
    )
    conn.commit()
    return int(cursor.lastrowid)


def get_palette_colors(conn: sqlite3.Connection, palette_id: int) -> list[PaletteColor]:
    """Get all colors for a palette, ordered by position."""
    rows = conn.execute(
        """
        SELECT id, palette_id, hex_code, color_name, position, created_at
        FROM palette_colors
        WHERE palette_id = ?
        ORDER BY position
        """,
        (palette_id,),
    ).fetchall()
    return [PaletteColor(*row) for row in rows]


def update_palette_color(
    conn: sqlite3.Connection,
    color_id: int,
    hex_code: Optional[str] = None,
    color_name: Optional[str] = None,
) -> None:
    """Update a palette color's hex code or name."""
    if hex_code is not None:
        conn.execute(
            "UPDATE palette_colors SET hex_code = ? WHERE id = ?",
            (hex_code, color_id),
        )
    if color_name is not None:
        conn.execute(
            "UPDATE palette_colors SET color_name = ? WHERE id = ?",
            (color_name, color_id),
        )
    conn.commit()


def delete_palette_color(conn: sqlite3.Connection, color_id: int) -> None:
    """Remove a color from a palette."""
    conn.execute("DELETE FROM palette_colors WHERE id = ?", (color_id,))
    conn.commit()


def replace_palette_colors(
    conn: sqlite3.Connection,
    palette_id: int,
    colors: list[tuple[str, Optional[str]]],
) -> None:
    """
    Replace all colors in a palette.

    Args:
        palette_id: The palette to update
        colors: List of (hex_code, color_name) tuples in order
    """
    timestamp = _timestamp()

    conn.execute("DELETE FROM palette_colors WHERE palette_id = ?", (palette_id,))

    for position, (hex_code, color_name) in enumerate(colors):
        conn.execute(
            """
            INSERT INTO palette_colors (palette_id, hex_code, color_name, position, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (palette_id, hex_code, color_name, position, timestamp),
        )

    conn.execute(
        "UPDATE palettes SET updated_at = ? WHERE id = ?",
        (timestamp, palette_id),
    )
    conn.commit()


# =============================================================================
# THEME CRUD
# =============================================================================


def create_theme(
    conn: sqlite3.Connection,
    name: str,
    description: Optional[str] = None,
) -> int:
    """Create a new theme."""
    timestamp = _timestamp()
    cursor = conn.execute(
        """
        INSERT INTO themes (name, description, created_at, updated_at)
        VALUES (?, ?, ?, ?)
        """,
        (name, description, timestamp, timestamp),
    )
    conn.commit()
    return int(cursor.lastrowid)


def upsert_theme(
    conn: sqlite3.Connection,
    name: str,
    description: Optional[str] = None,
) -> int:
    """Insert or update a theme by name."""
    timestamp = _timestamp()
    conn.execute(
        """
        INSERT INTO themes (name, description, created_at, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(name) DO UPDATE SET
            description=excluded.description,
            updated_at=excluded.updated_at
        """,
        (name, description, timestamp, timestamp),
    )
    row = conn.execute(
        "SELECT id FROM themes WHERE name = ?",
        (name,),
    ).fetchone()
    conn.commit()
    return int(row[0])


def get_theme(conn: sqlite3.Connection, theme_id: int) -> Optional[Theme]:
    """Fetch a theme by ID."""
    row = conn.execute(
        "SELECT id, name, description, created_at, updated_at FROM themes WHERE id = ?",
        (theme_id,),
    ).fetchone()
    if row:
        return Theme(*row)
    return None


def get_theme_by_name(conn: sqlite3.Connection, name: str) -> Optional[Theme]:
    """Fetch a theme by name."""
    row = conn.execute(
        "SELECT id, name, description, created_at, updated_at FROM themes WHERE name = ?",
        (name,),
    ).fetchone()
    if row:
        return Theme(*row)
    return None


def list_themes(conn: sqlite3.Connection) -> list[Theme]:
    """List all themes ordered by name."""
    rows = conn.execute(
        "SELECT id, name, description, created_at, updated_at FROM themes ORDER BY name"
    ).fetchall()
    return [Theme(*row) for row in rows]


def delete_theme(conn: sqlite3.Connection, theme_id: int) -> None:
    """Delete a theme."""
    conn.execute("DELETE FROM themes WHERE id = ?", (theme_id,))
    conn.commit()


# =============================================================================
# ENTITY-PALETTE ASSOCIATIONS
# =============================================================================


def assign_palette_to_entity(
    conn: sqlite3.Connection,
    entity_id: int,
    palette_id: int,
    context: str = "general",
    notes: Optional[str] = None,
) -> int:
    """
    Assign a palette to an entity with a context.

    Context examples: "general", "costume", "magic", "mood", "aura", "setting"
    """
    timestamp = _timestamp()
    cursor = conn.execute(
        """
        INSERT INTO entity_palettes (entity_id, palette_id, context, notes, assigned_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(entity_id, palette_id, context) DO UPDATE SET
            notes=excluded.notes,
            assigned_at=excluded.assigned_at
        """,
        (entity_id, palette_id, context, notes, timestamp),
    )
    conn.commit()
    row = conn.execute(
        "SELECT id FROM entity_palettes WHERE entity_id = ? AND palette_id = ? AND context = ?",
        (entity_id, palette_id, context),
    ).fetchone()
    return int(row[0])


def get_entity_palettes(
    conn: sqlite3.Connection,
    entity_id: int,
    context: Optional[str] = None,
) -> list[tuple[EntityPalette, Palette]]:
    """
    Get all palettes assigned to an entity, optionally filtered by context.

    Returns list of (EntityPalette, Palette) tuples.
    """
    if context:
        rows = conn.execute(
            """
            SELECT ep.id, ep.entity_id, ep.palette_id, ep.context, ep.notes, ep.assigned_at,
                   p.id, p.name, p.description, p.created_at, p.updated_at
            FROM entity_palettes ep
            JOIN palettes p ON ep.palette_id = p.id
            WHERE ep.entity_id = ? AND ep.context = ?
            ORDER BY p.name
            """,
            (entity_id, context),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT ep.id, ep.entity_id, ep.palette_id, ep.context, ep.notes, ep.assigned_at,
                   p.id, p.name, p.description, p.created_at, p.updated_at
            FROM entity_palettes ep
            JOIN palettes p ON ep.palette_id = p.id
            WHERE ep.entity_id = ?
            ORDER BY ep.context, p.name
            """,
            (entity_id,),
        ).fetchall()

    return [
        (EntityPalette(*row[:6]), Palette(*row[6:]))
        for row in rows
    ]


def get_entities_with_palette(conn: sqlite3.Connection, palette_id: int) -> list[tuple[int, str, str]]:
    """
    Get all entities using a specific palette.

    Returns list of (entity_id, entity_name, context) tuples.
    """
    rows = conn.execute(
        """
        SELECT e.id, e.name, ep.context
        FROM entity_palettes ep
        JOIN entities e ON ep.entity_id = e.id
        WHERE ep.palette_id = ?
        ORDER BY e.name
        """,
        (palette_id,),
    ).fetchall()
    return [(row[0], row[1], row[2]) for row in rows]


def remove_palette_from_entity(
    conn: sqlite3.Connection,
    entity_id: int,
    palette_id: int,
    context: Optional[str] = None,
) -> None:
    """Remove a palette assignment from an entity."""
    if context:
        conn.execute(
            "DELETE FROM entity_palettes WHERE entity_id = ? AND palette_id = ? AND context = ?",
            (entity_id, palette_id, context),
        )
    else:
        conn.execute(
            "DELETE FROM entity_palettes WHERE entity_id = ? AND palette_id = ?",
            (entity_id, palette_id),
        )
    conn.commit()


# =============================================================================
# ENTITY-THEME ASSOCIATIONS
# =============================================================================


def assign_theme_to_entity(
    conn: sqlite3.Connection,
    entity_id: int,
    theme_id: int,
    intensity: int = 3,
    notes: Optional[str] = None,
) -> int:
    """
    Assign a theme to an entity with intensity.

    Intensity: 1=subtle, 2=minor, 3=moderate, 4=significant, 5=dominant
    """
    if not 1 <= intensity <= 5:
        raise ValueError("Intensity must be between 1 and 5")

    timestamp = _timestamp()
    conn.execute(
        """
        INSERT INTO entity_themes (entity_id, theme_id, intensity, notes, assigned_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(entity_id, theme_id) DO UPDATE SET
            intensity=excluded.intensity,
            notes=excluded.notes,
            assigned_at=excluded.assigned_at
        """,
        (entity_id, theme_id, intensity, notes, timestamp),
    )
    conn.commit()
    row = conn.execute(
        "SELECT id FROM entity_themes WHERE entity_id = ? AND theme_id = ?",
        (entity_id, theme_id),
    ).fetchone()
    return int(row[0])


def get_entity_themes(conn: sqlite3.Connection, entity_id: int) -> list[tuple[EntityTheme, Theme]]:
    """
    Get all themes assigned to an entity.

    Returns list of (EntityTheme, Theme) tuples ordered by intensity (highest first).
    """
    rows = conn.execute(
        """
        SELECT et.id, et.entity_id, et.theme_id, et.intensity, et.notes, et.assigned_at,
               t.id, t.name, t.description, t.created_at, t.updated_at
        FROM entity_themes et
        JOIN themes t ON et.theme_id = t.id
        WHERE et.entity_id = ?
        ORDER BY et.intensity DESC, t.name
        """,
        (entity_id,),
    ).fetchall()

    return [
        (EntityTheme(*row[:6]), Theme(*row[6:]))
        for row in rows
    ]


def get_entities_with_theme(conn: sqlite3.Connection, theme_id: int) -> list[tuple[int, str, int]]:
    """
    Get all entities with a specific theme.

    Returns list of (entity_id, entity_name, intensity) tuples.
    """
    rows = conn.execute(
        """
        SELECT e.id, e.name, et.intensity
        FROM entity_themes et
        JOIN entities e ON et.entity_id = e.id
        WHERE et.theme_id = ?
        ORDER BY et.intensity DESC, e.name
        """,
        (theme_id,),
    ).fetchall()
    return [(row[0], row[1], row[2]) for row in rows]


def update_entity_theme_intensity(
    conn: sqlite3.Connection,
    entity_id: int,
    theme_id: int,
    intensity: int,
) -> None:
    """Update the intensity of a theme for an entity."""
    if not 1 <= intensity <= 5:
        raise ValueError("Intensity must be between 1 and 5")

    timestamp = _timestamp()
    conn.execute(
        """
        UPDATE entity_themes
        SET intensity = ?, assigned_at = ?
        WHERE entity_id = ? AND theme_id = ?
        """,
        (intensity, timestamp, entity_id, theme_id),
    )
    conn.commit()


def remove_theme_from_entity(
    conn: sqlite3.Connection,
    entity_id: int,
    theme_id: int,
) -> None:
    """Remove a theme from an entity."""
    conn.execute(
        "DELETE FROM entity_themes WHERE entity_id = ? AND theme_id = ?",
        (entity_id, theme_id),
    )
    conn.commit()


# =============================================================================
# ENTITY CONNECTIONS
# =============================================================================


def create_entity_connection(
    conn: sqlite3.Connection,
    entity_a_id: int,
    entity_b_id: int,
    relationship_type: str,
    description: Optional[str] = None,
    bidirectional: bool = True,
) -> int:
    """
    Create a connection between two entities.

    Relationship types: "ally", "enemy", "family", "mentor", "romantic", "rival", etc.
    """
    if entity_a_id == entity_b_id:
        raise ValueError("Cannot create connection between an entity and itself")

    timestamp = _timestamp()
    cursor = conn.execute(
        """
        INSERT INTO entity_connections
            (entity_a_id, entity_b_id, relationship_type, description, bidirectional, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(entity_a_id, entity_b_id, relationship_type) DO UPDATE SET
            description=excluded.description,
            bidirectional=excluded.bidirectional,
            updated_at=excluded.updated_at
        """,
        (entity_a_id, entity_b_id, relationship_type, description, int(bidirectional), timestamp, timestamp),
    )
    conn.commit()
    row = conn.execute(
        "SELECT id FROM entity_connections WHERE entity_a_id = ? AND entity_b_id = ? AND relationship_type = ?",
        (entity_a_id, entity_b_id, relationship_type),
    ).fetchone()
    return int(row[0])


def get_entity_connections(
    conn: sqlite3.Connection,
    entity_id: int,
    relationship_type: Optional[str] = None,
) -> list[tuple[EntityConnection, int, str]]:
    """
    Get all connections for an entity (both directions for bidirectional).

    Returns list of (EntityConnection, other_entity_id, other_entity_name) tuples.
    """
    params: list = [entity_id, entity_id]
    type_filter = ""
    if relationship_type:
        type_filter = " AND ec.relationship_type = ?"
        params.append(relationship_type)

    rows = conn.execute(
        f"""
        SELECT ec.id, ec.entity_a_id, ec.entity_b_id, ec.relationship_type,
               ec.description, ec.bidirectional, ec.created_at, ec.updated_at,
               CASE WHEN ec.entity_a_id = ? THEN ec.entity_b_id ELSE ec.entity_a_id END as other_id,
               e.name as other_name
        FROM entity_connections ec
        JOIN entities e ON e.id = CASE WHEN ec.entity_a_id = ? THEN ec.entity_b_id ELSE ec.entity_a_id END
        WHERE (ec.entity_a_id = ? OR (ec.entity_b_id = ? AND ec.bidirectional = 1))
        {type_filter}
        ORDER BY ec.relationship_type, e.name
        """,
        params[:2] + [entity_id, entity_id] + params[2:],
    ).fetchall()

    return [
        (EntityConnection(*row[:8]), row[8], row[9])
        for row in rows
    ]


def delete_entity_connection(
    conn: sqlite3.Connection,
    entity_a_id: int,
    entity_b_id: int,
    relationship_type: str,
) -> None:
    """Delete a specific connection between entities."""
    conn.execute(
        "DELETE FROM entity_connections WHERE entity_a_id = ? AND entity_b_id = ? AND relationship_type = ?",
        (entity_a_id, entity_b_id, relationship_type),
    )
    conn.commit()


# =============================================================================
# PALETTE EVOLUTION
# =============================================================================


def record_palette_evolution(
    conn: sqlite3.Connection,
    entity_id: int,
    palette_id: int,
    context: str,
    scene_id: Optional[int] = None,
    chapter_id: Optional[int] = None,
) -> int:
    """
    Record a palette change for an entity at a story point.

    Use this to track how a character's color associations change throughout the narrative.
    """
    timestamp = _timestamp()
    cursor = conn.execute(
        """
        INSERT INTO palette_evolution (entity_id, palette_id, scene_id, chapter_id, context, recorded_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (entity_id, palette_id, scene_id, chapter_id, context, timestamp),
    )
    conn.commit()
    return int(cursor.lastrowid)


def get_palette_evolution(
    conn: sqlite3.Connection,
    entity_id: int,
) -> list[tuple[PaletteEvolution, Palette]]:
    """
    Get the palette evolution history for an entity.

    Returns list of (PaletteEvolution, Palette) tuples ordered by recorded_at.
    """
    rows = conn.execute(
        """
        SELECT pe.id, pe.entity_id, pe.palette_id, pe.scene_id, pe.chapter_id,
               pe.context, pe.recorded_at,
               p.id, p.name, p.description, p.created_at, p.updated_at
        FROM palette_evolution pe
        JOIN palettes p ON pe.palette_id = p.id
        WHERE pe.entity_id = ?
        ORDER BY pe.recorded_at
        """,
        (entity_id,),
    ).fetchall()

    return [
        (PaletteEvolution(*row[:7]), Palette(*row[7:]))
        for row in rows
    ]


# =============================================================================
# THEME EVOLUTION
# =============================================================================


def record_theme_evolution(
    conn: sqlite3.Connection,
    entity_id: int,
    theme_id: int,
    intensity_before: int,
    intensity_after: int,
    context: str,
    scene_id: Optional[int] = None,
    chapter_id: Optional[int] = None,
) -> int:
    """
    Record a theme intensity change for an entity at a story point.

    Use this to track how a character's thematic associations shift throughout the narrative.
    """
    if not (1 <= intensity_before <= 5 and 1 <= intensity_after <= 5):
        raise ValueError("Intensities must be between 1 and 5")

    timestamp = _timestamp()
    cursor = conn.execute(
        """
        INSERT INTO theme_evolution
            (entity_id, theme_id, intensity_before, intensity_after, scene_id, chapter_id, context, recorded_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (entity_id, theme_id, intensity_before, intensity_after, scene_id, chapter_id, context, timestamp),
    )
    conn.commit()
    return int(cursor.lastrowid)


def get_theme_evolution(
    conn: sqlite3.Connection,
    entity_id: int,
    theme_id: Optional[int] = None,
) -> list[tuple[ThemeEvolution, Theme]]:
    """
    Get the theme evolution history for an entity.

    Returns list of (ThemeEvolution, Theme) tuples ordered by recorded_at.
    """
    if theme_id:
        rows = conn.execute(
            """
            SELECT te.id, te.entity_id, te.theme_id, te.intensity_before, te.intensity_after,
                   te.scene_id, te.chapter_id, te.context, te.recorded_at,
                   t.id, t.name, t.description, t.created_at, t.updated_at
            FROM theme_evolution te
            JOIN themes t ON te.theme_id = t.id
            WHERE te.entity_id = ? AND te.theme_id = ?
            ORDER BY te.recorded_at
            """,
            (entity_id, theme_id),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT te.id, te.entity_id, te.theme_id, te.intensity_before, te.intensity_after,
                   te.scene_id, te.chapter_id, te.context, te.recorded_at,
                   t.id, t.name, t.description, t.created_at, t.updated_at
            FROM theme_evolution te
            JOIN themes t ON te.theme_id = t.id
            WHERE te.entity_id = ?
            ORDER BY te.recorded_at
            """,
            (entity_id,),
        ).fetchall()

    return [
        (ThemeEvolution(*row[:9]), Theme(*row[9:]))
        for row in rows
    ]


# =============================================================================
# QUERY HELPERS
# =============================================================================


def find_entities_sharing_palette(conn: sqlite3.Connection, palette_id: int) -> list[tuple[int, str, str]]:
    """
    Find all entities that share a specific palette.

    Useful for finding characters with visual connections.
    Returns list of (entity_id, entity_name, entity_type) tuples.
    """
    rows = conn.execute(
        """
        SELECT DISTINCT e.id, e.name, e.type
        FROM entity_palettes ep
        JOIN entities e ON ep.entity_id = e.id
        WHERE ep.palette_id = ?
        ORDER BY e.type, e.name
        """,
        (palette_id,),
    ).fetchall()
    return [(row[0], row[1], row[2]) for row in rows]


def find_entities_sharing_theme(conn: sqlite3.Connection, theme_id: int) -> list[tuple[int, str, str, int]]:
    """
    Find all entities that share a specific theme.

    Useful for finding characters with thematic connections.
    Returns list of (entity_id, entity_name, entity_type, intensity) tuples.
    """
    rows = conn.execute(
        """
        SELECT e.id, e.name, e.type, et.intensity
        FROM entity_themes et
        JOIN entities e ON et.entity_id = e.id
        WHERE et.theme_id = ?
        ORDER BY et.intensity DESC, e.type, e.name
        """,
        (theme_id,),
    ).fetchall()
    return [(row[0], row[1], row[2], row[3]) for row in rows]


def get_entity_color_profile(conn: sqlite3.Connection, entity_id: int) -> dict:
    """
    Get complete color profile for an entity.

    Returns dict with:
        - entity: (id, name, type)
        - palettes: list of {palette, colors, context}
        - themes: list of {theme, intensity}
        - connections: list of {entity, relationship}
        - palette_history: list of evolution records
        - theme_history: list of evolution records
    """
    # Get entity info
    entity_row = conn.execute(
        "SELECT id, name, type FROM entities WHERE id = ?",
        (entity_id,),
    ).fetchone()

    if not entity_row:
        return {}

    # Get palettes with colors
    palettes = []
    for ep, palette in get_entity_palettes(conn, entity_id):
        colors = get_palette_colors(conn, palette.id)
        palettes.append({
            "palette": palette,
            "colors": colors,
            "context": ep.context,
            "notes": ep.notes,
        })

    # Get themes
    themes = []
    for et, theme in get_entity_themes(conn, entity_id):
        themes.append({
            "theme": theme,
            "intensity": et.intensity,
            "notes": et.notes,
        })

    # Get connections
    connections = []
    for ec, other_id, other_name in get_entity_connections(conn, entity_id):
        connections.append({
            "entity_id": other_id,
            "entity_name": other_name,
            "relationship": ec.relationship_type,
            "description": ec.description,
            "bidirectional": ec.bidirectional,
        })

    # Get evolution histories
    palette_history = get_palette_evolution(conn, entity_id)
    theme_history = get_theme_evolution(conn, entity_id)

    return {
        "entity": {"id": entity_row[0], "name": entity_row[1], "type": entity_row[2]},
        "palettes": palettes,
        "themes": themes,
        "connections": connections,
        "palette_history": palette_history,
        "theme_history": theme_history,
    }


# =============================================================================
# CONVENIENCE: Connect using db_path
# =============================================================================


def with_connection(db_path: Path):
    """
    Decorator/context manager for database operations.

    Usage:
        with with_connection(db_path) as conn:
            create_palette(conn, "Elara's Magic", ...)
    """
    class ConnectionContext:
        def __init__(self, path: Path):
            self.path = path
            self.conn: Optional[sqlite3.Connection] = None

        def __enter__(self) -> sqlite3.Connection:
            self.conn = sqlite3.connect(self.path, timeout=5)
            init_palette_theme_tables(self.conn)
            self.conn.commit()
            return self.conn

        def __exit__(self, exc_type, exc_val, exc_tb):
            if self.conn:
                self.conn.close()

    return ConnectionContext(db_path)
