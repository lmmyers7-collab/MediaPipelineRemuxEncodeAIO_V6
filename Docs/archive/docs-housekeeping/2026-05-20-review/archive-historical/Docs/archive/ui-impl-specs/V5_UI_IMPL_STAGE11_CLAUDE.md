# V5 UI Implementation — Stage 11 (Claude)

**Owner:** Claude  
**Depends on:** Stages 1–10 verified green and Panel Order Pass applied.  
**Design authority:** `Docs/DesktopApp/docs/V5_UI_DESIGN_REFERENCE.md`  
**Validation:** `DesktopApp/Runtime/Python/python.exe -m pytest tests/ --tb=line -q` — must report 1183 passed 0 failed after every task.

---

## Context

This stage closes the five items that were declared out of scope after Stage 2. Two of the five are already done by prior stages — they are acknowledged and dismissed here. Three remain and are implemented below.

### Status of the five deferred items

| Deferred item | Status | Closed by |
|---|---|---|
| Spacing migration | ✅ Done | Stage 3 — all raw `margin`/`padding`/`gap` px values replaced with `--space-*` tokens; only legitimate zero resets remain |
| Primary button application (3 named buttons) | ✅ Done | Stage 3 — `pipeline-start-button`, `settings-save-patch-button`, `rename-apply-selected-button` re-classed |
| Evidence panel tint | ✅ Done | Stage 4 — `.panel[data-panel-type="evidence"]` rule applies `--evidence-bg` background and `3px --purple-700` left border universally; all evidence panels covered |
| Empty state design | ⚠️ Partial | Stage 6 added the CSS component; Stage 7 placed the HTML. **Remaining:** icon and context-specific copy — covered here in Task 1 and Task 2 |
| Light mode option | ❌ Not done | Covered here in Task 3 |

There is also one button that was missed in Stage 3's primary-button pass, identified during Stage 11 audit — covered in Task 0.

---

## Task 0 — Missed primary button: Save Schedule

**Problem:** `schedule-editor-save-button` ("Save Schedule") uses `danger-button`. Saving a schedule is a positive, reversible write action — not destructive. `danger-button` red colouring implies "this will destroy something," which misrepresents the action and adds visual noise to the Schedule page.

**Action:** In `index.html`, change the single class attribute on this button.

**Locate:**
```powershell
Select-String -Path "DesktopApp\mediapipeline_desktop_app\ui_web\static\index.html" `
  -Pattern 'schedule-editor-save-button'
```

**Change:**
```html
<!-- Before -->
<button type="button" id="schedule-editor-save-button" class="danger-button">Save Schedule</button>

<!-- After -->
<button type="button" id="schedule-editor-save-button" class="primary-button">Save Schedule</button>
```

**Buttons left as danger-button (intentional):**

| Button | Reason |
|---|---|
| `pending-drain-button` (Publish Parked Outputs) | Moves files out of the pending queue permanently — irreversible |
| `audit-start-button` (Start Audit) | Starts a pipeline run — irreversible mid-run |
| `rerun-start-button` (Start CSV Rerun) | Starts a pipeline run — irreversible mid-run |
| `backend-shutdown-button` (Request Backend Shutdown) | Terminates the backend process |

**Verification:**
```powershell
# Confirm schedule button now uses primary-button
Select-String -Path "DesktopApp\mediapipeline_desktop_app\ui_web\static\index.html" `
  -Pattern 'schedule-editor-save-button.*primary-button|primary-button.*schedule-editor-save-button'
# Must return 1 result

# Confirm no unintended additional primary-button appearances
(Select-String -Path "DesktopApp\mediapipeline_desktop_app\ui_web\static\index.html" `
  -Pattern 'class="primary-button"').Count
# Should now be 4 (was 3 after Stage 3)
```

---

## Task 1 — Empty state icon

**Problem:** Every empty state currently renders two text lines with no visual anchor. The component needs an icon above the label to give the eye something to land on before reading. A CSS `::before` pseudo-element avoids adding any new DOM nodes.

**Files:** `styles.css` only. No HTML changes in this task.

**Action:** Add a `::before` rule to `.empty-state` immediately after the existing `.empty-state` block.

**Locate the insertion point:**
```css
/* Current state — add ::before immediately after this closing brace */
.empty-state {
  display: flex;
  …
}
```

**Add:**
```css
.empty-state::before {
  content: "—";
  display: block;
  font-size: var(--text-xl);
  font-weight: 300;
  color: var(--grey-600);
  margin-bottom: var(--space-3);
  letter-spacing: 0.08em;
}
```

Rationale: an em-dash at `text-xl` (24px) reads as a visual separator rather than meaningful content. It is neutral enough to work for any table type (errors, files, jobs, events) without making a domain-specific claim. A heavier symbol (✕, ○) would imply state.

**Verify (no test change expected — pseudo-element is not DOM):**
```powershell
Select-String -Path "DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\styles.css" `
  -Pattern '\.empty-state::before'
# Must return 1
```

---

## Task 2 — Empty state copy (context-specific)

**Problem:** All 97 empty-state instances use identical copy: `"No items"` / `"Items will appear here when available."` This tells the operator nothing about *why* there are no items or *what to do*.

**Files:** `index.html` only.

**Approach:** Replace the label and hint text on each empty-state div. The table that owns the empty state is always the sibling `<table>` immediately before the `.empty-state` div inside the same `.table-wrap`. Use the nearest `<h2>` or `<h3>` heading as the identifier.

The 97 instances fall into four categories. Resolve all instances in each category at once using search-and-replace where the copy is identical, then handle the individually-worded ones.

---

### Category A — Status / readiness tables (read-only, populated by backend on refresh)

These tables are populated on page load and are empty only when no backend data has loaded yet or the backend reports nothing.

**Label:** `No data loaded`  
**Hint:** `Refresh to load data from the backend.`

**Tables in this category:**

| Heading | ID in tbody |
|---|---|
| System Readiness | `daily-driver-rows` |
| Readiness Checklist | `daily-driver-rows` (second instance is the checklist detail table) |
| Cross-page Conflict Summary | `cross-page-conflict-rows` |
| Evidence Correlation | `cross-page-sample-rows` |
| Validation Worksheet | various SV worksheet rows |
| Evidence Handoff, Evidence Gaps | SV sub-panel rows |
| Pilot Worksheets | SV pilot rows |
| Acceptance Gate, Accepted Records | SV acceptance rows |
| Queue readiness sub-panels | readiness row tables |
| Run History (Queue + Completed) | run-history row tables |
| First Response (Diagnostics) | `diagnostics-first-response-rows` |
| Launch sub-panel readiness tables | launch-scope, preflight rows |
| Rename Apply Status | `rename-readiness-rows` |
| Name Overrides table | `rename-table` (the bulk-override table) |
| Settings policy/change tables | staged-changes, active-policy rows |
| Network lifecycle/evidence tables | network-lifecycle, evidence-checklist rows |
| Workers Worker State table | worker-state rows |
| Maintenance history table | maintenance-history rows |
| Report Paths table | report-path rows |
| Report Locations table | report-location rows |
| Audit Log table | audit-entry rows |
| Failure Details table | failure-detail rows |
| Command history tables (Diagnostics, Launch, Settings) | command-history rows |
| Command Detail sub-tables | impact-summary, related-evidence, resolution rows |
| GPU Details table | `gpu-rows` |
| Active Jobs table | `active-job-detail-rows` |
| Progress Detail table | `progress-detail-rows` |

---

### Category B — Selection-driven tables (populated only after the operator selects a row)

These tables are empty until the operator selects a row in a sibling table.

**Label:** `No row selected`  
**Hint:** `Select a row above to see details here.`

**Tables in this category:**

| Heading | Context |
|---|---|
| Selected File (Queue) | appears when queue row is selected |
| Selected File (Completed) | appears when output-files row is selected |
| Selected Item (Pending Publish) | appears when pending row is selected |
| Artifact Detail (Diagnostics) | appears when state-summary row is selected |
| Command Detail sub-tables | appears when command-history row is selected |

---

### Category C — Live-signal tables (empty means the system is healthy or idle)

For these tables, empty is the *good* state. The copy should communicate that.

**Label:** `No items`  
**Hint:** Varies — see table below.

| Heading | Label | Hint |
|---|---|---|
| Errors (Diagnostics) | `No errors recorded` | `Errors appear here when the backend reports a failure.` |
| Events (Diagnostics) | `No events recorded` | `Events appear here when the backend emits state changes.` |
| Flagged Items (Queue) | `Nothing flagged` | `Flagged rows appear here when the backend marks a file blocked.` |
| Flagged Items (Completed) | `Nothing flagged` | `Flagged rows appear here when output validation finds a problem.` |
| Flagged Items (Pending Publish) | `Nothing flagged` | `Flagged rows appear here when the drain guard blocks a publish.` |
| Collision Risk (Queue) | `No collisions detected` | `Collision rows appear here when two queue items would write the same output path.` |
| Excluded Files (Queue) | `No exclusions` | `Excluded rows appear here when files are filtered out of the active scope.` |
| Warnings (Reports) | `No warnings` | `Warnings appear here when the backend emits advisory-level signals.` |

---

### Category D — Scope-preview tables (populated after a deliberate operator action)

These tables are empty until the operator triggers a preview or scope calculation.

**Label:** `No preview loaded`  
**Hint:** Varies — see table below.

| Heading | Hint |
|---|---|
| Launch Scope / Launch Checklist sub-panels | `Run a scope check from the Settings Check panel to populate this.` |
| Rename preview table | `Run Preview Rename Plan to populate this.` |
| Staged Changes (Settings) | `Edit a setting and trigger a diff to see staged changes.` |
| Size Check / Size Evidence (Completed) | `Select a completed file to see size comparison data.` |
| Drain Evidence / Drain Scope (Pending Publish) | `A drain operation must run before this populates.` |

---

### Implementation note

Do not attempt a blanket find-and-replace across all 97 instances in one operation — the surrounding context differs between table wrappers. Work page by page:

1. Read the page section from `index.html`.
2. For each `.empty-state` div, identify its category from the table above.
3. Replace the `empty-state-label` and `empty-state-hint` span text.
4. Move to the next page section.

The `data-empty-state="hidden"` attribute and `style="display:none"` must not be changed.

**Verification (after all 97 are updated):**
```powershell
# No generic hint should remain
(Select-String -Path "DesktopApp\mediapipeline_desktop_app\ui_web\static\index.html" `
  -Pattern "Items will appear here when available").Count
# Must be 0

# No generic label should remain
(Select-String -Path "DesktopApp\mediapipeline_desktop_app\ui_web\static\index.html" `
  -Pattern '>No items<').Count
# Must be 0 (the category C "No items" instances are replaced with specific wording above)
```

---

## Task 3 — Light mode token set

**Problem:** The app is hard-coded dark-mode only (`color-scheme: dark` in `:root`). The token system was designed from the start for light-mode compatibility — the `:root` comment explicitly states: *"Token names match the design reference so a future light-mode switch only needs to redefine these values, not any class names."* This task redeems that promise.

**Files:** `styles.css` only. No HTML or JS changes.

**Approach:** Add a `@media (prefers-color-scheme: light)` block that redefines:
1. `color-scheme` (to `light`)
2. The entire grey scale (inverted: grey-900 becomes near-white, grey-50 becomes near-black)
3. `--evidence-bg` (use `--purple-100` as noted in the existing CSS comment)
4. All five shadow tokens (significantly reduced opacity)
5. `--focus-ring` and `--focus-ring-error` (adjust alpha to remain visible on light backgrounds)

Status colors (blue, green, amber, red, purple) do **not** need redefining — their mid-range saturation reads on both dark and light backgrounds. The grey inversion handles all surface, text, and border colours automatically.

**Locate the insertion point:** immediately before the `* { box-sizing: border-box; }` rule, after the closing `}` of `:root`.

**Add this block:**

```css
/* ===== LIGHT MODE — redefines grey scale, shadows, and evidence tint only =====
   Status colours (blue, green, amber, red, purple) are mid-range saturated and
   require no adjustment. All class names and component tokens inherit from :root
   unless listed here.                                                           */
@media (prefers-color-scheme: light) {
  :root {
    color-scheme: light;

    /* Grey scale — inverted from dark-mode values */
    --grey-900: hsl(220, 4%,  95%);
    --grey-800: hsl(220, 5%,  90%);
    --grey-700: hsl(220, 6%,  82%);
    --grey-600: hsl(220, 7%,  70%);
    --grey-500: hsl(220, 8%,  55%);
    --grey-400: hsl(220, 9%,  42%);
    --grey-300: hsl(220, 10%, 30%);
    --grey-200: hsl(220, 11%, 20%);
    --grey-100: hsl(220, 13%, 12%);
    --grey-50:  hsl(220, 15%, 7%);

    /* Evidence panel tint — use light purple on light surfaces */
    --evidence-bg: var(--purple-100);

    /* Shadows — reduced opacity for light backgrounds */
    --shadow-1: 0 1px 2px hsl(220 15% 10% / 0.08);
    --shadow-2: 0 2px 4px hsl(220 15% 10% / 0.10);
    --shadow-3: 0 4px 8px hsl(220 15% 10% / 0.12), 0 1px 3px hsl(220 15% 10% / 0.07);
    --shadow-4: 0 8px 24px hsl(220 15% 10% / 0.14), 0 2px 6px hsl(220 15% 10% / 0.09);
    --shadow-5: 0 16px 48px hsl(220 15% 10% / 0.16), 0 4px 12px hsl(220 15% 10% / 0.10);

    /* Focus rings — slightly higher alpha on light backgrounds */
    --focus-ring:       0 0 0 2px hsl(215, 55%, 56%, 0.35);
    --focus-ring-error: 0 0 0 2px hsl(5,   68%, 48%, 0.35);
  }
}
```

**Additional light-mode rule — text selection:**

The existing `::selection` rule uses `var(--blue-700)` as background and `var(--grey-50)` as text. In light mode, `--grey-50` becomes near-black, which has poor contrast against `--blue-700` (mid-range blue). Add a scoped override after the `@media` block above:

```css
@media (prefers-color-scheme: light) {
  ::selection {
    background: var(--blue-500);
    color: var(--grey-900);
  }
}
```

In light mode: `--blue-500` = hsl(215, 55%, 56%) — a medium-bright blue; `--grey-900` = hsl(220, 4%, 95%) — near-white. Contrast passes WCAG AA.

**Verification:**
```powershell
# Confirm both @media blocks are present
(Select-String -Path "DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\styles.css" `
  -Pattern "prefers-color-scheme: light").Count
# Must be 2 (one for :root redefinitions, one for ::selection)

# Confirm grey inversion is present
Select-String -Path "DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\styles.css" `
  -Pattern '--grey-900: hsl\(220, 4%'
# Must return 2 (one in dark :root, one in light @media)
```

---

## What is not in scope

- Any change to `index.html` beyond Task 0 (Save Schedule button) and Task 2 (empty state copy).
- Any change to `app.js` or any other JS file.
- A `.light-mode` CSS class toggle — this stage uses `prefers-color-scheme` only. A manual toggle button is a future task.
- Per-table icon variants (a different icon for errors vs. files vs. jobs) — the single `::before` em-dash from Task 1 covers all cases.
- Updating backend routes, test assertions, or inventory files — this stage touches no DOM IDs, no exports, no routes, and no test-visible panel text.

---

## Completion checklist

- [ ] Task 0 — `schedule-editor-save-button` uses `class="primary-button"`. `primary-button` count = 4.
- [ ] Task 1 — `.empty-state::before` rule present in `styles.css`.
- [ ] Task 2 — Zero occurrences of `"Items will appear here when available."` in `index.html`. Zero occurrences of `">No items<"` (the category C instances have specific wording).
- [ ] Task 3 — Two `@media (prefers-color-scheme: light)` blocks in `styles.css`. Grey-900 in light block = `hsl(220, 4%, 95%)`.
- [ ] Test suite — `1183 passed 0 failed` (Task 0 changes a button class; Tasks 1–3 are CSS-only and invisible to tests).
