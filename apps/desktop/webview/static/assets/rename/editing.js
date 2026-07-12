// Rename staged-path reset, ordering, selected overrides, and bulk-edit workflow.
(function () {
  "use strict";

  function createRenameEditingModule(deps = {}) {
    const {
      byId = () => null,
      clearRows = () => {},
      appendCells = () => {},
      collectRenameRequest = () => ({}),
      getCheckedRenameRows = () => [],
      getSelectedRenameRow = () => null,
      getRenameApplyScopeRows = () => ({ rows: [] }),
      renameCurrentPathValues = () => [],
      renamePathLines = () => [],
      renameConfidenceExplanation = () => "",
      renameConfidenceLabel = () => "",
      renamePreviewSourceLabel = () => "",
      renameRenderedRowsCount = () => 0,
      renameRowCanApply = () => false,
      renameSourceKey = () => "",
      renameSourceLabelFromRow = () => "",
      renameSourcePathFromRow = () => "",
      renameStatusExplanation = () => "",
      renameMarkInputChanged = () => {},
      RENAME_PREVIEW_RENDER_LIMIT = 250,
      refreshRenamePreview = async () => {},
      renderRenameFileSourceSummary = () => {},
      renderRenameRows = () => {},
      resetRenameApplyEvidence = () => {},
      setRenamePathLines = () => {},
      setRenameStatusLine = () => {},
      setText = () => {},
      state = {},
      syncRenameCheckedCount = () => {},
      syncRenameCommandButtons = () => {},
    } = deps;
    const documentRef = deps.documentRef || document;
    const windowRef = deps.windowRef || window;

  function clearRenamePaths() {
    const input = byId("rename-paths");
    if (input) input.value = "";
    const addInput = byId("rename-add-path-input");
    if (addInput) addInput.value = "";
    state.rows = [];
    state.selectedSourceKey = "";
    state.checkedSourceKeys.clear();
    Object.keys(state.pathOrigins).forEach((key) => delete state.pathOrigins[key]);
    state.previewSignature = "";
    state.previewStale = false;
    state.emptyMessage = "No paths entered. Add one file path per line, then run Preview.";
    clearRows(byId("rename-rows"), 6, state.emptyMessage);
    setRenameStatusLine("rename-status", "Idle", "empty");
    setRenameStatusLine("rename-preview-status", "No preview", "empty");
    setText("rename-summary", state.emptyMessage);
    renderRenameFileSourceSummary("Cleared staged rename paths.");
    renderRenameBatchSafety({ rows: [], counts: {} });
    renderRenamePipelineHandoff({ rows: [], counts: {} });
    renderRenameReviewBoard({ rows: [], counts: {} });
    renderRenameSelectionAudit();
    renderRenameApplyReadiness();
    renderRenameBulkEditor();
    resetRenameApplyEvidence("Cleared staged rename paths. Previous apply evidence is no longer tied to the current scope.");
    syncRenameCheckedCount();
    syncRenameCommandButtons();
  }

  function useSelectedQueueRowForRename() {
    const row = typeof windowRef.getSelectedQueueRow === "function"
      ? windowRef.getSelectedQueueRow()
      : (windowRef.mediaPipelineQueueView?.getSelectedQueueRow?.() || null);
    const path = renameSourcePathFromRow(row);
    if (!path) {
      renderRenameFileSourceSummary("No selected Queue row with a source path.");
      return;
    }
    appendRenamePaths([path], renameSourceLabelFromRow(row) || "Selected Queue row", "queue");
  }

  function useLoadedQueueRowsForRename() {
    const rows = typeof windowRef.getLastQueueRows === "function"
      ? windowRef.getLastQueueRows()
      : (windowRef.mediaPipelineQueueView?.getLastQueueRows?.() || []);
    const paths = (Array.isArray(rows) ? rows : []).map(renameSourcePathFromRow).filter(Boolean);
    if (!paths.length) {
      renderRenameFileSourceSummary("No loaded Queue source paths.");
      return;
    }
    appendRenamePaths(paths, "Loaded Queue rows", "queue");
  }

  function renameLineKey(line) {
    return String(line || "").trim().toLowerCase();
  }

  function checkedOrSelectedRenameKeys() {
    if (state.checkedSourceKeys.size) return new Set(state.checkedSourceKeys);
    return state.selectedSourceKey ? new Set([state.selectedSourceKey]) : new Set();
  }

  function moveCheckedRenamePaths(direction) {
    const keys = checkedOrSelectedRenameKeys();
    if (!keys.size) {
      setText("rename-detail", "Check one or more rows, or select one row, before moving path order.");
      return;
    }
    const lines = renamePathLines();
    const indexed = lines.map((line) => ({ line, selected: keys.has(renameLineKey(line)) }));
    const selectedCount = indexed.filter((item) => item.selected).length;
    if (!selectedCount) {
      setText("rename-detail", "Checked/selected rename rows are not present in the Paths textbox. Refresh preview or re-add paths before moving order.");
      return;
    }
    if (Number(direction) < 0) {
      for (let index = 1; index < indexed.length; index += 1) {
        if (indexed[index].selected && !indexed[index - 1].selected) {
          const previous = indexed[index - 1];
          indexed[index - 1] = indexed[index];
          indexed[index] = previous;
        }
      }
    } else {
      for (let index = indexed.length - 2; index >= 0; index -= 1) {
        if (indexed[index].selected && !indexed[index + 1].selected) {
          const next = indexed[index + 1];
          indexed[index + 1] = indexed[index];
          indexed[index] = next;
        }
      }
    }
    setRenamePathLines(indexed.map((item) => item.line));
    setText("rename-detail", `Moved ${selectedCount} path row(s) ${Number(direction) < 0 ? "up" : "down"}. Run Preview to rebuild TV sequence numbering from the new order.`);
  }

  function naturalCompareText(left, right) {
    const leftParts = String(left || "").toLowerCase().match(/\d+|\D+/g) || [String(left || "").toLowerCase()];
    const rightParts = String(right || "").toLowerCase().match(/\d+|\D+/g) || [String(right || "").toLowerCase()];
    const length = Math.max(leftParts.length, rightParts.length);
    for (let index = 0; index < length; index += 1) {
      const a = leftParts[index] || "";
      const b = rightParts[index] || "";
      const aNumber = /^\d+$/.test(a) ? Number(a) : NaN;
      const bNumber = /^\d+$/.test(b) ? Number(b) : NaN;
      if (Number.isFinite(aNumber) && Number.isFinite(bNumber) && aNumber !== bNumber) return aNumber - bNumber;
      if (a !== b) return a < b ? -1 : 1;
    }
    return 0;
  }

  function naturalSortRenamePaths() {
    const lines = renamePathLines();
    const nonEmpty = lines.filter((line) => line.trim());
    const empty = lines.filter((line) => !line.trim());
    nonEmpty.sort(naturalCompareText);
    setRenamePathLines([...nonEmpty, ...empty]);
    setText("rename-detail", "Paths were natural-sorted. Run Preview to rebuild TV sequence numbering from the new order.");
  }

  function syncRenameSelectedInputs(item) {
    const key = renameSourceKey(item);
    const finalInput = byId("rename-selected-final");
    const forceInput = byId("rename-selected-force");
    if (finalInput) finalInput.value = state.finalOverrides[key] || item?.target_name || "";
    if (forceInput) forceInput.checked = Boolean(state.forceOverrides[key] ?? item?.force_pipeline_name);
  }

  function captureRenameSelectionScroll() {
    return windowRef.mediaPipelineDom?.captureScrollablePositions?.() || null;
  }

  function restoreRenameSelectionScroll(snapshot) {
    if (snapshot) windowRef.mediaPipelineDom?.restoreScrollablePositions?.(snapshot);
  }

  function selectRenameRow(item) {
    const scrollSnapshot = captureRenameSelectionScroll();
    const key = renameSourceKey(item);
    state.selectedSourceKey = key;
    syncRenameSelectedInputs(item);
    renderRenameDetail(item || null);
    renderRenameBulkEditor();
    renderRenameRows();
    restoreRenameSelectionScroll(scrollSnapshot);
  }

  const renamePreviewSlice = windowRef.mediaPipelineRenamePreviewSlice.create({
    RENAME_PREVIEW_RENDER_LIMIT,
    collectRenameRequest,
    getCheckedRenameRows,
    getLastRenameEmptyMessage: () => state.emptyMessage,
    getLastSettings: () => (typeof windowRef.mediaPipelineSettingsView?.getLastSettings === "function" ? windowRef.mediaPipelineSettingsView.getLastSettings() : {}),
    getRenameFinalOverrides: () => state.finalOverrides,
    getRenameForceOverrides: () => state.forceOverrides,
    renamePreviewSourceLabel,
    renameRenderedRowsCount,
    renameSourceKey,
    setText,
  });
  const {
    renderRenameBatchSafety,
    renderRenamePipelineHandoff,
    renderRenameReviewBoard,
    renderRenameSummary,
    renameBatchSafetyLines,
    renameDuplicateTargets,
    renameFormatCounts,
    renamePipelineHandoffLines,
    renamePipelineHandoffStatus,
    renamePreviewAggregateObject,
    renameReviewBoardLines,
    renameReviewBoardStatus,
    renameSavedSettingsConfig,
    renameTemplateLabel,
  } = renamePreviewSlice;

  function renameBulkScopeRows() {
    const scope = byId("rename-bulk-scope")?.value || "checked";
    if (scope === "selected") {
      const selected = getSelectedRenameRow();
      return selected && renameRowCanApply(selected) ? [selected] : [];
    }
    if (scope === "all_applicable") return state.rows.filter((row) => renameRowCanApply(row));
    return getCheckedRenameRows().filter((row) => renameRowCanApply(row));
  }

  function renameBulkScopeLabel() {
    const scope = byId("rename-bulk-scope")?.value || "checked";
    if (scope === "selected") return "selected row";
    if (scope === "all_applicable") return "all applicable preview rows";
    return "checked rows";
  }

  function renameSplitFilename(name) {
    const value = String(name || "").trim();
    const dotIndex = value.lastIndexOf(".");
    if (dotIndex <= 0 || dotIndex === value.length - 1) return { base: value, ext: "" };
    return { base: value.slice(0, dotIndex), ext: value.slice(dotIndex) };
  }

  function renameBulkEditedName(name) {
    const findValue = byId("rename-bulk-find")?.value || "";
    const replaceValue = byId("rename-bulk-replace")?.value || "";
    const prefixValue = byId("rename-bulk-prefix")?.value || "";
    const suffixValue = byId("rename-bulk-suffix")?.value || "";
    const parts = renameSplitFilename(name);
    let edited = parts.base;
    if (findValue) edited = edited.split(findValue).join(replaceValue);
    edited = `${prefixValue}${edited}${suffixValue}`.trim();
    return edited ? `${edited}${parts.ext}` : "";
  }

  function renameBulkHasEditInput() {
    return Boolean(
      (byId("rename-bulk-find")?.value || "")
      || (byId("rename-bulk-prefix")?.value || "")
      || (byId("rename-bulk-suffix")?.value || "")
    );
  }

  function renameNameHasPathSeparator(name) {
    return /[\\/]/.test(String(name || ""));
  }

  function renameSetFinalOverride(row, finalName) {
    const key = renameSourceKey(row);
    if (!key) return false;
    const pipelineName = row?.pipeline_guess || row?.target_name || "";
    if (finalName && finalName !== pipelineName) state.finalOverrides[key] = finalName;
    else delete state.finalOverrides[key];
    return true;
  }

  function renderRenameBulkEditor(message = "") {
    const rows = renameBulkScopeRows();
    const stagedFinal = Object.keys(state.finalOverrides).length;
    const stagedForce = Object.keys(state.forceOverrides).filter((key) => state.forceOverrides[key]).length;
    const stagedForceOff = Object.keys(state.forceOverrides).filter((key) => state.forceOverrides[key] === false).length;
    const status = rows.length ? `${rows.length} row(s)` : "No scope";
    const lines = [
      `Scope: ${renameBulkScopeLabel()}; applicable rows in scope: ${rows.length}`,
      `Staged overrides: ${stagedFinal} final-name override(s), ${stagedForce} force-through-pipeline row(s), ${stagedForceOff} force-off row(s)`,
      "Stage Bulk Edit uses the current backend preview final names, edits only the filename stem, preserves extensions, then rebuilds backend preview.",
      "Use Pipeline Names clears final-name overrides for the scope; Clear Scope Overrides clears both final-name and force overrides for the scope.",
      "Mutation guardrail: this panel stages preview overrides only. Apply still calls backend rename.apply with selected_sources.",
    ];
    if (message) lines.unshift(message);
    setText("rename-bulk-edit-status", status);
    setText("rename-bulk-edit-summary", lines.join("\n"));
  }

  function stageRenameBulkEdit() {
    const rows = renameBulkScopeRows();
    if (!rows.length) {
      renderRenameBulkEditor(`No applicable rows in ${renameBulkScopeLabel()}. Check rows, select one row, or change the bulk scope.`);
      return;
    }
    if (!renameBulkHasEditInput()) {
      renderRenameBulkEditor("Enter a Find value, Prefix, or Suffix before staging a bulk final-name edit.");
      return;
    }
    let staged = 0;
    let unchanged = 0;
    let skipped = 0;
    rows.forEach((row) => {
      const current = renameCurrentFinalName(row);
      const edited = renameBulkEditedName(current);
      if (!edited || renameNameHasPathSeparator(edited)) {
        skipped += 1;
        return;
      }
      if (edited === current) {
        unchanged += 1;
        return;
      }
      if (renameSetFinalOverride(row, edited)) staged += 1;
    });
    renderRenameBulkEditor(`Staged ${staged} bulk final-name edit(s); ${unchanged} unchanged; ${skipped} skipped because the generated name was empty or contained a path separator.`);
    refreshRenamePreview();
  }

  function usePipelineNamesForRenameScope() {
    const rows = renameBulkScopeRows();
    if (!rows.length) {
      renderRenameBulkEditor(`No applicable rows in ${renameBulkScopeLabel()} to reset to pipeline names.`);
      return;
    }
    rows.forEach((row) => delete state.finalOverrides[renameSourceKey(row)]);
    renderRenameBulkEditor(`Cleared final-name overrides for ${rows.length} row(s). Backend preview will use pipeline names for this scope.`);
    refreshRenamePreview();
  }

  function setRenameBulkForce(forceValue) {
    const rows = renameBulkScopeRows();
    if (!rows.length) {
      renderRenameBulkEditor(`No applicable rows in ${renameBulkScopeLabel()} to update force-through-pipeline state.`);
      return;
    }
    rows.forEach((row) => {
      const key = renameSourceKey(row);
      if (!key) return;
      if (forceValue) state.forceOverrides[key] = true;
      else state.forceOverrides[key] = false;
    });
    renderRenameBulkEditor(`${forceValue ? "Enabled" : "Cleared"} force-through-pipeline override for ${rows.length} row(s).`);
    refreshRenamePreview();
  }

  function clearRenameBulkOverrides() {
    const rows = renameBulkScopeRows();
    if (!rows.length) {
      renderRenameBulkEditor(`No applicable rows in ${renameBulkScopeLabel()} to clear overrides.`);
      return;
    }
    rows.forEach((row) => {
      const key = renameSourceKey(row);
      delete state.finalOverrides[key];
      delete state.forceOverrides[key];
    });
    renderRenameBulkEditor(`Cleared final-name and force overrides for ${rows.length} row(s).`);
    refreshRenamePreview();
  }

  const renameApplyReadinessSlice = windowRef.mediaPipelineRenameApplyReadinessSlice.create({
    RENAME_PREVIEW_RENDER_LIMIT,
    appendCells,
    byId,
    collectRenameRequest,
    getCheckedRenameRows,
    getLastRenameRows: () => state.rows,
    getRenameFinalOverrides: () => state.finalOverrides,
    getRenameApplyScopeRows,
    getSelectedRenameRow,
    renameConfidenceExplanation,
    renameConfidenceLabel,
    renameDuplicateTargets,
    renameRenderedRowsCount,
    renameRowCanApply,
    renameSourceKey,
    renameStatusExplanation,
    setText,
  });
  const {
    renderRenameApplyReadiness,
    renderRenameDetail,
    renderRenameSelectionAudit,
    renameApplyReadinessRows,
    renameApplyReadinessStatus,
    renameApplyScopeBlockers,
    renameSelectionAuditStatus,
    renameSelectionDuplicateTargets,
  } = renameApplyReadinessSlice;

  function applyRenameSelectedOverride() {
    const row = getSelectedRenameRow();
    if (!row) {
      setText("rename-detail", "Select a rename row before previewing an override.");
      return;
    }
    const key = renameSourceKey(row);
    const finalValue = (byId("rename-selected-final")?.value || "").trim();
    const forceValue = Boolean(byId("rename-selected-force")?.checked);
    if (finalValue && finalValue !== row.pipeline_guess) state.finalOverrides[key] = finalValue;
    else delete state.finalOverrides[key];
    state.forceOverrides[key] = forceValue;
    refreshRenamePreview();
  }

  function clearRenameSelectedOverride() {
    const row = getSelectedRenameRow();
    if (!row) {
      setText("rename-detail", "Select a rename row before clearing an override.");
      return;
    }
    const key = renameSourceKey(row);
    delete state.finalOverrides[key];
    delete state.forceOverrides[key];
    const finalInput = byId("rename-selected-final");
    const forceInput = byId("rename-selected-force");
    if (finalInput) finalInput.value = row.pipeline_guess || row.target_name || "";
    if (forceInput) forceInput.checked = Boolean(row.force_pipeline_name);
    refreshRenamePreview();
  }

  function replaceRenamePathText(appliedRows) {
    const input = byId("rename-paths");
    if (!input || !Array.isArray(appliedRows) || !appliedRows.length) return;
    const replacements = {};
    appliedRows.forEach((row) => {
      if (row.source && row.destination) {
        replacements[String(row.source).toLowerCase()] = String(row.destination);
      }
    });
    const lines = input.value.split(/\r?\n/).map((line) => {
      const trimmed = line.trim();
      const key = trimmed.toLowerCase();
      const replacement = replacements[key];
      if (replacement && state.pathOrigins[key]) {
        state.pathOrigins[String(replacement).toLowerCase()] = state.pathOrigins[key];
        delete state.pathOrigins[key];
      }
      return replacement || line;
    });
    input.value = lines.join("\n");
    renderRenameFileSourceSummary();
    renameMarkInputChanged();
  }

  const renameApplyResultSlice = windowRef.mediaPipelineRenameApplyResultSlice.create({
    appendCells,
    byId,
    renderProgressBarsInto: function () {
      if (typeof windowRef.mediaPipelineProgressView?.renderProgressBarsInto === "function") {
        windowRef.mediaPipelineProgressView.renderProgressBarsInto.apply(windowRef.mediaPipelineProgressView, arguments);
      }
    },
    setText,
  });
  const {
    renderRenameApplyOutcomeReview,
    renderRenameApplyInFlight,
    renderRenameApplyProgress,
    renderRenameApplyResult: renderRenameApplyResultFromSlice,
    renameApplyOutcomeRows,
    renameApplyOutcomeStatus,
    renameApplyOutcomeStatusState,
    renameApplyOutcomeSummaryLines,
    renameApplyProgressBars,
    renameApplyResultLines,
  } = renameApplyResultSlice;


    return {
      renderRenameApplyReadiness,
      renderRenameBatchSafety,
      renderRenameDetail,
      renderRenamePipelineHandoff,
      renderRenameReviewBoard,
      renderRenameSelectionAudit,
      renderRenameSummary,
      renameApplyReadinessRows,
      renameApplyReadinessStatus,
      renameApplyScopeBlockers,
      renameBatchSafetyLines,
      renameDuplicateTargets,
      renameFormatCounts,
      renamePipelineHandoffLines,
      renamePipelineHandoffStatus,
      renamePreviewAggregateObject,
      renameReviewBoardLines,
      renameReviewBoardStatus,
      renameSavedSettingsConfig,
      renameSelectionAuditStatus,
      renameSelectionDuplicateTargets,
      renameTemplateLabel,
      renderRenameApplyOutcomeReview,
      renderRenameApplyInFlight,
      renderRenameApplyProgress,
      renderRenameApplyResult: renderRenameApplyResultFromSlice,
      renameApplyOutcomeRows,
      renameApplyOutcomeStatus,
      renameApplyOutcomeStatusState,
      renameApplyOutcomeSummaryLines,
      renameApplyProgressBars,
      renameApplyResultLines,
      clearRenamePaths,
      useSelectedQueueRowForRename,
      useLoadedQueueRowsForRename,
      renameLineKey,
      checkedOrSelectedRenameKeys,
      moveCheckedRenamePaths,
      naturalCompareText,
      naturalSortRenamePaths,
      syncRenameSelectedInputs,
      captureRenameSelectionScroll,
      restoreRenameSelectionScroll,
      selectRenameRow,
      renameBulkScopeRows,
      renameBulkScopeLabel,
      renameSplitFilename,
      renameBulkEditedName,
      renameBulkHasEditInput,
      renameNameHasPathSeparator,
      renameSetFinalOverride,
      renderRenameBulkEditor,
      stageRenameBulkEdit,
      usePipelineNamesForRenameScope,
      setRenameBulkForce,
      clearRenameBulkOverrides,
      applyRenameSelectedOverride,
      clearRenameSelectedOverride,
      replaceRenamePathText,
    };
  }

  window.__renameEditingModule = { createRenameEditingModule };
})();
