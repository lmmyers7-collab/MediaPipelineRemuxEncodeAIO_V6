---
file: apps/desktop/webview/static/assets/pipelineLogWindow.js
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: JavaScript
pipeline_stage: n/a
token_priority: medium
owner_domain: webview
last_modified: 2026-07-04
last_reviewed: 2026-06-24
sha256: f1f0891ab23f25f8467764826bc18878cc4df49b6174376d8dd024cd245b3769
---
# `apps/desktop/webview/static/assets/pipelineLogWindow.js`

**Purpose:** JavaScript implementation for pipeline log window; exposes activeEvidenceState, activeJobRowLooksRelevant, activeJobsSummaryLines.

**Public symbols:** `activeEvidenceState`, `activeJobRowLooksRelevant`, `activeJobsSummaryLines`, `activeProcessLogLines`, `activeWorkEvidenceLines`, `activeWorkLogLines`, `boundedLogLine`, `byId`, `closeReadinessIndicatesActiveWork`, `closeReadinessLine`, `compactRepeatedProgressLines`, `displayMode`, `flushPending`, `hasActiveWorkEvidence`, `initPipelineLogWindow`, `isNearBottom`, `isPlainObject`, `localTimestamp`, `logTextLines`, `pipelineLogDisplayText`, `progressCompactionKey`, `readCloseReadiness`, `readRawPipelineLogTail`, `refreshPipelineLogWindow`, `renderPipelineLogWindow`, `renderRawPipelineLogWindow`, `renderRefreshError`, `scrollToBottom`, `setDetail`, `setStatus`, `setUpdated`, `startRefreshTimer`, `summarizeActiveJobRow`, `workerProgressSummaryLines`
**In-repo imports:** `window.addEventListener`, `window.clearInterval`, `window.mediaPipelineApi`, `window.mediaPipelinePipelineLogWindow`, `window.requestAnimationFrame`, `window.setInterval`
**HTTP routes:** `/api/backend/close-readiness`, `/api/backend/close-readiness.`, `/api/diagnostics`, `/api/diagnostics/tail?target=pipeline_log&max_bytes=262144`, `/api/diagnostics/tail?target=pipeline_log.`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths apps/desktop/webview/static/assets/pipelineLogWindow.js`._
