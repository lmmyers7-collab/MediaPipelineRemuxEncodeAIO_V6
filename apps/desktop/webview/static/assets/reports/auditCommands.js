// reports/auditCommands.js
// Audit command request, source table, progress, refresh, and result helpers for reportsView.js.

(function () {
  "use strict";

  function noop() {}

  function createReportsAuditCommandsModule(deps = {}) {
    const reportsState = deps.state && typeof deps.state === "object" ? deps.state : {};
    const apiPost = typeof deps.apiPost === "function" ? deps.apiPost : async function () { throw new Error("apiPost unavailable"); };
    const appendCommandResult = typeof deps.appendCommandResult === "function" ? deps.appendCommandResult : null;
    const byId = typeof deps.byId === "function" ? deps.byId : function () { return null; };
    const hiddenAuditSelectionMessage = typeof deps.hiddenAuditSelectionMessage === "function" ? deps.hiddenAuditSelectionMessage : function () { return "Selected audit rows are hidden by the active filter/search."; };
    const hiddenSelectedAuditCount = typeof deps.hiddenSelectedAuditCount === "function" ? deps.hiddenSelectedAuditCount : function () { return 0; };
    const jsonDetailText = typeof deps.jsonDetailText === "function" ? deps.jsonDetailText : null;
    const refreshAll = typeof deps.refreshAll === "function" ? deps.refreshAll : null;
    const renderAuditProgressInto = typeof deps.renderAuditProgressInto === "function" ? deps.renderAuditProgressInto : null;
    const reportAuditCommandButtonIds = Array.isArray(deps.reportAuditCommandButtonIds) ? deps.reportAuditCommandButtonIds : [];
    const reportAuditScoreFieldIds = deps.reportAuditScoreFieldIds && typeof deps.reportAuditScoreFieldIds === "object" ? deps.reportAuditScoreFieldIds : {};
    const reportNumber = typeof deps.reportNumber === "function" ? deps.reportNumber : function (value) { const numeric = Number(value); return Number.isFinite(numeric) ? numeric : 0; };
    const selectedAuditRowKeysList = typeof deps.selectedAuditRowKeysList === "function" ? deps.selectedAuditRowKeysList : function () { return []; };
    const setButtonsBusy = typeof deps.setButtonsBusy === "function" ? deps.setButtonsBusy : noop;
    const setText = typeof deps.setText === "function" ? deps.setText : noop;
    const REPORT_AUDIT_POST_START_REFRESH_DELAYS_MS = [1000, 3000, 7000, 15000, 30000];
    const REPORT_AUDIT_BACKEND_ACTIVE_FRESH_MS = 10 * 60 * 1000;

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

  function formatReportAuditElapsed(startedAtMs) {
    const timestamp = Number(startedAtMs || 0);
    const elapsedSeconds = Math.max(0, Math.floor((Date.now() - timestamp) / 1000));
    const hours = Math.floor(elapsedSeconds / 3600);
    const minutes = Math.floor((elapsedSeconds % 3600) / 60);
    const seconds = elapsedSeconds % 60;
    const minuteText = hours ? String(minutes).padStart(2, "0") : String(minutes);
    return `${hours ? `${hours}:` : ""}${minuteText}:${String(seconds).padStart(2, "0")}`;
  }

  function parseReportAuditTimestamp(value) {
    if (!value) return 0;
    const timestamp = Date.parse(String(value));
    return Number.isFinite(timestamp) ? timestamp : 0;
  }

  function reportAuditProgressPayload(snapshot = {}) {
    return snapshot?.audit_progress && typeof snapshot.audit_progress === "object" ? snapshot.audit_progress : {};
  }

  function reportAuditProgressBars(snapshot = {}) {
    const bars = Array.isArray(snapshot?.progress_bars) ? snapshot.progress_bars : [];
    return bars.filter((bar) => {
      const id = String(bar?.id || "").toLowerCase();
      const source = String(bar?.source || "").toLowerCase();
      return id === "audit_progress" || id === "audit_reports" || source.includes("audit_progress");
    });
  }

  function reportAuditProgressIsTerminal(snapshot = {}) {
    const auditProgress = reportAuditProgressPayload(snapshot);
    if (auditProgress.completed === true || auditProgress.failed === true) return true;
    const status = String(auditProgress.status || auditProgress.Status || "").toLowerCase();
    if (["completed", "complete", "failed", "error", "blocked", "stopped"].includes(status)) return true;
    const statuses = reportAuditProgressBars(snapshot).map((bar) => String(bar?.status || "").toLowerCase());
    if (statuses.some((item) => ["blocked", "error", "failed"].includes(item))) return true;
    return Boolean(statuses.length) && statuses.every((item) => item === "complete");
  }

  function reportAuditProgressSucceeded(snapshot = {}) {
    const auditProgress = reportAuditProgressPayload(snapshot);
    if (auditProgress.failed === true || auditProgress.Failed === true) return false;
    if (auditProgress.completed === true || auditProgress.Completed === true) return true;
    const status = String(auditProgress.status || auditProgress.Status || "").toLowerCase();
    return status === "completed" || status === "complete";
  }

  function reportAuditPriorityCsvPath(snapshot = {}) {
    const auditProgress = reportAuditProgressPayload(snapshot);
    return String(auditProgress.latest_priority_csv_path || auditProgress.LatestPriorityCsvPath || "").trim();
  }

  function selectReportAuditPriorityTable(snapshot = {}) {
    if (!reportAuditProgressSucceeded(snapshot)) return false;
    const priorityCsvPath = reportAuditPriorityCsvPath(snapshot);
    if (!priorityCsvPath) return false;
    if (reportsState.reportAuditAutoPriorityCsvPath === priorityCsvPath) return false;
    reportsState.reportAuditAutoPriorityCsvPath = priorityCsvPath;
    const priorityOnly = byId("audit-preview-priority-only");
    if (!priorityOnly || priorityOnly.checked) return false;
    priorityOnly.checked = true;
    window.setTimeout(() => {
      const refresh = typeof window.refreshAll === "function" ? window.refreshAll : refreshAll;
      if (typeof refresh === "function") refresh({ automatic: true });
    }, 0);
    return true;
  }

  function reportAuditProgressIsActive(snapshot = {}) {
    if (reportAuditProgressIsTerminal(snapshot)) return false;
    const auditProgress = reportAuditProgressPayload(snapshot);
    const status = String(auditProgress.status || auditProgress.Status || "").toLowerCase();
    if (["starting", "scanning", "writing-reports", "running", "active", "audit", "auditing"].includes(status)) return true;
    return reportAuditProgressBars(snapshot).some((bar) => ["active", "running", "warning"].includes(String(bar?.status || "").toLowerCase()));
  }

  function reportAuditAcceptedRunEvidence() {
    if (!reportsState.reportAuditAcceptedRun) return null;
    const startedAtMs = Number(reportsState.reportAuditAcceptedRun.startedAtMs || 0);
    if (!startedAtMs) return null;
    const request = reportsState.reportAuditAcceptedRun.request && typeof reportsState.reportAuditAcceptedRun.request === "object" ? reportsState.reportAuditAcceptedRun.request : {};
    const result = reportsState.reportAuditAcceptedRun.result && typeof reportsState.reportAuditAcceptedRun.result === "object" ? reportsState.reportAuditAcceptedRun.result : {};
    const data = result.data && typeof result.data === "object" ? result.data : {};
    return {
      startedAtMs,
      elapsed: formatReportAuditElapsed(startedAtMs),
      pid: data.pid || "",
      libraryRoot: data.library_root || request.library_root || "",
      libraryRoots: Array.isArray(data.library_roots) ? data.library_roots : Array.isArray(request.library_roots) ? request.library_roots : [],
      includeSidecars: data.include_sidecars ?? request.include_sidecars,
      result,
      request,
    };
  }

  function reportAuditSnapshotTimestampMs(snapshot = {}) {
    const auditProgress = reportAuditProgressPayload(snapshot);
    const timestamps = [
      auditProgress.started_at,
      auditProgress.StartedAt,
      auditProgress.last_update,
      auditProgress.LastUpdate,
      auditProgress.updated_at,
      ...reportAuditProgressBars(snapshot).map((bar) => bar?.updated_at),
    ].map(parseReportAuditTimestamp).filter((value) => value > 0);
    return timestamps.length ? Math.max(...timestamps) : 0;
  }

  function reportAuditSnapshotCoversAcceptedRun(snapshot = {}) {
    const evidence = reportAuditAcceptedRunEvidence();
    if (!evidence) return true;
    const snapshotTimestamp = reportAuditSnapshotTimestampMs(snapshot);
    return Boolean(snapshotTimestamp && snapshotTimestamp >= evidence.startedAtMs - 2000);
  }

  function reportAuditSnapshotIsFreshForUi(snapshot = {}) {
    const timestamp = reportAuditSnapshotTimestampMs(snapshot);
    if (!timestamp) return false;
    return Date.now() - timestamp <= REPORT_AUDIT_BACKEND_ACTIVE_FRESH_MS;
  }

  function reportAuditActiveWorkerRows(snapshot = {}) {
    const rows = Array.isArray(snapshot?.worker_progress?.rows) ? snapshot.worker_progress.rows : [];
    return rows.filter((row) => {
      const kind = String(row?.job_kind || row?.kind || "").trim().replace(/-/g, "_").toLowerCase();
      if (kind !== "audit") return false;
      if (row?.stale === true) return false;
      const state = String(row?.status_state || row?.status || "").toLowerCase();
      const status = String(row?.status || row?.stage || "").toLowerCase();
      return /running|active|launching|scanning/.test(`${state} ${status}`);
    });
  }

  function reportAuditHasBackendActiveRunEvidence(snapshot = {}) {
    return reportAuditActiveWorkerRows(snapshot).length > 0;
  }

  function reportAuditSnapshotRunEvidence(snapshot = {}, { requireFresh = true } = {}) {
    if (!reportAuditProgressIsActive(snapshot)) return null;
    const fresh = reportAuditSnapshotIsFreshForUi(snapshot);
    if (requireFresh && !fresh) return null;
    const auditProgress = reportAuditProgressPayload(snapshot);
    const startedAtMs = parseReportAuditTimestamp(auditProgress.started_at || auditProgress.StartedAt)
      || reportAuditSnapshotTimestampMs(snapshot)
      || Date.now();
    return {
      startedAtMs,
      elapsed: formatReportAuditElapsed(startedAtMs),
      pid: "",
      libraryRoot: auditProgress.library_root || auditProgress.LibraryRoot || "",
      libraryRoots: Array.isArray(auditProgress.library_roots) ? auditProgress.library_roots : [],
      includeSidecars: auditProgress.include_sidecars ?? auditProgress.IncludeSidecars,
      result: null,
      request: null,
      stale: !fresh,
      backendActive: reportAuditHasBackendActiveRunEvidence(snapshot),
    };
  }

  function reportAuditStaleProgressEvidence(snapshot = {}) {
    if (!reportAuditProgressIsActive(snapshot)) return null;
    if (reportAuditProgressIsTerminal(snapshot)) return null;
    if (reportAuditSnapshotIsFreshForUi(snapshot)) return null;
    const timestamp = reportAuditSnapshotTimestampMs(snapshot);
    if (!timestamp) return null;
    const auditProgress = reportAuditProgressPayload(snapshot);
    return {
      elapsed: formatReportAuditElapsed(timestamp),
      libraryRoot: auditProgress.library_root || auditProgress.LibraryRoot || "",
      libraryRoots: Array.isArray(auditProgress.library_roots) ? auditProgress.library_roots : [],
      timestamp,
    };
  }

  function reportAuditCurrentRunEvidence(snapshot = reportsState.lastReportSnapshot) {
    const accepted = reportAuditAcceptedRunEvidence();
    if (accepted) {
      if (reportAuditProgressIsTerminal(snapshot || {}) && reportAuditSnapshotCoversAcceptedRun(snapshot || {})) return null;
      return accepted;
    }
    if (reportAuditProgressIsTerminal(snapshot || {})) return null;
    return reportAuditSnapshotRunEvidence(snapshot || {}, {
      requireFresh: !reportAuditHasBackendActiveRunEvidence(snapshot || {}),
    });
  }

  function reportAuditSyntheticSnapshot(snapshot = {}) {
    const evidence = reportAuditCurrentRunEvidence(snapshot);
    const accepted = reportAuditAcceptedRunEvidence();
    const existingAuditBarsAreCurrent = reportAuditProgressBars(snapshot).length
      && (!accepted || reportAuditSnapshotCoversAcceptedRun(snapshot || {}));
    if (!evidence || existingAuditBarsAreCurrent) return snapshot || {};
    const base = snapshot && typeof snapshot === "object" ? { ...snapshot } : {};
    const useExistingAuditProgress = !accepted || reportAuditSnapshotCoversAcceptedRun(snapshot || {});
    base.audit_progress = useExistingAuditProgress && Object.keys(reportAuditProgressPayload(base)).length
      ? reportAuditProgressPayload(base)
      : {
          status: "starting",
          completed: false,
          failed: false,
          processed_files: 0,
          total_files: 0,
          percent_complete: 0,
          started_at: new Date(evidence.startedAtMs).toISOString(),
          current_operation: "Backend accepted audit start; waiting for audit_progress.json.",
          library_root: evidence.libraryRoot,
          library_roots: evidence.libraryRoots || [],
          include_sidecars: Boolean(evidence.includeSidecars),
        };
    base.progress_bars = [
      ...(Array.isArray(base.progress_bars)
        ? base.progress_bars.filter((bar) => !reportAuditProgressBars({ progress_bars: [bar] }).length)
        : []),
      {
        id: "audit_progress",
        label: "Audit running",
        mode: "indeterminate",
        percent: null,
        status: "active",
        detail: `elapsed ${evidence.elapsed} | waiting for audit_progress.json | ETA unavailable until backend progress reports file count`,
        source: "local audit_progress launch state",
        updated_at: "",
      },
    ];
    return base;
  }

  function clearReportAuditRefreshTimers() {
    reportsState.reportAuditRefreshTimerIds.forEach((timerId) => window.clearTimeout(timerId));
    reportsState.reportAuditRefreshTimerIds = [];
  }

  function scheduleReportAuditRefreshes() {
    clearReportAuditRefreshTimers();
    reportsState.reportAuditRefreshTimerIds = REPORT_AUDIT_POST_START_REFRESH_DELAYS_MS.map((delayMs) => window.setTimeout(() => {
      if (!reportsState.reportAuditAcceptedRun) return;
      const refresh = window.refreshAll;
      if (typeof refresh === "function") refresh({ automatic: true });
    }, delayMs));
  }

  function stopReportAuditTimerIfIdle(snapshot = reportsState.lastReportSnapshot) {
    if (reportAuditCurrentRunEvidence(snapshot)) return;
    if (!reportsState.reportAuditTimerId) return;
    window.clearInterval(reportsState.reportAuditTimerId);
    reportsState.reportAuditTimerId = 0;
  }

  function ensureReportAuditTimer() {
    if (reportsState.reportAuditTimerId) return;
    reportsState.reportAuditTimerId = window.setInterval(() => {
      renderReportAuditRunningState(reportsState.lastReportSnapshot);
    }, 1000);
  }

  function updateReportAuditStartButtonState(snapshot = reportsState.lastReportSnapshot) {
    const button = byId("report-audit-start-button");
    const stopButton = byId("report-audit-stop-button");
    const evidence = reportAuditCurrentRunEvidence(snapshot || {});
    const hasSelectedSources = selectedReportAuditSourceRows().length > 0;
    const disabled = reportsState.reportAuditStartBusy || Boolean(reportsState.reportAuditCommandBusy) || Boolean(evidence) || !hasSelectedSources;
    if (button) {
      button.disabled = disabled;
      button.setAttribute("aria-busy", String(Boolean(reportsState.reportAuditStartBusy || evidence)));
      button.textContent = evidence ? "Audit Running" : "Start Audit Selected";
      button.title = hasSelectedSources
        ? "Start an audit for the selected Locations table rows."
        : "Select one or more Locations table rows before starting an audit.";
    }
    if (stopButton) {
      const stopBusy = reportsState.reportAuditCommandBusy === "audit.stop";
      stopButton.disabled = reportsState.reportAuditStartBusy || Boolean(reportsState.reportAuditCommandBusy) || !evidence;
      stopButton.setAttribute("aria-busy", String(stopBusy));
      stopButton.textContent = stopBusy ? "Stopping..." : "Stop Audit";
    }
  }

  function renderReportAuditProgressPanel(snapshot = reportsState.lastReportSnapshot) {
    if (typeof renderAuditProgressInto === "function") renderAuditProgressInto({
      containerId: "report-progress-bars",
      statusId: "report-progress-status",
      summaryId: "report-progress-summary",
      snapshot: reportAuditSyntheticSnapshot(snapshot || {}),
      emptyText: "No audit report progress loaded.",
    });
  }

  function renderReportAuditRunningState(snapshot = reportsState.lastReportSnapshot) {
    if (reportAuditProgressIsTerminal(snapshot || {}) && reportAuditSnapshotCoversAcceptedRun(snapshot || {})) {
      const priorityTableSelected = selectReportAuditPriorityTable(snapshot || {});
      reportsState.reportAuditAcceptedRun = null;
      clearReportAuditRefreshTimers();
      if (reportAuditProgressSucceeded(snapshot || {})) {
        const priorityCsvPath = reportAuditPriorityCsvPath(snapshot || {});
        setText("report-audit-launch-status", "Completed");
        setText(
          "report-audit-launch-detail",
          priorityCsvPath
            ? (priorityTableSelected
              ? `Audit completed. Loaded priority table from ${priorityCsvPath}.`
              : `Audit completed. Priority table is already selected from ${priorityCsvPath}.`)
            : "Audit completed. No priority table was generated for this audit.",
        );
      }
    }
    const evidence = reportAuditCurrentRunEvidence(snapshot || {});
    if (evidence) {
      setText("report-audit-launch-status", `${evidence.stale ? "Stale" : "Running"} ${evidence.elapsed}`);
      const result = evidence.result || {
        command: "audit.start",
        ok: true,
        severity: "info",
        message: evidence.stale
          ? "Audit process evidence is active, but audit progress is stale in the backend snapshot."
          : "Audit progress is active in the backend snapshot.",
      };
      const request = evidence.request || collectReportAuditStartRequest();
      setText("report-audit-launch-detail", [
        formatReportAuditCommandDetail(result, request),
        "",
        `Running indicator: ${evidence.stale ? "stale active" : "active"}`,
        `Elapsed: ${evidence.elapsed}`,
        `PID: ${evidence.pid || "not reported"}`,
        `Locations: ${(evidence.libraryRoots || request.library_roots || []).length || 1}`,
        `Primary location: ${evidence.libraryRoot || request.library_root || "(backend configured Outsource fallback)"}`,
        "ETA: unavailable until backend audit progress reports file count and elapsed evidence.",
        `Progress source: backend audit_progress.json when present; otherwise local accepted-start state.${evidence.stale ? " Snapshot is stale." : ""}`,
      ].join("\n"));
      renderReportAuditProgressPanel(snapshot || {});
      ensureReportAuditTimer();
    } else {
      const staleProgress = reportAuditStaleProgressEvidence(snapshot || {});
      if (staleProgress) {
        setText("report-audit-launch-status", `Review ${staleProgress.elapsed}`);
        const result = {
          command: "audit.status",
          ok: true,
          severity: "warning",
          message: "Audit progress is stale and no active audit process is visible in the backend snapshot.",
        };
        const request = collectReportAuditStartRequest();
        setText("report-audit-launch-detail", [
          formatReportAuditCommandDetail(result, request),
          "",
          "Running indicator: stale progress only",
          `Last progress update age: ${staleProgress.elapsed}`,
          `Locations: ${(staleProgress.libraryRoots || []).length || 1}`,
          `Primary location: ${staleProgress.libraryRoot || request.library_root || "(backend configured Outsource fallback)"}`,
          "Stop Audit is unavailable until backend active-run evidence appears.",
          "Safe action: refresh Reports, inspect ActiveJobs if close-readiness blocks, or start a new audit when ready.",
        ].join("\n"));
      }
      stopReportAuditTimerIfIdle(snapshot || {});
    }
    updateReportAuditStartButtonState(snapshot || {});
  }

  function setReportAuditCommandBusy(command, activeId = "") {
    reportsState.reportAuditCommandBusy = command || "";
    setButtonsBusy(reportAuditCommandButtonIds, Boolean(reportsState.reportAuditCommandBusy), activeId);
    updateReportAuditStartButtonState();
  }

  function reportAuditBusyResult(command) {
    return {
      command,
      ok: false,
      severity: "warning",
      message: `Another Reports audit command is already in progress: ${reportsState.reportAuditCommandBusy}.`,
    };
  }
  function reportAuditReviewCount() {
    const actionableCount = reportsState.lastAuditPreviewPayload?.actionable_count;
    if (actionableCount !== undefined && actionableCount !== null) {
      return reportNumber(actionableCount);
    }
    return reportNumber(reportsState.lastAuditPreviewPayload?.redownload_count)
      + reportNumber(reportsState.lastAuditPreviewPayload?.rerun_count)
      + reportNumber(reportsState.lastAuditPreviewPayload?.priority_count ?? reportsState.lastAuditPreviewPayload?.high_priority_count);
  }

  function collectReportAuditScorePolicyForm() {
    const policy = {};
    Object.entries(reportAuditScoreFieldIds).forEach(([key, id]) => {
      const raw = Number(byId(id)?.value);
      policy[key] = Number.isFinite(raw) ? Math.max(0, Math.min(1000, Math.round(raw))) : 0;
    });
    policy.issue_code_weights = {};
    const details = byId("report-audit-score-redownload-bucket")?.closest("details");
    const issueInputs = details ? Array.from(details.querySelectorAll("[data-audit-score-issue-code]")) : [];
    issueInputs.forEach((input) => {
      const code = String(input.dataset.auditScoreIssueCode || "").trim();
      if (!code) return;
      const raw = Number(input.value);
      policy.issue_code_weights[code] = Number.isFinite(raw) ? Math.max(0, Math.min(1000, Math.round(raw))) : 0;
    });
    return policy;
  }

  async function refreshReportsAuditData() {
    const refresh = typeof window.refreshAll === "function" ? window.refreshAll : refreshAll;
    if (typeof refresh === "function") {
      await refresh();
    }
  }

  function collectReportAuditStartRequest() {
    const selectedRows = selectedReportAuditSourceRows();
    const selectedRoots = selectedRows.map((row) => reportAuditLocationText(row.path)).filter(Boolean);
    const sourceIds = selectedRows.map(reportAuditSourceId).filter(Boolean);
    const libraryRoots = selectedRoots;
    return {
      library_root: libraryRoots[0] || "",
      library_roots: libraryRoots,
      source_ids: sourceIds,
      include_sidecars: Boolean(byId("report-audit-start-include-sidecars")?.checked),
      show_console: Boolean(byId("report-audit-start-show-console")?.checked),
    };
  }

  function reportAuditLaunchPreflightLines(request = collectReportAuditStartRequest()) {
    const roots = Array.isArray(request.library_roots) ? request.library_roots.filter(Boolean) : [];
    const typedRoot = reportAuditLocationText(byId("report-audit-start-library-root")?.value);
    const typedRootIsSelected = Boolean(typedRoot && roots.some((root) => reportAuditLocationKey(root) === reportAuditLocationKey(typedRoot)));
    const lines = [
      "Reports audit start request:",
      `Selected table locations: ${roots.length}`,
      typedRoot
        ? `Typed location: ${typedRoot}${typedRootIsSelected ? "" : " (not in the table selection)"}`
        : "Typed location: none",
      `Primary location: ${request.library_root || "(none selected)"}`,
      `Include sidecars: ${request.include_sidecars ? "yes" : "no"}`,
      `Show console: ${request.show_console ? "yes" : "no"}`,
      ...roots.slice(0, 5).map((root, index) => `Location ${index + 1}: ${root}`),
      ...(roots.length > 5 ? [`Additional locations: ${roots.length - 5}`] : []),
      ...(!roots.length ? ["Add Source to put the typed location in the Locations table, then select it before starting an audit."] : []),
      "Readiness preview: informational only; this is not a backend dry-run.",
      "Boundary: Reports submits /api/audit/start only after confirmation. Backend launch locking, config identity, duplicate-audit detection, and audit/pipeline concurrency policy remain authoritative.",
      "Concurrency: an active backend pipeline does not by itself block audit start; an active audit or CSV rerun still blocks this request.",
    ];
    return lines;
  }

  function renderReportAuditLaunchPreflight(request = collectReportAuditStartRequest()) {
    setText("report-audit-launch-preflight", reportAuditLaunchPreflightLines(request).join("\n"));
    updateReportAuditStartButtonState();
  }

  function renderReportAuditSourceCommandResult(result, request) {
    setText("report-audit-launch-status", result?.ok ? "Updated" : "Blocked");
    setText("report-audit-launch-detail", formatReportAuditCommandDetail(result, request));
    const auditSources = result?.data?.audit_sources;
    if (auditSources && typeof auditSources === "object") {
      renderReportAuditSources(auditSources, result?.message || "");
    } else if (result?.ok === false) {
      updateReportAuditSourceSelectionStatus(
        reportAuditSourceRows(),
        result?.message || "Audit source command failed."
      );
    }
  }

  async function addReportAuditSourceFromForm() {
    if (reportsState.reportAuditCommandBusy) {
      const result = reportAuditBusyResult("audit.sources");
      appendReportAuditCommandResult(result);
      renderReportAuditSourceCommandResult(result, null);
      return;
    }
    const path = reportAuditLocationText(byId("report-audit-start-library-root")?.value);
    if (!path) {
      const result = {
        command: "audit.sources",
        ok: false,
        severity: "warning",
        message: "Enter a location before adding an audit source.",
      };
      appendReportAuditCommandResult(result);
      renderReportAuditSourceCommandResult(result, { action: "add", path });
      return;
    }
    const request = { action: "add", path, enabled: true };
    setReportAuditCommandBusy("audit.sources", "report-audit-add-source-button");
    setText("report-audit-launch-status", "Adding...");
    setText("report-audit-launch-detail", "Adding backend-owned audit source...");
    try {
      const result = await apiPost("/api/audit/sources", request, { timeoutMs: 15000 });
      appendReportAuditCommandResult(result);
      const auditSources = result?.data?.audit_sources;
      const added = reportAuditSourceRows(auditSources).find((row) => reportAuditLocationKey(row.path) === reportAuditLocationKey(path));
      const addedId = reportAuditSourceId(added);
      if (result.ok && addedId) reportAuditSelectedSourceIds().add(addedId);
      renderReportAuditSourceCommandResult(result, request);
      await refreshReportsAuditData();
    } catch (error) {
      const text = error instanceof Error ? error.message : String(error);
      const result = { command: "audit.sources", ok: false, severity: "error", message: text };
      appendReportAuditCommandResult(result);
      renderReportAuditSourceCommandResult(result, request);
    } finally {
      setReportAuditCommandBusy("");
    }
  }

  async function removeReportAuditSource(sourceId) {
    if (reportsState.reportAuditCommandBusy) {
      const result = reportAuditBusyResult("audit.sources");
      appendReportAuditCommandResult(result);
      renderReportAuditSourceCommandResult(result, null);
      return;
    }
    const source = reportAuditSourceRows().find((row) => reportAuditSourceId(row) === sourceId);
    if (!source) return;
    if (!window.confirm(`Remove audit source?\n\n${source.path || source.label || sourceId}`)) return;
    const request = { action: "remove", source_id: sourceId };
    setReportAuditCommandBusy("audit.sources");
    setText("report-audit-launch-status", "Removing...");
    setText("report-audit-launch-detail", "Removing backend-owned audit source...");
    try {
      const result = await apiPost("/api/audit/sources", request, { timeoutMs: 15000 });
      appendReportAuditCommandResult(result);
      reportAuditSelectedSourceIds().delete(sourceId);
      renderReportAuditSourceCommandResult(result, request);
      await refreshReportsAuditData();
    } catch (error) {
      const text = error instanceof Error ? error.message : String(error);
      const result = { command: "audit.sources", ok: false, severity: "error", message: text };
      appendReportAuditCommandResult(result);
      renderReportAuditSourceCommandResult(result, request);
    } finally {
      setReportAuditCommandBusy("");
    }
  }

  async function scanReportAuditSources(sourceIds = null) {
    if (reportsState.reportAuditCommandBusy) {
      const result = reportAuditBusyResult("audit.sources.scan");
      appendReportAuditCommandResult(result);
      renderReportAuditSourceCommandResult(result, null);
      return;
    }
    const selectedIds = Array.isArray(sourceIds)
      ? sourceIds.filter(Boolean)
      : Array.from(reportAuditSelectedSourceIds()).filter(Boolean);
    const request = selectedIds.length ? { source_ids: selectedIds } : { scope: "all" };
    const scopeText = selectedIds.length ? `${selectedIds.length} selected source(s)` : "all audit sources";
    if (!window.confirm(`Scan ${scopeText} for media, sidecars, and folders?`)) return;
    setReportAuditCommandBusy("audit.sources.scan", selectedIds.length ? "report-audit-scan-selected-button" : "report-audit-scan-all-button");
    setText("report-audit-launch-status", "Scanning...");
    setText("report-audit-launch-detail", `Scanning ${scopeText}...`);
    try {
      const result = await apiPost("/api/audit/sources/scan", request, { timeoutMs: 0 });
      appendReportAuditCommandResult(result);
      renderReportAuditSourceCommandResult(result, request);
      await refreshReportsAuditData();
    } catch (error) {
      const text = error instanceof Error ? error.message : String(error);
      const result = { command: "audit.sources.scan", ok: false, severity: "error", message: text };
      appendReportAuditCommandResult(result);
      renderReportAuditSourceCommandResult(result, request);
    } finally {
      setReportAuditCommandBusy("");
    }
  }

  function reportAuditSelectionRequest() {
    return {
      row_keys: selectedAuditRowKeysList(),
      priority_only: Boolean(reportsState.lastAuditPreviewPayload.priority_only),
      limit: 100,
    };
  }

  function appendReportAuditCommandResult(result) {
    if (typeof appendCommandResult === "function") appendCommandResult(result);
  }

  function reportAuditJsonDetail(label, value, intro) {
    if (typeof jsonDetailText === "function") {
      return jsonDetailText({ label, value, intro });
    }
    try {
      return JSON.stringify(value, null, 2);
    } catch (_) {
      return String(value || "");
    }
  }

  function formatReportAuditCommandDetail(result, request = null) {
    const payload = result && typeof result === "object" ? result : {
      ok: false,
      severity: "error",
      message: String(result || "Unknown command result."),
    };
    const lines = [
      `Command: ${payload.command || "unknown"}`,
      `Result: ${payload.ok ? "ok" : "blocked"}${payload.severity ? ` (${payload.severity})` : ""}`,
    ];
    const displayFormatter = window.commandResultDisplayMessage;
    const displayMessage = typeof displayFormatter === "function"
      ? displayFormatter(payload)
      : String(payload.message || "");
    if (displayMessage) {
      lines.push("", displayMessage);
    }
    if (payload.refresh_hint) {
      lines.push("", `Refresh hint: ${payload.refresh_hint}`);
    }
    if (payload.data && Object.keys(payload.data).length) {
      lines.push("", "Backend data:", reportAuditJsonDetail(
        "Backend data JSON",
        payload.data,
        "Read-only backend command result data."
      ));
    }
    if (request) {
      lines.push("", "Submitted request:", reportAuditJsonDetail(
        "Submitted request JSON",
        request,
        "Read-only request payload submitted to the backend command route."
      ));
    }
    return lines.join("\n");
  }

  async function startReportAuditFromForm() {
    if (reportsState.reportAuditStartBusy || reportsState.reportAuditCommandBusy) {
      const result = reportAuditBusyResult("audit.start");
      appendReportAuditCommandResult(result);
      setText("report-audit-launch-status", "Busy");
      setText("report-audit-launch-detail", formatReportAuditCommandDetail(result));
      return;
    }
    const request = collectReportAuditStartRequest();
    renderReportAuditLaunchPreflight(request);
    const rootCount = Array.isArray(request.library_roots) ? request.library_roots.length : 0;
    if (!rootCount) {
      const result = {
        command: "audit.start",
        ok: false,
        severity: "warning",
        message: "Select one or more locations in the Locations table before starting an audit. Use Add Source to create a table row from the typed Location to Scan.",
      };
      appendReportAuditCommandResult(result);
      setText("report-audit-launch-status", "Select location");
      setText("report-audit-launch-detail", formatReportAuditCommandDetail(result, request));
      updateReportAuditStartButtonState();
      return;
    }
    if (!window.confirm(`Start audit for ${rootCount} location${rootCount === 1 ? "" : "s"} from Reports?`)) {
      const result = {
        command: "audit.start",
        ok: false,
        severity: "info",
        message: "Audit start canceled.",
      };
      appendReportAuditCommandResult(result);
      setText("report-audit-launch-status", "Canceled");
      setText("report-audit-launch-detail", formatReportAuditCommandDetail(result, request));
      return;
    }
    reportsState.reportAuditStartBusy = true;
    reportsState.reportAuditAutoPriorityCsvPath = "";
    setReportAuditCommandBusy("audit.start", "report-audit-start-button");
    setText("report-audit-launch-status", "Starting...");
    setText("report-audit-launch-detail", formatReportAuditCommandDetail({
      command: "audit.start",
      ok: true,
      severity: "info",
      message: "Submitting backend audit start request.",
    }, request));
    try {
      const result = await apiPost("/api/audit/start", request);
      appendReportAuditCommandResult(result);
      if (result.ok) {
        reportsState.reportAuditAcceptedRun = {
          startedAtMs: Date.now(),
          request,
          result,
        };
        scheduleReportAuditRefreshes();
        renderReportAuditRunningState(reportsState.lastReportSnapshot);
      } else {
        reportsState.reportAuditAcceptedRun = null;
        setText("report-audit-launch-status", "Blocked");
        setText("report-audit-launch-detail", formatReportAuditCommandDetail(result, request));
        updateReportAuditStartButtonState();
      }
      if ((result.refresh_hint || "") === "snapshot") {
        await refreshReportsAuditData();
      }
    } catch (error) {
      const text = error instanceof Error ? error.message : String(error);
      const result = { command: "audit.start", ok: false, severity: "error", message: text };
      appendReportAuditCommandResult(result);
      reportsState.reportAuditAcceptedRun = null;
      setText("report-audit-launch-status", "Error");
      setText("report-audit-launch-detail", formatReportAuditCommandDetail(result, request));
    } finally {
      reportsState.reportAuditStartBusy = false;
      setReportAuditCommandBusy("");
      renderReportAuditRunningState(reportsState.lastReportSnapshot);
    }
  }

  async function stopReportAuditFromForm() {
    if (reportsState.reportAuditStartBusy || reportsState.reportAuditCommandBusy) {
      const result = reportAuditBusyResult("audit.stop");
      appendReportAuditCommandResult(result);
      setText("report-audit-launch-status", "Busy");
      setText("report-audit-launch-detail", formatReportAuditCommandDetail(result));
      return;
    }
    const evidence = reportAuditCurrentRunEvidence(reportsState.lastReportSnapshot);
    const request = {
      confirm_stop: true,
      reason: "Reports Stop Audit button",
    };
    if (!evidence) {
      const result = {
        command: "audit.stop",
        ok: false,
        severity: "warning",
        message: "No active audit run is visible to stop.",
      };
      appendReportAuditCommandResult(result);
      setText("report-audit-launch-status", "Idle");
      setText("report-audit-launch-detail", formatReportAuditCommandDetail(result, request));
      updateReportAuditStartButtonState();
      return;
    }
    if (!window.confirm("Stop the active audit from Reports?")) {
      const result = {
        command: "audit.stop",
        ok: false,
        severity: "info",
        message: "Audit stop canceled.",
      };
      appendReportAuditCommandResult(result);
      setText("report-audit-launch-status", "Running");
      setText("report-audit-launch-detail", formatReportAuditCommandDetail(result, request));
      updateReportAuditStartButtonState();
      return;
    }
    setReportAuditCommandBusy("audit.stop", "report-audit-stop-button");
    setText("report-audit-launch-status", "Stopping...");
    setText("report-audit-launch-detail", formatReportAuditCommandDetail({
      command: "audit.stop",
      ok: true,
      severity: "info",
      message: "Submitting backend audit stop request.",
    }, request));
    try {
      const result = await apiPost("/api/audit/stop", {
        confirm_stop: true,
        reason: request.reason,
      });
      appendReportAuditCommandResult(result);
      if (result.ok) {
        reportsState.reportAuditAcceptedRun = null;
        clearReportAuditRefreshTimers();
        stopReportAuditTimerIfIdle({});
        setText("report-audit-launch-status", "Stopped");
      } else {
        setText("report-audit-launch-status", "Blocked");
      }
      setText("report-audit-launch-detail", formatReportAuditCommandDetail(result, request));
      if ((result.refresh_hint || "") === "snapshot") {
        await refreshReportsAuditData();
      }
    } catch (error) {
      const text = error instanceof Error ? error.message : String(error);
      const result = { command: "audit.stop", ok: false, severity: "error", message: text };
      appendReportAuditCommandResult(result);
      setText("report-audit-launch-status", "Error");
      setText("report-audit-launch-detail", formatReportAuditCommandDetail(result, request));
    } finally {
      setReportAuditCommandBusy("");
      renderReportAuditRunningState(reportsState.lastReportSnapshot);
    }
  }

  async function saveReportAuditScorePolicy(reset = false) {
    if (reportsState.reportAuditCommandBusy) {
      const result = reportAuditBusyResult("audit.score_policy");
      appendReportAuditCommandResult(result);
      setText("report-audit-score-policy-status", "Busy");
      setText("report-audit-score-policy-detail", formatReportAuditCommandDetail(result));
      return;
    }
    const request = reset ? { reset: true } : { policy: collectReportAuditScorePolicyForm() };
    const message = reset ? "Reset audit score policy to defaults?" : "Save audit score policy for future audit runs?";
    if (!window.confirm(message)) return;
    setReportAuditCommandBusy("audit.score_policy", reset ? "report-audit-score-policy-reset-button" : "report-audit-score-policy-save-button");
    setText("report-audit-score-policy-status", reset ? "Resetting..." : "Saving...");
    setText("report-audit-score-policy-detail", reset ? "Resetting audit score policy..." : "Saving audit score policy...");
    try {
      const result = await apiPost("/api/audit/score-policy", request);
      appendReportAuditCommandResult(result);
      setText("report-audit-score-policy-detail", formatReportAuditCommandDetail(result, request));
      await refreshReportsAuditData();
    } catch (error) {
      const text = error instanceof Error ? error.message : String(error);
      const result = { command: "audit.score_policy", ok: false, severity: "error", message: text };
      appendReportAuditCommandResult(result);
      setText("report-audit-score-policy-status", "Error");
      setText("report-audit-score-policy-detail", formatReportAuditCommandDetail(result, request));
    } finally {
      setReportAuditCommandBusy("");
    }
  }

  async function ignoreSelectedAuditRows() {
    if (reportsState.reportAuditCommandBusy) {
      const result = reportAuditBusyResult("audit.ignore");
      appendReportAuditCommandResult(result);
      setText("report-audit-export-status", "Busy");
      setText("report-audit-export-detail", formatReportAuditCommandDetail(result));
      return;
    }
    const rowKeys = selectedAuditRowKeysList();
    if (!rowKeys.length) {
      setText("report-audit-export-status", "Select rows");
      setText("report-audit-export-detail", "Select one or more audit rows before setting audit ignore.");
      return;
    }
    if (hiddenSelectedAuditCount()) {
      setText("report-audit-export-status", "Blocked");
      setText("report-audit-export-detail", hiddenAuditSelectionMessage("ignoring selected rows"));
      return;
    }
    if (!window.confirm(`Ignore ${rowKeys.length} selected audit row(s) from audit triage/export?`)) return;
    const request = {
      ...reportAuditSelectionRequest(),
      action: "add",
      reason: "Ignored from audit triage by operator.",
    };
    setReportAuditCommandBusy("audit.ignore", "report-audit-ignore-selected-button");
    setText("report-audit-export-status", "Ignoring...");
    setText("report-audit-export-detail", "Saving audit ignore entries...");
    try {
      const result = await apiPost("/api/audit/ignore", request);
      appendReportAuditCommandResult(result);
      reportsState.selectedAuditRowKeys = new Set();
      reportsState.selectedAuditRowKey = "";
      setText("report-audit-export-status", result.ok ? "Ignored" : "Blocked");
      setText("report-audit-export-detail", formatReportAuditCommandDetail(result, request));
      await refreshReportsAuditData();
    } catch (error) {
      const text = error instanceof Error ? error.message : String(error);
      const result = { command: "audit.ignore", ok: false, severity: "error", message: text };
      appendReportAuditCommandResult(result);
      setText("report-audit-export-status", "Error");
      setText("report-audit-export-detail", formatReportAuditCommandDetail(result, request));
    } finally {
      setReportAuditCommandBusy("");
    }
  }

  function auditRerunExportData(result) {
    return result?.data && typeof result.data === "object" ? result.data : {};
  }

  function auditRerunExportHandoff(result) {
    const data = auditRerunExportData(result);
    return data.handoff && typeof data.handoff === "object" ? data.handoff : {};
  }

  function auditRerunExportCsvPath(result) {
    const data = auditRerunExportData(result);
    const handoff = auditRerunExportHandoff(result);
    return String(handoff.csv_path || data.exported_csv_path || data.output_path || "").trim();
  }

  async function handoffAuditRerunCsvToQueue(result, request) {
    if (!result?.ok) return false;
    const csvPath = auditRerunExportCsvPath(result);
    if (!csvPath) return false;
    const data = auditRerunExportData(result);
    const handoff = auditRerunExportHandoff(result);
    const queueView = window.mediaPipelineQueueView || {};
    if (typeof window.showPage === "function") window.showPage("queue");
    if (typeof queueView.activateQueueTab === "function") queueView.activateQueueTab("rerun", { persist: true });
    if (typeof queueView.selectRerunCsvPathForPreview !== "function") {
      setText("report-audit-export-status", "Exported");
      setText("report-audit-export-detail", [
        formatReportAuditCommandDetail(result, request),
        "",
        `Queue CSV Rerun handoff path: ${csvPath}`,
        "Queue preview helper is unavailable; open Queue > CSV Rerun and preview the exported CSV.",
      ].join("\n"));
      return false;
    }
    setText("report-audit-export-status", "Opening Queue");
    setText("report-audit-export-detail", [
      formatReportAuditCommandDetail(result, request),
      "",
      `Opening Queue CSV Rerun with ${csvPath}`,
    ].join("\n"));
    try {
      const preview = await queueView.selectRerunCsvPathForPreview(csvPath, {
        source: "audit_export",
        rowCount: data.row_count,
        handoff,
      });
      const previewStatus = String(preview?.status || (preview?.ok === false ? "blocked" : preview?.ok ? "ready" : "requested"));
      setText("report-audit-export-status", preview?.ok === false ? "Preview blocked" : "Queue preview");
      setText("report-audit-export-detail", [
        formatReportAuditCommandDetail(result, request),
        "",
        `Queue CSV Rerun handoff: ${previewStatus}.`,
        `CSV: ${csvPath}`,
        `Preview route: ${handoff.preview_route || "/api/rerun/preview"}`,
        "Start route remains /api/rerun/start; normal /api/pipeline/start is not used.",
      ].join("\n"));
      return true;
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setText("report-audit-export-status", "Exported");
      setText("report-audit-export-detail", [
        formatReportAuditCommandDetail(result, request),
        "",
        `Queue CSV Rerun handoff path: ${csvPath}`,
        `Queue preview request failed: ${message}`,
      ].join("\n"));
      return false;
    }
  }

  async function exportAuditRerunCsv() {
    if (reportsState.reportAuditCommandBusy) {
      const result = reportAuditBusyResult("audit.export_rerun_csv");
      appendReportAuditCommandResult(result);
      setText("report-audit-export-status", "Busy");
      setText("report-audit-export-detail", formatReportAuditCommandDetail(result));
      return;
    }
    const request = reportAuditSelectionRequest();
    if (request.row_keys.length && hiddenSelectedAuditCount()) {
      setText("report-audit-export-status", "Blocked");
      setText("report-audit-export-detail", hiddenAuditSelectionMessage("exporting selected rows"));
      return;
    }
    const scope = request.row_keys.length
      ? `${request.row_keys.length} selected row(s)`
      : "all non-ignored rows in the latest audit CSV (current filter is display-only)";
    if (!window.confirm(`Build CSV rerun queue for ${scope}?`)) return;
    setReportAuditCommandBusy("audit.export_rerun_csv", "report-audit-export-rerun-csv-button");
    setText("report-audit-export-status", "Building...");
    setText("report-audit-export-detail", "Building backend-owned rerun CSV for Queue...");
    try {
      const result = await apiPost("/api/audit/export-rerun-csv", request);
      appendReportAuditCommandResult(result);
      setText("report-audit-export-status", result.ok ? "Exported" : "Blocked");
      setText("report-audit-export-detail", formatReportAuditCommandDetail(result, request));
      if (result.ok) {
        await handoffAuditRerunCsvToQueue(result, request);
      } else {
        await refreshReportsAuditData();
      }
    } catch (error) {
      const text = error instanceof Error ? error.message : String(error);
      const result = { command: "audit.export_rerun_csv", ok: false, severity: "error", message: text };
      appendReportAuditCommandResult(result);
      setText("report-audit-export-status", "Error");
      setText("report-audit-export-detail", formatReportAuditCommandDetail(result, request));
    } finally {
      setReportAuditCommandBusy("");
    }
  }

    return {
      addReportAuditSourceFromForm,
      collectReportAuditStartRequest,
      exportAuditRerunCsv,
      ignoreSelectedAuditRows,
      renderReportAuditSources,
      renderReportAuditLaunchPreflight,
      renderReportAuditProgressPanel,
      renderReportAuditRunningState,
      reportAuditBusyResult,
      reportAuditJsonDetail,
      reportAuditReviewCount,
      scanReportAuditSources,
      selectAllReportAuditSources,
      clearReportAuditSourceSelection,
      saveReportAuditScorePolicy,
      setReportAuditCommandBusy,
      startReportAuditFromForm,
      stopReportAuditFromForm,
    };
  }

  window.__reportsViewAuditCommandsModule = {
    createReportsAuditCommandsModule,
  };
})();
