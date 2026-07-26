---
file: apps/desktop/webview/static/assets/librariesRouteMap.js
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: JavaScript
pipeline_stage: n/a
token_priority: medium
owner_domain: webview
last_modified: 2026-07-26
last_reviewed: 2026-06-07
sha256: 1ff3c37b2aaa17d40969f8ffe651229bf1bfc93722db4be78dff4112a6a52969
---
# `apps/desktop/webview/static/assets/librariesRouteMap.js`

**Purpose:** JavaScript implementation for libraries route map; exposes activeProfile, apiGetLocal, byId.

**Public symbols:** `activeProfile`, `apiGetLocal`, `byId`, `collectEvidenceRows`, `compareValueStateTone`, `emptyRows`, `errorMessage`, `escapeHtml`, `focusAfterRender`, `focusLibraryControl`, `guidedFocusMovedElsewhere`, `initLibraryRouteMapEvents`, `navigationLink`, `profileLabel`, `refreshCompare`, `refreshLibraryRouteMap`, `refreshReadOnlyDetails`, `refreshTrace`, `refreshValidation`, `renderAll`, `renderCompareRows`, `renderDecisionMatrix`, `renderNavigationRows`, `renderNodeEvidence`, `renderOptions`, `renderProfileSelectors`, `renderRouteContext`, `renderRouteGraph`, `renderRouteMap`, `renderTraceRows`, `renderTraceSelector`, `renderValidationRows`, `routeProfiles`, `rowKey`, `selectedTraceQuery`
**In-repo imports:** `window.apiGet`, `window.mediaPipelineLibraryRouteMap`, `window.mediaPipelineSettingsLibraries`, `window.requestAnimationFrame`, `window.setTimeout`, `window.showPage`
**HTTP routes:** `/api/libraries/route-map`, `/api/libraries/route-map/compare?`, `/api/libraries/route-map/trace`, `/api/libraries/route-map/validation?limit=20`
**DOM selectors:** `[data-library-profile-pane]`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths apps/desktop/webview/static/assets/librariesRouteMap.js`._
