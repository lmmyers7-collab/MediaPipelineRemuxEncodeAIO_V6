(function () {
  const REFRESH_INTERVAL_MS = 2000;
  const DIAGNOSTICS_TIMEOUT_MS = 10000;
  const RAW_PIPELINE_LOG_TAIL_ENDPOINT = "/api/diagnostics/tail?target=pipeline_log&max_bytes=262144";
  let refreshTimer = null;
  let refreshInFlight = false;
  let lastSuccessfulRefresh = 0;
  let lastCloseReadinessPayload = null;

  function byId(id) {
    return document.getElementById(id);
  }

  function displayMode() {
    return byId("pipeline-log-window-mode")?.value === "raw" ? "raw" : "activity";
  }

  function setStatus(label, state) {
    const status = byId("pipeline-log-window-status");
    if (!status) return;
    status.textContent = label;
    status.dataset.state = state || "unknown";
  }

  function setDetail(text) {
    const detail = byId("pipeline-log-window-detail");
    if (detail) detail.textContent = text;
  }

  function setUpdated(value) {
    const updated = byId("pipeline-log-window-updated");
    if (updated) updated.textContent = value;
  }

  function localTimestamp(date) {
    try {
      return date.toLocaleTimeString([], { hour: "numeric", minute: "2-digit", second: "2-digit" });
    } catch (_error) {
      return date.toISOString();
    }
  }

  function isNearBottom(node) {
    if (!node) return true;
    return node.scrollTop + node.clientHeight >= node.scrollHeight - 32;
  }

  function scrollToBottom(node) {
    if (!node) return;
    node.scrollTop = node.scrollHeight;
  }

  function logTextLines(value) {
    const text = String(value || "").trim();
    return text ? text.split(/\r?\n/).map((line) => line.trim()).filter(Boolean) : [];
  }

  function progressCompactionKey(line) {
    const text = String(line || "").trim();
    const match = text.match(/^(?:\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:\.\d+)?\s+)?(?:\[[A-Z]+\]\s+)?([A-Z][A-Z0-9_-]*)\s*:\s*(\d{1,3})%\s*$/i);
    if (!match) return "";
    return `${match[1].toUpperCase()}:${match[2]}`;
  }

  function compactRepeatedProgressLines(value) {
    const lines = logTextLines(value);
    const compacted = [];
    let pending = null;
    const flushPending = () => {
      if (!pending) return;
      compacted.push(
        pending.count > 1
          ? `${pending.lastLine} (shown once; ${pending.count} repeated progress updates collapsed)`
          : pending.lastLine
      );
      pending = null;
    };

    lines.forEach((line) => {
      const key = progressCompactionKey(line);
      if (!key) {
        flushPending();
        compacted.push(line);
        return;
      }
      if (pending && pending.key === key) {
        pending.count += 1;
        pending.lastLine = line;
        return;
      }
      flushPending();
      pending = { key, lastLine: line, count: 1 };
    });
    flushPending();
    return compacted.join("\n");
  }

  function isPlainObject(value) {
    return Boolean(value && typeof value === "object" && !Array.isArray(value));
  }

  function closeReadinessIndicatesActiveWork(closeReadiness) {
    return isPlainObject(closeReadiness)
      && (closeReadiness.safe_to_close === false || closeReadiness.active_work === true);
  }

  function activeEvidenceState(value) {
    return String(value || "").trim().toLowerCase();
  }

  function boundedLogLine(value, maxChars = 420) {
    const text = String(value || "").replace(/\s+/g, " ").trim();
    if (!text) return "";
    return text.length <= maxChars ? text : `${text.slice(0, maxChars - 3)}...`;
  }

  function activeJobRowLooksRelevant(row) {
    if (!isPlainObject(row)) return false;
    const state = activeEvidenceState(row.status_state);
    if (["running", "blocked", "warning"].includes(state)) return true;
    const text = [
      row.status,
      row.issue,
      row.source,
      row.job_kind,
    ].map(activeEvidenceState).join(" ");
    if (text.includes("completed")) return false;
    return ["launching", "active", "running", "processing", "blocked", "stale", "review", "unreadable", "invalid"].some((term) => text.includes(term));
  }

  function summarizeActiveJobRow(row) {
    const kind = String(row.job_kind || row.kind || "job").trim();
    const mode = String(row.mode || "").trim();
    const status = String(row.status || row.status_state || "unknown").trim();
    const pid = row.pid || row.app_pid ? `pid=${row.pid || row.app_pid}` : "pid=unknown";
    const id = String(row.launch_id || row.record_file || "").trim();
    const issue = String(row.issue || "").trim();
    return [
      `${kind}${mode ? ` ${mode}` : ""}: ${status}`,
      pid,
      id ? `id=${id}` : "",
      issue ? `issue=${issue}` : "",
    ].filter(Boolean).join("; ");
  }

  function activeJobsSummaryLines(diagnostics) {
    const rows = Array.isArray(diagnostics?.active_job_rows) ? diagnostics.active_job_rows : [];
    const rowLines = rows.filter(activeJobRowLooksRelevant).map(summarizeActiveJobRow);
    const summaryLines = (Array.isArray(diagnostics?.active_jobs) ? diagnostics.active_jobs : [])
      .map((line) => String(line || "").trim())
      .filter((line) => line && !/^(no activejobs records found|activejobs folder is empty|no active jobs)/i.test(line));
    return Array.from(new Set([...rowLines, ...summaryLines])).slice(0, 6);
  }

  function workerProgressSummaryLines(diagnostics) {
    const payload = isPlainObject(diagnostics?.worker_progress) ? diagnostics.worker_progress : {};
    const rows = Array.isArray(payload.rows) ? payload.rows : [];
    return rows
      .filter((row) => ["running", "blocked", "warning"].includes(activeEvidenceState(row?.status_state)))
      .map((row) => {
        const label = String(row.worker_label || row.worker_id || row.job_kind || "worker").trim();
        const stage = String(row.stage || row.status || "active").trim();
        const pid = row.pid ? `pid=${row.pid}` : "";
        const source = String(row.source || "").trim();
        return [`${label}: ${stage}`, pid, source ? `source=${source}` : ""].filter(Boolean).join("; ");
      })
      .filter(Boolean)
      .slice(0, 6);
  }

  function activeProcessLogLines(diagnostics) {
    const payload = isPlainObject(diagnostics?.worker_progress) ? diagnostics.worker_progress : {};
    const rows = Array.isArray(payload.rows) ? payload.rows : [];
    return Array.from(new Set(rows
      .filter((row) => ["running", "blocked", "warning"].includes(activeEvidenceState(row?.status_state)))
      .map((row) => {
        const latest = boundedLogLine(row?.last_log_line);
        if (!latest) return "";
        const kind = String(row.job_kind || "").trim().toLowerCase();
        const label = kind === "rerun_csv"
          ? "CSV rerun process"
          : String(row.worker_label || row.worker_id || row.job_kind || "Active process").trim();
        const stage = String(row.stage || row.status || "").trim();
        return `${label}${stage ? ` (${stage})` : ""}: ${latest}`;
      })
      .filter(Boolean))).slice(0, 6);
  }

  function activeWorkEvidenceLines(diagnostics) {
    return Array.from(new Set([
      ...activeJobsSummaryLines(diagnostics),
      ...workerProgressSummaryLines(diagnostics),
    ])).slice(0, 8);
  }

  function hasActiveWorkEvidence(diagnostics, closeReadiness) {
    return closeReadinessIndicatesActiveWork(closeReadiness) || activeWorkEvidenceLines(diagnostics).length > 0;
  }

  function closeReadinessLine(closeReadiness) {
    if (!isPlainObject(closeReadiness)) return "Close readiness: not loaded in this log refresh.";
    const closeState = closeReadiness.safe_to_close === true
      ? "safe"
      : closeReadiness.safe_to_close === false
        ? "active/blocked"
        : "unknown";
    const state = String(closeReadiness.state || "").trim();
    return `Close readiness: ${closeState}${state ? ` (${state})` : ""}`;
  }

  function activeWorkLogLines(diagnostics, closeReadiness) {
    if (!hasActiveWorkEvidence(diagnostics, closeReadiness)) return [];
    const lines = [
      "ACTIVE WORK DETECTED",
      closeReadinessLine(closeReadiness),
    ];
    const reason = String(closeReadiness?.reason || "").trim();
    if (reason) lines.push(`Reason: ${reason}`);
    const warnings = Array.isArray(closeReadiness?.warnings)
      ? closeReadiness.warnings.map((item) => String(item || "").trim()).filter(Boolean)
      : [];
    if (warnings.length) lines.push(`Warnings: ${warnings.slice(0, 3).join(" | ")}`);
    const evidence = activeWorkEvidenceLines(diagnostics);
    if (evidence.length) {
      lines.push("Active evidence:");
      evidence.forEach((line) => lines.push(`- ${line}`));
    } else {
      lines.push("Active evidence: close-readiness reports active work, but no structured ActiveJobs rows are present in this diagnostics payload.");
    }
    const processLines = activeProcessLogLines(diagnostics);
    if (processLines.length) {
      lines.push("Active process log:");
      processLines.forEach((line) => lines.push(`- ${line}`));
    }
    lines.push("Log note: the pipeline tail below may be from a previous run until the active process writes or flushes new log lines.");
    return lines;
  }

  function pipelineLogDisplayText(diagnostics, closeReadiness) {
    const rawLogText = String(diagnostics?.log_tail || "");
    const logText = compactRepeatedProgressLines(rawLogText);
    const activeLines = activeWorkLogLines(diagnostics, closeReadiness);
    if (!activeLines.length) return logText || "No pipeline log tail loaded.";
    const tailLines = logText
      ? ["--- pipeline log tail ---", logText]
      : ["No pipeline log tail loaded yet."];
    return [...tailLines, "", "--- current activity ---", ...activeLines].join("\n");
  }

  async function readCloseReadiness(apiClient) {
    try {
      return await apiClient.apiGet("/api/backend/close-readiness", {
        timeoutMs: DIAGNOSTICS_TIMEOUT_MS,
      });
    } catch (_error) {
      return lastCloseReadinessPayload;
    }
  }

  async function readRawPipelineLogTail(apiClient) {
    return apiClient.apiGet(RAW_PIPELINE_LOG_TAIL_ENDPOINT, {
      timeoutMs: DIAGNOSTICS_TIMEOUT_MS,
    });
  }

  function renderPipelineLogWindow(diagnostics, closeReadiness) {
    if (arguments.length > 1) lastCloseReadinessPayload = closeReadiness || null;
    const textNode = byId("pipeline-log-window-text");
    const follow = byId("pipeline-log-window-follow");
    if (!textNode) return;

    const shouldFollow = Boolean(follow?.checked) || isNearBottom(textNode);
    const previousScrollTop = textNode.scrollTop;
    const rawLogText = String(diagnostics?.log_tail || "");
    const activeWork = hasActiveWorkEvidence(diagnostics, lastCloseReadinessPayload);
    const nextLogText = pipelineLogDisplayText(diagnostics, lastCloseReadinessPayload);
    if (textNode.textContent !== nextLogText) textNode.textContent = nextLogText;
    if (shouldFollow) {
      window.requestAnimationFrame(() => scrollToBottom(textNode));
    } else {
      textNode.scrollTop = previousScrollTop;
    }

    lastSuccessfulRefresh = Date.now();
    setUpdated(`Last refresh: ${localTimestamp(new Date(lastSuccessfulRefresh))}`);
    setStatus(activeWork ? "Active work" : rawLogText ? "Loaded" : "Empty", activeWork ? "stale" : rawLogText ? "ok" : "empty");
    setDetail("Source: GET /api/diagnostics log_tail + GET /api/backend/close-readiness. This window is read-only and refreshes every 2 seconds.");
  }

  function renderRawPipelineLogWindow(tailPayload) {
    const textNode = byId("pipeline-log-window-text");
    const follow = byId("pipeline-log-window-follow");
    if (!textNode) return;

    const ok = tailPayload?.ok === true;
    const rawLogText = String(tailPayload?.text ?? "");
    const fallbackLines = [
      ...(Array.isArray(tailPayload?.warnings) ? tailPayload.warnings : []),
      ...(Array.isArray(tailPayload?.errors) ? tailPayload.errors : []),
    ].map((item) => String(item || "").trim()).filter(Boolean);
    const nextLogText = ok ? rawLogText : fallbackLines.join("\n") || "Raw pipeline log tail is not available.";
    const shouldFollow = Boolean(follow?.checked) || isNearBottom(textNode);
    const previousScrollTop = textNode.scrollTop;
    if (textNode.textContent !== nextLogText) textNode.textContent = nextLogText;
    if (shouldFollow) {
      window.requestAnimationFrame(() => scrollToBottom(textNode));
    } else {
      textNode.scrollTop = previousScrollTop;
    }

    lastSuccessfulRefresh = Date.now();
    setUpdated(`Last refresh: ${localTimestamp(new Date(lastSuccessfulRefresh))}`);
    setStatus(ok ? (rawLogText ? "Raw tail" : "Empty") : "Raw unavailable", ok ? (rawLogText ? "ok" : "empty") : "error");
    setDetail("Source: GET /api/diagnostics/tail?target=pipeline_log. This window is read-only and refreshes every 2 seconds.");
  }

  function renderRefreshError(error) {
    const message = error && error.message ? error.message : String(error || "Unknown diagnostics error");
    const stale = lastSuccessfulRefresh > 0;
    setStatus(stale ? "Stale" : "Read failed", stale ? "stale" : "error");
    setDetail(`Last refresh failed: ${message}`);
    setUpdated(stale ? `Last good refresh: ${localTimestamp(new Date(lastSuccessfulRefresh))}` : "No successful refresh yet");
  }

  async function refreshPipelineLogWindow() {
    if (refreshInFlight) return;
    refreshInFlight = true;
    const refreshButton = byId("pipeline-log-window-refresh-button");
    if (refreshButton) refreshButton.disabled = true;
    setStatus("Refreshing", "loading");
    try {
      const apiClient = window.mediaPipelineApi || {};
      if (typeof apiClient.apiGet !== "function") {
        throw new Error("API client is not available.");
      }
      if (displayMode() === "raw") {
        renderRawPipelineLogWindow(await readRawPipelineLogTail(apiClient));
        return;
      }
      const [diagnostics, closeReadiness] = await Promise.all([
        apiClient.apiGet("/api/diagnostics", {
          timeoutMs: DIAGNOSTICS_TIMEOUT_MS,
        }),
        readCloseReadiness(apiClient),
      ]);
      renderPipelineLogWindow(diagnostics, closeReadiness);
    } catch (error) {
      renderRefreshError(error);
    } finally {
      refreshInFlight = false;
      if (refreshButton) refreshButton.disabled = false;
    }
  }

  function startRefreshTimer() {
    if (refreshTimer) window.clearInterval(refreshTimer);
    refreshTimer = window.setInterval(refreshPipelineLogWindow, REFRESH_INTERVAL_MS);
  }

  function initPipelineLogWindow() {
    const refreshButton = byId("pipeline-log-window-refresh-button");
    if (refreshButton) refreshButton.addEventListener("click", refreshPipelineLogWindow);
    const modeSelect = byId("pipeline-log-window-mode");
    if (modeSelect) modeSelect.addEventListener("change", refreshPipelineLogWindow);
    document.addEventListener("visibilitychange", () => {
      if (document.visibilityState === "visible") refreshPipelineLogWindow();
    });
    window.addEventListener("beforeunload", () => {
      if (refreshTimer) window.clearInterval(refreshTimer);
    });
    startRefreshTimer();
    refreshPipelineLogWindow();
  }

  /**
   * Public namespace for the Pipeline Log window module.
   * Prefer this namespace from new code; flat window.* exports are intentionally not added for this read-only window.
   */
  window.mediaPipelinePipelineLogWindow = {
    initPipelineLogWindow,
    refreshPipelineLogWindow,
    renderPipelineLogWindow,
    compactRepeatedProgressLines,
    refreshIntervalMs: REFRESH_INTERVAL_MS,
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initPipelineLogWindow, { once: true });
  } else {
    initPipelineLogWindow();
  }
})();
