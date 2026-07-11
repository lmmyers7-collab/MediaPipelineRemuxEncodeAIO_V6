(function () {
  function createProgressFfmpegEtaModule(deps) {
    const { formatProgressValue, formatProgressByteRate, formatProgressBytes } = deps || {};
    const formatBytes = typeof formatProgressBytes === "function"
      ? formatProgressBytes
      : (value) => {
          const bytes = Number(value);
          if (!Number.isFinite(bytes) || bytes < 0) return "";
          const units = ["B", "KB", "MB", "GB", "TB"];
          let size = bytes;
          for (const unit of units) {
            if (size < 1024 || unit === units[units.length - 1]) {
              return unit === "B" ? `${Math.round(size)} ${unit}` : `${size.toFixed(1)} ${unit}`;
            }
            size /= 1024;
          }
          return `${Math.round(bytes)} B`;
        };
    const formatByteRate = typeof formatProgressByteRate === "function"
      ? formatProgressByteRate
      : (value) => {
          const text = formatBytes(value);
          return text ? `${text}/s` : "";
        };
    function progressFfmpegPayload(snapshot = null, diagnostics = null) { const fromSnapshot = snapshot?.ffmpeg_progress && typeof snapshot.ffmpeg_progress === "object" ? snapshot.ffmpeg_progress : null; const fromDiagnostics = diagnostics?.ffmpeg_progress && typeof diagnostics.ffmpeg_progress === "object" ? diagnostics.ffmpeg_progress : null; return fromDiagnostics || fromSnapshot || {}; }
    function progressFfmpegRows(snapshot = null, diagnostics = null) { const payload = progressFfmpegPayload(snapshot, diagnostics); return Array.isArray(payload.rows) ? payload.rows.filter(Boolean) : []; }
    function progressFfmpegSummaryLine(snapshot = null, diagnostics = null) { const payload = progressFfmpegPayload(snapshot, diagnostics); const rows = Array.isArray(payload.rows) ? payload.rows : []; return !payload.schema_version && !rows.length ? "FFmpeg progress proof: no backend FFmpeg-progress contract loaded." : `FFmpeg progress proof: ${payload.status || "unknown"}; rows=${rows.length}; parsed=${payload.parsed_count || 0}; parse_errors=${payload.parse_error_count || 0}.`; }
    function formatFfmpegProgressRow(row) { return [row.job_id ? `job=${formatProgressValue(row.job_id)}` : "", row.stage ? `stage=${formatProgressValue(row.stage)}` : "", row.source ? `file=${formatProgressValue(row.source)}` : "", row.frame !== undefined && row.frame !== null ? `frame=${formatProgressValue(row.frame)}` : "", row.fps !== undefined && row.fps !== null ? `fps=${formatProgressValue(row.fps)}` : "", row.time ? `time=${formatProgressValue(row.time)}` : "", row.speed ? `speed=${formatProgressValue(row.speed)}` : "", row.bitrate ? `bitrate=${formatProgressValue(row.bitrate)}` : "", row.parse_error ? `parse_error=${formatProgressValue(row.parse_error)}` : ""].filter(Boolean).join("; ") || "No FFmpeg key/value progress fields parsed."; }
    function progressEtaPayload(snapshot = null, diagnostics = null) { const fromSnapshot = snapshot?.eta && typeof snapshot.eta === "object" ? snapshot.eta : null; const fromDiagnostics = diagnostics?.eta && typeof diagnostics.eta === "object" ? diagnostics.eta : null; return fromDiagnostics || fromSnapshot || {}; }
    function progressEtaRows(snapshot = null, diagnostics = null) { const payload = progressEtaPayload(snapshot, diagnostics); return Array.isArray(payload.rows) ? payload.rows.filter(Boolean) : []; }
    function formatEtaSeconds(value) { const seconds = Number(value); if (!Number.isFinite(seconds) || seconds < 0) return "not available"; const rounded = Math.round(seconds); const hours = Math.floor(rounded / 3600); const minutes = Math.floor((rounded % 3600) / 60); const remainingSeconds = rounded % 60; if (hours > 0) return `${hours}h ${String(minutes).padStart(2, "0")}m`; if (minutes > 0) return `${minutes}m ${String(remainingSeconds).padStart(2, "0")}s`; return `${remainingSeconds}s`; }
    function progressEtaSummaryLine(snapshot = null, diagnostics = null) { const payload = progressEtaPayload(snapshot, diagnostics); const rows = Array.isArray(payload.rows) ? payload.rows : []; if (!payload.schema_version && !rows.length) return "ETA: no backend ETA contract loaded."; const estimate = rows.find((row) => row && row.eta_seconds !== undefined && row.eta_seconds !== null); const estimateText = estimate ? `; next=${formatEtaSeconds(estimate.eta_seconds)}; confidence=${estimate.confidence || "unknown"}` : ""; return `ETA: ${payload.status || "unknown"}; rows=${rows.length}; estimated=${payload.estimated_count || 0}; unavailable=${payload.unavailable_count || 0}${estimateText}.`; }
    function formatEtaRow(row) { return [row.job_id ? `job=${formatProgressValue(row.job_id)}` : "", row.stage ? `stage=${formatProgressValue(row.stage)}` : "", row.source ? `file=${formatProgressValue(row.source)}` : "", row.eta_seconds !== undefined && row.eta_seconds !== null ? `eta=${formatEtaSeconds(row.eta_seconds)}` : "", row.confidence ? `confidence=${formatProgressValue(row.confidence)}` : "", row.percent !== undefined && row.percent !== null ? `percent=${formatProgressValue(row.percent)}` : "", row.elapsed_seconds !== undefined && row.elapsed_seconds !== null ? `elapsed=${formatEtaSeconds(row.elapsed_seconds)}` : "", row.bytes_per_second !== undefined && row.bytes_per_second !== null ? `rate=${formatByteRate(row.bytes_per_second)}` : "", row.bytes_remaining !== undefined && row.bytes_remaining !== null ? `remaining=${formatBytes(row.bytes_remaining)}` : "", row.unavailable_reason ? `unavailable=${formatProgressValue(row.unavailable_reason)}` : ""].filter(Boolean).join("; ") || "No ETA row details available."; }
    return { progressFfmpegPayload, progressFfmpegRows, progressFfmpegSummaryLine, formatFfmpegProgressRow, progressEtaPayload, progressEtaRows, formatEtaSeconds, progressEtaSummaryLine, formatEtaRow };
  }
  window.__progressFfmpegEtaModule = { createProgressFfmpegEtaModule };
}());
