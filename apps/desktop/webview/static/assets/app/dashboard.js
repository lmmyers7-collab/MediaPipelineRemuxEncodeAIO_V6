/* Dashboard snapshot projection, current-work metrics, and queue outcome rendering. */
function renderSnapshot(snapshot) {
  lastSnapshot = snapshot || {};
  const state = snapshot.pipeline_state || "idle";
  renderBrandVersion(snapshot);
  renderTopbarActivity(snapshot);
  renderTopbarEventTicker(snapshot);
  renderHomePipelineState(state);
  setText("status-summary", snapshot.status_summary || "No status summary.");
  const pill = byId("state-pill");
  if (pill) {
    const phaseLabel = snapshot?.current_work?.current_stage_label || snapshot?.current_work?.phase_label || state;
    pill.textContent = phaseLabel;
    pill.dataset.state = state;
    pill.title = [
      snapshot?.current_work?.summary_label,
      snapshot?.current_work?.item_label,
      snapshot?.current_work?.latest_evidence_label,
      snapshot?.current_work?.next_stage_label ? `Next: ${snapshot.current_work.next_stage_label}` : "",
    ].filter(Boolean).join("\n");
  }
  const counts = snapshot.counts || {};
  renderDashboardCurrentWorkMetric(snapshot, counts);
  const pipelineState = byId("pipeline-state");
  if (pipelineState) delete pipelineState.dataset.state;
  setText("processed-count", String(counts.processed || 0));
  renderDashboardIssueMetric(snapshot, dashboardCount(counts.failed));
  window.mediaPipelineProgressView?.renderProgressDetails?.(snapshot.progress || {});
  window.mediaPipelineProgressView?.renderProgressBars?.(Array.isArray(snapshot.progress_bars) ? snapshot.progress_bars : [], snapshot, {
    closeReadiness: lastCloseReadiness,
    stdoutTail: lastStdoutTail,
  });
  window.mediaPipelineProgressView?.renderProgressEvidence?.({ snapshot: lastSnapshot, closeReadiness: lastCloseReadiness, diagnostics: null });
  window.mediaPipelineProgressView?.renderDiagnosticsProgress?.(lastSnapshot);
  window.mediaPipelineProgressView?.renderLiveRunStrip?.({
    snapshot: lastSnapshot,
    diagnostics: null,
    closeReadiness: lastCloseReadiness,
    stdoutTail: lastStdoutTail,
  });
  const recentEvents = Array.isArray(snapshot.recent_events) ? snapshot.recent_events : [];
  window.mediaPipelineProgressView?.renderPipelineEvents?.(recentEvents);
  renderSparkline(recentEvents);
  window.mediaPipelineReportsView?.renderReports?.(lastSnapshot, getLastSettings());
  renderControlReadiness(lastSnapshot, lastCloseReadiness);
  renderLaunchReadinessPanel({ snapshot: lastSnapshot, closeReadiness: lastCloseReadiness, schedule: lastSchedule, settings: getLastSettings() });
  renderBackendLifecycle(lastCloseReadiness, lastSnapshot);
}

function dashboardCurrentWork(snapshot = {}) {
  return snapshot?.current_work && typeof snapshot.current_work === "object" ? snapshot.current_work : {};
}

function dashboardCurrentWorkDetail(currentWork = {}, counts = {}) {
  const queueIndex = Math.max(0, Math.trunc(Number(counts.queue_index) || 0));
  const queueTotal = Math.max(0, Math.trunc(Number(counts.queue_total) || 0));
  return [
    currentWork.current_stage_label ? `Stage: ${currentWork.current_stage_label}` : "",
    currentWork.latest_evidence_label ? `Evidence: ${currentWork.latest_evidence_label}` : "",
    currentWork.missing_evidence_label || "",
    currentWork.route_label || "",
    currentWork.queue_position_label || (queueTotal > 0 ? `item ${queueIndex} of ${queueTotal}` : ""),
    currentWork.next_stage_label ? `Next: ${currentWork.next_stage_label}` : "",
  ].filter(Boolean).join(" · ");
}

function renderDashboardCurrentWorkMetric(snapshot = {}, counts = {}) {
  const currentWork = dashboardCurrentWork(snapshot);
  const item = currentWork.item_label || "";
  const summary = currentWork.summary_label || currentWork.latest_evidence_label || currentWork.current_stage_label || "";
  const queueIndex = Math.max(0, Math.trunc(Number(counts.queue_index) || 0));
  const queueTotal = Math.max(0, Math.trunc(Number(counts.queue_total) || 0));
  const queueCount = byId("queue-count");
  if (item || summary) {
    setText("queue-count", item || summary);
    setText("queue-count-detail", dashboardCurrentWorkDetail(currentWork, counts) || "Backend current-work summary.");
    if (queueCount) {
      queueCount.title = [item, summary, dashboardCurrentWorkDetail(currentWork, counts)].filter(Boolean).join("\n");
      queueCount.dataset.mode = "file";
      queueCount.dataset.state = currentWork.evidence_status === "waiting" ? "warning" : "running";
    }
    return;
  }
  setText("queue-count", `${queueIndex} / ${queueTotal}`);
  setText("queue-count-detail", "Backend queue position.");
  if (queueCount) {
    delete queueCount.dataset.mode;
    delete queueCount.dataset.state;
    queueCount.title = "";
  }
}

function dashboardText(value) {
  return String(value || "").trim().toLowerCase();
}

function dashboardCount(value) {
  const number = Number(value);
  return Number.isFinite(number) ? Math.max(0, Math.trunc(number)) : 0;
}

function dashboardBoolean(value) {
  if (typeof value === "boolean") return value;
  const text = dashboardText(value);
  if (["1", "true", "yes", "y"].includes(text)) return true;
  if (["0", "false", "no", "n"].includes(text)) return false;
  return false;
}

function dashboardEventData(event) {
  return event?.data && typeof event.data === "object" ? event.data : {};
}

function dashboardEventIsStopRequested(event) {
  const data = dashboardEventData(event);
  const status = dashboardText(data.completion_status || event?.status || "");
  const errorCode = dashboardText(data.error_code || data.ErrorCode || "");
  const reason = dashboardText(data.reason || data.suggested_action || "");
  return status === "stopped" && (errorCode === "stop_requested" || (reason.includes("stop") && reason.includes("operator")));
}

function dashboardEventIsFailure(event) {
  const data = dashboardEventData(event);
  const status = dashboardText(data.completion_status || event?.status || data.classification || "");
  const errorCode = dashboardText(data.error_code || data.ErrorCode || "");
  return ["failed", "failure", "error", "blocked"].includes(status)
    || String(event?.event_type || "").toLowerCase() === "failure_recorded"
    || Boolean(errorCode && errorCode !== "stop_requested");
}

function dashboardProgressHasStopRequested(progress = {}) {
  const payload = progress && typeof progress === "object" ? progress : {};
  if (dashboardBoolean(payload.StopRequested) || dashboardBoolean(payload.stop_requested)) return true;
  const errorCode = dashboardText(payload.ErrorCode || payload.error_code || "");
  const reason = dashboardText(payload.Reason || payload.reason || "");
  if (errorCode === "stop_requested") return true;
  if (reason.includes("stop") && reason.includes("operator")) return true;
  const text = dashboardText([
    payload.CurrentStage,
    payload.Status,
    payload.status,
    payload.CurrentStatus,
  ].filter(Boolean).join(" "));
  return /\bstopped\b/.test(text) && (errorCode === "stop_requested" || (reason.includes("stop") && reason.includes("operator")));
}

function dashboardLatestStopRequestedOutcome(snapshot = {}) {
  const events = Array.isArray(snapshot?.recent_events) ? snapshot.recent_events : [];
  for (let index = events.length - 1; index >= 0; index -= 1) {
    const event = events[index];
    if (dashboardEventIsStopRequested(event)) return true;
    if (dashboardEventIsFailure(event)) return false;
  }
  return dashboardProgressHasStopRequested(snapshot?.progress || {});
}

function renderDashboardIssueMetric(snapshot = {}, failedCount = 0) {
  const stoppedByRequest = failedCount > 0 && dashboardLatestStopRequestedOutcome(snapshot);
  const visibleFailedCount = stoppedByRequest ? Math.max(0, failedCount - 1) : failedCount;
  const label = "Failed";
  const title = stoppedByRequest
    ? visibleFailedCount
      ? "Stop After Current is shown in progress; this remaining count still needs Diagnostics or run-log review."
      : "Stop After Current is shown in progress; this marker is not counted as a failed media output."
    : visibleFailedCount
      ? "Failed items need Diagnostics or run-log review."
      : "No failed items reported.";
  setText("failed-count", String(visibleFailedCount));
  setText("home-failed-count", String(visibleFailedCount));
  setText("failed-label", label);
  setText("home-failed-label", label);
  ["failed-count", "home-failed-count", "failed-label", "home-failed-label"].forEach((id) => {
    const node = byId(id);
    if (node) {
      node.title = title;
      node.dataset.state = visibleFailedCount ? "blocked" : "ok";
    }
  });
}

function dashboardHasOwn(source, key) {
  return Boolean(source && typeof source === "object" && Object.prototype.hasOwnProperty.call(source, key));
}

function dashboardPipelineStateAllowsEmptyScan(snapshot = lastSnapshot) {
  const state = dashboardText(snapshot?.pipeline_state || "");
  return !state || ["idle", "complete", "completed", "sleeping"].includes(state);
}

function dashboardQueueScanStatus(queue = {}) {
  const status = queue?.queue_scan_status;
  return status && typeof status === "object" ? status : {};
}

function dashboardQueueProgress(queue = {}) {
  const progress = queue?.queue_progress;
  return progress && typeof progress === "object" ? progress : {};
}

function dashboardQueueScanRunning(queue = {}) {
  const status = dashboardQueueScanStatus(queue);
  return Boolean(status.running) || dashboardText(status.status) === "running";
}

function dashboardQueueStale(queue = {}) {
  const progress = dashboardQueueProgress(queue);
  return Boolean(progress.stale)
    || dashboardText(queue.snapshot_file_freshness_status) === "stale"
    || dashboardText(queue.produced_freshness_status) === "stale";
}

function dashboardQueueBlockingWarnings(queue = {}) {
  const warnings = Array.isArray(queue.warnings) ? queue.warnings : [];
  return warnings.some((warning) => dashboardText(warning) !== "queue snapshot contains no runnable rows.");
}

function dashboardQueueRunnableCount(queue = {}) {
  if (dashboardHasOwn(queue, "runnable_count")) return dashboardCount(queue.runnable_count);
  if (Array.isArray(queue.rows)) return queue.rows.length;
  return null;
}

function dashboardQueueHasFreshEmptyProof(queue = {}) {
  const status = dashboardQueueScanStatus(queue);
  const scanStatus = dashboardText(status.status);
  if (scanStatus === "completed" && dashboardHasOwn(status, "curated_row_count")) {
    return dashboardCount(status.curated_row_count) === 0;
  }

  const runnableCount = dashboardQueueRunnableCount(queue);
  if (runnableCount !== 0) return false;

  const progress = dashboardQueueProgress(queue);
  const progressStatus = dashboardText(progress.status);
  const hasFreshnessEvidence = Boolean(queue.snapshot_file_freshness_status || queue.produced_freshness_status);
  return progressStatus === "complete" || hasFreshnessEvidence;
}

function renderHomePipelineQueueOutcome(snapshot = lastSnapshot, queue = {}) {
  if (!dashboardPipelineStateAllowsEmptyScan(snapshot)) return false;
  if (!queue || typeof queue !== "object" || !queue.schema_version || queue.error) return false;
  if (dashboardQueueScanRunning(queue) || dashboardQueueStale(queue) || dashboardQueueBlockingWarnings(queue)) return false;
  if (!dashboardQueueHasFreshEmptyProof(queue)) return false;
  renderHomePipelineState("no_new_sources");
  return true;
}
