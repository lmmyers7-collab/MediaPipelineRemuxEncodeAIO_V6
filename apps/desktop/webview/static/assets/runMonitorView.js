(function () {
  "use strict";

  const PROJECTION_SCHEMA = "desktop_run_monitor.v1";
  const LAUNCH_SCHEMA = "desktop_run_monitor_launch.v1";
  const COMPACT_ITEM_LIMIT = 20;
  const VERIFIED_DISPLAY_NAME_SOURCE = "plex_destination_plan.v1";
  const LAUNCH_ACCEPTANCE_STATES = new Set(["backend_accepted", "awaiting_engine_confirmation"]);
  const ACTIVE_RUN_STATES = new Set(["starting", "scanning", "running", "paused", "stop_requested", "stopping"]);
  const TERMINAL_ITEM_STATES = new Set(["completed", "failed", "skipped", "blocked", "review", "parked", "stopped"]);
  const ATTENTION_ITEM_STATES = new Set(["failed", "blocked", "review", "parked"]);
  const STAGE_LABELS = Object.freeze({
    accepted: "Accepted into run",
    source_discovery: "Source discovery / scanning",
    copy_to_scratch: "Copy to scratch",
    probe: "Probe",
    route_decision: "Route decision",
    audio: "Audio policy",
    subtitles: "Subtitle policy / work",
    transcode: "Encode or remux",
    mux: "Mux",
    verification: "Verification",
    sidecar_writing: "Sidecar writing",
    publish: "Direct publish or park",
    final_evidence: "Final run evidence",
  });
  const TERMINAL_LINK_PAGES = Object.freeze({
    completed: "completed",
    pending_publish: "pending",
    failure: "reports",
    review: "reports",
    report: "reports",
    sidecar: "completed",
  });
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

  function text(value, fallback = "") {
    const normalized = value === null || value === undefined ? "" : String(value).trim();
    return normalized || fallback;
  }

  function array(value) {
    return Array.isArray(value) ? value.filter(Boolean) : [];
  }

  function object(value) {
    return value && typeof value === "object" && !Array.isArray(value) ? value : {};
  }

  function setText(id, value) {
    const node = byId(id);
    if (node) node.textContent = value;
  }

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

  function humanize(value, fallback = "Unknown") {
    const normalized = text(value);
    if (!normalized) return fallback;
    return normalized
      .replace(/[_-]+/g, " ")
      .replace(/\s+/g, " ")
      .trim()
      .replace(/\b\w/g, (letter) => letter.toUpperCase());
  }

  function stageLabel(stageId) {
    return STAGE_LABELS[text(stageId)] || humanize(stageId, "Unknown stage");
  }

  function formatTimestamp(value, fallback = "—") {
    const normalized = text(value);
    if (!normalized) return fallback;
    const parsed = Date.parse(normalized);
    if (!Number.isFinite(parsed)) return normalized;
    try {
      return new Date(parsed).toLocaleString([], {
        year: "numeric",
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      });
    } catch (_error) {
      return normalized;
    }
  }

  function formatAge(value) {
    const seconds = Number(value);
    if (!Number.isFinite(seconds) || seconds < 0) return "age unknown";
    if (seconds < 1) return "just now";
    if (seconds < 60) return `${Math.floor(seconds)}s ago`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${Math.floor(seconds % 60)}s ago`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m ago`;
    return `${Math.floor(seconds / 86400)}d ago`;
  }

  function formatDurationSeconds(value) {
    const seconds = Number(value);
    if (!Number.isFinite(seconds) || seconds < 0) return "";
    const whole = Math.floor(seconds);
    if (whole < 60) return `${whole}s`;
    if (whole < 3600) return `${Math.floor(whole / 60)}m ${whole % 60}s`;
    return `${Math.floor(whole / 3600)}h ${Math.floor((whole % 3600) / 60)}m`;
  }

  function trackTimingLabel(track) {
    const startedAt = Date.parse(text(track?.started_at));
    if (!Number.isFinite(startedAt)) return "";
    const completedAt = Date.parse(text(track?.completed_at));
    const end = Number.isFinite(completedAt) ? completedAt : Date.now();
    if (end < startedAt) return "";
    const duration = formatDurationSeconds((end - startedAt) / 1000);
    if (!duration) return "";
    return Number.isFinite(completedAt) ? `Duration ${duration}` : `Elapsed ${duration}`;
  }

  function trackTimelineLabel(track) {
    return [
      text(track?.started_at) ? `Started ${formatTimestamp(track.started_at)}` : "",
      text(track?.updated_at) ? `Updated ${formatTimestamp(track.updated_at)}` : "",
      text(track?.completed_at) ? `Completed ${formatTimestamp(track.completed_at)}` : "",
      trackTimingLabel(track),
    ].filter(Boolean).join(" · ");
  }

  function collectionStateLabel(collection) {
    const record = object(collection);
    return [
      humanize(record.state),
      record.policy_final === true ? "Terminal policy evidence" : "Policy evidence not terminal",
    ].join(" · ");
  }

  function progressUnitLabel(value) {
    const normalized = text(value).toLowerCase();
    if (!normalized || normalized === "unknown") return "";
    const known = new Set(["items", "pages", "cues", "frames", "seconds", "bytes", "percent"]);
    return known.has(normalized) ? normalized : "";
  }

  function progressLabel(progress, unit = "") {
    const evidence = object(progress);
    const kind = text(evidence.kind, "none");
    const unitLabel = progressUnitLabel(unit);
    if (kind === "indeterminate") return `Working${unitLabel ? ` (${unitLabel})` : ""} · progress is indeterminate`;
    if (kind !== "determinate") return "";
    const numerator = Number(evidence.numerator);
    const denominator = Number(evidence.denominator);
    if (!Number.isFinite(numerator) || !Number.isFinite(denominator) || denominator <= 0 || numerator < 0 || numerator > denominator) {
      return "Progress evidence invalid";
    }
    const percent = (numerator / denominator) * 100;
    return `${numerator} / ${denominator}${unitLabel ? ` ${unitLabel}` : ""} · ${Math.round(percent * 10) / 10}%`;
  }

  function subtitleStepLabel(track) {
    const stepIndex = Number(track?.step_index);
    const stepTotal = Number(track?.step_total);
    const stepName = text(track?.step_name);
    const position = Number.isInteger(stepIndex) && Number.isInteger(stepTotal) && stepTotal > 0 && stepIndex >= 0 && stepIndex <= stepTotal
      ? `Step ${stepIndex} of ${stepTotal}`
      : "";
    return [position, stepName ? humanize(stepName) : ""].filter(Boolean).join(" · ");
  }

  function subtitleCueLabel(track) {
    if (track?.cue_count === null || track?.cue_count === undefined || track?.cue_count === "") return "";
    const count = Number(track.cue_count);
    return Number.isInteger(count) && count >= 0 ? `Cues ${count}` : "Cue count evidence invalid";
  }

  function evidenceLabel(evidence) {
    const record = object(evidence);
    return [
      text(record.source) ? `Source: ${record.source}` : "Source: unknown",
      text(record.provenance) ? `Provenance: ${humanize(record.provenance)}` : "Provenance: unknown",
      text(record.recorded_at) ? `Recorded: ${formatTimestamp(record.recorded_at)}` : "Timestamp: unknown",
    ].join(" · ");
  }

  function routeDisplay(route, fallbackLabel, fallbackReasonLabel) {
    const record = object(route);
    const stateValue = text(record.state, "unknown");
    const available = stateValue === "available" && Boolean(text(record.value));
    const explainsUnavailable = stateValue === "unknown" || stateValue === "not_applicable";
    return {
      label: text(record.label, fallbackLabel),
      reasonLabel: text(record.reason_label, fallbackReasonLabel),
      state: stateValue,
      value: available ? text(record.value) : "",
      reason: available || explainsUnavailable ? text(record.reason) : "",
      reasonCode: available || explainsUnavailable ? text(record.reason_code) : "",
      evidence: object(record.evidence),
    };
  }

  function routeUnavailableLabel(route) {
    if (route.state === "awaiting_evidence") return "Awaiting backend evidence";
    if (route.state === "not_applicable") return "Not applicable";
    return "Unknown";
  }

  function selectedItem(payload = state.payload) {
    return array(payload?.items).find((item) => text(item?.job_id) === state.selectedJobId) || null;
  }

  function currentClaimsAllowed(freshnessState) {
    return freshnessState === "current" || freshnessState === "terminal";
  }

  function itemEvidenceAllowed(item, freshnessState) {
    // A stale or unavailable run must not revive live claims. Terminal item
    // artifacts are historical proof, however, and remain useful/selectable
    // after live evidence has aged out.
    return currentClaimsAllowed(text(freshnessState))
      || TERMINAL_ITEM_STATES.has(text(item?.lifecycle_state));
  }

  function workerJobIds(payload = state.payload) {
    return new Set(array(payload?.current_workers).map((worker) => text(worker?.job_id)).filter(Boolean));
  }

  function selectInitialJob(payload) {
    const items = array(payload?.items);
    if (!items.length) return "";
    if (items.some((item) => text(item.job_id) === state.selectedJobId)) return state.selectedJobId;
    if (text(payload?.freshness?.state) === "current") {
      const currentIds = workerJobIds(payload);
      const workerItem = items.find((item) => currentIds.has(text(item.job_id)));
      if (workerItem) return text(workerItem.job_id);
      const activeItem = items.find((item) => text(item.lifecycle_state) === "active");
      if (activeItem) return text(activeItem.job_id);
    }
    return text(items[0]?.job_id);
  }

  function visibleLifecycleState(item, freshnessState) {
    const lifecycleState = text(item?.lifecycle_state, "unknown");
    if (currentClaimsAllowed(text(freshnessState)) || TERMINAL_ITEM_STATES.has(lifecycleState)) return lifecycleState;
    return "unknown";
  }

  function currentStageLabel(item, freshnessState) {
    const record = object(item);
    const freshness = text(freshnessState);
    if (!itemEvidenceAllowed(record, freshness)) return `Suppressed · ${humanize(freshness)}`;
    if (freshness === "current") {
      const current = object(record.current_stage);
      if (text(current.stage_id) && text(current.state) === "active") return stageLabel(current.stage_id);
    }
    const stages = array(record.stages);
    const explicit = [...stages].reverse().find((stage) => text(stage.state) !== "not_started");
    if (explicit) return `${stageLabel(explicit.stage_id)} · ${humanize(explicit.state)}`;
    if (text(record.lifecycle_state) === "queued" || text(record.lifecycle_state) === "accepted") return "Not started";
    return "Unknown";
  }

  function routeSummary(item, freshnessState) {
    if (!itemEvidenceAllowed(item, freshnessState)) return `Route claims suppressed · ${humanize(freshnessState)}`;
    const record = object(item);
    const finalRoute = routeDisplay(record.final_route, "Final route", "Final reason");
    if (finalRoute.value) return `Final route: ${finalRoute.value}`;
    const executedRoute = routeDisplay(record.executed_route, "Executed route", "Executed reason");
    if (executedRoute.value) return `Executed route: ${executedRoute.value}`;
    const plannedRoute = routeDisplay(record.planned_route, "Planned route", "Planned reason");
    if (plannedRoute.value) return `Planned route: ${plannedRoute.value}`;
    return "Route evidence unknown";
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

  function displayNameBasis(item) {
    const declaredBasis = text(item?.display_name_basis);
    if (["verified_queue_plan", "terminal_output", "legacy_accepted"].includes(declaredBasis)) return declaredBasis;
    const evidence = object(item?.display_name_evidence);
    if (text(evidence.source) === VERIFIED_DISPLAY_NAME_SOURCE && text(evidence.provenance) === "queue_plan") {
      return "verified_queue_plan";
    }
    return "legacy_accepted";
  }

  function displayNameAuthorityLabel(item) {
    const basis = displayNameBasis(item);
    if (basis === "verified_queue_plan") {
      return "File name authority: Verified backend production naming plan";
    }
    if (basis === "terminal_output") {
      return "File name authority: Exact job-correlated terminal output evidence";
    }
    return "File name authority: Legacy accepted label; cleaned-name evidence unknown";
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

  function duplicateDisplayNames(items) {
    const counts = new Map();
    items.forEach((item) => {
      const key = text(item.display_name, "Unnamed accepted file").toLocaleLowerCase();
      counts.set(key, (counts.get(key) || 0) + 1);
    });
    return new Set(Array.from(counts.entries()).filter(([, count]) => count > 1).map(([key]) => key));
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

  function cssEscape(value) {
    if (window.CSS && typeof window.CSS.escape === "function") return window.CSS.escape(String(value));
    return String(value).replace(/(["\\])/g, "\\$1");
  }

  function captureDynamicMonitorFocus() {
    const active = document.activeElement;
    if (!active || active === document.body || typeof active.closest !== "function") return null;
    const worker = active.closest("[data-run-monitor-worker-id]");
    if (worker) {
      return {
        kind: "worker",
        key: text(worker.getAttribute("data-run-monitor-worker-id")),
        jobId: text(worker.getAttribute("data-run-monitor-job-id")),
      };
    }
    const terminal = active.closest("[data-run-monitor-terminal-key]");
    if (terminal) {
      return {
        kind: "terminal",
        key: text(terminal.getAttribute("data-run-monitor-terminal-key")),
        jobId: state.selectedJobId,
      };
    }
    const lastKnownItem = active.closest("[data-last-known-job-id]");
    if (lastKnownItem) {
      return {
        kind: "last-known-item",
        key: text(lastKnownItem.getAttribute("data-last-known-job-id")),
        jobId: text(lastKnownItem.getAttribute("data-last-known-job-id")),
      };
    }
    return null;
  }

  function restoreDynamicMonitorFocus(context) {
    const record = object(context);
    if (!text(record.kind) || !text(record.key)) return;
    window.setTimeout(() => {
      const active = document.activeElement;
      if (active && active !== document.body && active !== document.documentElement && active.isConnected) return;
      const attribute = record.kind === "worker"
        ? "data-run-monitor-worker-id"
        : record.kind === "last-known-item"
          ? "data-last-known-job-id"
          : "data-run-monitor-terminal-key";
      const exact = document.querySelector(`[${attribute}="${cssEscape(record.key)}"]`);
      const fileButton = text(record.jobId)
        ? byId("run-monitor-items")?.querySelector(`[data-run-monitor-job-id="${cssEscape(record.jobId)}"]`)
        : null;
      const fallback = record.kind === "terminal" ? byId("run-monitor-detail") : fileButton || byId("run-monitor-detail");
      const target = exact || fallback;
      if (!target || typeof target.focus !== "function") return;
      target.scrollIntoView?.({ block: "nearest", inline: "nearest" });
      target.focus({ preventScroll: true });
    }, 0);
  }

  function handleItemKeydown(event) {
    if (!["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) return;
    const buttons = Array.from(byId("run-monitor-items")?.querySelectorAll(".run-monitor-item-button") || []);
    const index = buttons.indexOf(event.currentTarget);
    if (index < 0 || !buttons.length) return;
    let nextIndex = index;
    if (event.key === "ArrowDown") nextIndex = Math.min(buttons.length - 1, index + 1);
    if (event.key === "ArrowUp") nextIndex = Math.max(0, index - 1);
    if (event.key === "Home") nextIndex = 0;
    if (event.key === "End") nextIndex = buttons.length - 1;
    event.preventDefault();
    const next = buttons[nextIndex];
    selectJob(next.getAttribute("data-run-monitor-job-id") || "", { focusDetail: false, focusButton: true });
  }

  function selectJob(jobId, options = {}) {
    const normalized = text(jobId);
    if (!normalized || !array(state.payload?.items).some((item) => text(item.job_id) === normalized)) return false;
    state.selectedJobId = normalized;
    state.focusedJobId = normalized;
    if (options.focusButton) state.workloadExpanded = true;
    const freshnessState = text(state.payload?.freshness?.state, "unavailable");
    renderItems(state.payload, freshnessState);
    const selector = `[data-run-monitor-job-id="${cssEscape(normalized)}"]`;
    if (options.focusButton) {
      window.setTimeout(() => byId("run-monitor-items")?.querySelector(selector)?.focus({ preventScroll: true }), 0);
    }
    if (options.focusDetail) {
      window.setTimeout(() => byId("run-monitor-detail")?.focus({ preventScroll: false }), 0);
    }
    return true;
  }

  function appendRouteCard(container, route) {
    const card = document.createElement("div");
    card.className = "run-monitor-route-card";
    card.dataset.state = route.state;
    const title = document.createElement("strong");
    title.textContent = route.label;
    const value = document.createElement("span");
    value.textContent = route.value || routeUnavailableLabel(route);
    const reasonTitle = document.createElement("span");
    reasonTitle.className = "run-monitor-route-reason-label";
    reasonTitle.textContent = route.reasonLabel;
    const reason = document.createElement("span");
    const reasonText = route.reason || (route.value ? "No reason reported" : routeUnavailableLabel(route));
    reason.textContent = route.reasonCode ? `${reasonText} (${route.reasonCode})` : reasonText;
    const evidence = document.createElement("small");
    evidence.textContent = evidenceLabel(route.evidence);
    card.append(title, value, reasonTitle, reason, evidence);
    container.appendChild(card);
  }

  function renderRoutes(item, freshnessState) {
    const container = byId("run-monitor-routes");
    if (!container) return;
    container.replaceChildren();
    if (!itemEvidenceAllowed(item, freshnessState)) {
      const suppressed = document.createElement("p");
      suppressed.textContent = `Route claims are suppressed while freshness is ${humanize(freshnessState).toLowerCase()}. Use “Last known — not current” for clearly separated historical evidence.`;
      container.appendChild(suppressed);
      return;
    }
    appendRouteCard(container, routeDisplay(item?.planned_route, "Planned route", "Planned reason"));
    appendRouteCard(container, routeDisplay(item?.executed_route, "Executed route", "Executed reason"));
    appendRouteCard(container, routeDisplay(item?.final_route, "Final route", "Final reason"));
  }

  function renderStages(item, freshnessState) {
    const container = byId("run-monitor-stage-list");
    if (!container) return;
    container.replaceChildren();
    if (!itemEvidenceAllowed(item, freshnessState)) {
      const suppressed = document.createElement("li");
      suppressed.textContent = `Current timeline is suppressed while freshness is ${humanize(freshnessState).toLowerCase()}.`;
      container.appendChild(suppressed);
      return;
    }
    const stages = array(item?.stages);
    if (!stages.length) {
      const empty = document.createElement("li");
      empty.textContent = "No backend stage ledger loaded.";
      container.appendChild(empty);
      return;
    }
    stages.forEach((stage) => {
      const li = document.createElement("li");
      li.className = "run-monitor-stage";
      li.dataset.state = text(stage.state, "unknown");
      if (text(stage.state) === "active") li.setAttribute("aria-current", "step");
      const heading = document.createElement("div");
      heading.className = "run-monitor-stage-heading";
      const label = document.createElement("strong");
      label.textContent = stageLabel(stage.stage_id);
      const stageState = document.createElement("span");
      stageState.className = "run-monitor-stage-state";
      stageState.textContent = humanize(stage.state);
      heading.append(label, stageState);
      const detail = document.createElement("p");
      detail.textContent = text(stage.detail, text(stage.reason_code, "No additional backend detail."));
      const meta = document.createElement("small");
      const progress = progressLabel(stage.progress);
      meta.textContent = [
        progress,
        text(stage.started_at) ? `Started ${formatTimestamp(stage.started_at)}` : "",
        text(stage.updated_at) ? `Updated ${formatTimestamp(stage.updated_at)}` : "",
        text(stage.completed_at) ? `Completed ${formatTimestamp(stage.completed_at)}` : "",
        evidenceLabel(stage.evidence),
      ].filter(Boolean).join(" · ");
      li.append(heading, detail, meta);
      container.appendChild(li);
    });
  }

  function collectionEmptyText(kind, collection) {
    const collectionState = text(collection?.state, "unknown");
    if (collectionState === "not_applicable") return `No ${kind} tracks · Not applicable`;
    if (collectionState === "awaiting_evidence") return `Awaiting backend ${kind} evidence`;
    if (collectionState === "unknown") return `${humanize(kind)} evidence unknown`;
    return `No per-track ${kind} evidence reported`;
  }

  function appendEmptyTrackRow(body, message) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = 4;
    cell.dataset.label = "Track evidence";
    cell.textContent = message;
    row.appendChild(cell);
    body.appendChild(row);
  }

  function renderAudio(item, freshnessState) {
    const collection = object(item?.audio);
    const tracks = array(collection.tracks);
    const body = byId("run-monitor-audio-body");
    if (!body) return;
    if (!itemEvidenceAllowed(item, freshnessState)) {
      setText("run-monitor-audio-state", `Evidence suppressed · ${humanize(freshnessState)}`);
      body.replaceChildren();
      appendEmptyTrackRow(body, `Current audio-track claims are suppressed while freshness is ${humanize(freshnessState).toLowerCase()}.`);
      return;
    }
    setText("run-monitor-audio-state", collectionStateLabel(collection));
    body.replaceChildren();
    if (!tracks.length) {
      appendEmptyTrackRow(body, collectionEmptyText("audio", collection));
      return;
    }
    tracks.forEach((track) => {
      const row = document.createElement("tr");
      row.dataset.state = text(track.state, "unknown");
      const identity = document.createElement("td");
      identity.dataset.label = "Track";
      identity.textContent = [
        `Stream ${Number.isFinite(Number(track.stream_index)) ? track.stream_index : "unknown"}`,
        text(track.language, "language unknown"),
        text(track.track_id),
        track.is_default ? "default" : "",
      ].filter(Boolean).join(" · ");
      const source = document.createElement("td");
      source.dataset.label = "Source";
      source.textContent = [
        text(track.source_codec, "codec unknown"),
        Number(track.source_channels) > 0 ? `${track.source_channels} channels` : "channels unknown",
        text(track.source_layout),
      ].filter(Boolean).join(" · ");
      const planned = document.createElement("td");
      planned.dataset.label = "Planned action";
      planned.textContent = text(track.planned_action, "Not reported");
      const current = document.createElement("td");
      current.dataset.label = "Current / final evidence";
      current.textContent = [
        humanize(track.state),
        text(track.current_action),
        text(track.output_codec) ? `Output ${track.output_codec}` : "",
        Number(track.output_channels) > 0 ? `${track.output_channels} channels` : "",
        text(track.output_layout),
        progressLabel(track.progress),
        trackTimelineLabel(track),
        text(track.result),
        text(track.reason),
        evidenceLabel(track.evidence),
      ].filter(Boolean).join(" · ");
      row.append(identity, source, planned, current);
      body.appendChild(row);
    });
  }

  function subtitleActions(track) {
    const actions = [text(track.planned_action)];
    if (track.preserve === true) actions.push("Preserve original");
    if (track.extract === true) actions.push("Extract");
    if (track.convert === true) actions.push("Convert");
    if (track.ocr === true) actions.push("OCR");
    if (track.write_embedded === true) actions.push("Write embedded");
    if (track.write_sidecar === true) actions.push("Write external sidecar");
    return actions.filter(Boolean).join(" · ") || "Not reported";
  }

  function renderSubtitles(item, freshnessState) {
    const collection = object(item?.subtitles);
    const tracks = array(collection.tracks);
    const body = byId("run-monitor-subtitle-body");
    if (!body) return;
    if (!itemEvidenceAllowed(item, freshnessState)) {
      setText("run-monitor-subtitle-state", `Evidence suppressed · ${humanize(freshnessState)}`);
      body.replaceChildren();
      appendEmptyTrackRow(body, `Current subtitle-track claims are suppressed while freshness is ${humanize(freshnessState).toLowerCase()}.`);
      return;
    }
    setText("run-monitor-subtitle-state", collectionStateLabel(collection));
    body.replaceChildren();
    if (!tracks.length) {
      appendEmptyTrackRow(body, collectionEmptyText("subtitle", collection));
      return;
    }
    tracks.forEach((track) => {
      const row = document.createElement("tr");
      row.dataset.state = text(track.state, "unknown");
      const identity = document.createElement("td");
      identity.dataset.label = "Track";
      const index = track.stream_index === null || track.stream_index === undefined
        ? track.source_ordinal === null || track.source_ordinal === undefined ? "unknown" : `ordinal ${track.source_ordinal}`
        : `stream ${track.stream_index}`;
      identity.textContent = [index, text(track.language, "language unknown"), text(track.track_id)].join(" · ");
      const source = document.createElement("td");
      source.dataset.label = "Source";
      source.textContent = [text(track.source_codec, "codec unknown"), humanize(track.source_type), humanize(track.source_kind)].join(" · ");
      const planned = document.createElement("td");
      planned.dataset.label = "Planned action";
      planned.textContent = subtitleActions(track);
      const current = document.createElement("td");
      current.dataset.label = "Current / final evidence";
      current.textContent = [
        humanize(track.state),
        text(track.current_action),
        subtitleStepLabel(track),
        progressLabel(track.progress, track.progress_unit),
        subtitleCueLabel(track),
        trackTimelineLabel(track),
        text(track.output_codec) ? `Output ${track.output_codec}` : "",
        text(track.output_location) && track.output_location !== "unknown" ? humanize(track.output_location) : "",
        text(track.output_path),
        text(track.parked_path),
        text(track.intended_final_path),
        text(track.result),
        text(track.reason),
        evidenceLabel(track.evidence),
      ].filter(Boolean).join(" · ");
      row.append(identity, source, planned, current);
      body.appendChild(row);
    });
  }

  function appendFact(list, label, value) {
    const row = document.createElement("div");
    const term = document.createElement("dt");
    term.textContent = label;
    const detail = document.createElement("dd");
    detail.textContent = value || "Not reported";
    row.append(term, detail);
    list.appendChild(row);
  }

  function terminalLinkPage(reference, item) {
    const kind = text(reference?.kind);
    if (kind === "manifest") return text(item?.lifecycle_state) === "parked" ? "pending" : "completed";
    if (kind === "sidecar") {
      const lifecycleState = text(item?.lifecycle_state);
      if (lifecycleState === "parked") return "pending";
      if (["failed", "blocked", "review"].includes(lifecycleState)) return "reports";
      return "completed";
    }
    return TERMINAL_LINK_PAGES[kind] || "";
  }

  function terminalFocusKey(page, reference) {
    return [page, text(reference?.kind), text(reference?.reference), text(reference?.path)].join("\u241f");
  }

  function focusSelectorForPage(page) {
    return `[data-page-panel="${page}"] h1`;
  }

  const TERMINAL_PATH_FIELDS = Object.freeze({
    completed: ["manifest_path", "completed_manifest_path", "output_path", "source_json", "sidecar_path"],
    pending: ["manifest_path", "local_file", "server_out", "source_path", "parked_path", "intended_final_path"],
    reports: ["source_json", "artifact_path", "report_path", "source_path", "marker_path"],
  });

  function normalizedTerminalKey(value) {
    return text(value).toLocaleLowerCase();
  }

  function normalizedTerminalPath(value) {
    return text(value).replace(/\//g, "\\").toLocaleLowerCase();
  }

  function terminalDestinationAdapter(page) {
    if (page === "completed") {
      const view = window.mediaPipelineCompletedView || {};
      return {
        getRows: view.getLastCompletedRows,
        rowKey: (row) => text(row?.row_key),
        select: view.selectCompletedRow,
        detailSelector: "#completed-selected-summary",
        rowSelector: "#completed-rows tr[data-row-key]",
      };
    }
    if (page === "pending") {
      const view = window.mediaPipelinePendingPublishView || {};
      return {
        getRows: view.getLastPendingPublishRows,
        rowKey: typeof view.pendingRowKey === "function" ? view.pendingRowKey : (row) => text(row?.row_key),
        select: view.selectPendingRow,
        detailSelector: "#pending-selected-summary",
        rowSelector: "#pending-rows tr[data-row-key]",
      };
    }
    if (page === "reports") {
      const view = window.mediaPipelineReportsView || {};
      return {
        getRows: view.getLastFailureRows,
        rowKey: typeof view.failureRowKey === "function" ? view.failureRowKey : (row) => text(row?.row_key),
        select: view.selectFailureRow,
        detailSelector: "#failure-detail",
        rowSelector: "#failure-rows tr[data-row-key]",
      };
    }
    return null;
  }

  function terminalRowPathValues(page, row) {
    const values = array(TERMINAL_PATH_FIELDS[page]).map((field) => row?.[field]);
    if (page === "completed") {
      array(row?.sidecars).forEach((sidecar) => values.push(sidecar?.path));
      array(row?.sidecar_paths).forEach((path) => values.push(path));
    }
    return values.map(normalizedTerminalPath).filter(Boolean);
  }

  function terminalReferenceMatch(page, adapter, row, reference) {
    const stableReference = normalizedTerminalKey(reference?.reference);
    const artifactPath = normalizedTerminalPath(reference?.path);
    const stableRowKey = normalizedTerminalKey(adapter.rowKey(row));
    if (stableReference && stableRowKey && stableReference === stableRowKey) return "stable_row_key";
    if (artifactPath && terminalRowPathValues(page, row).includes(artifactPath)) return "artifact_path";
    return "";
  }

  function focusTerminalHeading(page) {
    const heading = document.querySelector(focusSelectorForPage(page));
    if (!heading || typeof heading.focus !== "function") return false;
    if (!heading.matches("button, a, input, select, textarea, [tabindex]")) heading.setAttribute("tabindex", "-1");
    heading.focus({ preventScroll: false });
    return document.activeElement === heading;
  }

  function terminalPageIsVisible(page) {
    return document.querySelector(`[data-page-panel="${page}"].is-visible`) !== null;
  }

  function clearTerminalHandoff() {
    if (state.terminalHandoffObserver) state.terminalHandoffObserver.disconnect();
    if (state.terminalHandoffApplyTimer !== null) window.clearTimeout(state.terminalHandoffApplyTimer);
    if (state.terminalHandoffExpiryTimer !== null) window.clearTimeout(state.terminalHandoffExpiryTimer);
    state.terminalHandoff = null;
    state.terminalHandoffObserver = null;
    state.terminalHandoffApplyTimer = null;
    state.terminalHandoffExpiryTimer = null;
    state.terminalHandoffApplying = false;
    state.terminalHandoffTarget = null;
  }

  function focusTerminalDestination(page, reference) {
    const adapter = terminalDestinationAdapter(page);
    if (!adapter || typeof adapter.getRows !== "function" || typeof adapter.select !== "function") return false;
    const rows = array(adapter.getRows());
    const match = rows.map((row) => ({ row, kind: terminalReferenceMatch(page, adapter, row, reference) }))
      .find((entry) => entry.kind);
    if (!match) return false;
    state.terminalHandoffApplying = true;
    adapter.select(match.row);
    const selectedKey = normalizedTerminalKey(adapter.rowKey(match.row));
    window.setTimeout(() => {
      const exactRow = Array.from(document.querySelectorAll(adapter.rowSelector))
        .find((row) => normalizedTerminalKey(row.dataset.rowKey) === selectedKey);
      const target = exactRow || document.querySelector(adapter.detailSelector);
      if (target && typeof target.focus === "function") {
        if (!target.matches("button, a, input, select, textarea, [tabindex]")) target.setAttribute("tabindex", "-1");
        target.dataset.terminalReferenceMatch = match.kind;
        target.focus({ preventScroll: false });
        // A detail panel is only a temporary landing while an asynchronous
        // destination render catches up. Only an exact row can satisfy the
        // handoff and suppress another correlated re-apply.
        state.terminalHandoffTarget = exactRow || null;
      }
      state.terminalHandoffApplying = false;
    }, 0);
    return true;
  }

  function applyTerminalHandoff() {
    const handoff = state.terminalHandoff;
    if (!handoff || state.terminalHandoffApplying) return false;
    if (!terminalPageIsVisible(handoff.page)) {
      clearTerminalHandoff();
      return false;
    }
    const matched = focusTerminalDestination(handoff.page, handoff.reference);
    if (!matched) {
      state.terminalHandoffTarget = null;
      focusTerminalHeading(handoff.page);
    }
    return matched;
  }

  function scheduleTerminalHandoffApply(delay = 0) {
    if (!state.terminalHandoff || state.terminalHandoffApplyTimer !== null) return;
    state.terminalHandoffApplyTimer = window.setTimeout(() => {
      state.terminalHandoffApplyTimer = null;
      applyTerminalHandoff();
    }, delay);
  }

  function beginTerminalHandoff(page, reference) {
    clearTerminalHandoff();
    state.terminalHandoff = { page, reference: { ...object(reference) } };
    const panel = document.querySelector(`[data-page-panel="${page}"]`);
    if (panel && typeof window.MutationObserver === "function") {
      state.terminalHandoffObserver = new window.MutationObserver(() => {
        if (state.terminalHandoffApplying) return;
        if (!terminalPageIsVisible(page)) {
          clearTerminalHandoff();
          return;
        }
        if (state.terminalHandoffTarget?.isConnected) return;
        scheduleTerminalHandoffApply();
      });
      state.terminalHandoffObserver.observe(panel, { childList: true, subtree: true });
    }
    state.terminalHandoffExpiryTimer = window.setTimeout(() => {
      if (state.terminalHandoff?.page !== page) return;
      if (terminalPageIsVisible(page) && !state.terminalHandoffTarget?.isConnected) focusTerminalHeading(page);
      clearTerminalHandoff();
    }, 30000);
  }

  function reapplyTerminalHandoff(page) {
    const handoff = state.terminalHandoff;
    if (!handoff || text(handoff.page) !== text(page)) return false;
    if (!terminalPageIsVisible(handoff.page)) {
      clearTerminalHandoff();
      return false;
    }
    if (state.terminalHandoffTarget?.isConnected) return true;
    applyTerminalHandoff();
    return true;
  }

  function navigateToTerminalReference(reference, item) {
    const page = terminalLinkPage(reference, item);
    if (!page) return;
    if (page === "reports") window.mediaPipelineReportsView?.activateReportsTab?.("failures");
    beginTerminalHandoff(page, reference);
    const navigation = window.mediaPipelineAppLifecycle || {};
    if (typeof navigation.navigateToPage === "function") {
      navigation.navigateToPage(page, { focusSelector: focusSelectorForPage(page), restoreFocus: false });
    } else {
      window.showPage?.(page);
      window.setTimeout(() => focusTerminalHeading(page), 0);
    }
    applyTerminalHandoff();
  }

  function renderOutput(item, freshnessState) {
    const output = object(item?.output);
    const list = byId("run-monitor-output");
    const sidecars = byId("run-monitor-sidecars");
    const recovery = byId("run-monitor-recovery");
    const links = byId("run-monitor-terminal-links");
    if (!itemEvidenceAllowed(item, freshnessState)) {
      if (list) {
        list.replaceChildren();
        appendFact(list, "Output evidence", `Suppressed while freshness is ${humanize(freshnessState).toLowerCase()}.`);
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
      return;
    }
    if (list) {
      list.replaceChildren();
      appendFact(list, "Output state", humanize(output.state));
      appendFact(list, "Verification", humanize(output.verification_state));
      const sizeBytes = output.size_bytes;
      appendFact(list, "Verified output size", typeof sizeBytes === "number" && Number.isFinite(sizeBytes) && sizeBytes >= 0 ? `${sizeBytes.toLocaleString()} bytes` : "Unknown");
      appendFact(list, "Scratch path", text(output.scratch_path, "Not reported"));
      appendFact(list, "Working output path", text(output.working_output_path, "Not reported"));
      appendFact(list, "Published path", text(output.published_path, "Not reported"));
      appendFact(list, "Parked path", text(output.parked_path, "Not reported"));
      appendFact(list, "Intended final destination", text(output.intended_final_path, "Not reported"));
      appendFact(list, "Output evidence", evidenceLabel(output.evidence));
    }
    if (sidecars) {
      sidecars.replaceChildren();
      const heading = document.createElement("h4");
      heading.textContent = "Sidecar results";
      sidecars.appendChild(heading);
      const rows = array(output.sidecars);
      if (!rows.length) {
        const empty = document.createElement("p");
        empty.textContent = "No backend sidecar result evidence reported.";
        sidecars.appendChild(empty);
      } else {
        const ul = document.createElement("ul");
        rows.forEach((sidecar) => {
          const li = document.createElement("li");
          li.dataset.state = text(sidecar.state, "unknown");
          li.textContent = [humanize(sidecar.kind), humanize(sidecar.state), text(sidecar.path), text(sidecar.reason), evidenceLabel(sidecar.evidence)].filter(Boolean).join(" · ");
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
      const detail = document.createElement("p");
      detail.textContent = [
        `Failure state: ${humanize(failure.state)}`,
        text(failure.reason),
        text(failure.reason_code) ? `Reason code: ${failure.reason_code}` : "",
        failure.retryable === true ? "Retryable: yes" : failure.retryable === false ? "Retryable: no" : "Retryability: unknown",
        `Owner: ${text(guidance.owner, "pipeline")}`,
        text(guidance.next_action, "No next action reported"),
        evidenceLabel(guidance.evidence),
      ].filter(Boolean).join(" · ");
      recovery.append(title, detail);
    }
    if (links) {
      links.replaceChildren();
      array(item?.terminal_references).forEach((reference) => {
        const page = terminalLinkPage(reference, item);
        if (!page) return;
        const button = document.createElement("button");
        button.type = "button";
        button.className = "secondary-button";
        button.dataset.runMonitorDeepLink = page;
        button.setAttribute("data-run-monitor-terminal-key", terminalFocusKey(page, reference));
        button.textContent = `Open ${page === "pending" ? "Pending Publish" : page === "completed" ? "Completed Output" : "Reports"} proof`;
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
      setText("run-monitor-source", "Select an accepted file to inspect backend evidence.");
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
    setText("run-monitor-source", [text(item.source_path), text(item.parent_context), `Job ID ${text(item.job_id)}`, `Source identity ${text(item.source_identity?.value, "unknown")} (${text(item.source_identity?.algorithm, "algorithm unknown")})`].filter(Boolean).join(" · "));
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

  function unavailableItem(item) {
    const record = object(item);
    if (TERMINAL_ITEM_STATES.has(text(record.lifecycle_state))) return record;
    return {
      ...record,
      lifecycle_state: "unknown",
      current_stage: null,
      current_progress: null,
      stages: [],
      audio: { state: "unknown", policy_final: false, tracks: [], evidence: object(record.audio?.evidence) },
      subtitles: { state: "unknown", policy_final: false, tracks: [], evidence: object(record.subtitles?.evidence) },
      output: {
        ...object(record.output),
        state: "unknown",
        scratch_path: "",
        working_output_path: "",
        published_path: "",
        parked_path: "",
        intended_final_path: "",
        size_bytes: null,
        verification_state: "unknown",
        sidecars: [],
      },
    };
  }

  function unavailablePayload(reasonCode, detail = "", previousPayload = state.payload) {
    const previous = object(previousPayload);
    const existingLastKnown = object(previous.last_known);
    const previousItems = array(previous.items);
    const historicalItems = array(existingLastKnown.items).length ? array(existingLastKnown.items) : previousItems;
    const historicalWorkers = array(existingLastKnown.current_workers).length
      ? array(existingLastKnown.current_workers)
      : array(previous.current_workers);
    const lastUpdated = text(existingLastKnown.updated_at, text(previous.freshness?.updated_at, text(previous.run?.updated_at)));
    const parsedUpdated = Date.parse(lastUpdated);
    const ageSeconds = Number.isFinite(parsedUpdated)
      ? Math.max(0, (Date.now() - parsedUpdated) / 1000)
      : Number.isFinite(Number(existingLastKnown.age_seconds))
        ? Number(existingLastKnown.age_seconds)
        : Number.isFinite(Number(previous.freshness?.age_seconds))
          ? Number(previous.freshness.age_seconds)
          : null;
    const previousRun = object(previous.run);
    const terminalRun = ["completed", "failed", "blocked", "review", "stopped", "force_stopped"].includes(text(previousRun.lifecycle_state));
    const run = text(previousRun.run_id)
      ? {
          ...previousRun,
          lifecycle_state: terminalRun ? text(previousRun.lifecycle_state) : "unknown",
          stop_after_current: terminalRun
            ? object(previousRun.stop_after_current)
            : { state: "unavailable", requested_at: "", evidence: null },
        }
      : null;
    return {
      schema_version: PROJECTION_SCHEMA,
      run,
      freshness: {
        state: "unavailable",
        reason_code: reasonCode,
        detail,
        updated_at: lastUpdated,
        age_seconds: ageSeconds,
        backend_state: "unavailable",
      },
      items: previousItems.map(unavailableItem),
      current_workers: [],
      last_known: historicalItems.length || historicalWorkers.length
        ? {
            label: "Last known — not current",
            updated_at: lastUpdated,
            age_seconds: ageSeconds,
            items: historicalItems,
            current_workers: historicalWorkers,
          }
        : null,
      compatibility: { legacy_current_work_used: false },
    };
  }

  function launchAcceptancePayload(identity) {
    return {
      schema_version: PROJECTION_SCHEMA,
      run: {
        run_id: identity.runId,
        mode: "once",
        scope: "backend_queue",
        display_mode: "Run Once · Backend Queue",
        accepted_queue: {
          schema_version: "queue_plan_fingerprint.v1",
          fingerprint: identity.fingerprint,
          accepted_count: null,
        },
        lifecycle_state: "starting",
        launch_acceptance_state: identity.acceptanceState,
        started_at: "",
        updated_at: "",
        ended_at: "",
        stop_after_current: { state: "unavailable", requested_at: "", evidence: null },
        counts: {},
        outcome: null,
        evidence: {
          source: "pipeline_start_response",
          provenance: "backend_launch_response",
          recorded_at: "",
        },
      },
      freshness: {
        state: "unknown",
        reason_code: identity.acceptanceState,
        detail: "The backend accepted the launch. Current Work is loading the durable run monitor before showing accepted files or current claims.",
        updated_at: "",
        age_seconds: null,
        backend_state: "launch_accepted",
      },
      items: [],
      current_workers: [],
      last_known: null,
      compatibility: { legacy_current_work_used: false },
    };
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

  function launchMonitorIdentity(result) {
    const payload = object(result);
    const data = object(payload.data);
    const monitor = object(data.run_monitor);
    return {
      schema: text(monitor.schema_version),
      runId: text(monitor.run_id, text(data.run_id)),
      route: text(monitor.route),
      acceptanceState: text(monitor.acceptance_state),
      fingerprint: text(monitor.expected_queue?.fingerprint, text(data.accepted_queue_fingerprint)),
    };
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

  function focusSelectedFile(options = {}) {
    const jobId = state.selectedJobId;
    if (!jobId) return false;
    if (options.detail !== true && !state.workloadExpanded) {
      state.workloadExpanded = true;
      renderItems(state.payload, text(state.payload?.freshness?.state, "unavailable"));
    }
    const button = byId("run-monitor-items")?.querySelector(`[data-run-monitor-job-id="${cssEscape(jobId)}"]`);
    const target = options.detail === true ? byId("run-monitor-detail") : button;
    if (!target || typeof target.focus !== "function") return false;
    target.scrollIntoView?.({ block: "center", inline: "nearest" });
    target.focus({ preventScroll: true });
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
