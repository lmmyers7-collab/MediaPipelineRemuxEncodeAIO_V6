---
file: apps/desktop/webview/static/assets/settingsView.js
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: JavaScript
pipeline_stage: n/a
token_priority: medium
owner_domain: webview
last_modified: 2026-07-11
last_reviewed: 2026-06-04
sha256: 9deed8a12cb9aea9791616c54e804674f5e41f4106af904f21d31ad49624f854
---
# `apps/desktop/webview/static/assets/settingsView.js`

**Purpose:** JavaScript implementation for settings view; exposes getLastSettings, maybeShowSettingsRuntimeRestartNotice, readSettingsBuilderFloat.

**Public symbols:** `getLastSettings`, `maybeShowSettingsRuntimeRestartNotice`, `readSettingsBuilderFloat`, `readSettingsBuilderNumber`, `rejectSettingsCommandWhileBusy`, `renderSettingsActiveMediaPolicyHandoff`, `renderSettingsMediaPolicyCrossCheck`, `renderSettingsPatchSummary`, `reportSettingsPostSaveRefreshFailure`, `scheduleSettingsPostSaveRefresh`, `setSettingsBuilderControl`, `setSettingsCommandBusy`, `settingsBoolValue`, `settingsBuilderConfigValue`, `settingsBuilderCoveredKeys`, `settingsBuilderInputValue`, `settingsImpactGroupForKey`, `settingsPatchLocalValidationHintLines`, `settingsPatchLocalValidationHints`, `settingsPatchReviewCall`, `settingsPostErrorMessage`, `settingsResultStatusLabel`, `settingsRuntimeRestartConfirmationLine`, `settingsRuntimeRestartNoticeLines`, `settingsRuntimeRestartWarningNeeded`, `settingsRuntimeState`, `syncSettingsRenameLogCaseButton`, `writeSettingsPatchJson`
**In-repo imports:** `window.__settingsBuilderControlsModule`, `window.__settingsMetadataFieldsModule`, `window.__settingsRawTriageModule`, `window.__settingsSafetyLocksModule`, `window.__settingsViewAudioBuilderModule`, `window.__settingsViewFacade`, `window.__settingsViewFileSafetyBuilderModule`, `window.__settingsViewNetworkBuilderModule`, `window.__settingsViewPendingPublishBuilderModule`, `window.__settingsViewQualityBuilderModule`, `window.__settingsViewQueueBuilderModule`, `window.__settingsViewRuntimeBuilderModule`, `window.__settingsViewSubtitleBuilderModule`, `window.__settingsViewVideoBuilderModule`, `window.alert`, `window.appendCells`, `window.appendCommandResult`, `window.applyAudioSettingsBuilderToPatch`, `window.applyFileSafetySettingsBuilderToPatch`, `window.applyNetworkSettingsBuilderToPatch`, `window.applyPendingPublishSettingsBuilderToPatch`, `window.applyQualityDetailSettingsBuilderToPatch`, `window.applyQueueSettingsBuilderToPatch`, `window.applyRuntimeSettingsBuilderToPatch`, `window.applySettingsFieldMetadataToControls`, `window.applySubtitleSettingsBuilderToPatch`, `window.applyVideoDetailSettingsBuilderToPatch`, `window.audioSettingsBuilderFields`, `window.audioSettingsBuilderState`, `window.byId`, `window.clearRows`, `window.fileSafetySettingsBuilderFields`, `window.fileSafetySettingsBuilderState`, `window.finalLibraryPromotionSettingsBuilderFields`, `window.finalLibraryPromotionSettingsBuilderState`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths apps/desktop/webview/static/assets/settingsView.js`._
