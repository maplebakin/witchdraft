# WitchDraft PRD (Technical Specification)

## Overview
WitchDraft is a local-first, distraction-free writing app built with a PyQt6 GUI. It uses spaCy for offline entity tracking and SQLite as a relational "Constellation" map to connect scenes, characters, and places. The goal is to provide a calm writing environment with powerful, private metadata extraction and minimal UI distractions.

## Goals
- Provide a focused, minimalist writing experience on desktop.
- Track narrative entities offline via spaCy without network access.
- Store and query a relational "Constellation" of entities and scene links in SQLite.
- Offer safe deletion via a hidden "Compost Bin".
- Visualize narrative structure via a "Spiral Timeline" graph.

## Non-Goals
- No cloud sync or external services.
- No collaborative editing.
- No web-based UI.

## Target Environment
- Python 3.10+
- PyQt6 (GUI)
- Optional: spaCy (offline model)
- SQLite (bundled, local DB)
- OS: macOS, Linux, Windows

---

## Functional Requirements

### 1) Hearth UI (Minimalist Writing Surface)

**Purpose:** The Hearth is the primary writing space. It must feel calm, focused, and visually distinct, with minimal UI chrome.

**Key UI Characteristics:**
- Single-pane editor view with optional status line.
- Minimal UI elements; avoid borders unless they clarify focus.
- A pulsing cursor to emphasize the live writing focus.
- Custom hex color palette (no defaults).

**Requirements:**
- **Layout:**
  - Full-screen editor area.
  - Optional single-line status bar at bottom with word count, file name, and mode.
  - No sidebars by default.
- **Cursor:**
  - Must animate (pulse in brightness) at a steady rhythm.
  - Pulse speed: 1.2-1.6 seconds per cycle.
- Pulse behavior implemented via a QTimer and cursor updates.
- **Color Palette (Custom Hex):**
  - Background: `#E6E5E6`
  - Foreground text: `#2B2B2B`
  - Cursor (active): `#BCA67A`
  - Cursor (dim): `#DED3BF`
  - Status line: `#D2D0CD`
  - Accent (links/metadata hints): `#6BBF9B`

**PyQt6 Implementation Notes:**
- Use `QTextEdit` for primary text editing.
- Use `QTimer` for cursor pulsing and UI rhythm.
- No visible scrollbars unless user explicitly enables.

---

### 2) Shadow Bible Logic (Entity Extraction and DB Sync)

**Purpose:** The Shadow Bible is a background process that parses user text locally to extract names, traits, and other narrative entities, storing them in SQLite.

**Entity Types:**
- Characters (PERSON)
- Places (GPE)
- (Optional future) Organizations (ORG) and other custom tags

**Flow Requirements:**
1. On save or manual trigger, run spaCy pipeline over the current document or changed portions.
2. Extract named entities and normalize them (case folding, whitespace trimming).
3. Store entities in SQLite with a "last seen" timestamp.
4. Link extracted entities to the current scene entry.

**spaCy Requirements:**
- Offline model required (e.g., `en_core_web_sm` or packaged custom).
- Text must not leave local machine.
- Configured pipeline only needs NER and tokenization.

**Suggested spaCy Extraction Snippet (Specification-Level):**
```python
import spacy

nlp = spacy.load("en_core_web_sm")
doc = nlp(text)

entities = []
for ent in doc.ents:
    if ent.label_ in {"PERSON", "GPE"}:
        entities.append((ent.text.strip(), ent.label_))
```

**SQLite Schema (Constellation Map Core):**
- `entities`
  - `id` INTEGER PRIMARY KEY
  - `name` TEXT UNIQUE
  - `type` TEXT
  - `last_seen` DATETIME
- `scenes`
  - `id` INTEGER PRIMARY KEY
  - `title` TEXT
  - `position` INTEGER
  - `updated_at` DATETIME
- `scene_entities`
  - `scene_id` INTEGER
  - `entity_id` INTEGER
  - `count` INTEGER
  - PRIMARY KEY (`scene_id`, `entity_id`)
- `traits`
  - `id` INTEGER PRIMARY KEY
  - `entity_id` INTEGER
  - `trait` TEXT
  - `recorded_at` DATETIME

**Shadow Bible Rules:**
- Deduplicate by case-insensitive name.
- Maintain counts of entity appearances per scene.
- Allow user to manually "pin" entities with custom metadata later (not part of this PRD).

---

### 3) Compost Bin (Soft-Delete System)

**Purpose:** The Compost Bin is a hidden folder where deleted text or files are stored instead of being permanently removed.

**Behavior:**
- Deleting a file moves it to `.compost/` in the project root.
- Delete action should preserve file name plus timestamp.
- `.compost/` is hidden by prefix and must not clutter UI.

**Requirements:**
- On deletion, move to:
  `PROJECT_ROOT/.compost/<timestamp>__<original_filename>`
- If the folder doesn't exist, create it.
- If collision occurs, append a suffix counter.
- Provide a "restore" command later (not in scope to implement now).

**Example Naming:**
- Original: `chapter-03.md`
- Composted: `.compost/2025-01-14T22-41-03__chapter-03.md`

---

### 4) Spiral Timeline (Graph of Connected Scenes)

**Purpose:** The Spiral Timeline is a conceptual and visual representation of scenes and how they connect via shared entities. It is not a timeline view but a graph-based "spiral" map where nodes represent scenes.

**Data Inputs:**
- Scene list (files or saved entries)
- Scene-entity relationship table

**Graph Logic:**
- Nodes = scenes
- Edge weight = number of shared entities between two scenes
- Only draw edges above a configurable threshold (e.g., 2 shared entities)

**Spiral Layout Requirements:**
- Arrange scenes in a spiral order by `created_at` or `scene index`.
- Scene positions computed by polar coordinates:
  - `r = a + b * t`
  - `theta = t`
  - `t` = normalized scene index
- Connect nodes with weighted lines (heavier for more shared entities).

**Data Output Requirements (for Constellation rendering):**
- Return list of nodes: `id`, `x`, `y`, `label`
- Return list of edges: `source_id`, `target_id`, `weight`

**Rendering Notes:**
- Use curved seams between nodes with lightweight styling.
- Use concise labels for nodes.
- Provide a quick toggle to show/hide the map.

---

## User Stories (Technical-Focused)
- As a writer, I want the cursor to pulse so I can keep my attention anchored.
- As a writer, I want entities to be tracked offline so I can explore my narrative structure without exposing my text.
- As a writer, I want deletions to feel safe and reversible.
- As a writer, I want a visual map of scenes based on shared elements.

---

## Data Persistence
- All data stored locally.
- SQLite DB stored at: `PROJECT_ROOT/vault.db` (GUI projects use `~/WitchDraftProjects/<project>/vault.db`).
- .compost stored at: `PROJECT_ROOT/.compost/`

---

## Error Handling and Edge Cases
- spaCy model missing -> show user prompt to install local model.
- DB locked -> retry and warn, do not crash.
- Composted file exists -> auto-append suffix.
- Huge document -> allow incremental parse (future enhancement).

---

## Open Questions
- Should the Hearth allow inline annotations from the Shadow Bible?
- Should Spiral Timeline allow manual links not derived from entities?
- Should entity types be user-extendable (e.g., "artifact", "spell")?

---

## Out of Scope (for this PRD)
- Plugin system.
- Cloud sync.
- Multi-user collaboration.
