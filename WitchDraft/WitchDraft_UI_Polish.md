# WitchDraft UI Polish Spec — Dark Academia Overhaul

## Vision

WitchDraft should feel like writing at a candlelit desk in a very old library. Rich, dark, warm. Ink and leather and wood. The kind of interface that makes you want to sit down and stay. Not a productivity app. A sanctuary.

The three aesthetic pillars:
- **Dark academia overall** — deep backgrounds, warm ambers and golds, aged paper tones for text surfaces
- **Soft and rounded sidebars** — journaling-app warmth, not file manager rigidity
- **Atmospheric status bar** — whispers information rather than announcing it

---

## Color Palette (Full Replacement)

Replace the existing palette entirely. These are the new canonical colors for all UI elements.

| Token | Hex | Usage |
|---|---|---|
| `BG_DEEP` | `#1a1714` | Main window background, title bar |
| `BG_PANEL` | `#211e1a` | Sidebar and panel backgrounds |
| `BG_SURFACE` | `#f5f0e8` | Hearth writing surface (aged paper) |
| `BG_CARD` | `#2a2520` | Card/item backgrounds within panels |
| `BG_CARD_HOVER` | `#332e28` | Card hover state |
| `BORDER_SOFT` | `#3d3730` | Subtle panel borders and dividers |
| `ACCENT_GOLD` | `#c9a84c` | Primary accent — buttons, highlights, active states |
| `ACCENT_GOLD_DIM` | `#8a6f30` | Secondary gold — dimmed accents, icons |
| `ACCENT_GREEN` | `#6b8f71` | Secondary accent — completion states, Exhale progress |
| `TEXT_PRIMARY` | `#e8e0d0` | Primary text on dark surfaces |
| `TEXT_SECONDARY` | `#9a8f7e` | Secondary/muted text on dark surfaces |
| `TEXT_FAINT` | `#5a5248` | Very muted text, placeholders, timestamps |
| `TEXT_HEARTH` | `#2b2318` | Writing text on paper surface |
| `CURSOR_COLOR` | `#c9a84c` | Hearth cursor (matches ACCENT_GOLD) |
| `SELECTION_BG` | `#3d3020` | Text selection background in Hearth |
| `SCROLLBAR` | `#3d3730` | Scrollbar track |
| `SCROLLBAR_HANDLE` | `#5a5248` | Scrollbar handle |

---

## Global Stylesheet

Apply this as the base QSS stylesheet on the QApplication object. All specific overrides below build on this foundation.

```css
QWidget {
    background-color: #1a1714;
    color: #e8e0d0;
    font-family: "Georgia", "Palatino Linotype", serif;
    font-size: 13px;
    border: none;
    outline: none;
}

QMainWindow {
    background-color: #1a1714;
}

QScrollBar:vertical {
    background: #1a1714;
    width: 6px;
    border: none;
}

QScrollBar::handle:vertical {
    background: #5a5248;
    border-radius: 3px;
    min-height: 20px;
}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar:horizontal {
    background: #1a1714;
    height: 6px;
    border: none;
}

QScrollBar::handle:horizontal {
    background: #5a5248;
    border-radius: 3px;
}

QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal {
    width: 0px;
}

QToolTip {
    background-color: #2a2520;
    color: #e8e0d0;
    border: 1px solid #3d3730;
    border-radius: 4px;
    padding: 4px 8px;
    font-size: 12px;
}
```

---

## Title Bar

The custom draggable title bar should feel like the header of an old manuscript.

```css
/* Title bar container */
background-color: #1a1714;
border-bottom: 1px solid #3d3730;
height: 42px;
padding: 0 12px;
```

**WitchDraft wordmark:**
- Font: `"Georgia"` or `"Palatino Linotype"`, italic, 15px
- Color: `#c9a84c` (ACCENT_GOLD)
- Letter spacing: 0.05em

**Project name (E.D.E.N. etc.):**
- Font: same serif, regular weight, 13px
- Color: `#9a8f7e` (TEXT_SECONDARY)
- Separator between WitchDraft and project name: `·` in TEXT_FAINT

**Scan status text:**
- Font: monospace (system mono), 11px
- Color: `#5a5248` (TEXT_FAINT)
- When scan is running: color shifts to `#8a6f30` (ACCENT_GOLD_DIM)

**Title bar buttons (Project, Constellation, Actions):**
```css
QPushButton {
    background-color: transparent;
    color: #9a8f7e;
    border: 1px solid #3d3730;
    border-radius: 6px;
    padding: 4px 12px;
    font-family: "Georgia", serif;
    font-size: 12px;
}

QPushButton:hover {
    background-color: #2a2520;
    color: #e8e0d0;
    border-color: #5a5248;
}

QPushButton:pressed, QPushButton:checked {
    background-color: #3d3020;
    color: #c9a84c;
    border-color: #8a6f30;
}
```

**Window control dots (close/minimize):**
- Size: 10px circles
- Colors: `#5a5248` default, `#c9a84c` on hover
- No system-style red/yellow/green — keep them monochrome gold

---

## Hearth (Writing Surface)

The Hearth is aged paper in a dark room. Warm, slightly textured in feel if not literally.

**Writing surface:**
```css
QTextEdit#hearth {
    background-color: #f5f0e8;
    color: #2b2318;
    font-family: "Georgia", "Palatino Linotype", "Book Antiqua", serif;
    font-size: 16px;
    line-height: 1.8;
    border: none;
    selection-background-color: #3d3020;
    selection-color: #f5f0e8;
}
```

**Typewriter margins:**
- Left and right margins: minimum 15% of panel width each side
- Maximum content width: 680px centered
- Top padding: 48px
- These create the sense of writing on a page, not filling a form

**Cursor:**
- Color: `#c9a84c` (warm gold)
- Pulse: existing 1.2–1.6s cycle retained, pulse between `#c9a84c` and `#8a6f30`

**The border between Hearth and the dark surround:**
- No hard border
- Instead: the dark `#1a1714` background of the window shows around the paper surface naturally
- Add a very subtle box shadow on the paper surface if the framework supports it:
  `box-shadow: 0 2px 24px rgba(0,0,0,0.6)`
- In PyQt6, simulate with a slightly darker `#f0ebe2` at the very edges of the QTextEdit, or simply let the contrast between `#f5f0e8` and `#1a1714` speak for itself

---

## Sidebar Panels (Chapters, Storylines)

Soft, rounded, journaling-app feel. Like sticky notes or journal tabs on the dark desk.

**Panel container:**
```css
background-color: #211e1a;
border-right: 1px solid #3d3730;
padding: 8px;
```

**Section headers (CHAPTERS, STORYLINES):**
```css
font-family: "Georgia", serif;
font-size: 10px;
font-weight: normal;
letter-spacing: 0.15em;
text-transform: uppercase;
color: #5a5248;
padding: 12px 8px 6px 8px;
```
No bold. No borders under them. Just quiet labeling.

**Chapter/Storyline items:**
```css
background-color: #2a2520;
border-radius: 8px;
padding: 8px 12px;
margin: 2px 4px;
color: #e8e0d0;
font-family: "Georgia", serif;
font-size: 13px;
border: 1px solid transparent;
```

**Hover state:**
```css
background-color: #332e28;
border-color: #3d3730;
```

**Active/selected state:**
```css
background-color: #3d3020;
border-color: #8a6f30;
color: #c9a84c;
```

**New / Delete buttons at panel bottom:**
```css
background-color: transparent;
color: #5a5248;
border: 1px solid #3d3730;
border-radius: 6px;
padding: 4px 10px;
font-size: 11px;
font-family: "Georgia", serif;
```
Hover: color becomes `#9a8f7e`, border becomes `#5a5248`

**Remove all QTreeView / QTableView default styling** from the Outliner panel. Replace the tree/table widget with a custom list of rounded card items matching the above pattern. The spreadsheet-style outliner should be replaced with a softer stacked card list.

---

## Right Panel (Outliner / Notes)

Currently feels like a spreadsheet. Replace with journaling cards.

**Outliner — replace table with card list:**
- Each chapter entry becomes a rounded card (`border-radius: 8px`, `background: #2a2520`)
- Chapter name in Georgia serif, 13px, `#e8e0d0`
- Word count as a small badge: `#5a5248` text, `#2a2520` background, `border-radius: 4px`, 10px font
- No column headers, no grid lines, no alternating row colors

**Notes panel:**
```css
QTextEdit#notes {
    background-color: #2a2520;
    color: #c8bfaf;
    font-family: "Georgia", serif;
    font-size: 13px;
    border: none;
    border-radius: 8px;
    padding: 12px;
    line-height: 1.6;
}
```

**Edit / Delete buttons:**
- Match the New/Delete button style from sidebar panels above

---

## Status Bar

Currently: a dense single line of system information. 

New vision: a quiet whisper at the bottom of the page. Like marginalia. Like a librarian's note.

**Layout:**
- Slim — maximum 28px height
- Background: `#1a1714` (same as window, no visible bar)
- A single hairline border top: `1px solid #2a2520`
- Text centered or left-aligned with generous padding

**Content — rewrite the status line format:**

Current: `E.D.E.N. — Chapter 1 — Chapter: 2 words | Project: 2 words | Goal: 0/500 (0%) | Streak: 0d | last saved 2026-02-26T23:51:24Z`

New format: `Chapter 1  ·  2 words  ·  saved just now`

Rules:
- Project name removed from status bar (it's already in the title bar)
- Separator: `·` in `#3d3730`
- All text: `#5a5248` (TEXT_FAINT), 11px, Georgia or system serif
- "saved just now" / "saved 2 minutes ago" — human-readable relative time, not ISO timestamp
- Goal/Exhale progress: shown as `↑ 847 / 1000` with a small upward arrow glyph when an Exhale is set, hidden when not set
- Streak: hidden unless streak > 0, shown as `· 🜂 3d` using an alchemical fire symbol or similar if available, else just `· 3d`
- On hover over the status bar: full details fade in as a tooltip

**Atmospheric touch:**
- When the Shadow Bible scan completes, the status bar briefly shows `· the shadows have read` in `#5a5248` for 3 seconds before returning to normal
- When Exhale is reached: status bar briefly shows `· exhaled` in `#6b8f71` (ACCENT_GREEN) for 3 seconds

---

## Sparks Panel (from Addendum)

```css
/* Panel container */
background-color: #211e1a;
border-radius: 10px;
padding: 12px;

/* Section label */
font-size: 10px;
letter-spacing: 0.15em;
text-transform: uppercase;
color: #5a5248;

/* Spark item */
background-color: #2a2520;
border-radius: 8px;
padding: 8px 12px;
margin: 3px 0;
color: #e8e0d0;
font-family: "Georgia", serif;

/* Completed spark item */
color: #5a5248;
text-decoration: line-through;

/* Completion toggle (circle) */
width: 14px;
height: 14px;
border-radius: 7px;
border: 1px solid #5a5248;
/* When complete: background #c9a84c, border #c9a84c */

/* Progress text */
color: #5a5248;
font-size: 11px;
text-align: center;
padding-top: 8px;
```

---

## Companion Doc Capture Bar (from Addendum)

```css
/* Overlay bar */
background-color: #211e1a;
border-top: 1px solid #3d3730;
border-radius: 8px 8px 0 0;
padding: 8px 16px;
height: 44px;

/* Label */
color: #5a5248;
font-size: 11px;
font-family: "Georgia", serif;
font-style: italic;
content: "companion ·";

/* Input field */
background-color: transparent;
color: #e8e0d0;
font-family: "Georgia", serif;
font-size: 13px;
border: none;
caret-color: #c9a84c;
```

---

## Dialogs (Exhale, Project Manager, etc.)

```css
QDialog {
    background-color: #211e1a;
    border: 1px solid #3d3730;
    border-radius: 10px;
}

QLabel {
    color: #9a8f7e;
    font-family: "Georgia", serif;
    font-size: 13px;
}

QLineEdit, QSpinBox {
    background-color: #2a2520;
    color: #e8e0d0;
    border: 1px solid #3d3730;
    border-radius: 6px;
    padding: 6px 10px;
    font-family: "Georgia", serif;
    font-size: 14px;
    selection-background-color: #3d3020;
}

QLineEdit:focus, QSpinBox:focus {
    border-color: #8a6f30;
}

QPushButton#confirm {
    background-color: #3d3020;
    color: #c9a84c;
    border: 1px solid #8a6f30;
    border-radius: 6px;
    padding: 6px 18px;
    font-family: "Georgia", serif;
    font-size: 13px;
}

QPushButton#confirm:hover {
    background-color: #4d3e28;
    border-color: #c9a84c;
}
```

---

## Typography Summary

| Context | Font | Size | Weight | Color |
|---|---|---|---|---|
| Hearth writing | Georgia serif | 16px | Regular | `#2b2318` |
| Panel headers | Georgia serif | 10px | Regular | `#5a5248` |
| Panel items | Georgia serif | 13px | Regular | `#e8e0d0` |
| Status bar | Georgia/system | 11px | Regular | `#5a5248` |
| Title wordmark | Georgia italic | 15px | Regular | `#c9a84c` |
| Dialog labels | Georgia serif | 13px | Regular | `#9a8f7e` |
| Timestamps | System mono | 11px | Regular | `#5a5248` |

**Never use system default sans-serif for visible text.** Georgia or Palatino everywhere except monospace contexts.

---

## Implementation Notes for LLM

- Apply the global QSS stylesheet on `QApplication` at startup, before any windows are shown
- Override specific widgets with `setObjectName()` and target them in QSS with `#objectName` selectors
- The Hearth QTextEdit needs `setObjectName("hearth")` to receive paper-surface styling without affecting other text inputs
- Remove any existing `QPalette` calls that set default colors — let the QSS take over entirely
- The Outliner table widget (`QTableView` or `QTreeView`) should be replaced with a `QListWidget` or custom `QScrollArea` with card items — do not attempt to restyle the table, replace it
- Status bar: replace `QStatusBar` with a custom `QWidget` with a `QLabel` — `QStatusBar` has opinionated styling that fights QSS
- Test all panels with the focus fade system to ensure opacity animations still work after restyling
- Font fallbacks: `"Georgia", "Palatino Linotype", "Book Antiqua", serif` — use this full stack everywhere serif is specified

---

## What Success Looks Like

When you open WitchDraft after this pass:
- The window feels like a dark room with a warm lamp on
- The writing surface feels like paper, not a text box
- The sidebars feel like journal tabs, not a file tree
- The status bar is barely there until you need it
- Every button and label feels like it belongs in a library
- Nothing looks like default Qt
