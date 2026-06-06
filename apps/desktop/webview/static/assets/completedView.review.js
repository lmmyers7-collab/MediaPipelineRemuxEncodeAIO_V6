(function () {
  function createCompletedReviewModule(deps = {}) {
    const {
      appendCells,
      byId,
      clearRows,
      completedAcceptanceProofRowsForItem,
      completedDiagnosticsActionsForRow,
      completedFilterFields = [],
      completedFormatCounts,
      completedFreshnessLine = () => "",
      completedManifestIsAged,
      completedPendingProofIsExactPathSignal,
      completedProofCompletedOutputPath,
      completedProofCompletedSourcePath,
      completedProofRowLabel,
      completedProofRowMissingOutput,
      diagnosticsBridgeRowTrustLines,
      filterRows,
      makeRowSelectable,
      renderCompletedDetail,
      renderCompletedFinalTrust,
      renderCompletedOutputAcceptance,
      renderCompletedPendingProof,
      renderCompletedPilotEvidencePacket,
      renderCompletedRealMediaProof,
      renderCompletedRows,
      selectCompletedRow,
      setText,
      state,
      tableStatusMatchesFilter,
      tableStatusFilterLabel,
      updateTableStatusLegend,
    } = deps;

    const completedReviewNoop = function () {};
    let completedReviewRowReasons = completedReviewNoop;

    const reviewIntegrityModule = window.__completedViewReviewIntegrityModule || {};
    delete window.__completedViewReviewIntegrityModule;
    const reviewIntegrity = typeof reviewIntegrityModule.createCompletedReviewIntegrityModule === "function"
      ? reviewIntegrityModule.createCompletedReviewIntegrityModule({
        completedFreshnessLine,
        completedFormatCounts,
        completedManifestIsAged,
      })
      : {};
    const {
      completedRowHasIntegrityIssue = completedReviewNoop,
      completedIntegrityStatus = completedReviewNoop,
      completedIntegrityLines = completedReviewNoop,
    } = reviewIntegrity;

    function renderCompletedIntegrity(completed, rows) {
      const rowList = Array.isArray(rows) ? rows : [];
      setText("completed-integrity-status", completedIntegrityStatus(completed || {}, rowList));
      setText("completed-integrity", completedIntegrityLines(completed || {}, rowList).join("\n"));
    }

    function completedWorkflowStatus(completed, rows) {
      const payload = completed || {};
      const rowList = Array.isArray(rows) ? rows : [];
      const warnings = Array.isArray(payload.warnings) ? payload.warnings.filter(Boolean) : [];
      const sidecarIssues = Number(payload.missing_sidecar_count || 0) + Number(payload.output_sidecar_mismatch_count || 0) + Number(payload.stale_sidecar_count || 0);
      if (payload.error) return "Diagnostics first";
      if (!rowList.length) return "No history";
      if (Number(payload.missing_output_count || 0) > 0 || rowList.some(completedRowHasIntegrityIssue)) return "Output review";
      if (Number(payload.size_growth_over_5_count || 0) > 0) return "Size review";
      if (sidecarIssues > 0) return "Sidecar review";
      if (warnings.length || payload.runtime_outcome_warning || Number((payload.runtime_outcome_freshness_counts || {}).stale || 0) > 0 || completedManifestIsAged(payload)) return "Review context";
      return "Completed clear";
    }

    function completedWorkflowLines(completed, rows) {
      const payload = completed || {};
      const rowList = Array.isArray(rows) ? rows : [];
      const warnings = Array.isArray(payload.warnings) ? payload.warnings.filter(Boolean) : [];
      const issueRows = rowList.filter(completedRowHasIntegrityIssue);
      const sidecarIssues = Number(payload.missing_sidecar_count || 0) + Number(payload.output_sidecar_mismatch_count || 0) + Number(payload.stale_sidecar_count || 0);
      const staleHistory = Number((payload.runtime_outcome_freshness_counts || {}).stale || 0);
      const lines = [
        "Cross-page workflow: Completed",
        `Completed integrity: ${completedIntegrityStatus(payload, rowList)}`,
        `Completed validation: ${completedValidationStatus(payload, rowList)}`,
        `Rows loaded: ${payload.count || rowList.length || 0}`,
        `Missing outputs: ${payload.missing_output_count || 0}`,
        `Rows needing review: ${issueRows.length}`,
        `Rows over +5% output growth: ${payload.size_growth_over_5_count || 0}`,
        `Sidecar issues: ${sidecarIssues}`,
        `Runtime matches: ${payload.runtime_outcome_match_count || 0}`,
      ];
      lines.push("");
      if (payload.error) {
        lines.push("Next step: open Diagnostics > State Artifact Summary, Completed Manifest, Run Logs, and Last Stderr before trusting completed history.");
      } else if (!rowList.length) {
        lines.push("Next step: no completed rows are loaded. This is normal before first success; otherwise open Completed Manifest before rerun.");
      } else if (Number(payload.missing_output_count || 0) > 0 || issueRows.length) {
        lines.push("Next step: select the affected completed row, use Completed Diagnostics Cross-Links, and check Pending Publish before rerun.");
      } else if (Number(payload.size_growth_over_5_count || 0) > 0) {
        lines.push("Next step: inspect size-growth rows before using them as success proof. Check route metadata and Last Stderr for unexpected encode routing.");
      } else if (sidecarIssues > 0) {
        lines.push("Next step: inspect output/sidecar consistency from the selected row before library cleanup or rerun.");
      } else if (warnings.length || payload.runtime_outcome_warning || staleHistory > 0 || completedManifestIsAged(payload)) {
        lines.push("Next step: treat completed history as context until Diagnostics confirms the manifest and recent logs agree.");
      } else {
        lines.push("Next step: completed history is coherent. Use Queue to inspect new work or Pending Publish to verify deferred output state.");
      }
      lines.push("Owning pages: Completed for output proof, Pending Publish before rerun of deferred outputs, Queue before processing new files, Diagnostics for artifacts/logs.");
      lines.push("Mutation guardrail: this workflow panel is read-only. Repair, rerun, cleanup, and reconcile actions remain backend-owned.");
      return lines;
    }

    function renderCompletedWorkflow(completed, rows) {
      const rowList = Array.isArray(rows) ? rows : [];
      setText("completed-workflow-status", completedWorkflowStatus(completed || {}, rowList));
      setText("completed-workflow", completedWorkflowLines(completed || {}, rowList).join("\n"));
    }

    const reviewSizeReviewModule = window.__completedViewReviewSizeReviewModule || {};
    delete window.__completedViewReviewSizeReviewModule;
    const reviewSizeReview = typeof reviewSizeReviewModule.createCompletedReviewSizeReviewModule === "function"
      ? reviewSizeReviewModule.createCompletedReviewSizeReviewModule({
        completedRowHasIntegrityIssue,
        completedReviewRowReasons: (...args) => completedReviewRowReasons(...args),
      })
      : {};
    const {
      completedSizeDeltaPercent = () => Number.NaN,
      completedHasSmallHealthySizeDelta = completedReviewNoop,
      completedSizeReviewRows = () => [],
      completedSizeReviewStatus = completedReviewNoop,
      completedSizeReviewAction = completedReviewNoop,
      completedSizeReviewLines = () => [],
    } = reviewSizeReview;

    const reviewHealthSignalsModule = window.__completedViewReviewHealthSignalsModule || {};
    delete window.__completedViewReviewHealthSignalsModule;
    const reviewHealthSignals = typeof reviewHealthSignalsModule.createCompletedReviewHealthSignalsModule === "function"
      ? reviewHealthSignalsModule.createCompletedReviewHealthSignalsModule({
        completedRowHasIntegrityIssue,
        completedSizeDeltaPercent,
      })
      : {};
    const {
      completedRowHasBasicHealthyEvidence = completedReviewNoop,
      completedRowHasSmallHealthySizeGrowth = completedReviewNoop,
      completedRowLooksHealthy = completedReviewNoop,
      completedRuntimeAlreadyProcessedIsBenign = completedReviewNoop,
      completedReviewFlagIsBenign = completedReviewNoop,
      completedPrimaryConcernIsBenign = completedReviewNoop,
      completedRowHasBenignAlreadyProcessedOutcome = completedReviewNoop,
    } = reviewHealthSignals;

    const reviewRowsModule = window.__completedViewReviewRowsModule || {};
    delete window.__completedViewReviewRowsModule;
    const reviewRows = typeof reviewRowsModule.createCompletedReviewRowsModule === "function"
      ? reviewRowsModule.createCompletedReviewRowsModule({
        completedFormatCounts,
        completedManifestIsAged,
        completedWorkflowStatus,
        completedHasSmallHealthySizeDelta,
        completedPrimaryConcernIsBenign,
        completedReviewFlagIsBenign,
        completedRowHasIntegrityIssue,
        completedRowHasSmallHealthySizeGrowth,
        completedRowLooksHealthy,
        completedRowHasBenignAlreadyProcessedOutcome,
      })
      : {};
    completedReviewRowReasons = reviewRows.completedReviewRowReasons || completedReviewNoop;
    const {
      completedReviewRows = () => [],
      completedReviewStatus = completedReviewNoop,
      completedReviewBoardLines = () => [],
      completedReviewDigestStatus = completedReviewNoop,
      completedReviewDigestAction = completedReviewNoop,
      completedTableRowStatus = completedReviewNoop,
    } = reviewRows;

    const reviewInvestigationFiltersModule = window.__completedViewReviewInvestigationFiltersModule || {};
    delete window.__completedViewReviewInvestigationFiltersModule;
    const reviewInvestigationFilters = typeof reviewInvestigationFiltersModule.createCompletedReviewInvestigationFiltersModule === "function"
      ? reviewInvestigationFiltersModule.createCompletedReviewInvestigationFiltersModule({
        byId,
        completedFilterFields,
        completedSizeDeltaPercent,
        completedTableRowStatus,
        filterRows,
        tableStatusMatchesFilter,
        tableStatusFilterLabel,
      })
      : {};
    const {
      completedInvestigationFilterLabel = completedReviewNoop,
      completedMatchesInvestigationFilter = completedReviewNoop,
      completedFocusedInvestigationLabels = () => [],
      completedFilterVisibilityLines = () => [],
      completedSelectedQuickSignalLines = () => [],
      completedInvestigationSignalLines = () => [],
    } = reviewInvestigationFilters;

    function renderCompletedReviewDigest(completed, rows) {
      const tbody = byId("completed-review-rows");
      if (!tbody) return;
      const payload = completed || {};
      const rowList = Array.isArray(rows) ? rows : [];
      const reviewRows = completedReviewRows(payload, rowList).slice(0, 12);
      if (!reviewRows.length) {
        clearRows(
          tbody,
          5,
          payload.error
            ? "Completed history is unavailable. Use Diagnostics > Completed Manifest, Run Logs, and Last Stderr before rerun or cleanup."
            : rowList.length
              ? "No completed rows are flagged by the loaded backend payload. Select rows in the main table to inspect output and sidecar proof."
              : "No completed rows loaded. This is normal before the first successful job; otherwise open Completed Manifest from Diagnostics.",
        );
        updateTableStatusLegend("completed-review-legend", tbody, "Completed review rows");
        return;
      }
      tbody.replaceChildren();
      reviewRows.forEach((entry) => {
        const item = entry.row || {};
        const row = document.createElement("tr");
        row.dataset.rowKey = item.row_key || "";
        row.dataset.status = completedReviewDigestStatus(entry);
        appendCells(row, [
          item.completed_at || item.manifest_recorded_at || "",
          item.operator_trust_state || item.consistency_status || item.output_health || row.dataset.status,
          item.lookup_title || item.output_file || item.output_path || "",
          entry.reasons.slice(0, 3).join("; "),
          completedReviewDigestAction(item),
        ]);
        makeRowSelectable(row, () => selectCompletedRow(item), {
          selected: Boolean(item.row_key && item.row_key === state.selectedCompletedRowKey),
          label: `Completed review row ${item.lookup_title || item.output_file || item.output_path || ""}`,
        });
        tbody.appendChild(row);
      });
      updateTableStatusLegend("completed-review-legend", tbody, "Completed review rows");
    }

    function renderCompletedReviewBoard(completed, rows) {
      const rowList = Array.isArray(rows) ? rows : [];
      setText("completed-review-status", completedReviewStatus(completed || {}, rowList));
      setText("completed-review-board", completedReviewBoardLines(completed || {}, rowList).join("\n"));
      renderCompletedReviewDigest(completed || {}, rowList);
    }

    function renderCompletedSizeReview(completed, rows) {
      const payload = completed || {};
      const rowList = Array.isArray(rows) ? rows : [];
      const reviewRows = completedSizeReviewRows(rowList).slice(0, 20);
      setText("completed-size-review-status", completedSizeReviewStatus(payload, rowList));
      setText("completed-size-review-summary", completedSizeReviewLines(payload, rowList).join("\n"));
      const tbody = byId("completed-size-review-rows");
      if (!tbody) return;
      if (!reviewRows.length) {
        clearRows(tbody, 5, rowList.length ? "No completed rows with output growth or unknown size comparison." : "No completed rows loaded.");
        updateTableStatusLegend("completed-size-review-legend", tbody, "Completed size-growth rows");
        return;
      }
      tbody.replaceChildren();
      reviewRows.forEach(({ row: item }) => {
        const row = document.createElement("tr");
        row.dataset.status = item.size_policy_exceeded
          ? "warning"
          : item.size_growth_over_5 && !item.size_policy_available
            ? "warning"
            : completedHasSmallHealthySizeDelta(item)
              ? "match"
              : Number.isFinite(completedSizeDeltaPercent(item)) && completedSizeDeltaPercent(item) > 0
                ? "changed"
                : "unknown";
        appendCells(row, [
          item.size_delta_label || "unknown",
          item.route_decision_summary || item.route_label || item.route || "",
          item.size_policy_limit_label || item.encoder || item.encoder_kind || "",
          item.lookup_title || item.output_file || item.output_path || "",
          completedSizeReviewAction(item),
        ], ["num", null, "num", null, null]);
        makeRowSelectable(row, () => selectCompletedRow(item), {
          selected: Boolean(item.row_key && item.row_key === state.selectedCompletedRowKey),
          label: `Review completed size row ${item.lookup_title || item.output_file || item.output_path || ""}`,
        });
        tbody.appendChild(row);
      });
      updateTableStatusLegend("completed-size-review-legend", tbody, "Completed size-growth rows");
    }

    function completedSizeEvidencePostureStatus(posture) {
      const normalized = String(posture || "").toLowerCase();
      if (normalized.includes("blocked")) return "blocked";
      if (normalized.includes("review")) return "warning";
      if (normalized.includes("read-first")) return "changed";
      if (normalized.includes("observe")) return "changed";
      if (normalized.includes("empty")) return "unknown";
      return "match";
    }

    function completedSizeEvidenceRows(completed, rows, proofRows = state.lastCompletedPendingProofRows) {
      const payload = completed || {};
      const rowList = Array.isArray(rows) ? rows : [];
      const reviewRows = completedSizeReviewRows(rowList);
      const policyExceededRows = reviewRows.filter(({ row }) => row?.size_policy_exceeded).map(({ row }) => row);
      const legacyOverFiveRows = reviewRows.filter(({ row }) => row?.size_growth_over_5 && !row?.size_policy_available).map(({ row }) => row);
      const policyAllowedRows = reviewRows
        .filter(({ row }) => row?.size_policy_available && !row?.size_policy_exceeded && Number.isFinite(completedSizeDeltaPercent(row)) && completedSizeDeltaPercent(row) > 0)
        .map(({ row }) => row);
      const positiveRows = reviewRows
        .filter(({ row }) => Number.isFinite(completedSizeDeltaPercent(row)) && completedSizeDeltaPercent(row) > 0 && !row.size_policy_exceeded && !row.size_growth_over_5)
        .map(({ row }) => row);
      const neutralSmallRows = rowList.filter(completedHasSmallHealthySizeDelta);
      const unknownRows = reviewRows
        .filter(({ row }) => !Number.isFinite(completedSizeDeltaPercent(row)))
        .map(({ row }) => row);
      const proofList = Array.isArray(proofRows) ? proofRows : [];
      const proofBlocked = proofList.filter((row) => row?.status === "blocked");
      const proofExact = proofList.filter((row) => completedPendingProofIsExactPathSignal(row?.signal));
      const proofSameLeaf = proofList.filter((row) => row?.signal === "same-leaf-review");
      const topGrowthRow = policyExceededRows[0] || legacyOverFiveRows[0] || policyAllowedRows[0] || positiveRows[0] || null;
      const topGrowthLabel = topGrowthRow ? completedProofRowLabel(topGrowthRow) : "none";
      const topGrowthDelta = topGrowthRow?.size_delta_label || (typeof topGrowthRow?.size_delta_percent === "number" ? `${topGrowthRow.size_delta_percent}%` : "unknown");
      const routeSummary = topGrowthRow
        ? topGrowthRow.route_decision_summary || topGrowthRow.route_label || topGrowthRow.route || "unknown route"
        : "no growth row selected";
      const encoderSummary = topGrowthRow ? topGrowthRow.encoder || topGrowthRow.encoder_kind || "unknown encoder" : "no encoder evidence";
      const outputProofText = proofBlocked.length
        ? `${proofBlocked.length} blocked proof row(s); exact full-path proof beats same-leaf review.`
        : proofExact.length
          ? `${proofExact.length} exact pending/drain overlap row(s); exact full-path proof beats same-leaf review.`
          : proofSameLeaf.length
            ? `${proofSameLeaf.length} same-leaf duplicate-title hint(s); exact full-path proof beats same-leaf review.`
            : "No pending-publish overlap proof in the loaded payloads; exact full-path proof beats same-leaf review.";

      if (!rowList.length) {
        return [
          {
            key: "no-completed-history",
            checkpoint: "Completed manifest",
            posture: payload.error ? "Review" : "Empty",
            evidence: payload.error ? `Completed history unavailable: ${payload.error}` : "No completed rows are loaded yet.",
            action: payload.error ? "Open Diagnostics > Completed Manifest and Run Logs before trusting size history." : "Run or load completed history before using this evidence handoff.",
            detail: [
              "This board is read-only and only correlates loaded Completed and Pending Publish payloads.",
              "No output-size policy is changed from this panel.",
            ],
          },
        ];
      }

      return [
        {
          key: "oversized-outputs",
          checkpoint: "Size policy result",
          posture: policyExceededRows.length ? "Review" : legacyOverFiveRows.length ? "Review" : policyAllowedRows.length || positiveRows.length ? "Observe" : "Read-only",
          evidence: policyExceededRows.length
            ? `${policyExceededRows.length} row(s) exceeded recorded size_policy; largest visible row: ${topGrowthLabel} (${topGrowthDelta}).`
            : legacyOverFiveRows.length
              ? `${legacyOverFiveRows.length} legacy row(s) grew over +5% without recorded size_policy; largest visible row: ${topGrowthLabel} (${topGrowthDelta}).`
              : policyAllowedRows.length
                ? `${policyAllowedRows.length} row(s) grew but stayed within recorded size_policy; largest visible row: ${topGrowthLabel} (${topGrowthDelta}).`
                : positiveRows.length
                  ? `${positiveRows.length} row(s) grew under +5% or without policy classification; largest visible row: ${topGrowthLabel} (${topGrowthDelta}).`
              : neutralSmallRows.length
                ? `${neutralSmallRows.length} healthy row(s) have only +/-1% size delta and are treated as neutral.`
                : "No loaded completed rows report review-level positive output growth.",
          action: policyExceededRows.length || legacyOverFiveRows.length
            ? "Select largest growth row and compare route/encoder/size_policy/log evidence before accepting output."
            : "Use this as supporting evidence only; backend size_policy may already allow compatibility growth.",
          completedRow: topGrowthRow,
          detail: [
            `Rows loaded: ${payload.count || rowList.length}`,
            `Rows exceeding recorded size_policy: ${policyExceededRows.length}`,
            `Rows within recorded size_policy: ${policyAllowedRows.length}`,
            `Legacy rows over +5% with no size_policy: ${legacyOverFiveRows.length}`,
            `Rows with smaller positive growth: ${positiveRows.length}`,
            `Healthy +/-1% neutral rows: ${neutralSmallRows.length}`,
          ],
        },
        {
          key: "size-comparison-fields",
          checkpoint: "Size comparison fields",
          posture: unknownRows.length ? "Review" : "Read-only",
          evidence: unknownRows.length
            ? `${unknownRows.length} completed row(s) lack source/output comparison fields.`
            : "Loaded completed rows include size comparison fields where size review needs them.",
          action: unknownRows.length
            ? "Open Completed Manifest and Run Logs before treating size as proof."
            : "Use the size board as triage; manifest/log evidence remains the source of truth.",
          completedRow: unknownRows[0] || null,
          detail: [
            "Unknown size comparison means the UI cannot prove shrink, growth, or no-change from loaded metadata.",
            "Do not infer successful publish solely from a missing size delta.",
          ],
        },
        {
          key: "route-encoder-evidence",
          checkpoint: "Route and encoder evidence",
          posture: topGrowthRow ? "Read-first" : "Read-only",
          evidence: topGrowthRow ? `Top growth row route: ${routeSummary}; encoder: ${encoderSummary}; size policy ${topGrowthRow.size_policy_limit_label || "not recorded"}.` : "No growth row is available for route/encoder review.",
          action: topGrowthRow
            ? "Compare route reason, encoder/GPU, audio, and subtitle decisions against the intended Plex profile."
            : "When a growth row appears, review route metadata before rerun or policy changes.",
          completedRow: topGrowthRow,
          detail: [
            "Size growth may be intentional for compatibility, subtitles, or audio normalization.",
            "Compare route_evidence_lines and safe_next_action before changing encoder/remux policy.",
          ],
        },
        {
          key: "pending-proof-handoff",
          checkpoint: "Pending publish proof",
          posture: proofBlocked.length ? "Blocked review" : proofExact.length || proofSameLeaf.length ? "Review" : "Read-only",
          evidence: outputProofText,
          action: proofBlocked.length
            ? "Use Output Proof Cross-Check before rerun, cleanup, or drain; resolve blockers first."
            : "Use Output Proof Cross-Check before rerun/cleanup; exact paths are proof, same-leaf is advisory.",
          completedRow: (proofBlocked[0] || proofExact[0] || proofSameLeaf[0])?.completed || topGrowthRow,
          detail: [
            `Proof rows loaded: ${proofList.length}`,
            `Blocked proof rows: ${proofBlocked.length}`,
            `Exact overlap rows: ${proofExact.length}`,
            `Same-leaf advisory rows: ${proofSameLeaf.length}`,
          ],
        },
        {
          key: "diagnostics-order",
          checkpoint: "Diagnostics order",
          posture: "Read-first",
          evidence: "Completed Manifest -> Run Logs -> Last Stderr -> Latest Failure -> Pending Publish when applicable.",
          action: "Use Completed Diagnostics Cross-Links; no repair/rerun from this board.",
          completedRow: topGrowthRow,
          detail: [
            "The diagnostics buttons use backend allowlists and do not accept arbitrary frontend paths.",
            "For oversized outputs, read route evidence before assuming a bad encode.",
          ],
        },
        {
          key: "policy-boundary",
          checkpoint: "Policy boundary",
          posture: "Read-only",
          evidence: "This board does not alter Output Size Check settings, media policy, manifests, pending publish state, or filesystem contents.",
          action: "Change policy only through Settings preview/save and verify the backend risk preview.",
          detail: [
            "Frontend remains read-only here.",
            "Backend-owned settings commands remain the only supported policy mutation path.",
          ],
        },
      ];
    }

    function completedSizeEvidenceStatus(evidenceRows) {
      const rows = Array.isArray(evidenceRows) ? evidenceRows : [];
      if (!rows.length) return "No evidence";
      if (rows.some((row) => completedSizeEvidencePostureStatus(row.posture) === "blocked")) return "Blocked review";
      if (rows.some((row) => completedSizeEvidencePostureStatus(row.posture) === "warning")) return "Review evidence";
      if (rows.some((row) => completedSizeEvidencePostureStatus(row.posture) === "changed")) return "Read evidence";
      if (rows.some((row) => completedSizeEvidencePostureStatus(row.posture) === "unknown")) return "No history";
      return "Read-only";
    }

    function completedSizeEvidenceSummaryLines(evidenceRows) {
      const rows = Array.isArray(evidenceRows) ? evidenceRows : [];
      const reviewCount = rows.filter((row) => ["blocked", "warning"].includes(completedSizeEvidencePostureStatus(row.posture))).length;
      const lines = [
        "Size growth evidence handoff:",
        `Checkpoints loaded: ${rows.length}`,
        `Checkpoints needing review: ${reviewCount}`,
        "Proof order: Completed Manifest, Run Logs, Last Stderr, Output Proof Cross-Check, Settings policy preview.",
        "Rule: exact full-path proof beats same-leaf review.",
      ];
      if (reviewCount) {
        lines.push("First action: select review checkpoints, then select the associated completed row before accepting an oversized output.");
      } else {
        lines.push("First action: keep this as read-only supporting evidence; no size or media policy is changed here.");
      }
      lines.push("Mutation guardrail: size-growth investigation remains read-only in WebView.");
      return lines;
    }

    function completedSizeEvidenceDetailLines(item) {
      if (!item) {
        return [
          "Size growth evidence handoff:",
          "Select a checkpoint row to see proof-order detail.",
          "Mutation guardrail: this detail panel is read-only.",
        ];
      }
      const completedRow = item.completedRow || null;
      const lines = [
        "Size growth evidence handoff:",
        `Checkpoint: ${item.checkpoint || "unknown"}`,
        `Posture: ${item.posture || "unknown"}`,
        `Evidence: ${item.evidence || "not reported"}`,
        `Action: ${item.action || "Review Completed, Pending Publish, and Diagnostics evidence before acting."}`,
      ];
      const details = Array.isArray(item.detail) ? item.detail.filter(Boolean) : [];
      if (details.length) {
        lines.push("", "Checkpoint detail:");
        details.forEach((line) => lines.push(String(line)));
      }
      if (completedRow) {
        lines.push(
          "",
          "Associated completed row:",
          `Title: ${completedProofRowLabel(completedRow)}`,
          `Output: ${completedProofCompletedOutputPath(completedRow) || "unknown"}`,
          `Source: ${completedProofCompletedSourcePath(completedRow) || "unknown"}`,
        );
      }
      lines.push("", "Mutation guardrail: this detail panel does not accept, repair, rerun, drain, cleanup, delete, publish, rewrite manifests, or touch media files.");
      return lines;
    }

    function selectedCompletedSizeEvidenceRow(evidenceRows) {
      const rows = Array.isArray(evidenceRows) ? evidenceRows : [];
      return rows.find((row) => row.key === state.selectedCompletedSizeEvidenceKey)
        || rows.find((row) => completedSizeEvidencePostureStatus(row.posture) === "blocked")
        || rows.find((row) => completedSizeEvidencePostureStatus(row.posture) === "warning")
        || rows[0]
        || null;
    }

    function selectCompletedSizeEvidenceRow(item) {
      state.selectedCompletedSizeEvidenceKey = item?.key || "";
      if (item?.completedRow?.row_key) {
        state.selectedCompletedRowKey = item.completedRow.row_key;
        renderCompletedDetail(item.completedRow);
        renderCompletedReviewDigest(state.lastCompletedPayload, state.lastCompletedRows);
        renderCompletedSizeReview(state.lastCompletedPayload, state.lastCompletedRows);
        renderCompletedPendingProof(state.lastCompletedPayload, state.lastCompletedRows, state.lastCompletedPendingPayload);
        renderCompletedOutputAcceptance(state.lastCompletedPayload, state.lastCompletedRows, state.lastCompletedPendingProofRows);
        renderCompletedRealMediaProof(state.lastCompletedPayload, state.lastCompletedRows, state.lastCompletedPendingProofRows, state.lastCompletedPendingPayload);
        renderCompletedFinalTrust(state.lastCompletedPayload, state.lastCompletedRows, state.lastCompletedPendingProofRows, state.lastCompletedPendingPayload);
        renderCompletedPilotEvidencePacket(state.lastCompletedPayload, state.lastCompletedRows, state.lastCompletedPendingProofRows, state.lastCompletedPendingPayload);
        renderCompletedRows();
        return;
      }
      renderCompletedSizeEvidence(state.lastCompletedPayload, state.lastCompletedRows, state.lastCompletedPendingProofRows);
    }

    function renderCompletedSizeEvidence(completed, rows, proofRows = state.lastCompletedPendingProofRows) {
      const payload = completed || {};
      const rowList = Array.isArray(rows) ? rows : [];
      const evidenceRows = completedSizeEvidenceRows(payload, rowList, proofRows);
      if (state.selectedCompletedSizeEvidenceKey && !evidenceRows.some((row) => row.key === state.selectedCompletedSizeEvidenceKey)) {
        state.selectedCompletedSizeEvidenceKey = "";
      }
      const selected = selectedCompletedSizeEvidenceRow(evidenceRows);
      setText("completed-size-evidence-status", completedSizeEvidenceStatus(evidenceRows));
      setText("completed-size-evidence-summary", completedSizeEvidenceSummaryLines(evidenceRows).join("\n"));
      setText("completed-size-evidence-detail", completedSizeEvidenceDetailLines(selected).join("\n"));
      const tbody = byId("completed-size-evidence-rows");
      if (!tbody) return;
      if (!evidenceRows.length) {
        clearRows(tbody, 4, "No size-growth evidence checkpoints loaded.");
        updateTableStatusLegend("completed-size-evidence-legend", tbody, "Completed size-growth evidence rows");
        return;
      }
      tbody.replaceChildren();
      evidenceRows.forEach((item) => {
        const row = document.createElement("tr");
        row.dataset.status = completedSizeEvidencePostureStatus(item.posture);
        appendCells(row, [
          item.checkpoint || "",
          item.posture || "Read-only",
          item.evidence || "",
          item.action || "",
        ]);
        makeRowSelectable(row, () => selectCompletedSizeEvidenceRow(item), {
          selected: item.key === state.selectedCompletedSizeEvidenceKey,
          label: `Review completed size-growth evidence ${item.checkpoint || ""}`,
        });
        tbody.appendChild(row);
      });
      updateTableStatusLegend("completed-size-evidence-legend", tbody, "Completed size-growth evidence rows");
    }

    function completedBreakdownStatus(completed, rows) {
      const rowList = Array.isArray(rows) ? rows : [];
      if (!rowList.length) return "No rows";
      if (Number(completed?.size_growth_over_5_count || 0) > 0) return "Growth review";
      if (Number(completed?.missing_output_count || 0) > 0) return "Output review";
      if (completedManifestIsAged(completed)) return "History aged";
      return "Loaded";
    }

    function completedBreakdownLines(completed, rows) {
      const payload = completed || {};
      const rowList = Array.isArray(rows) ? rows : [];
      const decisionTotals = payload.decision_totals && typeof payload.decision_totals === "object" ? payload.decision_totals : {};
      const lines = [
        `Rows loaded: ${payload.count || rowList.length || 0}`,
        completedFreshnessLine("Manifest age", payload.manifest_age_text, payload.manifest_freshness_status, payload.manifest_mtime_utc),
        `Routes: ${completedFormatCounts(payload.route_counts)}`,
        `Publish states: ${completedFormatCounts(payload.publish_counts)}`,
        `Output health: ${completedFormatCounts(payload.health_counts)}`,
        `Operator statuses: ${completedFormatCounts(payload.operator_status_counts)}`,
        `Operator severities: ${completedFormatCounts(payload.operator_severity_counts)}`,
        `Media types: ${completedFormatCounts(payload.media_type_counts)}`,
        `Runtime outcomes: ${completedFormatCounts(payload.runtime_outcome_status_counts)}`,
        `Runtime outcome errors: ${completedFormatCounts(payload.runtime_outcome_error_code_counts)}`,
        `Runtime outcome freshness: ${completedFormatCounts(payload.runtime_outcome_freshness_counts)}`,
        `Decision totals: audio ${decisionTotals.audio || 0}, subtitle ${decisionTotals.subtitle || 0}`,
        `Size growth: ${payload.size_growth_count || 0}; over +5%: ${payload.size_growth_over_5_count || 0}; unknown: ${payload.size_unknown_count || 0}`,
        "Operator note: completed history is a manifest preview. Use output-integrity and Diagnostics before rerunning or deleting outputs.",
      ];
      return lines;
    }

    function renderCompletedBreakdown(completed, rows) {
      const rowList = Array.isArray(rows) ? rows : [];
      setText("completed-breakdown-status", completedBreakdownStatus(completed || {}, rowList));
      setText("completed-breakdown", completedBreakdownLines(completed || {}, rowList).join("\n"));
    }

    function completedRuntimeStatus(completed, rows) {
      const payload = completed || {};
      const rowList = Array.isArray(rows) ? rows : [];
      if (payload.error) return "Unavailable";
      if (!payload.runtime_outcome_source) return "No event source";
      if (payload.runtime_outcome_warning) return "History warning";
      if (!Number(payload.runtime_outcome_event_count || 0)) return "No recent events";
      if (!Number(payload.runtime_outcome_match_count || 0)) return rowList.length ? "No row matches" : "No rows";
      const freshness = payload.runtime_outcome_freshness_counts || {};
      if (Number(freshness.stale || 0) > 0) return "Stale matches";
      const statuses = payload.runtime_outcome_status_counts || {};
      const failed = Object.entries(statuses).some(([key, count]) => {
        const text = String(key || "").toLowerCase();
        return Number(count || 0) > 0 && (text.includes("fail") || text === "skipped" || text === "stopped");
      });
      return failed ? "Review history" : "Matched";
    }

    function completedRuntimeLines(completed, rows) {
      const payload = completed || {};
      const rowList = Array.isArray(rows) ? rows : [];
      const lines = [
        `Pipeline event source: ${payload.runtime_outcome_source || "(not configured)"}`,
        `Recent events read: ${payload.runtime_outcome_event_count || 0}`,
        `Completed rows loaded: ${rowList.length}`,
        `Rows with exact source/output runtime history: ${payload.runtime_outcome_match_count || 0}`,
        `Outcome statuses: ${completedFormatCounts(payload.runtime_outcome_status_counts)}`,
        `Outcome event types: ${completedFormatCounts(payload.runtime_outcome_event_type_counts)}`,
        `Outcome error codes: ${completedFormatCounts(payload.runtime_outcome_error_code_counts)}`,
        `Outcome freshness: ${completedFormatCounts(payload.runtime_outcome_freshness_counts)}`,
      ];
      if (payload.runtime_outcome_warning) {
        lines.push("", `Warning: ${payload.runtime_outcome_warning}`);
      }
      const stale = Number((payload.runtime_outcome_freshness_counts || {}).stale || 0);
      if (stale > 0) {
        lines.push("", "Stale history is shown only as context. Inspect recent run logs before treating old runtime events as current completed-state truth.");
      }
      if (!Number(payload.runtime_outcome_event_count || 0)) {
        lines.push("", "No recent pipeline completion/failure events were available in the bounded event tail.");
      } else if (!Number(payload.runtime_outcome_match_count || 0)) {
        lines.push("", "No completed row matched recent runtime history. Matching is exact source-path first, then exact output-path if event output data exists.");
      } else {
        lines.push("", "Select a completed row to inspect the matching runtime status, error code, reason, publish state, and output path.");
      }
      lines.push("Mutation guardrail: runtime history is read-only context; repair, reconcile, rerun, and cleanup remain backend-owned.");
      return lines;
    }

    function renderCompletedRuntime(completed, rows) {
      const rowList = Array.isArray(rows) ? rows : [];
      setText("completed-runtime-status", completedRuntimeStatus(completed || {}, rowList));
      setText("completed-runtime", completedRuntimeLines(completed || {}, rowList).join("\n"));
    }

    function completedConsistencyStatus(completed, rows) {
      const rowList = Array.isArray(rows) ? rows : [];
      if (completed?.error) return "Unavailable";
      if (!rowList.length) return "No rows";
      if (Number(completed?.missing_output_count || 0) > 0) return "Broken";
      if (Number(completed?.missing_sidecar_count || 0) > 0 || Number(completed?.output_sidecar_mismatch_count || 0) > 0 || Number(completed?.stale_sidecar_count || 0) > 0) return "Review";
      return "Consistent";
    }

    function completedConsistencyLines(completed, rows) {
      const payload = completed || {};
      const rowList = Array.isArray(rows) ? rows : [];
      const lines = [
        `Rows loaded: ${payload.count || rowList.length || 0}`,
        `Consistency statuses: ${completedFormatCounts(payload.consistency_status_counts)}`,
        `Consistency severities: ${completedFormatCounts(payload.consistency_severity_counts)}`,
        `Size buckets: ${completedFormatCounts(payload.size_bucket_counts)}`,
        `Missing outputs: ${payload.missing_output_count || 0}`,
        `Missing sidecars: ${payload.missing_sidecar_count || 0}`,
        `Output/sidecar mismatches: ${payload.output_sidecar_mismatch_count || 0}`,
        `Sidecars older than output: ${payload.stale_sidecar_count || 0}`,
        `Manifest rows without output path/file: ${payload.missing_manifest_output_path_count || 0}`,
      ];
      lines.push("");
      if (!rowList.length) {
        lines.push("Next step: no completed rows are loaded. This is normal before the first successful job; otherwise open Completed Manifest from Diagnostics.");
      } else if (Number(payload.missing_output_count || 0) > 0) {
        lines.push("Next step: inspect broken rows before rerun or cleanup. A completed manifest row without output is not proof of success.");
      } else if (Number(payload.missing_sidecar_count || 0) > 0 || Number(payload.output_sidecar_mismatch_count || 0) > 0 || Number(payload.stale_sidecar_count || 0) > 0) {
        lines.push("Next step: inspect sidecar consistency before rerun or library cleanup. Open backend-selected output and sidecar locations from the selected row.");
      } else {
        lines.push("Next step: loaded completed rows have matching output/sidecar consistency checks.");
      }
      lines.push("Mutation guardrail: this panel is read-only. Repair, reconcile, and backfill remain backend-owned actions.");
      return lines;
    }

    function renderCompletedConsistency(completed, rows) {
      const rowList = Array.isArray(rows) ? rows : [];
      setText("completed-consistency-status", completedConsistencyStatus(completed || {}, rowList));
      setText("completed-consistency", completedConsistencyLines(completed || {}, rowList).join("\n"));
    }

    const COMPLETED_VALIDATION_STATE_SCHEMA_VERSION = "desktop_validation_state.v1";

    function completedValidationStatePayload(completed) {
      const payload = completed || {};
      return payload.validation_state && typeof payload.validation_state === "object" ? payload.validation_state : {};
    }

    function completedValidationStatusLabel(state) {
      const normalized = String(state || "").toLowerCase();
      if (normalized === "blocked") return "Blocked";
      if (normalized === "validation-needed") return "Validation needed";
      if (normalized === "completed") return "Complete";
      if (normalized === "warning") return "Review";
      if (normalized === "idle") return "No history";
      return normalized ? normalized.replace(/-/g, " ") : "Unknown";
    }

    function completedValidationProofLabel(value) {
      if (value === true) return "passed";
      if (value === false) return "failed";
      return "not reported";
    }

    function completedValidationStatus(completed, rows) {
      const payload = completed || {};
      const rowList = Array.isArray(rows) ? rows : [];
      const validation = completedValidationStatePayload(payload);
      if (payload.error) return "Unavailable";
      if (validation.status_state) return completedValidationStatusLabel(validation.status_state);
      if (!rowList.length) return "No history";
      if (Number(payload.missing_output_count || 0) > 0) return "Broken outputs";
      if (Number(payload.size_growth_over_5_count || 0) > 0) return "Size review";
      if (Number(payload.missing_sidecar_count || 0) > 0 || Number(payload.output_sidecar_mismatch_count || 0) > 0 || Number(payload.stale_sidecar_count || 0) > 0) return "Sidecar review";
      if (payload.runtime_outcome_warning) return "History warning";
      if (Number((payload.runtime_outcome_freshness_counts || {}).stale || 0) > 0 || completedManifestIsAged(payload)) return "Stale context";
      return "Trustworthy";
    }

    function completedValidationChecklistLines(completed, rows) {
      const payload = completed || {};
      const rowList = Array.isArray(rows) ? rows : [];
      const validation = completedValidationStatePayload(payload);
      const warnings = Array.isArray(payload.warnings) ? payload.warnings.filter(Boolean) : [];
      if (payload.error) {
        return [
          "Validation state: completed history is unavailable.",
          `Error: ${payload.error}`,
          "Operator action: open Diagnostics > Completed Manifest, Run Logs, and Last Stderr before trusting completed-state decisions.",
          "Mutation guardrail: this checklist is read-only and does not repair, reconcile, rerun, or delete outputs.",
        ];
      }
      const lines = [
        "Real-media validation checklist:",
        `Expected validation contract: ${COMPLETED_VALIDATION_STATE_SCHEMA_VERSION}`,
        `Validation contract: ${validation.schema_version || "not reported"}`,
        `Validation state: ${completedValidationStatusLabel(validation.status_state)}`,
        `Validation rows: ${validation.row_count || 0}; blocked=${validation.blocked_count || 0}; needed=${validation.validation_needed_count || 0}; complete=${validation.completed_count || 0}; unavailable=${validation.unavailable_count || 0}`,
        `Playback required rows: ${validation.playback_required_count || 0}`,
        `Probe proof: ${validation.row_count ? "row-level; see selected row" : "not reported"}`,
        `Hash proof: ${validation.row_count ? "row-level; see selected row" : "not reported"}`,
        `Manifest fresh enough: ${completedManifestIsAged(payload) ? "no - treat as old context" : "yes"}`,
        payload.manifest_freshness_status ? completedFreshnessLine("Manifest age", payload.manifest_age_text, payload.manifest_freshness_status, payload.manifest_mtime_utc) : "Manifest age: not reported",
        `Completed rows loaded: ${payload.count || rowList.length || 0}`,
        `Missing outputs: ${payload.missing_output_count || 0}`,
        `Missing sidecars: ${payload.missing_sidecar_count || 0}`,
        `Output/sidecar mismatches: ${payload.output_sidecar_mismatch_count || 0}`,
        `Stale sidecars: ${payload.stale_sidecar_count || 0}`,
        `Size growth over +5%: ${payload.size_growth_over_5_count || 0}`,
        `Unknown size rows: ${payload.size_unknown_count || 0}`,
        `Runtime history matched rows: ${payload.runtime_outcome_match_count || 0}`,
        `Runtime freshness: ${completedFormatCounts(payload.runtime_outcome_freshness_counts)}`,
        `Runtime error codes: ${completedFormatCounts(payload.runtime_outcome_error_code_counts)}`,
        `Warnings: ${warnings.length}`,
      ];
      lines.push("");
      if (!rowList.length) {
        lines.push("Operator action: no completed rows are loaded. This is normal before first success; otherwise open the completed manifest and run logs.");
      } else if (validation.status_state === "blocked") {
        lines.push("Operator action: filter for blocked validation rows. A missing output or failed proof is not safe Sample Validation evidence.");
      } else if (validation.status_state === "validation-needed") {
        lines.push("Operator action: treat Completed rows as output-presence evidence only until probe/hash/playback proof is available or manually recorded.");
      } else if (Number(payload.missing_output_count || 0) > 0) {
        lines.push("Operator action: filter for missing/broken outputs. A completed manifest row without an output is not proof of success.");
      } else if (Number(payload.size_growth_over_5_count || 0) > 0) {
        lines.push("Operator action: inspect size-growth rows before trusting encode/remux decisions; growth may be expected, but large growth needs review.");
      } else if (Number(payload.missing_sidecar_count || 0) > 0 || Number(payload.output_sidecar_mismatch_count || 0) > 0 || Number(payload.stale_sidecar_count || 0) > 0) {
        lines.push("Operator action: inspect sidecar consistency before rerun, cleanup, or Plex library decisions.");
      } else if (payload.runtime_outcome_warning || Number((payload.runtime_outcome_freshness_counts || {}).stale || 0) > 0 || completedManifestIsAged(payload)) {
        lines.push("Operator action: treat completed rows as historical context until Run Logs or a fresh manifest confirm the current disk state.");
      } else if (warnings.length) {
        lines.push("Operator action: review warning text before using completed history for rerun or cleanup decisions.");
      } else {
        lines.push("Operator action: completed manifest, output presence, sidecar consistency, size policy, and runtime context look internally consistent.");
      }
      lines.push("Proof boundary: this checklist does not run ffprobe, hash files, or mark playback accepted.");
      lines.push("Mutation guardrail: this checklist does not repair manifests, reconcile outputs, rerun jobs, or delete files.");
      return lines;
    }

    function renderCompletedValidation(completed, rows) {
      const rowList = Array.isArray(rows) ? rows : [];
      setText("completed-validation-status", completedValidationStatus(completed || {}, rowList));
      setText("completed-validation", completedValidationChecklistLines(completed || {}, rowList).join("\n"));
    }

    function completedRowReviewChecklistLines(item) {
      if (!item) {
        return [
          "Selected completed-row review checklist:",
          "Select a completed row to see output, sidecar, size-growth, route, and runtime-history guidance.",
        ];
      }
      const reviewFlags = Array.isArray(item.review_flags) ? item.review_flags.filter(Boolean) : [];
      const consistencyIssues = Array.isArray(item.consistency_issues) ? item.consistency_issues.filter(Boolean) : [];
      const runtimeStatus = String(item.runtime_outcome_status || "").toLowerCase();
      const runtimeFreshness = String(item.runtime_outcome_freshness_status || "").toLowerCase();
      const missingOutput = item.output_exists === false || String(item.output_health || "").toLowerCase().includes("missing");
      const missingSidecar = item.sidecar_exists === false || consistencyIssues.some((issue) => String(issue).toLowerCase().includes("sidecar"));
      const recentRuntimeIssue = runtimeFreshness === "fresh" && ["failed", "error", "skipped"].some((value) => runtimeStatus.includes(value));
      const needsReview = missingOutput || missingSidecar || item.size_growth_over_5 || recentRuntimeIssue || reviewFlags.length > 0 || consistencyIssues.length > 0;
      const backendTrustState = String(item.operator_trust_state || "").trim();
      const lines = [
        "Selected completed-row review checklist:",
        `Row state: ${backendTrustState || (missingOutput ? "broken-output" : needsReview ? "review" : "consistent-looking")}`,
        `Output health: ${item.output_health || (item.output_exists === false ? "missing output" : "ok")}`,
        `Validation state: ${completedValidationStatusLabel(item.validation_status_state)}`,
        `Probe proof: ${completedValidationProofLabel(item.validation_probe_ok)}`,
        `Hash proof: ${completedValidationProofLabel(item.validation_hash_ok)}`,
        `Playback required: ${item.validation_playback_required === true ? "yes" : item.validation_playback_required === false ? "no" : "not reported"}`,
        `Consistency: ${item.consistency_status || "not reported"}`,
        `Size growth: ${item.size_delta_label || "unknown"}${item.size_growth_over_5 ? " (over +5%)" : ""}`,
        `Runtime history: ${item.runtime_outcome_status || "none"}${item.runtime_outcome_freshness_status ? ` (${item.runtime_outcome_freshness_status})` : ""}`,
        `Review flags: ${reviewFlags.length ? reviewFlags.join(", ") : "none"}`,
        `Consistency issues: ${consistencyIssues.length ? consistencyIssues.join(", ") : "none"}`,
      ];
      const reviewMarkers = [
        ...reviewFlags,
        ...consistencyIssues.map((issue) => `consistency:${issue}`),
      ];
      const reviewFlagExplanations = typeof window.mediaPipelineDom?.reviewFlagExplanationLines === "function"
        ? window.mediaPipelineDom.reviewFlagExplanationLines(reviewMarkers, {
          title: "Review flag explanations:",
          emptyMessage: "No Completed review flags or consistency issues were reported for this row.",
          guardrail: "Mutation guardrail: review-flag explanations translate Completed history markers only; they cannot accept outputs, repair manifests, rerun jobs, reconcile sidecars, publish, or delete files.",
        })
        : [];
      lines.push(...reviewFlagExplanations);
      if (item.runtime_outcome_error_code || item.runtime_outcome_reason) {
        lines.push(`Runtime issue: ${[item.runtime_outcome_error_code, item.runtime_outcome_reason].filter(Boolean).join(" - ")}`);
      }
      if (item.validation_failure_reason) {
        lines.push(`Validation proof gap: ${item.validation_failure_reason}`);
      }
      if (Array.isArray(item.validation_unavailable_reasons) && item.validation_unavailable_reasons.length) {
        lines.push(`Validation unavailable proof: ${item.validation_unavailable_reasons.join(", ")}`);
      }
      if (item.operator_guidance) {
        lines.push(`Operator action: ${item.operator_guidance}`);
      } else if (missingOutput) {
        lines.push("Operator action: inspect the output folder and Run Logs before trusting this row as completed.");
      } else if (missingSidecar) {
        lines.push("Operator action: inspect sidecar consistency before cleanup, rerun, or Plex library decisions.");
      } else if (item.size_growth_over_5) {
        lines.push("Operator action: compare source/output details before treating this encode as acceptable.");
      } else if (recentRuntimeIssue) {
        lines.push("Operator action: recent runtime conflict is fresh; inspect Run Logs before rerun or cleanup.");
      } else {
        lines.push("Operator action: row looks internally consistent; repair, reconcile, rerun, and cleanup remain backend-owned.");
      }
      lines.push("Mutation guardrail: selected-row detail is read-only and cannot repair manifests, rerun jobs, reconcile outputs, or delete files.");
      return lines;
    }

    function completedSelectedAtAGlanceState(item) {
      if (!item) return "unknown";
      const backendState = typeof backendRowStatusState === "function" ? backendRowStatusState(item) : "";
      const benignAlreadyProcessed = completedRowHasBenignAlreadyProcessedOutcome(item);
      if (["blocked", "failed"].includes(backendState)) return "blocked";
      if (completedRowLooksHealthy(item) && ["", "normal", "warning", "changed", "unknown"].includes(backendState)) return "ready";
      if (benignAlreadyProcessed && ["", "normal", "warning", "changed", "unknown"].includes(backendState)) return "ready";
      if (["warning", "running", "skipped", "parked", "publishing", "health-check"].includes(backendState)) return "warning";
      if (["match", "ready", "completed"].includes(backendState)) return "ready";
      const reviewFlags = Array.isArray(item.review_flags) ? item.review_flags.filter((flag) => !completedReviewFlagIsBenign(flag, item)) : [];
      const consistencyIssues = Array.isArray(item.consistency_issues) ? item.consistency_issues.filter(Boolean) : [];
      const runtimeStatus = String(item.runtime_outcome_status || "").toLowerCase();
      const runtimeFreshness = String(item.runtime_outcome_freshness_status || "").toLowerCase();
      const missingOutput = item.output_exists === false || String(item.output_health || "").toLowerCase().includes("missing");
      const missingSidecar = item.sidecar_exists === false || consistencyIssues.some((issue) => String(issue).toLowerCase().includes("sidecar"));
      const recentRuntimeIssue = runtimeFreshness === "fresh" && ["failed", "error", "skipped"].some((value) => runtimeStatus.includes(value));
      if (missingOutput) return "blocked";
      if (missingSidecar || item.size_growth_over_5 || recentRuntimeIssue || reviewFlags.length || consistencyIssues.length) return "warning";
      return "ready";
    }

    function completedSelectedOutputUnavailable(item) {
      if (!item) return false;
      const outputHealth = String(item.output_health || "").toLowerCase();
      return item.output_exists === false
        || outputHealth.includes("missing")
        || outputHealth.includes("unavailable")
        || outputHealth.includes("without media");
    }

    function completedSelectedAtAGlanceStatus(item) {
      const state = completedSelectedAtAGlanceState(item);
      if (state === "blocked") return completedSelectedOutputUnavailable(item) ? "Output unavailable" : "Needs review";
      if (state === "warning") return "Review";
      if (state === "ready") return "Consistent-looking";
      return "No selection";
    }

    function completedSelectedVisibilitySummary(item) {
      const lines = completedFilterVisibilityLines(item);
      return lines
        .filter((line) => /^Selected row visible|^Active filters|^Hidden by current filters/.test(String(line || "")))
        .join(" ");
    }

    function completedSelectedLabel(item) {
      if (!item) return "No completed row selected";
      return item.output_file || item.lookup_title || item.output_path || item.source_path || "(unnamed row)";
    }

    function completedSelectedConcern(item) {
      if (!item) return "No row selected.";
      const healthy = completedRowLooksHealthy(item);
      return healthy && completedPrimaryConcernIsBenign(item)
        ? "row has no output, sidecar, size, or runtime blocker in the loaded completed manifest"
        : item.primary_concern
        || (item.output_exists === false ? "completed row points to a missing output" : "")
        || (item.size_growth_over_5 ? "output grew beyond policy threshold" : "")
        || item.operator_guidance
        || "no primary concern reported";
    }

    function completedSelectedSafeAction(item) {
      if (!item) return "Select a completed row to review output, sidecar, route, size, pending-publish, and diagnostics evidence.";
      return item.safe_next_action
        || item.operator_guidance
        || (completedSelectedAtAGlanceState(item) === "ready"
          ? "Compare output/sidecar proof and Pending Publish state before treating this as accepted."
          : "Read Completed Manifest, Pending Publish, Run Logs, and Last Stderr before rerun or cleanup.");
    }

    function completedSelectedTrustStatus(item) {
      if (!item) return "not selected";
      if (completedSelectedOutputUnavailable(item)) return "output unavailable";
      return completedRowLooksHealthy(item)
        ? "consistent-looking"
        : item.operator_trust_state || item.output_health || item.consistency_status || "not reported";
    }

    function completedSelectedRouteLabel(item) {
      if (!item) return "not reported";
      return item.route_decision_summary || item.route_label || item.route || "not reported";
    }

    function completedSelectedSizeLabel(item) {
      if (!item) return "unknown";
      return item.size_delta_label || item.size_reduction_text || "unknown";
    }

    function completedSelectedRuntimeLabel(item) {
      if (!item) return "none reported";
      return [
        item.runtime_outcome_status,
        item.runtime_outcome_error_code,
        item.runtime_outcome_reason,
        item.runtime_outcome_freshness_status,
      ].filter(Boolean).join(" - ") || "none reported";
    }

    function completedSelectedPolicyLabel(item) {
      if (!item) return "not reported";
      return [item.route_reason_code, item.route_reason, item.route_decision_summary].filter(Boolean).join(" - ") || "not reported";
    }

    function completedSelectedEvidenceItems(item) {
      return [
        ["Route", completedSelectedRouteLabel(item)],
        ["Size change", completedSelectedSizeLabel(item)],
        ["Health", item?.output_health || "unknown"],
        ["Runtime", completedSelectedRuntimeLabel(item)],
        ["Audio tracks", String(item?.audio_decision_count || 0)],
        ["Subtitle tracks", String(item?.subtitle_decision_count || 0)],
        ["Current table visibility", completedSelectedVisibilitySummary(item) || "not evaluated"],
        ["Policy / route reason", completedSelectedPolicyLabel(item)],
      ];
    }

    function completedSelectedNode(tagName, className, text) {
      const node = document.createElement(tagName);
      if (className) node.className = className;
      if (text !== undefined && text !== null) node.textContent = String(text);
      return node;
    }

    function completedSelectedPriorityRow(label, value) {
      const row = completedSelectedNode("div", "completed-selected-priority-row");
      row.appendChild(completedSelectedNode("span", "completed-selected-label", label));
      row.appendChild(completedSelectedNode("p", "completed-selected-priority-text", value || "not reported"));
      return row;
    }

    function completedSelectedEvidenceItem(label, value) {
      const item = completedSelectedNode("div", "completed-selected-evidence-item");
      item.appendChild(completedSelectedNode("span", "completed-selected-label", label));
      item.appendChild(completedSelectedNode("strong", "completed-selected-evidence-value", value || "not reported"));
      return item;
    }

    function completedSelectedPaths(item) {
      const details = completedSelectedNode("details", "completed-selected-paths");
      details.appendChild(completedSelectedNode("summary", "", "Paths"));
      const list = completedSelectedNode("div", "completed-selected-path-list");
      const paths = [
        ["Output", item?.output_path],
        ["Source", item?.source_path],
        ["Sidecar", item?.sidecar_path],
      ].filter((entry) => entry[1]);
      if (!paths.length) {
        list.appendChild(completedSelectedNode("p", "completed-selected-path-empty", "No output, source, or sidecar path is reported for this row."));
      } else {
        paths.forEach(([label, value]) => {
          const row = completedSelectedNode("div", "completed-selected-path-row");
          row.appendChild(completedSelectedNode("span", "completed-selected-label", label));
          row.appendChild(completedSelectedNode("code", "completed-selected-path-value", value));
          list.appendChild(row);
        });
      }
      details.appendChild(list);
      return details;
    }

    function completedSelectedSummaryNodes(item, status, statusState) {
      const strip = completedSelectedNode("div", "completed-selected-decision-strip");
      const titleWrap = completedSelectedNode("div", "completed-selected-title-wrap");
      titleWrap.appendChild(completedSelectedNode("span", "completed-selected-label", "File/title"));
      titleWrap.appendChild(completedSelectedNode("strong", "completed-selected-title", completedSelectedLabel(item)));
      titleWrap.appendChild(completedSelectedNode("span", "completed-selected-trust", `Trust state: ${completedSelectedTrustStatus(item)}`));
      strip.appendChild(titleWrap);

      const badge = completedSelectedNode("strong", "completed-selected-status-chip", status);
      badge.dataset.state = statusState;
      strip.appendChild(badge);

      const priority = completedSelectedNode("div", "completed-selected-priority-grid");
      priority.appendChild(completedSelectedPriorityRow("Primary concern", completedSelectedConcern(item)));
      priority.appendChild(completedSelectedPriorityRow("Recommended next check", completedSelectedSafeAction(item)));

      const evidenceGrid = completedSelectedNode("div", "completed-selected-evidence-grid");
      completedSelectedEvidenceItems(item).forEach(([label, value]) => {
        evidenceGrid.appendChild(completedSelectedEvidenceItem(label, value));
      });

      const authority = completedSelectedNode(
        "p",
        "completed-selected-authority",
        item
          ? "Authority: this summary is read-only. It cannot accept outputs, repair manifests, rerun jobs, reconcile sidecars, publish, or delete files."
          : "Authority: this summary is read-only. Completed history is proof to inspect, not acceptance or cleanup authority.",
      );

      return [strip, priority, evidenceGrid, completedSelectedPaths(item), authority];
    }

    function completedSelectedAtAGlanceLines(item) {
      const sharedSummary = window.mediaPipelineDom?.selectedRowAtAGlanceLines;
      const authority = "Authority: this summary is read-only. It cannot accept outputs, repair manifests, rerun jobs, reconcile sidecars, publish, or delete files.";
      if (!item) {
        return typeof sharedSummary === "function"
          ? sharedSummary({
            title: "Selected Completed row",
            item: null,
            emptyNextStep: "Next step: select a completed row to review output, sidecar, route, size, pending-publish, and diagnostics evidence.",
            authority: "Authority: this summary is read-only. Completed history is proof to inspect, not acceptance or cleanup authority.",
          })
          : [
            "Selected Completed row: none",
            "Next step: select a completed row to review output, sidecar, route, size, pending-publish, and diagnostics evidence.",
            "Authority: this summary is read-only. Completed history is proof to inspect, not acceptance or cleanup authority.",
          ];
      }
      const concern = completedSelectedConcern(item);
      const safeAction = completedSelectedSafeAction(item);
      const outputReview = `${item.output_path || "output not reported"}; ${completedSelectedRouteLabel(item) || "route not reported"}; size=${completedSelectedSizeLabel(item)}; audio=${item.audio_decision_count || 0}; subtitles=${item.subtitle_decision_count || 0}; health=${item.output_health || "unknown"}`;
      const trustStatus = completedSelectedTrustStatus(item);
      if (typeof sharedSummary === "function") {
        return sharedSummary({
          title: "Selected Completed row",
          item,
          label: completedSelectedLabel(item),
          trustStatus,
          atAGlanceStatus: completedSelectedAtAGlanceStatus(item),
          proofLabel: "Output review",
          proof: outputReview,
          primaryConcern: concern,
          safeNextStep: safeAction,
          filterVisibility: completedSelectedVisibilitySummary(item) || "not evaluated",
          authority,
        });
      }
      return [
        `Selected Completed row: ${completedSelectedLabel(item)}`,
        `Trust/status: ${trustStatus}; at-a-glance=${completedSelectedAtAGlanceStatus(item)}`,
        `Output review: ${outputReview}`,
        `Primary concern: ${concern}`,
        `Safe next step: ${safeAction}`,
        `Filter visibility: ${completedSelectedVisibilitySummary(item) || "not evaluated"}`,
        authority,
      ];
    }

    function renderCompletedSelectedAtAGlance(item) {
      const status = completedSelectedAtAGlanceStatus(item);
      const statusState = completedSelectedAtAGlanceState(item);
      setText("completed-selected-status", status);
      const statusNode = byId("completed-selected-status");
      if (statusNode) statusNode.dataset.state = statusState;
      const summaryNode = byId("completed-selected-summary");
      if (!summaryNode || typeof summaryNode.replaceChildren !== "function") {
        setText("completed-selected-summary", completedSelectedAtAGlanceLines(item).join("\n"));
        return;
      }
      summaryNode.className = `completed-selected-summary${item ? "" : " is-empty"}`;
      summaryNode.dataset.state = statusState;
      summaryNode.replaceChildren(...completedSelectedSummaryNodes(item, status, statusState));
    }

    function completedRowIssueDigestLines(item) {
      if (!item) return [];
      const reviewFlags = Array.isArray(item.review_flags) ? item.review_flags.filter((flag) => !completedReviewFlagIsBenign(flag, item)) : [];
      const consistencyIssues = Array.isArray(item.consistency_issues) ? item.consistency_issues.filter(Boolean) : [];
      const runtimeStatus = String(item.runtime_outcome_status || "").toLowerCase();
      const runtimeFreshness = String(item.runtime_outcome_freshness_status || "").toLowerCase();
      const missingOutput = item.output_exists === false || String(item.output_health || "").toLowerCase().includes("missing");
      const missingSidecar = item.sidecar_exists === false || consistencyIssues.some((issue) => String(issue).toLowerCase().includes("sidecar"));
      const recentRuntimeIssue = runtimeFreshness === "fresh" && ["failed", "error", "skipped"].some((value) => runtimeStatus.includes(value));
      const issues = [];
      if (missingOutput) issues.push("output missing or unhealthy");
      if (missingSidecar) issues.push("sidecar missing or inconsistent");
      if (item.size_growth_over_5) issues.push("output grew more than 5%");
      if (recentRuntimeIssue) issues.push(`fresh runtime issue: ${[item.runtime_outcome_error_code, item.runtime_outcome_reason, item.runtime_outcome_status].filter(Boolean).join(" - ") || "failed/skipped"}`);
      consistencyIssues.forEach((issue) => issues.push(`consistency issue: ${issue}`));
      reviewFlags.forEach((flag) => issues.push(`review flag: ${flag}`));
      const level = missingOutput ? "broken-output" : issues.length ? "review" : "consistent-looking";
      const backendTrustState = completedRowLooksHealthy(item) ? "consistent-looking" : String(item.operator_trust_state || "").trim();
      const lines = [
        "Selected completed issue digest:",
        `Issue level: ${backendTrustState || level}`,
        `Primary issue(s): ${issues.length ? issues.join("; ") : "none reported by completed history"}`,
        `Proof to inspect: completed manifest row=${item.row_key || "not reported"}; output=${item.output_path || "not reported"}`,
        `Route/size proof: ${item.route_decision_summary || item.route_label || item.route || "not reported"}; ${item.size_delta_label || item.size_reduction_text || "size delta unknown"}`,
        `Runtime proof: ${item.runtime_outcome_status || "none"}${item.runtime_outcome_freshness_status ? ` (${item.runtime_outcome_freshness_status})` : ""}`,
      ];
      if (missingOutput) {
        lines.push("Safe next action: inspect Completed Manifest, Pending Publish, output folder, Run Logs, and Last Stderr before rerun.");
      } else if (missingSidecar || consistencyIssues.length) {
        lines.push("Safe next action: inspect sidecar/output consistency before cleanup, Plex library decisions, or rerun.");
      } else if (item.size_growth_over_5) {
        lines.push("Safe next action: compare route metadata and logs before accepting this output as intentional compatibility growth.");
      } else if (recentRuntimeIssue) {
        lines.push("Safe next action: use Completed Diagnostics Cross-Links before rerun; fresh runtime conflicts are not proof of success.");
      } else {
        lines.push("Safe next action: row is coherent in the loaded manifest; repair, reconcile, rerun, and cleanup remain backend-owned.");
      }
      return lines;
    }

    function completedRowCombinedReviewPlanLines(item) {
      if (!item) return [];
      const reviewFlags = Array.isArray(item.review_flags) ? item.review_flags.filter(Boolean) : [];
      const consistencyIssues = Array.isArray(item.consistency_issues) ? item.consistency_issues.filter(Boolean) : [];
      const runtimeStatus = String(item.runtime_outcome_status || "").toLowerCase();
      const runtimeFreshness = String(item.runtime_outcome_freshness_status || "").toLowerCase();
      const missingOutput = item.output_exists === false || String(item.output_health || "").toLowerCase().includes("missing");
      const missingSidecar = item.sidecar_exists === false || consistencyIssues.some((issue) => String(issue).toLowerCase().includes("sidecar"));
      const recentRuntimeIssue = runtimeFreshness === "fresh" && ["failed", "error", "skipped"].some((value) => runtimeStatus.includes(value));
      const signals = [];
      if (missingOutput) signals.push("missing output");
      if (missingSidecar) signals.push("sidecar/metadata mismatch");
      if (item.size_growth_over_5) signals.push("size growth over policy");
      if (recentRuntimeIssue) signals.push("fresh runtime failure");
      consistencyIssues.forEach((issue) => signals.push(`consistency ${issue}`));
      reviewFlags.forEach((flag) => signals.push(`review flag ${flag}`));
      const readFirst = ["Completed Manifest"];
      if (missingOutput || missingSidecar) readFirst.push("Pending Publish");
      if (missingOutput || missingSidecar || item.size_growth_over_5 || recentRuntimeIssue) readFirst.push("Last Stderr", "Run Logs");
      if (recentRuntimeIssue || missingOutput) readFirst.push("Latest Failure");
      const crossCheck = ["Output path", "Sidecar path", "Route/size proof"];
      if (missingOutput || missingSidecar) crossCheck.push("Pending Publish parked-output proof");
      if (item.size_growth_over_5) crossCheck.push("Settings size policy and encoder route");
      const lines = [
        "Combined completed-row review plan:",
        `Signal count: ${signals.length}`,
        `Signals: ${signals.length ? signals.join("; ") : "none reported by the selected completed row"}`,
        `Read first: ${[...new Set(readFirst)].join(" -> ")}`,
        `Cross-check: ${[...new Set(crossCheck)].join(" -> ")}`,
      ];
      if (missingOutput || missingSidecar) {
        lines.push("Decision: do not treat this completed row as output proof until manifest, output, sidecar, and pending-publish evidence agree.");
      } else if (item.size_growth_over_5) {
        lines.push("Decision: require route/log explanation before accepting the larger output as intentional compatibility growth.");
      } else if (recentRuntimeIssue) {
        lines.push("Decision: fresh runtime failure evidence must be reconciled before rerun, cleanup, or Plex library decisions.");
      } else {
        lines.push("Decision: row is consistent-looking, but Completed remains historical proof rather than acceptance or cleanup authority.");
      }
      lines.push("Guardrail: this combined plan is read-only and cannot repair manifests, accept outputs, rerun, reconcile, publish, or delete files.");
      return lines;
    }

    function completedRealMediaTraceLines(item) {
      if (!item) return [];
      const routeEvidence = Array.isArray(item.route_evidence_lines) ? item.route_evidence_lines.filter(Boolean) : [];
      const audioPreview = Array.isArray(item.audio_decision_preview) ? item.audio_decision_preview.filter(Boolean) : [];
      const subtitlePreview = Array.isArray(item.subtitle_decision_preview) ? item.subtitle_decision_preview.filter(Boolean) : [];
      const outputProof = item.output_exists === false
        ? "missing output"
        : item.output_exists === true
          ? "output exists"
          : item.output_health || "output existence not reported";
      const lines = [
        "Real-media sample trace: Completed",
        `Trace key: source=${item.source_path || "not reported"}; output=${item.output_path || "not reported"}`,
        `Completed proof: ${outputProof}; sidecar=${item.sidecar_exists === false ? "missing" : item.sidecar_exists === true ? "present" : item.sidecar_path ? "reported" : "unknown"}; consistency=${item.consistency_status || "not reported"}`,
        `Route/size proof: ${item.route_decision_summary || item.route_label || item.route || "not reported"}; growth=${item.size_delta_label || item.size_reduction_text || "unknown"}`,
        "What this proves: the backend recorded a completed-history row and exposes output, sidecar, route, size, audio, and subtitle evidence if present.",
        "What remains unproven: final publish success when output is parked, Plex playback quality, and any manual operator acceptance decision.",
      ];
      if (routeEvidence.length) {
        lines.push("Route evidence to compare with Queue and logs:");
        routeEvidence.slice(0, 6).forEach((line) => lines.push(`  ${line}`));
      }
      if (audioPreview.length || subtitlePreview.length) {
        lines.push("Audio/subtitle proof to compare with settings and logs:");
        audioPreview.slice(0, 4).forEach((line) => lines.push(`  audio: ${line}`));
        subtitlePreview.slice(0, 4).forEach((line) => lines.push(`  subtitle: ${line}`));
      }
      if (item.size_growth_over_5) {
        lines.push("Size boundary: output growth above +5% needs route/log explanation before accepting the result.");
      }
      lines.push("Next evidence stop: check Pending Publish if output is parked or missing; read Diagnostics Last Stderr/Run Logs if route, subtitle, audio, or size evidence is surprising.");
      lines.push("Mutation guardrail: this trace is read-only and cannot accept, delete, rerun, reconcile, drain, rewrite manifests, or mutate files.");
      return lines;
    }

    function completedRowTrustSummaryLines(item) {
      if (!item || typeof diagnosticsBridgeRowTrustLines !== "function") return [];
      const reviewFlags = Array.isArray(item.review_flags) ? item.review_flags.filter(Boolean) : [];
      const consistencyIssues = Array.isArray(item.consistency_issues) ? item.consistency_issues.filter(Boolean) : [];
      const runtimeStatus = String(item.runtime_outcome_status || "").toLowerCase();
      const runtimeFreshness = String(item.runtime_outcome_freshness_status || "").toLowerCase();
      const missingOutput = item.output_exists === false || String(item.output_health || "").toLowerCase().includes("missing");
      const missingSidecar = item.sidecar_exists === false || consistencyIssues.some((issue) => String(issue).toLowerCase().includes("sidecar"));
      const recentRuntimeIssue = runtimeFreshness === "fresh" && ["failed", "error", "skipped"].some((value) => runtimeStatus.includes(value));
      const backendTrustState = String(item.operator_trust_state || "").trim();
      const trustState = backendTrustState || (missingOutput
        ? "broken-output"
        : missingSidecar || item.size_growth_over_5 || recentRuntimeIssue || reviewFlags.length || consistencyIssues.length
          ? "review-before-rerun-or-cleanup"
          : "consistent-looking");
      const concern = item.primary_concern || (missingOutput
        ? "completed manifest row points to a missing/unhealthy output"
        : missingSidecar
          ? "sidecar is missing or inconsistent with output"
          : item.size_growth_over_5
            ? "output grew more than size policy threshold"
            : recentRuntimeIssue
              ? [item.runtime_outcome_status, item.runtime_outcome_error_code, item.runtime_outcome_reason].filter(Boolean).join(" - ") || "fresh runtime issue"
              : consistencyIssues.length
                ? consistencyIssues.join(", ")
                : reviewFlags.length
                  ? reviewFlags.join(", ")
                  : "row has no output/sidecar blocker in the loaded completed manifest");
      const proofSummary = Array.isArray(item.proof_summary) ? item.proof_summary.filter(Boolean) : [];
      return diagnosticsBridgeRowTrustLines("Completed selected row", completedDiagnosticsActionsForRow(item), {
        trustState,
        primaryConcern: concern,
        evidence: proofSummary.length ? proofSummary : [
          item.output_health || item.output_exists === false ? `output=${item.output_health || "missing"}` : "",
          item.consistency_status ? `consistency=${item.consistency_status}` : "",
          item.size_delta_label || item.size_reduction_text ? `size=${item.size_delta_label || item.size_reduction_text}` : "",
          item.output_path ? `output_path=${item.output_path}` : "",
          item.runtime_outcome_status || item.runtime_outcome_reason ? `runtime=${[item.runtime_outcome_status, item.runtime_outcome_error_code, item.runtime_outcome_reason].filter(Boolean).join(" - ")}` : "",
        ],
        safeAction: item.safe_next_action || (missingOutput || missingSidecar || recentRuntimeIssue ? "inspect Completed Manifest, Pending Publish, Run Logs, and Last Stderr before rerun or cleanup." : "treat the row as historical proof only after output/sidecar and route evidence agree."),
        unsafeAction: item.unsafe_if_ignored || "delete outputs, rerun sources, repair manifests, or reconcile sidecars from this page.",
        owningPages: "Completed owns output proof; Pending Publish owns parked outputs; Queue owns future processing; Diagnostics owns artifact/log evidence.",
      });
    }

    function completedSampleValidationComparisonLines(item) {
      const context = window.mediaPipelineLastCrossPageContext || {};
      const log = context.sampleValidation || {};
      const rows = typeof window.sampleValidationRecordComparisonRowsForPaths === "function"
        ? window.sampleValidationRecordComparisonRowsForPaths(
          log,
          [
            completedProofCompletedSourcePath(item),
            completedProofCompletedOutputPath(item),
            item?.runtime_outcome_output_path,
            item?.output_file,
          ],
          item?.lookup_title || item?.output_file || "",
        )
        : [];
      const current = rows.filter((row) => row.current_status === "current").length;
      const stale = rows.filter((row) => row.current_status === "stale").length;
      const review = rows.filter((row) => ["review", "not checked", "unknown"].includes(row.current_status)).length;
      const accepted = rows.filter((row) => row.operator_decision === "accepted").length;
      const lines = [
        "Sample Validation comparison for selected Completed row:",
        `Matching evidence records: ${rows.length}; accepted=${accepted}; current=${current}; stale=${stale}; review/not-checked=${review}.`,
        `Selected source: ${completedProofCompletedSourcePath(item) || "unknown"}`,
        `Selected output: ${completedProofCompletedOutputPath(item) || "unknown"}`,
      ];
      if (!rows.length) {
        lines.push(
          "No matching Sample Validation record is loaded for this Completed source/output.",
          "Next action: use Home > Sample Validation > Preview Record after Completed, Pending Publish, Diagnostics, playback, subtitle, audio, and size proof agree."
        );
      } else {
        rows.slice(0, 4).forEach((row) => {
          const gaps = Array.isArray(row.missing_current_evidence) && row.missing_current_evidence.length
            ? ` gaps=${row.missing_current_evidence.join("; ")}`
            : " gaps=none";
          lines.push(`- ${row.created_at || "unknown time"} ${row.operator_decision || "unknown decision"} category=${row.sample_category || "general"} proof=${row.proof_strength || "unknown"} match=${row.match_strength} fields=${(row.match_fields || []).join(",") || "unknown"} current=${row.current_status || "not checked"}${gaps}`);
        });
        lines.push("Next action: if the latest matching record is stale/review/not-checked, preview a new evidence note before trusting this Completed output as a WebView pilot result.");
      }
      lines.push(
        "Post-run capture: Preview Record now includes a copyable route/output/log/publish/subtitle/audio/size checklist for this sample.",
        "Mutation guardrail: this comparison is read-only and cannot append Sample Validation records, accept output, rerun, drain, publish, rewrite manifests/sidecars, save settings, rename, or touch media."
      );
      return lines;
    }

    return {
      completedIntegrityStatus,
      completedIntegrityLines,
      renderCompletedIntegrity,
      completedWorkflowStatus,
      completedWorkflowLines,
      renderCompletedWorkflow,
      completedReviewRowReasons,
      completedReviewRows,
      completedReviewStatus,
      completedReviewBoardLines,
      completedReviewDigestStatus,
      completedReviewDigestAction,
      completedTableRowStatus,
      completedInvestigationFilterLabel,
      completedMatchesInvestigationFilter,
      completedFocusedInvestigationLabels,
      completedFilterVisibilityLines,
      completedSelectedQuickSignalLines,
      completedInvestigationSignalLines,
      renderCompletedReviewDigest,
      renderCompletedReviewBoard,
      completedSizeReviewRows,
      completedSizeReviewStatus,
      completedSizeReviewAction,
      completedSizeReviewLines,
      renderCompletedSizeReview,
      completedSizeEvidencePostureStatus,
      completedSizeEvidenceRows,
      completedSizeEvidenceStatus,
      completedSizeEvidenceSummaryLines,
      completedSizeEvidenceDetailLines,
      renderCompletedSizeEvidence,
      completedBreakdownStatus,
      completedBreakdownLines,
      renderCompletedBreakdown,
      completedRuntimeStatus,
      completedRuntimeLines,
      renderCompletedRuntime,
      completedConsistencyStatus,
      completedConsistencyLines,
      renderCompletedConsistency,
      completedValidationStatus,
      completedValidationChecklistLines,
      renderCompletedValidation,
      completedRowReviewChecklistLines,
      completedSelectedAtAGlanceState,
      completedSelectedAtAGlanceStatus,
      completedSelectedAtAGlanceLines,
      renderCompletedSelectedAtAGlance,
      completedRowIssueDigestLines,
      completedRowCombinedReviewPlanLines,
      completedRealMediaTraceLines,
      completedRowTrustSummaryLines,
      completedSampleValidationComparisonLines,
    };
  }

  window.__completedViewReviewModule = {
    createCompletedReviewModule,
  };
})();
