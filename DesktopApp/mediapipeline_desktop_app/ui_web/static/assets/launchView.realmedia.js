(function () {
  function createLaunchRealMediaModule(deps = {}) {
    const {
      appendCells = function () {},
      byId = function () { return null; },
      clearRows = function () {},
      getLastQueueRows = null,
      getSelectedQueueRow = null,
      launchPilotPathFromRow = function () { return ""; },
      launchPilotReadinessContext = function (context) { return context || {}; },
      launchPilotRowLabel = function () { return ""; },
      makeRowSelectable = null,
      renderLaunchPilotRunReadiness = function () {},
      renderLaunchStartDecisionSummary = function () {},
      setText = function () {},
      state = {},
      updateTableStatusLegend = function () {},
    } = deps;

    function currentLaunchRealMediaContext() {
      return state.context && typeof state.context === "object" ? state.context : {};
    }

    function setLaunchRealMediaContext(context) {
      state.context = context && typeof context === "object" ? context : {};
      return state.context;
    }

  function launchCrossPageView() {
    return window.mediaPipelineCrossPageContextView && typeof window.mediaPipelineCrossPageContextView === "object"
      ? window.mediaPipelineCrossPageContextView
      : {};
  }

  function launchRealMediaProofBaseRows(context = currentLaunchRealMediaContext()) {
    const view = launchCrossPageView();
    if (typeof view.crossPageRealMediaWorksheetRows === "function") return view.crossPageRealMediaWorksheetRows(context || {});
    if (typeof window.crossPageRealMediaWorksheetRows === "function") return window.crossPageRealMediaWorksheetRows(context || {});
    return [];
  }

  function launchRealMediaProofRowKey(row, index) {
    return String(row?.checkpoint || `proof-${index + 1}`)
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "") || `proof-${index + 1}`;
  }

  function launchRealMediaSample(context = currentLaunchRealMediaContext()) {
    const view = launchCrossPageView();
    if (typeof view.crossPageSampleRows === "function") return view.crossPageSampleRows(context || {})[0] || null;
    if (typeof window.crossPageSampleRows === "function") return window.crossPageSampleRows(context || {})[0] || null;
    return null;
  }

  function launchWorksheetRunsPayload(context = currentLaunchRealMediaContext()) {
    const sampleValidation = context?.sampleValidation && typeof context.sampleValidation === "object" ? context.sampleValidation : {};
    return sampleValidation.worksheet_runs && typeof sampleValidation.worksheet_runs === "object" ? sampleValidation.worksheet_runs : {};
  }

  function launchWorksheetRunRows(context = currentLaunchRealMediaContext()) {
    const view = launchCrossPageView();
    const sampleValidation = context?.sampleValidation && typeof context.sampleValidation === "object" ? context.sampleValidation : {};
    if (typeof view.sampleValidationWorksheetRows === "function") return view.sampleValidationWorksheetRows(sampleValidation);
    if (typeof window.sampleValidationWorksheetRows === "function") return window.sampleValidationWorksheetRows(sampleValidation);
    const payload = launchWorksheetRunsPayload(context);
    return Array.isArray(payload.rows) ? payload.rows : [];
  }

  function launchWorksheetRunsMatchingSample(context = currentLaunchRealMediaContext()) {
    const view = launchCrossPageView();
    const matcher = typeof view.sampleValidationWorksheetRunMatchesSample === "function"
      ? view.sampleValidationWorksheetRunMatchesSample
      : typeof window.sampleValidationWorksheetRunMatchesSample === "function"
        ? window.sampleValidationWorksheetRunMatchesSample
        : null;
    const sample = launchRealMediaSample(context);
    const rows = launchWorksheetRunRows(context);
    if (!sample || !matcher) return [];
    return rows.filter((row) => matcher(row, sample));
  }

  function launchWorksheetEvidence(context = currentLaunchRealMediaContext()) {
    const payload = launchWorksheetRunsPayload(context);
    const rows = launchWorksheetRunRows(context);
    const sample = launchRealMediaSample(context);
    const matches = launchWorksheetRunsMatchingSample(context);
    const errors = Array.isArray(payload.errors) ? payload.errors : [];
    const warnings = Array.isArray(payload.warnings) ? payload.warnings : [];
    const blocked = payload.operator_status === "blocked" || rows.some((row) => row.operator_status === "blocked") || errors.length > 0;
    const posture = blocked
      ? "blocked"
      : matches.length
        ? "match"
        : rows.length
          ? "warning"
          : "unknown";
    const sampleLabel = sample?.seed?.display || "no selected sample";
    const evidence = [
      `worksheet status=${payload.operator_status || (rows.length ? "loaded" : "not loaded")}`,
      `runs=${rows.length}`,
      `samples=${payload.sample_count || 0}`,
      `packet rows=${payload.packet_row_count || 0}`,
      `selected sample=${sampleLabel}`,
      `matches=${sample ? matches.length : "no sample"}`,
    ].join("; ");
    const nextCheck = blocked
      ? "Resolve generated worksheet read errors before using worksheet evidence for a pilot start decision."
      : matches.length
        ? "Open Home > Generated Pilot Worksheets and compare the matching worksheet sample/packet rows before pressing Start."
        : rows.length
          ? "Confirm the selected sample is represented in a generated worksheet, or create/update a worksheet before the pilot run."
          : "Generate a real-media validation worksheet before the pilot run if persistent Markdown evidence is expected.";
    const detail = [
      `Worksheet payload status: ${payload.operator_status || "not loaded"}`,
      `Selected sample: ${sampleLabel}`,
      `Worksheet runs loaded: ${rows.length}`,
      `Matching worksheet runs: ${sample ? matches.length : "no selected sample"}`,
      `Parsed sample rows: ${payload.sample_count || 0}`,
      `Parsed pilot packet rows: ${payload.packet_row_count || 0}`,
    ];
    if (matches.length) {
      detail.push("", "Matching worksheet rows:");
      matches.slice(0, 5).forEach((row) => {
        detail.push(`- ${row.file_name || "worksheet"}: status=${row.operator_status || "unknown"}; samples=${row.sample_count || 0}; packet rows=${row.packet_row_count || 0}`);
      });
    } else if (rows.length) {
      detail.push("", "Loaded worksheets without selected-sample match:");
      rows.slice(0, 5).forEach((row) => {
        detail.push(`- ${row.file_name || "worksheet"}: status=${row.operator_status || "unknown"}; samples=${row.sample_count || 0}; packet rows=${row.packet_row_count || 0}`);
      });
    }
    if (warnings.length) detail.push("", "Worksheet warnings:", ...warnings.slice(0, 6).map((item) => `- ${item}`));
    if (errors.length) detail.push("", "Worksheet errors:", ...errors.slice(0, 6).map((item) => `- ${item}`));
    const view = launchCrossPageView();
    const detailBuilder = typeof view.sampleValidationWorksheetDetailLines === "function"
      ? view.sampleValidationWorksheetDetailLines
      : typeof window.sampleValidationWorksheetDetailLines === "function"
        ? window.sampleValidationWorksheetDetailLines
        : null;
    if (detailBuilder && matches[0]) {
      detail.push("", "First matching worksheet detail:");
      detail.push(...detailBuilder(matches[0], sample).slice(0, 28));
    }
    detail.push("", payload.guardrail || "Read-only generated worksheet evidence. It cannot launch, append validation records, accept output, save settings, rename, publish, drain, or touch media.");
    return {
      posture,
      evidence,
      nextCheck,
      detail,
      sample,
      matches,
      rows,
      payload,
    };
  }

  function launchSampleValidationRecordsPayload(context = currentLaunchRealMediaContext()) {
    return context?.sampleValidation && typeof context.sampleValidation === "object" ? context.sampleValidation : {};
  }

  function launchPolicyAlignmentPayload(context = currentLaunchRealMediaContext()) {
    const sampleValidation = launchSampleValidationRecordsPayload(context);
    return sampleValidation.policy_alignment && typeof sampleValidation.policy_alignment === "object" ? sampleValidation.policy_alignment : {};
  }

  function launchPolicyAlignmentRows(context = currentLaunchRealMediaContext()) {
    const payload = launchPolicyAlignmentPayload(context);
    return Array.isArray(payload.rows) ? payload.rows : [];
  }

  function launchQueueIntentText(row = null) {
    const source = row && typeof row === "object" ? row : {};
    const fields = [
      source.route,
      source.route_name,
      source.route_reason,
      source.route_reason_code,
      source.route_decision_summary,
      source.operator_status,
      source.operator_guidance,
      source.media_kind,
      source.phase,
      source.display_name,
      source.relative_path,
      source.source_path,
    ];
    if (Array.isArray(source.route_evidence_lines)) fields.push(...source.route_evidence_lines);
    if (Array.isArray(source.priority_reasons)) fields.push(...source.priority_reasons);
    if (Array.isArray(source.review_flags)) fields.push(...source.review_flags);
    return fields.filter(Boolean).map((item) => String(item)).join(" ").toLowerCase();
  }

  function launchQueueIntentCategoryMatch(row = null, categoryKey = "") {
    const text = launchQueueIntentText(row);
    if (!text) return "missing-row";
    const category = String(categoryKey || "").trim().toLowerCase();
    const hasAny = (tokens) => tokens.some((token) => text.includes(token));
    if (category === "h264-remux-safe") {
      return hasAny(["h.264", "h264", "direct-stream", "direct stream", "remux", "copy"]) ? "visible-route-signal" : "not-visible";
    }
    if (category === "subtitle-srt-generation") {
      return hasAny(["subtitle", "srt", "tx3g", "mov_text", "mov text", "bdpgs", "pgs", "vobsub", "dvd_subtitle", "ass", "ssa"]) ? "visible-route-signal" : "not-visible";
    }
    if (category === "audio-routing") {
      return hasAny(["audio", "aac", "ac3", "eac3", "dts", "truehd", "flac", "channel", "default track", "passthrough", "downmix"]) ? "visible-route-signal" : "not-visible";
    }
    if (category === "encode-size-policy") {
      return hasAny(["encode", "transcode", "size", "growth", "remux", "copy", "h265", "hevc", "x264", "x265", "nvenc", "qsv", "amf"]) ? "visible-route-signal" : "not-visible";
    }
    if (category === "deferred-publish") {
      return hasAny(["deferred", "pending", "publish", "park", "drain", "outsource", "final destination"]) ? "visible-route-signal" : "not-visible";
    }
    return "not-visible";
  }

  function launchPolicyAlignmentQueueIntentEvidence(context = currentLaunchRealMediaContext()) {
    const merged = launchPilotReadinessContext(context);
    const queueRows = typeof getLastQueueRows === "function" ? getLastQueueRows() : (Array.isArray(merged.queue?.rows) ? merged.queue.rows : []);
    const selectedQueue = typeof getSelectedQueueRow === "function" ? getSelectedQueueRow() : null;
    const selectedSample = launchRealMediaSample(merged);
    const selectedRow = selectedQueue || selectedSample?.seed?.row || queueRows[0] || null;
    const label = launchPilotRowLabel(selectedRow) || selectedSample?.seed?.display || "(no representative Queue row)";
    const sourcePath = launchPilotPathFromRow(selectedRow);
    const payload = launchPolicyAlignmentPayload(merged);
    const policyRows = launchPolicyAlignmentRows(merged);
    const requiredRows = policyRows.filter((row) => row.required !== false);
    const blockedRows = requiredRows.filter((row) => ["blocked", "missing"].includes(String(row.status || "").toLowerCase()));
    const reviewRows = requiredRows.filter((row) => String(row.status || "").toLowerCase() === "review");
    const matchedRows = policyRows.filter((row) => launchQueueIntentCategoryMatch(selectedRow, row.category_key) === "visible-route-signal");
    const unmatchedRequired = requiredRows.filter((row) => {
      const status = String(row.status || "").toLowerCase();
      return !["blocked", "missing"].includes(status) && launchQueueIntentCategoryMatch(selectedRow, row.category_key) !== "visible-route-signal";
    });
    const posture = blockedRows.length
      ? "blocked"
      : !policyRows.length || !selectedRow
        ? "unknown"
        : reviewRows.length
          ? "warning"
          : unmatchedRequired.length
            ? "changed"
            : "match";
    const evidence = [
      `policy=${payload.operator_status || "not loaded"}`,
      `required ready=${payload.required_ready_count || 0}/${payload.required_count || requiredRows.length}`,
      `queue intent=${label}`,
      `visible category signals=${matchedRows.length}/${policyRows.length || 0}`,
      `unmatched required signals=${unmatchedRequired.length}`,
      `blocked policy rows=${blockedRows.length}`,
    ].join("; ");
    const nextCheck = blockedRows.length
      ? "Resolve blocked saved-policy rows before using this Queue route for a real-media pilot."
      : !policyRows.length
        ? "Load Sample Validation / saved media-policy alignment before comparing Launch intent to policy."
        : !selectedRow
          ? "Select or load a representative Queue row before trusting policy-to-route comparison."
          : reviewRows.length
            ? "Review saved-policy tradeoffs for the selected Queue route before pressing Start."
            : unmatchedRequired.length
              ? "Read the unmatched category rows below; Queue route text may be too thin to prove subtitle/audio/size policy before the run."
              : "Saved policy categories have visible selected-route signals; backend Start and post-run proof remain authoritative.";
    const detail = [
      "Saved policy vs Queue route evidence packet:",
      `Policy alignment status: ${payload.operator_status || "not loaded"}`,
      `Representative Queue intent: ${label}`,
      `Representative source: ${sourcePath || "not reported"}`,
      `Route: ${selectedRow?.route || selectedRow?.route_name || "not reported"}`,
      `Route reason: ${selectedRow?.route_reason || selectedRow?.route_decision_summary || "not reported"}`,
      `Matched visible policy categories: ${matchedRows.length}/${policyRows.length || 0}`,
      `Unmatched required category signals: ${unmatchedRequired.length}`,
      `Blocked/missing required policy rows: ${blockedRows.length}`,
      `Review required policy rows: ${reviewRows.length}`,
      "",
      "Category comparison rows:",
    ];
    if (policyRows.length) {
      policyRows.forEach((row) => {
        const match = launchQueueIntentCategoryMatch(selectedRow, row.category_key);
        detail.push(`- ${row.category || row.category_key || "Category"}: policy=${row.status || "unknown"}; required=${row.required === false ? "no" : "yes"}; queue signal=${match}; evidence=${row.evidence || "not reported"}`);
      });
    } else {
      detail.push("- No policy alignment category rows loaded.");
    }
    if (unmatchedRequired.length) {
      detail.push("", "Unmatched required queue-route signals:");
      unmatchedRequired.slice(0, 6).forEach((row) => detail.push(`- ${row.category || row.category_key || "Category"}: ${row.safe_next_action || "Confirm this category after backend run evidence is available."}`));
    }
    detail.push(
      "",
      "Advisory boundary: queue-route matching uses loaded route/status text only. Absence of a visible token does not mean backend media policy is wrong; it means Launch cannot prove that policy category from the selected Queue row alone.",
      payload.guardrail || "Read-only real-media policy alignment. It cannot save settings, launch, append records, accept output, publish/drain, repair, rename, rewrite manifests, run FFmpeg, or touch media.",
    );
    return {
      posture,
      pilotPosture: posture === "match" ? "ready" : posture === "blocked" ? "blocked" : posture === "unknown" ? "unknown" : "review",
      evidence,
      nextCheck,
      detail,
      payload,
      policyRows,
      matchedRows,
      unmatchedRequired,
      selectedRow,
    };
  }

  function launchSampleSetGuidePayload(context = currentLaunchRealMediaContext()) {
    const sampleValidation = launchSampleValidationRecordsPayload(context);
    return sampleValidation.sample_set_guide && typeof sampleValidation.sample_set_guide === "object" ? sampleValidation.sample_set_guide : {};
  }

  function launchSampleSetGuideRows(context = currentLaunchRealMediaContext()) {
    const view = launchCrossPageView();
    const sampleValidation = launchSampleValidationRecordsPayload(context);
    if (typeof view.sampleValidationSampleSetRows === "function") return view.sampleValidationSampleSetRows(sampleValidation);
    if (typeof window.sampleValidationSampleSetRows === "function") return window.sampleValidationSampleSetRows(sampleValidation);
    const guide = launchSampleSetGuidePayload(context);
    return Array.isArray(guide.rows) ? guide.rows : [];
  }

  function launchSampleSetCoverageLine(context = currentLaunchRealMediaContext()) {
    const view = launchCrossPageView();
    const sampleValidation = launchSampleValidationRecordsPayload(context);
    if (typeof view.sampleValidationSampleSetCoverageLine === "function") return view.sampleValidationSampleSetCoverageLine(sampleValidation);
    if (typeof window.sampleValidationSampleSetCoverageLine === "function") return window.sampleValidationSampleSetCoverageLine(sampleValidation);
    const guide = launchSampleSetGuidePayload(context);
    const rows = launchSampleSetGuideRows(context);
    const explicitMatches = rows.filter((row) => Number(row.accepted_record_match_count || row.current_record_match_count || 0) > 0).length;
    const currentMatches = rows.filter((row) => Number(row.current_record_match_count || 0) > 0).length;
    const staleMatches = rows.reduce((count, row) => count + Number(row.stale_record_match_count || 0), 0);
    const reviewMatches = rows.reduce((count, row) => count + Number(row.review_record_match_count || 0), 0);
    return `Pilot category coverage: ${guide.operator_status || "not loaded"}; required ready=${guide.required_ready_count || 0}/${guide.required_count || 0}; explicit category records=${explicitMatches}/${rows.length || 0}; current=${currentMatches}; stale=${staleMatches}; review records=${reviewMatches}; missing=${guide.missing_count || 0}; review=${guide.review_count || 0}; blocked=${guide.blocked_count || 0}`;
  }

  function launchSampleSetCoverageEvidence(context = currentLaunchRealMediaContext()) {
    const guide = launchSampleSetGuidePayload(context);
    const rows = launchSampleSetGuideRows(context);
    const requiredRows = rows.filter((row) => row.required !== false);
    const blockedRows = rows.filter((row) => row.status === "blocked");
    const nonReadyRequired = requiredRows.filter((row) => row.status !== "ready");
    const acceptedRows = rows.filter((row) => Number(row.accepted_record_match_count || 0) > 0);
    const currentRows = rows.filter((row) => Number(row.current_record_match_count || 0) > 0);
    const staleRecords = rows.reduce((count, row) => count + Number(row.stale_record_match_count || 0), 0);
    const reviewRecords = rows.reduce((count, row) => count + Number(row.review_record_match_count || 0), 0);
    const reviewRows = rows.filter((row) => ["review", "planned", "needs-sample"].includes(String(row.status || "")));
    const posture = blockedRows.length
      ? "blocked"
      : nonReadyRequired.length
        ? "warning"
        : rows.length
          ? "match"
          : "unknown";
    const evidence = launchSampleSetCoverageLine(context);
    const nextCheck = blockedRows.length
      ? "Resolve blocked Sample Validation / sample-set evidence before using WebView as a pilot shell."
      : nonReadyRequired.length
        ? "Open Home > Real-Media Sample Set Guide and cover missing required categories before daily-driver trial."
        : rows.length
          ? "Keep the explicit category records in the regression set and rerun them after media-policy changes."
          : "Load Sample Validation evidence before using category coverage as Launch proof.";
    const detail = [
      "Pilot category coverage:",
      `Status: ${guide.operator_status || "not loaded"}`,
      `Required ready: ${guide.required_ready_count || 0}/${guide.required_count || requiredRows.length}`,
      `Rows loaded: ${rows.length}`,
      `Current category record matches: ${currentRows.length}`,
      `Accepted/historical category record matches: ${acceptedRows.length}`,
      `Stale category records: ${staleRecords}`,
      `Review category records: ${reviewRecords}`,
      `Current accepted records: ${guide.current_accepted_record_count || 0}`,
      `Worksheet samples: ${guide.worksheet_sample_count || 0}`,
      `Safe next action: ${guide.safe_next_action || nextCheck}`,
      "",
      "Category rows:",
    ];
    if (rows.length) {
      rows.forEach((row) => {
        detail.push(`- ${row.category || row.category_key || "Category"}: ${row.status || "unknown"}; required=${row.required === false ? "no" : "yes"}; accepted=${row.accepted_record_match_count || 0}; current=${row.current_record_match_count || 0}; stale=${row.stale_record_match_count || 0}; review=${row.review_record_match_count || 0}; worksheet samples=${row.worksheet_sample_count || 0}`);
      });
    } else {
      detail.push("- No sample-set guide rows loaded.");
    }
    if (reviewRows.length) {
      detail.push("", "Rows needing pilot attention:");
      reviewRows.slice(0, 6).forEach((row) => detail.push(`- ${row.category || row.category_key || "Category"}: ${row.safe_next_action || row.operator_action || "Add or validate a representative sample."}`));
    }
    detail.push("", guide.guardrail || "Read-only representative sample-set guidance. It cannot launch, accept, publish, save settings, rename, rewrite manifests, or touch media.");
    return {
      posture,
      evidence,
      nextCheck,
      detail,
      guide,
      rows,
    };
  }

  function launchSampleValidationRecordRows(context = currentLaunchRealMediaContext()) {
    const view = launchCrossPageView();
    const sampleValidation = launchSampleValidationRecordsPayload(context);
    if (typeof view.sampleValidationRecordRows === "function") return view.sampleValidationRecordRows(sampleValidation);
    if (typeof window.sampleValidationRecordRows === "function") return window.sampleValidationRecordRows(sampleValidation);
    return Array.isArray(sampleValidation.records) ? sampleValidation.records : [];
  }

  function launchSampleValidationReconciliationRows(context = currentLaunchRealMediaContext()) {
    const view = launchCrossPageView();
    const sampleValidation = launchSampleValidationRecordsPayload(context);
    if (typeof view.sampleValidationReconciliationRows === "function") return view.sampleValidationReconciliationRows(sampleValidation);
    if (typeof window.sampleValidationReconciliationRows === "function") return window.sampleValidationReconciliationRows(sampleValidation);
    const reconciliation = sampleValidation.reconciliation && typeof sampleValidation.reconciliation === "object" ? sampleValidation.reconciliation : {};
    return Array.isArray(reconciliation.rows) ? reconciliation.rows : [];
  }

  function launchSampleValidationRecordReconciliation(record = {}, context = currentLaunchRealMediaContext()) {
    const view = launchCrossPageView();
    const sampleValidation = launchSampleValidationRecordsPayload(context);
    if (typeof view.sampleValidationReconciliationForRecord === "function") {
      return view.sampleValidationReconciliationForRecord(record, sampleValidation);
    }
    if (typeof window.sampleValidationReconciliationForRecord === "function") {
      return window.sampleValidationReconciliationForRecord(record, sampleValidation);
    }
    const recordId = String(record?.record_id || "");
    return launchSampleValidationReconciliationRows(context).find((row) => String(row?.record_id || "") === recordId) || null;
  }

  function launchSampleValidationRecordsMatchingSample(context = currentLaunchRealMediaContext()) {
    const view = launchCrossPageView();
    const sampleValidation = launchSampleValidationRecordsPayload(context);
    const sample = launchRealMediaSample(context);
    if (!sample) return [];
    if (typeof view.sampleValidationRecordsMatchingSample === "function") return view.sampleValidationRecordsMatchingSample(sampleValidation, sample);
    if (typeof window.sampleValidationRecordsMatchingSample === "function") return window.sampleValidationRecordsMatchingSample(sampleValidation, sample);
    const matcher = typeof view.sampleValidationRecordMatchesSample === "function"
      ? view.sampleValidationRecordMatchesSample
      : typeof window.sampleValidationRecordMatchesSample === "function"
        ? window.sampleValidationRecordMatchesSample
        : null;
    const rows = launchSampleValidationRecordRows(context);
    return matcher ? rows.filter((record) => matcher(record, sample)) : [];
  }

  function launchSampleValidationRecordEvidence(context = currentLaunchRealMediaContext()) {
    const sampleValidation = launchSampleValidationRecordsPayload(context);
    const reconciliation = sampleValidation.reconciliation && typeof sampleValidation.reconciliation === "object" ? sampleValidation.reconciliation : {};
    const summary = sampleValidation.summary && typeof sampleValidation.summary === "object" ? sampleValidation.summary : {};
    const rows = launchSampleValidationRecordRows(context);
    const reconciliationRows = launchSampleValidationReconciliationRows(context);
    const sample = launchRealMediaSample(context);
    const matches = launchSampleValidationRecordsMatchingSample(context);
    const errors = Array.isArray(sampleValidation.errors) ? sampleValidation.errors : [];
    const warnings = Array.isArray(sampleValidation.warnings) ? sampleValidation.warnings : [];
    const matchingReconciliations = matches
      .map((record) => launchSampleValidationRecordReconciliation(record, context))
      .filter(Boolean);
    const currentMatches = matchingReconciliations.filter((row) => row.status === "current").length;
    const staleMatches = matchingReconciliations.filter((row) => row.status === "stale").length;
    const reviewMatches = matchingReconciliations.filter((row) => !["current", "stale"].includes(String(row.status || ""))).length;
    const blocked = errors.length > 0 || reconciliation.operator_status === "blocked";
    const posture = blocked
      ? "blocked"
      : staleMatches
        ? "warning"
        : currentMatches
          ? "match"
          : matches.length
            ? "warning"
            : rows.length
              ? "warning"
              : "unknown";
    const sampleLabel = sample?.seed?.display || "no selected sample";
    const evidence = [
      `record log=${summary.operator_status || (sampleValidation.exists ? "loaded" : "not started")}`,
      `records=${rows.length}`,
      `selected sample=${sampleLabel}`,
      `matches=${sample ? matches.length : "no sample"}`,
      `current=${currentMatches}`,
      `stale=${staleMatches}`,
      `review=${reviewMatches}`,
    ].join("; ");
    const nextCheck = blocked
      ? "Resolve sample-validation log errors before using validation records as Launch evidence."
      : currentMatches
        ? "Open Home > Sample Validation records and compare the matching current record before pressing Start."
        : staleMatches
          ? "Treat the matching validation record as stale; refresh Queue/Completed/Diagnostics proof or rerun a small sample before unattended starts."
          : matches.length
            ? "Review the matching validation record because current-evidence reconciliation is not clean."
            : rows.length
              ? "No loaded validation record matches the selected sample; preview/append a record only after a real backend run has current proof."
              : "No sample-validation records exist yet; run a small sample and record evidence before trusting WebView as daily driver.";
    const detail = [
      `Record log status: ${summary.operator_status || (sampleValidation.exists ? "loaded" : "not started")}`,
      `Reconciliation status: ${reconciliation.operator_status || "not loaded"}`,
      `Selected sample: ${sampleLabel}`,
      `Records loaded: ${rows.length}`,
      `Matching records: ${sample ? matches.length : "no selected sample"}`,
      `Matching current records: ${currentMatches}`,
      `Matching stale records: ${staleMatches}`,
      `Matching review records: ${reviewMatches}`,
    ];
    if (matches.length) {
      detail.push("", "Matching sample-validation records:");
      matches.slice(0, 5).forEach((record) => {
        const rec = launchSampleValidationRecordReconciliation(record, context);
        detail.push(`- ${record.record_id || "record"}: decision=${record.operator_decision || "unknown"}; proof=${record.proof_strength || "unknown"}; current=${rec?.status || "not reconciled"}; sample=${record.sample_label || record.source_path || record.output_path || "unknown"}`);
      });
    } else if (rows.length) {
      detail.push("", "Loaded records without selected-sample match:");
      rows.slice(0, 5).forEach((record) => {
        const rec = launchSampleValidationRecordReconciliation(record, context);
        detail.push(`- ${record.record_id || "record"}: decision=${record.operator_decision || "unknown"}; current=${rec?.status || "not reconciled"}; sample=${record.sample_label || record.source_path || record.output_path || "unknown"}`);
      });
    }
    if (warnings.length) detail.push("", "Validation record warnings:", ...warnings.slice(0, 6).map((item) => `- ${item}`));
    if (errors.length) detail.push("", "Validation record errors:", ...errors.slice(0, 6).map((item) => `- ${item}`));
    const view = launchCrossPageView();
    const detailBuilder = typeof view.sampleValidationRecordLines === "function"
      ? view.sampleValidationRecordLines
      : typeof window.sampleValidationRecordLines === "function"
        ? window.sampleValidationRecordLines
        : null;
    if (detailBuilder && matches[0]) {
      detail.push("", "First matching validation record detail:");
      detail.push(...detailBuilder(matches[0], launchSampleValidationRecordReconciliation(matches[0], context)).slice(0, 28));
    }
    detail.push("", sampleValidation.guardrail || "Sample Validation records are read-only operator evidence. They cannot launch, accept output, clear failures, drain, publish, save settings, rename, rewrite manifests, or touch media.");
    return {
      posture,
      evidence,
      nextCheck,
      detail,
      sample,
      matches,
      rows,
      reconciliationRows,
      sampleValidation,
    };
  }

  function launchRealMediaProofRows(context = currentLaunchRealMediaContext()) {
    const rows = launchRealMediaProofBaseRows(context || {}).map((row, index) => ({
      key: launchRealMediaProofRowKey(row, index),
      checkpoint: row.checkpoint || "Proof checkpoint",
      posture: row.posture || "unknown",
      evidence: row.evidence || "No evidence loaded.",
      nextCheck: row.nextCheck || "Review owning pages before acting.",
      detail: Array.isArray(row.detail) ? row.detail : [],
    }));
    const worksheetEvidence = launchWorksheetEvidence(context || {});
    rows.splice(1, 0, {
      key: "generated-worksheet-evidence",
      checkpoint: "Generated worksheet evidence",
      posture: worksheetEvidence.posture,
      evidence: worksheetEvidence.evidence,
      nextCheck: worksheetEvidence.nextCheck,
      detail: worksheetEvidence.detail,
    });
    const recordEvidence = launchSampleValidationRecordEvidence(context || {});
    rows.splice(2, 0, {
      key: "sample-validation-record-evidence",
      checkpoint: "Sample Validation record evidence",
      posture: recordEvidence.posture,
      evidence: recordEvidence.evidence,
      nextCheck: recordEvidence.nextCheck,
      detail: recordEvidence.detail,
    });
    const categoryCoverage = launchSampleSetCoverageEvidence(context || {});
    rows.splice(3, 0, {
      key: "pilot-category-coverage",
      checkpoint: "Pilot category coverage",
      posture: categoryCoverage.posture,
      evidence: categoryCoverage.evidence,
      nextCheck: categoryCoverage.nextCheck,
      detail: categoryCoverage.detail,
    });
    const policyQueueIntent = launchPolicyAlignmentQueueIntentEvidence(context || {});
    rows.splice(4, 0, {
      key: "saved-policy-queue-intent",
      checkpoint: "Saved policy vs Queue route",
      posture: policyQueueIntent.posture,
      evidence: policyQueueIntent.evidence,
      nextCheck: policyQueueIntent.nextCheck,
      detail: policyQueueIntent.detail,
    });
    rows.push({
      key: "launch-proof-boundary",
      checkpoint: "Launch proof boundary",
      posture: "changed",
      evidence: "Launch can request backend-owned work, but it cannot prove FFmpeg output, subtitle/audio result, final publish state, Plex playback, or size-growth acceptance before a real sample finishes.",
      nextCheck: "Run a small known sample, then verify Queue route, Diagnostics run logs, Completed output/sidecar/size, Pending Publish, Settings policy, and Sample Validation evidence before unattended batches.",
      detail: [
        "Proof source: this Launch handoff mirrors Home's Real-Media Validation Worksheet from already-loaded backend payloads.",
        "Operator proof: complete at least one known sample and compare route, subtitle, audio, sidecar, size, publish, and playback evidence.",
        "Mutation guardrail: this panel is read-only and cannot start, accept, repair, rerun, drain, delete, publish, rename, save settings, append validation records, or touch media files.",
      ],
    });
    return rows;
  }

  function launchRealMediaProofStatus(rows = launchRealMediaProofRows()) {
    if (!rows.length) return "No proof";
    if (rows.some((row) => row.posture === "blocked")) return "Blocked proof";
    if (rows.some((row) => ["warning", "unknown", "changed"].includes(row.posture))) return "Needs sample proof";
    return "Evidence loaded";
  }

  function launchRealMediaProofRowStatus(posture) {
    const normalized = String(posture || "").toLowerCase();
    if (normalized === "blocked") return "blocked";
    if (normalized === "match") return "match";
    if (normalized === "changed") return "changed";
    if (normalized === "unknown") return "unknown";
    return "warning";
  }

  function launchRealMediaProofSummaryLines(context = currentLaunchRealMediaContext(), rows = launchRealMediaProofRows(context)) {
    const counts = rows.reduce((acc, row) => {
      const key = row.posture || "unknown";
      acc[key] = (acc[key] || 0) + 1;
      return acc;
    }, {});
    const nonReady = rows.filter((row) => row.posture !== "match");
    const lines = [
      "Launch real-media sample proof handoff:",
      "Purpose: mirror the Home Real-Media Validation Worksheet at the Launch start surface so the operator sees what remains unproven before a daily-driver sample run.",
      `Rows: ${rows.length}; match=${counts.match || 0}; warning=${counts.warning || 0}; unknown=${counts.unknown || 0}; blocked=${counts.blocked || 0}; boundary=${counts.changed || 0}.`,
      `Generated worksheet evidence: ${launchWorksheetEvidence(context || {}).evidence}`,
      `Sample Validation record evidence: ${launchSampleValidationRecordEvidence(context || {}).evidence}`,
      launchSampleSetCoverageLine(context || {}),
      `Saved policy vs Queue route: ${launchPolicyAlignmentQueueIntentEvidence(context || {}).evidence}`,
      "Pre-run boundary: Launch can prove selected intent, saved policy posture, backend preflight, and sample checklist context only; finished-output proof must come later from Completed, Pending Publish, Diagnostics, playback, and Sample Validation.",
      "Decision rule: Launch readiness and backend preflight can approve a start request, but daily-driver trust still requires post-run output, sidecar, subtitle/audio, size, diagnostics, pending-publish, and playback evidence.",
    ];
    if (nonReady.length) {
      lines.push("First action: select each non-match proof row and complete the owning-page check after a small known Run Once sample.");
      nonReady.slice(0, 6).forEach((row) => lines.push(`- ${row.checkpoint}: ${row.posture}; ${row.nextCheck}`));
      if (nonReady.length > 6) lines.push(`- ${nonReady.length - 6} more proof checkpoint(s) need review.`);
    } else {
      lines.push("First action: current loaded evidence has no local proof blockers, but backend Launch and real-media validation remain authoritative.");
    }
    lines.push("Mutation guardrail: this Launch proof handoff is read-only and cannot launch, accept, drain, publish, save settings, rename, append validation records, or touch media files.");
    return lines;
  }

  function selectedLaunchRealMediaProofRow(rows = []) {
    const source = Array.isArray(rows) ? rows : [];
    return source.find((row) => row.key === state.selectedLaunchRealMediaProofKey) || source.find((row) => row.posture !== "match") || source[0] || null;
  }

  function launchRealMediaProofDetailLines(row) {
    if (!row) {
      return [
        "Launch real-media sample proof handoff:",
        "No proof checkpoint is selected.",
        "Refresh the WebView or select a proof row after backend payloads load.",
        "Mutation guardrail: this panel is read-only.",
      ];
    }
    const lines = [
      "Launch real-media sample proof handoff:",
      `Checkpoint: ${row.checkpoint}`,
      `Posture: ${row.posture}`,
      "",
      "Evidence:",
      row.evidence || "(none)",
      "",
      "Operator proof:",
      row.nextCheck || "Review owning pages before acting.",
    ];
    if (row.detail.length) {
      lines.push("", "Detail:");
      row.detail.forEach((item) => lines.push(`- ${item}`));
    }
    lines.push(
      "",
      "Owning pages: Queue for route intent, Completed for output/sidecar/size proof, Diagnostics for run evidence, Pending Publish for parked/final destination proof, Settings for saved policy posture, Home for Sample Validation evidence.",
      "Guardrail: backend launch validation remains authoritative at submit time; this panel is pre-run intent context and only explains post-run proof requirements.",
    );
    return lines;
  }

  function selectLaunchRealMediaProofRow(row) {
    state.selectedLaunchRealMediaProofKey = row?.key || "";
    renderLaunchRealMediaProofHandoff();
  }

  function renderLaunchRealMediaProofHandoff(context = null) {
    if (context && typeof context === "object") setLaunchRealMediaContext(context);
    const rows = launchRealMediaProofRows(currentLaunchRealMediaContext());
    if (state.selectedLaunchRealMediaProofKey && !rows.some((row) => row.key === state.selectedLaunchRealMediaProofKey)) {
      state.selectedLaunchRealMediaProofKey = "";
    }
    const selected = selectedLaunchRealMediaProofRow(rows);
    const status = launchRealMediaProofStatus(rows);
    setText("launch-real-media-proof-status", status);
    const statusNode = byId("launch-real-media-proof-status");
    if (statusNode) statusNode.dataset.state = status === "Blocked proof" ? "blocked" : status === "Evidence loaded" ? "ready" : "warning";
    setText("launch-real-media-proof-summary", launchRealMediaProofSummaryLines(currentLaunchRealMediaContext(), rows).join("\n"));
    setText("launch-real-media-proof-detail", launchRealMediaProofDetailLines(selected).join("\n"));
    const tbody = byId("launch-real-media-proof-rows");
    if (!tbody) return;
    if (!rows.length) {
      clearRows(tbody, 4, "No Launch real-media proof rows loaded.");
      updateTableStatusLegend("launch-real-media-proof-legend", tbody, "Launch real-media proof rows");
      renderLaunchPilotRunReadiness();
      renderLaunchStartDecisionSummary();
      return;
    }
    tbody.replaceChildren();
    rows.forEach((item) => {
      const row = document.createElement("tr");
      row.dataset.status = launchRealMediaProofRowStatus(item.posture);
      appendCells(row, [item.checkpoint, item.posture, item.evidence, item.nextCheck]);
      if (typeof makeRowSelectable === "function") {
        makeRowSelectable(row, () => selectLaunchRealMediaProofRow(item), {
          selected: item.key === selected?.key,
          label: `Launch real-media proof ${item.checkpoint} ${item.posture}`,
        });
      }
      tbody.appendChild(row);
    });
    updateTableStatusLegend("launch-real-media-proof-legend", tbody, "Launch real-media proof rows");
    renderLaunchSampleExecutionChecklist();
  }

  function launchSampleExecutionPlan(context = currentLaunchRealMediaContext()) {
    const sampleValidation = context?.sampleValidation && typeof context.sampleValidation === "object" ? context.sampleValidation : {};
    return sampleValidation.pilot_plan && typeof sampleValidation.pilot_plan === "object" ? sampleValidation.pilot_plan : {};
  }

  function launchSampleExecutionRowKey(row, index) {
    return String(`${row?.phase || "phase"}-${row?.check || `check-${index + 1}`}`)
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "") || `sample-execution-${index + 1}`;
  }

  function launchSampleExecutionRows(context = currentLaunchRealMediaContext()) {
    const plan = launchSampleExecutionPlan(context);
    const source = Array.isArray(plan.execution_checklist) ? plan.execution_checklist : [];
    return source.map((row, index) => ({
      key: launchSampleExecutionRowKey(row, index),
      phase: row.phase || "Sample execution",
      check: row.check || "Review sample evidence",
      status: row.status || "unknown",
      severity: row.severity || "info",
      required: row.required !== false,
      ownerPage: row.owner_page || "Home / Sample Validation",
      backendEvidence: row.backend_evidence || "",
      currentEvidence: row.current_evidence || "",
      operatorProof: row.operator_proof || "",
      safeNextAction: row.safe_next_action || "",
      unsafeIfIgnored: row.unsafe_if_ignored || "",
      guardrail: row.guardrail || "Read-only sample execution checklist. Backend launch validation remains authoritative.",
    }));
  }

  function launchSampleExecutionRowStatus(row) {
    const status = String(row?.status || "").toLowerCase();
    const severity = String(row?.severity || "").toLowerCase();
    if (status === "ready" || status === "manual") return "match";
    if (status === "blocked" || severity === "error") return "blocked";
    if (status === "review" || severity === "warning") return "warning";
    if (["needs-sample", "needs-settings", "post-run-needed", "after-proof", "optional-review"].includes(status)) return "warning";
    return status || "unknown";
  }

  function launchSampleExecutionStatus(rows = launchSampleExecutionRows()) {
    if (!rows.length) return "No checklist";
    if (rows.some((row) => launchSampleExecutionRowStatus(row) === "blocked")) return "Blocked checklist";
    if (rows.some((row) => launchSampleExecutionRowStatus(row) === "warning")) return "Needs sample proof";
    return "Checklist visible";
  }

  function launchSampleExecutionSummaryLines(context = currentLaunchRealMediaContext(), rows = launchSampleExecutionRows(context)) {
    const plan = launchSampleExecutionPlan(context);
    const requiredRows = rows.filter((row) => row.required);
    const ready = requiredRows.filter((row) => row.status === "ready").length;
    const manual = requiredRows.filter((row) => row.status === "manual").length;
    const attention = rows.filter((row) => !["ready", "manual"].includes(row.status) && (row.required || ["error", "warning"].includes(String(row.severity || "").toLowerCase()))).length;
    const lines = [
      "Launch sample execution checklist:",
      "Purpose: mirror Home's backend-authored operator sample execution checklist at the actual Launch decision surface.",
      `Pilot status: ${plan.operator_status || "not loaded"}; sample run required: ${plan.sample_run_required === true ? "yes" : plan.sample_run_required === false ? "no" : "unknown"}.`,
      `Execution rows: ${rows.length}; required ready=${ready}/${requiredRows.length}; manual=${manual}; attention=${attention}.`,
      "Decision rule: before pressing Start, the before-launch and backend-launch-boundary rows should be understood; post-run rows remain proof tasks after the backend run finishes.",
    ];
    const firstAttention = rows.find((row) => !["ready", "manual"].includes(row.status) && (row.required || ["error", "warning"].includes(String(row.severity || "").toLowerCase())));
    if (firstAttention) {
      lines.push(`First action: ${firstAttention.phase} / ${firstAttention.check} - ${firstAttention.safeNextAction || firstAttention.operatorProof || "review before starting."}`);
    } else if (rows.length) {
      lines.push("First action: current checklist has no local blocker, but backend Launch validation and post-run real-media proof remain authoritative.");
    } else {
      lines.push("First action: refresh Home/Sample Validation evidence before planning a real-media sample run.");
    }
    lines.push("Mutation guardrail: this Launch checklist is read-only and cannot launch, accept, drain, publish, save settings, rename, append validation records, or touch media files.");
    return lines;
  }

  function selectedLaunchSampleExecutionRow(rows = []) {
    const source = Array.isArray(rows) ? rows : [];
    return source.find((row) => row.key === state.selectedLaunchSampleExecutionKey)
      || source.find((row) => !["ready", "manual"].includes(row.status) && row.required)
      || source[0]
      || null;
  }

  function launchSampleExecutionDetailLines(row) {
    if (!row) {
      return [
        "Launch sample execution checklist:",
        "No checklist row is selected.",
        "Refresh backend payloads or open Home Sample Validation after the sample-validation payload loads.",
        "Mutation guardrail: this panel is read-only.",
      ];
    }
    return [
      "Launch sample execution checklist:",
      `Phase: ${row.phase}`,
      `Check: ${row.check}`,
      `Status: ${row.status} (${row.severity})`,
      `Required: ${row.required ? "yes" : "no"}`,
      `Owner page: ${row.ownerPage}`,
      "",
      "Current backend evidence:",
      row.currentEvidence || row.backendEvidence || "(none loaded)",
      "",
      "Expected backend proof:",
      row.backendEvidence || "(none)",
      "",
      "Operator proof:",
      row.operatorProof || "(none)",
      "",
      "Safe next action:",
      row.safeNextAction || "Review this checklist row before trusting the real-media pilot.",
      "",
      "Unsafe if ignored:",
      row.unsafeIfIgnored || "(not specified)",
      "",
      "Launch boundary: this row does not start processing. The existing backend-owned Launch buttons still own start requests and re-check backend guards at submission time.",
      row.guardrail,
    ];
  }

  function selectLaunchSampleExecutionRow(row) {
    state.selectedLaunchSampleExecutionKey = row?.key || "";
    renderLaunchSampleExecutionChecklist();
  }

  function renderLaunchSampleExecutionChecklist(context = null) {
    if (context && typeof context === "object") setLaunchRealMediaContext(context);
    const rows = launchSampleExecutionRows(currentLaunchRealMediaContext());
    if (state.selectedLaunchSampleExecutionKey && !rows.some((row) => row.key === state.selectedLaunchSampleExecutionKey)) {
      state.selectedLaunchSampleExecutionKey = "";
    }
    const selected = selectedLaunchSampleExecutionRow(rows);
    const status = launchSampleExecutionStatus(rows);
    setText("launch-sample-execution-status", status);
    const statusNode = byId("launch-sample-execution-status");
    if (statusNode) statusNode.dataset.state = status === "Blocked checklist" ? "blocked" : status === "Checklist visible" ? "ready" : "warning";
    setText("launch-sample-execution-summary", launchSampleExecutionSummaryLines(currentLaunchRealMediaContext(), rows).join("\n"));
    setText("launch-sample-execution-detail", launchSampleExecutionDetailLines(selected).join("\n"));
    const tbody = byId("launch-sample-execution-rows");
    if (!tbody) return;
    if (!rows.length) {
      clearRows(tbody, 5, "No Launch sample execution checklist rows loaded.");
      updateTableStatusLegend("launch-sample-execution-legend", tbody, "Launch sample execution checklist rows");
      renderLaunchPilotRunReadiness();
      renderLaunchStartDecisionSummary();
      return;
    }
    tbody.replaceChildren();
    rows.forEach((item) => {
      const row = document.createElement("tr");
      row.dataset.status = launchSampleExecutionRowStatus(item);
      appendCells(row, [item.phase, item.check, item.status, item.ownerPage, item.required ? "Yes" : "No"]);
      if (typeof makeRowSelectable === "function") {
        makeRowSelectable(row, () => selectLaunchSampleExecutionRow(item), {
          selected: item.key === selected?.key,
          label: `Launch sample execution ${item.phase} ${item.check}`,
        });
      }
      tbody.appendChild(row);
    });
    updateTableStatusLegend("launch-sample-execution-legend", tbody, "Launch sample execution checklist rows");
    renderLaunchPilotRunReadiness();
    renderLaunchStartDecisionSummary();
  }

    return {
      launchRealMediaSample,
      launchWorksheetEvidence,
      launchWorksheetRunRows,
      launchWorksheetRunsMatchingSample,
      launchPolicyAlignmentPayload,
      launchPolicyAlignmentRows,
      launchQueueIntentCategoryMatch,
      launchPolicyAlignmentQueueIntentEvidence,
      launchSampleSetCoverageEvidence,
      launchSampleSetCoverageLine,
      launchSampleValidationRecordEvidence,
      launchSampleValidationRecordRows,
      launchSampleValidationRecordsMatchingSample,
      launchRealMediaProofRows,
      launchRealMediaProofStatus,
      launchRealMediaProofSummaryLines,
      launchRealMediaProofDetailLines,
      renderLaunchRealMediaProofHandoff,
      launchSampleExecutionRows,
      launchSampleExecutionStatus,
      launchSampleExecutionSummaryLines,
      launchSampleExecutionDetailLines,
      renderLaunchSampleExecutionChecklist,
    };
  }

  window.__launchViewRealMediaModule = {
    createLaunchRealMediaModule,
  };
})();
