// reports/failureView.js
// Failure rendering and selection helpers for reportsView.js. Backend command
// requests and confirmation-gated mutations live in reports/failureCommands.js.

(function () {
  "use strict";

  function noop() {}

  function createReportsFailureViewModule(deps = {}) {
    const reportsState = deps.state && typeof deps.state === "object" ? deps.state : {};
    const appendCells = typeof deps.appendCells === "function" ? deps.appendCells : noop;
    const appendReportOwnerNavigationButton = typeof deps.appendReportOwnerNavigationButton === "function" ? deps.appendReportOwnerNavigationButton : noop;
    const byId = typeof deps.byId === "function" ? deps.byId : function () { return null; };
    const clearRows = typeof deps.clearRows === "function" ? deps.clearRows : noop;
    const configureFailurePrimaryAction = typeof deps.configureFailurePrimaryAction === "function" ? deps.configureFailurePrimaryAction : noop;
    const failureActionOwner = typeof deps.failureActionOwner === "function" ? deps.failureActionOwner : function () { return "Diagnostics"; };
    const failureClassificationText = typeof deps.failureClassificationText === "function" ? deps.failureClassificationText : function () { return "review"; };
    const failureCountsForRows = typeof deps.failureCountsForRows === "function" ? deps.failureCountsForRows : function () { return {}; };
    const failureDiagnosticsActionsForGroup = typeof deps.failureDiagnosticsActionsForGroup === "function" ? deps.failureDiagnosticsActionsForGroup : function () { return []; };
    const failureDiagnosticsActionsForRow = typeof deps.failureDiagnosticsActionsForRow === "function" ? deps.failureDiagnosticsActionsForRow : function () { return []; };
    const failureEmptyStateMessage = typeof deps.failureEmptyStateMessage === "function" ? deps.failureEmptyStateMessage : function () { return "No failure rows available."; };
    const failureEvidenceProofLines = typeof deps.failureEvidenceProofLines === "function" ? deps.failureEvidenceProofLines : function () { return []; };
    const failureFileText = typeof deps.failureFileText === "function" ? deps.failureFileText : function () { return "Unknown file"; };
    const failureGroupLifecycleState = typeof deps.failureGroupLifecycleState === "function" ? deps.failureGroupLifecycleState : function () { return "new"; };
    const failureGroupMatchesChip = typeof deps.failureGroupMatchesChip === "function" ? deps.failureGroupMatchesChip : function () { return true; };
    const failureGroupSearchText = typeof deps.failureGroupSearchText === "function" ? deps.failureGroupSearchText : function () { return ""; };
    const failureMarkerModeActive = typeof deps.failureMarkerModeActive === "function" ? deps.failureMarkerModeActive : function () { return false; };
    const failureMatchesChip = typeof deps.failureMatchesChip === "function" ? deps.failureMatchesChip : function () { return true; };
    const failurePlainSummaryText = typeof deps.failurePlainSummaryText === "function" ? deps.failurePlainSummaryText : function () { return ""; };
    const failureReasonText = typeof deps.failureReasonText === "function" ? deps.failureReasonText : function () { return "Review failure evidence."; };
    const failureRecordedText = typeof deps.failureRecordedText === "function" ? deps.failureRecordedText : function () { return "not recorded"; };
    const failureResolutionGroupKey = typeof deps.failureResolutionGroupKey === "function" ? deps.failureResolutionGroupKey : function () { return ""; };
    const failureResolutionGroupForRow = typeof deps.failureResolutionGroupForRow === "function" ? deps.failureResolutionGroupForRow : function () { return null; };
    const failureResolutionGroupsFromPayload = typeof deps.failureResolutionGroupsFromPayload === "function" ? deps.failureResolutionGroupsFromPayload : function (_payload, rows) { return Array.isArray(rows) ? [] : []; };
    const failureResolutionPrimaryAction = typeof deps.failureResolutionPrimaryAction === "function" ? deps.failureResolutionPrimaryAction : function () { return { label: "Review details", kind: "review_details" }; };
    const failureResolutionSummaryPayload = typeof deps.failureResolutionSummaryPayload === "function" ? deps.failureResolutionSummaryPayload : function () { return {}; };
    const failureRetryDetailLines = typeof deps.failureRetryDetailLines === "function" ? deps.failureRetryDetailLines : function () { return []; };
    const failureRetryPreviewSummaryLine = typeof deps.failureRetryPreviewSummaryLine === "function" ? deps.failureRetryPreviewSummaryLine : function () { return ""; };
    const failureReviewBoardLines = typeof deps.failureReviewBoardLines === "function" ? deps.failureReviewBoardLines : function () { return []; };
    const failureReviewBoardTiles = typeof deps.failureReviewBoardTiles === "function" ? deps.failureReviewBoardTiles : function () { return []; };
    const failureReviewStatus = typeof deps.failureReviewStatus === "function" ? deps.failureReviewStatus : function () { return "Waiting"; };
    const failureReviewTileNode = typeof deps.failureReviewTileNode === "function" ? deps.failureReviewTileNode : function (tile) {
      const section = document.createElement("section");
      section.textContent = tile?.value || tile?.label || "";
      return section;
    };
    const failureRowKey = typeof deps.failureRowKey === "function" ? deps.failureRowKey : function () { return ""; };
    const failureRowsForGroup = typeof deps.failureRowsForGroup === "function" ? deps.failureRowsForGroup : function () { return []; };
    const failureSeverity = typeof deps.failureSeverity === "function" ? deps.failureSeverity : function () { return "info"; };
    const failureStageText = typeof deps.failureStageText === "function" ? deps.failureStageText : function () { return "review"; };
    const failureStatusLabel = typeof deps.failureStatusLabel === "function" ? deps.failureStatusLabel : function () { return "Review"; };
    const failureSuggestedActionText = typeof deps.failureSuggestedActionText === "function" ? deps.failureSuggestedActionText : function () { return "Review diagnostics before retry."; };
    const failureTableEvidenceText = typeof deps.failureTableEvidenceText === "function" ? deps.failureTableEvidenceText : function () { return ""; };
    const failureTransition = typeof deps.failureTransition === "function" ? deps.failureTransition : function () { return null; };
    const filterRows = typeof deps.filterRows === "function" ? deps.filterRows : function (rows) { return Array.isArray(rows) ? rows : []; };
    const getSelectedFailureGroup = typeof deps.getSelectedFailureGroup === "function" ? deps.getSelectedFailureGroup : function () { return null; };
    const getSelectedFailureRow = typeof deps.getSelectedFailureRow === "function" ? deps.getSelectedFailureRow : function () { return null; };
    const hiddenSelectedCount = typeof deps.hiddenSelectedCount === "function" ? deps.hiddenSelectedCount : function () { return 0; };
    const makeRowSelectable = typeof deps.makeRowSelectable === "function" ? deps.makeRowSelectable : noop;
    const normalizeFailureMarkerPaths = typeof deps.normalizeFailureMarkerPaths === "function" ? deps.normalizeFailureMarkerPaths : function (paths) { return Array.isArray(paths) ? paths.filter(Boolean) : []; };
    const renderReportDiagnosticsActions = typeof deps.renderReportDiagnosticsActions === "function" ? deps.renderReportDiagnosticsActions : noop;
    const renderReportTriage = typeof deps.renderReportTriage === "function" ? deps.renderReportTriage : noop;
    const reportNumber = typeof deps.reportNumber === "function" ? deps.reportNumber : function (value) { const numeric = Number(value); return Number.isFinite(numeric) ? numeric : 0; };
    const reportRenderedRows = typeof deps.reportRenderedRows === "function" ? deps.reportRenderedRows : function (rows) { return Array.isArray(rows) ? rows : []; };
    const reportRenderedRowsNote = typeof deps.reportRenderedRowsNote === "function" ? deps.reportRenderedRowsNote : function () { return ""; };
    const reportTableStatusText = typeof deps.reportTableStatusText === "function" ? deps.reportTableStatusText : function (visibleCount, totalCount) { return `${visibleCount} / ${totalCount}`; };
    const rowKeySet = typeof deps.rowKeySet === "function" ? deps.rowKeySet : function () { return new Set(); };
    const runFailurePrimaryAction = typeof deps.runFailurePrimaryAction === "function" ? deps.runFailurePrimaryAction : noop;
    const setCellStatusChip = typeof deps.setCellStatusChip === "function" ? deps.setCellStatusChip : null;
    const setFailureLifecycleButton = typeof deps.setFailureLifecycleButton === "function" ? deps.setFailureLifecycleButton : noop;
    const setReportChipPressed = typeof deps.setReportChipPressed === "function" ? deps.setReportChipPressed : noop;
    const setText = typeof deps.setText === "function" ? deps.setText : noop;
    const setTextState = typeof deps.setTextState === "function" ? deps.setTextState : noop;
    const updateFailureClearConfirmState = typeof deps.updateFailureClearConfirmState === "function" ? deps.updateFailureClearConfirmState : noop;
    const updateFailureLifecycleConfirmState = typeof deps.updateFailureLifecycleConfirmState === "function" ? deps.updateFailureLifecycleConfirmState : noop;
    const updateTableStatusLegend = typeof deps.updateTableStatusLegend === "function" ? deps.updateTableStatusLegend : noop;

  function renderFailurePreview(failures) {
      reportsState.lastFailurePreviewPayload = failures || {};
      reportsState.lastFailureClearPreview = null;
      reportsState.lastFailureLifecyclePreview = null;
      const rows = Array.isArray(failures.rows) ? failures.rows : [];
      reportsState.lastFailureRows = rows;
      reportsState.lastFailureResolutionGroups = failureResolutionGroupsFromPayload(failures, rows);
      const availableGroupKeys = new Set(reportsState.lastFailureResolutionGroups.map((group) => failureResolutionGroupKey(group)).filter(Boolean));
      if (reportsState.selectedFailureGroupKey && !availableGroupKeys.has(reportsState.selectedFailureGroupKey)) {
        reportsState.selectedFailureGroupKey = "";
      }
      if (!reportsState.selectedFailureGroupKey) {
        const preferred = String(failures?.resolution_summary?.primary_group_key || "").toLowerCase();
        reportsState.selectedFailureGroupKey = (preferred && availableGroupKeys.has(preferred))
          ? preferred
          : failureResolutionGroupKey(reportsState.lastFailureResolutionGroups[0]);
      }
      if (reportsState.selectedFailureRowKey && !rows.some((row) => failureRowKey(row) === reportsState.selectedFailureRowKey)) {
        reportsState.selectedFailureRowKey = "";
      }
      const availableKeys = new Set(rows.map((row) => failureRowKey(row)).filter(Boolean));
      reportsState.selectedFailureRowKeys = new Set(Array.from(reportsState.selectedFailureRowKeys).filter((key) => availableKeys.has(key)));
      reportsState.lastFailureEmptyMessage = failureEmptyStateMessage(failures, rows);
      const summary = [
        failures.source ? `Source: ${failures.source}` : "",
        `Source type: ${failures.source_kind || "latest_json"}`,
        `Rows: ${failures.count || rows.length || 0}`,
        `Operator required: ${failures.operator_required_count || 0}`,
        `Permanent: ${failures.permanent_count || 0}`,
        `Transient: ${failures.transient_count || 0}`,
        failureRetryPreviewSummaryLine(failures),
        ...(failures.warnings || []),
        !rows.length ? failureEmptyStateMessage(failures, rows) : "",
      ].filter(Boolean);
      setText("failure-summary", summary.join("\n") || "No failure preview loaded.");
      renderFailureResolutionSummary();
      renderFailureResolutionGroups();
      renderFailureDetail(getSelectedFailureRow());
      renderFailureRows();
      updateFailureClearConfirmState();
      renderReportTriage();
    }

  function visibleFailureGroups() {
      const groups = Array.isArray(reportsState.lastFailureResolutionGroups) ? reportsState.lastFailureResolutionGroups : [];
      const filteredRows = visibleFailureRows();
      const filterText = String(byId("failure-filter")?.value || "").trim();
      const visibleKeys = rowKeySet(filteredRows, failureRowKey);
      return groups.filter((group) => {
        if (!failureGroupMatchesChip(group, reportsState.activeFailureFilterChip)) return false;
        const keys = Array.isArray(group?.affected_row_keys) ? group.affected_row_keys : [];
        if (keys.some((key) => visibleKeys.has(String(key || "").toLowerCase()))) return true;
        const text = failureGroupSearchText(group);
        return filterText && text.includes(filterText.toLowerCase());
      });
    }

  function ensureSelectedFailureGroupVisible() {
      const groups = visibleFailureGroups();
      if (!groups.length) {
        reportsState.selectedFailureGroupKey = "";
        return null;
      }
      if (!reportsState.selectedFailureGroupKey || !groups.some((group) => failureResolutionGroupKey(group) === reportsState.selectedFailureGroupKey)) {
        reportsState.selectedFailureGroupKey = failureResolutionGroupKey(groups[0]);
      }
      return getSelectedFailureGroup();
    }

  function visibleFailureRows() {
      const filterText = byId("failure-filter")?.value || "";
      const textRows = filterRows(reportsState.lastFailureRows, filterText, [
        "classification",
        "error_code",
        "stage",
        "media_type",
        "lookup_title",
        "source_path",
        "reason",
        "suggested_action",
        "retry_safe_next_action",
      ]);
      return textRows.filter((row) => failureMatchesChip(row, reportsState.activeFailureFilterChip));
    }

  function hiddenSelectedFailureCount(rows = visibleFailureRows()) {
      return hiddenSelectedCount(reportsState.selectedFailureRowKeys, rows, failureRowKey);
    }

  function renderFailureResolutionSummary() {
      const summary = failureResolutionSummaryPayload();
      const lifecycleCounts = summary.lifecycle_counts && typeof summary.lifecycle_counts === "object" ? summary.lifecycle_counts : {};
      const activeLifecycleCount = ["new", "acknowledged", "working", "waiting_backend", "ready_to_clear", "reopened"]
        .reduce((total, key) => total + reportNumber(lifecycleCounts[key]), 0);
      setText("failure-resolution-posture", summary.status_label || summary.status || "Not loaded");
      setText("failure-resolution-lifecycle-counts", `${activeLifecycleCount || reportNumber(summary.group_count)} active`);
      setText("failure-resolution-primary-action", summary.primary_action_label || "Review details");
      setText("failure-resolution-blocking-count", String(reportNumber(summary.blocking_count)));
      setText("failure-resolution-retry-count", String(reportNumber(summary.retryable_count)));
      setText("failure-resolution-working-count", String(reportNumber(summary.working_count) || reportNumber(lifecycleCounts.working) + reportNumber(lifecycleCounts.acknowledged)));
      setText("failure-resolution-clearable-count", String(reportNumber(summary.clearable_count)));
      setText("failure-resolution-source-mode", summary.source_mode_label || (failureMarkerModeActive() ? "Failure markers" : "Latest JSON"));
    }

  function selectFailureGroup(group) {
      reportsState.selectedFailureGroupKey = failureResolutionGroupKey(group);
      reportsState.lastFailureClearPreview = null;
      reportsState.lastFailureLifecyclePreview = null;
      const rows = failureRowsForGroup(group);
      reportsState.selectedFailureRowKey = rows.length ? failureRowKey(rows[0]) : "";
      renderFailureResolutionGroups();
      renderFailureResolutionDetail(group || null, rows[0] || null);
      renderFailureRows();
      updateFailureClearConfirmState();
    }

  function renderFailureResolutionGroups() {
      const container = byId("failure-resolution-groups");
      if (!container) return;
      const groups = visibleFailureGroups();
      setText("failure-resolution-group-status", `${groups.length} / ${reportsState.lastFailureResolutionGroups.length} group${reportsState.lastFailureResolutionGroups.length === 1 ? "" : "s"}`);
      if (!groups.length) {
        container.replaceChildren();
        const empty = document.createElement("p");
        empty.className = "note";
        empty.textContent = reportsState.lastFailureRows.length ? "No grouped issues match the active filter." : reportsState.lastFailureEmptyMessage;
        container.appendChild(empty);
        configureFailurePrimaryAction(null);
        setText("failure-resolution-detail-status", "No selection");
        setText("failure-detail", reportsState.lastFailureEmptyMessage);
        renderReportDiagnosticsActions("failure-diagnostics-actions", failureDiagnosticsActionsForRow(null), "Reports failure page");
        updateFailureClearConfirmState();
        return;
      }
      const selected = ensureSelectedFailureGroupVisible();
      container.replaceChildren();
      groups.forEach((group) => {
        const key = failureResolutionGroupKey(group);
        const button = document.createElement("button");
        button.type = "button";
        button.className = "failure-resolution-group-button";
        button.dataset.groupKey = key;
        button.setAttribute("aria-pressed", String(key && key === reportsState.selectedFailureGroupKey));
        const title = document.createElement("span");
        title.className = "failure-resolution-group-title";
        title.textContent = group.cause || group.error_code || "Failure group";
        const meta = document.createElement("span");
        meta.className = "failure-resolution-group-meta";
        meta.textContent = [
          group.status_label || "Review",
          `${group.row_count || 0} row${Number(group.row_count || 0) === 1 ? "" : "s"}`,
          group.owner || "Diagnostics",
        ].filter(Boolean).join(" | ");
        const hint = document.createElement("span");
        hint.className = "failure-resolution-group-hint";
        hint.textContent = group.primary_action_label || group.primary_action?.label || group.suggested_action || "";
        button.append(title, meta, hint);
        button.addEventListener("click", () => selectFailureGroup(group));
        container.appendChild(button);
      });
      renderFailureResolutionDetail(selected, failureRowsForGroup(selected)[0] || null);
    }

  function renderFailurePlaybook(group) {
      const steps = Array.isArray(group?.playbook_steps) ? group.playbook_steps : [];
      const list = byId("failure-playbook-steps");
      setText("failure-playbook-status", steps.length ? `${steps.length} steps` : "No playbook");
      if (!list) return;
      list.replaceChildren();
      if (!steps.length) {
        const item = document.createElement("li");
        item.textContent = "No backend-authored playbook loaded.";
        list.appendChild(item);
        return;
      }
      steps.forEach((step) => {
        const item = document.createElement("li");
        const status = String(step?.status || "not_started").toLowerCase();
        item.dataset.status = status;
        item.textContent = `${step?.label || "Step"} | ${status.replaceAll("_", " ")} | ${step?.detail || ""}`;
        list.appendChild(item);
      });
    }

  function renderFailureVerification(group) {
      const verification = group?.verification && typeof group.verification === "object" ? group.verification : {};
      const panel = byId("failure-verification-panel");
      const safe = verification.safe_to_resolve === true;
      const markerCount = reportNumber(verification.active_marker_count);
      const blockers = Array.isArray(verification.blockers) ? verification.blockers.filter(Boolean) : [];
      setText("failure-verification-status", safe ? "Pass" : "Blocked");
      setText("failure-lifecycle-verification-state", safe ? "Pass" : markerCount ? `${markerCount} marker${markerCount === 1 ? "" : "s"}` : "Review");
      if (!panel) return;
      panel.replaceChildren();
      [
        ["Active markers", String(markerCount)],
        ["Failure rows", String(reportNumber(verification.active_failure_row_count || group?.row_count))],
        ["Blocking rows", String(reportNumber(verification.blocking_count || group?.blocking_count))],
        ["Retryable rows", String(reportNumber(verification.retryable_count || group?.retryable_count))],
        ["Safe to resolve", safe ? "Yes" : "No"],
        ["Next action", verification.safe_next_action || group?.safe_next_action || "Review details"],
      ].forEach(([label, value]) => {
        const item = document.createElement("section");
        item.className = "failure-verification-item";
        const labelEl = document.createElement("span");
        labelEl.textContent = label;
        const valueEl = document.createElement("strong");
        valueEl.textContent = value;
        item.append(labelEl, valueEl);
        panel.appendChild(item);
      });
      if (blockers.length) {
        const item = document.createElement("section");
        item.className = "failure-verification-item";
        const labelEl = document.createElement("span");
        labelEl.textContent = "Blockers";
        const valueEl = document.createElement("strong");
        valueEl.textContent = blockers.join(" | ");
        item.append(labelEl, valueEl);
        panel.appendChild(item);
      }
    }

  function renderFailureTimeline(group) {
      const timeline = Array.isArray(group?.timeline) ? group.timeline : [];
      const list = byId("failure-timeline");
      setText("failure-timeline-status", timeline.length ? `${timeline.length} event${timeline.length === 1 ? "" : "s"}` : "No events");
      if (!list) return;
      list.replaceChildren();
      if (!timeline.length) {
        const item = document.createElement("li");
        item.textContent = "No lifecycle events recorded.";
        list.appendChild(item);
        return;
      }
      timeline.slice(-8).forEach((event) => {
        const item = document.createElement("li");
        item.textContent = [
          event?.recorded_at || "time unknown",
          event?.transition || event?.lifecycle_state || "event",
          event?.reason || event?.operator_note || "",
        ].filter(Boolean).join(" | ");
        list.appendChild(item);
      });
    }

  function renderFailureLifecycleControls(group) {
      const current = group || getSelectedFailureGroup();
      const state = failureGroupLifecycleState(current);
      const stateLabel = current?.lifecycle_label || state.replaceAll("_", " ");
      const stateChip = byId("failure-lifecycle-strip")?.querySelector(".failure-lifecycle-chip");
      if (stateChip) stateChip.dataset.state = state;
      setText("failure-lifecycle-state", current ? stateLabel : "No selection");
      setText("failure-lifecycle-last-transition", current?.last_transition_at || "None");
      const acknowledge = failureTransition(current, "acknowledge");
      const start = failureTransition(current, "start_work");
      const resolve = failureTransition(current, "mark_resolved");
      const reopen = failureTransition(current, "reopen");
      setFailureLifecycleButton(
        "failure-lifecycle-ack-button",
        Boolean(current && acknowledge),
        Boolean(acknowledge?.disabled),
        acknowledge?.disabled_reason || ""
      );
      setFailureLifecycleButton(
        "failure-lifecycle-start-button",
        Boolean(current && start),
        Boolean(start?.disabled),
        start?.disabled_reason || ""
      );
      setFailureLifecycleButton(
        "failure-lifecycle-resolve-preview-button",
        Boolean(current && resolve),
        Boolean(resolve?.disabled),
        resolve?.disabled_reason || ""
      );
      setFailureLifecycleButton(
        "failure-lifecycle-reopen-preview-button",
        Boolean(current && reopen),
        Boolean(reopen?.disabled),
        reopen?.disabled_reason || ""
      );
      updateFailureLifecycleConfirmState();
    }

  function renderFailureLifecyclePanels(group) {
      const current = group || getSelectedFailureGroup();
      if (!current) {
        setText("failure-lifecycle-state", "No selection");
        setText("failure-lifecycle-last-transition", "None");
        setText("failure-lifecycle-verification-state", "Not checked");
        setText("failure-playbook-status", "No playbook");
        setText("failure-verification-status", "Not checked");
        setText("failure-timeline-status", "No events");
        renderFailurePlaybook(null);
        renderFailureVerification(null);
        renderFailureTimeline(null);
        renderFailureLifecycleControls(null);
        return;
      }
      renderFailurePlaybook(current);
      renderFailureVerification(current);
      renderFailureTimeline(current);
      renderFailureLifecycleControls(current);
    }

  function renderFailureResolutionDetail(group, selectedRow = null) {
      const current = group || getSelectedFailureGroup();
      if (!current) {
        configureFailurePrimaryAction(null);
        setText("failure-resolution-detail-status", "No selection");
        setText("failure-detail", reportsState.lastFailureEmptyMessage);
        renderFailureLifecyclePanels(null);
        renderReportDiagnosticsActions("failure-diagnostics-actions", failureDiagnosticsActionsForRow(null), "Reports failure page");
        updateFailureClearConfirmState();
        return;
      }
      const rows = failureRowsForGroup(current);
      const sample = selectedRow || rows[0] || null;
      const clearablePaths = normalizeFailureMarkerPaths(current.clearable_marker_paths || []);
      const affected = Array.isArray(current.affected_sources) ? current.affected_sources : [];
      const action = failureResolutionPrimaryAction(current);
      const proofLines = sample ? failureEvidenceProofLines(sample, { includeFallback: true }) : [];
      configureFailurePrimaryAction(current);
      renderFailureLifecyclePanels(current);
      setText("failure-resolution-detail-status", `${current.owner || "Diagnostics"} | ${current.row_count || rows.length || 0} row${Number(current.row_count || rows.length || 0) === 1 ? "" : "s"}`);
      const lines = [
        "Why it stopped",
        `Status: ${current.status_label || (sample ? failureStatusLabel(sample) : "Review")}`,
        `Cause: ${current.cause || (sample ? failurePlainSummaryText(sample) : "")}`,
        `Stage: ${current.stage || sample?.stage || ""}`,
        `Code: ${current.error_code || sample?.error_code || ""}`,
        "",
        "Suggested resolution",
        `Owner: ${current.owner || (sample ? failureActionOwner(sample) : "Diagnostics")}`,
        `Primary action: ${action.label || current.primary_action_label || "Review details"}`,
        `Suggested fix: ${current.suggested_action || (sample ? failureSuggestedActionText(sample) : "")}`,
        `Safe next action: ${current.safe_next_action || sample?.retry_safe_next_action || ""}`,
        "",
        "Affected files",
        ...(affected.length ? affected.slice(0, 8).map((source) => `- ${source}`) : ["- No affected file path reported."]),
        affected.length > 8 ? `- ... ${affected.length - 8} more` : "",
        "",
        "Structured proof",
        ...(proofLines.length ? proofLines.map((line) => `- ${line}`) : ["- No selected failure row proof loaded."]),
        "",
        "Evidence",
        `Rows: ${current.row_count || rows.length || 0}`,
        `Blocking rows: ${current.blocking_count || 0}`,
        `Retryable rows: ${current.retryable_count || 0}`,
        `Clearable marker paths: ${clearablePaths.length}`,
        ...clearablePaths.slice(0, 6).map((path) => `- ${path}`),
        clearablePaths.length > 6 ? `- ... ${clearablePaths.length - 6} more markers` : "",
        sample?.artifact_path ? `Artifact: ${sample.artifact_path}` : "",
        sample?.repro_path ? `Repro: ${sample.repro_path}` : "",
        sample?.source_json ? `Record file: ${sample.source_json}` : "",
      ].filter((line) => line !== "");
      setText("failure-detail", lines.join("\n"));
      renderReportDiagnosticsActions("failure-diagnostics-actions", failureDiagnosticsActionsForGroup(current), "Reports failure selected group");
      updateFailureClearConfirmState();
    }

  function selectFailureRow(item) {
      reportsState.selectedFailureRowKey = failureRowKey(item);
      const group = failureResolutionGroupForRow(item) || getSelectedFailureGroup();
      if (group) reportsState.selectedFailureGroupKey = failureResolutionGroupKey(group);
      reportsState.lastFailureLifecyclePreview = null;
      renderFailureResolutionGroups();
      renderFailureResolutionDetail(group || null, item || null);
      renderFailureRows();
    }

  function toggleFailureRowSelection(item, checked) {
      const key = failureRowKey(item);
      if (!key) return;
      if (checked) {
        reportsState.selectedFailureRowKeys.add(key);
        reportsState.selectedFailureRowKey = key;
      } else {
        reportsState.selectedFailureRowKeys.delete(key);
        if (reportsState.selectedFailureRowKey === key) {
          reportsState.selectedFailureRowKey = Array.from(reportsState.selectedFailureRowKeys)[0] || "";
        }
      }
      renderFailureDetail(getSelectedFailureRow());
      renderFailureRows();
    }

  function renderFailureDetail(item) {
      const group = item ? failureResolutionGroupForRow(item) : getSelectedFailureGroup();
      if (group) reportsState.selectedFailureGroupKey = failureResolutionGroupKey(group);
      renderFailureResolutionDetail(group || null, item || null);
    }

  function renderFailureRows() {
      setReportChipPressed("[data-failure-filter-chip]", reportsState.activeFailureFilterChip);
      const rows = visibleFailureRows();
      const hiddenCount = hiddenSelectedFailureCount(rows);
      setText("failure-status", reportTableStatusText(rows.length, reportsState.lastFailureRows.length, reportsState.selectedFailureRowKeys.size, hiddenCount));
      const tbody = byId("failure-rows");
      if (!rows.length) {
        clearRows(tbody, 6, reportsState.lastFailureRows.length ? "No failure rows match the filter." : reportsState.lastFailureEmptyMessage);
        updateTableStatusLegend("failure-table-legend", tbody, "Failure rows");
        return;
      }
      tbody.replaceChildren();
      reportRenderedRows(rows).forEach((item) => {
        const row = document.createElement("tr");
        const severity = failureSeverity(item);
        row.dataset.status = severity;
        const key = failureRowKey(item);
        row.dataset.rowKey = key;
        const selectCell = document.createElement("td");
        const checkbox = document.createElement("input");
        checkbox.type = "checkbox";
        checkbox.checked = Boolean(key && reportsState.selectedFailureRowKeys.has(key));
        checkbox.setAttribute("aria-label", `Select failure ${item.lookup_title || item.source_path || item.error_code || ""}`);
        checkbox.addEventListener("click", (event) => event.stopPropagation());
        checkbox.addEventListener("change", () => toggleFailureRowSelection(item, checkbox.checked));
        selectCell.appendChild(checkbox);
        row.appendChild(selectCell);
        const statusCell = document.createElement("td");
        if (typeof setCellStatusChip === "function") {
          setCellStatusChip(statusCell, failureStatusLabel(item), severity);
        } else {
          statusCell.textContent = failureStatusLabel(item);
        }
        row.appendChild(statusCell);
        appendCells(row, [
          failureFileText(item),
          failureTableEvidenceText(item),
          failureSuggestedActionText(item),
          failureActionOwner(item),
        ]);
        makeRowSelectable(row, () => selectFailureRow(item), {
          selected: Boolean(key && key === reportsState.selectedFailureRowKey),
          label: `Failure row ${item.lookup_title || item.source_path || item.error_code || ""}`,
        });
        tbody.appendChild(row);
      });
      updateTableStatusLegend("failure-table-legend", tbody, "Failure rows");
    }

  function renderFailureReviewBoard() {
      setText("failure-review-status", failureReviewStatus());
      const board = byId("failure-review-board");
      if (board) {
        board.replaceChildren(...failureReviewBoardTiles().map(failureReviewTileNode));
      }
      setText("failure-review-board-detail", failureReviewBoardLines().join("\n"));
    }

  function reportsFailuresTabActive() {
      const page = document.querySelector('[data-page-panel="reports"]');
      if (!page || page.hidden) return false;
      const failuresPanel = page.querySelector('[data-reports-tab-panel="failures"]');
      return Boolean(failuresPanel && !failuresPanel.hidden && failuresPanel.classList.contains("is-active"));
    }

  function eventTargetAcceptsText(event) {
      const target = event?.target;
      if (!(target instanceof HTMLElement)) return false;
      const tag = target.tagName.toLowerCase();
      return tag === "input" || tag === "textarea" || tag === "select" || target.isContentEditable;
    }

  function moveFailureGroupSelection(delta) {
      const groups = visibleFailureGroups();
      if (!groups.length) return;
      const currentIndex = groups.findIndex((group) => failureResolutionGroupKey(group) === reportsState.selectedFailureGroupKey);
      const nextIndex = currentIndex < 0
        ? 0
        : Math.min(groups.length - 1, Math.max(0, currentIndex + delta));
      selectFailureGroup(groups[nextIndex]);
    }

  function handleReportsFailureKeyboard(event) {
      if (!reportsFailuresTabActive()) return;
      const key = String(event.key || "");
      const typing = eventTargetAcceptsText(event);
      if (key === "Escape") {
        const more = byId("failure-more-actions");
        if (more) more.open = false;
        return;
      }
      if (typing) return;
      if (key === "/") {
        const filter = byId("failure-filter");
        if (filter) {
          event.preventDefault();
          filter.focus();
          filter.select?.();
        }
        return;
      }
      if (key === "j" || key === "ArrowDown") {
        event.preventDefault();
        moveFailureGroupSelection(1);
        return;
      }
      if (key === "k" || key === "ArrowUp") {
        event.preventDefault();
        moveFailureGroupSelection(-1);
        return;
      }
      if (key === "Enter") {
        event.preventDefault();
        runFailurePrimaryAction(getSelectedFailureGroup());
        return;
      }
      if (key.toLowerCase() === "m") {
        const more = byId("failure-more-actions");
        if (more) {
          event.preventDefault();
          more.open = !more.open;
        }
      }
    }

    return {
      ensureSelectedFailureGroupVisible,
      eventTargetAcceptsText,
      handleReportsFailureKeyboard,
      hiddenSelectedFailureCount,
      moveFailureGroupSelection,
      renderFailureDetail,
      renderFailureLifecycleControls,
      renderFailureLifecyclePanels,
      renderFailurePlaybook,
      renderFailurePreview,
      renderFailureResolutionDetail,
      renderFailureResolutionGroups,
      renderFailureResolutionSummary,
      renderFailureReviewBoard,
      renderFailureRows,
      renderFailureTimeline,
      renderFailureVerification,
      reportsFailuresTabActive,
      selectFailureGroup,
      selectFailureRow,
      toggleFailureRowSelection,
      visibleFailureGroups,
      visibleFailureRows,
    };
  }

  window.__reportsViewFailureViewModule = {
    createReportsFailureViewModule,
  };
})();
