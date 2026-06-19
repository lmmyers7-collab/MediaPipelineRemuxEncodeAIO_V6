// crossPageContextView.sampleValidation.runbook.js
// Split child of crossPageContextView.sampleValidation.js. Owns read-only
// Sample Validation helper clusters and exposes one temporary factory stash.
// Loaded before the parent; the parent consumes and deletes the stash during load.

(function () {
  "use strict";

  function createCrossPageSvRunbookModule({
    appendCells,
    byId,
    clearRows,
    makeRowSelectable,
    setText,
    updateTableStatusLegend,
  } = {}) {
    function sampleValidationPanelState(message) {
      const text = String(message || "").toLowerCase();
      if (!text || text.includes("not loaded") || text.startsWith("no ")) return "empty";
      if (text.includes("blocked") || text.includes("error")) return "blocked";
      if (text.includes("missing") || text.includes("needed") || text.includes("review") || text.includes("pilot needed") || text.includes("gaps") || text.includes("attention")) return "warning";
      if (text.includes("ready") || text.includes("present") || text.includes("trial")) return "ready";
      return "unknown";
    }

    function setRunbookPanelStatus(id, message, state) {
      if (typeof setPanelStatus === "function") {
        setPanelStatus(id, message, state || sampleValidationPanelState(message));
      } else {
        setText(id, message);
      }
    }

    function sampleValidationGapPayload(log = {}) {
      return log.evidence_gap_summary && typeof log.evidence_gap_summary === "object" ? log.evidence_gap_summary : {};
    }

    function sampleValidationGapRows(log = {}) {
      const payload = sampleValidationGapPayload(log);
      return Array.isArray(payload.rows) ? payload.rows : [];
    }

    function sampleValidationGapState(row = {}) {
      const status = String(row.status || "").trim().toLowerCase();
      if (status === "ready" || status === "manual") return "ready";
      if (status === "blocked" || row.severity === "error") return "blocked";
      if (status === "review" || status === "missing" || status === "unknown" || row.severity === "warning") return "warning";
      return status || "unknown";
    }

    function sampleValidationGapStatus(log = {}) {
      const payload = sampleValidationGapPayload(log);
      const status = payload.operator_status || "not loaded";
      if (status === "ready-looking") return "Required proof present";
      if (status === "missing-required-evidence") return "Missing required proof";
      if (status === "blocked") return "Blocked";
      if (status === "review") return "Review";
      return `Gaps ${status}`;
    }

    function sampleValidationGapSummaryLines(log = {}) {
      const payload = sampleValidationGapPayload(log);
      const lines = Array.isArray(payload.summary_lines) && payload.summary_lines.length
        ? [...payload.summary_lines]
        : [
            `Real-media evidence gap summary: ${payload.operator_status || "not loaded"}`,
            `Rows: ready=${payload.ready_count || 0}; review=${payload.review_count || 0}; missing=${payload.missing_count || 0}; blocked=${payload.blocked_count || 0}`,
            `Required gaps: ${Array.isArray(payload.required_gaps) && payload.required_gaps.length ? payload.required_gaps.join(", ") : "none loaded"}`,
            `Safe next action: ${payload.safe_next_action || "Refresh Sample Validation after Queue, Completed, Pending Publish, Diagnostics, and Settings payloads load."}`,
          ];
      lines.push(payload.guardrail || "Read-only real-media evidence-gap summary.");
      return lines;
    }

    function sampleValidationGapDetailLines(row = {}) {
      if (!row || !Object.keys(row).length) return ["No real-media evidence-gap row selected."];
      const missing = Array.isArray(row.missing_evidence) ? row.missing_evidence.filter(Boolean) : [];
      return [
        `Checkpoint: ${row.checkpoint || "unknown"}`,
        `Status: ${row.status || "unknown"} (${row.severity || "info"})`,
        `Owner page: ${row.owner_page || "unknown"}`,
        `Required: ${row.required === false ? "no" : "yes"}`,
        "",
        "Evidence:",
        row.evidence || "(none loaded)",
        "",
        "Missing evidence:",
        missing.length ? missing.map((item) => `- ${item}`).join("\n") : "none reported",
        "",
        "Safe next action:",
        row.safe_next_action || "Review owning pages before trusting this sample.",
        "",
        row.guardrail || "Read-only evidence-gap row.",
      ];
    }

    function renderSampleValidationGapSummary(log = {}) {
      setRunbookPanelStatus("sample-validation-gap-status", sampleValidationGapStatus(log || {}));
      setText("sample-validation-gap-summary", sampleValidationGapSummaryLines(log || {}).join("\n"));
      const tbody = byId("sample-validation-gap-rows");
      if (!tbody) return;
      const rows = sampleValidationGapRows(log || {});
      if (!rows.length) {
        clearRows(tbody, 5, "No real-media evidence-gap rows loaded.");
        updateTableStatusLegend("sample-validation-gap-legend", tbody, "Real-media evidence-gap rows");
        setText("sample-validation-gap-detail", sampleValidationGapPayload(log).guardrail || "No real-media evidence-gap row selected.");
        return;
      }
      tbody.replaceChildren();
      rows.forEach((item, index) => {
        const missing = Array.isArray(item.missing_evidence) && item.missing_evidence.length
          ? item.missing_evidence.join(", ")
          : "none";
        const row = document.createElement("tr");
        row.dataset.status = sampleValidationGapState(item);
        appendCells(row, [
          item.checkpoint || "",
          item.status || "",
          item.owner_page || "",
          item.required === false ? "No" : "Yes",
          missing,
        ]);
        makeRowSelectable(row, () => setText("sample-validation-gap-detail", sampleValidationGapDetailLines(item).join("\n")), {
          selected: index === 0,
          label: `Review real-media evidence gap ${item.checkpoint || index + 1}`,
        });
        tbody.appendChild(row);
        if (index === 0) setText("sample-validation-gap-detail", sampleValidationGapDetailLines(item).join("\n"));
      });
      updateTableStatusLegend("sample-validation-gap-legend", tbody, "Real-media evidence-gap rows");
    }

    function sampleValidationRunbookPayload(log = {}) {
      return log.pilot_runbook && typeof log.pilot_runbook === "object" ? log.pilot_runbook : {};
    }

    function sampleValidationRunbookRows(log = {}) {
      const payload = sampleValidationRunbookPayload(log);
      return Array.isArray(payload.rows) ? payload.rows : [];
    }

    function sampleValidationRunbookState(row = {}) {
      const status = String(row.status || "").trim().toLowerCase();
      if (status === "ready" || status === "manual") return "ready";
      if (status === "blocked" || row.severity === "error") return "blocked";
      if (status === "review" || status === "missing" || status === "unknown" || row.severity === "warning") return "warning";
      return status || "unknown";
    }

    function sampleValidationRunbookStatus(log = {}) {
      const payload = sampleValidationRunbookPayload(log);
      const status = payload.operator_status || "not loaded";
      if (status === "ready-looking") return "Runbook ready";
      if (status === "missing-required-evidence") return "Runbook gaps";
      if (status === "blocked") return "Runbook blocked";
      if (status === "review") return "Runbook review";
      return `Runbook ${status}`;
    }

    function sampleValidationRunbookSummaryLines(log = {}) {
      const payload = sampleValidationRunbookPayload(log);
      const lines = Array.isArray(payload.summary_lines) && payload.summary_lines.length
        ? [...payload.summary_lines]
        : [
            `Real-media pilot runbook: ${payload.operator_status || "not loaded"}`,
            `Steps: ready=${payload.ready_count || 0}; review=${payload.review_count || 0}; missing=${payload.missing_count || 0}; blocked=${payload.blocked_count || 0}`,
            `Required runbook gaps: ${Array.isArray(payload.required_gaps) && payload.required_gaps.length ? payload.required_gaps.join(", ") : "none loaded"}`,
            `Safe next action: ${payload.safe_next_action || "Refresh Sample Validation after Queue, Completed, Pending Publish, Diagnostics, and Settings payloads load."}`,
          ];
      lines.push(payload.guardrail || "Read-only real-media pilot runbook.");
      return lines;
    }

    function sampleValidationRunbookMarkdownLines(log = {}) {
      const payload = sampleValidationRunbookPayload(log);
      if (Array.isArray(payload.markdown_lines) && payload.markdown_lines.length) return payload.markdown_lines;
      if (typeof payload.markdown_text === "string" && payload.markdown_text.trim()) return payload.markdown_text.split(/\r?\n/);
      return [
        "# Real-Media WebView Pilot Runbook",
        "",
        "No backend-authored pilot runbook is loaded.",
        "",
        "Refresh Sample Validation after Queue, Completed, Pending Publish, Diagnostics, and Settings payloads load.",
        "",
        payload.guardrail || "Read-only real-media pilot runbook.",
      ];
    }

    function sampleValidationRunbookDetailLines(row = {}) {
      if (!row || !Object.keys(row).length) return ["No real-media pilot runbook row selected."];
      const requiredEvidence = Array.isArray(row.required_evidence) ? row.required_evidence.filter(Boolean) : [];
      return [
        `Step: ${row.order || ""}. ${row.step || "unknown"}`,
        `Status: ${row.status || "unknown"} (${row.severity || "info"})`,
        `Owner page: ${row.owner_page || "unknown"}`,
        `Required: ${row.required === false ? "no" : "yes"}`,
        "",
        "Evidence:",
        row.evidence || "(none loaded)",
        "",
        "Required evidence:",
        requiredEvidence.length ? requiredEvidence.map((item) => `- ${item}`).join("\n") : "none reported",
        "",
        "Safe next action:",
        row.safe_next_action || "Review the owning WebView page and backend evidence before proceeding.",
        "",
        row.guardrail || "Read-only pilot runbook row.",
      ];
    }

    function renderSampleValidationRunbook(log = {}) {
      setRunbookPanelStatus("sample-validation-runbook-status", sampleValidationRunbookStatus(log || {}));
      setText("sample-validation-runbook-summary", sampleValidationRunbookSummaryLines(log || {}).join("\n"));
      setText("sample-validation-runbook-markdown", sampleValidationRunbookMarkdownLines(log || {}).join("\n"));
      const tbody = byId("sample-validation-runbook-rows");
      if (!tbody) return;
      const rows = sampleValidationRunbookRows(log || {});
      if (!rows.length) {
        clearRows(tbody, 5, "No real-media pilot runbook rows loaded.");
        updateTableStatusLegend("sample-validation-runbook-legend", tbody, "Real-media pilot runbook rows");
        setText("sample-validation-runbook-detail", sampleValidationRunbookPayload(log).guardrail || "No real-media pilot runbook row selected.");
        return;
      }
      tbody.replaceChildren();
      rows.forEach((item, index) => {
        const row = document.createElement("tr");
        row.dataset.status = sampleValidationRunbookState(item);
        appendCells(row, [
          item.step || "",
          item.status || "",
          item.owner_page || "",
          item.required === false ? "No" : "Yes",
          item.safe_next_action || "",
        ]);
        makeRowSelectable(row, () => setText("sample-validation-runbook-detail", sampleValidationRunbookDetailLines(item).join("\n")), {
          selected: index === 0,
          label: `Review real-media pilot runbook step ${item.order || index + 1}`,
        });
        tbody.appendChild(row);
        if (index === 0) setText("sample-validation-runbook-detail", sampleValidationRunbookDetailLines(item).join("\n"));
      });
      updateTableStatusLegend("sample-validation-runbook-legend", tbody, "Real-media pilot runbook rows");
    }

    function sampleValidationPilotPlanLines(log = {}) {
      const plan = log.pilot_plan && typeof log.pilot_plan === "object" ? log.pilot_plan : {};
      const rows = Array.isArray(plan.rows) ? plan.rows : [];
      const stopConditions = Array.isArray(plan.stop_conditions) ? plan.stop_conditions : [];
      const attention = Array.isArray(plan.pilot_attention) ? plan.pilot_attention : [];
      const lines = [
        `Real-media pilot plan: ${plan.operator_status || "not loaded"}`,
        `Sample run required: ${plan.sample_run_required === true ? "yes" : plan.sample_run_required === false ? "no" : "unknown"}`,
        `Recommended sample count: ${plan.recommended_sample_count || "Start with 1-3 small known files before unattended WebView use."}`,
        `Pilot checkpoints: ready=${plan.ready_stage_count || 0}/${plan.required_stage_count || 0}; manual=${plan.manual_stage_count || 0}; attention=${plan.attention_stage_count || 0}; blocked=${plan.blocked_stage_count || 0}; review=${plan.review_stage_count || 0}`,
        `Pilot next required action: ${plan.next_required_action || plan.safe_next_action || "Select a sample and compare backend-owned evidence before processing."}`,
        `Pilot next action: ${plan.safe_next_action || "Select a small sample and compare backend-owned evidence before processing."}`,
      ];
      if (attention.length) {
        lines.push("Pilot attention:");
        attention.slice(0, 5).forEach((row) => {
          lines.push(`- ${row.stage || "Pilot step"}: ${row.status || "unknown"} (${row.severity || "info"}) - ${row.operator_action || ""}`);
        });
      }
      rows.slice(0, 7).forEach((row) => {
        lines.push(`- ${row.stage || "Pilot step"}: ${row.status || "unknown"} (${row.severity || "info"}) - ${row.evidence || ""} Next: ${row.operator_action || ""}`);
      });
      if (stopConditions.length) {
        lines.push("Stop conditions:", ...stopConditions.slice(0, 5).map((item) => `- ${item}`));
      }
      lines.push(plan.guardrail || "Pilot plan is read-only and cannot launch, accept, publish, rename, or mutate media.");
      return lines;
    }

    function sampleValidationCutoverPayload(log = {}) {
      return log.cutover_gate && typeof log.cutover_gate === "object" ? log.cutover_gate : {};
    }

    function sampleValidationCutoverRows(log = {}) {
      const gate = sampleValidationCutoverPayload(log);
      return Array.isArray(gate.rows) ? gate.rows : [];
    }

    function sampleValidationCutoverState(row = {}) {
      const status = String(row.status || "").trim().toLowerCase();
      if (status === "ready") return "ready";
      if (status === "blocked" || row.severity === "error") return "blocked";
      if (status === "review" || row.severity === "warning") return "warning";
      return status || "unknown";
    }

    function sampleValidationCutoverStatus(log = {}) {
      const gate = sampleValidationCutoverPayload(log);
      const status = gate.operator_status || "not loaded";
      if (status === "ready-for-operator-trial") return "Ready for trial";
      if (status === "pilot-needed") return "Pilot needed";
      if (status === "blocked") return "Blocked";
      if (status === "review") return "Review";
      return `Gate ${status}`;
    }

    function sampleValidationCutoverSummaryLines(log = {}) {
      const gate = sampleValidationCutoverPayload(log);
      const lines = Array.isArray(gate.summary_lines) && gate.summary_lines.length
        ? [...gate.summary_lines]
        : [
            `WebView cutover gate: ${gate.operator_status || "not loaded"}`,
            `Rows: ready=${gate.ready_count || 0}; review=${gate.review_count || 0}; blocked=${gate.blocked_count || 0}; current accepted records=${gate.current_accepted_record_count || 0}`,
            `Safe next action: ${gate.safe_next_action || "Run a small real-media pilot and compare backend-owned evidence before WebView daily use."}`,
          ];
      const boundary = gate.acceptance_evidence_boundary || "";
      if (boundary && !lines.some((line) => line.includes(boundary))) {
        lines.push(`Acceptance evidence boundary: ${boundary}`);
      }
      lines.push(gate.guardrail || "Read-only WebView cutover evidence. This is not a production cutover switch.");
      return lines;
    }

    function sampleValidationCutoverDetailLines(row = {}) {
      if (!row || !Object.keys(row).length) return ["No WebView cutover gate row selected."];
      return [
        `Checkpoint: ${row.checkpoint || "unknown"}`,
        `Status: ${row.status || "unknown"} (${row.severity || "info"})`,
        `Required: ${row.required === false ? "no" : "yes"}`,
        "",
        "Evidence:",
        row.evidence || "(none loaded)",
        "",
        "Safe next action:",
        row.safe_next_action || "Review current sample-validation evidence before expanding WebView use.",
        "",
        row.guardrail || "Read-only cutover-gate evidence.",
      ];
    }

    function renderSampleValidationCutoverGate(log = {}) {
      setRunbookPanelStatus("sample-validation-cutover-status", sampleValidationCutoverStatus(log || {}));
      setText("sample-validation-cutover-summary", sampleValidationCutoverSummaryLines(log || {}).join("\n"));
      const tbody = byId("sample-validation-cutover-rows");
      if (!tbody) return;
      const rows = sampleValidationCutoverRows(log || {});
      if (!rows.length) {
        clearRows(tbody, 4, "No WebView cutover gate rows loaded.");
        updateTableStatusLegend("sample-validation-cutover-legend", tbody, "WebView cutover gate rows");
        setText("sample-validation-cutover-detail", sampleValidationCutoverPayload(log).guardrail || "No WebView cutover gate row selected.");
        return;
      }
      tbody.replaceChildren();
      rows.forEach((item, index) => {
        const row = document.createElement("tr");
        row.dataset.status = sampleValidationCutoverState(item);
        appendCells(row, [
          item.checkpoint || "",
          item.status || "",
          item.required === false ? "No" : "Yes",
          item.evidence || "",
        ]);
        makeRowSelectable(row, () => setText("sample-validation-cutover-detail", sampleValidationCutoverDetailLines(item).join("\n")), {
          selected: index === 0,
          label: `Review WebView cutover gate ${item.checkpoint || index + 1}`,
        });
        tbody.appendChild(row);
        if (index === 0) setText("sample-validation-cutover-detail", sampleValidationCutoverDetailLines(item).join("\n"));
      });
      updateTableStatusLegend("sample-validation-cutover-legend", tbody, "WebView cutover gate rows");
    }

    function sampleValidationExecutionRows(log = {}) {
      const plan = log.pilot_plan && typeof log.pilot_plan === "object" ? log.pilot_plan : {};
      return Array.isArray(plan.execution_checklist) ? plan.execution_checklist : [];
    }

    function sampleValidationExecutionState(row = {}) {
      const status = String(row.status || "").trim().toLowerCase();
      if (status === "ready" || status === "manual") return "ready";
      if (status === "blocked" || row.severity === "error") return "blocked";
      if (status === "review" || row.severity === "warning") return "warning";
      return status || "unknown";
    }

    function sampleValidationExecutionStatus(log = {}) {
      const plan = log.pilot_plan && typeof log.pilot_plan === "object" ? log.pilot_plan : {};
      const rows = sampleValidationExecutionRows(log);
      if (!rows.length) return "No execution checklist";
      const status = plan.operator_status || "unknown";
      const ready = Number(plan.execution_ready_count || 0);
      const required = Number(plan.execution_required_count || 0);
      const attention = Number(plan.execution_attention_count || 0);
      return `Execution ${status}: ready ${ready}/${required}; attention ${attention}`;
    }

    function sampleValidationExecutionSummaryLines(log = {}) {
      const plan = log.pilot_plan && typeof log.pilot_plan === "object" ? log.pilot_plan : {};
      const lines = Array.isArray(plan.execution_summary_lines) ? plan.execution_summary_lines : [];
      if (lines.length) return lines;
      return [
        "Operator-selected real-media sample execution: not loaded",
        "Execution next action: Load backend sample-validation evidence before planning a sample run.",
        "Boundary: execution checklist is read-only guidance and cannot launch, publish, rename, accept, or mutate media.",
      ];
    }

    function sampleValidationExecutionDetailLines(row = {}) {
      if (!row || !Object.keys(row).length) return ["No sample execution checklist row selected."];
      return [
        `Phase: ${row.phase || "unknown"}`,
        `Check: ${row.check || "unknown"}`,
        `Status: ${row.status || "unknown"} (${row.severity || "info"})`,
        `Required: ${row.required === false ? "no" : "yes"}`,
        `Owner page: ${row.owner_page || "unknown"}`,
        "",
        "Backend evidence:",
        row.current_evidence || row.backend_evidence || "(none loaded)",
        "",
        "Expected backend proof:",
        row.backend_evidence || "(none)",
        "",
        "Operator proof:",
        row.operator_proof || "(none)",
        "",
        "Safe next action:",
        row.safe_next_action || "Review this row before trusting the sample run.",
        "",
        "Unsafe if ignored:",
        row.unsafe_if_ignored || "(not specified)",
        "",
        row.guardrail || "Read-only execution checklist; media-affecting behavior remains backend-owned.",
      ];
    }

    function renderSampleValidationExecutionChecklist(log = {}) {
      setRunbookPanelStatus("sample-validation-execution-status", sampleValidationExecutionStatus(log || {}));
      setText("sample-validation-execution-summary", sampleValidationExecutionSummaryLines(log || {}).join("\n"));
      const tbody = byId("sample-validation-execution-rows");
      if (!tbody) return;
      const rows = sampleValidationExecutionRows(log || {});
      if (!rows.length) {
        clearRows(tbody, 5, "No sample execution checklist rows loaded.");
        updateTableStatusLegend("sample-validation-execution-legend", tbody, "Sample execution checklist rows");
        setText("sample-validation-execution-detail", "No sample execution checklist row selected.");
        return;
      }
      tbody.replaceChildren();
      rows.forEach((item, index) => {
        const row = document.createElement("tr");
        row.dataset.status = sampleValidationExecutionState(item);
        appendCells(row, [
          item.phase || "",
          item.check || "",
          item.status || "",
          item.owner_page || "",
          item.required === false ? "No" : "Yes",
        ]);
        makeRowSelectable(row, () => setText("sample-validation-execution-detail", sampleValidationExecutionDetailLines(item).join("\n")), {
          selected: index === 0,
          label: `Review sample execution checklist ${item.phase || ""} ${item.check || index + 1}`,
        });
        tbody.appendChild(row);
        if (index === 0) setText("sample-validation-execution-detail", sampleValidationExecutionDetailLines(item).join("\n"));
      });
      updateTableStatusLegend("sample-validation-execution-legend", tbody, "Sample execution checklist rows");
    }

    return {
      sampleValidationGapPayload,
      sampleValidationGapRows,
      sampleValidationGapState,
      sampleValidationGapStatus,
      sampleValidationGapSummaryLines,
      sampleValidationGapDetailLines,
      renderSampleValidationGapSummary,
      sampleValidationRunbookPayload,
      sampleValidationRunbookRows,
      sampleValidationRunbookState,
      sampleValidationRunbookStatus,
      sampleValidationRunbookSummaryLines,
      sampleValidationRunbookMarkdownLines,
      sampleValidationRunbookDetailLines,
      renderSampleValidationRunbook,
      sampleValidationPilotPlanLines,
      sampleValidationCutoverPayload,
      sampleValidationCutoverRows,
      sampleValidationCutoverState,
      sampleValidationCutoverStatus,
      sampleValidationCutoverSummaryLines,
      sampleValidationCutoverDetailLines,
      renderSampleValidationCutoverGate,
      sampleValidationExecutionRows,
      sampleValidationExecutionState,
      sampleValidationExecutionStatus,
      sampleValidationExecutionSummaryLines,
      sampleValidationExecutionDetailLines,
      renderSampleValidationExecutionChecklist,
    };
  }

  window.__crossPageSvRunbookModule = { createCrossPageSvRunbookModule };
})();
