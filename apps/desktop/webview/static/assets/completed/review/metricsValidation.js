(function () {
  function createCompletedReviewMetricsValidationModule(deps = {}) {
    const {
      appendCells, byId, captureSelectionScroll, clearRows, completedFormatCounts,
      completedFreshnessLine, completedHasSmallHealthySizeDelta, completedManifestIsAged,
      completedPendingProofIsExactPathSignal, completedProofCompletedOutputPath,
      completedProofCompletedSourcePath, completedProofRowLabel, completedSizeDeltaPercent,
      completedSizeReviewRows, makeRowSelectable, renderCompletedDetail, renderCompletedProofStrip,
      renderCompletedReviewDigest, restoreSelectionScroll, setText, state, updateTableStatusLegend,
      readOnlyBoundary = "Mutation guardrail: read-only evidence; backend routes own output and manifest changes.",
    } = deps;
    const COMPLETED_READ_ONLY_BOUNDARY = readOnlyBoundary;
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
      lines.push(COMPLETED_READ_ONLY_BOUNDARY);
      return lines;
    }

    function completedSizeEvidenceDetailLines(item) {
      if (!item) {
        return [
          "Size growth evidence handoff:",
          "Select a checkpoint row to see proof-order detail.",
          COMPLETED_READ_ONLY_BOUNDARY,
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
      const scrollSnapshot = captureCompletedReviewSelectionScroll();
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
        restoreCompletedReviewSelectionScroll(scrollSnapshot);
        return;
      }
      renderCompletedSizeEvidence(state.lastCompletedPayload, state.lastCompletedRows, state.lastCompletedPendingProofRows);
      restoreCompletedReviewSelectionScroll(scrollSnapshot);
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
          COMPLETED_READ_ONLY_BOUNDARY,
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
      const status = completedValidationStatus(completed || {}, rowList);
      const lines = completedValidationChecklistLines(completed || {}, rowList);
      setText("completed-validation-status", status);
      renderCompletedProofStrip("completed-validation-strip", status, lines);
      setText("completed-validation", lines.join("\n"));
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
          guardrail: COMPLETED_READ_ONLY_BOUNDARY,
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
      lines.push(COMPLETED_READ_ONLY_BOUNDARY);
      return lines;
    }

    return {
      completedSizeEvidencePostureStatus, completedSizeEvidenceRows, completedSizeEvidenceStatus,
      completedSizeEvidenceSummaryLines, completedSizeEvidenceDetailLines, selectedCompletedSizeEvidenceRow,
      selectCompletedSizeEvidenceRow, renderCompletedSizeEvidence, completedValidationStatePayload,
      completedValidationStatusLabel, completedValidationProofLabel, completedValidationStatus,
      completedValidationChecklistLines, renderCompletedValidation, completedRowReviewChecklistLines,    };
  }

  window.__completedReviewMetricsValidationModule = {
    createCompletedReviewMetricsValidationModule,
  };
})();
