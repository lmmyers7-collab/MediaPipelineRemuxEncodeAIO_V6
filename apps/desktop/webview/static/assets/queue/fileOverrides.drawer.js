// queue/fileOverrides.drawer.js
// Public registration facade for the Queue file override drawer.

/* =============================================================================
   S80 — Per-File Settings Drawer  (Phase 3)
   Assembles focused child modules while preserving backend-owned override routes.
   ============================================================================= */
(function initFileSettingsDrawerModule() {
  const stateModule = window.__queueFileOverridesDrawerStateModule || {};
  const formModule = window.__queueFileOverridesDrawerFormModule || {};
  const seriesModule = window.__queueFileOverridesDrawerSeriesModule || {};
  const tracksModule = window.__queueFileOverridesDrawerTracksModule || {};
  const apiModule = window.__queueFileOverridesDrawerApiModule || {};
  const focusModule = window.__queueFileOverridesDrawerFocusModule || {};
  const routePreviewModule = window.__queueFileOverridesRoutePreviewModule || {};
  delete window.__queueFileOverridesDrawerStateModule;
  delete window.__queueFileOverridesDrawerFormModule;
  delete window.__queueFileOverridesDrawerSeriesModule;
  delete window.__queueFileOverridesDrawerTracksModule;
  delete window.__queueFileOverridesDrawerApiModule;
  delete window.__queueFileOverridesDrawerFocusModule;
  delete window.__queueFileOverridesRoutePreviewModule;

  const ctx = stateModule.createFileOverridesDrawerState({ documentRef: document, windowRef: window });
  ctx.tracks = tracksModule.createFileOverridesDrawerTracksModule(ctx);
  ctx.form = formModule.createFileOverridesDrawerFormModule(ctx);
  ctx.routePreview = typeof routePreviewModule.createFileOverridesRoutePreviewModule === "function"
    ? routePreviewModule.createFileOverridesRoutePreviewModule({
      apiPost: function routePreviewApiPost(path, body, options) {
        const fn = typeof window.apiPost === "function"
          ? window.apiPost
          : async function () { return { ok: false, message: "API unavailable." }; };
        return fn(path, body, options);
      },
      backendErrorMessage: ctx.backendErrorMessage,
      buildOverridePayload: () => ctx.form.buildOverridePayload(),
      byId: ctx.byId,
      documentRef: document,
      getCurrentPath: () => ctx.state.foCurrentPath,
      isPlainObject: ctx.isPlainObject,
      normalizeRouteChoiceOptions: ctx.form.normalizeRouteChoiceOptions,
      populateRouteSelectOptions: ctx.form.populateRouteSelectOptions,
      routeFieldConfig: ctx.ROUTE_FIELD_CONFIG,
      routeFieldKeys: ctx.ROUTE_FIELD_KEYS,
      routeForceValues: ctx.ROUTE_FORCE_VALUES,
      setStatus: ctx.setStatus,
    })
    : {
      clearProcessingRouteControls: function () {},
      clearRoutePreviewStatus: function () {},
      ensureRoutePreviewAllowsSave: async function () { return true; },
      loadRoutePreviewForPayload: async function () { return { ok: true }; },
      payloadHasRouteVideoOverride: function (payload) { return Boolean(payload && (ctx.isPlainObject(payload.routing) || ctx.isPlainObject(payload.video))); },
      refreshRoutePreviewFromCurrentForm: async function () {},
      renderProcessingRouteControls: function () {},
      renderRoutePreviewFromEffectivePayload: function () {},
      routeControlElement: function () { return null; },
      scheduleRoutePreviewFromCurrentForm: function () {},
    };
  ctx.focus = focusModule.createFileOverridesDrawerFocusModule(ctx);
  ctx.series = seriesModule.createFileOverridesDrawerSeriesModule(ctx);
  ctx.api = apiModule.createFileOverridesDrawerApiModule(ctx);

  function openFileSettingsDrawer(item, options = {}) {
    const queueItem = item || {};
    const state = ctx.state;
    state.fileSettingsDrawerTrigger = ctx.focus.fileSettingsTriggerFromOptions(options);
    const path = queueItem.source_path || "";
    state.foCurrentPath = path;
    state.foCurrentItem = queueItem;
    state.foLastEffectivePayload = null;
    state.foDrawerLoadToken = Number(state.foDrawerLoadToken || 0) + 1;
    const loadToken = state.foDrawerLoadToken;
    state.foDrawerLoading = true;
    state.foPendingClearFieldPaths = new Set();
    ctx.series.resetSeriesPreviewState();
    ctx.series.syncRemuxPilotPromotionState();

    const titleEl = ctx.byId("fo-drawer-title");
    const pathEl = ctx.byId("fo-drawer-path");
    const name = queueItem.display_name || queueItem.relative_path || path || "Unknown";
    if (titleEl) titleEl.textContent = "File — " + (name.length > 40 ? name.slice(0, 40) + "…" : name);
    if (pathEl) pathEl.textContent = path;

    ctx.form.clearDrawerForm();
    ctx.tracks.showDrawerTrackMetadataLoadingState();
    ctx.form.renderDrawerInheritedDefaults(ctx.form.getDrawerLibraryDefaults(queueItem));
    ctx.setStatus("Loading current override…");
    ctx.form.markDrawerClean();
    state.foDrawerLoading = true;
    ctx.form.setDrawerCommandButtonsDisabled(true);
    Promise.allSettled([
      ctx.api.loadFileOverrideForPath(path, loadToken),
      ctx.api.loadFileOverrideEffectiveForPath(path, queueItem, loadToken),
    ]).finally(() => {
      if (!ctx.api.drawerRequestIsCurrent(path, loadToken)) return;
      state.foDrawerLoading = false;
      ctx.form.setDrawerCommandButtonsDisabled(false);
      ctx.series.syncRemuxPilotPromotionState();
    });

    const overlay = ctx.byId("fo-overlay");
    const drawer = ctx.byId("fo-drawer");
    if (overlay) { overlay.hidden = false; overlay.removeAttribute("aria-hidden"); }
    if (drawer) { drawer.hidden = false; }

    setTimeout(ctx.focus.focusInitialFileSettingsDrawerControl, 50);
  }

  function requestCloseFileSettingsDrawer() {
    if (ctx.form.confirmDiscardDrawerChanges("close this drawer")) closeFileSettingsDrawer();
  }

  function closeFileSettingsDrawer() {
    const overlay = ctx.byId("fo-overlay");
    const drawer = ctx.byId("fo-drawer");
    ctx.focus.closeSeriesModal({ restoreFocus: false, restoreDrawer: false });
    ctx.series.resetSeriesPreviewState();
    if (overlay) { overlay.hidden = true; overlay.setAttribute("aria-hidden", "true"); }
    if (drawer) { drawer.hidden = true; }
    ctx.form.clearDrawerOverrideMarkers();
    ctx.form.clearDrawerUseInheritedButtons();
    ctx.tracks.clearDrawerTrackMetadata();
    ctx.routePreview.clearProcessingRouteControls();
    ctx.resetClosedDrawerState();
    ctx.focus.restoreFileSettingsDrawerFocus();
  }

  ctx.requestCloseFileSettingsDrawer = requestCloseFileSettingsDrawer;
  ctx.closeFileSettingsDrawer = closeFileSettingsDrawer;

  try {
    if (typeof window.__queueSetFileDrawer === "function") {
      window.__queueSetFileDrawer(openFileSettingsDrawer);
    }
  } finally {
    delete window.__queueSetFileDrawer;
  }

  function initFileSettingsDrawer() {
    const overlay = ctx.byId("fo-overlay");
    const closeBtn = ctx.byId("fo-drawer-close");
    const saveBtn = ctx.byId("fo-drawer-save");
    const clearBtn = ctx.byId("fo-drawer-clear");
    const seriesBtn = ctx.byId("fo-series-preview-open");
    const seriesClearBtn = ctx.byId("fo-series-clear-open");
    const remuxPilotBtn = ctx.byId("fo-remux-pilot-promote");
    const seriesApplyBtn = ctx.byId("fo-series-apply");
    const seriesCloseBtn = ctx.byId("fo-series-modal-close");
    const seriesCancelBtn = ctx.byId("fo-series-cancel");
    const seriesModal = ctx.byId("fo-series-modal");
    const stripAll = ctx.byId("fo-sub-strip-all");
    const routeOverrideToggle = ctx.byId("fo-route-override-toggle");

    if (overlay) overlay.addEventListener("click", requestCloseFileSettingsDrawer);
    if (closeBtn) closeBtn.addEventListener("click", requestCloseFileSettingsDrawer);
    if (saveBtn) saveBtn.addEventListener("click", ctx.api.saveFileOverrideForPath);
    if (clearBtn) clearBtn.addEventListener("click", ctx.api.clearFileOverrideForPath);
    if (seriesBtn) seriesBtn.addEventListener("click", ctx.series.requestSeriesPreview);
    if (seriesClearBtn) seriesClearBtn.addEventListener("click", ctx.series.requestSeriesClearPreview);
    if (remuxPilotBtn) remuxPilotBtn.addEventListener("click", ctx.series.requestRemuxPilotPromotion);
    if (seriesApplyBtn) seriesApplyBtn.addEventListener("click", ctx.series.applySeriesPreview);
    if (seriesCloseBtn) seriesCloseBtn.addEventListener("click", () => ctx.focus.closeSeriesModal());
    if (seriesCancelBtn) seriesCancelBtn.addEventListener("click", () => ctx.focus.closeSeriesModal());
    if (routeOverrideToggle) routeOverrideToggle.addEventListener("click", ctx.form.toggleRouteOverrideDisclosure);
    if (seriesModal) {
      seriesModal.addEventListener("click", (event) => {
        if (event.target === seriesModal) ctx.focus.closeSeriesModal();
      });
    }
    document.querySelectorAll("[data-fo-series-filter]").forEach((button) => {
      button.addEventListener("click", () => {
        ctx.state.foSeriesFilter = button.dataset.foSeriesFilter || "all";
        document.querySelectorAll("[data-fo-series-filter]").forEach((filterButton) => {
          filterButton.setAttribute("aria-pressed", filterButton === button ? "true" : "false");
        });
        ctx.series.renderSeriesRows(ctx.state.foSeriesPreviewPayload?.rows);
      });
    });
    if (stripAll) stripAll.addEventListener("change", ctx.form.syncSubFilterFields);
    if (stripAll) stripAll.addEventListener("change", ctx.routePreview.scheduleRoutePreviewFromCurrentForm);
    document.querySelectorAll("[data-fo-field] input, [data-fo-field] select").forEach((control) => {
      control.addEventListener("input", ctx.form.handleDrawerFormChanged);
      control.addEventListener("change", ctx.form.handleDrawerFormChanged);
    });
    document.querySelectorAll("[data-fo-use-inherited]").forEach((button) => {
      button.addEventListener("click", () => ctx.form.stageUseSavedPolicyField(button.dataset.foUseInherited || ""));
    });
    document.querySelectorAll("[data-fo-route-control]").forEach((control) => {
      control.addEventListener("change", ctx.routePreview.scheduleRoutePreviewFromCurrentForm);
      control.addEventListener("change", () => ctx.form.syncRouteOverrideDisclosure());
    });
    document.addEventListener("change", (event) => {
      if (event.target?.matches?.("[data-fo-track-action]")) {
        ctx.form.syncSubFilterFields();
        ctx.form.handleDrawerFormChanged();
        ctx.routePreview.scheduleRoutePreviewFromCurrentForm();
      }
    });

    document.addEventListener("keydown", ctx.focus.handleFileSettingsDrawerKeydown);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initFileSettingsDrawer);
  } else {
    initFileSettingsDrawer();
  }
})();
