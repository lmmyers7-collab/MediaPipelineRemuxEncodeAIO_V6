(function () {
  function createProgressWorkerModule(deps) {
    const formatProgressValue = deps?.formatProgressValue || ((value) => String(value ?? ""));
    function progressWorkerPayload(snapshot = null, diagnostics = null) {
      const fromSnapshot = snapshot?.worker_progress && typeof snapshot.worker_progress === "object" ? snapshot.worker_progress : null;
      const fromDiagnostics = diagnostics?.worker_progress && typeof diagnostics.worker_progress === "object" ? diagnostics.worker_progress : null;
      return fromDiagnostics || fromSnapshot || {};
    }
    function progressWorkerRows(snapshot = null, diagnostics = null) { const payload = progressWorkerPayload(snapshot, diagnostics); return Array.isArray(payload.rows) ? payload.rows.filter(Boolean) : []; }
    function progressWorkerSummaryLine(snapshot = null, diagnostics = null) { const payload = progressWorkerPayload(snapshot, diagnostics); const rows = Array.isArray(payload.rows) ? payload.rows : []; return !payload.schema_version && !rows.length ? "Worker progress: no backend worker-progress contract loaded." : `Worker progress: ${payload.status || "unknown"}; rows=${rows.length}; running=${payload.active_count || 0}; blocked=${payload.blocked_count || 0}; warning=${payload.warning_count || 0}.`; }
    function formatWorkerProgressRow(row) { return [row.worker_label || row.worker_id || "Local worker", row.stage ? `stage=${formatProgressValue(row.stage)}` : "", row.percent !== undefined && row.percent !== null ? `percent=${formatProgressValue(row.percent)}` : "", row.source ? `file=${formatProgressValue(row.source)}` : "", row.last_log_line ? `last=${formatProgressValue(row.last_log_line)}` : ""].filter(Boolean).join("; "); }
    return { progressWorkerPayload, progressWorkerRows, progressWorkerSummaryLine, formatWorkerProgressRow };
  }
  window.__progressWorkerModule = { createProgressWorkerModule };
}());
