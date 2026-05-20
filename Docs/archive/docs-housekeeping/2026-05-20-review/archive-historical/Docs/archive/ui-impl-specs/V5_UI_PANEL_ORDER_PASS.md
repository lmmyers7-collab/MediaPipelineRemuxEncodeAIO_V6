# V5 UI Panel Order Pass - Implementation Plan

**Owner:** Codex  
**Date:** 2026-05-16  
**Target file:** `DesktopApp/mediapipeline_desktop_app/ui_web/static/index.html`  
**Status:** Plan only. Do not implement until this plan is approved.

---

## Objective

Reorder existing WebView panels so each affected tab reads in the operator's natural workflow:

1. Current state and critical signals first.
2. Evidence before the action that depends on it.
3. Controls next to the status they control.
4. Problem signals before reference, history, and file-navigation panels.
5. Advanced/reference material lower than normal operational material.

This is an HTML ordering pass only. It does not rename panels, change behavior, change styling, or add/remove controls.

---

## Hard Constraints

- Modify only `DesktopApp/mediapipeline_desktop_app/ui_web/static/index.html`.
- Do not modify CSS or JS files.
- Do not change visible text.
- Do not change any existing `id`, `class`, `type`, `scope`, `data-*`, `style`, or other attribute values.
- Do not add or remove existing panels, controls, tables, empty-state blocks, or rows.
- Do not reorder metric strips.
- Move whole structural blocks only:
  - For top-level pages, move whole `<section class="panel" ...>...</section>` blocks.
  - For the Rename page, move whole internal blocks inside the existing single `Rename Plan` panel. Details are called out separately below.
- Preserve nested contents exactly. The moved block carries all nested tables, buttons, empty states, advanced wrappers, and script-targeted IDs with it.

---

## Scope

The ordering audit recommends changes on six tabs:

1. Dashboard (`data-page-panel="home"`)
2. Telemetry (`data-page-panel="live"`)
3. Rename (`data-page-panel="rename"`)
4. Reports (`data-page-panel="reports"`)
5. Workers (`data-page-panel="network"`)
6. Diagnostics (`data-page-panel="diagnostics"`)

No order change is planned for:

- Queue
- Completed / Output
- Pending Publish
- Launch
- Schedule
- Maintenance
- Settings

Reason: those pages either already follow the evidence-to-action flow, or their questionable ordering only appears inside advanced/reference sections and is not worth structural churn in this pass.

---

## Current Top-Level Panel Inventory

Generated from the current `index.html` after Stages 1-9.

### Dashboard

Metric strip remains first and is not moved.

| Current # | Panel | Type |
|---:|---|---|
| 1 | System Readiness | evidence |
| 2 | Readiness Checklist | evidence |
| 3 | Settings Health | evidence |
| 4 | Tool Status | evidence |
| 5 | Current Run | evidence |
| 6 | Pipeline Overview | interactive |
| 7 | Runtime Files | interactive |
| 8 | Status | interactive |
| 9 | Run Progress | evidence |
| 10 | Recent Events | evidence |
| 11 | Recent Commands | evidence |

### Telemetry

| Current # | Panel | Type |
|---:|---|---|
| 1 | CPU Usage | evidence |
| 2 | NVENC Usage | evidence |
| 3 | RAM Usage | evidence |
| 4 | Monitoring Status | evidence |
| 5 | GPU Details | evidence |

### Rename

Important: Rename is one top-level `<section class="panel" data-panel-type="interactive">`, not seven separate top-level panels. The order below refers to major internal blocks inside that one panel.

| Current # | Internal block | Notes |
|---:|---|---|
| 1 | Rename Plan | Main heading, form fields, movie filters, preview button, summary blocks |
| 2 | Pipeline Context | `panel-heading sub-panel-heading` plus `rename-pipeline-handoff` |
| 3 | Review | `panel-heading sub-panel-heading` plus `rename-review-board` |
| 4 | Selection Check | `panel-heading sub-panel-heading` plus `rename-selection-audit` |
| 5 | Apply Status | heading, readiness table, empty state, legend, applicable-row action buttons |
| 6 | Name Overrides | heading, bulk override form/actions, rename table, empty state, selected override controls, apply button, detail |
| 7 | Last Result | heading plus advanced Outcome Review block and apply history/detail |

### Reports

Metric strip remains first and is not moved.

| Current # | Panel | Type |
|---:|---|---|
| 1 | Report Summary | interactive |
| 2 | Report Paths | evidence |
| 3 | Failures | interactive |
| 4 | Audit Log | interactive |
| 5 | Report Locations | evidence |
| 6 | Recently Opened | evidence |
| 7 | Warnings | evidence |

### Workers

Metric strip remains first and is not moved.

| Current # | Panel | Type |
|---:|---|---|
| 1 | Mode Status | interactive |
| 2 | Open History | evidence |
| 3 | Readiness | evidence |
| 4 | Lifecycle Handoff | evidence |
| 5 | Evidence Checklist | evidence |
| 6 | State Files | evidence |
| 7 | Worker State | interactive |
| 8 | Network Config | evidence |
| 9 | API Contract | evidence |

### Diagnostics

| Current # | Panel | Type |
|---:|---|---|
| 1 | Triage Overview | evidence |
| 2 | First Response | evidence |
| 3 | Investigation Path | evidence |
| 4 | Page Handoff | evidence |
| 5 | Artifact Detail | evidence |
| 6 | State Summary | evidence |
| 7 | Shutdown Readiness | evidence |
| 8 | Backend State | interactive |
| 9 | Current Progress | evidence |
| 10 | Log Access | interactive |
| 11 | Command History | evidence |
| 12 | Command Detail | evidence |
| 13 | Errors | evidence |
| 14 | Events | evidence |
| 15 | Active Jobs | evidence |
| 16 | Pipeline Log | evidence |
| 17 | File Log | interactive |
| 18 | Launch Log | evidence |
| 19 | Open Files | interactive |
| 20 | API Contract | interactive |

---

## Proposed Changes

### Task 1 - Dashboard Order

**Problem:** The live-run cluster is split. `Current Run` is separated from `Status` controls and `Run Progress` by `Pipeline Overview` and `Runtime Files`. `Pipeline Overview` contains many validation/transition subsections and is better as a lower reference block.

**Implementation:** Move whole top-level panel `<section>` blocks inside `data-page-panel="home"`. Do not move the metric grid.

| Position | Current | Suggested |
|---:|---|---|
| 1 | System Readiness | System Readiness |
| 2 | Readiness Checklist | Readiness Checklist |
| 3 | Settings Health | Current Run |
| 4 | Tool Status | Status |
| 5 | Current Run | Run Progress |
| 6 | Pipeline Overview | Settings Health |
| 7 | Runtime Files | Tool Status |
| 8 | Status | Runtime Files |
| 9 | Run Progress | Recent Events |
| 10 | Recent Events | Recent Commands |
| 11 | Recent Commands | Pipeline Overview |

**Move units:**

- `Current Run` panel moves from 5 to 3.
- `Status` panel moves from 8 to 4.
- `Run Progress` panel moves from 9 to 5.
- `Pipeline Overview` panel moves from 6 to 11.
- `Settings Health`, `Tool Status`, `Runtime Files`, `Recent Events`, and `Recent Commands` shift around those moves without internal edits.

---

### Task 2 - Telemetry Order

**Problem:** `Monitoring Status` validates whether the telemetry feed is trustworthy, but it appears after CPU/NVENC/RAM readings.

**Implementation:** Move the whole `Monitoring Status` panel before the three usage panels.

| Position | Current | Suggested |
|---:|---|---|
| 1 | CPU Usage | Monitoring Status |
| 2 | NVENC Usage | CPU Usage |
| 3 | RAM Usage | NVENC Usage |
| 4 | Monitoring Status | RAM Usage |
| 5 | GPU Details | GPU Details |

---

### Task 3 - Rename Internal Order

**Problem:** Context and override configuration appear after the main form. The operator should first see whether the pipeline context permits rename work, then configure any overrides, then use the rename form/action flow.

**Implementation:** This is not a top-level panel move. The Rename page has one large top-level panel. Move whole internal blocks within that one panel.

| Position | Current internal block | Suggested internal block |
|---:|---|---|
| 1 | Rename Plan | Pipeline Context |
| 2 | Pipeline Context | Name Overrides |
| 3 | Review | Rename Plan |
| 4 | Selection Check | Selection Check |
| 5 | Apply Status | Review |
| 6 | Name Overrides | Apply Status |
| 7 | Last Result | Last Result |

**Move units:**

- `Pipeline Context` block:
  - Starts at `<div class="panel-heading sub-panel-heading">` containing `<h2>Pipeline Context</h2>`.
  - Includes the following `pre id="rename-pipeline-handoff"` only.
- `Name Overrides` block:
  - Starts at `<div class="panel-heading sub-panel-heading">` containing `<h2>Name Overrides</h2>`.
  - Includes the bulk override form, bulk action row, `rename-bulk-edit-summary`, rename table and empty state, `rename-table-legend`, selected final-name override form, selected override action row, apply button, and `rename-detail`.
  - Ends immediately before the `Last Result` heading.
- `Rename Plan` block:
  - Starts with the page's main `<div class="panel-heading">` containing `<h2>Rename Plan</h2>`.
  - Includes form fields, movie filters, sidecar/pipeline preview options, Preview Rename Plan action, `rename-summary`, and `rename-batch-safety`.
  - Ends immediately before the current `Pipeline Context` heading.
- `Selection Check`, `Review`, `Apply Status`, and `Last Result` move as complete internal blocks, preserving all nested IDs, tables, empty-state blocks, buttons, and advanced wrappers.

**Important:** The `Last Result` block contains a nested `<div data-advanced>` for `Outcome Review`; keep that advanced wrapper with `Last Result`.

---

### Task 4 - Reports Order

**Problem:** `Warnings` is a problem-signal panel, but it is currently last, after reference/file-navigation panels.

**Implementation:** Move whole top-level panel `<section>` blocks inside `data-page-panel="reports"`. Do not move the metric grid.

| Position | Current | Suggested |
|---:|---|---|
| 1 | Report Summary | Report Summary |
| 2 | Report Paths | Failures |
| 3 | Failures | Warnings |
| 4 | Audit Log | Audit Log |
| 5 | Report Locations | Report Paths |
| 6 | Recently Opened | Report Locations |
| 7 | Warnings | Recently Opened |

---

### Task 5 - Workers Order

**Problem:** `Readiness` and `Worker State` are operationally more urgent than `Open History` and reference panels. They should be near `Mode Status`.

**Implementation:** Move whole top-level panel `<section>` blocks inside `data-page-panel="network"`. Do not move the metric grid.

| Position | Current | Suggested |
|---:|---|---|
| 1 | Mode Status | Mode Status |
| 2 | Open History | Readiness |
| 3 | Readiness | Worker State |
| 4 | Lifecycle Handoff | Network Config |
| 5 | Evidence Checklist | Open History |
| 6 | State Files | Lifecycle Handoff |
| 7 | Worker State | Evidence Checklist |
| 8 | Network Config | State Files |
| 9 | API Contract | API Contract |

---

### Task 6 - Diagnostics Order

**Problem:** Raw live signals (`Errors`, `Events`, `Active Jobs`) are buried after investigation/history panels. They should appear directly after `Triage Overview`, which remains the synthesized top-level diagnosis.

**Implementation:** Move whole top-level panel `<section>` blocks inside `data-page-panel="diagnostics"`.

| Position | Current | Suggested |
|---:|---|---|
| 1 | Triage Overview | Triage Overview |
| 2 | First Response | Errors |
| 3 | Investigation Path | Events |
| 4 | Page Handoff | Active Jobs |
| 5 | Artifact Detail | First Response |
| 6 | State Summary | Current Progress |
| 7 | Shutdown Readiness | Shutdown Readiness |
| 8 | Backend State | State Summary |
| 9 | Current Progress | Artifact Detail |
| 10 | Log Access | Investigation Path |
| 11 | Command History | Log Access |
| 12 | Command Detail | Command History |
| 13 | Errors | Command Detail |
| 14 | Events | Pipeline Log |
| 15 | Active Jobs | File Log |
| 16 | Pipeline Log | Launch Log |
| 17 | File Log | Page Handoff |
| 18 | Launch Log | Backend State |
| 19 | Open Files | Open Files |
| 20 | API Contract | API Contract |

**Note:** `Page Handoff` and `Backend State` are reference/advanced-style panels in the current workflow even if their current markup does not expose `data-advanced` in the top-level extractor. They move below the normal investigation sequence but above utility/file panels.

---

## Implementation Sequence

1. Snapshot current invariants:
   - DOM ID count.
   - Page marker count.
   - Top-level panel order for scoped pages.
   - Empty-state/table-wrap counts.
2. Reorder Dashboard top-level panel blocks.
3. Verify Dashboard heading order and ID count.
4. Reorder Telemetry top-level panel blocks.
5. Verify Telemetry heading order and ID count.
6. Reorder Rename internal blocks.
7. Verify Rename internal heading order, IDs, button texts, and table/empty-state counts.
8. Reorder Reports top-level panel blocks.
9. Verify Reports heading order and ID count.
10. Reorder Workers top-level panel blocks.
11. Verify Workers heading order and ID count.
12. Reorder Diagnostics top-level panel blocks.
13. Verify Diagnostics heading order and ID count.
14. Run final global verification.

---

## Verification Plan

Use PowerShell from the repository root.

### 1. DOM and marker invariants

```powershell
$htmlPath = "DesktopApp\mediapipeline_desktop_app\ui_web\static\index.html"
$html = Get-Content $htmlPath -Raw

(Select-String -Path $htmlPath -Pattern '\bid="').Count
# Expected: 955

(Select-String -Path $htmlPath -Pattern 'data-page-panel=').Count
# Expected: 13

(Select-String -Path $htmlPath -Pattern 'class="empty-state"').Count
# Expected: equals table-wrap count

(Select-String -Path $htmlPath -Pattern 'class="table-wrap').Count
# Expected: equals empty-state count
```

### 2. Scoped top-level panel order check

```powershell
$htmlPath = "DesktopApp\mediapipeline_desktop_app\ui_web\static\index.html"
$html = [IO.File]::ReadAllText((Resolve-Path $htmlPath))
$pageRegex = [regex]'(?s)<section class="page[^"]*" data-page-panel="(?<page>[^"]+)">(?<body>.*?)(?=\n      <section class="page|\n    </main>)'
$panelRegex = [regex]'(?s)<section class="panel"[^>]*data-panel-type="(?<type>[^"]+)"[^>]*>.*?<div class="[^"]*\bpanel-heading\b[^"]*">\s*<(?<tag>h[23])>(?<heading>[^<]+)</\k<tag>>'

foreach ($page in @("home","live","reports","network","diagnostics")) {
  $match = $pageRegex.Matches($html) | Where-Object { $_.Groups["page"].Value -eq $page }
  Write-Host "--- $page ---"
  $i = 0
  foreach ($panel in $panelRegex.Matches($match.Groups["body"].Value)) {
    $i++
    Write-Host ("{0}. {1}" -f $i, $panel.Groups["heading"].Value)
  }
}
```

Expected orders are the target tables above.

### 3. Rename internal order check

```powershell
$htmlPath = "DesktopApp\mediapipeline_desktop_app\ui_web\static\index.html"
$html = [IO.File]::ReadAllText((Resolve-Path $htmlPath))
$page = [regex]::Match($html, '(?s)<section class="page" data-page-panel="rename">(?<body>.*?)(?=\n      <section class="page|\n    </main>)').Groups["body"].Value
[regex]::Matches($page, '<h2>[^<]+</h2>|<h3>[^<]+</h3>') |
  ForEach-Object { $_.Value }
```

Expected first major headings:

1. `Pipeline Context`
2. `Name Overrides`
3. `Rename Plan`
4. `Selection Check`
5. `Review`
6. `Apply Status`
7. `Last Result`
8. `Outcome Review`

### 4. Global safety checks

```powershell
$htmlPath = "DesktopApp\mediapipeline_desktop_app\ui_web\static\index.html"

# ID count unchanged
(Select-String -Path $htmlPath -Pattern '\bid="').Count

# Button labels from prior stages still present
Select-String -Path $htmlPath -Pattern '>Start Pipeline<'
Select-String -Path $htmlPath -Pattern '>Save Settings<'
Select-String -Path $htmlPath -Pattern '>Submit Rename to Backend<'

# Stage 5/7 invariants still true
(Select-String -Path $htmlPath -Pattern '<button' | Where-Object { $_.Line -notmatch 'type=' }).Count
(Select-String -Path $htmlPath -Pattern '<th(\s|>)' | Where-Object { $_.Line -notmatch 'scope=' }).Count
(Select-String -Path $htmlPath -Pattern 'class="table-wrap').Count
(Select-String -Path $htmlPath -Pattern 'class="empty-state"').Count

# Stage 9 invariant remains true
$withTabindex = (Select-String -Path $htmlPath -Pattern 'data-selectable-row="true".*tabindex="0"|tabindex="0".*data-selectable-row="true"').Count
$total = (Select-String -Path $htmlPath -Pattern 'data-selectable-row="true"').Count
Write-Host "Selectable row tabindex match: $($withTabindex -eq $total)"
```

### 5. Optional runtime tests

Run the relevant UI/backend test ladder if time permits. Do not hard-code a pass count in the plan; use the current suite output as the source of truth.

```powershell
DesktopApp\Runtime\Python\python.exe -m pytest tests/ --tb=line -q
```

---

## Acceptance Criteria

- Only `index.html` changes during implementation.
- The six scoped pages match the target orders above.
- DOM ID count remains `955`.
- Page marker count remains `13`.
- No existing text changes.
- No existing `id`, `class`, `type`, `scope`, `data-*`, or `style` attributes change.
- Table/empty-state counts remain equal.
- Buttons still all have `type=`.
- Real `<th>` elements still all have `scope=`.
- No JS or CSS files are modified.

---

## Open Decision Before Implementation

Confirm whether the Rename target should be:

1. **Strict context-first:** `Pipeline Context -> Name Overrides -> Rename Plan -> Selection Check -> Review -> Apply Status -> Last Result`
2. **Form-first with context immediately above validation:** `Pipeline Context -> Rename Plan -> Name Overrides -> Selection Check -> Review -> Apply Status -> Last Result`

This plan uses option 1 because it follows evidence/configuration/action most strictly, but option 2 may feel more natural if `Name Overrides` is mostly a post-preview override tool rather than pre-action configuration.
