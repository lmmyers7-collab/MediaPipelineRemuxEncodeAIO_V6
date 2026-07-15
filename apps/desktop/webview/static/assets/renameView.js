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
  let lastRenamePreviewFingerprint = "";
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

  const __renameCleaningFiltersMod = window.__renameCleaningFiltersModule || {};
  delete window.__renameCleaningFiltersModule;
  const _renameCleaningFilters = typeof __renameCleaningFiltersMod.createRenameCleaningFiltersModule === "function"
    ? __renameCleaningFiltersMod.createRenameCleaningFiltersModule({
      RENAME_CLEANING_FILTER_STORAGE_KEY,
      RENAME_CLEAN_FILENAME_PREVIEW_ROUTE,
      RENAME_FILTER_CATALOG_ROUTE,
      RENAME_MOVIE_FILTER_CATALOG_ROUTE,
      RENAME_CLEANING_IDS,
      apiGet: typeof apiGet === "function" ? apiGet : window.apiGet,
      appendCommandResult: typeof appendCommandResult === "function" ? appendCommandResult : window.appendCommandResult,
      byId: typeof byId === "function" ? byId : window.byId,
      documentRef: document,
      markRenameWorkbenchNeedsTest: (...args) => markRenameWorkbenchNeedsTest(...args),
      renameCleaningNode,
      setText: typeof setText === "function" ? setText : window.setText,
      syncRenameCommandButtons: (...args) => syncRenameCommandButtons(...args),
      windowRef: window,
    })
    : {};
  const {
    renameCleaningFilterTextareas = function () {},
    renameTvFilterTextareas = function () {},
    renameMovieFilterCheckboxes = function () {},
    renameTvFilterCheckboxes = function () {},
    collectRenameMovieFilterOptions = function () {},
    collectRenameTvFilterOptions = function () {},
    parseRenameFilterTerms = function () {},
    collectRenameMovieFilterTermsText = function () {},
    collectRenameMovieFilterTerms = function () {},
    collectRenameTvFilterTermsText = function () {},
    collectRenameTvFilterTerms = function () {},
    renameCleaningFilterState = function () {},
    renameCleaningFilterConfigPatch = function () {},
    renderRenameCleaningFilterEditor = function () {},
    saveRenameCleaningFilterDraft = function () {},
    stageRenameCleaningFilterPatch = function () {},
    saveRenameCleaningFilterState = function () {},
    resetRenameCleaningFilters = function () {},
    loadRenameCleaningFilterState = function () {},
    applyRenameFilterCatalogSection = function () {},
    loadRenameMovieFilterCatalog = function () {},
    renameCleanFilenamePreviewQuery = function () {},
    renderRenameFilterPreviewPayload = function () {},
    updateRenameFilterPreview = function () {},
  } = _renameCleaningFilters;

  const __renameCleaningWorkbenchMod = window.__renameCleaningWorkbenchModule || {};
  delete window.__renameCleaningWorkbenchModule;
  const _renameCleaningWorkbench = typeof __renameCleaningWorkbenchMod.createRenameCleaningWorkbenchModule === "function"
    ? __renameCleaningWorkbenchMod.createRenameCleaningWorkbenchModule({
      apiGet: typeof apiGet === "function" ? apiGet : window.apiGet,
      apiPost: (...args) => (typeof apiPost === "function" ? apiPost : window.apiPost)(...args),
      appendCommandResult: typeof appendCommandResult === "function" ? appendCommandResult : window.appendCommandResult,
      byId: typeof byId === "function" ? byId : window.byId,
      collectRenameMovieFilterOptions,
      collectRenameMovieFilterTerms,
      collectRenameTvFilterOptions,
      collectRenameTvFilterTerms,
      documentRef: document,
      loadRenameMovieFilterCatalog,
      parseRenameFilterTerms,
      RENAME_CLEAN_FILENAME_PREVIEW_ROUTE,
      renameCleaningNode,
      renderRenameCleaningFilterEditor,
      saveRenameCleaningFilterDraft,
      saveRenameCleaningFilterState,
      setText: typeof setText === "function" ? setText : window.setText,
      submitRenameBadCasePayload: (...args) => window.mediaPipelineRenameView?.submitRenameBadCasePayload?.(...args),
      state: {
        get inFlight() { return renameWorkbenchInFlight; },
        set inFlight(value) { renameWorkbenchInFlight = Boolean(value); },
        get eventsBound() { return renameWorkbenchEventsBound; },
        set eventsBound(value) { renameWorkbenchEventsBound = Boolean(value); },
        get lastPayload() { return lastRenameWorkbenchPayload; },
        set lastPayload(value) { lastRenameWorkbenchPayload = value; },
        get hasStagedSuggestions() { return renameWorkbenchHasStagedSuggestions; },
        set hasStagedSuggestions(value) { renameWorkbenchHasStagedSuggestions = Boolean(value); },
        get saveNewFiltersReady() { return renameWorkbenchSaveNewFiltersReady; },
        set saveNewFiltersReady(value) { renameWorkbenchSaveNewFiltersReady = Boolean(value); },
      },
      updateRenameFilterPreview,
      windowRef: window,
    })
    : {};
  const {
    renameWorkbenchInput = function () {},
    renameWorkbenchValue = function () {},
    renameWorkbenchMode = function () {},
    setRenameWorkbenchSaveState = function () {},
    renameWorkbenchDestinationLabel = function () {},
    syncRenameWorkbenchModeFields = function () {},
    updateRenameWorkbenchSaveNewFiltersButton = function () {},
    setRenameWorkbenchBusy = function () {},
    markRenameWorkbenchNeedsTest = function () {},
    renameWorkbenchRequiredIssues = function () {},
    renameWorkbenchRequest = function () {},
    renameWorkbenchPreviewQuery = function () {},
    renderRenameWorkbenchPayload = function () {},
    renderRenameWorkbenchSuggestionRows = function () {},
    renderRenameWorkbenchSuggestions = function () {},
    runRenameWorkbenchPreview = function () {},
    saveRenameWorkbenchCase = function () {},
    appendRenameWorkbenchTerm = function () {},
    renameWorkbenchDestinationNode = function () {},
    enableRenameWorkbenchDestination = function () {},
    stageRenameWorkbenchSuggestions = function () {},
    saveRenameWorkbenchNewFilters = function () {},
    initRenameWorkbenchEvents = function () {},
  } = _renameCleaningWorkbench;

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

  const __renameSelectionMod = window.__renameSelectionModule || {};
  delete window.__renameSelectionModule;
  const _renameSelection = typeof __renameSelectionMod.createRenameSelectionModule === "function"
    ? __renameSelectionMod.createRenameSelectionModule({
      apiPost: (...args) => (typeof apiPost === "function" ? apiPost : window.apiPost)(...args),
      appendCommandResult: typeof appendCommandResult === "function" ? appendCommandResult : window.appendCommandResult,
      byId: typeof byId === "function" ? byId : window.byId,
      documentRef: document,
      renameDialogById: (...args) => renameDialogById(...args),
      RENAME_PREVIEW_RENDER_LIMIT,
      renderRenameApplyReadiness: (...args) => renderRenameApplyReadiness(...args),
      renderRenameBulkEditor: (...args) => renderRenameBulkEditor(...args),
      renderRenameSelectionAudit: (...args) => renderRenameSelectionAudit(...args),
      setText: typeof setText === "function" ? setText : window.setText,
      state: {
        get badCaseInFlight() { return renameBadCaseInFlight; },
        set badCaseInFlight(value) { renameBadCaseInFlight = Boolean(value); },
        get applyInFlight() { return renameApplyInFlight; },
        get browseInFlight() { return renameBrowseInFlight; },
        get checkedSourceKeys() { return checkedRenameSourceKeys; },
        get finalOverrides() { return renameFinalOverrides; },
        get forceOverrides() { return renameForceOverrides; },
        get rows() { return lastRenameRows; },
        set rows(value) { lastRenameRows = Array.isArray(value) ? value : []; },
        get previewInFlight() { return renamePreviewInFlight; },
        get selectedSourceKey() { return selectedRenameSourceKey; },
        set selectedSourceKey(value) { selectedRenameSourceKey = String(value || ""); },
      },
      syncRenameCommandButtons: (...args) => syncRenameCommandButtons(...args),
      windowRef: window,
    })
    : {};
  const {
    renameSourceKey = function () {},
    getSelectedRenameRow = function () {},
    getCheckedRenameRows = function () {},
    renameRenderedRowsCount = function () {},
    renameRenderCapText = function () {},
    renameStatusState = function () {},
    setRenameStatusLine = function () {},
    renameRowStatus = function () {},
    renameRowHasWarnings = function () {},
    renameDuplicateTargetSet = function () {},
    renameTargetKey = function () {},
    renameAutoCheckSkipReason = function () {},
    updateRenameTableLegend = function () {},
    renameCurrentFinalName = function () {},
    renameRowCanApply = function () {},
    renameImportantRowReason = function () {},
    renameRowStatusDisplay = function () {},
    getRenameApplyScopeRows = function () {},
    syncRenameCheckedCount = function () {},
    setRenameRowChecked = function () {},
    setRenameRowCheckedFromCheckbox = function () {},
    checkApplicableRenameRows = function () {},
    checkAllRenameRows = function () {},
    clearCheckedRenameRows = function () {},
    renamePathLines = function () {},
    setRenamePathLines = function () {},
    renameSourcePathFromRow = function () {},
    renameSourceLabelFromRow = function () {},
    renamePathSegments = function () {},
    renameFileLeafFromPath = function () {},
    renameParentFolderLeafFromPath = function () {},
    renameFolderLeafFromValue = function () {},
    renameExpectedShowFromName = function () {},
    renameExpectedSeasonFromName = function () {},
    renameSeasonNumberFromWorkbench = function () {},
    compactRenameNote = function () {},
    renameBadCasePayloadFromRow = function () {},
    submitRenameBadCasePayload = function () {},
    setRenameBadCaseBusy = function () {},
    renameLogCaseInput = function () {},
    setRenameLogCaseInputValue = function () {},
    renameBadCaseDialogOverrides = function () {},
    syncRenameBadCaseButton = function () {},
    openRenameBadCaseDialog = function () {},
    submitRenameBadCaseDialog = function () {},
  } = _renameSelection;

  const __renamePathsMod = window.__renamePathsModule || {};
  delete window.__renamePathsModule;
  const _renamePaths = typeof __renamePathsMod.createRenamePathsModule === "function"
    ? __renamePathsMod.createRenamePathsModule({
      apiPost: (...args) => (typeof apiPost === "function" ? apiPost : window.apiPost)(...args),
      appendCommandResult: typeof appendCommandResult === "function" ? appendCommandResult : window.appendCommandResult,
      byId: typeof byId === "function" ? byId : window.byId,
      documentRef: document,
      renamePathLines,
      renameSourceLabelFromRow,
      renameSourcePathFromRow,
      RENAME_MEDIA_EXTENSIONS,
      RENAME_SIDECAR_SUFFIXES,
      setRenameStatusLine,
      setText: typeof setText === "function" ? setText : window.setText,
      state: {
        get applyInFlight() { return renameApplyInFlight; },
        get browseInFlight() { return renameBrowseInFlight; },
        set browseInFlight(value) { renameBrowseInFlight = Boolean(value); },
        get pathOrigins() { return renamePathOrigins; },
        get previewInFlight() { return renamePreviewInFlight; },
      },
      syncRenameCommandButtons: (...args) => syncRenameCommandButtons(...args),
      windowRef: window,
    })
    : {};
  const {
    renameCurrentPathValues = function () {},
    renamePathLeaf = function () {},
    renamePathExtension = function () {},
    renameIsSidecarPath = function () {},
    classifyRenamePathValues = function () {},
    renameLooksLikeAbsolutePath = function () {},
    normalizeRenameDroppedPathValues = function () {},
    renameDroppedPathFromFile = function () {},
    renameDroppedPathValuesFromDataTransfer = function () {},
    renameDroppedPathValuesFromBridgeDetail = function () {},
    handleRenameDroppedPaths = function () {},
    renameDropZoneIsVisible = function () {},
    renamePathOriginKey = function () {},
    rememberRenamePathOrigins = function () {},
    pruneRenamePathOrigins = function () {},
    renamePathOriginCounts = function () {},
    renamePathOriginSummary = function () {},
    renderRenameFileSourceSummary = function () {},
    appendRenamePaths = function () {},
    renameIgnoredPathSuffix = function () {},
    appendResolvedRenameBrowsePaths = function () {},
    addRenamePathFromInput = function () {},
    browseRenamePaths = function () {},
  } = _renamePaths;

  const __renameEditingMod = window.__renameEditingModule || {};
  delete window.__renameEditingModule;
  const _renameEditing = typeof __renameEditingMod.createRenameEditingModule === "function"
    ? __renameEditingMod.createRenameEditingModule({
      byId: typeof byId === "function" ? byId : window.byId,
      clearRows: typeof clearRows === "function" ? clearRows : window.clearRows,
      appendCells: typeof appendCells === "function" ? appendCells : window.appendCells,
      collectRenameRequest,
      documentRef: document,
      getCheckedRenameRows,
      getSelectedRenameRow,
      getRenameApplyScopeRows,
      renameCurrentPathValues,
      renamePathLines,
      renameConfidenceExplanation,
      renameConfidenceLabel,
      renamePreviewSourceLabel,
      renameRenderedRowsCount,
      renameRowCanApply,
      renameSourceKey,
      renameSourceLabelFromRow,
      renameSourcePathFromRow,
      renameStatusExplanation,
      renameMarkInputChanged,
      RENAME_PREVIEW_RENDER_LIMIT,
      renderRenameApplyReadiness: (...args) => renderRenameApplyReadiness(...args),
      renderRenameBatchSafety: (...args) => renderRenameBatchSafety(...args),
      renderRenameBulkEditor: (...args) => renderRenameBulkEditor(...args),
      renderRenameFileSourceSummary,
      renderRenamePipelineHandoff: (...args) => renderRenamePipelineHandoff(...args),
      renderRenameReviewBoard: (...args) => renderRenameReviewBoard(...args),
      renderRenameRows: (...args) => renderRenameRows(...args),
      renderRenameSelectionAudit: (...args) => renderRenameSelectionAudit(...args),
      resetRenameApplyEvidence: (...args) => resetRenameApplyEvidence(...args),
      refreshRenamePreview: (...args) => refreshRenamePreview(...args),
      setRenamePathLines,
      setRenameStatusLine,
      setText: typeof setText === "function" ? setText : window.setText,
      state: {
        get checkedSourceKeys() { return checkedRenameSourceKeys; },
        get emptyMessage() { return lastRenameEmptyMessage; },
        set emptyMessage(value) { lastRenameEmptyMessage = String(value || ""); },
        get finalOverrides() { return renameFinalOverrides; },
        get forceOverrides() { return renameForceOverrides; },
        get pathOrigins() { return renamePathOrigins; },
        get previewSignature() { return lastRenamePreviewSignature; },
        set previewSignature(value) { lastRenamePreviewSignature = String(value || ""); },
        get previewStale() { return renamePreviewStale; },
        set previewStale(value) { renamePreviewStale = Boolean(value); },
        get rows() { return lastRenameRows; },
        set rows(value) { lastRenameRows = Array.isArray(value) ? value : []; },
        get selectedSourceKey() { return selectedRenameSourceKey; },
        set selectedSourceKey(value) { selectedRenameSourceKey = String(value || ""); },
      },
      syncRenameCheckedCount: (...args) => syncRenameCheckedCount(...args),
      syncRenameCommandButtons: (...args) => syncRenameCommandButtons(...args),
      windowRef: window,
    })
    : {};
  const {
    renderRenameApplyReadiness = function () {},
    renderRenameBatchSafety = function () {},
    renderRenameDetail = function () {},
    renderRenamePipelineHandoff = function () {},
    renderRenameReviewBoard = function () {},
    renderRenameSelectionAudit = function () {},
    renderRenameSummary = function () {},
    renameApplyReadinessRows = function () { return []; },
    renameApplyReadinessStatus = function () { return ""; },
    renameApplyScopeBlockers = function () { return []; },
    renameBatchSafetyLines = function () { return []; },
    renameDuplicateTargets = function () { return []; },
    renameFormatCounts = function () { return ""; },
    renamePipelineHandoffLines = function () { return []; },
    renamePipelineHandoffStatus = function () { return ""; },
    renamePreviewAggregateObject = function () { return {}; },
    renameReviewBoardLines = function () { return []; },
    renameReviewBoardStatus = function () { return ""; },
    renameSavedSettingsConfig = function () { return {}; },
    renameSelectionAuditStatus = function () { return ""; },
    renameSelectionDuplicateTargets = function () { return []; },
    renameTemplateLabel = function () { return ""; },
    renderRenameApplyOutcomeReview = function () {},
    renderRenameApplyInFlight = function () {},
    renderRenameApplyProgress = function () {},
  renderRenameApplyResult: renderRenameApplyResultFromSlice = function () {},
    renameApplyOutcomeRows = function () { return []; },
    renameApplyOutcomeStatus = function () { return ""; },
    renameApplyOutcomeStatusState = function () { return ""; },
    renameApplyOutcomeSummaryLines = function () { return []; },
    renameApplyProgressBars = function () { return []; },
    renameApplyResultLines = function () { return []; },
    clearRenamePaths = function () {},
    useSelectedQueueRowForRename = function () {},
    useLoadedQueueRowsForRename = function () {},
    renameLineKey = function () {},
    checkedOrSelectedRenameKeys = function () {},
    moveCheckedRenamePaths = function () {},
    naturalCompareText = function () {},
    naturalSortRenamePaths = function () {},
    syncRenameSelectedInputs = function () {},
    captureRenameSelectionScroll = function () {},
    restoreRenameSelectionScroll = function () {},
    selectRenameRow = function () {},
    renameBulkScopeRows = function () { return []; },
    renameBulkScopeLabel = function () {},
    renameSplitFilename = function () {},
    renameBulkEditedName = function () {},
    renameBulkHasEditInput = function () {},
    renameNameHasPathSeparator = function () {},
    renameSetFinalOverride = function () {},
    renderRenameBulkEditor = function () {},
    stageRenameBulkEdit = function () {},
    usePipelineNamesForRenameScope = function () {},
    setRenameBulkForce = function () {},
    clearRenameBulkOverrides = function () {},
    applyRenameSelectedOverride = function () {},
    clearRenameSelectedOverride = function () {},
    replaceRenamePathText = function () {},
  } = _renameEditing;

  const __renameCommandEvidenceMod = window.__renameCommandEvidenceModule || {};
  delete window.__renameCommandEvidenceModule;
  const _renameCommandEvidence = typeof __renameCommandEvidenceMod.createRenameCommandEvidenceModule === "function"
    ? __renameCommandEvidenceMod.createRenameCommandEvidenceModule({
      byId: typeof byId === "function" ? byId : window.byId,
      documentRef: document,
      renameConfirmBasename: (...args) => renameConfirmBasename(...args),
      renderRenameApplyResultFromSlice,
      setRenameStatusLine,
      setText: typeof setText === "function" ? setText : window.setText,
      state: {
        get applyInFlight() { return renameApplyInFlight; },
        get commandActivityState() { return renameCommandActivityState; },
        set commandActivityState(value) { renameCommandActivityState = value; },
        get commandActivityTimer() { return renameCommandActivityTimer; },
        set commandActivityTimer(value) { renameCommandActivityTimer = value; },
        get lastApplyHadResult() { return lastRenameApplyHadResult; },
        set lastApplyHadResult(value) { lastRenameApplyHadResult = Boolean(value); },
        get lastApplyResultPayload() { return lastRenameApplyResultPayload; },
        set lastApplyResultPayload(value) { lastRenameApplyResultPayload = value; },
        get lastUndoCompleted() { return lastRenameUndoCompleted; },
        set lastUndoCompleted(value) { lastRenameUndoCompleted = Boolean(value); },
        get lastUndoManifest() { return lastRenameUndoManifest; },
        set lastUndoManifest(value) { lastRenameUndoManifest = String(value || ""); },
        get undoInFlight() { return renameUndoInFlight; },
      },
      windowRef: window,
    })
    : {};
  const {
    renameApplyPayloadFromResult = function () { return {}; },
    renameUndoManifestFromApplyResult = function () { return ""; },
    stopRenameCommandActivity = function () {},
    startRenameCommandActivity = function () {},
    syncRenameUndoButton = function () {},
    renderRenameApplyResult = function () {},
    renameLastApplyUndoCounts = function () { return { totalOps: 0, manifestName: "last apply manifest" }; },
    renderRenameUndoResult = function () {},
    resetRenameApplyEvidence = function () {},
  } = _renameCommandEvidence;



  async function applySelectedRename() {
    return applyRenameWorkbench();
  }

  const __renamePreviewLifecycleMod = window.__renamePreviewLifecycleModule || {};
  delete window.__renamePreviewLifecycleModule;
  const _renamePreviewLifecycle = typeof __renamePreviewLifecycleMod.createRenamePreviewLifecycleModule === "function"
    ? __renamePreviewLifecycleMod.createRenamePreviewLifecycleModule({
      apiPost: typeof apiPost === "function" ? apiPost : window.apiPost,
      appendCells: typeof appendCells === "function" ? appendCells : window.appendCells,
      byId: typeof byId === "function" ? byId : window.byId,
      clearRows: typeof clearRows === "function" ? clearRows : window.clearRows,
      collectRenameRequest,
      documentRef: document,
      getCheckedRenameRows,
      getRenameApplyScopeRows,
      getSelectedRenameRow,
      makeRowSelectable: typeof makeRowSelectable === "function" ? makeRowSelectable : window.makeRowSelectable,
      renameApplyScopeBlockers,
      renameBulkScopeRows,
      renameConfidenceExplanation,
      renameConfidenceLabel,
      renameCurrentRequestSignature,
      renameDuplicateTargetSet,
      renameImportantRowReason,
      renamePathLines,
      renamePreviewSourceLabel,
      renamePreviewStatusText,
      renameRenderCapText,
      renameRequestSignatureFromRequest,
      renameRowCanApply,
      renameRowStatusDisplay,
      renameSourceKey,
      renameStatusExplanation,
      renameTargetKey,
      RENAME_PREVIEW_RENDER_LIMIT,
      renderRenameApplyReadiness,
      renderRenameBatchSafety,
      renderRenameBulkEditor,
      renderRenameDetail,
      renderRenameFileSourceSummary,
      renderRenamePipelineHandoff,
      renderRenameReviewBoard,
      renderRenameSelectionAudit,
      renderRenameSummary,
      selectRenameRow,
      setRenameRowCheckedFromCheckbox,
      setRenameStatusLine,
      setText: typeof setText === "function" ? setText : window.setText,
      state: {
        get activePreviewRequestId() { return activeRenamePreviewRequestId; },
        set activePreviewRequestId(value) { activeRenamePreviewRequestId = Number(value || 0); },
        get applyInFlight() { return renameApplyInFlight; },
        set applyInFlight(value) { renameApplyInFlight = Boolean(value); },
        get badCaseInFlight() { return renameBadCaseInFlight; },
        get browseInFlight() { return renameBrowseInFlight; },
        get checkedSourceKeys() { return checkedRenameSourceKeys; },
        get emptyMessage() { return lastRenameEmptyMessage; },
        set emptyMessage(value) { lastRenameEmptyMessage = String(value || ""); },
        get previewFingerprint() { return lastRenamePreviewFingerprint; },
        set previewFingerprint(value) { lastRenamePreviewFingerprint = String(value || ""); },
        get previewInFlight() { return renamePreviewInFlight; },
        set previewInFlight(value) { renamePreviewInFlight = Boolean(value); },
        get previewRequestId() { return renamePreviewRequestId; },
        set previewRequestId(value) { renamePreviewRequestId = Number(value || 0); },
        get previewSignature() { return lastRenamePreviewSignature; },
        set previewSignature(value) { lastRenamePreviewSignature = String(value || ""); },
        get previewStale() { return renamePreviewStale; },
        set previewStale(value) { renamePreviewStale = Boolean(value); },
        get rows() { return lastRenameRows; },
        set rows(value) { lastRenameRows = Array.isArray(value) ? value : []; },
        get selectedSourceKey() { return selectedRenameSourceKey; },
        set selectedSourceKey(value) { selectedRenameSourceKey = String(value || ""); },
        get undoInFlight() { return renameUndoInFlight; },
        set undoInFlight(value) { renameUndoInFlight = Boolean(value); },
      },
      syncRenameBadCaseButton,
      syncRenameCheckedCount,
      syncRenameSelectedInputs,
      syncRenameUndoButton,
      updateRenamePreviewFreshnessState,
      updateRenameTableLegend,
    })
    : {};
  const {
    renderRenamePreview = function () {},
    renderRenameRows = function () {},
    setRenamePreviewBusy = function () {},
    setRenameApplyBusy = function () {},
    setRenameUndoBusy = function () {},
    syncRenameCommandButtons = function () {},
    refreshRenamePreview = async function () {},
  } = _renamePreviewLifecycle;



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

  const __renameConfirmSummaryMod = window.__renameConfirmSummaryModule || {};
  delete window.__renameConfirmSummaryModule;
  const _renameConfirmSummary = typeof __renameConfirmSummaryMod.createRenameConfirmSummaryModule === "function"
    ? __renameConfirmSummaryMod.createRenameConfirmSummaryModule({
      byId: typeof byId === "function" ? byId : window.byId,
      renameDuplicateTargets: (rows) => typeof renameDuplicateTargets === "function" ? renameDuplicateTargets(rows) : [],
      renameLastApplyUndoCounts,
    })
    : {};
  const {
    renameConfirmBasename = function (value) { return String(value || ""); },
    renameDialogById = function () { return null; },
    renderRenameConfirmSummary = function () {},
    renderRenameUndoConfirmSummary = function () {},
  } = _renameConfirmSummary;

  const __renameDialogsMod = window.__renameDialogsModule || {};
  delete window.__renameDialogsModule;
  const _renameDialogs = typeof __renameDialogsMod.createRenameDialogsModule === "function"
    ? __renameDialogsMod.createRenameDialogsModule({
      byId: typeof byId === "function" ? byId : window.byId,
      documentRef: document,
      previewRenderLimit: RENAME_PREVIEW_RENDER_LIMIT,
      renameConfirmBasename,
      renameDialogById,
      renameLastApplyUndoCounts,
      renderRenameConfirmSummary,
      renderRenameUndoConfirmSummary,
      setText: typeof setText === "function" ? setText : window.setText,
      state: {
        get rows() { return lastRenameRows; },
        get lastUndoManifest() { return lastRenameUndoManifest; },
      },
      windowRef: window,
    })
    : {};
  const {
    renameOpenConfirmDialog = async function () { return false; },
    renameOpenUndoConfirmDialog = async function () { return false; },
    renameOpenResultDialog = function () {},
  } = _renameDialogs;



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
    if (!lastRenamePreviewFingerprint) {
      const message = "Backend preview fingerprint is unavailable. Run Preview again before applying.";
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
      request.preview_fingerprint = lastRenamePreviewFingerprint;
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
  };
  const renameInteractionsModule = window.__renameInteractionsModule || {};
  delete window.__renameInteractionsModule;
  const renameInteractions = typeof renameInteractionsModule.createRenameInteractionsModule === "function"
    ? renameInteractionsModule.createRenameInteractionsModule({
        byId,
        handleRenameDroppedPaths,
        renameDroppedPathValuesFromDataTransfer,
        renameDroppedPathValuesFromBridgeDetail,
        renameDropZoneIsVisible,
        renameWebviewFileDropEvent: RENAME_WEBVIEW_FILE_DROP_EVENT,
        applyRenameWorkbench,
        undoLastRenameApply,
        refreshRenamePreview,
        browseRenamePaths,
        openRenameBadCaseDialog,
        renameDialogById,
        submitRenameBadCaseDialog,
        clearRenamePaths,
        renameMarkInputChanged,
        syncRenameBadCaseButton,
        syncRenameUndoButton,
      })
    : {};
  const {
    renameSyncModeFieldVisibility = () => {},
    renameInitWorkbenchEvents = () => {},
  } = renameInteractions;
  window.mediaPipelineRenameView.renameSyncModeFieldVisibility = renameSyncModeFieldVisibility;
  window.mediaPipelineRenameView.renameInitDropZone = () => {};
  window.mediaPipelineRenameView.renameInitWorkbenchEvents = renameInitWorkbenchEvents;

})();
