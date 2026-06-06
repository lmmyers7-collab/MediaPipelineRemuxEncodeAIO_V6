/* global lastRefreshCompletedAt, lastRefreshDurationMs, lastRefreshStartedAt, refreshAll, renderCompleted, renderHomeRecentCompleted, renderTopbarActivity */
(function () {
  let queueRefreshBusy = false;

  function queueRefreshButton() {
    return typeof document.querySelector === "function" ? document.querySelector("[data-queue-refresh-button]") : null;
  }

  function setQueueRefreshButtonBusy(isBusy) {
    queueRefreshBusy = Boolean(isBusy);
    const button = queueRefreshButton();
    if (!button) return;
    button.disabled = Boolean(isBusy);
    button.textContent = isBusy ? "Scanning..." : "Scan Sources";
    if (isBusy) {
      button.setAttribute("aria-busy", "true");
      button.title = "Backend source scan is running. Fast inventory is shown before full queue curation completes.";
    } else {
      button.removeAttribute("aria-busy");
      button.title = "Scan configured source roots and then curate the authoritative backend queue snapshot.";
    }
  }

  function renderQueueRefreshInProgress() {
    setQueueRefreshButtonBusy(true);
    renderTopbarActivity({
      activity: "Scanning",
      current_work: {
        phase_label: "Queue source scan",
        percent_label: "0%",
      },
      progress: {
        CurrentStage: "scanning",
        CurrentStagePercent: 0,
      },
    });
    const ticker = byId("topbar-event-ticker");
    if (ticker) {
      const text = "Latest event: queue source scan requested";
      ticker.textContent = text;
      ticker.title = text;
      ticker.dataset.state = "pending";
    }
    setText("queue-filter-summary", [
      "Queue source scan requested.",
      "The backend builds a fast source inventory first, then curates authoritative queue rows through the queue-plan dry run.",
      "Mutation guardrail: filters, launch scope, queue state commands, source files, and processing commands remain backend-owned.",
    ].join("\n"));
    setText("queue-open-status", "Scanning sources and curating queue snapshot...");
    window.mediaPipelineQueueView?.renderQueueScanLoadingState?.();
  }

  async function refreshCurrentOutputStatus() {
    const button = byId("completed-refresh-current-output-button");
    if (button) button.disabled = true;
    setText("completed-current-status", "Refreshing");
    let scrollSnapshot = null;
    try {
      const [completedRaw, promotionRaw] = await Promise.all([apiGet("/api/completed?limit=all&force_refresh=true&proof=live", {
        timeoutMs: 30000
      }), apiGet("/api/final-library-promotion/status", {
        timeoutMs: 30000
      })]);
      const completed = attachRefreshMetadata("completed", completedRaw);
      const finalLibraryPromotion = attachRefreshMetadata("final library promotion", promotionRaw);
      scrollSnapshot = window.mediaPipelineDom?.captureScrollablePositions?.();
      renderCompleted(completed);
      window.mediaPipelineCompletedView?.renderFinalLibraryPromotion?.(finalLibraryPromotion);
      window.mediaPipelineAppHome?.renderHomePromotionEntry?.(finalLibraryPromotion);
      renderHomeRecentCompleted(completed || {});
      renderTopbarActivity({
        activity: "Current Output Status refreshed from completed history."
      });
      setText("completed-open-status", "Current Output Status refreshed. Destination existence was rechecked; no output was accepted, deleted, moved, rerun, published, or drained.");
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setText("completed-current-status", "Refresh failed");
      setText("completed-current-summary", [`Current Output Status refresh failed: ${message}`, "Safe next step: use Diagnostics > Completed Manifest and Run Logs before rerun, cleanup, drain, deletion, or library decisions.", "Mutation guardrail: failed refresh did not repair, rerun, drain, publish, rewrite manifests, or touch media."].join("\n"));
      renderTopbarActivity({
        activity: `Current Output Status refresh failed: ${message}`
      });
    } finally {
      window.mediaPipelineDom?.restoreScrollablePositions?.(scrollSnapshot);
      if (button) button.disabled = false;
    }
  }

  function refreshTimeLabel(value) {
    if (!value) return "never";
    try {
      return value.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
    } catch {
      return String(value);
    }
  }
  
    function renderRefreshInProgress(options = {}) {
    const node = byId("refresh-health");
    if (node) {
      node.textContent = "Refresh";
      node.dataset.state = "updating";
      node.setAttribute("aria-busy", "true");
      node.title = `Refresh started ${refreshTimeLabel(lastRefreshStartedAt)}. Previous completed refresh: ${refreshTimeLabel(lastRefreshCompletedAt)}.`;
    }
    const button = byId("refresh-button");
    if (button) {
      button.disabled = true;
      button.textContent = "Refresh";
      button.setAttribute("aria-busy", "true");
      button.title = "Refreshing backend health, queue, completed, pending publish, diagnostics, settings, network, schedule, and contract state.";
    }
    if (options && options.queueRefresh === true) setQueueRefreshButtonBusy(true);
  }
  
    function renderRefreshHealth(failures, options = {}) {
    const node = byId("refresh-health");
    const button = byId("refresh-button");
    if (button) {
      button.disabled = false;
      button.textContent = "Refresh";
      button.removeAttribute("aria-busy");
    }
    const queueScanRunning = Boolean(window.mediaPipelineQueueView?.queueScanIsRunning?.());
    if (options && options.queueRefresh === true) {
      setQueueRefreshButtonBusy(queueScanRunning);
    } else if (!queueRefreshBusy || !queueScanRunning) {
      setQueueRefreshButtonBusy(queueScanRunning);
    }
    if (!node) return;
    node.removeAttribute("aria-busy");
    const items = Array.isArray(failures) ? failures : [];
    const timing = `Last refresh: ${refreshTimeLabel(lastRefreshCompletedAt)}${Number.isFinite(lastRefreshDurationMs) ? ` (${lastRefreshDurationMs} ms)` : ""}.`;
    if (!items.length) {
      node.textContent = "Refresh: ok";
      node.dataset.state = "ok";
      node.title = `All backend reads completed. ${timing}`;
      if (button) button.title = `Refresh all WebView read-only state. ${timing}`;
      return;
    }
    node.textContent = `Refresh: ${items.length} issue${items.length === 1 ? "" : "s"}`;
    node.dataset.state = items.some((item) => item.required) ? "failed" : "warning";
    node.title = [...items.map((item) => `${item.name}: ${item.message}`), timing].join("\n");
    if (button) button.title = `Refresh all WebView read-only state. Last result had ${items.length} issue${items.length === 1 ? "" : "s"}.`;
  }
  
    function attachRefreshMetadata(name, payload) {
    if (!payload || typeof payload !== "object") return payload;
    try {
      Object.defineProperty(payload, "__mediaPipelineRefreshMeta", {
        value: {
          name,
          fetched_at: new Date().toISOString(),
          refresh_started_at: lastRefreshStartedAt ? lastRefreshStartedAt.toISOString() : "",
        },
        enumerable: false,
        configurable: true,
      });
    } catch (_) {
      // Read-only/frozen payloads still render; they simply omit WebView refresh metadata.
    }
    return payload;
  }
  
    function initPageRefreshButtons() {
    if (typeof document.querySelectorAll !== "function") return;
    document.querySelectorAll("[data-page-refresh-button]").forEach((button) => {
      button.addEventListener("click", () => refreshAll());
      if (!button.title) {
        button.title = "Refreshes backend read-only state for this page without starting, saving, publishing, repairing, deleting, or moving files.";
      }
    });
  }
  
    function refreshFailure(name, result, required = false) {
    if (result.status === "fulfilled") return null;
    const reason = result.reason;
    return {
      name,
      required,
      message: reason instanceof Error ? reason.message : String(reason),
    };
  }

  /**
   * Public namespace for app refresh helpers.
   * Flat window.* exports remain owned by app.js compatibility wrappers.
   */
  window.mediaPipelineAppRefresh = {
    refreshCurrentOutputStatus,
    refreshTimeLabel,
    renderRefreshInProgress,
    renderRefreshHealth,
    renderQueueRefreshInProgress,
    setQueueRefreshButtonBusy,
    attachRefreshMetadata,
    initPageRefreshButtons,
    refreshFailure
  };
})();
