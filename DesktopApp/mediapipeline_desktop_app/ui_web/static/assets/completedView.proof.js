(function () {
  function createCompletedProofModule(deps = {}) {
    const {
      appendCells,
      byId,
      clearRows,
      completedAcceptanceCommandEntries,
      completedAcceptanceIssueLevel,
      completedAcceptancePostureStatus,
      completedAcceptanceProofRowsForItem,
      completedAcceptanceRows,
      completedPendingProofIsExactPathSignal,
      completedPendingProofIsFinalPlacementReviewSignal,
      completedProofCompletedOutputPath,
      completedProofCompletedSourcePath,
      completedProofDrainSummaryPayload,
      completedProofRowKey,
      completedProofRowLabel,
      completedProofRowMissingOutput,
      completedSampleValidationComparisonLines,
      getSelectedCompletedRow,
      makeRowSelectable,
      setText,
      state,
      updateTableStatusLegend,
    } = deps;

    function completedRealMediaProofSelectedOrFirst(rows) {
      const selected = getSelectedCompletedRow();
      if (selected) return selected;
      const rowList = Array.isArray(rows) ? rows : [];
      return rowList.find((row) => completedProofRowMissingOutput(row) || row?.size_growth_over_5 || row?.sidecar_exists === false)
        || rowList[0]
        || null;
    }

    function completedPolicyAlignmentPayload() {
      const context = window.mediaPipelineLastCrossPageContext || {};
      const log = context.sampleValidation && typeof context.sampleValidation === "object" ? context.sampleValidation : {};
      return log.policy_alignment && typeof log.policy_alignment === "object" ? log.policy_alignment : {};
    }

    function completedPolicyAlignmentRows() {
      const payload = completedPolicyAlignmentPayload();
      return Array.isArray(payload.rows) ? payload.rows : [];
    }

    function completedPolicyOutputText(item = null) {
      const row = item && typeof item === "object" ? item : {};
      const fields = [
        row.route,
        row.route_label,
        row.route_reason,
        row.route_reason_code,
        row.route_decision_summary,
        row.encoder,
        row.encoder_kind,
        row.publish,
        row.output_health,
        row.operator_status,
        row.operator_guidance,
        row.size_delta_label,
        row.size_reduction_text,
        row.size_policy_mode,
        row.size_policy_status,
        row.size_policy_limit_label,
        row.size_policy_message,
        row.audio_summary,
        row.subtitle_summary,
        row.runtime_outcome_status,
        row.runtime_outcome_reason,
        row.runtime_outcome_publish_state,
        row.runtime_outcome_publish_mode,
        row.output_file,
        row.output_path,
        row.source_path,
      ];
      if (Array.isArray(row.route_evidence_lines)) fields.push(...row.route_evidence_lines);
      if (Array.isArray(row.audio_decision_preview)) fields.push(...row.audio_decision_preview);
      if (Array.isArray(row.subtitle_decision_preview)) fields.push(...row.subtitle_decision_preview);
      if (Array.isArray(row.proof_summary)) fields.push(...row.proof_summary);
      return fields.filter(Boolean).map((value) => String(value)).join(" ").toLowerCase();
    }

    function completedPolicyOutputCategorySignal(item = null, categoryKey = "", proofRows = []) {
      const text = completedPolicyOutputText(item);
      const category = String(categoryKey || "").trim().toLowerCase();
      const hasAny = (tokens) => tokens.some((token) => text.includes(token));
      if (category === "h264-remux-safe") {
        if (hasAny(["h.264", "h264", "direct-stream", "direct stream", "remux", "copy", "encoder=copy"])) return "completed-route-signal";
        return "not-visible";
      }
      if (category === "subtitle-srt-generation") {
        if (Number(item?.subtitle_decision_count || 0) > 0 || hasAny(["subtitle", "srt", "tx3g", "mov_text", "mov text", "bdpgs", "pgs", "ass", "ssa"])) return "completed-media-signal";
        return "not-visible";
      }
      if (category === "audio-routing") {
        if (Number(item?.audio_decision_count || 0) > 0 || hasAny(["audio", "aac", "ac3", "eac3", "dts", "truehd", "flac", "channel", "default track", "passthrough", "downmix"])) return "completed-media-signal";
        return "not-visible";
      }
      if (category === "encode-size-policy") {
        if (item?.size_policy_available || hasAny(["size policy", "size_policy", "growth", "encode", "transcode", "remux", "copy", "h265", "hevc", "x264", "x265", "nvenc", "qsv", "amf"])) return "completed-size-signal";
        return "not-visible";
      }
      if (category === "deferred-publish") {
        const exact = (Array.isArray(proofRows) ? proofRows : []).some((row) => completedPendingProofIsExactPathSignal(row?.signal));
        if (exact || hasAny(["deferred", "pending", "publish", "park", "drain", "outsource", "final destination"])) return "completed-placement-signal";
        return "not-visible";
      }
      return "not-visible";
    }

    function completedPolicyAlignmentOutputEvidence(item = null, proofRows = []) {
      const payload = completedPolicyAlignmentPayload();
      const policyRows = completedPolicyAlignmentRows();
      const requiredRows = policyRows.filter((row) => row.required !== false);
      const missingOutput = completedProofRowMissingOutput(item);
      const blockedRows = requiredRows.filter((row) => ["blocked", "missing"].includes(String(row.status || "").toLowerCase()));
      const reviewRows = requiredRows.filter((row) => String(row.status || "").toLowerCase() === "review");
      const matchedRows = policyRows.filter((row) => completedPolicyOutputCategorySignal(item, row.category_key, proofRows) !== "not-visible");
      const unmatchedRequired = requiredRows.filter((row) => {
        const status = String(row.status || "").toLowerCase();
        return !["blocked", "missing"].includes(status) && completedPolicyOutputCategorySignal(item, row.category_key, proofRows) === "not-visible";
      });
      const posture = missingOutput || blockedRows.length
        ? "Blocked review"
        : !policyRows.length || !item
          ? "No policy evidence"
          : reviewRows.length || unmatchedRequired.length
            ? "Review"
            : "Current proof";
      const evidence = [
        `policy=${payload.operator_status || "not loaded"}`,
        `required ready=${payload.required_ready_count || 0}/${payload.required_count || requiredRows.length}`,
        `completed category signals=${matchedRows.length}/${policyRows.length || 0}`,
        `unmatched required=${unmatchedRequired.length}`,
        `blocked policy rows=${blockedRows.length}`,
      ].join("; ");
      const action = missingOutput
        ? "Resolve missing output proof before treating completed media as policy-aligned."
        : blockedRows.length
          ? "Resolve blocked saved-policy rows before accepting this completed sample as proof."
          : !policyRows.length
            ? "Load Sample Validation policy alignment before using this Completed row as saved-policy proof."
            : reviewRows.length || unmatchedRequired.length
              ? "Read the category comparison rows; this completed row does not visibly prove every saved-policy category."
              : "Use this as supporting post-run evidence, then still confirm playback, subtitle, audio, size, and final placement manually.";
      const detail = [
        "Completed policy reconciliation:",
        `Policy alignment status: ${payload.operator_status || "not loaded"}`,
        `Completed output: ${completedProofCompletedOutputPath(item) || "unknown"}`,
        `Completed source: ${completedProofCompletedSourcePath(item) || "unknown"}`,
        `Route: ${item?.route_decision_summary || item?.route_label || item?.route || "unknown"}`,
        `Route reason: ${[item?.route_reason_code, item?.route_reason].filter(Boolean).join(" - ") || "unknown"}`,
        `Size policy: ${item?.size_policy_mode || "unknown"} ${item?.size_policy_limit_label || ""}; status=${item?.size_policy_status || "unknown"}`,
        `Audio/subtitle decision rows: ${item?.audio_decision_count || 0}/${item?.subtitle_decision_count || 0}`,
        `Matched policy categories: ${matchedRows.length}/${policyRows.length || 0}`,
        `Unmatched required policy categories: ${unmatchedRequired.length}`,
        "",
        "Category comparison rows:",
      ];
      if (policyRows.length) {
        policyRows.forEach((row) => {
          const signal = completedPolicyOutputCategorySignal(item, row.category_key, proofRows);
          detail.push(`- ${row.category || row.category_key || "Category"}: policy=${row.status || "unknown"}; required=${row.required === false ? "no" : "yes"}; completed signal=${signal}; evidence=${row.evidence || "not reported"}`);
        });
      } else {
        detail.push("- No saved policy-alignment rows loaded.");
      }
      if (unmatchedRequired.length) {
        detail.push("", "Unmatched required post-run categories:");
        unmatchedRequired.slice(0, 6).forEach((row) => detail.push(`- ${row.category || row.category_key || "Category"}: ${row.safe_next_action || "Confirm this category with Completed, Pending Publish, Diagnostics, and playback evidence."}`));
      }
      detail.push(
        "",
        "Post-run boundary: Completed can prove output-side evidence only from loaded metadata. It cannot prove Plex playback by itself, and missing visible tokens do not mean backend policy failed.",
        payload.guardrail || "Read-only real-media policy alignment. It cannot save settings, launch, append records, accept output, publish/drain, repair, rename, rewrite manifests, run FFmpeg, or touch media.",
      );
      return { posture, evidence, action, detail, payload, policyRows, matchedRows, unmatchedRequired };
    }

    function completedRealMediaProofRows(completed, rows, proofRows = state.lastCompletedPendingProofRows, pending = state.lastCompletedPendingPayload, commandEntries) {
      const payload = completed || {};
      const rowList = Array.isArray(rows) ? rows : [];
      const item = completedRealMediaProofSelectedOrFirst(rowList);
      const relevantProofRows = completedAcceptanceProofRowsForItem(item, proofRows);
      const blockedProofRows = relevantProofRows.filter((row) => row?.status === "blocked");
      const exactProofRows = relevantProofRows.filter((row) => completedPendingProofIsExactPathSignal(row?.signal));
      const sameLeafRows = relevantProofRows.filter((row) => row?.signal === "same-leaf-review");
      const drainSummary = completedProofDrainSummaryPayload(pending || {});
      const commands = completedAcceptanceCommandEntries(commandEntries);
      const commandIssues = commands.filter((entry) => !["ok", "info", "none"].includes(completedAcceptanceIssueLevel(entry)));
      const missingOutput = completedProofRowMissingOutput(item);
      const consistencyIssues = Array.isArray(item?.consistency_issues) ? item.consistency_issues.filter(Boolean) : [];
      const sidecarIssue = item?.sidecar_exists === false || consistencyIssues.some((issue) => String(issue || "").toLowerCase().includes("sidecar"));
      const routeText = item ? item.route_decision_summary || item.route_label || item.route || "unknown route" : "no completed row selected";
      const routeReason = item ? [item.route_reason_code, item.route_reason].filter(Boolean).join(" - ") || "not reported" : "not reported";
      const sizeText = item ? item.size_delta_label || item.size_reduction_text || "unknown" : "unknown";
      const audioCount = Number(item?.audio_decision_count || 0);
      const subtitleCount = Number(item?.subtitle_decision_count || 0);
      const runtimeStatus = String(item?.runtime_outcome_status || "").toLowerCase();
      const runtimeReview = runtimeStatus.includes("fail") || runtimeStatus.includes("error") || String(item?.runtime_outcome_freshness_status || "").toLowerCase() === "fresh";
      const policyOutput = completedPolicyAlignmentOutputEvidence(item, relevantProofRows);

      if (!rowList.length) {
        return [
          {
            key: "no-real-media-output-proof",
            checkpoint: "Real-media output proof",
            posture: payload.error ? "Blocked review" : "No history",
            evidence: payload.error ? `Completed history unavailable: ${payload.error}` : "No completed rows are loaded.",
            action: "Open Diagnostics > Completed Manifest, Run Logs, and Last Stderr before using WebView as real-media proof.",
            detail: [
              "Real-media output proof ladder:",
              "No selected or recent Completed row is available.",
              "This board is read-only and cannot accept, rerun, drain, publish, rewrite, delete, or touch media.",
            ],
          },
        ];
      }

      return [
        {
          key: "selected-completed-output",
          checkpoint: "Output and sidecar",
          posture: missingOutput || sidecarIssue ? "Blocked review" : "Current proof",
          evidence: `${completedProofRowLabel(item)}; output=${missingOutput ? "missing" : item?.output_health || "present/unknown"}; sidecar=${item?.sidecar_exists === false ? "missing" : sidecarIssue ? "review" : "present/unknown"}.`,
          action: missingOutput || sidecarIssue
            ? "Open Completed Manifest, output folder, sidecar, Run Logs, and Last Stderr before rerun or cleanup."
            : "Use output and sidecar proof as one part of the real-media evidence chain.",
          completedRow: item,
          detail: [
            `Output path: ${completedProofCompletedOutputPath(item) || "unknown"}`,
            `Source path: ${completedProofCompletedSourcePath(item) || "unknown"}`,
            `Sidecar path: ${item?.sidecar_path || item?.expected_sidecar_path || "unknown"}`,
            `Consistency: ${item?.consistency_status || "unknown"}`,
            `Consistency issues: ${consistencyIssues.join(", ") || "none loaded"}`,
          ],
        },
        {
          key: "launch-to-output-transition",
          checkpoint: "Launch-to-output transition",
          posture: missingOutput || runtimeReview || commandIssues.length ? "Review" : "Read-first",
          evidence: `pre-run=Launch intent/checklist; post-run=Completed/Pending/Diagnostics proof; completed source=${completedProofCompletedSourcePath(item) ? "present" : "missing"}; completed output=${completedProofCompletedOutputPath(item) ? "present" : "missing"}; runtime=${item?.runtime_outcome_status || "unknown"}; command issues=${commandIssues.length}.`,
          action: missingOutput || runtimeReview || commandIssues.length
            ? "Do not treat Launch intent as completion proof; compare command history, Completed row, Pending Publish, Run Logs, and Last Stderr before accepting or rerunning."
            : "Compare the Launch start decision/command context with this Completed row before recording accepted sample evidence.",
          completedRow: item,
          detail: [
            "Pre-run proof source: Launch real-media sample proof handoff and Launch sample execution checklist.",
            "Post-run proof source: Completed output/sidecar, Pending Publish parked/final placement, Diagnostics logs, and Home Sample Validation preview/append.",
            "Transition rule: Launch can prove intent before start; only Completed/Pending/Diagnostics/playback can prove a finished output.",
            `Selected source: ${completedProofCompletedSourcePath(item) || "unknown"}`,
            `Selected output: ${completedProofCompletedOutputPath(item) || "unknown"}`,
            `Runtime status: ${item?.runtime_outcome_status || "unknown"} (${item?.runtime_outcome_freshness_status || "unknown"})`,
            `Relevant Completed/Pending command entries: ${commands.length}`,
          ],
        },
        {
          key: "route-size-media-proof",
          checkpoint: "Route, size, and media decisions",
          posture: item?.size_growth_over_5 || item?.size_delta_percent === null || item?.size_delta_percent === undefined || routeText === "unknown route" ? "Review" : "Current proof",
          evidence: `Route=${routeText}; reason=${routeReason}; size=${sizeText}; encoder=${item?.encoder || item?.encoder_kind || "unknown"}; audio/subtitle decisions=${audioCount}/${subtitleCount}.`,
          action: item?.size_growth_over_5
            ? "Compare route reason, encoder, audio/subtitle decisions, Settings policy, and Last Stderr before accepting size growth."
            : "Confirm the route/size/media decision matches the intended Plex profile for this sample.",
          completedRow: item,
          detail: [
            "Plex compatibility proof needs more than output existence.",
            `Route evidence lines: ${Array.isArray(item?.route_evidence_lines) ? item.route_evidence_lines.length : 0}`,
            `Audio preview rows: ${Array.isArray(item?.audio_decision_preview) ? item.audio_decision_preview.length : 0}`,
            `Subtitle preview rows: ${Array.isArray(item?.subtitle_decision_preview) ? item.subtitle_decision_preview.length : 0}`,
          ],
        },
        {
          key: "completed-policy-reconciliation",
          checkpoint: "Saved policy reconciliation",
          posture: policyOutput.posture,
          evidence: policyOutput.evidence,
          action: policyOutput.action,
          completedRow: item,
          detail: policyOutput.detail,
        },
        {
          key: "pending-drain-proof",
          checkpoint: "Pending/drain proof",
          posture: blockedProofRows.length ? "Blocked review" : exactProofRows.length ? "Current proof" : sameLeafRows.length ? "Review" : "Read-first",
          evidence: `${relevantProofRows.length} related proof row(s); blocked=${blockedProofRows.length}; exact=${exactProofRows.length}; same-leaf=${sameLeafRows.length}; drain summary=${drainSummary.read_error ? "unreadable" : drainSummary.exists === false ? "not found" : "loaded/unknown"}.`,
          action: blockedProofRows.length
            ? "Do not rerun, delete, or drain until blocked pending/drain proof is explained."
            : exactProofRows.length
              ? "Use exact pending/drain proof as supporting evidence and still verify current output state."
              : "If output is missing, remember an empty Pending Publish view is not proof that publishing succeeded.",
          completedRow: item,
          detail: [
            "Proof order: Completed Manifest row -> exact output/source path -> current Pending Publish row -> durable drain summary -> Run Logs / Last Stderr.",
            "Same-leaf matches are duplicate-title hints only.",
            `Last drain summary status: ${drainSummary.read_error ? "unreadable" : drainSummary.exists === false ? "not found" : drainSummary.completed_at || drainSummary.started_at || "loaded without timestamp"}`,
          ],
        },
        {
          key: "diagnostics-and-runtime-proof",
          checkpoint: "Diagnostics and runtime",
          posture: runtimeReview || commandIssues.length ? "Review" : "Read-first",
          evidence: `Runtime=${item?.runtime_outcome_status || "unknown"} (${item?.runtime_outcome_freshness_status || "unknown"}); recent command issues=${commandIssues.length}.`,
          action: runtimeReview || commandIssues.length
            ? "Read command detail, Completed Manifest, Run Logs, Last Stderr, and Latest Failure before trusting this output."
            : "Use diagnostics as supporting proof; table state alone is not completion proof.",
          completedRow: item,
          detail: [
            `Runtime stage/route: ${item?.runtime_outcome_stage || "unknown"} / ${item?.runtime_outcome_route || "unknown"}`,
            `Runtime reason: ${item?.runtime_outcome_reason || "not reported"}`,
            `Completed/Pending command entries: ${commands.length}`,
          ],
        },
        {
          key: "sample-validation-handoff",
          checkpoint: "Sample validation handoff",
          posture: missingOutput || !completedProofCompletedSourcePath(item) || !completedProofCompletedOutputPath(item) ? "Review" : "Read-first",
          evidence: `source=${completedProofCompletedSourcePath(item) ? "present" : "missing"}; output=${completedProofCompletedOutputPath(item) ? "present" : "missing"}; exact pending/drain proof=${exactProofRows.length}; diagnostics commands=${commands.length}.`,
          action: missingOutput
            ? "Do not append an accepted sample validation record until current Completed, Pending Publish, Diagnostics, and playback evidence explain the missing output."
            : "Use Home > Sample Validation Record after comparing current Queue, Completed, Pending Publish, Diagnostics, Settings, and playback evidence.",
          completedRow: item,
          detail: [
            "Sample Validation handoff is evidence-only.",
            "Suggested record source_path is the selected Completed source path.",
            "Suggested record output_path is the selected Completed output path.",
            "Use Preview Record first; append only after current backend evidence and manual playback/subtitle/audio/size checks agree.",
            "Home Sample Validation can write JSONL evidence notes only; it does not accept output, clear failures, drain pending publish, launch work, or mutate media.",
          ],
        },
        {
          key: "operator-trust-boundary",
          checkpoint: "Operator trust boundary",
          posture: "Read-only",
          evidence: "This proof ladder correlates existing backend payloads only.",
          action: "Treat this as decision support; backend commands remain the only source of mutation.",
          completedRow: item,
          detail: [
            "No WebView state here marks a file accepted, clears failures, drains pending publish, rewrites manifests/sidecars, launches work, saves settings, renames files, or touches media.",
            "If proof is blocked or stale, use backend-owned Diagnostics/open commands and existing pipeline controls.",
          ],
        },
      ];
    }

    function completedRealMediaProofPostureStatus(posture) {
      const normalized = String(posture || "").toLowerCase();
      if (normalized.includes("blocked")) return "blocked";
      if (normalized.includes("review")) return "warning";
      if (normalized.includes("current")) return "match";
      if (normalized.includes("read-first")) return "changed";
      if (normalized.includes("no history") || normalized.includes("no policy")) return "unknown";
      return "match";
    }

    function completedRealMediaProofStatus(rows) {
      const list = Array.isArray(rows) ? rows : [];
      if (!list.length) return "No proof";
      if (list.some((row) => completedRealMediaProofPostureStatus(row.posture) === "blocked")) return "Blocked proof";
      if (list.some((row) => completedRealMediaProofPostureStatus(row.posture) === "warning")) return "Review proof";
      if (list.some((row) => completedRealMediaProofPostureStatus(row.posture) === "changed")) return "Read evidence";
      if (list.some((row) => completedRealMediaProofPostureStatus(row.posture) === "unknown")) return "No history";
      return "Proof coherent";
    }

    function completedRealMediaProofSummaryLines(rows) {
      const list = Array.isArray(rows) ? rows : [];
      const blocked = list.filter((row) => completedRealMediaProofPostureStatus(row.posture) === "blocked").length;
      const review = list.filter((row) => completedRealMediaProofPostureStatus(row.posture) === "warning").length;
      const readFirst = list.filter((row) => completedRealMediaProofPostureStatus(row.posture) === "changed").length;
      const lines = [
        "Real-media output proof ladder:",
        `Checkpoints loaded: ${list.length}`,
        `Blocked checkpoints: ${blocked}`,
        `Review checkpoints: ${review}`,
        `Read-first checkpoints: ${readFirst}`,
        "Decision rule: output proof, sidecar proof, route/size/media decision, pending/drain posture, and diagnostics/runtime evidence must agree before trusting a sample.",
        "Phase boundary: Launch proof is pre-run intent only; this ladder is post-run verification for the selected Completed row.",
      ];
      if (blocked) {
        lines.push("First action: stop treating this sample as proof and inspect blocked rows from Completed, Pending Publish, and Diagnostics.");
      } else if (review) {
        lines.push("First action: read review checkpoints before accepting output growth, route changes, or publish state as intentional.");
      } else {
        lines.push("First action: use this as read-only operator confidence; playback/manual proof still matters for real-media validation.");
      }
      lines.push("Mutation guardrail: this ladder does not accept, rerun, drain, repair, delete, publish, rewrite, save settings, rename, or touch media.");
      return lines;
    }

    function completedRealMediaProofDetailLines(item) {
      if (!item) {
        return [
          "Real-media output proof ladder:",
          "Select a proof checkpoint to inspect the evidence chain.",
          "Mutation guardrail: this detail panel is read-only.",
        ];
      }
      const lines = [
        "Real-media output proof ladder:",
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
        lines.push(`Route: ${item.completedRow.route_decision_summary || item.completedRow.route_label || item.completedRow.route || "unknown"}`);
        lines.push(`Route reason: ${[item.completedRow.route_reason_code, item.completedRow.route_reason].filter(Boolean).join(" - ") || "unknown"}`);
        lines.push(`Output growth: ${item.completedRow.size_delta_label || item.completedRow.size_reduction_text || "unknown"}`);
        lines.push(`Audio/subtitle decisions: ${item.completedRow.audio_decision_count || 0}/${item.completedRow.subtitle_decision_count || 0}`);
      }
      lines.push("");
      lines.push("Boundary: this is operator proof support only. Backend state and real playback/output inspection remain authoritative.");
      return lines;
    }

    function selectedCompletedRealMediaProofRow(rows) {
      const list = Array.isArray(rows) ? rows : [];
      return list.find((row) => row.key === state.selectedCompletedRealMediaProofKey) || list[0] || null;
    }

    function selectCompletedRealMediaProofRow(item) {
      state.selectedCompletedRealMediaProofKey = item?.key || "";
      if (item?.completedRow?.row_key) {
        selectedCompletedRowKey = item.completedRow.row_key;
        renderCompletedDetail(item.completedRow);
        renderCompletedRows();
        renderCompletedReviewDigest(state.lastCompletedPayload, state.lastCompletedRows);
        renderCompletedSizeReview(state.lastCompletedPayload, state.lastCompletedRows);
      }
      renderCompletedRealMediaProof(state.lastCompletedPayload, state.lastCompletedRows, state.lastCompletedPendingProofRows, state.lastCompletedPendingPayload);
      renderCompletedFinalTrust(state.lastCompletedPayload, state.lastCompletedRows, state.lastCompletedPendingProofRows, state.lastCompletedPendingPayload);
      renderCompletedPilotEvidencePacket(state.lastCompletedPayload, state.lastCompletedRows, state.lastCompletedPendingProofRows, state.lastCompletedPendingPayload);
    }

    function renderCompletedRealMediaProof(completed = state.lastCompletedPayload, rows = state.lastCompletedRows, proofRows = state.lastCompletedPendingProofRows, pending = state.lastCompletedPendingPayload, commandEntries) {
      const payload = completed || {};
      const rowList = Array.isArray(rows) ? rows : [];
      const proof = completedRealMediaProofRows(payload, rowList, proofRows, pending, commandEntries);
      if (state.selectedCompletedRealMediaProofKey && !proof.some((row) => row.key === state.selectedCompletedRealMediaProofKey)) {
        state.selectedCompletedRealMediaProofKey = "";
      }
      const selected = selectedCompletedRealMediaProofRow(proof);
      setText("completed-real-media-proof-status", completedRealMediaProofStatus(proof));
      setText("completed-real-media-proof-summary", completedRealMediaProofSummaryLines(proof).join("\n"));
      setText("completed-real-media-proof-detail", completedRealMediaProofDetailLines(selected).join("\n"));
      const tbody = byId("completed-real-media-proof-rows");
      if (!tbody) return;
      if (!proof.length) {
        clearRows(tbody, 4, "No real-media proof checkpoints loaded.");
        updateTableStatusLegend("completed-real-media-proof-legend", tbody, "Real-media output proof rows");
        return;
      }
      tbody.replaceChildren();
      proof.forEach((item) => {
        const row = document.createElement("tr");
        row.dataset.status = completedRealMediaProofPostureStatus(item.posture);
        appendCells(row, [
          item.checkpoint || "",
          item.posture || "Read-only",
          item.evidence || "",
          item.action || "",
        ]);
        makeRowSelectable(row, () => selectCompletedRealMediaProofRow(item), {
          selected: item.key === state.selectedCompletedRealMediaProofKey,
          label: `Review real-media output proof ${item.checkpoint || ""}`,
        });
        tbody.appendChild(row);
      });
      updateTableStatusLegend("completed-real-media-proof-legend", tbody, "Real-media output proof rows");
    }

    function completedFinalTrustRows(completed, rows, proofRows = state.lastCompletedPendingProofRows, pending = state.lastCompletedPendingPayload, commandEntries) {
      const payload = completed || {};
      const rowList = Array.isArray(rows) ? rows : [];
      const item = completedRealMediaProofSelectedOrFirst(rowList);
      const realMediaRows = completedRealMediaProofRows(payload, rowList, proofRows, pending, commandEntries);
      const acceptanceRows = completedAcceptanceRows(payload, rowList, proofRows, commandEntries);
      const relevantProofRows = completedAcceptanceProofRowsForItem(item, proofRows);
      const commands = completedAcceptanceCommandEntries(commandEntries);
      const missingOutput = completedProofRowMissingOutput(item);
      const missingSidecar = item?.sidecar_exists === false || (Array.isArray(item?.consistency_issues) && item.consistency_issues.some((issue) => String(issue || "").toLowerCase().includes("sidecar")));
      const exactProofRows = relevantProofRows.filter((row) => completedPendingProofIsExactPathSignal(row?.signal));
      const blockedProofRows = relevantProofRows.filter((row) => row?.status === "blocked");
      const reviewProofRows = relevantProofRows.filter((row) => row?.status === "warning" || row?.signal === "same-leaf-review");
      const drainSummary = completedProofDrainSummaryPayload(pending || {});
      const commandIssues = commands.filter((entry) => !["ok", "info", "none"].includes(completedAcceptanceIssueLevel(entry)));
      const routeEvidence = Array.isArray(item?.route_evidence_lines) ? item.route_evidence_lines.length : 0;
      const audioCount = Number(item?.audio_decision_count || 0);
      const subtitleCount = Number(item?.subtitle_decision_count || 0);
      const realMediaBlocked = realMediaRows.filter((row) => completedRealMediaProofPostureStatus(row.posture) === "blocked").length;
      const realMediaReview = realMediaRows.filter((row) => completedRealMediaProofPostureStatus(row.posture) === "warning").length;
      const acceptanceBlocked = acceptanceRows.filter((row) => completedAcceptancePostureStatus(row.posture) === "blocked").length;
      const acceptanceReview = acceptanceRows.filter((row) => completedAcceptancePostureStatus(row.posture) === "warning").length;
      const rowsOut = [];
      const add = (key, step, posture, evidence, action, detail = [], completedRow = item) => {
        rowsOut.push({ key, step, posture, evidence, action, detail, completedRow });
      };

      if (!rowList.length) {
        add(
          "no-completed-final-trust",
          "Select completed output",
          payload.error ? "Blocked review" : "No history",
          payload.error ? `Completed history unavailable: ${payload.error}` : "No completed rows are loaded.",
          "Open Diagnostics > Completed Manifest, Run Logs, and Last Stderr before treating WebView as final-output proof.",
          [
            "Completed final output trust walkthrough:",
            "A selected Completed row is required before final output trust can be reviewed.",
          ],
          null,
        );
        return rowsOut;
      }

      add(
        "selected-completed-row",
        "1. Selected Completed row",
        missingOutput ? "Blocked review" : item ? "Current proof" : "Select row",
        `${completedProofRowLabel(item)}; output=${completedProofCompletedOutputPath(item) || "unknown"}; source=${completedProofCompletedSourcePath(item) || "unknown"}.`,
        missingOutput
          ? "Stop here: a Completed row with missing output is not final-output proof."
          : "Use this row as the anchor for all output, sidecar, pending, diagnostics, and validation checks.",
        [
          "Proof starts with the backend-authored Completed Manifest row.",
          `Output health: ${item?.output_health || (item?.output_exists === false ? "missing output" : "unknown")}`,
          `Consistency: ${item?.consistency_status || "unknown"}`,
        ],
      );
      add(
        "disk-sidecar-proof",
        "2. Output and sidecar on disk",
        missingOutput || missingSidecar ? "Blocked review" : "Current proof",
        `output=${missingOutput ? "missing" : "present/unknown"}; sidecar=${missingSidecar ? "missing/review" : "present/unknown"}; sidecar_path=${item?.sidecar_path || item?.expected_sidecar_path || "unknown"}.`,
        missingOutput || missingSidecar
          ? "Open Completed Manifest, output folder, sidecar, Run Logs, and Last Stderr before rerun, cleanup, or validation acceptance."
          : "Confirm the output and sidecar are the expected files before treating the run as accepted.",
        [
          `Output path: ${completedProofCompletedOutputPath(item) || "unknown"}`,
          `Sidecar path: ${item?.sidecar_path || item?.expected_sidecar_path || "unknown"}`,
          `Consistency issues: ${Array.isArray(item?.consistency_issues) && item.consistency_issues.length ? item.consistency_issues.join(", ") : "none loaded"}`,
        ],
      );
      add(
        "pending-drain-final-placement",
        "3. Pending/drain final placement",
        blockedProofRows.length ? "Blocked review" : exactProofRows.length ? "Current proof" : reviewProofRows.length ? "Review" : "Read-first",
        `related proof=${relevantProofRows.length}; exact=${exactProofRows.length}; blocked=${blockedProofRows.length}; review=${reviewProofRows.length}; drain_summary=${drainSummary.read_error ? "unreadable" : drainSummary.exists === false ? "not found" : "loaded/unknown"}.`,
        blockedProofRows.length
          ? "Resolve blocked Completed/Pending proof before retrying drain, rerun, cleanup, delete, or acceptance."
          : exactProofRows.length
            ? "Use exact pending/drain proof as supporting final-placement evidence, then still verify current output state."
            : "If output is missing, empty Pending Publish is not proof that final publish succeeded.",
        [
          "Proof order: Completed Manifest row -> exact output/source path -> current Pending Publish row/state -> durable drain summary -> Run Logs / Last Stderr.",
          "Same-leaf rows are duplicate-title hints only.",
        ],
      );
      add(
        "plex-media-policy-proof",
        "4. Plex/media policy proof",
        item?.size_growth_over_5 || routeEvidence === 0 ? "Review" : "Read-first",
        `route=${item?.route_decision_summary || item?.route_label || item?.route || "unknown"}; encoder=${item?.encoder || item?.encoder_kind || "unknown"}; size=${item?.size_delta_label || item?.size_reduction_text || "unknown"}; audio/subtitle=${audioCount}/${subtitleCount}; route_evidence=${routeEvidence}.`,
        item?.size_growth_over_5
          ? "Compare route reason, size policy, audio/subtitle decisions, Settings, and Last Stderr before accepting growth."
          : "Confirm route, size, audio, and subtitle decisions match the intended Plex direct-stream/direct-play profile.",
        [
          "Output existence does not prove Plex compatibility.",
          `Route reason: ${[item?.route_reason_code, item?.route_reason].filter(Boolean).join(" - ") || "unknown"}`,
          `Audio/subtitle preview rows: ${Array.isArray(item?.audio_decision_preview) ? item.audio_decision_preview.length : 0}/${Array.isArray(item?.subtitle_decision_preview) ? item.subtitle_decision_preview.length : 0}`,
        ],
      );
      add(
        "diagnostics-log-proof",
        "5. Diagnostics and logs",
        commandIssues.length || String(item?.runtime_outcome_status || "").toLowerCase().includes("fail") || String(item?.runtime_outcome_status || "").toLowerCase().includes("error") ? "Review" : "Read-first",
        `runtime=${item?.runtime_outcome_status || "unknown"} (${item?.runtime_outcome_freshness_status || "unknown"}); command issues=${commandIssues.length}.`,
        commandIssues.length
          ? "Read command detail, Completed Manifest, Run Logs, Last Stderr, and Latest Failure before trusting this output."
          : "Use Diagnostics as supporting evidence before recording sample acceptance.",
        [
          "Read order: Completed Manifest -> Pending Publish -> Last Stderr -> Run Logs -> Latest Failure.",
          `Runtime reason: ${item?.runtime_outcome_reason || "not reported"}`,
        ],
      );
      add(
        "sample-validation-acceptance",
        "6. Sample Validation evidence",
        missingOutput || realMediaBlocked || acceptanceBlocked ? "Blocked review" : realMediaReview || acceptanceReview ? "Review" : "Read-first",
        `real-media blocked/review=${realMediaBlocked}/${realMediaReview}; acceptance blocked/review=${acceptanceBlocked}/${acceptanceReview}; source=${completedProofCompletedSourcePath(item) ? "present" : "missing"}; output=${completedProofCompletedOutputPath(item) ? "present" : "missing"}.`,
        missingOutput || realMediaBlocked || acceptanceBlocked
          ? "Do not append an accepted Sample Validation record until current proof is coherent and manual playback checks are done."
          : "Use Home > Sample Validation Preview Record, then append evidence only after playback/subtitle/audio/size checks agree.",
        [
          "Sample Validation is evidence-only JSONL.",
          "It cannot accept output, clear failures, drain Pending Publish, launch work, rewrite manifests, or mutate media.",
          "Manual playback/subtitle/audio/size inspection remains required before acceptance.",
        ],
      );
      add(
        "final-boundary",
        "7. Boundary",
        "Read-only",
        "This walkthrough joins existing proof panels; it does not execute backend commands.",
        "Treat this as a final read order, not an action button.",
        [
          "Mutation guardrail: this walkthrough cannot accept, repair, rerun, drain, publish, delete, save settings, rename, rewrite manifests/sidecars, or touch media.",
        ],
        item,
      );
      return rowsOut;
    }

    function completedFinalTrustPostureStatus(posture) {
      const normalized = String(posture || "").toLowerCase();
      if (normalized.includes("blocked")) return "blocked";
      if (normalized.includes("review")) return "warning";
      if (normalized.includes("read-first")) return "changed";
      if (normalized.includes("current")) return "match";
      if (normalized.includes("select") || normalized.includes("no history")) return "unknown";
      return "match";
    }

    function completedFinalTrustStatus(rows) {
      const list = Array.isArray(rows) ? rows : [];
      if (!list.length) return "No walkthrough";
      if (list.some((row) => completedFinalTrustPostureStatus(row.posture) === "blocked")) return "Blocked trust";
      if (list.some((row) => completedFinalTrustPostureStatus(row.posture) === "warning")) return "Review trust";
      if (list.some((row) => completedFinalTrustPostureStatus(row.posture) === "changed")) return "Read evidence";
      if (list.some((row) => completedFinalTrustPostureStatus(row.posture) === "unknown")) return "Select row";
      return "Trust coherent";
    }

    function completedFinalTrustSummaryLines(rows) {
      const list = Array.isArray(rows) ? rows : [];
      const blocked = list.filter((row) => completedFinalTrustPostureStatus(row.posture) === "blocked").length;
      const review = list.filter((row) => completedFinalTrustPostureStatus(row.posture) === "warning").length;
      const readFirst = list.filter((row) => completedFinalTrustPostureStatus(row.posture) === "changed").length;
      const lines = [
        "Completed final output trust walkthrough:",
        `Steps loaded: ${list.length}`,
        `Blocked/review/read-first: ${blocked}/${review}/${readFirst}`,
        "Decision rule: trust the selected output only after Completed Manifest, disk/sidecar state, Pending Publish/drain proof, Plex/media policy evidence, Diagnostics logs, and Sample Validation preview agree.",
      ];
      if (blocked) {
        lines.push("First action: stop before acceptance, cleanup, deletion, rerun, or another drain and inspect blocked steps.");
      } else if (review || readFirst) {
        lines.push("First action: walk the steps in order, then use Home > Sample Validation Preview Record only after manual playback/subtitle/audio/size checks agree.");
      } else {
        lines.push("First action: evidence is coherent-looking; still treat playback/manual inspection as required before acceptance.");
      }
      lines.push("Mutation guardrail: this walkthrough is read-only and cannot accept, repair, rerun, drain, publish, delete, save settings, rename, rewrite manifests/sidecars, or touch media.");
      return lines;
    }

    function completedFinalTrustDetailLines(item) {
      if (!item) {
        return [
          "Completed final output trust walkthrough:",
          "Select a walkthrough step to inspect proof order and safe next action.",
          "Mutation guardrail: this detail panel is read-only.",
        ];
      }
      const lines = [
        "Completed final output trust walkthrough:",
        `Step: ${item.step || "unknown"}`,
        `Posture: ${item.posture || "read-only"}`,
        `Evidence: ${item.evidence || ""}`,
        `Operator action: ${item.action || ""}`,
      ];
      (Array.isArray(item.detail) ? item.detail : []).forEach((line) => lines.push(line));
      if (item.completedRow) {
        lines.push("");
        lines.push("Associated completed row:");
        lines.push(`Title: ${completedProofRowLabel(item.completedRow)}`);
        lines.push(`Output: ${completedProofCompletedOutputPath(item.completedRow) || "unknown"}`);
        lines.push(`Source: ${completedProofCompletedSourcePath(item.completedRow) || "unknown"}`);
        lines.push(`Route: ${item.completedRow.route_decision_summary || item.completedRow.route_label || item.completedRow.route || "unknown"}`);
        lines.push(`Size: ${item.completedRow.size_delta_label || item.completedRow.size_reduction_text || "unknown"}`);
      }
      lines.push("");
      lines.push("Guardrail: this walkthrough is decision support only; backend state, diagnostics, and manual playback/output inspection remain authoritative.");
      return lines;
    }

    function selectedCompletedFinalTrustRow(rows) {
      const list = Array.isArray(rows) ? rows : [];
      return list.find((row) => row.key === state.selectedCompletedFinalTrustKey)
        || list.find((row) => completedFinalTrustPostureStatus(row.posture) === "blocked")
        || list.find((row) => completedFinalTrustPostureStatus(row.posture) === "warning")
        || list[0]
        || null;
    }

    function selectCompletedFinalTrustRow(item) {
      state.selectedCompletedFinalTrustKey = item?.key || "";
      if (item?.completedRow?.row_key) {
        selectedCompletedRowKey = item.completedRow.row_key;
        renderCompletedDetail(item.completedRow);
        renderCompletedRows();
        renderCompletedReviewDigest(state.lastCompletedPayload, state.lastCompletedRows);
        renderCompletedSizeReview(state.lastCompletedPayload, state.lastCompletedRows);
      }
      renderCompletedFinalTrust(state.lastCompletedPayload, state.lastCompletedRows, state.lastCompletedPendingProofRows, state.lastCompletedPendingPayload);
      renderCompletedPilotEvidencePacket(state.lastCompletedPayload, state.lastCompletedRows, state.lastCompletedPendingProofRows, state.lastCompletedPendingPayload);
    }

    function selectCompletedFinalTrustStep(stepOrKey) {
      const target = String(stepOrKey || "").trim().toLowerCase();
      if (!target) return false;
      const trustRows = completedFinalTrustRows(
        state.lastCompletedPayload,
        state.lastCompletedRows,
        state.lastCompletedPendingProofRows,
        state.lastCompletedPendingPayload,
      );
      const selected = trustRows.find((row) => {
        const key = String(row?.key || "").trim().toLowerCase();
        const step = String(row?.step || "").trim().toLowerCase();
        return key === target || step === target || (step && step.startsWith(target));
      });
      if (!selected) return false;
      state.selectedCompletedFinalTrustKey = selected.key || "";
      renderCompletedFinalTrust(state.lastCompletedPayload, state.lastCompletedRows, state.lastCompletedPendingProofRows, state.lastCompletedPendingPayload);
      return true;
    }

    function renderCompletedFinalTrust(completed = state.lastCompletedPayload, rows = state.lastCompletedRows, proofRows = state.lastCompletedPendingProofRows, pending = state.lastCompletedPendingPayload, commandEntries) {
      const payload = completed || {};
      const rowList = Array.isArray(rows) ? rows : [];
      const trustRows = completedFinalTrustRows(payload, rowList, proofRows, pending, commandEntries);
      if (state.selectedCompletedFinalTrustKey && !trustRows.some((row) => row.key === state.selectedCompletedFinalTrustKey)) {
        state.selectedCompletedFinalTrustKey = "";
      }
      const selected = selectedCompletedFinalTrustRow(trustRows);
      setText("completed-final-trust-status", completedFinalTrustStatus(trustRows));
      setText("completed-final-trust-summary", completedFinalTrustSummaryLines(trustRows).join("\n"));
      setText("completed-final-trust-detail", completedFinalTrustDetailLines(selected).join("\n"));
      setText("completed-final-trust-legend", "Final output trust rows are read-only and do not accept, repair, rerun, drain, publish, delete, rewrite, save settings, rename, or touch media.");
      const tbody = byId("completed-final-trust-rows");
      if (!tbody) return;
      if (!trustRows.length) {
        clearRows(tbody, 4, "No final output trust walkthrough rows loaded.");
        updateTableStatusLegend("completed-final-trust-legend", tbody, "Completed final output trust rows");
        return;
      }
      tbody.replaceChildren();
      trustRows.forEach((item) => {
        const row = document.createElement("tr");
        row.dataset.status = completedFinalTrustPostureStatus(item.posture);
        appendCells(row, [item.step || "", item.posture || "Read-only", item.evidence || "", item.action || ""]);
        makeRowSelectable(row, () => selectCompletedFinalTrustRow(item), {
          selected: item.key === selected?.key,
          label: `Review completed final output trust step ${item.step || ""}`,
        });
        tbody.appendChild(row);
      });
      updateTableStatusLegend("completed-final-trust-legend", tbody, "Completed final output trust rows");
    }

    function completedPilotEvidenceSelectedRow(rows) {
      return getSelectedCompletedRow() || completedRealMediaProofSelectedOrFirst(rows);
    }

    function completedPilotEvidencePacketRows(completed, rows, proofRows = state.lastCompletedPendingProofRows, pending = state.lastCompletedPendingPayload, commandEntries) {
      const payload = completed || {};
      const rowList = Array.isArray(rows) ? rows : [];
      const item = completedPilotEvidenceSelectedRow(rowList);
      const relevantProofRows = completedAcceptanceProofRowsForItem(item, proofRows);
      const realMediaRows = completedRealMediaProofRows(payload, rowList, proofRows, pending, commandEntries);
      const finalTrustRows = completedFinalTrustRows(payload, rowList, proofRows, pending, commandEntries);
      const acceptanceRows = completedAcceptanceRows(payload, rowList, proofRows, commandEntries);
      const commands = completedAcceptanceCommandEntries(commandEntries);
      const commandIssues = commands.filter((entry) => !["ok", "info", "none"].includes(completedAcceptanceIssueLevel(entry)));
      const exactProofRows = relevantProofRows.filter((row) => completedPendingProofIsExactPathSignal(row?.signal));
      const blockedProofRows = relevantProofRows.filter((row) => row?.status === "blocked");
      const reviewProofRows = relevantProofRows.filter((row) => row?.status === "warning" || row?.signal === "same-leaf-review");
      const finalPlacementRows = relevantProofRows.filter((row) => completedPendingProofIsFinalPlacementReviewSignal(row?.signal));
      const missingOutput = completedProofRowMissingOutput(item);
      const consistencyIssues = Array.isArray(item?.consistency_issues) ? item.consistency_issues.filter(Boolean) : [];
      const missingSidecar = item?.sidecar_exists === false || consistencyIssues.some((issue) => String(issue || "").toLowerCase().includes("sidecar"));
      const unknownSidecar = item && item.sidecar_exists !== true && item.sidecar_exists !== false && !item.sidecar_path && !item.expected_sidecar_path;
      const routeEvidence = Array.isArray(item?.route_evidence_lines) ? item.route_evidence_lines.length : 0;
      const audioCount = Number(item?.audio_decision_count || 0);
      const subtitleCount = Number(item?.subtitle_decision_count || 0);
      const sizeReview = Boolean(
        item?.size_growth_over_5
        || item?.size_policy_exceeded
        || String(item?.size_policy_status || "").toLowerCase().includes("exceed")
        || String(item?.size_policy_status || "").toLowerCase().includes("review")
      );
      const runtimeStatus = String(item?.runtime_outcome_status || "").toLowerCase();
      const runtimeReview = runtimeStatus.includes("fail") || runtimeStatus.includes("error") || runtimeStatus.includes("stale");
      const realMediaBlocked = realMediaRows.filter((row) => completedRealMediaProofPostureStatus(row.posture) === "blocked").length;
      const realMediaReview = realMediaRows.filter((row) => completedRealMediaProofPostureStatus(row.posture) === "warning").length;
      const finalTrustBlocked = finalTrustRows.filter((row) => completedFinalTrustPostureStatus(row.posture) === "blocked").length;
      const finalTrustReview = finalTrustRows.filter((row) => completedFinalTrustPostureStatus(row.posture) === "warning").length;
      const acceptanceBlocked = acceptanceRows.filter((row) => completedAcceptancePostureStatus(row.posture) === "blocked").length;
      const acceptanceReview = acceptanceRows.filter((row) => completedAcceptancePostureStatus(row.posture) === "warning").length;
      const sampleLines = completedSampleValidationComparisonLines(item);
      const policyOutput = completedPolicyAlignmentOutputEvidence(item, relevantProofRows);
      const rowsOut = [];
      const add = (key, checkpoint, posture, evidence, action, detail = [], completedRow = item) => {
        rowsOut.push({ key, checkpoint, posture, evidence, action, detail, completedRow });
      };

      if (!rowList.length) {
        add(
          "no-selected-pilot-evidence",
          "Select Completed row",
          payload.error ? "Blocked review" : "No history",
          payload.error ? `Completed history unavailable: ${payload.error}` : "No Completed rows are loaded.",
          "Open Diagnostics > Completed Manifest, Run Logs, and Last Stderr before treating WebView as pilot-run evidence.",
          [
            "Selected pilot evidence packet:",
            "A Completed row is required before a post-run pilot evidence packet can be built.",
            "Guardrail: this panel is read-only and cannot accept, rerun, drain, publish, rename, rewrite manifests/sidecars, or touch media.",
          ],
          null,
        );
        return rowsOut;
      }

      add(
        "selected-completed-output",
        "1. Selected Completed output",
        missingOutput ? "Blocked review" : item ? "Current proof" : "Select row",
        `${completedProofRowLabel(item)}; output=${completedProofCompletedOutputPath(item) || "unknown"}; source=${completedProofCompletedSourcePath(item) || "unknown"}.`,
        missingOutput
          ? "Stop before sample acceptance: selected Completed row points at a missing or unhealthy output."
          : "Use this row as the anchor for route, size, Pending Publish, Diagnostics, and playback evidence.",
        [
          "Selected pilot evidence packet:",
          `Completed row key: ${completedProofRowKey(item) || "unknown"}`,
          `Output health: ${item?.output_health || (item?.output_exists === false ? "missing output" : "unknown")}`,
          `Operator trust state: ${item?.operator_trust_state || item?.operator_status || "unknown"}`,
        ],
      );
      add(
        "output-sidecar-proof",
        "2. Output and sidecar proof",
        missingOutput || missingSidecar ? "Blocked review" : unknownSidecar ? "Review" : "Current proof",
        `output=${missingOutput ? "missing" : "present/unknown"}; sidecar=${missingSidecar ? "missing/review" : unknownSidecar ? "unknown" : "present/unknown"}; sidecar_path=${item?.sidecar_path || item?.expected_sidecar_path || "unknown"}.`,
        missingOutput || missingSidecar
          ? "Stop before sample acceptance: open output folder, Completed Manifest, sidecar, Run Logs, and Last Stderr before accepting the pilot."
          : "Confirm the output and sidecar match the selected source/output before recording pilot evidence.",
        [
          `Output path: ${completedProofCompletedOutputPath(item) || "unknown"}`,
          `Sidecar path: ${item?.sidecar_path || item?.expected_sidecar_path || "unknown"}`,
          `Consistency status: ${item?.consistency_status || "unknown"}`,
          `Consistency issues: ${consistencyIssues.length ? consistencyIssues.join(", ") : "none loaded"}`,
        ],
      );
      add(
        "route-size-media-proof",
        "3. Route, size, audio, subtitle proof",
        sizeReview || routeEvidence === 0 ? "Review" : "Current proof",
        `route=${item?.route_decision_summary || item?.route_label || item?.route || "unknown"}; size=${item?.size_delta_label || item?.size_reduction_text || "unknown"}; audio/subtitle=${audioCount}/${subtitleCount}; route_evidence=${routeEvidence}.`,
        sizeReview
          ? "Compare route reason, size policy, audio/subtitle decisions, Settings, and Last Stderr before accepting output growth."
          : "Confirm the route and media decisions match the intended Plex profile and operator expectation.",
        [
          `Route reason: ${[item?.route_reason_code, item?.route_reason].filter(Boolean).join(" - ") || "unknown"}`,
          `Encoder: ${item?.encoder || item?.encoder_kind || "unknown"}`,
          `Size policy: ${item?.size_policy_mode || "unknown"} ${item?.size_policy_limit_label || ""}; status=${item?.size_policy_status || "unknown"}`,
          `Audio/subtitle preview rows: ${Array.isArray(item?.audio_decision_preview) ? item.audio_decision_preview.length : 0}/${Array.isArray(item?.subtitle_decision_preview) ? item.subtitle_decision_preview.length : 0}`,
        ],
      );
      add(
        "completed-policy-reconciliation",
        "3b. Saved policy reconciliation",
        policyOutput.posture,
        policyOutput.evidence,
        policyOutput.action,
        policyOutput.detail,
      );
      add(
        "pending-final-placement-proof",
        "4. Pending/final placement proof",
        blockedProofRows.length || (missingOutput && !exactProofRows.length) ? "Blocked review" : exactProofRows.length ? "Current proof" : reviewProofRows.length || finalPlacementRows.length ? "Review" : "Read-first",
        `related pending/drain rows=${relevantProofRows.length}; exact=${exactProofRows.length}; blocked=${blockedProofRows.length}; review=${reviewProofRows.length}; final-placement=${finalPlacementRows.length}.`,
        blockedProofRows.length || (missingOutput && !exactProofRows.length)
          ? "Resolve Completed/Pending/drain proof before cleanup, rerun, drain, or sample acceptance."
          : "Use exact path proof as support only; current output and sidecar state still decide whether the sample is acceptable.",
        [
          "Proof order: Completed Manifest row -> exact output/source path -> Pending Publish row/state -> durable drain summary -> Run Logs / Last Stderr.",
          "Same-leaf rows are duplicate-title hints only and do not prove final placement.",
        ],
      );
      add(
        "diagnostics-runtime-proof",
        "5. Diagnostics/runtime proof",
        runtimeReview || commandIssues.length ? "Review" : "Read-first",
        `runtime=${item?.runtime_outcome_status || "unknown"} (${item?.runtime_outcome_freshness_status || "unknown"}); command issues=${commandIssues.length}.`,
        runtimeReview || commandIssues.length
          ? "Read Completed Manifest, Pending Publish, Last Stderr, Run Logs, Latest Failure, and command details before accepting this pilot."
          : "Use Diagnostics as supporting evidence before recording the selected output as accepted.",
        [
          "Read order: Completed Manifest -> Pending Publish -> Last Stderr -> Run Logs -> Latest Failure.",
          `Runtime reason: ${item?.runtime_outcome_reason || "not reported"}`,
          `Recent command entries loaded: ${commands.length}`,
        ],
      );
      add(
        "sample-validation-readiness",
        "6. Sample Validation readiness",
        missingOutput || realMediaBlocked || finalTrustBlocked || acceptanceBlocked ? "Blocked review" : realMediaReview || finalTrustReview || acceptanceReview ? "Review" : "Manual check",
        `real-media blocked/review=${realMediaBlocked}/${realMediaReview}; final trust blocked/review=${finalTrustBlocked}/${finalTrustReview}; acceptance blocked/review=${acceptanceBlocked}/${acceptanceReview}.`,
        missingOutput || realMediaBlocked || finalTrustBlocked || acceptanceBlocked
          ? "Do not append accepted Sample Validation evidence until blocked rows are explained and manual playback checks pass."
          : "Use Home > Sample Validation Preview Record, then append only after playback, subtitle, audio, size, and placement checks agree.",
        [
          ...sampleLines,
          "Sample Validation is evidence-only JSONL; it cannot publish, rerun, repair, drain, rename, rewrite manifests, or touch media.",
        ],
      );
      add(
        "manual-playback-checks",
        "7. Manual playback checks",
        "Manual check",
        "Verify Plex/client playback, direct-stream/direct-play expectation, subtitles, audio language/channel behavior, duration, seek, and file size before acceptance.",
        "Record accepted evidence only after real playback/output inspection matches the packet.",
        [
          "Suggested playback checks: open in Plex/client, confirm video starts/seeks, confirm expected subtitles are present, confirm preferred audio/default track behavior, compare duration, and verify no unexpected size balloon.",
          "For pilot runs, keep source and output available until acceptance is recorded and a rollback path exists.",
        ],
      );
      add(
        "mutation-boundary",
        "8. Read-only mutation boundary",
        "Read-only",
        "This packet only joins already-loaded backend proof panels and selected-row metadata.",
        "Treat it as a copyable evidence packet, not an approval or repair command.",
        [
          "Mutation guardrail: this packet cannot accept output, rerun jobs, drain Pending Publish, publish files, delete files, save settings, rename files, rewrite manifests/sidecars, or touch media.",
          "Backend-owned commands and Diagnostics remain authoritative for mutation and recovery.",
        ],
      );
      return rowsOut;
    }

    function completedPilotEvidencePostureStatus(posture) {
      const normalized = String(posture || "").toLowerCase();
      if (normalized.includes("blocked")) return "blocked";
      if (normalized.includes("review")) return "warning";
      if (normalized.includes("manual") || normalized.includes("read-first") || normalized.includes("read-only")) return "changed";
      if (normalized.includes("current") || normalized.includes("ready")) return "match";
      if (normalized.includes("select") || normalized.includes("no history")) return "unknown";
      return "match";
    }

    function completedPilotEvidencePacketStatus(rows) {
      const list = Array.isArray(rows) ? rows : [];
      if (!list.length) return "No packet";
      if (list.some((row) => completedPilotEvidencePostureStatus(row.posture) === "blocked")) return "Packet blocked";
      if (list.some((row) => completedPilotEvidencePostureStatus(row.posture) === "warning")) return "Review packet";
      if (list.some((row) => completedPilotEvidencePostureStatus(row.posture) === "changed")) return "Manual checks";
      if (list.some((row) => completedPilotEvidencePostureStatus(row.posture) === "unknown")) return "Select row";
      return "Current proof";
    }

    function completedPilotEvidencePacketSummaryLines(rows) {
      const list = Array.isArray(rows) ? rows : [];
      const blocked = list.filter((row) => completedPilotEvidencePostureStatus(row.posture) === "blocked").length;
      const review = list.filter((row) => completedPilotEvidencePostureStatus(row.posture) === "warning").length;
      const manual = list.filter((row) => completedPilotEvidencePostureStatus(row.posture) === "changed").length;
      const current = list.filter((row) => completedPilotEvidencePostureStatus(row.posture) === "match").length;
      const lines = [
        "Selected pilot evidence packet:",
        "Purpose: copyable post-run proof for a selected Completed row after a real-media pilot run.",
        `Checkpoints loaded: ${list.length}`,
        `Blocked/review/manual: ${blocked}/${review}/${manual}`,
        `Blocked checkpoints: ${blocked}`,
        `Review checkpoints: ${review}`,
        `Manual-check checkpoints: ${manual}`,
        `Current-proof checkpoints: ${current}`,
        "Decision rule: do not append an accepted Sample Validation record until output, sidecar, route/size/media, pending/final placement, diagnostics, and manual playback checks agree.",
        "Mutation guardrail: this packet is read-only; backend-owned commands remain authoritative for publish, rerun, repair, drain, delete, rename, manifest, sidecar, and media changes.",
      ];
      if (!list.length) {
        lines.push("First action: select a Completed row or open Diagnostics > Completed Manifest before building pilot evidence.");
      } else if (blocked) {
        lines.push("First action: stop before acceptance, cleanup, rerun, deletion, or another drain until blocked evidence is resolved.");
      } else if (review) {
        lines.push("First action: read review checkpoints and diagnostics before recording acceptance.");
      } else {
        lines.push("First action: perform manual playback checks before writing any Sample Validation acceptance evidence.");
      }
      return lines;
    }

    function completedPilotEvidencePacketDetailLines(item) {
      if (!item) {
        return [
          "Selected pilot evidence packet:",
          "Checkpoint: none selected",
          "Associated completed row: none",
          "Guardrail: select a packet row to inspect read-only pilot evidence before recording acceptance.",
        ];
      }
      const completedRow = item.completedRow || null;
      const lines = [
        "Selected pilot evidence packet:",
        `Checkpoint: ${item.checkpoint || "unknown"}`,
        `Posture: ${item.posture || "unknown"}`,
        `Evidence: ${item.evidence || "not reported"}`,
        `Action: ${item.action || "Review owning pages and diagnostics before acting."}`,
        `Associated completed row: ${completedRow ? completedProofRowLabel(completedRow) : "none"}`,
      ];
      if (completedRow) {
        lines.push(`Source: ${completedProofCompletedSourcePath(completedRow) || "unknown"}`);
        lines.push(`Output: ${completedProofCompletedOutputPath(completedRow) || "unknown"}`);
      }
      const details = Array.isArray(item.detail) ? item.detail.filter(Boolean) : [];
      if (details.length) {
        lines.push("", "Checkpoint detail:");
        details.forEach((line) => lines.push(String(line)));
      }
      lines.push("", "Guardrail: this detail is read-only and cannot accept output, rerun jobs, drain Pending Publish, publish files, delete files, save settings, rename files, rewrite manifests/sidecars, or touch media.");
      return lines;
    }

    function completedPilotEvidencePacketMarkdownLines(rows) {
      const list = Array.isArray(rows) ? rows : [];
      const selected = selectedCompletedPilotEvidenceRow(list);
      const completedRow = selected?.completedRow || list.find((row) => row?.completedRow)?.completedRow || null;
      const lines = [
        "# Selected Completed Pilot Evidence Packet",
        "",
        `Title: ${completedRow ? completedProofRowLabel(completedRow) : "(no completed row selected)"}`,
        `Source: ${completedRow ? completedProofCompletedSourcePath(completedRow) || "unknown" : "unknown"}`,
        `Output: ${completedRow ? completedProofCompletedOutputPath(completedRow) || "unknown" : "unknown"}`,
        `Output proof: output=${completedProofRowMissingOutput(completedRow) ? "missing" : "present-or-unverified"}`,
        "",
        "## Checklist",
      ];
      if (!list.length) {
        lines.push("- [ ] Select Completed row: no pilot evidence packet rows are loaded.");
      } else {
        list.forEach((row) => {
          lines.push(`- [ ] ${row.checkpoint || "Checkpoint"}: ${row.posture || "Review"} - ${row.action || row.evidence || "Review evidence."}`);
        });
      }
      lines.push(
        "",
        "Confirm Plex/client playback, expected subtitles, audio track/default behavior, duration, seek, and output size before recording acceptance.",
        "Home > Sample Validation evidence is evidence-only; append accepted evidence only after manual playback/output inspection agrees with this packet.",
        "",
        "## Backend mutation boundary:",
        "Backend mutation boundary: this packet cannot accept output, rerun jobs, drain Pending Publish, publish files, delete files, save settings, rename files, rewrite manifests/sidecars, or touch media.",
      );
      return lines;
    }

    function selectedCompletedPilotEvidenceRow(rows) {
      const list = Array.isArray(rows) ? rows : [];
      return list.find((row) => row.key === state.selectedCompletedPilotEvidenceKey)
        || list.find((row) => completedPilotEvidencePostureStatus(row.posture) === "blocked")
        || list.find((row) => completedPilotEvidencePostureStatus(row.posture) === "warning")
        || list[0]
        || null;
    }

    function selectCompletedPilotEvidenceRow(item) {
      state.selectedCompletedPilotEvidenceKey = item?.key || "";
      renderCompletedPilotEvidencePacket(state.lastCompletedPayload, state.lastCompletedRows, state.lastCompletedPendingProofRows, state.lastCompletedPendingPayload);
    }

    function renderCompletedPilotEvidencePacket(completed = state.lastCompletedPayload, rows = state.lastCompletedRows, proofRows = state.lastCompletedPendingProofRows, pending = state.lastCompletedPendingPayload, commandEntries) {
      const payload = completed || {};
      const rowList = Array.isArray(rows) ? rows : [];
      const packetRows = completedPilotEvidencePacketRows(payload, rowList, proofRows, pending, commandEntries);
      if (state.selectedCompletedPilotEvidenceKey && !packetRows.some((row) => row.key === state.selectedCompletedPilotEvidenceKey)) {
        state.selectedCompletedPilotEvidenceKey = "";
      }
      const selected = selectedCompletedPilotEvidenceRow(packetRows);
      if (!state.selectedCompletedPilotEvidenceKey && selected) state.selectedCompletedPilotEvidenceKey = selected.key || "";
      setText("completed-pilot-evidence-status", completedPilotEvidencePacketStatus(packetRows));
      setText("completed-pilot-evidence-summary", completedPilotEvidencePacketSummaryLines(packetRows).join("\n"));
      setText("completed-pilot-evidence-detail", completedPilotEvidencePacketDetailLines(selected).join("\n"));
      setText("completed-pilot-evidence-markdown", completedPilotEvidencePacketMarkdownLines(packetRows).join("\n"));
      const tbody = byId("completed-pilot-evidence-rows");
      if (!tbody) return;
      if (!packetRows.length) {
        clearRows(tbody, 4, rowList.length ? "No selected pilot evidence packet rows were built." : "No completed rows loaded.");
        updateTableStatusLegend("completed-pilot-evidence-legend", tbody, "Selected pilot evidence packet rows");
        return;
      }
      tbody.replaceChildren();
      packetRows.forEach((item) => {
        const row = document.createElement("tr");
        row.dataset.status = completedPilotEvidencePostureStatus(item.posture);
        appendCells(row, [item.checkpoint || "", item.posture || "Read-only", item.evidence || "", item.action || ""]);
        makeRowSelectable(row, () => selectCompletedPilotEvidenceRow(item), {
          selected: item.key === selected?.key,
          label: `Review selected pilot evidence checkpoint ${item.checkpoint || ""}`,
        });
        tbody.appendChild(row);
      });
      updateTableStatusLegend("completed-pilot-evidence-legend", tbody, "Selected pilot evidence packet rows");
    }

    return {
      completedRealMediaProofRows,
      completedRealMediaProofStatus,
      completedRealMediaProofSummaryLines,
      completedRealMediaProofDetailLines,
      completedRealMediaProofPostureStatus,
      completedPolicyAlignmentOutputEvidence,
      completedPolicyOutputCategorySignal,
      renderCompletedRealMediaProof,
      completedFinalTrustRows,
      completedFinalTrustStatus,
      completedFinalTrustSummaryLines,
      completedFinalTrustDetailLines,
      completedFinalTrustPostureStatus,
      selectCompletedFinalTrustStep,
      renderCompletedFinalTrust,
      completedPilotEvidencePacketRows,
      completedPilotEvidencePacketStatus,
      completedPilotEvidencePacketSummaryLines,
      completedPilotEvidencePacketDetailLines,
      completedPilotEvidencePacketMarkdownLines,
      completedPilotEvidencePostureStatus,
      renderCompletedPilotEvidencePacket,
    };
  }

  window.__completedViewProofModule = {
    createCompletedProofModule,
  };
})();
