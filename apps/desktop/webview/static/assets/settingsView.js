(function () {
  const settingsOverview = window.mediaPipelineSettingsOverview || {};
  const configValue = settingsOverview.configValue || function () { return "(not set)"; };
  const buildSettingsOverviewRows = settingsOverview.buildSettingsOverviewRows || function () { return []; };
  const renderSettingsOverview = settingsOverview.renderSettingsOverview || function () {};
  const renderSettingsOperatorTrust = settingsOverview.renderSettingsOperatorTrust || function () {};
  const settingsCommandHistory = window.mediaPipelineSettingsCommandHistory || {};
  const isSettingsCommand = settingsCommandHistory.isSettingsCommand || function () { return false; };
  const settingsCommandHistoryLine = settingsCommandHistory.settingsCommandHistoryLine || function () { return ""; };
  const renderSettingsCommandHistory = settingsCommandHistory.renderSettingsCommandHistory || function () {};
  const domHelpers = window.mediaPipelineDom || {};
  const formatters = window.mediaPipelineFormatters || {};
  const formatConfigValue = typeof formatters.formatConfigValue === "function"
    ? formatters.formatConfigValue
    : function (value) {
      if (Array.isArray(value)) return value.join(", ");
      if (value && typeof value === "object") return JSON.stringify(value);
      if (value === null || value === undefined) return "";
      return String(value);
    };
  const parseSettingsListText = typeof formatters.parseSettingsListText === "function"
    ? formatters.parseSettingsListText
    : function (raw) {
      return String(raw || "").split(/[\n,;]+/).map((item) => item.trim()).filter(Boolean);
    };
  const formatSettingsListValue = typeof formatters.formatSettingsListValue === "function"
    ? formatters.formatSettingsListValue
    : function (value) {
      if (Array.isArray(value)) return value.join(", ");
      if (value === undefined || value === null) return "";
      return String(value);
    };
  const settingsValuesEqual = typeof formatters.settingsValuesEqual === "function"
    ? formatters.settingsValuesEqual
    : function (left, right) {
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
const SETTINGS_PREVIEW_POST_TIMEOUT_MS = 60000;
const SETTINGS_SAVE_POST_TIMEOUT_MS = 120000;

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

function scheduleSettingsPostSaveRefresh() {
  const refresh = window.refreshAll || (typeof refreshAll === "function" ? refreshAll : null);
  if (typeof refresh !== "function") {
    reportSettingsPostSaveRefreshFailure("Settings were saved, but automatic refresh is not available. Reload settings before launching.");
    return;
  }
  window.setTimeout(() => {
    try {
      const result = refresh();
      if (result && typeof result.catch === "function") {
        result.catch((error) => reportSettingsPostSaveRefreshFailure(error));
      }
    } catch (error) {
      reportSettingsPostSaveRefreshFailure(error);
    }
  }, 0);
}

function reportSettingsPostSaveRefreshFailure(error) {
  const message = error instanceof Error ? error.message : String(error);
  const detail = [
    byId("settings-patch-detail")?.textContent || "",
    "",
    `Post-save refresh failed: ${message}`,
    "The backend save may have succeeded, but the WebView could still be showing stale settings. Use Reload From Disk or refresh before launching.",
  ].filter(Boolean).join("\n");
  setText("settings-patch-status", "Saved; refresh failed");
  setText("settings-patch-detail", detail);
  window.mediaPipelineSettingsLibraries?.handleSettingsPostSaveRefreshFailure?.(message);
  renderSettingsPatchSummary();
}

function settingsPostErrorMessage(error, action) {
  const raw = error instanceof Error ? error.message : String(error);
  const lower = raw.toLowerCase();
  if (!lower.includes("timed out") && !lower.includes("timeout")) return raw;
  if (action === "save") {
    return "Settings save timed out before backend success was reported. Save status unknown; use Reload From Disk or refresh to verify saved backend settings before launching.";
  }
  return "Settings preview timed out before backend validation completed. No save command was sent; use Preview again or refresh before saving.";
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
  const command = String(result?.command || "").trim().toLowerCase();
  const message = String(result?.message || "").trim().toLowerCase();
  if (severity === "warning") {
    if (message.includes("no changes")) return "No backend changes";
    if (command === "settings.preview_patch") return "Review warnings";
    return "Review warnings";
  }
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

function settingsSaveReviewModalHost() {
  return document.querySelector("[data-settings-modal-host]") || document.querySelector("main.workspace") || document.body;
}

function ensureSettingsSaveReviewDialogGlobal(dialog) {
  const hiddenPage = dialog?.closest?.(".page:not(.is-visible)");
  if (!hiddenPage) return dialog;
  const host = settingsSaveReviewModalHost();
  if (host && typeof host.appendChild === "function") {
    host.appendChild(dialog);
  } else if (document.body && typeof document.body.appendChild === "function") {
    document.body.appendChild(dialog);
  }
  return dialog;
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
    const result = await apiPost("/api/settings/preview-patch", { changes }, { timeoutMs: SETTINGS_PREVIEW_POST_TIMEOUT_MS });
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
    const message = settingsPostErrorMessage(error, "preview");
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
  setFinalLibraryPromotionStatus("Previewing save...", "Requesting backend preview before saving Final Library Promotion settings.");
  try {
    const previewResult = await apiPost("/api/settings/preview-patch", { changes }, { timeoutMs: SETTINGS_PREVIEW_POST_TIMEOUT_MS });
    appendCommandResult(previewResult);
    const previewData = previewResult.data && typeof previewResult.data === "object" ? previewResult.data : {};
    const reviewConfirmation = previewData.review_confirmation && typeof previewData.review_confirmation === "object"
      ? previewData.review_confirmation
      : null;
    if (!previewResult.ok || (previewResult.errors || []).length) {
      setFinalLibraryPromotionStatus("Preview blocked", finalLibraryPromotionSettingsResultLines("Backend preview", previewResult, changes).join("\n"));
      return;
    }
    if (!reviewConfirmation) {
      setFinalLibraryPromotionStatus("Preview missing confirmation", "Backend preview did not return a review_confirmation contract, so no save command was sent.");
      return;
    }
    setFinalLibraryPromotionStatus("Saving...", "Saving backend-validated Final Library Promotion settings to the active PSD1. A backup will be created first.");
    const result = await apiPost(
      "/api/settings/save-patch",
      { changes, review_confirmation: reviewConfirmation, confirm_save: true },
      { timeoutMs: SETTINGS_SAVE_POST_TIMEOUT_MS }
    );
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
      scheduleSettingsPostSaveRefresh();
    }
  } catch (error) {
    const message = settingsPostErrorMessage(error, "save");
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
function settingsLibraryProfilePatchStateKind() {
  const provider = window.mediaPipelineSettingsLibraries?.libraryPatchStateKind;
  if (typeof provider !== "function") return "";
  try {
    return String(provider() || "");
  } catch (_error) {
    return "";
  }
}
function settingsPatchHasStaleLibraryProfiles(changes) {
  return Boolean(
    changes
    && typeof changes === "object"
    && !Array.isArray(changes)
    && Object.prototype.hasOwnProperty.call(changes, "LibraryProfiles")
    && settingsLibraryProfilePatchStateKind() === "stale"
  );
}
function blockStaleLibraryProfilesPatch(command) {
  if (command && typeof appendCommandResult === "function") {
    appendCommandResult({
      command,
      ok: false,
      severity: "warning",
      message: "Stale LibraryProfiles patch blocked before backend settings save.",
    });
  }
  setText("settings-patch-status", "Stale LibraryProfiles blocked");
  setText(
    "settings-patch-detail",
    [
      "Changes JSON contains LibraryProfiles, but the Library Profiles editor says that patch is stale.",
      "Stage Patch from the Library Profiles tab to save the current profile editor state, or Reset From Current to remove the stale LibraryProfiles key before saving unrelated settings.",
      "No backend preview or save command was sent.",
    ].join("\n")
  );
  renderSettingsPatchSummary();
  return true;
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
      if (typeof window.mediaPipelineProgressView?.renderProgressBarsInto === "function") {
        window.mediaPipelineProgressView.renderProgressBarsInto.apply(window.mediaPipelineProgressView, arguments);
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
    let headerText = patchStatusEl.textContent || "No changes";
    if (headerText !== "No backend changes") {
      try {
        if (!settingsPatchIsTouched() || !settingsPatchHasUnsavedChanges()) {
          headerText = "No changes";
        }
      } catch (_error) {}
    }
    headerPatchEl.textContent = headerText || "No changes";
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
    if (Array.isArray(value) && value.some((item) => item && typeof item === "object")) {
      try {
        return JSON.stringify(value);
      } catch (_) {}
    }
    if (value && typeof value === "object") {
      try {
        return JSON.stringify(value);
      } catch (_) {}
    }
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

  const renameFilterTermKeys = new Set([
    "RenameMovieFilterTerms",
    "RenameTVFilterTerms",
  ]);
  const renameFilterOptionKeys = new Set([
    "RenameMovieFilterOptions",
    "RenameTVFilterOptions",
  ]);
  const renameFilterRemoveTermKeys = new Set([
    "RenameMovieRemoveTerms",
    "RenameTVRemoveTerms",
  ]);

  function settingsSaveReviewObjectValue(value) {
    if (value && typeof value === "object" && !Array.isArray(value)) return value;
    if (typeof value !== "string") return null;
    const trimmed = value.trim();
    if (!trimmed.startsWith("{")) return null;
    try {
      const parsed = JSON.parse(trimmed);
      return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : null;
    } catch (_error) {
      return null;
    }
  }

  function settingsSaveReviewTermList(value) {
    if (Array.isArray(value)) {
      return value.map((item) => String(item || "").trim()).filter(Boolean);
    }
    if (value === undefined || value === null) return [];
    if (typeof value === "string") {
      const trimmed = value.trim();
      if (!trimmed) return [];
      if (trimmed.startsWith("[")) {
        try {
          const parsed = JSON.parse(trimmed);
          if (Array.isArray(parsed)) return settingsSaveReviewTermList(parsed);
        } catch (_error) {}
      }
      return parseSettingsListText(trimmed);
    }
    return [String(value).trim()].filter(Boolean);
  }

  function settingsSaveReviewTermMap(value) {
    const map = new Map();
    settingsSaveReviewTermList(value).forEach((term) => {
      const normalized = term.toLowerCase();
      if (!map.has(normalized)) map.set(normalized, term);
    });
    return map;
  }

  function settingsSaveReviewTermDeltas(currentValue, newValue) {
    const currentMap = settingsSaveReviewTermMap(currentValue);
    const newMap = settingsSaveReviewTermMap(newValue);
    const added = [];
    const removed = [];
    newMap.forEach((term, normalized) => {
      if (!currentMap.has(normalized)) added.push(term);
    });
    currentMap.forEach((term, normalized) => {
      if (!newMap.has(normalized)) removed.push(term);
    });
    return { added, removed };
  }

  function settingsSaveReviewRenameFilterLabel(value) {
    return String(value || "").replace(/_/g, " ").replace(/\s+/g, " ").trim() || "default";
  }

  function settingsSaveReviewLimitedText(values, limit = 6) {
    const visible = values.slice(0, limit);
    const suffix = values.length > visible.length ? `, +${values.length - visible.length} more` : "";
    return `${visible.join(", ")}${suffix}`;
  }

  function settingsSaveReviewRenameTermDictionaryText(currentValue, newValue, side) {
    const currentTerms = settingsSaveReviewObjectValue(currentValue);
    const newTerms = settingsSaveReviewObjectValue(newValue);
    if (!currentTerms || !newTerms) return "";
    const keys = Array.from(new Set([...Object.keys(currentTerms), ...Object.keys(newTerms)]))
      .sort((a, b) => a.localeCompare(b));
    const addedLines = [];
    const removedLines = [];
    keys.forEach((key) => {
      const delta = settingsSaveReviewTermDeltas(currentTerms[key], newTerms[key]);
      if (delta.added.length) {
        addedLines.push(`${settingsSaveReviewRenameFilterLabel(key)}: ${settingsSaveReviewLimitedText(delta.added)}`);
      }
      if (delta.removed.length) {
        removedLines.push(`${settingsSaveReviewRenameFilterLabel(key)}: ${settingsSaveReviewLimitedText(delta.removed)}`);
      }
    });
    const lines = side === "current" ? removedLines : addedLines;
    const oppositeLines = side === "current" ? addedLines : removedLines;
    if (lines.length) {
      return `${side === "current" ? "Removed terms" : "Added terms"}: ${lines.join("; ")}. Unchanged terms hidden.`;
    }
    if (oppositeLines.length) {
      return `${side === "current" ? "No removed terms" : "No added terms"}. Unchanged terms hidden.`;
    }
    return "No added or removed terms after trim/case comparison; unchanged terms hidden.";
  }

  function settingsSaveReviewOptionState(value) {
    if (value === undefined) return "(not set)";
    if (value === true) return "on";
    if (value === false) return "off";
    const text = String(value).trim().toLowerCase();
    if (["true", "1", "yes", "on"].includes(text)) return "on";
    if (["false", "0", "no", "off"].includes(text)) return "off";
    return String(value);
  }

  function settingsSaveReviewRenameOptionDictionaryText(currentValue, newValue) {
    const currentOptions = settingsSaveReviewObjectValue(currentValue);
    const newOptions = settingsSaveReviewObjectValue(newValue);
    if (!currentOptions || !newOptions) return "";
    const keys = Array.from(new Set([...Object.keys(currentOptions), ...Object.keys(newOptions)]))
      .sort((a, b) => a.localeCompare(b));
    const changed = keys
      .filter((key) => settingsSaveReviewOptionState(currentOptions[key]) !== settingsSaveReviewOptionState(newOptions[key]))
      .map((key) => `${settingsSaveReviewRenameFilterLabel(key)}: ${settingsSaveReviewOptionState(currentOptions[key])} -> ${settingsSaveReviewOptionState(newOptions[key])}`);
    if (!changed.length) return "No option toggles changed; unchanged options hidden.";
    return `Changed toggles: ${changed.join("; ")}. Unchanged options hidden.`;
  }

  function settingsSaveReviewRenameRemoveTermsText(currentValue, newValue, side) {
    const delta = settingsSaveReviewTermDeltas(currentValue, newValue);
    const values = side === "current" ? delta.removed : delta.added;
    const oppositeValues = side === "current" ? delta.added : delta.removed;
    if (values.length) {
      return `${side === "current" ? "Removed terms" : "Added terms"}: ${settingsSaveReviewLimitedText(values)}. Unchanged terms hidden.`;
    }
    if (oppositeValues.length) {
      return `${side === "current" ? "No removed terms" : "No added terms"}. Unchanged terms hidden.`;
    }
    return "No added or removed terms after trim/case comparison; unchanged terms hidden.";
  }

  function settingsSaveReviewLibraryProfiles(value) {
    let candidate = value;
    if (typeof candidate === "string") {
      const trimmed = candidate.trim();
      if (!trimmed) return [];
      try {
        candidate = JSON.parse(trimmed);
      } catch (_error) {
        return [];
      }
    }
    if (!Array.isArray(candidate)) return [];
    return candidate.filter((profile) => profile && typeof profile === "object" && !Array.isArray(profile));
  }

  function settingsSaveReviewCanonicalProfileId(value, fallback) {
    const id = String(value || "").trim().toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "") || fallback;
    if (id === "movie" || id === "movies") return "movies";
    if (id === "show" || id === "shows" || id === "tv") return "tv";
    return id;
  }

  function settingsSaveReviewProfileId(profile, index = 0) {
    const raw = String(profile?.id || profile?.library_id || profile?.name || "").trim();
    return settingsSaveReviewCanonicalProfileId(raw, `profile-${index + 1}`);
  }

  function settingsSaveReviewProfileLabel(profile, index = 0) {
    const id = settingsSaveReviewProfileId(profile, index);
    const name = String(profile?.name || "").trim();
    return name && name !== id ? `${name} (${id})` : id;
  }

  function settingsSaveReviewPrimitiveText(value) {
    if (value === undefined) return "(not set)";
    if (value === null) return "null";
    if (Array.isArray(value) || (value && typeof value === "object")) {
      try {
        return JSON.stringify(value);
      } catch (_) {
        return String(value);
      }
    }
    return String(value);
  }

  function settingsSaveReviewProfileOverrideEntries(profile, index = 0) {
    const overrides = profile?.overrides && typeof profile.overrides === "object" && !Array.isArray(profile.overrides)
      ? profile.overrides
      : {};
    const profileId = settingsSaveReviewProfileId(profile, index);
    const profileLabel = settingsSaveReviewProfileLabel(profile, index);
    return Object.keys(overrides).sort((a, b) => a.localeCompare(b)).flatMap((group) => {
      const groupValues = overrides[group];
      if (!groupValues || typeof groupValues !== "object" || Array.isArray(groupValues)) return [];
      return Object.keys(groupValues).sort((a, b) => a.localeCompare(b)).map((key) => ({
        profileId,
        profileLabel,
        path: `${group}.${key}`,
        value: groupValues[key],
      }));
    });
  }

  function settingsSaveReviewLibraryProfileSummary(value) {
    const profiles = settingsSaveReviewLibraryProfiles(value);
    if (!profiles.length) return settingsSaveReviewValueText(value);
    const enabledCount = profiles.filter((profile) => profile.enabled !== false).length;
    const profileLabels = profiles
      .slice(0, 4)
      .map((profile, index) => settingsSaveReviewProfileLabel(profile, index));
    const profileSuffix = profiles.length > profileLabels.length ? `, +${profiles.length - profileLabels.length} more` : "";
    const overrideEntries = profiles.flatMap((profile, index) => settingsSaveReviewProfileOverrideEntries(profile, index));
    const overrideLabels = overrideEntries
      .slice(0, 5)
      .map((entry) => `${entry.profileId}.${entry.path}=${settingsSaveReviewPrimitiveText(entry.value)}`);
    const overrideSuffix = overrideEntries.length > overrideLabels.length ? `, +${overrideEntries.length - overrideLabels.length} more` : "";
    return [
      `${profiles.length} profile${profiles.length === 1 ? "" : "s"} (${enabledCount} enabled): ${profileLabels.join(", ")}${profileSuffix}`,
      overrideEntries.length ? `Overrides: ${overrideLabels.join("; ")}${overrideSuffix}` : "Overrides: none",
    ].join(". ");
  }

  function settingsSaveReviewProfileMap(profiles) {
    const map = new Map();
    profiles.forEach((profile, index) => {
      map.set(settingsSaveReviewProfileId(profile, index), { profile, index });
    });
    return map;
  }

  function settingsSaveReviewOverrideMap(profile, index = 0) {
    const map = new Map();
    settingsSaveReviewProfileOverrideEntries(profile, index).forEach((entry) => {
      map.set(entry.path, entry.value);
    });
    return map;
  }

  function settingsSaveReviewValuesDiffer(left, right) {
    try {
      return !settingsValuesEqual(left, right);
    } catch (_error) {
      return JSON.stringify(left) !== JSON.stringify(right);
    }
  }

  function settingsSaveReviewLibraryProfileDiffEntries(currentValue, newValue) {
    const currentProfiles = settingsSaveReviewLibraryProfiles(currentValue);
    const newProfiles = settingsSaveReviewLibraryProfiles(newValue);
    const currentMap = settingsSaveReviewProfileMap(currentProfiles);
    const newMap = settingsSaveReviewProfileMap(newProfiles);
    const ids = Array.from(new Set([...currentMap.keys(), ...newMap.keys()])).sort((a, b) => a.localeCompare(b));
    const topLevelKeys = ["name", "enabled", "designation", "source_path", "output_path", "promotion_enabled", "promotion_destination"];
    const entries = [];
    ids.forEach((id) => {
      const currentRecord = currentMap.get(id);
      const newRecord = newMap.get(id);
      if (!currentRecord && newRecord) {
        entries.push({
          profileLabel: settingsSaveReviewProfileLabel(newRecord.profile, newRecord.index),
          path: "profile",
          before: undefined,
          after: "added",
        });
        return;
      }
      if (currentRecord && !newRecord) {
        entries.push({
          profileLabel: settingsSaveReviewProfileLabel(currentRecord.profile, currentRecord.index),
          path: "profile",
          before: "present",
          after: undefined,
        });
        return;
      }
      if (!currentRecord || !newRecord) return;
      topLevelKeys.forEach((key) => {
        const before = currentRecord.profile[key];
        const after = newRecord.profile[key];
        if (settingsSaveReviewValuesDiffer(before, after)) {
          entries.push({
            profileLabel: settingsSaveReviewProfileLabel(newRecord.profile, newRecord.index),
            path: key,
            before,
            after,
          });
        }
      });
      const currentOverrides = settingsSaveReviewOverrideMap(currentRecord.profile, currentRecord.index);
      const newOverrides = settingsSaveReviewOverrideMap(newRecord.profile, newRecord.index);
      Array.from(new Set([...currentOverrides.keys(), ...newOverrides.keys()]))
        .sort((a, b) => a.localeCompare(b))
        .forEach((path) => {
          const before = currentOverrides.get(path);
          const after = newOverrides.get(path);
          if (settingsSaveReviewValuesDiffer(before, after)) {
            entries.push({
              profileLabel: settingsSaveReviewProfileLabel(newRecord.profile, newRecord.index),
              path,
              before,
              after,
            });
          }
        });
    });
    return entries;
  }

  function settingsSaveReviewLibraryProfileCellText(value, currentValue, newValue, side) {
    const summary = settingsSaveReviewLibraryProfileSummary(value);
    const deltas = settingsSaveReviewLibraryProfileDiffEntries(currentValue, newValue);
    if (!deltas.length) return summary;
    const valueKey = side === "current" ? "before" : "after";
    const labels = deltas
      .slice(0, 4)
      .map((entry) => `${entry.profileLabel}.${entry.path}=${settingsSaveReviewPrimitiveText(entry[valueKey])}`);
    const suffix = deltas.length > labels.length ? `, +${deltas.length - labels.length} more` : "";
    return `${summary}. ${side === "current" ? "Current" : "New"} changed values: ${labels.join("; ")}${suffix}`;
  }

  function settingsSaveReviewCellText(key, value, currentValue, newValue, side) {
    if (key === "LibraryProfiles") {
      return settingsSaveReviewLibraryProfileCellText(value, currentValue, newValue, side);
    }
    if (renameFilterTermKeys.has(key)) {
      return settingsSaveReviewRenameTermDictionaryText(currentValue, newValue, side) || "Changed; unchanged terms hidden.";
    }
    if (renameFilterOptionKeys.has(key)) {
      return settingsSaveReviewRenameOptionDictionaryText(currentValue, newValue) || "Changed; unchanged options hidden.";
    }
    if (renameFilterRemoveTermKeys.has(key)) {
      return settingsSaveReviewRenameRemoveTermsText(currentValue, newValue, side);
    }
    return settingsSaveReviewValueText(value);
  }

  function settingsSaveReviewBackendEntries(entries = []) {
    return (Array.isArray(entries) ? entries : [])
      .filter((entry) => entry && typeof entry === "object" && !Array.isArray(entry) && String(entry.key || "").trim());
  }

  function settingsSaveReviewBackendEntryForKey(entries = [], key) {
    return settingsSaveReviewBackendEntries(entries).find((entry) => String(entry.key || "") === key) || null;
  }

  function settingsReviewDigestShort(value) {
    const text = String(value || "").trim();
    return text ? `${text.slice(0, 12)}...` : "n/a";
  }

  function settingsSaveReviewSourceLabel(source) {
    const value = String(source || "").trim();
    if (value === "mirrored_from_library_profiles") return "mirrored from LibraryProfiles";
    if (value === "backend_normalized") return "backend normalized";
    if (value === "removed") return "remove request";
    if (value === "submitted") return "submitted";
    return value || "backend";
  }

  function settingsSaveReviewStatusLabel(entry) {
    const status = String(entry?.status || "").trim().toLowerCase();
    const statusLabel = status === "new" ? "New" : status === "removed" ? "Removed" : "Changed";
    const sourceLabel = settingsSaveReviewSourceLabel(entry?.source);
    return sourceLabel && sourceLabel !== "submitted" && sourceLabel !== "remove request"
      ? `${statusLabel} (${sourceLabel})`
      : statusLabel;
  }

  function settingsSaveReviewEntryCellText(entry, side) {
    const key = String(entry?.key || "");
    const currentExists = entry?.current_exists !== false;
    const newExists = entry?.new_exists !== false;
    const currentValue = currentExists ? entry.current_value : undefined;
    const newValue = newExists ? entry.new_value : undefined;
    if (side === "current") {
      return currentExists
        ? settingsSaveReviewCellText(key, currentValue, currentValue, newValue, "current")
        : "(not previously set)";
    }
    if (!newExists || String(entry?.status || "").toLowerCase() === "removed") return "(remove key)";
    return settingsSaveReviewCellText(key, newValue, currentValue, newValue, "new");
  }

  function settingsSaveReviewLibraryProfileDetailLines(currentValue, newValue) {
    const deltas = settingsSaveReviewLibraryProfileDiffEntries(currentValue, newValue);
    if (!deltas.length) {
      return ["LibraryProfiles changed, but no profile field or override delta was summarized. Use the backend redacted diff before saving."];
    }
    const lines = deltas.slice(0, 20).map((entry) => (
      `- ${entry.profileLabel}.${entry.path}: ${settingsSaveReviewPrimitiveText(entry.before)} -> ${settingsSaveReviewPrimitiveText(entry.after)}`
    ));
    if (deltas.length > lines.length) lines.push(`- +${deltas.length - lines.length} more LibraryProfiles change(s).`);
    return lines;
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

  function settingsUniqueKeys(keys = []) {
    return Array.from(new Set((Array.isArray(keys) ? keys : [])
      .map((key) => String(key || "").trim())
      .filter(Boolean)));
  }

  function settingsSaveActualKeys(changedKeys = [], removedKeys = []) {
    return settingsUniqueKeys([...settingsUniqueKeys(changedKeys), ...settingsUniqueKeys(removedKeys)]);
  }

  function clearSettingsPatchCandidate() {
    const patchNode = byId("settings-patch-json");
    if (patchNode) patchNode.value = "{}";
    settingsPatchTouched = false;
  }

  function settingsSavePreviewDetailLines(result, localHintLines = [], options = {}) {
    const data = result?.data && typeof result.data === "object" ? result.data : {};
    const changedKeys = settingsUniqueKeys(data.changed_keys || []);
    const removedKeys = settingsUniqueKeys(data.removed_keys || []);
    const submittedCount = Number.isFinite(options.submittedCount) ? options.submittedCount : 0;
    const lines = [
      result?.message || "Backend settings save preview completed.",
      "",
      "Backend preview is authoritative for which submitted settings will actually change.",
      `Submitted keys: ${submittedCount}`,
      `Backend-confirmed changed keys: ${settingsPersistedKeyDisplayList(changedKeys) || "none"}`,
      `Backend-confirmed removed keys: ${settingsPersistedKeyDisplayList(removedKeys) || "none"}`,
      `Writes config during preview: ${data.writes_config === true ? "yes" : "no"}`,
      `Review contract: ${data.review_entries_schema_version || "legacy"}; confirmation ${settingsReviewDigestShort(data.review_confirmation?.preview_id)}`,
    ];
    if (localHintLines.length) lines.push("", ...localHintLines);
    if ((result?.errors || []).length) {
      lines.push("", "Errors:", ...(result.errors || []).map((item) => `- ${item}`));
      lines.push("Backend validation errors are authoritative; this WebView did not save or bypass them.");
    }
    if ((result?.warnings || []).length) {
      lines.push("", "Warnings:", ...(result.warnings || []).map((item) => `- ${item}`));
    }
    appendSettingsRiskSummaryLines(lines, data.risk_summary);
    if ((data.redacted_diff_lines || []).length) {
      lines.push("", "Redacted diff:", ...(data.redacted_diff_lines || []));
      if (data.diff_truncated) lines.push("...diff truncated...");
    }
    return lines;
  }

  function renderSettingsSaveReviewDialogRows({ changes, changedKeys, removedKeys, libraryProfileResetCount, reviewEntries = [] }) {
    const tbody = byId("settings-save-review-dialog-rows");
    if (!tbody) return;
    const backendEntries = settingsSaveReviewBackendEntries(reviewEntries);
    const effectiveChangedKeys = settingsUniqueKeys(changedKeys).sort((a, b) => a.localeCompare(b));
    const effectiveRemovedKeys = settingsUniqueKeys(removedKeys).sort((a, b) => a.localeCompare(b));
    tbody.replaceChildren();
    if (!backendEntries.length && !effectiveChangedKeys.length && !effectiveRemovedKeys.length && !libraryProfileResetCount) {
      const row = document.createElement("tr");
      const cell = document.createElement("td");
      cell.colSpan = 4;
      cell.textContent = "No settings changes to review.";
      row.appendChild(cell);
      tbody.appendChild(row);
      return;
    }
    if (backendEntries.length) {
      backendEntries
        .slice()
        .sort((a, b) => String(a.key || "").localeCompare(String(b.key || "")))
        .forEach((entry) => {
          const key = String(entry.key || "");
          const row = document.createElement("tr");
          appendSettingsSaveReviewCell(row, settingsSaveReviewLabel(key));
          appendSettingsSaveReviewCell(row, settingsSaveReviewEntryCellText(entry, "current"));
          appendSettingsSaveReviewCell(row, settingsSaveReviewEntryCellText(entry, "new"));
          appendSettingsSaveReviewCell(row, settingsSaveReviewStatusLabel(entry));
          tbody.appendChild(row);
        });
    }
    if (!backendEntries.length) effectiveChangedKeys.forEach((key) => {
      const row = document.createElement("tr");
      const currentExists = lastSettingsValues && Object.prototype.hasOwnProperty.call(lastSettingsValues, key);
      const currentValue = currentExists ? lastSettingsValues[key] : undefined;
      const newValue = changes[key];
      appendSettingsSaveReviewCell(row, settingsSaveReviewLabel(key));
      appendSettingsSaveReviewCell(row, currentExists ? settingsSaveReviewCellText(key, currentValue, currentValue, newValue, "current") : "(not previously set)");
      appendSettingsSaveReviewCell(row, settingsSaveReviewCellText(key, newValue, currentValue, newValue, "new"));
      appendSettingsSaveReviewCell(row, currentExists ? "Changed" : "New");
      tbody.appendChild(row);
    });
    if (!backendEntries.length) effectiveRemovedKeys.forEach((key) => {
      const row = document.createElement("tr");
      const currentExists = lastSettingsValues && Object.prototype.hasOwnProperty.call(lastSettingsValues, key);
      appendSettingsSaveReviewCell(row, settingsSaveReviewLabel(key));
      appendSettingsSaveReviewCell(row, currentExists ? settingsSaveReviewValueText(lastSettingsValues[key]) : "(not previously set)");
      appendSettingsSaveReviewCell(row, "(remove key)");
      appendSettingsSaveReviewCell(row, "Removed");
      tbody.appendChild(row);
    });
    if (!effectiveChangedKeys.length && !effectiveRemovedKeys.length && libraryProfileResetCount) {
      const row = document.createElement("tr");
      appendSettingsSaveReviewCell(row, "Library profile reset");
      appendSettingsSaveReviewCell(row, "Current profile overrides");
      appendSettingsSaveReviewCell(row, `${libraryProfileResetCount} reset request(s)`);
      appendSettingsSaveReviewCell(row, "Reset");
      tbody.appendChild(row);
    }
  }

  function openSettingsSaveReviewDialog(options) {
    const dialog = ensureSettingsSaveReviewDialogGlobal(byId("settings-save-review-dialog"));
    if (!dialog || typeof dialog.showModal !== "function") {
      setText("settings-patch-status", "Review unavailable");
      setText("settings-patch-detail", "The Save Settings review dialog could not open, so no backend save command was sent.");
      return Promise.resolve(false);
    }
    const {
      changes,
      keys,
      changedKeys,
      removedKeys,
      libraryProfileResetCount,
      localHintLines,
      renameMerge,
      previewResult,
    } = options;
    const reviewEntries = settingsSaveReviewBackendEntries(previewResult?.data?.review_entries || options.reviewEntries || []);
    const effectiveChangeCount = settingsSaveActualKeys(changedKeys, removedKeys).length;
    setText(
      "settings-save-review-summary",
      `Review ${effectiveChangeCount} backend-confirmed change${effectiveChangeCount === 1 ? "" : "s"} from ${keys.length} submitted key${keys.length === 1 ? "" : "s"} before writing the active PSD1.`
    );
    setText("settings-save-review-dialog-changed", String(effectiveChangeCount));
    setText("settings-save-review-dialog-submitted", String(keys.length));
    setText("settings-save-review-dialog-resets", String(libraryProfileResetCount));
    renderSettingsSaveReviewDialogRows({ changes, changedKeys, removedKeys, libraryProfileResetCount, reviewEntries });
    const detailLines = [
      "Backend preview already filtered out submitted values that are unchanged. Confirming will save only backend-confirmed changes.",
      "Backend save will validate again, write a backup, persist the PSD1, and reload settings after confirmation.",
      settingsRuntimeRestartConfirmationLine(),
    ];
    if (renameMerge?.included) {
      detailLines.push(`Rename filter keys included: ${settingsPersistedKeyDisplayList(renameMerge.keys)}.`);
    }
    if (settingsUniqueKeys(changedKeys).includes("LibraryProfiles")) {
      const libraryProfileEntry = settingsSaveReviewBackendEntryForKey(reviewEntries, "LibraryProfiles");
      detailLines.push(
        "",
        "LibraryProfiles change detail:",
        ...settingsSaveReviewLibraryProfileDetailLines(
          libraryProfileEntry ? libraryProfileEntry.current_value : lastSettingsValues?.LibraryProfiles,
          libraryProfileEntry ? libraryProfileEntry.new_value : changes.LibraryProfiles
        )
      );
    }
    if ((previewResult?.warnings || []).length) {
      detailLines.push("", "Backend preview warning(s):", ...(previewResult.warnings || []).map((item) => `- ${item}`));
    }
    if (localHintLines.length) detailLines.push("", ...localHintLines);
    setText("settings-save-review-dialog-detail", detailLines.join("\n"));
    return new Promise((resolve) => {
      const form = dialog.querySelector("form");
      let settled = false;
      const cleanup = () => {
        dialog.removeEventListener("close", onClose);
        form?.removeEventListener("submit", onSubmit);
      };
      const finish = (value) => {
        if (settled) return;
        settled = true;
        cleanup();
        resolve(value);
      };
      const onSubmit = (event) => {
        event.preventDefault();
        const submitter = event.submitter;
        const value = String(submitter?.value || "cancel");
        dialog.returnValue = value;
        dialog.close(value);
      };
      const onClose = () => {
        finish(dialog.returnValue === "confirm");
      };
      dialog.addEventListener("close", onClose);
      form?.addEventListener("submit", onSubmit);
      try {
        dialog.returnValue = "cancel";
        dialog.showModal();
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        setText("settings-patch-status", "Review unavailable");
        setText("settings-patch-detail", `The Save Settings review dialog could not open: ${message}`);
        finish(false);
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
  if (settingsPatchHasStaleLibraryProfiles(changes)) {
    blockStaleLibraryProfilesPatch("settings.preview_patch");
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
    const result = await apiPost("/api/settings/preview-patch", { changes, ...requestExtras }, { timeoutMs: SETTINGS_PREVIEW_POST_TIMEOUT_MS });
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
    const message = settingsPostErrorMessage(error, "preview");
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
  if (settingsPatchHasStaleLibraryProfiles(changes)) {
    blockStaleLibraryProfilesPatch("settings.save_patch");
    return;
  }
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
  const rawAtRequest = byId("settings-patch-json")?.value || "{}";
  let previewResult;
  setSettingsCommandBusy(true);
  setText("settings-patch-status", "Previewing save...");
  setText("settings-patch-detail", [
    "Requesting backend save preview. This filters submitted keys down to settings that will actually change.",
    ...localHintLines,
  ].join("\n"));
  try {
    previewResult = await apiPost("/api/settings/preview-patch", { changes, ...requestExtras }, { timeoutMs: SETTINGS_PREVIEW_POST_TIMEOUT_MS });
  } catch (error) {
    const message = settingsPostErrorMessage(error, "preview");
    const result = {
      command: "settings.preview_patch",
      ok: false,
      severity: "error",
      message,
    };
    appendCommandResult(result);
    lastSettingsPatchPreviewEvidence = {
      signature,
      command: "settings.preview_patch",
      result,
      captured_at: new Date().toISOString(),
    };
    setText("settings-patch-status", "Preview failed");
    setText("settings-patch-detail", message);
    renderSettingsPatchSummary();
    setSettingsCommandBusy(false);
    return;
  }
  if ((byId("settings-patch-json")?.value || "{}") !== rawAtRequest) {
    setText("settings-patch-status", "Preview replaced");
    setText("settings-patch-detail", "Patch JSON changed before the backend save preview returned. Save again to review the current values before writing.");
    renderSettingsPatchSummary();
    setSettingsCommandBusy(false);
    return;
  }
  appendCommandResult(previewResult);
  lastSettingsPatchPreviewEvidence = {
    signature,
    command: "settings.preview_patch",
    result: previewResult,
    captured_at: new Date().toISOString(),
  };
  const previewData = previewResult.data && typeof previewResult.data === "object" ? previewResult.data : {};
  const reviewConfirmation = previewData.review_confirmation && typeof previewData.review_confirmation === "object"
    ? previewData.review_confirmation
    : null;
  const changedKeys = settingsUniqueKeys(previewData.changed_keys || []);
  const removedKeys = settingsUniqueKeys(previewData.removed_keys || []);
  const actualChangeKeys = settingsSaveActualKeys(changedKeys, removedKeys);
  const previewLines = settingsSavePreviewDetailLines(previewResult, localHintLines, { submittedCount: keys.length });
  if (!previewResult.ok || (previewResult.errors || []).length) {
    setText("settings-patch-status", "Preview blocked");
    setText("settings-patch-detail", previewLines.join("\n"));
    renderSettingsPatchSummary();
    setSettingsCommandBusy(false);
    return;
  }
  if (!actualChangeKeys.length) {
    clearSettingsPatchCandidate();
    resetSettingsBuilderSyncState();
    setText("settings-patch-status", "No backend changes");
    setText("settings-patch-detail", [
      renameMerge.draftSaved ? "Rename filter draft retained in this browser for local recovery." : "",
      ...previewLines,
      "",
      "No backend settings differ from the saved config, so no save command was sent.",
      "The stale save candidate was cleared to avoid reviewing unchanged values again.",
    ].filter(Boolean).join("\n"));
    renderSettingsPatchSummary();
    if (typeof renderAllLaunchPreflights === "function") renderAllLaunchPreflights();
    setSettingsCommandBusy(false);
    return;
  }
  if (!reviewConfirmation) {
    setText("settings-patch-status", "Preview missing confirmation");
    setText("settings-patch-detail", [
      ...previewLines,
      "",
      "Backend preview did not return a review_confirmation contract, so no save command was sent.",
    ].join("\n"));
    renderSettingsPatchSummary();
    setSettingsCommandBusy(false);
    return;
  }
  setText("settings-patch-status", (previewResult.warnings || []).length ? "Review warnings" : "Review ready");
  setText("settings-patch-detail", previewLines.join("\n"));
  renderSettingsPatchSummary();
  const confirmed = await openSettingsSaveReviewDialog({
    changes,
    keys,
    changedKeys,
    removedKeys,
    libraryProfileResetCount,
    localHintLines,
    renameMerge,
    previewResult,
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
    setSettingsCommandBusy(false);
    return;
  }
  const snapshotBefore = {};
  actualChangeKeys.forEach((key) => {
    if (lastSettingsValues && Object.prototype.hasOwnProperty.call(lastSettingsValues, key)) {
      snapshotBefore[key] = lastSettingsValues[key];
    }
  });
  setText("settings-patch-status", "Saving...");
  setText("settings-patch-detail", [
    "Saving backend-validated settings changes to the active PSD1. A backup will be created first.",
    ...localHintLines,
  ].join("\n"));
  try {
    const result = await apiPost(
      "/api/settings/save-patch",
      { changes, ...requestExtras, review_confirmation: reviewConfirmation, confirm_save: true },
      { timeoutMs: SETTINGS_SAVE_POST_TIMEOUT_MS }
    );
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
    const saveReviewEntries = settingsSaveReviewBackendEntries(data.review_entries || []);
    const lines = [
      result.message || "Settings save completed.",
      "",
      `Writes config: ${data.writes_config === true ? "yes" : "no"}`,
      `Config: ${data.config_path || ""}`,
      `Backup: ${data.backup_path || ""}`,
      `Reloaded: ${data.reloaded === true ? "yes" : data.reloaded === false ? "no" : "n/a"}`,
      `Reload verified: ${data.save_verification?.verified_from_reload === true ? "yes" : data.save_verification?.verified_from_reload === false ? "no" : "n/a"}`,
      `Review confirmation: ${settingsReviewDigestShort(data.review_confirmation?.preview_id)}`,
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
        const reviewEntry = settingsSaveReviewBackendEntryForKey(saveReviewEntries, key);
        const afterValue = reviewEntry && reviewEntry.new_exists !== false ? reviewEntry.new_value : changes[key];
        lines.push(`  ${key}: ${JSON.stringify(snapshotBefore[key])} -> ${JSON.stringify(afterValue)}`);
      });
      if (data.backup_path) lines.push(`  Backup: ${data.backup_path}`);
    }
    if (result.ok) {
      clearSettingsPatchCandidate();
      resetSettingsBuilderSyncState();
    }
    setText("settings-patch-detail", lines.join("\n"));
    renderSettingsPatchSummary();
    maybeShowSettingsRuntimeRestartNotice(result);
    if (result.ok) {
      scheduleSettingsPostSaveRefresh();
    }
  } catch (error) {
    const message = settingsPostErrorMessage(error, "save");
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
  window.renderSettingsRawActionPlan = renderSettingsRawActionPlan;
  window.renderSettings = renderSettings; window.getLastSettings = getLastSettings;
  window.initSettingsViewEvents = initSettingsViewEvents;

  (function () {
    const saveBtn = byId("settings-save-header-save-button");
    if (saveBtn) saveBtn.addEventListener("click", saveSettingsPatch);
    const reloadBtn = byId("settings-save-header-reload-button");
    if (reloadBtn) reloadBtn.addEventListener("click", reloadSettingsFromDisk);
  }());
})();
