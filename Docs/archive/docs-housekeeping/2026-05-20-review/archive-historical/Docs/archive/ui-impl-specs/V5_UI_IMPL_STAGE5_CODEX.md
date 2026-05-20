# V5 UI Implementation — Stage 5 (Codex)

**Owner:** Codex
**Depends on:** Stages 1–4 complete and verified.
**Design authority:** `Docs/DesktopApp/docs/V5_UI_DESIGN_REFERENCE.md`

---

## Context

Stages 1–4 covered text corrections, panel classification, the full CSS token system, personality rules, spacing migration, button wiring, shadows, focus states, and evidence panel styling.

Stage 5 is a pure HTML correctness pass: two mechanical fixes to `index.html` that have no design-reference ambiguity and no judgment calls.

**One file is modified:**

- `DesktopApp\mediapipeline_desktop_app\ui_web\static\index.html`

**Critical constraints (same as all prior stages):**
- Do NOT change any `id`, `data-page`, `data-panel-type`, `data-state`, or other data attributes
- Do NOT change any visible text
- Do NOT touch any JS or CSS files
- Only add the two attributes described below — nothing else

---

## Task 1 — Add `type="button"` to all buttons that lack a type attribute

### Why

HTML buttons default to `type="submit"` when no `type` is specified. In a WebView2/Tauri app with no traditional form submissions this causes no harm today, but it is incorrect markup, risks unexpected behavior if a button is ever placed inside a `<form>` element, and confuses accessibility tools that inspect button roles.

Every button in this app that is not a deliberate submit button must carry `type="button"`.

### Rule

For every `<button` element in `index.html`:

- If it already has `type="button"`, `type="submit"`, or `type="reset"` → leave it unchanged
- If it has no `type` attribute at all → add `type="button"` immediately after the `<button` opening tag (before `id=`, `class=`, or other attributes)

There are no `<form>` submit buttons in this codebase. If any `<button>` lacks a `type`, add `type="button"`.

### How to find buttons missing a type attribute

```powershell
$html = "DesktopApp\mediapipeline_desktop_app\ui_web\static\index.html"

# Find lines with <button that do NOT contain type=
Select-String -Path $html -Pattern "<button" |
  Where-Object { $_.Line -notmatch 'type=' }
```

Review the output. Every line returned is a button that needs `type="button"` added.

### Transformation

```html
<!-- Before -->
<button id="some-action-button" class="secondary-button">Label</button>

<!-- After -->
<button type="button" id="some-action-button" class="secondary-button">Label</button>
```

The `type="button"` attribute goes immediately after `<button`, before all other attributes. No other attribute, text, or whitespace changes.

### Verify Task 1

```powershell
$html = "DesktopApp\mediapipeline_desktop_app\ui_web\static\index.html"

# After the fix, this must return 0 results.
$missing = Select-String -Path $html -Pattern "<button" |
  Where-Object { $_.Line -notmatch 'type=' }
$missing | ForEach-Object { Write-Host "LINE $($_.LineNumber): $($_.Line.Trim())" }
Write-Host "Buttons missing type=: $($missing.Count)"
# Must print 0.
```

---

## Task 2 — Add `scope="col"` to all `<th>` elements that lack a scope attribute

### Why

The design reference (Section 7, table component) specifies that column headers carry `scope="col"`. This is the correct semantic attribute for column headers in an HTML table — it binds each header to its column for screen readers, browser accessibility APIs, and automated accessibility checkers. The existing `<th>` elements lack it.

### Rule

For every `<th` element in `index.html`:

- If it already has `scope="col"` or `scope="row"` → leave it unchanged
- If it has no `scope` attribute → add `scope="col"` immediately after the `<th` opening tag

All `<th>` elements in this app are column headers (top of a table column), so `scope="col"` is correct for all of them.

### Transformation

```html
<!-- Before -->
<th>Column Name</th>

<!-- After -->
<th scope="col">Column Name</th>
```

No other attribute, text, or whitespace changes.

### Verify Task 2

```powershell
$html = "DesktopApp\mediapipeline_desktop_app\ui_web\static\index.html"

# After the fix, this must return 0 results.
$missing = Select-String -Path $html -Pattern "<th" |
  Where-Object { $_.Line -notmatch 'scope=' }
$missing | ForEach-Object { Write-Host "LINE $($_.LineNumber): $($_.Line.Trim())" }
Write-Host "th elements missing scope=: $($missing.Count)"
# Must print 0.
```

---

## Task 3 — Inventory and log updates

### 3a — DOM ID count

No new `id` attributes are added in Stage 5. Confirm count is unchanged from Stages 1–4 (955):

```powershell
$html = "DesktopApp\mediapipeline_desktop_app\ui_web\static\index.html"
(Select-String -Path $html -Pattern '\bid="').Count
# Must still be 955. If different, investigate before logging.
```

### 3b — Append to DOC_TOUCH_LOG.md

Append one row after the existing Stage 4 execution row:

```
| 2026-05-16 | V5 UI Stage 5 execution (Codex) — button type attribute and th scope attribute | `REMEDIATION_CHANGELOG.md` | `WEBVIEW_DOM_ID_INVENTORY.md` (no new IDs — count confirmed 955), `WEBVIEW_GLOBAL_EXPORT_INVENTORY.md` (no JS files touched), `API_ROUTE_INVENTORY.md` (no new routes), `BROWSER_SMOKE_DOES_NOT_MUTATE_MATRIX.md` (no mutation changes), `TEST_COVERAGE_MATRIX.md` (no test changes), `TAURI_WEBVIEW_PARITY_MATRIX.md` (no parity change), `VALIDATION_LADDER_RUNBOOK.md` (no rung changes), `DOCS_INDEX.md` (no new docs) | index.html: type="button" added to all <button> elements missing a type attribute; scope="col" added to all <th> elements missing a scope attribute; no text, id, data-*, or class changes |
```

### 3c — Append to REMEDIATION_CHANGELOG.md

Add a dated H2 entry before the existing 2026-05-16 Stage 4 entry (i.e. at the top of the entry block, newest first).

Minimum content:

```markdown
## 2026-05-16 - V5 UI Stage 5: Button Type Attribute and Table Header Scope Attribute

Applied two HTML correctness fixes to `index.html` with no visible or behavioral changes.

Changes:

- `index.html`: Added `type="button"` to every `<button>` element that lacked a type attribute — prevents default `type="submit"` semantics on action buttons
- `index.html`: Added `scope="col"` to every `<th>` element that lacked a scope attribute — binds column headers to their columns for accessibility tooling

Validation:

[Paste Task 1 and Task 2 verification output here]

Regression risk: none. Both changes are additive attribute-only additions with no effect on layout, styling, or JS behavior. JS targets all buttons by ID. CSS selectors do not target `type=` or `scope=` attributes.
```

Also update the Full Entry Index count from `826 entries across 11 days` to `827 entries across 11 days`, update `#### 2026-05-16 (4 entries)` to `(5 entries)`, and add the Stage 5 entry to the `#### 2026-05-16` list.

---

## Completion checklist

- [ ] Task 1 done — 0 `<button>` elements without `type=` attribute
- [ ] Task 2 done — 0 `<th>` elements without `scope=` attribute
- [ ] Task 3a done — DOM ID count still 955
- [ ] Task 3b done — DOC_TOUCH_LOG row appended
- [ ] Task 3c done — REMEDIATION_CHANGELOG H2 entry added, entry count updated
- [ ] No `id`, `data-page`, `data-panel-type`, `class`, or other attributes changed
- [ ] No button or heading text changed
- [ ] No JS or CSS files modified
