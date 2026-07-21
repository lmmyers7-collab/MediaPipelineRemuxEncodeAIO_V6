---
file: apps/desktop/webview/static/assets/settingsWizard.js
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: JavaScript
pipeline_stage: n/a
token_priority: medium
owner_domain: webview
last_modified: 2026-07-11
last_reviewed: 2026-06-04
sha256: 276baa4933b9fe61744000009bc4dc759db386a8920747e7a256a1f5460693dd
---
# `apps/desktop/webview/static/assets/settingsWizard.js`

**Purpose:** JavaScript implementation for settings wizard; exposes activateWizardTab, activeRiskAckMissing, activeRiskAckRules.

**Public symbols:** `activateWizardTab`, `activeRiskAckMissing`, `activeRiskAckRules`, `apiGetLocal`, `apiPostLocal`, `applyWizardDefaults`, `bindDeploymentActionPath`, `boolValue`, `collectDangerAck`, `collectErrorsAndWarnings`, `collectWizardPayload`, `copyDiagnostics`, `detectTools`, `enhanceWizardChoiceSelect`, `footerActionLabel`, `handlePrimaryWizardAction`, `initSettingsWizardEvents`, `initWizardChoiceGroups`, `loadWizardDefaults`, `loadWizardStatus`, `markDirty`, `numberValue`, `openDeploymentLaunchReadiness`, `openWizard`, `parseListText`, `phaseStatuses`, `previewPayload`, `previewStatus`, `previewWizard`, `probeHardware`, `renderSettingsWizardStatus`, `resultStatus`, `runWizardCommand`, `saveWizard`, `setChecked`
**In-repo imports:** `window.__settingsWizardLibraryEditorModule`, `window.__settingsWizardPreviewRenderModule`, `window.apiGet`, `window.apiPost`, `window.appendCells`, `window.appendCommandResult`, `window.byId`, `window.clearRows`, `window.confirm`, `window.mediaPipelineLaunchView`, `window.mediaPipelineSettingsView`, `window.mediaPipelineSettingsWizard`, `window.setText`, `window.showPage`, `window.updatePagePanelEmptyStates`
**HTTP routes:** `/api/settings/wizard/defaults`, `/api/settings/wizard/preview`, `/api/settings/wizard/probe-hardware`, `/api/settings/wizard/save`, `/api/settings/wizard/status`, `/api/settings/wizard/validate-paths`, `/api/settings/wizard/validate-tools`, `/api/settings/wizard/validate-workers`
**DOM selectors:** `#settings-save-header`, `#settings-validate-button`, `.settings-section-nav-btn[data-settings-tab]`, `.settings-tab-pane[data-settings-tab]`, `.settings-wizard-panel input, .settings-wizard-panel select`, `[data-risk-ack-row]`, `[data-wizard-step-button]`, `[data-wizard-step]`, `input`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths apps/desktop/webview/static/assets/settingsWizard.js`._
