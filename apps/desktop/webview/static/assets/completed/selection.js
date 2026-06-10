// completed/selection.js
// Split child of completedView.js. Owns selected-row lookup and read-only detail rendering.

(function () {
  "use strict";

  function noop() {}
  function emptyLines() { return []; }

  function normalizeDeps(deps = {}) {
    return {
      completedDiagnosticsActionsForRow: typeof deps.completedDiagnosticsActionsForRow === "function" ? deps.completedDiagnosticsActionsForRow : emptyLines,
      completedInvestigationSignalLines: typeof deps.completedInvestigationSignalLines === "function" ? deps.completedInvestigationSignalLines : emptyLines,
      completedRealMediaTraceLines: typeof deps.completedRealMediaTraceLines === "function" ? deps.completedRealMediaTraceLines : emptyLines,
      completedRowCombinedReviewPlanLines: typeof deps.completedRowCombinedReviewPlanLines === "function" ? deps.completedRowCombinedReviewPlanLines : emptyLines,
      completedRowIssueDigestLines: typeof deps.completedRowIssueDigestLines === "function" ? deps.completedRowIssueDigestLines : emptyLines,
      completedRowReviewChecklistLines: typeof deps.completedRowReviewChecklistLines === "function" ? deps.completedRowReviewChecklistLines : emptyLines,
      completedRowTrustSummaryLines: typeof deps.completedRowTrustSummaryLines === "function" ? deps.completedRowTrustSummaryLines : emptyLines,
      completedSampleValidationComparisonLines: typeof deps.completedSampleValidationComparisonLines === "function" ? deps.completedSampleValidationComparisonLines : emptyLines,
      completedSelectedAtAGlanceLines: typeof deps.completedSelectedAtAGlanceLines === "function" ? deps.completedSelectedAtAGlanceLines : emptyLines,
      completedSelectedOpenTargetLines: typeof deps.completedSelectedOpenTargetLines === "function" ? deps.completedSelectedOpenTargetLines : emptyLines,
      completedSelectedQuickSignalLines: typeof deps.completedSelectedQuickSignalLines === "function" ? deps.completedSelectedQuickSignalLines : emptyLines,
      diagnosticsBridgeHandoffLines: typeof deps.diagnosticsBridgeHandoffLines === "function" ? deps.diagnosticsBridgeHandoffLines : null,
      renderCompletedDiagnosticsLinks: typeof deps.renderCompletedDiagnosticsLinks === "function" ? deps.renderCompletedDiagnosticsLinks : noop,
      renderCompletedPromotionActions: typeof deps.renderCompletedPromotionActions === "function" ? deps.renderCompletedPromotionActions : noop,
      renderCompletedRows: typeof deps.renderCompletedRows === "function" ? deps.renderCompletedRows : noop,
      renderCompletedSelectedAtAGlance: typeof deps.renderCompletedSelectedAtAGlance === "function" ? deps.renderCompletedSelectedAtAGlance : noop,
      selectedRowDetailDrawerLines: typeof deps.selectedRowDetailDrawerLines === "function" ? deps.selectedRowDetailDrawerLines : null,
      setText: typeof deps.setText === "function" ? deps.setText : noop,
      state: deps.state && typeof deps.state === "object" ? deps.state : {},
    };
  }

  function createCompletedSelectionModule(deps = {}) {
    const ctx = normalizeDeps(deps);

    function getSelectedCompletedRow() {
      const rows = Array.isArray(ctx.state.lastCompletedRows) ? ctx.state.lastCompletedRows : [];
      return rows.find((row) => row?.row_key && row.row_key === ctx.state.selectedCompletedRowKey) || rows[0] || null;
    }

    function getLastCompletedPayload() {
      return ctx.state.lastCompletedPayload;
    }

    function getLastCompletedRows() {
      return Array.isArray(ctx.state.lastCompletedRows) ? ctx.state.lastCompletedRows.slice() : [];
    }

    function getLastCompletedPendingProofRows() {
      return Array.isArray(ctx.state.lastCompletedPendingProofRows) ? ctx.state.lastCompletedPendingProofRows.slice() : [];
    }

    function captureCompletedSelectionScroll() {
      return window.mediaPipelineDom?.captureScrollablePositions?.() || null;
    }

    function restoreCompletedSelectionScroll(snapshot) {
      if (snapshot) window.mediaPipelineDom?.restoreScrollablePositions?.(snapshot);
    }

    function selectCompletedRow(item) {
      const scrollSnapshot = captureCompletedSelectionScroll();
      if (item?.row_key) ctx.state.selectedCompletedRowKey = item.row_key;
      ctx.renderCompletedRows();
      renderCompletedDetail(item || getSelectedCompletedRow());
      restoreCompletedSelectionScroll(scrollSnapshot);
    }

    function renderCompletedDetail(item) {
      ctx.renderCompletedSelectedAtAGlance(item || null);
      const guardrail = "Mutation guardrail: selected-row detail is read-only and cannot accept outputs, repair manifests, rerun jobs, reconcile sidecars, publish, or delete files.";
      if (!item) {
        const bodyLines = ctx.completedRowReviewChecklistLines(null);
        const detailLines = ctx.selectedRowDetailDrawerLines
          ? ctx.selectedRowDetailDrawerLines({
            title: "Completed selected-row detail",
            summaryLines: ctx.completedSelectedAtAGlanceLines(null),
            bodyLines,
            guardrail,
          })
          : bodyLines;
        ctx.setText("completed-detail", detailLines.join("\n"));
        ctx.setText("completed-open-status", "Select a completed row to open a backend-selected location.");
        ctx.renderCompletedDiagnosticsLinks(null);
        ctx.renderCompletedPromotionActions(null);
        return;
      }
      const audioPreview = Array.isArray(item.audio_decision_preview) ? item.audio_decision_preview : [];
      const subtitlePreview = Array.isArray(item.subtitle_decision_preview) ? item.subtitle_decision_preview : [];
      const reviewFlags = Array.isArray(item.review_flags) ? item.review_flags.join(", ") : "";
      const routeEvidence = Array.isArray(item.route_evidence_lines) ? item.route_evidence_lines : [];
      const proofSummary = Array.isArray(item.proof_summary) ? item.proof_summary : [];
      const diagnosticTargets = Array.isArray(item.recommended_diagnostics_targets) ? item.recommended_diagnostics_targets.join(", ") : "";
      const handoffLines = ctx.diagnosticsBridgeHandoffLines
        ? ctx.diagnosticsBridgeHandoffLines("Completed selected row", ctx.completedDiagnosticsActionsForRow(item), {
          evidence: [
            item.output_health || item.output_exists === false ? `output=${item.output_health || "missing"}` : "",
            item.consistency_status ? `consistency=${item.consistency_status}` : "",
            item.size_delta_label ? `size=${item.size_delta_label}` : "",
            item.runtime_outcome_status || item.runtime_outcome_reason ? `runtime=${[item.runtime_outcome_status, item.runtime_outcome_error_code, item.runtime_outcome_reason].filter(Boolean).join(" - ")}` : "",
          ],
          safeAction: "compare Completed Manifest, output/sidecar state, Pending Publish, Run Logs, and Last Stderr before rerun or cleanup.",
        })
        : [];
      const detail = [
        ...ctx.completedSelectedQuickSignalLines(item),
        "",
        ...ctx.completedRowReviewChecklistLines(item),
        "",
        ...ctx.completedRowIssueDigestLines(item),
        "",
        ...ctx.completedRowCombinedReviewPlanLines(item),
        "",
        ...ctx.completedInvestigationSignalLines(item),
        "",
        ...ctx.completedRealMediaTraceLines(item),
        "",
        ...ctx.completedRowTrustSummaryLines(item),
        "",
        ...ctx.completedSampleValidationComparisonLines(item),
        "",
        ...handoffLines,
        "",
        ...ctx.completedSelectedOpenTargetLines(item),
        "",
        item.row_key ? `Row key: ${item.row_key}` : "",
        `Completed: ${item.completed_at || ""}`,
        item.operator_trust_state ? `Backend trust state: ${item.operator_trust_state}` : "",
        item.primary_concern ? `Primary concern: ${item.primary_concern}` : "",
        item.safe_next_action ? `Safe next action: ${item.safe_next_action}` : "",
        item.unsafe_if_ignored ? `Unsafe if ignored: ${item.unsafe_if_ignored}` : "",
        proofSummary.length ? "Backend proof summary:" : "",
        ...proofSummary.map((line) => `  ${line}`),
        diagnosticTargets ? `Recommended diagnostics targets: ${diagnosticTargets}` : "",
        item.operator_status ? `Operator status: ${item.operator_status}` : "",
        item.operator_guidance ? `Next step: ${item.operator_guidance}` : "",
        reviewFlags ? `Review flags: ${reviewFlags}` : "",
        item.consistency_status ? `Consistency: ${item.consistency_status}` : "",
        item.consistency_guidance ? `Consistency next step: ${item.consistency_guidance}` : "",
        Array.isArray(item.consistency_issues) && item.consistency_issues.length ? `Consistency issues: ${item.consistency_issues.join(", ")}` : "",
        item.validation_status_state ? `Validation state: ${item.validation_status_state}` : "",
        item.validation_failure_reason ? `Validation proof gap: ${item.validation_failure_reason}` : "",
        item.validation_probe_ok === true ? "Probe proof: passed" : item.validation_probe_ok === false ? "Probe proof: failed" : "Probe proof: not reported",
        item.validation_hash_ok === true ? "Hash proof: passed" : item.validation_hash_ok === false ? "Hash proof: failed" : "Hash proof: not reported",
        item.validation_playback_required === true ? "Playback required: yes" : item.validation_playback_required === false ? "Playback required: no" : "Playback required: not reported",
        Array.isArray(item.validation_unavailable_reasons) && item.validation_unavailable_reasons.length ? `Validation unavailable proof: ${item.validation_unavailable_reasons.join(", ")}` : "",
        item.validation_safe_next_action ? `Validation next step: ${item.validation_safe_next_action}` : "",
        item.expected_sidecar_path ? `Expected sidecar: ${item.expected_sidecar_path}` : "",
        item.sidecar_exists === false ? "Sidecar: missing" : item.sidecar_exists === true ? "Sidecar: present" : "",
        item.route_decision_summary ? `Route decision: ${item.route_decision_summary}` : "",
        routeEvidence.length ? "Route evidence:" : "",
        ...routeEvidence.map((line) => `  ${line}`),
        item.runtime_outcome_status ? `Last runtime outcome: ${item.runtime_outcome_status}` : "",
        item.runtime_outcome_event_type ? `Runtime event type: ${item.runtime_outcome_event_type}` : "",
        item.runtime_outcome_at ? `Runtime event at: ${item.runtime_outcome_at}` : "",
        item.runtime_outcome_age_text || item.runtime_outcome_freshness_status ? `Runtime history age: ${item.runtime_outcome_age_text || "unknown"} (${item.runtime_outcome_freshness_status || "unknown"})` : "",
        item.runtime_outcome_stage || item.runtime_outcome_route ? `Runtime stage/route: ${item.runtime_outcome_stage || "unknown"} / ${item.runtime_outcome_route || "unknown"}` : "",
        item.runtime_outcome_error_code ? `Runtime error code: ${item.runtime_outcome_error_code}` : "",
        item.runtime_outcome_reason ? `Runtime reason: ${item.runtime_outcome_reason}` : "",
        item.runtime_outcome_publish_state || item.runtime_outcome_publish_mode ? `Runtime publish: ${item.runtime_outcome_publish_state || "unknown"} / ${item.runtime_outcome_publish_mode || "unknown"}` : "",
        item.runtime_outcome_output_path ? `Runtime output: ${item.runtime_outcome_output_path}` : "",
        item.runtime_outcome_match ? `Runtime match: ${item.runtime_outcome_match}` : "",
        `Route: ${item.route_label || item.route || ""}`,
        item.route_reason || item.route_reason_code ? `Route reason: ${[item.route_reason_code, item.route_reason].filter(Boolean).join(" - ")}` : "",
        `Publish: ${item.publish || ""}`,
        item.final_library_promotion_status_label ? `Final library promotion: ${item.final_library_promotion_status_label}` : "",
        item.final_library_rule_label ? `Final library rule: ${item.final_library_rule_label}` : "",
        item.final_library_destination_path ? `Final library destination: ${item.final_library_destination_path}` : "",
        item.last_promotion_run_id ? `Last promotion run: ${item.last_promotion_run_id}` : "",
        item.last_promotion_completed_at ? `Last promotion completed: ${item.last_promotion_completed_at}` : "",
        item.promotion_error ? `Promotion error: ${item.promotion_error}` : "",
        `Media: ${item.media_type || ""}`,
        `Title: ${item.lookup_title || item.output_file || ""}`,
        `Output: ${item.output_path || ""}`,
        `Source: ${item.source_path || ""}`,
        `Sidecar: ${item.sidecar_path || ""}`,
        `Size: ${item.size_reduction_text || item.output_size_text || ""}`,
        `Output growth: ${item.size_delta_label || "unknown"}`,
        item.size_growth_over_5 ? "Size review: output is more than 5% larger than source." : "",
        `Encoder: ${item.encoder || item.encoder_kind || ""}`,
        `Audio decisions: ${item.audio_decision_count || 0}`,
        ...audioPreview.map((line) => `  ${line}`),
        `Subtitle decisions: ${item.subtitle_decision_count || 0}`,
        ...subtitlePreview.map((line) => `  ${line}`),
        `Health: ${item.output_health || (item.output_exists === false ? "missing output" : "ok")}`,
      ].filter((line) => line !== "");
      const detailLines = ctx.selectedRowDetailDrawerLines
        ? ctx.selectedRowDetailDrawerLines({
          title: "Completed selected-row detail",
          summaryLines: ctx.completedSelectedAtAGlanceLines(item),
          bodyLines: detail,
          guardrail,
        })
        : detail;
      ctx.setText("completed-detail", detailLines.join("\n"));
      ctx.setText("completed-open-status", "Selected completed row. Open commands use backend-selected paths from the manifest.");
      ctx.renderCompletedPromotionActions(item);
      ctx.renderCompletedDiagnosticsLinks(item);
    }

    return {
      getLastCompletedPayload,
      getLastCompletedPendingProofRows,
      getLastCompletedRows,
      getSelectedCompletedRow,
      renderCompletedDetail,
      selectCompletedRow,
    };
  }

  window.__completedViewSelectionModule = {
    createCompletedSelectionModule,
  };
})();
