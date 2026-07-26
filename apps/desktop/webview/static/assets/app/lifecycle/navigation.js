/* global THEME_STORAGE_KEY, _layoutRenderDrawer, refreshAll */
(function () {
  function createAppLifecycleNavigation(deps) {
    const { completedTabStorageKey: COMPLETED_TAB_STORAGE_KEY } = deps;
    let uiQuickLinkEventsInitialized = false;
    const pageFocusHistory = new Map();

  function visiblePagePanel() {
    return document.querySelector(".page.is-visible[data-page-panel]");
  }
  void [visiblePagePanel];

  function panelVisibilityEmptyState(page) {
    let node = page.querySelector(':scope > [data-page-empty-state="panel-visibility"]');
    if (node) return node;

    node = document.createElement("section");
    node.className = "page-panel-empty-window";
    node.dataset.pageEmptyState = "panel-visibility";
    node.setAttribute("aria-hidden", "true");

    const title = document.createElement("strong");
    title.textContent = "No boxes are visible on this tab.";
    const detail = document.createElement("p");
    detail.className = "page-panel-empty-detail";
    detail.textContent = "Boxes may be hidden by Advanced, Evidence, or Customize settings.";

    const actions = document.createElement("div");
    actions.className = "inline-actions page-panel-empty-actions";
    const showEvidence = document.createElement("button");
    showEvidence.type = "button";
    showEvidence.className = "secondary-button";
    showEvidence.textContent = "Show Evidence";
    showEvidence.addEventListener("click", () => {
      if (document.body.classList.contains("evidence-hidden")) {
        byId("evidence-toggle")?.click();
      } else {
        updatePagePanelEmptyStates();
      }
    });
    const showAdvanced = document.createElement("button");
    showAdvanced.type = "button";
    showAdvanced.className = "secondary-button";
    showAdvanced.textContent = "Show Advanced";
    showAdvanced.addEventListener("click", () => {
      if (!document.body.classList.contains("advanced-mode")) {
        byId("advanced-toggle")?.click();
      } else {
        updatePagePanelEmptyStates();
      }
    });
    const customize = document.createElement("button");
    customize.type = "button";
    customize.className = "secondary-button";
    customize.textContent = "Customize";
    customize.addEventListener("click", () => {
      if (!document.body.classList.contains("layout-editor-open")) {
        byId("customize-layout-btn")?.click();
      } else {
        if (typeof _layoutRenderDrawer === "function") _layoutRenderDrawer({ preserveStatus: true });
        updatePagePanelEmptyStates();
      }
    });
    actions.append(showEvidence, showAdvanced, customize);
    node.append(title, detail, actions);
    page.appendChild(node);
    return node;
  }

  function panelIsCurrentlyVisible(panel) {
    return Boolean(panel.offsetWidth || panel.offsetHeight || panel.getClientRects().length);
  }

  function panelHiddenByAdvancedGate(panel) {
    if (document.body.classList.contains("advanced-mode")) return false;
    return panel.hasAttribute("data-panel-advanced") || panel.hasAttribute("data-advanced") || Boolean(panel.closest("[data-advanced]"));
  }

  function panelHiddenByEvidenceGate(panel) {
    if (!document.body.classList.contains("evidence-hidden")) return false;
    if (panel.dataset.evidenceToggleExempt === "true") return false;
    return panel.dataset.panelType === "evidence";
  }

  function pagePanelHiddenReasonLines(page, panels) {
    const reasons = [];
    if (panels.some(panelHiddenByAdvancedGate)) reasons.push("Advanced is off.");
    if (panels.some(panelHiddenByEvidenceGate)) reasons.push("Evidence is hidden.");
    if (panels.some((panel) => panel.hasAttribute("data-panel-hidden"))) reasons.push("Customize has hidden panel(s).");
    if (!reasons.length) reasons.push("A display filter is hiding this tab's panels.");
    return `Boxes may be hidden by ${reasons.join(" ")} Use the controls above to restore them.`;
  }

  function updatePagePanelEmptyState(page) {
    if (!page) return;
    const empty = panelVisibilityEmptyState(page);
    const panels = Array.from(page.querySelectorAll(".panel")).filter((panel) => !panel.closest("[data-page-empty-state]"));
    const hasVisiblePanel = panels.some(panelIsCurrentlyVisible);
    const shouldShow = page.classList.contains("is-visible") && panels.length > 0 && !hasVisiblePanel;
    empty.classList.toggle("is-visible", shouldShow);
    empty.setAttribute("aria-hidden", String(!shouldShow));
    if (shouldShow) {
      const detail = empty.querySelector(".page-panel-empty-detail");
      if (detail) detail.textContent = pagePanelHiddenReasonLines(page, panels);
    }
  }

  function updatePagePanelEmptyStates() {
    document.querySelectorAll(".page[data-page-panel]").forEach(updatePagePanelEmptyState);
  }

  function kebabCase(value) {
    return String(value || "").replace(/[A-Z]/g, (match) => `-${match.toLowerCase()}`);
  }

  function ensureElementId(element, prefix, suffix) {
    if (element.id) return element.id;
    const cleanPrefix = String(prefix || "tab").replace(/[^a-z0-9_-]+/gi, "-").toLowerCase();
    const cleanSuffix = String(suffix || "panel").replace(/[^a-z0-9_-]+/gi, "-").toLowerCase();
    element.id = `${cleanPrefix}-${cleanSuffix}`;
    return element.id;
  }

  function tabDatasetKey(button) {
    return Object.keys(button?.dataset || {}).find((key) => key.endsWith("Tab") && !key.endsWith("TabPanel")) || "";
  }

  function tabPanelDatasetKey(page, buttonKey) {
    const candidates = [`${buttonKey}Panel`, buttonKey];
    return candidates.find((key) => page.querySelector(`.settings-tab-pane[data-${kebabCase(key)}]`)) || "";
  }

  function syncTabAccessibility() {
    document.querySelectorAll('[role="tablist"]').forEach((tablist) => {
      const buttons = Array.from(tablist.querySelectorAll('[role="tab"]'));
      if (!buttons.length) return;
      const page = tablist.closest("[data-page-panel]") || document;
      const buttonKey = tabDatasetKey(buttons[0]);
      const panelKey = tabPanelDatasetKey(page, buttonKey);
      if (!buttonKey || !panelKey) return;
      const pageName = page.dataset?.pagePanel || "page";
      const panels = Array.from(page.querySelectorAll(`.settings-tab-pane[data-${kebabCase(panelKey)}]`));
      buttons.forEach((button) => {
        const tabValue = button.dataset[buttonKey] || "";
        const active = button.getAttribute("aria-selected") === "true";
        const buttonId = ensureElementId(button, `${pageName}-tab`, tabValue || "button");
        const controlledPanels = panels.filter((panel) => panel.dataset[panelKey] === tabValue);
        const panelIds = controlledPanels.map((panel, index) => ensureElementId(panel, `${pageName}-tabpanel-${tabValue || "pane"}`, String(index + 1)));
        if (panelIds.length) button.setAttribute("aria-controls", panelIds.join(" "));
        button.tabIndex = active ? 0 : -1;
        controlledPanels.forEach((panel) => {
          panel.setAttribute("role", "tabpanel");
          panel.setAttribute("aria-labelledby", buttonId);
          panel.hidden = !active;
        });
      });
      if (!tablist.dataset.tabKeyboardBound) {
        tablist.dataset.tabKeyboardBound = "true";
        tablist.addEventListener("keydown", (event) => {
          const current = event.target?.closest?.('[role="tab"]');
          if (!current || !tablist.contains(current)) return;
          const index = buttons.indexOf(current);
          if (index < 0) return;
          const lastIndex = buttons.length - 1;
          let nextIndex = -1;
          if (event.key === "ArrowRight" || event.key === "ArrowDown") nextIndex = index === lastIndex ? 0 : index + 1;
          if (event.key === "ArrowLeft" || event.key === "ArrowUp") nextIndex = index === 0 ? lastIndex : index - 1;
          if (event.key === "Home") nextIndex = 0;
          if (event.key === "End") nextIndex = lastIndex;
          if (nextIndex < 0) return;
          event.preventDefault();
          buttons[nextIndex].focus();
          buttons[nextIndex].click();
        });
        tablist.addEventListener("click", () => window.setTimeout(syncTabAccessibility, 0));
      }
    });
  }

  const resetWorkspaceScroll = function () {
    const workspace = document.querySelector(".workspace");
    if (workspace && typeof workspace.scrollTo === "function") {
      workspace.scrollTo(0, 0);
    }
    const scroller = document.scrollingElement || document.documentElement || document.body;
    if (scroller) {
      scroller.scrollTop = 0;
      scroller.scrollLeft = 0;
    }
    if (typeof window.scrollTo === "function") {
      window.scrollTo(0, 0);
    }
  };

  function showPage(page) {
    const normalized = String(page || "").trim();
    if (!normalized) return;
    const buttons = Array.from(document.querySelectorAll(".nav-button"));
    const panels = Array.from(document.querySelectorAll("[data-page-panel]"));
    const current = panels.find((panel) => panel.classList.contains("is-visible"))?.dataset.pagePanel || "";
    buttons.forEach((item) => {
      const active = item.dataset.page === normalized;
      item.classList.toggle("is-active", active);
      if (active) item.setAttribute("aria-current", "page");
      else item.removeAttribute("aria-current");
    });
    panels.forEach((panel) => panel.classList.toggle("is-visible", panel.dataset.pagePanel === normalized));
    if (current && current !== normalized) resetWorkspaceScroll();
    updatePagePanelEmptyStates();
    if (typeof refreshAll === "function") void refreshAll({ automatic: true, queueRefresh: true, page: normalized });
    if (document.body.classList.contains("layout-editor-open")) _layoutRenderDrawer();
    const maintenanceView = window.mediaPipelineMaintenanceView || {};
    if (normalized === "maintenance" && typeof maintenanceView.hasMaintenanceLoaded === "function" && !maintenanceView.hasMaintenanceLoaded()) {
      maintenanceView.refreshMaintenance?.();
    }
  }

  function rememberPageFocus(pageName) {
    const page = String(pageName || "").trim();
    const active = document.activeElement;
    if (!page || !active || active === document.body || typeof active.closest !== "function") return;
    const panel = active.closest(`[data-page-panel="${page}"]`);
    if (!panel) return;
    pageFocusHistory.set(page, active);
  }

  function defaultPageFocusTarget(panel) {
    if (!panel) return null;
    return panel.querySelector(
      "[data-page-focus-target], h1, .panel-heading h2, h2",
    );
  }

  function focusElementTarget(target) {
    if (!target || !target.isConnected) return false;
    if (typeof target.matches === "function" && !target.matches("a[href], button, input, select, textarea, summary, [tabindex]")) {
      target.setAttribute("tabindex", "-1");
    }
    target.scrollIntoView?.({ block: "start", inline: "nearest" });
    target.focus?.({ preventScroll: true });
    return document.activeElement === target;
  }

  function focusPageDestination(pageName, options = {}) {
    const page = String(pageName || "").trim();
    const panel = document.querySelector(`[data-page-panel="${page}"]`);
    if (!panel) return false;
    const exact = options.focusSelector ? panel.querySelector(options.focusSelector) || document.querySelector(options.focusSelector) : null;
    if (exact && focusElementTarget(exact)) return true;
    if (options.restoreFocus !== false) {
      const saved = pageFocusHistory.get(page);
      if (saved && panel.contains(saved) && focusElementTarget(saved)) return true;
    }
    if (page === "home" && window.mediaPipelineRunMonitor?.focusSelectedFile?.({ detail: options.detail === true })) {
      return true;
    }
    return focusElementTarget(defaultPageFocusTarget(panel));
  }

  function navigateToPage(page, options = {}) {
    const normalized = String(page || "").trim();
    if (!normalized) return false;
    const current = document.querySelector("[data-page-panel].is-visible")?.dataset?.pagePanel || "";
    if (current && current !== normalized) rememberPageFocus(current);
    showPage(normalized);
    window.setTimeout(() => focusPageDestination(normalized, options), 0);
    return true;
  }

  function applyDefaultActionTooltips() {
    const tooltips = [
      ["#pipeline-start-button", "Start is disabled while active work is reported. Backend start routes re-check queue, schedule, settings, and process locks at submission time."],
      ["#home-refresh-button", "Refreshes dashboard state from backend snapshots without starting or mutating media work."],
      ["#rerun-start-button", "Starts backend CSV rerun with the selected lifecycle policy after backend preview and preflight evidence."],
      ["#rerun-open-audit-tool-button", "Opens Reports > Audit for audit rows, score policy, and backend-owned rerun CSV export controls."],
      ["#pending-drain-button", "Requests backend pending-publish drain. Drain safety remains backend-owned and requires parked payload evidence."],
      ['[data-control-action="pause"]', "Pause or resume the active backend pipeline. Disabled while no active work is reported."],
      ['[data-control-action="rescan"]', "Request a backend queue rescan flag for the running pipeline. Disabled while no active work is reported."],
      ['[data-control-action="stop"]', "Request graceful Stop After Current. The current file may finish; no new item should start."],
      ['[data-control-action="kill"]', "Emergency force stop. Requires confirmation and asks the backend to terminate related pipeline, audit, and CSV rerun process trees."],
      ["#backend-shutdown-button", "Request backend shutdown only when close-readiness reports safe."],
      ["#maintenance-refresh-button", "Runs backend maintenance probes. Tool checks can take several seconds on portable bundles."],
      ["#release-dry-run-button", "Plans a deployment package without writing files. Review dry-run evidence before creating a deployment."],
      ["#release-build-button", "Creates a deployment package through the backend release builder after confirmation."],
      ["#backfill-dry-run-button", "Dry-run completed-manifest backfill. No manifest writes should occur during dry-run."],
      ["#dependency-atlas-button", "Regenerates dependency atlas HTML, images, and CSV exports through backend tooling."],
      ["#completed-refresh-current-output-button", "Rereads completed history and rechecks destination existence. It does not accept, delete, rerun, publish, drain, or move media."],
      ['[data-home-promotion-entry]', "Opens Completed Output when Final Library Promotion has reviewed files ready for delivery."],
      ['[data-completed-promote-selected]', "Promotes the selected reviewed file through the backend after confirmation. It never sends raw filesystem paths."],
      ["#diagnostics-tail-refresh-button", "Reads a bounded backend-allowlisted log tail. It cannot open arbitrary paths."],
      ["#sample-validation-append-button", "Appends backend-authored sample validation evidence only after preview/review. It does not accept output or publish media."],
      ["#sample-validation-preview-button", "Previews the sample validation record before any append."],
      ["#rename-apply-selected-button", "Submits selected rename rows to the backend transaction. Blocked rows cannot be applied."],
      ["#rename-preview-button", "Builds a backend rename preview. It does not rename files."],
      ["#rename-preview-top-button", "Builds a backend rename preview. It does not rename files."],
      ["#rename-use-selected-queue-button", "Copies the selected Queue source path into Rename paths. It does not rename files."],
      ["#rename-use-loaded-queue-button", "Copies loaded Queue source paths into Rename paths. It does not rename files."],
      ["#rename-browse-files-button", "Opens the Windows file browser and stages selected paths. It does not preview or rename files."],
      ["#rename-browse-folder-button", "Opens the Windows folder browser and stages the selected folder path. It does not preview or rename files."],
      ["#rename-add-path-button", "Adds the typed source path to Rename paths. It does not inspect or rename files."],
      ["#rename-clear-paths-button", "Clears staged Rename paths and preview rows. It does not touch source files."],
      ["#settings-network-apply-button", "Stages standalone/coordinator/worker settings into the shared Settings patch JSON. It does not start or stop workers."],
      ["#settings-network-reset-button", "Reloads the Network Workers tab mode controls from current saved backend settings."],
      ["#network-settings-preview-button", "Previews staged Distributed Mode Settings through the backend settings route. It does not save the PSD1."],
      ["#network-settings-save-button", "Saves staged Distributed Mode Settings through backend validation and config backup. It does not start or stop workers."],
      ["#settings-library-add-button", "Adds a new editable library profile tab. It does not scan, move, publish, promote, or delete media files."],
      ["#settings-library-delete-button", "Deletes the selected custom library profile from the staged editor only. Save Library Profile is required before config changes persist."],
      ["#settings-library-defaults-button", "Clears all Editor, Video/Media, Subtitle, and Audio overrides for the selected library."],
      ["#settings-library-build-patch-button", "Stages LibraryProfiles into the shared Settings patch JSON. It does not scan, move, publish, promote, or delete media files."],
      ["#settings-library-preview-button", "Previews staged LibraryProfiles through backend settings validation without saving the PSD1."],
      ["#settings-library-save-button", "Saves the selected Library Profile state through backend validation and config backup. It does not scan, move, publish, promote, or delete media files."],
      ["#settings-library-reset-button", "Reloads library cards from current saved backend settings."],
      ['[data-settings-path-key]', "Opens a backend-owned Windows folder picker and stages this Settings field. It does not save the PSD1 or touch media files."],
      ['[data-path-picker-target]', "Opens a backend-owned Windows picker and stages this path field only. It does not save settings, launch work, or touch media files."],
      ["#settings-save-patch-button", "Saves staged settings through backend validation. Raw WebView fields never write directly to the PSD1."],
    ];
    tooltips.forEach(([selector, title]) => {
      document.querySelectorAll(selector).forEach((node) => {
        if (!node.title) node.title = title;
      });
    });
  }

  function initSettingsTabNav() {
    const STORAGE_KEY = "mediapipeline-settings-section";
    const LEGACY_STORAGE_KEY = "mediapipeline-settings-tab";
    const page = document.querySelector('[data-page-panel="settings"]');
    if (!page) return;
    const btns = Array.from(page.querySelectorAll(".settings-section-nav-btn[data-settings-tab]"));
    const panes = Array.from(page.querySelectorAll(".settings-tab-pane[data-settings-tab]"));
    if (!btns.length || !panes.length) return;

    function activateSection(tabId) {
      btns.forEach((b) => {
        const active = b.dataset.settingsTab === tabId;
        if (active) b.setAttribute("aria-current", "location");
        else b.removeAttribute("aria-current");
      });
      panes.forEach((p) => {
        p.classList.toggle("is-active", p.dataset.settingsTab === tabId);
      });
      const saveHeader = page.querySelector("#settings-save-header");
      if (saveHeader) saveHeader.hidden = tabId === "guided-setup";
      try { localStorage.setItem(STORAGE_KEY, tabId); } catch (_) {}
      updatePagePanelEmptyStates();
    }

    btns.forEach((btn) => {
      btn.addEventListener("click", () => activateSection(btn.dataset.settingsTab));
    });

    let stored = "status";
    try { stored = localStorage.getItem(STORAGE_KEY) || localStorage.getItem(LEGACY_STORAGE_KEY) || "status"; } catch (_) {}
    // Validate stored value is a real section, fall back to status.
    if (!btns.some((b) => b.dataset.settingsTab === stored)) stored = "status";
    activateSection(stored);
  }

  function activateDiagnosticsTab(tabId) {
    const STORAGE_KEY = "mediapipeline-diag-tab";
    const page = document.querySelector('[data-page-panel="diagnostics"]');
    if (!page) return false;
    const btns = Array.from(page.querySelectorAll(".settings-tab-btn[data-diag-tab]"));
    const panes = Array.from(page.querySelectorAll(".settings-tab-pane[data-diag-tab]"));
    if (!btns.length || !panes.length) return false;

    let selected = String(tabId || "triage").trim();
    if (!btns.some((b) => b.dataset.diagTab === selected)) selected = "triage";
    btns.forEach((b) => {
      const active = b.dataset.diagTab === selected;
      b.setAttribute("aria-selected", String(active));
    });
    panes.forEach((p) => {
      p.classList.toggle("is-active", p.dataset.diagTab === selected);
    });
    try { localStorage.setItem(STORAGE_KEY, selected); } catch (_) {}
    syncTabAccessibility();
    updatePagePanelEmptyStates();
    return true;
  }

  function initDiagnosticsTabNav() {
    const STORAGE_KEY = "mediapipeline-diag-tab";
    const page = document.querySelector('[data-page-panel="diagnostics"]');
    if (!page) return;
    const btns = Array.from(page.querySelectorAll(".settings-tab-btn[data-diag-tab]"));
    const panes = Array.from(page.querySelectorAll(".settings-tab-pane[data-diag-tab]"));
    if (!btns.length || !panes.length) return;

    btns.forEach((btn) => {
      btn.addEventListener("click", () => activateDiagnosticsTab(btn.dataset.diagTab));
    });

    let stored = "triage";
    try { stored = localStorage.getItem(STORAGE_KEY) || "triage"; } catch (_) {}
    // Validate stored value is a real tab, fall back to Overview.
    if (!btns.some((b) => b.dataset.diagTab === stored)) stored = "triage";
    activateDiagnosticsTab(stored);
  }

  function activateCompletedTab(tabId) {
    const page = document.querySelector('[data-page-panel="completed"]');
    if (!page) return false;
    const btns = Array.from(page.querySelectorAll(".settings-tab-btn[data-completed-tab]"));
    const panes = Array.from(page.querySelectorAll(".settings-tab-pane[data-completed-tab]"));
    if (!btns.length || !panes.length) return false;

    let normalized = String(tabId || "overview").trim() || "overview";
    if (normalized === "advanced" || normalized === "proof") normalized = "evidence";
    if (!btns.some((b) => b.dataset.completedTab === normalized)) normalized = "overview";
    btns.forEach((b) => {
      const active = b.dataset.completedTab === normalized;
      b.setAttribute("aria-selected", String(active));
    });
    panes.forEach((p) => {
      p.classList.toggle("is-active", p.dataset.completedTab === normalized);
    });
    try { localStorage.setItem(COMPLETED_TAB_STORAGE_KEY, normalized); } catch (_) {}
    syncTabAccessibility();
    updatePagePanelEmptyStates();
    return true;
  }

  function showCompletedOutputTab(tabId) {
    activateCompletedTab(tabId);
    navigateToPage("completed", { restoreFocus: false });
  }

  function activateCrossPageTarget(button) {
    const target = button?.dataset?.crossPageTarget || "";
    if (!target) return;
    navigateToPage(target, {
      focusSelector: button.dataset.crossPageFocus || "",
      restoreFocus: button.dataset.crossPageRestoreFocus !== "false",
    });
    if (target === "reports" && button.dataset.crossPageReportsTab) {
      const reportsView = window.mediaPipelineReportsView || {};
      reportsView.activateReportsTab?.(button.dataset.crossPageReportsTab);
    }
  }

  function focusUiQuickLinkTarget(selector) {
    const target = selector ? document.querySelector(selector) : null;
    if (!target) return false;
    if (typeof target.scrollIntoView === "function") {
      target.scrollIntoView({ block: "center", inline: "nearest" });
    }
    const focusable = typeof target.matches === "function"
      && target.matches("a[href], button, input, select, textarea, summary, [tabindex]");
    if (!focusable && typeof target.setAttribute === "function") target.setAttribute("tabindex", "-1");
    if (typeof target.focus === "function") target.focus({ preventScroll: true });
    return document.activeElement === target;
  }

  function focusUiQuickLinkWhenReady(selector, attemptsRemaining = 40, stableChecks = 0, focusClaimed = false) {
    const target = selector ? document.querySelector(selector) : null;
    const ready = Boolean(target && !target.disabled && target.getAttribute?.("aria-busy") !== "true");
    const active = document.activeElement;
    if (ready && focusClaimed && active !== target && active && active !== document.body && active.isConnected) return;
    if (ready && active !== target) focusUiQuickLinkTarget(selector);
    const nextStableChecks = ready && document.activeElement === target ? stableChecks + 1 : 0;
    const nextFocusClaimed = focusClaimed || nextStableChecks > 0;
    if (nextStableChecks >= 4 || attemptsRemaining <= 0) return;
    window.setTimeout(
      () => focusUiQuickLinkWhenReady(selector, attemptsRemaining - 1, nextStableChecks, nextFocusClaimed),
      50,
    );
  }

  function activateUiQuickLinkModule(moduleName, action, trigger) {
    const modules = {
      completed: window.mediaPipelineCompletedView,
      pending: window.mediaPipelinePendingPublishView,
      reports: window.mediaPipelineReportsView,
      network: window.mediaPipelineNetworkView,
      maintenance: window.mediaPipelineMaintenanceView,
      schedule: window.mediaPipelineScheduleView,
    };
    const module = modules[String(moduleName || "").trim().toLowerCase()];
    if (!module || typeof module.activateQuickLink !== "function") return false;
    return module.activateQuickLink(action, trigger) !== false;
  }

  function activateUiQuickLink(trigger) {
    const dataset = trigger?.dataset || {};
    const page = String(dataset.quickLinkPage || "").trim();
    if (page) {
      const current = document.querySelector("[data-page-panel].is-visible")?.dataset?.pagePanel || "";
      if (current === page && dataset.quickLinkFocus) {
        window.setTimeout(() => focusUiQuickLinkWhenReady(dataset.quickLinkFocus), 0);
      } else {
        navigateToPage(page, {
          focusSelector: dataset.quickLinkFocus || "",
          restoreFocus: !dataset.quickLinkFocus,
        });
      }
    }
    if (dataset.quickLinkReportsTab) {
      window.mediaPipelineReportsView?.activateReportsTab?.(dataset.quickLinkReportsTab);
    }
    if (dataset.quickLinkDiagTab) activateDiagnosticsTab(dataset.quickLinkDiagTab);
    if (dataset.quickLinkMetricsTab) {
      window.mediaPipelineMetricsView?.activateMetricsTab?.(dataset.quickLinkMetricsTab);
    }
    if (dataset.quickLinkLaunchTab) {
      window.mediaPipelineLaunchView?.activateLaunchTab?.(dataset.quickLinkLaunchTab);
    }
    if (dataset.quickLinkCompletedTab) activateCompletedTab(dataset.quickLinkCompletedTab);
    if (dataset.quickLinkModule || dataset.quickLinkAction) {
      activateUiQuickLinkModule(dataset.quickLinkModule, dataset.quickLinkAction, trigger);
    }
    if (dataset.quickLinkFocus && !page) {
      window.setTimeout(() => focusUiQuickLinkWhenReady(dataset.quickLinkFocus), 0);
    }
  }

  function initUiQuickLinks() {
    if (uiQuickLinkEventsInitialized) return;
    uiQuickLinkEventsInitialized = true;
    document.addEventListener("click", (event) => {
      const trigger = event.target?.closest?.("[data-ui-quick-link]");
      if (!trigger) return;
      event.preventDefault();
      activateUiQuickLink(trigger);
    });
    document.addEventListener("keydown", (event) => {
      if (event.key !== "Enter" && event.key !== " ") return;
      const trigger = event.target?.closest?.("[data-ui-quick-link]");
      if (!trigger) return;
      event.preventDefault();
      activateUiQuickLink(trigger);
    });
  }

  function initCompletedTabNav() {
    const page = document.querySelector('[data-page-panel="completed"]');
    if (!page) return;
    const btns = Array.from(page.querySelectorAll(".settings-tab-btn[data-completed-tab]"));
    const panes = Array.from(page.querySelectorAll(".settings-tab-pane[data-completed-tab]"));
    if (!btns.length || !panes.length) return;

    btns.forEach((btn) => {
      btn.addEventListener("click", () => activateCompletedTab(btn.dataset.completedTab));
    });

    let stored = "overview";
    try { stored = localStorage.getItem(COMPLETED_TAB_STORAGE_KEY) || "overview"; } catch (_) {}
    activateCompletedTab(stored);
  }

  function initNavigation() {
    const buttons = Array.from(document.querySelectorAll(".nav-button"));
    buttons.forEach((button) => {
      button.addEventListener("click", () => {
        navigateToPage(button.dataset.page, { restoreFocus: true });
      });
      button.addEventListener("keydown", (event) => {
        if (event.key !== "Enter") return;
        event.preventDefault();
        event.stopPropagation();
        if (event.repeat) return;
        navigateToPage(button.dataset.page, { restoreFocus: true });
      });
    });
    document.querySelectorAll("[data-cross-page-target]").forEach((button) => {
      button.addEventListener("click", () => activateCrossPageTarget(button));
    });
    initUiQuickLinks();
    syncTabAccessibility();
    // S15: topbar health/readiness buttons navigate to Diagnostics.
    const refreshHealthBadge = byId("refresh-health");
    if (refreshHealthBadge) refreshHealthBadge.addEventListener("click", () => navigateToPage("diagnostics", { restoreFocus: true }));
    const closeReadinessBadge = byId("close-readiness");
    if (closeReadinessBadge) closeReadinessBadge.addEventListener("click", () => navigateToPage("diagnostics", { restoreFocus: true }));
  }

  function sparkKind(event) {
    const t = String(event.event_type || event.type || event.Status || event.status || event || "").toLowerCase();
    if (/complet|done|accept|success|ok\b|publish|pass/.test(t))       return "success";
    if (/process|encod|remux|copy|audit|running|active|launch/.test(t)) return "active";
    if (/fail|error|block|reject/.test(t))                             return "failed";
    if (/pause|stop|skip|stale|warn|unknown/.test(t))                  return "warning";
    return "skip";
  }

  function renderSparkline(events) {
    const el = byId("pipeline-sparkline");
    if (!el) return;
    const items = Array.isArray(events) ? events.slice(-20) : [];
    if (!items.length) { el.replaceChildren(); return; }
    el.replaceChildren();
    items.forEach((ev) => {
      const sq = document.createElement("span");
      sq.className = "spark";
      sq.dataset.kind = sparkKind(ev);
      sq.title = String(ev.event_type || ev.type || "event");
      el.appendChild(sq);
    });
  }

  function initLaunchEvidenceToggle() {
    const STORAGE_KEY = "mediapipeline-launch-evidence-expanded";
    const body = byId("launch-evidence-body");
    const btn  = byId("launch-evidence-toggle");
    if (!body || !btn) return;

    function applyCollapsed(collapsed) {
      body.classList.toggle("is-collapsed", collapsed);
      btn.textContent = collapsed ? "Expand" : "Collapse";
      btn.setAttribute("aria-expanded", String(!collapsed));
      try { localStorage.setItem(STORAGE_KEY, collapsed ? "0" : "1"); } catch (_) {}
    }

    // Restore persisted preference (default: expanded)
    let stored = true;
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw !== null) stored = raw === "1";
    } catch (_) {}
    applyCollapsed(!stored);

    btn.addEventListener("click", () => applyCollapsed(!body.classList.contains("is-collapsed")));
  }

  function initCollapsibleSummaries() {
    document.querySelectorAll("pre.prose-block").forEach((pre) => {
      const next = pre.nextElementSibling;
      if (!next || !next.classList.contains("table-wrap")) return;

      const id = pre.id || "";
      const STORAGE_KEY = id ? `mediapipeline-summary-${id}` : null;

      // Default: collapsed (table first). Restore to expanded only if stored as "1".
      let isExpanded = false;
      if (STORAGE_KEY) {
        try {
          const raw = localStorage.getItem(STORAGE_KEY);
          if (raw === "1") isExpanded = true;
        } catch (_) {}
      }

      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "tertiary-button summary-toggle";
      if (id) btn.setAttribute("aria-controls", id);

      function applyState(expanded) {
        isExpanded = expanded;
        pre.hidden = !expanded;
        btn.textContent = expanded ? "Hide summary" : "Show summary";
        btn.setAttribute("aria-expanded", String(expanded));
        if (STORAGE_KEY) {
          try { localStorage.setItem(STORAGE_KEY, expanded ? "1" : "0"); } catch (_) {}
        }
      }

      btn.addEventListener("click", () => applyState(!isExpanded));
      pre.parentNode.insertBefore(btn, pre);
      applyState(isExpanded);
    });
  }

  function initThemeToggle() {
    applyThemePreference(false);
  }

  function applyThemePreference(_light) {
    const btn = byId("theme-toggle");
    if (btn && typeof btn.remove === "function") btn.remove();
    document.body.classList.remove("light-mode");
    try { localStorage.setItem(THEME_STORAGE_KEY, "dark"); } catch (_) {}
    window.mediaPipelineTelemetryView?.redrawTelemetryCharts?.();
  }

    return {
      updatePagePanelEmptyStates,
      syncTabAccessibility,
      showPage,
      navigateToPage,
      focusPageDestination,
      focusUiQuickLinkTarget,
      applyDefaultActionTooltips,
      initSettingsTabNav,
      activateDiagnosticsTab,
      initDiagnosticsTabNav,
      activateCompletedTab,
      initCompletedTabNav,
      activateUiQuickLink,
      initUiQuickLinks,
      initNavigation,
      renderSparkline,
      initLaunchEvidenceToggle,
      initCollapsibleSummaries,
      initThemeToggle,
      applyThemePreference,
    };
  }

  window.__appLifecycleNavigationModule = { createAppLifecycleNavigation };
})();
