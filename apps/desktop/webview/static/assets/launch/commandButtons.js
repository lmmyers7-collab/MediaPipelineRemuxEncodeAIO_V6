/* eslint-disable max-lines-per-function */
(function () {
  function createLaunchCommandButtonsModule(deps = {}) {
    const {
      appendCommandResult = function () {},
      byId = function () { return null; },
      clearStartupBanner = function () {},
      collectAuditStartRequest = function () { return {}; },
      collectPipelineStartRequest = function () { return {}; },
      collectRerunStartRequest = function () { return {}; },
      launchBackendPreflightOverallStatus = function () { return "Not loaded"; },
      launchBackendPreflightPayloadForTarget = function () { return null; },
      launchPauseRequested = function () { return false; },
      launchPipelineIsActive = function () { return false; },
      launchPreflightRequestMatches = function () { return false; },
      launchStartDecisionPostureFromStatus = function () { return "unknown"; },
      launchStartDecisionRows = function () { return []; },
      launchStartDecisionStatus = function () { return "Unknown"; },
      launchStartDecisionWorstPosture = function () { return "unknown"; },
      pipelineProgressIsStuck = function () { return false; },
      pipelineSingleFileValue = function () { return ""; },
      renderPipelineControllerStatus = function () {},
      setPipelineControlMessage = function () {},
      setText = function () {},
      syncPipelineScopeControls = function () {},
      state = {
        controlCommandInFlight: false,
        launchCommandInFlight: false,
        lastLaunchCommandState: { snapshot: null, closeReadiness: null },
        pipelineFileBrowseInFlight: false,
      },
    } = deps;

  const controlActionLabels = {
    pause: "Pause / Resume",
    rescan: "Rescan",
    stop: "Stop After Current",
    kill: "Force Stop",
  };

  const controlConfirmMessages = {
    rescan: "Request a queue rescan flag for the running pipeline? This does not start a new run or touch media, but it can change what the active loop sees next.",
    stop: "Request Stop After Current? The current file may finish; no new file should start. Use Force Stop only if the run is stalled.",
    kill: "Force stop immediately? This terminates related pipeline, audit, and CSV rerun PowerShell process trees and resets stuck progress state to idle. The current file may be left partial in scratch; source media should not be touched.",
  };

  const launchCommandButtonIds = [
    "pipeline-start-button",
    "pending-drain-button",
    "audit-start-button",
    "rerun-dry-run-button",
    "rerun-start-button",
  ];
  const pipelineStartBoundaryNote = "Backend start still re-checks queue, schedule, settings, and process locks; Queue tab display filters and row selection are not submitted.";

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
      return targetGate;
    }
    if (id === "rerun-start-button" || id === "rerun-dry-run-button") {
      const request = collectRerunStartRequest({ dry_run: id === "rerun-dry-run-button" });
      const targetGate = launchTargetGate("rerun", request, {
        allowMissing: false,
        matchKeys: ["csv_path", "stage_mode", "original_mode", "return_mode"],
      });
      if (targetGate.blocked) return targetGate;
      return targetGate;
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
    if (button.id === "pipeline-start-button") {
      setText("pipeline-start-disabled-reason", disabled && reason ? reason : pipelineStartBoundaryNote);
    }
  }

  function updateLaunchCommandButtonStates(snapshot = state.lastLaunchCommandState.snapshot, closeReadiness = state.lastLaunchCommandState.closeReadiness) {
    state.lastLaunchCommandState = { snapshot: snapshot || null, closeReadiness: closeReadiness || null };
    const active = launchPipelineIsActive(snapshot, closeReadiness);
    const stuck = pipelineProgressIsStuck(snapshot);
    syncPipelineScopeControls();
    if (active) clearStartupBanner();
    const startReason = active
      ? "Disabled while backend close-readiness reports active work. Stop or wait for idle before starting another pipeline/audit/rerun command."
      : "Backend start route will re-check queue, settings, schedule, and process locks at submission time.";
    launchCommandButtonIds.forEach((id) => {
      const button = byId(id);
      const gate = active || state.launchCommandInFlight ? { blocked: false, reason: "" } : launchButtonGate(id);
      setButtonDisabledWithReason(
        button,
        state.launchCommandInFlight || active || gate.blocked,
        state.launchCommandInFlight ? "A launch command is already in progress." : (active ? startReason : (gate.reason || startReason))
      );
    });

    const singleFile = String(byId("pipeline-start-single-file")?.value || "").trim();
    setButtonDisabledWithReason(
      byId("pipeline-single-file-browse-button"),
      state.pipelineFileBrowseInFlight || state.launchCommandInFlight || active,
      state.pipelineFileBrowseInFlight
        ? "Windows file browser is already open."
        : (state.launchCommandInFlight || active ? startReason : "Open the backend-owned Windows file browser for single-file staging.")
    );
    setButtonDisabledWithReason(
      byId("pipeline-single-file-clear-button"),
      state.pipelineFileBrowseInFlight || state.launchCommandInFlight || active || !singleFile,
      state.pipelineFileBrowseInFlight
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
      const disabled = action === "kill" ? (state.controlCommandInFlight || !killable) : (state.controlCommandInFlight || !active);
      const busyReason = "A pipeline control command is already in progress.";
      const idleReason = action === "kill"
        ? "Disabled: no active backend work and no stuck progress state detected."
        : "Disabled while no active backend work is reported.";
      const activeReason = {
        pause: `${pauseLabel} the active backend pipeline.`,
        rescan: "Request a queue rescan flag for the running backend pipeline.",
        stop: "Request graceful Stop After Current for the active backend pipeline.",
        kill: "Force stop: terminates related pipeline, audit, and CSV rerun process trees and resets stuck progress to idle.",
      }[action] || "Backend-owned pipeline control.";
      const effective = action === "kill" ? killable : active;
      setButtonDisabledWithReason(button, disabled, state.controlCommandInFlight ? busyReason : (effective ? activeReason : idleReason));
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
    state.launchCommandInFlight = Boolean(isBusy);
    updateLaunchCommandButtonStates();
  }

  function rejectLaunchCommandWhileBusy(command, statusId, detailId) {
    if (!state.launchCommandInFlight) return false;
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
    state.controlCommandInFlight = Boolean(isBusy);
    updateLaunchCommandButtonStates();
  }

  function rejectControlCommandWhileBusy(action) {
    if (!state.controlCommandInFlight) return false;
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

    return {
      controlActionLabels,
      launchButtonGate,
      setButtonClass,
      setButtonDisabledWithReason,
      updateLaunchCommandButtonStates,
      setLaunchCommandBusy,
      rejectLaunchCommandWhileBusy,
      setControlCommandBusy,
      rejectControlCommandWhileBusy,
      shouldConfirmControl,
      confirmControlAction,
    };
  }

  window.__launchCommandButtonsModule = {
    createLaunchCommandButtonsModule,
  };
})();
