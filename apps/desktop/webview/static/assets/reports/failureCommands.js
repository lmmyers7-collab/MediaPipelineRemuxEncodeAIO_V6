// reports/failureCommands.js
// Failure command request, preview, confirmation, and result helpers for reportsView.js.

(function () {
  "use strict";

  function noop() {}

  function createReportsFailureCommandsModule(deps = {}) {
    const reportsState = deps.state && typeof deps.state === "object" ? deps.state : {};
    const apiPost = typeof deps.apiPost === "function" ? deps.apiPost : async function () { throw new Error("apiPost unavailable"); };
    const appendCommandResult = typeof deps.appendCommandResult === "function" ? deps.appendCommandResult : null;
    const byId = typeof deps.byId === "function" ? deps.byId : function () { return null; };
    const failureArchiveButtonIds = Array.isArray(deps.failureArchiveButtonIds) ? deps.failureArchiveButtonIds : [];
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

    function setFailureLifecycleBusy(busy, activeId = "") {
      reportsState.failureLifecycleBusy = Boolean(busy);
      setButtonsBusy(failureLifecycleButtonIds, reportsState.failureLifecycleBusy, activeId);
      if (!reportsState.failureLifecycleBusy) updateFailureLifecycleConfirmState();
    }

    function hiddenFailureSelectionMessage(actionLabel = "selected marker cleanup") {
      const count = hiddenSelectedFailureCount();
      return `${count} selected failure row${count === 1 ? " is" : "s are"} hidden by the active filter/search. Return to All and clear search, or deselect hidden rows before ${actionLabel}.`;
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
      if (kind === "preview_marker_clear") {
        const select = byId("failure-clear-scope");
        if (select) select.value = "selected_group";
        requestFailureMarkerClear("selected_group", true);
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
      if (!dryRun && failureLifecyclePreviewRequired(transition)) {
        const key = failureLifecyclePreviewKey(request);
        if (!reportsState.lastFailureLifecyclePreview || reportsState.lastFailureLifecyclePreview.key !== key || !reportsState.lastFailureLifecyclePreview.dry_run_fingerprint) {
          return { error: "Preview this lifecycle transition again before confirming." };
        }
        request.dry_run_fingerprint = reportsState.lastFailureLifecyclePreview.dry_run_fingerprint;
      }
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
      const resolveMatches = Boolean(
        !resolveRequest.error &&
        reportsState.lastFailureLifecyclePreview?.key === failureLifecyclePreviewKey(resolveRequest) &&
        reportsState.lastFailureLifecyclePreview?.dry_run_fingerprint
      );
      const reopenMatches = Boolean(
        !reopenRequest.error &&
        reportsState.lastFailureLifecyclePreview?.key === failureLifecyclePreviewKey(reopenRequest) &&
        reportsState.lastFailureLifecyclePreview?.dry_run_fingerprint
      );
      setFailureLifecycleButton(
        "failure-lifecycle-resolve-confirm-button",
        Boolean(group && resolve),
        !resolveMatches || Boolean(resolve?.disabled),
        resolveMatches ? "Confirm the previewed resolve transition." : resolve?.disabled_reason || "Preview resolve first."
      );
      setFailureLifecycleButton(
        "failure-lifecycle-reopen-confirm-button",
        Boolean(group && reopen),
        !reopenMatches || Boolean(reopen?.disabled),
        reopenMatches ? "Confirm the previewed reopen transition." : reopen?.disabled_reason || "Preview reopen first."
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
        if (!window.confirm(`Confirm ${stateLabel}?\n\nThis writes only the failure resolution journal. It does not clear markers, archive reports, retry files, or touch media.`)) return;
      }
      const activeButtonId = transition === "mark_resolved"
        ? dryRun ? "failure-lifecycle-resolve-preview-button" : "failure-lifecycle-resolve-confirm-button"
        : transition === "reopen"
          ? dryRun ? "failure-lifecycle-reopen-preview-button" : "failure-lifecycle-reopen-confirm-button"
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
        return { error: hiddenFailureSelectionMessage(dryRun ? "previewing selected markers" : "clearing selected markers") };
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
        setText("failure-clear-summary", reportRenderedRowsNote(visibleRows, "failure rows"));
      }
      if (!markerPaths.length) {
        return {
          error: clearAll
            ? "No marker rows are loaded."
            : normalizedScope === "visible"
              ? "No visible marker rows are loaded."
              : normalizedScope === "selected_group"
                ? "Selected failure group has no active clearable marker paths."
                : "Select one or more failure marker rows first.",
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
        button.title = "Marker clear command is running.";
        return;
      }
      const scope = byId("failure-clear-scope")?.value || "selected_group";
      const request = failureClearRequest(scope, false);
      const matchesPreview = Boolean(
        !request.error &&
        reportsState.lastFailureClearPreview &&
        reportsState.lastFailureClearPreview.key === failureClearPreviewKey(request),
      );
      button.disabled = !matchesPreview;
      button.title = matchesPreview
        ? "Clear markers for the previewed scope."
        : "Preview marker clear for the current scope before confirming.";
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
        data.scope === "all_markers" ? "Scope note: all backend failure markers; backend enumerates marker paths." : "",
        `Planned marker clears: ${planned.length}`,
        `Moved markers: ${data.markers || 0}`,
        `Writes active marker folder: ${data.writes_failure_markers ? "yes" : "no"}`,
        `Touches media: ${data.touches_media ? "unexpected yes" : "no"}`,
        data.manifest_path ? `Clear manifest: ${data.manifest_path}` : "",
        data.archive_dir ? `Cleared marker archive: ${data.archive_dir}` : "",
        `Safe next action: ${data.safe_next_action || "Review marker rows before confirming."}`,
        "Guardrail: this command moves marker JSON out of State\\Failures\\Markers only; it does not delete media, logs, reports, completed manifests, pending publish state, or source/output files.",
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
        lines.push("", "Planned markers:", ...planned.slice(0, 8).map((item) => `- ${item.path || ""}`));
        if (planned.length > 8) lines.push(`- ... ${planned.length - 8} more`);
      }
      setText("failure-clear-status", result?.ok ? (data.dry_run ? "Preview ready" : "Cleared") : "Blocked");
      setText("failure-clear-summary", lines.join("\n"));
    }

    async function requestFailureMarkerClear(scope, dryRun) {
      if (reportsState.failureClearBusy) {
        setText("failure-clear-status", "Busy");
        setText("failure-clear-summary", "Another Reports marker cleanup command is already in progress.");
        return;
      }
      const request = failureClearRequest(scope, dryRun);
      if (request.error) {
        setText("failure-clear-status", "Blocked");
        setText("failure-clear-summary", request.error);
        return;
      }
      if (!dryRun && (!reportsState.lastFailureClearPreview || reportsState.lastFailureClearPreview.key !== failureClearPreviewKey(request))) {
        setText("failure-clear-status", "Preview required");
        setText("failure-clear-summary", "Preview marker clear for the current scope before confirming. This prevents clearing a different selection than the one reviewed.");
        return;
      }
      if (!dryRun) {
        const count = Array.isArray(request.marker_paths) ? request.marker_paths.length : 0;
        const targetText = request.all_markers ? "all active failure markers" : `${count} failure marker${count === 1 ? "" : "s"}`;
        const cappedNote = request.capped_visible_scope
          ? `\n\n${reportRenderedRowsNote(visibleFailureRows(), "failure rows")}`
          : "";
        const message = `Clear ${targetText}?\n\nThis moves active failure marker JSON out of the blocking folder so affected files can be retried later. It does not delete media files, logs, reports, manifests, source files, or output files.${cappedNote}`;
        if (!window.confirm(message)) return;
      }
      const activeButtonId = dryRun ? "failure-clear-preview-button" : "failure-clear-confirm-button";
      setFailureClearBusy(true, activeButtonId);
      setText("failure-clear-status", dryRun ? "Previewing..." : "Clearing...");
      setText("failure-clear-summary", dryRun
        ? `Previewing backend marker clear. No marker files will move.${request.capped_visible_scope ? `\n${reportRenderedRowsNote(visibleFailureRows(), "failure rows")}` : ""}`
        : request.all_markers ? "Clearing all backend marker files." : "Clearing backend marker files after confirmation.");
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

    function failureArchiveRequest(dryRun) {
      const includeMarkers = byId("failure-archive-include-markers")?.checked === true;
      const includeReports = byId("failure-archive-include-reports")?.checked === true;
      const reason = String(byId("failure-archive-reason")?.value || "").trim();
      if (!includeMarkers && !includeReports) {
        return { error: "Select active markers, round failure reports, or both before previewing archive." };
      }
      if (!dryRun && !reason) {
        return { error: "Enter a reason before confirming evidence archive." };
      }
      if (!dryRun && !reportsState.lastFailureArchivePreview?.dry_run_fingerprint) {
        return { error: "Preview archive first so the backend can issue a dry-run fingerprint." };
      }
      const requestKey = failureArchivePreviewKey({ scope: "all_active", include_markers: includeMarkers, include_reports: includeReports, journal_key: failureGroupJournalKey(getSelectedFailureGroup()) });
      if (!dryRun && reportsState.lastFailureArchivePreview?.key && reportsState.lastFailureArchivePreview.key !== requestKey) {
        return { error: "Preview archive again after changing evidence options." };
      }
      return {
        scope: "all_active",
        include_markers: includeMarkers,
        include_reports: includeReports,
        dry_run: Boolean(dryRun),
        confirm_archive: !dryRun,
        reason,
        dry_run_fingerprint: dryRun ? "" : reportsState.lastFailureArchivePreview.dry_run_fingerprint,
        journal_key: failureGroupJournalKey(getSelectedFailureGroup()),
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
        button.title = "Evidence archive command is running.";
        return;
      }
      const includeMarkers = byId("failure-archive-include-markers")?.checked === true;
      const includeReports = byId("failure-archive-include-reports")?.checked === true;
      const reason = String(byId("failure-archive-reason")?.value || "").trim();
      const currentKey = failureArchivePreviewKey({ scope: "all_active", include_markers: includeMarkers, include_reports: includeReports, journal_key: failureGroupJournalKey(getSelectedFailureGroup()) });
      const matchesPreview = Boolean(
        includeMarkers || includeReports
      ) && Boolean(
        reason &&
        reportsState.lastFailureArchivePreview?.dry_run_fingerprint &&
        (!reportsState.lastFailureArchivePreview.key || reportsState.lastFailureArchivePreview.key === currentKey)
      );
      button.disabled = !matchesPreview;
      button.title = matchesPreview
        ? "Archive evidence for the previewed options."
        : "Preview archive and enter a reason before confirming.";
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
        `Include markers: ${data.include_markers ? "yes" : "no"}`,
        `Include reports: ${data.include_reports ? "yes" : "no"}`,
        `Planned evidence files: ${planned.length}`,
        `Moved markers: ${data.markers || 0}`,
        `Moved reports: ${data.reports || 0}`,
        `Writes failure evidence: ${data.writes_failure_evidence ? "yes" : "no"}`,
        `Touches media: ${data.touches_media ? "unexpected yes" : "no"}`,
        data.manifest_path ? `Clear manifest: ${data.manifest_path}` : "",
        data.archive_dir ? `Evidence archive: ${data.archive_dir}` : "",
        data.dry_run_fingerprint ? `Fingerprint: ${data.dry_run_fingerprint}` : "",
        `Safe next action: ${data.safe_next_action || "Review preview and reason before confirming archive."}`,
        "Guardrail: archive moves active failure markers and round failure reports into a manifest-backed archive; it does not delete media, completed manifests, pending publish state, source files, or output files.",
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
      setText("failure-archive-status", result?.ok ? (data.dry_run ? "Preview ready" : "Archived") : "Blocked");
      setText("failure-archive-summary", lines.join("\n"));
    }

    async function requestFailureEvidenceArchive(dryRun) {
      if (reportsState.failureArchiveBusy) {
        setText("failure-archive-status", "Busy");
        setText("failure-archive-summary", "Another failure evidence archive command is already in progress.");
        return;
      }
      const request = failureArchiveRequest(dryRun);
      if (request.error) {
        setText("failure-archive-status", "Blocked");
        setText("failure-archive-summary", request.error);
        updateFailureArchiveConfirmState();
        return;
      }
      if (!dryRun) {
        const target = [
          request.include_markers ? "active markers" : "",
          request.include_reports ? "round failure reports" : "",
        ].filter(Boolean).join(" and ");
        if (!window.confirm(`Archive ${target}?\n\nReason: ${request.reason}\n\nThis moves evidence into the cleared-evidence archive and writes a manifest. It does not delete media, completed manifests, pending publish state, source files, or output files.`)) return;
      }
      setFailureArchiveBusy(true, dryRun ? "failure-archive-preview-button" : "failure-archive-confirm-button");
      setText("failure-archive-status", dryRun ? "Previewing..." : "Archiving...");
      setText("failure-archive-summary", dryRun ? "Previewing evidence archive. No evidence files will move." : "Archiving failure evidence after confirmation.");
      try {
        const result = await apiPost("/api/failures/archive-evidence", request);
        if (typeof appendCommandResult === "function") appendCommandResult(result);
        renderFailureArchiveResult(result);
        if (dryRun && result?.ok) {
          reportsState.lastFailureArchivePreview = {
            ...(result.data || {}),
            key: failureArchivePreviewKey(request),
          };
          updateFailureArchiveConfirmState();
        }
        if (!dryRun && result?.ok) {
          reportsState.lastFailureArchivePreview = null;
          updateFailureArchiveConfirmState();
          if (typeof refreshAll === "function") await refreshAll();
        }
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

    return {
      configureFailurePrimaryAction,
      failureTransition,
      renderFailureArchiveResult,
      renderFailureClearResult,
      requestFailureEvidenceArchive,
      requestFailureLifecycleTransition,
      requestFailureMarkerClear,
      requestFailureRowClear,
      runFailurePrimaryAction,
      setFailureLifecycleButton,
      updateFailureArchiveConfirmState,
      updateFailureClearConfirmState,
      updateFailureLifecycleConfirmState,
    };
  }

  window.__reportsViewFailureCommandsModule = {
    createReportsFailureCommandsModule,
  };
})();
