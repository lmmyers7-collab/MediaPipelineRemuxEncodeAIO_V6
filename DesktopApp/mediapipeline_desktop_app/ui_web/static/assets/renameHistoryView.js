(function () {
  function isRenameApplyCommand(entry) {
    return String(entry?.command || "").toLowerCase() === "rename.apply";
  }

  function renameApplyHistoryLine(entry) {
    const raw = entry?.raw && typeof entry.raw === "object" ? entry.raw : {};
    const data = raw.data && typeof raw.data === "object" ? raw.data : {};
    const request = raw.request && typeof raw.request === "object" ? raw.request : {};
    const rows = Array.isArray(data.rows) ? data.rows : [];
    const selectedSources = Array.isArray(request.selected_sources) ? request.selected_sources : [];
    const bits = [];
    if (rows.length) bits.push(`${rows.length} renamed row${rows.length === 1 ? "" : "s"}`);
    if (selectedSources.length) bits.push(`${selectedSources.length} selected source${selectedSources.length === 1 ? "" : "s"}`);
    if (data.applied_count !== undefined) bits.push(`applied=${data.applied_count}`);
    if (data.skipped_count !== undefined) bits.push(`skipped=${data.skipped_count}`);
    if (data.rollback_performed !== undefined) bits.push(`rollback=${data.rollback_performed ? "yes" : "no"}`);
    if (typeof commandHistoryCompactEvidenceLine === "function") {
      return commandHistoryCompactEvidenceLine(entry, {
        label: "rename.apply",
        detail: bits.length ? ` (${bits.join("; ")})` : "",
      });
    }
    const status = entry?.result || (entry?.ok ? "ok" : entry?.severity || "unknown");
    const local = entry?.local ? "local" : "journal";
    return `${entry?.at || ""} rename.apply [${status}; ${local}] ${entry?.message || ""}${bits.length ? ` (${bits.join("; ")})` : ""}`.trim();
  }

  function renderRenameApplyHistory(history = []) {
    const entries = Array.isArray(history) ? history.filter(isRenameApplyCommand).slice(0, 5) : [];
    if (typeof renderRenameApplyResult === "function") {
      renderRenameApplyResult(entries[0] || null);
    }
    if (!Array.isArray(history) || !history.length) {
      setText("rename-apply-history", "No rename apply command history loaded. Apply a selected rename to see backend results here after refresh.");
      return;
    }
    if (!entries.length) {
      setText("rename-apply-history", "No rename apply commands found in recent command history.");
      return;
    }
    setText("rename-apply-history", [
      `Last ${entries.length} rename apply command${entries.length === 1 ? "" : "s"}:`,
      ...entries.map(renameApplyHistoryLine),
      "Backend rename preview/apply remains the source of truth for filesystem changes.",
    ].join("\n"));
  }

  /**
   * Public namespace for the rename history module.
   * Prefer this namespace from new code; flat window.* exports are transitional compatibility aliases when present.
   */
  window.mediaPipelineRenameHistoryView = {
    isRenameApplyCommand,
    renameApplyHistoryLine,
    renderRenameApplyHistory,
  };
  window.isRenameApplyCommand = isRenameApplyCommand;
  window.renameApplyHistoryLine = renameApplyHistoryLine;
  window.renderRenameApplyHistory = renderRenameApplyHistory;
})();
