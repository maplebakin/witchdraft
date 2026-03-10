# WitchDraft

Local-first, file-native writing sanctuary with a PyQt6 GUI.

## Requirements
- Python 3.10+
- `PyQt6` (GUI app)
- Optional: `spacy` with the `en_core_web_sm` model (Shadow Bible / entity scan)
- Optional: `reportlab` for PDF export

## Build / Install (no compile step)
GUI app:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Optional Shadow Bible model for local entity scanning:
```bash
pip install -e .[spacy]
python -m spacy download en_core_web_sm
```

GUI app with Shadow Bible (installs spaCy):
```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[spacy]
python -m spacy download en_core_web_sm
```

Optional PDF support:
```bash
pip install -e .[pdf]
```

## Launch
```bash
python -m witchdraft
```

Single entry point (recommended):
```bash
witchdraft
```

Default behavior:
- `witchdraft` always launches the GUI.
- CLI/TUI entry points are disabled.

Key controls:
- Project button opens the project manager (create/switch projects).
- Constellation button (or `Ctrl+M`) toggles the dockable Spiral Constellation panel.
- Actions menu includes Library/Index, Ingest Voice Notes, and export options.
- Scroll to zoom, drag to pan, drag nodes to rearrange the map.

Projects:
- Stored under `~/WitchDraftProjects/`
- Each project contains `vault.db` and a `chapters/` folder of Markdown files
- Chapters are individual `.md` files; storylines are tags linked per chapter

## Export
Use the Actions menu in the GUI to export Markdown or PDF (optional custom font).

## Files and Data
- `vault.db`: local SQLite entity/scene vault per project
- `.compost/`: deleted text fragments
