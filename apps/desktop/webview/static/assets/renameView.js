(function () {
  const renameLabels = window.mediaPipelineRenameLabels || {};
  const renameStatusExplanation = window.renameStatusExplanation || renameLabels.renameStatusExplanation || function () { return "Unknown: refresh preview before applying."; };
  const renamePreviewSourceLabel = window.renamePreviewSourceLabel || renameLabels.renamePreviewSourceLabel || function (value) { return value ? String(value) : "Not reported"; };
  const renameConfidenceExplanation = window.renameConfidenceExplanation || renameLabels.renameConfidenceExplanation || function () { return "Confidence not reported by backend."; };
  const renameConfidenceLabel = window.renameConfidenceLabel || renameLabels.renameConfidenceLabel || function () { return ""; };
  const renameHistoryView = window.mediaPipelineRenameHistoryView || {};
  const isRenameApplyCommand = window.isRenameApplyCommand || renameHistoryView.isRenameApplyCommand || function () { return false; };
  const renameApplyHistoryLine = window.renameApplyHistoryLine || renameHistoryView.renameApplyHistoryLine || function () { return ""; };
  const renderRenameApplyHistory = window.renderRenameApplyHistory || renameHistoryView.renderRenameApplyHistory || function () {};
  const RENAME_PREVIEW_RENDER_LIMIT = 250;
  const RENAME_CLEANING_FILTER_STORAGE_KEY = "mediapipeline.rename.cleaningFilters.v1";
  const RENAME_MOVIE_FILTER_CATALOG_ROUTE = "/api/rename/movie-cleaning-filters";
  const RENAME_CLEAN_FILENAME_PREVIEW_ROUTE = "/api/rename/clean-filename-preview";
  const RENAME_CLEANING_IDS = {
    removeTerms: ["settings-rename-remove-terms", "rename-remove-terms"],
    status: ["settings-rename-cleaning-filter-status", "rename-cleaning-filter-status"],
    summary: ["settings-rename-cleaning-filter-summary", "rename-cleaning-filter-summary"],
    saveButton: ["settings-rename-cleaning-filters-save-button", "rename-cleaning-filters-save-button"],
    resetButton: ["settings-rename-cleaning-filters-reset-button", "rename-cleaning-filters-reset-button"],
  };
  let lastRenameRows = [];
  let selectedRenameSourceKey = "";
  const renameFinalOverrides = {};
  const renameForceOverrides = {};
  let lastRenameEmptyMessage = "No rename rows available.";
  let renamePreviewRequestId = 0;
  let activeRenamePreviewRequestId = 0;
  let renameFilterPreviewRequestId = 0;
  let renameFilterPreviewTimer = 0;
  let renamePreviewInFlight = false;
  let renameBrowseInFlight = false;
  let renameApplyInFlight = false;
  let renameCleaningFilterEventsBound = false;
  let lastRenamePreviewSignature = "";
  let renamePreviewStale = false;
  let renameCleaningFilterSaveMessage = "";
  let renameCleaningFilterSaveMessageUntil = 0;
  const checkedRenameSourceKeys = new Set();
  const renamePathOrigins = {};

  function byAnyId(ids) {
    for (const id of ids) {
      const node = byId(id);
      if (node) return node;
    }
    return null;
  }

  function renameCleaningNode(name) {
    return byAnyId(RENAME_CLEANING_IDS[name] || []);
  }

  function collectRenameRequest() {
    const rawPaths = (byId("rename-paths")?.value || "")
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean);
    return {
      paths: rawPaths,
      mode: byId("rename-mode")?.value || "tv",
      template_preset: byId("rename-template-preset")?.value || "",
      show_name: byId("rename-show")?.value || "",
      season: byId("rename-season")?.value || "S01",
      start_episode: byId("rename-start")?.value || "E01",
      movie_title: byId("rename-movie-title")?.value || "",
      movie_year: byId("rename-movie-year")?.value || "",
      final_name_overrides: { ...renameFinalOverrides },
      rename_sidecars: Boolean(byId("rename-sidecars")?.checked),
      force_pipeline_name: Boolean(byId("rename-force-pipeline")?.checked),
      force_pipeline_name_overrides: { ...renameForceOverrides },
      use_pipeline_naming_preview: Boolean(byId("rename-pipeline-preview")?.checked),
    };
  }

  function renameRequestSignatureFromRequest(request) {
    return JSON.stringify(request || {});
  }

  function renameCurrentRequestSignature() {
    return renameRequestSignatureFromRequest(collectRenameRequest());
  }

  function renamePreviewStatusText() {
    return `${lastRenameRows.length} preview row${lastRenameRows.length === 1 ? "" : "s"}`;
  }

  function updateRenamePreviewFreshnessState() {
    const wasStale = renamePreviewStale;
    renamePreviewStale = Boolean(
      lastRenameRows.length
      && lastRenamePreviewSignature
      && renameCurrentRequestSignature() !== lastRenamePreviewSignature
    );
    if (renamePreviewStale) {
      setText("rename-preview-status", "Preview out of date");
    } else if (wasStale && lastRenameRows.length) {
      setText("rename-preview-status", renamePreviewStatusText());
    }
    return renamePreviewStale;
  }

  function renameMarkInputChanged() {
    updateRenamePreviewFreshnessState();
    syncRenameCommandButtons();
  }

  function renameCleaningFilterTextareas() {
    return Array.from(document.querySelectorAll("[data-rename-movie-filter-terms], [data-movie-filter-terms]"));
  }

  function renameMovieFilterCheckboxes() {
    return Array.from(document.querySelectorAll("[data-rename-movie-filter], [data-movie-filter]"));
  }

  function collectRenameMovieFilterOptions() {
    const options = {};
    renameMovieFilterCheckboxes().forEach((input) => {
      const key = input.dataset.renameMovieFilter || input.dataset.movieFilter || "";
      if (key) options[key] = Boolean(input.checked);
    });
    return options;
  }

  function parseRenameFilterTerms(value) {
    const seen = new Set();
    const terms = [];
    String(value || "").split(/[,;\n]+/).forEach((item) => {
      const term = item.trim();
      const key = term.toLowerCase();
      if (!term || seen.has(key)) return;
      seen.add(key);
      terms.push(term);
    });
    return terms;
  }

  function collectRenameMovieFilterTermsText() {
    const terms = {};
    renameCleaningFilterTextareas().forEach((input) => {
      const key = input.dataset.renameMovieFilterTerms || input.dataset.movieFilterTerms || "";
      if (key) terms[key] = input.value || "";
    });
    return terms;
  }

  function collectRenameMovieFilterTerms() {
    const terms = {};
    Object.entries(collectRenameMovieFilterTermsText()).forEach(([key, value]) => {
      terms[key] = parseRenameFilterTerms(value);
    });
    return terms;
  }

  function renameCleaningFilterState() {
    return {
      remove_terms_text: renameCleaningNode("removeTerms")?.value || "",
      movie_filter_options: collectRenameMovieFilterOptions(),
      movie_filter_terms_text: collectRenameMovieFilterTermsText(),
    };
  }

  function renameCleaningFilterConfigPatch() {
    return {
      RenameMovieFilterOptions: collectRenameMovieFilterOptions(),
      RenameMovieFilterTerms: collectRenameMovieFilterTerms(),
      RenameMovieRemoveTerms: parseRenameFilterTerms(renameCleaningNode("removeTerms")?.value || ""),
    };
  }

  function renderRenameCleaningFilterEditor(message = "") {
    const movieTerms = collectRenameMovieFilterTerms();
    const categoryCounts = Object.entries(movieTerms)
      .map(([key, values]) => `${key.replace(/_/g, " ")}=${values.length}`)
      .join("; ");
    const customTermsCount = parseRenameFilterTerms(renameCleaningNode("removeTerms")?.value || "").length;
    const statusNode = renameCleaningNode("status");
    if (statusNode) statusNode.textContent = "Backend terms active";
    const summaryNode = renameCleaningNode("summary");
    if (summaryNode) setText(summaryNode.id, [
      message,
      `Custom negative terms: ${customTermsCount}`,
      `Movie filter terms: ${categoryCounts || "none"}`,
      "Save writes RenameMovieFilterOptions, RenameMovieFilterTerms, and RenameMovieRemoveTerms through backend Settings.",
      "Saved filters affect future pipeline output naming, Rename preview planning, and Rename apply planning.",
      "Browser storage is draft recovery only; unsaved edits affect only the filename test preview on this page.",
      "Mutation guardrail: editing cleaning filters changes rename preview/apply planning only; filesystem changes still require backend rename apply confirmation.",
    ].filter(Boolean).join("\n"));
  }

  function saveRenameCleaningFilterDraft(message = "Cleaning filter draft retained in this browser.") {
    try {
      localStorage.setItem(RENAME_CLEANING_FILTER_STORAGE_KEY, JSON.stringify(renameCleaningFilterState()));
      renderRenameCleaningFilterEditor(message);
      updateRenameFilterPreview();
      return true;
    } catch (_) {
      renderRenameCleaningFilterEditor("Cleaning filters could not be saved in browser storage.");
      return false;
    }
  }

  async function saveRenameCleaningFilterState(message = "Rename cleaning filters saved to backend settings.") {
    const draftSaved = saveRenameCleaningFilterDraft("Saving rename cleaning filters to backend settings...");
    const post = typeof apiPost === "function" ? apiPost : window.apiPost;
    if (typeof post !== "function") {
      renderRenameCleaningFilterEditor(
        draftSaved
          ? "Backend Settings API is unavailable; filter edits were retained only as a browser draft."
          : "Backend Settings API is unavailable and browser draft storage failed."
      );
      return false;
    }
    const changes = renameCleaningFilterConfigPatch();
    try {
      const preview = await post("/api/settings/preview-patch", { changes });
      appendCommandResult(preview);
      if (!preview?.ok) {
        renderRenameCleaningFilterEditor(preview?.message || "Backend rejected the rename filter settings preview.");
        return false;
      }
      const result = await post("/api/settings/save-patch", { changes, confirm_save: true });
      appendCommandResult(result);
      if (!result?.ok) {
        renderRenameCleaningFilterEditor(result?.message || "Rename filter settings save failed.");
        return false;
      }
      try { localStorage.removeItem(RENAME_CLEANING_FILTER_STORAGE_KEY); } catch (_) {}
      renameCleaningFilterSaveMessage = message;
      renameCleaningFilterSaveMessageUntil = Date.now() + 1500;
      const reloaded = result?.data?.reloaded !== false;
      if (reloaded) {
        await loadRenameMovieFilterCatalog({ preserveValues: false, message });
      }
      if (reloaded && typeof window.refreshAll === "function") await window.refreshAll();
      renderRenameCleaningFilterEditor(message);
      updateRenameFilterPreview();
      syncRenameCommandButtons();
      return true;
    } catch (error) {
      renderRenameCleaningFilterEditor(`Rename filter settings save failed: ${error?.message || error}`);
      return false;
    }
  }

  function resetRenameCleaningFilters() {
    const removeTerms = renameCleaningNode("removeTerms");
    if (removeTerms) removeTerms.value = removeTerms.dataset.defaultTerms || "sample, trailer, extras, featurette, deleted scenes, behind the scenes";
    renameMovieFilterCheckboxes().forEach((input) => {
      input.checked = Boolean(input.defaultChecked);
    });
    renameCleaningFilterTextareas().forEach((input) => {
      input.value = input.dataset.defaultTerms || "";
    });
    try { localStorage.removeItem(RENAME_CLEANING_FILTER_STORAGE_KEY); } catch (_) {}
    renderRenameCleaningFilterEditor("Cleaning filter draft reset to saved backend policy.");
    updateRenameFilterPreview();
    syncRenameCommandButtons();
  }

  function loadRenameCleaningFilterState() {
    let state = null;
    try { state = JSON.parse(localStorage.getItem(RENAME_CLEANING_FILTER_STORAGE_KEY) || "null"); } catch (_) { state = null; }
    if (!state || typeof state !== "object") {
      renderRenameCleaningFilterEditor();
      return false;
    }
    const removeTerms = renameCleaningNode("removeTerms");
    if (removeTerms && typeof state.remove_terms_text === "string") removeTerms.value = state.remove_terms_text;
    const filterOptions = state.movie_filter_options && typeof state.movie_filter_options === "object"
      ? state.movie_filter_options
      : {};
    renameMovieFilterCheckboxes().forEach((input) => {
      const key = input.dataset.renameMovieFilter || input.dataset.movieFilter || "";
      if (Object.prototype.hasOwnProperty.call(filterOptions, key)) input.checked = Boolean(filterOptions[key]);
    });
    const textByKey = state.movie_filter_terms_text && typeof state.movie_filter_terms_text === "object"
      ? state.movie_filter_terms_text
      : {};
    renameCleaningFilterTextareas().forEach((input) => {
      const key = input.dataset.renameMovieFilterTerms || input.dataset.movieFilterTerms || "";
      if (Object.prototype.hasOwnProperty.call(textByKey, key)) input.value = String(textByKey[key] || "");
    });
    renderRenameCleaningFilterEditor("Unsaved cleaning filter draft loaded from browser storage.");
    updateRenameFilterPreview();
    return true;
  }

  async function loadRenameMovieFilterCatalog(options = {}) {
    const get = typeof apiGet === "function" ? apiGet : window.apiGet;
    if (typeof get !== "function") return;
    try {
      const payload = await get(RENAME_MOVIE_FILTER_CATALOG_ROUTE, { timeoutMs: 10000 });
      const textByKey = payload?.saved_terms_text && typeof payload.saved_terms_text === "object"
        ? payload.saved_terms_text
        : payload?.default_terms_text && typeof payload.default_terms_text === "object"
          ? payload.default_terms_text
          : {};
      const optionsByKey = payload?.saved_options && typeof payload.saved_options === "object"
        ? payload.saved_options
        : {};
      const removeTermsText = typeof payload?.saved_remove_terms_text === "string"
        ? payload.saved_remove_terms_text
        : "";
      const removeTerms = renameCleaningNode("removeTerms");
      if (removeTerms && removeTermsText) {
        const previousDefault = removeTerms.dataset.defaultTerms || "";
        removeTerms.dataset.defaultTerms = removeTermsText;
        if (!options.preserveValues && (!removeTerms.value || removeTerms.value === previousDefault)) {
          removeTerms.value = removeTermsText;
        }
      }
      renameMovieFilterCheckboxes().forEach((input) => {
        const key = input.dataset.renameMovieFilter || input.dataset.movieFilter || "";
        if (!key || !Object.prototype.hasOwnProperty.call(optionsByKey, key)) return;
        input.defaultChecked = Boolean(optionsByKey[key]);
        if (!options.preserveValues) input.checked = Boolean(optionsByKey[key]);
      });
      renameCleaningFilterTextareas().forEach((input) => {
        const key = input.dataset.renameMovieFilterTerms || input.dataset.movieFilterTerms || "";
        const backendText = String(textByKey[key] || "");
        if (!backendText) return;
        const previousDefault = input.dataset.defaultTerms || "";
        input.dataset.defaultTerms = backendText;
        if (!options.preserveValues && (!input.value || input.value === previousDefault)) {
          input.value = backendText;
        }
      });
      const activeSaveMessage = renameCleaningFilterSaveMessage
        && Date.now() < renameCleaningFilterSaveMessageUntil;
      renderRenameCleaningFilterEditor(
        (activeSaveMessage ? renameCleaningFilterSaveMessage : options.message)
          || options.message
          || (options.preserveValues
            ? "Saved backend movie filter policy loaded; unsaved browser draft preserved."
            : "Saved backend movie filter policy loaded.")
      );
      updateRenameFilterPreview();
    } catch (error) {
      renderRenameCleaningFilterEditor(`Backend movie filter catalog could not load; using packaged fallback terms. ${error?.message || error}`);
    }
  }

  function renameCleanFilenamePreviewQuery(rawInput) {
    const pairs = [
      ["filename", rawInput],
      ["remove_terms_text", renameCleaningNode("removeTerms")?.value || ""],
      ["movie_filter_options", JSON.stringify(collectRenameMovieFilterOptions())],
      ["movie_filter_terms", JSON.stringify(collectRenameMovieFilterTerms())],
    ];
    return `${RENAME_CLEAN_FILENAME_PREVIEW_ROUTE}?${pairs
      .map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(value)}`)
      .join("&")}`;
  }

  function renderRenameFilterPreviewPayload(payload, rawInput) {
    const targetName = String(payload?.target_name || payload?.cleaned_title || "").trim();
    const lines = [];
    if (targetName) {
      lines.push(targetName);
    } else {
      lines.push("Filename is empty after backend movie cleaning.");
    }
    (payload?.warnings || []).forEach((warning) => lines.push(`Warning: ${warning}`));
    (payload?.errors || []).forEach((error) => lines.push(`Error: ${error}`));
    const policySource = payload?.rename_cleaning_policy_source || payload?.effective_policy_source || payload?.movie_filter_terms_mode;
    if (policySource) {
      lines.push(`Movie filter policy: ${String(policySource).replace(/_/g, " ")}.`);
    }
    lines.push("Source: backend clean_pipeline_movie_name.");
    return {
      text: lines.join("\n"),
      state: targetName && targetName !== rawInput ? "changed" : "unchanged",
      status: payload?.ok ? "Backend clean preview complete." : "Backend clean preview needs review.",
    };
  }

  function updateRenameFilterPreview(options = {}) {
    const input = document.getElementById("settings-rename-preview-input");
    const output = document.getElementById("settings-rename-preview-output");
    const status = document.getElementById("settings-rename-preview-status");
    if (!input || !output) return;
    const raw = input.value.trim();
    if (typeof window.clearTimeout === "function") window.clearTimeout(renameFilterPreviewTimer);
    const requestId = ++renameFilterPreviewRequestId;
    if (!raw) {
      output.textContent = "";
      output.dataset.state = "";
      if (status) status.textContent = "Backend cleaner waits for input.";
      return;
    }
    const runPreview = async () => {
      const get = typeof apiGet === "function" ? apiGet : window.apiGet;
      if (typeof get !== "function") {
        output.textContent = "Backend filename preview is unavailable in this surface.";
        output.dataset.state = "unchanged";
        if (status) status.textContent = "Backend cleaner unavailable.";
        return;
      }
      if (status) status.textContent = "Testing with backend cleaner...";
      try {
        const payload = await get(renameCleanFilenamePreviewQuery(raw), { timeoutMs: 10000 });
        if (requestId !== renameFilterPreviewRequestId) return;
        const rendered = renderRenameFilterPreviewPayload(payload, raw);
        output.textContent = rendered.text;
        output.dataset.state = rendered.state;
        if (status) status.textContent = rendered.status;
      } catch (error) {
        if (requestId !== renameFilterPreviewRequestId) return;
        output.textContent = `Backend filename preview failed: ${error?.message || error}`;
        output.dataset.state = "unchanged";
        if (status) status.textContent = "Backend clean preview failed.";
      }
    };
    if (options.immediate) {
      runPreview();
    } else {
      renameFilterPreviewTimer = typeof window.setTimeout === "function" ? window.setTimeout(runPreview, 300) : 0;
      if (!renameFilterPreviewTimer) runPreview();
    }
  }

  function initRenameCleaningFilterEditorEvents() {
    const preserveValues = loadRenameCleaningFilterState();
    loadRenameMovieFilterCatalog({ preserveValues });
    if (renameCleaningFilterEventsBound) return;
    if (!renameCleaningNode("saveButton") && !renameCleaningNode("removeTerms") && !renameCleaningFilterTextareas().length) return;
    renameCleaningFilterEventsBound = true;
    const removeTerms = renameCleaningNode("removeTerms");
    if (removeTerms) removeTerms.addEventListener("input", () => {
      renderRenameCleaningFilterEditor();
      syncRenameCommandButtons();
      updateRenameFilterPreview();
    });
    renameCleaningFilterTextareas().forEach((input) => {
      input.addEventListener("input", () => {
        renderRenameCleaningFilterEditor();
        syncRenameCommandButtons();
        updateRenameFilterPreview();
      });
    });
    const saveButton = renameCleaningNode("saveButton");
    if (saveButton) saveButton.addEventListener("click", () => saveRenameCleaningFilterState());
    const resetButton = renameCleaningNode("resetButton");
    if (resetButton) resetButton.addEventListener("click", resetRenameCleaningFilters);
    const previewInput = document.getElementById("settings-rename-preview-input");
    if (previewInput) {
      previewInput.addEventListener("input", updateRenameFilterPreview);
      document.getElementById("settings-rename-preview-button")
        ?.addEventListener("click", () => updateRenameFilterPreview({ immediate: true }));
      renameMovieFilterCheckboxes()
        .forEach((cb) => cb.addEventListener("change", updateRenameFilterPreview));
    }
  }

  function renameSourceKey(item) {
    return String(item?.source || "").toLowerCase();
  }

  function getSelectedRenameRow() {
    if (!selectedRenameSourceKey) return null;
    return lastRenameRows.find((row) => renameSourceKey(row) === selectedRenameSourceKey) || null;
  }

  function getCheckedRenameRows() {
    return lastRenameRows.filter((row) => checkedRenameSourceKeys.has(renameSourceKey(row)));
  }

  function renameRenderedRowsCount(rows = lastRenameRows) {
    const rowCount = Array.isArray(rows) ? rows.length : 0;
    return Math.min(rowCount, RENAME_PREVIEW_RENDER_LIMIT);
  }

  function renameRenderCapText(rows = lastRenameRows) {
    const rowCount = Array.isArray(rows) ? rows.length : 0;
    if (rowCount <= RENAME_PREVIEW_RENDER_LIMIT) return "";
    return `${RENAME_PREVIEW_RENDER_LIMIT} shown / ${rowCount} preview rows`;
  }

  function updateRenameTableLegend(tbody) {
    updateTableStatusLegend("rename-table-legend", tbody, "Rename rows");
    const capText = renameRenderCapText();
    if (!capText) return;
    const current = byId("rename-table-legend")?.textContent || "";
    setText("rename-table-legend", `${current} Display cap: ${capText} rendered. Checked/apply scope may include backend preview rows that are not visible in the table.`);
  }

  function renameCurrentFinalName(row) {
    const key = renameSourceKey(row);
    return renameFinalOverrides[key] || row?.target_name || row?.pipeline_guess || row?.source_name || "";
  }

  function renameRowCanApply(item) {
    if (!item) return false;
    if (String(item.status || "").toLowerCase() === "blocked") return false;
    return !(Array.isArray(item.errors) && item.errors.length);
  }

  function renameImportantRowReason(item) {
    const errors = Array.isArray(item?.errors) ? item.errors.map(String) : [];
    const warnings = Array.isArray(item?.warnings) ? item.warnings.map(String) : [];
    const candidates = [...errors, ...warnings];
    const match = (pattern) => candidates.find((value) => value.toLowerCase().includes(pattern));
    if (match("two selected files would produce the same destination")) return "duplicate destination";
    if (match("destination already exists")) return "destination already exists";
    if (match("sidecar destination already exists")) return "sidecar destination exists";
    if (match("outside configured")) return "outside configured roots";
    return candidates[0] || "";
  }

  function renameRowStatusDisplay(item) {
    const status = String(item?.status || "").trim();
    const reason = renameImportantRowReason(item);
    if (!status || !reason) return status;
    return `${status.charAt(0).toUpperCase()}${status.slice(1)}: ${reason}`;
  }

  function getRenameApplyScopeRows() {
    const checked = getCheckedRenameRows();
    if (checked.length) return { rows: checked, source: "checked rows" };
    const applicable = lastRenameRows.filter((row) => renameRowCanApply(row));
    return applicable.length
      ? { rows: applicable, source: "all applicable preview rows" }
      : { rows: [], source: "none" };
  }

  function syncRenameCheckedCount() {
    const rows = getCheckedRenameRows();
    const blocked = rows.filter((row) => !renameRowCanApply(row)).length;
    const text = blocked
      ? `${rows.length} checked; ${blocked} blocked`
      : `${rows.length} checked`;
    setText("rename-selected-count", text);
    renderRenameSelectionAudit();
    renderRenameApplyReadiness();
    renderRenameBulkEditor();
    syncRenameCommandButtons();
  }

  function setRenameRowChecked(item, checked) {
    const key = renameSourceKey(item);
    if (!key) return;
    if (checked) checkedRenameSourceKeys.add(key);
    else checkedRenameSourceKeys.delete(key);
    syncRenameCheckedCount();
  }

  function checkApplicableRenameRows() {
    checkedRenameSourceKeys.clear();
    lastRenameRows.forEach((row) => {
      if (renameRowCanApply(row)) checkedRenameSourceKeys.add(renameSourceKey(row));
    });
    renderRenameRows();
  }

  function clearCheckedRenameRows() {
    checkedRenameSourceKeys.clear();
    renderRenameRows();
  }

  function renamePathLines() {
    return (byId("rename-paths")?.value || "").split(/\r?\n/);
  }

  function setRenamePathLines(lines) {
    const input = byId("rename-paths");
    if (!input) return;
    input.value = lines.join("\n");
    renderRenameFileSourceSummary();
    syncRenameCommandButtons();
  }

  function renameSourcePathFromRow(row) {
    return String(row?.source_path || row?.source || row?.path || row?.file || row?.input_path || "").trim();
  }

  function renameSourceLabelFromRow(row) {
    return String(row?.display_name || row?.relative_path || row?.source_name || row?.source_path || row?.source || "").trim();
  }

  function renameCurrentPathValues() {
    return renamePathLines().map((line) => line.trim()).filter(Boolean);
  }

  function renamePathOriginKey(path) {
    return String(path || "").trim().toLowerCase();
  }

  function rememberRenamePathOrigins(paths, origin) {
    const label = String(origin || "").trim();
    if (!label) return;
    (Array.isArray(paths) ? paths : []).forEach((path) => {
      const key = renamePathOriginKey(path);
      if (key) renamePathOrigins[key] = label;
    });
  }

  function pruneRenamePathOrigins(paths = renameCurrentPathValues()) {
    const current = new Set(paths.map(renamePathOriginKey).filter(Boolean));
    Object.keys(renamePathOrigins).forEach((key) => {
      if (!current.has(key)) delete renamePathOrigins[key];
    });
  }

  function renamePathOriginCounts(paths = renameCurrentPathValues()) {
    const counts = {};
    paths.forEach((path) => {
      const origin = renamePathOrigins[renamePathOriginKey(path)] || "manual";
      counts[origin] = (counts[origin] || 0) + 1;
    });
    return counts;
  }

  function renamePathOriginSummary(paths = renameCurrentPathValues()) {
    const counts = renamePathOriginCounts(paths);
    const parts = Object.keys(counts)
      .sort()
      .map((origin) => `${origin}=${counts[origin]}`);
    return parts.length ? `Origins: ${parts.join(", ")}` : "";
  }

  function renderRenameFileSourceSummary(message = "") {
    const paths = renameCurrentPathValues();
    pruneRenamePathOrigins(paths);
    const queueRows = typeof window.getLastQueueRows === "function"
      ? window.getLastQueueRows()
      : (window.mediaPipelineQueueView?.getLastQueueRows?.() || []);
    const selectedQueue = typeof window.getSelectedQueueRow === "function"
      ? window.getSelectedQueueRow()
      : (window.mediaPipelineQueueView?.getSelectedQueueRow?.() || null);
    const selectedPath = renameSourcePathFromRow(selectedQueue);
    setText("rename-file-source-status", paths.length ? `${paths.length} path${paths.length === 1 ? "" : "s"}` : "No paths");
    setText("rename-file-source-summary", [
      message,
      paths.length ? `Source paths staged: ${paths.length}` : "No source paths staged.",
      paths.length ? renamePathOriginSummary(paths) : "",
      `Loaded Queue rows: ${Array.isArray(queueRows) ? queueRows.length : 0}`,
      `Selected Queue source: ${selectedPath || "(none)"}`,
      paths.length ? `First staged path: ${paths[0]}` : "",
    ].filter(Boolean).join("\n"));
  }

  function appendRenamePaths(paths, sourceLabel, origin = "") {
    const input = byId("rename-paths");
    if (!input) return 0;
    const current = renameCurrentPathValues();
    const seen = new Set(current.map((line) => line.toLowerCase()));
    const additions = [];
    (Array.isArray(paths) ? paths : []).forEach((path) => {
      const text = String(path || "").trim();
      const key = text.toLowerCase();
      if (!text || seen.has(key)) return;
      seen.add(key);
      additions.push(text);
    });
    if (!additions.length) {
      renderRenameFileSourceSummary(`${sourceLabel || "Source"} added no new paths.`);
      return 0;
    }
    input.value = [...current, ...additions].join("\n");
    rememberRenamePathOrigins(additions, origin || "manual");
    renderRenameFileSourceSummary(`${sourceLabel || "Source"} added ${additions.length} path${additions.length === 1 ? "" : "s"}.`);
    syncRenameCommandButtons();
    return additions.length;
  }

  function addRenamePathFromInput() {
    const input = byId("rename-add-path-input");
    const path = String(input?.value || "").trim();
    if (!path) {
      renderRenameFileSourceSummary("Enter or paste a source path, then click Add manual path.");
      return 0;
    }
    const added = appendRenamePaths([path], "Manual path", "manual");
    if (added && input) input.value = "";
    syncRenameCommandButtons();
    return added;
  }

  async function browseRenamePaths(selectionMode = "files") {
    if (renameBrowseInFlight || renamePreviewInFlight || renameApplyInFlight) {
      renderRenameFileSourceSummary("Rename path browser is busy. Wait for the current Rename command to finish.");
      return;
    }
    const rawMode = String(selectionMode || "").toLowerCase();
    const mode = rawMode === "folder" || rawMode === "folder_files" ? rawMode : "files";
    const currentPaths = renameCurrentPathValues();
    const typedPath = String(byId("rename-add-path-input")?.value || "").trim();
    const initialPath = currentPaths[0] || typedPath;
    renameBrowseInFlight = true;
    syncRenameCommandButtons();
    renderRenameFileSourceSummary(mode === "folder" ? "Opening Windows folder browser..." : "Opening Windows file browser...");
    try {
      const result = await apiPost("/api/rename/browse", { selection_mode: mode, initial_path: initialPath });
      appendCommandResult(result);
      const data = result.data && typeof result.data === "object" ? result.data : {};
      const paths = Array.isArray(data.paths) ? data.paths : [];
      if (!result.ok) {
        renderRenameFileSourceSummary(result.message || "Windows file browser failed.");
        return;
      }
      if (data.canceled || !paths.length) {
        renderRenameFileSourceSummary(result.message || "Windows file browser canceled.");
        return;
      }
      const folderMode = mode === "folder" || mode === "folder_files";
      appendRenamePaths(paths, folderMode ? "Windows folder browser" : "Windows file browser", folderMode ? "folder" : "browse");
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      const routeMissing = String(message || "").trim().toLowerCase() === "not found";
      const displayMessage = routeMissing
        ? "Rename path browser route is not available in the running backend. Restart the Local API/Tauri shell, then open Rename again."
        : `Windows file browser failed:\n${message}`;
      appendCommandResult({
        command: "rename.browse",
        ok: false,
        severity: "error",
        message: displayMessage,
      });
      renderRenameFileSourceSummary(displayMessage);
    } finally {
      renameBrowseInFlight = false;
      syncRenameCommandButtons();
    }
  }

  function clearRenamePaths() {
    const input = byId("rename-paths");
    if (input) input.value = "";
    const addInput = byId("rename-add-path-input");
    if (addInput) addInput.value = "";
    lastRenameRows = [];
    selectedRenameSourceKey = "";
    checkedRenameSourceKeys.clear();
    Object.keys(renamePathOrigins).forEach((key) => delete renamePathOrigins[key]);
    lastRenamePreviewSignature = "";
    renamePreviewStale = false;
    lastRenameEmptyMessage = "No paths entered. Add one file path per line, then run Preview.";
    clearRows(byId("rename-rows"), 6, lastRenameEmptyMessage);
    setText("rename-status", "Idle");
    setText("rename-summary", lastRenameEmptyMessage);
    renderRenameFileSourceSummary("Cleared staged rename paths.");
    renderRenameBatchSafety({ rows: [], counts: {} });
    renderRenamePipelineHandoff({ rows: [], counts: {} });
    renderRenameReviewBoard({ rows: [], counts: {} });
    renderRenameSelectionAudit();
    renderRenameApplyReadiness();
    renderRenameBulkEditor();
    syncRenameCheckedCount();
    syncRenameCommandButtons();
  }

  function useSelectedQueueRowForRename() {
    const row = typeof window.getSelectedQueueRow === "function"
      ? window.getSelectedQueueRow()
      : (window.mediaPipelineQueueView?.getSelectedQueueRow?.() || null);
    const path = renameSourcePathFromRow(row);
    if (!path) {
      renderRenameFileSourceSummary("No selected Queue row with a source path.");
      return;
    }
    appendRenamePaths([path], renameSourceLabelFromRow(row) || "Selected Queue row", "queue");
  }

  function useLoadedQueueRowsForRename() {
    const rows = typeof window.getLastQueueRows === "function"
      ? window.getLastQueueRows()
      : (window.mediaPipelineQueueView?.getLastQueueRows?.() || []);
    const paths = (Array.isArray(rows) ? rows : []).map(renameSourcePathFromRow).filter(Boolean);
    if (!paths.length) {
      renderRenameFileSourceSummary("No loaded Queue source paths.");
      return;
    }
    appendRenamePaths(paths, "Loaded Queue rows", "queue");
  }

  function renameLineKey(line) {
    return String(line || "").trim().toLowerCase();
  }

  function checkedOrSelectedRenameKeys() {
    if (checkedRenameSourceKeys.size) return new Set(checkedRenameSourceKeys);
    return selectedRenameSourceKey ? new Set([selectedRenameSourceKey]) : new Set();
  }

  function moveCheckedRenamePaths(direction) {
    const keys = checkedOrSelectedRenameKeys();
    if (!keys.size) {
      setText("rename-detail", "Check one or more rows, or select one row, before moving path order.");
      return;
    }
    const lines = renamePathLines();
    const indexed = lines.map((line) => ({ line, selected: keys.has(renameLineKey(line)) }));
    const selectedCount = indexed.filter((item) => item.selected).length;
    if (!selectedCount) {
      setText("rename-detail", "Checked/selected rename rows are not present in the Paths textbox. Refresh preview or re-add paths before moving order.");
      return;
    }
    if (Number(direction) < 0) {
      for (let index = 1; index < indexed.length; index += 1) {
        if (indexed[index].selected && !indexed[index - 1].selected) {
          const previous = indexed[index - 1];
          indexed[index - 1] = indexed[index];
          indexed[index] = previous;
        }
      }
    } else {
      for (let index = indexed.length - 2; index >= 0; index -= 1) {
        if (indexed[index].selected && !indexed[index + 1].selected) {
          const next = indexed[index + 1];
          indexed[index + 1] = indexed[index];
          indexed[index] = next;
        }
      }
    }
    setRenamePathLines(indexed.map((item) => item.line));
    setText("rename-detail", `Moved ${selectedCount} path row(s) ${Number(direction) < 0 ? "up" : "down"}. Run Preview to rebuild TV sequence numbering from the new order.`);
  }

  function naturalCompareText(left, right) {
    const leftParts = String(left || "").toLowerCase().match(/\d+|\D+/g) || [String(left || "").toLowerCase()];
    const rightParts = String(right || "").toLowerCase().match(/\d+|\D+/g) || [String(right || "").toLowerCase()];
    const length = Math.max(leftParts.length, rightParts.length);
    for (let index = 0; index < length; index += 1) {
      const a = leftParts[index] || "";
      const b = rightParts[index] || "";
      const aNumber = /^\d+$/.test(a) ? Number(a) : NaN;
      const bNumber = /^\d+$/.test(b) ? Number(b) : NaN;
      if (Number.isFinite(aNumber) && Number.isFinite(bNumber) && aNumber !== bNumber) return aNumber - bNumber;
      if (a !== b) return a < b ? -1 : 1;
    }
    return 0;
  }

  function naturalSortRenamePaths() {
    const lines = renamePathLines();
    const nonEmpty = lines.filter((line) => line.trim());
    const empty = lines.filter((line) => !line.trim());
    nonEmpty.sort(naturalCompareText);
    setRenamePathLines([...nonEmpty, ...empty]);
    setText("rename-detail", "Paths were natural-sorted. Run Preview to rebuild TV sequence numbering from the new order.");
  }

  function syncRenameSelectedInputs(item) {
    const key = renameSourceKey(item);
    const finalInput = byId("rename-selected-final");
    const forceInput = byId("rename-selected-force");
    if (finalInput) finalInput.value = renameFinalOverrides[key] || item?.target_name || "";
    if (forceInput) forceInput.checked = Boolean(renameForceOverrides[key] ?? item?.force_pipeline_name);
  }

  function selectRenameRow(item) {
    const key = renameSourceKey(item);
    selectedRenameSourceKey = key;
    syncRenameSelectedInputs(item);
    renderRenameDetail(item || null);
    renderRenameBulkEditor();
    renderRenameRows();
  }

  const renamePreviewSlice = window.mediaPipelineRenamePreviewSlice.create({
    RENAME_PREVIEW_RENDER_LIMIT,
    collectRenameRequest,
    getCheckedRenameRows,
    getLastRenameEmptyMessage: () => lastRenameEmptyMessage,
    getLastSettings: () => (typeof window.getLastSettings === "function" ? window.getLastSettings() : {}),
    getRenameFinalOverrides: () => renameFinalOverrides,
    getRenameForceOverrides: () => renameForceOverrides,
    renamePreviewSourceLabel,
    renameRenderedRowsCount,
    renameSourceKey,
    setText,
  });
  const {
    renderRenameBatchSafety,
    renderRenamePipelineHandoff,
    renderRenameReviewBoard,
    renderRenameSummary,
    renameBatchSafetyLines,
    renameDuplicateTargets,
    renameFormatCounts,
    renamePipelineHandoffLines,
    renamePipelineHandoffStatus,
    renamePreviewAggregateObject,
    renameReviewBoardLines,
    renameReviewBoardStatus,
    renameSavedSettingsConfig,
    renameTemplateLabel,
  } = renamePreviewSlice;

  function renameBulkScopeRows() {
    const scope = byId("rename-bulk-scope")?.value || "checked";
    if (scope === "selected") {
      const selected = getSelectedRenameRow();
      return selected && renameRowCanApply(selected) ? [selected] : [];
    }
    if (scope === "all_applicable") return lastRenameRows.filter((row) => renameRowCanApply(row));
    return getCheckedRenameRows().filter((row) => renameRowCanApply(row));
  }

  function renameBulkScopeLabel() {
    const scope = byId("rename-bulk-scope")?.value || "checked";
    if (scope === "selected") return "selected row";
    if (scope === "all_applicable") return "all applicable preview rows";
    return "checked rows";
  }

  function renameSplitFilename(name) {
    const value = String(name || "").trim();
    const dotIndex = value.lastIndexOf(".");
    if (dotIndex <= 0 || dotIndex === value.length - 1) return { base: value, ext: "" };
    return { base: value.slice(0, dotIndex), ext: value.slice(dotIndex) };
  }

  function renameBulkEditedName(name) {
    const findValue = byId("rename-bulk-find")?.value || "";
    const replaceValue = byId("rename-bulk-replace")?.value || "";
    const prefixValue = byId("rename-bulk-prefix")?.value || "";
    const suffixValue = byId("rename-bulk-suffix")?.value || "";
    const parts = renameSplitFilename(name);
    let edited = parts.base;
    if (findValue) edited = edited.split(findValue).join(replaceValue);
    edited = `${prefixValue}${edited}${suffixValue}`.trim();
    return edited ? `${edited}${parts.ext}` : "";
  }

  function renameBulkHasEditInput() {
    return Boolean(
      (byId("rename-bulk-find")?.value || "")
      || (byId("rename-bulk-prefix")?.value || "")
      || (byId("rename-bulk-suffix")?.value || "")
    );
  }

  function renameNameHasPathSeparator(name) {
    return /[\\/]/.test(String(name || ""));
  }

  function renameSetFinalOverride(row, finalName) {
    const key = renameSourceKey(row);
    if (!key) return false;
    const pipelineName = row?.pipeline_guess || row?.target_name || "";
    if (finalName && finalName !== pipelineName) renameFinalOverrides[key] = finalName;
    else delete renameFinalOverrides[key];
    return true;
  }

  function renderRenameBulkEditor(message = "") {
    const rows = renameBulkScopeRows();
    const stagedFinal = Object.keys(renameFinalOverrides).length;
    const stagedForce = Object.keys(renameForceOverrides).filter((key) => renameForceOverrides[key]).length;
    const stagedForceOff = Object.keys(renameForceOverrides).filter((key) => renameForceOverrides[key] === false).length;
    const status = rows.length ? `${rows.length} row(s)` : "No scope";
    const lines = [
      `Scope: ${renameBulkScopeLabel()}; applicable rows in scope: ${rows.length}`,
      `Staged overrides: ${stagedFinal} final-name override(s), ${stagedForce} force-through-pipeline row(s), ${stagedForceOff} force-off row(s)`,
      "Stage Bulk Edit uses the current backend preview final names, edits only the filename stem, preserves extensions, then rebuilds backend preview.",
      "Use Pipeline Names clears final-name overrides for the scope; Clear Scope Overrides clears both final-name and force overrides for the scope.",
      "Mutation guardrail: this panel stages preview overrides only. Apply still calls backend rename.apply with selected_sources.",
    ];
    if (message) lines.unshift(message);
    setText("rename-bulk-edit-status", status);
    setText("rename-bulk-edit-summary", lines.join("\n"));
  }

  function stageRenameBulkEdit() {
    const rows = renameBulkScopeRows();
    if (!rows.length) {
      renderRenameBulkEditor(`No applicable rows in ${renameBulkScopeLabel()}. Check rows, select one row, or change the bulk scope.`);
      return;
    }
    if (!renameBulkHasEditInput()) {
      renderRenameBulkEditor("Enter a Find value, Prefix, or Suffix before staging a bulk final-name edit.");
      return;
    }
    let staged = 0;
    let unchanged = 0;
    let skipped = 0;
    rows.forEach((row) => {
      const current = renameCurrentFinalName(row);
      const edited = renameBulkEditedName(current);
      if (!edited || renameNameHasPathSeparator(edited)) {
        skipped += 1;
        return;
      }
      if (edited === current) {
        unchanged += 1;
        return;
      }
      if (renameSetFinalOverride(row, edited)) staged += 1;
    });
    renderRenameBulkEditor(`Staged ${staged} bulk final-name edit(s); ${unchanged} unchanged; ${skipped} skipped because the generated name was empty or contained a path separator.`);
    refreshRenamePreview();
  }

  function usePipelineNamesForRenameScope() {
    const rows = renameBulkScopeRows();
    if (!rows.length) {
      renderRenameBulkEditor(`No applicable rows in ${renameBulkScopeLabel()} to reset to pipeline names.`);
      return;
    }
    rows.forEach((row) => delete renameFinalOverrides[renameSourceKey(row)]);
    renderRenameBulkEditor(`Cleared final-name overrides for ${rows.length} row(s). Backend preview will use pipeline names for this scope.`);
    refreshRenamePreview();
  }

  function setRenameBulkForce(forceValue) {
    const rows = renameBulkScopeRows();
    if (!rows.length) {
      renderRenameBulkEditor(`No applicable rows in ${renameBulkScopeLabel()} to update force-through-pipeline state.`);
      return;
    }
    rows.forEach((row) => {
      const key = renameSourceKey(row);
      if (!key) return;
      if (forceValue) renameForceOverrides[key] = true;
      else renameForceOverrides[key] = false;
    });
    renderRenameBulkEditor(`${forceValue ? "Enabled" : "Cleared"} force-through-pipeline override for ${rows.length} row(s).`);
    refreshRenamePreview();
  }

  function clearRenameBulkOverrides() {
    const rows = renameBulkScopeRows();
    if (!rows.length) {
      renderRenameBulkEditor(`No applicable rows in ${renameBulkScopeLabel()} to clear overrides.`);
      return;
    }
    rows.forEach((row) => {
      const key = renameSourceKey(row);
      delete renameFinalOverrides[key];
      delete renameForceOverrides[key];
    });
    renderRenameBulkEditor(`Cleared final-name and force overrides for ${rows.length} row(s).`);
    refreshRenamePreview();
  }

  const renameApplyReadinessSlice = window.mediaPipelineRenameApplyReadinessSlice.create({
    RENAME_PREVIEW_RENDER_LIMIT,
    appendCells,
    byId,
    collectRenameRequest,
    getCheckedRenameRows,
    getLastRenameRows: () => lastRenameRows,
    getRenameFinalOverrides: () => renameFinalOverrides,
    getRenameApplyScopeRows,
    getSelectedRenameRow,
    renameConfidenceExplanation,
    renameConfidenceLabel,
    renameDuplicateTargets,
    renameRenderedRowsCount,
    renameRowCanApply,
    renameSourceKey,
    renameStatusExplanation,
    setText,
  });
  const {
    renderRenameApplyReadiness,
    renderRenameDetail,
    renderRenameSelectionAudit,
    renameApplyReadinessRows,
    renameApplyReadinessStatus,
    renameApplyScopeBlockers,
    renameSelectionAuditStatus,
    renameSelectionDuplicateTargets,
  } = renameApplyReadinessSlice;

  function applyRenameSelectedOverride() {
    const row = getSelectedRenameRow();
    if (!row) {
      setText("rename-detail", "Select a rename row before previewing an override.");
      return;
    }
    const key = renameSourceKey(row);
    const finalValue = (byId("rename-selected-final")?.value || "").trim();
    const forceValue = Boolean(byId("rename-selected-force")?.checked);
    if (finalValue && finalValue !== row.pipeline_guess) renameFinalOverrides[key] = finalValue;
    else delete renameFinalOverrides[key];
    renameForceOverrides[key] = forceValue;
    refreshRenamePreview();
  }

  function clearRenameSelectedOverride() {
    const row = getSelectedRenameRow();
    if (!row) {
      setText("rename-detail", "Select a rename row before clearing an override.");
      return;
    }
    const key = renameSourceKey(row);
    delete renameFinalOverrides[key];
    delete renameForceOverrides[key];
    const finalInput = byId("rename-selected-final");
    const forceInput = byId("rename-selected-force");
    if (finalInput) finalInput.value = row.pipeline_guess || row.target_name || "";
    if (forceInput) forceInput.checked = Boolean(row.force_pipeline_name);
    refreshRenamePreview();
  }

  function replaceRenamePathText(appliedRows) {
    const input = byId("rename-paths");
    if (!input || !Array.isArray(appliedRows) || !appliedRows.length) return;
    const replacements = {};
    appliedRows.forEach((row) => {
      if (row.source && row.destination) {
        replacements[String(row.source).toLowerCase()] = String(row.destination);
      }
    });
    const lines = input.value.split(/\r?\n/).map((line) => {
      const trimmed = line.trim();
      const key = trimmed.toLowerCase();
      const replacement = replacements[key];
      if (replacement && renamePathOrigins[key]) {
        renamePathOrigins[String(replacement).toLowerCase()] = renamePathOrigins[key];
        delete renamePathOrigins[key];
      }
      return replacement || line;
    });
    input.value = lines.join("\n");
    renderRenameFileSourceSummary();
    renameMarkInputChanged();
  }

  const renameApplyResultSlice = window.mediaPipelineRenameApplyResultSlice.create({
    appendCells,
    byId,
    renderProgressBarsInto: function () {
      if (typeof window.renderProgressBarsInto === "function") {
        window.renderProgressBarsInto.apply(window, arguments);
      }
    },
    setText,
  });
  const {
    renderRenameApplyOutcomeReview,
    renderRenameApplyProgress,
    renderRenameApplyResult,
    renameApplyOutcomeRows,
    renameApplyOutcomeStatus,
    renameApplyOutcomeStatusState,
    renameApplyOutcomeSummaryLines,
    renameApplyProgressBars,
    renameApplyResultLines,
  } = renameApplyResultSlice;

  async function applySelectedRename() {
    if (renamePreviewInFlight) {
      const message = "Wait for the active rename preview to finish before applying a selected rename.";
      setText("rename-detail", message);
      appendCommandResult({
        command: "rename.apply",
        ok: false,
        severity: "warning",
        message,
      });
      return;
    }
    if (renameApplyInFlight) {
      const message = "Another rename apply command is already in progress.";
      setText("rename-detail", message);
      appendCommandResult({
        command: "rename.apply",
        ok: false,
        severity: "warning",
        message,
      });
      return;
    }
    if (updateRenamePreviewFreshnessState()) {
      const message = "Preview out of date. Run Preview again before applying.";
      setText("rename-detail", message);
      syncRenameCommandButtons();
      return;
    }
    const checkedRows = getCheckedRenameRows();
    const row = getSelectedRenameRow();
    const rowsToApply = checkedRows.length ? checkedRows : row ? [row] : [];
    if (!rowsToApply.length) {
      setText("rename-detail", "Select a rename row or check one or more rows before applying.");
      return;
    }
    const blocked = rowsToApply.filter((item) => !renameRowCanApply(item));
    if (blocked.length) {
      setText("rename-detail", `Rename selection has ${blocked.length} blocked row(s). Fix the preview before applying.`);
      return;
    }
    const readinessBlockers = renameApplyScopeBlockers(rowsToApply);
    if (readinessBlockers.length) {
      const message = `Rename selection is blocked by apply readiness: ${readinessBlockers.join("; ")}. Fix the preview before applying.`;
      setText("rename-detail", message);
      appendCommandResult({
        command: "rename.apply",
        ok: false,
        severity: "warning",
        message,
      });
      renderRenameApplyReadiness();
      return;
    }
    const confirmLines = rowsToApply.slice(0, 6).map((item) => `${item.source_name || item.source}\n-> ${item.target_name || item.destination || ""}`);
    if (rowsToApply.length > 6) confirmLines.push(`...and ${rowsToApply.length - 6} more row(s)`);
    const outsideRootRows = rowsToApply.filter((item) => item.path_authority === "outside_configured_roots");
    const outsideRootWarning = outsideRootRows.length
      ? `\n\nOutside configured roots: ${outsideRootRows.length} selected row(s). Review exact source/destination paths before confirming standalone rename.`
      : "";
    if (!window.confirm(`Apply rename for ${rowsToApply.length} selected row(s)?${outsideRootWarning}\n\n${confirmLines.join("\n\n")}`)) return;
    setRenameApplyBusy(true);
    try {
      const request = collectRenameRequest();
      request.selected_sources = rowsToApply.map((item) => item.source);
      request.confirm_apply = true;
      request.allow_outside_configured_roots = outsideRootRows.length > 0;
      const result = await apiPost("/api/rename/apply", request);
      const visibleResult = { ...result, request };
      appendCommandResult(visibleResult);
      renderRenameApplyResult(visibleResult);
      if (result.ok) {
        replaceRenamePathText((result.data || {}).rows || []);
        selectedRenameSourceKey = "";
        Object.keys(renameFinalOverrides).forEach((key) => {
          const applied = ((result.data || {}).rows || []).some((appliedRow) => String(appliedRow.source || "").toLowerCase() === key);
          if (applied) delete renameFinalOverrides[key];
        });
        Object.keys(renameForceOverrides).forEach((key) => {
          const applied = ((result.data || {}).rows || []).some((appliedRow) => String(appliedRow.source || "").toLowerCase() === key);
          if (applied) delete renameForceOverrides[key];
        });
        ((result.data || {}).rows || []).forEach((appliedRow) => checkedRenameSourceKeys.delete(String(appliedRow.source || "").toLowerCase()));
        await refreshRenamePreview();
      } else {
        setText("rename-detail", commandResultDisplayMessage(result) || "Rename apply failed.");
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setText("rename-detail", `Rename apply failed:\n${message}`);
      const result = {
        command: "rename.apply",
        ok: false,
        message,
        severity: "error",
      };
      appendCommandResult(result);
      renderRenameApplyResult(result);
    } finally {
      setRenameApplyBusy(false);
    }
  }

  function renderRenamePreview(preview, requestSignature = "") {
    const rows = Array.isArray(preview.rows) ? preview.rows : [];
    lastRenameRows = rows;
    lastRenamePreviewSignature = rows.length ? (requestSignature || renameCurrentRequestSignature()) : "";
    renamePreviewStale = false;
    lastRenameEmptyMessage = (preview.warnings || []).join(" | ") || "No rename rows available.";
    if (selectedRenameSourceKey && !rows.some((row) => renameSourceKey(row) === selectedRenameSourceKey)) {
      selectedRenameSourceKey = "";
    }
    Array.from(checkedRenameSourceKeys).forEach((key) => {
      if (!rows.some((row) => renameSourceKey(row) === key)) checkedRenameSourceKeys.delete(key);
    });
    const counts = preview.counts || {};
    const capText = renameRenderCapText(rows);
    setText("rename-status", `${counts.ready || 0} ready, ${counts.match || 0} match, ${counts.blocked || 0} blocked${capText ? `; ${capText}` : ""}`);
    setText("rename-preview-status", renamePreviewStatusText());
    const selectedRow = getSelectedRenameRow();
    if (selectedRow) syncRenameSelectedInputs(selectedRow);
    renderRenameSummary(preview);
    renderRenameDetail(selectedRow);
    renderRenameRows();
    renderRenameSelectionAudit();
    renderRenameApplyReadiness();
  }

  function renderRenameRows() {
    const tbody = byId("rename-rows");
    if (!lastRenameRows.length) {
      clearRows(tbody, 6, lastRenameEmptyMessage);
      updateRenameTableLegend(tbody);
      syncRenameCheckedCount();
      return;
    }
    tbody.replaceChildren();
    lastRenameRows.slice(0, RENAME_PREVIEW_RENDER_LIMIT).forEach((item) => {
      const row = document.createElement("tr");
      row.dataset.status = item.status || "";
      row.title = [
        `Status: ${item.status || "unknown"} - ${renameStatusExplanation(item.status)}`,
        `Confidence: ${renameConfidenceLabel(item) || "unknown"} - ${renameConfidenceExplanation(item.confidence)}`,
        `Preview source: ${renamePreviewSourceLabel(item.preview_source || "unknown")}`,
        `Change kind: ${item.change_kind || "unknown"}`,
      ].join("\n");
      const key = renameSourceKey(item);
      row.dataset.sourceKey = key;
      const checkCell = document.createElement("td");
      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.checked = checkedRenameSourceKeys.has(key);
      checkbox.disabled = !renameRowCanApply(item);
      const rowReason = renameImportantRowReason(item);
      checkbox.title = checkbox.disabled
        ? `Blocked rename rows cannot be checked for apply${rowReason ? `: ${rowReason}` : "."}`
        : "Check this row for backend selected_sources apply.";
      checkbox.addEventListener("click", (event) => event.stopPropagation());
      checkbox.addEventListener("change", () => setRenameRowChecked(item, checkbox.checked));
      checkCell.appendChild(checkbox);
      row.appendChild(checkCell);
      appendCells(row, [
        item.source_name || item.source || "",
        item.pipeline_guess || "",
        item.target_name || "",
        renameConfidenceLabel(item),
        renameRowStatusDisplay(item),
      ]);
      makeRowSelectable(row, () => selectRenameRow(item), {
        selected: Boolean(key && key === selectedRenameSourceKey),
        label: `Rename row ${item.source_name || item.source || ""}`,
      });
      tbody.appendChild(row);
    });
    updateRenameTableLegend(tbody);
    syncRenameCheckedCount();
  }

  function setRenamePreviewBusy(isBusy) {
    renamePreviewInFlight = Boolean(isBusy);
    syncRenameCommandButtons();
  }

  function setRenameApplyBusy(isBusy) {
    renameApplyInFlight = Boolean(isBusy);
    syncRenameCommandButtons();
  }

  function syncRenameCommandButtons() {
    const commandBusy = renamePreviewInFlight || renameBrowseInFlight || renameApplyInFlight;
    const stalePreview = updateRenamePreviewFreshnessState();
    const applyScope = getRenameApplyScopeRows();
    const rowsToApply = applyScope.rows;
    const readinessBlockers = stalePreview ? [] : renameApplyScopeBlockers(rowsToApply);
    const previewHasBlockedRows = lastRenameRows.some((row) => !renameRowCanApply(row));
    ["rename-preview-button", "rename-preview-top-button"].forEach((id) => {
      const button = byId(id);
      if (button) button.disabled = commandBusy;
    });
    const applyButton = byId("rename-apply-button");
    if (applyButton) {
      if (!lastRenameRows.length) {
        applyButton.textContent = "Preview before apply";
      } else if (stalePreview) {
        applyButton.textContent = "Preview out of date";
      } else if (readinessBlockers.length || (!rowsToApply.length && previewHasBlockedRows)) {
        applyButton.textContent = "Resolve blockers before apply";
      } else if (checkedRenameSourceKeys.size) {
        applyButton.textContent = `Apply ${rowsToApply.length} checked rename${rowsToApply.length === 1 ? "" : "s"}`;
      } else {
        applyButton.textContent = `Apply all ${rowsToApply.length} safe rename${rowsToApply.length === 1 ? "" : "s"}`;
      }
      applyButton.disabled = commandBusy || !lastRenameRows.length || stalePreview || !rowsToApply.length || readinessBlockers.length > 0;
    }
    const hint = byId("rename-apply-status-hint");
    if (hint) {
      if (stalePreview) {
        hint.textContent = "Preview out of date. Run Preview again before applying.";
      } else if (readinessBlockers.length) {
        hint.textContent = `Blocked by readiness: ${readinessBlockers.join("; ")}`;
      } else if (lastRenameRows.length && !rowsToApply.length && previewHasBlockedRows) {
        hint.textContent = "Resolve blocked preview rows before applying.";
      } else if (lastRenameRows.length && rowsToApply.length && !checkedRenameSourceKeys.size) {
        hint.textContent = "No rows checked; Apply uses all safe rows in the current preview.";
      } else if (lastRenameRows.length && checkedRenameSourceKeys.size) {
        hint.textContent = "Checked rows are the apply scope.";
      } else {
        hint.textContent = "";
      }
    }
    const selectedQueueButton = byId("rename-use-selected-queue-button");
    if (selectedQueueButton) selectedQueueButton.disabled = commandBusy;
    const loadedQueueButton = byId("rename-use-loaded-queue-button");
    if (loadedQueueButton) loadedQueueButton.disabled = commandBusy;
    const browseFilesButton = byId("rename-browse-files-button");
    if (browseFilesButton) browseFilesButton.disabled = commandBusy;
    const browseFolderButton = byId("rename-browse-folder-button");
    if (browseFolderButton) browseFolderButton.disabled = commandBusy;
    const addPathButton = byId("rename-add-path-button");
    if (addPathButton) addPathButton.disabled = commandBusy;
    const clearPathsButton = byId("rename-clear-paths-button");
    if (clearPathsButton) clearPathsButton.disabled = commandBusy || !renamePathLines().some((line) => line.trim());
    const checkButton = byId("rename-check-applicable-button");
    if (checkButton) checkButton.disabled = commandBusy || !lastRenameRows.length;
    const clearButton = byId("rename-clear-checks-button");
    if (clearButton) clearButton.disabled = renameBrowseInFlight || renameApplyInFlight || checkedRenameSourceKeys.size === 0;
    const moveUpButton = byId("rename-move-checked-up-button");
    if (moveUpButton) moveUpButton.disabled = commandBusy || !lastRenameRows.length;
    const moveDownButton = byId("rename-move-checked-down-button");
    if (moveDownButton) moveDownButton.disabled = commandBusy || !lastRenameRows.length;
    const sortButton = byId("rename-natural-sort-button");
    if (sortButton) sortButton.disabled = commandBusy || !renamePathLines().some((line) => line.trim());
    const bulkRows = renameBulkScopeRows();
    [
      "rename-bulk-stage-button",
      "rename-bulk-use-pipeline-button",
      "rename-bulk-force-button",
      "rename-bulk-clear-force-button",
      "rename-bulk-clear-button",
    ].forEach((id) => {
      const bulkButton = byId(id);
      if (bulkButton) bulkButton.disabled = commandBusy || !bulkRows.length;
    });
  }

  async function refreshRenamePreview() {
    const requestId = ++renamePreviewRequestId;
    activeRenamePreviewRequestId = requestId;
    setRenamePreviewBusy(true);
    try {
      const request = collectRenameRequest();
      if (!request.paths.length) {
        if (requestId === activeRenamePreviewRequestId) {
          lastRenameRows = [];
          selectedRenameSourceKey = "";
          checkedRenameSourceKeys.clear();
          lastRenamePreviewSignature = "";
          renamePreviewStale = false;
          lastRenameEmptyMessage = "No paths entered. Add one file path per line, then run Preview.";
          clearRows(byId("rename-rows"), 6, lastRenameEmptyMessage);
          setText("rename-status", "Idle");
          setText("rename-summary", lastRenameEmptyMessage);
          renderRenameFileSourceSummary(lastRenameEmptyMessage);
          renderRenameBatchSafety({ rows: [], counts: {} });
          renderRenamePipelineHandoff({ rows: [], counts: {} });
          renderRenameReviewBoard({ rows: [], counts: {} });
          renderRenameSelectionAudit();
          renderRenameApplyReadiness();
          renderRenameBulkEditor();
        }
        return;
      }
      renderRenameFileSourceSummary();
      setText("rename-status", "Previewing...");
      const preview = await apiPost("/api/rename/preview", request);
      if (requestId !== activeRenamePreviewRequestId) return;
      renderRenamePreview(preview, renameRequestSignatureFromRequest(request));
    } catch (error) {
      if (requestId !== activeRenamePreviewRequestId) return;
      const message = error instanceof Error ? error.message : String(error);
      lastRenameRows = [];
      selectedRenameSourceKey = "";
      checkedRenameSourceKeys.clear();
      lastRenamePreviewSignature = "";
      renamePreviewStale = false;
      lastRenameEmptyMessage = message;
      clearRows(byId("rename-rows"), 6, message);
      setText("rename-status", "Error");
      setText("rename-summary", `Rename preview failed.\n${message}`);
      renderRenameBatchSafety({ rows: [], counts: {}, warnings: [message] });
      renderRenamePipelineHandoff({ rows: [], counts: {}, warnings: [message] });
      renderRenameReviewBoard({ rows: [], counts: {}, warnings: [message] });
      renderRenameSelectionAudit();
      renderRenameApplyReadiness();
      renderRenameBulkEditor(message);
    } finally {
      if (requestId === activeRenamePreviewRequestId) {
        activeRenamePreviewRequestId = 0;
        setRenamePreviewBusy(false);
      }
    }
  }

  /**
   * Public namespace for the Rename page module.
   * Prefer this namespace from new code; flat window.* exports are transitional compatibility aliases when present.
   */
  window.mediaPipelineRenameView = {
    collectRenameRequest,
    collectRenameMovieFilterTerms,
    renameCleaningFilterConfigPatch,
    renderRenameCleaningFilterEditor,
    saveRenameCleaningFilterDraft,
    saveRenameCleaningFilterState,
    resetRenameCleaningFilters,
    initRenameCleaningFilterEditorEvents,
    refreshRenamePreview,
    renderRenamePreview,
    renderRenameRows,
    renderRenameSummary,
    renderRenameBatchSafety,
    renameBatchSafetyLines,
    renderRenamePipelineHandoff,
    renamePipelineHandoffLines,
    renamePipelineHandoffStatus,
    renameSavedSettingsConfig,
    renderRenameReviewBoard,
    renameReviewBoardLines,
    renameReviewBoardStatus,
    renamePreviewAggregateObject,
    renameFormatCounts,
    renameTemplateLabel,
    renderRenameBulkEditor,
    stageRenameBulkEdit,
    usePipelineNamesForRenameScope,
    setRenameBulkForce,
    clearRenameBulkOverrides,
    renameBulkScopeRows,
    renameBulkEditedName,
    renameCurrentFinalName,
    renderRenameSelectionAudit,
    renameSelectionAuditStatus,
    renameSelectionDuplicateTargets,
    renameApplyScopeBlockers,
    renderRenameApplyReadiness,
    renameApplyReadinessRows,
    renameApplyReadinessStatus,
    setRenamePreviewBusy,
    setRenameApplyBusy,
    syncRenameCommandButtons,
    renderRenameDetail,
    selectRenameRow,
    getSelectedRenameRow,
    getCheckedRenameRows,
    renameRowCanApply,
    setRenameRowChecked,
    checkApplicableRenameRows,
    clearCheckedRenameRows,
    moveCheckedRenamePaths,
    naturalSortRenamePaths,
    naturalCompareText,
    renderRenameFileSourceSummary,
    useSelectedQueueRowForRename,
    useLoadedQueueRowsForRename,
    appendRenamePaths,
    addRenamePathFromInput,
    browseRenamePaths,
    clearRenamePaths,
    syncRenameCheckedCount,
    applyRenameSelectedOverride,
    clearRenameSelectedOverride,
    applySelectedRename,
    replaceRenamePathText,
    renderRenameApplyResult,
    renameApplyResultLines,
    renderRenameApplyOutcomeReview,
    renderRenameApplyProgress,
    renameApplyProgressBars,
    renameApplyOutcomeRows,
    renameApplyOutcomeStatus,
    renameApplyOutcomeSummaryLines,
    renameApplyOutcomeStatusState,
    renameSourceKey,
    renameStatusExplanation,
    renamePreviewSourceLabel,
    renameConfidenceExplanation,
    renameConfidenceLabel,
    isRenameApplyCommand,
    renameApplyHistoryLine,
    renderRenameApplyHistory,
    applyRenameWorkbench,
    renameApplicablePreviewRows,
    renameOpenConfirmDialog,
    renameOpenResultDialog,
    renameSyncModeFieldVisibility,
    renameInitDropZone,
    renameInitWorkbenchEvents,
  };
  /* --------------------------------------------------------------------
   * Rename workbench: 3-step standalone tool
   *
   * Adds: confirm dialog, result dialog, TV-only field visibility,
   * drag-and-drop on the drop zone, Browse Folder uses folder_files mode,
   * Apply operates on every non-blocked preview row by default.
   *
   * Older queue-coupled buttons (rename-use-selected-queue-button,
   * rename-add-path-button, rename-paths textarea, etc.) are intentionally
   * absent from the current HTML; the existing handlers above remain for
   * historical compatibility and gracefully no-op when their DOM nodes
   * are missing.
   * -------------------------------------------------------------------- */

  function renameDialogById(id) {
    const el = byId(id);
    return el && typeof el.showModal === "function" ? el : null;
  }

  function renameOpenConfirmDialog(rowsToApply, outsideRootRows) {
    const dialog = renameDialogById("rename-confirm-dialog");
    if (!dialog) return Promise.resolve(false);
    const countEl = byId("rename-confirm-count");
    if (countEl) countEl.textContent = `Renaming ${rowsToApply.length} file(s).`;
    const listEl = byId("rename-confirm-list");
    if (listEl) {
      listEl.innerHTML = "";
      rowsToApply.forEach((item) => {
        const row = document.createElement("div");
        row.className = "rename-modal-list-row";
        row.setAttribute("role", "listitem");
        const oldName = String(item.source_name || item.source || "");
        const newName = String(item.target_name || item.destination || item.final_name || "");
        const oldSpan = document.createElement("span");
        oldSpan.className = "rename-modal-old";
        oldSpan.textContent = oldName;
        const arrow = document.createElement("span");
        arrow.className = "rename-modal-arrow";
        arrow.textContent = "->";
        const newSpan = document.createElement("span");
        newSpan.className = "rename-modal-new";
        newSpan.textContent = newName;
        row.append(oldSpan, arrow, newSpan);
        listEl.appendChild(row);
      });
    }
    const warningEl = byId("rename-confirm-warning");
    if (warningEl) {
      const warnings = [];
      if (!getCheckedRenameRows().length) {
        warnings.push("No rows were checked; this will apply all safe rows in the current preview.");
      }
      if (outsideRootRows && outsideRootRows.length) {
        warnings.push(`Warning: ${outsideRootRows.length} row(s) are outside configured media roots. Verify source/destination before continuing.`);
      }
      warningEl.textContent = warnings.join(" ");
      warningEl.hidden = !warnings.length;
    }
    return new Promise((resolve) => {
      const onClose = () => {
        dialog.removeEventListener("close", onClose);
        resolve(dialog.returnValue === "confirm");
      };
      dialog.addEventListener("close", onClose);
      const cancelBtn = byId("rename-confirm-cancel-button");
      if (cancelBtn) {
        cancelBtn.onclick = () => dialog.close("cancel");
      }
      try {
        dialog.showModal();
      } catch (_err) {
        dialog.removeEventListener("close", onClose);
        resolve(false);
      }
    });
  }

  function renameOpenResultDialog(result) {
    const dialog = renameDialogById("rename-result-dialog");
    if (!dialog) return;
    const payload = result && typeof result === "object" ? (result.raw && typeof result.raw === "object" ? result.raw : result) : {};
    const data = payload.data && typeof payload.data === "object" ? payload.data : {};
    const rows = Array.isArray(data.rows) ? data.rows : [];
    let success = Number.isFinite(data.success_count) ? Number(data.success_count) : 0;
    let failed = Number.isFinite(data.failed_count) ? Number(data.failed_count) : 0;
    let skipped = Number.isFinite(data.skipped_count) ? Number(data.skipped_count) : 0;
    if (!success && !failed && !skipped && rows.length) {
      rows.forEach((row) => {
        const status = String(row.status || row.outcome || "").toLowerCase();
        if (status === "success" || status === "renamed" || status === "applied" || row.renamed === true) success += 1;
        else if (status === "skipped" || status === "match" || row.skipped === true) skipped += 1;
        else if (status === "failed" || status === "error" || row.failed === true) failed += 1;
      });
    }
    if (!success && Number.isFinite(data.renamed)) success = Number(data.renamed);
    if (!success && Number.isFinite(data.applied_count) && !failed && !skipped) success = Number(data.applied_count);
    const setNum = (id, value) => {
      const el = byId(id);
      if (el) el.textContent = String(value);
    };
    setNum("rename-result-success", success);
    setNum("rename-result-failed", failed);
    setNum("rename-result-skipped", skipped);
    const summaryEl = byId("rename-result-summary");
    if (summaryEl) {
      const summary = String(payload.message || (payload.ok ? "Rename completed." : "Rename did not complete."));
      const undoManifest = String(data.undo_manifest || "").trim();
      summaryEl.textContent = undoManifest ? `${summary}\nUndo manifest: ${undoManifest}` : summary;
    }
    const errorsEl = byId("rename-result-errors");
    const errors = Array.isArray(payload.errors) ? payload.errors.filter((value) => String(value || "").trim()) : [];
    if (errorsEl) {
      errorsEl.innerHTML = "";
      if (errors.length || failed > 0) {
        errorsEl.hidden = false;
        const heading = document.createElement("strong");
        heading.textContent = "Errors";
        errorsEl.appendChild(heading);
        const list = document.createElement("ul");
        list.className = "rename-modal-error-list";
        const messages = errors.length
          ? errors
          : rows.filter((row) => String(row.status || row.outcome || "").toLowerCase() === "failed").map((row) => String(row.error || row.message || row.source || "Unknown error"));
        messages.forEach((msg) => {
          const li = document.createElement("li");
          li.textContent = String(msg);
          list.appendChild(li);
        });
        errorsEl.appendChild(list);
      } else {
        errorsEl.hidden = true;
      }
    }
    const openLogButton = byId("rename-result-open-log-button");
    if (openLogButton) {
      const logPath = String(data.log_path || data.log_folder || data.output_log || "");
      openLogButton.hidden = true;
      openLogButton.onclick = null;
      openLogButton.title = logPath
        ? `Log evidence reported by backend: ${logPath}. Open logs through the backend-owned Diagnostics targets.`
        : "";
    }
    try {
      dialog.showModal();
    } catch (_err) { /* swallow */ }
  }

  function renameApplicablePreviewRows() {
    return getRenameApplyScopeRows().rows;
  }

  async function applyRenameWorkbench() {
    if (renamePreviewInFlight || renameApplyInFlight) {
      return;
    }
    if (updateRenamePreviewFreshnessState()) {
      const message = "Preview out of date. Run Preview again before applying.";
      const hint = byId("rename-apply-status-hint");
      if (hint) hint.textContent = message;
      setText("rename-detail", message);
      syncRenameCommandButtons();
      return;
    }
    const rowsToApply = renameApplicablePreviewRows();
    if (!rowsToApply.length) {
      const message = "Preview has no applicable rows. Run Preview, then resolve any blocked rows.";
      const hint = byId("rename-apply-status-hint");
      if (hint) hint.textContent = message;
      setText("rename-detail", message);
      return;
    }
    const readinessBlockers = typeof renameApplyScopeBlockers === "function" ? renameApplyScopeBlockers(rowsToApply) : [];
    if (readinessBlockers.length) {
      const message = `Rename selection is blocked by apply readiness: ${readinessBlockers.join("; ")}. Fix the preview before applying.`;
      const hint = byId("rename-apply-status-hint");
      if (hint) hint.textContent = `Blocked by readiness: ${readinessBlockers.join("; ")}`;
      setText("rename-detail", message);
      return;
    }
    const outsideRootRows = rowsToApply.filter((row) => row.path_authority === "outside_configured_roots");
    const confirmed = await renameOpenConfirmDialog(rowsToApply, outsideRootRows);
    if (!confirmed) return;
    setRenameApplyBusy(true);
    let visibleResult = null;
    try {
      const request = collectRenameRequest();
      request.selected_sources = rowsToApply.map((row) => row.source);
      request.confirm_apply = true;
      request.allow_outside_configured_roots = outsideRootRows.length > 0;
      const result = await apiPost("/api/rename/apply", request);
      visibleResult = { ...result, request };
      appendCommandResult(visibleResult);
      renderRenameApplyResult(visibleResult);
      if (result.ok) {
        replaceRenamePathText((result.data || {}).rows || []);
        await refreshRenamePreview();
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      visibleResult = { ok: false, severity: "error", message, errors: [message] };
      appendCommandResult({ command: "rename.apply", ok: false, severity: "error", message });
    } finally {
      setRenameApplyBusy(false);
      if (visibleResult) renameOpenResultDialog(visibleResult);
    }
  }

  function renameSyncModeFieldVisibility() {
    const modeSelect = byId("rename-mode");
    const mode = String(modeSelect?.value || "tv").toLowerCase();
    const isTv = mode === "tv";
    document.querySelectorAll('[data-rename-mode-field="tv"]').forEach((node) => {
      node.style.display = isTv ? "" : "none";
    });
    const titleLabel = document.querySelector('label > input#rename-show')?.parentElement;
    if (titleLabel) {
      const firstTextNode = Array.from(titleLabel.childNodes).find((node) => node.nodeType === Node.TEXT_NODE && String(node.textContent || "").trim());
      if (firstTextNode) {
        firstTextNode.textContent = "Title / Show";
      }
    }
  }

  function renameInitDropZone() {
    const zone = byId("rename-drop-zone");
    if (!zone) return;
    const onDragOver = (event) => {
      event.preventDefault();
      event.stopPropagation();
      try { event.dataTransfer.dropEffect = "copy"; } catch (_err) { /* */ }
      zone.classList.add("is-dragging");
    };
    const onDragLeave = () => zone.classList.remove("is-dragging");
    const onDrop = (event) => {
      event.preventDefault();
      event.stopPropagation();
      zone.classList.remove("is-dragging");
      const files = Array.from(event.dataTransfer?.files || []);
      const collected = [];
      files.forEach((file) => {
        // Tauri / WebView2 may expose .path on the File object for OS files.
        const path = file && (file.path || file.fullPath || file.name);
        if (path) collected.push(String(path));
      });
      if (collected.length) {
        appendRenamePaths(collected, "Drag and drop", "drop");
      } else {
        renderRenameFileSourceSummary("Drop captured 0 paths. On browsers without OS file path access, use Browse Files / Add files from folder instead.");
      }
    };
    zone.addEventListener("dragenter", onDragOver);
    zone.addEventListener("dragover", onDragOver);
    zone.addEventListener("dragleave", onDragLeave);
    zone.addEventListener("drop", onDrop);
  }

  function renameInitWorkbenchEvents() {
    const applyButton = byId("rename-apply-button");
    if (applyButton) applyButton.addEventListener("click", () => applyRenameWorkbench());
    const previewButton = byId("rename-preview-button");
    if (previewButton) previewButton.addEventListener("click", () => refreshRenamePreview());
    const browseFilesButton = byId("rename-browse-files-button");
    if (browseFilesButton) browseFilesButton.addEventListener("click", () => browseRenamePaths("files"));
    const browseFolderButton = byId("rename-browse-folder-button");
    if (browseFolderButton) browseFolderButton.addEventListener("click", () => browseRenamePaths("folder_files"));
    const clearButton = byId("rename-clear-paths-button");
    if (clearButton) clearButton.addEventListener("click", () => clearRenamePaths());
    const modeSelect = byId("rename-mode");
    if (modeSelect) {
      modeSelect.addEventListener("change", () => {
        renameSyncModeFieldVisibility();
        refreshRenamePreview();
      });
    }
    [
      "rename-paths",
      "rename-template-preset",
      "rename-show",
      "rename-season",
      "rename-start",
      "rename-movie-year",
      "rename-sidecars",
      "rename-force-pipeline",
      "rename-pipeline-preview",
    ].forEach((id) => {
      const node = byId(id);
      if (!node) return;
      node.addEventListener("input", renameMarkInputChanged);
      node.addEventListener("change", renameMarkInputChanged);
    });
    renameSyncModeFieldVisibility();
    renameInitDropZone();
  }

  window.refreshRenamePreview = refreshRenamePreview;
  window.renderRenameBulkEditor = renderRenameBulkEditor;
  window.stageRenameBulkEdit = stageRenameBulkEdit;
  window.usePipelineNamesForRenameScope = usePipelineNamesForRenameScope;
  window.setRenameBulkForce = setRenameBulkForce;
  window.clearRenameBulkOverrides = clearRenameBulkOverrides;
  window.syncRenameCommandButtons = syncRenameCommandButtons;
  window.checkApplicableRenameRows = checkApplicableRenameRows;
  window.clearCheckedRenameRows = clearCheckedRenameRows;
  window.moveCheckedRenamePaths = moveCheckedRenamePaths;
  window.naturalSortRenamePaths = naturalSortRenamePaths;
  window.renderRenameFileSourceSummary = renderRenameFileSourceSummary;
  window.useSelectedQueueRowForRename = useSelectedQueueRowForRename;
  window.useLoadedQueueRowsForRename = useLoadedQueueRowsForRename;
  window.addRenamePathFromInput = addRenamePathFromInput;
  window.clearRenamePaths = clearRenamePaths;
  window.applyRenameSelectedOverride = applyRenameSelectedOverride;
  window.clearRenameSelectedOverride = clearRenameSelectedOverride;
  window.renameStatusExplanation = renameStatusExplanation;
  window.renamePreviewSourceLabel = renamePreviewSourceLabel;
  window.renameConfidenceExplanation = renameConfidenceExplanation;
  window.renameConfidenceLabel = renameConfidenceLabel;
  window.isRenameApplyCommand = isRenameApplyCommand;
  window.renameApplyHistoryLine = renameApplyHistoryLine;
  window.renderRenameApplyHistory = renderRenameApplyHistory;
})();
