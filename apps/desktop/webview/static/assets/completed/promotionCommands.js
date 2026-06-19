// completed/promotionCommands.js
// Split child of completedView.js. Delegates final-library promotion commands to backend routes.
/* eslint-disable max-lines-per-function -- moved promotion command logic during the completed-view split without behavior changes. */

(function () {
  "use strict";

  function noop() {}

  function normalizeDeps(deps = {}) {
    return {
      apiPost: typeof deps.apiPost === "function" ? deps.apiPost : async function () { throw new Error("apiPost is not available."); },
      appendCells: typeof deps.appendCells === "function" ? deps.appendCells : noop,
      appendCommandResult: typeof deps.appendCommandResult === "function" ? deps.appendCommandResult : noop,
      byId: typeof deps.byId === "function" ? deps.byId : function () { return null; },
      clearRows: typeof deps.clearRows === "function" ? deps.clearRows : noop,
      getSelectedCompletedRow: typeof deps.getSelectedCompletedRow === "function" ? deps.getSelectedCompletedRow : function () { return null; },
      refreshAll: typeof deps.refreshAll === "function" ? deps.refreshAll : null,
      refreshCurrentOutputStatus: typeof deps.refreshCurrentOutputStatus === "function" ? deps.refreshCurrentOutputStatus : null,
      renderCompletedRows: typeof deps.renderCompletedRows === "function" ? deps.renderCompletedRows : noop,
      selectCompletedRow: typeof deps.selectCompletedRow === "function" ? deps.selectCompletedRow : noop,
      setCellStatusChip: typeof deps.setCellStatusChip === "function" ? deps.setCellStatusChip : null,
      setText: typeof deps.setText === "function" ? deps.setText : noop,
      state: deps.state && typeof deps.state === "object" ? deps.state : {},
    };
  }

  function createCompletedPromotionCommandsModule(deps = {}) {
    const ctx = normalizeDeps(deps);
    const apiPost = ctx.apiPost;
    let commandInFlight = false;

    function finalLibraryPromotionItemsByKey(status = ctx.state.lastFinalLibraryPromotionStatus) {
      const payload = status && typeof status === "object" ? status : {};
      const items = Array.isArray(payload.items) ? payload.items : Array.isArray(payload.item_rows) ? payload.item_rows : [];
      const byKey = {};
      items.forEach((item) => {
        if (item?.row_key) byKey[item.row_key] = item;
      });
      return byKey;
    }

    function mergeFinalLibraryPromotionRows(rows, status = ctx.state.lastFinalLibraryPromotionStatus) {
      const byKey = finalLibraryPromotionItemsByKey(status);
      return (Array.isArray(rows) ? rows : []).map((row) => {
        const item = byKey[row?.row_key || ""];
        return item ? { ...row, ...item } : row;
      });
    }

    function finalLibraryPromotionStatusText(item = {}) {
      if (item.promoted_cleaned) return "✓ Promoted + cleaned";
      if (item.promoted) return "✓ Promoted";
      if (item.promoting) return "Promoting";
      if (item.paused) return "Paused";
      if (item.promotion_failed) return "Failed";
      if (item.ready_for_promotion) return "✓ Ready";
      if (item.no_destination_rule) return "No Destination Rule";
      if (item.destination_offline) return "Destination Offline";
      return item.final_library_promotion_status_label || "";
    }

    function finalLibraryPromotionChipState(item = {}) {
      if (item.promoted || item.promoted_cleaned) return "success";
      if (item.ready_for_promotion || item.promoting) return "ready";
      if (item.paused || item.destination_offline || item.no_destination_rule) return "warning";
      if (item.promotion_failed) return "error";
      return "unknown";
    }

    function finalLibraryPromotionActiveRun(status = ctx.state.lastFinalLibraryPromotionStatus) {
      const active = status?.active_run && typeof status.active_run === "object" ? status.active_run : {};
      return active?.run_id ? active : {};
    }

    function finalLibraryPromotionRunActive(status = ctx.state.lastFinalLibraryPromotionStatus) {
      const active = finalLibraryPromotionActiveRun(status);
      const state = String(active.status || "").toLowerCase();
      return Boolean(active.run_id && ["running", "pausing", "paused"].includes(state));
    }

    function finalLibraryPromotionActionState(item = {}) {
      const enabled = Boolean(ctx.state.lastFinalLibraryPromotionStatus?.enabled);
      if (!item) return { available: false, reason: "Select a completed output first." };
      if (commandInFlight) return { available: false, reason: "A promotion command is already in progress." };
      if (!enabled) return { available: false, reason: "Final Library Promotion is disabled in Settings." };
      if (finalLibraryPromotionRunActive(ctx.state.lastFinalLibraryPromotionStatus)) return { available: false, reason: "A final-library promotion run is already active." };
      if (item.promoted || item.promoted_cleaned) return { available: false, reason: "This output has already been promoted." };
      if (item.output_exists === false) return { available: false, reason: "The reviewed output is not present at the promotion source location." };
      if (item.no_destination_rule) return { available: false, reason: "No final-library destination rule is configured for this output." };
      if (item.destination_offline) return { available: false, reason: "The configured final-library destination is offline." };
      if (!item.final_library_destination_path) return { available: false, reason: "No final-library destination path is configured for this output." };
      if (!item.ready_for_promotion) return { available: false, reason: "This output is not currently marked ready for final-library promotion." };
      if (!item.row_key) return { available: false, reason: "This completed output has no backend row key." };
      return { available: true, reason: "Promote this reviewed output to the final library." };
    }

    function promotionStatusTone(message, available = false) {
      const text = String(message || "").toLowerCase();
      if (available || text.includes("ready") || text.includes("promote this reviewed")) return "ready";
      if (text.includes("in progress") || text.includes("active") || text.includes("running") || text.includes("paused")) return "running";
      if (text.includes("disabled") || text.includes("offline") || text.includes("not present") || text.includes("no final-library") || text.includes("no destination") || text.includes("not currently marked ready")) return "blocked";
      return "warning";
    }

    function setInlineStatus(id, message, state = "unknown") {
      const node = ctx.byId(id);
      if (!node) return;
      node.textContent = message || "";
      node.dataset.state = state || "unknown";
    }

    function finalLibraryPromotionFlagLines(status = ctx.state.lastFinalLibraryPromotionStatus) {
      const payload = status && typeof status === "object" ? status : {};
      return [
        `Overwrite existing final files: ${payload.overwrite_existing ? "yes - destructive" : "no"}`,
        `Cleanup after verified promotion: ${payload.cleanup_after_verified ? "yes" : "no"}`,
        "Backend owns destination selection and file movement.",
      ];
    }

    function finalLibraryPromotionConfirmMessage(rowCount, status = ctx.state.lastFinalLibraryPromotionStatus) {
      const count = Number(rowCount || 0);
      const heading = count === 1
        ? "Promote this reviewed output to the final library?"
        : `Promote ${count || "all eligible"} reviewed outputs to the final library?`;
      const reviewed = count === 1
        ? "This means you have reviewed the output and are ready for backend final-library promotion."
        : "This means you have reviewed the outputs and are ready for backend final-library promotion.";
      const lines = [
        heading,
        "",
        reviewed,
        ...finalLibraryPromotionFlagLines(status),
      ];
      return lines.join("\n");
    }

    function shouldConfirmFinalLibraryPromotion(rowCount, status = ctx.state.lastFinalLibraryPromotionStatus) {
      if (typeof window.confirm !== "function") return true;
      return window.confirm(finalLibraryPromotionConfirmMessage(rowCount, status));
    }

    function createCompletedPromotionButton(item = {}) {
      const action = finalLibraryPromotionActionState(item);
      if (!action.available) return null;
      const button = document.createElement("button");
      button.type = "button";
      button.className = "secondary-button completed-row-promotion-button";
      button.textContent = "Promote Reviewed Output";
      button.title = "Promote this reviewed output to the final library after confirmation.";
      button.dataset.completedPromoteRowKey = item.row_key || "";
      button.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        ctx.selectCompletedRow(item);
        requestSelectedFinalLibraryPromotion(item);
      });
      return button;
    }

    function appendCompletedPromotionCellAction(cell, item = {}) {
      if (!cell) return;
      const button = createCompletedPromotionButton(item);
      if (!button) return;
      cell.classList.add("completed-promotion-cell");
      cell.appendChild(button);
    }

    function renderCompletedPromotionActions(item = ctx.getSelectedCompletedRow()) {
      const action = finalLibraryPromotionActionState(item);
      document.querySelectorAll("[data-completed-promote-selected]").forEach((button) => {
        button.disabled = !action.available;
        button.setAttribute("aria-disabled", String(!action.available));
        button.textContent = "Promote Selected Reviewed Output";
        button.title = action.reason;
      });
      setInlineStatus(
        "completed-selected-promotion-status",
        action.available
          ? "Confirmable: selected output is ready for backend final-library promotion after operator confirmation."
          : `Blocked: ${action.reason}`,
        promotionStatusTone(action.reason, action.available)
      );
    }

    function renderFinalLibraryPromotion(status = {}) {
      const payload = status && typeof status === "object" ? status : {};
      ctx.state.lastFinalLibraryPromotionStatus = payload;
      if (Array.isArray(ctx.state.lastCompletedRows) && ctx.state.lastCompletedRows.length) {
        ctx.state.lastCompletedRows = mergeFinalLibraryPromotionRows(ctx.state.lastCompletedRows, payload);
      }
      const counts = payload.counts && typeof payload.counts === "object" ? payload.counts : {};
      const active = finalLibraryPromotionActiveRun(payload);
      const activeStatus = String(active.status || "").toLowerCase();
      const enabled = Boolean(payload.enabled);
      const eligible = Number(counts.eligible || 0);
      const warnings = Array.isArray(payload.warnings) ? payload.warnings.filter(Boolean) : [];
      const statusText = active.run_id
        ? `${active.status || "active"} / ${Number(active.completed_count || 0)} of ${Number(active.eligible_count || eligible || 0)}`
        : enabled
          ? `${eligible} ready`
          : "Disabled";
      ctx.setText("final-library-promotion-status", statusText);
      ctx.setText("final-library-promotion-summary", [
        `Enabled: ${enabled ? "yes" : "no"}`,
        `Verification: ${payload.verification_mode || "cautious"}`,
        `Cleanup after verified: ${payload.cleanup_after_verified ? "yes" : "no"}`,
        `Overwrite existing: ${payload.overwrite_existing ? "yes - destructive" : "no"}`,
        `Rows: ${Number(counts.total || 0)} total; ${eligible} ready; ${Number(counts.no_destination_rule || 0)} no rule; ${Number(counts.destination_offline || 0)} offline; ${Number(counts.promoted || 0)} promoted; ${Number(counts.promoted_cleaned || 0)} promoted + cleaned`,
        active.run_id ? `Active run: ${active.run_id}; status=${active.status || ""}; pause=${active.pause_state || ""}; consecutive failures=${Number(active.consecutive_failures || 0)}` : "Active run: none",
        active.stop_reason ? `Stop reason: ${active.stop_reason}` : "",
        payload.publish_root ? `Publish root: ${payload.publish_root}` : "",
        payload.evidence_root ? `Evidence: ${payload.evidence_root}` : "",
        ...warnings,
      ].filter(Boolean).join("\n"));

      const promoteButton = ctx.byId("final-library-promote-button");
      const pauseButton = ctx.byId("final-library-pause-button");
      const resumeButton = ctx.byId("final-library-resume-button");
      if (promoteButton) {
        promoteButton.disabled = commandInFlight || !enabled || finalLibraryPromotionRunActive(payload) || eligible <= 0;
        promoteButton.setAttribute("aria-disabled", String(promoteButton.disabled));
        promoteButton.title = promoteButton.disabled
          ? (enabled ? "No eligible reviewed files are ready for final-library promotion, or a promotion run is active." : "Final Library Promotion is disabled in Settings.")
          : `Promote ${eligible} reviewed file${eligible === 1 ? "" : "s"} to final-library destinations after confirmation.`;
      }
      const promoteReason = !enabled
        ? "Blocked: Final Library Promotion is disabled in Settings."
        : commandInFlight
          ? "Active: promotion command is already in progress."
          : finalLibraryPromotionRunActive(payload)
            ? `Active: promotion run ${active.run_id || ""} is ${active.status || "running"}.`
            : eligible <= 0
              ? "Blocked: no reviewed outputs are currently eligible for final-library promotion."
              : `Confirmable: ${eligible} reviewed output${eligible === 1 ? "" : "s"} can be sent to backend promotion after confirmation.`;
      setInlineStatus("final-library-promotion-command-status", promoteReason, promotionStatusTone(promoteReason, eligible > 0 && enabled && !commandInFlight && !finalLibraryPromotionRunActive(payload)));
      if (pauseButton) pauseButton.disabled = commandInFlight || !(active.run_id && ["running", "pausing"].includes(activeStatus));
      if (resumeButton) resumeButton.disabled = commandInFlight || !(active.run_id && activeStatus === "paused");

      const tbody = ctx.byId("final-library-promotion-rows");
      const items = Array.isArray(payload.items) ? payload.items : Array.isArray(payload.item_rows) ? payload.item_rows : [];
      if (!items.length) {
        ctx.clearRows(tbody, 3, "No final library promotion rows loaded.");
      } else {
        tbody.replaceChildren();
        items.slice(0, 40).forEach((item) => {
          const tr = document.createElement("tr");
          ctx.appendCells(tr, [
            finalLibraryPromotionStatusText(item),
            item.lookup_title || item.output_file || "",
            item.final_library_destination_path || "",
          ]);
          const statusCell = tr.querySelector("td");
          if (ctx.setCellStatusChip) {
            ctx.setCellStatusChip(statusCell, finalLibraryPromotionStatusText(item), finalLibraryPromotionChipState(item));
          }
          tbody.appendChild(tr);
        });
      }
      renderCompletedPromotionActions(ctx.getSelectedCompletedRow());
      window.mediaPipelineAppHome?.renderHomePromotionEntry?.(payload);
      ctx.renderCompletedRows();
    }

    function currentFinalLibraryPromotionRunId() {
      return String(finalLibraryPromotionActiveRun(ctx.state.lastFinalLibraryPromotionStatus).run_id || "");
    }

    function setFinalLibraryPromotionCommandBusy(isBusy) {
      commandInFlight = Boolean(isBusy);
      renderFinalLibraryPromotion(ctx.state.lastFinalLibraryPromotionStatus);
    }

    async function requestFinalLibraryPromotion(rowKeys = []) {
      if (commandInFlight) return;
      const selectedRowKeys = (Array.isArray(rowKeys) ? rowKeys : [rowKeys])
        .map((value) => String(value || "").trim())
        .filter(Boolean);
      if (!shouldConfirmFinalLibraryPromotion(selectedRowKeys.length || Number(ctx.state.lastFinalLibraryPromotionStatus?.counts?.eligible || 0), ctx.state.lastFinalLibraryPromotionStatus)) return;
      setFinalLibraryPromotionCommandBusy(true);
      ctx.setText("final-library-promotion-status", "Starting");
      try {
        const request = { confirm_promote: true };
        if (selectedRowKeys.length) request.row_keys = selectedRowKeys;
        const result = await apiPost("/api/final-library-promotion/promote-queue", request);
        ctx.appendCommandResult(result);
        ctx.setText("final-library-promotion-status", result.ok ? "Started" : "Start failed");
        if (result?.data && typeof result.data === "object") {
          renderFinalLibraryPromotion({ ...ctx.state.lastFinalLibraryPromotionStatus, active_run: result.data });
        }
        if (result?.ok) {
          if (ctx.refreshCurrentOutputStatus) {
            await ctx.refreshCurrentOutputStatus();
          } else if (ctx.refreshAll) {
            await ctx.refreshAll();
          }
        }
      } catch (error) {
        const message = error?.message || String(error);
        ctx.appendCommandResult({
          command: "final_library.promote_queue",
          ok: false,
          message,
          severity: "error",
        });
        ctx.setText("final-library-promotion-status", `Start failed: ${message}`);
      } finally {
        setFinalLibraryPromotionCommandBusy(false);
      }
    }

    async function requestSelectedFinalLibraryPromotion(item = ctx.getSelectedCompletedRow()) {
      const row = item || ctx.getSelectedCompletedRow();
      const action = finalLibraryPromotionActionState(row);
      if (!action.available) {
        ctx.setText("completed-open-status", action.reason);
        renderCompletedPromotionActions(row || null);
        return;
      }
      ctx.setText("completed-open-status", "Promotion request will be sent after confirmation. The backend owns destination selection and file movement.");
      await requestFinalLibraryPromotion([row.row_key]);
    }

    async function requestFinalLibraryPromotionPause() {
      if (commandInFlight) return;
      const runId = currentFinalLibraryPromotionRunId();
      if (!runId) {
        ctx.setText("final-library-promotion-status", "No active promotion run to pause.");
        return;
      }
      setFinalLibraryPromotionCommandBusy(true);
      try {
        const result = await apiPost("/api/final-library-promotion/pause", { run_id: runId });
        ctx.appendCommandResult(result);
        if (result?.data && typeof result.data === "object") {
          renderFinalLibraryPromotion({ ...ctx.state.lastFinalLibraryPromotionStatus, active_run: result.data });
        }
      } catch (error) {
        const message = error?.message || String(error);
        ctx.appendCommandResult({
          command: "final_library.pause",
          ok: false,
          message,
          severity: "error",
        });
        ctx.setText("final-library-promotion-status", `Pause failed: ${message}`);
      } finally {
        setFinalLibraryPromotionCommandBusy(false);
      }
    }

    async function requestFinalLibraryPromotionResume() {
      if (commandInFlight) return;
      const runId = currentFinalLibraryPromotionRunId();
      if (!runId) {
        ctx.setText("final-library-promotion-status", "No paused promotion run to resume.");
        return;
      }
      setFinalLibraryPromotionCommandBusy(true);
      try {
        const result = await apiPost("/api/final-library-promotion/resume", { run_id: runId });
        ctx.appendCommandResult(result);
        if (result?.data && typeof result.data === "object") {
          renderFinalLibraryPromotion({ ...ctx.state.lastFinalLibraryPromotionStatus, active_run: result.data });
        }
      } catch (error) {
        const message = error?.message || String(error);
        ctx.appendCommandResult({
          command: "final_library.resume",
          ok: false,
          message,
          severity: "error",
        });
        ctx.setText("final-library-promotion-status", `Resume failed: ${message}`);
      } finally {
        setFinalLibraryPromotionCommandBusy(false);
      }
    }

    return {
      appendCompletedPromotionCellAction,
      currentFinalLibraryPromotionRunId,
      finalLibraryPromotionActionState,
      finalLibraryPromotionChipState,
      finalLibraryPromotionStatusText,
      finalLibraryPromotionRunActive,
      finalLibraryPromotionItemsByKey,
      mergeFinalLibraryPromotionRows,
      renderCompletedPromotionActions,
      renderFinalLibraryPromotion,
      requestFinalLibraryPromotion,
      requestFinalLibraryPromotionPause,
      requestFinalLibraryPromotionResume,
      requestSelectedFinalLibraryPromotion,
    };
  }

  window.__completedViewPromotionCommandsModule = {
    createCompletedPromotionCommandsModule,
  };
})();
