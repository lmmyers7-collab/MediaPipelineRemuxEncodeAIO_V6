(function () {
  function createProgressLiveRunModule(deps) {
    const { formatProgressValue, progressNumericValue, csvRerunCompletionSummary, csvRerunActivityEvidence, timelineLooksIdleWaiting, compactProgressUpdatedAt, progressWorkerRows, progressEtaRows, progressFfmpegPayload, activeWorkProgressLine, activeWorkRouteLine, activeWorkQueueLine, activeWorkControlLine, progressWorkerSummaryLine, progressFfmpegSummaryLine, progressEtaSummaryLine, formatEtaSeconds, formatWorkerProgressRow, byId, setText, setProgressPanelStatus } = deps;

  function progressLooksFinalizing(progress = {}) {
    const stage = String(progress?.CurrentStage || progress?.Status || "").trim().toLowerCase();
    const percent = progressNumericValue(progress?.CurrentStagePercent, NaN);
    const pushState = String(progress?.PushState || "").trim().toLowerCase();
    const sidecarState = String(progress?.SidecarState || "").trim().toLowerCase();
    if (!Number.isFinite(percent) || percent < 95 || percent >= 100) return false;
    if (["encode", "encode_cpu", "remux_av"].includes(stage)) return true;
    return Boolean(pushState || sidecarState);
  }

  function activeWorkFinalizingLine(progress) {
    if (!progressLooksFinalizing(progress)) return "";
    const stage = String(progress?.CurrentStage || "").trim().toLowerCase();
    if (["encode", "encode_cpu"].includes(stage)) return "Stage note: encoding is near completion; backend may still be verifying output, writing sidecars, publishing, or parking.";
    if (stage === "remux_av") return "Stage note: remux is near completion; backend may still be verifying output, writing sidecars, publishing, or parking.";
    return "Stage note: progress is near completion; wait for backend completion, parked-publish, or close-readiness evidence.";
  }

  function latestEventLine(diagnostics, snapshot) {
    const diagnosticEvents = Array.isArray(diagnostics?.recent_events) ? diagnostics.recent_events : [];
    if (diagnosticEvents.length) return `Latest diagnostic event: ${formatProgressValue(diagnosticEvents[0])}`;
    const snapshotEvents = Array.isArray(snapshot?.recent_events) ? snapshot.recent_events : [];
    if (!snapshotEvents.length) return "";
    const event = snapshotEvents[snapshotEvents.length - 1];
    return `Latest pipeline event: ${formatProgressValue(event?.event_type || event?.type || event)}`;
  }

  function liveRunStatus({ snapshot = null, diagnostics = null, closeReadiness = null, stdoutTail = null } = {}) {
    const completion = csvRerunCompletionSummary(snapshot);
    if (completion) {
      return {
        label: String(completion.display_label || "CSV rerun complete"),
        state: String(completion.display_state || "ok"),
      };
    }
    const activity = String(snapshot?.activity || snapshot?.current_activity || "").toLowerCase();
    const state = String(snapshot?.pipeline_state || closeReadiness?.state || "").toLowerCase();
    const currentWork = snapshot?.current_work && typeof snapshot.current_work === "object" ? snapshot.current_work : {};
    const activeWorkSummary = String(currentWork.summary_label || currentWork.latest_evidence_label || currentWork.current_stage_label || "").trim();
    const csvRerun = csvRerunActivityEvidence({ snapshot, diagnostics, closeReadiness, stdoutTail });
    if (activity.includes("stale progress") && closeReadiness?.safe_to_close === true) return { label: "Idle", state: "ok" };
    if (activeWorkSummary && !activeWorkSummary.toLowerCase().includes("csv") && !timelineLooksIdleWaiting(activeWorkSummary)) {
      return { label: "Active work", state: "running" };
    }
    if (csvRerun.isActive) return { label: "CSV rerun active", state: "running" };
    if (closeReadiness?.safe_to_close === false || ["processing", "running", "active", "publishing"].includes(state)) {
      return { label: "Active work", state: "running" };
    }
    if (closeReadiness?.safe_to_close === true) return { label: "Idle", state: "ok" };
    return { label: "Checking", state: "unknown" };
  }

  function compactUpdatedAgeText(value) {
    const updated = compactProgressUpdatedAt(value);
    return updated?.text || "";
  }

  function liveRunItem(label, value, hint = "", status = "") {
    return {
      label,
      value: String(value || "").trim() || "Not loaded",
      hint: String(hint || "").trim(),
      status: status || "unknown",
    };
  }

  function longRunReliabilityPayload(snapshot = null) {
    const counts = snapshot?.counts && typeof snapshot.counts === "object" ? snapshot.counts : {};
    return counts.long_run_reliability && typeof counts.long_run_reliability === "object" ? counts.long_run_reliability : {};
  }

  function longRunReliabilitySummary(snapshot = null) {
    const payload = longRunReliabilityPayload(snapshot);
    if (!Object.keys(payload).length) return "";
    const continuous = payload.continuous_round_state || {};
    const pending = payload.pending_publish_backpressure || {};
    const workers = payload.worker_slots || {};
    const stateDb = payload.state_db || {};
    return [
      `round_blocked=${Boolean(continuous.blocked)}`,
      `round_failures=${Number(continuous.consecutive_unexpected_round_failures || 0)}`,
      `pending_blocked=${Boolean(pending.blocked)}`,
      `pending_manifests=${Number(pending.manifest_count || 0)}`,
      `stale_workers=${Number(workers.stale_heartbeat_count || 0)}`,
      `wal_bytes=${Number(stateDb.wal_size_bytes || 0)}`,
    ].join("; ");
  }

  function longRunReliabilityStatus(snapshot = null) {
    const payload = longRunReliabilityPayload(snapshot);
    const continuous = payload.continuous_round_state || {};
    const pending = payload.pending_publish_backpressure || {};
    const workers = payload.worker_slots || {};
    if (continuous.blocked || pending.blocked || Number(workers.stale_heartbeat_count || 0) > 0) return "blocked";
    if (Number(continuous.consecutive_unexpected_round_failures || 0) > 0 || Number(payload?.state_db?.wal_size_bytes || 0) >= Number(payload?.state_db?.wal_review_bytes || 0)) return "warning";
    return Object.keys(payload).length ? "ok" : "unknown";
  }

  function liveRunStripItems({ snapshot = null, diagnostics = null, closeReadiness = null, stdoutTail = null } = {}) {
    const completion = csvRerunCompletionSummary(snapshot);
    if (completion) {
      const totals = completion.totals && typeof completion.totals === "object" ? completion.totals : {};
      const state = String(completion.display_state || "ok");
      return [
        liveRunItem("CSV rerun", completion.display_label || "CSV rerun complete", completion.detail || "Backend manifest terminal state.", state),
        liveRunItem("CSV", completion.csv_name || completion.batch_id || "Current CSV", "Backend-owned CSV rerun identity.", "ok"),
        liveRunItem("Processed", `${totals.processed || 0} / ${totals.total || 0}`, "Backend-owned terminal row count.", state),
        liveRunItem("Completed", totals.completed || 0, "Completed or returned rows.", "ok"),
        liveRunItem("Failed", totals.failed || 0, "Failed rows remain available for review.", totals.failed ? "warning" : "ok"),
        liveRunItem("Skipped / held", `${totals.skipped || 0} / ${totals.held || 0}`, "Skipped and review-held rows.", totals.held ? "warning" : "ok"),
        liveRunItem("Pending", totals.pending || 0, "Rows not terminal at the manifest boundary.", totals.pending ? "warning" : "ok"),
        liveRunItem("Pending publish", totals.pending_publish || 0, "Outputs parked for manifest-backed publish drain.", totals.pending_publish ? "warning" : "ok"),
        liveRunItem("Evidence", completion.historical_evidence_note || "Historical progress evidence is available for review.", "This terminal summary is backend manifest evidence.", "ok"),
      ];
    }
    const progress = snapshot?.progress && typeof snapshot.progress === "object" ? snapshot.progress : {};
    const currentWork = snapshot?.current_work && typeof snapshot.current_work === "object" ? snapshot.current_work : {};
    const workerRows = progressWorkerRows(snapshot, diagnostics);
    const etaRows = progressEtaRows(snapshot, diagnostics);
    const ffmpegPayload = progressFfmpegPayload(snapshot, diagnostics);
    const csvRerun = csvRerunActivityEvidence({ snapshot, diagnostics, stdoutTail });
    const state = snapshot?.pipeline_state || closeReadiness?.state || progress.Status || "unknown";
    const rawStage = currentWork.current_stage_label || currentWork.phase_label || progress.CurrentStage || progress.Status || "No active work";
    const normalizedStage = String(rawStage || "").trim().toLowerCase();
    const stage = ["encode_verify", "remux_verify"].includes(normalizedStage) ? "Verification" : rawStage;
    const percent = currentWork.percent_label || (progress.CurrentStagePercent !== undefined && progress.CurrentStagePercent !== null && progress.CurrentStagePercent !== "" ? `${formatProgressValue(progress.CurrentStagePercent)}%` : "");
    const file = currentWork.item_label || progress.CurrentFileDisplay || progress.CurrentFile || progress.InputFile || "";
    const route = currentWork.route_label || progress.CurrentRoute || progress.Route || "";
    const queue = currentWork.queue_position_label || activeWorkQueueLine(progress).replace(/^Queue position:\s*/i, "");
    const updated = compactUpdatedAgeText(progress.LastUpdate || progress.UpdatedAt || progress.updated_at);
    const eta = etaRows.find((row) => row && row.eta_seconds !== undefined && row.eta_seconds !== null);
    const activeWorker = workerRows.find((row) => ["running", "active", "warning"].includes(String(row.status_state || row.status || "").toLowerCase())) || workerRows[0];
    const reliabilitySummary = longRunReliabilitySummary(snapshot);
    const reliabilityStatus = longRunReliabilityStatus(snapshot);
    const nowValue = currentWork.summary_label || currentWork.latest_evidence_label || stage || "No active work";
    const nowHint = [
      file ? `Current item: ${file}` : "",
      currentWork.latest_event_label ? `Latest event: ${currentWork.latest_event_label}` : "",
      currentWork.next_stage_label ? `Next: ${currentWork.next_stage_label}` : "",
      currentWork.missing_evidence_label || "",
    ].filter(Boolean).join(" | ");
    const nowItem = liveRunItem("Now", nowValue, nowHint, currentWork.evidence_status === "waiting" ? "warning" : "running");
    const items = [
      liveRunItem("Stage", [formatProgressValue(stage), percent].filter(Boolean).join(" "), activeWorkFinalizingLine(progress), progressLooksFinalizing(progress) ? "warning" : "running"),
      liveRunItem("File", file || "No current file", file ? "Current backend-reported item." : "No current file evidence loaded.", file ? "running" : "empty"),
      liveRunItem("Route", route ? formatProgressValue(route) : "No route", progress.RouteReason || progress.CurrentRouteReason || "Backend route evidence only.", route ? "ok" : "empty"),
      liveRunItem("Queue", queue || "No queue position", "Display filters do not define Launch scope.", queue ? "ok" : "empty"),
      liveRunItem("ETA", eta ? formatEtaSeconds(eta.eta_seconds) : "Unavailable", eta?.basis || progressEtaSummaryLine(snapshot, diagnostics), eta ? "ok" : "warning"),
      liveRunItem("Last update", updated || "Not loaded", updated ? "Runtime progress update age." : "No runtime progress timestamp loaded.", updated ? "ok" : "unknown"),
      liveRunItem("FFmpeg", ffmpegPayload?.status || "idle", progressFfmpegSummaryLine(snapshot, diagnostics), ffmpegPayload?.status === "unavailable" ? "warning" : "ok"),
      liveRunItem("Worker", activeWorker ? formatWorkerProgressRow(activeWorker) : "No active worker", progressWorkerSummaryLine(snapshot, diagnostics), activeWorker ? "running" : "empty"),
      liveRunItem("Reliability", reliabilityStatus === "ok" ? "Ready" : reliabilityStatus === "blocked" ? "Blocked" : reliabilityStatus === "warning" ? "Review" : "Unknown", reliabilitySummary || "Long-run reliability counters are backend-owned and read-only.", reliabilityStatus),
      liveRunItem("Close", closeReadiness ? (closeReadiness.safe_to_close ? "Safe" : "Not safe") : "Unknown", closeReadiness?.reason || "Close-readiness is backend-owned.", closeReadiness?.safe_to_close ? "ok" : closeReadiness?.safe_to_close === false ? "blocked" : "unknown"),
    ];
    if (csvRerun.isActive) {
      items.unshift(
        liveRunItem("CSV rows", csvRerun.plannedRows || "CSV rerun active", "From the bounded last stdout log.", csvRerun.plannedRows ? "ok" : "running"),
        liveRunItem(
          "Importing",
          csvRerun.currentImport || currentWork.latest_evidence_label || currentWork.missing_evidence_label || "Waiting for backend evidence",
          csvRerun.currentImport ? "Current CSV staging/import line." : "Backend active-work evidence replaces missing CSV import text.",
          csvRerun.currentImport || currentWork.latest_evidence_label ? "running" : "warning"
        ),
        liveRunItem("Last imported", csvRerun.lastImported || "No staged copy yet", "Most recent completed stage copy in the stdout tail.", csvRerun.lastImported ? "ok" : "empty"),
        liveRunItem("Processing", csvRerun.processing || "Waiting for processing evidence", "Processing starts after CSV staging/import completes.", csvRerun.processing && !csvRerun.processing.startsWith("Not processing yet") ? "running" : "warning"),
      );
    }
    items.unshift(nowItem);
    const status = liveRunStatus({ snapshot, diagnostics, closeReadiness, stdoutTail });
    if (status.state === "warning") {
      items.unshift(liveRunItem("Review", "Stale progress", "No update from runtime progress. Inspect Diagnostics, ActiveJobs, Run Logs, and Last Stderr before stopping or closing.", "warning"));
    }
    return items;
  }

  const liveRunStripTargets = [
    { statusId: "home-live-run-status", bodyId: "home-live-run-strip" },
    { statusId: "launch-live-run-status", bodyId: "launch-live-run-strip" },
    { statusId: "pending-live-run-status", bodyId: "pending-live-run-strip" },
    { statusId: "diagnostics-live-run-status", bodyId: "diagnostics-live-run-strip" },
  ];

  const liveRunQuickLinks = {
    stage: { page: "home", focus: "#run-monitor-detail", label: "Open Current Work stage evidence" },
    file: { page: "home", focus: "#run-monitor-detail", label: "Open Current Work file evidence" },
    eta: { page: "home", focus: "#run-monitor-detail", label: "Open Current Work progress evidence" },
    "last update": { page: "home", focus: "#current-work-heading", label: "Open Current Work freshness evidence" },
    state: { page: "home", focus: "#current-work-heading", label: "Open Current Work run state" },
    route: { page: "home", focus: "#run-monitor-detail", label: "Open Current Work executed-route evidence" },
    queue: { page: "queue", label: "Open Queue" },
    ffmpeg: { page: "diagnostics", diagTab: "logs", label: "Open Diagnostics logs" },
    worker: { page: "home", focus: "#run-monitor-workers", label: "Open Current Work active workers" },
    reliability: { page: "diagnostics", diagTab: "triage", label: "Open Diagnostics reliability evidence" },
    close: { page: "diagnostics", diagTab: "readiness", label: "Open Diagnostics readiness" },
  };

  const homeLiveRunSummaryLabels = ["Review", "Now", "Stage", "Processing", "CSV rows", "File"];
  const homeLiveRunFileLabels = ["File", "Processing", "Importing", "Last imported"];
  const homeLiveRunDefaultFacts = ["Route", "Queue", "ETA", "Last update", "Close"];
  const homeLiveRunCsvFacts = ["CSV rows", "Queue", "ETA", "Last update", "Close"];
  const homeLiveRunFallbackFacts = ["Processing", "Route", "FFmpeg", "Worker", "Reliability"];

  function liveRunQuickLink(item) {
    return liveRunQuickLinks[String(item?.label || "").trim().toLowerCase()] || null;
  }

  function createLiveRunChipNode(item, { compact = false } = {}) {
    const quickLink = liveRunQuickLink(item);
    const node = document.createElement("span");
    node.className = compact ? "live-run-chip live-run-chip-compact" : "live-run-chip";
    node.dataset.status = item.status;
    if (quickLink) {
      node.setAttribute("role", "button");
      node.setAttribute("tabindex", "0");
      node.dataset.uiQuickLink = "";
      node.dataset.quickLinkPage = quickLink.page;
      if (quickLink.focus) node.dataset.quickLinkFocus = quickLink.focus;
      if (quickLink.diagTab) node.dataset.quickLinkDiagTab = quickLink.diagTab;
      const ariaLabel = `${quickLink.label}: ${item.label} ${item.value}`.trim();
      node.setAttribute("aria-label", ariaLabel);
      node.title = ariaLabel;
    }
    const label = document.createElement("span");
    label.className = "live-run-chip-label";
    label.textContent = item.label;
    const value = document.createElement("strong");
    value.className = "live-run-chip-value";
    value.textContent = item.value;
    node.append(label, value);
    if (item.hint) {
      const hint = document.createElement("span");
      hint.className = "live-run-chip-hint";
      hint.textContent = item.hint;
      if (!quickLink) node.title = item.hint;
      node.appendChild(hint);
    }
    return node;
  }

  function findLiveRunItem(items, labels) {
    const wanted = new Set(labels.map((label) => String(label).toLowerCase()));
    return items.find((item) => wanted.has(String(item?.label || "").toLowerCase())) || null;
  }

  function progressPercentFromText(value) {
    const match = String(value || "").match(/(\d+(?:\.\d+)?)\s*%/);
    if (!match) return null;
    const number = Number(match[1]);
    return Number.isFinite(number) ? Math.max(0, Math.min(100, number)) : null;
  }

  function homeLiveRunFactItems(items) {
    const hasCsv = items.some((item) => item.label === "CSV rows");
    const preferred = hasCsv ? homeLiveRunCsvFacts : homeLiveRunDefaultFacts;
    const selected = [];
    const addByLabel = (label) => {
      const item = findLiveRunItem(items, [label]);
      if (item && !selected.includes(item)) selected.push(item);
    };
    preferred.forEach(addByLabel);
    homeLiveRunFallbackFacts.forEach((label) => {
      if (selected.length < 5) addByLabel(label);
    });
    return selected.slice(0, 5);
  }

  function renderHomeLiveRunMonitor(body, status, items) {
    body.classList.add("live-run-monitor");
    const summaryItem = findLiveRunItem(items, homeLiveRunSummaryLabels) || items[0] || liveRunItem("State", status.label, "", status.state);
    const fileItem = findLiveRunItem(items, homeLiveRunFileLabels);
    const factItems = homeLiveRunFactItems(items);
    const percent = progressPercentFromText(summaryItem.value) ?? progressPercentFromText(findLiveRunItem(items, ["Processing"])?.value);

    const summary = document.createElement("section");
    summary.className = "live-run-monitor-summary";
    summary.dataset.state = status.state;
    summary.dataset.status = summaryItem.status || status.state || "unknown";

    const eyebrow = document.createElement("div");
    eyebrow.className = "live-run-monitor-eyebrow";
    const label = document.createElement("span");
    label.textContent = "Now";
    const state = document.createElement("strong");
    state.className = "live-run-monitor-state";
    state.dataset.state = status.state;
    state.textContent = status.label;
    eyebrow.append(label, state);

    const title = document.createElement("strong");
    title.className = "live-run-monitor-title";
    title.textContent = summaryItem.value;

    const subtitle = document.createElement("span");
    subtitle.className = "live-run-monitor-subtitle";
    subtitle.textContent = fileItem && fileItem !== summaryItem
      ? `${fileItem.label}: ${fileItem.value}`
      : summaryItem.hint || "Backend live-run state loaded.";

    summary.append(eyebrow, title, subtitle);
    if (percent !== null) {
      const meter = document.createElement("div");
      meter.className = "live-run-monitor-meter";
      meter.setAttribute("role", "progressbar");
      meter.setAttribute("aria-label", `${summaryItem.label} progress`);
      meter.setAttribute("aria-valuemin", "0");
      meter.setAttribute("aria-valuemax", "100");
      meter.setAttribute("aria-valuenow", String(Math.round(percent)));
      const fill = document.createElement("span");
      fill.style.width = `${percent}%`;
      meter.appendChild(fill);
      summary.appendChild(meter);
    }

    const facts = document.createElement("div");
    facts.className = "live-run-monitor-facts";
    factItems.forEach((item) => facts.appendChild(createLiveRunChipNode(item, { compact: true })));

    const details = document.createElement("details");
    details.className = "live-run-monitor-details";
    const detailsSummary = document.createElement("summary");
    detailsSummary.textContent = `Evidence details (${items.length})`;
    const detailGrid = document.createElement("div");
    detailGrid.className = "live-run-monitor-detail-grid";
    items.forEach((item) => detailGrid.appendChild(createLiveRunChipNode(item, { compact: true })));
    details.append(detailsSummary, detailGrid);

    body.replaceChildren(summary, facts, details);
  }

  function liveRunHandoffLines(context = {}, status = liveRunStatus(context), items = liveRunStripItems(context)) {
    const completion = csvRerunCompletionSummary(context?.snapshot);
    if (completion) {
      return [
        `Run state: ${status.label}.`,
        `CSV: ${completion.csv_name || completion.batch_id || "current CSV"}.`,
        `Summary: ${completion.detail || "Backend manifest reports a terminal CSV rerun state."}`,
        completion.historical_evidence_note || "Historical progress evidence is available for review.",
        "Safe next step: open Queue for row evidence, Pending Publish for parked outputs, or Reports for failures as indicated by the terminal totals.",
        "Mutation guardrail: this handoff is read-only and cannot start, stop, drain, publish, rename, or touch media.",
      ];
    }
    const active = status.state === "running";
    const review = status.state === "warning";
    const stage = items.find((item) => item.label === "Stage")?.value || "No stage";
    const file = items.find((item) => item.label === "File")?.value || "No current file";
    const close = items.find((item) => item.label === "Close")?.value || "Unknown";
    const csvRerun = csvRerunActivityEvidence(context);
    const next = review
      ? "Open Diagnostics, Active Jobs, Run Logs, and Last Stderr before stopping or closing."
      : active
        ? "Monitor Run Progress and wait for close-readiness to report safe before closing."
        : "No active work is reported; refresh before starting a long unattended operation.";
    const csvLines = csvRerun.isActive ? [
      `CSV rerun: ${csvRerun.plannedRows || "active"}.`,
      `Importing: ${csvRerun.currentImport || "no active copy line in stdout tail"}.`,
      `Last imported: ${csvRerun.lastImported || "none in stdout tail"}.`,
      `Processing: ${csvRerun.processing || "waiting for processing evidence"}.`,
      `Latest stdout: ${csvRerun.latestLine || "none"}.`,
    ] : [];
    return [
      `Run state: ${status.label}; stage=${stage}; file=${file}; close=${close}.`,
      ...csvLines,
      `Safe next step: ${next}`,
      "Mutation guardrail: this handoff is read-only and cannot start, stop, drain, publish, rename, or touch media.",
    ];
  }

  function renderLiveRunStrip(context = {}, targets = liveRunStripTargets) {
    const status = liveRunStatus(context);
    const items = liveRunStripItems(context);
    targets.forEach((target) => {
      const statusNode = byId(target.statusId);
      if (statusNode) {
        statusNode.textContent = status.label;
        statusNode.dataset.state = status.state;
      }
      const body = byId(target.bodyId);
      if (!body) return;
      body.classList.toggle("live-run-monitor", target.bodyId === "home-live-run-strip");
      if (target.bodyId === "home-live-run-strip") {
        renderHomeLiveRunMonitor(body, status, items);
        return;
      }
      body.replaceChildren();
      items.forEach((item) => body.appendChild(createLiveRunChipNode(item)));
    });
    setText("home-run-state-handoff", liveRunHandoffLines(context, status, items).join("\n"));
  }

  function activeWorkNextStep({ activeJobs, closeReadiness, state }) {
    if (activeJobs.length || closeReadiness?.safe_to_close === false) {
      return "Inspect Progress Details, Diagnostics > ActiveJobs, and Run Logs before closing or starting more work.";
    }
    const normalized = String(state || "").toLowerCase();
    if (["processing", "running", "active", "publishing"].includes(normalized)) {
      return "Monitor Progress Details and wait for close-readiness to report safe before exiting.";
    }
    return "No active work indicators are currently reported.";
  }

  function renderHomeActiveWork({ snapshot = null, diagnostics = null, closeReadiness = null, stdoutTail = null } = {}) {
    const completion = csvRerunCompletionSummary(snapshot);
    if (completion) {
      const state = String(completion.display_state || "ok");
      setProgressPanelStatus("home-active-work-status", completion.display_label || "CSV rerun complete", state);
      setText(
        "home-active-work-summary",
        [
          `CSV rerun: ${completion.display_label || "complete"}`,
          `CSV: ${completion.csv_name || completion.batch_id || "current CSV"}`,
          completion.detail || "Backend manifest reports a terminal CSV rerun state.",
          completion.historical_evidence_note || "Historical progress evidence is available for review.",
        ].join("\n"),
      );
      return;
    }
    const activeJobs = Array.isArray(diagnostics?.active_jobs) ? diagnostics.active_jobs.filter(Boolean) : [];
    const workerRows = progressWorkerRows(snapshot, diagnostics);
    const progress = snapshot?.progress && typeof snapshot.progress === "object" ? snapshot.progress : {};
    const currentWork = snapshot?.current_work && typeof snapshot.current_work === "object" ? snapshot.current_work : {};
    const auditProgress = snapshot?.audit_progress && typeof snapshot.audit_progress === "object" ? snapshot.audit_progress : {};
    const state = snapshot?.pipeline_state || closeReadiness?.state || "unknown";
    const csvRerun = csvRerunActivityEvidence({ snapshot, diagnostics, stdoutTail });
    const stateActive = ["processing", "running", "active", "publishing"].includes(String(state || "").toLowerCase());
    const currentWorkSummary = String(currentWork.summary_label || currentWork.latest_evidence_label || "").trim();
    const currentWorkActive = Boolean(currentWorkSummary) && !timelineLooksIdleWaiting(currentWorkSummary);
    const active = activeJobs.length > 0 || closeReadiness?.safe_to_close === false || stateActive || csvRerun.isActive || currentWorkActive;
    setProgressPanelStatus("home-active-work-status", active ? "Active work" : closeReadiness?.safe_to_close === true ? "Idle" : "Checking", active ? "running" : closeReadiness?.safe_to_close === true ? "ok" : "loading");
    const lines = [
      currentWork.summary_label ? `Now: ${currentWork.summary_label}` : "",
      currentWork.item_label ? `Current item: ${currentWork.item_label}` : "",
      currentWork.current_stage_label ? `Current stage: ${currentWork.current_stage_label}` : "",
      currentWork.latest_evidence_label ? `Latest evidence: ${currentWork.latest_evidence_label}` : "",
      currentWork.latest_event_label ? `Latest event: ${currentWork.latest_event_label}` : "",
      currentWork.missing_evidence_label ? `Missing evidence: ${currentWork.missing_evidence_label}` : "",
      currentWork.next_stage_label ? `Next stage: ${currentWork.next_stage_label}` : "",
      `Pipeline state: ${state}`,
      `Close readiness: ${closeReadiness ? (closeReadiness.safe_to_close ? "safe" : "active work") : "unknown"}`,
      closeReadiness?.reason ? `Close reason: ${closeReadiness.reason}` : "",
      `ActiveJobs: ${activeJobs.length || 0}`,
      progressWorkerSummaryLine(snapshot, diagnostics),
      progressEtaSummaryLine(snapshot, diagnostics),
      longRunReliabilitySummary(snapshot) ? `Long-run reliability: ${longRunReliabilitySummary(snapshot)}` : "",
      csvRerun.isActive ? `CSV rerun: ${csvRerun.plannedRows || "active"}` : "",
      csvRerun.currentImport ? `Importing: ${csvRerun.currentImport}` : "",
      csvRerun.lastImported ? `Last imported: ${csvRerun.lastImported}` : "",
      csvRerun.processing ? `Processing: ${csvRerun.processing}` : "",
      csvRerun.latestLine ? `Latest stdout: ${csvRerun.latestLine}` : "",
      ...workerRows.slice(0, 4).map((row) => `- ${formatWorkerProgressRow(row)}`),
      ...activeJobs.slice(0, 5).map((item) => `- ${item}`),
      activeJobs.length > 5 ? `- and ${activeJobs.length - 5} more ActiveJobs row(s)` : "",
      activeWorkProgressLine(progress),
      activeWorkRouteLine(progress),
      activeWorkQueueLine(progress),
      activeWorkControlLine(progress),
      activeWorkFinalizingLine(progress),
      auditProgress.status || auditProgress.Status ? `Audit: ${formatProgressValue(auditProgress.status || auditProgress.Status)}` : "",
      latestEventLine(diagnostics, snapshot),
      "",
      `Next step: ${currentWork.next_stage_label || activeWorkNextStep({ activeJobs, closeReadiness, state })}`,
    ].filter((line) => line !== "");
    setText("home-active-work-summary", lines.join("\n"));
  }

    return { latestEventLine, liveRunStatus, liveRunStripItems, renderLiveRunStrip, activeWorkNextStep, renderHomeActiveWork };
  }

  window.__progressLiveRunModule = { createProgressLiveRunModule };
}());
