(function () {
  function createLaunchCommandOrchestrationModule(deps = {}) {
    const {
      Event,
      apiPost,
      appendCommandResult,
      byId,
      collectPipelineStartRequest,
      confirmControlAction,
      controlActionLabels,
      initLaunchTabNav,
      launchPipelineIsActive,
      launchRerunCsvIsActive,
      nextLaunchCommandFrame,
      pendingDrainGuardState,
      pipelineLaunchPreflightLines,
      pipelineModeLabel,
      queueRerunRouteDispatcher,
      refreshAll,
      refreshLaunchBackendPreflight,
      refreshLaunchBackendPreflightEncoderCapability,
      refreshRerunResults,
      rejectControlCommandWhileBusy,
      rejectLaunchCommandWhileBusy,
      renderAllLaunchPreflights,
      renderJsonDetail,
      renderLaunchCommandResult,
      renderLaunchCompactGate,
      renderLaunchPreflight,
      selectPipelineModePreset,
      selectPipelineScopePreset,
      setControlCommandBusy,
      setLaunchCommandBusy,
      setLaunchCommandButtonState,
      setPipelineControlMessage,
      setPipelineSingleFileBrowseStatus,
      setStartupBanner,
      setText,
      state,
      syncPipelineModeControls,
      syncPipelineScopeControls,
      updateLaunchCommandButtonStates,
    } = deps;

    function initLaunchViewEvents() {
      initLaunchTabNav();
      const refreshLaunchControlsForInput = (event = null) => {
        void event;
        syncPipelineModeControls();
        renderPipelineStartSafetySummary(collectPipelineStartRequest());
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
      ].forEach((id) => {
        const element = byId(id);
        if (!element) return;
        element.addEventListener("input", refreshLaunchControlsForInput);
        element.addEventListener("change", refreshLaunchControlsForInput);
      });
      ["launch-backend-preflight-refresh-button", "pipeline-compact-gate-refresh-button"].forEach((id) => {
        const backendPreflightRefresh = byId(id);
        if (!backendPreflightRefresh) return;
        backendPreflightRefresh.addEventListener("click", async () => {
          await refreshLaunchBackendPreflight();
          renderLaunchCompactGate();
          updateLaunchCommandButtonStates();
        });
      });
      const encoderCapabilityRefreshButton = byId("launch-encoder-capability-refresh-button");
      if (encoderCapabilityRefreshButton) {
        encoderCapabilityRefreshButton.addEventListener("click", async () => {
          await refreshLaunchBackendPreflightEncoderCapability();
          renderLaunchCompactGate();
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
      initLaunchRecoveryActionEvents();
      renderAllLaunchPreflights();
      refreshLaunchBackendPreflight()
        .then(() => {
          renderLaunchCompactGate();
          renderPipelineStartSafetySummary(collectPipelineStartRequest());
          updateLaunchCommandButtonStates();
        })
        .catch((error) => {
          const message = error instanceof Error ? error.message : String(error);
          setText("launch-backend-preflight-status", "Load failed");
          const statusNode = byId("launch-backend-preflight-status");
          if (statusNode) statusNode.dataset.state = "warning";
          setText("launch-backend-preflight-summary", [
            "Pipeline backend preflight did not load automatically.",
            `Error: ${message}`,
            "Action: refresh the backend preflight from Launch for current evidence; routine Start still submits to backend guards.",
            "Mutation guardrail: automatic preflight loading is read-only and cannot launch, reserve locks, save settings, drain, rename, publish, or touch media files.",
          ].join("\n"));
          renderLaunchCompactGate();
          renderPipelineStartSafetySummary(collectPipelineStartRequest());
          updateLaunchCommandButtonStates();
        });
      syncPipelineModeControls();
      renderPipelineStartSafetySummary(collectPipelineStartRequest());
      updateLaunchCommandButtonStates();
    }

    function initLaunchRecoveryActionEvents() {
      if (!document || document.__launchRecoveryEventsBound === true) return;
      document.__launchRecoveryEventsBound = true;
      document.addEventListener("click", async (event) => {
        const button = event.target?.closest?.("[data-launch-recovery-action]");
        if (!button) return;
        event.preventDefault();
        const action = String(button.dataset.launchRecoveryAction || "").toLowerCase();
        if (action === "drain_pending_pushes") {
          await startPendingPublishDrain();
        } else if (action === "archive_state_journals") {
          await startStateJournalArchive(button);
        } else if (action === "pending_publish_recovery_plan") {
          if (typeof window.showPage === "function") window.showPage("pending");
          setText("launch-readiness-action-status", "Open Pending Publish and review the recovery plan before draining parked outputs.");
        }
      });
    }

    async function requestPipelineControl(action, sourceButton = null) {
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
      const monitorOwnedStop = normalized === "stop" && sourceButton?.dataset?.controlOwner === "run-monitor";
      const expectedRunId = monitorOwnedStop
        ? String(window.mediaPipelineRunMonitor?.getPayload?.()?.run?.run_id || "").trim()
        : "";
      if (monitorOwnedStop && !expectedRunId) {
        const result = {
          command: "pipeline.control.stop",
          ok: false,
          severity: "error",
          message: "Current Work has no exact backend run identity. Refresh Current Work before requesting Stop After Current.",
        };
        appendCommandResult(result);
        setPipelineControlMessage(result.message);
        return;
      }
      const routeToRerunControl = (normalized === "stop" || normalized === "pause") && launchRerunCsvIsActive(
        state.lastLaunchCommandState.snapshot,
        state.lastLaunchCommandState.closeReadiness
      );
      const rerunControlCommand = normalized === "pause" ? "rerun.control.pause" : "rerun.control.stop_after_current";
      const rerunControlDispatcher = normalized === "pause" ? "postRerunControlPause" : "postRerunControlStopAfterCurrent";
      const commandName = routeToRerunControl ? rerunControlCommand : `pipeline.control.${normalized}`;
      setPipelineControlMessage(`Confirming ${controlActionLabels[normalized] || normalized}...`);
      document.querySelectorAll(`[data-control-action="${normalized}"]`).forEach((button) => {
        button.dataset.commandState = "confirming";
      });
      await nextLaunchCommandFrame();
      if (!confirmControlAction(normalized)) {
        const result = {
          command: commandName,
          ok: false,
          severity: "info",
          message: `${controlActionLabels[normalized] || normalized} canceled.`,
        };
        appendCommandResult(result);
        setPipelineControlMessage(result.message);
        updateLaunchCommandButtonStates();
        return;
      }
      setControlCommandBusy(true);
      setPipelineControlMessage(`Sending ${controlActionLabels[normalized] || normalized}...`);
      try {
        const result = routeToRerunControl
          ? await queueRerunRouteDispatcher(rerunControlDispatcher)()
          : await apiPost("/api/pipeline/control", {
            action: normalized,
            ...(normalized === "kill" ? { confirm_force_stop: true } : {}),
            ...(monitorOwnedStop ? { expected_run_id: expectedRunId } : {}),
          });
        appendCommandResult(result);
        setPipelineControlMessage(result.message || "Control request sent.");
        if (routeToRerunControl) {
          await refreshRerunResults({ quiet: true });
        }
        if ((result.refresh_hint || "") === "snapshot") {
          await refreshAll();
        }
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        appendCommandResult({
          command: commandName,
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
      if (state.pipelineFileBrowseInFlight || state.launchCommandInFlight) {
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
      state.pipelineStartScope = "single_file";
      state.pipelineFileBrowseInFlight = true;
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
        state.pipelineStartScope = "single_file";
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
        state.pipelineFileBrowseInFlight = false;
        updateLaunchCommandButtonStates();
      }
    }

    function clearPipelineSingleFile() {
      const input = byId("pipeline-start-single-file");
      if (input) {
        input.value = "";
        input.dispatchEvent(new Event("input", { bubbles: true }));
      }
      state.pipelineStartScope = "queue";
      syncPipelineScopeControls();
      setPipelineSingleFileBrowseStatus("Single-file staging cleared.");
      renderAllLaunchPreflights();
      updateLaunchCommandButtonStates();
    }

    function pipelineStartConfirmMessage(request, label) {
      const scope = request?.single_file ? "Single File" : "Queue";
      const parts = [
        `Submitting ${label} for ${scope}. Backend will re-check queue, settings, schedule, and locks before starting.`,
      ];
      if (String(request?.mode || "").toLowerCase() === "continuous") {
        parts.push("Continuous mode keeps requesting work until stopped or schedule policy blocks work.");
      }
      if (request?.schedule_override) {
        parts.push("Schedule override is selected for this submission.");
      }
      return parts.join("\n");
    }

    function renderPipelineStartSafetySummary(request) {
      const target = byId("pipeline-start-safety-summary");
      if (!target) return;
      const queueRows = typeof window.getLastQueueRows === "function" ? window.getLastQueueRows() : [];
      const queueCount = Array.isArray(queueRows) ? queueRows.length : 0;
      const scope = request?.single_file
        ? "one selected file"
        : queueCount
          ? `${queueCount} loaded backend queue item${queueCount === 1 ? "" : "s"}`
          : "the saved backend queue (refresh to confirm its count)";
      const readiness = String(byId("pipeline-compact-gate-status")?.textContent || "Needs Evidence").trim();
      const mode = pipelineModeLabel(request?.mode || "once");
      target.textContent = `Selected scope: ${scope}. Readiness: ${readiness}. ${mode} will continue only after the backend rechecks readiness. Original source files stay read-only; completed results follow the existing backend review and publish safeguards.`;
    }

    async function startPipelineFromForm() {
      if (rejectLaunchCommandWhileBusy("pipeline.start", "pipeline-launch-status", "pipeline-launch-detail")) return;
      const request = collectPipelineStartRequest();
      renderPipelineStartSafetySummary(request);
      renderLaunchPreflight("pipeline-launch-preflight", pipelineLaunchPreflightLines(request));
      const label = pipelineModeLabel(request.mode);
      const startBtn = byId("pipeline-start-button");
      const startBtnText = startBtn ? startBtn.textContent : "";
      setLaunchCommandButtonState("pipeline-start-button", "submitting", "Starting...");
      setText("pipeline-launch-status", "Starting...");
      setText("pipeline-launch-detail", pipelineStartConfirmMessage(request, label));
      await nextLaunchCommandFrame();
      if (startBtn) startBtn.textContent = "Launching…";
      setLaunchCommandBusy(true);
      setStartupBanner("Spooling up tasks…");
      setText("pipeline-launch-status", "Starting...");
      renderJsonDetail("pipeline-launch-detail", {
        label: "Submitted request",
        value: request,
        intro: "Pipeline start request submitted to the backend; backend launch guards remain authoritative.",
      });
      try {
        const result = await apiPost("/api/pipeline/start", request);
        appendCommandResult(result);
        renderLaunchCommandResult("pipeline-launch-status", "pipeline-launch-detail", result, request);
        if (result.ok) {
          const pidMatch = String(result.message || "").match(/\bPID\s*(\d+)\b/i);
          const pid = pidMatch ? pidMatch[1] : "";
          window.setTopbarPendingLaunch?.({ pid });
          const standardBackendQueueRun = String(request.mode || "").toLowerCase() === "once" && !String(request.single_file || "").trim();
          if (standardBackendQueueRun) {
            window.mediaPipelineRunMonitor?.acceptLaunchResult?.(result, { navigate: true });
          } else {
            window.mediaPipelineRunMonitor?.clearBackendQueueContext?.();
          }
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
        if (startBtn) startBtn.textContent = startBtnText || "Start Pipeline";
        syncPipelineModeControls();
      }
    }

    async function startPendingPublishDrain() {
      if (rejectLaunchCommandWhileBusy("pending_publish.drain", "pending-drain-status", "pending-drain-detail")) return;
      const guard = typeof pendingDrainGuardState === "function" ? pendingDrainGuardState() : null;
      const request = {
        mode: "drain_pending_pushes",
        sleep_seconds: 30,
        show_config: false,
        show_console: false,
        schedule_override: "",
      };
      const confirmMessage = guard?.confirm_message || "Publish parked pending outputs now?";
      const drainBtn = byId("pending-drain-button");
      const drainBtnText = drainBtn ? drainBtn.textContent : "";
      setLaunchCommandButtonState("pending-drain-button", "confirming", "Confirming...");
      setText("pending-drain-status", "Confirming");
      setText("pending-drain-detail", confirmMessage);
      await nextLaunchCommandFrame();
      if (!window.confirm(confirmMessage)) {
        const canceled = {
          command: "pending_publish.drain",
          ok: false,
          severity: "info",
          message: "Pending publish drain canceled.",
        };
        appendCommandResult(canceled);
        setText("pending-drain-status", "Canceled");
        setText("pending-drain-detail", canceled.message);
        if (drainBtn) drainBtn.textContent = drainBtnText || "Drain Parked Outputs";
        updateLaunchCommandButtonStates();
        return;
      }
      if (drainBtn) drainBtn.textContent = "Draining...";
      setLaunchCommandBusy(true);
      setText("pending-drain-status", "Draining...");
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
        if (result.ok) window.mediaPipelineRunMonitor?.clearBackendQueueContext?.();
        if ((result.refresh_hint || "") === "snapshot") {
          await refreshAll();
        }
        await refreshRerunResults({ quiet: true });
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
        if (drainBtn) drainBtn.textContent = drainBtnText || "Drain Parked Outputs";
      }
    }

    async function startStateJournalArchive(sourceButton = null) {
      if (rejectLaunchCommandWhileBusy("maintenance.archive_state_journals", "launch-readiness-status", "launch-readiness-action-status")) return;
      const request = {
        confirm_archive: true,
        reason: "launch recovery",
      };
      const confirmMessage = [
        "Archive the oversized backend event journal now?",
        "The backend may only move State\\Progress\\pipeline_events.jsonl into ArchivedEvents and create a fresh empty replacement.",
        "Media, queue, pending publish, completed manifest, and final output files are not touched by this action.",
      ].join("\n");
      const button = sourceButton || null;
      const buttonText = button ? button.textContent : "";
      if (button) button.dataset.commandState = "confirming";
      setText("launch-readiness-action-status", confirmMessage);
      await nextLaunchCommandFrame();
      if (!window.confirm(confirmMessage)) {
        const canceled = {
          command: "maintenance.archive_state_journals",
          ok: false,
          severity: "info",
          message: "State journal archive canceled.",
        };
        appendCommandResult(canceled);
        setText("launch-readiness-action-status", canceled.message);
        if (button) {
          button.dataset.commandState = "";
          button.textContent = buttonText || "Archive Event Journal";
        }
        updateLaunchCommandButtonStates();
        return;
      }
      if (button) button.textContent = "Archiving...";
      setLaunchCommandBusy(true);
      renderJsonDetail("launch-readiness-action-status", {
        label: "Submitted request",
        value: request,
        intro: "State journal archive request confirmed by the operator and about to be submitted.",
      });
      try {
        const result = await apiPost("/api/maintenance/archive-state-journals", request);
        appendCommandResult(result);
        renderLaunchCommandResult("launch-readiness-status", "launch-readiness-action-status", result, request);
        if ((result.refresh_hint || "") === "snapshot") {
          await refreshAll();
        } else {
          await refreshLaunchBackendPreflight();
        }
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        const result = {
          command: "maintenance.archive_state_journals",
          ok: false,
          severity: "error",
          message,
        };
        appendCommandResult(result);
        renderLaunchCommandResult("launch-readiness-status", "launch-readiness-action-status", result, request);
      } finally {
        setLaunchCommandBusy(false);
        if (button) {
          button.dataset.commandState = "";
          button.textContent = buttonText || "Archive Event Journal";
        }
      }
    }


    return {
      initLaunchViewEvents,
      initLaunchRecoveryActionEvents,
      requestPipelineControl,
      browsePipelineSingleFile,
      clearPipelineSingleFile,
      pipelineStartConfirmMessage,
      renderPipelineStartSafetySummary,
      startPipelineFromForm,
      startPendingPublishDrain,
      startStateJournalArchive,
    };
  }

  window.__launchCommandOrchestrationModule = { createLaunchCommandOrchestrationModule };
})();
