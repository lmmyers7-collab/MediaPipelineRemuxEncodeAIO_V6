/* global ADVANCED_MODE_STORAGE_KEY, EVIDENCE_HIDDEN_STORAGE_KEY, applyAdvancedModePreference, applyEvidenceHiddenPreference, applyThemePreference, closeReadinessRequiresWarning, readBooleanUiPreference, showPage, updatePagePanelEmptyStates */
(function () {
  const LAYOUT_STORAGE_KEY = "mediapipeline-layout-v1";

  const _layoutDragHintTimers = new WeakMap();

  const _layoutDefaultOrders = new Map();

  const _layoutDefaultPanelState = new Map();

  const _layoutContainersByKey = new Map();

  const _layoutPreviewTimers = new WeakMap();

  const _layoutDrawerState = {
    selectedContainerKey: "",
    selectedPanelKey: "",
    dragSource: null,
    pointerDrag: null,
    pointerDragCleanup: null,
    resetAllArmed: false,
    resetAllForced: false,
    resetAllTimer: null,
  };

  function _layoutSlug(text) {
    return String(text || "")
      .trim()
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "");
  }

  function _panelKey(containerKey, panel) {
    const h = panel.querySelector(".panel-heading h2, .panel-heading h3");
    const label = h ? h.textContent.trim() : "";
    return `${containerKey}::${_layoutSlug(label || "panel")}`;
  }

  function _layoutPageIdFor(container) {
    const page = container?.classList?.contains("page")
      ? container
      : container?.closest?.(".page[data-page-panel]");
    return page?.dataset?.pagePanel || "page";
  }

  function _layoutContainerKey(container) {
    if (!container) return "page";
    const pageId = _layoutPageIdFor(container);
    if (container.classList?.contains("page")) return pageId;
    const tabPairs = [
      ["settingsTab", "settings"],
      ["diagTab", "diagnostics"],
      ["completedTab", "completed"],
      ["launchTabPanel", "launch"],
      ["queueTabPanel", "queue"],
      ["reportsTabPanel", "reports"],
    ];
    for (const [datasetKey, label] of tabPairs) {
      if (container.dataset?.[datasetKey]) {
        return `${pageId}::${label}-${_layoutSlug(container.dataset[datasetKey])}`;
      }
    }
    if (container.id) return `${pageId}::${_layoutSlug(container.id)}`;
    const parentPanel = container.closest?.("section.panel[data-panel-key]");
    if (parentPanel?.dataset?.panelKey) return `${parentPanel.dataset.panelKey}::subsections`;
    return `${pageId}::container-${_layoutSlug(container.className || "subsections")}`;
  }

  function _layoutTabPaneKey(pane) {
    if (!pane) return "";
    const pageId = _layoutPageIdFor(pane);
    const tabPairs = [
      ["settingsTab", "settings"],
      ["diagTab", "diagnostics"],
      ["completedTab", "completed"],
      ["launchTabPanel", "launch"],
      ["queueTabPanel", "queue"],
      ["reportsTabPanel", "reports"],
    ];
    for (const [datasetKey, label] of tabPairs) {
      if (pane.dataset?.[datasetKey] !== undefined) {
        return `${pageId}::${label}-${_layoutSlug(pane.dataset[datasetKey])}`;
      }
    }
    return "";
  }

  function _layoutActivePage() {
    return document.querySelector(".page[data-page-panel].is-visible")
      || document.querySelector(".page[data-page-panel]");
  }

  function _layoutPageLabel(page) {
    if (!page) return "Page";
    const pageId = page.dataset?.pagePanel || "";
    const nav = pageId ? document.querySelector(`.nav-button[data-page="${pageId}"]`) : null;
    const label = nav?.textContent?.trim() || page.querySelector("h1")?.textContent?.trim() || pageId || "Page";
    return label;
  }

  function _layoutContainerLabel(container) {
    if (!container) return "Page";
    if (container.classList?.contains("page")) return "Page";
    return _layoutPaneTitle(container) || "Subtab";
  }

  function _layoutPanelTitle(panel) {
    const h = panel?.querySelector?.(".panel-heading h2, .panel-heading h3");
    return h?.textContent?.trim() || "Panel";
  }

  function _layoutPanelIsEditorExcluded(panel) {
    return Boolean(panel?.hasAttribute?.("data-layout-editor-exclude"));
  }

  function _layoutPanelsInContainer(container) {
    if (!container) return [];
    return Array.from(container.querySelectorAll(":scope > section.panel[data-panel-key]"))
      .filter((panel) => !_layoutPanelIsEditorExcluded(panel));
  }

  function _layoutSetStatus(message) {
    const status = byId("layout-editor-status");
    if (status) status.textContent = message || "Choose a panel to preview or adjust its layout.";
  }

  function _loadLayout() {
    try { return JSON.parse(localStorage.getItem(LAYOUT_STORAGE_KEY) || "{}"); } catch (_) { return {}; }
  }

  function _saveLayout(state) {
    try { localStorage.setItem(LAYOUT_STORAGE_KEY, JSON.stringify(state)); } catch (_) {}
  }

  function _layoutSetPanelType(panel, panelType) {
    const normalized = String(panelType || "").trim();
    if (normalized) {
      panel.dataset.panelType = normalized;
    } else {
      delete panel.dataset.panelType;
    }
  }

  function _layoutDefaultPanelType(panel) {
    return String(panel?.dataset?.layoutDefaultPanelType || "");
  }

  function _layoutPanelIsEvidence(panel) {
    return panel?.dataset?.panelType === "evidence";
  }

  function _layoutPanelIsAuthoredEvidence(panel) {
    return _layoutDefaultPanelType(panel) === "evidence";
  }

  function _updateCustomizeBar(panel) {
    const bar = panel.querySelector(".panel-customize-bar");
    if (!bar) return;
    const btnAdv = bar.querySelector(".pcb-btn-advanced");
    const btnHid = bar.querySelector(".pcb-btn-hidden");
    const isAdv = panel.hasAttribute("data-panel-advanced");
    const isHid = panel.hasAttribute("data-panel-hidden");
    if (btnAdv) {
      btnAdv.setAttribute("aria-pressed", String(isAdv));
      btnAdv.dataset.state = isAdv ? "on" : "off";
      btnAdv.title = isAdv
        ? "Panel is behind the Advanced gate — click to make always visible"
        : "Click to move panel behind the Advanced gate";
    }
    if (btnHid) {
      btnHid.setAttribute("aria-pressed", String(isHid));
      btnHid.dataset.state = isHid ? "on" : "off";
      btnHid.title = isHid
        ? "Panel is hidden — click to restore visibility"
        : "Click to hide this panel";
    }
  }

  function _injectCustomizeBar(panel, title) {
    if (panel.querySelector(".panel-customize-bar")) return;
    const bar = document.createElement("div");
    bar.className = "panel-customize-bar";
    bar.setAttribute("aria-hidden", "true");

    const handle = document.createElement("span");
    handle.className = "pcb-drag-handle";
    handle.textContent = "⠿";
    handle.title = "Drag to reorder";

    const nameEl = document.createElement("span");
    nameEl.className = "pcb-panel-name";
    nameEl.textContent = title || "Panel";

    const actions = document.createElement("div");
    actions.className = "pcb-actions";

    const btnUp = document.createElement("button");
    btnUp.type = "button";
    btnUp.className = "pcb-btn-move pcb-btn-move-up";
    btnUp.textContent = "↑";
    btnUp.setAttribute("aria-label", `Move ${title || "panel"} up`);
    btnUp.title = "Move this panel up";

    const btnDown = document.createElement("button");
    btnDown.type = "button";
    btnDown.className = "pcb-btn-move pcb-btn-move-down";
    btnDown.textContent = "↓";
    btnDown.setAttribute("aria-label", `Move ${title || "panel"} down`);
    btnDown.title = "Move this panel down";

    const btnAdv = document.createElement("button");
    btnAdv.type = "button";
    btnAdv.className = "pcb-btn-advanced";
    btnAdv.textContent = "Advanced";
    btnAdv.setAttribute("aria-pressed", "false");

    const btnHid = document.createElement("button");
    btnHid.type = "button";
    btnHid.className = "pcb-btn-hidden";
    btnHid.textContent = "Hidden";
    btnHid.setAttribute("aria-pressed", "false");

    actions.appendChild(btnUp);
    actions.appendChild(btnDown);
    actions.appendChild(btnAdv);
    actions.appendChild(btnHid);
    bar.appendChild(handle);
    bar.appendChild(nameEl);
    bar.appendChild(actions);

    // Insert bar as the very first child of the panel so it sits above all content.
    panel.insertBefore(bar, panel.firstChild);

    _updateCustomizeBar(panel);
  }

  function _showLayoutDragHint(panel) {
    const bar = panel.querySelector(".panel-customize-bar");
    if (!bar) return;
    let hint = bar.querySelector(".layout-drag-hint");
    if (!hint) {
      hint = document.createElement("span");
      hint.className = "layout-drag-hint";
      bar.appendChild(hint);
    }
    hint.textContent = "Still gated. Click Advanced to make this panel always visible.";
    panel.classList.add("panel-drag-hint-active");
    const oldTimer = _layoutDragHintTimers.get(panel);
    if (oldTimer) clearTimeout(oldTimer);
    const timer = setTimeout(() => {
      panel.classList.remove("panel-drag-hint-active");
      const currentHint = bar.querySelector(".layout-drag-hint");
      if (currentHint) currentHint.remove();
      _layoutDragHintTimers.delete(panel);
    }, 3500);
    _layoutDragHintTimers.set(panel, timer);
  }

  let _dndSrc = null;

  let _dndContainer = null;

  let _dndPointerOffsetY = 0;

  let _dndSourceHeight = 0;

  let _dndDropTarget = null;

  let _dndDropPlacement = "below";

  let _pointerDragStartX = 0;

  let _pointerDragStartY = 0;

  let _pointerDragStarted = false;

  let _pointerDragCleanup = null;

  function _layoutSiblingPanels(panel) {
    const container = panel?.parentElement;
    if (!container) return [];
    return _layoutPanelsInContainer(container);
  }

  function _syncPanelMoveButtons(container) {
    if (!container) return;
    const panels = _layoutPanelsInContainer(container);
    panels.forEach((panel, index) => {
      const up = panel.querySelector(".pcb-btn-move-up");
      const down = panel.querySelector(".pcb-btn-move-down");
      if (up) up.disabled = index === 0;
      if (down) down.disabled = index === panels.length - 1;
    });
  }

  function _panelIndexInContainer(panel) {
    return _layoutSiblingPanels(panel).indexOf(panel);
  }

  function _pulseMovedPanel(panel) {
    if (!panel) return;
    panel.classList.remove("panel-layout-moved");
    void panel.offsetWidth;
    panel.classList.add("panel-layout-moved");
  }

  function _setPanelHolding(panel, holding) {
    if (!panel) return;
    panel.classList.toggle("panel-drag-holding", Boolean(holding));
  }

  function _clearPanelHolding(panel) {
    _setPanelHolding(panel, false);
  }

  function _beginPanelPointerDrag(panel, event) {
    if (!panel) return;
    if (_dndSrc && _dndSrc !== panel) _resetPanelPointerDragState();
    const rect = panel.getBoundingClientRect();
    _dndSrc = panel;
    _dndContainer = panel.parentElement;
    _dndSourceHeight = rect.height || 0;
    _dndPointerOffsetY = Number.isFinite(event.clientY)
      ? Math.max(0, Math.min(event.clientY - rect.top, _dndSourceHeight || event.clientY))
      : Math.min(32, _dndSourceHeight / 2);
    _dndDropTarget = null;
    _dndDropPlacement = "below";
    _pointerDragStartX = Number.isFinite(event.clientX) ? event.clientX : 0;
    _pointerDragStartY = Number.isFinite(event.clientY) ? event.clientY : 0;
    _pointerDragStarted = false;
    if (panel.hasAttribute("data-panel-advanced")) _showLayoutDragHint(panel);
    _setPanelHolding(panel, true);
  }

  function _finishPanelPointerDrag() {
    if (_dndSrc && _dndDropTarget && _dndDropTarget.parentElement === _dndContainer) {
      if (_dndDropPlacement === "above") {
        _dndDropTarget.parentNode.insertBefore(_dndSrc, _dndDropTarget);
      } else {
        _dndDropTarget.parentNode.insertBefore(_dndSrc, _dndDropTarget.nextSibling);
      }
      _savePanelOrder(_dndContainer);
      _syncPanelMoveButtons(_dndContainer);
      _pulseMovedPanel(_dndSrc);
    }
  }

  function _resetPanelPointerDragState() {
    if (_dndSrc) _dndSrc.classList.remove("panel-dragging", "panel-drag-holding");
    _clearDropTargetClasses();
    _dndSrc = null;
    _dndContainer = null;
    _dndPointerOffsetY = 0;
    _dndSourceHeight = 0;
    _dndDropTarget = null;
    _dndDropPlacement = "below";
    _pointerDragStartX = 0;
    _pointerDragStartY = 0;
    _pointerDragStarted = false;
    if (_pointerDragCleanup) {
      const cleanup = _pointerDragCleanup;
      _pointerDragCleanup = null;
      cleanup();
    }
  }

  function _updatePanelPointerDrag(event) {
    if (!_dndSrc || !_dndContainer) return;
    const dx = Math.abs((Number.isFinite(event.clientX) ? event.clientX : 0) - _pointerDragStartX);
    const dy = Math.abs((Number.isFinite(event.clientY) ? event.clientY : 0) - _pointerDragStartY);
    if (!_pointerDragStarted && dx + dy >= 4) {
      _pointerDragStarted = true;
      _dndSrc.classList.add("panel-dragging");
    }
    const clientX = Math.max(0, Math.min(window.innerWidth - 1, event.clientX));
    const clientY = Math.max(0, Math.min(window.innerHeight - 1, event.clientY));
    const hit = document.elementFromPoint(clientX, clientY);
    const target = hit?.closest?.("section.panel[data-panel-key]");
    if (!target || target === _dndSrc || target.parentElement !== _dndContainer) {
      _dndDropTarget = null;
      _dndDropPlacement = "below";
      _clearDropTargetClasses();
      return;
    }
    const dropState = _projectedDropState(target, event);
    if (!dropState.qualifies) {
      if (_dndDropTarget === target) {
        _dndDropTarget = null;
        _dndDropPlacement = "below";
      }
      target.classList.remove("panel-drop-above", "panel-drop-below", "panel-drop-target");
      return;
    }
    _clearDropTargetClasses(target);
    _dndDropTarget = target;
    _dndDropPlacement = dropState.above ? "above" : "below";
    target.classList.add("panel-drop-target");
    target.classList.toggle("panel-drop-above", dropState.above);
    target.classList.toggle("panel-drop-below", !dropState.above);
  }

  function _onDragHandlePointerDown(e) {
    if (!document.body.classList.contains("layout-customize-mode")) return;
    const panel = e.currentTarget?.closest?.("section.panel[data-panel-key]");
    if (!panel) return;
    _beginPanelPointerDrag(panel, e);
    e.preventDefault();
    try { e.currentTarget.setPointerCapture?.(e.pointerId); } catch (_) {}
    const handle = e.currentTarget;
    const pointerId = e.pointerId;
    const move = (event) => {
      _updatePanelPointerDrag(event);
    };
    const release = () => {
      _finishPanelPointerDrag();
      _resetPanelPointerDragState();
    };
    const cancel = () => {
      _resetPanelPointerDragState();
    };
    const keyCancel = (event) => {
      if (event.key === "Escape") cancel();
    };
    _pointerDragCleanup = () => {
      try { handle.releasePointerCapture?.(pointerId); } catch (_) {}
      document.removeEventListener("pointermove", move);
      document.removeEventListener("pointerup", release);
      document.removeEventListener("pointercancel", cancel);
      document.removeEventListener("keydown", keyCancel);
      window.removeEventListener("blur", cancel);
    };
    document.addEventListener("pointermove", move);
    document.addEventListener("pointerup", release);
    document.addEventListener("pointercancel", cancel);
    document.addEventListener("keydown", keyCancel);
    window.addEventListener("blur", cancel);
  }

  function _movePanelByStep(panel, delta) {
    const siblings = _layoutSiblingPanels(panel);
    const currentIndex = siblings.indexOf(panel);
    if (currentIndex < 0) return;
    const targetIndex = currentIndex + delta;
    if (targetIndex < 0 || targetIndex >= siblings.length) return;
    const target = siblings[targetIndex];
    if (delta < 0) {
      panel.parentNode.insertBefore(panel, target);
    } else {
      panel.parentNode.insertBefore(target, panel);
    }
    _savePanelOrder(panel.parentElement);
    _syncPanelMoveButtons(panel.parentElement);
    _pulseMovedPanel(panel);
    panel.querySelector(".pcb-btn-move-up, .pcb-btn-move-down")?.focus();
  }


const layoutDrawerModule = window.__layoutManagerDrawerModule;
  if (!layoutDrawerModule?.createLayoutManagerDrawer) {
    throw new Error("layoutManager drawer module must load before layoutManager.js");
  }
  const {
    _layoutRenderDrawer,
    _layoutDrawerIsOpen,
    _setLayoutDrawerAccessibility,
    _layoutResetVisiblePage,
    _layoutResetContainer,
    _layoutRequestResetAll,
    _layoutDisarmResetAll,
    _layoutContainerByKey,
    _layoutDefaultSelectedContainer,
  } = layoutDrawerModule.createLayoutManagerDrawer({
    layoutStorageKey: LAYOUT_STORAGE_KEY,
    drawerState: _layoutDrawerState,
    layoutContainersByKey: _layoutContainersByKey,
    layoutDefaultOrders: _layoutDefaultOrders,
    layoutDefaultPanelState: _layoutDefaultPanelState,
    layoutPreviewTimers: _layoutPreviewTimers,
    getLayoutManagedContainers: (...args) => _layoutManagedContainers(...args),
    layoutActivePage: _layoutActivePage,
    layoutPageLabel: _layoutPageLabel,
    layoutContainerLabel: _layoutContainerLabel,
    layoutContainerKey: _layoutContainerKey,
    layoutPanelsInContainer: _layoutPanelsInContainer,
    layoutPanelTitle: _layoutPanelTitle,
    layoutPanelIsEvidence: _layoutPanelIsEvidence,
    layoutPanelIsAuthoredEvidence: _layoutPanelIsAuthoredEvidence,
    layoutSetStatus: _layoutSetStatus,
    layoutSetPanelType: _layoutSetPanelType,
    layoutDefaultPanelType: _layoutDefaultPanelType,
    loadLayout: _loadLayout,
    saveLayout: _saveLayout,
    savePanelOrder: _savePanelOrder,
    syncPanelMoveButtons: _syncPanelMoveButtons,
    pulseMovedPanel: _pulseMovedPanel,
    movePanelByStep: _movePanelByStep,
    togglePanelAdvanced: _togglePanelAdvanced,
    togglePanelHidden: _togglePanelHidden,
    togglePanelEvidence: _togglePanelEvidence,
    updateCustomizeBar: _updateCustomizeBar,
  });
  delete window.__layoutManagerDrawerModule;

  function _onDragStart(e) {
    // Only allow drag to start from the handle element.
    const handle = this.querySelector(".pcb-drag-handle");
    if (!handle || !handle.contains(e.target)) {
      e.preventDefault();
      return;
    }
    _dndSrc = this;
    _dndContainer = this.parentElement;
    const rect = this.getBoundingClientRect();
    _dndSourceHeight = rect.height || 0;
    _dndPointerOffsetY = Number.isFinite(e.clientY)
      ? Math.max(0, Math.min(e.clientY - rect.top, _dndSourceHeight || e.clientY))
      : Math.min(32, _dndSourceHeight / 2);
    if (this.hasAttribute("data-panel-advanced")) _showLayoutDragHint(this);
    _setPanelHolding(this, true);
    this.classList.add("panel-dragging");
    e.dataTransfer.effectAllowed = "move";
    e.dataTransfer.setData("text/plain", this.dataset.panelKey || "");
  }

  function _clearDropTargetClasses(except = null) {
    document.querySelectorAll(".panel-drop-above, .panel-drop-below, .panel-drop-target").forEach((el) => {
      if (except && el === except) return;
      el.classList.remove("panel-drop-above", "panel-drop-below", "panel-drop-target");
    });
  }

  function _projectedDropState(target, event) {
    const targetRect = target.getBoundingClientRect();
    const sourceHeight = _dndSourceHeight || _dndSrc?.getBoundingClientRect?.().height || targetRect.height || 0;
    const pointerOffset = Number.isFinite(_dndPointerOffsetY) ? _dndPointerOffsetY : Math.min(32, sourceHeight / 2);
    const draggedTop = event.clientY - pointerOffset;
    const draggedBottom = draggedTop + sourceHeight;
    const overlap = Math.max(0, Math.min(draggedBottom, targetRect.bottom) - Math.max(draggedTop, targetRect.top));
    const threshold = Math.max(1, Math.min(sourceHeight, targetRect.height) / 2);
    const sourceIndex = _panelIndexInContainer(_dndSrc);
    const targetIndex = _panelIndexInContainer(target);
    return {
      qualifies: overlap >= threshold,
      above: sourceIndex > targetIndex,
    };
  }

  function _onDragOver(e) {
    if (!_dndSrc || _dndSrc === this) return;
    if (this.parentElement !== _dndContainer) return;
    const dropState = _projectedDropState(this, e);
    if (!dropState.qualifies) {
      if (_dndDropTarget === this) {
        _dndDropTarget = null;
        _dndDropPlacement = "below";
      }
      this.classList.remove("panel-drop-above", "panel-drop-below", "panel-drop-target");
      return;
    }
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
    _clearDropTargetClasses(this);
    _dndDropTarget = this;
    _dndDropPlacement = dropState.above ? "above" : "below";
    this.classList.add("panel-drop-target");
    this.classList.toggle("panel-drop-above", dropState.above);
    this.classList.toggle("panel-drop-below", !dropState.above);
  }

  function _onDragLeave() {
    if (_dndDropTarget === this) {
      _dndDropTarget = null;
      _dndDropPlacement = "below";
    }
    this.classList.remove("panel-drop-above", "panel-drop-below");
    this.classList.remove("panel-drop-target");
  }

  function _onDrop(e) {
    if (!_dndSrc || _dndSrc === this) return;
    if (this.parentElement !== _dndContainer) return;
    let dropState = {
      qualifies: _dndDropTarget === this,
      above: _dndDropPlacement === "above",
    };
    if (!dropState.qualifies) dropState = _projectedDropState(this, e);
    if (!dropState.qualifies) return;
    e.preventDefault();
    _clearDropTargetClasses();
    if (dropState.above) {
      this.parentNode.insertBefore(_dndSrc, this);
    } else {
      this.parentNode.insertBefore(_dndSrc, this.nextSibling);
    }
    _savePanelOrder(_dndContainer);
    _syncPanelMoveButtons(_dndContainer);
    _pulseMovedPanel(_dndSrc);
  }

  function _onDragEnd() {
    _resetPanelPointerDragState();
  }

  function _savePanelOrder(container) {
    if (!container) return;
    const containerKey = _layoutContainerKey(container);
    const panels = _layoutPanelsInContainer(container);
    const state = _loadLayout();
    state[`__order__${containerKey}`] = panels.map((p) => p.dataset.panelKey || "");
    _saveLayout(state);
  }

  function _togglePanelAdvanced(panel) {
    const key = panel.dataset.panelKey;
    const wasAdv = panel.hasAttribute("data-panel-advanced");
    const state = _loadLayout();
    if (!state[key]) state[key] = {};
    state[key].advanced = !wasAdv;
    _saveLayout(state);
    panel.toggleAttribute("data-panel-advanced", !wasAdv);
    if (wasAdv) {
      panel.classList.remove("panel-drag-hint-active");
      const hint = panel.querySelector(".layout-drag-hint");
      if (hint) hint.remove();
    }
    _updateCustomizeBar(panel);
    updatePagePanelEmptyStates();
  }

  function _togglePanelHidden(panel) {
    const key = panel.dataset.panelKey;
    const wasHid = panel.hasAttribute("data-panel-hidden");
    const state = _loadLayout();
    if (!state[key]) state[key] = {};
    state[key].hidden = !wasHid;
    _saveLayout(state);
    panel.toggleAttribute("data-panel-hidden", !wasHid);
    _updateCustomizeBar(panel);
    updatePagePanelEmptyStates();
  }

  function _togglePanelEvidence(panel) {
    const key = panel.dataset.panelKey;
    const wasEvidence = _layoutPanelIsEvidence(panel);
    const defaultType = _layoutDefaultPanelType(panel);
    const state = _loadLayout();
    if (!state[key]) state[key] = {};
    if (wasEvidence && defaultType !== "evidence") {
      delete state[key].panelType;
      _layoutSetPanelType(panel, defaultType);
    } else {
      state[key].panelType = "evidence";
      _layoutSetPanelType(panel, "evidence");
    }
    _saveLayout(state);
    _updateCustomizeBar(panel);
    updatePagePanelEmptyStates();
  }


const layoutNormalizationModule = window.__layoutManagerNormalizationModule;
  if (!layoutNormalizationModule?.createLayoutManagerNormalization) {
    throw new Error("layoutManager normalization module must load before layoutManager.js");
  }
  const {
    _initPageLayout,
    _layoutManagedContainers,
    _applyStoredPanelState,
    _applyStoredOrder,
    _layoutPaneTitle,
  } = layoutNormalizationModule.createLayoutManagerNormalization({
    layoutContainersByKey: _layoutContainersByKey,
    layoutDefaultOrders: _layoutDefaultOrders,
    layoutDefaultPanelState: _layoutDefaultPanelState,
    layoutContainerKey: _layoutContainerKey,
    layoutPanelsInContainer: _layoutPanelsInContainer,
    layoutPanelIsEditorExcluded: _layoutPanelIsEditorExcluded,
    layoutSetPanelType: _layoutSetPanelType,
    layoutDefaultPanelType: _layoutDefaultPanelType,
    layoutTabPaneKey: _layoutTabPaneKey,
    panelKey: _panelKey,
    injectCustomizeBar: _injectCustomizeBar,
    updateCustomizeBar: _updateCustomizeBar,
    loadLayout: _loadLayout,
    saveLayout: _saveLayout,
    syncPanelMoveButtons: _syncPanelMoveButtons,
    movePanelByStep: _movePanelByStep,
    togglePanelAdvanced: _togglePanelAdvanced,
    togglePanelHidden: _togglePanelHidden,
    onDragHandlePointerDown: _onDragHandlePointerDown,
    onDragStart: _onDragStart,
    onDragOver: _onDragOver,
    onDragLeave: _onDragLeave,
    onDrop: _onDrop,
    onDragEnd: _onDragEnd,
  });
  delete window.__layoutManagerNormalizationModule;

  function applyStoredLayoutPreferences() {
    const state = _loadLayout();
    _layoutContainersByKey.forEach((container) => {
      const panels = _layoutPanelsInContainer(container);
      panels.forEach((panel) => {
        const key = panel.dataset.panelKey || "";
        if (!key) return;
        _applyStoredPanelState(panel, state[key] || {});
        _updateCustomizeBar(panel);
      });
      _applyStoredOrder(container, panels, state);
      _syncPanelMoveButtons(container);
    });
    updatePagePanelEmptyStates();
    if (_layoutDrawerIsOpen()) _layoutRenderDrawer({ preserveStatus: true });
  }

  function applySharedUiPreferenceRuntimeState() {
    applyAdvancedModePreference(readBooleanUiPreference(ADVANCED_MODE_STORAGE_KEY));
    applyEvidenceHiddenPreference(readBooleanUiPreference(EVIDENCE_HIDDEN_STORAGE_KEY));
    applyThemePreference(false);
    applyStoredLayoutPreferences();
  }

  function initLayoutManager() {
    const state = _loadLayout();
    document.querySelectorAll(".page[data-page-panel]").forEach(page => {
      _initPageLayout(page, state);
    });

    // ── Customize toggle ──

    const customizeBtn = byId("customize-layout-btn");
    const resetBtn = byId("reset-layout-btn");
    function enterCustomize() {
      document.body.classList.add("layout-editor-open");
      _setLayoutDrawerAccessibility(true);
      if (customizeBtn) {
        customizeBtn.setAttribute("aria-pressed", "true");
        customizeBtn.dataset.state = "on";
        customizeBtn.textContent = "Done";
        customizeBtn.title = "Close the Layout Editor drawer";
      }
      if (resetBtn) {
        resetBtn.textContent = "Reset Page";
        resetBtn.dataset.state = "idle";
        resetBtn.title = "Reset the current page layout to its authored order";
      }
      _layoutRenderDrawer();
      updatePagePanelEmptyStates();
    }
    function exitCustomize() {
      document.body.classList.remove("layout-editor-open");
      _setLayoutDrawerAccessibility(false);
      if (customizeBtn) {
        customizeBtn.setAttribute("aria-pressed", "false");
        customizeBtn.dataset.state = "off";
        customizeBtn.textContent = "Customize";
        customizeBtn.title = "Open the Layout Editor drawer";
      }
      if (resetBtn) {
        resetBtn.textContent = "Reset Layout";
        resetBtn.dataset.state = "idle";
        resetBtn.title = "Reset layout preferences for the current page while the Layout Editor is open";
      }
      document.querySelectorAll("section.panel[data-panel-key]").forEach(p => {
        p.removeAttribute("draggable");
        p.classList.remove("panel-dragging", "panel-drag-holding", "panel-drop-above", "panel-drop-below", "panel-drop-target", "layout-panel-preview");
      });
      _layoutDisarmResetAll(byId("layout-editor-reset-all"));
      updatePagePanelEmptyStates();
    }
    if (customizeBtn) {
      customizeBtn.addEventListener("click", () => {
        const active = _layoutDrawerIsOpen();
        if (active) exitCustomize();else enterCustomize();
      });
    }
    if (resetBtn) {
      resetBtn.addEventListener("click", () => {
        if (!_layoutDrawerIsOpen()) return;
        _layoutResetVisiblePage();
      });
    }
    const drawerDone = byId("layout-editor-done");
    if (drawerDone) drawerDone.addEventListener("click", exitCustomize);
    const resetSubtab = byId("layout-editor-reset-subtab");
    if (resetSubtab) {
      resetSubtab.addEventListener("click", () => {
        if (!_layoutDrawerIsOpen()) return;
        const container = _layoutContainerByKey(_layoutDrawerState.selectedContainerKey) || _layoutDefaultSelectedContainer(_layoutActivePage());
        _layoutResetContainer(container);
      });
    }
    const resetPage = byId("layout-editor-reset-page");
    if (resetPage) {
      resetPage.addEventListener("click", () => {
        if (!_layoutDrawerIsOpen()) return;
        _layoutResetVisiblePage();
      });
    }
    const resetAll = byId("layout-editor-reset-all");
    if (resetAll) {
      resetAll.addEventListener("click", () => {
        if (!_layoutDrawerIsOpen()) return;
        _layoutRequestResetAll(resetAll);
      });
    }
  }

  /**
   * Public namespace for the app layout manager.
   * Flat window.* exports remain owned by app.js compatibility wrappers.
   */
  window.mediaPipelineAppLayoutManager = {
    initLayoutManager,
    _layoutRenderDrawer,
    _movePanelByStep,
    applyStoredLayoutPreferences,
    applySharedUiPreferenceRuntimeState
  };
})();
