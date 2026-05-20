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
  let lastRenameRows = [];
  let selectedRenameSourceKey = "";
  const renameFinalOverrides = {};
  const renameForceOverrides = {};
  let lastRenameEmptyMessage = "No rename rows available.";
  let renamePreviewRequestId = 0;
  let activeRenamePreviewRequestId = 0;
  let renamePreviewInFlight = false;
  let renameBrowseInFlight = false;
  let renameApplyInFlight = false;
  const checkedRenameSourceKeys = new Set();

  function collectRenameRequest() {
    const rawPaths = (byId("rename-paths")?.value || "")
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean);
    const movieFilterOptions = {};
    document.querySelectorAll("[data-movie-filter]").forEach((input) => {
      movieFilterOptions[input.dataset.movieFilter || ""] = Boolean(input.checked);
    });
    const editableCleaningFilters = Boolean(byId("rename-use-editable-cleaning-filters")?.checked);
    return {
      paths: rawPaths,
      mode: byId("rename-mode")?.value || "tv",
      template_preset: byId("rename-template-preset")?.value || "",
      show_name: byId("rename-show")?.value || "",
      season: byId("rename-season")?.value || "S01",
      start_episode: byId("rename-start")?.value || "E01",
      movie_title: byId("rename-movie-title")?.value || "",
      movie_year: byId("rename-movie-year")?.value || "",
      remove_terms_text: byId("rename-remove-terms")?.value || "",
      movie_filter_options: movieFilterOptions,
      movie_filter_terms_enabled: editableCleaningFilters,
      movie_filter_terms: editableCleaningFilters ? collectRenameMovieFilterTerms() : {},
      final_name_overrides: { ...renameFinalOverrides },
      rename_sidecars: Boolean(byId("rename-sidecars")?.checked),
      force_pipeline_name: Boolean(byId("rename-force-pipeline")?.checked),
      force_pipeline_name_overrides: { ...renameForceOverrides },
      use_pipeline_naming_preview: Boolean(byId("rename-pipeline-preview")?.checked),
    };
  }

  function renameCleaningFilterTextareas() {
    return Array.from(document.querySelectorAll("[data-movie-filter-terms]"));
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
      const key = input.dataset.movieFilterTerms || "";
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
      use_editable_filters: Boolean(byId("rename-use-editable-cleaning-filters")?.checked),
      remove_terms_text: byId("rename-remove-terms")?.value || "",
      movie_filter_terms_text: collectRenameMovieFilterTermsText(),
    };
  }

  function renderRenameCleaningFilterEditor(message = "") {
    const editable = Boolean(byId("rename-use-editable-cleaning-filters")?.checked);
    const movieTerms = collectRenameMovieFilterTerms();
    const categoryCounts = Object.entries(movieTerms)
      .map(([key, values]) => `${key.replace(/_/g, " ")}=${values.length}`)
      .join("; ");
    const customTermsCount = parseRenameFilterTerms(byId("rename-remove-terms")?.value || "").length;
    setText("rename-cleaning-filter-status", editable ? "Editable terms" : "Backend built-ins");
    setText("rename-cleaning-filter-summary", [
      message,
      `Custom negative terms: ${customTermsCount}`,
      editable ? `Editable movie filters: ${categoryCounts || "none"}` : "Movie filters: backend built-in regex/categories",
      editable ? "Preview request will replace enabled built-in movie filter categories with these literal terms." : "Enable editable terms to replace built-in movie filter categories for preview.",
      "Mutation guardrail: editing cleaning filters changes rename preview/apply planning only; filesystem changes still require backend rename apply confirmation.",
    ].filter(Boolean).join("\n"));
  }

  function saveRenameCleaningFilterState() {
    try {
      localStorage.setItem(RENAME_CLEANING_FILTER_STORAGE_KEY, JSON.stringify(renameCleaningFilterState()));
      renderRenameCleaningFilterEditor("Cleaning filters saved for this browser.");
    } catch (_) {
      renderRenameCleaningFilterEditor("Cleaning filters could not be saved in browser storage.");
    }
  }

  function resetRenameCleaningFilters() {
    const removeTerms = byId("rename-remove-terms");
    if (removeTerms) removeTerms.value = removeTerms.dataset.defaultTerms || "sample, trailer, extras, featurette, deleted scenes, behind the scenes";
    const editableToggle = byId("rename-use-editable-cleaning-filters");
    if (editableToggle) editableToggle.checked = false;
    renameCleaningFilterTextareas().forEach((input) => {
      input.value = input.dataset.defaultTerms || "";
    });
    try { localStorage.removeItem(RENAME_CLEANING_FILTER_STORAGE_KEY); } catch (_) {}
    renderRenameCleaningFilterEditor("Cleaning filters reset to defaults.");
    syncRenameCommandButtons();
  }

  function loadRenameCleaningFilterState() {
    let state = null;
    try { state = JSON.parse(localStorage.getItem(RENAME_CLEANING_FILTER_STORAGE_KEY) || "null"); } catch (_) { state = null; }
    if (!state || typeof state !== "object") {
      renderRenameCleaningFilterEditor();
      return;
    }
    const editableToggle = byId("rename-use-editable-cleaning-filters");
    if (editableToggle) editableToggle.checked = Boolean(state.use_editable_filters);
    const removeTerms = byId("rename-remove-terms");
    if (removeTerms && typeof state.remove_terms_text === "string") removeTerms.value = state.remove_terms_text;
    const textByKey = state.movie_filter_terms_text && typeof state.movie_filter_terms_text === "object"
      ? state.movie_filter_terms_text
      : {};
    renameCleaningFilterTextareas().forEach((input) => {
      const key = input.dataset.movieFilterTerms || "";
      if (Object.prototype.hasOwnProperty.call(textByKey, key)) input.value = String(textByKey[key] || "");
    });
    renderRenameCleaningFilterEditor("Cleaning filters loaded from browser storage.");
  }

  function initRenameCleaningFilterEditorEvents() {
    loadRenameCleaningFilterState();
    const editableToggle = byId("rename-use-editable-cleaning-filters");
    if (editableToggle) editableToggle.addEventListener("change", () => {
      renderRenameCleaningFilterEditor();
      syncRenameCommandButtons();
    });
    const removeTerms = byId("rename-remove-terms");
    if (removeTerms) removeTerms.addEventListener("input", () => {
      renderRenameCleaningFilterEditor();
      syncRenameCommandButtons();
    });
    renameCleaningFilterTextareas().forEach((input) => {
      input.addEventListener("input", () => {
        renderRenameCleaningFilterEditor();
        syncRenameCommandButtons();
      });
    });
    const saveButton = byId("rename-cleaning-filters-save-button");
    if (saveButton) saveButton.addEventListener("click", saveRenameCleaningFilterState);
    const resetButton = byId("rename-cleaning-filters-reset-button");
    if (resetButton) resetButton.addEventListener("click", resetRenameCleaningFilters);
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

  function renderRenameFileSourceSummary(message = "") {
    const paths = renameCurrentPathValues();
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
      `Loaded Queue rows: ${Array.isArray(queueRows) ? queueRows.length : 0}`,
      `Selected Queue source: ${selectedPath || "(none)"}`,
      paths.length ? `First staged path: ${paths[0]}` : "",
    ].filter(Boolean).join("\n"));
  }

  function appendRenamePaths(paths, sourceLabel) {
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
    renderRenameFileSourceSummary(`${sourceLabel || "Source"} added ${additions.length} path${additions.length === 1 ? "" : "s"}.`);
    syncRenameCommandButtons();
    return additions.length;
  }

  function addRenamePathFromInput() {
    const input = byId("rename-add-path-input");
    const path = String(input?.value || "").trim();
    if (!path) {
      renderRenameFileSourceSummary("Enter or paste a source path, then click Add Path.");
      return 0;
    }
    const added = appendRenamePaths([path], "Manual path");
    if (added && input) input.value = "";
    syncRenameCommandButtons();
    return added;
  }

  async function browseRenamePaths(selectionMode = "files") {
    if (renameBrowseInFlight || renamePreviewInFlight || renameApplyInFlight) {
      renderRenameFileSourceSummary("Rename path browser is busy. Wait for the current Rename command to finish.");
      return;
    }
    const mode = String(selectionMode || "").toLowerCase() === "folder" ? "folder" : "files";
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
      appendRenamePaths(paths, mode === "folder" ? "Windows folder browser" : "Windows file browser");
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
    appendRenamePaths([path], renameSourceLabelFromRow(row) || "Selected Queue row");
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
    appendRenamePaths(paths, "Loaded Queue rows");
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

  function renamePreviewAggregateObject(preview, aggregateKey, rowKey) {
    const aggregate = preview?.[aggregateKey];
    if (aggregate && typeof aggregate === "object" && !Array.isArray(aggregate) && Object.keys(aggregate).length) {
      return aggregate;
    }
    const rows = Array.isArray(preview?.rows) ? preview.rows : [];
    return rows.reduce((acc, row) => {
      const key = String(row?.[rowKey] || "unknown").trim() || "unknown";
      acc[key] = (acc[key] || 0) + 1;
      return acc;
    }, {});
  }

  function renameFormatCounts(counts, labeler = null) {
    if (!counts || typeof counts !== "object") return "none";
    const parts = Object.keys(counts)
      .sort()
      .map((key) => `${labeler ? labeler(key) : key}: ${counts[key]}`);
    return parts.length ? parts.join(", ") : "none";
  }

  function renameTemplateLabel(preview, key) {
    const catalog = Array.isArray(preview?.template_catalog) ? preview.template_catalog : [];
    const match = catalog.find((item) => item && item.key === key);
    return match ? `${match.label || match.key}: ${match.description || ""}`.trim() : (key || "Backend default");
  }

  function renameDuplicateTargets(rows) {
    const seen = {};
    rows.forEach((row) => {
      const key = String(row.destination || row.target_name || "").trim().toLowerCase();
      if (!key) return;
      seen[key] = (seen[key] || 0) + 1;
    });
    return Object.keys(seen).filter((key) => seen[key] > 1);
  }

  function renameReviewBoardStatus(preview) {
    const rows = Array.isArray(preview?.rows) ? preview.rows : [];
    if (!rows.length) return "No preview";
    const counts = preview?.counts || {};
    const confidenceCounts = renamePreviewAggregateObject(preview, "confidence_counts", "confidence");
    if ((counts.blocked || 0) > 0) return "Blocked";
    if ((counts.warning || 0) > 0) return "Review warnings";
    if ((confidenceCounts.blocked || 0) > 0 || (confidenceCounts.low || 0) > 0 || (confidenceCounts.unknown || 0) > 0) return "Review confidence";
    if ((confidenceCounts.medium || 0) > 0) return "Verify";
    return "Ready";
  }

  function renameReviewBoardLines(preview) {
    const request = collectRenameRequest();
    const rows = Array.isArray(preview?.rows) ? preview.rows : [];
    const counts = preview?.counts || {};
    if (!rows.length) {
      return [
        "No rename preview rows loaded.",
        "Next step: add one file path per line and run Preview.",
        "Mutation guardrail: this board is read-only; Apply Checked / Selected still uses the backend selected_sources command.",
      ];
    }
    const confidenceCounts = renamePreviewAggregateObject(preview, "confidence_counts", "confidence");
    const sourceCounts = renamePreviewAggregateObject(preview, "preview_source_counts", "preview_source");
    const changeCounts = renamePreviewAggregateObject(preview, "change_kind_counts", "change_kind");
    const warningRows = rows.filter((row) => Array.isArray(row.warnings) && row.warnings.length).length;
    const errorRows = rows.filter((row) => Array.isArray(row.errors) && row.errors.length).length;
    const sidecarMoves = rows.reduce((acc, row) => acc + Number(row.sidecar_count || 0), 0);
    const forcedRows = rows.filter((row) => Boolean(row.force_pipeline_name)).length;
    const overrideRows = rows.filter((row) => Boolean(row.final_name_override || renameFinalOverrides[renameSourceKey(row)])).length;
    const duplicates = renameDuplicateTargets(rows);
    const firstTarget = rows[0]?.target_name || rows[0]?.destination || "";
    const lastTarget = rows[rows.length - 1]?.target_name || rows[rows.length - 1]?.destination || "";
    const lines = [
      "Preview-wide review board. This is read-only; Apply Checked / Selected still calls the backend rename.apply command.",
      `Template: ${renameTemplateLabel(preview, preview?.active_template || request.template_preset || "")}`,
      `Rows/status: ${counts.total || rows.length} total; ready ${counts.ready || 0}, match ${counts.match || 0}, warning ${counts.warning || 0}, blocked ${counts.blocked || 0}`,
      `Confidence mix: ${renameFormatCounts(confidenceCounts)}`,
      `Source-of-truth signals: ${renameFormatCounts(sourceCounts, renamePreviewSourceLabel)}`,
      `Change kinds: ${renameFormatCounts(changeCounts)}`,
      `Review flags: ${warningRows} row(s) with warnings, ${errorRows} row(s) with errors, ${duplicates.length} duplicate destination target(s)`,
      `Sidecars/forcing: ${sidecarMoves} sidecar move(s) planned, ${forcedRows} force-pipeline row(s), ${overrideRows} final-name override row(s)`,
    ];
    if (request.mode === "movie") {
      lines.push(
        `Movie seeds: title '${request.movie_title || "(scrub/backend)"}', year '${request.movie_year || "(scrub/backend)"}'`,
        "Movie review: compare Current, Scrubbed / Pipeline, and Final before forcing a pipeline name."
      );
    } else {
      lines.push(
        `TV seeds: show '${request.show_name || "(auto/backend)"}', season '${request.season || "(auto/backend)"}', start '${request.start_episode || "(auto/backend)"}'`,
        `TV range: first target '${firstTarget || "(none)"}'; last target '${lastTarget || "(none)"}'`,
        "TV review: verify row order before applying because numbering follows the current Paths textarea order."
      );
    }
    if (duplicates.length) {
      lines.push(`Duplicate target examples: ${duplicates.slice(0, 3).join(" | ")}`);
    }
    if (Array.isArray(preview?.warnings) && preview.warnings.length) {
      lines.push(`Preview warnings: ${preview.warnings.join(" | ")}`);
    }
    lines.push("Backend rename preview/apply remains the source of truth for filesystem changes.");
    return lines;
  }

  function renderRenameReviewBoard(preview) {
    setText("rename-review-board-status", renameReviewBoardStatus(preview || {}));
    setText("rename-review-board", renameReviewBoardLines(preview || {}).join("\n"));
  }

  function renderRenameSummary(preview) {
    const rows = Array.isArray(preview?.rows) ? preview.rows : [];
    if (!rows.length) {
      const warning = Array.isArray(preview?.warnings) && preview.warnings.length ? `\nWarnings: ${preview.warnings.join(" | ")}` : "";
      setText("rename-summary", `${lastRenameEmptyMessage}${warning}`);
      renderRenameBatchSafety(preview);
      renderRenamePipelineHandoff(preview);
      renderRenameReviewBoard(preview);
      return;
    }
    const counts = preview.counts || {};
    const confidenceCounts = renamePreviewAggregateObject(preview, "confidence_counts", "confidence");
    const sourceCounts = renamePreviewAggregateObject(preview, "preview_source_counts", "preview_source");
    const guidance = [
      `Rows: ${counts.total || rows.length}; ready: ${counts.ready || 0}; match: ${counts.match || 0}; warning: ${counts.warning || 0}; blocked: ${counts.blocked || 0}`,
      `Confidence: ${renameFormatCounts(confidenceCounts)}`,
      `Preview source: ${renameFormatCounts(sourceCounts, renamePreviewSourceLabel)}`,
      "Select a row to inspect confidence reasons, warnings, sidecar moves, and force-pipeline behavior before applying.",
      "Checked-row apply still rebuilds the plan through the backend and mutates only explicit selected_sources.",
    ];
    if (Array.isArray(preview.warnings) && preview.warnings.length) {
      guidance.push(`Preview warnings: ${preview.warnings.join(" | ")}`);
    }
    setText("rename-summary", guidance.join("\n"));
    renderRenameBatchSafety(preview);
    renderRenamePipelineHandoff(preview);
    renderRenameReviewBoard(preview);
  }

  function renameBatchSafetyLines(preview) {
    const request = collectRenameRequest();
    const rows = Array.isArray(preview?.rows) ? preview.rows : [];
    const counts = preview?.counts || {};
    const overrides = Object.keys(renameFinalOverrides).length;
    const forceOverrides = Object.keys(renameForceOverrides).filter((key) => renameForceOverrides[key]).length;
    const lines = [
      `Mode: ${request.mode === "movie" ? "Movie" : "TV"}`,
      `Input paths: ${request.paths.length}; preview rows: ${rows.length}`,
      `Rendered preview rows: ${renameRenderedRowsCount(rows)} of ${rows.length}`,
      `Apply scope: checked rows are sent as selected_sources; if none are checked, Apply uses only the selected detail row.`,
      `Sidecars: ${request.rename_sidecars ? "rename sidecar preview enabled" : "sidecar rename preview disabled"}`,
      `Pipeline naming preview: ${request.use_pipeline_naming_preview ? "preferred when backend can provide it" : "disabled"}`,
      `Global force pipeline name: ${request.force_pipeline_name ? "enabled" : "disabled"}`,
      `Overrides staged: ${overrides} final-name override(s), ${forceOverrides} force-through-pipeline override(s)`,
      `Status counts: ready ${counts.ready || 0}, match ${counts.match || 0}, warning ${counts.warning || 0}, blocked ${counts.blocked || 0}`,
      `Checked rows: ${getCheckedRenameRows().length}`,
    ];
    if (request.mode !== "movie") {
      lines.push(
        `TV sequence seed: show '${request.show_name || "(auto/backend)"}', season '${request.season || "(auto/backend)"}', start '${request.start_episode || "(auto/backend)"}'`,
        "TV ordering: backend preview follows the current Paths textarea order. Verify SxxEyy rows before checking and applying batch renames."
      );
    } else {
      lines.push(
        `Movie seed: title '${request.movie_title || "(scrub/backend)"}', year '${request.movie_year || "(scrub/backend)"}'`,
        "Movie safety: forced names should be reviewed against the scrubbed/pipeline guess before applying."
      );
    }
    if ((counts.blocked || 0) > 0) {
      lines.push("Blocked rows will not apply until backend errors are fixed.");
    }
    if ((counts.warning || 0) > 0) {
      lines.push("Warning rows can apply, but inspect row details before changing files.");
    }
    if (!rows.length) {
      lines.push("No preview rows are available yet. Add paths and run Preview.");
    } else if (rows.length > RENAME_PREVIEW_RENDER_LIMIT) {
      lines.push(`Display cap: only ${RENAME_PREVIEW_RENDER_LIMIT} rows are rendered, but Check Applicable Rows and Apply scope use the full backend preview row set.`);
    }
    lines.push("Backend rename preview/apply remains the source of truth for filesystem changes.");
    return lines;
  }

  function renderRenameBatchSafety(preview) {
    setText("rename-batch-safety", renameBatchSafetyLines(preview || {}).join("\n"));
  }

  function renameSavedSettingsConfig() {
    const settings = typeof getLastSettings === "function" ? getLastSettings() : {};
    return settings && typeof settings.config === "object" && settings.config ? settings.config : {};
  }

  function renameConfigValue(config, key, fallback = "(not set)") {
    const value = config && Object.prototype.hasOwnProperty.call(config, key) ? config[key] : undefined;
    if (Array.isArray(value)) return value.join(", ") || fallback;
    if (value === true) return "true";
    if (value === false) return "false";
    if (value === null || value === undefined || value === "") return fallback;
    return String(value);
  }

  function renameExtensionName(name) {
    const value = String(name || "").trim();
    const dotIndex = value.lastIndexOf(".");
    return dotIndex >= 0 ? value.slice(dotIndex).toLowerCase() : "";
  }

  function renamePipelineHandoffStatus(preview) {
    const rows = Array.isArray(preview?.rows) ? preview.rows : [];
    if (!rows.length) return "No preview";
    const config = renameSavedSettingsConfig();
    if (!Object.keys(config).length) return "Settings not loaded";
    const request = collectRenameRequest();
    const confidenceCounts = renamePreviewAggregateObject(preview, "confidence_counts", "confidence");
    const forceRows = rows.filter((row) => Boolean(row.force_pipeline_name)).length;
    const overrideRows = rows.filter((row) => Boolean(row.final_name_override || renameFinalOverrides[renameSourceKey(row)])).length;
    const targetExtensions = new Set(rows.map((row) => renameExtensionName(row.target_name || row.destination || "")).filter(Boolean));
    if ((preview?.counts || {}).blocked > 0) return "Blocked";
    if (forceRows || overrideRows || !request.rename_sidecars) return "Review";
    if ((confidenceCounts.low || 0) || (confidenceCounts.unknown || 0) || (confidenceCounts.medium || 0)) return "Review confidence";
    if (targetExtensions.size > 1) return "Mixed extensions";
    return "Ready";
  }

  function renamePipelineHandoffLines(preview) {
    const rows = Array.isArray(preview?.rows) ? preview.rows : [];
    const request = collectRenameRequest();
    const config = renameSavedSettingsConfig();
    if (!rows.length) {
      return [
        "No rename preview rows loaded.",
        "Run Preview to compare target names against saved pipeline routing and sidecar/force-name behavior.",
        "Mutation guardrail: this handoff is read-only and cannot rename, save settings, launch work, remux, encode, publish, rewrite sidecars, or touch media files.",
      ];
    }
    const counts = preview?.counts || {};
    const confidenceCounts = renamePreviewAggregateObject(preview, "confidence_counts", "confidence");
    const sourceCounts = renamePreviewAggregateObject(preview, "preview_source_counts", "preview_source");
    const forceRows = rows.filter((row) => Boolean(row.force_pipeline_name)).length;
    const finalOverrideRows = rows.filter((row) => Boolean(row.final_name_override || renameFinalOverrides[renameSourceKey(row)])).length;
    const sidecarMoves = rows.reduce((acc, row) => acc + Number(row.sidecar_count || 0), 0);
    const sourceExtensions = new Set(rows.map((row) => renameExtensionName(row.source_name || row.source || "")).filter(Boolean));
    const targetExtensions = new Set(rows.map((row) => renameExtensionName(row.target_name || row.destination || "")).filter(Boolean));
    const lines = [
      "Rename-to-pipeline handoff:",
      `Preview rows: ${rows.length}; ready=${counts.ready || 0}; match=${counts.match || 0}; warning=${counts.warning || 0}; blocked=${counts.blocked || 0}`,
      `Mode/template: ${request.mode === "movie" ? "Movie" : "TV"} / ${renameTemplateLabel(preview, preview?.active_template || request.template_preset || "")}`,
      `Confidence mix: ${renameFormatCounts(confidenceCounts)}`,
      `Source-of-truth signals: ${renameFormatCounts(sourceCounts, renamePreviewSourceLabel)}`,
      `Saved routing profile: ${renameConfigValue(config, "RoutingProfile")}; size guard: ${renameConfigValue(config, "SizeGuardMode")}; output container: ${renameConfigValue(config, "OutputContainer")}`,
      `Saved subtitle posture: TX3G convert=${renameConfigValue(config, "ConvertTx3gToSrt")}, drop=${renameConfigValue(config, "DropTx3gAfterConversion")}; BDPGS convert=${renameConfigValue(config, "ConvertBdpgsToSrt")}, drop=${renameConfigValue(config, "DropBdpgsAfterConversion")}; ASS drop=${renameConfigValue(config, "DropAssAfterConversion")}`,
      `Saved publish posture: deferred publish=${renameConfigValue(config, "DeferredPublish")}; source delete=${renameConfigValue(config, "DeleteSourceAfterProcessing", "false")}`,
      `Filename extensions: source=${Array.from(sourceExtensions).join(", ") || "unknown"}; target=${Array.from(targetExtensions).join(", ") || "unknown"}`,
      `Sidecar/force state: sidecar preview ${request.rename_sidecars ? "enabled" : "disabled"}; planned sidecar move(s) ${sidecarMoves}; force-pipeline row(s) ${forceRows}; final-name override row(s) ${finalOverrideRows}`,
    ];
    lines.push("");
    if (!Object.keys(config).length) {
      lines.push("Operator check: saved settings are not loaded in this WebView session. Refresh before trusting routing/container/subtitle handoff text.");
    } else {
      lines.push("Operator check: renaming changes filenames only. It does not convert containers, change codecs, remux, encode, OCR subtitles, publish, or make staged Settings JSON active.");
    }
    if (String(config.OutputContainer || "").toLowerCase() === "mp4") {
      lines.push("Container note: saved OutputContainer is MP4. MP4 cannot preserve every subtitle format, so subtitle drop/convert settings matter during pipeline processing even if rename preview looks clean.");
    } else {
      lines.push("Container note: filename extension here is not proof of final mux container; the pipeline output container is governed by saved backend settings at processing time.");
    }
    if (forceRows) {
      lines.push("Force-name note: force-pipeline rows can affect future pipeline destination planning through backend sidecar/override behavior. Confirm Final names are Plex-ready before applying.");
    }
    if (finalOverrideRows) {
      lines.push("Override note: final-name overrides are explicit operator choices. Compare them with Scrubbed / Pipeline before applying.");
    }
    if (!request.rename_sidecars) {
      lines.push("Sidecar note: sidecar rename preview is disabled. Post-processing renames may leave associated sidecars behind unless the backend apply request is intentionally scoped that way.");
    }
    if ((confidenceCounts.low || 0) || (confidenceCounts.unknown || 0) || (confidenceCounts.medium || 0)) {
      lines.push("Confidence note: one or more rows are below high confidence. Inspect row detail before applying to avoid bad Plex naming or wrong TV numbering.");
    }
    lines.push("Mutation guardrail: this handoff is read-only. Apply Checked / Selected still rebuilds the plan and mutates files only through backend rename.apply selected_sources.");
    return lines;
  }

  function renderRenamePipelineHandoff(preview) {
    setText("rename-pipeline-handoff-status", renamePipelineHandoffStatus(preview || {}));
    setText("rename-pipeline-handoff", renamePipelineHandoffLines(preview || {}).join("\n"));
  }

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
      "Mutation guardrail: this panel stages preview overrides only. Apply Checked / Selected still calls backend rename.apply with selected_sources.",
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

  function renameApplyScopeRows() {
    const checked = getCheckedRenameRows();
    if (checked.length) return { rows: checked, source: "checked rows" };
    const selected = getSelectedRenameRow();
    return selected ? { rows: [selected], source: "selected row" } : { rows: [], source: "none" };
  }

  function renameSelectionAuditStatus(rows) {
    if (!rows.length) return "No selection";
    const blocked = rows.filter((row) => !renameRowCanApply(row)).length;
    const warning = rows.filter((row) => String(row.status || "").toLowerCase() === "warning").length;
    const match = rows.filter((row) => String(row.status || "").toLowerCase() === "match").length;
    if (blocked) return "Blocked";
    if (warning) return "Review warnings";
    if (match === rows.length) return "All match";
    return "Ready";
  }

  function renameSelectionDuplicateTargets(rows) {
    return renameDuplicateTargets(rows);
  }

  function renameApplyScopeBlockers(rows) {
    const scopedRows = Array.isArray(rows) ? rows : [];
    const duplicateTargets = renameDuplicateTargets(scopedRows);
    const destinationExistsRows = scopedRows.filter((row) => Boolean(row.destination_exists) && !row.matches_target);
    const blockers = [];
    if (duplicateTargets.length) {
      blockers.push(`duplicate destination target(s): ${duplicateTargets.slice(0, 3).join(" | ")}`);
    }
    if (destinationExistsRows.length) {
      blockers.push(`${destinationExistsRows.length} existing destination path(s) outside match/no-op rows`);
    }
    return blockers;
  }

  function renderRenameSelectionAudit() {
    const scope = renameApplyScopeRows();
    const rows = scope.rows;
    const renderedRows = renameRenderedRowsCount();
    setText("rename-selection-audit-status", renameSelectionAuditStatus(rows));
    if (!rows.length) {
      setText("rename-selection-audit", [
        "Apply scope: none",
        "Next step: check one or more applicable rows, or select a single row, before applying.",
        "Mutation guardrail: Apply still rebuilds the selected plan through the backend.",
      ].join("\n"));
      return;
    }
    const counts = rows.reduce((acc, row) => {
      const status = String(row.status || "unknown").toLowerCase();
      const change = String(row.change_kind || "unknown").toLowerCase();
      acc.status[status] = (acc.status[status] || 0) + 1;
      acc.change[change] = (acc.change[change] || 0) + 1;
      if (row.force_pipeline_name) acc.force += 1;
      acc.sidecars += Number(row.sidecar_count || 0);
      return acc;
    }, { status: {}, change: {}, force: 0, sidecars: 0 });
    const duplicates = renameSelectionDuplicateTargets(rows);
    const warnings = rows.flatMap((row) => Array.isArray(row.warnings) ? row.warnings : []);
    const errors = rows.flatMap((row) => Array.isArray(row.errors) ? row.errors : []);
    const lines = [
      `Apply scope: ${scope.source}`,
      `Rows in scope: ${rows.length}`,
      `Rendered rows: ${renderedRows} of ${lastRenameRows.length}`,
      `Statuses: ready ${counts.status.ready || 0}, match ${counts.status.match || 0}, warning ${counts.status.warning || 0}, blocked ${counts.status.blocked || 0}`,
      `Actions: rename ${counts.change.rename || 0}, case-only ${counts.change.case_only || 0}, unchanged ${counts.change.unchanged || 0}, blocked ${counts.change.blocked || 0}`,
      `Sidecar moves planned: ${counts.sidecars}`,
      `Force pipeline override rows: ${counts.force}`,
      `First source: ${rows[0]?.source_name || rows[0]?.source || ""}`,
      `Last source: ${rows[rows.length - 1]?.source_name || rows[rows.length - 1]?.source || ""}`,
    ];
    if (duplicates.length) lines.push(`Duplicate destination(s) in scope: ${duplicates.length}`);
    if (errors.length) lines.push(`Errors: ${errors.slice(0, 4).join(" | ")}`);
    if (warnings.length) lines.push(`Warnings: ${warnings.slice(0, 4).join(" | ")}`);
    if (lastRenameRows.length > RENAME_PREVIEW_RENDER_LIMIT) {
      lines.push("Render cap note: checked scope may include rows not currently rendered; Apply uses backend selected_sources for checked rows, not visible table rows only.");
    }
    lines.push("Next step: if the audit looks correct, Apply sends only this scope as backend selected_sources.");
    lines.push("Mutation guardrail: no frontend filesystem mutation is performed.");
    setText("rename-selection-audit", lines.join("\n"));
  }

  function renameApplyReadinessRow(checkpoint, posture, evidence, operatorCheck) {
    return {
      checkpoint,
      posture,
      evidence,
      operator_check: operatorCheck,
    };
  }

  function renameApplyReadinessRows() {
    const request = collectRenameRequest();
    const scope = renameApplyScopeRows();
    const rows = scope.rows;
    const previewCount = lastRenameRows.length;
    const renderedCount = renameRenderedRowsCount();
    const blockedRows = rows.filter((row) => !renameRowCanApply(row));
    const warningRows = rows.filter((row) => String(row.status || "").toLowerCase() === "warning");
    const matchRows = rows.filter((row) => String(row.status || "").toLowerCase() === "match");
    const duplicateTargets = renameDuplicateTargets(rows);
    const destinationExistsRows = rows.filter((row) => Boolean(row.destination_exists) && !row.matches_target);
    const sidecarMoves = rows.reduce((acc, row) => acc + Number(row.sidecar_count || 0), 0);
    const forceRows = rows.filter((row) => Boolean(row.force_pipeline_name)).length;
    const finalOverrideRows = rows.filter((row) => Boolean(row.final_name_override || renameFinalOverrides[renameSourceKey(row)])).length;
    const firstTarget = rows[0]?.target_name || rows[0]?.destination || "";
    const lastTarget = rows[rows.length - 1]?.target_name || rows[rows.length - 1]?.destination || "";
    const readinessRows = [];

    readinessRows.push(renameApplyReadinessRow(
      "Backend preview",
      previewCount ? "ready" : "waiting",
      previewCount ? `${previewCount} backend preview row(s) loaded.` : "No backend preview rows loaded.",
      previewCount ? "Review Current, Scrubbed / Pipeline, Final, confidence, and status before apply." : "Add paths and run Preview before applying any rename.",
    ));
    readinessRows.push(renameApplyReadinessRow(
      "Render cap visibility",
      previewCount > RENAME_PREVIEW_RENDER_LIMIT ? "review" : (previewCount ? "ready" : "waiting"),
      previewCount ? `${renderedCount} of ${previewCount} preview row(s) are rendered; ${getCheckedRenameRows().length} checked row(s).` : "No preview rows are rendered.",
      previewCount > RENAME_PREVIEW_RENDER_LIMIT ? "Use Selection Audit and checked count; applying checked rows can include unrendered backend preview rows after Check Applicable Rows." : "All backend preview rows are visible in the current table render.",
    ));
    readinessRows.push(renameApplyReadinessRow(
      "Apply scope",
      rows.length ? "ready" : "blocked",
      `${scope.source}; ${rows.length} row(s) would be submitted as backend selected_sources.`,
      rows.length ? "Confirm this is the intended batch. Checked rows win; otherwise the selected row is used." : "Check applicable rows or select one row before applying.",
    ));
    readinessRows.push(renameApplyReadinessRow(
      "Blocked rows",
      blockedRows.length ? "blocked" : "ready",
      `${blockedRows.length} blocked/non-applicable row(s) in current apply scope.`,
      blockedRows.length ? "Fix preview errors before applying. Blocked rows are not safe to send to rename.apply." : "No blocked rows in the selected apply scope.",
    ));
    readinessRows.push(renameApplyReadinessRow(
      "Duplicate destinations",
      duplicateTargets.length ? "blocked" : "ready",
      duplicateTargets.length ? `${duplicateTargets.length} duplicate target(s): ${duplicateTargets.slice(0, 3).join(" | ")}` : "No duplicate destinations inside the current apply scope.",
      duplicateTargets.length ? "Change row order, overrides, or template before applying to avoid collisions." : "Batch destinations are unique within this preview scope.",
    ));
    readinessRows.push(renameApplyReadinessRow(
      "Existing destinations",
      destinationExistsRows.length ? "blocked" : "ready",
      `${destinationExistsRows.length} target path(s) already exist outside a match/no-op row.`,
      destinationExistsRows.length ? "Inspect row errors/warnings and choose a unique final name before applying." : "No existing destination collision is reported in the current scope.",
    ));
    readinessRows.push(renameApplyReadinessRow(
      "Warnings and matches",
      warningRows.length ? "review" : "ready",
      `${warningRows.length} warning row(s), ${matchRows.length} match/no-op row(s).`,
      warningRows.length ? "Open selected-row detail and review warning text before applying." : "Warnings are not present in the current apply scope.",
    ));
    const outsideRootRows = rows.filter((row) => row.path_authority === "outside_configured_roots");
    readinessRows.push(renameApplyReadinessRow(
      "Path authority",
      outsideRootRows.length ? "review" : "ready",
      outsideRootRows.length
        ? `${outsideRootRows.length} selected row(s) are outside configured SourceMovies, SourceTV, or output roots.`
        : "Selected rows are inside configured media roots or no backend root scope was reported.",
      outsideRootRows.length
        ? "Browser confirmation must include outside-root review before backend rename.apply accepts standalone paths."
        : "Continue comparing exact source and destination paths before applying.",
    ));

    if (request.mode === "movie") {
      readinessRows.push(renameApplyReadinessRow(
        "Movie scrub review",
        rows.length ? "review" : "waiting",
        `Movie seed title='${request.movie_title || "(scrub/backend)"}', year='${request.movie_year || "(scrub/backend)"}'.`,
        "Compare source name, scrubbed/pipeline guess, and final name before forcing pipeline names.",
      ));
    } else {
      readinessRows.push(renameApplyReadinessRow(
        "TV ordering review",
        rows.length > 1 ? "review" : rows.length ? "ready" : "waiting",
        `TV seed show='${request.show_name || "(auto/backend)"}', season='${request.season || "(auto/backend)"}', start='${request.start_episode || "(auto/backend)"}'; first='${firstTarget || "(none)"}'; last='${lastTarget || "(none)"}'.`,
        rows.length > 1 ? "Verify row order before apply because backend numbering follows the Paths textarea order." : "Single-row TV apply has no batch-order numbering risk.",
      ));
    }

    readinessRows.push(renameApplyReadinessRow(
      "Sidecars and pipeline force",
      sidecarMoves || forceRows || finalOverrideRows || !request.rename_sidecars ? "review" : "ready",
      `${sidecarMoves} sidecar move(s); ${forceRows} force-pipeline row(s); ${finalOverrideRows} final-name override row(s); sidecar preview ${request.rename_sidecars ? "enabled" : "disabled"}.`,
      "Confirm sidecar and force settings match pre/post-processing intent before mutation.",
    ));
    readinessRows.push(renameApplyReadinessRow(
      "Mutation boundary",
      "ready",
      "Apply posts confirm_apply plus selected_sources to /api/rename/apply; the frontend does not rename files.",
      "Use the browser confirmation and Last Apply Result/command history to verify backend outcome.",
    ));
    return readinessRows;
  }

  function renameApplyReadinessStatus(rows) {
    const items = Array.isArray(rows) ? rows : renameApplyReadinessRows();
    if (!lastRenameRows.length || !renameApplyScopeRows().rows.length) return "No scope";
    const postures = new Set(items.map((row) => String(row.posture || "").toLowerCase()));
    if (postures.has("blocked")) return "Blocked";
    if (postures.has("waiting")) return "No scope";
    if (postures.has("review")) return "Review";
    return "Ready";
  }

  function renderRenameApplyReadiness() {
    const rows = renameApplyReadinessRows();
    const tbody = byId("rename-apply-readiness-rows");
    setText("rename-apply-readiness-status", renameApplyReadinessStatus(rows));
    if (!tbody) return;
    tbody.replaceChildren();
    rows.forEach((item) => {
      const row = document.createElement("tr");
      row.dataset.status = item.posture || "";
      appendCells(row, [item.checkpoint, item.posture, item.evidence, item.operator_check]);
      tbody.appendChild(row);
    });
    const counts = rows.reduce((acc, item) => {
      const key = String(item.posture || "unknown").toLowerCase();
      acc[key] = (acc[key] || 0) + 1;
      return acc;
    }, {});
    const countText = Object.keys(counts).sort().map((key) => `${key}=${counts[key]}`).join(", ");
    setText("rename-apply-readiness-legend", `Rename apply readiness: ${countText || "none"}. Read-only; backend rename.apply remains the only filesystem mutation path.`);
  }

  function renderRenameDetail(item) {
    if (!item) {
      setText("rename-detail", "No rename row selected. Select a preview row to inspect confidence, source logic, warnings, sidecar moves, and exact destination.");
      return;
    }
    const warnings = Array.isArray(item.warnings) ? item.warnings : [];
    const errors = Array.isArray(item.errors) ? item.errors : [];
    const confidenceReasons = Array.isArray(item.confidence_reasons) ? item.confidence_reasons : [];
    const sidecarMoves = Array.isArray(item.sidecar_moves) ? item.sidecar_moves : [];
    const detail = [
      `Source: ${item.source || ""}`,
      `Destination: ${item.destination || ""}`,
      `Source folder: ${item.source_parent || ""}`,
      `Destination folder: ${item.destination_parent || ""}`,
      `Pipeline guess: ${item.pipeline_guess || ""}`,
      `Final: ${item.target_name || ""}`,
      `Template: ${item.template_preset || ""}`,
      `Change kind: ${item.change_kind || ""}`,
      `Status: ${item.status || ""}`,
      `Status meaning: ${renameStatusExplanation(item.status)}`,
      `Confidence: ${renameConfidenceLabel(item) || "not reported"}`,
      `Confidence meaning: ${renameConfidenceExplanation(item.confidence)}`,
      confidenceReasons.length ? `Confidence reason(s): ${confidenceReasons.join(" | ")}` : "",
      `Path authority: ${item.path_authority || "not reported"} (${item.path_authority_message || "no backend authority note"})`,
      `Force pipeline name: ${item.force_pipeline_name ? "yes" : "no"}`,
      `Matches current name: ${item.matches_target ? "yes" : "no"}`,
      `Sidecar moves: ${item.sidecar_count ?? sidecarMoves.length}`,
      warnings.length ? `Warnings: ${warnings.join(" | ")}` : "",
      errors.length ? `Errors: ${errors.join(" | ")}` : "",
    ].filter(Boolean);
    setText("rename-detail", detail.join("\n"));
  }

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
      return replacements[trimmed.toLowerCase()] || line;
    });
    input.value = lines.join("\n");
    renderRenameFileSourceSummary();
  }

  function renameApplyResultLines(result) {
    const payload = result && typeof result === "object" ? result : {};
    const data = payload.data && typeof payload.data === "object" ? payload.data : {};
    const request = payload.request && typeof payload.request === "object" ? payload.request : {};
    const rows = Array.isArray(data.rows) ? data.rows : [];
    const selectedSources = Array.isArray(request.selected_sources) ? request.selected_sources : [];
    const lines = [
      `Command: ${payload.command || "rename.apply"}`,
      `Result: ${payload.ok ? "ok" : payload.severity || "error"}`,
      `Message: ${payload.message || ""}`,
      `Selected rows: ${data.selected ?? selectedSources.length ?? ""}`,
      `Applied rows: ${data.applied_count ?? rows.length}`,
      `Renamed media files: ${data.renamed ?? ""}`,
      `Unchanged media files: ${data.unchanged ?? ""}`,
      `Sidecar moves: ${data.sidecars ?? ""}`,
      `Media operations: ${data.media_operations ?? ""}`,
      `Sidecar operations: ${data.sidecar_operations ?? ""}`,
      `Undo manifest: ${data.undo_manifest || ""}`,
    ];
    const warnings = Array.isArray(payload.warnings) ? payload.warnings : [];
    const errors = Array.isArray(payload.errors) ? payload.errors : [];
    if (warnings.length) lines.push(`Warnings: ${warnings.join(" | ")}`);
    if (errors.length) lines.push(`Errors: ${errors.join(" | ")}`);
    if (rows.length) {
      lines.push("", "Rows:");
      rows.slice(0, 12).forEach((row) => {
        const sidecars = row.sidecar_count ?? row.sidecars ?? "";
        lines.push(`- ${row.source || ""} -> ${row.destination || ""} [${row.status || ""}; sidecars=${sidecars}]`);
      });
      if (rows.length > 12) lines.push(`...and ${rows.length - 12} more row(s)`);
    }
    lines.push("", "Backend rename preview/apply remains the source of truth for filesystem changes.");
    return lines;
  }

  function renameApplyOutcomePayload(result) {
    if (!result) return {};
    return result.raw && typeof result.raw === "object" ? result.raw : result;
  }

  function renameApplyOutcomeNumber(value, fallback = 0) {
    const numberValue = Number(value);
    return Number.isFinite(numberValue) ? numberValue : fallback;
  }

  function renameApplyOutcomeStatus(result) {
    const payload = renameApplyOutcomePayload(result);
    if (!payload || !Object.keys(payload).length) return "No apply";
    const data = payload.data && typeof payload.data === "object" ? payload.data : {};
    const rows = Array.isArray(data.rows) ? data.rows : [];
    const warnings = Array.isArray(payload.warnings) ? payload.warnings : [];
    const errors = Array.isArray(payload.errors) ? payload.errors : [];
    if (!payload.ok || errors.length) return "Failed";
    if (warnings.length) return "Review";
    const renamed = renameApplyOutcomeNumber(data.renamed, 0);
    const applied = renameApplyOutcomeNumber(data.applied_count, rows.length);
    const unchanged = renameApplyOutcomeNumber(data.unchanged, 0);
    if (renamed > 0 || applied > 0) return "Applied";
    if (unchanged > 0) return "No changes";
    return "Recorded";
  }

  function renameApplyOutcomeStatusState(status) {
    const normalized = String(status || "").toLowerCase();
    if (normalized.includes("fail")) return "blocked";
    if (normalized.includes("review")) return "warning";
    if (normalized.includes("applied")) return "ready";
    if (normalized.includes("recorded") || normalized.includes("no changes")) return "changed";
    return "unknown";
  }

  function renameApplyOutcomeRow(checkpoint, posture, evidence, action) {
    return { checkpoint, posture, evidence, action };
  }

  function renameApplyOutcomeRows(result) {
    const payload = renameApplyOutcomePayload(result);
    if (!payload || !Object.keys(payload).length) {
      return [
        renameApplyOutcomeRow(
          "Backend result",
          "waiting",
          "No rename.apply command result is loaded.",
          "Apply checked or selected rows only after preview/readiness agree.",
        ),
      ];
    }
    const data = payload.data && typeof payload.data === "object" ? payload.data : {};
    const request = payload.request && typeof payload.request === "object" ? payload.request : {};
    const rows = Array.isArray(data.rows) ? data.rows : [];
    const selectedSources = Array.isArray(request.selected_sources) ? request.selected_sources : [];
    const warnings = Array.isArray(payload.warnings) ? payload.warnings : [];
    const errors = Array.isArray(payload.errors) ? payload.errors : [];
    const selected = renameApplyOutcomeNumber(data.selected, selectedSources.length);
    const applied = renameApplyOutcomeNumber(data.applied_count, rows.length);
    const renamed = renameApplyOutcomeNumber(data.renamed, 0);
    const unchanged = renameApplyOutcomeNumber(data.unchanged, 0);
    const sidecars = renameApplyOutcomeNumber(data.sidecars, 0);
    const mediaOperations = renameApplyOutcomeNumber(data.media_operations, renamed);
    const sidecarOperations = renameApplyOutcomeNumber(data.sidecar_operations, sidecars);
    return [
      renameApplyOutcomeRow(
        "Backend result",
        payload.ok && !errors.length ? (warnings.length ? "review" : "ok") : "failed",
        `${payload.command || "rename.apply"} returned ${payload.ok ? "ok" : payload.severity || "error"}; message=${payload.message || "(none)"}.`,
        payload.ok && !errors.length ? "Compare row counts below and inspect command history for durable backend evidence." : "Do not assume any rename completed; inspect warnings/errors and backend command history.",
      ),
      renameApplyOutcomeRow(
        "Selected scope",
        selected ? "ok" : "review",
        `${selected} selected source(s) submitted; request mode=${request.mode || "(unknown)"}; confirmed=${request.confirm_apply === true ? "yes" : "not reported"}.`,
        "Confirm selected_sources matches the intended checked/selected preview scope.",
      ),
      renameApplyOutcomeRow(
        "Applied rows",
        applied ? "ok" : "review",
        `${applied} applied row(s); ${renamed} renamed media file(s); ${unchanged} unchanged/no-op file(s).`,
        applied ? "Spot-check renamed rows below and confirm expected no-op rows were intentional." : "If no rows applied, read backend message before retrying.",
      ),
      renameApplyOutcomeRow(
        "Sidecar operations",
        sidecarOperations || sidecars ? "review" : "ok",
        `${sidecars} sidecar move(s) reported; media operations=${mediaOperations}; sidecar operations=${sidecarOperations}.`,
        sidecarOperations || sidecars ? "Verify associated .pipeline.json/SRT sidecars followed the media file where expected." : "No sidecar move evidence reported.",
      ),
      renameApplyOutcomeRow(
        "Undo / rollback evidence",
        data.undo_manifest ? "ok" : "review",
        data.undo_manifest ? `Undo manifest: ${data.undo_manifest}` : "No undo manifest path reported in the backend result.",
        data.undo_manifest ? "Keep this path for manual recovery review if a later row looks wrong." : "Do not rely on WebView for undo; inspect backend logs before manual repair.",
      ),
      renameApplyOutcomeRow(
        "Warnings and errors",
        errors.length ? "failed" : warnings.length ? "review" : "ok",
        `${warnings.length} warning(s), ${errors.length} error(s).${warnings.length ? ` warnings=${warnings.slice(0, 3).join(" | ")}` : ""}${errors.length ? ` errors=${errors.slice(0, 3).join(" | ")}` : ""}`,
        errors.length || warnings.length ? "Resolve backend-reported issues before another batch apply." : "No backend warning/error evidence reported.",
      ),
      renameApplyOutcomeRow(
        "Paths textarea update",
        rows.length ? "ok" : "review",
        rows.length ? `${rows.length} backend result row(s) available for local Paths textarea replacement.` : "No backend rows available for local Paths textarea replacement.",
        "Treat updated textarea paths as local convenience only; backend command result remains source of truth.",
      ),
      renameApplyOutcomeRow(
        "Mutation boundary",
        "ok",
        "Only /api/rename/apply can mutate files. This outcome review cannot rename, undo, retry, delete, or touch files.",
        "For any doubt, compare preview, command history, output folders, and backend logs before applying another batch.",
      ),
    ];
  }

  function renameApplyOutcomeSummaryLines(result) {
    const payload = renameApplyOutcomePayload(result);
    const rows = renameApplyOutcomeRows(payload);
    const status = renameApplyOutcomeStatus(payload);
    if (!payload || !Object.keys(payload).length) {
      return [
        "Backend rename apply outcome review:",
        "Status: No apply",
        "Next step: run Preview, check intended rows, read Apply Readiness, then use backend-owned Apply Checked / Selected Rename.",
        "Mutation guardrail: this panel is read-only and cannot rename, undo, retry, or touch files.",
      ];
    }
    const data = payload.data && typeof payload.data === "object" ? payload.data : {};
    const blocked = rows.filter((row) => ["failed", "blocked"].includes(String(row.posture || "").toLowerCase())).length;
    const review = rows.filter((row) => String(row.posture || "").toLowerCase() === "review").length;
    return [
      "Backend rename apply outcome review:",
      `Status: ${status}; checkpoints needing review=${review}; failed/blocked=${blocked}`,
      `Applied: selected=${data.selected ?? ""}; applied=${data.applied_count ?? ""}; renamed=${data.renamed ?? ""}; unchanged=${data.unchanged ?? ""}; sidecars=${data.sidecars ?? ""}`,
      `Undo manifest: ${data.undo_manifest || "(not reported)"}`,
      "Next step: verify rows/sidecars on disk only after command result and history agree.",
      "Mutation guardrail: this panel is read-only and cannot rename, undo, retry, delete, or touch files.",
    ];
  }

  function renderRenameApplyOutcomeReview(result) {
    const payload = renameApplyOutcomePayload(result);
    const status = renameApplyOutcomeStatus(payload);
    setText("rename-apply-outcome-status", status);
    const statusNode = byId("rename-apply-outcome-status");
    if (statusNode) statusNode.dataset.state = renameApplyOutcomeStatusState(status);
    renderRenameApplyProgress(payload);
    setText("rename-apply-outcome-summary", renameApplyOutcomeSummaryLines(payload).join("\n"));
    const tbody = byId("rename-apply-outcome-rows");
    if (!tbody) return;
    const rows = renameApplyOutcomeRows(payload);
    tbody.replaceChildren();
    rows.forEach((item) => {
      const row = document.createElement("tr");
      row.dataset.status = item.posture || "";
      appendCells(row, [item.checkpoint, item.posture, item.evidence, item.action]);
      tbody.appendChild(row);
    });
    const counts = rows.reduce((acc, item) => {
      const key = String(item.posture || "unknown").toLowerCase();
      acc[key] = (acc[key] || 0) + 1;
      return acc;
    }, {});
    const countText = Object.keys(counts).sort().map((key) => `${key}=${counts[key]}`).join(", ");
    setText("rename-apply-outcome-legend", `Rename apply outcome review: ${countText || "none"}. Read-only; backend rename.apply remains the only filesystem mutation path.`);
  }

  function renameApplyProgressBars(payload) {
    const data = payload?.data && typeof payload.data === "object" ? payload.data : {};
    const progress = data.rename_progress && typeof data.rename_progress === "object" ? data.rename_progress : {};
    if (Array.isArray(progress.progress_bars)) return progress.progress_bars.filter(Boolean);
    if (Array.isArray(data.progress_bars)) return data.progress_bars.filter(Boolean);
    return [];
  }

  function renderRenameApplyProgress(payload) {
    if (typeof renderProgressBarsInto !== "function") return;
    const data = payload?.data && typeof payload.data === "object" ? payload.data : {};
    const progress = data.rename_progress && typeof data.rename_progress === "object" ? data.rename_progress : {};
    renderProgressBarsInto("rename-apply-progress-bars", renameApplyProgressBars(payload), progress, "No rename apply progress loaded.");
  }

  function renderRenameApplyResult(result) {
    if (!result) {
      setText("rename-last-apply-status", "No apply");
      setText("rename-last-apply-detail", "No rename apply result loaded.");
      renderRenameApplyOutcomeReview(null);
      return;
    }
    const payload = result.raw && typeof result.raw === "object" ? result.raw : result;
    const data = payload.data && typeof payload.data === "object" ? payload.data : {};
    const renamed = data.renamed ?? "";
    const applied = data.applied_count ?? (Array.isArray(data.rows) ? data.rows.length : "");
    setText("rename-last-apply-status", payload.ok ? `${renamed} renamed / ${applied} applied` : payload.severity || "failed");
    setText("rename-last-apply-detail", renameApplyResultLines(payload).join("\n"));
    renderRenameApplyOutcomeReview(payload);
  }

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

  function renderRenamePreview(preview) {
    const rows = Array.isArray(preview.rows) ? preview.rows : [];
    lastRenameRows = rows;
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
      checkbox.title = checkbox.disabled ? "Blocked rename rows cannot be checked for apply." : "Check this row for backend selected_sources apply.";
      checkbox.addEventListener("click", (event) => event.stopPropagation());
      checkbox.addEventListener("change", () => setRenameRowChecked(item, checkbox.checked));
      checkCell.appendChild(checkbox);
      row.appendChild(checkCell);
      appendCells(row, [
        item.source_name || item.source || "",
        item.pipeline_guess || "",
        item.target_name || "",
        renameConfidenceLabel(item),
        item.status || "",
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
    ["rename-preview-button", "rename-preview-top-button"].forEach((id) => {
      const button = byId(id);
      if (button) button.disabled = commandBusy;
    });
    const applyButton = byId("rename-apply-selected-button");
    if (applyButton) applyButton.disabled = renameBrowseInFlight || renameApplyInFlight;
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
      renderRenamePreview(preview);
    } catch (error) {
      if (requestId !== activeRenamePreviewRequestId) return;
      const message = error instanceof Error ? error.message : String(error);
      lastRenameRows = [];
      selectedRenameSourceKey = "";
      checkedRenameSourceKeys.clear();
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
    renderRenameCleaningFilterEditor,
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
  };
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
