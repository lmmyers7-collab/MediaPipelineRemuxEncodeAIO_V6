---
file: apps/desktop/webview/static/assets/diagnostics/matrixConsole.js
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: JavaScript
pipeline_stage: observability
token_priority: medium
owner_domain: webview
last_modified: 2026-07-15
last_reviewed: 2026-07-11
sha256: 48954f3280b98329a61d91623a1636e77186cb32abff4db714d6790a9ee75449
---
# `apps/desktop/webview/static/assets/diagnostics/matrixConsole.js`

**Purpose:** JavaScript implementation for matrix console; exposes appendTdarrMatrixAuditFindingCell, createDiagnosticsMatrixConsoleModule, getTdarrMatrixConsoleState.

**Public symbols:** `appendTdarrMatrixAuditFindingCell`, `createDiagnosticsMatrixConsoleModule`, `getTdarrMatrixConsoleState`, `rejectTdarrMatrixAuditWhileBusy`, `renderTdarrMatrixAuditFindings`, `renderTdarrMatrixBucketCoverage`, `renderTdarrMatrixConsole`, `renderTdarrMatrixEvidenceActions`, `renderTdarrMatrixProofPackRows`, `renderTdarrMatrixRunComparison`, `renderTdarrMatrixSelectedFinding`, `requestTdarrMatrixAudit`, `requestTdarrMatrixConsole`, `requestTdarrMatrixEvidenceOpen`, `requestTdarrMatrixRerun`, `requestTdarrMatrixRunComparison`, `scheduleTdarrMatrixBackgroundPoll`, `selectFinding`, `setTdarrMatrixAuditBusy`, `setTdarrMatrixAuditDetail`, `setTdarrMatrixAuditStatus`, `stopTdarrMatrixBackgroundPoll`, `tdarrMatrixActionGate`, `tdarrMatrixActionSeverity`, `tdarrMatrixAuditActionLabel`, `tdarrMatrixAuditDetailLines`, `tdarrMatrixAuditFindingMessage`, `tdarrMatrixAuditFindingRoute`, `tdarrMatrixCompareExamples`, `tdarrMatrixDeleteConfirmReady`, `tdarrMatrixFilteredFindings`, `tdarrMatrixFilteredProofRows`, `tdarrMatrixFindingSearchText`, `tdarrMatrixHasLatestEvidence`, `tdarrMatrixHasProofEvidence`
**In-repo imports:** `window.__diagnosticsMatrixConsoleModule`, `window.clearInterval`, `window.confirm`, `window.setInterval`
**HTTP routes:** `/api/diagnostics/tdarr-matrix-audit`, `/api/diagnostics/tdarr-matrix/compare?`, `/api/diagnostics/tdarr-matrix/evidence/open`, `/api/diagnostics/tdarr-matrix/latest?`, `/api/diagnostics/tdarr-matrix/rerun`
**DOM selectors:** `[data-tdarr-matrix-audit-action]`, `[data-tdarr-proof-pack-view]`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths apps/desktop/webview/static/assets/diagnostics/matrixConsole.js`._
