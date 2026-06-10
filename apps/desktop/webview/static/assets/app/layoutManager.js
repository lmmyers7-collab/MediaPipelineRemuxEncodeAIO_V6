/* global ADVANCED_MODE_STORAGE_KEY, EVIDENCE_HIDDEN_STORAGE_KEY, THEME_STORAGE_KEY, applyAdvancedModePreference, applyEvidenceHiddenPreference, applyThemePreference, closeReadinessRequiresWarning, readBooleanUiPreference, showPage, updatePagePanelEmptyStates */
(function () {
  const LAYOUT_STORAGE_KEY = "mediapipeline-layout-v1";

  const _layoutDragHintTimers = new WeakMap();

  const _layoutDefaultOrders = new Map();

  const _layoutDefaultPanelState = new Map();

  const _layoutContainersByKey = new Map();

  const _layoutPreviewTimers = new WeakMap();

  let _layoutDrawerSelectedContainerKey = "";

  let _layoutDrawerSelectedPanelKey = "";

  let _layoutDrawerDragSource = null;

  let _layoutResetAllArmed = false;

  let _layoutResetAllForced = false;

  let _layoutResetAllTimer = null;

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

  function _layoutPanelsInContainer(container) {
    if (!container) return [];
    return Array.from(container.querySelectorAll(":scope > section.panel[data-panel-key]"));
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
    return Array.from(container.querySelectorAll(":scope > section.panel[data-panel-key]"));
  }

  function _syncPanelMoveButtons(container) {
    if (!container) return;
    const panels = Array.from(container.querySelectorAll(":scope > section.panel[data-panel-key]"));
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

  function _layoutMovePanelRelative(sourcePanel, targetPanel, after = false) {
    if (!sourcePanel || !targetPanel || sourcePanel === targetPanel) return false;
    if (sourcePanel.parentElement !== targetPanel.parentElement) return false;
    const container = sourcePanel.parentElement;
    if (after) {
      container.insertBefore(sourcePanel, targetPanel.nextSibling);
    } else {
      container.insertBefore(sourcePanel, targetPanel);
    }
    _savePanelOrder(container);
    _syncPanelMoveButtons(container);
    _pulseMovedPanel(sourcePanel);
    return true;
  }

  function _layoutDrawerContainers(page) {
    return _layoutManagedContainers(page)
      .filter((container) => _layoutPanelsInContainer(container).length > 0);
  }

  function _layoutDefaultSelectedContainer(page) {
    const containers = _layoutDrawerContainers(page);
    if (!containers.length) return null;
    const activePane = containers.find((container) => (
      !container.classList?.contains("page")
      && container.classList?.contains("settings-tab-pane")
      && container.classList?.contains("is-active")
    ));
    return activePane || containers[0];
  }

  function _layoutContainerByKey(containerKey) {
    return _layoutContainersByKey.get(containerKey) || null;
  }

  function _layoutDrawerIsOpen() {
    return document.body.classList.contains("layout-editor-open");
  }

  function _layoutClickTabButton(page, datasetKey, value) {
    if (!page || !datasetKey || value === undefined) return false;
    const button = Array.from(page.querySelectorAll(".settings-tab-btn, .settings-section-nav-btn, .profile-nav-btn"))
      .find((candidate) => candidate.dataset?.[datasetKey] === value);
    if (!button) return false;
    button.click();
    return true;
  }

  function _layoutActivateContainer(container) {
    const page = container?.closest?.(".page[data-page-panel]");
    if (!page) return;
    showPage(page.dataset.pagePanel);
    if (container.dataset?.settingsTab) {
      _layoutClickTabButton(page, "settingsTab", container.dataset.settingsTab);
    } else if (container.dataset?.diagTab) {
      _layoutClickTabButton(page, "diagTab", container.dataset.diagTab);
    } else if (container.dataset?.completedTab) {
      _layoutClickTabButton(page, "completedTab", container.dataset.completedTab);
    } else if (container.dataset?.launchTabPanel) {
      _layoutClickTabButton(page, "launchTab", container.dataset.launchTabPanel);
    } else if (container.dataset?.reportsTabPanel) {
      _layoutClickTabButton(page, "reportsTab", container.dataset.reportsTabPanel);
    }
  }

  function _layoutPanelIsVisible(panel) {
    if (!panel) return false;
    const style = window.getComputedStyle(panel);
    return style.display !== "none" && style.visibility !== "hidden";
  }

  function _layoutPreviewPanel(panel) {
    document.querySelectorAll(".layout-panel-preview").forEach((node) => {
      node.classList.remove("layout-panel-preview");
    });
    if (!panel) return;
    const title = _layoutPanelTitle(panel);
    if (panel.hasAttribute("data-panel-hidden")) {
      _layoutSetStatus(`${title} is hidden. Turn Visible on before previewing it on the page.`);
      return;
    }
    if (panel.hasAttribute("data-panel-advanced") && !document.body.classList.contains("advanced-mode")) {
      _layoutSetStatus(`${title} is behind the Advanced gate. Turn Advanced on or switch it to Normal before previewing it.`);
      return;
    }
    if (!_layoutPanelIsVisible(panel)) {
      _layoutSetStatus(`${title} is not visible on the current surface.`);
      return;
    }
    panel.scrollIntoView({ block: "center", behavior: "smooth" });
    panel.classList.add("layout-panel-preview");
    const oldTimer = _layoutPreviewTimers.get(panel);
    if (oldTimer) clearTimeout(oldTimer);
    const timer = setTimeout(() => {
      panel.classList.remove("layout-panel-preview");
      _layoutPreviewTimers.delete(panel);
    }, 2200);
    _layoutPreviewTimers.set(panel, timer);
    _layoutSetStatus(`${title} selected. The matching panel is highlighted on the page.`);
  }

  function _layoutSelectPanel(panel, { preview = true } = {}) {
    if (!panel) return;
    const container = panel.parentElement;
    _layoutDrawerSelectedContainerKey = _layoutContainerKey(container);
    _layoutDrawerSelectedPanelKey = panel.dataset.panelKey || "";
    _layoutActivateContainer(container);
    if (preview) _layoutPreviewPanel(panel);
    _layoutRenderDrawer({ preserveStatus: true });
  }

  function _layoutResetContainerState(container, state) {
    if (!container) return;
    const containerKey = _layoutContainerKey(container);
    const panels = _layoutPanelsInContainer(container);
    const panelMap = new Map(panels.map((panel) => [panel.dataset.panelKey, panel]));
    const defaultOrder = _layoutDefaultOrders.get(containerKey) || panels.map((panel) => panel.dataset.panelKey || "").filter(Boolean);
    delete state[`__order__${containerKey}`];
    defaultOrder.forEach((panelKey) => {
      const panel = panelMap.get(panelKey);
      if (panel) container.appendChild(panel);
    });
    panels.forEach((panel) => {
      if (!defaultOrder.includes(panel.dataset.panelKey)) container.appendChild(panel);
    });
    _layoutPanelsInContainer(container).forEach((panel) => {
      const panelKey = panel.dataset.panelKey || "";
      delete state[panelKey];
      const defaults = _layoutDefaultPanelState.get(panelKey) || {};
      panel.toggleAttribute("data-panel-advanced", Boolean(defaults.advanced));
      panel.toggleAttribute("data-panel-hidden", false);
      _updateCustomizeBar(panel);
    });
    _syncPanelMoveButtons(container);
  }

  function _layoutResetContainer(container) {
    if (!container) return;
    const state = _loadLayout();
    _layoutResetContainerState(container, state);
    _saveLayout(state);
    _layoutDrawerSelectedContainerKey = _layoutContainerKey(container);
    _layoutDrawerSelectedPanelKey = "";
    _layoutRenderDrawer();
    _layoutSetStatus(`${_layoutContainerLabel(container)} layout reset to its authored order.`);
    updatePagePanelEmptyStates();
  }

  function _layoutResetVisiblePage() {
    const page = _layoutActivePage();
    if (!page) return;
    const state = _loadLayout();
    _layoutDrawerContainers(page).forEach((container) => _layoutResetContainerState(container, state));
    _saveLayout(state);
    _layoutDrawerSelectedContainerKey = _layoutContainerKey(_layoutDefaultSelectedContainer(page) || page);
    _layoutDrawerSelectedPanelKey = "";
    _layoutRenderDrawer();
    _layoutSetStatus(`${_layoutPageLabel(page)} layout reset to its authored order.`);
    updatePagePanelEmptyStates();
  }

  function _layoutDisarmResetAll(button) {
    _layoutResetAllArmed = false;
    _layoutResetAllForced = false;
    clearTimeout(_layoutResetAllTimer);
    _layoutResetAllTimer = null;
    if (button) {
      button.textContent = "Reset All Layouts";
      button.dataset.state = "idle";
    }
    const warn = byId("layout-reset-warning");
    if (warn) warn.remove();
  }

  function _layoutRequestResetAll(button) {
    if (!_layoutResetAllArmed) {
      _layoutResetAllArmed = true;
      if (button) {
        button.textContent = "Confirm Reset All?";
        button.dataset.state = "armed";
      }
      _layoutResetAllTimer = setTimeout(() => _layoutDisarmResetAll(button), 3000);
      return;
    }
  
    const hasUnsaved = typeof closeReadinessRequiresWarning === "function"
      && closeReadinessRequiresWarning();
    if (hasUnsaved && !_layoutResetAllForced) {
      _layoutResetAllForced = true;
      if (button) {
        button.textContent = "Reset All Anyway?";
        button.dataset.state = "forced";
      }
      if (!byId("layout-reset-warning")) {
        const note = document.createElement("div");
        note.id = "layout-reset-warning";
        note.className = "layout-reset-warning-note";
        note.textContent = "Warning: unsaved page changes are present. Click Reset All Anyway? once more to discard layout preferences and reload.";
        const topbar = document.querySelector(".topbar");
        if (topbar) topbar.insertAdjacentElement("afterend", note);
      }
      clearTimeout(_layoutResetAllTimer);
      _layoutResetAllTimer = setTimeout(() => _layoutDisarmResetAll(button), 3000);
      return;
    }
  
    _layoutDisarmResetAll(button);
    try { localStorage.removeItem(LAYOUT_STORAGE_KEY); } catch (_) {}
    document.body.classList.remove("layout-editor-open");
    location.reload();
  }

  function _layoutClearDrawerDropState() {
    document.querySelectorAll(".layout-editor-panel-row.is-dragging, .layout-editor-panel-row.is-drop-target").forEach((row) => {
      row.classList.remove("is-dragging", "is-drop-target", "is-drop-after");
    });
  }

  function _layoutCreateDrawerButton(label, className, onClick, disabled = false) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = className;
    button.textContent = label;
    button.disabled = Boolean(disabled);
    button.addEventListener("click", (event) => {
      event.stopPropagation();
      onClick();
    });
    return button;
  }

  function _layoutRenderDrawer(options = {}) {
    const drawer = byId("layout-editor-drawer");
    const tree = byId("layout-editor-tree");
    if (!drawer || !tree) return;
    const page = _layoutActivePage();
    if (!page) return;
    const pageLabel = _layoutPageLabel(page);
    setText("layout-editor-page-label", `Page: ${pageLabel}`);
    const containers = _layoutDrawerContainers(page);
    if (!containers.some((container) => _layoutContainerKey(container) === _layoutDrawerSelectedContainerKey)) {
      const selected = _layoutDefaultSelectedContainer(page);
      _layoutDrawerSelectedContainerKey = selected ? _layoutContainerKey(selected) : "";
      _layoutDrawerSelectedPanelKey = "";
    }
    tree.textContent = "";
    if (!containers.length) {
      const empty = document.createElement("p");
      empty.className = "layout-editor-empty";
      empty.textContent = "No layout-managed panels exist on this page.";
      tree.appendChild(empty);
      if (!options.preserveStatus) _layoutSetStatus("No layout-managed panels exist on this page.");
      return;
    }
  
    containers.forEach((container) => {
      const containerKey = _layoutContainerKey(container);
      const panels = _layoutPanelsInContainer(container);
      const details = document.createElement("details");
      details.className = "layout-editor-group";
      details.dataset.layoutEditorContainerKey = containerKey;
      details.open = containerKey === _layoutDrawerSelectedContainerKey
        || container.classList?.contains("page")
        || container.classList?.contains("is-active");
  
      const summary = document.createElement("summary");
      summary.className = "layout-editor-group-summary";
      const title = document.createElement("span");
      title.textContent = _layoutContainerLabel(container);
      const count = document.createElement("span");
      count.className = "layout-editor-group-count";
      count.textContent = `${panels.length} panel${panels.length === 1 ? "" : "s"}`;
      summary.append(title, count);
      summary.addEventListener("click", () => {
        _layoutDrawerSelectedContainerKey = containerKey;
        _layoutDrawerSelectedPanelKey = "";
      });
      details.appendChild(summary);
  
      const list = document.createElement("div");
      list.className = "layout-editor-panel-list";
      panels.forEach((panel, index) => {
        const panelKey = panel.dataset.panelKey || "";
        const row = document.createElement("div");
        row.className = "layout-editor-panel-row";
        if (panelKey === _layoutDrawerSelectedPanelKey) row.classList.add("is-selected");
        row.dataset.layoutEditorPanelKey = panelKey;
        row.dataset.layoutEditorContainerKey = containerKey;
        row.draggable = true;
        row.tabIndex = 0;
        row.setAttribute("role", "treeitem");
  
        const grip = document.createElement("button");
        grip.type = "button";
        grip.className = "layout-editor-panel-grip";
        grip.textContent = "↕";
        grip.setAttribute("aria-label", `Drag ${_layoutPanelTitle(panel)}`);
  
        const name = document.createElement("span");
        name.className = "layout-editor-panel-name";
        name.textContent = _layoutPanelTitle(panel);
  
        const actions = document.createElement("div");
        actions.className = "layout-editor-panel-actions";
        actions.append(
          _layoutCreateDrawerButton("Up", "layout-editor-move-button", () => {
            _movePanelByStep(panel, -1);
            _layoutDrawerSelectedContainerKey = containerKey;
            _layoutDrawerSelectedPanelKey = panelKey;
            _layoutRenderDrawer();
          }, index === 0),
          _layoutCreateDrawerButton("Down", "layout-editor-move-button", () => {
            _movePanelByStep(panel, 1);
            _layoutDrawerSelectedContainerKey = containerKey;
            _layoutDrawerSelectedPanelKey = panelKey;
            _layoutRenderDrawer();
          }, index === panels.length - 1),
          _layoutCreateDrawerButton(
            panel.hasAttribute("data-panel-hidden") ? "Hidden" : "Visible",
            panel.hasAttribute("data-panel-hidden") ? "layout-editor-toggle-button is-active" : "layout-editor-toggle-button",
            () => {
              _togglePanelHidden(panel);
              _layoutDrawerSelectedContainerKey = containerKey;
              _layoutDrawerSelectedPanelKey = panelKey;
              _layoutRenderDrawer();
              _layoutSetStatus(`${_layoutPanelTitle(panel)} is now ${panel.hasAttribute("data-panel-hidden") ? "hidden" : "visible"}.`);
            },
          ),
          _layoutCreateDrawerButton(
            panel.hasAttribute("data-panel-advanced") ? "Advanced" : "Normal",
            panel.hasAttribute("data-panel-advanced") ? "layout-editor-toggle-button is-active" : "layout-editor-toggle-button",
            () => {
              _togglePanelAdvanced(panel);
              _layoutDrawerSelectedContainerKey = containerKey;
              _layoutDrawerSelectedPanelKey = panelKey;
              _layoutRenderDrawer();
              _layoutSetStatus(`${_layoutPanelTitle(panel)} is now ${panel.hasAttribute("data-panel-advanced") ? "behind the Advanced gate" : "normal"}.`);
            },
          ),
        );
  
        row.append(grip, name, actions);
        row.addEventListener("click", (event) => {
          if (event.target?.closest?.("button")) return;
          _layoutSelectPanel(panel);
        });
        row.addEventListener("keydown", (event) => {
          if (event.key !== "Enter" && event.key !== " ") return;
          event.preventDefault();
          _layoutSelectPanel(panel);
        });
        row.addEventListener("dragstart", (event) => {
          if (!event.target?.closest?.(".layout-editor-panel-grip")) {
            event.preventDefault();
            return;
          }
          _layoutDrawerDragSource = { panel, containerKey };
          row.classList.add("is-dragging");
          event.dataTransfer?.setData("text/plain", panelKey);
          if (event.dataTransfer) event.dataTransfer.effectAllowed = "move";
        });
        row.addEventListener("dragover", (event) => {
          if (!_layoutDrawerDragSource || _layoutDrawerDragSource.containerKey !== containerKey || _layoutDrawerDragSource.panel === panel) return;
          event.preventDefault();
          const rect = row.getBoundingClientRect();
          const after = event.clientY > rect.top + rect.height / 2;
          _layoutClearDrawerDropState();
          row.classList.add("is-drop-target");
          row.classList.toggle("is-drop-after", after);
        });
        row.addEventListener("drop", (event) => {
          if (!_layoutDrawerDragSource || _layoutDrawerDragSource.containerKey !== containerKey || _layoutDrawerDragSource.panel === panel) return;
          event.preventDefault();
          const rect = row.getBoundingClientRect();
          const after = event.clientY > rect.top + rect.height / 2;
          if (_layoutMovePanelRelative(_layoutDrawerDragSource.panel, panel, after)) {
            _layoutDrawerSelectedContainerKey = containerKey;
            _layoutDrawerSelectedPanelKey = _layoutDrawerDragSource.panel.dataset.panelKey || "";
            _layoutSetStatus(`${_layoutPanelTitle(_layoutDrawerDragSource.panel)} moved within ${_layoutContainerLabel(container)}.`);
          }
          _layoutDrawerDragSource = null;
          _layoutClearDrawerDropState();
          _layoutRenderDrawer({ preserveStatus: true });
        });
        row.addEventListener("dragend", () => {
          _layoutDrawerDragSource = null;
          _layoutClearDrawerDropState();
        });
        list.appendChild(row);
      });
      details.appendChild(list);
      tree.appendChild(details);
    });
    if (!options.preserveStatus) {
      _layoutSetStatus("Choose a panel to preview or adjust its layout.");
    }
  }

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
    const panels = Array.from(container.querySelectorAll(":scope > section.panel[data-panel-key]"));
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

  function _layoutNodeHasContent(node) {
    if (!node) return false;
    if (node.nodeType === 3) return Boolean(String(node.textContent || "").trim());
    if (node.nodeType === 1) return true;
    return false;
  }

  function _layoutPanelTitleFromHeading(heading, fallback = "Panel") {
    const h = heading?.querySelector?.("h2, h3");
    return (h?.textContent || fallback).trim() || fallback;
  }

  function _layoutPaneTitle(container) {
    const page = container.closest?.(".page[data-page-panel]");
    const pairs = [
      ["settingsTab", "settingsTab"],
      ["diagTab", "diagTab"],
      ["completedTab", "completedTab"],
      ["launchTabPanel", "launchTab"],
      ["reportsTabPanel", "reportsTab"],
    ];
    for (const [paneKey, buttonKey] of pairs) {
      const tab = container.dataset?.[paneKey];
      if (!tab || !page) continue;
      const dataAttribute = buttonKey.replace(/[A-Z]/g, (m) => `-${m.toLowerCase()}`);
      const button = page.querySelector(`.settings-tab-btn[data-${dataAttribute}="${tab}"], .settings-section-nav-btn[data-${dataAttribute}="${tab}"], .profile-nav-btn[data-${dataAttribute}="${tab}"]`);
      const label = button?.textContent?.trim();
      if (label) return label;
    }
    return "Summary";
  }

  function _layoutMakeHeading(title, statusId = "") {
    const heading = document.createElement("div");
    heading.className = "panel-heading";
    const h = document.createElement("h2");
    h.textContent = title || "Summary";
    heading.appendChild(h);
    if (statusId) {
      const status = document.createElement("strong");
      status.id = statusId;
      heading.appendChild(status);
    }
    return heading;
  }

  function _layoutInferPanelType(nodes) {
    return nodes.some((node) => (
      node.nodeType === 1
      && (
        node.matches?.("button, input, select, textarea")
        || node.querySelector?.("button, input, select, textarea")
      )
    )) ? "interactive" : "evidence";
  }

  function _copyPanelContextAttributes(source, target) {
    if (!source || !target) return;
    if (source.classList?.contains("settings-tab-pane")) target.classList.add("settings-tab-pane");
    ["launch-tab-panel", "reports-tab-panel"].forEach((className) => {
      if (source.classList?.contains(className)) target.classList.add(className);
    });
    [
      "launchTabPanel",
      "reportsTabPanel",
      "evidenceToggleExempt",
    ].forEach((key) => {
      if (source.dataset?.[key] !== undefined) target.dataset[key] = source.dataset[key];
    });
  }

  function _createLayoutGeneratedPanel(nodes, options = {}) {
    const panel = document.createElement("section");
    panel.className = "panel";
    panel.dataset.layoutGeneratedPanel = "true";
    panel.dataset.panelType = options.panelType || _layoutInferPanelType(nodes);
    if (options.advanced) panel.setAttribute("data-advanced", "");
    if (options.sourcePanel) _copyPanelContextAttributes(options.sourcePanel, panel);
    if (options.syntheticHeading) panel.appendChild(_layoutMakeHeading(options.title || "Summary"));
    nodes.forEach((node) => panel.appendChild(node));
    return panel;
  }

  function _extractLooseGroups(nodes, defaultTitle, advanced = false) {
    const groups = [];
    let current = null;
    nodes.forEach((node) => {
      if (!_layoutNodeHasContent(node)) return;
      if (node.nodeType === 1 && node.matches("div[data-advanced]")) {
        const advancedGroups = _extractLooseGroups(Array.from(node.childNodes), defaultTitle, true);
        groups.push(...advancedGroups);
        node.remove();
        current = null;
        return;
      }
      if (node.nodeType === 1 && node.matches("section.panel")) {
        current = null;
        return;
      }
      if (node.nodeType === 1 && node.matches(".panel-heading.panel-subheading")) {
        current = {
          title: _layoutPanelTitleFromHeading(node, defaultTitle),
          nodes: [node],
          advanced,
          syntheticHeading: false,
        };
        groups.push(current);
        return;
      }
      if (node.nodeType === 1 && node.matches(".panel-heading")) {
        current = {
          title: _layoutPanelTitleFromHeading(node, defaultTitle),
          nodes: [node],
          advanced,
          syntheticHeading: false,
        };
        groups.push(current);
        return;
      }
      if (!current) {
        current = {
          title: defaultTitle,
          nodes: [],
          advanced,
          syntheticHeading: true,
        };
        groups.push(current);
      }
      current.nodes.push(node);
    });
    return groups.filter((group) => group.nodes.some(_layoutNodeHasContent));
  }

  function _normalizeLayoutTabPaneContainers(page) {
    if (!page || page.dataset.layoutTabPanesNormalized === "true") return;
    page.querySelectorAll("section.panel.settings-tab-pane").forEach((pane) => {
      const container = document.createElement("div");
      Array.from(pane.attributes).forEach((attr) => {
        if (attr.name === "data-panel-type") return;
        container.setAttribute(attr.name, attr.value);
      });
      container.className = Array.from(pane.classList)
        .filter((className) => className !== "panel")
        .join(" ");
      while (pane.firstChild) container.appendChild(pane.firstChild);
      pane.parentNode?.replaceChild(container, pane);
    });
  
    const panesByKey = new Map();
    Array.from(page.querySelectorAll(".settings-tab-pane")).forEach((pane) => {
      const key = _layoutTabPaneKey(pane);
      if (!key) return;
      const existing = panesByKey.get(key);
      if (!existing) {
        panesByKey.set(key, pane);
        return;
      }
      if (pane.classList.contains("is-active")) existing.classList.add("is-active");
      while (pane.firstChild) existing.appendChild(pane.firstChild);
      pane.remove();
    });
    page.dataset.layoutTabPanesNormalized = "true";
  }

  function _splitLooseContentIntoPanels(container) {
    if (!container || container.dataset.layoutLoosePanelsReady === "true") return;
    if (container.classList?.contains("page")) return;
    const nodes = Array.from(container.childNodes);
    if (!nodes.some(_layoutNodeHasContent)) return;
    const hasPanelishHeading = nodes.some((node) => (
      node.nodeType === 1
      && (
        node.matches(".panel-heading.panel-subheading")
        || (node.matches("div[data-advanced]") && node.querySelector(":scope > .panel-heading.panel-subheading"))
      )
    ));
    const isKnownTabPane = container.matches?.(".settings-tab-pane[data-settings-tab], .settings-tab-pane[data-diag-tab], .settings-tab-pane[data-completed-tab], .settings-tab-pane[data-launch-tab-panel], .settings-tab-pane[data-reports-tab-panel]");
    if (!hasPanelishHeading && !isKnownTabPane) return;
    const defaultTitle = _layoutPaneTitle(container);
    const groups = _extractLooseGroups(nodes, defaultTitle, false);
    groups.forEach((group) => {
      container.appendChild(_createLayoutGeneratedPanel(group.nodes, {
        title: group.title,
        advanced: group.advanced,
        syntheticHeading: group.syntheticHeading,
      }));
    });
    container.dataset.layoutLoosePanelsReady = "true";
  }

  function _splitDirectPanelSubsections(container) {
    if (!container) return;
    Array.from(container.querySelectorAll(":scope > section.panel")).forEach((panel) => {
      if (panel.dataset.layoutSubsectionsReady === "true" || panel.dataset.layoutGeneratedPanel === "true") return;
      const directNodes = Array.from(panel.childNodes);
      const groups = [];
      let current = null;
      directNodes.forEach((node) => {
        if (!_layoutNodeHasContent(node)) return;
        if (node.nodeType === 1 && node.matches("div[data-advanced]")) {
          const advancedGroups = _extractLooseGroups(Array.from(node.childNodes), "Advanced", true);
          groups.push(...advancedGroups);
          node.remove();
          current = null;
          return;
        }
        if (node.nodeType === 1 && node.matches(".panel-heading.panel-subheading")) {
          current = {
            title: _layoutPanelTitleFromHeading(node, "Detail"),
            nodes: [node],
            advanced: false,
            syntheticHeading: false,
          };
          groups.push(current);
          return;
        }
        if (current) current.nodes.push(node);
      });
      if (!groups.length) {
        panel.dataset.layoutSubsectionsReady = "true";
        return;
      }
      let insertAfter = panel;
      groups.forEach((group) => {
        const generated = _createLayoutGeneratedPanel(group.nodes, {
          title: group.title,
          advanced: group.advanced,
          syntheticHeading: group.syntheticHeading,
          sourcePanel: panel,
        });
        insertAfter.parentNode.insertBefore(generated, insertAfter.nextSibling);
        insertAfter = generated;
      });
      panel.dataset.layoutSubsectionsReady = "true";
    });
  }

  function _flattenAdvancedWrappers(container) {
    Array.from(container.querySelectorAll(":scope > div[data-advanced]")).forEach((wrapper) => {
      Array.from(wrapper.querySelectorAll(":scope > section.panel")).forEach((p) => {
        p.dataset.advancedDefault = "true";
        wrapper.parentNode.insertBefore(p, wrapper);
      });
      if (wrapper.children.length === 0) wrapper.remove();
    });
    Array.from(container.querySelectorAll(":scope > section.panel[data-advanced]")).forEach((p) => {
      p.dataset.advancedDefault = "true";
      p.removeAttribute("data-advanced");
    });
  }

  function _applyStoredPanelState(panel, panelState) {
    const defaultAdv = panel.dataset.advancedDefault === "true";
    const isAdv = panelState.advanced !== undefined ? Boolean(panelState.advanced) : defaultAdv;
    panel.toggleAttribute("data-panel-advanced", isAdv);
    panel.toggleAttribute("data-panel-hidden", Boolean(panelState.hidden));
  }

  function _panelKeys(panels) {
    return panels.map((p) => p.dataset.panelKey || "").filter(Boolean);
  }

  function _storedOrderMatchesCurrentPanels(storedOrder, currentKeys) {
    if (!Array.isArray(storedOrder) || storedOrder.length === 0) return true;
    const storedKeys = storedOrder.filter(Boolean);
    if (storedKeys.length !== currentKeys.length) return false;
    const currentSet = new Set(currentKeys);
    const storedSet = new Set(storedKeys);
    return storedSet.size === currentSet.size && storedKeys.every((key) => currentSet.has(key));
  }

  function _applyStoredOrder(container, allPanels, state) {
    const containerKey = _layoutContainerKey(container);
    const storedOrder = state[`__order__${containerKey}`];
    if (!Array.isArray(storedOrder) || storedOrder.length === 0) return;
    const currentKeys = _panelKeys(allPanels);
    if (!_storedOrderMatchesCurrentPanels(storedOrder, currentKeys)) {
      // A page schema changed: keep hidden/advanced panel state, but reset order so
      // newly added panels appear at their authored default position instead of
      // being appended below every stored panel.
      state[`__order__${containerKey}`] = currentKeys;
      _saveLayout(state);
      container.dataset.layoutOrderStatus = "schema-reset";
      const page = container.closest?.(".page[data-page-panel]");
      if (page) page.dataset.layoutOrderStatus = "schema-reset";
      return;
    }
    const panelMap = new Map(allPanels.map((p) => [p.dataset.panelKey, p]));
    const known = storedOrder.filter((k) => panelMap.has(k));
    const extra = allPanels
      .map((p) => p.dataset.panelKey)
      .filter((k) => !known.includes(k));
    [...known, ...extra].forEach((k) => {
      const p = panelMap.get(k);
      if (p) container.appendChild(p);
    });
  }

  function _initLayoutContainer(container, state) {
    const containerKey = _layoutContainerKey(container);
    _layoutContainersByKey.set(containerKey, container);
  
    _splitLooseContentIntoPanels(container);
    _flattenAdvancedWrappers(container);
    _splitDirectPanelSubsections(container);
    _flattenAdvancedWrappers(container);
  
    // Dedup map: if two panels on the same page share an identical h2 (key
    // collision), the second gets a "-2" suffix, the third "-3", and so on.
    // This prevents silent localStorage corruption without requiring any HTML changes.
    const _keySeen = new Map();
  
    const panels = Array.from(container.querySelectorAll(":scope > section.panel"));
    panels.forEach((panel) => {
      let key = _panelKey(containerKey, panel);
      const seen = (_keySeen.get(key) || 0) + 1;
      _keySeen.set(key, seen);
      if (seen > 1) key = `${key}-${seen}`;
      panel.dataset.panelKey = key;
      const h = panel.querySelector(".panel-heading h2, .panel-heading h3");
      const title = h ? h.textContent.trim() : key.split("::")[1] || "Panel";
      _applyStoredPanelState(panel, state[key] || {});
      _layoutDefaultPanelState.set(key, {
        advanced: panel.dataset.advancedDefault === "true",
        hidden: false,
      });
      _injectCustomizeBar(panel, title);
  
      // Wire per-panel button clicks inside the bar.
      const bar = panel.querySelector(".panel-customize-bar");
      if (bar) {
        const handle = bar.querySelector(".pcb-drag-handle");
        if (handle) handle.addEventListener("pointerdown", _onDragHandlePointerDown);
        const btnAdv = bar.querySelector(".pcb-btn-advanced");
        if (btnAdv) btnAdv.addEventListener("click", () => _togglePanelAdvanced(panel));
        const btnHid = bar.querySelector(".pcb-btn-hidden");
        if (btnHid) btnHid.addEventListener("click", () => _togglePanelHidden(panel));
        const btnUp = bar.querySelector(".pcb-btn-move-up");
        if (btnUp) btnUp.addEventListener("click", () => _movePanelByStep(panel, -1));
        const btnDown = bar.querySelector(".pcb-btn-move-down");
        if (btnDown) btnDown.addEventListener("click", () => _movePanelByStep(panel, 1));
      }
  
      // DnD listeners — active only when draggable attr is set.
      panel.addEventListener("dragstart", _onDragStart);
      panel.addEventListener("dragover", _onDragOver);
      panel.addEventListener("dragleave", _onDragLeave);
      panel.addEventListener("drop", _onDrop);
      panel.addEventListener("dragend", _onDragEnd);
    });
  
    _layoutDefaultOrders.set(containerKey, panels.map((panel) => panel.dataset.panelKey || "").filter(Boolean));
    _applyStoredOrder(container, panels, state);
    _syncPanelMoveButtons(container);
  }

  function _layoutManagedContainers(page) {
    const containers = [];
    const seen = new Set();
    function add(container) {
      if (!container || seen.has(container)) return;
      seen.add(container);
      containers.push(container);
    }
    add(page);
    page.querySelectorAll(
      ".settings-tab-pane:not(section.panel)[data-settings-tab], .settings-tab-pane:not(section.panel)[data-diag-tab], .settings-tab-pane:not(section.panel)[data-completed-tab], .settings-tab-pane:not(section.panel)[data-launch-tab-panel], .settings-tab-pane:not(section.panel)[data-reports-tab-panel]"
    ).forEach(add);
    page.querySelectorAll("section.panel > div, .settings-tab-pane > div").forEach((node) => {
      if (node.querySelector(":scope > .panel-heading.panel-subheading")) add(node);
    });
    return containers;
  }

  function _initPageLayout(page, state) {
    _normalizeLayoutTabPaneContainers(page);
    _layoutManagedContainers(page).forEach((container) => _initLayoutContainer(container, state));
  }

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
    let storedTheme = null;
    try { storedTheme = localStorage.getItem(THEME_STORAGE_KEY); } catch (_) {}
    applyThemePreference(storedTheme === "light");
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
      const drawer = byId("layout-editor-drawer");
      if (drawer) drawer.setAttribute("aria-hidden", "false");
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
      const drawer = byId("layout-editor-drawer");
      if (drawer) drawer.setAttribute("aria-hidden", "true");
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
        const container = _layoutContainerByKey(_layoutDrawerSelectedContainerKey) || _layoutDefaultSelectedContainer(_layoutActivePage());
        _layoutResetContainer(container);
      });
    }
    const resetPage = byId("layout-editor-reset-page");
    if (resetPage) resetPage.addEventListener("click", _layoutResetVisiblePage);
    const resetAll = byId("layout-editor-reset-all");
    if (resetAll) resetAll.addEventListener("click", () => _layoutRequestResetAll(resetAll));
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
