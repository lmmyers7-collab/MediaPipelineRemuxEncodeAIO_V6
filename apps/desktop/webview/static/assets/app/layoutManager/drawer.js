/* global closeReadinessRequiresWarning, showPage, updatePagePanelEmptyStates */
(function () {
  function createLayoutManagerDrawer(deps) {
    const {
      layoutStorageKey: LAYOUT_STORAGE_KEY,
      drawerState: _layoutDrawerState,
      layoutContainersByKey: _layoutContainersByKey,
      layoutDefaultOrders: _layoutDefaultOrders,
      layoutDefaultPanelState: _layoutDefaultPanelState,
      layoutPreviewTimers: _layoutPreviewTimers,
      getLayoutManagedContainers,
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
    } = deps;
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

  function _layoutPanelForDrawerRow(row) {
    const panelKey = row?.dataset?.layoutEditorPanelKey || "";
    const containerKey = row?.dataset?.layoutEditorContainerKey || "";
    const container = _layoutContainerByKey(containerKey);
    if (!panelKey || !container) return null;
    return _layoutPanelsInContainer(container).find((panel) => (
      (panel.dataset.panelKey || "") === panelKey
    )) || null;
  }

  function _layoutDrawerPointerClient(event) {
    return {
      x: Number.isFinite(event?.clientX) ? Math.max(0, Math.min(window.innerWidth - 1, event.clientX)) : 0,
      y: Number.isFinite(event?.clientY) ? Math.max(0, Math.min(window.innerHeight - 1, event.clientY)) : 0,
    };
  }

  function _layoutDrawerRowFromPoint(event) {
    const point = _layoutDrawerPointerClient(event);
    const hit = document.elementFromPoint?.(point.x, point.y);
    return hit?.closest?.(".layout-editor-panel-row[data-layout-editor-panel-key]")
      || event?.target?.closest?.(".layout-editor-panel-row[data-layout-editor-panel-key]")
      || null;
  }

  function _layoutDrawerDropStateForRow(row, event) {
    if (!row) return { qualifies: false, after: false };
    const rect = row.getBoundingClientRect();
    const clientY = Number.isFinite(event?.clientY) ? event.clientY : rect.top;
    return {
      qualifies: rect.height > 0,
      after: clientY > rect.top + rect.height / 2,
    };
  }

  function _layoutDrawerContainers(page) {
    return getLayoutManagedContainers(page)
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

  function _setLayoutDrawerAccessibility(open) {
    const drawer = byId("layout-editor-drawer");
    if (!drawer) return;
    if (open) {
      drawer.hidden = false;
      drawer.inert = false;
      drawer.removeAttribute("inert");
      drawer.setAttribute("aria-hidden", "false");
      return;
    }
    if (drawer.contains(document.activeElement)) byId("customize-layout-btn")?.focus();
    drawer.inert = true;
    drawer.setAttribute("inert", "");
    drawer.setAttribute("aria-hidden", "true");
    drawer.hidden = true;
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
    _layoutDrawerState.selectedContainerKey = _layoutContainerKey(container);
    _layoutDrawerState.selectedPanelKey = panel.dataset.panelKey || "";
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
      _layoutSetPanelType(panel, defaults.panelType || "");
      _updateCustomizeBar(panel);
    });
    _syncPanelMoveButtons(container);
  }

  function _layoutResetContainer(container) {
    if (!container) return;
    const state = _loadLayout();
    _layoutResetContainerState(container, state);
    _saveLayout(state);
    _layoutDrawerState.selectedContainerKey = _layoutContainerKey(container);
    _layoutDrawerState.selectedPanelKey = "";
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
    _layoutDrawerState.selectedContainerKey = _layoutContainerKey(_layoutDefaultSelectedContainer(page) || page);
    _layoutDrawerState.selectedPanelKey = "";
    _layoutRenderDrawer();
    _layoutSetStatus(`${_layoutPageLabel(page)} layout reset to its authored order.`);
    updatePagePanelEmptyStates();
  }

  function _layoutDisarmResetAll(button) {
    _layoutDrawerState.resetAllArmed = false;
    _layoutDrawerState.resetAllForced = false;
    clearTimeout(_layoutDrawerState.resetAllTimer);
    _layoutDrawerState.resetAllTimer = null;
    if (button) {
      button.textContent = "Reset All Layouts";
      button.dataset.state = "idle";
    }
    const warn = byId("layout-reset-warning");
    if (warn) warn.remove();
  }

  function _layoutRequestResetAll(button) {
    if (!_layoutDrawerState.resetAllArmed) {
      _layoutDrawerState.resetAllArmed = true;
      if (button) {
        button.textContent = "Confirm Reset All?";
        button.dataset.state = "armed";
      }
      _layoutDrawerState.resetAllTimer = setTimeout(() => _layoutDisarmResetAll(button), 3000);
      return;
    }

    const hasUnsaved = typeof closeReadinessRequiresWarning === "function"
      && closeReadinessRequiresWarning();
    if (hasUnsaved && !_layoutDrawerState.resetAllForced) {
      _layoutDrawerState.resetAllForced = true;
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
      clearTimeout(_layoutDrawerState.resetAllTimer);
      _layoutDrawerState.resetAllTimer = setTimeout(() => _layoutDisarmResetAll(button), 3000);
      return;
    }

    _layoutDisarmResetAll(button);
    try { localStorage.removeItem(LAYOUT_STORAGE_KEY); } catch (_) {}
    document.body.classList.remove("layout-editor-open");
    location.reload();
  }

  function _layoutClearDrawerDropState(except = null) {
    document.querySelectorAll(".layout-editor-panel-row.is-drop-target").forEach((row) => {
      if (except && row === except) return;
      row.classList.remove("is-drop-target", "is-drop-after");
    });
  }

  function _layoutClearDrawerDragState() {
    document.querySelectorAll(".layout-editor-panel-row.is-dragging, .layout-editor-panel-row.is-drag-holding").forEach((row) => {
      row.classList.remove("is-dragging", "is-drag-holding");
    });
  }

  function _layoutResetDrawerPointerDragState() {
    _layoutDrawerState.dragSource = null;
    _layoutClearDrawerDropState();
    _layoutClearDrawerDragState();
    _layoutDrawerState.pointerDrag = null;
    if (_layoutDrawerState.pointerDragCleanup) {
      const cleanup = _layoutDrawerState.pointerDragCleanup;
      _layoutDrawerState.pointerDragCleanup = null;
      cleanup();
    }
  }

  function _layoutUpdateDrawerPointerDrag(event) {
    const drag = _layoutDrawerState.pointerDrag;
    if (!drag) return;
    const clientX = Number.isFinite(event?.clientX) ? event.clientX : drag.startX;
    const clientY = Number.isFinite(event?.clientY) ? event.clientY : drag.startY;
    const dx = Math.abs(clientX - drag.startX);
    const dy = Math.abs(clientY - drag.startY);
    if (!drag.started && dx + dy >= 4) {
      drag.started = true;
      drag.sourceRow.classList.add("is-dragging");
    }

    const row = _layoutDrawerRowFromPoint(event);
    if (
      !row
      || row === drag.sourceRow
      || row.dataset.layoutEditorContainerKey !== drag.containerKey
    ) {
      drag.dropRow = null;
      drag.dropAfter = false;
      _layoutClearDrawerDropState();
      return;
    }

    const dropState = _layoutDrawerDropStateForRow(row, event);
    if (!dropState.qualifies) {
      drag.dropRow = null;
      drag.dropAfter = false;
      _layoutClearDrawerDropState();
      return;
    }

    drag.dropRow = row;
    drag.dropAfter = dropState.after;
    _layoutClearDrawerDropState(row);
    row.classList.add("is-drop-target");
    row.classList.toggle("is-drop-after", dropState.after);
  }

  function _layoutFinishDrawerPointerDrag(event) {
    const drag = _layoutDrawerState.pointerDrag;
    if (!drag) return;
    _layoutUpdateDrawerPointerDrag(event);
    const targetPanel = drag.dropRow ? _layoutPanelForDrawerRow(drag.dropRow) : null;
    let moved = false;
    if (targetPanel && _layoutMovePanelRelative(drag.panel, targetPanel, drag.dropAfter)) {
      _layoutDrawerState.selectedContainerKey = drag.containerKey;
      _layoutDrawerState.selectedPanelKey = drag.panel.dataset.panelKey || "";
      _layoutSetStatus(`${_layoutPanelTitle(drag.panel)} moved within ${_layoutContainerLabel(drag.container)}.`);
      moved = true;
    }
    _layoutResetDrawerPointerDragState();
    if (moved) _layoutRenderDrawer({ preserveStatus: true });
  }

  function _onLayoutDrawerGripPointerDown(event) {
    if (!_layoutDrawerIsOpen()) return;
    if (event.button !== undefined && event.button !== 0) return;
    const grip = event.currentTarget;
    const row = grip?.closest?.(".layout-editor-panel-row[data-layout-editor-panel-key]");
    const panel = _layoutPanelForDrawerRow(row);
    const containerKey = row?.dataset?.layoutEditorContainerKey || "";
    const container = _layoutContainerByKey(containerKey);
    if (!row || !panel || !container) return;

    if (_layoutDrawerState.pointerDrag) _layoutResetDrawerPointerDragState();
    event.preventDefault();
    event.stopPropagation();

    _layoutDrawerState.dragSource = { panel, containerKey };
    row.classList.add("is-drag-holding");
    _layoutDrawerState.pointerDrag = {
      sourceRow: row,
      panel,
      container,
      containerKey,
      startX: Number.isFinite(event.clientX) ? event.clientX : 0,
      startY: Number.isFinite(event.clientY) ? event.clientY : 0,
      started: false,
      dropRow: null,
      dropAfter: false,
    };

    try { grip.setPointerCapture?.(event.pointerId); } catch (_) {}
    const pointerId = event.pointerId;
    const move = (moveEvent) => _layoutUpdateDrawerPointerDrag(moveEvent);
    const release = (releaseEvent) => _layoutFinishDrawerPointerDrag(releaseEvent);
    const cancel = () => _layoutResetDrawerPointerDragState();
    const keyCancel = (keyEvent) => {
      if (keyEvent.key === "Escape") cancel();
    };
    _layoutDrawerState.pointerDragCleanup = () => {
      try { grip.releasePointerCapture?.(pointerId); } catch (_) {}
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

  function _layoutCreateDrawerButton(label, className, onClick, disabled = false, options = {}) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = className;
    button.textContent = label;
    button.disabled = Boolean(disabled);
    if (options.pressed !== undefined) button.setAttribute("aria-pressed", String(Boolean(options.pressed)));
    if (options.title) button.title = options.title;
    if (options.ariaLabel) button.setAttribute("aria-label", options.ariaLabel);
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
    if (!containers.some((container) => _layoutContainerKey(container) === _layoutDrawerState.selectedContainerKey)) {
      const selected = _layoutDefaultSelectedContainer(page);
      _layoutDrawerState.selectedContainerKey = selected ? _layoutContainerKey(selected) : "";
      _layoutDrawerState.selectedPanelKey = "";
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
      details.open = containerKey === _layoutDrawerState.selectedContainerKey
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
        _layoutDrawerState.selectedContainerKey = containerKey;
        _layoutDrawerState.selectedPanelKey = "";
      });
      details.appendChild(summary);

      const list = document.createElement("div");
      list.className = "layout-editor-panel-list";
      panels.forEach((panel, index) => {
        const panelKey = panel.dataset.panelKey || "";
        const row = document.createElement("div");
        row.className = "layout-editor-panel-row";
        if (panelKey === _layoutDrawerState.selectedPanelKey) row.classList.add("is-selected");
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
        const evidenceActive = _layoutPanelIsEvidence(panel);
        const evidenceLocked = evidenceActive && _layoutPanelIsAuthoredEvidence(panel);
        actions.append(
          _layoutCreateDrawerButton("Up", "layout-editor-move-button", () => {
            _movePanelByStep(panel, -1);
            _layoutDrawerState.selectedContainerKey = containerKey;
            _layoutDrawerState.selectedPanelKey = panelKey;
            _layoutRenderDrawer();
          }, index === 0),
          _layoutCreateDrawerButton("Down", "layout-editor-move-button", () => {
            _movePanelByStep(panel, 1);
            _layoutDrawerState.selectedContainerKey = containerKey;
            _layoutDrawerState.selectedPanelKey = panelKey;
            _layoutRenderDrawer();
          }, index === panels.length - 1),
          _layoutCreateDrawerButton(
            panel.hasAttribute("data-panel-hidden") ? "Hidden" : "Visible",
            panel.hasAttribute("data-panel-hidden") ? "layout-editor-toggle-button is-active" : "layout-editor-toggle-button",
            () => {
              _togglePanelHidden(panel);
              _layoutDrawerState.selectedContainerKey = containerKey;
              _layoutDrawerState.selectedPanelKey = panelKey;
              _layoutRenderDrawer();
              _layoutSetStatus(`${_layoutPanelTitle(panel)} is now ${panel.hasAttribute("data-panel-hidden") ? "hidden" : "visible"}.`);
            },
          ),
          _layoutCreateDrawerButton(
            panel.hasAttribute("data-panel-advanced") ? "Advanced" : "Normal",
            panel.hasAttribute("data-panel-advanced") ? "layout-editor-toggle-button is-active" : "layout-editor-toggle-button",
            () => {
              _togglePanelAdvanced(panel);
              _layoutDrawerState.selectedContainerKey = containerKey;
              _layoutDrawerState.selectedPanelKey = panelKey;
              _layoutRenderDrawer();
              _layoutSetStatus(`${_layoutPanelTitle(panel)} is now ${panel.hasAttribute("data-panel-advanced") ? "behind the Advanced gate" : "normal"}.`);
            },
          ),
          _layoutCreateDrawerButton(
            "Evidence",
            evidenceActive ? "layout-editor-toggle-button is-active" : "layout-editor-toggle-button",
            () => {
              _togglePanelEvidence(panel);
              _layoutDrawerState.selectedContainerKey = containerKey;
              _layoutDrawerState.selectedPanelKey = panelKey;
              _layoutRenderDrawer();
              _layoutSetStatus(`${_layoutPanelTitle(panel)} is now ${_layoutPanelIsEvidence(panel) ? "marked as evidence" : "restored to its authored panel type"}.`);
            },
            evidenceLocked,
            {
              pressed: evidenceActive,
              title: evidenceLocked
                ? "This panel is authored as evidence"
                : evidenceActive
                  ? "Restore this panel to its authored panel type"
                  : "Mark this panel as read-only evidence",
            },
          ),
        );

        row.append(grip, name, actions);
        grip.addEventListener("pointerdown", _onLayoutDrawerGripPointerDown);
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
          _layoutDrawerState.dragSource = { panel, containerKey };
          row.classList.add("is-dragging");
          event.dataTransfer?.setData("text/plain", panelKey);
          if (event.dataTransfer) event.dataTransfer.effectAllowed = "move";
        });
        row.addEventListener("dragover", (event) => {
          if (!_layoutDrawerState.dragSource || _layoutDrawerState.dragSource.containerKey !== containerKey || _layoutDrawerState.dragSource.panel === panel) return;
          event.preventDefault();
          const rect = row.getBoundingClientRect();
          const after = event.clientY > rect.top + rect.height / 2;
          _layoutClearDrawerDropState();
          row.classList.add("is-drop-target");
          row.classList.toggle("is-drop-after", after);
        });
        row.addEventListener("drop", (event) => {
          if (!_layoutDrawerState.dragSource || _layoutDrawerState.dragSource.containerKey !== containerKey || _layoutDrawerState.dragSource.panel === panel) return;
          event.preventDefault();
          const rect = row.getBoundingClientRect();
          const after = event.clientY > rect.top + rect.height / 2;
          if (_layoutMovePanelRelative(_layoutDrawerState.dragSource.panel, panel, after)) {
            _layoutDrawerState.selectedContainerKey = containerKey;
            _layoutDrawerState.selectedPanelKey = _layoutDrawerState.dragSource.panel.dataset.panelKey || "";
            _layoutSetStatus(`${_layoutPanelTitle(_layoutDrawerState.dragSource.panel)} moved within ${_layoutContainerLabel(container)}.`);
          }
          _layoutDrawerState.dragSource = null;
          _layoutClearDrawerDropState();
          _layoutRenderDrawer({ preserveStatus: true });
        });
        row.addEventListener("dragend", () => {
          _layoutDrawerState.dragSource = null;
          _layoutClearDrawerDropState();
          _layoutClearDrawerDragState();
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
    return {
      _layoutRenderDrawer,
      _layoutDrawerIsOpen,
      _setLayoutDrawerAccessibility,
      _layoutResetVisiblePage,
      _layoutResetContainer,
      _layoutRequestResetAll,
      _layoutDisarmResetAll,
      _layoutContainerByKey,
      _layoutDefaultSelectedContainer,
    };
  }

  window.__layoutManagerDrawerModule = { createLayoutManagerDrawer };
})();
