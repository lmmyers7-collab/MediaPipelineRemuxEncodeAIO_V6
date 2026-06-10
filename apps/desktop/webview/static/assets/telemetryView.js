(function () {
  const telemetryHistory = {
    cpu: [],
    gpu: [],
    ram: [],
  };
  const TELEMETRY_REFRESH_SECONDS = 4;
  const TELEMETRY_HISTORY_SECONDS = 120 * TELEMETRY_REFRESH_SECONDS;

  function pushTelemetryHistory(name, value) {
    const list = telemetryHistory[name];
    const prior = list.length ? list[list.length - 1] : 0;
    const numeric = value === null || value === undefined ? prior : Number(value);
    const next = Number.isFinite(numeric) ? Math.max(0, Math.min(100, numeric)) : prior;
    list.push(next);
    while (list.length > 120) list.shift();
  }

  function telemetryCssToken(name, fallback) {
    try {
      const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
      return value || fallback;
    } catch (_) {
      return fallback;
    }
  }

  function telemetryCanvasColors() {
    const isLight = document.body.classList.contains("light-mode");
    return {
      background: telemetryCssToken(isLight ? "--grey-100" : "--grey-800", "Canvas"),
      grid: telemetryCssToken(isLight ? "--grey-300" : "--grey-700", "currentColor"),
      baseline: telemetryCssToken(isLight ? "--grey-500" : "--grey-400", "currentColor"),
      label: telemetryCssToken(isLight ? "--grey-600" : "--grey-300", "currentColor"),
      cpu: telemetryCssToken("--blue-400", "currentColor"),
      gpu: telemetryCssToken("--green-500", "currentColor"),
      ram: telemetryCssToken("--amber-500", "currentColor"),
    };
  }

  function drawTelemetryChart(id, values, color) {
    const canvas = byId(id);
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    const width = canvas.width;
    const height = canvas.height;
    const colors = telemetryCanvasColors();
    ctx.clearRect(0, 0, width, height);
    ctx.fillStyle = colors.background;
    ctx.fillRect(0, 0, width, height);
    ctx.strokeStyle = colors.grid;
    ctx.lineWidth = 1;
    for (let i = 1; i < 4; i += 1) {
      const y = (height / 4) * i;
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(width, y);
      ctx.stroke();
    }
    if (!values.length) {
      ctx.fillStyle = colors.label;
      ctx.font = "12px sans-serif";
      ctx.fillText("waiting for sample", 12, height - 12);
      return;
    }
    ctx.strokeStyle = colors.baseline;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(0, height - 2);
    ctx.lineTo(width, height - 2);
    ctx.stroke();
    const step = values.length > 1 ? width / (values.length - 1) : width;
    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.beginPath();
    values.forEach((value, index) => {
      const x = index * step;
      const y = Math.max(2, Math.min(height - 2, height - (value / 100) * height));
      if (index === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.stroke();
    if (values.length === 1) {
      const y = Math.max(2, Math.min(height - 2, height - (values[0] / 100) * height));
      ctx.fillStyle = color;
      ctx.beginPath();
      ctx.arc(8, y, 3, 0, Math.PI * 2);
      ctx.fill();
    }
  }

  function formatGpuEncoderPercent(value) {
    return formatPercent(value);
  }

  function formatTelemetryNumber(value, digits = 0) {
    const numeric = Number(value);
    if (!Number.isFinite(numeric)) return "unavailable";
    return numeric.toFixed(digits);
  }

  function telemetryGpuNote(telemetry) {
    const details = [];
    if (!telemetryGpuPresent(telemetry)) {
      details.push("GPU video encoder telemetry unavailable. CPU/RAM data is still usable.");
    } else {
      details.push("GPU video encoder telemetry available.");
    }
    if (telemetry.gpu_name) details.push(`Device: ${telemetry.gpu_name}`);
    if (telemetry.source) details.push(`Source: ${telemetry.source}`);
    if (telemetry.error) details.push(`Telemetry warning: ${telemetry.error}`);
    const rows = Array.isArray(telemetry.gpu_rows) ? telemetry.gpu_rows : [];
    if (rows.length > 1) {
      details.push(rows.map((row) => `GPU ${row.index}: ${formatGpuEncoderPercent(row.encoder_percent)}`).join(", "));
    } else if (rows.length === 1) {
      details.push(`GPU ${rows[0].index ?? 0}: ${formatGpuEncoderPercent(rows[0].encoder_percent)}`);
    }
    return details.join(" | ");
  }

  function telemetryGpuUsagePayload(telemetry) {
    const payload = telemetry?.gpu_encoder_usage && typeof telemetry.gpu_encoder_usage === "object" ? telemetry.gpu_encoder_usage : {};
    if (payload.schema_version) return payload;
    return {
      schema_version: "desktop_gpu_encoder_usage.v1",
      status: telemetryGpuPresent(telemetry) ? "loaded" : "unavailable",
      row_count: Array.isArray(telemetry?.gpu_rows) ? telemetry.gpu_rows.length : 0,
      active_encoder_count: telemetryHasNumber(telemetry?.gpu_encoder_percent) && Number(telemetry.gpu_encoder_percent) > 0 ? 1 : 0,
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

  function telemetryGpuUsageDetailLines(telemetry) {
    const payload = telemetryGpuUsagePayload(telemetry);
    const rows = Array.isArray(payload.rows) ? payload.rows : [];
    const lines = [
      `Contract: ${payload.schema_version || "desktop_gpu_encoder_usage.v1"}`,
      telemetryGpuUsageSummaryLine(telemetry),
    ];
    rows.slice(0, 4).forEach((row) => {
      const memory = row.memory_used_mb !== undefined && row.memory_used_mb !== null
        ? `${formatTelemetryNumber(row.memory_used_mb, 0)} MB${row.memory_total_mb !== undefined && row.memory_total_mb !== null ? ` / ${formatTelemetryNumber(row.memory_total_mb, 0)} MB` : ""}`
        : "memory not reported";
      lines.push(`${row.adapter || "GPU"}${row.adapter_index ? ` (${row.adapter_index})` : ""}: encoder=${formatGpuEncoderPercent(row.utilization_percent)}; sessions=${row.encoder_sessions ?? "not reported"}; ${memory}`);
    });
    if (!rows.length) lines.push("No GPU/NVENC usage rows were reported by the backend.");
    if (Array.isArray(payload.summary_lines)) {
      const sessionLine = payload.summary_lines.find((line) => String(line || "").includes("Encoder sessions"));
      if (sessionLine) lines.push(sessionLine);
    }
    lines.push("Mutation guardrail: GPU/NVENC telemetry is read-only and cannot start, stop, retry, or tune encoder work.");
    return lines;
  }

  function parseTelemetrySampleTime(telemetry) {
    const raw = telemetry?.sampled_at || telemetry?.collected_at || telemetry?.timestamp || "";
    if (!raw) return null;
    const parsed = new Date(raw);
    return Number.isNaN(parsed.getTime()) ? null : parsed;
  }

  function telemetrySampleAgeSeconds(telemetry) {
    const parsed = parseTelemetrySampleTime(telemetry);
    if (!parsed) return null;
    return Math.max(0, Math.round((Date.now() - parsed.getTime()) / 1000));
  }

  function formatTelemetryAge(seconds) {
    if (seconds === null || seconds === undefined) return "unknown";
    if (seconds < 60) return `${seconds}s`;
    const minutes = Math.floor(seconds / 60);
    const remainder = seconds % 60;
    if (minutes < 60) return `${minutes}m ${remainder}s`;
    const hours = Math.floor(minutes / 60);
    return `${hours}h ${minutes % 60}m`;
  }

  function telemetryHasNumber(value) {
    if (value === null || value === undefined) return false;
    if (typeof value === "string" && value.trim() === "") return false;
    return Number.isFinite(Number(value));
  }

  function telemetryPercentNumber(value) {
    if (!telemetryHasNumber(value)) return null;
    return Math.max(0, Math.min(100, Number(value)));
  }

  function cpuUtilityNoteText(telemetry) {
    const util = telemetryPercentNumber(telemetry?.cpu_utility_percent);
    if (util === null) return "Task Manager-equivalent (% Utility): unavailable";
    return `Task Manager-equivalent (% Utility): ${formatPercent(util)}`;
  }

  function telemetryGpuPresent(telemetry) {
    const rows = Array.isArray(telemetry?.gpu_rows) ? telemetry.gpu_rows : [];
    return Boolean(
      telemetry?.gpu_present ||
      rows.length ||
      telemetryHasNumber(telemetry?.gpu_encoder_percent) ||
      String(telemetry?.gpu_name || "").trim()
    );
  }

  function telemetryHasUsefulValues(telemetry) {
    return Boolean(
      telemetryHasNumber(telemetry?.cpu_percent)
      || telemetryHasNumber(telemetry?.memory_percent)
      || telemetryGpuPresent(telemetry)
    );
  }

  function telemetryActiveWork(snapshot) {
    if (!snapshot || typeof snapshot !== "object") return false;
    if (snapshot.active_work === true) return true;
    const state = String(snapshot.pipeline_state || snapshot.state || snapshot.status || "").trim().toLowerCase();
    if (["running", "processing", "encoding", "remuxing", "copying", "publishing", "active", "audit", "auditing", "starting", "stopping"].includes(state)) {
      return true;
    }
    if (["idle", "stopped", "complete", "completed", "ready", "safe"].includes(state)) return false;
    const progress = snapshot.progress && typeof snapshot.progress === "object" ? snapshot.progress : {};
    const progressStatus = String(progress.Status || progress.status || progress.CurrentStage || "").trim().toLowerCase();
    if (["running", "processing", "encoding", "remuxing", "copying", "publishing", "audit", "auditing"].some((token) => progressStatus.includes(token))) {
      return true;
    }
    const currentWork = snapshot.current_work && typeof snapshot.current_work === "object" ? snapshot.current_work : {};
    return [
      currentWork.item_label,
      currentWork.source_path,
      currentWork.phase_label,
      currentWork.route_label,
      progress.CurrentDisplayName,
      progress.CurrentFileDisplay,
      progress.CleanDisplayName,
    ].some((value) => String(value || "").trim());
  }

  function telemetryOperatingState(telemetry, options = {}) {
    const payload = telemetry && typeof telemetry === "object" ? telemetry : {};
    const snapshot = options && typeof options === "object" ? options.snapshot : null;
    const age = telemetrySampleAgeSeconds(payload);
    const cpu = telemetryPercentNumber(payload.cpu_percent);
    const ram = telemetryPercentNumber(payload.memory_percent);
    const encoder = telemetryPercentNumber(payload.gpu_encoder_percent);
    const gpuPresent = telemetryGpuPresent(payload);
    const active = telemetryActiveWork(snapshot);
    const hasUsefulValues = telemetryHasUsefulValues(payload);
    const base = (key, label, state, nextStep) => ({ key, label, state, nextStep, active, age });
    if (payload.error) {
      return base(
        "degraded",
        "Telemetry degraded",
        "blocked",
        "Telemetry is degraded. If hardware encoding is expected, inspect Maintenance GPU tools, Diagnostics nvidia-smi, and Video settings."
      );
    }
    if (age !== null && age > 60) {
      return base(
        "stale",
        "Telemetry stale",
        "warning",
        "Telemetry sample is stale. Check whether the backend sampler is running before trusting graph values."
      );
    }
    if (!hasUsefulValues) {
      return base(
        "waiting",
        "Waiting for telemetry",
        "loading",
        "Waiting for the first hardware telemetry sample. Refresh or open Diagnostics if telemetry remains empty."
      );
    }
    if (ram !== null && ram >= 85) {
      return base(
        "memory-pressure",
        "Memory pressure",
        "warning",
        "RAM pressure is high. Inspect active jobs and close unrelated apps before starting more work."
      );
    }
    if (active && encoder !== null && encoder >= 80) {
      return base(
        "gpu-bound",
        "GPU-bound encode",
        "changed",
        "The GPU video encoder is the likely bottleneck. Inspect encode progress and GPU Details if throughput is lower than expected."
      );
    }
    if (active && cpu !== null && cpu >= 85 && (encoder === null || encoder < 20)) {
      return base(
        "cpu-bound",
        "CPU-bound encode",
        "warning",
        "CPU is likely limiting the current job. Inspect the active job stage and whether this encode is using CPU fallback."
      );
    }
    if (!active && cpu !== null && cpu < 20 && (ram === null || ram < 80) && (encoder === null || encoder === 0)) {
      return base(
        "idle",
        "Idle",
        "empty",
        "No active work is reported; hardware usage looks idle."
      );
    }
    if (!gpuPresent && (cpu !== null || ram !== null)) {
      return base(
        "cpu-ram-only",
        "CPU/RAM only",
        "warning",
        "GPU video encoder telemetry is not available. CPU/RAM data is still usable. If hardware encoding is expected, inspect Maintenance GPU tools, Diagnostics nvidia-smi, and Video settings."
      );
    }
    return base(
      "normal",
      "Monitoring normal",
      "ok",
      "No CPU, GPU video encoder, or RAM pressure is obvious from the current sample."
    );
  }

  function telemetryReadinessStatus(telemetry, options = {}) {
    return telemetryOperatingState(telemetry, options).label;
  }

  function telemetryChartMetaText(telemetry) {
    const age = telemetrySampleAgeSeconds(telemetry);
    return `0-100% | Last ~${Math.round(TELEMETRY_HISTORY_SECONDS / 60)} min | Refreshes every ${TELEMETRY_REFRESH_SECONDS}s | Sample age ${formatTelemetryAge(age)}`;
  }

  function telemetryReadinessLines(telemetry, options = {}) {
    if (!telemetry || typeof telemetry !== "object") {
      return [
        "Payload: unavailable",
        "Next step: Refresh the page or open Diagnostics if telemetry remains unavailable.",
      ];
    }
    const operatingState = telemetryOperatingState(telemetry, options);
    const rows = Array.isArray(telemetry.gpu_rows) ? telemetry.gpu_rows : [];
    const age = telemetrySampleAgeSeconds(telemetry);
    const sampleTime = telemetry.sampled_at || telemetry.collected_at || telemetry.timestamp || "not reported";
    const gpuPresent = telemetryGpuPresent(telemetry);
    const lines = [
      `Operating state: ${operatingState.label}`,
      `Next step: ${operatingState.nextStep}`,
      "Payload: loaded",
      `Sample: ${sampleTime}`,
      `Age: ${formatTelemetryAge(age)}`,
      `Source: ${telemetry.source || "not reported"}`,
      `CPU: ${telemetryHasNumber(telemetry.cpu_percent) ? formatPercent(telemetry.cpu_percent) : "unavailable"}`,
      `CPU (Task Manager-equivalent, % Utility): ${telemetryHasNumber(telemetry.cpu_utility_percent) ? formatPercent(telemetry.cpu_utility_percent) : "unavailable"}`,
      `RAM: ${telemetryHasNumber(telemetry.memory_percent) ? formatPercent(telemetry.memory_percent) : "unavailable"}`,
      `GPU present: ${gpuPresent ? "yes" : "no"}`,
      `Video encoder (NVENC): ${gpuPresent ? formatGpuEncoderPercent(telemetry.gpu_encoder_percent) : "unavailable"}`,
      `GPU rows: ${rows.length}`,
      ...telemetryGpuUsageDetailLines(telemetry),
    ];
    if (telemetry.error) lines.push(`Warning: ${telemetry.error}`);
    return lines;
  }

  function setTelemetryTextState(id, text, state) {
    if (typeof setTextState === "function") {
      setTextState(id, text, state);
      return;
    }
    setText(id, text);
    const node = byId(id);
    if (node) node.dataset.state = state || "";
  }

  function setTelemetryDatasetState(id, state) {
    const node = byId(id);
    if (node) node.dataset.state = state || "";
  }

  function renderTelemetryReadiness(telemetry, options = {}) {
    const operatingState = telemetryOperatingState(telemetry, options);
    setTelemetryTextState("telemetry-readiness-status", operatingState.label, operatingState.state);
    setText("telemetry-operator-state-label", operatingState.label);
    setText("telemetry-operator-next-step", operatingState.nextStep);
    setTelemetryDatasetState("telemetry-operator-state", operatingState.key);
    setText("telemetry-readiness-summary", telemetryReadinessLines(telemetry, options).join("\n"));
  }

  function telemetryKpiGpuStatus(telemetry) {
    if (telemetry?.error) return "Degraded";
    const age = telemetrySampleAgeSeconds(telemetry);
    if (age !== null && age > 60) return "Stale";
    if (telemetryGpuPresent(telemetry)) return "Available";
    if (telemetryHasNumber(telemetry?.cpu_percent) || telemetryHasNumber(telemetry?.memory_percent)) return "Not available";
    return "Waiting";
  }

  function renderTelemetryKpis(telemetry) {
    setText("telemetry-kpi-cpu-value", telemetryHasNumber(telemetry?.cpu_percent) ? formatPercent(telemetry.cpu_percent) : "Unavailable");
    setText("telemetry-kpi-encoder-value", telemetryGpuPresent(telemetry) ? formatGpuEncoderPercent(telemetry?.gpu_encoder_percent) : "Unavailable");
    setText("telemetry-kpi-ram-value", telemetryHasNumber(telemetry?.memory_percent) ? formatPercent(telemetry.memory_percent) : "Unavailable");
    setText("telemetry-kpi-gpu-status", telemetryKpiGpuStatus(telemetry));
  }

  function renderTelemetryChartMetadata(telemetry) {
    const text = telemetryChartMetaText(telemetry);
    setText("cpu-chart-meta", text);
    setText("gpu-chart-meta", text);
    setText("ram-chart-meta", text);
  }

  function renderTelemetry(telemetry, options = {}) {
    telemetry = telemetry && typeof telemetry === "object" ? telemetry : {};
    const cpu = telemetry.cpu_percent;
    const gpu = telemetry.gpu_encoder_percent;
    const ram = telemetry.memory_percent;
    pushTelemetryHistory("cpu", cpu);
    pushTelemetryHistory("gpu", gpu);
    pushTelemetryHistory("ram", ram);
    setText("cpu-value", formatPercent(cpu));
    setText("cpu-utility-note", cpuUtilityNoteText(telemetry));
    setText("gpu-value", telemetryGpuPresent(telemetry) ? formatGpuEncoderPercent(gpu) : "Unavailable");
    setText("ram-value", formatPercent(ram));
    setText("gpu-note", telemetryGpuNote(telemetry));
    renderTelemetryKpis(telemetry);
    renderTelemetryChartMetadata(telemetry);
    const colors = telemetryCanvasColors();
    drawTelemetryChart("cpu-chart", telemetryHistory.cpu, colors.cpu);
    drawTelemetryChart("gpu-chart", telemetryHistory.gpu, colors.gpu);
    drawTelemetryChart("ram-chart", telemetryHistory.ram, colors.ram);
    renderGpuRows(telemetry);
    renderTelemetryReadiness(telemetry, options);
  }

  function renderGpuRows(telemetry) {
    const rows = telemetryVisibleGpuRows(telemetry);
    setText("gpu-detail-status", rows.length ? `${rows.length} GPU row${rows.length === 1 ? "" : "s"}` : "No GPU rows");
    const tbody = byId("gpu-rows");
    if (!tbody) return;
    if (!rows.length) {
      clearRows(tbody, 5, telemetryGpuPresent(telemetry) ? "GPU telemetry source returned no per-device rows." : "No GPU telemetry loaded.");
      return;
    }
    tbody.replaceChildren();
    rows.forEach((item) => {
      const row = document.createElement("tr");
      appendCells(row, [
        item.index || "",
        item.name || "",
        formatGpuEncoderPercent(item.encoder_percent),
        formatPercent(item.gpu_percent ?? item.encoder_percent),
        formatMemoryMb(item.memory_used_mb, item.memory_total_mb),
      ], ["num", null, "num", "num", "num"]);
      tbody.appendChild(row);
    });
  }

  function telemetryVisibleGpuRows(telemetry) {
    const rows = Array.isArray(telemetry?.gpu_rows) ? telemetry.gpu_rows : [];
    if (rows.length) return rows;
    if (!telemetryGpuPresent(telemetry)) return [];
    const usedGb = telemetryHasNumber(telemetry?.gpu_memory_used_gb) ? Number(telemetry.gpu_memory_used_gb) : null;
    const totalGb = telemetryHasNumber(telemetry?.gpu_memory_total_gb) ? Number(telemetry.gpu_memory_total_gb) : null;
    return [{
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
      synthesized: true,
    }];
  }

  /**
   * Public namespace for the Telemetry page module.
   * Prefer this namespace from new code; flat window.* exports are transitional compatibility aliases when present.
   */
  window.mediaPipelineTelemetryView = {
    renderTelemetry,
    renderGpuRows,
    renderTelemetryReadiness,
    drawTelemetryChart,
    telemetryCssToken,
    telemetryCanvasColors,
    formatGpuEncoderPercent,
    telemetryGpuNote,
    cpuUtilityNoteText,
    telemetryVisibleGpuRows,
    telemetryGpuUsagePayload,
    telemetryGpuUsageSummaryLine,
    telemetryGpuUsageDetailLines,
    telemetryActiveWork,
    telemetryOperatingState,
    telemetryChartMetaText,
    telemetryReadinessStatus,
    telemetryReadinessLines,
  };
})();
