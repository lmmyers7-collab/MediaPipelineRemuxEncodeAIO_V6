(function () {
  function createCompletedReviewWorkflowOverviewModule(deps = {}) {
    const {
      byId, completedIntegrityLines, completedIntegrityStatus, completedManifestIsAged,
      completedRowHasIntegrityIssue, completedValidationStatus, setText,
      readOnlyBoundary = "Mutation guardrail: read-only evidence; backend routes own output and manifest changes.",
    } = deps;
    const COMPLETED_READ_ONLY_BOUNDARY = readOnlyBoundary;
    function completedProofStripState(statusText) {
      const normalized = String(statusText || "").toLowerCase();
      if (["clear", "ok", "ready", "pass", "consistent", "complete"].some((token) => normalized.includes(token))) return "ok";
      if (["blocked", "missing", "failed", "error", "unavailable"].some((token) => normalized.includes(token))) return "blocked";
      if (["review", "warning", "stale", "aged", "unknown", "check"].some((token) => normalized.includes(token))) return "warning";
      return "unknown";
    }

    function completedProofStripChip(label, state) {
      if (window.mediaPipelineDom?.makeStatusChip) {
        return window.mediaPipelineDom.makeStatusChip(label, state);
      }
      const chip = document.createElement("span");
      chip.className = "status-chip";
      chip.dataset.status = state || "unknown";
      chip.textContent = label || "";
      return chip;
    }

    function renderCompletedProofStrip(id, statusText, lines) {
      const node = byId(id);
      if (!node) return;
      const rowLines = Array.isArray(lines) ? lines.map((line) => String(line || "").trim()).filter(Boolean) : [];
      const state = completedProofStripState(statusText);
      const chips = [
        completedProofStripChip(statusText || "Not loaded", state),
        completedProofStripChip(rowLines.length ? `${rowLines.length} proof lines` : "No proof lines", rowLines.length ? "normal" : "unknown"),
      ];
      rowLines.slice(0, 2).forEach((line) => {
        chips.push(completedProofStripChip(line.replace(/^[-*]\s*/, ""), state));
      });
      node.replaceChildren(...chips);
    }

    function renderCompletedIntegrity(completed, rows) {
      const rowList = Array.isArray(rows) ? rows : [];
      const status = completedIntegrityStatus(completed || {}, rowList);
      const lines = completedIntegrityLines(completed || {}, rowList);
      setText("completed-integrity-status", status);
      renderCompletedProofStrip("completed-integrity-strip", status, lines);
      setText("completed-integrity", lines.join("\n"));
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
      lines.push(COMPLETED_READ_ONLY_BOUNDARY);
      return lines;
    }

    function renderCompletedWorkflow(completed, rows) {
      const rowList = Array.isArray(rows) ? rows : [];
      const status = completedWorkflowStatus(completed || {}, rowList);
      const lines = completedWorkflowLines(completed || {}, rowList);
      setText("completed-workflow-status", status);
      renderCompletedProofStrip("completed-workflow-strip", status, lines);
      setText("completed-workflow", lines.join("\n"));
    }

    return {
      completedProofStripState, completedProofStripChip, renderCompletedProofStrip,
      renderCompletedIntegrity, completedWorkflowStatus, completedWorkflowLines, renderCompletedWorkflow,    };
  }

  window.__completedReviewWorkflowOverviewModule = {
    createCompletedReviewWorkflowOverviewModule,
  };
})();
