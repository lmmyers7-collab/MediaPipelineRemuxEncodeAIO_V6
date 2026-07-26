---
file: apps/desktop/webview/static/assets/runMonitorView.js
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: JavaScript
pipeline_stage: n/a
token_priority: medium
owner_domain: webview
last_modified: 2026-07-26
last_reviewed: 2026-07-16
sha256: 876b5583cb5407fb426787ba94cddbff6a2b60a25aabdfd0ae88042019da1f3e
---
# `apps/desktop/webview/static/assets/runMonitorView.js`

**Purpose:** JavaScript implementation for run monitor view; exposes acceptLaunchResult, activeJobIdentity, announce.

**Public symbols:** `acceptLaunchResult`, `activeJobIdentity`, `announce`, `backendQueueCorrelationContext`, `byId`, `clearBackendQueueContext`, `enforceSingleHomeLiveRegion`, `init`, `meaningfulAnnouncement`, `observeHomeLiveRegions`, `refresh`, `render`, `renderCompactItems`, `renderDetail`, `renderItems`, `renderLastKnown`, `renderOutput`, `renderOutputFacts`, `renderStopAfterCurrentControl`, `renderSummary`, `renderSuppressedOutput`, `renderWorkers`, `setFreshness`, `setStopCommandBusy`, `setText`, `updateWorkloadDisclosure`, `updateWorkloadNameHelp`, `workerRenderSignature`, `workloadRenderSignature`
**In-repo imports:** `window.__runMonitorFormatters`, `window.__runMonitorInteractionModule`, `window.__runMonitorNormalizationModule`, `window.__runMonitorRenderingModule`, `window.addEventListener`, `window.apiGet`, `window.dispatchEvent`, `window.mediaPipelineAppLifecycle`, `window.mediaPipelineRunMonitor`, `window.setTimeout`, `window.showPage`
**HTTP routes:** `/api/run-monitor`
**DOM selectors:** `summary`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths apps/desktop/webview/static/assets/runMonitorView.js`._
