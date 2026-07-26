---
file: apps/desktop/webview/static/assets/app/lifecycle/topbar.js
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: JavaScript
pipeline_stage: n/a
token_priority: medium
owner_domain: webview
last_modified: 2026-07-26
last_reviewed: 2026-07-11
sha256: 6e949210509e6ef6ac23a5b07674c90982da3b452fe64a19ccbe8bd3bcc0e39e
---
# `apps/desktop/webview/static/assets/app/lifecycle/topbar.js`

**Purpose:** JavaScript implementation for topbar; exposes backendLifecycleState, clearTopbarPendingLaunch, closeReadinessWatcherData.

**Public symbols:** `backendLifecycleState`, `clearTopbarPendingLaunch`, `closeReadinessWatcherData`, `closeReadinessWatcherIsArmed`, `closeReadinessWatcherSummary`, `createAppLifecycleTopbar`, `formatCloseReadiness`, `normalizeTauriBackendLifecycleEvent`, `pipelineControlReadinessLines`, `pipelineControlReadinessStatus`, `renderControlReadiness`, `renderTauriBackendLifecycleAlert`, `renderTopbarActivity`, `renderTopbarEventTicker`, `replaceTopbarActivityContent`, `setTopbarPendingLaunch`, `startupProgressLines`, `tauriBackendLifecycleLines`, `tauriBackendLifecycleStatusLabel`, `topbarActiveWorkerNames`, `topbarBackendQueueMonitorContext`, `topbarBackendQueueMonitorText`, `topbarBackendQueueRun`, `topbarCleanCurrentName`, `topbarCurrentWorkers`, `topbarCurrentWorkMeta`, `topbarEventData`, `topbarEventDisplayName`, `topbarEventKey`, `topbarEventTickerLine`, `topbarEventTimestampMs`, `topbarFirstText`, `topbarLatestEvent`, `topbarMonitorIsTerminal`, `topbarObject`
**In-repo imports:** `window.__appLifecycleTopbarModule`, `window.mediaPipelineFormatters`, `window.mediaPipelineLaunchView`, `window.mediaPipelineRunMonitor`, `window.mediaPipelineScheduleView`
**HTTP routes:** `/api/pipeline/control`, `/api/pipeline/control.`
**DOM selectors:** `.tauri-lifecycle-alert`, `.topbar`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths apps/desktop/webview/static/assets/app/lifecycle/topbar.js`._
