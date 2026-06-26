# Split Plan - styles.components.css

Date: 2026-06-25
Status: planning only
Change packet: MP-CHANGE-2026-0625-003

## Target

Split:

```text
apps/desktop/webview/static/assets/styles.components.css
```

Current measured shape:

| Metric | Count |
|---|---:|
| Lines | 5,611 |
| Top-level rule blocks | 807 |
| Selector arms, comma-split | 1,082 |
| Top-level media/support blocks | 3 |

This is the first split because it owns shared components and many current tests
read it directly. Stabilizing the test-helper pattern here makes the later
pages and queue splits safer.

## Current Selector Families

Current high-volume selector families:

| Selector family | Approx selector arms | Current line range | Notes |
|---|---:|---:|---|
| `completed-*` | 162 | 1110-4414 | Completed current-output, selected-output, proof, review, and table evidence styling. |
| `pipeline-*` | 118 | 154-5275 | Pipeline state, controller, launch mode, scope, compact gate, log-window styling. |
| `progress-*` | 85 | 345-967 | Progress rows, bars, phase/status detail, running-state UI. |
| `settings-*` | 73 | 2168-3778 | Save review dialog and shared settings builder component rules. |
| `schedule-*` | 65 | 4769-5080 | Schedule editor panel, status strip, time rail, block grid, action controls. |
| `panel-*` | 59 | 8-2163 | Shared panel base, evidence/interactivity badges, headings. |
| `telemetry-*` | 59 | 1448-1701 | Telemetry grid, operator state, trust strip, KPI grid. |
| `launch-*` | 44 | 1928-4039 | Launch history, command history, command status, scope/controller helpers. |
| `pending-*` | 42 | 4435-4648 | Pending Publish action center and decision controls. |
| `metrics-*` | 36 | 435-592 | Metrics chart rows and source-backfill display. |
| table/data/workflow selectors | 40+ | 3907-4757 | Shared table wrappers, enhanced table behavior, workflow table sizing. |

## Target Child Files

Create only files that receive moved rules in the current phase. The final
target shape should be:

```text
apps/desktop/webview/static/assets/styles.components.css
apps/desktop/webview/static/assets/styles/components/base-panels.css
apps/desktop/webview/static/assets/styles/components/progress-live.css
apps/desktop/webview/static/assets/styles/components/review-metrics.css
apps/desktop/webview/static/assets/styles/components/output-overview.css
apps/desktop/webview/static/assets/styles/components/telemetry.css
apps/desktop/webview/static/assets/styles/components/lifecycle-diagnostics.css
apps/desktop/webview/static/assets/styles/components/launch-history.css
apps/desktop/webview/static/assets/styles/components/settings-builders.css
apps/desktop/webview/static/assets/styles/components/completed-output.css
apps/desktop/webview/static/assets/styles/components/data-tables.css
apps/desktop/webview/static/assets/styles/components/pending-action-center.css
apps/desktop/webview/static/assets/styles/components/schedule-editor.css
apps/desktop/webview/static/assets/styles/components/empty-state.css
apps/desktop/webview/static/assets/styles/components/responsive.css
```

`styles.components.css` should become an import-only wrapper after the final
phase:

```css
@import url("./styles/components/base-panels.css");
@import url("./styles/components/progress-live.css");
@import url("./styles/components/review-metrics.css");
@import url("./styles/components/output-overview.css");
@import url("./styles/components/telemetry.css");
@import url("./styles/components/lifecycle-diagnostics.css");
@import url("./styles/components/launch-history.css");
@import url("./styles/components/settings-builders.css");
@import url("./styles/components/completed-output.css");
@import url("./styles/components/data-tables.css");
@import url("./styles/components/pending-action-center.css");
@import url("./styles/components/schedule-editor.css");
@import url("./styles/components/empty-state.css");
@import url("./styles/components/responsive.css");
```

Do not move component rules into `styles.pages.css`, `styles.queue.css`, or
`styles.controls.css` during this split. That is a separate cascade decision.

## Phase 0 - Baseline And Test Helper

Before moving selectors:

1. Capture `git status --short`.
2. Capture current selector families with the same analyzer used for this pack
   or an equivalent top-level rule/selector inventory.
3. Add or reuse a recursive CSS import resolver for tests.
4. Update direct component CSS tests to read resolved CSS where the assertion is
   about selectors, not about parent wrapper import order.
5. Add a static assertion that nested component CSS import paths resolve under
   `apps/desktop/webview/static/assets`.

Minimum validation before selector movement:

```powershell
$py = ".\apps\desktop\runtime\Python\python.exe"
& $py -m unittest tests.webview.test_webview_css_design_tokens -q
& $py -m unittest tests.webview.test_webview_dropdown_remediation_static -q
& $py -m unittest tests.python.desktop.test_application_facade_web_static_shell -q
& $py -m unittest tests.python.desktop.test_api_static_files_policy -q
```

Exit criteria:

- Tests pass while `styles.components.css` still contains the original rules.
- The test helper can resolve import wrappers but does not weaken selector
  assertions.

## Phase 1 - Shared Base, Panels, Metrics, Choices

Move the top shared component rules that are least page-specific:

| Move to | Rule families |
|---|---|
| `styles/components/base-panels.css` | `.metric-grid`, `.metric`, `.panel`, evidence/interactive panel styles, panel headings, evidence badges, enhanced choice source/group/card rules. |
| `styles/components/review-metrics.css` | `.review-tile-*`, `.metrics-chart-*`, shared metric cards not tied to one page. |

Keep declarations byte-for-byte unless formatting is necessary for the move.
Preserve original order within the child files.

Validation after phase:

```powershell
& $py -m unittest tests.webview.test_webview_css_design_tokens -q
& $py -m unittest tests.python.desktop.test_application_facade_web_static -q
```

Rollback:

- Restore moved blocks to their original location in `styles.components.css`.
- Remove the new child imports and files from this phase only.

## Phase 2 - Progress, Live, Telemetry, Lifecycle, Diagnostics

Move state/evidence display rules:

| Move to | Rule families |
|---|---|
| `styles/components/progress-live.css` | `.progress-*`, `.live-*`, progress bars, running state rows, progress detail text. |
| `styles/components/telemetry.css` | `.telemetry-*`, canvas state rules that belong only to telemetry, KPI/trust strips. |
| `styles/components/lifecycle-diagnostics.css` | `.lifecycle-*`, `.diagnostic-*`, `.prose-*`, `.log-block`, `.status-block`, diagnostic callouts. |

Stop if a moved rule is also used by Queue file-overrides or Settings page
specific selectors; keep shared rules in components rather than duplicating.

Validation after phase:

```powershell
& $py -m unittest tests.webview.test_webview_css_design_tokens -q
& $py -m unittest tests.python.desktop.test_metrics_feature -q
& $py -m unittest tests.webview.test_webview_schedule_smoke -q
```

Browser validation if any declarations change:

```powershell
.\ops\scripts\smoke\Test-WebViewBrowserHomeLiveStateSmoke.ps1
.\ops\scripts\smoke\Test-WebViewBrowserTelemetrySmoke.ps1
```

## Phase 3 - Launch And Pipeline Controller Components

Move launch/pipeline components that are still shared component styling:

| Move to | Rule families |
|---|---|
| `styles/components/launch-history.css` | `.launch-command-history`, `.launch-history-*`, launch command result/status strips. |
| `styles/components/output-overview.css` | `.output-overview-*`, selected-output overview shared by Completed output panels. |
| `styles/components/completed-output.css` | `.completed-current-*`, `.completed-selected-*`, completed status/proof/review component strips. |

Do not move Launch page tab or Settings page tab rules from `styles.pages.css`
in this component phase.

Validation after phase:

```powershell
& $py -m unittest tests.webview.test_webview_css_design_tokens -q
& $py -m unittest tests.python.desktop.test_application_facade_web_static -q
& $py -m unittest tests.webview.test_webview_browser_launch_queue_readiness_smoke -q
```

If browser smoke prerequisites are unavailable, record the skip and run the
static Launch/Completed tests available in this environment.

## Phase 4 - Settings Builder Shared Components

Move settings component rules that support builders, dialogs, options, form
grids, and save-review surfaces:

| Move to | Rule families |
|---|---|
| `styles/components/settings-builders.css` | `.settings-save-review-*`, `.settings-handbrake-*`, `.settings-summary-*`, `.settings-tv-library-panel`, `.option-*`, `.form-grid*`, shared setting-builder cards. |

Keep page navigation and page-level wizard/library profile rules in
`styles.pages.css` until the pages split.

Validation after phase:

```powershell
& $py -m unittest tests.webview.test_webview_handbrake_settings_ui -q
& $py -m unittest tests.webview.test_webview_settings_libraries -q
& $py -m unittest tests.webview.test_webview_css_design_tokens -q
```

## Phase 5 - Tables, Pending Publish, Schedule, Empty State

Move remaining large component areas:

| Move to | Rule families |
|---|---|
| `styles/components/data-tables.css` | `.table-*`, `.data-*`, `.workflow-table`, selected-row table rules, completed table scoped rules that are component/table behavior. |
| `styles/components/pending-action-center.css` | `.pending-action-*`, `#pending-action-status`, pending action center layout. |
| `styles/components/schedule-editor.css` | `.schedule-editor-*`, `.schedule-time-*`, `.schedule-block-*`, schedule action/status strips. |
| `styles/components/empty-state.css` | `.empty-state-*`, `.page-panel-empty-*`. |

Validation after phase:

```powershell
& $py -m unittest tests.webview.test_webview_css_design_tokens -q
& $py -m unittest tests.webview.test_webview_schedule_smoke -q
& $py -m unittest tests.python.desktop.test_application_facade_web_static -q
```

Browser validation if layout moved:

```powershell
.\ops\scripts\smoke\Test-WebViewBrowserLargeTableSmoke.ps1
.\ops\scripts\smoke\Test-WebViewBrowserScheduleSmoke.ps1
.\ops\scripts\smoke\Test-WebViewBrowserPendingDrainGuardSmoke.ps1
```

## Phase 6 - Responsive Wrapper

Move the bottom responsive blocks last into
`styles/components/responsive.css`.

Rules:

- Keep breakpoint order exactly as today.
- Keep combined selector lists intact at first, even when they reference
  components owned by different child files.
- Do not split responsive selectors into owner files until after a browser
  screenshot/smoke pass proves no cascade drift.

Validation after phase:

```powershell
& $py -m unittest tests.webview.test_webview_css_design_tokens -q
& $py -m unittest tests.python.desktop.test_application_facade_web_static_shell -q
npm run webview:check
```

Browser validation:

```powershell
.\ops\scripts\smoke\Test-WebViewBrowserLargeTableSmoke.ps1
.\ops\scripts\smoke\Test-WebViewBrowserLayoutManagerSmoke.ps1
```

## Final Component Split Exit Criteria

The component split is complete only when:

- `styles.components.css` is an import-only wrapper.
- All child imports point under `./styles/components/`.
- No child CSS file imports `styles.components.css`.
- Resolved component CSS still contains the selectors currently pinned by tests:
  `.metric-grid`, `.workflow-table`, `.data-table-wrap`,
  `.completed-current-at-a-glance`, `.panel[data-panel-type="evidence"]`,
  `.schedule-time-rail`, and `.telemetry-grid`.
- The direct static asset contract still serves `/assets/styles.components.css`.
- Generated summaries are refreshed for touched CSS and tests.
- The phase packet records validation and rollback notes.

Recommended final validation:

```powershell
& $py -m unittest tests.webview.test_webview_css_design_tokens -q
& $py -m unittest tests.python.desktop.test_application_facade_web_static -q
& $py -m unittest tests.webview.test_webview_handbrake_settings_ui -q
& $py -m unittest tests.webview.test_webview_schedule_smoke -q
& $py -m unittest tests.python.desktop.test_metrics_feature -q
& $py -m unittest tests.python.desktop.test_reports_view_static -q
npm run webview:prework:check
```
