// reports/auditView.js
// Audit rendering, selection, and score-policy UI helpers for reportsView.js.

(function () {
  "use strict";

  function noop() {}

  function createReportsAuditViewModule(deps = {}) {
    const reportsState = deps.state && typeof deps.state === "object" ? deps.state : {};
    const appendCells = typeof deps.appendCells === "function" ? deps.appendCells : noop;
    const appendReportOwnerNavigationButton = typeof deps.appendReportOwnerNavigationButton === "function" ? deps.appendReportOwnerNavigationButton : noop;
    const auditActionOwner = typeof deps.auditActionOwner === "function" ? deps.auditActionOwner : function () { return "Completed evidence review"; };
    const auditDiagnosticsActionsForRow = typeof deps.auditDiagnosticsActionsForRow === "function" ? deps.auditDiagnosticsActionsForRow : function () { return []; };
    const auditEmptyStateMessage = typeof deps.auditEmptyStateMessage === "function" ? deps.auditEmptyStateMessage : function () { return "No audit rows available."; };
    const auditMatchesChip = typeof deps.auditMatchesChip === "function" ? deps.auditMatchesChip : function () { return true; };
    const auditReviewBoardLines = typeof deps.auditReviewBoardLines === "function" ? deps.auditReviewBoardLines : function () { return []; };
    const auditReviewStatus = typeof deps.auditReviewStatus === "function" ? deps.auditReviewStatus : function () { return "No rows"; };
    const auditRowKey = typeof deps.auditRowKey === "function" ? deps.auditRowKey : function () { return ""; };
    const byId = typeof deps.byId === "function" ? deps.byId : function () { return null; };
    const clearRows = typeof deps.clearRows === "function" ? deps.clearRows : noop;
    const diagnosticsBridgeApi = typeof deps.diagnosticsBridgeApi === "function" ? deps.diagnosticsBridgeApi : function () { return {}; };
    const filterRows = typeof deps.filterRows === "function" ? deps.filterRows : function (rows) { return Array.isArray(rows) ? rows : []; };
    const hiddenSelectedCount = typeof deps.hiddenSelectedCount === "function" ? deps.hiddenSelectedCount : function () { return 0; };
    const makeRowSelectable = typeof deps.makeRowSelectable === "function" ? deps.makeRowSelectable : noop;
    const renderReportDiagnosticsActions = typeof deps.renderReportDiagnosticsActions === "function" ? deps.renderReportDiagnosticsActions : noop;
    const renderReportTriage = typeof deps.renderReportTriage === "function" ? deps.renderReportTriage : noop;
    const reportAuditScoreFieldIds = deps.reportAuditScoreFieldIds && typeof deps.reportAuditScoreFieldIds === "object" ? deps.reportAuditScoreFieldIds : {};
    const reportAuditScoreGroupDefaultKeys = deps.reportAuditScoreGroupDefaultKeys && typeof deps.reportAuditScoreGroupDefaultKeys === "object" ? deps.reportAuditScoreGroupDefaultKeys : {};
    const reportRenderedRows = typeof deps.reportRenderedRows === "function" ? deps.reportRenderedRows : function (rows) { return Array.isArray(rows) ? rows : []; };
    const reportTableStatusText = typeof deps.reportTableStatusText === "function" ? deps.reportTableStatusText : function (visibleCount, totalCount) { return `${visibleCount} / ${totalCount}`; };
    const rowKeySet = typeof deps.rowKeySet === "function" ? deps.rowKeySet : function () { return new Set(); };
    const setReportChipPressed = typeof deps.setReportChipPressed === "function" ? deps.setReportChipPressed : noop;
    const setText = typeof deps.setText === "function" ? deps.setText : noop;
    const updateTableStatusLegend = typeof deps.updateTableStatusLegend === "function" ? deps.updateTableStatusLegend : noop;

    function visibleAuditRows() {
      const filterText = byId("audit-preview-filter")?.value || "";
      return filterRows(reportsState.lastAuditRows, filterText, [
        "path",
        "relative_path",
        "lookup_title",
        "media_type",
        "effective_bucket",
        "priority_fix_level",
        "primary_issue_code",
        "primary_suggested_action",
        "issue_messages",
      ]).filter((row) => auditMatchesChip(row, reportsState.activeAuditFilterChip));
    }

    function hiddenSelectedAuditCount(rows = visibleAuditRows()) {
      return hiddenSelectedCount(reportsState.selectedAuditRowKeys, rows, auditRowKey);
    }

    function hiddenAuditSelectionMessage(actionLabel = "audit selected action") {
      const count = hiddenSelectedAuditCount();
      return `${count} selected audit row${count === 1 ? " is" : "s are"} hidden by the active filter/search. Return to All and clear search, or deselect hidden rows before ${actionLabel}.`;
    }

    function auditScoreValue(item) {
      const score = Number(item?.priority_score);
      return Number.isFinite(score) ? score : 0;
    }

    function auditScoreThresholdValue() {
      const input = document.querySelector("[data-audit-score-threshold-input]");
      const raw = String(input?.value || "").trim();
      if (!raw) return null;
      const value = Number(raw);
      return Number.isFinite(value) ? value : null;
    }

    function formatAuditScoreThreshold(value) {
      return Number.isInteger(value) ? String(value) : String(value);
    }

    function auditCompletionTimestamp(source) {
      const match = String(source || "").match(/audit_summary_(\d{8})_(\d{6})(?:\.priority)?\.csv$/i);
      if (!match) return "";
      const [, datePart, timePart] = match;
      const completedAt = new Date(
        Number(datePart.slice(0, 4)),
        Number(datePart.slice(4, 6)) - 1,
        Number(datePart.slice(6, 8)),
        Number(timePart.slice(0, 2)),
        Number(timePart.slice(2, 4)),
        Number(timePart.slice(4, 6)),
      );
      if (Number.isNaN(completedAt.getTime())) return "";
      return completedAt.toLocaleString(undefined, {
        year: "numeric",
        month: "short",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      });
    }

    function updateAuditSelectionControls(rows = visibleAuditRows()) {
      const visibleCount = Array.isArray(rows) ? rows.length : 0;
      document.querySelectorAll("[data-audit-selection-action]").forEach((button) => {
        const action = button.dataset.auditSelectionAction || "";
        button.onclick = () => runAuditSelectionAction(action);
        button.disabled = action === "clear" ? !reportsState.selectedAuditRowKeys.size : !visibleCount;
      });
      const thresholdInput = document.querySelector("[data-audit-score-threshold-input]");
      if (thresholdInput) thresholdInput.disabled = !reportsState.lastAuditRows.length;
    }

    function getSelectedAuditRow() {
      if (!reportsState.selectedAuditRowKey) return null;
      return reportsState.lastAuditRows.find((row) => auditRowKey(row) === reportsState.selectedAuditRowKey) || null;
    }

    function setAuditSelectionFromRows(rows, actionLabel, emptyMessage = "") {
      reportsState.selectedAuditRowKeys = rowKeySet(rows, auditRowKey);
      if (!reportsState.selectedAuditRowKeys.has(reportsState.selectedAuditRowKey)) {
        reportsState.selectedAuditRowKey = Array.from(reportsState.selectedAuditRowKeys)[0] || "";
      }
      renderAuditDetail(getSelectedAuditRow());
      renderAuditRows();
      const count = reportsState.selectedAuditRowKeys.size;
      setText("report-audit-export-status", count ? `${count} selected` : "No selection");
      setText("report-audit-export-detail", count
        ? `${actionLabel}: selected ${count} audit row${count === 1 ? "" : "s"} from the current filter/search. Ignore and Export submit these row keys only.`
        : emptyMessage || `${actionLabel}: no audit rows matched the current filter/search.`);
    }

    function selectVisibleAuditRows() {
      setAuditSelectionFromRows(visibleAuditRows(), "Select All");
    }

    function selectAuditRowsAtOrAboveScore() {
      const threshold = auditScoreThresholdValue();
      if (threshold === null) {
        setText("report-audit-export-status", "Enter score");
        setText("report-audit-export-detail", "Enter a minimum audit score before selecting rows by score.");
        return;
      }
      const rows = visibleAuditRows().filter((row) => auditScoreValue(row) >= threshold);
      const label = `Select Score or Higher (${formatAuditScoreThreshold(threshold)})`;
      setAuditSelectionFromRows(rows, label, `No visible audit rows have score at or above ${formatAuditScoreThreshold(threshold)}.`);
    }

    function clearAuditSelection() {
      reportsState.selectedAuditRowKeys = new Set();
      reportsState.selectedAuditRowKey = "";
      renderAuditDetail(null);
      renderAuditRows();
      setText("report-audit-export-status", "No selection");
      setText("report-audit-export-detail", "Cleared selected audit rows. Export without selected row keys still uses backend default scope.");
    }

    function runAuditSelectionAction(action) {
      if (action === "select-visible") selectVisibleAuditRows();
      if (action === "select-score-at-least") selectAuditRowsAtOrAboveScore();
      if (action === "clear") clearAuditSelection();
    }

    function renderAuditPreview(audit) {
      const payload = audit || {};
      reportsState.lastAuditPreviewPayload = payload;
      const rows = Array.isArray(payload.rows) ? payload.rows : [];
      reportsState.lastAuditRows = rows;
      if (reportsState.selectedAuditRowKey && !rows.some((row) => auditRowKey(row) === reportsState.selectedAuditRowKey)) {
        reportsState.selectedAuditRowKey = "";
      }
      const availableKeys = new Set(rows.map((row) => auditRowKey(row)).filter(Boolean));
      reportsState.selectedAuditRowKeys = new Set(Array.from(reportsState.selectedAuditRowKeys).filter((key) => availableKeys.has(key)));
      reportsState.lastAuditEmptyMessage = auditEmptyStateMessage(payload, rows);
      const completedAt = auditCompletionTimestamp(payload.source);
      const summary = [
        completedAt ? `Audit completed: ${completedAt}` : "",
        payload.source ? `Source: ${payload.source}` : "",
        `Priority CSV mode: ${payload.priority_only ? "yes" : "no"}`,
        `Rows: ${payload.count || rows.length || 0}`,
        `Ignored rows hidden: ${payload.ignored_count || 0}`,
        `Priority rows: ${payload.priority_count ?? payload.high_priority_count ?? 0}`,
        `High priority: ${payload.high_priority_count || 0}`,
        `Medium priority: ${payload.medium_priority_count || 0}`,
        `Rerun: ${payload.rerun_count || 0}`,
        `Redownload: ${payload.redownload_count || 0}`,
        `Review: ${payload.review_count || 0}`,
        `Duplicate groups: ${payload.duplicate_group_count || 0}`,
        ...(payload.warnings || []),
        !rows.length ? auditEmptyStateMessage(payload, rows) : "",
      ].filter(Boolean);
      setText("audit-preview-summary", summary.join("\n") || "No audit preview loaded.");
      renderAuditDetail(getSelectedAuditRow());
      renderAuditRows();
      renderReportTriage();
    }

    function renderAuditReviewBoard() {
      setText("audit-review-status", auditReviewStatus());
      setText("audit-review-board", auditReviewBoardLines().join("\n"));
    }

    function selectedAuditRowKeysList() {
      return Array.from(reportsState.selectedAuditRowKeys).filter(Boolean);
    }

    function reportAuditScoreInputId(code) {
      return `report-audit-score-issue-${String(code || "").replace(/[^A-Za-z0-9_-]/g, "-")}`;
    }

    function reportAuditScoreValue(policy, defaults, key) {
      return policy[key] ?? defaults[key] ?? 0;
    }

    function reportAuditScoreIssueValue(policy, defaults, marker) {
      const code = String(marker?.code || "");
      const groupKey = reportAuditScoreGroupDefaultKeys[String(marker?.group || "")] || "";
      return policy.issue_code_weights?.[code]
        ?? defaults.issue_code_weights?.[code]
        ?? (groupKey ? reportAuditScoreValue(policy, defaults, groupKey) : 0);
    }

    function reportSyncAuditScoreIssueDefaults(group) {
      const groupKey = reportAuditScoreGroupDefaultKeys[group];
      if (!groupKey) return;
      const source = byId(reportAuditScoreFieldIds[groupKey]);
      if (!source) return;
      const raw = Number(source.value);
      const value = Number.isFinite(raw) ? Math.max(0, Math.min(1000, Math.round(raw))) : 0;
      const details = byId("report-audit-score-redownload-bucket")?.closest("details");
      if (!details) return;
      details.querySelectorAll(`[data-audit-score-issue-group="${group}"]`).forEach((input) => {
        if (input.dataset.auditScoreDirty === "true") return;
        input.value = String(value);
      });
    }

    function bindReportAuditScoreGroupInputs() {
      Object.entries(reportAuditScoreGroupDefaultKeys).forEach(([group, key]) => {
        const input = byId(reportAuditScoreFieldIds[key]);
        if (!input || input.dataset.auditScoreGroupBound === "true") return;
        input.dataset.auditScoreGroupBound = "true";
        input.addEventListener("input", () => reportSyncAuditScoreIssueDefaults(group));
      });
    }

    function renderReportAuditIssueRows(score, group, beforeKey) {
      const details = byId("report-audit-score-redownload-bucket")?.closest("details");
      const anchor = byId(reportAuditScoreFieldIds[beforeKey])?.closest("tr");
      if (!details || !anchor || !anchor.parentNode) return;
      details.querySelectorAll(`[data-audit-score-policy-dynamic-row="${group}"]`).forEach((row) => row.remove());
      const policy = score.policy && typeof score.policy === "object" ? score.policy : {};
      const defaults = score.defaults && typeof score.defaults === "object" ? score.defaults : {};
      const markers = Array.isArray(score.markers) ? score.markers : [];
      markers
        .filter((marker) => marker?.type === "issue_code" && marker?.group === group)
        .forEach((marker) => {
          const code = String(marker.code || "");
          if (!code) return;
          const row = document.createElement("tr");
          row.dataset.auditScorePolicyDynamicRow = group;

          const issueCell = document.createElement("td");
          const label = document.createElement("label");
          label.setAttribute("for", reportAuditScoreInputId(code));
          label.append(`${group === "high" ? "High" : "Medium"} issue: `);
          const codeNode = document.createElement("code");
          codeNode.textContent = code;
          label.appendChild(codeNode);
          issueCell.appendChild(label);

          const pointsCell = document.createElement("td");
          pointsCell.className = "num";
          const input = document.createElement("input");
          input.id = reportAuditScoreInputId(code);
          input.type = "number";
          input.min = "0";
          input.max = "1000";
          input.step = "1";
          const issueValue = reportAuditScoreIssueValue(policy, defaults, marker);
          const groupKey = reportAuditScoreGroupDefaultKeys[group] || "";
          const groupValue = groupKey ? reportAuditScoreValue(policy, defaults, groupKey) : issueValue;
          input.value = String(issueValue);
          input.dataset.auditScoreIssueCode = code;
          input.dataset.auditScoreIssueGroup = group;
          input.dataset.auditScoreDirty = issueValue === groupValue ? "false" : "true";
          input.addEventListener("input", () => { input.dataset.auditScoreDirty = "true"; });
          pointsCell.appendChild(input);

          const appliesCell = document.createElement("td");
          appliesCell.textContent = marker.applies_when || "";

          row.append(issueCell, pointsCell, appliesCell);
          anchor.parentNode.insertBefore(row, anchor);
        });
    }

    function renderAuditControls(payload) {
      reportsState.lastAuditControls = payload && typeof payload === "object" ? payload : {};
      const score = reportsState.lastAuditControls.score_policy && typeof reportsState.lastAuditControls.score_policy === "object"
        ? reportsState.lastAuditControls.score_policy
        : {};
      const policy = score.policy && typeof score.policy === "object" ? score.policy : {};
      const defaults = score.defaults && typeof score.defaults === "object" ? score.defaults : {};
      Object.entries(reportAuditScoreFieldIds).forEach(([key, id]) => {
        const input = byId(id);
        if (!input) return;
        input.value = String(policy[key] ?? defaults[key] ?? 0);
      });
      bindReportAuditScoreGroupInputs();
      renderReportAuditIssueRows(score, "high", "rerun_bucket");
      renderReportAuditIssueRows(score, "medium", "review_bucket");
      const ignoreManifest = reportsState.lastAuditControls.ignore_manifest && typeof reportsState.lastAuditControls.ignore_manifest === "object"
        ? reportsState.lastAuditControls.ignore_manifest
        : {};
      const ignoredCount = Number(ignoreManifest.entry_count || 0);
      const scoreValid = score.valid !== false;
      const ignoreValid = ignoreManifest.valid !== false;
      setText("report-audit-score-policy-status", scoreValid ? (score.persisted ? "Saved" : "Defaults") : "Invalid");
      setText("report-audit-score-policy-summary", [
        `Score policy source: ${score.persisted ? "saved state" : "defaults"}${scoreValid ? "" : " (invalid policy)"}`,
        ...(!scoreValid && score.error ? [`Audit score policy error: ${score.error}`] : []),
        `Audit ignore entries: ${ignoredCount}${ignoreValid ? "" : " (invalid manifest)"}`,
        ...(!ignoreValid && ignoreManifest.error ? [`Audit ignore manifest error: ${ignoreManifest.error}`] : []),
        `Policy path: ${score.path || "not configured"}`,
        "Advanced score controls: enable Advanced mode, then open Advanced score controls to edit point issues.",
        "Boundary: score and ignore controls affect audit reporting/export only; they do not write queue priority, file overrides, settings, or media files.",
      ].join("\n"));
    }

    function selectAuditRow(item) {
      reportsState.selectedAuditRowKey = auditRowKey(item);
      renderAuditDetail(item || null);
      renderAuditRows();
    }

    function toggleAuditRowSelection(item, checked) {
      const key = auditRowKey(item);
      if (!key) return;
      if (checked) {
        reportsState.selectedAuditRowKeys.add(key);
        reportsState.selectedAuditRowKey = key;
      } else {
        reportsState.selectedAuditRowKeys.delete(key);
        if (reportsState.selectedAuditRowKey === key) {
          reportsState.selectedAuditRowKey = Array.from(reportsState.selectedAuditRowKeys)[0] || "";
        }
      }
      renderAuditDetail(getSelectedAuditRow());
      renderAuditRows();
    }

    function renderAuditDetail(item) {
      if (!item) {
        setText("audit-preview-detail", "No audit row selected. Select a row to inspect priority score, issue bucket, suggested action, and source CSV.");
        renderReportDiagnosticsActions("audit-preview-diagnostics-actions", auditDiagnosticsActionsForRow(null), "Reports audit page");
        return;
      }
      const bridge = diagnosticsBridgeApi();
      const handoffLines = typeof bridge.diagnosticsBridgeHandoffLines === "function"
        ? bridge.diagnosticsBridgeHandoffLines("Reports audit selected row", auditDiagnosticsActionsForRow(item), {
          evidence: [
            item.effective_bucket ? `bucket=${item.effective_bucket}` : "",
            item.priority_fix_level || item.priority_score ? `priority=${item.priority_fix_level || ""} ${item.priority_score || ""}`.trim() : "",
            item.primary_issue_code ? `issue=${item.primary_issue_code}` : "",
            item.path ? `path=${item.path}` : "",
          ],
          safeAction: "compare Latest Audit CSV, Completed Manifest, Queue Snapshot, and Run Logs before CSV rerun or library decisions.",
        })
        : [];
      const detail = [
        ...handoffLines,
        "",
        `Title: ${item.lookup_title || ""}`,
        `Media: ${item.media_type || ""}`,
        `Bucket: ${item.effective_bucket || ""}`,
        `Priority: ${item.priority_fix_level || ""} (${item.priority_score || 0})`,
        `Issue: ${item.primary_issue_code || ""}`,
        `Suggested action: ${item.primary_suggested_action || ""}`,
        `Messages: ${item.issue_messages || ""}`,
        "",
        "Owner routing",
        "Evidence owner: Diagnostics",
        `Action owner: ${auditActionOwner(item)}`,
        "",
        `Path: ${item.path || ""}`,
        `Relative: ${item.relative_path || ""}`,
        `Source CSV: ${item.source_csv || ""}`,
        `Row key: ${auditRowKey(item)}`,
        `Ignored: ${item.ignored ? "yes" : "no"}`,
      ];
      setText("audit-preview-detail", detail.join("\n"));
      renderReportDiagnosticsActions("audit-preview-diagnostics-actions", auditDiagnosticsActionsForRow(item), "Reports audit selected row");
      appendReportOwnerNavigationButton(byId("audit-preview-diagnostics-actions"), auditActionOwner(item));
    }

    function renderAuditRows() {
      setReportChipPressed("[data-audit-filter-chip]", reportsState.activeAuditFilterChip);
      const rows = visibleAuditRows();
      const selectedCount = reportsState.selectedAuditRowKeys.size;
      const hiddenCount = hiddenSelectedAuditCount(rows);
      updateAuditSelectionControls(rows);
      setText("audit-preview-status", reportTableStatusText(rows.length, reportsState.lastAuditRows.length, selectedCount, hiddenCount));
      setText("report-audit-export-status", selectedCount
        ? `${selectedCount} selected${hiddenCount ? `, ${hiddenCount} hidden by filter` : ""}`
        : "All loaded (filter not applied)");
      const tbody = byId("audit-preview-rows");
      if (!rows.length) {
        clearRows(tbody, 8, reportsState.lastAuditRows.length ? "No audit rows match the filter." : reportsState.lastAuditEmptyMessage);
        updateTableStatusLegend("audit-preview-table-legend", tbody, "Audit rows");
        return;
      }
      tbody.replaceChildren();
      reportRenderedRows(rows).forEach((item) => {
        const row = document.createElement("tr");
        const bucket = String(item.effective_bucket || "").toUpperCase();
        const priority = String(item.priority_fix_level || "").toUpperCase();
        row.dataset.status = bucket === "REDOWNLOAD_CANDIDATE" ? "blocked" : bucket === "RERUN_PIPELINE" || priority === "HIGH" ? "warning" : bucket === "OK" ? "match" : "";
        const key = auditRowKey(item);
        row.dataset.rowKey = key;
        const selectCell = document.createElement("td");
        const checkbox = document.createElement("input");
        checkbox.type = "checkbox";
        checkbox.checked = Boolean(key && reportsState.selectedAuditRowKeys.has(key));
        checkbox.setAttribute("aria-label", `Select audit row ${item.lookup_title || item.relative_path || item.path || ""}`);
        checkbox.addEventListener("click", (event) => event.stopPropagation());
        checkbox.addEventListener("change", () => toggleAuditRowSelection(item, checkbox.checked));
        selectCell.appendChild(checkbox);
        row.appendChild(selectCell);
        appendCells(row, [
          item.priority_score || "",
          item.priority_fix_level || "",
          item.effective_bucket || "",
          item.media_type || "",
          item.lookup_title || item.relative_path || item.path || "",
          item.primary_issue_code || item.issue_messages || item.primary_suggested_action || "",
          auditActionOwner(item),
        ], ["num", null, null, null, null, null, null]);
        ["Select", "Score", "Priority", "Bucket", "Media", "Title", "Issue", "Owner"].forEach((label, index) => {
          if (row.children[index]) row.children[index].dataset.label = label;
        });
        makeRowSelectable(row, () => selectAuditRow(item), {
          selected: Boolean(key && key === reportsState.selectedAuditRowKey),
          label: `Audit row ${item.lookup_title || item.relative_path || item.path || ""}`,
        });
        tbody.appendChild(row);
      });
      updateTableStatusLegend("audit-preview-table-legend", tbody, "Audit rows");
    }

    return {
      auditScoreThresholdValue,
      clearAuditSelection,
      getSelectedAuditRow,
      hiddenAuditSelectionMessage,
      hiddenSelectedAuditCount,
      renderAuditControls,
      renderAuditDetail,
      renderAuditPreview,
      renderAuditReviewBoard,
      renderAuditRows,
      runAuditSelectionAction,
      selectedAuditRowKeysList,
      selectAuditRow,
      selectAuditRowsAtOrAboveScore,
      selectVisibleAuditRows,
      toggleAuditRowSelection,
      updateAuditSelectionControls,
      visibleAuditRows,
    };
  }

  window.__reportsViewAuditViewModule = {
    createReportsAuditViewModule,
  };
})();
