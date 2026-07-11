(function () {
  function createCompletedReviewSelectedEvidenceModule(deps = {}) {
    const {
      completedDiagnosticsActionsForRow, completedProofCompletedOutputPath,
      completedProofCompletedSourcePath, completedReviewFlagIsBenign, completedRowLooksHealthy,
      diagnosticsBridgeRowTrustLines, readOnlyBoundary = "Mutation guardrail: read-only evidence; backend routes own output and manifest changes.",
    } = deps;
    const COMPLETED_READ_ONLY_BOUNDARY = readOnlyBoundary;
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
      lines.push(COMPLETED_READ_ONLY_BOUNDARY);
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
        COMPLETED_READ_ONLY_BOUNDARY
      );
      return lines;
    }

    return {
      completedRowIssueDigestLines, completedRowCombinedReviewPlanLines, completedRealMediaTraceLines,
      completedRowTrustSummaryLines, completedSampleValidationComparisonLines,    };
  }

  window.__completedReviewSelectedEvidenceModule = {
    createCompletedReviewSelectedEvidenceModule,
  };
})();
