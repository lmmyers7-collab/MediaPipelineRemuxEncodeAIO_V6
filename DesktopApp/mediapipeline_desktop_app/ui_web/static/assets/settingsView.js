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
let settingsPipelinePlanPreviewRequestId = 0;

const settingsCommandButtonIds = [
  "settings-validate-button",
  "settings-reload-button",
  "settings-preview-plan-button",
  "settings-preview-patch-button",
  "settings-save-patch-button",
  "settings-final-library-preview-button",
  "settings-final-library-save-button",
  "settings-file-safety-source-movies-browse",
  "settings-file-safety-source-tv-browse",
  "settings-file-safety-outsource-browse",
  "settings-file-safety-local-base-browse",
  "network-settings-preview-button",
  "network-settings-save-button",
  "settings-save-header-preview-button",
  "settings-save-header-save-button",
  "settings-save-header-reload-button",
];
let settingsCommandInFlight = false;

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
      ? "Save Patch reports Reloaded: yes; the backend and future launches have the saved config."
      : data.reloaded === false
        ? "Save Patch wrote config, but backend reload did not complete. Use Reload From Disk or restart Tauri after resolving the reload issue."
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
const finalLibraryPromotionSettingsBuilderFields = settingsMetadata.finalLibraryPromotionSettingsBuilderFields || [];
const subtitleSettingsBuilderFields = settingsMetadata.subtitleSettingsBuilderFields || [];
const audioSettingsBuilderFields = settingsMetadata.audioSettingsBuilderFields || [];
const settingsSafetyLockDefinitions = settingsMetadata.settingsSafetyLockDefinitions || [];
const settingsImpactGroups = settingsMetadata.settingsImpactGroups || [];
const settingsSpecificImpactHints = settingsMetadata.settingsSpecificImpactHints || {};
const settingsChoiceLabels = settingsMetadata.settingsChoiceLabels || {};
const settingsDisplayLabels = settingsMetadata.settingsDisplayLabels || {};

function settingsFieldDefaultValue(key, fallback) {
  const field = settingsFieldDefinition(key);
  if (field && Object.prototype.hasOwnProperty.call(field, "default_value") && field.default_value !== null && field.default_value !== undefined) {
    return field.default_value;
  }
  if (field && Object.prototype.hasOwnProperty.call(field, "default") && field.default !== null && field.default !== undefined) {
    return field.default;
  }
  return fallback;
}

function settingsBuilderConfigValue(key, fallback) {
  const value = lastSettingsValues ? lastSettingsValues[key] : undefined;
  if (value === undefined || value === null || value === "") return settingsFieldDefaultValue(key, fallback);
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

function settingsFieldAllowedValues(field) {
  if (Array.isArray(field?.allowed_values) && field.allowed_values.length) return field.allowed_values;
  if (Array.isArray(field?.choices) && field.choices.length) return field.choices;
  return [];
}

function settingsFieldLabel(key, fallback = "") {
  const field = settingsFieldDefinition(key);
  return field?.label || settingsDisplayLabels[key] || fallback || key;
}

function settingsFieldHelpText(field) {
  return String(field?.help_text || field?.help || "").trim();
}

function settingsMetadataTags(value) {
  if (Array.isArray(value)) return value.map((item) => String(item || "").trim()).filter(Boolean);
  const text = String(value || "").trim();
  return text ? [text] : [];
}

function settingsMetadataBadgeText(value) {
  return String(value || "").replace(/_/g, " ").toUpperCase();
}

function settingsDirectLabelChild(label, descendant) {
  let node = descendant;
  while (node && node.parentElement && node.parentElement !== label) {
    node = node.parentElement;
  }
  return node?.parentElement === label ? node : null;
}

function renderSettingsFieldTaxonomyBadges(label, control, field) {
  if (!label || !control || !field) return;
  label.querySelectorAll(".settings-field-metadata-badges").forEach((node) => node.remove());
  const taxonomy = settingsMetadataTags(field.rule_taxonomy).map((value) => ["taxonomy", value]);
  const strictness = settingsMetadataTags(field.strictness).map((value) => ["strictness", value]);
  const badges = [...taxonomy, ...strictness];
  if (!badges.length) return;
  const row = document.createElement("span");
  row.className = "settings-field-metadata-badges";
  row.dataset.settingsMetadataSource = "backend";
  badges.forEach(([kind, value]) => {
    const badge = document.createElement("span");
    badge.className = "rule-badge settings-field-metadata-badge";
    badge.dataset.metadataKind = kind;
    badge.dataset.ruleKind = value;
    badge.textContent = settingsMetadataBadgeText(value);
    row.appendChild(badge);
  });
  const anchor = settingsDirectLabelChild(label, control);
  if (anchor) {
    label.insertBefore(row, anchor);
  } else {
    label.appendChild(row);
  }
}

function settingsMetadataValue(value) {
  if (value === undefined || value === null) return "";
  if (Array.isArray(value)) return value.join(", ");
  if (typeof value === "object") {
    try {
      return JSON.stringify(value);
    } catch (_error) {
      return String(value);
    }
  }
  return String(value);
}

function updateSettingsLabelText(label, control, labelText) {
  if (!label || !control || !labelText) return;
  const childNodes = Array.from(label.childNodes || []);
  const controlIndex = childNodes.indexOf(control);
  const textNodes = childNodes.filter((node) => node.nodeType === Node.TEXT_NODE && String(node.nodeValue || "").trim());
  if (!textNodes.length) return;
  const target = label.classList.contains("check-row")
    ? textNodes.find((node) => childNodes.indexOf(node) > controlIndex) || textNodes[0]
    : textNodes.find((node) => childNodes.indexOf(node) < controlIndex) || textNodes[0];
  const original = String(target.nodeValue || "");
  const leading = original.match(/^\s*/)?.[0] || "";
  const trailing = original.match(/\s*$/)?.[0] || "";
  target.nodeValue = `${leading}${labelText}${trailing || " "}`;
}

function applySettingsFieldMetadataToControl([key, id, fallbackKind]) {
  const field = settingsFieldDefinition(key);
  const element = byId(id);
  if (!field || !element) return;
  const label = element.closest?.("label") || null;
  const labelText = settingsFieldLabel(key);
  const valueType = String(field.value_type || field.kind || fallbackKind || "");
  const advancedVisibility = String(field.advanced_visibility || "standard");
  const persistedKey = String(field.persisted_key || key);
  element.dataset.settingsKey = key;
  element.dataset.settingsPersistedKey = persistedKey;
  element.dataset.settingsValueType = valueType;
  element.dataset.settingsAdvancedVisibility = advancedVisibility;
  if (field.short_label) element.dataset.settingsShortLabel = String(field.short_label);
  if (field.section) element.dataset.settingsSection = String(field.section);
  if (field.strictness) element.dataset.settingsStrictness = String(field.strictness);
  if (field.rule_taxonomy) element.dataset.settingsRuleTaxonomy = settingsMetadataTags(field.rule_taxonomy).join(",");
  if (label) {
    label.dataset.settingsKey = key;
    label.dataset.settingsPersistedKey = persistedKey;
    label.dataset.settingsAdvancedVisibility = advancedVisibility;
    if (field.short_label) label.dataset.settingsShortLabel = String(field.short_label);
    if (field.section) label.dataset.settingsSection = String(field.section);
    if (field.strictness) label.dataset.settingsStrictness = String(field.strictness);
    if (field.rule_taxonomy) label.dataset.settingsRuleTaxonomy = settingsMetadataTags(field.rule_taxonomy).join(",");
    updateSettingsLabelText(label, element, labelText);
    renderSettingsFieldTaxonomyBadges(label, element, field);
  }
  const help = settingsFieldHelpText(field);
  if (help) {
    element.title = help;
    if (label) label.title = help;
  }
  const defaultValue = settingsFieldDefaultValue(key, undefined);
  if (defaultValue !== undefined) {
    element.dataset.settingsDefaultValue = settingsMetadataValue(defaultValue);
  }
  if (field.default_source) element.dataset.settingsDefaultSource = String(field.default_source);
  if (field.validation_owner) element.dataset.settingsValidationOwner = String(field.validation_owner);
  if (field.runtime_consumer) element.dataset.settingsRuntimeConsumer = String(field.runtime_consumer);
  if (element instanceof HTMLInputElement && element.type !== "checkbox") {
    if (["integer", "number"].includes(String(field.value_type || ""))) {
      element.type = "number";
    }
    if (field.min !== null && field.min !== undefined) element.min = String(field.min);
    if (field.max !== null && field.max !== undefined) element.max = String(field.max);
    if (field.step !== null && field.step !== undefined) element.step = String(field.step);
  }
}

function settingsBuilderFieldGroups() {
  return [
    settingsBuilderFields,
    videoDetailSettingsBuilderFields,
    subtitleSettingsBuilderFields,
    audioSettingsBuilderFields,
    fileSafetySettingsBuilderFields,
    runtimeSettingsBuilderFields,
    pendingPublishSettingsBuilderFields,
    queueSettingsBuilderFields,
    networkSettingsBuilderFields,
    finalLibraryPromotionSettingsBuilderFields,
  ];
}

function settingsAllBuilderFields() {
  const seen = new Set();
  return settingsBuilderFieldGroups()
    .flat()
    .filter((field) => {
      const key = String(field?.[0] || "");
      const id = String(field?.[1] || "");
      const identity = `${key}|${id}`;
      if (!key || !id || seen.has(identity)) return false;
      seen.add(identity);
      return true;
    });
}

function applySettingsFieldMetadataToControls() {
  settingsAllBuilderFields().forEach(applySettingsFieldMetadataToControl);
}

function refreshSettingsSelectChoices(fields) {
  fields.forEach(([key, id]) => {
    const element = byId(id);
    const field = settingsFieldDefinition(key);
    const choices = settingsFieldAllowedValues(field);
    if (!element || element.tagName !== "SELECT" || !choices.length) return;
    const current = element.value;
    element.replaceChildren();
    choices.forEach((choice) => {
      const option = document.createElement("option");
      option.value = String(choice);
      option.textContent = formatSettingsChoiceLabel(choice);
      if (field.choice_help && field.choice_help[String(choice)]) {
        option.title = field.choice_help[String(choice)];
      }
      element.appendChild(option);
    });
    const choiceValues = choices.map((choice) => String(choice));
    const fallback = settingsFieldDefaultValue(key, choices[0] || "");
    element.value = choiceValues.includes(current) ? current : String(fallback || choices[0] || "");
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
    settingsDisplayLabels,
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
  if (fn) fn();
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
function settingsPolicyDeltaStatus(rows) { return settingsPolicyImpactCall("settingsPolicyDeltaStatus", [rows], "No staged change"); }
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
      markQueueSettingsBuilderDirty,
      markRuntimeSettingsBuilderDirty,
      markSettingsBuilderDirty,
      markSettingsPatchTouched,
      markSubtitleSettingsBuilderDirty,
      markVideoDetailSettingsBuilderDirty,
      previewFinalLibraryPromotionSettings,
      previewSettingsPipelinePlan,
      previewSettingsPatch,
      renderAudioSettingsBuilderGuidance,
      renderFileSafetySettingsBuilderGuidance,
      renderNetworkSettingsBuilderGuidance,
      renderPendingPublishSettingsBuilderGuidance,
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
    settingsBuilderInputValue,
    settingsCommandHistoryLine,
    settingsFieldDefinition,
    settingsDisplayLabels,
    settingsPatchImpactEntries,
    settingsPatchCandidateValue,
    settingsPatchListValue,
    settingsRawConfigValue,
    settingsValuesEqual,
    networkSettingsBuilderFields,
    networkSettingsBuilderState,
    pendingPublishSettingsBuilderFields,
    pendingPublishSettingsBuilderState,
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
function settingsPatchSaveReadinessStatus(issues = []) { return settingsPatchReviewCall("settingsPatchSaveReadinessStatus", [issues], "No patch"); }
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
    settingsDisplayLabels,
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
 * Save Patch is the only persistence command.
 * Preview/Save remains backend-owned.
 * Frontend advisory only; backend Preview Patch and Save Patch remain authoritative for source-deletion acceptance and PSD1 writes.
 * Patch JSON changed after the last preview. Preview again before saving.
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
    headerPatchEl.textContent = patchStatusEl.textContent || "No patch";
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
  const fn = settingsPatchReviewFunction("renderSettings");
  if (fn) fn(lastSettings);
  applySettingsFieldMetadataToControls();
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

function planValue(item, keys, fallback = "") {
  if (!item || typeof item !== "object") return fallback;
  for (const key of keys) {
    if (Object.prototype.hasOwnProperty.call(item, key) && item[key] !== undefined && item[key] !== null && item[key] !== "") {
      return item[key];
    }
  }
  return fallback;
}

function compactPlanList(values, fallback = "none") {
  const lines = (Array.isArray(values) ? values : [])
    .map((value) => String(value || "").trim())
    .filter(Boolean);
  return lines.length ? lines.join(", ") : fallback;
}

function formatSettingsBytes(value) {
  const bytes = Number(value);
  if (!Number.isFinite(bytes) || bytes <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let scaled = bytes;
  let unitIndex = 0;
  while (scaled >= 1024 && unitIndex < units.length - 1) {
    scaled /= 1024;
    unitIndex += 1;
  }
  const digits = unitIndex === 0 ? 0 : 1;
  return `${scaled.toFixed(digits)} ${units[unitIndex]}`;
}

function parseSettingsSourceMediaJson() {
  const raw = byId("settings-source-media-json")?.value || "";
  if (!raw.trim()) {
    throw new Error("SourceMediaInfo source facts JSON is required.");
  }
  const parsed = JSON.parse(raw);
  if (!parsed || Array.isArray(parsed) || typeof parsed !== "object") {
    throw new Error("SourceMediaInfo JSON must be an object.");
  }
  return parsed;
}

function settingsSourceFactSummary(sourceMedia) {
  const container = planValue(sourceMedia, ["container"], {});
  const videos = Array.isArray(sourceMedia?.video_streams) ? sourceMedia.video_streams : [];
  const audio = Array.isArray(sourceMedia?.audio_streams) ? sourceMedia.audio_streams : [];
  const subtitles = Array.isArray(sourceMedia?.subtitle_streams) ? sourceMedia.subtitle_streams : [];
  const video = videos[0] || {};
  const containerText = [
    planValue(container, ["format_name"], "unknown container"),
    planValue(container, ["media_type"], "unknown"),
    formatSettingsBytes(Number(planValue(container, ["file_size_bytes"], 0)) || 0),
  ].filter(Boolean).join("; ");
  const videoText = video && Object.keys(video).length
    ? [
      planValue(video, ["codec"], "unknown codec"),
      `${planValue(video, ["width"], 0)}x${planValue(video, ["height"], 0)}`,
      `${Math.round((Number(planValue(video, ["bitrate_bps"], 0)) || 0) / 1000000)} Mbps`,
    ].join("; ")
    : "No video stream facts loaded";
  return {
    container: containerText,
    video: videoText,
    audio: `${audio.length} track${audio.length === 1 ? "" : "s"}`,
    subtitles: `${subtitles.length} track${subtitles.length === 1 ? "" : "s"}`,
  };
}

function renderSettingsSourceFactsRows(sourceMedia, routeSummary) {
  const tbody = byId("settings-source-facts-rows");
  if (!tbody) return;
  const summary = settingsSourceFactSummary(sourceMedia || {});
  const rows = [
    ["Container", summary.container || "No SourceMediaInfo payload loaded.", "Read-only source fact"],
    ["Video codec / profile / level", summary.video, "Backend validated before preview"],
    ["Dimensions / aspect / bitrate", summary.video, "Backend validated before preview"],
    ["Audio tracks", summary.audio, "Backend stream actions only"],
    ["Subtitle tracks", summary.subtitles, "Backend stream actions only"],
    ["Compatibility verdict", routeSummary || "UNKNOWN", "Rendered from backend PipelinePlan"],
  ];
  tbody.replaceChildren();
  rows.forEach((rowValues) => {
    const row = document.createElement("tr");
    appendCells(row, rowValues);
    tbody.appendChild(row);
  });
}

function settingsPipelinePlanPatchRequest() {
  const raw = byId("settings-patch-json")?.value || "{}";
  const changes = JSON.parse(raw);
  if (!changes || Array.isArray(changes) || typeof changes !== "object") {
    throw new Error("Patch JSON must be an object of config keys and values.");
  }
  return { changes, removeKeys: [] };
}

function settingsPipelinePlanActionLines(plan) {
  const actions = Array.isArray(plan?.streamActions) ? plan.streamActions : [];
  if (!actions.length) return ["- none returned"];
  return actions.map((action) => {
    const type = planValue(action, ["streamType"], "stream");
    const index = planValue(action, ["streamIndex"], null);
    const indexText = index === null || index === undefined ? "" : ` ${index}`;
    const input = planValue(action, ["inputCodec"], "unknown");
    const output = planValue(action, ["outputCodec"], "unchanged");
    const reasons = compactPlanList(planValue(action, ["reasonCodes"], []), "no reason code");
    return `- ${type}${indexText}: ${planValue(action, ["action"], "unknown")} (${input} -> ${output}; ${reasons})`;
  });
}

function settingsPipelinePlanReasonLines(plan) {
  const reasons = Array.isArray(plan?.reasonSummary) ? plan.reasonSummary : [];
  if (!reasons.length) return ["- none returned"];
  return reasons.map((reason) => `- ${planValue(reason, ["code"], "reason")}: ${planValue(reason, ["text"], "")}`);
}

function settingsPipelinePlanCommandLines(plan) {
  const commandPlans = Array.isArray(plan?.commandPlans) ? plan.commandPlans : [];
  if (!commandPlans.length) return ["- no abstract command plan returned"];
  const lines = [];
  commandPlans.forEach((commandPlan) => {
    const previewLines = Array.isArray(commandPlan.previewLines) ? commandPlan.previewLines : [];
    previewLines.forEach((line) => lines.push(`- ${line}`));
    const steps = Array.isArray(commandPlan.steps) ? commandPlan.steps : [];
    steps.forEach((step) => lines.push(`- ${planValue(step, ["label"], "Step")}: ${planValue(step, ["dryRunText"], "")}`));
  });
  return lines.length ? lines : ["- no command preview lines returned"];
}

function settingsPipelinePlanVerificationLines(plan) {
  const result = plan?.verificationResult && typeof plan.verificationResult === "object" ? plan.verificationResult : {};
  const check = result.outputSizeCheck && typeof result.outputSizeCheck === "object" ? result.outputSizeCheck : {};
  const guards = Array.isArray(plan?.verificationGuards) ? plan.verificationGuards : [];
  const publishRequirements = Array.isArray(plan?.publishRequirements) ? plan.publishRequirements : [];
  const lines = [
    `- status: ${planValue(result, ["status"], "planned")}`,
    `- Output Size Check: ${planValue(check, ["action"], "not returned")} / ${planValue(check, ["status"], "not returned")}`,
    `- target output size: ${planValue(check, ["targetOutputSizeBytes"], "not available")}`,
    `- growth tolerance: ${planValue(check, ["growthTolerancePercent"], "not returned")}%; actual output size: ${planValue(check, ["actualOutputSizeBytes"], "pending post-process")}`,
  ];
  const guardLines = guards.map((guard) => `- guard ${planValue(guard, ["code"], "guard")}: ${planValue(guard, ["stage"], "stage")} ${planValue(guard, ["enforcement"], "enforcement")} -> ${planValue(guard, ["onFail"], "on fail not returned")}`);
  const publishLines = publishRequirements.map((item) => `- publish ${planValue(item, ["code"], "requirement")}: ${planValue(item, ["text"], "")}`);
  return [
    ...lines,
    ...(guardLines.length ? guardLines : ["- no verification guards returned"]),
    ...(publishLines.length ? publishLines : ["- no publish requirements returned"]),
  ];
}

function renderSettingsPipelinePlanPreview(result, sourceMedia) {
  const plan = result?.data && typeof result.data === "object" ? result.data : {};
  const routeSummary = String(plan.routeSummary || "UNKNOWN").toUpperCase();
  const meta = plan.effectivePresetSnapshot?.settingsPreview || {};
  const output = plan.output && typeof plan.output === "object" ? plan.output : {};
  const verification = plan.verificationResult && typeof plan.verificationResult === "object" ? plan.verificationResult : {};
  const outputSizeCheck = verification.outputSizeCheck && typeof verification.outputSizeCheck === "object" ? verification.outputSizeCheck : {};
  const warnings = Array.from(new Set([
    ...(Array.isArray(plan.warnings) ? plan.warnings : []),
    ...(Array.isArray(result?.warnings) ? result.warnings : []),
  ]));
  const summary = settingsSourceFactSummary(sourceMedia || {});
  setText("settings-handbrake-preview-status", "Predicted pending cutover");
  setText("settings-handbrake-decision", routeSummary);
  setText("settings-handbrake-active-preset", "Saved settings plus staged patch");
  setText("settings-handbrake-source-container", summary.container || "No source selected");
  setText("settings-handbrake-source-video", summary.video);
  setText("settings-handbrake-source-audio", summary.audio);
  setText("settings-handbrake-source-subtitles", summary.subtitles);
  setText("settings-handbrake-output-container", planValue(output, ["container"], "Not returned"));
  setText("settings-handbrake-publish-requirements", planValue(plan, ["publishStrategy"], "Not returned"));
  setText(
    "settings-handbrake-output-guards",
    `Output Size Check: ${planValue(outputSizeCheck, ["action"], "not returned")} / ${planValue(outputSizeCheck, ["status"], "not returned")}`
  );
  renderSettingsSourceFactsRows(sourceMedia, routeSummary);
  const lines = [
    result?.message || "Settings PipelinePlan preview returned.",
    "",
    `Schema: ${plan.schemaVersion || "unknown"}`,
    `Route: ${routeSummary}`,
    `Output proposal: ${planValue(output, ["path"], "not returned")}`,
    `Dry run only: ${meta.dryRunOnly === false ? "no" : "yes"}`,
    `Can execute: ${meta.canExecute === true ? "yes" : "no"}`,
    `Authority: ${meta.authority || "python_preview_legacy_execution_still_authoritative"}`,
    "",
    "Stream actions:",
    ...settingsPipelinePlanActionLines(plan),
    "",
    "Reasons:",
    ...settingsPipelinePlanReasonLines(plan),
    "",
    "Warnings:",
    ...(warnings.length ? warnings.map((warning) => `- ${warning}`) : ["- none returned"]),
    "",
    "Verification / publish:",
    ...settingsPipelinePlanVerificationLines(plan),
    "",
    "Command preview:",
    ...settingsPipelinePlanCommandLines(plan),
    "",
    "Preview label remains Predicted pending cutover because legacy execution is still authoritative.",
  ];
  setText("settings-source-media-json-status", result?.ok ? "Preview ready" : "Preview returned issues");
  setText("settings-source-media-json-detail", `Backend route: ${routeSummary}. This dry-run preview did not save settings, launch work, or touch media files.`);
  setText("settings-handbrake-preview-detail", lines.join("\n"));
}

function renderSettingsPipelinePlanPreviewError(message) {
  setText("settings-source-media-json-status", "Preview failed");
  setText("settings-source-media-json-detail", message);
  setText("settings-handbrake-preview-status", "Predicted pending cutover");
  setText("settings-handbrake-decision", "UNKNOWN");
  setText(
    "settings-handbrake-preview-detail",
    [
      `Settings PipelinePlan preview failed: ${message}`,
      "No backend route summary or stream actions were rendered.",
      "This did not save settings, launch work, mutate queue state, publish, rename, drain pending publish, or touch media files.",
    ].join("\n")
  );
}

async function previewSettingsPipelinePlan() {
  if (rejectSettingsCommandWhileBusy("settings.pipeline_plan_preview", "settings-source-media-json-status", "settings-source-media-json-detail")) return;
  let sourceMedia;
  let patchRequest;
  try {
    sourceMedia = parseSettingsSourceMediaJson();
    patchRequest = settingsPipelinePlanPatchRequest();
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    appendCommandResult({
      command: "settings.pipeline_plan_preview",
      ok: false,
      severity: "error",
      message,
    });
    renderSettingsPipelinePlanPreviewError(message);
    return;
  }
  const requestId = ++settingsPipelinePlanPreviewRequestId;
  setSettingsCommandBusy(true);
  setText("settings-source-media-json-status", "Previewing...");
  setText("settings-source-media-json-detail", "Requesting backend-owned dry-run PipelinePlan preview. No settings will be saved.");
  try {
    const result = await apiPost("/api/settings/pipeline-plan-preview", {
      source_media: sourceMedia,
      changes: patchRequest.changes,
      remove_keys: patchRequest.removeKeys,
    });
    if (requestId !== settingsPipelinePlanPreviewRequestId) return;
    appendCommandResult(result);
    renderSettingsPipelinePlanPreview(result, sourceMedia);
  } catch (error) {
    if (requestId !== settingsPipelinePlanPreviewRequestId) return;
    const message = error instanceof Error ? error.message : String(error);
    appendCommandResult({
      command: "settings.pipeline_plan_preview",
      ok: false,
      severity: "error",
      message,
    });
    renderSettingsPipelinePlanPreviewError(message);
  } finally {
    if (requestId === settingsPipelinePlanPreviewRequestId) setSettingsCommandBusy(false);
  }
}

  function flushDirtySettingsBuilders() {
    // Merge any builder the operator edited (dirty) into the Changes JSON before
    // preview/save read it. Without this, toggling a control only marks the builder
    // dirty and the change never reaches the patch that is actually sent to the backend.
    const flushTargets = [
      [settingsBuilderDirty, applySettingsBuilderToPatch],
      [videoDetailSettingsBuilderState.dirty, applyVideoDetailSettingsBuilderToPatch],
      [fileSafetySettingsBuilderState.dirty, applyFileSafetySettingsBuilderToPatch],
      [networkSettingsBuilderState.dirty, applyNetworkSettingsBuilderToPatch],
      [queueSettingsBuilderState.dirty, applyQueueSettingsBuilderToPatch],
      [runtimeSettingsBuilderState.dirty, applyRuntimeSettingsBuilderToPatch],
      [pendingPublishSettingsBuilderState.dirty, applyPendingPublishSettingsBuilderToPatch],
      [subtitleSettingsBuilderState.dirty, applySubtitleSettingsBuilderToPatch],
      [audioSettingsBuilderState.dirty, applyAudioSettingsBuilderToPatch],
    ];
    let flushed = 0;
    flushTargets.forEach(([dirty, applyFn]) => {
      if (!dirty || typeof applyFn !== "function") return;
      try {
        applyFn();
        flushed += 1;
      } catch (error) {
        // Each apply function already reports its own validation error to the UI.
      }
    });
    return flushed;
  }

  async function previewSettingsPatch() {
    if (rejectSettingsCommandWhileBusy("settings.preview_patch", "settings-patch-status", "settings-patch-detail")) return;
    flushDirtySettingsBuilders();
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
  setSettingsCommandBusy(true);
  setText("settings-patch-status", "Previewing...");
  setText("settings-patch-detail", "Requesting backend patch preview. This will not save the PSD1.");
  const requestId = ++settingsPatchPreviewRequestId;
  try {
    const result = await apiPost("/api/settings/preview-patch", { changes, ...requestExtras });
    if (requestId !== settingsPatchPreviewRequestId) return;
    if ((byId("settings-patch-json")?.value || "{}") !== rawAtRequest) {
      setText("settings-patch-status", "Preview stale");
      setText("settings-patch-detail", "Patch JSON changed before the backend preview returned. Preview again before using this result.");
      return;
    }
    appendCommandResult(result);
    lastSettingsPatchPreviewEvidence = {
      signature: requestSignature,
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
  flushDirtySettingsBuilders();
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
  const requestExtras = settingsPatchRequestExtras();
  const signature = settingsPatchRequestSignature(changes, requestExtras);
  const previewMatches = Boolean(lastSettingsPatchPreviewEvidence && lastSettingsPatchPreviewEvidence.signature === signature);
  const previewOk = previewMatches && lastSettingsPatchPreviewEvidence.result?.ok === true;
  const previewWarning = previewOk
    ? "A matching backend Preview Patch result is available for this staged JSON."
    : previewMatches
      ? "The matching backend Preview Patch result has warnings/errors. Review it before saving."
      : "No matching backend Preview Patch result is available for this exact staged JSON.";
  const keyChanged = (key) => {
    if (!lastSettingsValues || !Object.prototype.hasOwnProperty.call(lastSettingsValues, key)) return true;
    return !settingsValuesEqual(lastSettingsValues[key], changes[key]);
  };
  const changedKeys = keys.filter(keyChanged);
  if (!changedKeys.length) {
    setText("settings-patch-status", "No changes");
    setText("settings-patch-detail", [
      "No staged settings differ from the saved config, so nothing was saved.",
      "Edit a setting on any tab (subtitle / audio / routing / etc.), then Save again.",
      "Builder edits are merged into the Changes JSON automatically when you Save.",
    ].join("\n"));
    renderSettingsPatchSummary();
    if (typeof renderAllLaunchPreflights === "function") renderAllLaunchPreflights();
    return;
  }
  const overwriteLines = changedKeys.slice(0, 12).map((key) => {
    const oldVal = (lastSettingsValues && Object.prototype.hasOwnProperty.call(lastSettingsValues, key))
      ? JSON.stringify(lastSettingsValues[key])
      : "(not previously set)";
    const newVal = JSON.stringify(changes[key]);
    return `  ${key}: ${oldVal} -> ${newVal}`;
  });
  if (changedKeys.length > 12) overwriteLines.push(`  ...and ${changedKeys.length - 12} more changed key(s)`);
  const confirmLines = [
    `Save ${changedKeys.length} changed setting(s) to the active PSD1 config?`,
    "",
    previewWarning,
    "",
    "Values being overwritten:",
    ...overwriteLines,
    "",
    "A backup will be created first.",
    "",
    settingsRuntimeRestartConfirmationLine(),
  ];
  if (!window.confirm(confirmLines.join("\n"))) {
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
  const snapshotBefore = {};
  changedKeys.forEach((key) => {
    if (lastSettingsValues && Object.prototype.hasOwnProperty.call(lastSettingsValues, key)) {
      snapshotBefore[key] = lastSettingsValues[key];
    }
  });
  setSettingsCommandBusy(true);
  setText("settings-patch-status", "Saving...");
  setText("settings-patch-detail", `Saving backend-validated patch to the active PSD1. A backup will be created first.\n${previewWarning}`);
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
    if (result.ok) {
      lines.push("", ...settingsRuntimeRestartNoticeLines(result));
    }
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

  function settingsBrowsePathDetailLines(result, fieldLabel) {
    const data = result?.data && typeof result.data === "object" ? result.data : {};
    const validation = data.validation && typeof data.validation === "object" ? data.validation : {};
    const lines = [
      result?.message || `Settings folder browse returned for ${fieldLabel}.`,
      validation.message ? `Validation: ${validation.message}` : "Validation: no selected-folder evidence returned.",
      `Writes config: ${data.writes_config === true ? "yes" : "no"}`,
      `Stages only: ${data.stages_only === true ? "yes" : "no"}`,
      "Next step: Merge File Safety Patch, then Preview Patch before Save Patch. Launch uses saved backend settings only.",
      "Mutation guardrail: this route only opens a backend-owned Windows folder picker and stages one allowlisted Settings field. It cannot save settings, launch work, rewrite queue state, publish, rename, delete, or touch media files.",
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
        "Use Merge File Safety Patch and backend Preview Patch before Save Patch.",
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
        setText("settings-file-safety-builder-status", `${fieldLabel} path staged`);
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
  }

  window.mediaPipelineSettingsView = {
    configValue, buildSettingsOverviewRows, renderSettingsOverview, setSettingsRows, renderSettingsRows, settingsBuilderCoveredKeys,
    settingsRawTriageRows, settingsRawTriageStatus, settingsRawTriageSummaryLines, settingsRawTriageDetailLines, renderSettingsRawTriage,
    settingsRawActionPlanRows, settingsRawActionPlanStatus, settingsRawActionPlanSummaryLines, settingsRawActionPlanDetailLines, renderSettingsRawActionPlan,
    settingsSafetyLockRows, settingsSafetyLockStatus, settingsSafetyLockSummaryLines, renderSettingsSafetyLocks,
    renderSettings, getLastSettings, validateCurrentSettings, reloadSettingsFromDisk, browseSettingsPath, settingsBrowsePathDetailLines,
    setSettingsCommandBusy, rejectSettingsCommandWhileBusy, previewSettingsPipelinePlan, previewSettingsPatch, saveSettingsPatch, isSettingsCommand, settingsCommandHistoryLine, renderSettingsCommandHistory,
    renderSettingsPatchSummary, settingsPatchImpactEntries, renderSettingsPatchImpactSummaryFromEntries, settingsPatchSaveReadinessIssues, settingsPatchSaveReadinessStatus, renderSettingsPatchSaveReadinessFromEntries,
    settingsPolicyDeltaRows, settingsPolicyDeltaStatus, settingsPolicyDeltaSummaryLines, renderSettingsPolicyDeltaFromEntries,
    settingsEffectivePolicyRows, settingsEffectivePolicyTrustStatus, settingsEffectivePolicySummaryLines, settingsEffectivePolicyDetailLines, renderSettingsEffectivePolicyTrustFromEntries, renderSettingsEffectivePolicyTrustForError,
    settingsSaveReviewRows, settingsSaveReviewStatus, settingsSaveReviewDetailLines, renderSettingsSaveReviewFromEntries,
    settingsLaunchImpactRows, settingsLaunchImpactStatus, settingsLaunchImpactSummaryLines, renderSettingsLaunchImpactHandoffFromEntries,
    markSettingsPatchTouched, settingsPatchIsTouched, settingsPatchEffectiveChangedEntries, settingsPatchHasUnsavedChanges, settingsStableJsonValue, settingsPatchSignature, settingsCurrentPatchSignature,
    syncSettingsBuilderFromConfig, collectSettingsBuilderPatch, applySettingsBuilderToPatch, refreshSettingsBuilderChoices, renderSettingsBuilderGuidance, markSettingsBuilderDirty,
    syncVideoDetailSettingsBuilderFromConfig, collectVideoDetailSettingsBuilderPatch, applyVideoDetailSettingsBuilderToPatch, renderVideoDetailSettingsBuilderGuidance, markVideoDetailSettingsBuilderDirty,
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
    writeSettingsPatchJson, parseSettingsPatchJson, initSettingsViewEvents,
  };
  window.configValue = configValue; window.buildSettingsOverviewRows = buildSettingsOverviewRows; window.renderSettingsOverview = renderSettingsOverview; window.setSettingsRows = setSettingsRows;
  window.renderSettingsRows = renderSettingsRows; window.settingsBuilderCoveredKeys = settingsBuilderCoveredKeys; window.settingsRawTriageRows = settingsRawTriageRows; window.settingsRawTriageStatus = settingsRawTriageStatus;
  window.settingsRawTriageSummaryLines = settingsRawTriageSummaryLines; window.settingsRawTriageDetailLines = settingsRawTriageDetailLines; window.renderSettingsRawTriage = renderSettingsRawTriage; window.settingsRawActionPlanRows = settingsRawActionPlanRows;
  window.settingsRawActionPlanStatus = settingsRawActionPlanStatus; window.settingsRawActionPlanSummaryLines = settingsRawActionPlanSummaryLines; window.settingsRawActionPlanDetailLines = settingsRawActionPlanDetailLines; window.renderSettingsRawActionPlan = renderSettingsRawActionPlan;
  window.settingsSafetyLockRows = settingsSafetyLockRows; window.settingsSafetyLockStatus = settingsSafetyLockStatus; window.settingsSafetyLockSummaryLines = settingsSafetyLockSummaryLines; window.renderSettingsSafetyLocks = renderSettingsSafetyLocks;
  window.renderSettings = renderSettings; window.getLastSettings = getLastSettings; window.isSettingsCommand = isSettingsCommand; window.settingsCommandHistoryLine = settingsCommandHistoryLine; window.renderSettingsCommandHistory = renderSettingsCommandHistory;
  window.settingsPolicyDeltaRows = settingsPolicyDeltaRows; window.settingsPolicyDeltaStatus = settingsPolicyDeltaStatus; window.settingsLaunchImpactRows = settingsLaunchImpactRows; window.settingsLaunchImpactStatus = settingsLaunchImpactStatus;
  window.settingsPatchIsTouched = settingsPatchIsTouched; window.settingsPatchEffectiveChangedEntries = settingsPatchEffectiveChangedEntries; window.syncVideoDetailSettingsBuilderFromConfig = syncVideoDetailSettingsBuilderFromConfig; window.collectVideoDetailSettingsBuilderPatch = collectVideoDetailSettingsBuilderPatch;
  window.applyVideoDetailSettingsBuilderToPatch = applyVideoDetailSettingsBuilderToPatch; window.renderVideoDetailSettingsBuilderGuidance = renderVideoDetailSettingsBuilderGuidance; window.markVideoDetailSettingsBuilderDirty = markVideoDetailSettingsBuilderDirty; window.syncFileSafetySettingsBuilderFromConfig = syncFileSafetySettingsBuilderFromConfig;
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
  window.renderSettingsMediaPolicyCrossCheck = renderSettingsMediaPolicyCrossCheck; window.writeSettingsPatchJson = writeSettingsPatchJson; window.previewSettingsPipelinePlan = previewSettingsPipelinePlan; window.initSettingsViewEvents = initSettingsViewEvents;
  window.settingsRuntimeRestartConfirmationLine = settingsRuntimeRestartConfirmationLine; window.settingsRuntimeRestartNoticeLines = settingsRuntimeRestartNoticeLines;

  (function () {
    const previewBtn = byId("settings-save-header-preview-button");
    if (previewBtn) previewBtn.addEventListener("click", previewSettingsPatch);
    const saveBtn = byId("settings-save-header-save-button");
    if (saveBtn) saveBtn.addEventListener("click", saveSettingsPatch);
    const reloadBtn = byId("settings-save-header-reload-button");
    if (reloadBtn) reloadBtn.addEventListener("click", reloadSettingsFromDisk);
  }());
})();
