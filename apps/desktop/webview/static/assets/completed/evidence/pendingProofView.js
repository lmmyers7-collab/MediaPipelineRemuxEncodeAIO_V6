(function () {
  function createCompletedPendingProofViewModule(deps = {}) {
    const {
      appendCells = function () {},
      byId = function () { return null; },
      captureCompletedEvidenceSelectionScroll = function () { return null; },
      clearRows = function () {},
      getSelectedCompletedRow = function () { return null; },
      makeRowSelectable = function () {},
      proofModel = {},
      renderCompletedDetail = function () {},
      renderCompletedFinalTrust = function () {},
      renderCompletedOutputAcceptance = function () {},
      renderCompletedPilotEvidencePacket = function () {},
      renderCompletedRealMediaProof = function () {},
      renderCompletedReviewDigest = function () {},
      renderCompletedRows = function () {},
      renderCompletedSizeEvidence = function () {},
      renderCompletedSizeReview = function () {},
      restoreCompletedEvidenceSelectionScroll = function () {},
      setText = function () {},
      state = {},
      updateTableStatusLegend = function () {},
    } = deps;
    const {
      completedPendingProofDataStatus = function () { return "warning"; },
      completedPendingProofDto = function () { return null; },
      completedPendingProofDtoRows = function () { return []; },
      completedPendingProofEvidenceText = function () { return ""; },
      completedPendingProofIsFinalPlacementReviewSignal = function () { return false; },
      completedPendingProofNextAction = function () { return "Review row detail and diagnostics before acting."; },
      completedPendingProofRowKey = function (item, index) { return `completed-pending-proof-${index}`; },
      completedPendingProofSignalLabel = function (signal) { return signal || "Review"; },
      completedProofCompletedOutputPath = function () { return ""; },
      completedProofCompletedSourcePath = function () { return ""; },
      completedProofDrainItemLabel = function () { return ""; },
      completedProofDrainSummaryItems = function () { return []; },
      completedProofDrainSummaryPayload = function () { return {}; },
      completedProofLeaf = function () { return ""; },
      completedProofNormalizePath = function () { return ""; },
      completedProofPathLooksAbsolute = function () { return false; },
      completedProofPendingDestinationPath = function () { return ""; },
      completedProofPendingLabel = function () { return ""; },
      completedProofPendingLocalPath = function () { return ""; },
      completedProofPendingSourcePath = function () { return ""; },
      completedProofRowKey = function () { return ""; },
      completedProofRowLabel = function () { return ""; },
      completedProofRowMissingOutput = function () { return false; },
      completedProofRows = function () { return []; },
    } = proofModel;
    function completedPendingProofSelectedRow(rows) {
      const list = Array.isArray(rows) ? rows : [];
      return list.find((row, index) => completedPendingProofRowKey(row, index) === state.selectedCompletedPendingProofKey)
        || list.find((row) => row.status === "blocked")
        || list.find((row) => row.status === "warning")
        || list[0]
        || null;
    }

    function completedPendingProofDetailLines(item) {
      if (!item) {
        return [
          "Completed-to-Pending output proof cross-check:",
          "Select a proof row to inspect the exact Completed, Pending Publish, or durable drain-summary evidence.",
          "Mutation guardrail: this detail panel is read-only and cannot accept, repair, rerun, drain, delete, publish, rewrite manifests, or touch media files.",
        ];
      }
      const lines = [
        "Completed-to-Pending output proof cross-check:",
        `Signal: ${completedPendingProofSignalLabel(item.signal)}`,
        `Status: ${item.status || "review"}`,
        `Evidence: ${completedPendingProofEvidenceText(item) || "no evidence text"}`,
        `Safe next step: ${completedPendingProofNextAction(item)}`,
      ];
      if (item.completed) {
        lines.push("");
        lines.push("Completed row:");
        lines.push(`Title: ${completedProofRowLabel(item.completed)}`);
        lines.push(`Row key: ${item.completed.row_key || completedProofRowKey(item.completed, item.completed_index) || "(not reported)"}`);
        lines.push(`Source: ${completedProofCompletedSourcePath(item.completed) || "unknown"}`);
        lines.push(`Output: ${completedProofCompletedOutputPath(item.completed) || "unknown"}`);
        lines.push(`Output health: ${item.completed.output_health || (item.completed.output_exists === false ? "missing output" : "not reported")}`);
        lines.push(`Route: ${item.completed.route || item.completed.route_label || "unknown"}; reason=${item.completed.route_reason_code || item.completed.route_reason || "unknown"}`);
        lines.push(`Size: ${item.completed.size_delta_label || item.completed.size_reduction_text || "unknown"}`);
      }
      if (item.pending) {
        lines.push("");
        lines.push("Pending Publish row:");
        lines.push(`State: ${item.pending.state || item.pending.diagnostic_status || "unknown"}`);
        lines.push(`Drain recommendation: ${item.pending.drain_recommendation || "not reported"}`);
        lines.push(`Local payload: ${completedProofPendingLocalPath(item.pending) || "unknown"}`);
        lines.push(`Destination: ${completedProofPendingDestinationPath(item.pending) || "unknown"}`);
        lines.push(`Source: ${completedProofPendingSourcePath(item.pending) || "unknown"}`);
        lines.push(`Issue summary: ${item.pending.issue_summary || item.pending.error || "none loaded"}`);
      }
      if (item.drain_item) {
        lines.push("");
        lines.push("Durable drain summary item:");
        lines.push(`Status: ${item.drain_item.status || item.drain_item.result || "unknown"}`);
        lines.push(`Destination: ${completedProofPendingDestinationPath(item.drain_item) || "unknown"}`);
        lines.push(`Source: ${completedProofPendingSourcePath(item.drain_item) || "unknown"}`);
        lines.push(`Local payload: ${completedProofPendingLocalPath(item.drain_item) || "unknown"}`);
        if (item.drain_item.error) lines.push(`Error: ${item.drain_item.error}`);
      }
      lines.push("");
      lines.push("Proof order: Completed Manifest row -> exact output/source path -> Pending Publish row/state -> durable drain summary -> Run Logs / Last Stderr.");
      lines.push("Boundary: same-leaf matches are duplicate-title hints only; exact normalized paths are stronger evidence.");
      lines.push("Mutation guardrail: this detail panel does not accept, repair, rerun, drain, cleanup, delete, publish, rewrite manifests, or touch media files.");
      return lines;
    }

    function renderCompletedPendingProofDetail(item) {
      setText("completed-pending-proof-detail", completedPendingProofDetailLines(item).join("\n"));
    }

    function selectCompletedPendingProofRow(item, index = 0) {
      const scrollSnapshot = captureCompletedEvidenceSelectionScroll();
      state.selectedCompletedPendingProofKey = completedPendingProofRowKey(item, index);
      if (item?.completed?.row_key) {
        state.selectedCompletedRowKey = item.completed.row_key;
      }
      renderCompletedDetail(item?.completed || getSelectedCompletedRow());
      renderCompletedRows();
      renderCompletedReviewDigest(state.lastCompletedPayload, state.lastCompletedRows);
      renderCompletedSizeReview(state.lastCompletedPayload, state.lastCompletedRows);
      renderCompletedPendingProof(state.lastCompletedPayload, state.lastCompletedRows, state.lastCompletedPendingPayload);
      renderCompletedSizeEvidence(state.lastCompletedPayload, state.lastCompletedRows, state.lastCompletedPendingProofRows);
      renderCompletedOutputAcceptance(state.lastCompletedPayload, state.lastCompletedRows, state.lastCompletedPendingProofRows);
      renderCompletedRealMediaProof(state.lastCompletedPayload, state.lastCompletedRows, state.lastCompletedPendingProofRows, state.lastCompletedPendingPayload);
      renderCompletedFinalTrust(state.lastCompletedPayload, state.lastCompletedRows, state.lastCompletedPendingProofRows, state.lastCompletedPendingPayload);
      renderCompletedPilotEvidencePacket(state.lastCompletedPayload, state.lastCompletedRows, state.lastCompletedPendingProofRows, state.lastCompletedPendingPayload);
      restoreCompletedEvidenceSelectionScroll(scrollSnapshot);
    }

    function completedPendingProofRows(completed, rows, pending) {
      const dto = completedPendingProofDto(completed || {}, pending || {});
      if (dto) return completedPendingProofDtoRows(dto);
      const completedRows = Array.isArray(rows) ? rows : completedProofRows(completed || {});
      const pendingRows = completedProofRows(pending || {});
      const drainItems = completedProofDrainSummaryItems(pending || {});
      const proofRows = [];
      const seen = new Set();
      const pendingDestinationIndex = new Map();
      const pendingSourceIndex = new Map();
      const pendingLeafIndex = new Map();
      const drainDestinationIndex = new Map();
      const drainSourceIndex = new Map();
      const drainLeafIndex = new Map();

      function addProof(item) {
        const completedKey = completedProofRowKey(item.completed, item.completed_index);
        const pendingKey = item.pending ? completedProofRowKey(item.pending, item.pending_index) : "";
        const drainKey = item.drain_item ? `${item.drain_index}:${completedProofDrainItemLabel(item.drain_item)}` : "";
        const signature = [item.signal, completedKey, pendingKey, drainKey, item.match_path || ""].join("|");
        if (seen.has(signature)) return;
        seen.add(signature);
        proofRows.push(item);
      }

      function addIndex(map, key, record) {
        if (!key) return;
        if (!map.has(key)) map.set(key, []);
        map.get(key).push(record);
      }

      pendingRows.forEach((pendingRow, pendingIndex) => {
        const pendingDestination = completedProofPendingDestinationPath(pendingRow);
        const pendingDestinationKey = completedProofNormalizePath(pendingDestination);
        const pendingDestinationIsPath = completedProofPathLooksAbsolute(pendingDestination);
        const pendingSource = completedProofPendingSourcePath(pendingRow);
        const pendingSourceKey = completedProofNormalizePath(pendingSource);
        const pendingSourceIsPath = completedProofPathLooksAbsolute(pendingSource);
        const pendingLocal = completedProofPendingLocalPath(pendingRow);
        const pendingLeaf = completedProofLeaf(pendingDestination || pendingLocal).toLowerCase();
        const record = {
          row: pendingRow,
          index: pendingIndex,
          destination: pendingDestination,
          destinationKey: pendingDestinationKey,
          destinationIsPath: pendingDestinationIsPath,
          source: pendingSource,
          sourceKey: pendingSourceKey,
          sourceIsPath: pendingSourceIsPath,
          local: pendingLocal,
        };
        if (pendingDestinationIsPath) addIndex(pendingDestinationIndex, pendingDestinationKey, record);
        if (pendingSourceIsPath) addIndex(pendingSourceIndex, pendingSourceKey, record);
        addIndex(pendingLeafIndex, pendingLeaf, record);
      });

      drainItems.forEach((drainItem, drainIndex) => {
        const drainDestination = completedProofPendingDestinationPath(drainItem);
        const drainDestinationKey = completedProofNormalizePath(drainDestination);
        const drainDestinationIsPath = completedProofPathLooksAbsolute(drainDestination);
        const drainSource = completedProofPendingSourcePath(drainItem);
        const drainSourceKey = completedProofNormalizePath(drainSource);
        const drainSourceIsPath = completedProofPathLooksAbsolute(drainSource);
        const drainLocal = completedProofPendingLocalPath(drainItem);
        const drainLeaf = completedProofLeaf(drainDestination || drainLocal).toLowerCase();
        const record = {
          item: drainItem,
          index: drainIndex,
          destination: drainDestination,
          destinationKey: drainDestinationKey,
          destinationIsPath: drainDestinationIsPath,
          source: drainSource,
          sourceKey: drainSourceKey,
          sourceIsPath: drainSourceIsPath,
          local: drainLocal,
        };
        if (drainDestinationIsPath) addIndex(drainDestinationIndex, drainDestinationKey, record);
        if (drainSourceIsPath) addIndex(drainSourceIndex, drainSourceKey, record);
        addIndex(drainLeafIndex, drainLeaf, record);
      });

      completedRows.forEach((completedRow, completedIndex) => {
        const completedOutput = completedProofCompletedOutputPath(completedRow);
        const completedOutputKey = completedProofNormalizePath(completedOutput);
        const completedOutputLeaf = completedProofLeaf(completedOutput).toLowerCase();
        const completedOutputIsPath = completedProofPathLooksAbsolute(completedOutput);
        const completedSource = completedProofCompletedSourcePath(completedRow);
        const completedSourceKey = completedProofNormalizePath(completedSource);
        const completedSourceIsPath = completedProofPathLooksAbsolute(completedSource);
        let exactProofForCompleted = false;
        const missingCompletedOutput = completedProofRowMissingOutput(completedRow);

        if (completedOutputIsPath && completedOutputKey) {
          (pendingDestinationIndex.get(completedOutputKey) || []).forEach((record) => {
            const rowStatus = completedPendingProofDataStatus(record.row, { defaultStatus: "warning" });
            exactProofForCompleted = true;
            addProof({
              signal: missingCompletedOutput ? "completed-missing-output-still-pending" : "pending-destination-overlap",
              status: missingCompletedOutput && rowStatus === "match" ? "warning" : rowStatus,
              completed: completedRow,
              completed_index: completedIndex,
              pending: record.row,
              pending_index: record.index,
              match_path: record.destination,
            });
          });
          (drainDestinationIndex.get(completedOutputKey) || []).forEach((record) => {
            const rowStatus = completedPendingProofDataStatus(record.item, { defaultStatus: "match", allowSkippedAsReview: true });
            exactProofForCompleted = true;
            addProof({
              signal: missingCompletedOutput ? "completed-missing-output-with-drain-proof" : "drain-summary-output-proof",
              status: missingCompletedOutput && rowStatus === "match" ? "warning" : rowStatus,
              completed: completedRow,
              completed_index: completedIndex,
              drain_item: record.item,
              drain_index: record.index,
              match_path: record.destination,
            });
          });
        }

        if (completedSourceIsPath && completedSourceKey) {
          (pendingSourceIndex.get(completedSourceKey) || []).forEach((record) => {
            const rowStatus = completedPendingProofDataStatus(record.row, { defaultStatus: "warning" });
            exactProofForCompleted = true;
            addProof({
              signal: missingCompletedOutput ? "completed-missing-output-still-pending" : "completed-source-still-pending",
              status: missingCompletedOutput && rowStatus === "match" ? "warning" : rowStatus,
              completed: completedRow,
              completed_index: completedIndex,
              pending: record.row,
              pending_index: record.index,
              match_path: record.source,
            });
          });
          (drainSourceIndex.get(completedSourceKey) || []).forEach((record) => {
            const rowStatus = completedPendingProofDataStatus(record.item, { defaultStatus: "match", allowSkippedAsReview: true });
            exactProofForCompleted = true;
            addProof({
              signal: missingCompletedOutput ? "completed-missing-output-with-drain-proof" : "drain-summary-source-proof",
              status: missingCompletedOutput && rowStatus === "match" ? "warning" : rowStatus,
              completed: completedRow,
              completed_index: completedIndex,
              drain_item: record.item,
              drain_index: record.index,
              match_path: record.source,
            });
          });
        }

        if (missingCompletedOutput && !exactProofForCompleted) {
          addProof({
            signal: "completed-missing-output-no-pending-proof",
            status: "blocked",
            completed: completedRow,
            completed_index: completedIndex,
            match_path: completedOutput || completedSource,
          });
        }

        (pendingLeafIndex.get(completedOutputLeaf) || []).forEach((record) => {
          const exactDestination = Boolean(completedOutputIsPath && record.destinationIsPath && completedOutputKey === record.destinationKey);
          if (exactDestination) return;
          addProof({
            signal: "same-leaf-review",
            status: "warning",
            completed: completedRow,
            completed_index: completedIndex,
            pending: record.row,
            pending_index: record.index,
            match_path: record.destination || record.local,
          });
        });

        (drainLeafIndex.get(completedOutputLeaf) || []).forEach((record) => {
          const exactDestination = Boolean(completedOutputIsPath && record.destinationIsPath && completedOutputKey === record.destinationKey);
          if (exactDestination) return;
          addProof({
            signal: "same-leaf-review",
            status: "warning",
            completed: completedRow,
            completed_index: completedIndex,
            drain_item: record.item,
            drain_index: record.index,
            match_path: record.destination || record.local,
          });
        });
      });

      const statusWeight = { blocked: 0, warning: 1, match: 2 };
      return proofRows.sort((a, b) => (statusWeight[a.status] ?? 3) - (statusWeight[b.status] ?? 3));
    }

    function completedPendingProofStatus(completed, rows, pending) {
      const dto = completedPendingProofDto(completed || {}, pending || {});
      if (dto && dto.status) return String(dto.status);
      const rowList = Array.isArray(rows) ? rows : completedProofRows(completed || {});
      const pendingRows = completedProofRows(pending || {});
      const proofRows = completedPendingProofRows(completed || {}, rowList, pending || {});
      if ((completed || {}).error) return "Completed unavailable";
      if ((pending || {}).error) return "Pending unavailable";
      if (!rowList.length) return "No completed proof";
      if (proofRows.some((row) => row.status === "blocked")) return "Review blockers";
      if (proofRows.some((row) => completedPendingProofIsFinalPlacementReviewSignal(row.signal))) return "Review final placement";
      if (proofRows.some((row) => row.signal === "pending-destination-overlap" || row.signal === "completed-source-still-pending")) return "Review overlaps";
      if (proofRows.some((row) => row.signal === "same-leaf-review")) return "Review leaf matches";
      if (proofRows.some((row) => row.status === "match")) return pendingRows.length ? "Proof with parked rows" : "Proof aligned";
      return pendingRows.length ? "No exact overlap" : "No overlap";
    }

    function completedPendingProofSummaryLines(completed, rows, pending) {
      const dto = completedPendingProofDto(completed || {}, pending || {});
      if (dto && Array.isArray(dto.summary_lines) && dto.summary_lines.length) {
        return dto.summary_lines.filter((line) => String(line || "").trim());
      }
      const payload = completed || {};
      const pendingPayload = pending || {};
      const rowList = Array.isArray(rows) ? rows : completedProofRows(payload);
      const pendingRows = completedProofRows(pendingPayload);
      const drainSummary = completedProofDrainSummaryPayload(pendingPayload);
      const proofRows = completedPendingProofRows(payload, rowList, pendingPayload);
      const exactOutput = proofRows.filter((row) => row.signal === "pending-destination-overlap").length;
      const exactSource = proofRows.filter((row) => row.signal === "completed-source-still-pending").length;
      const drainOutput = proofRows.filter((row) => row.signal === "drain-summary-output-proof" || row.signal === "drain-summary-source-proof").length;
      const leafOnly = proofRows.filter((row) => row.signal === "same-leaf-review").length;
      const missingWithPendingProof = proofRows.filter((row) => row.signal === "completed-missing-output-still-pending").length;
      const missingWithDrainProof = proofRows.filter((row) => row.signal === "completed-missing-output-with-drain-proof").length;
      const missingWithoutProof = proofRows.filter((row) => row.signal === "completed-missing-output-no-pending-proof").length;
      const lines = [
        "Completed-to-Pending output proof cross-check:",
        `Completed rows: ${payload.count || rowList.length || 0}`,
        `Pending rows: ${pendingPayload.count || pendingRows.length || 0}`,
        `Exact completed output -> pending destination: ${exactOutput}`,
        `Exact completed source -> pending source: ${exactSource}`,
        `Completed row found in last drain summary: ${drainOutput}`,
        `Missing completed output with pending proof: ${missingWithPendingProof}`,
        `Missing completed output with drain proof: ${missingWithDrainProof}`,
        `Missing completed output without pending/drain proof: ${missingWithoutProof}`,
        `Same leaf review matches: ${leafOnly}`,
        `Last drain summary: ${drainSummary.read_error ? "unreadable" : drainSummary.exists === false ? "not found" : drainSummary.completed_at || drainSummary.started_at ? "loaded" : "not loaded"}`,
        "",
        "Proof order:",
        "1. Completed Manifest row",
        "2. Completed output/source path",
        "3. Pending Publish row/state",
        "4. Last durable pending drain summary",
        "5. Run Logs / Last Stderr from Diagnostics",
        "",
      ];
      if (payload.error) {
        lines.push(`First action: Completed history is unavailable: ${payload.error}. Open Diagnostics > Completed Manifest and Run Logs.`);
      } else if (pendingPayload.error) {
        lines.push(`First action: Pending Publish state is unavailable: ${pendingPayload.error}. Open Diagnostics > Pending Publish and Run Logs.`);
      } else if (missingWithoutProof) {
        lines.push("First action: missing completed outputs have no exact pending/drain proof. Open Completed Manifest, Pending Publish, Run Logs, and Last Stderr before rerun; empty Pending Publish is not proof of publish.");
      } else if (missingWithPendingProof || missingWithDrainProof) {
        lines.push("First action: missing completed outputs have exact pending/drain proof. Treat this as a final-placement conflict; compare output folder, Pending Publish, durable drain summary, Run Logs, and Last Stderr before rerun or cleanup.");
      } else if (proofRows.some((row) => row.status === "blocked")) {
        lines.push("First action: inspect blocked overlap rows before retrying drain, rerun, cleanup, or output deletion.");
      } else if (exactOutput || exactSource) {
        lines.push("First action: review exact overlaps. A completed row that is still parked can mean stale state, a deferred publish, or a failed drain.");
      } else if (leafOnly) {
        lines.push("First action: review same-leaf rows as duplicate-title hints only; full paths do not prove the same file.");
      } else if (drainOutput) {
        lines.push("First action: use drain-summary matches as supporting publish evidence, then confirm with output folder and run logs if a title is missing.");
      } else if (pendingRows.length) {
        lines.push("First action: no exact completed-to-pending overlap was found. Continue review from Pending Publish readiness and drain evidence.");
      } else {
        lines.push("First action: no completed-to-pending overlap is visible in the loaded payloads.");
      }
      lines.push("Mutation guardrail: this cross-check is read-only; repair, reconciliation, rerun, drain, cleanup, and deletion remain backend-owned.");
      return lines;
    }

    function renderCompletedPendingProof(completed, rows, pending) {
      const payload = completed || {};
      const rowList = Array.isArray(rows) ? rows : completedProofRows(payload);
      state.lastCompletedPendingPayload = pending && typeof pending === "object" ? pending : {};
      const proofRows = completedPendingProofRows(payload, rowList, state.lastCompletedPendingPayload);
      state.lastCompletedPendingProofRows = proofRows;
      if (state.selectedCompletedPendingProofKey && !proofRows.some((row, index) => completedPendingProofRowKey(row, index) === state.selectedCompletedPendingProofKey)) {
        state.selectedCompletedPendingProofKey = "";
      }
      const selectedProofRow = completedPendingProofSelectedRow(proofRows);
      if (!state.selectedCompletedPendingProofKey && selectedProofRow) {
        const selectedIndex = proofRows.indexOf(selectedProofRow);
        state.selectedCompletedPendingProofKey = completedPendingProofRowKey(selectedProofRow, selectedIndex < 0 ? 0 : selectedIndex);
      }
      setText("completed-pending-proof-status", completedPendingProofStatus(payload, rowList, state.lastCompletedPendingPayload));
      setText("completed-pending-proof-summary", completedPendingProofSummaryLines(payload, rowList, state.lastCompletedPendingPayload).join("\n"));
      renderCompletedPendingProofDetail(selectedProofRow);
      const tbody = byId("completed-pending-proof-rows");
      if (!tbody) return;
      if (!proofRows.length) {
        clearRows(tbody, 5, rowList.length ? "No completed-to-pending proof overlaps in the loaded payloads." : "No completed rows loaded.");
        updateTableStatusLegend("completed-pending-proof-legend", tbody, "Completed-to-pending proof rows");
        renderCompletedPendingProofDetail(null);
        return;
      }
      tbody.replaceChildren();
      proofRows.slice(0, 250).forEach((item, index) => {
        const row = document.createElement("tr");
        const key = completedPendingProofRowKey(item, index);
        row.dataset.rowKey = key;
        row.dataset.status = item.status || "warning";
        appendCells(row, [
          completedPendingProofSignalLabel(item.signal),
          completedProofRowLabel(item.completed),
          item.pending ? completedProofPendingLabel(item.pending) : completedProofDrainItemLabel(item.drain_item),
          completedPendingProofEvidenceText(item),
          completedPendingProofNextAction(item),
        ]);
        makeRowSelectable(row, () => selectCompletedPendingProofRow(item, index), {
          selected: Boolean(key && key === state.selectedCompletedPendingProofKey),
          label: `Review completed pending proof row ${completedProofRowLabel(item.completed)}`,
        });
        tbody.appendChild(row);
      });
      updateTableStatusLegend("completed-pending-proof-legend", tbody, "Completed-to-pending proof rows");
    }


    return {
      completedPendingProofDetailLines,
      completedPendingProofRows,
      completedPendingProofSelectedRow,
      completedPendingProofStatus,
      completedPendingProofSummaryLines,
      renderCompletedPendingProof,
      renderCompletedPendingProofDetail,
      selectCompletedPendingProofRow,
    };
  }

  window.__completedPendingProofViewModule = { createCompletedPendingProofViewModule };
})();
