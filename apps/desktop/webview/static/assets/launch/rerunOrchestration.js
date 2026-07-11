(function () {
  function createLaunchRerunOrchestrationModule(deps = {}) {
    const {
      appendCommandResult,
      applyRerunOpenButtonState,
      applyRerunPreviewButtonState,
      byId,
      collectRerunMinimumWorkerCount,
      collectRerunNetworkStartDryRunRequest,
      collectRerunNetworkStartRequest,
      collectRerunStartRequest,
      nextLaunchCommandFrame,
      queueRerunRouteDispatcher,
      refreshAll,
      refreshRerunPreview,
      rejectLaunchCommandWhileBusy,
      renderJsonDetail,
      renderLaunchCommandResult,
      renderLaunchPreflight,
      renderRerunFilterOptions,
      renderRerunHandlingSummary,
      renderRerunHistorySummary,
      renderRerunLifecycleEvidence,
      renderRerunPolicyPanel,
      renderRerunPreviewRows,
      renderRerunPreviewTiles,
      renderRerunRecentCsvs,
      renderRerunReviewHeader,
      renderRerunTopbarFinished,
      renderRerunTopbarPending,
      rerunCsvLeaf,
      rerunIsNetworkMode,
      rerunQueuePreflightLines,
      rerunStartPolicySummary,
      rerunSummaryLines,
      setLaunchCommandBusy,
      setLaunchCommandButtonState,
      setText,
      state,
      updateLaunchCommandButtonStates,
    } = deps;

    function renderRerunPreview(payload) {
      state.lastRerunPreviewPayload = payload && typeof payload === "object" ? payload : null;
      renderRerunHandlingSummary();
      renderRerunReviewHeader(state.lastRerunPreviewPayload);
      renderRerunLifecycleEvidence(state.lastRerunPreviewPayload, state.lastRerunCommandResult);
      setText("rerun-preview-summary", rerunSummaryLines(state.lastRerunPreviewPayload).join("\n"));
      renderRerunRecentCsvs(state.lastRerunPreviewPayload);
      renderRerunFilterOptions(state.lastRerunPreviewPayload);
      renderRerunPreviewTiles(state.lastRerunPreviewPayload);
      renderRerunPreviewRows(state.lastRerunPreviewPayload);
      renderRerunPolicyPanel(state.lastRerunPreviewPayload);
      renderRerunHistorySummary();
      applyRerunPreviewButtonState();
      applyRerunOpenButtonState();
    }
  
    function networkDryRunFingerprint(result = {}) {
      const data = result && typeof result.data === "object" ? result.data : {};
      return String(data.dry_run_fingerprint || result.dry_run_fingerprint || "").trim();
    }
  
    function networkDryRunSafeToApply(result = {}) {
      const data = result && typeof result.data === "object" ? result.data : {};
      return result.ok !== false && data.safe_to_apply === true && Boolean(networkDryRunFingerprint(result));
    }
  
    async function checkNetworkRerunStartDryRunFromForm() {
      if (rejectLaunchCommandWhileBusy("rerun.network.start_dry_run", "rerun-queue-status", "rerun-queue-detail")) return;
      const request = collectRerunNetworkStartDryRunRequest();
      renderLaunchPreflight("rerun-queue-preflight", rerunQueuePreflightLines(collectRerunStartRequest({ dry_run: false })));
      if (!String(request.csv_path || "").trim()) {
        const missing = {
          command: "rerun.network.start_dry_run",
          ok: false,
          severity: "blocked",
          message: "CSV path is required.",
          frontend_guard: true,
        };
        renderLaunchCommandResult("rerun-queue-status", "rerun-queue-detail", missing, request);
        return missing;
      }
      setLaunchCommandBusy(true);
      setText("rerun-queue-status", "Checking network start");
      renderJsonDetail("rerun-queue-detail", {
        label: "Network CSV rerun start dry-run",
        value: request,
        intro: "Backend dry-run checks coordinator readiness, worker evidence, handoff root, and planned state writes.",
      });
      try {
        const result = await queueRerunRouteDispatcher("postRerunNetworkStartDryRun")(request);
        const resultWithRequest = { ...result, request };
        state.lastRerunCommandResult = resultWithRequest;
        appendCommandResult(resultWithRequest);
        renderLaunchCommandResult("rerun-queue-status", "rerun-queue-detail", resultWithRequest, request);
        renderRerunLifecycleEvidence(state.lastRerunPreviewPayload, state.lastRerunCommandResult);
        return result;
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        const result = {
          command: "rerun.network.start_dry_run",
          ok: false,
          severity: "error",
          message,
          request,
        };
        state.lastRerunCommandResult = result;
        appendCommandResult(result);
        renderLaunchCommandResult("rerun-queue-status", "rerun-queue-detail", result, request);
        renderRerunLifecycleEvidence(state.lastRerunPreviewPayload, state.lastRerunCommandResult);
        return result;
      } finally {
        setLaunchCommandBusy(false);
        applyRerunPreviewButtonState();
      }
    }
  
    async function startNetworkRerunFromForm(options = {}) {
      if (rejectLaunchCommandWhileBusy("rerun.network.start", "rerun-queue-status", "rerun-queue-detail")) return;
      const dryRunRequest = collectRerunNetworkStartDryRunRequest();
      const previewRequest = collectRerunStartRequest({ dry_run: false, plan_only: false });
      const actionLabel = "Network CSV rerun";
      const modeSummary = `${rerunStartPolicySummary(previewRequest)}; minimum workers ${collectRerunMinimumWorkerCount()}`;
      renderLaunchPreflight("rerun-queue-preflight", rerunQueuePreflightLines(previewRequest));
      if (!String(dryRunRequest.csv_path || "").trim()) {
        const missing = {
          command: "rerun.network.start",
          ok: false,
          severity: "blocked",
          message: "CSV path is required.",
          frontend_guard: true,
        };
        renderLaunchCommandResult("rerun-queue-status", "rerun-queue-detail", missing, dryRunRequest);
        renderRerunLifecycleEvidence(state.lastRerunPreviewPayload, missing);
        applyRerunPreviewButtonState();
        return;
      }
      const preview = await refreshRerunPreview({ quiet: true });
      if (!preview || preview.status === "blocked") {
        const blocked = {
          command: "rerun.network.start",
          ok: false,
          severity: "blocked",
          message: preview?.message || "Network CSV rerun preview is blocked.",
          frontend_guard: true,
          data: preview || {},
        };
        renderLaunchCommandResult("rerun-queue-status", "rerun-queue-detail", blocked, dryRunRequest);
        renderRerunLifecycleEvidence(state.lastRerunPreviewPayload, blocked);
        applyRerunPreviewButtonState();
        return;
      }
      const rerunButtonId = "rerun-start-button";
      const rerunBtn = byId(rerunButtonId);
      const rerunBtnText = rerunBtn ? rerunBtn.textContent : "";
      if (rerunBtn) rerunBtn.textContent = "Checking...";
      setLaunchCommandBusy(true);
      setText("rerun-queue-status", "Checking network start");
      renderJsonDetail("rerun-queue-detail", {
        label: "Network CSV rerun start dry-run",
        value: dryRunRequest,
        intro: "Backend start dry-run request before confirmed Network CSV rerun start.",
      });
      renderRerunTopbarPending(dryRunRequest, actionLabel, "dry-run", "waiting for backend proof");
      try {
        const dryRun = await queueRerunRouteDispatcher("postRerunNetworkStartDryRun")(dryRunRequest);
        const dryRunWithRequest = { ...dryRun, request: dryRunRequest };
        state.lastRerunCommandResult = dryRunWithRequest;
        appendCommandResult(dryRunWithRequest);
        renderLaunchCommandResult("rerun-queue-status", "rerun-queue-detail", dryRunWithRequest, dryRunRequest);
        renderRerunLifecycleEvidence(state.lastRerunPreviewPayload, state.lastRerunCommandResult);
        if (!networkDryRunSafeToApply(dryRun)) {
          renderRerunTopbarFinished(dryRunRequest, actionLabel, `${actionLabel} dry-run blocked`);
          applyRerunPreviewButtonState();
          return dryRun;
        }
        if (rerunBtn) rerunBtn.textContent = "Confirming...";
        setText("rerun-queue-status", "Confirming");
        setText("rerun-queue-detail", `Confirm Network CSV rerun batch start with ${modeSummary} policy.`);
        await nextLaunchCommandFrame();
        if (!window.confirm(`Start Network CSV rerun batch after backend dry-run proof with ${modeSummary} policy?`)) {
          const canceled = {
            command: "rerun.network.start",
            ok: false,
            severity: "info",
            message: `${actionLabel} canceled.`,
            data: { dry_run_fingerprint: networkDryRunFingerprint(dryRun) },
            request: dryRunRequest,
          };
          state.lastRerunCommandResult = canceled;
          appendCommandResult(canceled);
          renderRerunTopbarFinished(dryRunRequest, actionLabel, canceled.message);
          setText("rerun-queue-status", "Canceled");
          setText("rerun-queue-detail", canceled.message);
          renderRerunLifecycleEvidence(state.lastRerunPreviewPayload, state.lastRerunCommandResult);
          return canceled;
        }
        const startRequest = collectRerunNetworkStartRequest(dryRun);
        if (rerunBtn) rerunBtn.textContent = "Starting...";
        setText("rerun-queue-status", "Starting network batch");
        renderJsonDetail("rerun-queue-detail", {
          label: "Submitted request",
          value: startRequest,
          intro: "Confirmed Network CSV rerun request is about to be submitted to the backend.",
        });
        renderRerunTopbarPending(startRequest, actionLabel, "submitted", "waiting for backend response");
        const result = await queueRerunRouteDispatcher("postRerunNetworkStart")(startRequest);
        const resultWithRequest = { ...result, request: startRequest };
        state.lastRerunCommandResult = resultWithRequest;
        appendCommandResult(resultWithRequest);
        renderLaunchCommandResult("rerun-queue-status", "rerun-queue-detail", resultWithRequest, startRequest);
        renderRerunLifecycleEvidence(state.lastRerunPreviewPayload, state.lastRerunCommandResult);
        if (result.ok) {
          window.setTopbarPendingLaunch?.({
            label: actionLabel,
            status_label: "accepted",
            wait_label: "waiting for worker claim evidence",
          });
          window.mediaPipelineAppTopbar?.renderTopbarActivity?.({
            activity: `${actionLabel} accepted${rerunCsvLeaf(startRequest.csv_path) ? `: ${rerunCsvLeaf(startRequest.csv_path)}` : ""}`,
            current_work: { phase_label: actionLabel },
            progress: { CurrentStage: "Network CSV rerun" },
          });
        } else {
          renderRerunTopbarFinished(startRequest, actionLabel, `${actionLabel} did not start`);
        }
        if ((result.refresh_hint || "") === "snapshot") {
          await refreshAll();
        }
        return result;
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        const result = {
          command: "rerun.network.start",
          ok: false,
          severity: "error",
          message,
          request: dryRunRequest,
        };
        state.lastRerunCommandResult = result;
        renderRerunTopbarFinished(dryRunRequest, actionLabel, `${actionLabel} failed: ${message}`);
        appendCommandResult(result);
        renderLaunchCommandResult("rerun-queue-status", "rerun-queue-detail", result, dryRunRequest);
        renderRerunLifecycleEvidence(state.lastRerunPreviewPayload, state.lastRerunCommandResult);
        return result;
      } finally {
        setLaunchCommandBusy(false);
        if (rerunBtn) rerunBtn.textContent = rerunBtnText || "Start Network Batch";
        applyRerunPreviewButtonState();
      }
    }
  
    async function startRerunFromForm(options = {}) {
      if (rerunIsNetworkMode()) return startNetworkRerunFromForm(options);
      if (rejectLaunchCommandWhileBusy("rerun.start", "rerun-queue-status", "rerun-queue-detail")) return;
      const request = collectRerunStartRequest({ dry_run: false, plan_only: false });
      const actionLabel = "CSV rerun";
      const modeSummary = rerunStartPolicySummary(request);
      renderLaunchPreflight("rerun-queue-preflight", rerunQueuePreflightLines(request));
      if (!request.csv_path.trim()) {
        const missing = {
          command: "rerun.start",
          ok: false,
          severity: "blocked",
          message: "CSV path is required.",
          frontend_guard: true,
        };
        renderLaunchCommandResult("rerun-queue-status", "rerun-queue-detail", missing, request);
        renderRerunLifecycleEvidence(state.lastRerunPreviewPayload, state.lastRerunCommandResult);
        applyRerunPreviewButtonState();
        return;
      }
      const preview = await refreshRerunPreview({ quiet: true });
      if (!preview || preview.status === "blocked") {
        const blocked = {
          command: "rerun.start",
          ok: false,
          severity: "blocked",
          message: preview?.message || "CSV rerun preview is blocked.",
          frontend_guard: true,
          data: preview || {},
        };
        renderLaunchCommandResult("rerun-queue-status", "rerun-queue-detail", blocked, request);
        renderRerunLifecycleEvidence(state.lastRerunPreviewPayload, state.lastRerunCommandResult);
        applyRerunPreviewButtonState();
        return;
      }
      const rerunButtonId = "rerun-start-button";
      const rerunBtn = byId(rerunButtonId);
      const rerunBtnText = rerunBtn ? rerunBtn.textContent : "";
      setLaunchCommandButtonState(rerunButtonId, "confirming", "Confirming...");
      setText("rerun-queue-status", "Confirming");
      setText("rerun-queue-detail", `Confirm live CSV rerun with ${modeSummary} policy.`);
      await nextLaunchCommandFrame();
      if (!window.confirm(`Start live CSV rerun with ${modeSummary} policy?`)) {
        const canceled = {
          command: "rerun.start",
          ok: false,
          severity: "info",
          message: `${actionLabel} canceled.`,
          data: { dry_run: Boolean(request.dry_run), plan_only: Boolean(request.plan_only) },
          request,
        };
        state.lastRerunCommandResult = canceled;
        appendCommandResult(canceled);
        setText("rerun-queue-status", "Canceled");
        setText("rerun-queue-detail", canceled.message);
        renderRerunLifecycleEvidence(state.lastRerunPreviewPayload, state.lastRerunCommandResult);
        if (rerunBtn) rerunBtn.textContent = rerunBtnText || "Review & Start";
        updateLaunchCommandButtonStates();
        return;
      }
      if (rerunBtn) rerunBtn.textContent = "Starting...";
      setLaunchCommandBusy(true);
      setText("rerun-queue-status", "Starting...");
      renderJsonDetail("rerun-queue-detail", {
        label: "Submitted request",
        value: request,
        intro: "Live CSV rerun request confirmed by the operator and about to be submitted.",
      });
      renderRerunTopbarPending(request, actionLabel, "submitted", "waiting for backend response");
      try {
        const result = await queueRerunRouteDispatcher("postRerunStart")(request);
        const resultWithRequest = { ...result, request };
        state.lastRerunCommandResult = resultWithRequest;
        appendCommandResult(resultWithRequest);
        renderLaunchCommandResult("rerun-queue-status", "rerun-queue-detail", resultWithRequest, request);
        renderRerunLifecycleEvidence(state.lastRerunPreviewPayload, state.lastRerunCommandResult);
        if (result.ok) {
          const pidMatch = String(result.message || "").match(/\bPID\s*(\d+)\b/i);
          const pid = pidMatch ? pidMatch[1] : "";
          window.setTopbarPendingLaunch?.({
            label: actionLabel,
            pid,
            status_label: "accepted",
            wait_label: "waiting for backend event",
          });
          window.mediaPipelineAppTopbar?.renderTopbarActivity?.({
            activity: `${actionLabel} accepted${rerunCsvLeaf(request.csv_path) ? `: ${rerunCsvLeaf(request.csv_path)}` : ""}`,
            current_work: { phase_label: actionLabel },
            progress: { CurrentStage: "CSV rerun" },
          });
        } else {
          renderRerunTopbarFinished(request, actionLabel, `${actionLabel} did not start`);
        }
        if ((result.refresh_hint || "") === "snapshot") {
          await refreshAll();
        }
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        const result = {
          command: "rerun.start",
          ok: false,
          severity: "error",
          message,
          request,
        };
        state.lastRerunCommandResult = result;
        renderRerunTopbarFinished(request, actionLabel, `${actionLabel} failed: ${message}`);
        appendCommandResult(result);
        renderLaunchCommandResult("rerun-queue-status", "rerun-queue-detail", result, request);
        renderRerunLifecycleEvidence(state.lastRerunPreviewPayload, state.lastRerunCommandResult);
      } finally {
        setLaunchCommandBusy(false);
        if (rerunBtn) rerunBtn.textContent = rerunBtnText || "Review & Start";
        applyRerunPreviewButtonState();
      }
    }
  

    return {
      renderRerunPreview,
      networkDryRunFingerprint,
      networkDryRunSafeToApply,
      checkNetworkRerunStartDryRunFromForm,
      startNetworkRerunFromForm,
      startRerunFromForm,
    };
  }

  window.__launchRerunOrchestrationModule = { createLaunchRerunOrchestrationModule };
})();
