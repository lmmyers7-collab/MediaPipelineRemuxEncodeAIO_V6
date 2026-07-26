---
file: apps/desktop/webview/static/assets/queue/fileOverrides.drawer.api.js
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: JavaScript
pipeline_stage: orchestration
token_priority: medium
owner_domain: webview
last_modified: 2026-07-16
last_reviewed: 2026-06-05
sha256: 22a91e7a668a85ad01f72d131a241dfebd2e041d0780f08cffbc1c689f925575
---
# `apps/desktop/webview/static/assets/queue/fileOverrides.drawer.api.js`

**Purpose:** JavaScript implementation for file overrides drawer api; exposes apiGet, apiPost, appendCommandResultFn.

**Public symbols:** `apiGet`, `apiPost`, `appendCommandResultFn`, `applyDisplayedQueueFileOverrideMarker`, `applyFileOverrideEffectivePayload`, `buildOverridePayload`, `clearDrawerForm`, `clearDrawerTrackMetadata`, `clearFileOverrideField`, `clearFileOverrideForPath`, `collectFileOverrideFieldsToClearOnSave`, `confirmDiscardDrawerChanges`, `confirmSubtitleBurnBeforeSave`, `createFileOverridesDrawerApiModule`, `drawerRequestIsCurrent`, `effectivePayloadHasFileOverride`, `ensureRoutePreviewAllowsSave`, `fieldPathsIncludeRouteVideo`, `initFileOverridesDrawerApiModule`, `loadFileOverrideEffectiveForPath`, `loadFileOverrideForPath`, `loadFileOverrideTracksForPath`, `loadRoutePreviewForPayload`, `markDrawerClean`, `payloadHasRouteVideoOverride`, `populateDrawerForm`, `refreshAllFn`, `refreshRoutePreviewFromCurrentForm`, `renderDrawerTrackMetadata`, `resetExactTrackActionsForField`, `saveFileOverrideForPath`, `setDrawerCommandButtonsDisabled`, `showDrawerTrackMetadataLoadingState`, `trackMetadataFromTracksPayload`, `validateExactTrackSelectionsBeforeSave`
**In-repo imports:** `window.__queueFileOverridesDrawerApiModule`, `window.apiGet`, `window.apiPost`, `window.appendCommandResult`, `window.confirm`, `window.mediaPipelineQueueView`, `window.refreshAll`
**HTTP routes:** `/api/queue/file-overrides`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths apps/desktop/webview/static/assets/queue/fileOverrides.drawer.api.js`._
