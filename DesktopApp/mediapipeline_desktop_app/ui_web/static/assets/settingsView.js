(function () {
  const settingsOverview = window.mediaPipelineSettingsOverview || {};
  const configValue = window.configValue || settingsOverview.configValue || function () { return "(not set)"; };
  const buildSettingsOverviewRows = window.buildSettingsOverviewRows || settingsOverview.buildSettingsOverviewRows || function () { return []; };
  const renderSettingsOverview = window.renderSettingsOverview || settingsOverview.renderSettingsOverview || function () {};
  const renderSettingsOperatorTrust = window.renderSettingsOperatorTrust || settingsOverview.renderSettingsOperatorTrust || function () {};
  const settingsCommandHistory = window.mediaPipelineSettingsCommandHistory || {};
  const isSettingsCommand = window.isSettingsCommand || settingsCommandHistory.isSettingsCommand || function () { return false; };
  const settingsCommandHistoryLine = window.settingsCommandHistoryLine || settingsCommandHistory.settingsCommandHistoryLine || function () { return ""; };
  const renderSettingsCommandHistory = window.renderSettingsCommandHistory || settingsCommandHistory.renderSettingsCommandHistory || function () {};

  function settingsBuilderCoveredKeys() {
    return new Set([
      ...settingsBuilderFields,
      ...fileSafetySettingsBuilderFields,
      ...networkSettingsBuilderFields,
      ...queueSettingsBuilderFields,
      ...videoDetailSettingsBuilderFields,
      ...runtimeSettingsBuilderFields,
      ...pendingPublishSettingsBuilderFields,
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
const runtimeSettingsBuilderState = { initialized: false, dirty: false };
const pendingPublishSettingsBuilderState = { initialized: false, dirty: false };
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
  "settings-preview-patch-button",
  "settings-save-patch-button",
  "network-settings-preview-button",
  "network-settings-save-button",
];
let settingsCommandInFlight = false;

function setSettingsCommandBusy(isBusy) {
  settingsCommandInFlight = Boolean(isBusy);
  settingsCommandButtonIds.forEach((id) => {
    const button = byId(id);
    if (button) button.disabled = settingsCommandInFlight;
  });
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

const settingsMetadata = window.mediaPipelineSettingsMetadata || {};
const settingsBuilderFields = settingsMetadata.settingsBuilderFields || [];
const fileSafetySettingsBuilderFields = settingsMetadata.fileSafetySettingsBuilderFields || [];
const networkSettingsBuilderFields = settingsMetadata.networkSettingsBuilderFields || [];
const queueSettingsBuilderFields = settingsMetadata.queueSettingsBuilderFields || [];
const videoDetailSettingsBuilderFields = settingsMetadata.videoDetailSettingsBuilderFields || [];
const runtimeSettingsBuilderFields = settingsMetadata.runtimeSettingsBuilderFields || [];
const pendingPublishSettingsBuilderFields = settingsMetadata.pendingPublishSettingsBuilderFields || [];
const subtitleSettingsBuilderFields = settingsMetadata.subtitleSettingsBuilderFields || [];
const audioSettingsBuilderFields = settingsMetadata.audioSettingsBuilderFields || [];
const settingsSafetyLockDefinitions = settingsMetadata.settingsSafetyLockDefinitions || [];
const settingsImpactGroups = settingsMetadata.settingsImpactGroups || [];
const settingsSpecificImpactHints = settingsMetadata.settingsSpecificImpactHints || {};
const settingsChoiceLabels = settingsMetadata.settingsChoiceLabels || {};

function settingsBuilderConfigValue(key, fallback) {
  const value = lastSettingsValues ? lastSettingsValues[key] : undefined;
  if (value === undefined || value === null || value === "") return fallback;
  return value;
}

function settingsFieldDefinition(key) {
  return lastSettingsFieldMap ? lastSettingsFieldMap[key] : null;
}

function formatSettingsChoiceLabel(value) {
  const text = String(value || "");
  if (settingsChoiceLabels[text]) return settingsChoiceLabels[text];
  return text.replace(/_/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function refreshSettingsSelectChoices(fields) {
  fields.forEach(([key, id]) => {
    const element = byId(id);
    const field = settingsFieldDefinition(key);
    if (!element || element.tagName !== "SELECT" || !Array.isArray(field?.choices)) return;
    const current = element.value;
    element.replaceChildren();
    field.choices.forEach((choice) => {
      const option = document.createElement("option");
      option.value = String(choice);
      option.textContent = formatSettingsChoiceLabel(choice);
      if (field.choice_help && field.choice_help[String(choice)]) {
        option.title = field.choice_help[String(choice)];
      }
      element.appendChild(option);
    });
    const choices = field.choices.map((choice) => String(choice));
    element.value = choices.includes(current) ? current : String(field.default || choices[0] || "");
  });
}

function refreshSettingsBuilderChoices() {
  refreshSettingsSelectChoices(settingsBuilderFields);
}

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
    byId,
    formatSettingsChoiceLabel,
    formatSettingsListValue,
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
  const element = byId(id);
  if (!element) return;
  const normalized = String(value ?? "");
  if (element.tagName === "SELECT") {
    const optionValues = Array.from(element.options || []).map((option) => option.value);
    element.value = optionValues.includes(normalized) ? normalized : (optionValues[0] || "");
    return;
  }
  element.value = normalized;
}

function syncSettingsBuilderFromConfig() {
  refreshSettingsBuilderChoices();
  setSettingsBuilderControl("settings-builder-routing-profile", settingsBuilderConfigValue("RoutingProfile", "plex_direct_stream"));
  setSettingsBuilderControl("settings-builder-size-guard", settingsBuilderConfigValue("SizeGuardMode", "advisory"));
  setSettingsBuilderControl("settings-builder-encode-tuning", settingsBuilderConfigValue("EncodeTuningPreset", "balanced_nvenc"));
  setSettingsBuilderControl("settings-builder-encode-ladder", settingsBuilderConfigValue("EncodeLadder", "auto"));
  setSettingsBuilderControl("settings-builder-video-codec", settingsBuilderConfigValue("VideoCodec", "hevc_nvenc"));
  setSettingsBuilderControl("settings-builder-output-container", settingsBuilderConfigValue("OutputContainer", "mkv"));
  setSettingsBuilderControl("settings-builder-max-growth", settingsBuilderConfigValue("MaxEncodeGrowthPercent", 5));
  setSettingsBuilderControl("settings-builder-compat-growth", settingsBuilderConfigValue("CompatibilityEncodeGrowthPercent", 15));
  setSettingsBuilderControl("settings-builder-movie-threshold", settingsBuilderConfigValue("EncodeThresholdGB", 8));
  setSettingsBuilderControl("settings-builder-tv-threshold", settingsBuilderConfigValue("TVEncodeThresholdGB", 3));
  settingsBuilderInitialized = true;
  settingsBuilderDirty = false;
  setText("settings-builder-status", "Loaded current values");
  renderSettingsBuilderGuidance();
  renderSettingsActiveMediaPolicyHandoff();
}

function markSettingsBuilderDirty() {
  settingsBuilderInitialized = true;
  settingsBuilderDirty = true;
  setText("settings-builder-status", "Editing builder values");
  renderSettingsBuilderGuidance();
  renderSettingsActiveMediaPolicyHandoff();
}

function settingsBuilderInputValue(id) {
  return String(byId(id)?.value ?? "").trim();
}

function readSettingsBuilderNumber(id, label) {
  const raw = settingsBuilderInputValue(id);
  if (!raw) throw new Error(`${label} is required.`);
  const value = Number(raw);
  if (!Number.isFinite(value) || value < 0) throw new Error(`${label} must be zero or higher.`);
  return Math.round(value);
}

function readSettingsBuilderFloat(id, label) {
  const raw = settingsBuilderInputValue(id);
  if (!raw) throw new Error(`${label} is required.`);
  const value = Number(raw);
  if (!Number.isFinite(value) || value < 0) throw new Error(`${label} must be zero or higher.`);
  return value;
}

function settingsRawConfigValue(key) {
  if (Object.prototype.hasOwnProperty.call(lastSettingsValues || {}, key)) return lastSettingsValues[key];
  const match = Object.keys(lastSettingsValues || {}).find((item) => item.toLowerCase() === String(key).toLowerCase());
  return match ? lastSettingsValues[match] : undefined;
}

function parseSettingsPatchJson() {
  const raw = byId("settings-patch-json")?.value || "{}";
  const parsed = JSON.parse(raw);
  if (!parsed || Array.isArray(parsed) || typeof parsed !== "object") {
    throw new Error("Patch JSON must be an object of config keys and values.");
  }
  return parsed;
}

function markSettingsPatchTouched() {
  settingsPatchTouched = true;
}

function settingsPatchIsTouched() {
  return settingsPatchTouched;
}

function settingsPatchEffectiveChangedEntries() {
  if (!settingsPatchTouched) return [];
  return settingsPatchImpactEntries(parseSettingsPatchJson()).filter((entry) => entry.changed);
}

function settingsPatchHasUnsavedChanges() {
  return settingsPatchEffectiveChangedEntries().length > 0;
}

function readSettingsPatchJsonForMerge() {
  try {
    return parseSettingsPatchJson();
  } catch {
    return {};
  }
  return {};
}

function writeSettingsPatchJson(patch, detail) {
  const textarea = byId("settings-patch-json");
  if (!textarea) return;
  const merged = { ...readSettingsPatchJsonForMerge(), ...patch };
  markSettingsPatchTouched();
  textarea.value = JSON.stringify(merged, null, 2);
  setText("settings-patch-status", "Patch built");
  setText("settings-patch-detail", detail || "Builder updated Changes JSON. Preview or Save still uses backend validation.");
  renderSettingsPatchSummary();
  if (typeof renderAllLaunchPreflights === "function") renderAllLaunchPreflights();
}

function collectSettingsBuilderPatch() {
  const patch = {
    RoutingProfile: settingsBuilderInputValue("settings-builder-routing-profile"),
    SizeGuardMode: settingsBuilderInputValue("settings-builder-size-guard"),
    EncodeTuningPreset: settingsBuilderInputValue("settings-builder-encode-tuning"),
    EncodeLadder: settingsBuilderInputValue("settings-builder-encode-ladder"),
    VideoCodec: settingsBuilderInputValue("settings-builder-video-codec"),
    OutputContainer: settingsBuilderInputValue("settings-builder-output-container"),
    MaxEncodeGrowthPercent: readSettingsBuilderNumber("settings-builder-max-growth", "Normal growth percent"),
    CompatibilityEncodeGrowthPercent: readSettingsBuilderNumber("settings-builder-compat-growth", "Compatibility growth percent"),
    EncodeThresholdGB: readSettingsBuilderNumber("settings-builder-movie-threshold", "Movie threshold GB"),
    TVEncodeThresholdGB: readSettingsBuilderNumber("settings-builder-tv-threshold", "TV threshold GB"),
  };
  Object.entries(patch).forEach(([key, value]) => {
    if (typeof value === "string" && !value.trim()) {
      throw new Error(`${key} must be selected.`);
    }
  });
  return patch;
}

function applySettingsBuilderToPatch() {
  let patch;
  try {
    patch = collectSettingsBuilderPatch();
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    setText("settings-builder-status", "Invalid builder value");
    setText("settings-patch-status", "Builder invalid");
    setText("settings-patch-detail", message);
    return;
  }
  writeSettingsPatchJson(patch, "Structured builder merged routing, size, and encoder keys into Changes JSON. Preview or Save still uses backend validation.");
  settingsBuilderInitialized = true;
  settingsBuilderDirty = true;
  setText("settings-builder-status", `${Object.keys(patch).length} patch keys ready`);
  renderSettingsBuilderGuidance();
  renderSettingsActiveMediaPolicyHandoff();
}

function settingsMediaPolicyList(id, key, fallback) {
  const element = byId(id);
  if (element) return parseSettingsListText(element.value || "");
  return parseSettingsListText(formatSettingsListValue(settingsBuilderConfigValue(key, fallback)));
}

function settingsMediaPolicyBool(id, key, fallback) {
  const element = byId(id);
  if (element) return element.checked === true;
  const value = settingsBuilderConfigValue(key, fallback);
  return value === true || String(value).toLowerCase() === "true";
}

function settingsMediaPolicyValue(id, key, fallback) {
  const element = byId(id);
  if (element) return settingsBuilderInputValue(id);
  return String(settingsBuilderConfigValue(key, fallback) ?? "");
}

function settingsMediaPolicyNumber(id, key, fallback) {
  const raw = settingsMediaPolicyValue(id, key, fallback);
  const value = Number(raw);
  return Number.isFinite(value) ? value : Number(fallback || 0);
}

function settingsMediaPolicyLanguageGaps(base, candidate) {
  const normalizedBase = new Set((base || []).map((item) => String(item).toLowerCase()));
  return (candidate || []).filter((item) => !normalizedBase.has(String(item).toLowerCase()));
}

function settingsMediaPolicyRows() {
  const keepLanguages = settingsMediaPolicyList("settings-subtitle-languages", "SubKeepLanguages", ["eng", "und"]);
  const tx3gLanguages = settingsMediaPolicyList("settings-subtitle-tx3g-languages", "Tx3gExtractLanguages", ["eng", "und"]);
  const bdpgsLanguages = settingsMediaPolicyList("settings-subtitle-bdpgs-languages", "BdpgsExtractLanguages", ["eng", "und"]);
  const convertTx3g = settingsMediaPolicyBool("settings-subtitle-convert-tx3g", "ConvertTx3gToSrt", true);
  const dropTx3g = settingsMediaPolicyBool("settings-subtitle-drop-tx3g", "DropTx3gAfterConversion", false);
  const sidecarTx3g = settingsMediaPolicyBool("settings-subtitle-sidecar-tx3g", "CreateExternalTx3gSrtSidecars", false);
  const preserveTx3gSrt = settingsMediaPolicyBool("settings-subtitle-preserve-tx3g-srt", "Tx3gPreserveExistingSrt", true);
  const convertBdpgs = settingsMediaPolicyBool("settings-subtitle-convert-bdpgs", "ConvertBdpgsToSrt", true);
  const dropBdpgs = settingsMediaPolicyBool("settings-subtitle-drop-bdpgs", "DropBdpgsAfterConversion", false);
  const dropAss = settingsMediaPolicyBool("settings-subtitle-drop-ass", "DropAssAfterConversion", false);
  const stripFormatting = settingsMediaPolicyBool("settings-subtitle-strip-formatting", "StripFormatting", true);
  const removeKaraoke = settingsMediaPolicyBool("settings-subtitle-remove-karaoke", "RemoveKaraoke", true);
  const keepSigns = settingsMediaPolicyBool("settings-subtitle-keep-signs", "KeepSignsAndSongs", true);
  const extractTimeout = settingsMediaPolicyNumber("settings-subtitle-extract-timeout", "SubtitleExtractTimeoutSeconds", 180);
  const probeTimeout = settingsMediaPolicyNumber("settings-subtitle-probe-timeout", "SubtitleProbeTimeoutSeconds", 30);
  const bdpgsTimeout = settingsMediaPolicyNumber("settings-subtitle-bdpgs-timeout", "BdpgsOcrTimeoutSeconds", 1800);
  const passthroughProfile = settingsMediaPolicyValue("settings-audio-passthrough-profile", "AudioPassthroughProfile", "plex_balanced") || "plex_balanced";
  const compatibleCodecs = settingsMediaPolicyList("settings-audio-compatible-codecs", "CompatibleAudioCodecs", ["aac", "ac3", "eac3", "mp3", "opus", "vorbis"]);
  const defaultAudioLanguages = settingsMediaPolicyList("settings-audio-preferred-languages", "PreferredDefaultAudioLanguages", ["english"]);
  const transcodeCodec = settingsMediaPolicyValue("settings-audio-transcode-codec", "AudioTranscodeCodec", "eac3") || "eac3";
  const transcodeBitrate = settingsMediaPolicyValue("settings-audio-transcode-bitrate", "AudioTranscodeBitrate", "640k") || "640k";
  const autoBitrate = settingsMediaPolicyBool("settings-audio-auto-bitrate", "AudioTranscodeAutoBitrateByChannels", false);
  const downmixMode = settingsMediaPolicyValue("settings-audio-downmix-mode", "AudioDownmixMode", "max_channels") || "max_channels";
  const maxChannels = settingsMediaPolicyNumber("settings-audio-max-channels", "AudioMaxChannels", 6);
  const allowNoAudio = settingsMediaPolicyBool("settings-audio-allow-no-audio", "AllowNoAudio", false);
  const tx3gGaps = settingsMediaPolicyLanguageGaps(keepLanguages, tx3gLanguages);
  const bdpgsGaps = settingsMediaPolicyLanguageGaps(keepLanguages, bdpgsLanguages);
  const rows = [
    {
      area: "Subtitle language routing",
      posture: !keepLanguages.length ? "warning" : (tx3gGaps.length || bdpgsGaps.length ? "review" : "coherent"),
      evidence: `keep=${keepLanguages.join(", ") || "(empty)"}; TX3G=${tx3gLanguages.join(", ") || "(empty)"}; BDPGS=${bdpgsLanguages.join(", ") || "(empty)"}`,
      action: tx3gGaps.length || bdpgsGaps.length
        ? `Review extract-only language gaps: TX3G ${tx3gGaps.join(", ") || "none"}; BDPGS ${bdpgsGaps.join(", ") || "none"}.`
        : "Preferred subtitle language policy is visible before backend preview/save.",
    },
    {
      area: "TX3G / mov_text SRT generation",
      posture: dropTx3g && !convertTx3g ? "blocked" : (!convertTx3g || dropTx3g ? "review" : "coherent"),
      evidence: `convert=${convertTx3g ? "on" : "off"}; drop original=${dropTx3g ? "on" : "off"}; sidecar=${sidecarTx3g ? "on" : "off"}; preserve existing SRT=${preserveTx3gSrt ? "on" : "off"}`,
      action: dropTx3g && !convertTx3g
        ? "Do not drop TX3G while conversion is disabled; that can remove subtitles without creating SRT."
        : "Default Plex posture is add SRT for preferred languages while preserving original TX3G unless drop is intentional.",
    },
    {
      area: "BDPGS OCR to SRT",
      posture: dropBdpgs && !convertBdpgs ? "blocked" : (!convertBdpgs || dropBdpgs ? "review" : "coherent"),
      evidence: `OCR=${convertBdpgs ? "on" : "off"}; drop original=${dropBdpgs ? "on" : "off"}; timeout=${bdpgsTimeout}s`,
      action: dropBdpgs && !convertBdpgs
        ? "Do not drop BDPGS while OCR is disabled; that can remove image subtitles without creating SRT."
        : "Preferred-language BDPGS should generate SRT for Plex while original image subtitles stay unless drop is intentional.",
    },
    {
      area: "ASS / SSA preservation",
      posture: dropAss ? "review" : "coherent",
      evidence: `drop original=${dropAss ? "on" : "off"}; strip formatting=${stripFormatting ? "on" : "off"}; remove karaoke=${removeKaraoke ? "on" : "off"}; keep signs/songs=${keepSigns ? "on" : "off"}`,
      action: "SRT conversion can strip styling through filters, but ASS/SSA originals should remain available unless the drop toggle is intentional.",
    },
    {
      area: "Subtitle timeout posture",
      posture: extractTimeout <= 0 || probeTimeout <= 0 || bdpgsTimeout <= 0 ? "blocked" : (extractTimeout < 60 || probeTimeout < 10 || bdpgsTimeout < 600 ? "review" : "coherent"),
      evidence: `extract=${extractTimeout}s; probe=${probeTimeout}s; BDPGS OCR=${bdpgsTimeout}s`,
      action: "Short timeout ceilings can turn slow disks, network shares, or OCR-heavy files into manual-review failures.",
    },
    {
      area: "Audio language/default routing",
      posture: defaultAudioLanguages.length ? "coherent" : "review",
      evidence: `preferred defaults=${defaultAudioLanguages.join(", ") || "(empty)"}`,
      action: "Preferred default audio languages make default-track behavior predictable when sources have mixed or missing metadata.",
    },
    {
      area: "Audio passthrough/transcode policy",
      posture: passthroughProfile === "custom_codec_list" && !compatibleCodecs.length ? "blocked" : (passthroughProfile === "lossless_passthrough" || passthroughProfile === "custom_codec_list" ? "review" : "coherent"),
      evidence: `profile=${formatSettingsChoiceLabel(passthroughProfile)}; codecs=${compatibleCodecs.join(", ") || "(empty)"}; transcode=${formatSettingsChoiceLabel(transcodeCodec)} ${autoBitrate ? "auto bitrate by channels" : transcodeBitrate}`,
      action: "Custom/lossless passthrough can be valid, but it should be intentional because it changes Plex Direct Play predictability.",
    },
    {
      area: "Audio channel / no-audio safety",
      posture: allowNoAudio ? "blocked" : (downmixMode === "stereo" || maxChannels < 6 ? "review" : "coherent"),
      evidence: `downmix=${formatSettingsChoiceLabel(downmixMode)}; max channels=${maxChannels}; allow no-audio=${allowNoAudio ? "on" : "off"}`,
      action: allowNoAudio
        ? "No-audio output is unsafe for normal Plex publishing and should stay disabled unless this is a deliberate manual-review case."
        : "Channel caps/downmix settings should match the operator's compatibility target before staging a patch.",
    },
  ];
  return rows;
}

function settingsMediaPolicyStatus(rows = settingsMediaPolicyRows()) {
  if (rows.some((row) => row.posture === "blocked")) return "Blocked review";
  if (rows.some((row) => row.posture === "warning" || row.posture === "review")) return "Review";
  return rows.length ? "Coherent" : "No policy";
}

function settingsActiveMediaPolicyRows() {
  const routingProfile = settingsMediaPolicyValue("settings-builder-routing-profile", "RoutingProfile", "plex_direct_stream") || "plex_direct_stream";
  const sizeGuard = settingsMediaPolicyValue("settings-builder-size-guard", "SizeGuardMode", "advisory") || "advisory";
  const encodeTuning = settingsMediaPolicyValue("settings-builder-encode-tuning", "EncodeTuningPreset", "balanced_nvenc") || "balanced_nvenc";
  const encodeLadder = settingsMediaPolicyValue("settings-builder-encode-ladder", "EncodeLadder", "auto") || "auto";
  const videoCodec = settingsMediaPolicyValue("settings-builder-video-codec", "VideoCodec", "hevc_nvenc") || "hevc_nvenc";
  const outputContainer = settingsMediaPolicyValue("settings-builder-output-container", "OutputContainer", "mkv") || "mkv";
  const maxGrowth = settingsMediaPolicyNumber("settings-builder-max-growth", "MaxEncodeGrowthPercent", 5);
  const compatGrowth = settingsMediaPolicyNumber("settings-builder-compat-growth", "CompatibilityEncodeGrowthPercent", 15);
  const movieThreshold = settingsMediaPolicyNumber("settings-builder-movie-threshold", "EncodeThresholdGB", 8);
  const tvThreshold = settingsMediaPolicyNumber("settings-builder-tv-threshold", "TVEncodeThresholdGB", 3);
  const allowH264Copy = settingsMediaPolicyBool("settings-video-h264-remux", "AllowH264RemuxIfPlexCompatible", true);
  const h264MaxBitrate = settingsMediaPolicyNumber("settings-video-h264-max-bitrate", "H264RemuxMaxBitrateMbps", 35);
  const h264MaxHeight = settingsMediaPolicyNumber("settings-video-h264-max-height", "H264RemuxMaxHeight", 1080);
  const remuxSafeCodecs = settingsMediaPolicyList("settings-video-remux-safe-codecs", "RemuxSafeVideoCodecs", ["hevc", "h265", "h264", "avc"]);
  const extraVideoFlags = settingsMediaPolicyList("settings-video-extra-flags", "ExtraVideoFlags", []);
  const convertTx3g = settingsMediaPolicyBool("settings-subtitle-convert-tx3g", "ConvertTx3gToSrt", true);
  const dropTx3g = settingsMediaPolicyBool("settings-subtitle-drop-tx3g", "DropTx3gAfterConversion", false);
  const convertBdpgs = settingsMediaPolicyBool("settings-subtitle-convert-bdpgs", "ConvertBdpgsToSrt", true);
  const dropBdpgs = settingsMediaPolicyBool("settings-subtitle-drop-bdpgs", "DropBdpgsAfterConversion", false);
  const dropAss = settingsMediaPolicyBool("settings-subtitle-drop-ass", "DropAssAfterConversion", false);
  const allowNoAudio = settingsMediaPolicyBool("settings-audio-allow-no-audio", "AllowNoAudio", false);
  const passthroughProfile = settingsMediaPolicyValue("settings-audio-passthrough-profile", "AudioPassthroughProfile", "plex_balanced") || "plex_balanced";
  const defaultAudioLanguages = settingsMediaPolicyList("settings-audio-preferred-languages", "PreferredDefaultAudioLanguages", ["english"]);
  const deferredPublish = settingsMediaPolicyBool("settings-pending-deferred-publish", "DeferredPublish", false);
  const cleanupRemote = settingsMediaPolicyBool("settings-pending-cleanup-remote", "CleanupRemoteStaging", false);
  const skipStability = settingsMediaPolicyBool("settings-pending-skip-stability", "SkipStabilityCheck", false);
  const integrity = settingsMediaPolicyBool("settings-pending-enable-integrity", "EnableIntegrityCheck", true);
  const rows = [
    {
      area: "Routing profile / size guard",
      posture: ["off", "disabled"].includes(String(sizeGuard).toLowerCase()) ? "review" : "coherent",
      evidence: `profile=${formatSettingsChoiceLabel(routingProfile)}; size guard=${formatSettingsChoiceLabel(sizeGuard)}; normal growth=${maxGrowth}%; compatibility growth=${compatGrowth}%; movie>${movieThreshold}GB; TV>${tvThreshold}GB`,
      handoff: "Launch should show these saved route/size values before Start. Strict mode can block growth; advisory mode should warn without changing policy by itself.",
    },
    {
      area: "Video copy / encoder path",
      posture: !allowH264Copy || extraVideoFlags.length ? "review" : "coherent",
      evidence: `codec=${formatSettingsChoiceLabel(videoCodec)}; tuning=${formatSettingsChoiceLabel(encodeTuning)}; ladder=${formatSettingsChoiceLabel(encodeLadder)}; H.264 copy=${allowH264Copy ? "on" : "off"} <=${h264MaxBitrate}Mbps/${h264MaxHeight}p; remux-safe=${remuxSafeCodecs.join(", ") || "(empty)"}; legacy flags=${extraVideoFlags.length}`,
      handoff: allowH264Copy
        ? "Plex-compatible H.264 sources can remain copy/remux candidates; fallback encoder choices remain backend-owned."
        : "Compatible H.264 sources may encode instead of copy. Confirm this is intentional before large batches.",
    },
    {
      area: "Container / subtitle mux posture",
      posture: String(outputContainer).toLowerCase() === "mp4" && (!dropBdpgs || !dropAss) ? "review" : "coherent",
      evidence: `container=${formatSettingsChoiceLabel(outputContainer)}; TX3G convert/drop=${convertTx3g ? "on" : "off"}/${dropTx3g ? "on" : "off"}; BDPGS OCR/drop=${convertBdpgs ? "on" : "off"}/${dropBdpgs ? "on" : "off"}; ASS drop=${dropAss ? "on" : "off"}`,
      handoff: String(outputContainer).toLowerCase() === "mp4"
        ? "MP4 cannot carry every original subtitle format. Backend routing must externalize or drop unsupported tracks deliberately."
        : "MKV remains the safer container for preserving original subtitle/audio streams while adding Plex-friendly SRT.",
    },
    {
      area: "SRT generation / original preservation",
      posture: (dropTx3g && !convertTx3g) || (dropBdpgs && !convertBdpgs) ? "blocked" : (!convertTx3g || !convertBdpgs || dropTx3g || dropBdpgs || dropAss ? "review" : "coherent"),
      evidence: `TX3G SRT=${convertTx3g ? "on" : "off"}; BDPGS OCR=${convertBdpgs ? "on" : "off"}; drop originals=${[dropTx3g ? "TX3G" : "", dropBdpgs ? "BDPGS" : "", dropAss ? "ASS" : ""].filter(Boolean).join(", ") || "none"}`,
      handoff: "Default Plex posture is add SRT for preferred languages while preserving originals unless a drop toggle is explicitly enabled.",
    },
    {
      area: "Audio default / passthrough",
      posture: allowNoAudio ? "blocked" : (!defaultAudioLanguages.length || passthroughProfile === "lossless_passthrough" || passthroughProfile === "custom_codec_list" ? "review" : "coherent"),
      evidence: `passthrough=${formatSettingsChoiceLabel(passthroughProfile)}; default languages=${defaultAudioLanguages.join(", ") || "(empty)"}; allow no-audio=${allowNoAudio ? "on" : "off"}`,
      handoff: allowNoAudio
        ? "No-audio output should block normal Plex publishing until deliberately reviewed."
        : "Preferred default-language and passthrough policy should be visible in Launch before unattended runs.",
    },
    {
      area: "Publish / recovery posture",
      posture: cleanupRemote || skipStability || !integrity ? "review" : "coherent",
      evidence: `deferred publish=${deferredPublish ? "on" : "off"}; remote cleanup=${cleanupRemote ? "on" : "off"}; stability=${skipStability ? "skipped" : "enabled"}; integrity=${integrity ? "enabled" : "disabled"}`,
      handoff: deferredPublish
        ? "Completed files may park in Pending Publish; verify drain readiness and output proof after the sample run."
        : "Direct publish remains backend-owned; source files should still be copied to scratch and preserved.",
    },
  ];
  return rows;
}

function settingsActiveMediaPolicyStatus(rows = settingsActiveMediaPolicyRows()) {
  if (rows.some((row) => row.posture === "blocked")) return "Blocked review";
  if (rows.some((row) => row.posture === "review" || row.posture === "warning")) return "Review";
  return rows.length ? "Coherent" : "No policy";
}

function settingsActiveMediaPolicySummaryLines(rows = settingsActiveMediaPolicyRows()) {
  const counts = rows.reduce((acc, row) => {
    const key = row.posture || "review";
    acc[key] = (acc[key] || 0) + 1;
    return acc;
  }, {});
  const reviewRows = rows.filter((row) => row.posture !== "coherent");
  const lines = [
    "Active media-policy handoff:",
    `Rows: ${rows.length}; coherent=${counts.coherent || 0}; review=${counts.review || 0}; warning=${counts.warning || 0}; blocked=${counts.blocked || 0}.`,
    "This is the operator-facing bridge between Settings builders and Launch saved-settings checks.",
    "Builder edits are not launch-active until backend Preview/Save succeeds and settings reload/refresh completes.",
  ];
  if (reviewRows.length) {
    lines.push("", "Rows needing launch-time attention:");
    reviewRows.forEach((row) => lines.push(`- ${row.area}: ${row.handoff}`));
  } else {
    lines.push("", "No local route/size/subtitle/audio/publish contradictions detected in visible builder state.");
  }
  lines.push("Mutation guardrail: this table is read-only and cannot stage, save, launch, encode, remux, publish, or touch files.");
  return lines;
}

function renderSettingsActiveMediaPolicyHandoff() {
  const rows = settingsActiveMediaPolicyRows();
  setText("settings-active-media-policy-status", settingsActiveMediaPolicyStatus(rows));
  setText("settings-active-media-policy-summary", settingsActiveMediaPolicySummaryLines(rows).join("\n"));
  setText("settings-active-media-policy-legend", "Active media-policy handoff rows are read-only and do not stage, save, launch, encode, remux, publish, or touch files.");
  const tbody = byId("settings-active-media-policy-rows");
  if (!tbody) return;
  if (!rows.length) {
    clearRows(tbody, 4, "No active media-policy handoff rows loaded.");
    return;
  }
  tbody.replaceChildren();
  rows.forEach((item) => {
    const row = document.createElement("tr");
    row.dataset.status = item.posture === "blocked" ? "blocked" : (item.posture === "warning" || item.posture === "review" ? "warning" : "match");
    appendCells(row, [item.area, item.posture, item.evidence, item.handoff]);
    tbody.appendChild(row);
  });
}

function settingsEffectivePolicyRowKey(row) {
  return String(row?.checkpoint || "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "policy-row";
}

function settingsEvidenceMatch(evidence, signature) {
  return Boolean(signature && evidence && evidence.signature === signature);
}

function settingsEvidenceResultLabel(evidence, signature) {
  if (!signature || signature === "{}") return "no staged patch";
  if (!evidence) return "missing";
  if (evidence.signature !== signature) return "stale";
  const result = evidence.result || {};
  if (result.ok === true) return Array.isArray(result.warnings) && result.warnings.length ? "fresh with warnings" : "fresh ok";
  if (result.ok === false) return "fresh failed";
  return "fresh unknown";
}

function settingsEffectivePolicyRows(entries) {
  const list = Array.isArray(entries) ? entries : [];
  const changedEntries = list.filter((entry) => entry.changed);
  const unknownEntries = changedEntries.filter((entry) => !entry.field);
  const changedLabels = changedEntries.slice(0, 8).map((entry) => entry.label || entry.key);
  const signature = settingsCurrentPatchSignature();
  const hasStagedPatch = Boolean(signature && signature !== "{}");
  const previewLabel = settingsEvidenceResultLabel(lastSettingsPatchPreviewEvidence, signature);
  const saveLabel = settingsEvidenceResultLabel(lastSettingsPatchSaveEvidence, signature);
  const previewMatches = settingsEvidenceMatch(lastSettingsPatchPreviewEvidence, signature);
  const saveMatches = settingsEvidenceMatch(lastSettingsPatchSaveEvidence, signature);
  const previewResult = lastSettingsPatchPreviewEvidence?.result || {};
  const saveResult = lastSettingsPatchSaveEvidence?.result || {};
  const readiness = settingsBackendMediaPolicyReadiness(lastSettings);
  const readinessRows = Array.isArray(readiness.rows) ? readiness.rows : [];
  const readinessStatus = settingsBackendMediaPolicyStatus(readiness);
  const readinessBlocked = readinessRows.some((row) => String(row.posture || "").toLowerCase().includes("blocked"));
  const readinessReview = readinessRows.some((row) => {
    const posture = String(row.posture || "").toLowerCase();
    return posture.includes("review") || posture.includes("warning");
  });
  const deltaRows = settingsPolicyDeltaRows(list);
  const deltaStatus = settingsPolicyDeltaStatus(deltaRows);
  const deltaReviewRows = deltaRows.filter((row) => {
    const posture = String(row.posture || "").toLowerCase();
    return posture.includes("blocked") || posture.includes("critical") || posture.includes("review") || posture.includes("preview") || posture.includes("staged");
  });
  const savedKeyCount = Object.keys(lastSettingsValues || {}).length;
  const rows = [
    {
      checkpoint: "Launch-active source of truth",
      posture: savedKeyCount ? "saved backend active" : "blocked",
      saved: savedKeyCount ? `${savedKeyCount} loaded config key(s); Launch and pipeline use this saved backend config.` : "No saved config values are loaded in WebView.",
      staged: hasStagedPatch ? `${changedEntries.length} effective staged change(s) remain inactive until backend Save Patch succeeds and settings reload/refresh completes.` : "No staged Changes JSON is active.",
      action: savedKeyCount ? "Use saved backend settings as the operational source of truth. Do not treat visible builder or Changes JSON edits as launch-active." : "Reload settings from disk before launching or saving.",
      detail: [
        `Saved config key count: ${savedKeyCount}`,
        `Staged patch signature: ${signature || "(unavailable)"}`,
        "Launch-active rule: saved backend settings win until backend save and reload/refresh complete.",
      ],
    },
    {
      checkpoint: "Saved media-policy readiness",
      posture: readinessBlocked ? "blocked" : (readinessReview ? "review" : (readinessRows.length ? "coherent" : "not loaded")),
      saved: readinessRows.length ? `Backend readiness status=${readinessStatus}; rows=${readinessRows.length}.` : "No backend media-policy readiness payload is loaded.",
      staged: "Staged Changes JSON does not change saved readiness evidence.",
      action: readinessBlocked
        ? "Resolve blocked saved media-policy rows before unattended runs."
        : "Use this as saved-policy evidence, then verify any staged candidate with Preview Patch before saving.",
      detail: readinessRows.slice(0, 8).map((row) => `${row.area || "Policy"}: ${row.posture || "review"}; ${row.operator_check || row.evidence || ""}`),
    },
    {
      checkpoint: "Staged WebView patch activity",
      posture: unknownEntries.length ? "blocked" : (changedEntries.length ? "staged inactive" : "idle"),
      saved: changedEntries.length ? `${changedEntries.length} effective change(s) differ from saved config.` : "No effective staged change differs from saved config.",
      staged: changedLabels.length ? changedLabels.join(", ") : "No changed staged keys.",
      action: unknownEntries.length
        ? "Unknown keys are schema drift. Do not save until backend Preview Patch explains them."
        : (changedEntries.length ? "Run backend Preview Patch; Save Patch is required before any change can become active." : "No save action is needed for an unchanged patch."),
      detail: [
        `Staged keys: ${list.length}`,
        `Effective changes: ${changedEntries.length}`,
        `Unknown changed keys: ${unknownEntries.length}`,
        `Changed keys: ${changedEntries.map((entry) => entry.key).join(", ") || "(none)"}`,
      ],
    },
    {
      checkpoint: "Backend preview/save proof",
      posture: !hasStagedPatch || !changedEntries.length
        ? "idle"
        : (saveMatches && saveResult.ok === true ? "saved proof present" : (previewMatches && previewResult.ok === true ? "previewed" : "review")),
      saved: `Preview=${previewLabel}; Save=${saveLabel}.`,
      staged: hasStagedPatch ? "Current Changes JSON has a stable signature for evidence matching." : "No staged patch signature is active.",
      action: !changedEntries.length
        ? "No preview/save proof is needed for an unchanged patch."
        : (saveMatches && saveResult.ok === true
            ? "Reload/refresh settings before treating saved changes as launch-active."
            : (previewMatches && previewResult.ok === true
                ? "Preview matches current JSON. Save Patch still requires explicit confirmation and backend success."
                : "Run Preview Patch before Save Patch; stale or missing preview evidence is not enough.")),
      detail: [
        `Current patch signature: ${signature || "(unavailable)"}`,
        `Preview evidence: ${previewLabel}`,
        `Save evidence: ${saveLabel}`,
        `Preview command ok: ${previewResult.ok === true ? "yes" : previewResult.ok === false ? "no" : "unknown"}`,
        `Save command ok: ${saveResult.ok === true ? "yes" : saveResult.ok === false ? "no" : "unknown"}`,
      ],
    },
    {
      checkpoint: "Policy delta attention",
      posture: deltaStatus === "Blocked review" ? "blocked" : (deltaStatus === "No blocker" || deltaStatus === "No staged change" ? "coherent" : "review"),
      saved: `Delta status=${deltaStatus}; saved values remain active.`,
      staged: deltaReviewRows.length ? `${deltaReviewRows.length} staged policy row(s) need attention.` : "No staged media-policy contradictions detected locally.",
      action: deltaReviewRows.length
        ? "Review the first changed policy rows below and confirm backend Preview Patch before save."
        : "No local staged media-policy blocker is visible; backend preview remains authoritative.",
      detail: deltaReviewRows.slice(0, 8).map((row) => `${row.area}: ${row.posture}; ${row.check}`),
    },
    {
      checkpoint: "Mutation boundary",
      posture: "backend-owned",
      saved: "Settings display, builders, deltas, and trust rows are read-only until a backend command is sent.",
      staged: "Preview Patch is non-writing. Save Patch is the only persistence command and requires confirmation.",
      action: "This panel cannot save config, launch work, run FFmpeg, rename files, drain pending publish, or touch source media.",
      detail: [
        "Boundary: frontend may stage JSON and request backend commands only.",
        "Backend owns PSD1 serialization, backups, validation, risk classification, and settings reload evidence.",
      ],
    },
  ];
  return rows;
}

function settingsEffectivePolicyTrustStatus(rows = settingsEffectivePolicyRows(settingsPatchImpactEntries(parseSettingsPatchJson()))) {
  if (!rows.length) return "Not evaluated";
  if (rows.some((row) => String(row.posture || "").includes("blocked"))) return "Blocked review";
  if (rows.some((row) => ["review", "staged inactive", "previewed"].includes(String(row.posture || "")))) return "Review";
  return "Trusted saved policy";
}

function settingsEffectivePolicySummaryLines(rows = settingsEffectivePolicyRows(settingsPatchImpactEntries(parseSettingsPatchJson()))) {
  const counts = rows.reduce((acc, row) => {
    const key = String(row.posture || "unknown").toLowerCase();
    acc[key] = (acc[key] || 0) + 1;
    return acc;
  }, {});
  const reviewRows = rows.filter((row) => {
    const posture = String(row.posture || "").toLowerCase();
    return posture.includes("blocked") || posture.includes("review") || posture.includes("staged") || posture.includes("preview");
  });
  const lines = [
    "Effective policy trust summary:",
    `Status: ${settingsEffectivePolicyTrustStatus(rows)}`,
    `Rows: ${rows.length}; blocked=${counts.blocked || 0}; review=${counts.review || 0}; staged-inactive=${counts["staged inactive"] || 0}; previewed=${counts.previewed || 0}; saved-backend-active=${counts["saved backend active"] || 0}.`,
    "Launch-active policy is the saved backend config. WebView builder values and Changes JSON are candidates only.",
    "Backend Preview Patch is non-writing. Save Patch plus settings reload/refresh is required before staged policy can affect a run.",
  ];
  if (reviewRows.length) {
    lines.push("", "First operator checks:");
    reviewRows.slice(0, 6).forEach((row) => lines.push(`- ${row.checkpoint}: ${row.action}`));
  } else {
    lines.push("", "No local trust contradiction detected. Continue to backend preview/save only if you intend to change settings.");
  }
  lines.push("", "Mutation guardrail: this summary is read-only and cannot save settings, launch work, mutate queues, publish, rename, or touch media.");
  return lines;
}

function settingsEffectivePolicyDetailLines(row) {
  if (!row) {
    return [
      "No effective policy row selected.",
      "Select a row to inspect launch-active state, staged-state limitations, preview/save evidence, and backend ownership.",
      "Mutation guardrail: this detail view is read-only and cannot save settings or touch media.",
    ];
  }
  const lines = [
    `Checkpoint: ${row.checkpoint}`,
    `Posture: ${row.posture}`,
    `Saved backend state: ${row.saved}`,
    `Staged WebView state: ${row.staged}`,
    `Operator action: ${row.action}`,
  ];
  const detail = Array.isArray(row.detail) ? row.detail.filter(Boolean) : [];
  if (detail.length) {
    lines.push("", "Proof / detail:");
    detail.forEach((item) => lines.push(`- ${item}`));
  }
  lines.push("", "Mutation guardrail: effective-policy trust is display-only; backend Preview/Save owns validation and persistence.");
  return lines;
}

function selectedSettingsEffectivePolicyRow(rows) {
  if (!selectedSettingsEffectivePolicyKey) return null;
  return (Array.isArray(rows) ? rows : []).find((row) => settingsEffectivePolicyRowKey(row) === selectedSettingsEffectivePolicyKey) || null;
}

function renderSettingsEffectivePolicyTrustFromEntries(entries) {
  const rows = settingsEffectivePolicyRows(entries);
  if (selectedSettingsEffectivePolicyKey && !rows.some((row) => settingsEffectivePolicyRowKey(row) === selectedSettingsEffectivePolicyKey)) {
    selectedSettingsEffectivePolicyKey = "";
  }
  if (!selectedSettingsEffectivePolicyKey && rows.length) {
    selectedSettingsEffectivePolicyKey = settingsEffectivePolicyRowKey(rows[0]);
  }
  setText("settings-effective-policy-status", settingsEffectivePolicyTrustStatus(rows));
  setText("settings-effective-policy-summary", settingsEffectivePolicySummaryLines(rows).join("\n"));
  setText("settings-effective-policy-legend", "Effective policy trust rows are read-only; backend Preview/Save remains the only settings persistence boundary.");
  setText("settings-effective-policy-detail", settingsEffectivePolicyDetailLines(selectedSettingsEffectivePolicyRow(rows)).join("\n"));
  const tbody = byId("settings-effective-policy-rows");
  if (!tbody) return;
  if (!rows.length) {
    clearRows(tbody, 5, "No effective policy trust rows loaded.");
    return;
  }
  tbody.replaceChildren();
  rows.forEach((item) => {
    const row = document.createElement("tr");
    const posture = String(item.posture || "").toLowerCase();
    row.dataset.status = posture.includes("blocked")
      ? "blocked"
      : posture.includes("review") || posture.includes("staged") || posture.includes("preview")
        ? "warning"
        : "match";
    const key = settingsEffectivePolicyRowKey(item);
    appendCells(row, [item.checkpoint, item.posture, item.saved, item.staged, item.action]);
    makeRowSelectable(row, () => {
      selectedSettingsEffectivePolicyKey = key;
      renderSettingsEffectivePolicyTrustFromEntries(entries);
    }, {
      selected: selectedSettingsEffectivePolicyKey === key,
      label: `Inspect effective policy checkpoint ${item.checkpoint}`,
    });
    tbody.appendChild(row);
  });
  updateTableStatusLegend("settings-effective-policy-legend", tbody, "Effective policy trust rows");
}

function renderSettingsEffectivePolicyTrustForError(message) {
  setText("settings-effective-policy-status", "Invalid JSON");
  setText(
    "settings-effective-policy-summary",
    [
      "Effective policy trust summary unavailable because Changes JSON is invalid.",
      message,
      "Saved backend settings remain launch-active; staged Changes JSON cannot be previewed or saved until it is valid JSON.",
      "Mutation guardrail: invalid JSON handling is local UI feedback only and does not write config.",
    ].join("\n")
  );
  clearRows(byId("settings-effective-policy-rows"), 5, "Effective policy trust unavailable because Changes JSON is invalid.");
  setText("settings-effective-policy-legend", "Effective policy trust rows are read-only; backend Preview/Save remains the only settings persistence boundary.");
  setText("settings-effective-policy-detail", [
    "Effective policy trust detail:",
    `Patch JSON is invalid: ${message}`,
    "Fix Changes JSON before Preview Patch or Save Patch can run.",
    "Launch-active rule: saved backend settings remain active.",
  ].join("\n"));
}

function settingsMediaPolicySummaryLines(rows = settingsMediaPolicyRows()) {
  const counts = rows.reduce((acc, row) => {
    const key = row.posture || "review";
    acc[key] = (acc[key] || 0) + 1;
    return acc;
  }, {});
  const reviewRows = rows.filter((row) => row.posture !== "coherent");
  const lines = [
    "Audio / subtitle policy cross-check:",
    `Rows: ${rows.length}; coherent=${counts.coherent || 0}; review=${counts.review || 0}; warning=${counts.warning || 0}; blocked=${counts.blocked || 0}.`,
    "SRT creation, original-track preservation, language routing, and audio predictability are checked from the visible builder state.",
    "Preview/Save remains backend-owned; this panel does not change FFmpeg, subtitle, audio, remux, encode, or publish behavior.",
  ];
  if (reviewRows.length) {
    lines.push("", "Rows needing review:");
    reviewRows.forEach((row) => lines.push(`- ${row.area}: ${row.action}`));
  } else {
    lines.push("", "No local audio/subtitle contradictions detected. Run backend Preview Patch before saving.");
  }
  return lines;
}

function renderSettingsMediaPolicyCrossCheck() {
  const rows = settingsMediaPolicyRows();
  setText("settings-media-policy-status", settingsMediaPolicyStatus(rows));
  setText("settings-media-policy-summary", settingsMediaPolicySummaryLines(rows).join("\n"));
  setText("settings-media-policy-legend", "Audio/subtitle policy rows are read-only and have no selectable actions.");
  const tbody = byId("settings-media-policy-rows");
  if (!rows.length) {
    clearRows(tbody, 4, "No audio/subtitle policy rows loaded.");
    return;
  }
  tbody.replaceChildren();
  rows.forEach((item) => {
    const row = document.createElement("tr");
    row.dataset.status = item.posture === "blocked" ? "blocked" : (item.posture === "warning" || item.posture === "review" ? "warning" : "match");
    appendCells(row, [item.area, item.posture, item.evidence, item.action]);
    tbody.appendChild(row);
  });
}

function settingsBackendMediaPolicyReadiness(settings = lastSettings) {
  const readiness = settings?.media_policy_readiness || {};
  if (!readiness || readiness.schema_version !== "settings_media_policy_readiness.v1") {
    return { operator_status: "Not loaded", rows: [], counts: {}, summary_lines: [] };
  }
  return readiness;
}

function settingsBackendMediaPolicyStatus(readiness = settingsBackendMediaPolicyReadiness()) {
  return readiness.operator_status || "Not evaluated";
}

function settingsBackendMediaPolicySummaryLines(readiness = settingsBackendMediaPolicyReadiness()) {
  const rows = Array.isArray(readiness.rows) ? readiness.rows : [];
  const lines = Array.isArray(readiness.summary_lines) && readiness.summary_lines.length
    ? readiness.summary_lines.slice()
    : [
      "Backend media-policy readiness:",
      `Status: ${settingsBackendMediaPolicyStatus(readiness)}; rows=${rows.length}.`,
      "This is read-only evidence from saved backend settings.",
    ];
  lines.push("", "Mutation guardrail: this table cannot stage settings, save config, launch work, run FFmpeg, publish files, or touch source media.");
  return lines;
}

function renderSettingsBackendMediaPolicyReadiness(settings = lastSettings) {
  const readiness = settingsBackendMediaPolicyReadiness(settings);
  const rows = Array.isArray(readiness.rows) ? readiness.rows : [];
  setText("settings-backend-media-policy-status", settingsBackendMediaPolicyStatus(readiness));
  setText("settings-backend-media-policy-summary", settingsBackendMediaPolicySummaryLines(readiness).join("\n"));
  setText("settings-backend-media-policy-legend", "Backend media-policy readiness rows are read-only and have no selectable actions.");
  const tbody = byId("settings-backend-media-policy-rows");
  if (!tbody) return;
  if (!rows.length) {
    clearRows(tbody, 4, "No backend media-policy readiness rows loaded.");
    return;
  }
  tbody.replaceChildren();
  rows.forEach((item) => {
    const posture = String(item.posture || "review").toLowerCase();
    const row = document.createElement("tr");
    row.dataset.status = posture === "blocked" ? "blocked" : posture === "review" ? "warning" : "match";
    appendCells(row, [
      item.area || "Policy",
      item.posture || "review",
      item.evidence || "",
      item.operator_check || "Review saved media-policy setting.",
    ]);
    tbody.appendChild(row);
  });
}

function settingsImpactGroupForKey(key) {
  return settingsImpactGroups.find((group) => group.keys.includes(key)) || null;
}

function settingsPatchEntryStatus(key, staged) {
  const field = settingsFieldDefinition(key);
  const current = settingsRawConfigValue(key);
  if (!field) return { field, current, changed: true, status: "unknown key" };
  if (settingsValuesEqual(current, staged)) return { field, current, changed: false, status: "unchanged" };
  return { field, current, changed: true, status: current === undefined ? "new value" : "changed" };
}

function settingsPatchImpactSeverity(entries) {
  if (entries.some((entry) => entry.severity === "high")) return "high";
  if (entries.some((entry) => entry.severity === "medium")) return "medium";
  return entries.length ? "low" : "none";
}

function settingsPatchImpactEntries(patch) {
  return Object.keys(patch || {}).sort((a, b) => a.localeCompare(b)).map((key) => {
    const status = settingsPatchEntryStatus(key, patch[key]);
    const group = settingsImpactGroupForKey(key);
    return {
      key,
      staged: patch[key],
      group,
      severity: status.field ? (group?.severity || "low") : "high",
      label: status.field?.label || key,
      ...status,
    };
  });
}

function renderSettingsPatchImpactSummaryFromEntries(entries) {
  const changedEntries = entries.filter((entry) => entry.changed);
  const unknownEntries = entries.filter((entry) => !entry.field);
  const severity = settingsPatchImpactSeverity(changedEntries);
  const lines = [
    `Local impact: ${severity === "none" ? "none" : severity}`,
    `Changed/new keys: ${changedEntries.length}; unchanged keys: ${entries.length - changedEntries.length}; unknown keys: ${unknownEntries.length}`,
    "Backend preview remains the source of truth before saving.",
  ];
  if (!changedEntries.length) {
    lines.push("No effective staged changes detected.");
    setText("settings-patch-impact-summary", lines.join("\n"));
    return;
  }
  const grouped = new Map();
  changedEntries.forEach((entry) => {
    const groupName = entry.group?.name || "Unknown / custom";
    if (!grouped.has(groupName)) grouped.set(groupName, []);
    grouped.get(groupName).push(entry);
  });
  grouped.forEach((groupEntries, groupName) => {
    const group = groupEntries[0].group;
    lines.push("", `${groupName}: ${groupEntries.length} key${groupEntries.length === 1 ? "" : "s"}`);
    if (group?.note) lines.push(`  ${group.note}`);
    groupEntries.slice(0, 8).forEach((entry) => {
      const currentText = entry.current === undefined ? "(not set)" : formatConfigValue(entry.current);
      lines.push(`  - ${entry.label}: ${currentText} -> ${formatConfigValue(entry.staged)} (${entry.status})`);
      const hint = settingsSpecificImpactHints[entry.key];
      if (hint) lines.push(`    ${hint}`);
    });
    if (groupEntries.length > 8) lines.push(`  - ${groupEntries.length - 8} more key(s) in this group.`);
  });
  setText("settings-patch-impact-summary", lines.join("\n"));
}

function settingsBoolValue(value) {
  if (typeof value === "boolean") return value;
  if (value === undefined || value === null || value === "") return null;
  const normalized = String(value).trim().toLowerCase();
  if (["true", "1", "yes", "y", "on", "enabled"].includes(normalized)) return true;
  if (["false", "0", "no", "n", "off", "disabled"].includes(normalized)) return false;
  return null;
}

function settingsPatchCandidateValue(entries, key) {
  const entry = entries.find((item) => item.key === key);
  return entry ? entry.staged : settingsRawConfigValue(key);
}

function settingsStableJsonValue(value) {
  if (Array.isArray(value)) return value.map(settingsStableJsonValue);
  if (value && typeof value === "object") {
    const ordered = {};
    Object.keys(value).sort((left, right) => left.localeCompare(right)).forEach((key) => {
      ordered[key] = settingsStableJsonValue(value[key]);
    });
    return ordered;
  }
  return value;
}

function settingsPatchSignature(changes) {
  try {
    return JSON.stringify(settingsStableJsonValue(changes || {}));
  } catch (_error) {
    return "";
  }
}

function settingsCurrentPatchSignature() {
  try {
    return settingsPatchSignature(parseSettingsPatchJson());
  } catch (_error) {
    return "";
  }
}

function settingsPatchListValue(value) {
  if (Array.isArray(value)) return value.map((item) => String(item).trim()).filter(Boolean);
  if (typeof value === "string") return parseSettingsListText(value);
  return value === undefined || value === null || value === "" ? [] : [String(value)];
}

function settingsPatchCandidateText(entries, key, fallback = "") {
  const value = settingsPatchCandidateValue(entries, key);
  if (value === undefined || value === null || value === "") return String(fallback ?? "");
  return String(value).trim();
}

function settingsPatchCandidateNumber(entries, key, fallback = 0) {
  const value = Number(settingsPatchCandidateValue(entries, key));
  return Number.isFinite(value) ? value : Number(fallback || 0);
}

function settingsPatchCandidateBool(entries, key, fallback = false) {
  const value = settingsBoolValue(settingsPatchCandidateValue(entries, key));
  if (value === null) return Boolean(fallback);
  return value;
}

function settingsPatchCandidateList(entries, key, fallback = []) {
  const value = settingsPatchCandidateValue(entries, key);
  if (value === undefined) return Array.isArray(fallback) ? fallback.slice() : settingsPatchListValue(fallback);
  return settingsPatchListValue(value);
}

function settingsPatchCurrentText(key, fallback = "") {
  const value = settingsRawConfigValue(key);
  if (value === undefined || value === null || value === "") return String(fallback ?? "");
  return String(value).trim();
}

function settingsPatchCurrentNumber(key, fallback = 0) {
  const value = Number(settingsRawConfigValue(key));
  return Number.isFinite(value) ? value : Number(fallback || 0);
}

function settingsPatchCurrentBool(key, fallback = false) {
  const value = settingsBoolValue(settingsRawConfigValue(key));
  if (value === null) return Boolean(fallback);
  return value;
}

function settingsPatchCurrentList(key, fallback = []) {
  const value = settingsRawConfigValue(key);
  if (value === undefined) return Array.isArray(fallback) ? fallback.slice() : settingsPatchListValue(fallback);
  return settingsPatchListValue(value);
}

function settingsPolicyDeltaChangedLabels(entries, keys) {
  const wanted = new Set(keys);
  return entries
    .filter((entry) => entry.changed && wanted.has(entry.key))
    .map((entry) => entry.label || entry.key);
}

function settingsPolicyDeltaChangedText(entries, keys) {
  const labels = settingsPolicyDeltaChangedLabels(entries, keys);
  return labels.length ? `Changed: ${labels.join(", ")}.` : "No effective staged change in this area.";
}

function settingsPolicyDeltaBoolText(value) {
  return value ? "on" : "off";
}

function settingsPolicyDeltaStatus(rows) {
  if (!rows.length) return "No staged change";
  const postures = rows.map((row) => String(row.posture || "").toLowerCase());
  if (postures.some((posture) => posture.includes("blocked") || posture.includes("critical"))) return "Blocked review";
  if (postures.some((posture) => posture.includes("high"))) return "High review";
  if (postures.some((posture) => posture.includes("review") || posture.includes("staged") || posture.includes("preview"))) return "Preview required";
  return "No blocker";
}

// Frontend advisory only: backend Preview Patch and Save Patch remain
// authoritative for schema validation, source-deletion acceptance, and PSD1 writes.
function settingsPolicyDeltaRows(entries) {
  const changedEntries = entries.filter((entry) => entry.changed);
  const unknownEntries = changedEntries.filter((entry) => !entry.field);
  const rows = [];

  rows.push({
    area: "Patch scope",
    posture: !changedEntries.length ? "idle" : unknownEntries.length ? "blocked" : "staged",
    current: `${entries.length} staged key(s); ${changedEntries.length} effective change(s).`,
    candidate: unknownEntries.length
      ? `${unknownEntries.length} unknown key(s): ${unknownEntries.slice(0, 6).map((entry) => entry.key).join(", ")}${unknownEntries.length > 6 ? ", ..." : ""}`
      : `${changedEntries.length} known effective change(s).`,
    check: changedEntries.length
      ? "Run backend Preview Patch before Save Patch; Launch continues using saved settings until backend save/reload succeeds."
      : "No effective settings change is staged.",
  });

  const routingKeys = [
    "RoutingProfile",
    "SizeGuardMode",
    "EncodeThresholdGB",
    "TVEncodeThresholdGB",
    "MaxEncodeGrowthPercent",
    "CompatibilityEncodeGrowthPercent",
  ];
  const currentSizeGuard = settingsPatchCurrentText("SizeGuardMode", "advisory").toLowerCase();
  const nextSizeGuard = settingsPatchCandidateText(entries, "SizeGuardMode", "advisory").toLowerCase();
  const currentMaxGrowth = settingsPatchCurrentNumber("MaxEncodeGrowthPercent", 5);
  const nextMaxGrowth = settingsPatchCandidateNumber(entries, "MaxEncodeGrowthPercent", 5);
  const currentCompatGrowth = settingsPatchCurrentNumber("CompatibilityEncodeGrowthPercent", 15);
  const nextCompatGrowth = settingsPatchCandidateNumber(entries, "CompatibilityEncodeGrowthPercent", 15);
  rows.push({
    area: "Routing / size guard",
    posture: ["off", "disabled"].includes(nextSizeGuard) || nextMaxGrowth > 15 || nextCompatGrowth > 30 ? "review" : (settingsPolicyDeltaChangedLabels(entries, routingKeys).length ? "preview required" : "unchanged"),
    current: `profile=${formatSettingsChoiceLabel(settingsPatchCurrentText("RoutingProfile", "plex_direct_stream"))}; guard=${formatSettingsChoiceLabel(currentSizeGuard)}; growth=${currentMaxGrowth}%/${currentCompatGrowth}%; movie>${settingsPatchCurrentNumber("EncodeThresholdGB", 8)}GB; TV>${settingsPatchCurrentNumber("TVEncodeThresholdGB", 3)}GB`,
    candidate: `profile=${formatSettingsChoiceLabel(settingsPatchCandidateText(entries, "RoutingProfile", "plex_direct_stream"))}; guard=${formatSettingsChoiceLabel(nextSizeGuard)}; growth=${nextMaxGrowth}%/${nextCompatGrowth}%; movie>${settingsPatchCandidateNumber(entries, "EncodeThresholdGB", 8)}GB; TV>${settingsPatchCandidateNumber(entries, "TVEncodeThresholdGB", 3)}GB`,
    check: `${settingsPolicyDeltaChangedText(entries, routingKeys)} Size guards and growth limits affect remux-vs-encode trust and oversized-output review.`,
  });

  const videoKeys = [
    "VideoCodec",
    "EncodeTuningPreset",
    "EncodeLadder",
    "AllowH264RemuxIfPlexCompatible",
    "H264RemuxMaxBitrateMbps",
    "H264RemuxMaxHeight",
    "RemuxSafeVideoCodecs",
    "ExtraVideoFlags",
  ];
  const nextH264Copy = settingsPatchCandidateBool(entries, "AllowH264RemuxIfPlexCompatible", true);
  const nextExtraFlags = settingsPatchCandidateList(entries, "ExtraVideoFlags", []);
  rows.push({
    area: "Video route / encoder precision",
    posture: !nextH264Copy || nextExtraFlags.length ? "review" : (settingsPolicyDeltaChangedLabels(entries, videoKeys).length ? "preview required" : "unchanged"),
    current: `codec=${formatSettingsChoiceLabel(settingsPatchCurrentText("VideoCodec", "hevc_nvenc"))}; H.264 copy=${settingsPolicyDeltaBoolText(settingsPatchCurrentBool("AllowH264RemuxIfPlexCompatible", true))}; safe=${settingsPatchCurrentList("RemuxSafeVideoCodecs", ["hevc", "h265", "h264", "avc"]).join(", ") || "(empty)"}; raw flags=${settingsPatchCurrentList("ExtraVideoFlags", []).length}`,
    candidate: `codec=${formatSettingsChoiceLabel(settingsPatchCandidateText(entries, "VideoCodec", "hevc_nvenc"))}; H.264 copy=${settingsPolicyDeltaBoolText(nextH264Copy)} <=${settingsPatchCandidateNumber(entries, "H264RemuxMaxBitrateMbps", 35)}Mbps/${settingsPatchCandidateNumber(entries, "H264RemuxMaxHeight", 1080)}p; safe=${settingsPatchCandidateList(entries, "RemuxSafeVideoCodecs", ["hevc", "h265", "h264", "avc"]).join(", ") || "(empty)"}; raw flags=${nextExtraFlags.length}`,
    check: nextExtraFlags.length
      ? "Legacy FFmpeg flags are staged. Backend preview must review them before any route or size policy depends on this patch."
      : `${settingsPolicyDeltaChangedText(entries, videoKeys)} Compatible low-bitrate H.264 should normally remain copy/remux eligible.`,
  });

  const subtitleKeys = [
    "OutputContainer",
    "SubKeepLanguages",
    "Tx3gExtractLanguages",
    "BdpgsExtractLanguages",
    "ConvertTx3gToSrt",
    "DropTx3gAfterConversion",
    "CreateExternalTx3gSrtSidecars",
    "ConvertBdpgsToSrt",
    "DropBdpgsAfterConversion",
    "DropAssAfterConversion",
    "StripFormatting",
    "RemoveKaraoke",
    "KeepSignsAndSongs",
  ];
  const nextContainer = settingsPatchCandidateText(entries, "OutputContainer", "mkv").toLowerCase();
  const nextConvertTx3g = settingsPatchCandidateBool(entries, "ConvertTx3gToSrt", true);
  const nextDropTx3g = settingsPatchCandidateBool(entries, "DropTx3gAfterConversion", false);
  const nextConvertBdpgs = settingsPatchCandidateBool(entries, "ConvertBdpgsToSrt", true);
  const nextDropBdpgs = settingsPatchCandidateBool(entries, "DropBdpgsAfterConversion", false);
  const nextDropAss = settingsPatchCandidateBool(entries, "DropAssAfterConversion", false);
  const subtitleBlocked = (nextDropTx3g && !nextConvertTx3g) || (nextDropBdpgs && !nextConvertBdpgs);
  rows.push({
    area: "Container / subtitle preservation",
    posture: subtitleBlocked ? "blocked" : (nextContainer === "mp4" || nextDropTx3g || nextDropBdpgs || nextDropAss || !nextConvertTx3g || !nextConvertBdpgs ? "review" : (settingsPolicyDeltaChangedLabels(entries, subtitleKeys).length ? "preview required" : "unchanged")),
    current: `container=${formatSettingsChoiceLabel(settingsPatchCurrentText("OutputContainer", "mkv"))}; TX3G=${settingsPolicyDeltaBoolText(settingsPatchCurrentBool("ConvertTx3gToSrt", true))}/${settingsPolicyDeltaBoolText(settingsPatchCurrentBool("DropTx3gAfterConversion", false))}; BDPGS=${settingsPolicyDeltaBoolText(settingsPatchCurrentBool("ConvertBdpgsToSrt", true))}/${settingsPolicyDeltaBoolText(settingsPatchCurrentBool("DropBdpgsAfterConversion", false))}; ASS drop=${settingsPolicyDeltaBoolText(settingsPatchCurrentBool("DropAssAfterConversion", false))}`,
    candidate: `container=${formatSettingsChoiceLabel(nextContainer)}; keep=${settingsPatchCandidateList(entries, "SubKeepLanguages", ["eng", "und"]).join(", ") || "(empty)"}; TX3G=${settingsPolicyDeltaBoolText(nextConvertTx3g)}/${settingsPolicyDeltaBoolText(nextDropTx3g)}; BDPGS=${settingsPolicyDeltaBoolText(nextConvertBdpgs)}/${settingsPolicyDeltaBoolText(nextDropBdpgs)}; ASS drop=${settingsPolicyDeltaBoolText(nextDropAss)}`,
    check: subtitleBlocked
      ? "Do not drop TX3G/BDPGS originals when the matching SRT/OCR conversion is disabled."
      : `${settingsPolicyDeltaChangedText(entries, subtitleKeys)} Default Plex posture is add preferred-language SRT while preserving original subtitles unless a drop toggle is explicit.`,
  });

  const audioKeys = [
    "AudioPassthroughProfile",
    "CompatibleAudioCodecs",
    "PreferredDefaultAudioLanguages",
    "AudioTranscodeCodec",
    "AudioTranscodeBitrate",
    "AudioTranscodeAutoBitrateByChannels",
    "AudioDownmixMode",
    "AudioMaxChannels",
    "AllowNoAudio",
  ];
  const nextAudioProfile = settingsPatchCandidateText(entries, "AudioPassthroughProfile", "plex_balanced");
  const nextAudioCodecs = settingsPatchCandidateList(entries, "CompatibleAudioCodecs", ["aac", "ac3", "eac3", "mp3", "opus", "vorbis"]);
  const nextAudioLanguages = settingsPatchCandidateList(entries, "PreferredDefaultAudioLanguages", ["english"]);
  const nextAllowNoAudio = settingsPatchCandidateBool(entries, "AllowNoAudio", false);
  rows.push({
    area: "Audio direct-play predictability",
    posture: nextAllowNoAudio || (nextAudioProfile === "custom_codec_list" && !nextAudioCodecs.length) ? "blocked" : (!nextAudioLanguages.length || nextAudioProfile === "lossless_passthrough" || nextAudioProfile === "custom_codec_list" || settingsPatchCandidateNumber(entries, "AudioMaxChannels", 6) < 6 ? "review" : (settingsPolicyDeltaChangedLabels(entries, audioKeys).length ? "preview required" : "unchanged")),
    current: `profile=${formatSettingsChoiceLabel(settingsPatchCurrentText("AudioPassthroughProfile", "plex_balanced"))}; languages=${settingsPatchCurrentList("PreferredDefaultAudioLanguages", ["english"]).join(", ") || "(empty)"}; downmix=${formatSettingsChoiceLabel(settingsPatchCurrentText("AudioDownmixMode", "max_channels"))}; max=${settingsPatchCurrentNumber("AudioMaxChannels", 6)}; no-audio=${settingsPolicyDeltaBoolText(settingsPatchCurrentBool("AllowNoAudio", false))}`,
    candidate: `profile=${formatSettingsChoiceLabel(nextAudioProfile)}; codecs=${nextAudioCodecs.join(", ") || "(empty)"}; languages=${nextAudioLanguages.join(", ") || "(empty)"}; downmix=${formatSettingsChoiceLabel(settingsPatchCandidateText(entries, "AudioDownmixMode", "max_channels"))}; max=${settingsPatchCandidateNumber(entries, "AudioMaxChannels", 6)}; no-audio=${settingsPolicyDeltaBoolText(nextAllowNoAudio)}`,
    check: nextAllowNoAudio
      ? "No-audio outputs should stay disabled for normal Plex publishing."
      : `${settingsPolicyDeltaChangedText(entries, audioKeys)} Preferred-language defaults and passthrough policy should be intentional before unattended runs.`,
  });

  const publishKeys = [
    "DeferredPublish",
    "CleanupRemoteStaging",
    "SkipStabilityCheck",
    "EnableIntegrityCheck",
    "DeleteSourceAfterProcessing",
    "TransientFailureRetryLimit",
    "RobocopyTimeoutSeconds",
    "OutsourceMinFreeSpaceGB",
    "OutputSizeMultiplier",
  ];
  const nextDeleteSource = settingsPatchCandidateBool(entries, "DeleteSourceAfterProcessing", false);
  const nextSkipStability = settingsPatchCandidateBool(entries, "SkipStabilityCheck", false);
  const nextIntegrity = settingsPatchCandidateBool(entries, "EnableIntegrityCheck", true);
  const nextCleanupRemote = settingsPatchCandidateBool(entries, "CleanupRemoteStaging", false);
  rows.push({
    area: "Publish / source safety",
    posture: nextDeleteSource ? "critical blocked" : (nextSkipStability || !nextIntegrity || nextCleanupRemote ? "review" : (settingsPolicyDeltaChangedLabels(entries, publishKeys).length ? "preview required" : "unchanged")),
    current: `deferred=${settingsPolicyDeltaBoolText(settingsPatchCurrentBool("DeferredPublish", false))}; cleanup remote=${settingsPolicyDeltaBoolText(settingsPatchCurrentBool("CleanupRemoteStaging", false))}; stability=${settingsPatchCurrentBool("SkipStabilityCheck", false) ? "skipped" : "enabled"}; integrity=${settingsPatchCurrentBool("EnableIntegrityCheck", true) ? "enabled" : "disabled"}; delete source=${settingsPolicyDeltaBoolText(settingsPatchCurrentBool("DeleteSourceAfterProcessing", false))}`,
    candidate: `deferred=${settingsPolicyDeltaBoolText(settingsPatchCandidateBool(entries, "DeferredPublish", false))}; cleanup remote=${settingsPolicyDeltaBoolText(nextCleanupRemote)}; stability=${nextSkipStability ? "skipped" : "enabled"}; integrity=${nextIntegrity ? "enabled" : "disabled"}; delete source=${settingsPolicyDeltaBoolText(nextDeleteSource)}; copy timeout=${settingsPatchCandidateNumber(entries, "RobocopyTimeoutSeconds", 14400)}s`,
    check: nextDeleteSource
      ? "Source deletion must remain an explicit opt-in safety decision and should not be enabled from routine patch work."
      : `${settingsPolicyDeltaChangedText(entries, publishKeys)} Source files should still be copied to scratch and preserved during normal processing.`,
  });

  const runtimeKeys = [
    "DebugMode",
    "ConsoleLogLevel",
    "FileLogLevel",
    "LogRetentionDays",
    "FFmpegEncodeTimeoutSeconds",
    "FFmpegRemuxTimeoutSeconds",
    "FFmpegCpuEncodeTimeoutSeconds",
    "MkvmergeRemuxTimeoutSeconds",
    "SourceScanIntervalSeconds",
    "TransientFailureRetryLimit",
    "AllowSystemTools",
  ];
  const nextAllowSystemTools = settingsPatchCandidateBool(entries, "AllowSystemTools", false);
  const nextEncodeTimeout = settingsPatchCandidateNumber(entries, "FFmpegEncodeTimeoutSeconds", 21600);
  const nextRetention = settingsPatchCandidateNumber(entries, "LogRetentionDays", 7);
  rows.push({
    area: "Runtime / diagnostics guardrails",
    posture: nextAllowSystemTools || nextEncodeTimeout < 1800 || nextRetention === 0 ? "review" : (settingsPolicyDeltaChangedLabels(entries, runtimeKeys).length ? "preview required" : "unchanged"),
    current: `debug=${settingsPolicyDeltaBoolText(settingsPatchCurrentBool("DebugMode", false))}; encode timeout=${settingsPatchCurrentNumber("FFmpegEncodeTimeoutSeconds", 21600)}s; remux timeout=${settingsPatchCurrentNumber("FFmpegRemuxTimeoutSeconds", 7200)}s; retention=${settingsPatchCurrentNumber("LogRetentionDays", 7)}d; PATH tools=${settingsPolicyDeltaBoolText(settingsPatchCurrentBool("AllowSystemTools", false))}`,
    candidate: `debug=${settingsPolicyDeltaBoolText(settingsPatchCandidateBool(entries, "DebugMode", false))}; encode timeout=${nextEncodeTimeout}s; remux timeout=${settingsPatchCandidateNumber(entries, "FFmpegRemuxTimeoutSeconds", 7200)}s; retention=${nextRetention}d; PATH tools=${settingsPolicyDeltaBoolText(nextAllowSystemTools)}`,
    check: nextAllowSystemTools
      ? "Bundled tools should remain preferred; PATH fallback can hide FFmpeg/ffprobe version drift."
      : `${settingsPolicyDeltaChangedText(entries, runtimeKeys)} Timeout and log-retention changes affect long-running failure diagnosis.`,
  });

  const networkKeys = [
    "NetworkRole",
    "CoordinatorPort",
    "CoordinatorBindAddress",
    "CoordinatorAlsoEncodeLocally",
    "WorkerCoordinatorUrl",
    "WorkerName",
    "WorkerSourcePathMap",
    "WorkerConfigOverrides",
  ];
  const nextNetworkRole = settingsPatchCandidateText(entries, "NetworkRole", "standalone").toLowerCase();
  const nextWorkerOverrides = settingsPatchCandidateText(entries, "WorkerConfigOverrides", "");
  rows.push({
    area: "Network visibility / worker policy",
    posture: nextNetworkRole !== "standalone" || nextWorkerOverrides ? "review" : (settingsPolicyDeltaChangedLabels(entries, networkKeys).length ? "preview required" : "unchanged"),
    current: `role=${formatSettingsChoiceLabel(settingsPatchCurrentText("NetworkRole", "standalone"))}; worker=${settingsPatchCurrentText("WorkerName", "(not set)") || "(not set)"}; overrides=${settingsPatchCurrentText("WorkerConfigOverrides", "") ? "present" : "none"}`,
    candidate: `role=${formatSettingsChoiceLabel(nextNetworkRole)}; worker=${settingsPatchCandidateText(entries, "WorkerName", "(not set)") || "(not set)"}; coordinator=${settingsPatchCandidateText(entries, "WorkerCoordinatorUrl", "(not set)") || "(not set)"}; overrides=${nextWorkerOverrides ? "present" : "none"}`,
    check: `${settingsPolicyDeltaChangedText(entries, networkKeys)} WebView network lifecycle controls remain read-only/backend-owned during transition.`,
  });

  rows.push({
    area: "Mutation boundary",
    posture: "backend-owned",
    current: "Current config is read-only in this table.",
    candidate: "Changes JSON is still only staged text until backend Preview/Save succeeds.",
    check: "This delta cannot save settings, launch work, run FFmpeg, rename, drain, publish, or touch files.",
  });

  return rows;
}

function settingsPolicyDeltaSummaryLines(rows) {
  const counts = rows.reduce((acc, row) => {
    const key = String(row.posture || "unknown").toLowerCase();
    acc[key] = (acc[key] || 0) + 1;
    return acc;
  }, {});
  const reviewRows = rows.filter((row) => {
    const posture = String(row.posture || "").toLowerCase();
    return posture.includes("blocked") || posture.includes("critical") || posture.includes("review") || posture.includes("staged") || posture.includes("preview");
  });
  const lines = [
    "Staged media-policy delta:",
    `Status: ${settingsPolicyDeltaStatus(rows)}`,
    `Rows: ${rows.length}; blocked=${counts.blocked || 0}; critical-blocked=${counts["critical blocked"] || 0}; review=${counts.review || 0}; preview-required=${counts["preview required"] || 0}; staged=${counts.staged || 0}.`,
    "This compares current saved values against the local Changes JSON candidate before backend preview/save.",
    "Backend Preview Patch remains authoritative for schema validation, risk classification, PSD1 serialization, and redacted diff evidence.",
  ];
  if (reviewRows.length) {
    lines.push("", "Rows needing operator attention:");
    reviewRows.slice(0, 7).forEach((row) => lines.push(`- ${row.area}: ${row.posture}; ${row.check}`));
  } else {
    lines.push("", "No staged media-policy contradictions detected locally.");
  }
  lines.push("", "Mutation guardrail: this delta is read-only and cannot save settings, launch work, mutate queues, publish, rename, or touch media.");
  return lines;
}

function renderSettingsPolicyDeltaFromEntries(entries) {
  const rows = settingsPolicyDeltaRows(entries);
  const tbody = byId("settings-policy-delta-rows");
  setText("settings-policy-delta-status", settingsPolicyDeltaStatus(rows));
  setText("settings-policy-delta-summary", settingsPolicyDeltaSummaryLines(rows).join("\n"));
  setText("settings-policy-delta-legend", "Staged media-policy delta is read-only; backend preview/save remains authoritative.");
  if (!tbody) return;
  if (!rows.length) {
    clearRows(tbody, 5, "No staged media-policy delta loaded.");
    return;
  }
  tbody.replaceChildren();
  rows.forEach((item) => {
    const row = document.createElement("tr");
    const posture = String(item.posture || "").toLowerCase();
    row.dataset.status = posture.includes("blocked") || posture.includes("critical")
      ? "blocked"
      : posture.includes("review") || posture.includes("staged") || posture.includes("preview")
        ? "warning"
        : "match";
    appendCells(row, [item.area, item.posture, item.current, item.candidate, item.check]);
    tbody.appendChild(row);
  });
}

function renderSettingsPolicyDeltaForError(message) {
  setText("settings-policy-delta-status", "Invalid JSON");
  setText(
    "settings-policy-delta-summary",
    `Staged media-policy delta unavailable because Changes JSON is invalid.\n${message}\nBackend preview/save cannot run until this is valid JSON.`
  );
  clearRows(byId("settings-policy-delta-rows"), 5, "Staged media-policy delta unavailable because Changes JSON is invalid.");
  setText("settings-policy-delta-legend", "Staged media-policy delta is read-only; backend preview/save remains authoritative.");
}

function settingsReadinessIssue(severity, message) {
  return { severity, message };
}

function settingsPatchSaveReadinessIssues(entries) {
  const changedEntries = entries.filter((entry) => entry.changed);
  const issues = [];
  const boolValue = (key) => settingsBoolValue(settingsPatchCandidateValue(entries, key));
  const listValue = (key) => settingsPatchListValue(settingsPatchCandidateValue(entries, key));
  const textValue = (key) => String(settingsPatchCandidateValue(entries, key) ?? "").trim();
  const changedKey = (key) => changedEntries.some((entry) => entry.key === key);

  entries.filter((entry) => !entry.field).forEach((entry) => {
    issues.push(settingsReadinessIssue("high", `Unknown key '${entry.key}' is not in the WebView schema; backend preview must validate it before save.`));
  });
  changedEntries.filter((entry) => entry.severity === "high" && entry.field).forEach((entry) => {
    issues.push(settingsReadinessIssue("review", `${entry.label} is a high-impact setting. Confirm the change before saving.`));
  });
  if (changedKey("DeleteSourceAfterProcessing") && boolValue("DeleteSourceAfterProcessing") === true) {
    issues.push(settingsReadinessIssue("critical", "DeleteSourceAfterProcessing would allow source deletion. This must stay an explicit, intentional source-safety decision."));
  }
  if (changedKey("SkipStabilityCheck") && boolValue("SkipStabilityCheck") === true) {
    issues.push(settingsReadinessIssue("high", "SkipStabilityCheck is enabled. Half-copied downloads, active torrents, and network-share writes can enter processing."));
  }
  if (changedKey("EnableIntegrityCheck") && boolValue("EnableIntegrityCheck") === false) {
    issues.push(settingsReadinessIssue("high", "EnableIntegrityCheck is disabled. Corrupt or partially-written sources may pass discovery."));
  }
  if (changedKey("AllowNoAudio") && boolValue("AllowNoAudio") === true) {
    issues.push(settingsReadinessIssue("high", "AllowNoAudio is enabled. Outputs without audio can be published and look broken in Plex."));
  }
  if (changedKey("ReprocessAll") && boolValue("ReprocessAll") === true) {
    issues.push(settingsReadinessIssue("medium", "ReprocessAll is enabled. A future run can reconsider already-completed outputs."));
  }
  if (changedKey("ExtraVideoFlags") && listValue("ExtraVideoFlags").length) {
    issues.push(settingsReadinessIssue("high", "ExtraVideoFlags contains legacy raw FFmpeg flags. Backend risk preview should review this before save."));
  }
  if (changedKey("ValidExtensions") && listValue("ValidExtensions").some((item) => !String(item).startsWith("."))) {
    issues.push(settingsReadinessIssue("medium", "ValidExtensions contains values without a leading dot. Backend preview should reject or normalize this."));
  }
  if (changedKey("ValidExtensions") && listValue("ValidExtensions").some((item) => [".part", ".tmp", ".crdownload", ".download"].includes(String(item).toLowerCase()))) {
    issues.push(settingsReadinessIssue("high", "ValidExtensions includes partial-download style extensions."));
  }
  if (changedKey("DropTx3gAfterConversion") && boolValue("DropTx3gAfterConversion") === true) {
    issues.push(settingsReadinessIssue("medium", "TX3G originals will be dropped after conversion. Keep disabled to preserve source subtitle tracks."));
  }
  if (changedKey("DropBdpgsAfterConversion") && boolValue("DropBdpgsAfterConversion") === true) {
    issues.push(settingsReadinessIssue("medium", "BDPGS originals will be dropped after OCR. Keep disabled when preserving image subtitle tracks matters."));
  }
  if (changedKey("DropAssAfterConversion") && boolValue("DropAssAfterConversion") === true) {
    issues.push(settingsReadinessIssue("medium", "ASS/SSA originals will be dropped after conversion. Keep disabled to preserve styling."));
  }
  if ((changedKey("DropTx3gAfterConversion") || changedKey("ConvertTx3gToSrt")) && boolValue("DropTx3gAfterConversion") === true && boolValue("ConvertTx3gToSrt") === false) {
    issues.push(settingsReadinessIssue("high", "Drop TX3G is enabled while TX3G conversion is disabled."));
  }
  if ((changedKey("DropBdpgsAfterConversion") || changedKey("ConvertBdpgsToSrt")) && boolValue("DropBdpgsAfterConversion") === true && boolValue("ConvertBdpgsToSrt") === false) {
    issues.push(settingsReadinessIssue("high", "Drop BDPGS is enabled while BDPGS OCR is disabled."));
  }
  if (changedKey("SubKeepLanguages") && !listValue("SubKeepLanguages").length) {
    issues.push(settingsReadinessIssue("medium", "SubKeepLanguages is empty. Preferred-language subtitle routing may become unpredictable."));
  }
  if (changedKey("ConvertTx3gToSrt") && boolValue("ConvertTx3gToSrt") === false) {
    issues.push(settingsReadinessIssue("medium", "ConvertTx3gToSrt is disabled. Preferred-language TX3G/mov_text subtitles will not produce SRT copies."));
  }
  if (changedKey("ConvertBdpgsToSrt") && boolValue("ConvertBdpgsToSrt") === false) {
    issues.push(settingsReadinessIssue("medium", "ConvertBdpgsToSrt is disabled. Preferred-language PGS subtitles will not produce OCR SRT copies."));
  }
  if (changedKey("PreferredDefaultAudioLanguages") && !listValue("PreferredDefaultAudioLanguages").length) {
    issues.push(settingsReadinessIssue("medium", "PreferredDefaultAudioLanguages is empty. Default audio selection will depend on source metadata."));
  }
  if ((changedKey("CompatibleAudioCodecs") || changedKey("AudioPassthroughProfile")) && !listValue("CompatibleAudioCodecs").length && textValue("AudioPassthroughProfile") === "custom_codec_list") {
    issues.push(settingsReadinessIssue("high", "AudioPassthroughProfile is custom_codec_list but CompatibleAudioCodecs is empty."));
  }
  if (changedKey("AudioPassthroughProfile") && textValue("AudioPassthroughProfile") === "custom_codec_list") {
    issues.push(settingsReadinessIssue("medium", "AudioPassthroughProfile uses a manual codec list. Preview should confirm copy-vs-transcode impact."));
  }
  if (changedKey("AudioPassthroughProfile") && textValue("AudioPassthroughProfile") === "lossless_passthrough") {
    issues.push(settingsReadinessIssue("medium", "AudioPassthroughProfile preserves lossless codecs. Some Plex clients may transcode those tracks."));
  }
  if (changedKey("AudioDownmixMode") && textValue("AudioDownmixMode") === "stereo") {
    issues.push(settingsReadinessIssue("medium", "AudioDownmixMode forces stereo. This improves compatibility but discards surround channels."));
  }
  if (changedKey("AudioMaxChannels") && Number(textValue("AudioMaxChannels") || 0) > 0 && Number(textValue("AudioMaxChannels") || 0) < 6) {
    issues.push(settingsReadinessIssue("medium", "AudioMaxChannels is below 6. Normal 5.1 tracks may be downmixed during normalization."));
  }
  if (changedKey("OutputContainer") && textValue("OutputContainer").toLowerCase() === "mp4") {
    issues.push(settingsReadinessIssue("medium", "OutputContainer is MP4. Verify subtitle and audio policies avoid muxing unsupported streams into MP4."));
  }
  if (changedKey("NetworkRole") && textValue("NetworkRole") && textValue("NetworkRole").toLowerCase() !== "standalone") {
    issues.push(settingsReadinessIssue("medium", "NetworkRole changes should be saved only when no local pipeline/coordinator/worker work is active."));
  }
  if (changedKey("DeferredPublish") && boolValue("DeferredPublish") === true) {
    issues.push(settingsReadinessIssue("review", "DeferredPublish is enabled. Pending Publish must be monitored and drained after output validation."));
  }
  if (changedKey("CleanupRemoteStaging") && boolValue("CleanupRemoteStaging") === true) {
    issues.push(settingsReadinessIssue("medium", "CleanupRemoteStaging is enabled. Remote staging cleanup should be reviewed against slow or unreliable publish shares."));
  }
  if (changedKey("TransientFailureRetryLimit") && Number(textValue("TransientFailureRetryLimit") || 0) > 8) {
    issues.push(settingsReadinessIssue("medium", "TransientFailureRetryLimit is high. Persistent publish or copy failures may wait too long for operator review."));
  }
  if (changedKey("RobocopyTimeoutSeconds")) {
    const timeoutSeconds = Number(textValue("RobocopyTimeoutSeconds") || 0);
    if (timeoutSeconds > 0 && timeoutSeconds < 300) {
      issues.push(settingsReadinessIssue("medium", "RobocopyTimeoutSeconds is below five minutes. Large media copies on slow disks or SMB shares may fail prematurely."));
    }
  }
  return issues;
}

function settingsPatchSaveReadinessStatus(entries) {
  if (!entries.length) return "No patch";
  const changedEntries = entries.filter((entry) => entry.changed);
  if (!changedEntries.length) return "No changes";
  const issues = settingsPatchSaveReadinessIssues(entries);
  if (issues.some((issue) => issue.severity === "critical")) return "Blocked";
  if (issues.some((issue) => issue.severity === "high")) return "High review";
  if (issues.some((issue) => issue.severity === "medium" || issue.severity === "review")) return "Review";
  return "Ready to preview";
}

function settingsSaveReviewPostureStatus(posture) {
  const value = String(posture || "").toLowerCase();
  if (value.includes("blocked") || value.includes("critical") || value.includes("high")) return "blocked";
  if (value.includes("review") || value.includes("staged") || value.includes("preview") || value.includes("medium") || value.includes("no history")) return "warning";
  return "match";
}

function settingsSaveReviewLatestCommand() {
  const history = typeof getCommandHistory === "function" ? getCommandHistory() : [];
  if (!Array.isArray(history)) return null;
  return history.find(isSettingsCommand) || null;
}

function settingsSaveReviewRows(entries) {
  const rows = [];
  const changedEntries = entries.filter((entry) => entry.changed);
  const unknownEntries = entries.filter((entry) => !entry.field);
  const issues = settingsPatchSaveReadinessIssues(entries);
  const criticalIssues = issues.filter((issue) => issue.severity === "critical");
  const highIssues = issues.filter((issue) => issue.severity === "high");
  const reviewIssues = issues.filter((issue) => !["critical", "high"].includes(issue.severity));
  const groups = Array.from(new Set(changedEntries.map((entry) => entry.group?.name || "Unknown / custom")));
  const readinessStatus = settingsPatchSaveReadinessStatus(entries);

  rows.push({
    key: "patch-state",
    checkpoint: "Patch state",
    posture: changedEntries.length ? "staged" : entries.length ? "unchanged" : "idle",
    evidence: `${entries.length} staged key(s); ${changedEntries.length} effective change(s); ${unknownEntries.length} unknown key(s).`,
    action: changedEntries.length
      ? "Run backend Preview Patch before Save Patch; do not assume local review is complete."
      : entries.length
        ? "No effective save is needed unless the JSON is being edited for a future patch."
        : "Stage Changes JSON with a builder or manual edit before preview/save.",
    detail: [
      `Readiness status: ${readinessStatus}`,
      groups.length ? `Impacted groups: ${groups.join(", ")}` : "Impacted groups: none",
      "Backend preview/save remains authoritative for schema validation, PSD1 serialization, backups, and reload.",
    ],
  });

  rows.push({
    key: "schema-coverage",
    checkpoint: "Schema coverage",
    posture: unknownEntries.length ? "blocked review" : "known keys",
    evidence: unknownEntries.length
      ? unknownEntries.slice(0, 8).map((entry) => entry.key).join(", ") + (unknownEntries.length > 8 ? `, +${unknownEntries.length - 8} more` : "")
      : "Every staged key is present in the backend field definitions loaded by the WebView.",
    action: unknownEntries.length
      ? "Treat unknown keys as schema drift. Preview Patch must explain them before Save Patch."
      : "Use structured builders for routine edits; backend Preview Patch still validates known keys.",
    detail: unknownEntries.length
      ? unknownEntries.map((entry) => `${entry.key}: staged=${formatConfigValue(entry.staged)}`)
      : ["No staged schema-drift keys were detected locally."],
  });

  rows.push({
    key: "safety-blockers",
    checkpoint: "Safety blockers",
    posture: criticalIssues.length ? "critical blocked" : highIssues.length ? "high review" : "clear",
    evidence: criticalIssues.concat(highIssues).slice(0, 4).map((issue) => `[${issue.severity}] ${issue.message}`).join(" | ") || "No critical/high local safety blocker detected.",
    action: criticalIssues.length
      ? "Do not save until critical source-safety or policy conflicts are deliberately resolved."
      : highIssues.length
        ? "Review each high-risk item and run backend Preview Patch before Save Patch."
        : "Continue to medium review and backend preview.",
    detail: criticalIssues.concat(highIssues).length
      ? criticalIssues.concat(highIssues).map((issue) => `[${issue.severity}] ${issue.message}`)
      : ["Critical/high checks were clear in local review."],
  });

  rows.push({
    key: "medium-review",
    checkpoint: "Policy review",
    posture: reviewIssues.length ? "review" : "clear",
    evidence: reviewIssues.slice(0, 5).map((issue) => `[${issue.severity}] ${issue.message}`).join(" | ") || "No medium/review local issue detected.",
    action: reviewIssues.length
      ? "Confirm these are intentional before unattended processing; backend preview may add stricter warnings."
      : "No local policy-review item detected; backend preview is still required before saving meaningful changes.",
    detail: reviewIssues.length
      ? reviewIssues.map((issue) => `[${issue.severity}] ${issue.message}`)
      : ["No medium/review local checks were triggered."],
  });

  const latestCommand = settingsSaveReviewLatestCommand();
  if (!latestCommand) {
    rows.push({
      key: "backend-command",
      checkpoint: "Backend evidence",
      posture: "no history",
      evidence: "No recent settings validate/reload/preview/save command is available.",
      action: "Use Preview Patch first, then Save Patch only after the backend response is clean.",
      detail: [
        "No backend command evidence is visible in recent command history.",
        "This panel never writes the PSD1; Save Patch remains the backend-owned persistence command.",
      ],
    });
  } else {
    const command = String(latestCommand.command || latestCommand.raw?.command || "").toLowerCase();
    const ok = latestCommand.ok === true || latestCommand.result === "ok" || latestCommand.raw?.ok === true;
    const isSave = command === "settings.save_patch";
    const isPreview = command === "settings.preview_patch";
    rows.push({
      key: "backend-command",
      checkpoint: "Backend evidence",
      posture: ok && isSave ? "saved evidence" : ok && isPreview ? "preview only" : ok ? "ok" : "review",
      evidence: settingsCommandHistoryLine(latestCommand) || command || "settings command",
      action: ok && isSave
        ? "Refresh/reload and confirm Saved Settings Trust before relying on this config for Launch."
        : isPreview
          ? "Preview does not persist settings. Save Patch must succeed before Launch uses the staged config."
          : "Resolve backend command warning/error before saving or launching with this patch.",
      detail: [
        `Command: ${command || "unknown"}`,
        `Result: ${latestCommand.result || (ok ? "ok" : latestCommand.severity || "unknown")}`,
        latestCommand.message ? `Message: ${latestCommand.message}` : "Message: none",
        "Use Settings Command History and Home/Diagnostics command drilldown for full backend result data.",
      ],
    });
  }

  rows.push({
    key: "mutation-boundary",
    checkpoint: "Mutation boundary",
    posture: "backend-owned",
    evidence: "Local review is display-only; Preview Patch and Save Patch remain backend-owned commands.",
    action: "Do not treat this table as persistence proof. Confirm backend result and saved trust summary after saving.",
    detail: [
      "This review table does not save settings, launch work, mutate queue state, rewrite PSD1 files, or touch media.",
      "Backend preview/save owns validation, redacted diffs, backups, PSD1 serialization, reload, and command journaling.",
    ],
  });

  return rows;
}

function settingsSaveReviewStatus(rows = []) {
  if (!rows.length) return "No review";
  if (rows.some((row) => settingsSaveReviewPostureStatus(row.posture) === "blocked")) return "Blocked review";
  if (rows.some((row) => settingsSaveReviewPostureStatus(row.posture) === "warning")) return "Review";
  return "Ready";
}

function settingsSaveReviewDetailLines(row) {
  if (!row) {
    return [
      "No settings save review row selected.",
      "Select a row to inspect why a staged patch is blocked, review-needed, preview-only, or safe to continue.",
      "Mutation guardrail: this detail view is read-only and cannot save settings, launch work, or touch media files.",
    ];
  }
  const lines = [
    `Checkpoint: ${row.checkpoint}`,
    `Posture: ${row.posture}`,
    `Evidence: ${row.evidence}`,
    `Safe next step: ${row.action}`,
  ];
  if (Array.isArray(row.detail) && row.detail.length) {
    lines.push("", "Detail:");
    row.detail.forEach((line) => lines.push(`- ${line}`));
  }
  lines.push("", "Mutation guardrail: Settings Preview/Save remains backend-owned; this row only explains local review posture.");
  return lines;
}

function selectedSettingsSaveReviewRow(rows) {
  if (!selectedSettingsSaveReviewKey) return null;
  return rows.find((row) => row.key === selectedSettingsSaveReviewKey) || null;
}

function renderSettingsSaveReviewFromEntries(entries) {
  const rows = settingsSaveReviewRows(entries);
  const tbody = byId("settings-save-review-rows");
  if (!tbody) return;
  if (selectedSettingsSaveReviewKey && !rows.some((row) => row.key === selectedSettingsSaveReviewKey)) {
    selectedSettingsSaveReviewKey = "";
  }
  if (!rows.length) {
    clearRows(tbody, 4, "No settings save review rows loaded.");
    setText("settings-save-review-legend", "Settings save review rows: no selectable rows.");
    setText("settings-save-review-detail", settingsSaveReviewDetailLines(null).join("\n"));
    return;
  }
  tbody.replaceChildren();
  rows.forEach((item) => {
    const row = document.createElement("tr");
    row.dataset.status = settingsSaveReviewPostureStatus(item.posture);
    appendCells(row, [item.checkpoint, item.posture, item.evidence, item.action]);
    makeRowSelectable(row, () => {
      selectedSettingsSaveReviewKey = item.key;
      renderSettingsSaveReviewFromEntries(entries);
    }, {
      selected: selectedSettingsSaveReviewKey === item.key,
      label: `Settings save review ${item.checkpoint} ${item.posture}`,
    });
    tbody.appendChild(row);
  });
  updateTableStatusLegend("settings-save-review-legend", tbody, "Settings save review rows");
  setText("settings-save-review-detail", settingsSaveReviewDetailLines(selectedSettingsSaveReviewRow(rows)).join("\n"));
}

function renderSettingsPatchSaveReadinessFromEntries(entries) {
  const changedEntries = entries.filter((entry) => entry.changed);
  const status = settingsPatchSaveReadinessStatus(entries);
  const issues = settingsPatchSaveReadinessIssues(entries);
  setText("settings-save-readiness-status", status);
  const lines = [
    "Local save readiness checklist:",
    `Status: ${status}`,
    `Patch keys: ${entries.length}; effective changes: ${changedEntries.length}; unknown keys: ${entries.filter((entry) => !entry.field).length}.`,
    "Required operator action: use Preview Patch before Save Patch for any non-trivial change.",
    "Backend preview/save remains the source of truth for schema validation, risk policy, PSD1 serialization, backup creation, and config reload.",
  ];
  if (!entries.length) {
    lines.push("", "No patch keys are staged.");
  } else if (!changedEntries.length) {
    lines.push("", "No effective staged changes were detected.");
  }
  const changedGroups = Array.from(new Set(changedEntries.map((entry) => entry.group?.name || "Unknown / custom")));
  if (changedGroups.length) lines.push("", `Impacted group(s): ${changedGroups.join(", ")}.`);
  if (issues.length) {
    lines.push("", "Review item(s):");
    issues.forEach((issue) => lines.push(`- [${issue.severity}] ${issue.message}`));
  } else if (changedEntries.length) {
    lines.push("", "No local blocker detected. Run backend Preview Patch before saving.");
  }
  lines.push("", "Mutation guardrail: this checklist does not save settings, launch work, mutate queue state, or touch media files.");
  setText("settings-save-readiness", lines.join("\n"));
}

function renderSettingsPatchImpactSummaryForError(message) {
  setText(
    "settings-patch-impact-summary",
    `Local impact unavailable because Changes JSON is invalid.\n${message}\nBackend preview cannot run until this is valid JSON.`
  );
}

function renderSettingsPatchSaveReadinessForError(message) {
  setText("settings-save-readiness-status", "Invalid JSON");
  setText(
    "settings-save-readiness",
    `Local save readiness unavailable because Changes JSON is invalid.\n${message}\nBackend preview/save cannot run until this is valid JSON.`
  );
  clearRows(byId("settings-save-review-rows"), 4, "Settings save review unavailable because Changes JSON is invalid.");
  setText("settings-save-review-legend", "Settings save review rows: no selectable rows.");
  setText(
    "settings-save-review-detail",
    [
      "Settings save review unavailable because Changes JSON is invalid.",
      message,
      "Backend preview/save cannot run until this is valid JSON.",
      "Mutation guardrail: this detail view is read-only and cannot save settings, launch work, or touch media files.",
    ].join("\n")
  );
}

function settingsLaunchImpactGroupText(entry) {
  const groupName = String(entry?.group?.name || "Unknown / custom");
  const normalized = groupName.toLowerCase();
  if (normalized.includes("paths") || normalized.includes("file safety")) {
    return "May change source discovery, scratch/output roots, file stability checks, or source-preservation safeguards.";
  }
  if (normalized.includes("routing") || normalized.includes("size")) {
    return "May change remux-vs-encode routing, Plex compatibility posture, or output growth handling.";
  }
  if (normalized.includes("encoder") || normalized.includes("gpu")) {
    return "May change FFmpeg encoder selection, GPU/CPU fallback behavior, speed, or output size.";
  }
  if (normalized.includes("subtitle")) {
    return "May change SRT creation, original subtitle preservation, OCR/conversion routing, or language filtering.";
  }
  if (normalized.includes("audio")) {
    return "May change passthrough, default audio selection, downmixing, or no-audio output safeguards.";
  }
  if (normalized.includes("pending") || normalized.includes("publish") || normalized.includes("network")) {
    return "May change pending-publish behavior, copy retries, worker coordination, or slow-share recovery.";
  }
  if (normalized.includes("queue") || normalized.includes("reprocess")) {
    return "May change queue ordering, processed-output detection, or deliberate reprocess behavior.";
  }
  if (normalized.includes("runtime") || normalized.includes("diagnostics")) {
    return "May change scan cadence, subprocess timeout ceilings, retry escalation, or log volume.";
  }
  return "Backend preview must explain this setting before it is used for launch decisions.";
}

function settingsLaunchImpactLatestSettingsCommand() {
  const history = typeof getCommandHistory === "function" ? getCommandHistory() : [];
  if (!Array.isArray(history)) return null;
  return history.find(isSettingsCommand) || null;
}

function settingsLaunchImpactRows(entries) {
  const changedEntries = entries.filter((entry) => entry.changed);
  const issues = settingsPatchSaveReadinessIssues(entries);
  const rows = [];
  rows.push({
    area: "Patch state",
    posture: changedEntries.length ? "staged" : entries.length ? "unchanged" : "idle",
    evidence: `${entries.length} staged key(s); ${changedEntries.length} effective change(s); ${entries.filter((entry) => !entry.field).length} unknown key(s).`,
    check: changedEntries.length
      ? "Launch continues to use saved backend settings until Save Patch succeeds and settings reload/refresh completes."
      : "No effective staged changes are waiting to affect Launch.",
  });

  const grouped = new Map();
  changedEntries.forEach((entry) => {
    const name = entry.group?.name || "Unknown / custom";
    if (!grouped.has(name)) grouped.set(name, []);
    grouped.get(name).push(entry);
  });
  grouped.forEach((groupEntries, groupName) => {
    const hasUnknown = groupEntries.some((entry) => !entry.field);
    const hasHigh = groupEntries.some((entry) => entry.severity === "high");
    const posture = hasUnknown ? "blocked" : hasHigh ? "high review" : "review";
    rows.push({
      area: groupName,
      posture,
      evidence: groupEntries.slice(0, 8).map((entry) => entry.key).join(", ") + (groupEntries.length > 8 ? `, +${groupEntries.length - 8} more` : ""),
      check: settingsLaunchImpactGroupText(groupEntries[0]),
    });
  });

  rows.push({
    area: "Save readiness",
    posture: settingsPatchSaveReadinessStatus(entries),
    evidence: issues.length ? issues.slice(0, 4).map((issue) => `[${issue.severity}] ${issue.message}`).join(" | ") : "No local save blocker detected.",
    check: "Run backend Preview Patch before Save Patch. Backend preview/save owns schema validation, PSD1 writes, backups, and reload.",
  });

  const latestCommand = settingsLaunchImpactLatestSettingsCommand();
  if (!latestCommand) {
    rows.push({
      area: "Last backend settings command",
      posture: "no history",
      evidence: "No settings validate/reload/preview/save command is available in recent command history.",
      check: "Use Preview Patch before Save Patch; use Reload From Disk after out-of-band config edits.",
    });
  } else {
    const command = String(latestCommand.command || latestCommand.raw?.command || "").toLowerCase();
    const ok = latestCommand.ok === true || latestCommand.result === "ok" || latestCommand.raw?.ok === true;
    const isSave = command === "settings.save_patch";
    const isPreview = command === "settings.preview_patch";
    rows.push({
      area: "Last backend settings command",
      posture: ok && isSave ? "saved evidence" : ok && isPreview ? "preview only" : ok ? "ok" : "review",
      evidence: settingsCommandHistoryLine(latestCommand) || command || "settings command",
      check: ok && isSave
        ? "A successful backend save is visible. Confirm Saved Settings Trust/Launch risk after refresh before starting long runs."
        : isPreview
          ? "Preview does not apply changes to Launch. Save Patch must succeed before Launch uses this config."
          : "Resolve command warnings/errors before relying on changed settings for Launch.",
    });
  }

  rows.push({
    area: "Launch authority",
    posture: "backend-owned",
    evidence: "This panel never starts work, bypasses schedule, rewrites config, or touches media files.",
    check: "Launch readiness, schedule gates, close-readiness, and pipeline locks remain backend-owned.",
  });
  return rows;
}

function settingsLaunchImpactStatus(rows) {
  if (!rows.length) return "Not evaluated";
  const postures = rows.map((row) => String(row.posture || "").toLowerCase());
  if (postures.some((posture) => posture.includes("blocked"))) return "Blocked review";
  if (postures.some((posture) => posture.includes("high"))) return "High review";
  if (postures.some((posture) => posture.includes("staged") || posture.includes("preview only") || posture.includes("review") || posture.includes("no history"))) return "Review";
  return "Ready";
}

function settingsLaunchImpactSummaryLines(rows) {
  const counts = rows.reduce((acc, row) => {
    const key = String(row.posture || "unknown");
    acc[key] = (acc[key] || 0) + 1;
    return acc;
  }, {});
  const reviewRows = rows.filter((row) => {
    const posture = String(row.posture || "").toLowerCase();
    return posture.includes("staged")
      || posture.includes("review")
      || posture.includes("blocked")
      || posture.includes("high")
      || posture.includes("preview only")
      || posture.includes("no history");
  });
  const lines = [
    "Settings-to-launch handoff:",
    `Status: ${settingsLaunchImpactStatus(rows)}`,
    `Rows: ${rows.length}; staged=${counts.staged || 0}; blocked=${counts.blocked || 0}; high-review=${counts["high review"] || 0}; preview-only=${counts["preview only"] || 0}.`,
    "Launch uses saved backend settings, not unsaved Changes JSON. Save Patch plus refresh/reload is required before a staged patch can affect Launch.",
    "Backend launch validation remains the source of truth for schedule gates, active-work locks, and pipeline start acceptance.",
  ];
  if (reviewRows.length) {
    lines.push("", "Rows needing operator review before launch:");
    reviewRows.slice(0, 6).forEach((row) => lines.push(`- ${row.area}: ${row.posture}; ${row.check}`));
  } else {
    lines.push("", "No local settings-to-launch review items detected.");
  }
  lines.push("", "Mutation guardrail: this handoff is read-only and cannot save settings, launch work, mutate queue state, or touch media files.");
  return lines;
}

function renderSettingsLaunchImpactHandoffFromEntries(entries) {
  const rows = settingsLaunchImpactRows(entries);
  setText("settings-launch-impact-status", settingsLaunchImpactStatus(rows));
  setText("settings-launch-impact-summary", settingsLaunchImpactSummaryLines(rows).join("\n"));
  setText("settings-launch-impact-legend", "Settings-to-launch handoff is read-only; backend launch validation remains authoritative.");
  const tbody = byId("settings-launch-impact-rows");
  if (!rows.length) {
    clearRows(tbody, 4, "No settings-to-launch impact rows loaded.");
    return;
  }
  tbody.replaceChildren();
  rows.forEach((item) => {
    const row = document.createElement("tr");
    const posture = String(item.posture || "").toLowerCase();
    row.dataset.status = posture.includes("blocked") ? "blocked" : (posture.includes("review") || posture.includes("staged") || posture.includes("preview only") || posture.includes("no history") ? "warning" : "match");
    appendCells(row, [item.area, item.posture, item.evidence, item.check]);
    tbody.appendChild(row);
  });
}

function renderSettingsLaunchImpactHandoffForError(message) {
  setText("settings-launch-impact-status", "Invalid JSON");
  setText(
    "settings-launch-impact-summary",
    `Settings-to-launch handoff unavailable because Changes JSON is invalid.\n${message}\nLaunch will continue using saved backend settings; backend preview/save cannot run until this is valid JSON.`
  );
  clearRows(byId("settings-launch-impact-rows"), 4, "Settings-to-launch handoff unavailable because Changes JSON is invalid.");
  setText("settings-launch-impact-legend", "Settings-to-launch handoff is read-only; backend launch validation remains authoritative.");
}

function settingsBackendCommandEvidenceLine(evidence) {
  if (!evidence || !evidence.result) return "No command result captured.";
  return settingsCommandHistoryLine(evidence.result) || evidence.result.message || evidence.command || "settings command";
}

function settingsBackendResultEvidence(kind) {
  if (kind === "preview") return lastSettingsPatchPreviewEvidence;
  if (kind === "save") return lastSettingsPatchSaveEvidence;
  if (kind === "reload") return lastSettingsReloadEvidence;
  return null;
}

function settingsCommandProgressObject(result) {
  const data = result?.data && typeof result.data === "object" ? result.data : {};
  return data.settings_progress && typeof data.settings_progress === "object" ? data.settings_progress : {};
}

function settingsCommandProgressBars(result) {
  const data = result?.data && typeof result.data === "object" ? result.data : {};
  const progress = settingsCommandProgressObject(result);
  if (Array.isArray(progress.progress_bars)) return progress.progress_bars.filter(Boolean);
  if (Array.isArray(data.progress_bars)) return data.progress_bars.filter(Boolean);
  return [];
}

function settingsLatestProgressResult() {
  const candidates = [
    lastSettingsPatchSaveEvidence?.result,
    lastSettingsReloadEvidence?.result,
    lastSettingsPatchPreviewEvidence?.result,
  ];
  return candidates.find((result) => settingsCommandProgressBars(result).length) || null;
}

function renderSettingsSaveProgress(result = null) {
  if (typeof renderProgressBarsInto !== "function") return;
  const payload = result || settingsLatestProgressResult();
  const progress = settingsCommandProgressObject(payload);
  renderProgressBarsInto("settings-save-progress-bars", settingsCommandProgressBars(payload), progress, "No settings save/reload progress loaded.");
}

function settingsProgressDetailLines(progress) {
  if (!progress || typeof progress !== "object" || !Object.keys(progress).length) return [];
  const steps = Array.isArray(progress.steps) ? progress.steps.filter(Boolean) : [];
  const lines = [
    "",
    "Settings save/reload progress:",
    `Status: ${progress.status || "unknown"}`,
    progress.detail ? `Detail: ${progress.detail}` : "",
  ].filter(Boolean);
  if (steps.length) {
    lines.push("Steps:");
    steps.forEach((step) => {
      lines.push(`- ${step.label || step.key || "Step"}: ${step.status || "unknown"}${step.detail ? `; ${step.detail}` : ""}`);
    });
  }
  return lines;
}

function settingsBackendResultRowKey(row) {
  return String(row?.key || row?.signal || "backend-result").toLowerCase().replace(/[^a-z0-9]+/g, "-");
}

function settingsBackendResultRows(entries = []) {
  const rows = [];
  const changedEntries = entries.filter((entry) => entry.changed);
  const signature = settingsCurrentPatchSignature();
  const hasPatch = Boolean(signature && signature !== "{}");
  const preview = lastSettingsPatchPreviewEvidence;
  const save = lastSettingsPatchSaveEvidence;
  const previewMatches = Boolean(preview && signature && preview.signature === signature);
  const saveMatches = Boolean(save && signature && save.signature === signature);
  const previewResult = preview?.result || {};
  const saveResult = save?.result || {};
  const previewData = previewResult.data && typeof previewResult.data === "object" ? previewResult.data : {};
  const saveData = saveResult.data && typeof saveResult.data === "object" ? saveResult.data : {};

  rows.push({
    key: "current-staged-patch",
    signal: "Current staged patch",
    posture: !hasPatch ? "idle" : changedEntries.length ? "staged" : "unchanged",
    evidence: !hasPatch
      ? "Changes JSON is empty."
      : `${entries.length} staged key(s); ${changedEntries.length} effective change(s); signature=${signature.slice(0, 16)}...`,
    action: changedEntries.length
      ? "Run Preview Patch and confirm the backend result matches the current staged JSON before saving."
      : "No effective save is needed unless this JSON is being prepared for a future edit.",
  });

  rows.push({
    key: "backend-preview",
    signal: "Backend preview",
    evidence_ref: "preview",
    posture: !preview ? "missing" : previewMatches && previewResult.ok === true ? "fresh preview" : previewMatches ? "preview issue" : "stale preview",
    evidence: preview
      ? settingsBackendCommandEvidenceLine(preview)
      : "No backend Preview Patch result has been captured in this page session.",
    action: !preview
      ? "Use Preview Patch before Save Patch for any non-trivial change."
      : previewMatches && previewResult.ok === true
        ? "Preview matches the current staged JSON. Review warnings/errors and redacted diff before saving."
        : previewMatches
          ? "Resolve backend preview warnings/errors before saving."
          : "Patch JSON changed after the last preview. Preview again before saving.",
  });

  rows.push({
    key: "preview-risk-output",
    signal: "Preview risk output",
    evidence_ref: "preview",
    posture: !preview ? "missing" : Array.isArray(previewResult.errors) && previewResult.errors.length ? "blocked" : previewData.diff_truncated ? "review" : Array.isArray(previewResult.warnings) && previewResult.warnings.length ? "review" : "available",
    evidence: preview
      ? `changed=${Array.isArray(previewData.changed_keys) ? previewData.changed_keys.length : 0}; removed=${Array.isArray(previewData.removed_keys) ? previewData.removed_keys.length : 0}; diff_lines=${Array.isArray(previewData.redacted_diff_lines) ? previewData.redacted_diff_lines.length : 0}; truncated=${previewData.diff_truncated === true ? "yes" : "no"}`
      : "No backend redacted diff or risk summary is available.",
    action: preview
      ? "Use the redacted diff and risk summary as the backend-owned evidence for what would change."
      : "Run Preview Patch to get backend-owned redacted diff and risk classification.",
  });

  rows.push({
    key: "save-confirmation-boundary",
    signal: "Save confirmation boundary",
    posture: "explicit confirmation required",
    evidence: "The backend save command requires confirm_save=true and the WebView asks for confirmation before sending it.",
    action: "Cancel if the preview is stale, if warnings are unexplained, or if active pipeline work could observe a partially reviewed config change.",
  });

  rows.push({
    key: "backend-save",
    signal: "Backend save",
    evidence_ref: "save",
    posture: !save ? "not saved" : saveMatches && saveResult.ok === true ? "saved" : saveMatches ? "save issue" : "previous save",
    evidence: save
      ? settingsBackendCommandEvidenceLine(save)
      : "No backend Save Patch result has been captured in this page session.",
    action: !save
      ? "Save Patch must succeed before Launch can use these staged settings."
      : saveMatches && saveResult.ok === true
        ? "Confirm reload and Saved Settings Trust before launching unattended work."
        : saveMatches
          ? "Resolve backend save warnings/errors before relying on the patch."
          : "The last save was for different JSON. Do not treat it as proof for the current patch.",
  });

  rows.push({
    key: "reload-saved-state",
    signal: "Reload / saved state",
    evidence_ref: "save",
    posture: saveMatches && saveResult.ok === true && saveData.reloaded === true
      ? "reloaded"
      : saveMatches && saveResult.ok === true && saveData.reloaded === false
        ? "reload issue"
        : save && saveResult.ok === true
          ? "previous reload"
          : "not proven",
    evidence: saveMatches && saveResult.ok === true
      ? `writes_config=${saveData.writes_config === true ? "yes" : "no"}; reloaded=${saveData.reloaded === true ? "yes" : saveData.reloaded === false ? "no" : "n/a"}; config=${saveData.config_path || ""}`
      : save && saveResult.ok === true
        ? "The last successful save/reload evidence belongs to different staged JSON."
        : "No successful save/reload evidence is available for this staged patch.",
    action: saveMatches && saveResult.ok === true && saveData.reloaded === true
      ? "Refresh has backend proof that the active config was reloaded."
      : save && saveResult.ok === true && !saveMatches
        ? "Preview/save the current staged JSON before treating reload evidence as relevant."
      : "Use Reload From Disk or refresh after resolving save/reload issues; Launch uses saved backend settings only.",
  });

  rows.push({
    key: "mutation-boundary",
    signal: "Mutation boundary",
    posture: "backend-owned",
    evidence: "This table is read-only and cannot save settings, launch work, drain, rename, publish, or touch media files.",
    action: "Only backend command results count as persistence evidence.",
  });

  return rows;
}

function settingsBackendResultSelectedRow(rows) {
  const list = Array.isArray(rows) ? rows : [];
  if (selectedSettingsBackendResultKey) {
    const selected = list.find((row) => settingsBackendResultRowKey(row) === selectedSettingsBackendResultKey);
    if (selected) return selected;
  }
  return list.find((row) => {
    const posture = String(row?.posture || "").toLowerCase();
    return posture.includes("blocked") || posture.includes("issue") || posture.includes("stale");
  }) || list.find((row) => {
    const posture = String(row?.posture || "").toLowerCase();
    return posture.includes("missing") || posture.includes("not saved") || posture.includes("previous") || posture.includes("not proven") || posture.includes("review");
  }) || list[0] || null;
}

function settingsBackendResultListLines(label, values, limit = 8) {
  const list = Array.isArray(values) ? values.map((item) => String(item || "").trim()).filter(Boolean) : [];
  if (!list.length) return [`${label}: none`];
  const lines = [`${label}:`];
  list.slice(0, limit).forEach((item) => lines.push(`- ${item}`));
  if (list.length > limit) lines.push(`- ...${list.length - limit} more`);
  return lines;
}

function settingsBackendRiskSummaryLines(riskSummary) {
  if (!riskSummary || typeof riskSummary !== "object") return ["Risk summary: none"];
  const counts = riskSummary.counts && typeof riskSummary.counts === "object" ? riskSummary.counts : {};
  const items = Array.isArray(riskSummary.items) ? riskSummary.items : [];
  const lines = [
    "Risk summary:",
    `Highest severity: ${riskSummary.highest_severity || "unknown"}`,
    `Counts: critical ${counts.critical || 0}, high ${counts.high || 0}, medium ${counts.medium || 0}, low ${counts.low || 0}`,
  ];
  if (!items.length) {
    lines.push("- none");
    return lines;
  }
  items.slice(0, 8).forEach((item) => {
    lines.push(`- [${item?.severity || "unknown"}] ${item?.key || "(unknown key)"} (${item?.code || "risk"}): ${item?.message || ""}`);
  });
  if (items.length > 8) lines.push(`- ...${items.length - 8} more`);
  return lines;
}

function settingsBackendResultDetailLines(row) {
  if (!row) {
    return [
      "Backend preview/save result detail:",
      "Select a backend result row to inspect command evidence, warnings, errors, redacted diff, risk summary, and reload proof.",
      "Mutation guardrail: this detail panel is read-only and cannot save settings, launch work, drain, rename, publish, or touch media files.",
    ];
  }
  const evidence = settingsBackendResultEvidence(row.evidence_ref);
  const result = evidence?.result || null;
  const data = result?.data && typeof result.data === "object" ? result.data : {};
  const currentSignature = settingsCurrentPatchSignature();
  const evidenceSignature = evidence?.signature || "";
  const changedKeys = Array.isArray(data.changed_keys) ? data.changed_keys : [];
  const removedKeys = Array.isArray(data.removed_keys) ? data.removed_keys : [];
  const diffLines = Array.isArray(data.redacted_diff_lines) ? data.redacted_diff_lines : [];
  const lines = [
    "Backend preview/save result detail:",
    `Signal: ${row.signal || "unknown"}`,
    `Posture: ${row.posture || "unknown"}`,
    `Evidence: ${row.evidence || ""}`,
    `Operator action: ${row.action || ""}`,
    "",
    "Patch identity:",
    `Current staged signature: ${currentSignature ? `${currentSignature.slice(0, 48)}${currentSignature.length > 48 ? "..." : ""}` : "(invalid or empty)"}`,
    `Evidence signature: ${evidenceSignature ? `${evidenceSignature.slice(0, 48)}${evidenceSignature.length > 48 ? "..." : ""}` : "(none)"}`,
    `Evidence matches current JSON: ${evidenceSignature && currentSignature && evidenceSignature === currentSignature ? "yes" : "no"}`,
  ];
  if (evidence) {
    lines.push(`Captured at: ${evidence.captured_at || "unknown"}`);
    lines.push(`Captured command: ${evidence.command || result?.command || "unknown"}`);
  }
  if (result) {
    lines.push("");
    lines.push("Command result:");
    lines.push(`Command: ${result.command || "unknown"}`);
    lines.push(`OK: ${result.ok === true ? "yes" : "no"}`);
    lines.push(`Severity: ${result.severity || "unknown"}`);
    lines.push(`Message: ${result.message || ""}`);
    lines.push(...settingsBackendResultListLines("Warnings", result.warnings));
    lines.push(...settingsBackendResultListLines("Errors", result.errors));
  }
  if (Object.keys(data).length) {
    lines.push("");
    lines.push("Backend data:");
    lines.push(`Writes config: ${data.writes_config === true ? "yes" : data.writes_config === false ? "no" : "n/a"}`);
    lines.push(`Reloaded: ${data.reloaded === true ? "yes" : data.reloaded === false ? "no" : "n/a"}`);
    if (data.config_path) lines.push(`Config: ${data.config_path}`);
    if (data.backup_path) lines.push(`Backup: ${data.backup_path}`);
    lines.push(`Changed keys: ${changedKeys.join(", ") || "none"}`);
    lines.push(`Removed keys: ${removedKeys.join(", ") || "none"}`);
    lines.push(`Redacted diff lines: ${diffLines.length}; truncated=${data.diff_truncated === true ? "yes" : "no"}`);
    if (diffLines.length) {
      lines.push("Redacted diff:");
      diffLines.slice(0, 12).forEach((item) => lines.push(item));
      if (diffLines.length > 12) lines.push(`...${diffLines.length - 12} more diff line(s)`);
    }
    lines.push(...settingsBackendRiskSummaryLines(data.risk_summary));
    lines.push(...settingsProgressDetailLines(data.settings_progress));
  }
  if (!evidence && row.key === "save-confirmation-boundary") {
    lines.push("");
    lines.push("Save boundary:");
    lines.push("The WebView sends Save Patch only after browser confirmation and includes confirm_save=true.");
    lines.push("The backend still rejects saves without confirmation and owns PSD1 serialization, backup creation, validation, and reload.");
  }
  if (!evidence && row.key === "current-staged-patch") {
    lines.push("");
    lines.push("Current staged patch:");
    try {
      const entries = settingsPatchImpactEntries(parseSettingsPatchJson());
      const changed = entries.filter((entry) => entry.changed);
      const unknown = entries.filter((entry) => !entry.field);
      lines.push(`Staged keys: ${entries.length}`);
      lines.push(`Effective changes: ${changed.length}`);
      lines.push(`Unknown keys: ${unknown.length}`);
      changed.slice(0, 10).forEach((entry) => lines.push(`- ${entry.key}: ${formatConfigValue(entry.current)} -> ${formatConfigValue(entry.staged)} (${entry.status})`));
      if (changed.length > 10) lines.push(`- ...${changed.length - 10} more change(s)`);
    } catch (error) {
      lines.push(`Patch JSON could not be parsed: ${error instanceof Error ? error.message : String(error)}`);
    }
  }
  lines.push("");
  lines.push("Mutation guardrail: selecting this row does not preview, save, reload, launch, drain, rename, publish, rewrite config, or touch media files.");
  return lines;
}

function settingsBackendResultStatus(rows = []) {
  const postures = rows.map((row) => String(row.posture || "").toLowerCase());
  if (postures.some((posture) => posture.includes("blocked") || posture.includes("issue"))) return "Blocked review";
  if (postures.some((posture) => posture.includes("stale") || posture.includes("missing") || posture.includes("not saved") || posture.includes("previous") || posture.includes("not proven") || posture.includes("review"))) return "Review";
  if (postures.some((posture) => posture.includes("saved") || posture.includes("reloaded"))) return "Saved evidence";
  return "No backend result";
}

function settingsBackendResultSummaryLines(rows) {
  const previewRow = rows.find((row) => row.signal === "Backend preview");
  const saveRow = rows.find((row) => row.signal === "Backend save");
  const reloadRow = rows.find((row) => row.signal === "Reload / saved state");
  const lines = [
    "Backend preview/save handoff:",
    `Status: ${settingsBackendResultStatus(rows)}`,
    `Preview: ${previewRow?.posture || "missing"}`,
    `Save: ${saveRow?.posture || "not saved"}`,
    `Reload: ${reloadRow?.posture || "not proven"}`,
    "Preview Patch is non-writing. Save Patch is the only persistence command and still requires explicit confirmation.",
    "Launch uses saved backend settings only; staged Changes JSON is not launch-active until save and reload succeed.",
  ];
  const reviewRows = rows.filter((row) => {
    const posture = String(row.posture || "").toLowerCase();
    return posture.includes("missing")
      || posture.includes("stale")
      || posture.includes("issue")
      || posture.includes("blocked")
      || posture.includes("not saved")
      || posture.includes("previous")
      || posture.includes("not proven")
      || posture.includes("review");
  });
  if (reviewRows.length) {
    lines.push("", "Rows needing attention:");
    reviewRows.slice(0, 6).forEach((row) => lines.push(`- ${row.signal}: ${row.action}`));
  } else {
    lines.push("", "No backend result contradiction detected for the current staged patch.");
  }
  lines.push("", "Mutation guardrail: this handoff is read-only and cannot save settings, launch work, or touch media files.");
  return lines;
}

function renderSettingsBackendResultFromEntries(entries) {
  const tbody = byId("settings-backend-result-rows");
  if (!tbody) return;
  const rows = settingsBackendResultRows(entries);
  if (selectedSettingsBackendResultKey && !rows.some((row) => settingsBackendResultRowKey(row) === selectedSettingsBackendResultKey)) {
    selectedSettingsBackendResultKey = "";
  }
  const selected = settingsBackendResultSelectedRow(rows);
  if (!selectedSettingsBackendResultKey && selected) {
    selectedSettingsBackendResultKey = settingsBackendResultRowKey(selected);
  }
  setText("settings-backend-result-status", settingsBackendResultStatus(rows));
  setText("settings-backend-result-summary", settingsBackendResultSummaryLines(rows).join("\n"));
  renderSettingsSaveProgress();
  setText("settings-backend-result-legend", "Backend result rows are read-only; Preview Patch and Save Patch remain backend-owned commands.");
  setText("settings-backend-result-detail", settingsBackendResultDetailLines(selected).join("\n"));
  if (!rows.length) {
    clearRows(tbody, 4, "No backend settings result rows loaded.");
    return;
  }
  tbody.replaceChildren();
  rows.forEach((item) => {
    const row = document.createElement("tr");
    const posture = String(item.posture || "").toLowerCase();
    row.dataset.status = posture.includes("blocked") || posture.includes("issue")
      ? "blocked"
      : (posture.includes("stale") || posture.includes("missing") || posture.includes("not saved") || posture.includes("previous") || posture.includes("not proven") || posture.includes("review") ? "warning" : "match");
    appendCells(row, [item.signal, item.posture, item.evidence, item.action]);
    const key = settingsBackendResultRowKey(item);
    makeRowSelectable(row, () => {
      selectedSettingsBackendResultKey = key;
      renderSettingsBackendResultFromEntries(entries);
    }, {
      selected: selectedSettingsBackendResultKey === key,
      label: `Inspect settings backend result ${item.signal || ""}`,
    });
    tbody.appendChild(row);
  });
  updateTableStatusLegend("settings-backend-result-legend", tbody, "Backend preview/save result rows");
}

function renderSettingsBackendResultForError(message) {
  setText("settings-backend-result-status", "Invalid JSON");
  setText(
    "settings-backend-result-summary",
    `Backend preview/save handoff unavailable because Changes JSON is invalid.\n${message}\nPreview Patch and Save Patch cannot run until this is valid JSON.`
  );
  clearRows(byId("settings-backend-result-rows"), 4, "Backend result handoff unavailable because Changes JSON is invalid.");
  renderSettingsSaveProgress(null);
  setText("settings-backend-result-legend", "Backend result rows are read-only; Preview Patch and Save Patch remain backend-owned commands.");
  setText("settings-backend-result-detail", [
    "Backend preview/save result detail:",
    `Patch JSON is invalid: ${message}`,
    "Fix Changes JSON before Preview Patch or Save Patch can run.",
    "Mutation guardrail: invalid JSON handling is local UI feedback only and does not write config.",
  ].join("\n"));
}

function renderSettingsPatchSummary() {
  const tbody = byId("settings-patch-summary-rows");
  if (!tbody) return;
  const changedOnly = byId("settings-patch-summary-changed-only")?.checked === true;
  let patch;
  try {
    patch = parseSettingsPatchJson();
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    clearRows(tbody, 5, `Patch JSON is invalid: ${message}`);
    setText("settings-patch-summary-status", "Patch summary unavailable because Changes JSON is invalid.");
    renderSettingsPatchImpactSummaryForError(message);
    renderSettingsPolicyDeltaForError(message);
    renderSettingsEffectivePolicyTrustForError(message);
    renderSettingsPatchSaveReadinessForError(message);
    renderSettingsLaunchImpactHandoffForError(message);
    renderSettingsBackendResultForError(message);
    return;
  }
  const impactEntries = settingsPatchImpactEntries(patch);
  renderSettingsPatchImpactSummaryFromEntries(impactEntries);
  renderSettingsPolicyDeltaFromEntries(impactEntries);
  renderSettingsEffectivePolicyTrustFromEntries(impactEntries);
  renderSettingsPatchSaveReadinessFromEntries(impactEntries);
  renderSettingsSaveReviewFromEntries(impactEntries);
  renderSettingsLaunchImpactHandoffFromEntries(impactEntries);
  renderSettingsBackendResultFromEntries(impactEntries);
  const keys = Object.keys(patch);
  if (!keys.length) {
    clearRows(tbody, 5, "No patch keys staged.");
    setText("settings-patch-summary-status", "No staged settings changes.");
    return;
  }
  tbody.replaceChildren();
  let changedCount = 0;
  let unchangedCount = 0;
  let unknownCount = 0;
  let visibleCount = 0;
  keys.sort((a, b) => a.localeCompare(b)).forEach((key) => {
    const field = settingsFieldDefinition(key);
    const current = settingsRawConfigValue(key);
    const staged = patch[key];
    let status = "";
    let statusKey = "";
    if (!field) {
      unknownCount += 1;
      status = "unknown key";
      statusKey = "unknown";
    } else if (settingsValuesEqual(current, staged)) {
      unchangedCount += 1;
      status = "unchanged";
      statusKey = "unchanged";
    } else {
      changedCount += 1;
      status = current === undefined ? "new value" : "changed";
      statusKey = current === undefined ? "new" : "changed";
    }
    if (changedOnly && statusKey === "unchanged") return;
    visibleCount += 1;
    const row = document.createElement("tr");
    row.dataset.status = statusKey;
    appendCells(row, [
      key,
      field?.label || key,
      current === undefined ? "(not set)" : formatConfigValue(current),
      formatConfigValue(staged),
      status,
    ]);
    tbody.appendChild(row);
  });
  if (!visibleCount) {
    clearRows(tbody, 5, "No changed or unknown patch keys to show.");
  }
  setText(
    "settings-patch-summary-status",
    `${keys.length} staged key${keys.length === 1 ? "" : "s"}: ${changedCount} changed, ${unchangedCount} unchanged, ${unknownCount} unknown, ${visibleCount} shown. Backend preview remains the source of truth.`
  );
}

function renderSettingsBuilderGuidance() {
  const lines = [];
  settingsBuilderFields.forEach(([key, id]) => {
    const field = settingsFieldDefinition(key);
    const label = field?.label || key;
    const value = settingsBuilderInputValue(id);
    const formattedValue = value ? formatSettingsChoiceLabel(value) : "(not set)";
    lines.push(`${label}: ${formattedValue}`);
    const choiceHelp = field?.choice_help && value ? field.choice_help[value] : "";
    if (choiceHelp) {
      lines.push(`  ${choiceHelp}`);
    } else if (field?.help) {
      lines.push(`  ${field.help}`);
    }
  });
  setText("settings-builder-guidance", lines.join("\n") || "No builder guidance loaded.");
}

function renderSettings(settings) {
  lastSettings = settings || {};
  const config = settings.config || {};
  lastSettingsValues = { ...config };
  lastSettingsFieldDefinitions = Array.isArray(settings.field_definitions) ? settings.field_definitions : [];
  lastSettingsFieldMap = Object.fromEntries(
    lastSettingsFieldDefinitions
      .filter((field) => field && field.key)
      .map((field) => [String(field.key), field])
  );
  const settingsEntries = Object.keys(config).sort((a, b) => a.localeCompare(b)).map((key) => ({
    key,
    value: formatConfigValue(config[key]),
  }));
  setSettingsRows(settingsEntries, settings.error || "No config values loaded.");
  const warnings = (settings.warnings || []).concat(settings.errors || []);
  setText("settings-status", warnings.length ? `${warnings.length} warning${warnings.length === 1 ? "" : "s"}` : "Read-only");
  setText("settings-count", `${settings.key_count || settingsEntries.length} keys`);
  const pathLines = Object.entries(settings.paths || {}).map(([key, value]) => `${key}: ${value}`);
  setText("settings-paths", pathLines.join("\n") || settings.error || "No settings paths loaded.");
  const auditRootInput = byId("audit-start-library-root");
  if (auditRootInput && !auditRootInput.value && (settings.paths || {}).outsource) {
    auditRootInput.value = settings.paths.outsource;
  }
  setText("settings-profiles", (settings.profiles || []).join("\n") || "No profiles found.");
  setText("settings-validation", warnings.join("\n") || "No validation warnings.");
  renderSettingsOverview(config);
  renderSettingsOperatorTrust(settings);
  renderSettingsBackendMediaPolicyReadiness(settings);
  if (!settingsBuilderInitialized || !settingsBuilderDirty) {
    syncSettingsBuilderFromConfig();
  } else {
    refreshSettingsBuilderChoices();
    renderSettingsBuilderGuidance();
  }
  if (!videoDetailSettingsBuilderState.initialized || !videoDetailSettingsBuilderState.dirty) {
    syncVideoDetailSettingsBuilderFromConfig();
  } else {
    refreshSettingsSelectChoices(videoDetailSettingsBuilderFields);
    renderVideoDetailSettingsBuilderGuidance();
  }
  if (!fileSafetySettingsBuilderState.initialized || !fileSafetySettingsBuilderState.dirty) {
    syncFileSafetySettingsBuilderFromConfig();
  } else {
    renderFileSafetySettingsBuilderGuidance();
  }
  if (!networkSettingsBuilderState.initialized || !networkSettingsBuilderState.dirty) {
    syncNetworkSettingsBuilderFromConfig();
  } else {
    refreshSettingsSelectChoices(networkSettingsBuilderFields);
    renderNetworkSettingsBuilderGuidance();
  }
  if (!queueSettingsBuilderState.initialized || !queueSettingsBuilderState.dirty) {
    syncQueueSettingsBuilderFromConfig();
  } else {
    renderQueueSettingsBuilderGuidance();
  }
  if (!runtimeSettingsBuilderState.initialized || !runtimeSettingsBuilderState.dirty) {
    syncRuntimeSettingsBuilderFromConfig();
  } else {
    refreshSettingsSelectChoices(runtimeSettingsBuilderFields);
    renderRuntimeSettingsBuilderGuidance();
  }
  if (!pendingPublishSettingsBuilderState.initialized || !pendingPublishSettingsBuilderState.dirty) {
    syncPendingPublishSettingsBuilderFromConfig();
  } else {
    renderPendingPublishSettingsBuilderGuidance();
  }
  if (!subtitleSettingsBuilderState.initialized || !subtitleSettingsBuilderState.dirty) {
    syncSubtitleSettingsBuilderFromConfig();
  } else {
    renderSubtitleSettingsBuilderGuidance();
  }
  if (!audioSettingsBuilderState.initialized || !audioSettingsBuilderState.dirty) {
    syncAudioSettingsBuilderFromConfig();
  } else {
    refreshAudioSettingsBuilderChoices();
    renderAudioSettingsBuilderGuidance();
  }
  renderSettingsMediaPolicyCrossCheck();
  renderSettingsActiveMediaPolicyHandoff();
  renderSettingsBdpgsOcrPathEvidence();
  renderSettingsPatchSummary();
  renderSettingsSafetyLocks();
  renderSettingsRawTriage();
  renderSettingsRawActionPlan();
  renderSettingsRows();
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

  async function previewSettingsPatch() {
    if (rejectSettingsCommandWhileBusy("settings.preview_patch", "settings-patch-status", "settings-patch-detail")) return;
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
  setSettingsCommandBusy(true);
  setText("settings-patch-status", "Previewing...");
  setText("settings-patch-detail", "Requesting backend patch preview. This will not save the PSD1.");
  const requestId = ++settingsPatchPreviewRequestId;
  try {
    const result = await apiPost("/api/settings/preview-patch", { changes });
    if (requestId !== settingsPatchPreviewRequestId) return;
    if ((byId("settings-patch-json")?.value || "{}") !== rawAtRequest) {
      setText("settings-patch-status", "Preview stale");
      setText("settings-patch-detail", "Patch JSON changed before the backend preview returned. Preview again before using this result.");
      return;
    }
    appendCommandResult(result);
    lastSettingsPatchPreviewEvidence = {
      signature: settingsPatchSignature(changes),
      command: "settings.preview_patch",
      result,
      captured_at: new Date().toISOString(),
    };
    setText("settings-patch-status", result.ok ? "Preview ready" : result.severity || "Preview failed");
    const data = result.data || {};
    const lines = [
      result.message || "Settings patch preview completed.",
      "",
      `Writes config: ${data.writes_config === true ? "yes" : "no"}`,
      `Changed keys: ${(data.changed_keys || []).join(", ") || "none"}`,
      `Removed keys: ${(data.removed_keys || []).join(", ") || "none"}`,
    ];
    if ((result.errors || []).length) {
      lines.push("", "Errors:", ...(result.errors || []).map((item) => `- ${item}`));
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
      setText("settings-patch-status", "Preview stale");
      setText("settings-patch-detail", "Patch JSON changed before the backend preview returned. Preview again before using this result.");
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
      signature: settingsPatchSignature(changes),
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
  const keys = Object.keys(changes);
  if (!keys.length) {
    setText("settings-patch-status", "No changes");
    setText("settings-patch-detail", "No settings patch keys were provided.");
    return;
  }
  const signature = settingsPatchSignature(changes);
  const previewMatches = Boolean(lastSettingsPatchPreviewEvidence && lastSettingsPatchPreviewEvidence.signature === signature);
  const previewOk = previewMatches && lastSettingsPatchPreviewEvidence.result?.ok === true;
  const previewWarning = previewOk
    ? "A matching backend Preview Patch result is available for this staged JSON."
    : previewMatches
      ? "The matching backend Preview Patch result has warnings/errors. Review it before saving."
      : "No matching backend Preview Patch result is available for this exact staged JSON.";
  if (!window.confirm(`Save ${keys.length} setting patch key(s) to the active PSD1 config?\n\n${previewWarning}\n\nA backup will be created first.`)) {
    selectedSettingsBackendResultKey = "save-confirmation-boundary";
    setText("settings-patch-status", "Save cancelled");
    setText("settings-patch-detail", [
      "Save Patch was cancelled before any backend save command was sent.",
      previewWarning,
      "No config backup was created, no PSD1 file was written, and the staged Changes JSON remains unsaved.",
      "Launch still uses saved backend settings only; run Save Patch again when ready.",
    ].join("\n"));
    renderSettingsPatchSummary();
    if (typeof renderAllLaunchPreflights === "function") renderAllLaunchPreflights();
    return;
  }
  setSettingsCommandBusy(true);
  setText("settings-patch-status", "Saving...");
  setText("settings-patch-detail", `Saving backend-validated patch to the active PSD1. A backup will be created first.\n${previewWarning}`);
  try {
    const result = await apiPost("/api/settings/save-patch", { changes, confirm_save: true });
    appendCommandResult(result);
    lastSettingsPatchSaveEvidence = {
      signature,
      command: "settings.save_patch",
      result,
      captured_at: new Date().toISOString(),
    };
    setText("settings-patch-status", result.ok ? "Saved" : result.severity || "Save failed");
    const data = result.data || {};
    const lines = [
      result.message || "Settings patch save completed.",
      "",
      `Writes config: ${data.writes_config === true ? "yes" : "no"}`,
      `Config: ${data.config_path || ""}`,
      `Backup: ${data.backup_path || ""}`,
      `Reloaded: ${data.reloaded === true ? "yes" : data.reloaded === false ? "no" : "n/a"}`,
      `Changed keys: ${(data.changed_keys || []).join(", ") || "none"}`,
      `Removed keys: ${(data.removed_keys || []).join(", ") || "none"}`,
    ];
    if ((result.errors || []).length) {
      lines.push("", "Errors:", ...(result.errors || []).map((item) => `- ${item}`));
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
    if (result.ok) await refreshAll();
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

  function initSettingsViewEvents() {
    const settingsValidateButton = byId("settings-validate-button");
    if (settingsValidateButton) settingsValidateButton.addEventListener("click", validateCurrentSettings);
    const settingsReloadButton = byId("settings-reload-button");
    if (settingsReloadButton) settingsReloadButton.addEventListener("click", reloadSettingsFromDisk);
    const settingsPreviewPatchButton = byId("settings-preview-patch-button");
    if (settingsPreviewPatchButton) settingsPreviewPatchButton.addEventListener("click", previewSettingsPatch);
    const settingsSavePatchButton = byId("settings-save-patch-button");
    if (settingsSavePatchButton) settingsSavePatchButton.addEventListener("click", saveSettingsPatch);
    const settingsSummarizePatchButton = byId("settings-summarize-patch-button");
    if (settingsSummarizePatchButton) settingsSummarizePatchButton.addEventListener("click", renderSettingsPatchSummary);
    const settingsPatchJson = byId("settings-patch-json");
    if (settingsPatchJson) settingsPatchJson.addEventListener("input", () => {
      markSettingsPatchTouched();
      renderSettingsPatchSummary();
      if (typeof renderAllLaunchPreflights === "function") renderAllLaunchPreflights();
    });
    const settingsPatchSummaryChangedOnly = byId("settings-patch-summary-changed-only");
    if (settingsPatchSummaryChangedOnly) settingsPatchSummaryChangedOnly.addEventListener("change", renderSettingsPatchSummary);
    const settingsBuilderApplyButton = byId("settings-builder-apply-button");
    if (settingsBuilderApplyButton) settingsBuilderApplyButton.addEventListener("click", applySettingsBuilderToPatch);
    const settingsBuilderResetButton = byId("settings-builder-reset-button");
    if (settingsBuilderResetButton) settingsBuilderResetButton.addEventListener("click", syncSettingsBuilderFromConfig);
    settingsBuilderFields.forEach(([, id]) => {
      const control = byId(id);
      if (control) control.addEventListener("input", markSettingsBuilderDirty);
      if (control) control.addEventListener("change", markSettingsBuilderDirty);
    });
    const videoDetailBuilderApplyButton = byId("settings-video-apply-button");
    if (videoDetailBuilderApplyButton) videoDetailBuilderApplyButton.addEventListener("click", applyVideoDetailSettingsBuilderToPatch);
    const videoDetailBuilderResetButton = byId("settings-video-reset-button");
    if (videoDetailBuilderResetButton) videoDetailBuilderResetButton.addEventListener("click", syncVideoDetailSettingsBuilderFromConfig);
    videoDetailSettingsBuilderFields.forEach(([, id]) => {
      const control = byId(id);
      if (control) control.addEventListener("input", markVideoDetailSettingsBuilderDirty);
      if (control) control.addEventListener("change", markVideoDetailSettingsBuilderDirty);
    });
    const fileSafetyBuilderApplyButton = byId("settings-file-safety-apply-button");
    if (fileSafetyBuilderApplyButton) fileSafetyBuilderApplyButton.addEventListener("click", applyFileSafetySettingsBuilderToPatch);
    const fileSafetyBuilderResetButton = byId("settings-file-safety-reset-button");
    if (fileSafetyBuilderResetButton) fileSafetyBuilderResetButton.addEventListener("click", syncFileSafetySettingsBuilderFromConfig);
    fileSafetySettingsBuilderFields.forEach(([, id]) => {
      const control = byId(id);
      if (control) control.addEventListener("input", markFileSafetySettingsBuilderDirty);
      if (control) control.addEventListener("change", markFileSafetySettingsBuilderDirty);
    });
    const networkBuilderApplyButton = byId("settings-network-apply-button");
    if (networkBuilderApplyButton) networkBuilderApplyButton.addEventListener("click", applyNetworkSettingsBuilderToPatch);
    const networkBuilderResetButton = byId("settings-network-reset-button");
    if (networkBuilderResetButton) networkBuilderResetButton.addEventListener("click", syncNetworkSettingsBuilderFromConfig);
    networkSettingsBuilderFields.forEach(([, id]) => {
      const control = byId(id);
      if (control) control.addEventListener("input", markNetworkSettingsBuilderDirty);
      if (control) control.addEventListener("change", markNetworkSettingsBuilderDirty);
    });
    const queueBuilderApplyButton = byId("settings-queue-apply-button");
    if (queueBuilderApplyButton) queueBuilderApplyButton.addEventListener("click", applyQueueSettingsBuilderToPatch);
    const queueBuilderResetButton = byId("settings-queue-reset-button");
    if (queueBuilderResetButton) queueBuilderResetButton.addEventListener("click", syncQueueSettingsBuilderFromConfig);
    queueSettingsBuilderFields.forEach(([, id]) => {
      const control = byId(id);
      if (control) control.addEventListener("input", markQueueSettingsBuilderDirty);
      if (control) control.addEventListener("change", markQueueSettingsBuilderDirty);
    });
    const runtimeBuilderApplyButton = byId("settings-runtime-apply-button");
    if (runtimeBuilderApplyButton) runtimeBuilderApplyButton.addEventListener("click", applyRuntimeSettingsBuilderToPatch);
    const runtimeBuilderResetButton = byId("settings-runtime-reset-button");
    if (runtimeBuilderResetButton) runtimeBuilderResetButton.addEventListener("click", syncRuntimeSettingsBuilderFromConfig);
    runtimeSettingsBuilderFields.forEach(([, id]) => {
      const control = byId(id);
      if (control) control.addEventListener("input", markRuntimeSettingsBuilderDirty);
      if (control) control.addEventListener("change", markRuntimeSettingsBuilderDirty);
    });
    const pendingPublishBuilderApplyButton = byId("settings-pending-apply-button");
    if (pendingPublishBuilderApplyButton) pendingPublishBuilderApplyButton.addEventListener("click", applyPendingPublishSettingsBuilderToPatch);
    const pendingPublishBuilderResetButton = byId("settings-pending-reset-button");
    if (pendingPublishBuilderResetButton) pendingPublishBuilderResetButton.addEventListener("click", syncPendingPublishSettingsBuilderFromConfig);
    pendingPublishSettingsBuilderFields.forEach(([, id]) => {
      const control = byId(id);
      if (control) control.addEventListener("input", markPendingPublishSettingsBuilderDirty);
      if (control) control.addEventListener("change", markPendingPublishSettingsBuilderDirty);
    });
    const subtitleBuilderApplyButton = byId("settings-subtitle-apply-button");
    if (subtitleBuilderApplyButton) subtitleBuilderApplyButton.addEventListener("click", applySubtitleSettingsBuilderToPatch);
    const subtitleBuilderResetButton = byId("settings-subtitle-reset-button");
    if (subtitleBuilderResetButton) subtitleBuilderResetButton.addEventListener("click", syncSubtitleSettingsBuilderFromConfig);
    subtitleSettingsBuilderFields.forEach(([, id]) => {
      const control = byId(id);
      if (control) control.addEventListener("input", markSubtitleSettingsBuilderDirty);
      if (control) control.addEventListener("change", markSubtitleSettingsBuilderDirty);
    });
    const audioBuilderApplyButton = byId("settings-audio-apply-button");
    if (audioBuilderApplyButton) audioBuilderApplyButton.addEventListener("click", applyAudioSettingsBuilderToPatch);
    const audioBuilderResetButton = byId("settings-audio-reset-button");
    if (audioBuilderResetButton) audioBuilderResetButton.addEventListener("click", syncAudioSettingsBuilderFromConfig);
    audioSettingsBuilderFields.forEach(([, id]) => {
      const control = byId(id);
      if (control) control.addEventListener("input", markAudioSettingsBuilderDirty);
      if (control) control.addEventListener("change", markAudioSettingsBuilderDirty);
    });
    const settingsFilter = byId("settings-filter");
    if (settingsFilter) settingsFilter.addEventListener("input", renderSettingsRows);
  }

  /**
   * Public namespace for the Settings page module.
   * Prefer this namespace from new code; flat window.* exports are transitional compatibility aliases when present.
   */
  window.mediaPipelineSettingsView = {
    configValue,
    buildSettingsOverviewRows,
    renderSettingsOverview,
    setSettingsRows,
    renderSettingsRows,
    settingsBuilderCoveredKeys,
    settingsRawTriageRows,
    settingsRawTriageStatus,
    settingsRawTriageSummaryLines,
    settingsRawTriageDetailLines,
    renderSettingsRawTriage,
    settingsRawActionPlanRows,
    settingsRawActionPlanStatus,
    settingsRawActionPlanSummaryLines,
    settingsRawActionPlanDetailLines,
    renderSettingsRawActionPlan,
    settingsSafetyLockRows,
    settingsSafetyLockStatus,
    settingsSafetyLockSummaryLines,
    renderSettingsSafetyLocks,
    renderSettings,
    getLastSettings,
    validateCurrentSettings,
    reloadSettingsFromDisk,
    setSettingsCommandBusy,
    rejectSettingsCommandWhileBusy,
    previewSettingsPatch,
    saveSettingsPatch,
    isSettingsCommand,
    settingsCommandHistoryLine,
    renderSettingsCommandHistory,
    renderSettingsPatchSummary,
    settingsPatchImpactEntries,
    renderSettingsPatchImpactSummaryFromEntries,
    settingsPatchSaveReadinessIssues,
    settingsPatchSaveReadinessStatus,
    renderSettingsPatchSaveReadinessFromEntries,
    settingsPolicyDeltaRows,
    settingsPolicyDeltaStatus,
    settingsPolicyDeltaSummaryLines,
    renderSettingsPolicyDeltaFromEntries,
    settingsEffectivePolicyRows,
    settingsEffectivePolicyTrustStatus,
    settingsEffectivePolicySummaryLines,
    settingsEffectivePolicyDetailLines,
    renderSettingsEffectivePolicyTrustFromEntries,
    renderSettingsEffectivePolicyTrustForError,
    settingsSaveReviewRows,
    settingsSaveReviewStatus,
    settingsSaveReviewDetailLines,
    renderSettingsSaveReviewFromEntries,
    settingsLaunchImpactRows,
    settingsLaunchImpactStatus,
    settingsLaunchImpactSummaryLines,
    renderSettingsLaunchImpactHandoffFromEntries,
    markSettingsPatchTouched,
    settingsPatchIsTouched,
    settingsPatchEffectiveChangedEntries,
    settingsPatchHasUnsavedChanges,
    settingsStableJsonValue,
    settingsPatchSignature,
    settingsCurrentPatchSignature,
    syncSettingsBuilderFromConfig,
    collectSettingsBuilderPatch,
    applySettingsBuilderToPatch,
    refreshSettingsBuilderChoices,
    renderSettingsBuilderGuidance,
    markSettingsBuilderDirty,
    syncVideoDetailSettingsBuilderFromConfig,
    collectVideoDetailSettingsBuilderPatch,
    applyVideoDetailSettingsBuilderToPatch,
    renderVideoDetailSettingsBuilderGuidance,
    markVideoDetailSettingsBuilderDirty,
    syncFileSafetySettingsBuilderFromConfig,
    collectFileSafetySettingsBuilderPatch,
    applyFileSafetySettingsBuilderToPatch,
    renderFileSafetySettingsBuilderGuidance,
    markFileSafetySettingsBuilderDirty,
    syncNetworkSettingsBuilderFromConfig,
    collectNetworkSettingsBuilderPatch,
    applyNetworkSettingsBuilderToPatch,
    renderNetworkSettingsBuilderGuidance,
    markNetworkSettingsBuilderDirty,
    syncQueueSettingsBuilderFromConfig,
    collectQueueSettingsBuilderPatch,
    applyQueueSettingsBuilderToPatch,
    renderQueueSettingsBuilderGuidance,
    markQueueSettingsBuilderDirty,
    syncRuntimeSettingsBuilderFromConfig,
    collectRuntimeSettingsBuilderPatch,
    applyRuntimeSettingsBuilderToPatch,
    renderRuntimeSettingsBuilderGuidance,
    markRuntimeSettingsBuilderDirty,
    syncPendingPublishSettingsBuilderFromConfig,
    collectPendingPublishSettingsBuilderPatch,
    applyPendingPublishSettingsBuilderToPatch,
    renderPendingPublishSettingsBuilderGuidance,
    markPendingPublishSettingsBuilderDirty,
    syncSubtitleSettingsBuilderFromConfig,
    collectSubtitleSettingsBuilderPatch,
    applySubtitleSettingsBuilderToPatch,
    renderSubtitleSettingsBuilderGuidance,
    settingsBdpgsOcrPathEvidence,
    settingsBdpgsOcrPathEvidenceStatus,
    settingsBdpgsOcrPathEvidenceLines,
    renderSettingsBdpgsOcrPathEvidence,
    syncAudioSettingsBuilderFromConfig,
    collectAudioSettingsBuilderPatch,
    applyAudioSettingsBuilderToPatch,
    renderAudioSettingsBuilderGuidance,
    settingsMediaPolicyRows,
    settingsMediaPolicyStatus,
    settingsMediaPolicySummaryLines,
    renderSettingsMediaPolicyCrossCheck,
    settingsBackendMediaPolicyReadiness,
    settingsBackendMediaPolicyStatus,
    settingsBackendMediaPolicySummaryLines,
    renderSettingsBackendMediaPolicyReadiness,
    settingsActiveMediaPolicyRows,
    settingsActiveMediaPolicyStatus,
    settingsActiveMediaPolicySummaryLines,
    renderSettingsActiveMediaPolicyHandoff,
    settingsBackendResultRows,
    settingsBackendResultRowKey,
    settingsCommandProgressBars,
    renderSettingsSaveProgress,
    settingsProgressDetailLines,
    settingsBackendResultDetailLines,
    settingsBackendResultStatus,
    settingsBackendResultSummaryLines,
    renderSettingsBackendResultFromEntries,
    renderSettingsBackendResultForError,
    writeSettingsPatchJson,
    parseSettingsPatchJson,
    initSettingsViewEvents,
  };
  window.configValue = configValue;
  window.buildSettingsOverviewRows = buildSettingsOverviewRows;
  window.renderSettingsOverview = renderSettingsOverview;
  window.setSettingsRows = setSettingsRows;
  window.renderSettingsRows = renderSettingsRows;
  window.settingsBuilderCoveredKeys = settingsBuilderCoveredKeys;
  window.settingsRawTriageRows = settingsRawTriageRows;
  window.settingsRawTriageStatus = settingsRawTriageStatus;
  window.settingsRawTriageSummaryLines = settingsRawTriageSummaryLines;
  window.settingsRawTriageDetailLines = settingsRawTriageDetailLines;
  window.renderSettingsRawTriage = renderSettingsRawTriage;
  window.settingsRawActionPlanRows = settingsRawActionPlanRows;
  window.settingsRawActionPlanStatus = settingsRawActionPlanStatus;
  window.settingsRawActionPlanSummaryLines = settingsRawActionPlanSummaryLines;
  window.settingsRawActionPlanDetailLines = settingsRawActionPlanDetailLines;
  window.renderSettingsRawActionPlan = renderSettingsRawActionPlan;
  window.settingsSafetyLockRows = settingsSafetyLockRows;
  window.settingsSafetyLockStatus = settingsSafetyLockStatus;
  window.settingsSafetyLockSummaryLines = settingsSafetyLockSummaryLines;
  window.renderSettingsSafetyLocks = renderSettingsSafetyLocks;
  window.renderSettings = renderSettings;
  window.getLastSettings = getLastSettings;
  window.isSettingsCommand = isSettingsCommand;
  window.settingsCommandHistoryLine = settingsCommandHistoryLine;
  window.renderSettingsCommandHistory = renderSettingsCommandHistory;
  window.settingsPolicyDeltaRows = settingsPolicyDeltaRows;
  window.settingsPolicyDeltaStatus = settingsPolicyDeltaStatus;
  window.settingsLaunchImpactRows = settingsLaunchImpactRows;
  window.settingsLaunchImpactStatus = settingsLaunchImpactStatus;
  window.settingsPatchIsTouched = settingsPatchIsTouched;
  window.settingsPatchEffectiveChangedEntries = settingsPatchEffectiveChangedEntries;
  window.syncVideoDetailSettingsBuilderFromConfig = syncVideoDetailSettingsBuilderFromConfig;
  window.collectVideoDetailSettingsBuilderPatch = collectVideoDetailSettingsBuilderPatch;
  window.applyVideoDetailSettingsBuilderToPatch = applyVideoDetailSettingsBuilderToPatch;
  window.renderVideoDetailSettingsBuilderGuidance = renderVideoDetailSettingsBuilderGuidance;
  window.markVideoDetailSettingsBuilderDirty = markVideoDetailSettingsBuilderDirty;
  window.syncFileSafetySettingsBuilderFromConfig = syncFileSafetySettingsBuilderFromConfig;
  window.collectFileSafetySettingsBuilderPatch = collectFileSafetySettingsBuilderPatch;
  window.applyFileSafetySettingsBuilderToPatch = applyFileSafetySettingsBuilderToPatch;
  window.renderFileSafetySettingsBuilderGuidance = renderFileSafetySettingsBuilderGuidance;
  window.markFileSafetySettingsBuilderDirty = markFileSafetySettingsBuilderDirty;
  window.syncNetworkSettingsBuilderFromConfig = syncNetworkSettingsBuilderFromConfig;
  window.collectNetworkSettingsBuilderPatch = collectNetworkSettingsBuilderPatch;
  window.applyNetworkSettingsBuilderToPatch = applyNetworkSettingsBuilderToPatch;
  window.renderNetworkSettingsBuilderGuidance = renderNetworkSettingsBuilderGuidance;
  window.markNetworkSettingsBuilderDirty = markNetworkSettingsBuilderDirty;
  window.syncQueueSettingsBuilderFromConfig = syncQueueSettingsBuilderFromConfig;
  window.collectQueueSettingsBuilderPatch = collectQueueSettingsBuilderPatch;
  window.applyQueueSettingsBuilderToPatch = applyQueueSettingsBuilderToPatch;
  window.renderQueueSettingsBuilderGuidance = renderQueueSettingsBuilderGuidance;
  window.markQueueSettingsBuilderDirty = markQueueSettingsBuilderDirty;
  window.syncRuntimeSettingsBuilderFromConfig = syncRuntimeSettingsBuilderFromConfig;
  window.collectRuntimeSettingsBuilderPatch = collectRuntimeSettingsBuilderPatch;
  window.applyRuntimeSettingsBuilderToPatch = applyRuntimeSettingsBuilderToPatch;
  window.renderRuntimeSettingsBuilderGuidance = renderRuntimeSettingsBuilderGuidance;
  window.markRuntimeSettingsBuilderDirty = markRuntimeSettingsBuilderDirty;
  window.syncPendingPublishSettingsBuilderFromConfig = syncPendingPublishSettingsBuilderFromConfig;
  window.collectPendingPublishSettingsBuilderPatch = collectPendingPublishSettingsBuilderPatch;
  window.applyPendingPublishSettingsBuilderToPatch = applyPendingPublishSettingsBuilderToPatch;
  window.renderPendingPublishSettingsBuilderGuidance = renderPendingPublishSettingsBuilderGuidance;
  window.markPendingPublishSettingsBuilderDirty = markPendingPublishSettingsBuilderDirty;
  window.syncSubtitleSettingsBuilderFromConfig = syncSubtitleSettingsBuilderFromConfig;
  window.collectSubtitleSettingsBuilderPatch = collectSubtitleSettingsBuilderPatch;
  window.applySubtitleSettingsBuilderToPatch = applySubtitleSettingsBuilderToPatch;
  window.renderSubtitleSettingsBuilderGuidance = renderSubtitleSettingsBuilderGuidance;
  window.settingsBdpgsOcrPathEvidence = settingsBdpgsOcrPathEvidence;
  window.settingsBdpgsOcrPathEvidenceStatus = settingsBdpgsOcrPathEvidenceStatus;
  window.settingsBdpgsOcrPathEvidenceLines = settingsBdpgsOcrPathEvidenceLines;
  window.renderSettingsBdpgsOcrPathEvidence = renderSettingsBdpgsOcrPathEvidence;
  window.markSubtitleSettingsBuilderDirty = markSubtitleSettingsBuilderDirty;
  window.syncAudioSettingsBuilderFromConfig = syncAudioSettingsBuilderFromConfig;
  window.collectAudioSettingsBuilderPatch = collectAudioSettingsBuilderPatch;
  window.applyAudioSettingsBuilderToPatch = applyAudioSettingsBuilderToPatch;
  window.renderAudioSettingsBuilderGuidance = renderAudioSettingsBuilderGuidance;
  window.markAudioSettingsBuilderDirty = markAudioSettingsBuilderDirty;
  window.renderSettingsMediaPolicyCrossCheck = renderSettingsMediaPolicyCrossCheck;
  window.writeSettingsPatchJson = writeSettingsPatchJson;
  window.initSettingsViewEvents = initSettingsViewEvents;
})();
