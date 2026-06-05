// completed/review/healthSignals.js
// Split child of completedView.review.js. Owns healthy and benign completed-row predicates.

(function () {
  "use strict";

  function createCompletedReviewHealthSignalsModule(deps = {}) {
    const completedRowHasIntegrityIssue = typeof deps.completedRowHasIntegrityIssue === "function" ? deps.completedRowHasIntegrityIssue : () => false;
    const completedSizeDeltaPercent = typeof deps.completedSizeDeltaPercent === "function" ? deps.completedSizeDeltaPercent : () => Number.NaN;

    function completedRowHasBasicHealthyEvidence(row) {
      const consistency = String(row?.consistency_status || "").toLowerCase();
      return row?.output_exists !== false
        && row?.sidecar_exists !== false
        && !row?.size_growth_over_5
        && !row?.size_policy_exceeded
        && !completedRowHasIntegrityIssue(row)
        && (!consistency || ["ok", "healthy", "consistent", "consistent-looking"].includes(consistency));
    }

    function completedRowHasSmallHealthySizeGrowth(row) {
      const delta = completedSizeDeltaPercent(row);
      if (!Number.isFinite(delta) || Math.abs(delta) > 1) return false;
      const flags = Array.isArray(row?.review_flags)
        ? row.review_flags.map((flag) => String(flag || "").trim().toLowerCase()).filter(Boolean)
        : [];
      const benignRuntimeAlreadyProcessed = String(row?.runtime_outcome_status || "").toLowerCase().includes("succeed")
        && String(row?.runtime_outcome_error_code || row?.runtime_outcome_reason || "").toLowerCase() === "already_processed";
      const benignFlags = ["size_growth", "remuxed", "encoded", "runtime_outcome", "runtime_outcome:succeeded"];
      if (benignRuntimeAlreadyProcessed) benignFlags.push("runtime_error:already_processed");
      const significantFlags = flags.filter((flag) => !benignFlags.includes(flag));
      const concern = String(row?.primary_concern || "").trim().toLowerCase();
      const concernTokens = concern.split(/[,;]/).map((token) => token.trim()).filter(Boolean);
      return completedRowHasBasicHealthyEvidence(row)
        && !significantFlags.length
        && (!concern
          || concern === "size_growth"
          || concern.includes("no output, sidecar, size, or runtime blocker")
          || concernTokens.every((token) => benignFlags.includes(token)));
    }

    function completedRowLooksHealthy(row) {
      const severity = String(row?.operator_severity || "").toLowerCase();
      return completedRowHasBasicHealthyEvidence(row)
        && severity !== "error"
        && (severity !== "warning" || completedRowHasSmallHealthySizeGrowth(row));
    }

    function completedRuntimeAlreadyProcessedIsBenign(row) {
      const runtimeStatus = String(row?.runtime_outcome_status || "").toLowerCase();
      const runtimeError = String(row?.runtime_outcome_error_code || row?.runtime_outcome_reason || "").toLowerCase();
      return completedRowLooksHealthy(row)
        && runtimeStatus.includes("succeed")
        && runtimeError === "already_processed";
    }

    function completedReviewFlagIsBenign(flag, row) {
      const normalized = String(flag || "").trim().toLowerCase();
      if (!normalized) return true;
      if (["remuxed", "encoded"].includes(normalized)) return true;
      if (["runtime_outcome", "runtime_outcome:succeeded"].includes(normalized) && completedRowLooksHealthy(row)) return true;
      if (normalized === "runtime_error:already_processed" && completedRuntimeAlreadyProcessedIsBenign(row)) return true;
      if (normalized === "size_growth") return completedRowHasSmallHealthySizeGrowth(row);
      return false;
    }

    function completedPrimaryConcernIsBenign(row) {
      const concern = String(row?.primary_concern || "").trim().toLowerCase();
      if (!concern || !completedRowLooksHealthy(row)) return false;
      return concern.includes("no output, sidecar, size, or runtime blocker")
        || concern.includes("no blocker in the loaded")
        || concern.includes("no current output blocker")
        || concern.includes("no completed rows are locally flagged")
        || concern.includes("completed outputs look healthy")
        || (concern.includes("size_growth") && completedRowHasSmallHealthySizeGrowth(row))
        || concern.split(/[,;]/).map((token) => token.trim()).filter(Boolean).every((token) => ["size_growth", "runtime_outcome", "runtime_outcome:succeeded", "remuxed", "encoded"].includes(token))
        || (concern.includes("runtime_outcome:succeeded") && concern.includes("runtime_error:already_processed") && completedRuntimeAlreadyProcessedIsBenign(row));
    }

    function completedRowHasBenignAlreadyProcessedOutcome(row) {
      const concern = String(row?.primary_concern || "").trim().toLowerCase();
      const flags = Array.isArray(row?.review_flags)
        ? row.review_flags.map((flag) => String(flag || "").trim().toLowerCase()).filter(Boolean)
        : [];
      const runtimeStatus = String(row?.runtime_outcome_status || "").toLowerCase();
      const runtimeError = String(row?.runtime_outcome_error_code || row?.runtime_outcome_reason || "").toLowerCase();
      const delta = completedSizeDeltaPercent(row);
      const benignFlags = ["size_growth", "remuxed", "encoded", "runtime_outcome", "runtime_outcome:succeeded", "runtime_error:already_processed"];
      const concernTokens = concern.split(/[,;]/).map((token) => token.trim()).filter(Boolean);
      const hasAlreadyProcessed = runtimeError === "already_processed"
        || flags.includes("runtime_error:already_processed")
        || concern.includes("runtime_error:already_processed");
      const hasSucceeded = runtimeStatus.includes("succeed")
        || flags.includes("runtime_outcome:succeeded")
        || concern.includes("runtime_outcome:succeeded");
      const significantFlags = flags.filter((flag) => !benignFlags.includes(flag));
      return completedRowHasBasicHealthyEvidence(row)
        && Number.isFinite(delta)
        && Math.abs(delta) <= 1
        && hasAlreadyProcessed
        && hasSucceeded
        && !significantFlags.length
        && (!concern || completedPrimaryConcernIsBenign(row) || concernTokens.every((token) => benignFlags.includes(token)));
    }

    return {
      completedRowHasBasicHealthyEvidence,
      completedRowHasSmallHealthySizeGrowth,
      completedRowLooksHealthy,
      completedRuntimeAlreadyProcessedIsBenign,
      completedReviewFlagIsBenign,
      completedPrimaryConcernIsBenign,
      completedRowHasBenignAlreadyProcessedOutcome,
    };
  }

  window.__completedViewReviewHealthSignalsModule = {
    createCompletedReviewHealthSignalsModule,
  };
})();
