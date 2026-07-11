(function () {
  function createProgressAuditModule({
    formatProgressValue,
    progressBarStatusLabel,
    renderProgressBarsInto,
    setText,
  } = {}) {
    const AUDIT_PROGRESS_ACTIVE_FRESH_MS = 10 * 60 * 1000;
      function auditProgressPayload(snapshot = {}) {
        return snapshot?.audit_progress && typeof snapshot.audit_progress === "object" ? snapshot.audit_progress : {};
      }

      function rawAuditProgressBars(snapshot = {}) {
        const bars = Array.isArray(snapshot?.progress_bars) ? snapshot.progress_bars : [];
        return bars.filter((bar) => {
          const id = String(bar?.id || "").toLowerCase();
          const source = String(bar?.source || "").toLowerCase();
          return id === "audit_progress" || id === "audit_reports" || source.includes("audit_progress");
        });
      }

      function parseAuditProgressTimestamp(value) {
        if (!value) return 0;
        const timestamp = Date.parse(String(value));
        return Number.isFinite(timestamp) ? timestamp : 0;
      }

      function auditProgressSnapshotTimestampMs(snapshot = {}, bars = rawAuditProgressBars(snapshot)) {
        const auditProgress = auditProgressPayload(snapshot);
        const timestamps = [
          auditProgress.started_at,
          auditProgress.StartedAt,
          auditProgress.last_update,
          auditProgress.LastUpdate,
          auditProgress.updated_at,
          auditProgress.UpdatedAt,
          ...(Array.isArray(bars) ? bars.map((bar) => bar?.updated_at) : []),
        ].map(parseAuditProgressTimestamp).filter((value) => value > 0);
        return timestamps.length ? Math.max(...timestamps) : 0;
      }

      function auditProgressActiveState(snapshot = {}, bars = rawAuditProgressBars(snapshot)) {
        const auditProgress = auditProgressPayload(snapshot);
        if (auditProgress.completed === true || auditProgress.failed === true) return false;
        const status = String(auditProgress.status || auditProgress.Status || "").toLowerCase();
        if (["completed", "complete", "failed", "error", "blocked", "stopped", "idle"].includes(status)) return false;
        if (["starting", "scanning", "writing-reports", "running", "active", "audit", "auditing"].includes(status)) return true;
        return (Array.isArray(bars) ? bars : []).some((bar) => ["active", "running", "warning"].includes(String(bar?.status || "").toLowerCase()));
      }

      function auditProgressIsStaleForUi(snapshot = {}, bars = rawAuditProgressBars(snapshot)) {
        if (!auditProgressActiveState(snapshot, bars)) return false;
        const timestamp = auditProgressSnapshotTimestampMs(snapshot, bars);
        return Boolean(timestamp && Date.now() - timestamp > AUDIT_PROGRESS_ACTIVE_FRESH_MS);
      }

      function auditProgressBars(snapshot = {}) {
        const bars = rawAuditProgressBars(snapshot);
        if (!auditProgressIsStaleForUi(snapshot, bars)) return bars;
        return bars.map((bar) => {
          const status = String(bar?.status || "").toLowerCase();
          return {
            ...bar,
            status: ["active", "running"].includes(status) ? "warning" : bar.status,
            stale: true,
          };
        });
      }

      function auditProgressStatus(snapshot = {}, bars = auditProgressBars(snapshot)) {
        if (!snapshot) return "No snapshot";
        const auditProgress = auditProgressPayload(snapshot);
        const statuses = Array.isArray(bars) ? bars.map((bar) => String(bar?.status || "").toLowerCase()) : [];
        if (auditProgressIsStaleForUi(snapshot)) return "Audit stale";
        if (statuses.some((status) => status === "blocked")) return "Audit blocked";
        if (statuses.some((status) => status === "active")) return "Audit active";
        if (statuses.length && statuses.every((status) => status === "complete")) return "Audit complete";
        if (statuses.length) return "Audit progress loaded";
        return Object.keys(auditProgress).length ? "Audit fields loaded" : "No audit progress";
      }

      function auditProgressSummaryLines(snapshot = {}, bars = auditProgressBars(snapshot)) {
        const auditProgress = auditProgressPayload(snapshot);
        if (!Object.keys(auditProgress).length && (!Array.isArray(bars) || !bars.length)) {
          return [
            "Audit progress: no audit progress object is loaded.",
            "Next step: start Audit from Launch or refresh after an audit process has created audit_progress.json.",
            "Mutation guardrail: this view is read-only and cannot start, rerun, export, repair, or edit report files.",
          ];
        }
        const processed = auditProgress.processed_files ?? auditProgress.ProcessedFiles ?? "";
        const total = auditProgress.total_files ?? auditProgress.TotalFiles ?? "";
        const percent = auditProgress.percent_complete ?? auditProgress.PercentComplete ?? "";
        const reportIndex = auditProgress.report_step_index ?? auditProgress.ReportStepIndex ?? "";
        const reportTotal = auditProgress.report_step_total ?? auditProgress.ReportStepTotal ?? "";
        const reportStage = auditProgress.report_stage ?? auditProgress.ReportStage ?? "";
        const completedSteps = Array.isArray(auditProgress.report_completed_steps)
          ? auditProgress.report_completed_steps
          : Array.isArray(auditProgress.ReportCompletedSteps) ? auditProgress.ReportCompletedSteps : [];
        const lines = [
          `Audit status: ${formatProgressValue(auditProgress.status || auditProgress.Status || "unknown")}`,
          `Audit scan: ${processed !== "" && total !== "" ? `${processed} / ${total}` : "no scan count"}${percent !== "" ? ` (${percent}%)` : ""}`,
          auditProgress.current_operation ? `Current operation: ${formatProgressValue(auditProgress.current_operation)}` : "",
          reportTotal !== "" && Number(reportTotal) > 0
            ? `Report generation: ${reportIndex || 0} / ${reportTotal}${reportStage ? ` (${String(reportStage).replaceAll("_", " ")})` : ""}`
            : "Report generation: no stepped report progress loaded.",
          completedSteps.length ? `Completed report steps: ${completedSteps.map((step) => String(step).replaceAll("_", " ")).join(", ")}` : "",
          bars.length ? `Progress bars: ${bars.map((bar) => `${bar.label || bar.id}: ${progressBarStatusLabel(bar)}`).join(" | ")}` : "Progress bars: none emitted.",
        ].filter(Boolean);
        if (auditProgressIsStaleForUi(snapshot, bars)) {
          lines.push("Audit health: stale progress only; refresh or check ActiveJobs before treating it as active work.");
        }
        const written = [
          auditProgress.latest_json_path ? "JSON" : "",
          auditProgress.latest_csv_path ? "CSV" : "",
          auditProgress.latest_priority_csv_path ? "Priority CSV" : "",
          auditProgress.latest_text_path ? "Text" : "",
        ].filter(Boolean);
        if (written.length) lines.push(`Written reports: ${written.join(", ")}`);
        lines.push("Mutation guardrail: audit progress is runtime/report evidence only; report writing and launch remain backend-owned.");
        return lines;
      }

      function renderAuditProgressInto({ containerId, statusId, summaryId, snapshot = null, emptyText = "" } = {}) {
        const bars = auditProgressBars(snapshot || {});
        renderProgressBarsInto(containerId, bars, snapshot, emptyText || "No audit progress bars loaded.");
        if (statusId) setText(statusId, auditProgressStatus(snapshot || {}, bars));
        if (summaryId) setText(summaryId, auditProgressSummaryLines(snapshot || {}, bars).join("\n"));
      }

    return {
      auditProgressPayload,
      rawAuditProgressBars,
      auditProgressIsStaleForUi,
      auditProgressBars,
      auditProgressStatus,
      auditProgressSummaryLines,
      renderAuditProgressInto,
    };
  }

  window.__progressAuditModule = { createProgressAuditModule };
})();

