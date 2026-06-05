// completed/evidence/routeAgreement.js
// Split child of completedView.evidence.js. Builds read-only Queue/Completed route-agreement evidence.

/* eslint-disable max-lines-per-function */
(function () {
  "use strict";

  function createCompletedEvidenceRouteAgreementModule(deps = {}) {
    const completedProofCompletedOutputPath = deps.completedProofCompletedOutputPath;
    const completedProofCompletedSourcePath = deps.completedProofCompletedSourcePath;
    const completedProofFirstValue = deps.completedProofFirstValue;
    const completedProofLeaf = deps.completedProofLeaf;
    const completedProofNormalizePath = deps.completedProofNormalizePath;
    const completedProofRowLabel = deps.completedProofRowLabel;
    const renderCompletedDetail = deps.renderCompletedDetail;
    const renderCompletedFinalTrust = deps.renderCompletedFinalTrust;
    const renderCompletedOutputAcceptance = deps.renderCompletedOutputAcceptance;
    const renderCompletedPendingProof = deps.renderCompletedPendingProof;
    const renderCompletedPilotEvidencePacket = deps.renderCompletedPilotEvidencePacket;
    const renderCompletedRealMediaProof = deps.renderCompletedRealMediaProof;
    const renderCompletedReviewDigest = deps.renderCompletedReviewDigest;
    const renderCompletedRouteAgreement = deps.renderCompletedRouteAgreement;
    const renderCompletedRows = deps.renderCompletedRows;
    const renderCompletedSizeEvidence = deps.renderCompletedSizeEvidence;
    const renderCompletedSizeReview = deps.renderCompletedSizeReview;
    const state = deps.state || {};

    function completedRouteAgreementRouteToken(row, kind = "completed") {
      const value = kind === "queue"
        ? completedProofFirstValue(row, ["route_name", "route", "route_label", "route_decision_summary"])
        : completedProofFirstValue(row, ["route", "route_label", "route_name", "route_decision_summary"]);
      const text = String(value || "").trim().toLowerCase();
      if (!text) return "";
      if (text.includes("remux") || text.includes("copy")) return "remux";
      if (text.includes("encode") || text.includes("transcode")) return "encode";
      return text.replace(/[^a-z0-9]+/g, " ").trim().split(/\s+/)[0] || text;
    }

    function completedRouteAgreementReason(row, kind = "completed") {
      const value = kind === "queue"
        ? completedProofFirstValue(row, ["route_reason_code", "route_reason", "route_decision_summary", "blocked_reason_code"])
        : completedProofFirstValue(row, ["route_reason_code", "route_reason", "route_decision_summary"]);
      return String(value || "").trim().toLowerCase();
    }

    function completedRouteAgreementQueueSourcePath(row) {
      return completedProofFirstValue(row, ["source_path", "path", "file", "input_path"]);
    }

    function completedRouteAgreementQueueRowLabel(row) {
      return completedProofFirstValue(row, ["display_name", "relative_path", "source_path", "path"]) || "(queue row)";
    }

    function completedRouteAgreementRouteEvidenceCount(rows) {
      return (Array.isArray(rows) ? rows : []).filter((row) => {
        const evidence = Array.isArray(row?.route_evidence_lines) ? row.route_evidence_lines : [];
        return Boolean(row?.route_decision_summary || row?.route_reason || row?.route_reason_code || evidence.length);
      }).length;
    }

    function completedRouteAgreementQueueIndexes(queueRows) {
      const exact = new Map();
      const leaf = new Map();
      (Array.isArray(queueRows) ? queueRows : []).forEach((row, index) => {
        const path = completedRouteAgreementQueueSourcePath(row);
        const normalized = completedProofNormalizePath(path);
        const leafKey = completedProofLeaf(path).toLowerCase();
        const record = { row, index, path, normalized, leafKey, label: completedRouteAgreementQueueRowLabel(row) };
        if (normalized) {
          if (!exact.has(normalized)) exact.set(normalized, []);
          exact.get(normalized).push(record);
        }
        if (leafKey) {
          if (!leaf.has(leafKey)) leaf.set(leafKey, []);
          leaf.get(leafKey).push(record);
        }
      });
      return { exact, leaf };
    }

    function completedRouteAgreementPostureStatus(posture) {
      const normalized = String(posture || "").toLowerCase();
      if (normalized.includes("blocked") || normalized.includes("mismatch")) return "blocked";
      if (normalized.includes("review")) return "warning";
      if (normalized.includes("read-first")) return "changed";
      if (normalized.includes("unknown") || normalized.includes("no queue")) return "unknown";
      return "match";
    }

    function completedRouteAgreementRows(completed = state.lastCompletedPayload, completedRows = state.lastCompletedRows, queuePayload, queueRows) {
      const payload = completed || {};
      const rowList = Array.isArray(completedRows) ? completedRows : [];
      const queue = queuePayload && typeof queuePayload === "object" ? queuePayload : {};
      const qRows = Array.isArray(queueRows) ? queueRows : [];
      const rowsOut = [];
      const add = (key, signal, posture, evidence, action, detail = [], completedRow = null, queueRow = null) => {
        rowsOut.push({ key, signal, posture, evidence, action, detail, completedRow, queueRow });
      };
      const completedEvidenceCount = completedRouteAgreementRouteEvidenceCount(rowList);
      const audioRows = rowList.filter((row) => Number(row?.audio_decision_count || 0) > 0 || (Array.isArray(row?.audio_decision_preview) && row.audio_decision_preview.length)).length;
      const subtitleRows = rowList.filter((row) => Number(row?.subtitle_decision_count || 0) > 0 || (Array.isArray(row?.subtitle_decision_preview) && row.subtitle_decision_preview.length)).length;

      add(
        "completed-route-proof-coverage",
        "Completed route proof coverage",
        rowList.length && completedEvidenceCount < rowList.length ? "Review" : rowList.length ? "Ready-looking" : "Read-only",
        `completed rows=${rowList.length}; rows with route proof=${completedEvidenceCount}; audio proof rows=${audioRows}; subtitle proof rows=${subtitleRows}`,
        rowList.length
          ? "Use selected completed rows to compare route, audio, subtitle, size, and publish proof before accepting surprising outputs."
          : "Run or load completed history before using route agreement as real-media proof.",
        [
          "This coverage check only tells whether completed rows expose proof fields in the loaded manifest preview.",
          "It does not prove Plex playback, subtitle OCR quality, or pending-publish completion.",
        ],
      );

      if (payload.error) {
        add(
          "completed-unavailable",
          "Completed manifest unavailable",
          "Blocked review",
          `Completed history unavailable: ${payload.error}`,
          "Open Diagnostics > Completed Manifest, Run Logs, and Last Stderr before trusting route agreement.",
        );
        return rowsOut;
      }
      if (queue.error) {
        add(
          "queue-unavailable",
          "Queue context unavailable",
          "Review",
          `Queue preview unavailable: ${queue.error}`,
          "Open Queue Snapshot and Run Logs; completed rows cannot be compared against current queue state.",
        );
        return rowsOut;
      }

      const indexes = completedRouteAgreementQueueIndexes(qRows);
      let exactMatches = 0;
      let routeMismatches = 0;
      let reasonMismatches = 0;
      let leafHints = 0;
      const matchedCompletedKeys = new Set();

      rowList.forEach((completedRow, completedIndex) => {
        const source = completedProofCompletedSourcePath(completedRow);
        const normalized = completedProofNormalizePath(source);
        const sourceLeaf = completedProofLeaf(source).toLowerCase();
        const exactQueue = normalized ? indexes.exact.get(normalized) || [] : [];
        if (exactQueue.length) {
          matchedCompletedKeys.add(completedRow.row_key || String(completedIndex));
          exactQueue.slice(0, 4).forEach((queueRecord) => {
            exactMatches += 1;
            const completedRoute = completedRouteAgreementRouteToken(completedRow, "completed");
            const queueRoute = completedRouteAgreementRouteToken(queueRecord.row, "queue");
            const completedReason = completedRouteAgreementReason(completedRow, "completed");
            const queueReason = completedRouteAgreementReason(queueRecord.row, "queue");
            const routeMismatch = Boolean(completedRoute && queueRoute && completedRoute !== queueRoute);
            const reasonMismatch = Boolean(completedReason && queueReason && completedReason !== queueReason);
            if (routeMismatch) routeMismatches += 1;
            if (!routeMismatch && reasonMismatch) reasonMismatches += 1;
            add(
              `exact-${completedRow.row_key || completedIndex}-${queueRecord.index}`,
              routeMismatch ? "Route mismatch" : "Completed source still queued",
              routeMismatch ? "Blocked mismatch" : reasonMismatch ? "Review" : "Review",
              `source=${source || "unknown"}; completed route=${completedRoute || "unknown"}; queue route=${queueRoute || "unknown"}; completed reason=${completedReason || "unknown"}; queue reason=${queueReason || "unknown"}`,
              routeMismatch
                ? "Refresh Queue, inspect Completed Manifest and Queue Snapshot, and do not launch this source until the route conflict is explained."
                : "Confirm whether this is stale queue state, intentional reprocess, or an output that completed but still appears runnable.",
              [
                `Completed: ${completedProofRowLabel(completedRow)}`,
                `Queue: ${queueRecord.label}`,
                `Completed output: ${completedProofCompletedOutputPath(completedRow) || "unknown"}`,
                `Queue source: ${queueRecord.path || "unknown"}`,
                "Exact source-path overlap is stronger than title matching and should be resolved before unattended launch.",
              ],
              completedRow,
              queueRecord.row,
            );
          });
          return;
        }
        const leafQueue = sourceLeaf ? indexes.leaf.get(sourceLeaf) || [] : [];
        leafQueue.slice(0, 2).forEach((queueRecord) => {
          leafHints += 1;
          add(
            `leaf-${completedRow.row_key || completedIndex}-${queueRecord.index}`,
            "Same filename review",
            "Read-first",
            `filename=${sourceLeaf || "unknown"}; completed source=${source || "unknown"}; queue source=${queueRecord.path || "unknown"}`,
            "Treat this as a duplicate-title hint only; compare full folders, season/movie context, and route evidence before acting.",
            [
              "Filename-only matches are deliberately weaker than exact path matches.",
              "They can catch duplicate-title or moved-folder surprises, but they are not proof of a completed/queued conflict.",
            ],
            completedRow,
            queueRecord.row,
          );
        });
      });

      if (!qRows.length) {
        add(
          "no-queue-context",
          "No current queue rows",
          rowList.length ? "Ready-looking" : "No queue context",
          `completed rows=${rowList.length}; queue rows=0`,
          rowList.length
            ? "This is expected after a clean run, but empty Queue does not prove missing source discovery is correct. Use Diagnostics if sources are expected."
            : "No completed or queued rows are loaded, so route agreement cannot prove anything yet.",
        );
      } else if (!exactMatches && !leafHints) {
        add(
          "no-overlap",
          "No source overlap",
          "Ready-looking",
          `completed rows=${rowList.length}; queue rows=${qRows.length}; exact overlaps=0; filename hints=0`,
          "Completed sources do not appear in current Queue by exact path. Continue with row-level route proof for surprising output size or subtitle/audio behavior.",
        );
      }

      add(
        "agreement-summary",
        "Agreement summary",
        routeMismatches ? "Blocked mismatch" : exactMatches || reasonMismatches || leafHints ? "Review" : "Ready-looking",
        `exact source overlaps=${exactMatches}; route mismatches=${routeMismatches}; reason mismatches=${reasonMismatches}; filename hints=${leafHints}; matched completed rows=${matchedCompletedKeys.size}`,
        routeMismatches
          ? "Resolve route mismatches before launch/rerun. A completed source appearing queued with a different route is high-risk."
          : exactMatches
            ? "Review exact overlaps before launch; they may indicate stale queue state, intentional reprocess, or completed-history drift."
            : "No loaded queue/completed route conflict is visible.",
        [
          "Agreement checks are read-only and compare loaded WebView payloads only.",
          "Backend launch, completed-history reconciliation, rerun, cleanup, and pending-publish movement remain separate backend-owned workflows.",
        ],
      );

      return rowsOut.sort((left, right) => {
        const rank = { blocked: 0, warning: 1, changed: 2, unknown: 3, match: 4 };
        return (rank[completedRouteAgreementPostureStatus(left.posture)] ?? 5) - (rank[completedRouteAgreementPostureStatus(right.posture)] ?? 5);
      });
    }

    function completedRouteAgreementStatus(rows) {
      const list = Array.isArray(rows) ? rows : [];
      if (list.some((row) => completedRouteAgreementPostureStatus(row.posture) === "blocked")) return "Route mismatch";
      if (list.some((row) => completedRouteAgreementPostureStatus(row.posture) === "warning")) return "Review overlap";
      if (list.some((row) => completedRouteAgreementPostureStatus(row.posture) === "changed")) return "Read filename hints";
      if (list.some((row) => completedRouteAgreementPostureStatus(row.posture) === "unknown")) return "No queue context";
      return list.length ? "Ready-looking" : "Not loaded";
    }

    function completedRouteAgreementSummaryLines(rows) {
      const list = Array.isArray(rows) ? rows : [];
      const blocked = list.filter((row) => completedRouteAgreementPostureStatus(row.posture) === "blocked").length;
      const review = list.filter((row) => completedRouteAgreementPostureStatus(row.posture) === "warning").length;
      const readFirst = list.filter((row) => completedRouteAgreementPostureStatus(row.posture) === "changed").length;
      const lines = [
        "Queue / Completed route agreement:",
        `Rows: ${list.length}; blocked=${blocked}; review=${review}; read-first=${readFirst}.`,
        "Decision rule: a completed source should not appear runnable in Queue unless this is deliberate reprocess; if it does, completed route/reason evidence should not contradict Queue route/reason evidence.",
      ];
      if (blocked) {
        lines.push("First action: refresh Queue, open Completed Manifest and Queue Snapshot, then read Last Stderr/Run Logs before launch or rerun.");
      } else if (review || readFirst) {
        lines.push("First action: select review/read-first rows and compare full paths before trusting same-title or stale queue state.");
      } else {
        lines.push("First action: no loaded queue/completed route conflict is visible; use selected Completed rows for route/audio/subtitle/size proof.");
      }
      lines.push("Mutation guardrail: this agreement panel does not launch, rerun, drain, repair, reconcile, delete, rewrite manifests, or touch media files.");
      return lines;
    }

    function completedRouteAgreementDetailLines(item) {
      if (!item) {
        return [
          "Queue / Completed route agreement:",
          "Select an agreement row to inspect the queue/completed evidence.",
          "Mutation guardrail: no action is performed from this detail panel.",
        ];
      }
      const lines = [
        "Queue / Completed route agreement:",
        `Signal: ${item.signal || "unknown"}`,
        `Posture: ${item.posture || "read-only"}`,
        `Evidence: ${item.evidence || ""}`,
        `Safe next step: ${item.action || ""}`,
      ];
      (Array.isArray(item.detail) ? item.detail : []).forEach((line) => lines.push(line));
      if (item.completedRow) {
        lines.push("");
        lines.push("Completed row proof:");
        lines.push(`Title: ${completedProofRowLabel(item.completedRow)}`);
        lines.push(`Source: ${completedProofCompletedSourcePath(item.completedRow) || "unknown"}`);
        lines.push(`Output: ${completedProofCompletedOutputPath(item.completedRow) || "unknown"}`);
        lines.push(`Route: ${completedRouteAgreementRouteToken(item.completedRow, "completed") || "unknown"}; reason=${completedRouteAgreementReason(item.completedRow, "completed") || "unknown"}`);
        lines.push(`Size: ${item.completedRow.size_delta_label || item.completedRow.size_reduction_text || "unknown"}`);
        const evidence = Array.isArray(item.completedRow.route_evidence_lines) ? item.completedRow.route_evidence_lines.filter(Boolean) : [];
        evidence.slice(0, 5).forEach((line) => lines.push(`Completed evidence: ${line}`));
      }
      if (item.queueRow) {
        lines.push("");
        lines.push("Queue row proof:");
        lines.push(`Source: ${completedRouteAgreementQueueSourcePath(item.queueRow) || "unknown"}`);
        lines.push(`Route: ${completedRouteAgreementRouteToken(item.queueRow, "queue") || "unknown"}; reason=${completedRouteAgreementReason(item.queueRow, "queue") || "unknown"}`);
        lines.push(`Status: ${item.queueRow.operator_status || item.queueRow.status || "unknown"}`);
        const evidence = Array.isArray(item.queueRow.route_evidence_lines) ? item.queueRow.route_evidence_lines.filter(Boolean) : [];
        evidence.slice(0, 5).forEach((line) => lines.push(`Queue evidence: ${line}`));
      }
      lines.push("");
      lines.push("Guardrail: this compares loaded Queue and Completed payloads only. Backend state, launch preflight, and diagnostics remain authoritative.");
      return lines;
    }

    function selectedCompletedRouteAgreementRow(rows) {
      const list = Array.isArray(rows) ? rows : [];
      return list.find((row) => row.key === state.selectedCompletedRouteAgreementKey)
        || list.find((row) => completedRouteAgreementPostureStatus(row.posture) !== "match")
        || list[0]
        || null;
    }

    function selectCompletedRouteAgreementRow(item) {
      state.selectedCompletedRouteAgreementKey = item?.key || "";
      if (item?.completedRow?.row_key) {
        state.selectedCompletedRowKey = item.completedRow.row_key;
        renderCompletedDetail(item.completedRow);
        renderCompletedRows();
        renderCompletedReviewDigest(state.lastCompletedPayload, state.lastCompletedRows);
        renderCompletedSizeReview(state.lastCompletedPayload, state.lastCompletedRows);
        renderCompletedPendingProof(state.lastCompletedPayload, state.lastCompletedRows, state.lastCompletedPendingPayload);
        renderCompletedSizeEvidence(state.lastCompletedPayload, state.lastCompletedRows, state.lastCompletedPendingProofRows);
        renderCompletedOutputAcceptance(state.lastCompletedPayload, state.lastCompletedRows, state.lastCompletedPendingProofRows);
        renderCompletedRealMediaProof(state.lastCompletedPayload, state.lastCompletedRows, state.lastCompletedPendingProofRows, state.lastCompletedPendingPayload);
        renderCompletedFinalTrust(state.lastCompletedPayload, state.lastCompletedRows, state.lastCompletedPendingProofRows, state.lastCompletedPendingPayload);
        renderCompletedPilotEvidencePacket(state.lastCompletedPayload, state.lastCompletedRows, state.lastCompletedPendingProofRows, state.lastCompletedPendingPayload);
      }
      renderCompletedRouteAgreement(
        state.lastCompletedPayload,
        state.lastCompletedRows,
        typeof window.getLastQueuePayload === "function" ? window.getLastQueuePayload() : {},
        typeof window.getLastQueueRows === "function" ? window.getLastQueueRows() : [],
      );
    }

    return {
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
    };
  }

  window.__completedViewEvidenceRouteAgreementModule = {
    createCompletedEvidenceRouteAgreementModule,
  };
})();
