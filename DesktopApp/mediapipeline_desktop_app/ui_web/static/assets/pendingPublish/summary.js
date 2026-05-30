(function () {
  function createPendingPublishSummaryModule(deps = {}) {
    const {
      appendCells = function () {},
      byId = function () { return null; },
      clearRows = function () {},
      getSelectedPendingRowKey = function () { return ""; },
      makeRowSelectable = function () {},
      pendingDrainSummaryStatus = function () { return "No summary"; },
      pendingRowKey = function (row) { return row?.row_key || ""; },
      renderProgressBarsInto = null,
      selectPendingRow = function () {},
      setText = function () {},
      shortenPath = function (value) { return value; },
      updateTableStatusLegend = function () {},
    } = deps;

function pendingInventoryProgressBars(pending) {
    const payload = pending && typeof pending === "object" ? pending : {};
    const progress = payload.inventory_progress && typeof payload.inventory_progress === "object" ? payload.inventory_progress : {};
    if (Array.isArray(progress.progress_bars)) return progress.progress_bars.filter(Boolean);
    if (Array.isArray(payload.progress_bars)) return payload.progress_bars.filter(Boolean);
    return [];
  }

function renderPendingInventoryProgress(pending) {
    if (typeof renderProgressBarsInto !== "function") return;
    const payload = pending && typeof pending === "object" ? pending : {};
    const progress = payload.inventory_progress && typeof payload.inventory_progress === "object" ? payload.inventory_progress : {};
    renderProgressBarsInto("pending-inventory-progress-bars", pendingInventoryProgressBars(payload), progress, "No pending inventory progress loaded.");
  }

function pendingEmptyStateMessage(pending, rows) {
    if (pending.error) {
      return `Pending publish unavailable: ${pending.error}. Open Diagnostics > Pending Publish and Run Logs.`;
    }
    const warnings = Array.isArray(pending.warnings) ? pending.warnings.filter(Boolean) : [];
    if (warnings.length) {
      return `Pending publish loaded with warning: ${warnings.join(" | ")}`;
    }
    if (!pending.exists) {
      return "No pending-publish folder exists yet. This is normal until Deferred Publish parks an output.";
    }
    if (!rows.length) {
      return "No parked outputs are waiting to publish. If an output is missing, check completed history and Run Logs before reprocessing.";
    }
    return "No pending publish rows available.";
  }

function pendingStateCounts(rows) {
    const counts = {};
    rows.forEach((row) => {
      const key = String(row?.state || "unknown").trim() || "unknown";
      counts[key] = (counts[key] || 0) + 1;
    });
    return counts;
  }

function formatPendingStateCounts(rows) {
    const counts = pendingStateCounts(rows);
    return Object.keys(counts).sort().map((key) => `${key}=${counts[key]}`).join(", ") || "none";
  }

function pendingRowHasHealthIssue(row) {
    const missingSidecars = Number(row?.missing_sidecar_count || 0);
    const state = String(row?.state || "").toLowerCase();
    return Boolean(
      row?.diagnostic_severity === "error" ||
      row?.drain_recommendation === "do_not_drain" ||
      row?.error ||
      row?.local_exists === false ||
      missingSidecars > 0 ||
      state === "orphan_payload" ||
      state === "invalid_manifest" ||
      state === "unreadable_manifest"
    );
  }

function pendingPublishReadinessStatus(pending, rows) {
    const rowList = Array.isArray(rows) ? rows : [];
    if (pending?.error) return "Unavailable";
    if (!pending?.exists) return "No pending root";
    if (!rowList.length) return "Empty";
    if (rowList.some(pendingRowHasHealthIssue) || Number(pending?.health_count || 0) > 0 || Number(pending?.missing_local_count || 0) > 0) {
      return "Review before drain";
    }
    const warnings = Array.isArray(pending?.warnings) ? pending.warnings.filter(Boolean) : [];
    if (warnings.length) return "Warnings";
    return "Ready-looking";
  }

function pendingPublishReadinessLines(pending, rows) {
    const payload = pending || {};
    const rowList = Array.isArray(rows) ? rows : [];
    if (payload.error) {
      return [
        `Status: unavailable`,
        `Error: ${payload.error}`,
        "Safe action: open Diagnostics > Pending Publish and Run Logs before retrying a drain.",
        "Backend drain command remains the source of truth; this summary does not authorize publish.",
      ];
    }
    const issueRows = rowList.filter(pendingRowHasHealthIssue);
    const warnings = Array.isArray(payload.warnings) ? payload.warnings.filter(Boolean) : [];
    const lines = [
      `Pending root: ${payload.pending_root || "not reported"}`,
      `Root exists: ${payload.exists ? "yes" : "no"}`,
      `Parked manifests: ${payload.count || rowList.length || 0}`,
      `Payloads: ${payload.payload_count || 0}`,
      `Health rows: ${payload.health_count || 0}`,
      `Missing payload references: ${payload.missing_local_count || 0}`,
      `Ready rows: ${payload.ready_count || 0}`,
      `Issue rows: ${payload.issue_count || issueRows.length}`,
      `Missing sidecars: ${payload.missing_sidecar_count || 0}`,
      `Rows needing review: ${issueRows.length}`,
      `States: ${formatPendingStateCounts(rowList)}`,
      `Diagnostic statuses: ${pendingFormatCounts(payload.diagnostic_status_counts)}`,
      `Diagnostic severities: ${pendingFormatCounts(payload.diagnostic_severity_counts)}`,
      `Backend trust states: ${pendingFormatCounts(payload.operator_trust_state_counts)}`,
      `Recovery classes: ${pendingFormatCounts(payload.recovery_class_counts)}`,
      `Suggested open targets: ${pendingFormatCounts(payload.recommended_open_target_counts)}`,
      `Available open targets: ${pendingFormatCounts(payload.available_open_target_counts)}`,
    ];
    lines.push("", ...pendingRecoverySummaryLines(payload));
    if (warnings.length) {
      lines.push("", "Warning(s):");
      warnings.slice(0, 5).forEach((warning) => lines.push(`- ${warning}`));
    }
    lines.push("");
    if (!payload.exists) {
      lines.push("Safe action: no drain is needed until Deferred Publish parks outputs.");
    } else if (!rowList.length) {
      lines.push("Safe action: no parked outputs are waiting. Do not reprocess solely because this list is empty; check Completed History and Run Logs first.");
    } else if (issueRows.length || Number(payload.health_count || 0) > 0 || Number(payload.missing_local_count || 0) > 0) {
      lines.push("Safe action: review row issues before publishing. Open the selected manifest/local payload/destination using backend-selected open buttons.");
    } else if (warnings.length) {
      lines.push("Safe action: drain may be possible, but review warnings first.");
    } else {
      lines.push("Safe action: pending rows look ready for Publish Parked Outputs.");
    }
    lines.push("Backend drain command remains the source of truth; this summary does not bypass backend validation or publish checks.");
    return lines;
  }

function renderPendingPublishReadiness(pending, rows) {
    const rowList = Array.isArray(rows) ? rows : [];
    setText("pending-publish-readiness-status", pendingPublishReadinessStatus(pending || {}, rowList));
    setText("pending-publish-readiness", pendingPublishReadinessLines(pending || {}, rowList).join("\n"));
  }

function pendingWorkflowStatus(pending, rows) {
    const payload = pending || {};
    const rowList = Array.isArray(rows) ? rows : [];
    const warnings = Array.isArray(payload.warnings) ? payload.warnings.filter(Boolean) : [];
    if (payload.error) return "Diagnostics first";
    if (payload.exists === false) return "No pending root";
    if (!rowList.length) return "No drain";
    if (pendingValidationStatus(payload, rowList) === "Do not drain") return "Do not drain";
    if (Number(payload.issue_count || 0) > 0 || rowList.some(pendingRowHasHealthIssue)) return "Review rows";
    if (warnings.length) return "Review context";
    return "Drain path clear";
  }

function pendingWorkflowLines(pending, rows) {
    const payload = pending || {};
    const rowList = Array.isArray(rows) ? rows : [];
    const warnings = Array.isArray(payload.warnings) ? payload.warnings.filter(Boolean) : [];
    const issueRows = rowList.filter(pendingRowHasHealthIssue);
    const lines = [
      "Cross-page workflow: Pending Publish",
      `Drain readiness: ${pendingPublishReadinessStatus(payload, rowList)}`,
      `Pending validation: ${pendingValidationStatus(payload, rowList)}`,
      `Rows loaded: ${payload.count || rowList.length || 0}`,
      `Payload rows: ${payload.payload_count || 0}`,
      `Ready rows: ${payload.ready_count || 0}`,
      `Issue rows: ${payload.issue_count || issueRows.length}`,
      `Health rows: ${payload.health_count || 0}`,
      `Missing payload references: ${payload.missing_local_count || 0}`,
    ];
    lines.push("");
    if (payload.error) {
      lines.push("Next step: open Diagnostics > State Artifact Summary, Pending Publish, Run Logs, and Last Stderr before another publish attempt.");
    } else if (payload.exists === false) {
      lines.push("Next step: no pending-publish root exists. Check Completed before rerun and do not assume outputs were lost solely from an empty pending view.");
    } else if (!rowList.length) {
      lines.push("Next step: no parked outputs are waiting. If an expected output is missing, inspect Completed and Run Logs before reprocessing.");
    } else if (pendingValidationStatus(payload, rowList) === "Do not drain") {
      lines.push("Next step: do not drain. Select the issue row, use Pending Diagnostics Cross-Links, and inspect manifest/payload/sidecar/log evidence first.");
    } else if (Number(payload.issue_count || 0) > 0 || issueRows.length || warnings.length) {
      lines.push("Next step: review issue/warning rows and Last Stderr before using Publish Parked Outputs.");
    } else {
      lines.push("Next step: pending publish context is coherent. Publish Parked Outputs remains the backend-owned drain command.");
    }
    lines.push("Owning pages: Pending Publish for parked output safety, Completed for output proof, Queue before rerun, Diagnostics for artifacts/logs.");
    lines.push("Mutation guardrail: this workflow panel is read-only. Publish Parked Outputs remains backend-owned.");
    return lines;
  }

function renderPendingWorkflow(pending, rows) {
    const rowList = Array.isArray(rows) ? rows : [];
    setText("pending-workflow-status", pendingWorkflowStatus(pending || {}, rowList));
    setText("pending-workflow", pendingWorkflowLines(pending || {}, rowList).join("\n"));
  }

function pendingReviewRowReasons(row) {
    const reasons = [];
    const severity = String(row?.diagnostic_severity || "").toLowerCase();
    const recommendation = String(row?.drain_recommendation || "").toLowerCase();
    const state = String(row?.state || "").toLowerCase();
    if (severity === "error") reasons.push("diagnostic error");
    if (severity === "warning") reasons.push("diagnostic warning");
    if (recommendation === "do_not_drain") reasons.push("do-not-drain recommendation");
    if (row?.local_exists === false) reasons.push("missing local payload");
    if (Number(row?.missing_sidecar_count || 0) > 0) reasons.push(`missing sidecars: ${row.missing_sidecar_count}`);
    if (["orphan_payload", "invalid_manifest", "unreadable_manifest"].includes(state)) reasons.push(`state: ${row.state}`);
    if (row?.error) reasons.push(`error: ${row.error}`);
    if (row?.issue_summary) reasons.push(`issue: ${row.issue_summary}`);
    if (String(row?.operator_trust_state || "").toLowerCase().includes("review") || String(row?.operator_trust_state || "").toLowerCase().includes("drain")) {
      reasons.push(`trust state: ${row.operator_trust_state}`);
    }
    if (row?.recovery_class && String(row.recovery_class).toLowerCase() !== "ready") reasons.push(`recovery: ${row.recovery_class}`);
    if (row?.primary_concern) reasons.push(`primary concern: ${row.primary_concern}`);
    return reasons.filter(Boolean);
  }

function pendingReviewRows(pending, rows) {
    const rowList = Array.isArray(rows) ? rows : [];
    return rowList
      .map((row, index) => ({ row, index, reasons: pendingReviewRowReasons(row) }))
      .filter((entry) => entry.reasons.length)
      .sort((a, b) => {
        const rank = (entry) => String(entry.row?.drain_recommendation || "").toLowerCase() === "do_not_drain" ? 0
          : String(entry.row?.diagnostic_severity || "").toLowerCase() === "error" ? 1
            : entry.row?.local_exists === false ? 2
              : String(entry.row?.diagnostic_severity || "").toLowerCase() === "warning" ? 3
                : 4;
        return rank(a) - rank(b) || a.index - b.index;
      });
  }

function pendingReviewStatus(pending, rows) {
    const payload = pending || {};
    const rowList = Array.isArray(rows) ? rows : [];
    if (payload.error) return "Diagnostics first";
    if (payload.exists === false) return "No pending root";
    const reviewRows = pendingReviewRows(payload, rowList);
    if (reviewRows.length) return `${reviewRows.length} row${reviewRows.length === 1 ? "" : "s"} need review`;
    if (!rowList.length) return "No parked rows";
    return "No flagged rows";
  }

function pendingReviewBoardLines(pending, rows) {
    const payload = pending || {};
    const rowList = Array.isArray(rows) ? rows : [];
    const reviewRows = pendingReviewRows(payload, rowList);
    const lines = [
      "Operator review board: Pending Publish",
      `Page status: ${pendingWorkflowStatus(payload, rowList)}`,
      `Rows loaded: ${payload.count || rowList.length || 0}`,
      `Flagged rows: ${reviewRows.length}`,
      `Ready / issue rows: ${payload.ready_count || 0} / ${payload.issue_count || reviewRows.length}`,
      `Backend trust states: ${pendingFormatCounts(payload.operator_trust_state_counts)}`,
      `Diagnostic severities: ${pendingFormatCounts(payload.diagnostic_severity_counts)}`,
      `Recovery classes: ${pendingFormatCounts(payload.recovery_class_counts)}`,
    ];
    lines.push("");
    if (payload.error) {
      lines.push("First action: open Diagnostics > Pending Publish, Run Logs, and Last Stderr. Do not drain while the pending view is unavailable.");
    } else if (payload.exists === false) {
      lines.push("First action: no pending-publish root exists. Check Completed before rerun; do not assume a missing output is lost from this empty view alone.");
    } else if (reviewRows.length) {
      lines.push("First rows to inspect before drain:");
      reviewRows.slice(0, 6).forEach(({ row, reasons }, index) => {
        const label = row.local_file || row.manifest_path || row.server_out || `row ${index + 1}`;
        const action = row.safe_next_action || row.operator_guidance || row.recovery_action || "build a selected-row recovery dry-run plan and inspect backend-selected targets before drain.";
        lines.push(`- ${label}: ${reasons.slice(0, 3).join("; ")}. Safe action: ${action}`);
      });
      if (reviewRows.length > 6) lines.push(`- ${reviewRows.length - 6} more flagged row(s) not shown.`);
    } else if (!rowList.length) {
      lines.push("First action: no parked outputs are waiting. If expected outputs are missing, inspect Completed and Run Logs before reprocessing.");
    } else {
      lines.push("First action: no pending rows are locally flagged. Publish Parked Outputs remains the backend-owned validation and drain path.");
    }
    lines.push("Mutation guardrail: this board is read-only; drain, repair, rewrite, move, delete, and publish actions remain backend-owned.");
    return lines;
  }

function pendingReviewDigestStatus(entry) {
    const row = entry?.row || {};
    const severity = String(row.diagnostic_severity || "").toLowerCase();
    const recommendation = String(row.drain_recommendation || "").toLowerCase();
    if (recommendation === "do_not_drain" || severity === "error" || row.local_exists === false || row.error) return "blocked";
    if (severity === "warning" || entry?.reasons?.length || row.ready_to_drain === false) return "warning";
    return "match";
  }

function pendingReviewDigestAction(row) {
    return row?.safe_next_action
      || row?.operator_guidance
      || row?.recovery_action
      || "Select this row, inspect Pending detail and Diagnostics Cross-Links, then use backend recovery dry-run before drain if anything is unclear.";
  }

function renderPendingReviewDigest(pending, rows) {
    const tbody = byId("pending-review-rows");
    if (!tbody) return;
    const payload = pending || {};
    const rowList = Array.isArray(rows) ? rows : [];
    const reviewRows = pendingReviewRows(payload, rowList).slice(0, 12);
    if (!reviewRows.length) {
      clearRows(
        tbody,
        5,
        payload.error
          ? "Pending publish scan is unavailable. Use Diagnostics > Pending Publish, Run Logs, and Last Stderr before drain."
          : payload.exists === false
            ? "No pending-publish root exists. Check Completed and Run Logs before assuming a missing output is lost."
            : rowList.length
              ? "No pending rows are flagged by the loaded backend payload. Publish Parked Outputs remains backend-owned validation."
              : "No parked outputs are waiting. Cross-check Completed before reprocessing expected outputs.",
      );
      updateTableStatusLegend("pending-review-legend", tbody, "Pending publish review rows");
      return;
    }
    tbody.replaceChildren();
    reviewRows.forEach((entry) => {
      const item = entry.row || {};
      const row = document.createElement("tr");
      const key = pendingRowKey(item);
      row.dataset.rowKey = key;
      row.dataset.status = pendingReviewDigestStatus(entry);
      const reviewPathRaw = item.local_file || item.manifest_path || item.server_out || item.source_path || "";
      const reviewPathDisplay = typeof shortenPath === "function" ? shortenPath(reviewPathRaw, 40) : reviewPathRaw;
      appendCells(row, [
        item.recovery_class || item.diagnostic_status || item.state || row.dataset.status,
        item.drain_recommendation || "review",
        reviewPathDisplay,
        entry.reasons.slice(0, 3).join("; "),
        pendingReviewDigestAction(item),
      ], [null, null, "path-cell", null, null]);
      if (reviewPathRaw) {
        const reviewCells = row.querySelectorAll("td");
        if (reviewCells[2]) reviewCells[2].title = reviewPathRaw;
      }
      makeRowSelectable(row, () => selectPendingRow(item), {
        selected: Boolean(key && key === getSelectedPendingRowKey()),
        label: `Pending publish review row ${item.local_file || item.server_out || item.manifest_path || ""}`,
      });
      tbody.appendChild(row);
    });
    updateTableStatusLegend("pending-review-legend", tbody, "Pending publish review rows");
  }

function renderPendingReviewBoard(pending, rows) {
    const rowList = Array.isArray(rows) ? rows : [];
    setText("pending-review-status", pendingReviewStatus(pending || {}, rowList));
    setText("pending-review-board", pendingReviewBoardLines(pending || {}, rowList).join("\n"));
    renderPendingReviewDigest(pending || {}, rowList);
  }

function pendingFormatCounts(value) {
    const entries = value && typeof value === "object" ? Object.entries(value) : [];
    if (!entries.length) return "none";
    return entries.map(([key, count]) => `${key || "unknown"}=${count}`).join(", ");
  }

function pendingRecoverySummaryPayload(pending) {
    const summary = pending?.recovery_summary;
    return summary && typeof summary === "object" ? summary : {};
  }

function pendingRecoverySummaryLines(pending) {
    const summary = pendingRecoverySummaryPayload(pending);
    if (!Object.keys(summary).length) {
      return [
        "Backend recovery summary:",
        "- Status: not reported",
        "- Primary action: use row diagnostics and backend validation before drain.",
      ];
    }
    const lines = [
      "Backend recovery summary:",
      `- Status: ${summary.status || "unknown"}`,
      `- Blockers/review/ready: ${summary.blocker_count || 0} / ${summary.review_count || 0} / ${summary.ready_count || 0}`,
      `- Recovery classes: ${pendingFormatCounts(summary.class_counts)}`,
      `- Primary action: ${summary.primary_action || "Review pending publish diagnostics before drain."}`,
    ];
    const steps = Array.isArray(summary.next_steps) ? summary.next_steps.filter(Boolean) : [];
    if (steps.length) {
      lines.push("- Next steps:");
      steps.slice(0, 5).forEach((step) => lines.push(`  - ${step}`));
    }
    return lines;
  }

function pendingRiskStatus(pending, rows) {
    const rowList = Array.isArray(rows) ? rows : [];
    if (pending?.error) return "Unavailable";
    if (!pending?.exists) return "No root";
    if (!rowList.length) return "Empty";
    if (Number(pending?.issue_count || 0) > 0 || Number(pending?.health_count || 0) > 0 || rowList.some(pendingRowHasHealthIssue)) return "Review";
    return "Ready";
  }

function pendingRiskLines(pending, rows) {
    const payload = pending || {};
    const rowList = Array.isArray(rows) ? rows : [];
    const issues = rowList.filter(pendingRowHasHealthIssue);
    const lines = [
      `Rows loaded: ${payload.count || rowList.length || 0}`,
      `Ready rows: ${payload.ready_count || 0}`,
      `Issue rows: ${payload.issue_count || issues.length}`,
      `States: ${pendingFormatCounts(payload.state_counts)}`,
      `Routes: ${pendingFormatCounts(payload.route_counts)}`,
      `Diagnostic statuses: ${pendingFormatCounts(payload.diagnostic_status_counts)}`,
      `Diagnostic severities: ${pendingFormatCounts(payload.diagnostic_severity_counts)}`,
      `Recovery classes: ${pendingFormatCounts(payload.recovery_class_counts)}`,
      `Suggested open targets: ${pendingFormatCounts(payload.recommended_open_target_counts)}`,
      `Available open targets: ${pendingFormatCounts(payload.available_open_target_counts)}`,
      `Orphan payloads: ${payload.orphan_payload_count || 0}`,
      `Invalid/unreadable manifests: ${payload.invalid_manifest_count || 0}`,
      `Missing payload references: ${payload.missing_local_count || 0}`,
      `Missing sidecars: ${payload.missing_sidecar_count || 0}`,
    ];
    if (issues.length) {
      lines.push("", "First issue rows:");
      issues.slice(0, 5).forEach((row) => {
        lines.push(`- ${row.local_file || row.manifest_path || row.server_out || row.row_key || "(row)"}: ${row.issue_summary || row.error || row.state || "review required"}`);
      });
    }
    lines.push("", ...pendingRecoverySummaryLines(payload));
    lines.push("", "Operator note: drain readiness is advisory. The backend Publish Parked Outputs command still performs authoritative validation.");
    return lines;
  }

function renderPendingRiskBreakdown(pending, rows) {
    const rowList = Array.isArray(rows) ? rows : [];
    setText("pending-risk-status", pendingRiskStatus(pending || {}, rowList));
    setText("pending-risk", pendingRiskLines(pending || {}, rowList).join("\n"));
  }

function pendingValidationStatus(pending, rows) {
    const payload = pending || {};
    const rowList = Array.isArray(rows) ? rows : [];
    if (payload.error) return "Unavailable";
    if (payload.exists === false) return "No root";
    if (!rowList.length) return "Empty";
    const doNotDrainRows = rowList.filter((row) => String(row?.drain_recommendation || "").toLowerCase() === "do_not_drain");
    const severeRows = rowList.filter((row) => String(row?.diagnostic_severity || "").toLowerCase() === "error");
    const invalidRows = rowList.filter((row) => ["invalid_manifest", "unreadable_manifest"].includes(String(row?.state || "").toLowerCase()));
    const missingPayloadRows = rowList.filter((row) => row?.local_exists === false);
    const missingSidecarRows = rowList.filter((row) => Number(row?.missing_sidecar_count || 0) > 0);
    if (
      doNotDrainRows.length ||
      severeRows.length ||
      invalidRows.length ||
      missingPayloadRows.length ||
      missingSidecarRows.length ||
      Number(payload.health_count || 0) > 0 ||
      Number(payload.missing_local_count || 0) > 0
    ) {
      return "Do not drain";
    }
    const warnings = Array.isArray(payload.warnings) ? payload.warnings.filter(Boolean) : [];
    if (warnings.length || Number(payload.issue_count || 0) > 0 || rowList.some(pendingRowHasHealthIssue)) return "Review";
    return "Ready";
  }

function pendingValidationChecklistLines(pending, rows) {
    const payload = pending || {};
    const rowList = Array.isArray(rows) ? rows : [];
    const warnings = Array.isArray(payload.warnings) ? payload.warnings.filter(Boolean) : [];
    const issueRows = rowList.filter(pendingRowHasHealthIssue);
    const doNotDrainRows = rowList.filter((row) => String(row?.drain_recommendation || "").toLowerCase() === "do_not_drain");
    const severeRows = rowList.filter((row) => String(row?.diagnostic_severity || "").toLowerCase() === "error");
    const invalidRows = rowList.filter((row) => ["invalid_manifest", "unreadable_manifest"].includes(String(row?.state || "").toLowerCase()));
    const missingPayloadRows = rowList.filter((row) => row?.local_exists === false);
    const missingSidecarRows = rowList.filter((row) => Number(row?.missing_sidecar_count || 0) > 0);
    const existsText = payload.exists === true ? "yes" : payload.exists === false ? "no" : "unknown";
    if (payload.error) {
      return [
        "Real-media validation checklist:",
        `Status: unavailable`,
        `Error: ${payload.error}`,
        "Operator action: open Diagnostics > Pending Publish and Run Logs before another publish attempt.",
        "Mutation guardrail: this checklist is read-only and cannot drain, repair, delete, rewrite, or publish files.",
      ];
    }
    const lines = [
      "Real-media validation checklist:",
      `Pending root: ${payload.pending_root || "not reported"}`,
      `Pending root exists: ${existsText}`,
      `Parked manifest rows: ${payload.count || rowList.length || 0}`,
      `Payload rows: ${payload.payload_count || 0}`,
      `Ready rows: ${payload.ready_count || 0}`,
      `Issue rows: ${payload.issue_count || issueRows.length}`,
      `Health rows: ${payload.health_count || 0}`,
      `Do-not-drain rows: ${doNotDrainRows.length}`,
      `Diagnostic error rows: ${severeRows.length}`,
      `Invalid/unreadable manifest rows: ${payload.invalid_manifest_count || invalidRows.length}`,
      `Missing payload references: ${payload.missing_local_count || missingPayloadRows.length}`,
      `Missing sidecar rows: ${payload.missing_sidecar_count || missingSidecarRows.length}`,
      `Orphan payloads: ${payload.orphan_payload_count || 0}`,
      `States: ${pendingFormatCounts(payload.state_counts || pendingStateCounts(rowList))}`,
      `Diagnostic statuses: ${pendingFormatCounts(payload.diagnostic_status_counts)}`,
      `Diagnostic severities: ${pendingFormatCounts(payload.diagnostic_severity_counts)}`,
      `Recovery classes: ${pendingFormatCounts(payload.recovery_class_counts)}`,
      `Suggested open targets: ${pendingFormatCounts(payload.recommended_open_target_counts)}`,
      `Available open targets: ${pendingFormatCounts(payload.available_open_target_counts)}`,
      `Last drain summary: ${pendingDrainSummaryStatus(payload)}`,
    ];
    lines.push("", ...pendingRecoverySummaryLines(payload));
    if (warnings.length) {
      lines.push("", "Warning(s):");
      warnings.slice(0, 5).forEach((warning) => lines.push(`- ${warning}`));
    }
    lines.push("");
    if (payload.exists === false) {
      lines.push("Operator action: no pending-publish folder exists yet. This is normal until Deferred Publish parks an output.");
    } else if (!rowList.length) {
      lines.push("Operator action: no parked outputs are waiting. Cross-check Completed History and Run Logs before reprocessing anything.");
    } else if (doNotDrainRows.length || severeRows.length || invalidRows.length || missingPayloadRows.length || missingSidecarRows.length) {
      lines.push("Operator action: do not drain yet. Select issue rows and use backend-selected open/diagnostic actions to inspect manifests, payloads, sidecars, and logs.");
    } else if (warnings.length || Number(payload.issue_count || 0) > 0 || issueRows.length) {
      lines.push("Operator action: review warnings and issue rows before publishing parked outputs.");
    } else {
      lines.push("Operator action: rows appear ready, but Publish Parked Outputs remains the authoritative backend validation path.");
    }
    lines.push("Mutation guardrail: this checklist is read-only and cannot drain, repair, delete, rewrite, or publish files.");
    return lines;
  }

function renderPendingValidation(pending, rows) {
    const rowList = Array.isArray(rows) ? rows : [];
    setText("pending-validation-status", pendingValidationStatus(pending || {}, rowList));
    setText("pending-validation", pendingValidationChecklistLines(pending || {}, rowList).join("\n"));
  }

    return {
      pendingInventoryProgressBars,
      renderPendingInventoryProgress,
      pendingEmptyStateMessage,
      pendingStateCounts,
      formatPendingStateCounts,
      pendingRowHasHealthIssue,
      pendingPublishReadinessStatus,
      pendingPublishReadinessLines,
      renderPendingPublishReadiness,
      pendingWorkflowStatus,
      pendingWorkflowLines,
      renderPendingWorkflow,
      pendingReviewRowReasons,
      pendingReviewRows,
      pendingReviewStatus,
      pendingReviewBoardLines,
      pendingReviewDigestStatus,
      pendingReviewDigestAction,
      renderPendingReviewDigest,
      renderPendingReviewBoard,
      pendingFormatCounts,
      pendingRecoverySummaryPayload,
      pendingRecoverySummaryLines,
      pendingRiskStatus,
      pendingRiskLines,
      renderPendingRiskBreakdown,
      pendingValidationStatus,
      pendingValidationChecklistLines,
      renderPendingValidation,
    };
  }

  window.__pendingPublishSummaryModule = {
    createPendingPublishSummaryModule,
  };
})();
