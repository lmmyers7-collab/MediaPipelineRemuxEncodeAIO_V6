// Queue priority request and optimistic-display workflow. Loaded before queueView.js.
(function () {
  "use strict";

  function createQueuePriorityModule(deps = {}) {
    const getRows = typeof deps.getRows === "function" ? deps.getRows : () => [];
    const setRows = typeof deps.setRows === "function" ? deps.setRows : () => {};
    const getPayload = typeof deps.getPayload === "function" ? deps.getPayload : () => ({});
    const setPayload = typeof deps.setPayload === "function" ? deps.setPayload : () => {};
    const getExcludedRows = typeof deps.getExcludedRows === "function" ? deps.getExcludedRows : () => [];
    const getScanLoading = typeof deps.getScanLoading === "function" ? deps.getScanLoading : () => false;
    const getSelectedRows = typeof deps.getSelectedRows === "function" ? deps.getSelectedRows : () => [];
    const byId = typeof deps.byId === "function" ? deps.byId : () => null;
    const setText = typeof deps.setText === "function" ? deps.setText : () => {};
    const apiPost = typeof deps.apiPost === "function" ? deps.apiPost : async () => ({});
    const appendCommandResult = typeof deps.appendCommandResult === "function" ? deps.appendCommandResult : () => {};
    const refreshAll = typeof deps.refreshAll === "function" ? deps.refreshAll : async () => {};
    const requestQueueScan = typeof deps.requestQueueScan === "function" ? deps.requestQueueScan : refreshAll;
    const syncSelectedRows = typeof deps.syncSelectedRows === "function" ? deps.syncSelectedRows : () => {};
    const renderSummary = typeof deps.renderSummary === "function" ? deps.renderSummary : () => {};
    const renderBreakdown = typeof deps.renderBreakdown === "function" ? deps.renderBreakdown : () => {};
    const renderRows = typeof deps.renderRows === "function" ? deps.renderRows : () => {};
    const updateManualOrderControls = typeof deps.updateManualOrderControls === "function" ? deps.updateManualOrderControls : () => {};
    const filteredRows = typeof deps.filteredRows === "function" ? deps.filteredRows : () => [];
    const overrideMarkers = deps.overrideMarkers instanceof Map ? deps.overrideMarkers : new Map();
    let inFlight = false;
    let commandSeq = 0;

    function pathKey(value) { return String(value || "").trim().replace(/[\\/]+/g, "\\").toLowerCase(); }
    function normalizedLevel(level) {
      const normalized = String(level || "normal").trim().toLowerCase();
      return ["high", "low", "hold"].includes(normalized) ? normalized : "normal";
    }
    function rowPath(row) { return row ? (row.source_path || row.relative_path || "") : ""; }
    function rowMatchesPath(row, targetKey) {
      return Boolean(targetKey) && [row?.source_path, row?.relative_path].some((value) => pathKey(value) === targetKey);
    }
    function rowHasVisibleMarker(row) {
      const level = normalizedLevel(row?.manifest_priority_level);
      return Boolean(row?.is_priority) || ["high", "low", "hold"].includes(level);
    }
    function displayedFileOverrideMarkerForRow(row) {
      for (const key of [row?.source_path, row?.relative_path].map(pathKey).filter(Boolean)) {
        if (overrideMarkers.has(key)) return overrideMarkers.get(key);
      }
      return null;
    }
    function rowWithDisplayedFileOverrideMarker(row) {
      const marker = displayedFileOverrideMarkerForRow(row);
      if (marker === null) return row;
      const next = { ...row, __queue_has_override: marker, has_file_override: marker };
      if (!marker) {
        next.has_override = false;
        next.file_override = null;
        next.file_override_path = "";
      }
      return next;
    }
    function refreshDisplayedRows() {
      const previous = getPayload() || {};
      const refreshMeta = previous.__mediaPipelineRefreshMeta;
      const rows = getRows();
      const payload = { ...previous, rows, priority_visible_count: rows.filter(rowHasVisibleMarker).length };
      if (refreshMeta) {
        try { Object.defineProperty(payload, "__mediaPipelineRefreshMeta", { value: refreshMeta, enumerable: false, configurable: true }); } catch (_) {}
      }
      setPayload(payload);
      syncSelectedRows(rows, getExcludedRows());
      renderSummary(payload, rows);
      renderBreakdown(payload, rows);
      renderRows();
    }
    function applyDisplayedPriorityUpdates(items) {
      const levelsByPath = new Map();
      (Array.isArray(items) ? items : []).forEach((item) => {
        const key = pathKey(item?.path);
        if (key) levelsByPath.set(key, normalizedLevel(item?.level));
      });
      if (!levelsByPath.size) return false;
      let changed = false;
      const rows = getRows().map((row) => {
        let level = null;
        levelsByPath.forEach((value, key) => { if (level === null && rowMatchesPath(row, key)) level = value; });
        if (level === null) return row;
        changed = true;
        return { ...row, manifest_priority_level: level };
      });
      if (!changed) return false;
      setRows(rows);
      refreshDisplayedRows();
      return true;
    }
    function clearDisplayedPriorityManifest() {
      let changed = false;
      const rows = getRows().map((row) => {
        if (normalizedLevel(row?.manifest_priority_level) === "normal") return row;
        changed = true;
        return { ...row, manifest_priority_level: "normal" };
      });
      if (!changed) return false;
      setRows(rows);
      refreshDisplayedRows();
      return true;
    }
    function applyDisplayedFileOverrideMarker(path, hasOverride) {
      const targetKey = pathKey(path);
      if (!targetKey) return false;
      const marker = Boolean(hasOverride);
      overrideMarkers.set(targetKey, marker);
      let changed = false;
      const rows = getRows().map((row) => {
        if (!rowMatchesPath(row, targetKey)) return row;
        const current = Boolean(row?.__queue_has_override || row?.has_override || row?.has_file_override || row?.file_override || row?.file_override_path);
        if (current === marker && Boolean(row?.__queue_has_override) === marker && Boolean(row?.has_file_override) === marker) return row;
        changed = true;
        const next = { ...row, __queue_has_override: marker, has_file_override: marker };
        if (!marker) { next.has_override = false; next.file_override = null; next.file_override_path = ""; }
        return next;
      });
      if (!changed) return false;
      setRows(rows);
      refreshDisplayedRows();
      return true;
    }
    function controlIds() {
      return ["queue-priority-promote-btn", "queue-priority-normal-btn", "queue-priority-low-btn", "queue-priority-hold-btn", "queue-priority-promote-movies-btn", "queue-priority-promote-tv-btn", "queue-priority-clear-all-btn", "queue-priority-export-btn"];
    }
    function updateControls() {
      const disabled = Boolean(inFlight || getScanLoading());
      controlIds().forEach((id) => { const button = byId(id); if (button) button.disabled = disabled; });
      updateManualOrderControls();
    }
    function beginCommand(message = "") {
      inFlight = true;
      commandSeq += 1;
      if (message) setText("queue-priority-status", message);
      updateControls();
      return commandSeq;
    }
    function isCurrentCommand(seq) { return seq === commandSeq; }
    function endCommand(seq) { if (isCurrentCommand(seq)) inFlight = false; updateControls(); }
    function actionsPausedForScan() {
      if (!getScanLoading()) return false;
      setText("queue-priority-status", "Priority actions are paused while the backend builds a fresh queue preview. The table shows the previous snapshot; retry after the refresh completes.");
      return true;
    }
    async function sendPriority(path, level, reason) {
      if (actionsPausedForScan()) return;
      if (inFlight) { setText("queue-priority-status", "Queue priority command already in progress."); return; }
      if (!path) { setText("queue-priority-status", "No row selected — select a queue row first."); return; }
      const seq = beginCommand("Sending...");
      try {
        const result = await apiPost("/api/queue/priority", { path, level, reason });
        const message = result?.message || `Priority set to '${level}'.`;
        if (isCurrentCommand(seq)) setText("queue-priority-status", message);
        appendCommandResult({ command: "queue.priority", ok: Boolean(result?.ok), severity: result?.ok ? "ok" : "error", message });
        if (result?.ok) applyDisplayedPriorityUpdates([{ path, level }]);
        if (result?.ok) await requestQueueScan();
      } catch (error) { if (isCurrentCommand(seq)) setText("queue-priority-status", `Priority request failed: ${error}`); } finally { endCommand(seq); }
    }
    async function sendPriorityBulk(items, description) {
      if (actionsPausedForScan()) return;
      if (inFlight) { setText("queue-priority-status", "Queue priority command already in progress."); return; }
      if (!items?.length) { setText("queue-priority-status", "No rows to update."); return; }
      const seq = beginCommand(`Updating ${items.length} row(s)...`);
      try {
        const result = await apiPost("/api/queue/priority", { items });
        const message = result?.message || description || "Bulk priority updated.";
        if (isCurrentCommand(seq)) setText("queue-priority-status", message);
        appendCommandResult({ command: "queue.priority", ok: Boolean(result?.ok), severity: result?.ok ? "ok" : "error", message });
        if (result?.ok) applyDisplayedPriorityUpdates(items);
        if (result?.ok) await requestQueueScan();
      } catch (error) { if (isCurrentCommand(seq)) setText("queue-priority-status", `Bulk priority request failed: ${error}`); } finally { endCommand(seq); }
    }
    function priorityItemsForSelected(level, reason) {
      const seen = new Set();
      return getSelectedRows().map((row) => ({ path: rowPath(row), level: normalizedLevel(level), reason: reason || "" })).filter((item) => {
        const key = pathKey(item.path);
        if (!key || seen.has(key)) return false;
        seen.add(key);
        return true;
      });
    }
    function confirmBulk(kindLabel, items) {
      if (!items?.length || typeof window.confirm !== "function") return true;
      const count = filteredRows().filter((row) => String(row.media_type || "").toLowerCase() === String(kindLabel || "").toLowerCase()).length;
      return window.confirm([`Promote ${items.length} loaded ${kindLabel} row(s) to High priority?`, "", `Loaded queue rows: ${getRows().length}.`, `Current display-filter matches for ${kindLabel}: ${count}.`, "This loaded-row action ignores display filters and the table render cap for the selected media kind.", "Backend Launch scope remains unchanged and is still decided by Launch routes.", "This sends a queue-state request only; it does not touch source, scratch, output, or rename files."].join("\n"));
    }
    async function sendSelectedPriority(level, reason) {
      const items = priorityItemsForSelected(level, reason);
      if (!items.length) { setText("queue-priority-status", "No priority rows selected — select one or more queue rows first."); return; }
      if (items.length === 1) return sendPriority(items[0].path, items[0].level, items[0].reason);
      return sendPriorityBulk(items, `Priority set to '${normalizedLevel(level)}' for ${items.length} selected row(s).`);
    }
    function confirmClearManifest() {
      return typeof window.confirm === "function" && window.confirm(["Clear the entire queue priority manifest?", "", "This resets every backend priority override to Normal, including rows hidden by display filters or render caps.", "Backend Launch scope remains unchanged and is still decided by Launch routes.", "This sends a queue-state request only; it does not touch source, scratch, output, or rename files."].join("\n"));
    }
    async function clearPriorityManifest() {
      if (inFlight) { setText("queue-priority-status", "Queue priority command already in progress."); return; }
      if (!confirmClearManifest()) { setText("queue-priority-status", "Priority manifest clear cancelled before any backend request."); return; }
      const seq = beginCommand("Clearing entire priority manifest...");
      try {
        const result = await apiPost("/api/queue/priority", { clear_all: true });
        const message = result?.message || "All priority manifest entries cleared.";
        if (isCurrentCommand(seq)) setText("queue-priority-status", message);
        appendCommandResult({ command: "queue.priority", ok: Boolean(result?.ok), severity: result?.ok ? "ok" : "error", message });
        if (result?.ok) clearDisplayedPriorityManifest();
        if (result?.ok) await requestQueueScan();
      } catch (error) { if (isCurrentCommand(seq)) setText("queue-priority-status", `Priority manifest clear failed: ${error}`); } finally { endCommand(seq); }
    }
    async function exportPriorityQueue() {
      if (actionsPausedForScan()) return;
      if (inFlight) { setText("queue-priority-status", "Queue priority command already in progress."); return; }
      const seq = beginCommand("Preparing a backend-owned priority export...");
      try {
        const result = await apiPost("/api/queue/priority-export", {});
        const data = result?.data && typeof result.data === "object" ? result.data : {};
        const count = Number(data.count || 0);
        const exportId = String(data.export_id || "");
        const message = result?.ok
          ? `Priority export ready: ${count} item${count === 1 ? "" : "s"}. Open Launch and choose Priority Export. Export ID: ${exportId}`
          : result?.message || "Priority export is not ready.";
        if (isCurrentCommand(seq)) setText("queue-priority-status", message);
        appendCommandResult({ command: "queue.priority_export", ok: Boolean(result?.ok), severity: result?.ok ? "ok" : "warning", message });
      } catch (error) {
        if (isCurrentCommand(seq)) setText("queue-priority-status", `Priority export failed: ${error}`);
      } finally {
        endCommand(seq);
      }
    }
    return { applyDisplayedFileOverrideMarker, applyDisplayedPriorityUpdates, beginCommand, clearDisplayedPriorityManifest, confirmBulk, clearPriorityManifest, endCommand, exportPriorityQueue, getInFlight: () => inFlight, isCurrentCommand, normalizedLevel, pathKey, priorityItemsForSelected, refreshDisplayedRows, rowHasVisibleMarker, rowMatchesPath, rowPath, rowWithDisplayedFileOverrideMarker, sendPriority, sendPriorityBulk, sendSelectedPriority, updateControls };
  }
  window.__queuePriorityModule = { createQueuePriorityModule };
})();
