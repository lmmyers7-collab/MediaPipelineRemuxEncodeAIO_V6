// reports/failureCommands.js
// Failure command request, preview, delete, and result helpers for reportsView.js.

(function () {
  "use strict";

  const FAILURE_ARTIFACT_CLEANUP_REASON = "Operator confirmed failure artifact cleanup from Reports.";

  function noop() {}

  function createReportsFailureCommandsModule(deps = {}) {
    const reportsState = deps.state && typeof deps.state === "object" ? deps.state : {};
    const apiPost = typeof deps.apiPost === "function" ? deps.apiPost : async function () { throw new Error("apiPost unavailable"); };
    const appendCommandResult = typeof deps.appendCommandResult === "function" ? deps.appendCommandResult : null;
    const byId = typeof deps.byId === "function" ? deps.byId : function () { return null; };
    const failureArchiveButtonIds = Array.isArray(deps.failureArchiveButtonIds) ? deps.failureArchiveButtonIds : [];
    const failureArtifactCleanupButtonIds = Array.isArray(deps.failureArtifactCleanupButtonIds) ? deps.failureArtifactCleanupButtonIds : [];
    const failureClearButtonIds = Array.isArray(deps.failureClearButtonIds) ? deps.failureClearButtonIds : [];
    const failureClearMarkerPathsForRow = typeof deps.failureClearMarkerPathsForRow === "function" ? deps.failureClearMarkerPathsForRow : function () { return []; };
    const failureClearUnavailableReason = typeof deps.failureClearUnavailableReason === "function" ? deps.failureClearUnavailableReason : function () { return "No marker path is available for this row."; };
    const failureCountsForRows = typeof deps.failureCountsForRows === "function" ? deps.failureCountsForRows : function (rows) { return { count: Array.isArray(rows) ? rows.length : 0 }; };
    const failureGroupJournalKey = typeof deps.failureGroupJournalKey === "function" ? deps.failureGroupJournalKey : function () { return ""; };
    const failureLifecycleBackendReasons = deps.failureLifecycleBackendReasons && typeof deps.failureLifecycleBackendReasons === "object" ? deps.failureLifecycleBackendReasons : {};
    const failureLifecycleButtonIds = Array.isArray(deps.failureLifecycleButtonIds) ? deps.failureLifecycleButtonIds : [];
    const failureMarkerModeActive = typeof deps.failureMarkerModeActive === "function" ? deps.failureMarkerModeActive : function () { return false; };
    const failureResolutionFallbackGroups = typeof deps.failureResolutionFallbackGroups === "function" ? deps.failureResolutionFallbackGroups : function () { return []; };
    const failureResolutionGroupKey = typeof deps.failureResolutionGroupKey === "function" ? deps.failureResolutionGroupKey : function () { return ""; };
    const failureResolutionGroupsFromPayload = typeof deps.failureResolutionGroupsFromPayload === "function" ? deps.failureResolutionGroupsFromPayload : function () { return []; };
    const failureResolutionPrimaryAction = typeof deps.failureResolutionPrimaryAction === "function" ? deps.failureResolutionPrimaryAction : function () { return { label: "Review details", kind: "review_details" }; };
    const failureRowKey = typeof deps.failureRowKey === "function" ? deps.failureRowKey : function () { return ""; };
    const failureRowsForGroup = typeof deps.failureRowsForGroup === "function" ? deps.failureRowsForGroup : function () { return []; };
    const getSelectedFailureGroup = typeof deps.getSelectedFailureGroup === "function" ? deps.getSelectedFailureGroup : function () { return null; };
    const getSelectedFailureRow = typeof deps.getSelectedFailureRow === "function" ? deps.getSelectedFailureRow : function () { return null; };
    const getSelectedFailureRows = typeof deps.getSelectedFailureRows === "function" ? deps.getSelectedFailureRows : function () { return []; };
    const hiddenSelectedFailureCount = typeof deps.hiddenSelectedFailureCount === "function" ? deps.hiddenSelectedFailureCount : function () { return 0; };
    const normalizeFailureMarkerPaths = typeof deps.normalizeFailureMarkerPaths === "function" ? deps.normalizeFailureMarkerPaths : function (paths) { return Array.isArray(paths) ? paths.filter(Boolean) : []; };
    const refreshAll = typeof deps.refreshAll === "function" ? deps.refreshAll : null;
    const renderFailureDetail = typeof deps.renderFailureDetail === "function" ? deps.renderFailureDetail : noop;
    const renderFailurePreview = typeof deps.renderFailurePreview === "function" ? deps.renderFailurePreview : noop;
    const renderFailureRows = typeof deps.renderFailureRows === "function" ? deps.renderFailureRows : noop;
    const reportNumber = typeof deps.reportNumber === "function" ? deps.reportNumber : function (value) { const numeric = Number(value); return Number.isFinite(numeric) ? numeric : 0; };
    const reportOwnerPage = typeof deps.reportOwnerPage === "function" ? deps.reportOwnerPage : function () { return null; };
    const reportRenderedRowsNote = typeof deps.reportRenderedRowsNote === "function" ? deps.reportRenderedRowsNote : function () { return ""; };
    const REPORTS_ROW_RENDER_LIMIT = Number(deps.rowRenderLimit || 250);
    const selectedFailureGroupMarkerPaths = typeof deps.selectedFailureGroupMarkerPaths === "function" ? deps.selectedFailureGroupMarkerPaths : function () { return []; };
    const setButtonsBusy = typeof deps.setButtonsBusy === "function" ? deps.setButtonsBusy : noop;
    const setFailureMarkerSourceMode = typeof deps.setFailureMarkerSourceMode === "function" ? deps.setFailureMarkerSourceMode : noop;
    const setText = typeof deps.setText === "function" ? deps.setText : noop;
    const visibleFailureRows = typeof deps.visibleFailureRows === "function" ? deps.visibleFailureRows : function () { return []; };
    const FAILURE_LIFECYCLE_BACKEND_REASONS = failureLifecycleBackendReasons;

    function setFailureClearBusy(busy, activeId = "") {
      reportsState.failureClearBusy = Boolean(busy);
      setButtonsBusy(failureClearButtonIds, reportsState.failureClearBusy, activeId);
      if (!reportsState.failureClearBusy) updateFailureClearConfirmState();
    }

    function setFailureArchiveBusy(busy, activeId = "") {
      reportsState.failureArchiveBusy = Boolean(busy);
      setButtonsBusy(failureArchiveButtonIds, reportsState.failureArchiveBusy, activeId);
      if (!reportsState.failureArchiveBusy) updateFailureArchiveConfirmState();
    }

    function setFailureArtifactCleanupBusy(busy, activeId = "") {
      reportsState.failureArtifactCleanupBusy = Boolean(busy);
      setButtonsBusy(failureArtifactCleanupButtonIds, reportsState.failureArtifactCleanupBusy, activeId);
      if (!reportsState.failureArtifactCleanupBusy) updateFailureArtifactCleanupConfirmState();
    }

    function setFailureLifecycleBusy(busy, activeId = "") {
      reportsState.failureLifecycleBusy = Boolean(busy);
      setButtonsBusy(failureLifecycleButtonIds, reportsState.failureLifecycleBusy, activeId);
      if (!reportsState.failureLifecycleBusy) updateFailureLifecycleConfirmState();
    }

    function hiddenFailureSelectionMessage(actionLabel = "selected error clear") {
      const count = hiddenSelectedFailureCount();
      return `${count} selected error row${count === 1 ? " is" : "s are"} hidden by the active filter/search. Return to All and clear search, or deselect hidden rows before ${actionLabel}.`;
    }

    function selectedFailureMarkerPaths() {
      const seen = new Set();
      const paths = [];
      getSelectedFailureRows().forEach((item) => {
        failureClearMarkerPathsForRow(item).forEach((markerPath) => {
          const key = markerPath.toLowerCase();
          if (markerPath && !seen.has(key)) {
            seen.add(key);
            paths.push(markerPath);
          }
        });
      });
      return paths;
    }

    function visibleFailureMarkerPaths() {
      const seen = new Set();
      const paths = [];
      visibleFailureRows().forEach((item) => {
        failureClearMarkerPathsForRow(item).forEach((markerPath) => {
          const key = markerPath.toLowerCase();
          if (markerPath && !seen.has(key)) {
            seen.add(key);
            paths.push(markerPath);
          }
        });
      });
      return paths;
    }

    function allFailureMarkerPaths() {
      const seen = new Set();
      const paths = [];
      reportsState.lastFailureRows.forEach((item) => {
        failureClearMarkerPathsForRow(item).forEach((markerPath) => {
          const key = markerPath.toLowerCase();
          if (markerPath && !seen.has(key)) {
            seen.add(key);
            paths.push(markerPath);
          }
        });
      });
      return paths;
    }

    function runFailurePrimaryAction(group) {
      const selected = group || getSelectedFailureGroup();
      const action = failureResolutionPrimaryAction(selected);
      const kind = String(action.kind || "");
      if (kind === "preview_marker_clear" || kind === "clear_marker") {
        const select = byId("failure-clear-scope");
        if (select) select.value = "selected_group";
        requestFailureMarkerClear("selected_group", false);
        return;
      }
      if (kind === "wait_for_backend_retry") {
        setText("failure-clear-status", "Waiting");
        setText("failure-clear-summary", selected?.safe_next_action || "Backend retry is already staged by retry policy.");
        return;
      }
      const page = action.page || reportOwnerPage(action.owner || selected?.owner)?.page;
      if (page && typeof window.showPage === "function") {
        window.showPage(page);
        return;
      }
      setText("failure-clear-status", "Review");
      setText("failure-clear-summary", selected?.safe_next_action || "Review details and evidence before taking action.");
    }

    function configureFailurePrimaryAction(group) {
      const button = byId("failure-primary-action-button");
      if (!button) return;
      const action = group ? failureResolutionPrimaryAction(group) : { label: "Load failures", kind: "review_details" };
      button.textContent = action.label || "Review details";
      button.disabled = !group || reportsState.failureClearBusy || reportsState.failureArchiveBusy;
      button.onclick = () => runFailurePrimaryAction(group);
    }

    function failureTransition(group, transition) {
      const transitions = Array.isArray(group?.available_transitions) ? group.available_transitions : [];
      return transitions.find((item) => String(item?.transition || "") === transition) || null;
    }

    function setFailureLifecycleButton(id, visible, disabled = false, title = "") {
      const button = byId(id);
      if (!button) return;
      button.hidden = !visible;
      button.disabled = Boolean(disabled || reportsState.failureLifecycleBusy);
      button.title = title || "";
    }

    function failureLifecycleStepId(transition) {
      if (transition === "mark_resolved") return "close_issue";
      if (transition === "reopen") return "reopen_issue";
      if (transition === "start_work") return "open_owner";
      if (transition === "acknowledge") return "review_evidence";
      return transition || "";
    }

    function failureLifecycleRequiresReason(transition) {
      return ["mark_resolved", "reopen", "waive_step"].includes(String(transition || ""));
    }

    function failureLifecyclePreviewRequired(transition) {
      return ["mark_resolved", "reopen", "waive_step"].includes(String(transition || ""));
    }

    function failureLifecycleBackendReason(transition) {
      return FAILURE_LIFECYCLE_BACKEND_REASONS[String(transition || "")] || "";
    }

    function failureLifecycleRequest(transition, dryRun) {
      const group = getSelectedFailureGroup();
      const journalKey = failureGroupJournalKey(group);
      const reason = failureLifecycleRequiresReason(transition) ? failureLifecycleBackendReason(transition) : "";
      if (!group || !journalKey) return { error: "Select a failure group before changing lifecycle state." };
      const request = {
        journal_key: journalKey,
        transition,
        step_id: failureLifecycleStepId(transition),
        operator_note: "",
        reason,
        dry_run: Boolean(dryRun),
        confirm_transition: !dryRun,
        dry_run_fingerprint: "",
      };
      return request;
    }

    function failureLifecyclePreviewKey(request) {
      return JSON.stringify({
        journal_key: request?.journal_key || "",
        transition: request?.transition || "",
        step_id: request?.step_id || "",
        reason: request?.reason || "",
      });
    }

    function updateFailureLifecycleConfirmState() {
      const group = reportsState.selectedFailureGroupKey ? getSelectedFailureGroup() : null;
      const resolve = failureTransition(group, "mark_resolved");
      const reopen = failureTransition(group, "reopen");
      const resolveRequest = group && resolve ? failureLifecycleRequest("mark_resolved", false) : { error: "not available" };
      const reopenRequest = group && reopen ? failureLifecycleRequest("reopen", false) : { error: "not available" };
      const resolveReady = Boolean(!resolveRequest.error && !resolve?.disabled);
      const reopenReady = Boolean(!reopenRequest.error && !reopen?.disabled);
      setFailureLifecycleButton(
        "failure-lifecycle-resolve-confirm-button",
        Boolean(group && resolve),
        !resolveReady,
        resolveReady ? "Mark this issue resolved." : resolve?.disabled_reason || resolveRequest.error || "Resolve is not available."
      );
      setFailureLifecycleButton(
        "failure-lifecycle-reopen-confirm-button",
        Boolean(group && reopen),
        !reopenReady,
        reopenReady ? "Reopen this issue." : reopen?.disabled_reason || reopenRequest.error || "Reopen is not available."
      );
    }

    function renderFailureLifecycleResult(result) {
      const data = result?.data && typeof result.data === "object" ? result.data : {};
      const blockers = Array.isArray(data.blockers) ? data.blockers : [];
      const errors = Array.isArray(result?.errors) ? result.errors : [];
      const lines = [
        `Command accepted: ${result?.ok ? "yes" : "no"}`,
        `Dry run: ${data.dry_run ? "yes" : "no"}`,
        `Transition: ${data.transition || ""}`,
        `Current state: ${data.current_state || ""}`,
        `Next state: ${data.next_state || data.lifecycle_state || ""}`,
        data.dry_run_fingerprint ? `Fingerprint: ${data.dry_run_fingerprint}` : "",
        `Writes resolution journal: ${data.writes_failure_resolution_journal ? "yes" : "no"}`,
        `Touches media: ${data.touches_media ? "unexpected yes" : "no"}`,
        data.journal_path ? `Journal: ${data.journal_path}` : "",
        data.confirmation_mode ? `Confirmation: ${data.confirmation_mode}` : "",
        `Safe next action: ${data.safe_next_action || "Refresh Reports and continue from the playbook."}`,
        "",
        result?.message || "",
      ].filter((line) => line !== "");
      if (blockers.length) lines.push("", "Blockers:", ...blockers.map((item) => `- ${item}`));
      if (errors.length) lines.push("", "Errors:", ...errors.map((item) => `- ${item}`));
      setText("failure-lifecycle-result", lines.join("\n"));
    }

    async function requestFailureLifecycleTransition(transition, dryRun = false) {
      if (reportsState.failureLifecycleBusy) {
        setText("failure-lifecycle-result", "Another failure lifecycle command is already in progress.");
        return;
      }
      const request = failureLifecycleRequest(transition, dryRun);
      if (request.error) {
        setText("failure-lifecycle-result", request.error);
        updateFailureLifecycleConfirmState();
        return;
      }
      if (!dryRun && failureLifecyclePreviewRequired(transition)) {
        const stateLabel = transition === "reopen" ? "reopen this issue" : "mark this issue resolved";
        if (!window.confirm(`Confirm ${stateLabel}?\n\nThis writes only the failure resolution journal. It does not clear errors, archive reports, retry files, or touch media.`)) return;
      }
      const activeButtonId = dryRun
        ? ""
        : transition === "mark_resolved"
          ? "failure-lifecycle-resolve-confirm-button"
          : transition === "reopen"
            ? "failure-lifecycle-reopen-confirm-button"
          : transition === "start_work"
            ? "failure-lifecycle-start-button"
            : "failure-lifecycle-ack-button";
      setFailureLifecycleBusy(true, activeButtonId);
      setText("failure-lifecycle-result", dryRun ? "Previewing lifecycle transition..." : "Recording lifecycle transition...");
      try {
        const result = await apiPost("/api/failures/lifecycle", request);
        if (typeof appendCommandResult === "function") appendCommandResult(result);
        renderFailureLifecycleResult(result);
        if (dryRun && result?.ok) {
          reportsState.lastFailureLifecyclePreview = {
            key: failureLifecyclePreviewKey(request),
            dry_run_fingerprint: result?.data?.dry_run_fingerprint || "",
            transition,
          };
          updateFailureLifecycleConfirmState();
        }
        if (!dryRun && result?.ok) {
          reportsState.lastFailureLifecyclePreview = null;
          updateFailureLifecycleConfirmState();
          if (typeof refreshAll === "function") await refreshAll();
        }
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        const result = {
          command: "failures.lifecycle",
          ok: false,
          severity: "error",
          message,
          errors: [message],
        };
        if (typeof appendCommandResult === "function") appendCommandResult(result);
        renderFailureLifecycleResult(result);
      } finally {
        setFailureLifecycleBusy(false);
      }
    }

    function failureMarkerSourcePath() {
      return String(
        reportsState.lastReportSettings?.paths?.failed_markers
        || reportsState.lastFailurePreviewPayload?.source
        || "backend failure markers"
      ).trim();
    }

    function applyLocalFailureMarkerClear(request, result) {
      if (!request || request.dry_run || !result?.ok) return false;
      const data = result?.data && typeof result.data === "object" ? result.data : {};
      const movedMarkers = Number(data.markers || 0) || 0;
      if (!request.all_markers && movedMarkers <= 0) return false;
      const currentRows = Array.isArray(reportsState.lastFailureRows) ? reportsState.lastFailureRows : [];
      const clearedPaths = new Set(normalizeFailureMarkerPaths(request.marker_paths).map((path) => path.toLowerCase()));
      const remainingRows = request.all_markers
        ? []
        : currentRows.filter((item) => !failureClearMarkerPathsForRow(item).some((markerPath) => clearedPaths.has(markerPath.toLowerCase())));
      if (!request.all_markers && remainingRows.length === currentRows.length) return false;
      const nextPreview = {
        ...reportsState.lastFailurePreviewPayload,
        ...(request.all_markers || failureMarkerModeActive()
          ? { source: failureMarkerSourcePath(), source_kind: "markers" }
          : {}),
        ...failureCountsForRows(remainingRows),
        count: remainingRows.length,
        rows: remainingRows,
      };
      delete nextPreview.retry_state;
      delete nextPreview.resolution_summary;
      delete nextPreview.resolution_groups;
      renderFailurePreview(nextPreview);
      return true;
    }

    function failureClearRequest(scope, dryRun) {
      const normalizedScope = scope === "selected_files" ? "selected" : scope;
      const clearAll = normalizedScope === "all" || normalizedScope === "all_markers";
      const apiScope = clearAll ? "all_markers" : normalizedScope === "selected_group" ? "selected" : normalizedScope;
      const visibleRows = visibleFailureRows();
      const journalKey = failureGroupJournalKey(getSelectedFailureGroup());
      if (!clearAll && normalizedScope === "selected" && hiddenSelectedFailureCount(visibleRows)) {
        return { error: hiddenFailureSelectionMessage(dryRun ? "previewing selected errors" : "clearing selected errors") };
      }
      const markerPaths = clearAll
        ? []
        : normalizedScope === "visible"
          ? visibleFailureMarkerPaths()
          : normalizedScope === "selected_group"
            ? selectedFailureGroupMarkerPaths()
            : selectedFailureMarkerPaths();
      if (clearAll) {
        const markerCount = reportNumber(reportsState.lastFailurePreviewPayload.count || reportsState.lastFailureRows.length);
        return { scope: "all_markers", marker_paths: [], dry_run: dryRun, confirm_clear: !dryRun, journal_key: journalKey, all_markers: true, marker_count: markerCount };
      }
      if (normalizedScope === "visible" && visibleRows.length > REPORTS_ROW_RENDER_LIMIT) {
        setText("failure-clear-summary", reportRenderedRowsNote(visibleRows, "error rows"));
      }
      if (!markerPaths.length) {
        return {
          error: clearAll
            ? "No active errors are loaded."
            : normalizedScope === "visible"
              ? "No visible errors are loaded."
              : normalizedScope === "selected_group"
                ? "Selected issue has no active errors to clear."
                : "Check one or more error rows first.",
        };
      }
      return {
        scope: apiScope,
        marker_paths: markerPaths,
        dry_run: dryRun,
        confirm_clear: !dryRun,
        journal_key: journalKey,
        all_markers: false,
        requested_scope: normalizedScope,
        marker_count: markerPaths.length,
        visible_count: visibleRows.length,
        rendered_count: Math.min(visibleRows.length, REPORTS_ROW_RENDER_LIMIT),
        capped_visible_scope: normalizedScope === "visible" && visibleRows.length > REPORTS_ROW_RENDER_LIMIT,
      };
    }

    function failureClearPreviewKey(request) {
      const markerPaths = normalizeFailureMarkerPaths(request?.marker_paths || []).sort();
      return JSON.stringify({
        scope: request?.scope || "",
        requested_scope: request?.requested_scope || request?.scope || "",
        all_markers: Boolean(request?.all_markers),
        journal_key: request?.journal_key || "",
        marker_paths: markerPaths,
      });
    }

    function updateFailureClearConfirmState() {
      const button = byId("failure-clear-confirm-button");
      if (!button) return;
      if (reportsState.failureClearBusy) {
        button.disabled = true;
        button.title = "Error clear command is running.";
        return;
      }
      const scope = byId("failure-clear-scope")?.value || "selected_files";
      const request = failureClearRequest(scope, false);
      const ready = !request.error;
      button.disabled = !ready;
      button.title = ready ? "Clear errors for the selected scope." : (request.error || "Select errors before clearing.");
    }

    function renderFailureClearResult(result) {
      const data = result?.data && typeof result.data === "object" ? result.data : {};
      const planned = Array.isArray(data.planned) ? data.planned : [];
      const skipped = Array.isArray(data.skipped) ? data.skipped : [];
      const errors = Array.isArray(result?.errors) ? result.errors : Array.isArray(data.errors) ? data.errors : [];
      const lines = [
        `Command accepted: ${result?.ok ? "yes" : "no"}`,
        `Dry run: ${data.dry_run ? "yes" : "no"}`,
        `Scope: ${data.scope || ""}`,
        data.scope === "all_markers" ? "Scope note: all active backend error records." : "",
        `Planned error clears: ${planned.length}`,
        `Cleared errors: ${data.markers || 0}`,
        `Writes active error folder: ${data.writes_failure_markers ? "yes" : "no"}`,
        `Touches media: ${data.touches_media ? "unexpected yes" : "no"}`,
        data.manifest_path ? `Clear manifest: ${data.manifest_path}` : "",
        data.archive_dir ? `Cleared error archive: ${data.archive_dir}` : "",
        `Next action: ${data.safe_next_action || "Refresh Reports and retry only after reviewing evidence."}`,
        "Scope: backend error records only; media files are not touched.",
        "",
        result?.message || "",
      ].filter((line) => line !== "");
      if (errors.length) {
        lines.push("", "Errors:", ...errors.map((item) => `- ${item}`));
      }
      if (skipped.length) {
        lines.push("", "Skipped:", ...skipped.slice(0, 8).map((item) => `- ${item.path || ""}: ${item.reason || "skipped"}`));
      }
      if (planned.length) {
        lines.push("", "Planned errors:", ...planned.slice(0, 8).map((item) => `- ${item.path || ""}`));
        if (planned.length > 8) lines.push(`- ... ${planned.length - 8} more`);
      }
      setText("failure-clear-status", result?.ok ? (data.dry_run ? "Checked" : "Cleared") : "Blocked");
      setText("failure-clear-summary", lines.join("\n"));
    }

    async function requestFailureMarkerClear(scope, dryRun) {
      if (reportsState.failureClearBusy) {
        setText("failure-clear-status", "Busy");
        setText("failure-clear-summary", "Another error clear command is already in progress.");
        return;
      }
      const request = failureClearRequest(scope, dryRun);
      if (request.error) {
        setText("failure-clear-status", "Blocked");
        setText("failure-clear-summary", request.error);
        return;
      }
      const activeButtonId = dryRun ? "" : "failure-clear-confirm-button";
      setFailureClearBusy(true, activeButtonId);
      setText("failure-clear-status", dryRun ? "Checking..." : "Clearing...");
      setText("failure-clear-summary", dryRun
        ? `Checking error clear. Nothing will move yet.${request.capped_visible_scope ? `\n${reportRenderedRowsNote(visibleFailureRows(), "error rows")}` : ""}`
        : request.all_markers ? "Clearing all active errors." : "Clearing selected errors.");
      try {
        const payload = {
          scope: request.scope,
          dry_run: dryRun,
          confirm_clear: !dryRun,
        };
        if (!request.all_markers) payload.marker_paths = request.marker_paths;
        if (request.journal_key) payload.journal_key = request.journal_key;
        const result = await apiPost("/api/failures/clear", payload);
        if (typeof appendCommandResult === "function") appendCommandResult(result);
        renderFailureClearResult(result);
        if (dryRun && result?.ok) {
          reportsState.lastFailureClearPreview = {
            key: failureClearPreviewKey(request),
            scope: request.requested_scope || request.scope,
            data: result.data || {},
          };
          updateFailureClearConfirmState();
        }
        if (!dryRun && result?.ok) {
          reportsState.lastFailureClearPreview = null;
          updateFailureClearConfirmState();
          const movedMarkers = Number(result?.data?.markers || 0) || 0;
          if (movedMarkers > 0 || request.all_markers) {
            setFailureMarkerSourceMode(true);
          }
          reportsState.selectedFailureRowKey = "";
          reportsState.selectedFailureRowKeys.clear();
          if (!applyLocalFailureMarkerClear(request, result)) {
            renderFailureDetail(getSelectedFailureRow());
            renderFailureRows();
          }
          if (typeof refreshAll === "function") await refreshAll();
        }
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        const result = {
          command: "failures.clear",
          ok: false,
          severity: "error",
          message,
          errors: [message],
        };
        if (typeof appendCommandResult === "function") appendCommandResult(result);
        renderFailureClearResult(result);
      } finally {
        setFailureClearBusy(false);
      }
    }

    async function requestFailureRowClear(item) {
      const markerPaths = failureClearMarkerPathsForRow(item);
      if (!markerPaths.length) {
        setText("failure-clear-status", "Blocked");
        setText("failure-clear-summary", failureClearUnavailableReason(item));
        return;
      }
      reportsState.selectedFailureRowKey = failureRowKey(item);
      reportsState.selectedFailureRowKeys = new Set([reportsState.selectedFailureRowKey].filter(Boolean));
      renderFailureRows();
      await requestFailureMarkerClear("selected", false);
    }

    function failureArchiveRequest(dryRun, dryRunFingerprint = "") {
      const includeMarkers = byId("failure-archive-include-markers")?.checked === true;
      const includeReports = byId("failure-archive-include-reports")?.checked === true;
      const reason = String(byId("failure-archive-reason")?.value || "").trim();
      if (!includeMarkers && !includeReports) {
        return { error: "Select active errors, round failure reports, or both before archiving evidence." };
      }
      const requestKey = failureArchivePreviewKey({ scope: "all_active", include_markers: includeMarkers, include_reports: includeReports, journal_key: failureGroupJournalKey(getSelectedFailureGroup()) });
      return {
        scope: "all_active",
        include_markers: includeMarkers,
        include_reports: includeReports,
        dry_run: Boolean(dryRun),
        confirm_archive: !dryRun,
        reason,
        dry_run_fingerprint: dryRun ? "" : dryRunFingerprint,
        journal_key: failureGroupJournalKey(getSelectedFailureGroup()),
        key: requestKey,
      };
    }

    function failureArchivePreviewKey(request) {
      return JSON.stringify({
        scope: request?.scope || "all_active",
        include_markers: Boolean(request?.include_markers),
        include_reports: Boolean(request?.include_reports),
        journal_key: request?.journal_key || "",
      });
    }

    function updateFailureArchiveConfirmState() {
      const button = byId("failure-archive-confirm-button");
      if (!button) return;
      if (reportsState.failureArchiveBusy) {
        button.disabled = true;
        button.title = "Archive command is running.";
        return;
      }
      const includeMarkers = byId("failure-archive-include-markers")?.checked === true;
      const includeReports = byId("failure-archive-include-reports")?.checked === true;
      const ready = Boolean(includeMarkers || includeReports);
      button.disabled = !ready;
      button.title = ready ? "Archive selected evidence." : "Select evidence before archiving.";
    }

    function renderFailureArchiveResult(result) {
      const data = result?.data && typeof result.data === "object" ? result.data : {};
      const planned = Array.isArray(data.planned) ? data.planned : [];
      const moved = Array.isArray(data.moved) ? data.moved : [];
      const skipped = Array.isArray(data.skipped) ? data.skipped : [];
      const errors = Array.isArray(result?.errors) ? result.errors : Array.isArray(data.errors) ? data.errors : [];
      const lines = [
        `Command accepted: ${result?.ok ? "yes" : "no"}`,
        `Dry run: ${data.dry_run ? "yes" : "no"}`,
        `Scope: ${data.scope || "all_active"}`,
        `Include active errors: ${data.include_markers ? "yes" : "no"}`,
        `Include reports: ${data.include_reports ? "yes" : "no"}`,
        `Planned evidence files: ${planned.length}`,
        `Moved active errors: ${data.markers || 0}`,
        `Moved reports: ${data.reports || 0}`,
        `Writes failure evidence: ${data.writes_failure_evidence ? "yes" : "no"}`,
        `Touches media: ${data.touches_media ? "unexpected yes" : "no"}`,
        data.manifest_path ? `Clear manifest: ${data.manifest_path}` : "",
        data.archive_dir ? `Evidence archive: ${data.archive_dir}` : "",
        data.dry_run_fingerprint ? `Fingerprint: ${data.dry_run_fingerprint}` : "",
        `Next action: ${data.safe_next_action || "Refresh Reports before making retry decisions."}`,
        "Scope: active errors and round failure reports only; media files are not touched.",
        "",
        result?.message || "",
      ].filter((line) => line !== "");
      if (errors.length) {
        lines.push("", "Errors:", ...errors.map((item) => `- ${item}`));
      }
      if (skipped.length) {
        lines.push("", "Skipped:", ...skipped.slice(0, 8).map((item) => `- ${item.path || ""}: ${item.reason || "skipped"}`));
      }
      if (planned.length) {
        lines.push("", "Planned evidence:", ...planned.slice(0, 8).map((item) => `- ${item.kind || "evidence"}: ${item.path || ""}`));
        if (planned.length > 8) lines.push(`- ... ${planned.length - 8} more`);
      }
      if (moved.length) {
        lines.push("", "Moved evidence:", ...moved.slice(0, 8).map((item) => `- ${item.path || ""} -> ${item.archive_path || ""}`));
        if (moved.length > 8) lines.push(`- ... ${moved.length - 8} more`);
      }
      setText("failure-archive-status", result?.ok ? (data.dry_run ? "Checked" : "Archived") : "Blocked");
      setText("failure-archive-summary", lines.join("\n"));
    }

    async function requestFailureEvidenceArchive(dryRun) {
      if (reportsState.failureArchiveBusy) {
        setText("failure-archive-status", "Busy");
        setText("failure-archive-summary", "Another evidence archive command is already in progress.");
        return;
      }
      const request = failureArchiveRequest(dryRun);
      if (request.error) {
        setText("failure-archive-status", "Blocked");
        setText("failure-archive-summary", request.error);
        updateFailureArchiveConfirmState();
        return;
      }
      setFailureArchiveBusy(true, dryRun ? "" : "failure-archive-confirm-button");
      setText("failure-archive-status", dryRun ? "Checking..." : "Archiving...");
      setText("failure-archive-summary", dryRun ? "Checking evidence archive. Nothing will move yet." : "Checking selected evidence, then archiving.");
      try {
        if (dryRun) {
          const result = await apiPost("/api/failures/archive-evidence", request);
          if (typeof appendCommandResult === "function") appendCommandResult(result);
          renderFailureArchiveResult(result);
          if (result?.ok) {
            reportsState.lastFailureArchivePreview = {
              ...(result.data || {}),
              key: failureArchivePreviewKey(request),
            };
            updateFailureArchiveConfirmState();
          }
          return;
        }

        const result = await apiPost("/api/failures/archive-evidence", request);
        if (typeof appendCommandResult === "function") appendCommandResult(result);
        renderFailureArchiveResult(result);
        reportsState.lastFailureArchivePreview = null;
        updateFailureArchiveConfirmState();
        if (result?.ok && typeof refreshAll === "function") await refreshAll();
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        const result = {
          command: "failures.archive_evidence",
          ok: false,
          severity: "error",
          message,
          errors: [message],
        };
        if (typeof appendCommandResult === "function") appendCommandResult(result);
        renderFailureArchiveResult(result);
        updateFailureArchiveConfirmState();
      } finally {
        setFailureArchiveBusy(false);
      }
    }

    function selectedFailureArtifactPaths() {
      const selected = reportsState.selectedFailureArtifactPaths;
      if (!(selected instanceof Set)) return [];
      return Array.from(selected).map((path) => String(path || "").trim()).filter(Boolean);
    }

    function artifactCleanupPolicyKey(paths = selectedFailureArtifactPaths()) {
      return JSON.stringify({
        mode: "selected_failure_artifacts",
        artifact_paths: paths.slice().sort(),
      });
    }

    function failureArtifactCleanupRequest(dryRun, dryRunFingerprint = "") {
      const summary = reportsState.lastFailureArtifactSummary || {};
      if (!summary.schema_version) return { error: "Load failure artifact storage before deleting artifacts." };
      if (summary.cleanup_route_available === false) return { error: "Failure artifact delete route is not available." };
      const artifactPaths = selectedFailureArtifactPaths();
      if (!artifactPaths.length) return { error: "Select one or more artifact files first." };
      const key = artifactCleanupPolicyKey(artifactPaths);
      return {
        dry_run: Boolean(dryRun),
        confirm_delete: !dryRun,
        reason: dryRun ? "" : FAILURE_ARTIFACT_CLEANUP_REASON,
        dry_run_fingerprint: dryRun ? "" : dryRunFingerprint,
        artifact_paths: artifactPaths,
        key,
      };
    }

    function updateFailureArtifactCleanupConfirmState() {
      const button = byId("failure-artifact-cleanup-confirm-button");
      if (!button) return;
      if (reportsState.failureArtifactCleanupBusy) {
        button.disabled = true;
        button.title = "Artifact delete command is running.";
        return;
      }
      const request = failureArtifactCleanupRequest(false);
      const ready = !request.error;
      button.disabled = !ready;
      button.title = ready ? `Delete ${request.artifact_paths.length} selected artifact file(s).` : (request.error || "Select artifacts before deleting.");
    }

    function artifactCleanupSizeText(bytesValue, gbValue) {
      const bytes = Number(bytesValue || 0);
      if (Number.isFinite(bytes) && bytes > 0) {
        const gib = 1024 * 1024 * 1024;
        const mib = 1024 * 1024;
        if (bytes >= gib) return `${(bytes / gib).toFixed(3)} GB`;
        if (bytes >= mib) return `${(bytes / mib).toFixed(1)} MB`;
        if (bytes >= 1024) return `${(bytes / 1024).toFixed(1)} KB`;
        return `${bytes} B`;
      }
      const gb = Number(gbValue || 0);
      return gb > 0 ? `${gb.toFixed(gb % 1 ? 3 : 0)} GB` : "0 B";
    }

    function appendFailureArtifactCleanupList(lines, heading, items, formatter) {
      if (!items.length) return;
      lines.push("", heading, ...items.slice(0, 8).map(formatter));
      if (items.length > 8) lines.push(`- ... ${items.length - 8} more`);
    }

    function appendFailureArtifactCleanupDetails(lines, details) {
      const { errors, skipped, planned, deleted } = details;
      if (errors.length) {
        lines.push("", "Errors:", ...errors.map((item) => `- ${item}`));
      }
      appendFailureArtifactCleanupList(
        lines,
        "Skipped:",
        skipped,
        (item) => `- ${item.path || item.reason || "skipped"}${item.detail ? `: ${item.detail}` : ""}`
      );
      appendFailureArtifactCleanupList(
        lines,
        "Planned artifacts:",
        planned,
        (item) => `- ${item.relative_path || item.path || ""} (${artifactCleanupSizeText(item.size_bytes, item.size_gb)})`
      );
      appendFailureArtifactCleanupList(
        lines,
        "Deleted artifacts:",
        deleted,
        (item) => `- ${item.relative_path || item.path || ""}`
      );
    }

    function renderFailureArtifactCleanupResult(result) {
      const data = result?.data && typeof result.data === "object" ? result.data : {};
      const policy = data.policy && typeof data.policy === "object" ? data.policy : {};
      const planned = Array.isArray(data.planned) ? data.planned : [];
      const deleted = Array.isArray(data.deleted) ? data.deleted : [];
      const skipped = Array.isArray(data.skipped) ? data.skipped : [];
      const errors = Array.isArray(result?.errors) ? result.errors : Array.isArray(data.errors) ? data.errors : [];
      const requested = Array.isArray(data.requested_artifact_paths) ? data.requested_artifact_paths : [];
      const lines = [
        data.dry_run ? "Checked selected artifacts" : result?.ok ? "Delete complete" : "Delete blocked",
        requested.length ? `Selected: ${requested.length} file(s)` : "",
        `Planned: ${data.planned_count || planned.length} file(s), ${artifactCleanupSizeText(data.planned_bytes, data.planned_gb)}`,
        `Deleted: ${data.deleted_count || deleted.length} file(s), ${artifactCleanupSizeText(data.deleted_bytes, data.deleted_gb)}`,
        Number(policy.retention_days || 0) > 0 ? `Retention: ${policy.retention_days} day(s)` : "",
        policy.selection_enabled ? "Selection: checked artifact files" : "",
        policy.target_enabled && Number(policy.cleanup_target_gb || 0) === 0 ? "Storage target: current artifact backlog" : "",
        Number(policy.cleanup_target_gb || 0) > 0 ? `Storage target: ${policy.cleanup_target_gb} GB` : "",
        result?.message || "",
      ].filter((line) => line !== "");
      appendFailureArtifactCleanupDetails(lines, { errors, skipped, planned, deleted });
      setText("failure-artifact-cleanup-status", result?.ok ? (data.dry_run ? "Checked" : "Deleted") : "Blocked");
      setText("failure-artifact-cleanup-summary", lines.join("\n"));
    }

    function failureArtifactCleanupPayload(request) {
      return {
        dry_run: Boolean(request.dry_run),
        confirm_delete: Boolean(request.confirm_delete),
        reason: request.reason || "",
        dry_run_fingerprint: request.dry_run_fingerprint || "",
        artifact_paths: Array.isArray(request.artifact_paths) ? request.artifact_paths : [],
      };
    }

    async function requestFailureArtifactCleanup(dryRun) {
      if (reportsState.failureArtifactCleanupBusy) {
        setText("failure-artifact-cleanup-status", "Busy");
        setText("failure-artifact-cleanup-summary", "Another artifact delete command is already in progress.");
        return;
      }
      const request = failureArtifactCleanupRequest(dryRun);
      if (request.error) {
        setText("failure-artifact-cleanup-status", "Blocked");
        setText("failure-artifact-cleanup-summary", request.error);
        updateFailureArtifactCleanupConfirmState();
        return;
      }
      setFailureArtifactCleanupBusy(true, dryRun ? "" : "failure-artifact-cleanup-confirm-button");
      setText("failure-artifact-cleanup-status", dryRun ? "Checking..." : "Deleting...");
      setText("failure-artifact-cleanup-summary", dryRun ? "Checking selected artifacts. Nothing will be deleted yet." : "Checking selected artifacts, then deleting.");
      try {
        const confirmedArtifactCleanupPayload = (confirmedRequest) => ({
          ...failureArtifactCleanupPayload(confirmedRequest),
          confirm_delete: true,
        });
        const previewRequest = dryRun ? request : failureArtifactCleanupRequest(true);
        let result = await apiPost("/api/failures/artifacts/cleanup", failureArtifactCleanupPayload(previewRequest));
        if (dryRun) {
          if (typeof appendCommandResult === "function") appendCommandResult(result);
          renderFailureArtifactCleanupResult(result);
        }
        if (dryRun && result?.ok) {
          reportsState.lastFailureArtifactCleanupPreview = {
            ...(result.data || {}),
            key: previewRequest.key,
          };
          updateFailureArtifactCleanupConfirmState();
        }
        if (!dryRun) {
          if (!result?.ok) {
            if (typeof appendCommandResult === "function") appendCommandResult(result);
            renderFailureArtifactCleanupResult(result);
            return;
          }
          const plannedCount = Number(result?.data?.planned_count || 0) || (Array.isArray(result?.data?.planned) ? result.data.planned.length : 0);
          if (plannedCount < 1) {
            if (typeof appendCommandResult === "function") appendCommandResult(result);
            renderFailureArtifactCleanupResult(result);
            setText("failure-artifact-cleanup-status", "Blocked");
            return;
          }
          reportsState.lastFailureArtifactCleanupPreview = {
            ...(result.data || {}),
            key: previewRequest.key,
          };
          const confirmRequest = failureArtifactCleanupRequest(false, String(result?.data?.dry_run_fingerprint || ""));
          result = await apiPost("/api/failures/artifacts/cleanup", confirmedArtifactCleanupPayload(confirmRequest));
          if (typeof appendCommandResult === "function") appendCommandResult(result);
          renderFailureArtifactCleanupResult(result);
          reportsState.lastFailureArtifactCleanupPreview = null;
          if (result?.ok && reportsState.selectedFailureArtifactPaths instanceof Set) {
            confirmRequest.artifact_paths.forEach((path) => reportsState.selectedFailureArtifactPaths.delete(path));
          }
          updateFailureArtifactCleanupConfirmState();
          if (result?.ok && typeof refreshAll === "function") await refreshAll();
        }
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        const result = {
          command: "failures.artifacts_cleanup",
          ok: false,
          severity: "error",
          message,
          errors: [message],
        };
        if (typeof appendCommandResult === "function") appendCommandResult(result);
        renderFailureArtifactCleanupResult(result);
        updateFailureArtifactCleanupConfirmState();
      } finally {
        setFailureArtifactCleanupBusy(false);
      }
    }

    async function requestFailureEvidenceOpen(row, target, button = null) {
      const rowKey = failureRowKey(row);
      const cleanTarget = String(target || "").trim();
      if (!rowKey || !cleanTarget) {
        const message = "Select a failure evidence row before opening evidence.";
        const result = {
          command: "failures.open",
          ok: false,
          severity: "warning",
          message,
          warnings: [message],
        };
        if (typeof appendCommandResult === "function") appendCommandResult(result);
        return result;
      }
      const sourceKind = failureMarkerModeActive() ? "markers" : "latest_json";
      const payload = { row_key: rowKey, target: cleanTarget, source_kind: sourceKind };
      const originalDisabled = button ? button.disabled : false;
      if (button) {
        button.disabled = true;
        button.setAttribute("aria-busy", "true");
      }
      try {
        const result = await apiPost("/api/failures/open", payload);
        if (typeof appendCommandResult === "function") appendCommandResult(result);
        return result;
      } catch (error) {
        const message = error?.message || String(error || "Failed to open failure evidence.");
        const result = {
          command: "failures.open",
          ok: false,
          severity: "error",
          message,
          errors: [message],
        };
        if (typeof appendCommandResult === "function") appendCommandResult(result);
        return result;
      } finally {
        if (button) {
          button.disabled = originalDisabled;
          button.removeAttribute("aria-busy");
        }
      }
    }

    return {
      configureFailurePrimaryAction,
      failureTransition,
      renderFailureArtifactCleanupResult,
      renderFailureArchiveResult,
      renderFailureClearResult,
      requestFailureArtifactCleanup,
      requestFailureEvidenceOpen,
      requestFailureEvidenceArchive,
      requestFailureLifecycleTransition,
      requestFailureMarkerClear,
      requestFailureRowClear,
      runFailurePrimaryAction,
      setFailureLifecycleButton,
      updateFailureArtifactCleanupConfirmState,
      updateFailureArchiveConfirmState,
      updateFailureClearConfirmState,
      updateFailureLifecycleConfirmState,
    };
  }

  window.__reportsViewFailureCommandsModule = {
    createReportsFailureCommandsModule,
  };
})();
