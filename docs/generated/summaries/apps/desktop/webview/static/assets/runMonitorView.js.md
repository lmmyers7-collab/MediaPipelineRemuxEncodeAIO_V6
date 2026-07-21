---
file: apps/desktop/webview/static/assets/runMonitorView.js
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: JavaScript
pipeline_stage: n/a
token_priority: medium
owner_domain: webview
last_modified: 2026-07-21
last_reviewed: 2026-07-16
sha256: e3157ae054b387c486e7d21d99ca0913f0806764f9e688b72014c6b92a847b87
---
# `apps/desktop/webview/static/assets/runMonitorView.js`

**Purpose:** JavaScript implementation for run monitor view; exposes acceptLaunchResult, activeJobIdentity, announce.

**Public symbols:** `acceptLaunchResult`, `activeJobIdentity`, `announce`, `backendQueueCorrelationContext`, `byId`, `clearBackendQueueContext`, `enforceSingleHomeLiveRegion`, `init`, `meaningfulAnnouncement`, `observeHomeLiveRegions`, `refresh`, `render`, `renderCompactItems`, `renderDetail`, `renderItems`, `renderLastKnown`, `renderOutput`, `renderStopAfterCurrentControl`, `renderSummary`, `renderWorkers`, `setFreshness`, `setStopCommandBusy`, `setText`, `updateWorkloadDisclosure`, `updateWorkloadNameHelp`, `workerRenderSignature`, `workloadRenderSignature`
**In-repo imports:** `window.__runMonitorFormatters`, `window.__runMonitorInteractionModule`, `window.__runMonitorNormalizationModule`, `window.__runMonitorRenderingModule`, `window.addEventListener`, `window.apiGet`, `window.dispatchEvent`, `window.mediaPipelineAppLifecycle`, `window.mediaPipelineRunMonitor`, `window.setTimeout`, `window.showPage`
**HTTP routes:** `/api/run-monitor`
**DOM selectors:** `summary`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths apps/desktop/webview/static/assets/runMonitorView.js`._
