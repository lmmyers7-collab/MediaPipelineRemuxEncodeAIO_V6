// reports/auditCommands.js
// Audit command request, source table, progress, refresh, and result helpers for reportsView.js.

(function () {
  "use strict";

  const reportsAuditSourcesModule = window.__reportsAuditSourcesModule || {};
  delete window.__reportsAuditSourcesModule;
  if (typeof reportsAuditSourcesModule.createReportsAuditSourcesModule !== "function") {
    throw new Error("reports/audit/sources.js must load before reports/auditCommands.js");
  }
  const reportsAuditProgressModule = window.__reportsAuditProgressModule || {};
  delete window.__reportsAuditProgressModule;
  if (typeof reportsAuditProgressModule.createReportsAuditProgressModule !== "function") {
    throw new Error("reports/audit/progress.js must load before reports/auditCommands.js");
  }

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
    const reportAuditCommandButtonIds = deps.reportAuditCommandButtonIds && typeof deps.reportAuditCommandButtonIds === "object"
      ? deps.reportAuditCommandButtonIds
      : {};
    const reportAuditScoreFieldIds = deps.reportAuditScoreFieldIds && typeof deps.reportAuditScoreFieldIds === "object" ? deps.reportAuditScoreFieldIds : {};
    const reportNumber = typeof deps.reportNumber === "function" ? deps.reportNumber : function (value) { const numeric = Number(value); return Number.isFinite(numeric) ? numeric : 0; };
    const selectedAuditRowKeysList = typeof deps.selectedAuditRowKeysList === "function" ? deps.selectedAuditRowKeysList : function () { return []; };
    const setButtonsBusy = typeof deps.setButtonsBusy === "function" ? deps.setButtonsBusy : noop;
    const setText = typeof deps.setText === "function" ? deps.setText : noop;
    const REPORT_AUDIT_POST_START_REFRESH_DELAYS_MS = [1000, 3000, 7000, 15000, 30000];
    const REPORT_AUDIT_BACKEND_ACTIVE_FRESH_MS = 10 * 60 * 1000;
    const REPORT_AUDIT_REFRESH_TIMEOUT_MS = 15 * 1000;

  function reportAuditBusyOperations() {
    if (!reportsState.reportAuditBusyOperations || typeof reportsState.reportAuditBusyOperations !== "object") {
      reportsState.reportAuditBusyOperations = {};
    }
    return reportsState.reportAuditBusyOperations;
  }

  function reportAuditOperationIsBusy(scope) {
    return Boolean(reportAuditBusyOperations()[scope]);
  }

  function reportAuditBusyCommand(scopes = []) {
    for (const scope of scopes) {
      const command = String(reportAuditBusyOperations()[scope] || "").trim();
      if (command) return command;
    }
    return "";
  }

  function setReportAuditOperationBusy(scope, command, activeId = "") {
    const operations = reportAuditBusyOperations();
    if (command) operations[scope] = command;
    else delete operations[scope];
    setButtonsBusy(reportAuditCommandButtonIds[scope] || [], Boolean(command), activeId);
    if (typeof renderReportAuditSources === "function") {
      renderReportAuditSources(reportsState.lastReportAuditSources);
    }
    updateReportAuditStartButtonState();
  }

  function reportAuditBusyResult(command, scopes = []) {
    const activeCommand = reportAuditBusyCommand(scopes) || "another audit operation";
    return {
      command,
      ok: false,
      severity: "warning",
      message: `Another Reports audit command is already in progress: ${activeCommand}.`,
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

  function appendReportsAuditRefreshWarning({ statusId, detailId, message }) {
    const statusNode = byId(statusId);
    const detailNode = byId(detailId);
    const currentStatus = String(statusNode?.textContent || "Updated").replace(/\s*·\s*refresh warning$/i, "");
    const currentDetail = String(detailNode?.textContent || "").trim();
    if (statusId === "report-audit-launch-status" && detailId === "report-audit-launch-detail") {
      reportsState.reportAuditRefreshWarning = message;
    }
    setText(statusId, `${currentStatus || "Updated"} · refresh warning`);
    setText(detailId, [
      currentDetail,
      "",
      `Refresh warning: ${message}`,
      "The backend command already completed. Command controls remain available. Wait for top-bar refresh activity to finish before retrying; reload the app if it does not return to idle.",
    ].filter(Boolean).join("\n"));
  }

  async function refreshReportsAuditData({ automatic = false, statusId = "report-audit-launch-status", detailId = "report-audit-launch-detail" } = {}) {
    const refresh = typeof window.refreshAll === "function" ? window.refreshAll : refreshAll;
    if (typeof refresh !== "function") return { ok: true, skipped: true };
    let timeoutId = 0;
    try {
      await Promise.race([
        Promise.resolve().then(() => refresh({ automatic })),
        new Promise((_, reject) => {
          timeoutId = window.setTimeout(() => {
            reject(new Error("Full Reports refresh timed out after 15 seconds."));
          }, REPORT_AUDIT_REFRESH_TIMEOUT_MS);
        }),
      ]);
      if (statusId === "report-audit-launch-status" && detailId === "report-audit-launch-detail") {
        reportsState.reportAuditRefreshWarning = "";
      }
      return { ok: true, skipped: false };
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      appendReportsAuditRefreshWarning({ statusId, detailId, message });
      return { ok: false, skipped: false, message };
    } finally {
      if (timeoutId) window.clearTimeout(timeoutId);
    }
  }

  function queueReportsAuditRefresh(options = {}) {
    void refreshReportsAuditData(options);
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
    const busyScopes = ["sourceEdit", "sourceScan", "start", "stop"];
    if (reportAuditBusyCommand(busyScopes)) {
      const result = reportAuditBusyResult("audit.sources", busyScopes);
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
    setReportAuditOperationBusy("sourceEdit", "audit.sources", "report-audit-add-source-button");
    setText("report-audit-launch-status", "Adding...");
    setText("report-audit-launch-detail", "Adding backend-owned audit source...");
    let refreshAfterCommand = false;
    try {
      const result = await apiPost("/api/audit/sources", request, { timeoutMs: 15000 });
      appendReportAuditCommandResult(result);
      const auditSources = result?.data?.audit_sources;
      const added = reportAuditSourceRows(auditSources).find((row) => reportAuditLocationKey(row.path) === reportAuditLocationKey(path));
      const addedId = reportAuditSourceId(added);
      if (result.ok && addedId) reportAuditSelectedSourceIds().add(addedId);
      renderReportAuditSourceCommandResult(result, request);
      refreshAfterCommand = true;
    } catch (error) {
      const text = error instanceof Error ? error.message : String(error);
      const result = { command: "audit.sources", ok: false, severity: "error", message: text };
      appendReportAuditCommandResult(result);
      renderReportAuditSourceCommandResult(result, request);
    } finally {
      setReportAuditOperationBusy("sourceEdit", "");
      if (refreshAfterCommand) queueReportsAuditRefresh();
    }
  }

  async function removeReportAuditSource(sourceId) {
    const busyScopes = ["sourceEdit", "sourceScan", "start", "stop"];
    if (reportAuditBusyCommand(busyScopes)) {
      const result = reportAuditBusyResult("audit.sources", busyScopes);
      appendReportAuditCommandResult(result);
      renderReportAuditSourceCommandResult(result, null);
      return;
    }
    const source = reportAuditSourceRows().find((row) => reportAuditSourceId(row) === sourceId);
    if (!source) return;
    if (!window.confirm(`Remove audit source?\n\n${source.path || source.label || sourceId}`)) return;
    const request = { action: "remove", source_id: sourceId };
    setReportAuditOperationBusy("sourceEdit", "audit.sources");
    setText("report-audit-launch-status", "Removing...");
    setText("report-audit-launch-detail", "Removing backend-owned audit source...");
    let refreshAfterCommand = false;
    try {
      const result = await apiPost("/api/audit/sources", request, { timeoutMs: 15000 });
      appendReportAuditCommandResult(result);
      reportAuditSelectedSourceIds().delete(sourceId);
      renderReportAuditSourceCommandResult(result, request);
      refreshAfterCommand = true;
    } catch (error) {
      const text = error instanceof Error ? error.message : String(error);
      const result = { command: "audit.sources", ok: false, severity: "error", message: text };
      appendReportAuditCommandResult(result);
      renderReportAuditSourceCommandResult(result, request);
    } finally {
      setReportAuditOperationBusy("sourceEdit", "");
      if (refreshAfterCommand) queueReportsAuditRefresh();
    }
  }

  async function scanReportAuditSources(sourceIds = null) {
    const busyScopes = ["sourceEdit", "sourceScan", "start", "stop"];
    if (reportAuditBusyCommand(busyScopes)) {
      const result = reportAuditBusyResult("audit.sources.scan", busyScopes);
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
    setReportAuditOperationBusy("sourceScan", "audit.sources.scan", selectedIds.length ? "report-audit-scan-selected-button" : "report-audit-scan-all-button");
    setText("report-audit-launch-status", "Scanning...");
    setText("report-audit-launch-detail", `Scanning ${scopeText}...`);
    let refreshAfterCommand = false;
    try {
      const result = await apiPost("/api/audit/sources/scan", request, { timeoutMs: 0 });
      appendReportAuditCommandResult(result);
      renderReportAuditSourceCommandResult(result, request);
      refreshAfterCommand = true;
    } catch (error) {
      const text = error instanceof Error ? error.message : String(error);
      const result = { command: "audit.sources.scan", ok: false, severity: "error", message: text };
      appendReportAuditCommandResult(result);
      renderReportAuditSourceCommandResult(result, request);
    } finally {
      setReportAuditOperationBusy("sourceScan", "");
      if (refreshAfterCommand) queueReportsAuditRefresh();
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

  function prepareReportAuditSnapshotForAcceptedStart() {
    const snapshot = reportsState.lastReportSnapshot && typeof reportsState.lastReportSnapshot === "object"
      ? reportsState.lastReportSnapshot
      : {};
    reportsState.lastReportSnapshot = {
      ...snapshot,
      audit_progress: {},
      progress_bars: Array.isArray(snapshot.progress_bars)
        ? snapshot.progress_bars.filter((bar) => {
            const id = String(bar?.id || "").toLowerCase();
            const source = String(bar?.source || "").toLowerCase();
            return id !== "audit_progress" && id !== "audit_reports" && !source.includes("audit_progress");
          })
        : [],
    };
  }

  async function startReportAuditFromForm() {
    const busyScopes = ["start", "stop", "sourceEdit", "sourceScan"];
    if (reportAuditBusyCommand(busyScopes)) {
      const result = reportAuditBusyResult("audit.start", busyScopes);
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
    reportsState.reportAuditAutoPriorityCsvPath = "";
    reportsState.reportAuditRefreshWarning = "";
    setReportAuditOperationBusy("start", "audit.start", "report-audit-start-button");
    setText("report-audit-launch-status", "Starting...");
    setText("report-audit-launch-detail", formatReportAuditCommandDetail({
      command: "audit.start",
      ok: true,
      severity: "info",
      message: "Submitting backend audit start request.",
    }, request));
    let refreshAfterCommand = false;
    try {
      const result = await apiPost("/api/audit/start", request);
      appendReportAuditCommandResult(result);
      if (result.ok) {
        prepareReportAuditSnapshotForAcceptedStart();
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
        refreshAfterCommand = true;
      }
    } catch (error) {
      const text = error instanceof Error ? error.message : String(error);
      const result = { command: "audit.start", ok: false, severity: "error", message: text };
      appendReportAuditCommandResult(result);
      reportsState.reportAuditAcceptedRun = null;
      setText("report-audit-launch-status", "Error");
      setText("report-audit-launch-detail", formatReportAuditCommandDetail(result, request));
    } finally {
      setReportAuditOperationBusy("start", "");
      renderReportAuditRunningState(reportsState.lastReportSnapshot);
      if (refreshAfterCommand) queueReportsAuditRefresh();
    }
  }

  function applyReportAuditStoppedSnapshot() {
    const snapshot = reportsState.lastReportSnapshot && typeof reportsState.lastReportSnapshot === "object"
      ? reportsState.lastReportSnapshot
      : {};
    const auditProgress = snapshot.audit_progress && typeof snapshot.audit_progress === "object"
      ? snapshot.audit_progress
      : {};
    const now = new Date().toISOString();
    const progressBars = Array.isArray(snapshot.progress_bars)
      ? snapshot.progress_bars.filter((bar) => {
          const id = String(bar?.id || "").toLowerCase();
          const source = String(bar?.source || "").toLowerCase();
          return id !== "audit_progress" && id !== "audit_reports" && !source.includes("audit_progress");
        })
      : [];
    const workerProgress = snapshot.worker_progress && typeof snapshot.worker_progress === "object"
      ? { ...snapshot.worker_progress }
      : {};
    if (Array.isArray(workerProgress.rows)) {
      workerProgress.rows = workerProgress.rows.filter((row) => {
        const kind = String(row?.job_kind || row?.kind || "").replace(/-/g, "_").toLowerCase();
        return kind !== "audit";
      });
    }
    reportsState.lastReportSnapshot = {
      ...snapshot,
      audit_progress: {
        ...auditProgress,
        status: "stopped",
        completed: false,
        failed: false,
        current_operation: "Stopped by operator from Reports.",
        last_update: now,
        updated_at: now,
      },
      progress_bars: progressBars,
      worker_progress: workerProgress,
    };
  }

  async function stopReportAuditFromForm() {
    const busyScopes = ["start", "stop"];
    if (reportAuditBusyCommand(busyScopes)) {
      const result = reportAuditBusyResult("audit.stop", busyScopes);
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
    setReportAuditOperationBusy("stop", "audit.stop", "report-audit-stop-button");
    setText("report-audit-launch-status", "Stopping...");
    setText("report-audit-launch-detail", formatReportAuditCommandDetail({
      command: "audit.stop",
      ok: true,
      severity: "info",
      message: "Submitting backend audit stop request.",
    }, request));
    let refreshAfterCommand = false;
    try {
      const result = await apiPost("/api/audit/stop", {
        confirm_stop: true,
        reason: request.reason,
      });
      appendReportAuditCommandResult(result);
      if (result.ok) {
        reportsState.reportAuditAcceptedRun = null;
        applyReportAuditStoppedSnapshot();
        clearReportAuditRefreshTimers();
        stopReportAuditTimerIfIdle({});
        setText("report-audit-launch-status", "Stopped");
      } else {
        setText("report-audit-launch-status", "Blocked");
      }
      setText("report-audit-launch-detail", formatReportAuditCommandDetail(result, request));
      if ((result.refresh_hint || "") === "snapshot") {
        refreshAfterCommand = true;
      }
    } catch (error) {
      const text = error instanceof Error ? error.message : String(error);
      const result = { command: "audit.stop", ok: false, severity: "error", message: text };
      appendReportAuditCommandResult(result);
      setText("report-audit-launch-status", "Error");
      setText("report-audit-launch-detail", formatReportAuditCommandDetail(result, request));
    } finally {
      setReportAuditOperationBusy("stop", "");
      renderReportAuditRunningState(reportsState.lastReportSnapshot);
      if (refreshAfterCommand) queueReportsAuditRefresh();
    }
  }

  async function saveReportAuditScorePolicy(reset = false) {
    const busyScopes = ["policy"];
    if (reportAuditBusyCommand(busyScopes)) {
      const result = reportAuditBusyResult("audit.score_policy", busyScopes);
      appendReportAuditCommandResult(result);
      setText("report-audit-score-policy-status", "Busy");
      setText("report-audit-score-policy-detail", formatReportAuditCommandDetail(result));
      return;
    }
    const request = reset ? { reset: true } : { policy: collectReportAuditScorePolicyForm() };
    const message = reset ? "Reset audit score policy to defaults?" : "Save audit score policy for future audit runs?";
    if (!window.confirm(message)) return;
    setReportAuditOperationBusy("policy", "audit.score_policy", reset ? "report-audit-score-policy-reset-button" : "report-audit-score-policy-save-button");
    setText("report-audit-score-policy-status", reset ? "Resetting..." : "Saving...");
    setText("report-audit-score-policy-detail", reset ? "Resetting audit score policy..." : "Saving audit score policy...");
    let refreshAfterCommand = false;
    try {
      const result = await apiPost("/api/audit/score-policy", request);
      appendReportAuditCommandResult(result);
      setText("report-audit-score-policy-status", result.ok ? (reset ? "Defaults" : "Saved") : "Blocked");
      setText("report-audit-score-policy-detail", formatReportAuditCommandDetail(result, request));
      refreshAfterCommand = true;
    } catch (error) {
      const text = error instanceof Error ? error.message : String(error);
      const result = { command: "audit.score_policy", ok: false, severity: "error", message: text };
      appendReportAuditCommandResult(result);
      setText("report-audit-score-policy-status", "Error");
      setText("report-audit-score-policy-detail", formatReportAuditCommandDetail(result, request));
    } finally {
      setReportAuditOperationBusy("policy", "");
      if (refreshAfterCommand) queueReportsAuditRefresh({
        statusId: "report-audit-score-policy-status",
        detailId: "report-audit-score-policy-detail",
      });
    }
  }

  async function ignoreSelectedAuditRows() {
    const busyScopes = ["triage"];
    if (reportAuditBusyCommand(busyScopes)) {
      const result = reportAuditBusyResult("audit.ignore", busyScopes);
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
    setReportAuditOperationBusy("triage", "audit.ignore", "report-audit-ignore-selected-button");
    setText("report-audit-export-status", "Ignoring...");
    setText("report-audit-export-detail", "Saving audit ignore entries...");
    let refreshAfterCommand = false;
    try {
      const result = await apiPost("/api/audit/ignore", request);
      appendReportAuditCommandResult(result);
      reportsState.selectedAuditRowKeys = new Set();
      reportsState.selectedAuditRowKey = "";
      setText("report-audit-export-status", result.ok ? "Ignored" : "Blocked");
      setText("report-audit-export-detail", formatReportAuditCommandDetail(result, request));
      refreshAfterCommand = true;
    } catch (error) {
      const text = error instanceof Error ? error.message : String(error);
      const result = { command: "audit.ignore", ok: false, severity: "error", message: text };
      appendReportAuditCommandResult(result);
      setText("report-audit-export-status", "Error");
      setText("report-audit-export-detail", formatReportAuditCommandDetail(result, request));
    } finally {
      setReportAuditOperationBusy("triage", "");
      if (refreshAfterCommand) queueReportsAuditRefresh({
        statusId: "report-audit-export-status",
        detailId: "report-audit-export-detail",
      });
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
    const busyScopes = ["triage"];
    if (reportAuditBusyCommand(busyScopes)) {
      const result = reportAuditBusyResult("audit.export_rerun_csv", busyScopes);
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
    setReportAuditOperationBusy("triage", "audit.export_rerun_csv", "report-audit-export-rerun-csv-button");
    setText("report-audit-export-status", "Building...");
    setText("report-audit-export-detail", "Building backend-owned rerun CSV for Queue...");
    let refreshAfterCommand = false;
    try {
      const result = await apiPost("/api/audit/export-rerun-csv", request);
      appendReportAuditCommandResult(result);
      setText("report-audit-export-status", result.ok ? "Exported" : "Blocked");
      setText("report-audit-export-detail", formatReportAuditCommandDetail(result, request));
      if (result.ok) {
        await handoffAuditRerunCsvToQueue(result, request);
      } else {
        refreshAfterCommand = true;
      }
    } catch (error) {
      const text = error instanceof Error ? error.message : String(error);
      const result = { command: "audit.export_rerun_csv", ok: false, severity: "error", message: text };
      appendReportAuditCommandResult(result);
      setText("report-audit-export-status", "Error");
      setText("report-audit-export-detail", formatReportAuditCommandDetail(result, request));
    } finally {
      setReportAuditOperationBusy("triage", "");
      if (refreshAfterCommand) queueReportsAuditRefresh({
        statusId: "report-audit-export-status",
        detailId: "report-audit-export-detail",
      });
    }
  }

    const reportsAuditSources = reportsAuditSourcesModule.createReportsAuditSourcesModule({
      byId,
      removeReportAuditSource,
      renderReportAuditLaunchPreflight,
      scanReportAuditSources,
      setText,
      startReportAuditFromForm,
      state: reportsState,
    });
    const {
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
    } = reportsAuditSources;
    const reportsAuditProgress = reportsAuditProgressModule.createReportsAuditProgressModule({
      backendActiveFreshMs: REPORT_AUDIT_BACKEND_ACTIVE_FRESH_MS,
      byId,
      collectReportAuditStartRequest,
      formatReportAuditCommandDetail,
      postStartRefreshDelaysMs: REPORT_AUDIT_POST_START_REFRESH_DELAYS_MS,
      queueReportsAuditRefresh,
      refreshAll,
      renderAuditProgressInto,
      selectedReportAuditSourceRows,
      setText,
      state: reportsState,
    });
    const {
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
    } = reportsAuditProgress;

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
      reportAuditOperationIsBusy,
      reportAuditJsonDetail,
      reportAuditReviewCount,
      scanReportAuditSources,
      selectAllReportAuditSources,
      clearReportAuditSourceSelection,
      queueReportsAuditRefresh,
      saveReportAuditScorePolicy,
      setReportAuditOperationBusy,
      startReportAuditFromForm,
      stopReportAuditFromForm,
    };
  }

  window.__reportsViewAuditCommandsModule = {
    createReportsAuditCommandsModule,
  };
})();
