/* Pending Publish payload projection, recovery invalidation, and parked-file inventory rendering. */
(function () {
  function createPendingPublishRenderingModule(deps = {}) {
    const {
      byId, setText, clearRows, appendCells, setCellStatusChip, updateTableStatusLegend, shortenPath,
      tableScrollSnapshot, deferTableScrollRestore, pendingRowKey, getSelectedPendingRow,
      setLastPendingRows, setLastPendingPayload, setLastPendingSnapshot, setLastPendingEmptyMessage,
      getLastPendingRows, getLastPendingPayload, getSelectedPendingRowKey, setSelectedPendingRowKey,
      getLastRecoveryPlanRows, setLastRecoveryPlanRows, getLastRecoveryPlanSignature, setLastRecoveryPlanSignature,
      getSelectedRecoveryPlanKey, setSelectedRecoveryPlanKey,
      pendingEmptyStateMessage, pendingFormatCounts, renderPendingInventoryProgress,
      renderPendingPublishReadiness, renderPendingRiskBreakdown, renderPendingValidation, renderPendingWorkflow,
      renderPendingReviewBoard, renderPendingDrainEvidence, renderPendingDrainHistory, renderPendingOpenHistory,
      renderPendingRecoveryPlanHistory, renderPendingRepairManifestHistory, renderPendingDrainEvents,
      renderPendingDrainSummary, renderPendingDrainCorrelation, renderPendingPostDrainTrust,
      renderPendingDrainActionConfidence, renderPendingBackendDrainScopePreview, renderPendingDrainDecisionChecklist,
      renderPendingDrainGuard, renderPendingDetail, renderPendingRows, renderPendingRepairManifestControls,
      renderPendingRepairOrphanControls, renderPendingRecoveryPlanRows, getCommandHistory,
    } = deps;
function renderPendingPublish(pending, snapshot = {}) {
    const rows = Array.isArray(pending.rows) ? pending.rows : [];
    setLastPendingRows(rows);
    setLastPendingPayload(pending || {});
    setLastPendingSnapshot(snapshot || {});
    const selectedPendingRowKey = getSelectedPendingRowKey();
    if (selectedPendingRowKey && !rows.some((row) => pendingRowKey(row) === selectedPendingRowKey)) {
      setSelectedPendingRowKey("");
    }
    clearStalePendingRecoveryPlan(pending || {}, rows);
    setLastPendingEmptyMessage(pendingEmptyStateMessage(pending, rows));
    setText("pending-count", String(pending.count || 0));
    setText("pending-payload-count", String(pending.payload_count || 0));
    setText("pending-size", pending.total_size_text || "0 B");
    setText("pending-health-count", String(pending.health_count || 0));
    const freshnessLines = window.mediaPipelineDom?.payloadFreshnessLines
      ? window.mediaPipelineDom.payloadFreshnessLines({
        payload: pending,
        label: "Pending Publish",
        rowCount: pending.count || rows.length || 0,
        sourceLine: pending.pending_root ? `Pending root: ${pending.pending_root}` : "",
        artifactLine: pending.exists ? "Pending scan: backend returned current parked-output inventory." : "Pending scan: pending root does not exist.",
        readError: pending.error || "",
        refreshAction: "Use Refresh Pending or topbar Refresh. This re-reads parked-output evidence only and does not publish, repair, delete, or move files.",
      })
      : [];
    const summary = [
      ...freshnessLines,
      freshnessLines.length ? "" : (pending.pending_root ? `Pending root: ${pending.pending_root}` : ""),
      freshnessLines.length ? "" : (pending.exists ? "" : "Pending root does not exist."),
      `Manifests: ${pending.count || rows.length || 0}`,
      `Payloads: ${pending.payload_count || 0}`,
      `Health rows: ${pending.health_count || 0}`,
      `Ready/review: ${pending.ready_count || 0} / ${pending.issue_count || 0}`,
      pending.operator_trust_state_counts ? `Backend trust states: ${pendingFormatCounts(pending.operator_trust_state_counts)}` : "",
      pending.available_open_target_counts ? `Backend open targets: ${pendingFormatCounts(pending.available_open_target_counts)}` : "",
      pending.missing_local_count ? `${pending.missing_local_count} payload reference(s) missing.` : "",
      ...(pending.warnings || []),
      !rows.length ? pendingEmptyStateMessage(pending, rows) : "",
    ].filter(Boolean);
    setText("pending-summary", summary.join("\n") || pending.error || "No pending publish health issues.");
    renderPendingDrainProgress(snapshot || {});
    renderPendingInventoryProgress(pending);
    renderPendingFileInventory(pending);
    renderPendingPublishReadiness(pending, rows);
    renderPendingRiskBreakdown(pending, rows);
    renderPendingValidation(pending, rows);
    renderPendingWorkflow(pending, rows);
    renderPendingReviewBoard(pending, rows);
    renderPendingDrainEvidence(pending, rows);
    if (typeof getCommandHistory === "function") renderPendingDrainHistory(getCommandHistory());
    if (typeof getCommandHistory === "function") renderPendingOpenHistory(getCommandHistory());
    if (typeof getCommandHistory === "function") renderPendingRecoveryPlanHistory(getCommandHistory());
    if (typeof getCommandHistory === "function") renderPendingRepairManifestHistory(getCommandHistory());
    renderPendingDrainEvents(snapshot || {});
    renderPendingDrainSummary(pending || {});
    renderPendingDrainCorrelation(pending || {}, rows, snapshot || {}, typeof getCommandHistory === "function" ? getCommandHistory() : []);
    renderPendingPostDrainTrust(pending || {}, rows, snapshot || {}, typeof getCommandHistory === "function" ? getCommandHistory() : []);
    renderPendingDrainActionConfidence(pending || {}, rows, snapshot || {}, typeof getCommandHistory === "function" ? getCommandHistory() : []);
    renderPendingBackendDrainScopePreview(pending || {}, rows, snapshot || {}, typeof getCommandHistory === "function" ? getCommandHistory() : []);
    renderPendingDrainDecisionChecklist(pending || {}, rows, snapshot || {}, typeof getCommandHistory === "function" ? getCommandHistory() : []);
    renderPendingDrainGuard(pending || {}, rows, snapshot || {}, typeof getCommandHistory === "function" ? getCommandHistory() : []);
    renderPendingDetail(getSelectedPendingRow());
    renderPendingRows();
    renderPendingRepairManifestControls();
    renderPendingRepairOrphanControls();
    const completedView = window.mediaPipelineCompletedView || {};
    if (
      typeof completedView.renderCompletedPendingProof === "function"
      && typeof completedView.getLastCompletedPayload === "function"
      && typeof completedView.getLastCompletedRows === "function"
    ) {
      const completedPayload = completedView.getLastCompletedPayload();
      const completedRows = completedView.getLastCompletedRows();
      completedView.renderCompletedPendingProof(completedPayload, completedRows, getLastPendingPayload());
      if (typeof completedView.renderCompletedRealMediaProof === "function" && typeof completedView.getLastCompletedPendingProofRows === "function") {
        const completedPendingProofRows = completedView.getLastCompletedPendingProofRows();
        completedView.renderCompletedRealMediaProof(
          completedPayload,
          completedRows,
          completedPendingProofRows,
          getLastPendingPayload(),
        );
        if (typeof completedView.renderCompletedPilotEvidencePacket === "function") {
          completedView.renderCompletedPilotEvidencePacket(
            completedPayload,
            completedRows,
            completedPendingProofRows,
            getLastPendingPayload(),
          );
        }
      }
    }
  }

  function renderPendingDrainProgress(snapshot = {}) {
    const bars = Array.isArray(snapshot?.progress_bars)
      ? snapshot.progress_bars.filter((bar) => ["pending_drain", "publish_copy", "publish_output"].includes(String(bar?.id || "")))
      : [];
    window.mediaPipelineProgressView?.renderProgressBarsInto?.(
      "pending-drain-progress-bars",
      bars,
      snapshot,
      "No active pending-publish drain progress loaded.",
      { compact: "pendingDrain" },
    );
  }

  function getLastPendingPublishPayload() {
    return getLastPendingPayload();
  }

  function getLastPendingPublishRows() {
    return getLastPendingRows().slice();
  }

  function pendingRecoverySignatureValue(value) {
    return String(value ?? "").replace(/[\\/]+/g, "/").trim().toLowerCase();
  }

  function pendingRecoveryPlanSignature(pending = getLastPendingPayload(), rows = getLastPendingRows()) {
    const payload = pending && typeof pending === "object" ? pending : {};
    const rowList = Array.isArray(rows) ? rows : [];
    const rowParts = rowList.map((row, index) => [
      pendingRecoverySignatureValue(pendingRowKey(row) || `row-${index}`),
      pendingRecoverySignatureValue(row?.manifest_path),
      pendingRecoverySignatureValue(row?.local_file),
      pendingRecoverySignatureValue(row?.server_out),
      pendingRecoverySignatureValue(row?.source_path),
      pendingRecoverySignatureValue(row?.state),
      pendingRecoverySignatureValue(row?.diagnostic_status),
      pendingRecoverySignatureValue(row?.diagnostic_severity),
      pendingRecoverySignatureValue(row?.drain_recommendation),
      pendingRecoverySignatureValue(row?.operator_trust_state),
    ].join("::")).sort();
    return [
      pendingRecoverySignatureValue(payload.pending_root),
      String(payload.count || rowList.length || 0),
      String(payload.ready_count || 0),
      String(payload.issue_count || 0),
      String(payload.health_count || 0),
      String(payload.missing_local_count || 0),
      rowParts.join("||"),
    ].join("|");
  }

  function clearStalePendingRecoveryPlan(pending, rows) {
    const currentSignature = pendingRecoveryPlanSignature(pending, rows);
    const hasPlanRows = Array.isArray(getLastRecoveryPlanRows()) && getLastRecoveryPlanRows().length > 0;
    const hasRecoveryState = hasPlanRows || Boolean(getLastRecoveryPlanSignature() || getSelectedRecoveryPlanKey());
    if (!hasRecoveryState || (hasPlanRows && getLastRecoveryPlanSignature() === currentSignature)) {
      return currentSignature;
    }
    setLastRecoveryPlanRows([]);
    setLastRecoveryPlanSignature("");
    setSelectedRecoveryPlanKey("");
    setText("pending-recovery-plan-status", "Recovery dry-run cleared because Pending Publish evidence changed. Build a fresh dry-run before drain review.");
    renderPendingRecoveryPlanRows([]);
    return currentSignature;
  }

  function pendingFileInventoryPayload(pending) {
    const inventory = pending?.file_inventory;
    return inventory && typeof inventory === "object" ? inventory : {};
  }

  function pendingFileInventoryRows(pending) {
    const rows = pendingFileInventoryPayload(pending).rows;
    return Array.isArray(rows) ? rows.filter(Boolean) : [];
  }

  function pendingFileInventoryStatus(pending) {
    const inventory = pendingFileInventoryPayload(pending);
    const rows = pendingFileInventoryRows(pending);
    if (inventory.error) return "Unavailable";
    if (inventory.exists === false) return "No pending root";
    if (!Number(inventory.total_count || rows.length || 0)) return "No parked files";
    if (inventory.truncated) return `${rows.length} shown / ${inventory.total_count} files`;
    if (Number(inventory.orphan_payload_count || 0) > 0) return "Review files";
    return "Inventory loaded";
  }

  function pendingFileInventorySummaryLines(pending) {
    const inventory = pendingFileInventoryPayload(pending);
    const summary = Array.isArray(inventory.summary_lines) ? inventory.summary_lines.filter(Boolean) : [];
    if (summary.length) return summary;
    if (inventory.error) {
      return [
        "Pending parked file inventory:",
        `Status: unavailable`,
        `Error: ${inventory.error}`,
        "Safe action: open Diagnostics > Pending Publish and Run Logs before drain, cleanup, rerun, or manual move.",
      ];
    }
    return [
      "Pending parked file inventory:",
      `Pending root: ${inventory.pending_root || pending?.pending_root || "not reported"}`,
      `Files scanned: ${inventory.total_count || 0}`,
      `Rows shown: ${inventory.shown_count || pendingFileInventoryRows(pending).length || 0}`,
      `Manifest files: ${inventory.manifest_count || 0}`,
      `Payload-like files: ${inventory.payload_like_count || 0}`,
      `Referenced payload files: ${inventory.referenced_payload_count || 0}`,
      `Unreferenced payload files: ${inventory.orphan_payload_count || 0}`,
      `Total size: ${inventory.total_size_text || "0 B"}`,
      "Evidence boundary: directory listing only; file bytes were not read and no files were changed.",
    ];
  }

  function pendingFileInventoryRowStatus(item) {
    const role = String(item?.role || "").toLowerCase();
    const status = String(item?.status || "").toLowerCase();
    if (role === "scan_error" || status === "error") return "failed";
    if (role === "orphan_payload" || status === "unreferenced") return "warning";
    if (role === "manifest") return "changed";
    return "match";
  }

  function renderPendingFileInventory(pending) {
    setText("pending-file-inventory-status", pendingFileInventoryStatus(pending || {}));
    setText("pending-file-inventory-summary", pendingFileInventorySummaryLines(pending || {}).join("\n"));
    const tbody = byId("pending-file-inventory-rows");
    if (!tbody) return;
    const rows = pendingFileInventoryRows(pending || {});
    const scrollSnapshot = tableScrollSnapshot(tbody);
    if (!rows.length) {
      clearRows(tbody, 6, "No parked files were reported by the backend pending directory scan.");
      updateTableStatusLegend("pending-file-inventory-legend", tbody, "Parked file inventory rows");
      deferTableScrollRestore(scrollSnapshot);
      return;
    }
    tbody.replaceChildren();
    rows.slice(0, 250).forEach((item) => {
      const row = document.createElement("tr");
      row.dataset.status = pendingFileInventoryRowStatus(item);
      const pathRaw = item.path || item.name || "";
      const pathDisplay = typeof shortenPath === "function" ? shortenPath(pathRaw, 56) : pathRaw;
      appendCells(row, [
        item.kind || "unknown",
        item.role || item.status || "unknown",
        item.size_text || "",
        item.modified_at || "",
        pathDisplay,
        item.evidence || "",
      ], [null, null, "num", null, "path-cell", null]);
      const cells = row.querySelectorAll("td");
      if (typeof setCellStatusChip === "function") setCellStatusChip(cells[0], item.kind || "unknown", row.dataset.status);
      if (cells[4] && pathRaw) cells[4].title = pathRaw;
      tbody.appendChild(row);
    });
    updateTableStatusLegend("pending-file-inventory-legend", tbody, "Parked file inventory rows");
    deferTableScrollRestore(scrollSnapshot);
  }
    return {
      renderPendingPublish,
      renderPendingDrainProgress,
      getLastPendingPublishPayload,
      getLastPendingPublishRows,
      pendingRecoverySignatureValue,
      pendingRecoveryPlanSignature,
      clearStalePendingRecoveryPlan,
      pendingFileInventoryPayload,
      pendingFileInventoryRows,
      pendingFileInventoryStatus,
      pendingFileInventorySummaryLines,
      pendingFileInventoryRowStatus,
      renderPendingFileInventory,
    };
  }
  window.__pendingPublishRenderingModule = { createPendingPublishRenderingModule };
})();
