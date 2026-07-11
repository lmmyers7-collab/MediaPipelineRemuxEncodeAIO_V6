(function () {
  function createCompletedPendingProofModel(deps = {}) {
    const {
      getLastPublishReconciliationPayload = function () { return {}; },
    } = deps;
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
        getLastPublishReconciliationPayload()?.completed_pending_proof,
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

    return {
      completedPendingProofDataStatus,
      completedPendingProofDto,
      completedPendingProofDtoMatches,
      completedPendingProofDtoRows,
      completedPendingProofEvidenceText,
      completedPendingProofIsExactPathSignal,
      completedPendingProofIsFinalPlacementReviewSignal,
      completedPendingProofNextAction,
      completedPendingProofRowKey,
      completedPendingProofSignalLabel,
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
      completedProofRows,
    };
  }

  window.__completedPendingProofModelModule = { createCompletedPendingProofModel };
})();
