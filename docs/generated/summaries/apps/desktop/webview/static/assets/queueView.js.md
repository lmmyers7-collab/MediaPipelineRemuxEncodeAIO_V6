---
file: apps/desktop/webview/static/assets/queueView.js
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: JavaScript
pipeline_stage: orchestration
token_priority: medium
owner_domain: webview
last_modified: 2026-07-15
last_reviewed: 2026-06-04
sha256: 0436013214c1bbd3d5a88eac9d410c18c3ebdcc504102c0d32b61ab365d2c5f6
---
# `apps/desktop/webview/static/assets/queueView.js`

**Purpose:** JavaScript implementation for queue view; exposes diagnosticsBridgeApi, queueSourceTileTitle, queueTableElement.

**Public symbols:** `diagnosticsBridgeApi`, `queueSourceTileTitle`, `queueTableElement`, `queueTableWrap`, `renderQueue`, `renderQueueLoadingTable`, `renderQueueScanLoadingState`, `requestQueueDiagnosticsAction`, `scheduleQueueScanPoll`, `setQueueLoadingScreenVisible`
**In-repo imports:** `window.__queueControlsModule`, `window.__queueDecisionModule`, `window.__queueDetailModule`, `window.__queueLaunchModule`, `window.__queueOpenActionsModule`, `window.__queueRerunModule`, `window.__queueReviewModule`, `window.__queueScanModule`, `window.__queueSelectionModule`, `window.__queueSetFileDrawer`, `window.__queueSourceModelModule`, `window.__queueSourceRenderModule`, `window.__queueStatusPanelsModule`, `window.__queueSummaryModule`, `window.__queueTableModule`, `window.__queueTableViewModule`, `window.__queueTabsModule`, `window.apiGet`, `window.appendCells`, `window.appendCommandResult`, `window.byId`, `window.clearRows`, `window.clearTimeout`, `window.commandHistoryCompactEvidenceLine`, `window.filterRows`, `window.filterRowsByInvestigation`, `window.filterRowsByStatus`, `window.getCommandHistory`, `window.getLastQueuePayload`, `window.getLastQueueRows`, `window.getSelectedQueuePriorityRowKeys`, `window.getSelectedQueuePriorityRows`, `window.getSelectedQueueRow`, `window.isQueueLaunchCommand`, `window.isQueueOpenCommand`
**HTTP routes:** `/api/queue/file-overrides`, `/api/queue/priority`, `/api/queue/strategy`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths apps/desktop/webview/static/assets/queueView.js`._
