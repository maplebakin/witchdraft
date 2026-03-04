# WitchDraft Project Overview

## Purpose
WitchDraft is a local-first, distraction-free writing app built with Python and PyQt6. It keeps all data offline, tracks narrative entities, and provides lightweight visualizations to support story structure.

## Main Features (PyQt6 App)
- Sanctuary Shell UI with a frameless window and custom draggable title bar.
- Hearth editor with typewriter margins and serif typography.
- Focus "breathe" effect that fades controls while typing.
- Slow pulsing cursor animation.
- Project manager for creating/switching projects.
- Chapter and storyline panels for organizing the manuscript.
- Library/Index dialog for chapter metadata and filtering.
- Voice inbox ingestion to turn notes into chapters.
- Markdown/PDF export from the GUI.
- Shadow Bible scanning via spaCy (`en_core_web_sm`) every 5 minutes.
  - Extracts `PERSON` and `GPE` entities.
  - Stores entities, scenes, and traits in `vault.db`.
- Floating Echo label that appears in the margin with recent traits.
- Spiral Constellation view:
  - QGraphicsView spiral layout of scenes.
  - Draws curved "Seams" between scenes with 2+ shared entities.
  - Dockable panel with zoom, pan, and draggable nodes.

## Package App (src/witchdraft)
- `src/witchdraft/app.py` provides the PyQt6 GUI:
  - Custom title bar and focus fade logic.
  - QTextEdit writing surface with line spacing and margins.
  - Background spaCy scanning thread and SQLite persistence.
  - Project selection with per-project chapter files.
  - Dockable Constellation panel for the scene map.
  - Export actions for Markdown/PDF (ReportLab for PDF).

## Key Data Files
- `vault.db`: local SQLite database for entities/scenes/traits.
- `.compost/`: hidden folder of deleted text fragments.

## Notes
- spaCy runs locally; no network is required after model install.
- All UI is desktop-based via PyQt6.
