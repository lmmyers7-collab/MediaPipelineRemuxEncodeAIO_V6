// Rename row selection, checked-scope, path textbox, and bad-case workflow.
(function () {
  "use strict";

  function createRenameSelectionModule(deps = {}) {
    const {
      apiPost = null,
      appendCommandResult = () => {},
      byId = () => null,
      renameDialogById = () => null,
      renameDuplicateTargets = null,
      RENAME_PREVIEW_RENDER_LIMIT = 250,
      renderRenameApplyReadiness = () => {},
      renderRenameBulkEditor = () => {},
      renderRenameSelectionAudit = () => {},
      setText = () => {},
      state = {},
      syncRenameCommandButtons = () => {},
    } = deps;
    const documentRef = deps.documentRef || document;
    const windowRef = deps.windowRef || window;

  function renameSourceKey(item) {
    return String(item?.source || "").toLowerCase();
  }

  function getSelectedRenameRow() {
    if (!state.selectedSourceKey) return null;
    return state.rows.find((row) => renameSourceKey(row) === state.selectedSourceKey) || null;
  }

  function getCheckedRenameRows() {
    return state.rows.filter((row) => state.checkedSourceKeys.has(renameSourceKey(row)));
  }

  function renameRenderedRowsCount(rows = state.rows) {
    const rowCount = Array.isArray(rows) ? rows.length : 0;
    return Math.min(rowCount, RENAME_PREVIEW_RENDER_LIMIT);
  }

  function renameRenderCapText(rows = state.rows) {
    const rowCount = Array.isArray(rows) ? rows.length : 0;
    if (rowCount <= RENAME_PREVIEW_RENDER_LIMIT) return "";
    return `${RENAME_PREVIEW_RENDER_LIMIT} shown / ${rowCount} preview rows`;
  }

  function renameStatusState(value) {
    const normalized = String(value || "").toLowerCase();
    if (normalized.includes("block") || normalized.includes("duplicate") || normalized.includes("failed") || normalized.includes("error")) return "blocked";
    if (normalized.includes("review") || normalized.includes("warning") || normalized.includes("out of date") || normalized.includes("verify") || normalized.includes("mixed")) return "warning";
    if (normalized.includes("ready") || normalized.includes("applied") || normalized.includes("renamed")) return "ready";
    if (normalized.includes("match") || normalized.includes("no changes") || normalized.includes("recorded") || normalized.includes("checked")) return "changed";
    if (normalized.includes("idle") || normalized.includes("no ") || normalized.includes("waiting")) return "empty";
    return "unknown";
  }

  function setRenameStatusLine(id, value, state = "") {
    setText(id, value);
    const node = byId(id);
    if (node) node.dataset.state = state || renameStatusState(value);
  }

  function renameRowStatus(item) {
    return String(item?.status || "").trim().toLowerCase();
  }

  function renameRowHasWarnings(item) {
    return Array.isArray(item?.warnings) && item.warnings.length > 0;
  }

    function renameDuplicateTargetSet(rows = state.rows) {
    const candidates = Array.isArray(rows) ? rows : [];
    const duplicates = typeof renameDuplicateTargets === "function"
      ? renameDuplicateTargets(candidates)
      : candidates.reduce((values, row) => {
        const target = String(row?.destination || row?.target_name || "").trim().toLowerCase();
        if (!target) return values;
        values[target] = (values[target] || 0) + 1;
        return values;
      }, {});
    const duplicateValues = Array.isArray(duplicates)
      ? duplicates
      : Object.keys(duplicates).filter((key) => Number(duplicates[key]) > 1);
    return new Set(duplicateValues.map((value) => String(value || "").trim().toLowerCase()).filter(Boolean));
  }

  function renameTargetKey(item) {
    return String(item?.destination || item?.target_name || "").trim().toLowerCase();
  }

  function renameAutoCheckSkipReason(item, duplicateTargets = renameDuplicateTargetSet()) {
    if (!renameRowCanApply(item)) return "blocked";
    if (renameRowHasWarnings(item) || renameRowStatus(item) === "warning") return "warning";
    if (duplicateTargets.has(renameTargetKey(item))) return "duplicate";
    if (Boolean(item?.destination_exists) && !item?.matches_target) return "existing destination";
    return "";
  }

  function updateRenameTableLegend(tbody) {
    updateTableStatusLegend("rename-table-legend", tbody, "Rename rows");
    const capText = renameRenderCapText();
    if (!capText) return;
    const checkedRows = getCheckedRenameRows();
    const hiddenChecked = checkedRows.filter((row) => state.rows.indexOf(row) >= RENAME_PREVIEW_RENDER_LIMIT).length;
    const current = byId("rename-table-legend")?.textContent || "";
    setText("rename-table-legend", `${current} Display cap: ${capText} rendered. ${hiddenChecked ? `${hiddenChecked} checked row(s) are outside the visible table; clear them and review visible rows before applying.` : "Rows not visible in the table are not selected automatically; automatic selection is limited to visible rows for review."}`);
  }

  function renameCurrentFinalName(row) {
    const key = renameSourceKey(row);
    return state.finalOverrides[key] || row?.target_name || row?.pipeline_guess || row?.source_name || "";
  }

  function renameRowCanApply(item) {
    if (!item) return false;
    if (String(item.status || "").toLowerCase() === "blocked") return false;
    return !(Array.isArray(item.errors) && item.errors.length);
  }

  function renameImportantRowReason(item) {
    const errors = Array.isArray(item?.errors) ? item.errors.map(String) : [];
    const warnings = Array.isArray(item?.warnings) ? item.warnings.map(String) : [];
    const candidates = [...errors, ...warnings];
    const match = (pattern) => candidates.find((value) => value.toLowerCase().includes(pattern));
    if (match("two selected files would produce the same destination")) return "duplicate destination";
    if (match("destination already exists")) return "destination already exists";
    if (match("sidecar destination already exists")) return "sidecar destination exists";
    if (match("outside configured")) return "outside configured roots";
    return candidates[0] || "";
  }

  function renameRowStatusDisplay(item) {
    const status = String(item?.status || "").trim();
    const reason = renameImportantRowReason(item);
    if (!status || !reason) return status;
    return `${status.charAt(0).toUpperCase()}${status.slice(1)}: ${reason}`;
  }

  function getRenameApplyScopeRows() {
    const checked = getCheckedRenameRows();
    if (checked.length) return { rows: checked, source: "checked rows" };
    return { rows: [], source: "none; check intended rows before apply" };
  }

  function syncRenameCheckedCount() {
    const rows = getCheckedRenameRows();
    const blocked = rows.filter((row) => !renameRowCanApply(row)).length;
    const text = blocked
      ? `${rows.length} checked; ${blocked} blocked`
      : `${rows.length} checked`;
    setText("rename-selected-count", text);
    renderRenameSelectionAudit();
    renderRenameApplyReadiness();
    renderRenameBulkEditor();
    syncRenameCommandButtons();
  }

  function setRenameRowChecked(item, checked) {
    const key = renameSourceKey(item);
    if (!key) return;
    if (checked) state.checkedSourceKeys.add(key);
    else state.checkedSourceKeys.delete(key);
    syncRenameCheckedCount();
  }

  function setRenameRowCheckedFromCheckbox(item, checkbox) {
    if (!checkbox || checkbox.disabled) return;
    setRenameRowChecked(item, checkbox.checked);
  }

  function checkApplicableRenameRows() {
    state.checkedSourceKeys.clear();
    const duplicateTargets = renameDuplicateTargetSet(state.rows);
    const skipped = {};
    const reviewableRows = state.rows.slice(0, RENAME_PREVIEW_RENDER_LIMIT);
    reviewableRows.forEach((row) => {
      const reason = renameAutoCheckSkipReason(row, duplicateTargets);
      if (!reason) {
        state.checkedSourceKeys.add(renameSourceKey(row));
      } else {
        skipped[reason] = (skipped[reason] || 0) + 1;
      }
    });
    renderRenameRows();
    renderRenameSelectionAudit();
    renderRenameApplyReadiness();
    const checkedCount = state.checkedSourceKeys.size;
    const skippedText = Object.keys(skipped).sort().map((key) => `${key}=${skipped[key]}`).join(", ");
    const unrendered = Math.max(0, state.rows.length - reviewableRows.length);
    const message = `Checked ${checkedCount} visible ready/match row${checkedCount === 1 ? "" : "s"}; skipped ${reviewableRows.length - checkedCount}${skippedText ? ` (${skippedText})` : ""}.${unrendered ? ` ${unrendered} additional preview row${unrendered === 1 ? " is" : "s are"} not selected because they are not visible for review.` : ""}`;
    setRenameStatusLine("rename-selection-audit-status", checkedCount ? "Checked ready rows" : "No ready rows checked", checkedCount ? "ready" : "blocked");
    setText("rename-apply-status-hint", message);
    setText("rename-detail", `${message} Warning rows remain manually checkable after review; duplicate, blocked, and existing-destination rows stay out of apply scope.`);
  }

  function checkAllRenameRows() {
    state.checkedSourceKeys.clear();
    const duplicateTargets = renameDuplicateTargetSet(state.rows);
    const skipped = {};
    const reviewableRows = state.rows.slice(0, RENAME_PREVIEW_RENDER_LIMIT);
    reviewableRows.forEach((row) => {
      let reason = "";
      if (!renameRowCanApply(row)) reason = "blocked";
      else if (duplicateTargets.has(renameTargetKey(row))) reason = "duplicate";
      else if (Boolean(row?.destination_exists) && !row?.matches_target) reason = "existing destination";
      if (!reason) {
        state.checkedSourceKeys.add(renameSourceKey(row));
      } else {
        skipped[reason] = (skipped[reason] || 0) + 1;
      }
    });
    renderRenameRows();
    renderRenameSelectionAudit();
    renderRenameApplyReadiness();
    const checkedCount = state.checkedSourceKeys.size;
    const skippedText = Object.keys(skipped).sort().map((key) => `${key}=${skipped[key]}`).join(", ");
    const unrendered = Math.max(0, state.rows.length - reviewableRows.length);
    const message = `Checked ${checkedCount} visible selectable row${checkedCount === 1 ? "" : "s"}; skipped ${reviewableRows.length - checkedCount}${skippedText ? ` (${skippedText})` : ""}.${unrendered ? ` ${unrendered} additional preview row${unrendered === 1 ? " is" : "s are"} not selected because they are not visible for review.` : ""}`;
    setRenameStatusLine("rename-selection-audit-status", checkedCount ? "Checked selectable rows" : "No selectable rows checked", checkedCount ? "ready" : "blocked");
    setText("rename-apply-status-hint", message);
    setText("rename-detail", `${message} Review warnings before apply; duplicate, blocked, and existing-destination rows stay out of apply scope.`);
  }

  function clearCheckedRenameRows() {
    state.checkedSourceKeys.clear();
    renderRenameRows();
    renderRenameSelectionAudit();
    renderRenameApplyReadiness();
    setRenameStatusLine("rename-selection-audit-status", "No selection", "empty");
    setText("rename-apply-status-hint", "Cleared checked rows. Check intended rows before applying.");
    setText("rename-detail", "Cleared checked rows. No rename apply scope is staged.");
  }

  function renamePathLines() {
    return (byId("rename-paths")?.value || "").split(/\r?\n/);
  }

  function setRenamePathLines(lines) {
    const input = byId("rename-paths");
    if (!input) return;
    input.value = lines.join("\n");
    renderRenameFileSourceSummary();
    syncRenameCommandButtons();
  }

  function renameSourcePathFromRow(row) {
    return String(row?.source_path || row?.source || row?.path || row?.file || row?.input_path || "").trim();
  }

  function renameSourceLabelFromRow(row) {
    return String(row?.display_name || row?.relative_path || row?.source_name || row?.source_path || row?.source || "").trim();
  }

  function renamePathSegments(value) {
    return String(value || "").trim().split(/[\\/]+/).filter(Boolean);
  }

  function renameFileLeafFromPath(value) {
    const parts = renamePathSegments(value);
    return parts.length ? parts[parts.length - 1] : "";
  }

  function renameParentFolderLeafFromPath(value) {
    const parts = renamePathSegments(value);
    return parts.length > 1 ? parts[parts.length - 2] : "";
  }

  function renameFolderLeafFromValue(value) {
    const parts = renamePathSegments(value);
    return parts.length ? parts[parts.length - 1] : "";
  }

  function renameExpectedShowFromName(name) {
    const match = String(name || "").match(/^(.+?)\s+-\s+S\d{2}E\d{2,3}\b/i);
    return match ? match[1].trim() : "";
  }

  function renameExpectedSeasonFromName(name) {
    const match = String(name || "").match(/\bS(\d{2})E\d{2,3}\b/i);
    return match ? Number.parseInt(match[1], 10) : null;
  }

  function renameSeasonNumberFromWorkbench() {
    const value = String(byId("rename-season")?.value || "").trim();
    const match = value.match(/\d+/);
    const parsed = match ? Number.parseInt(match[0], 10) : 1;
    return Number.isFinite(parsed) && parsed > 0 ? parsed : 1;
  }

  function compactRenameNote(value) {
    return String(value || "").replace(/\s+/g, " ").trim();
  }

  function renameBadCasePayloadFromRow(row, overrides = {}) {
    const sourcePath = renameSourcePathFromRow(row);
    const sourceFolder = renameFolderLeafFromValue(row?.source_folder || row?.parent_folder || row?.folder || "")
      || renameParentFolderLeafFromPath(sourcePath);
    const sourceFile = renameFileLeafFromPath(sourcePath)
      || renameFileLeafFromPath(row?.source_name || row?.name || row?.file || "");
    const expectedName = String(overrides.expected_name ?? renameCurrentFinalName(row) ?? "").trim();
    const expectedShow = String(overrides.expected_show ?? renameExpectedShowFromName(expectedName) ?? "").trim();
    const expectedSeason = overrides.expected_season ?? renameExpectedSeasonFromName(expectedName);
    const payload = {
      source_folder: String(overrides.source_folder ?? sourceFolder ?? "").trim(),
      source_file: String(overrides.source_file ?? sourceFile ?? "").trim(),
      expected_name: expectedName,
      expected_show: expectedShow,
      season_number: Number.isFinite(Number(overrides.season_number))
        ? Number(overrides.season_number)
        : renameSeasonNumberFromWorkbench(),
      status: String(overrides.status || "pending").trim().toLowerCase(),
      notes: compactRenameNote(overrides.notes || ""),
      confirm_append: true,
    };
    if (expectedShow) payload.expected_clean_folder = expectedShow;
    if (expectedSeason !== null && expectedSeason !== undefined && String(expectedSeason).trim() !== "") {
      const parsedSeason = Number.parseInt(String(expectedSeason), 10);
      if (Number.isFinite(parsedSeason)) payload.expected_season = parsedSeason;
    }
    if (!payload.notes) delete payload.notes;
    return payload;
  }

  async function submitRenameBadCasePayload(payload) {
    const request = { ...(payload || {}), confirm_append: true };
    const result = await apiPost("/api/rename/filter-cases", request);
    appendCommandResult({ ...result, request });
    return result;
  }

  function setRenameBadCaseBusy(isBusy) {
    state.badCaseInFlight = Boolean(isBusy);
    const submitButton = byId("rename-log-case-submit-button");
    if (submitButton) {
      submitButton.disabled = state.badCaseInFlight;
      submitButton.textContent = state.badCaseInFlight ? "Appending..." : "Append Case";
    }
    syncRenameCommandButtons();
  }

  function renameLogCaseInput(id) {
    return byId(`rename-log-case-${id}`);
  }

  function setRenameLogCaseInputValue(id, value) {
    const node = renameLogCaseInput(id);
    if (node) node.value = value === null || value === undefined ? "" : String(value);
  }

  function renameBadCaseDialogOverrides() {
    const expectedSeason = renameLogCaseInput("expected-season")?.value || "";
    return {
      source_folder: renameLogCaseInput("source-folder")?.value || "",
      source_file: renameLogCaseInput("source-file")?.value || "",
      expected_name: renameLogCaseInput("expected-name")?.value || "",
      expected_show: renameLogCaseInput("expected-show")?.value || "",
      expected_season: expectedSeason,
      status: byId("rename-log-case-status-select")?.value || "pending",
      notes: renameLogCaseInput("notes")?.value || "",
    };
  }

  function syncRenameBadCaseButton() {
    const button = byId("rename-log-bad-case-button");
    const row = getSelectedRenameRow();
    const commandBusy = state.previewInFlight || state.browseInFlight || state.applyInFlight || state.badCaseInFlight;
    if (button) button.disabled = commandBusy || !row;
    const status = byId("rename-log-bad-case-status");
    if (status && !state.badCaseInFlight) {
      status.textContent = row ? "Selected row can be logged to the filter corpus." : "Select a preview row to log a case.";
    }
  }

  function openRenameBadCaseDialog() {
    const row = getSelectedRenameRow();
    if (!row) {
      setText("rename-log-bad-case-status", "Select a preview row before logging a case.");
      syncRenameBadCaseButton();
      return;
    }
    const payload = renameBadCasePayloadFromRow(row);
    setRenameLogCaseInputValue("source-folder", payload.source_folder);
    setRenameLogCaseInputValue("source-file", payload.source_file);
    setRenameLogCaseInputValue("expected-name", payload.expected_name);
    setRenameLogCaseInputValue("expected-show", payload.expected_show);
    setRenameLogCaseInputValue("expected-season", payload.expected_season ?? "");
    const statusSelect = byId("rename-log-case-status-select");
    if (statusSelect) statusSelect.value = payload.status || "pending";
    setRenameLogCaseInputValue("notes", payload.notes || "");
    setText("rename-log-case-message", "");
    const dialog = renameDialogById("rename-log-case-dialog");
    if (!dialog) return;
    try {
      dialog.showModal();
    } catch (_err) { /* swallow */ }
  }

  async function submitRenameBadCaseDialog() {
    const row = getSelectedRenameRow();
    if (!row || state.badCaseInFlight) return;
    const payload = renameBadCasePayloadFromRow(row, renameBadCaseDialogOverrides());
    if (!payload.source_folder || !payload.source_file || !payload.expected_name) {
      setText("rename-log-case-message", "Source folder, source file, and expected name are required.");
      return;
    }
    setRenameBadCaseBusy(true);
    setText("rename-log-case-message", "Appending case...");
    setText("rename-log-bad-case-status", "Appending case...");
    try {
      const result = await submitRenameBadCasePayload(payload);
      const message = result?.message || (result?.ok ? "Rename filter case appended." : "Rename filter case was not appended.");
      if (result?.ok) {
        const visibleMessage = `${message} Backend corpus entry recorded; no filesystem rename was requested.`;
        setText("rename-log-bad-case-status", visibleMessage);
        setText("rename-log-case-message", visibleMessage);
      } else {
        setText("rename-log-case-message", message);
        setText("rename-log-bad-case-status", message);
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setText("rename-log-case-message", message);
      setText("rename-log-bad-case-status", message);
      appendCommandResult({ command: "rename.filter_case.append", ok: false, severity: "error", message });
    } finally {
      setRenameBadCaseBusy(false);
    }
  }


    return {
      renameSourceKey,
      getSelectedRenameRow,
      getCheckedRenameRows,
      renameRenderedRowsCount,
      renameRenderCapText,
      renameStatusState,
      setRenameStatusLine,
      renameRowStatus,
      renameRowHasWarnings,
      renameDuplicateTargetSet,
      renameTargetKey,
      renameAutoCheckSkipReason,
      updateRenameTableLegend,
      renameCurrentFinalName,
      renameRowCanApply,
      renameImportantRowReason,
      renameRowStatusDisplay,
      getRenameApplyScopeRows,
      syncRenameCheckedCount,
      setRenameRowChecked,
      setRenameRowCheckedFromCheckbox,
      checkApplicableRenameRows,
      checkAllRenameRows,
      clearCheckedRenameRows,
      renamePathLines,
      setRenamePathLines,
      renameSourcePathFromRow,
      renameSourceLabelFromRow,
      renamePathSegments,
      renameFileLeafFromPath,
      renameParentFolderLeafFromPath,
      renameFolderLeafFromValue,
      renameExpectedShowFromName,
      renameExpectedSeasonFromName,
      renameSeasonNumberFromWorkbench,
      compactRenameNote,
      renameBadCasePayloadFromRow,
      submitRenameBadCasePayload,
      setRenameBadCaseBusy,
      renameLogCaseInput,
      setRenameLogCaseInputValue,
      renameBadCaseDialogOverrides,
      syncRenameBadCaseButton,
      openRenameBadCaseDialog,
      submitRenameBadCaseDialog,
    };
  }

  window.__renameSelectionModule = { createRenameSelectionModule };
})();
