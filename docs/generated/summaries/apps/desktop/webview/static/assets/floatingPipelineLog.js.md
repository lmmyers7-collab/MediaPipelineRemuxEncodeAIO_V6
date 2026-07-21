---
file: apps/desktop/webview/static/assets/floatingPipelineLog.js
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: JavaScript
pipeline_stage: n/a
token_priority: medium
owner_domain: webview
last_modified: 2026-07-04
last_reviewed: 2026-06-25
sha256: 4938ebd1810df4a2d270b231bbdea7d9277c2189678a385ce7d52abf8af263c4
---
# `apps/desktop/webview/static/assets/floatingPipelineLog.js`

**Purpose:** JavaScript implementation for floating pipeline log; exposes activeEvidenceState, activeJobRowLooksRelevant, activeJobsSummaryLines.

**Public symbols:** `activeEvidenceState`, `activeJobRowLooksRelevant`, `activeJobsSummaryLines`, `activeProcessLogLines`, `activeWorkEvidenceLines`, `activeWorkLogLines`, `applyPanelPosition`, `boundedLogLine`, `byId`, `clampPanelPosition`, `clearCustomPosition`, `closeFloatingPipelineLog`, `closeReadinessIndicatesActiveWork`, `closeReadinessLine`, `compactRepeatedProgressLines`, `displayMode`, `flushPending`, `hasActiveWorkEvidence`, `initFloatingPipelineLogDragEvents`, `initFloatingPipelineLogEvents`, `isCompactLayout`, `isInteractiveDragTarget`, `isNearBottom`, `isPlainObject`, `keepPanelInsideViewport`, `localTimestamp`, `logTextLines`, `movePanelDrag`, `openFloatingPipelineLog`, `panelNode`, `pipelineLogDisplayText`, `progressCompactionKey`, `readCloseReadiness`, `readRawPipelineLogTail`, `refreshFloatingPipelineLog`
**In-repo imports:** `window.addEventListener`, `window.clearInterval`, `window.innerHeight`, `window.innerWidth`, `window.matchMedia`, `window.mediaPipelineApi`, `window.mediaPipelineFloatingPipelineLog`, `window.requestAnimationFrame`, `window.setInterval`
**HTTP routes:** `/api/backend/close-readiness`, `/api/diagnostics`, `/api/diagnostics/tail?target=pipeline_log&max_bytes=262144`
**DOM selectors:** `.floating-pipeline-log-header`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths apps/desktop/webview/static/assets/floatingPipelineLog.js`._
