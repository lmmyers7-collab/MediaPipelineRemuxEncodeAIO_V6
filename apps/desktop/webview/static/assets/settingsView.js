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
let settingsViewParts = {};

function getLastSettings(...args) { return settingsViewParts.getLastSettings(...args); }
function readSettingsBuilderFloat(...args) { return settingsViewParts.readSettingsBuilderFloat(...args); }
function readSettingsBuilderNumber(...args) { return settingsViewParts.readSettingsBuilderNumber(...args); }
function renderSettingsActiveMediaPolicyHandoff(...args) { return settingsViewParts.renderSettingsActiveMediaPolicyHandoff(...args); }
function renderSettingsMediaPolicyCrossCheck(...args) { return settingsViewParts.renderSettingsMediaPolicyCrossCheck(...args); }
function renderSettingsPatchSummary(...args) { return settingsViewParts.renderSettingsPatchSummary(...args); }
function setSettingsBuilderControl(...args) { return settingsViewParts.setSettingsBuilderControl(...args); }
function settingsBoolValue(...args) { return settingsViewParts.settingsBoolValue(...args); }
function settingsBuilderInputValue(...args) { return settingsViewParts.settingsBuilderInputValue(...args); }
function settingsImpactGroupForKey(...args) { return settingsViewParts.settingsImpactGroupForKey(...args); }
function settingsPatchReviewCall(...args) { return settingsViewParts.settingsPatchReviewCall(...args); }
function syncSettingsRenameLogCaseButton(...args) { return settingsViewParts.syncSettingsRenameLogCaseButton(...args); }
function writeSettingsPatchJson(...args) { return settingsViewParts.writeSettingsPatchJson(...args); }

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
  const settingsViewState = {
    get lastSettingsValues() { return lastSettingsValues; }, set lastSettingsValues(value) { lastSettingsValues = value; },
    get lastSettingsFieldDefinitions() { return lastSettingsFieldDefinitions; }, set lastSettingsFieldDefinitions(value) { lastSettingsFieldDefinitions = value; },
    get lastSettingsFieldMap() { return lastSettingsFieldMap; }, set lastSettingsFieldMap(value) { lastSettingsFieldMap = value; },
    get settingsBuilderInitialized() { return settingsBuilderInitialized; }, set settingsBuilderInitialized(value) { settingsBuilderInitialized = value; },
    get settingsBuilderDirty() { return settingsBuilderDirty; }, set settingsBuilderDirty(value) { settingsBuilderDirty = value; },
    get lastSettings() { return lastSettings; }, set lastSettings(value) { lastSettings = value; },
    get settingsPatchPreviewRequestId() { return settingsPatchPreviewRequestId; }, set settingsPatchPreviewRequestId(value) { settingsPatchPreviewRequestId = value; },
    get selectedSettingsSaveReviewKey() { return selectedSettingsSaveReviewKey; }, set selectedSettingsSaveReviewKey(value) { selectedSettingsSaveReviewKey = value; },
    get selectedSettingsBackendResultKey() { return selectedSettingsBackendResultKey; }, set selectedSettingsBackendResultKey(value) { selectedSettingsBackendResultKey = value; },
    get selectedSettingsEffectivePolicyKey() { return selectedSettingsEffectivePolicyKey; }, set selectedSettingsEffectivePolicyKey(value) { selectedSettingsEffectivePolicyKey = value; },
    get settingsPatchTouched() { return settingsPatchTouched; }, set settingsPatchTouched(value) { settingsPatchTouched = value; },
    get lastSettingsPatchPreviewEvidence() { return lastSettingsPatchPreviewEvidence; }, set lastSettingsPatchPreviewEvidence(value) { lastSettingsPatchPreviewEvidence = value; },
    get lastSettingsPatchSaveEvidence() { return lastSettingsPatchSaveEvidence; }, set lastSettingsPatchSaveEvidence(value) { lastSettingsPatchSaveEvidence = value; },
    get lastSettingsReloadEvidence() { return lastSettingsReloadEvidence; }, set lastSettingsReloadEvidence(value) { lastSettingsReloadEvidence = value; },
    get settingsCommandInFlight() { return settingsCommandInFlight; }, set settingsCommandInFlight(value) { settingsCommandInFlight = value; },
    get settingsRenameLogCaseInFlight() { return settingsRenameLogCaseInFlight; }, set settingsRenameLogCaseInFlight(value) { settingsRenameLogCaseInFlight = value; },
    get settingsRenameLogCaseEventsBound() { return settingsRenameLogCaseEventsBound; }, set settingsRenameLogCaseEventsBound(value) { settingsRenameLogCaseEventsBound = value; },
    get settingsAdvancedToggleEventsBound() { return settingsAdvancedToggleEventsBound; }, set settingsAdvancedToggleEventsBound(value) { settingsAdvancedToggleEventsBound = value; },
    settingsPatchReview: {}, settingsPolicyImpact: {},
  };
  const settingsViewFacadeFactory = window.__settingsViewFacade || {};
  delete window.__settingsViewFacade;
  settingsViewParts = settingsViewFacadeFactory.createSettingsViewFacade({
    apiPost: typeof apiPost !== "undefined" ? apiPost : window.apiPost,
    appendCells: typeof appendCells !== "undefined" ? appendCells : window.appendCells,
    appendCommandResult: typeof appendCommandResult !== "undefined" ? appendCommandResult : window.appendCommandResult,
    applyAudioSettingsBuilderToPatch: typeof applyAudioSettingsBuilderToPatch !== "undefined" ? applyAudioSettingsBuilderToPatch : window.applyAudioSettingsBuilderToPatch,
    applyFileSafetySettingsBuilderToPatch: typeof applyFileSafetySettingsBuilderToPatch !== "undefined" ? applyFileSafetySettingsBuilderToPatch : window.applyFileSafetySettingsBuilderToPatch,
    applyNetworkSettingsBuilderToPatch: typeof applyNetworkSettingsBuilderToPatch !== "undefined" ? applyNetworkSettingsBuilderToPatch : window.applyNetworkSettingsBuilderToPatch,
    applyPendingPublishSettingsBuilderToPatch: typeof applyPendingPublishSettingsBuilderToPatch !== "undefined" ? applyPendingPublishSettingsBuilderToPatch : window.applyPendingPublishSettingsBuilderToPatch,
    applyQualityDetailSettingsBuilderToPatch: typeof applyQualityDetailSettingsBuilderToPatch !== "undefined" ? applyQualityDetailSettingsBuilderToPatch : window.applyQualityDetailSettingsBuilderToPatch,
    applyQueueSettingsBuilderToPatch: typeof applyQueueSettingsBuilderToPatch !== "undefined" ? applyQueueSettingsBuilderToPatch : window.applyQueueSettingsBuilderToPatch,
    applyRuntimeSettingsBuilderToPatch: typeof applyRuntimeSettingsBuilderToPatch !== "undefined" ? applyRuntimeSettingsBuilderToPatch : window.applyRuntimeSettingsBuilderToPatch,
    applySettingsFieldMetadataToControls: typeof applySettingsFieldMetadataToControls !== "undefined" ? applySettingsFieldMetadataToControls : window.applySettingsFieldMetadataToControls,
    applySubtitleSettingsBuilderToPatch: typeof applySubtitleSettingsBuilderToPatch !== "undefined" ? applySubtitleSettingsBuilderToPatch : window.applySubtitleSettingsBuilderToPatch,
    applyVideoDetailSettingsBuilderToPatch: typeof applyVideoDetailSettingsBuilderToPatch !== "undefined" ? applyVideoDetailSettingsBuilderToPatch : window.applyVideoDetailSettingsBuilderToPatch,
    audioSettingsBuilderFields: typeof audioSettingsBuilderFields !== "undefined" ? audioSettingsBuilderFields : window.audioSettingsBuilderFields,
    audioSettingsBuilderState: typeof audioSettingsBuilderState !== "undefined" ? audioSettingsBuilderState : window.audioSettingsBuilderState,
    byId: typeof byId !== "undefined" ? byId : window.byId,
    clearRows: typeof clearRows !== "undefined" ? clearRows : window.clearRows,
    fileSafetySettingsBuilderFields: typeof fileSafetySettingsBuilderFields !== "undefined" ? fileSafetySettingsBuilderFields : window.fileSafetySettingsBuilderFields,
    fileSafetySettingsBuilderState: typeof fileSafetySettingsBuilderState !== "undefined" ? fileSafetySettingsBuilderState : window.fileSafetySettingsBuilderState,
    finalLibraryPromotionSettingsBuilderFields: typeof finalLibraryPromotionSettingsBuilderFields !== "undefined" ? finalLibraryPromotionSettingsBuilderFields : window.finalLibraryPromotionSettingsBuilderFields,
    finalLibraryPromotionSettingsBuilderState: typeof finalLibraryPromotionSettingsBuilderState !== "undefined" ? finalLibraryPromotionSettingsBuilderState : window.finalLibraryPromotionSettingsBuilderState,
    formatConfigValue: typeof formatConfigValue !== "undefined" ? formatConfigValue : window.formatConfigValue,
    formatSettingsChoiceLabel: typeof formatSettingsChoiceLabel !== "undefined" ? formatSettingsChoiceLabel : window.formatSettingsChoiceLabel,
    formatSettingsListValue: typeof formatSettingsListValue !== "undefined" ? formatSettingsListValue : window.formatSettingsListValue,
    getCommandHistory: typeof getCommandHistory !== "undefined" ? getCommandHistory : window.getCommandHistory,
    handleSettingsAdvancedToggleClick: typeof handleSettingsAdvancedToggleClick !== "undefined" ? handleSettingsAdvancedToggleClick : window.handleSettingsAdvancedToggleClick,
    isSettingsCommand: typeof isSettingsCommand !== "undefined" ? isSettingsCommand : window.isSettingsCommand,
    jsonDetailText: typeof jsonDetailText !== "undefined" ? jsonDetailText : window.jsonDetailText,
    makeRowSelectable: typeof makeRowSelectable !== "undefined" ? makeRowSelectable : window.makeRowSelectable,
    markAudioSettingsBuilderDirty: typeof markAudioSettingsBuilderDirty !== "undefined" ? markAudioSettingsBuilderDirty : window.markAudioSettingsBuilderDirty,
    markFileSafetySettingsBuilderDirty: typeof markFileSafetySettingsBuilderDirty !== "undefined" ? markFileSafetySettingsBuilderDirty : window.markFileSafetySettingsBuilderDirty,
    markNetworkSettingsBuilderDirty: typeof markNetworkSettingsBuilderDirty !== "undefined" ? markNetworkSettingsBuilderDirty : window.markNetworkSettingsBuilderDirty,
    markPendingPublishSettingsBuilderDirty: typeof markPendingPublishSettingsBuilderDirty !== "undefined" ? markPendingPublishSettingsBuilderDirty : window.markPendingPublishSettingsBuilderDirty,
    markQualityDetailSettingsBuilderDirty: typeof markQualityDetailSettingsBuilderDirty !== "undefined" ? markQualityDetailSettingsBuilderDirty : window.markQualityDetailSettingsBuilderDirty,
    markQueueSettingsBuilderDirty: typeof markQueueSettingsBuilderDirty !== "undefined" ? markQueueSettingsBuilderDirty : window.markQueueSettingsBuilderDirty,
    markRuntimeSettingsBuilderDirty: typeof markRuntimeSettingsBuilderDirty !== "undefined" ? markRuntimeSettingsBuilderDirty : window.markRuntimeSettingsBuilderDirty,
    markSubtitleSettingsBuilderDirty: typeof markSubtitleSettingsBuilderDirty !== "undefined" ? markSubtitleSettingsBuilderDirty : window.markSubtitleSettingsBuilderDirty,
    markVideoDetailSettingsBuilderDirty: typeof markVideoDetailSettingsBuilderDirty !== "undefined" ? markVideoDetailSettingsBuilderDirty : window.markVideoDetailSettingsBuilderDirty,
    maybeShowSettingsRuntimeRestartNotice: typeof maybeShowSettingsRuntimeRestartNotice !== "undefined" ? maybeShowSettingsRuntimeRestartNotice : window.maybeShowSettingsRuntimeRestartNotice,
    networkSettingsBuilderFields: typeof networkSettingsBuilderFields !== "undefined" ? networkSettingsBuilderFields : window.networkSettingsBuilderFields,
    networkSettingsBuilderState: typeof networkSettingsBuilderState !== "undefined" ? networkSettingsBuilderState : window.networkSettingsBuilderState,
    parseSettingsListText: typeof parseSettingsListText !== "undefined" ? parseSettingsListText : window.parseSettingsListText,
    pendingPublishSettingsBuilderFields: typeof pendingPublishSettingsBuilderFields !== "undefined" ? pendingPublishSettingsBuilderFields : window.pendingPublishSettingsBuilderFields,
    pendingPublishSettingsBuilderState: typeof pendingPublishSettingsBuilderState !== "undefined" ? pendingPublishSettingsBuilderState : window.pendingPublishSettingsBuilderState,
    qualityDetailSettingsBuilderFields: typeof qualityDetailSettingsBuilderFields !== "undefined" ? qualityDetailSettingsBuilderFields : window.qualityDetailSettingsBuilderFields,
    qualityDetailSettingsBuilderState: typeof qualityDetailSettingsBuilderState !== "undefined" ? qualityDetailSettingsBuilderState : window.qualityDetailSettingsBuilderState,
    queueSettingsBuilderFields: typeof queueSettingsBuilderFields !== "undefined" ? queueSettingsBuilderFields : window.queueSettingsBuilderFields,
    queueSettingsBuilderState: typeof queueSettingsBuilderState !== "undefined" ? queueSettingsBuilderState : window.queueSettingsBuilderState,
    refreshAll: typeof refreshAll !== "undefined" ? refreshAll : window.refreshAll,
    refreshAudioSettingsBuilderChoices: typeof refreshAudioSettingsBuilderChoices !== "undefined" ? refreshAudioSettingsBuilderChoices : window.refreshAudioSettingsBuilderChoices,
    refreshSettingsBuilderChoices: typeof refreshSettingsBuilderChoices !== "undefined" ? refreshSettingsBuilderChoices : window.refreshSettingsBuilderChoices,
    refreshSettingsSelectChoices: typeof refreshSettingsSelectChoices !== "undefined" ? refreshSettingsSelectChoices : window.refreshSettingsSelectChoices,
    rejectSettingsCommandWhileBusy: typeof rejectSettingsCommandWhileBusy !== "undefined" ? rejectSettingsCommandWhileBusy : window.rejectSettingsCommandWhileBusy,
    renderAllLaunchPreflights: typeof renderAllLaunchPreflights !== "undefined" ? renderAllLaunchPreflights : window.renderAllLaunchPreflights,
    renderAudioSettingsBuilderGuidance: typeof renderAudioSettingsBuilderGuidance !== "undefined" ? renderAudioSettingsBuilderGuidance : window.renderAudioSettingsBuilderGuidance,
    renderFileSafetySettingsBuilderGuidance: typeof renderFileSafetySettingsBuilderGuidance !== "undefined" ? renderFileSafetySettingsBuilderGuidance : window.renderFileSafetySettingsBuilderGuidance,
    renderNetworkSettingsBuilderGuidance: typeof renderNetworkSettingsBuilderGuidance !== "undefined" ? renderNetworkSettingsBuilderGuidance : window.renderNetworkSettingsBuilderGuidance,
    renderPendingPublishSettingsBuilderGuidance: typeof renderPendingPublishSettingsBuilderGuidance !== "undefined" ? renderPendingPublishSettingsBuilderGuidance : window.renderPendingPublishSettingsBuilderGuidance,
    renderQualityDetailSettingsBuilderGuidance: typeof renderQualityDetailSettingsBuilderGuidance !== "undefined" ? renderQualityDetailSettingsBuilderGuidance : window.renderQualityDetailSettingsBuilderGuidance,
    renderQueueSettingsBuilderGuidance: typeof renderQueueSettingsBuilderGuidance !== "undefined" ? renderQueueSettingsBuilderGuidance : window.renderQueueSettingsBuilderGuidance,
    renderRuntimeSettingsBuilderGuidance: typeof renderRuntimeSettingsBuilderGuidance !== "undefined" ? renderRuntimeSettingsBuilderGuidance : window.renderRuntimeSettingsBuilderGuidance,
    renderSettingsAdvancedControls: typeof renderSettingsAdvancedControls !== "undefined" ? renderSettingsAdvancedControls : window.renderSettingsAdvancedControls,
    renderSettingsBdpgsOcrPathEvidence: typeof renderSettingsBdpgsOcrPathEvidence !== "undefined" ? renderSettingsBdpgsOcrPathEvidence : window.renderSettingsBdpgsOcrPathEvidence,
    renderSettingsEncoderCapabilityReport: typeof renderSettingsEncoderCapabilityReport !== "undefined" ? renderSettingsEncoderCapabilityReport : window.renderSettingsEncoderCapabilityReport,
    renderSettingsOperatorTrust: typeof renderSettingsOperatorTrust !== "undefined" ? renderSettingsOperatorTrust : window.renderSettingsOperatorTrust,
    renderSettingsOverview: typeof renderSettingsOverview !== "undefined" ? renderSettingsOverview : window.renderSettingsOverview,
    renderSettingsRawActionPlan: typeof renderSettingsRawActionPlan !== "undefined" ? renderSettingsRawActionPlan : window.renderSettingsRawActionPlan,
    renderSettingsRawTriage: typeof renderSettingsRawTriage !== "undefined" ? renderSettingsRawTriage : window.renderSettingsRawTriage,
    renderSettingsRows: typeof renderSettingsRows !== "undefined" ? renderSettingsRows : window.renderSettingsRows,
    renderSettingsSafetyLocks: typeof renderSettingsSafetyLocks !== "undefined" ? renderSettingsSafetyLocks : window.renderSettingsSafetyLocks,
    renderSettingsVobSubOcrPathEvidence: typeof renderSettingsVobSubOcrPathEvidence !== "undefined" ? renderSettingsVobSubOcrPathEvidence : window.renderSettingsVobSubOcrPathEvidence,
    renderSubtitleSettingsBuilderGuidance: typeof renderSubtitleSettingsBuilderGuidance !== "undefined" ? renderSubtitleSettingsBuilderGuidance : window.renderSubtitleSettingsBuilderGuidance,
    renderVideoDetailSettingsBuilderGuidance: typeof renderVideoDetailSettingsBuilderGuidance !== "undefined" ? renderVideoDetailSettingsBuilderGuidance : window.renderVideoDetailSettingsBuilderGuidance,
    runtimeSettingsBuilderFields: typeof runtimeSettingsBuilderFields !== "undefined" ? runtimeSettingsBuilderFields : window.runtimeSettingsBuilderFields,
    runtimeSettingsBuilderState: typeof runtimeSettingsBuilderState !== "undefined" ? runtimeSettingsBuilderState : window.runtimeSettingsBuilderState,
    scheduleSettingsPostSaveRefresh: typeof scheduleSettingsPostSaveRefresh !== "undefined" ? scheduleSettingsPostSaveRefresh : window.scheduleSettingsPostSaveRefresh,
    setSettingsCommandBusy: typeof setSettingsCommandBusy !== "undefined" ? setSettingsCommandBusy : window.setSettingsCommandBusy,
    setSettingsRows: typeof setSettingsRows !== "undefined" ? setSettingsRows : window.setSettingsRows,
    setText: typeof setText !== "undefined" ? setText : window.setText,
    SETTINGS_PREVIEW_POST_TIMEOUT_MS: typeof SETTINGS_PREVIEW_POST_TIMEOUT_MS !== "undefined" ? SETTINGS_PREVIEW_POST_TIMEOUT_MS : window.SETTINGS_PREVIEW_POST_TIMEOUT_MS,
    SETTINGS_SAVE_POST_TIMEOUT_MS: typeof SETTINGS_SAVE_POST_TIMEOUT_MS !== "undefined" ? SETTINGS_SAVE_POST_TIMEOUT_MS : window.SETTINGS_SAVE_POST_TIMEOUT_MS,
    settingsBuilderConfigValue: typeof settingsBuilderConfigValue !== "undefined" ? settingsBuilderConfigValue : window.settingsBuilderConfigValue,
    settingsBuilderFields: typeof settingsBuilderFields !== "undefined" ? settingsBuilderFields : window.settingsBuilderFields,
    settingsCommandHistoryLine: typeof settingsCommandHistoryLine !== "undefined" ? settingsCommandHistoryLine : window.settingsCommandHistoryLine,
    settingsFieldAllowedValues: typeof settingsFieldAllowedValues !== "undefined" ? settingsFieldAllowedValues : window.settingsFieldAllowedValues,
    settingsFieldDefinition: typeof settingsFieldDefinition !== "undefined" ? settingsFieldDefinition : window.settingsFieldDefinition,
    settingsFieldLabel: typeof settingsFieldLabel !== "undefined" ? settingsFieldLabel : window.settingsFieldLabel,
    settingsFriendlyPersistedKeyAliases: typeof settingsFriendlyPersistedKeyAliases !== "undefined" ? settingsFriendlyPersistedKeyAliases : window.settingsFriendlyPersistedKeyAliases,
    settingsHasBackendFieldDefinitions: typeof settingsHasBackendFieldDefinitions !== "undefined" ? settingsHasBackendFieldDefinitions : window.settingsHasBackendFieldDefinitions,
    settingsImpactGroups: typeof settingsImpactGroups !== "undefined" ? settingsImpactGroups : window.settingsImpactGroups,
    settingsPatchComplexBackendKeys: typeof settingsPatchComplexBackendKeys !== "undefined" ? settingsPatchComplexBackendKeys : window.settingsPatchComplexBackendKeys,
    settingsPatchLocalValidationHintLines: typeof settingsPatchLocalValidationHintLines !== "undefined" ? settingsPatchLocalValidationHintLines : window.settingsPatchLocalValidationHintLines,
    settingsPersistedKeyDisplayList: typeof settingsPersistedKeyDisplayList !== "undefined" ? settingsPersistedKeyDisplayList : window.settingsPersistedKeyDisplayList,
    settingsPostErrorMessage: typeof settingsPostErrorMessage !== "undefined" ? settingsPostErrorMessage : window.settingsPostErrorMessage,
    settingsResultStatusLabel: typeof settingsResultStatusLabel !== "undefined" ? settingsResultStatusLabel : window.settingsResultStatusLabel,
    settingsRuntimeRestartConfirmationLine: typeof settingsRuntimeRestartConfirmationLine !== "undefined" ? settingsRuntimeRestartConfirmationLine : window.settingsRuntimeRestartConfirmationLine,
    settingsRuntimeRestartNoticeLines: typeof settingsRuntimeRestartNoticeLines !== "undefined" ? settingsRuntimeRestartNoticeLines : window.settingsRuntimeRestartNoticeLines,
    settingsSpecificImpactHints: typeof settingsSpecificImpactHints !== "undefined" ? settingsSpecificImpactHints : window.settingsSpecificImpactHints,
    settingsValuesEqual: typeof settingsValuesEqual !== "undefined" ? settingsValuesEqual : window.settingsValuesEqual,
    subtitleSettingsBuilderFields: typeof subtitleSettingsBuilderFields !== "undefined" ? subtitleSettingsBuilderFields : window.subtitleSettingsBuilderFields,
    subtitleSettingsBuilderState: typeof subtitleSettingsBuilderState !== "undefined" ? subtitleSettingsBuilderState : window.subtitleSettingsBuilderState,
    syncAudioSettingsBuilderFromConfig: typeof syncAudioSettingsBuilderFromConfig !== "undefined" ? syncAudioSettingsBuilderFromConfig : window.syncAudioSettingsBuilderFromConfig,
    syncFileSafetySettingsBuilderFromConfig: typeof syncFileSafetySettingsBuilderFromConfig !== "undefined" ? syncFileSafetySettingsBuilderFromConfig : window.syncFileSafetySettingsBuilderFromConfig,
    syncNetworkSettingsBuilderFromConfig: typeof syncNetworkSettingsBuilderFromConfig !== "undefined" ? syncNetworkSettingsBuilderFromConfig : window.syncNetworkSettingsBuilderFromConfig,
    syncPendingPublishSettingsBuilderFromConfig: typeof syncPendingPublishSettingsBuilderFromConfig !== "undefined" ? syncPendingPublishSettingsBuilderFromConfig : window.syncPendingPublishSettingsBuilderFromConfig,
    syncQualityDetailSettingsBuilderFromConfig: typeof syncQualityDetailSettingsBuilderFromConfig !== "undefined" ? syncQualityDetailSettingsBuilderFromConfig : window.syncQualityDetailSettingsBuilderFromConfig,
    syncQueueSettingsBuilderFromConfig: typeof syncQueueSettingsBuilderFromConfig !== "undefined" ? syncQueueSettingsBuilderFromConfig : window.syncQueueSettingsBuilderFromConfig,
    syncRuntimeSettingsBuilderFromConfig: typeof syncRuntimeSettingsBuilderFromConfig !== "undefined" ? syncRuntimeSettingsBuilderFromConfig : window.syncRuntimeSettingsBuilderFromConfig,
    syncSubtitleSettingsBuilderFromConfig: typeof syncSubtitleSettingsBuilderFromConfig !== "undefined" ? syncSubtitleSettingsBuilderFromConfig : window.syncSubtitleSettingsBuilderFromConfig,
    syncVideoDetailSettingsBuilderFromConfig: typeof syncVideoDetailSettingsBuilderFromConfig !== "undefined" ? syncVideoDetailSettingsBuilderFromConfig : window.syncVideoDetailSettingsBuilderFromConfig,
    updateTableStatusLegend: typeof updateTableStatusLegend !== "undefined" ? updateTableStatusLegend : window.updateTableStatusLegend,
    videoDetailSettingsBuilderFields: typeof videoDetailSettingsBuilderFields !== "undefined" ? videoDetailSettingsBuilderFields : window.videoDetailSettingsBuilderFields,
    videoDetailSettingsBuilderState: typeof videoDetailSettingsBuilderState !== "undefined" ? videoDetailSettingsBuilderState : window.videoDetailSettingsBuilderState,
  }, settingsViewState);
  const {
    addFinalLibraryPromotionRule, appendSettingsRiskSummaryLines, appendSettingsSaveReviewCell, applySettingsBuilderToPatch, blockStaleLibraryProfilesPatch,
    browseFinalLibraryPromotionRulePath, browseSettingsPath, clearSettingsPatchCandidate, collectFinalLibraryPromotionSettingsPatch, collectSettingsBuilderPatch,
    ensureSettingsSaveReviewDialogGlobal, finalLibraryPromotionBrowseDetailLines, finalLibraryPromotionSettingsResultLines, flushDirtySettingsBuilders, initSettingsRenameLogCaseEvents,
    initSettingsViewEvents, markFinalLibraryPromotionSettingsBuilderDirty, markSettingsBuilderDirty, markSettingsPatchTouched, mergeRenameCleaningFiltersForSave,
    openSettingsSaveReviewDialog, parseSettingsPatchJson, previewFinalLibraryPromotionSettings, previewSettingsPatch, recordSettingsBuilderFlushFailure,
    reloadSettingsFromDisk, renderFinalLibraryPromotionSettingsGuidance, renderSettings, renderSettingsBackendMediaPolicyReadiness, renderSettingsBackendResultForError,
    renderSettingsBackendResultFromEntries, renderSettingsBuilderGuidance, renderSettingsEffectivePolicyTrustForError, renderSettingsEffectivePolicyTrustFromEntries, renderSettingsLaunchImpactHandoffForError,
    renderSettingsLaunchImpactHandoffFromEntries, renderSettingsPatchImpactSummaryForError, renderSettingsPatchImpactSummaryFromEntries, renderSettingsPatchSaveReadinessFromEntries, renderSettingsPolicyDeltaForError,
    renderSettingsPolicyDeltaFromEntries, renderSettingsSaveProgress, renderSettingsSaveReviewDialogRows, renderSettingsSaveReviewFromEntries, resetSettingsBuilderSyncState,
    saveFinalLibraryPromotionSettings, saveRenameCleaningFiltersFromSettingsSave, saveSettingsPatch, setFinalLibraryPromotionStatus, setSettingsRenameLogCaseBusy,
    settingsActiveMediaPolicyRows, settingsActiveMediaPolicyStatus, settingsActiveMediaPolicySummaryLines, settingsBackendMediaPolicyReadiness, settingsBackendMediaPolicyStatus,
    settingsBackendMediaPolicySummaryLines, settingsBackendPolicyImpact, settingsBackendResultCall, settingsBackendResultDetailLines, settingsBackendResultRowKey,
    settingsBackendResultRows, settingsBackendResultStatus, settingsBackendResultSummaryLines, settingsBrowsePathDetailLines, settingsBuilderFlushFailureMessage,
    settingsCommandProgressBars, settingsCurrentPatchSignature, settingsEffectivePolicyDetailLines, settingsEffectivePolicyRows, settingsEffectivePolicySummaryLines,
    settingsEffectivePolicyTrustStatus, settingsLaunchImpactRows, settingsLaunchImpactStatus, settingsLaunchImpactSummaryLines, settingsLibraryProfilePatchStateKind,
    settingsMediaPolicyRows, settingsMediaPolicyStatus, settingsMediaPolicySummaryLines, settingsPatchCandidateValue, settingsPatchEffectiveChangedEntries,
    settingsPatchHasStaleLibraryProfiles, settingsPatchHasUnsavedChanges, settingsPatchImpactEntries, settingsPatchIsTouched, settingsPatchListValue,
    settingsPatchRequestExtras, settingsPatchRequestSignature, settingsPatchReviewFunction, settingsPatchSaveReadinessIssues, settingsPatchSaveReadinessStatus,
    settingsPatchSignature, settingsPolicyDeltaRows, settingsPolicyDeltaStatus, settingsPolicyDeltaSummaryLines, settingsPolicyImpactCall,
    settingsPolicyImpactDo, settingsPolicyImpactFunction, settingsProfileSummaryLines, settingsProgressDetailLines, settingsRawConfigValue,
    settingsRenameLogCaseInput, settingsRenameLogCaseInteger, settingsRenameLogCasePayload, settingsRenameLogCaseRequiredIssues, settingsRenameLogCaseValue,
    settingsReviewDigestShort, settingsSaveActualKeys, settingsSavePreviewDetailLines, settingsSaveReviewBackendEntries, settingsSaveReviewBackendEntryForKey,
    settingsSaveReviewCanonicalProfileId, settingsSaveReviewCellText, settingsSaveReviewDetailLines, settingsSaveReviewEntryCellText, settingsSaveReviewLabel,
    settingsSaveReviewLibraryProfileCellText, settingsSaveReviewLibraryProfileDetailLines, settingsSaveReviewLibraryProfileDiffEntries, settingsSaveReviewLibraryProfiles, settingsSaveReviewLibraryProfileSummary,
    settingsSaveReviewLimitedText, settingsSaveReviewModalHost, settingsSaveReviewObjectValue, settingsSaveReviewOptionState, settingsSaveReviewOverrideMap,
    settingsSaveReviewPrimitiveText, settingsSaveReviewProfileId, settingsSaveReviewProfileLabel, settingsSaveReviewProfileMap, settingsSaveReviewProfileOverrideEntries,
    settingsSaveReviewRenameFilterLabel, settingsSaveReviewRenameOptionDictionaryText, settingsSaveReviewRenameRemoveTermsText, settingsSaveReviewRenameTermDictionaryText, settingsSaveReviewRows,
    settingsSaveReviewSourceLabel, settingsSaveReviewStatus, settingsSaveReviewStatusLabel, settingsSaveReviewTermDeltas, settingsSaveReviewTermList,
    settingsSaveReviewTermMap, settingsSaveReviewValuesDiffer, settingsSaveReviewValueText, settingsStableJsonValue, settingsUniqueKeys,
    submitSettingsRenameLogCase, syncFinalLibraryPromotionSettingsBuilderFromConfig, syncSaveHeaderStatus, syncSettingsBuilderFromConfig, validateCurrentSettings,
  } = settingsViewParts;

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
