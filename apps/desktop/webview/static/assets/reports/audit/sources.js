// reports/audit/sources.js
// Read-only source-selection state and table rendering for Reports audit locations.
(function () {
  "use strict";

  function createReportsAuditSourcesModule(deps = {}) {
    const reportsState = deps.state && typeof deps.state === "object" ? deps.state : {};
    const byId = typeof deps.byId === "function" ? deps.byId : function () { return null; };
    const renderReportAuditLaunchPreflight = typeof deps.renderReportAuditLaunchPreflight === "function" ? deps.renderReportAuditLaunchPreflight : function () {};
    const removeReportAuditSource = typeof deps.removeReportAuditSource === "function" ? deps.removeReportAuditSource : function () {};
    const scanReportAuditSources = typeof deps.scanReportAuditSources === "function" ? deps.scanReportAuditSources : function () {};
    const setText = typeof deps.setText === "function" ? deps.setText : function () {};
    const startReportAuditFromForm = typeof deps.startReportAuditFromForm === "function" ? deps.startReportAuditFromForm : function () {};
  function reportAuditLocationText(value) {
    return String(value || "").trim();
  }

  function reportAuditLocationKey(value) {
    return reportAuditLocationText(value).replace(/[\\/]+$/g, "").replace(/\//g, "\\").toLowerCase();
  }

  function reportAuditPositiveInteger(value) {
    const numeric = Number(value);
    return Number.isFinite(numeric) ? Math.max(0, Math.round(numeric)) : 0;
  }

  function formatReportAuditSourceTimestamp(value) {
    const raw = reportAuditLocationText(value);
    if (!raw) return "-";
    const parsed = new Date(raw);
    if (Number.isNaN(parsed.getTime())) return raw;
    return parsed.toLocaleString(undefined, {
      year: "numeric",
      month: "short",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  function reportAuditSourceRows(payload = reportsState.lastReportAuditSources) {
    const roots = Array.isArray(payload?.roots) ? payload.roots : [];
    return roots.filter((row) => row && typeof row === "object");
  }

  function reportAuditSourceId(row) {
    return reportAuditLocationText(row?.source_id) || reportAuditLocationKey(row?.path);
  }

  function reportAuditSelectedSourceIds() {
    if (!(reportsState.selectedReportAuditSourceIds instanceof Set)) {
      reportsState.selectedReportAuditSourceIds = new Set();
    }
    return reportsState.selectedReportAuditSourceIds;
  }

  function selectedReportAuditSourceRows() {
    const selectedIds = reportAuditSelectedSourceIds();
    return reportAuditSourceRows().filter((row) => selectedIds.has(reportAuditSourceId(row)));
  }

  function appendReportAuditSourceCell(row, value, className = "") {
    const cell = document.createElement("td");
    cell.textContent = value;
    if (className) cell.className = className;
    row.appendChild(cell);
    return cell;
  }

  function formatReportAuditSourceCount(value, truncated) {
    const numeric = Number(value);
    if (!Number.isFinite(numeric)) return "-";
    return `${truncated ? "~" : ""}${reportAuditPositiveInteger(numeric).toLocaleString()}`;
  }

  function reportAuditSourceStatusLabel(row) {
    const enabled = row?.enabled !== false;
    if (!enabled) return "Disabled";
    const status = String(row?.scan_status || row?.last_scan_status || "not_scanned").toLowerCase();
    if (status === "complete" || status === "completed") return "Complete";
    if (status === "partial") return "Partial";
    if (status === "warning") return "Warning";
    if (status === "unreachable") return "Unavailable";
    if (status === "blocked" || status === "error" || status === "failed") return "Error";
    return "Not scanned";
  }

  function syncReportAuditSelectionWithSources(rows) {
    const selectedIds = reportAuditSelectedSourceIds();
    const availableIds = new Set(rows.map(reportAuditSourceId).filter(Boolean));
    Array.from(selectedIds).forEach((sourceId) => {
      if (!availableIds.has(sourceId)) selectedIds.delete(sourceId);
    });
  }

  function updateReportAuditSourceSelectionStatus(rows = reportAuditSourceRows(), message = "") {
    const selectedRows = selectedReportAuditSourceRows();
    const enabledRows = rows.filter((row) => row?.enabled !== false);
    setText("report-audit-source-status", rows.length ? `${selectedRows.length}/${rows.length} selected` : "No sources");
    setText(
      "report-audit-source-selection-status",
      message || (rows.length
        ? `${selectedRows.length} selected; ${enabledRows.length}/${rows.length} enabled. Start Audit uses selected rows.`
        : "Add a location to scan, then select one or more locations before starting an audit.")
    );
    const hasRows = rows.length > 0;
    const hasSelection = selectedRows.length > 0;
    const scanSelected = byId("report-audit-scan-selected-button");
    if (scanSelected) scanSelected.disabled = reportsState.reportAuditCommandBusy || !hasSelection;
    const scanAll = byId("report-audit-scan-all-button");
    if (scanAll) scanAll.disabled = reportsState.reportAuditCommandBusy || !hasRows;
    const clearSelection = byId("report-audit-clear-source-selection-button");
    if (clearSelection) clearSelection.disabled = !hasSelection;
    renderReportAuditLaunchPreflight();
  }

  function setReportAuditSourceSelection(sourceId, selected) {
    const selectedIds = reportAuditSelectedSourceIds();
    if (selected) selectedIds.add(sourceId);
    else selectedIds.delete(sourceId);
    renderReportAuditSources(reportsState.lastReportAuditSources);
  }

  function selectAllReportAuditSources() {
    const selectedIds = reportAuditSelectedSourceIds();
    reportAuditSourceRows().forEach((row) => {
      if (row?.enabled === false) return;
      const sourceId = reportAuditSourceId(row);
      if (sourceId) selectedIds.add(sourceId);
    });
    renderReportAuditSources(reportsState.lastReportAuditSources);
  }

  function clearReportAuditSourceSelection() {
    reportAuditSelectedSourceIds().clear();
    renderReportAuditSources(reportsState.lastReportAuditSources);
  }

  function selectOnlyReportAuditSource(sourceId) {
    const selectedIds = reportAuditSelectedSourceIds();
    selectedIds.clear();
    if (sourceId) selectedIds.add(sourceId);
    renderReportAuditSources(reportsState.lastReportAuditSources);
  }

  function renderReportAuditSourceRows(rows) {
    const tbody = byId("report-audit-source-rows");
    if (!tbody) return;
    tbody.replaceChildren();
    if (!rows.length) {
      const row = document.createElement("tr");
      appendReportAuditSourceCell(row, "No audit source locations configured. Add a location to scan.", "");
      row.children[0].colSpan = 8;
      tbody.appendChild(row);
      return;
    }
    const selectedIds = reportAuditSelectedSourceIds();
    rows.forEach((source, index) => {
      const row = document.createElement("tr");
      const sourceId = reportAuditSourceId(source);
      const selected = Boolean(sourceId && selectedIds.has(sourceId));
      const enabled = source?.enabled !== false;
      row.dataset.auditSourceRow = sourceId;
      row.classList.toggle("is-selected", selected);
      row.tabIndex = 0;
      row.setAttribute("aria-selected", selected ? "true" : "false");
      row.addEventListener("click", (event) => {
        if (event.target?.closest?.("button,input")) return;
        if (!enabled) return;
        setReportAuditSourceSelection(sourceId, !selectedIds.has(sourceId));
      });
      row.addEventListener("keydown", (event) => {
        if (event.key !== "Enter" && event.key !== " ") return;
        event.preventDefault();
        if (!enabled) return;
        setReportAuditSourceSelection(sourceId, !selectedIds.has(sourceId));
      });

      const selectCell = document.createElement("td");
      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.checked = selected;
      checkbox.disabled = !enabled;
      checkbox.dataset.auditSourceAction = "select";
      checkbox.dataset.auditSourceId = sourceId;
      checkbox.setAttribute("aria-label", `Select audit source ${source.path || index + 1}`);
      checkbox.addEventListener("change", () => setReportAuditSourceSelection(sourceId, checkbox.checked));
      selectCell.appendChild(checkbox);
      row.appendChild(selectCell);

      const pathCell = appendReportAuditSourceCell(row, source.path || "", "path-cell");
      pathCell.title = source.path || "";
      appendReportAuditSourceCell(row, reportAuditSourceStatusLabel(source), "");
      appendReportAuditSourceCell(row, formatReportAuditSourceCount(source.media_file_count, source.counts_truncated), "numeric-cell");
      appendReportAuditSourceCell(row, formatReportAuditSourceCount(source.sidecar_file_count, source.counts_truncated), "numeric-cell");
      appendReportAuditSourceCell(row, formatReportAuditSourceCount(source.folder_count, source.counts_truncated), "numeric-cell");
      appendReportAuditSourceCell(row, formatReportAuditSourceTimestamp(source.last_scan_utc), "");
      const actionCell = document.createElement("td");
      actionCell.className = "report-audit-source-actions";
      const runButton = document.createElement("button");
      runButton.type = "button";
      runButton.className = "secondary-button";
      runButton.dataset.auditSourceAction = "run";
      runButton.dataset.auditSourceId = sourceId;
      runButton.textContent = "Run";
      runButton.disabled = !enabled || reportsState.reportAuditCommandBusy || reportsState.reportAuditStartBusy;
      runButton.addEventListener("click", () => {
        selectOnlyReportAuditSource(sourceId);
        startReportAuditFromForm();
      });
      const scanButton = document.createElement("button");
      scanButton.type = "button";
      scanButton.className = "secondary-button";
      scanButton.dataset.auditSourceAction = "scan";
      scanButton.dataset.auditSourceId = sourceId;
      scanButton.textContent = "Scan";
      scanButton.disabled = !enabled || Boolean(reportsState.reportAuditCommandBusy);
      scanButton.addEventListener("click", () => scanReportAuditSources([sourceId]));
      const removeButton = document.createElement("button");
      removeButton.type = "button";
      removeButton.className = "secondary-button";
      removeButton.dataset.auditSourceAction = "remove";
      removeButton.dataset.auditSourceId = sourceId;
      removeButton.textContent = "Remove";
      removeButton.disabled = Boolean(reportsState.reportAuditCommandBusy);
      removeButton.addEventListener("click", () => removeReportAuditSource(sourceId));
      actionCell.append(runButton, scanButton, removeButton);
      row.appendChild(actionCell);
      ["Select", "Location", "Status", "Video files", "Sidecars", "Folders", "Last scan", "Actions"].forEach((label, cellIndex) => {
        if (row.children[cellIndex]) row.children[cellIndex].dataset.label = label;
      });
      tbody.appendChild(row);
      row.style.setProperty("--audit-source-index", String(index + 1));
    });
  }

  function renderReportAuditSources(payload = reportsState.lastReportAuditSources, message = "") {
    reportsState.lastReportAuditSources = payload && typeof payload === "object" ? payload : {};
    const rows = reportAuditSourceRows();
    syncReportAuditSelectionWithSources(rows);
    renderReportAuditSourceRows(rows);
    updateReportAuditSourceSelectionStatus(rows, message);
  }


    return {
      appendReportAuditSourceCell,
      clearReportAuditSourceSelection,
      formatReportAuditSourceCount,
      formatReportAuditSourceTimestamp,
      renderReportAuditSourceRows,
      renderReportAuditSources,
      reportAuditLocationKey,
      reportAuditLocationText,
      reportAuditPositiveInteger,
      reportAuditSelectedSourceIds,
      reportAuditSourceId,
      reportAuditSourceRows,
      reportAuditSourceStatusLabel,
      selectAllReportAuditSources,
      selectedReportAuditSourceRows,
      selectOnlyReportAuditSource,
      setReportAuditSourceSelection,
      syncReportAuditSelectionWithSources,
      updateReportAuditSourceSelectionStatus,
    };
  }

  window.__reportsAuditSourcesModule = { createReportsAuditSourcesModule };
})();
