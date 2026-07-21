---
file: apps/desktop/webview/static/assets/app/lifecycle/topbar.js
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: JavaScript
pipeline_stage: n/a
token_priority: medium
owner_domain: webview
last_modified: 2026-07-17
last_reviewed: 2026-07-11
sha256: 192111372becf5c0ee64f60132d9f35cb9069e734343c089582c810654f973b4
---
# `apps/desktop/webview/static/assets/app/lifecycle/topbar.js`

**Purpose:** JavaScript implementation for topbar; exposes backendLifecycleState, clearTopbarPendingLaunch, closeReadinessWatcherData.

**Public symbols:** `backendLifecycleState`, `clearTopbarPendingLaunch`, `closeReadinessWatcherData`, `closeReadinessWatcherIsArmed`, `closeReadinessWatcherSummary`, `createAppLifecycleTopbar`, `formatCloseReadiness`, `normalizeTauriBackendLifecycleEvent`, `pipelineControlReadinessLines`, `pipelineControlReadinessStatus`, `renderControlReadiness`, `renderTauriBackendLifecycleAlert`, `renderTopbarActivity`, `renderTopbarEventTicker`, `setTopbarPendingLaunch`, `startupProgressLines`, `tauriBackendLifecycleLines`, `tauriBackendLifecycleStatusLabel`, `topbarBackendQueueMonitorContext`, `topbarBackendQueueMonitorText`, `topbarCleanCurrentName`, `topbarCurrentWorkMeta`, `topbarEventData`, `topbarEventDisplayName`, `topbarEventKey`, `topbarEventTickerLine`, `topbarEventTimestampMs`, `topbarLatestEvent`, `topbarPathLeaf`, `topbarPendingLaunchIsValid`, `topbarPendingLaunchLine`, `topbarPipelineState`, `topbarSnapshotDeclaresBackendQueueRun`, `topbarSnapshotIsFreshlyActive`, `topbarSnapshotProvesDifferentWorkflow`
**In-repo imports:** `window.__appLifecycleTopbarModule`, `window.mediaPipelineFormatters`, `window.mediaPipelineLaunchView`, `window.mediaPipelineRunMonitor`, `window.mediaPipelineScheduleView`
**HTTP routes:** `/api/pipeline/control`, `/api/pipeline/control.`
**DOM selectors:** `.tauri-lifecycle-alert`, `.topbar`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths apps/desktop/webview/static/assets/app/lifecycle/topbar.js`._
