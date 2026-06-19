(function () {
  function createCrossPageSampleValidationModule(deps = {}) {
    const {
      apiPost,
      appendCells,
      appendCommandResult,
      byId,
      clearRows,
      crossPageCount,
      crossPageDiagnosticsCounts,
      crossPageFormatCounts,
      crossPageRows,
      crossPageSampleRows,
      crossPageSettingsPolicyEvidence,
      crossPageValidationTemplateLines,
      crossPageSampleValidationState: state = {},
      makeRowSelectable,
      refreshAll,
      sampleValidationCheckFields: SAMPLE_VALIDATION_CHECK_FIELDS = [],
      setText,
      updateTableStatusLegend,
    } = deps;

    // -------------------------------------------------------------------------
    // Consume nested Sample Validation split children.
    // Child stashes are temporary and deleted immediately after factory calls.
    // -------------------------------------------------------------------------

    const __svNoop = function () {};

    const __worksheetMod = window.__crossPageSvWorksheetModule || {};
    delete window.__crossPageSvWorksheetModule;
    const _worksheet = typeof __worksheetMod.createCrossPageSvWorksheetModule === "function"
      ? __worksheetMod.createCrossPageSvWorksheetModule({
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
      })
      : {};
    const {
      crossPageSamplePageStrength = __svNoop,
      crossPageWorksheetRow = __svNoop,
      crossPageSampleValidationEvidence = __svNoop,
      crossPageRealMediaWorksheetRows = __svNoop,
      crossPageRealMediaWorksheetStatus = __svNoop,
      crossPageRealMediaWorksheetSummary = __svNoop,
      crossPageRealMediaWorksheetDetailLines = __svNoop,
      renderCrossPageRealMediaWorksheet = __svNoop,
      sampleValidationPolicyAlignmentPayload = __svNoop,
      sampleValidationPolicyAlignmentSummaryLines = __svNoop,
      sampleValidationSampleSetPayload = __svNoop,
      sampleValidationSampleSetRows = __svNoop,
      sampleValidationSampleSetState = __svNoop,
      sampleValidationSampleSetStatus = __svNoop,
      sampleValidationSampleSetSummaryLines = __svNoop,
      sampleValidationSampleSetCoverageLine = __svNoop,
      sampleValidationSampleSetDetailLines = __svNoop,
      sampleValidationSampleSetKey = __svNoop,
      selectSampleValidationSampleSetRow = __svNoop,
      selectedSampleValidationSampleSet = __svNoop,
      sampleValidationCategorySummaryRows = __svNoop,
      sampleValidationCategorySummaryState = __svNoop,
      sampleValidationCategorySummaryStatus = __svNoop,
      sampleValidationCategorySummaryLines = __svNoop,
      sampleValidationCategorySummaryDetailLines = __svNoop,
      selectedSampleValidationCategorySummaryRow = __svNoop,
      renderSampleValidationCategorySummary = __svNoop,
      useSelectedSampleSetCategory = __svNoop,
      renderSampleValidationSampleSetGuide = __svNoop,
      sampleValidationWorksheetPayload = __svNoop,
      sampleValidationWorksheetRows = __svNoop,
      sampleValidationPathToken = __svNoop,
      sampleValidationWorksheetRunMatchesSample = __svNoop,
      sampleValidationWorksheetStatus = __svNoop,
      sampleValidationWorksheetSummaryLines = __svNoop,
      sampleValidationWorksheetDetailLines = __svNoop,
      renderSampleValidationWorksheets = __svNoop,
    } = _worksheet;

    const __runbookMod = window.__crossPageSvRunbookModule || {};
    delete window.__crossPageSvRunbookModule;
    const _runbook = typeof __runbookMod.createCrossPageSvRunbookModule === "function"
      ? __runbookMod.createCrossPageSvRunbookModule({
        appendCells,
        byId,
        clearRows,
        makeRowSelectable,
        setText,
        updateTableStatusLegend,
      })
      : {};
    const {
      sampleValidationGapPayload = __svNoop,
      sampleValidationGapRows = __svNoop,
      sampleValidationGapState = __svNoop,
      sampleValidationGapStatus = __svNoop,
      sampleValidationGapSummaryLines = __svNoop,
      sampleValidationGapDetailLines = __svNoop,
      renderSampleValidationGapSummary = __svNoop,
      sampleValidationRunbookPayload = __svNoop,
      sampleValidationRunbookRows = __svNoop,
      sampleValidationRunbookState = __svNoop,
      sampleValidationRunbookStatus = __svNoop,
      sampleValidationRunbookSummaryLines = __svNoop,
      sampleValidationRunbookMarkdownLines = __svNoop,
      sampleValidationRunbookDetailLines = __svNoop,
      renderSampleValidationRunbook = __svNoop,
      sampleValidationPilotPlanLines = __svNoop,
      sampleValidationCutoverPayload = __svNoop,
      sampleValidationCutoverRows = __svNoop,
      sampleValidationCutoverState = __svNoop,
      sampleValidationCutoverStatus = __svNoop,
      sampleValidationCutoverSummaryLines = __svNoop,
      sampleValidationCutoverDetailLines = __svNoop,
      renderSampleValidationCutoverGate = __svNoop,
      sampleValidationExecutionRows = __svNoop,
      sampleValidationExecutionState = __svNoop,
      sampleValidationExecutionStatus = __svNoop,
      sampleValidationExecutionSummaryLines = __svNoop,
      sampleValidationExecutionDetailLines = __svNoop,
      renderSampleValidationExecutionChecklist = __svNoop,
    } = _runbook;

    const __recordsMod = window.__crossPageSvRecordsModule || {};
    delete window.__crossPageSvRecordsModule;
    const _records = typeof __recordsMod.createCrossPageSvRecordsModule === "function"
      ? __recordsMod.createCrossPageSvRecordsModule({
        appendCells,
        byId,
        buildSampleValidationRequest,
        clearRows,
        crossPageSampleRows,
        makeRowSelectable,
        sampleValidationCheckFields: SAMPLE_VALIDATION_CHECK_FIELDS,
        sampleValidationCheckedSummary,
        sampleValidationPath,
        sampleValidationPathToken,
        setText,
        state,
        updateTableStatusLegend,
      })
      : {};
    const {
      sampleValidationRecordRows = __svNoop,
      sampleValidationReconciliationRows = __svNoop,
      sampleValidationReconciliationForRecord = __svNoop,
      sampleValidationRecordMatchesSample = __svNoop,
      sampleValidationRecordComparisonRowsForPaths = __svNoop,
      sampleValidationRecordsMatchingSample = __svNoop,
      sampleValidationRecordDecisionIsAccepted = __svNoop,
      sampleValidationRecordReviewCandidate = __svNoop,
      sampleValidationRecordReviewRowStatus = __svNoop,
      sampleValidationRecordReviewRows = __svNoop,
      sampleValidationRecordReviewStatus = __svNoop,
      sampleValidationRecordReviewSummaryLines = __svNoop,
      sampleValidationRecordReviewDetailLines = __svNoop,
      selectedSampleValidationRecordReviewRow = __svNoop,
      renderSampleValidationRecordReview = __svNoop,
      sampleValidationRecordLines = __svNoop,
      sampleValidationRecordCurrentEvidenceLabel = __svNoop,
      sampleValidationRecordGapLabel = __svNoop,
      sampleValidationRecordRowState = __svNoop,
      renderSampleValidationRecords = __svNoop,
      sampleValidationCompletedPacketRows = __svNoop,
      sampleValidationCompletedPacketPostureStatus = __svNoop,
      sampleValidationCompletedPacketStatus = __svNoop,
      sampleValidationCompletedPolicyReconciliationRow = __svNoop,
      sampleValidationCompletedPolicyReconciliationStatus = __svNoop,
      sampleValidationCompletedPacketSummaryLines = __svNoop,
      sampleValidationCompletedPacketDetailLines = __svNoop,
      sampleValidationCompletedPacketMarkdownLines = __svNoop,
      selectedSampleValidationCompletedPacketRow = __svNoop,
      renderSampleValidationCompletedPacketHandoff = __svNoop,
      sampleValidationAcceptanceCheckLabels = __svNoop,
      sampleValidationAcceptanceGateRowStatus = __svNoop,
      sampleValidationAcceptanceGateRows = __svNoop,
      sampleValidationAcceptanceGateStatus = __svNoop,
      sampleValidationAcceptanceGateSummaryLines = __svNoop,
      sampleValidationAcceptanceGateDetailLines = __svNoop,
      selectedSampleValidationAcceptanceGateRow = __svNoop,
      renderSampleValidationAcceptanceGate = __svNoop,
    } = _records;

    function sampleValidationProofStrength(sample) {
      if (!sample) return "none";
      const exactCount = sample.exactPages?.size || 0;
      const advisoryCount = sample.advisoryPages?.size || 0;
      if (exactCount >= 2) return "exact-path";
      if (exactCount === 1) return "partial-exact";
      if (advisoryCount > 0) return "filename-advisory";
      return "none";
    }

    function sampleValidationPath(sample, roles) {
      const paths = Array.isArray(sample?.seed?.paths) ? sample.seed.paths : [];
      const roleSet = new Set(roles);
      const match = paths.find((item) => roleSet.has(item.role));
      return String(match?.path || "").trim();
    }

    function sampleValidationEvidence(sample) {
      const result = { queue: [], completed: [], pending_publish: [], diagnostics: [], commands: [] };
      const matches = Array.isArray(sample?.matches) ? sample.matches : [];
      matches.slice(0, 24).forEach((match) => {
        const item = {
          strength: match.strength || "",
          field: match.field || "",
          value: match.value || "",
          note: match.note || "",
        };
        if (match.page === "Queue") result.queue.push(item);
        else if (match.page === "Completed") result.completed.push(item);
        else if (match.page === "Pending Publish") result.pending_publish.push(item);
        else if (match.page === "Diagnostics") result.diagnostics.push(item);
      });
      return result;
    }

    function sampleValidationChecks(evidence) {
      return {
        queue_route_checked: Boolean(evidence.queue.length),
        ffmpeg_log_checked: Boolean(evidence.diagnostics.length),
        subtitle_checked: false,
        audio_checked: false,
        completed_output_checked: Boolean(evidence.completed.length),
        sidecar_manifest_checked: Boolean(evidence.completed.length),
        size_growth_checked: Boolean(evidence.completed.length),
        pending_publish_checked: Boolean(evidence.pending_publish.length),
        diagnostics_checked: Boolean(evidence.diagnostics.length),
      };
    }

    function sampleValidationChecksFromUi() {
      const result = { ...state.sampleValidationManualChecks };
      SAMPLE_VALIDATION_CHECK_FIELDS.forEach(([key, , id]) => {
        const input = byId(id);
        if (input) result[key] = Boolean(input.checked);
      });
      return result;
    }

    function sampleValidationMergedChecks(autoChecks = {}) {
      const manualChecks = sampleValidationChecksFromUi();
      const merged = { ...autoChecks };
      SAMPLE_VALIDATION_CHECK_FIELDS.forEach(([key]) => {
        merged[key] = Boolean(autoChecks[key] || manualChecks[key]);
      });
      merged.ffmpeg_log_checked = Boolean(merged.ffmpeg_log_checked || merged.diagnostics_checked);
      return merged;
    }

    function sampleValidationShellSurface() {
      const bootstrap = window.MEDIA_PIPELINE_BOOTSTRAP || {};
      const value = String(bootstrap.shellSurface || bootstrap.shell_surface || "webview").toLowerCase();
      return value === "tauri" ? "tauri" : "webview";
    }

    function syncSampleValidationCheckControls(autoChecks = {}) {
      const manualChecks = { ...state.sampleValidationManualChecks };
      const checkedLabels = [];
      const manualLabels = [];
      SAMPLE_VALIDATION_CHECK_FIELDS.forEach(([key, label, id]) => {
        const checked = Boolean(autoChecks[key] || manualChecks[key]);
        const input = byId(id);
        if (input) {
          input.checked = checked;
          input.dataset.autoEvidence = autoChecks[key] ? "true" : "false";
          input.dataset.manualEvidence = manualChecks[key] ? "true" : "false";
        }
        if (checked) checkedLabels.push(label);
        if (manualChecks[key]) manualLabels.push(label);
      });
      setText(
        "sample-validation-check-status",
        `Checks ready: ${checkedLabels.length}/${SAMPLE_VALIDATION_CHECK_FIELDS.length}; manual: ${manualLabels.length ? manualLabels.join(", ") : "none"}`
      );
    }

    function sampleValidationCheckedSummary(checks) {
      const source = checks && typeof checks === "object" ? checks : {};
      const labels = [
        ["queue_route_checked", "queue route"],
        ["ffmpeg_log_checked", "ffmpeg/log"],
        ...SAMPLE_VALIDATION_CHECK_FIELDS.filter(([key]) => key !== "queue_route_checked"),
      ];
      const checked = labels.filter(([key]) => Boolean(source[key])).map(([, label]) => label);
      const missing = labels.filter(([key]) => !source[key]).map(([, label]) => label);
      return [
        `checked=${checked.length ? checked.join(", ") : "none"}`,
        `manual/missing=${missing.length ? missing.join(", ") : "none"}`,
      ].join("; ");
    }

    function sampleValidationLogSummaryLines(log = {}) {
      const summary = log.summary && typeof log.summary === "object" ? log.summary : {};
      const latest = summary.latest && typeof summary.latest === "object" ? summary.latest : {};
      const lines = [
        `Log posture: ${summary.operator_status || (log.exists ? "unknown" : "not-started")}`,
        `History decisions: ${crossPageFormatCounts(summary.decision_counts)}`,
        `Proof strengths: ${crossPageFormatCounts(summary.proof_strength_counts)}`,
        `Pilot categories: ${crossPageFormatCounts(summary.sample_category_counts)}`,
        `Loaded evidence counts: ${crossPageFormatCounts(summary.evidence_counts)}`,
      ];
      if (latest.record_id || latest.sample_label || latest.created_at) {
        lines.push(`Latest record: ${latest.created_at || "unknown time"}; decision=${latest.operator_decision || "unknown"}; proof=${latest.proof_strength || "unknown"}; category=${latest.sample_category || "general"}; sample=${latest.sample_label || latest.source_path || latest.output_path || latest.record_id || "unknown"}`);
      } else {
        lines.push("Latest record: none loaded");
      }
      lines.push(`History next action: ${summary.safe_next_action || "Run a known sample and compare current Queue, Completed, Pending Publish, and Diagnostics evidence before trusting WebView daily-driver behavior."}`);
      return lines;
    }

    function sampleValidationAuditPayload(log = {}) {
      return log.validation_audit && typeof log.validation_audit === "object" ? log.validation_audit : {};
    }

    function sampleValidationAuditSummaryLines(log = {}) {
      const audit = sampleValidationAuditPayload(log);
      const lines = Array.isArray(audit.summary_lines) && audit.summary_lines.length
        ? [...audit.summary_lines]
        : [
            `Real-media validation audit: ${audit.operator_status || "not loaded"}`,
            `Required rows ready: ${audit.required_ready_count || 0}/${audit.required_count || 0}; blocked=${audit.blocked_count || 0}; missing_required=${audit.missing_required_count || 0}; review_required=${audit.review_required_count || 0}`,
            `Safe next action: ${audit.safe_next_action || "Refresh Sample Validation after Queue, Completed, Pending Publish, Diagnostics, Settings, and generated worksheet evidence loads."}`,
          ];
      lines.push(audit.guardrail || "Boundary: validation audit is read-only. It cannot launch, append records, accept outputs, publish/drain, repair, save settings, rename, rewrite manifests, or touch media.");
      return lines;
    }

    function sampleValidationReadinessLines(log = {}) {
      const readiness = log.readiness && typeof log.readiness === "object" ? log.readiness : {};
      const rows = Array.isArray(readiness.rows) ? readiness.rows : [];
      const lines = [
        `Backend readiness: ${readiness.operator_status || "not loaded"}`,
        `Required evidence ready: ${readiness.required_ready_count || 0}/${readiness.required_count || 0}; warnings=${readiness.warning_count || 0}; blockers=${readiness.blocker_count || 0}`,
        `Readiness next action: ${readiness.safe_next_action || "Load Queue, Completed, Pending Publish, Diagnostics, and Settings evidence before recording a sample."}`,
      ];
      rows.slice(0, 6).forEach((row) => {
        lines.push(`- ${row.area || "Evidence"}: ${row.status || "unknown"} (${row.severity || "info"}) - ${row.evidence || ""} Next: ${row.next_step || ""}`);
      });
      lines.push(readiness.guardrail || "Readiness is advisory only and does not mutate media or pipeline state.");
      return lines;
    }

    function sampleValidationReconciliationLines(log = {}) {
      const reconciliation = log.reconciliation && typeof log.reconciliation === "object" ? log.reconciliation : {};
      const rows = Array.isArray(reconciliation.rows) ? reconciliation.rows : [];
      const lines = [
        `Current evidence reconciliation: ${reconciliation.operator_status || "not loaded"}`,
        `Records checked: ${reconciliation.checked_count || 0}; current=${reconciliation.current_count || 0}; review=${reconciliation.review_count || 0}; stale=${reconciliation.stale_count || 0}; errors=${reconciliation.error_count || 0}`,
        `Reconciliation next action: ${reconciliation.safe_next_action || "Compare historical validation notes against current Queue, Completed, Pending Publish, and Diagnostics evidence."}`,
      ];
      rows.slice(0, 6).forEach((row) => {
        const missing = Array.isArray(row.missing_current_evidence) && row.missing_current_evidence.length
          ? ` Missing: ${row.missing_current_evidence.join(" ")}`
          : "";
        lines.push(`- ${row.status || "unknown"} (${row.severity || "info"}) ${row.sample_label || row.record_id || "record"} - ${row.evidence || ""}.${missing} Next: ${row.safe_next_action || ""}`);
      });
      lines.push(reconciliation.guardrail || "Reconciliation is read-only and does not mutate media or pipeline state.");
      return lines;
    }

    function buildSampleValidationRequest(context = {}) {
      const sample = crossPageSampleRows(context || {})[0] || null;
      const evidence = sampleValidationEvidence(sample);
      const checks = sampleValidationMergedChecks(sampleValidationChecks(evidence));
      return {
        schema: "sample_validation_record.v1",
        shell: sampleValidationShellSurface(),
        source_path: sampleValidationPath(sample, ["source"]),
        output_path: sampleValidationPath(sample, ["output", "destination", "runtime output", "parked payload"]),
        sample_label: sample?.seed?.display || "",
        sample_category: byId("sample-validation-category")?.value || "",
        proof_strength: sampleValidationProofStrength(sample),
        operator_decision: byId("sample-validation-decision")?.value || "hold_review",
        checks,
        evidence,
        operator_notes: byId("sample-validation-notes")?.value || "",
      };
    }

    function sampleValidationSummaryLines(context = {}) {
      const sample = crossPageSampleRows(context || {})[0] || null;
      const log = context.sampleValidation || {};
      const records = Array.isArray(log.records) ? log.records : [];
      const request = buildSampleValidationRequest(context || {});
      const pendingFailure = (Array.isArray(context.failures) ? context.failures : [])
        .find((item) => item?.name === "pending publish");
      return [
        "Backend-owned sample validation records:",
        "Purpose: persist operator observations from a real sample run without changing pipeline truth.",
        `Current sample: ${sample ? sample.seed.display : "none loaded"}`,
        `Proposed proof strength: ${request.proof_strength}`,
        `Pilot category: ${request.sample_category || "general / not categorized"}`,
        `Proposed evidence coverage: ${sampleValidationCheckedSummary(request.checks)}`,
        `Recent records loaded: ${records.length}`,
        `Log path: ${log.log_path || "not reported"}`,
        pendingFailure ? `Pending Publish proof unavailable: ${pendingFailure.message || "route read failed"}. Treat final-placement evidence as blocked until refresh succeeds.` : "Pending Publish proof: loaded or not required by the selected sample.",
        `WebView cutover gate: ${sampleValidationCutoverPayload(log).operator_status || "not loaded"}`,
        `Real-media validation audit: ${sampleValidationAuditPayload(log).operator_status || "not loaded"}`,
        `Real-media policy alignment: ${sampleValidationPolicyAlignmentPayload(log).operator_status || "not loaded"}`,
        `Evidence gaps: ${sampleValidationGapPayload(log).operator_status || "not loaded"}`,
        `Pilot runbook: ${sampleValidationRunbookPayload(log).operator_status || "not loaded"}`,
        `Real-media sample set: ${sampleValidationSampleSetPayload(log).operator_status || "not loaded"}`,
        sampleValidationSampleSetCoverageLine(log),
        ...sampleValidationAuditSummaryLines(log),
        ...sampleValidationPolicyAlignmentSummaryLines(log),
        ...sampleValidationGapSummaryLines(log),
        ...sampleValidationRunbookSummaryLines(log),
        ...sampleValidationPilotPlanLines(log),
        ...sampleValidationWorksheetSummaryLines(context || {}),
        ...sampleValidationReadinessLines(log),
        ...sampleValidationReconciliationLines(log),
        ...sampleValidationLogSummaryLines(log),
        "Guardrail: records do not mark jobs complete, clear failures, drain pending publish, rewrite manifests/sidecars, launch work, or mutate media files.",
      ];
    }

    function sampleValidationStatus(context = {}) {
      const sample = crossPageSampleRows(context || {})[0] || null;
      const log = context.sampleValidation || {};
      const readiness = log.readiness || {};
      const reconciliation = log.reconciliation || {};
      if ((Array.isArray(context.failures) ? context.failures : []).some((item) => item?.name === "pending publish")) return "Pending proof blocked";
      if (readiness.operator_status === "blocked") return "Readiness blocked";
      if (Array.isArray(log.errors) && log.errors.length) return "Log error";
      if (reconciliation.operator_status === "blocked") return "Evidence blocked";
      if (reconciliation.operator_status === "stale") return "Stale evidence";
      if (readiness.operator_status === "not-ready") return "Needs evidence";
      if (reconciliation.operator_status === "review") return "Evidence review";
      if (readiness.operator_status === "review") return "Readiness review";
      if (readiness.operator_status === "ready-to-record" && sample) return "Ready to preview";
      if (!sample) return "Needs sample";
      if (!log.exists) return "Ready to preview";
      return "Evidence log loaded";
    }

    function sampleValidationStatusState(label) {
      const text = String(label || "").toLowerCase();
      if (text.includes("blocked") || text.includes("error")) return "blocked";
      if (text.includes("stale") || text.includes("review") || text.includes("needs")) return "warning";
      if (text.includes("ready") || text.includes("loaded")) return "ready";
      return "unknown";
    }

    function renderSampleValidationDecisionStrip(context = {}) {
      const strip = byId("sample-validation-decision-strip");
      const summary = byId("sample-validation-decision-strip-summary");
      if (!strip || !summary) return;
      const sample = crossPageSampleRows(context || {})[0] || null;
      const request = buildSampleValidationRequest(context || {});
      const checkEntries = SAMPLE_VALIDATION_CHECK_FIELDS.map(([key]) => key);
      const checkedCount = checkEntries.filter((key) => Boolean(request.checks?.[key])).length;
      const status = sampleValidationStatus(context || {});
      const stateName = sampleValidationStatusState(status);
      strip.dataset.state = stateName;
      summary.textContent = [
        `Decision: ${request.operator_decision || "hold_review"}`,
        `Category: ${request.sample_category || "general"}`,
        `Checks: ${checkedCount}/${checkEntries.length}`,
        `Sample: ${sample?.seed?.display || "none selected"}`,
        `Gate: ${status}`,
      ].join(" | ");
    }

    function renderSampleValidationRecordPanel(context = {}) {
      const sample = crossPageSampleRows(context || {})[0] || null;
      syncSampleValidationCheckControls(sampleValidationChecks(sampleValidationEvidence(sample)));
      const status = sampleValidationStatus(context || {});
      if (typeof setPanelStatus === "function") setPanelStatus("sample-validation-status", status, sampleValidationStatusState(status));
      else setText("sample-validation-status", status);
      setText("sample-validation-summary", sampleValidationSummaryLines(context || {}).join("\n"));
      renderSampleValidationDecisionStrip(context || {});
      renderSampleValidationCompletedPacketHandoff(context || {});
      renderSampleValidationAcceptanceGate(context || {});
      renderSampleValidationRecordReview(context || {});
      renderSampleValidationGapSummary(context.sampleValidation || {});
      renderSampleValidationRunbook(context.sampleValidation || {});
      renderSampleValidationCutoverGate(context.sampleValidation || {});
      renderSampleValidationSampleSetGuide(context.sampleValidation || {});
      renderSampleValidationCategorySummary(context.sampleValidation || {});
      renderSampleValidationExecutionChecklist(context.sampleValidation || {});
      renderSampleValidationWorksheets(context || {});
      renderSampleValidationRecords(context.sampleValidation || {});
    }

    function sampleValidationResultLines(payload = {}) {
      const preview = payload.preview || payload.data?.preview || payload;
      const record = preview.record || {};
      const currentEvidence = preview.current_evidence || payload.data?.current_evidence || {};
      const appendReadiness = preview.append_readiness || payload.data?.append_readiness || {};
      const pilotEvidencePacket = preview.pilot_evidence_packet || payload.data?.pilot_evidence_packet || {};
      const postRunCapture = preview.post_run_capture || payload.data?.post_run_capture || {};
      const lines = [
        `Schema: ${preview.schema_version || payload.schema_version || ""}`,
        `OK: ${Boolean(payload.ok ?? preview.ok)}`,
        `Record id: ${record.record_id || payload.data?.record_id || ""}`,
        `Decision: ${record.operator_decision || ""}`,
        `Proof: ${record.proof_strength || ""}`,
        `Pilot category: ${record.sample_category || "general / not categorized"}`,
        `Log path: ${payload.data?.log_path || preview.log_path || ""}`,
        `Record size: ${payload.data?.record_size_bytes || preview.record_size_bytes || 0} bytes`,
      ];
      if (currentEvidence.schema_version || currentEvidence.status || currentEvidence.evidence) {
        const missing = Array.isArray(currentEvidence.missing_current_evidence) ? currentEvidence.missing_current_evidence : [];
        const artifactErrors = Array.isArray(currentEvidence.artifact_errors) ? currentEvidence.artifact_errors : [];
        lines.push(
          "",
          "Current backend evidence:",
          `Status: ${currentEvidence.status || "unknown"} (${currentEvidence.severity || "warning"})`,
          `Matches: ${currentEvidence.evidence || "not reported"}`,
          `Next action: ${currentEvidence.safe_next_action || "Compare Queue, Completed, Pending Publish, and Diagnostics before appending."}`
        );
        if (missing.length) lines.push("Missing current evidence:", ...missing.map((item) => `- ${item}`));
        if (artifactErrors.length) lines.push("Artifact read problems:", ...artifactErrors.map((item) => `- ${item}`));
        if (currentEvidence.guardrail) lines.push(currentEvidence.guardrail);
      }
      if (pilotEvidencePacket.schema_version || pilotEvidencePacket.operator_status) {
        const rows = Array.isArray(pilotEvidencePacket.rows) ? pilotEvidencePacket.rows : [];
        const stopConditions = Array.isArray(pilotEvidencePacket.stop_conditions) ? pilotEvidencePacket.stop_conditions : [];
        lines.push(
          "",
          "Pilot evidence packet:",
          `Status: ${pilotEvidencePacket.operator_status || "unknown"}`,
          `Required checks: ${pilotEvidencePacket.required_checked_count || 0}/${pilotEvidencePacket.required_check_count || 0}; recommended checks: ${pilotEvidencePacket.recommended_checked_count || 0}/${pilotEvidencePacket.recommended_check_count || 0}`,
          `Rows: ready=${pilotEvidencePacket.ready_count || 0}; review=${pilotEvidencePacket.review_count || 0}; blocked=${pilotEvidencePacket.blocked_count || 0}`,
          `Current backend matches: ${currentEvidence.evidence || "not reported"}`,
          `Next action: ${pilotEvidencePacket.safe_next_action || "Compare Queue, Completed, Pending Publish, Diagnostics, playback, subtitles, audio, and size before appending."}`
        );
        rows.slice(0, 8).forEach((row) => {
          lines.push(`- ${row.checkpoint || "Evidence"}: ${row.status || "unknown"} (${row.severity || "info"}); owner=${row.owner_page || "unknown"}; ${row.evidence || ""} Next: ${row.operator_action || ""}`);
        });
        if (stopConditions.length) lines.push("Stop conditions:", ...stopConditions.slice(0, 4).map((item) => `- ${item}`));
        lines.push(pilotEvidencePacket.guardrail || "Read-only pilot evidence packet.");
      }
      if (postRunCapture.schema_version || postRunCapture.operator_status) {
        const rows = Array.isArray(postRunCapture.rows) ? postRunCapture.rows : [];
        const gaps = Array.isArray(postRunCapture.required_gaps) ? postRunCapture.required_gaps : [];
        const markdown = Array.isArray(postRunCapture.markdown_lines)
          ? postRunCapture.markdown_lines
          : typeof postRunCapture.markdown_text === "string" ? postRunCapture.markdown_text.split(/\r?\n/) : [];
        lines.push(
          "",
          "Post-run evidence capture:",
          `Status: ${postRunCapture.operator_status || "unknown"}`,
          `Rows: ready=${postRunCapture.ready_count || 0}; manual=${postRunCapture.manual_count || 0}; review=${postRunCapture.review_count || 0}; blocked=${postRunCapture.blocked_count || 0}`,
          `Required capture gaps: ${gaps.length ? gaps.join(", ") : "none"}`,
          `Next action: ${postRunCapture.safe_next_action || "Review capture rows before appending."}`
        );
        rows.slice(0, 9).forEach((row) => {
          const missing = Array.isArray(row.missing_capture) && row.missing_capture.length ? ` Missing: ${row.missing_capture.join(", ")}` : "";
          lines.push(`- ${row.checkpoint || "Capture"}: ${row.status || "unknown"} (${row.severity || "info"}); owner=${row.owner_page || "unknown"}; ${row.captured_evidence || ""}${missing} Next: ${row.safe_next_action || ""}`);
        });
        if (markdown.length) {
          lines.push(
            "",
            "Copyable post-run Markdown:",
            ...markdown.slice(0, 38)
          );
        }
        lines.push(postRunCapture.guardrail || "Read-only post-run evidence capture packet.");
      }
      if (appendReadiness.schema_version || appendReadiness.operator_status) {
        const readinessRows = Array.isArray(appendReadiness.rows) ? appendReadiness.rows : [];
        const requiredGaps = Array.isArray(appendReadiness.required_acceptance_gaps) ? appendReadiness.required_acceptance_gaps : [];
        const recommendedGaps = Array.isArray(appendReadiness.recommended_review_gaps) ? appendReadiness.recommended_review_gaps : [];
        lines.push(
          "",
          "Append readiness:",
          `Status: ${appendReadiness.operator_status || "unknown"}`,
          `Append allowed: ${appendReadiness.append_allowed === false ? "no" : "yes"}; accepted-ready: ${appendReadiness.accepted_ready === true ? "yes" : "no"}`,
          `Manual checks complete: ${appendReadiness.manual_checked_count || 0}/${appendReadiness.manual_check_count || 0}; warnings=${appendReadiness.warning_count || 0}; blockers=${appendReadiness.blocker_count || 0}`,
          `Required acceptance gaps: ${requiredGaps.length ? requiredGaps.join(", ") : "none"}`,
          `Recommended review gaps: ${recommendedGaps.length ? recommendedGaps.join(", ") : "none"}`,
          `Current backend proof clean: ${appendReadiness.current_backend_proof_clean === true ? "yes" : "no"}`,
          `Next action: ${appendReadiness.safe_next_action || "Review manual checks and current backend evidence before append."}`
        );
        readinessRows.slice(0, 9).forEach((row) => {
          lines.push(`- ${row.label || row.check || "Check"}: ${row.status || "unknown"} (${row.severity || "info"}) - ${row.evidence || ""} Next: ${row.safe_next_action || ""}`);
        });
        lines.push(appendReadiness.guardrail || "Read-only append-readiness advice.");
      }
      const warnings = payload.warnings || preview.warnings || [];
      const errors = payload.errors || preview.errors || [];
      if (warnings.length) lines.push("", "Warnings:", ...warnings.map((item) => `- ${item}`));
      if (errors.length) lines.push("", "Errors:", ...errors.map((item) => `- ${item}`));
      lines.push("", preview.guardrail || payload.data?.guardrail || "Sample validation records are evidence only.");
      return lines;
    }

    function setSampleValidationActionBusy(kind, busy) {
      const buttons = [
        byId("sample-validation-preview-button"),
        byId("sample-validation-strip-preview-button"),
        byId("sample-validation-append-button"),
        byId("sample-validation-clear-checks-button"),
        byId("sample-validation-strip-clear-checks-button"),
      ].filter(Boolean);
      buttons.forEach((button) => {
        if (!button.dataset.idleText) button.dataset.idleText = button.textContent || "";
        button.disabled = Boolean(busy);
        if (busy) button.setAttribute("aria-busy", "true");
        else button.removeAttribute("aria-busy");
        if (busy && kind === "preview" && button.id.includes("preview")) button.textContent = "Previewing...";
        else if (busy && kind === "append" && button.id.includes("append")) button.textContent = "Appending...";
        else if (busy && kind === "clear" && button.id.includes("clear")) button.textContent = "Clearing...";
        else if (!busy) button.textContent = button.dataset.idleText;
      });
      const active = kind === "append"
        ? byId("sample-validation-append-button")
        : kind === "clear"
          ? byId("sample-validation-clear-checks-button") || byId("sample-validation-strip-clear-checks-button")
          : byId("sample-validation-preview-button") || byId("sample-validation-strip-preview-button");
      if (typeof setInlineActionStatus === "function" && active) {
        setInlineActionStatus(active, busy ? `${kind} in progress...` : `${kind} finished`, busy ? "loading" : "ready");
      }
    }

    async function previewSampleValidationRecord() {
      if (state.sampleValidationInFlight) return;
      state.sampleValidationInFlight = true;
      setSampleValidationActionBusy("preview", true);
      setText("sample-validation-result", "Previewing backend-owned sample validation record...");
      try {
        const result = await apiPost("/api/sample-validation/preview", buildSampleValidationRequest(state.lastCrossPageContext));
        setText("sample-validation-result", sampleValidationResultLines(result).join("\n"));
      } catch (error) {
        setText("sample-validation-result", `Preview failed: ${error?.message || String(error)}`);
      } finally {
        state.sampleValidationInFlight = false;
        setSampleValidationActionBusy("preview", false);
      }
    }

    async function appendSampleValidationRecord() {
      if (state.sampleValidationInFlight) return;
      const request = buildSampleValidationRequest(state.lastCrossPageContext);
      if (request.operator_decision === "accepted") {
        const confirmed = window.confirm(
          "Append this as operator evidence only?\n\nThis will not mark the job complete, clear failures, drain pending publish, rewrite manifests/sidecars, launch work, or mutate media files."
        );
        if (!confirmed) {
          setText("sample-validation-result", "Append cancelled.");
          return;
        }
      }
      state.sampleValidationInFlight = true;
      setSampleValidationActionBusy("append", true);
      setText("sample-validation-result", "Appending backend-owned sample validation record...");
      try {
        const result = await apiPost("/api/sample-validation/append", request);
        appendCommandResult(result);
        setText("sample-validation-result", sampleValidationResultLines(result).join("\n"));
        if (typeof refreshAll === "function") window.setTimeout(refreshAll, 0);
      } catch (error) {
        const message = error?.message || String(error);
        setText("sample-validation-result", `Append failed: ${message}`);
        appendCommandResult({
          command: "sample_validation.append",
          ok: false,
          severity: "error",
          message,
          errors: [message],
          refresh_hint: "sample_validation",
        });
      } finally {
        state.sampleValidationInFlight = false;
        setSampleValidationActionBusy("append", false);
      }
    }

    function clearManualSampleValidationChecks() {
      setSampleValidationActionBusy("clear", true);
      state.sampleValidationManualChecks = {};
      renderSampleValidationRecordPanel(state.lastCrossPageContext || {});
      setText("sample-validation-result", "Manual sample-validation checks cleared. Loaded backend evidence still pre-checks matching items.");
      window.setTimeout(() => setSampleValidationActionBusy("clear", false), 150);
    }

    function initSampleValidationViewEvents() {
      const previewButton = byId("sample-validation-preview-button");
      if (previewButton) previewButton.addEventListener("click", previewSampleValidationRecord);
      const stripPreviewButton = byId("sample-validation-strip-preview-button");
      if (stripPreviewButton) stripPreviewButton.addEventListener("click", previewSampleValidationRecord);
      const appendButton = byId("sample-validation-append-button");
      if (appendButton) appendButton.addEventListener("click", appendSampleValidationRecord);
      const useSampleSetCategoryButton = byId("sample-validation-use-sample-set-category-button");
      if (useSampleSetCategoryButton) useSampleSetCategoryButton.addEventListener("click", useSelectedSampleSetCategory);
      const categorySelect = byId("sample-validation-category");
      if (categorySelect) {
        categorySelect.addEventListener("change", () => {
          renderSampleValidationRecordPanel(state.lastCrossPageContext || {});
        });
      }
      SAMPLE_VALIDATION_CHECK_FIELDS.forEach(([key, , id]) => {
        const input = byId(id);
        if (!input) return;
        input.addEventListener("change", () => {
          state.sampleValidationManualChecks[key] = Boolean(input.checked);
          renderSampleValidationRecordPanel(state.lastCrossPageContext || {});
        });
      });
      const clearChecksButton = byId("sample-validation-clear-checks-button");
      if (clearChecksButton) clearChecksButton.addEventListener("click", clearManualSampleValidationChecks);
      const stripClearChecksButton = byId("sample-validation-strip-clear-checks-button");
      if (stripClearChecksButton) stripClearChecksButton.addEventListener("click", clearManualSampleValidationChecks);
      const decisionSelect = byId("sample-validation-decision");
      if (decisionSelect) {
        decisionSelect.addEventListener("change", () => {
          renderSampleValidationRecordPanel(state.lastCrossPageContext || {});
        });
      }
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
      sampleValidationProofStrength,
      sampleValidationPath,
      sampleValidationEvidence,
      sampleValidationChecks,
      sampleValidationChecksFromUi,
      sampleValidationMergedChecks,
      sampleValidationShellSurface,
      syncSampleValidationCheckControls,
      sampleValidationCheckedSummary,
      sampleValidationLogSummaryLines,
      sampleValidationAuditPayload,
      sampleValidationAuditSummaryLines,
      sampleValidationPolicyAlignmentPayload,
      sampleValidationPolicyAlignmentSummaryLines,
      sampleValidationReadinessLines,
      sampleValidationReconciliationLines,
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
      sampleValidationExecutionRows,
      sampleValidationExecutionState,
      sampleValidationExecutionStatus,
      sampleValidationExecutionSummaryLines,
      sampleValidationExecutionDetailLines,
      renderSampleValidationExecutionChecklist,
      sampleValidationWorksheetPayload,
      sampleValidationWorksheetRows,
      sampleValidationPathToken,
      sampleValidationWorksheetRunMatchesSample,
      sampleValidationWorksheetStatus,
      sampleValidationWorksheetSummaryLines,
      sampleValidationWorksheetDetailLines,
      sampleValidationRecordRows,
      sampleValidationReconciliationRows,
      sampleValidationReconciliationForRecord,
      sampleValidationRecordMatchesSample,
      sampleValidationRecordComparisonRowsForPaths,
      sampleValidationRecordsMatchingSample,
      sampleValidationRecordDecisionIsAccepted,
      sampleValidationRecordReviewCandidate,
      sampleValidationRecordReviewRowStatus,
      sampleValidationRecordReviewRows,
      sampleValidationRecordReviewStatus,
      sampleValidationRecordReviewSummaryLines,
      sampleValidationRecordReviewDetailLines,
      selectedSampleValidationRecordReviewRow,
      renderSampleValidationRecordReview,
      renderSampleValidationWorksheets,
      buildSampleValidationRequest,
      sampleValidationSummaryLines,
      sampleValidationStatus,
      sampleValidationRecordLines,
      sampleValidationRecordCurrentEvidenceLabel,
      sampleValidationRecordGapLabel,
      sampleValidationRecordRowState,
      renderSampleValidationRecords,
      sampleValidationCompletedPacketRows,
      sampleValidationCompletedPacketPostureStatus,
      sampleValidationCompletedPacketStatus,
      sampleValidationCompletedPolicyReconciliationRow,
      sampleValidationCompletedPolicyReconciliationStatus,
      sampleValidationCompletedPacketSummaryLines,
      sampleValidationCompletedPacketDetailLines,
      sampleValidationCompletedPacketMarkdownLines,
      selectedSampleValidationCompletedPacketRow,
      renderSampleValidationCompletedPacketHandoff,
      sampleValidationAcceptanceCheckLabels,
      sampleValidationAcceptanceGateRowStatus,
      sampleValidationAcceptanceGateRows,
      sampleValidationAcceptanceGateStatus,
      sampleValidationAcceptanceGateSummaryLines,
      sampleValidationAcceptanceGateDetailLines,
      selectedSampleValidationAcceptanceGateRow,
      renderSampleValidationAcceptanceGate,
      renderSampleValidationRecordPanel,
      sampleValidationResultLines,
      previewSampleValidationRecord,
      appendSampleValidationRecord,
      initSampleValidationViewEvents
    };
  }

  window.__crossPageSampleValidationModule = {
    createCrossPageSampleValidationModule,
  };
})();
