(function () {
  function createQueueTabsModule({ updateQueueRerunButtonState, refreshRerunResults } = {}) {
      const QUEUE_TAB_STORAGE_KEY = "mediapipeline-queue-tab";

      function queueTabIds() {
        return ["main", "rerun"];
      }

      function activateQueueTab(tabId, options = {}) {
        const page = document.querySelector('[data-page-panel="queue"]');
        if (!page) return;
        const selected = queueTabIds().includes(tabId) ? tabId : "main";
        const persist = options?.persist !== false;
        const buttons = Array.from(page.querySelectorAll(".settings-tab-btn[data-queue-tab]"));
        const panels = Array.from(page.querySelectorAll(":scope > .queue-tab-panel[data-queue-tab-panel]"));
        buttons.forEach((button) => {
          const active = button.dataset.queueTab === selected;
          button.setAttribute("aria-selected", String(active));
        });
        panels.forEach((panel) => {
          const active = panel.dataset.queueTabPanel === selected;
          panel.classList.toggle("is-active", active);
        });
        if (persist) {
          try { localStorage.setItem(QUEUE_TAB_STORAGE_KEY, selected); } catch (_) {}
        }
        if (typeof window.mediaPipelineAppLifecycle?.syncTabAccessibility === "function") window.mediaPipelineAppLifecycle.syncTabAccessibility();
        if (typeof updatePagePanelEmptyStates === "function") updatePagePanelEmptyStates();
        if (selected === "rerun") {
          updateQueueRerunButtonState();
          refreshRerunResults({ quiet: true }).catch(() => {});
        }
      }

      function initQueueTabNav() {
        const page = document.querySelector('[data-page-panel="queue"]');
        if (!page || page.dataset.queueTabsBound === "true") return;
        const buttons = Array.from(page.querySelectorAll(".settings-tab-btn[data-queue-tab]"));
        const panels = Array.from(page.querySelectorAll(":scope > .queue-tab-panel[data-queue-tab-panel]"));
        if (!buttons.length || !panels.length) return;
        page.dataset.queueTabsBound = "true";
        buttons.forEach((button) => {
          button.addEventListener("click", () => activateQueueTab(button.dataset.queueTab || "main"));
          button.addEventListener("keydown", (event) => {
            const keys = ["ArrowLeft", "ArrowRight", "Home", "End"];
            if (!keys.includes(event.key)) return;
            event.preventDefault();
            const current = buttons.indexOf(button);
            const next = event.key === "Home" ? 0 : event.key === "End" ? buttons.length - 1 : (current + (event.key === "ArrowRight" ? 1 : -1) + buttons.length) % buttons.length;
            buttons[next].focus();
            activateQueueTab(buttons[next].dataset.queueTab || "main");
          });
        });
        let stored = "main";
        try { stored = localStorage.getItem(QUEUE_TAB_STORAGE_KEY) || "main"; } catch (_) {}
        activateQueueTab(stored);
      }

    return { queueTabIds, activateQueueTab, initQueueTabNav };
  }

  window.__queueTabsModule = { createQueueTabsModule };
})();
