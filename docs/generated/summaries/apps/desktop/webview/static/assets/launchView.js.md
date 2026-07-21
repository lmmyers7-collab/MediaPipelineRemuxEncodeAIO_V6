---
file: apps/desktop/webview/static/assets/launchView.js
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: JavaScript
pipeline_stage: n/a
token_priority: medium
owner_domain: webview
last_modified: 2026-07-11
last_reviewed: 2026-06-04
sha256: ac20c43007fda3bb5c5cb40da1f5eda00a600759ba65d5467876483216e30555
---
# `apps/desktop/webview/static/assets/launchView.js`

**Purpose:** JavaScript implementation for launch view; exposes activateLaunchTab, initLaunchTabNav, launchTabIds.

**Public symbols:** `activateLaunchTab`, `initLaunchTabNav`, `launchTabIds`, `pipelineControlHistoryEntries`, `queueRerunRouteDispatcher`, `renderLaunchLatestCommandEvidence`, `renderPipelineControlJournal`, `renderPipelineControlLatest`, `renderRerunQueuePreflight`, `rerunExecutionTarget`, `rerunExecutionTargetLabel`, `rerunIsNetworkMode`, `rerunPreviewRouteName`, `rerunStartRouteName`
**In-repo imports:** `window.__launchCommandButtonsModule`, `window.__launchCommandOrchestrationModule`, `window.__launchControllerStateModule`, `window.__launchRerunFacade`, `window.__launchScopeControlsModule`, `window.__launchStartRequestModule`, `window.__launchStatusRenderModule`, `window.__launchViewPreflightModule`, `window.__launchViewRealMediaModule`, `window.__launchViewRiskModule`, `window.__launchViewScopeModule`, `window.__queueRerunRequestModule`, `window.appendCells`, `window.appendCommandResult`, `window.byId`, `window.clearRows`, `window.commandHistoryCompactEvidenceLine`, `window.commandResultDisplayMessage`, `window.Event`, `window.formatSettingsChoiceLabel`, `window.getCommandHistory`, `window.getLastLaunchReadinessPayload`, `window.getLastQueuePayload`, `window.getLastQueueRows`, `window.getLastSnapshot`, `window.getSelectedQueueRow`, `window.launchCommandCorrelationRows`, `window.launchCommandCorrelationStatus`, `window.launchCommandDiagnosticsActions`, `window.launchCommandReviewRows`, `window.launchCommandReviewStatus`, `window.launchCommandReviewSummaryLines`, `window.launchReadinessLines`, `window.launchReadinessStatus`, `window.launchTimingStatus`
**HTTP routes:** `/api/rerun/network-preview`, `/api/rerun/network/start`, `/api/rerun/preview`, `/api/rerun/start`
**DOM selectors:** `.settings-tab-btn[data-launch-tab]`, `:scope > .launch-tab-panel[data-launch-tab-panel]`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths apps/desktop/webview/static/assets/launchView.js`._
