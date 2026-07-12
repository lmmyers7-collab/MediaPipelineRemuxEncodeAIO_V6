// Queue priority, manual-order, and strategy controls composed for queueView.js.
(function () {
  "use strict";

  const priorityFactory = (window.__queuePriorityModule || {}).createQueuePriorityModule;
  const manualOrderFactory = (window.__queueManualOrderModule || {}).createQueueManualOrderModule;
  const strategyFactory = (window.__queueStrategyModule || {}).createQueueStrategyModule;
  delete window.__queuePriorityModule;
  delete window.__queueManualOrderModule;
  delete window.__queueStrategyModule;

  function createQueueControlsModule(deps = {}) {
    const {
      appendCommandResult = () => {},
      apiGet = async () => ({}),
      apiPost = async () => ({}),
      byId = () => null,
      documentRef = document,
      getExcludedRows = () => [],
      getPayload = () => ({}),
      getRows = () => [],
      getScanLoading = () => false,
      getSelectedPriorityRows = () => [],
      initQueueRerunEvents = () => {},
      initQueueTabNav = () => {},
      moveQueueTablePage = () => {},
      refreshAll = async () => {},
      renderBreakdown = () => {},
      renderRows = () => {},
      renderSummary = () => {},
      requestQueueScan = () => {},
      setPayload = () => {},
      setRows = () => {},
      setText = () => {},
      state = {},
      strategyRoute = "",
      syncSelectedRows = () => {},
      queuePriorityRoute = "",
      queueRowKey = () => "",
    } = deps;
    const noop = () => {};
    const emptyArray = () => [];
    const emptyString = () => "";
    const identity = (value) => value;
    const falseValue = () => false;
    let updateManualOrderControls = noop;

    const priority = typeof priorityFactory === "function"
      ? priorityFactory({
        appendCommandResult,
        apiPost,
        byId,
        filteredRows: () => deps.filteredRows?.() || [],
        getExcludedRows,
        getPayload,
        getRows,
        getScanLoading,
        getSelectedRows: getSelectedPriorityRows,
        overrideMarkers: deps.overrideMarkers,
        refreshAll,
        renderBreakdown,
        renderRows,
        renderSummary,
        setPayload,
        setRows,
        setText,
        syncSelectedRows,
        updateManualOrderControls: (...args) => updateManualOrderControls(...args),
      })
      : {};
    const {
      applyDisplayedFileOverrideMarker = noop,
      beginCommand: beginPriorityCommand = () => 0,
      clearPriorityManifest = noop,
      confirmBulk = () => true,
      endCommand: endPriorityCommand = noop,
      getInFlight: isPriorityCommandInFlight = falseValue,
      isCurrentCommand: isCurrentPriorityCommand = falseValue,
      normalizedLevel: priorityNormalizedLevel = emptyString,
      pathKey: priorityPathKey = emptyString,
      priorityItemsForSelected = emptyArray,
      refreshDisplayedRows: refreshPriorityRows = noop,
      rowHasVisibleMarker: priorityRowHasVisibleMarker = falseValue,
      rowMatchesPath: priorityRowMatchesPath = falseValue,
      rowPath: priorityRowPath = emptyString,
      rowWithDisplayedFileOverrideMarker = identity,
      sendPriorityBulk = noop,
      sendSelectedPriority = noop,
      updateControls: updatePriorityControls = noop,
    } = priority;

    const manualOrder = typeof manualOrderFactory === "function"
      ? manualOrderFactory({
        state,
        apiPost,
        appendCommandResult,
        beginQueuePriorityCommand: beginPriorityCommand,
        byId,
        endQueuePriorityCommand: endPriorityCommand,
        getQueueScanLoading: getScanLoading,
        getSelectedQueuePriorityRows: getSelectedPriorityRows,
        isCurrentQueuePriorityCommand: isCurrentPriorityCommand,
        isQueuePriorityCommandInFlight: isPriorityCommandInFlight,
        moveQueueTablePage,
        queuePriorityNormalizedLevel: priorityNormalizedLevel,
        queuePriorityRowPath: priorityRowPath,
        queueRowKey,
        refreshDisplayedQueuePriorityRows: refreshPriorityRows,
        renderQueueRows: renderRows,
        sendQueuePriorityBulk: sendPriorityBulk,
        setText,
        updateQueuePriorityControls: updatePriorityControls,
      })
      : {};
    const {
      resetQueueManualOrderLoadedKeys = noop,
      queueManualOrderIsEnabled = falseValue,
      updateQueueManualOrderControls: updateManualControls = noop,
      wireQueueManualOrderRow = noop,
      initQueueManualOrderToolbar = noop,
    } = manualOrder;
    updateManualOrderControls = updateManualControls;

    function initQueuePriorityToolbar() {
      const wire = (id, handler) => {
        const button = byId(id);
        if (button) button.addEventListener("click", handler);
      };
      wire("queue-priority-promote-btn", () => sendSelectedPriority("high", "Operator promoted via toolbar"));
      wire("queue-priority-normal-btn", () => sendSelectedPriority("normal", ""));
      wire("queue-priority-low-btn", () => sendSelectedPriority("low", "Operator demoted via toolbar"));
      wire("queue-priority-hold-btn", () => sendSelectedPriority("hold", "Operator hold via toolbar"));
      const refreshButton = typeof documentRef.querySelector === "function"
        ? documentRef.querySelector("[data-queue-refresh-button]")
        : null;
      if (refreshButton) refreshButton.addEventListener("click", requestQueueScan);

      const sendBulkForMediaType = (mediaType, label) => {
        const items = getRows()
          .filter((row) => String(row.media_type || "").toLowerCase() === mediaType)
          .map((row) => ({ path: row.source_path || row.relative_path || "", level: "high", reason: `Bulk promote all ${label}` }))
          .filter((item) => item.path);
        if (!confirmBulk(mediaType, items)) {
          setText("queue-priority-status", `Loaded-row ${label} priority update cancelled before any backend request.`);
          return;
        }
        sendPriorityBulk(items, `Promoted ${items.length} loaded ${label} row(s) to High.`);
      };
      wire("queue-priority-promote-movies-btn", () => sendBulkForMediaType("movie", "Movie"));
      wire("queue-priority-promote-tv-btn", () => sendBulkForMediaType("tv", "TV"));
      wire("queue-priority-clear-all-btn", clearPriorityManifest);
      updatePriorityControls();
    }

    const strategy = typeof strategyFactory === "function"
      ? strategyFactory({
        apiGet,
        apiPost,
        appendCommandResult,
        byId,
        documentRef,
        getActiveStrategy: () => state.activeStrategy,
        getRows,
        renderRows,
        setActiveStrategy: (value) => { state.activeStrategy = value; },
        strategyRoute,
        updateManualOrderControls: (...args) => updateManualOrderControls(...args),
      })
      : {};
    const { loadQueueStrategy = noop } = strategy;

    function wireQueuePanelVisibilityObserver() {
      const panel = typeof documentRef.querySelector === "function"
        ? documentRef.querySelector('[data-page-panel="queue"]')
        : null;
      const Observer = typeof MutationObserver === "function" ? MutationObserver : window.MutationObserver;
      if (!panel || typeof Observer !== "function") return;
      let wasVisible = panel.classList.contains("is-visible");
      new Observer(() => {
        const isNowVisible = panel.classList.contains("is-visible");
        if (isNowVisible && !wasVisible) loadQueueStrategy();
        wasVisible = isNowVisible;
      }).observe(panel, { attributes: true, attributeFilter: ["class"] });
    }

    function initQueueControlsLifecycle() {
      const initialize = () => {
        initQueueTabNav();
        initQueueRerunEvents();
        initQueuePriorityToolbar();
        initQueueManualOrderToolbar();
      };
      if (documentRef.readyState === "loading") {
        documentRef.addEventListener("DOMContentLoaded", initialize);
      } else {
        initialize();
      }
      wireQueuePanelVisibilityObserver();
    }

    initQueueControlsLifecycle();
    return {
      applyDisplayedFileOverrideMarker,
      clearPriorityManifest,
      priorityItemsForSelected,
      priorityPathKey,
      priorityRowHasVisibleMarker,
      priorityRowMatchesPath,
      rowWithDisplayedFileOverrideMarker,
      queueManualOrderIsEnabled,
      resetQueueManualOrderLoadedKeys,
      sendSelectedPriority,
      updateManualOrderControls,
      wireQueueManualOrderRow,
    };
  }

  window.__queueControlsModule = { createQueueControlsModule };
})();
