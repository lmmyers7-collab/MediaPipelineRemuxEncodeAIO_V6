---
file: apps/desktop/webview/static/assets/settingsLibraries/interaction.js
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: JavaScript
pipeline_stage: n/a
token_priority: medium
owner_domain: webview
last_modified: 2026-07-15
last_reviewed: 2026-07-11
sha256: 056726662d5ed8df1a0f2a8fe9d53049ec5d3b8cdc49fcb4427013a99a3d1d18
---
# `apps/desktop/webview/static/assets/settingsLibraries/interaction.js`

**Purpose:** JavaScript implementation for interaction; exposes addLibraryCard, applyLibraryCompatibilityPreset, applyLibraryRouteBoundary.

**Public symbols:** `addLibraryCard`, `applyLibraryCompatibilityPreset`, `applyLibraryRouteBoundary`, `buildPatchFromLibraries`, `captureLibraryForcedRowState`, `clearLibraryCompatibilityPreset`, `clearLibraryForcedRowState`, `clearLibraryProfilesPatchJson`, `collectLibraryProfileResetsFromDom`, `collectProfilesFromDom`, `createSettingsLibrariesInteractionModule`, `currentPatchIncludesLibraryProfiles`, `currentSettingsPatchKeys`, `deleteActiveLibrary`, `fieldValue`, `handleSettingsPostSaveRefreshFailure`, `initSettingsLibrariesEvents`, `libraryPatchStateKind`, `libraryProfileResetRequest`, `libraryRouteRow`, `localInheritedFields`, `overrideRowInheritedValue`, `overrideRowValuesEqual`, `presetReasonForKey`, `previewLibraryProfiles`, `profileCardsFromDom`, `profileFromCard`, `readOverrideControlValue`, `renderLibraryPatchHandoff`, `renderLibraryStateStrip`, `renderLibraryWarningSummary`, `replaceActiveLibraryValuesWithDefaults`, `rerenderLibraryCard`, `resetFromSaved`, `resetLibraryRouteBoundary`
**In-repo imports:** `window.__settingsLibrariesInteractionModule`, `window.confirm`, `window.mediaPipelineLibraryRouteMap`, `window.mediaPipelineSettingsView`, `window.updatePagePanelEmptyStates`
**DOM selectors:** `#settings-library-profile-list .settings-library-card`, `[data-library-compatibility-note]`, `[data-library-compatibility-select]`, `[data-library-override-control]`, `[data-library-override-row]`, `[data-library-override-state-label]`, `[data-library-profile-nav]`, `[data-library-route-editor]`, `[data-library-route-rail]`, `[data-library-use-default-override]`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths apps/desktop/webview/static/assets/settingsLibraries/interaction.js`._
