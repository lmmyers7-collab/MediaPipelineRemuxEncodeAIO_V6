(function () {
  /**
   * Renders the read-only relationship between saved policy, staged changes, and backend proof.
   * Settings persistence stays in the policy-impact facade and backend save route.
   */
  function createSettingsEffectivePolicyView(deps) {
    deps = deps || {};
    const byId = deps.byId || function () { return null; };
    const setText = deps.setText || function () {};
    const clearRows = deps.clearRows || function () {};
    const appendCells = deps.appendCells || function () {};
    const makeRowSelectable = deps.makeRowSelectable || function (row, handler) { if (row) row.addEventListener("click", handler); };
    const updateTableStatusLegend = deps.updateTableStatusLegend || function () {};
    const settingsCurrentPatchSignature = deps.settingsCurrentPatchSignature || function () { return ""; };
    const getLastSettingsPatchPreviewEvidence = deps.getLastSettingsPatchPreviewEvidence || function () { return null; };
    const getLastSettingsPatchSaveEvidence = deps.getLastSettingsPatchSaveEvidence || function () { return null; };
    const getLastSettings = deps.getLastSettings || function () { return null; };
    const getLastSettingsValues = deps.getLastSettingsValues || function () { return {}; };
    const getSelectedSettingsEffectivePolicyKey = deps.getSelectedSettingsEffectivePolicyKey || function () { return ""; };
    const setSelectedSettingsEffectivePolicyKey = deps.setSelectedSettingsEffectivePolicyKey || function () {};
    const settingsBackendMediaPolicyReadiness = deps.settingsBackendMediaPolicyReadiness || function () { return { rows: [] }; };
    const settingsBackendMediaPolicyStatus = deps.settingsBackendMediaPolicyStatus || function () { return "Not evaluated"; };
    const settingsPolicyDeltaRows = deps.settingsPolicyDeltaRows || function () { return []; };
    const settingsPolicyDeltaStatus = deps.settingsPolicyDeltaStatus || function () { return "No current change"; };
    const settingsPatchImpactEntries = deps.settingsPatchImpactEntries || function () { return []; };
    const parseSettingsPatchJson = deps.parseSettingsPatchJson || function () { return {}; };

function settingsEffectivePolicyRowKey(row) {
  return String(row?.checkpoint || "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "policy-row";
}

function settingsEvidenceMatch(evidence, signature) {
  return Boolean(signature && evidence && evidence.signature === signature);
}

function settingsEvidenceResultLabel(evidence, signature) {
  if (!signature || signature === "{}") return "no current changes";
  if (!evidence) return "missing";
  if (evidence.signature !== signature) return "previous result";
  const result = evidence.result || {};
  if (result.ok === true) return Array.isArray(result.warnings) && result.warnings.length ? "current needs review" : "current ok";
  if (result.ok === false) return "current failed";
  return "current unknown";
}

function settingsEffectivePolicyRows(entries) {
  const list = Array.isArray(entries) ? entries : [];
  const changedEntries = list.filter((entry) => entry.changed);
  const unknownEntries = changedEntries.filter((entry) => !entry.field);
  const changedLabels = changedEntries.slice(0, 8).map((entry) => entry.label || entry.key);
  const signature = settingsCurrentPatchSignature();
  const hasStagedPatch = Boolean(signature && signature !== "{}");
  const previewLabel = settingsEvidenceResultLabel(getLastSettingsPatchPreviewEvidence(), signature);
  const saveLabel = settingsEvidenceResultLabel(getLastSettingsPatchSaveEvidence(), signature);
  const previewMatches = settingsEvidenceMatch(getLastSettingsPatchPreviewEvidence(), signature);
  const saveMatches = settingsEvidenceMatch(getLastSettingsPatchSaveEvidence(), signature);
  const previewResult = getLastSettingsPatchPreviewEvidence()?.result || {};
  const saveResult = getLastSettingsPatchSaveEvidence()?.result || {};
  const readiness = settingsBackendMediaPolicyReadiness(getLastSettings());
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
  const savedKeyCount = Object.keys(getLastSettingsValues() || {}).length;
  const rows = [
    {
      checkpoint: "Launch-active source of truth",
      posture: savedKeyCount ? "saved backend active" : "blocked",
      saved: savedKeyCount ? `${savedKeyCount} loaded config key(s); Launch and pipeline use this saved backend config.` : "No saved config values are loaded in WebView.",
      staged: hasStagedPatch ? `${changedEntries.length} effective current change(s) remain inactive until Save Settings succeeds and settings reload/refresh completes.` : "No current save candidate is active.",
      action: savedKeyCount ? "Use saved backend settings as the operational source of truth. Do not treat visible builder edits as launch-active." : "Reload settings from disk before launching or saving.",
      detail: [
        `Saved config key count: ${savedKeyCount}`,
        `Save candidate signature: ${signature || "(unavailable)"}`,
        "Launch-active rule: saved backend settings win until backend save and reload/refresh complete.",
      ],
    },
    {
      checkpoint: "Saved media-policy readiness",
      posture: readinessBlocked ? "blocked" : (readinessReview ? "review" : (readinessRows.length ? "coherent" : "not loaded")),
      saved: readinessRows.length ? `Backend readiness status=${readinessStatus}; rows=${readinessRows.length}.` : "No backend media-policy readiness payload is loaded.",
      staged: "Current edits do not change saved readiness evidence.",
      action: readinessBlocked
        ? "Resolve blocked saved media-policy rows before unattended runs."
        : "Use this as saved-policy evidence, then review any staged candidate in Save Settings before writing.",
      detail: readinessRows.slice(0, 8).map((row) => `${row.area || "Policy"}: ${row.posture || "review"}; ${row.operator_check || row.evidence || ""}`),
    },
    {
      checkpoint: "Current WebView changes",
      posture: unknownEntries.length ? "blocked" : (changedEntries.length ? "not active yet" : "idle"),
      saved: changedEntries.length ? `${changedEntries.length} effective change(s) differ from saved config.` : "No effective current change differs from saved config.",
      staged: changedLabels.length ? changedLabels.join(", ") : "No changed keys.",
      action: unknownEntries.length
        ? "Unknown keys are schema drift. Do not save until backend validation explains them."
        : (changedEntries.length ? "Use Save Settings to review and validate before any change can become active." : "No save action is needed for an unchanged patch."),
      detail: [
        `Save candidate keys: ${list.length}`,
        `Effective changes: ${changedEntries.length}`,
        `Unknown changed keys: ${unknownEntries.length}`,
        `Changed keys: ${changedEntries.map((entry) => entry.key).join(", ") || "(none)"}`,
      ],
    },
    {
      checkpoint: "Backend save proof",
      posture: !hasStagedPatch || !changedEntries.length
        ? "idle"
        : (saveMatches && saveResult.ok === true ? "saved proof present" : (previewMatches && previewResult.ok === true ? "previewed" : "review")),
      saved: `Preview=${previewLabel}; Save=${saveLabel}.`,
      staged: hasStagedPatch ? "Current save candidate has a stable signature for evidence matching." : "No current save-candidate signature is active.",
      action: !changedEntries.length
        ? "No save proof is needed for an unchanged patch."
        : (saveMatches && saveResult.ok === true
            ? "Reload/refresh settings before treating saved changes as launch-active."
            : (previewMatches && previewResult.ok === true
                ? "Optional preview matches current JSON. Save Settings still requires explicit confirmation and backend success."
                : "Use Save Settings to review current values before backend validation and write.")),
      detail: [
        `Current save-candidate signature: ${signature || "(unavailable)"}`,
        `Preview evidence: ${previewLabel}`,
        `Save evidence: ${saveLabel}`,
        `Preview command ok: ${previewResult.ok === true ? "yes" : previewResult.ok === false ? "no" : "unknown"}`,
        `Save command ok: ${saveResult.ok === true ? "yes" : saveResult.ok === false ? "no" : "unknown"}`,
      ],
    },
    {
      checkpoint: "Policy delta attention",
      posture: deltaStatus === "Blocked review" ? "blocked" : (deltaStatus === "No blocker" || deltaStatus === "No current change" ? "coherent" : "review"),
      saved: `Delta status=${deltaStatus}; saved values remain active.`,
      staged: deltaReviewRows.length ? `${deltaReviewRows.length} current policy row(s) need attention.` : "No current media-policy contradictions detected locally.",
      action: deltaReviewRows.length
        ? "Review the first changed policy rows below before Save Settings."
        : "No local media-policy blocker is visible; backend save remains authoritative.",
      detail: deltaReviewRows.slice(0, 8).map((row) => `${row.area}: ${row.posture}; ${row.check}`),
    },
    {
      checkpoint: "Mutation boundary",
      posture: "backend-owned",
      saved: "Settings display, builders, deltas, and trust rows are read-only until a backend command is sent.",
      staged: "Save Settings is the persistence command and requires confirmation.",
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
    "Launch-active policy is the saved backend config. WebView builder edits are candidates only.",
    "Save Settings plus settings reload/refresh is required before staged policy can affect a run.",
  ];
  if (reviewRows.length) {
    lines.push("", "First operator checks:");
    reviewRows.slice(0, 6).forEach((row) => lines.push(`- ${row.checkpoint}: ${row.action}`));
  } else {
    lines.push("", "No local trust contradiction detected. Continue to Save Settings only if you intend to change settings.");
  }
  lines.push("", "Mutation guardrail: this summary is read-only and cannot save settings, launch work, mutate queues, publish, rename, or touch media.");
  return lines;
}

function settingsEffectivePolicyDetailLines(row) {
  if (!row) {
    return [
      "No effective policy row selected.",
      "Select a row to inspect launch-active state, staged-state limitations, save evidence, and backend ownership.",
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
  lines.push("", "Mutation guardrail: effective-policy trust is display-only; backend Save owns validation and persistence.");
  return lines;
}

function selectedSettingsEffectivePolicyRow(rows) {
  const selectedKey = getSelectedSettingsEffectivePolicyKey();
  if (!selectedKey) return null;
  return (Array.isArray(rows) ? rows : []).find((row) => settingsEffectivePolicyRowKey(row) === selectedKey) || null;
}

function renderSettingsEffectivePolicyTrustFromEntries(entries) {
  const rows = settingsEffectivePolicyRows(entries);
  let selectedKey = getSelectedSettingsEffectivePolicyKey();
  if (selectedKey && !rows.some((row) => settingsEffectivePolicyRowKey(row) === selectedKey)) {
    setSelectedSettingsEffectivePolicyKey("");
    selectedKey = "";
  }
  if (!selectedKey && rows.length) {
    setSelectedSettingsEffectivePolicyKey(settingsEffectivePolicyRowKey(rows[0]));
    selectedKey = getSelectedSettingsEffectivePolicyKey();
  }
  setText("settings-effective-policy-status", settingsEffectivePolicyTrustStatus(rows));
  setText("settings-effective-policy-summary", settingsEffectivePolicySummaryLines(rows).join("\n"));
  setText("settings-effective-policy-legend", "Effective policy trust rows are read-only; backend Save remains the only settings persistence boundary.");
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
      setSelectedSettingsEffectivePolicyKey(key);
      renderSettingsEffectivePolicyTrustFromEntries(entries);
    }, {
      selected: selectedKey === key,
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
  setText("settings-effective-policy-legend", "Effective policy trust rows are read-only; backend Save remains the only settings persistence boundary.");
  setText("settings-effective-policy-detail", [
    "Effective policy trust detail:",
    `Patch JSON is invalid: ${message}`,
    "Fix Changes JSON before Save Settings can run.",
    "Launch-active rule: saved backend settings remain active.",
  ].join("\n"));
}


    return {
      settingsEffectivePolicyRowKey, settingsEvidenceMatch, settingsEvidenceResultLabel, settingsEffectivePolicyRows,
      settingsEffectivePolicyTrustStatus, settingsEffectivePolicySummaryLines, settingsEffectivePolicyDetailLines,
      selectedSettingsEffectivePolicyRow, renderSettingsEffectivePolicyTrustFromEntries, renderSettingsEffectivePolicyTrustForError,
    };
  }

  window.__settingsEffectivePolicyViewModule = createSettingsEffectivePolicyView;
})();
