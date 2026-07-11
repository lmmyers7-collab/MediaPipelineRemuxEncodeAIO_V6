(function () {
  function createProgressDiagnosticsModule(deps) {
    deps = deps || {};
    const formatProgressValue = deps.formatProgressValue || ((value) => String(value ?? ""));
    const progressRowsForSource = deps.progressRowsForSource || (() => []);
    const audioProgressLine = deps.audioProgressLine || (() => "");
    const pendingDrainProgressLine = deps.pendingDrainProgressLine || (() => "");
    const progressWorkerRows = deps.progressWorkerRows || (() => []);
    const formatWorkerProgressRow = deps.formatWorkerProgressRow || (() => "");
    const progressFfmpegRows = deps.progressFfmpegRows || (() => []);
    const formatFfmpegProgressRow = deps.formatFfmpegProgressRow || (() => "");
    const progressEtaRows = deps.progressEtaRows || (() => []);
    const formatEtaRow = deps.formatEtaRow || (() => "");
    const auditProgressIsStaleForUi = deps.auditProgressIsStaleForUi || (() => false);
    const activeWorkProgressLine = deps.activeWorkProgressLine || (() => "");
    const activeWorkRouteLine = deps.activeWorkRouteLine || (() => "");
    const activeWorkQueueLine = deps.activeWorkQueueLine || (() => "");
    const activeWorkControlLine = deps.activeWorkControlLine || (() => "");
    const progressWorkerSummaryLine = deps.progressWorkerSummaryLine || (() => "");
    const progressFfmpegSummaryLine = deps.progressFfmpegSummaryLine || (() => "");
    const progressEtaSummaryLine = deps.progressEtaSummaryLine || (() => "");
    const setText = deps.setText || (() => {});
    const renderProgressBarsInto = deps.renderProgressBarsInto || (() => {});
    const progressWorkerPayload = deps.progressWorkerPayload || (() => ({}));
    const byId = deps.byId || (() => null);
    const clearRows = deps.clearRows || (() => {});
    const appendCells = deps.appendCells || (() => {});

    function diagnosticsProgressRows(snapshot, diagnostics = null) {
      const pipelinePreferred = [
        "Status", "CurrentStage", "CurrentStagePercent", "CurrentFileDisplay", "CurrentFile",
        "CurrentRoute", "RouteReason", "CurrentQueueIndex", "CurrentQueueTotal", "CurrentStageStartedAt",
        "CurrentItemStartedAt", "PushState", "CopyStartedAt", "CopyUpdatedAt", "PauseRequested",
        "StopRequested", "UpdatedAt",
      ];
      const auditPreferred = [
        "status", "current_operation", "current_file", "processed_files", "total_files",
        "percent_complete", "report_stage", "report_step_index", "report_step_total",
        "report_completed_steps", "started_at", "updated_at", "error",
      ];
      const progress = snapshot?.progress && typeof snapshot.progress === "object" ? snapshot.progress : {};
      const rows = [
        ...progressRowsForSource("Pipeline", progress, pipelinePreferred),
        ...progressRowsForSource("Audit", snapshot?.audit_progress, auditPreferred),
      ];
      if (progress.AudioProgress && typeof progress.AudioProgress === "object") {
        rows.push({ source: "Pipeline", field: "AudioProgress summary", value: audioProgressLine(progress.AudioProgress) });
      }
      if (progress.PendingDrainProgress && typeof progress.PendingDrainProgress === "object") {
        rows.push({ source: "Pipeline", field: "PendingDrainProgress summary", value: pendingDrainProgressLine(progress.PendingDrainProgress) });
      }
      progressWorkerRows(snapshot, diagnostics).forEach((row) => {
        rows.push({ source: "Worker", field: row.worker_label || row.worker_id || "Local worker", value: formatWorkerProgressRow(row) });
        if (row.last_log_line) rows.push({ source: "Worker", field: "last_log_line", value: row.last_log_line });
      });
      progressFfmpegRows(snapshot, diagnostics).forEach((row) => {
        rows.push({ source: "FFmpeg", field: "latest", value: formatFfmpegProgressRow(row) });
        ["job_id", "frame", "fps", "time", "speed", "bitrate", "progress_source", "updated_at", "parse_error"].forEach((field) => {
          const value = row[field];
          if (value !== undefined && value !== null && value !== "") rows.push({ source: "FFmpeg", field, value });
        });
        if (row.last_log_line) rows.push({ source: "FFmpeg", field: "last_log_line", value: row.last_log_line });
      });
      progressEtaRows(snapshot, diagnostics).forEach((row) => {
        rows.push({ source: "ETA", field: row.worker_label || row.worker_id || "estimate", value: formatEtaRow(row) });
        ["job_id", "eta_seconds", "confidence", "basis", "bytes_per_second", "bytes_remaining", "bytes_copied", "bytes_total", "updated_at", "unavailable_reason"].forEach((field) => {
          const value = row[field];
          if (value !== undefined && value !== null && value !== "") rows.push({ source: "ETA", field, value });
        });
      });
      return rows;
    }

    function diagnosticsProgressStatus(snapshot, rows) {
      if (!snapshot) return "No snapshot";
      if (/stale progress/i.test(String(snapshot.activity || ""))) return "Stale progress review";
      const progress = snapshot.progress && typeof snapshot.progress === "object" ? snapshot.progress : {};
      const auditProgress = snapshot.audit_progress && typeof snapshot.audit_progress === "object" ? snapshot.audit_progress : {};
      const pipelineState = String(snapshot.pipeline_state || progress.Status || "").toLowerCase();
      const auditState = String(auditProgress.status || auditProgress.Status || "").toLowerCase();
      if (pipelineState && /processing|running|active|publishing/.test(pipelineState)) return "Pipeline active";
      if (auditProgressIsStaleForUi(snapshot)) return "Audit stale";
      if (auditState && /running|active|processing|scanning/.test(auditState)) return "Audit active";
      return rows.length ? "Progress loaded" : "No progress";
    }

    function diagnosticsProgressSummaryLines(snapshot, rows, diagnostics = null) {
      if (!snapshot) {
        return [
          "Snapshot: unavailable",
          "Next step: refresh the WebView or open Diagnostics > Run Logs if close-readiness is blocked.",
        ];
      }
      const progress = snapshot.progress && typeof snapshot.progress === "object" ? snapshot.progress : {};
      const auditProgress = snapshot.audit_progress && typeof snapshot.audit_progress === "object" ? snapshot.audit_progress : {};
      const staleProgress = /stale progress/i.test(String(snapshot.activity || ""));
      const lines = [
        `Pipeline state: ${snapshot.pipeline_state || progress.Status || "unknown"}`,
        activeWorkProgressLine(progress) || "Pipeline progress: no active progress fields reported.",
        activeWorkRouteLine(progress),
        activeWorkQueueLine(progress),
        activeWorkControlLine(progress),
        progressWorkerSummaryLine(snapshot, diagnostics),
        progressFfmpegSummaryLine(snapshot, diagnostics),
        progressEtaSummaryLine(snapshot, diagnostics),
      ].filter(Boolean);
      if (staleProgress) {
        lines.push(
          "",
          "Stale progress warning:",
          "Runtime progress looks older than the current backend state. Treat Progress as context only until Close Readiness, ActiveJobs, Run Logs, and Last Stderr agree.",
          "Safe next step: read ActiveJobs and bounded logs before clearing state, closing the app, rerunning, or starting new work.",
        );
      }
      if (Object.keys(auditProgress).length) {
        lines.push(
          "",
          `Audit status: ${formatProgressValue(auditProgress.status || auditProgress.Status || "unknown")}`,
          auditProgress.current_operation ? `Audit operation: ${formatProgressValue(auditProgress.current_operation)}` : "",
          auditProgress.current_file ? `Audit file: ${formatProgressValue(auditProgress.current_file)}` : "",
          auditProgress.percent_complete !== undefined ? `Audit percent: ${formatProgressValue(auditProgress.percent_complete)}` : "",
        );
      }
      lines.push(
        "",
        `Structured fields: ${rows.length}`,
        "Next step: compare Runtime Progress with Worker Progress, Close Readiness, and ActiveJobs before closing the app or clearing runtime state.",
        "Mutation guardrail: this table is read-only; progress files are still backend/runtime-owned.",
      );
      return lines.filter((line) => line !== "");
    }

    function renderDiagnosticsProgress(snapshot = null, diagnostics = null) {
      const rows = diagnosticsProgressRows(snapshot || {}, diagnostics);
      setText("diagnostics-progress-status", diagnosticsProgressStatus(snapshot, rows));
      renderProgressBarsInto(
        "diagnostics-progress-bars",
        [
          ...(Array.isArray(snapshot?.progress_bars) ? snapshot.progress_bars : []),
          ...(Array.isArray(progressWorkerPayload(snapshot, diagnostics).progress_bars) ? progressWorkerPayload(snapshot, diagnostics).progress_bars : []),
        ],
        snapshot,
        "No runtime progress bars loaded.",
      );
      const tbody = byId("diagnostics-progress-rows");
      if (tbody) {
        if (!rows.length) {
          clearRows(tbody, 3, "No runtime progress fields loaded.");
        } else {
          tbody.replaceChildren();
          rows.forEach((item) => {
            const row = document.createElement("tr");
            const source = String(item.source || "").toLowerCase();
            row.dataset.status = source === "audit" ? "warning" : "";
            appendCells(row, [item.source, item.field, formatProgressValue(item.value)]);
            tbody.appendChild(row);
          });
        }
      }
      setText("diagnostics-progress-detail", diagnosticsProgressSummaryLines(snapshot, rows, diagnostics).join("\n"));
    }

    return {
      diagnosticsProgressRows,
      diagnosticsProgressStatus,
      diagnosticsProgressSummaryLines,
      renderDiagnosticsProgress,
    };
  }

  window.__progressDiagnosticsModule = { createProgressDiagnosticsModule };
}());
