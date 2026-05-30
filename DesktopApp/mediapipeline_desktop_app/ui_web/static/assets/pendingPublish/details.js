(function () {
  function createPendingPublishDetailsModule(deps = {}) {
    const {
      backendRowStatusState = null,
      byId = function () { return null; },
      diagnosticsBridgeHandoffLines = null,
      diagnosticsBridgeRowTrustLines = null,
      pendingDiagnosticsActionsForRow = function () { return []; },
      pendingFilterVisibilityLines = function () { return []; },
      pendingInvestigationSignalLines = function () { return []; },
      pendingListText = function (value) { return Array.isArray(value) && value.length ? value.join(", ") : "none"; },
      pendingRowKey = function (row) { return row?.row_key || ""; },
      pendingSelectedOpenTargetLines = function () { return []; },
      pendingSelectedQuickSignalLines = function () { return []; },
      renderPendingDiagnosticsLinks = function () {},
      setText = function () {},
    } = deps;

function pendingRowReviewChecklistLines(item) {
    if (!item) {
      return [
        "Selected pending-row review checklist:",
        "Select a pending publish row to see drain safety, payload, sidecar, manifest, and diagnostics guidance.",
      ];
    }
    const status = String(item.diagnostic_status || "").toLowerCase();
    const severity = String(item.diagnostic_severity || "").toLowerCase();
    const recommendation = String(item.drain_recommendation || "review").toLowerCase();
    const state = String(item.state || "").toLowerCase();
    const missingSidecars = Number(item.missing_sidecar_count || 0);
    const blockers = [];
    if (recommendation === "do_not_drain") blockers.push("backend marked do_not_drain");
    if (severity === "error") blockers.push("diagnostic severity is error");
    if (item.local_exists === false) blockers.push("local payload missing");
    if (missingSidecars > 0) blockers.push(`${missingSidecars} missing sidecar${missingSidecars === 1 ? "" : "s"}`);
    if (["invalid_manifest", "unreadable_manifest"].includes(state) || ["invalid_manifest", "unreadable_manifest"].includes(status)) blockers.push("manifest unreadable or invalid");
    if (state === "orphan_payload" || status === "orphan_payload") blockers.push("orphan payload");
    if (item.error) blockers.push("row error");
    const backendTrustState = String(item.operator_trust_state || "").trim();
    const lines = [
      "Selected pending-row review checklist:",
      `Row state: ${backendTrustState || (blockers.length ? "do-not-drain" : recommendation === "ready" || item.ready_to_drain ? "ready-looking" : "review")}`,
      `Diagnostic status: ${item.diagnostic_status || "unknown"}`,
      `Diagnostic severity: ${item.diagnostic_severity || "unknown"}`,
      `Drain recommendation: ${item.drain_recommendation || "review"}`,
      `Recovery class: ${item.recovery_class || "manual_review"}`,
      `Health blockers: ${blockers.length ? blockers.join(", ") : "none"}`,
      `Evidence fields: ${pendingListText(item.evidence_fields)}`,
      `Recommended open targets: ${pendingListText(item.recommended_open_targets)}`,
    ];
    if (item.issue_summary) lines.push(`Issue summary: ${item.issue_summary}`);
    if (item.error) lines.push(`Row error: ${item.error}`);
    if (item.operator_guidance) {
      lines.push(`Operator action: ${item.operator_guidance}`);
    }
    if (item.recovery_action) {
      lines.push(`Recovery action: ${item.recovery_action}`);
    } else if (blockers.length) {
      lines.push("Operator action: do not drain this row yet; inspect backend-selected payload/manifest/sidecar targets and logs.");
    } else if (recommendation === "review") {
      lines.push("Operator action: review row targets and diagnostics before publishing parked outputs.");
    } else {
      lines.push("Operator action: row looks ready, but Publish Parked Outputs remains the authoritative backend validation path.");
    }
    lines.push("Mutation guardrail: selected-row detail is read-only and cannot drain, repair, delete, rewrite, or publish files.");
    return lines;
  }

function pendingSelectedAtAGlanceState(item) {
    if (!item) return "unknown";
    const backendState = typeof backendRowStatusState === "function" ? backendRowStatusState(item) : "";
    if (["failed", "blocked"].includes(backendState)) return "blocked";
    if (backendState === "warning") return "warning";
    if (["match", "ready"].includes(backendState)) return "ready";
    const status = String(item.diagnostic_status || "").toLowerCase();
    const severity = String(item.diagnostic_severity || "").toLowerCase();
    const recommendation = String(item.drain_recommendation || "review").toLowerCase();
    const state = String(item.state || "").toLowerCase();
    const missingSidecars = Number(item.missing_sidecar_count || 0);
    const blocked = recommendation === "do_not_drain"
      || severity === "error"
      || item.local_exists === false
      || ["invalid_manifest", "unreadable_manifest"].includes(state)
      || ["invalid_manifest", "unreadable_manifest"].includes(status)
      || Boolean(item.error);
    if (blocked) return "blocked";
    if (missingSidecars > 0 || state === "orphan_payload" || status === "orphan_payload" || recommendation === "review" || !item.ready_to_drain) return "warning";
    return "ready";
  }

function pendingSelectedAtAGlanceStatus(item) {
    const state = pendingSelectedAtAGlanceState(item);
    if (state === "blocked") return "Do not drain";
    if (state === "warning") return "Review";
    if (state === "ready") return "Ready-looking";
    return "No selection";
  }

function pendingSelectedVisibilitySummary(item) {
    const lines = pendingFilterVisibilityLines(item);
    return lines
      .filter((line) => /^Selected row visible|^Active filters|^Hidden by current filters/.test(String(line || "")))
      .join(" ");
  }

function pendingSelectedAtAGlanceLines(item) {
    if (!item) {
      return [
        "Selected Pending Publish row: none",
        "Next step: select a pending row to review parked payload, manifest, sidecars, Completed correlation, and drain guidance.",
        "Authority: this summary is read-only. Backend Publish Parked Outputs remains the only path that can move parked files.",
      ];
    }
    const concern = item.primary_concern
      || item.issue_summary
      || item.error
      || item.operator_guidance
      || "no primary concern reported";
    const safeAction = item.safe_next_action
      || item.operator_guidance
      || item.recovery_action
      || (pendingSelectedAtAGlanceState(item) === "ready"
        ? "Use only backend-owned Publish Parked Outputs after page-level drain validation agrees."
        : "Inspect pending manifest/payload/sidecars, Completed correlation, Last Stderr, and Run Logs before drain.");
    return [
      `Selected Pending Publish row: ${item.local_file || item.server_out || item.manifest_path || "(unnamed row)"}`,
      `Trust/status: ${item.operator_trust_state || item.diagnostic_status || item.state || "not reported"}; at-a-glance=${pendingSelectedAtAGlanceStatus(item)}`,
      `Drain proof: recommendation=${item.drain_recommendation || "review"}; ready=${item.ready_to_drain ? "yes" : "no"}; recovery=${item.recovery_class || "manual_review"}`,
      `Primary concern: ${concern}`,
      `Safe next step: ${safeAction}`,
      `Filter visibility: ${pendingSelectedVisibilitySummary(item) || "not evaluated"}`,
      "Authority: this summary is read-only. It cannot drain, repair, move, delete, rewrite manifests, publish, or touch media files.",
    ];
  }

function renderPendingSelectedAtAGlance(item) {
    const status = pendingSelectedAtAGlanceStatus(item);
    setText("pending-selected-status", status);
    const statusNode = byId("pending-selected-status");
    if (statusNode) statusNode.dataset.state = pendingSelectedAtAGlanceState(item);
    setText("pending-selected-summary", pendingSelectedAtAGlanceLines(item).join("\n"));
  }

function pendingRowIssueDigestLines(item) {
    if (!item) return [];
    const status = String(item.diagnostic_status || "").toLowerCase();
    const severity = String(item.diagnostic_severity || "").toLowerCase();
    const recommendation = String(item.drain_recommendation || "review").toLowerCase();
    const state = String(item.state || "").toLowerCase();
    const missingSidecars = Number(item.missing_sidecar_count || 0);
    const issues = [];
    if (recommendation === "do_not_drain") issues.push("backend marked do_not_drain");
    if (severity === "error") issues.push("diagnostic severity is error");
    if (item.local_exists === false) issues.push("local payload missing");
    if (missingSidecars > 0) issues.push(`${missingSidecars} missing sidecar${missingSidecars === 1 ? "" : "s"}`);
    if (["invalid_manifest", "unreadable_manifest"].includes(state) || ["invalid_manifest", "unreadable_manifest"].includes(status)) issues.push("manifest unreadable or invalid");
    if (state === "orphan_payload" || status === "orphan_payload") issues.push("orphan payload");
    if (item.error) issues.push(`row error: ${item.error}`);
    const level = recommendation === "do_not_drain" || severity === "error" ? "do-not-drain" : issues.length ? "review" : item.ready_to_drain ? "ready-looking" : "review";
    const backendTrustState = String(item.operator_trust_state || "").trim();
    const lines = [
      "Selected pending issue digest:",
      `Issue level: ${backendTrustState || level}`,
      `Recovery class: ${item.recovery_class || "manual_review"}`,
      `Primary issue(s): ${issues.length ? issues.join("; ") : "none reported by pending scan"}`,
      `Evidence fields: ${pendingListText(item.evidence_fields)}`,
      `Proof to inspect: manifest=${item.manifest_path || "not reported"}; payload=${item.local_file || "not reported"}; destination=${item.server_out || "not reported"}`,
      `Drain proof: ${item.drain_recommendation || "review"}; status=${item.diagnostic_status || "unknown"}; severity=${item.diagnostic_severity || "unknown"}`,
    ];
    if (recommendation === "do_not_drain" || severity === "error") {
      lines.push("Safe next action: do not drain; inspect row targets, Pending Publish diagnostics, Last Stderr, and Run Logs first.");
    } else if (issues.length) {
      lines.push("Safe next action: review row targets before Publish Parked Outputs; backend drain validation remains authoritative.");
    } else if (item.ready_to_drain) {
      lines.push("Safe next action: row looks ready, but use only the backend-owned Publish Parked Outputs command to move files.");
    } else {
      lines.push("Safe next action: treat this row as review-needed until backend diagnostics or a refreshed pending scan marks it ready.");
    }
    return lines;
  }

function pendingRowCombinedReviewPlanLines(item) {
    if (!item) return [];
    const status = String(item.diagnostic_status || "").toLowerCase();
    const severity = String(item.diagnostic_severity || "").toLowerCase();
    const recommendation = String(item.drain_recommendation || "review").toLowerCase();
    const state = String(item.state || "").toLowerCase();
    const missingSidecars = Number(item.missing_sidecar_count || 0);
    const signals = [];
    if (recommendation === "do_not_drain") signals.push("backend do_not_drain");
    if (severity === "error") signals.push("diagnostic error");
    if (item.local_exists === false) signals.push("missing payload");
    if (missingSidecars > 0) signals.push(`${missingSidecars} missing sidecar${missingSidecars === 1 ? "" : "s"}`);
    if (["invalid_manifest", "unreadable_manifest"].includes(state) || ["invalid_manifest", "unreadable_manifest"].includes(status)) signals.push("invalid/unreadable manifest");
    if (state === "orphan_payload" || status === "orphan_payload") signals.push("orphan payload");
    if (item.error) signals.push(`row error ${item.error}`);
    const readFirst = ["Pending manifest"];
    if (item.local_exists === false) readFirst.push("Pending payload path");
    if (missingSidecars > 0) readFirst.push("Sidecar paths");
    if (recommendation === "do_not_drain" || severity === "error" || item.error) readFirst.push("Last Stderr", "Run Logs");
    const crossCheck = ["Completed Manifest correlation", "Durable drain summary"];
    if (item.source_path) crossCheck.push("Queue/source route evidence before rerun");
    if (item.recovery_class) crossCheck.push(`Recovery class ${item.recovery_class}`);
    const lines = [
      "Combined pending-row drain review plan:",
      `Signal count: ${signals.length}`,
      `Signals: ${signals.length ? signals.join("; ") : "none reported by the selected pending row"}`,
      `Read first: ${[...new Set(readFirst)].join(" -> ")}`,
      `Cross-check: ${[...new Set(crossCheck)].join(" -> ")}`,
    ];
    if (recommendation === "do_not_drain" || severity === "error") {
      lines.push("Decision: do not run Publish Parked Outputs for this row until pending artifacts and logs explain the blocker.");
    } else if (signals.length) {
      lines.push("Decision: review the selected artifacts first; backend drain validation remains authoritative.");
    } else if (item.ready_to_drain) {
      lines.push("Decision: row is ready-looking, but only backend-owned Publish Parked Outputs may move files.");
    } else {
      lines.push("Decision: treat this row as review-needed until pending scan and drain decision both report ready.");
    }
    lines.push("Guardrail: this combined plan is read-only and cannot drain, repair, move, delete, rewrite manifests, publish, or touch media files.");
    return lines;
  }

function pendingRealMediaTraceLines(item) {
    if (!item) return [];
    const proofSummary = Array.isArray(item.proof_summary) ? item.proof_summary.filter(Boolean) : [];
    const evidenceFields = Array.isArray(item.evidence_fields) ? item.evidence_fields.filter(Boolean) : [];
    const sidecars = Array.isArray(item.sidecar_paths) ? item.sidecar_paths.filter(Boolean) : [];
    const lines = [
      "Real-media sample trace: Pending Publish",
      `Trace key: payload=${item.local_file || "not reported"}; destination=${item.server_out || "not reported"}; source=${item.source_path || "not reported"}`,
      `Parking proof: state=${item.state || "unknown"}; manifest=${item.manifest_path || "not reported"}; payload exists=${item.local_exists === false ? "no" : item.local_exists === true ? "yes" : "unknown"}`,
      `Drain proof: recommendation=${item.drain_recommendation || "review"}; diagnostic=${[item.diagnostic_status, item.diagnostic_severity].filter(Boolean).join(" / ") || "unknown"}; ready=${item.ready_to_drain ? "yes" : "no"}`,
      "What this proves: the backend pending-publish scan can see a parked output or parked-output issue and can classify drain safety.",
      "What remains unproven: final publish completion until Publish Parked Outputs succeeds and durable drain summary/recent drain event agrees with Completed output proof.",
    ];
    if (proofSummary.length || evidenceFields.length) {
      lines.push("Pending proof to compare with Completed and logs:");
      proofSummary.slice(0, 5).forEach((line) => lines.push(`  ${line}`));
      if (evidenceFields.length) lines.push(`  evidence fields: ${evidenceFields.join(", ")}`);
    }
    if (sidecars.length) {
      lines.push(`Sidecar payloads: ${sidecars.length}; verify they drain with the media file when subtitle SRT sidecars are expected.`);
    }
    if (item.drain_recommendation === "do_not_drain" || item.ready_to_drain === false || item.local_exists === false) {
      lines.push("Drain boundary: do not drain this row until blockers are explained by pending diagnostics and logs.");
    }
    lines.push("Next evidence stop: run or review backend-owned recovery dry-run, then compare durable drain summary with Completed output proof after Publish Parked Outputs.");
    lines.push("Mutation guardrail: this trace is read-only and cannot drain, repair, delete, rewrite, move, publish, or mutate files.");
    return lines;
  }

function pendingCompletedCorrelationFirstValue(item, keys) {
    for (const key of keys) {
      const value = item?.[key];
      if (value !== undefined && value !== null && String(value).trim()) return String(value).trim();
    }
    return "";
  }

function pendingCompletedCorrelationNormalizePath(value) {
    const s = String(value || "").trim().replace(/\//g, "\\");
    const unc = s.startsWith("\\\\") ? "\\\\" : "";
    return (unc + s.slice(unc.length).replace(/\\+/g, "\\")).toLowerCase();
  }

function pendingCompletedCorrelationLeaf(value) {
    const text = String(value || "").trim();
    if (!text) return "";
    const parts = text.split(/[\\/]/).filter(Boolean);
    return parts.length ? parts[parts.length - 1] : text;
  }

function pendingCompletedCorrelationPendingDestinationPath(row) {
    return pendingCompletedCorrelationFirstValue(row, ["server_out", "destination_path", "output_path", "target_path", "final_path"]);
  }
function pendingCompletedCorrelationPendingSourcePath(row) {
    return pendingCompletedCorrelationFirstValue(row, ["source_path", "input_path", "source_file"]);
  }
function pendingCompletedCorrelationPendingLocalPath(row) {
    return pendingCompletedCorrelationFirstValue(row, ["local_file", "payload_path", "payload_file"]);
  }
function pendingCompletedCorrelationCompletedOutputPath(row) {
    return pendingCompletedCorrelationFirstValue(row, ["output_path", "server_out", "destination_path", "final_path", "output_file"]);
  }
function pendingCompletedCorrelationCompletedSourcePath(row) {
    return pendingCompletedCorrelationFirstValue(row, ["source_path", "input_path", "source_file"]);
  }

function pendingCompletedCorrelationCompletedRowLabel(row) {
    return pendingCompletedCorrelationFirstValue(row, ["lookup_title", "output_file", "title", "route_label"])
      || pendingCompletedCorrelationLeaf(pendingCompletedCorrelationCompletedOutputPath(row))
      || pendingCompletedCorrelationLeaf(pendingCompletedCorrelationCompletedSourcePath(row))
      || "(completed row)";
  }

function pendingCompletedCorrelationLoadedRows() {
    if (typeof window.getLastCompletedRows === "function") {
      const rows = window.getLastCompletedRows();
      return Array.isArray(rows) ? rows : [];
    }
    return [];
  }

function pendingSelectedCompletedCorrelationRows(item) {
    const completedRows = pendingCompletedCorrelationLoadedRows();
    const pendingDestination = pendingCompletedCorrelationPendingDestinationPath(item);
    const pendingSource = pendingCompletedCorrelationPendingSourcePath(item);
    const pendingLocal = pendingCompletedCorrelationPendingLocalPath(item);
    const pendingDestinationKey = pendingCompletedCorrelationNormalizePath(pendingDestination);
    const pendingSourceKey = pendingCompletedCorrelationNormalizePath(pendingSource);
    const pendingDestinationLeaf = pendingCompletedCorrelationLeaf(pendingDestination).toLowerCase();
    const pendingLocalLeaf = pendingCompletedCorrelationLeaf(pendingLocal).toLowerCase();
    const exactDestination = [];
    const exactSource = [];
    const sameLeaf = [];
    const addMatch = (collection, completedRow, index, matchType, evidence, outputPath, sourcePath) => {
      collection.push({
        completedRow,
        index,
        matchType,
        evidence,
        outputPath,
        sourcePath,
        label: pendingCompletedCorrelationCompletedRowLabel(completedRow),
        status: completedRow?.operator_trust_state || completedRow?.consistency_status || completedRow?.output_health || completedRow?.status || "unknown",
      });
    };
    completedRows.forEach((completedRow, index) => {
      const outputPath = pendingCompletedCorrelationCompletedOutputPath(completedRow);
      const sourcePath = pendingCompletedCorrelationCompletedSourcePath(completedRow);
      const outputKey = pendingCompletedCorrelationNormalizePath(outputPath);
      const sourceKey = pendingCompletedCorrelationNormalizePath(sourcePath);
      const outputLeaf = pendingCompletedCorrelationLeaf(outputPath).toLowerCase();
      if (pendingDestinationKey && outputKey && pendingDestinationKey === outputKey) {
        addMatch(exactDestination, completedRow, index, "exact-destination", "pending destination equals completed output", outputPath, sourcePath);
      }
      if (pendingSourceKey && sourceKey && pendingSourceKey === sourceKey) {
        addMatch(exactSource, completedRow, index, "exact-source", "pending source equals completed source", outputPath, sourcePath);
      }
      if (
        outputLeaf
        && (outputLeaf === pendingDestinationLeaf || outputLeaf === pendingLocalLeaf)
        && !(pendingDestinationKey && outputKey && pendingDestinationKey === outputKey)
      ) {
        addMatch(sameLeaf, completedRow, index, "same-leaf", "completed output filename matches pending destination or local payload leaf only", outputPath, sourcePath);
      }
    });
    return {
      completedRows,
      pendingDestination,
      pendingSource,
      pendingLocal,
      exactDestination,
      exactSource,
      sameLeaf,
    };
  }

function pendingCompletedCorrelationMatchLine(match) {
    return `- ${match.label}: ${match.evidence}; status=${match.status}; completed output=${match.outputPath || "unknown"}; completed source=${match.sourcePath || "unknown"}`;
  }

function pendingSelectedCompletedCorrelationLines(item) {
    if (!item) {
      return [
        "Completed Manifest correlation for selected pending row:",
        "Select a pending row to compare its destination/source against the loaded Completed Manifest rows.",
        "Mutation guardrail: this pending-row correlation is read-only and cannot mark done, drain, rerun, delete, publish, rewrite manifests, or touch media.",
      ];
    }
    const correlation = pendingSelectedCompletedCorrelationRows(item);
    const lines = [
      "Completed Manifest correlation for selected pending row:",
      `Completed rows loaded: ${correlation.completedRows.length}`,
      `Pending destination: ${correlation.pendingDestination || "unknown"}`,
      `Pending source: ${correlation.pendingSource || "unknown"}`,
      `Pending local payload: ${correlation.pendingLocal || "unknown"}`,
      `Exact pending destination -> completed output: ${correlation.exactDestination.length}`,
      `Exact pending source -> completed source: ${correlation.exactSource.length}`,
      `Same-leaf completed output hints: ${correlation.sameLeaf.length}`,
      "Proof order: exact normalized destination/source path matches are stronger than same-leaf filename matches.",
      "Boundary: same-leaf matches are duplicate-title hints only and do not prove publish completion.",
    ];
    if (!correlation.completedRows.length) {
      lines.push("No Completed rows are loaded in this WebView session. Open or refresh Completed before deciding whether this parked output already has completed-history proof.");
    }
    if (correlation.exactDestination.length) {
      lines.push("Exact destination matches:");
      correlation.exactDestination.slice(0, 4).forEach((match) => lines.push(pendingCompletedCorrelationMatchLine(match)));
    }
    if (correlation.exactSource.length) {
      lines.push("Exact source matches:");
      correlation.exactSource.slice(0, 4).forEach((match) => lines.push(pendingCompletedCorrelationMatchLine(match)));
    }
    if (correlation.sameLeaf.length) {
      lines.push("Same-leaf review hints:");
      correlation.sameLeaf.slice(0, 4).forEach((match) => lines.push(pendingCompletedCorrelationMatchLine(match)));
    }
    if (!correlation.exactDestination.length && !correlation.exactSource.length && correlation.completedRows.length) {
      lines.push("No exact Completed proof is loaded for this pending row. Inspect Completed, Pending Publish, Run Logs, Last Stderr, and durable drain summaries before assuming publish success or data loss.");
    }
    lines.push("Mutation guardrail: this pending-row correlation is read-only and cannot mark done, drain, rerun, delete, publish, rewrite manifests, or touch media.");
    return lines;
  }

function pendingSampleValidationHandoffLines(item) {
    if (!item) return [];
    const recommendation = String(item.drain_recommendation || "review").toLowerCase();
    const state = String(item.state || "").toLowerCase();
    const status = String(item.diagnostic_status || item.state || "").toLowerCase();
    const severity = String(item.diagnostic_severity || "").toLowerCase();
    const blocked = Boolean(
      recommendation === "do_not_drain"
      || item.ready_to_drain === false
      || item.local_exists === false
      || severity === "error"
      || ["invalid_manifest", "unreadable_manifest", "orphan_payload", "missing_payload"].some((token) => status.includes(token) || state.includes(token))
    );
    const suggestedDecision = blocked
      ? "hold_review until pending blockers are explained"
      : "accepted only after Completed output proof and durable drain summary agree";
    const lines = [
      "Sample Validation handoff: Pending Publish",
      "Suggested pilot category: deferred-publish",
      `Suggested evidence decision: ${suggestedDecision}`,
      `Current pending proof: recommendation=${item.drain_recommendation || "review"}; ready=${item.ready_to_drain ? "yes" : "no"}; state=${item.state || "unknown"}; diagnostic=${[item.diagnostic_status, item.diagnostic_severity].filter(Boolean).join(" / ") || "unknown"}`,
      "Record evidence only after comparing Pending Publish row proof, Completed output proof, durable drain summary, Run Logs, and Last Stderr.",
    ];
    if (blocked) {
      lines.push("Do not append accepted sample evidence from this pending row until blockers are resolved or intentionally documented as review evidence.");
    } else {
      lines.push("If this row is part of a real-media pilot, use Home Sample Validation after backend-owned Publish Parked Outputs and post-drain proof are checked.");
    }
    lines.push("Home Sample Validation can write JSONL evidence notes only; it cannot drain, publish, mark complete, accept output, rewrite manifests, or mutate media.");
    return lines;
  }

function pendingSampleValidationComparisonLines(item) {
    const context = window.mediaPipelineLastCrossPageContext || {};
    const log = context.sampleValidation || {};
    const rows = typeof window.sampleValidationRecordComparisonRowsForPaths === "function"
      ? window.sampleValidationRecordComparisonRowsForPaths(
        log,
        [
          item?.source_path,
          item?.server_out,
          item?.destination_path,
          item?.output_path,
          item?.local_file,
          item?.payload_path,
        ],
        item?.lookup_title || item?.output_file || item?.server_out || item?.local_file || "",
      )
      : [];
    const current = rows.filter((row) => row.current_status === "current").length;
    const stale = rows.filter((row) => row.current_status === "stale").length;
    const review = rows.filter((row) => ["review", "not checked", "unknown"].includes(row.current_status)).length;
    const accepted = rows.filter((row) => row.operator_decision === "accepted").length;
    const lines = [
      "Sample Validation comparison for selected Pending Publish row:",
      `Matching evidence records: ${rows.length}; accepted=${accepted}; current=${current}; stale=${stale}; review/not-checked=${review}.`,
      `Pending source: ${item?.source_path || "unknown"}`,
      `Pending destination: ${item?.server_out || item?.destination_path || item?.output_path || "unknown"}`,
      `Parked payload: ${item?.local_file || item?.payload_path || "unknown"}`,
    ];
    if (!rows.length) {
      lines.push(
        "No matching Sample Validation record is loaded for this pending source/destination/payload.",
        "Next action: keep deferred-publish evidence at hold/review until Completed, Pending Publish, durable drain summary, Diagnostics, playback, and output proof agree."
      );
    } else {
      rows.slice(0, 4).forEach((row) => {
        const gaps = Array.isArray(row.missing_current_evidence) && row.missing_current_evidence.length
          ? ` gaps=${row.missing_current_evidence.join("; ")}`
          : " gaps=none";
        lines.push(`- ${row.created_at || "unknown time"} ${row.operator_decision || "unknown decision"} category=${row.sample_category || "general"} proof=${row.proof_strength || "unknown"} match=${row.match_strength} fields=${(row.match_fields || []).join(",") || "unknown"} current=${row.current_status || "not checked"}${gaps}`);
      });
      lines.push("Next action: if a matching record is not current, preview a fresh deferred-publish evidence note only after post-drain/final-placement proof is coherent.");
    }
    lines.push(
      "Post-run capture: Preview Record includes pending/final-placement proof rows; use category deferred-publish for parked/drained samples.",
      "Mutation guardrail: this comparison is read-only and cannot append Sample Validation records, drain, publish, repair, rewrite manifests/sidecars, move/delete payloads, save settings, rename, or touch media."
    );
    return lines;
  }

function pendingRowTrustSummaryLines(item) {
    if (!item || typeof diagnosticsBridgeRowTrustLines !== "function") return [];
    const status = String(item.diagnostic_status || "").toLowerCase();
    const severity = String(item.diagnostic_severity || "").toLowerCase();
    const recommendation = String(item.drain_recommendation || "review").toLowerCase();
    const state = String(item.state || "").toLowerCase();
    const missingSidecars = Number(item.missing_sidecar_count || 0);
    const issues = [];
    if (recommendation === "do_not_drain") issues.push("backend marked do_not_drain");
    if (severity === "error") issues.push("diagnostic severity is error");
    if (item.local_exists === false) issues.push("local payload missing");
    if (missingSidecars > 0) issues.push(`${missingSidecars} missing sidecar${missingSidecars === 1 ? "" : "s"}`);
    if (["invalid_manifest", "unreadable_manifest"].includes(state) || ["invalid_manifest", "unreadable_manifest"].includes(status)) issues.push("manifest unreadable or invalid");
    if (state === "orphan_payload" || status === "orphan_payload") issues.push("orphan payload");
    if (item.error) issues.push(`row error: ${item.error}`);
    const backendTrustState = String(item.operator_trust_state || "").trim();
    const trustState = backendTrustState || (recommendation === "do_not_drain" || severity === "error"
      ? "do-not-drain"
      : issues.length
        ? "review-before-drain"
        : item.ready_to_drain
          ? "ready-looking"
          : "review");
    const proofSummary = Array.isArray(item.proof_summary) ? item.proof_summary.filter(Boolean) : [];
    return diagnosticsBridgeRowTrustLines("Pending Publish selected row", pendingDiagnosticsActionsForRow(item), {
      trustState,
      primaryConcern: item.primary_concern || (issues.length ? issues.join("; ") : item.ready_to_drain ? "row has no blocker in the loaded pending scan" : "backend still marks this row for review"),
      evidence: proofSummary.length ? proofSummary : [
        item.diagnostic_status || item.diagnostic_severity ? `diagnostic=${[item.diagnostic_status, item.diagnostic_severity].filter(Boolean).join(" / ")}` : "",
        item.drain_recommendation ? `drain=${item.drain_recommendation}` : "",
        item.recovery_class || item.recovery_action ? `recovery=${[item.recovery_class, item.recovery_action].filter(Boolean).join(" - ")}` : "",
        item.local_file ? `payload=${item.local_file}` : "",
        item.manifest_path ? `manifest=${item.manifest_path}` : "",
        item.server_out ? `destination=${item.server_out}` : "",
      ],
      safeAction: item.safe_next_action || (trustState === "ready-looking" ? "use only backend-owned Publish Parked Outputs after page-level validation agrees." : "inspect pending manifest/payload/sidecar evidence, Last Stderr, and Run Logs before drain."),
      unsafeAction: item.unsafe_if_ignored || "move, delete, drain, repair, or rewrite pending payloads/manifests from this page.",
      owningPages: "Pending Publish owns parked output safety; Completed owns output proof; Queue owns rerun risk; Diagnostics owns artifact/log evidence.",
    });
  }

function renderPendingDetail(item) {
    renderPendingSelectedAtAGlance(item || null);
    if (!item) {
      setText("pending-detail", pendingRowReviewChecklistLines(null).join("\n"));
      renderPendingDiagnosticsLinks(null);
      return;
    }
    const sidecars = Array.isArray(item.sidecar_paths) ? item.sidecar_paths.join("\n  ") : "";
    const proofSummary = Array.isArray(item.proof_summary) ? item.proof_summary : [];
    const diagnosticTargets = Array.isArray(item.recommended_diagnostics_targets) ? item.recommended_diagnostics_targets.join(", ") : "";
    const handoffLines = typeof diagnosticsBridgeHandoffLines === "function"
      ? diagnosticsBridgeHandoffLines("Pending Publish selected row", pendingDiagnosticsActionsForRow(item), {
        evidence: [
          item.diagnostic_status || item.diagnostic_severity ? `diagnostic=${[item.diagnostic_status, item.diagnostic_severity].filter(Boolean).join(" / ")}` : "",
          item.drain_recommendation ? `drain=${item.drain_recommendation}` : "",
          item.recovery_class || item.recovery_action ? `recovery=${[item.recovery_class, item.recovery_action].filter(Boolean).join(" - ")}` : "",
          item.manifest_path || item.local_file ? `payload=${item.local_file || item.manifest_path}` : "",
        ],
        safeAction: "compare Pending Publish, manifest/payload/sidecar evidence, Last Stderr, and Run Logs before using Publish Parked Outputs.",
      })
      : [];
    const detail = [
      ...pendingSelectedQuickSignalLines(item),
      "",
      ...pendingRowReviewChecklistLines(item),
      "",
      ...pendingRowIssueDigestLines(item),
      "",
      ...pendingRowCombinedReviewPlanLines(item),
      "",
      ...pendingInvestigationSignalLines(item),
      "",
      ...pendingRealMediaTraceLines(item),
      "",
      ...pendingSelectedCompletedCorrelationLines(item),
      "",
      ...pendingSampleValidationHandoffLines(item),
      "",
      ...pendingSampleValidationComparisonLines(item),
      "",
      ...pendingRowTrustSummaryLines(item),
      "",
      ...handoffLines,
      "",
      ...pendingSelectedOpenTargetLines(item),
      "",
      `State: ${item.state || ""}`,
      item.operator_trust_state ? `Backend trust state: ${item.operator_trust_state}` : "",
      item.primary_concern ? `Primary concern: ${item.primary_concern}` : "",
      item.safe_next_action ? `Safe next action: ${item.safe_next_action}` : "",
      item.unsafe_if_ignored ? `Unsafe if ignored: ${item.unsafe_if_ignored}` : "",
      proofSummary.length ? "Backend proof summary:" : "",
      ...proofSummary.map((line) => `  ${line}`),
      diagnosticTargets ? `Recommended diagnostics targets: ${diagnosticTargets}` : "",
      `Row key: ${item.row_key || pendingRowKey(item) || ""}`,
      `Route: ${item.route || ""}`,
      `Publish mode: ${item.publish_mode || ""}`,
      `Diagnostic status: ${item.diagnostic_status || "unknown"}`,
      `Diagnostic severity: ${item.diagnostic_severity || "unknown"}`,
      `Drain recommendation: ${item.drain_recommendation || "review"}`,
      `Operator guidance: ${item.operator_guidance || "Review this pending row before drain."}`,
      `Recovery class: ${item.recovery_class || "manual_review"}`,
      `Recovery action: ${item.recovery_action || "Review this row with Pending Publish diagnostics before drain."}`,
      `Evidence fields: ${pendingListText(item.evidence_fields)}`,
      `Recommended open targets: ${pendingListText(item.recommended_open_targets)}`,
      `Available open targets: ${pendingListText(item.available_open_targets)}`,
      `Size: ${item.size_text || ""} (${item.output_size || 0} bytes)`,
      `Parked: ${item.parked_at || item.parked_at_display || ""}`,
      `Age: ${item.age_text || ""}`,
      `Local payload: ${item.local_file || ""}`,
      `Local exists: ${item.local_exists === false ? "no" : item.local_exists === true ? "yes" : ""}`,
      `Destination: ${item.server_out || ""}`,
      `Source: ${item.source_path || ""}`,
      `Manifest: ${item.manifest_path || ""}`,
      `Schema: ${item.schema_version || ""}`,
      `Sidecars: ${item.sidecar_count || 0}`,
      `Missing sidecars: ${item.missing_sidecar_count || 0}`,
      `Ready to drain: ${item.ready_to_drain ? "yes" : "no"}`,
      item.issue_summary ? `Issue summary: ${item.issue_summary}` : "",
      sidecars ? `Sidecar paths:\n  ${sidecars}` : "",
      item.error ? `Issue: ${item.error}` : "",
    ].filter(Boolean);
    setText("pending-detail", detail.join("\n"));
    renderPendingDiagnosticsLinks(item);
  }

    return {
      pendingRowReviewChecklistLines,
      pendingSelectedAtAGlanceState,
      pendingSelectedAtAGlanceStatus,
      pendingSelectedVisibilitySummary,
      pendingSelectedAtAGlanceLines,
      renderPendingSelectedAtAGlance,
      pendingRowIssueDigestLines,
      pendingRowCombinedReviewPlanLines,
      pendingRealMediaTraceLines,
      pendingCompletedCorrelationFirstValue,
      pendingCompletedCorrelationNormalizePath,
      pendingCompletedCorrelationLeaf,
      pendingCompletedCorrelationPendingDestinationPath,
      pendingCompletedCorrelationPendingSourcePath,
      pendingCompletedCorrelationPendingLocalPath,
      pendingCompletedCorrelationCompletedOutputPath,
      pendingCompletedCorrelationCompletedSourcePath,
      pendingCompletedCorrelationCompletedRowLabel,
      pendingCompletedCorrelationLoadedRows,
      pendingSelectedCompletedCorrelationRows,
      pendingCompletedCorrelationMatchLine,
      pendingSelectedCompletedCorrelationLines,
      pendingSampleValidationHandoffLines,
      pendingSampleValidationComparisonLines,
      pendingRowTrustSummaryLines,
      renderPendingDetail,
    };
  }

  window.__pendingPublishDetailsModule = {
    createPendingPublishDetailsModule,
  };
})();
