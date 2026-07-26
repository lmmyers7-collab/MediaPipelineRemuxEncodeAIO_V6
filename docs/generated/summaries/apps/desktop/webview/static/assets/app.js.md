---
file: apps/desktop/webview/static/assets/app.js
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: JavaScript
pipeline_stage: n/a
token_priority: medium
owner_domain: webview
last_modified: 2026-07-12
last_reviewed: 2026-06-04
sha256: 2c1311971a9d9cb1c8d1006a8ac631f72a58a89a9234c1ca3224ec367b49d3f3
---
# `apps/desktop/webview/static/assets/app.js`

**Purpose:** JavaScript implementation for app; exposes _layoutRenderDrawer, _movePanelByStep, activeKeyboardPage.

**Public symbols:** `_layoutRenderDrawer`, `_movePanelByStep`, `activeKeyboardPage`, `activeKeyboardPanel`, `activePageSelectableRows`, `appendBackendShutdownResult`, `applyAdvancedModePreference`, `applyDefaultActionTooltips`, `applyEvidenceHiddenPreference`, `applySharedUiPreferenceRuntimeState`, `applyStoredLayoutPreferences`, `applyThemePreference`, `attachRefreshMetadata`, `backendLifecycleCommandEntries`, `backendLifecycleCommandLine`, `backendLifecycleState`, `backendShutdownStatusMessage`, `clearActivePageFilters`, `clearTopbarPendingLaunch`, `closeReadinessRequiresWarning`, `closeReadinessWarningMessage`, `closeReadinessWatcherData`, `closeReadinessWatcherIsArmed`, `closeReadinessWatcherSummary`, `csvRerunActivityEvidence`, `csvRerunHomeIsActive`, `csvRerunTailEvidence`, `currentUiPreferenceSurface`, `dailyDriverRows`, `dailyDriverStatusClass`, `dailyDriverSummaryLines`, `dependencyStatusLabel`, `dispatchShortcutInputChange`, `externalDependencyEvidenceText`, `externalDependencyOverallStatus`
**In-repo imports:** `window.__appUiPreferencesModule`, `window.clearTopbarPendingLaunch`, `window.commandHistoryCompactEvidenceLine`, `window.confirm`, `window.externalDependencyEvidenceText`, `window.externalDependencyOverallStatus`, `window.externalDependencyRows`, `window.externalDependencySummaryLines`, `window.getLastSnapshot`, `window.localStorage`, `window.MEDIA_PIPELINE_BOOTSTRAP`, `window.mediaPipelineAppCloseReadiness`, `window.mediaPipelineAppHomeReadiness`, `window.mediaPipelineAppLayoutManager`, `window.mediaPipelineAppLifecycle`, `window.mediaPipelineAppRefresh`, `window.mediaPipelineAppRowOpenActions`, `window.mediaPipelineAppTauriLifecycle`, `window.mediaPipelineAppTopbar`, `window.mediaPipelineCommandHistory`, `window.mediaPipelineLaunchReadinessView`, `window.mediaPipelineLaunchView`, `window.mediaPipelineProgressView`, `window.mediaPipelineSettingsView`, `window.mediaPipelineTelemetryView`, `window.refreshAll`, `window.refreshAllNow`, `window.renderExternalDependencyDigest`, `window.setTopbarPendingLaunch`, `window.showPage`
**HTTP routes:** `/api/backend/shutdown`, `/api/ui-preferences`
**DOM selectors:** `.diagnostic-callout-advanced[data-advanced]`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths apps/desktop/webview/static/assets/app.js`._
