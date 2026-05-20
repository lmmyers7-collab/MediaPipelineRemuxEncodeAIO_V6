# V5 UI Implementation — Stage 1 (Codex)

**Owner:** Codex
**Depends on:** Nothing. This is the first stage.
**Blocks:** `V5_UI_IMPL_STAGE2_CLAUDE.md` — Claude cannot start Stage 2 until all tasks here are marked Done and verified.
**Design authority:** `Docs/DesktopApp/docs/V5_UI_DESIGN_REFERENCE.md`

---

## Context

The V5 WebView UI has been audited against the design reference. This document contains all the mechanical text changes that result from that audit. No behavior changes, no CSS changes, no JS logic changes. Every task here is a find-and-replace or a label correction in one of two files:

- `index.html` — the single-page HTML for the WebView
- No other files should be modified in Stage 1

**Critical constraint:** Do NOT rename or change any of the following — they are wired to backend routing and JS behavior:

- `data-page` attribute values (`home`, `live`, `queue`, `completed`, `pending`, `rename`, `launch`, `reports`, `schedule`, `network`, `maintenance`, `diagnostics`, `settings`)
- `data-page-panel` attribute values
- Any `id="..."` attribute
- Any `class="..."` attribute
- Any `data-state`, `data-label`, or other data attribute
- The `<title>` tag content (`MediaPipeline V5`) — leave it alone

Only the visible text inside elements changes. Nothing else.

---

## File path

```
DesktopApp\mediapipeline_desktop_app\ui_web\static\index.html
```

---

## Task 1 — Nav button labels

The sidebar nav has 13 buttons. Four of them have wrong labels. Change only those four. Do not touch the others.

| Find (exact text) | Replace with | Button `data-page` |
|---|---|---|
| `>Home<` | `>Dashboard<` | `data-page="home"` |
| `>Live<` | `>Telemetry<` | `data-page="live"` |
| `>Audit / Reports<` | `>Reports<` | `data-page="reports"` |
| `>Network<` | `>Workers<` | `data-page="network"` |

The nav buttons look like this in the HTML:
```html
<button class="nav-button is-active" data-page="home">Home</button>
```

After change:
```html
<button class="nav-button is-active" data-page="home">Dashboard</button>
```

**Verify:**
```powershell
$html = "DesktopApp\mediapipeline_desktop_app\ui_web\static\index.html"
# These four must be present after the change
Select-String -Path $html -Pattern '>Dashboard<'
Select-String -Path $html -Pattern '>Telemetry<'
Select-String -Path $html -Pattern '>Reports<'
Select-String -Path $html -Pattern '>Workers<'
# These four must NOT be present
Select-String -Path $html -Pattern '>Home<'
Select-String -Path $html -Pattern '>Live<'
Select-String -Path $html -Pattern 'Audit / Reports'
# Note: ">Network<" may still appear in panel headings — only the nav button matters here.
# Verify the nav button specifically:
Select-String -Path $html -Pattern 'data-page="network">Network<'
# Must return zero results.
```

---

## Task 2 — Panel headings

The canonical panel names are defined in `Docs/DesktopApp/docs/V5_UI_DESIGN_REFERENCE.md` Section 8. That document contains a table for each of the 13 pages with two columns: "Canonical name" (what it should be) and "Notes" (what it was before, prefixed with "Was").

For each page in Section 8, read the panel name table and apply every rename to `index.html`. The HTML panel headings are inside `<h2>` and `<h3>` tags inside `<div class="panel-heading">` elements.

Example — what a panel heading looks like in HTML:
```html
<div class="panel-heading">
  <h2>Operator Readiness</h2>
  <strong id="home-readiness-status">Checking</strong>
</div>
```

After renaming per Section 8 (Dashboard page, "Operator Readiness" → "System Readiness"):
```html
<div class="panel-heading">
  <h2>System Readiness</h2>
  <strong id="home-readiness-status">Checking</strong>
</div>
```

### Rules for this task

1. Only change the text content of `<h2>` and `<h3>` elements that are direct children of `<div class="panel-heading">` divs.
2. Do not change any `id` attributes on sibling elements.
3. Do not change any `<h2>` or `<h3>` text that does not appear in Section 8's tables. If a heading is not listed in Section 8, leave it unchanged and note it at the end of this task.
4. Where Section 8 shows a subheading with a `—` prefix (e.g., `— Conflict Summary`), that means it is an `<h3>` inside a `panel-subheading` div. The `—` is not part of the heading text — strip it.
5. Work page by page in the order they appear in Section 8.

### Verification

After completing all heading renames, verify a sample from each page:

```powershell
$html = "DesktopApp\mediapipeline_desktop_app\ui_web\static\index.html"

# Dashboard page — sample checks
Select-String -Path $html -Pattern '<h2>System Readiness</h2>'        # was: Operator Readiness
Select-String -Path $html -Pattern '<h2>Readiness Checklist</h2>'     # was: Daily-Driver Checklist
Select-String -Path $html -Pattern '<h2>Settings Health</h2>'         # was: Saved Settings Trust
Select-String -Path $html -Pattern '<h2>Tool Status</h2>'             # was: External Dependency Digest
Select-String -Path $html -Pattern '<h2>Current Run</h2>'             # was: Active Work
Select-String -Path $html -Pattern '<h2>Pipeline Overview</h2>'       # was: Cross-Page Context

# Queue page
Select-String -Path $html -Pattern '<h2>Queue</h2>'                   # was: Queue Preview
Select-String -Path $html -Pattern '<h3>Readiness</h3>'               # was: Queue Readiness
Select-String -Path $html -Pattern '<h3>Launch Scope</h3>'            # was: Backend Launch Scope Preview
Select-String -Path $html -Pattern '<h3>Flagged Items</h3>'           # was: Operator Review Board

# Output page (data-page-panel="completed")
Select-String -Path $html -Pattern '<h2>Output Files</h2>'            # was: Completed Jobs
Select-String -Path $html -Pattern '<h3>Size Check</h3>'              # was: Size Growth Review
Select-String -Path $html -Pattern '<h3>Evidence Packet</h3>'         # was: Selected Pilot Evidence Packet
Select-String -Path $html -Pattern '<h3>Output Verification</h3>'     # was: Final Output Trust Walkthrough

# Publish page (data-page-panel="pending")
Select-String -Path $html -Pattern '<h3>Drain Evidence</h3>'          # was: Drain Evidence Board
Select-String -Path $html -Pattern '<h3>Drain Scope</h3>'             # was: Backend Drain Scope Preview
Select-String -Path $html -Pattern '<h3>Flagged Items</h3>'           # was: Operator Review Board

# Launch page
Select-String -Path $html -Pattern '<h2>Start Pipeline</h2>'          # was: Pipeline Launch
Select-String -Path $html -Pattern '<h3>Schedule Alignment</h3>'      # was: Timing Trust
Select-String -Path $html -Pattern '<h3>Preflight Check</h3>'         # was: Backend Launch Preflight

# Settings page
Select-String -Path $html -Pattern '<h2>Settings Editor</h2>'         # was: Structured Patch Builder
Select-String -Path $html -Pattern '<h2>Config Health</h2>'           # was: Saved Settings Trust
Select-String -Path $html -Pattern '<h2>Change Preview</h2>'          # was: Patch Preview
Select-String -Path $html -Pattern '<h2>Advanced Keys</h2>'           # was: Raw-Key Triage

# Diagnostics page
Select-String -Path $html -Pattern '<h2>First Response</h2>'          # was: First Response Checklist
Select-String -Path $html -Pattern '<h2>Shutdown Readiness</h2>'      # was: Close Readiness
Select-String -Path $html -Pattern '<h2>Log Access</h2>'              # was: Log Triage

# Workers page (data-page-panel="network")
Select-String -Path $html -Pattern '<h2>Mode Status</h2>'             # was: Network Mode
Select-String -Path $html -Pattern '<h2>Worker State</h2>'            # was: Worker Runtime State

# Maintenance page
Select-String -Path $html -Pattern '<h2>System Health</h2>'           # was: Environment Health
Select-String -Path $html -Pattern '<h2>Tool Status</h2>'             # was: Toolchain Readiness

# Telemetry page (data-page-panel="live")
Select-String -Path $html -Pattern '<h2>CPU Usage</h2>'               # was: CPU
Select-String -Path $html -Pattern '<h2>NVENC Usage</h2>'             # was: NVENC
Select-String -Path $html -Pattern '<h2>RAM Usage</h2>'               # was: RAM
Select-String -Path $html -Pattern '<h2>Monitoring Status</h2>'       # was: Telemetry Readiness

# Reports page
Select-String -Path $html -Pattern '<h2>Report Summary</h2>'          # was: Report Triage
Select-String -Path $html -Pattern '<h2>Audit Log</h2>'               # was: Latest Audit Rows
Select-String -Path $html -Pattern '<h2>Report Locations</h2>'        # was: Report Roots

# Rename page
Select-String -Path $html -Pattern '<h2>Rename Plan</h2>'             # was: Rename Preview
Select-String -Path $html -Pattern '<h2>Apply Status</h2>'            # was: Apply Readiness

# Schedule page
Select-String -Path $html -Pattern '<h2>Current Schedule</h2>'        # was: Schedule Status
Select-String -Path $html -Pattern '<h2>Edit Schedule</h2>'           # was: Schedule Editor
Select-String -Path $html -Pattern '<h2>Launch Windows</h2>'          # was: Launch Guidance
```

Every result above must return exactly one match. Zero results means the rename did not apply or the wrong name was used.

**Also verify that old names are gone — spot check:**
```powershell
$html = "DesktopApp\mediapipeline_desktop_app\ui_web\static\index.html"

# These old names must no longer appear as heading text
# (They may still appear in comments or id attributes — only check h2/h3 content)
$oldNames = @(
    '<h2>Operator Readiness</h2>',
    '<h2>Daily-Driver Checklist</h2>',
    '<h2>External Dependency Digest</h2>',
    '<h2>Cross-Page Context</h2>',
    '<h2>Queue Preview</h2>',
    '<h2>Completed Jobs</h2>',
    '<h2>Pending Publish</h2>',
    '<h2>Pipeline Launch</h2>',
    '<h2>Structured Patch Builder</h2>',
    '<h2>Environment Health</h2>',
    '<h2>First Response Checklist</h2>',
    '<h2>Close Readiness</h2>',
    '<h2>Log Triage</h2>',
    '<h2>Network Mode</h2>',
    '<h2>Rename Preview</h2>',
    '<h2>Schedule Status</h2>',
    '<h3>Operator Review Board</h3>',
    '<h3>Backend Launch Scope Preview</h3>',
    '<h3>Backend Drain Scope Preview</h3>',
    '<h3>Size Growth Review</h3>',
    '<h3>Drain Evidence Board</h3>',
    '<h3>Final Output Trust Walkthrough</h3>',
    '<h3>Selected Pilot Evidence Packet</h3>',
    '<h3>Timing Trust</h3>',
    '<h3>Backend Launch Preflight</h3>',
    '<h3>Raw-Key Triage</h3>'
)
foreach ($old in $oldNames) {
    $result = Select-String -Path $html -Pattern ([regex]::Escape($old))
    if ($result) { Write-Host "STILL PRESENT: $old" }
}
# Must print nothing.
```

---

## Task 3 — Button labels

Find every button in `index.html` whose label is a single generic word that fails Rule 7 of the design reference. Rewrite it to name the action and its scope.

The specific changes required are listed below. These are the only button label changes in Stage 1. Do not change any button whose label is not in this list.

| Find (exact button text) | Replace with | Location hint |
|---|---|---|
| `>Save<` (inside Settings page) | `>Save Settings<` | Inside `data-page-panel="settings"` |
| `>Apply<` (inside Rename page) | `>Submit Rename to Backend<` | Inside `data-page-panel="rename"` |
| `>Preview<` (inside Rename page) | `>Preview Rename Plan<` | Inside `data-page-panel="rename"` |
| `>Append<` (inside Home page sample validation) | `>Append Validation Record<` | Inside `data-page-panel="home"` |
| `>Accept<` (inside Home page sample validation) | `>Accept Selected Sample<` | Inside `data-page-panel="home"` |

**Important:** Use the `data-page-panel` context to scope your search. A button labeled "Save" inside the settings section is different from any "Save" that might appear elsewhere. Only change buttons within the stated page panel.

**Verify:**
```powershell
$html = "DesktopApp\mediapipeline_desktop_app\ui_web\static\index.html"

Select-String -Path $html -Pattern '>Save Settings<'
Select-String -Path $html -Pattern '>Submit Rename to Backend<'
Select-String -Path $html -Pattern '>Preview Rename Plan<'
Select-String -Path $html -Pattern '>Append Validation Record<'
Select-String -Path $html -Pattern '>Accept Selected Sample<'
# Each must return exactly one result.

# Generic labels that must now be absent from the changed locations.
# Run these and confirm the results are from OTHER pages, not the ones listed above.
Select-String -Path $html -Pattern '(?<!\w)>Save<(?!\w)'
Select-String -Path $html -Pattern '(?<!\w)>Apply<(?!\w)'
```

---

## Task 4 — data-panel-type attributes

Every `<section class="panel">` must carry a `data-panel-type` attribute set to either `evidence` or `interactive`.

This is the most important structural change in Stage 1. The classification rules are:

- **`evidence`** — the panel is read-only. It displays backend-authored information. The only permitted button inside an evidence panel is a tertiary Copy button that writes to the clipboard. No `apiPost` calls.
- **`interactive`** — the panel contains operator controls: inputs, primary or secondary buttons, form elements, or controls that trigger backend commands.

### Classification rules (apply in order)

1. If a panel contains an `<input>`, a `<select>`, a `<textarea>`, or a form, it is `interactive`.
2. If a panel contains a `<button>` that is NOT a Copy or clipboard button, it is `interactive`.
3. If a panel contains only `<pre>`, `<table>`, `<p>`, `<strong>`, or a Copy button, it is `evidence`.
4. If a panel heading appears in Section 8 with the label "(read-only)" in its notes, it is `evidence`.
5. If you cannot determine the type from the above rules, mark it `evidence` and add a `<!-- REVIEW: panel type uncertain -->` comment on the same line for Claude to resolve in Stage 2.

### How to apply

Change:
```html
<section class="panel">
```

To one of:
```html
<section class="panel" data-panel-type="evidence">
<section class="panel" data-panel-type="interactive">
```

**Verify:**
```powershell
$html = "DesktopApp\mediapipeline_desktop_app\ui_web\static\index.html"

# Every panel must have the attribute. This must return zero results.
Select-String -Path $html -Pattern '<section class="panel">' |
  Where-Object { $_.Line -notmatch 'data-panel-type=' }

# Count how many panels were classified as each type.
$ev = (Select-String -Path $html -Pattern 'data-panel-type="evidence"').Count
$in = (Select-String -Path $html -Pattern 'data-panel-type="interactive"').Count
$un = (Select-String -Path $html -Pattern 'REVIEW: panel type uncertain').Count
Write-Host "evidence: $ev  interactive: $in  uncertain: $un"
# Report these counts. Claude will review the uncertain ones in Stage 2.
```

---

## Completion checklist

Before handing off to Stage 2, confirm all of the following:

- [ ] Task 1 done — 4 nav labels updated, verified by grep
- [ ] Task 2 done — all panel headings renamed per Section 8, sample verification passed, old-names grep returns nothing
- [ ] Task 3 done — 5 button labels updated, verified by grep
- [ ] Task 4 done — all `<section class="panel">` elements have `data-panel-type`, zero unattributed panels remain
- [ ] No `data-page`, `id`, `class`, or other attributes were changed
- [ ] No CSS files were modified
- [ ] No JS files were modified
- [ ] Uncertain panel type count reported (may be zero)

When all boxes are checked, Stage 2 (`V5_UI_IMPL_STAGE2_CLAUDE.md`) can begin.
