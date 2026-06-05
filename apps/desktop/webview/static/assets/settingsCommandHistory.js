(function () {
  const commandHistoryView = window.mediaPipelineCommandHistory || {};

  function isSettingsCommand(entry) {
    const command = String(entry?.command || "").toLowerCase();
    return (
      command === "settings.validate" ||
      command === "settings.reload" ||
      command === "settings.browse_path" ||
      command === "settings.preview_patch" ||
      command === "settings.save_patch"
    );
  }

  function settingsCommandLabel(command) {
    if (command === "settings.validate") return "Validate";
    if (command === "settings.reload") return "Reload";
    if (command === "settings.browse_path") return "Browse path";
    if (command === "settings.preview_patch") return "Preview patch";
    if (command === "settings.save_patch") return "Save patch";
    return command || "Settings command";
  }

  function settingsCommandDetail(entry) {
    const raw = entry?.raw && typeof entry.raw === "object" ? entry.raw : {};
    const data = raw.data && typeof raw.data === "object" ? raw.data : {};
    const request = raw.request && typeof raw.request === "object" ? raw.request : {};
    const changes = request.changes && typeof request.changes === "object" && !Array.isArray(request.changes) ? request.changes : {};
    const parts = [];
    if (data.setting_key) parts.push(`key=${data.setting_key}`);
    if (data.selected_path) parts.push(`selected=${data.selected_path}`);
    if (data.writes_config !== undefined) parts.push(`writes config ${data.writes_config === true ? "yes" : "no"}`);
    if (Object.keys(changes).length) parts.push(`${Object.keys(changes).length} requested key(s)`);
    if (Array.isArray(data.changed_keys)) parts.push(`${data.changed_keys.length} changed key(s)`);
    if (Array.isArray(data.removed_keys) && data.removed_keys.length) parts.push(`${data.removed_keys.length} removed key(s)`);
    if (data.reloaded !== undefined) parts.push(`reloaded ${data.reloaded === true ? "yes" : data.reloaded === false ? "no" : "n/a"}`);
    if (data.config_path) parts.push(`config=${data.config_path}`);
    return parts.length ? ` (${parts.join("; ")})` : "";
  }

  function settingsCommandHistoryLine(entry) {
    if (typeof commandHistoryCompactEvidenceLine === "function") {
      return commandHistoryCompactEvidenceLine(entry, {
        label: (command) => settingsCommandLabel(command),
        detail: settingsCommandDetail,
      });
    }
    const command = String(entry?.command || "");
    const status = entry?.result || (entry?.ok ? "ok" : entry?.severity || "unknown");
    const source = entry?.local ? "local" : "journal";
    return `${entry?.at || ""} ${settingsCommandLabel(command)} [${status}; ${source}] ${entry?.message || ""}${settingsCommandDetail(entry)}`.trim();
  }

  function renderSettingsCommandHistory(history = []) {
    if (typeof commandHistoryView.renderCompactCommandHistoryBlock === "function") {
      commandHistoryView.renderCompactCommandHistoryBlock({
        history,
        filter: isSettingsCommand,
        limit: 6,
        targetId: "settings-command-history",
        statusId: "settings-command-history-status",
        statusText: (entries) => `${entries.length} command${entries.length === 1 ? "" : "s"}`,
        itemLabel: "settings command",
        emptyHistoryText: "No settings command history loaded yet. Browse, validate, reload, preview, and save results will appear here after refresh.",
        emptyMatchText: "No settings browse, validate, reload, preview, or save commands found in the recent command history.",
        lineFor: settingsCommandHistoryLine,
        footer: "Backend settings patch validation/save remains the source of truth.",
      });
      return;
    }
    const entries = Array.isArray(history) ? history.filter(isSettingsCommand).slice(0, 6) : [];
    setText("settings-command-history-status", `${entries.length} command${entries.length === 1 ? "" : "s"}`);
    if (!Array.isArray(history) || !history.length) {
      setText("settings-command-history", "No settings command history loaded yet. Browse, validate, reload, preview, and save results will appear here after refresh.");
      return;
    }
    if (!entries.length) {
      setText("settings-command-history", "No settings browse, validate, reload, preview, or save commands found in the recent command history.");
      return;
    }
    const lines = [
      `Last ${entries.length} settings command${entries.length === 1 ? "" : "s"}:`,
      ...entries.map(settingsCommandHistoryLine),
      "Backend settings patch validation/save remains the source of truth.",
    ];
    setText("settings-command-history", lines.join("\n"));
  }

  /**
   * Public namespace for the settings command-history module.
   * Prefer this namespace from new code; flat window.* exports are transitional compatibility aliases when present.
   */
  window.mediaPipelineSettingsCommandHistory = {
    isSettingsCommand,
    settingsCommandLabel,
    settingsCommandDetail,
    settingsCommandHistoryLine,
    renderSettingsCommandHistory,
  };
  window.isSettingsCommand = isSettingsCommand;
  window.settingsCommandHistoryLine = settingsCommandHistoryLine;
  window.renderSettingsCommandHistory = renderSettingsCommandHistory;
})();
