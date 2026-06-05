(function () {
  const home = () => window.mediaPipelineAppHome || {};

  function renderHomeReadiness(context = {}) {
    return home().renderHomeReadiness?.(context);
  }

  function dailyDriverRows(context = {}) {
    return home().dailyDriverRows?.(context) || [];
  }

  function dailyDriverStatusClass(status) {
    return home().dailyDriverStatusClass?.(status) || "match";
  }

  function dailyDriverSummaryLines(rows = []) {
    return home().dailyDriverSummaryLines?.(rows) || [];
  }

  function dependencyStatusLabel(status) {
    return home().dependencyStatusLabel?.(status) || "review";
  }

  function homeProgressPercent(value) {
    return home().homeProgressPercent?.(value) || "";
  }

  function renderHomePendingCount(pending) {
    return home().renderHomePendingCount?.(pending);
  }

  function renderHomeNetworkRole(settings) {
    return home().renderHomeNetworkRole?.(settings);
  }

  function renderHomeStorageHealth(context = {}) {
    return home().renderHomeStorageHealth?.(context);
  }

  function renderHomeQueueSnapshot(queue) {
    return home().renderHomeQueueSnapshot?.(queue);
  }

  function renderHomeRecentCompleted(completed) {
    return home().renderHomeRecentCompleted?.(completed);
  }

  function renderHomePromotionEntry(status = {}) {
    return home().renderHomePromotionEntry?.(status);
  }

  function externalDependencyRows(context = {}) {
    return home().externalDependencyRows?.(context) || [];
  }

  function externalDependencyOverallStatus(context = {}) {
    return home().externalDependencyOverallStatus?.(context) || "unknown";
  }

  function externalDependencySummaryLines(context = {}) {
    return home().externalDependencySummaryLines?.(context) || [];
  }

  function externalDependencyEvidenceText(context = {}) {
    return home().externalDependencyEvidenceText?.(context) || "external dependency evidence not loaded";
  }

  function renderExternalDependencyDigest(context = {}) {
    return home().renderExternalDependencyDigest?.(context);
  }

  function renderHomeNextQueue(context = {}) {
    return home().renderHomeNextQueue?.(context);
  }

  function renderDailyDriverReadiness(context = {}) {
    return home().renderDailyDriverReadiness?.(context);
  }

  window.mediaPipelineAppHomeReadiness = {
    renderHomeReadiness,
    dailyDriverRows,
    dailyDriverStatusClass,
    dailyDriverSummaryLines,
    dependencyStatusLabel,
    homeProgressPercent,
    renderHomePendingCount,
    renderHomeNetworkRole,
    renderHomeStorageHealth,
    renderHomeQueueSnapshot,
    renderHomeRecentCompleted,
    renderHomePromotionEntry,
    externalDependencyRows,
    externalDependencyOverallStatus,
    externalDependencySummaryLines,
    externalDependencyEvidenceText,
    renderExternalDependencyDigest,
    renderHomeNextQueue,
    renderDailyDriverReadiness,
  };
})();
