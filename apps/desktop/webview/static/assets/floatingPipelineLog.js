(function () {
  const REFRESH_INTERVAL_MS = 2000;
  const DIAGNOSTICS_TIMEOUT_MS = 10000;
  let refreshTimer = null;
  let refreshInFlight = false;
  let lastSuccessfulRefresh = 0;
  let lastDiagnosticsPayload = null;
  let isOpen = false;
  let dragState = null;
  let hasCustomPosition = false;

  function byId(id) {
    return document.getElementById(id);
  }

  function panelNode() {
    return byId("floating-pipeline-log-panel");
  }

  function topbarButton() {
    return byId("pipeline-log-window-button");
  }

  function isCompactLayout() {
    return window.matchMedia?.("(max-width: 720px)")?.matches === true;
  }

  function clearCustomPosition() {
    const panel = panelNode();
    if (!panel) return;
    panel.style.left = "";
    panel.style.top = "";
    panel.style.right = "";
    panel.style.bottom = "";
    hasCustomPosition = false;
  }

  function clampPanelPosition(left, top) {
    const panel = panelNode();
    if (!panel) return { left, top };
    const width = panel.offsetWidth || panel.getBoundingClientRect?.().width || 0;
    const height = panel.offsetHeight || panel.getBoundingClientRect?.().height || 0;
    const maxLeft = Math.max(0, window.innerWidth - width);
    const maxTop = Math.max(0, window.innerHeight - height);
    return {
      left: Math.min(Math.max(0, left), maxLeft),
      top: Math.min(Math.max(0, top), maxTop),
    };
  }

  function applyPanelPosition(left, top) {
    const panel = panelNode();
    if (!panel) return;
    const nextPosition = clampPanelPosition(left, top);
    panel.style.left = `${Math.round(nextPosition.left)}px`;
    panel.style.top = `${Math.round(nextPosition.top)}px`;
    panel.style.right = "auto";
    panel.style.bottom = "auto";
    hasCustomPosition = true;
  }

  function keepPanelInsideViewport() {
    const panel = panelNode();
    if (!panel) return;
    if (isCompactLayout()) {
      clearCustomPosition();
      return;
    }
    if (!hasCustomPosition) return;
    const rect = panel.getBoundingClientRect();
    applyPanelPosition(rect.left, rect.top);
  }

  function isInteractiveDragTarget(target) {
    if (!target || typeof target.closest !== "function") return false;
    return Boolean(target.closest("button, input, label, select, textarea, a, [data-no-drag]"));
  }

  function setStatus(label, state, title) {
    const status = byId("floating-pipeline-log-status");
    if (!status) return;
    status.textContent = label;
    status.dataset.state = state || "unknown";
    status.title = title || "";
  }

  function setUpdated(value) {
    const updated = byId("floating-pipeline-log-updated");
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

  function setButtonOpenState(open) {
    const button = topbarButton();
    if (!button) return;
    button.setAttribute("aria-pressed", open ? "true" : "false");
    button.dataset.state = open ? "active" : "";
  }

  function setPanelOpenState(open) {
    const panel = panelNode();
    isOpen = Boolean(open);
    setButtonOpenState(isOpen);
    if (!panel) return;
    panel.hidden = !isOpen;
    panel.setAttribute("aria-hidden", isOpen ? "false" : "true");
    if (isOpen) keepPanelInsideViewport();
  }

  function renderFloatingPipelineLog(diagnostics) {
    lastDiagnosticsPayload = diagnostics || {};
    const textNode = byId("floating-pipeline-log-text");
    const follow = byId("floating-pipeline-log-follow");
    const rawLogText = String(lastDiagnosticsPayload?.log_tail || "");
    const logText = compactRepeatedProgressLines(rawLogText);

    if (textNode) {
      const shouldFollow = Boolean(follow?.checked) || isNearBottom(textNode);
      const previousScrollTop = textNode.scrollTop;
      const nextLogText = logText || "No pipeline log tail loaded.";
      if (textNode.textContent !== nextLogText) textNode.textContent = nextLogText;
      if (shouldFollow) {
        window.requestAnimationFrame(() => scrollToBottom(textNode));
      } else {
        textNode.scrollTop = previousScrollTop;
      }
    }

    lastSuccessfulRefresh = Date.now();
    setUpdated(`Last refresh: ${localTimestamp(new Date(lastSuccessfulRefresh))}`);
    setStatus(rawLogText ? "Loaded" : "Empty", rawLogText ? "ok" : "empty");
  }

  function renderRefreshError(error) {
    const message = error && error.message ? error.message : String(error || "Unknown diagnostics error");
    const stale = lastSuccessfulRefresh > 0;
    setStatus(stale ? "Stale" : "Read failed", stale ? "stale" : "error", message);
    setUpdated(stale ? `Last good refresh: ${localTimestamp(new Date(lastSuccessfulRefresh))}` : `Read failed: ${message}`);
    if (!stale) {
      const textNode = byId("floating-pipeline-log-text");
      if (textNode) textNode.textContent = "Unable to load pipeline log.";
    }
  }

  async function refreshFloatingPipelineLog() {
    if (refreshInFlight) return;
    refreshInFlight = true;
    const refreshButton = byId("floating-pipeline-log-refresh-button");
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
      renderFloatingPipelineLog(diagnostics);
    } catch (error) {
      renderRefreshError(error);
    } finally {
      refreshInFlight = false;
      if (refreshButton) refreshButton.disabled = false;
    }
  }

  function startRefreshTimer() {
    if (refreshTimer) window.clearInterval(refreshTimer);
    refreshTimer = window.setInterval(refreshFloatingPipelineLog, REFRESH_INTERVAL_MS);
  }

  function stopRefreshTimer() {
    if (!refreshTimer) return;
    window.clearInterval(refreshTimer);
    refreshTimer = null;
  }

  function openFloatingPipelineLog() {
    setPanelOpenState(true);
    if (lastDiagnosticsPayload) renderFloatingPipelineLog(lastDiagnosticsPayload);
    startRefreshTimer();
    refreshFloatingPipelineLog();
    return { opened: true };
  }

  function closeFloatingPipelineLog() {
    stopRefreshTimer();
    setPanelOpenState(false);
    setStatus("Closed", "empty");
    return { opened: false };
  }

  function toggleFloatingPipelineLog() {
    return isOpen ? closeFloatingPipelineLog() : openFloatingPipelineLog();
  }

  function startPanelDrag(event) {
    const panel = panelNode();
    if (!panel || !isOpen || isCompactLayout() || isInteractiveDragTarget(event.target)) return;
    if (event.button !== undefined && event.button !== 0) return;

    const rect = panel.getBoundingClientRect();
    dragState = {
      pointerId: event.pointerId,
      offsetX: event.clientX - rect.left,
      offsetY: event.clientY - rect.top,
    };
    panel.classList.add("floating-pipeline-log--dragging");
    panel.setPointerCapture?.(event.pointerId);
    event.preventDefault();
  }

  function movePanelDrag(event) {
    const panel = panelNode();
    if (!panel || !dragState || dragState.pointerId !== event.pointerId) return;
    applyPanelPosition(event.clientX - dragState.offsetX, event.clientY - dragState.offsetY);
    event.preventDefault();
  }

  function stopPanelDrag(event) {
    const panel = panelNode();
    if (!panel || !dragState || dragState.pointerId !== event.pointerId) return;
    panel.classList.remove("floating-pipeline-log--dragging");
    panel.releasePointerCapture?.(event.pointerId);
    dragState = null;
  }

  function initFloatingPipelineLogDragEvents() {
    const panel = panelNode();
    if (!panel || panel.dataset.floatingPipelineLogDragBound === "true") return;
    panel.dataset.floatingPipelineLogDragBound = "true";
    const header = panel.querySelector(".floating-pipeline-log-header");
    if (!header) return;
    header.addEventListener("pointerdown", startPanelDrag);
    panel.addEventListener("pointermove", movePanelDrag);
    panel.addEventListener("pointerup", stopPanelDrag);
    panel.addEventListener("pointercancel", stopPanelDrag);
    window.addEventListener("resize", keepPanelInsideViewport);
  }

  function initFloatingPipelineLogEvents() {
    const button = topbarButton();
    if (button && button.dataset.floatingPipelineLogBound !== "true") {
      button.dataset.floatingPipelineLogBound = "true";
      button.addEventListener("click", (event) => {
        event.preventDefault();
        toggleFloatingPipelineLog();
      });
    }

    const refreshButton = byId("floating-pipeline-log-refresh-button");
    if (refreshButton && refreshButton.dataset.floatingPipelineLogBound !== "true") {
      refreshButton.dataset.floatingPipelineLogBound = "true";
      refreshButton.addEventListener("click", () => refreshFloatingPipelineLog());
    }

    const closeButton = byId("floating-pipeline-log-close-button");
    if (closeButton && closeButton.dataset.floatingPipelineLogBound !== "true") {
      closeButton.dataset.floatingPipelineLogBound = "true";
      closeButton.addEventListener("click", () => closeFloatingPipelineLog());
    }

    document.addEventListener("keydown", (event) => {
      const panel = panelNode();
      if (event.key === "Escape" && isOpen && panel && panel.contains(document.activeElement)) {
        closeFloatingPipelineLog();
      }
    });

    window.addEventListener("beforeunload", stopRefreshTimer);
    initFloatingPipelineLogDragEvents();
    setPanelOpenState(false);
  }

  /**
   * Public namespace for the floating Pipeline Log overlay module.
   * Prefer this namespace from new code; flat window.* exports are intentionally not added for this read-only overlay.
   */
  window.mediaPipelineFloatingPipelineLog = {
    initFloatingPipelineLogEvents,
    toggleFloatingPipelineLog,
    openFloatingPipelineLog,
    closeFloatingPipelineLog,
    refreshFloatingPipelineLog,
    renderFloatingPipelineLog,
    initFloatingPipelineLogDragEvents,
    compactRepeatedProgressLines,
    refreshIntervalMs: REFRESH_INTERVAL_MS,
  };
})();
