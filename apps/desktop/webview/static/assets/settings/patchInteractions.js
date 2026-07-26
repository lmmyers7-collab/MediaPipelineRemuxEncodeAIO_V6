(function () {
  function createSettingsPatchInteractionsModule(deps) {
    deps = deps || {};
    const addSettingsEventHandlers = deps.addSettingsEventHandlers || {};
    const applyRouteRailBoundaryHeight = deps.applyRouteRailBoundaryHeight || function () {};
    const applyRouteRailBoundaryInput = deps.applyRouteRailBoundaryInput || function () {};
    const audioSettingsBuilderFields = deps.audioSettingsBuilderFields || [];
    const byId = deps.byId || function () { return null; };
    const fileSafetySettingsBuilderFields = deps.fileSafetySettingsBuilderFields || [];
    const markSettingsBuilderDirty = deps.markSettingsBuilderDirty || function () {};
    const networkSettingsBuilderFields = deps.networkSettingsBuilderFields || [];
    const pendingPublishSettingsBuilderFields = deps.pendingPublishSettingsBuilderFields || [];
    const qualityDetailSettingsBuilderFields = deps.qualityDetailSettingsBuilderFields || [];
    const queueSettingsBuilderFields = deps.queueSettingsBuilderFields || [];
    const renderAllLaunchPreflights = deps.renderAllLaunchPreflights || function () {};
    const renderSettingsPatchSummary = deps.renderSettingsPatchSummary || function () {};
    const renderSettingsRows = deps.renderSettingsRows || function () {};
    const resetSettingsBuilderFromConfig = deps.resetSettingsBuilderFromConfig || function (_fields, syncFromConfig) {
      if (typeof syncFromConfig === "function") syncFromConfig();
    };
    const routeClamp = deps.routeClamp || function (value) { return value; };
    const routeRailBoundaryConfig = deps.routeRailBoundaryConfig || function () { return null; };
    const routeRailCurrentBoundaryHeight = deps.routeRailCurrentBoundaryHeight || function () { return 0; };
    const runtimeSettingsBuilderFields = deps.runtimeSettingsBuilderFields || [];
    const settingsBuilderFields = deps.settingsBuilderFields || [];
    const subtitleSettingsBuilderFields = deps.subtitleSettingsBuilderFields || [];
    const videoDetailSettingsBuilderFields = deps.videoDetailSettingsBuilderFields || [];
    let routeRailDragState = null;

    function routeRailBoundaryFromSegment(target, event) {
      const boundary = target?.dataset?.routeDragBoundary || "";
      if (boundary === "first" || boundary === "second") return boundary;
      if (boundary === "middle" && event) {
        const rect = target.getBoundingClientRect();
        return event.clientX < rect.left + (rect.width / 2) ? "first" : "second";
      }
      return "";
    }

    function routeRailTrackRect(rail) {
      const track = rail?.querySelector?.(".settings-route-slider-track");
      const trackRect = track?.getBoundingClientRect?.();
      if (trackRect && trackRect.width > 0) return trackRect;
      return rail?.getBoundingClientRect?.() || null;
    }

    function routeRailHeightFromPointer(boundary, event, rail) {
      const config = routeRailBoundaryConfig(boundary);
      const rect = routeRailTrackRect(rail);
      if (!config || !event || !rect) return null;
      const ratio = routeClamp((event.clientX - rect.left) / Math.max(rect.width, 1), 0, 1);
      const height = 1080 + (ratio * (2160 - 1080));
      return routeClamp(Math.round(height), config.min, config.max);
    }

    function routeRailApplyDrag(event) {
      if (!routeRailDragState) return;
      event.preventDefault();
      const config = routeRailBoundaryConfig(routeRailDragState.boundary);
      if (!config) return;
      const height = routeRailDragState.mode === "absolute"
        ? routeRailHeightFromPointer(routeRailDragState.boundary, event, routeRailDragState.rail)
        : routeRailDragState.startHeight + Math.round(
          (event.clientX - routeRailDragState.startX) * ((2160 - 1080) / Math.max(routeRailDragState.railWidth, 1))
        );
      if (height === null || height === undefined) return;
      applyRouteRailBoundaryHeight(routeRailDragState.boundary, height);
      markSettingsBuilderDirty({ target: { id: routeRailDragState.inputId } });
    }

    function routeRailEndDrag() {
      if (!routeRailDragState) return;
      routeRailDragState.target?.classList.remove("is-dragging");
      routeRailDragState = null;
      document.removeEventListener("pointermove", routeRailApplyDrag);
      document.removeEventListener("pointerup", routeRailEndDrag);
      document.removeEventListener("pointercancel", routeRailEndDrag);
    }

    function routeRailStartDrag(event) {
      if (event.button !== undefined && event.button !== 0) return;
      if (event.target?.closest?.("input, select, textarea, button")) return;
      const target = event.target?.closest?.("[data-route-drag-boundary]");
      if (!target) return;
      const boundary = routeRailBoundaryFromSegment(target, event);
      const config = routeRailBoundaryConfig(boundary);
      const rail = target.closest(".settings-route-range-rail");
      if (!config || !rail) return;
      event.preventDefault();
      routeRailEndDrag();
      const trackRect = routeRailTrackRect(rail);
      const mode = target.classList.contains("settings-route-slider-hit") ? "absolute" : "delta";
      if (mode === "absolute") {
        const height = routeRailHeightFromPointer(boundary, event, rail);
        if (height !== null && height !== undefined) {
          applyRouteRailBoundaryHeight(boundary, height);
          markSettingsBuilderDirty({ target: { id: config.inputId } });
        }
      }
      routeRailDragState = {
        boundary,
        inputId: config.inputId,
        mode,
        rail,
        railWidth: Math.max(trackRect?.width || rail.getBoundingClientRect().width, 1),
        startHeight: routeRailCurrentBoundaryHeight(boundary),
        startX: event.clientX,
        target,
      };
      target.classList.add("is-dragging");
      document.addEventListener("pointermove", routeRailApplyDrag);
      document.addEventListener("pointerup", routeRailEndDrag);
      document.addEventListener("pointercancel", routeRailEndDrag);
    }

    function bindRouteRangeRailControls() {
      const rail = byId("settings-route-boundary-1080p-end-input")?.closest?.(".settings-route-range-rail");
      if (!rail || rail.dataset.routeRailBound === "true") return;
      rail.dataset.routeRailBound = "true";
      rail.addEventListener("pointerdown", routeRailStartDrag);
      [
        "settings-route-boundary-1080p-end-input",
        "settings-route-boundary-4k-start-input",
      ].forEach((id) => {
        const input = byId(id);
        if (!input) return;
        input.addEventListener("change", () => applyRouteRailBoundaryInput(id));
        input.addEventListener("keydown", (event) => {
          if (event.key !== "Enter") return;
          event.preventDefault();
          applyRouteRailBoundaryInput(id);
          input.blur();
        });
      });
    }

    function bindSettingsControls(fields, handler) {
      if (typeof handler !== "function") return;
      fields.forEach(([, id]) => {
        const control = byId(id);
        if (control) control.addEventListener("input", handler);
        if (control) control.addEventListener("change", handler);
      });
    }

    function bindSettingsClick(id, handler) {
      const element = byId(id);
      if (element && typeof handler === "function") element.addEventListener("click", handler);
    }

    function bindSettingsReset(id, fields, syncFromConfig) {
      bindSettingsClick(id, () => resetSettingsBuilderFromConfig(fields, syncFromConfig));
    }

    function initSettingsViewEvents() {
      bindSettingsClick("settings-validate-button", addSettingsEventHandlers.validateCurrentSettings);
      bindSettingsClick("settings-reload-button", addSettingsEventHandlers.reloadSettingsFromDisk);
      bindSettingsClick("settings-save-patch-button", addSettingsEventHandlers.saveSettingsPatch);
      bindSettingsClick("settings-summarize-patch-button", renderSettingsPatchSummary);
      const settingsPatchJson = byId("settings-patch-json");
      if (settingsPatchJson) settingsPatchJson.addEventListener("input", () => {
        if (typeof addSettingsEventHandlers.markSettingsPatchTouched === "function") addSettingsEventHandlers.markSettingsPatchTouched();
        renderSettingsPatchSummary();
        renderAllLaunchPreflights();
      });
      const changedOnly = byId("settings-patch-summary-changed-only");
      if (changedOnly) changedOnly.addEventListener("change", renderSettingsPatchSummary);
      bindSettingsClick("settings-builder-apply-button", addSettingsEventHandlers.applySettingsBuilderToPatch);
      bindSettingsReset("settings-builder-reset-button", settingsBuilderFields, addSettingsEventHandlers.syncSettingsBuilderFromConfig);
      bindSettingsControls(settingsBuilderFields, addSettingsEventHandlers.markSettingsBuilderDirty);
      bindRouteRangeRailControls();
      bindSettingsClick("settings-video-apply-button", addSettingsEventHandlers.applyVideoDetailSettingsBuilderToPatch);
      bindSettingsReset("settings-video-reset-button", videoDetailSettingsBuilderFields, addSettingsEventHandlers.syncVideoDetailSettingsBuilderFromConfig);
      bindSettingsControls(videoDetailSettingsBuilderFields, addSettingsEventHandlers.markVideoDetailSettingsBuilderDirty);
      bindSettingsClick("settings-quality-apply-button", addSettingsEventHandlers.applyQualityDetailSettingsBuilderToPatch);
      bindSettingsReset("settings-quality-reset-button", qualityDetailSettingsBuilderFields, addSettingsEventHandlers.syncQualityDetailSettingsBuilderFromConfig);
      bindSettingsControls(qualityDetailSettingsBuilderFields, addSettingsEventHandlers.markQualityDetailSettingsBuilderDirty);
      bindSettingsClick("settings-file-safety-apply-button", addSettingsEventHandlers.applyFileSafetySettingsBuilderToPatch);
      bindSettingsReset("settings-file-safety-reset-button", fileSafetySettingsBuilderFields, addSettingsEventHandlers.syncFileSafetySettingsBuilderFromConfig);
      bindSettingsControls(fileSafetySettingsBuilderFields, addSettingsEventHandlers.markFileSafetySettingsBuilderDirty);
      document.querySelectorAll("[data-settings-path-browse-key]").forEach((button) => {
        button.addEventListener("click", () => {
          if (typeof addSettingsEventHandlers.browseSettingsPath === "function") {
            addSettingsEventHandlers.browseSettingsPath(button.dataset.settingsPathKey || "", button.dataset.settingsPathInput || "");
          }
        });
      });
      bindSettingsClick("settings-network-apply-button", addSettingsEventHandlers.applyNetworkSettingsBuilderToPatch);
      bindSettingsReset("settings-network-reset-button", networkSettingsBuilderFields, addSettingsEventHandlers.syncNetworkSettingsBuilderFromConfig);
      bindSettingsControls(networkSettingsBuilderFields, addSettingsEventHandlers.markNetworkSettingsBuilderDirty);
      bindSettingsClick("settings-queue-apply-button", addSettingsEventHandlers.applyQueueSettingsBuilderToPatch);
      bindSettingsReset("settings-queue-reset-button", queueSettingsBuilderFields, addSettingsEventHandlers.syncQueueSettingsBuilderFromConfig);
      bindSettingsControls(queueSettingsBuilderFields, addSettingsEventHandlers.markQueueSettingsBuilderDirty);
      bindSettingsClick("settings-runtime-apply-button", addSettingsEventHandlers.applyRuntimeSettingsBuilderToPatch);
      bindSettingsReset("settings-runtime-reset-button", runtimeSettingsBuilderFields, addSettingsEventHandlers.syncRuntimeSettingsBuilderFromConfig);
      bindSettingsControls(runtimeSettingsBuilderFields, addSettingsEventHandlers.markRuntimeSettingsBuilderDirty);
      bindSettingsClick("settings-pending-apply-button", addSettingsEventHandlers.applyPendingPublishSettingsBuilderToPatch);
      bindSettingsReset("settings-pending-reset-button", pendingPublishSettingsBuilderFields, addSettingsEventHandlers.syncPendingPublishSettingsBuilderFromConfig);
      bindSettingsControls(pendingPublishSettingsBuilderFields, addSettingsEventHandlers.markPendingPublishSettingsBuilderDirty);
      bindSettingsClick("settings-subtitle-apply-button", addSettingsEventHandlers.applySubtitleSettingsBuilderToPatch);
      bindSettingsReset("settings-subtitle-reset-button", subtitleSettingsBuilderFields, addSettingsEventHandlers.syncSubtitleSettingsBuilderFromConfig);
      bindSettingsControls(subtitleSettingsBuilderFields, addSettingsEventHandlers.markSubtitleSettingsBuilderDirty);
      bindSettingsClick("settings-audio-apply-button", addSettingsEventHandlers.applyAudioSettingsBuilderToPatch);
      bindSettingsReset("settings-audio-reset-button", audioSettingsBuilderFields, addSettingsEventHandlers.syncAudioSettingsBuilderFromConfig);
      bindSettingsControls(audioSettingsBuilderFields, addSettingsEventHandlers.markAudioSettingsBuilderDirty);
      const settingsFilter = byId("settings-filter");
      if (settingsFilter) settingsFilter.addEventListener("input", renderSettingsRows);
    }


    return {
      initSettingsViewEvents,
    };
  }

  window.__settingsPatchInteractionsModule = {
    createSettingsPatchInteractionsModule,
  };
}());
