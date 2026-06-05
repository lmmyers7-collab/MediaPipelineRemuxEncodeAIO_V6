/* eslint-disable max-lines-per-function */
(function () {
  function createLaunchStatusRenderModule(deps = {}) {
    const {
      byId = function () { return null; },
      commandEntryState = function () { return ""; },
      commandEntrySummary = function () { return ""; },
      commandResultDisplayMessage = null,
      jsonDetailText = function (options = {}) { return JSON.stringify(options.value, null, 2); },
      latestCommandEntry = function () { return null; },
      launchCommandCorrelationRows = null,
      launchCommandCorrelationStatus = null,
      launchCommandDiagnosticsActions = null,
      launchPipelineIsActive = function () { return false; },
      pipelineControllerStageSummary = function () { return "No active backend work."; },
      pipelineControllerState = function () { return "idle"; },
      pipelineProgressIsStuck = function () { return false; },
      setText = function () {},
      state = { lastLaunchCommandState: { snapshot: null, closeReadiness: null } },
    } = deps;

  function setPipelineControlMessage(message) {
    setText("control-status", message);
    setText("home-control-message", message);
  }

  function setPipelineSingleFileBrowseStatus(message) {
    setText("pipeline-single-file-browse-status", message);
  }

  function setControllerStatusText(id, text, state = "") {
    setText(id, text);
    const element = byId(id);
    if (!element) return;
    if (state) element.dataset.state = state;
    else delete element.dataset.state;
  }

  function renderPipelineControllerStatus(
    snapshot = state.lastLaunchCommandState.snapshot,
    closeReadiness = state.lastLaunchCommandState.closeReadiness,
    active = launchPipelineIsActive(snapshot, closeReadiness),
    stuck = pipelineProgressIsStuck(snapshot)
  ) {
    const state = pipelineControllerState(snapshot, closeReadiness, active, stuck);
    const panel = document.querySelector(".pipeline-controller-panel");
    if (panel) panel.dataset.pipelineControllerState = state;
    const controls = document.querySelector(".pipeline-controller-controls");
    if (controls) controls.dataset.liveState = stuck ? "stuck" : active ? "active" : "idle";

    setControllerStatusText("pipeline-controller-backend-status", snapshot ? "Started" : "Snapshot pending", snapshot ? "ok" : "warning");
    setText("pipeline-controller-backend-detail", snapshot ? "Backend snapshot loaded." : "Waiting for backend snapshot refresh.");

    const pipelineLabel = stuck ? "Review" : active ? "Active" : String(snapshot?.pipeline_state || closeReadiness?.state || "idle");
    setControllerStatusText("pipeline-controller-pipeline-state", pipelineLabel, state);
    setText("pipeline-controller-stage-summary", pipelineControllerStageSummary(snapshot, closeReadiness, active, stuck));

    const controlLabel = stuck ? "Emergency available" : active ? "Controls active" : "Idle";
    setControllerStatusText("pipeline-live-control-state", stuck ? "Stuck" : active ? "Active" : "Idle", state);
    setText("pipeline-controller-control-summary", stuck ? "Stuck progress can be force-stopped after review." : active ? "Pause, rescan, or graceful stop can be submitted." : "No active backend work; controls are disabled.");
    setText("pipeline-live-control-summary", stuck ? "Progress is non-idle without confirmed active work. Use Force Stop only after checking Diagnostics." : active ? "Backend work is active. Prefer Stop After Current before emergency control." : "No active backend work.");
    const controlSummary = byId("control-readiness-status");
    if (controlSummary && !controlSummary.textContent.trim()) controlSummary.textContent = controlLabel;

    const latestStart = latestCommandEntry((entry) => String(entry?.command || "").toLowerCase() === "pipeline.start");
    const launchStatus = String(byId("pipeline-launch-status")?.textContent || "Idle").trim() || "Idle";
    const launchStatusState = latestStart ? commandEntryState(latestStart) : (launchStatus.toLowerCase() === "idle" ? "idle" : "review");
    setControllerStatusText("pipeline-controller-last-start-status", latestStart ? (entryResultLabel(latestStart) || launchStatus) : launchStatus, launchStatusState);
    setText("pipeline-controller-last-start-summary", commandEntrySummary(latestStart, "No launch command in recent history."));
  }

  function entryResultLabel(entry) {
    if (!entry) return "";
    return String(entry.result || (entry.ok ? "ok" : entry.severity || "") || "").trim();
  }

  function setStartupBanner(text) {
    document.querySelectorAll(".pipeline-startup-banner").forEach((el) => {
      el.textContent = text;
      el.hidden = false;
      el.dataset.state = "loading";
    });
  }

  function clearStartupBanner() {
    document.querySelectorAll(".pipeline-startup-banner").forEach((el) => {
      el.hidden = true;
      el.textContent = "";
      delete el.dataset.state;
    });
  }

  function launchCommandStatusLabel(result, successLabel = "Started") {
    if (!result || typeof result !== "object") return "Unknown";
    if (result.ok) return result.severity === "warning" ? "Warning" : successLabel;
    return result.severity || "Blocked";
  }

  function launchSanitizedCauseText(value) {
    const text = String(value || "").trim();
    if (!text) return "";
    const lines = text.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
    const safe = lines.filter((line) => {
      if (/^Traceback\b/i.test(line)) return false;
      if (/^File\s+["']/i.test(line)) return false;
      if (/^\s*at\s+\S+/i.test(line)) return false;
      return true;
    });
    return (safe[0] || lines[0] || "").slice(0, 500);
  }

  function launchCommandRootCauseLines(result) {
    const payload = result && typeof result === "object" ? result : {};
    if (payload.ok) return [];
    const errors = Array.isArray(payload.errors) ? payload.errors : [];
    const warnings = Array.isArray(payload.warnings) ? payload.warnings : [];
    const cause = launchSanitizedCauseText(errors[0] || payload.message || warnings[0] || "");
    const lines = ["", "Root-cause summary:"];
    lines.push(`Cause: ${cause || "The backend rejected or failed the command without a detailed cause."}`);
    if (payload.command === "pipeline.start") {
      lines.push("Suggested next step: compare Backend Preflight, Launch Start Summary, Queue selected row, Run Logs, and Last Stderr before pressing Start again.");
    } else if (payload.command === "audit.start") {
      lines.push("Suggested next step: verify the library root/Outsource path, audit preflight, Run Logs, and Last Stderr before starting Audit again.");
    } else if (payload.command === "rerun.start") {
      lines.push("Suggested next step: verify the CSV path plus copy / keep / park policy, then inspect Run Logs and Last Stderr before starting CSV rerun again.");
    } else if (payload.command === "pending_publish.drain") {
      lines.push("Suggested next step: inspect Pending Publish drain safety, parked payload evidence, Run Logs, and Last Stderr before retrying drain.");
    } else {
      lines.push("Suggested next step: inspect the owning page and backend-allowlisted diagnostics evidence before retrying.");
    }
    lines.push("Stack traces are intentionally omitted from this operator surface; use Diagnostics log targets for raw detail.");
    return lines;
  }

  function launchCommandResultCorrelationLines(result, request = null) {
    const payload = result && typeof result === "object" ? result : {};
    if (!payload.command || typeof launchCommandCorrelationRows !== "function") return [];
    const raw = payload.raw && typeof payload.raw === "object" ? payload.raw : {};
    const entry = {
      ...payload,
      raw: {
        ...raw,
        data: raw.data && typeof raw.data === "object" ? raw.data : (payload.data && typeof payload.data === "object" ? payload.data : {}),
        request: request || raw.request || payload.request || {},
      },
    };
    const status = typeof launchCommandCorrelationStatus === "function" ? launchCommandCorrelationStatus(entry) : "not evaluated";
    const rows = launchCommandCorrelationRows(entry);
    const issue = payload.ok ? String(payload.severity || "info").toLowerCase() : "error";
    const success = payload.ok === true && !["warning", "error", "blocked"].includes(issue);
    const lines = [
      "",
      "Command evidence snapshot:",
      `Status: ${status}`,
    ];
    if (success) {
      lines.push("Backend command accepted. Rows below are cached evidence only; they did not block or authorize this submitted command.");
    }
    if (!rows.length) {
      lines.push("- No cached Backend Preflight, Launch intent, or Queue evidence rows were available.");
    } else {
      rows.slice(0, 8).forEach((row) => {
        lines.push(`- ${row.source} / ${row.checkpoint}: ${row.posture}; ${row.evidence || "no evidence"}; ${row.action || "review before retry"}`);
      });
      if (rows.length > 8) lines.push(`- ${rows.length - 8} more correlated evidence row(s) omitted.`);
    }
    if (typeof launchCommandDiagnosticsActions === "function") {
      const actions = launchCommandDiagnosticsActions(entry);
      if (success) {
        lines.push("Diagnostics guidance:");
        lines.push("Use Diagnostics only if Home, Launch, Progress, or ActiveJobs disagree with this successful backend result.");
      } else {
        const readTargets = actions.filter((action) => action.kind === "tail").map((action) => action.target).join(", ") || "none";
        const openTargets = actions.filter((action) => action.kind !== "tail").map((action) => action.target).join(", ") || "none";
        lines.push("Diagnostics retry guidance:");
        lines.push(`Read-first targets: ${readTargets}`);
        lines.push(`Open-next targets: ${openTargets}`);
      }
    }
    lines.push("Evidence is explanatory only; backend start routes remain authoritative at submission time.");
    return lines;
  }

  function formatLaunchCommandDetail(result, request = null) {
    const payload = result && typeof result === "object" ? result : {
      ok: false,
      severity: "error",
      message: String(result || "Unknown command result."),
    };
    const lines = [
      `Command: ${payload.command || "unknown"}`,
      `Result: ${payload.ok ? "ok" : "blocked"}${payload.severity ? ` (${payload.severity})` : ""}`,
    ];
    const displayMessage = typeof commandResultDisplayMessage === "function"
      ? commandResultDisplayMessage(payload)
      : String(payload.message || "");
    if (displayMessage) {
      lines.push("", displayMessage);
    }
    lines.push(...launchCommandRootCauseLines(payload));
    lines.push(...launchCommandResultCorrelationLines(payload, request));
    if (payload.refresh_hint) {
      lines.push("", `Refresh hint: ${payload.refresh_hint}`);
    }
    if (payload.data && Object.keys(payload.data).length) {
      lines.push("", "Backend data:", jsonDetailText({
        label: "Backend data JSON",
        value: payload.data,
        intro: "Read-only backend command result data.",
      }));
    }
    if (request) {
      lines.push("", "Submitted request:", jsonDetailText({
        label: "Submitted request JSON",
        value: request,
        intro: "Read-only request payload that was submitted to the backend command route.",
      }));
    }
    return lines.join("\n");
  }

  function renderLaunchCommandResult(statusId, detailId, result, request = null, successLabel = "Started") {
    setText(statusId, launchCommandStatusLabel(result, successLabel));
    if (detailId) {
      setText(detailId, formatLaunchCommandDetail(result, request));
    }
  }

    return {
      setPipelineControlMessage,
      setPipelineSingleFileBrowseStatus,
      setControllerStatusText,
      renderPipelineControllerStatus,
      entryResultLabel,
      setStartupBanner,
      clearStartupBanner,
      launchCommandStatusLabel,
      launchSanitizedCauseText,
      launchCommandRootCauseLines,
      launchCommandResultCorrelationLines,
      formatLaunchCommandDetail,
      renderLaunchCommandResult,
    };
  }

  window.__launchStatusRenderModule = {
    createLaunchStatusRenderModule,
  };
})();
