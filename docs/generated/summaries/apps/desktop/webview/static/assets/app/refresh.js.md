---
file: apps/desktop/webview/static/assets/app/refresh.js
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: JavaScript
pipeline_stage: n/a
token_priority: medium
owner_domain: webview
last_modified: 2026-06-26
last_reviewed: 2026-06-04
sha256: b7fa7eb640126686fa4d03de7b04dee37787b03aa32e0d3afe42b60ae1030605
---
# `apps/desktop/webview/static/assets/app/refresh.js`

**Purpose:** JavaScript implementation for refresh; exposes appendCompletedRefreshFailureMetric, attachRefreshMetadata, initPageRefreshButtons.

**Public symbols:** `appendCompletedRefreshFailureMetric`, `attachRefreshMetadata`, `initPageRefreshButtons`, `pageRefreshBusyLabel`, `queueRefreshButton`, `refreshButtons`, `refreshCurrentOutputStatus`, `refreshFailure`, `refreshTimeLabel`, `renderCurrentOutputRefreshFailure`, `renderQueueRefreshInProgress`, `renderRefreshHealth`, `renderRefreshInProgress`, `setQueueRefreshButtonBusy`
**In-repo imports:** `window.mediaPipelineAppHome`, `window.mediaPipelineAppRefresh`, `window.mediaPipelineCompletedView`, `window.mediaPipelineDom`, `window.mediaPipelineQueueView`
**HTTP routes:** `/api/completed?limit=500&force_refresh=true&proof=bounded`, `/api/final-library-promotion/status`
**DOM selectors:** `[data-page-refresh-button]`, `[data-queue-refresh-button]`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths apps/desktop/webview/static/assets/app/refresh.js`._
