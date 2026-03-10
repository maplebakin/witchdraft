# WitchDraft UI Layout Specification

> Read WitchDraft_Philosophy.md before implementing anything in this document.
> Every decision here flows from that document. If something feels unclear, the philosophy is the tiebreaker.

---

## The Golden Rule

**The Hearth is the whole app. Everything else is a drawer.**

When a writer opens WitchDraft, they should feel the room go quiet. Not see a dashboard. Not make decisions. Just arrive.

---

## Top-Level Layout

```
┌─────────────────────────────────────────────────────────────┐
│  SLIM TOP BAR                                               │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│                                                             │
│                      HEARTH                                 │
│                  (writing canvas)                           │
│                                                             │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│  SLIM STATUS BAR                                            │
└─────────────────────────────────────────────────────────────┘
```

No permanent sidebars. No panels open by default. Just the Hearth.

---

## The Top Bar

Slim. Dark. Unobtrusive. Always present.

```
[ ≡ ]  WitchDraft  |  E.D.E.N.  |  Chapter 1  ·  saved  ·  312 words        [ ⊞ Beats ]  [ ✦ Constellation ]  [ ⬡ Characters ]  [ ··· Actions ]  [ ⤢ Fullscreen ]
```

### Elements left to right:

**[ ≡ ] Nav drawer trigger**
Opens the left navigation drawer (Chapters + Storylines). Icon only. Tooltip: "Navigation."

**WitchDraft**
App name. Static. Subtle gold or parchment tone.

**| Project name |**
Current project. Clickable → opens Project settings overlay.

**| Chapter name |**
Current chapter. Clickable → opens chapter list drawer inline.

**· saved · 312 words**
Save state + word count. Quiet, small, always truthful.

---

**Right side — the Tier 3 summons:**

**[ ⊞ Beats ]**
Opens the Beats panel. The global story idea pool.

**[ ✦ Constellation ]**
Opens the Constellation overlay. The pattern reading.

**[ ⬡ Characters ]**
Opens the Characters panel. Roster + card access.

**[ ··· Actions ]**
Dropdown: Sparks, Companion Doc, Exhale, Export, Settings.

**[ ⤢ Fullscreen ]**
Full Hearth mode. Top bar collapses to a single hover-reveal strip. Nothing else visible.

---

## The Status Bar

Single slim line at the bottom. Always present unless in Fullscreen.

```
Chapter 1  ·  2 words  ·  saved  ·  [Exhale: 500 words]  ·  [🔥 3 Sparks active]
```

- Chapter name
- Session word count / total word count toggle on click
- Save state (saved / saving... / unsaved)
- Exhale target if set (click to set/clear)
- Sparks count if active (click to open Sparks)

---

## Left Drawer — Navigation

**Trigger:** [ ≡ ] top bar icon, or swipe/keyboard shortcut.
**Behavior:** Slides in from left, semi-transparent overlay. Does not push the Hearth. Click outside to dismiss.

```
┌──────────────────┐
│  CHAPTERS        │
│  ────────────    │
│  ▶ Chapter 1     │
│    Chapter 2     │
│    Chapter 3     │
│                  │
│  [ + New ]       │
│                  │
│  STORYLINES      │
│  ────────────    │
│  ◈ Reason to L…  │  ← full name in tooltip on hover
│                  │
│  [ + New ]       │
└──────────────────┘
```

- Chapter names truncate gracefully with tooltip on hover showing full name
- Active chapter highlighted
- Storyline names truncate with tooltip
- Drawer is wide enough to show ~25 characters comfortably
- Delete actions behind long-press or right-click context menu — not default visible

---

## Right Drawer — Outliner

**Trigger:** Swipe from right edge, or keyboard shortcut `Ctrl+Shift+O`.
**Behavior:** Slides in from right. Same overlay behavior as left drawer.

```
┌──────────────────────┐
│  OUTLINER            │
│  ──────────────────  │
│  Chapter 1           │
│    Synopsis...       │
│  Chapter 2           │
│    Synopsis...       │
│                      │
│  [ + Add ]  [ Del ]  │
└──────────────────────┘
```

Clean. Full labels. No truncation because the drawer is wide enough.

---

## Beats Panel

**Trigger:** [ ⊞ Beats ] top bar button.
**Behavior:** Opens as a right-side drawer OR a floating panel — user can pin it. Remembers last state.

### Two modes:

**Global view (default)**
The full pool. All beats regardless of chapter or status.

```
┌─────────────────────────────────────────┐
│  BEATS                          [ + ]   │
│  ─────────────────────────────────────  │
│  Filter: [ All ▾ ]  [ Characters ▾ ]   │
│                                         │
│  ○ Josh realizes Maggie remembers       │
│    → ADAM, EVE  ·  idea                 │
│                                         │
│  ● The garden conversation              │
│    → ADAM  ·  active  ·  Ch.2           │
│                                         │
│  ✓ First contact with colonists         │
│    → EVE  ·  used                       │
│                                         │
└─────────────────────────────────────────┘
```

- `○` = Idea (unchecked, unassigned)
- `●` = Active (assigned to a chapter, in progress)
- `✓` = Used (composted but visible, dimmed)
- Click a beat to expand → full text, character tags, notes, status controls
- [ + ] captures a new beat instantly — one field, no decisions required

**Chapter view (when inside a chapter)**
Automatically filters to beats relevant to this chapter — active beats assigned here, plus the full idea pool to draw from.

```
┌─────────────────────────────────────────┐
│  BEATS  ·  Chapter 2            [ + ]   │
│  ─────────────────────────────────────  │
│  THIS CHAPTER                           │
│  ● The garden conversation   [ ✓ done ] │
│  ● Josh's first memory flash [ ✓ done ] │
│                                         │
│  IDEA POOL  (pull one in)               │
│  ○ Josh realizes Maggie remembers  [ → ]│
│  ○ The naming scene                [ → ]│
│                                         │
└─────────────────────────────────────────┘
```

- [ → ] assigns a beat to this chapter (pulls it from pool to active)
- [ ✓ done ] marks it used (composts it)
- The pool below is always available to pull from mid-session

---

## Character Cards

**Trigger:** [ ⬡ Characters ] top bar, or clicking a character tag on a beat.
**Behavior:** Opens as an overlay panel. Character roster on left, active card on right.

### Roster view:
```
┌──────────────────────────────────────────────────────┐
│  CHARACTERS                              [ + New ]   │
│  ──────────────────────────────────────────────────  │
│  [ ADAM / Josh ]                                     │
│  [ EVE / Maggie ]                                    │
│  [ The Mayor ]                                       │
└──────────────────────────────────────────────────────┘
```

### Character card view (click a character):
```
┌──────────────────────────────────────────────────────┐
│  ← Characters                                        │
│                                                      │
│  ADAM / Josh                                         │
│  ──────────────────────────────────────────────────  │
│  PROFILE                                             │
│  Colonial employee. Designated resource manager.     │
│  Doesn't know he's become a god. Earnest, confused,  │
│  quietly terrified. Voice: plain, sincere.           │
│                                                      │
│  ARC  ·  read from beats                            │
│                                                      │
│  PAST                                                │
│  ✓ First contact with colonists                      │
│  ✓ The garden conversation                           │
│                                                      │
│  ACTIVE                                              │
│  ● Josh's first memory flash                         │
│  ● Josh realizes Maggie remembers                    │
│                                                      │
│  INTENDED                                            │
│  ○ The naming scene                                  │
│  ○ Josh attempts to leave the island                 │
│                                                      │
└──────────────────────────────────────────────────────┘
```

- Arc is **assembled automatically from beats** — never manually entered
- Profile is freeform text — write it like you'd describe them to a friend
- Edit button reveals profile text as editable field
- No forms. No required fields. Just space to put what you know.

---

## Constellation Overlay

**Trigger:** [ ✦ Constellation ] top bar.
**Behavior:** Full-screen overlay. Escape or button to dismiss.

No changes to existing Constellation behavior — it already does what it should do. It just needs to be accessed as an intentional reach rather than a permanent sidebar fixture.

---

## Actions Menu

**Trigger:** [ ··· Actions ] top bar.
**Behavior:** Dropdown.

```
  Sparks          Ctrl+Shift+S
  Companion Doc   Ctrl+Shift+C
  Exhale          Ctrl+Shift+E
  ─────────────────────────
  Export Project
  Project Settings
  ─────────────────────────
  Preferences
```

---

## Fullscreen / Hearth Mode

**Trigger:** [ ⤢ Fullscreen ] or `F11`.

Everything disappears. The Hearth fills the screen. A single pixel-thin strip at the top reveals the top bar on hover.

Status bar remains at the bottom — word count and save state are sacred, they stay.

Escape exits Fullscreen.

---

## Keyboard Shortcuts — Master List

| Action | Shortcut |
|---|---|
| Navigation drawer | `Ctrl+\` |
| Outliner drawer | `Ctrl+Shift+O` |
| Beats panel | `Ctrl+Shift+B` |
| Characters panel | `Ctrl+Shift+H` |
| Constellation | `Ctrl+Shift+X` |
| Sparks | `Ctrl+Shift+S` |
| Companion Doc | `Ctrl+Shift+C` |
| Exhale | `Ctrl+Shift+E` |
| Fullscreen | `F11` |
| New beat (quick capture) | `Ctrl+Shift+N` |
| Save | `Ctrl+S` |

---

## What Was Removed From Always-Visible

These things existed as permanent sidebar fixtures. They are now drawers and overlays.

| Was | Now |
|---|---|
| Left sidebar — Chapters | Left drawer, triggered by ≡ |
| Left sidebar — Storylines | Left drawer, below chapters |
| Right sidebar — Outliner | Right drawer, `Ctrl+Shift+O` |
| Right sidebar — Characters Present | Beats panel, chapter view (character-tagged beats) |
| Right sidebar — Notes | Companion Doc, `Ctrl+Shift+C` |

Nothing was deleted. Everything was given space to breathe.

---

## Migration Notes for Implementation

- All existing panel content maps cleanly to the new structure above
- The biggest structural change is **removing permanent sidebars** and replacing with drawer/overlay pattern
- Beats system is **new** — requires new DB table and UI
- Character card arc assembly from beats is **new** — requires join query on beats ↔ characters
- Everything else is **reorganization**, not rebuild
- Implement in this order:
  1. Strip permanent sidebars, implement left/right drawers
  2. Rebuild top bar with new trigger buttons
  3. Implement Beats system (DB + UI)
  4. Wire character arc assembly from beats
  5. Polish: tooltips, keyboard shortcuts, fullscreen

---

*Layout Spec version: March 2026*
*Companion document to: WitchDraft_Philosophy.md*
