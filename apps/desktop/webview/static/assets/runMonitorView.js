(function () {
  "use strict";

  const PROJECTION_SCHEMA = "desktop_run_monitor.v1";
  const LAUNCH_SCHEMA = "desktop_run_monitor_launch.v1";
  const COMPACT_ITEM_LIMIT = 20;

  const LAUNCH_ACCEPTANCE_STATES = new Set(["backend_accepted", "awaiting_engine_confirmation"]);
  const ACTIVE_RUN_STATES = new Set(["starting", "scanning", "running", "paused", "stop_requested", "stopping"]);
  const TERMINAL_ITEM_STATES = new Set(["completed", "failed", "skipped", "blocked", "review", "parked", "stopped"]);
  const ATTENTION_ITEM_STATES = new Set(["failed", "blocked", "review", "parked"]);


  const state = {
    payload: null,
    launchAcceptance: null,
    requestedRunId: "",
    selectedJobId: "",
    focusedJobId: "",
    workloadExpanded: false,
    workloadRunId: "",
    previousItemStates: new Map(),
    previousActiveJobIds: new Set(),
    previousRunState: "",
    previousStopState: "",
    workloadRenderSignature: "",
    workerRenderSignature: "",
    initialized: false,
    refreshPromise: null,
    refreshRunId: "",
    refreshGeneration: 0,
    requestGeneration: 0,
    terminalHandoff: null,
    terminalHandoffObserver: null,
    terminalHandoffApplyTimer: null,
    terminalHandoffExpiryTimer: null,
    terminalHandoffApplying: false,
    terminalHandoffTarget: null,
    liveRegionObserver: null,
    stopCommandBusy: false,
    lastKnownSignature: "",
  };

  function byId(id) {
    return document.getElementById(id);
  }







  function setText(id, value) {
    const node = byId(id);
    if (node) node.textContent = value;
  }

  const runMonitorFormatters = window.__runMonitorFormatters;
  const createRunMonitorNormalization = window.__runMonitorNormalizationModule;
  const createRunMonitorRendering = window.__runMonitorRenderingModule;
  const createRunMonitorInteraction = window.__runMonitorInteractionModule;
  delete window.__runMonitorFormatters;
  delete window.__runMonitorNormalizationModule;
  delete window.__runMonitorRenderingModule;
  delete window.__runMonitorInteractionModule;
  if (!runMonitorFormatters || typeof createRunMonitorNormalization !== "function" || typeof createRunMonitorRendering !== "function" || typeof createRunMonitorInteraction !== "function") {
    throw new Error("Run monitor child modules must load before runMonitorView.js");
  }
  const {
    text, humanize, stageLabel, formatTimestamp, formatAge, trackTimelineLabel, collectionStateLabel,
    progressLabel, subtitleStepLabel,
    subtitleCueLabel, evidenceLabel, routeDisplay, routeUnavailableLabel,
  } = runMonitorFormatters;
  const runMonitorNormalization = createRunMonitorNormalization({
    state, text, humanize, stageLabel, routeDisplay, terminalItemStates: TERMINAL_ITEM_STATES,
    projectionSchema: PROJECTION_SCHEMA,
  });
  const {
    array, object, selectedItem, currentClaimsAllowed, itemEvidenceAllowed, workerJobIds, selectInitialJob,
    visibleLifecycleState, currentStageLabel, routeSummary, displayNameBasis, displayNameAuthorityLabel,
    duplicateDisplayNames, unavailablePayload, launchAcceptancePayload, launchMonitorIdentity,
  } = runMonitorNormalization;
  const runMonitorRendering = createRunMonitorRendering({
    byId, setText, text, array, object, humanize, stageLabel, formatTimestamp, progressLabel, evidenceLabel,
    routeDisplay, routeUnavailableLabel, itemEvidenceAllowed, collectionStateLabel, trackTimelineLabel,
    subtitleStepLabel, subtitleCueLabel,
  });
  const {
    appendFact, appendTechnicalDetails, formatBytes, renderOutcome, renderRouteSummary,
    renderRoutes, renderStages, renderAudio, renderSubtitles,
  } = runMonitorRendering;
  const runMonitorInteraction = createRunMonitorInteraction({
    state, text, array, object, byId, renderItems: (...args) => renderItems(...args),
  });
  const {
    cssEscape, captureDynamicMonitorFocus, restoreDynamicMonitorFocus, handleItemKeydown, selectJob,
    terminalLinkPage, terminalFocusKey, reapplyTerminalHandoff, navigateToTerminalReference, focusSelectedFile,
  } = runMonitorInteraction;

  function enforceSingleHomeLiveRegion() {
    const home = document.querySelector('[data-page-panel="home"]');
    const announcer = byId("run-monitor-announcer");
    if (!home || !announcer) return;
    home.querySelectorAll('[aria-live], [role="status"]').forEach((node) => {
      if (node === announcer) return;
      node.removeAttribute("aria-live");
      if (node.getAttribute("role") === "status") node.removeAttribute("role");
    });
  }

  function observeHomeLiveRegions() {
    if (state.liveRegionObserver || typeof MutationObserver !== "function") return;
    const home = document.querySelector('[data-page-panel="home"]');
    if (!home) return;
    state.liveRegionObserver = new MutationObserver(() => enforceSingleHomeLiveRegion());
    state.liveRegionObserver.observe(home, {
      attributes: true,
      attributeFilter: ["aria-live", "role"],
      childList: true,
      subtree: true,
    });
    enforceSingleHomeLiveRegion();
  }















































  function setFreshness(payload) {
    const freshness = object(payload?.freshness);
    const freshnessState = text(freshness.state, "unavailable");
    const labels = {
      current: "Backend-confirmed current",
      terminal: "Terminal backend evidence",
      stale: "Stale",
      unknown: "Unknown",
      unavailable: "Unavailable",
    };
    const node = byId("run-monitor-freshness");
    if (node) {
      node.textContent = labels[freshnessState] || humanize(freshnessState);
      node.dataset.state = freshnessState;
    }
    const summary = byId("run-monitor-summary");
    if (summary) summary.dataset.state = freshnessState;
    return freshnessState;
  }

  function renderSummary(payload) {
    const freshness = object(payload?.freshness);
    const freshnessState = setFreshness(payload);
    const run = object(payload?.run);
    const counts = object(run.counts);
    const stop = object(run.stop_after_current);
    const awaitingMonitor = LAUNCH_ACCEPTANCE_STATES.has(text(run.launch_acceptance_state));
    setText("run-monitor-mode", text(run.display_mode, "Run Once · Backend Queue"));
    setText("run-monitor-state", run.run_id ? humanize(run.lifecycle_state) : "No run loaded");
    setText("run-monitor-started", formatTimestamp(run.started_at));
    setText("run-monitor-ended", formatTimestamp(run.ended_at));
    setText(
      "run-monitor-updated",
      text(freshness.updated_at)
        ? `${formatTimestamp(freshness.updated_at)} · ${formatAge(freshness.age_seconds)}`
        : "No backend update timestamp",
    );
    setText("run-monitor-stop-state", humanize(stop.state, "Unavailable"));
    const countOrder = ["accepted", "queued", "active", "completed", "parked", "review", "failed", "blocked", "skipped", "stopped"];
    const countText = run.run_id
      ? awaitingMonitor
        ? "Backend accepted the workload; loading durable run-wide file identities."
        : freshnessState === "unavailable"
          ? `Accepted ${Math.max(0, Number(run.accepted_queue?.accepted_count) || array(payload?.items).length)} · current run-scoped counts unavailable.`
        : countOrder.map((key) => `${humanize(key)} ${Math.max(0, Number(counts[key]) || 0)}`).join(" · ")
      : "No accepted workload loaded.";
    setText("run-monitor-counts", countText);
    const outcome = object(run.outcome);
    setText(
      "run-monitor-outcome",
      run.run_id
        ? [
            `Outcome: ${humanize(outcome.state, "Pending")}`,
            text(outcome.reason),
            text(outcome.reason_code) ? `Reason code: ${outcome.reason_code}` : "",
            outcome.retryable === true ? "Retryable: yes" : outcome.retryable === false ? "Retryable: no" : "",
            text(outcome.owner) ? `Owner: ${outcome.owner}` : "",
            text(outcome.next_action),
            outcome.evidence ? evidenceLabel(outcome.evidence) : "",
          ].filter(Boolean).join(" · ")
        : "No run outcome loaded.",
    );
    const authority = [
      text(freshness.reason_code) ? `Freshness decision: ${humanize(freshness.reason_code)}` : "Freshness decision unavailable",
      text(freshness.backend_state) ? `Backend activity: ${humanize(freshness.backend_state)}` : "Backend activity unknown",
      text(run.evidence?.source) ? evidenceLabel(run.evidence) : "Run evidence unavailable",
      text(run.accepted_queue?.fingerprint) ? `Accepted queue fingerprint: ${run.accepted_queue.fingerprint}` : "Accepted queue fingerprint unavailable",
    ];
    setText("run-monitor-authority", authority.join(" · "));

    renderStopAfterCurrentControl(payload);
  }

  function renderStopAfterCurrentControl(payload = state.payload) {
    const stopButton = byId("run-monitor-stop-after-current");
    if (!stopButton) return;
    const freshnessState = text(payload?.freshness?.state, "unavailable");
    const run = object(payload?.run);
    const stop = object(run.stop_after_current);
    const stopState = text(stop.state, "unavailable");
    const active = freshnessState === "current" && ACTIVE_RUN_STATES.has(text(run.lifecycle_state));
    const available = active && stopState === "not_requested" && !state.stopCommandBusy;
    stopButton.disabled = !available;
    stopButton.setAttribute("aria-disabled", available ? "false" : "true");
    stopButton.setAttribute("aria-describedby", "run-monitor-stop-state");
    stopButton.dataset.commandState = state.stopCommandBusy ? "running" : available ? "ready" : "blocked";
    stopButton.title = state.stopCommandBusy
      ? "A backend pipeline control command is in progress."
      : active
        ? stopState === "not_requested"
          ? "Request backend-owned graceful Stop After Current. The current file or active worker set may finish; no new file should start."
          : `Stop After Current is ${humanize(stopState).toLowerCase()}.`
        : "Stop After Current is available only while the backend confirms this Run Once workload is active.";
  }

  function setStopCommandBusy(isBusy) {
    state.stopCommandBusy = Boolean(isBusy);
    renderStopAfterCurrentControl();
  }

  function workerRenderSignature(payload, freshnessState, workers) {
    const itemsByJob = new Map(array(payload?.items).map((item) => [text(item.job_id), item]));
    return JSON.stringify({
      run_id: text(payload?.run?.run_id),
      freshness: freshnessState,
      workers: workers.map((worker) => {
        const item = object(itemsByJob.get(text(worker.job_id)));
        return [
          text(worker.worker_id),
          text(worker.job_id),
          text(worker.state),
          text(worker.stage_id),
          text(worker.route),
          progressLabel(worker.progress),
          evidenceLabel(worker.evidence),
          text(item.display_name),
          text(item.parent_context),
          text(item.source_path),
        ];
      }),
    });
  }

  function renderWorkers(payload, freshnessState) {
    const container = byId("run-monitor-workers");
    if (!container) return;
    const workers = freshnessState === "current" ? array(payload?.current_workers) : [];
    setText("run-monitor-workers-count", `${workers.length} active`);
    const signature = workerRenderSignature(payload, freshnessState, workers);
    if (signature === state.workerRenderSignature && container.hasChildNodes()) return;
    state.workerRenderSignature = signature;
    container.replaceChildren();
    if (!workers.length) {
      const empty = document.createElement("li");
      empty.textContent = freshnessState === "current"
        ? "No backend-confirmed active workers."
        : `Current worker claims are suppressed while freshness is ${humanize(freshnessState).toLowerCase()}.`;
      container.appendChild(empty);
      return;
    }
    const itemsByJob = new Map(array(payload?.items).map((item) => [text(item.job_id), item]));
    workers.forEach((worker) => {
      const item = object(itemsByJob.get(text(worker.job_id)));
      const li = document.createElement("li");
      li.className = "run-monitor-worker";
      li.dataset.state = text(worker.state, "unknown");
      const button = document.createElement("button");
      button.type = "button";
      button.className = "run-monitor-worker-button";
      button.setAttribute("data-run-monitor-job-id", text(worker.job_id));
      button.setAttribute("data-run-monitor-worker-id", text(worker.worker_id));
      const progress = progressLabel(worker.progress);
      const route = text(worker.route) ? `Executed route: ${worker.route}` : "Executed route awaiting backend evidence";
      const visibleIdentity = [
        text(item.display_name, text(worker.job_id, "Active file")),
        text(item.parent_context),
      ].filter(Boolean).join(" · ");
      button.textContent = [
        visibleIdentity,
        `Worker ${text(worker.worker_id, "unknown")} · ${humanize(worker.state)} · ${stageLabel(worker.stage_id)}`,
        route,
        progress,
      ].filter(Boolean).join(" — ");
      button.setAttribute("aria-label", [
        `Active worker for ${text(item.display_name, text(worker.job_id, "accepted file"))}`,
        text(item.source_path) && text(item.source_path) !== text(item.display_name)
          ? `Source ${text(item.source_path)}`
          : "",
        `Worker ${text(worker.worker_id, "unknown")}`,
        `Stage ${stageLabel(worker.stage_id)}`,
        route,
        progress,
        evidenceLabel(worker.evidence),
      ].join(". "));
      button.addEventListener("click", () => selectJob(text(worker.job_id), { focusDetail: false }));
      li.appendChild(button);
      container.appendChild(li);
    });
  }

  function updateWorkloadDisclosure(items) {
    const count = items.length;
    if (count === 0) state.workloadExpanded = false;
    const toggle = byId("run-monitor-items-toggle");
    const visibleCount = state.workloadExpanded ? count : Math.min(count, COMPACT_ITEM_LIMIT);
    setText(
      "run-monitor-items-count",
      !state.workloadExpanded && count > COMPACT_ITEM_LIMIT
        ? `Showing first ${visibleCount} of ${count}`
        : `${count} file${count === 1 ? "" : "s"}`,
    );
    if (!toggle) return;
    toggle.disabled = count === 0;
    toggle.setAttribute("aria-expanded", String(state.workloadExpanded));
    toggle.textContent = state.workloadExpanded
      ? count > COMPACT_ITEM_LIMIT ? `Show first ${COMPACT_ITEM_LIMIT} files` : "Close file selection"
      : count > COMPACT_ITEM_LIMIT ? `Show all ${count} files` : "Open file selection";
  }





  function updateWorkloadNameHelp(items) {
    const bases = items.map((item) => displayNameBasis(item));
    const hasLegacyName = bases.includes("legacy_accepted");
    const hasTerminalName = bases.includes("terminal_output");
    let help;
    if (hasLegacyName) {
      help = "This saved run predates verified cleaned-name evidence. Its unresolved labels remain exactly as accepted; refresh Queue and launch a new Backend Queue Run Once for those names. The folded view shows up to 20 files; open file selection to choose from the complete workload.";
    } else if (hasTerminalName) {
      help = "Names come from the backend production naming plan or exact job-correlated terminal output evidence. The folded view shows up to 20 accepted files; open file selection to choose from the complete workload with Arrow keys, Home, and End.";
    } else {
      help = "Names come from the verified backend production naming plan. The folded view shows up to 20 accepted files; open file selection to choose from the complete workload with Arrow keys, Home, and End.";
    }
    setText("run-monitor-items-help", help);
  }



  function renderCompactItems(container, items, currentIds, freshnessState) {
    items.slice(0, COMPACT_ITEM_LIMIT).forEach((item) => {
      const jobId = text(item.job_id);
      const lifecycleState = visibleLifecycleState(item, freshnessState);
      const li = document.createElement("li");
      li.className = "run-monitor-item-preview";
      li.dataset.state = lifecycleState;
      if (jobId === state.selectedJobId) li.classList.add("is-selected");
      if (currentIds.has(jobId)) li.classList.add("is-current");
      const name = document.createElement("strong");
      name.className = "run-monitor-file-name";
      name.textContent = text(item.display_name, "Unnamed accepted file");
      li.appendChild(name);
      const displayName = text(item.display_name, "Unnamed accepted file");
      li.setAttribute("aria-label", [
        displayName,
        `File ${Number(item.position) || "unknown"} of ${Number(item.total) || items.length}`,
        text(item.source_path) && text(item.source_path) !== displayName ? `Source ${text(item.source_path)}` : "",
        jobId === state.selectedJobId ? "Selected file detail" : "Not selected",
        currentIds.has(jobId) ? "Current backend worker item" : "Not a current worker item",
        `State ${humanize(lifecycleState)}`,
      ].filter(Boolean).join(". "));
      container.appendChild(li);
    });
  }

  function workloadRenderSignature(payload, items, currentIds, freshnessState) {
    return JSON.stringify({
      run_id: text(payload?.run?.run_id),
      launch_acceptance_state: text(payload?.run?.launch_acceptance_state),
      has_run: Boolean(payload?.run),
      freshness: freshnessState,
      expanded: state.workloadExpanded,
      selected_job_id: state.selectedJobId,
      current_job_ids: Array.from(currentIds).sort(),
      items: items.map((item) => {
        const displayNameEvidence = object(item?.display_name_evidence);
        return [
          text(item.job_id),
          text(item.display_name),
          text(displayNameEvidence.source),
          text(displayNameEvidence.provenance),
          text(item.source_path),
          text(item.parent_context),
          Number(item.position) || 0,
          Number(item.total) || 0,
          visibleLifecycleState(item, freshnessState),
          currentStageLabel(item, freshnessState),
          routeSummary(item, freshnessState),
        ];
      }),
    });
  }

  function renderItems(payload, freshnessState) {
    const container = byId("run-monitor-items");
    if (!container) return;
    const activeElement = document.activeElement;
    const focusedItem = activeElement && container.contains(activeElement)
      ? activeElement.closest?.("[data-run-monitor-job-id]")
      : null;
    const focusedBefore = focusedItem?.getAttribute("data-run-monitor-job-id") || "";
    const items = array(payload?.items);
    const currentIds = freshnessState === "current" ? workerJobIds(payload) : new Set();
    state.selectedJobId = selectInitialJob(payload);
    updateWorkloadDisclosure(items);
    updateWorkloadNameHelp(items);
    const signature = workloadRenderSignature(payload, items, currentIds, freshnessState);
    if (signature === state.workloadRenderSignature && container.hasChildNodes()) {
      renderDetail(selectedItem(payload), freshnessState);
      return;
    }
    state.workloadRenderSignature = signature;
    container.replaceChildren();
    if (!items.length) {
      const empty = document.createElement("li");
      empty.className = "run-monitor-empty";
      empty.textContent = LAUNCH_ACCEPTANCE_STATES.has(text(payload?.run?.launch_acceptance_state))
        ? "Backend launch accepted; loading the durable accepted workload. No file identities are shown until that backend evidence exists."
        : payload?.run
          ? "The backend monitor did not return accepted workload rows."
        : "No accepted Run Once workload loaded. Load Queue, then use Launch with Backend Queue.";
      container.appendChild(empty);
      renderDetail(null, freshnessState);
      return;
    }

    if (!state.workloadExpanded) {
      renderCompactItems(container, items, currentIds, freshnessState);
      renderDetail(selectedItem(payload), freshnessState);
      if (focusedBefore) {
        window.setTimeout(() => byId("run-monitor-items-toggle")?.focus({ preventScroll: true }), 0);
      }
      return;
    }

    const duplicateNames = duplicateDisplayNames(items);
    items.forEach((item) => {
      const jobId = text(item.job_id);
      const selected = jobId === state.selectedJobId;
      const current = currentIds.has(jobId);
      const lifecycleState = visibleLifecycleState(item, freshnessState);
      const li = document.createElement("li");
      li.className = "run-monitor-item";
      li.dataset.state = lifecycleState;
      if (selected) li.classList.add("is-selected");
      if (current) li.classList.add("is-current");
      const button = document.createElement("button");
      button.type = "button";
      button.className = "run-monitor-item-button";
      button.setAttribute("data-run-monitor-job-id", jobId);
      button.setAttribute("aria-pressed", String(selected));
      button.tabIndex = selected ? 0 : -1;
      const identity = document.createElement("span");
      identity.className = "run-monitor-identity";
      const name = document.createElement("strong");
      name.className = "run-monitor-file-name";
      name.textContent = text(item.display_name, "Unnamed accepted file");
      identity.appendChild(name);
      if (duplicateNames.has(text(item.display_name, "Unnamed accepted file").toLocaleLowerCase())) {
        const context = document.createElement("span");
        context.className = "run-monitor-parent-context";
        context.textContent = text(item.parent_context, text(item.source_path, "Source context unavailable"));
        identity.appendChild(context);
      }
      const cues = [];
      if (current) cues.push("Current");
      cues.push(humanize(lifecycleState));
      if (selected) cues.push("Selected");
      if (cues.length) {
        const cue = document.createElement("span");
        cue.className = "run-monitor-compact-cue";
        cue.dataset.state = lifecycleState;
        cue.textContent = cues.join(" · ");
        button.append(identity, cue);
      } else {
        button.appendChild(identity);
      }
      const displayName = text(item.display_name, "Unnamed accepted file");
      button.setAttribute("aria-label", [
        displayName,
        `File ${Number(item.position) || "unknown"} of ${Number(item.total) || items.length}`,
        text(item.source_path) && text(item.source_path) !== displayName ? `Source ${text(item.source_path)}` : "",
        selected ? "Selected file detail" : "Not selected",
        current ? "Current backend worker item" : "Not a current worker item",
        `State ${humanize(lifecycleState)}`,
        `Stage ${currentStageLabel(item, freshnessState)}`,
        routeSummary(item, freshnessState),
      ].filter(Boolean).join(". "));
      button.addEventListener("click", () => selectJob(jobId, { focusDetail: false }));
      button.addEventListener("keydown", handleItemKeydown);
      li.appendChild(button);
      container.appendChild(li);
    });
    renderDetail(selectedItem(payload), freshnessState);
    const restoreJobId = items.some((item) => text(item.job_id) === focusedBefore) ? focusedBefore : "";
    if (restoreJobId) {
      window.setTimeout(() => {
        const next = container.querySelector(`[data-run-monitor-job-id="${cssEscape(restoreJobId)}"]`);
        if (next && typeof next.focus === "function") next.focus({ preventScroll: true });
      }, 0);
    }
  }

































































  function renderSuppressedOutput(freshnessState) {
    const list = byId("run-monitor-output");
    const evidenceList = byId("run-monitor-output-evidence");
    const sidecars = byId("run-monitor-sidecars");
    const recovery = byId("run-monitor-recovery");
    const links = byId("run-monitor-terminal-links");
    if (list) {
      list.replaceChildren();
      appendFact(list, "Output evidence", `Suppressed while freshness is ${humanize(freshnessState).toLowerCase()}.`);
    }
    if (evidenceList) {
      evidenceList.replaceChildren();
      appendFact(evidenceList, "Output evidence", `Suppressed while freshness is ${humanize(freshnessState).toLowerCase()}.`);
    }
    if (sidecars) {
      sidecars.replaceChildren();
      const suppressed = document.createElement("p");
      suppressed.textContent = `Current sidecar claims are suppressed while freshness is ${humanize(freshnessState).toLowerCase()}.`;
      sidecars.appendChild(suppressed);
    }
    if (recovery) {
      recovery.replaceChildren();
      const suppressed = document.createElement("p");
      suppressed.textContent = `Current recovery guidance is suppressed while freshness is ${humanize(freshnessState).toLowerCase()}.`;
      recovery.appendChild(suppressed);
    }
    if (links) links.replaceChildren();
  }

  function renderOutputFacts(output) {
    const list = byId("run-monitor-output");
    if (list) {
      list.replaceChildren();
      appendFact(list, "Output state", humanize(output.state));
      appendFact(list, "Verification", humanize(output.verification_state));
      const sizeBytes = output.size_bytes;
      if (typeof sizeBytes === "number" && Number.isFinite(sizeBytes) && sizeBytes >= 0) {
        appendFact(list, "Verified size", formatBytes(sizeBytes));
      }
      if (text(output.published_path)) appendFact(list, "Published destination", output.published_path);
      if (text(output.parked_path)) appendFact(list, "Parked destination", output.parked_path);
      if (!text(output.published_path) && !text(output.parked_path) && text(output.intended_final_path)) {
        appendFact(list, "Intended destination", output.intended_final_path);
      }
    }
    const evidenceList = byId("run-monitor-output-evidence");
    if (evidenceList) {
      evidenceList.replaceChildren();
      const sizeBytes = output.size_bytes;
      appendFact(evidenceList, "Exact verified size", typeof sizeBytes === "number" && Number.isFinite(sizeBytes) && sizeBytes >= 0 ? `${sizeBytes.toLocaleString()} bytes` : "Unknown");
      appendFact(evidenceList, "Scratch path", text(output.scratch_path, "Not reported"));
      appendFact(evidenceList, "Working output path", text(output.working_output_path, "Not reported"));
      appendFact(evidenceList, "Published path", text(output.published_path, "Not reported"));
      appendFact(evidenceList, "Parked path", text(output.parked_path, "Not reported"));
      appendFact(evidenceList, "Intended final destination", text(output.intended_final_path, "Not reported"));
      appendFact(evidenceList, "Output evidence", evidenceLabel(output.evidence));
    }
  }

  function renderOutput(item, freshnessState) {
    const output = object(item?.output);
    const sidecars = byId("run-monitor-sidecars");
    const recovery = byId("run-monitor-recovery");
    const links = byId("run-monitor-terminal-links");
    if (!itemEvidenceAllowed(item, freshnessState)) {
      renderSuppressedOutput(freshnessState);
      return;
    }
    renderOutputFacts(output);
    if (sidecars) {
      sidecars.replaceChildren();
      const heading = document.createElement("h4");
      heading.textContent = "Sidecar results";
      const rows = array(output.sidecars);
      if (!rows.length) {
        heading.setAttribute("data-advanced", "");
        sidecars.appendChild(heading);
        const empty = document.createElement("p");
        empty.setAttribute("data-advanced", "");
        empty.textContent = "No backend sidecar result evidence reported.";
        sidecars.appendChild(empty);
      } else {
        sidecars.appendChild(heading);
        const ul = document.createElement("ul");
        rows.forEach((sidecar) => {
          const li = document.createElement("li");
          li.dataset.state = text(sidecar.state, "unknown");
          li.textContent = [humanize(sidecar.kind), humanize(sidecar.state), text(sidecar.path)].filter(Boolean).join(" · ");
          appendTechnicalDetails(li, [text(sidecar.reason), evidenceLabel(sidecar.evidence)]);
          ul.appendChild(li);
        });
        sidecars.appendChild(ul);
      }
    }
    if (recovery) {
      recovery.replaceChildren();
      const failure = object(item?.failure);
      const guidance = object(item?.recovery);
      const title = document.createElement("h4");
      title.textContent = "Recovery and next action";
      const lifecycleState = text(item?.lifecycle_state, "unknown");
      const nextAction = text(guidance.next_action);
      const actionRequired = ["failed", "blocked", "review", "parked", "stopped"].includes(lifecycleState)
        || Boolean(nextAction && nextAction.toLowerCase() !== "no action required.");
      if (!actionRequired) title.setAttribute("data-advanced", "");
      const detail = document.createElement("p");
      detail.textContent = [
        text(failure.state) && text(failure.state) !== "none" ? `Failure state: ${humanize(failure.state)}` : "",
        text(failure.reason),
        actionRequired
          ? failure.retryable === true ? "Retryable: yes" : failure.retryable === false ? "Retryable: no" : "Retryability: unknown"
          : "",
        `Owner: ${text(guidance.owner, "pipeline")}`,
        text(guidance.next_action, "No next action reported"),
      ].filter(Boolean).join(" · ");
      if (!actionRequired) detail.setAttribute("data-advanced", "");
      const technical = document.createElement("p");
      technical.className = "run-monitor-technical-detail";
      technical.setAttribute("data-advanced", "");
      technical.textContent = [
        text(failure.reason_code) ? `Reason code: ${failure.reason_code}` : "",
        failure.retryable === true ? "Retryable: yes" : failure.retryable === false ? "Retryable: no" : "Retryability: unknown",
        evidenceLabel(guidance.evidence),
      ].filter(Boolean).join(" · ");
      recovery.append(title, detail, technical);
    }
    if (links) {
      links.replaceChildren();
      const renderedTargets = new Set();
      array(item?.terminal_references).forEach((reference) => {
        const page = terminalLinkPage(reference, item);
        if (!page) return;
        const focusKey = terminalFocusKey(page, reference);
        if (renderedTargets.has(focusKey)) return;
        renderedTargets.add(focusKey);
        const button = document.createElement("button");
        button.type = "button";
        button.className = "secondary-button";
        button.dataset.runMonitorDeepLink = page;
        button.setAttribute("data-run-monitor-terminal-key", focusKey);
        const referenceKind = text(reference.kind);
        const destinationLabel = page === "pending"
          ? referenceKind === "manifest" ? "Pending Publish manifest" : "Pending Publish"
          : page === "completed"
            ? referenceKind === "sidecar" ? "Completed Sidecar" : "Completed Output"
            : "Reports";
        button.textContent = `Open ${destinationLabel} proof`;
        button.setAttribute("aria-label", [
          button.textContent,
          `${humanize(reference.kind)} reference ${text(reference.reference)}`,
          text(reference.path),
        ].filter(Boolean).join(". "));
        button.title = [text(reference.reference), text(reference.path), evidenceLabel(reference.evidence)].filter(Boolean).join("\n");
        button.addEventListener("click", () => navigateToTerminalReference(reference, item));
        links.appendChild(button);
      });
    }
  }

  function renderDetail(item, freshnessState) {
    if (!item) {
      setText("run-monitor-detail-heading", "Selected file");
      setText("run-monitor-detail-state", "No selection");
      setText("run-monitor-source", "Select an accepted file to inspect its outcome.");
      setText("run-monitor-identity-evidence", "Source identity will appear after the backend monitor loads.");
      renderOutcome({}, freshnessState);
      renderRouteSummary({}, freshnessState);
      renderRoutes({}, freshnessState);
      renderStages({}, freshnessState);
      renderAudio({}, freshnessState);
      renderSubtitles({}, freshnessState);
      renderOutput({}, freshnessState);
      setText("run-monitor-evidence", "Evidence source, timestamp, and freshness will appear after the backend monitor loads.");
      return;
    }
    setText("run-monitor-detail-heading", text(item.display_name, "Selected file"));
    setText("run-monitor-detail-state", `${Number(item.position) || "?"} / ${Number(item.total) || "?"} · ${humanize(visibleLifecycleState(item, freshnessState))}`);
    const duplicateNames = duplicateDisplayNames(array(state.payload?.items));
    const selectedName = text(item.display_name, "Selected file").toLocaleLowerCase();
    setText("run-monitor-source", duplicateNames.has(selectedName) ? text(item.parent_context, "Backend-selected file") : "Backend-selected file");
    setText("run-monitor-identity-evidence", [text(item.source_path), `Job ID ${text(item.job_id)}`, `Source identity ${text(item.source_identity?.value, "unknown")} (${text(item.source_identity?.algorithm, "algorithm unknown")})`].filter(Boolean).join(" · "));
    renderOutcome(item, freshnessState);
    renderRouteSummary(item, freshnessState);
    renderRoutes(item, freshnessState);
    renderStages(item, freshnessState);
    renderAudio(item, freshnessState);
    renderSubtitles(item, freshnessState);
    renderOutput(item, freshnessState);
    setText("run-monitor-evidence", [
      `Monitor freshness: ${humanize(freshnessState)}`,
      `Item updated: ${formatTimestamp(item.updated_at)}`,
      displayNameAuthorityLabel(item),
      `File name evidence: ${evidenceLabel(item.display_name_evidence)}`,
      evidenceLabel(item.lifecycle_evidence),
    ].join(" · "));
  }

  function renderLastKnown(payload) {
    const details = byId("run-monitor-last-known");
    const body = byId("run-monitor-last-known-body");
    if (!details || !body) return;
    const lastKnown = object(payload?.last_known);
    const hasLastKnown = Boolean(text(lastKnown.label)) && (array(lastKnown.items).length > 0 || array(lastKnown.current_workers).length > 0);
    details.hidden = !hasLastKnown;
    if (!hasLastKnown) {
      body.replaceChildren();
      state.lastKnownSignature = "";
      return;
    }
    const summary = details.querySelector("summary");
    if (summary) summary.textContent = "Last known — not current";
    setText("run-monitor-last-known-meta", [
      formatTimestamp(lastKnown.updated_at),
      formatAge(lastKnown.age_seconds),
      "This disclosure is historical and does not populate current file, stage, route, worker, or progress claims.",
    ].join(" · "));
    const workers = array(lastKnown.current_workers);
    const items = array(lastKnown.items);
    const signature = JSON.stringify({
      updated_at: text(lastKnown.updated_at),
      workers: workers.map((worker) => [text(worker.worker_id), text(worker.job_id), text(worker.stage_id), text(worker.updated_at)]),
      items: items.map((item) => [text(item.job_id), text(item.lifecycle_state), text(item.updated_at)]),
    });
    if (signature === state.lastKnownSignature) return;
    const wasOpen = details.open;
    body.replaceChildren();
    const workerHeading = document.createElement("h3");
    workerHeading.textContent = `Last known workers (${workers.length})`;
    const workerList = document.createElement("ul");
    workers.forEach((worker) => {
      const li = document.createElement("li");
      li.tabIndex = -1;
      li.dataset.lastKnownWorkerId = text(worker.worker_id);
      li.textContent = [text(worker.worker_id), text(worker.job_id), stageLabel(worker.stage_id), progressLabel(worker.progress), evidenceLabel(worker.evidence)].filter(Boolean).join(" · ");
      workerList.appendChild(li);
    });
    if (!workers.length) {
      const li = document.createElement("li");
      li.textContent = "No last-known worker rows.";
      workerList.appendChild(li);
    }
    const itemHeading = document.createElement("h3");
    itemHeading.textContent = `Last known accepted workload (${items.length})`;
    const itemList = document.createElement("ol");
    items.forEach((item) => {
      const li = document.createElement("li");
      li.tabIndex = -1;
      li.dataset.lastKnownJobId = text(item.job_id);
      li.textContent = [
        `${Number(item.position) || "?"} / ${Number(item.total) || "?"}`,
        text(item.source_path, text(item.display_name)),
        text(item.job_id),
        humanize(item.lifecycle_state),
        currentStageLabel(item, "current"),
      ].join(" · ");
      itemList.appendChild(li);
    });
    body.append(workerHeading, workerList, itemHeading, itemList);
    state.lastKnownSignature = signature;
    details.open = wasOpen;
  }

  function meaningfulAnnouncement(payload) {
    const freshnessState = text(payload?.freshness?.state, "unavailable");
    if (!currentClaimsAllowed(freshnessState)) return "";
    const run = object(payload?.run);
    const workers = array(payload?.current_workers);
    const items = array(payload?.items);
    const activeJobIdentity = (worker) => text(worker.job_id, text(worker.worker_id));
    const currentActiveJobIds = new Set(workers.map(activeJobIdentity).filter(Boolean));
    const messages = [];
    if (state.payload) {
      const newActiveWorkers = workers.filter((worker) => !state.previousActiveJobIds.has(activeJobIdentity(worker)));
      if (newActiveWorkers.length) {
        const itemsByJob = new Map(items.map((item) => [text(item.job_id), item]));
        const announcedJobs = new Set();
        const newlyActiveLabels = newActiveWorkers.flatMap((worker) => {
          const jobId = text(worker.job_id);
          const identity = activeJobIdentity(worker);
          if (!identity || announcedJobs.has(identity)) return [];
          announcedJobs.add(identity);
          const item = object(itemsByJob.get(jobId));
          return [[text(item.display_name, identity), text(item.parent_context)].filter(Boolean).join(" — ")];
        });
        if (newlyActiveLabels.length) messages.push(`Current work changed: ${newlyActiveLabels.join(", ")}.`);
      }
      items.forEach((item) => {
        const jobId = text(item.job_id);
        const itemState = text(item.lifecycle_state);
        if (ATTENTION_ITEM_STATES.has(itemState) && state.previousItemStates.get(jobId) !== itemState) {
          const identity = [text(item.display_name, jobId), text(item.parent_context)].filter(Boolean).join(" — ");
          messages.push(`${identity} is now ${humanize(itemState).toLowerCase()}.`);
        }
      });
      const stopState = text(run.stop_after_current?.state);
      if (["requested", "acknowledged", "stopping"].includes(stopState) && state.previousStopState !== stopState) {
        messages.push(`Stop After Current ${humanize(stopState).toLowerCase()}.`);
      }
      const runState = text(run.lifecycle_state);
      if (runState === "completed" && state.previousRunState !== "completed") messages.push("Run Once workload complete.");
    }
    state.previousActiveJobIds = currentActiveJobIds;
    state.previousItemStates = new Map(items.map((item) => [text(item.job_id), text(item.lifecycle_state)]));
    state.previousRunState = text(run.lifecycle_state);
    state.previousStopState = text(run.stop_after_current?.state);
    return messages.join(" ");
  }

  function announce(message) {
    const normalized = text(message);
    if (!normalized) return;
    const node = byId("run-monitor-announcer");
    if (!node) return;
    node.textContent = "";
    window.setTimeout(() => { node.textContent = normalized; }, 20);
  }







  function render(payload) {
    const projection = object(payload);
    if (text(projection.schema_version) !== PROJECTION_SCHEMA) {
      return render(unavailablePayload("invalid_projection", "The backend response was absent or did not use desktop_run_monitor.v1."));
    }
    const dynamicFocus = captureDynamicMonitorFocus();
    const normalized = {
      ...projection,
      items: array(projection.items),
      current_workers: array(projection.current_workers),
    };
    const runId = text(normalized.run?.run_id);
    if (runId && runId !== state.workloadRunId) {
      state.workloadRunId = runId;
      state.workloadExpanded = false;
    }
    const announcement = meaningfulAnnouncement(normalized);
    state.payload = normalized;
    const freshnessState = text(normalized.freshness?.state, "unavailable");
    renderSummary(normalized);
    renderWorkers(normalized, freshnessState);
    renderItems(normalized, freshnessState);
    renderLastKnown(normalized);
    restoreDynamicMonitorFocus(dynamicFocus);
    enforceSingleHomeLiveRegion();
    announce(announcement);
    window.dispatchEvent(new CustomEvent("mediapipeline:run-monitor-rendered", {
      detail: {
        run_id: text(normalized.run?.run_id),
        freshness: freshnessState,
        selected_job_id: state.selectedJobId,
        item_count: normalized.items.length,
        worker_count: freshnessState === "current" ? normalized.current_workers.length : 0,
      },
    }));
    return normalized;
  }

  async function refresh(options = {}) {
    const requestedRunId = state.requestedRunId;
    const requestGeneration = state.requestGeneration;
    if (state.refreshPromise) {
      if (state.refreshRunId === requestedRunId && state.refreshGeneration === requestGeneration) {
        return state.refreshPromise;
      }
      return state.refreshPromise.finally(() => {
        if (state.requestedRunId !== requestedRunId || state.requestGeneration !== requestGeneration) return state.payload;
        return refresh(options);
      });
    }
    const baseRoute = "/api/run-monitor";
    const route = requestedRunId ? `${baseRoute}?run_id=${encodeURIComponent(requestedRunId)}` : baseRoute;
    state.refreshRunId = requestedRunId;
    state.refreshGeneration = requestGeneration;
    state.refreshPromise = (async () => {
      const button = byId("run-monitor-refresh");
      if (button && options.automatic !== true) {
        button.disabled = true;
        button.setAttribute("aria-busy", "true");
        button.textContent = "Refreshing…";
      }
      try {
        if (typeof window.apiGet !== "function") throw new Error("Local API client unavailable");
        const payload = await window.apiGet(route, { timeoutMs: options.automatic === true ? 8000 : 30000 });
        if (state.requestedRunId !== requestedRunId || state.requestGeneration !== requestGeneration) return state.payload;
        if (
          state.launchAcceptance
          && !payload?.run
          && text(payload?.freshness?.reason_code) === "monitor_not_found"
        ) {
          return state.payload;
        }
        if (text(payload?.run?.run_id) === state.requestedRunId) state.launchAcceptance = null;
        return render(payload);
      } catch (error) {
        if (state.requestedRunId !== requestedRunId || state.requestGeneration !== requestGeneration) return state.payload;
        const message = error instanceof Error ? error.message : String(error);
        return render(unavailablePayload("read_failed", message));
      } finally {
        if (button) {
          button.disabled = false;
          button.removeAttribute("aria-busy");
          button.textContent = "Refresh";
        }
        state.refreshPromise = null;
        state.refreshRunId = "";
        state.refreshGeneration = 0;
      }
    })();
    return state.refreshPromise;
  }



  function backendQueueCorrelationContext() {
    return {
      expected: Boolean(state.requestedRunId),
      requested_run_id: state.requestedRunId,
      projected_run_id: text(state.payload?.run?.run_id),
      freshness: text(state.payload?.freshness?.state, "unavailable"),
    };
  }

  function clearBackendQueueContext() {
    state.requestedRunId = "";
    state.launchAcceptance = null;
    state.requestGeneration += 1;
  }

  function acceptLaunchResult(result, options = {}) {
    const identity = launchMonitorIdentity(result);
    if (
      identity.schema !== LAUNCH_SCHEMA
      || !LAUNCH_ACCEPTANCE_STATES.has(identity.acceptanceState)
      || !identity.runId
      || !identity.fingerprint
      || identity.route !== "/api/run-monitor"
    ) return false;
    state.requestedRunId = identity.runId;
    state.requestGeneration += 1;
    state.launchAcceptance = identity;
    render(launchAcceptancePayload(identity));
    void refresh({ automatic: false });
    if (options.navigate !== false) {
      const navigation = window.mediaPipelineAppLifecycle || {};
      if (typeof navigation.navigateToPage === "function") {
        navigation.navigateToPage("home", { focusSelector: "#current-work-heading", restoreFocus: false });
      } else {
        window.showPage?.("home");
        window.setTimeout(() => byId("current-work-heading")?.focus(), 0);
      }
    }
    return true;
  }



  function init() {
    if (state.initialized) return;
    state.initialized = true;
    observeHomeLiveRegions();
    byId("run-monitor-refresh")?.addEventListener("click", () => { void refresh({ automatic: false }); });
    byId("run-monitor-items-toggle")?.addEventListener("click", (event) => {
      state.workloadExpanded = !state.workloadExpanded;
      renderItems(state.payload, text(state.payload?.freshness?.state, "unavailable"));
      if (!state.workloadExpanded) {
        window.setTimeout(() => event.currentTarget?.focus({ preventScroll: true }), 0);
      }
    });
    window.addEventListener("mediapipeline:focus-current-work", (event) => {
      focusSelectedFile({ detail: event?.detail?.detail === true });
    });
    void refresh({ automatic: true });
  }

  /**
   * Public namespace for the read-only backend Run Once monitor projection.
   * Boundary: renders backend-authored evidence and stages operator navigation;
   * it does not infer media policy, mutate queue scope, or touch media files.
   * No flat window.* exports are provided; consumers use this namespace only.
   */
  window.mediaPipelineRunMonitor = {
    acceptLaunchResult,
    backendQueueCorrelationContext,
    clearBackendQueueContext,
    focusSelectedFile,
    getPayload: () => state.payload,
    getSelectedJobId: () => state.selectedJobId,
    init,
    launchMonitorIdentity,
    reapplyTerminalHandoff,
    refresh,
    render,
    selectJob,
    setStopCommandBusy,
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, { once: true });
  } else {
    init();
  }
})();
