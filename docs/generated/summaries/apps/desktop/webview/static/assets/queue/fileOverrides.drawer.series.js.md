---
file: apps/desktop/webview/static/assets/queue/fileOverrides.drawer.series.js
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: JavaScript
pipeline_stage: orchestration
token_priority: medium
owner_domain: webview
last_modified: 2026-07-16
last_reviewed: 2026-06-05
sha256: 0795c5027e26f503e2c8f9719cd4011898c039bc8eb781f8d98791a05166474b
---
# `apps/desktop/webview/static/assets/queue/fileOverrides.drawer.series.js`

**Purpose:** JavaScript implementation for file overrides drawer series; exposes apiPost, appendCommandResultFn, appendProofChip.

**Public symbols:** `apiPost`, `appendCommandResultFn`, `appendProofChip`, `appendSeriesChip`, `applySeriesClearPreview`, `applySeriesPreview`, `buildOverridePayload`, `buildSeriesProposedOverridePayload`, `closeFileSettingsDrawer`, `closeSeriesModal`, `confirmDiscardDrawerChanges`, `createFileOverridesDrawerSeriesModule`, `fieldPathLabel`, `initFileOverridesDrawerSeriesModule`, `loadFileOverrideEffectiveForPath`, `markDrawerClean`, `openSeriesModal`, `refreshAllFn`, `remuxPilotStatusText`, `renderRemuxPilotPromotionResult`, `renderSeriesPreview`, `renderSeriesRows`, `requestRemuxPilotPromotion`, `requestSeriesClearPreview`, `requestSeriesPreview`, `resetSeriesPreviewState`, `selectedPilotSourcePaths`, `seriesActionLabel`, `seriesActionTone`, `seriesEpisodeText`, `seriesPreviewOperation`, `seriesRowVisible`, `setDrawerCommandButtonsDisabled`, `setSeriesModalMode`, `setSeriesStatus`
**In-repo imports:** `window.__queueFileOverridesDrawerSeriesModule`, `window.apiPost`, `window.appendCommandResult`, `window.getSelectedQueuePriorityRows`, `window.getSelectedQueueRow`, `window.mediaPipelineQueueView`, `window.refreshAll`
**HTTP routes:** `/api/queue/file-overrides/remux-pilot-promote`, `/api/queue/file-overrides/series-apply`, `/api/queue/file-overrides/series-clear-apply`, `/api/queue/file-overrides/series-clear-preview`, `/api/queue/file-overrides/series-preview`
**DOM selectors:** `[data-fo-series-filter]`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths apps/desktop/webview/static/assets/queue/fileOverrides.drawer.series.js`._
