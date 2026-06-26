(function () {
  const REFRESH_INTERVAL_MS = 2000;
  const DIAGNOSTICS_TIMEOUT_MS = 10000;
  let refreshTimer = null;
  let refreshInFlight = false;
  let lastSuccessfulRefresh = 0;

  function byId(id) {
    return document.getElementById(id);
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

  function renderPipelineLogWindow(diagnostics) {
    const textNode = byId("pipeline-log-window-text");
    const follow = byId("pipeline-log-window-follow");
    if (!textNode) return;

    const shouldFollow = Boolean(follow?.checked) || isNearBottom(textNode);
    const previousScrollTop = textNode.scrollTop;
    const rawLogText = String(diagnostics?.log_tail || "");
    const logText = compactRepeatedProgressLines(rawLogText);
    const nextLogText = logText || "No pipeline log tail loaded.";
    if (textNode.textContent !== nextLogText) textNode.textContent = nextLogText;
    if (shouldFollow) {
      window.requestAnimationFrame(() => scrollToBottom(textNode));
    } else {
      textNode.scrollTop = previousScrollTop;
    }

    lastSuccessfulRefresh = Date.now();
    setUpdated(`Last refresh: ${localTimestamp(new Date(lastSuccessfulRefresh))}`);
    setStatus(rawLogText ? "Loaded" : "Empty", rawLogText ? "ok" : "empty");
    setDetail("Source: GET /api/diagnostics log_tail. This window is read-only and refreshes every 2 seconds.");
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
      const diagnostics = await apiClient.apiGet("/api/diagnostics", {
        timeoutMs: DIAGNOSTICS_TIMEOUT_MS,
      });
      renderPipelineLogWindow(diagnostics);
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
