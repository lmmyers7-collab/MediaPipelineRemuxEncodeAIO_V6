(function () {
  function createSettingsSafetyLocksModule(deps) {
    deps = deps || {};
    const byId = deps.byId || function () { return null; };
    const setText = deps.setText || function () {};
    const clearRows = deps.clearRows || function () {};
    const appendCells = deps.appendCells || function () {};
    const boundedSettingsValueText = deps.boundedSettingsValueText || function (value) { return String(value ?? ""); };
    const settingsBoolValue = deps.settingsBoolValue || function (value) { return value === true || String(value).toLowerCase() === "true"; };
    const settingsSafetyLockDefinitions = Array.isArray(deps.settingsSafetyLockDefinitions) ? deps.settingsSafetyLockDefinitions : [];
    const getLastSettingsValues = deps.getLastSettingsValues || function () { return {}; };

  function settingsValueIsNonEmpty(value) {
    if (value === undefined || value === null) return false;
    if (Array.isArray(value)) return value.length > 0;
    if (typeof value === "object") return Object.keys(value).length > 0;
    return String(value).trim().length > 0;
  }

  function settingsSafetyLockRisk(definition, value) {
    if (value === undefined) return false;
    const riskyWhen = String(definition.risky_when || "");
    if (riskyWhen === "true") return settingsBoolValue(value) === true;
    if (riskyWhen === "false") return settingsBoolValue(value) === false;
    if (riskyWhen === "non_empty") return settingsValueIsNonEmpty(value);
    if (riskyWhen === "empty") return !settingsValueIsNonEmpty(value);
    return false;
  }

  function settingsSafetyLockRows() {
    return settingsSafetyLockDefinitions.map((definition) => {
      const value = getLastSettingsValues() ? getLastSettingsValues()[definition.key] : undefined;
      const missing = value === undefined;
      const risky = settingsSafetyLockRisk(definition, value);
      return {
        key: definition.key,
        label: definition.label || definition.key,
        value,
        current: missing ? "(not set)" : boundedSettingsValueText(value),
        severity: missing ? "unknown" : (risky ? (definition.severity || "medium") : "safe"),
        status: missing ? "review default" : (risky ? "review" : "safe"),
        action: missing
          ? (definition.missing_note || "Confirm backend default before unattended processing.")
          : (risky ? (definition.risk_note || "Review this setting before unattended processing.") : (definition.safe_note || "Current value is within the normal safe posture.")),
      };
    });
  }

  function settingsSafetyLockStatus(rows = settingsSafetyLockRows()) {
    if (!rows.length) return "No locks";
    if (rows.some((row) => row.severity === "critical")) return "Critical review";
    if (rows.some((row) => row.severity === "high")) return "High review";
    if (rows.some((row) => row.severity === "medium")) return "Review";
    if (rows.some((row) => row.severity === "unknown")) return "Defaults review";
    return "Safe posture";
  }

  function settingsSafetyLockSummaryLines(rows = settingsSafetyLockRows()) {
    const counts = rows.reduce((acc, row) => {
      acc[row.severity] = (acc[row.severity] || 0) + 1;
      return acc;
    }, {});
    const reviewRows = rows.filter((row) => row.severity !== "safe");
    const lines = [
      "Settings safety lock review:",
      `- Safe=${counts.safe || 0}; critical=${counts.critical || 0}; high=${counts.high || 0}; medium=${counts.medium || 0}; unknown/default=${counts.unknown || 0}.`,
      reviewRows.length
        ? `- First review keys: ${reviewRows.slice(0, 6).map((row) => row.key).join(", ")}${reviewRows.length > 6 ? ", ..." : ""}.`
        : "- No high-risk saved safety toggles are active.",
      "Mutation guardrail: this panel is read-only. To change a lock, stage Changes JSON and use Save Settings.",
    ];
    return lines;
  }

  function renderSettingsSafetyLocks() {
    const rows = settingsSafetyLockRows();
    setText("settings-safety-lock-status", settingsSafetyLockStatus(rows));
    setText("settings-safety-lock-summary", settingsSafetyLockSummaryLines(rows).join("\n"));
    const tbody = byId("settings-safety-lock-rows");
    if (!tbody) return;
    if (!rows.length) {
      clearRows(tbody, 4, "No safety lock definitions loaded.");
      return;
    }
    tbody.replaceChildren();
    rows.forEach((item) => {
      const row = document.createElement("tr");
      if (item.severity === "critical" || item.severity === "high" || item.severity === "medium" || item.severity === "unknown") row.dataset.status = "warning";
      else row.dataset.status = "match";
      appendCells(row, [item.label, item.current, item.status, item.action]);
      tbody.appendChild(row);
    });
  }


    return {
      settingsValueIsNonEmpty,
      settingsSafetyLockRisk,
      settingsSafetyLockRows,
      settingsSafetyLockStatus,
      settingsSafetyLockSummaryLines,
      renderSettingsSafetyLocks,
    };
  }

  window.__settingsSafetyLocksModule = {
    createSettingsSafetyLocksModule,
  };
})();
