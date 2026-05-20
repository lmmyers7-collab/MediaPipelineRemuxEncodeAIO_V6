# V5 UI Implementation — Stage 3 (Codex)

**Owner:** Codex
**Depends on:** Stage 1 and Stage 2 complete and verified.
**Design authority:** `Docs/DesktopApp/docs/V5_UI_DESIGN_REFERENCE.md`

---

## Context

Stage 1 fixed text and added panel type attributes. Stage 2 defined the CSS token system and applied personality rules. This stage completes the token migration and wires primary button styling.

Two files are modified:

- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\styles.css` — spacing values tokenized (Task 1)
- `DesktopApp\mediapipeline_desktop_app\ui_web\static\index.html` — three buttons re-classed (Task 2)

**Critical constraints (same as Stage 1):**
- Do NOT change any `id`, `data-page`, `data-panel-type`, `data-state`, or other data attributes
- Do NOT change any button's visible text
- Do NOT touch any JS files
- In Task 2, only change the `class` attribute on the three explicitly named buttons — nothing else

---

## Task 1 — Migrate spacing values to tokens

Every `margin`, `padding`, and `gap` declaration in `styles.css` that uses a raw pixel value must be replaced with a `--space-*` token. The tokens are already defined in `:root`.

The only raw values permitted after this task: `0` and `auto`. No other raw values in margin/padding/gap.

### Mapping table

All judgment calls are pre-decided. Apply the table exactly.

| Line (approx) | Selector / context | Current value | Replace with |
|---|---|---|---|
| `input, select, textarea` | `padding` | `9px 10px` | `var(--space-4) var(--space-4)` |
| `.sidebar` | `padding` | `18px 16px` | `var(--space-7) var(--space-6)` |
| `.brand` | `margin-bottom` | `24px` | `var(--space-8)` |
| `.brand-version` | `margin-top` | `6px` | `var(--space-3)` |
| `.nav` | `gap` | `10px` | `var(--space-4)` |
| `.nav-button, .secondary-button, .danger-button` | `padding` | `10px 12px` | `var(--space-4) var(--space-5)` |
| `.workspace` | `padding` | `18px` | `var(--space-7)` |
| `.topbar` | `gap` | `18px` | `var(--space-7)` |
| `.topbar` | `margin-bottom` | `18px` | `var(--space-6)` |
| `.topbar` | `padding` | `14px 16px` | `var(--space-5) var(--space-6)` |
| `.topbar h1` | `margin` | `8px 0 0` | `var(--space-4) 0 0` |
| `.topbar-actions` | `gap` | `10px` | `var(--space-4)` |
| `.state-pill` | `padding` | `4px 10px` | `var(--space-2) var(--space-4)` |
| `.close-readiness, .refresh-health` | `padding` | `4px 10px` | `var(--space-2) var(--space-4)` |
| `.metric-grid` | `gap` | `12px` | `var(--space-5)` |
| `.metric-grid` | `margin-bottom` | `18px` | `var(--space-6)` |
| `.metric` | `padding` | `14px` | `var(--space-5)` |
| `.metric-label` | `margin-bottom` | `8px` | `var(--space-4)` |
| `.panel` | `margin-bottom` | `14px` | `var(--space-5)` |
| `.panel` | `padding` | `14px` | `var(--space-5)` |
| `.panel-heading` | `gap` | `12px` | `var(--space-5)` |
| `.panel-heading` | `margin-bottom` | `10px` | `var(--space-4)` |
| `.panel-subheading` | `margin-top` | `10px` | `var(--space-4)` |
| `.inline-actions` | `gap` | `8px` | `var(--space-4)` |
| `.telemetry-grid` | `gap` | `14px` | `var(--space-5)` |
| `.compact-text-block` | `margin-bottom` | `12px` | `var(--space-5)` |
| `.note` | `margin` | `10px 0 0` | `var(--space-4) 0 0` |
| `.form-grid` | `gap` | `12px` | `var(--space-5)` |
| `.form-grid` | `margin-bottom` | `12px` | `var(--space-5)` |
| `.form-grid label, .full-field` | `gap` | `6px` | `var(--space-3)` |
| `.full-field` | `margin-bottom` | `12px` | `var(--space-5)` |
| `.filter-field` | `gap` | `6px` | `var(--space-3)` |
| `.filter-field` | `margin` | `0 0 12px` | `0 0 var(--space-5)` |
| `.option-panel` | `margin-bottom` | `12px` | `var(--space-5)` |
| `.option-panel` | `padding` | `12px` | `var(--space-5)` |
| `.option-panel-heading` | `gap` | `12px` | `var(--space-5)` |
| `.option-panel-heading` | `margin-bottom` | `10px` | `var(--space-4)` |
| `.option-grid` | `gap` | `8px 12px` | `var(--space-4) var(--space-5)` |
| `.option-grid` | `margin-bottom` | `12px` | `var(--space-5)` |
| `.settings-summary-grid` | `gap` | `12px` | `var(--space-5)` |
| `.settings-summary-grid` | `margin` | `12px 0` | `var(--space-5) 0` |
| `.settings-summary-grid h3` | `margin` | `0 0 8px` | `0 0 var(--space-4)` |
| `.check-row` | `gap` | `8px` | `var(--space-4)` |
| `.action-row` | `gap` | `8px` | `var(--space-4)` |
| `.action-row` | `margin-bottom` | `12px` | `var(--space-5)` |
| `.action-row-left` | `margin` | `12px 0 0` | `var(--space-5) 0 0` |
| `.action-group-label` | `margin-right` | `2px` | `var(--space-1)` |
| `th, td` | `padding` | `9px 10px` | `var(--space-4) var(--space-4)` |
| `.table-legend` | `margin` | `8px 0 10px` | `var(--space-4) 0 var(--space-4)` |

### Notes on rounding decisions

- `9px` → `--space-4` (8px): 1px difference, negligible
- `10px` → `--space-4` (8px): used as a tight inset/gap throughout; 8px is correct here
- `14px` → `--space-5` (12px): rounds down; panels feel compact but that is consistent with the dense operator dashboard aesthetic
- `18px` → `--space-6` (16px) or `--space-7` (20px) depending on context: workspace/sidebar/topbar gap uses `--space-7`; margin-below-topbar and metric-grid-margin-bottom use `--space-6`
- `24px` → `--space-8`: exact match

### Verify Task 1

```powershell
$css = "DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\styles.css"

# All spacing declarations must use tokens. Must return 0 results.
$raw = Select-String -Path $css -Pattern '(margin|padding|gap)\s*:' |
  Where-Object {
    $_.Line -notmatch 'var\(--space-' -and
    $_.Line -notmatch ':\s*0'         -and
    $_.Line -notmatch '\bauto\b'      -and
    $_.Line -notmatch '^\s*/\*'
  }
$raw | ForEach-Object { Write-Host "LINE $($_.LineNumber): $($_.Line.Trim())" }
Write-Host "Remaining raw spacing lines: $($raw.Count)"
# Must print 0.
```

---

## Task 2 — Wire primary button class

Three buttons in `index.html` are currently classed as `danger-button` but are the **primary action** on their page. The design reference (Section 7) requires primary actions to use the `.primary-button` class — solid blue, not dark red.

### Pre-check: confirm no JS selects .danger-button to target these buttons

Before changing the class, verify that no JS file uses `.danger-button` as a selector for these specific buttons. They must be referenced by ID in JS.

```powershell
$jsDir = "DesktopApp\mediapipeline_desktop_app\ui_web\static\assets"

# These IDs must be how JS reaches these buttons — not via class
Select-String -Path "$jsDir\*.js" -Pattern 'pipeline-start-button'     # must find references
Select-String -Path "$jsDir\*.js" -Pattern 'settings-save-patch-button' # must find references
Select-String -Path "$jsDir\*.js" -Pattern 'rename-apply-selected-button' # must find references

# .danger-button must NOT appear as a querySelector/getElementById target for these
# (It may appear for CSS purposes — that is fine. Only selectors matter.)
Select-String -Path "$jsDir\*.js" -Pattern 'querySelector.*danger-button|getElementsByClassName.*danger'
# Review any results. If none of them are targeting the three buttons above, proceed.
```

If any of the three buttons is reached via `.danger-button` in JS rather than by ID, stop and report — do not change the class until the JS is also updated.

### The three changes

| Button ID | Current class | New class | Page | Location hint |
|---|---|---|---|---|
| `pipeline-start-button` | `danger-button` | `primary-button` | Launch | Inside `data-page-panel="launch"` |
| `settings-save-patch-button` | `danger-button` | `primary-button` | Settings | Inside `data-page-panel="settings"` |
| `rename-apply-selected-button` | `danger-button` | `primary-button` | Rename | Inside `data-page-panel="rename"` |

The HTML looks like:
```html
<!-- Before -->
<button id="pipeline-start-button" class="danger-button">Start Pipeline</button>

<!-- After -->
<button id="pipeline-start-button" class="primary-button">Start Pipeline</button>
```

**Do not change the button text. Do not change the id. Do not change any other attribute. Only the class value changes.**

### Verify Task 2

```powershell
$html = "DesktopApp\mediapipeline_desktop_app\ui_web\static\index.html"

# Three buttons must now carry primary-button
Select-String -Path $html -Pattern 'id="pipeline-start-button".*primary-button|primary-button.*id="pipeline-start-button"'
Select-String -Path $html -Pattern 'id="settings-save-patch-button".*primary-button|primary-button.*id="settings-save-patch-button"'
Select-String -Path $html -Pattern 'id="rename-apply-selected-button".*primary-button|primary-button.*id="rename-apply-selected-button"'
# Each must return exactly 1 result.

# None of the three must still carry danger-button
Select-String -Path $html -Pattern 'id="pipeline-start-button".*danger-button|danger-button.*id="pipeline-start-button"'
Select-String -Path $html -Pattern 'id="settings-save-patch-button".*danger-button|danger-button.*id="settings-save-patch-button"'
Select-String -Path $html -Pattern 'id="rename-apply-selected-button".*danger-button|danger-button.*id="rename-apply-selected-button"'
# Each must return 0 results.

# Button texts must be unchanged
Select-String -Path $html -Pattern '>Start Pipeline<'
Select-String -Path $html -Pattern '>Save Settings<'
Select-String -Path $html -Pattern '>Submit Rename to Backend<'
# Each must return exactly 1 result.
```

---

## Task 3 — Inventory and log updates

### 3a — DOM ID count

No new `id` attributes are added in Stage 3. Confirm count is unchanged from Stage 2 (955):

```powershell
$html = "DesktopApp\mediapipeline_desktop_app\ui_web\static\index.html"
(Select-String -Path $html -Pattern '\bid="').Count
# Must still be 955. If different, investigate before logging.
```

### 3b — Append to DOC_TOUCH_LOG.md

Append one row after the existing Stage 2 execution row:

```
| 2026-05-16 | V5 UI Stage 3 execution (Codex) — spacing token migration and primary button wiring | `REMEDIATION_CHANGELOG.md` | `WEBVIEW_DOM_ID_INVENTORY.md` (no new IDs — count confirmed 955), `WEBVIEW_GLOBAL_EXPORT_INVENTORY.md` (no JS files touched), `API_ROUTE_INVENTORY.md` (no new routes), `BROWSER_SMOKE_DOES_NOT_MUTATE_MATRIX.md` (no mutation changes), `TEST_COVERAGE_MATRIX.md` (no test changes), `TAURI_WEBVIEW_PARITY_MATRIX.md` (no parity change), `VALIDATION_LADDER_RUNBOOK.md` (no rung changes), `DOCS_INDEX.md` (no new docs) | styles.css: all margin/padding/gap values tokenized — 0 raw px spacing values remain; index.html: pipeline-start-button, settings-save-patch-button, rename-apply-selected-button re-classed from danger-button to primary-button |
```

### 3c — Append to REMEDIATION_CHANGELOG.md

Add a dated H2 entry before the existing 2026-05-16 Stage 1 entry (i.e. at the top of the entry block, newest first). Follow the format used by Stage 1 and Stage 2 entries immediately above.

Minimum content:

```markdown
## 2026-05-16 - V5 UI Stage 3: Spacing Token Migration and Primary Button Wiring

Completed the CSS token migration by tokenizing all spacing values, and wired the primary button class to the three main action buttons.

Changes:

- `styles.css`: All `margin`, `padding`, and `gap` declarations tokenized — 0 raw px spacing values remain; only `0` and `auto` are permitted raw spacing values; full mapping table in `V5_UI_IMPL_STAGE3_CODEX.md`
- `index.html`: `pipeline-start-button` re-classed `danger-button` → `primary-button` (Start Pipeline — primary action on Launch page)
- `index.html`: `settings-save-patch-button` re-classed `danger-button` → `primary-button` (Save Settings — primary action on Settings page)
- `index.html`: `rename-apply-selected-button` re-classed `danger-button` → `primary-button` (Submit Rename to Backend — primary action on Rename page)

Validation:

[Paste Task 1 and Task 2 verification output here]

Regression risk: low. Spacing rounding is within 2px of original values throughout; no layout should break. Button re-classing changes visual treatment from dark-red to solid-blue for three buttons; JS references all three buttons by ID so the class change does not affect behavior.
```

Also update the Full Entry Index count in the Navigation section from `824 entries across 11 days` to `825 entries across 11 days`, and add the Stage 3 entry to the `#### 2026-05-16` list.

---

## Completion checklist

- [ ] Task 1 done — 0 raw px values in `margin`/`padding`/`gap` declarations
- [ ] Task 2 pre-check done — confirmed JS reaches all three buttons by ID, not by `.danger-button` class
- [ ] Task 2 done — 3 buttons carry `primary-button`; 0 of those 3 still carry `danger-button`; button texts unchanged
- [ ] Task 3a done — DOM ID count still 955
- [ ] Task 3b done — DOC_TOUCH_LOG row appended
- [ ] Task 3c done — REMEDIATION_CHANGELOG H2 entry added, entry count updated
- [ ] No `id`, `data-page`, `data-panel-type`, or other attributes changed
- [ ] No button text changed
- [ ] No JS files modified
