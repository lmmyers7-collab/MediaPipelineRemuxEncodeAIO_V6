(function () {
  function createQueueManualOrderModule(deps = {}) {
    const {
      state = {},
      byId = () => null,
      getQueueScanLoading = () => false,
      getSelectedQueuePriorityRows = () => [],
      isCurrentQueuePriorityCommand = () => false,
      isQueuePriorityCommandInFlight = () => false,
      queuePriorityNormalizedLevel = () => "",
      queuePriorityRowPath = () => "",
      queueRowKey = () => "",
      renderQueueRows = () => {},
      sendQueuePriorityBulk = () => {},
      setText = () => {},
      updateQueuePriorityControls = () => {},
    } = deps;
    function queueManualOrderStatus(message) {
      setText("queue-manual-order-status", message);
    }

    function queueManualOrderKeyOrder(rows) {
      return (Array.isArray(rows) ? rows : [])
        .map(queueRowKey)
        .filter(Boolean);
    }

    function resetQueueManualOrderLoadedKeys(rows = state.rows) {
      state.loadedKeys = queueManualOrderKeyOrder(rows);
      state.draftDirty = false;
    }

    function queueManualOrderCurrentKeySignature() {
      return queueManualOrderKeyOrder(state.rows).join("\u001f");
    }

    function queueManualOrderLoadedKeySignature() {
      return state.loadedKeys.join("\u001f");
    }

    function syncQueueManualOrderDraftDirty() {
      state.draftDirty = Boolean(
        state.loadedKeys.length
        && queueManualOrderCurrentKeySignature() !== queueManualOrderLoadedKeySignature()
      );
      return state.draftDirty;
    }

    function queueManualOrderSelectValue() {
      const select = byId("queue-strategy-select");
      return select ? String(select.value || "") : state.activeStrategy;
    }

    function queueManualOrderIsEnabled() {
      return queueManualOrderSelectValue() === "ManualOrder";
    }

    function queueManualOrderRowPhase(row) {
      const level = queuePriorityNormalizedLevel(row?.manifest_priority_level);
      const isTv = String(row?.media_type || row?.media_kind || "").trim().toLowerCase() === "tv" || Boolean(row?.is_tv);
      if (level === "hold") return "hold";
      if (level === "low") return "low";
      if (level === "high" || (Boolean(row?.is_priority) && level === "normal")) return isTv ? "priority-tv" : "priority-movie";
      return isTv ? "tv" : "movie";
    }

    function queueManualOrderPhaseLabel(phase) {
      const labels = {
        "priority-movie": "priority movies",
        "priority-tv": "priority TV",
        movie: "normal movies",
        tv: "normal TV",
        low: "low priority",
        hold: "held rows",
      };
      return labels[phase] || "this backend phase";
    }

    function queueManualOrderItemPath(row) {
      return queuePriorityRowPath(row);
    }

    function queueManualOrderPositionItems() {
      return state.rows
        .map((row, index) => {
          const path = queueManualOrderItemPath(row);
          if (!path) return null;
          return {
            path,
            level: queuePriorityNormalizedLevel(row?.manifest_priority_level),
            position: index + 1,
          };
        })
        .filter(Boolean);
    }

    function queueManualOrderSelectedContext() {
      const selectedRows = getSelectedQueuePriorityRows().filter((row) => queueManualOrderItemPath(row));
      if (!selectedRows.length) {
        return { ok: false, message: "Select one or more queue rows before moving manual order." };
      }
      const phase = queueManualOrderRowPhase(selectedRows[0]);
      if (phase === "hold") {
        return { ok: false, message: "Held rows are excluded from backend processing and cannot be manually ordered." };
      }
      const eligibleRows = selectedRows.filter((row) => queueManualOrderRowPhase(row) === phase);
      const selectedKeys = new Set(eligibleRows.map(queueRowKey).filter(Boolean));
      if (!selectedKeys.size) {
        return { ok: false, message: "The selected row does not have a stable queue key for manual ordering." };
      }
      const phaseRows = state.rows.filter((row) => queueManualOrderRowPhase(row) === phase && queueManualOrderItemPath(row));
      return {
        ok: true,
        phase,
        phaseRows,
        selectedKeys,
        ignoredCount: selectedRows.length - eligibleRows.length,
      };
    }

    function queueManualOrderSameKeys(left, right) {
      if (left.length !== right.length) return false;
      return left.every((row, index) => queueRowKey(row) === queueRowKey(right[index]));
    }

    function queueManualOrderMoveRows(rows, selectedKeys, mode, targetKey = "") {
      const next = rows.slice();
      const isSelected = (row) => selectedKeys.has(queueRowKey(row));
      if (mode === "top") {
        return next.filter(isSelected).concat(next.filter((row) => !isSelected(row)));
      }
      if (mode === "bottom") {
        return next.filter((row) => !isSelected(row)).concat(next.filter(isSelected));
      }
      if (mode === "up") {
        for (let index = 1; index < next.length; index += 1) {
          if (isSelected(next[index]) && !isSelected(next[index - 1])) {
            const previous = next[index - 1];
            next[index - 1] = next[index];
            next[index] = previous;
          }
        }
        return next;
      }
      if (mode === "down") {
        for (let index = next.length - 2; index >= 0; index -= 1) {
          if (isSelected(next[index]) && !isSelected(next[index + 1])) {
            const following = next[index + 1];
            next[index + 1] = next[index];
            next[index] = following;
          }
        }
        return next;
      }
      if (mode === "drop") {
        if (!targetKey || selectedKeys.has(targetKey)) return next;
        const selectedRows = next.filter(isSelected);
        const remaining = next.filter((row) => !isSelected(row));
        const targetIndex = remaining.findIndex((row) => queueRowKey(row) === targetKey);
        if (targetIndex < 0) return next;
        remaining.splice(targetIndex, 0, ...selectedRows);
        return remaining;
      }
      return next;
    }

    function queueManualOrderApplyPhaseRows(phase, phaseRows) {
      let phaseIndex = 0;
      state.rows = state.rows.map((row) => {
        if (queueManualOrderRowPhase(row) !== phase || !queueManualOrderItemPath(row)) return row;
        const replacement = phaseRows[phaseIndex];
        phaseIndex += 1;
        return replacement || row;
      });
      refreshDisplayedQueuePriorityRows();
      syncQueueManualOrderDraftDirty();
    }

    async function saveQueueManualOrderPositions(message) {
      if (getQueueScanLoading()) {
        queueManualOrderStatus("Manual order is paused while the backend builds a fresh queue preview. Retry after the refreshed snapshot arrives.");
        return false;
      }
      if (isQueuePriorityCommandInFlight()) {
        queueManualOrderStatus("A queue priority/order command is already in progress.");
        return false;
      }
      const items = queueManualOrderPositionItems();
      if (!items.length) {
        queueManualOrderStatus("No queue rows are available to save manual order positions.");
        return false;
      }
      if (!syncQueueManualOrderDraftDirty()) {
        queueManualOrderStatus("No staged manual-order changes to save.");
        updateQueueManualOrderControls();
        return false;
      }
      const seq = beginQueuePriorityCommand();
      queueManualOrderStatus(`Saving loaded backend manual positions for ${items.length} row(s)...`);
      let finalStatusMessage = "";
      try {
        const result = await apiPost("/api/queue/priority", { items });
        const ok = Boolean(result && result.ok);
        const resultMessage = result && result.message ? result.message : message || "Manual order positions saved.";
        finalStatusMessage = ok
          ? `${message || resultMessage} ManualOrder takes effect on the next backend queue build.`
          : `Manual order save failed: ${resultMessage}`;
        if (isCurrentQueuePriorityCommand(seq)) {
          queueManualOrderStatus(finalStatusMessage);
        }
        if (typeof appendCommandResult === "function") {
          appendCommandResult({
            command: "queue.priority",
            ok,
            severity: ok ? "ok" : "error",
            message: ok ? (message || resultMessage) : resultMessage,
          });
        }
        if (ok) resetQueueManualOrderLoadedKeys(state.rows);
        return ok;
      } catch (err) {
        finalStatusMessage = `Manual order save failed: ${err}`;
        if (isCurrentQueuePriorityCommand(seq)) queueManualOrderStatus(finalStatusMessage);
        return false;
      } finally {
        endQueuePriorityCommand(seq);
        updateQueueManualOrderControls();
        if (finalStatusMessage) queueManualOrderStatus(finalStatusMessage);
      }
    }

    async function moveQueueManualOrder(mode, targetKey = "") {
      if (getQueueScanLoading()) {
        queueManualOrderStatus("Manual order is paused while the backend builds a fresh queue preview. Retry after the refreshed snapshot arrives.");
        updateQueueManualOrderControls();
        return;
      }
      if (!queueManualOrderIsEnabled()) {
        queueManualOrderStatus("Choose Manual Order in the strategy selector to enable drag/drop and arrow moves.");
        updateQueueManualOrderControls();
        return;
      }
      const context = queueManualOrderSelectedContext();
      if (!context.ok) {
        queueManualOrderStatus(context.message);
        updateQueueManualOrderControls();
        return;
      }
      const nextPhaseRows = queueManualOrderMoveRows(context.phaseRows, context.selectedKeys, mode, targetKey);
      if (queueManualOrderSameKeys(context.phaseRows, nextPhaseRows)) {
        queueManualOrderStatus(`Selected row(s) are already at that edge within ${queueManualOrderPhaseLabel(context.phase)}.`);
        updateQueueManualOrderControls();
        return;
      }
      queueManualOrderApplyPhaseRows(context.phase, nextPhaseRows);
      const ignored = context.ignoredCount > 0 ? ` ${context.ignoredCount} selected row(s) in other backend phases stayed put.` : "";
      queueManualOrderStatus(`Staged manual order for ${queueManualOrderPhaseLabel(context.phase)}.${ignored} Use Save Loaded Backend Order to write backend positions, or Discard Loaded Order Changes to restore the loaded order.`);
      renderQueueRows({ preservePage: true });
      updateQueueManualOrderControls();
    }

    async function saveCurrentQueueManualOrder() {
      if (!queueManualOrderIsEnabled()) {
        queueManualOrderStatus("Choose Manual Order in the strategy selector before saving manual positions.");
        updateQueueManualOrderControls();
        return;
      }
      await saveQueueManualOrderPositions("Saved loaded backend queue order to the backend manifest. Display filters and render caps did not define the saved scope.");
      updateQueueManualOrderControls();
    }

    function discardQueueManualOrderDraft() {
      if (!queueManualOrderIsEnabled()) {
        queueManualOrderStatus("Choose Manual Order in the strategy selector before discarding staged positions.");
        updateQueueManualOrderControls();
        return;
      }
      if (!syncQueueManualOrderDraftDirty()) {
        queueManualOrderStatus("No staged manual-order changes to discard.");
        updateQueueManualOrderControls();
        return;
      }
      restoreQueueManualOrderLoadedOrder();
      queueManualOrderStatus("Discarded staged manual-order changes. Loaded backend order restored locally; no backend request was sent.");
      renderQueueRows({ preservePage: true });
      updateQueueManualOrderControls();
    }

    function restoreQueueManualOrderLoadedOrder() {
      const currentRowsByKey = new Map(state.rows.map((row) => [queueRowKey(row), row]));
      const restored = [];
      state.loadedKeys.forEach((key) => {
        const row = currentRowsByKey.get(key);
        if (!row) return;
        restored.push(row);
        currentRowsByKey.delete(key);
      });
      state.rows = restored.concat(Array.from(currentRowsByKey.values()));
      state.draftDirty = false;
      refreshDisplayedQueuePriorityRows();
    }

    function wireQueueManualOrderRow(row, item) {
      if (!row) return;
      const key = queueRowKey(item);
      const enabled = queueManualOrderIsEnabled() && queueManualOrderRowPhase(item) !== "hold";
      row.draggable = enabled;
      row.classList.toggle("queue-manual-order-row", enabled);
      if (enabled) {
        row.dataset.manualOrderDraggable = "true";
        row.title = row.title ? `${row.title} Manual order: drag to move within this backend phase.` : "Manual order: drag to move within this backend phase.";
      } else {
        delete row.dataset.manualOrderDraggable;
      }
      row.addEventListener("keydown", (event) => {
        if (!event.altKey || (event.key !== "ArrowUp" && event.key !== "ArrowDown")) return;
        event.preventDefault();
        event.stopImmediatePropagation();
        if (key && !getSelectedQueuePriorityRowKeys().includes(key)) selectQueueRow(item);
        void moveQueueManualOrder(event.key === "ArrowUp" ? "up" : "down");
      }, true);
      row.addEventListener("dragstart", (event) => {
        if (!queueManualOrderIsEnabled() || !enabled || !key) {
          event.preventDefault();
          return;
        }
        if (!getSelectedQueuePriorityRowKeys().includes(key)) selectQueueRow(item);
        state.dragKey = key;
        row.classList.add("is-manual-dragging");
        if (event.dataTransfer) {
          event.dataTransfer.effectAllowed = "move";
          event.dataTransfer.setData("text/plain", key);
        }
      });
      row.addEventListener("dragover", (event) => {
        if (!state.dragKey || !enabled) return;
        event.preventDefault();
        row.classList.add("is-manual-drop-target");
        if (event.dataTransfer) event.dataTransfer.dropEffect = "move";
      });
      row.addEventListener("dragleave", () => {
        row.classList.remove("is-manual-drop-target");
      });
      row.addEventListener("drop", (event) => {
        if (!state.dragKey || !enabled) return;
        event.preventDefault();
        row.classList.remove("is-manual-drop-target");
        void moveQueueManualOrder("drop", key);
      });
      row.addEventListener("dragend", () => {
        state.dragKey = "";
        row.classList.remove("is-manual-dragging", "is-manual-drop-target");
      });
    }

    function updateQueueManualOrderControls() {
      syncQueueManualOrderDraftDirty();
      const enabled = queueManualOrderIsEnabled();
      const hasRows = state.rows.length > 0 && !getQueueScanLoading();
      const hasSelection = getSelectedQueuePriorityRows().length > 0;
      [
        "queue-manual-save-order-btn",
        "queue-manual-discard-order-btn",
        "queue-manual-move-top-btn",
        "queue-manual-move-up-btn",
        "queue-manual-move-down-btn",
        "queue-manual-move-bottom-btn",
      ].forEach((id) => {
        const button = byId(id);
        if (!button) return;
        const needsSelection = !["queue-manual-save-order-btn", "queue-manual-discard-order-btn"].includes(id);
        const needsDraft = id === "queue-manual-save-order-btn" || id === "queue-manual-discard-order-btn";
        button.disabled = isQueuePriorityCommandInFlight() || !enabled || !hasRows || (needsSelection && !hasSelection) || (needsDraft && !state.draftDirty);
      });
      const status = byId("queue-manual-order-status");
      if (!status) return;
      const currentStatus = String(status.textContent || "");
      const preserveResultStatus = /^(Saved loaded backend queue order|Manual order save failed|Discarded staged manual-order changes)/.test(currentStatus);
      if (!enabled) {
        status.textContent = "Manual order controls are available when the strategy selector is Manual Order. Move controls stage loaded backend rows locally; Save Loaded Backend Order writes the staged positions. Display filters and render caps do not define Launch scope.";
      } else if (getQueueScanLoading()) {
        status.textContent = "Manual order is paused while the backend builds a fresh queue preview.";
      } else if (!hasRows) {
        status.textContent = "Manual order is active, but no queue rows are loaded.";
      } else if (isQueuePriorityCommandInFlight()) {
        status.textContent = "Manual order is paused while a backend queue priority/order request is in progress.";
      } else if (state.draftDirty) {
        status.textContent = "Manual order has staged local changes. Save Loaded Backend Order writes backend positions; Discard restores the loaded order. Launch scope is unchanged.";
      } else if (!hasSelection) {
        if (preserveResultStatus) return;
        status.textContent = "Manual order is active. Select a row, use arrow buttons or Alt+Up/Alt+Down, or drag within its backend phase to stage local order changes.";
      }
    }

    function initQueueManualOrderToolbar() {
      const wire = (id, handler) => {
        const btn = byId(id);
        if (btn) btn.addEventListener("click", handler);
      };
      wire("queue-manual-save-order-btn", () => saveCurrentQueueManualOrder());
      wire("queue-manual-discard-order-btn", () => discardQueueManualOrderDraft());
      wire("queue-manual-move-top-btn", () => moveQueueManualOrder("top"));
      wire("queue-manual-move-up-btn", () => moveQueueManualOrder("up"));
      wire("queue-manual-move-down-btn", () => moveQueueManualOrder("down"));
      wire("queue-manual-move-bottom-btn", () => moveQueueManualOrder("bottom"));
      wire("queue-page-prev-btn", () => moveQueueTablePage(-1));
      wire("queue-page-next-btn", () => moveQueueTablePage(1));
      const select = byId("queue-strategy-select");
      if (select) {
        select.addEventListener("change", () => {
          if (!queueManualOrderIsEnabled() && state.draftDirty) {
            restoreQueueManualOrderLoadedOrder();
            queueManualOrderStatus("Discarded staged manual-order changes because Manual Order is no longer selected. No backend request was sent.");
          }
          updateQueueManualOrderControls();
          renderQueueRows();
        });
      }
      updateQueueManualOrderControls();
    }

    return {
      queueManualOrderStatus, queueManualOrderKeyOrder, resetQueueManualOrderLoadedKeys,
      queueManualOrderCurrentKeySignature, queueManualOrderLoadedKeySignature,
      syncQueueManualOrderDraftDirty, queueManualOrderSelectValue, queueManualOrderIsEnabled,
      queueManualOrderRowPhase, queueManualOrderPhaseLabel, queueManualOrderItemPath,
      queueManualOrderPositionItems, queueManualOrderSelectedContext, queueManualOrderSameKeys,
      queueManualOrderMoveRows, queueManualOrderApplyPhaseRows, saveQueueManualOrderPositions,
      moveQueueManualOrder, saveCurrentQueueManualOrder, discardQueueManualOrderDraft,
      restoreQueueManualOrderLoadedOrder, wireQueueManualOrderRow, updateQueueManualOrderControls,
      initQueueManualOrderToolbar,
    };
  }

  window.__queueManualOrderModule = { createQueueManualOrderModule };
})();
