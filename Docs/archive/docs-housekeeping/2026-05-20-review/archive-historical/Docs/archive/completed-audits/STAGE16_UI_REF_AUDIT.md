# Stage 16 — UI Design Reference Audit

**Date:** 2026-05-17  
**Scope:** All gaps identified by auditing `V5_UI_DESIGN_REFERENCE.md` against the current CSS/HTML implementation.  
**Status:** In progress

---

## Item Tracker

| # | Item | Section | Priority | Status |
|---|------|---------|----------|--------|
| 1 | Disabled button colour (not opacity) | 7, 9 | 🔴 Violation | ✅ Done |
| 2 | Panel heading: small-caps, de-emphasised | 5, 6 | 🟠 High | ✅ Done |
| 3 | Semantic row backgrounds (Queue/Rename/Schedule) | 8 | 🟠 High | ✅ Done |
| 4 | Number columns right-aligned | 6 | 🟡 Medium | ✅ Done |
| 5 | Form label size/weight | 7 | 🟡 Medium | ✅ Done |
| 6 | Input inset shadow | 7 | 🟡 Medium | ✅ Done |
| 7 | Prose 65ch max-width | 3 | 🟡 Medium | ✅ Done |

---

## Item 1 — Disabled Button Colour (not opacity)

**Design reference:** Section 7 (Button states), Section 9 "What Not to Do" — rule #4.

> "Do not dim disabled controls with `opacity`. Change colour instead.  
> Use `--grey-700` bg / `--grey-500` text / `cursor: not-allowed`."

**Root cause:** Global `button:disabled { opacity: 0.58; }` dimmed the entire element including border, which is the behaviour the spec explicitly bans. The specific button variant rules (`.nav-button:disabled`, etc.) set the correct colours but were undermined by the opacity.

**Fix:**
- Removed `opacity: 0.58` from `button:disabled`.
- Added `background: var(--grey-700)` to `.nav-button:disabled, .secondary-button:disabled` so the surface visually changes (previously the opacity was doing that work).
- `.danger-button:disabled` and `.primary-button:disabled` already had correct colour-change rules — no change needed.

---

## Item 2 — Panel Heading Treatment

**Design reference:** Section 5 (Panel Anatomy), Section 6 (Tables & Data).

> Panel headings: `--text-sm`, `ALL CAPS`, `--grey-400`, `letter-spacing: 0.04em`.  
> Current: `--text-md` (17 px), sentence case, `--grey-50`.

**Fix applied to `.panel-heading h2, .panel-heading h3`:**
- `font-size`: `var(--text-md)` → `var(--text-sm)`
- `color`: `var(--grey-50)` → `var(--grey-400)`
- Added: `text-transform: uppercase; letter-spacing: 0.04em; font-weight: 600`

Result: panel headings read as structural labels rather than page titles, matching the compact operator-UI aesthetic described in the reference.

---

## Item 3 — Semantic Row Backgrounds

**Design reference:** Section 8 (Page-specific rules).

### 3a — Queue: warning rows
> "Rows with warnings show `--amber-100` row background."  
`tr[data-status="warning"]` → `--amber-100` bg (light) / dark amber (dark).

### 3b — Rename: duplicate-target conflicts  
> "Duplicate-target conflicts: `--red-100` row background."  
Duplicate rows receive `posture="blocked"` from `renameView.js`.  
`tr[data-status="blocked"]` → `--red-100` bg (light) / dark red (dark).

### 3c — Schedule: day rows by window coverage  
> "Days where launch permitted: `--green-100`. No window: `--grey-100`. Partial: `--amber-100`."  
`scheduleDayRowStatus()` returns: `match` (full day), `ready` (partial), `normal`/`review` (no window), `blocked` (no payload).  
Scoped to `[data-page-panel="schedule"]` to avoid polluting queue/rename "ready" and "match" rows.

**Note:** `tr[data-status="warning"]` and `tr[data-status="blocked"]` backgrounds apply globally — these states are semantically consistent across Queue, Rename, and Diagnostics. The schedule-specific states (`match`, `ready`, `normal`, `review`) are page-scoped.

---

## Item 4 — Number Column Right-Alignment

**Design reference:** Section 6.

> "Right-align numbers in table columns: file sizes, durations, row counts, percentages.  
> Use `tabular-nums` (font-variant-numeric) for column alignment."

**CSS added:** `.num { text-align: right; font-variant-numeric: tabular-nums; }`

**Applied to `<th>` elements:**
- Telemetry GPU table: GPU index, Encoder %, GPU %, Memory
- Completed/Pending: Size, Age
- Reports: Score, GB, GB/h
- Rename history: Size

**Note:** `<td>` body cells are rendered dynamically by `appendCells()` in `domHelpers.js`. To right-align those cells at the JS level, `appendCells()` would need to accept an optional class list per cell — a future `domHelpers.js` Stage 17 refactor. For now, the right-aligned `<th>` headers provide the visual column intent.

---

## Item 5 — Form Label Typography

**Design reference:** Section 7 (Form Inputs).

> "Labels: `--text-sm`, `font-weight: 600`."  
Current: `--text-xs` (11 px), `font-weight: 700`.

**Fix applied to `.form-grid label, .full-field` and `.filter-field`:**
- `font-size`: `var(--text-xs)` → `var(--text-sm)`
- `font-weight`: `700` → `600`
- Color (`--grey-300`) unchanged — correct for both modes.

---

## Item 6 — Input Inset Shadow

**Design reference:** Section 7 (Form Inputs).

> "Default input state: `box-shadow: inset 0 1px 2px hsl(220 5% 0% / 0.08)`"

**Fix:** Added inset shadow to the base `input, select, textarea` rule. The 8 % opacity makes it invisible in dark mode (input bg is already dark) but renders as a subtle depth cue in light mode where the background lightens.

---

## Item 7 — Prose max-width 65ch

**Design reference:** Section 3 (Typography).

> "Prose text (`.note`, description paragraphs inside panels) must not exceed 65 ch."

**Fix:** Added `max-width: 65ch` to `.note`. This caps the readable line length on wide viewports without constraining panels that use `.note` in narrow grid columns (65ch is a soft maximum — the grid will naturally be narrower in those contexts).

---

## Files Changed

| File | Changes |
|------|---------|
| `DesktopApp/…/static/assets/styles.css` | Items 1–7 CSS additions |
| `DesktopApp/…/static/index.html` | `.num` class on numeric `<th>` headers |
| `Docs/REMEDIATION_CHANGELOG.md` | Stage 16 entry added |
| `Docs/DOC_TOUCH_LOG.md` | Stage 16 row added |

---

## Future Work (Stage 17)

- Extend `appendCells(row, values, classes)` in `domHelpers.js` so call-sites can pass per-cell class arrays, enabling `.num` on `<td>` body cells.
- Audit every `appendCells` call site for numeric columns and update accordingly.
