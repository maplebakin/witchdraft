-- WitchDraft Palette & Theme Schema Extension
-- Extends vault.db to support character/theme/color connections

-- =============================================================================
-- PALETTES: Store reusable color palette definitions
-- =============================================================================

CREATE TABLE IF NOT EXISTS palettes (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(name)
);

-- Individual colors within a palette
CREATE TABLE IF NOT EXISTS palette_colors (
    id INTEGER PRIMARY KEY,
    palette_id INTEGER NOT NULL,
    hex_code TEXT NOT NULL,          -- e.g., "#6BBF9B"
    color_name TEXT,                  -- e.g., "Primary", "Accent", "Shadow"
    position INTEGER NOT NULL,        -- ordering within palette (0-indexed)
    created_at TEXT NOT NULL,
    FOREIGN KEY(palette_id) REFERENCES palettes(id) ON DELETE CASCADE,
    UNIQUE(palette_id, position)
);

-- =============================================================================
-- THEMES: Store thematic associations (redemption, loss, growth, etc.)
-- =============================================================================

CREATE TABLE IF NOT EXISTS themes (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(name)
);

-- =============================================================================
-- ENTITY-PALETTE ASSOCIATIONS
-- =============================================================================

-- Link entities to palettes with context (why this palette?)
CREATE TABLE IF NOT EXISTS entity_palettes (
    id INTEGER PRIMARY KEY,
    entity_id INTEGER NOT NULL,
    palette_id INTEGER NOT NULL,
    context TEXT NOT NULL DEFAULT 'general',  -- e.g., "costume", "magic", "mood", "aura"
    notes TEXT,
    assigned_at TEXT NOT NULL,
    FOREIGN KEY(entity_id) REFERENCES entities(id) ON DELETE CASCADE,
    FOREIGN KEY(palette_id) REFERENCES palettes(id) ON DELETE CASCADE,
    UNIQUE(entity_id, palette_id, context)
);

-- =============================================================================
-- ENTITY-THEME ASSOCIATIONS
-- =============================================================================

-- Link entities to themes with intensity and notes
CREATE TABLE IF NOT EXISTS entity_themes (
    id INTEGER PRIMARY KEY,
    entity_id INTEGER NOT NULL,
    theme_id INTEGER NOT NULL,
    intensity INTEGER NOT NULL DEFAULT 3 CHECK(intensity BETWEEN 1 AND 5),  -- 1=subtle, 5=dominant
    notes TEXT,
    assigned_at TEXT NOT NULL,
    FOREIGN KEY(entity_id) REFERENCES entities(id) ON DELETE CASCADE,
    FOREIGN KEY(theme_id) REFERENCES themes(id) ON DELETE CASCADE,
    UNIQUE(entity_id, theme_id)
);

-- =============================================================================
-- ENTITY CONNECTIONS: Relationships between entities
-- =============================================================================

CREATE TABLE IF NOT EXISTS entity_connections (
    id INTEGER PRIMARY KEY,
    entity_a_id INTEGER NOT NULL,
    entity_b_id INTEGER NOT NULL,
    relationship_type TEXT NOT NULL,  -- e.g., "ally", "enemy", "family", "mentor", "romantic"
    description TEXT,
    bidirectional INTEGER NOT NULL DEFAULT 1,  -- 1=mutual, 0=directional (A->B)
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(entity_a_id) REFERENCES entities(id) ON DELETE CASCADE,
    FOREIGN KEY(entity_b_id) REFERENCES entities(id) ON DELETE CASCADE,
    UNIQUE(entity_a_id, entity_b_id, relationship_type),
    CHECK(entity_a_id != entity_b_id)
);

-- =============================================================================
-- PALETTE EVOLUTION: Track how palettes change as characters develop
-- =============================================================================

-- Records palette changes at specific story points
CREATE TABLE IF NOT EXISTS palette_evolution (
    id INTEGER PRIMARY KEY,
    entity_id INTEGER NOT NULL,
    palette_id INTEGER NOT NULL,
    scene_id INTEGER,                 -- nullable: palette shift at specific scene
    chapter_id INTEGER,               -- nullable: palette shift at chapter level
    context TEXT NOT NULL,            -- what triggered this evolution
    recorded_at TEXT NOT NULL,
    FOREIGN KEY(entity_id) REFERENCES entities(id) ON DELETE CASCADE,
    FOREIGN KEY(palette_id) REFERENCES palettes(id) ON DELETE CASCADE,
    FOREIGN KEY(scene_id) REFERENCES scenes(id) ON DELETE SET NULL,
    FOREIGN KEY(chapter_id) REFERENCES chapters(id) ON DELETE SET NULL
);

-- =============================================================================
-- THEME EVOLUTION: Track thematic shifts through the narrative
-- =============================================================================

CREATE TABLE IF NOT EXISTS theme_evolution (
    id INTEGER PRIMARY KEY,
    entity_id INTEGER NOT NULL,
    theme_id INTEGER NOT NULL,
    intensity_before INTEGER NOT NULL CHECK(intensity_before BETWEEN 1 AND 5),
    intensity_after INTEGER NOT NULL CHECK(intensity_after BETWEEN 1 AND 5),
    scene_id INTEGER,
    chapter_id INTEGER,
    context TEXT NOT NULL,            -- what caused the shift
    recorded_at TEXT NOT NULL,
    FOREIGN KEY(entity_id) REFERENCES entities(id) ON DELETE CASCADE,
    FOREIGN KEY(theme_id) REFERENCES themes(id) ON DELETE CASCADE,
    FOREIGN KEY(scene_id) REFERENCES scenes(id) ON DELETE SET NULL,
    FOREIGN KEY(chapter_id) REFERENCES chapters(id) ON DELETE SET NULL
);

-- =============================================================================
-- INDEXES for query performance
-- =============================================================================

CREATE INDEX IF NOT EXISTS idx_palette_colors_palette ON palette_colors(palette_id);
CREATE INDEX IF NOT EXISTS idx_entity_palettes_entity ON entity_palettes(entity_id);
CREATE INDEX IF NOT EXISTS idx_entity_palettes_palette ON entity_palettes(palette_id);
CREATE INDEX IF NOT EXISTS idx_entity_themes_entity ON entity_themes(entity_id);
CREATE INDEX IF NOT EXISTS idx_entity_themes_theme ON entity_themes(theme_id);
CREATE INDEX IF NOT EXISTS idx_entity_connections_a ON entity_connections(entity_a_id);
CREATE INDEX IF NOT EXISTS idx_entity_connections_b ON entity_connections(entity_b_id);
CREATE INDEX IF NOT EXISTS idx_palette_evolution_entity ON palette_evolution(entity_id);
CREATE INDEX IF NOT EXISTS idx_theme_evolution_entity ON theme_evolution(entity_id);

-- =============================================================================
-- ENHANCED SHADOW BIBLE TABLES
-- These tables store rich semantic extraction from narrative text
-- =============================================================================

-- Enhanced traits with category, source context, and confidence scores
CREATE TABLE IF NOT EXISTS enhanced_traits (
    id INTEGER PRIMARY KEY,
    entity_id INTEGER NOT NULL,
    trait TEXT NOT NULL,
    category TEXT NOT NULL,           -- "personality", "emotion", "physical", "archetype"
    source_text TEXT,                 -- The sentence/clause it was extracted from
    confidence REAL DEFAULT 1.0,      -- Extraction confidence (0.0-1.0)
    scene_id INTEGER,
    recorded_at TEXT NOT NULL,
    FOREIGN KEY(entity_id) REFERENCES entities(id) ON DELETE CASCADE,
    FOREIGN KEY(scene_id) REFERENCES scenes(id) ON DELETE SET NULL
);

-- Color hints extracted from descriptive language
CREATE TABLE IF NOT EXISTS entity_color_hints (
    id INTEGER PRIMARY KEY,
    entity_id INTEGER NOT NULL,
    color_family TEXT NOT NULL,       -- "red", "blue", "green", "purple", etc.
    trigger_words TEXT NOT NULL,      -- Comma-separated words that suggested this color
    weight REAL NOT NULL,             -- How strongly this color is suggested (0.0-1.0)
    scene_id INTEGER,
    recorded_at TEXT NOT NULL,
    FOREIGN KEY(entity_id) REFERENCES entities(id) ON DELETE CASCADE,
    FOREIGN KEY(scene_id) REFERENCES scenes(id) ON DELETE SET NULL
);

-- Scene atmosphere classifications
CREATE TABLE IF NOT EXISTS scene_atmospheres (
    id INTEGER PRIMARY KEY,
    scene_id INTEGER NOT NULL,
    atmosphere TEXT NOT NULL,         -- "ominous", "serene", "chaotic", "magical", etc.
    recorded_at TEXT NOT NULL,
    FOREIGN KEY(scene_id) REFERENCES scenes(id) ON DELETE CASCADE,
    UNIQUE(scene_id, atmosphere)
);

-- Additional indexes for enhanced tables
CREATE INDEX IF NOT EXISTS idx_enhanced_traits_entity ON enhanced_traits(entity_id);
CREATE INDEX IF NOT EXISTS idx_enhanced_traits_category ON enhanced_traits(category);
CREATE INDEX IF NOT EXISTS idx_entity_color_hints_entity ON entity_color_hints(entity_id);
CREATE INDEX IF NOT EXISTS idx_entity_color_hints_color ON entity_color_hints(color_family);
CREATE INDEX IF NOT EXISTS idx_scene_atmospheres_scene ON scene_atmospheres(scene_id);
