---
file: apps/desktop/webview/static/assets/app/refreshCoordinator.js
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: JavaScript
pipeline_stage: n/a
token_priority: medium
owner_domain: webview
last_modified: 2026-07-26
last_reviewed: 2026-07-11
sha256: dcfba5ff4807b7d9d37c8eeb3b2b9364dfb0632a841ae6fc6d2637a848e2f16b
---
# `apps/desktop/webview/static/assets/app/refreshCoordinator.js`

**Purpose:** JavaScript implementation for refresh coordinator; exposes activeRefreshPage, mergeRefreshOptions, normalizeRefreshOptions.

**Public symbols:** `activeRefreshPage`, `mergeRefreshOptions`, `normalizeRefreshOptions`, `refreshAll`, `refreshAllNow`, `refreshCurrentOutputStatus`, `refreshGet`, `refreshLiveRunTail`, `refreshRequestIncluded`
**In-repo imports:** `window.mediaPipelineAppRefresh`, `window.mediaPipelineCommandHistory`, `window.mediaPipelineCompletedView`, `window.mediaPipelineContractView`, `window.mediaPipelineDiagnosticsStateSummaryView`, `window.mediaPipelineDiagnosticsView`, `window.mediaPipelineDom`, `window.mediaPipelineFloatingPipelineLog`, `window.mediaPipelineLaunchView`, `window.mediaPipelineLibraryRouteMap`, `window.mediaPipelineMaintenanceView`, `window.mediaPipelineMetricsView`, `window.mediaPipelineNetworkView`, `window.mediaPipelineOperatorToast`, `window.mediaPipelinePresetLibraryView`, `window.mediaPipelineProgressView`, `window.mediaPipelineProvenanceView`, `window.mediaPipelineQueueView`, `window.mediaPipelineRecoverySupportView`, `window.mediaPipelineReportsView`, `window.mediaPipelineRunMonitor`, `window.mediaPipelineScheduleView`, `window.mediaPipelineSettingsLibraries`, `window.mediaPipelineSettingsView`, `window.setTimeout`
**HTTP routes:** `/api/audit-controls`, `/api/audit-results?limit=100`, `/api/audit-sources`, `/api/backend/close-readiness`, `/api/backend/recovery-status`, `/api/commands?limit=20`, `/api/completed?limit=500`, `/api/diagnostics`, `/api/diagnostics/state-summary`, `/api/diagnostics/tail?target=last_stdout_log&max_bytes=65536`, `/api/failures/artifacts`, `/api/failures?limit=100`, `/api/final-library-promotion/status.`, `/api/health`, `/api/libraries/route-map`, `/api/libraries/summary`, `/api/maintenance/productization`, `/api/metrics`, `/api/network/workers`, `/api/pending-publish`, `/api/queue`, `/api/rerun/results?limit=24`, `/api/sample-validation?limit=10`, `/api/schedule`
**DOM selectors:** `[data-page-panel].is-visible`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths apps/desktop/webview/static/assets/app/refreshCoordinator.js`._
