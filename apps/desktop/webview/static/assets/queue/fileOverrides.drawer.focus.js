// queue/fileOverrides.drawer.focus.js
// Focus management for the Queue file override drawer and series modal.

(function initFileOverridesDrawerFocusModule() {
  function createFileOverridesDrawerFocusModule(ctx) {
    const {
      documentRef: document,
      windowRef: window,
      state,
      DRAWER_FOCUSABLE_SELECTOR,
      byId,
    } = ctx;

    function requestCloseFileSettingsDrawer() { return ctx.requestCloseFileSettingsDrawer(); }
    function setSeriesStatus(message, tone) { return ctx.series.setSeriesStatus(message, tone); }

  function isHTMLElement(value) {
    if (!value || typeof value !== "object") return false;
    if (typeof HTMLElement === "function") return value instanceof HTMLElement;
    return value.nodeType === 1;
  }

  function fileSettingsTriggerFromOptions(options) {
    if (isHTMLElement(options?.trigger)) return options.trigger;
    return isHTMLElement(document.activeElement) ? document.activeElement : null;
  }

  function isFileSettingsDrawerOpen() {
    const drawer = byId("fo-drawer");
    return Boolean(drawer && !drawer.hidden);
  }

  function fileSettingsElementIsHidden(element) {
    if (!element || element.hidden) return true;
    if (typeof element.closest === "function" && element.closest("[hidden]")) return true;
    if (typeof window.getComputedStyle === "function") {
      const style = window.getComputedStyle(element);
      if (style.display === "none" || style.visibility === "hidden") return true;
    }
    return false;
  }

  function getFileSettingsDrawerFocusableElements() {
    const drawer = byId("fo-drawer");
    if (!drawer || drawer.hidden || typeof drawer.querySelectorAll !== "function") return [];
    return Array.from(drawer.querySelectorAll(DRAWER_FOCUSABLE_SELECTOR)).filter((element) => {
      if (!isHTMLElement(element)) return false;
      if (element.disabled) return false;
      if (element.getAttribute("aria-hidden") === "true") return false;
      return !fileSettingsElementIsHidden(element);
    });
  }

  function focusInitialFileSettingsDrawerControl() {
    const drawer = byId("fo-drawer");
    if (!drawer || drawer.hidden) return;
    const focusable = getFileSettingsDrawerFocusableElements();
    const target = focusable[0] || drawer;
    if (target && typeof target.focus === "function") target.focus();
  }

  function restoreFileSettingsDrawerFocus() {
    const trigger = state.fileSettingsDrawerTrigger;
    state.fileSettingsDrawerTrigger = null;
    if (
      trigger &&
      trigger.isConnected &&
      typeof trigger.focus === "function" &&
      !trigger.disabled
    ) {
      trigger.focus();
    }
  }

  function handleFileSettingsDrawerKeydown(event) {
    if (!isFileSettingsDrawerOpen()) return;
    if (isSeriesModalOpen()) {
      if (event.key === "Escape") {
        event.preventDefault();
        closeSeriesModal();
        return;
      }
      if (event.key === "Tab") handleSeriesModalTab(event);
      return;
    }
    if (event.key === "Escape") {
      event.preventDefault();
      requestCloseFileSettingsDrawer();
      return;
    }
    if (event.key !== "Tab") return;
    const drawer = byId("fo-drawer");
    const focusable = getFileSettingsDrawerFocusableElements();
    if (!focusable.length) {
      event.preventDefault();
      if (drawer && typeof drawer.focus === "function") drawer.focus();
      return;
    }
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    const active = document.activeElement;
    if (event.shiftKey && active === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && active === last) {
      event.preventDefault();
      first.focus();
    }
  }
  function isSeriesModalOpen() {
    const modal = byId("fo-series-modal");
    return Boolean(modal && !modal.hidden);
  }

  function openSeriesModal(trigger) {
    const modal = byId("fo-series-modal");
    if (!modal) return;
    state.foSeriesModalTrigger = trigger || document.activeElement;
    hideDrawerForSeriesModal();
    modal.hidden = false;
    modal.removeAttribute("aria-hidden");
    const focusTarget = byId("fo-series-apply") || byId("fo-series-modal-close") || modal;
    setTimeout(() => {
      if (focusTarget && typeof focusTarget.focus === "function") focusTarget.focus();
    }, 0);
  }

  function closeSeriesModal({ restoreFocus = true, restoreDrawer = true } = {}) {
    const modal = byId("fo-series-modal");
    if (modal) {
      modal.hidden = true;
      modal.setAttribute("aria-hidden", "true");
    }
    setSeriesStatus("");
    if (restoreDrawer) {
      restoreDrawerAfterSeriesModal();
    } else {
      state.foDrawerHiddenForSeriesModal = false;
    }
    if (restoreFocus) {
      const trigger = state.foSeriesModalTrigger;
      if (trigger && trigger.isConnected && typeof trigger.focus === "function" && !trigger.disabled) {
        trigger.focus();
      }
    }
    state.foSeriesModalTrigger = null;
  }

  function hideDrawerForSeriesModal() {
    const overlay = byId("fo-overlay");
    const drawer = byId("fo-drawer");
    if (!drawer || drawer.hidden) return;
    state.foDrawerHiddenForSeriesModal = true;
    if (overlay) {
      overlay.hidden = true;
      overlay.setAttribute("aria-hidden", "true");
    }
    drawer.hidden = true;
    drawer.setAttribute("aria-hidden", "true");
  }

  function restoreDrawerAfterSeriesModal() {
    if (!state.foDrawerHiddenForSeriesModal) return;
    const overlay = byId("fo-overlay");
    const drawer = byId("fo-drawer");
    if (overlay) {
      overlay.hidden = false;
      overlay.removeAttribute("aria-hidden");
    }
    if (drawer) {
      drawer.hidden = false;
      drawer.removeAttribute("aria-hidden");
    }
    state.foDrawerHiddenForSeriesModal = false;
  }

  function getSeriesModalFocusableElements() {
    const modal = byId("fo-series-modal");
    if (!modal || modal.hidden || typeof modal.querySelectorAll !== "function") return [];
    return Array.from(modal.querySelectorAll(DRAWER_FOCUSABLE_SELECTOR)).filter((element) => {
      if (!isHTMLElement(element)) return false;
      if (element.disabled) return false;
      if (element.getAttribute("aria-hidden") === "true") return false;
      return !fileSettingsElementIsHidden(element);
    });
  }

  function handleSeriesModalTab(event) {
    const focusable = getSeriesModalFocusableElements();
    const modal = byId("fo-series-modal");
    if (!focusable.length) {
      event.preventDefault();
      if (modal && typeof modal.focus === "function") modal.focus();
      return;
    }
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    const active = document.activeElement;
    if (event.shiftKey && active === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && active === last) {
      event.preventDefault();
      first.focus();
    }
  }

    return {
      isHTMLElement,
      fileSettingsTriggerFromOptions,
      isFileSettingsDrawerOpen,
      fileSettingsElementIsHidden,
      getFileSettingsDrawerFocusableElements,
      focusInitialFileSettingsDrawerControl,
      restoreFileSettingsDrawerFocus,
      handleFileSettingsDrawerKeydown,
      isSeriesModalOpen,
      openSeriesModal,
      closeSeriesModal,
      hideDrawerForSeriesModal,
      restoreDrawerAfterSeriesModal,
      getSeriesModalFocusableElements,
      handleSeriesModalTab,
    };
  }

  window.__queueFileOverridesDrawerFocusModule = { createFileOverridesDrawerFocusModule };
})();
