# V5 UI Implementation — Stage 9 (Codex)

**Owner:** Codex
**Depends on:** Stages 1–8 complete and verified.
**Design authority:** `Docs/DesktopApp/docs/V5_UI_DESIGN_REFERENCE.md`

---

## Context

Stage 8 wired `focus-visible` rings to all buttons using the `--focus-ring` token. The matching CSS rules for selectable table rows (`tr[data-selectable-row="true"]:focus-visible td { ... }`) were already written in Stage 2, but they can never fire because `<tr>` elements are not in the tab order by default — they require `tabindex="0"` to be keyboard-focusable.

Stage 9 fixes this: add `tabindex="0"` to every `<tr>` that carries `data-selectable-row="true"`.

**One file is modified:**

- `DesktopApp\mediapipeline_desktop_app\ui_web\static\index.html`

**Critical constraints:**
- Do NOT change any `id`, `data-page`, `data-panel-type`, `data-state`, `data-selectable-row`, `type`, `scope`, or other existing attributes
- Do NOT change any visible text
- Do NOT touch any JS or CSS files
- Do NOT remove or reorder any existing elements
- Only add the `tabindex="0"` attribute to the specific rows described below

---

## Task 1 — Add `tabindex="0"` to selectable rows

### Why

`tr[data-selectable-row="true"]:focus-visible` is already styled in `styles.css` (blue halo on cells, set in Stage 2). But `<tr>` elements are not focusable by default in HTML — the browser skips them during tab navigation unless `tabindex="0"` is present. Without this attribute the CSS rule is dead code and keyboard users cannot select rows.

### Rule

For every `<tr` element that has `data-selectable-row="true"`, add `tabindex="0"` immediately after the `data-selectable-row="true"` attribute.

```html
<!-- Before -->
<tr data-selectable-row="true">

<!-- After -->
<tr data-selectable-row="true" tabindex="0">
```

Do not add `tabindex` to any `<tr>` that does not have `data-selectable-row="true"`.

### Find target rows

```powershell
$html = "DesktopApp\mediapipeline_desktop_app\ui_web\static\index.html"

# Count rows that need the attribute
$targets = Select-String -Path $html -Pattern 'data-selectable-row="true"'
Write-Host "Selectable rows found: $($targets.Count)"

# Confirm none already has tabindex (should be 0 before you start)
$already = Select-String -Path $html -Pattern 'data-selectable-row="true".*tabindex|tabindex.*data-selectable-row="true"'
Write-Host "Already have tabindex: $($already.Count)"
# Must be 0 before you start.
```

Apply `tabindex="0"` to every row the first query returns.

### Verify Task 1

```powershell
$html = "DesktopApp\mediapipeline_desktop_app\ui_web\static\index.html"

# All selectable rows must now have tabindex="0"
$withTabindex = (Select-String -Path $html -Pattern 'data-selectable-row="true".*tabindex="0"|tabindex="0".*data-selectable-row="true"').Count
$total        = (Select-String -Path $html -Pattern 'data-selectable-row="true"').Count

Write-Host "Total selectable rows: $total"
Write-Host "Rows with tabindex=0: $withTabindex"
Write-Host "Match: $($withTabindex -eq $total)"
# Match must be True.

# No row without data-selectable-row should have gained tabindex
$unexpected = Select-String -Path $html -Pattern '<tr[^>]*tabindex' |
  Where-Object { $_.Line -notmatch 'data-selectable-row="true"' }
Write-Host "Unexpected tabindex rows: $($unexpected.Count)"
# Must be 0.

# DOM ID count unchanged
(Select-String -Path $html -Pattern '\bid="').Count
# Must still be 955.
```

---

## Task 2 — Inventory and log updates

### 2a — DOM ID count

No new `id` attributes are added. Confirm count is still 955.

```powershell
(Select-String -Path "DesktopApp\mediapipeline_desktop_app\ui_web\static\index.html" -Pattern '\bid="').Count
# Must be 955.
```

### 2b — Append to DOC_TOUCH_LOG.md

Append one row after the existing Stage 8 execution row:

```
| 2026-05-16 | V5 UI Stage 9 execution (Codex) — tabindex="0" on selectable table rows | `REMEDIATION_CHANGELOG.md` | `WEBVIEW_DOM_ID_INVENTORY.md` (no new IDs — count confirmed 955), `WEBVIEW_GLOBAL_EXPORT_INVENTORY.md` (no JS files touched), `API_ROUTE_INVENTORY.md` (no new routes), `BROWSER_SMOKE_DOES_NOT_MUTATE_MATRIX.md` (no mutation changes), `TEST_COVERAGE_MATRIX.md` (no test changes), `TAURI_WEBVIEW_PARITY_MATRIX.md` (no parity change), `VALIDATION_LADDER_RUNBOOK.md` (no rung changes), `DOCS_INDEX.md` (no new docs) | index.html: tabindex="0" added to every <tr data-selectable-row="true">; activates the already-written :focus-visible CSS rule on selectable rows; no text, id, data-*, class, or type changes to existing elements |
```

### 2c — Append to REMEDIATION_CHANGELOG.md

Add a dated H2 entry before the existing 2026-05-16 Stage 8 entry (newest first).

Minimum content:

```markdown
## 2026-05-16 - V5 UI Stage 9: Selectable Row Keyboard Focus (tabindex)

Added `tabindex="0"` to every `<tr data-selectable-row="true">` in `index.html`. Activates the Stage 2 `:focus-visible` CSS rule that was otherwise unreachable.

Changes:

- `index.html`: `tabindex="0"` added to every `<tr data-selectable-row="true">` — makes selectable rows reachable via keyboard tab navigation; the `tr[data-selectable-row="true"]:focus-visible td` CSS rule (defined in Stage 2) can now fire

Validation:

[Paste Task 1 verification output here — total selectable rows, rows with tabindex=0, Match: True, unexpected=0]

Regression risk: none. `tabindex="0"` makes existing rows focusable; it does not change their render, their data attributes, or their JS event handlers. JS already listens for click events on these rows; keyboard Enter/Space activation is handled by the existing JS event delegation.
```

Also update entry count from `830` to `831` and `#### 2026-05-16 (8 entries)` to `(9 entries)`, and add the Stage 9 anchor to the `#### 2026-05-16` list.

---

## Completion checklist

- [ ] Task 1 done — every `<tr data-selectable-row="true">` has `tabindex="0"`
- [ ] Task 1 verified — total count equals tabindex count, unexpected=0, DOM ID still 955
- [ ] Task 2a done — DOM ID count confirmed 955
- [ ] Task 2b done — DOC_TOUCH_LOG row appended
- [ ] Task 2c done — REMEDIATION_CHANGELOG H2 entry added, entry count updated
- [ ] No `id`, `data-selectable-row`, `data-page`, `data-panel-type`, `type`, `scope`, `class`, or other existing attributes changed
- [ ] No visible text changed
- [ ] No JS or CSS files modified
- [ ] No `tabindex` added to any `<tr>` that does not have `data-selectable-row="true"`
