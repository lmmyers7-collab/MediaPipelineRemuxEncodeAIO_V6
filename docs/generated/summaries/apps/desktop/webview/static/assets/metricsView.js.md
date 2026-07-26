---
file: apps/desktop/webview/static/assets/metricsView.js
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: JavaScript
pipeline_stage: n/a
token_priority: medium
owner_domain: webview
last_modified: 2026-07-15
last_reviewed: 2026-06-05
sha256: 5bd0b3a0b81337044ce70b1c8c642c86374f987416ab87db45d625e19691b576
---
# `apps/desktop/webview/static/assets/metricsView.js`

**Purpose:** JavaScript implementation for metrics view; exposes activateMetricsTab, appendMetricsCommandResult, appendSourceActionButton.

**Public symbols:** `activateMetricsTab`, `appendMetricsCommandResult`, `appendSourceActionButton`, `countLabel`, `entriesFromCounts`, `fixedText`, `gbhText`, `gbText`, `initMetricsTabNav`, `initMetricsViewEvents`, `integerText`, `metricsPayloadError`, `metricsTabIds`, `numberValue`, `percentText`, `postMetricsCommand`, `refreshMetricsAfterCommand`, `renderAttentionRows`, `renderCountRows`, `renderCoverageRows`, `renderMetricChart`, `renderMetrics`, `renderMetricsSourceRows`, `renderMetricsUnavailable`, `renderOverview`, `renderProduction`, `renderReasonGroupRows`, `renderRoutes`, `renderRouteSeries`, `renderSourceBackfill`, `renderStorage`, `renderStorageBreakdown`, `renderStorageTopRows`, `renderThroughputRows`, `renderWorkerPosture`
**In-repo imports:** `window.apiPost`, `window.appendCommandResult`, `window.mediaPipelineAppLifecycle`, `window.mediaPipelineMetricsView`, `window.refreshAllNow`
**HTTP routes:** `/api/metrics/backfill`, `/api/metrics/sources`
**DOM selectors:** `.settings-tab-btn[data-metrics-tab]`, `:scope > .metrics-tab-panel[data-metrics-tab-panel]`, `[data-metrics-source-action]`, `h2`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths apps/desktop/webview/static/assets/metricsView.js`._
