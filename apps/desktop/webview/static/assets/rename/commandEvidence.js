// Rename command activity, result evidence, and undo status projection.
(function () {
  "use strict";

  function createRenameCommandEvidenceModule(deps = {}) {
    const {
      byId = () => null,
      renameConfirmBasename = (value) => String(value || ""),
      renderRenameApplyResultFromSlice = () => {},
      setRenameStatusLine = () => {},
      setText = () => {},
      state = {},
      windowRef = window,
    } = deps;
    const documentRef = deps.documentRef || document;

    function renameApplyPayloadFromResult(result) {
      if (!result || typeof result !== "object") return {};
      return result.raw && typeof result.raw === "object" ? result.raw : result;
    }

    function renameUndoManifestFromApplyResult(result) {
      const payload = renameApplyPayloadFromResult(result);
      const data = payload.data && typeof payload.data === "object" ? payload.data : {};
      return String(data.undo_manifest || "").trim();
    }

    function renameElapsedText(startedAt) {
      const elapsedMs = Math.max(0, Date.now() - Number(startedAt || Date.now()));
      const seconds = Math.floor(elapsedMs / 1000);
      if (seconds < 60) return `${seconds}s`;
      const minutes = Math.floor(seconds / 60);
      return `${minutes}m ${String(seconds % 60).padStart(2, "0")}s`;
    }

    function stopRenameCommandActivity() {
      if (state.commandActivityTimer) {
        clearTimeout(state.commandActivityTimer);
        state.commandActivityTimer = 0;
      }
      state.commandActivityState = null;
    }

    function scheduleRenameCommandActivityTick() {
      if (!state.commandActivityState || typeof setTimeout !== "function") return;
      if (state.commandActivityTimer) clearTimeout(state.commandActivityTimer);
      state.commandActivityTimer = setTimeout(() => {
        state.commandActivityTimer = 0;
        if (!state.commandActivityState) return;
        renderRenameCommandActivity();
        scheduleRenameCommandActivityTick();
      }, 1000);
    }

    function renderRenameCommandActivity() {
      const container = byId("rename-apply-progress-bars");
      if (!container || !state.commandActivityState) return;
      const activity = state.commandActivityState;
      const wrapper = documentRef.createElement("div");
      wrapper.className = "rename-command-activity";
      wrapper.dataset.state = "running";
      wrapper.setAttribute("role", "status");
      wrapper.setAttribute("aria-live", "polite");

      const header = documentRef.createElement("div");
      header.className = "rename-command-activity-header";
      const title = documentRef.createElement("p");
      title.className = "rename-command-activity-title";
      title.textContent = activity.title;
      const meta = documentRef.createElement("p");
      meta.className = "rename-command-activity-meta rename-command-activity-indicator";
      meta.textContent = `Waiting for backend result - elapsed ${renameElapsedText(activity.startedAt)}`;
      header.appendChild(title);
      header.appendChild(meta);
      wrapper.appendChild(header);

      const detail = documentRef.createElement("p");
      detail.className = "rename-command-activity-detail";
      detail.textContent = activity.detail;
      wrapper.appendChild(detail);
      container.replaceChildren(wrapper);
    }

    function startRenameCommandActivity(kind, count) {
      stopRenameCommandActivity();
      const planned = Math.max(0, Number(count || 0));
      const isUndo = kind === "undo";
      state.commandActivityState = {
        kind,
        startedAt: Date.now(),
        title: isUndo
          ? "Undoing last apply... waiting for backend result"
          : `Renaming ${planned} media file${planned === 1 ? "" : "s"}... waiting for backend result`,
        detail: isUndo
          ? "Undo command submitted to the backend. This is command activity, not row-by-row progress."
          : `${planned} checked rename${planned === 1 ? "" : "s"} submitted. This is command activity, not row-by-row progress.`,
      };
      const panel = byId("rename-apply-status-panel");
      if (panel) panel.dataset.state = "running";
      setRenameStatusLine("rename-apply-status-summary", state.commandActivityState.title, "running");
      renderRenameCommandActivity();
      scheduleRenameCommandActivityTick();
    }

    function syncRenameUndoButton() {
      const button = byId("rename-undo-button");
      const status = byId("rename-undo-status");
      const hasManifest = Boolean(state.lastUndoManifest);
      if (button) {
        button.hidden = !state.lastApplyHadResult;
        button.disabled = state.applyInFlight || state.undoInFlight || !hasManifest || state.lastUndoCompleted;
        button.textContent = "Undo Last Apply";
        button.title = hasManifest
          ? `Undo manifest: ${state.lastUndoManifest}`
          : "Undo is unavailable because the last backend apply result did not report an undo manifest.";
      }
      if (status) {
        if (!state.lastApplyHadResult) status.textContent = "No undo available.";
        else if (state.lastUndoCompleted) status.textContent = "Undo completed.";
        else if (hasManifest) status.textContent = "Undo available for the last apply.";
        else status.textContent = "No undo manifest reported for this apply.";
      }
    }

    function syncRenameApplyStatusPanelFromResult(result) {
      const payload = renameApplyPayloadFromResult(result);
      const data = payload.data && typeof payload.data === "object" ? payload.data : {};
      const panel = byId("rename-apply-status-panel");
      const renamed = Number(data.renamed || 0);
      const applied = Number(data.applied_count ?? data.selected ?? 0);
      if (panel) panel.dataset.state = payload.ok ? "ready" : payload.severity || "blocked";
      if (!payload || !Object.keys(payload).length) {
        setRenameStatusLine("rename-apply-status-summary", "Ready to apply 0 checked renames", "waiting");
        return;
      }
      if (payload.ok) {
        setRenameStatusLine("rename-apply-status-summary", `${renamed} renamed / ${applied} applied`, "ready");
      } else {
        setRenameStatusLine("rename-apply-status-summary", payload.message || "Rename apply failed", "blocked");
      }
    }

    function renderRenameApplyResult(result) {
      stopRenameCommandActivity();
      renderRenameApplyResultFromSlice(result);
      if (!result) {
        state.lastApplyHadResult = false;
        state.lastUndoManifest = "";
        state.lastUndoCompleted = false;
        state.lastApplyResultPayload = null;
        syncRenameApplyStatusPanelFromResult(null);
        syncRenameUndoButton();
        return;
      }
      const payload = renameApplyPayloadFromResult(result);
      state.lastApplyHadResult = Boolean(payload && Object.keys(payload).length);
      state.lastUndoManifest = payload.ok ? renameUndoManifestFromApplyResult(payload) : "";
      state.lastApplyResultPayload = payload.ok ? payload : null;
      state.lastUndoCompleted = false;
      syncRenameApplyStatusPanelFromResult(payload);
      syncRenameUndoButton();
    }

    function renameFiniteNumber(value, fallback = 0) {
      const numberValue = Number(value);
      return Number.isFinite(numberValue) ? numberValue : fallback;
    }

    function renameLastApplyUndoCounts() {
      const payload = state.lastApplyResultPayload && typeof state.lastApplyResultPayload === "object" ? state.lastApplyResultPayload : {};
      const data = payload.data && typeof payload.data === "object" ? payload.data : {};
      const rows = Array.isArray(data.rows) ? data.rows : [];
      const media = renameFiniteNumber(data.media_operations, renameFiniteNumber(data.applied_count, renameFiniteNumber(data.selected, rows.length)));
      const sidecarOps = renameFiniteNumber(data.sidecar_operations, renameFiniteNumber(data.sidecars, rows.reduce((acc, row) => acc + renameFiniteNumber(row?.sidecar_count, 0), 0)));
      return {
        media,
        sidecars: renameFiniteNumber(data.sidecars, sidecarOps),
        sidecarOps,
        totalOps: media + sidecarOps,
        manifestName: renameConfirmBasename(state.lastUndoManifest) || "last apply manifest",
      };
    }

    function renderRenameUndoCompletionProgress(payload) {
      stopRenameCommandActivity();
      const data = payload.data && typeof payload.data === "object" ? payload.data : {};
      const undone = renameFiniteNumber(data.undone, 0);
      const skipped = renameFiniteNumber(data.skipped, 0);
      const failed = renameFiniteNumber(data.failed, payload.ok ? 0 : 1);
      const isOk = Boolean(payload.ok && failed <= 0);
      const detail = isOk
        ? `${undone} restored / ${skipped} skipped / ${failed} failed`
        : String(payload.message || "Rename undo failed.");
      const renderer = windowRef.mediaPipelineProgressView?.renderProgressBarsInto;
      if (typeof renderer === "function") {
        const updatedAt = new Date().toISOString();
        renderer("rename-apply-progress-bars", [{
          id: "rename_undo",
          label: "Rename undo",
          mode: "determinate",
          percent: isOk ? 100 : 0,
          status: isOk ? "complete" : "failed",
          detail,
          source: payload.command || "rename.undo",
          updated_at: updatedAt,
          stale: false,
        }], { status: isOk ? "complete" : "failed", updated_at: updatedAt }, "No rename undo result loaded.");
        return;
      }
      setText("rename-apply-progress-bars", `Rename undo\n${isOk ? "complete - 100%" : "failed"}\n${detail}`);
    }

    function renderRenameUndoResult(result) {
      stopRenameCommandActivity();
      const payload = renameApplyPayloadFromResult(result);
      const data = payload.data && typeof payload.data === "object" ? payload.data : {};
      const undone = Number(data.undone || 0);
      const skipped = Number(data.skipped || 0);
      const failed = Number(data.failed || 0);
      const status = payload.ok && failed <= 0 ? "ready" : "blocked";
      const panel = byId("rename-apply-status-panel");
      if (panel) panel.dataset.state = payload.ok && failed <= 0 ? "undone" : "failed";
      setRenameStatusLine("rename-apply-status-summary", payload.ok ? `${undone} restored / ${skipped} skipped operations` : payload.message || "Rename undo failed", status);
      setRenameStatusLine("rename-last-apply-status", payload.ok ? `Undo completed: ${undone} restored / ${skipped} skipped` : "Undo failed", status);
      renderRenameUndoCompletionProgress(payload);
      setText("rename-last-apply-detail", [
        `Command: ${payload.command || "rename.undo"}`,
        `Result: ${payload.ok ? "ok" : payload.severity || "error"}`,
        `Message: ${payload.message || ""}`,
        `Undo manifest: ${renameConfirmBasename(data.undo_manifest || state.lastUndoManifest)}`,
        `Media operations: ${data.media_operations ?? ""}`,
        `Sidecar operations: ${data.sidecar_operations ?? ""}`,
        `Undone operations: ${undone}`,
        `Skipped operations: ${skipped}`,
        `Failed operations: ${failed}`,
      ].join("\n"));
      state.lastUndoCompleted = Boolean(payload.ok && failed <= 0);
      syncRenameUndoButton();
    }

    function resetRenameApplyEvidence(reason = "") {
      renderRenameApplyResult(null);
      setRenameStatusLine("rename-last-apply-status", "No apply", "empty");
      if (reason) {
        setText("rename-last-apply-detail", reason);
        setText("rename-apply-history", `${reason}\nRecent backend command history may still include earlier rename.apply entries, but no apply evidence is staged for the current paths.`);
      }
    }

    return {
      renameApplyPayloadFromResult,
      renameUndoManifestFromApplyResult,
      stopRenameCommandActivity,
      startRenameCommandActivity,
      syncRenameUndoButton,
      renderRenameApplyResult,
      renameLastApplyUndoCounts,
      renderRenameUndoResult,
      resetRenameApplyEvidence,
    };
  }

  window.__renameCommandEvidenceModule = { createRenameCommandEvidenceModule };
})();
