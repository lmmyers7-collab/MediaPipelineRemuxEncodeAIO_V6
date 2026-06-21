(function () {
  const settingsOverview = window.mediaPipelineSettingsOverview || {};
  const configValue = window.configValue || settingsOverview.configValue || function () { return "(not set)"; };
  const buildSettingsOverviewRows = window.buildSettingsOverviewRows || settingsOverview.buildSettingsOverviewRows || function () { return []; };
  const renderSettingsOverview = window.renderSettingsOverview || settingsOverview.renderSettingsOverview || function () {};
  const renderSettingsOperatorTrust = window.renderSettingsOperatorTrust || settingsOverview.renderSettingsOperatorTrust || function () {};
  const settingsCommandHistory = window.mediaPipelineSettingsCommandHistory || {};
  const isSettingsCommand = settingsCommandHistory.isSettingsCommand || function () { return false; };
  const settingsCommandHistoryLine = settingsCommandHistory.settingsCommandHistoryLine || function () { return ""; };
  const renderSettingsCommandHistory = settingsCommandHistory.renderSettingsCommandHistory || function () {};
  const domHelpers = window.mediaPipelineDom || {};
  const settingsValuesEqual = window.settingsValuesEqual || function (left, right) {
    return JSON.stringify(left) === JSON.stringify(right);
  };
  const jsonDetailText = domHelpers.jsonDetailText || function (options = {}) {
    const label = options.label || "JSON detail";
    try {
      return `${label}:\n${JSON.stringify(options.value, null, 2)}`;
    } catch (error) {
      return `${label}:\nJSON render error: ${error instanceof Error ? error.message : String(error)}`;
    }
  };

  function settingsBuilderCoveredKeys() {
    return new Set([
      ...settingsBuilderFields,
      ...fileSafetySettingsBuilderFields,
      ...networkSettingsBuilderFields,
      ...queueSettingsBuilderFields,
      ...videoDetailSettingsBuilderFields,
      ...qualityDetailSettingsBuilderFields,
      ...runtimeSettingsBuilderFields,
      ...pendingPublishSettingsBuilderFields,
      ...finalLibraryPromotionSettingsBuilderFields,
      ...subtitleSettingsBuilderFields,
      ...audioSettingsBuilderFields,
    ].map((field) => String(field?.[0] || "")).filter(Boolean));
  }

let lastSettingsValues = {};
let lastSettingsFieldDefinitions = [];
let lastSettingsFieldMap = {};
let settingsBuilderInitialized = false;
let settingsBuilderDirty = false;
const fileSafetySettingsBuilderState = { initialized: false, dirty: false };
const networkSettingsBuilderState = { initialized: false, dirty: false };
const queueSettingsBuilderState = { initialized: false, dirty: false };
const videoDetailSettingsBuilderState = { initialized: false, dirty: false };
const qualityDetailSettingsBuilderState = { initialized: false, dirty: false };
const runtimeSettingsBuilderState = { initialized: false, dirty: false };
const pendingPublishSettingsBuilderState = { initialized: false, dirty: false };
const finalLibraryPromotionSettingsBuilderState = { initialized: false, dirty: false };
const subtitleSettingsBuilderState = { initialized: false, dirty: false };
const audioSettingsBuilderState = { initialized: false, dirty: false };
let lastSettings = null;
let settingsPatchPreviewRequestId = 0;
let selectedSettingsSaveReviewKey = "";
let selectedSettingsBackendResultKey = "";
let selectedSettingsEffectivePolicyKey = "";
let settingsPatchTouched = false;
let lastSettingsPatchPreviewEvidence = null;
let lastSettingsPatchSaveEvidence = null;
let lastSettingsReloadEvidence = null;

const settingsCommandButtonIds = [
  "settings-validate-button",
  "settings-reload-button",
  "settings-save-patch-button",
  "settings-file-safety-source-movies-browse",
  "settings-file-safety-source-tv-browse",
  "settings-file-safety-outsource-browse",
  "settings-file-safety-local-base-browse",
  "network-settings-preview-button",
  "network-settings-save-button",
  "settings-save-header-save-button",
  "settings-save-header-reload-button",
];
let settingsCommandInFlight = false;
let settingsRenameLogCaseInFlight = false;
let settingsRenameLogCaseEventsBound = false;

const settingsRuntimeActiveStates = new Set(["processing", "running", "active", "publishing", "audit", "rerun", "stopping", "paused"]);
const settingsRuntimeInactiveStages = new Set(["", "idle", "sleeping", "stopped", "completed"]);

function settingsRuntimeState() {
  const snapshot = typeof window.getLastSnapshot === "function" ? (window.getLastSnapshot() || {}) : {};
  const progress = snapshot.progress && typeof snapshot.progress === "object" ? snapshot.progress : {};
  const state = String(snapshot.pipeline_state || "").trim().toLowerCase();
  const stage = String(progress.CurrentStage || progress.Status || "").trim().toLowerCase();
  return {
    state: state || "unknown",
    stage,
    active: settingsRuntimeActiveStates.has(state) || !settingsRuntimeInactiveStages.has(stage),
  };
}

function settingsRuntimeRestartWarningNeeded() {
  return settingsRuntimeState().active;
}

function settingsRuntimeRestartConfirmationLine() {
  const runtime = settingsRuntimeState();
  if (runtime.active) {
    return "Runtime note: active pipeline/audit/rerun work keeps the settings it loaded at start. Stop or wait for idle, then start a new run for these changes to affect that work.";
  }
  return "Runtime note: restarting Tauri is not required after a successful reload; future launches use the saved settings.";
}

function settingsRuntimeRestartNoticeLines(result = null) {
  const data = result?.data && typeof result.data === "object" ? result.data : {};
  const runtime = settingsRuntimeState();
  const lines = [
    "Settings runtime note:",
    data.reloaded === true
      ? "Save Settings reports Reloaded: yes; the backend and future launches have the saved config."
      : data.reloaded === false
        ? "Save Settings wrote config, but backend reload did not complete. Use Reload From Disk or restart Tauri after resolving the reload issue."
        : "Saved settings affect future launches after backend reload evidence is available.",
    "Running pipeline/audit/rerun work keeps the settings loaded when it started.",
  ];
  if (runtime.active) {
    lines.push(`Current backend state: ${runtime.state}${runtime.stage ? `; stage: ${runtime.stage}` : ""}. Stop or wait for idle, then start a new run for these settings to affect active work.`);
  } else {
    lines.push("No active backend work is currently shown; the next launch will use the saved settings.");
  }
  lines.push("Restarting the Tauri shell is not required when reload succeeds.");
  return lines;
}

function maybeShowSettingsRuntimeRestartNotice(result = null) {
  if (!result?.ok || typeof window.alert !== "function") return;
  const data = result.data && typeof result.data === "object" ? result.data : {};
  if (data.writes_config !== true || data.reloaded !== true) return;
  if (!settingsRuntimeRestartWarningNeeded()) return;
  window.alert(settingsRuntimeRestartNoticeLines(result).join("\n"));
}

function setSettingsCommandBusy(isBusy) {
  settingsCommandInFlight = Boolean(isBusy);
  settingsCommandButtonIds.forEach((id) => {
    const button = byId(id);
    if (button) button.disabled = settingsCommandInFlight;
  });
  syncSettingsRenameLogCaseButton();
}

function rejectSettingsCommandWhileBusy(command, statusId, detailId) {
  if (!settingsCommandInFlight) return false;
  const result = {
    command,
    ok: false,
    severity: "warning",
    message: "Another settings command is already in progress.",
  };
  appendCommandResult(result);
  setText(statusId, "Busy");
  if (detailId) setText(detailId, result.message);
  return true;
}

function settingsResultStatusLabel(result, okLabel, fallbackLabel) {
  if (result?.ok) return okLabel;
  const severity = String(result?.severity || "").trim().toLowerCase();
  if (severity === "warning") return "Needs review";
  if (severity === "error") return fallbackLabel;
  return result?.severity || fallbackLabel;
}

const settingsMetadata = window.mediaPipelineSettingsMetadata || {};
const settingsBuilderFields = settingsMetadata.settingsBuilderFields || [];
const fileSafetySettingsBuilderFields = settingsMetadata.fileSafetySettingsBuilderFields || [];
const networkSettingsBuilderFields = settingsMetadata.networkSettingsBuilderFields || [];
const queueSettingsBuilderFields = settingsMetadata.queueSettingsBuilderFields || [];
const videoDetailSettingsBuilderFields = settingsMetadata.videoDetailSettingsBuilderFields || [];
const qualityDetailSettingsBuilderFields = settingsMetadata.qualityDetailSettingsBuilderFields || [];
const runtimeSettingsBuilderFields = settingsMetadata.runtimeSettingsBuilderFields || [];
const pendingPublishSettingsBuilderFields = settingsMetadata.pendingPublishSettingsBuilderFields || [];
const finalLibraryPromotionSettingsBuilderFields = settingsMetadata.finalLibraryPromotionSettingsBuilderFields || [];
const subtitleSettingsBuilderFields = settingsMetadata.subtitleSettingsBuilderFields || [];
const audioSettingsBuilderFields = settingsMetadata.audioSettingsBuilderFields || [];
const settingsSafetyLockDefinitions = settingsMetadata.settingsSafetyLockDefinitions || [];
const settingsImpactGroups = settingsMetadata.settingsImpactGroups || [];
const settingsSpecificImpactHints = settingsMetadata.settingsSpecificImpactHints || {};
const settingsChoiceLabels = settingsMetadata.settingsChoiceLabels || {};
const settingsFriendlyPersistedKeyAliases = settingsMetadata.settingsFriendlyPersistedKeyAliases || {};
const settingsAdvancedFallbackKeys = new Set(settingsMetadata.settingsAdvancedFallbackKeys || []);
const settingsPatchComplexBackendKeys = new Set(["LibraryProfiles", "FinalLibraryPromotionRules"]);
let settingsAdvancedToggleEventsBound = false;

const settingsMetadataFieldsModule = window.__settingsMetadataFieldsModule || {};
delete window.__settingsMetadataFieldsModule;
const settingsMetadataFields = typeof settingsMetadataFieldsModule.createSettingsMetadataFieldsModule === "function"
  ? settingsMetadataFieldsModule.createSettingsMetadataFieldsModule({
    getLastSettingsFieldMap: () => lastSettingsFieldMap,
    settingsAdvancedFallbackKeys,
    settingsChoiceLabels,
  })
  : {};
const settingsFieldDefinition = settingsMetadataFields.settingsFieldDefinition || function (key) {
  return lastSettingsFieldMap ? lastSettingsFieldMap[key] || null : null;
};
const settingsFieldDefaultValue = settingsMetadataFields.settingsFieldDefaultValue || function (_key, fallback) { return fallback; };
const formatSettingsChoiceLabel = settingsMetadataFields.formatSettingsChoiceLabel || function (value) { return String(value || ""); };
const settingsFieldAllowedValues = settingsMetadataFields.settingsFieldAllowedValues || function (field) {
  if (Array.isArray(field?.allowed_values) && field.allowed_values.length) return field.allowed_values;
  if (Array.isArray(field?.choices) && field.choices.length) return field.choices;
  return [];
};
const settingsHasBackendFieldDefinitions = settingsMetadataFields.settingsHasBackendFieldDefinitions || function () {
  return Boolean(lastSettingsFieldMap && Object.keys(lastSettingsFieldMap).length);
};
const settingsFieldLabel = settingsMetadataFields.settingsFieldLabel || function (key, fallback = "") { return fallback || key; };
const settingsPersistedKeyDisplayList = settingsMetadataFields.settingsPersistedKeyDisplayList || function (keys) {
  return (Array.isArray(keys) ? keys : []).map((key) => String(key || "")).filter(Boolean).join(", ");
};
const settingsFieldHelpText = settingsMetadataFields.settingsFieldHelpText || function (field) {
  return String(field?.help_text || field?.help || "").trim();
};
const settingsFieldIsAdvanced = settingsMetadataFields.settingsFieldIsAdvanced || function () { return false; };
const settingsMetadataValue = settingsMetadataFields.settingsMetadataValue || function (value) { return String(value ?? ""); };

function settingsBuilderConfigValue(key, fallback) {
  const value = lastSettingsValues ? lastSettingsValues[key] : undefined;
  if (value === undefined || value === null || value === "") return settingsFieldDefaultValue(key, fallback);
  return value;
}

function settingsPatchLocalValidationHints(changes) {
  return settingsPatchReviewCall("settingsPatchLocalValidationHints", [changes], []);
}

function settingsPatchLocalValidationHintLines(changes) {
  return settingsPatchReviewCall("settingsPatchLocalValidationHintLines", [changes], []);
}

const settingsBuilderControlsModule = window.__settingsBuilderControlsModule || {};
delete window.__settingsBuilderControlsModule;
const settingsBuilderControls = typeof settingsBuilderControlsModule.createSettingsBuilderControlsModule === "function"
  ? settingsBuilderControlsModule.createSettingsBuilderControlsModule({
    audioSettingsBuilderFields,
    byId,
    fileSafetySettingsBuilderFields,
    finalLibraryPromotionSettingsBuilderFields,
    formatSettingsChoiceLabel,
    networkSettingsBuilderFields,
    pendingPublishSettingsBuilderFields,
    qualityDetailSettingsBuilderFields,
    queueSettingsBuilderFields,
    runtimeSettingsBuilderFields,
    settingsBuilderFields,
    settingsFieldAllowedValues,
    settingsFieldDefaultValue,
    settingsFieldDefinition,
    settingsFieldHelpText,
    settingsFieldIsAdvanced,
    settingsFieldLabel,
    settingsMetadataValue,
    subtitleSettingsBuilderFields,
    videoDetailSettingsBuilderFields,
  })
  : {};
const renderSettingsAdvancedControls = settingsBuilderControls.renderSettingsAdvancedControls || function () {};
const handleSettingsAdvancedToggleClick = settingsBuilderControls.handleSettingsAdvancedToggleClick || function () {};
const applySettingsFieldMetadataToControls = settingsBuilderControls.applySettingsFieldMetadataToControls || function () {};
const refreshSettingsSelectChoices = settingsBuilderControls.refreshSettingsSelectChoices || function () {};
const refreshSettingsBuilderChoices = settingsBuilderControls.refreshSettingsBuilderChoices || function () {};

const audioSettingsBuilderModule = window.__settingsViewAudioBuilderModule || {};
delete window.__settingsViewAudioBuilderModule;
const audioSettingsBuilder = typeof audioSettingsBuilderModule.createAudioSettingsBuilder === "function"
  ? audioSettingsBuilderModule.createAudioSettingsBuilder({
    audioSettingsBuilderFields,
    audioSettingsBuilderState,
    byId,
    formatSettingsChoiceLabel,
    formatSettingsListValue,
    parseSettingsListText,
    readSettingsBuilderNumber,
    refreshSettingsSelectChoices,
    renderSettingsActiveMediaPolicyHandoff,
    renderSettingsMediaPolicyCrossCheck,
    setSettingsBuilderControl,
    setText,
    settingsBuilderConfigValue,
    settingsBuilderInputValue,
    settingsFieldDefinition,
    settingsSpecificImpactHints,
    writeSettingsPatchJson,
  })
  : {};
const refreshAudioSettingsBuilderChoices = audioSettingsBuilder.refreshAudioSettingsBuilderChoices || function () {
  refreshSettingsSelectChoices(audioSettingsBuilderFields);
};
const syncAudioSettingsBuilderFromConfig = audioSettingsBuilder.syncAudioSettingsBuilderFromConfig || function () {};
const markAudioSettingsBuilderDirty = audioSettingsBuilder.markAudioSettingsBuilderDirty || function () {};
const collectAudioSettingsBuilderPatch = audioSettingsBuilder.collectAudioSettingsBuilderPatch || function () { return {}; };
const applyAudioSettingsBuilderToPatch = audioSettingsBuilder.applyAudioSettingsBuilderToPatch || function () {};
const renderAudioSettingsBuilderGuidance = audioSettingsBuilder.renderAudioSettingsBuilderGuidance || function () {};

const videoDetailSettingsBuilderModule = window.__settingsViewVideoBuilderModule || {};
delete window.__settingsViewVideoBuilderModule;
const videoDetailSettingsBuilder = typeof videoDetailSettingsBuilderModule.createVideoDetailSettingsBuilder === "function"
  ? videoDetailSettingsBuilderModule.createVideoDetailSettingsBuilder({
    clearRows,
    byId,
    formatSettingsChoiceLabel,
    formatSettingsListValue,
    getLastSettings,
    parseSettingsListText,
    readSettingsBuilderNumber,
    refreshSettingsSelectChoices,
    renderSettingsActiveMediaPolicyHandoff,
    setSettingsBuilderControl,
    setText,
    settingsBuilderConfigValue,
    settingsBuilderInputValue,
    settingsFieldDefinition,
    settingsSpecificImpactHints,
    videoDetailSettingsBuilderFields,
    videoDetailSettingsBuilderState,
    writeSettingsPatchJson,
  })
  : {};
const syncVideoDetailSettingsBuilderFromConfig = videoDetailSettingsBuilder.syncVideoDetailSettingsBuilderFromConfig || function () {};
const markVideoDetailSettingsBuilderDirty = videoDetailSettingsBuilder.markVideoDetailSettingsBuilderDirty || function () {};
const collectVideoDetailSettingsBuilderPatch = videoDetailSettingsBuilder.collectVideoDetailSettingsBuilderPatch || function () { return {}; };
const applyVideoDetailSettingsBuilderToPatch = videoDetailSettingsBuilder.applyVideoDetailSettingsBuilderToPatch || function () {};
const renderVideoDetailSettingsBuilderGuidance = videoDetailSettingsBuilder.renderVideoDetailSettingsBuilderGuidance || function () {};
const settingsEncoderCapabilityReport = videoDetailSettingsBuilder.settingsEncoderCapabilityReport || function () { return {}; };
const settingsEncoderCapabilityStatus = videoDetailSettingsBuilder.settingsEncoderCapabilityStatus || function () { return "Not loaded"; };
const settingsEncoderCapabilitySummaryLines = videoDetailSettingsBuilder.settingsEncoderCapabilitySummaryLines || function () { return []; };
const renderSettingsEncoderCapabilityReport = videoDetailSettingsBuilder.renderSettingsEncoderCapabilityReport || function () {};

const qualityDetailSettingsBuilderModule = window.__settingsViewQualityBuilderModule || {};
delete window.__settingsViewQualityBuilderModule;
const qualityDetailSettingsBuilder = typeof qualityDetailSettingsBuilderModule.createQualityDetailSettingsBuilder === "function"
  ? qualityDetailSettingsBuilderModule.createQualityDetailSettingsBuilder({
    byId,
    formatSettingsChoiceLabel,
    qualityDetailSettingsBuilderFields,
    qualityDetailSettingsBuilderState,
    readSettingsBuilderFloat,
    readSettingsBuilderNumber,
    refreshSettingsSelectChoices,
    renderSettingsActiveMediaPolicyHandoff,
    setSettingsBuilderControl,
    setText,
    settingsBuilderConfigValue,
    settingsBuilderInputValue,
    settingsFieldDefinition,
    settingsSpecificImpactHints,
    writeSettingsPatchJson,
  })
  : {};
const syncQualityDetailSettingsBuilderFromConfig = qualityDetailSettingsBuilder.syncQualityDetailSettingsBuilderFromConfig || function () {};
const markQualityDetailSettingsBuilderDirty = qualityDetailSettingsBuilder.markQualityDetailSettingsBuilderDirty || function () {};
const collectQualityDetailSettingsBuilderPatch = qualityDetailSettingsBuilder.collectQualityDetailSettingsBuilderPatch || function () { return {}; };
const applyQualityDetailSettingsBuilderToPatch = qualityDetailSettingsBuilder.applyQualityDetailSettingsBuilderToPatch || function () {};
const renderQualityDetailSettingsBuilderGuidance = qualityDetailSettingsBuilder.renderQualityDetailSettingsBuilderGuidance || function () {};

const subtitleSettingsBuilderModule = window.__settingsViewSubtitleBuilderModule || {};
delete window.__settingsViewSubtitleBuilderModule;
const subtitleSettingsBuilder = typeof subtitleSettingsBuilderModule.createSubtitleSettingsBuilder === "function"
  ? subtitleSettingsBuilderModule.createSubtitleSettingsBuilder({
    byId,
    formatSettingsListValue,
    getLastSettings,
    parseSettingsListText,
    readSettingsBuilderNumber,
    renderSettingsActiveMediaPolicyHandoff,
    renderSettingsMediaPolicyCrossCheck,
    setText,
    settingsBuilderConfigValue,
    settingsBuilderInputValue,
    settingsFieldDefinition,
    settingsSpecificImpactHints,
    subtitleSettingsBuilderFields,
    subtitleSettingsBuilderState,
    writeSettingsPatchJson,
  })
  : {};
const syncSubtitleSettingsBuilderFromConfig = subtitleSettingsBuilder.syncSubtitleSettingsBuilderFromConfig || function () {};
const markSubtitleSettingsBuilderDirty = subtitleSettingsBuilder.markSubtitleSettingsBuilderDirty || function () {};
const collectSubtitleSettingsBuilderPatch = subtitleSettingsBuilder.collectSubtitleSettingsBuilderPatch || function () { return {}; };
const applySubtitleSettingsBuilderToPatch = subtitleSettingsBuilder.applySubtitleSettingsBuilderToPatch || function () {};
const settingsBdpgsOcrPathEvidence = subtitleSettingsBuilder.settingsBdpgsOcrPathEvidence || function () { return {}; };
const settingsBdpgsOcrPathEvidenceStatus = subtitleSettingsBuilder.settingsBdpgsOcrPathEvidenceStatus || function () { return "Not loaded"; };
const settingsBdpgsOcrPathEvidenceLines = subtitleSettingsBuilder.settingsBdpgsOcrPathEvidenceLines || function () { return []; };
const renderSettingsBdpgsOcrPathEvidence = subtitleSettingsBuilder.renderSettingsBdpgsOcrPathEvidence || function () {};
const settingsVobSubOcrPathEvidence = subtitleSettingsBuilder.settingsVobSubOcrPathEvidence || function () { return {}; };
const settingsVobSubOcrPathEvidenceStatus = subtitleSettingsBuilder.settingsVobSubOcrPathEvidenceStatus || function () { return "Not loaded"; };
const settingsVobSubOcrPathEvidenceLines = subtitleSettingsBuilder.settingsVobSubOcrPathEvidenceLines || function () { return []; };
const renderSettingsVobSubOcrPathEvidence = subtitleSettingsBuilder.renderSettingsVobSubOcrPathEvidence || function () {};
const renderSubtitleSettingsBuilderGuidance = subtitleSettingsBuilder.renderSubtitleSettingsBuilderGuidance || function () {};

const queueSettingsBuilderModule = window.__settingsViewQueueBuilderModule || {};
delete window.__settingsViewQueueBuilderModule;
const queueSettingsBuilder = typeof queueSettingsBuilderModule.createQueueSettingsBuilder === "function"
  ? queueSettingsBuilderModule.createQueueSettingsBuilder({
    byId,
    formatSettingsListValue,
    parseSettingsListText,
    queueSettingsBuilderFields,
    queueSettingsBuilderState,
    readSettingsBuilderNumber,
    setText,
    settingsBuilderConfigValue,
    settingsBuilderInputValue,
    settingsFieldDefinition,
    settingsSpecificImpactHints,
    writeSettingsPatchJson,
  })
  : {};
const syncQueueSettingsBuilderFromConfig = queueSettingsBuilder.syncQueueSettingsBuilderFromConfig || function () {};
const markQueueSettingsBuilderDirty = queueSettingsBuilder.markQueueSettingsBuilderDirty || function () {};
const collectQueueSettingsBuilderPatch = queueSettingsBuilder.collectQueueSettingsBuilderPatch || function () { return {}; };
const applyQueueSettingsBuilderToPatch = queueSettingsBuilder.applyQueueSettingsBuilderToPatch || function () {};
const renderQueueSettingsBuilderGuidance = queueSettingsBuilder.renderQueueSettingsBuilderGuidance || function () {};

const runtimeSettingsBuilderModule = window.__settingsViewRuntimeBuilderModule || {};
delete window.__settingsViewRuntimeBuilderModule;
const runtimeSettingsBuilder = typeof runtimeSettingsBuilderModule.createRuntimeSettingsBuilder === "function"
  ? runtimeSettingsBuilderModule.createRuntimeSettingsBuilder({
    byId,
    readSettingsBuilderNumber,
    refreshSettingsSelectChoices,
    runtimeSettingsBuilderFields,
    runtimeSettingsBuilderState,
    setSettingsBuilderControl,
    setText,
    settingsBuilderConfigValue,
    settingsBuilderInputValue,
    settingsFieldDefinition,
    settingsSpecificImpactHints,
    writeSettingsPatchJson,
  })
  : {};
const syncRuntimeSettingsBuilderFromConfig = runtimeSettingsBuilder.syncRuntimeSettingsBuilderFromConfig || function () {};
const markRuntimeSettingsBuilderDirty = runtimeSettingsBuilder.markRuntimeSettingsBuilderDirty || function () {};
const collectRuntimeSettingsBuilderPatch = runtimeSettingsBuilder.collectRuntimeSettingsBuilderPatch || function () { return {}; };
const applyRuntimeSettingsBuilderToPatch = runtimeSettingsBuilder.applyRuntimeSettingsBuilderToPatch || function () {};
const renderRuntimeSettingsBuilderGuidance = runtimeSettingsBuilder.renderRuntimeSettingsBuilderGuidance || function () {};

const fileSafetySettingsBuilderModule = window.__settingsViewFileSafetyBuilderModule || {};
delete window.__settingsViewFileSafetyBuilderModule;
const fileSafetySettingsBuilder = typeof fileSafetySettingsBuilderModule.createFileSafetySettingsBuilder === "function"
  ? fileSafetySettingsBuilderModule.createFileSafetySettingsBuilder({
    byId,
    fileSafetySettingsBuilderFields,
    fileSafetySettingsBuilderState,
    formatSettingsListValue,
    parseSettingsListText,
    readSettingsBuilderFloat,
    readSettingsBuilderNumber,
    renderSettingsActiveMediaPolicyHandoff,
    setText,
    settingsBuilderConfigValue,
    settingsBuilderInputValue,
    settingsFieldDefinition,
    settingsSpecificImpactHints,
    writeSettingsPatchJson,
  })
  : {};
const syncFileSafetySettingsBuilderFromConfig = fileSafetySettingsBuilder.syncFileSafetySettingsBuilderFromConfig || function () {};
const markFileSafetySettingsBuilderDirty = fileSafetySettingsBuilder.markFileSafetySettingsBuilderDirty || function () {};
const collectFileSafetySettingsBuilderPatch = fileSafetySettingsBuilder.collectFileSafetySettingsBuilderPatch || function () { return {}; };
const applyFileSafetySettingsBuilderToPatch = fileSafetySettingsBuilder.applyFileSafetySettingsBuilderToPatch || function () {};
const renderFileSafetySettingsBuilderGuidance = fileSafetySettingsBuilder.renderFileSafetySettingsBuilderGuidance || function () {};

const pendingPublishSettingsBuilderModule = window.__settingsViewPendingPublishBuilderModule || {};
delete window.__settingsViewPendingPublishBuilderModule;
const pendingPublishSettingsBuilder = typeof pendingPublishSettingsBuilderModule.createPendingPublishSettingsBuilder === "function"
  ? pendingPublishSettingsBuilderModule.createPendingPublishSettingsBuilder({
    byId,
    formatSettingsListValue,
    parseSettingsListText,
    pendingPublishSettingsBuilderFields,
    pendingPublishSettingsBuilderState,
    readSettingsBuilderFloat,
    readSettingsBuilderNumber,
    renderSettingsActiveMediaPolicyHandoff,
    setText,
    settingsBuilderConfigValue,
    settingsBuilderInputValue,
    settingsFieldDefinition,
    settingsSpecificImpactHints,
    writeSettingsPatchJson,
  })
  : {};
const syncPendingPublishSettingsBuilderFromConfig = pendingPublishSettingsBuilder.syncPendingPublishSettingsBuilderFromConfig || function () {};
const markPendingPublishSettingsBuilderDirty = pendingPublishSettingsBuilder.markPendingPublishSettingsBuilderDirty || function () {};
const collectPendingPublishSettingsBuilderPatch = pendingPublishSettingsBuilder.collectPendingPublishSettingsBuilderPatch || function () { return {}; };
const applyPendingPublishSettingsBuilderToPatch = pendingPublishSettingsBuilder.applyPendingPublishSettingsBuilderToPatch || function () {};
const renderPendingPublishSettingsBuilderGuidance = pendingPublishSettingsBuilder.renderPendingPublishSettingsBuilderGuidance || function () {};

const networkSettingsBuilderModule = window.__settingsViewNetworkBuilderModule || {};
delete window.__settingsViewNetworkBuilderModule;
const networkSettingsBuilder = typeof networkSettingsBuilderModule.createNetworkSettingsBuilder === "function"
  ? networkSettingsBuilderModule.createNetworkSettingsBuilder({
    byId,
    formatSettingsChoiceLabel,
    networkSettingsBuilderFields,
    networkSettingsBuilderState,
    readSettingsBuilderNumber,
    refreshSettingsSelectChoices,
    setSettingsBuilderControl,
    setText,
    settingsBuilderConfigValue,
    settingsBuilderInputValue,
    settingsFieldDefinition,
    runNetworkWorkerTestConnection: (options) => window.mediaPipelineNetworkView?.runNetworkWorkerTestConnection?.(options),
    writeSettingsPatchJson,
  })
  : {};
const syncNetworkSettingsBuilderFromConfig = networkSettingsBuilder.syncNetworkSettingsBuilderFromConfig || function () {};
const markNetworkSettingsBuilderDirty = networkSettingsBuilder.markNetworkSettingsBuilderDirty || function () {};
const collectNetworkSettingsBuilderPatch = networkSettingsBuilder.collectNetworkSettingsBuilderPatch || function () { return {}; };
const applyNetworkSettingsBuilderToPatch = networkSettingsBuilder.applyNetworkSettingsBuilderToPatch || function () {};
const renderNetworkSettingsBuilderGuidance = networkSettingsBuilder.renderNetworkSettingsBuilderGuidance || function () {};

const settingsRawTriageModule = window.__settingsRawTriageModule || {};
delete window.__settingsRawTriageModule;
const settingsRawTriage = typeof settingsRawTriageModule.createSettingsRawTriageModule === "function"
  ? settingsRawTriageModule.createSettingsRawTriageModule({
    appendCells,
    byId,
    clearRows,
    filterRows,
    formatConfigValue,
    getLastSettingsFieldDefinitions: () => lastSettingsFieldDefinitions,
    getLastSettingsValues: () => lastSettingsValues,
    makeRowSelectable,
    setText,
    settingsBdpgsOcrPathEvidenceLines,
    settingsBdpgsOcrPathEvidenceStatus,
    settingsVobSubOcrPathEvidenceLines,
    settingsVobSubOcrPathEvidenceStatus,
    settingsBuilderCoveredKeys,
    settingsFieldDefinition,
    settingsImpactGroupForKey,
    settingsSpecificImpactHints,
    updateTableStatusLegend,
  })
  : {};
const setSettingsRows = settingsRawTriage.setSettingsRows || function () {};
const renderSettingsRows = settingsRawTriage.renderSettingsRows || function () {};
const settingsRawTriageRows = settingsRawTriage.settingsRawTriageRows || function () { return []; };
const settingsRawTriageStatus = settingsRawTriage.settingsRawTriageStatus || function () { return "No config"; };
const settingsRawTriageSummaryLines = settingsRawTriage.settingsRawTriageSummaryLines || function () { return []; };
const settingsRawTriageDetailLines = settingsRawTriage.settingsRawTriageDetailLines || function () { return []; };
const renderSettingsRawTriage = settingsRawTriage.renderSettingsRawTriage || function () {};
const settingsRawActionPlanRows = settingsRawTriage.settingsRawActionPlanRows || function () { return []; };
const settingsRawActionPlanStatus = settingsRawTriage.settingsRawActionPlanStatus || function () { return "No config"; };
const settingsRawActionPlanSummaryLines = settingsRawTriage.settingsRawActionPlanSummaryLines || function () { return []; };
const settingsRawActionPlanDetailLines = settingsRawTriage.settingsRawActionPlanDetailLines || function () { return []; };
const renderSettingsRawActionPlan = settingsRawTriage.renderSettingsRawActionPlan || function () {};
const boundedSettingsValueText = settingsRawTriage.boundedSettingsValueText || function (value) {
  const text = formatConfigValue(value);
  if (!text) return "(empty)";
  return text.length > 600 ? `${text.slice(0, 600)}...` : text;
};

const settingsSafetyLocksModule = window.__settingsSafetyLocksModule || {};
delete window.__settingsSafetyLocksModule;
const settingsSafetyLocks = typeof settingsSafetyLocksModule.createSettingsSafetyLocksModule === "function"
  ? settingsSafetyLocksModule.createSettingsSafetyLocksModule({
    appendCells,
    boundedSettingsValueText,
    byId,
    clearRows,
    getLastSettingsValues: () => lastSettingsValues,
    setText,
    settingsBoolValue,
    settingsSafetyLockDefinitions,
  })
  : {};
const settingsSafetyLockRows = settingsSafetyLocks.settingsSafetyLockRows || function () { return []; };
const settingsSafetyLockStatus = settingsSafetyLocks.settingsSafetyLockStatus || function () { return "No locks"; };
const settingsSafetyLockSummaryLines = settingsSafetyLocks.settingsSafetyLockSummaryLines || function () { return []; };
const renderSettingsSafetyLocks = settingsSafetyLocks.renderSettingsSafetyLocks || function () {};
function setSettingsBuilderControl(id, value) {
  const fn = settingsPatchReviewFunction("setSettingsBuilderControl");
  if (fn) fn(id, value);
}

function syncSettingsBuilderFromConfig() {
  const fn = settingsPatchReviewFunction("syncSettingsBuilderFromConfig");
  if (fn) fn();
}

function markSettingsBuilderDirty() {
  const fn = settingsPatchReviewFunction("markSettingsBuilderDirty");
  if (fn) fn();
}

function settingsBuilderInputValue(id) {
  const fn = settingsPatchReviewFunction("settingsBuilderInputValue");
  return fn ? fn(id) : "";
}

function readSettingsBuilderNumber(id, label) {
  const fn = settingsPatchReviewFunction("readSettingsBuilderNumber");
  if (!fn) throw new Error(`${label} is required.`);
  return fn(id, label);
}

function readSettingsBuilderFloat(id, label) {
  const fn = settingsPatchReviewFunction("readSettingsBuilderFloat");
  if (!fn) throw new Error(`${label} is required.`);
  return fn(id, label);
}

function settingsRawConfigValue(key) {
  const fn = settingsPatchReviewFunction("settingsRawConfigValue");
  return fn ? fn(key) : undefined;
}

function parseSettingsPatchJson() {
  const fn = settingsPatchReviewFunction("parseSettingsPatchJson");
  return fn ? fn() : {};
}

function markSettingsPatchTouched() {
  const fn = settingsPatchReviewFunction("markSettingsPatchTouched");
  if (fn) fn();
}

function settingsPatchIsTouched() {
  const fn = settingsPatchReviewFunction("settingsPatchIsTouched");
  return fn ? fn() : settingsPatchTouched;
}

function settingsPatchEffectiveChangedEntries() {
  const fn = settingsPatchReviewFunction("settingsPatchEffectiveChangedEntries");
  return fn ? fn() : [];
}

function settingsPatchHasUnsavedChanges() {
  const fn = settingsPatchReviewFunction("settingsPatchHasUnsavedChanges");
  return fn ? fn() : false;
}

function writeSettingsPatchJson(patch, detail) {
  const fn = settingsPatchReviewFunction("writeSettingsPatchJson");
  if (fn) fn(patch, detail);
}

let settingsPatchReview = {};

function settingsPatchReviewFunction(name) {
  const fn = settingsPatchReview ? settingsPatchReview[name] : null;
  return typeof fn === "function" ? fn : null;
}

function setFinalLibraryPromotionStatus(status, detail) {
  const fn = settingsPatchReviewFunction("setFinalLibraryPromotionStatus");
  if (fn) {
    fn(status, detail);
    return;
  }
  setText("settings-final-library-status", status || "Not loaded");
  if (detail !== undefined) setText("settings-final-library-guidance", detail);
}

function finalLibraryPromotionBrowseDetailLines(result, label) {
  const fn = settingsPatchReviewFunction("finalLibraryPromotionBrowseDetailLines");
  return fn ? fn(result, label) : [result?.message || `Folder browse returned for ${label}.`];
}

function addFinalLibraryPromotionRule() {
  const fn = settingsPatchReviewFunction("addFinalLibraryPromotionRule");
  if (fn) fn();
}

function syncFinalLibraryPromotionSettingsBuilderFromConfig() {
  const fn = settingsPatchReviewFunction("syncFinalLibraryPromotionSettingsBuilderFromConfig");
  if (fn) fn();
}

function markFinalLibraryPromotionSettingsBuilderDirty() {
  const fn = settingsPatchReviewFunction("markFinalLibraryPromotionSettingsBuilderDirty");
  if (fn) fn();
}

function collectFinalLibraryPromotionSettingsPatch() {
  const fn = settingsPatchReviewFunction("collectFinalLibraryPromotionSettingsPatch");
  if (!fn) throw new Error("Final Library Promotion settings module is unavailable.");
  return fn();
}

function renderFinalLibraryPromotionSettingsGuidance() {
  const fn = settingsPatchReviewFunction("renderFinalLibraryPromotionSettingsGuidance");
  if (fn) fn();
}

function finalLibraryPromotionSettingsResultLines(action, result, changes) {
  const fn = settingsPatchReviewFunction("finalLibraryPromotionSettingsResultLines");
  return fn ? fn(action, result, changes) : [`${action}: ${result?.message || "No backend message returned."}`];
}

async function browseFinalLibraryPromotionRulePath(input, settingKey, label) {
  if (rejectSettingsCommandWhileBusy("settings.browse_path", "settings-final-library-status", "settings-final-library-guidance")) return;
  setSettingsCommandBusy(true);
  setFinalLibraryPromotionStatus(`Opening ${label} folder browser...`, [
    `Opening backend-owned Windows folder browser for ${label}.`,
    "No settings will be saved by this action.",
  ].join("\n"));
  try {
    const initialPath = input?.value || "";
    const result = await apiPost(
      "/api/settings/browse-path",
      { setting_key: settingKey, selection_mode: "folder", initial_path: initialPath },
      { timeoutMs: 15 * 60 * 1000 }
    );
    appendCommandResult(result);
    const data = result?.data && typeof result.data === "object" ? result.data : {};
    const selectedPath = String(data.selected_path || "");
    if (result.ok && !data.canceled && selectedPath && input) {
      input.value = selectedPath;
      markFinalLibraryPromotionSettingsBuilderDirty();
      setText("settings-final-library-status", `${label} path staged`);
    } else if (data.canceled) {
      setText("settings-final-library-status", "Folder browse canceled");
    } else {
      setText("settings-final-library-status", result.ok ? "Folder browse needs review" : "Folder browse failed");
    }
    setText("settings-final-library-guidance", finalLibraryPromotionBrowseDetailLines(result, label).join("\n"));
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    const result = {
      command: "settings.browse_path",
      ok: false,
      severity: "error",
      message,
    };
    appendCommandResult(result);
    setFinalLibraryPromotionStatus("Folder browse failed", finalLibraryPromotionBrowseDetailLines(result, label).join("\n"));
  } finally {
    setSettingsCommandBusy(false);
  }
}

async function previewFinalLibraryPromotionSettings() {
  if (rejectSettingsCommandWhileBusy("settings.preview_patch", "settings-final-library-status", "settings-final-library-guidance")) return;
  let changes;
  try {
    changes = collectFinalLibraryPromotionSettingsPatch();
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    setFinalLibraryPromotionStatus("Invalid final library settings", message);
    appendCommandResult({
      command: "settings.preview_patch",
      ok: false,
      severity: "error",
      message,
    });
    return;
  }
  setSettingsCommandBusy(true);
  setFinalLibraryPromotionStatus("Previewing...", "Requesting backend preview for Final Library Promotion settings. This will not save the PSD1.");
  try {
    const result = await apiPost("/api/settings/preview-patch", { changes });
    appendCommandResult(result);
    lastSettingsPatchPreviewEvidence = {
      command: "settings.preview_patch",
      result,
      changes: settingsStableJsonValue(changes),
      signature: settingsPatchSignature(changes),
      captured_at: new Date().toISOString(),
    };
    setFinalLibraryPromotionStatus(result.ok ? "Preview ready" : result.severity || "Preview failed", finalLibraryPromotionSettingsResultLines("Backend preview", result, changes).join("\n"));
    renderSettingsPatchSummary();
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    const result = {
      command: "settings.preview_patch",
      ok: false,
      severity: "error",
      message,
    };
    appendCommandResult(result);
    setFinalLibraryPromotionStatus("Preview failed", finalLibraryPromotionSettingsResultLines("Backend preview", result, changes).join("\n"));
  } finally {
    setSettingsCommandBusy(false);
  }
}

async function saveFinalLibraryPromotionSettings() {
  if (rejectSettingsCommandWhileBusy("settings.save_patch", "settings-final-library-status", "settings-final-library-guidance")) return;
  let changes;
  try {
    changes = collectFinalLibraryPromotionSettingsPatch();
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    setFinalLibraryPromotionStatus("Invalid final library settings", message);
    appendCommandResult({
      command: "settings.save_patch",
      ok: false,
      severity: "error",
      message,
    });
    return;
  }
  const confirmation = [
    "Save Final Library Promotion settings to the active backend config?",
    "",
    `Promotion enabled: ${changes.FinalLibraryPromotionEnabled ? "yes" : "no"}`,
    `Rules: ${changes.FinalLibraryPromotionRules.filter((rule) => rule.enabled).length} enabled`,
    `Verification: ${changes.FinalLibraryPromotionVerificationMode}`,
    `Cleanup after verified promotion: ${changes.FinalLibraryPromotionCleanupAfterVerified ? "yes" : "no"}`,
    `Destructive overwrite: ${changes.FinalLibraryPromotionOverwriteExisting ? "yes" : "no"}`,
    "",
    settingsRuntimeRestartConfirmationLine(),
  ];
  if (changes.FinalLibraryPromotionOverwriteExisting) {
    confirmation.push("", "Overwrite warning: existing final files will be deleted before replacement copies when promotion runs.");
  }
  if (changes.FinalLibraryPromotionCleanupAfterVerified) {
    confirmation.push("", "Cleanup warning: verified promoted publish-output files below Outsource can be deleted after promotion.");
  }
  if (!window.confirm(confirmation.join("\n"))) {
    setFinalLibraryPromotionStatus("Save cancelled", "No Final Library Promotion settings were saved.");
    appendCommandResult({
      command: "settings.save_patch",
      ok: false,
      severity: "info",
      message: "Final Library Promotion settings save cancelled by operator.",
    });
    return;
  }
  setSettingsCommandBusy(true);
  setFinalLibraryPromotionStatus("Saving...", "Saving backend-validated Final Library Promotion settings to the active PSD1. A backup will be created first.");
  try {
    const result = await apiPost("/api/settings/save-patch", { changes, confirm_save: true });
    appendCommandResult(result);
    lastSettingsPatchSaveEvidence = {
      command: "settings.save_patch",
      result,
      changes: settingsStableJsonValue(changes),
      signature: settingsPatchSignature(changes),
      captured_at: new Date().toISOString(),
    };
    const statusLines = finalLibraryPromotionSettingsResultLines("Backend save", result, changes);
    if (result.ok) {
      statusLines.push("", ...settingsRuntimeRestartNoticeLines(result));
      maybeShowSettingsRuntimeRestartNotice(result);
    }
    setFinalLibraryPromotionStatus(result.ok ? "Saved" : result.severity || "Save failed", statusLines.join("\n"));
    renderSettingsPatchSummary();
    if (result.ok) {
      finalLibraryPromotionSettingsBuilderState.dirty = false;
      await refreshAll();
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    const result = {
      command: "settings.save_patch",
      ok: false,
      severity: "error",
      message,
    };
    appendCommandResult(result);
    setFinalLibraryPromotionStatus("Save failed", finalLibraryPromotionSettingsResultLines("Backend save", result, changes).join("\n"));
  } finally {
    setSettingsCommandBusy(false);
  }
}

function collectSettingsBuilderPatch() {
  const fn = settingsPatchReviewFunction("collectSettingsBuilderPatch");
  return fn ? fn() : {};
}

function applySettingsBuilderToPatch() {
  const fn = settingsPatchReviewFunction("applySettingsBuilderToPatch");
  return fn ? fn() : true;
}

let settingsPolicyImpact = {};
function settingsPolicyImpactFunction(name) {
  return settingsPolicyImpact && typeof settingsPolicyImpact[name] === "function" ? settingsPolicyImpact[name] : null;
}

function settingsPolicyImpactCall(name, args, fallback) {
  const fn = settingsPolicyImpactFunction(name);
  return fn ? fn(...args) : fallback;
}

function settingsPolicyImpactDo(name, args) {
  const fn = settingsPolicyImpactFunction(name);
  if (fn) fn(...args);
}

function settingsMediaPolicyRows() { return settingsPolicyImpactCall("settingsMediaPolicyRows", [], []); }
function settingsMediaPolicyStatus(rows = settingsMediaPolicyRows()) { return settingsPolicyImpactCall("settingsMediaPolicyStatus", [rows], "No policy"); }
function settingsActiveMediaPolicyRows() { return settingsPolicyImpactCall("settingsActiveMediaPolicyRows", [], []); }
function settingsActiveMediaPolicyStatus(rows = settingsActiveMediaPolicyRows()) { return settingsPolicyImpactCall("settingsActiveMediaPolicyStatus", [rows], "No policy"); }
function settingsActiveMediaPolicySummaryLines(rows = settingsActiveMediaPolicyRows()) { return settingsPolicyImpactCall("settingsActiveMediaPolicySummaryLines", [rows], []); }
function renderSettingsActiveMediaPolicyHandoff() { settingsPolicyImpactDo("renderSettingsActiveMediaPolicyHandoff", []); }
function settingsEffectivePolicyRows(entries) { return settingsPolicyImpactCall("settingsEffectivePolicyRows", [entries], []); }
function settingsEffectivePolicyTrustStatus(rows = settingsEffectivePolicyRows(settingsPatchImpactEntries(parseSettingsPatchJson()))) { return settingsPolicyImpactCall("settingsEffectivePolicyTrustStatus", [rows], "Not evaluated"); }
function settingsEffectivePolicySummaryLines(rows = settingsEffectivePolicyRows(settingsPatchImpactEntries(parseSettingsPatchJson()))) { return settingsPolicyImpactCall("settingsEffectivePolicySummaryLines", [rows], []); }
function settingsEffectivePolicyDetailLines(row) { return settingsPolicyImpactCall("settingsEffectivePolicyDetailLines", [row], []); }
function renderSettingsEffectivePolicyTrustFromEntries(entries) { settingsPolicyImpactDo("renderSettingsEffectivePolicyTrustFromEntries", [entries]); }
function renderSettingsEffectivePolicyTrustForError(message) { settingsPolicyImpactDo("renderSettingsEffectivePolicyTrustForError", [message]); }
function settingsMediaPolicySummaryLines(rows = settingsMediaPolicyRows()) { return settingsPolicyImpactCall("settingsMediaPolicySummaryLines", [rows], []); }
function renderSettingsMediaPolicyCrossCheck() { settingsPolicyImpactDo("renderSettingsMediaPolicyCrossCheck", []); }
function settingsBackendPolicyImpact(settings = lastSettings) { return settingsPolicyImpactCall("settingsBackendPolicyImpact", [settings], { schema_version: "", media_policy_readiness: null, launch_risk_handoff: null }); }
function settingsBackendMediaPolicyReadiness(settings = lastSettings) { return settingsPolicyImpactCall("settingsBackendMediaPolicyReadiness", [settings], { operator_status: "Not loaded", rows: [], counts: {}, summary_lines: [] }); }
function settingsBackendMediaPolicyStatus(readiness = settingsBackendMediaPolicyReadiness()) { return settingsPolicyImpactCall("settingsBackendMediaPolicyStatus", [readiness], "Not evaluated"); }
function settingsBackendMediaPolicySummaryLines(readiness = settingsBackendMediaPolicyReadiness()) { return settingsPolicyImpactCall("settingsBackendMediaPolicySummaryLines", [readiness], []); }
function renderSettingsBackendMediaPolicyReadiness(settings = lastSettings) { settingsPolicyImpactDo("renderSettingsBackendMediaPolicyReadiness", [settings]); }
function settingsImpactGroupForKey(key) { return settingsPolicyImpactCall("settingsImpactGroupForKey", [key], null); }
function settingsPatchImpactEntries(patch) { return settingsPolicyImpactCall("settingsPatchImpactEntries", [patch], []); }
function renderSettingsPatchImpactSummaryFromEntries(entries) { settingsPolicyImpactDo("renderSettingsPatchImpactSummaryFromEntries", [entries]); }
function settingsBoolValue(value) { return settingsPolicyImpactCall("settingsBoolValue", [value], null); }
function settingsPatchCandidateValue(entries, key) { return settingsPolicyImpactCall("settingsPatchCandidateValue", [entries, key], settingsRawConfigValue(key)); }
function settingsStableJsonValue(value) { return settingsPolicyImpactCall("settingsStableJsonValue", [value], value); }
function settingsPatchSignature(changes) { return settingsPolicyImpactCall("settingsPatchSignature", [changes], ""); }
function settingsPatchRequestExtras() {
  const provider = window.mediaPipelineSettingsLibraries?.libraryProfileResetRequest;
  if (typeof provider !== "function") return {};
  try {
    const libraryProfileResets = provider();
    if (Array.isArray(libraryProfileResets) && libraryProfileResets.length) {
      return { library_profile_resets: libraryProfileResets };
    }
  } catch (_error) {
    return {};
  }
  return {};
}
function settingsPatchRequestSignature(changes, extras = {}) {
  if (Array.isArray(extras.library_profile_resets) && extras.library_profile_resets.length) {
    return settingsPatchSignature({ changes, library_profile_resets: extras.library_profile_resets });
  }
  return settingsPatchSignature(changes);
}
function settingsCurrentPatchSignature() { return settingsPolicyImpactCall("settingsCurrentPatchSignature", [], ""); }
function settingsPatchListValue(value) { return settingsPolicyImpactCall("settingsPatchListValue", [value], []); }
function settingsPolicyDeltaStatus(rows) { return settingsPolicyImpactCall("settingsPolicyDeltaStatus", [rows], "No current change"); }
function settingsPolicyDeltaRows(entries) { return settingsPolicyImpactCall("settingsPolicyDeltaRows", [entries], []); }
function settingsPolicyDeltaSummaryLines(rows) { return settingsPolicyImpactCall("settingsPolicyDeltaSummaryLines", [rows], []); }
function renderSettingsPolicyDeltaFromEntries(entries) { settingsPolicyImpactDo("renderSettingsPolicyDeltaFromEntries", [entries]); }
function renderSettingsPolicyDeltaForError(message) { settingsPolicyImpactDo("renderSettingsPolicyDeltaForError", [message]); }

const settingsPatchReviewModule = window.__settingsPatchReviewModule || {};
delete window.__settingsPatchReviewModule;
settingsPatchReview = typeof settingsPatchReviewModule.createSettingsPatchReviewModule === "function"
  ? settingsPatchReviewModule.createSettingsPatchReviewModule({
    addSettingsEventHandlers: {
      addFinalLibraryPromotionRule,
      applyAudioSettingsBuilderToPatch,
      applyFileSafetySettingsBuilderToPatch,
      applyNetworkSettingsBuilderToPatch,
      applyPendingPublishSettingsBuilderToPatch,
      applyQualityDetailSettingsBuilderToPatch,
      applyQueueSettingsBuilderToPatch,
      applyRuntimeSettingsBuilderToPatch,
      applySettingsBuilderToPatch,
      applySubtitleSettingsBuilderToPatch,
      applyVideoDetailSettingsBuilderToPatch,
      browseSettingsPath,
      markAudioSettingsBuilderDirty,
      markFileSafetySettingsBuilderDirty,
      markFinalLibraryPromotionSettingsBuilderDirty,
      markNetworkSettingsBuilderDirty,
      markPendingPublishSettingsBuilderDirty,
      markQualityDetailSettingsBuilderDirty,
      markQueueSettingsBuilderDirty,
      markRuntimeSettingsBuilderDirty,
      markSettingsBuilderDirty,
      markSettingsPatchTouched,
      markSubtitleSettingsBuilderDirty,
      markVideoDetailSettingsBuilderDirty,
      previewFinalLibraryPromotionSettings,
      previewSettingsPatch,
      renderAudioSettingsBuilderGuidance,
      renderFileSafetySettingsBuilderGuidance,
      renderNetworkSettingsBuilderGuidance,
      renderPendingPublishSettingsBuilderGuidance,
      renderQualityDetailSettingsBuilderGuidance,
      renderQueueSettingsBuilderGuidance,
      renderRuntimeSettingsBuilderGuidance,
      renderSubtitleSettingsBuilderGuidance,
      renderVideoDetailSettingsBuilderGuidance,
      reloadSettingsFromDisk,
      saveFinalLibraryPromotionSettings,
      saveSettingsPatch,
      syncAudioSettingsBuilderFromConfig,
      syncFileSafetySettingsBuilderFromConfig,
      syncFinalLibraryPromotionSettingsBuilderFromConfig,
      syncNetworkSettingsBuilderFromConfig,
      syncPendingPublishSettingsBuilderFromConfig,
      syncQualityDetailSettingsBuilderFromConfig,
      syncQueueSettingsBuilderFromConfig,
      syncRuntimeSettingsBuilderFromConfig,
      syncSettingsBuilderFromConfig,
      syncSubtitleSettingsBuilderFromConfig,
      syncVideoDetailSettingsBuilderFromConfig,
      validateCurrentSettings,
    },
    appendCells,
    audioSettingsBuilderFields,
    audioSettingsBuilderState,
    browseFinalLibraryPromotionRulePath,
    byId,
    clearRows,
    fileSafetySettingsBuilderFields,
    fileSafetySettingsBuilderState,
    finalLibraryPromotionSettingsBuilderState,
    finalLibraryPromotionSettingsBuilderFields,
    formatConfigValue,
    formatSettingsChoiceLabel,
    getCommandHistory: typeof getCommandHistory === "function" ? getCommandHistory : function () { return []; },
    getLastSettings: () => lastSettings,
    getLastSettingsValues: () => lastSettingsValues,
    getSelectedSettingsSaveReviewKey: () => selectedSettingsSaveReviewKey,
    getSettingsBuilderState: () => ({ initialized: settingsBuilderInitialized, dirty: settingsBuilderDirty }),
    getSettingsPatchTouched: () => settingsPatchTouched,
    isSettingsCommand,
    makeRowSelectable,
    parseSettingsPatchJson,
    refreshSettingsBuilderChoices,
    renderSettingsActiveMediaPolicyHandoff,
    renderSettingsBackendResultForError,
    renderSettingsBackendResultFromEntries,
    renderSettingsBackendMediaPolicyReadiness,
    renderSettingsBdpgsOcrPathEvidence,
    renderSettingsVobSubOcrPathEvidence,
    renderSettingsEffectivePolicyTrustForError,
    renderSettingsEffectivePolicyTrustFromEntries,
    renderSettingsLaunchImpactHandoffForError,
    renderSettingsLaunchImpactHandoffFromEntries,
    renderSettingsMediaPolicyCrossCheck,
    renderSettingsOperatorTrust,
    renderSettingsOverview,
    renderSettingsPatchImpactSummaryForError,
    renderSettingsPatchImpactSummaryFromEntries,
    renderSettingsPolicyDeltaForError,
    renderSettingsPolicyDeltaFromEntries,
    renderAllLaunchPreflights: typeof window.renderAllLaunchPreflights === "function" ? window.renderAllLaunchPreflights : function () {},
    renderSettingsRawActionPlan,
    renderSettingsRawTriage,
    renderSettingsRows,
    renderSettingsSafetyLocks,
    refreshAudioSettingsBuilderChoices,
    refreshSettingsSelectChoices,
    runtimeSettingsBuilderFields,
    runtimeSettingsBuilderState,
    setSelectedSettingsSaveReviewKey: (value) => { selectedSettingsSaveReviewKey = value || ""; },
    setSettingsBuilderState: (initialized, dirty) => {
      settingsBuilderInitialized = Boolean(initialized);
      settingsBuilderDirty = Boolean(dirty);
    },
    setSettingsRows,
    setSettingsPatchTouched: (value) => { settingsPatchTouched = Boolean(value); },
    setText,
    settingsBoolValue,
    settingsBuilderConfigValue,
    settingsBuilderFields,
    settingsFieldAllowedValues,
    settingsBuilderInputValue,
    settingsCommandHistoryLine,
    settingsFieldDefinition,
    settingsFriendlyPersistedKeyAliases,
    settingsHasBackendFieldDefinitions,
    settingsPatchComplexBackendKeys,
    settingsPatchImpactEntries,
    settingsPatchCandidateValue,
    settingsPatchListValue,
    settingsRawConfigValue,
    settingsValuesEqual,
    networkSettingsBuilderFields,
    networkSettingsBuilderState,
    pendingPublishSettingsBuilderFields,
    pendingPublishSettingsBuilderState,
    qualityDetailSettingsBuilderFields,
    qualityDetailSettingsBuilderState,
    queueSettingsBuilderFields,
    queueSettingsBuilderState,
    subtitleSettingsBuilderFields,
    subtitleSettingsBuilderState,
    videoDetailSettingsBuilderFields,
    videoDetailSettingsBuilderState,
    updateTableStatusLegend,
  })
  : {};

function settingsPatchReviewCall(name, args, fallback) {
  const fn = settingsPatchReview && settingsPatchReview[name];
  return typeof fn === "function" ? fn(...args) : fallback;
}

function settingsPatchSaveReadinessIssues(entries = []) { return settingsPatchReviewCall("settingsPatchSaveReadinessIssues", [entries], []); }
function settingsPatchSaveReadinessStatus(issues = []) { return settingsPatchReviewCall("settingsPatchSaveReadinessStatus", [issues], "No changes"); }
function settingsSaveReviewRows(entries = []) { return settingsPatchReviewCall("settingsSaveReviewRows", [entries], []); }
function settingsSaveReviewStatus(rows = []) { return settingsPatchReviewCall("settingsSaveReviewStatus", [rows], "No review"); }
function settingsSaveReviewDetailLines(row) { return settingsPatchReviewCall("settingsSaveReviewDetailLines", [row], []); }
function renderSettingsSaveReviewFromEntries(entries = []) { settingsPatchReviewCall("renderSettingsSaveReviewFromEntries", [entries]); }
function renderSettingsPatchSaveReadinessFromEntries(entries = []) { settingsPatchReviewCall("renderSettingsPatchSaveReadinessFromEntries", [entries]); }

function renderSettingsPatchImpactSummaryForError(message) {
  setText(
    "settings-patch-impact-summary",
    `Local impact unavailable because Changes JSON is invalid.\n${message}\nBackend preview cannot run until this is valid JSON.`
  );
}

const settingsPolicyImpactModule = window.__settingsPolicyImpactModule || {};
delete window.__settingsPolicyImpactModule;
settingsPolicyImpact = typeof settingsPolicyImpactModule.createSettingsPolicyImpactModule === "function"
  ? settingsPolicyImpactModule.createSettingsPolicyImpactModule({
    appendCells,
    byId,
    clearRows,
    getCommandHistory: typeof getCommandHistory === "function" ? getCommandHistory : function () { return []; },
    formatConfigValue,
    formatSettingsChoiceLabel,
    formatSettingsListValue,
    getLastSettings: () => lastSettings,
    getLastSettingsValues: () => lastSettingsValues,
    getLastSettingsPatchPreviewEvidence: () => lastSettingsPatchPreviewEvidence,
    getLastSettingsPatchSaveEvidence: () => lastSettingsPatchSaveEvidence,
    getSelectedSettingsEffectivePolicyKey: () => selectedSettingsEffectivePolicyKey,
    makeRowSelectable,
    parseSettingsListText,
    parseSettingsPatchJson,
    setSelectedSettingsEffectivePolicyKey: (value) => { selectedSettingsEffectivePolicyKey = value || ""; },
    settingsBuilderConfigValue,
    settingsBuilderInputValue,
    settingsFieldDefinition,
    settingsImpactGroups,
    settingsRawConfigValue,
    settingsSpecificImpactHints,
    settingsValuesEqual,
    updateTableStatusLegend,
    isSettingsCommand,
    setText,
    settingsCommandHistoryLine,
    settingsPatchSaveReadinessIssues,
    settingsPatchSaveReadinessStatus,
  })
  : {};

function settingsLaunchImpactRows(entries = []) { return settingsPolicyImpactCall("settingsLaunchImpactRows", [entries], []); }
function settingsLaunchImpactStatus(rows = []) { return settingsPolicyImpactCall("settingsLaunchImpactStatus", [rows], "Not evaluated"); }
function settingsLaunchImpactSummaryLines(rows = [], latest = null, issues = []) { return settingsPolicyImpactCall("settingsLaunchImpactSummaryLines", [rows, latest, issues], []); }
function renderSettingsLaunchImpactHandoffFromEntries(entries = []) { settingsPolicyImpactDo("renderSettingsLaunchImpactHandoffFromEntries", [entries]); }
function renderSettingsLaunchImpactHandoffForError(message) { settingsPolicyImpactDo("renderSettingsLaunchImpactHandoffForError", [message]); }
const settingsBackendResultModule = window.__settingsBackendResultModule || {};
delete window.__settingsBackendResultModule;
const settingsBackendResult = typeof settingsBackendResultModule.createSettingsBackendResultModule === "function"
  ? settingsBackendResultModule.createSettingsBackendResultModule({
    appendCells,
    byId,
    clearRows,
    formatConfigValue,
    getLastSettingsPatchPreviewEvidence: () => lastSettingsPatchPreviewEvidence,
    getLastSettingsPatchSaveEvidence: () => lastSettingsPatchSaveEvidence,
    getLastSettingsReloadEvidence: () => lastSettingsReloadEvidence,
    getSelectedSettingsBackendResultKey: () => selectedSettingsBackendResultKey,
    jsonDetailText,
    makeRowSelectable,
    parseSettingsPatchJson,
    renderProgressBarsInto: function () {
      if (typeof window.renderProgressBarsInto === "function") {
        window.renderProgressBarsInto.apply(window, arguments);
      }
    },
    setSelectedSettingsBackendResultKey: (value) => { selectedSettingsBackendResultKey = value || ""; },
    setText,
    settingsCommandHistoryLine,
    settingsCurrentPatchSignature,
    settingsPatchImpactEntries,
    updateTableStatusLegend,
  })
  : {};

/*
 * Static smoke compatibility: settingsView.js remains the settings parent owner
 * while backend-result rendering lives in settings/backendResult.js.
 * Backend media-policy readiness:
 * Save Settings is the only persistence command.
 * Save remains backend-owned.
 * Frontend advisory only; backend Save remains authoritative for source-deletion acceptance and PSD1 writes.
 * Patch JSON changed after the last preview. Save reviews the current values before writing.
 * The last save was for different JSON. Do not treat it as proof for the current patch.
 * Evidence matches current JSON:
 * settings-backend-result-rows
 * settings-backend-result-detail
 */

function settingsBackendResultCall(name, args, fallback) {
  const fn = settingsBackendResult && settingsBackendResult[name];
  return typeof fn === "function" ? fn(...args) : fallback;
}

function settingsCommandProgressBars(result) { return settingsBackendResultCall("settingsCommandProgressBars", [result], []); }
function renderSettingsSaveProgress(result) { settingsBackendResultCall("renderSettingsSaveProgress", [result]); }
function settingsProgressDetailLines(result) { return settingsBackendResultCall("settingsProgressDetailLines", [result], []); }
function settingsBackendResultRowKey(row) { return settingsBackendResultCall("settingsBackendResultRowKey", [row], String(row?.key || row?.signal || "backend-result")); }
function settingsBackendResultRows(entries = []) { return settingsBackendResultCall("settingsBackendResultRows", [entries], []); }
function settingsBackendResultDetailLines(row) { return settingsBackendResultCall("settingsBackendResultDetailLines", [row], []); }
function settingsBackendResultStatus(rows = []) { return settingsBackendResultCall("settingsBackendResultStatus", [rows], "No backend result"); }
function settingsBackendResultSummaryLines(rows = []) { return settingsBackendResultCall("settingsBackendResultSummaryLines", [rows], []); }
function renderSettingsBackendResultFromEntries(entries = []) { settingsBackendResultCall("renderSettingsBackendResultFromEntries", [entries]); }
function renderSettingsBackendResultForError(message) { settingsBackendResultCall("renderSettingsBackendResultForError", [message]); }
function renderSettingsPatchSummary() {
  const fn = settingsPatchReviewFunction("renderSettingsPatchSummary");
  if (fn) fn();
  syncSaveHeaderStatus();
}

function syncSaveHeaderStatus() {
  const patchStatusEl = byId("settings-patch-status");
  const headerPatchEl = byId("settings-save-header-patch-status");
  if (patchStatusEl && headerPatchEl) {
    headerPatchEl.textContent = patchStatusEl.textContent || "No changes";
  }
  const reloaded = lastSettingsPatchSaveEvidence?.result?.data?.reloaded;
  const headerReloadEl = byId("settings-save-header-reload-status");
  if (headerReloadEl) {
    headerReloadEl.textContent = reloaded === true ? "Yes" : reloaded === false ? "No" : "—";
  }
}

function renderSettingsBuilderGuidance() {
  const fn = settingsPatchReviewFunction("renderSettingsBuilderGuidance");
  if (fn) fn();
}

function settingsProfileSummaryLines(settings) {
  const fn = settingsPatchReviewFunction("settingsProfileSummaryLines");
  return fn ? fn(settings) : "No profiles found.";
}

function renderSettings(settings) {
  lastSettings = settings || {};
  const config = lastSettings.config || {};
  lastSettingsValues = { ...config };
  lastSettingsFieldDefinitions = Array.isArray(lastSettings.field_definitions) ? lastSettings.field_definitions : [];
  lastSettingsFieldMap = Object.fromEntries(
    lastSettingsFieldDefinitions
      .filter((field) => field && field.key)
      .map((field) => [String(field.key), field])
  );
  applySettingsFieldMetadataToControls();
  renderSettingsAdvancedControls();
  const fn = settingsPatchReviewFunction("renderSettings");
  if (fn) fn(lastSettings);
  renderSettingsEncoderCapabilityReport(lastSettings);
  applySettingsFieldMetadataToControls();
  renderSettingsAdvancedControls();
}

async function validateCurrentSettings() {
  if (rejectSettingsCommandWhileBusy("settings.validate", "settings-status", "")) return;
  setSettingsCommandBusy(true);
  try {
    const result = await apiPost("/api/settings/validate", { values: lastSettingsValues });
    appendCommandResult(result);
    setText("settings-status", result.message || "Settings validation completed.");
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    appendCommandResult({
      command: "settings.validate",
      ok: false,
      severity: "error",
      message,
    });
    setText("settings-status", `Validation failed: ${message}`);
  } finally {
    setSettingsCommandBusy(false);
  }
}

function appendSettingsRiskSummaryLines(lines, riskSummary) {
  const items = Array.isArray(riskSummary?.items) ? riskSummary.items : [];
  if (!items.length) return;
  const counts = riskSummary.counts || {};
  lines.push(
    "",
    "Risk summary:",
    `Highest severity: ${riskSummary.highest_severity || "unknown"}`,
    `Counts: critical ${counts.critical || 0}, high ${counts.high || 0}, medium ${counts.medium || 0}, low ${counts.low || 0}`
  );
  items.forEach((item) => {
    const key = item.key || "(unknown key)";
    const severity = item.severity || "unknown";
    const code = item.code || "risk";
    const message = item.message || "";
    lines.push(`- [${severity}] ${key} (${code}): ${message}`);
  });
}

  function settingsBuilderFlushFailureMessage(failedBuilders) {
    const names = Array.isArray(failedBuilders) && failedBuilders.length ? failedBuilders.join(", ") : "unknown builder";
    return `Fix invalid Settings builder input before Save Settings. Failed builder(s): ${names}.`;
  }

  function recordSettingsBuilderFlushFailure(command, flushResult) {
    const failedBuilders = Array.isArray(flushResult?.failedBuilders) ? flushResult.failedBuilders : [];
    const message = flushResult?.message || settingsBuilderFlushFailureMessage(failedBuilders);
    const existingDetail = byId("settings-patch-detail")?.textContent || "";
    appendCommandResult({
      command,
      ok: false,
      severity: "error",
      message,
      errors: failedBuilders,
    });
    setText("settings-patch-status", "Builder invalid");
    setText("settings-patch-detail", [message, existingDetail].filter(Boolean).join("\n"));
    renderSettingsPatchSummary();
    if (typeof renderAllLaunchPreflights === "function") renderAllLaunchPreflights();
  }

  function flushDirtySettingsBuilders() {
    // Merge any builder the operator edited (dirty) into the Changes JSON before
    // Save reads it. Without this, toggling a control only marks the builder
    // dirty and the change never reaches the patch that is actually sent to the backend.
    const flushTargets = [
      ["routing and size builder", settingsBuilderDirty, applySettingsBuilderToPatch],
      ["video detail builder", videoDetailSettingsBuilderState.dirty, applyVideoDetailSettingsBuilderToPatch],
      ["quality verification builder", qualityDetailSettingsBuilderState.dirty, applyQualityDetailSettingsBuilderToPatch],
      ["file safety builder", fileSafetySettingsBuilderState.dirty, applyFileSafetySettingsBuilderToPatch],
      ["network builder", networkSettingsBuilderState.dirty, applyNetworkSettingsBuilderToPatch],
      ["queue builder", queueSettingsBuilderState.dirty, applyQueueSettingsBuilderToPatch],
      ["runtime builder", runtimeSettingsBuilderState.dirty, applyRuntimeSettingsBuilderToPatch],
      ["pending publish builder", pendingPublishSettingsBuilderState.dirty, applyPendingPublishSettingsBuilderToPatch],
      ["subtitle builder", subtitleSettingsBuilderState.dirty, applySubtitleSettingsBuilderToPatch],
      ["audio builder", audioSettingsBuilderState.dirty, applyAudioSettingsBuilderToPatch],
    ];
    let flushed = 0;
    const failedBuilders = [];
    flushTargets.forEach(([label, dirty, applyFn]) => {
      if (!dirty || typeof applyFn !== "function") return;
      try {
        const result = applyFn();
        if (result === false) {
          failedBuilders.push(label);
          return;
        }
        flushed += 1;
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        failedBuilders.push(`${label}: ${message}`);
      }
    });
    if (failedBuilders.length) {
      return {
        ok: false,
        flushed,
        failedBuilders,
        message: settingsBuilderFlushFailureMessage(failedBuilders),
      };
    }
    return {
      ok: true,
      flushed,
      failedBuilders: [],
    };
  }

  function resetSettingsBuilderSyncState(options = {}) {
    settingsBuilderInitialized = false;
    settingsBuilderDirty = false;
    [
      videoDetailSettingsBuilderState,
      qualityDetailSettingsBuilderState,
      fileSafetySettingsBuilderState,
      networkSettingsBuilderState,
      queueSettingsBuilderState,
      runtimeSettingsBuilderState,
      pendingPublishSettingsBuilderState,
      subtitleSettingsBuilderState,
      audioSettingsBuilderState,
    ].forEach((state) => {
      state.initialized = false;
      state.dirty = false;
    });
    if (options.includeFinalLibraryPromotion) {
      finalLibraryPromotionSettingsBuilderState.initialized = false;
      finalLibraryPromotionSettingsBuilderState.dirty = false;
    }
  }

  function saveRenameCleaningFiltersFromSettingsSave(message = "Rename filter draft retained in this browser for local recovery.") {
    const releaseGroupsEditor = byId("settings-rename-filter-release-groups");
    const renameView = window.mediaPipelineRenameView || {};
    if (!releaseGroupsEditor || typeof renameView.saveRenameCleaningFilterDraft !== "function") return false;
    return renameView.saveRenameCleaningFilterDraft(message);
  }

  function mergeRenameCleaningFiltersForSave(changes) {
    const releaseGroupsEditor = byId("settings-rename-filter-release-groups");
    const renameView = window.mediaPipelineRenameView || {};
    if (!releaseGroupsEditor || typeof renameView.renameCleaningFilterConfigPatch !== "function") {
      return { changes, included: false, keys: [], draftSaved: false };
    }
    let filterPatch = {};
    try {
      filterPatch = renameView.renameCleaningFilterConfigPatch();
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      return { changes, included: false, keys: [], draftSaved: false, error: message };
    }
    const effectivePatch = {};
    Object.entries(filterPatch).forEach(([key, value]) => {
      const alreadyRequested = Object.prototype.hasOwnProperty.call(changes, key);
      const savedValue = lastSettingsValues ? lastSettingsValues[key] : undefined;
      const differsFromSaved = !Object.prototype.hasOwnProperty.call(lastSettingsValues || {}, key) || !settingsValuesEqual(savedValue, value);
      if (alreadyRequested || differsFromSaved) effectivePatch[key] = value;
    });
    const keys = Object.keys(effectivePatch);
    const draftSaved = keys.length
      ? saveRenameCleaningFiltersFromSettingsSave("Rename filters are included in the current Save Settings review.")
      : false;
    if (!keys.length) return { changes, included: false, keys, draftSaved };
    const nextChanges = { ...changes, ...effectivePatch };
    const patchNode = byId("settings-patch-json");
    if (patchNode) {
      patchNode.value = JSON.stringify(nextChanges, null, 2);
      patchNode.dispatchEvent(new Event("input", { bubbles: true }));
      patchNode.dispatchEvent(new Event("change", { bubbles: true }));
    } else {
      markSettingsPatchTouched();
    }
    renderSettingsPatchSummary();
    if (typeof renderAllLaunchPreflights === "function") renderAllLaunchPreflights();
    return { changes: nextChanges, included: true, keys, draftSaved };
  }

  function settingsSaveReviewValueText(value) {
    if (value === undefined) return "(not previously set)";
    try {
      return formatConfigValue(value) || JSON.stringify(value) || String(value);
    } catch (_) {
      try {
        return JSON.stringify(value);
      } catch {
        return String(value);
      }
    }
  }

  function settingsSaveReviewLabel(key) {
    const field = settingsFieldDefinition(key);
    return settingsFieldLabel(key, field?.label || field?.name || key);
  }

  function appendSettingsSaveReviewCell(row, value) {
    const cell = document.createElement("td");
    cell.textContent = value;
    row.appendChild(cell);
  }

  function renderSettingsSaveReviewDialogRows({ changes, changedKeys, libraryProfileResetCount }) {
    const tbody = byId("settings-save-review-dialog-rows");
    if (!tbody) return;
    tbody.replaceChildren();
    if (!changedKeys.length && !libraryProfileResetCount) {
      const row = document.createElement("tr");
      const cell = document.createElement("td");
      cell.colSpan = 4;
      cell.textContent = "No settings changes to review.";
      row.appendChild(cell);
      tbody.appendChild(row);
      return;
    }
    changedKeys.sort((a, b) => a.localeCompare(b)).forEach((key) => {
      const row = document.createElement("tr");
      const currentExists = lastSettingsValues && Object.prototype.hasOwnProperty.call(lastSettingsValues, key);
      appendSettingsSaveReviewCell(row, settingsSaveReviewLabel(key));
      appendSettingsSaveReviewCell(row, currentExists ? settingsSaveReviewValueText(lastSettingsValues[key]) : "(not previously set)");
      appendSettingsSaveReviewCell(row, settingsSaveReviewValueText(changes[key]));
      appendSettingsSaveReviewCell(row, currentExists ? "Changed" : "New");
      tbody.appendChild(row);
    });
    if (!changedKeys.length && libraryProfileResetCount) {
      const row = document.createElement("tr");
      appendSettingsSaveReviewCell(row, "Library profile reset");
      appendSettingsSaveReviewCell(row, "Current profile overrides");
      appendSettingsSaveReviewCell(row, `${libraryProfileResetCount} reset request(s)`);
      appendSettingsSaveReviewCell(row, "Reset");
      tbody.appendChild(row);
    }
  }

  function openSettingsSaveReviewDialog(options) {
    const dialog = byId("settings-save-review-dialog");
    if (!dialog || typeof dialog.showModal !== "function") {
      setText("settings-patch-status", "Review unavailable");
      setText("settings-patch-detail", "The Save Settings review dialog could not open, so no backend save command was sent.");
      return Promise.resolve(false);
    }
    const {
      changes,
      keys,
      changedKeys,
      libraryProfileResetCount,
      localHintLines,
      renameMerge,
    } = options;
    setText(
      "settings-save-review-summary",
      `Review ${changedKeys.length} value change${changedKeys.length === 1 ? "" : "s"} before writing ${keys.length} submitted key${keys.length === 1 ? "" : "s"} to the active PSD1.`
    );
    setText("settings-save-review-dialog-changed", String(changedKeys.length));
    setText("settings-save-review-dialog-submitted", String(keys.length));
    setText("settings-save-review-dialog-resets", String(libraryProfileResetCount));
    renderSettingsSaveReviewDialogRows({ changes, changedKeys, libraryProfileResetCount });
    const detailLines = [
      "Backend save will validate the current values, write a backup, persist the PSD1, and reload settings after confirmation.",
      settingsRuntimeRestartConfirmationLine(),
    ];
    if (renameMerge?.included) {
      detailLines.push(`Rename filter keys included: ${settingsPersistedKeyDisplayList(renameMerge.keys)}.`);
    }
    if (localHintLines.length) detailLines.push("", ...localHintLines);
    setText("settings-save-review-dialog-detail", detailLines.join("\n"));
    return new Promise((resolve) => {
      const form = dialog.querySelector("form");
      const onSubmit = (event) => {
        event.preventDefault();
        const submitter = event.submitter;
        const value = String(submitter?.value || "cancel");
        dialog.returnValue = value;
        dialog.close(value);
      };
      const onClose = () => {
        dialog.removeEventListener("close", onClose);
        form?.removeEventListener("submit", onSubmit);
        resolve(dialog.returnValue === "confirm");
      };
      dialog.addEventListener("close", onClose);
      form?.addEventListener("submit", onSubmit);
      try {
        dialog.returnValue = "cancel";
        dialog.showModal();
      } catch (error) {
        dialog.removeEventListener("close", onClose);
        form?.removeEventListener("submit", onSubmit);
        const message = error instanceof Error ? error.message : String(error);
        setText("settings-patch-status", "Review unavailable");
        setText("settings-patch-detail", `The Save Settings review dialog could not open: ${message}`);
        resolve(false);
      }
    });
  }

  function settingsRenameLogCaseInput(id) {
    return byId(`settings-rename-log-case-${id}`);
  }

  function settingsRenameLogCaseValue(id) {
    return String(settingsRenameLogCaseInput(id)?.value || "").trim();
  }

  function settingsRenameLogCaseInteger(id, minValue, label) {
    const raw = settingsRenameLogCaseValue(id);
    if (!raw) return { value: null, error: "" };
    if (!/^\d+$/.test(raw)) return { value: null, error: `${label} must be a whole number.` };
    const value = Number.parseInt(raw, 10);
    if (!Number.isFinite(value) || value < minValue) {
      return { value: null, error: `${label} must be ${minValue} or greater.` };
    }
    return { value, error: "" };
  }

  function settingsRenameLogCasePayload() {
    const seasonNumber = settingsRenameLogCaseInteger("season-number", 1, "Season number");
    const expectedSeason = settingsRenameLogCaseInteger("expected-season", 0, "Expected season");
    const expectedShow = settingsRenameLogCaseValue("expected-show");
    const notes = settingsRenameLogCaseValue("notes").replace(/\s+/g, " ");
    const payload = {
      source_folder: settingsRenameLogCaseValue("source-folder"),
      source_file: settingsRenameLogCaseValue("source-file"),
      expected_name: settingsRenameLogCaseValue("expected-name"),
      expected_show: expectedShow,
      status: String(byId("settings-rename-log-case-status-select")?.value || "pending").trim().toLowerCase(),
      confirm_append: true,
    };
    if (seasonNumber.value !== null) payload.season_number = seasonNumber.value;
    if (expectedSeason.value !== null) payload.expected_season = expectedSeason.value;
    if (expectedShow) payload.expected_clean_folder = expectedShow;
    if (notes) payload.notes = notes;
    return { payload, issues: [seasonNumber.error, expectedSeason.error].filter(Boolean) };
  }

  function settingsRenameLogCaseRequiredIssues(payload) {
    const issues = [];
    if (!payload.source_folder) issues.push("Source folder is required.");
    if (!payload.source_file) issues.push("Source file is required.");
    if (!payload.expected_name) issues.push("Expected name is required.");
    if (!["active", "pending"].includes(payload.status)) issues.push("Status must be pending or active.");
    return issues;
  }

  function syncSettingsRenameLogCaseButton() {
    const button = byId("settings-rename-log-case-submit-button");
    if (button) button.disabled = settingsCommandInFlight || settingsRenameLogCaseInFlight;
  }

  function setSettingsRenameLogCaseBusy(isBusy) {
    settingsRenameLogCaseInFlight = Boolean(isBusy);
    syncSettingsRenameLogCaseButton();
  }

  async function submitSettingsRenameLogCase() {
    if (settingsRenameLogCaseInFlight) return;
    if (settingsCommandInFlight) {
      setText("settings-rename-log-case-status", "Busy");
      setText("settings-rename-log-case-message", "Finish the current Settings command before appending a rename filter case.");
      return;
    }
    const renameView = window.mediaPipelineRenameView || {};
    if (typeof renameView.submitRenameBadCasePayload !== "function") {
      setText("settings-rename-log-case-status", "Unavailable");
      setText("settings-rename-log-case-message", "Rename filter case logging is not loaded.");
      return;
    }
    const { payload, issues } = settingsRenameLogCasePayload();
    issues.push(...settingsRenameLogCaseRequiredIssues(payload));
    if (issues.length) {
      setText("settings-rename-log-case-status", "Needs details");
      setText("settings-rename-log-case-message", issues.join(" "));
      return;
    }
    setSettingsRenameLogCaseBusy(true);
    setText("settings-rename-log-case-status", "Appending case...");
    setText("settings-rename-log-case-message", "Appending rename filter case...");
    try {
      const result = await renameView.submitRenameBadCasePayload(payload);
      const message = result?.message || (result?.ok ? "Rename filter case appended." : "Rename filter case was not appended.");
      setText("settings-rename-log-case-status", result?.ok ? "Case appended" : "Append failed");
      setText("settings-rename-log-case-message", message);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setText("settings-rename-log-case-status", "Append failed");
      setText("settings-rename-log-case-message", message);
      appendCommandResult({ command: "rename.filter_case.append", ok: false, severity: "error", message });
    } finally {
      setSettingsRenameLogCaseBusy(false);
    }
  }

  function initSettingsRenameLogCaseEvents() {
    const form = byId("settings-rename-log-case-form");
    if (form && !settingsRenameLogCaseEventsBound) {
      form.addEventListener("submit", (event) => {
        event.preventDefault();
        submitSettingsRenameLogCase();
      });
      settingsRenameLogCaseEventsBound = true;
    }
    syncSettingsRenameLogCaseButton();
  }

  async function previewSettingsPatch() {
    if (rejectSettingsCommandWhileBusy("settings.preview_patch", "settings-patch-status", "settings-patch-detail")) return;
    const flushResult = flushDirtySettingsBuilders();
    if (!flushResult.ok) {
      recordSettingsBuilderFlushFailure("settings.preview_patch", flushResult);
      return;
    }
    const raw = byId("settings-patch-json")?.value || "{}";
    const rawAtRequest = raw;
    markSettingsPatchTouched();
    if (typeof renderAllLaunchPreflights === "function") renderAllLaunchPreflights();
    let changes;
  try {
    changes = JSON.parse(raw);
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    const result = {
      command: "settings.preview_patch",
      ok: false,
      severity: "error",
      message: `Patch JSON is invalid: ${message}`,
    };
    appendCommandResult(result);
    setText("settings-patch-status", "Invalid JSON");
    setText("settings-patch-detail", result.message);
    return;
  }
  if (!changes || Array.isArray(changes) || typeof changes !== "object") {
    const result = {
      command: "settings.preview_patch",
      ok: false,
      severity: "error",
      message: "Patch JSON must be an object of config keys and values.",
    };
    appendCommandResult(result);
    setText("settings-patch-status", "Invalid patch");
    setText("settings-patch-detail", result.message);
    return;
  }
  const requestExtras = settingsPatchRequestExtras();
  const requestSignature = settingsPatchRequestSignature(changes, requestExtras);
  const localHintLines = settingsPatchLocalValidationHintLines(changes);
  setSettingsCommandBusy(true);
  setText("settings-patch-status", "Previewing...");
  setText("settings-patch-detail", [
    "Requesting backend patch preview. This will not save the PSD1.",
    ...localHintLines,
  ].join("\n"));
  const requestId = ++settingsPatchPreviewRequestId;
  try {
    const result = await apiPost("/api/settings/preview-patch", { changes, ...requestExtras });
    if (requestId !== settingsPatchPreviewRequestId) return;
    if ((byId("settings-patch-json")?.value || "{}") !== rawAtRequest) {
      setText("settings-patch-status", "Preview replaced");
      setText("settings-patch-detail", "Patch JSON changed before the backend preview returned. Save will review the current values before writing.");
      return;
    }
    appendCommandResult(result);
    lastSettingsPatchPreviewEvidence = {
      signature: requestSignature,
      command: "settings.preview_patch",
      result,
      captured_at: new Date().toISOString(),
    };
    setText("settings-patch-status", settingsResultStatusLabel(result, "Preview ready", "Preview failed"));
    const data = result.data || {};
    const lines = [
      result.message || "Settings patch preview completed.",
      "",
      `Writes config: ${data.writes_config === true ? "yes" : "no"}`,
      `Active preset: ${byId("settings-handbrake-active-preset")?.textContent || "Saved settings"}`,
      "Preset scope: display/preset adapters only; backend save writes stable persisted keys.",
      `Changed keys: ${settingsPersistedKeyDisplayList(data.changed_keys || []) || "none"}`,
      `Removed keys: ${settingsPersistedKeyDisplayList(data.removed_keys || []) || "none"}`,
      "Preview/save uses persisted keys. Friendly labels are display only and are not saved keys.",
    ];
    if (localHintLines.length) lines.push("", ...localHintLines);
    if ((result.errors || []).length) {
      lines.push("", "Errors:", ...(result.errors || []).map((item) => `- ${item}`));
      lines.push("Backend validation errors are authoritative; this WebView did not save or bypass them.");
    }
    if ((result.warnings || []).length) {
      lines.push("", "Warnings:", ...(result.warnings || []).map((item) => `- ${item}`));
    }
    appendSettingsRiskSummaryLines(lines, data.risk_summary);
    if ((data.redacted_diff_lines || []).length) {
      lines.push("", "Redacted diff:", ...(data.redacted_diff_lines || []));
      if (data.diff_truncated) lines.push("...diff truncated...");
    }
    setText("settings-patch-detail", lines.join("\n"));
    renderSettingsPatchSummary();
  } catch (error) {
    if (requestId !== settingsPatchPreviewRequestId) return;
    if ((byId("settings-patch-json")?.value || "{}") !== rawAtRequest) {
      setText("settings-patch-status", "Preview replaced");
      setText("settings-patch-detail", "Patch JSON changed before the backend preview returned. Save will review the current values before writing.");
      return;
    }
    const message = error instanceof Error ? error.message : String(error);
    const result = {
      command: "settings.preview_patch",
      ok: false,
      severity: "error",
      message,
    };
    appendCommandResult(result);
    lastSettingsPatchPreviewEvidence = {
      signature: requestSignature,
      command: "settings.preview_patch",
      result,
      captured_at: new Date().toISOString(),
    };
    setText("settings-patch-status", "Preview failed");
    setText("settings-patch-detail", message);
    renderSettingsPatchSummary();
  } finally {
    if (requestId === settingsPatchPreviewRequestId) setSettingsCommandBusy(false);
  }
}

async function saveSettingsPatch() {
  if (rejectSettingsCommandWhileBusy("settings.save_patch", "settings-patch-status", "settings-patch-detail")) return;
  const flushResult = flushDirtySettingsBuilders();
  if (!flushResult.ok) {
    recordSettingsBuilderFlushFailure("settings.save_patch", flushResult);
    return;
  }
  const raw = byId("settings-patch-json")?.value || "{}";
  markSettingsPatchTouched();
  if (typeof renderAllLaunchPreflights === "function") renderAllLaunchPreflights();
  let changes;
  try {
    changes = JSON.parse(raw);
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    appendCommandResult({
      command: "settings.save_patch",
      ok: false,
      severity: "error",
      message: `Patch JSON is invalid: ${message}`,
    });
    setText("settings-patch-status", "Invalid JSON");
    setText("settings-patch-detail", `Patch JSON is invalid: ${message}`);
    return;
  }
  if (!changes || Array.isArray(changes) || typeof changes !== "object") {
    const message = "Patch JSON must be an object of config keys and values.";
    appendCommandResult({
      command: "settings.save_patch",
      ok: false,
      severity: "error",
      message,
    });
    setText("settings-patch-status", "Invalid patch");
    setText("settings-patch-detail", message);
    return;
  }
  const renameMerge = mergeRenameCleaningFiltersForSave(changes);
  if (renameMerge.error) {
    const message = `Rename filter values could not be prepared for save: ${renameMerge.error}`;
    appendCommandResult({
      command: "settings.save_patch",
      ok: false,
      severity: "error",
      message,
    });
    setText("settings-patch-status", "Rename filters invalid");
    setText("settings-patch-detail", message);
    return;
  }
  changes = renameMerge.changes;
  const requestExtras = settingsPatchRequestExtras();
  const libraryProfileResetCount = Array.isArray(requestExtras.library_profile_resets) ? requestExtras.library_profile_resets.length : 0;
  const hasLibraryProfileResets = libraryProfileResetCount > 0;
  const keys = Object.keys(changes);
  if (!keys.length && !hasLibraryProfileResets) {
    setText("settings-patch-status", "No changes");
    setText("settings-patch-detail", [
      renameMerge.draftSaved ? "Rename filter draft retained in this browser for local recovery." : "",
      "No backend settings change keys were provided, so the PSD1 was not changed.",
    ].filter(Boolean).join("\n"));
    return;
  }
  const signature = settingsPatchRequestSignature(changes, requestExtras);
  const localHintLines = settingsPatchLocalValidationHintLines(changes);
  const keyChanged = (key) => {
    if (!lastSettingsValues || !Object.prototype.hasOwnProperty.call(lastSettingsValues, key)) return true;
    return !settingsValuesEqual(lastSettingsValues[key], changes[key]);
  };
  const changedKeys = keys.filter(keyChanged);
  if (!changedKeys.length && !hasLibraryProfileResets) {
    setText("settings-patch-status", "No changes");
    setText("settings-patch-detail", [
      renameMerge.draftSaved ? "Rename filter draft retained in this browser for local recovery." : "",
      "No settings differ from the saved config, so nothing was saved.",
      "Edit a setting on any tab (subtitle / audio / routing / etc.), then Save again.",
      "Builder edits are gathered automatically when you Save.",
    ].join("\n"));
    renderSettingsPatchSummary();
    if (typeof renderAllLaunchPreflights === "function") renderAllLaunchPreflights();
    return;
  }
  const confirmed = await openSettingsSaveReviewDialog({
    changes,
    keys,
    changedKeys,
    libraryProfileResetCount,
    localHintLines,
    renameMerge,
  });
  if (!confirmed) {
    selectedSettingsBackendResultKey = "save-confirmation-boundary";
    setText("settings-patch-status", "Save cancelled");
    setText("settings-patch-detail", [
      "Save Settings was cancelled before any backend save command was sent.",
      "No config backup was created, no PSD1 file was written, and the current edits remain available.",
      "Launch still uses saved backend settings only; press Save Settings again when ready.",
    ].join("\n"));
    renderSettingsPatchSummary();
    if (typeof renderAllLaunchPreflights === "function") renderAllLaunchPreflights();
    return;
  }
  const snapshotBefore = {};
  changedKeys.forEach((key) => {
    if (lastSettingsValues && Object.prototype.hasOwnProperty.call(lastSettingsValues, key)) {
      snapshotBefore[key] = lastSettingsValues[key];
    }
  });
  setSettingsCommandBusy(true);
  setText("settings-patch-status", "Saving...");
  setText("settings-patch-detail", [
    "Saving backend-validated settings changes to the active PSD1. A backup will be created first.",
    ...localHintLines,
  ].join("\n"));
  try {
    const result = await apiPost("/api/settings/save-patch", { changes, ...requestExtras, confirm_save: true });
    appendCommandResult(result);
    lastSettingsPatchSaveEvidence = {
      signature,
      command: "settings.save_patch",
      result,
      changes: settingsStableJsonValue(changes),
      snapshot_before: snapshotBefore,
      captured_at: new Date().toISOString(),
    };
    setText("settings-patch-status", settingsResultStatusLabel(result, "Saved", "Save failed"));
    const data = result.data || {};
    const lines = [
      result.message || "Settings save completed.",
      "",
      `Writes config: ${data.writes_config === true ? "yes" : "no"}`,
      `Config: ${data.config_path || ""}`,
      `Backup: ${data.backup_path || ""}`,
      `Reloaded: ${data.reloaded === true ? "yes" : data.reloaded === false ? "no" : "n/a"}`,
      `Active preset: ${byId("settings-handbrake-active-preset")?.textContent || "Saved settings"}`,
      "Preset scope: display/preset adapters only; backend save writes stable persisted keys.",
      `Changed keys: ${settingsPersistedKeyDisplayList(data.changed_keys || []) || "none"}`,
      `Removed keys: ${settingsPersistedKeyDisplayList(data.removed_keys || []) || "none"}`,
      "Save uses persisted keys. Friendly labels are display only and are not saved keys.",
    ];
    if (localHintLines.length) lines.push("", ...localHintLines);
    if (result.ok) {
      lines.push("", ...settingsRuntimeRestartNoticeLines(result));
    }
    if ((result.errors || []).length) {
      lines.push("", "Errors:", ...(result.errors || []).map((item) => `- ${item}`));
      lines.push("Backend validation errors are authoritative; this WebView did not save or bypass them.");
    }
    if ((result.warnings || []).length) {
      lines.push("", "Warnings:", ...(result.warnings || []).map((item) => `- ${item}`));
    }
    appendSettingsRiskSummaryLines(lines, data.risk_summary);
    if ((data.redacted_diff_lines || []).length) {
      lines.push("", "Redacted diff:", ...(data.redacted_diff_lines || []));
      if (data.diff_truncated) lines.push("...diff truncated...");
    }
    if (result.ok && Object.keys(snapshotBefore).length) {
      lines.push("", "Overwrite record (values replaced by this save):");
      Object.keys(snapshotBefore).sort().forEach((key) => {
        lines.push(`  ${key}: ${JSON.stringify(snapshotBefore[key])} -> ${JSON.stringify(changes[key])}`);
      });
      if (data.backup_path) lines.push(`  Backup: ${data.backup_path}`);
    }
    setText("settings-patch-detail", lines.join("\n"));
    renderSettingsPatchSummary();
    maybeShowSettingsRuntimeRestartNotice(result);
    if (result.ok) {
      resetSettingsBuilderSyncState();
      await refreshAll();
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    const result = {
      command: "settings.save_patch",
      ok: false,
      severity: "error",
      message,
    };
    appendCommandResult(result);
    lastSettingsPatchSaveEvidence = {
      signature,
      command: "settings.save_patch",
      result,
      captured_at: new Date().toISOString(),
    };
    setText("settings-patch-status", "Save failed");
    setText("settings-patch-detail", message);
    renderSettingsPatchSummary();
  } finally {
    setSettingsCommandBusy(false);
  }
}

async function reloadSettingsFromDisk() {
  if (rejectSettingsCommandWhileBusy("settings.reload", "settings-status", "")) return;
  setSettingsCommandBusy(true);
  setText("settings-status", "Reloading...");
  try {
    const result = await apiPost("/api/settings/reload", {});
    appendCommandResult(result);
    lastSettingsReloadEvidence = {
      command: "settings.reload",
      result,
      captured_at: new Date().toISOString(),
    };
    setText("settings-status", result.message || "Settings reload completed.");
    renderSettingsPatchSummary();
    if (result.ok) {
      resetSettingsBuilderSyncState({ includeFinalLibraryPromotion: true });
      await refreshAll();
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    appendCommandResult({
      command: "settings.reload",
      ok: false,
      severity: "error",
      message,
    });
    lastSettingsReloadEvidence = {
      command: "settings.reload",
      result: {
        command: "settings.reload",
        ok: false,
        severity: "error",
        message,
      },
      captured_at: new Date().toISOString(),
    };
    setText("settings-status", `Reload failed: ${message}`);
    renderSettingsPatchSummary();
  } finally {
    setSettingsCommandBusy(false);
  }
}

  function getLastSettings() {
    return lastSettings || {};
  }

  function settingsBrowsePathDetailLines(result, fieldLabel) {
    const data = result?.data && typeof result.data === "object" ? result.data : {};
    const validation = data.validation && typeof data.validation === "object" ? data.validation : {};
    const lines = [
      result?.message || `Settings folder browse returned for ${fieldLabel}.`,
      validation.message ? `Validation: ${validation.message}` : "Validation: no selected-folder evidence returned.",
      `Writes config: ${data.writes_config === true ? "yes" : "no"}`,
      `Save candidate only: ${data.stages_only === true ? "yes" : "no"}`,
      "Next step: Save Settings. Launch uses saved backend settings only.",
      "Mutation guardrail: this route only opens a backend-owned Windows folder picker and prepares one allowlisted Settings field. It cannot save settings, launch work, rewrite queue state, publish, rename, delete, or touch media files.",
    ];
    if (data.selected_path) lines.splice(1, 0, `Selected path: ${data.selected_path}`);
    return lines;
  }

  async function browseSettingsPath(settingKey, inputId) {
    if (rejectSettingsCommandWhileBusy("settings.browse_path", "settings-file-safety-builder-status", "settings-file-safety-guidance")) return;
    const input = byId(inputId);
    const field = settingsFieldDefinition(settingKey);
    const fieldLabel = field?.label || settingKey;
    const initialPath = input?.value || settingsBuilderConfigValue(settingKey, "");
    setSettingsCommandBusy(true);
    setText("settings-file-safety-builder-status", `Opening ${fieldLabel} folder browser...`);
    setText(
      "settings-file-safety-guidance",
      [
        `Opening backend-owned Windows folder browser for ${fieldLabel}.`,
        "No Settings file will be saved by this action.",
        "Use Save Settings to review and write the prepared File Safety change.",
      ].join("\n")
    );
    try {
      const result = await apiPost(
        "/api/settings/browse-path",
        { setting_key: settingKey, selection_mode: "folder", initial_path: initialPath },
        { timeoutMs: 15 * 60 * 1000 }
      );
      appendCommandResult(result);
      const data = result?.data && typeof result.data === "object" ? result.data : {};
      const validation = data.validation && typeof data.validation === "object" ? data.validation : {};
      const selectedPath = String(data.selected_path || "");
      if (result.ok && !data.canceled && selectedPath && validation.status_state === "ready" && input) {
        input.value = selectedPath;
        markFileSafetySettingsBuilderDirty();
        setText("settings-file-safety-builder-status", `${fieldLabel} path ready`);
      } else if (data.canceled) {
        setText("settings-file-safety-builder-status", "Folder browse canceled");
      } else {
        setText("settings-file-safety-builder-status", result.ok ? "Folder browse needs review" : "Folder browse failed");
      }
      setText("settings-file-safety-guidance", settingsBrowsePathDetailLines(result, fieldLabel).join("\n"));
      renderSettingsActiveMediaPolicyHandoff();
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      const result = {
        command: "settings.browse_path",
        ok: false,
        severity: "error",
        message,
      };
      appendCommandResult(result);
      setText("settings-file-safety-builder-status", "Folder browse failed");
      setText("settings-file-safety-guidance", settingsBrowsePathDetailLines(result, fieldLabel).join("\n"));
    } finally {
      setSettingsCommandBusy(false);
    }
  }

  function initSettingsViewEvents() {
    const fn = settingsPatchReviewFunction("initSettingsViewEvents");
    if (fn) fn();
    initSettingsRenameLogCaseEvents();
    if (!settingsAdvancedToggleEventsBound) {
      document.addEventListener("click", handleSettingsAdvancedToggleClick);
      settingsAdvancedToggleEventsBound = true;
    }
  }

  /**
   * Public namespace for the settings view module.
   * Prefer this namespace from new code; flat window.* exports are transitional compatibility aliases when present.
   */
  window.mediaPipelineSettingsView = {
    configValue, buildSettingsOverviewRows, renderSettingsOverview, setSettingsRows, renderSettingsRows, settingsBuilderCoveredKeys,
    settingsRawTriageRows, settingsRawTriageStatus, settingsRawTriageSummaryLines, settingsRawTriageDetailLines, renderSettingsRawTriage,
    settingsRawActionPlanRows, settingsRawActionPlanStatus, settingsRawActionPlanSummaryLines, settingsRawActionPlanDetailLines, renderSettingsRawActionPlan,
    settingsSafetyLockRows, settingsSafetyLockStatus, settingsSafetyLockSummaryLines, renderSettingsSafetyLocks,
    renderSettings, getLastSettings, validateCurrentSettings, reloadSettingsFromDisk, browseSettingsPath, settingsBrowsePathDetailLines,
    setSettingsCommandBusy, rejectSettingsCommandWhileBusy, previewSettingsPatch, saveSettingsPatch, isSettingsCommand, settingsCommandHistoryLine, renderSettingsCommandHistory,
    settingsPatchLocalValidationHints, settingsPatchLocalValidationHintLines,
    renderSettingsPatchSummary, settingsPatchImpactEntries, renderSettingsPatchImpactSummaryFromEntries, settingsPatchSaveReadinessIssues, settingsPatchSaveReadinessStatus, renderSettingsPatchSaveReadinessFromEntries,
    settingsPolicyDeltaRows, settingsPolicyDeltaStatus, settingsPolicyDeltaSummaryLines, renderSettingsPolicyDeltaFromEntries,
    settingsEffectivePolicyRows, settingsEffectivePolicyTrustStatus, settingsEffectivePolicySummaryLines, settingsEffectivePolicyDetailLines, renderSettingsEffectivePolicyTrustFromEntries, renderSettingsEffectivePolicyTrustForError,
    settingsSaveReviewRows, settingsSaveReviewStatus, settingsSaveReviewDetailLines, renderSettingsSaveReviewFromEntries,
    settingsLaunchImpactRows, settingsLaunchImpactStatus, settingsLaunchImpactSummaryLines, renderSettingsLaunchImpactHandoffFromEntries,
    markSettingsPatchTouched, settingsPatchIsTouched, settingsPatchEffectiveChangedEntries, settingsPatchHasUnsavedChanges, settingsStableJsonValue, settingsPatchSignature, settingsCurrentPatchSignature,
    syncSettingsBuilderFromConfig, collectSettingsBuilderPatch, applySettingsBuilderToPatch, refreshSettingsBuilderChoices, renderSettingsBuilderGuidance, markSettingsBuilderDirty,
    syncVideoDetailSettingsBuilderFromConfig, collectVideoDetailSettingsBuilderPatch, applyVideoDetailSettingsBuilderToPatch, renderVideoDetailSettingsBuilderGuidance, markVideoDetailSettingsBuilderDirty,
    settingsEncoderCapabilityReport, settingsEncoderCapabilityStatus, settingsEncoderCapabilitySummaryLines, renderSettingsEncoderCapabilityReport,
    syncQualityDetailSettingsBuilderFromConfig, collectQualityDetailSettingsBuilderPatch, applyQualityDetailSettingsBuilderToPatch, renderQualityDetailSettingsBuilderGuidance, markQualityDetailSettingsBuilderDirty,
    syncFileSafetySettingsBuilderFromConfig, collectFileSafetySettingsBuilderPatch, applyFileSafetySettingsBuilderToPatch, renderFileSafetySettingsBuilderGuidance, markFileSafetySettingsBuilderDirty,
    syncNetworkSettingsBuilderFromConfig, collectNetworkSettingsBuilderPatch, applyNetworkSettingsBuilderToPatch, renderNetworkSettingsBuilderGuidance, markNetworkSettingsBuilderDirty,
    syncQueueSettingsBuilderFromConfig, collectQueueSettingsBuilderPatch, applyQueueSettingsBuilderToPatch, renderQueueSettingsBuilderGuidance, markQueueSettingsBuilderDirty,
    syncRuntimeSettingsBuilderFromConfig, collectRuntimeSettingsBuilderPatch, applyRuntimeSettingsBuilderToPatch, renderRuntimeSettingsBuilderGuidance, markRuntimeSettingsBuilderDirty,
    syncPendingPublishSettingsBuilderFromConfig, collectPendingPublishSettingsBuilderPatch, applyPendingPublishSettingsBuilderToPatch, renderPendingPublishSettingsBuilderGuidance, markPendingPublishSettingsBuilderDirty,
    syncFinalLibraryPromotionSettingsBuilderFromConfig, collectFinalLibraryPromotionSettingsPatch, previewFinalLibraryPromotionSettings, saveFinalLibraryPromotionSettings, renderFinalLibraryPromotionSettingsGuidance, markFinalLibraryPromotionSettingsBuilderDirty,
    syncSubtitleSettingsBuilderFromConfig, collectSubtitleSettingsBuilderPatch, applySubtitleSettingsBuilderToPatch, renderSubtitleSettingsBuilderGuidance, settingsBdpgsOcrPathEvidence, settingsBdpgsOcrPathEvidenceStatus, settingsBdpgsOcrPathEvidenceLines, renderSettingsBdpgsOcrPathEvidence, settingsVobSubOcrPathEvidence, settingsVobSubOcrPathEvidenceStatus, settingsVobSubOcrPathEvidenceLines, renderSettingsVobSubOcrPathEvidence,
    syncAudioSettingsBuilderFromConfig, collectAudioSettingsBuilderPatch, applyAudioSettingsBuilderToPatch, renderAudioSettingsBuilderGuidance,
    settingsMediaPolicyRows, settingsMediaPolicyStatus, settingsMediaPolicySummaryLines, renderSettingsMediaPolicyCrossCheck, settingsBackendPolicyImpact, settingsBackendMediaPolicyReadiness, settingsBackendMediaPolicyStatus, settingsBackendMediaPolicySummaryLines, renderSettingsBackendMediaPolicyReadiness,
    settingsActiveMediaPolicyRows, settingsActiveMediaPolicyStatus, settingsActiveMediaPolicySummaryLines, renderSettingsActiveMediaPolicyHandoff,
    settingsBackendResultRows, settingsBackendResultRowKey, settingsCommandProgressBars, renderSettingsSaveProgress, settingsProgressDetailLines, settingsBackendResultDetailLines, settingsBackendResultStatus, settingsBackendResultSummaryLines, renderSettingsBackendResultFromEntries, renderSettingsBackendResultForError,
    settingsRuntimeState, settingsRuntimeRestartWarningNeeded, settingsRuntimeRestartConfirmationLine, settingsRuntimeRestartNoticeLines, maybeShowSettingsRuntimeRestartNotice,
    settingsRenameLogCasePayload, submitSettingsRenameLogCase, initSettingsRenameLogCaseEvents,
    writeSettingsPatchJson, parseSettingsPatchJson, initSettingsViewEvents,
  };
  window.configValue = configValue; window.buildSettingsOverviewRows = buildSettingsOverviewRows; window.renderSettingsOverview = renderSettingsOverview; window.setSettingsRows = setSettingsRows;
  window.renderSettingsRows = renderSettingsRows; window.settingsBuilderCoveredKeys = settingsBuilderCoveredKeys; window.settingsRawTriageRows = settingsRawTriageRows; window.settingsRawTriageStatus = settingsRawTriageStatus;
  window.settingsRawTriageSummaryLines = settingsRawTriageSummaryLines; window.settingsRawTriageDetailLines = settingsRawTriageDetailLines; window.renderSettingsRawTriage = renderSettingsRawTriage; window.settingsRawActionPlanRows = settingsRawActionPlanRows;
  window.settingsRawActionPlanStatus = settingsRawActionPlanStatus; window.settingsRawActionPlanSummaryLines = settingsRawActionPlanSummaryLines; window.settingsRawActionPlanDetailLines = settingsRawActionPlanDetailLines; window.renderSettingsRawActionPlan = renderSettingsRawActionPlan;
  window.settingsSafetyLockRows = settingsSafetyLockRows; window.settingsSafetyLockStatus = settingsSafetyLockStatus; window.settingsSafetyLockSummaryLines = settingsSafetyLockSummaryLines; window.renderSettingsSafetyLocks = renderSettingsSafetyLocks;
  window.renderSettings = renderSettings; window.getLastSettings = getLastSettings;
  window.settingsPatchLocalValidationHints = settingsPatchLocalValidationHints; window.settingsPatchLocalValidationHintLines = settingsPatchLocalValidationHintLines;
  window.settingsPolicyDeltaRows = settingsPolicyDeltaRows; window.settingsPolicyDeltaStatus = settingsPolicyDeltaStatus; window.settingsLaunchImpactRows = settingsLaunchImpactRows; window.settingsLaunchImpactStatus = settingsLaunchImpactStatus;
  window.settingsPatchIsTouched = settingsPatchIsTouched; window.settingsPatchEffectiveChangedEntries = settingsPatchEffectiveChangedEntries; window.syncVideoDetailSettingsBuilderFromConfig = syncVideoDetailSettingsBuilderFromConfig; window.collectVideoDetailSettingsBuilderPatch = collectVideoDetailSettingsBuilderPatch;
  window.applyVideoDetailSettingsBuilderToPatch = applyVideoDetailSettingsBuilderToPatch; window.renderVideoDetailSettingsBuilderGuidance = renderVideoDetailSettingsBuilderGuidance; window.markVideoDetailSettingsBuilderDirty = markVideoDetailSettingsBuilderDirty; window.syncFileSafetySettingsBuilderFromConfig = syncFileSafetySettingsBuilderFromConfig;
  window.syncQualityDetailSettingsBuilderFromConfig = syncQualityDetailSettingsBuilderFromConfig; window.collectQualityDetailSettingsBuilderPatch = collectQualityDetailSettingsBuilderPatch; window.applyQualityDetailSettingsBuilderToPatch = applyQualityDetailSettingsBuilderToPatch; window.renderQualityDetailSettingsBuilderGuidance = renderQualityDetailSettingsBuilderGuidance; window.markQualityDetailSettingsBuilderDirty = markQualityDetailSettingsBuilderDirty;
  window.collectFileSafetySettingsBuilderPatch = collectFileSafetySettingsBuilderPatch; window.applyFileSafetySettingsBuilderToPatch = applyFileSafetySettingsBuilderToPatch; window.renderFileSafetySettingsBuilderGuidance = renderFileSafetySettingsBuilderGuidance; window.markFileSafetySettingsBuilderDirty = markFileSafetySettingsBuilderDirty;
  window.syncNetworkSettingsBuilderFromConfig = syncNetworkSettingsBuilderFromConfig; window.collectNetworkSettingsBuilderPatch = collectNetworkSettingsBuilderPatch; window.applyNetworkSettingsBuilderToPatch = applyNetworkSettingsBuilderToPatch; window.renderNetworkSettingsBuilderGuidance = renderNetworkSettingsBuilderGuidance; window.markNetworkSettingsBuilderDirty = markNetworkSettingsBuilderDirty;
  window.syncQueueSettingsBuilderFromConfig = syncQueueSettingsBuilderFromConfig; window.collectQueueSettingsBuilderPatch = collectQueueSettingsBuilderPatch; window.applyQueueSettingsBuilderToPatch = applyQueueSettingsBuilderToPatch; window.renderQueueSettingsBuilderGuidance = renderQueueSettingsBuilderGuidance; window.markQueueSettingsBuilderDirty = markQueueSettingsBuilderDirty;
  window.syncRuntimeSettingsBuilderFromConfig = syncRuntimeSettingsBuilderFromConfig; window.collectRuntimeSettingsBuilderPatch = collectRuntimeSettingsBuilderPatch; window.applyRuntimeSettingsBuilderToPatch = applyRuntimeSettingsBuilderToPatch; window.renderRuntimeSettingsBuilderGuidance = renderRuntimeSettingsBuilderGuidance; window.markRuntimeSettingsBuilderDirty = markRuntimeSettingsBuilderDirty;
  window.syncPendingPublishSettingsBuilderFromConfig = syncPendingPublishSettingsBuilderFromConfig; window.collectPendingPublishSettingsBuilderPatch = collectPendingPublishSettingsBuilderPatch; window.applyPendingPublishSettingsBuilderToPatch = applyPendingPublishSettingsBuilderToPatch; window.renderPendingPublishSettingsBuilderGuidance = renderPendingPublishSettingsBuilderGuidance; window.markPendingPublishSettingsBuilderDirty = markPendingPublishSettingsBuilderDirty;
  window.syncFinalLibraryPromotionSettingsBuilderFromConfig = syncFinalLibraryPromotionSettingsBuilderFromConfig; window.collectFinalLibraryPromotionSettingsPatch = collectFinalLibraryPromotionSettingsPatch; window.previewFinalLibraryPromotionSettings = previewFinalLibraryPromotionSettings; window.saveFinalLibraryPromotionSettings = saveFinalLibraryPromotionSettings;
  window.renderFinalLibraryPromotionSettingsGuidance = renderFinalLibraryPromotionSettingsGuidance; window.markFinalLibraryPromotionSettingsBuilderDirty = markFinalLibraryPromotionSettingsBuilderDirty; window.syncSubtitleSettingsBuilderFromConfig = syncSubtitleSettingsBuilderFromConfig; window.collectSubtitleSettingsBuilderPatch = collectSubtitleSettingsBuilderPatch;
  window.applySubtitleSettingsBuilderToPatch = applySubtitleSettingsBuilderToPatch; window.renderSubtitleSettingsBuilderGuidance = renderSubtitleSettingsBuilderGuidance; window.settingsBdpgsOcrPathEvidence = settingsBdpgsOcrPathEvidence; window.settingsBdpgsOcrPathEvidenceStatus = settingsBdpgsOcrPathEvidenceStatus;
  window.settingsBdpgsOcrPathEvidenceLines = settingsBdpgsOcrPathEvidenceLines; window.renderSettingsBdpgsOcrPathEvidence = renderSettingsBdpgsOcrPathEvidence; window.settingsVobSubOcrPathEvidence = settingsVobSubOcrPathEvidence; window.settingsVobSubOcrPathEvidenceStatus = settingsVobSubOcrPathEvidenceStatus;
  window.settingsVobSubOcrPathEvidenceLines = settingsVobSubOcrPathEvidenceLines; window.renderSettingsVobSubOcrPathEvidence = renderSettingsVobSubOcrPathEvidence; window.markSubtitleSettingsBuilderDirty = markSubtitleSettingsBuilderDirty; window.syncAudioSettingsBuilderFromConfig = syncAudioSettingsBuilderFromConfig;
  window.collectAudioSettingsBuilderPatch = collectAudioSettingsBuilderPatch; window.applyAudioSettingsBuilderToPatch = applyAudioSettingsBuilderToPatch; window.renderAudioSettingsBuilderGuidance = renderAudioSettingsBuilderGuidance; window.markAudioSettingsBuilderDirty = markAudioSettingsBuilderDirty;
  window.renderSettingsMediaPolicyCrossCheck = renderSettingsMediaPolicyCrossCheck; window.writeSettingsPatchJson = writeSettingsPatchJson; window.initSettingsViewEvents = initSettingsViewEvents;
  window.settingsRuntimeRestartConfirmationLine = settingsRuntimeRestartConfirmationLine; window.settingsRuntimeRestartNoticeLines = settingsRuntimeRestartNoticeLines;

  (function () {
    const saveBtn = byId("settings-save-header-save-button");
    if (saveBtn) saveBtn.addEventListener("click", saveSettingsPatch);
    const reloadBtn = byId("settings-save-header-reload-button");
    if (reloadBtn) reloadBtn.addEventListener("click", reloadSettingsFromDisk);
  }());
})();
