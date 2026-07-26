---
file: apps/desktop/webview/static/assets/settings/view/builder.js
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: JavaScript
pipeline_stage: n/a
token_priority: medium
owner_domain: webview
last_modified: 2026-07-12
last_reviewed: 2026-07-11
sha256: eb826f1ed05dde107f9786b1021f4c9671d2dd7aa63246cf4e98b8cd30858983
---
# `apps/desktop/webview/static/assets/settings/view/builder.js`

**Purpose:** JavaScript implementation for builder; exposes addFinalLibraryPromotionRule, applySettingsBuilderToPatch, blockStaleLibraryProfilesPatch.

**Public symbols:** `addFinalLibraryPromotionRule`, `applySettingsBuilderToPatch`, `blockStaleLibraryProfilesPatch`, `browseFinalLibraryPromotionRulePath`, `collectFinalLibraryPromotionSettingsPatch`, `collectSettingsBuilderPatch`, `createSettingsViewBuilderModule`, `ensureSettingsSaveReviewDialogGlobal`, `finalLibraryPromotionBrowseDetailLines`, `finalLibraryPromotionSettingsResultLines`, `markFinalLibraryPromotionSettingsBuilderDirty`, `markSettingsBuilderDirty`, `markSettingsPatchTouched`, `parseSettingsPatchJson`, `previewFinalLibraryPromotionSettings`, `readSettingsBuilderFloat`, `readSettingsBuilderNumber`, `renderFinalLibraryPromotionSettingsGuidance`, `renderSettingsActiveMediaPolicyHandoff`, `renderSettingsBackendMediaPolicyReadiness`, `renderSettingsEffectivePolicyTrustForError`, `renderSettingsEffectivePolicyTrustFromEntries`, `renderSettingsMediaPolicyCrossCheck`, `renderSettingsPatchImpactSummaryFromEntries`, `renderSettingsPolicyDeltaForError`, `renderSettingsPolicyDeltaFromEntries`, `saveFinalLibraryPromotionSettings`, `setFinalLibraryPromotionStatus`, `setSettingsBuilderControl`, `settingsActiveMediaPolicyRows`, `settingsActiveMediaPolicyStatus`, `settingsActiveMediaPolicySummaryLines`, `settingsBackendMediaPolicyReadiness`, `settingsBackendMediaPolicyStatus`, `settingsBackendMediaPolicySummaryLines`
**In-repo imports:** `window.__settingsPatchReviewModule`, `window.__settingsViewBuilderModule`, `window.confirm`, `window.mediaPipelineSettingsLibraries`, `window.renderAllLaunchPreflights`
**HTTP routes:** `/api/settings/browse-path`, `/api/settings/preview-patch`, `/api/settings/save-patch`
**DOM selectors:** `[data-settings-modal-host]`, `main.workspace`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths apps/desktop/webview/static/assets/settings/view/builder.js`._
