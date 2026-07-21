---
file: apps/desktop/webview/static/assets/diagnosticsView.js
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: JavaScript
pipeline_stage: observability
token_priority: medium
owner_domain: webview
last_modified: 2026-07-15
last_reviewed: 2026-06-04
sha256: 08096597a90a62ac2b22c4485118d5fd8c739a296cd72271e34d8510606859cc
---
# `apps/desktop/webview/static/assets/diagnosticsView.js`

**Purpose:** JavaScript implementation for diagnostics view; exposes appendDiagnosticsActionGroup, boundedDiagnosticsText, byName.

**Public symbols:** `appendDiagnosticsActionGroup`, `boundedDiagnosticsText`, `byName`, `compactedDiagnosticsTextLines`, `compactRepeatedProgressLines`, `diagnosticsActionGroups`, `diagnosticsActionGroupText`, `diagnosticsActionLabel`, `diagnosticsActionPlanLines`, `diagnosticsArtifactsForLine`, `diagnosticsBridgeApi`, `diagnosticsFailureMessage`, `diagnosticsLogPanelStatus`, `diagnosticsLongRunReliabilityLines`, `diagnosticsMalformedStateLines`, `diagnosticsOrderedActions`, `diagnosticsPayloadFirstString`, `diagnosticsPayloadFlag`, `diagnosticsRealMediaBoundaryLines`, `diagnosticsSeverityForLine`, `diagnosticsTextLines`, `flushPending`, `initDiagnosticsViewEvents`, `progressCompactionKey`, `rejectDiagnosticsOpenWhileBusy`, `renderDiagnostics`, `renderDiagnosticsRefreshFailures`, `requestDiagnosticsOpen`, `setDiagnosticsOpenBusy`, `setDiagnosticsOpenStatus`, `setDiagnosticsPanelStatus`, `setTextIfChanged`
**In-repo imports:** `window.__diagnosticsActiveJobsModule`, `window.__diagnosticsFirstResponseModule`, `window.__diagnosticsInvestigationModule`, `window.__diagnosticsLogModule`, `window.__diagnosticsMatrixConsoleModule`, `window.__diagnosticsTriageModule`, `window.activeJobDiagnosticsActions`, `window.activeJobRowKey`, `window.appendDiagnosticsActionGroup`, `window.diagnosticsActionGroups`, `window.diagnosticsActionPlanLines`, `window.diagnosticsActiveJobRealMediaTraceLines`, `window.diagnosticsArtifactsForLine`, `window.diagnosticsCommandIssueRows`, `window.diagnosticsCompletedFinalTrustLines`, `window.diagnosticsCompletedFinalTrustStepForRow`, `window.diagnosticsCompletedPolicyReconciliationLines`, `window.diagnosticsConflictSignalLabel`, `window.diagnosticsCrossPageConflictRows`, `window.diagnosticsInvestigationActions`, `window.diagnosticsInvestigationStatus`, `window.diagnosticsLineTimestamp`, `window.diagnosticsListText`, `window.diagnosticsLogRows`, `window.diagnosticsMalformedStateLines`, `window.diagnosticsOwnerDefaultAction`, `window.diagnosticsOwnerHandoffActions`, `window.diagnosticsOwnerHandoffRowKey`, `window.diagnosticsOwnerHandoffRows`, `window.diagnosticsOwnerHandoffStatus`, `window.diagnosticsOwnerHandoffSummaryLines`, `window.diagnosticsOwnerNavigationLabel`, `window.diagnosticsOwnerPageId`, `window.diagnosticsOwnerRowSeverity`, `window.diagnosticsOwnerSelectFunction`
**HTTP routes:** `/api/diagnostics/open`
**State/config identifiers:** `stateDb.db`
**DOM selectors:** `[data-read-diagnostics-tail]`, `[data-tdarr-matrix-audit-action]`, `[data-tdarr-proof-pack-view]`, `button[data-open-target-action-group]`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths apps/desktop/webview/static/assets/diagnosticsView.js`._
