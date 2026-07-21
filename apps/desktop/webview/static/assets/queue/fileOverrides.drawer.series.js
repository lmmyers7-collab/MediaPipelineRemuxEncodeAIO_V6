// queue/fileOverrides.drawer.series.js
// Series preview/apply modal behavior for the Queue file override drawer.

(function initFileOverridesDrawerSeriesModule() {
  // eslint-disable-next-line max-lines-per-function
  function createFileOverridesDrawerSeriesModule(ctx) {
    const {
      documentRef: document,
      state,
      byId,
      statusToneForMessage,
      setStatus,
      isPlainObject,
      backendErrorMessage,
    } = ctx;
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
      const queueView = window.mediaPipelineQueueView || {};
      if (typeof queueView.requestQueueScan === "function") {
        await queueView.requestQueueScan();
        return;
      }
      if (typeof window.refreshAll === "function") await window.refreshAll();
    }

    function buildOverridePayload() { return ctx.form.buildOverridePayload(); }
    function validateExactTrackSelectionsBeforeSave() { return ctx.tracks.validateExactTrackSelectionsBeforeSave(); }
    function setDrawerCommandButtonsDisabled(disabled) { return ctx.form.setDrawerCommandButtonsDisabled(disabled); }
    function openSeriesModal(trigger) { return ctx.focus.openSeriesModal(trigger); }
    function closeSeriesModal(options) { return ctx.focus.closeSeriesModal(options); }
    function loadFileOverrideEffectiveForPath(path, item) { return ctx.api.loadFileOverrideEffectiveForPath(path, item); }
    function closeFileSettingsDrawer() { return ctx.closeFileSettingsDrawer(); }
    function markDrawerClean() { return ctx.form.markDrawerClean(); }
    function confirmDiscardDrawerChanges(action) { return ctx.form.confirmDiscardDrawerChanges(action); }

  function buildSeriesProposedOverridePayload() {
    const payload = buildOverridePayload();
    if (!payload) return null;
    const proposed = { ...payload };
    delete proposed.path;
    return proposed;
  }

  function setSeriesStatus(message, tone = "") {
    const el = byId("fo-series-status");
    if (!el) return;
    const text = String(message || "");
    const resolvedTone = tone || statusToneForMessage(text);
    el.textContent = text;
    el.dataset.tone = resolvedTone;
    el.setAttribute("role", resolvedTone === "error" ? "alert" : "status");
    el.setAttribute("aria-live", resolvedTone === "error" ? "assertive" : "polite");
  }

  function seriesPreviewOperation(payload) {
    const operation = String(payload?.operation || state.foSeriesPreviewOperation || "apply").trim();
    return operation === "clear" ? "clear" : "apply";
  }

  function setSeriesModalMode(operation) {
    const mode = operation === "clear" ? "clear" : "apply";
    state.foSeriesPreviewOperation = mode;
    const title = byId("fo-series-modal-title");
    const applyButton = byId("fo-series-apply");
    const updateFilter = document.querySelector('[data-fo-series-filter="will_update"]');
    const protectedFilter = document.querySelector('[data-fo-series-filter="protected"]');
    if (title) title.textContent = mode === "clear" ? "Clear Series Overrides" : "Apply Override to Series";
    if (applyButton) applyButton.textContent = mode === "clear" ? "Clear From Series" : "Apply to Series";
    if (updateFilter) updateFilter.textContent = mode === "clear" ? "Will clear" : "Will update";
    if (protectedFilter) protectedFilter.textContent = mode === "clear" ? "Unchanged" : "Protected";
  }

  function resetSeriesPreviewState(operation = "apply") {
    setSeriesModalMode(operation);
    state.foSeriesPreviewPayload = null;
    state.foSeriesFilter = "all";
    document.querySelectorAll("[data-fo-series-filter]").forEach((button) => {
      button.setAttribute("aria-pressed", button.dataset.foSeriesFilter === "all" ? "true" : "false");
    });
    const summary = byId("fo-series-summary");
    const detected = byId("fo-series-detected");
    const fields = byId("fo-series-fields");
    const counts = byId("fo-series-counts");
    const issues = byId("fo-series-issues");
    const rows = byId("fo-series-rows");
    const applyButton = byId("fo-series-apply");
    if (summary) summary.textContent = "Preview has not loaded.";
    [detected, fields, counts, issues].forEach((el) => { if (el) el.replaceChildren(); });
    if (rows) {
      rows.replaceChildren();
      const row = document.createElement("tr");
      const cell = document.createElement("td");
      cell.colSpan = 4;
      cell.textContent = "No preview loaded.";
      row.appendChild(cell);
      rows.appendChild(row);
    }
    if (applyButton) applyButton.disabled = true;
    renderRemuxPilotPromotionResult(null);
    syncRemuxPilotPromotionState();
  }

  function fieldPathLabel(path) {
    const labels = {
      "routing.profile": "Route profile",
      "routing.routeThresholdMode": "Route threshold mode",
      "video.codec": "Video codec",
      "video.container": "Output container",
      "video.encodePreset": "Encode preset",
      "video.encodeLadder": "Encode ladder",
      "audio.keepTracks": "Audio keep tracks",
      "audio.dropTracks": "Audio drop tracks",
      "audio.maxChannels": "Audio max channels",
      "audio.preferDefaultLanguage": "Audio preferred default language",
      "subtitles.keepTracks": "Subtitle keep tracks",
      "subtitles.dropTracks": "Subtitle drop tracks",
      "subtitles.burnTrack": "Subtitle burn track",
      "subtitles.stripAll": "Subtitle strip all",
    };
    const text = String(path || "").trim();
    return labels[text] || text.replace(/[._-]+/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
  }

  function appendSeriesChip(container, label, tone = "") {
    if (!container) return;
    const chip = document.createElement("span");
    chip.textContent = label;
    if (tone) chip.dataset.tone = tone;
    container.appendChild(chip);
  }

  function seriesActionLabel(action) {
    const labels = {
      will_update: "Will update",
      replace_prior_batch: "Replace batch",
      protected_manual: "Protected",
      clear_batch: "Clear batch",
      clear_manual: "Clear manual",
      inherited: "Inherited",
      no_override: "No exact override",
      skipped: "Skipped",
      issue: "Issue",
    };
    return labels[String(action || "")] || String(action || "Unknown");
  }

  function seriesActionTone(action) {
    if (action === "protected_manual" || action === "inherited") return "warning";
    if (action === "issue") return "error";
    if (action === "skipped") return "warning";
    if (action === "no_override") return "";
    return "success";
  }

  function seriesEpisodeText(row) {
    const season = Number(row?.season_number || 0);
    const episode = Number(row?.episode_number || 0);
    if (season || episode) return `S${String(season).padStart(2, "0")}E${String(episode).padStart(2, "0")}`;
    return "";
  }

  function seriesRowVisible(row) {
    const action = String(row?.action || "");
    if (state.foSeriesFilter === "all") return true;
    if (state.foSeriesFilter === "will_update") {
      return ["will_update", "replace_prior_batch", "clear_batch", "clear_manual"].includes(action);
    }
    if (state.foSeriesFilter === "protected") return ["protected_manual", "inherited", "no_override"].includes(action);
    if (state.foSeriesFilter === "issues") return action === "issue";
    return true;
  }

  function renderSeriesRows(rows) {
    const body = byId("fo-series-rows");
    if (!body) return;
    body.replaceChildren();
    const visibleRows = (Array.isArray(rows) ? rows : []).filter(seriesRowVisible);
    if (!visibleRows.length) {
      const row = document.createElement("tr");
      const cell = document.createElement("td");
      cell.colSpan = 4;
      cell.textContent = "No rows match this filter.";
      row.appendChild(cell);
      body.appendChild(row);
      return;
    }
    visibleRows.forEach((previewRow) => {
      const row = document.createElement("tr");
      row.dataset.action = String(previewRow.action || "");

      const actionCell = document.createElement("td");
      const badge = document.createElement("span");
      badge.className = "fo-track-badge";
      badge.textContent = seriesActionLabel(previewRow.action);
      badge.dataset.tone = seriesActionTone(previewRow.action);
      actionCell.appendChild(badge);

      const fileCell = document.createElement("td");
      const displayName = String(previewRow.display_name || "").trim();
      const relativePath = String(previewRow.relative_path || "").trim();
      const sourcePath = String(previewRow.source_path || "").trim();
      fileCell.textContent = displayName || relativePath || sourcePath || "Unknown file";
      if (relativePath && relativePath !== fileCell.textContent) {
        const detail = document.createElement("small");
        detail.textContent = relativePath;
        fileCell.appendChild(document.createElement("br"));
        fileCell.appendChild(detail);
      }

      const episodeCell = document.createElement("td");
      episodeCell.textContent = seriesEpisodeText(previewRow);

      const reasonCell = document.createElement("td");
      reasonCell.textContent = String(previewRow.reason || "");

      row.append(actionCell, fileCell, episodeCell, reasonCell);
      body.appendChild(row);
    });
  }

  function renderSeriesPreview(payload) {
    const summary = byId("fo-series-summary");
    const detectedEl = byId("fo-series-detected");
    const fieldsEl = byId("fo-series-fields");
    const countsEl = byId("fo-series-counts");
    const issuesEl = byId("fo-series-issues");
    const applyButton = byId("fo-series-apply");
    const data = isPlainObject(payload) ? payload : {};
    const counts = isPlainObject(data.counts) ? data.counts : {};
    const detected = isPlainObject(data.detected) ? data.detected : {};
    const operation = seriesPreviewOperation(data);
    const isClear = operation === "clear";
    setSeriesModalMode(operation);

    if (summary) summary.textContent = String(data.message || "Series preview loaded.");
    [detectedEl, fieldsEl, countsEl, issuesEl].forEach((el) => { if (el) el.replaceChildren(); });

    appendSeriesChip(detectedEl, `Show: ${detected.show_name || "Unknown"}`);
    appendSeriesChip(detectedEl, `Root: ${detected.show_root || "Unknown"}`);
    appendSeriesChip(detectedEl, `Confidence: ${detected.confidence || "unknown"}`);

    const proposedFields = Array.isArray(data.proposed_fields) ? data.proposed_fields : [];
    if (isClear) {
      appendSeriesChip(fieldsEl, "Exact file override entries");
      appendSeriesChip(fieldsEl, "Folder and inherited rules stay unchanged", "warning");
    } else if (proposedFields.length) {
      proposedFields.forEach((field) => appendSeriesChip(fieldsEl, fieldPathLabel(field)));
    } else {
      appendSeriesChip(fieldsEl, "No proposed fields", "warning");
    }

    if (isClear) {
      appendSeriesChip(countsEl, `Clear batch: ${counts.clear_batch || 0}`);
      appendSeriesChip(countsEl, `Clear manual: ${counts.clear_manual || 0}`);
      appendSeriesChip(countsEl, `Inherited: ${counts.inherited || 0}`, counts.inherited ? "warning" : "");
      appendSeriesChip(countsEl, `No exact override: ${counts.no_override || 0}`);
    } else {
      appendSeriesChip(countsEl, `Will update: ${counts.will_update || 0}`);
      appendSeriesChip(countsEl, `Replace batch: ${counts.replace_prior_batch || 0}`);
      appendSeriesChip(countsEl, `Protected: ${counts.protected_manual || 0}`, counts.protected_manual ? "warning" : "");
    }
    appendSeriesChip(countsEl, `Skipped: ${counts.skipped || 0}`, counts.skipped ? "warning" : "");
    appendSeriesChip(countsEl, `Issues: ${counts.issue || 0}`, counts.issue ? "error" : "");

    const blockers = Array.isArray(data.blockers) ? data.blockers : [];
    const warnings = Array.isArray(data.warnings) ? data.warnings : [];
    blockers.forEach((blocker) => appendSeriesChip(issuesEl, String(blocker?.message || blocker || ""), "error"));
    warnings.forEach((warning) => appendSeriesChip(issuesEl, String(warning?.message || warning || ""), "warning"));
    if (!blockers.length && !warnings.length) appendSeriesChip(issuesEl, "No blockers reported.");

    renderSeriesRows(data.rows);
    if (applyButton) {
      applyButton.disabled = state.foCommandInFlight || !data.ok || blockers.length > 0 || !String(data.preview_fingerprint || "").trim();
    }
    setSeriesStatus(
      data.ok ? `Review the affected rows before ${isClear ? "clearing" : "applying"}.` : "Preview has blockers.",
      data.ok ? "info" : "error",
    );
  }

  function selectedPilotSourcePaths() {
    const rows = typeof window.getSelectedQueuePriorityRows === "function"
      ? window.getSelectedQueuePriorityRows()
      : (typeof window.getSelectedQueueRow === "function" ? [window.getSelectedQueueRow()] : []);
    const paths = [];
    const seen = new Set();
    (Array.isArray(rows) ? rows : []).forEach((row) => {
      const path = String(row?.source_path || "").trim();
      const key = path.toLocaleLowerCase();
      if (!path || seen.has(key)) return;
      seen.add(key);
      paths.push(path);
    });
    return paths;
  }

  function remuxPilotStatusText(paths) {
    if (!paths.length) return "";
    if (paths.length !== 3) return `${paths.length} selected; select exactly 3 pilot rows.`;
    return "3 pilot rows selected.";
  }

  function syncRemuxPilotPromotionState() {
    const button = byId("fo-remux-pilot-promote");
    if (!button) return;
    const paths = selectedPilotSourcePaths();
    button.hidden = paths.length === 0;
    button.disabled = state.foCommandInFlight || paths.length !== 3;
    button.title = remuxPilotStatusText(paths);
    button.setAttribute("aria-label", `Promote remux fallback from ${paths.length} selected pilot row${paths.length === 1 ? "" : "s"}`);
  }

  function appendProofChip(container, label, tone = "") {
    if (!container) return;
    const chip = document.createElement("span");
    chip.textContent = label;
    if (tone) chip.dataset.tone = tone;
    container.appendChild(chip);
  }

  function renderRemuxPilotPromotionResult(result) {
    const container = byId("fo-remux-pilot-proof");
    if (!container) return;
    container.replaceChildren();
    if (!result) {
      container.hidden = true;
      return;
    }
    container.hidden = false;
    const data = isPlainObject(result) ? result : {};
    const counts = isPlainObject(data.counts) ? data.counts : {};
    const detected = isPlainObject(data.detected_series) ? data.detected_series : {};
    const blockers = Array.isArray(data.blockers) ? data.blockers : [];
    const pilotEvidence = Array.isArray(data.pilot_evidence) ? data.pilot_evidence : [];
    appendProofChip(container, data.ok ? "Promotion ready" : "Promotion blocked", data.ok ? "success" : "error");
    appendProofChip(container, `Pilots: ${pilotEvidence.length}`);
    if (detected.show_name) appendProofChip(container, `Show: ${detected.show_name}`);
    appendProofChip(container, `Updated: ${counts.eligible_update_count || 0}`);
    appendProofChip(container, `Protected: ${counts.protected_manual || 0}`, counts.protected_manual ? "warning" : "");
    appendProofChip(container, `Skipped: ${counts.skipped || 0}`, counts.skipped ? "warning" : "");
    blockers.slice(0, 3).forEach((blocker) => {
      appendProofChip(container, String(blocker?.message || blocker || ""), "error");
    });
  }

  async function requestRemuxPilotPromotion() {
    if (state.foCommandInFlight) { setStatus("File override command already in progress."); return; }
    const pilotPaths = selectedPilotSourcePaths();
    if (pilotPaths.length !== 3) {
      setStatus(remuxPilotStatusText(pilotPaths) || "Select exactly 3 pilot rows.", "warning");
      syncRemuxPilotPromotionState();
      return;
    }
    state.foCommandInFlight = true;
    setDrawerCommandButtonsDisabled(true);
    syncRemuxPilotPromotionState();
    setStatus("Promoting remux fallback from selected pilots...");
    renderRemuxPilotPromotionResult(null);
    try {
      const result = await apiPost("/api/queue/file-overrides/remux-pilot-promote", {
        pilot_source_paths: pilotPaths,
        confirm_apply: true,
        reason: "queue_drawer_selected_pilot_paths",
      });
      renderRemuxPilotPromotionResult(result);
      if (!(result && result.ok)) {
        setStatus("Error: " + backendErrorMessage(result, "Remux pilot promotion failed."), "error");
        return;
      }
      appendCommandResultFn(result);
      await refreshAllFn();
      if (state.foCurrentPath) await loadFileOverrideEffectiveForPath(state.foCurrentPath, state.foCurrentItem);
      markDrawerClean();
      setStatus(result.message || "Remux pilot promotion applied.");
    } catch (err) {
      setStatus("Error promoting remux fallback: " + (err.message || err), "error");
    } finally {
      state.foCommandInFlight = false;
      setDrawerCommandButtonsDisabled(false);
      syncRemuxPilotPromotionState();
    }
  }

  async function requestSeriesPreview() {
    if (state.foCommandInFlight) { setStatus("File override command already in progress."); return; }
    if (!state.foCurrentPath) { setStatus("No file selected."); return; }
    if (!byId("fo-series-auto-detect")?.checked) {
      setStatus("Enable Auto-detect series scope before previewing a series batch.", "warning");
      return;
    }
    const proposed = buildSeriesProposedOverridePayload();
    if (!proposed) {
      setStatus("Set at least one override field before applying to a series.", "warning");
      return;
    }
    if (!validateExactTrackSelectionsBeforeSave()) return;

    resetSeriesPreviewState();
    state.foCommandInFlight = true;
    setDrawerCommandButtonsDisabled(true);
    setStatus("Previewing series override...");
    try {
      const result = await apiPost("/api/queue/file-overrides/series-preview", {
        path: state.foCurrentPath,
        proposed_override: proposed,
      });
      state.foSeriesPreviewPayload = result;
      renderSeriesPreview(result);
      openSeriesModal(byId("fo-series-preview-open"));
      if (result && result.ok) {
        setStatus("Series override preview loaded.");
      } else {
        setStatus("Error: " + backendErrorMessage(result, "Series preview failed."), "error");
      }
    } catch (err) {
      setStatus("Error previewing series override: " + (err.message || err), "error");
      setSeriesStatus("Error previewing series override: " + (err.message || err), "error");
    } finally {
      state.foCommandInFlight = false;
      setDrawerCommandButtonsDisabled(false);
      if (state.foSeriesPreviewPayload) renderSeriesPreview(state.foSeriesPreviewPayload);
    }
  }

  async function requestSeriesClearPreview() {
    if (state.foCommandInFlight) { setStatus("File override command already in progress."); return; }
    if (!state.foCurrentPath) { setStatus("No file selected."); return; }
    if (!byId("fo-series-auto-detect")?.checked) {
      setStatus("Enable Auto-detect series scope before previewing a series clear.", "warning");
      return;
    }
    if (!confirmDiscardDrawerChanges("preview clearing series overrides")) return;

    resetSeriesPreviewState("clear");
    state.foCommandInFlight = true;
    setDrawerCommandButtonsDisabled(true);
    setStatus("Previewing series override clear...");
    try {
      const result = await apiPost("/api/queue/file-overrides/series-clear-preview", {
        path: state.foCurrentPath,
      });
      state.foSeriesPreviewPayload = result;
      renderSeriesPreview(result);
      openSeriesModal(byId("fo-series-clear-open"));
      if (result && result.ok) {
        setStatus("Series clear preview loaded.");
      } else {
        setStatus("Error: " + backendErrorMessage(result, "Series clear preview failed."), "error");
      }
    } catch (err) {
      setStatus("Error previewing series clear: " + (err.message || err), "error");
      setSeriesStatus("Error previewing series clear: " + (err.message || err), "error");
    } finally {
      state.foCommandInFlight = false;
      setDrawerCommandButtonsDisabled(false);
      if (state.foSeriesPreviewPayload) renderSeriesPreview(state.foSeriesPreviewPayload);
    }
  }

  async function applySeriesClearPreview() {
    if (state.foCommandInFlight) { setSeriesStatus("File override command already in progress.", "warning"); return; }
    if (!state.foCurrentPath) { setSeriesStatus("No file selected.", "error"); return; }
    if (!state.foSeriesPreviewPayload || !state.foSeriesPreviewPayload.ok) {
      setSeriesStatus("Preview the series before clearing.", "warning");
      return;
    }
    const fingerprint = String(state.foSeriesPreviewPayload.preview_fingerprint || "").trim();
    if (!fingerprint) {
      setSeriesStatus("Preview fingerprint is missing; preview again.", "error");
      return;
    }

    state.foCommandInFlight = true;
    setDrawerCommandButtonsDisabled(true);
    setSeriesStatus("Clearing series overrides...");
    setStatus("Clearing series overrides...");
    try {
      const result = await apiPost("/api/queue/file-overrides/series-clear-apply", {
        path: state.foCurrentPath,
        confirm_apply: true,
        preview_fingerprint: fingerprint,
      });
      if (!(result && result.ok)) {
        setSeriesStatus("Error: " + backendErrorMessage(result, "Series clear failed."), "error");
        setStatus("Error: " + backendErrorMessage(result, "Series clear failed."), "error");
        return;
      }
      appendCommandResultFn(result);
      await refreshAllFn();
      await loadFileOverrideEffectiveForPath(state.foCurrentPath, state.foCurrentItem);
      markDrawerClean();
      setStatus(result.message || "Series overrides cleared.");
      closeSeriesModal({ restoreFocus: false, restoreDrawer: false });
      closeFileSettingsDrawer();
    } catch (err) {
      setSeriesStatus("Error clearing series overrides: " + (err.message || err), "error");
      setStatus("Error clearing series overrides: " + (err.message || err), "error");
    } finally {
      state.foCommandInFlight = false;
      setDrawerCommandButtonsDisabled(false);
    }
  }

  async function applySeriesPreview() {
    if (seriesPreviewOperation(state.foSeriesPreviewPayload) === "clear") {
      await applySeriesClearPreview();
      return;
    }
    if (state.foCommandInFlight) { setSeriesStatus("File override command already in progress.", "warning"); return; }
    if (!state.foCurrentPath) { setSeriesStatus("No file selected.", "error"); return; }
    if (!state.foSeriesPreviewPayload || !state.foSeriesPreviewPayload.ok) {
      setSeriesStatus("Preview the series before applying.", "warning");
      return;
    }
    const fingerprint = String(state.foSeriesPreviewPayload.preview_fingerprint || "").trim();
    if (!fingerprint) {
      setSeriesStatus("Preview fingerprint is missing; preview again.", "error");
      return;
    }
    const proposed = buildSeriesProposedOverridePayload();
    if (!proposed) {
      setSeriesStatus("Set at least one override field before applying to a series.", "warning");
      return;
    }
    if (!validateExactTrackSelectionsBeforeSave()) return;

    state.foCommandInFlight = true;
    setDrawerCommandButtonsDisabled(true);
    setSeriesStatus("Applying series override...");
    setStatus("Applying series override...");
    try {
      const result = await apiPost("/api/queue/file-overrides/series-apply", {
        path: state.foCurrentPath,
        proposed_override: proposed,
        confirm_apply: true,
        preview_fingerprint: fingerprint,
      });
      if (!(result && result.ok)) {
        setSeriesStatus("Error: " + backendErrorMessage(result, "Series apply failed."), "error");
        setStatus("Error: " + backendErrorMessage(result, "Series apply failed."), "error");
        return;
      }
      appendCommandResultFn(result);
      await refreshAllFn();
      await loadFileOverrideEffectiveForPath(state.foCurrentPath, state.foCurrentItem);
      markDrawerClean();
      setStatus(result.message || "Series override applied.");
      closeSeriesModal({ restoreFocus: false, restoreDrawer: false });
      closeFileSettingsDrawer();
    } catch (err) {
      setSeriesStatus("Error applying series override: " + (err.message || err), "error");
      setStatus("Error applying series override: " + (err.message || err), "error");
    } finally {
      state.foCommandInFlight = false;
      setDrawerCommandButtonsDisabled(false);
    }
  }


    return {
      buildSeriesProposedOverridePayload,
      setSeriesStatus,
      resetSeriesPreviewState,
      renderSeriesRows,
      renderSeriesPreview,
      renderRemuxPilotPromotionResult,
      syncRemuxPilotPromotionState,
      requestSeriesPreview,
      requestSeriesClearPreview,
      applySeriesPreview,
      requestRemuxPilotPromotion,
    };
  }

  window.__queueFileOverridesDrawerSeriesModule = { createFileOverridesDrawerSeriesModule };
})();
