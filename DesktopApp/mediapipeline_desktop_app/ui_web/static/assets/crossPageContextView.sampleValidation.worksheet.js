// crossPageContextView.sampleValidation.worksheet.js
// Split child of crossPageContextView.sampleValidation.js. Owns read-only
// Sample Validation helper clusters and exposes one temporary factory stash.
// Loaded before the parent; the parent consumes and deletes the stash during load.

(function () {
  "use strict";

  function createCrossPageSvWorksheetModule({
    appendCells,
    byId,
    clearRows,
    crossPageCount,
    crossPageDiagnosticsCounts,
    crossPageRows,
    crossPageSampleRows,
    crossPageSettingsPolicyEvidence,
    crossPageValidationTemplateLines,
    makeRowSelectable,
    sampleValidationPath,
    setText,
    state,
    updateTableStatusLegend,
  } = {}) {
    function crossPageSamplePageStrength(sample, page) {
      const matches = Array.isArray(sample?.matches) ? sample.matches : [];
      if (matches.some((item) => item.page === page && item.strength === "exact")) return "exact";
      if (matches.some((item) => item.page === page && item.strength === "advisory")) return "advisory";
      return "";
    }

    function crossPageWorksheetRow(checkpoint, posture, evidence, nextCheck, detail = []) {
      return { checkpoint, posture, evidence, nextCheck, detail };
    }

    function crossPageWorksheetRunnableCount(queue) {
      if (queue && Object.prototype.hasOwnProperty.call(queue, "runnable_count")) {
        return crossPageCount(queue.runnable_count);
      }
      return crossPageRows(queue).length;
    }

    function crossPageSampleValidationEvidence(context = {}) {
      const log = context.sampleValidation && typeof context.sampleValidation === "object" ? context.sampleValidation : {};
      const readiness = log.readiness && typeof log.readiness === "object" ? log.readiness : {};
      const reconciliation = log.reconciliation && typeof log.reconciliation === "object" ? log.reconciliation : {};
      const pilot = log.pilot_plan && typeof log.pilot_plan === "object" ? log.pilot_plan : {};
      const summary = log.summary && typeof log.summary === "object" ? log.summary : {};
      const records = Array.isArray(log.records) ? log.records : [];
      const decisionCounts = summary.decision_counts && typeof summary.decision_counts === "object" ? summary.decision_counts : {};
      const readinessStatus = String(readiness.operator_status || "not loaded").toLowerCase();
      const reconciliationStatus = String(reconciliation.operator_status || "not loaded").toLowerCase();
      const pilotStatus = String(pilot.operator_status || "not loaded").toLowerCase();
      const blockers = crossPageCount(readiness.blocker_count) + crossPageCount(pilot.blocked_stage_count);
      const stale = reconciliationStatus.includes("stale") || pilotStatus.includes("stale");
      const needsReview = [
        readinessStatus,
        reconciliationStatus,
        pilotStatus,
      ].some((value) => /review|not-ready|not-started|pilot-needed|unknown/.test(value));
      const currentEnough = reconciliationStatus.includes("current") || pilotStatus.includes("current-evidence");
      const sampleRunRequired = pilot.sample_run_required === true ? "yes" : pilot.sample_run_required === false ? "no" : "unknown";
      let status = "warning";
      if (blockers || stale || readinessStatus.includes("blocked") || reconciliationStatus.includes("blocked") || pilotStatus.includes("blocked")) {
        status = "blocked";
      } else if (currentEnough && !needsReview) {
        status = "match";
      } else if (needsReview) {
        status = "warning";
      } else if (!records.length && log.exists === false) {
        status = "warning";
      }
      const accepted = crossPageCount(decisionCounts.accepted);
      const evidence = [
        `records=${records.length}`,
        `accepted=${accepted}`,
        `readiness=${readiness.operator_status || "not loaded"}`,
        `reconciliation=${reconciliation.operator_status || "not loaded"}`,
        `pilot=${pilot.operator_status || "not loaded"}`,
        `sample run required=${sampleRunRequired}`,
      ].join("; ");
      const nextCheck = pilot.next_required_action
        || readiness.safe_next_action
        || reconciliation.safe_next_action
        || summary.safe_next_action
        || "Use Preview Record first and append only after Queue, Completed, Pending Publish, Diagnostics, Settings, and playback evidence agree.";
      return {
        status,
        evidence,
        nextCheck,
        detail: [
          `Log path: ${log.log_path || "not reported"}`,
          `Readiness guardrail: ${readiness.guardrail || "Readiness is advisory only."}`,
          `Reconciliation guardrail: ${reconciliation.guardrail || "Reconciliation is read-only."}`,
          `Pilot guardrail: ${pilot.guardrail || "Pilot plan is read-only."}`,
          "Sample Validation is evidence-only: it can append JSONL notes through the backend route but cannot accept output, clear failures, drain pending publish, launch work, or mutate media.",
        ],
      };
    }

    function crossPageRealMediaWorksheetRows(context = {}) {
      const queue = context.queue || {};
      const completed = context.completed || {};
      const pending = context.pending || {};
      const diagnosticsCounts = crossPageDiagnosticsCounts(context.diagnostics || {});
      const sample = crossPageSampleRows(context || {})[0] || null;
      const settingsEvidence = crossPageSettingsPolicyEvidence(context || {});
      const sampleValidationEvidence = crossPageSampleValidationEvidence(context || {});
      const rows = [];
      const queueStrength = crossPageSamplePageStrength(sample, "Queue");
      const completedStrength = crossPageSamplePageStrength(sample, "Completed");
      const pendingStrength = crossPageSamplePageStrength(sample, "Pending Publish");
      const diagnosticsStrength = crossPageSamplePageStrength(sample, "Diagnostics");

      rows.push(crossPageWorksheetRow(
        "Sample identity",
        sample ? sample.status : "warning",
        sample
          ? `${sample.seed.kind}: ${sample.seed.display}; proof=${sample.proofStrength}; exact=${Array.from(sample.exactPages || []).join(", ") || "none"}; advisory=${Array.from(sample.advisoryPages || []).join(", ") || "none"}`
          : "No selected or recent Queue, Completed, or Pending Publish sample is visible.",
        sample
          ? "Use the same sample across Queue, Completed, Pending Publish, Diagnostics, and Settings before accepting WebView parity."
          : "Refresh pages or select a real Queue/Completed/Pending Publish row before logging a validation result.",
        sample ? crossPageValidationTemplateLines(context || {}) : ["No sample row is available for the worksheet."],
      ));

      rows.push(crossPageWorksheetRow(
        "Queue route decision",
        queue.error ? "blocked" : queueStrength === "exact" ? "match" : queueStrength === "advisory" || crossPageRows(queue).length ? "warning" : "unknown",
        `queue rows=${crossPageRows(queue).length}; runnable=${crossPageWorksheetRunnableCount(queue)}; stale=${queue.snapshot_file_freshness_status || "unknown"}; sample evidence=${queueStrength || "none"}`,
        queueStrength === "exact"
          ? "Open Queue selected-row trace and compare route/remux-vs-encode reason against FFmpeg/run evidence after processing."
          : "Review Queue route evidence before launch; missing Queue evidence means this worksheet cannot prove the sample route.",
        [
          "What Queue can prove: source discovery, route/remux-vs-encode intent, blockers, deferred runtime checks, and launch-safe posture.",
          "What Queue cannot prove: FFmpeg completed, output exists, publish drained, sidecar is current, or Plex playback succeeds.",
        ],
      ));

      rows.push(crossPageWorksheetRow(
        "Completed output and size proof",
        completed.error || crossPageCount(completed.missing_output_count) ? "blocked" : completedStrength === "exact" && !crossPageCount(completed.size_growth_over_5_count) ? "match" : "warning",
        `completed rows=${completed.count || crossPageRows(completed).length || 0}; missing outputs=${crossPageCount(completed.missing_output_count)}; missing sidecars=${crossPageCount(completed.missing_sidecar_count)}; output/sidecar mismatch=${crossPageCount(completed.output_sidecar_mismatch_count)}; size growth >5%=${crossPageCount(completed.size_growth_over_5_count)}; sample evidence=${completedStrength || "none"}`,
        completedStrength === "exact"
          ? "Inspect Completed selected-row output, sidecar, route, subtitle/audio, and size-growth fields before accepting the sample."
          : "Do not accept the sample until Completed has exact output/sidecar proof or the missing proof is explained.",
        [
          "What Completed can prove: manifest history, output/sidecar fields, route metadata, size comparison, runtime outcome correlation, and output-open command results.",
          "What Completed cannot prove by itself: final drain success when output is parked, every Plex client Direct Play result, or a manual file move outside the pipeline.",
        ],
      ));

      rows.push(crossPageWorksheetRow(
        "Pending publish and final destination",
        crossPageCount(pending.issue_count) || crossPageCount(pending.health_count) ? "warning" : pendingStrength === "exact" ? "warning" : "match",
        `pending rows=${pending.count || crossPageRows(pending).length || 0}; ready=${crossPageCount(pending.ready_count)}; issue=${crossPageCount(pending.issue_count)}; health=${crossPageCount(pending.health_count)}; missing payload=${crossPageCount(pending.missing_payload_reference_count)}; sample evidence=${pendingStrength || "none"}`,
        pendingStrength || crossPageRows(pending).length
          ? "Review Pending Publish drain decision and durable drain summary before treating the final destination as complete."
          : "If no pending rows exist, still confirm Completed output points at the expected final destination before accepting.",
        [
          "What Pending Publish can prove: parked payload state, drain blockers, dry-run recovery plan, durable drain summary, and backend-owned publish attempts.",
          "What Pending Publish cannot prove from an empty page: that a missing Completed output was successfully drained earlier.",
        ],
      ));

      rows.push(crossPageWorksheetRow(
        "Diagnostics and run evidence",
        diagnosticsCounts.error ? "blocked" : diagnosticsCounts.warning || diagnosticsStrength ? "warning" : "match",
        `diagnostics error=${diagnosticsCounts.error || 0}; warning=${diagnosticsCounts.warning || 0}; active=${diagnosticsCounts.active || 0}; sample evidence=${diagnosticsStrength || "none"}`,
        diagnosticsCounts.error || diagnosticsCounts.warning || diagnosticsStrength
          ? "Read bounded Run Logs, Last Stderr, ActiveJobs, and State artifacts before retrying or accepting the sample."
          : "No loaded diagnostics issue is visible; still inspect route/run logs for at least one known validation sample.",
        [
          "Diagnostics evidence is a clue, not durable output proof.",
          "Missing diagnostics evidence is not success; compare it with Queue route proof, Completed output proof, and Pending Publish state.",
        ],
      ));

      rows.push(crossPageWorksheetRow(
        "Saved media policy",
        settingsEvidence.status,
        settingsEvidence.summary,
        settingsEvidence.status === "blocked"
          ? "Resolve saved Settings errors/critical risk before launching or accepting a WebView-observed sample."
          : settingsEvidence.status === "warning"
            ? "Compare saved route, size, subtitle, audio, and pending-publish settings against the sample outcome before acceptance."
            : "Saved media-policy posture is loaded; compare the listed policy fields with the observed route/subtitle/audio/size result.",
        settingsEvidence.lines,
      ));

      rows.push(crossPageWorksheetRow(
        "Sample Validation readiness",
        sampleValidationEvidence.status,
        sampleValidationEvidence.evidence,
        sampleValidationEvidence.nextCheck,
        sampleValidationEvidence.detail,
      ));

      rows.push(crossPageWorksheetRow(
        "Acceptance boundary",
        "changed",
        "This worksheet is read-only; the separate Sample Validation Record panel can append evidence-only JSONL but cannot accept, repair, drain, launch, or mutate media.",
        "Preview or append a Sample Validation Record only after comparing Queue, Completed, Pending Publish, Diagnostics, Settings, and playback evidence.",
        [
          "Boundary: this worksheet does not save, accept, repair, rerun, drain, delete, publish, rename, rewrite manifests, or touch media files.",
          "Sample validation records are notes/evidence only and cannot override backend truth, manifests, sidecars, failures, or pending-publish state.",
        ],
      ));
      return rows;
    }

    function crossPageRealMediaWorksheetStatus(context = {}) {
      const rows = crossPageRealMediaWorksheetRows(context || {});
      if (!rows.length) return "No worksheet";
      if (rows.some((row) => row.posture === "blocked")) return "Blocked";
      if (rows.some((row) => ["warning", "unknown", "changed"].includes(row.posture))) return "Needs review";
      return "Ready";
    }

    function crossPageRealMediaWorksheetSummary(context = {}) {
      const rows = crossPageRealMediaWorksheetRows(context || {});
      const counts = rows.reduce((acc, row) => {
        acc[row.posture] = (acc[row.posture] || 0) + 1;
        return acc;
      }, {});
      const sample = crossPageSampleRows(context || {})[0] || null;
      const sampleValidationEvidence = crossPageSampleValidationEvidence(context || {});
      return [
        "Real-media validation worksheet:",
        "Purpose: join Queue route intent, Completed output proof, Pending Publish final-destination proof, Diagnostics run clues, saved media-policy posture, and Sample Validation evidence posture for one known sample.",
        `Sample seed: ${sample ? `${sample.seed.kind}: ${sample.seed.display}` : "none loaded"}`,
        `Rows: ${rows.length}; blocked=${counts.blocked || 0}; warning=${counts.warning || 0}; unknown=${counts.unknown || 0}; match=${counts.match || 0}; boundary=${counts.changed || 0}`,
        `Sample validation: ${sampleValidationEvidence.evidence}`,
        "Use this as a read-only operator handoff after a test run. It is not backend acceptance state and it does not mutate files.",
      ].join("\n");
    }

    function crossPageRealMediaWorksheetDetailLines(row) {
      if (!row) return ["No real-media validation worksheet row selected."];
      const detail = Array.isArray(row.detail) && row.detail.length ? row.detail : ["No additional detail for this checkpoint."];
      return [
        `Checkpoint: ${row.checkpoint}`,
        `Posture: ${row.posture}`,
        "",
        "Evidence:",
        row.evidence || "(none)",
        "",
        "Operator next check:",
        row.nextCheck || "Review owning pages before acting.",
        "",
        "Detail:",
        ...detail,
      ];
    }

    function renderCrossPageRealMediaWorksheet(context = {}) {
      const rows = crossPageRealMediaWorksheetRows(context || {});
      setText("cross-page-real-media-status", crossPageRealMediaWorksheetStatus(context || {}));
      setText("cross-page-real-media-summary", crossPageRealMediaWorksheetSummary(context || {}));
      const tbody = byId("cross-page-real-media-rows");
      if (!tbody) return;
      if (!rows.length) {
        clearRows(tbody, 4, "No real-media validation worksheet rows loaded.");
        updateTableStatusLegend("cross-page-real-media-legend", tbody, "Real-media validation worksheet rows");
        setText("cross-page-real-media-detail", "No real-media validation worksheet row selected.");
        return;
      }
      tbody.replaceChildren();
      rows.forEach((item, index) => {
        const row = document.createElement("tr");
        row.dataset.status = item.posture === "blocked"
          ? "blocked"
          : item.posture === "match"
            ? "match"
            : item.posture === "changed"
              ? "changed"
              : "warning";
        appendCells(row, [
          item.checkpoint,
          item.posture,
          item.evidence,
          item.nextCheck,
        ]);
        makeRowSelectable(row, () => setText("cross-page-real-media-detail", crossPageRealMediaWorksheetDetailLines(item).join("\n")), {
          selected: index === 0,
          label: `Review real-media worksheet ${item.checkpoint}`,
        });
        tbody.appendChild(row);
        if (index === 0) setText("cross-page-real-media-detail", crossPageRealMediaWorksheetDetailLines(item).join("\n"));
      });
      updateTableStatusLegend("cross-page-real-media-legend", tbody, "Real-media validation worksheet rows");
    }

    function sampleValidationPolicyAlignmentPayload(log = {}) {
      return log.policy_alignment && typeof log.policy_alignment === "object" ? log.policy_alignment : {};
    }

    function sampleValidationPolicyAlignmentSummaryLines(log = {}) {
      const policy = sampleValidationPolicyAlignmentPayload(log);
      const lines = Array.isArray(policy.summary_lines) && policy.summary_lines.length
        ? [...policy.summary_lines]
        : [
            `Real-media policy alignment: ${policy.operator_status || "not loaded"}`,
            `Required category settings ready: ${policy.required_ready_count || 0}/${policy.required_count || 0}; review=${policy.review_count || 0}; blocked=${policy.blocked_count || 0}; missing=${policy.missing_count || 0}`,
            `Safe next action: ${policy.safe_next_action || "Refresh Sample Validation and Settings before comparing saved policy to the real-media pilot categories."}`,
          ];
      lines.push(policy.guardrail || "Read-only real-media policy alignment.");
      return lines;
    }

    function sampleValidationSampleSetPayload(log = {}) {
      return log.sample_set_guide && typeof log.sample_set_guide === "object" ? log.sample_set_guide : {};
    }

    function sampleValidationSampleSetRows(log = {}) {
      const guide = sampleValidationSampleSetPayload(log);
      return Array.isArray(guide.rows) ? guide.rows : [];
    }

    function sampleValidationSampleSetState(row = {}) {
      const status = String(row.status || "").trim().toLowerCase();
      if (status === "ready") return "ready";
      if (status === "blocked" || row.severity === "error") return "blocked";
      if (status === "review" || status === "planned" || status === "needs-sample" || row.severity === "warning") return "warning";
      return status || "unknown";
    }

    function sampleValidationSampleSetStatus(log = {}) {
      const guide = sampleValidationSampleSetPayload(log);
      const status = guide.operator_status || "not loaded";
      if (status === "sample-set-ready") return "Sample set ready";
      if (status === "coverage-needed") return "Coverage needed";
      if (status === "pilot-needed") return "Pilot needed";
      if (status === "blocked") return "Blocked";
      if (status === "review") return "Review";
      return `Sample set ${status}`;
    }

    function sampleValidationSampleSetSummaryLines(log = {}) {
      const guide = sampleValidationSampleSetPayload(log);
      const lines = Array.isArray(guide.summary_lines) && guide.summary_lines.length
        ? [...guide.summary_lines]
        : [
            `Recommended real-media sample set: ${guide.operator_status || "not loaded"}`,
            `Rows: ready=${guide.ready_count || 0}; review=${guide.review_count || 0}; planned=${guide.planned_count || 0}; missing=${guide.missing_count || 0}; blocked=${guide.blocked_count || 0}`,
            `Safe next action: ${guide.safe_next_action || "Select a 3-5 file real-media pilot set before relying on WebView daily."}`,
          ];
      const boundary = guide.acceptance_evidence_boundary || "";
      if (boundary && !lines.some((line) => line.includes(boundary))) {
        lines.push(`Acceptance evidence boundary: ${boundary}`);
      }
      lines.push(guide.guardrail || "Read-only representative sample-set guidance.");
      return lines;
    }

    function sampleValidationSampleSetCoverageLine(log = {}) {
      const guide = sampleValidationSampleSetPayload(log);
      const rows = sampleValidationSampleSetRows(log);
      const acceptedMatches = rows.filter((row) => Number(row.accepted_record_match_count || 0) > 0).length;
      const currentMatches = rows.filter((row) => Number(row.current_record_match_count || 0) > 0).length;
      const staleMatches = rows.reduce((count, row) => count + Number(row.stale_record_match_count || 0), 0);
      const reviewMatches = rows.reduce((count, row) => count + Number(row.review_record_match_count || 0), 0);
      const requiredRows = rows.filter((row) => row.required !== false);
      const missing = rows.filter((row) => ["needs-sample", "planned"].includes(String(row.status || ""))).length;
      return [
        `Pilot category coverage: ${guide.operator_status || "not loaded"}`,
        `required ready=${guide.required_ready_count || 0}/${guide.required_count || requiredRows.length}`,
        `current category records=${currentMatches}/${rows.length || "0"}`,
        `historical accepted category records=${acceptedMatches}`,
        `stale=${staleMatches}`,
        `review records=${reviewMatches}`,
        `planned=${guide.planned_count || 0}`,
        `missing=${guide.missing_count || missing}`,
        `review=${guide.review_count || 0}`,
        `blocked=${guide.blocked_count || 0}`,
      ].join("; ");
    }

    function sampleValidationSampleSetDetailLines(row = {}) {
      if (!row || !Object.keys(row).length) return ["No representative sample-set row selected."];
      const sampleExamples = Array.isArray(row.sample_examples) && row.sample_examples.length ? row.sample_examples : [];
      const recordExamples = Array.isArray(row.record_examples) && row.record_examples.length ? row.record_examples : [];
      const owners = Array.isArray(row.owner_pages) && row.owner_pages.length ? row.owner_pages.join(", ") : "Home, Queue, Completed, Diagnostics";
      const lines = [
        `Category: ${row.category || row.category_key || "unknown"}`,
        `Status: ${row.status || "unknown"} (${row.severity || "info"})`,
        `Required: ${row.required === false ? "no" : "yes"}`,
        `Accepted category records: ${row.accepted_record_match_count || 0}; current=${row.current_record_match_count || 0}; stale=${row.stale_record_match_count || 0}; review=${row.review_record_match_count || 0}`,
        `Owner pages: ${owners}`,
        "",
        "Evidence goal:",
        row.evidence_goal || "(none loaded)",
        "",
        "Current evidence:",
        row.evidence || "(none loaded)",
        "",
        "Operator action:",
        row.operator_action || row.safe_next_action || "Add and validate a representative real-media sample.",
        "",
        "Safe next action:",
        row.safe_next_action || "Use backend-owned Launch and Sample Validation evidence for this category.",
      ];
      if (sampleExamples.length) lines.push("", "Worksheet sample examples:", ...sampleExamples.map((item) => `- ${item}`));
      if (recordExamples.length) lines.push("", "Current accepted record examples:", ...recordExamples.map((item) => `- ${item}`));
      lines.push("", row.proof_boundary || "Category proof is advisory until the operator ties a record to this category.", "", row.guardrail || "Read-only sample-set guidance.");
      return lines;
    }

    function sampleValidationSampleSetKey(row = {}, index = 0) {
      return String(row.category_key || row.category || `sample-set-${index + 1}`).trim();
    }

    function selectSampleValidationSampleSetRow(row = {}, key = "") {
      state.selectedSampleValidationSampleSetKey = key || sampleValidationSampleSetKey(row);
      state.selectedSampleValidationSampleSetRow = row || null;
      setText("sample-validation-sample-set-detail", sampleValidationSampleSetDetailLines(row).join("\n"));
    }

    function selectedSampleValidationSampleSet(rows = []) {
      if (!Array.isArray(rows) || !rows.length) return null;
      if (!state.selectedSampleValidationSampleSetKey) return null;
      return rows.find((row, index) => sampleValidationSampleSetKey(row, index) === state.selectedSampleValidationSampleSetKey) || null;
    }

    function sampleValidationCategorySummaryRows(log = {}) {
      return sampleValidationSampleSetRows(log).map((row, index) => {
        const status = String(row.status || "unknown");
        const currentRecords = Number(row.current_record_match_count || 0);
        const acceptedRecords = Number(row.accepted_record_match_count || 0);
        const staleRecords = Number(row.stale_record_match_count || 0);
        const reviewRecords = Number(row.review_record_match_count || 0);
        const worksheetSamples = Number(row.worksheet_sample_count || 0);
        let posture = "Missing sample";
        if (status === "blocked") posture = "Blocked";
        else if (status === "ready" && currentRecords > 0) posture = "Current accepted";
        else if (worksheetSamples > 0 && !currentRecords) posture = "Worksheet only";
        else if (acceptedRecords > 0 && !currentRecords) posture = "Historical accepted";
        else if (staleRecords > 0 || reviewRecords > 0) posture = "Review records";
        else if (status === "planned") posture = "Planned";
        else if (status === "review") posture = "Review";
        const evidence = [
          `current=${currentRecords}`,
          `accepted=${acceptedRecords}`,
          `worksheet=${worksheetSamples}`,
          `stale=${staleRecords}`,
          `review=${reviewRecords}`,
          `required=${row.required === false ? "no" : "yes"}`,
        ].join("; ");
        return {
          key: sampleValidationSampleSetKey(row, index),
          category: row.category || row.category_key || `Category ${index + 1}`,
          category_key: row.category_key || "",
          posture,
          status,
          evidence,
          next_action: row.safe_next_action || row.operator_action || "Run and validate a representative sample for this category.",
          source_row: row,
        };
      });
    }

    function sampleValidationCategorySummaryState(row = {}) {
      const posture = String(row.posture || row.status || "").toLowerCase();
      if (posture.includes("blocked")) return "blocked";
      if (posture.includes("current accepted")) return "match";
      if (posture.includes("worksheet") || posture.includes("historical") || posture.includes("review") || posture.includes("planned") || posture.includes("missing")) return "warning";
      return "unknown";
    }

    function sampleValidationCategorySummaryStatus(log = {}) {
      const guide = sampleValidationSampleSetPayload(log);
      const rows = sampleValidationCategorySummaryRows(log);
      const requiredCount = Number(guide.required_count || 0);
      const blocked = rows.filter((row) => sampleValidationCategorySummaryState(row) === "blocked").length;
      const current = rows.filter((row) => row.posture === "Current accepted").length;
      const review = rows.filter((row) => sampleValidationCategorySummaryState(row) === "warning").length;
      if (!rows.length) return "No categories";
      if (blocked) return "Category blocked";
      if (requiredCount > 0 && current >= requiredCount && !review) return "Categories current";
      if (current) return "Partial current";
      return "Categories need pilots";
    }

    function sampleValidationCategorySummaryLines(log = {}) {
      const guide = sampleValidationSampleSetPayload(log);
      const rows = sampleValidationCategorySummaryRows(log);
      const current = rows.filter((row) => row.posture === "Current accepted").length;
      const worksheetOnly = rows.filter((row) => row.posture === "Worksheet only").length;
      const historical = rows.filter((row) => row.posture === "Historical accepted").length;
      const missing = rows.filter((row) => row.posture === "Missing sample" || row.posture === "Planned").length;
      const blocked = rows.filter((row) => row.posture === "Blocked").length;
      return [
        "Pilot category validation summary:",
        `Summary status: ${sampleValidationCategorySummaryStatus(log)}`,
        `Categories: current accepted=${current}; worksheet only=${worksheetOnly}; historical accepted=${historical}; missing/planned=${missing}; blocked=${blocked}; total=${rows.length}`,
        `Required categories ready: ${guide.required_ready_count || 0}/${guide.required_count || 0}; current accepted records=${guide.current_accepted_record_count || 0}; worksheet samples=${guide.worksheet_sample_count || 0}`,
        "Decision rule: a category is ready only when an accepted validation record for that category remains current against backend evidence; worksheets and historical notes are planning/review evidence only.",
        `Safe next action: ${guide.safe_next_action || "Run representative real-media pilots and append accepted records only after current proof agrees."}`,
        "Mutation guardrail: this summary is read-only and cannot launch, append records, accept output, rerun, drain, publish, repair, save settings, rename, rewrite manifests/sidecars, change media policy, or touch media.",
      ];
    }

    function sampleValidationCategorySummaryDetailLines(row = {}) {
      if (!row || !Object.keys(row).length) {
        return [
          "Pilot category validation summary:",
          "Select a category row to inspect current accepted, worksheet, stale, and review evidence.",
          "Mutation guardrail: this detail panel is read-only.",
        ];
      }
      const source = row.source_row || {};
      const lines = [
        "Pilot category validation summary:",
        `Category: ${row.category || "unknown"}`,
        `Posture: ${row.posture || "unknown"}; backend status=${row.status || "unknown"}`,
        `Evidence: ${row.evidence || ""}`,
        `Safe next action: ${row.next_action || ""}`,
        "",
        "Evidence goal:",
        source.evidence_goal || "(none loaded)",
        "",
        "Operator action:",
        source.operator_action || source.safe_next_action || "Validate a representative real-media sample for this category.",
        "",
        "Proof boundary:",
        source.proof_boundary || "Category proof requires a current accepted record; worksheet and historical records are not enough.",
      ];
      const examples = Array.isArray(source.record_examples) ? source.record_examples : [];
      if (examples.length) lines.push("", "Current accepted record examples:", ...examples.map((item) => `- ${item}`));
      const worksheets = Array.isArray(source.sample_examples) ? source.sample_examples : [];
      if (worksheets.length) lines.push("", "Worksheet sample examples:", ...worksheets.map((item) => `- ${item}`));
      lines.push("", "Mutation guardrail: this row cannot launch, append records, accept output, rerun, drain, publish, repair, save settings, rename, rewrite manifests/sidecars, change media policy, or touch media.");
      return lines;
    }

    function selectedSampleValidationCategorySummaryRow(rows) {
      const list = Array.isArray(rows) ? rows : [];
      return list.find((row) => row.key === state.selectedSampleValidationCategorySummaryKey)
        || list.find((row) => sampleValidationCategorySummaryState(row) === "blocked")
        || list.find((row) => sampleValidationCategorySummaryState(row) === "warning")
        || list[0]
        || null;
    }

    function renderSampleValidationCategorySummary(log = {}) {
      const rows = sampleValidationCategorySummaryRows(log || {});
      if (state.selectedSampleValidationCategorySummaryKey && !rows.some((row) => row.key === state.selectedSampleValidationCategorySummaryKey)) {
        state.selectedSampleValidationCategorySummaryKey = "";
      }
      const selected = selectedSampleValidationCategorySummaryRow(rows);
      setText("sample-validation-category-summary-status", sampleValidationCategorySummaryStatus(log || {}));
      setText("sample-validation-category-summary", sampleValidationCategorySummaryLines(log || {}).join("\n"));
      setText("sample-validation-category-summary-detail", sampleValidationCategorySummaryDetailLines(selected).join("\n"));
      setText("sample-validation-category-summary-legend", "Pilot category validation rows are read-only and cannot launch, append records, accept output, rerun, drain, publish, repair, save settings, rename, rewrite manifests/sidecars, change media policy, or touch media.");
      const tbody = byId("sample-validation-category-summary-rows");
      if (!tbody) return;
      if (!rows.length) {
        clearRows(tbody, 4, "No pilot category validation summary rows loaded.");
        updateTableStatusLegend("sample-validation-category-summary-legend", tbody, "Pilot category validation rows");
        return;
      }
      tbody.replaceChildren();
      rows.forEach((item) => {
        const row = document.createElement("tr");
        row.dataset.status = sampleValidationCategorySummaryState(item);
        appendCells(row, [item.category || "", item.posture || "", item.evidence || "", item.next_action || ""]);
        makeRowSelectable(row, () => {
          state.selectedSampleValidationCategorySummaryKey = item.key || "";
          setText("sample-validation-category-summary-detail", sampleValidationCategorySummaryDetailLines(item).join("\n"));
        }, {
          selected: item.key === selected?.key,
          label: `Review pilot category validation ${item.category || ""}`,
        });
        tbody.appendChild(row);
      });
      updateTableStatusLegend("sample-validation-category-summary-legend", tbody, "Pilot category validation rows");
    }

    function useSelectedSampleSetCategory() {
      const rows = sampleValidationSampleSetRows(state.lastCrossPageContext?.sampleValidation || {});
      const row = state.selectedSampleValidationSampleSetRow || selectedSampleValidationSampleSet(rows);
      const category = String(row?.category_key || "").trim();
      const select = byId("sample-validation-category");
      if (!select) {
        setText("sample-validation-result", "Cannot set pilot category: sample-validation category control is missing.");
        return;
      }
      if (!category) {
        setText("sample-validation-result", "Cannot set pilot category: selected sample-set row has no backend category key.");
        return;
      }
      select.value = category;
      select.dispatchEvent(new Event("change", { bubbles: true }));
      setText(
        "sample-validation-result",
        `Pilot category set to ${category} from Real-Media Sample Set Guide. Preview/Append still writes evidence only and cannot mutate media.`
      );
    }

    function renderSampleValidationSampleSetGuide(log = {}) {
      setText("sample-validation-sample-set-status", sampleValidationSampleSetStatus(log || {}));
      setText("sample-validation-sample-set-summary", sampleValidationSampleSetSummaryLines(log || {}).join("\n"));
      const tbody = byId("sample-validation-sample-set-rows");
      if (!tbody) return;
      const rows = sampleValidationSampleSetRows(log || {});
      if (!rows.length) {
        clearRows(tbody, 4, "No representative sample-set rows loaded.");
        updateTableStatusLegend("sample-validation-sample-set-legend", tbody, "Representative sample-set rows");
        setText("sample-validation-sample-set-detail", sampleValidationSampleSetPayload(log).guardrail || "No representative sample-set row selected.");
        return;
      }
      tbody.replaceChildren();
      if (!state.selectedSampleValidationSampleSetKey) {
        state.selectedSampleValidationSampleSetKey = sampleValidationSampleSetKey(rows[0], 0);
      } else if (!rows.some((item, index) => sampleValidationSampleSetKey(item, index) === state.selectedSampleValidationSampleSetKey)) {
        state.selectedSampleValidationSampleSetKey = "";
        state.selectedSampleValidationSampleSetRow = null;
        setText("sample-validation-sample-set-detail", "Sample-set guide refreshed. Previous row is no longer present — select a row to review.");
      }
      state.selectedSampleValidationSampleSetRow = selectedSampleValidationSampleSet(rows);
      rows.forEach((item, index) => {
        const key = sampleValidationSampleSetKey(item, index);
        const row = document.createElement("tr");
        row.dataset.status = sampleValidationSampleSetState(item);
        appendCells(row, [
          item.category || item.category_key || "",
          item.status || "",
          item.required === false ? "No" : "Yes",
          item.evidence || "",
        ]);
        makeRowSelectable(row, () => selectSampleValidationSampleSetRow(item, key), {
          selected: key === state.selectedSampleValidationSampleSetKey,
          label: `Review real-media sample-set category ${item.category || index + 1}`,
        });
        tbody.appendChild(row);
        if (key === state.selectedSampleValidationSampleSetKey) selectSampleValidationSampleSetRow(item, key);
      });
      updateTableStatusLegend("sample-validation-sample-set-legend", tbody, "Representative sample-set rows");
    }

    function sampleValidationWorksheetPayload(log = {}) {
      return log.worksheet_runs && typeof log.worksheet_runs === "object" ? log.worksheet_runs : {};
    }

    function sampleValidationWorksheetRows(log = {}) {
      const worksheet = sampleValidationWorksheetPayload(log);
      return Array.isArray(worksheet.rows) ? worksheet.rows : [];
    }

    function sampleValidationPathToken(value) {
      return String(value || "").trim().replaceAll("\\", "/").toLowerCase();
    }

    function sampleValidationWorksheetRunMatchesSample(run = {}, sample = null) {
      if (!sample) return false;
      const sourcePath = sampleValidationPath(sample, ["source"]);
      const outputPath = sampleValidationPath(sample, ["output", "destination", "runtime output", "parked payload"]);
      const sourceToken = sampleValidationPathToken(sourcePath);
      const outputToken = sampleValidationPathToken(outputPath);
      const sampleLabel = sampleValidationPathToken(sample?.seed?.display || "");
      const samples = Array.isArray(run.samples) ? run.samples : [];
      const packetRows = Array.isArray(run.packet_rows) ? run.packet_rows : [];
      return samples.some((row) => {
        const rowSource = sampleValidationPathToken(row.source_path || "");
        const rowLeaf = sampleValidationPathToken(row.source_leaf || "");
        return Boolean(
          (sourceToken && rowSource && (rowSource === sourceToken || rowSource.endsWith(sourceToken) || sourceToken.endsWith(rowSource)))
          || (outputToken && rowSource && (rowSource === outputToken || rowSource.endsWith(outputToken) || outputToken.endsWith(rowSource)))
          || (sampleLabel && rowLeaf && sampleLabel.includes(rowLeaf))
        );
      }) || packetRows.some((row) => {
        const label = sampleValidationPathToken(row.sample_label || "");
        return Boolean(sampleLabel && label && (sampleLabel.includes(label) || label.includes(sampleLabel)));
      });
    }

    function sampleValidationWorksheetStatus(context = {}) {
      const worksheet = sampleValidationWorksheetPayload(context.sampleValidation || {});
      const rows = sampleValidationWorksheetRows(context.sampleValidation || {});
      if (worksheet.operator_status === "blocked") return "Worksheet blocked";
      if (!rows.length) return "No worksheet runs";
      if (rows.some((row) => row.operator_status === "blocked")) return "Worksheet blocked";
      if (rows.some((row) => ["needs-evidence", "review"].includes(row.operator_status))) return "Worksheet review";
      return "Worksheet evidence";
    }

    function sampleValidationWorksheetSummaryLines(context = {}) {
      const worksheet = sampleValidationWorksheetPayload(context.sampleValidation || {});
      const rows = sampleValidationWorksheetRows(context.sampleValidation || {});
      const sample = crossPageSampleRows(context || {})[0] || null;
      const matching = rows.filter((row) => sampleValidationWorksheetRunMatchesSample(row, sample)).length;
      const lines = Array.isArray(worksheet.summary_lines) && worksheet.summary_lines.length
        ? [...worksheet.summary_lines]
        : [
            `Generated real-media worksheets: ${worksheet.operator_status || "not loaded"}`,
            `Runs loaded: ${rows.length}; samples=${worksheet.sample_count || 0}; packet rows=${worksheet.packet_row_count || 0}`,
            `Safe next action: ${worksheet.safe_next_action || "Generate a worksheet before the real-media pilot run if you want persistent Markdown evidence."}`,
          ];
      lines.push(`Selected sample worksheet matches: ${sample ? matching : "no sample selected"}`);
      lines.push(worksheet.guardrail || "Worksheet evidence is read-only Markdown context and cannot mutate media or pipeline state.");
      return lines;
    }

    function sampleValidationWorksheetDetailLines(run = {}, sample = null) {
      if (!run || !Object.keys(run).length) return ["No generated worksheet row selected."];
      const samples = Array.isArray(run.samples) ? run.samples : [];
      const packetRows = Array.isArray(run.packet_rows) ? run.packet_rows : [];
      const matches = sampleValidationWorksheetRunMatchesSample(run, sample);
      const lines = [
        `Worksheet: ${run.file_name || "unknown"}`,
        `Run id: ${run.run_id || ""}`,
        `Status: ${run.operator_status || "unknown"}`,
        `Selected sample match: ${matches ? "yes" : sample ? "no" : "no sample selected"}`,
        `Modified: ${run.modified_at || ""}`,
        `Operator: ${run.operator || ""}`,
        `Shell: ${run.shell || ""}`,
        `Path: ${run.path || ""}`,
        "",
        "Evidence:",
        run.evidence || "(none)",
        "",
        "Samples:",
      ];
      if (samples.length) {
        samples.slice(0, 8).forEach((row) => {
          lines.push(`- ${row.sample_number || ""}: ${row.source_path || row.source_leaf || "(blank)"}; category=${row.category || "not filled"}; expected=${row.expected_route || "not filled"}`);
        });
      } else {
        lines.push("- none parsed");
      }
      lines.push("", "Pilot packet rows:");
      if (packetRows.length) {
        packetRows.slice(0, 8).forEach((row) => {
          lines.push(`- ${row.sample_number || ""}: ${row.sample_label || "(blank)"}; status=${row.packet_status || "not filled"}; stop=${row.stop_condition_hit || "not filled"}`);
        });
      } else {
        lines.push("- none parsed yet");
      }
      const warnings = Array.isArray(run.warnings) ? run.warnings : [];
      const errors = Array.isArray(run.errors) ? run.errors : [];
      if (warnings.length) lines.push("", "Warnings:", ...warnings.map((item) => `- ${item}`));
      if (errors.length) lines.push("", "Errors:", ...errors.map((item) => `- ${item}`));
      lines.push("", `Safe next action: ${run.safe_next_action || "Compare worksheet evidence with current backend proof."}`);
      lines.push(run.guardrail || "Worksheet evidence is read-only.");
      return lines;
    }

    function renderSampleValidationWorksheets(context = {}) {
      const log = context.sampleValidation || {};
      const rows = sampleValidationWorksheetRows(log);
      const sample = crossPageSampleRows(context || {})[0] || null;
      setText("sample-validation-worksheet-status", sampleValidationWorksheetStatus(context || {}));
      setText("sample-validation-worksheet-summary", sampleValidationWorksheetSummaryLines(context || {}).join("\n"));
      const tbody = byId("sample-validation-worksheet-rows");
      if (!tbody) return;
      if (!rows.length) {
        clearRows(tbody, 5, "No generated pilot worksheet rows loaded.");
        updateTableStatusLegend("sample-validation-worksheet-legend", tbody, "Generated worksheet rows");
        setText("sample-validation-worksheet-detail", sampleValidationWorksheetPayload(log).guardrail || "No generated worksheet row selected.");
        return;
      }
      tbody.replaceChildren();
      rows.forEach((item, index) => {
        const row = document.createElement("tr");
        const status = item.operator_status || "unknown";
        row.dataset.status = status === "blocked" ? "blocked" : status === "worksheet-evidence-present" ? "match" : "warning";
        const matches = sampleValidationWorksheetRunMatchesSample(item, sample);
        appendCells(row, [
          item.file_name || "",
          status,
          String(item.sample_count || 0),
          String(item.packet_row_count || 0),
          sample ? (matches ? "match" : "no match") : "no sample",
        ]);
        makeRowSelectable(row, () => setText("sample-validation-worksheet-detail", sampleValidationWorksheetDetailLines(item, sample).join("\n")), {
          selected: index === 0,
          label: `Review generated pilot worksheet ${item.file_name || index + 1}`,
        });
        tbody.appendChild(row);
        if (index === 0) setText("sample-validation-worksheet-detail", sampleValidationWorksheetDetailLines(item, sample).join("\n"));
      });
      updateTableStatusLegend("sample-validation-worksheet-legend", tbody, "Generated worksheet rows");
    }

    return {
      crossPageSamplePageStrength,
      crossPageWorksheetRow,
      crossPageSampleValidationEvidence,
      crossPageRealMediaWorksheetRows,
      crossPageRealMediaWorksheetStatus,
      crossPageRealMediaWorksheetSummary,
      crossPageRealMediaWorksheetDetailLines,
      renderCrossPageRealMediaWorksheet,
      sampleValidationPolicyAlignmentPayload,
      sampleValidationPolicyAlignmentSummaryLines,
      sampleValidationSampleSetPayload,
      sampleValidationSampleSetRows,
      sampleValidationSampleSetState,
      sampleValidationSampleSetStatus,
      sampleValidationSampleSetSummaryLines,
      sampleValidationSampleSetCoverageLine,
      sampleValidationSampleSetDetailLines,
      sampleValidationSampleSetKey,
      selectSampleValidationSampleSetRow,
      selectedSampleValidationSampleSet,
      sampleValidationCategorySummaryRows,
      sampleValidationCategorySummaryState,
      sampleValidationCategorySummaryStatus,
      sampleValidationCategorySummaryLines,
      sampleValidationCategorySummaryDetailLines,
      selectedSampleValidationCategorySummaryRow,
      renderSampleValidationCategorySummary,
      useSelectedSampleSetCategory,
      renderSampleValidationSampleSetGuide,
      sampleValidationWorksheetPayload,
      sampleValidationWorksheetRows,
      sampleValidationPathToken,
      sampleValidationWorksheetRunMatchesSample,
      sampleValidationWorksheetStatus,
      sampleValidationWorksheetSummaryLines,
      sampleValidationWorksheetDetailLines,
      renderSampleValidationWorksheets,
    };
  }

  window.__crossPageSvWorksheetModule = { createCrossPageSvWorksheetModule };
})();
