/* global byId, setText, setTextState, homeProgressPercent, lastCloseReadiness, lastSnapshot, lastStartupProgress, lastTauriBackendLifecycleEvent */
(function () {
  function createAppLifecycleTopbar() {  const TOPBAR_PENDING_LAUNCH_TTL_MS = 120000;
  const TOPBAR_IDLE_PENDING_GRACE_MS = 45000;
  const COMPLETED_TAB_STORAGE_KEY = "mediapipeline-completed-tab";
  const formatters = window.mediaPipelineFormatters || {};
  const formatProgressValue = typeof formatters.formatProgressValue === "function"
    ? formatters.formatProgressValue
    : (value) => {
        if (value === null || value === undefined) return "";
        if (Array.isArray(value)) return value.join(", ");
        if (value && typeof value === "object") return JSON.stringify(value);
        return String(value);
      };
  const scheduleView = window.mediaPipelineScheduleView || {};
  const scheduleDisplayValue = typeof scheduleView.scheduleDisplayValue === "function" ? scheduleView.scheduleDisplayValue : null;
  let topbarPendingLaunch = null;

  function topbarPathLeaf(value) {
    const text = formatProgressValue(value || "").trim();
    if (!text) return "";
    return text.split(/[\\/]/).filter(Boolean).pop() || text;
  }

  function topbarCleanCurrentName(progress = {}, currentWork = {}) {
    return formatProgressValue(
      currentWork.item_label
        || progress.CurrentDisplayName
        || progress.CleanDisplayName
        || progress.CleanedName
        || progress.CurrentFileDisplay
        || "",
    ).trim();
  }

  function topbarStageContext(progress = {}) {
    const stage = formatProgressValue(progress.CurrentStage || progress.Status || "").trim();
    const percent = homeProgressPercent(progress.CurrentStagePercent);
    const route = formatProgressValue(progress.CurrentRoute || progress.Route || "").trim();
    return [
      stage,
      percent,
      route ? `Route ${route}` : "",
    ].filter(Boolean).join(" · ");
  }

  function topbarCurrentWorkMeta(currentWork = {}, progress = {}) {
    const item = formatProgressValue(currentWork.item_label || "").trim();
    const library = formatProgressValue(currentWork.library_label || "").trim();
    const queue = formatProgressValue(currentWork.queue_label || "").trim();
    const queuePosition = formatProgressValue(currentWork.queue_position_label || "").trim();
    const route = formatProgressValue(currentWork.route_label || "").trim();
    const percent = formatProgressValue(currentWork.percent_label || "").trim() || homeProgressPercent(progress.CurrentStagePercent);
    const next = formatProgressValue(currentWork.next_stage_label || "").trim();
    const missing = formatProgressValue(currentWork.missing_evidence_label || "").trim();
    const parts = [];
    if (item) parts.push(item);
    if (library) parts.push(library);
    if (queue && queue.toLowerCase() !== library.toLowerCase()) parts.push(queue);
    if (queuePosition) parts.push(queuePosition);
    if (route) parts.push(route);
    if (percent) parts.push(percent);
    if (next) parts.push(`Next: ${next}`);
    if (missing) parts.push(missing);
    return parts.join(" · ");
  }

  function renderTopbarActivity(snapshot = {}) {
    const node = byId("activity");
    if (!node) return;
    const payload = snapshot && typeof snapshot === "object" ? snapshot : {};
    const latestEvent = topbarLatestEvent(Array.isArray(payload.recent_events) ? payload.recent_events : []);
    const pendingLaunch = topbarPendingLaunchIsValid(payload, latestEvent) ? topbarPendingLaunch : null;
    const progress = payload.progress && typeof payload.progress === "object" ? payload.progress : {};
    const currentWork = payload.current_work && typeof payload.current_work === "object" ? payload.current_work : {};
    const pendingPid = pendingLaunch?.pid ? ` · PID ${pendingLaunch.pid}` : "";
    const pendingActivity = pendingLaunch
      ? `${pendingLaunch.label || "pipeline.start"} ${pendingLaunch.statusLabel || "accepted"}${pendingPid}`
      : "";
    const activity = formatProgressValue(pendingActivity || payload.activity || "No active work reported.").trim();
    const cleanName = topbarCleanCurrentName(progress, currentWork);
    const activeSummary = formatProgressValue(
      currentWork.summary_label
      || currentWork.latest_evidence_label
      || currentWork.current_stage_label
      || ""
    ).trim();
    const phaseLabel = formatProgressValue(pendingLaunch?.label || currentWork.current_stage_label || currentWork.phase_label || "").trim();
    const metaText = pendingLaunch
      ? topbarTickerCompactText(pendingLaunch.waitLabel || "", 64)
      : topbarCurrentWorkMeta(currentWork, progress) || topbarStageContext(progress);
    const primaryText = activeSummary || cleanName || activity || "No active work reported.";

    const primary = document.createElement("span");
    primary.className = "activity-primary";
    primary.textContent = primaryText;
    primary.title = primaryText;
    const meta = document.createElement("span");
    meta.className = "activity-meta";
    meta.textContent = metaText;
    if (metaText) meta.title = metaText;
    node.replaceChildren(primary, meta);
    node.title = [phaseLabel, primaryText, metaText].filter(Boolean).join("\n");
  }

  function topbarTickerCompactText(value, maxLength = 96) {
    const text = formatProgressValue(value || "").replace(/\s+/g, " ").trim();
    if (!text) return "";
    return text.length > maxLength ? `${text.slice(0, Math.max(0, maxLength - 1))}…` : text;
  }

  function topbarEventData(event = {}) {
    return event && typeof event.data === "object" && event.data && !Array.isArray(event.data) ? event.data : {};
  }

  function topbarEventTimestampMs(event = {}) {
    const value = event.timestamp || event.created_at || event.recorded_at || event.time || "";
    if (!value) return null;
    const parsed = Date.parse(String(value));
    return Number.isFinite(parsed) ? parsed : null;
  }

  function topbarLatestEvent(events) {
    const items = Array.isArray(events) ? events.filter(Boolean) : [];
    if (!items.length) return null;
    let latest = items[items.length - 1];
    let latestTimestamp = topbarEventTimestampMs(latest);
    items.forEach((item) => {
      const timestamp = topbarEventTimestampMs(item);
      if (timestamp !== null && (latestTimestamp === null || timestamp >= latestTimestamp)) {
        latest = item;
        latestTimestamp = timestamp;
      }
    });
    return latest;
  }

  function topbarEventKey(event) {
    if (!event || typeof event !== "object") return "";
    const data = topbarEventData(event);
    return [
      event.event_id,
      event.timestamp,
      event.created_at,
      event.event_type || event.type || event.kind,
      event.stage,
      event.route,
      event.status,
      event.source_path || data.source_path || data.local_file || data.input_file,
    ].map((value) => String(value || "").trim()).join("|");
  }

  function topbarEventDisplayName(event = {}) {
    const data = topbarEventData(event);
    return topbarPathLeaf(
      data.display_name
        || data.current_file
        || data.currentFile
        || data.source_path
        || data.local_file
        || data.input_file
        || event.source_path
        || event.SourcePath
        || "",
    );
  }

  function topbarEventTickerLine(event) {
    if (!event || typeof event !== "object") return "";
    const type = topbarTickerCompactText(event.event_type || event.type || event.kind || "event", 48);
    const stage = topbarTickerCompactText(event.stage || "", 44);
    const route = topbarTickerCompactText(event.route || "", 44);
    const status = topbarTickerCompactText(event.status || "", 44);
    const display = topbarTickerCompactText(topbarEventDisplayName(event), 96);
    const parts = [type, stage, route, status, display].filter(Boolean);
    return parts.length ? `Latest event: ${parts.join(" · ")}` : "Latest event: backend event received";
  }

  function topbarPendingLaunchLine(pending) {
    const label = topbarTickerCompactText(pending?.label || pending?.command || "pipeline.start", 48) || "pipeline.start";
    const status = topbarTickerCompactText(pending?.statusLabel || "accepted", 32) || "accepted";
    const wait = topbarTickerCompactText(pending?.waitLabel || "waiting for backend event", 64);
    const pid = pending?.pid ? ` · PID ${pending.pid}` : "";
    return `Latest event: ${label} ${status}${pid}${wait ? ` · ${wait}` : ""}`;
  }

  function topbarPipelineState(snapshot = {}) {
    return String(snapshot?.pipeline_state || snapshot?.progress?.Status || "").trim().toLowerCase();
  }

  function topbarPendingLaunchIsValid(snapshot = {}, latestEvent = null) {
    if (!topbarPendingLaunch) return false;
    const now = Date.now();
    if (now > Number(topbarPendingLaunch.expiresAt || 0)) {
      topbarPendingLaunch = null;
      return false;
    }
    const latestKey = topbarEventKey(latestEvent);
    if (latestKey && latestKey !== topbarPendingLaunch.baselineEventKey) {
      topbarPendingLaunch = null;
      return false;
    }
    const elapsed = now - Number(topbarPendingLaunch.acceptedAt || now);
    if (elapsed > TOPBAR_IDLE_PENDING_GRACE_MS && topbarPipelineState(snapshot) === "idle") {
      topbarPendingLaunch = null;
      return false;
    }
    return true;
  }

  function renderTopbarEventTicker(snapshot = {}) {
    const node = byId("topbar-event-ticker");
    if (!node) return;
    const payload = snapshot && typeof snapshot === "object" ? snapshot : {};
    const events = Array.isArray(payload.recent_events) ? payload.recent_events : [];
    const latestEvent = topbarLatestEvent(events);
    let text = "";
    let state = "empty";
    if (topbarPendingLaunchIsValid(payload, latestEvent)) {
      text = topbarPendingLaunchLine(topbarPendingLaunch);
      state = "pending";
    } else if (latestEvent) {
      text = topbarEventTickerLine(latestEvent);
      state = "event";
    } else {
      text = "Latest event: no backend pipeline events reported yet";
    }
    node.textContent = text;
    node.title = text;
    node.dataset.state = state;
  }

  function setTopbarPendingLaunch(payload = {}) {
    const latestEvent = topbarLatestEvent(Array.isArray(lastSnapshot?.recent_events) ? lastSnapshot.recent_events : []);
    const acceptedAt = Date.now();
    topbarPendingLaunch = {
      acceptedAt,
      baselineEventKey: topbarEventKey(latestEvent),
      expiresAt: acceptedAt + TOPBAR_PENDING_LAUNCH_TTL_MS,
      label: topbarTickerCompactText(payload.label || payload.command || "pipeline.start", 48) || "pipeline.start",
      pid: topbarTickerCompactText(payload.pid || "", 24),
      statusLabel: topbarTickerCompactText(payload.status_label || payload.statusLabel || payload.status || "accepted", 32) || "accepted",
      waitLabel: topbarTickerCompactText(payload.wait_label || payload.waitLabel || "waiting for backend event", 64),
    };
    renderTopbarEventTicker(lastSnapshot || {});
  }

  function clearTopbarPendingLaunch(snapshot = lastSnapshot || {}) {
    topbarPendingLaunch = null;
    renderTopbarEventTicker(snapshot || {});
  }

  function formatCloseReadiness(closeReadiness) {
    if (!closeReadiness) return "Close readiness has not loaded yet.";
    const warnings = Array.isArray(closeReadiness.warnings) ? closeReadiness.warnings : [];
    const watcher = closeReadinessWatcherData(closeReadiness);
    const lines = [
      `Safe to close: ${closeReadiness.safe_to_close ? "yes" : "no"}`,
      `State: ${closeReadiness.state || "unknown"}`,
      `Active work: ${closeReadiness.active_work ? "yes" : "no"}`,
      `Reason: ${closeReadiness.reason || "No reason reported."}`,
      `Continuous watcher: ${closeReadinessWatcherSummary(closeReadiness)}`,
    ];
    if (Object.keys(watcher).length) {
      lines.push(
        `Watcher generation: ${Number(watcher.generation || 0) > 0 ? watcher.generation : "none"}`,
        `Watcher stop requested: ${watcher.stop_requested ? "yes" : "no"}`,
        `Watcher message: ${watcher.message || "(not reported)"}`,
        `Watcher error: ${watcher.error || "none"}`
      );
    }
    if (warnings.length) {
      lines.push("", "Warnings:");
      warnings.forEach((warning) => lines.push(`- ${warning}`));
    }
    return lines.join("\n");
  }

  function closeReadinessWatcherData(closeReadiness = lastCloseReadiness) {
    return closeReadiness?.continuous_watcher && typeof closeReadiness.continuous_watcher === "object"
      ? closeReadiness.continuous_watcher
      : {};
  }

  function closeReadinessWatcherSummary(closeReadiness = lastCloseReadiness) {
    const watcher = closeReadinessWatcherData(closeReadiness);
    const status = String(watcher.status || "unknown");
    const pid = Number(watcher.pid || 0) > 0 ? ` for PID ${watcher.pid}` : "";
    const deadline = watcher.deadline ? ` until ${typeof scheduleDisplayValue === "function" ? scheduleDisplayValue(watcher.deadline) : watcher.deadline}` : "";
    return `${status}${pid}${deadline}`;
  }

  function closeReadinessWatcherIsArmed(closeReadiness = lastCloseReadiness) {
    return String(closeReadinessWatcherData(closeReadiness).status || "").toLowerCase() === "armed";
  }

  function backendLifecycleState(closeReadiness = lastCloseReadiness) {
    if (!closeReadiness) {
      return {
        label: "Waiting",
        state: "unknown",
        canShutdown: false,
        reason: "Close-readiness has not loaded yet.",
      };
    }
    if (closeReadiness.safe_to_close === true) {
      return {
        label: "Safe to request",
        state: "ready",
        canShutdown: true,
        reason: closeReadiness.reason || "Close-readiness reports that no active work is blocking backend shutdown.",
      };
    }
    if (closeReadinessWatcherIsArmed(closeReadiness)) {
      return {
        label: "Watcher armed",
        state: "blocked",
        canShutdown: false,
        reason: closeReadiness.reason || "Backend schedule-stop watcher is armed; keep the local backend running or use backend-owned stop controls first.",
      };
    }
    return {
      label: "Blocked",
      state: "blocked",
      canShutdown: false,
      reason: closeReadiness.reason || "Active work, stale runtime state, or unverifiable close-readiness is blocking shutdown.",
    };
  }

  function startupProgressLines(progress = lastStartupProgress) {
    const payload = progress && typeof progress === "object" ? progress : null;
    if (!payload || !Array.isArray(payload.steps)) {
      return ["Startup progress: not reported by backend bootstrap."];
    }
    const steps = payload.steps;
    const status = payload.status || "unknown";
    const completed = Number(payload.completed_steps || 0);
    const total = Number(payload.total_steps || steps.length || 0);
    const percent = Number(payload.percent);
    const summary = `Startup progress: ${status}; ${completed} / ${total} step${total === 1 ? "" : "s"}${Number.isFinite(percent) ? `; ${percent.toFixed(1)}%` : ""}`;
    const recent = steps.slice(-5).map((step) => {
      const detail = step.detail ? ` - ${step.detail}` : "";
      return `- ${step.label || step.id || "startup step"}: ${step.status || "unknown"}${detail}`;
    });
    return [summary, ...recent];
  }

  function normalizeTauriBackendLifecycleEvent(payload) {
    const source = payload && typeof payload === "object" && payload.payload && typeof payload.payload === "object"
      ? payload.payload
      : payload && typeof payload === "object"
        ? payload
        : {};
    return {
      schema_version: source.schema_version || "unknown",
      status: String(source.status || "unknown"),
      detail: String(source.detail || "No lifecycle detail was reported."),
      consecutive_failures: Number(source.consecutive_failures || 0),
      emitted_at_unix_seconds: Number(source.emitted_at_unix_seconds || 0),
    };
  }

  function tauriBackendLifecycleStatusLabel(status) {
    if (status === "backend_exited") return "Backend exited";
    if (status === "backend_health_failed") return "Backend health failed";
    if (status === "monitor_error") return "Lifecycle monitor error";
    return "Backend lifecycle warning";
  }

  function tauriBackendLifecycleLines(event = lastTauriBackendLifecycleEvent) {
    if (!event) return [];
    return [
      "",
      "Tauri lifecycle monitor:",
      `Status: ${tauriBackendLifecycleStatusLabel(event.status)} (${event.status})`,
      `Detail: ${event.detail}`,
      `Consecutive health failures: ${event.consecutive_failures}`,
      `Schema: ${event.schema_version}`,
      "Recovery: refresh once, then inspect Diagnostics run logs, close-readiness, ActiveJobs, and backend stderr before launching, draining, saving settings, renaming, publishing, or closing the shell.",
    ];
  }

  function renderTauriBackendLifecycleAlert(event = lastTauriBackendLifecycleEvent) {
    const topbar = document.querySelector(".topbar");
    if (!topbar || !event) return;
    let node = document.querySelector(".tauri-lifecycle-alert");
    if (!node) {
      node = document.createElement("div");
      node.className = "tauri-lifecycle-alert";
      node.setAttribute("role", "alert");
      topbar.insertAdjacentElement("afterend", node);
    }
    node.dataset.state = event.status === "backend_health_failed" ? "warning" : "blocked";
    const title = document.createElement("strong");
    title.textContent = tauriBackendLifecycleStatusLabel(event.status);
    const detail = document.createElement("span");
    detail.textContent = event.detail;
    const hint = document.createElement("span");
    hint.textContent = "Open Diagnostics before starting, draining, saving, renaming, publishing, or closing.";
    node.replaceChildren(title, detail, hint);
  }

  function pipelineControlReadinessStatus(snapshot, closeReadiness) {
    if (!snapshot) return "No snapshot";
    if (closeReadiness?.safe_to_close === false || closeReadiness?.active_work) return "Active controls";
    const state = String(snapshot.pipeline_state || closeReadiness?.state || "").toLowerCase();
    if (["processing", "running", "active", "publishing", "audit"].includes(state)) return "Active controls";
    if (["idle", "completed", "failed"].includes(state)) return "Idle";
    return "Review state";
  }

  function pipelineControlReadinessLines(snapshot, closeReadiness) {
    if (!snapshot) {
      return [
        "Snapshot: unavailable",
        "Control guidance: wait for snapshot refresh before sending pipeline controls.",
        "Mutation guardrail: control buttons send backend-owned control flags through /api/pipeline/control.",
      ];
    }
    const state = snapshot.pipeline_state || closeReadiness?.state || "unknown";
    const progress = snapshot.progress && typeof snapshot.progress === "object" ? snapshot.progress : {};
    const active = closeReadiness?.safe_to_close === false || closeReadiness?.active_work === true;
    const lines = [
      `Pipeline state: ${state}`,
      `Active work: ${active ? "yes" : "no"}`,
      `Close readiness: ${closeReadiness ? (closeReadiness.safe_to_close ? "safe" : "active/blocked") : "unknown"}`,
      progress.CurrentStage ? `Current backend stage: ${progress.CurrentStage}` : "",
      progress.Status ? `Progress status: ${progress.Status}` : "",
    ].filter(Boolean);
    if (closeReadiness?.reason) lines.push(`Close reason: ${closeReadiness.reason}`);
    lines.push("");
    if (active) {
      lines.push("Pause / Resume: meaningful while backend work is active.");
      lines.push("Rescan: request only when the running pipeline should refresh queue state.");
      lines.push("Stop After Current: request when current work should finish but no new item should start.");
    } else {
      lines.push("Pause / Resume: normally unnecessary while no active work is reported.");
      lines.push("Rescan: normally unnecessary while idle; refresh Queue or launch a fresh preview instead.");
      lines.push("Stop After Current: normally unnecessary while close-readiness reports safe.");
    }
    lines.push("Mutation guardrail: control buttons send backend-owned control flags through /api/pipeline/control and backend locks remain the source of truth.");
    return lines;
  }

  function renderControlReadiness(snapshot = lastSnapshot, closeReadiness = lastCloseReadiness) {
    setTextState("control-readiness-status", pipelineControlReadinessStatus(snapshot, closeReadiness));
    setTextState("home-control-readiness-status", pipelineControlReadinessStatus(snapshot, closeReadiness));
    setText("control-readiness", pipelineControlReadinessLines(snapshot, closeReadiness).join("\n"));
    window.mediaPipelineLaunchView?.updateLaunchCommandButtonStates?.(snapshot, closeReadiness);
  }
    return {
      formatProgressValue,
      topbarStageContext,
      renderTopbarActivity,
      renderTopbarEventTicker,
      setTopbarPendingLaunch,
      clearTopbarPendingLaunch,
      topbarEventTickerLine,
      formatCloseReadiness,
      closeReadinessWatcherData,
      closeReadinessWatcherSummary,
      closeReadinessWatcherIsArmed,
      backendLifecycleState,
      startupProgressLines,
      normalizeTauriBackendLifecycleEvent,
      tauriBackendLifecycleLines,
      renderTauriBackendLifecycleAlert,
      renderControlReadiness,
    };
  }

  window.__appLifecycleTopbarModule = { createAppLifecycleTopbar };
})();
