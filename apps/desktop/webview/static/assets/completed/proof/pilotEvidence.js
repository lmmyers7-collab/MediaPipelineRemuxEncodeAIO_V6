(function () {
  function createCompletedPilotEvidenceModule(deps = {}) {
    const {
      appendCells = function () {},
      byId = function () { return null; },
      captureCompletedProofSelectionScroll = function () { return null; },
      clearRows = function () {},
      completedAcceptanceCommandEntries = function () { return []; },
      completedAcceptanceIssueLevel = function () { return "none"; },
      completedAcceptancePostureStatus = function () { return "unknown"; },
      completedAcceptanceProofRowsForItem = function () { return []; },
      completedAcceptanceRows = function () { return []; },
      completedFinalTrustPostureStatus = function () { return "unknown"; },
      completedFinalTrustRows = function () { return []; },
      completedPendingProofIsExactPathSignal = function () { return false; },
      completedPendingProofIsFinalPlacementReviewSignal = function () { return false; },
      completedPolicyAlignmentOutputEvidence = function () { return {}; },
      completedProofCompletedOutputPath = function () { return ""; },
      completedProofCompletedSourcePath = function () { return ""; },
      completedProofRowKey = function () { return ""; },
      completedProofRowLabel = function () { return ""; },
      completedProofRowMissingOutput = function () { return false; },
      completedRealMediaProofPostureStatus = function () { return "unknown"; },
      completedRealMediaProofRows = function () { return []; },
      completedRealMediaProofSelectedOrFirst = function () { return null; },
      completedSampleValidationComparisonLines = function () { return []; },
      completedSubtitleQaLines = function () { return []; },
      getSelectedCompletedRow = function () { return null; },
      makeRowSelectable = function () {},
      restoreCompletedProofSelectionScroll = function () {},
      setText = function () {},
      state = {},
      updateTableStatusLegend = function () {},
    } = deps;
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
      const validationUnavailable = Array.isArray(item?.validation_unavailable_reasons) ? item.validation_unavailable_reasons.filter(Boolean) : [];
      const validationState = String(item?.validation_status_state || "").toLowerCase();
      const validationBlocked = validationState === "blocked";
      const validationNeeded = validationState === "validation-needed" || validationUnavailable.length > 0 || item?.validation_playback_required === true;
      const validationProbe = item?.validation_probe_ok === true ? "passed" : item?.validation_probe_ok === false ? "failed" : "not reported";
      const validationHash = item?.validation_hash_ok === true ? "passed" : item?.validation_hash_ok === false ? "failed" : "not reported";
      const validationPlayback = item?.validation_playback_required === true ? "required" : item?.validation_playback_required === false ? "not required" : "not reported";
      const routeEvidence = Array.isArray(item?.route_evidence_lines) ? item.route_evidence_lines.length : 0;
      const audioCount = Number(item?.audio_decision_count || 0);
      const subtitleCount = Number(item?.subtitle_decision_count || 0);
      const subtitleQaPosture = String(item?.subtitle_qa?.posture || "").toLowerCase();
      const subtitleQaReview = ["blocked", "review", "unknown"].includes(subtitleQaPosture);
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
        "validation-state-proof",
        "2b. Validation state proof",
        validationBlocked ? "Blocked review" : validationNeeded ? "Review" : "Current proof",
        `state=${item?.validation_status_state || "not reported"}; probe=${validationProbe}; hash=${validationHash}; playback=${validationPlayback}.`,
        validationBlocked
          ? "Stop before sample acceptance: selected Completed validation proof is blocked."
          : validationNeeded
            ? "Treat this as output-presence proof only until probe/hash/playback proof is available or manually documented."
            : "Use validation state as supporting evidence; backend mutation and Sample Validation append remain authoritative.",
        [
          `Validation proof gap: ${item?.validation_failure_reason || "none reported"}`,
          `Unavailable proof: ${validationUnavailable.length ? validationUnavailable.join(", ") : "none reported"}`,
          `Safe next action: ${item?.validation_safe_next_action || "not reported"}`,
          "Proof boundary: this packet does not run ffprobe, hash files, or mark playback accepted.",
        ],
      );
      add(
        "route-size-media-proof",
        "3. Route, size, audio, subtitle proof",
        sizeReview || subtitleQaReview || routeEvidence === 0 ? "Review" : "Current proof",
        `route=${item?.route_decision_summary || item?.route_label || item?.route || "unknown"}; size=${item?.size_delta_label || item?.size_reduction_text || "unknown"}; audio/subtitle=${audioCount}/${subtitleCount}; subtitle_qa=${subtitleQaPosture || "not_reported"}; route_evidence=${routeEvidence}.`,
        sizeReview
          ? "Compare route reason, size policy, audio/subtitle decisions, Settings, and Last Stderr before accepting output growth."
          : subtitleQaReview
            ? "Read subtitle QA evidence and manually verify subtitle selection, type, and sync before accepting this pilot."
            : "Confirm the route and media decisions match the intended Plex profile and operator expectation.",
        [
          `Route reason: ${[item?.route_reason_code, item?.route_reason].filter(Boolean).join(" - ") || "unknown"}`,
          `Encoder: ${item?.encoder || item?.encoder_kind || "unknown"}`,
          `Size policy: ${item?.size_policy_mode || "unknown"} ${item?.size_policy_limit_label || ""}; status=${item?.size_policy_status || "unknown"}`,
          `Audio/subtitle preview rows: ${Array.isArray(item?.audio_decision_preview) ? item.audio_decision_preview.length : 0}/${Array.isArray(item?.subtitle_decision_preview) ? item.subtitle_decision_preview.length : 0}`,
          ...completedSubtitleQaLines(item),
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
      const scrollSnapshot = captureCompletedProofSelectionScroll();
      state.selectedCompletedPilotEvidenceKey = item?.key || "";
      renderCompletedPilotEvidencePacket(state.lastCompletedPayload, state.lastCompletedRows, state.lastCompletedPendingProofRows, state.lastCompletedPendingPayload);
      restoreCompletedProofSelectionScroll(scrollSnapshot);
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
      completedPilotEvidencePacketDetailLines,
      completedPilotEvidencePacketMarkdownLines,
      completedPilotEvidencePacketRows,
      completedPilotEvidencePacketStatus,
      completedPilotEvidencePacketSummaryLines,
      completedPilotEvidencePostureStatus,
      renderCompletedPilotEvidencePacket,
    };
  }

  window.__completedPilotEvidenceModule = { createCompletedPilotEvidenceModule };
})();
