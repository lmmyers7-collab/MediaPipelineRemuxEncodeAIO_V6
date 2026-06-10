// completed/evidence/acceptance.js
// Split child of completedView.evidence.js. Builds read-only output acceptance readiness evidence.

/* eslint-disable complexity, max-lines-per-function */
(function () {
  "use strict";

  function createCompletedEvidenceAcceptanceModule(deps = {}) {
    const commandHistorySuggestedAction = deps.commandHistorySuggestedAction;
    const completedAcceptanceCommandEntries = deps.completedAcceptanceCommandEntries;
    const completedAcceptanceIssueLevel = deps.completedAcceptanceIssueLevel;
    const completedCurrentFilterScope = deps.completedCurrentFilterScope;
    const completedFilterScopeAction = deps.completedFilterScopeAction;
    const completedFilterScopeDetailLines = deps.completedFilterScopeDetailLines;
    const completedFilterScopeEvidence = deps.completedFilterScopeEvidence;
    const completedFilterScopePosture = deps.completedFilterScopePosture;
    const completedPendingProofIsExactPathSignal = deps.completedPendingProofIsExactPathSignal;
    const completedProofCompletedOutputPath = deps.completedProofCompletedOutputPath;
    const completedProofCompletedSourcePath = deps.completedProofCompletedSourcePath;
    const completedProofNormalizePath = deps.completedProofNormalizePath;
    const completedProofRowKey = deps.completedProofRowKey;
    const completedProofRowLabel = deps.completedProofRowLabel;
    const completedProofRowMissingOutput = deps.completedProofRowMissingOutput;
    const getSelectedCompletedRow = deps.getSelectedCompletedRow;
    const renderCompletedDetail = deps.renderCompletedDetail;
    const renderCompletedFinalTrust = deps.renderCompletedFinalTrust;
    const renderCompletedOutputAcceptance = deps.renderCompletedOutputAcceptance;
    const renderCompletedPendingProof = deps.renderCompletedPendingProof;
    const renderCompletedPilotEvidencePacket = deps.renderCompletedPilotEvidencePacket;
    const renderCompletedRealMediaProof = deps.renderCompletedRealMediaProof;
    const renderCompletedReviewDigest = deps.renderCompletedReviewDigest;
    const renderCompletedRows = deps.renderCompletedRows;
    const renderCompletedSizeEvidence = deps.renderCompletedSizeEvidence;
    const renderCompletedSizeReview = deps.renderCompletedSizeReview;
    const state = deps.state || {};

    function captureCompletedAcceptanceSelectionScroll() {
      return window.mediaPipelineDom?.captureScrollablePositions?.() || null;
    }

    function restoreCompletedAcceptanceSelectionScroll(snapshot) {
      if (snapshot) window.mediaPipelineDom?.restoreScrollablePositions?.(snapshot);
    }

    function completedAcceptancePostureStatus(posture) {
      const normalized = String(posture || "").toLowerCase();
      if (normalized.includes("blocked")) return "blocked";
      if (normalized.includes("review")) return "warning";
      if (normalized.includes("read-first")) return "changed";
      if (normalized.includes("select")) return "unknown";
      return "match";
    }

    function completedAcceptanceProofRowsForItem(item, proofRows = state.lastCompletedPendingProofRows) {
      if (!item) return [];
      const itemKey = completedProofRowKey(item);
      const itemOutput = completedProofNormalizePath(completedProofCompletedOutputPath(item));
      const itemSource = completedProofNormalizePath(completedProofCompletedSourcePath(item));
      return (Array.isArray(proofRows) ? proofRows : []).filter((row) => {
        const completed = row?.completed || {};
        const completedKey = completedProofRowKey(completed);
        const completedOutput = completedProofNormalizePath(completedProofCompletedOutputPath(completed));
        const completedSource = completedProofNormalizePath(completedProofCompletedSourcePath(completed));
        return (
          (itemKey && completedKey && itemKey === completedKey) ||
          (itemOutput && completedOutput && itemOutput === completedOutput) ||
          (itemSource && completedSource && itemSource === completedSource)
        );
      });
    }

    function completedAcceptanceSelectedOrFirst(rows) {
      const selected = getSelectedCompletedRow();
      if (selected) return selected;
      const rowList = Array.isArray(rows) ? rows : [];
      return rowList.find((row) => row?.size_growth_over_5 || completedProofRowMissingOutput(row)) || rowList[0] || null;
    }

    function completedAcceptanceRows(completed, rows, proofRows = state.lastCompletedPendingProofRows, commandEntries) {
      const payload = completed || {};
      const rowList = Array.isArray(rows) ? rows : [];
      const item = completedAcceptanceSelectedOrFirst(rowList);
      const relevantProofRows = completedAcceptanceProofRowsForItem(item, proofRows);
      const blockedProofRows = relevantProofRows.filter((row) => row?.status === "blocked");
      const exactProofRows = relevantProofRows.filter((row) => completedPendingProofIsExactPathSignal(row?.signal));
      const sameLeafRows = relevantProofRows.filter((row) => row?.signal === "same-leaf-review");
      const commands = completedAcceptanceCommandEntries(commandEntries);
      const commandIssues = commands.filter((entry) => !["ok", "info", "none"].includes(completedAcceptanceIssueLevel(entry)));
      const latestCommand = commands[0] || null;
      const latestIssue = completedAcceptanceIssueLevel(latestCommand);
      const missingOutput = completedProofRowMissingOutput(item);
      const consistencyIssues = Array.isArray(item?.consistency_issues) ? item.consistency_issues.filter(Boolean) : [];
      const sidecarIssue = item?.sidecar_exists === false || consistencyIssues.length || item?.expected_sidecar_path && item?.sidecar_path && item.expected_sidecar_path !== item.sidecar_path;
      const growthReview = item?.size_growth_over_5 || item?.size_delta_percent === null || item?.size_delta_percent === undefined;
      const runtimeStatus = String(item?.runtime_outcome_status || "").toLowerCase();
      const runtimeFreshness = String(item?.runtime_outcome_freshness_status || "").toLowerCase();
      const runtimeReview = runtimeStatus.includes("fail") || runtimeStatus.includes("error") || runtimeFreshness === "fresh";
      const filterScope = completedCurrentFilterScope(rowList);

      if (!rowList.length) {
        return [
          {
            key: "no-completed-output",
            checkpoint: "Completed output",
            posture: payload.error ? "Blocked review" : "Select history",
            evidence: payload.error ? `Completed history unavailable: ${payload.error}` : "No completed rows are loaded.",
            action: "Open Diagnostics > Completed Manifest and Run Logs before accepting, deleting, rerunning, or reprocessing any output.",
            detail: [
              "Output acceptance readiness:",
              "No completed row can be accepted from this WebView state.",
              "Mutation guardrail: this checklist does not accept, delete, rerun, reprocess, move, drain, or write files.",
            ],
          },
        ];
      }

      return [
        {
          key: "display-filter-scope",
          checkpoint: "Display filter / backend action scope",
          posture: completedFilterScopePosture(filterScope),
          evidence: completedFilterScopeEvidence(filterScope),
          action: completedFilterScopeAction(filterScope),
          completedRow: item,
          detail: completedFilterScopeDetailLines(filterScope),
        },
        {
          key: "selected-output-proof",
          checkpoint: "Selected output proof",
          posture: missingOutput || sidecarIssue ? "Blocked review" : "Read-only",
          evidence: item
            ? `${completedProofRowLabel(item)}; output ${missingOutput ? "missing" : item.output_health || "present/unknown"}; sidecar ${item.sidecar_exists === false ? "missing" : sidecarIssue ? "review" : "ok/unknown"}.`
            : "No completed row selected.",
          action: missingOutput || sidecarIssue
            ? "Read Completed Manifest, output folder, sidecar, Run Logs, and Last Stderr before rerun/delete/reprocess."
            : "Use row detail and diagnostics as supporting evidence before accepting output.",
          completedRow: item,
          detail: [
            "Output acceptance readiness:",
            `Selected row: ${item ? completedProofRowLabel(item) : "none"}`,
            `Output path: ${completedProofCompletedOutputPath(item) || "unknown"}`,
            `Source path: ${completedProofCompletedSourcePath(item) || "unknown"}`,
            `Consistency issues: ${consistencyIssues.join(", ") || "none loaded"}`,
          ],
        },
        {
          key: "size-route-proof",
          checkpoint: "Size and route proof",
          posture: growthReview ? "Review" : "Read-only",
          evidence: item
            ? `Size ${item.size_delta_label || "unknown"}; route ${item.route_decision_summary || item.route_label || item.route || "unknown"}; encoder ${item.encoder || item.encoder_kind || "unknown"}.`
            : "No completed row selected.",
          action: growthReview
            ? "Compare route evidence, encoder/GPU choice, audio/subtitle decisions, Run Logs, and settings policy before accepting growth."
            : "Confirm route evidence matches the intended Plex profile before treating output as accepted.",
          completedRow: item,
          detail: [
            "Oversized outputs can be intentional when subtitle conversion, audio normalization, or compatibility routing changed the mux/encode path.",
            "Do not use size alone as proof that an encode is wrong or right.",
          ],
        },
        {
          key: "pending-publish-proof",
          checkpoint: "Pending/publish proof",
          posture: blockedProofRows.length ? "Blocked review" : exactProofRows.length || sameLeafRows.length ? "Review" : "Read-first",
          evidence: `${relevantProofRows.length} proof row(s); ${blockedProofRows.length} blocked; ${exactProofRows.length} exact; ${sameLeafRows.length} same-leaf advisory.`,
          action: blockedProofRows.length
            ? "Resolve blocked pending proof before rerun, drain, cleanup, delete, or reprocess."
            : exactProofRows.length
              ? "Confirm whether exact pending/drain proof means parked output, stale state, or completed publish before acting."
              : "If output is missing, remember an empty Pending Publish view is not proof that publishing succeeded.",
          completedRow: item,
          detail: [
            "Proof order: completed row -> exact output/source path -> pending row/state -> durable drain summary -> run logs.",
            "Same-leaf matches are duplicate-title hints only; exact full paths are stronger proof.",
          ],
        },
        {
          key: "recent-command-evidence",
          checkpoint: "Recent command evidence",
          posture: commandIssues.length ? "Review" : latestCommand ? "Read-first" : "Read-only",
          evidence: latestCommand
            ? `${commands.length} Completed/Pending command(s); latest ${latestCommand.command || "unknown"} (${latestIssue}).`
            : "No recent Completed/Pending command history loaded.",
          action: commandIssues.length
            ? "Review command-result warnings/errors and their diagnostics handoff before trusting the visible table state."
            : "Use command history as supporting evidence; refresh Completed/Pending after backend-owned actions.",
          completedRow: item,
          detail: [
            `Completed/Pending command entries: ${commands.length}`,
            `Command entries needing review: ${commandIssues.length}`,
            latestCommand ? `Latest command suggested action: ${typeof commandHistorySuggestedAction === "function" ? commandHistorySuggestedAction(latestCommand) : "inspect command detail"}` : "Latest command suggested action: none loaded",
          ],
        },
        {
          key: "diagnostics-read-order",
          checkpoint: "Diagnostics read order",
          posture: runtimeReview ? "Review" : "Read-first",
          evidence: runtimeReview
            ? `Runtime status ${item?.runtime_outcome_status || "unknown"} (${item?.runtime_outcome_freshness_status || "unknown"}).`
            : "Completed Manifest -> Run Logs -> Last Stderr -> Latest Failure -> Pending Publish.",
          action: "Use backend allowlisted diagnostics targets before any destructive operator action outside WebView.",
          completedRow: item,
          detail: [
            "Diagnostics buttons are backend allowlisted.",
            "This checklist never accepts output on the operator's behalf; it only orders evidence.",
          ],
        },
        {
          key: "decision-boundary",
          checkpoint: "Decision boundary",
          posture: "Read-only",
          evidence: "Acceptance here means operator confidence only; WebView does not mark accepted, delete outputs, or suppress future reruns.",
          action: "Use backend-owned settings, queue, pending publish, or maintenance commands for any real action.",
          completedRow: item,
          detail: [
            "Mutation guardrail: no accept, delete, rerun, reprocess, drain, cleanup, manifest write, or policy change happens from this checklist.",
            "If any row above is blocked/review, read diagnostics before changing files outside the app.",
          ],
        },
      ];
    }

    function completedAcceptanceStatus(rows) {
      const list = Array.isArray(rows) ? rows : [];
      if (!list.length) return "No checklist";
      if (list.some((row) => completedAcceptancePostureStatus(row.posture) === "blocked")) return "Blocked review";
      if (list.some((row) => completedAcceptancePostureStatus(row.posture) === "warning")) return "Review before trusting";
      if (list.some((row) => completedAcceptancePostureStatus(row.posture) === "changed")) return "Read evidence";
      if (list.some((row) => completedAcceptancePostureStatus(row.posture) === "unknown")) return "Select row";
      return "Read-only";
    }

    function completedAcceptanceSummaryLines(rows) {
      const list = Array.isArray(rows) ? rows : [];
      const blocked = list.filter((row) => completedAcceptancePostureStatus(row.posture) === "blocked").length;
      const review = list.filter((row) => completedAcceptancePostureStatus(row.posture) === "warning").length;
      const readFirst = list.filter((row) => completedAcceptancePostureStatus(row.posture) === "changed").length;
      const unknown = list.filter((row) => completedAcceptancePostureStatus(row.posture) === "unknown").length;
      const outcome = blocked ? "Blocked review" : review ? "Review before trusting" : readFirst ? "Read evidence" : unknown ? "Select row" : list.length ? "Read-only" : "No readiness";
      const lines = [
        "Completed output acceptance readiness:",
        `Daily-use handoff: Completed evidence supports an operator trust decision; it does not mark output accepted or perform cleanup. Operator outcome: ${outcome}.`,
        `Checkpoints loaded: ${list.length}`,
        `Blocked checkpoints: ${blocked}`,
        `Review checkpoints: ${review}`,
        `Read-first checkpoints: ${readFirst}`,
        "Decision rule: readiness requires display filter scope, output/sidecar proof, route/size explanation, pending-publish proof, and recent command evidence to agree.",
        "Scope boundary: Current Output filters, Completed History filters, selected rows, proof boards, and rendered row caps never accept outputs, delete files, rerun jobs, repair manifests, or change pending-publish state.",
      ];
      if (blocked) {
        lines.push("First action: do not rerun, delete, cleanup, drain, or reprocess until blocked proof is explained.");
      } else if (review) {
        lines.push("First action: read the review rows, then compare Completed Manifest, Run Logs, Last Stderr, and Pending Publish before trusting output.");
      } else {
        lines.push("First action: use this as read-only confidence support; backend state remains authoritative.");
      }
      lines.push("Mutation guardrail: this checklist does not accept, delete, rerun, reprocess, drain, cleanup, write manifests, or change policy.");
      return lines;
    }

    function completedAcceptanceDetailLines(item) {
      if (!item) {
        return [
          "Completed output acceptance readiness:",
          "Select a completed output readiness checkpoint for detail.",
          "Mutation guardrail: no action is performed from this detail panel.",
        ];
      }
      const lines = [
        "Completed output acceptance readiness:",
        `Checkpoint: ${item.checkpoint || "unknown"}`,
        `Posture: ${item.posture || "read-only"}`,
        `Evidence: ${item.evidence || ""}`,
        `Safe next step: ${item.action || ""}`,
      ];
      (Array.isArray(item.detail) ? item.detail : []).forEach((line) => lines.push(line));
      if (item.completedRow) {
        lines.push("");
        lines.push("Associated completed row:");
        lines.push(`Title: ${completedProofRowLabel(item.completedRow)}`);
        lines.push(`Output: ${completedProofCompletedOutputPath(item.completedRow) || "unknown"}`);
        lines.push(`Source: ${completedProofCompletedSourcePath(item.completedRow) || "unknown"}`);
        lines.push(`Output growth: ${item.completedRow.size_delta_label || "unknown"}`);
        lines.push(`Safe next action: ${item.completedRow.safe_next_action || "read diagnostics before acting"}`);
      }
      lines.push("");
      lines.push("Guardrail: accepting an output is an operator judgment, not a WebView state mutation.");
      return lines;
    }

    function selectedCompletedAcceptanceRow(rows) {
      const list = Array.isArray(rows) ? rows : [];
      return list.find((row) => row.key === state.selectedCompletedAcceptanceKey) || list[0] || null;
    }

    function selectCompletedAcceptanceRow(item) {
      const scrollSnapshot = captureCompletedAcceptanceSelectionScroll();
      state.selectedCompletedAcceptanceKey = item?.key || "";
      if (item?.completedRow?.row_key) {
        state.selectedCompletedRowKey = item.completedRow.row_key;
        renderCompletedDetail(item.completedRow);
        renderCompletedRows();
        renderCompletedReviewDigest(state.lastCompletedPayload, state.lastCompletedRows);
        renderCompletedSizeReview(state.lastCompletedPayload, state.lastCompletedRows);
        renderCompletedPendingProof(state.lastCompletedPayload, state.lastCompletedRows, state.lastCompletedPendingPayload);
        renderCompletedSizeEvidence(state.lastCompletedPayload, state.lastCompletedRows, state.lastCompletedPendingProofRows);
      }
      renderCompletedOutputAcceptance(state.lastCompletedPayload, state.lastCompletedRows, state.lastCompletedPendingProofRows);
      renderCompletedRealMediaProof(state.lastCompletedPayload, state.lastCompletedRows, state.lastCompletedPendingProofRows, state.lastCompletedPendingPayload);
      renderCompletedFinalTrust(state.lastCompletedPayload, state.lastCompletedRows, state.lastCompletedPendingProofRows, state.lastCompletedPendingPayload);
      renderCompletedPilotEvidencePacket(state.lastCompletedPayload, state.lastCompletedRows, state.lastCompletedPendingProofRows, state.lastCompletedPendingPayload);
      restoreCompletedAcceptanceSelectionScroll(scrollSnapshot);
    }

    return {
      completedAcceptancePostureStatus,
      completedAcceptanceProofRowsForItem,
      completedAcceptanceSelectedOrFirst,
      completedAcceptanceRows,
      completedAcceptanceStatus,
      completedAcceptanceSummaryLines,
      completedAcceptanceDetailLines,
      selectedCompletedAcceptanceRow,
      selectCompletedAcceptanceRow,
    };
  }

  window.__completedViewEvidenceAcceptanceModule = {
    createCompletedEvidenceAcceptanceModule,
  };
})();
