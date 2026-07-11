/* global updatePagePanelEmptyStates */
(function () {
  function createLayoutManagerNormalization(deps) {
    const {
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
    } = deps;
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
      ["queueTabPanel", "queueTab"],
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
    ["launch-tab-panel", "queue-tab-panel", "reports-tab-panel"].forEach((className) => {
      if (source.classList?.contains(className)) target.classList.add(className);
    });
    [
      "launchTabPanel",
      "queueTabPanel",
      "reportsTabPanel",
      "evidenceToggleExempt",
      "layoutSourcePanelType",
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

  function _extractLooseGroups(nodes, defaultTitle, advanced = false, defaultPanelType = "") {
    const groups = [];
    let current = null;
    nodes.forEach((node) => {
      if (!_layoutNodeHasContent(node)) return;
      if (node.nodeType === 1 && node.matches("div[data-advanced]")) {
        const advancedGroups = _extractLooseGroups(Array.from(node.childNodes), defaultTitle, true, defaultPanelType);
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
          panelType: node.dataset?.layoutSourcePanelType || defaultPanelType,
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
          panelType: node.dataset?.layoutSourcePanelType || defaultPanelType,
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
          panelType: defaultPanelType,
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
      let sourcePanelType = "";
      Array.from(pane.attributes).forEach((attr) => {
        if (attr.name === "data-panel-type") {
          sourcePanelType = attr.value;
          return;
        }
        container.setAttribute(attr.name, attr.value);
      });
      container.className = Array.from(pane.classList)
        .filter((className) => className !== "panel")
        .join(" ");
      while (pane.firstChild) container.appendChild(pane.firstChild);
      if (sourcePanelType) {
        const heading = container.querySelector(":scope > .panel-heading");
        if (heading) heading.dataset.layoutSourcePanelType = sourcePanelType;
        else container.dataset.layoutSourcePanelType = sourcePanelType;
      }
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
    const isKnownTabPane = container.matches?.(".settings-tab-pane[data-settings-tab], .settings-tab-pane[data-diag-tab], .settings-tab-pane[data-completed-tab], .settings-tab-pane[data-launch-tab-panel], .settings-tab-pane[data-queue-tab-panel], .settings-tab-pane[data-reports-tab-panel]");
    if (!hasPanelishHeading && !isKnownTabPane) return;
    const defaultTitle = _layoutPaneTitle(container);
    const groups = _extractLooseGroups(nodes, defaultTitle, false, container.dataset.layoutSourcePanelType || "");
    groups.forEach((group) => {
      container.appendChild(_createLayoutGeneratedPanel(group.nodes, {
        title: group.title,
        advanced: group.advanced,
        panelType: group.panelType || "",
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
        if (_layoutPanelIsEditorExcluded(p)) p.setAttribute("data-advanced", "");
        wrapper.parentNode.insertBefore(p, wrapper);
      });
      if (wrapper.children.length === 0) wrapper.remove();
    });
    Array.from(container.querySelectorAll(":scope > section.panel[data-advanced]")).forEach((p) => {
      if (_layoutPanelIsEditorExcluded(p)) return;
      p.dataset.advancedDefault = "true";
      p.removeAttribute("data-advanced");
    });
  }

  function _applyStoredPanelState(panel, panelState) {
    const defaultAdv = panel.dataset.advancedDefault === "true";
    const isAdv = panelState.advanced !== undefined ? Boolean(panelState.advanced) : defaultAdv;
    const panelType = panelState.panelType === "evidence" ? "evidence" : _layoutDefaultPanelType(panel);
    _layoutSetPanelType(panel, panelType);
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

    const panels = Array.from(container.querySelectorAll(":scope > section.panel"))
      .filter((panel) => !_layoutPanelIsEditorExcluded(panel));
    panels.forEach((panel) => {
      let key = _panelKey(containerKey, panel);
      const seen = (_keySeen.get(key) || 0) + 1;
      _keySeen.set(key, seen);
      if (seen > 1) key = `${key}-${seen}`;
      panel.dataset.panelKey = key;
      panel.dataset.layoutDefaultPanelType = panel.dataset.panelType || "";
      const h = panel.querySelector(".panel-heading h2, .panel-heading h3");
      const title = h ? h.textContent.trim() : key.split("::")[1] || "Panel";
      _applyStoredPanelState(panel, state[key] || {});
      _layoutDefaultPanelState.set(key, {
        advanced: panel.dataset.advancedDefault === "true",
        hidden: false,
        panelType: panel.dataset.layoutDefaultPanelType || "",
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
      ".settings-tab-pane:not(section.panel)[data-settings-tab], .settings-tab-pane:not(section.panel)[data-diag-tab], .settings-tab-pane:not(section.panel)[data-completed-tab], .settings-tab-pane:not(section.panel)[data-launch-tab-panel], .settings-tab-pane:not(section.panel)[data-queue-tab-panel], .settings-tab-pane:not(section.panel)[data-reports-tab-panel]"
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

    return {
      _initPageLayout,
      _layoutManagedContainers,
      _applyStoredPanelState,
      _applyStoredOrder,
      _layoutPaneTitle,
    };
  }

  window.__layoutManagerNormalizationModule = { createLayoutManagerNormalization };
})();
