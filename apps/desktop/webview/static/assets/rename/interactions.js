(function () {
  function createRenameInteractionsModule(deps = {}) {
    const { byId, handleRenameDroppedPaths, renameDroppedPathValuesFromDataTransfer, renameDroppedPathValuesFromBridgeDetail, renameDropZoneIsVisible, renameWebviewFileDropEvent, applyRenameWorkbench, undoLastRenameApply, refreshRenamePreview, browseRenamePaths, openRenameBadCaseDialog, renameDialogById, submitRenameBadCaseDialog, clearRenamePaths, renameMarkInputChanged, syncRenameBadCaseButton, syncRenameUndoButton } = deps;
    const RENAME_WEBVIEW_FILE_DROP_EVENT = renameWebviewFileDropEvent;
      function renameSyncModeFieldVisibility() {
        const modeSelect = byId("rename-mode");
        const mode = String(modeSelect?.value || "tv").toLowerCase();
        const isTv = mode === "tv";
        document.querySelectorAll('[data-rename-mode-field="tv"]').forEach((node) => {
          node.style.display = isTv ? "" : "none";
        });
        const titleLabel = document.querySelector('label > input#rename-show')?.parentElement;
        if (titleLabel) {
          const firstTextNode = Array.from(titleLabel.childNodes).find((node) => node.nodeType === Node.TEXT_NODE && String(node.textContent || "").trim());
          if (firstTextNode) {
            firstTextNode.textContent = "Title / Show";
          }
        }
      }

      function renameInitDropZone() {
        const zone = byId("rename-drop-zone");
        if (!zone) return;
        const onDragOver = (event) => {
          event.preventDefault();
          event.stopPropagation();
          try { event.dataTransfer.dropEffect = "copy"; } catch (_err) { /* */ }
          zone.classList.add("is-dragging");
        };
        const onDragLeave = () => zone.classList.remove("is-dragging");
        const onDrop = (event) => {
          event.preventDefault();
          event.stopPropagation();
          zone.classList.remove("is-dragging");
          void handleRenameDroppedPaths(renameDroppedPathValuesFromDataTransfer(event.dataTransfer), "Drag and drop");
        };
        const onTauriFileDrop = (event) => {
          if (!renameDropZoneIsVisible(zone)) return;
          const detail = event?.detail || {};
          const kind = String(detail.kind || "").toLowerCase();
          if (kind === "enter" || kind === "over") {
            zone.classList.add("is-dragging");
            return;
          }
          if (kind === "leave") {
            zone.classList.remove("is-dragging");
            return;
          }
          if (kind !== "drop") return;
          zone.classList.remove("is-dragging");
          void handleRenameDroppedPaths(renameDroppedPathValuesFromBridgeDetail(detail), "Tauri drag and drop");
        };
        zone.addEventListener("dragenter", onDragOver);
        zone.addEventListener("dragover", onDragOver);
        zone.addEventListener("dragleave", onDragLeave);
        zone.addEventListener("drop", onDrop);
        window.addEventListener(RENAME_WEBVIEW_FILE_DROP_EVENT, onTauriFileDrop);
      }

      function renameInitWorkbenchEvents() {
        const applyButton = byId("rename-apply-button");
        if (applyButton) applyButton.addEventListener("click", () => applyRenameWorkbench());
        const undoButton = byId("rename-undo-button");
        if (undoButton) undoButton.addEventListener("click", () => undoLastRenameApply());
        const previewButton = byId("rename-preview-button");
        if (previewButton) previewButton.addEventListener("click", () => refreshRenamePreview());
        const browseFilesButton = byId("rename-browse-files-button");
        if (browseFilesButton) browseFilesButton.addEventListener("click", () => browseRenamePaths("files"));
        const browseFolderButton = byId("rename-browse-folder-button");
        if (browseFolderButton) browseFolderButton.addEventListener("click", () => browseRenamePaths("folder_files"));
        const logBadCaseButton = byId("rename-log-bad-case-button");
        if (logBadCaseButton) logBadCaseButton.addEventListener("click", () => openRenameBadCaseDialog());
        const logBadCaseCancelButton = byId("rename-log-case-cancel-button");
        if (logBadCaseCancelButton) {
          logBadCaseCancelButton.addEventListener("click", () => {
            const dialog = renameDialogById("rename-log-case-dialog");
            if (dialog) dialog.close("cancel");
          });
        }
        const logBadCaseSubmitButton = byId("rename-log-case-submit-button");
        if (logBadCaseSubmitButton) logBadCaseSubmitButton.addEventListener("click", () => submitRenameBadCaseDialog());
        const logBadCaseDialog = byId("rename-log-case-dialog");
        const logBadCaseForm = logBadCaseDialog?.querySelector("form");
        if (logBadCaseForm) {
          logBadCaseForm.addEventListener("submit", (event) => {
            event.preventDefault();
            submitRenameBadCaseDialog();
          });
        }
        const clearButton = byId("rename-clear-paths-button");
        if (clearButton) clearButton.addEventListener("click", () => clearRenamePaths());
        const modeSelect = byId("rename-mode");
        if (modeSelect) {
          modeSelect.addEventListener("change", () => {
            renameSyncModeFieldVisibility();
            refreshRenamePreview();
          });
        }
        [
          "rename-paths",
          "rename-template-preset",
          "rename-show",
          "rename-season",
          "rename-start",
          "rename-movie-year",
          "rename-sidecars",
          "rename-force-pipeline",
          "rename-pipeline-preview",
        ].forEach((id) => {
          const node = byId(id);
          if (!node) return;
          node.addEventListener("input", renameMarkInputChanged);
          node.addEventListener("change", renameMarkInputChanged);
        });
        renameSyncModeFieldVisibility();
        renameInitDropZone();
        syncRenameBadCaseButton();
        syncRenameUndoButton();
      }

    return { renameSyncModeFieldVisibility, renameInitWorkbenchEvents };
  }
  window.__renameInteractionsModule = { createRenameInteractionsModule };
})();
