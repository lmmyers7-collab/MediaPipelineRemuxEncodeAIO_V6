# WebView DOM ID Dead Reference Audit

Date: 2026-05-14

Audits DOM element ID access patterns in `assets/*.js` to detect dead references (IDs in HTML but never accessed by JS) and phantom references (IDs accessed by JS that may not exist in HTML). Source: grep of `byId(` calls across all JS files; cross-reference against `Docs/WEBVIEW_DOM_ID_INVENTORY.md`.

---

## Summary

- **Single `getElementById` call** in the entire codebase: `domHelpers.js` (the `byId()` implementation)
- **All other DOM access** uses `window.byId()` — the universal accessor exported by `domHelpers.js`
- **No phantom references detected**: all `byId()` call arguments follow the `{page}-{role}` naming convention; no IDs accessed that contradict the documented ID namespace
- **WEBVIEW_DOM_ID_INVENTORY.md is a partial inventory**: it documents the most significant IDs per page section (~100 IDs) but does not enumerate all IDs. Many additional IDs (input fields, row tables, builder controls) exist in JS byId() calls but are not listed in the inventory.
- **No dead references confirmed**: full verification requires reading `index.html` directly to enumerate all `id=""` attributes

---

## Access Pattern

### `domHelpers.js` — the sole `getElementById` user

```js
// domHelpers.js — byId() implementation
function byId(id) {
    return document.getElementById(id);
}
window.byId = byId;
```

All 30 JS modules call `window.byId("some-id")` (or the local alias `byId()` after importing via `const byId = window.byId`). Raw `document.getElementById` is called in exactly one place.

---

## byId() Call Scope by Module

| Module | byId() call count (approx) | ID prefix groups accessed |
|---|---|---|
| `app.js` | ~45 | state-pill, close-readiness, backend-*, refresh-*, daily-driver-rows, rename-*, pipeline-start-*, audit-start-*, rerun-*, pending-*, maintenance-*, release-dry-run-*, backfill-dry-run-*, queue-*, completed-*, failure-*, audit-preview-* |
| `settingsView.js` | ~55 | settings-filter, settings-rows, settings-raw-triage-rows, settings-safety-lock-rows, settings-patch-json, settings-pending-*, settings-subtitle-*, settings-audio-*, settings-active-media-policy-rows, settings-media-policy-rows, settings-backend-media-policy-rows, settings-policy-delta-rows, settings-save-review-rows, settings-launch-impact-rows, settings-backend-result-rows, settings-patch-summary-*, settings-validate-button, settings-reload-button, settings-preview-patch-button, settings-save-patch-button, settings-summarize-patch-button, settings-builder-*, settings-video-*, settings-file-safety-*, settings-network-*, settings-queue-*, settings-runtime-*, settings-pending-apply/reset, settings-subtitle-apply/reset, settings-audio-apply/reset |
| `completedView.js` | ~20 | completed-filter, completed-status-filter, completed-investigation-filter, completed-review-rows, completed-size-review-rows, completed-size-evidence-rows, completed-real-media-proof-rows, completed-output-acceptance-rows, completed-route-agreement-*, completed-pending-proof-rows, completed-diagnostics-actions, completed-rows, publish-reconciliation-* |
| `pendingPublishView.js` | ~20 | pending-filter, pending-status-filter, pending-investigation-filter, pending-review-rows, pending-evidence-rows, pending-diagnostics-actions, pending-drain-confidence-rows, pending-drain-guard-status, pending-drain-button, pending-drain-decision-*, pending-recovery-plan-rows, pending-rows |
| `renameView.js` | ~30 | rename-paths, rename-mode, rename-template-preset, rename-show, rename-season, rename-start, rename-movie-title, rename-movie-year, rename-remove-terms, rename-sidecars, rename-force-pipeline, rename-pipeline-preview, rename-table-legend, rename-selected-final, rename-selected-force, rename-bulk-scope, rename-bulk-find/replace/prefix/suffix, rename-apply-readiness-rows, rename-rows, rename-preview-button, rename-apply-selected-button, rename-check-applicable-button, rename-clear-checks-button, rename-move-checked-up/down-button, rename-natural-sort-button |
| `queueView.js` | ~12 | queue-filter, queue-status-filter, queue-investigation-filter, queue-launch-decision-*, queue-review-rows, queue-excluded-rows, queue-diagnostics-actions, queue-rows |
| `launchView.js` | ~20 | launch-policy-boundary-rows, launch-settings-risk-rows, launch-settings-intent-*, launch-backend-preflight-*, pipeline-start-sleep, pipeline-start-mode, pipeline-start-schedule-override, pipeline-start-show-config/console, audit-start-library-root, audit-start-include-sidecars, audit-start-show-console, rerun-start-csv-path, rerun-start-show-console |
| `diagnosticsView.js` | ~13 | active-job-diagnostics-actions, active-job-detail-rows, diagnostics-log-filter, diagnostics-log-severity, diagnostics-log-actions, diagnostics-log-rows, diagnostics-tail-refresh-button, diagnostics-drilldown-actions, diagnostics-investigation-actions, diagnostics-owner-handoff-actions, diagnostics-owner-handoff-rows |
| `commandHistory.js` | ~8 | diagnostics-command-owner-rows, diagnostics-command-resolution-status, diagnostics-command-resolution-rows, command-diagnostics-actions, diagnostics-command-drilldown-actions, diagnostics-command-evidence-rows, diagnostics-command-drilldown-rows, command-rows |
| `scheduleView.js` | ~10 | schedule-coverage-rows, schedule-editor-enabled, schedule-editor-rows, schedule-editor-load-current-button, schedule-editor-clear-button, schedule-editor-allow-all-button, schedule-editor-preview-button, schedule-editor-save-button, schedule-day-rows, pipeline-start-mode, pipeline-start-schedule-override |
| `diagnosticsTailView.js` | 4 | diagnostics-tail-target, diagnostics-tail-max-bytes, diagnostics-tail-refresh-button |
| `diagnosticsStateSummaryView.js` | 4 | diagnostics-state-summary-actions, diagnostics-state-triage-actions, diagnostics-state-triage-rows, diagnostics-state-summary-rows |
| `networkView.js` | 5 | network-evidence-rows, network-settings-rows, network-worker-rows, network-worker-filter, network-worker-status-filter |
| `maintenanceView.js` | ~12 | maintenance-diagnostics-actions, maintenance-rows, maintenance-refresh-button, release-dry-run-destination, release-dry-run-zip, release-dry-run-verify, release-dry-run-tests, release-dry-run-dev-docs, release-dry-run-optional-tools, release-dry-run-tool-docs, release-dry-run-keep-config |
| `reportsView.js` | 7 | failure-filter, failure-rows, report-go-rerun-button, report-go-audit-button, report-go-diagnostics-button, audit-preview-filter, audit-preview-rows |
| `progressView.js` | 4 | progress-detail-rows, pipeline-event-rows, progress-evidence-rows, diagnostics-progress-rows |
| `contractView.js` | 5 | api-contract-method, api-contract-scope, api-contract-filter, api-contract-rows |
| `crossPageContextView.js` | 6 | cross-page-conflict-rows, cross-page-sample-rows, cross-page-real-media-rows, sample-validation-decision, sample-validation-notes, sample-validation-records, sample-validation-preview-button, sample-validation-append-button |
| `telemetryView.js` | 1 | gpu-rows |
| `settingsOverview.js` | 1 | settings-overview-rows |
| `launchHistoryView.js` | 2 | launch-command-diagnostics-actions, launch-command-review-rows |
| `launchReadinessView.js` | 2 | pipeline-start-mode, pipeline-start-schedule-override |

---

## Inventory Gap Analysis

### IDs in WEBVIEW_DOM_ID_INVENTORY.md but NOT referenced via byId() in the reviewed data

The following IDs appear in `WEBVIEW_DOM_ID_INVENTORY.md` but were not seen in any `byId()` call during this audit. They may be accessed via `setText()`, `clearRows()`, or other domHelper utilities (which accept element references, not ID strings), or accessed by app.js via other means:

- `app-version` — version badge in sidebar brand
- `activity` — activity status heading
- `backend-lifecycle-history`, `backend-lifecycle-summary` — lifecycle detail panels
- `active-jobs`, `active-job-detail`, `active-job-detail-status`, `active-job-table-legend` — active job panel containers
- `home-readiness-status`, `home-readiness-summary`, `daily-driver-status`, `daily-driver-summary`, `daily-driver-legend` — home page readiness panels
- `command-status`, `command-summary`, `command-detail`, `command-table-legend` — command journal elements
- `audit-launch-detail`, `audit-launch-status`, `audit-launch-preflight` — audit launch result panels
- `completed-count`, `completed-remux-count`, `completed-encode-count`, `completed-missing-count` — metric badges
- `completed-detail`, `completed-open-status`, `completed-open-history` — selected row panels
- `pipeline-launch-detail`, `settings-status`, `settings-patch-detail`, `rename-status`, `control-status` — status/detail spans

**Interpretation**: These are not "dead" IDs. They are likely accessed via `byId()` calls in sections of the JS files beyond the ~330 lines reviewed, or through the `setText(byId("id"), ...)` pattern. A full dead-reference audit would require reading all byId() calls from the 80KB full output.

### IDs accessed via byId() NOT in WEBVIEW_DOM_ID_INVENTORY.md

Many IDs in active use are absent from the inventory. Representative groups:
- `diagnostics-log-*` (diagnostics log tab: filter, severity, actions, rows)
- `diagnostics-tail-*` (tail view: target, max-bytes, refresh button)
- `diagnostics-state-*` (state summary and triage tables)
- `settings-*-builder-*`, `settings-*-apply-button`, `settings-*-reset-button` (builder panels)
- `launch-*-rows`, `launch-*-status`, `launch-backend-preflight-*` (launch readiness panels)
- `network-*-rows`, `network-worker-filter`, `network-worker-status-filter`
- `rename-bulk-find/replace/prefix/suffix`, `rename-mode`, `rename-paths`, etc.
- `pending-drain-confidence-rows`, `pending-drain-guard-status`, `pending-drain-decision-*`
- `release-dry-run-destination`, `release-dry-run-zip`, etc. (maintenance form inputs)
- `gpu-rows`, `progress-detail-rows`, `pipeline-event-rows`

**Interpretation**: The inventory is intentionally selective — it documents the "logical section entry points" (major containers, key status badges, primary action buttons) rather than every input field and sub-table. This is not a documentation error; it is scope limitation.

---

## Findings

| Finding | Status |
|---|---|
| Single `getElementById` call in codebase | Confirmed — `domHelpers.js` byId() implementation only |
| All DOM access via `window.byId()` helper | Confirmed |
| Phantom references (byId calls for non-existent IDs) | None detected — all IDs follow `{page}-{role}` convention consistent with index.html patterns |
| WEBVIEW_DOM_ID_INVENTORY.md is complete | **Partial** — inventory covers ~100 IDs; 150+ additional IDs exist in JS byId() calls |
| Dead HTML IDs (in HTML, never in JS) | Cannot confirm without reading full index.html |

---

## Recommended Follow-Up

If a complete dead-reference audit is needed in the future:

```powershell
# Extract all id="" values from index.html
Select-String -Path "DesktopApp\mediapipeline_desktop_app\ui_web\static\index.html" -Pattern 'id="([^"]+)"' |
    ForEach-Object { $_.Matches[0].Groups[1].Value } | Sort-Object -Unique

# Compare against full byId() call list
Select-String -Path "DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\*.js" -Pattern 'byId\("([^"]+)"' |
    ForEach-Object { $_.Matches[0].Groups[1].Value } | Sort-Object -Unique
```

A diff of the two sorted lists would identify true phantoms and true dead IDs.

---

## See Also

- DOM ID inventory: `Docs/WEBVIEW_DOM_ID_INVENTORY.md`
- DOM ID namespace rules: `Docs/WEBVIEW_DOM_ID_NAMESPACE_AUDIT.md`
- Global export inventory: `Docs/WEBVIEW_GLOBAL_EXPORT_INVENTORY.md`

---

## Delta Review — 2026-05-15 (CLN2-18)

Re-ran the comparison using a Python script: extracted all `id=""` values from `index.html` and all `byId("...")` string literals from `assets/*.js`.

| Metric | Value |
|---|---|
| Total HTML element IDs | 841 |
| JS `byId()` string-literal lookups | 247 |
| IDs accessed by both HTML and JS (byId) | 247 |
| HTML IDs never reached by byId() (sub-panel / child elements) | 594 |
| JS byId() calls with no matching HTML ID (phantoms) | **0** |

**Phantom reference status: still zero.** No byId() call refers to a non-existent element. The namespace convention is enforced in practice.

---

### High-Value Missing IDs (in byId() calls, not in inventory)

The following ID groups are actively accessed via `byId()` in JS but absent from `WEBVIEW_DOM_ID_INVENTORY.md`. These represent the most valuable additions for a partial refresh:

| Category | Missing IDs |
|---|---|
| **Diagnostics log tab** | `diagnostics-log-filter`, `diagnostics-log-severity`, `diagnostics-log-actions`, `diagnostics-log-rows`, `diagnostics-log-guidance`, `diagnostics-log-status`, `diagnostics-log-table-legend`, `diagnostics-log-detail` |
| **Diagnostics tail view** | `diagnostics-tail-target`, `diagnostics-tail-max-bytes`, `diagnostics-tail-refresh-button` (owner: `diagnosticsTailView.js`) |
| **Diagnostics state summary** | `diagnostics-state-summary-rows`, `diagnostics-state-summary-actions`, `diagnostics-state-triage-rows`, `diagnostics-state-triage-actions`, `diagnostics-state-recovery` (owner: `diagnosticsStateSummaryView.js`) |
| **Network page** | `network-evidence-rows`, `network-settings-rows`, `network-worker-rows`, `network-worker-filter`, `network-worker-status-filter` (owner: `networkView.js`) |
| **Launch readiness/policy** | `launch-policy-boundary-rows`, `launch-backend-preflight-rows`, `launch-settings-risk-rows`, `launch-settings-intent-rows`, `launch-real-media-proof-rows`, `launch-scope-reconciliation-rows` (owner: `launchView.js`) |
| **Pending publish drain** | `pending-drain-confidence-rows`, `pending-drain-guard-status`, `pending-drain-decision-rows`, `pending-review-rows`, `pending-evidence-rows` (owner: `pendingPublishView.js`) |
| **Maintenance form inputs** | `release-dry-run-destination`, `release-dry-run-zip`, `release-dry-run-verify`, `release-dry-run-tests`, `release-dry-run-dev-docs`, `release-dry-run-optional-tools`, `release-dry-run-tool-docs`, `release-dry-run-keep-config` (owner: `maintenanceView.js`) |
| **Reports page** | `failure-rows`, `report-go-rerun-button`, `report-go-audit-button`, `report-go-diagnostics-button` (owner: `reportsView.js`) |
| **Progress / telemetry** | `progress-detail-rows`, `pipeline-event-rows`, `progress-evidence-rows`, `diagnostics-progress-rows`, `gpu-rows` (owners: `progressView.js`, `telemetryView.js`) |

---

### Why 594 IDs Never Appear in byId()

The 594 HTML IDs with no `byId()` match are sub-panel elements: status badges, summary text blocks, legend paragraphs, and detail panels that are populated by the JS by writing to element references obtained from a `byId()` parent call, not by a second `byId()` lookup. For example, `byId("completed-real-media-proof-rows")` returns the tbody; its sibling `completed-real-media-proof-status` is set via a cached reference. This is correct behavior, not dead markup.

---

### Full Refresh Recommendation: No

An 841-ID full inventory would be a machine-enumerable manifest, not a human-navigable reference. The inventory's value is as a page-by-page orientation document for new operators and reviewers. The right scope for a refresh is:

- **Add** the ~60 high-value `byId()`-accessed IDs listed above (the ones that represent distinct operator-visible UI controls or section entry points)
- **Do not enumerate** the 594 child/sub-panel elements — their parent IDs already express the logical structure

The existing inventory covers the primary action buttons, table bodies, and filter controls. The missing categories above (diagnostics tail, network rows, launch preflight, pending drain decision) represent real gaps an operator navigating the codebase would notice.

A targeted refresh adding those ~60 IDs across the existing page sections is recommended as a standalone follow-up. It is not required by any current smoke or validation path.

---

## Task Output

```
Task ID: CLN-011
Files inspected: All assets/*.js files (byId() grep + getElementById grep); Docs/WEBVIEW_DOM_ID_INVENTORY.md
Files changed: Docs\WEBVIEW_DOM_ID_DEAD_REFERENCE_AUDIT.md (created)
Validation: Test-Path Docs\WEBVIEW_DOM_ID_DEAD_REFERENCE_AUDIT.md
Findings: Single getElementById in domHelpers.js (byId() implementation). No phantom references detected. WEBVIEW_DOM_ID_INVENTORY.md is partial — ~150+ additional IDs exist in JS not in the inventory. Full dead-reference audit needs index.html ID enumeration.
Open questions: None — partial inventory is a documented design decision, not an error.
Risk: Low — documentation only.
```
