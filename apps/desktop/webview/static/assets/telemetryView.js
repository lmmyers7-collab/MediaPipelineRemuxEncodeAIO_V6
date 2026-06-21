(function () {
  const telemetryHistory = {
    cpu: [],
    gpu: [],
    ram: [],
  };

  const DEFAULT_TELEMETRY_REFRESH_SECONDS = 15;
  const GPU_TELEMETRY_PROBE_SECONDS = 12;
  const TELEMETRY_HISTORY_SECONDS = 8 * 60;
  const TELEMETRY_STALE_SECONDS = 60;
  const TELEMETRY_FUTURE_SKEW_SECONDS = 5;
  const TELEMETRY_SOURCE_WARNING_TOKENS = ["fixture", "mock", "sample", "test"];

  let lastTelemetryContext = null;
  let lastTelemetryChartStates = {
    cpu: "loading",
    gpu: "loading",
    ram: "loading",
  };

  function telemetryHasNumber(value) {
    if (value === null || value === undefined) return false;
    if (typeof value === "string" && value.trim() === "") return false;
    return Number.isFinite(Number(value));
  }

  function telemetryPercentNumber(value) {
    if (!telemetryHasNumber(value)) return null;
    return Math.max(0, Math.min(100, Number(value)));
  }

  function telemetryRefreshSeconds(options = {}) {
    const rawMs = Number(options.refreshIntervalMs);
    if (Number.isFinite(rawMs) && rawMs > 0) return Math.max(1, Math.round(rawMs / 1000));
    const rawSeconds = Number(options.refreshSeconds);
    if (Number.isFinite(rawSeconds) && rawSeconds > 0) return Math.max(1, Math.round(rawSeconds));
    return DEFAULT_TELEMETRY_REFRESH_SECONDS;
  }

  function telemetryHistoryLimit(options = {}) {
    return Math.max(2, Math.round(TELEMETRY_HISTORY_SECONDS / telemetryRefreshSeconds(options)));
  }

  function pushTelemetryHistory(name, value, options = {}) {
    const list = telemetryHistory[name];
    if (!list) return;
    list.push(telemetryPercentNumber(value));
    const limit = telemetryHistoryLimit(options);
    while (list.length > limit) list.shift();
  }

  function telemetryHistorySnapshot() {
    return {
      cpu: telemetryHistory.cpu.slice(),
      gpu: telemetryHistory.gpu.slice(),
      ram: telemetryHistory.ram.slice(),
    };
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
      label: telemetryCssToken(isLight ? "--grey-700" : "--grey-300", "currentColor"),
      cpu: telemetryCssToken("--blue-400", "currentColor"),
      gpu: telemetryCssToken("--green-500", "currentColor"),
      ram: telemetryCssToken("--amber-500", "currentColor"),
      warning: telemetryCssToken("--semantic-warning-accent", "currentColor"),
      danger: telemetryCssToken("--semantic-danger-accent", "currentColor"),
      unavailable: telemetryCssToken(isLight ? "--grey-500" : "--grey-400", "currentColor"),
      bandWarning: telemetryCssToken("--semantic-warning-bg", "transparent"),
      bandDanger: telemetryCssToken("--semantic-danger-bg", "transparent"),
    };
  }

  function chartColorForState(kind, state, colors = telemetryCanvasColors()) {
    if (["error", "danger", "degraded", "blocked"].includes(state)) return colors.danger;
    if (["warning", "stale", "clock-skew", "high"].includes(state)) return colors.warning;
    if (["unavailable", "unsupported", "loading", "idle", "empty"].includes(state)) return colors.unavailable;
    if (kind === "cpu") return colors.cpu;
    if (kind === "gpu") return colors.gpu;
    if (kind === "ram") return colors.ram;
    return colors.cpu;
  }

  function prepareTelemetryCanvas(canvas) {
    const ctx = canvas.getContext("2d");
    const rect = typeof canvas.getBoundingClientRect === "function" ? canvas.getBoundingClientRect() : null;
    const attrWidth = Number(canvas.getAttribute("width")) || 520;
    const attrHeight = Number(canvas.getAttribute("height")) || 140;
    const width = Math.max(1, Math.round(rect?.width || canvas.clientWidth || attrWidth));
    const height = Math.max(1, Math.round(rect?.height || canvas.clientHeight || attrHeight));
    const dpr = Math.max(1, Math.min(2, Number(window.devicePixelRatio) || 1));
    const targetWidth = Math.round(width * dpr);
    const targetHeight = Math.round(height * dpr);
    if (canvas.width !== targetWidth) canvas.width = targetWidth;
    if (canvas.height !== targetHeight) canvas.height = targetHeight;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    return { ctx, width, height };
  }

  function drawTelemetryChart(id, values, color, options = {}) {
    const canvas = byId(id);
    if (!canvas) return;
    const { ctx, width, height } = prepareTelemetryCanvas(canvas);
    const colors = telemetryCanvasColors();
    const state = options.state || "normal";
    const normalizedValues = Array.isArray(values) ? values : [];
    canvas.dataset.state = state;

    ctx.clearRect(0, 0, width, height);
    ctx.fillStyle = colors.background;
    ctx.fillRect(0, 0, width, height);

    const dangerY = height - (90 / 100) * height;
    const warningY = height - (80 / 100) * height;
    ctx.fillStyle = colors.bandDanger;
    ctx.globalAlpha = 0.14;
    ctx.fillRect(0, 0, width, dangerY);
    ctx.fillStyle = colors.bandWarning;
    ctx.fillRect(0, dangerY, width, Math.max(0, warningY - dangerY));
    ctx.globalAlpha = 1;

    ctx.strokeStyle = colors.grid;
    ctx.lineWidth = 1;
    for (let i = 1; i < 4; i += 1) {
      const y = (height / 4) * i;
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(width, y);
      ctx.stroke();
    }

    ctx.strokeStyle = colors.baseline;
    ctx.beginPath();
    ctx.moveTo(0, height - 2);
    ctx.lineTo(width, height - 2);
    ctx.stroke();

    const finiteValues = normalizedValues.filter((value) => telemetryPercentNumber(value) !== null);
    if (!finiteValues.length) {
      ctx.fillStyle = colors.label;
      ctx.font = "12px sans-serif";
      ctx.fillText(options.emptyLabel || "waiting for sample", 12, height - 12);
      return;
    }

    const step = normalizedValues.length > 1 ? width / (normalizedValues.length - 1) : width;
    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.beginPath();
    let hasSegment = false;
    let previousWasFinite = false;
    normalizedValues.forEach((rawValue, index) => {
      const value = telemetryPercentNumber(rawValue);
      if (value === null) {
        previousWasFinite = false;
        return;
      }
      const x = normalizedValues.length > 1 ? index * step : 8;
      const y = Math.max(2, Math.min(height - 2, height - (value / 100) * height));
      if (!previousWasFinite) ctx.moveTo(x, y);
      else {
        ctx.lineTo(x, y);
        hasSegment = true;
      }
      previousWasFinite = true;
    });
    if (hasSegment) ctx.stroke();

    if (finiteValues.length === 1) {
      const single = telemetryPercentNumber(finiteValues[0]);
      const y = Math.max(2, Math.min(height - 2, height - (single / 100) * height));
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

  function formatNotReported(value, fallback = "not reported") {
    if (value === null || value === undefined) return fallback;
    const text = String(value).trim();
    return text || fallback;
  }

  function parseTelemetrySampleTime(telemetry) {
    const raw = telemetry?.sampled_at || telemetry?.collected_at || telemetry?.timestamp || "";
    if (!raw) return null;
    const parsed = new Date(raw);
    return Number.isNaN(parsed.getTime()) ? null : parsed;
  }

  function telemetrySampleDeltaSeconds(telemetry) {
    const parsed = parseTelemetrySampleTime(telemetry);
    if (!parsed) return null;
    return Math.round((Date.now() - parsed.getTime()) / 1000);
  }

  function telemetrySampleAgeSeconds(telemetry) {
    return telemetrySampleDeltaSeconds(telemetry);
  }

  function formatTelemetryAge(seconds) {
    if (seconds === null || seconds === undefined || !Number.isFinite(Number(seconds))) return "unknown";
    const numeric = Number(seconds);
    const abs = Math.abs(numeric);
    if (abs < 60) return `${Math.round(abs)}s`;
    const minutes = Math.floor(abs / 60);
    const remainder = Math.round(abs % 60);
    if (minutes < 60) return `${minutes}m ${remainder}s`;
    const hours = Math.floor(minutes / 60);
    return `${hours}h ${minutes % 60}m`;
  }

  function telemetrySampleTiming(telemetry) {
    const delta = telemetrySampleDeltaSeconds(telemetry);
    if (delta === null) {
      return {
        state: "unknown",
        label: "Sample age unknown",
        ageLabel: "unknown",
        delta,
      };
    }
    if (delta < -TELEMETRY_FUTURE_SKEW_SECONDS) {
      return {
        state: "clock-skew",
        label: `Clock skew +${formatTelemetryAge(delta)}`,
        ageLabel: `clock +${formatTelemetryAge(delta)}`,
        delta,
      };
    }
    if (delta > TELEMETRY_STALE_SECONDS) {
      return {
        state: "stale",
        label: `Stale ${formatTelemetryAge(delta)}`,
        ageLabel: formatTelemetryAge(delta),
        delta,
      };
    }
    return {
      state: "live",
      label: `Live ${formatTelemetryAge(delta)}`,
      ageLabel: formatTelemetryAge(delta),
      delta,
    };
  }

  function telemetrySourceSignal(telemetry, options = {}) {
    if (options.unavailableReason) {
      return { label: "not reported", state: "unavailable", warnings: [] };
    }
    const payload = telemetryGpuUsagePayload(telemetry);
    const structuredRows = Array.isArray(payload.rows) ? payload.rows : [];
    const legacyRows = Array.isArray(telemetry?.gpu_rows) ? telemetry.gpu_rows : [];
    const sources = [];
    const sourceKeys = new Set();
    const warnings = new Set();

    const addSource = (value, prefix = "") => {
      const text = formatNotReported(value, "").trim();
      if (!text) return;
      const key = text.toLowerCase();
      if (!sourceKeys.has(key)) {
        sourceKeys.add(key);
        sources.push(prefix ? `${prefix} ${text}` : text);
      }
      if (TELEMETRY_SOURCE_WARNING_TOKENS.some((token) => key.includes(token))) {
        warnings.add(`Source looks fixture-like: ${prefix ? `${prefix} ${text}` : text}`);
      }
    };

    addSource(telemetry?.source || payload.source);
    if (payload.source && String(payload.source).trim().toLowerCase() !== String(telemetry?.source || "").trim().toLowerCase()) {
      addSource(payload.source, "gpu");
    }
    [...structuredRows, ...legacyRows].forEach((row) => {
      if (!row || typeof row !== "object") return;
      addSource(row.source, "row");
      if (row.read_error) warnings.add(`GPU row read warning: ${row.read_error}`);
    });
    const payloadStatus = String(payload.status || "").trim();
    if (["warning", "degraded", "error"].includes(payloadStatus.toLowerCase())) {
      warnings.add(`GPU usage status: ${payloadStatus}`);
    }

    const label = sources.length ? sources.join(" / ") : "not reported";
    return {
      label,
      state: label === "not reported" ? "unavailable" : warnings.size ? "warning" : "normal",
      warnings: Array.from(warnings),
    };
  }

  function telemetrySourceText(telemetry, options = {}) {
    return telemetrySourceSignal(telemetry, options).label;
  }

  function telemetrySourceState(telemetry, options = {}) {
    return telemetrySourceSignal(telemetry, options).state;
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

  function telemetryGpuUsageDetailLines(telemetry) {
    const payload = telemetryGpuUsagePayload(telemetry);
    const rows = telemetryGpuUsageRows(telemetry);
    const lines = [
      `Contract: ${payload.schema_version || "desktop_gpu_encoder_usage.v1"}`,
      telemetryGpuUsageSummaryLine(telemetry),
    ];
    rows.slice(0, 4).forEach((row) => {
      lines.push(`${row.name || "GPU"}${row.index !== "" ? ` (${row.index})` : ""}: status=${formatGpuStatus(row, payload)}; encoder=${formatGpuEncoderPercent(row.encoder_percent)}; sessions=${formatSessionsCell(row.encoder_sessions)}; memory=${formatGpuMemoryCell(row)}`);
    });
    if (!rows.length) lines.push("No GPU/NVENC usage rows were reported by the backend.");
    if (Array.isArray(payload.summary_lines)) {
      const sessionLine = payload.summary_lines.find((line) => String(line || "").includes("Encoder sessions"));
      if (sessionLine) lines.push(sessionLine);
    }
    lines.push("Mutation guardrail: GPU/NVENC telemetry is read-only and cannot start, stop, retry, or tune encoder work.");
    return lines;
  }

  function cpuUtilityNoteText(telemetry, options = {}) {
    if (options.unavailableReason) return "Task Manager-equivalent (% Utility): telemetry unavailable";
    const util = telemetryPercentNumber(telemetry?.cpu_utility_percent);
    if (util === null) return "Task Manager-equivalent (% Utility): unavailable";
    return `Task Manager-equivalent (% Utility): ${formatPercent(util)}`;
  }

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

  function telemetryHasUsefulValues(telemetry) {
    const rows = Array.isArray(telemetry?.gpu_rows) ? telemetry.gpu_rows : [];
    const payloadRows = Array.isArray(telemetry?.gpu_encoder_usage?.rows) ? telemetry.gpu_encoder_usage.rows : [];
    return Boolean(
      telemetryHasNumber(telemetry?.cpu_percent)
      || telemetryHasNumber(telemetry?.memory_percent)
      || telemetryHasNumber(telemetry?.gpu_encoder_percent)
      || telemetryHasNumber(telemetry?.gpu_percent)
      || rows.length
      || payloadRows.length
    );
  }

  function telemetrySnapshotTextValues(snapshot) {
    if (!snapshot || typeof snapshot !== "object") return [];
    const progress = snapshot.progress && typeof snapshot.progress === "object" ? snapshot.progress : {};
    const currentWork = snapshot.current_work && typeof snapshot.current_work === "object" ? snapshot.current_work : {};
    return [
      snapshot.pipeline_state,
      snapshot.state,
      snapshot.status,
      snapshot.stage,
      snapshot.route,
      snapshot.mode,
      progress.Status,
      progress.status,
      progress.CurrentStage,
      progress.stage,
      progress.CurrentDisplayName,
      progress.CurrentFileDisplay,
      progress.CleanDisplayName,
      currentWork.item_label,
      currentWork.source_path,
      currentWork.phase_label,
      currentWork.route_label,
      currentWork.stage,
      currentWork.mode,
      currentWork.policy,
    ].map((value) => String(value || "").trim()).filter(Boolean);
  }

  function telemetryActiveWork(snapshot) {
    if (!snapshot || typeof snapshot !== "object") return false;
    if (snapshot.active_work === true) return true;
    const state = String(snapshot.pipeline_state || snapshot.state || snapshot.status || "").trim().toLowerCase();
    if (["running", "processing", "encoding", "remuxing", "copying", "publishing", "active", "audit", "auditing", "starting", "stopping"].includes(state)) {
      return true;
    }
    if (["idle", "stopped", "complete", "completed", "ready", "safe"].includes(state)) return false;
    const values = telemetrySnapshotTextValues(snapshot).map((value) => value.toLowerCase());
    return values.some((value) => ["running", "processing", "encoding", "remuxing", "copying", "publishing", "audit", "auditing"].some((token) => value.includes(token)));
  }

  function telemetryExpectedEncoderMode(snapshot) {
    if (!telemetryActiveWork(snapshot)) return "idle";
    const text = telemetrySnapshotTextValues(snapshot).join(" ").toLowerCase();
    if (/(nvenc|hardware|gpu encode|video encoder|h264_nvenc|hevc_nvenc)/.test(text)) return "hardware";
    if (/(cpu fallback|software|libx264|libx265|x264|x265|cpu encode)/.test(text)) return "cpu";
    if (/(remux|copy|publish|probe|scan|subtitle|audio copy|direct stream)/.test(text)) return "remux";
    if (/(encode|encoding|transcode|transcoding)/.test(text)) return "hardware";
    return "unknown-active";
  }

  function telemetryExpectedEncoderLabel(mode) {
    if (mode === "hardware") return "NVENC/hardware likely";
    if (mode === "cpu") return "CPU/software likely";
    if (mode === "remux") return "Remux/copy stage";
    if (mode === "idle") return "No active work";
    return "Unknown active stage";
  }

  function telemetryRenderContext(telemetry, options = {}) {
    const snapshot = options && typeof options === "object" ? options.snapshot : null;
    const timing = telemetrySampleTiming(telemetry);
    const active = telemetryActiveWork(snapshot);
    const expectedEncoder = telemetryExpectedEncoderMode(snapshot);
    return {
      active,
      expectedEncoder,
      gpuPresent: telemetryGpuPresent(telemetry),
      hasUsefulValues: telemetryHasUsefulValues(telemetry),
      sourceSignal: telemetrySourceSignal(telemetry, options),
      timing,
      unavailableReason: options.unavailableReason || "",
      refreshSeconds: telemetryRefreshSeconds(options),
    };
  }

  function telemetryOperatingState(telemetry, options = {}) {
    const payload = telemetry && typeof telemetry === "object" ? telemetry : {};
    const context = telemetryRenderContext(payload, options);
    const cpu = telemetryPercentNumber(payload.cpu_percent);
    const ram = telemetryPercentNumber(payload.memory_percent);
    const encoder = telemetryPercentNumber(payload.gpu_encoder_percent);
    const base = (key, label, state, nextStep) => ({
      key,
      label,
      state,
      nextStep,
      active: context.active,
      age: context.timing.delta,
      timing: context.timing,
      expectedEncoder: context.expectedEncoder,
    });
    if (context.unavailableReason) {
      return base(
        "unavailable",
        "Telemetry unavailable",
        "blocked",
        `Telemetry refresh failed: ${context.unavailableReason}. Last values are not trusted until the next successful sample.`
      );
    }
    if (payload.error) {
      return base(
        "degraded",
        "Telemetry degraded",
        "blocked",
        "Telemetry is degraded. If hardware encoding is expected, inspect Maintenance GPU tools, Diagnostics nvidia-smi, and Video settings."
      );
    }
    if (context.timing.state === "clock-skew") {
      return base(
        "clock-skew",
        "Telemetry clock skew",
        "warning",
        "Telemetry sample time is ahead of the UI clock. Confirm backend and Windows time before trusting graph age."
      );
    }
    if (context.timing.state === "stale") {
      return base(
        "stale",
        "Telemetry stale",
        "warning",
        "Telemetry sample is stale. Check whether the backend sampler is running before trusting graph values."
      );
    }
    if (!context.hasUsefulValues) {
      return base(
        "waiting",
        "Waiting for telemetry",
        "loading",
        "Waiting for the first hardware telemetry sample. Refresh or open Diagnostics if telemetry remains empty."
      );
    }
    if (context.sourceSignal.state === "warning") {
      const reasonText = context.sourceSignal.warnings.join("; ");
      return base(
        "source-warning",
        "Telemetry source warning",
        "warning",
        `Telemetry source is not fully trusted: ${reasonText}. Treat values as diagnostic until a live source reports cleanly.`
      );
    }
    if (!context.gpuPresent && (cpu !== null || ram !== null)) {
      return base(
        context.active && context.expectedEncoder === "hardware" ? "hardware-telemetry-unavailable" : "cpu-ram-only",
        context.active && context.expectedEncoder === "hardware" ? "Hardware telemetry unavailable" : "CPU/RAM only",
        "warning",
        "GPU video encoder telemetry is not available. CPU/RAM data is still usable. If hardware encoding is expected, inspect Maintenance GPU tools, Diagnostics nvidia-smi, and Video settings."
      );
    }
    if (context.active && encoder === 0 && context.expectedEncoder === "hardware") {
      const memoryNote = ram !== null && ram >= 85
        ? " RAM pressure is also high; inspect active jobs and close unrelated apps before starting more work."
        : "";
      return base(
        "nvenc-expected-idle",
        "NVENC expected but idle",
        "warning",
        `The active stage looks like a hardware encode, but NVENC is 0%. Inspect the active job stage and Video settings before assuming hardware acceleration is working.${memoryNote}`
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
    if (context.active && encoder === 0 && ["cpu", "remux"].includes(context.expectedEncoder)) {
      return base(
        "nvenc-idle-expected",
        "NVENC idle as expected",
        "ok",
        "The active stage does not appear to require NVENC, so 0% video encoder usage is expected."
      );
    }
    if (context.active && encoder !== null && encoder >= 80) {
      return base(
        "gpu-bound",
        "GPU-bound encode",
        "changed",
        "The GPU video encoder is the likely bottleneck. Inspect encode progress and GPU Details if throughput is lower than expected."
      );
    }
    if (context.active && cpu !== null && cpu >= 85 && (encoder === null || encoder < 20)) {
      return base(
        "cpu-bound",
        "CPU-bound encode",
        "warning",
        "CPU is likely limiting the current job. Inspect the active job stage and whether this encode is using CPU fallback."
      );
    }
    if (!context.active && cpu !== null && cpu < 20 && (ram === null || ram < 80) && (encoder === null || encoder === 0)) {
      return base(
        "idle",
        "Idle",
        "empty",
        "No active work is reported; hardware usage looks idle."
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

  function telemetryChartMetaText(telemetry, options = {}) {
    const timing = telemetrySampleTiming(telemetry);
    const refreshSeconds = telemetryRefreshSeconds(options);
    return `0-100% | Last ~${Math.round(TELEMETRY_HISTORY_SECONDS / 60)} min | UI refresh ${refreshSeconds}s | GPU probe up to ${GPU_TELEMETRY_PROBE_SECONDS}s | Sample age ${timing.ageLabel}`;
  }

  function telemetryReadinessLines(telemetry, options = {}) {
    if (options.unavailableReason) {
      return [
        "Payload: unavailable",
        `Refresh failure: ${options.unavailableReason}`,
        "Next step: confirm the local API telemetry route is reachable before trusting graphs.",
      ];
    }
    if (!telemetry || typeof telemetry !== "object") {
      return [
        "Payload: unavailable",
        "Next step: Refresh the page or open Diagnostics if telemetry remains unavailable.",
      ];
    }
    const operatingState = telemetryOperatingState(telemetry, options);
    const rows = telemetryGpuUsageRows(telemetry);
    const sourceSignal = telemetrySourceSignal(telemetry, options);
    const timing = telemetrySampleTiming(telemetry);
    const sampleTime = telemetry.sampled_at || telemetry.collected_at || telemetry.timestamp || "not reported";
    const gpuPresent = telemetryGpuPresent(telemetry);
    const expectedMode = telemetryExpectedEncoderMode(options.snapshot);
    const lines = [
      `Operating state: ${operatingState.label}`,
      `Next step: ${operatingState.nextStep}`,
      "Payload: loaded",
      `Sample: ${sampleTime}`,
      `Age: ${timing.label}`,
      `Source: ${sourceSignal.label}`,
      `Expected encoder: ${telemetryExpectedEncoderLabel(expectedMode)}`,
      `CPU: ${telemetryHasNumber(telemetry.cpu_percent) ? formatPercent(telemetry.cpu_percent) : "unavailable"}`,
      `CPU (Task Manager-equivalent, % Utility): ${telemetryHasNumber(telemetry.cpu_utility_percent) ? formatPercent(telemetry.cpu_utility_percent) : "unavailable"}`,
      `RAM: ${telemetryHasNumber(telemetry.memory_percent) ? formatPercent(telemetry.memory_percent) : "unavailable"}`,
      `GPU present: ${gpuPresent ? "yes" : "no"}`,
      `Video encoder (NVENC): ${gpuPresent ? formatGpuEncoderPercent(telemetry.gpu_encoder_percent) : "unavailable"}`,
      `GPU rows: ${rows.length}`,
      ...telemetryGpuUsageDetailLines(telemetry),
    ];
    if (sourceSignal.warnings.length) lines.push(`Source warning: ${sourceSignal.warnings.join("; ")}`);
    if (telemetry.error) lines.push(`Warning: ${telemetry.error}`);
    return lines;
  }

  function setTelemetryTextState(id, text, state) {
    setText(id, text);
    const node = byId(id);
    if (node) node.dataset.state = state || "";
  }

  function setTelemetryDatasetState(id, state) {
    const node = byId(id);
    if (node) node.dataset.state = state || "";
  }

  function setTelemetryKpiState(name, state) {
    const node = document.querySelector(`[data-telemetry-kpi="${name}"]`);
    if (node) node.dataset.state = state || "";
  }

  function setTelemetryChartPanelState(name, state) {
    const node = document.querySelector(`[data-telemetry-chart-panel="${name}"]`);
    if (node) node.dataset.state = state || "";
  }

  function setTelemetryTrustFactState(id, state) {
    const node = byId(id);
    const fact = node?.closest(".telemetry-trust-fact");
    if (fact) fact.dataset.state = state || "";
  }

  function telemetryUsageState(kind, value, context) {
    const numeric = telemetryPercentNumber(value);
    if (context.unavailableReason) return "unavailable";
    if (context.timing.state === "clock-skew") return "clock-skew";
    if (context.timing.state === "stale") return "stale";
    if (context.sourceSignal?.state === "warning") return "warning";
    if (numeric === null) return "unavailable";
    if (kind === "ram") {
      if (numeric >= 90) return "danger";
      if (numeric >= 80) return "warning";
      return "normal";
    }
    if (kind === "cpu") {
      if (numeric >= 95) return "danger";
      if (numeric >= 85) return "warning";
      return "normal";
    }
    if (kind === "gpu") {
      if (!context.gpuPresent) return "unavailable";
      if (numeric === 0) {
        if (context.active && context.expectedEncoder === "hardware") return "warning";
        return "idle";
      }
      if (numeric >= 95) return "warning";
      if (numeric >= 80) return "active";
      return "normal";
    }
    return "normal";
  }

  function formatTelemetryPercentValue(value, state) {
    const numeric = telemetryPercentNumber(value);
    if (numeric !== null) return formatPercent(numeric);
    if (state === "loading") return "Waiting";
    return "Unavailable";
  }

  function telemetryKpiGpuStatus(telemetry, options = {}) {
    if (options.unavailableReason) return "Unavailable";
    if (telemetry?.error) return "Degraded";
    const timing = telemetrySampleTiming(telemetry);
    if (timing.state === "clock-skew") return "Clock skew";
    if (timing.state === "stale") return "Stale";
    if (telemetrySourceState(telemetry, options) === "warning") return "Warning";
    if (telemetryGpuPresent(telemetry)) return "Available";
    if (telemetryHasNumber(telemetry?.cpu_percent) || telemetryHasNumber(telemetry?.memory_percent)) return "Not available";
    return "Waiting";
  }

  function renderTelemetryTrustStrip(telemetry, options = {}, context = telemetryRenderContext(telemetry, options)) {
    const operatingState = telemetryOperatingState(telemetry, options);
    const timing = context.timing;
    const sourceState = telemetrySourceState(telemetry, options);
    setText("telemetry-live-state", operatingState.label);
    setTelemetryTrustFactState("telemetry-live-state", operatingState.state);
    setText("telemetry-sample-age", timing.label.replace(/^Live /, ""));
    setTelemetryTrustFactState("telemetry-sample-age", timing.state === "live" ? "normal" : timing.state);
    setText("telemetry-source", telemetrySourceText(telemetry, options));
    setTelemetryTrustFactState("telemetry-source", sourceState);
    setText("telemetry-expected-encoder", telemetryExpectedEncoderLabel(context.expectedEncoder));
    setTelemetryTrustFactState("telemetry-expected-encoder", context.expectedEncoder === "hardware" ? "active" : context.expectedEncoder === "unknown-active" ? "warning" : "normal");
    setText("telemetry-refresh-cadence", `UI ${context.refreshSeconds}s / GPU ${GPU_TELEMETRY_PROBE_SECONDS}s`);
    setTelemetryTrustFactState("telemetry-refresh-cadence", "normal");
  }

  function renderTelemetryReadiness(telemetry, options = {}) {
    const operatingState = telemetryOperatingState(telemetry, options);
    setTelemetryTextState("telemetry-readiness-status", operatingState.label, operatingState.state);
    setText("telemetry-operator-state-label", operatingState.label);
    setText("telemetry-operator-next-step", operatingState.nextStep);
    setTelemetryDatasetState("telemetry-operator-state", operatingState.key);
    setText("telemetry-readiness-summary", telemetryReadinessLines(telemetry, options).join("\n"));
  }

  function renderTelemetryKpis(telemetry, options = {}, context = telemetryRenderContext(telemetry, options)) {
    const cpuState = telemetryUsageState("cpu", telemetry?.cpu_percent, context);
    const gpuState = telemetryUsageState("gpu", telemetry?.gpu_encoder_percent, context);
    const ramState = telemetryUsageState("ram", telemetry?.memory_percent, context);
    const gpuStatusState = options.unavailableReason
      ? "unavailable"
      : telemetry?.error
        ? "error"
          : context.timing.state === "clock-skew" || context.timing.state === "stale"
            ? context.timing.state
            : context.sourceSignal.state === "warning"
              ? "warning"
              : telemetryGpuPresent(telemetry)
                ? "normal"
                : context.hasUsefulValues
                  ? "warning"
                  : "loading";

    setText("telemetry-kpi-cpu-value", formatTelemetryPercentValue(telemetry?.cpu_percent, context.hasUsefulValues ? cpuState : "loading"));
    setText("telemetry-kpi-encoder-value", telemetryGpuPresent(telemetry) ? formatTelemetryPercentValue(telemetry?.gpu_encoder_percent, gpuState) : (context.hasUsefulValues || options.unavailableReason ? "Unavailable" : "Waiting"));
    setText("telemetry-kpi-ram-value", formatTelemetryPercentValue(telemetry?.memory_percent, context.hasUsefulValues ? ramState : "loading"));
    setText("telemetry-kpi-gpu-status", telemetryKpiGpuStatus(telemetry, options));

    setTelemetryKpiState("cpu", cpuState);
    setTelemetryKpiState("encoder", gpuState);
    setTelemetryKpiState("ram", ramState);
    setTelemetryKpiState("gpu", gpuStatusState);
    setTelemetryDatasetState("telemetry-kpi-cpu-value", cpuState);
    setTelemetryDatasetState("telemetry-kpi-encoder-value", gpuState);
    setTelemetryDatasetState("telemetry-kpi-ram-value", ramState);
    setTelemetryDatasetState("telemetry-kpi-gpu-status", gpuStatusState);
  }

  function renderTelemetryChartMetadata(telemetry, options = {}) {
    const text = telemetryChartMetaText(telemetry, options);
    setText("cpu-chart-meta", text);
    setText("gpu-chart-meta", text);
    setText("ram-chart-meta", text);
  }

  function telemetryGpuNote(telemetry, options = {}) {
    const details = [];
    if (options.unavailableReason) {
      details.push(`Telemetry unavailable: ${options.unavailableReason}.`);
    } else if (!telemetryGpuPresent(telemetry)) {
      details.push("GPU video encoder telemetry unavailable. CPU/RAM data is still usable.");
    } else {
      const encoder = telemetryPercentNumber(telemetry?.gpu_encoder_percent);
      if (encoder === 0) details.push("GPU video encoder is idle at 0%.");
      else details.push("GPU video encoder telemetry available.");
    }
    if (telemetry?.gpu_name) details.push(`Device: ${telemetry.gpu_name}`);
    const source = telemetrySourceText(telemetry, options);
    if (source !== "not reported") details.push(`Source: ${source}`);
    if (telemetry?.error) details.push(`Telemetry warning: ${telemetry.error}`);
    const rows = telemetryGpuUsageRows(telemetry);
    if (rows.length > 1) {
      details.push(rows.map((row) => `GPU ${row.index}: ${formatGpuEncoderPercent(row.encoder_percent)}`).join(", "));
    } else if (rows.length === 1) {
      details.push(`GPU ${rows[0].index || 0}: ${formatGpuEncoderPercent(rows[0].encoder_percent)}`);
    }
    return details.join(" | ");
  }

  function renderTelemetry(telemetry, options = {}) {
    const payload = telemetry && typeof telemetry === "object" ? telemetry : {};
    const context = telemetryRenderContext(payload, options);
    const cpu = options.unavailableReason ? null : payload.cpu_percent;
    const gpu = options.unavailableReason ? null : payload.gpu_encoder_percent;
    const ram = options.unavailableReason ? null : payload.memory_percent;
    const cpuState = telemetryUsageState("cpu", cpu, context);
    const gpuState = telemetryUsageState("gpu", gpu, context);
    const ramState = telemetryUsageState("ram", ram, context);

    pushTelemetryHistory("cpu", cpu, options);
    pushTelemetryHistory("gpu", gpu, options);
    pushTelemetryHistory("ram", ram, options);

    setTelemetryTextState("cpu-value", formatTelemetryPercentValue(cpu, context.hasUsefulValues ? cpuState : "loading"), cpuState);
    setText("cpu-utility-note", cpuUtilityNoteText(payload, options));
    setTelemetryTextState("gpu-value", telemetryGpuPresent(payload) && !options.unavailableReason ? formatTelemetryPercentValue(gpu, gpuState) : (context.hasUsefulValues || options.unavailableReason ? "Unavailable" : "Waiting"), gpuState);
    setTelemetryTextState("ram-value", formatTelemetryPercentValue(ram, context.hasUsefulValues ? ramState : "loading"), ramState);
    setText("gpu-note", telemetryGpuNote(payload, options));

    renderTelemetryKpis(payload, options, context);
    renderTelemetryTrustStrip(payload, options, context);
    renderTelemetryChartMetadata(payload, options);

    lastTelemetryChartStates = { cpu: cpuState, gpu: gpuState, ram: ramState };
    setTelemetryChartPanelState("cpu", cpuState);
    setTelemetryChartPanelState("encoder", gpuState);
    setTelemetryChartPanelState("ram", ramState);
    redrawTelemetryCharts();

    renderGpuRows(payload);
    renderTelemetryReadiness(payload, options);
    lastTelemetryContext = { telemetry: payload, options: { ...options } };
  }

  function redrawTelemetryCharts() {
    const colors = telemetryCanvasColors();
    drawTelemetryChart("cpu-chart", telemetryHistory.cpu, chartColorForState("cpu", lastTelemetryChartStates.cpu, colors), {
      state: lastTelemetryChartStates.cpu,
      emptyLabel: "waiting for CPU sample",
    });
    drawTelemetryChart("gpu-chart", telemetryHistory.gpu, chartColorForState("gpu", lastTelemetryChartStates.gpu, colors), {
      state: lastTelemetryChartStates.gpu,
      emptyLabel: "NVENC unavailable",
    });
    drawTelemetryChart("ram-chart", telemetryHistory.ram, chartColorForState("ram", lastTelemetryChartStates.ram, colors), {
      state: lastTelemetryChartStates.ram,
      emptyLabel: "waiting for RAM sample",
    });
  }

  function formatGpuMemoryCell(row) {
    if (telemetryHasNumber(row.memory_used_mb) && telemetryHasNumber(row.memory_total_mb) && Number(row.memory_total_mb) > 0) {
      return formatMemoryMb(row.memory_used_mb, row.memory_total_mb);
    }
    if (telemetryHasNumber(row.memory_used_mb)) return `${formatTelemetryNumber(row.memory_used_mb, 0)} MB used`;
    if (telemetryHasNumber(row.memory_percent)) return `${formatPercent(row.memory_percent)} reported`;
    return "not reported";
  }

  function formatTemperatureCell(value) {
    if (!telemetryHasNumber(value)) return "not reported";
    return `${Math.round(Number(value))} C`;
  }

  function formatSessionsCell(value) {
    if (!telemetryHasNumber(value)) return "not reported";
    return String(Math.round(Number(value)));
  }

  function formatGpuStatus(row, payload = {}) {
    if (row.read_error) return "Read warning";
    const payloadStatus = String(payload.status || row.status || "").trim();
    const encoder = telemetryPercentNumber(row.encoder_percent);
    const sessions = telemetryHasNumber(row.encoder_sessions) ? Number(row.encoder_sessions) : null;
    if (sessions !== null && sessions > 0) return "Active";
    if (encoder !== null && encoder > 0) return "Active";
    if (encoder === 0) return "Idle";
    if (row.synthesized) return "Top-level sample";
    if (payloadStatus) return payloadStatus;
    return "not reported";
  }

  function renderGpuRows(telemetry) {
    const payload = telemetryGpuUsagePayload(telemetry);
    const rows = telemetryVisibleGpuRows(telemetry);
    const status = rows.length
      ? `${rows.length} GPU row${rows.length === 1 ? "" : "s"}`
      : payload.status && payload.status !== "loaded"
        ? `No GPU rows (${payload.status})`
        : "No GPU rows";
    setText("gpu-detail-status", status);
    const tbody = byId("gpu-rows");
    const empty = byId("gpu-empty-state");
    if (empty) {
      empty.style.display = rows.length ? "none" : "";
      empty.dataset.emptyState = rows.length ? "hidden" : "visible";
    }
    if (!tbody) return;
    if (!rows.length) {
      const message = telemetryGpuPresent(telemetry)
        ? "GPU telemetry source returned no per-device rows."
        : "GPU/NVENC telemetry unavailable or unsupported.";
      clearRows(tbody, 9, message);
      return;
    }
    tbody.replaceChildren();
    rows.forEach((item) => {
      const row = document.createElement("tr");
      const statusText = formatGpuStatus(item, payload);
      if (statusText === "Read warning") row.dataset.status = "warning";
      else if (statusText === "Idle") row.dataset.status = "idle";
      else if (statusText === "Active") row.dataset.status = "active";
      appendCells(row, [
        item.index || "",
        item.name || "",
        statusText,
        formatGpuEncoderPercent(item.encoder_percent),
        formatPercent(item.gpu_percent ?? item.encoder_percent),
        formatGpuMemoryCell(item),
        formatTemperatureCell(item.temperature_c),
        formatSessionsCell(item.encoder_sessions),
        [formatNotReported(item.source), item.read_error ? `warning: ${item.read_error}` : ""].filter(Boolean).join(" | "),
      ], ["num", null, null, "num", "num", "num", "num", "num", null]);
      tbody.appendChild(row);
    });
  }

  function telemetryVisibleGpuRows(telemetry) {
    return telemetryGpuUsageRows(telemetry);
  }

  /**
   * Public namespace for the Telemetry page module.
   * Prefer this namespace from new code; flat window.* exports are not required for telemetry callers.
   */
  const telemetryNamespace = {
    renderTelemetry,
    renderGpuRows,
    renderTelemetryReadiness,
    renderTelemetryTrustStrip,
    renderTelemetryKpis,
    renderTelemetryChartMetadata,
    redrawTelemetryCharts,
    drawTelemetryChart,
    telemetryCssToken,
    telemetryCanvasColors,
    chartColorForState,
    formatGpuEncoderPercent,
    telemetryGpuNote,
    cpuUtilityNoteText,
    telemetryVisibleGpuRows,
    telemetryGpuUsagePayload,
    telemetryGpuUsageSummaryLine,
    telemetryGpuUsageDetailLines,
    telemetryGpuUsageRows,
    telemetryActiveWork,
    telemetryExpectedEncoderMode,
    telemetryExpectedEncoderLabel,
    telemetryOperatingState,
    telemetryChartMetaText,
    telemetryReadinessStatus,
    telemetryReadinessLines,
    telemetrySampleAgeSeconds,
    telemetrySampleTiming,
    telemetryHistorySnapshot,
    lastTelemetryContext: () => lastTelemetryContext,
  };

  window.mediaPipelineTelemetryView = telemetryNamespace;
})();
