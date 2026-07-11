// Queue excluded-source evidence renderer. Loaded before queueView.js.
(function () {
  function createQueueExcludedModule(deps = {}) {
    const byId = typeof deps.byId === "function" ? deps.byId : () => null;
    const setText = typeof deps.setText === "function" ? deps.setText : () => {};
    const clearRows = typeof deps.clearRows === "function" ? deps.clearRows : () => {};
    const updateTableStatusLegend = typeof deps.updateTableStatusLegend === "function" ? deps.updateTableStatusLegend : () => {};
    const appendCells = typeof deps.appendCells === "function" ? deps.appendCells : () => {};
    const makeRowSelectable = typeof deps.makeRowSelectable === "function" ? deps.makeRowSelectable : () => {};
    const queueExcludedStatus = typeof deps.queueExcludedStatus === "function" ? deps.queueExcludedStatus : () => "";
    const queueExcludedSummaryLines = typeof deps.queueExcludedSummaryLines === "function" ? deps.queueExcludedSummaryLines : () => [];
    const queueExcludedRowKey = typeof deps.queueExcludedRowKey === "function" ? deps.queueExcludedRowKey : () => "";
    const selectQueueExcludedRow = typeof deps.selectQueueExcludedRow === "function" ? deps.selectQueueExcludedRow : () => {};
    const getSelectedQueueExcludedRowKey = typeof deps.getSelectedQueueExcludedRowKey === "function" ? deps.getSelectedQueueExcludedRowKey : () => "";
    const document = deps.documentRef || window.document;

  function queueCompactPathText(value, maxChars) {
    const raw = String(value || "");
    const max = Math.max(16, Number(maxChars) || 64);
    if (!raw || raw.length <= max) return raw;
    const endCount = Math.max(8, Math.floor((max - 3) * 0.62));
    const startCount = Math.max(4, max - endCount - 3);
    return `${raw.slice(0, startCount)}...${raw.slice(-endCount)}`;
  }

  function queueExcludedSourceDisplay(sourcePath) {
    const raw = String(sourcePath || "");
    if (!raw) return "";
    const sep = raw.includes("\\") ? "\\" : "/";
    const parts = raw.split(/[\\/]+/).filter(Boolean);
    const filename = parts[parts.length - 1] || raw;
    const parent = parts.length > 1 ? parts[parts.length - 2] : "";
    let root = "";
    if (raw.startsWith("\\\\")) {
      root = parts.length >= 2 ? `\\\\${parts[0]}${sep}${parts[1]}` : "\\\\";
    } else if (/^[A-Za-z]:$/.test(parts[0] || "")) {
      root = parts[0];
    } else if (parts.length > 2 && !raw.startsWith("/")) {
      root = parts[0];
    }
    const prefix = root ? `${root}${sep}...${sep}` : `...${sep}`;
    const parentPrefix = parent && parent !== filename ? `${parent}${sep}` : "";
    const filenameBudget = Math.max(12, 64 - prefix.length - parentPrefix.length);
    const compactFilename = queueCompactPathText(filename, filenameBudget);
    return `${prefix}${parentPrefix}${compactFilename}`;
  }

  function renderQueueExcluded(queue) {
    const payload = queue || {};
    const rows = Array.isArray(payload.excluded_rows) ? payload.excluded_rows : [];
    setText("queue-excluded-status", queueExcludedStatus(payload));
    setText("queue-excluded-summary", queueExcludedSummaryLines(payload).join("\n"));
    const tbody = byId("queue-excluded-rows");
    if (!rows.length) {
      clearRows(tbody, 5, payload.completed_collision_row_level_available ? "No excluded source rows reported." : "Excluded row detail is unavailable until a fresh queue snapshot is emitted.");
      updateTableStatusLegend("queue-excluded-table-legend", tbody, "Excluded rows");
      return;
    }
    tbody.replaceChildren();
    rows.slice(0, 100).forEach((item) => {
      const row = document.createElement("tr");
      const key = queueExcludedRowKey(item);
      row.dataset.rowKey = key;
      const sourcePath = item.source_path || "";
      appendCells(row, [
        item.source_order || "",
        item.media_type || item.media_kind || "",
        item.reason_code || "excluded",
        item.display_name || item.relative_path || "",
        queueExcludedSourceDisplay(sourcePath),
      ], [null, null, null, null, "path-cell"]);
      const cells = row.querySelectorAll("td");
      if (cells[4] && sourcePath) cells[4].title = sourcePath;
      makeRowSelectable(row, () => selectQueueExcludedRow(item), {
        selected: Boolean(key && key === getSelectedQueueExcludedRowKey()),
        label: `Excluded source ${item.display_name || item.relative_path || item.source_path || ""}`,
      });
      tbody.appendChild(row);
    });
    updateTableStatusLegend("queue-excluded-table-legend", tbody, "Excluded rows");
  }


    return { renderQueueExcluded };
  }
  window.__queueExcludedModule = { createQueueExcludedModule };
})();

