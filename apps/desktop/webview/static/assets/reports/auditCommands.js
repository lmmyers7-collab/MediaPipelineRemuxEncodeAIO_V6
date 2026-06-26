// reports/auditCommands.js
// Audit command request, progress, saved-location, refresh, and result helpers for reportsView.js.

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
    const REPORT_AUDIT_SAVED_LOCATIONS_STORAGE_KEY = "mediapipeline-report-audit-locations.v1";
    const REPORT_AUDIT_SAVED_LOCATION_LIMIT = 10;
    const REPORT_AUDIT_POST_START_REFRESH_DELAYS_MS = [1000, 3000, 7000, 15000, 30000];
    const REPORT_AUDIT_BACKEND_ACTIVE_FRESH_MS = 10 * 60 * 1000;

  function reportAuditLocationText(value) {
    return String(value || "").trim();
  }

  function reportAuditLocationKey(value) {
    return reportAuditLocationText(value).replace(/[\\/]+$/g, "").replace(/\//g, "\\").toLowerCase();
  }

  function normalizeReportAuditSavedLocations(values) {
    const locations = [];
    const seen = new Set();
    (Array.isArray(values) ? values : []).forEach((value) => {
      const location = reportAuditLocationText(value);
      const key = reportAuditLocationKey(location);
      if (!key || seen.has(key)) return;
      seen.add(key);
      locations.push(location);
    });
    return locations.slice(0, REPORT_AUDIT_SAVED_LOCATION_LIMIT);
  }

  function readReportAuditSavedLocations() {
    try {
      const parsed = JSON.parse(localStorage.getItem(REPORT_AUDIT_SAVED_LOCATIONS_STORAGE_KEY) || "[]");
      reportsState.lastReportAuditSavedLocations = normalizeReportAuditSavedLocations(parsed);
    } catch (_) {
      reportsState.lastReportAuditSavedLocations = normalizeReportAuditSavedLocations(reportsState.lastReportAuditSavedLocations);
    }
    return [...reportsState.lastReportAuditSavedLocations];
  }

  function writeReportAuditSavedLocations(locations) {
    reportsState.lastReportAuditSavedLocations = normalizeReportAuditSavedLocations(locations);
    try {
      localStorage.setItem(REPORT_AUDIT_SAVED_LOCATIONS_STORAGE_KEY, JSON.stringify(reportsState.lastReportAuditSavedLocations));
    } catch (_) {}
    return [...reportsState.lastReportAuditSavedLocations];
  }

  function renderReportAuditSavedLocations(message = "") {
    const locations = readReportAuditSavedLocations();
    const input = byId("report-audit-start-library-root");
    const select = byId("report-audit-saved-location-select");
    const currentLocation = reportAuditLocationText(input?.value);
    const currentKey = reportAuditLocationKey(currentLocation);
    const matchingLocation = locations.find((location) => reportAuditLocationKey(location) === currentKey) || "";
    if (select) {
      const previousValue = select.value;
      select.replaceChildren();
      const placeholder = document.createElement("option");
      placeholder.value = "";
      placeholder.textContent = locations.length ? "Select saved location" : "No saved locations";
      select.appendChild(placeholder);
      locations.forEach((location, index) => {
        const option = document.createElement("option");
        option.value = location;
        option.textContent = `${index + 1}. ${location}`;
        select.appendChild(option);
      });
      select.value = matchingLocation || (locations.includes(previousValue) ? previousValue : "");
    }
    const newLocationAtLimit = Boolean(currentKey)
      && !locations.some((location) => reportAuditLocationKey(location) === currentKey)
      && locations.length >= REPORT_AUDIT_SAVED_LOCATION_LIMIT;
    const saveButton = byId("report-audit-save-location-button");
    if (saveButton) saveButton.disabled = !currentKey || newLocationAtLimit;
    const removeButton = byId("report-audit-remove-location-button");
    const removableLocation = reportAuditLocationText(select?.value || matchingLocation);
    if (removeButton) removeButton.disabled = !locations.length || !removableLocation;
    const lines = [`Saved audit locations: ${locations.length}/${REPORT_AUDIT_SAVED_LOCATION_LIMIT}`];
    if (message) lines.push(message);
    if (locations.length) {
      locations.forEach((location, index) => lines.push(`${index + 1}. ${location}`));
    } else {
      lines.push("No saved audit locations.");
    }
    if (newLocationAtLimit) {
      lines.push("Saved location limit reached; remove one before saving a new location.");
    }
    lines.push("Start Audit submits one staged library root; saved locations only change the staged input.");
    setText("report-audit-location-summary", lines.join("\n"));
  }

  function saveReportAuditLocationFromForm() {
    const location = reportAuditLocationText(byId("report-audit-start-library-root")?.value);
    const key = reportAuditLocationKey(location);
    if (!key) {
      renderReportAuditSavedLocations("Enter a library root before saving it.");
      return;
    }
    const locations = readReportAuditSavedLocations();
    const withoutLocation = locations.filter((item) => reportAuditLocationKey(item) !== key);
    if (withoutLocation.length === locations.length && locations.length >= REPORT_AUDIT_SAVED_LOCATION_LIMIT) {
      renderReportAuditSavedLocations("Saved location limit reached; remove one before saving a new location.");
      return;
    }
    writeReportAuditSavedLocations([location, ...withoutLocation]);
    renderReportAuditSavedLocations(withoutLocation.length === locations.length ? "Saved audit location." : "Updated saved audit location.");
    renderReportAuditLaunchPreflight();
  }

  function removeReportAuditLocationFromForm() {
    const select = byId("report-audit-saved-location-select");
    const input = byId("report-audit-start-library-root");
    const target = reportAuditLocationText(select?.value || input?.value);
    const targetKey = reportAuditLocationKey(target);
    if (!targetKey) {
      renderReportAuditSavedLocations("Select a saved location before removing it.");
      return;
    }
    const locations = readReportAuditSavedLocations();
    const nextLocations = locations.filter((location) => reportAuditLocationKey(location) !== targetKey);
    if (nextLocations.length === locations.length) {
      renderReportAuditSavedLocations("That location is not saved.");
      return;
    }
    writeReportAuditSavedLocations(nextLocations);
    if (select) select.value = "";
    renderReportAuditSavedLocations("Removed saved audit location.");
    renderReportAuditLaunchPreflight();
  }

  function selectReportAuditSavedLocation(value) {
    const location = reportAuditLocationText(value);
    if (!location) {
      renderReportAuditSavedLocations();
      return;
    }
    const input = byId("report-audit-start-library-root");
    if (input) input.value = location;
    renderReportAuditLaunchPreflight();
    renderReportAuditSavedLocations();
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
      includeSidecars: auditProgress.include_sidecars ?? auditProgress.IncludeSidecars,
      result: null,
      request: null,
      stale: !fresh,
    };
  }

  function reportAuditCurrentRunEvidence(snapshot = reportsState.lastReportSnapshot) {
    const accepted = reportAuditAcceptedRunEvidence();
    if (accepted) {
      if (reportAuditProgressIsTerminal(snapshot || {}) && reportAuditSnapshotCoversAcceptedRun(snapshot || {})) return null;
      return accepted;
    }
    if (reportAuditProgressIsTerminal(snapshot || {})) return null;
    return reportAuditSnapshotRunEvidence(snapshot || {}, { requireFresh: false });
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
    const disabled = reportsState.reportAuditStartBusy || Boolean(reportsState.reportAuditCommandBusy) || Boolean(evidence);
    if (button) {
      button.disabled = disabled;
      button.setAttribute("aria-busy", String(Boolean(reportsState.reportAuditStartBusy || evidence)));
      button.textContent = evidence ? "Audit Running" : "Start Audit";
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
      reportsState.reportAuditAcceptedRun = null;
      clearReportAuditRefreshTimers();
    }
    const evidence = reportAuditCurrentRunEvidence(snapshot || {});
    if (evidence) {
      setText("report-audit-launch-status", `${evidence.stale ? "Stale" : "Running"} ${evidence.elapsed}`);
      const result = evidence.result || {
        command: "audit.start",
        ok: true,
        severity: "info",
        message: evidence.stale
          ? "Audit progress is active but stale in the backend snapshot."
          : "Audit progress is active in the backend snapshot.",
      };
      const request = evidence.request || collectReportAuditStartRequest();
      setText("report-audit-launch-detail", [
        formatReportAuditCommandDetail(result, request),
        "",
        `Running indicator: ${evidence.stale ? "stale active" : "active"}`,
        `Elapsed: ${evidence.elapsed}`,
        `PID: ${evidence.pid || "not reported"}`,
        `Library root: ${evidence.libraryRoot || request.library_root || "(backend configured Outsource fallback)"}`,
        "ETA: unavailable until backend audit progress reports file count and elapsed evidence.",
        `Progress source: backend audit_progress.json when present; otherwise local accepted-start state.${evidence.stale ? " Snapshot is stale." : ""}`,
      ].join("\n"));
      renderReportAuditProgressPanel(snapshot || {});
      ensureReportAuditTimer();
    } else {
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
    return reportNumber(reportsState.lastAuditPreviewPayload?.redownload_count)
      + reportNumber(reportsState.lastAuditPreviewPayload?.rerun_count)
      + reportNumber(reportsState.lastAuditPreviewPayload?.high_priority_count);
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
    return {
      library_root: String(byId("report-audit-start-library-root")?.value || "").trim(),
      include_sidecars: Boolean(byId("report-audit-start-include-sidecars")?.checked),
      show_console: Boolean(byId("report-audit-start-show-console")?.checked),
    };
  }

  function reportAuditLaunchPreflightLines(request = collectReportAuditStartRequest()) {
    const savedLocations = readReportAuditSavedLocations();
    const lines = [
      "Reports audit start request:",
      `Library root: ${request.library_root || "(backend configured Outsource fallback)"}`,
      `Saved locations: ${savedLocations.length}/${REPORT_AUDIT_SAVED_LOCATION_LIMIT}`,
      `Include sidecars: ${request.include_sidecars ? "yes" : "no"}`,
      `Show console: ${request.show_console ? "yes" : "no"}`,
      "Readiness preview: informational only; this is not a backend dry-run.",
      "Boundary: Reports submits /api/audit/start only after confirmation. Backend launch locking, config identity, duplicate-audit detection, and audit/pipeline concurrency policy remain authoritative.",
      "Concurrency: an active backend pipeline does not by itself block audit start; an active audit or CSV rerun still blocks this request.",
    ];
    return lines;
  }

  function renderReportAuditLaunchPreflight(request = collectReportAuditStartRequest()) {
    setText("report-audit-launch-preflight", reportAuditLaunchPreflightLines(request).join("\n"));
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
    if (!window.confirm("Start audit from Reports?")) {
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
      : "all loaded non-ignored rows (current filter is display-only)";
    if (!window.confirm(`Export rerun CSV for ${scope}?`)) return;
    setReportAuditCommandBusy("audit.export_rerun_csv", "report-audit-export-rerun-csv-button");
    setText("report-audit-export-status", "Exporting...");
    setText("report-audit-export-detail", "Exporting backend-owned rerun CSV...");
    try {
      const result = await apiPost("/api/audit/export-rerun-csv", request);
      appendReportAuditCommandResult(result);
      setText("report-audit-export-status", result.ok ? "Exported" : "Blocked");
      setText("report-audit-export-detail", formatReportAuditCommandDetail(result, request));
      await refreshReportsAuditData();
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
      collectReportAuditStartRequest,
      exportAuditRerunCsv,
      ignoreSelectedAuditRows,
      renderReportAuditLaunchPreflight,
      renderReportAuditProgressPanel,
      renderReportAuditRunningState,
      renderReportAuditSavedLocations,
      reportAuditBusyResult,
      reportAuditJsonDetail,
      reportAuditReviewCount,
      removeReportAuditLocationFromForm,
      saveReportAuditLocationFromForm,
      saveReportAuditScorePolicy,
      selectReportAuditSavedLocation,
      setReportAuditCommandBusy,
      startReportAuditFromForm,
      stopReportAuditFromForm,
    };
  }

  window.__reportsViewAuditCommandsModule = {
    createReportsAuditCommandsModule,
  };
})();
