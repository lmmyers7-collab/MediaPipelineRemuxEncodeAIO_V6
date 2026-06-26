(function () {
  const renameLabels = window.mediaPipelineRenameLabels || {};
  const renameStatusExplanation = renameLabels.renameStatusExplanation || function () { return "Unknown: refresh preview before applying."; };
  const renamePreviewSourceLabel = renameLabels.renamePreviewSourceLabel || function (value) { return value ? String(value) : "Not reported"; };
  const renameConfidenceExplanation = renameLabels.renameConfidenceExplanation || function () { return "Confidence not reported by backend."; };
  const renameConfidenceLabel = renameLabels.renameConfidenceLabel || function () { return ""; };
  const renameHistoryView = window.mediaPipelineRenameHistoryView || {};
  const isRenameApplyCommand = renameHistoryView.isRenameApplyCommand || function () { return false; };
  const renameApplyHistoryLine = renameHistoryView.renameApplyHistoryLine || function () { return ""; };
  const renderRenameApplyHistory = renameHistoryView.renderRenameApplyHistory || function () {};
  const RENAME_PREVIEW_RENDER_LIMIT = 250;
  const RENAME_CLEANING_FILTER_STORAGE_KEY = "mediapipeline.rename.cleaningFilters.v1";
  const RENAME_FILTER_CATALOG_ROUTE = "/api/rename/cleaning-filters";
  const RENAME_MOVIE_FILTER_CATALOG_ROUTE = "/api/rename/movie-cleaning-filters";
  const RENAME_CLEAN_FILENAME_PREVIEW_ROUTE = "/api/rename/clean-filename-preview";
  const RENAME_WEBVIEW_FILE_DROP_EVENT = "mediapipeline:file-drop";
  const RENAME_MEDIA_EXTENSIONS = new Set([".mkv", ".mp4", ".m4v", ".mov", ".avi", ".ts", ".m2ts", ".webm"]);
  const RENAME_SIDECAR_SUFFIXES = [".mediapipeline.rename.json", ".mediapipeline.json", ".pipeline.json"];
  const RENAME_CLEANING_IDS = {
    removeTerms: ["settings-rename-remove-terms", "rename-remove-terms"],
    tvRemoveTerms: ["settings-rename-tv-remove-terms", "rename-tv-remove-terms"],
    previewMode: ["settings-rename-preview-mode"],
    previewSourceFolder: ["settings-rename-preview-source-folder"],
    status: ["settings-rename-cleaning-filter-status", "rename-cleaning-filter-status"],
    summary: ["settings-rename-cleaning-filter-summary", "rename-cleaning-filter-summary"],
    saveButton: ["rename-cleaning-filters-save-button"],
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
  let renameUndoInFlight = false;
  let renameBadCaseInFlight = false;
  let lastRenameApplyHadResult = false;
  let lastRenameUndoManifest = "";
  let lastRenameUndoCompleted = false;
  let lastRenameApplyResultPayload = null;
  let renameCommandActivityTimer = 0;
  let renameCommandActivityState = null;
  let renameCleaningFilterEventsBound = false;
  let lastRenamePreviewSignature = "";
  let renamePreviewStale = false;
  let renameCleaningFilterSaveMessage = "";
  let renameCleaningFilterSaveMessageUntil = 0;
  let renameWorkbenchInFlight = false;
  let renameWorkbenchEventsBound = false;
  let lastRenameWorkbenchPayload = null;
  let renameWorkbenchHasStagedSuggestions = false;
  let renameWorkbenchSaveNewFiltersReady = false;
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
      setRenameStatusLine("rename-preview-status", "Preview out of date", "warning");
    } else if (wasStale && lastRenameRows.length) {
      setRenameStatusLine("rename-preview-status", renamePreviewStatusText(), "ready");
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

  function renameTvFilterTextareas() {
    return Array.from(document.querySelectorAll("[data-rename-tv-filter-terms], [data-tv-filter-terms]"));
  }

  function renameMovieFilterCheckboxes() {
    return Array.from(document.querySelectorAll("[data-rename-movie-filter], [data-movie-filter]"));
  }

  function renameTvFilterCheckboxes() {
    return Array.from(document.querySelectorAll("[data-rename-tv-filter], [data-tv-filter]"));
  }

  function collectRenameMovieFilterOptions() {
    const options = {};
    renameMovieFilterCheckboxes().forEach((input) => {
      const key = input.dataset.renameMovieFilter || input.dataset.movieFilter || "";
      if (key) options[key] = Boolean(input.checked);
    });
    return options;
  }

  function collectRenameTvFilterOptions() {
    const options = {};
    renameTvFilterCheckboxes().forEach((input) => {
      const key = input.dataset.renameTvFilter || input.dataset.tvFilter || "";
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

  function collectRenameTvFilterTermsText() {
    const terms = {};
    renameTvFilterTextareas().forEach((input) => {
      const key = input.dataset.renameTvFilterTerms || input.dataset.tvFilterTerms || "";
      if (key) terms[key] = input.value || "";
    });
    return terms;
  }

  function collectRenameTvFilterTerms() {
    const terms = {};
    Object.entries(collectRenameTvFilterTermsText()).forEach(([key, value]) => {
      terms[key] = parseRenameFilterTerms(value);
    });
    return terms;
  }

  function renameCleaningFilterState() {
    return {
      remove_terms_text: renameCleaningNode("removeTerms")?.value || "",
      movie_filter_options: collectRenameMovieFilterOptions(),
      movie_filter_terms_text: collectRenameMovieFilterTermsText(),
      tv_remove_terms_text: renameCleaningNode("tvRemoveTerms")?.value || "",
      tv_filter_options: collectRenameTvFilterOptions(),
      tv_filter_terms_text: collectRenameTvFilterTermsText(),
    };
  }

  function renameCleaningFilterConfigPatch() {
    return {
      RenameMovieFilterOptions: collectRenameMovieFilterOptions(),
      RenameMovieFilterTerms: collectRenameMovieFilterTerms(),
      RenameMovieRemoveTerms: parseRenameFilterTerms(renameCleaningNode("removeTerms")?.value || ""),
      RenameTVFilterOptions: collectRenameTvFilterOptions(),
      RenameTVFilterTerms: collectRenameTvFilterTerms(),
      RenameTVRemoveTerms: parseRenameFilterTerms(renameCleaningNode("tvRemoveTerms")?.value || ""),
    };
  }

  function renderRenameCleaningFilterEditor(message = "") {
    const movieTerms = collectRenameMovieFilterTerms();
    const categoryCounts = Object.entries(movieTerms)
      .map(([key, values]) => `${key.replace(/_/g, " ")}=${values.length}`)
      .join("; ");
    const tvTerms = collectRenameTvFilterTerms();
    const tvCategoryCounts = Object.entries(tvTerms)
      .map(([key, values]) => `${key.replace(/_/g, " ")}=${values.length}`)
      .join("; ");
    const customTermsCount = parseRenameFilterTerms(renameCleaningNode("removeTerms")?.value || "").length;
    const tvCustomTermsCount = parseRenameFilterTerms(renameCleaningNode("tvRemoveTerms")?.value || "").length;
    const statusNode = renameCleaningNode("status");
    if (statusNode) statusNode.textContent = "Backend terms active";
    const summaryNode = renameCleaningNode("summary");
    if (summaryNode) setText(summaryNode.id, [
      message,
      `Movie custom negative terms: ${customTermsCount}`,
      `TV custom negative terms: ${tvCustomTermsCount}`,
      `Movie filter terms: ${categoryCounts || "none"}`,
      `TV filter terms: ${tvCategoryCounts || "none"}`,
      "Save Settings writes RenameMovieFilterOptions, RenameMovieFilterTerms, RenameMovieRemoveTerms, RenameTVFilterOptions, RenameTVFilterTerms, and RenameTVRemoveTerms through the backend PSD1 save path.",
      "Saved filters affect future pipeline output naming, Rename preview planning, and Rename apply planning.",
      "Browser storage is local draft recovery only; it does not persist PSD1 settings.",
      "Next step: press Save Settings.",
      "Mutation guardrail: editing cleaning filters changes rename preview/apply planning only; filesystem changes still require backend rename apply confirmation.",
    ].filter(Boolean).join("\n"));
  }

  function saveRenameCleaningFilterDraft(message = "Cleaning filter draft retained in this browser.") {
    try {
      localStorage.setItem(RENAME_CLEANING_FILTER_STORAGE_KEY, JSON.stringify(renameCleaningFilterState()));
      renameCleaningFilterSaveMessage = message;
      renameCleaningFilterSaveMessageUntil = Date.now() + 1500;
      renderRenameCleaningFilterEditor(message);
      updateRenameFilterPreview();
      return true;
    } catch (_) {
      renderRenameCleaningFilterEditor("Cleaning filters could not be saved in browser storage.");
      return false;
    }
  }

  function stageRenameCleaningFilterPatch(changes) {
    const patchNode = byId("settings-patch-json");
    if (!patchNode) return false;
    let current = {};
    try {
      current = JSON.parse(patchNode.value || "{}");
    } catch (error) {
      renderRenameCleaningFilterEditor(`Cannot prepare rename filters for Save Settings: Settings Changes JSON is invalid. ${error?.message || error}`);
      return false;
    }
    if (!current || Array.isArray(current) || typeof current !== "object") {
      renderRenameCleaningFilterEditor("Cannot prepare rename filters for Save Settings: Settings Changes JSON must be an object.");
      return false;
    }
    const next = { ...current, ...changes };
    patchNode.value = JSON.stringify(next, null, 2);
    patchNode.dispatchEvent(new Event("input", { bubbles: true }));
    patchNode.dispatchEvent(new Event("change", { bubbles: true }));
    const settingsView = window.mediaPipelineSettingsView || {};
    if (typeof settingsView.markSettingsPatchTouched === "function") settingsView.markSettingsPatchTouched();
    if (typeof settingsView.renderSettingsPatchSummary === "function") settingsView.renderSettingsPatchSummary();
    if (typeof window.renderAllLaunchPreflights === "function") window.renderAllLaunchPreflights();
    return true;
  }

  async function saveRenameCleaningFilterState(message = "Rename cleaning filters prepared for Save Settings.") {
    const draftSaved = saveRenameCleaningFilterDraft("Rename filter draft retained in this browser while preparing Settings changes...");
    const changes = renameCleaningFilterConfigPatch();
    if (!stageRenameCleaningFilterPatch(changes)) {
      return false;
    }
    renameCleaningFilterSaveMessage = message;
    renameCleaningFilterSaveMessageUntil = Date.now() + 1500;
    renderRenameCleaningFilterEditor([
      message,
      draftSaved
        ? "Local draft retained until Settings Save succeeds and saved backend settings reload."
        : "Local browser draft storage failed; Settings changes remain the save source.",
      "Next step: press Save Settings.",
    ].join("\n"));
    if (typeof appendCommandResult === "function") {
      appendCommandResult({
        command: "settings.stage_rename_filters",
        ok: true,
        severity: "info",
        message: "Rename filter changes prepared for Save Settings; no backend save route was called.",
      });
    }
    updateRenameFilterPreview();
    syncRenameCommandButtons();
    return true;
  }

  function resetRenameCleaningFilters() {
    const removeTerms = renameCleaningNode("removeTerms");
    if (removeTerms) removeTerms.value = removeTerms.dataset.defaultTerms || "sample, trailer, extras, featurette, deleted scenes, behind the scenes";
    const tvRemoveTerms = renameCleaningNode("tvRemoveTerms");
    if (tvRemoveTerms) tvRemoveTerms.value = tvRemoveTerms.dataset.defaultTerms || "sample, trailer, extras, featurette, deleted scenes, behind the scenes";
    renameMovieFilterCheckboxes().forEach((input) => {
      input.checked = Boolean(input.defaultChecked);
    });
    renameTvFilterCheckboxes().forEach((input) => {
      input.checked = Boolean(input.defaultChecked);
    });
    renameCleaningFilterTextareas().forEach((input) => {
      input.value = input.dataset.defaultTerms || "";
    });
    renameTvFilterTextareas().forEach((input) => {
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
    const tvRemoveTerms = renameCleaningNode("tvRemoveTerms");
    if (tvRemoveTerms && typeof state.tv_remove_terms_text === "string") tvRemoveTerms.value = state.tv_remove_terms_text;
    const tvFilterOptions = state.tv_filter_options && typeof state.tv_filter_options === "object"
      ? state.tv_filter_options
      : {};
    renameTvFilterCheckboxes().forEach((input) => {
      const key = input.dataset.renameTvFilter || input.dataset.tvFilter || "";
      if (Object.prototype.hasOwnProperty.call(tvFilterOptions, key)) input.checked = Boolean(tvFilterOptions[key]);
    });
    const tvTextByKey = state.tv_filter_terms_text && typeof state.tv_filter_terms_text === "object"
      ? state.tv_filter_terms_text
      : {};
    renameTvFilterTextareas().forEach((input) => {
      const key = input.dataset.renameTvFilterTerms || input.dataset.tvFilterTerms || "";
      if (Object.prototype.hasOwnProperty.call(tvTextByKey, key)) input.value = String(tvTextByKey[key] || "");
    });
    renderRenameCleaningFilterEditor("Unsaved cleaning filter draft loaded from browser storage.");
    updateRenameFilterPreview();
    return true;
  }

  function applyRenameFilterCatalogSection(section, options = {}) {
    const textByKey = section?.saved_terms_text && typeof section.saved_terms_text === "object"
      ? section.saved_terms_text
      : section?.default_terms_text && typeof section.default_terms_text === "object"
        ? section.default_terms_text
        : {};
    const optionsByKey = section?.saved_options && typeof section.saved_options === "object"
      ? section.saved_options
      : {};
    const removeTermsText = typeof section?.saved_remove_terms_text === "string"
      ? section.saved_remove_terms_text
      : "";
    const removeTerms = options.mode === "tv" ? renameCleaningNode("tvRemoveTerms") : renameCleaningNode("removeTerms");
    const checkboxes = options.mode === "tv" ? renameTvFilterCheckboxes() : renameMovieFilterCheckboxes();
    const textareas = options.mode === "tv" ? renameTvFilterTextareas() : renameCleaningFilterTextareas();
    if (removeTerms && removeTermsText) {
      const previousDefault = removeTerms.dataset.defaultTerms || "";
      removeTerms.dataset.defaultTerms = removeTermsText;
      if (!options.preserveValues && (!removeTerms.value || removeTerms.value === previousDefault)) {
        removeTerms.value = removeTermsText;
      }
    }
    checkboxes.forEach((input) => {
      const key = input.dataset.renameMovieFilter || input.dataset.movieFilter || input.dataset.renameTvFilter || input.dataset.tvFilter || "";
      if (!key || !Object.prototype.hasOwnProperty.call(optionsByKey, key)) return;
      input.defaultChecked = Boolean(optionsByKey[key]);
      if (!options.preserveValues) input.checked = Boolean(optionsByKey[key]);
    });
    textareas.forEach((input) => {
      const key = input.dataset.renameMovieFilterTerms || input.dataset.movieFilterTerms || input.dataset.renameTvFilterTerms || input.dataset.tvFilterTerms || "";
      const backendText = String(textByKey[key] || "");
      if (!backendText) return;
      const previousDefault = input.dataset.defaultTerms || "";
      input.dataset.defaultTerms = backendText;
      if (!options.preserveValues && (!input.value || input.value === previousDefault)) {
        input.value = backendText;
      }
    });
  }

  async function loadRenameMovieFilterCatalog(options = {}) {
    const get = typeof apiGet === "function" ? apiGet : window.apiGet;
    if (typeof get !== "function") return;
    try {
      let payload = await get(RENAME_FILTER_CATALOG_ROUTE, { timeoutMs: 10000 });
      if (!payload?.movie) payload = { movie: payload };
      applyRenameFilterCatalogSection(payload.movie, { ...options, mode: "movie" });
      applyRenameFilterCatalogSection(payload.tv, { ...options, mode: "tv" });
      const activeSaveMessage = renameCleaningFilterSaveMessage
        && Date.now() < renameCleaningFilterSaveMessageUntil;
      renderRenameCleaningFilterEditor(
        (activeSaveMessage ? renameCleaningFilterSaveMessage : options.message)
          || options.message
          || (options.preserveValues
            ? "Saved backend movie and TV filter policy loaded; unsaved browser draft preserved."
            : "Saved backend movie and TV filter policy loaded.")
      );
      updateRenameFilterPreview();
    } catch (error) {
      try {
        const payload = await get(RENAME_MOVIE_FILTER_CATALOG_ROUTE, { timeoutMs: 10000 });
        applyRenameFilterCatalogSection(payload, { ...options, mode: "movie" });
        renderRenameCleaningFilterEditor(`Backend split filter catalog could not load; movie fallback terms loaded. ${error?.message || error}`);
      } catch (fallbackError) {
        renderRenameCleaningFilterEditor(`Backend rename filter catalog could not load; using packaged fallback terms. ${fallbackError?.message || fallbackError}`);
      }
    }
  }

  function renameCleanFilenamePreviewQuery(rawInput) {
    const previewMode = String(renameCleaningNode("previewMode")?.value || "movie").toLowerCase() === "tv" ? "tv" : "movie";
    const pairs = [
      ["filename", rawInput],
      ["mode", previewMode],
      ["source_folder", renameCleaningNode("previewSourceFolder")?.value || ""],
      ["remove_terms_text", renameCleaningNode("removeTerms")?.value || ""],
      ["movie_filter_options", JSON.stringify(collectRenameMovieFilterOptions())],
      ["movie_filter_terms", JSON.stringify(collectRenameMovieFilterTerms())],
      ["tv_remove_terms_text", renameCleaningNode("tvRemoveTerms")?.value || ""],
      ["tv_filter_options", JSON.stringify(collectRenameTvFilterOptions())],
      ["tv_filter_terms", JSON.stringify(collectRenameTvFilterTerms())],
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
    const policySource = payload?.rename_cleaning_policy_source || payload?.effective_policy_source || payload?.tv_filter_terms_mode || payload?.movie_filter_terms_mode;
    if (policySource) {
      if (String(payload?.mode || "movie").toLowerCase() === "tv") {
        lines.push(`TV filter policy: ${String(policySource).replace(/_/g, " ")}.`);
      } else {
        lines.push(`Movie filter policy: ${String(policySource).replace(/_/g, " ")}.`);
      }
    }
    (payload?.filter_evidence || []).forEach((item) => {
      if (!item || !item.label) return;
      lines.push(`${item.label}: ${String(item.value ?? "").replace(/\s+/g, " ").trim()}.`);
    });
    lines.push(String(payload?.mode || "movie").toLowerCase() === "tv"
      ? "Source: backend build_auto_tv_rename_name."
      : "Source: backend clean_pipeline_movie_name.");
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

  function renameWorkbenchInput(id) {
    return byId(`settings-rename-workbench-${id}`);
  }

  function renameWorkbenchValue(id) {
    return String(renameWorkbenchInput(id)?.value || "").trim();
  }

  function renameWorkbenchMode() {
    return String(renameWorkbenchInput("mode")?.value || "movie").toLowerCase() === "tv" ? "tv" : "movie";
  }

  function setRenameWorkbenchSaveState(message, state = "waiting") {
    const node = renameWorkbenchInput("save-state");
    if (!node) return;
    node.textContent = message;
    node.dataset.state = state;
  }

  function renameWorkbenchDestinationLabel(value) {
    const labels = {
      ignore: "Ignore",
      remove_terms: "Movie custom negative terms",
      tv_remove_terms: "TV custom negative terms",
      "movie_filter_terms.video_source": "Movie video / source",
      "movie_filter_terms.audio_channels": "Movie audio / channels",
      "movie_filter_terms.editions": "Movie editions / cuts",
      "movie_filter_terms.file_size": "Movie file size",
      "movie_filter_terms.services_containers": "Movie services / containers",
      "movie_filter_terms.languages_subs_dubs": "Movie languages / subs / dubs",
      "movie_filter_terms.release_groups": "Movie release groups",
      "tv_filter_terms.video_source": "TV video / source",
      "tv_filter_terms.audio_channels": "TV audio / channels",
      "tv_filter_terms.release_flags": "TV release flags",
      "tv_filter_terms.services_containers": "TV services / containers",
      "tv_filter_terms.languages_subs_dubs": "TV languages / subs / dubs",
      "tv_filter_terms.release_groups": "TV release groups",
    };
    return labels[value] || String(value || "").replace(/_/g, " ");
  }

  function syncRenameWorkbenchModeFields() {
    const mode = renameWorkbenchMode();
    document.querySelectorAll("[data-rename-workbench-mode-field]").forEach((node) => {
      const active = node.dataset.renameWorkbenchModeField === mode;
      node.hidden = false;
      node.classList.toggle("rename-workbench-inactive", !active);
      node.querySelectorAll("input, select, textarea").forEach((control) => {
        control.disabled = !active;
      });
    });
    document.querySelectorAll("[data-rename-workbench-required-modes]").forEach((node) => {
      const requiredModes = String(node.dataset.renameWorkbenchRequiredModes || "").split(/\s+/).filter(Boolean);
      const active = !node.classList.contains("rename-workbench-inactive");
      const required = active && requiredModes.includes(mode);
      node.classList.toggle("rename-workbench-required", required);
      node.querySelectorAll("input, select, textarea").forEach((control) => {
        control.required = required;
      });
    });
    renderRenameWorkbenchSuggestions([]);
    updateRenameWorkbenchSaveNewFiltersButton();
  }

  function updateRenameWorkbenchSaveNewFiltersButton() {
    const node = renameWorkbenchInput("save-filters-button");
    if (!node) return;
    node.disabled = renameWorkbenchInFlight || !renameWorkbenchSaveNewFiltersReady;
  }

  function setRenameWorkbenchBusy(isBusy) {
    renameWorkbenchInFlight = Boolean(isBusy);
    [
      "test-button",
      "save-case-button",
      "stage-suggestions-button",
      "retest-button",
    ].forEach((id) => {
      const node = renameWorkbenchInput(id);
      if (node) node.disabled = renameWorkbenchInFlight;
    });
    updateRenameWorkbenchSaveNewFiltersButton();
  }

  function markRenameWorkbenchNeedsTest() {
    if (!renameWorkbenchInput("form") || renameWorkbenchInFlight) return;
    lastRenameWorkbenchPayload = null;
    renameWorkbenchHasStagedSuggestions = false;
    renameWorkbenchSaveNewFiltersReady = false;
    renderRenameWorkbenchSuggestions([]);
    setText("settings-rename-workbench-status", "Needs test");
    setRenameWorkbenchSaveState("Run a test before Save Settings.", "waiting");
    updateRenameWorkbenchSaveNewFiltersButton();
  }

  function renameWorkbenchRequiredIssues() {
    const mode = renameWorkbenchMode();
    const issues = [];
    if (!renameWorkbenchValue("source-file")) issues.push("Source file/title is required.");
    if (mode === "tv") {
      if (!renameWorkbenchValue("source-folder")) issues.push("Source folder is required for TV.");
      if (!renameWorkbenchValue("expected-show")) issues.push("Expected show title is required.");
      if (!renameWorkbenchValue("expected-season")) issues.push("Expected season is required.");
      if (!renameWorkbenchValue("expected-episode")) issues.push("Expected episode is required.");
    } else {
      if (!renameWorkbenchValue("expected-movie-title")) issues.push("Expected movie title is required.");
      if (!renameWorkbenchValue("expected-year")) issues.push("Expected year is required.");
    }
    return issues;
  }

  function renameWorkbenchRequest() {
    const mode = renameWorkbenchMode();
    const expectedSeason = renameWorkbenchValue("expected-season");
    const request = {
      filename: renameWorkbenchValue("source-file"),
      mode,
      source_folder: renameWorkbenchValue("source-folder"),
      remove_terms_text: renameCleaningNode("removeTerms")?.value || "",
      movie_filter_options: JSON.stringify(collectRenameMovieFilterOptions()),
      movie_filter_terms: JSON.stringify(collectRenameMovieFilterTerms()),
      tv_remove_terms_text: renameCleaningNode("tvRemoveTerms")?.value || "",
      tv_filter_options: JSON.stringify(collectRenameTvFilterOptions()),
      tv_filter_terms: JSON.stringify(collectRenameTvFilterTerms()),
      include_case_analysis: "true",
    };
    if (mode === "tv") {
      request.template_preset = renameWorkbenchValue("template") || "tv_standard";
      request.season = expectedSeason ? `S${expectedSeason}` : "";
      request.expected_show = renameWorkbenchValue("expected-show");
      request.expected_season = expectedSeason;
      request.expected_episode = renameWorkbenchValue("expected-episode");
      request.expected_episode_title = renameWorkbenchValue("expected-episode-title");
    } else {
      request.template_preset = "movie_standard";
      request.expected_movie_title = renameWorkbenchValue("expected-movie-title");
      request.expected_year = renameWorkbenchValue("expected-year");
    }
    const notes = renameWorkbenchValue("notes");
    if (notes) request.notes = notes;
    return request;
  }

  function renameWorkbenchPreviewQuery() {
    const request = renameWorkbenchRequest();
    return `${RENAME_CLEAN_FILENAME_PREVIEW_ROUTE}?${Object.entries(request)
      .map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(value)}`)
      .join("&")}`;
  }

  function renderRenameWorkbenchPayload(payload) {
    const output = renameWorkbenchInput("output");
    if (!output) return;
    const actual = payload?.actual_fields || {};
    const expected = payload?.expected_fields || {};
    const comparison = payload?.comparison || {};
    const lines = [
      `Actual: ${actual.target_name || payload?.target_name || "(no backend result)"}`,
      `Expected: ${expected.expected_name || "(expected fields incomplete)"}`,
      `Result: ${comparison.ok ? "Pass" : "Needs review"}`,
    ];
    (comparison.fields || []).forEach((row) => {
      lines.push(`${row.ok ? "OK" : "Mismatch"} ${String(row.field || "").replace(/_/g, " ")}: ${row.actual ?? ""} / ${row.expected ?? ""}`);
    });
    (payload?.warnings || []).forEach((warning) => lines.push(`Warning: ${warning}`));
    (payload?.errors || []).forEach((error) => lines.push(`Error: ${error}`));
    lines.push(`Source: backend rename cleaner and ${comparison.policy_label || "current Settings filter draft"}.`);
    output.textContent = lines.join("\n");
    output.dataset.state = comparison.ok ? "match" : "changed";
  }

  function renderRenameWorkbenchSuggestionRows(tbody, rows, emptyText) {
    if (!tbody) return;
    tbody.replaceChildren();
    if (!rows.length) {
      const row = document.createElement("tr");
      const cell = document.createElement("td");
      cell.colSpan = 4;
      cell.textContent = emptyText;
      row.appendChild(cell);
      tbody.appendChild(row);
      return;
    }
    rows.forEach(({ item, index }) => {
      const row = document.createElement("tr");
      const alreadyFiltered = Boolean(item.already_filtered);
      const stageRecommended = Boolean(item.stage_recommended ?? (!alreadyFiltered && item.default_destination !== "ignore"));
      row.dataset.suggestionState = alreadyFiltered ? "existing" : "new";
      const checkCell = document.createElement("td");
      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.checked = stageRecommended;
      checkbox.disabled = alreadyFiltered;
      checkbox.title = alreadyFiltered ? "Already covered by current filters or cleaner result." : "Stage this new filter term.";
      checkbox.dataset.renameWorkbenchSuggestionIndex = String(index);
      checkCell.appendChild(checkbox);

      const termCell = document.createElement("td");
      termCell.textContent = item.term || "";

      const destinationCell = document.createElement("td");
      const select = document.createElement("select");
      (item.destinations || ["ignore"]).forEach((destination) => {
        const option = document.createElement("option");
        option.value = destination;
        option.textContent = renameWorkbenchDestinationLabel(destination);
        select.appendChild(option);
      });
      select.value = item.default_destination || "ignore";
      select.disabled = alreadyFiltered;
      destinationCell.appendChild(select);

      const reasonCell = document.createElement("td");
      const reason = item.reason || item.source || "";
      const coverageReason = item.coverage_reason || "";
      reasonCell.textContent = alreadyFiltered
        ? `Already covered: ${coverageReason || reason}`
        : [reason, coverageReason].filter(Boolean).join("; ");
      row.append(checkCell, termCell, destinationCell, reasonCell);
      tbody.appendChild(row);
    });
  }

  function renderRenameWorkbenchSuggestions(suggestions) {
    const rows = Array.isArray(suggestions) ? suggestions : [];
    const indexedRows = rows.map((item, index) => ({ item, index }));
    const newRows = indexedRows.filter(({ item }) => Boolean(
      item.stage_recommended ?? (!item.already_filtered && item.default_destination !== "ignore")
    ));
    renderRenameWorkbenchSuggestionRows(
      renameWorkbenchInput("suggestions"),
      newRows,
      rows.length ? "No new terms need staging for this result." : "Run a test to load new filter suggestions."
    );
  }

  async function runRenameWorkbenchPreview(options = {}) {
    const issues = renameWorkbenchRequiredIssues();
    if (issues.length) {
      setText("settings-rename-workbench-status", "Needs details");
      setText("settings-rename-workbench-message", issues.join(" "));
      setRenameWorkbenchSaveState("Complete required fields first.", "blocked");
      return null;
    }
    const get = typeof apiGet === "function" ? apiGet : window.apiGet;
    if (typeof get !== "function") {
      setText("settings-rename-workbench-status", "Unavailable");
      setText("settings-rename-workbench-message", "Backend filename preview is unavailable in this surface.");
      setRenameWorkbenchSaveState("Backend preview unavailable.", "blocked");
      return null;
    }
    setRenameWorkbenchBusy(true);
    setText("settings-rename-workbench-status", "Testing...");
    setRenameWorkbenchSaveState(
      options.stagedRetest ? "Retesting staged draft filters..." : "Testing current draft filters...",
      "testing"
    );
    if (!options.quiet) {
      setText(
        "settings-rename-workbench-message",
        options.stagedRetest
          ? "Retesting staged draft filters with backend cleaner..."
          : "Testing current draft filters with backend cleaner..."
      );
    }
    try {
      const payload = await get(renameWorkbenchPreviewQuery(), { timeoutMs: 10000 });
      lastRenameWorkbenchPayload = payload;
      if (payload?.comparison && options.stagedRetest) payload.comparison.policy_label = "current staged Settings filter draft";
      renderRenameWorkbenchPayload(payload);
      renderRenameWorkbenchSuggestions(payload?.filter_suggestions || []);
      setText("settings-rename-workbench-status", payload?.comparison?.ok ? "Pass" : "Needs review");
      if (options.stagedRetest && payload?.comparison?.ok) {
        if (renameWorkbenchHasStagedSuggestions) {
          const prepared = await saveRenameCleaningFilterState("Retest passed; rename filters are prepared for Save Settings.");
          renameWorkbenchSaveNewFiltersReady = Boolean(prepared);
          setText(
            "settings-rename-workbench-message",
            prepared
              ? "Retest passed. Save New Filters is ready."
              : "Retest passed, but the Settings save candidate could not be prepared."
          );
        } else if (!options.quiet) {
          setText("settings-rename-workbench-message", "Retest passed. No new staged suggestions needed.");
        }
        setRenameWorkbenchSaveState(renameWorkbenchSaveNewFiltersReady ? "Ready to save new filters." : "Ready for Save Settings.", "ready");
      } else if (options.stagedRetest && !payload?.comparison?.ok) {
        if (!options.quiet) setText("settings-rename-workbench-message", "Retest still needs review; staged terms remain draft-only.");
        renameWorkbenchSaveNewFiltersReady = false;
        setRenameWorkbenchSaveState("Not ready: review suggestions and retest.", "needs-review");
      } else {
        renameWorkbenchSaveNewFiltersReady = false;
        if (!options.quiet) setText("settings-rename-workbench-message", "Backend comparison complete.");
        setRenameWorkbenchSaveState(
          payload?.comparison?.ok
            ? "Current filters pass. Save Settings can persist draft filter changes."
            : "Not ready: stage new terms, then retest.",
          payload?.comparison?.ok ? "ready" : "needs-review"
        );
      }
      updateRenameWorkbenchSaveNewFiltersButton();
      return payload;
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setText("settings-rename-workbench-status", "Preview failed");
      setText("settings-rename-workbench-message", message);
      setRenameWorkbenchSaveState("Preview failed.", "blocked");
      return null;
    } finally {
      setRenameWorkbenchBusy(false);
    }
  }

  async function saveRenameWorkbenchCase() {
    const payload = await runRenameWorkbenchPreview({ quiet: true });
    const casePayload = { ...(payload?.case_payload || {}) };
    if (!casePayload.source_file || !casePayload.expected_name) {
      setText("settings-rename-workbench-status", "Needs details");
      setText("settings-rename-workbench-message", "Run a complete backend comparison before saving a regression case.");
      return;
    }
    casePayload.status = payload?.comparison?.ok ? "active" : "pending";
    casePayload.notes = renameWorkbenchValue("notes");
    casePayload.confirm_append = true;
    setRenameWorkbenchBusy(true);
    setText("settings-rename-workbench-status", "Saving case...");
    setText("settings-rename-workbench-message", "Appending regression case to backend corpus...");
    try {
      const result = await submitRenameBadCasePayload(casePayload);
      const message = result?.message || (result?.ok ? "Rename filter case appended." : "Rename filter case was not appended.");
      setText("settings-rename-workbench-status", result?.ok ? "Case saved" : "Save failed");
      setText("settings-rename-workbench-message", message);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setText("settings-rename-workbench-status", "Save failed");
      setText("settings-rename-workbench-message", message);
      appendCommandResult({ command: "rename.filter_case.append", ok: false, severity: "error", message });
    } finally {
      setRenameWorkbenchBusy(false);
    }
  }

  function appendRenameWorkbenchTerm(node, term) {
    if (!node || !term) return false;
    const terms = parseRenameFilterTerms(node.value || "");
    const key = String(term).trim().toLowerCase();
    if (!key || terms.some((item) => item.toLowerCase() === key)) return false;
    terms.push(String(term).trim());
    node.value = terms.join(", ");
    node.dispatchEvent(new Event("input", { bubbles: true }));
    return true;
  }

  function renameWorkbenchDestinationNode(destination) {
    if (destination === "remove_terms") return renameCleaningNode("removeTerms");
    if (destination === "tv_remove_terms") return renameCleaningNode("tvRemoveTerms");
    const movieMatch = /^movie_filter_terms\.(.+)$/.exec(destination);
    if (movieMatch) return document.querySelector(`[data-rename-movie-filter-terms="${movieMatch[1]}"]`);
    const tvMatch = /^tv_filter_terms\.(.+)$/.exec(destination);
    if (tvMatch) return document.querySelector(`[data-rename-tv-filter-terms="${tvMatch[1]}"]`);
    return null;
  }

  function enableRenameWorkbenchDestination(destination) {
    const movieMatch = /^movie_filter_terms\.(.+)$/.exec(destination);
    if (movieMatch) {
      const checkbox = document.querySelector(`[data-rename-movie-filter="${movieMatch[1]}"]`);
      if (checkbox) checkbox.checked = true;
    }
    const tvMatch = /^tv_filter_terms\.(.+)$/.exec(destination);
    if (tvMatch) {
      const checkbox = document.querySelector(`[data-rename-tv-filter="${tvMatch[1]}"]`);
      if (checkbox) checkbox.checked = true;
    }
  }

  function stageRenameWorkbenchSuggestions() {
    const suggestions = Array.isArray(lastRenameWorkbenchPayload?.filter_suggestions)
      ? lastRenameWorkbenchPayload.filter_suggestions
      : [];
    if (!suggestions.length) {
      setText("settings-rename-workbench-message", "Run a backend test before staging suggestions.");
      return;
    }
    let staged = 0;
    const tbody = renameWorkbenchInput("suggestions");
    Array.from(tbody?.querySelectorAll("tr") || []).forEach((row) => {
      const checkbox = row.querySelector('input[type="checkbox"]');
      const select = row.querySelector("select");
      const index = Number(checkbox?.dataset.renameWorkbenchSuggestionIndex || -1);
      const item = suggestions[index];
      const destination = String(select?.value || "ignore");
      if (!checkbox?.checked || !item || destination === "ignore") return;
      const node = renameWorkbenchDestinationNode(destination);
      if (appendRenameWorkbenchTerm(node, item.term)) {
        enableRenameWorkbenchDestination(destination);
        staged += 1;
      }
    });
    saveRenameCleaningFilterDraft(staged ? `Staged ${staged} rename filter suggestion(s) in the Settings draft.` : "No new rename filter suggestions were staged.");
    renderRenameCleaningFilterEditor(staged ? `Staged ${staged} suggestion(s). Use Save Settings to persist them.` : "Selected suggestions already exist in the draft.");
    renameWorkbenchHasStagedSuggestions = staged > 0;
    renameWorkbenchSaveNewFiltersReady = false;
    lastRenameWorkbenchPayload = null;
    setText("settings-rename-workbench-status", staged ? "Suggestions staged" : "No new terms");
    setText("settings-rename-workbench-message", staged ? "Suggestions are staged in the draft only. Retest with staged filters before Save Settings." : "Selected suggestions were already present or ignored.");
    setRenameWorkbenchSaveState(staged ? "Staged in draft; retest required." : "No new staged terms.", staged ? "staged" : "waiting");
    updateRenameWorkbenchSaveNewFiltersButton();
  }

  function saveRenameWorkbenchNewFilters() {
    if (!renameWorkbenchSaveNewFiltersReady) {
      setText("settings-rename-workbench-message", "Stage new suggestions and pass a staged retest before saving filters.");
      setRenameWorkbenchSaveState("Retest staged filters before saving.", "needs-review");
      updateRenameWorkbenchSaveNewFiltersButton();
      return;
    }
    const saveButton = byId("settings-save-header-save-button");
    if (!saveButton) {
      setText("settings-rename-workbench-message", "Save Settings is unavailable on this surface.");
      return;
    }
    setText("settings-rename-workbench-message", "Opening Save Settings review for the staged rename filters.");
    saveButton.click();
  }

  function initRenameWorkbenchEvents() {
    if (renameWorkbenchEventsBound) return;
    const form = renameWorkbenchInput("form");
    if (!form) return;
    renameWorkbenchEventsBound = true;
    form.addEventListener("submit", (event) => event.preventDefault());
    renameWorkbenchInput("mode")?.addEventListener("change", () => {
      lastRenameWorkbenchPayload = null;
      renameWorkbenchHasStagedSuggestions = false;
      renameWorkbenchSaveNewFiltersReady = false;
      syncRenameWorkbenchModeFields();
      setText("settings-rename-workbench-status", "Backend cleaner waits for input.");
      setText("settings-rename-workbench-message", "Waiting for case details.");
      setRenameWorkbenchSaveState("Run a test before Save Settings.", "waiting");
      updateRenameWorkbenchSaveNewFiltersButton();
    });
    form.querySelectorAll("input, select, textarea").forEach((node) => {
      node.addEventListener("input", () => {
        markRenameWorkbenchNeedsTest();
      });
      node.addEventListener("change", () => {
        markRenameWorkbenchNeedsTest();
      });
    });
    renameWorkbenchInput("test-button")?.addEventListener("click", () => runRenameWorkbenchPreview({ immediate: true }));
    renameWorkbenchInput("retest-button")?.addEventListener("click", () => runRenameWorkbenchPreview({ immediate: true, stagedRetest: true }));
    renameWorkbenchInput("save-filters-button")?.addEventListener("click", saveRenameWorkbenchNewFilters);
    renameWorkbenchInput("save-case-button")?.addEventListener("click", () => saveRenameWorkbenchCase());
    renameWorkbenchInput("stage-suggestions-button")?.addEventListener("click", stageRenameWorkbenchSuggestions);
    syncRenameWorkbenchModeFields();
  }

  function initRenameCleaningFilterEditorEvents() {
    const preserveValues = loadRenameCleaningFilterState();
    loadRenameMovieFilterCatalog({ preserveValues });
    if (renameCleaningFilterEventsBound) return;
    if (!renameCleaningNode("saveButton") && !renameCleaningNode("removeTerms") && !renameCleaningNode("tvRemoveTerms") && !renameCleaningFilterTextareas().length && !renameTvFilterTextareas().length) return;
    renameCleaningFilterEventsBound = true;
    const removeTerms = renameCleaningNode("removeTerms");
    if (removeTerms) removeTerms.addEventListener("input", () => {
      renderRenameCleaningFilterEditor();
      syncRenameCommandButtons();
      updateRenameFilterPreview();
      markRenameWorkbenchNeedsTest();
    });
    const tvRemoveTerms = renameCleaningNode("tvRemoveTerms");
    if (tvRemoveTerms) tvRemoveTerms.addEventListener("input", () => {
      renderRenameCleaningFilterEditor();
      syncRenameCommandButtons();
      updateRenameFilterPreview();
      markRenameWorkbenchNeedsTest();
    });
    renameCleaningFilterTextareas().forEach((input) => {
      input.addEventListener("input", () => {
        renderRenameCleaningFilterEditor();
        syncRenameCommandButtons();
        updateRenameFilterPreview();
        markRenameWorkbenchNeedsTest();
      });
    });
    renameTvFilterTextareas().forEach((input) => {
      input.addEventListener("input", () => {
        renderRenameCleaningFilterEditor();
        syncRenameCommandButtons();
        updateRenameFilterPreview();
        markRenameWorkbenchNeedsTest();
      });
    });
    const saveButton = renameCleaningNode("saveButton");
    if (saveButton) saveButton.addEventListener("click", () => saveRenameCleaningFilterState());
    const resetButton = renameCleaningNode("resetButton");
    if (resetButton) resetButton.addEventListener("click", resetRenameCleaningFilters);
    const previewInput = document.getElementById("settings-rename-preview-input");
    const onRenameFilterOptionChange = () => {
      updateRenameFilterPreview();
      markRenameWorkbenchNeedsTest();
    };
    renameMovieFilterCheckboxes()
      .forEach((cb) => cb.addEventListener("change", onRenameFilterOptionChange));
    renameTvFilterCheckboxes()
      .forEach((cb) => cb.addEventListener("change", onRenameFilterOptionChange));
    if (previewInput) {
      previewInput.addEventListener("input", updateRenameFilterPreview);
      document.getElementById("settings-rename-preview-button")
        ?.addEventListener("click", () => updateRenameFilterPreview({ immediate: true }));
      renameCleaningNode("previewMode")?.addEventListener("change", () => updateRenameFilterPreview({ immediate: true }));
      renameCleaningNode("previewSourceFolder")?.addEventListener("input", updateRenameFilterPreview);
    }
    initRenameWorkbenchEvents();
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

  function renameStatusState(value) {
    const normalized = String(value || "").toLowerCase();
    if (normalized.includes("block") || normalized.includes("duplicate") || normalized.includes("failed") || normalized.includes("error")) return "blocked";
    if (normalized.includes("review") || normalized.includes("warning") || normalized.includes("out of date") || normalized.includes("verify") || normalized.includes("mixed")) return "warning";
    if (normalized.includes("ready") || normalized.includes("applied") || normalized.includes("renamed")) return "ready";
    if (normalized.includes("match") || normalized.includes("no changes") || normalized.includes("recorded") || normalized.includes("checked")) return "changed";
    if (normalized.includes("idle") || normalized.includes("no ") || normalized.includes("waiting")) return "empty";
    return "unknown";
  }

  function setRenameStatusLine(id, value, state = "") {
    setText(id, value);
    const node = byId(id);
    if (node) node.dataset.state = state || renameStatusState(value);
  }

  function renameRowStatus(item) {
    return String(item?.status || "").trim().toLowerCase();
  }

  function renameRowHasWarnings(item) {
    return Array.isArray(item?.warnings) && item.warnings.length > 0;
  }

  function renameDuplicateTargetSet(rows = lastRenameRows) {
    const duplicates = typeof renameDuplicateTargets === "function" ? renameDuplicateTargets(rows) : [];
    return new Set(duplicates.map((value) => String(value || "").trim().toLowerCase()).filter(Boolean));
  }

  function renameTargetKey(item) {
    return String(item?.destination || item?.target_name || "").trim().toLowerCase();
  }

  function renameAutoCheckSkipReason(item, duplicateTargets = renameDuplicateTargetSet()) {
    if (!renameRowCanApply(item)) return "blocked";
    if (renameRowHasWarnings(item) || renameRowStatus(item) === "warning") return "warning";
    if (duplicateTargets.has(renameTargetKey(item))) return "duplicate";
    if (Boolean(item?.destination_exists) && !item?.matches_target) return "existing destination";
    return "";
  }

  function updateRenameTableLegend(tbody) {
    updateTableStatusLegend("rename-table-legend", tbody, "Rename rows");
    const capText = renameRenderCapText();
    if (!capText) return;
    const checkedRows = getCheckedRenameRows();
    const hiddenChecked = checkedRows.filter((row) => lastRenameRows.indexOf(row) >= RENAME_PREVIEW_RENDER_LIMIT).length;
    const current = byId("rename-table-legend")?.textContent || "";
    setText("rename-table-legend", `${current} Display cap: ${capText} rendered. ${hiddenChecked ? `${hiddenChecked} checked row(s) are outside the visible table; confirmation must be reviewed before mutation.` : "Check Applicable may include backend preview rows that are not visible in the table."}`);
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
    return { rows: [], source: "none; check intended rows before apply" };
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

  function setRenameRowCheckedFromCheckbox(item, checkbox) {
    if (!checkbox || checkbox.disabled) return;
    setRenameRowChecked(item, checkbox.checked);
  }

  function checkApplicableRenameRows() {
    checkedRenameSourceKeys.clear();
    const duplicateTargets = renameDuplicateTargetSet(lastRenameRows);
    const skipped = {};
    lastRenameRows.forEach((row) => {
      const reason = renameAutoCheckSkipReason(row, duplicateTargets);
      if (!reason) {
        checkedRenameSourceKeys.add(renameSourceKey(row));
      } else {
        skipped[reason] = (skipped[reason] || 0) + 1;
      }
    });
    renderRenameRows();
    renderRenameSelectionAudit();
    renderRenameApplyReadiness();
    const checkedCount = checkedRenameSourceKeys.size;
    const skippedText = Object.keys(skipped).sort().map((key) => `${key}=${skipped[key]}`).join(", ");
    const message = `Checked ${checkedCount} ready/match row${checkedCount === 1 ? "" : "s"}; skipped ${lastRenameRows.length - checkedCount}${skippedText ? ` (${skippedText})` : ""}.`;
    setRenameStatusLine("rename-selection-audit-status", checkedCount ? "Checked ready rows" : "No ready rows checked", checkedCount ? "ready" : "blocked");
    setText("rename-apply-status-hint", message);
    setText("rename-detail", `${message} Warning rows remain manually checkable after review; duplicate, blocked, and existing-destination rows stay out of apply scope.`);
  }

  function checkAllRenameRows() {
    checkedRenameSourceKeys.clear();
    const duplicateTargets = renameDuplicateTargetSet(lastRenameRows);
    const skipped = {};
    lastRenameRows.forEach((row) => {
      let reason = "";
      if (!renameRowCanApply(row)) reason = "blocked";
      else if (duplicateTargets.has(renameTargetKey(row))) reason = "duplicate";
      else if (Boolean(row?.destination_exists) && !row?.matches_target) reason = "existing destination";
      if (!reason) {
        checkedRenameSourceKeys.add(renameSourceKey(row));
      } else {
        skipped[reason] = (skipped[reason] || 0) + 1;
      }
    });
    renderRenameRows();
    renderRenameSelectionAudit();
    renderRenameApplyReadiness();
    const checkedCount = checkedRenameSourceKeys.size;
    const skippedText = Object.keys(skipped).sort().map((key) => `${key}=${skipped[key]}`).join(", ");
    const message = `Checked ${checkedCount} selectable row${checkedCount === 1 ? "" : "s"}; skipped ${lastRenameRows.length - checkedCount}${skippedText ? ` (${skippedText})` : ""}.`;
    setRenameStatusLine("rename-selection-audit-status", checkedCount ? "Checked selectable rows" : "No selectable rows checked", checkedCount ? "ready" : "blocked");
    setText("rename-apply-status-hint", message);
    setText("rename-detail", `${message} Review warnings before apply; duplicate, blocked, and existing-destination rows stay out of apply scope.`);
  }

  function clearCheckedRenameRows() {
    checkedRenameSourceKeys.clear();
    renderRenameRows();
    renderRenameSelectionAudit();
    renderRenameApplyReadiness();
    setRenameStatusLine("rename-selection-audit-status", "No selection", "empty");
    setText("rename-apply-status-hint", "Cleared checked rows. Check intended rows before applying.");
    setText("rename-detail", "Cleared checked rows. No rename apply scope is staged.");
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

  function renamePathSegments(value) {
    return String(value || "").trim().split(/[\\/]+/).filter(Boolean);
  }

  function renameFileLeafFromPath(value) {
    const parts = renamePathSegments(value);
    return parts.length ? parts[parts.length - 1] : "";
  }

  function renameParentFolderLeafFromPath(value) {
    const parts = renamePathSegments(value);
    return parts.length > 1 ? parts[parts.length - 2] : "";
  }

  function renameFolderLeafFromValue(value) {
    const parts = renamePathSegments(value);
    return parts.length ? parts[parts.length - 1] : "";
  }

  function renameExpectedShowFromName(name) {
    const match = String(name || "").match(/^(.+?)\s+-\s+S\d{2}E\d{2,3}\b/i);
    return match ? match[1].trim() : "";
  }

  function renameExpectedSeasonFromName(name) {
    const match = String(name || "").match(/\bS(\d{2})E\d{2,3}\b/i);
    return match ? Number.parseInt(match[1], 10) : null;
  }

  function renameSeasonNumberFromWorkbench() {
    const value = String(byId("rename-season")?.value || "").trim();
    const match = value.match(/\d+/);
    const parsed = match ? Number.parseInt(match[0], 10) : 1;
    return Number.isFinite(parsed) && parsed > 0 ? parsed : 1;
  }

  function compactRenameNote(value) {
    return String(value || "").replace(/\s+/g, " ").trim();
  }

  function renameBadCasePayloadFromRow(row, overrides = {}) {
    const sourcePath = renameSourcePathFromRow(row);
    const sourceFolder = renameFolderLeafFromValue(row?.source_folder || row?.parent_folder || row?.folder || "")
      || renameParentFolderLeafFromPath(sourcePath);
    const sourceFile = renameFileLeafFromPath(sourcePath)
      || renameFileLeafFromPath(row?.source_name || row?.name || row?.file || "");
    const expectedName = String(overrides.expected_name ?? renameCurrentFinalName(row) ?? "").trim();
    const expectedShow = String(overrides.expected_show ?? renameExpectedShowFromName(expectedName) ?? "").trim();
    const expectedSeason = overrides.expected_season ?? renameExpectedSeasonFromName(expectedName);
    const payload = {
      source_folder: String(overrides.source_folder ?? sourceFolder ?? "").trim(),
      source_file: String(overrides.source_file ?? sourceFile ?? "").trim(),
      expected_name: expectedName,
      expected_show: expectedShow,
      season_number: Number.isFinite(Number(overrides.season_number))
        ? Number(overrides.season_number)
        : renameSeasonNumberFromWorkbench(),
      status: String(overrides.status || "pending").trim().toLowerCase(),
      notes: compactRenameNote(overrides.notes || ""),
      confirm_append: true,
    };
    if (expectedShow) payload.expected_clean_folder = expectedShow;
    if (expectedSeason !== null && expectedSeason !== undefined && String(expectedSeason).trim() !== "") {
      const parsedSeason = Number.parseInt(String(expectedSeason), 10);
      if (Number.isFinite(parsedSeason)) payload.expected_season = parsedSeason;
    }
    if (!payload.notes) delete payload.notes;
    return payload;
  }

  async function submitRenameBadCasePayload(payload) {
    const request = { ...(payload || {}), confirm_append: true };
    const result = await apiPost("/api/rename/filter-cases", request);
    appendCommandResult({ ...result, request });
    return result;
  }

  function setRenameBadCaseBusy(isBusy) {
    renameBadCaseInFlight = Boolean(isBusy);
    const submitButton = byId("rename-log-case-submit-button");
    if (submitButton) {
      submitButton.disabled = renameBadCaseInFlight;
      submitButton.textContent = renameBadCaseInFlight ? "Appending..." : "Append Case";
    }
    syncRenameCommandButtons();
  }

  function renameLogCaseInput(id) {
    return byId(`rename-log-case-${id}`);
  }

  function setRenameLogCaseInputValue(id, value) {
    const node = renameLogCaseInput(id);
    if (node) node.value = value === null || value === undefined ? "" : String(value);
  }

  function renameBadCaseDialogOverrides() {
    const expectedSeason = renameLogCaseInput("expected-season")?.value || "";
    return {
      source_folder: renameLogCaseInput("source-folder")?.value || "",
      source_file: renameLogCaseInput("source-file")?.value || "",
      expected_name: renameLogCaseInput("expected-name")?.value || "",
      expected_show: renameLogCaseInput("expected-show")?.value || "",
      expected_season: expectedSeason,
      status: byId("rename-log-case-status-select")?.value || "pending",
      notes: renameLogCaseInput("notes")?.value || "",
    };
  }

  function syncRenameBadCaseButton() {
    const button = byId("rename-log-bad-case-button");
    const row = getSelectedRenameRow();
    const commandBusy = renamePreviewInFlight || renameBrowseInFlight || renameApplyInFlight || renameBadCaseInFlight;
    if (button) button.disabled = commandBusy || !row;
    const status = byId("rename-log-bad-case-status");
    if (status && !renameBadCaseInFlight) {
      status.textContent = row ? "Selected row can be logged to the filter corpus." : "Select a preview row to log a case.";
    }
  }

  function openRenameBadCaseDialog() {
    const row = getSelectedRenameRow();
    if (!row) {
      setText("rename-log-bad-case-status", "Select a preview row before logging a case.");
      syncRenameBadCaseButton();
      return;
    }
    const payload = renameBadCasePayloadFromRow(row);
    setRenameLogCaseInputValue("source-folder", payload.source_folder);
    setRenameLogCaseInputValue("source-file", payload.source_file);
    setRenameLogCaseInputValue("expected-name", payload.expected_name);
    setRenameLogCaseInputValue("expected-show", payload.expected_show);
    setRenameLogCaseInputValue("expected-season", payload.expected_season ?? "");
    const statusSelect = byId("rename-log-case-status-select");
    if (statusSelect) statusSelect.value = payload.status || "pending";
    setRenameLogCaseInputValue("notes", payload.notes || "");
    setText("rename-log-case-message", "");
    const dialog = renameDialogById("rename-log-case-dialog");
    if (!dialog) return;
    try {
      dialog.showModal();
    } catch (_err) { /* swallow */ }
  }

  async function submitRenameBadCaseDialog() {
    const row = getSelectedRenameRow();
    if (!row || renameBadCaseInFlight) return;
    const payload = renameBadCasePayloadFromRow(row, renameBadCaseDialogOverrides());
    if (!payload.source_folder || !payload.source_file || !payload.expected_name) {
      setText("rename-log-case-message", "Source folder, source file, and expected name are required.");
      return;
    }
    setRenameBadCaseBusy(true);
    setText("rename-log-case-message", "Appending case...");
    setText("rename-log-bad-case-status", "Appending case...");
    try {
      const result = await submitRenameBadCasePayload(payload);
      const message = result?.message || (result?.ok ? "Rename filter case appended." : "Rename filter case was not appended.");
      if (result?.ok) {
        const visibleMessage = `${message} Backend corpus entry recorded; no filesystem rename was requested.`;
        setText("rename-log-bad-case-status", visibleMessage);
        setText("rename-log-case-message", visibleMessage);
      } else {
        setText("rename-log-case-message", message);
        setText("rename-log-bad-case-status", message);
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setText("rename-log-case-message", message);
      setText("rename-log-bad-case-status", message);
      appendCommandResult({ command: "rename.filter_case.append", ok: false, severity: "error", message });
    } finally {
      setRenameBadCaseBusy(false);
    }
  }

  function renameCurrentPathValues() {
    return renamePathLines().map((line) => line.trim()).filter(Boolean);
  }

  function renamePathLeaf(value) {
    const parts = String(value || "").trim().split(/[\\/]+/).filter(Boolean);
    return parts.length ? parts[parts.length - 1] : "";
  }

  function renamePathExtension(value) {
    const leaf = renamePathLeaf(value);
    const index = leaf.lastIndexOf(".");
    return index >= 0 ? leaf.slice(index).toLowerCase() : "";
  }

  function renameIsSidecarPath(value) {
    const leaf = renamePathLeaf(value).toLowerCase();
    return RENAME_SIDECAR_SUFFIXES.some((suffix) => leaf.endsWith(suffix));
  }

  function classifyRenamePathValues(paths = renameCurrentPathValues()) {
    const seenMedia = new Set();
    const media = [];
    const sidecars = [];
    const nonMedia = [];
    const duplicates = [];
    paths.forEach((path) => {
      const text = String(path || "").trim();
      if (!text) return;
      if (RENAME_MEDIA_EXTENSIONS.has(renamePathExtension(text))) {
        const key = text.toLowerCase();
        if (seenMedia.has(key)) {
          duplicates.push(text);
          return;
        }
        seenMedia.add(key);
        media.push(text);
      } else if (renameIsSidecarPath(text)) {
        sidecars.push(text);
      } else {
        nonMedia.push(text);
      }
    });
    return {
      raw: paths.length,
      media,
      sidecars,
      nonMedia,
      duplicates,
      ignored: sidecars.length + nonMedia.length + duplicates.length,
    };
  }

  function renameLooksLikeAbsolutePath(value) {
    const text = String(value || "").trim();
    return Boolean(
      /^[a-zA-Z]:[\\/]/.test(text)
      || /^\\\\[^\\]+\\[^\\]+/.test(text)
      || /^\/[^/]/.test(text)
    );
  }

  function normalizeRenameDroppedPathValues(values) {
    const seen = new Set();
    const paths = [];
    (Array.isArray(values) ? values : []).forEach((value) => {
      const text = String(value || "").trim();
      const key = text.toLowerCase();
      if (!text || !renameLooksLikeAbsolutePath(text) || seen.has(key)) return;
      seen.add(key);
      paths.push(text);
    });
    return paths;
  }

  function renameDroppedPathFromFile(file) {
    if (!file || typeof file !== "object") return "";
    const candidates = [file.path, file.fullPath, file.webkitRelativePath];
    for (const candidate of candidates) {
      const text = String(candidate || "").trim();
      if (renameLooksLikeAbsolutePath(text)) return text;
    }
    return "";
  }

  function renameDroppedPathValuesFromDataTransfer(dataTransfer) {
    return normalizeRenameDroppedPathValues(
      Array.from(dataTransfer?.files || []).map(renameDroppedPathFromFile)
    );
  }

  function renameDroppedPathValuesFromBridgeDetail(detail) {
    if (!detail || typeof detail !== "object") return [];
    return normalizeRenameDroppedPathValues(Array.isArray(detail.paths) ? detail.paths : []);
  }

  async function handleRenameDroppedPaths(paths, sourceLabel = "Drag and drop") {
    const normalized = normalizeRenameDroppedPathValues(paths);
    if (!normalized.length) {
      renderRenameFileSourceSummary("Drop did not expose full filesystem paths. Use Browse Files / Add files from folder, or paste the full path manually.");
      return 0;
    }
    if (renameBrowseInFlight || renamePreviewInFlight || renameApplyInFlight) {
      renderRenameFileSourceSummary("Rename path browser is busy. Wait for the current Rename command to finish.");
      return 0;
    }
    renameBrowseInFlight = true;
    syncRenameCommandButtons();
    renderRenameFileSourceSummary(`${sourceLabel || "Drag and drop"} resolving dropped files/folders...`);
    try {
      const result = await apiPost("/api/rename/browse", {
        selection_mode: "folder_files",
        paths: normalized,
        source: "drop",
      });
      appendCommandResult(result);
      const data = result?.data && typeof result.data === "object" ? result.data : {};
      const resolved = Array.isArray(data.paths) ? data.paths : [];
      if (!result?.ok) {
        renderRenameFileSourceSummary(result?.message || "Dropped path resolution failed.");
        return 0;
      }
      if (!resolved.length) {
        const suffix = renameIgnoredPathSuffix(data);
        renderRenameFileSourceSummary(`${sourceLabel || "Drag and drop"} found no media files to stage.${suffix ? ` ${suffix}` : ""}`);
        return 0;
      }
      return appendResolvedRenameBrowsePaths(data, sourceLabel, "drop");
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      appendCommandResult({
        command: "rename.browse",
        ok: false,
        severity: "error",
        message: `Dropped path resolution failed:\n${message}`,
      });
      const classified = classifyRenamePathValues(normalized);
      if (classified.media.length) {
        return appendRenamePaths(classified.media, sourceLabel, "drop", "Backend dropped-folder expansion failed; staged dropped media files only.");
      }
      renderRenameFileSourceSummary(`Dropped path resolution failed:\n${message}`);
      return 0;
    } finally {
      renameBrowseInFlight = false;
      syncRenameCommandButtons();
    }
  }

  function renameDropZoneIsVisible(zone) {
    const page = zone?.closest?.('[data-page-panel="rename"]');
    return !page || page.classList?.contains("is-visible");
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
    const classified = classifyRenamePathValues(paths);
    pruneRenamePathOrigins(paths);
    const queueRows = typeof window.getLastQueueRows === "function"
      ? window.getLastQueueRows()
      : (window.mediaPipelineQueueView?.getLastQueueRows?.() || []);
    const selectedQueue = typeof window.getSelectedQueueRow === "function"
      ? window.getSelectedQueueRow()
      : (window.mediaPipelineQueueView?.getSelectedQueueRow?.() || null);
    const selectedPath = renameSourcePathFromRow(selectedQueue);
    const mediaCount = classified.media.length;
    setRenameStatusLine(
      "rename-file-source-status",
      paths.length ? `${mediaCount} media / ${paths.length} path${paths.length === 1 ? "" : "s"}` : "No paths",
      mediaCount ? "ready" : paths.length ? "warning" : "empty"
    );
    setText("rename-file-source-summary", [
      message,
      paths.length ? `Source paths staged: ${paths.length}` : "No source paths staged.",
      paths.length ? `Media paths eligible for preview/apply: ${mediaCount}` : "",
      classified.ignored
        ? `Ignored by preview/apply: ${classified.ignored} (${classified.sidecars.length} sidecar, ${classified.nonMedia.length} non-media, ${classified.duplicates.length} duplicate media)`
        : "",
      paths.length ? renamePathOriginSummary(paths) : "",
      `Loaded Queue rows: ${Array.isArray(queueRows) ? queueRows.length : 0}`,
      `Selected Queue source: ${selectedPath || "(none)"}`,
      paths.length ? `First staged path: ${paths[0]}` : "",
      mediaCount ? `First media path: ${classified.media[0]}` : "",
    ].filter(Boolean).join("\n"));
  }

  function appendRenamePaths(paths, sourceLabel, origin = "", messageSuffix = "") {
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
    const suffix = messageSuffix ? ` ${messageSuffix}` : "";
    if (!additions.length) {
      renderRenameFileSourceSummary(`${sourceLabel || "Source"} added no new paths.${suffix}`);
      return 0;
    }
    input.value = [...current, ...additions].join("\n");
    rememberRenamePathOrigins(additions, origin || "manual");
    renderRenameFileSourceSummary(`${sourceLabel || "Source"} added ${additions.length} path${additions.length === 1 ? "" : "s"}.${suffix}`);
    syncRenameCommandButtons();
    return additions.length;
  }

  function renameIgnoredPathSuffix(data = {}) {
    const ignored = Number(data.ignored_path_count || 0);
    const ignoredSidecars = Number(data.ignored_sidecar_count || 0);
    if (!ignored) return "";
    return `Ignored ${ignored} non-media path${ignored === 1 ? "" : "s"}${ignoredSidecars ? ` including ${ignoredSidecars} sidecar path${ignoredSidecars === 1 ? "" : "s"}` : ""}.`;
  }

  function appendResolvedRenameBrowsePaths(data, sourceLabel, origin) {
    const paths = Array.isArray(data?.paths) ? data.paths : [];
    return appendRenamePaths(paths, sourceLabel, origin, renameIgnoredPathSuffix(data));
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
      appendResolvedRenameBrowsePaths(data, folderMode ? "Windows folder browser" : "Windows file browser", folderMode ? "folder" : "browse");
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
    setRenameStatusLine("rename-status", "Idle", "empty");
    setRenameStatusLine("rename-preview-status", "No preview", "empty");
    setText("rename-summary", lastRenameEmptyMessage);
    renderRenameFileSourceSummary("Cleared staged rename paths.");
    renderRenameBatchSafety({ rows: [], counts: {} });
    renderRenamePipelineHandoff({ rows: [], counts: {} });
    renderRenameReviewBoard({ rows: [], counts: {} });
    renderRenameSelectionAudit();
    renderRenameApplyReadiness();
    renderRenameBulkEditor();
    resetRenameApplyEvidence("Cleared staged rename paths. Previous apply evidence is no longer tied to the current scope.");
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

  function captureRenameSelectionScroll() {
    return window.mediaPipelineDom?.captureScrollablePositions?.() || null;
  }

  function restoreRenameSelectionScroll(snapshot) {
    if (snapshot) window.mediaPipelineDom?.restoreScrollablePositions?.(snapshot);
  }

  function selectRenameRow(item) {
    const scrollSnapshot = captureRenameSelectionScroll();
    const key = renameSourceKey(item);
    selectedRenameSourceKey = key;
    syncRenameSelectedInputs(item);
    renderRenameDetail(item || null);
    renderRenameBulkEditor();
    renderRenameRows();
    restoreRenameSelectionScroll(scrollSnapshot);
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
      if (typeof window.mediaPipelineProgressView?.renderProgressBarsInto === "function") {
        window.mediaPipelineProgressView.renderProgressBarsInto.apply(window.mediaPipelineProgressView, arguments);
      }
    },
    setText,
  });
  const {
    renderRenameApplyOutcomeReview,
    renderRenameApplyInFlight,
    renderRenameApplyProgress,
    renderRenameApplyResult: renderRenameApplyResultFromSlice,
    renameApplyOutcomeRows,
    renameApplyOutcomeStatus,
    renameApplyOutcomeStatusState,
    renameApplyOutcomeSummaryLines,
    renameApplyProgressBars,
    renameApplyResultLines,
  } = renameApplyResultSlice;

  function renameApplyPayloadFromResult(result) {
    if (!result || typeof result !== "object") return {};
    return result.raw && typeof result.raw === "object" ? result.raw : result;
  }

  function renameUndoManifestFromApplyResult(result) {
    const payload = renameApplyPayloadFromResult(result);
    const data = payload.data && typeof payload.data === "object" ? payload.data : {};
    return String(data.undo_manifest || "").trim();
  }

  function renameElapsedText(startedAt) {
    const elapsedMs = Math.max(0, Date.now() - Number(startedAt || Date.now()));
    const seconds = Math.floor(elapsedMs / 1000);
    if (seconds < 60) return `${seconds}s`;
    const minutes = Math.floor(seconds / 60);
    return `${minutes}m ${String(seconds % 60).padStart(2, "0")}s`;
  }

  function stopRenameCommandActivity() {
    if (renameCommandActivityTimer) {
      clearTimeout(renameCommandActivityTimer);
      renameCommandActivityTimer = 0;
    }
    renameCommandActivityState = null;
  }

  function scheduleRenameCommandActivityTick() {
    if (!renameCommandActivityState || typeof setTimeout !== "function") return;
    if (renameCommandActivityTimer) clearTimeout(renameCommandActivityTimer);
    renameCommandActivityTimer = setTimeout(() => {
      renameCommandActivityTimer = 0;
      if (!renameCommandActivityState) return;
      renderRenameCommandActivity();
      scheduleRenameCommandActivityTick();
    }, 1000);
  }

  function renderRenameCommandActivity() {
    const container = byId("rename-apply-progress-bars");
    if (!container || !renameCommandActivityState) return;
    const state = renameCommandActivityState;
    const wrapper = document.createElement("div");
    wrapper.className = "rename-command-activity";
    wrapper.dataset.state = "running";
    wrapper.setAttribute("role", "status");
    wrapper.setAttribute("aria-live", "polite");

    const header = document.createElement("div");
    header.className = "rename-command-activity-header";
    const title = document.createElement("p");
    title.className = "rename-command-activity-title";
    title.textContent = state.title;
    const meta = document.createElement("p");
    meta.className = "rename-command-activity-meta rename-command-activity-indicator";
    meta.textContent = `Waiting for backend result - elapsed ${renameElapsedText(state.startedAt)}`;
    header.appendChild(title);
    header.appendChild(meta);
    wrapper.appendChild(header);

    const detail = document.createElement("p");
    detail.className = "rename-command-activity-detail";
    detail.textContent = state.detail;
    wrapper.appendChild(detail);
    container.replaceChildren(wrapper);
  }

  function startRenameCommandActivity(kind, count) {
    stopRenameCommandActivity();
    const planned = Math.max(0, Number(count || 0));
    const isUndo = kind === "undo";
    renameCommandActivityState = {
      kind,
      startedAt: Date.now(),
      title: isUndo
        ? "Undoing last apply... waiting for backend result"
        : `Renaming ${planned} media file${planned === 1 ? "" : "s"}... waiting for backend result`,
      detail: isUndo
        ? "Undo command submitted to the backend. This is command activity, not row-by-row progress."
        : `${planned} checked rename${planned === 1 ? "" : "s"} submitted. This is command activity, not row-by-row progress.`,
    };
    const panel = byId("rename-apply-status-panel");
    if (panel) panel.dataset.state = "running";
    setRenameStatusLine("rename-apply-status-summary", renameCommandActivityState.title, "running");
    renderRenameCommandActivity();
    scheduleRenameCommandActivityTick();
  }

  function syncRenameUndoButton() {
    const button = byId("rename-undo-button");
    const status = byId("rename-undo-status");
    const hasManifest = Boolean(lastRenameUndoManifest);
    if (button) {
      button.hidden = !lastRenameApplyHadResult;
      button.disabled = renameApplyInFlight || renameUndoInFlight || !hasManifest || lastRenameUndoCompleted;
      button.textContent = "Undo Last Apply";
      button.title = hasManifest
        ? `Undo manifest: ${lastRenameUndoManifest}`
        : "Undo is unavailable because the last backend apply result did not report an undo manifest.";
    }
    if (status) {
      if (!lastRenameApplyHadResult) status.textContent = "No undo available.";
      else if (lastRenameUndoCompleted) status.textContent = "Undo completed.";
      else if (hasManifest) status.textContent = "Undo available for the last apply.";
      else status.textContent = "No undo manifest reported for this apply.";
    }
  }

  function syncRenameApplyStatusPanelFromResult(result) {
    const payload = renameApplyPayloadFromResult(result);
    const data = payload.data && typeof payload.data === "object" ? payload.data : {};
    const panel = byId("rename-apply-status-panel");
    const renamed = Number(data.renamed || 0);
    const applied = Number(data.applied_count ?? data.selected ?? 0);
    if (panel) panel.dataset.state = payload.ok ? "ready" : payload.severity || "blocked";
    if (!payload || !Object.keys(payload).length) {
      setRenameStatusLine("rename-apply-status-summary", "Ready to apply 0 checked renames", "waiting");
      return;
    }
    if (payload.ok) {
      setRenameStatusLine("rename-apply-status-summary", `${renamed} renamed / ${applied} applied`, "ready");
    } else {
      setRenameStatusLine("rename-apply-status-summary", payload.message || "Rename apply failed", "blocked");
    }
  }

  function renderRenameApplyResult(result) {
    stopRenameCommandActivity();
    renderRenameApplyResultFromSlice(result);
    if (!result) {
      lastRenameApplyHadResult = false;
      lastRenameUndoManifest = "";
      lastRenameUndoCompleted = false;
      lastRenameApplyResultPayload = null;
      syncRenameApplyStatusPanelFromResult(null);
      syncRenameUndoButton();
      return;
    }
    const payload = renameApplyPayloadFromResult(result);
    lastRenameApplyHadResult = Boolean(payload && Object.keys(payload).length);
    lastRenameUndoManifest = payload.ok ? renameUndoManifestFromApplyResult(payload) : "";
    lastRenameApplyResultPayload = payload.ok ? payload : null;
    lastRenameUndoCompleted = false;
    syncRenameApplyStatusPanelFromResult(payload);
    syncRenameUndoButton();
  }

  function renameFiniteNumber(value, fallback = 0) {
    const numberValue = Number(value);
    return Number.isFinite(numberValue) ? numberValue : fallback;
  }

  function renameLastApplyUndoCounts() {
    const payload = lastRenameApplyResultPayload && typeof lastRenameApplyResultPayload === "object" ? lastRenameApplyResultPayload : {};
    const data = payload.data && typeof payload.data === "object" ? payload.data : {};
    const rows = Array.isArray(data.rows) ? data.rows : [];
    const media = renameFiniteNumber(data.media_operations, renameFiniteNumber(data.applied_count, renameFiniteNumber(data.selected, rows.length)));
    const sidecarOps = renameFiniteNumber(data.sidecar_operations, renameFiniteNumber(data.sidecars, rows.reduce((acc, row) => acc + renameFiniteNumber(row?.sidecar_count, 0), 0)));
    return {
      media,
      sidecars: renameFiniteNumber(data.sidecars, sidecarOps),
      sidecarOps,
      totalOps: media + sidecarOps,
      manifestName: renameConfirmBasename(lastRenameUndoManifest) || "last apply manifest",
    };
  }

  function renderRenameUndoCompletionProgress(payload) {
    stopRenameCommandActivity();
    const data = payload.data && typeof payload.data === "object" ? payload.data : {};
    const undone = renameFiniteNumber(data.undone, 0);
    const skipped = renameFiniteNumber(data.skipped, 0);
    const failed = renameFiniteNumber(data.failed, payload.ok ? 0 : 1);
    const isOk = Boolean(payload.ok && failed <= 0);
    const detail = isOk
      ? `${undone} restored / ${skipped} skipped / ${failed} failed`
      : String(payload.message || "Rename undo failed.");
    const renderer = window.mediaPipelineProgressView?.renderProgressBarsInto;
    if (typeof renderer === "function") {
      const updatedAt = new Date().toISOString();
      renderer("rename-apply-progress-bars", [{
        id: "rename_undo",
        label: "Rename undo",
        mode: "determinate",
        percent: isOk ? 100 : 0,
        status: isOk ? "complete" : "failed",
        detail,
        source: payload.command || "rename.undo",
        updated_at: updatedAt,
        stale: false,
      }], {
        status: isOk ? "complete" : "failed",
        updated_at: updatedAt,
      }, "No rename undo result loaded.");
      return;
    }
    setText("rename-apply-progress-bars", `Rename undo\n${isOk ? "complete - 100%" : "failed"}\n${detail}`);
  }

  function renderRenameUndoResult(result) {
    stopRenameCommandActivity();
    const payload = renameApplyPayloadFromResult(result);
    const data = payload.data && typeof payload.data === "object" ? payload.data : {};
    const undone = Number(data.undone || 0);
    const skipped = Number(data.skipped || 0);
    const failed = Number(data.failed || 0);
    const status = payload.ok && failed <= 0 ? "ready" : "blocked";
    const panel = byId("rename-apply-status-panel");
    if (panel) panel.dataset.state = payload.ok && failed <= 0 ? "undone" : "failed";
    setRenameStatusLine(
      "rename-apply-status-summary",
      payload.ok ? `${undone} restored / ${skipped} skipped operations` : payload.message || "Rename undo failed",
      status,
    );
    setRenameStatusLine(
      "rename-last-apply-status",
      payload.ok ? `Undo completed: ${undone} restored / ${skipped} skipped` : "Undo failed",
      status,
    );
    renderRenameUndoCompletionProgress(payload);
    setText(
      "rename-last-apply-detail",
      [
        `Command: ${payload.command || "rename.undo"}`,
        `Result: ${payload.ok ? "ok" : payload.severity || "error"}`,
        `Message: ${payload.message || ""}`,
        `Undo manifest: ${renameConfirmBasename(data.undo_manifest || lastRenameUndoManifest)}`,
        `Media operations: ${data.media_operations ?? ""}`,
        `Sidecar operations: ${data.sidecar_operations ?? ""}`,
        `Undone operations: ${undone}`,
        `Skipped operations: ${skipped}`,
        `Failed operations: ${failed}`,
      ].join("\n"),
    );
    lastRenameUndoCompleted = Boolean(payload.ok && failed <= 0);
    syncRenameUndoButton();
  }

  function resetRenameApplyEvidence(reason = "") {
    renderRenameApplyResult(null);
    setRenameStatusLine("rename-last-apply-status", "No apply", "empty");
    if (reason) {
      setText("rename-last-apply-detail", reason);
      setText("rename-apply-history", `${reason}\nRecent backend command history may still include earlier rename.apply entries, but no apply evidence is staged for the current paths.`);
    }
  }

  async function applySelectedRename() {
    return applyRenameWorkbench();
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
    setRenameStatusLine("rename-status", `${counts.ready || 0} ready, ${counts.match || 0} match, ${counts.blocked || 0} blocked${capText ? `; ${capText}` : ""}`, (counts.blocked || 0) ? "blocked" : (counts.warning || 0) ? "warning" : "ready");
    setRenameStatusLine("rename-preview-status", renamePreviewStatusText(), "ready");
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
    const duplicateTargets = renameDuplicateTargetSet(lastRenameRows);
    Array.from(checkedRenameSourceKeys).forEach((key) => {
      const checkedRow = lastRenameRows.find((row) => renameSourceKey(row) === key);
      const hardBlocked = !checkedRow
        || !renameRowCanApply(checkedRow)
        || duplicateTargets.has(renameTargetKey(checkedRow))
        || (Boolean(checkedRow.destination_exists) && !checkedRow.matches_target);
      if (hardBlocked) checkedRenameSourceKeys.delete(key);
    });
    tbody.replaceChildren();
    lastRenameRows.slice(0, RENAME_PREVIEW_RENDER_LIMIT).forEach((item) => {
      const row = document.createElement("tr");
      const isDuplicateTarget = duplicateTargets.has(renameTargetKey(item));
      const isExistingCollision = Boolean(item.destination_exists) && !item.matches_target;
      row.dataset.status = isDuplicateTarget ? "duplicate" : isExistingCollision ? "blocked" : (item.status || "");
      if (isDuplicateTarget) row.dataset.renameDuplicate = "true";
      row.title = [
        `Status: ${item.status || "unknown"} - ${renameStatusExplanation(item.status)}`,
        `Confidence: ${renameConfidenceLabel(item) || "unknown"} - ${renameConfidenceExplanation(item.confidence)}`,
        `Preview source: ${renamePreviewSourceLabel(item.preview_source || "unknown")}`,
        `Change kind: ${item.change_kind || "unknown"}`,
        isDuplicateTarget ? "Duplicate target: this staged preview collides with another row and cannot be auto-checked." : "",
      ].filter(Boolean).join("\n");
      const key = renameSourceKey(item);
      row.dataset.sourceKey = key;
      const checkCell = document.createElement("td");
      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.checked = checkedRenameSourceKeys.has(key);
      checkbox.disabled = !renameRowCanApply(item) || isDuplicateTarget || isExistingCollision;
      const rowReason = renameImportantRowReason(item);
      checkbox.title = checkbox.disabled
        ? `Blocked rename rows cannot be checked for apply${isDuplicateTarget ? ": duplicate target in staged preview" : isExistingCollision ? ": existing destination path" : rowReason ? `: ${rowReason}` : "."}`
        : "Check this row for backend selected_sources apply.";
      checkbox.addEventListener("click", (event) => {
        event.stopPropagation();
        setRenameRowCheckedFromCheckbox(item, checkbox);
      });
      checkbox.addEventListener("change", () => setRenameRowCheckedFromCheckbox(item, checkbox));
      checkCell.appendChild(checkbox);
      checkCell.addEventListener("click", (event) => {
        if (event.target === checkbox || checkbox.disabled) return;
        event.stopPropagation();
        checkbox.checked = !checkbox.checked;
        setRenameRowCheckedFromCheckbox(item, checkbox);
      });
      row.appendChild(checkCell);
      appendCells(row, [
        item.source_name || item.source || "",
        item.pipeline_guess || "",
        item.target_name || "",
        renameConfidenceLabel(item),
        isDuplicateTarget ? "Duplicate target" : isExistingCollision ? "Existing destination" : renameRowStatusDisplay(item),
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
    syncRenameUndoButton();
  }

  function setRenameUndoBusy(isBusy) {
    renameUndoInFlight = Boolean(isBusy);
    syncRenameCommandButtons();
    syncRenameUndoButton();
  }

  function syncRenameCommandButtons() {
    const commandBusy = renamePreviewInFlight || renameBrowseInFlight || renameApplyInFlight || renameUndoInFlight || renameBadCaseInFlight;
    const stalePreview = updateRenamePreviewFreshnessState();
    const applyScope = getRenameApplyScopeRows();
    const rowsToApply = applyScope.rows;
    const readinessBlockers = stalePreview ? [] : renameApplyScopeBlockers(rowsToApply);
    const previewDuplicateTargets = renameDuplicateTargetSet(lastRenameRows);
    const previewHasBlockedRows = previewDuplicateTargets.size > 0 || lastRenameRows.some((row) => !renameRowCanApply(row));
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
        applyButton.textContent = "Check rows before apply";
      }
      applyButton.disabled = commandBusy || !lastRenameRows.length || stalePreview || !checkedRenameSourceKeys.size || !rowsToApply.length || readinessBlockers.length > 0;
    }
    const hint = byId("rename-apply-status-hint");
    if (hint) {
      if (stalePreview) {
        hint.textContent = "Preview out of date. Run Preview again before applying.";
      } else if (readinessBlockers.length) {
        hint.textContent = `Blocked by readiness: ${readinessBlockers.join("; ")}`;
      } else if (lastRenameRows.length && !rowsToApply.length && previewHasBlockedRows) {
        hint.textContent = previewDuplicateTargets.size
          ? `Resolve duplicate destination targets before applying: ${Array.from(previewDuplicateTargets).slice(0, 3).join(" | ")}`
          : "Resolve blocked preview rows before applying.";
      } else if (lastRenameRows.length && !checkedRenameSourceKeys.size) {
        hint.textContent = "No rows checked. Use Check Applicable or manually check reviewed rows before applying.";
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
    const checkAllButton = byId("rename-check-all-button");
    if (checkAllButton) checkAllButton.disabled = commandBusy || !lastRenameRows.length;
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
    syncRenameBadCaseButton();
    syncRenameUndoButton();
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
          setRenameStatusLine("rename-status", "Idle", "empty");
          setRenameStatusLine("rename-preview-status", "No preview", "empty");
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
      setRenameStatusLine("rename-status", "Previewing...", "running");
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
      setRenameStatusLine("rename-status", "Error", "blocked");
      setRenameStatusLine("rename-preview-status", "Preview failed", "blocked");
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
    collectRenameTvFilterTerms,
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
    syncRenameBadCaseButton,
    renameBadCasePayloadFromRow,
    submitRenameBadCasePayload,
    openRenameBadCaseDialog,
    submitRenameBadCaseDialog,
    renderRenameDetail,
    selectRenameRow,
    getSelectedRenameRow,
    getCheckedRenameRows,
    renameRowCanApply,
    setRenameRowChecked,
    checkApplicableRenameRows,
    checkAllRenameRows,
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
    undoLastRenameApply,
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
    classifyRenamePathValues,
    normalizeRenameDroppedPathValues,
    renameDroppedPathFromFile,
    renameDroppedPathValuesFromDataTransfer,
    renameDroppedPathValuesFromBridgeDetail,
    handleRenameDroppedPaths,
    renameApplicablePreviewRows,
    renameOpenConfirmDialog,
    renameOpenUndoConfirmDialog,
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
   * Apply operates only on checked preview rows after confirmation.
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

  function renameConfirmBasename(value) {
    const text = String(value || "").trim();
    if (!text) return "";
    const normalized = text.replace(/\\/g, "/");
    return normalized.split("/").filter(Boolean).pop() || text;
  }

  function renameConfirmSourceName(item) {
    return String(item?.source_name || "").trim() || renameConfirmBasename(item?.source_path || item?.source);
  }

  function renameConfirmTargetName(item) {
    return String(item?.target_name || item?.final_name || item?.pipeline_guess || "").trim()
      || renameConfirmBasename(item?.destination || item?.target_path);
  }

  function renameConfirmSidecarCount(item) {
    const explicit = Number(item?.sidecar_count ?? item?.sidecars);
    if (Number.isFinite(explicit)) return Math.max(0, explicit);
    return Array.isArray(item?.sidecar_moves) ? item.sidecar_moves.length : 0;
  }

  function renameConfirmRowState(item) {
    const status = String(item?.status || "").trim().toLowerCase();
    const hasErrors = Array.isArray(item?.errors) && item.errors.length > 0;
    if (hasErrors || ["blocked", "failed", "error", "duplicate"].includes(status)) return "blocked";
    if (["warning", "review"].includes(status) || (Array.isArray(item?.warnings) && item.warnings.length > 0)) return "review";
    if (status === "match") return "match";
    return "ready";
  }

  function renameConfirmStatusToken(state) {
    if (state === "blocked") return { symbol: "×", label: "Blocked" };
    if (state === "review") return { symbol: "!", label: "Review" };
    if (state === "match") return { symbol: "=", label: "Match" };
    return { symbol: "✓", label: "Ready" };
  }

  function renameConfirmSequenceText(rows) {
    if (!rows.length) return "No rename rows selected";
    const first = renameConfirmTargetName(rows[0]);
    const last = renameConfirmTargetName(rows[rows.length - 1]);
    if (!first && !last) return "No target names reported";
    if (!last || first === last) return first || last;
    return `${first} -> ${last}`;
  }

  function renameConfirmCounts(rows) {
    const duplicateTargets = typeof renameDuplicateTargets === "function" ? renameDuplicateTargets(rows) : [];
    const existingDestinations = rows.filter((row) => Boolean(row?.destination_exists) && !row?.matches_target).length;
    return rows.reduce((acc, row) => {
      const state = renameConfirmRowState(row);
      acc[state] = (acc[state] || 0) + 1;
      acc.sidecars += renameConfirmSidecarCount(row);
      return acc;
    }, {
      ready: 0,
      match: 0,
      review: 0,
      blocked: 0,
      sidecars: 0,
      conflicts: duplicateTargets.length,
      existingDestinations,
    });
  }

  function renameConfirmAppendText(parent, className, text) {
    const node = document.createElement("span");
    node.className = className;
    node.textContent = text;
    parent.appendChild(node);
    return node;
  }

  function renameConfirmStatusBadge(state) {
    const token = renameConfirmStatusToken(state);
    const badge = document.createElement("span");
    badge.className = `rename-confirm-status-badge rename-confirm-status-${state}`;
    badge.title = token.label;
    badge.setAttribute("aria-label", token.label);
    badge.textContent = token.symbol;
    return badge;
  }

  function renderRenameConfirmSummary(listEl, rowsToApply, outsideRootRows) {
    if (!listEl) return;
    if (typeof listEl.replaceChildren === "function") listEl.replaceChildren();
    else listEl.innerHTML = "";
    const counts = renameConfirmCounts(rowsToApply);
    const primaryState = counts.blocked ? "blocked" : counts.review ? "review" : "ready";

    const summary = document.createElement("div");
    summary.className = "rename-confirm-summary";

    const metrics = document.createElement("div");
    metrics.className = "rename-confirm-metrics";
    [
      [`${rowsToApply.length} media file${rowsToApply.length === 1 ? "" : "s"} ready`, "Media"],
      [`${counts.sidecars} matching sidecar${counts.sidecars === 1 ? "" : "s"} will move`, "Sidecars"],
    ].forEach(([value, label]) => {
      const metric = document.createElement("div");
      metric.className = "rename-confirm-metric";
      renameConfirmAppendText(metric, "rename-confirm-metric-value", value);
      renameConfirmAppendText(metric, "rename-confirm-metric-label", label);
      metrics.appendChild(metric);
    });
    summary.appendChild(metrics);

    const sequence = document.createElement("div");
    sequence.className = "rename-confirm-sequence";
    renameConfirmAppendText(sequence, "rename-confirm-label", "Sequence");
    renameConfirmAppendText(sequence, "rename-confirm-sequence-value", renameConfirmSequenceText(rowsToApply));
    summary.appendChild(sequence);

    const health = document.createElement("div");
    health.className = "rename-confirm-health";
    const batchBadge = renameConfirmStatusBadge(primaryState);
    health.appendChild(batchBadge);
    renameConfirmAppendText(health, "rename-confirm-health-label", renameConfirmStatusToken(primaryState).label);
    [
      `${counts.blocked} blocked`,
      `${counts.conflicts} conflicts`,
      `${counts.existingDestinations} existing destinations`,
    ].forEach((label) => renameConfirmAppendText(health, "rename-confirm-health-chip", label));
    summary.appendChild(health);
    listEl.appendChild(summary);

    const details = document.createElement("details");
    details.className = "rename-confirm-details";
    const detailsSummary = document.createElement("summary");
    detailsSummary.textContent = "Show details";
    details.appendChild(detailsSummary);
    const table = document.createElement("div");
    table.className = "rename-confirm-detail-table";
    table.setAttribute("role", "table");
    const header = document.createElement("div");
    header.className = "rename-confirm-detail-row rename-confirm-detail-header";
    header.setAttribute("role", "row");
    ["Status", "Original", "New name", "Sidecars"].forEach((label) => {
      const cell = document.createElement("span");
      cell.setAttribute("role", "columnheader");
      cell.textContent = label;
      header.appendChild(cell);
    });
    table.appendChild(header);
    rowsToApply.forEach((item) => {
      const state = renameConfirmRowState(item);
      const row = document.createElement("div");
      row.className = `rename-confirm-detail-row rename-confirm-detail-row-${state}`;
      row.setAttribute("role", "row");
      const statusCell = document.createElement("span");
      statusCell.setAttribute("role", "cell");
      statusCell.appendChild(renameConfirmStatusBadge(state));
      row.appendChild(statusCell);
      [renameConfirmSourceName(item), renameConfirmTargetName(item), String(renameConfirmSidecarCount(item))].forEach((value) => {
        const cell = document.createElement("span");
        cell.setAttribute("role", "cell");
        cell.textContent = value;
        row.appendChild(cell);
      });
      table.appendChild(row);
      if (state === "review" || state === "blocked") {
        const evidence = document.createElement("div");
        evidence.className = "rename-confirm-detail-row rename-confirm-detail-evidence";
        evidence.setAttribute("role", "row");
        evidence.textContent = [
          ...(Array.isArray(item.warnings) ? item.warnings : []),
          ...(Array.isArray(item.errors) ? item.errors : []),
          item.destination_exists && !item.matches_target ? `Destination exists: ${item.destination || item.target_path || renameConfirmTargetName(item)}` : "",
          Array.isArray(outsideRootRows) && outsideRootRows.includes(item) && state === "blocked" ? `Path evidence: ${item.source || item.source_path || renameConfirmSourceName(item)}` : "",
        ].filter(Boolean).join(" ");
        if (evidence.textContent) table.appendChild(evidence);
      }
    });
    details.appendChild(table);
    listEl.appendChild(details);
  }

  function renderRenameUndoConfirmSummary(listEl) {
    if (!listEl) return;
    if (typeof listEl.replaceChildren === "function") listEl.replaceChildren();
    else listEl.innerHTML = "";
    const counts = renameLastApplyUndoCounts();

    const summary = document.createElement("div");
    summary.className = "rename-confirm-summary";

    const metrics = document.createElement("div");
    metrics.className = "rename-confirm-metrics";
    [
      [`${counts.media} media file${counts.media === 1 ? "" : "s"} will restore`, "Media"],
      [`${counts.sidecars} matching sidecar${counts.sidecars === 1 ? "" : "s"} will move back`, "Sidecars"],
      [`${counts.totalOps} total operation${counts.totalOps === 1 ? "" : "s"}`, "Scope"],
    ].forEach(([value, label]) => {
      const metric = document.createElement("div");
      metric.className = "rename-confirm-metric";
      renameConfirmAppendText(metric, "rename-confirm-metric-value", value);
      renameConfirmAppendText(metric, "rename-confirm-metric-label", label);
      metrics.appendChild(metric);
    });
    summary.appendChild(metrics);

    const manifest = document.createElement("div");
    manifest.className = "rename-confirm-sequence";
    renameConfirmAppendText(manifest, "rename-confirm-label", "Undo manifest");
    renameConfirmAppendText(manifest, "rename-confirm-sequence-value", counts.manifestName);
    summary.appendChild(manifest);

    const health = document.createElement("div");
    health.className = "rename-confirm-health";
    health.appendChild(renameConfirmStatusBadge("review"));
    renameConfirmAppendText(health, "rename-confirm-health-label", "Confirm restore");
    renameConfirmAppendText(health, "rename-confirm-health-chip", "last apply only");
    renameConfirmAppendText(health, "rename-confirm-health-chip", "backend undo");
    summary.appendChild(health);
    listEl.appendChild(summary);
  }

  function renameOpenConfirmDialog(rowsToApply, outsideRootRows) {
    const dialog = renameDialogById("rename-confirm-dialog");
    if (!dialog) return Promise.resolve(false);
    setText("rename-confirm-title", "Confirm filesystem rename");
    const countEl = byId("rename-confirm-count");
    if (countEl) countEl.textContent = `Renaming ${rowsToApply.length} checked media file${rowsToApply.length === 1 ? "" : "s"}.`;
    setText("rename-confirm-mutation-warning", "Backend rename.apply will rename the checked media and matching sidecars.");
    const applyButton = byId("rename-confirm-apply-button");
    if (applyButton) applyButton.textContent = `Apply ${rowsToApply.length} Rename${rowsToApply.length === 1 ? "" : "s"}`;
    renderRenameConfirmSummary(byId("rename-confirm-list"), rowsToApply, outsideRootRows);
    const warningEl = byId("rename-confirm-warning");
    if (warningEl) {
      const warnings = [];
      if (lastRenameRows.length > RENAME_PREVIEW_RENDER_LIMIT) {
        const hiddenChecked = rowsToApply.filter((row) => lastRenameRows.indexOf(row) >= RENAME_PREVIEW_RENDER_LIMIT).length;
        warnings.push(`Render cap: ${RENAME_PREVIEW_RENDER_LIMIT} of ${lastRenameRows.length} preview rows are visible${hiddenChecked ? `; ${hiddenChecked} checked row(s) are not visible in the table` : ""}.`);
      }
      warningEl.textContent = warnings.join(" ");
      warningEl.hidden = !warnings.length;
    }
    return new Promise((resolve) => {
      const onClose = () => {
        if (typeof dialog.removeEventListener === "function") {
          dialog.removeEventListener("close", onClose);
        }
        const confirmed = dialog.returnValue === "confirm";
        if (!confirmed) {
          setText("rename-apply-status-hint", "Apply canceled. No rename.apply request was sent.");
          setText("rename-detail", "Apply canceled from confirmation modal. Preview and checked rows remain staged; no filesystem rename was requested.");
        }
        resolve(confirmed);
      };
      dialog.addEventListener("close", onClose);
      const cancelBtn = byId("rename-confirm-cancel-button");
      if (cancelBtn) {
        cancelBtn.onclick = () => dialog.close("cancel");
      }
      try {
        dialog.showModal();
      } catch (_err) {
        if (typeof dialog.removeEventListener === "function") {
          dialog.removeEventListener("close", onClose);
        }
        resolve(false);
      }
    });
  }

  function renameOpenUndoConfirmDialog() {
    const dialog = renameDialogById("rename-confirm-dialog");
    if (!dialog) return Promise.resolve(false);
    const counts = renameLastApplyUndoCounts();
    setText("rename-confirm-title", "Confirm undo rename");
    setText(
      "rename-confirm-count",
      `Undo last apply: ${counts.totalOps} operation${counts.totalOps === 1 ? "" : "s"}.`,
    );
    setText("rename-confirm-mutation-warning", "Backend rename.undo will restore the last apply using its undo manifest.");
    const applyButton = byId("rename-confirm-apply-button");
    if (applyButton) applyButton.textContent = "Undo Last Apply";
    renderRenameUndoConfirmSummary(byId("rename-confirm-list"));
    const warningEl = byId("rename-confirm-warning");
    if (warningEl) {
      warningEl.textContent = "";
      warningEl.hidden = true;
    }
    return new Promise((resolve) => {
      const onClose = () => {
        if (typeof dialog.removeEventListener === "function") {
          dialog.removeEventListener("close", onClose);
        }
        const confirmed = dialog.returnValue === "confirm";
        if (!confirmed) {
          setText("rename-apply-status-hint", "Undo canceled. No rename.undo request was sent.");
          setText("rename-detail", "Undo canceled from confirmation modal. The last apply undo remains available.");
        }
        resolve(confirmed);
      };
      dialog.addEventListener("close", onClose);
      const cancelBtn = byId("rename-confirm-cancel-button");
      if (cancelBtn) {
        cancelBtn.onclick = () => dialog.close("cancel");
      }
      try {
        dialog.showModal();
      } catch (_err) {
        if (typeof dialog.removeEventListener === "function") {
          dialog.removeEventListener("close", onClose);
        }
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
    const isUndo = String(payload.command || "").toLowerCase() === "rename.undo"
      || String(data.schema_version || "").toLowerCase() === "desktop_rename_undo_result.v1";
    const finiteCount = (value) => {
      const numberValue = Number(value);
      return Number.isFinite(numberValue) ? numberValue : null;
    };
    const setResultLabel = (id, value) => setText(id, value);
    if (isUndo) {
      const restored = finiteCount(data.undone) ?? rows.filter((row) => String(row.status || "").toLowerCase() === "undone").length;
      const skipped = finiteCount(data.skipped) ?? rows.filter((row) => String(row.status || "").toLowerCase() === "skipped").length;
      const failed = finiteCount(data.failed) ?? (payload.ok ? 0 : 1);
      const mediaOps = finiteCount(data.media_operations) ?? 0;
      const sidecarOps = finiteCount(data.sidecar_operations) ?? 0;
      setText("rename-result-title", "Undo result");
      setResultLabel("rename-result-success-label", "Restored");
      setResultLabel("rename-result-unchanged-label", "Media ops");
      setResultLabel("rename-result-skipped-label", "Skipped");
      setResultLabel("rename-result-protected-label", "Sidecar ops");
      setResultLabel("rename-result-failed-label", "Failed");
      const setNum = (id, value) => {
        const el = byId(id);
        if (el) el.textContent = String(value);
      };
      setNum("rename-result-success", restored);
      setNum("rename-result-renamed", restored);
      setNum("rename-result-unchanged", mediaOps);
      setNum("rename-result-skipped", skipped);
      setNum("rename-result-protected", sidecarOps);
      setNum("rename-result-failed", failed);
      const summaryEl = byId("rename-result-summary");
      if (summaryEl) {
        const manifestName = renameConfirmBasename(data.undo_manifest || lastRenameUndoManifest);
        const warnings = Array.isArray(payload.warnings) ? payload.warnings.filter(Boolean) : [];
        summaryEl.textContent = [
          payload.ok ? `${restored} restored / ${skipped} skipped / ${failed} failed` : payload.message || "Rename undo failed.",
          manifestName ? `Undo manifest: ${manifestName}` : "",
          warnings.length ? `Warning: ${warnings.join("; ")}` : "",
        ].filter(Boolean).join("\n");
      }
      const errorsEl = byId("rename-result-errors");
      const errors = Array.isArray(payload.errors) ? payload.errors.filter((value) => String(value || "").trim()) : [];
      if (errorsEl) {
        errorsEl.innerHTML = "";
        if (errors.length || failed > 0 || !payload.ok) {
          errorsEl.hidden = false;
          const heading = document.createElement("strong");
          heading.textContent = "Errors";
          errorsEl.appendChild(heading);
          const list = document.createElement("ul");
          list.className = "rename-modal-error-list";
          const messages = errors.length ? errors : [payload.message || "Rename undo failed."];
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
        openLogButton.hidden = true;
        openLogButton.onclick = null;
      }
      try {
        dialog.showModal();
      } catch (_err) { /* swallow */ }
      return;
    }
    setText("rename-result-title", "Rename result");
    setResultLabel("rename-result-success-label", "Renamed");
    setResultLabel("rename-result-unchanged-label", "Unchanged");
    setResultLabel("rename-result-skipped-label", "Skipped");
    setResultLabel("rename-result-protected-label", "Protected");
    setResultLabel("rename-result-failed-label", "Failed");
    let renamed = finiteCount(data.renamed) ?? finiteCount(data.success_count) ?? null;
    let unchanged = finiteCount(data.unchanged) ?? null;
    let failed = finiteCount(data.failed_count) ?? null;
    let skipped = finiteCount(data.skipped_count) ?? finiteCount(data.skipped) ?? null;
    let protectedCount = finiteCount(data.protected_count) ?? finiteCount(data.protected) ?? null;
    if ([renamed, unchanged, failed, skipped, protectedCount].some((value) => value === null) && rows.length) {
      const inferred = { renamed: 0, unchanged: 0, failed: 0, skipped: 0, protectedCount: 0 };
      rows.forEach((row) => {
        const status = String(row.status || row.outcome || "").toLowerCase();
        if (status === "success" || status === "renamed" || row.renamed === true) inferred.renamed += 1;
        else if (status === "match" || status === "unchanged" || status === "noop" || status === "no-op" || row.unchanged === true) inferred.unchanged += 1;
        else if (status === "protected" || row.protected === true) inferred.protectedCount += 1;
        else if (status === "skipped" || row.skipped === true) inferred.skipped += 1;
        else if (status === "failed" || status === "error" || row.failed === true) inferred.failed += 1;
      });
      if (renamed === null) renamed = inferred.renamed;
      if (unchanged === null) unchanged = inferred.unchanged;
      if (failed === null) failed = inferred.failed;
      if (skipped === null) skipped = inferred.skipped;
      if (protectedCount === null) protectedCount = inferred.protectedCount;
    }
    renamed = renamed ?? 0;
    unchanged = unchanged ?? 0;
    failed = failed ?? 0;
    skipped = skipped ?? 0;
    protectedCount = protectedCount ?? 0;
    const setNum = (id, value) => {
      const el = byId(id);
      if (el) el.textContent = String(value);
    };
    setNum("rename-result-success", renamed);
    setNum("rename-result-renamed", renamed);
    setNum("rename-result-unchanged", unchanged);
    setNum("rename-result-failed", failed);
    setNum("rename-result-skipped", skipped);
    setNum("rename-result-protected", protectedCount);
    const summaryEl = byId("rename-result-summary");
    if (summaryEl) {
      const summary = String(payload.message || (payload.ok ? "Rename completed." : "Rename did not complete."));
      const undoManifest = String(data.undo_manifest || "").trim();
      const undoManifestName = renameConfirmBasename(undoManifest);
      const logPath = String(data.log_path || data.log_folder || data.output_log || "").trim();
      summaryEl.textContent = [
        summary,
        undoManifestName ? `Undo manifest: ${undoManifestName}` : "",
        logPath ? `Run log evidence: ${logPath}` : "",
      ].filter(Boolean).join("\n");
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
      const logPath = String(data.log_path || data.log_folder || data.output_log || "").trim();
      openLogButton.hidden = !logPath;
      openLogButton.textContent = "Open Run Logs";
      openLogButton.onclick = logPath
        ? () => {
          const requestOpen = window.mediaPipelineDiagnosticsView?.requestDiagnosticsOpen || window.requestDiagnosticsOpen;
          if (typeof requestOpen === "function") requestOpen("run_logs");
        }
        : null;
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
      const message = lastRenameRows.length
        ? "No rows checked. Check intended rows before applying; blocked, duplicate, and existing-destination rows cannot be applied."
        : "Preview has no rows. Run Preview before applying.";
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
      renderRenameApplyInFlight(rowsToApply.length);
      startRenameCommandActivity("apply", rowsToApply.length);
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
      visibleResult = { command: "rename.apply", ok: false, severity: "error", message, errors: [message] };
      appendCommandResult({ command: "rename.apply", ok: false, severity: "error", message });
      renderRenameApplyResult(visibleResult);
    } finally {
      setRenameApplyBusy(false);
      if (visibleResult) renameOpenResultDialog(visibleResult);
    }
  }

  async function undoLastRenameApply() {
    if (renameUndoInFlight || renameApplyInFlight || !lastRenameUndoManifest || lastRenameUndoCompleted) {
      syncRenameUndoButton();
      return;
    }
    const confirmed = await renameOpenUndoConfirmDialog();
    if (!confirmed) {
      syncRenameUndoButton();
      return;
    }
    setRenameUndoBusy(true);
    let visibleResult = null;
    setRenameStatusLine("rename-apply-status-summary", "Undoing last rename apply", "active");
    try {
      startRenameCommandActivity("undo", renameLastApplyUndoCounts().totalOps);
      const result = await apiPost("/api/rename/undo", {
        undo_manifest: lastRenameUndoManifest,
        confirm_undo: true,
      });
      visibleResult = result;
      appendCommandResult(result);
      renderRenameUndoResult(result);
      if (result.ok) {
        replaceRenamePathText((result.data || {}).rows || []);
        await refreshRenamePreview();
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      visibleResult = { command: "rename.undo", ok: false, severity: "error", message, errors: [message] };
      renderRenameUndoResult(visibleResult);
      appendCommandResult(visibleResult);
    } finally {
      setRenameUndoBusy(false);
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
      void handleRenameDroppedPaths(renameDroppedPathValuesFromDataTransfer(event.dataTransfer), "Drag and drop");
    };
    const onTauriFileDrop = (event) => {
      if (!renameDropZoneIsVisible(zone)) return;
      const detail = event?.detail || {};
      const kind = String(detail.kind || "").toLowerCase();
      if (kind === "enter" || kind === "over") {
        zone.classList.add("is-dragging");
        return;
      }
      if (kind === "leave") {
        zone.classList.remove("is-dragging");
        return;
      }
      if (kind !== "drop") return;
      zone.classList.remove("is-dragging");
      void handleRenameDroppedPaths(renameDroppedPathValuesFromBridgeDetail(detail), "Tauri drag and drop");
    };
    zone.addEventListener("dragenter", onDragOver);
    zone.addEventListener("dragover", onDragOver);
    zone.addEventListener("dragleave", onDragLeave);
    zone.addEventListener("drop", onDrop);
    window.addEventListener(RENAME_WEBVIEW_FILE_DROP_EVENT, onTauriFileDrop);
  }

  function renameInitWorkbenchEvents() {
    const applyButton = byId("rename-apply-button");
    if (applyButton) applyButton.addEventListener("click", () => applyRenameWorkbench());
    const undoButton = byId("rename-undo-button");
    if (undoButton) undoButton.addEventListener("click", () => undoLastRenameApply());
    const previewButton = byId("rename-preview-button");
    if (previewButton) previewButton.addEventListener("click", () => refreshRenamePreview());
    const browseFilesButton = byId("rename-browse-files-button");
    if (browseFilesButton) browseFilesButton.addEventListener("click", () => browseRenamePaths("files"));
    const browseFolderButton = byId("rename-browse-folder-button");
    if (browseFolderButton) browseFolderButton.addEventListener("click", () => browseRenamePaths("folder_files"));
    const logBadCaseButton = byId("rename-log-bad-case-button");
    if (logBadCaseButton) logBadCaseButton.addEventListener("click", () => openRenameBadCaseDialog());
    const logBadCaseCancelButton = byId("rename-log-case-cancel-button");
    if (logBadCaseCancelButton) {
      logBadCaseCancelButton.addEventListener("click", () => {
        const dialog = renameDialogById("rename-log-case-dialog");
        if (dialog) dialog.close("cancel");
      });
    }
    const logBadCaseSubmitButton = byId("rename-log-case-submit-button");
    if (logBadCaseSubmitButton) logBadCaseSubmitButton.addEventListener("click", () => submitRenameBadCaseDialog());
    const logBadCaseDialog = byId("rename-log-case-dialog");
    const logBadCaseForm = logBadCaseDialog?.querySelector("form");
    if (logBadCaseForm) {
      logBadCaseForm.addEventListener("submit", (event) => {
        event.preventDefault();
        submitRenameBadCaseDialog();
      });
    }
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
    syncRenameBadCaseButton();
    syncRenameUndoButton();
  }

})();
