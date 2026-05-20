# V5 UI Implementation — Stage 7 (Codex)

**Owner:** Codex
**Depends on:** Stages 1–6 complete and verified.
**Design authority:** `Docs/DesktopApp/docs/V5_UI_DESIGN_REFERENCE.md`

---

## Context

Stage 6 defined the `.empty-state` CSS component (centered muted-text placeholder, minimum 120px height). Stage 7 places the HTML elements for that component inside every table wrapper and panel that can be empty at runtime.

**One file is modified:**

- `DesktopApp\mediapipeline_desktop_app\ui_web\static\index.html`

**Critical constraints:**
- Do NOT change any `id`, `data-page`, `data-panel-type`, `data-state`, `type`, `scope`, or other existing attributes
- Do NOT change any existing visible text
- Do NOT touch any JS or CSS files
- Do NOT remove or reorder any existing elements
- Only insert the empty state markup described below — nothing else

---

## Task 1 — Place empty state elements

### The pattern

Every `.table-wrap` div that wraps a `<table>` must contain a sibling empty state element. The JS already controls visibility of rows; when the `<tbody>` is empty at runtime, no row is displayed, but currently nothing tells the operator why the table is blank. The empty state element sits inside the `.table-wrap`, after the `<table>`, hidden by default via `data-empty-state="hidden"`.

The JS will toggle `data-empty-state` between `"hidden"` and `"visible"` (this is existing JS behavior — Stage 7 only supplies the target HTML). **Do not add any JS.** The CSS `.empty-state` class handles layout; JS will show/hide by setting `display` or `data-empty-state`.

### Empty state markup

```html
<div class="empty-state" data-empty-state="hidden" style="display:none">
  <span class="empty-state-label">No items</span>
  <span class="empty-state-hint">Items will appear here when available.</span>
</div>
```

> **Note on `style="display:none"`:** The inline `display:none` hides the element on initial load. JS removes it when it needs to show the empty state. This is consistent with how other elements are shown/hidden in this codebase (JS sets `display` directly). Do not use a class for hiding — the inline style is intentional.

### Placement rule

Insert the empty state markup **immediately after the closing `</table>` tag** and **before the closing `</div>` of the `.table-wrap`**:

```html
<!-- Before -->
<div class="table-wrap">
  <table>
    ...
  </table>
</div>

<!-- After -->
<div class="table-wrap">
  <table>
    ...
  </table>
  <div class="empty-state" data-empty-state="hidden" style="display:none">
    <span class="empty-state-label">No items</span>
    <span class="empty-state-hint">Items will appear here when available.</span>
  </div>
</div>
```

### Identify target table wrappers

```powershell
$html = "DesktopApp\mediapipeline_desktop_app\ui_web\static\index.html"

# Find all .table-wrap divs — these are the targets
Select-String -Path $html -Pattern 'class="table-wrap'
# Count the results — each one needs an empty state element.

# Verify none already has an empty-state child
Select-String -Path $html -Pattern 'empty-state'
# Should return 0 before you start. After the task it should match the count above.
```

Apply the insertion to **every** `.table-wrap` found. There are no exceptions — every table in this app can be empty at runtime.

### Verify Task 1

```powershell
$html = "DesktopApp\mediapipeline_desktop_app\ui_web\static\index.html"

# Count table-wrap divs
$wrapCount = (Select-String -Path $html -Pattern 'class="table-wrap').Count

# Count empty-state elements
$emptyCount = (Select-String -Path $html -Pattern 'class="empty-state"').Count

Write-Host "table-wrap count: $wrapCount"
Write-Host "empty-state count: $emptyCount"
Write-Host "Match: $($wrapCount -eq $emptyCount)"
# Match must be True and both counts must be equal and > 0.

# No existing element should have been removed
(Select-String -Path $html -Pattern '\bid="').Count
# Must still be 955.
```

---

## Task 2 — Inventory and log updates

### 2a — DOM ID count

No new `id` attributes are added. Confirm count is still 955.

```powershell
$html = "DesktopApp\mediapipeline_desktop_app\ui_web\static\index.html"
(Select-String -Path $html -Pattern '\bid="').Count
# Must be 955.
```

### 2b — Append to DOC_TOUCH_LOG.md

Append one row after the existing Stage 6 execution row:

```
| 2026-05-16 | V5 UI Stage 7 execution (Codex) — empty state HTML placement in all table wrappers | `REMEDIATION_CHANGELOG.md` | `WEBVIEW_DOM_ID_INVENTORY.md` (no new IDs — count confirmed 955), `WEBVIEW_GLOBAL_EXPORT_INVENTORY.md` (no JS files touched), `API_ROUTE_INVENTORY.md` (no new routes), `BROWSER_SMOKE_DOES_NOT_MUTATE_MATRIX.md` (no mutation changes), `TEST_COVERAGE_MATRIX.md` (no test changes), `TAURI_WEBVIEW_PARITY_MATRIX.md` (no parity change), `VALIDATION_LADDER_RUNBOOK.md` (no rung changes), `DOCS_INDEX.md` (no new docs) | index.html: .empty-state div (with .empty-state-label and .empty-state-hint children) inserted after </table> inside every .table-wrap; data-empty-state="hidden" style="display:none" on initial load; table-wrap count and empty-state count confirmed equal |
```

### 2c — Append to REMEDIATION_CHANGELOG.md

Add a dated H2 entry before the existing 2026-05-16 Stage 6 entry (newest first).

Minimum content:

```markdown
## 2026-05-16 - V5 UI Stage 7: Empty State HTML Placement

Placed `.empty-state` elements inside every `.table-wrap` in `index.html`. No text, attribute, JS, or CSS changes.

Changes:

- `index.html`: For every `<div class="table-wrap">`, inserted `<div class="empty-state" data-empty-state="hidden" style="display:none">` with two child spans immediately after the `</table>` tag; table-wrap count and empty-state count are equal

Validation:

[Paste Task 1 verification output here — table-wrap count, empty-state count, Match: True]

Regression risk: none. Elements are hidden by inline style on initial load. Existing JS behavior (setting display directly) will activate them. No existing markup was removed or reordered.
```

Also update entry count from `828` to `829` and `#### 2026-05-16 (6 entries)` to `(7 entries)`, and add the Stage 7 anchor to the `#### 2026-05-16` list.

---

## Completion checklist

- [ ] Task 1 done — every `.table-wrap` has exactly one `.empty-state` sibling; counts match
- [ ] Task 1 verified — table-wrap count equals empty-state count, both > 0
- [ ] Task 2a done — DOM ID count still 955
- [ ] Task 2b done — DOC_TOUCH_LOG row appended
- [ ] Task 2c done — REMEDIATION_CHANGELOG H2 entry added, entry count updated
- [ ] No `id`, `data-page`, `data-panel-type`, `type`, `scope`, `class`, or other existing attributes changed
- [ ] No visible text changed
- [ ] No JS or CSS files modified
