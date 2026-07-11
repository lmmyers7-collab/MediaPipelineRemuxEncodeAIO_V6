(function () {
  function createProgressEvidenceRowsModule(deps = {}) {
    const { formatProgressValue, formatProgressUpdatedAt, normalizedProgressState, progressStateIsActive, progressLatestEvent, progressEventLabel, progressActiveJobRows, formatActiveJobEvidenceRow, progressWorkerRows, progressWorkerPayload, progressWorkerSummaryLine, formatWorkerProgressRow, progressFfmpegRows, progressFfmpegPayload, progressFfmpegSummaryLine, formatFfmpegProgressRow, progressEtaRows, progressEtaPayload, progressEtaSummaryLine, formatEtaRow } = deps;
    const activeWorkProgressLine = (...args) => deps.getActiveWorkProgressLine()(...args);
    const activeWorkRouteLine = (...args) => deps.getActiveWorkRouteLine()(...args);
    const activeWorkQueueLine = (...args) => deps.getActiveWorkQueueLine()(...args);
    const activeWorkControlLine = (...args) => deps.getActiveWorkControlLine()(...args);
      function progressEvidenceRows({ snapshot = null, closeReadiness = null, diagnostics = null } = {}) {
        const progress = snapshot?.progress && typeof snapshot.progress === "object" ? snapshot.progress : {};
        const auditProgress = snapshot?.audit_progress && typeof snapshot.audit_progress === "object" ? snapshot.audit_progress : {};
        const state = normalizedProgressState(snapshot, progress);
        const active = progressStateIsActive(state);
        const activeJobs = progressActiveJobRows(diagnostics);
        const workerRows = progressWorkerRows(snapshot, diagnostics);
        const workerPayload = progressWorkerPayload(snapshot, diagnostics);
        const ffmpegRows = progressFfmpegRows(snapshot, diagnostics);
        const ffmpegPayload = progressFfmpegPayload(snapshot, diagnostics);
        const ffmpegParseError = Number(ffmpegPayload.parse_error_count || 0) > 0;
        const etaRows = progressEtaRows(snapshot, diagnostics);
        const etaPayload = progressEtaPayload(snapshot, diagnostics);
        const etaEstimated = Number(etaPayload.estimated_count || 0) > 0;
        const etaUnavailable = Number(etaPayload.unavailable_count || 0) > 0;
        const events = Array.isArray(snapshot?.recent_events) ? snapshot.recent_events : [];
        const latest = progressLatestEvent(events);
        const route = activeWorkRouteLine(progress);
        const queue = activeWorkQueueLine(progress);
        const control = activeWorkControlLine(progress);
        const auditState = String(auditProgress.status || auditProgress.Status || "").trim().toLowerCase();
        const auditActive = progressStateIsActive(auditState);
        const rows = [];

        rows.push({
          key: "snapshot-state",
          checkpoint: "Snapshot state",
          posture: active ? "active" : state === "unknown" ? "unknown" : "idle",
          evidence: `${snapshot?.activity || "No activity text"}; state=${state}`,
          action: active
            ? "Monitor Progress Details and wait for close-readiness to report safe before closing or starting more work."
            : "Confirm Queue/Completed/Pending pages if you expected active work.",
          detail: [
            `Pipeline state: ${state}`,
            `Activity: ${snapshot?.activity || "not reported"}`,
            activeWorkProgressLine(progress) || "No active stage/file progress reported.",
          ],
        });

        rows.push({
          key: "close-readiness",
          checkpoint: "Close readiness",
          posture: closeReadiness ? (closeReadiness.safe_to_close ? "safe" : "active work") : "unknown",
          evidence: closeReadiness ? `${closeReadiness.state || "unknown"}; ${closeReadiness.reason || "no reason"}` : "Close-readiness payload has not loaded.",
          action: closeReadiness?.safe_to_close === false
            ? "Do not close unless intentionally interrupting work. Inspect ActiveJobs, Run Logs, Last Stderr, and progress fields first."
            : closeReadiness?.safe_to_close === true
              ? "Safe-to-close is reported, but still compare ActiveJobs and progress rows if state looks stale."
              : "Refresh before closing; unknown close-readiness is not proof that work is idle.",
          detail: [
            `Safe to close: ${closeReadiness ? (closeReadiness.safe_to_close ? "yes" : "no") : "unknown"}`,
            `Reason: ${closeReadiness?.reason || "not reported"}`,
            `Warnings: ${(closeReadiness?.warnings || []).join(" | ") || "none"}`,
          ],
        });

        rows.push({
          key: "active-jobs",
          checkpoint: "ActiveJobs",
          posture: activeJobs.length ? "active work" : "no active job rows",
          evidence: `${activeJobs.length} ActiveJobs row${activeJobs.length === 1 ? "" : "s"} loaded.`,
          action: activeJobs.length
            ? "Open Diagnostics > ActiveJobs or Runtime Artifacts before closing, relaunching, or clearing state."
            : "If progress says active but ActiveJobs is empty, inspect Run Logs and Last Stderr for stale progress state.",
          detail: activeJobs.length
            ? activeJobs.slice(0, 8).map(formatActiveJobEvidenceRow)
            : ["No ActiveJobs rows were loaded from Diagnostics."],
        });

        rows.push({
          key: "worker-progress",
          checkpoint: "Worker progress",
          posture: workerPayload.status || (workerRows.length ? "loaded" : "not loaded"),
          evidence: progressWorkerSummaryLine(snapshot, diagnostics),
          action: workerRows.length
            ? "Use worker progress as live telemetry only; compare it with ActiveJobs and Run Logs before close, stop, retry, or rerun decisions."
            : "Do not infer per-worker progress in the WebView until the backend worker-progress contract is present.",
          detail: workerRows.length
            ? workerRows.slice(0, 8).map(formatWorkerProgressRow)
            : ["No desktop_worker_progress.v1 rows were loaded."],
        });

        rows.push({
          key: "ffmpeg-progress",
          checkpoint: "FFmpeg progress proof",
          posture: ffmpegParseError ? "missing progress" : ffmpegRows.length ? (ffmpegPayload.status || "loaded") : ffmpegPayload.status === "unavailable" ? "missing progress" : ffmpegPayload.status || "idle",
          evidence: progressFfmpegSummaryLine(snapshot, diagnostics),
          action: ffmpegParseError || ffmpegPayload.status === "unavailable"
            ? "Open Run Logs and Last Stderr; active encode/remux work did not expose parseable FFmpeg key/value progress."
            : ffmpegRows.length
            ? "Use FFmpeg progress as runtime proof only; do not infer ETA, GPU use, or output integrity from it."
            : "No FFmpeg progress action is needed while encode/remux evidence is idle or absent.",
          detail: ffmpegRows.length
            ? ffmpegRows.slice(0, 8).map(formatFfmpegProgressRow)
            : Array.isArray(ffmpegPayload.summary_lines) && ffmpegPayload.summary_lines.length
              ? ffmpegPayload.summary_lines
              : ["No desktop_ffmpeg_progress.v1 rows were loaded."],
        });

        rows.push({
          key: "eta",
          checkpoint: "ETA",
          posture: etaEstimated ? "loaded" : etaUnavailable ? "missing progress" : etaPayload.status || "idle",
          evidence: progressEtaSummaryLine(snapshot, diagnostics),
          action: etaEstimated
            ? "Treat ETA as a rough current-stage estimate only; keep using progress, logs, and close-readiness for run decisions."
            : etaUnavailable
            ? "No ETA is shown until backend worker progress reports usable percent and elapsed-time evidence."
            : "No ETA action is needed while no active worker row is reported.",
          detail: etaRows.length
            ? etaRows.slice(0, 8).map(formatEtaRow)
            : Array.isArray(etaPayload.summary_lines) && etaPayload.summary_lines.length
              ? etaPayload.summary_lines
              : ["No desktop_eta.v1 rows were loaded."],
        });

        rows.push({
          key: "current-item",
          checkpoint: "Current item",
          posture: activeWorkProgressLine(progress) ? (active ? "active" : "loaded") : active ? "missing progress" : "idle",
          evidence: activeWorkProgressLine(progress) || "No current stage/file fields are present.",
          action: active && !activeWorkProgressLine(progress)
            ? "Inspect Run Logs and Last Stderr; active state without current-item detail may mean stale or malformed progress."
            : "Use this as live context only; Completed/Pending evidence remains the output proof.",
          detail: [
            activeWorkProgressLine(progress) || "No stage/file progress line available.",
            `Current file: ${formatProgressValue(progress.CurrentFileDisplay || progress.CurrentFile || progress.InputFile || "not reported")}`,
            `Updated at: ${formatProgressUpdatedAt(progress.UpdatedAt || progress.updated_at) || "not reported"}`,
          ],
        });

        rows.push({
          key: "route-queue",
          checkpoint: "Route / queue",
          posture: route || queue ? "loaded" : active ? "missing route" : "idle",
          evidence: [route, queue].filter(Boolean).join(" | ") || "No route or queue-position fields are present.",
          action: route || queue
            ? "Compare route/queue fields against Queue row route evidence before judging remux/encode behavior."
            : "Use Queue and Completed row details if route/queue fields are missing.",
          detail: [
            route || "Route: not reported",
            queue || "Queue position: not reported",
            `Route reason: ${formatProgressValue(progress.RouteReason || progress.CurrentRouteReason || "not reported")}`,
          ],
        });

        rows.push({
          key: "control-flags",
          checkpoint: "Control flags",
          posture: /yes/.test(control) ? "paused/stop requested" : control ? "clear" : "unknown",
          evidence: control || "Pause/stop request fields are not present.",
          action: /yes/.test(control)
            ? "Expect progress to slow, pause, or finish current item. Check Control command history and Run Logs before pressing another control."
            : "Use controls only when close-readiness and active-work summary agree work is running.",
          detail: [
            `Pause requested: ${progress.PauseRequested === undefined ? "not reported" : progress.PauseRequested ? "yes" : "no"}`,
            `Stop requested: ${progress.StopRequested === undefined ? "not reported" : progress.StopRequested ? "yes" : "no"}`,
          ],
        });

        rows.push({
          key: "recent-events",
          checkpoint: "Recent events",
          posture: events.length ? "events loaded" : active ? "missing events" : "no recent events",
          evidence: `${events.length} event${events.length === 1 ? "" : "s"}; latest=${progressEventLabel(latest)}`,
          action: events.length
            ? "Use Recent Pipeline Events as supporting context, not as output proof."
            : active
              ? "Open Run Logs and Last Stderr if active work has no recent events."
              : "No event history is expected when idle or after older events roll off.",
          detail: events.length
            ? events.slice(-8).reverse().map((event) => `${progressEventLabel(event)}: ${formatProgressValue(event.data || event)}`)
            : ["No recent pipeline events are loaded in the snapshot."],
        });

        rows.push({
          key: "audit-progress",
          checkpoint: "Audit progress",
          posture: auditActive ? "audit active" : Object.keys(auditProgress).length ? "audit loaded" : "no audit progress",
          evidence: auditProgress.status || auditProgress.Status || auditProgress.current_operation || "No audit progress fields are loaded.",
          action: auditActive
            ? "Use Diagnostics runtime progress and audit logs before closing or launching pipeline work."
            : "Audit progress is informational unless audit state is active or close-readiness blocks.",
          detail: Object.keys(auditProgress).length
            ? Object.keys(auditProgress).sort().slice(0, 12).map((key) => `${key}: ${formatProgressValue(auditProgress[key])}`)
            : ["No audit progress object is present in the snapshot."],
        });

        rows.push({
          key: "proof-boundary",
          checkpoint: "Proof boundary",
          posture: "read-only",
          evidence: "Progress explains current activity; it is not publish, completion, or output-integrity proof.",
          action: "Use Completed, Pending Publish, Queue, and Diagnostics proof panels before rerun, cleanup, drain, or trust decisions.",
          detail: [
            "This board does not launch, pause, stop, rescan, drain, publish, delete, repair, rewrite, or open arbitrary paths.",
            "Progress is runtime evidence only. Output proof belongs to Completed, Pending Publish, and durable drain/manifest artifacts.",
          ],
        });

        return rows;
      }

    return { progressEvidenceRows };
  }

  window.__progressEvidenceRowsModule = { createProgressEvidenceRowsModule };
})();

