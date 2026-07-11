// Rename preview rendering, request lifecycle, and command-control projection.
(function () {
  "use strict";

  function createRenamePreviewLifecycleModule(deps = {}) {
    const {
      apiPost = async () => ({}),
      appendCells = () => {},
      byId = () => null,
      clearRows = () => {},
      collectRenameRequest = () => ({ paths: [] }),
      getCheckedRenameRows = () => [],
      getRenameApplyScopeRows = () => ({ rows: [] }),
      getSelectedRenameRow = () => null,
      makeRowSelectable = () => {},
      renameApplyScopeBlockers = () => [],
      renameConfidenceExplanation = () => "",
      renameConfidenceLabel = () => "",
      renameCurrentRequestSignature = () => "",
      renameDuplicateTargetSet = () => new Set(),
      renameImportantRowReason = () => "",
      renamePathLines = () => [],
      renamePreviewSourceLabel = () => "",
      renamePreviewStatusText = () => "",
      renameRenderCapText = () => "",
      renameRequestSignatureFromRequest = () => "",
      renameRowCanApply = () => false,
      renameRowStatusDisplay = () => "",
      renameSourceKey = () => "",
      renameStatusExplanation = () => "",
      renameTargetKey = () => "",
      RENAME_PREVIEW_RENDER_LIMIT = 250,
      renderRenameApplyReadiness = () => {},
      renderRenameBatchSafety = () => {},
      renderRenameBulkEditor = () => {},
      renderRenameDetail = () => {},
      renderRenameFileSourceSummary = () => {},
      renderRenamePipelineHandoff = () => {},
      renderRenameReviewBoard = () => {},
      renderRenameSelectionAudit = () => {},
      renderRenameSummary = () => {},
      selectRenameRow = () => {},
      setRenameRowCheckedFromCheckbox = () => {},
      setRenameStatusLine = () => {},
      setText = () => {},
      state = {},
      syncRenameBadCaseButton = () => {},
      syncRenameCheckedCount = () => {},
      syncRenameSelectedInputs = () => {},
      syncRenameUndoButton = () => {},
      updateRenamePreviewFreshnessState = () => false,
      updateRenameTableLegend = () => {},
    } = deps;
    const documentRef = deps.documentRef || document;

  function renderRenamePreview(preview, requestSignature = "") {
    const rows = Array.isArray(preview.rows) ? preview.rows : [];
    state.rows = rows;
    state.previewSignature = rows.length ? (requestSignature || renameCurrentRequestSignature()) : "";
    state.previewFingerprint = rows.length ? String(preview.preview_fingerprint || "").trim() : "";
    state.previewStale = false;
    state.emptyMessage = (preview.warnings || []).join(" | ") || "No rename rows available.";
    if (state.selectedSourceKey && !rows.some((row) => renameSourceKey(row) === state.selectedSourceKey)) {
      state.selectedSourceKey = "";
    }
    Array.from(state.checkedSourceKeys).forEach((key) => {
      if (!rows.some((row) => renameSourceKey(row) === key)) state.checkedSourceKeys.delete(key);
    });
    const counts = preview.counts || {};
    const capText = renameRenderCapText(rows);
    setRenameStatusLine("rename-status", `${counts.ready || 0} ready, ${counts.match || 0} match, ${counts.blocked || 0} blocked${capText ? `; ${capText}` : ""}`, (counts.blocked || 0) ? "blocked" : (counts.warning || 0) ? "warning" : "ready");
    setRenameStatusLine("rename-preview-status", renamePreviewStatusText(), "ready");
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
    if (!state.rows.length) {
      clearRows(tbody, 6, state.emptyMessage);
      updateRenameTableLegend(tbody);
      syncRenameCheckedCount();
      return;
    }
    const duplicateTargets = renameDuplicateTargetSet(state.rows);
    Array.from(state.checkedSourceKeys).forEach((key) => {
      const checkedRow = state.rows.find((row) => renameSourceKey(row) === key);
      const hardBlocked = !checkedRow
        || !renameRowCanApply(checkedRow)
        || duplicateTargets.has(renameTargetKey(checkedRow))
        || (Boolean(checkedRow.destination_exists) && !checkedRow.matches_target);
      if (hardBlocked) state.checkedSourceKeys.delete(key);
    });
    tbody.replaceChildren();
    state.rows.slice(0, RENAME_PREVIEW_RENDER_LIMIT).forEach((item) => {
      const row = documentRef.createElement("tr");
      const isDuplicateTarget = duplicateTargets.has(renameTargetKey(item));
      const isExistingCollision = Boolean(item.destination_exists) && !item.matches_target;
      row.dataset.status = isDuplicateTarget ? "duplicate" : isExistingCollision ? "blocked" : (item.status || "");
      if (isDuplicateTarget) row.dataset.renameDuplicate = "true";
      row.title = [
        `Status: ${item.status || "unknown"} - ${renameStatusExplanation(item.status)}`,
        `Confidence: ${renameConfidenceLabel(item) || "unknown"} - ${renameConfidenceExplanation(item.confidence)}`,
        `Preview source: ${renamePreviewSourceLabel(item.preview_source || "unknown")}`,
        `Change kind: ${item.change_kind || "unknown"}`,
        isDuplicateTarget ? "Duplicate target: this staged preview collides with another row and cannot be auto-checked." : "",
      ].filter(Boolean).join("\n");
      const key = renameSourceKey(item);
      row.dataset.sourceKey = key;
      const checkCell = documentRef.createElement("td");
      const checkbox = documentRef.createElement("input");
      checkbox.type = "checkbox";
      checkbox.checked = state.checkedSourceKeys.has(key);
      checkbox.disabled = !renameRowCanApply(item) || isDuplicateTarget || isExistingCollision;
      const rowReason = renameImportantRowReason(item);
      checkbox.title = checkbox.disabled
        ? `Blocked rename rows cannot be checked for apply${isDuplicateTarget ? ": duplicate target in staged preview" : isExistingCollision ? ": existing destination path" : rowReason ? `: ${rowReason}` : "."}`
        : "Check this row for backend selected_sources apply.";
      checkbox.addEventListener("click", (event) => {
        event.stopPropagation();
        setRenameRowCheckedFromCheckbox(item, checkbox);
      });
      checkbox.addEventListener("change", () => setRenameRowCheckedFromCheckbox(item, checkbox));
      checkCell.appendChild(checkbox);
      checkCell.addEventListener("click", (event) => {
        if (event.target === checkbox || checkbox.disabled) return;
        event.stopPropagation();
        checkbox.checked = !checkbox.checked;
        setRenameRowCheckedFromCheckbox(item, checkbox);
      });
      row.appendChild(checkCell);
      appendCells(row, [
        item.source_name || item.source || "",
        item.pipeline_guess || "",
        item.target_name || "",
        renameConfidenceLabel(item),
        isDuplicateTarget ? "Duplicate target" : isExistingCollision ? "Existing destination" : renameRowStatusDisplay(item),
      ]);
      makeRowSelectable(row, () => selectRenameRow(item), {
        selected: Boolean(key && key === state.selectedSourceKey),
        label: `Rename row ${item.source_name || item.source || ""}`,
      });
      tbody.appendChild(row);
    });
    updateRenameTableLegend(tbody);
    syncRenameCheckedCount();
  }

  function setRenamePreviewBusy(isBusy) {
    state.previewInFlight = Boolean(isBusy);
    syncRenameCommandButtons();
  }

  function setRenameApplyBusy(isBusy) {
    state.applyInFlight = Boolean(isBusy);
    syncRenameCommandButtons();
    syncRenameUndoButton();
  }

  function setRenameUndoBusy(isBusy) {
    state.undoInFlight = Boolean(isBusy);
    syncRenameCommandButtons();
    syncRenameUndoButton();
  }

  function syncRenameCommandButtons() {
    const commandBusy = state.previewInFlight || state.browseInFlight || state.applyInFlight || state.undoInFlight || state.badCaseInFlight;
    const stalePreview = updateRenamePreviewFreshnessState();
    const applyScope = getRenameApplyScopeRows();
    const rowsToApply = applyScope.rows;
    const readinessBlockers = stalePreview ? [] : renameApplyScopeBlockers(rowsToApply);
    const previewDuplicateTargets = renameDuplicateTargetSet(state.rows);
    const previewHasBlockedRows = previewDuplicateTargets.size > 0 || state.rows.some((row) => !renameRowCanApply(row));
    ["rename-preview-button", "rename-preview-top-button"].forEach((id) => {
      const button = byId(id);
      if (button) button.disabled = commandBusy;
    });
    const applyButton = byId("rename-apply-button");
    if (applyButton) {
      if (!state.rows.length) {
        applyButton.textContent = "Preview before apply";
      } else if (stalePreview) {
        applyButton.textContent = "Preview out of date";
      } else if (readinessBlockers.length || (!rowsToApply.length && previewHasBlockedRows)) {
        applyButton.textContent = "Resolve blockers before apply";
      } else if (state.checkedSourceKeys.size) {
        applyButton.textContent = `Apply ${rowsToApply.length} checked rename${rowsToApply.length === 1 ? "" : "s"}`;
      } else {
        applyButton.textContent = "Check rows before apply";
      }
      applyButton.disabled = commandBusy || !state.rows.length || stalePreview || !state.checkedSourceKeys.size || !rowsToApply.length || readinessBlockers.length > 0;
    }
    const hint = byId("rename-apply-status-hint");
    if (hint) {
      if (stalePreview) {
        hint.textContent = "Preview out of date. Run Preview again before applying.";
      } else if (readinessBlockers.length) {
        hint.textContent = `Blocked by readiness: ${readinessBlockers.join("; ")}`;
      } else if (state.rows.length && !rowsToApply.length && previewHasBlockedRows) {
        hint.textContent = previewDuplicateTargets.size
          ? `Resolve duplicate destination targets before applying: ${Array.from(previewDuplicateTargets).slice(0, 3).join(" | ")}`
          : "Resolve blocked preview rows before applying.";
      } else if (state.rows.length && !state.checkedSourceKeys.size) {
        hint.textContent = "No rows checked. Use Check visible ready rows or manually check reviewed rows before applying.";
      } else if (state.rows.length && state.checkedSourceKeys.size) {
        hint.textContent = "Checked rows are the apply scope.";
      } else {
        hint.textContent = "";
      }
    }
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
    if (checkButton) checkButton.disabled = commandBusy || !state.rows.length;
    const checkAllButton = byId("rename-check-all-button");
    if (checkAllButton) checkAllButton.disabled = commandBusy || !state.rows.length;
    const clearButton = byId("rename-clear-checks-button");
    if (clearButton) clearButton.disabled = state.browseInFlight || state.applyInFlight || state.checkedSourceKeys.size === 0;
    const moveUpButton = byId("rename-move-checked-up-button");
    if (moveUpButton) moveUpButton.disabled = commandBusy || !state.rows.length;
    const moveDownButton = byId("rename-move-checked-down-button");
    if (moveDownButton) moveDownButton.disabled = commandBusy || !state.rows.length;
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
    syncRenameBadCaseButton();
    syncRenameUndoButton();
  }

  async function refreshRenamePreview() {
    const requestId = ++state.previewRequestId;
    state.activePreviewRequestId = requestId;
    setRenamePreviewBusy(true);
    try {
      const request = collectRenameRequest();
      if (!request.paths.length) {
        if (requestId === state.activePreviewRequestId) {
          state.rows = [];
          state.selectedSourceKey = "";
          state.checkedSourceKeys.clear();
          state.previewSignature = "";
          state.previewStale = false;
          state.emptyMessage = "No paths entered. Add one file path per line, then run Preview.";
          clearRows(byId("rename-rows"), 6, state.emptyMessage);
          setRenameStatusLine("rename-status", "Idle", "empty");
          setRenameStatusLine("rename-preview-status", "No preview", "empty");
          setText("rename-summary", state.emptyMessage);
          renderRenameFileSourceSummary(state.emptyMessage);
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
      setRenameStatusLine("rename-status", "Previewing...", "running");
      const preview = await apiPost("/api/rename/preview", request);
      if (requestId !== state.activePreviewRequestId) return;
      renderRenamePreview(preview, renameRequestSignatureFromRequest(request));
    } catch (error) {
      if (requestId !== state.activePreviewRequestId) return;
      const message = error instanceof Error ? error.message : String(error);
      state.rows = [];
      state.selectedSourceKey = "";
      state.checkedSourceKeys.clear();
      state.previewSignature = "";
      state.previewStale = false;
      state.emptyMessage = message;
      clearRows(byId("rename-rows"), 6, message);
      setRenameStatusLine("rename-status", "Error", "blocked");
      setRenameStatusLine("rename-preview-status", "Preview failed", "blocked");
      setText("rename-summary", `Rename preview failed.\n${message}`);
      renderRenameBatchSafety({ rows: [], counts: {}, warnings: [message] });
      renderRenamePipelineHandoff({ rows: [], counts: {}, warnings: [message] });
      renderRenameReviewBoard({ rows: [], counts: {}, warnings: [message] });
      renderRenameSelectionAudit();
      renderRenameApplyReadiness();
      renderRenameBulkEditor(message);
    } finally {
      if (requestId === state.activePreviewRequestId) {
        state.activePreviewRequestId = 0;
        setRenamePreviewBusy(false);
      }
    }
  }
    return {
      renderRenamePreview,
      renderRenameRows,
      setRenamePreviewBusy,
      setRenameApplyBusy,
      setRenameUndoBusy,
      syncRenameCommandButtons,
      refreshRenamePreview,
    };
  }

  window.__renamePreviewLifecycleModule = { createRenamePreviewLifecycleModule };
})();

