# Master Refactor Prompt Playbook (WitchDraft)

This file is a copy/paste guide for non-coders.

How to use:
1. Open your coding LLM in the WitchDraft repository.
2. Copy one prompt at a time from this file.
3. Wait for it to finish and verify results before moving to the next prompt.
4. Do not skip prompts.

Important rule for every prompt:
- Tell the LLM to make changes directly in files, run checks, and summarize results with file paths.
- Tell it to stop and report if blocked.

---

## Prompt 0: Safety Setup + Baseline Snapshot

```text
You are in the WitchDraft repo root. Create a baseline snapshot and audit report before refactoring.

Tasks:
1. Run these commands and summarize results:
   - git status --short
   - rg --files
   - python3 -m compileall -q src/witchdraft
   - python3 -m unittest discover -s tests -p 'test_*.py' -v
2. Write a file named refactor_baseline_report.md with:
   - Current failures
   - Current test status
   - High-risk files by size/complexity
3. Do not change code yet.

Output requirements:
- Show a concise summary and list all created/modified files.
```

---

## Prompt 1: Unbreak Test Discovery and Runtime Baseline

```text
Fix baseline breakages so the project has a runnable minimum test baseline.

Context:
- hearth.py currently has an indentation/syntax problem.
- tests/test_split_scenes.py imports from hearth.py and fails test discovery.
- Current product direction is PyQt GUI under src/witchdraft, not old Textual hearth.py.

Tasks:
1. Fix syntax errors that block imports.
2. Refactor tests/test_split_scenes.py to test the active implementation in src/witchdraft (not legacy hearth.py), or replace it with equivalent tests for src/witchdraft logic.
3. Ensure tests can run with:
   - python3 -m unittest discover -s tests -p 'test_*.py' -v
4. If pytest is not configured, do not require it yet.
5. Add or adjust tests so at least scene splitting behavior is validated in active code paths.

Verification:
- Run compile and unittest commands.
- Report pass/fail counts.

Output requirements:
- Show exact files changed and why.
```

---

## Prompt 2: Documentation + Packaging Truth Alignment

```text
Align packaging metadata and docs with the actual product behavior.

Known mismatch:
- pyproject.toml description still says Textual CLI.
- README describes PyQt GUI and disabled CLI/TUI paths.

Tasks:
1. Update pyproject.toml metadata to reflect the real GUI-first product.
2. Update README.md to include:
   - Actual launch path
   - Optional dependencies (spacy/reportlab)
   - Current testing command(s)
   - Current architecture status (legacy files if still present)
3. Add a new docs/ARCHITECTURE_STATUS.md that clearly states:
   - Active code paths
   - Legacy/deprecated code paths
   - Planned direction
4. Do not add marketing text. Keep it factual.

Verification:
- Show diffs summary.
- Run a quick import/compile check.
```

---

## Prompt 3: Extract Shared Utility Layer and Remove Duplication

```text
Create a shared utility module to remove duplicated logic across app.py, hearth.py, and scripts/build_index.py.

Duplication targets:
- frontmatter parsing
- slugify
- compost move helper
- friendly title
- created/sequence parsing
- index entry collection helpers

Tasks:
1. Create src/witchdraft/core/io_utils.py (or a similarly named core module).
2. Move shared pure functions there.
3. Update callers in:
   - src/witchdraft/app.py
   - scripts/build_index.py
   - src/witchdraft/export.py if applicable
4. For legacy hearth.py:
   - Either rewire to shared utilities or mark deprecated with minimal wrapper behavior.
5. Keep behavior identical unless fixing obvious bugs.

Verification:
- Run tests and compile checks.
- Confirm no duplicated implementations remain for those helpers.

Output requirements:
- Show before/after duplication map.
```

---

## Prompt 4: Introduce Service-Oriented App Structure

```text
Refactor monolithic src/witchdraft/app.py into services without changing user-facing behavior.

Goal:
- Keep PyQt UI working, but move business logic into testable modules.

Create modules:
1. src/witchdraft/services/document_service.py
2. src/witchdraft/services/index_service.py
3. src/witchdraft/services/analysis_service.py
4. src/witchdraft/services/export_service.py
5. src/witchdraft/services/project_service.py

Tasks:
1. Move logic from app.py to services in small safe increments.
2. Keep HearthWindow as orchestration/UI only.
3. Add type hints and concise docstrings.
4. Add unit tests for each new service module.
5. Keep backward-compatible behavior for current menus and actions.

Verification:
- Run all tests.
- Run compile check.
- Confirm app entrypoint still launches.

Output requirements:
- List moved methods and new module ownership.
```

---

## Prompt 5: Database Integrity + Migration System

```text
Implement robust SQLite schema management with migrations and foreign key enforcement.

Problems to solve:
- CREATE TABLE IF NOT EXISTS only; no schema versioning.
- Foreign keys declared but not consistently enforced.

Tasks:
1. Add a migration system:
   - src/witchdraft/db/migrations/
   - src/witchdraft/db/migrate.py
2. Track schema version in DB (pragma user_version or schema_version table).
3. Ensure every sqlite connection enables:
   - PRAGMA foreign_keys = ON
4. Move schema init from ad hoc app startup to migration runner.
5. Add migration tests:
   - fresh DB
   - older DB upgrade path
6. Keep existing user data safe during upgrade.

Verification:
- Run migration tests and standard tests.
- Demonstrate foreign key enforcement with a small automated test case.

Output requirements:
- Show migration files added and current latest schema version.
```

---

## Prompt 6: Error Handling and Observability Pass

```text
Replace silent exception swallowing with structured, actionable error handling.

Known issue:
- constellation_enhanced.py has many 'except sqlite3.OperationalError: pass' blocks.

Tasks:
1. Replace silent pass patterns with:
   - user-safe fallback behavior
   - debug-level logging containing table/query context
2. Add a lightweight logging setup module:
   - src/witchdraft/logging_config.py
3. Ensure GUI messages remain friendly while logs keep technical details.
4. Add tests for failure paths where practical.

Verification:
- Simulate missing optional tables and show graceful behavior.
- Confirm no silent pass remains in critical data-loading paths.

Output requirements:
- Report which silent handlers were replaced.
```

---

## Prompt 7: Autosave Durability + Recovery Journal

```text
Add crash-safe document durability features.

Tasks:
1. Implement debounced autosave (not every keystroke write).
2. Add write-ahead recovery journal for unsaved editor buffer states.
3. On app start, detect recovery candidates and prompt restore.
4. Keep chapter files as canonical source, but ensure minimal data loss on crash.
5. Add tests for:
   - autosave debounce behavior
   - recovery detection
   - restore flow

Verification:
- Show simulated crash/restart recovery test result.

Output requirements:
- List new files and where recovery data is stored.
```

---

## Prompt 8: Incremental Analysis Pipeline (No Full Rebuild Scans)

```text
Refactor NLP analysis from full-project destructive scans to incremental chapter-based updates.

Current issue:
- periodic scans rebuild scene tables from whole manuscript text.

Tasks:
1. Track per-chapter hash/updated_at to detect changed content.
2. Re-scan only changed chapters.
3. Preserve stable scene/chapter mapping IDs where possible.
4. Avoid deleting all scene rows on each scan.
5. Add a manual "full reindex" action for explicit rebuild.
6. Add integration tests validating incremental updates.

Verification:
- Demonstrate:
   - first full scan
   - second run with no changes does minimal/no work
   - one chapter change updates only related records

Output requirements:
- Show data model changes and migration needs if any.
```

---

## Prompt 9: Test Suite Expansion + CI

```text
Build a robust test and quality gate pipeline.

Tasks:
1. Add test structure:
   - tests/unit/
   - tests/integration/
2. Add tests for:
   - project lifecycle
   - chapter create/delete + compost behavior
   - exports
   - index build
   - migration behavior
3. Add lint/type checks (ruff + mypy or pyright) with minimal practical config.
4. Add GitHub Actions CI workflow to run:
   - compile/import checks
   - unit + integration tests
   - lint/type checks
5. Ensure CI does not require GUI display for non-UI tests.

Verification:
- Show local command set and expected outputs.
- Provide the final CI workflow file path.
```

---

## Prompt 10: Search and Document Navigation Foundation

```text
Add robust document creation capabilities focused on retrieval and structure.

Tasks:
1. Implement SQLite FTS5 full-text search index over chapters/scenes.
2. Add UI search panel with:
   - query box
   - result list
   - open-to-chapter jump
3. Add outline navigation:
   - heading hierarchy per chapter
   - click-to-jump in editor
4. Add tests for search indexing and query correctness.

Verification:
- Demonstrate search for a sample phrase returns expected chapter/scene.

Output requirements:
- List new DB tables/indexes and UI entry points.
```

---

## Prompt 11: Export Pipeline Hardening

```text
Refactor and harden export behavior for reliable manuscript output.

Tasks:
1. Ensure export logic lives in service layer (not UI event handlers).
2. Add deterministic chapter ordering and clean heading handling.
3. Improve PDF export error messaging and optional font handling.
4. Add export tests for markdown and pdf code paths (mock reportlab where needed).
5. Add pre-export validation summary:
   - missing chapter files
   - empty chapters
   - duplicate sequence metadata

Verification:
- Run export tests and show sample output paths.

Output requirements:
- Show exported structure contract in docs.
```

---

## Prompt 12: Final Hardening + Release Readiness

```text
Perform a final production-readiness pass and generate release docs.

Tasks:
1. Run full test/lint/type/compile pipeline.
2. Run a structured code review for:
   - data integrity
   - error handling
   - concurrency/threading safety
   - backward compatibility
3. Create docs/RELEASE_READINESS.md with:
   - completed checklist
   - known risks
   - deferred items
4. Create docs/REFRACTOR_CHANGELOG.md summarizing all major refactor changes by module.
5. Provide a final "operator runbook" with exact commands for:
   - setup
   - launch
   - tests
   - migration
   - troubleshooting

Verification:
- Include final command outputs summary and pass/fail status.

Output requirements:
- No placeholder TODO sections in release docs.
```

---

## Optional Prompt: Legacy Cleanup (After Everything Passes)

```text
Now that the refactor is stable, remove or quarantine legacy code paths safely.

Tasks:
1. Identify legacy files not used by current app runtime.
2. Move them to a clearly marked legacy/ folder or remove them if confirmed unused.
3. Update docs to reflect final architecture.
4. Re-run full test and quality pipeline.

Safety rules:
- Do not remove anything unless usage is verified by search/import checks.
- Keep a clear changelog entry for each removed/moved file.
```

