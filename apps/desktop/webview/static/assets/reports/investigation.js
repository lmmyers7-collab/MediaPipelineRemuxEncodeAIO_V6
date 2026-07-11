(function () {
  function createReportsInvestigationModule(deps = {}) {
    const state = deps.state || {};
    const byId = typeof deps.byId === "function" ? deps.byId : () => null;
    const failureResolutionGroupKey = typeof deps.failureResolutionGroupKey === "function" ? deps.failureResolutionGroupKey : () => "";
    const normalizeFailureMarkerPaths = typeof deps.normalizeFailureMarkerPaths === "function" ? deps.normalizeFailureMarkerPaths : () => [];
    const failureRowsForGroup = typeof deps.failureRowsForGroup === "function" ? deps.failureRowsForGroup : () => [];
    const failureClearMarkerPathsForRow = typeof deps.failureClearMarkerPathsForRow === "function" ? deps.failureClearMarkerPathsForRow : () => [];
    const failureRowKey = typeof deps.failureRowKey === "function" ? deps.failureRowKey : () => "";
    const renderFailureResolutionGroups = typeof deps.renderFailureResolutionGroups === "function" ? deps.renderFailureResolutionGroups : () => {};
    const renderFailureRows = typeof deps.renderFailureRows === "function" ? deps.renderFailureRows : () => {};
    const updateFailureClearConfirmState = typeof deps.updateFailureClearConfirmState === "function" ? deps.updateFailureClearConfirmState : () => {};
    const updateFailureLifecycleConfirmState = typeof deps.updateFailureLifecycleConfirmState === "function" ? deps.updateFailureLifecycleConfirmState : () => {};
    const renderAuditRows = typeof deps.renderAuditRows === "function" ? deps.renderAuditRows : () => {};
    const activateReportsTab = typeof deps.activateReportsTab === "function" ? deps.activateReportsTab : () => {};

    function getSelectedFailureGroup() {
      if (!state.selectedFailureGroupKey) return state.lastFailureResolutionGroups?.[0] || null;
      return state.lastFailureResolutionGroups?.find((group) => failureResolutionGroupKey(group) === state.selectedFailureGroupKey)
        || state.lastFailureResolutionGroups?.[0]
        || null;
    }

    function selectedFailureGroupMarkerPaths() {
      const group = getSelectedFailureGroup();
      const groupPaths = normalizeFailureMarkerPaths(group?.clearable_marker_paths || []);
      if (groupPaths.length) return groupPaths;
      const seen = new Set();
      const paths = [];
      failureRowsForGroup(group).forEach((row) => {
        failureClearMarkerPathsForRow(row).forEach((markerPath) => {
          const key = markerPath.toLowerCase();
          if (markerPath && !seen.has(key)) {
            seen.add(key);
            paths.push(markerPath);
          }
        });
      });
      return paths;
    }

    function setReportChipPressed(selector, activeValue) {
      document.querySelectorAll(selector).forEach((button) => {
        const value = button.dataset.failureFilterChip || button.dataset.auditFilterChip || "all";
        button.setAttribute("aria-pressed", String(value === activeValue));
      });
    }

    function getSelectedFailureRow() {
      if (!state.selectedFailureRowKey) return null;
      return state.lastFailureRows?.find((row) => failureRowKey(row) === state.selectedFailureRowKey) || null;
    }

    function getSelectedFailureRows() {
      if (!state.selectedFailureRowKeys?.size) {
        const single = getSelectedFailureRow();
        return single ? [single] : [];
      }
      return (state.lastFailureRows || []).filter((row) => state.selectedFailureRowKeys.has(failureRowKey(row)));
    }

    function failureMarkerModeActive() {
      return String(state.lastFailurePreviewPayload?.source_kind || "").toLowerCase() === "markers";
    }

    function setFailureMarkerSourceMode(enabled) {
      const checkbox = byId("failure-source-markers");
      if (!checkbox) return false;
      checkbox.checked = Boolean(enabled);
      return true;
    }

    function reportNumber(value) {
      const numeric = Number(value);
      return Number.isFinite(numeric) ? numeric : 0;
    }

    function reportPreviewLoaded(payload, rows) {
      const warnings = Array.isArray(payload?.warnings) ? payload.warnings : [];
      return Boolean(
        payload?.source
        || payload?.source_kind
        || payload?.count !== undefined
        || payload?.error
        || warnings.length
        || (Array.isArray(rows) && rows.length)
      );
    }

    function reportCountBy(rows, keys, fallback = "unknown") {
      const keyList = Array.isArray(keys) ? keys : [keys];
      const counts = {};
      (Array.isArray(rows) ? rows : []).forEach((row) => {
        let value = "";
        keyList.some((key) => {
          value = String(row?.[key] || "").trim();
          return Boolean(value);
        });
        const normalized = value || fallback;
        counts[normalized] = (counts[normalized] || 0) + 1;
      });
      return counts;
    }

    function reportSortedCountEntries(counts, limit = 6) {
      return Object.entries(counts || {})
        .sort((left, right) => Number(right[1] || 0) - Number(left[1] || 0) || String(left[0]).localeCompare(String(right[0])))
        .slice(0, limit);
    }

    function reportFormatCounts(counts, limit = 6) {
      const entries = reportSortedCountEntries(counts, limit);
      return entries.length ? entries.map(([key, value]) => `${key}: ${value}`).join(", ") : "none";
    }

    function reportHumanLabel(value, fallback = "None") {
      const text = String(value || "").trim();
      if (!text) return fallback;
      const spaced = text.replace(/[_-]+/g, " ").replace(/\s+/g, " ").trim();
      if (spaced.length <= 4 && spaced === spaced.toUpperCase()) return spaced;
      return spaced.toLowerCase().replace(/\b[a-z]/g, (letter) => letter.toUpperCase());
    }

    function reportCompactCountPairs(counts, limit = 3, fallback = "None") {
      const entries = reportSortedCountEntries(counts, limit);
      if (!entries.length) return fallback;
      return entries.map(([key, value]) => `${reportHumanLabel(key)} ${value}`).join(" / ");
    }

    function focusReportsQuickLinkTarget(selector) {
      const target = selector ? document.querySelector(selector) : null;
      if (!target) return false;
      target.scrollIntoView?.({ block: "center", inline: "nearest" });
      if (!target.matches?.("a[href], button, input, select, textarea, summary, [tabindex]")) {
        target.setAttribute("tabindex", "-1");
      }
      target.focus?.({ preventScroll: true });
      return true;
    }

    function setFailureQuickFilter(chip) {
      state.activeFailureFilterChip = chip || "all";
      state.lastFailureClearPreview = null;
      state.lastFailureLifecyclePreview = null;
      setReportChipPressed("[data-failure-filter-chip]", state.activeFailureFilterChip);
      renderFailureResolutionGroups();
      renderFailureRows();
      updateFailureClearConfirmState();
      updateFailureLifecycleConfirmState();
      return focusReportsQuickLinkTarget("#failure-rows");
    }

    function setAuditQuickFilter(chip) {
      state.activeAuditFilterChip = chip || "all";
      setReportChipPressed("[data-audit-filter-chip]", state.activeAuditFilterChip);
      renderAuditRows();
      return focusReportsQuickLinkTarget("#audit-preview-rows");
    }

    function activateQuickLink(action) {
      const normalized = String(action || "").trim().toLowerCase();
      const failureFilters = {
        "failure-needs-action": "needs_action",
        "failure-working": "working",
        "failure-waiting-retry": "waiting_retry",
        "failure-ready-clear": "ready_to_clear",
        "failure-all": "all",
      };
      const auditFilters = {
        "audit-review": "review",
        "audit-high": "high",
        "audit-all": "all",
      };
      if (Object.prototype.hasOwnProperty.call(failureFilters, normalized)) {
        activateReportsTab("failures");
        return setFailureQuickFilter(failureFilters[normalized]);
      }
      if (Object.prototype.hasOwnProperty.call(auditFilters, normalized)) {
        activateReportsTab("audit");
        return setAuditQuickFilter(auditFilters[normalized]);
      }
      if (normalized === "locations" || normalized === "files") {
        activateReportsTab("files");
        return focusReportsQuickLinkTarget('[data-reports-tab-panel="files"]');
      }
      return true;
    }

    return {
      getSelectedFailureGroup,
      selectedFailureGroupMarkerPaths,
      setReportChipPressed,
      getSelectedFailureRow,
      getSelectedFailureRows,
      failureMarkerModeActive,
      setFailureMarkerSourceMode,
      reportNumber,
      reportPreviewLoaded,
      reportCountBy,
      reportFormatCounts,
      reportSortedCountEntries,
      reportHumanLabel,
      reportCompactCountPairs,
      focusReportsQuickLinkTarget,
      setFailureQuickFilter,
      setAuditQuickFilter,
      activateQuickLink,
    };
  }

  window.__reportsViewInvestigationModule = {
    createReportsInvestigationModule,
  };
})();
