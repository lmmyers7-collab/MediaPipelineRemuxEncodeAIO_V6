// queue/fileOverrides.drawer.api.js
// Backend API orchestration for the Queue file override drawer.

(function initFileOverridesDrawerApiModule() {
  // eslint-disable-next-line max-lines-per-function
  function createFileOverridesDrawerApiModule(ctx) {
    const {
      documentRef: document,
      state,
      FILE_OVERRIDES_ROUTE,
      FILE_OVERRIDES_EFFECTIVE_ROUTE,
      FILE_OVERRIDES_TRACKS_ROUTE,
      DRAWER_FIELD_PATHS,
      ROUTE_FIELD_KEYS,
      setStatus,
      isPlainObject,
      backendErrorMessage,
    } = ctx;
    function apiGet(path, options) {
      const fn = typeof window.apiGet === "function" ? window.apiGet : async function () { return null; };
      return fn(path, options);
    }
    function apiPost(path, body, options) {
      const fn = typeof window.apiPost === "function"
        ? window.apiPost
        : async function () { return { ok: false, message: "API unavailable." }; };
      return fn(path, body, options);
    }
    function appendCommandResultFn(result) {
      if (typeof window.appendCommandResult === "function") window.appendCommandResult(result);
    }
    async function refreshAllFn() {
      if (typeof window.refreshAll === "function") await window.refreshAll();
    }
    function effectivePayloadHasFileOverride() {
      return state.foLastEffectivePayload?.file_override_scope === "file"
        && isPlainObject(state.foLastEffectivePayload?.file_override);
    }
    function applyDisplayedQueueFileOverrideMarker(hasOverride) {
      const queueView = window.mediaPipelineQueueView || {};
      if (typeof queueView.applyDisplayedQueueFileOverrideMarker === "function") {
        queueView.applyDisplayedQueueFileOverrideMarker(state.foCurrentPath, hasOverride);
      }
    }

    function populateDrawerForm(entry) { return ctx.form.populateDrawerForm(entry); }
    function markDrawerClean() { return ctx.form.markDrawerClean(); }
    function clearDrawerForm(options) { return ctx.form.clearDrawerForm(options); }
    function applyFileOverrideEffectivePayload(payload, item) { return ctx.form.applyFileOverrideEffectivePayload(payload, item); }
    function showDrawerTrackMetadataLoadingState(message) { return ctx.tracks.showDrawerTrackMetadataLoadingState(message); }
    function renderDrawerTrackMetadata(payload) { return ctx.tracks.renderDrawerTrackMetadata(payload); }
    function trackMetadataFromTracksPayload(payload) { return ctx.tracks.trackMetadataFromTracksPayload(payload); }
    function clearDrawerTrackMetadata(message) { return ctx.tracks.clearDrawerTrackMetadata(message); }
    function buildOverridePayload() { return ctx.form.buildOverridePayload(); }
    function collectFileOverrideFieldsToClearOnSave() { return ctx.form.collectFileOverrideFieldsToClearOnSave(); }
    function validateExactTrackSelectionsBeforeSave() { return ctx.tracks.validateExactTrackSelectionsBeforeSave(); }
    function confirmSubtitleBurnBeforeSave(payload) { return ctx.tracks.confirmSubtitleBurnBeforeSave(payload); }
    function payloadHasRouteVideoOverride(payload) { return ctx.routePreview.payloadHasRouteVideoOverride(payload); }
    function fieldPathsIncludeRouteVideo(fieldPaths) { return ctx.form.fieldPathsIncludeRouteVideo(fieldPaths); }
    function setDrawerCommandButtonsDisabled(disabled) { return ctx.form.setDrawerCommandButtonsDisabled(disabled); }
    function ensureRoutePreviewAllowsSave(payload) { return ctx.routePreview.ensureRoutePreviewAllowsSave(payload); }
    function loadRoutePreviewForPayload(payload) { return ctx.routePreview.loadRoutePreviewForPayload(payload); }
    function refreshRoutePreviewFromCurrentForm() { return ctx.routePreview.refreshRoutePreviewFromCurrentForm(); }
    function resetExactTrackActionsForField(fieldKey) { return ctx.tracks.resetExactTrackActionsForField(fieldKey); }
    function confirmDiscardDrawerChanges(actionLabel) { return ctx.form.confirmDiscardDrawerChanges(actionLabel); }

  async function loadFileOverrideForPath(path) {
    if (!path) { setStatus("No source path — cannot load override."); return; }
    try {
      const url  = FILE_OVERRIDES_ROUTE + "?path=" + encodeURIComponent(path);
      const data = await apiGet(url);
      if (data && data.entry) {
        populateDrawerForm(data.entry);
        setStatus("Override loaded.");
        markDrawerClean();
      } else {
        clearDrawerForm({
          resetRouteControls: !state.foLastEffectivePayload,
          resetTrackMetadata: false,
        });
        setStatus("No override set for this file.");
        markDrawerClean();
      }
    } catch (err) {
      setStatus("Error loading override: " + (err.message || err));
    }
  }

  async function loadFileOverrideEffectiveForPath(path, item) {
    if (!path) return false;
    try {
      const url = FILE_OVERRIDES_EFFECTIVE_ROUTE + "?path=" + encodeURIComponent(path);
      const data = await apiGet(url);
      const applied = applyFileOverrideEffectivePayload(data, item);
      if (applied && !isPlainObject(data?.track_metadata)) await loadFileOverrideTracksForPath(path);
      return applied;
    } catch (_err) {
      await loadFileOverrideTracksForPath(path);
      return false;
    }
  }

  async function loadFileOverrideTracksForPath(path) {
    if (!path) return false;
    showDrawerTrackMetadataLoadingState();
    try {
      const url = FILE_OVERRIDES_TRACKS_ROUTE + "?path=" + encodeURIComponent(path);
      const data = await apiGet(url);
      if (path !== state.foCurrentPath) return false;
      renderDrawerTrackMetadata({
        track_metadata: trackMetadataFromTracksPayload(data),
        track_selection_preview: {},
      });
      return true;
    } catch (_err) {
      if (path === state.foCurrentPath) clearDrawerTrackMetadata("Track metadata could not be loaded.");
      return false;
    }
  }

  async function saveFileOverrideForPath() {
    if (state.foCommandInFlight) { setStatus("File override command already in progress."); return; }
    if (!state.foCurrentPath) { setStatus("No file selected."); return; }
    if (!state.foDrawerDirty) { setStatus("No unsaved changes to save.", "warning"); return; }
    const payload = buildOverridePayload();
    const clearFields = collectFileOverrideFieldsToClearOnSave();
    if (!payload && !clearFields.length) { setStatus("No overrides specified — nothing to save."); return; }
    if (payload && !validateExactTrackSelectionsBeforeSave()) return;
    if (payload && !confirmSubtitleBurnBeforeSave(payload)) return;
    const hasRouteVideoOverride = payloadHasRouteVideoOverride(payload);
    const clearsRouteVideoOverride = fieldPathsIncludeRouteVideo(clearFields);

    state.foCommandInFlight = true;
    setDrawerCommandButtonsDisabled(true);
    try {
      if (payload && !(await ensureRoutePreviewAllowsSave(payload))) return;
      setStatus("Saving…");
      let clearResult = null;
      if (clearFields.length) {
        clearResult = await apiPost("/api/queue/file-overrides", {
          path: state.foCurrentPath,
          clear_fields: clearFields,
        });
        if (!(clearResult && clearResult.ok)) {
          setStatus("Error: " + backendErrorMessage(clearResult));
          return;
        }
        clearFields.forEach((fieldPath) => {
          const fieldKey = Object.keys(DRAWER_FIELD_PATHS).find((key) => DRAWER_FIELD_PATHS[key] === fieldPath);
          if (fieldKey) resetExactTrackActionsForField(fieldKey);
        });
      }

      let result = clearResult;
      if (payload) {
        result = await apiPost("/api/queue/file-overrides", payload);
        if (!(result && result.ok)) {
          setStatus("Error: " + backendErrorMessage(result));
          return;
        }
        populateDrawerForm({
          audio: payload.audio || {},
          subtitles: payload.subtitles || {},
          routing: payload.routing || {},
          video: payload.video || {},
        });
      }

      const reloaded = await loadFileOverrideEffectiveForPath(state.foCurrentPath, state.foCurrentItem);
      if (payload && hasRouteVideoOverride) await loadRoutePreviewForPayload(payload);
      else if (clearsRouteVideoOverride) await refreshRoutePreviewFromCurrentForm();
      if (result && result.ok) {
        const savedMessage = payload
          ? "Override saved. Takes effect on next pipeline round."
          : "Override field cleared. Saved policy value will be used.";
        applyDisplayedQueueFileOverrideMarker(payload ? true : effectivePayloadHasFileOverride());
        setStatus(reloaded ? savedMessage : `${savedMessage} Effective settings could not be reloaded.`);
        markDrawerClean();
        if (clearResult && clearResult !== result) appendCommandResultFn(clearResult);
        appendCommandResultFn(result);
        await refreshAllFn();
      }
    } catch (err) {
      setStatus("Error saving override: " + (err.message || err));
    } finally {
      state.foCommandInFlight = false;
      setDrawerCommandButtonsDisabled(false);
    }
  }

  async function clearFileOverrideField(fieldKey) {
    if (state.foCommandInFlight) { setStatus("File override command already in progress."); return; }
    const fieldPath = DRAWER_FIELD_PATHS[fieldKey];
    if (!state.foCurrentPath) { setStatus("No file selected."); return; }
    if (!fieldPath) { setStatus("Cannot clear this override field."); return; }

    state.foCommandInFlight = true;
    setDrawerCommandButtonsDisabled(true);
    const button = document.querySelector(`[data-fo-use-inherited="${fieldKey}"]`);
    if (button) button.disabled = true;
    setStatus("Clearing field override…");
    try {
      const result = await apiPost("/api/queue/file-overrides", {
        path: state.foCurrentPath,
        clear_fields: [fieldPath],
      });
      if (result && result.ok) {
        resetExactTrackActionsForField(fieldKey);
        const reloaded = await loadFileOverrideEffectiveForPath(state.foCurrentPath, state.foCurrentItem);
        if (ROUTE_FIELD_KEYS.includes(fieldKey)) await refreshRoutePreviewFromCurrentForm();
        applyDisplayedQueueFileOverrideMarker(effectivePayloadHasFileOverride());
        setStatus(reloaded ? "Override field cleared. Saved policy value will be used." : "Override field cleared, but effective settings could not be reloaded.");
        markDrawerClean();
        appendCommandResultFn(result);
        await refreshAllFn();
      } else {
        setStatus("Error: " + backendErrorMessage(result));
      }
    } catch (err) {
      setStatus("Error clearing override field: " + (err.message || err));
    } finally {
      state.foCommandInFlight = false;
      setDrawerCommandButtonsDisabled(false);
      if (button && !button.hidden) button.disabled = false;
    }
  }

  async function clearFileOverrideForPath() {
    if (state.foCommandInFlight) { setStatus("File override command already in progress."); return; }
    if (!state.foCurrentPath) { setStatus("No file selected."); return; }
    if (!confirmDiscardDrawerChanges("clear the saved override")) return;
    const confirmed = window.confirm("Clear all saved file override fields for this file and use saved policy values?");
    if (!confirmed) {
      setStatus("Clear Override cancelled.", "warning");
      return;
    }
    state.foCommandInFlight = true;
    setDrawerCommandButtonsDisabled(true);
    setStatus("Clearing…");
    try {
      const result = await apiPost("/api/queue/file-overrides", { path: state.foCurrentPath, clear: true });
      if (result && result.ok) {
        clearDrawerForm();
        await loadFileOverrideEffectiveForPath(state.foCurrentPath, state.foCurrentItem);
        applyDisplayedQueueFileOverrideMarker(false);
        setStatus("Override cleared.");
        markDrawerClean();
        appendCommandResultFn(result);
        await refreshAllFn();
      } else {
        setStatus("Error: " + backendErrorMessage(result));
      }
    } catch (err) {
      setStatus("Error clearing override: " + (err.message || err));
    } finally {
      state.foCommandInFlight = false;
      setDrawerCommandButtonsDisabled(false);
    }
  }

    return {
      loadFileOverrideForPath,
      loadFileOverrideEffectiveForPath,
      loadFileOverrideTracksForPath,
      saveFileOverrideForPath,
      clearFileOverrideField,
      clearFileOverrideForPath,
    };
  }

  window.__queueFileOverridesDrawerApiModule = { createFileOverridesDrawerApiModule };
})();
