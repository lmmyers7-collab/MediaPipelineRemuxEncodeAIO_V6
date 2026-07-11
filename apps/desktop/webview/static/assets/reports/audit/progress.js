// reports/audit/progress.js
// Backend-progress normalization, evidence freshness, and refresh lifecycle for Reports audits.
(function () {
  "use strict";

  function createReportsAuditProgressModule(deps = {}) {
    const reportsState = deps.state && typeof deps.state === "object" ? deps.state : {};
    const byId = typeof deps.byId === "function" ? deps.byId : function () { return null; };
    const collectReportAuditStartRequest = typeof deps.collectReportAuditStartRequest === "function" ? deps.collectReportAuditStartRequest : function () { return {}; };
    const formatReportAuditCommandDetail = typeof deps.formatReportAuditCommandDetail === "function" ? deps.formatReportAuditCommandDetail : function () { return ""; };
    const refreshAll = typeof deps.refreshAll === "function" ? deps.refreshAll : null;
    const renderAuditProgressInto = typeof deps.renderAuditProgressInto === "function" ? deps.renderAuditProgressInto : null;
    const selectedReportAuditSourceRows = typeof deps.selectedReportAuditSourceRows === "function" ? deps.selectedReportAuditSourceRows : function () { return []; };
    const setText = typeof deps.setText === "function" ? deps.setText : function () {};
    const REPORT_AUDIT_POST_START_REFRESH_DELAYS_MS = Array.isArray(deps.postStartRefreshDelaysMs) ? deps.postStartRefreshDelaysMs : [1000, 3000, 7000, 15000, 30000];
    const REPORT_AUDIT_BACKEND_ACTIVE_FRESH_MS = Number.isFinite(Number(deps.backendActiveFreshMs)) ? Number(deps.backendActiveFreshMs) : 10 * 60 * 1000;
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


    return {
      clearReportAuditRefreshTimers,
      ensureReportAuditTimer,
      formatReportAuditElapsed,
      parseReportAuditTimestamp,
      renderReportAuditProgressPanel,
      renderReportAuditRunningState,
      reportAuditAcceptedRunEvidence,
      reportAuditActiveWorkerRows,
      reportAuditCurrentRunEvidence,
      reportAuditHasBackendActiveRunEvidence,
      reportAuditPriorityCsvPath,
      reportAuditProgressBars,
      reportAuditProgressIsActive,
      reportAuditProgressIsTerminal,
      reportAuditProgressPayload,
      reportAuditProgressSucceeded,
      reportAuditSnapshotCoversAcceptedRun,
      reportAuditSnapshotIsFreshForUi,
      reportAuditSnapshotRunEvidence,
      reportAuditSnapshotTimestampMs,
      reportAuditStaleProgressEvidence,
      reportAuditSyntheticSnapshot,
      scheduleReportAuditRefreshes,
      selectReportAuditPriorityTable,
      stopReportAuditTimerIfIdle,
      updateReportAuditStartButtonState,
    };
  }

  window.__reportsAuditProgressModule = { createReportsAuditProgressModule };
})();
