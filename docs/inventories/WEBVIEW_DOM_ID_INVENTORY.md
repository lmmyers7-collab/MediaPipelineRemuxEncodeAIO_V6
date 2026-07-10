# WebView DOM ID Inventory

Date: 2026-07-03

Lists all `id=""` elements defined in the frontend and maps each ID prefix to its owning JavaScript module and WebView page. Source: `apps/desktop/webview/static/index.html` and `assets/*.js`.

Total unique element IDs: 2017. IDs are grouped by prefix (owning module/page).

---

## Naming Convention

IDs follow a `{page-or-section}-{semantic-role}` naming pattern. The prefix identifies the owning page or subsystem. IDs that cross pages (e.g., `command-*`, `diagnostics-*`) are owned by shared modules that render into the DOM of multiple pages.

---

## Topbar / App Shell — owner: `app.js`

These IDs live in the persistent topbar and sidebar, visible on all pages.

| ID | Element | Purpose |
|---|---|---|
| `app-version` | `<div>` | Calendar build badge in sidebar brand |
| `state-pill` | `<div>` | Pipeline state pill in topbar |
| `activity` | `<h1>` | Activity status heading |
| `refresh-health` | `<span>` | Auto-refresh health indicator |
| `close-readiness` | `<span>` | Backend close-readiness badge; click navigates to Diagnostics (S15) |
| `pipeline-sparkline` | `<div>` | Last 20 pipeline events rendered as coloured `.spark` squares (S45); between close-readiness and advanced-toggle |
| `advanced-toggle` | `<button>` | Advanced-mode gate toggle; persisted in localStorage under `mediapipeline-advanced-mode`; sets `aria-pressed` and `.advanced-mode` on `<body>` |
| `refresh-button` | `<button>` | Manual refresh trigger |
| `pipeline-log-window-button` | `<button>` | Toggle the read-only floating Pipeline Log overlay in the persistent app shell |
| `floating-pipeline-log-panel` | `<section>` | Persistent floating Pipeline Log overlay container |
| `floating-pipeline-log-title` | `<h2>` | Accessible title for the floating Pipeline Log overlay |
| `floating-pipeline-log-status` | `<strong>` | Floating Pipeline Log refresh/status badge |
| `floating-pipeline-log-follow` | `<input>` | Follow-tail toggle for the floating Pipeline Log text |
| `floating-pipeline-log-mode` | `<select>` | Activity/raw-tail display mode for the floating Pipeline Log overlay |
| `floating-pipeline-log-refresh-button` | `<button>` | Manually refresh the floating Pipeline Log overlay |
| `floating-pipeline-log-close-button` | `<button>` | Close the floating Pipeline Log overlay |
| `floating-pipeline-log-updated` | `<span>` | Last refresh or stale/error timestamp for the floating Pipeline Log overlay |
| `floating-pipeline-log-text` | `<pre>` | Read-only `/api/diagnostics` pipeline `log_tail` text in the floating overlay |
| `backend-shutdown-button` | `<button>` | Backend graceful shutdown trigger |
| `backend-lifecycle-callout` | `<div>` | Structured backend lifecycle shutdown callout |
| `backend-lifecycle-facts` | `<dl>` | Compact backend lifecycle close-readiness facts |
| `backend-lifecycle-status` | `<strong>` | Shutdown/lifecycle result status |
| `backend-lifecycle-history` | `<div>` | Shutdown history detail |
| `backend-lifecycle-history-rows` | `<tbody>` | Structured backend shutdown command evidence rows |
| `backend-lifecycle-summary` | `<div>` | Lifecycle state summary |
---

## Home Page — owner: `app.js`, `crossPageContextView.js`

| ID | Element | Purpose |
|---|---|---|
| `pipeline-state` | `<strong>` | Pipeline state metric |
| `queue-count` | `<strong>` | Queue count metric |
| `queue-count-detail` | `<span>` | Queue count detail metric |
| `processed-count` | `<strong>` | Processed count metric |
| `failed-count` | `<strong>` | Failed count metric |
| `home-failure-artifact-storage-status` | `<strong>` | Failure artifact total-size metric on Home |
| `home-failure-artifact-storage-detail` | `<span>` | Failure artifact file count, oldest-age, and threshold summary on Home |
| `home-readiness-status` | `<strong>` | Operator readiness status badge |
| `home-readiness-summary` | `<pre>` | Operator readiness text block |
| `home-pending-count` | `<strong>` | Pending parked count metric chip — updated by `renderHomePendingCount` |
| `home-failed-count` | `<strong>` | Failed-file count metric chip — updated by `renderSnapshot` from `snapshot.counts.failed` (swapped for `home-network-role` in UI refactor phase 1) |
| `home-queue-snapshot-status` | `<strong>` | Queue snapshot panel status badge |
| `home-queue-snapshot` | `<pre>` | Queue snapshot compact text block — updated by `renderHomeQueueSnapshot` |
| `home-recent-completed-status` | `<strong>` | Recently completed panel status badge |
| `home-recent-completed-tbody` | `<tbody>` | Recently completed compact table body (last 5 rows) — updated by `renderHomeRecentCompleted` |
| `daily-driver-status` | `<strong>` | Daily-driver checklist status badge |
| `daily-driver-summary` | `<pre>` | Daily-driver checklist summary |
| `daily-driver-rows` | `<tbody>` | Daily-driver checklist table body |
| `daily-driver-legend` | `<p>` | Read-only mutation boundary legend |
| `cross-page-conflict-rows` | `<tbody>` | Cross-page conflict rows |
| `cross-page-sample-rows` | `<tbody>` | Cross-page sample records |
| `cross-page-real-media-rows` | `<tbody>` | Cross-page real-media evidence rows |
| `sample-validation-decision` | input/select | Sample validation decision field |
| `sample-validation-notes` | textarea | Sample validation notes field |
| `sample-validation-execution-status` | `<strong>` | Operator sample execution checklist status |
| `sample-validation-execution-summary` | `<pre>` | Backend-authored sample execution checklist summary |
| `sample-validation-execution-rows` | `<tbody>` | Operator sample execution checklist table body |
| `sample-validation-execution-legend` | `<p>` | Sample execution checklist selectable-row legend |
| `sample-validation-execution-detail` | `<pre>` | Selected sample execution checklist detail |
| `sample-validation-worksheet-status` | `<strong>` | Generated pilot worksheet status badge |
| `sample-validation-worksheet-summary` | `<pre>` | Generated worksheet evidence summary |
| `sample-validation-worksheet-rows` | `<tbody>` | Generated pilot worksheet table body |
| `sample-validation-worksheet-legend` | `<p>` | Generated worksheet selectable-row legend |
| `sample-validation-worksheet-detail` | `<pre>` | Selected generated worksheet detail |
| `sample-validation-records` | `<tbody>` | Sample validation records table body |
| `sample-validation-preview-button` | `<button>` | Trigger `/api/sample-validation/preview` |

---

## Live / Progress Page — owner: `progressView.js`

| ID | Element | Purpose |
|---|---|---|
| `active-jobs` | `<div>` | Active jobs container |
| `active-job-detail` | `<div>` | Selected active job detail panel |
| `active-job-detail-rows` | `<tbody>` | Active job detail table body |
| `active-job-detail-status` | `<strong>` | Active job detail status badge |
| `active-job-diagnostics-actions` | `<div>` | Diagnostics action links for active job |
| `active-job-table-legend` | `<p>` | Legend for active job table |

---

## Queue Page — owner: `queueView.js`

| ID | Element | Purpose |
|---|---|---|
| `queue-filter` | `<input>` | Queue text filter |
| `queue-status-filter` | `<select>` | Queue status filter dropdown |
| `queue-investigation-filter` | `<select>` | Queue investigation filter dropdown |
| `queue-clear-filters-button` | `<button>` | Clear all queue filters |
| `queue-rows` | `<tbody>` | Queue table body |
| `queue-selected-status` | `<strong>` | Selected queue row at-a-glance status |
| `queue-selected-summary` | `<pre>` | Selected queue row at-a-glance summary |
| `queue-backend-scope-status` | `<strong>` | Backend launch scope preview status |
| `queue-backend-scope-summary` | `<pre>` | Backend launch route/scope/filter/selection summary |
| `queue-backend-scope-rows` | `<tbody>` | Backend launch scope evidence rows |
| `queue-backend-scope-legend` | `<p>` | Read-only launch scope boundary legend |

---

## Completed Page — owner: `completedView.js`

| ID | Element | Purpose |
|---|---|---|
| `completed-filter` | `<input>` | Completed text filter |
| `completed-status-filter` | `<select>` | Status filter |
| `completed-investigation-filter` | `<select>` | Investigation filter |
| `completed-clear-filters-button` | `<button>` | Clear all completed filters |
| `completed-rows` | `<tbody>` | Main completed table body |
| `completed-count` | `<strong>` | Total completed count |
| `completed-remux-count` | `<strong>` | Remux count |
| `completed-encode-count` | `<strong>` | Encode count |
| `completed-missing-count` | `<strong>` | Missing output count |
| `completed-current-at-a-glance` | `<div>` | Current output compact operator status strip |
| `completed-current-filter-line` | `<p>` | One-line current output display-filter visibility |
| `completed-current-details` | `<details>` | Verbose current output and filter evidence disclosure |
| `completed-current-summary` | `<pre>` | Verbose current output status evidence |
| `completed-filter-summary` | `<pre>` | Verbose current filter scope summary |
| `completed-selected-status` | `<strong>` | Selected completed row at-a-glance status |
| `completed-selected-summary` | `<pre>` | Selected completed row at-a-glance summary |
| `completed-detail` | `<div>` | Selected row detail panel |
| `completed-open-status` | `<span>` | Open operation status |
| `completed-open-history` | `<div>` | Open operation history |
| `completed-diagnostics-actions` | `<div>` | Diagnostics handoff actions |
| `completed-diagnostics-guidance` | `<div>` | Diagnostics guidance text |
| `completed-diagnostics-status` | `<strong>` | Diagnostics status badge |
| `completed-breakdown` | `<div>` | Completed breakdown panel |
| `completed-breakdown-status` | `<strong>` | Breakdown status |
| `completed-review-board` | `<div>` | Review board panel |
| `completed-review-rows` | `<tbody>` | Review rows |
| `completed-review-legend` | `<p>` | Review legend |
| `completed-review-status` | `<strong>` | Review status |
| `completed-size-evidence-rows` | `<tbody>` | Size evidence rows |
| `completed-size-evidence-status` | `<strong>` | Size evidence status |
| `completed-size-evidence-summary` | `<div>` | Size evidence summary |
| `completed-size-evidence-detail` | `<div>` | Size evidence detail |
| `completed-size-evidence-legend` | `<p>` | Size evidence legend |
| `completed-real-media-proof-rows` | `<tbody>` | Real-media proof ladder rows |
| `completed-real-media-proof-status` | `<strong>` | Proof ladder status |
| `completed-real-media-proof-summary` | `<div>` | Proof ladder summary |
| `completed-real-media-proof-detail` | `<div>` | Proof detail |
| `completed-real-media-proof-legend` | `<p>` | Proof legend |
| `completed-output-acceptance-rows` | `<tbody>` | Output acceptance rows |
| `completed-output-acceptance-status` | `<strong>` | Acceptance status |
| `completed-output-acceptance-summary` | `<div>` | Acceptance summary |
| `completed-output-acceptance-detail` | `<div>` | Acceptance detail |
| `completed-output-acceptance-legend` | `<p>` | Acceptance legend |
| `completed-route-agreement-rows` | `<tbody>` | Route agreement rows |
| `completed-route-agreement-status` | `<strong>` | Route agreement status |
| `completed-route-agreement-summary` | `<div>` | Route agreement summary |
| `completed-route-agreement-detail` | `<div>` | Route agreement detail |
| `completed-route-agreement-legend` | `<p>` | Route agreement legend |
| `completed-pending-proof-rows` | `<tbody>` | Completed-to-pending overlap proof rows |
| `completed-pending-proof-status` | `<strong>` | Overlap proof status |
| `completed-pending-proof-summary` | `<div>` | Overlap proof summary |
| `completed-pending-proof-detail` | `<div>` | Overlap proof detail |
| `completed-pending-proof-legend` | `<p>` | Overlap proof legend |
| `completed-consistency` | `<div>` | Consistency panel |
| `completed-consistency-status` | `<strong>` | Consistency status |
| `completed-integrity` | `<div>` | Integrity panel |
| `completed-integrity-status` | `<strong>` | Integrity status |
| `completed-runtime` | `<div>` | Runtime evidence panel |
| `completed-runtime-status` | `<strong>` | Runtime status |
| `publish-reconciliation-rows` | `<tbody>` | Backend Publish Reconciliation rows |
| `publish-reconciliation-refresh-button` | `<button>` | Trigger `/api/publish-reconciliation` (GET) |

---

## Pending Publish Page — owner: `pendingPublishView.js`

| ID | Element | Purpose |
|---|---|---|
| `pending-filter` | `<input>` | Pending text filter |
| `pending-status-filter` | `<select>` | Status filter |
| `pending-investigation-filter` | `<select>` | Investigation filter |
| `pending-clear-filters-button` | `<button>` | Clear all pending filters |
| `pending-selected-status` | `<strong>` | Selected pending row at-a-glance status |
| `pending-selected-summary` | `<pre>` | Selected pending row at-a-glance summary |
| `pending-open-status` | `<span>` | Open operation status |
| `pending-recovery-plan-status` | `<span>` | Recovery plan status |
| `pending-recovery-plan-selected-button` | `<button>` | Trigger recovery-plan for selected row |
| `pending-recovery-plan-all-button` | `<button>` | Trigger recovery-plan for all |
| `pending-backend-scope-status` | `<strong>` | Backend drain scope preview status |
| `pending-backend-scope-summary` | `<pre>` | Backend drain route/scope/filter/selection summary |
| `pending-backend-scope-rows` | `<tbody>` | Backend drain scope evidence rows |
| `pending-backend-scope-legend` | `<p>` | Read-only drain scope boundary legend |
| `pending-drain-button` | `<button>` | Publish Parked Outputs (guarded) |
| `pending-drain-detail` | `<div>` | Drain request detail |
| `pending-repair-manifest-status` | `<strong>` | Pending manifest repair dry-run/apply status |
| `pending-repair-manifest-dry-run-button` | `<button>` | Trigger selected-row pending manifest repair dry-run |
| `pending-repair-manifest-apply-button` | `<button>` | Trigger fingerprint-gated pending manifest repair apply |
| `pending-reconcile-orphan-dry-run-button` | `<button>` | Trigger selected-row orphan payload reconcile dry-run |
| `pending-reconcile-orphan-apply-button` | `<button>` | Trigger fingerprint-gated orphan payload reconcile apply |
| `pending-reconcile-orphan-status` | `<span>` | Orphan payload reconcile dry-run/apply status |
| `pending-repair-manifest-detail` | `<pre>` | Pending manifest repair evidence detail |
| `pending-repair-manifest-history` | `<pre>` | Pending manifest repair command history |
| `pending-reconcile-orphan-detail` | `<pre>` | Orphan payload reconcile evidence detail |
| `pending-reconcile-orphan-history` | `<pre>` | Orphan payload reconcile command history |
| `pending-repair-manifest-legend` | `<p>` | Pending repair/reconcile backend-owned mutation boundary |

---

## Rename Page — owner: `renameView.js`

| ID | Element | Purpose |
|---|---|---|
| `rename-preview-button` | `<button>` | Trigger `/api/rename/preview` |
| `rename-add-path-input` | `<input>` | Add an operator-selected media path to the rename list |
| `rename-browse-files-button` | `<button>` | Open backend-owned Windows file browser for Rename source files |
| `rename-browse-folder-button` | `<button>` | Open backend-owned Windows folder browser for a Rename source folder |
| `rename-add-path-button` | `<button>` | Add the typed media path to the rename textarea |
| `rename-apply-button` | `<button>` | Trigger `/api/rename/apply` (guarded) |
| `rename-log-bad-case-button` | `<button>` | Open selected-row bad rename case dialog |
| `rename-log-bad-case-status` | `<span>` | Selected-row bad rename case append status |
| `rename-log-case-dialog` | `<dialog>` | Bad rename case append dialog |
| `rename-log-case-title` | `<h2>` | Bad rename case append dialog title |
| `rename-log-case-source-folder` | `<input>` | Bad rename case source folder field |
| `rename-log-case-source-file` | `<input>` | Bad rename case source file field |
| `rename-log-case-expected-name` | `<input>` | Bad rename case expected output filename field |
| `rename-log-case-expected-show` | `<input>` | Bad rename case expected show title field |
| `rename-log-case-expected-season` | `<input>` | Bad rename case expected season field |
| `rename-log-case-status-select` | `<select>` | Bad rename case status selector |
| `rename-log-case-notes` | `<textarea>` | Bad rename case notes field |
| `rename-log-case-message` | `<p>` | Bad rename case append result message |
| `rename-log-case-cancel-button` | `<button>` | Close bad rename case dialog |
| `rename-log-case-submit-button` | `<button>` | Append bad rename case through backend route |
| `rename-check-applicable-button` | `<button>` | Check applicable rows |
| `rename-clear-checks-button` | `<button>` | Clear checked rows |
| `rename-move-checked-up-button` | `<button>` | Move checked rows up |
| `rename-move-checked-down-button` | `<button>` | Move checked rows down |
| `rename-natural-sort-button` | `<button>` | Apply natural sort |
| `rename-bulk-scope` | `<select>` | Bulk operation scope selector |
| `rename-bulk-stage-button` | `<button>` | Stage bulk rename |
| `rename-bulk-use-pipeline-button` | `<button>` | Use pipeline name for bulk |
| `rename-bulk-force-button` | `<button>` | Force pipeline name |
| `rename-bulk-clear-force-button` | `<button>` | Clear force |
| `rename-bulk-clear-button` | `<button>` | Clear bulk |
| `rename-save-override-button` | `<button>` | Save sidecar override |
| `rename-clear-override-button` | `<button>` | Clear sidecar override |
| `rename-status` | `<span>` | Rename operation status |
| `rename-apply-outcome-status` | `<strong>` | Rename apply outcome review status |
| `rename-apply-outcome-summary` | `<pre>` | Rename apply outcome review summary |
| `rename-apply-outcome-rows` | `<tbody>` | Rename apply outcome review rows |
| `rename-apply-outcome-legend` | `<p>` | Rename apply outcome read-only guardrail |

---

## Launch Page — owner: `launchView.js`

| ID | Element | Purpose |
|---|---|---|
| `pipeline-start-button` | `<button>` | Trigger `/api/pipeline/start` |
| `pipeline-single-file-browse-button` | `<button>` | Open backend-owned Windows file browser for Launch single-file staging |
| `pipeline-single-file-clear-button` | `<button>` | Clear staged single-file path |
| `pipeline-single-file-browse-status` | `<p>` | Single-file browser staging status |
| `launch-open-pipeline-log-window-button` | `<button>` | Open the read-only native Pipeline Log window from Launch controls |
| `pipeline-launch-detail` | `<div>` | Launch request detail |
| `pipeline-launch-status` (inferred) | `<span>` | Launch status |
| `launch-start-decision-status` | `<strong>` | Compact Launch start decision rollup status |
| `launch-start-decision-summary` | `<pre>` | Launch start decision summary text |
| `launch-start-decision-rows` | `<tbody>` | Launch start decision signal table body |
| `launch-start-decision-legend` | `<p>` | Launch start decision selectable-row legend |
| `launch-start-decision-detail` | `<pre>` | Selected Launch start decision signal detail |
| `control-readiness-status` | `<strong>` | Launch-owned pipeline control readiness status |
| `control-status` | `<span>` | Control flag status |
| `control-history` | `<pre>` | Pipeline control command history |
| `status-summary` | `<pre>` | Hidden status summary consumed by control evidence |
| `control-readiness` | `<pre>` | Hidden pipeline control readiness detail |
| `audit-start-button` | `<button>` | Trigger `/api/audit/start` |
| `audit-start-include-sidecars` | `<input>` | Audit include-sidecars option |
| `audit-start-library-root` | `<input>` | Audit library root option |
| `audit-start-show-console` | `<input>` | Audit show-console option |
| `audit-launch-detail` | `<div>` | Audit launch detail |
| `audit-launch-status` | `<span>` | Audit launch status |
| `audit-launch-preflight` | `<div>` | Audit preflight result |
| `rerun-start-button` | `<button>` | Queue CSV Rerun trigger for `/api/rerun/start` |
| `rerun-network-start-dry-run-button` | `<button>` | Queue Network CSV Rerun backend start dry-run trigger |
| `rerun-open-audit-tool-button` | `<button>` | Navigate to Reports Audit controls |
| `rerun-start-target-mode` | `<select>` | Queue CSV Rerun local vs Network backend command target |
| `rerun-network-minimum-workers` | `<input>` | Network CSV Rerun minimum worker count for backend dry-run/start |
| `rerun-start-execution-mode` | `<select>` | CSV rerun execution mode for `/api/rerun/start` |
| `rerun-start-window-size` | `<input>` | CSV rerun bounded window size |
| `rerun-start-destination-mode` | `<select>` | CSV rerun output destination policy |
| `rerun-start-collision-policy` | `<select>` | CSV rerun destination collision policy |
| `rerun-start-confirm-source-overwrite` | `<input>` | CSV rerun explicit source-path overwrite confirmation |
| `rerun-mode-policy-note` | `<p>` | CSV rerun executable policy boundary |
| `rerun-scope-enabled-only` | `<input>` | CSV rerun preview/start scope: include enabled rows only |
| `rerun-scope-skip-blocked` | `<input>` | CSV rerun preview/start scope: skip backend-classified blocked rows |
| `rerun-scope-skip-warning-rows` | `<input>` | CSV rerun preview/start scope: skip warning rows |
| `rerun-scope-first-n` | `<input>` | CSV rerun preview/start scope: first N rows |
| `rerun-scope-issue-filter` | `<select>` | CSV rerun preview/start scope: issue-code multiselect |
| `rerun-scope-bucket-filter` | `<select>` | CSV rerun preview/start scope: bucket multiselect |
| `rerun-preview-limit` | `<input>` | CSV rerun bounded backend preview row limit |
| `rerun-recent-csv-rows` | `<tbody>` | Backend-known import and scoped CSV candidates |
| `rerun-preview-summary` | `<pre>` | Backend CSV rerun summary and scoped row counts |
| `rerun-preview-tiles` | `<div>` | Backend-authored CSV rerun lifecycle status tiles |
| `rerun-lifecycle-evidence` | `<div>` | CSV rerun lifecycle evidence panel |
| `rerun-lifecycle-title` | `<strong>` | CSV rerun lifecycle headline |
| `rerun-lifecycle-phase` | `<span>` | CSV rerun lifecycle phase |
| `rerun-lifecycle-summary` | `<span>` | CSV rerun lifecycle summary |
| `rerun-lifecycle-detail` | `<pre>` | CSV rerun lifecycle detail |
| `rerun-review-header` | `<div>` | CSV rerun review summary header |
| `rerun-review-status` | `<strong>` | CSV rerun review status |
| `rerun-review-csv` | `<span>` | Selected CSV rerun source |
| `rerun-review-counts` | `<span>` | CSV rerun review row counts |
| `rerun-review-next-action` | `<span>` | CSV rerun review next action |
| `rerun-policy-panel` | `<div>` | CSV rerun executable/blocked policy panel |
| `rerun-preview-rows` | `<tbody>` | Backend CSV rerun row preview |
| `rerun-results-panel` | `<div>` | Backend CSV rerun manifests, review outputs, and promote actions |
| `rerun-state-status-filter` | `<select>` | Backend CSV rerun queue-state status filter |
| `rerun-results-refresh-button` | `<button>` | Refresh backend CSV rerun queue-state results |
| `rerun-stop-after-current-button` | `<button>` | Request backend CSV rerun Stop After Current control |
| `rerun-state-rows` | `<tbody>` | Backend-owned first-class CSV rerun queue-state rows |
| `rerun-inspect-csv-button` | `<button>` | Inspect selected backend-known import/scoped CSV |
| `rerun-open-csv-button` | `<button>` | Open selected backend-known import/scoped CSV with default CSV reader |
| `rerun-open-csv-folder-button` | `<button>` | Open folder for selected backend-known import/scoped CSV |
| `rerun-open-latest-manifest-button` | `<button>` | Open latest loaded CSV rerun manifest through `/api/rerun/open` |
| `rerun-open-run-logs-button` | `<button>` | Open run logs through diagnostics open allowlist |
| `rerun-open-last-stdout-button` | `<button>` | Open latest stdout log through diagnostics open allowlist |
| `rerun-open-last-stderr-button` | `<button>` | Open latest stderr log through diagnostics open allowlist |
| `rerun-open-active-jobs-button` | `<button>` | Open active job records through diagnostics open allowlist |
| `rerun-show-command-history-button` | `<button>` | Render recent CSV rerun and diagnostics open command history |
| `rerun-history-summary` | `<pre>` | Recent CSV rerun command history summary |
| `rerun-queue-detail` | `<pre>` | Queue CSV Rerun result/detail evidence |
| `rerun-queue-preflight` | `<pre>` | Queue CSV Rerun local preflight summary |
| `rerun-queue-status` | `<strong>` | Queue CSV Rerun workflow status |
| `pending-drain-detail` | `<div>` | Pending drain launch detail |

---

## Audit / Reports Page — owner: `reportsView.js`

| ID | Element | Purpose |
|---|---|---|
| `audit-preview-rows` | `<tbody>` | Audit CSV preview rows |
| `audit-preview-filter` | `<input>` | Audit preview text filter |
| `audit-preview-priority-only` | `<input>` | Priority-only filter checkbox |
| `audit-preview-status` | `<strong>` | Audit preview status |
| `audit-preview-summary` | `<div>` | Audit preview summary |
| `audit-preview-detail` | `<div>` | Audit preview detail |
| `audit-preview-diagnostics-actions` | `<div>` | Diagnostics handoff for audit |
| `audit-preview-table-legend` | `<p>` | Audit table legend |
| `audit-review-board` | `<div>` | Audit review board panel |
| `audit-review-status` | `<strong>` | Audit review status |
| `report-audit-add-source-button` | `<button>` | Add the staged backend-owned Reports audit source location |
| `report-audit-clear-source-selection-button` | `<button>` | Clear selected Reports audit source table rows |
| `report-audit-scan-all-button` | `<button>` | Scan all configured Reports audit source locations for aggregate metrics |
| `report-audit-scan-selected-button` | `<button>` | Scan selected Reports audit source locations for aggregate metrics |
| `report-audit-select-all-sources-button` | `<button>` | Select all enabled Reports audit source table rows |
| `report-audit-source-rows` | `<tbody>` | Reports audit source locations and scan metrics rows |
| `report-audit-source-selection-status` | `<p>` | Reports audit source selection and launch-scope summary |
| `report-audit-source-status` | `<strong>` | Reports audit source table selection count |
| `failure-archive-confirm-button` | `<button>` | Archive selected failure evidence after internal dry-run fingerprint |
| `failure-archive-disclosure` | `<details>` | Advanced failure evidence archive disclosure |
| `failure-archive-include-markers` | `<input>` | Include active failure markers in advanced archive |
| `failure-archive-include-reports` | `<input>` | Include round failure reports in advanced archive |
| `failure-archive-reason` | `<input>` | Optional note for confirmed failure evidence archive |
| `failure-archive-status` | `<strong>` | Failure evidence archive result status |
| `failure-archive-summary` | `<pre>` | Failure evidence archive result summary |
| `failure-artifact-cleanup-confirm-button` | `<button>` | Delete selected failure artifact rows |
| `failure-artifact-cleanup-disclosure` | `<details>` | Failure artifact cleanup disclosure |
| `failure-artifact-cleanup-status` | `<strong>` | Failure artifact cleanup command status |
| `failure-artifact-cleanup-summary` | `<pre>` | Failure artifact cleanup result summary |
| `failure-artifact-file-count` | `<strong>` | Failure artifact file count metric |
| `failure-artifact-largest-files` | `<tbody>` | Largest captured failure artifact rows |
| `failure-artifact-oldest` | `<strong>` | Oldest captured failure artifact timestamp |
| `failure-artifact-select-all` | `<input>` | Select all visible failure artifact rows |
| `failure-artifact-storage-status` | `<strong>` | Failure artifact storage status |
| `failure-artifact-storage-summary` | `<pre>` | Failure artifact storage root, threshold, and safety summary |
| `failure-artifact-summary-panel` | `<section>` | Reports failure artifact storage panel |
| `failure-artifact-threshold` | `<strong>` | Failure artifact warning threshold metric |
| `failure-artifact-total-size` | `<strong>` | Failure artifact total size metric |
| `failure-clear-confirm-button` | `<button>` | Confirm marker clear for selected guided scope |
| `failure-clear-scope` | `<select>` | Guided failure marker clear scope selector |
| `failure-clear-status` | `<strong>` | Failure marker clear result status |
| `failure-clear-summary` | `<pre>` | Failure marker clear result summary |
| `failure-evidence-links` | `<div>` | Selected failure row artifact, repro, and record open actions |
| `failure-filter` | `<input>` | Failure text filter |
| `failure-lifecycle-ack-button` | `<button>` | Acknowledge selected failure group lifecycle state |
| `failure-lifecycle-last-transition` | `<strong>` | Selected failure group last lifecycle update timestamp |
| `failure-lifecycle-reopen-confirm-button` | `<button>` | Confirm previewed reopen lifecycle transition |
| `failure-lifecycle-reopen-preview-button` | `<button>` | Preview selected failure group reopen lifecycle transition |
| `failure-lifecycle-resolve-confirm-button` | `<button>` | Confirm previewed resolved lifecycle transition |
| `failure-lifecycle-resolve-preview-button` | `<button>` | Preview selected failure group resolved lifecycle transition |
| `failure-lifecycle-result` | `<pre>` | Failure lifecycle transition preview/result summary |
| `failure-lifecycle-start-button` | `<button>` | Mark selected failure group as work started |
| `failure-lifecycle-state` | `<strong>` | Selected failure group lifecycle state |
| `failure-lifecycle-strip` | `<div>` | Selected failure group lifecycle status strip |
| `failure-lifecycle-verification-state` | `<strong>` | Selected failure group verification summary |
| `failure-playbook-status` | `<strong>` | Selected failure group playbook step count |
| `failure-playbook-steps` | `<ol>` | Backend-authored selected failure group playbook steps |
| `failure-primary-action-button` | `<button>` | Selected failure group primary safe action |
| `failure-resolution-blocking-count` | `<strong>` | Failure resolution blocking count |
| `failure-resolution-clearable-count` | `<strong>` | Failure resolution clearable marker count |
| `failure-resolution-detail-heading` | `<h3>` | Failure selected issue detail heading |
| `failure-resolution-detail-status` | `<strong>` | Failure selected issue detail owner/status |
| `failure-resolution-group-heading` | `<h3>` | Failure grouped issue list heading |
| `failure-resolution-group-status` | `<strong>` | Failure grouped issue count status |
| `failure-resolution-groups` | `<div>` | Failure grouped issue list |
| `failure-resolution-lifecycle-counts` | `<strong>` | Failure resolution active lifecycle group count |
| `failure-resolution-posture` | `<strong>` | Failure resolution posture summary |
| `failure-resolution-primary-action` | `<strong>` | Failure resolution primary action summary |
| `failure-resolution-retry-count` | `<strong>` | Failure resolution retryable count |
| `failure-resolution-source-mode` | `<strong>` | Failure resolution source mode |
| `failure-resolution-summary-strip` | `<div>` | Failure resolution top summary strip |
| `failure-resolution-working-count` | `<strong>` | Failure resolution acknowledged/working group count |
| `failure-source-markers` | `<input>` | Failure source markers mode checkbox |
| `failure-timeline` | `<ol>` | Selected failure group lifecycle timeline |
| `failure-timeline-status` | `<strong>` | Selected failure group lifecycle timeline count |
| `failure-verification-panel` | `<div>` | Selected failure group backend-authored verification facts |
| `failure-verification-status` | `<strong>` | Selected failure group verification status |

---

## Schedule Page — owner: `scheduleView.js`

| ID | Element | Purpose |
|---|---|---|
| `schedule-editor-status` | `<span>` | Schedule editor status |
| `schedule-watch-folder-status` | `<strong>` | Watch-folder manager status badge |
| `schedule-watch-folder-summary` | `<pre>` | Read-only watch-folder manager summary |
| `schedule-watch-folder-recent` | `<pre>` | Recent stable watch-folder detections |

---

## Diagnostics Page — owner: `diagnosticsView.js`, `commandHistory.js`

| ID | Element | Purpose |
|---|---|---|
| `diagnostics-first-response-status` | `<strong>` | First response checklist status badge |
| `diagnostics-first-response-summary` | `<div>` | First response checklist summary |
| `diagnostics-first-response-rows` | `<tbody>` | First response checklist rows |
| `diagnostics-first-response-legend` | `<p>` | First response checklist read-only guardrail |
| `diagnostics-first-response-detail` | `<pre>` | Selected first-response row detail and read-only mutation boundary |
| `diagnostics-close-readiness-overview` | `<div>` | Structured close-readiness status callout |
| `diagnostics-close-readiness-facts` | `<dl>` | Compact close-readiness fact list |
| `launch-readiness-status` | `<strong>` | Diagnostics Readiness tab launch readiness status badge |
| `launch-readiness` | `<pre>` | Diagnostics Readiness tab launch readiness text |
| `launch-readiness-actions` | `<div>` | Backend-advertised readiness recovery actions |
| `launch-readiness-action-status` | `<p>` | Readiness recovery action status |
| `launch-timing-status` | `<strong>` | Schedule alignment status in Diagnostics Readiness |
| `launch-timing` | `<pre>` | Schedule alignment detail in Diagnostics Readiness |
| `launch-evidence-section` | `<section>` | Diagnostics Readiness Settings Check panel wrapper |
| `launch-evidence-body` | `<div>` | Collapsible body of the Settings Check panel |
| `launch-evidence-toggle` | `<button>` | Collapse/Expand toggle button in Settings Check heading |
| `launch-settings-trust-status` | `<strong>` | Settings trust status in Settings Check heading |
| `launch-settings-trust-summary` | `<pre>` | Settings trust summary in Diagnostics Readiness |
| `launch-settings-risk-status` | `<strong>` | Launch settings risk handoff status |
| `launch-settings-risk-summary` | `<pre>` | Launch settings risk handoff summary |
| `launch-settings-risk-rows` | `<tbody>` | Launch settings risk rows |
| `launch-settings-risk-legend` | `<p>` | Launch settings risk read-only boundary |
| `launch-settings-risk-detail` | `<pre>` | Selected launch settings risk row detail |
| `launch-policy-boundary-status` | `<strong>` | Launch media-policy boundary status |
| `launch-policy-boundary-summary` | `<pre>` | Launch media-policy boundary summary |
| `launch-policy-boundary-rows` | `<tbody>` | Launch media-policy boundary rows |
| `launch-policy-boundary-legend` | `<p>` | Launch media-policy boundary read-only legend |
| `launch-policy-boundary-detail` | `<pre>` | Selected launch policy boundary row detail |
| `launch-settings-intent-status` | `<strong>` | Saved-settings launch-intent status |
| `launch-settings-intent-summary` | `<pre>` | Saved-settings launch-intent summary |
| `launch-settings-intent-rows` | `<tbody>` | Saved-settings launch-intent rows |
| `launch-settings-intent-legend` | `<p>` | Saved-settings launch-intent read-only legend |
| `launch-settings-intent-detail` | `<pre>` | Selected launch-intent checkpoint detail |
| `launch-scope-reconciliation-status` | `<strong>` | Launch scope reconciliation status badge |
| `launch-scope-reconciliation-summary` | `<pre>` | Launch scope reconciliation summary text |
| `launch-scope-reconciliation-rows` | `<tbody>` | Launch scope reconciliation table body |
| `launch-scope-reconciliation-legend` | `<p>` | Launch scope reconciliation selectable-row legend |
| `launch-scope-reconciliation-detail` | `<pre>` | Selected launch scope reconciliation row detail |
| `launch-real-media-proof-status` | `<strong>` | Launch real-media sample proof handoff status badge |
| `launch-real-media-proof-summary` | `<pre>` | Launch real-media sample proof handoff summary text |
| `launch-real-media-proof-rows` | `<tbody>` | Launch real-media sample proof handoff table body |
| `launch-real-media-proof-legend` | `<p>` | Launch real-media sample proof selectable-row legend |
| `launch-real-media-proof-detail` | `<pre>` | Selected launch real-media proof row detail |
| `launch-sample-execution-status` | `<strong>` | Launch sample execution checklist status |
| `launch-sample-execution-summary` | `<pre>` | Launch sample execution checklist summary |
| `launch-sample-execution-rows` | `<tbody>` | Launch sample execution checklist table body |
| `launch-sample-execution-legend` | `<p>` | Launch sample execution checklist selectable-row legend |
| `launch-sample-execution-detail` | `<pre>` | Selected launch sample execution checklist detail |
| `launch-pilot-readiness-status` | `<strong>` | Launch pilot readiness status |
| `launch-pilot-readiness-summary` | `<pre>` | Launch pilot readiness summary |
| `launch-pilot-readiness-rows` | `<tbody>` | Launch pilot readiness rows |
| `launch-pilot-readiness-legend` | `<p>` | Launch pilot readiness read-only legend |
| `launch-pilot-readiness-detail` | `<pre>` | Selected launch pilot readiness detail |
| `launch-backend-preflight-refresh-button` | `<button>` | Refresh backend launch preflight evidence |
| `launch-backend-preflight-status` | `<strong>` | Backend launch preflight status |
| `launch-backend-preflight-summary` | `<pre>` | Backend launch preflight summary |
| `launch-backend-preflight-rows` | `<tbody>` | Backend launch preflight rows |
| `launch-backend-preflight-legend` | `<p>` | Backend launch preflight read-only legend |
| `launch-backend-preflight-detail` | `<pre>` | Selected backend launch preflight detail |
| `diagnostics-command-owner-rows` | `<tbody>` | Command owner rows in diagnostics |
| `diagnostics-command-drilldown-rows` | `<tbody>` | Command drilldown rows |
| `diagnostics-command-drilldown-actions` | `<div>` | Drilldown action links |
| `diagnostics-command-evidence-rows` | `<tbody>` | Command evidence rows |
| `diagnostics-command-resolution-status` | `<strong>` | Resolution status badge |
| `diagnostics-command-resolution-rows` | `<tbody>` | Resolution detail rows |

---

## Settings Page — owner: `settingsView.js`

| ID | Element | Purpose |
|---|---|---|
| `settings-status` | `<span>` | Settings operation status |
| `settings-runtime-failure-artifact-threshold` | `<input>` | Runtime builder failure artifact warning threshold in GB |
| `settings-runtime-failure-artifact-retention` | `<input>` | Runtime builder failure artifact age-retention cleanup threshold in days |
| `settings-runtime-failure-artifact-cleanup-target` | `<input>` | Runtime builder failure artifact cleanup target in GB |
| `settings-patch-detail` | `<div>` | Patch detail display |
| `settings-effective-policy-status` | `<strong>` | Effective policy trust status badge |
| `settings-effective-policy-summary` | `<pre>` | Saved-vs-staged policy trust summary |
| `settings-effective-policy-rows` | `<tbody>` | Effective policy trust checkpoint rows |
| `settings-effective-policy-legend` | `<p>` | Effective policy read-only boundary legend |
| `settings-effective-policy-detail` | `<pre>` | Selected effective policy checkpoint detail |
| `settings-builder-route-threshold-mode` | `<select>` | Settings builder route threshold filter mode |
| `settings-builder-movie-route-bitrate` | `<input>` | Settings builder movie remux/copy route bitrate ceiling |
| `settings-builder-tv-route-bitrate` | `<input>` | Settings builder TV remux/copy route bitrate ceiling |
| `settings-subtitle-bdpgs-ocr-tool-path` | `<input>` | Subtitle builder staged BDPGS OCR tool path |
| `settings-subtitle-bdpgs-ocr-tessdata-path` | `<input>` | Subtitle builder staged BDPGS tessdata path |
| `settings-subtitle-sdh-keywords` | `<input>` | Subtitle builder staged SDH title keyword list |
| `settings-subtitle-supplemental-keywords` | `<input>` | Subtitle builder staged supplemental title keyword list |
| `settings-file-safety-enable-watch` | `<input>` | File Safety builder watch-folder enable toggle |
| `settings-file-safety-watch-action` | `<select>` | File Safety builder watch-folder action mode |
| `settings-file-safety-watch-debounce` | `<input>` | File Safety builder watch-folder debounce seconds |
| `settings-file-safety-watch-respect-schedule` | `<input>` | File Safety builder watch-folder schedule-respect toggle |
| `settings-file-safety-watch-roots` | `<input>` | File Safety builder explicit watch root list |
| `settings-library-watch-panel` | `<section>` | Libraries page watch-folder auto-run toggle panel |
| `settings-library-watch-status` | `<strong>` | Libraries page watch-folder auto-run status badge |
| `settings-library-watch-auto-run` | `<input>` | Libraries page watch-folder auto-run toggle |
| `settings-library-watch-respect-schedule` | `<input>` | Libraries page watch-folder schedule-respect toggle |
| `settings-library-watch-stage-button` | `<button>` | Stage Libraries watch-folder auto-run patch |
| `settings-library-watch-preview-button` | `<button>` | Preview Libraries watch-folder auto-run patch |
| `settings-library-watch-save-button` | `<button>` | Save Libraries watch-folder auto-run patch |
| `settings-library-watch-summary` | `<pre>` | Libraries page watch-folder auto-run patch summary |
| `settings-quality-builder-status` | `<strong>` | Quality Verification builder status badge |
| `settings-builder-quality-enable` | `<input>` | Quality Verification builder enable toggle |
| `settings-builder-quality-metric` | `<select>` | Quality Verification builder metric selector |
| `settings-builder-quality-sample-mode` | `<select>` | Quality Verification builder sample mode selector |
| `settings-builder-quality-sample-seconds` | `<input>` | Quality Verification builder per-window sample seconds |
| `settings-builder-quality-sample-count` | `<input>` | Quality Verification builder sample window count |
| `settings-builder-quality-warn-threshold` | `<input>` | Quality Verification builder warning threshold |
| `settings-builder-quality-fail-threshold` | `<input>` | Quality Verification builder failure threshold |
| `settings-builder-quality-fail-action` | `<select>` | Quality Verification builder fail action selector |
| `settings-builder-quality-timeout` | `<input>` | Quality Verification builder FFmpeg verification timeout |
| `settings-quality-apply-button` | `<button>` | Merge Quality Verification Patch |
| `settings-quality-reset-button` | `<button>` | Reset Quality Verification builder from current settings |
| `settings-quality-guidance` | `<pre>` | Quality Verification builder guidance and staged-value summary |
| `settings-rename-workbench-status` | `<strong>` | Rename filter workbench backend comparison status |
| `settings-rename-workbench-form` | `<form>` | Rename filter case workbench form |
| `settings-rename-workbench-mode` | `<select>` | Workbench movie/TV media type selector |
| `settings-rename-workbench-template` | `<select>` | TV rename template selector |
| `settings-rename-workbench-source-folder` | `<input>` | Source folder text for workbench comparison/case payload; required for TV, optional for movies |
| `settings-rename-workbench-source-file` | `<input>` | Required source filename/title for workbench comparison/case payload |
| `settings-rename-workbench-expected-show` | `<input>` | Expected TV show title |
| `settings-rename-workbench-expected-season` | `<input>` | Expected TV season number |
| `settings-rename-workbench-expected-episode` | `<input>` | Expected TV episode number |
| `settings-rename-workbench-expected-episode-title` | `<input>` | Optional expected TV episode title |
| `settings-rename-workbench-expected-movie-title` | `<input>` | Expected movie title |
| `settings-rename-workbench-expected-year` | `<input>` | Expected movie year |
| `settings-rename-workbench-notes` | `<textarea>` | Operator notes for workbench case payload |
| `settings-rename-workbench-test-button` | `<button>` | Test current draft filters through backend cleaner |
| `settings-rename-workbench-result-heading` | `<h3>` | Backend comparison panel heading |
| `settings-rename-workbench-save-state` | `<span>` | Save-readiness state badge for staged rename filters |
| `settings-rename-workbench-save-case-button` | `<button>` | Append backend regression case with strict confirmation |
| `settings-rename-workbench-stage-suggestions-button` | `<button>` | Stage selected backend suggestions into unsaved Settings draft |
| `settings-rename-workbench-retest-button` | `<button>` | Retest after staging suggestions |
| `settings-rename-workbench-save-filters-button` | `<button>` | Save staged rename filters through the guarded Settings save path |
| `settings-rename-workbench-message` | `<span>` | Workbench action/status message |
| `settings-rename-workbench-output` | `<div>` | Backend actual/expected comparison output |
| `settings-rename-workbench-suggestions` | `<tbody>` | Backend filter suggestion rows |

---

## Command History — owner: `commandHistory.js` (shared across pages)

| ID | Element | Purpose |
|---|---|---|
| `command-rows` | `<tbody>` | Command journal rows |
| `command-status` | `<strong>` | Command journal status badge |
| `command-summary` | `<div>` | Command journal summary |
| `command-detail` | `<div>` | Selected command detail |
| `command-diagnostics-actions` | `<div>` | Diagnostics handoff from command |
| `command-table-legend` | `<p>` | Command table legend |

---

## Maintenance Page — owner: `maintenanceView.js`

| ID | Element | Purpose |
|---|---|---|
| `maintenance-refresh-button` | `<button>` | Trigger `GET /api/maintenance` |
| `maintenance-change-ledger-status` | `<strong>` | Change ledger load and hygiene status |
| `maintenance-change-ledger-refresh-button` | `<button>` | Trigger `GET /api/maintenance/change-ledger` |
| `maintenance-change-ledger-summary` | `<pre>` | Change ledger count and Python-impact summary |
| `maintenance-change-ledger-table-status` | `<strong>` | Filtered ledger row count |
| `maintenance-change-ledger-status-filter` | `<select>` | Change ledger status filter |
| `maintenance-change-ledger-type-filter` | `<select>` | Change ledger type filter |
| `maintenance-change-ledger-risk-filter` | `<select>` | Change ledger risk filter |
| `maintenance-change-ledger-search` | `<input>` | Change ledger text search |
| `maintenance-change-ledger-rows` | `<tbody>` | Change ledger table rows |
| `maintenance-change-ledger-table-legend` | `<p>` | Change ledger table legend |
| `maintenance-change-ledger-detail-status` | `<strong>` | Selected change detail status |
| `maintenance-change-ledger-detail` | `<pre>` | Selected issue/feature, affected scripts, validation, rollback, and notes |
| `maintenance-change-ledger-hygiene-status` | `<strong>` | Change-control hygiene status |
| `maintenance-change-ledger-hygiene` | `<pre>` | Missing/stale/invalid packet and changelog evidence |
| `release-dry-run-button` | `<button>` | Trigger `/api/maintenance/release-dry-run` |
| `release-dry-run-detail` | `<div>` | Dry-run result detail |
| `release-dry-run-status` | `<span>` | Dry-run status |
| `backfill-dry-run-button` | `<button>` | Trigger `/api/maintenance/completed-backfill-dry-run` |
| `backfill-dry-run-detail` | `<div>` | Backfill dry-run result detail |
| `backfill-dry-run-status` | `<span>` | Backfill status |
| `dependency-atlas-button` | `<button>` | Trigger `/api/maintenance/dependency-atlas` |
| `dependency-atlas-open-folder-button` | `<button>` | Trigger `/api/maintenance/dependency-atlas/open-folder` |
| `dependency-atlas-detail` | `<pre>` | Dependency atlas result detail |
| `dependency-atlas-progress-bars` | `<div>` | Dependency atlas progress bars |
| `dependency-atlas-status` | `<strong>` | Dependency atlas status |

---

## API Contract Page — owner: `contractView.js`

| ID | Element | Purpose |
|---|---|---|
| `api-contract` | `<div>` | API contract container |
| `api-contract-rows` | `<tbody>` | Contract route rows |
| `api-contract-method` | `<select>` | Method filter (GET/POST) |
| `api-contract-scope` | `<select>` | Scope filter |
| `api-contract-filter` | `<input>` | Text filter |
| `api-contract-detail` | `<div>` | Selected route detail |
| `api-contract-status` | `<strong>` | Contract load status |
| `api-contract-safety-status` | `<strong>` | Contract safety review status |
| `api-contract-safety-summary` | `<pre>` | Contract safety review summary |
| `api-contract-safety-rows` | `<tbody>` | Contract safety review rows |
| `api-contract-safety-legend` | `<p>` | Contract safety table legend |
| `api-contract-safety-detail` | `<pre>` | Selected contract safety detail |
| `api-contract-table-legend` | `<p>` | Contract table legend |

---

## ID Ownership Summary

| ID Prefix | Owning Module | Page |
|---|---|---|
| `active-job-*` | `progressView.js` | Live |
| `activity` | `app.js` | All (topbar) |
| `api-contract-*` | `contractView.js` | Diagnostics |
| `app-version` | `app.js` | All (sidebar) |
| `audit-launch-*`, `audit-start-*` | `launchView.js` | Launch |
| `audit-preview-*`, `audit-review-*` | `reportsView.js` | Reports |
| `report-audit-*` | `reportsView.js` | Reports |
| `backend-lifecycle-*`, `backend-shutdown-*` | `app.js` | All (topbar) |
| `backfill-dry-run-*` | `maintenanceView.js` | Maintenance |
| `close-readiness` | `app.js` | All (topbar) |
| `command-*` | `commandHistory.js` | Cross-page |
| `completed-*` | `completedView.js` | Completed |
| `cross-page-*` | `crossPageContextView.js` | Home |
| `daily-driver-*` | `app.js` + `crossPageContextView.js` | Home |
| `diagnostics-command-*` | `commandHistory.js` | Diagnostics |
| `failed-count` | `app.js` | Home |
| `failure-*` | `reportsView.js` | Reports |
| `home-readiness-*` | `crossPageContextView.js` | Home |
| `launch-backend-preflight-*` | `launchView.js` | Diagnostics |
| `launch-evidence-*` | `launchView.js` | Diagnostics |
| `launch-pilot-readiness-*` | `launchView.js` | Diagnostics |
| `launch-policy-boundary-*` | `launchView.js` | Diagnostics |
| `launch-readiness-*`, `launch-timing*` | `launchReadinessView.js` | Diagnostics |
| `launch-real-media-proof-*` | `launchView.js` | Diagnostics |
| `launch-sample-execution-*` | `launchView.js` | Diagnostics |
| `launch-scope-reconciliation-*` | `launchView.js` | Diagnostics |
| `launch-settings-*` | `launchView.js` | Diagnostics |
| `launch-start-decision-*` | `launchView.js` | Launch |
| `maintenance-change-ledger-*` | `maintenanceView.js` | Maintenance |
| `maintenance-refresh-*` | `maintenanceView.js` | Maintenance |
| `pending-*` | `pendingPublishView.js` | Pending Publish |
| `pipeline-launch-*`, `pipeline-start-*` | `launchView.js` | Launch |
| `pipeline-state` | `app.js` | Home |
| `processed-count`, `queue-count`, `queue-count-detail` | `app.js` | Home |
| `publish-reconciliation-*` | `completedView.js` | Completed |
| `queue-*` | `queueView.js` | Queue |
| `refresh-button`, `refresh-health` | `app.js` | All (topbar) |
| `release-dry-run-*` | `maintenanceView.js` | Maintenance |
| `rename-*` | `renameView.js` | Rename |
| `rerun-*` | `queueView.rerun.js` | Queue |
| `sample-validation-*` | `crossPageContextView.js` | Home |
| `schedule-*` | `scheduleView.js` | Schedule |
| `settings-*` | `settingsView.js` | Settings |
| `state-pill` | `app.js` | All (topbar) |
| `telemetry-*` | `telemetryView.js` | Home |

---

## Rules for Future ID Additions

From `archive/admin-audits/WEBVIEW_DOM_ID_NAMESPACE_AUDIT.md`:

- All IDs must use the `{page}-{role}` pattern matching the owning page/section prefix.
- No global/generic IDs (e.g., `status`, `detail`, `loading`).
- IDs within a shared module (e.g., `commandHistory.js`) must use a prefix that does not conflict with any page prefix.
- New shared-module IDs should use a prefix different from all existing page prefixes.

---

## See Also

- DOM ID namespace audit: `docs/archive/admin-audits/WEBVIEW_DOM_ID_NAMESPACE_AUDIT.md`
- Frontend module sizes: `docs/archive/completed-audits/FRONTEND_MODULE_SIZE_COHESION_REPORT.md`
- Mutation boundary review: `docs/archive/completed-audits/WEBVIEW_APIPOST_MUTATION_REVIEW.md`

---

## Delta Review — 2026-05-15 (CLN3-005)

Added 10 missing Launch page DOM IDs for two new panels added during the Launch Real-Media Proof Handoff and Launch Scope Reconciliation work.

| Panel | IDs added | Owner | Source in index.html |
|---|---|---|---|
| Launch Scope Reconciliation | `launch-scope-reconciliation-{status,summary,rows,legend,detail}` (5) | `launchView.js` | Lines ~1509–1528 |
| Launch Real-Media Sample Proof | `launch-real-media-proof-{status,summary,rows,legend,detail}` (5) | `launchView.js` | Lines ~1531–1550 |

Both panels are read-only from the frontend perspective — `launchView.js` renders backend-served evidence only, no mutation routes are posted by these panels. ID Ownership Summary updated with `launch-real-media-proof-*` and `launch-scope-reconciliation-*` entries.

```
Task ID: CLN3-005
Files inspected: docs\inventories\WEBVIEW_DOM_ID_INVENTORY.md, apps\desktop\webview\static\index.html (lines 1509–1550)
Files changed: docs\inventories\WEBVIEW_DOM_ID_INVENTORY.md (10 ID rows added to Launch Page table; 2 summary rows added to ID Ownership Summary)
Validation: Select-String -Path docs\inventories\WEBVIEW_DOM_ID_INVENTORY.md -Pattern "launch-real-media-proof|launch-scope-reconciliation"
Findings: 10 missing IDs identified and added. No phantom references — all 10 IDs exist in index.html.
Open questions: None.
Risk: Low — documentation only.
```

---

## Delta Review — 2026-05-16 (UI Stage 12)

Home page rebuilt as a daily-driver dashboard (Stage 12). The old home panels (lines 51–716) were replaced with a minimalist status strip + run controls + quick actions + recently completed structure. All existing panels are still present inside `<div data-advanced>`. Seventeen new IDs were added to the daily-driver section.

| Panel | IDs added | Owner | Purpose |
|---|---|---|---|
| Status strip metrics | `home-pending-count`, `home-failed-count` | `app.js` | Pending parked count; failed-file count chip (replaces `home-network-role` per UI refactor) |
| Queue Snapshot | `home-queue-snapshot-status`, `home-queue-snapshot` | `app.js` | Compact queue summary |
| Recently Completed | `home-recent-completed-status`, `home-recent-completed-tbody` | `app.js` | Last 5 completed files compact table |

**New unique ID count: 972** (was 956 after Advanced Gate; +16 daily-driver IDs, +1 pre-existing gap closed for `home-runtime-open-status` now properly counted).

```
Task: UI Stage 12
Files inspected: apps\desktop\webview\static\index.html (lines 51–716 replaced)
Files changed: docs\inventories\WEBVIEW_DOM_ID_INVENTORY.md (16 new ID rows added to Home Page table; Delta Review section appended)
Validation: (grep -o 'id="[^"]*"' index.html | sort | uniq | wc -l) → 972
Findings: 15 new home daily-driver IDs identified; 1 pre-existing gap (home-runtime-open-status) closed.
Open questions: None.
Risk: Low — documentation only.
```

---

## Delta Review — 2026-05-18 (Dashboard command-surface cleanup)

The Dashboard quick start, publish-drain, and schedule-toggle command IDs were removed from the Home page. Pipeline start and control actions are now Launch-owned, pending publish drain remains on Pending Publish, and schedule mutation remains on Schedule. Current static HTML contains 1011 unique IDs.

| Area | Inventory result |
|---|---|
| Home daily-driver command IDs | Removed from current ID table |
| Launch control evidence IDs | `control-readiness-status`, `control-status`, `control-history`, `status-summary`, `control-readiness` are tracked under Launch |
| Current ID count | 1011 unique `id=""` values |

```
Task: Dashboard command-surface cleanup
Files inspected: apps\desktop\webview\static\index.html
Files changed: docs\inventories\WEBVIEW_DOM_ID_INVENTORY.md
Validation: Python id scan over index.html -> 1011 unique IDs
Risk: Low — inventory update for visible command-surface relocation
```

---

## Delta Review — 2026-05-18 (Phase 3 per-file settings drawer)

Added 15 new `fo-*` IDs to `index.html` for the per-file override settings drawer (overlay, drawer panel, audio/subtitle form controls). Count updated from 1011 to 1026.

| Area | Inventory result |
|---|---|
| Per-file settings overlay | `fo-overlay` added |
| Per-file settings drawer | `fo-drawer`, `fo-drawer-title`, `fo-drawer-path`, `fo-drawer-close`, `fo-drawer-save`, `fo-drawer-clear`, `fo-drawer-status` added |
| Audio override fields | `fo-audio-keep-langs`, `fo-audio-drop-langs`, `fo-audio-max-channels` added |
| Subtitle override fields | `fo-sub-strip-all`, `fo-sub-filter-fields`, `fo-sub-keep-langs`, `fo-sub-drop-langs` added |
| Current ID count | 1026 unique `id=""` values |

```
Task: Phase 3 per-file settings drawer
Files changed: apps\desktop\webview\static\index.html, docs\inventories\WEBVIEW_DOM_ID_INVENTORY.md
Risk: Low — additive only; new IDs for queue drawer UI
```

---

## Delta Review — 2026-06-29 (Path picker badges)

Added compact backend-owned path picker badges beside real operator path labels.
The shared badge class is `path-picker-badge`; each static badge carries
`data-path-picker-target`, `data-path-picker-input`, `data-path-picker-mode`,
and optional `data-path-picker-status` / `data-path-picker-write` attributes.
Dynamic builder rows use the same class and data-attribute contract without
stable row-specific IDs.

| Area | Static badge IDs |
|---|---|
| Launch | `pipeline-single-file-path-picker-badge` |
| Queue | `rerun-csv-path-picker-badge` |
| Reports / Metrics | `report-audit-library-root-picker-badge`, `metrics-source-path-picker-badge` |
| Rename source staging | `rename-manual-path-picker-badge` |
| Settings wizard roots/tools | `wizard-output-root-picker-badge`, `wizard-scratch-path-picker-badge`, `wizard-ffmpeg-path-picker-badge`, `wizard-ffprobe-path-picker-badge` |
| Settings File Safety | `settings-file-safety-source-movies-picker-badge`, `settings-file-safety-source-tv-picker-badge`, `settings-file-safety-outsource-picker-badge`, `settings-file-safety-local-base-picker-badge`, `settings-file-safety-watch-roots-picker-badge` |
| Subtitle OCR paths | `settings-subtitle-bdpgs-ocr-tool-picker-badge`, `settings-subtitle-bdpgs-tessdata-picker-badge`, `settings-subtitle-vobsub-ocr-tool-picker-badge` |

Excluded fields remain picker-free: rename workbench source file/folder fields
and rename bad-case corpus example fields. Current ID count is 1943 unique
`id=""` values.

---

## Machine-Generated Full DOM ID Manifest - 2026-07-03

This section is generated from `apps/desktop/webview/static/index.html` and is the exhaustive ID set used by `test_webview_inventory_docs.py`. Curated page tables above remain the human orientation layer.

Count: 2017

<!-- BEGIN GENERATED DOM ID MANIFEST -->
```text
active-job-detail
active-job-detail-rows
active-job-detail-status
active-job-diagnostics-actions
active-job-table-legend
active-jobs
activity
advanced-toggle
api-contract
api-contract-detail
api-contract-filter
api-contract-method
api-contract-rows
api-contract-safety-detail
api-contract-safety-legend
api-contract-safety-rows
api-contract-safety-status
api-contract-safety-summary
api-contract-scope
api-contract-status
api-contract-table-legend
app-version
audit-preview-detail
audit-preview-diagnostics-actions
audit-preview-filter
audit-preview-priority-only
audit-preview-rows
audit-preview-status
audit-preview-summary
audit-preview-table-legend
audit-review-board
audit-review-status
backend-lifecycle-callout
backend-lifecycle-facts
backend-lifecycle-history
backend-lifecycle-history-rows
backend-lifecycle-status
backend-lifecycle-summary
backend-shutdown-button
backend-shutdown-status
backfill-dry-run-button
backfill-dry-run-detail
backfill-dry-run-progress-bars
backfill-dry-run-status
close-readiness
command-detail
command-diagnostics-actions
command-rows
command-status
command-summary
command-table-legend
completed-active-output-context
completed-active-output-paths
completed-active-output-placement
completed-active-output-title
completed-active-output-trust
completed-active-output-visibility
completed-breakdown
completed-breakdown-status
completed-breakdown-strip
completed-clear-filters-button
completed-consistency
completed-consistency-status
completed-consistency-strip
completed-copy-evidence-button
completed-copy-evidence-status
completed-count
completed-current-at-a-glance
completed-current-details
completed-current-filter-line
completed-current-output-heading
completed-current-status
completed-current-summary
completed-detail
completed-diagnostics-actions
completed-diagnostics-guidance
completed-diagnostics-status
completed-encode-count
completed-filter
completed-filter-summary
completed-final-trust-detail
completed-final-trust-legend
completed-final-trust-rows
completed-final-trust-status
completed-final-trust-summary
completed-history-clear-filters-button
completed-history-filter
completed-history-filter-summary
completed-history-investigation-filter
completed-history-rows
completed-history-status
completed-history-status-filter
completed-history-summary-heading
completed-history-table-legend
completed-integrity
completed-integrity-status
completed-integrity-strip
completed-inventory-progress-bars
completed-investigation-filter
completed-library-filter
completed-missing-count
completed-open-history
completed-open-status
completed-output-acceptance-detail
completed-output-acceptance-legend
completed-output-acceptance-rows
completed-output-acceptance-status
completed-output-acceptance-summary
completed-pending-proof-detail
completed-pending-proof-legend
completed-pending-proof-rows
completed-pending-proof-status
completed-pending-proof-summary
completed-pilot-evidence-detail
completed-pilot-evidence-legend
completed-pilot-evidence-markdown
completed-pilot-evidence-rows
completed-pilot-evidence-status
completed-pilot-evidence-summary
completed-raw-detail
completed-real-media-proof-detail
completed-real-media-proof-legend
completed-real-media-proof-rows
completed-real-media-proof-status
completed-real-media-proof-summary
completed-reconcile-manifest-apply-button
completed-reconcile-manifest-dry-run-button
completed-reconciliation-hint
completed-refresh-current-output-button
completed-remux-count
completed-repair-detail
completed-repair-history
completed-repair-legend
completed-repair-manifest-status
completed-repair-overall-status
completed-repair-sidecar-apply-button
completed-repair-sidecar-dry-run-button
completed-repair-sidecar-status
completed-route-agreement-detail
completed-route-agreement-legend
completed-route-agreement-rows
completed-route-agreement-status
completed-route-agreement-summary
completed-rows
completed-runtime
completed-runtime-status
completed-runtime-strip
completed-selected-promotion-status
completed-selected-status
completed-selected-summary
completed-show-selected-button
completed-size-evidence-detail
completed-size-evidence-legend
completed-size-evidence-rows
completed-size-evidence-status
completed-size-evidence-summary
completed-status
completed-status-filter
completed-summary
completed-table-legend
completed-trust-decision-chips
completed-trust-decision-heading
completed-trust-decision-status
completed-trust-decision-summary
completed-validation
completed-validation-status
completed-validation-strip
completed-workflow
completed-workflow-status
completed-workflow-strip
control-history
control-latest
control-readiness
control-readiness-status
control-status
cpu-chart
cpu-chart-meta
cpu-utility-note
cpu-value
cross-page-conflict-legend
cross-page-conflict-rows
cross-page-conflict-status
cross-page-context-board
cross-page-context-status
cross-page-context-summary
cross-page-real-media-detail
cross-page-real-media-legend
cross-page-real-media-rows
cross-page-real-media-status
cross-page-real-media-summary
cross-page-sample-legend
cross-page-sample-rows
cross-page-sample-status
cross-page-validation-template
cross-page-validation-template-status
customize-layout-btn
daily-driver-legend
daily-driver-rows
daily-driver-status
daily-driver-summary
dependency-atlas-button
dependency-atlas-detail
dependency-atlas-open-folder-button
dependency-atlas-progress-bars
dependency-atlas-status
diagnostics-close-readiness
diagnostics-close-readiness-facts
diagnostics-close-readiness-overview
diagnostics-close-status
diagnostics-command-drilldown-actions
diagnostics-command-drilldown-detail
diagnostics-command-drilldown-legend
diagnostics-command-drilldown-rows
diagnostics-command-drilldown-status
diagnostics-command-drilldown-summary
diagnostics-command-evidence-legend
diagnostics-command-evidence-rows
diagnostics-command-evidence-status
diagnostics-command-evidence-summary
diagnostics-command-history
diagnostics-command-owner-legend
diagnostics-command-owner-rows
diagnostics-command-owner-status
diagnostics-command-owner-summary
diagnostics-command-resolution-detail
diagnostics-command-resolution-legend
diagnostics-command-resolution-rows
diagnostics-command-resolution-status
diagnostics-command-resolution-summary
diagnostics-command-status
diagnostics-drilldown-actions
diagnostics-drilldown-status
diagnostics-drilldown-summary
diagnostics-first-response-detail
diagnostics-first-response-legend
diagnostics-first-response-rows
diagnostics-first-response-status
diagnostics-first-response-summary
diagnostics-investigation-actions
diagnostics-investigation-status
diagnostics-investigation-trail
diagnostics-launch-log-status
diagnostics-live-run-status
diagnostics-live-run-strip
diagnostics-log-actions
diagnostics-log-detail
diagnostics-log-filter
diagnostics-log-guidance
diagnostics-log-rows
diagnostics-log-severity
diagnostics-log-status
diagnostics-log-table-legend
diagnostics-open-history
diagnostics-open-status
diagnostics-owner-handoff
diagnostics-owner-handoff-actions
diagnostics-owner-handoff-detail
diagnostics-owner-handoff-legend
diagnostics-owner-handoff-nav-status
diagnostics-owner-handoff-rows
diagnostics-owner-handoff-status
diagnostics-pipeline-log-status
diagnostics-progress-bars
diagnostics-progress-detail
diagnostics-progress-rows
diagnostics-progress-status
diagnostics-state-recovery
diagnostics-state-recovery-status
diagnostics-state-summary
diagnostics-state-summary-actions
diagnostics-state-summary-detail
diagnostics-state-summary-rows
diagnostics-state-summary-status
diagnostics-state-summary-table-legend
diagnostics-state-triage-actions
diagnostics-state-triage-detail
diagnostics-state-triage-legend
diagnostics-state-triage-rows
diagnostics-state-triage-status
diagnostics-state-triage-summary
diagnostics-tail-detail
diagnostics-tail-evidence
diagnostics-tail-max-bytes
diagnostics-tail-refresh-button
diagnostics-tail-status
diagnostics-tail-target
diagnostics-tail-text
diagnostics-triage-status
diagnostics-triage-summary
evidence-toggle
failed-count
failed-label
failure-all-records-disclosure
failure-archive-confirm-button
failure-archive-disclosure
failure-archive-include-markers
failure-archive-include-reports
failure-archive-reason
failure-archive-status
failure-archive-summary
failure-artifact-cleanup-confirm-button
failure-artifact-cleanup-disclosure
failure-artifact-cleanup-status
failure-artifact-cleanup-summary
failure-artifact-file-count
failure-artifact-largest-files
failure-artifact-oldest
failure-artifact-select-all
failure-artifact-storage-status
failure-artifact-storage-summary
failure-artifact-summary-panel
failure-artifact-threshold
failure-artifact-total-size
failure-clear-confirm-button
failure-clear-scope
failure-clear-status
failure-clear-summary
failure-detail
failure-diagnostics-actions
failure-evidence-links
failure-filter
failure-lifecycle-ack-button
failure-lifecycle-last-transition
failure-lifecycle-reopen-confirm-button
failure-lifecycle-resolve-confirm-button
failure-lifecycle-result
failure-lifecycle-start-button
failure-lifecycle-state
failure-lifecycle-strip
failure-lifecycle-verification-state
failure-more-actions
failure-playbook-status
failure-playbook-steps
failure-primary-action-button
failure-resolution-blocking-count
failure-resolution-clearable-count
failure-resolution-detail-heading
failure-resolution-detail-status
failure-resolution-group-heading
failure-resolution-group-status
failure-resolution-groups
failure-resolution-lifecycle-counts
failure-resolution-posture
failure-resolution-primary-action
failure-resolution-retry-count
failure-resolution-source-mode
failure-resolution-summary-strip
failure-resolution-working-count
failure-review-board
failure-review-board-detail
failure-review-status
failure-rows
failure-source-markers
failure-status
failure-summary
failure-table-legend
failure-timeline
failure-timeline-status
failure-verification-panel
failure-verification-status
final-library-pause-button
final-library-promote-button
final-library-promotion-command-status
final-library-promotion-rows
final-library-promotion-status
final-library-promotion-summary
final-library-resume-button
floating-pipeline-log-close-button
floating-pipeline-log-follow
floating-pipeline-log-mode
floating-pipeline-log-panel
floating-pipeline-log-refresh-button
floating-pipeline-log-status
floating-pipeline-log-text
floating-pipeline-log-title
floating-pipeline-log-updated
fo-audio-drop-langs
fo-audio-drop-langs-inherited
fo-audio-keep-langs
fo-audio-keep-langs-inherited
fo-audio-max-channels
fo-audio-max-channels-inherited
fo-audio-prefer-default-language
fo-audio-prefer-default-language-inherited
fo-audio-track-count
fo-audio-track-group
fo-audio-track-list
fo-audio-track-status
fo-drawer
fo-drawer-clear
fo-drawer-close
fo-drawer-path
fo-drawer-save
fo-drawer-status
fo-drawer-title
fo-inherited-settings-status
fo-overlay
fo-processing-route-help
fo-processing-route-section
fo-remux-pilot-promote
fo-remux-pilot-proof
fo-route-encode-advisory
fo-route-override-controls
fo-route-override-disclosure-status
fo-route-override-toggle
fo-route-preview-status
fo-route-profile
fo-route-profile-inherited
fo-route-threshold-mode
fo-route-threshold-mode-inherited
fo-series-apply
fo-series-auto-detect
fo-series-cancel
fo-series-clear-open
fo-series-counts
fo-series-detected
fo-series-fields
fo-series-issues
fo-series-modal
fo-series-modal-close
fo-series-modal-title
fo-series-preview-open
fo-series-rows
fo-series-status
fo-series-summary
fo-source-info-grid
fo-source-info-missing
fo-source-info-section
fo-source-info-status
fo-source-info-title
fo-sub-drop-langs
fo-sub-drop-langs-inherited
fo-sub-filter-fields
fo-sub-keep-langs
fo-sub-keep-langs-inherited
fo-sub-strip-all
fo-sub-strip-all-inherited
fo-subtitle-track-count
fo-subtitle-track-group
fo-subtitle-track-list
fo-subtitle-track-status
fo-track-metadata-help
fo-track-metadata-section
fo-track-metadata-title
fo-track-warning-list
fo-video-codec
fo-video-codec-inherited
fo-video-container
fo-video-container-inherited
fo-video-encode-ladder
fo-video-encode-ladder-inherited
fo-video-encode-preset
fo-video-encode-preset-inherited
gpu-chart
gpu-chart-meta
gpu-detail-status
gpu-empty-state
gpu-note
gpu-rows
gpu-value
home-active-work-status
home-active-work-summary
home-control-message
home-control-readiness-status
home-external-dependencies-status
home-external-dependencies-summary
home-failed-count
home-failed-label
home-failure-artifact-storage-detail
home-failure-artifact-storage-status
home-live-run-status
home-live-run-strip
home-next-queue-detail
home-next-queue-list
home-next-queue-status
home-output-storage-detail
home-output-storage-status
home-pending-count
home-promotion-entry-message
home-queue-snapshot
home-queue-snapshot-status
home-readiness-status
home-readiness-summary
home-recent-completed-detail
home-recent-completed-status
home-recent-completed-tbody
home-refresh-button
home-run-state-handoff
home-runtime-open-status
home-scratch-storage-detail
home-scratch-storage-status
home-settings-trust-status
home-settings-trust-summary
launch-backend-preflight-detail
launch-backend-preflight-legend
launch-backend-preflight-refresh-button
launch-backend-preflight-rows
launch-backend-preflight-status
launch-backend-preflight-summary
launch-command-diagnostics-actions
launch-command-diagnostics-guidance
launch-command-review-detail
launch-command-review-legend
launch-command-review-rows
launch-command-review-status
launch-command-review-summary
launch-encoder-capability-refresh-button
launch-evidence-body
launch-evidence-section
launch-evidence-toggle
launch-history
launch-history-status
launch-latest-command-evidence
launch-live-run-status
launch-live-run-strip
launch-logs
launch-open-pipeline-log-window-button
launch-pilot-readiness-detail
launch-pilot-readiness-legend
launch-pilot-readiness-rows
launch-pilot-readiness-status
launch-pilot-readiness-summary
launch-policy-boundary-detail
launch-policy-boundary-legend
launch-policy-boundary-rows
launch-policy-boundary-status
launch-policy-boundary-summary
launch-readiness
launch-readiness-action-status
launch-readiness-actions
launch-readiness-status
launch-real-media-proof-detail
launch-real-media-proof-legend
launch-real-media-proof-rows
launch-real-media-proof-status
launch-real-media-proof-summary
launch-sample-execution-detail
launch-sample-execution-legend
launch-sample-execution-rows
launch-sample-execution-status
launch-sample-execution-summary
launch-scope-reconciliation-detail
launch-scope-reconciliation-legend
launch-scope-reconciliation-rows
launch-scope-reconciliation-status
launch-scope-reconciliation-summary
launch-settings-intent-detail
launch-settings-intent-legend
launch-settings-intent-rows
launch-settings-intent-status
launch-settings-intent-summary
launch-settings-risk-detail
launch-settings-risk-legend
launch-settings-risk-rows
launch-settings-risk-status
launch-settings-risk-summary
launch-settings-trust-status
launch-settings-trust-summary
launch-start-decision-detail
launch-start-decision-legend
launch-start-decision-rows
launch-start-decision-status
launch-start-decision-summary
launch-timing
launch-timing-status
layout-editor-done
layout-editor-drawer
layout-editor-page-label
layout-editor-reset-all
layout-editor-reset-page
layout-editor-reset-subtab
layout-editor-status
layout-editor-tree
library-route-compare-left
library-route-compare-right
library-route-compare-rows
library-route-compare-title
library-route-decision-rows
library-route-decision-title
library-route-map-context
library-route-map-graph
library-route-map-profile-select
library-route-map-status
library-route-map-warning-summary
library-route-navigation-rows
library-route-navigation-title
library-route-node-rows
library-route-node-title
library-route-trace-rows
library-route-trace-selector
library-route-trace-title
library-route-validation-rows
library-route-validation-title
log-tail
maintenance-change-ledger-detail
maintenance-change-ledger-detail-status
maintenance-change-ledger-hygiene
maintenance-change-ledger-hygiene-status
maintenance-change-ledger-refresh-button
maintenance-change-ledger-risk-filter
maintenance-change-ledger-rows
maintenance-change-ledger-search
maintenance-change-ledger-status
maintenance-change-ledger-status-filter
maintenance-change-ledger-summary
maintenance-change-ledger-table-legend
maintenance-change-ledger-table-status
maintenance-change-ledger-type-filter
maintenance-detail
maintenance-detail-status
maintenance-diagnostics-actions
maintenance-diagnostics-status
maintenance-dry-run-confidence
maintenance-dry-run-confidence-status
maintenance-dry-run-history
maintenance-dry-run-history-status
maintenance-missing-count
maintenance-ok-count
maintenance-progress-bars
maintenance-progress-status
maintenance-progress-steps
maintenance-readiness
maintenance-readiness-status
maintenance-refresh-button
maintenance-rows
maintenance-status
maintenance-table-legend
maintenance-toolchain
maintenance-toolchain-status
maintenance-total-count
maintenance-warning-count
maintenance-warnings
media-pipeline-bootstrap
metrics-attention-rows
metrics-attention-status
metrics-backfill-button
metrics-backfill-detail
metrics-coverage-rows
metrics-coverage-status
metrics-data-produced
metrics-encode-count
metrics-evidence-status
metrics-final-library-rows
metrics-final-library-status
metrics-overview-bars
metrics-overview-status
metrics-pending-bytes
metrics-pending-state-rows
metrics-pending-status
metrics-production-bars
metrics-production-detail
metrics-production-status
metrics-reason-group-rows
metrics-reason-group-status
metrics-remux-count
metrics-route-bars
metrics-route-detail
metrics-route-series-rows
metrics-route-status
metrics-source-add-button
metrics-source-evidence
metrics-source-label
metrics-source-path
metrics-source-path-picker-badge
metrics-sources-rows
metrics-sources-status
metrics-storage-bars
metrics-storage-breakdown-rows
metrics-storage-saved
metrics-storage-status
metrics-summary
metrics-throughput-detail
metrics-throughput-rows
metrics-throughput-status
metrics-top-growth-rows
metrics-top-growth-status
metrics-top-savings-rows
metrics-top-savings-status
metrics-total-jobs
metrics-worker-active
metrics-worker-average-gbh
metrics-worker-bars
metrics-worker-coordinator
metrics-worker-count
metrics-worker-encoded-gb
metrics-worker-posture
metrics-worker-role
metrics-worker-rows
metrics-worker-session-completed
metrics-worker-session-failed
metrics-worker-status
metrics-worker-warnings
network-action-readiness-gates
network-advanced-evidence-drawer
network-api-status
network-api-summary
network-attention-stack
network-command-board-title
network-command-evidence-drawer
network-coordinator-active-rows
network-coordinator-active-status
network-coordinator-join-copy
network-coordinator-join-create
network-coordinator-join-output
network-coordinator-join-result
network-coordinator-join-rotate
network-coordinator-join-status
network-coordinator-join-url
network-coordinator-overview-status
network-coordinator-overview-summary
network-coordinator-overview-tiles
network-coordinator-queue-rows
network-coordinator-queue-status
network-coordinator-target
network-diagnostic-auth
network-diagnostic-claim
network-diagnostic-paths
network-diagnostic-queue
network-diagnostic-rail
network-diagnostic-state-files
network-diagnostic-tcp
network-evidence-detail
network-evidence-legend
network-evidence-rows
network-evidence-status
network-evidence-summary
network-health-alerts
network-health-drift
network-health-strip
network-health-workers
network-lifecycle-boundary-status
network-lifecycle-boundary-summary
network-lifecycle-command-result
network-lifecycle-confirm-cancel
network-lifecycle-confirm-designation
network-lifecycle-confirm-detail
network-lifecycle-confirm-dialog
network-lifecycle-confirm-submit
network-lifecycle-confirm-summary
network-lifecycle-confirm-title
network-lifecycle-control-buttons
network-lifecycle-control-status
network-lifecycle-control-summary
network-lifecycle-detail
network-lifecycle-legend
network-lifecycle-rows
network-lifecycle-status
network-lifecycle-summary
network-local-api
network-mode-model
network-open-history
network-open-history-status
network-readiness-status
network-readiness-summary
network-rerun-board-title
network-rerun-detail
network-rerun-rows
network-rerun-status
network-rerun-summary
network-role
network-role-coordinator-setup-button
network-role-dashboards
network-role-setup-bind-address
network-role-setup-close-button
network-role-setup-coordinator-fields
network-role-setup-coordinator-port
network-role-setup-designation
network-role-setup-dialog
network-role-setup-guardrail
network-role-setup-heartbeat-timeout
network-role-setup-honor-coordinator-policy
network-role-setup-local-encode
network-role-setup-path-map
network-role-setup-path-map-add-row
network-role-setup-path-map-editor
network-role-setup-path-map-label
network-role-setup-path-map-rows
network-role-setup-path-map-status
network-role-setup-path-map-test-result
network-role-setup-preview-button
network-role-setup-save-button
network-role-setup-stage-button
network-role-setup-summary
network-role-setup-title
network-role-setup-worker-encoder-map
network-role-setup-worker-fields
network-role-setup-worker-name
network-role-setup-worker-overrides
network-role-setup-worker-poll
network-role-setup-worker-url
network-role-setup-worker-url-error
network-role-worker-setup-button
network-route-summary
network-route-summary-status
network-settings-control-status
network-settings-drawer
network-settings-patch-handoff
network-settings-preview-button
network-settings-rows
network-settings-save-button
network-settings-status
network-setup-drawer
network-state-files-detail
network-state-files-legend
network-state-files-rows
network-state-files-status
network-state-files-summary
network-status
network-status-banner-detail
network-status-banner-lines
network-status-banner-title
network-summary
network-topology-strip
network-unavailable-actions-drawer
network-worker-board-title
network-worker-claim-rows
network-worker-claim-status
network-worker-detail
network-worker-discover
network-worker-discovery-list
network-worker-discovery-result
network-worker-discovery-status
network-worker-filter
network-worker-filter-summary
network-worker-join-blob
network-worker-join-import
network-worker-join-result
network-worker-join-status
network-worker-overview-status
network-worker-overview-summary
network-worker-overview-tiles
network-worker-poll
network-worker-progress-bars
network-worker-progress-status
network-worker-progress-summary
network-worker-remote-queue-status
network-worker-remote-queue-summary
network-worker-rows
network-worker-status
network-worker-status-filter
network-worker-summary
network-worker-table-legend
network-worker-view-presets
pending-action-blocked-count
pending-action-blockers-button
pending-action-detail
pending-action-drain-button
pending-action-drained-count
pending-action-evidence-count
pending-action-failed-count
pending-action-feedback
pending-action-primary
pending-action-ready-count
pending-action-reason
pending-action-refresh-button
pending-action-review-count
pending-action-status
pending-action-subtitle
pending-backend-scope-legend
pending-backend-scope-rows
pending-backend-scope-status
pending-backend-scope-summary
pending-clear-filters-button
pending-count
pending-detail
pending-diagnostics-actions
pending-diagnostics-guidance
pending-diagnostics-status
pending-drain-button
pending-drain-confidence-legend
pending-drain-confidence-rows
pending-drain-confidence-status
pending-drain-confidence-summary
pending-drain-correlation
pending-drain-correlation-status
pending-drain-decision-chips
pending-drain-decision-detail
pending-drain-decision-legend
pending-drain-decision-rows
pending-drain-decision-status
pending-drain-decision-summary
pending-drain-detail
pending-drain-events
pending-drain-events-status
pending-drain-guard-status
pending-drain-guard-summary
pending-drain-history
pending-drain-overview
pending-drain-progress-bars
pending-drain-status
pending-drain-summary
pending-drain-summary-status
pending-evidence-legend
pending-evidence-rows
pending-evidence-status
pending-evidence-summary
pending-file-inventory-legend
pending-file-inventory-rows
pending-file-inventory-status
pending-file-inventory-summary
pending-filter
pending-filter-summary
pending-health-count
pending-inventory-progress-bars
pending-investigation-filter
pending-live-run-status
pending-live-run-strip
pending-open-history
pending-open-status
pending-payload-count
pending-post-drain-trust-detail
pending-post-drain-trust-legend
pending-post-drain-trust-rows
pending-post-drain-trust-status
pending-post-drain-trust-summary
pending-publish-readiness
pending-publish-readiness-status
pending-reconcile-orphan-apply-button
pending-reconcile-orphan-detail
pending-reconcile-orphan-dry-run-button
pending-reconcile-orphan-history
pending-reconcile-orphan-status
pending-recovery-plan-all-button
pending-recovery-plan-detail
pending-recovery-plan-history
pending-recovery-plan-legend
pending-recovery-plan-row-detail
pending-recovery-plan-rows
pending-recovery-plan-selected-button
pending-recovery-plan-status
pending-repair-manifest-apply-button
pending-repair-manifest-detail
pending-repair-manifest-dry-run-button
pending-repair-manifest-history
pending-repair-manifest-legend
pending-repair-manifest-status
pending-review-board
pending-review-legend
pending-review-rows
pending-review-status
pending-risk
pending-risk-status
pending-rows
pending-selected-status
pending-selected-summary
pending-size
pending-status
pending-status-filter
pending-summary
pending-table-legend
pending-validation
pending-validation-status
pending-workflow
pending-workflow-status
pipeline-compact-gate-detail
pipeline-compact-gate-refresh-button
pipeline-compact-gate-status
pipeline-compact-gate-strip
pipeline-controller-backend-detail
pipeline-controller-backend-status
pipeline-controller-control-summary
pipeline-controller-last-start-status
pipeline-controller-last-start-summary
pipeline-controller-pipeline-state
pipeline-controller-stage-summary
pipeline-event-rows
pipeline-events-status
pipeline-gate-active
pipeline-gate-backend
pipeline-gate-last
pipeline-gate-queue
pipeline-gate-schedule
pipeline-gate-settings
pipeline-launch-detail
pipeline-launch-preflight
pipeline-launch-status
pipeline-live-control-state
pipeline-live-control-summary
pipeline-log-window-button
pipeline-single-file-browse-button
pipeline-single-file-browse-status
pipeline-single-file-clear-button
pipeline-single-file-path-picker-badge
pipeline-sparkline
pipeline-start-button
pipeline-start-disabled-reason
pipeline-start-mode
pipeline-start-schedule-override
pipeline-start-show-config
pipeline-start-show-console
pipeline-start-single-file
pipeline-start-sleep
pipeline-state
processed-count
progress-bar-list
progress-detail-rows
progress-detail-status
progress-evidence-detail
progress-evidence-legend
progress-evidence-rows
progress-evidence-status
progress-evidence-summary
publish-reconciliation-detail
publish-reconciliation-legend
publish-reconciliation-refresh-button
publish-reconciliation-rows
publish-reconciliation-status
publish-reconciliation-summary
queue-attention-status
queue-attention-summary
queue-backend-scope-legend
queue-backend-scope-rows
queue-backend-scope-status
queue-backend-scope-summary
queue-breakdown
queue-breakdown-status
queue-clear-filters-button
queue-collision
queue-collision-status
queue-count
queue-count-detail
queue-decision-status
queue-decision-summary
queue-detail
queue-diagnostics-actions
queue-diagnostics-guidance
queue-diagnostics-status
queue-excluded-detail
queue-excluded-open-status
queue-excluded-rows
queue-excluded-status
queue-excluded-summary
queue-excluded-table-legend
queue-filter
queue-filter-summary
queue-investigation-filter
queue-launch-decision-detail
queue-launch-decision-legend
queue-launch-decision-rows
queue-launch-decision-status
queue-launch-decision-summary
queue-loading-screen
queue-loading-status
queue-manual-discard-order-btn
queue-manual-move-bottom-btn
queue-manual-move-down-btn
queue-manual-move-top-btn
queue-manual-move-up-btn
queue-manual-order-status
queue-manual-save-order-btn
queue-open-history
queue-open-status
queue-page-next-btn
queue-page-prev-btn
queue-priority-clear-all-btn
queue-priority-hold-btn
queue-priority-low-btn
queue-priority-normal-btn
queue-priority-promote-btn
queue-priority-promote-movies-btn
queue-priority-promote-tv-btn
queue-priority-status
queue-progress-bars
queue-progress-status
queue-progress-summary
queue-readiness
queue-readiness-status
queue-review-board
queue-review-legend
queue-review-rows
queue-review-status
queue-rows
queue-runtime
queue-runtime-status
queue-selected-status
queue-selected-summary
queue-source-inventory
queue-status
queue-status-filter
queue-strategy-apply-btn
queue-strategy-select
queue-strategy-status
queue-summary
queue-table-legend
queue-table-page-status
queue-table-pagination
queue-validation
queue-validation-status
queue-workflow
queue-workflow-status
ram-chart
ram-chart-meta
ram-value
recent-errors
recent-events
refresh-button
refresh-health
release-build-button
release-build-detail
release-build-force
release-build-progress-bars
release-build-state-chip
release-build-state-hint
release-build-state-value
release-build-status
release-dry-run-button
release-dry-run-destination
release-dry-run-detail
release-dry-run-dev-docs
release-dry-run-keep-config
release-dry-run-optional-tools
release-dry-run-progress-bars
release-dry-run-state-chip
release-dry-run-state-hint
release-dry-run-state-value
release-dry-run-status
release-dry-run-tauri-binary
release-dry-run-tests
release-dry-run-tool-docs
release-dry-run-verify
release-dry-run-zip
release-package-status-strip
rename-add-path-button
rename-add-path-input
rename-apply-button
rename-apply-history
rename-apply-outcome-details
rename-apply-outcome-legend
rename-apply-outcome-rows
rename-apply-outcome-status
rename-apply-outcome-summary
rename-apply-progress-bars
rename-apply-readiness-details
rename-apply-readiness-legend
rename-apply-readiness-rows
rename-apply-readiness-status
rename-apply-status-hint
rename-apply-status-panel
rename-apply-status-summary
rename-batch-safety
rename-browse-files-button
rename-browse-folder-button
rename-check-all-button
rename-check-applicable-button
rename-clear-checks-button
rename-clear-paths-button
rename-confirm-apply-button
rename-confirm-cancel-button
rename-confirm-count
rename-confirm-dialog
rename-confirm-list
rename-confirm-mutation-warning
rename-confirm-title
rename-confirm-warning
rename-detail
rename-drop-zone
rename-file-source-status
rename-file-source-summary
rename-force-pipeline
rename-last-apply-detail
rename-last-apply-status
rename-log-bad-case-button
rename-log-bad-case-status
rename-log-case-cancel-button
rename-log-case-dialog
rename-log-case-expected-name
rename-log-case-expected-season
rename-log-case-expected-show
rename-log-case-message
rename-log-case-notes
rename-log-case-source-file
rename-log-case-source-folder
rename-log-case-status-select
rename-log-case-submit-button
rename-log-case-title
rename-manual-path-picker-badge
rename-mode
rename-movie-year
rename-paths
rename-pipeline-handoff
rename-pipeline-handoff-status
rename-pipeline-preview
rename-preview-button
rename-preview-status
rename-result-counts
rename-result-dialog
rename-result-errors
rename-result-failed
rename-result-failed-label
rename-result-open-log-button
rename-result-protected
rename-result-protected-label
rename-result-skipped
rename-result-skipped-label
rename-result-success
rename-result-success-label
rename-result-summary
rename-result-title
rename-result-unchanged
rename-result-unchanged-label
rename-review-board
rename-review-board-status
rename-rows
rename-season
rename-selected-count
rename-selection-audit
rename-selection-audit-status
rename-show
rename-sidecars
rename-stage-files-heading
rename-stage-mode-heading
rename-stage-preview-heading
rename-start
rename-status
rename-summary
rename-table-legend
rename-template-preset
rename-undo-button
rename-undo-status
report-audit-add-source-button
report-audit-clear-source-selection-button
report-audit-csv-state
report-audit-export-detail
report-audit-export-rerun-csv-button
report-audit-export-status
report-audit-ignore-selected-button
report-audit-launch-detail
report-audit-launch-preflight
report-audit-launch-status
report-audit-library-root-picker-badge
report-audit-scan-all-button
report-audit-scan-selected-button
report-audit-score-fallback-issue
report-audit-score-high-issue
report-audit-score-medium-issue
report-audit-score-policy-detail
report-audit-score-policy-reset-button
report-audit-score-policy-save-button
report-audit-score-policy-status
report-audit-score-policy-summary
report-audit-score-redownload-bonus
report-audit-score-redownload-bucket
report-audit-score-rerun-bonus
report-audit-score-rerun-bucket
report-audit-score-review-bucket
report-audit-select-all-sources-button
report-audit-source-rows
report-audit-source-selection-status
report-audit-source-status
report-audit-start-button
report-audit-start-include-sidecars
report-audit-start-library-root
report-audit-start-show-console
report-audit-stop-button
report-failure-json-state
report-investigation-checklist
report-investigation-status
report-open-history
report-open-history-disclosure
report-open-history-status
report-path-rows
report-path-status
report-priority-csv-state
report-progress-bars
report-progress-status
report-progress-summary
report-root-rows
report-root-status
report-triage
report-triage-action-owner
report-triage-audit-count
report-triage-band-detail
report-triage-band-status
report-triage-failure-count
report-triage-next-action
report-triage-report-state
report-triage-status
report-triage-warning-count
report-warning-count
report-warning-rows
report-warning-status
rerun-csv-path-picker-badge
rerun-history-summary
rerun-inspect-csv-button
rerun-lifecycle-detail
rerun-lifecycle-evidence
rerun-lifecycle-phase
rerun-lifecycle-summary
rerun-lifecycle-title
rerun-mode-policy-note
rerun-network-minimum-workers
rerun-network-start-dry-run-button
rerun-open-active-jobs-button
rerun-open-audit-tool-button
rerun-open-csv-button
rerun-open-csv-folder-button
rerun-open-last-stderr-button
rerun-open-last-stdout-button
rerun-open-latest-manifest-button
rerun-open-run-logs-button
rerun-policy-panel
rerun-preview-limit
rerun-preview-rows
rerun-preview-summary
rerun-preview-tiles
rerun-queue-detail
rerun-queue-preflight
rerun-queue-status
rerun-recent-csv-rows
rerun-results-panel
rerun-results-refresh-button
rerun-review-counts
rerun-review-csv
rerun-review-header
rerun-review-next-action
rerun-review-status
rerun-scope-bucket-filter
rerun-scope-enabled-only
rerun-scope-first-n
rerun-scope-issue-filter
rerun-scope-skip-blocked
rerun-scope-skip-warning-rows
rerun-show-command-history-button
rerun-start-button
rerun-start-collision-policy
rerun-start-confirm-source-overwrite
rerun-start-csv-path
rerun-start-destination-mode
rerun-start-execution-mode
rerun-start-target-mode
rerun-start-window-size
rerun-state-rows
rerun-state-status-filter
rerun-stop-after-current-button
reset-layout-btn
sample-validation-acceptance-gate-detail
sample-validation-acceptance-gate-legend
sample-validation-acceptance-gate-rows
sample-validation-acceptance-gate-status
sample-validation-acceptance-gate-summary
sample-validation-append-button
sample-validation-category
sample-validation-category-summary
sample-validation-category-summary-detail
sample-validation-category-summary-legend
sample-validation-category-summary-rows
sample-validation-category-summary-status
sample-validation-check-audio
sample-validation-check-completed-output
sample-validation-check-diagnostics
sample-validation-check-pending-publish
sample-validation-check-queue-route
sample-validation-check-sidecar-manifest
sample-validation-check-size-growth
sample-validation-check-status
sample-validation-check-subtitle
sample-validation-clear-checks-button
sample-validation-completed-packet-detail
sample-validation-completed-packet-legend
sample-validation-completed-packet-markdown
sample-validation-completed-packet-rows
sample-validation-completed-packet-status
sample-validation-completed-packet-summary
sample-validation-cutover-detail
sample-validation-cutover-legend
sample-validation-cutover-rows
sample-validation-cutover-status
sample-validation-cutover-summary
sample-validation-decision
sample-validation-decision-strip
sample-validation-decision-strip-summary
sample-validation-detail
sample-validation-execution-detail
sample-validation-execution-legend
sample-validation-execution-rows
sample-validation-execution-status
sample-validation-execution-summary
sample-validation-gap-detail
sample-validation-gap-legend
sample-validation-gap-rows
sample-validation-gap-status
sample-validation-gap-summary
sample-validation-legend
sample-validation-notes
sample-validation-preview-button
sample-validation-record-review-detail
sample-validation-record-review-legend
sample-validation-record-review-rows
sample-validation-record-review-status
sample-validation-record-review-summary
sample-validation-records
sample-validation-result
sample-validation-runbook-detail
sample-validation-runbook-legend
sample-validation-runbook-markdown
sample-validation-runbook-rows
sample-validation-runbook-status
sample-validation-runbook-summary
sample-validation-sample-set-detail
sample-validation-sample-set-legend
sample-validation-sample-set-rows
sample-validation-sample-set-status
sample-validation-sample-set-summary
sample-validation-status
sample-validation-strip-clear-checks-button
sample-validation-strip-preview-button
sample-validation-summary
sample-validation-use-sample-set-category-button
sample-validation-worksheet-detail
sample-validation-worksheet-legend
sample-validation-worksheet-rows
sample-validation-worksheet-status
sample-validation-worksheet-summary
schedule-allowed-state
schedule-coverage-detail
schedule-coverage-rows
schedule-coverage-scope
schedule-coverage-status
schedule-current-scope
schedule-day-detail
schedule-day-legend
schedule-day-rows
schedule-day-scope
schedule-day-status
schedule-editor-allow-all-button
schedule-editor-clear-button
schedule-editor-draft-summary
schedule-editor-enabled
schedule-editor-impact
schedule-editor-load-current-button
schedule-editor-panel
schedule-editor-preview-button
schedule-editor-result
schedule-editor-rows
schedule-editor-save-button
schedule-editor-save-state
schedule-editor-status
schedule-enabled-state
schedule-guidance
schedule-guidance-scope
schedule-guidance-status
schedule-next-start
schedule-status
schedule-summary
schedule-timing
schedule-timing-scope
schedule-timing-status
schedule-watch-folder-event-rows
schedule-watch-folder-recent
schedule-watch-folder-root-rows
schedule-watch-folder-scope
schedule-watch-folder-status
schedule-watch-folder-summary
schedule-window-end
settings-active-media-policy-legend
settings-active-media-policy-rows
settings-active-media-policy-status
settings-active-media-policy-summary
settings-audio-allow-no-audio
settings-audio-apply-button
settings-audio-auto-bitrate
settings-audio-builder-status
settings-audio-compatible-codecs
settings-audio-downmix-mode
settings-audio-guidance
settings-audio-max-channels
settings-audio-passthrough-profile
settings-audio-preferred-languages
settings-audio-reset-button
settings-audio-transcode-bitrate
settings-audio-transcode-codec
settings-backend-media-policy-legend
settings-backend-media-policy-rows
settings-backend-media-policy-status
settings-backend-media-policy-summary
settings-backend-result-detail
settings-backend-result-legend
settings-backend-result-rows
settings-backend-result-status
settings-backend-result-summary
settings-bitrate-estimate-1080p
settings-bitrate-estimate-1440p
settings-bitrate-estimate-4k
settings-boundary-1080p-end
settings-boundary-1080p-end-readout
settings-boundary-1440p-end
settings-boundary-1440p-start
settings-boundary-4k-start
settings-boundary-4k-start-readout
settings-builder-1080p-route-bitrate
settings-builder-1080p-upper-tolerance
settings-builder-1080p-upper-tolerance-readout
settings-builder-1440p-lower-tolerance
settings-builder-1440p-lower-tolerance-readout
settings-builder-1440p-route-bitrate
settings-builder-1440p-upper-tolerance
settings-builder-1440p-upper-tolerance-readout
settings-builder-4k-lower-tolerance
settings-builder-4k-lower-tolerance-readout
settings-builder-4k-route-bitrate
settings-builder-apply-button
settings-builder-compat-growth
settings-builder-encode-ladder
settings-builder-encode-tuning
settings-builder-encoder-backend
settings-builder-guidance
settings-builder-max-growth
settings-builder-movie-1080p-target
settings-builder-movie-1440p-target
settings-builder-movie-4k-target
settings-builder-output-container
settings-builder-quality-enable
settings-builder-quality-fail-action
settings-builder-quality-fail-threshold
settings-builder-quality-metric
settings-builder-quality-sample-count
settings-builder-quality-sample-mode
settings-builder-quality-sample-seconds
settings-builder-quality-timeout
settings-builder-quality-warn-threshold
settings-builder-reset-button
settings-builder-route-threshold-mode
settings-builder-routing-profile
settings-builder-routing-profile-key-readout
settings-builder-size-guard
settings-builder-status
settings-builder-tv-1080p-target
settings-builder-tv-1440p-target
settings-builder-tv-4k-target
settings-builder-video-codec
settings-command-history
settings-command-history-status
settings-container-size-container
settings-count
settings-deployment-action-detail
settings-deployment-action-status
settings-deployment-launch-button
settings-deployment-path-panel
settings-deployment-repair-button
settings-deployment-start-button
settings-deployment-verify-button
settings-effective-policy-detail
settings-effective-policy-legend
settings-effective-policy-rows
settings-effective-policy-status
settings-effective-policy-summary
settings-encode-ladder-help
settings-encode-tuning-help
settings-encoder-capability-legend
settings-encoder-capability-panel
settings-encoder-capability-rows
settings-encoder-capability-status
settings-encoder-capability-summary
settings-file-safety-aggressive-episode
settings-file-safety-apply-button
settings-file-safety-builder-status
settings-file-safety-cleanup-age
settings-file-safety-cleanup-remote
settings-file-safety-create-tv-subfolder
settings-file-safety-deferred-publish
settings-file-safety-enable-integrity
settings-file-safety-enable-watch
settings-file-safety-guidance
settings-file-safety-local-base
settings-file-safety-local-base-browse
settings-file-safety-local-base-picker-badge
settings-file-safety-min-free
settings-file-safety-output-size-multiplier
settings-file-safety-outsource
settings-file-safety-outsource-browse
settings-file-safety-outsource-min-free
settings-file-safety-outsource-picker-badge
settings-file-safety-reset-button
settings-file-safety-robocopy-flags
settings-file-safety-skip-stability
settings-file-safety-source-movies
settings-file-safety-source-movies-browse
settings-file-safety-source-movies-picker-badge
settings-file-safety-source-tv
settings-file-safety-source-tv-browse
settings-file-safety-source-tv-picker-badge
settings-file-safety-stability-wait
settings-file-safety-valid-extensions
settings-file-safety-watch-action
settings-file-safety-watch-debounce
settings-file-safety-watch-respect-schedule
settings-file-safety-watch-roots
settings-file-safety-watch-roots-picker-badge
settings-filter
settings-handbrake-active-preset
settings-handbrake-decision
settings-handbrake-output-container
settings-handbrake-output-guards
settings-handbrake-output-video
settings-handbrake-preview-detail
settings-handbrake-preview-status
settings-handbrake-publish-requirements
settings-height-1080p-range
settings-height-1440p-range
settings-height-4k-range
settings-height-pixel-summary
settings-launch-impact-legend
settings-launch-impact-rows
settings-launch-impact-status
settings-launch-impact-summary
settings-libraries-status
settings-library-active-detail
settings-library-active-title
settings-library-add-button
settings-library-build-patch-button
settings-library-defaults-button
settings-library-delete-button
settings-library-editor-state
settings-library-editor-status
settings-library-patch-state
settings-library-preview-button
settings-library-profile-list
settings-library-profile-nav
settings-library-reset-button
settings-library-route-map-scope
settings-library-save-button
settings-library-scan-sources-button
settings-library-state-strip
settings-library-summary-detail
settings-library-summary-panel
settings-library-summary-rows
settings-library-summary-status
settings-library-summary-strip
settings-library-summary-warning
settings-library-warning-summary
settings-library-watch-auto-run
settings-library-watch-panel
settings-library-watch-preview-button
settings-library-watch-respect-schedule
settings-library-watch-save-button
settings-library-watch-stage-button
settings-library-watch-status
settings-library-watch-summary
settings-media-policy-legend
settings-media-policy-rows
settings-media-policy-status
settings-media-policy-summary
settings-network-apply-button
settings-network-bind-address
settings-network-builder-status
settings-network-coordinator-local-encode
settings-network-coordinator-port
settings-network-guidance
settings-network-heartbeat-timeout
settings-network-honor-coordinator-policy
settings-network-path-map
settings-network-path-map-add-row
settings-network-path-map-editor
settings-network-path-map-label
settings-network-path-map-rows
settings-network-path-map-status
settings-network-path-map-test-result
settings-network-reset-button
settings-network-role
settings-network-worker-encoder-map
settings-network-worker-name
settings-network-worker-overrides
settings-network-worker-poll
settings-network-worker-url
settings-network-worker-url-error
settings-open-wizard-button
settings-overview-rows
settings-overview-status
settings-patch-detail
settings-patch-impact-summary
settings-patch-json
settings-patch-status
settings-patch-summary-changed-only
settings-patch-summary-rows
settings-patch-summary-status
settings-paths
settings-pending-apply-button
settings-pending-block-budget-gib
settings-pending-builder-status
settings-pending-cleanup-age
settings-pending-cleanup-remote
settings-pending-deferred-publish
settings-pending-enable-integrity
settings-pending-guidance
settings-pending-output-size-multiplier
settings-pending-outsource-min-free
settings-pending-reset-button
settings-pending-review-budget-gib
settings-pending-robocopy-flags
settings-pending-robocopy-timeout
settings-pending-skip-stability
settings-pending-transient-retry-limit
settings-policy-delta-legend
settings-policy-delta-rows
settings-policy-delta-status
settings-policy-delta-summary
settings-profiles
settings-quality-apply-button
settings-quality-builder-status
settings-quality-guidance
settings-quality-reset-button
settings-queue-apply-button
settings-queue-builder-status
settings-queue-guidance
settings-queue-min-pipeline-version
settings-queue-priority-markers
settings-queue-processed-index-refresh
settings-queue-reprocess-all
settings-queue-reset-button
settings-raw-action-plan-detail
settings-raw-action-plan-legend
settings-raw-action-plan-rows
settings-raw-action-plan-status
settings-raw-action-plan-summary
settings-raw-triage
settings-raw-triage-detail
settings-raw-triage-legend
settings-raw-triage-rows
settings-raw-triage-status
settings-reload-button
settings-rename-cleaning-filter-status
settings-rename-cleaning-filter-summary
settings-rename-cleaning-filters-details
settings-rename-cleaning-filters-reset-button
settings-rename-filter-audio-channels
settings-rename-filter-editions
settings-rename-filter-file-size
settings-rename-filter-languages-subs-dubs
settings-rename-filter-release-groups
settings-rename-filter-services-containers
settings-rename-filter-video-source
settings-rename-remove-terms
settings-rename-tv-filter-audio-channels
settings-rename-tv-filter-languages-subs-dubs
settings-rename-tv-filter-release-flags
settings-rename-tv-filter-release-groups
settings-rename-tv-filter-services-containers
settings-rename-tv-filter-video-source
settings-rename-tv-remove-terms
settings-rename-workbench-expected-episode
settings-rename-workbench-expected-episode-title
settings-rename-workbench-expected-movie-title
settings-rename-workbench-expected-season
settings-rename-workbench-expected-show
settings-rename-workbench-expected-year
settings-rename-workbench-form
settings-rename-workbench-message
settings-rename-workbench-mode
settings-rename-workbench-notes
settings-rename-workbench-output
settings-rename-workbench-result-heading
settings-rename-workbench-retest-button
settings-rename-workbench-save-case-button
settings-rename-workbench-save-filters-button
settings-rename-workbench-save-state
settings-rename-workbench-source-file
settings-rename-workbench-source-folder
settings-rename-workbench-stage-suggestions-button
settings-rename-workbench-status
settings-rename-workbench-suggestions
settings-rename-workbench-template
settings-rename-workbench-test-button
settings-route-boundary-1080p-end-input
settings-route-boundary-4k-start-input
settings-route-card-range-1080p
settings-route-card-range-1440p
settings-route-card-range-4k
settings-route-consequence-summary
settings-route-height-slider
settings-route-trigger-summary
settings-routing-output-container-readout
settings-routing-video-codec-readout
settings-routing-video-preset-readout
settings-routing-video-quality-readout
settings-rows
settings-runtime-allow-system-tools
settings-runtime-apply-button
settings-runtime-builder-status
settings-runtime-cleanup-scan-timeout
settings-runtime-console-log
settings-runtime-cpu-encode-timeout
settings-runtime-debug-mode
settings-runtime-failure-artifact-cleanup-target
settings-runtime-failure-artifact-retention
settings-runtime-failure-artifact-threshold
settings-runtime-ffmpeg-encode-timeout
settings-runtime-ffmpeg-remux-timeout
settings-runtime-file-log
settings-runtime-guidance
settings-runtime-index-scan-timeout
settings-runtime-log-retention
settings-runtime-mkvmerge-timeout
settings-runtime-reset-button
settings-runtime-robocopy-timeout
settings-runtime-source-scan-interval
settings-runtime-source-scan-timeout
settings-runtime-transient-retry-limit
settings-safety-lock-rows
settings-safety-lock-status
settings-safety-lock-summary
settings-save-header
settings-save-header-patch-status
settings-save-header-reload-button
settings-save-header-reload-status
settings-save-header-save-button
settings-save-patch-button
settings-save-progress-bars
settings-save-readiness
settings-save-readiness-status
settings-save-review-cancel-button
settings-save-review-confirm-button
settings-save-review-detail
settings-save-review-dialog
settings-save-review-dialog-changed
settings-save-review-dialog-detail
settings-save-review-dialog-resets
settings-save-review-dialog-rows
settings-save-review-dialog-submitted
settings-save-review-legend
settings-save-review-rows
settings-save-review-summary
settings-save-review-title
settings-status
settings-subtitle-apply-button
settings-subtitle-ass-signs-forced
settings-subtitle-bdpgs-languages
settings-subtitle-bdpgs-ocr-tessdata-path
settings-subtitle-bdpgs-ocr-tool-path
settings-subtitle-bdpgs-ocr-tool-picker-badge
settings-subtitle-bdpgs-path-evidence
settings-subtitle-bdpgs-path-status
settings-subtitle-bdpgs-signs-forced
settings-subtitle-bdpgs-tessdata-picker-badge
settings-subtitle-bdpgs-timeout
settings-subtitle-builder-status
settings-subtitle-convert-bdpgs
settings-subtitle-convert-tx3g
settings-subtitle-convert-vobsub
settings-subtitle-drop-ass
settings-subtitle-drop-bdpgs
settings-subtitle-drop-tx3g
settings-subtitle-drop-vobsub
settings-subtitle-exclude-styles
settings-subtitle-extract-timeout
settings-subtitle-forced-tx3g
settings-subtitle-guidance
settings-subtitle-include-styles
settings-subtitle-keep-signs
settings-subtitle-languages
settings-subtitle-merge-adjacent
settings-subtitle-merge-threshold
settings-subtitle-preserve-tx3g-srt
settings-subtitle-probe-timeout
settings-subtitle-remove-karaoke
settings-subtitle-reset-button
settings-subtitle-sdh-keywords
settings-subtitle-sidecar-tx3g
settings-subtitle-strip-formatting
settings-subtitle-supplemental-keywords
settings-subtitle-tx3g-languages
settings-subtitle-tx3g-signs-forced
settings-subtitle-vobsub-languages
settings-subtitle-vobsub-ocr-tool-path
settings-subtitle-vobsub-ocr-tool-picker-badge
settings-subtitle-vobsub-path-evidence
settings-subtitle-vobsub-path-status
settings-subtitle-vobsub-signs-forced
settings-subtitle-vobsub-timeout
settings-summarize-patch-button
settings-summary-copy-remux-intent
settings-summary-encode-if-required
settings-summary-output-container
settings-summary-preview-scope
settings-summary-processing-strategy
settings-summary-size-bitrate-guards
settings-trust-status
settings-trust-summary
settings-tv-library-folder-evidence
settings-tv-library-folder-status
settings-validate-button
settings-validation
settings-video-apply-button
settings-video-apply-hint
settings-video-builder-status
settings-video-cpu-preset
settings-video-cpu-priority
settings-video-cpu-quality
settings-video-cpu-threads
settings-video-extra-flags
settings-video-guidance
settings-video-h264-max-bitrate
settings-video-h264-max-height
settings-video-h264-remux
settings-video-preset
settings-video-preset-help
settings-video-preset-value
settings-video-quality
settings-video-quality-help
settings-video-quality-value
settings-video-remux-safe-codecs
settings-video-reset-button
settings-wizard-acknowledgement-list
settings-wizard-add-library-button
settings-wizard-back-button
settings-wizard-copy-diagnostics-button
settings-wizard-detect-tools-button
settings-wizard-hardware-result
settings-wizard-library-list
settings-wizard-next-button
settings-wizard-path-rows
settings-wizard-phase-0-status
settings-wizard-phase-1-status
settings-wizard-phase-2-status
settings-wizard-phase-3-status
settings-wizard-phase-4-status
settings-wizard-preview-button
settings-wizard-probe-hardware-button
settings-wizard-readiness-blockers
settings-wizard-readiness-changed
settings-wizard-readiness-draft
settings-wizard-readiness-preview
settings-wizard-readiness-strip
settings-wizard-readiness-validation
settings-wizard-readiness-warnings
settings-wizard-review-summary
settings-wizard-save-button
settings-wizard-save-result
settings-wizard-status
settings-wizard-status-detail
settings-wizard-summary-rows
settings-wizard-tools-result
settings-wizard-validate-paths-button
settings-wizard-validate-workers-button
settings-wizard-validation-summary
settings-wizard-workers-result
state-pill
status-summary
tdarr-matrix-audit-bucket-filter
tdarr-matrix-audit-bucket-rows
tdarr-matrix-audit-bucket-status
tdarr-matrix-audit-detail
tdarr-matrix-audit-evidence-actions
tdarr-matrix-audit-evidence-status
tdarr-matrix-audit-filter
tdarr-matrix-audit-finding-detail
tdarr-matrix-audit-findings-rows
tdarr-matrix-audit-findings-status
tdarr-matrix-audit-load-latest
tdarr-matrix-audit-rerun-failures
tdarr-matrix-audit-rerun-selected
tdarr-matrix-audit-severity-filter
tdarr-matrix-audit-status
tdarr-matrix-compare-left
tdarr-matrix-compare-refresh
tdarr-matrix-compare-right
tdarr-matrix-console-summary
tdarr-matrix-delete-confirm
tdarr-matrix-proof-pack-rows
tdarr-matrix-proof-pack-status
tdarr-matrix-run-compare-rows
tdarr-matrix-run-compare-status
telemetry-expected-encoder
telemetry-kpi-cpu-value
telemetry-kpi-encoder-value
telemetry-kpi-gpu-status
telemetry-kpi-ram-value
telemetry-live-state
telemetry-operator-next-step
telemetry-operator-state
telemetry-operator-state-label
telemetry-readiness-status
telemetry-readiness-summary
telemetry-refresh-cadence
telemetry-sample-age
telemetry-source
topbar-event-ticker
wizard-ack-AllowNoAudio
wizard-ack-AllowSystemTools
wizard-ack-CleanupRemoteStaging
wizard-ack-ReprocessAll
wizard-audio-codec
wizard-audio-policy
wizard-danger-allow-no-audio
wizard-danger-allow-system-tools
wizard-danger-cleanup-remote
wizard-danger-reprocess-all
wizard-existing-policy
wizard-ffmpeg-path
wizard-ffmpeg-path-picker-badge
wizard-ffprobe-path
wizard-ffprobe-path-picker-badge
wizard-keep-all-audio
wizard-keep-unknown-subtitles
wizard-library-category-list
wizard-max-parallel-encodes
wizard-min-free-space-gb
wizard-mode
wizard-output-container
wizard-output-root
wizard-output-root-picker-badge
wizard-outsource-min-free-space-gb
wizard-parallel-encode-mode
wizard-preferred-codec
wizard-preserve-forced-subtitles
wizard-publish-mode
wizard-retry-limit
wizard-safety-integrity
wizard-safety-pending
wizard-safety-skip-processed
wizard-safety-stability
wizard-scratch-path
wizard-scratch-path-picker-badge
wizard-subtitle-languages
wizard-subtitle-policy
wizard-video-preset
wizard-video-quality
wizard-video-strategy
```
<!-- END GENERATED DOM ID MANIFEST -->
