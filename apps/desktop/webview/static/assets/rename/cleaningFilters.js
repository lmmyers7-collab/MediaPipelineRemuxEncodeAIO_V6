// Rename cleaning-filter draft, catalog, and backend filename-preview workflow.
(function () {
  "use strict";

  function createRenameCleaningFiltersModule(deps = {}) {
    const {
      RENAME_CLEANING_FILTER_STORAGE_KEY = "",
      RENAME_CLEAN_FILENAME_PREVIEW_ROUTE = "",
      RENAME_FILTER_CATALOG_ROUTE = "",
      RENAME_MOVIE_FILTER_CATALOG_ROUTE = "",
      RENAME_CLEANING_IDS = {},
      apiGet = null,
      appendCommandResult = () => {},
      byId = () => null,
      markRenameWorkbenchNeedsTest = () => {},
      renameCleaningNode = () => null,
      setText = () => {},
      syncRenameCommandButtons = () => {},
    } = deps;
    const documentRef = deps.documentRef || document;
    const windowRef = deps.windowRef || window;
    const storage = deps.storage || (typeof localStorage !== "undefined"
      ? localStorage
      : { getItem: () => null, removeItem: () => {}, setItem: () => {} });
    let renameFilterPreviewRequestId = 0;
    let renameFilterPreviewTimer = 0;
    let renameCleaningFilterSaveMessage = "";
    let renameCleaningFilterSaveMessageUntil = 0;

  function renameCleaningFilterTextareas() {
    return Array.from(documentRef.querySelectorAll("[data-rename-movie-filter-terms], [data-movie-filter-terms]"));
  }

  function renameTvFilterTextareas() {
    return Array.from(documentRef.querySelectorAll("[data-rename-tv-filter-terms], [data-tv-filter-terms]"));
  }

  function renameMovieFilterCheckboxes() {
    return Array.from(documentRef.querySelectorAll("[data-rename-movie-filter], [data-movie-filter]"));
  }

  function renameTvFilterCheckboxes() {
    return Array.from(documentRef.querySelectorAll("[data-rename-tv-filter], [data-tv-filter]"));
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
      storage.setItem(RENAME_CLEANING_FILTER_STORAGE_KEY, JSON.stringify(renameCleaningFilterState()));
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
    const settingsView = windowRef.mediaPipelineSettingsView || {};
    if (typeof settingsView.markSettingsPatchTouched === "function") settingsView.markSettingsPatchTouched();
    if (typeof settingsView.renderSettingsPatchSummary === "function") settingsView.renderSettingsPatchSummary();
    if (typeof windowRef.renderAllLaunchPreflights === "function") windowRef.renderAllLaunchPreflights();
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
    try { storage.removeItem(RENAME_CLEANING_FILTER_STORAGE_KEY); } catch (_) {}
    renderRenameCleaningFilterEditor("Cleaning filter draft reset to saved backend policy.");
    updateRenameFilterPreview();
    syncRenameCommandButtons();
  }

  function loadRenameCleaningFilterState() {
    let state = null;
    try { state = JSON.parse(storage.getItem(RENAME_CLEANING_FILTER_STORAGE_KEY) || "null"); } catch (_) { state = null; }
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
    const get = typeof apiGet === "function" ? apiGet : windowRef.apiGet;
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
    const input = documentRef.getElementById("settings-rename-preview-input");
    const output = documentRef.getElementById("settings-rename-preview-output");
    const status = documentRef.getElementById("settings-rename-preview-status");
    if (!input || !output) return;
    const raw = input.value.trim();
    if (typeof windowRef.clearTimeout === "function") windowRef.clearTimeout(renameFilterPreviewTimer);
    const requestId = ++renameFilterPreviewRequestId;
    if (!raw) {
      output.textContent = "";
      output.dataset.state = "";
      if (status) status.textContent = "Backend cleaner waits for input.";
      return;
    }
    const runPreview = async () => {
      const get = typeof apiGet === "function" ? apiGet : windowRef.apiGet;
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
      renameFilterPreviewTimer = typeof windowRef.setTimeout === "function" ? windowRef.setTimeout(runPreview, 300) : 0;
      if (!renameFilterPreviewTimer) runPreview();
    }
  }


    return {
      renameCleaningFilterTextareas,
      renameTvFilterTextareas,
      renameMovieFilterCheckboxes,
      renameTvFilterCheckboxes,
      collectRenameMovieFilterOptions,
      collectRenameTvFilterOptions,
      parseRenameFilterTerms,
      collectRenameMovieFilterTermsText,
      collectRenameMovieFilterTerms,
      collectRenameTvFilterTermsText,
      collectRenameTvFilterTerms,
      renameCleaningFilterState,
      renameCleaningFilterConfigPatch,
      renderRenameCleaningFilterEditor,
      saveRenameCleaningFilterDraft,
      stageRenameCleaningFilterPatch,
      saveRenameCleaningFilterState,
      resetRenameCleaningFilters,
      loadRenameCleaningFilterState,
      applyRenameFilterCatalogSection,
      loadRenameMovieFilterCatalog,
      renameCleanFilenamePreviewQuery,
      renderRenameFilterPreviewPayload,
      updateRenameFilterPreview,
    };
  }

  window.__renameCleaningFiltersModule = { createRenameCleaningFiltersModule };
})();
