(function () {
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

    function completedProofRows(payload) {
      return Array.isArray(payload?.rows) ? payload.rows : [];
    }

    function completedProofDrainSummaryPayload(pending) {
      const summary = pending?.drain_summary;
      return summary && typeof summary === "object" ? summary : {};
    }

    function completedProofDrainSummaryItems(pending) {
      const summary = completedProofDrainSummaryPayload(pending || {});
      return Array.isArray(summary.items) ? summary.items : [];
    }

    function completedProofNormalizePath(value) {
      const s = String(value || "").trim().replace(/\//g, "\\");
      const unc = s.startsWith("\\\\") ? "\\\\" : "";
      return (unc + s.slice(unc.length).replace(/\\+/g, "\\")).toLowerCase();
    }

    function completedProofPathLooksAbsolute(value) {
      const text = String(value || "").trim();
      return Boolean(text && (/^[a-zA-Z]:[\\/]/.test(text) || /^\\\\/.test(text) || text.includes("\\") || text.includes("/")));
    }

    function completedProofLeaf(value) {
      const text = String(value || "").trim();
      if (!text) return "";
      const parts = text.split(/[\\/]/).filter(Boolean);
      return parts.length ? parts[parts.length - 1] : text;
    }

    function completedProofFirstValue(item, keys) {
      for (const key of keys) {
        const value = item?.[key];
        if (value !== undefined && value !== null && String(value).trim()) return String(value).trim();
      }
      return "";
    }

    function completedProofCompletedOutputPath(row) {
      return completedProofFirstValue(row, ["output_path", "server_out", "destination_path", "final_path", "output_file"]);
    }

    function completedProofCompletedSourcePath(row) {
      return completedProofFirstValue(row, ["source_path", "input_path", "source_file"]);
    }

    function completedProofRowMissingOutput(row) {
      const outputHealth = String(row?.output_health || row?.output_status || row?.operator_status || "").toLowerCase();
      return Boolean(
        row?.output_exists === false
        || row?.missing_output === true
        || ["missing", "missing output", "not_found", "not found", "deleted", "unavailable"].some((token) => outputHealth.includes(token))
      );
    }

    function completedProofPendingDestinationPath(row) {
      return completedProofFirstValue(row, ["server_out", "destination_path", "output_path"]);
    }

    function completedProofPendingSourcePath(row) {
      return completedProofFirstValue(row, ["source_path", "input_path", "source_file"]);
    }

    function completedProofPendingLocalPath(row) {
      return completedProofFirstValue(row, ["local_file", "payload_path", "scratch_path", "manifest_path"]);
    }

    function completedProofRowKey(row, fallback = "") {
      return String(row?.row_key || row?.source_path || row?.output_path || row?.output_file || fallback || "").trim();
    }

    function completedProofRowLabel(row) {
      return completedProofFirstValue(row, ["lookup_title", "output_file", "title", "route_label"])
        || completedProofLeaf(completedProofCompletedOutputPath(row))
        || completedProofLeaf(completedProofCompletedSourcePath(row))
        || "(completed row)";
    }

    function completedProofPendingLabel(row) {
      return completedProofFirstValue(row, ["lookup_title", "output_file", "title", "state"])
        || completedProofLeaf(completedProofPendingDestinationPath(row))
        || completedProofLeaf(completedProofPendingLocalPath(row))
        || completedProofLeaf(completedProofPendingSourcePath(row))
        || "(pending row)";
    }

    function completedProofDrainItemLabel(item) {
      return completedProofFirstValue(item, ["lookup_title", "output_file", "title", "status"])
        || completedProofLeaf(completedProofPendingDestinationPath(item))
        || completedProofLeaf(completedProofPendingLocalPath(item))
        || completedProofLeaf(completedProofPendingSourcePath(item))
        || "(drain item)";
    }

    function completedPendingProofSignalLabel(signal) {
      const labels = {
        "pending-destination-overlap": "Pending destination overlap",
        "completed-source-still-pending": "Completed source still pending",
        "drain-summary-output-proof": "Drain output proof",
        "drain-summary-source-proof": "Drain source proof",
        "same-leaf-review": "Same leaf review",
        "completed-missing-output-still-pending": "Missing output still parked",
        "completed-missing-output-with-drain-proof": "Missing output with drain proof",
        "completed-missing-output-no-pending-proof": "Missing output without pending proof",
      };
      return labels[signal] || signal || "Review";
    }

    function completedPendingProofIsExactPathSignal(signal) {
      return [
        "pending-destination-overlap",
        "completed-source-still-pending",
        "drain-summary-output-proof",
        "drain-summary-source-proof",
        "completed-missing-output-still-pending",
        "completed-missing-output-with-drain-proof",
      ].includes(String(signal || ""));
    }

    function completedPendingProofIsFinalPlacementReviewSignal(signal) {
      return [
        "completed-missing-output-still-pending",
        "completed-missing-output-with-drain-proof",
      ].includes(String(signal || ""));
    }

    function completedPendingProofDataStatus(value, options = {}) {
      const status = String(value?.status || value?.state || value?.diagnostic_status || value?.result || "").toLowerCase();
      const severity = String(value?.diagnostic_severity || value?.operator_severity || value?.severity || "").toLowerCase();
      const recommendation = String(value?.drain_recommendation || value?.operator_guidance || value?.issue_summary || "").toLowerCase();
      if (value?.do_not_drain || value?.read_error || value?.error || severity === "error") return "blocked";
      if (["error", "failed", "failure", "stopped"].some((token) => status.includes(token))) return "blocked";
      if (status.includes("skipped") && !options.allowSkippedAsReview) return "blocked";
      if (["do not drain", "missing", "invalid", "blocked"].some((token) => recommendation.includes(token))) return "blocked";
      if (["succeeded", "success", "already_published", "already-published", "published"].some((token) => status.includes(token))) return "match";
      if (["warning", "review", "deferred", "skipped", "remaining"].some((token) => status.includes(token) || recommendation.includes(token))) return "warning";
      return options.defaultStatus || "warning";
    }

    function completedPendingProofEvidenceText(item) {
      const parts = [];
      if (item.signal === "pending-destination-overlap") {
        parts.push("Exact completed output path matches a current pending publish destination.");
      } else if (item.signal === "completed-source-still-pending") {
        parts.push("Exact completed source path also exists in current pending publish state.");
      } else if (item.signal === "drain-summary-output-proof") {
        parts.push("Exact completed output path appears in the latest durable pending drain summary.");
      } else if (item.signal === "drain-summary-source-proof") {
        parts.push("Exact completed source path appears in the latest durable pending drain summary.");
      } else if (item.signal === "same-leaf-review") {
        parts.push("Only the filename leaf matches; full paths differ or are missing.");
      } else if (item.signal === "completed-missing-output-still-pending") {
        parts.push("Completed row reports a missing output, but exact Pending Publish proof still exists for this source/output.");
      } else if (item.signal === "completed-missing-output-with-drain-proof") {
        parts.push("Completed row reports a missing output, but exact durable drain-summary proof exists for this source/output.");
      } else if (item.signal === "completed-missing-output-no-pending-proof") {
        parts.push("Completed row reports a missing output and no exact pending or durable drain proof matched this row.");
      }
      if (item.match_path) parts.push(`Path: ${item.match_path}`);
      if (item.pending?.state) parts.push(`Pending state: ${item.pending.state}`);
      if (item.pending?.drain_recommendation) parts.push(`Drain recommendation: ${item.pending.drain_recommendation}`);
      if (item.drain_item?.status) parts.push(`Drain status: ${item.drain_item.status}`);
      if (item.drain_item?.error) parts.push(`Drain error: ${item.drain_item.error}`);
      return parts.join(" ");
    }

    function completedPendingProofNextAction(item) {
      if (item.signal === "same-leaf-review") {
        return "Treat as a duplicate-title/path review only; compare folders before taking action.";
      }
      if (item.signal === "completed-missing-output-still-pending") {
        return "Treat as deferred-publish or stale Completed proof; inspect Pending Publish and do not rerun, clean up, or delete until the parked payload is explained.";
      }
      if (item.signal === "completed-missing-output-with-drain-proof") {
        return "Treat as final-placement conflict; compare output folder, durable drain summary, Run Logs, and Last Stderr before rerun or cleanup.";
      }
      if (item.signal === "completed-missing-output-no-pending-proof") {
        return "Open Completed Manifest, Pending Publish, Run Logs, and Last Stderr before rerun; an empty Pending Publish page is not proof that the file published.";
      }
      if (item.status === "blocked") {
        return "Open Pending Publish and Diagnostics; do not drain or rerun until the blocker is explained.";
      }
      if (item.signal === "pending-destination-overlap" || item.signal === "completed-source-still-pending") {
        return "Compare Completed, Pending Publish, and Run Logs before retrying or deleting any output.";
      }
      if (item.status === "match") {
        return "Use as supporting publish proof; Completed and Pending evidence still remain read-only here.";
      }
      return "Review row detail and diagnostics before acting.";
    }

    function completedPendingProofRowKey(item, index = 0) {
      if (!item || typeof item !== "object") return `completed-pending-proof-${index}`;
      return [
        item.signal || "proof",
        completedProofRowKey(item.completed, item.completed_index),
        item.pending ? completedProofRowKey(item.pending, item.pending_index) : "",
        item.drain_item ? `${item.drain_index || 0}:${completedProofDrainItemLabel(item.drain_item)}` : "",
        item.match_path || "",
        index,
      ].join("|");
    }

    function completedPendingProofDto(completed, pending) {
      const candidates = [
        completed?.completed_pending_proof,
        pending?.completed_pending_proof,
        state.lastPublishReconciliationPayload?.completed_pending_proof,
      ];
      return candidates.find((candidate) => (
        candidate
        && typeof candidate === "object"
        && candidate.schema_version === "desktop_completed_pending_proof.v1"
        && Array.isArray(candidate.rows)
        && completedPendingProofDtoMatches(candidate, completed || {}, pending || {})
      )) || null;
    }

    function completedPendingProofDtoMatches(dto, completed, pending) {
      const expectedCompletedCount = Number(completed?.count || (Array.isArray(completed?.rows) ? completed.rows.length : 0) || 0);
      if (Number.isFinite(Number(dto?.completed_count)) && Number(dto.completed_count) !== expectedCompletedCount) return false;
      const pendingHasExplicitPayload = pending && typeof pending === "object" && (
        Array.isArray(pending.rows)
        || pending.count !== undefined
        || (pending.drain_summary && typeof pending.drain_summary === "object")
      );
      if (pendingHasExplicitPayload) {
        const expectedPendingCount = Number(pending?.count || (Array.isArray(pending?.rows) ? pending.rows.length : 0) || 0);
        if (Number.isFinite(Number(dto?.pending_count)) && Number(dto.pending_count) !== expectedPendingCount) return false;
        const expectedDrainItems = Array.isArray(pending?.drain_summary?.items) ? pending.drain_summary.items.length : 0;
        if (expectedDrainItems && Number.isFinite(Number(dto?.drain_item_count)) && Number(dto.drain_item_count) !== expectedDrainItems) return false;
      }
      return true;
    }

    function completedPendingProofDtoRows(dto) {
      return Array.isArray(dto?.rows) ? dto.rows.filter((row) => row && typeof row === "object") : [];
    }

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

    function publishReconciliationStatusLabel(status) {
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
        error: "Error",
        not_loaded: "Not loaded",
      };
      return labels[String(status || "not_loaded")] || String(status || "Unknown");
    }

    function publishReconciliationTableStatus(item) {
      const status = String(item?.status || "").toLowerCase();
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
      setText("publish-reconciliation-status", publishReconciliationStatusLabel(data.status));
      setText("publish-reconciliation-summary", [
        ...(Array.isArray(data.summary_lines) ? data.summary_lines : []),
        data.schema_version ? `Schema: ${data.schema_version}` : "",
        data.completed_source ? `Completed source: ${data.completed_source}` : "",
        data.pending_root ? `Pending root: ${data.pending_root}` : "",
        data.drain_summary_path ? `Drain summary: ${data.drain_summary_path}` : "",
      ].filter(Boolean).join("\n") || "No backend publish reconciliation loaded.");
      setText("publish-reconciliation-detail", publishReconciliationDetailLines(selected).join("\n"));
      const tbody = byId("publish-reconciliation-rows");
      if (!tbody) return;
      if (!rows.length) {
        clearRows(tbody, 5, "No backend reconciliation rows were returned.");
        updateTableStatusLegend("publish-reconciliation-legend", tbody, "Backend publish reconciliation rows");
        return;
      }
      tbody.replaceChildren();
      rows.slice(0, 250).forEach((item, index) => {
        const key = publishReconciliationRowKey(item, index);
        const row = document.createElement("tr");
        row.dataset.rowKey = key;
        row.dataset.status = publishReconciliationTableStatus(item);
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
      setText("publish-reconciliation-status", "Loading");
      setText("publish-reconciliation-summary", "Requesting backend-owned Completed/Pending/drain-summary reconciliation. This does not mutate files.");
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
        window.mediaPipelineCompletedView?.renderCompletedReconciliationHint?.(state.lastCompletedPayload, state.lastCompletedRows);
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        state.lastPublishReconciliationPayload = { status: "error", rows: [], summary_lines: [`Backend publish reconciliation failed: ${message}`] };
        setText("publish-reconciliation-status", "Error");
        setText("publish-reconciliation-summary", [
          `Backend publish reconciliation failed: ${message}`,
          "Safe next step: use Completed Manifest, Pending Publish, Run Logs, and Last Stderr diagnostics before acting.",
          "Mutation guardrail: failed reconciliation did not repair, rerun, drain, publish, rewrite manifests, or touch media.",
        ].join("\n"));
        clearRows(byId("publish-reconciliation-rows"), 5, "Backend reconciliation failed.");
        setText("publish-reconciliation-detail", "No backend reconciliation row selected.");
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
