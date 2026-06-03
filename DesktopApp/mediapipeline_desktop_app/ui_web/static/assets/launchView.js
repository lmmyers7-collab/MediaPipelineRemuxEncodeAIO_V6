(function () {
  const launchReadinessView = window.mediaPipelineLaunchReadinessView || {};
  const launchReadinessStatus = window.launchReadinessStatus || launchReadinessView.launchReadinessStatus || function () { return "Checking"; };
  const launchReadinessLines = window.launchReadinessLines || launchReadinessView.launchReadinessLines || function () { return []; };
  const renderLaunchReadiness = window.renderLaunchReadiness || launchReadinessView.renderLaunchReadiness || function () {};
  const launchHistoryView = window.mediaPipelineLaunchHistoryView || {};
  const isLaunchCommand = window.isLaunchCommand || launchHistoryView.isLaunchCommand || function () { return false; };
  const launchHistoryLine = window.launchHistoryLine || launchHistoryView.launchHistoryLine || function () { return ""; };
  const renderLaunchCommandHistory = window.renderLaunchCommandHistory || launchHistoryView.renderLaunchCommandHistory || function () {};
  const domHelpers = window.mediaPipelineDom || {};
  const jsonDetailText = domHelpers.jsonDetailText || function (options = {}) {
    const label = options.label || "JSON detail";
    try {
      return `${label}:\n${JSON.stringify(options.value, null, 2)}`;
    } catch (error) {
      return `${label}:\nJSON render error: ${error instanceof Error ? error.message : String(error)}`;
    }
  };
  const renderJsonDetail = domHelpers.renderJsonDetail || function (id, options = {}) {
    setText(id, jsonDetailText(options));
  };
  const controlActionLabels = {
    pause: "Pause / Resume",
    rescan: "Rescan",
    stop: "Stop After Current",
    kill: "Force Stop",
  };

  const controlConfirmMessages = {
    rescan: "Request a queue rescan flag for the running pipeline? This does not start a new run or touch media, but it can change what the active loop sees next.",
    stop: "Request Stop After Current? The current file may finish; no new file should start. Use Force Stop only if the run is stalled.",
    kill: "Force stop immediately? This terminates any active pipeline processes and resets stuck progress state to idle. The current file may be left partial in scratch; source media should not be touched.",
  };

  const launchCommandButtonIds = [
    "pipeline-start-button",
    "pending-drain-button",
    "audit-start-button",
    "rerun-start-button",
  ];
  const LAUNCH_TAB_STORAGE_KEY = "mediapipeline-launch-tab";
  let launchCommandInFlight = false;
  let controlCommandInFlight = false;
  let pipelineFileBrowseInFlight = false;
  let pipelineStartScope = "queue";
  let selectedLaunchSettingsRiskKey = "";
  let selectedLaunchPolicyBoundaryKey = "";
  let selectedLaunchSettingsIntentKey = "";
  let selectedLaunchScopeReconciliationKey = "";
  let selectedLaunchStartDecisionKey = "";
  let selectedLaunchRealMediaProofKey = "";
  let selectedLaunchSampleExecutionKey = "";
  let selectedLaunchAuditLogRowKey = "";
  let lastLaunchAuditLogRows = [];
  let lastLaunchAuditLogEmptyMessage = "No audit rows loaded.";
  let lastLaunchRealMediaProofContext = {};
  let lastLaunchCommandState = { snapshot: null, closeReadiness: null };

  function launchTabIds() {
    return ["readiness", "pipeline", "audit", "rerun", "history"];
  }

  function activateLaunchTab(tabId) {
    const page = document.querySelector('[data-page-panel="launch"]');
    if (!page) return;
    const selected = launchTabIds().includes(tabId) ? tabId : "pipeline";
    const buttons = Array.from(page.querySelectorAll(".settings-tab-btn[data-launch-tab]"));
    const panels = Array.from(page.querySelectorAll(":scope > .launch-tab-panel[data-launch-tab-panel]"));
    buttons.forEach((button) => {
      const active = button.dataset.launchTab === selected;
      button.setAttribute("aria-selected", String(active));
    });
    panels.forEach((panel) => {
      panel.classList.toggle("is-active", panel.dataset.launchTabPanel === selected);
    });
    try { localStorage.setItem(LAUNCH_TAB_STORAGE_KEY, selected); } catch (_) {}
    if (typeof updatePagePanelEmptyStates === "function") updatePagePanelEmptyStates();
  }

  function initLaunchTabNav() {
    const page = document.querySelector('[data-page-panel="launch"]');
    if (!page) return;
    const buttons = Array.from(page.querySelectorAll(".settings-tab-btn[data-launch-tab]"));
    const panels = Array.from(page.querySelectorAll(":scope > .launch-tab-panel[data-launch-tab-panel]"));
    if (!buttons.length || !panels.length) return;
    buttons.forEach((button) => {
      button.addEventListener("click", () => activateLaunchTab(button.dataset.launchTab || "pipeline"));
    });
    let stored = "pipeline";
    try { stored = localStorage.getItem(LAUNCH_TAB_STORAGE_KEY) || "pipeline"; } catch (_) {}
    activateLaunchTab(stored);
  }

  document.addEventListener("click", (event) => {
    const button = event.target?.closest?.('[data-page-panel="launch"] .settings-tab-btn[data-launch-tab]');
    if (!button) return;
    activateLaunchTab(button.dataset.launchTab || "pipeline");
  });

  function launchPipelineIsActive(snapshot = lastLaunchCommandState.snapshot, closeReadiness = lastLaunchCommandState.closeReadiness) {
    if (closeReadiness?.safe_to_close === false || closeReadiness?.active_work === true) return true;
    const state = String(snapshot?.pipeline_state || closeReadiness?.state || "").trim().toLowerCase();
    return ["processing", "running", "active", "publishing", "audit", "rerun", "stopping", "paused"].includes(state);
  }

  function pipelineProgressIsStuck(snapshot = lastLaunchCommandState.snapshot) {
    const stage = String(snapshot?.progress?.CurrentStage || "").toLowerCase().trim();
    return !!stage && stage !== "idle" && stage !== "startup";
  }

  function launchPauseRequested(snapshot = lastLaunchCommandState.snapshot) {
    const progress = snapshot?.progress && typeof snapshot.progress === "object" ? snapshot.progress : {};
    return Boolean(progress.PauseRequested || progress.pause_requested || progress.Paused || progress.paused);
  }

  function launchRequestFieldValue(request, key) {
    const value = request && typeof request === "object" ? request[key] : undefined;
    if (value === undefined || value === null) return "";
    return String(value);
  }

  function launchPreflightRequestMatches(payload, request, keys) {
    if (!payload || typeof payload !== "object") return false;
    const payloadRequest = payload.request && typeof payload.request === "object" ? payload.request : {};
    return keys.every((key) => launchRequestFieldValue(payloadRequest, key) === launchRequestFieldValue(request, key));
  }

  function launchTargetGate(target, request, options = {}) {
    const payload = launchBackendPreflightPayloadForTarget(target);
    const allowMissing = Boolean(options.allowMissing);
    const matchKeys = Array.isArray(options.matchKeys) ? options.matchKeys : [];
    if (!payload) {
      return allowMissing
        ? { blocked: false, reason: "Backend start route will re-check queue, settings, schedule, and process locks at submission time." }
        : { blocked: true, reason: "Refresh Backend Preflight before using this start control." };
    }
    if (matchKeys.length && !launchPreflightRequestMatches(payload, request, matchKeys)) {
      return allowMissing
        ? { blocked: false, reason: "Cached Backend Preflight is for different form values; Validate remains available and backend will re-check at submission time." }
        : { blocked: true, reason: "Refresh Backend Preflight for the selected mode and form values before using this start control." };
    }
    const status = launchBackendPreflightOverallStatus([payload]);
    if (launchStartDecisionPostureFromStatus(status) === "blocked") {
      return { blocked: true, reason: "Resolve blocked Backend Preflight checks before using this start control." };
    }
    return { blocked: false, reason: "Backend start route will re-check queue, settings, schedule, and process locks at submission time." };
  }

  function launchStartDecisionGate(request) {
    const rows = typeof launchStartDecisionRows === "function" ? launchStartDecisionRows(request) : [];
    const posture = typeof launchStartDecisionStatus === "function"
      ? launchStartDecisionPostureFromStatus(launchStartDecisionStatus(rows))
      : launchStartDecisionWorstPosture(rows.map((row) => row.posture));
    if (posture === "blocked") {
      return { blocked: true, reason: "Resolve blocked Launch Start Summary rows before using this start control." };
    }
    return { blocked: false, reason: "" };
  }

  function launchButtonGate(id) {
    if (id === "pipeline-start-button") {
      const request = collectPipelineStartRequest();
      const allowMissing = String(request.mode || "") === "validate";
      const targetGate = launchTargetGate("pipeline", request, {
        allowMissing,
        matchKeys: ["mode", "sleep_seconds", "schedule_override", "single_file"],
      });
      if (targetGate.blocked) return targetGate;
      const decisionGate = launchStartDecisionGate(request);
      if (decisionGate.blocked) return decisionGate;
      return targetGate;
    }
    if (id === "pending-drain-button") {
      const request = { mode: "drain_pending_pushes", sleep_seconds: 30, schedule_override: "" };
      const targetGate = launchTargetGate("pipeline", request, {
        allowMissing: false,
        matchKeys: ["mode", "sleep_seconds", "schedule_override"],
      });
      if (targetGate.blocked) return targetGate;
      const decisionGate = launchStartDecisionGate(request);
      return decisionGate.blocked ? decisionGate : targetGate;
    }
    if (id === "audit-start-button") {
      const request = collectAuditStartRequest();
      const targetGate = launchTargetGate("audit", request, {
        allowMissing: false,
        matchKeys: ["library_root", "include_sidecars"],
      });
      if (targetGate.blocked) return targetGate;
      const decisionGate = launchStartDecisionGate(collectPipelineStartRequest());
      return decisionGate.blocked ? decisionGate : targetGate;
    }
    if (id === "rerun-start-button") {
      const request = collectRerunStartRequest();
      const targetGate = launchTargetGate("rerun", request, {
        allowMissing: false,
        matchKeys: ["csv_path", "stage_mode", "original_mode", "return_mode"],
      });
      if (targetGate.blocked) return targetGate;
      const decisionGate = launchStartDecisionGate(collectPipelineStartRequest());
      return decisionGate.blocked ? decisionGate : targetGate;
    }
    return { blocked: false, reason: "Backend start route will re-check queue, settings, schedule, and process locks at submission time." };
  }

  function setButtonClass(button, className) {
    if (!button) return;
    button.className = className;
  }

  function setButtonDisabledWithReason(button, disabled, reason) {
    if (!button) return;
    button.disabled = Boolean(disabled);
    button.setAttribute("aria-disabled", disabled ? "true" : "false");
    if (reason) button.title = reason;
  }

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

  function pipelineSingleFileValue() {
    return String(byId("pipeline-start-single-file")?.value || "").trim();
  }

  function commandHistoryEntries() {
    if (typeof window.getCommandHistory === "function") return window.getCommandHistory();
    if (typeof window.mediaPipelineCommandHistory?.getCommandHistory === "function") return window.mediaPipelineCommandHistory.getCommandHistory();
    return [];
  }

  function latestCommandEntry(predicate) {
    const history = commandHistoryEntries();
    return Array.isArray(history) ? history.find(predicate) || null : null;
  }

  function commandEntryState(entry) {
    if (!entry) return "";
    const severity = String(entry.severity || entry.result || "").toLowerCase();
    if (entry.ok === true && !["warning", "error", "blocked"].some((token) => severity.includes(token))) return "ok";
    if (severity.includes("warning")) return "warning";
    if (severity.includes("error") || severity.includes("blocked") || entry.ok === false) return "blocked";
    return "review";
  }

  function commandEntrySummary(entry, emptyText) {
    if (!entry) return emptyText;
    const message = String(entry.message || entry.command || "").replace(/\s+/g, " ").trim();
    const prefix = entry.at ? `${entry.at} - ` : "";
    return `${prefix}${message || entry.command || "Command recorded."}`.slice(0, 220);
  }

  function pipelineControllerState(snapshot, closeReadiness, active, stuck) {
    if (stuck) return "stuck";
    if (active) return "active";
    const state = String(snapshot?.pipeline_state || closeReadiness?.state || "idle").trim().toLowerCase();
    if (["failed", "blocked", "error"].includes(state)) return "blocked";
    if (["completed", "idle", ""].includes(state)) return "idle";
    return "review";
  }

  function pipelineControllerStageSummary(snapshot, closeReadiness, active, stuck) {
    const progress = snapshot?.progress && typeof snapshot.progress === "object" ? snapshot.progress : {};
    const stage = String(progress.CurrentStage || progress.current_stage || "").trim();
    const status = String(progress.Status || progress.status || "").trim();
    if (stuck) return stage ? `Progress reports ${stage}; no matching active work is confirmed.` : "Progress appears stuck; review Diagnostics before forcing stop.";
    if (active) return [stage ? `Stage: ${stage}` : "Backend work is active.", status].filter(Boolean).join(" - ");
    if (closeReadiness?.reason) return `Close-readiness: ${closeReadiness.reason}`;
    return "No active backend work.";
  }

  function renderPipelineControllerStatus(
    snapshot = lastLaunchCommandState.snapshot,
    closeReadiness = lastLaunchCommandState.closeReadiness,
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

  function updateLaunchCommandButtonStates(snapshot = lastLaunchCommandState.snapshot, closeReadiness = lastLaunchCommandState.closeReadiness) {
    lastLaunchCommandState = { snapshot: snapshot || null, closeReadiness: closeReadiness || null };
    const active = launchPipelineIsActive(snapshot, closeReadiness);
    const stuck = pipelineProgressIsStuck(snapshot);
    syncPipelineScopeControls();
    if (active) clearStartupBanner();
    const startReason = active
      ? "Disabled while backend close-readiness reports active work. Stop or wait for idle before starting another pipeline/audit/rerun command."
      : "Backend start route will re-check queue, settings, schedule, and process locks at submission time.";
    launchCommandButtonIds.forEach((id) => {
      const button = byId(id);
      const gate = active || launchCommandInFlight ? { blocked: false, reason: "" } : launchButtonGate(id);
      setButtonDisabledWithReason(
        button,
        launchCommandInFlight || active || gate.blocked,
        launchCommandInFlight ? "A launch command is already in progress." : (active ? startReason : (gate.reason || startReason))
      );
    });

    const singleFile = String(byId("pipeline-start-single-file")?.value || "").trim();
    setButtonDisabledWithReason(
      byId("pipeline-single-file-browse-button"),
      pipelineFileBrowseInFlight || launchCommandInFlight || active,
      pipelineFileBrowseInFlight
        ? "Windows file browser is already open."
        : (launchCommandInFlight || active ? startReason : "Open the backend-owned Windows file browser for single-file staging.")
    );
    setButtonDisabledWithReason(
      byId("pipeline-single-file-clear-button"),
      pipelineFileBrowseInFlight || launchCommandInFlight || active || !singleFile,
      pipelineFileBrowseInFlight
        ? "Windows file browser is already open."
        : (singleFile ? "Clear the staged single-file path." : "No single-file path is staged.")
    );

    const pauseLabel = active ? (launchPauseRequested(snapshot) ? "Resume" : "Pause") : "Pause / Resume";
    document.querySelectorAll('[data-control-action="pause"]').forEach((button) => {
      button.textContent = pauseLabel;
    });
    document.querySelectorAll("[data-control-action]").forEach((button) => {
      const action = String(button.dataset.controlAction || "").toLowerCase();
      const killable = active || stuck;
      const disabled = action === "kill" ? (controlCommandInFlight || !killable) : (controlCommandInFlight || !active);
      const busyReason = "A pipeline control command is already in progress.";
      const idleReason = action === "kill"
        ? "Disabled: no active backend work and no stuck progress state detected."
        : "Disabled while no active backend work is reported.";
      const activeReason = {
        pause: `${pauseLabel} the active backend pipeline.`,
        rescan: "Request a queue rescan flag for the running backend pipeline.",
        stop: "Request graceful Stop After Current for the active backend pipeline.",
        kill: "Force stop: terminates active processes and resets stuck progress to idle.",
      }[action] || "Backend-owned pipeline control.";
      const effective = action === "kill" ? killable : active;
      setButtonDisabledWithReason(button, disabled, controlCommandInFlight ? busyReason : (effective ? activeReason : idleReason));
      if (action === "pause") setButtonClass(button, active ? "primary-button" : "secondary-button");
      if (action === "rescan") setButtonClass(button, "secondary-button");
      if (action === "stop") setButtonClass(button, active ? "danger-button pipeline-stop-button" : "secondary-button pipeline-stop-button");
      if (action === "kill") {
        setButtonClass(button, button.classList.contains("topbar-emergency-control") ? "danger-button emergency-button topbar-emergency-control" : "danger-button emergency-button pipeline-emergency-button");
        if (button.classList.contains("topbar-emergency-control")) {
          button.hidden = !killable;
          button.setAttribute("aria-hidden", killable ? "false" : "true");
        } else {
          const emergency = button.closest?.(".pipeline-controller-emergency");
          if (emergency) {
            emergency.hidden = !killable;
            emergency.setAttribute("aria-hidden", killable ? "false" : "true");
          }
        }
      }
    });
    renderPipelineControllerStatus(snapshot, closeReadiness, active, stuck);
  }

  function setLaunchCommandBusy(isBusy) {
    launchCommandInFlight = Boolean(isBusy);
    updateLaunchCommandButtonStates();
  }

  function rejectLaunchCommandWhileBusy(command, statusId, detailId) {
    if (!launchCommandInFlight) return false;
    const result = {
      command,
      ok: false,
      severity: "warning",
      message: "Another launch command is already in progress.",
    };
    appendCommandResult(result);
    setText(statusId, "Busy");
    if (detailId) setText(detailId, result.message);
    return true;
  }

  function setControlCommandBusy(isBusy) {
    controlCommandInFlight = Boolean(isBusy);
    updateLaunchCommandButtonStates();
  }

  function rejectControlCommandWhileBusy(action) {
    if (!controlCommandInFlight) return false;
    const normalized = String(action || "unknown").trim().toLowerCase() || "unknown";
    const result = {
      command: `pipeline.control.${normalized}`,
      ok: false,
      severity: "warning",
      message: "Another pipeline control command is already in progress.",
    };
    appendCommandResult(result);
    setPipelineControlMessage(result.message);
    return true;
  }

  function shouldConfirmControl(action) {
    return Object.prototype.hasOwnProperty.call(controlConfirmMessages, action);
  }

  function confirmControlAction(action) {
    if (!shouldConfirmControl(action)) return true;
    return window.confirm(controlConfirmMessages[action]);
  }

  function pipelineModeLabel(mode) {
    const labels = {
      validate: "Validate",
      once: "Run Once",
      continuous: "Continuous",
      drain_pending_pushes: "Publish Parked",
    };
    return labels[mode] || mode || "Pipeline";
  }

  function pipelineModeStartLabel(mode) {
    return `Start ${pipelineModeLabel(mode)}`;
  }

  function syncPipelineScopeControls() {
    const singleFile = pipelineSingleFileValue();
    if (singleFile) pipelineStartScope = "single_file";
    const selectedScope = pipelineStartScope === "single_file" ? "single_file" : "queue";
    document.querySelectorAll("[data-pipeline-scope-preset]").forEach((button) => {
      const active = String(button.dataset.pipelineScopePreset || "") === selectedScope;
      button.classList.toggle("is-active", active);
      button.setAttribute("aria-pressed", String(active));
    });
    const singleFileContainer = document.querySelector("[data-pipeline-single-file-container]");
    if (singleFileContainer) {
      const show = selectedScope === "single_file" || Boolean(singleFile);
      singleFileContainer.hidden = !show;
      singleFileContainer.setAttribute("aria-hidden", show ? "false" : "true");
    }
    const status = byId("pipeline-single-file-browse-status");
    if (status && !singleFile && selectedScope === "queue" && !pipelineFileBrowseInFlight) {
      status.textContent = "Queue scope selected. Use Single File to stage one path.";
    }
  }

  function selectPipelineScopePreset(scope) {
    const selectedScope = String(scope || "").trim() === "single_file" ? "single_file" : "queue";
    pipelineStartScope = selectedScope;
    if (selectedScope === "queue") {
      const input = byId("pipeline-start-single-file");
      if (input && input.value) {
        input.value = "";
        input.dispatchEvent(new Event("input", { bubbles: true }));
      }
    }
    syncPipelineScopeControls();
    renderAllLaunchPreflights();
    updateLaunchCommandButtonStates();
  }

  function syncPipelineModeControls() {
    const selectedMode = byId("pipeline-start-mode")?.value || "validate";
    document.querySelectorAll("[data-pipeline-mode-preset]").forEach((button) => {
      const active = String(button.dataset.pipelineModePreset || "") === selectedMode;
      button.classList.toggle("is-active", active);
      button.setAttribute("aria-pressed", String(active));
    });
    const startButton = byId("pipeline-start-button");
    if (startButton && !launchCommandInFlight) {
      startButton.textContent = pipelineModeStartLabel(selectedMode);
    }
    syncPipelineScopeControls();
  }

  function selectPipelineModePreset(mode) {
    const selectedMode = String(mode || "").trim();
    const modeSelect = byId("pipeline-start-mode");
    if (!selectedMode || !modeSelect) return;
    modeSelect.value = selectedMode;
    syncPipelineModeControls();
    modeSelect.dispatchEvent(new Event("change", { bubbles: true }));
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

  function launchAuditLogRowKey(item) {
    return [
      item?.source_csv || "",
      item?.path || "",
      item?.relative_path || "",
      item?.primary_issue_code || "",
      item?.priority_score || "",
    ].join("\u001f").toLowerCase();
  }

  function launchAuditLogEmptyStateMessage(audit, rows) {
    if (audit?.error) {
      return `Audit log unavailable: ${audit.error}. Run a fresh audit from this panel or inspect Diagnostics > Audit Reports.`;
    }
    const warnings = Array.isArray(audit?.warnings) ? audit.warnings.filter(Boolean) : [];
    if (warnings.length) return `Audit log loaded with warning: ${warnings.join(" | ")}`;
    if (!rows.length) return "No audit rows found. Run Audit from this panel, or use Reports priority mode if you only need priority rows.";
    return "No audit rows available.";
  }

  function getSelectedLaunchAuditLogRow() {
    if (!selectedLaunchAuditLogRowKey) return null;
    return lastLaunchAuditLogRows.find((row) => launchAuditLogRowKey(row) === selectedLaunchAuditLogRowKey) || null;
  }

  function renderLaunchAuditLogDetail(item) {
    if (!item) {
      setText("audit-launch-log-detail", "No audit row selected. Select a row to inspect priority score, issue bucket, suggested action, and source CSV.");
      return;
    }
    const detail = [
      "Launch audit log selected row:",
      `Title: ${item.lookup_title || ""}`,
      `Media: ${item.media_type || ""}`,
      `Bucket: ${item.effective_bucket || ""}`,
      `Priority: ${item.priority_fix_level || ""} (${item.priority_score || 0})`,
      `Issue: ${item.primary_issue_code || ""}`,
      `Suggested action: ${item.primary_suggested_action || ""}`,
      `Messages: ${item.issue_messages || ""}`,
      `Path: ${item.path || ""}`,
      `Relative: ${item.relative_path || ""}`,
      `Source CSV: ${item.source_csv || ""}`,
      "",
      "Guardrail: this Launch copy of the audit log is read-only evidence. It cannot rerun, publish, rename, delete, save settings, or touch media.",
    ];
    setText("audit-launch-log-detail", detail.join("\n"));
  }

  function selectLaunchAuditLogRow(item) {
    selectedLaunchAuditLogRowKey = launchAuditLogRowKey(item);
    renderLaunchAuditLogDetail(item || null);
    renderLaunchAuditLogRows();
  }

  function launchAuditLogRowStatus(item) {
    const bucket = String(item?.effective_bucket || "").toUpperCase();
    const priority = String(item?.priority_fix_level || "").toUpperCase();
    if (bucket === "REDOWNLOAD_CANDIDATE") return "blocked";
    if (bucket === "RERUN_PIPELINE" || priority === "HIGH") return "warning";
    if (bucket === "OK") return "match";
    return "";
  }

  function renderLaunchAuditLogRows() {
    setText("audit-launch-log-status", `${lastLaunchAuditLogRows.length} row${lastLaunchAuditLogRows.length === 1 ? "" : "s"}`);
    const tbody = byId("audit-launch-log-rows");
    if (!tbody) return;
    if (!lastLaunchAuditLogRows.length) {
      clearRows(tbody, 6, lastLaunchAuditLogEmptyMessage);
      updateTableStatusLegend("audit-launch-log-table-legend", tbody, "Audit log rows");
      return;
    }
    tbody.replaceChildren();
    lastLaunchAuditLogRows.slice(0, 250).forEach((item) => {
      const row = document.createElement("tr");
      const key = launchAuditLogRowKey(item);
      row.dataset.status = launchAuditLogRowStatus(item);
      row.dataset.rowKey = key;
      appendCells(row, [
        item.priority_score || "",
        item.priority_fix_level || "",
        item.effective_bucket || "",
        item.media_type || "",
        item.lookup_title || item.relative_path || item.path || "",
        item.primary_issue_code || item.issue_messages || item.primary_suggested_action || "",
      ], ["num", null, null, null, null, null]);
      if (typeof makeRowSelectable === "function") {
        makeRowSelectable(row, () => selectLaunchAuditLogRow(item), {
          selected: Boolean(key && key === selectedLaunchAuditLogRowKey),
          label: `Launch audit log row ${item.lookup_title || item.relative_path || item.path || ""}`,
        });
      } else {
        row.addEventListener("click", () => selectLaunchAuditLogRow(item));
      }
      tbody.appendChild(row);
    });
    updateTableStatusLegend("audit-launch-log-table-legend", tbody, "Audit log rows");
  }

  function renderLaunchAuditLog(audit) {
    const payload = audit && typeof audit === "object" ? audit : {};
    const rows = Array.isArray(payload.rows) ? payload.rows : [];
    lastLaunchAuditLogRows = rows;
    if (selectedLaunchAuditLogRowKey && !rows.some((row) => launchAuditLogRowKey(row) === selectedLaunchAuditLogRowKey)) {
      selectedLaunchAuditLogRowKey = "";
    }
    lastLaunchAuditLogEmptyMessage = launchAuditLogEmptyStateMessage(payload, rows);
    const warnings = Array.isArray(payload.warnings) ? payload.warnings.filter(Boolean) : [];
    const summary = [
      payload.source ? `Source: ${payload.source}` : "",
      `Priority CSV mode: ${payload.priority_only ? "yes" : "no"}`,
      `Rows: ${payload.count || rows.length || 0}`,
      `High priority: ${payload.high_priority_count || 0}`,
      `Rerun: ${payload.rerun_count || 0}`,
      `Redownload: ${payload.redownload_count || 0}`,
      `Review: ${payload.review_count || 0}`,
      `Duplicate groups: ${payload.duplicate_group_count || 0}`,
      ...warnings,
      !rows.length ? lastLaunchAuditLogEmptyMessage : "",
      "Mutation guardrail: this is the same read-only audit-results evidence shown in Reports. Audit launch and report writing remain backend-owned.",
    ].filter(Boolean);
    setText("audit-launch-log-summary", summary.join("\n") || "No audit log loaded.");
    renderLaunchAuditLogDetail(getSelectedLaunchAuditLogRow());
    renderLaunchAuditLogRows();
  }

  const launchRiskState = {
    get selectedLaunchSettingsRiskKey() {
      return selectedLaunchSettingsRiskKey;
    },
    set selectedLaunchSettingsRiskKey(value) {
      selectedLaunchSettingsRiskKey = value || "";
    },
    get selectedLaunchPolicyBoundaryKey() {
      return selectedLaunchPolicyBoundaryKey;
    },
    set selectedLaunchPolicyBoundaryKey(value) {
      selectedLaunchPolicyBoundaryKey = value || "";
    },
    get selectedLaunchSettingsIntentKey() {
      return selectedLaunchSettingsIntentKey;
    },
    set selectedLaunchSettingsIntentKey(value) {
      selectedLaunchSettingsIntentKey = value || "";
    },
  };

  const launchRiskModule = window.__launchViewRiskModule || {};
  delete window.__launchViewRiskModule;
  const launchRiskFallbackRows = function () { return []; };
  const launchRiskFallbackLines = function () { return []; };
  const launchRiskFallbackStatus = function () { return "Unknown"; };
  const launchRiskFallbackWorkspace = function () { return {}; };
  const launchRiskFallbackPayload = function (payload = null) { return payload && typeof payload === "object" ? payload : {}; };
  const launchRiskFallbackRender = function () {};
  const launchRisk = typeof launchRiskModule.createLaunchRiskModule === "function"
    ? launchRiskModule.createLaunchRiskModule({
      appendCells: typeof appendCells === "function" ? appendCells : window.appendCells,
      byId: typeof byId === "function" ? byId : window.byId,
      clearRows: typeof clearRows === "function" ? clearRows : window.clearRows,
      collectPipelineStartRequest: (...args) => collectPipelineStartRequest(...args),
      formatSettingsChoiceLabel: typeof window.formatSettingsChoiceLabel === "function" ? window.formatSettingsChoiceLabel : (typeof formatSettingsChoiceLabel === "function" ? formatSettingsChoiceLabel : null),
      getCommandHistory: typeof window.getCommandHistory === "function" ? () => window.getCommandHistory() : (typeof getCommandHistory === "function" ? () => getCommandHistory() : () => []),
      getLastLaunchReadinessPayload: typeof window.getLastLaunchReadinessPayload === "function" ? () => window.getLastLaunchReadinessPayload() : (typeof getLastLaunchReadinessPayload === "function" ? () => getLastLaunchReadinessPayload() : () => ({})),
      getLastQueueRows: typeof window.getLastQueueRows === "function" ? () => window.getLastQueueRows() : (typeof getLastQueueRows === "function" ? () => getLastQueueRows() : () => []),
      getLastSettings: typeof window.getLastSettings === "function" ? () => window.getLastSettings() : (typeof getLastSettings === "function" ? () => getLastSettings() : () => ({})),
      isLaunchCommand,
      launchHistoryLine: typeof launchHistoryLine === "function" ? launchHistoryLine : window.launchHistoryLine,
      makeRowSelectable: typeof makeRowSelectable === "function" ? makeRowSelectable : window.makeRowSelectable,
      pipelineModeLabel,
      queueCurrentFilterScope: typeof window.queueCurrentFilterScope === "function" ? window.queueCurrentFilterScope : (typeof queueCurrentFilterScope === "function" ? queueCurrentFilterScope : null),
      queueFilterScopeDetailLines: typeof window.queueFilterScopeDetailLines === "function" ? window.queueFilterScopeDetailLines : (typeof queueFilterScopeDetailLines === "function" ? queueFilterScopeDetailLines : null),
      scheduleDisplayValue: typeof scheduleDisplayValue === "function" ? scheduleDisplayValue : window.scheduleDisplayValue,
      setText: typeof setText === "function" ? setText : window.setText,
      settingsCommandHistoryLine: typeof window.settingsCommandHistoryLine === "function" ? window.settingsCommandHistoryLine : (typeof settingsCommandHistoryLine === "function" ? settingsCommandHistoryLine : null),
      settingsLaunchImpactRows: typeof window.settingsLaunchImpactRows === "function" ? window.settingsLaunchImpactRows : (typeof settingsLaunchImpactRows === "function" ? settingsLaunchImpactRows : null),
      settingsLaunchImpactStatus: typeof window.settingsLaunchImpactStatus === "function" ? window.settingsLaunchImpactStatus : (typeof settingsLaunchImpactStatus === "function" ? settingsLaunchImpactStatus : null),
      settingsOperatorTrustStatus: typeof window.settingsOperatorTrustStatus === "function" ? window.settingsOperatorTrustStatus : (typeof settingsOperatorTrustStatus === "function" ? settingsOperatorTrustStatus : null),
      settingsPatchEffectiveChangedEntries: typeof window.settingsPatchEffectiveChangedEntries === "function" ? window.settingsPatchEffectiveChangedEntries : (typeof settingsPatchEffectiveChangedEntries === "function" ? settingsPatchEffectiveChangedEntries : null),
      settingsPatchIsTouched: typeof window.settingsPatchIsTouched === "function" ? window.settingsPatchIsTouched : (typeof settingsPatchIsTouched === "function" ? settingsPatchIsTouched : null),
      settingsPolicyDeltaRows: typeof window.settingsPolicyDeltaRows === "function" ? window.settingsPolicyDeltaRows : (typeof settingsPolicyDeltaRows === "function" ? settingsPolicyDeltaRows : null),
      settingsPolicyDeltaStatus: typeof window.settingsPolicyDeltaStatus === "function" ? window.settingsPolicyDeltaStatus : (typeof settingsPolicyDeltaStatus === "function" ? settingsPolicyDeltaStatus : null),
      state: launchRiskState,
      updateTableStatusLegend: typeof updateTableStatusLegend === "function" ? updateTableStatusLegend : window.updateTableStatusLegend,
    })
    : {};
  const {
    launchSettingsWorkspace = launchRiskFallbackWorkspace,
    launchSettingsTrustStatus = launchRiskFallbackStatus,
    launchSettingsDecision = function () { return { decision: "unknown", status: "Unknown", mode: "unknown", reasons: [], guidance: "Launch settings risk module is unavailable." }; },
    launchSettingsDecisionLines = launchRiskFallbackLines,
    launchUnsavedSettingsPatchLines = launchRiskFallbackLines,
    launchSettingsRiskLines = launchRiskFallbackLines,
    launchSettingsSeverityRank = function () { return 3; },
    launchRealMediaReadinessLines = launchRiskFallbackLines,
    launchSettingsRiskRows = launchRiskFallbackRows,
    launchSettingsRiskStatus = launchRiskFallbackStatus,
    launchSettingsRiskSummaryLines = launchRiskFallbackLines,
    launchSettingsRiskDetailLines = launchRiskFallbackLines,
    renderLaunchSettingsRiskHandoff = launchRiskFallbackRender,
    launchPolicyBoundaryRows = launchRiskFallbackRows,
    launchPolicyBoundaryStatus = launchRiskFallbackStatus,
    launchPolicyBoundarySummaryLines = launchRiskFallbackLines,
    launchPolicyBoundaryDetailLines = launchRiskFallbackLines,
    renderLaunchPolicyBoundary = launchRiskFallbackRender,
    launchSettingsIntentPayload = launchRiskFallbackPayload,
    launchSettingsIntentLatestCommand = function () { return null; },
    launchSettingsIntentCommandLine = function () { return "No matching command is visible in recent command history."; },
    launchSettingsIntentRows = launchRiskFallbackRows,
    launchSettingsIntentStatus = launchRiskFallbackStatus,
    launchSettingsIntentSummaryLines = launchRiskFallbackLines,
    launchSettingsIntentDetailLines = launchRiskFallbackLines,
    renderLaunchSettingsIntentChecklist = launchRiskFallbackRender,
  } = launchRisk;

  const launchPreflightFallbackRows = function () { return []; };
  const launchPreflightFallbackLines = function () { return []; };
  const launchPreflightFallbackStatus = function () { return "Unknown"; };
  const launchPreflightFallbackRender = function () {};
  let launchPilotReadinessContext = function (context = lastLaunchRealMediaProofContext) { return context && typeof context === "object" ? context : {}; };
  let launchPilotPathFromRow = function (row) { return row?.source_path || row?.path || row?.file || row?.input_path || ""; };
  let launchPilotRowLabel = function (row) { return row?.display_name || row?.relative_path || row?.source_path || row?.path || row?.file || ""; };
  let launchPilotPendingRows = launchPreflightFallbackRows;
  let launchPilotPendingBlockedCount = function () { return 0; };
  let launchPilotSettingsStatusLabel = function () { return { settingsStatus: "Unknown", settingsIntentStatus: "Unknown", policyStatus: "Unknown", intentRows: [], policyRows: [] }; };
  let launchPilotRunReadinessRows = launchPreflightFallbackRows;
  let launchPilotRunReadinessStatus = launchPreflightFallbackStatus;
  let launchPilotRunReadinessSummaryLines = launchPreflightFallbackLines;
  let launchPilotRunReadinessDetailLines = launchPreflightFallbackLines;
  let renderLaunchPilotRunReadiness = launchPreflightFallbackRender;
  let launchBackendPreflightTargetLabel = function (target) { return target || "Launch"; };
  let launchBackendPreflightQuery = function () { return "/api/launch/preflight"; };
  let launchBackendPreflightStatusRank = function () { return 0; };
  let launchBackendPreflightRowStatus = launchPreflightFallbackStatus;
  let launchBackendPreflightOverallStatus = function () { return "Not loaded"; };
  let launchBackendPreflightStatusState = function () { return "unknown"; };
  let launchBackendPreflightRows = launchPreflightFallbackRows;
  let getLastLaunchBackendPreflightPayloads = launchPreflightFallbackRows;
  let launchBackendPreflightPayloadForTarget = function () { return null; };
  let getLastLaunchBackendPreflightRefreshInfo = function () { return { loaded_at: "", request_count: 0, payload_count: 0, fetch_failure_count: 0 }; };
  let launchBackendPreflightSummaryLines = launchPreflightFallbackLines;
  let launchBackendPreflightDetailLines = launchPreflightFallbackLines;
  let renderLaunchBackendPreflight = launchPreflightFallbackRender;
  let refreshLaunchBackendPreflight = async function () {};
  let pipelineLaunchPreflightLines = launchPreflightFallbackLines;
  let auditLaunchPreflightLines = launchPreflightFallbackLines;
  let rerunLaunchPreflightLines = launchPreflightFallbackLines;
  let renderLaunchPreflight = function (id, lines) { setText(id, (lines || []).join("\n")); };
  let renderLaunchAuditProgress = launchPreflightFallbackRender;
  let renderAllLaunchPreflights = launchPreflightFallbackRender;
  let isPipelineControlCommand = function (entry) { return String(entry?.command || "").toLowerCase().startsWith("pipeline.control."); };
  let pipelineControlHistoryLine = function (entry) { return String(entry?.message || entry?.command || "pipeline.control"); };
  let renderPipelineControlHistory = launchPreflightFallbackRender;

  function pipelineControlHistoryEntries(history = []) {
    return Array.isArray(history) ? history.filter(isPipelineControlCommand) : [];
  }

  function renderPipelineControlLatest(history = []) {
    const entries = pipelineControlHistoryEntries(history);
    const latest = entries[0] || null;
    if (!latest) {
      setText("control-latest", "No pipeline control command in recent history.");
      return;
    }
    setText("control-latest", pipelineControlHistoryLine(latest));
  }

  function renderPipelineControlJournal(history = [], renderFullHistory = null) {
    renderPipelineControlLatest(history);
    if (typeof renderFullHistory === "function") renderFullHistory(history);
    renderPipelineControllerStatus();
  }

  const launchScopeState = {
    get selectedLaunchScopeReconciliationKey() {
      return selectedLaunchScopeReconciliationKey;
    },
    set selectedLaunchScopeReconciliationKey(value) {
      selectedLaunchScopeReconciliationKey = value || "";
    },
    get selectedLaunchStartDecisionKey() {
      return selectedLaunchStartDecisionKey;
    },
    set selectedLaunchStartDecisionKey(value) {
      selectedLaunchStartDecisionKey = value || "";
    },
  };

  const launchScopeModule = window.__launchViewScopeModule || {};
  delete window.__launchViewScopeModule;
  const launchScopeFallbackRows = function () { return []; };
  const launchScopeFallbackLines = function () { return []; };
  const launchScopeFallbackStatus = function () { return "Unknown"; };
  const launchScopeFallbackRender = function () {};
  const launchScope = typeof launchScopeModule.createLaunchScopeModule === "function"
    ? launchScopeModule.createLaunchScopeModule({
      appendCells: typeof appendCells === "function" ? appendCells : window.appendCells,
      byId: typeof byId === "function" ? byId : window.byId,
      clearRows: typeof clearRows === "function" ? clearRows : window.clearRows,
      collectPipelineStartRequest: (...args) => collectPipelineStartRequest(...args),
      commandHistoryIssueLevel: typeof window.commandHistoryIssueLevel === "function" ? window.commandHistoryIssueLevel : (typeof commandHistoryIssueLevel === "function" ? commandHistoryIssueLevel : null),
      getCommandHistory: typeof window.getCommandHistory === "function" ? () => window.getCommandHistory() : (typeof getCommandHistory === "function" ? () => getCommandHistory() : () => []),
      getLastLaunchBackendPreflightPayloads: () => getLastLaunchBackendPreflightPayloads(),
      getLastLaunchBackendPreflightRefreshInfo: () => getLastLaunchBackendPreflightRefreshInfo() || {},
      getLastQueuePayload: typeof window.getLastQueuePayload === "function" ? () => window.getLastQueuePayload() : (typeof getLastQueuePayload === "function" ? () => getLastQueuePayload() : () => null),
      getLastQueueRows: typeof window.getLastQueueRows === "function" ? () => window.getLastQueueRows() : (typeof getLastQueueRows === "function" ? () => getLastQueueRows() : () => []),
      getLaunchRealMediaContext: () => lastLaunchRealMediaProofContext || {},
      isLaunchCommand,
      launchBackendPreflightOverallStatus: (...args) => launchBackendPreflightOverallStatus(...args),
      launchBackendPreflightPayloadForTarget: (...args) => launchBackendPreflightPayloadForTarget(...args),
      launchBackendPreflightRows: (...args) => launchBackendPreflightRows(...args),
      launchBackendPreflightStatusState: (...args) => launchBackendPreflightStatusState(...args),
      launchBackendPreflightSummaryLines: (...args) => launchBackendPreflightSummaryLines(...args),
      launchCommandReviewRows: typeof window.launchCommandReviewRows === "function" ? window.launchCommandReviewRows : (typeof launchCommandReviewRows === "function" ? launchCommandReviewRows : null),
      launchCommandReviewStatus: typeof window.launchCommandReviewStatus === "function" ? window.launchCommandReviewStatus : (typeof launchCommandReviewStatus === "function" ? launchCommandReviewStatus : null),
      launchCommandReviewSummaryLines: typeof window.launchCommandReviewSummaryLines === "function" ? window.launchCommandReviewSummaryLines : (typeof launchCommandReviewSummaryLines === "function" ? launchCommandReviewSummaryLines : null),
      launchPolicyBoundaryRows: (...args) => launchPolicyBoundaryRows(...args),
      launchPolicyBoundaryStatus: (...args) => launchPolicyBoundaryStatus(...args),
      launchPolicyBoundarySummaryLines: (...args) => launchPolicyBoundarySummaryLines(...args),
      launchReadinessLines: typeof launchReadinessLines === "function" ? launchReadinessLines : null,
      launchReadinessStatus: typeof launchReadinessStatus === "function" ? launchReadinessStatus : null,
      launchRealMediaProofRows: (...args) => launchRealMediaProofRows(...args),
      launchRealMediaProofStatus: (...args) => launchRealMediaProofStatus(...args),
      launchRealMediaProofSummaryLines: (...args) => launchRealMediaProofSummaryLines(...args),
      launchRealMediaSample: (...args) => launchRealMediaSample(...args),
      launchSampleExecutionRows: (...args) => launchSampleExecutionRows(...args),
      launchSampleExecutionStatus: (...args) => launchSampleExecutionStatus(...args),
      launchSampleExecutionSummaryLines: (...args) => launchSampleExecutionSummaryLines(...args),
      launchSampleSetCoverageEvidence: (...args) => launchSampleSetCoverageEvidence(...args),
      launchSettingsIntentCommandLine: (...args) => launchSettingsIntentCommandLine(...args),
      launchSettingsIntentLatestCommand: (...args) => launchSettingsIntentLatestCommand(...args),
      launchSettingsIntentPayload: (...args) => launchSettingsIntentPayload(...args),
      launchSettingsIntentRows: (...args) => launchSettingsIntentRows(...args),
      launchSettingsIntentStatus: (...args) => launchSettingsIntentStatus(...args),
      launchSettingsIntentSummaryLines: (...args) => launchSettingsIntentSummaryLines(...args),
      launchSettingsWorkspace: (...args) => launchSettingsWorkspace(...args),
      launchTimingStatus: typeof launchTimingStatus === "function" ? launchTimingStatus : null,
      launchTimingTrustLines: typeof launchTimingTrustLines === "function" ? launchTimingTrustLines : null,
      makeRowSelectable: typeof makeRowSelectable === "function" ? makeRowSelectable : window.makeRowSelectable,
      pipelineModeLabel,
      queueCurrentFilterScope: typeof window.queueCurrentFilterScope === "function" ? window.queueCurrentFilterScope : (typeof queueCurrentFilterScope === "function" ? queueCurrentFilterScope : null),
      queueFilterScopeDetailLines: typeof window.queueFilterScopeDetailLines === "function" ? window.queueFilterScopeDetailLines : (typeof queueFilterScopeDetailLines === "function" ? queueFilterScopeDetailLines : null),
      queueLaunchDecisionPostureStatus: typeof window.queueLaunchDecisionPostureStatus === "function" ? window.queueLaunchDecisionPostureStatus : (typeof queueLaunchDecisionPostureStatus === "function" ? queueLaunchDecisionPostureStatus : null),
      queueLaunchDecisionRows: typeof window.queueLaunchDecisionRows === "function" ? window.queueLaunchDecisionRows : (typeof queueLaunchDecisionRows === "function" ? queueLaunchDecisionRows : null),
      queueLaunchDecisionStatus: typeof window.queueLaunchDecisionStatus === "function" ? window.queueLaunchDecisionStatus : (typeof queueLaunchDecisionStatus === "function" ? queueLaunchDecisionStatus : null),
      queueLaunchDecisionSummaryLines: typeof window.queueLaunchDecisionSummaryLines === "function" ? window.queueLaunchDecisionSummaryLines : (typeof queueLaunchDecisionSummaryLines === "function" ? queueLaunchDecisionSummaryLines : null),
      scheduleDisplayValue: typeof scheduleDisplayValue === "function" ? scheduleDisplayValue : window.scheduleDisplayValue,
      scheduleWatcherSummary: typeof scheduleWatcherSummary === "function" ? scheduleWatcherSummary : window.scheduleWatcherSummary,
      setText: typeof setText === "function" ? setText : window.setText,
      state: launchScopeState,
      updateTableStatusLegend: typeof updateTableStatusLegend === "function" ? updateTableStatusLegend : window.updateTableStatusLegend,
    })
    : {};
  const {
    launchScopeStatusValue = launchScopeFallbackStatus,
    launchScopeRank = function () { return 0; },
    launchScopeLatestLaunchCommand = function () { return null; },
    launchScopeCommandPosture = launchScopeFallbackStatus,
    launchScopeBackendPreflightPosture = launchScopeFallbackStatus,
    launchScopeQueuePosture = launchScopeFallbackStatus,
    launchScopeReconciliationRows = launchScopeFallbackRows,
    launchScopeReconciliationStatus = launchScopeFallbackStatus,
    launchScopeReconciliationSummaryLines = launchScopeFallbackLines,
    launchScopeReconciliationDetailLines = launchScopeFallbackLines,
    renderLaunchScopeReconciliation = launchScopeFallbackRender,
    launchStartDecisionPostureFromStatus = launchScopeFallbackStatus,
    launchStartDecisionWorstPosture = launchScopeFallbackStatus,
    launchStartDecisionRank = function () { return 0; },
    launchStartDecisionRowStatus = launchScopeFallbackStatus,
    launchStartDecisionRows = launchScopeFallbackRows,
    launchStartDecisionStatus = launchScopeFallbackStatus,
    launchStartDecisionSummaryLines = launchScopeFallbackLines,
    launchStartDecisionDetailLines = launchScopeFallbackLines,
    renderLaunchStartDecisionSummary = launchScopeFallbackRender,
  } = launchScope;

  const launchRealMediaState = {
    get context() {
      return lastLaunchRealMediaProofContext;
    },
    set context(value) {
      lastLaunchRealMediaProofContext = value && typeof value === "object" ? value : {};
    },
    get selectedLaunchRealMediaProofKey() {
      return selectedLaunchRealMediaProofKey;
    },
    set selectedLaunchRealMediaProofKey(value) {
      selectedLaunchRealMediaProofKey = value || "";
    },
    get selectedLaunchSampleExecutionKey() {
      return selectedLaunchSampleExecutionKey;
    },
    set selectedLaunchSampleExecutionKey(value) {
      selectedLaunchSampleExecutionKey = value || "";
    },
  };

  const launchRealMediaModule = window.__launchViewRealMediaModule || {};
  delete window.__launchViewRealMediaModule;
  const launchRealMediaFallbackRows = function () { return []; };
  const launchRealMediaFallbackLines = function () { return []; };
  const launchRealMediaFallbackStatus = function () { return "Unknown"; };
  const launchRealMediaFallbackObject = function () { return {}; };
  const launchRealMediaFallbackRender = function () {};
  const launchRealMedia = typeof launchRealMediaModule.createLaunchRealMediaModule === "function"
    ? launchRealMediaModule.createLaunchRealMediaModule({
      appendCells: typeof appendCells === "function" ? appendCells : window.appendCells,
      byId: typeof byId === "function" ? byId : window.byId,
      clearRows: typeof clearRows === "function" ? clearRows : window.clearRows,
      getLastQueueRows: typeof window.getLastQueueRows === "function" ? () => window.getLastQueueRows() : (typeof getLastQueueRows === "function" ? () => getLastQueueRows() : null),
      getSelectedQueueRow: typeof window.getSelectedQueueRow === "function" ? () => window.getSelectedQueueRow() : (typeof getSelectedQueueRow === "function" ? () => getSelectedQueueRow() : null),
      launchPilotPathFromRow: (...args) => launchPilotPathFromRow(...args),
      launchPilotReadinessContext: (...args) => launchPilotReadinessContext(...args),
      launchPilotRowLabel: (...args) => launchPilotRowLabel(...args),
      makeRowSelectable: typeof makeRowSelectable === "function" ? makeRowSelectable : window.makeRowSelectable,
      renderLaunchPilotRunReadiness: (...args) => renderLaunchPilotRunReadiness(...args),
      renderLaunchStartDecisionSummary: (...args) => renderLaunchStartDecisionSummary(...args),
      setText: typeof setText === "function" ? setText : window.setText,
      state: launchRealMediaState,
      updateTableStatusLegend: typeof updateTableStatusLegend === "function" ? updateTableStatusLegend : window.updateTableStatusLegend,
    })
    : {};
  const {
    launchRealMediaSample = launchRealMediaFallbackObject,
    launchWorksheetEvidence = launchRealMediaFallbackObject,
    launchWorksheetRunRows = launchRealMediaFallbackRows,
    launchWorksheetRunsMatchingSample = launchRealMediaFallbackRows,
    launchPolicyAlignmentPayload = launchRealMediaFallbackObject,
    launchPolicyAlignmentRows = launchRealMediaFallbackRows,
    launchQueueIntentCategoryMatch = launchRealMediaFallbackStatus,
    launchPolicyAlignmentQueueIntentEvidence = launchRealMediaFallbackObject,
    launchSampleSetCoverageEvidence = launchRealMediaFallbackObject,
    launchSampleSetCoverageLine = function () { return "Pilot category coverage: not loaded"; },
    launchSampleValidationRecordEvidence = launchRealMediaFallbackObject,
    launchSampleValidationRecordRows = launchRealMediaFallbackRows,
    launchSampleValidationRecordsMatchingSample = launchRealMediaFallbackRows,
    launchRealMediaProofRows = launchRealMediaFallbackRows,
    launchRealMediaProofStatus = launchRealMediaFallbackStatus,
    launchRealMediaProofSummaryLines = launchRealMediaFallbackLines,
    launchRealMediaProofDetailLines = launchRealMediaFallbackLines,
    renderLaunchRealMediaProofHandoff = launchRealMediaFallbackRender,
    launchSampleExecutionRows = launchRealMediaFallbackRows,
    launchSampleExecutionStatus = launchRealMediaFallbackStatus,
    launchSampleExecutionSummaryLines = launchRealMediaFallbackLines,
    launchSampleExecutionDetailLines = launchRealMediaFallbackLines,
    renderLaunchSampleExecutionChecklist = launchRealMediaFallbackRender,
  } = launchRealMedia;

  const launchPreflightModule = window.__launchViewPreflightModule || {};
  delete window.__launchViewPreflightModule;
  const launchPreflight = typeof launchPreflightModule.createLaunchPreflightModule === "function"
    ? launchPreflightModule.createLaunchPreflightModule({
      apiGet: typeof apiGet === "function" ? apiGet : window.apiGet,
      appendCells: typeof appendCells === "function" ? appendCells : window.appendCells,
      byId: typeof byId === "function" ? byId : window.byId,
      clearRows: typeof clearRows === "function" ? clearRows : window.clearRows,
      collectAuditStartRequest: (...args) => collectAuditStartRequest(...args),
      collectPipelineStartRequest: (...args) => collectPipelineStartRequest(...args),
      collectRerunStartRequest: (...args) => collectRerunStartRequest(...args),
      commandHistoryCompactEvidenceLine: typeof window.commandHistoryCompactEvidenceLine === "function" ? window.commandHistoryCompactEvidenceLine : (typeof commandHistoryCompactEvidenceLine === "function" ? commandHistoryCompactEvidenceLine : null),
      getCommandHistory: typeof window.getCommandHistory === "function" ? () => window.getCommandHistory() : (typeof getCommandHistory === "function" ? () => getCommandHistory() : () => []),
      getLastQueuePayload: typeof window.getLastQueuePayload === "function" ? () => window.getLastQueuePayload() : (typeof getLastQueuePayload === "function" ? () => getLastQueuePayload() : () => null),
      getLastQueueRows: typeof window.getLastQueueRows === "function" ? () => window.getLastQueueRows() : (typeof getLastQueueRows === "function" ? () => getLastQueueRows() : () => []),
      getLastSnapshot: typeof window.getLastSnapshot === "function" ? () => window.getLastSnapshot() : () => null,
      getSelectedQueueRow: typeof window.getSelectedQueueRow === "function" ? () => window.getSelectedQueueRow() : (typeof getSelectedQueueRow === "function" ? () => getSelectedQueueRow() : () => null),
      launchPolicyAlignmentQueueIntentEvidence: (...args) => launchPolicyAlignmentQueueIntentEvidence(...args),
      launchPolicyBoundaryRows: (...args) => launchPolicyBoundaryRows(...args),
      launchPolicyBoundaryStatus: (...args) => launchPolicyBoundaryStatus(...args),
      launchRealMediaProofRows: (...args) => launchRealMediaProofRows(...args),
      launchRealMediaProofStatus: (...args) => launchRealMediaProofStatus(...args),
      launchRealMediaProofSummaryLines: (...args) => launchRealMediaProofSummaryLines(...args),
      launchRealMediaReadinessLines: (...args) => launchRealMediaReadinessLines(...args),
      launchRealMediaSample: (...args) => launchRealMediaSample(...args),
      launchSampleExecutionRows: (...args) => launchSampleExecutionRows(...args),
      launchSampleExecutionStatus: (...args) => launchSampleExecutionStatus(...args),
      launchSampleExecutionSummaryLines: (...args) => launchSampleExecutionSummaryLines(...args),
      launchSampleSetCoverageEvidence: (...args) => launchSampleSetCoverageEvidence(...args),
      launchSettingsDecisionLines: (...args) => launchSettingsDecisionLines(...args),
      launchSettingsIntentPayload: (...args) => launchSettingsIntentPayload(...args),
      launchSettingsIntentRows: (...args) => launchSettingsIntentRows(...args),
      launchSettingsIntentStatus: (...args) => launchSettingsIntentStatus(...args),
      launchSettingsRiskLines: (...args) => launchSettingsRiskLines(...args),
      launchSettingsTrustStatus: (...args) => launchSettingsTrustStatus(...args),
      launchSettingsWorkspace: (...args) => launchSettingsWorkspace(...args),
      launchStartDecisionPostureFromStatus: (...args) => launchStartDecisionPostureFromStatus(...args),
      launchStartDecisionRank: (...args) => launchStartDecisionRank(...args),
      launchStartDecisionRowStatus: (...args) => launchStartDecisionRowStatus(...args),
      launchStartDecisionWorstPosture: (...args) => launchStartDecisionWorstPosture(...args),
      launchUnsavedSettingsPatchLines: (...args) => launchUnsavedSettingsPatchLines(...args),
      makeRowSelectable: typeof makeRowSelectable === "function" ? makeRowSelectable : window.makeRowSelectable,
      pipelineModeLabel,
      queueLaunchDecisionRows: typeof window.queueLaunchDecisionRows === "function" ? window.queueLaunchDecisionRows : (typeof queueLaunchDecisionRows === "function" ? queueLaunchDecisionRows : null),
      queueLaunchDecisionStatus: typeof window.queueLaunchDecisionStatus === "function" ? window.queueLaunchDecisionStatus : (typeof queueLaunchDecisionStatus === "function" ? queueLaunchDecisionStatus : null),
      renderAuditProgressInto: typeof window.renderAuditProgressInto === "function" ? window.renderAuditProgressInto : (typeof renderAuditProgressInto === "function" ? renderAuditProgressInto : null),
      renderLaunchPolicyBoundary: (...args) => renderLaunchPolicyBoundary(...args),
      renderLaunchRealMediaProofHandoff: (...args) => renderLaunchRealMediaProofHandoff(...args),
      renderLaunchScopeReconciliation: (...args) => renderLaunchScopeReconciliation(...args),
      renderLaunchSettingsIntentChecklist: (...args) => renderLaunchSettingsIntentChecklist(...args),
      renderLaunchSettingsRiskHandoff: (...args) => renderLaunchSettingsRiskHandoff(...args),
      renderLaunchStartDecisionSummary: (...args) => renderLaunchStartDecisionSummary(...args),
      renderLaunchTimingTrust: typeof window.renderLaunchTimingTrust === "function" ? window.renderLaunchTimingTrust : (typeof renderLaunchTimingTrust === "function" ? renderLaunchTimingTrust : null),
      renderQueueLaunchDecisionChecklist: typeof window.renderQueueLaunchDecisionChecklist === "function" ? window.renderQueueLaunchDecisionChecklist : (typeof renderQueueLaunchDecisionChecklist === "function" ? renderQueueLaunchDecisionChecklist : null),
      renderScheduleTimingTrust: typeof window.renderScheduleTimingTrust === "function" ? window.renderScheduleTimingTrust : (typeof renderScheduleTimingTrust === "function" ? renderScheduleTimingTrust : null),
      setText: typeof setText === "function" ? setText : window.setText,
      state: launchRealMediaState,
      updateTableStatusLegend: typeof updateTableStatusLegend === "function" ? updateTableStatusLegend : window.updateTableStatusLegend,
    })
    : {};
  launchPilotReadinessContext = typeof launchPreflight.launchPilotReadinessContext === "function" ? launchPreflight.launchPilotReadinessContext : launchPilotReadinessContext;
  launchPilotPathFromRow = typeof launchPreflight.launchPilotPathFromRow === "function" ? launchPreflight.launchPilotPathFromRow : launchPilotPathFromRow;
  launchPilotRowLabel = typeof launchPreflight.launchPilotRowLabel === "function" ? launchPreflight.launchPilotRowLabel : launchPilotRowLabel;
  launchPilotPendingRows = typeof launchPreflight.launchPilotPendingRows === "function" ? launchPreflight.launchPilotPendingRows : launchPilotPendingRows;
  launchPilotPendingBlockedCount = typeof launchPreflight.launchPilotPendingBlockedCount === "function" ? launchPreflight.launchPilotPendingBlockedCount : launchPilotPendingBlockedCount;
  launchPilotSettingsStatusLabel = typeof launchPreflight.launchPilotSettingsStatusLabel === "function" ? launchPreflight.launchPilotSettingsStatusLabel : launchPilotSettingsStatusLabel;
  launchPilotRunReadinessRows = typeof launchPreflight.launchPilotRunReadinessRows === "function" ? launchPreflight.launchPilotRunReadinessRows : launchPilotRunReadinessRows;
  launchPilotRunReadinessStatus = typeof launchPreflight.launchPilotRunReadinessStatus === "function" ? launchPreflight.launchPilotRunReadinessStatus : launchPilotRunReadinessStatus;
  launchPilotRunReadinessSummaryLines = typeof launchPreflight.launchPilotRunReadinessSummaryLines === "function" ? launchPreflight.launchPilotRunReadinessSummaryLines : launchPilotRunReadinessSummaryLines;
  launchPilotRunReadinessDetailLines = typeof launchPreflight.launchPilotRunReadinessDetailLines === "function" ? launchPreflight.launchPilotRunReadinessDetailLines : launchPilotRunReadinessDetailLines;
  renderLaunchPilotRunReadiness = typeof launchPreflight.renderLaunchPilotRunReadiness === "function" ? launchPreflight.renderLaunchPilotRunReadiness : renderLaunchPilotRunReadiness;
  launchBackendPreflightTargetLabel = typeof launchPreflight.launchBackendPreflightTargetLabel === "function" ? launchPreflight.launchBackendPreflightTargetLabel : launchBackendPreflightTargetLabel;
  launchBackendPreflightQuery = typeof launchPreflight.launchBackendPreflightQuery === "function" ? launchPreflight.launchBackendPreflightQuery : launchBackendPreflightQuery;
  launchBackendPreflightStatusRank = typeof launchPreflight.launchBackendPreflightStatusRank === "function" ? launchPreflight.launchBackendPreflightStatusRank : launchBackendPreflightStatusRank;
  launchBackendPreflightRowStatus = typeof launchPreflight.launchBackendPreflightRowStatus === "function" ? launchPreflight.launchBackendPreflightRowStatus : launchBackendPreflightRowStatus;
  launchBackendPreflightOverallStatus = typeof launchPreflight.launchBackendPreflightOverallStatus === "function" ? launchPreflight.launchBackendPreflightOverallStatus : launchBackendPreflightOverallStatus;
  launchBackendPreflightStatusState = typeof launchPreflight.launchBackendPreflightStatusState === "function" ? launchPreflight.launchBackendPreflightStatusState : launchBackendPreflightStatusState;
  launchBackendPreflightRows = typeof launchPreflight.launchBackendPreflightRows === "function" ? launchPreflight.launchBackendPreflightRows : launchBackendPreflightRows;
  getLastLaunchBackendPreflightPayloads = typeof launchPreflight.getLastLaunchBackendPreflightPayloads === "function" ? launchPreflight.getLastLaunchBackendPreflightPayloads : getLastLaunchBackendPreflightPayloads;
  launchBackendPreflightPayloadForTarget = typeof launchPreflight.launchBackendPreflightPayloadForTarget === "function" ? launchPreflight.launchBackendPreflightPayloadForTarget : launchBackendPreflightPayloadForTarget;
  getLastLaunchBackendPreflightRefreshInfo = typeof launchPreflight.getLastLaunchBackendPreflightRefreshInfo === "function" ? launchPreflight.getLastLaunchBackendPreflightRefreshInfo : getLastLaunchBackendPreflightRefreshInfo;
  launchBackendPreflightSummaryLines = typeof launchPreflight.launchBackendPreflightSummaryLines === "function" ? launchPreflight.launchBackendPreflightSummaryLines : launchBackendPreflightSummaryLines;
  launchBackendPreflightDetailLines = typeof launchPreflight.launchBackendPreflightDetailLines === "function" ? launchPreflight.launchBackendPreflightDetailLines : launchBackendPreflightDetailLines;
  renderLaunchBackendPreflight = typeof launchPreflight.renderLaunchBackendPreflight === "function" ? launchPreflight.renderLaunchBackendPreflight : renderLaunchBackendPreflight;
  refreshLaunchBackendPreflight = typeof launchPreflight.refreshLaunchBackendPreflight === "function" ? launchPreflight.refreshLaunchBackendPreflight : refreshLaunchBackendPreflight;
  pipelineLaunchPreflightLines = typeof launchPreflight.pipelineLaunchPreflightLines === "function" ? launchPreflight.pipelineLaunchPreflightLines : pipelineLaunchPreflightLines;
  auditLaunchPreflightLines = typeof launchPreflight.auditLaunchPreflightLines === "function" ? launchPreflight.auditLaunchPreflightLines : auditLaunchPreflightLines;
  rerunLaunchPreflightLines = typeof launchPreflight.rerunLaunchPreflightLines === "function" ? launchPreflight.rerunLaunchPreflightLines : rerunLaunchPreflightLines;
  renderLaunchPreflight = typeof launchPreflight.renderLaunchPreflight === "function" ? launchPreflight.renderLaunchPreflight : renderLaunchPreflight;
  renderLaunchAuditProgress = typeof launchPreflight.renderLaunchAuditProgress === "function" ? launchPreflight.renderLaunchAuditProgress : renderLaunchAuditProgress;
  renderAllLaunchPreflights = typeof launchPreflight.renderAllLaunchPreflights === "function" ? launchPreflight.renderAllLaunchPreflights : renderAllLaunchPreflights;
  isPipelineControlCommand = typeof launchPreflight.isPipelineControlCommand === "function" ? launchPreflight.isPipelineControlCommand : isPipelineControlCommand;
  pipelineControlHistoryLine = typeof launchPreflight.pipelineControlHistoryLine === "function" ? launchPreflight.pipelineControlHistoryLine : pipelineControlHistoryLine;
  {
    const renderPipelineControlFullHistory = typeof launchPreflight.renderPipelineControlHistory === "function" ? launchPreflight.renderPipelineControlHistory : renderPipelineControlHistory;
    renderPipelineControlHistory = (history = []) => renderPipelineControlJournal(history, renderPipelineControlFullHistory);
  }

  function initLaunchViewEvents() {
    initLaunchTabNav();
    const refreshLaunchControlsForInput = () => {
      syncPipelineModeControls();
      renderAllLaunchPreflights();
      updateLaunchCommandButtonStates();
    };
    document.querySelectorAll("[data-pipeline-mode-preset]").forEach((button) => {
      button.addEventListener("click", () => selectPipelineModePreset(button.dataset.pipelineModePreset || ""));
    });
    document.querySelectorAll("[data-pipeline-scope-preset]").forEach((button) => {
      button.addEventListener("click", () => selectPipelineScopePreset(button.dataset.pipelineScopePreset || ""));
    });
    [
      "pipeline-start-mode",
      "pipeline-start-single-file",
      "pipeline-start-sleep",
      "pipeline-start-schedule-override",
      "pipeline-start-show-config",
      "pipeline-start-show-console",
      "audit-start-library-root",
      "audit-start-include-sidecars",
      "audit-start-show-console",
      "rerun-start-csv-path",
      "rerun-start-show-console",
    ].forEach((id) => {
      const element = byId(id);
      if (!element) return;
      element.addEventListener("input", refreshLaunchControlsForInput);
      element.addEventListener("change", refreshLaunchControlsForInput);
    });
    const backendPreflightRefresh = byId("launch-backend-preflight-refresh-button");
    if (backendPreflightRefresh) {
      backendPreflightRefresh.addEventListener("click", async () => {
        await refreshLaunchBackendPreflight();
        updateLaunchCommandButtonStates();
      });
    }
    const pipelineFileBrowseButton = byId("pipeline-single-file-browse-button");
    if (pipelineFileBrowseButton) {
      pipelineFileBrowseButton.addEventListener("click", () => browsePipelineSingleFile());
    }
    const pipelineFileClearButton = byId("pipeline-single-file-clear-button");
    if (pipelineFileClearButton) {
      pipelineFileClearButton.addEventListener("click", () => clearPipelineSingleFile());
    }
    renderAllLaunchPreflights();
    syncPipelineModeControls();
    updateLaunchCommandButtonStates();
  }

  async function requestPipelineControl(action) {
    const normalized = String(action || "").trim().toLowerCase();
    if (rejectControlCommandWhileBusy(normalized || "unknown")) return;
    if (!normalized) {
      const result = {
        command: "pipeline.control.unknown",
        ok: false,
        severity: "error",
        message: "No pipeline control action was selected.",
      };
      appendCommandResult(result);
      setPipelineControlMessage(result.message);
      return;
    }
    if (!confirmControlAction(normalized)) {
      const result = {
        command: `pipeline.control.${normalized}`,
        ok: false,
        severity: "info",
        message: `${controlActionLabels[normalized] || normalized} canceled.`,
      };
      appendCommandResult(result);
      setPipelineControlMessage(result.message);
      return;
    }
    setControlCommandBusy(true);
    setPipelineControlMessage(`Sending ${controlActionLabels[normalized] || normalized}...`);
    try {
      const result = await apiPost("/api/pipeline/control", { action: normalized });
      appendCommandResult(result);
      setPipelineControlMessage(result.message || "Control request sent.");
      if ((result.refresh_hint || "") === "snapshot") {
        await refreshAll();
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      appendCommandResult({
        command: `pipeline.control.${normalized}`,
        ok: false,
        severity: "error",
        message,
      });
      setPipelineControlMessage(`Control request failed: ${message}`);
    } finally {
      setControlCommandBusy(false);
    }
  }

  async function browsePipelineSingleFile() {
    if (pipelineFileBrowseInFlight || launchCommandInFlight) {
      setPipelineSingleFileBrowseStatus("Single-file browser is busy. Wait for the current Launch command to finish.");
      return;
    }
    if (launchPipelineIsActive()) {
      setPipelineSingleFileBrowseStatus("Single-file browser is disabled while backend work is active.");
      return;
    }
    const input = byId("pipeline-start-single-file");
    const initialPath = String(input?.value || "").trim();
    const request = { selection_mode: "files", initial_path: initialPath };
    pipelineStartScope = "single_file";
    pipelineFileBrowseInFlight = true;
    syncPipelineScopeControls();
    updateLaunchCommandButtonStates();
    setPipelineSingleFileBrowseStatus("Opening Windows file browser...");
    try {
      const result = await apiPost("/api/pipeline/browse-file", request);
      appendCommandResult(result);
      const data = result.data && typeof result.data === "object" ? result.data : {};
      const selectedPath = String(data.selected_path || "").trim();
      if (!result.ok) {
        setPipelineSingleFileBrowseStatus(result.message || "Windows file browser failed.");
        return;
      }
      if (data.canceled || !selectedPath) {
        setPipelineSingleFileBrowseStatus(result.message || "Windows file browser canceled. No Launch field was changed.");
        return;
      }
      if (input) {
        input.value = selectedPath;
        input.dispatchEvent(new Event("input", { bubbles: true }));
      }
      pipelineStartScope = "single_file";
      syncPipelineScopeControls();
      setPipelineSingleFileBrowseStatus(`Single file staged: ${selectedPath}`);
      renderAllLaunchPreflights();
      updateLaunchCommandButtonStates();
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      const routeMissing = String(message || "").trim().toLowerCase() === "not found";
      const displayMessage = routeMissing
        ? "Pipeline single-file browser route is not available in the running backend. Restart the Local API/Tauri shell, then open Launch again."
        : `Windows file browser failed:\n${message}`;
      appendCommandResult({
        command: "pipeline.browse_file",
        ok: false,
        severity: "error",
        message: displayMessage,
      });
      setPipelineSingleFileBrowseStatus(displayMessage);
    } finally {
      pipelineFileBrowseInFlight = false;
      updateLaunchCommandButtonStates();
    }
  }

  function clearPipelineSingleFile() {
    const input = byId("pipeline-start-single-file");
    if (input) {
      input.value = "";
      input.dispatchEvent(new Event("input", { bubbles: true }));
    }
    pipelineStartScope = "queue";
    syncPipelineScopeControls();
    setPipelineSingleFileBrowseStatus("Single-file staging cleared.");
    renderAllLaunchPreflights();
    updateLaunchCommandButtonStates();
  }

  function collectPipelineStartRequest() {
    const rawSleep = Number(byId("pipeline-start-sleep")?.value || 30);
    const mode = byId("pipeline-start-mode")?.value || "validate";
    const scheduleOverride = byId("pipeline-start-schedule-override")?.value || "";
    const singleFile = String(byId("pipeline-start-single-file")?.value || "").trim();
    const request = {
      mode,
      sleep_seconds: Number.isFinite(rawSleep) ? Math.max(1, Math.round(rawSleep)) : 30,
      show_config: Boolean(byId("pipeline-start-show-config")?.checked),
      show_console: Boolean(byId("pipeline-start-show-console")?.checked),
      schedule_override: scheduleOverride,
    };
    if (singleFile) request.single_file = singleFile;
    return request;
  }

  async function startPipelineFromForm() {
    if (rejectLaunchCommandWhileBusy("pipeline.start", "pipeline-launch-status", "pipeline-launch-detail")) return;
    const request = collectPipelineStartRequest();
    renderLaunchPreflight("pipeline-launch-preflight", pipelineLaunchPreflightLines(request));
    const label = pipelineModeLabel(request.mode);
    if (!window.confirm(`Start pipeline mode: ${label}?`)) {
      const canceled = {
        command: "pipeline.start",
        ok: false,
        severity: "info",
        message: `${label} canceled.`,
      };
      appendCommandResult(canceled);
      setText("pipeline-launch-status", "Canceled");
      setText("pipeline-launch-detail", canceled.message);
      return;
    }
    const startBtn = byId("pipeline-start-button");
    if (startBtn) startBtn.textContent = "Launching…";
    setLaunchCommandBusy(true);
    setStartupBanner("Spooling up tasks…");
    setText("pipeline-launch-status", "Starting...");
    renderJsonDetail("pipeline-launch-detail", {
      label: "Submitted request",
      value: request,
      intro: "Pipeline start request confirmed by the operator and about to be submitted.",
    });
    try {
      const result = await apiPost("/api/pipeline/start", request);
      appendCommandResult(result);
      renderLaunchCommandResult("pipeline-launch-status", "pipeline-launch-detail", result, request);
      if (result.ok) {
        const pidMatch = String(result.message || "").match(/\bPID\s*(\d+)\b/i);
        const pid = pidMatch ? pidMatch[1] : "";
        window.setTopbarPendingLaunch?.({ pid });
        setStartupBanner(pid
          ? `Pipeline starting — PID ${pid}. Waiting for first status update…`
          : "Pipeline starting. Waiting for first status update…"
        );
      }
      if ((result.refresh_hint || "") === "snapshot") {
        await refreshAll();
      }
      if (result.ok) {
        window.setTimeout(refreshAll, 2000);
        window.setTimeout(refreshAll, 6000);
        window.setTimeout(refreshAll, 12000);
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      appendCommandResult({
        command: "pipeline.start",
        ok: false,
        severity: "error",
        message,
      });
      renderLaunchCommandResult("pipeline-launch-status", "pipeline-launch-detail", {
        command: "pipeline.start",
        ok: false,
        severity: "error",
        message,
      }, request);
    } finally {
      setLaunchCommandBusy(false);
      syncPipelineModeControls();
    }
  }

  async function startPendingPublishDrain() {
    if (rejectLaunchCommandWhileBusy("pending_publish.drain", "pending-drain-status", "pending-drain-detail")) return;
    const guard = typeof pendingDrainGuardState === "function" ? pendingDrainGuardState() : null;
    if (guard && guard.allowed === false) {
      const rejected = {
        command: "pending_publish.drain",
        ok: false,
        severity: "warning",
        message: guard.message || "Pending publish drain blocked by WebView evidence.",
        data: {
          frontend_guard: true,
          decision_status: guard.decision_status || "unknown",
        },
      };
      appendCommandResult(rejected);
      setText("pending-drain-status", "Blocked");
      setText("pending-drain-detail", typeof pendingDrainGuardLines === "function" ? pendingDrainGuardLines(guard).join("\n") : rejected.message);
      if (typeof renderPendingDrainGuard === "function") renderPendingDrainGuard();
      return;
    }
    const request = {
      mode: "drain_pending_pushes",
      sleep_seconds: 30,
      show_config: false,
      show_console: false,
      schedule_override: "",
    };
    const confirmMessage = guard?.confirm_message || "Publish parked pending outputs now?";
    if (!window.confirm(confirmMessage)) {
      const canceled = {
        command: "pending_publish.drain",
        ok: false,
        severity: "info",
        message: "Pending publish drain canceled.",
      };
      appendCommandResult(canceled);
      setText("pending-drain-status", "Canceled");
      return;
    }
    setLaunchCommandBusy(true);
    setText("pending-drain-status", "Starting...");
    renderJsonDetail("pending-drain-detail", {
      label: "Submitted request",
      value: request,
      intro: "Pending publish drain request confirmed by the operator and about to be submitted.",
    });
    try {
      const result = await apiPost("/api/pipeline/start", request);
      const drainResult = {
        ...result,
        command: "pending_publish.drain",
      };
      appendCommandResult(drainResult);
      renderLaunchCommandResult("pending-drain-status", "pending-drain-detail", drainResult, request);
      if ((result.refresh_hint || "") === "snapshot") {
        await refreshAll();
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      appendCommandResult({
        command: "pending_publish.drain",
        ok: false,
        severity: "error",
        message,
      });
      renderLaunchCommandResult("pending-drain-status", "pending-drain-detail", {
        command: "pending_publish.drain",
        ok: false,
        severity: "error",
        message,
      }, request);
    } finally {
      setLaunchCommandBusy(false);
    }
  }

  function collectAuditStartRequest() {
    return {
      library_root: byId("audit-start-library-root")?.value || "",
      include_sidecars: Boolean(byId("audit-start-include-sidecars")?.checked),
      show_console: Boolean(byId("audit-start-show-console")?.checked),
    };
  }

  async function startAuditFromForm() {
    if (rejectLaunchCommandWhileBusy("audit.start", "audit-launch-status", "audit-launch-detail")) return;
    const request = collectAuditStartRequest();
    renderLaunchPreflight("audit-launch-preflight", auditLaunchPreflightLines(request));
    if (!window.confirm("Start audit?")) {
      const canceled = {
        command: "audit.start",
        ok: false,
        severity: "info",
        message: "Audit start canceled.",
      };
      appendCommandResult(canceled);
      setText("audit-launch-status", "Canceled");
      setText("audit-launch-detail", canceled.message);
      return;
    }
    setLaunchCommandBusy(true);
    setText("audit-launch-status", "Starting...");
    renderJsonDetail("audit-launch-detail", {
      label: "Submitted request",
      value: request,
      intro: "Audit start request confirmed by the operator and about to be submitted.",
    });
    try {
      const result = await apiPost("/api/audit/start", request);
      appendCommandResult(result);
      renderLaunchCommandResult("audit-launch-status", "audit-launch-detail", result, request);
      if ((result.refresh_hint || "") === "snapshot") {
        await refreshAll();
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      appendCommandResult({
        command: "audit.start",
        ok: false,
        severity: "error",
        message,
      });
      renderLaunchCommandResult("audit-launch-status", "audit-launch-detail", {
        command: "audit.start",
        ok: false,
        severity: "error",
        message,
      }, request);
    } finally {
      setLaunchCommandBusy(false);
    }
  }

  function collectRerunStartRequest() {
    return {
      csv_path: byId("rerun-start-csv-path")?.value || "",
      dry_run: false,
      stage_mode: "copy",
      original_mode: "keep",
      return_mode: "park",
      show_console: Boolean(byId("rerun-start-show-console")?.checked),
    };
  }

  async function startRerunFromForm() {
    if (rejectLaunchCommandWhileBusy("rerun.start", "rerun-launch-status", "rerun-launch-detail")) return;
    const request = collectRerunStartRequest();
    renderLaunchPreflight("rerun-launch-preflight", rerunLaunchPreflightLines(request));
    if (!request.csv_path.trim()) {
      const missing = {
        command: "rerun.start",
        ok: false,
        severity: "error",
        message: "CSV path is required.",
      };
      appendCommandResult(missing);
      setText("rerun-launch-status", "Error");
      setText("rerun-launch-detail", missing.message);
      return;
    }
    if (!window.confirm("Start CSV rerun with copy / keep / park policy?")) {
      const canceled = {
        command: "rerun.start",
        ok: false,
        severity: "info",
        message: "CSV rerun start canceled.",
      };
      appendCommandResult(canceled);
      setText("rerun-launch-status", "Canceled");
      setText("rerun-launch-detail", canceled.message);
      return;
    }
    setLaunchCommandBusy(true);
    setText("rerun-launch-status", "Starting...");
    renderJsonDetail("rerun-launch-detail", {
      label: "Submitted request",
      value: request,
      intro: "CSV rerun request confirmed by the operator and about to be submitted.",
    });
    try {
      const result = await apiPost("/api/rerun/start", request);
      appendCommandResult(result);
      renderLaunchCommandResult("rerun-launch-status", "rerun-launch-detail", result, request);
      if ((result.refresh_hint || "") === "snapshot") {
        await refreshAll();
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      appendCommandResult({
        command: "rerun.start",
        ok: false,
        severity: "error",
        message,
      });
      renderLaunchCommandResult("rerun-launch-status", "rerun-launch-detail", {
        command: "rerun.start",
        ok: false,
        severity: "error",
        message,
      }, request);
    } finally {
      setLaunchCommandBusy(false);
    }
  }

  /**
   * Public namespace for the Launch page module.
   * Prefer this namespace from new code; flat window.* exports are transitional compatibility aliases when present.
   */
  window.mediaPipelineLaunchView = {
    requestPipelineControl,
    setControlCommandBusy,
    rejectControlCommandWhileBusy,
    isPipelineControlCommand,
    pipelineControlHistoryLine,
    renderPipelineControlHistory,
    launchReadinessStatus,
    launchReadinessLines,
    renderLaunchReadiness,
    setLaunchCommandBusy,
    updateLaunchCommandButtonStates,
    rejectLaunchCommandWhileBusy,
    collectPipelineStartRequest,
    syncPipelineModeControls,
    selectPipelineModePreset,
    browsePipelineSingleFile,
    clearPipelineSingleFile,
    startPipelineFromForm,
    startPendingPublishDrain,
    collectAuditStartRequest,
    startAuditFromForm,
    renderLaunchAuditLog,
    collectRerunStartRequest,
    startRerunFromForm,
    pipelineModeLabel,
    launchCommandStatusLabel,
    launchCommandResultCorrelationLines,
    formatLaunchCommandDetail,
    renderLaunchCommandResult,
    launchSettingsWorkspace,
    launchSettingsTrustStatus,
    launchSettingsDecision,
    launchSettingsDecisionLines,
    launchUnsavedSettingsPatchLines,
    launchSettingsRiskLines,
    launchRealMediaReadinessLines,
    launchSettingsRiskRows,
    launchSettingsRiskStatus,
    launchSettingsRiskSummaryLines,
    launchSettingsRiskDetailLines,
    renderLaunchSettingsRiskHandoff,
    launchPolicyBoundaryRows,
    launchPolicyBoundaryStatus,
    launchPolicyBoundarySummaryLines,
    launchPolicyBoundaryDetailLines,
    renderLaunchPolicyBoundary,
    launchSettingsIntentRows,
    launchSettingsIntentStatus,
    launchSettingsIntentSummaryLines,
    launchSettingsIntentDetailLines,
    renderLaunchSettingsIntentChecklist,
    launchScopeReconciliationRows,
    launchScopeReconciliationStatus,
    launchScopeReconciliationSummaryLines,
    launchScopeReconciliationDetailLines,
    renderLaunchScopeReconciliation,
    launchStartDecisionRows,
    launchStartDecisionStatus,
    launchStartDecisionSummaryLines,
    launchStartDecisionDetailLines,
    renderLaunchStartDecisionSummary,
    launchRealMediaProofRows,
    launchRealMediaProofStatus,
    launchRealMediaProofSummaryLines,
    launchRealMediaProofDetailLines,
    launchWorksheetEvidence,
    launchWorksheetRunRows,
    launchWorksheetRunsMatchingSample,
    launchPolicyAlignmentPayload,
    launchPolicyAlignmentRows,
    launchQueueIntentCategoryMatch,
    launchPolicyAlignmentQueueIntentEvidence,
    launchSampleSetCoverageEvidence,
    launchSampleSetCoverageLine,
    launchSampleValidationRecordEvidence,
    launchSampleValidationRecordRows,
    launchSampleValidationRecordsMatchingSample,
    renderLaunchRealMediaProofHandoff,
    launchSampleExecutionRows,
    launchSampleExecutionStatus,
    launchSampleExecutionSummaryLines,
    launchSampleExecutionDetailLines,
    renderLaunchSampleExecutionChecklist,
    launchPilotRunReadinessRows,
    launchPilotRunReadinessStatus,
    launchPilotRunReadinessSummaryLines,
    launchPilotRunReadinessDetailLines,
    renderLaunchPilotRunReadiness,
    launchBackendPreflightRows,
    getLastLaunchBackendPreflightPayloads,
    launchBackendPreflightPayloadForTarget,
    getLastLaunchBackendPreflightRefreshInfo,
    launchBackendPreflightSummaryLines,
    launchBackendPreflightDetailLines,
    renderLaunchBackendPreflight,
    refreshLaunchBackendPreflight,
    pipelineLaunchPreflightLines,
    auditLaunchPreflightLines,
    rerunLaunchPreflightLines,
    renderLaunchAuditProgress,
    isLaunchCommand,
    renderLaunchCommandHistory,
    launchHistoryLine,
    renderAllLaunchPreflights,
    activateLaunchTab,
    initLaunchTabNav,
    initLaunchViewEvents,
  };
  window.requestPipelineControl = requestPipelineControl;
  window.isPipelineControlCommand = isPipelineControlCommand;
  window.pipelineControlHistoryLine = pipelineControlHistoryLine;
  window.renderPipelineControlHistory = renderPipelineControlHistory;
  window.launchReadinessStatus = launchReadinessStatus;
  window.launchReadinessLines = launchReadinessLines;
  window.renderLaunchReadiness = renderLaunchReadiness;
  window.syncPipelineModeControls = syncPipelineModeControls;
  window.selectPipelineModePreset = selectPipelineModePreset;
  window.browsePipelineSingleFile = browsePipelineSingleFile;
  window.clearPipelineSingleFile = clearPipelineSingleFile;
  window.startPipelineFromForm = startPipelineFromForm;
  window.collectAuditStartRequest = collectAuditStartRequest;
  window.startAuditFromForm = startAuditFromForm;
  window.renderLaunchAuditLog = renderLaunchAuditLog;
  window.collectRerunStartRequest = collectRerunStartRequest;
  window.startRerunFromForm = startRerunFromForm;
  window.launchSettingsWorkspace = launchSettingsWorkspace;
  window.launchSettingsTrustStatus = launchSettingsTrustStatus;
  window.launchSettingsDecision = launchSettingsDecision;
  window.launchSettingsDecisionLines = launchSettingsDecisionLines;
  window.launchSettingsRiskLines = launchSettingsRiskLines;
  window.launchRealMediaReadinessLines = launchRealMediaReadinessLines;
  window.launchSettingsRiskRows = launchSettingsRiskRows;
  window.launchSettingsRiskStatus = launchSettingsRiskStatus;
  window.launchSettingsRiskSummaryLines = launchSettingsRiskSummaryLines;
  window.renderLaunchSettingsRiskHandoff = renderLaunchSettingsRiskHandoff;
  window.launchPolicyBoundaryStatus = launchPolicyBoundaryStatus;
  window.launchPolicyBoundarySummaryLines = launchPolicyBoundarySummaryLines;
  window.launchPolicyBoundaryDetailLines = launchPolicyBoundaryDetailLines;
  window.renderLaunchPolicyBoundary = renderLaunchPolicyBoundary;
  window.launchSettingsIntentRows = launchSettingsIntentRows;
  window.launchSettingsIntentStatus = launchSettingsIntentStatus;
  window.launchSettingsIntentSummaryLines = launchSettingsIntentSummaryLines;
  window.launchSettingsIntentDetailLines = launchSettingsIntentDetailLines;
  window.renderLaunchSettingsIntentChecklist = renderLaunchSettingsIntentChecklist;
  window.launchScopeReconciliationStatus = launchScopeReconciliationStatus;
  window.launchScopeReconciliationSummaryLines = launchScopeReconciliationSummaryLines;
  window.launchScopeReconciliationDetailLines = launchScopeReconciliationDetailLines;
  window.launchStartDecisionRows = launchStartDecisionRows;
  window.launchStartDecisionStatus = launchStartDecisionStatus;
  window.launchStartDecisionSummaryLines = launchStartDecisionSummaryLines;
  window.launchStartDecisionDetailLines = launchStartDecisionDetailLines;
  window.launchRealMediaProofRows = launchRealMediaProofRows;
  window.launchRealMediaProofStatus = launchRealMediaProofStatus;
  window.launchRealMediaProofSummaryLines = launchRealMediaProofSummaryLines;
  window.launchRealMediaProofDetailLines = launchRealMediaProofDetailLines;
  window.launchWorksheetEvidence = launchWorksheetEvidence;
  window.launchWorksheetRunRows = launchWorksheetRunRows;
  window.launchWorksheetRunsMatchingSample = launchWorksheetRunsMatchingSample;
  window.launchPolicyAlignmentPayload = launchPolicyAlignmentPayload;
  window.launchPolicyAlignmentRows = launchPolicyAlignmentRows;
  window.launchQueueIntentCategoryMatch = launchQueueIntentCategoryMatch;
  window.launchPolicyAlignmentQueueIntentEvidence = launchPolicyAlignmentQueueIntentEvidence;
  window.launchSampleSetCoverageLine = launchSampleSetCoverageLine;
  window.launchSampleValidationRecordEvidence = launchSampleValidationRecordEvidence;
  window.launchSampleValidationRecordRows = launchSampleValidationRecordRows;
  window.launchSampleValidationRecordsMatchingSample = launchSampleValidationRecordsMatchingSample;
  window.launchSampleExecutionRows = launchSampleExecutionRows;
  window.launchSampleExecutionStatus = launchSampleExecutionStatus;
  window.launchSampleExecutionSummaryLines = launchSampleExecutionSummaryLines;
  window.launchSampleExecutionDetailLines = launchSampleExecutionDetailLines;
  window.launchPilotRunReadinessRows = launchPilotRunReadinessRows;
  window.launchPilotRunReadinessStatus = launchPilotRunReadinessStatus;
  window.launchPilotRunReadinessSummaryLines = launchPilotRunReadinessSummaryLines;
  window.launchPilotRunReadinessDetailLines = launchPilotRunReadinessDetailLines;
  window.launchBackendPreflightRows = launchBackendPreflightRows;
  window.getLastLaunchBackendPreflightPayloads = getLastLaunchBackendPreflightPayloads;
  window.launchBackendPreflightPayloadForTarget = launchBackendPreflightPayloadForTarget;
  window.getLastLaunchBackendPreflightRefreshInfo = getLastLaunchBackendPreflightRefreshInfo;
  window.launchBackendPreflightSummaryLines = launchBackendPreflightSummaryLines;
  window.launchBackendPreflightDetailLines = launchBackendPreflightDetailLines;
  window.renderLaunchBackendPreflight = renderLaunchBackendPreflight;
  window.refreshLaunchBackendPreflight = refreshLaunchBackendPreflight;
  window.pipelineLaunchPreflightLines = pipelineLaunchPreflightLines;
  window.auditLaunchPreflightLines = auditLaunchPreflightLines;
  window.rerunLaunchPreflightLines = rerunLaunchPreflightLines;
  window.renderLaunchAuditProgress = renderLaunchAuditProgress;
  window.isLaunchCommand = isLaunchCommand;
  window.renderLaunchCommandHistory = renderLaunchCommandHistory;
  window.launchHistoryLine = launchHistoryLine;
  window.initLaunchViewEvents = initLaunchViewEvents;
})();
