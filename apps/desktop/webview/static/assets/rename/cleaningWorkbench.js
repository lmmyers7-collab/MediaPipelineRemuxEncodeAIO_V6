// Rename cleaning workbench: suggestion preview, staging, and settings handoff.
(function () {
  "use strict";

  function createRenameCleaningWorkbenchModule(deps = {}) {
    const {
      apiGet = null,
      apiPost = null,
      appendCommandResult = () => {},
      byId = () => null,
      collectRenameMovieFilterOptions = () => ({}),
      collectRenameMovieFilterTerms = () => ({}),
      collectRenameTvFilterOptions = () => ({}),
      collectRenameTvFilterTerms = () => ({}),
      loadRenameMovieFilterCatalog = () => {},
      parseRenameFilterTerms = () => [],
      RENAME_CLEAN_FILENAME_PREVIEW_ROUTE = "",
      renameCleaningNode = () => null,
      renderRenameCleaningFilterEditor = () => {},
      saveRenameCleaningFilterDraft = () => {},
      saveRenameCleaningFilterState = async () => false,
      setText = () => {},
      state = {},
      submitRenameBadCasePayload = async () => ({}),
      updateRenameFilterPreview = () => {},
    } = deps;
    const documentRef = deps.documentRef || document;
    const windowRef = deps.windowRef || window;

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
    documentRef.querySelectorAll("[data-rename-workbench-mode-field]").forEach((node) => {
      const active = node.dataset.renameWorkbenchModeField === mode;
      node.hidden = false;
      node.classList.toggle("rename-workbench-inactive", !active);
      node.querySelectorAll("input, select, textarea").forEach((control) => {
        control.disabled = !active;
      });
    });
    documentRef.querySelectorAll("[data-rename-workbench-required-modes]").forEach((node) => {
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
    node.disabled = state.inFlight || !state.saveNewFiltersReady;
  }

  function setRenameWorkbenchBusy(isBusy) {
    state.inFlight = Boolean(isBusy);
    [
      "test-button",
      "save-case-button",
      "stage-suggestions-button",
      "retest-button",
    ].forEach((id) => {
      const node = renameWorkbenchInput(id);
      if (node) node.disabled = state.inFlight;
    });
    updateRenameWorkbenchSaveNewFiltersButton();
  }

  function markRenameWorkbenchNeedsTest() {
    if (!renameWorkbenchInput("form") || state.inFlight) return;
    state.lastPayload = null;
    state.hasStagedSuggestions = false;
    state.saveNewFiltersReady = false;
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
    const productionParity = payload?.production_parity || {};
    const comparisonUnavailable = comparison.status === "unavailable";
    const lines = [
      `Actual: ${actual.target_name || payload?.target_name || "(no backend result)"}`,
      `Expected: ${expected.expected_name || "(expected fields incomplete)"}`,
      `Result: ${comparisonUnavailable ? "Unavailable" : (comparison.ok ? "Pass" : "Needs review")}`,
      `Runtime parity: ${productionParity.status || "unavailable"}`,
    ];
    (comparison.fields || []).forEach((row) => {
      lines.push(`${row.ok ? "OK" : "Mismatch"} ${String(row.field || "").replace(/_/g, " ")}: ${row.actual ?? ""} / ${row.expected ?? ""}`);
    });
    (payload?.warnings || []).forEach((warning) => lines.push(`Warning: ${warning}`));
    (payload?.errors || []).forEach((error) => lines.push(`Error: ${error}`));
    lines.push(`Source: production pipeline destination plan and ${comparison.policy_label || "current Settings filter draft"}.`);
    output.textContent = lines.join("\n");
    output.dataset.state = comparison.ok ? "match" : "changed";
  }

  function renderRenameWorkbenchSuggestionRows(tbody, rows, emptyText) {
    if (!tbody) return;
    tbody.replaceChildren();
    if (!rows.length) {
      const row = documentRef.createElement("tr");
      const cell = documentRef.createElement("td");
      cell.colSpan = 4;
      cell.textContent = emptyText;
      row.appendChild(cell);
      tbody.appendChild(row);
      return;
    }
    rows.forEach(({ item, index }) => {
      const row = documentRef.createElement("tr");
      const alreadyFiltered = Boolean(item.already_filtered);
      const stageRecommended = Boolean(item.stage_recommended ?? (!alreadyFiltered && item.default_destination !== "ignore"));
      row.dataset.suggestionState = alreadyFiltered ? "existing" : "new";
      const checkCell = documentRef.createElement("td");
      const checkbox = documentRef.createElement("input");
      checkbox.type = "checkbox";
      checkbox.checked = stageRecommended;
      checkbox.disabled = alreadyFiltered;
      checkbox.title = alreadyFiltered ? "Already covered by current filters or cleaner result." : "Stage this new filter term.";
      checkbox.dataset.renameWorkbenchSuggestionIndex = String(index);
      checkCell.appendChild(checkbox);

      const termCell = documentRef.createElement("td");
      termCell.textContent = item.term || "";

      const destinationCell = documentRef.createElement("td");
      const select = documentRef.createElement("select");
      (item.destinations || ["ignore"]).forEach((destination) => {
        const option = documentRef.createElement("option");
        option.value = destination;
        option.textContent = renameWorkbenchDestinationLabel(destination);
        select.appendChild(option);
      });
      select.value = item.default_destination || "ignore";
      select.disabled = alreadyFiltered;
      destinationCell.appendChild(select);

      const reasonCell = documentRef.createElement("td");
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
    const get = typeof apiGet === "function" ? apiGet : windowRef.apiGet;
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
          ? "Retesting staged draft filters with production naming plan..."
          : "Testing current draft filters with production naming plan..."
      );
    }
    try {
      const payload = await get(renameWorkbenchPreviewQuery(), { timeoutMs: 10000 });
      state.lastPayload = payload;
      if (payload?.comparison && options.stagedRetest) payload.comparison.policy_label = "current staged Settings filter draft";
      renderRenameWorkbenchPayload(payload);
      renderRenameWorkbenchSuggestions(payload?.filter_suggestions || []);
      const comparisonUnavailable = payload?.comparison?.status === "unavailable";
      setText("settings-rename-workbench-status", comparisonUnavailable ? "Unavailable" : (payload?.comparison?.ok ? "Pass" : "Needs review"));
      if (comparisonUnavailable) {
        state.saveNewFiltersReady = false;
        if (!options.quiet) setText("settings-rename-workbench-message", "Production naming comparison unavailable.");
        setRenameWorkbenchSaveState("Production naming comparison unavailable.", "blocked");
      } else if (options.stagedRetest && payload?.comparison?.ok) {
        if (state.hasStagedSuggestions) {
          const prepared = await saveRenameCleaningFilterState("Retest passed; rename filters are prepared for Save Settings.");
          state.saveNewFiltersReady = Boolean(prepared);
          setText(
            "settings-rename-workbench-message",
            prepared
              ? "Retest passed. Save New Filters is ready."
              : "Retest passed, but the Settings save candidate could not be prepared."
          );
        } else if (!options.quiet) {
          setText("settings-rename-workbench-message", "Retest passed. No new staged suggestions needed.");
        }
        setRenameWorkbenchSaveState(state.saveNewFiltersReady ? "Ready to save new filters." : "Ready for Save Settings.", "ready");
      } else if (options.stagedRetest && !payload?.comparison?.ok) {
        if (!options.quiet) setText("settings-rename-workbench-message", "Retest still needs review; staged terms remain draft-only.");
        state.saveNewFiltersReady = false;
        setRenameWorkbenchSaveState("Not ready: review suggestions and retest.", "needs-review");
      } else {
        state.saveNewFiltersReady = false;
        if (!options.quiet) setText("settings-rename-workbench-message", "Production naming comparison complete.");
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
    if (movieMatch) return documentRef.querySelector(`[data-rename-movie-filter-terms="${movieMatch[1]}"]`);
    const tvMatch = /^tv_filter_terms\.(.+)$/.exec(destination);
    if (tvMatch) return documentRef.querySelector(`[data-rename-tv-filter-terms="${tvMatch[1]}"]`);
    return null;
  }

  function enableRenameWorkbenchDestination(destination) {
    const movieMatch = /^movie_filter_terms\.(.+)$/.exec(destination);
    if (movieMatch) {
      const checkbox = documentRef.querySelector(`[data-rename-movie-filter="${movieMatch[1]}"]`);
      if (checkbox) checkbox.checked = true;
    }
    const tvMatch = /^tv_filter_terms\.(.+)$/.exec(destination);
    if (tvMatch) {
      const checkbox = documentRef.querySelector(`[data-rename-tv-filter="${tvMatch[1]}"]`);
      if (checkbox) checkbox.checked = true;
    }
  }

  function stageRenameWorkbenchSuggestions() {
    const suggestions = Array.isArray(state.lastPayload?.filter_suggestions)
      ? state.lastPayload.filter_suggestions
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
    state.hasStagedSuggestions = staged > 0;
    state.saveNewFiltersReady = false;
    state.lastPayload = null;
    setText("settings-rename-workbench-status", staged ? "Suggestions staged" : "No new terms");
    setText("settings-rename-workbench-message", staged ? "Suggestions are staged in the draft only. Retest with staged filters before Save Settings." : "Selected suggestions were already present or ignored.");
    setRenameWorkbenchSaveState(staged ? "Staged in draft; retest required." : "No new staged terms.", staged ? "staged" : "waiting");
    updateRenameWorkbenchSaveNewFiltersButton();
  }

  function saveRenameWorkbenchNewFilters() {
    if (!state.saveNewFiltersReady) {
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
    if (state.eventsBound) return;
    const form = renameWorkbenchInput("form");
    if (!form) return;
    state.eventsBound = true;
    form.addEventListener("submit", (event) => event.preventDefault());
    renameWorkbenchInput("mode")?.addEventListener("change", () => {
      state.lastPayload = null;
      state.hasStagedSuggestions = false;
      state.saveNewFiltersReady = false;
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


    return {
      renameWorkbenchInput,
      renameWorkbenchValue,
      renameWorkbenchMode,
      setRenameWorkbenchSaveState,
      renameWorkbenchDestinationLabel,
      syncRenameWorkbenchModeFields,
      updateRenameWorkbenchSaveNewFiltersButton,
      setRenameWorkbenchBusy,
      markRenameWorkbenchNeedsTest,
      renameWorkbenchRequiredIssues,
      renameWorkbenchRequest,
      renameWorkbenchPreviewQuery,
      renderRenameWorkbenchPayload,
      renderRenameWorkbenchSuggestionRows,
      renderRenameWorkbenchSuggestions,
      runRenameWorkbenchPreview,
      saveRenameWorkbenchCase,
      appendRenameWorkbenchTerm,
      renameWorkbenchDestinationNode,
      enableRenameWorkbenchDestination,
      stageRenameWorkbenchSuggestions,
      saveRenameWorkbenchNewFilters,
      initRenameWorkbenchEvents,
    };
  }

  window.__renameCleaningWorkbenchModule = { createRenameCleaningWorkbenchModule };
})();
