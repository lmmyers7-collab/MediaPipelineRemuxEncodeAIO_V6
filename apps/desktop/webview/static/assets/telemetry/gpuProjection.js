(function () {
  function createTelemetryGpuProjectionModule(deps = {}) {
    const telemetryHasNumber = typeof deps.telemetryHasNumber === "function" ? deps.telemetryHasNumber : () => false;
    const telemetryPercentNumber = typeof deps.telemetryPercentNumber === "function" ? deps.telemetryPercentNumber : () => null;

    function telemetryGpuPresent(telemetry) {
      const rows = Array.isArray(telemetry?.gpu_rows) ? telemetry.gpu_rows : [];
      const payloadRows = Array.isArray(telemetry?.gpu_encoder_usage?.rows) ? telemetry.gpu_encoder_usage.rows : [];
      const payloadStatus = String(telemetry?.gpu_encoder_usage?.status || "").toLowerCase();
      return Boolean(
        telemetry?.gpu_present
        || rows.length
        || payloadRows.length
        || ["loaded", "partial", "warning", "degraded"].includes(payloadStatus)
        || telemetryHasNumber(telemetry?.gpu_encoder_percent)
        || String(telemetry?.gpu_name || "").trim()
      );
    }

    function telemetryGpuUsagePayload(telemetry) {
      const payload = telemetry?.gpu_encoder_usage && typeof telemetry.gpu_encoder_usage === "object" ? telemetry.gpu_encoder_usage : {};
      if (payload.schema_version) return payload;
      const rows = Array.isArray(telemetry?.gpu_rows) ? telemetry.gpu_rows : [];
      return {
        schema_version: "desktop_gpu_encoder_usage.v1",
        status: telemetryGpuPresent(telemetry) ? "loaded" : "unavailable",
        row_count: rows.length,
        active_encoder_count: telemetryPercentNumber(telemetry?.gpu_encoder_percent) > 0 ? 1 : 0,
        missing_session_count: telemetryGpuPresent(telemetry) ? 1 : 0,
        rows: [],
        summary_lines: ["GPU/NVENC usage contract was not supplied by the backend."],
        read_only: true,
      };
    }

    function telemetryGpuUsageSummaryLine(telemetry) {
      const payload = telemetryGpuUsagePayload(telemetry);
      const rows = Array.isArray(payload.rows) ? payload.rows : [];
      return `GPU/NVENC usage: ${payload.status || "unknown"}; rows=${rows.length}; active_encoders=${payload.active_encoder_count || 0}; missing_session_counts=${payload.missing_session_count || 0}.`;
    }

    function normalizedGpuUsageRow(row = {}, fallback = {}) {
      return {
        index: row.adapter_index ?? row.index ?? fallback.index ?? "",
        name: row.adapter || row.name || fallback.name || "GPU",
        encoder_percent: row.utilization_percent ?? row.encoder_percent ?? row.gpu_encoder_percent ?? fallback.encoder_percent,
        gpu_percent: row.gpu_utilization_percent ?? row.gpu_percent ?? fallback.gpu_percent,
        memory_used_mb: row.memory_used_mb ?? fallback.memory_used_mb,
        memory_total_mb: row.memory_total_mb ?? fallback.memory_total_mb,
        memory_percent: row.memory_percent ?? fallback.memory_percent,
        temperature_c: row.temperature_c ?? row.temperature ?? fallback.temperature_c,
        encoder_sessions: row.encoder_sessions ?? fallback.encoder_sessions,
        sample_time: row.sample_time || row.sampled_at || fallback.sample_time,
        read_error: row.read_error || fallback.read_error,
        source: row.source || fallback.source,
        status: row.status || fallback.status,
        synthesized: Boolean(row.synthesized || fallback.synthesized),
      };
    }

    function telemetryGpuUsageRows(telemetry) {
      const payload = telemetryGpuUsagePayload(telemetry);
      const structuredRows = Array.isArray(payload.rows) ? payload.rows : [];
      if (structuredRows.length) {
        return structuredRows.map((row) => normalizedGpuUsageRow(row, {
          source: payload.source || telemetry?.source,
          status: payload.status,
        }));
      }
      const legacyRows = Array.isArray(telemetry?.gpu_rows) ? telemetry.gpu_rows : [];
      if (legacyRows.length) {
        return legacyRows.map((row) => normalizedGpuUsageRow(row, { source: telemetry?.source, status: payload.status }));
      }
      if (!telemetryGpuPresent(telemetry)) return [];
      const usedGb = telemetryHasNumber(telemetry?.gpu_memory_used_gb) ? Number(telemetry.gpu_memory_used_gb) : null;
      const totalGb = telemetryHasNumber(telemetry?.gpu_memory_total_gb) ? Number(telemetry.gpu_memory_total_gb) : null;
      return [normalizedGpuUsageRow({}, {
        index: telemetry?.gpu_index || "0",
        name: telemetry?.gpu_name || "GPU",
        encoder_percent: telemetry?.gpu_encoder_percent,
        gpu_percent: telemetry?.gpu_percent ?? telemetry?.gpu_encoder_percent,
        memory_used_mb: telemetryHasNumber(telemetry?.gpu_memory_used_mb)
          ? Number(telemetry.gpu_memory_used_mb)
          : (usedGb === null ? undefined : usedGb * 1024),
        memory_total_mb: telemetryHasNumber(telemetry?.gpu_memory_total_mb)
          ? Number(telemetry.gpu_memory_total_mb)
          : (totalGb === null ? undefined : totalGb * 1024),
        memory_percent: telemetry?.gpu_memory_percent,
        temperature_c: telemetry?.gpu_temperature_c,
        source: telemetry?.source,
        status: payload.status,
        synthesized: true,
      })];
    }

    return {
      telemetryGpuPresent,
      telemetryGpuUsagePayload,
      telemetryGpuUsageSummaryLine,
      normalizedGpuUsageRow,
      telemetryGpuUsageRows,
    };
  }

  window.__telemetryGpuProjectionModule = {
    createTelemetryGpuProjectionModule,
  };
})();
