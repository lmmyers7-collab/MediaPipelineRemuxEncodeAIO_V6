// Rename mutation confirmation and result-dialog presentation.
(function () {
  "use strict";

  function createRenameDialogsModule(deps = {}) {
    const {
      byId = () => null,
      previewRenderLimit = 250,
      renameConfirmBasename = (value) => String(value || ""),
      renameDialogById = () => null,
      renameLastApplyUndoCounts = () => ({ totalOps: 0 }),
      renderRenameConfirmSummary = () => {},
      renderRenameUndoConfirmSummary = () => {},
      setText = () => {},
      state = {},
      windowRef = window,
    } = deps;
    const documentRef = deps.documentRef || document;

  function renameOpenConfirmDialog(rowsToApply, outsideRootRows) {
    const dialog = renameDialogById("rename-confirm-dialog");
    if (!dialog) return Promise.resolve(false);
    setText("rename-confirm-title", "Confirm filesystem rename");
    const countEl = byId("rename-confirm-count");
    if (countEl) countEl.textContent = `Renaming ${rowsToApply.length} checked media file${rowsToApply.length === 1 ? "" : "s"}.`;
    setText("rename-confirm-mutation-warning", "Backend rename.apply will rename the checked media and matching sidecars.");
    const applyButton = byId("rename-confirm-apply-button");
    if (applyButton) applyButton.textContent = `Apply ${rowsToApply.length} Rename${rowsToApply.length === 1 ? "" : "s"}`;
    renderRenameConfirmSummary(byId("rename-confirm-list"), rowsToApply, outsideRootRows);
    const warningEl = byId("rename-confirm-warning");
    if (warningEl) {
      const warnings = [];
      const previewRows = Array.isArray(state.rows) ? state.rows : [];
      if (previewRows.length > previewRenderLimit) {
        const hiddenChecked = rowsToApply.filter((row) => previewRows.indexOf(row) >= previewRenderLimit).length;
        warnings.push(`Render cap: ${previewRenderLimit} of ${previewRows.length} preview rows are visible${hiddenChecked ? `; ${hiddenChecked} checked row(s) are not visible in the table` : ""}.`);
      }
      warningEl.textContent = warnings.join(" ");
      warningEl.hidden = !warnings.length;
    }
    return new Promise((resolve) => {
      const onClose = () => {
        if (typeof dialog.removeEventListener === "function") {
          dialog.removeEventListener("close", onClose);
        }
        const confirmed = dialog.returnValue === "confirm";
        if (!confirmed) {
          setText("rename-apply-status-hint", "Apply canceled. No rename.apply request was sent.");
          setText("rename-detail", "Apply canceled from confirmation modal. Preview and checked rows remain staged; no filesystem rename was requested.");
        }
        resolve(confirmed);
      };
      dialog.addEventListener("close", onClose);
      const cancelBtn = byId("rename-confirm-cancel-button");
      if (cancelBtn) {
        cancelBtn.onclick = () => dialog.close("cancel");
      }
      try {
        dialog.showModal();
      } catch (_err) {
        if (typeof dialog.removeEventListener === "function") {
          dialog.removeEventListener("close", onClose);
        }
        resolve(false);
      }
    });
  }

  function renameOpenUndoConfirmDialog() {
    const dialog = renameDialogById("rename-confirm-dialog");
    if (!dialog) return Promise.resolve(false);
    const counts = renameLastApplyUndoCounts();
    setText("rename-confirm-title", "Confirm undo rename");
    setText(
      "rename-confirm-count",
      `Undo last apply: ${counts.totalOps} operation${counts.totalOps === 1 ? "" : "s"}.`,
    );
    setText("rename-confirm-mutation-warning", "Backend rename.undo will restore the last apply using its undo manifest.");
    const applyButton = byId("rename-confirm-apply-button");
    if (applyButton) applyButton.textContent = "Undo Last Apply";
    renderRenameUndoConfirmSummary(byId("rename-confirm-list"));
    const warningEl = byId("rename-confirm-warning");
    if (warningEl) {
      warningEl.textContent = "";
      warningEl.hidden = true;
    }
    return new Promise((resolve) => {
      const onClose = () => {
        if (typeof dialog.removeEventListener === "function") {
          dialog.removeEventListener("close", onClose);
        }
        const confirmed = dialog.returnValue === "confirm";
        if (!confirmed) {
          setText("rename-apply-status-hint", "Undo canceled. No rename.undo request was sent.");
          setText("rename-detail", "Undo canceled from confirmation modal. The last apply undo remains available.");
        }
        resolve(confirmed);
      };
      dialog.addEventListener("close", onClose);
      const cancelBtn = byId("rename-confirm-cancel-button");
      if (cancelBtn) {
        cancelBtn.onclick = () => dialog.close("cancel");
      }
      try {
        dialog.showModal();
      } catch (_err) {
        if (typeof dialog.removeEventListener === "function") {
          dialog.removeEventListener("close", onClose);
        }
        resolve(false);
      }
    });
  }

  function renameOpenResultDialog(result) {
    const dialog = renameDialogById("rename-result-dialog");
    if (!dialog) return;
    const payload = result && typeof result === "object" ? (result.raw && typeof result.raw === "object" ? result.raw : result) : {};
    const data = payload.data && typeof payload.data === "object" ? payload.data : {};
    const rows = Array.isArray(data.rows) ? data.rows : [];
    const isUndo = String(payload.command || "").toLowerCase() === "rename.undo"
      || String(data.schema_version || "").toLowerCase() === "desktop_rename_undo_result.v1";
    const finiteCount = (value) => {
      const numberValue = Number(value);
      return Number.isFinite(numberValue) ? numberValue : null;
    };
    const setResultLabel = (id, value) => setText(id, value);
    if (isUndo) {
      const restored = finiteCount(data.undone) ?? rows.filter((row) => String(row.status || "").toLowerCase() === "undone").length;
      const skipped = finiteCount(data.skipped) ?? rows.filter((row) => String(row.status || "").toLowerCase() === "skipped").length;
      const failed = finiteCount(data.failed) ?? (payload.ok ? 0 : 1);
      const mediaOps = finiteCount(data.media_operations) ?? 0;
      const sidecarOps = finiteCount(data.sidecar_operations) ?? 0;
      setText("rename-result-title", "Undo result");
      setResultLabel("rename-result-success-label", "Restored");
      setResultLabel("rename-result-unchanged-label", "Media ops");
      setResultLabel("rename-result-skipped-label", "Skipped");
      setResultLabel("rename-result-protected-label", "Sidecar ops");
      setResultLabel("rename-result-failed-label", "Failed");
      const setNum = (id, value) => {
        const el = byId(id);
        if (el) el.textContent = String(value);
      };
      setNum("rename-result-success", restored);
      setNum("rename-result-renamed", restored);
      setNum("rename-result-unchanged", mediaOps);
      setNum("rename-result-skipped", skipped);
      setNum("rename-result-protected", sidecarOps);
      setNum("rename-result-failed", failed);
      const summaryEl = byId("rename-result-summary");
      if (summaryEl) {
        const manifestName = renameConfirmBasename(data.undo_manifest || state.lastUndoManifest);
        const warnings = Array.isArray(payload.warnings) ? payload.warnings.filter(Boolean) : [];
        summaryEl.textContent = [
          payload.ok ? `${restored} restored / ${skipped} skipped / ${failed} failed` : payload.message || "Rename undo failed.",
          manifestName ? `Undo manifest: ${manifestName}` : "",
          warnings.length ? `Warning: ${warnings.join("; ")}` : "",
        ].filter(Boolean).join("\n");
      }
      const errorsEl = byId("rename-result-errors");
      const errors = Array.isArray(payload.errors) ? payload.errors.filter((value) => String(value || "").trim()) : [];
      if (errorsEl) {
        errorsEl.innerHTML = "";
        if (errors.length || failed > 0 || !payload.ok) {
          errorsEl.hidden = false;
          const heading = documentRef.createElement("strong");
          heading.textContent = "Errors";
          errorsEl.appendChild(heading);
          const list = documentRef.createElement("ul");
          list.className = "rename-modal-error-list";
          const messages = errors.length ? errors : [payload.message || "Rename undo failed."];
          messages.forEach((msg) => {
            const li = documentRef.createElement("li");
            li.textContent = String(msg);
            list.appendChild(li);
          });
          errorsEl.appendChild(list);
        } else {
          errorsEl.hidden = true;
        }
      }
      const openLogButton = byId("rename-result-open-log-button");
      if (openLogButton) {
        openLogButton.hidden = true;
        openLogButton.onclick = null;
      }
      try {
        dialog.showModal();
      } catch (_err) { /* swallow */ }
      return;
    }
    setText("rename-result-title", "Rename result");
    setResultLabel("rename-result-success-label", "Renamed");
    setResultLabel("rename-result-unchanged-label", "Unchanged");
    setResultLabel("rename-result-skipped-label", "Skipped");
    setResultLabel("rename-result-protected-label", "Protected");
    setResultLabel("rename-result-failed-label", "Failed");
    let renamed = finiteCount(data.renamed) ?? finiteCount(data.success_count) ?? null;
    let unchanged = finiteCount(data.unchanged) ?? null;
    let failed = finiteCount(data.failed_count) ?? null;
    let skipped = finiteCount(data.skipped_count) ?? finiteCount(data.skipped) ?? null;
    let protectedCount = finiteCount(data.protected_count) ?? finiteCount(data.protected) ?? null;
    if ([renamed, unchanged, failed, skipped, protectedCount].some((value) => value === null) && rows.length) {
      const inferred = { renamed: 0, unchanged: 0, failed: 0, skipped: 0, protectedCount: 0 };
      rows.forEach((row) => {
        const status = String(row.status || row.outcome || "").toLowerCase();
        if (status === "success" || status === "renamed" || row.renamed === true) inferred.renamed += 1;
        else if (status === "match" || status === "unchanged" || status === "noop" || status === "no-op" || row.unchanged === true) inferred.unchanged += 1;
        else if (status === "protected" || row.protected === true) inferred.protectedCount += 1;
        else if (status === "skipped" || row.skipped === true) inferred.skipped += 1;
        else if (status === "failed" || status === "error" || row.failed === true) inferred.failed += 1;
      });
      if (renamed === null) renamed = inferred.renamed;
      if (unchanged === null) unchanged = inferred.unchanged;
      if (failed === null) failed = inferred.failed;
      if (skipped === null) skipped = inferred.skipped;
      if (protectedCount === null) protectedCount = inferred.protectedCount;
    }
    renamed = renamed ?? 0;
    unchanged = unchanged ?? 0;
    failed = failed ?? 0;
    skipped = skipped ?? 0;
    protectedCount = protectedCount ?? 0;
    const setNum = (id, value) => {
      const el = byId(id);
      if (el) el.textContent = String(value);
    };
    setNum("rename-result-success", renamed);
    setNum("rename-result-renamed", renamed);
    setNum("rename-result-unchanged", unchanged);
    setNum("rename-result-failed", failed);
    setNum("rename-result-skipped", skipped);
    setNum("rename-result-protected", protectedCount);
    const summaryEl = byId("rename-result-summary");
    if (summaryEl) {
      const summary = String(payload.message || (payload.ok ? "Rename completed." : "Rename did not complete."));
      const undoManifest = String(data.undo_manifest || "").trim();
      const undoManifestName = renameConfirmBasename(undoManifest);
      const logPath = String(data.log_path || data.log_folder || data.output_log || "").trim();
      summaryEl.textContent = [
        summary,
        undoManifestName ? `Undo manifest: ${undoManifestName}` : "",
        logPath ? `Run log evidence: ${logPath}` : "",
      ].filter(Boolean).join("\n");
    }
    const errorsEl = byId("rename-result-errors");
    const errors = Array.isArray(payload.errors) ? payload.errors.filter((value) => String(value || "").trim()) : [];
    if (errorsEl) {
      errorsEl.innerHTML = "";
      if (errors.length || failed > 0) {
        errorsEl.hidden = false;
        const heading = documentRef.createElement("strong");
        heading.textContent = "Errors";
        errorsEl.appendChild(heading);
        const list = documentRef.createElement("ul");
        list.className = "rename-modal-error-list";
        const messages = errors.length
          ? errors
          : rows.filter((row) => String(row.status || row.outcome || "").toLowerCase() === "failed").map((row) => String(row.error || row.message || row.source || "Unknown error"));
        messages.forEach((msg) => {
          const li = documentRef.createElement("li");
          li.textContent = String(msg);
          list.appendChild(li);
        });
        errorsEl.appendChild(list);
      } else {
        errorsEl.hidden = true;
      }
    }
    const openLogButton = byId("rename-result-open-log-button");
    if (openLogButton) {
      const logPath = String(data.log_path || data.log_folder || data.output_log || "").trim();
      openLogButton.hidden = !logPath;
      openLogButton.textContent = "Open Run Logs";
      openLogButton.onclick = logPath
        ? () => {
          const requestOpen = windowRef.mediaPipelineDiagnosticsView?.requestDiagnosticsOpen || windowRef.requestDiagnosticsOpen;
          if (typeof requestOpen === "function") requestOpen("run_logs");
        }
        : null;
      openLogButton.title = logPath
        ? `Log evidence reported by backend: ${logPath}. Open logs through the backend-owned Diagnostics targets.`
        : "";
    }
    try {
      dialog.showModal();
    } catch (_err) { /* swallow */ }
  }
    return {
      renameOpenConfirmDialog,
      renameOpenUndoConfirmDialog,
      renameOpenResultDialog,
    };
  }

  window.__renameDialogsModule = { createRenameDialogsModule };
})();
