# Settings View Refactor Prework Baseline

Change packet: `MP-CHANGE-2026-0626-012`

Scope: troubleshooting-oriented prework only for
`apps/desktop/webview/static/assets/settingsView.js`. No JavaScript, route,
script-tag, config, export, or UI behavior changed in this prework.

## Source Facts

| Fact | Current value |
| --- | --- |
| Parent facade | `apps/desktop/webview/static/assets/settingsView.js` |
| Current size | 2,853 lines |
| Public namespace | `window.mediaPipelineSettingsView` |
| Namespace member count | 167 |
| Flat compatibility exports | 4 |
| Current script tag | `/assets/settingsView.js` |
| Main partial | `apps/desktop/webview/static/partials/page-settings.html` |

Authority boundaries confirmed from the boundary register, config glossary,
raw-key triage docs, command ownership matrix, builder coverage matrix, and
source:

- Backend owns settings validation, preview, save, reload, schema migration,
  PSD1/JSON writes, backups, runtime policy, and network lifecycle policy.
- WebView stages local patches, displays backend evidence, and calls documented
  backend routes only.
- Save flows must preserve `confirm_save: true` and must pass the backend
  `review_confirmation` returned by preview.
- `window.mediaPipelineSettingsView` remains the compatibility facade for any
  future extraction.

## Export Ledgers

### Compatibility exports with known direct callers

These exports are the first compatibility contract to freeze before any
extraction. Source lines refer to the current `settingsView.js` unless a child
line is explicitly listed.

| Export | Current signature | Source line | Known direct callers | Proposed owner | Wrapper requirement | Compatibility status |
| --- | --- | ---: | --- | --- | --- | --- |
| `window.mediaPipelineSettingsView` | object namespace | 2810 | `app/home.js`, `launchView.js`, `networkView.js`, `renameView.js`, `settingsLibraries.js`, multiple WebView/static tests | parent facade | Required | Stable public facade |
| `window.renderSettings` | `renderSettings(settings)` | 1354, flat 2844 | `app.js`, diagnostics/settings launch smokes | parent wrapper over patch-review render | Required | Flat alias must stay |
| `window.getLastSettings` | `getLastSettings()` | 2724, flat 2844 | `app.js`, `commandHistory.js`, `crossPageContextView.settings.js`, `launchView.js`, `renameView.js`, `settingsLibraries.js`, tests | parent state facade | Required | Flat alias must stay |
| `window.initSettingsViewEvents` | `initSettingsViewEvents()` | 2796, flat 2845 | `app.js`, static tests | parent wrapper over patch-review init plus rename events | Required | Flat alias must stay |
| `window.renderSettingsRawActionPlan` | `renderSettingsRawActionPlan()` | child 425, flat 2843 | settings launch smoke, static tests | raw triage child | Required | Flat alias must stay |
| `setSettingsCommandBusy` | `setSettingsCommandBusy(isBusy)` | 163 | `app.js` command orchestration | parent busy-state facade | Required | Namespace export |
| `rejectSettingsCommandWhileBusy` | `rejectSettingsCommandWhileBusy(command, statusId, detailId)` | 214 | `app.js`, `settingsLibraries.js` | parent busy-state facade | Required | Namespace export |
| `previewSettingsPatch` | `previewSettingsPatch()` | 2281 | `networkView.js`, `settingsLibraries.js`, static/browser tests | future `settings/patchCommands.js` only if contract frozen | Required | Namespace export |
| `saveSettingsPatch` | `saveSettingsPatch()` | 2401 | `networkView.js`, `settingsLibraries.js`, rename/browser smokes | future `settings/patchCommands.js` only after strict-save tests | Required | Namespace export |
| `markSettingsPatchTouched` | `markSettingsPatchTouched()` | 696, child 1193 | `settingsLibraries.js`, settings launch smoke | patch-review child | Required | Namespace export |
| `renderSettingsPatchSummary` | `renderSettingsPatchSummary()` | 1317, child 436 | `settingsLibraries.js`, settings launch smoke | patch-review child | Required | Namespace export |
| `syncNetworkSettingsBuilderFromConfig` | `syncNetworkSettingsBuilderFromConfig()` | child 559 | `networkView.js`, builder/network browser smokes | network builder child | Required | Namespace export |
| `markNetworkSettingsBuilderDirty` | `markNetworkSettingsBuilderDirty()` | child 585 | builder flush smoke | network builder child | Required | Namespace export |
| `syncRuntimeSettingsBuilderFromConfig` | `syncRuntimeSettingsBuilderFromConfig()` | child 29 | builder flush smoke | runtime builder child | Required | Namespace export |
| `markRuntimeSettingsBuilderDirty` | `markRuntimeSettingsBuilderDirty()` | child 52 | builder flush smoke | runtime builder child | Required | Namespace export |
| `settingsRuntimeRestartConfirmationLine` | `settingsRuntimeRestartConfirmationLine()` | 126 | `settingsWizard.js`, static tests | parent/runtime notice helper | Required | Namespace export |
| `settingsRuntimeRestartNoticeLines` | `settingsRuntimeRestartNoticeLines(result = null)` | 134 | `settingsWizard.js`, static tests | parent/runtime notice helper | Required | Namespace export |
| `maybeShowSettingsRuntimeRestartNotice` | `maybeShowSettingsRuntimeRestartNotice(result = null)` | 155 | `settingsWizard.js` | parent/runtime notice helper | Required | Namespace export |

### Namespace member ledger by owner group

Full member count is 167. The current namespace exports are intentionally broad
because older child scripts and smoke tests reach through the facade.

| Current owner group | Namespace exports |
| --- | --- |
| Parent overview/raw rows | `configValue`, `buildSettingsOverviewRows`, `renderSettingsOverview`, `setSettingsRows`, `renderSettingsRows` |
| Raw triage child | `settingsBuilderCoveredKeys`, `settingsRawTriageRows`, `settingsRawTriageStatus`, `settingsRawTriageSummaryLines`, `settingsRawTriageDetailLines`, `renderSettingsRawTriage`, `settingsRawActionPlanRows`, `settingsRawActionPlanStatus`, `settingsRawActionPlanSummaryLines`, `settingsRawActionPlanDetailLines`, `renderSettingsRawActionPlan` |
| Safety locks child | `settingsSafetyLockRows`, `settingsSafetyLockStatus`, `settingsSafetyLockSummaryLines`, `renderSettingsSafetyLocks` |
| Parent render/commands | `renderSettings`, `getLastSettings`, `validateCurrentSettings`, `reloadSettingsFromDisk`, `browseSettingsPath`, `settingsBrowsePathDetailLines`, `setSettingsCommandBusy`, `rejectSettingsCommandWhileBusy`, `previewSettingsPatch`, `saveSettingsPatch`, `isSettingsCommand`, `settingsCommandHistoryLine`, `renderSettingsCommandHistory` |
| Patch-review child | `settingsPatchLocalValidationHints`, `settingsPatchLocalValidationHintLines`, `renderSettingsPatchSummary`, `settingsPatchSaveReadinessIssues`, `settingsPatchSaveReadinessStatus`, `renderSettingsPatchSaveReadinessFromEntries`, `settingsSaveReviewRows`, `settingsSaveReviewStatus`, `settingsSaveReviewDetailLines`, `renderSettingsSaveReviewFromEntries`, `markSettingsPatchTouched`, `settingsPatchIsTouched`, `settingsPatchEffectiveChangedEntries`, `settingsPatchHasUnsavedChanges`, `settingsStableJsonValue`, `settingsPatchSignature`, `settingsCurrentPatchSignature`, `syncSettingsBuilderFromConfig`, `collectSettingsBuilderPatch`, `applySettingsBuilderToPatch`, `refreshSettingsBuilderChoices`, `renderSettingsBuilderGuidance`, `markSettingsBuilderDirty`, `syncFinalLibraryPromotionSettingsBuilderFromConfig`, `collectFinalLibraryPromotionSettingsPatch`, `previewFinalLibraryPromotionSettings`, `saveFinalLibraryPromotionSettings`, `renderFinalLibraryPromotionSettingsGuidance`, `markFinalLibraryPromotionSettingsBuilderDirty`, `writeSettingsPatchJson`, `parseSettingsPatchJson`, `initSettingsViewEvents` |
| Policy-impact child | `settingsPatchImpactEntries`, `renderSettingsPatchImpactSummaryFromEntries`, `settingsPolicyDeltaRows`, `settingsPolicyDeltaStatus`, `settingsPolicyDeltaSummaryLines`, `renderSettingsPolicyDeltaFromEntries`, `settingsEffectivePolicyRows`, `settingsEffectivePolicyTrustStatus`, `settingsEffectivePolicySummaryLines`, `settingsEffectivePolicyDetailLines`, `renderSettingsEffectivePolicyTrustFromEntries`, `renderSettingsEffectivePolicyTrustForError`, `settingsLaunchImpactRows`, `settingsLaunchImpactStatus`, `settingsLaunchImpactSummaryLines`, `renderSettingsLaunchImpactHandoffFromEntries`, `settingsMediaPolicyRows`, `settingsMediaPolicyStatus`, `settingsMediaPolicySummaryLines`, `renderSettingsMediaPolicyCrossCheck`, `settingsBackendPolicyImpact`, `settingsBackendMediaPolicyReadiness`, `settingsBackendMediaPolicyStatus`, `settingsBackendMediaPolicySummaryLines`, `renderSettingsBackendMediaPolicyReadiness`, `settingsActiveMediaPolicyRows`, `settingsActiveMediaPolicyStatus`, `settingsActiveMediaPolicySummaryLines`, `renderSettingsActiveMediaPolicyHandoff` |
| Video builder child | `syncVideoDetailSettingsBuilderFromConfig`, `collectVideoDetailSettingsBuilderPatch`, `applyVideoDetailSettingsBuilderToPatch`, `renderVideoDetailSettingsBuilderGuidance`, `markVideoDetailSettingsBuilderDirty`, `settingsEncoderCapabilityReport`, `settingsEncoderCapabilityStatus`, `settingsEncoderCapabilitySummaryLines`, `renderSettingsEncoderCapabilityReport` |
| Quality builder child | `syncQualityDetailSettingsBuilderFromConfig`, `collectQualityDetailSettingsBuilderPatch`, `applyQualityDetailSettingsBuilderToPatch`, `renderQualityDetailSettingsBuilderGuidance`, `markQualityDetailSettingsBuilderDirty` |
| File-safety builder child | `syncFileSafetySettingsBuilderFromConfig`, `collectFileSafetySettingsBuilderPatch`, `applyFileSafetySettingsBuilderToPatch`, `renderFileSafetySettingsBuilderGuidance`, `markFileSafetySettingsBuilderDirty` |
| Network builder child | `syncNetworkSettingsBuilderFromConfig`, `collectNetworkSettingsBuilderPatch`, `applyNetworkSettingsBuilderToPatch`, `renderNetworkSettingsBuilderGuidance`, `markNetworkSettingsBuilderDirty` |
| Queue builder child | `syncQueueSettingsBuilderFromConfig`, `collectQueueSettingsBuilderPatch`, `applyQueueSettingsBuilderToPatch`, `renderQueueSettingsBuilderGuidance`, `markQueueSettingsBuilderDirty` |
| Runtime builder child | `syncRuntimeSettingsBuilderFromConfig`, `collectRuntimeSettingsBuilderPatch`, `applyRuntimeSettingsBuilderToPatch`, `renderRuntimeSettingsBuilderGuidance`, `markRuntimeSettingsBuilderDirty` |
| Pending publish builder child | `syncPendingPublishSettingsBuilderFromConfig`, `collectPendingPublishSettingsBuilderPatch`, `applyPendingPublishSettingsBuilderToPatch`, `renderPendingPublishSettingsBuilderGuidance`, `markPendingPublishSettingsBuilderDirty` |
| Subtitle builder child | `syncSubtitleSettingsBuilderFromConfig`, `collectSubtitleSettingsBuilderPatch`, `applySubtitleSettingsBuilderToPatch`, `renderSubtitleSettingsBuilderGuidance`, `settingsBdpgsOcrPathEvidence`, `settingsBdpgsOcrPathEvidenceStatus`, `settingsBdpgsOcrPathEvidenceLines`, `renderSettingsBdpgsOcrPathEvidence`, `settingsVobSubOcrPathEvidence`, `settingsVobSubOcrPathEvidenceStatus`, `settingsVobSubOcrPathEvidenceLines`, `renderSettingsVobSubOcrPathEvidence` |
| Audio builder child | `syncAudioSettingsBuilderFromConfig`, `collectAudioSettingsBuilderPatch`, `applyAudioSettingsBuilderToPatch`, `renderAudioSettingsBuilderGuidance` |
| Backend-result child | `settingsBackendResultRows`, `settingsBackendResultRowKey`, `settingsCommandProgressBars`, `renderSettingsSaveProgress`, `settingsProgressDetailLines`, `settingsBackendResultDetailLines`, `settingsBackendResultStatus`, `settingsBackendResultSummaryLines`, `renderSettingsBackendResultFromEntries`, `renderSettingsBackendResultForError` |
| Runtime/restart and rename bridge | `settingsRuntimeState`, `settingsRuntimeRestartWarningNeeded`, `settingsRuntimeRestartConfirmationLine`, `settingsRuntimeRestartNoticeLines`, `maybeShowSettingsRuntimeRestartNotice`, `settingsRenameLogCasePayload`, `submitSettingsRenameLogCase`, `initSettingsRenameLogCaseEvents` |

## Existing Child Module Ledger

All child scripts must load before `settingsView.js` because the parent reads
and deletes the stash globals while creating child modules.

| Child file | Stash global | Factory | Parent consume line | Injected dependency shape | Exports consumed by parent | Tests that assume child exists |
| --- | --- | --- | ---: | --- | --- | --- |
| `assets/settings/metadataFields.js` | `__settingsMetadataFieldsModule` | `createSettingsMetadataFieldsModule` | 263 | DOM/text helpers, metadata maps | field definition/map helpers used by render and patch review setup | static settings bundle tests |
| `assets/settings/builderControls.js` | `__settingsBuilderControlsModule` | `createSettingsBuilderControlsModule` | 309 | DOM value helpers and dirty markers | shared input/select/checkbox helpers | static settings bundle tests |
| `settingsView.builders.audio.js` | `__settingsViewAudioBuilderModule` | `createAudioSettingsBuilderModule` | 341 | config, patch read/write, DOM helpers | sync/collect/apply/render guidance functions | HandBrake/settings UI static tests |
| `settingsView.builders.video.js` | `__settingsViewVideoBuilderModule` | `createVideoDetailSettingsBuilderModule` | 373 | config, patch read/write, DOM helpers, encoder evidence helpers | sync/collect/apply/render/dirty plus encoder capability report | HandBrake/settings UI static tests |
| `settingsView.builders.quality.js` | `__settingsViewQualityBuilderModule` | `createQualityDetailSettingsBuilderModule` | 407 | config, patch read/write, DOM helpers | sync/collect/apply/render/dirty | static settings bundle tests |
| `settingsView.builders.subtitle.js` | `__settingsViewSubtitleBuilderModule` | `createSubtitleSettingsBuilderModule` | 434 | config, patch read/write, DOM helpers, path evidence helpers | sync/collect/apply/render plus OCR path evidence helpers | HandBrake/settings UI static tests |
| `settingsView.builders.queue.js` | `__settingsViewQueueBuilderModule` | `createQueueSettingsBuilderModule` | 469 | config, patch read/write, DOM helpers | sync/collect/apply/render/dirty | static settings bundle tests |
| `settingsView.builders.runtime.js` | `__settingsViewRuntimeBuilderModule` | `createRuntimeSettingsBuilderModule` | 493 | config, patch read/write, DOM helpers | sync/collect/apply/render/dirty | builder flush smoke |
| `settingsView.builders.file_safety.js` | `__settingsViewFileSafetyBuilderModule` | `createFileSafetySettingsBuilderModule` | 517 | config, patch read/write, DOM helpers, browse staging | sync/collect/apply/render/dirty | static settings bundle tests |
| `settingsView.builders.pending.js` | `__settingsViewPendingPublishBuilderModule` | `createPendingPublishSettingsBuilderModule` | 543 | config, patch read/write, DOM helpers | sync/collect/apply/render/dirty | static settings bundle tests |
| `settingsView.builders.network.js` | `__settingsViewNetworkBuilderModule` | `createNetworkSettingsBuilderModule` | 569 | config, patch read/write, DOM helpers, network setup bridge | sync/collect/apply/render/dirty, `openNetworkRoleSetup` | network browser smoke, builder flush smoke |
| `settingsView.rawTriage.js` | `__settingsRawTriageModule` | `createSettingsRawTriageModule` | 594 | settings rows, known builder keys, HTML/text helpers | raw triage rows/status/detail and raw action-plan rendering | static settings tests, launch smoke |
| `settingsView.safetyLocks.js` | `__settingsSafetyLocksModule` | `createSettingsSafetyLocksModule` | 636 | settings/config helpers | safety lock rows/status/summary/render | static settings tests |
| `assets/settings/patchReview.js` | `__settingsPatchReviewModule` | `createSettingsPatchReviewModule` | 1055 | patch JSON helpers, builder collection, review/evidence render callbacks, raw action plan callback | patch state, patch summary, readiness/save review, builder facade helpers, final-library-promotion helpers, `renderSettings`, event init | patch smoke, live smoke, library/profile/settings tests |
| `assets/settings/policyImpact.js` | `__settingsPolicyImpactModule` | `createSettingsPolicyImpactModule` | 1218 | last settings access, patch/evidence helpers, render callbacks | policy delta, effective policy trust, launch impact, active/backend media policy renderers | HandBrake/settings UI static tests, settings launch smoke |
| `assets/settings/backendResult.js` | `__settingsBackendResultModule` | `createSettingsBackendResultModule` | 1259 | command history, progress, selected row state, DOM helpers | backend preview/save/reload result rows, progress bars, details/errors | static settings tests |
| `assets/settings/routePolicyModel.js` | none consumed by parent | n/a | n/a | standalone route-policy model | consumed by libraries/tests before `settingsLibraries.js`, not by parent | settings libraries tests require load order |

## Settings Route Ledger

| Route or delegated route group | Current WebView caller | Confirmation contract | Ownership boundary |
| --- | --- | --- | --- |
| `GET /api/settings/workspace` | workspace refresh in app layer, then `renderSettings(settings)` | read-only | Backend supplies current config/workspace payload. |
| `POST /api/settings/validate` | `validateCurrentSettings()` line 1377 | none | Backend validates current staged `lastSettingsValues`. |
| `POST /api/settings/preview-patch` | `previewSettingsPatch()` line 2331, `saveSettingsPatch()` line 2475, final-library promotion preview/save lines 851 and 923 | preview returns `review_confirmation` for save | Backend owns merged patch, risk review, review entries, runtime policy evidence. |
| `POST /api/settings/save-patch` | final-library promotion save line 939, main save line 2592 | `{ review_confirmation, confirm_save: true }` required | Backend owns persistence, backups, PSD1/JSON writes, reload evidence, and migration. |
| `POST /api/settings/browse-path` | final-library-promotion browse line 784, generic browse line 2761 | none | Backend owns path validation/trust. WebView only stages returned paths. |
| `POST /api/settings/reload` | `reloadSettingsFromDisk()` line 2686 | none | Backend reloads settings authority and returns evidence. |
| Wizard: `GET /api/settings/wizard/defaults`, `GET /api/settings/wizard/status`, `POST /api/settings/wizard/validate-paths`, `validate-tools`, `probe-hardware`, `validate-workers`, `preview`, `save` | `settingsWizard.js` lines 523, 550, 901, 917, 936, 959, 1012, 1042 | wizard save sends `confirm_save: true` | Wizard routes remain owned by wizard module/backend; parent only supplies runtime-restart notice helpers. |
| Preset library: `GET /api/settings/preset-library`, command routes `validate`, `compare`, `import-preview`, `save`, `export`, `apply-preview`, `apply` | preset library contracts and `settingsLibraries.js` handoffs | save uses `confirm_save`; apply uses `confirm_apply` | Preset library persists preset-library state only; applying to active settings must remain backend-reviewed. |
| `POST /api/settings/pipeline-plan-preview` | route-policy/HandBrake preview surfaces, not `settingsView.js` | preview-only | Backend planner owns route/media policy interpretation. Frontend mutation-boundary tests assert `settingsView.js` does not call it. |
| Delegated rename routes: `/api/rename/cleaning-filters`, `/api/rename/movie-cleaning-filters`, `/api/rename/clean-filename-preview`, `/api/rename/filter-cases`, `/api/rename/browse`, `/api/rename/preview`, `/api/rename/apply`, `/api/rename/undo` | `renameView.js`; Settings uses the rename workbench bridge and settings patch staging | rename apply has its own confirmation contract | Settings must not own rename apply/mutation. Workbench suggestions may stage settings patch only. |
| Delegated network routes: `/api/network/workers` and coordinator/worker lifecycle/setup routes | `networkView.js`; Settings network builder only stages network settings | lifecycle routes have their own dry-run/confirmation contracts | Network backend owns coordinator/worker lifecycle. Settings builder does not start or stop network work. |

## DOM Ledger for `settings-*`

The DOM surface is broad. These are the current settings IDs grouped by
responsibility so future extraction can verify ownership without changing IDs.

| Area | Representative IDs |
| --- | --- |
| General settings/status | `settings-status`, `settings-paths`, `settings-profiles`, `settings-validation`, `settings-validate-button`, `settings-reload-button`, `settings-save-header`, `settings-save-header-patch-status`, `settings-save-header-reload-status`, `settings-save-header-save-button`, `settings-save-header-reload-button`, `settings-overview-status`, `settings-overview-rows`, `settings-command-history-status`, `settings-command-history` |
| Patch summary/save candidate | `settings-patch-json`, `settings-patch-status`, `settings-patch-summary-changed-only`, `settings-patch-impact-summary`, `settings-save-readiness-status`, `settings-save-readiness`, `settings-patch-summary-rows`, `settings-summarize-patch-button`, `settings-save-patch-button`, `settings-patch-summary-status`, `settings-patch-detail`, `settings-save-progress-bars` |
| Backend preview/save/reload evidence | `settings-backend-result-status`, `settings-backend-result-summary`, `settings-backend-result-rows`, `settings-backend-result-legend`, `settings-backend-result-detail` |
| Effective policy and media-policy evidence | `settings-effective-policy-status`, `settings-effective-policy-summary`, `settings-effective-policy-rows`, `settings-effective-policy-legend`, `settings-effective-policy-detail`, `settings-policy-delta-status`, `settings-policy-delta-summary`, `settings-policy-delta-rows`, `settings-media-policy-*`, `settings-backend-media-policy-*`, `settings-active-media-policy-*`, `settings-launch-impact-*`, `settings-handbrake-*` |
| Generic route/size builder | `settings-builder-status`, `settings-builder-routing-profile`, `settings-builder-route-threshold-mode`, `settings-route-height-slider`, `settings-route-boundary-1080p-end-input`, `settings-route-boundary-4k-start-input`, `settings-builder-movie-1080p-target`, `settings-builder-tv-1080p-target`, `settings-builder-size-guard`, `settings-builder-apply-button`, `settings-builder-reset-button`, `settings-builder-guidance` |
| Video/quality/audio/subtitle builders | `settings-video-*`, `settings-encoder-capability-*`, `settings-builder-quality-*`, `settings-quality-*`, `settings-audio-*`, `settings-subtitle-*`, `settings-bdpgs-*`, `settings-vobsub-*` |
| File safety, queue, runtime, pending, network builders | `settings-file-safety-*`, `settings-queue-*`, `settings-runtime-*`, `settings-pending-*`, `settings-network-*`, `settings-final-library-promotion-*` |
| Raw-key plan/safety locks | `settings-raw-triage-*`, `settings-raw-action-plan-*`, `settings-safety-lock-*` |
| Rename workbench | `settings-rename-workbench-status`, `settings-rename-workbench-form`, `settings-rename-workbench-mode`, `settings-rename-workbench-template`, `settings-rename-workbench-source-folder`, `settings-rename-workbench-source-file`, `settings-rename-workbench-*expected*`, `settings-rename-workbench-test-button`, `settings-rename-workbench-save-case-button`, `settings-rename-workbench-stage-suggestions-button`, `settings-rename-workbench-retest-button`, `settings-rename-workbench-output`, `settings-rename-workbench-suggestions` |
| Libraries handoff | `settings-library-*`, `settings-libraries-*`, `settings-library-watch-*` |
| Save review dialog | `settings-save-review-rows`, `settings-save-review-status`, `settings-save-review-detail`, `settings-save-review-legend` |
| Guided setup | `settings-wizard-*`, including readiness strip, step buttons, validation/tool/hardware/worker result IDs, preview/save controls, acknowledgements, and save result |

## Direct Caller Search Results

Search scope:
`apps/desktop/webview/static/assets/`, `tests/webview/`, and
`tests/python/desktop/test_application_facade_web_static_settings.py`.

| Pattern | Direct caller result |
| --- | --- |
| `window.mediaPipelineSettingsView` | `app.js` wires busy-state hooks; `app/home.js` and `launchView.js` read the namespace; `networkView.js` calls `previewSettingsPatch`, `saveSettingsPatch`, `syncNetworkSettingsBuilderFromConfig`; `settingsLibraries.js` calls reject/preview/save/touch/summary helpers; `settingsWizard.js` calls runtime restart helpers; `renameView.js` keeps the namespace reference for settings handoff. |
| Flat exports | `window.renderSettings` is called by `app.js` and browser smokes; `window.getLastSettings` is called by app, command history, launch, rename, cross-page context, libraries, and tests; `initSettingsViewEvents()` is called by `app.js`; `window.renderSettingsRawActionPlan` is asserted by launch/static tests. |
| Child stash globals | Each `window.__settings...Module` global is defined by its child script and consumed/deleted by `settingsView.js`. Static tests assert the stash names, parent consumption, and script order. |
| Strict save strings | `settingsView.js` main and final-library save paths contain `review_confirmation: reviewConfirmation` and `confirm_save: true`; `settingsWizard.js` contains wizard `confirm_save: true`; tests assert these strings. |

## Current Mutable State List

Current state in the parent and injected child graph:

- Last settings payload and metadata:
  `lastSettings`, `lastSettingsValues`, `lastSettingsFieldDefinitions`,
  `lastSettingsFieldMap`.
- Builder initialization and dirty state:
  `settingsBuilderInitialized`, `settingsBuilderDirty`,
  `fileSafetySettingsBuilderState`, `networkSettingsBuilderState`,
  `queueSettingsBuilderState`, `videoDetailSettingsBuilderState`,
  `qualityDetailSettingsBuilderState`, `runtimeSettingsBuilderState`,
  `pendingPublishSettingsBuilderState`,
  `finalLibraryPromotionSettingsBuilderState`,
  `subtitleSettingsBuilderState`, `audioSettingsBuilderState`.
- Patch state and review:
  `settingsPatchTouched`, child patch JSON helpers, child save-review selected
  row state, and pending review confirmation data returned by backend preview.
- Command/busy state:
  `settingsCommandInFlight`, command-history rendering state, progress-bar
  evidence.
- Preview/save/reload results:
  `settingsPatchPreviewRequestId`,
  `lastSettingsPatchPreviewEvidence`, `lastSettingsPatchSaveEvidence`,
  `lastSettingsReloadEvidence`.
- Selected evidence rows:
  `selectedSettingsPatchSaveReadinessKey`,
  `selectedSettingsSaveReviewKey`, `selectedSettingsBackendResultKey`,
  `selectedSettingsEffectivePolicyKey`.
- Raw triage selection:
  raw action-plan selected row and detail state inside the raw triage child.
- Browse/path staging:
  current browse button target, setting key, selected backend path, and staged
  path patch state; backend remains path authority.
- Rename workbench:
  rename log case event-binding/busy state plus suggestion staging state.
- Post-save refresh:
  scheduled refresh handoff through the app/workspace reload path.

Extraction stop rule: staged patch, busy state, preview/save result, builder
dirty state, raw triage selection, and post-save refresh state must each have
one owner at any time.

## Troubleshooting Seams and Rollback Rules

| Candidate seam | Candidate owner | Prework answer | Rollback rule |
| --- | --- | --- | --- |
| Parent facade cleanup | `settingsView.js` | Many namespace exports already delegate to existing child modules. Keep wrappers until callers/tests no longer depend on the facade. | Revert wrapper changes only; keep `window.mediaPipelineSettingsView` and flat aliases unchanged. |
| Patch staging | future `assets/settings/patchState.js` | Valid only for local JSON patch, touched state, signatures, dirty flags, and no backend calls. Must not persist config. | Restore helpers to parent/patch-review child and remove new script tag. |
| Preview/save commands | future `assets/settings/patchCommands.js` | High-risk but bounded: owns calls to preview/save routes and strict confirmations only; backend remains persistence authority. Must keep preview-before-save and matching `review_confirmation`. | Revert command module and script tag; parent `previewSettingsPatch`/`saveSettingsPatch` bodies become authoritative again. |
| Browse path commands | future `assets/settings/pathBrowse.js` | Narrowest route seam. It may call `/api/settings/browse-path` and stage returned values, but cannot trust paths or write config. | Inline browse helper back into parent; no route or payload change. |
| Effective policy trust | future `assets/settings/effectivePolicy.js` or existing `policyImpact.js` | Already mostly delegated to `policyImpact.js`. Any extraction should only render saved-vs-staged/backend evidence, never infer runtime media policy. | Restore delegated wrappers to `policyImpact.js` and parent facade. |
| Backend result rendering | existing `assets/settings/backendResult.js` | Existing owner already formats backend preview/save/reload rows and progress. Parent still stores evidence and routes errors into it. | Revert to parent wrappers; keep child load-before-parent order. |
| Rename workbench bridge | future `assets/settings/renameWorkbenchBridge.js` | Valid only for test/append case handoff and staging backend suggestions into settings patch. Rename apply remains in `renameView.js`. | Move bridge code back into parent; no rename route movement. |
| Network builder bridge | existing network builder | Existing child stages Network settings and opens Network setup handoff. It must not own lifecycle routes. | Revert builder changes; lifecycle remains in `networkView.js` and backend routes. |
| Preset and wizard handoffs | existing `settingsLibraries.js` and `settingsWizard.js` | Keep separate. Parent only exposes settings save/preview and restart-notice helpers. Preset apply/save and wizard save need their own route/confirmation ledgers before movement. | Revert handoff changes in their modules; parent facade remains compatibility point. |

Recommended first extraction phase after this baseline: extract no behavior
initially. First add characterization/static checks that freeze facade counts,
flat aliases, child load order, strict save confirmation strings, and direct
caller compatibility. If behavior extraction proceeds after that, start with
the browse-path seam because it is narrow, backend-authoritative, and has a
simple rollback.

## Validation Required Before Any Extraction

Baseline and extraction validation should include:

```powershell
git status --short
rg -n "mediaPipelineSettingsView|settingsView.js|/api/settings|confirm_save|review_confirmation|__settings" apps tests docs/inventories
.\apps\desktop\runtime\Python\python.exe -m unittest tests.webview.test_webview_settings_patch_smoke -q
.\apps\desktop\runtime\Python\python.exe -m unittest tests.webview.test_webview_settings_live_smoke -q
.\apps\desktop\runtime\Python\python.exe -m unittest tests.webview.test_webview_handbrake_settings_ui -q
.\apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_application_facade_web_static_settings -q
.\apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_facade_settings_patch_policy -q
npm run webview:prework:check
.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py mediapipeline.tools.change_control.validate_changes --require-worktree-coverage
```

Browser-backed smokes may be skipped only for a concrete local browser/runtime
reason, and the skipped reason must be recorded in the change packet.

## Prework Validation Results

Run on 2026-06-26:

| Command | Result |
| --- | --- |
| `git status --short` | Ran; worktree already contained many unrelated dirty files before this prework. |
| `rg -n "mediaPipelineSettingsView|settingsView.js|/api/settings|confirm_save|review_confirmation|__settings" apps tests docs/inventories` | Ran; results are summarized in the export, route, and direct-caller ledgers above. |
| `.\apps\desktop\runtime\Python\python.exe -m unittest tests.webview.test_webview_settings_patch_smoke -q` | Passed, 1 test. |
| `.\apps\desktop\runtime\Python\python.exe -m unittest tests.webview.test_webview_settings_live_smoke -q` | Passed, 1 test. |
| `.\apps\desktop\runtime\Python\python.exe -m unittest tests.webview.test_webview_handbrake_settings_ui -q` | Passed, 43 tests. |
| `.\apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_application_facade_web_static_settings -q` | Passed, 5 tests. |
| `.\apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_facade_settings_patch_policy -q` | Passed, 6 tests. |
| `npm run webview:prework:check` | Failed after `webview:check` passed. `webview:lint:budget:check` reported warning-budget increases: complexity `115 > 108`, max-lines-per-function `46 > 37`, no-extra-boolean-cast `1 > 0`, no-unused-vars `192 > 143`. No JavaScript changed in this prework. |
| `npm run webview:map:check` | Failed: `docs/generated/WEBVIEW_GODFILE_SPLIT_MAP.md` is stale. |
| `npm run webview:contract:check` | Failed: `docs/generated/WEBVIEW_PUBLIC_CONTRACT_BASELINE.json` is stale. |
| `npm run webview:slices:check` | Failed: `docs/generated/WEBVIEW_SPLIT_CANDIDATES.json` is stale. |
| `npm run webview:dom-gaps:check` | Failed: `docs/generated/WEBVIEW_DOM_ID_GAP_REPORT.json` is stale. |
| `npm run webview:routes:check` | Passed: route ownership guard is current. |
| `npm run webview:commands:check` | Failed: `docs/generated/WEBVIEW_COMMAND_BOUNDARY_AUDIT.json` is stale and reports forbidden frontend API findings for direct Tauri bridge access / Tauri invoke. |
| `npm run webview:script-order:smoke` | Passed: loaded 150 WebView scripts and verified expected globals including `mediaPipelineSettingsView`. |
| `.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py mediapipeline.tools.change_control.validate_changes --require-worktree-coverage` | Failed for unrelated existing change-control/worktree coverage issues: `MP-CHANGE-2026-0626-010.json` has invalid status `completed`, and 11 generated files are not listed in any unreleased change packet. |
