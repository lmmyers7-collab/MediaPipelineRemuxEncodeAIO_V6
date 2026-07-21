---
file: apps/desktop/webview/static/assets/runMonitorView.js
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: JavaScript
pipeline_stage: n/a
token_priority: medium
owner_domain: webview
last_modified: 2026-07-19
last_reviewed: 2026-07-16
sha256: 1aa6471e4acce0031f3f80b423e6ad8e972863c4c0dac568f6f2de9175efe1ab
---
# `apps/desktop/webview/static/assets/runMonitorView.js`

**Purpose:** JavaScript implementation for run monitor view; exposes acceptLaunchResult, activeJobIdentity, announce.

**Public symbols:** `acceptLaunchResult`, `activeJobIdentity`, `announce`, `appendEmptyTrackRow`, `appendFact`, `appendRouteCard`, `applyTerminalHandoff`, `array`, `backendQueueCorrelationContext`, `beginTerminalHandoff`, `byId`, `captureDynamicMonitorFocus`, `clearBackendQueueContext`, `clearTerminalHandoff`, `collectionEmptyText`, `collectionStateLabel`, `cssEscape`, `currentClaimsAllowed`, `currentStageLabel`, `displayNameAuthorityLabel`, `displayNameBasis`, `duplicateDisplayNames`, `enforceSingleHomeLiveRegion`, `evidenceLabel`, `focusSelectedFile`, `focusSelectorForPage`, `focusTerminalDestination`, `focusTerminalHeading`, `formatAge`, `formatDurationSeconds`, `formatTimestamp`, `handleItemKeydown`, `humanize`, `init`, `itemEvidenceAllowed`
**In-repo imports:** `window.addEventListener`, `window.apiGet`, `window.clearTimeout`, `window.CSS`, `window.dispatchEvent`, `window.mediaPipelineAppLifecycle`, `window.mediaPipelineCompletedView`, `window.mediaPipelinePendingPublishView`, `window.mediaPipelineReportsView`, `window.mediaPipelineRunMonitor`, `window.MutationObserver`, `window.setTimeout`, `window.showPage`
**HTTP routes:** `/api/run-monitor`
**DOM selectors:** `.run-monitor-item-button`, `summary`
**Exports:** `window.CSS.escape`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths apps/desktop/webview/static/assets/runMonitorView.js`._
