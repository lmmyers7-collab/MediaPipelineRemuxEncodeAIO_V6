(function () {
  const createSettingsMediaProjection = window.__settingsMediaProjectionModule;
  const createSettingsEffectivePolicyView = window.__settingsEffectivePolicyViewModule;
  delete window.__settingsMediaProjectionModule;
  delete window.__settingsEffectivePolicyViewModule;
  if (typeof createSettingsMediaProjection !== "function" || typeof createSettingsEffectivePolicyView !== "function") {
    throw new Error("Settings policy-impact child modules must load before policyImpact.js");
  }

  function createSettingsPolicyImpactModule(deps) {
    deps = deps || {};
    const byId = deps.byId || function () { return null; };
    const setText = deps.setText || function () {};
    const clearRows = deps.clearRows || function () {};
    const appendCells = deps.appendCells || function () {};
    const getCommandHistory = deps.getCommandHistory || function () { return []; };
    const isSettingsCommand = deps.isSettingsCommand || function () { return false; };
    const settingsCommandHistoryLine = deps.settingsCommandHistoryLine || function () { return ""; };
    const settingsPatchSaveReadinessIssues = deps.settingsPatchSaveReadinessIssues || function () { return []; };
    const settingsPatchSaveReadinessStatus = deps.settingsPatchSaveReadinessStatus || function () { return "No changes"; };
    const makeRowSelectable = deps.makeRowSelectable || function (row, handler) { if (row) row.addEventListener("click", handler); };
    const updateTableStatusLegend = deps.updateTableStatusLegend || function () {};
    const formatConfigValue = deps.formatConfigValue || function (value) { return String(value ?? ""); };
    const formatSettingsChoiceLabel = deps.formatSettingsChoiceLabel || function (value) { return String(value || ""); };
    const formatSettingsListValue = deps.formatSettingsListValue || function (value) { return Array.isArray(value) ? value.join(", ") : String(value ?? ""); };
    const parseSettingsListText = deps.parseSettingsListText || function (value) { return String(value || "").split(",").map((item) => item.trim()).filter(Boolean); };
    const settingsBuilderConfigValue = deps.settingsBuilderConfigValue || function (_key, fallback) { return fallback; };
    const settingsBuilderInputValue = deps.settingsBuilderInputValue || function () { return ""; };
    const settingsFieldDefinition = deps.settingsFieldDefinition || function () { return null; };
    const settingsRawConfigValue = deps.settingsRawConfigValue || function () { return undefined; };
    const parseSettingsPatchJson = deps.parseSettingsPatchJson || function () { return {}; };
    const settingsValuesEqual = deps.settingsValuesEqual || function (left, right) { return JSON.stringify(left) === JSON.stringify(right); };
    const settingsImpactGroups = Array.isArray(deps.settingsImpactGroups) ? deps.settingsImpactGroups : [];
    const settingsSpecificImpactHints = deps.settingsSpecificImpactHints || {};
    const getLastSettings = deps.getLastSettings || function () { return null; };
    const getLastSettingsValues = deps.getLastSettingsValues || function () { return {}; };
    const getLastSettingsPatchPreviewEvidence = deps.getLastSettingsPatchPreviewEvidence || function () { return null; };
    const getLastSettingsPatchSaveEvidence = deps.getLastSettingsPatchSaveEvidence || function () { return null; };
    const getSelectedSettingsEffectivePolicyKey = deps.getSelectedSettingsEffectivePolicyKey || function () { return ""; };
    const setSelectedSettingsEffectivePolicyKey = deps.setSelectedSettingsEffectivePolicyKey || function () {};

    const mediaProjection = createSettingsMediaProjection({
      appendCells, byId, clearRows, formatSettingsChoiceLabel, formatSettingsListValue, parseSettingsListText,
      setText, settingsActiveRouteHeightBoundaries, settingsBuilderConfigValue, settingsBuilderInputValue,
    });
    const effectivePolicyView = createSettingsEffectivePolicyView({
      appendCells, byId, clearRows, getLastSettings, getLastSettingsPatchPreviewEvidence, getLastSettingsPatchSaveEvidence,
      getLastSettingsValues, getSelectedSettingsEffectivePolicyKey, makeRowSelectable, parseSettingsPatchJson,
      setSelectedSettingsEffectivePolicyKey, setText, settingsBackendMediaPolicyReadiness, settingsBackendMediaPolicyStatus,
      settingsCurrentPatchSignature, settingsPatchImpactEntries, settingsPolicyDeltaRows, settingsPolicyDeltaStatus, updateTableStatusLegend,
    });
    const {
      settingsMediaPolicyList, settingsMediaPolicyBool, settingsMediaPolicyValue, settingsMediaPolicyNumber,
      settingsMediaPolicyLanguageGaps, settingsMediaPolicyRows, settingsMediaPolicyStatus,
      settingsActiveMediaPolicyRows, settingsActiveMediaPolicyStatus, settingsActiveMediaPolicySummaryLines,
      renderSettingsActiveMediaPolicyHandoff, settingsMediaPolicySummaryLines, renderSettingsMediaPolicyCrossCheck,
    } = mediaProjection;
    const {
      settingsEffectivePolicyRowKey, settingsEvidenceMatch, settingsEvidenceResultLabel, settingsEffectivePolicyRows,
      settingsEffectivePolicyTrustStatus, settingsEffectivePolicySummaryLines, settingsEffectivePolicyDetailLines,
      selectedSettingsEffectivePolicyRow, renderSettingsEffectivePolicyTrustFromEntries, renderSettingsEffectivePolicyTrustForError,
    } = effectivePolicyView;


function settingsRouteMaxHeightFromUpperTolerance(baseHeight, tolerancePercent) {
  return Math.round(Number(baseHeight) * (1 + (Number(tolerancePercent) / 100)));
}

function settingsRouteMinHeightFromLowerTolerance(baseHeight, tolerancePercent) {
  return Math.round(Number(baseHeight) * (1 - (Number(tolerancePercent) / 100)));
}

function settingsRouteHeightBoundariesFromValues(values) {
  return {
    route1080pMaxHeight: settingsRouteMaxHeightFromUpperTolerance(1080, values.route1080pUpperPercent ?? 11.111111),
    route1440pMinHeight: settingsRouteMinHeightFromLowerTolerance(1440, values.route1440pLowerPercent ?? 16.597222),
    route1440pMaxHeight: settingsRouteMaxHeightFromUpperTolerance(1440, values.route1440pUpperPercent ?? 24.930556),
    route4kMinHeight: settingsRouteMinHeightFromLowerTolerance(2160, values.route4kLowerPercent ?? 16.666667),
  };
}

function settingsActiveRouteHeightBoundaries() {
  return settingsRouteHeightBoundariesFromValues({
    route1080pUpperPercent: settingsMediaPolicyNumber("settings-builder-1080p-upper-tolerance", "Route1080pUpperHeightTolerancePercent", 11.111111),
    route1440pLowerPercent: settingsMediaPolicyNumber("settings-builder-1440p-lower-tolerance", "Route1440pLowerHeightTolerancePercent", 16.597222),
    route1440pUpperPercent: settingsMediaPolicyNumber("settings-builder-1440p-upper-tolerance", "Route1440pUpperHeightTolerancePercent", 24.930556),
    route4kLowerPercent: settingsMediaPolicyNumber("settings-builder-4k-lower-tolerance", "Route4KLowerHeightTolerancePercent", 16.666667),
  });
}

function settingsPatchHasCurrentPercentKeys() {
  return [
    "Route1080pUpperHeightTolerancePercent",
    "Route1440pLowerHeightTolerancePercent",
    "Route1440pUpperHeightTolerancePercent",
    "Route4KLowerHeightTolerancePercent",
  ].some((key) => {
    const value = settingsRawConfigValue(key);
    return value !== undefined && value !== null && String(value).trim() !== "";
  });
}

function settingsPatchHasCandidatePercentKeys(entries) {
  return settingsPatchHasCurrentPercentKeys() || entries.some((entry) => [
    "Route1080pUpperHeightTolerancePercent",
    "Route1440pLowerHeightTolerancePercent",
    "Route1440pUpperHeightTolerancePercent",
    "Route4KLowerHeightTolerancePercent",
  ].includes(entry.key));
}

function settingsPatchRouteHeightBoundaries(entries, mode) {
  const candidate = mode === "candidate";
  const numberValue = candidate ? settingsPatchCandidateNumber : ((_entries, key, fallback) => settingsPatchCurrentNumber(key, fallback));
  return settingsRouteHeightBoundariesFromValues({
    route1080pUpperPercent: numberValue(entries, "Route1080pUpperHeightTolerancePercent", 11.111111),
    route1440pLowerPercent: numberValue(entries, "Route1440pLowerHeightTolerancePercent", 16.597222),
    route1440pUpperPercent: numberValue(entries, "Route1440pUpperHeightTolerancePercent", 24.930556),
    route4kLowerPercent: numberValue(entries, "Route4KLowerHeightTolerancePercent", 16.666667),
  });
}


function settingsBackendPolicyImpact(settings = getLastSettings()) {
  const impact = settings?.policy_impact || {};
  if (!impact || impact.schema_version !== "settings_policy_impact.v1") {
    return { schema_version: "", media_policy_readiness: null, launch_risk_handoff: null };
  }
  return impact;
}

function settingsBackendMediaPolicyReadiness(settings = getLastSettings()) {
  const policyImpact = settingsBackendPolicyImpact(settings);
  const readiness = policyImpact.media_policy_readiness || settings?.media_policy_readiness || {};
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

function renderSettingsBackendMediaPolicyReadiness(settings = getLastSettings()) {
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
    "Backend Save remains the source of truth before writing.",
  ];
  if (!changedEntries.length) {
    lines.push("No effective changes detected.");
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
  return value === undefined || value === null ? [] : [String(value)];
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
  return labels.length ? `Changed: ${labels.join(", ")}.` : "No effective current change in this area.";
}

function settingsPolicyDeltaBoolText(value) {
  return value ? "on" : "off";
}

function settingsPolicyDeltaStatus(rows) {
  if (!rows.length) return "No current change";
  const postures = rows.map((row) => String(row.posture || "").toLowerCase());
  if (postures.some((posture) => posture.includes("blocked") || posture.includes("critical"))) return "Blocked review";
  if (postures.some((posture) => posture.includes("high"))) return "High review";
  if (postures.some((posture) => posture.includes("review") || posture.includes("staged") || posture.includes("preview"))) return "Review";
  return "No blocker";
}

// Frontend advisory only: backend Save Settings remains authoritative for
// schema validation, source-deletion acceptance, and PSD1 writes.
function settingsPolicyDeltaRows(entries) {
  const changedEntries = entries.filter((entry) => entry.changed);
  const unknownEntries = changedEntries.filter((entry) => !entry.field);
  const rows = [];

  rows.push({
    area: "Change scope",
    posture: !changedEntries.length ? "idle" : unknownEntries.length ? "blocked" : "pending",
    current: `${entries.length} candidate key(s); ${changedEntries.length} effective change(s).`,
    candidate: unknownEntries.length
      ? `${unknownEntries.length} unknown key(s): ${unknownEntries.slice(0, 6).map((entry) => entry.key).join(", ")}${unknownEntries.length > 6 ? ", ..." : ""}`
      : `${changedEntries.length} known effective change(s).`,
    check: changedEntries.length
      ? "Use Save Settings to review and validate; Launch continues using saved settings until backend save/reload succeeds."
      : "No effective settings change is pending.",
  });

  const routingKeys = [
    "RoutingProfile",
    "RouteThresholdMode",
    "SizeGuardMode",
    "MovieRoute1080pTargetSizeGB",
    "MovieRoute1440pTargetSizeGB",
    "MovieRoute4KTargetSizeGB",
    "TVRoute1080pTargetSizeGB",
    "TVRoute1440pTargetSizeGB",
    "TVRoute4KTargetSizeGB",
    "Route1080pUpperHeightTolerancePercent",
    "Route1080pMaxVideoBitrateMbps",
    "Route1440pLowerHeightTolerancePercent",
    "Route1440pUpperHeightTolerancePercent",
    "Route1440pMaxVideoBitrateMbps",
    "Route4KLowerHeightTolerancePercent",
    "Route4KMaxVideoBitrateMbps",
    "MaxEncodeGrowthPercent",
    "CompatibilityEncodeGrowthPercent",
  ];
  const currentRouteThresholdMode = settingsPatchCurrentText("RouteThresholdMode", "compatibility_advisory").toLowerCase();
  const nextRouteThresholdMode = settingsPatchCandidateText(entries, "RouteThresholdMode", "compatibility_advisory").toLowerCase();
  const currentSizeGuard = settingsPatchCurrentText("SizeGuardMode", "advisory").toLowerCase();
  const nextSizeGuard = settingsPatchCandidateText(entries, "SizeGuardMode", "advisory").toLowerCase();
  const currentMaxGrowth = settingsPatchCurrentNumber("MaxEncodeGrowthPercent", 5);
  const nextMaxGrowth = settingsPatchCandidateNumber(entries, "MaxEncodeGrowthPercent", 5);
  const currentCompatGrowth = settingsPatchCurrentNumber("CompatibilityEncodeGrowthPercent", 15);
  const nextCompatGrowth = settingsPatchCandidateNumber(entries, "CompatibilityEncodeGrowthPercent", 15);
  const currentRouteBoundaries = settingsPatchRouteHeightBoundaries(entries, "current");
  const nextRouteBoundaries = settingsPatchRouteHeightBoundaries(entries, "candidate");
  rows.push({
    area: "Routing / output-size guard",
    posture: ["off", "disabled"].includes(nextSizeGuard) || nextMaxGrowth > 15 || nextCompatGrowth > 30 ? "review" : (settingsPolicyDeltaChangedLabels(entries, routingKeys).length ? "preview required" : "unchanged"),
    current: `profile=${formatSettingsChoiceLabel(settingsPatchCurrentText("RoutingProfile", "plex_direct_stream"))}; threshold=${formatSettingsChoiceLabel(currentRouteThresholdMode)}; guard=${formatSettingsChoiceLabel(currentSizeGuard)}; growth=${currentMaxGrowth}%/${currentCompatGrowth}%; size targets 1080p=${settingsPatchCurrentNumber("MovieRoute1080pTargetSizeGB", 8)}/${settingsPatchCurrentNumber("TVRoute1080pTargetSizeGB", 3)}GB, 1440p=${settingsPatchCurrentNumber("MovieRoute1440pTargetSizeGB", 8)}/${settingsPatchCurrentNumber("TVRoute1440pTargetSizeGB", 3)}GB, 4K=${settingsPatchCurrentNumber("MovieRoute4KTargetSizeGB", 8)}/${settingsPatchCurrentNumber("TVRoute4KTargetSizeGB", 3)}GB; unknown height uses 1080p targets and ${settingsPatchCurrentNumber("Route1080pMaxVideoBitrateMbps", 20)}Mbps cap; buckets 1080p<=${currentRouteBoundaries.route1080pMaxHeight}p ${settingsPatchCurrentNumber("Route1080pMaxVideoBitrateMbps", 20)}Mbps, 1440p ${currentRouteBoundaries.route1440pMinHeight}-${currentRouteBoundaries.route1440pMaxHeight}p ${settingsPatchCurrentNumber("Route1440pMaxVideoBitrateMbps", 35)}Mbps, 4K>=${currentRouteBoundaries.route4kMinHeight}p ${settingsPatchCurrentNumber("Route4KMaxVideoBitrateMbps", 35)}Mbps`,
    candidate: `profile=${formatSettingsChoiceLabel(settingsPatchCandidateText(entries, "RoutingProfile", "plex_direct_stream"))}; threshold=${formatSettingsChoiceLabel(nextRouteThresholdMode)}; guard=${formatSettingsChoiceLabel(nextSizeGuard)}; growth=${nextMaxGrowth}%/${nextCompatGrowth}%; size targets 1080p=${settingsPatchCandidateNumber(entries, "MovieRoute1080pTargetSizeGB", 8)}/${settingsPatchCandidateNumber(entries, "TVRoute1080pTargetSizeGB", 3)}GB, 1440p=${settingsPatchCandidateNumber(entries, "MovieRoute1440pTargetSizeGB", 8)}/${settingsPatchCandidateNumber(entries, "TVRoute1440pTargetSizeGB", 3)}GB, 4K=${settingsPatchCandidateNumber(entries, "MovieRoute4KTargetSizeGB", 8)}/${settingsPatchCandidateNumber(entries, "TVRoute4KTargetSizeGB", 3)}GB; unknown height uses 1080p targets and ${settingsPatchCandidateNumber(entries, "Route1080pMaxVideoBitrateMbps", 20)}Mbps cap; buckets 1080p<=${nextRouteBoundaries.route1080pMaxHeight}p ${settingsPatchCandidateNumber(entries, "Route1080pMaxVideoBitrateMbps", 20)}Mbps, 1440p ${nextRouteBoundaries.route1440pMinHeight}-${nextRouteBoundaries.route1440pMaxHeight}p ${settingsPatchCandidateNumber(entries, "Route1440pMaxVideoBitrateMbps", 35)}Mbps, 4K>=${nextRouteBoundaries.route4kMinHeight}p ${settingsPatchCandidateNumber(entries, "Route4KMaxVideoBitrateMbps", 35)}Mbps`,
    check: `${settingsPolicyDeltaChangedText(entries, routingKeys)} The output-size guard and growth limits affect remux-vs-encode trust and oversized-output review.`,
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
    "VobSubExtractLanguages",
    "ConvertTx3gToSrt",
    "DropTx3gAfterConversion",
    "CreateExternalTx3gSrtSidecars",
    "ConvertBdpgsToSrt",
    "DropBdpgsAfterConversion",
    "ConvertVobSubToSrt",
    "DropVobSubAfterConversion",
    "DropAssAfterConversion",
    "StripFormatting",
    "RemoveKaraoke",
    "KeepSignsAndSongs",
  ];
  const nextContainer = settingsPatchCandidateText(entries, "OutputContainer", "mkv").toLowerCase();
  const nextConvertTx3g = settingsPatchCandidateBool(entries, "ConvertTx3gToSrt", true);
  const nextDropTx3g = settingsPatchCandidateBool(entries, "DropTx3gAfterConversion", false);
  const nextConvertBdpgs = settingsPatchCandidateBool(entries, "ConvertBdpgsToSrt", false);
  const nextDropBdpgs = settingsPatchCandidateBool(entries, "DropBdpgsAfterConversion", false);
  const nextConvertVobSub = settingsPatchCandidateBool(entries, "ConvertVobSubToSrt", false);
  const nextDropVobSub = settingsPatchCandidateBool(entries, "DropVobSubAfterConversion", false);
  const nextDropAss = settingsPatchCandidateBool(entries, "DropAssAfterConversion", false);
  const subtitleBlocked = (nextDropTx3g && !nextConvertTx3g) || (nextDropBdpgs && !nextConvertBdpgs) || (nextDropVobSub && !nextConvertVobSub);
  rows.push({
    area: "Container / subtitle preservation",
    posture: subtitleBlocked ? "blocked" : (nextContainer === "mp4" || nextDropTx3g || nextDropBdpgs || nextDropVobSub || nextDropAss || !nextConvertTx3g || !nextConvertBdpgs || !nextConvertVobSub ? "review" : (settingsPolicyDeltaChangedLabels(entries, subtitleKeys).length ? "preview required" : "unchanged")),
    current: `container=${formatSettingsChoiceLabel(settingsPatchCurrentText("OutputContainer", "mkv"))}; TX3G=${settingsPolicyDeltaBoolText(settingsPatchCurrentBool("ConvertTx3gToSrt", true))}/${settingsPolicyDeltaBoolText(settingsPatchCurrentBool("DropTx3gAfterConversion", false))}; BDPGS=${settingsPolicyDeltaBoolText(settingsPatchCurrentBool("ConvertBdpgsToSrt", false))}/${settingsPolicyDeltaBoolText(settingsPatchCurrentBool("DropBdpgsAfterConversion", false))}; VobSub=${settingsPolicyDeltaBoolText(settingsPatchCurrentBool("ConvertVobSubToSrt", false))}/${settingsPolicyDeltaBoolText(settingsPatchCurrentBool("DropVobSubAfterConversion", false))}; ASS drop=${settingsPolicyDeltaBoolText(settingsPatchCurrentBool("DropAssAfterConversion", false))}`,
    candidate: `container=${formatSettingsChoiceLabel(nextContainer)}; keep=${settingsPatchCandidateList(entries, "SubKeepLanguages", ["eng", "und"]).join(", ") || "(empty)"}; TX3G=${settingsPolicyDeltaBoolText(nextConvertTx3g)}/${settingsPolicyDeltaBoolText(nextDropTx3g)}; BDPGS=${settingsPolicyDeltaBoolText(nextConvertBdpgs)}/${settingsPolicyDeltaBoolText(nextDropBdpgs)}; VobSub=${settingsPolicyDeltaBoolText(nextConvertVobSub)}/${settingsPolicyDeltaBoolText(nextDropVobSub)}; ASS drop=${settingsPolicyDeltaBoolText(nextDropAss)}`,
    check: subtitleBlocked
      ? "Do not drop TX3G/BDPGS/VobSub originals when the matching SRT/OCR conversion is disabled."
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
    check: `${settingsPolicyDeltaChangedText(entries, networkKeys)} WebView network lifecycle controls remain backend-owned; WorkerConfigOverrides is currently ignored by backend encode policy.`,
  });

  rows.push({
    area: "Mutation boundary",
    posture: "backend-owned",
    current: "Current config is read-only in this table.",
    candidate: "Current edits are still pending until backend Save succeeds.",
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
    "Save-candidate media-policy delta:",
    `Status: ${settingsPolicyDeltaStatus(rows)}`,
    `Rows: ${rows.length}; blocked=${counts.blocked || 0}; critical-blocked=${counts["critical blocked"] || 0}; review=${counts.review || 0}; preview-required=${counts["preview required"] || 0}; staged=${counts.staged || 0}.`,
    "This compares current saved values against the local save candidate before backend Save.",
    "Backend Save remains authoritative for schema validation, risk classification, PSD1 serialization, and redacted diff evidence.",
  ];
  if (reviewRows.length) {
    lines.push("", "Rows needing operator attention:");
    reviewRows.slice(0, 7).forEach((row) => lines.push(`- ${row.area}: ${row.posture}; ${row.check}`));
  } else {
    lines.push("", "No current media-policy contradictions detected locally.");
  }
  lines.push("", "Mutation guardrail: this delta is read-only and cannot save settings, launch work, mutate queues, publish, rename, or touch media.");
  return lines;
}

function renderSettingsPolicyDeltaFromEntries(entries) {
  const rows = settingsPolicyDeltaRows(entries);
  const tbody = byId("settings-policy-delta-rows");
  setText("settings-policy-delta-status", settingsPolicyDeltaStatus(rows));
  setText("settings-policy-delta-summary", settingsPolicyDeltaSummaryLines(rows).join("\n"));
  setText("settings-policy-delta-legend", "Save-candidate media-policy delta is read-only; backend Save remains authoritative.");
  if (!tbody) return;
  if (!rows.length) {
    clearRows(tbody, 5, "No save-candidate media-policy delta loaded.");
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
    `Save-candidate media-policy delta unavailable because Changes JSON is invalid.\n${message}\nSave Settings cannot run until this is valid JSON.`
  );
  clearRows(byId("settings-policy-delta-rows"), 5, "Save-candidate media-policy delta unavailable because Changes JSON is invalid.");
  setText("settings-policy-delta-legend", "Save-candidate media-policy delta is read-only; backend Save remains authoritative.");
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
      const history = getCommandHistory();
      if (!Array.isArray(history)) return null;
      return history.find(isSettingsCommand) || null;
    }

    function settingsLaunchImpactRows(entries) {
      const changedEntries = entries.filter((entry) => entry.changed);
      const issues = settingsPatchSaveReadinessIssues(entries);
      const rows = [];
      rows.push({
        area: "Current changes",
        posture: changedEntries.length ? "pending" : entries.length ? "unchanged" : "idle",
        evidence: `${entries.length} candidate key(s); ${changedEntries.length} effective change(s); ${entries.filter((entry) => !entry.field).length} unknown key(s).`,
        check: changedEntries.length
          ? "Launch continues to use saved backend settings until Save Settings succeeds and settings reload/refresh completes."
          : "No effective changes are waiting to affect Launch.",
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
        check: "Use Save Settings to review and validate. Backend save owns schema validation, PSD1 writes, backups, and reload.",
      });

      const latestCommand = settingsLaunchImpactLatestSettingsCommand();
      if (!latestCommand) {
        rows.push({
          area: "Last backend settings command",
          posture: "no history",
          evidence: "No settings validate/reload/save command is available in recent command history.",
          check: "Use Save Settings for PSD1 writes; use Reload From Disk after out-of-band config edits.",
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
              ? "Preview does not apply changes to Launch. Save Settings must succeed before Launch uses this config."
            : "Resolve command review items/errors before relying on changed settings for Launch.",
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
      if (postures.some((posture) => posture.includes("pending") || posture.includes("preview only") || posture.includes("review") || posture.includes("no history"))) return "Review";
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
        return posture.includes("pending")
          || posture.includes("review")
          || posture.includes("blocked")
          || posture.includes("high")
          || posture.includes("preview only")
          || posture.includes("no history");
      });
      const lines = [
        "Settings-to-launch handoff:",
        `Status: ${settingsLaunchImpactStatus(rows)}`,
        `Rows: ${rows.length}; pending=${counts.staged || 0}; blocked=${counts.blocked || 0}; high-review=${counts["high review"] || 0}; preview-only=${counts["preview only"] || 0}.`,
        "Launch uses saved backend settings, not unsaved edits. Save Settings plus refresh/reload is required before current changes can affect Launch.",
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
      row.dataset.status = posture.includes("blocked") ? "blocked" : (posture.includes("review") || posture.includes("pending") || posture.includes("preview only") || posture.includes("no history") ? "warning" : "match");
        appendCells(row, [item.area, item.posture, item.evidence, item.check]);
        tbody.appendChild(row);
      });
    }

    function renderSettingsLaunchImpactHandoffForError(message) {
      setText("settings-launch-impact-status", "Invalid JSON");
      setText(
        "settings-launch-impact-summary",
        `Settings-to-launch handoff unavailable because Changes JSON is invalid.\n${message}\nLaunch will continue using saved backend settings; Save Settings cannot run until this is valid JSON.`
      );
      clearRows(byId("settings-launch-impact-rows"), 4, "Settings-to-launch handoff unavailable because Changes JSON is invalid.");
      setText("settings-launch-impact-legend", "Settings-to-launch handoff is read-only; backend launch validation remains authoritative.");
    }

    return {
      settingsMediaPolicyList,
      settingsMediaPolicyBool,
      settingsMediaPolicyValue,
      settingsMediaPolicyNumber,
      settingsMediaPolicyLanguageGaps,
      settingsMediaPolicyRows,
      settingsMediaPolicyStatus,
      settingsActiveMediaPolicyRows,
      settingsActiveMediaPolicyStatus,
      settingsActiveMediaPolicySummaryLines,
      renderSettingsActiveMediaPolicyHandoff,
      settingsEffectivePolicyRowKey,
      settingsEvidenceMatch,
      settingsEvidenceResultLabel,
      settingsEffectivePolicyRows,
      settingsEffectivePolicyTrustStatus,
      settingsEffectivePolicySummaryLines,
      settingsEffectivePolicyDetailLines,
      selectedSettingsEffectivePolicyRow,
      renderSettingsEffectivePolicyTrustFromEntries,
      renderSettingsEffectivePolicyTrustForError,
      settingsMediaPolicySummaryLines,
      renderSettingsMediaPolicyCrossCheck,
      settingsBackendPolicyImpact,
      settingsBackendMediaPolicyReadiness,
      settingsBackendMediaPolicyStatus,
      settingsBackendMediaPolicySummaryLines,
      renderSettingsBackendMediaPolicyReadiness,
      settingsImpactGroupForKey,
      settingsPatchEntryStatus,
      settingsPatchImpactSeverity,
      settingsPatchImpactEntries,
      renderSettingsPatchImpactSummaryFromEntries,
      settingsBoolValue,
      settingsPatchCandidateValue,
      settingsStableJsonValue,
      settingsPatchSignature,
      settingsCurrentPatchSignature,
      settingsPatchListValue,
      settingsPatchCandidateText,
      settingsPatchCandidateNumber,
      settingsPatchCandidateBool,
      settingsPatchCandidateList,
      settingsPatchCurrentText,
      settingsPatchCurrentNumber,
      settingsPatchCurrentBool,
      settingsPatchCurrentList,
      settingsPolicyDeltaChangedLabels,
      settingsPolicyDeltaChangedText,
      settingsPolicyDeltaBoolText,
      settingsPolicyDeltaStatus,
      settingsPolicyDeltaRows,
      settingsPolicyDeltaSummaryLines,
      renderSettingsPolicyDeltaFromEntries,
      renderSettingsPolicyDeltaForError,
      settingsLaunchImpactGroupText,
      settingsLaunchImpactLatestSettingsCommand,
      settingsLaunchImpactRows,
      settingsLaunchImpactStatus,
      settingsLaunchImpactSummaryLines,
      renderSettingsLaunchImpactHandoffFromEntries,
      renderSettingsLaunchImpactHandoffForError,
    };
  }

  window.__settingsPolicyImpactModule = {
    createSettingsPolicyImpactModule,
  };
})();
