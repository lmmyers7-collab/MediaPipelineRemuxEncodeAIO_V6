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
    const reportAuditCommandButtonIds = Array.isArray(deps.reportAuditCommandButtonIds) ? deps.reportAuditCommandButtonIds : [];
    const reportAuditScoreFieldIds = deps.reportAuditScoreFieldIds && typeof deps.reportAuditScoreFieldIds === "object" ? deps.reportAuditScoreFieldIds : {};
    const reportNumber = typeof deps.reportNumber === "function" ? deps.reportNumber : function (value) { const numeric = Number(value); return Number.isFinite(numeric) ? numeric : 0; };
    const selectedAuditRowKeysList = typeof deps.selectedAuditRowKeysList === "function" ? deps.selectedAuditRowKeysList : function () { return []; };
    const setButtonsBusy = typeof deps.setButtonsBusy === "function" ? deps.setButtonsBusy : noop;
    const setText = typeof deps.setText === "function" ? deps.setText : noop;
    const REPORT_AUDIT_POST_START_REFRESH_DELAYS_MS = [1000, 3000, 7000, 15000, 30000];
    const REPORT_AUDIT_BACKEND_ACTIVE_FRESH_MS = 10 * 60 * 1000;

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
