// Queue order-strategy selector and backend handoff. Loaded before queueView.js.
(function () {
  "use strict";
  function createQueueStrategyModule(deps = {}) {
    const byId = typeof deps.byId === "function" ? deps.byId : () => null;
    const apiGet = typeof deps.apiGet === "function" ? deps.apiGet : async () => ({});
    const apiPost = typeof deps.apiPost === "function" ? deps.apiPost : async () => ({});
    const appendCommandResult = typeof deps.appendCommandResult === "function" ? deps.appendCommandResult : () => {};
    const getRows = typeof deps.getRows === "function" ? deps.getRows : () => [];
    const getActiveStrategy = typeof deps.getActiveStrategy === "function" ? deps.getActiveStrategy : () => "Standard";
    const setActiveStrategy = typeof deps.setActiveStrategy === "function" ? deps.setActiveStrategy : () => {};
    const renderRows = typeof deps.renderRows === "function" ? deps.renderRows : () => {};
    const updateManualOrderControls = typeof deps.updateManualOrderControls === "function" ? deps.updateManualOrderControls : () => {};
    const requestQueueScan = typeof deps.requestQueueScan === "function" ? deps.requestQueueScan : async () => {};
    const document = deps.documentRef || window.document;
    const QUEUE_STRATEGY_ROUTE = deps.strategyRoute || "/api/queue/strategy";

  const QUEUE_STRATEGIES = [
    "Standard",
    "FreshestFirst",
    "ShowComplete",
    "RoundRobin",
    "DeadlineAware",
    "SmallFirst",
    "LargeFirst",
    "ManualOrder",
  ];

  const QUEUE_STRATEGY_DESCRIPTIONS = {
    Standard: "Priority, then Movies, then TV using the normal backend ordering.",
    FreshestFirst: "Put the newest detected work ahead of older rows.",
    ShowComplete: "Group TV work so a show can finish together.",
    RoundRobin: "Alternate across media groups to avoid one bucket dominating.",
    DeadlineAware: "Prefer work with deadline evidence from backend state.",
    SmallFirst: "Run smaller files first when a quick pass is useful.",
    LargeFirst: "Run larger files first when long jobs should start earlier.",
    ManualOrder: "Use the operator-saved order for loaded backend rows.",
  };

  function splitQueueStrategyOptionText(option) {
    const text = String(option?.textContent || option?.value || "").trim();
    const parts = text.split(/\s+[—-]\s+/);
    return {
      title: parts[0] || text,
      detail: parts.slice(1).join(" - ") || QUEUE_STRATEGY_DESCRIPTIONS[option?.value] || "",
    };
  }

  function syncQueueStrategyChoiceGroup() {
    const select = byId("queue-strategy-select");
    const group = document.querySelector("[data-queue-strategy-choice-grid]");
    if (!select || !group) return;
    group.querySelectorAll("input[type='radio']").forEach((radio) => {
      const selected = String(radio.value || "") === String(select.value || "");
      radio.checked = selected;
      radio.closest(".enhanced-choice-card")?.classList.toggle("is-selected", selected);
    });
  }

  function enhanceQueueStrategySelector() {
    const select = byId("queue-strategy-select");
    if (!select || document.querySelector("[data-queue-strategy-choice-grid]")) {
      syncQueueStrategyChoiceGroup();
      return;
    }
    const label = document.querySelector('label[for="queue-strategy-select"]');
    const grid = document.createElement("div");
    grid.className = "enhanced-choice-grid queue-strategy-choice-grid";
    grid.dataset.queueStrategyChoiceGrid = "true";
    grid.setAttribute("role", "radiogroup");
    grid.setAttribute("aria-label", "Queue order strategy");

    Array.from(select.options || []).forEach((option) => {
      const value = String(option.value || "");
      const optionText = splitQueueStrategyOptionText(option);
      const optionId = `queue-strategy-choice-${value.replace(/[^a-z0-9_-]+/gi, "-")}`;
      const card = document.createElement("label");
      card.className = "enhanced-choice-card queue-strategy-choice";
      card.htmlFor = optionId;

      const radio = document.createElement("input");
      radio.type = "radio";
      radio.id = optionId;
      radio.name = "queue-strategy-choice";
      radio.value = value;
      radio.checked = value === String(select.value || "");
      radio.addEventListener("change", () => {
        if (!radio.checked) return;
        select.value = value;
        select.dispatchEvent(new Event("input", { bubbles: true }));
        select.dispatchEvent(new Event("change", { bubbles: true }));
        syncQueueStrategyChoiceGroup();
      });

      const title = document.createElement("span");
      title.className = "enhanced-choice-card-title";
      title.textContent = optionText.title;

      const detail = document.createElement("span");
      detail.className = "enhanced-choice-card-detail";
      detail.textContent = optionText.detail;
      card.append(radio, title, detail);
      grid.appendChild(card);
    });

    if (label) label.classList.add("enhanced-choice-source-label");
    select.classList.add("enhanced-choice-source");
    select.addEventListener("input", syncQueueStrategyChoiceGroup);
    select.addEventListener("change", syncQueueStrategyChoiceGroup);
    select.insertAdjacentElement("afterend", grid);
    syncQueueStrategyChoiceGroup();
  }

  /**
   * Fetch the currently active strategy from the API and update the
   * <select> to reflect it.  Called on queue page show and after a
   * successful strategy change.
   */
  async function loadQueueStrategy() {
    const sel = document.getElementById("queue-strategy-select");
    if (!sel) return;
    try {
      const data = await apiGet(QUEUE_STRATEGY_ROUTE);
      const strategy = data && data.strategy ? String(data.strategy) : "Standard";
      if (QUEUE_STRATEGIES.includes(strategy)) {
        setActiveStrategy(strategy);
        sel.value = strategy;
        syncQueueStrategyChoiceGroup();
      }
      // Show source hint if strategy came from UI override vs default
      const source = data && data.source ? String(data.source) : "default";
      const statusEl = document.getElementById("queue-strategy-status");
      if (statusEl) {
        statusEl.textContent = source === "state_file"
          ? `Active strategy: ${strategy} (saved).`
          : `Active strategy: ${strategy} (config default).`;
      }
      if (getRows().length) renderRows();
      else updateManualOrderControls();
    } catch (_) {
      // Silently ignore — API may not be up yet
      updateManualOrderControls();
    }
  }

  // Revert the selector (and its radio-card mirror) to the last strategy the
  // backend confirmed, so a failed apply does not leave the UI showing an
  // unapplied strategy as if it were active.
  function resetQueueStrategySelectorToActive() {
    const sel = document.getElementById("queue-strategy-select");
    if (!sel) return;
    if (QUEUE_STRATEGIES.includes(getActiveStrategy())) sel.value = getActiveStrategy();
    syncQueueStrategyChoiceGroup();
    updateManualOrderControls();
    if (getRows().length) renderRows();
  }

  /**
   * POST the selected strategy to the API and update the status line.
   * Also refreshes the queue snapshot so the sorted order is visible.
   */
  async function applyQueueStrategy() {
    const sel    = document.getElementById("queue-strategy-select");
    const status = document.getElementById("queue-strategy-status");
    if (!sel) return;

    const strategy = sel.value;
    if (!QUEUE_STRATEGIES.includes(strategy)) {
      if (status) status.textContent = `Unknown strategy: ${strategy}`;
      return;
    }

    if (status) status.textContent = "Saving strategy…";
    try {
      const payload = await apiPost("/api/queue/strategy", { strategy });
      if (payload && payload.ok) {
        if (status) {
          status.textContent = `Strategy set to "${strategy}". Takes effect on next queue build.`;
        }
        appendCommandResult(payload);
        // Reload the strategy display to confirm round-trip
        await loadQueueStrategy();
        updateManualOrderControls();
        await requestQueueScan();
      } else {
        const msg = (payload && payload.message) ? payload.message : "Unknown error.";
        if (status) status.textContent = `Error: ${msg} Selector reset to active strategy "${getActiveStrategy()}".`;
        if (payload) appendCommandResult(payload);
        resetQueueStrategySelectorToActive();
      }
    } catch (err) {
      if (status) status.textContent = `Error: ${err.message || err} Selector reset to active strategy "${getActiveStrategy()}".`;
      resetQueueStrategySelectorToActive();
    }
  }

  function initQueueStrategySelector() {
    enhanceQueueStrategySelector();
    const applyBtn = document.getElementById("queue-strategy-apply-btn");
    if (applyBtn) {
      applyBtn.addEventListener("click", applyQueueStrategy);
    }
    // Populate the select with options that match VALID_STRATEGIES
    // (they are already hard-coded in index.html, so we just load current value)
    loadQueueStrategy();
  }

  // Wire on DOMContentLoaded
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initQueueStrategySelector);
  } else {
    initQueueStrategySelector();
  }


    return { applyQueueStrategy, enhanceQueueStrategySelector, initQueueStrategySelector, loadQueueStrategy, resetQueueStrategySelectorToActive, syncQueueStrategyChoiceGroup };
  }
  window.__queueStrategyModule = { createQueueStrategyModule };
})();
