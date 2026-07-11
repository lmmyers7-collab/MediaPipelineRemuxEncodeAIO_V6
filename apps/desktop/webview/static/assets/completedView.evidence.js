(function () {
  const completedPendingProofModelModule = window.__completedPendingProofModelModule || {};
  delete window.__completedPendingProofModelModule;
  if (typeof completedPendingProofModelModule.createCompletedPendingProofModel !== "function") {
    throw new Error("completed/evidence/pendingProofModel.js must load before completedView.evidence.js");
  }
  const completedPendingProofViewModule = window.__completedPendingProofViewModule || {};
  delete window.__completedPendingProofViewModule;
  if (typeof completedPendingProofViewModule.createCompletedPendingProofViewModule !== "function") {
    throw new Error("completed/evidence/pendingProofView.js must load before completedView.evidence.js");
  }

  function createCompletedEvidenceModule(deps) {
    const {
      apiGet,
      appendCells,
      byId,
      clearRows,
      commandHistoryCommandText,
      commandHistoryIssueLevel,
      commandHistoryOwnerPage,
      commandHistorySuggestedAction,
      completedEvidenceState: state,
      completedFilterFields,
      completedCurrentRows,
      completedInvestigationFilterLabel,
      completedLibraryFilterLabel,
      completedLibraryMatchesFilter,
      completedMatchesInvestigationFilter,
      completedReviewRowReasons,
      completedTableRowStatus,
      filterRows,
      filterRowsByInvestigation,
      filterRowsByStatus,
      getCommandHistory,
      getSelectedCompletedRow,
      makeRowSelectable,
      renderCompletedDetail,
      renderCompletedFinalTrust,
      renderCompletedRows,
      renderCompletedPilotEvidencePacket,
      renderCompletedRealMediaProof,
      renderCompletedReviewDigest,
      renderCompletedSizeEvidence,
      renderCompletedSizeReview,
      setText,
      tableStatusFilterLabel,
      updateTableStatusLegend,
    } = deps;

    function completedEvidenceNoop() {}

    const completedPendingProofModel = completedPendingProofModelModule.createCompletedPendingProofModel({
      getLastPublishReconciliationPayload: () => state.lastPublishReconciliationPayload || {},
    });
    const {
      completedPendingProofDetailLines,
      completedPendingProofRows,
      completedPendingProofSelectedRow,
      completedPendingProofStatus,
      completedPendingProofSummaryLines,
      renderCompletedPendingProof,
      renderCompletedPendingProofDetail,
      selectCompletedPendingProofRow,
    } = completedPendingProofViewModule.createCompletedPendingProofViewModule({
      appendCells,
      byId,
      captureCompletedEvidenceSelectionScroll,
      clearRows,
      getSelectedCompletedRow,
      makeRowSelectable,
      proofModel: completedPendingProofModel,
      renderCompletedDetail,
      renderCompletedFinalTrust,
      renderCompletedOutputAcceptance,
      renderCompletedPilotEvidencePacket,
      renderCompletedRealMediaProof,
      renderCompletedReviewDigest,
      renderCompletedRows,
      renderCompletedSizeEvidence,
      renderCompletedSizeReview,
      restoreCompletedEvidenceSelectionScroll,
      setText,
      state,
      updateTableStatusLegend,
    });
    const {
      completedPendingProofIsExactPathSignal,
      completedPendingProofIsFinalPlacementReviewSignal,
      completedPendingProofDataStatus,
      completedPendingProofEvidenceText,
      completedPendingProofNextAction,
      completedPendingProofRowKey,
      completedPendingProofSignalLabel,
      completedProofRows,
      completedProofCompletedOutputPath,
      completedProofCompletedSourcePath,
      completedProofDrainItemLabel,
      completedProofDrainSummaryItems,
      completedProofDrainSummaryPayload,
      completedProofFirstValue,
      completedProofLeaf,
      completedProofNormalizePath,
      completedProofPathLooksAbsolute,
      completedProofPendingDestinationPath,
      completedProofPendingLabel,
      completedProofPendingLocalPath,
      completedProofPendingSourcePath,
      completedProofRowKey,
      completedProofRowLabel,
      completedProofRowMissingOutput,
    } = completedPendingProofModel;

    const completedEvidenceCommandsModule = window.__completedViewEvidenceCommandsModule || {};
    delete window.__completedViewEvidenceCommandsModule;
    const completedEvidenceCommands = typeof completedEvidenceCommandsModule.createCompletedEvidenceCommandsModule === "function"
      ? completedEvidenceCommandsModule.createCompletedEvidenceCommandsModule({
        commandHistoryCommandText,
        commandHistoryIssueLevel,
        commandHistoryOwnerPage,
        getCommandHistory,
      })
      : {};
    const {
      completedAcceptanceCommandEntries = completedEvidenceNoop,
      completedAcceptanceIssueLevel = completedEvidenceNoop,
    } = completedEvidenceCommands;

    const completedEvidenceFilterScopeModule = window.__completedViewEvidenceFilterScopeModule || {};
    delete window.__completedViewEvidenceFilterScopeModule;
    const completedEvidenceFilterScope = typeof completedEvidenceFilterScopeModule.createCompletedEvidenceFilterScopeModule === "function"
      ? completedEvidenceFilterScopeModule.createCompletedEvidenceFilterScopeModule({
        byId,
        completedCurrentRows,
        completedFilterFields,
        completedInvestigationFilterLabel,
        completedLibraryFilterLabel,
        completedLibraryMatchesFilter,
        completedMatchesInvestigationFilter,
        completedReviewRowReasons,
        completedTableRowStatus,
        filterRows,
        filterRowsByInvestigation,
        filterRowsByStatus,
        state,
        tableStatusFilterLabel,
      })
      : {};
    const {
      completedCurrentFilterScope = completedEvidenceNoop,
      completedFilterScopePosture = completedEvidenceNoop,
      completedFilterScopeEvidence = completedEvidenceNoop,
      completedFilterScopeAction = completedEvidenceNoop,
      completedFilterScopeDetailLines = completedEvidenceNoop,
    } = completedEvidenceFilterScope;

    function captureCompletedEvidenceSelectionScroll() {
      return window.mediaPipelineDom?.captureScrollablePositions?.() || null;
    }

    function restoreCompletedEvidenceSelectionScroll(snapshot) {
      if (snapshot) window.mediaPipelineDom?.restoreScrollablePositions?.(snapshot);
    }

    const completedEvidenceAcceptanceModule = window.__completedViewEvidenceAcceptanceModule || {};
    delete window.__completedViewEvidenceAcceptanceModule;
    const completedEvidenceAcceptance = typeof completedEvidenceAcceptanceModule.createCompletedEvidenceAcceptanceModule === "function"
      ? completedEvidenceAcceptanceModule.createCompletedEvidenceAcceptanceModule({
        commandHistorySuggestedAction,
        completedAcceptanceCommandEntries,
        completedAcceptanceIssueLevel,
        completedCurrentFilterScope,
        completedFilterScopeAction,
        completedFilterScopeDetailLines,
        completedFilterScopeEvidence,
        completedFilterScopePosture,
        completedPendingProofIsExactPathSignal,
        completedProofCompletedOutputPath,
        completedProofCompletedSourcePath,
        completedProofNormalizePath,
        completedProofRowKey,
        completedProofRowLabel,
        completedProofRowMissingOutput,
        getSelectedCompletedRow,
        renderCompletedDetail,
        renderCompletedFinalTrust,
        renderCompletedOutputAcceptance,
        renderCompletedPendingProof,
        renderCompletedPilotEvidencePacket,
        renderCompletedRealMediaProof,
        renderCompletedReviewDigest,
        renderCompletedRows,
        renderCompletedSizeEvidence,
        renderCompletedSizeReview,
        state,
      })
      : {};
    const {
      completedAcceptancePostureStatus = completedEvidenceNoop,
      completedAcceptanceProofRowsForItem = completedEvidenceNoop,
      completedAcceptanceSelectedOrFirst = completedEvidenceNoop,
      completedAcceptanceRows = completedEvidenceNoop,
      completedAcceptanceStatus = completedEvidenceNoop,
      completedAcceptanceSummaryLines = completedEvidenceNoop,
      completedAcceptanceDetailLines = completedEvidenceNoop,
      selectedCompletedAcceptanceRow = completedEvidenceNoop,
      selectCompletedAcceptanceRow = completedEvidenceNoop,
    } = completedEvidenceAcceptance;

    function renderCompletedOutputAcceptance(completed = state.lastCompletedPayload, rows = state.lastCompletedRows, proofRows = state.lastCompletedPendingProofRows, commandEntries) {
      const payload = completed || {};
      const rowList = Array.isArray(rows) ? rows : [];
      const acceptanceRows = completedAcceptanceRows(payload, rowList, proofRows, commandEntries);
      if (state.selectedCompletedAcceptanceKey && !acceptanceRows.some((row) => row.key === state.selectedCompletedAcceptanceKey)) {
        state.selectedCompletedAcceptanceKey = "";
      }
      const selected = selectedCompletedAcceptanceRow(acceptanceRows);
      setText("completed-output-acceptance-status", completedAcceptanceStatus(acceptanceRows));
      setText("completed-output-acceptance-summary", completedAcceptanceSummaryLines(acceptanceRows).join("\n"));
      setText("completed-output-acceptance-detail", completedAcceptanceDetailLines(selected).join("\n"));
      const tbody = byId("completed-output-acceptance-rows");
      if (!tbody) return;
      if (!acceptanceRows.length) {
        clearRows(tbody, 4, "No completed output readiness rows loaded.");
        updateTableStatusLegend("completed-output-acceptance-legend", tbody, "Completed output readiness rows");
        return;
      }
      tbody.replaceChildren();
      acceptanceRows.forEach((item) => {
        const row = document.createElement("tr");
        row.dataset.status = completedAcceptancePostureStatus(item.posture);
        appendCells(row, [
          item.checkpoint || "",
          item.posture || "Read-only",
          item.evidence || "",
          item.action || "",
        ]);
        makeRowSelectable(row, () => selectCompletedAcceptanceRow(item), {
          selected: item.key === state.selectedCompletedAcceptanceKey,
          label: `Review completed output readiness checkpoint ${item.checkpoint || ""}`,
        });
        tbody.appendChild(row);
      });
      updateTableStatusLegend("completed-output-acceptance-legend", tbody, "Completed output readiness rows");
    }

    const completedEvidenceRouteAgreementModule = window.__completedViewEvidenceRouteAgreementModule || {};
    delete window.__completedViewEvidenceRouteAgreementModule;
    const completedEvidenceRouteAgreement = typeof completedEvidenceRouteAgreementModule.createCompletedEvidenceRouteAgreementModule === "function"
      ? completedEvidenceRouteAgreementModule.createCompletedEvidenceRouteAgreementModule({
        completedProofCompletedOutputPath,
        completedProofCompletedSourcePath,
        completedProofFirstValue,
        completedProofLeaf,
        completedProofNormalizePath,
        completedProofRowLabel,
        renderCompletedDetail,
        renderCompletedFinalTrust,
        renderCompletedOutputAcceptance,
        renderCompletedPendingProof,
        renderCompletedPilotEvidencePacket,
        renderCompletedRealMediaProof,
        renderCompletedReviewDigest,
        renderCompletedRouteAgreement,
        renderCompletedRows,
        renderCompletedSizeEvidence,
        renderCompletedSizeReview,
        state,
      })
      : {};
    const {
      completedRouteAgreementRouteToken = completedEvidenceNoop,
      completedRouteAgreementReason = completedEvidenceNoop,
      completedRouteAgreementQueueSourcePath = completedEvidenceNoop,
      completedRouteAgreementQueueRowLabel = completedEvidenceNoop,
      completedRouteAgreementRouteEvidenceCount = completedEvidenceNoop,
      completedRouteAgreementQueueIndexes = completedEvidenceNoop,
      completedRouteAgreementPostureStatus = completedEvidenceNoop,
      completedRouteAgreementRows = completedEvidenceNoop,
      completedRouteAgreementStatus = completedEvidenceNoop,
      completedRouteAgreementSummaryLines = completedEvidenceNoop,
      completedRouteAgreementDetailLines = completedEvidenceNoop,
      selectedCompletedRouteAgreementRow = completedEvidenceNoop,
      selectCompletedRouteAgreementRow = completedEvidenceNoop,
    } = completedEvidenceRouteAgreement;
    function renderCompletedRouteAgreement(completed = state.lastCompletedPayload, completedRows = state.lastCompletedRows, queuePayload, queueRows) {
      const rows = completedRouteAgreementRows(completed, completedRows, queuePayload, queueRows);
      state.lastCompletedRouteAgreementRows = rows;
      if (state.selectedCompletedRouteAgreementKey && !rows.some((row) => row.key === state.selectedCompletedRouteAgreementKey)) {
        state.selectedCompletedRouteAgreementKey = "";
      }
      const selected = selectedCompletedRouteAgreementRow(rows);
      setText("completed-route-agreement-status", completedRouteAgreementStatus(rows));
      const statusNode = byId("completed-route-agreement-status");
      if (statusNode) statusNode.dataset.state = completedRouteAgreementPostureStatus(selected?.posture || completedRouteAgreementStatus(rows));
      setText("completed-route-agreement-summary", completedRouteAgreementSummaryLines(rows).join("\n"));
      setText("completed-route-agreement-detail", completedRouteAgreementDetailLines(selected).join("\n"));
      const tbody = byId("completed-route-agreement-rows");
      if (!tbody) return;
      if (!rows.length) {
        clearRows(tbody, 4, "No queue/completed route agreement rows loaded.");
        updateTableStatusLegend("completed-route-agreement-legend", tbody, "Queue/completed route agreement rows");
        return;
      }
      tbody.replaceChildren();
      rows.slice(0, 120).forEach((item) => {
        const row = document.createElement("tr");
        row.dataset.status = completedRouteAgreementPostureStatus(item.posture);
        appendCells(row, [
          item.signal || "",
          item.posture || "Read-only",
          item.evidence || "",
          item.action || "",
        ]);
        makeRowSelectable(row, () => selectCompletedRouteAgreementRow(item), {
          selected: item.key === state.selectedCompletedRouteAgreementKey,
          label: `Review queue/completed agreement ${item.signal || ""}`,
        });
        tbody.appendChild(row);
      });
      updateTableStatusLegend("completed-route-agreement-legend", tbody, "Queue/completed route agreement rows");
    }

    function publishReconciliationStatusLabel(status, payload = null) {
      const labels = {
        completed_unavailable: "Completed unavailable",
        pending_unavailable: "Pending unavailable",
        no_completed_rows: "No completed rows",
        review_blockers: "Review blockers",
        review_overlaps: "Review overlaps",
        review_leaf_hints: "Review leaf hints",
        review_final_placement: "Review final placement",
        proof_aligned: "Proof aligned",
        no_overlap: "No overlap",
        loading: "Loading",
        stale: "Stale",
        error: "Error",
        not_loaded: "Not loaded",
      };
      if (payload?.stale) return "Stale";
      return labels[String(status || "not_loaded")] || String(status || "Unknown");
    }

    function publishReconciliationTableStatus(item) {
      const status = String(item?.status || "").toLowerCase();
      if (status === "stale") return "stale";
      if (status === "blocked") return "blocked";
      if (status === "warning") return "warning";
      if (status === "match") return "match";
      return "warning";
    }

    function publishReconciliationRows(payload) {
      return Array.isArray(payload?.rows) ? payload.rows : [];
    }

    function publishReconciliationRowKey(item, index = 0) {
      if (!item || typeof item !== "object") return `publish-reconciliation-${index}`;
      return [
        item.signal || "signal",
        item.completed_row_key || item.completed_output || "",
        item.pending_row_key || item.pending_destination || "",
        item.drain_index === undefined || item.drain_index === null ? "" : String(item.drain_index),
        item.match_path || "",
        index,
      ].join("|");
    }

    function publishReconciliationSelectedRow(rows) {
      const list = Array.isArray(rows) ? rows : [];
      return list.find((row, index) => publishReconciliationRowKey(row, index) === state.selectedPublishReconciliationKey)
        || list.find((row) => row.status === "blocked")
        || list.find((row) => row.status === "warning")
        || list[0]
        || null;
    }

    function publishReconciliationDetailLines(item) {
      if (!item) {
        return [
          "Backend publish reconciliation row:",
          "Select a backend reconciliation row to inspect Completed, Pending Publish, and durable drain-summary evidence.",
          "Mutation guardrail: this detail is read-only and cannot mark done, repair, rerun, drain, delete, publish, rewrite manifests, or touch media.",
        ];
      }
      const lines = [
        "Backend publish reconciliation row:",
        `Signal: ${item.signal_label || item.signal || "review"}`,
        `Status: ${item.status || "review"}`,
        `Evidence: ${item.evidence || "not reported"}`,
        `Safe next step: ${item.safe_next_action || "Review owning pages and diagnostics before acting."}`,
        "",
        "Completed row:",
        `Title: ${item.completed_title || "(completed row)"}`,
        `Row key: ${item.completed_row_key || "(not reported)"}`,
        `Output: ${item.completed_output || "unknown"}`,
        `Source: ${item.completed_source || "unknown"}`,
      ];
      if (item.pending_row_key || item.pending_destination || item.pending_local) {
        lines.push("");
        lines.push("Pending Publish row:");
        lines.push(`Title: ${item.pending_title || "(pending row)"}`);
        lines.push(`Row key: ${item.pending_row_key || "(not reported)"}`);
        lines.push(`Destination: ${item.pending_destination || "unknown"}`);
        lines.push(`Source: ${item.pending_source || "unknown"}`);
        lines.push(`Local payload: ${item.pending_local || "unknown"}`);
      }
      if (item.drain_index !== undefined && item.drain_index !== null || item.drain_status) {
        lines.push("");
        lines.push("Durable drain summary:");
        lines.push(`Item index: ${item.drain_index === undefined || item.drain_index === null ? "unknown" : item.drain_index}`);
        lines.push(`Status: ${item.drain_status || "unknown"}`);
      }
      lines.push("");
      lines.push("Proof order: Completed Manifest row -> exact output/source path -> current Pending Publish row/state -> latest durable pending drain summary -> Run Logs / Last Stderr.");
      lines.push("Boundary: same-leaf rows are duplicate-title hints only; exact normalized paths are stronger evidence.");
      lines.push("Mutation guardrail: this backend row cannot mark done, repair, rerun, drain, delete, publish, rewrite manifests, or touch media.");
      return lines;
    }

    function renderPublishReconciliation(payload) {
      const data = payload && typeof payload === "object" ? payload : {};
      const rows = publishReconciliationRows(data);
      const selected = publishReconciliationSelectedRow(rows);
      if (!state.selectedPublishReconciliationKey && selected) {
        const selectedIndex = rows.indexOf(selected);
        state.selectedPublishReconciliationKey = publishReconciliationRowKey(selected, selectedIndex < 0 ? 0 : selectedIndex);
      }
      setText("publish-reconciliation-status", publishReconciliationStatusLabel(data.status, data));
      setText("publish-reconciliation-summary", [
        data.stale ? `Stale snapshot: ${data.stale_reason || "Completed output status changed after this reconciliation was loaded."}` : "",
        ...(Array.isArray(data.summary_lines) ? data.summary_lines : []),
        data.schema_version ? `Schema: ${data.schema_version}` : "",
        data.completed_source ? `Completed source: ${data.completed_source}` : "",
        data.pending_root ? `Pending root: ${data.pending_root}` : "",
        data.drain_summary_path ? `Drain summary: ${data.drain_summary_path}` : "",
      ].filter(Boolean).join("\n") || "No backend publish reconciliation loaded.");
      setText("publish-reconciliation-detail", [
        data.stale ? "Stale backend reconciliation detail: refresh before trusting this row as current proof." : "",
        ...publishReconciliationDetailLines(selected),
      ].filter(Boolean).join("\n"));
      const tbody = byId("publish-reconciliation-rows");
      if (!tbody) return;
      if (!rows.length) {
        const status = String(data.status || "").toLowerCase();
        const message = status === "loading"
          ? "Backend reconciliation refresh is loading; previous proof rows are hidden until the new snapshot returns."
          : status === "error"
            ? "Backend reconciliation failed."
            : status === "stale"
              ? "Backend reconciliation is stale. Refresh to load current rows."
              : "No backend reconciliation rows were returned.";
        clearRows(tbody, 5, message);
        updateTableStatusLegend("publish-reconciliation-legend", tbody, "Backend publish reconciliation rows");
        return;
      }
      tbody.replaceChildren();
      rows.slice(0, 250).forEach((item, index) => {
        const key = publishReconciliationRowKey(item, index);
        const row = document.createElement("tr");
        row.dataset.rowKey = key;
        row.dataset.status = data.stale ? "stale" : publishReconciliationTableStatus(item);
        appendCells(row, [
          item.signal_label || item.signal || "Review",
          item.status || "review",
          item.completed_title || completedProofLeaf(item.completed_output) || "(completed row)",
          item.evidence || "",
          item.safe_next_action || "",
        ]);
        makeRowSelectable(row, () => selectPublishReconciliationRow(item, index), {
          selected: Boolean(key && key === state.selectedPublishReconciliationKey),
          label: `Review backend publish reconciliation ${item.signal_label || item.signal || ""}`,
        });
        tbody.appendChild(row);
      });
      updateTableStatusLegend("publish-reconciliation-legend", tbody, "Backend publish reconciliation rows");
    }

    function selectPublishReconciliationRow(item, index = 0) {
      state.selectedPublishReconciliationKey = publishReconciliationRowKey(item, index);
      renderPublishReconciliation({
        ...(state.lastPublishReconciliationPayload || {}),
        rows: publishReconciliationRows(state.lastPublishReconciliationPayload || {}),
      });
    }

    function setPublishReconciliationBusy(isBusy) {
      state.publishReconciliationInFlight = Boolean(isBusy);
      const button = byId("publish-reconciliation-refresh-button");
      if (button) button.disabled = state.publishReconciliationInFlight;
    }

    async function requestPublishReconciliation() {
      if (state.publishReconciliationInFlight) {
        setText("publish-reconciliation-status", "Already running");
        return;
      }
      setPublishReconciliationBusy(true);
      state.lastPublishReconciliationPayload = {
        status: "loading",
        rows: [],
        summary_lines: [
          "Requesting backend-owned Completed/Pending/drain-summary reconciliation. This does not mutate files.",
          "Previous reconciliation rows are hidden while the backend snapshot is in flight.",
        ],
      };
      state.selectedPublishReconciliationKey = "";
      renderPublishReconciliation(state.lastPublishReconciliationPayload);
      window.mediaPipelineCompletedView?.renderCompletedTrustDecision?.();
      window.mediaPipelineCompletedView?.renderCompletedReconciliationHint?.(state.lastCompletedPayload, state.lastCompletedRows);
      try {
        const payload = await apiGet("/api/publish-reconciliation?limit=250", { timeoutMs: 30000 });
        state.lastPublishReconciliationPayload = payload;
        state.selectedPublishReconciliationKey = "";
        renderPublishReconciliation(payload);
        renderCompletedPendingProof(state.lastCompletedPayload, state.lastCompletedRows, state.lastCompletedPendingPayload);
        renderCompletedSizeEvidence(state.lastCompletedPayload, state.lastCompletedRows, state.lastCompletedPendingProofRows);
        renderCompletedOutputAcceptance(state.lastCompletedPayload, state.lastCompletedRows, state.lastCompletedPendingProofRows);
        renderCompletedRealMediaProof(state.lastCompletedPayload, state.lastCompletedRows, state.lastCompletedPendingProofRows, state.lastCompletedPendingPayload);
        renderCompletedFinalTrust(state.lastCompletedPayload, state.lastCompletedRows, state.lastCompletedPendingProofRows, state.lastCompletedPendingPayload);
        renderCompletedPilotEvidencePacket(state.lastCompletedPayload, state.lastCompletedRows, state.lastCompletedPendingProofRows, state.lastCompletedPendingPayload);
        window.mediaPipelineCompletedView?.renderCompletedEvidenceCopyState?.();
        window.mediaPipelineCompletedView?.renderCompletedTrustDecision?.();
        window.mediaPipelineCompletedView?.renderCompletedReconciliationHint?.(state.lastCompletedPayload, state.lastCompletedRows);
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        state.lastPublishReconciliationPayload = { status: "error", rows: [], summary_lines: [
          `Backend publish reconciliation failed: ${message}`,
          "Safe next step: use Completed Manifest, Pending Publish, Run Logs, and Last Stderr diagnostics before acting.",
          "Mutation guardrail: failed reconciliation did not repair, rerun, drain, publish, rewrite manifests, or touch media.",
        ] };
        state.selectedPublishReconciliationKey = "";
        renderPublishReconciliation(state.lastPublishReconciliationPayload);
        window.mediaPipelineCompletedView?.renderCompletedTrustDecision?.();
        window.mediaPipelineCompletedView?.renderCompletedReconciliationHint?.(state.lastCompletedPayload, state.lastCompletedRows);
      } finally {
        setPublishReconciliationBusy(false);
      }
    }


    return {
      completedAcceptancePostureStatus,
      completedAcceptanceCommandEntries,
      completedAcceptanceIssueLevel,
      completedAcceptanceProofRowsForItem,
      completedAcceptanceSelectedOrFirst,
      completedCurrentFilterScope,
      completedFilterScopePosture,
      completedFilterScopeEvidence,
      completedFilterScopeAction,
      completedFilterScopeDetailLines,
      completedAcceptanceRows,
      completedAcceptanceStatus,
      completedAcceptanceSummaryLines,
      completedAcceptanceDetailLines,
      selectedCompletedAcceptanceRow,
      selectCompletedAcceptanceRow,
      renderCompletedOutputAcceptance,
      completedRouteAgreementRouteToken,
      completedRouteAgreementReason,
      completedRouteAgreementQueueSourcePath,
      completedRouteAgreementQueueRowLabel,
      completedRouteAgreementRouteEvidenceCount,
      completedRouteAgreementQueueIndexes,
      completedRouteAgreementPostureStatus,
      completedRouteAgreementRows,
      completedRouteAgreementStatus,
      completedRouteAgreementSummaryLines,
      completedRouteAgreementDetailLines,
      selectedCompletedRouteAgreementRow,
      selectCompletedRouteAgreementRow,
      renderCompletedRouteAgreement,
      completedProofRows,
      completedProofDrainSummaryPayload,
      completedProofDrainSummaryItems,
      completedProofNormalizePath,
      completedProofPathLooksAbsolute,
      completedProofLeaf,
      completedProofFirstValue,
      completedProofCompletedOutputPath,
      completedProofCompletedSourcePath,
      completedProofRowMissingOutput,
      completedProofPendingDestinationPath,
      completedProofPendingSourcePath,
      completedProofPendingLocalPath,
      completedProofRowKey,
      completedProofRowLabel,
      completedProofPendingLabel,
      completedProofDrainItemLabel,
      completedPendingProofSignalLabel,
      completedPendingProofIsExactPathSignal,
      completedPendingProofIsFinalPlacementReviewSignal,
      completedPendingProofDataStatus,
      completedPendingProofEvidenceText,
      completedPendingProofNextAction,
      completedPendingProofRowKey,
      completedPendingProofSelectedRow,
      completedPendingProofDetailLines,
      renderCompletedPendingProofDetail,
      selectCompletedPendingProofRow,
      completedPendingProofRows,
      completedPendingProofStatus,
      completedPendingProofSummaryLines,
      renderCompletedPendingProof,
      publishReconciliationStatusLabel,
      publishReconciliationTableStatus,
      publishReconciliationRows,
      publishReconciliationRowKey,
      publishReconciliationSelectedRow,
      publishReconciliationDetailLines,
      renderPublishReconciliation,
      selectPublishReconciliationRow,
      setPublishReconciliationBusy,
      requestPublishReconciliation,
    };
  }

  window.__completedViewEvidenceModule = {
    createCompletedEvidenceModule,
  };
})();
