// crossPageContextView.sampleValidation.records.js
// Split child of crossPageContextView.sampleValidation.js. Owns read-only
// Sample Validation helper clusters and exposes one temporary factory stash.
// Loaded before the parent; the parent consumes and deletes the stash during load.

(function () {
  "use strict";

  function createCrossPageSvRecordsModule({
    appendCells,
    byId,
    buildSampleValidationRequest,
    clearRows,
    crossPageSampleRows,
    makeRowSelectable,
    sampleValidationCheckFields,
    sampleValidationCheckedSummary,
    sampleValidationPath,
    sampleValidationPathToken,
    setText,
    state,
    updateTableStatusLegend,
  } = {}) {
    function sampleValidationPanelState(message) {
      const text = String(message || "").toLowerCase();
      if (!text || text.includes("not loaded") || text.startsWith("no ")) return "empty";
      if (text.includes("blocked") || text.includes("error")) return "blocked";
      if (text.includes("needed") || text.includes("review") || text.includes("manual") || text.includes("hold") || text.includes("partial")) return "warning";
      if (text.includes("ready") || text.includes("current") || text.includes("coherent") || text.includes("loaded")) return "ready";
      return "unknown";
    }

    function setRecordsPanelStatus(id, message, state) {
      if (typeof setPanelStatus === "function") {
        setPanelStatus(id, message, state || sampleValidationPanelState(message));
      } else {
        setText(id, message);
      }
    }

    const SAMPLE_VALIDATION_CHECK_FIELDS = Array.isArray(sampleValidationCheckFields)
      ? sampleValidationCheckFields
      : [];
    function sampleValidationRecordRows(log = {}) {
      return Array.isArray(log.records) ? log.records : [];
    }

    function sampleValidationReconciliationRows(log = {}) {
      const reconciliation = log.reconciliation && typeof log.reconciliation === "object" ? log.reconciliation : {};
      return Array.isArray(reconciliation.rows) ? reconciliation.rows : [];
    }

    function sampleValidationReconciliationForRecord(record = {}, log = {}) {
      const recordId = String(record?.record_id || "");
      return sampleValidationReconciliationRows(log).find((row) => String(row?.record_id || "") === recordId) || null;
    }

    function sampleValidationRecordMatchesSample(record = {}, sample = null) {
      if (!sample || !record) return false;
      const sourcePath = sampleValidationPath(sample, ["source"]);
      const outputPath = sampleValidationPath(sample, ["output", "destination", "runtime output", "parked payload"]);
      const sourceToken = sampleValidationPathToken(sourcePath);
      const outputToken = sampleValidationPathToken(outputPath);
      const sampleLabel = sampleValidationPathToken(sample?.seed?.display || "");
      const recordSource = sampleValidationPathToken(record.source_path || "");
      const recordOutput = sampleValidationPathToken(record.output_path || "");
      const recordLabel = sampleValidationPathToken(record.sample_label || "");
      return Boolean(
        (sourceToken && recordSource && (sourceToken === recordSource || sourceToken.endsWith(recordSource) || recordSource.endsWith(sourceToken)))
        || (outputToken && recordOutput && (outputToken === recordOutput || outputToken.endsWith(recordOutput) || recordOutput.endsWith(outputToken)))
        || (sampleLabel && recordLabel && (sampleLabel.includes(recordLabel) || recordLabel.includes(sampleLabel)))
      );
    }

    function sampleValidationRecordComparisonRowsForPaths(log = {}, paths = [], label = "") {
      const pathTokens = (Array.isArray(paths) ? paths : [])
        .map((item) => sampleValidationPathToken(item))
        .filter(Boolean);
      const labelToken = sampleValidationPathToken(label);
      return sampleValidationRecordRows(log).map((record) => {
        const recordSource = sampleValidationPathToken(record.source_path || "");
        const recordOutput = sampleValidationPathToken(record.output_path || "");
        const recordLabel = sampleValidationPathToken(record.sample_label || "");
        const matchFields = [];
        const exact = pathTokens.some((token) => {
          if (recordSource && (token === recordSource || token.endsWith(recordSource) || recordSource.endsWith(token))) {
            matchFields.push("source");
            return true;
          }
          if (recordOutput && (token === recordOutput || token.endsWith(recordOutput) || recordOutput.endsWith(token))) {
            matchFields.push("output");
            return true;
          }
          return false;
        });
        const labelMatch = Boolean(labelToken && recordLabel && (labelToken.includes(recordLabel) || recordLabel.includes(labelToken)));
        if (labelMatch) matchFields.push("label");
        if (!exact && !labelMatch) return null;
        const reconciliation = sampleValidationReconciliationForRecord(record, log);
        const missing = Array.isArray(reconciliation?.missing_current_evidence) ? reconciliation.missing_current_evidence : [];
        return {
          record,
          reconciliation,
          record_id: record.record_id || "",
          created_at: record.created_at || "",
          operator_decision: record.operator_decision || "",
          sample_category: record.sample_category || "general",
          proof_strength: record.proof_strength || "",
          sample_label: record.sample_label || "",
          source_path: record.source_path || "",
          output_path: record.output_path || "",
          match_strength: exact ? "exact-path" : "label-advisory",
          match_fields: Array.from(new Set(matchFields)),
          current_status: reconciliation?.status || "not checked",
          current_severity: reconciliation?.severity || "",
          missing_current_evidence: missing,
          evidence: reconciliation?.evidence || "No current reconciliation row is loaded for this record.",
          safe_next_action: reconciliation?.safe_next_action || "Refresh Sample Validation and compare current backend proof before relying on this record.",
        };
      }).filter(Boolean);
    }

    function sampleValidationRecordsMatchingSample(log = {}, sample = null) {
      return sampleValidationRecordRows(log).filter((record) => sampleValidationRecordMatchesSample(record, sample));
    }

    function sampleValidationRecordDecisionIsAccepted(record = {}) {
      return String(record?.operator_decision || "").toLowerCase() === "accepted";
    }

    function sampleValidationRecordReviewCandidate(context = {}) {
      const log = context.sampleValidation || {};
      const sample = crossPageSampleRows(context || {})[0] || null;
      const records = sampleValidationRecordRows(log);
      const samplePaths = [
        sampleValidationPath(sample, ["source"]),
        sampleValidationPath(sample, ["output", "destination", "runtime output", "parked payload"]),
      ].filter(Boolean);
      const comparisons = sampleValidationRecordComparisonRowsForPaths(log, samplePaths, sample?.seed?.display || "");
      const currentAccepted = comparisons.find((row) => sampleValidationRecordDecisionIsAccepted(row.record) && row.current_status === "current");
      if (currentAccepted?.record) return currentAccepted.record;
      const anyCurrent = comparisons.find((row) => row.current_status === "current");
      if (anyCurrent?.record) return anyCurrent.record;
      const acceptedComparison = comparisons.find((row) => sampleValidationRecordDecisionIsAccepted(row.record));
      if (acceptedComparison?.record) return acceptedComparison.record;
      const acceptedRecord = records.find((record) => sampleValidationRecordDecisionIsAccepted(record));
      if (acceptedRecord) return acceptedRecord;
      return records[0] || null;
    }

    function sampleValidationRecordReviewRowStatus(row) {
      const status = String(row?.status || "").toLowerCase();
      if (status.includes("blocked") || status.includes("stale")) return "blocked";
      if (status.includes("review") || status.includes("missing") || status.includes("historical")) return "warning";
      if (status.includes("manual") || status.includes("boundary")) return "changed";
      if (status.includes("ready") || status.includes("current") || status.includes("checked")) return "match";
      return "unknown";
    }

    function sampleValidationRecordReviewRows(context = {}) {
      const log = context.sampleValidation || {};
      const record = sampleValidationRecordReviewCandidate(context || {});
      if (!record) {
        return [{
          key: "no-record",
          proof_area: "Accepted record",
          status: "Blocked",
          evidence: "No sample-validation records are loaded.",
          action: "Run a real sample, compare output evidence, then preview/append a backend-owned validation record.",
          detail: ["Accepted proof review needs at least one parsed sample_validation_record.v1 row."],
        }];
      }
      const reconciliation = sampleValidationReconciliationForRecord(record, log);
      const checks = record.checks && typeof record.checks === "object" ? record.checks : {};
      const evidence = record.evidence && typeof record.evidence === "object" ? record.evidence : {};
      const evidenceCount = (key) => Array.isArray(evidence[key]) ? evidence[key].length : 0;
      const missing = Array.isArray(reconciliation?.missing_current_evidence) ? reconciliation.missing_current_evidence : [];
      const isAccepted = sampleValidationRecordDecisionIsAccepted(record);
      const isCurrent = reconciliation?.status === "current";
      const add = (key, proof_area, status, rowEvidence, action, detail = []) => ({
        key,
        proof_area,
        status,
        evidence: rowEvidence,
        action,
        detail: Array.isArray(detail) ? detail : [],
        record,
        reconciliation,
      });
      return [
        add(
          "record-identity",
          "Accepted/current record",
          isAccepted ? (isCurrent ? "Current" : "Historical review") : "Review",
          `decision=${record.operator_decision || "unknown"}; category=${record.sample_category || "general"}; proof=${record.proof_strength || "unknown"}; reconciliation=${reconciliation?.status || "not checked"}`,
          isAccepted && isCurrent
            ? "Use this record as current evidence only after manual playback and output proof still agree."
            : "Do not treat this record as accepted current proof until backend reconciliation is current.",
          [
            `Record: ${record.record_id || "unknown"}`,
            `Created: ${record.created_at || "unknown"}`,
            `Sample: ${record.sample_label || record.source_path || record.output_path || "unknown"}`,
          ],
        ),
        add(
          "output-sidecar-proof",
          "Completed output and sidecar",
          checks.completed_output_checked && checks.sidecar_manifest_checked && isCurrent ? "Checked" : "Review",
          `completed_output=${checks.completed_output_checked ? "checked" : "missing"}; sidecar_manifest=${checks.sidecar_manifest_checked ? "checked" : "missing"}; completed evidence rows=${evidenceCount("completed")}`,
          checks.completed_output_checked && checks.sidecar_manifest_checked
            ? "Compare the Completed Evidence Handoff with the record source/output before trusting final placement."
            : "Inspect Completed output, sidecar, and manifest before accepted evidence.",
          [
            `Source: ${record.source_path || "not recorded"}`,
            `Output: ${record.output_path || "not recorded"}`,
            "Completed evidence should agree with the selected Completed row, final output path, and sidecar fields.",
          ],
        ),
        add(
          "size-policy-proof",
          "Size/output-growth proof",
          checks.size_growth_checked ? "Checked" : "Review",
          `size_growth=${checks.size_growth_checked ? "checked" : "missing"}; notes=${record.operator_notes ? "present" : "empty"}`,
          checks.size_growth_checked
            ? "Confirm recorded size posture matches Completed size-policy evidence and any operator note."
            : "Review Completed size policy/output growth before accepted evidence.",
          [
            "Large output growth can still be intentional when compatibility routing, audio, or subtitle behavior changed.",
            "Compare Completed size-policy evidence, route reason, and manual notes.",
          ],
        ),
        add(
          "subtitle-audio-proof",
          "Subtitle and audio proof",
          checks.subtitle_checked && checks.audio_checked ? "Checked" : "Review",
          `subtitle=${checks.subtitle_checked ? "checked" : "missing"}; audio=${checks.audio_checked ? "checked" : "missing"}; completed evidence rows=${evidenceCount("completed")}`,
          checks.subtitle_checked && checks.audio_checked
            ? "Confirm Plex/client playback still matches subtitle/audio expectations."
            : "Verify preferred-language subtitles/SRT behavior and audio/default track behavior before accepted evidence.",
          [
            "Subtitle/audio checks are operator assertions backed by Completed/Diagnostics evidence and playback review.",
            "They do not prove OCR quality or Plex playback by themselves.",
          ],
        ),
        add(
          "diagnostics-proof",
          "Diagnostics/run-log proof",
          checks.diagnostics_checked || checks.ffmpeg_log_checked ? "Checked" : "Review",
          `diagnostics=${checks.diagnostics_checked ? "checked" : "missing"}; ffmpeg_log=${checks.ffmpeg_log_checked ? "checked" : "missing"}; diagnostics evidence rows=${evidenceCount("diagnostics")}`,
          checks.diagnostics_checked || checks.ffmpeg_log_checked
            ? "Read Last Stderr/Run Logs if route, subtitle, audio, size, or publish evidence is surprising."
            : "Read Diagnostics Last Stderr/Run Logs before accepted evidence.",
          [
            "Diagnostics evidence is supporting proof only; final trust still requires output, sidecar, and playback checks.",
          ],
        ),
        add(
          "pending-publish-proof",
          "Pending Publish/final placement",
          checks.pending_publish_checked || evidenceCount("pending_publish") ? "Checked" : "Manual review",
          `pending_publish=${checks.pending_publish_checked ? "checked" : "not checked"}; pending evidence rows=${evidenceCount("pending_publish")}`,
          checks.pending_publish_checked || evidenceCount("pending_publish")
            ? "Compare pending/drain/final-placement proof if deferred publish was involved."
            : "If deferred publish was not involved, document it as not applicable; otherwise inspect Pending Publish.",
          [
            "A parked or drained sample needs Pending Publish and Completed final-placement proof before acceptance.",
          ],
        ),
        add(
          "current-reconciliation",
          "Current backend reconciliation",
          !reconciliation ? "Review" : missing.length ? "Stale review" : reconciliation.status === "current" ? "Current" : "Review",
          reconciliation
            ? `status=${reconciliation.status || "unknown"}; severity=${reconciliation.severity || "info"}; missing=${missing.length || 0}`
            : "No reconciliation row is loaded for this record.",
          missing.length
            ? "Treat this record as historical until missing current evidence is resolved."
            : "Use reconciliation as current-proof support, then perform manual media checks.",
          missing.length ? missing : ["Reconciliation compares recent records against current Queue/Completed/Pending/Diagnostics evidence."],
        ),
        add(
          "record-boundary",
          "Record mutation boundary",
          "Boundary",
          "This review is derived from existing sample-validation records and current backend evidence.",
          "Use backend Preview/Append for any new record; this panel cannot mutate pipeline state.",
          [
            "This review cannot append validation records, accept output, clear failures, rerun, drain, publish, repair, save settings, rename, rewrite manifests/sidecars, change media policy, or touch media.",
          ],
        ),
      ];
    }

    function sampleValidationRecordReviewStatus(context = {}) {
      const rows = sampleValidationRecordReviewRows(context || {});
      if (rows.some((row) => sampleValidationRecordReviewRowStatus(row) === "blocked")) return "Review blocked";
      if (rows.some((row) => sampleValidationRecordReviewRowStatus(row) === "warning")) return "Review needed";
      if (rows.some((row) => sampleValidationRecordReviewRowStatus(row) === "changed")) return "Manual checks";
      return "Current proof loaded";
    }

    function sampleValidationRecordReviewSummaryLines(context = {}) {
      const record = sampleValidationRecordReviewCandidate(context || {});
      const rows = sampleValidationRecordReviewRows(context || {});
      const blocked = rows.filter((row) => sampleValidationRecordReviewRowStatus(row) === "blocked").length;
      const review = rows.filter((row) => sampleValidationRecordReviewRowStatus(row) === "warning").length;
      const checked = rows.filter((row) => sampleValidationRecordReviewRowStatus(row) === "match").length;
      const lines = [
        "Accepted sample-validation record proof review:",
        `Review status: ${sampleValidationRecordReviewStatus(context || {})}`,
        `Selected record: ${record?.record_id || "none"}; decision=${record?.operator_decision || "none"}; category=${record?.sample_category || "general"}`,
        `Rows: checked=${checked}; review=${review}; blocked=${blocked}; total=${rows.length}`,
        "Decision rule: treat accepted records as current proof only when backend reconciliation, Completed output/sidecar/size proof, Diagnostics logs, Pending Publish/final-placement posture, and manual playback/subtitle/audio checks still agree.",
      ];
      if (!record) {
        lines.push("First action: create a validation record only after running a known real-media sample and comparing output evidence.");
      } else if (blocked) {
        lines.push("First action: resolve stale/missing current evidence before relying on this accepted record.");
      } else if (review) {
        lines.push("First action: walk the review rows and document any not-applicable media checks before using the record as trust evidence.");
      } else {
        lines.push("First action: current proof is loaded; still perform manual playback/media checks before expanding WebView use.");
      }
      lines.push("Mutation guardrail: this review is read-only and cannot append records, accept output, rerun, drain, publish, repair, save settings, rename, rewrite manifests/sidecars, change media policy, or touch media.");
      return lines;
    }

    function sampleValidationRecordReviewDetailLines(row) {
      if (!row) {
        return [
          "Accepted sample-validation record proof review:",
          "Select a proof row to inspect current output, sidecar, size, subtitle/audio, Diagnostics, or pending-publish evidence for the chosen validation record.",
          "Mutation guardrail: this detail panel is read-only.",
        ];
      }
      return [
        "Accepted sample-validation record proof review:",
        `Proof area: ${row.proof_area || "unknown"}`,
        `Status: ${row.status || "unknown"}`,
        `Evidence: ${row.evidence || ""}`,
        `Safe next action: ${row.action || ""}`,
        ...((Array.isArray(row.detail) && row.detail.length) ? ["", "Detail:", ...row.detail.map((line) => `- ${line}`)] : []),
        "",
        "Mutation guardrail: this row cannot append records, accept output, rerun, drain, publish, repair, save settings, rename, rewrite manifests/sidecars, change media policy, or touch media.",
      ];
    }

    function selectedSampleValidationRecordReviewRow(rows) {
      const list = Array.isArray(rows) ? rows : [];
      return list.find((row) => row.key === state.selectedSampleValidationRecordReviewKey)
        || list.find((row) => sampleValidationRecordReviewRowStatus(row) === "blocked")
        || list.find((row) => sampleValidationRecordReviewRowStatus(row) === "warning")
        || list[0]
        || null;
    }

    function renderSampleValidationRecordReview(context = {}) {
      const rows = sampleValidationRecordReviewRows(context || {});
      if (state.selectedSampleValidationRecordReviewKey && !rows.some((row) => row.key === state.selectedSampleValidationRecordReviewKey)) {
        state.selectedSampleValidationRecordReviewKey = "";
      }
      const selected = selectedSampleValidationRecordReviewRow(rows);
      setRecordsPanelStatus("sample-validation-record-review-status", sampleValidationRecordReviewStatus(context || {}));
      setText("sample-validation-record-review-summary", sampleValidationRecordReviewSummaryLines(context || {}).join("\n"));
      setText("sample-validation-record-review-detail", sampleValidationRecordReviewDetailLines(selected).join("\n"));
      setText("sample-validation-record-review-legend", "Accepted record proof rows are read-only and cannot append records, accept output, rerun, drain, publish, repair, save settings, rename, rewrite manifests/sidecars, change media policy, or touch media.");
      const tbody = byId("sample-validation-record-review-rows");
      if (!tbody) return;
      if (!rows.length) {
        clearRows(tbody, 4, "No accepted sample-validation record proof rows loaded.");
        updateTableStatusLegend("sample-validation-record-review-legend", tbody, "Accepted sample-validation proof rows");
        return;
      }
      tbody.replaceChildren();
      rows.forEach((item) => {
        const row = document.createElement("tr");
        row.dataset.status = sampleValidationRecordReviewRowStatus(item);
        appendCells(row, [item.proof_area || "", item.status || "", item.evidence || "", item.action || ""]);
        makeRowSelectable(row, () => {
          state.selectedSampleValidationRecordReviewKey = item.key || "";
          setText("sample-validation-record-review-detail", sampleValidationRecordReviewDetailLines(item).join("\n"));
        }, {
          selected: item.key === selected?.key,
          label: `Review accepted sample-validation proof ${item.proof_area || ""}`,
        });
        tbody.appendChild(row);
      });
      updateTableStatusLegend("sample-validation-record-review-legend", tbody, "Accepted sample-validation proof rows");
    }

    function sampleValidationRecordLines(record, reconciliation = null) {
      if (!record) return ["No sample validation record selected."];
      const evidence = record.evidence || {};
      const lines = [
        `Record: ${record.record_id || "unknown"}`,
        `Created: ${record.created_at || ""}`,
        `Decision: ${record.operator_decision || ""}`,
        `Proof: ${record.proof_strength || ""}`,
        `Pilot category: ${record.sample_category || "general / not categorized"}`,
        `Sample: ${record.sample_label || ""}`,
        `Source: ${record.source_path || ""}`,
        `Output: ${record.output_path || ""}`,
        `Checks: ${sampleValidationCheckedSummary(record.checks || {})}`,
        `Evidence counts: queue=${(evidence.queue || []).length}; completed=${(evidence.completed || []).length}; pending=${(evidence.pending_publish || []).length}; diagnostics=${(evidence.diagnostics || []).length}`,
      ];
      if (reconciliation) {
        lines.push(
          "",
          `Current evidence status: ${reconciliation.status || "unknown"} (${reconciliation.severity || "info"})`,
          `Current matches: ${reconciliation.evidence || ""}`,
          `Reconciliation next action: ${reconciliation.safe_next_action || ""}`
        );
        const missing = Array.isArray(reconciliation.missing_current_evidence) ? reconciliation.missing_current_evidence : [];
        if (missing.length) lines.push("Missing current evidence:", ...missing.map((item) => `- ${item}`));
      } else {
        lines.push(
          "",
          "Current evidence status: not checked",
          "Current matches: no reconciliation row is loaded for this record.",
          "Reconciliation next action: refresh Sample Validation and compare Queue, Completed, Pending Publish, and Diagnostics before treating this historical note as current proof."
        );
      }
      lines.push(
        "",
        "Operator notes:",
        record.operator_notes || "(none)",
        "",
        "Boundary: this record is evidence only and cannot accept, rerun, repair, drain, delete, publish, or rewrite files."
      );
      return lines;
    }

    function sampleValidationRecordCurrentEvidenceLabel(reconciliation = null) {
      if (!reconciliation) return "not checked";
      const status = String(reconciliation.status || "unknown").trim() || "unknown";
      const severity = String(reconciliation.severity || "").trim();
      return severity && severity !== "info" ? `${status} (${severity})` : status;
    }

    function sampleValidationRecordGapLabel(reconciliation = null) {
      if (!reconciliation) return "not checked";
      const missing = Array.isArray(reconciliation.missing_current_evidence) ? reconciliation.missing_current_evidence : [];
      if (missing.length) return `${missing.length} missing`;
      if (reconciliation.status === "current") return "none";
      return reconciliation.safe_next_action ? "review" : "unknown";
    }

    function sampleValidationRecordRowState(record = {}, reconciliation = null) {
      if (reconciliation?.status === "current") return "match";
      if (reconciliation?.status === "stale") return "warning";
      if (reconciliation?.severity === "error" || reconciliation?.status === "blocked") return "blocked";
      if (record.operator_decision === "accepted") return "warning";
      return "unknown";
    }

    function renderSampleValidationRecords(payload = {}) {
      const tbody = byId("sample-validation-records");
      if (!tbody) return;
      const records = Array.isArray(payload.records) ? payload.records : [];
      if (!records.length) {
        clearRows(tbody, 7, payload.exists ? "No sample validation records parsed." : "No sample validation records loaded.");
        updateTableStatusLegend("sample-validation-legend", tbody, "Sample validation records");
        setText("sample-validation-detail", payload.guardrail || "No sample validation record selected.");
        return;
      }
      tbody.replaceChildren();
      const reconciliationRows = Array.isArray(payload.reconciliation?.rows) ? payload.reconciliation.rows : [];
      const reconciliationById = new Map(reconciliationRows.map((row) => [String(row.record_id || ""), row]));
      records.forEach((record, index) => {
        const reconciliation = reconciliationById.get(String(record.record_id || "")) || null;
        const row = document.createElement("tr");
        const rowState = sampleValidationRecordRowState(record, reconciliation);
        row.dataset.status = rowState;
        row.dataset.state = rowState;
        appendCells(row, [
          record.created_at || "",
          record.operator_decision || "",
          record.sample_category || "general",
          sampleValidationRecordCurrentEvidenceLabel(reconciliation),
          sampleValidationRecordGapLabel(reconciliation),
          record.sample_label || record.source_path || record.output_path || "",
          record.proof_strength || "",
        ]);
        makeRowSelectable(row, () => setText("sample-validation-detail", sampleValidationRecordLines(record, reconciliation).join("\n")), {
          selected: index === 0,
          label: `Review sample validation record ${record.record_id || index + 1}`,
        });
        tbody.appendChild(row);
        if (index === 0) setText("sample-validation-detail", sampleValidationRecordLines(record, reconciliation).join("\n"));
      });
      updateTableStatusLegend("sample-validation-legend", tbody, "Sample validation records");
    }

    function completedViewNamespace() {
      return window.mediaPipelineCompletedView || {};
    }

    function sampleValidationCompletedPacketRows(context = {}) {
      const completedView = completedViewNamespace();
      if (typeof completedView.completedPilotEvidencePacketRows !== "function") return [];
      const completed = context.completed || (typeof window.getLastCompletedPayload === "function" ? window.getLastCompletedPayload() : {});
      const rows = Array.isArray(completed?.rows)
        ? completed.rows
        : typeof window.getLastCompletedRows === "function" ? window.getLastCompletedRows() : [];
      const proofRows = typeof completedView.getLastCompletedPendingProofRows === "function" ? completedView.getLastCompletedPendingProofRows() : [];
      const pending = context.pending || (typeof window.getLastPendingPublishPayload === "function" ? window.getLastPendingPublishPayload() : {});
      return completedView.completedPilotEvidencePacketRows(completed || {}, rows || [], proofRows || [], pending || {});
    }

    function sampleValidationCompletedPacketPostureStatus(row) {
      const completedView = completedViewNamespace();
      if (typeof completedView.completedPilotEvidencePostureStatus === "function") {
        return completedView.completedPilotEvidencePostureStatus(row?.posture);
      }
      const normalized = String(row?.posture || "").toLowerCase();
      if (normalized.includes("blocked")) return "blocked";
      if (normalized.includes("review")) return "warning";
      if (normalized.includes("manual") || normalized.includes("read-first") || normalized.includes("read-only")) return "changed";
      if (normalized.includes("current") || normalized.includes("ready")) return "match";
      return "unknown";
    }

    function sampleValidationCompletedPacketStatus(context = {}) {
      const rows = sampleValidationCompletedPacketRows(context);
      if (!rows.length) return "No Completed packet";
      const completedView = completedViewNamespace();
      if (typeof completedView.completedPilotEvidencePacketStatus === "function") return completedView.completedPilotEvidencePacketStatus(rows);
      if (rows.some((row) => sampleValidationCompletedPacketPostureStatus(row) === "blocked")) return "Packet blocked";
      if (rows.some((row) => sampleValidationCompletedPacketPostureStatus(row) === "warning")) return "Packet review";
      if (rows.some((row) => sampleValidationCompletedPacketPostureStatus(row) === "changed")) return "Manual check";
      return "Packet coherent";
    }

    function sampleValidationCompletedPolicyReconciliationRow(context = {}) {
      return sampleValidationCompletedPacketRows(context).find((row) => row?.key === "completed-policy-reconciliation")
        || sampleValidationCompletedPacketRows(context).find((row) => String(row?.checkpoint || "").toLowerCase().includes("saved policy reconciliation"))
        || null;
    }

    function sampleValidationCompletedPolicyReconciliationStatus(context = {}) {
      const row = sampleValidationCompletedPolicyReconciliationRow(context);
      if (!row) return "No saved-policy row";
      const status = sampleValidationCompletedPacketPostureStatus(row);
      if (status === "blocked") return "Blocked";
      if (status === "warning") return "Review";
      if (status === "changed" || status === "unknown") return "Review";
      if (status === "match") return "Ready";
      return "Review";
    }

    function sampleValidationCompletedPacketSummaryLines(context = {}) {
      const rows = sampleValidationCompletedPacketRows(context);
      const blocked = rows.filter((row) => sampleValidationCompletedPacketPostureStatus(row) === "blocked").length;
      const review = rows.filter((row) => sampleValidationCompletedPacketPostureStatus(row) === "warning").length;
      const manual = rows.filter((row) => sampleValidationCompletedPacketPostureStatus(row) === "changed").length;
      const completedView = window.mediaPipelineCompletedView || {};
      const selected = typeof completedView.getSelectedCompletedRow === "function" ? completedView.getSelectedCompletedRow() : null;
      const policyRow = sampleValidationCompletedPolicyReconciliationRow(context);
      const lines = [
        "Completed evidence handoff for Sample Validation:",
        `Selected Completed row: ${selected?.lookup_title || selected?.output_file || selected?.output_path || (selected ? "(selected row)" : "none selected; using Completed packet default")}`,
        `Packet status: ${sampleValidationCompletedPacketStatus(context)}`,
        `Rows loaded: ${rows.length}; blocked/review/manual=${blocked}/${review}/${manual}`,
        `Saved-policy reconciliation: ${sampleValidationCompletedPolicyReconciliationStatus(context)}; ${policyRow?.evidence || "no Completed saved-policy reconciliation row loaded"}`,
        "Decision rule: keep Sample Validation at hold/review unless the selected Completed packet, Pending Publish/final placement, Diagnostics/runtime evidence, manual playback, subtitle/audio checks, and size review agree.",
      ];
      if (!rows.length) {
        lines.push("First action: load Completed evidence or select a Completed row before previewing a post-run accepted validation record.");
      } else if (blocked) {
        lines.push("First action: open Completed and resolve blocked packet rows before appending accepted evidence.");
      } else if (review || manual) {
        lines.push("First action: walk the Completed packet, then use Preview Record only after manual playback/subtitle/audio/size checks are done.");
      } else {
        lines.push("First action: packet is coherent-looking; Preview Record still decides backend append readiness and manual checks remain required.");
      }
      lines.push("Mutation guardrail: this handoff is read-only and cannot append validation records, accept output, rerun, drain, publish, repair, save settings, rename, rewrite manifests/sidecars, or touch media.");
      return lines;
    }

    function sampleValidationCompletedPacketDetailLines(row) {
      if (!row) {
        return [
          "Completed evidence handoff for Sample Validation:",
          "Select a packet row to inspect the Completed proof that should be reconciled before previewing/appending evidence.",
          "Mutation guardrail: this detail panel is read-only.",
        ];
      }
      const completedView = completedViewNamespace();
      if (typeof completedView.completedPilotEvidencePacketDetailLines === "function") {
        return completedView.completedPilotEvidencePacketDetailLines(row);
      }
      return [
        "Completed evidence handoff for Sample Validation:",
        `Checkpoint: ${row.checkpoint || "unknown"}`,
        `Posture: ${row.posture || "unknown"}`,
        `Evidence: ${row.evidence || ""}`,
        `Operator action: ${row.action || ""}`,
        "Mutation guardrail: read-only handoff only.",
      ];
    }

    function sampleValidationCompletedPacketMarkdownLines(context = {}) {
      const rows = sampleValidationCompletedPacketRows(context);
      const completedView = completedViewNamespace();
      if (typeof completedView.completedPilotEvidencePacketMarkdownLines === "function") {
        return completedView.completedPilotEvidencePacketMarkdownLines(rows);
      }
      return [
        "# Completed Evidence Handoff For Sample Validation",
        "",
        ...rows.map((row) => `- [ ] ${row.checkpoint || "Checkpoint"} - ${row.posture || "review"} - ${row.evidence || ""}`),
        "",
        "Backend mutation boundary: this handoff is read-only and cannot append records, accept output, rerun, drain, publish, repair, save settings, rename, rewrite manifests/sidecars, or touch media.",
      ];
    }

    function selectedSampleValidationCompletedPacketRow(rows) {
      const list = Array.isArray(rows) ? rows : [];
      return list.find((row) => row.key === state.selectedSampleValidationCompletedPacketKey)
        || list.find((row) => sampleValidationCompletedPacketPostureStatus(row) === "blocked")
        || list.find((row) => sampleValidationCompletedPacketPostureStatus(row) === "warning")
        || list.find((row) => sampleValidationCompletedPacketPostureStatus(row) === "changed")
        || list[0]
        || null;
    }

    function renderSampleValidationCompletedPacketHandoff(context = {}) {
      const rows = sampleValidationCompletedPacketRows(context);
      if (state.selectedSampleValidationCompletedPacketKey && !rows.some((row) => row.key === state.selectedSampleValidationCompletedPacketKey)) {
        state.selectedSampleValidationCompletedPacketKey = "";
      }
      const selected = selectedSampleValidationCompletedPacketRow(rows);
      setRecordsPanelStatus("sample-validation-completed-packet-status", sampleValidationCompletedPacketStatus(context));
      setText("sample-validation-completed-packet-summary", sampleValidationCompletedPacketSummaryLines(context).join("\n"));
      setText("sample-validation-completed-packet-detail", sampleValidationCompletedPacketDetailLines(selected).join("\n"));
      setText("sample-validation-completed-packet-markdown", sampleValidationCompletedPacketMarkdownLines(context).join("\n"));
      setText("sample-validation-completed-packet-legend", "Completed evidence handoff rows are read-only and do not append validation records, accept output, rerun, drain, publish, repair, save settings, rename, rewrite manifests/sidecars, or touch media.");
      const tbody = byId("sample-validation-completed-packet-rows");
      if (!tbody) return;
      if (!rows.length) {
        clearRows(tbody, 4, "No selected Completed evidence packet rows loaded.");
        updateTableStatusLegend("sample-validation-completed-packet-legend", tbody, "Completed evidence handoff rows");
        return;
      }
      tbody.replaceChildren();
      rows.forEach((item) => {
        const row = document.createElement("tr");
        row.dataset.status = sampleValidationCompletedPacketPostureStatus(item);
        appendCells(row, [item.checkpoint || "", item.posture || "Read-only", item.evidence || "", item.action || ""]);
        makeRowSelectable(row, () => {
          state.selectedSampleValidationCompletedPacketKey = item.key || "";
          setText("sample-validation-completed-packet-detail", sampleValidationCompletedPacketDetailLines(item).join("\n"));
        }, {
          selected: item.key === selected?.key,
          label: `Review Completed evidence handoff ${item.checkpoint || ""}`,
        });
        tbody.appendChild(row);
      });
      updateTableStatusLegend("sample-validation-completed-packet-legend", tbody, "Completed evidence handoff rows");
    }

    function sampleValidationAcceptanceCheckLabels(keys) {
      const keySet = new Set(Array.isArray(keys) ? keys : []);
      return SAMPLE_VALIDATION_CHECK_FIELDS
        .filter(([key]) => keySet.has(key))
        .map(([, label]) => label);
    }

    function sampleValidationAcceptanceGateRowStatus(row) {
      const status = String(row?.status || "").toLowerCase();
      if (status.includes("blocked")) return "blocked";
      if (status.includes("review") || status.includes("missing")) return "warning";
      if (status.includes("hold") || status.includes("manual") || status.includes("boundary")) return "changed";
      if (status.includes("ready") || status.includes("loaded")) return "match";
      return "unknown";
    }

    function sampleValidationAcceptanceGateRows(context = {}) {
      const sample = crossPageSampleRows(context || {})[0] || null;
      const log = context.sampleValidation || {};
      const readiness = log.readiness || {};
      const reconciliation = log.reconciliation || {};
      const request = buildSampleValidationRequest(context || {});
      const checks = request.checks || {};
      const requiredKeys = ["queue_route_checked", "completed_output_checked", "sidecar_manifest_checked", "size_growth_checked", "diagnostics_checked"];
      const recommendedKeys = ["subtitle_checked", "audio_checked", "pending_publish_checked"];
      const requiredMissing = requiredKeys.filter((key) => !checks[key]);
      const recommendedMissing = recommendedKeys.filter((key) => !checks[key]);
      const checkedCount = SAMPLE_VALIDATION_CHECK_FIELDS.filter(([key]) => Boolean(checks[key])).length;
      const completedRows = sampleValidationCompletedPacketRows(context || {});
      const completedBlocked = completedRows.filter((row) => sampleValidationCompletedPacketPostureStatus(row) === "blocked").length;
      const completedReview = completedRows.filter((row) => ["warning", "changed"].includes(sampleValidationCompletedPacketPostureStatus(row))).length;
      const completedPolicyRow = sampleValidationCompletedPolicyReconciliationRow(context || {});
      const completedPolicyStatus = sampleValidationCompletedPolicyReconciliationStatus(context || {});
      const completedPolicyRowState = completedPolicyRow ? sampleValidationCompletedPacketPostureStatus(completedPolicyRow) : "unknown";
      const decision = String(request.operator_decision || "hold_review");
      const category = String(request.sample_category || "");
      const proofStrength = String(request.proof_strength || "none");
      const add = (key, gate, status, evidence, action, detail = []) => ({
        key,
        gate,
        status,
        evidence,
        action,
        detail: Array.isArray(detail) ? detail : [],
      });
      const rows = [];
      rows.push(add(
        "selected-sample",
        "Selected real sample",
        sample ? (proofStrength === "none" ? "Review" : "Ready") : "Blocked",
        sample ? `sample=${sample.seed?.display || "loaded"}; proof=${proofStrength}; category=${category || "general"}` : "No selected Queue/Completed/Pending sample evidence is loaded.",
        sample ? "Confirm the selected sample is the actual file you just processed or plan to validate." : "Select or refresh Queue, Completed, or Pending Publish evidence before previewing a record.",
        [
          "A sample-validation record should describe one concrete media file.",
          "Filename-only or missing proof should stay review evidence until Queue, Completed, Pending Publish, and Diagnostics agree.",
        ],
      ));
      rows.push(add(
        "operator-decision",
        "Operator decision",
        decision === "accepted" ? (sample && !requiredMissing.length ? (recommendedMissing.length ? "Review" : "Ready") : "Blocked") : "Hold/review",
        `decision=${decision}; required missing=${sampleValidationAcceptanceCheckLabels(requiredMissing).join(", ") || "none"}; recommended missing=${sampleValidationAcceptanceCheckLabels(recommendedMissing).join(", ") || "none"}`,
        decision === "accepted"
          ? "Preview accepted evidence only after required proof is current and recommended media checks are intentionally complete or not applicable."
          : "Use Hold/Rerun/Fallback until current backend proof and manual media checks agree.",
        [
          "Accepted writes an operator evidence note only after backend Preview/Append validates it.",
          "Hold/Rerun/Fallback keeps the record useful without claiming this WebView sample is accepted.",
        ],
      ));
      rows.push(add(
        "checklist-coverage",
        "Acceptance checklist coverage",
        requiredMissing.length ? "Blocked" : (recommendedMissing.length ? "Review" : "Ready"),
        `checked=${checkedCount}/${SAMPLE_VALIDATION_CHECK_FIELDS.length}; required missing=${sampleValidationAcceptanceCheckLabels(requiredMissing).join(", ") || "none"}; recommended missing=${sampleValidationAcceptanceCheckLabels(recommendedMissing).join(", ") || "none"}`,
        requiredMissing.length
          ? "Complete required checks or keep the decision as hold/review."
          : recommendedMissing.length
            ? "Document why subtitle/audio/pending-publish checks are not applicable before accepting."
            : "Checklist coverage is complete; still use backend Preview before Append.",
        [
          "Required checks cover route, completed output, sidecar/manifest, size growth, and diagnostics/log evidence.",
          "Recommended checks cover subtitle behavior, audio behavior, and pending-publish/not-applicable proof.",
        ],
      ));
      rows.push(add(
        "completed-packet",
        "Completed evidence packet",
        !completedRows.length ? "Blocked" : (completedBlocked ? "Blocked" : (completedReview ? "Review" : "Ready")),
        `packet rows=${completedRows.length}; blocked=${completedBlocked}; review/manual=${completedReview}; packet=${sampleValidationCompletedPacketStatus(context || {})}`,
        !completedRows.length
          ? "Load/select a Completed row and inspect the Completed Evidence Handoff before accepting."
          : completedBlocked
            ? "Resolve blocked Completed packet rows before appending accepted evidence."
            : completedReview
              ? "Walk the packet and document manual checks before accepted evidence."
              : "Completed packet is coherent-looking; manual playback/media checks remain authoritative.",
        [
          "Completed packet proof includes output/sidecar, route, size, audio/subtitle, pending/final placement, diagnostics, and manual playback prompts.",
        ],
      ));
      rows.push(add(
        "completed-policy-reconciliation",
        "Saved policy reconciliation",
        !completedPolicyRow ? "Review" : (completedPolicyRowState === "blocked" ? "Blocked" : (completedPolicyRowState === "match" ? "Ready" : "Review")),
        completedPolicyRow
          ? `${completedPolicyStatus}; ${completedPolicyRow.evidence || "policy evidence loaded without summary"}`
          : "No Completed saved-policy reconciliation row is loaded in the selected packet.",
        !completedPolicyRow
          ? "Load Sample Validation policy alignment and select a Completed row before appending accepted evidence."
          : completedPolicyRowState === "blocked"
            ? "Resolve blocked saved-policy reconciliation before accepting this completed sample."
            : completedPolicyRowState === "match"
              ? "Use this as supporting evidence only; manual playback/subtitle/audio/size checks still decide acceptance."
              : "Read the Saved policy reconciliation detail before accepting this completed sample.",
        completedPolicyRow
          ? [
              "This gate mirrors Completed > Selected Pilot Evidence Packet > Saved policy reconciliation.",
              "It compares saved route/size/subtitle/audio/publish policy categories with selected Completed output evidence.",
              "Missing visible category tokens are review gaps, not proof that backend policy failed.",
              ...((Array.isArray(completedPolicyRow.detail) && completedPolicyRow.detail.length) ? ["", ...completedPolicyRow.detail.slice(0, 8)] : []),
            ]
          : [
              "Home can only show this gate when Completed exposes a saved-policy reconciliation row.",
              "Preview/Append remains backend-owned and cannot infer missing media proof from frontend state.",
            ],
      ));
      const readinessStatus = String(readiness.operator_status || (log.exists ? "unknown" : "not-started"));
      const reconciliationStatus = String(reconciliation.operator_status || "not-loaded");
      const logErrors = Array.isArray(log.errors) ? log.errors.length : 0;
      rows.push(add(
        "backend-validation-state",
        "Backend validation state",
        logErrors ? "Blocked" : (["blocked", "stale"].includes(reconciliationStatus) || readinessStatus === "not-ready" ? "Review" : "Ready"),
        `readiness=${readinessStatus}; reconciliation=${reconciliationStatus}; log errors=${logErrors}; records=${Array.isArray(log.records) ? log.records.length : 0}`,
        logErrors
          ? "Read Diagnostics > Sample Validation Log before trusting the record panel."
          : "Use backend Preview to generate current evidence and append-readiness before any append.",
        [
          "The WebView gate is advisory. The backend preview/append route remains authoritative for record schema, size, current proof, and append readiness.",
        ],
      ));
      const mediaMissing = ["subtitle_checked", "audio_checked", "size_growth_checked", "diagnostics_checked"].filter((key) => !checks[key]);
      rows.push(add(
        "manual-media-proof",
        "Manual playback/media proof",
        mediaMissing.length ? "Review" : "Ready",
        `missing media checks=${sampleValidationAcceptanceCheckLabels(mediaMissing).join(", ") || "none"}; notes=${String(request.operator_notes || "").trim() ? "present" : "empty"}`,
        mediaMissing.length
          ? "Confirm Plex/client playback, subtitles, audio/default track behavior, seek/duration, and size posture before accepted evidence."
          : "Media checks are marked; add notes if anything was surprising or manually verified outside the app.",
        [
          "The app cannot prove Plex playback quality by itself.",
          "Use notes for client playback, subtitle timing/OCR quality, audio language/channel behavior, and unexpected output growth.",
        ],
      ));
      rows.push(add(
        "mutation-boundary",
        "Preview/append boundary",
        "Boundary",
        "Preview and Append are backend-owned sample-validation commands; this gate is display-only.",
        "Preview first. Append only if backend warnings, this gate, Completed packet, and manual checks agree.",
        [
          "This gate cannot append records, accept output, rerun, drain, publish, repair, save settings, rename, rewrite manifests/sidecars, change media policy, or touch media.",
        ],
      ));
      return rows;
    }

    function sampleValidationAcceptanceGateStatus(context = {}) {
      const rows = sampleValidationAcceptanceGateRows(context);
      const request = buildSampleValidationRequest(context || {});
      const blocked = rows.filter((row) => sampleValidationAcceptanceGateRowStatus(row) === "blocked").length;
      const review = rows.filter((row) => sampleValidationAcceptanceGateRowStatus(row) === "warning").length;
      if (request.operator_decision !== "accepted") return blocked ? "Hold/review blocked" : "Hold/review ready";
      if (blocked) return "Accepted append blocked";
      if (review) return "Accepted append review";
      return "Accepted preview ready";
    }

    function sampleValidationAcceptanceGateSummaryLines(context = {}) {
      const rows = sampleValidationAcceptanceGateRows(context);
      const request = buildSampleValidationRequest(context || {});
      const blocked = rows.filter((row) => sampleValidationAcceptanceGateRowStatus(row) === "blocked").length;
      const review = rows.filter((row) => sampleValidationAcceptanceGateRowStatus(row) === "warning").length;
      const ready = rows.filter((row) => sampleValidationAcceptanceGateRowStatus(row) === "match").length;
      const lines = [
        "Sample Validation acceptance readiness gate:",
        `Gate status: ${sampleValidationAcceptanceGateStatus(context || {})}`,
        `Operator decision: ${request.operator_decision || "hold_review"}; category=${request.sample_category || "general"}`,
        `Rows: ready=${ready}; review=${review}; blocked=${blocked}; total=${rows.length}`,
        `Evidence coverage: ${sampleValidationCheckedSummary(request.checks || {})}`,
        "Decision rule: accepted sample evidence should not be appended until required backend proof, Completed packet posture, manual playback/subtitle/audio/size checks, and backend Preview agree.",
      ];
      if (blocked) {
        lines.push("First action: resolve blocked gate rows or keep the decision as hold/review.");
      } else if (review) {
        lines.push("First action: review highlighted rows and document any not-applicable media checks before append.");
      } else if (request.operator_decision === "accepted") {
        lines.push("First action: use Preview Record, read backend warnings/readiness, then append only if the preview remains clean.");
      } else {
        lines.push("First action: keep hold/review, rerun, or external rollback until the operator intentionally accepts this sample.");
      }
      lines.push("Mutation guardrail: this gate is read-only and cannot append validation records, accept output, rerun, drain, publish, repair, save settings, rename, rewrite manifests/sidecars, change media policy, or touch media.");
      return lines;
    }

    function sampleValidationAcceptanceGateDetailLines(row) {
      if (!row) {
        return [
          "Sample Validation acceptance readiness gate:",
          "Select a gate row to inspect why Preview/Append should stay hold/review or can proceed to backend Preview.",
          "Mutation guardrail: this detail panel is read-only.",
        ];
      }
      return [
        "Sample Validation acceptance readiness gate:",
        `Gate: ${row.gate || "unknown"}`,
        `Status: ${row.status || "unknown"}`,
        `Evidence: ${row.evidence || ""}`,
        `Safe next action: ${row.action || ""}`,
        ...((Array.isArray(row.detail) && row.detail.length) ? ["", "Detail:", ...row.detail.map((line) => `- ${line}`)] : []),
        "",
        "Mutation guardrail: gate rows cannot append evidence, accept output, rerun, drain, publish, repair, save settings, rename, rewrite manifests/sidecars, change media policy, or touch media.",
      ];
    }

    function selectedSampleValidationAcceptanceGateRow(rows) {
      const list = Array.isArray(rows) ? rows : [];
      return list.find((row) => row.key === state.selectedSampleValidationAcceptanceGateKey)
        || list.find((row) => sampleValidationAcceptanceGateRowStatus(row) === "blocked")
        || list.find((row) => sampleValidationAcceptanceGateRowStatus(row) === "warning")
        || list[0]
        || null;
    }

    function renderSampleValidationAcceptanceGate(context = {}) {
      const rows = sampleValidationAcceptanceGateRows(context || {});
      if (state.selectedSampleValidationAcceptanceGateKey && !rows.some((row) => row.key === state.selectedSampleValidationAcceptanceGateKey)) {
        state.selectedSampleValidationAcceptanceGateKey = "";
      }
      const selected = selectedSampleValidationAcceptanceGateRow(rows);
      setRecordsPanelStatus("sample-validation-acceptance-gate-status", sampleValidationAcceptanceGateStatus(context || {}));
      setText("sample-validation-acceptance-gate-summary", sampleValidationAcceptanceGateSummaryLines(context || {}).join("\n"));
      setText("sample-validation-acceptance-gate-detail", sampleValidationAcceptanceGateDetailLines(selected).join("\n"));
      setText("sample-validation-acceptance-gate-legend", "Acceptance gate rows are read-only guidance and do not append validation records, accept output, rerun, drain, publish, repair, save settings, rename, rewrite manifests/sidecars, change media policy, or touch media.");
      const tbody = byId("sample-validation-acceptance-gate-rows");
      if (!tbody) return;
      if (!rows.length) {
        clearRows(tbody, 4, "No sample-validation acceptance gate rows loaded.");
        updateTableStatusLegend("sample-validation-acceptance-gate-legend", tbody, "Sample validation acceptance gate rows");
        return;
      }
      tbody.replaceChildren();
      rows.forEach((item) => {
        const row = document.createElement("tr");
        row.dataset.status = sampleValidationAcceptanceGateRowStatus(item);
        appendCells(row, [item.gate || "", item.status || "", item.evidence || "", item.action || ""]);
        makeRowSelectable(row, () => {
          state.selectedSampleValidationAcceptanceGateKey = item.key || "";
          setText("sample-validation-acceptance-gate-detail", sampleValidationAcceptanceGateDetailLines(item).join("\n"));
        }, {
          selected: item.key === selected?.key,
          label: `Review sample-validation acceptance gate ${item.gate || ""}`,
        });
        tbody.appendChild(row);
      });
      updateTableStatusLegend("sample-validation-acceptance-gate-legend", tbody, "Sample validation acceptance gate rows");
    }

    return {
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
    };
  }

  window.__crossPageSvRecordsModule = { createCrossPageSvRecordsModule };
})();
