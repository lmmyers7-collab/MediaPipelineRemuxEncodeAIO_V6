(function () {
  const formatters = window.mediaPipelineFormatters || {};
  const formatProgressValue = typeof formatters.formatProgressValue === "function"
    ? formatters.formatProgressValue
    : (value) => {
        if (value === null || value === undefined) return "";
        if (Array.isArray(value)) return value.join(", ");
        if (value && typeof value === "object") return JSON.stringify(value);
        return String(value);
      };
  let selectedProgressEvidenceKey = "";
  let renderProgressBarsInto;

  const progressBarStateModule = window.__progressBarStateModule || {};
  const progressBarState = typeof progressBarStateModule.createProgressBarStateModule === "function"
    ? progressBarStateModule.createProgressBarStateModule()
    : {};
  const {
    setProgressPanelStatus,
    progressBarStatusLabel,
    progressBarPercent,
    formatProgressUpdatedAt,
    homeProgressTimelineGroups,
    progressBarId,
    progressBarStatus,
    progressBarMode,
    progressUsePendingDrainCompactText,
    progressBarDisplayLabel,
    progressStepDisplayLabel,
    progressBarDisplayStatusLabel,
    progressSnapshotItemKey,
    resetProgressStaleDisplayCountsForItem,
    resetProgressDisplayPercentForItem,
    progressBarWithStaleDisplayHysteresis,
    progressBarsWithStaleDisplayHysteresis,
    progressBarForStableDisplay,
    progressBarsForStableDisplay,
    progressBarPercentLabel,
  } = progressBarState;

  const progressDetailsModule = window.__progressDetailsModule || {};
  delete window.__progressDetailsModule;
  const progressDetails = typeof progressDetailsModule.createProgressDetailsModule === "function"
    ? progressDetailsModule.createProgressDetailsModule({
        formatProgressValue,
        progressBarId,
        setProgressPanelStatus,
        byId: typeof byId === "function" ? byId : () => null,
        clearRows: typeof clearRows === "function" ? clearRows : () => {},
        appendCells: typeof appendCells === "function" ? appendCells : () => {},
      })
    : {};
  const {
    progressNumericValue,
    progressBarsWithOperatorStop,
    audioProgressLine,
    pendingDrainProgressLine,
    renderProgressDetails,
    renderPipelineEvents,
    normalizedProgressState,
    progressStateIsActive,
    progressEvidencePostureStatus,
    progressLatestEvent,
    progressEventLabel,
    progressActiveJobRows,
    formatActiveJobEvidenceRow,
  } = progressDetails;

  const progressWorkerModule = window.__progressWorkerModule || {};
  delete window.__progressWorkerModule;
  const progressWorker = typeof progressWorkerModule.createProgressWorkerModule === "function"
    ? progressWorkerModule.createProgressWorkerModule({ formatProgressValue })
    : {};
  const { progressWorkerPayload, progressWorkerRows, progressWorkerSummaryLine, formatWorkerProgressRow } = progressWorker;

  const progressCsvRerunModule = window.__progressCsvRerunModule || {};
  delete window.__progressCsvRerunModule;
  const progressCsvRerun = typeof progressCsvRerunModule.createProgressCsvRerunModule === "function"
    ? progressCsvRerunModule.createProgressCsvRerunModule({ progressWorkerRows })
    : {};

  function csvRerunTailEvidence(stdoutTail = null) { return progressCsvRerun.csvRerunTailEvidence(stdoutTail); }
  function csvRerunActivityEvidence(context = {}) { return progressCsvRerun.csvRerunActivityEvidence(context); }
  function csvRerunTerminalLine(line) { return progressCsvRerun.csvRerunTerminalLine(line); }
  function csvRerunTimelineDetail(evidence = {}, backendWorkEvidence = "") {
    return progressCsvRerun.csvRerunTimelineDetail(evidence, backendWorkEvidence);
  }
  function csvRerunTimelineEvidenceLine(evidence = {}, backendWorkEvidence = "") {
    return progressCsvRerun.csvRerunTimelineEvidenceLine(evidence, backendWorkEvidence);
  }


  const progressFfmpegEtaModule = window.__progressFfmpegEtaModule || {};
  delete window.__progressFfmpegEtaModule;
  const progressFfmpegEta = typeof progressFfmpegEtaModule.createProgressFfmpegEtaModule === "function"
    ? progressFfmpegEtaModule.createProgressFfmpegEtaModule({ formatProgressValue })
    : {};
  const { progressFfmpegPayload, progressFfmpegRows, progressFfmpegSummaryLine, formatFfmpegProgressRow, progressEtaPayload, progressEtaRows, formatEtaSeconds, progressEtaSummaryLine, formatEtaRow } = progressFfmpegEta;

  const progressBarPresentationModule = window.__progressBarPresentationModule || {};
  delete window.__progressBarPresentationModule;
  const progressBarPresentation = typeof progressBarPresentationModule.createProgressBarPresentationModule === "function"
    ? progressBarPresentationModule.createProgressBarPresentationModule({
        formatEtaSeconds,
        progressEtaRows,
        progressBarId,
        progressBarMode,
        progressBarPercent,
        progressBarPercentLabel,
        progressBarStatus,
        progressBarStatusLabel,
        progressUsePendingDrainCompactText,
        progressBarDisplayLabel,
        progressStepDisplayLabel,
        formatProgressUpdatedAt,
      })
    : {};
  const {
    progressTimelineGroupKey,
    compactProgressUpdatedAt,
    progressTimelineSortRank,
    sortedProgressTimelineBars,
    formatProgressBytes,
    formatProgressByteRate,
    progressEtaRowForBar,
    progressEtaTokensForBar,
    progressBarDetailPieces,
    progressTimelineTokens,
    createProgressTrack,
    progressStepItems,
    createProgressStepList,
    renderHomeProgressTimelineRow,
  } = progressBarPresentation;

  const progressAuditModule = window.__progressAuditModule || {};
  delete window.__progressAuditModule;
  const progressAudit = typeof progressAuditModule.createProgressAuditModule === "function"
    ? progressAuditModule.createProgressAuditModule({
        formatProgressValue,
        progressBarStatusLabel,
        renderProgressBarsInto: (...args) => renderProgressBarsInto(...args),
        setText,
      })
    : {};
  const {
    auditProgressPayload,
    rawAuditProgressBars,
    auditProgressIsStaleForUi,
    auditProgressBars,
    auditProgressStatus,
    auditProgressSummaryLines,
    renderAuditProgressInto,
  } = progressAudit;

  const progressEvidenceRowsModule = window.__progressEvidenceRowsModule || {};
  delete window.__progressEvidenceRowsModule;
  const progressEvidenceRowsAdapter = typeof progressEvidenceRowsModule.createProgressEvidenceRowsModule === "function"
    ? progressEvidenceRowsModule.createProgressEvidenceRowsModule({
        formatProgressValue,
        formatProgressUpdatedAt,
        normalizedProgressState,
        progressStateIsActive,
        progressLatestEvent,
        progressEventLabel,
        progressActiveJobRows,
        formatActiveJobEvidenceRow,
        progressWorkerRows,
        progressWorkerPayload,
        progressWorkerSummaryLine,
        formatWorkerProgressRow,
        progressFfmpegRows,
        progressFfmpegPayload,
        progressFfmpegSummaryLine,
        formatFfmpegProgressRow,
        progressEtaRows,
        progressEtaPayload,
        progressEtaSummaryLine,
        formatEtaRow,
        getActiveWorkProgressLine: () => activeWorkProgressLine,
        getActiveWorkRouteLine: () => activeWorkRouteLine,
        getActiveWorkQueueLine: () => activeWorkQueueLine,
        getActiveWorkControlLine: () => activeWorkControlLine,
      })
    : {};
  const { progressEvidenceRows } = progressEvidenceRowsAdapter;

  const progressEvidenceModule = window.__progressEvidenceModule || {};
  delete window.__progressEvidenceModule;
  const progressEvidence = typeof progressEvidenceModule.createProgressEvidenceModule === "function"
    ? progressEvidenceModule.createProgressEvidenceModule({
      progressEvidenceRows,
      progressEvidencePostureStatus,
      getSelectedKey: () => selectedProgressEvidenceKey,
      setSelectedKey: (value) => { selectedProgressEvidenceKey = value; },
      setProgressPanelStatus,
      setText,
      byId,
      clearRows,
      updateTableStatusLegend,
      appendCells,
      makeRowSelectable,
    })
    : {};

  function progressEvidenceStatus(rows = []) { return progressEvidence.progressEvidenceStatus(rows); }
  function progressEvidenceSummaryLines(rows = []) { return progressEvidence.progressEvidenceSummaryLines(rows); }
  function selectedProgressEvidenceRow(rows) { return progressEvidence.selectedProgressEvidenceRow(rows); }
  function progressEvidenceDetailLines(row) { return progressEvidence.progressEvidenceDetailLines(row); }
  function renderProgressEvidence(context = {}) { return progressEvidence.renderProgressEvidence(context); }

  function progressRowsForSource(source, progress, preferred) {
    const payload = progress && typeof progress === "object" ? progress : {};
    const preferredRows = preferred.filter((key) => payload[key] !== undefined && payload[key] !== null && payload[key] !== "");
    const extraRows = Object.keys(payload).filter((key) => !preferred.includes(key)).sort((a, b) => a.localeCompare(b));
    return [...preferredRows, ...extraRows].slice(0, 40).map((key) => ({
      source,
      field: key,
      value: payload[key],
    }));
  }

  const progressActiveWorkModule = window.__progressActiveWorkModule || {};
  delete window.__progressActiveWorkModule;
  const progressActiveWork = typeof progressActiveWorkModule.createProgressActiveWorkModule === "function"
    ? progressActiveWorkModule.createProgressActiveWorkModule({ formatProgressValue })
    : {};
  const { activeWorkProgressLine, activeWorkRouteLine, activeWorkQueueLine, activeWorkControlLine } = progressActiveWork;

  const progressDiagnosticsModule = window.__progressDiagnosticsModule || {};
  delete window.__progressDiagnosticsModule;
  const progressDiagnostics = typeof progressDiagnosticsModule.createProgressDiagnosticsModule === "function"
    ? progressDiagnosticsModule.createProgressDiagnosticsModule({
      formatProgressValue,
      progressRowsForSource,
      audioProgressLine,
      pendingDrainProgressLine,
      progressWorkerRows,
      formatWorkerProgressRow,
      progressFfmpegRows,
      formatFfmpegProgressRow,
      progressEtaRows,
      formatEtaRow,
      auditProgressIsStaleForUi,
      activeWorkProgressLine,
      activeWorkRouteLine,
      activeWorkQueueLine,
      activeWorkControlLine,
      progressWorkerSummaryLine,
      progressFfmpegSummaryLine,
      progressEtaSummaryLine,
      setText,
      renderProgressBarsInto: (...args) => renderProgressBarsInto(...args),
      progressWorkerPayload,
      byId,
      clearRows,
      appendCells,
    })
    : {};

  function diagnosticsProgressRows(snapshot, diagnostics = null) {
    return progressDiagnostics.diagnosticsProgressRows(snapshot, diagnostics);
  }

  function diagnosticsProgressStatus(snapshot, rows) {
    return progressDiagnostics.diagnosticsProgressStatus(snapshot, rows);
  }

  function diagnosticsProgressSummaryLines(snapshot, rows, diagnostics = null) {
    return progressDiagnostics.diagnosticsProgressSummaryLines(snapshot, rows, diagnostics);
  }

  function renderDiagnosticsProgress(snapshot = null, diagnostics = null) {
    return progressDiagnostics.renderDiagnosticsProgress(snapshot, diagnostics);
  }

  const progressTimelineCoreModule = window.__progressTimelineCoreModule || {};
  delete window.__progressTimelineCoreModule;
  const progressTimelineCore = typeof progressTimelineCoreModule.createProgressTimelineCoreModule === "function"
    ? progressTimelineCoreModule.createProgressTimelineCoreModule({
        formatProgressValue,
        progressBarId,
        progressBarStatus,
        progressBarsForStableDisplay,
        progressBarsWithOperatorStop,
        progressBarsWithStaleDisplayHysteresis,
        csvRerunActivityEvidence,
      })
    : {};
  const {
    timelineText,
    timelineHasMeaningfulText,
    timelineMeaningfulText,
    timelineLooksIdleWaiting,
    timelineBarById,
    timelineBarMatching,
    runTimelineBarStatus,
    normalizeRunTimelineStatus,
    runTimelineItem,
    runTimelineProgressContext,
    stageMentions,
    publishOrParkBar,
    runTimelinePublishStatus,
    runTimelineCompletionStatus,
    runTimelineMarkFocus,
    csvRerunCompletionSummary,
    csvRerunCompletionTimelineItems,
  } = progressTimelineCore;

  const progressLiveRunModule = window.__progressLiveRunModule || {};
  delete window.__progressLiveRunModule;
  const progressLiveRun = typeof progressLiveRunModule.createProgressLiveRunModule === "function"
    ? progressLiveRunModule.createProgressLiveRunModule({ formatProgressValue, progressNumericValue, csvRerunCompletionSummary, csvRerunActivityEvidence, timelineLooksIdleWaiting, compactProgressUpdatedAt, progressWorkerRows, progressEtaRows, progressFfmpegPayload, activeWorkProgressLine, activeWorkRouteLine, activeWorkQueueLine, activeWorkControlLine, progressWorkerSummaryLine, progressFfmpegSummaryLine, progressEtaSummaryLine, formatEtaSeconds, formatWorkerProgressRow, byId, setText, setProgressPanelStatus })
    : {};

  function latestEventLine(diagnostics, snapshot) { return progressLiveRun.latestEventLine(diagnostics, snapshot); }
  function liveRunStatus(context = {}) { return progressLiveRun.liveRunStatus(context); }
  function liveRunStripItems(context = {}) { return progressLiveRun.liveRunStripItems(context); }
  function renderLiveRunStrip(context = {}) { return progressLiveRun.renderLiveRunStrip(context); }
  function activeWorkNextStep(context = {}) { return progressLiveRun.activeWorkNextStep(context); }
  function renderHomeActiveWork(context = {}) { return progressLiveRun.renderHomeActiveWork(context); }

  const progressTimelineViewModule = window.__progressTimelineViewModule || {};
  delete window.__progressTimelineViewModule;
  const progressTimelineView = typeof progressTimelineViewModule.createProgressTimelineViewModule === "function"
    ? progressTimelineViewModule.createProgressTimelineViewModule({
        formatProgressValue,
        progressBarId,
        progressBarPercent,
        progressBarStatusLabel,
        progressBarDisplayLabel,
        progressBarDisplayStatusLabel,
        progressBarsForStableDisplay,
        progressBarsWithOperatorStop,
        progressBarsWithStaleDisplayHysteresis,
        progressBarDetailPieces,
        progressStepItems,
        createProgressTrack,
        createProgressStepList,
        progressTimelineTokens,
        setProgressPanelStatus,
        byId,
        csvRerunCompletionSummary,
        csvRerunCompletionTimelineItems,
        csvRerunTerminalLine,
        csvRerunTimelineDetail,
        csvRerunTimelineEvidenceLine,
        timelineText,
        timelineHasMeaningfulText,
        timelineLooksIdleWaiting,
        timelineBarById,
        timelineBarMatching,
        runTimelineBarStatus,
        runTimelineItem,
        runTimelineProgressContext,
        stageMentions,
        publishOrParkBar,
        runTimelinePublishStatus,
        runTimelineCompletionStatus,
        runTimelineMarkFocus,
        latestEventLine,
      })
    : {};
  const { runTimelineItems, runTimelinePanelStatus, renderHomeProgressTimeline, renderProgressBars } = progressTimelineView;
  renderProgressBarsInto = progressTimelineView.renderProgressBarsInto;


  /**
   * Public namespace for the shared progress module.
   * Progress consumers should use this namespace; no flat window.* exports remain for this module.
   */
  window.mediaPipelineProgressView = {
    formatProgressUpdatedAt,
    renderProgressBarsInto,
    renderProgressBars,
    runTimelineItems,
    auditProgressBars,
    auditProgressStatus,
    auditProgressSummaryLines,
    renderAuditProgressInto,
    renderProgressDetails,
    renderPipelineEvents,
    renderProgressEvidence,
    progressWorkerPayload,
    progressWorkerRows,
    progressWorkerSummaryLine,
    progressFfmpegPayload,
    progressFfmpegRows,
    progressFfmpegSummaryLine,
    progressEtaPayload,
    progressEtaRows,
    progressEtaSummaryLine,
    csvRerunTailEvidence,
    csvRerunActivityEvidence,
    csvRerunCompletionSummary,
    csvRerunTerminalLine,
    progressEvidenceRows,
    progressEvidenceStatus,
    progressEvidenceSummaryLines,
    progressEvidenceDetailLines,
    renderDiagnosticsProgress,
    renderLiveRunStrip,
    liveRunStripItems,
    liveRunStatus,
    diagnosticsProgressRows,
    diagnosticsProgressStatus,
    diagnosticsProgressSummaryLines,
    renderHomeActiveWork,
    activeWorkNextStep,
    activeWorkProgressLine,
    activeWorkRouteLine,
    activeWorkQueueLine,
    activeWorkControlLine,
    latestEventLine,
  };
})();
