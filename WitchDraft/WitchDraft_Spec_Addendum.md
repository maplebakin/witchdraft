# WitchDraft PRD Addendum — Sparks, Companion Doc, and Exhale

## Overview

This addendum extends the WitchDraft PRD with three new features designed to support neurodivergent writing workflows. All three features are local-first, distraction-minimal, and use WitchDraft's existing vocabulary and aesthetic. None require network access. All data is stored in the existing `vault.db` per project.

The three features are:

- **Sparks** — a daily session intention list (up to 5 items) with earnable completions
- **Companion Doc** — a keystroke-triggered throw-forward note system that captures fix-it thoughts without breaking Hearth focus
- **Exhale** — a session word count target set intentionally before writing begins

---

## Goals

- Provide session initiation scaffolding for writers who struggle with starting
- Allow forward-momentum writing by capturing fix-it thoughts without backtracking
- Give writers an intentional, self-chosen word target that feels like release rather than pressure
- Integrate visually and linguistically with WitchDraft's existing aesthetic (Hearth, Shadow Bible, Compost, Constellation)

## Non-Goals

- No gamification beyond simple completion state
- No streak tracking, scoring, or external accountability
- No syncing, sharing, or notifications
- Sparks are not a project management system — they are session-scoped intentions only

---

## 1) Sparks

### Purpose

Sparks is a lightweight daily intention panel. Before or during a writing session, the writer sets up to 5 small, achievable tasks. Completing each Spark triggers a satisfying visual response. The goal is to give the ADHD/AuDHD brain a series of winnable micro-goals rather than one daunting macro-goal.

Sparks persist per project per day. Starting a new day clears completed Sparks and allows fresh ones to be set.

### UI Behavior

- Accessible via a **Sparks button** in the title bar or Actions menu, and via keyboard shortcut `Ctrl+Shift+S`
- Opens as a **dockable panel** (same pattern as the Constellation panel) or a **lightweight floating overlay** — implement whichever integrates more cleanly with existing dock architecture
- Panel contains:
  - Up to **5 editable text fields** for intention items
  - Each field has a **completion toggle** (click or checkbox) to its left
  - When toggled complete, the item text dims and a **small flame/spark animation** plays (subtle, 0.5–0.8 second CSS/QPainter animation — a brief brightness flare on the toggle icon)
  - A **progress indicator** at the bottom shows e.g. `3 / 5 sparked` in muted accent text
- Sparks panel should respect the Hearth's **focus fade** behavior — when the user is actively typing in the Hearth, the Sparks panel fades to low opacity if it is visible, same as other UI chrome
- Empty fields are hidden on render if not yet filled — only show filled fields and one empty field below them (expandable up to 5)

### Data

Add the following table to `vault.db`:

```sql
CREATE TABLE IF NOT EXISTS sparks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT NOT NULL,
    date TEXT NOT NULL,               -- ISO date string YYYY-MM-DD
    position INTEGER NOT NULL,        -- 1 through 5
    text TEXT NOT NULL,
    completed INTEGER NOT NULL DEFAULT 0,  -- 0 or 1
    completed_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

- `project_id` matches the existing project identifier used in the rest of vault.db
- On app launch or project switch, load today's Sparks for the current project
- On a new calendar day, previous Sparks are archived (retained in DB, not deleted) and a fresh set can be entered
- Do not auto-clear Sparks mid-session — only clear on new day

### Rules

- Maximum 5 Sparks per day per project
- Sparks can be edited until completed — once completed they are locked
- Completed state persists across app restarts for the current day
- No required fields — Sparks are optional. If the writer opens the Hearth without setting any Sparks, nothing prompts or warns them

---

## 2) Companion Doc

### Purpose

The Companion Doc is a parallel capture layer that runs alongside the Hearth. While writing, the writer will notice things that need fixing — a plot hole in chapter 2, a character who needs to be introduced earlier, a line of dialogue that isn't landing. The natural impulse is to stop and fix it immediately, breaking forward momentum.

The Companion Doc allows the writer to throw that thought forward with a single keystroke, capture it in one line, and return to writing without losing the thread. Notes accumulate in a separate view and are available for review outside of active writing sessions.

The Shadow Bible watches the text automatically. The Companion Doc is the writer talking back.

### UI Behavior

**Capture Mode (in-Hearth):**

- Triggered by `Ctrl+Shift+C` from anywhere in the app
- Opens a **slim single-line input bar** that overlays the bottom of the Hearth — similar to a command palette or search bar aesthetic
- The bar appears with a subtle fade-in (100ms)
- Writer types a note (free text, no formatting required)
- `Enter` saves the note and dismisses the bar instantly — writer is returned to their exact cursor position in the Hearth
- `Escape` dismisses without saving
- The bar should be visually minimal — dark background, single text field, a small `companion` label or quill icon to identify it, nothing else
- Do **not** pause the Shadow Bible scan or affect Hearth state while the bar is open

**Review Mode (outside active writing):**

- Accessible via **Actions menu → Companion Doc** or `Ctrl+Shift+D`
- Opens a **dockable panel** or **dialog** showing all Companion Doc notes for the current project
- Notes are listed in reverse chronological order (newest first)
- Each note shows:
  - Note text
  - Date and approximate chapter context if determinable (based on which chapter was active when the note was captured)
  - A **dismiss button** (moves note to `.compost/` — soft delete, consistent with existing Compost Bin behavior)
  - A **copy button** for pasting into the manuscript or a companion document
- No editing of existing notes in this view — notes are capture-only; dismiss and re-enter if correction needed
- Filter by chapter (optional enhancement, not required for v1)

### Data

Add the following table to `vault.db`:

```sql
CREATE TABLE IF NOT EXISTS companion_notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT NOT NULL,
    note TEXT NOT NULL,
    chapter_context TEXT,             -- chapter filename active at capture time, nullable
    captured_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    dismissed INTEGER NOT NULL DEFAULT 0,
    dismissed_at DATETIME
);
```

- `chapter_context` should be populated with the currently active chapter filename at time of capture if available; NULL otherwise
- Dismissed notes are soft-deleted (flag set, not removed) consistent with Compost Bin philosophy
- Notes are project-scoped

### Rules

- No character limit enforced, but the single-line capture UI naturally encourages brevity
- Capture bar must not intercept or swallow any keystrokes intended for the Hearth — only active when bar is explicitly open
- Notes persist indefinitely until dismissed
- Dismissed notes are recoverable from `.compost/` consistent with existing behavior — when dismissing, write a timestamped copy to `.compost/companion_<timestamp>__<note_excerpt>.txt`

---

## 3) Exhale

### Purpose

Exhale is a session word count target set intentionally by the writer before or at the start of a writing session. It is not a passive counter — it is an active declaration. The writer chooses how many words they intend to release in this session. The Exhale tracks progress toward that number and signals completion.

The name reflects the philosophy: writing is something held inside that needs to come out. The Exhale is not a quota imposed from outside. It is the writer choosing their own release.

### UI Behavior

**Setting the Exhale:**

- Accessible via **Actions menu → Set Exhale** or `Ctrl+Shift+E`
- Opens a **minimal numeric input dialog** — single field, large text, label reads `Words to exhale this session:`, confirm button
- Pre-populates with the last session's Exhale value as a convenience default (editable)
- Accepting sets the Exhale for the current session
- Exhale can be updated mid-session via the same shortcut — opens the same dialog with current value pre-filled

**Progress Display:**

- A **slim Exhale indicator** appears in the status bar at the bottom of the Hearth (same row as word count if word count is displayed)
- Shows current session word count vs. Exhale target: e.g. `847 / 1000` in muted accent color (`#6BBF9B`)
- When the Exhale is reached:
  - The indicator briefly **glows or pulses** (single pulse animation, 1–1.5 seconds, consistent with cursor pulse timing)
  - Text changes to `exhaled ✓` or equivalent
  - No modal, no interruption — the writer can keep writing
- If no Exhale is set for the session, the indicator shows only the running word count (existing behavior preserved)

**Session Word Count:**

- Session word count resets when:
  - A new session is explicitly started (if session concept exists in app)
  - The app is relaunched
  - The writer manually resets via Actions menu
- Session word count is **distinct from total project word count** — it measures only words written in the current sitting
- Implement session word delta by storing a baseline word count on session start and tracking the difference

### Data

Add the following table to `vault.db`:

```sql
CREATE TABLE IF NOT EXISTS exhale_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT NOT NULL,
    session_date TEXT NOT NULL,       -- ISO date YYYY-MM-DD
    target_words INTEGER NOT NULL,
    words_written INTEGER NOT NULL DEFAULT 0,
    completed INTEGER NOT NULL DEFAULT 0,  -- 1 when target reached
    started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME
);
```

- One record per session per project
- `words_written` updated periodically (on save, or on a background timer — same cadence as Shadow Bible scan)
- `completed` flagged when `words_written >= target_words`
- Last session's `target_words` used as default pre-fill for next session's Exhale dialog

### Rules

- Exhale is optional — no prompting or warning if writer opens Hearth without setting one
- Exhale target must be a positive integer — reject zero or negative values silently (reset field)
- No upper limit enforced
- Exhale does not lock the Hearth or prevent writing — it is ambient, not gating

---

## Integration Notes

### Keyboard Shortcuts Summary

| Feature | Shortcut | Action |
|---|---|---|
| Sparks panel | `Ctrl+Shift+S` | Toggle Sparks panel |
| Companion Doc capture | `Ctrl+Shift+C` | Open capture bar |
| Companion Doc review | `Ctrl+Shift+D` | Open review panel |
| Set Exhale | `Ctrl+Shift+E` | Open Exhale target dialog |

All shortcuts should be listed in the Actions menu alongside existing shortcuts.

### Focus Fade Behavior

All new UI elements must respect the existing Hearth focus fade logic:
- When the writer is actively typing, all chrome (including Sparks panel if visible) fades to low opacity
- Companion Doc capture bar is exempt from fade — it is only open when the writer has explicitly invoked it and is not typing in the Hearth
- Exhale indicator in the status bar fades with other status bar elements per existing behavior

### vault.db Migration

On app launch, run a migration check:

```python
def migrate_vault(conn):
    conn.execute("""
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
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS companion_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id TEXT NOT NULL,
            note TEXT NOT NULL,
            chapter_context TEXT,
            captured_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            dismissed INTEGER NOT NULL DEFAULT 0,
            dismissed_at DATETIME
        )
    """)
    conn.execute("""
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
    """)
    conn.commit()
```

`CREATE TABLE IF NOT EXISTS` ensures safe execution on existing databases with no existing data loss.

---

## Open Questions

- Should Sparks from previous days be viewable in a history panel, or archived silently?
- Should the Companion Doc capture bar support multi-line input (e.g. Shift+Enter for newline, Enter to save)?
- Should Exhale progress be visible in the Constellation view as session metadata on scene nodes?
- Should completed Sparks carry forward to the next day if not all 5 were set (i.e. preserve incomplete ones)?
