(function () {
  "use strict";

  const domNoop = function () {};
  const domEmptyLines = function () { return []; };

  const domQueryModule = window.__domQueryModule || {};
  delete window.__domQueryModule;
  const domQuery = typeof domQueryModule.createDomQueryModule === "function"
    ? domQueryModule.createDomQueryModule()
    : {};
  const {
    byId = (id) => document.getElementById(id),
  } = domQuery;

  const domTextModule = window.__domTextModule || {};
  delete window.__domTextModule;
  const domText = typeof domTextModule.createDomTextModule === "function"
    ? domTextModule.createDomTextModule({ byId })
    : {};
  const {
    setText = domNoop,
    applyDiagnosticCallouts = domNoop,
    applyProseBoxDispositions = domNoop,
    applyProseBoxDispositionToNode = domNoop,
    stateFromStatusText = () => "",
    setTextState = domNoop,
    selectedRowAtAGlanceLines = domEmptyLines,
    reviewFlagExplanationLines = domEmptyLines,
    selectedRowDetailDrawerLines = domEmptyLines,
    payloadFreshnessLines = domEmptyLines,
    jsonDetailText = () => "",
    renderJsonDetail = domNoop,
  } = domText;

  const domStatusModule = window.__domStatusModule || {};
  delete window.__domStatusModule;
  const domStatus = typeof domStatusModule.createDomStatusModule === "function"
    ? domStatusModule.createDomStatusModule({ setText, byId })
    : {};
  const {
    normalizedTableStatus = (value) => String(value || "").trim().toLowerCase() || "normal",
    normalizeBackendStatusState = () => "",
    backendRowStatusState = () => "",
    normalizePanelStatusState = () => "unknown",
    setPanelStatus = domNoop,
    setInlineActionStatus = domNoop,
    setActionBusy = domNoop,
    makeStatusChip = () => document.createElement("span"),
    setCellStatusChip = domNoop,
    tableStatusLegendText = () => "Table: no selectable rows.",
    updateTableStatusLegend = domNoop,
    reviewTileTone = () => "muted",
    makeReviewTile = () => document.createElement("section"),
    renderReviewTileBoard = () => 0,
  } = domStatus;

  const domFilteringModule = window.__domFilteringModule || {};
  delete window.__domFilteringModule;
  const domFiltering = typeof domFilteringModule.createDomFilteringModule === "function"
    ? domFilteringModule.createDomFilteringModule({ normalizedTableStatus })
    : {};
  const {
    filterRows = (rows) => rows,
    countRowsByStatus = () => ({}),
    formatStatusCounts = () => "none",
    tableStatusFilterLabel = () => "all",
    tableStatusMatchesFilter = () => true,
    filterRowsByStatus = (rows) => Array.isArray(rows) ? rows : [],
    tableInvestigationFilterLabel = () => "all",
    filterRowsByInvestigation = (rows) => Array.isArray(rows) ? rows : [],
    filterResultSummaryLines = domEmptyLines,
  } = domFiltering;

  const domTableModule = window.__domTableModule || {};
  delete window.__domTableModule;
  const domTable = typeof domTableModule.createDomTableModule === "function"
    ? domTableModule.createDomTableModule({ byId })
    : {};
  const {
    clearRows = domNoop,
    appendCells = domNoop,
    captureScrollablePositions = () => ({ entries: [] }),
    restoreScrollablePositions = domNoop,
    makeRowSelectable = domNoop,
    selectRowInGroup = domNoop,
    scrollSelectedRowIntoView = domNoop,
    renderOpenTargetActionGroups = () => ({ readFirst: 0, openNext: 0 }),
    enhanceDataTables = () => 0,
  } = domTable;

  /**
   * Public namespace for shared DOM helpers.
   * Prefer this namespace from new code; flat window.* exports are transitional compatibility aliases when present.
   */
  window.mediaPipelineDom = {
    byId,
    setText,
    applyDiagnosticCallouts,
    applyProseBoxDispositions,
    applyProseBoxDispositionToNode,
    stateFromStatusText,
    setTextState,
    clearRows,
    appendCells,
    filterRows,
    captureScrollablePositions,
    restoreScrollablePositions,
    makeRowSelectable,
    selectRowInGroup,
    scrollSelectedRowIntoView,
    normalizeBackendStatusState,
    backendRowStatusState,
    normalizePanelStatusState,
    setPanelStatus,
    setInlineActionStatus,
    setActionBusy,
    makeStatusChip,
    setCellStatusChip,
    tableStatusLegendText,
    updateTableStatusLegend,
    reviewTileTone,
    makeReviewTile,
    renderReviewTileBoard,
    countRowsByStatus,
    formatStatusCounts,
    tableStatusFilterLabel,
    tableStatusMatchesFilter,
    filterRowsByStatus,
    tableInvestigationFilterLabel,
    filterRowsByInvestigation,
    filterResultSummaryLines,
    selectedRowAtAGlanceLines,
    reviewFlagExplanationLines,
    selectedRowDetailDrawerLines,
    payloadFreshnessLines,
    jsonDetailText,
    renderJsonDetail,
    renderOpenTargetActionGroups,
    enhanceDataTables,
  };
  window.byId = byId;
  window.setText = setText;
  window.applyDiagnosticCallouts = applyDiagnosticCallouts;
  window.applyProseBoxDispositions = applyProseBoxDispositions;
  window.setTextState = setTextState;
  window.clearRows = clearRows;
  window.appendCells = appendCells;
  window.filterRows = filterRows;
  window.makeRowSelectable = makeRowSelectable;
  window.selectRowInGroup = selectRowInGroup;
  window.normalizeBackendStatusState = normalizeBackendStatusState;
  window.setPanelStatus = setPanelStatus;
  window.setInlineActionStatus = setInlineActionStatus;
  window.setActionBusy = setActionBusy;
  window.backendRowStatusState = backendRowStatusState;
  window.updateTableStatusLegend = updateTableStatusLegend;
  window.formatStatusCounts = formatStatusCounts;
  window.tableStatusFilterLabel = tableStatusFilterLabel;
  window.tableStatusMatchesFilter = tableStatusMatchesFilter;
  window.filterRowsByStatus = filterRowsByStatus;
  window.filterRowsByInvestigation = filterRowsByInvestigation;
  window.enhanceDataTables = enhanceDataTables;
})();
