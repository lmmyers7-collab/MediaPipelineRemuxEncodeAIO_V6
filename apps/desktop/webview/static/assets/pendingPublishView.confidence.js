(function () {
  const pendingPostDrainTrustModule = window.__pendingPostDrainTrustModule || {};
  delete window.__pendingPostDrainTrustModule;
  if (typeof pendingPostDrainTrustModule.createPendingPostDrainTrustModule !== "function") {
    throw new Error("pendingPublish/confidence/postDrainTrust.js must load before pendingPublishView.confidence.js");
  }

  function createPendingPublishConfidenceModule(deps = {}) {
    const {
      appendCells = function () {},
      byId = function () { return null; },
      clearRows = function () {},
      getCommandHistory = function () { return []; },
      getCurrentPendingRecoveryPlanSignature = function () { return ""; },
      getLastPendingPayload = function () { return {}; },
      getLastPendingRecoveryPlanSignature = function () { return ""; },
      getLastPendingRecoveryPlanRows = function () { return []; },
      getLastPendingRows = function () { return []; },
      getLastPendingSnapshot = function () { return {}; },
      getSelectedPendingRow = function () { return null; },
      makeRowSelectable = function () {},
      pendingCurrentFilterScope = function () { return {}; },
      pendingCurrentFilterScopeAction = function () { return "Review visible and hidden rows before drain."; },
      pendingCurrentFilterScopeEvidence = function () { return "filter scope unavailable"; },
      pendingDrainCommandIssueLevel = function () { return "none"; },
      pendingDrainCommandResultText = function () { return "unknown"; },
      pendingDrainEventCounts = function () { return "none"; },
      pendingDrainEventLeaf = function () { return "unknown"; },
      pendingDrainEventRoute = function () { return "unknown"; },
      pendingDrainEventStatus = function () { return "unknown"; },
      pendingDrainEventsFromSnapshot = function () { return []; },
      pendingDrainHistoryLine = function (entry) { return String(entry?.message || entry?.command || "pending publish drain"); },
      pendingDrainLatestCommand = function () { return null; },
      pendingDrainSummaryIssueLevel = function () { return "none"; },
      pendingDrainSummaryItems = function () { return []; },
      pendingDrainSummaryLeaf = function () { return "unknown"; },
      pendingDrainSummaryPayload = function () { return {}; },
      pendingDrainSummaryStatus = function () { return "Not loaded"; },
      pendingEvidenceClass = function () { return "review"; },
      pendingEvidenceRows = function () { return []; },
      pendingEvidenceStatus = function () { return "Not loaded"; },
      pendingEvidenceText = function () { return "No explicit evidence fields reported."; },
      pendingFormatCounts = function () { return "none"; },
      pendingRecoveryPlanRowStatus = function () { return "warning"; },
      pendingRowHasHealthIssue = function () { return false; },
      pendingRowKey = function (row) { return row?.row_key || ""; },
      pendingSampleValidationHandoffLines = function () { return []; },
      pendingValidationStatus = function () { return "Review"; },
      renderPendingDetail = function () {},
      renderPendingDrainEvidence = function () {},
      renderPendingReviewDigest = function () {},
      renderPendingRows = function () {},
      setSelectedPendingRowKey = function () {},
      setText = function () {},
      state = {},
      updateTableStatusLegend = function () {},
    } = deps;
    const PENDING_READ_ONLY_BOUNDARY = "Mutation guardrail: read-only evidence; backend routes own pending-publish changes.";

    function getSelectedPendingPostDrainTrustKey() {
      return state.selectedPendingPostDrainTrustKey || "";
    }

    function setSelectedPendingPostDrainTrustKey(value) {
      state.selectedPendingPostDrainTrustKey = value || "";
    }

    function getSelectedPendingDrainDecisionKey() {
      return state.selectedPendingDrainDecisionKey || "";
    }

    function setSelectedPendingDrainDecisionKey(value) {
      state.selectedPendingDrainDecisionKey = value || "";
    }

    function capturePendingConfidenceSelectionScroll() {
      return window.mediaPipelineDom?.captureScrollablePositions?.() || null;
    }

    function restorePendingConfidenceSelectionScroll(snapshot) {
      if (snapshot) window.mediaPipelineDom?.restoreScrollablePositions?.(snapshot);
    }

  function pendingDrainConfidenceRank(confidence) {
    const normalized = String(confidence || "").toLowerCase();
    if (normalized === "blocked") return 0;
    if (normalized === "review") return 1;
    if (normalized === "unknown") return 2;
    if (normalized === "ready") return 3;
    return 4;
  }

  function pendingOptionalNumber(value) {
    if (value === null || value === undefined) return null;
    if (typeof value === "string" && !value.trim()) return null;
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }

  function pendingCurrentRowCount(payload, rowList) {
    const reported = pendingOptionalNumber(payload?.count);
    return reported === null ? (Array.isArray(rowList) ? rowList.length : 0) : Math.max(0, Math.round(reported));
  }

  function pendingDrainSummaryStartCount(summary) {
    const count = pendingOptionalNumber(summary?.manifest_count_at_start);
    return count === null ? null : Math.max(0, Math.round(count));
  }

  function pendingDrainSummaryMatchesCurrentRows(summary, currentRowCount) {
    const startCount = pendingDrainSummaryStartCount(summary);
    if (startCount === null || currentRowCount === null || currentRowCount === undefined) return true;
    return startCount === currentRowCount;
  }

  function pendingDrainSummaryScopedIssueLevel(summary, currentRowCount) {
    const level = pendingDrainSummaryIssueLevel(summary);
    if (level !== "blocked" || summary?.read_error) return level;
    return pendingDrainSummaryMatchesCurrentRows(summary, currentRowCount) ? level : "review";
  }

  function pendingRecoveryRowsForCurrentEvidence(pending, rows) {
    const rawRows = Array.isArray(getLastPendingRecoveryPlanRows()) ? getLastPendingRecoveryPlanRows() : [];
    if (!rawRows.length) {
      return { rows: [], rawRows, stale: false, planSignature: "", currentSignature: "" };
    }
    const planSignature = String(getLastPendingRecoveryPlanSignature() || "");
    const currentSignature = String(getCurrentPendingRecoveryPlanSignature(pending, rows) || "");
    const stale = !planSignature || !currentSignature || planSignature !== currentSignature;
    return {
      rows: stale ? [] : rawRows,
      rawRows,
      stale,
      planSignature,
      currentSignature,
    };
  }

  function pendingDrainConfidenceBackendRows(pending) {
    const dto = pending?.drain_confidence;
    if (!dto || typeof dto !== "object" || dto.schema_version !== "desktop_pending_drain_confidence.v1") return [];
    return Array.isArray(dto.rows) ? dto.rows.filter((row) => row && typeof row === "object") : [];
  }

  function pendingDrainConfidenceBackendRowMap(pending) {
    const rows = pendingDrainConfidenceBackendRows(pending);
    const byCheck = new Map();
    rows.forEach((row) => {
      const check = String(row.check || "").trim();
      if (check && !byCheck.has(check)) byCheck.set(check, row);
    });
    return byCheck;
  }

  function pendingDrainConfidenceRows(pending, rows, snapshot, entries) {
    const payload = pending || {};
    const inputRows = Array.isArray(rows) ? rows : [];
    const loadedRows = typeof getLastPendingRows === "function" ? getLastPendingRows() : [];
    const payloadRows = Array.isArray(payload.rows) ? payload.rows : [];
    const rowLists = [inputRows, Array.isArray(loadedRows) ? loadedRows : [], payloadRows];
    const rowList = rowLists.reduce((largest, candidate) => candidate.length > largest.length ? candidate : largest, []);
    const entryList = Array.isArray(entries) ? entries : [];
    const summary = pendingDrainSummaryPayload(payload);
    const currentRowCount = pendingCurrentRowCount(payload, rowList);
    const summaryStartCount = pendingDrainSummaryStartCount(summary);
    const summaryMatchesCurrent = pendingDrainSummaryMatchesCurrentRows(summary, currentRowCount);
    const summaryLevel = pendingDrainSummaryScopedIssueLevel(summary, currentRowCount);
    const latest = pendingDrainLatestCommand(entryList);
    const events = pendingDrainEventsFromSnapshot(snapshot || {});
    const evidenceRows = pendingEvidenceRows(rowList);
    const blockingEvidence = evidenceRows.filter((entry) => ["do-not-drain", "diagnostic-error", "missing-payload", "manifest-invalid"].includes(entry.evidenceClass));
    const reviewEvidence = evidenceRows.filter((entry) => !["do-not-drain", "diagnostic-error", "missing-payload", "manifest-invalid"].includes(entry.evidenceClass));
    const selectedRow = getSelectedPendingRow();
    const recoveryState = pendingRecoveryRowsForCurrentEvidence(payload, rowList);
    const recoveryRows = recoveryState.rows;
    const recoveryBlocked = recoveryRows.filter((row) => pendingRecoveryPlanRowStatus(row) === "blocked").length;
    const recoveryReview = recoveryRows.filter((row) => pendingRecoveryPlanRowStatus(row) === "warning").length;
    const filterScope = pendingCurrentFilterScope(rowList);
    const backendRows = pendingDrainConfidenceBackendRowMap(payload);
    const rowsOut = [];
    const add = (check, confidence, evidence, action) => {
      const backendRow = backendRows.get(check);
      rowsOut.push(backendRow ? {
        check,
        confidence: backendRow.confidence || confidence,
        evidence: backendRow.evidence || evidence,
        action: backendRow.action || action,
        evidenceAuthority: backendRow.evidence_authority || payload.drain_confidence?.evidence_authority || "backend",
      } : { check, confidence, evidence, action });
    };
    if (payload.error) {
      add("Pending scan", "blocked", `scan unavailable: ${payload.error}`, "Open Diagnostics > Pending Publish, Run Logs, and Last Stderr before any drain attempt.");
      return rowsOut;
    }
    add(
      "Current parked rows",
      payload.exists === false ? "unknown" : !rowList.length ? "ready" : blockingEvidence.length ? "blocked" : reviewEvidence.length ? "review" : "ready",
      `root=${payload.exists === false ? "missing" : "available"}; rows=${payload.count || rowList.length || 0}; ready=${payload.ready_count || 0}; issues=${payload.issue_count || 0}`,
      payload.exists === false
        ? "No pending root exists. Confirm Completed and Run Logs before rerun."
        : !rowList.length
          ? "No parked outputs are waiting. Do not reprocess solely because Pending Publish is empty."
        : "Review row-level evidence below before pressing Drain Parked Outputs.",
    );
    add(
      "Display filter / drain scope",
      filterScope.hiddenBlockedCount ? "blocked" : filterScope.hiddenReviewCount || filterScope.hiddenCount ? "review" : "ready",
      pendingCurrentFilterScopeEvidence(filterScope),
      pendingCurrentFilterScopeAction(filterScope),
    );
    add(
      "Blocker evidence",
      blockingEvidence.length ? "blocked" : reviewEvidence.length ? "review" : "ready",
      `blocking=${blockingEvidence.length}; review=${reviewEvidence.length}; evidence status=${pendingEvidenceStatus(payload, rowList)}`,
      blockingEvidence.length
        ? "Do not drain. Select the highest-risk evidence row and inspect backend-selected targets or build a recovery dry-run plan."
        : reviewEvidence.length
          ? "Review warning/orphan/sidecar rows before drain."
          : "No loaded row exposes drain-blocking evidence.",
    );
    add(
      "Validation checklist",
      pendingValidationStatus(payload, rowList) === "Do not drain" ? "blocked" : pendingValidationStatus(payload, rowList) === "Review" ? "review" : "ready",
      `validation=${pendingValidationStatus(payload, rowList)}; health=${payload.health_count || 0}; missing payloads=${payload.missing_local_count || 0}; missing sidecars=${payload.missing_sidecar_count || 0}`,
      "Use the Real-media Validation Checklist as the page-level pre-drain gate; backend drain validation remains authoritative.",
    );
    add(
      "Recovery dry-run plan",
      recoveryBlocked ? "blocked" : recoveryReview ? "review" : recoveryRows.length ? "ready" : (blockingEvidence.length || reviewEvidence.length ? "review" : "unknown"),
      recoveryState.stale ? `stale recovery dry-run ignored; planned rows=${recoveryState.rawRows.length}` : recoveryRows.length ? `planned rows=${recoveryRows.length}; blocked=${recoveryBlocked}; review=${recoveryReview}` : "no recovery plan loaded",
      recoveryState.stale
        ? "Build a fresh selected-row or all-rows dry-run against the current Pending Publish evidence before using recovery rows as blockers."
        : recoveryRows.length
        ? "Use the recovery-plan row drilldown for any blocked or review planned action before drain."
        : "Build a selected-row or all-rows dry-run plan before risky drains.",
    );
    add(
      "Last drain command",
      pendingDrainCommandIssueLevel(latest) === "blocked" ? "blocked" : pendingDrainCommandIssueLevel(latest) === "review" ? "review" : latest ? "ready" : "unknown",
      latest ? `${latest.command || "drain"} [${pendingDrainCommandResultText(latest)}] ${latest.message || ""}` : "no drain command in loaded history",
      latest
        ? "Compare command result with durable summary and current rows before another drain."
        : "No previous drain command is loaded; this is normal before first publish.",
    );
    add(
      "Durable drain summary",
      summaryLevel === "blocked" ? "blocked" : summaryLevel === "review" ? "review" : summaryLevel === "ok" ? "ready" : "unknown",
      `status=${pendingDrainSummaryStatus(payload)}; summary rows=${summaryStartCount ?? "unknown"}; current rows=${currentRowCount}; attempted=${summary.attempted_count || 0}; errors=${summary.error_count || 0}; remaining=${summary.remaining_count || 0}`,
      summaryMatchesCurrent
        ? "Treat the durable summary as last-attempt evidence; the current pending rows remain the source of truth for what is still parked."
        : "The last drain summary covers a different parked-row count; review it as stale evidence while relying on current rows and backend validation.",
    );
    add(
      "Recent backend drain events",
      !Array.isArray(snapshot?.recent_events) ? "unknown" : events.some((event) => !["succeeded", "already_published"].includes(pendingDrainEventStatus(event).toLowerCase())) ? "review" : events.length ? "ready" : "unknown",
      Array.isArray(snapshot?.recent_events) ? `events=${events.length}${events.length ? `; statuses=${pendingDrainEventCounts(events, pendingDrainEventStatus)}` : ""}` : "snapshot events unavailable",
      "Recent events are bounded context only; use them to investigate mismatches between command result, durable summary, and current pending rows.",
    );
    add(
      "Selected row",
      !selectedRow ? "unknown" : ["do-not-drain", "diagnostic-error", "missing-payload", "manifest-invalid"].includes(pendingEvidenceClass(selectedRow)) ? "blocked" : pendingEvidenceClass(selectedRow) === "ready-evidence" ? "ready" : "review",
      selectedRow ? `${pendingEvidenceClass(selectedRow)}; ${pendingEvidenceText(selectedRow)}` : "no selected pending row",
      selectedRow
        ? "Use selected-row diagnostics and backend-selected open targets for row-specific proof."
        : "Select a pending row when reviewing a suspicious drain decision.",
    );
    return rowsOut.sort((left, right) => pendingDrainConfidenceRank(left.confidence) - pendingDrainConfidenceRank(right.confidence));
  }

  function pendingDrainConfidenceStatus(pending, rows, snapshot, entries) {
    const confidenceRows = pendingDrainConfidenceRows(pending, rows, snapshot, entries);
    if (confidenceRows.some((row) => row.confidence === "blocked")) return "Do not drain";
    if (confidenceRows.some((row) => row.confidence === "review")) return "Review first";
    if (confidenceRows.some((row) => row.confidence === "unknown")) return "Evidence incomplete";
    return confidenceRows.length ? "Ready-looking" : "Not evaluated";
  }

  function pendingDrainConfidenceSummaryLines(pending, rows, snapshot, entries) {
    const confidenceRows = pendingDrainConfidenceRows(pending, rows, snapshot, entries);
    const payload = pending || {};
    const inputRows = Array.isArray(rows) ? rows : [];
    const loadedRows = typeof getLastPendingRows === "function" ? getLastPendingRows() : [];
    const payloadRows = Array.isArray(payload.rows) ? payload.rows : [];
    const scopeRows = [inputRows, Array.isArray(loadedRows) ? loadedRows : [], payloadRows].reduce(
      (largest, candidate) => candidate.length > largest.length ? candidate : largest,
      [],
    );
    const filterScope = pendingCurrentFilterScope(scopeRows);
    const reportedRowCount = Number(payload.count || 0);
    const reportedIssueCount = Number(payload.issue_count || payload.health_count || 0);
    const filterScopeAction = (
      filterScope.active
      && !Number(filterScope.hiddenCount || 0)
      && reportedRowCount > Number(filterScope.totalCount || 0)
      && reportedIssueCount > 0
    )
      ? "Review hidden warning rows or clear filters before drain; display filters do not narrow backend drain scope."
      : pendingCurrentFilterScopeAction(filterScope);
    const counts = confidenceRows.reduce((acc, row) => {
      const key = row.confidence || "unknown";
      acc[key] = (acc[key] || 0) + 1;
      return acc;
    }, {});
    const lines = [
      "Pending Publish drain action confidence:",
      `Rows: ${confidenceRows.length}; ready=${counts.ready || 0}; review=${counts.review || 0}; blocked=${counts.blocked || 0}; unknown=${counts.unknown || 0}.`,
      "This is the final read-only operator handoff before Drain Parked Outputs.",
      "Backend Drain Parked Outputs remains the only authority that can validate and move parked files.",
    ];
    if (filterScope.active) {
      lines.push(`Display filter / drain scope: ${filterScopeAction}`);
    }
    const blockedRows = confidenceRows.filter((row) => row.confidence === "blocked");
    const reviewRows = confidenceRows.filter((row) => row.confidence === "review");
    const unknownRows = confidenceRows.filter((row) => row.confidence === "unknown");
    if (blockedRows.length) {
      lines.push("", "Do not drain until resolved:");
      blockedRows.slice(0, 6).forEach((row) => lines.push(`- ${row.check}: ${row.action}`));
    } else if (reviewRows.length) {
      lines.push("", "Review before drain:");
      reviewRows.slice(0, 6).forEach((row) => lines.push(`- ${row.check}: ${row.action}`));
    } else if (unknownRows.length) {
      lines.push("", "Evidence incomplete:");
      unknownRows.slice(0, 6).forEach((row) => lines.push(`- ${row.check}: ${row.action}`));
    } else {
      lines.push("", "No local drain blockers detected in the loaded Pending Publish data.");
    }
    lines.push(PENDING_READ_ONLY_BOUNDARY);
    return lines;
  }

  function renderPendingDrainActionConfidence(pending, rows, snapshot, entries) {
    const payload = pending || {};
    const rowList = Array.isArray(rows) ? rows : [];
    const snapshotPayload = snapshot || {};
    const entryList = Array.isArray(entries) ? entries : [];
    const confidenceRows = pendingDrainConfidenceRows(payload, rowList, snapshotPayload, entryList);
    setText("pending-drain-confidence-status", pendingDrainConfidenceStatus(payload, rowList, snapshotPayload, entryList));
    setText("pending-drain-confidence-summary", pendingDrainConfidenceSummaryLines(payload, rowList, snapshotPayload, entryList).join("\n"));
    setText("pending-drain-confidence-legend", "Drain confidence rows are read-only evidence; backend routes own pending-publish changes.");
    const tbody = byId("pending-drain-confidence-rows");
    if (!tbody) return;
    if (!confidenceRows.length) {
      clearRows(tbody, 4, "No pending publish drain confidence rows loaded.");
      return;
    }
    tbody.replaceChildren();
    confidenceRows.forEach((item) => {
      const row = document.createElement("tr");
      row.dataset.status = item.confidence === "blocked" ? "blocked" : item.confidence === "review" || item.confidence === "unknown" ? "warning" : "match";
      appendCells(row, [item.check, item.confidence, item.evidence, item.action]);
      tbody.appendChild(row);
    });
  }

  function pendingDrainDecisionPostureStatus(posture) {
    const normalized = String(posture || "").toLowerCase();
    if (normalized.includes("blocked") || normalized.includes("do not")) return "blocked";
    if (normalized.includes("review")) return "warning";
    if (normalized.includes("read-first") || normalized.includes("evidence incomplete")) return "changed";
    if (normalized.includes("unknown") || normalized.includes("select")) return "unknown";
    return "match";
  }

  function pendingDrainDecisionCompletedProofRows(pending) {
    const completedView = window.mediaPipelineCompletedView || {};
    if (
      typeof completedView.completedPendingProofRows === "function"
      && typeof completedView.getLastCompletedPayload === "function"
      && typeof completedView.getLastCompletedRows === "function"
    ) {
      return completedView.completedPendingProofRows(completedView.getLastCompletedPayload(), completedView.getLastCompletedRows(), pending || {});
    }
    return [];
  }

  function pendingDrainDecisionRows(pending, rows, snapshot, entries) {
    const payload = pending || {};
    const rowList = Array.isArray(rows) ? rows : [];
    const entryList = Array.isArray(entries) ? entries : [];
    const confidenceRows = pendingDrainConfidenceRows(payload, rowList, snapshot || {}, entryList);
    const blockedConfidence = confidenceRows.filter((row) => row.confidence === "blocked");
    const reviewConfidence = confidenceRows.filter((row) => row.confidence === "review");
    const unknownConfidence = confidenceRows.filter((row) => row.confidence === "unknown");
    const summary = pendingDrainSummaryPayload(payload);
    const currentRowCount = pendingCurrentRowCount(payload, rowList);
    const summaryStartCount = pendingDrainSummaryStartCount(summary);
    const summaryLevel = pendingDrainSummaryScopedIssueLevel(summary, currentRowCount);
    const latest = pendingDrainLatestCommand(entryList);
    const events = pendingDrainEventsFromSnapshot(snapshot || {});
    const recoveryState = pendingRecoveryRowsForCurrentEvidence(payload, rowList);
    const recoveryRows = recoveryState.rows;
    const recoveryBlocked = recoveryRows.filter((row) => pendingRecoveryPlanRowStatus(row) === "blocked").length;
    const recoveryReview = recoveryRows.filter((row) => pendingRecoveryPlanRowStatus(row) === "warning").length;
    const completedProofRows = pendingDrainDecisionCompletedProofRows(payload);
    const completedProofBlocked = completedProofRows.filter((row) => row.status === "blocked").length;
    const completedProofExact = completedProofRows.filter((row) => row.signal === "pending-destination-overlap" || row.signal === "completed-source-still-pending" || row.signal === "drain-summary-output-proof" || row.signal === "drain-summary-source-proof" || row.signal === "completed-missing-output-still-pending" || row.signal === "completed-missing-output-with-drain-proof").length;
    const completedProofLeaf = completedProofRows.filter((row) => row.signal === "same-leaf-review").length;
    const selectedRow = getSelectedPendingRow();
    const filterScope = pendingCurrentFilterScope(rowList);
    const rowsOut = [];
    const add = (key, checkpoint, posture, evidence, action, detail = [], row = null) => {
      rowsOut.push({ key, checkpoint, posture, evidence, action, detail, row });
    };

    if (payload.error) {
      add(
        "pending-scan",
        "Pending scan",
        "Blocked review",
        `Pending publish scan unavailable: ${payload.error}`,
        "Open Diagnostics > Pending Publish, Run Logs, and Last Stderr before any publish attempt.",
        [
          "Pending Publish drain decision checklist:",
          "A readable pending scan is required before Drain Parked Outputs is trustworthy.",
        ],
      );
      return rowsOut;
    }

    add(
      "backend-authority",
      "Backend movement authority",
      "Read-only",
      "Drain Parked Outputs remains the only authority that can validate and move parked files.",
      "Use this checklist only to decide whether evidence is coherent enough to press the backend-owned button.",
      [
        "This panel never drains, repairs, rewrites, moves, deletes, publishes, opens arbitrary paths, or bypasses backend validation.",
        "Frontend-only confidence is not a publish operation.",
      ],
    );
    add(
      "current-parked-rows",
      "Current parked rows",
      blockedConfidence.length ? "Blocked review" : reviewConfidence.length ? "Review" : unknownConfidence.length ? "Evidence incomplete" : "Ready-looking",
      `rows=${payload.count || rowList.length || 0}; ready=${payload.ready_count || 0}; issues=${payload.issue_count || 0}; confidence blocked/review/unknown=${blockedConfidence.length}/${reviewConfidence.length}/${unknownConfidence.length}`,
      blockedConfidence.length
        ? "Do not drain until blocked confidence rows are explained."
        : reviewConfidence.length || unknownConfidence.length
          ? "Review confidence rows, selected row detail, and diagnostics before publishing."
          : "No loaded row exposes a local drain blocker; backend validation still decides.",
      confidenceRows.slice(0, 8).map((row) => `${row.check}: ${row.confidence} - ${row.action}`),
      selectedRow,
    );
    add(
      "display-filter-drain-scope",
      "Display filter / backend drain scope",
      filterScope.hiddenBlockedCount ? "Blocked review" : filterScope.hiddenReviewCount || filterScope.hiddenCount ? "Review" : "Read-only",
      pendingCurrentFilterScopeEvidence(filterScope),
      pendingCurrentFilterScopeAction(filterScope),
      [
        "Pending Publish display filters are local UI only.",
        "Drain Parked Outputs does not drain only the visible table subset.",
        "Backend validation sees current parked payloads/manifests, not the filtered WebView table.",
      ],
      selectedRow,
    );
    add(
      "recovery-plan",
      "Recovery dry-run",
      recoveryBlocked ? "Blocked review" : recoveryReview ? "Review" : recoveryRows.length ? "Ready-looking" : rowList.length ? "Read-first" : "Read-only",
      recoveryState.stale ? `stale recovery dry-run ignored; planned rows=${recoveryState.rawRows.length}` : recoveryRows.length ? `planned rows=${recoveryRows.length}; blocked=${recoveryBlocked}; review=${recoveryReview}` : "no recovery dry-run plan loaded",
      recoveryState.stale
        ? "Build a fresh selected-row or all-rows recovery dry-run against the current Pending Publish evidence before relying on recovery-plan blockers."
        : recoveryRows.length
        ? "Use recovery-plan row drilldown for blocked/review planned actions before drain."
        : rowList.length
          ? "Build a selected-row or all-rows recovery dry-run before risky drains."
          : "No parked rows loaded; recovery dry-run is optional.",
      [
        "Recovery plan is dry-run only.",
        "It should explain what the backend would do without moving, deleting, repairing, or publishing files.",
        recoveryState.stale ? "Stale recovery dry-run rows are ignored by the drain guard until rebuilt for the current pending evidence." : "",
      ].filter(Boolean),
      selectedRow,
    );
    add(
      "drain-command-summary-events",
      "Command, summary, and event agreement",
      pendingDrainCommandIssueLevel(latest) === "blocked" || summaryLevel === "blocked"
        ? "Blocked review"
        : pendingDrainCommandIssueLevel(latest) === "review" || summaryLevel === "review"
          ? "Review"
          : latest || summaryLevel === "ok" || events.length
            ? "Read-first"
            : "Read-only",
      `latest=${latest ? `${latest.command || "drain"} [${pendingDrainCommandResultText(latest)}]` : "none"}; summary=${pendingDrainSummaryStatus(payload)}; summary rows=${summaryStartCount ?? "unknown"}; current rows=${currentRowCount}; events=${events.length}`,
      "Compare latest drain command, durable drain summary, recent drain events, and current parked rows before another drain.",
      [
        `Latest command: ${latest ? pendingDrainHistoryLine(latest) : "none loaded"}`,
        `Summary rows/current rows: ${summaryStartCount ?? "unknown"} / ${currentRowCount}`,
        `Summary attempted/succeeded/errors/remaining: ${summary.attempted_count || 0}/${summary.succeeded_count || 0}/${summary.error_count || 0}/${summary.remaining_count || 0}`,
        `Recent events: ${events.length}${events.length ? ` (${pendingDrainEventCounts(events, pendingDrainEventStatus)})` : ""}`,
      ],
    );
    add(
      "completed-output-proof",
      "Completed/output proof",
      completedProofBlocked ? "Blocked review" : completedProofExact || completedProofLeaf ? "Review" : "Read-first",
      `Completed/Pending proof rows=${completedProofRows.length}; blocked=${completedProofBlocked}; exact=${completedProofExact}; same-leaf=${completedProofLeaf}`,
      completedProofBlocked
        ? "Resolve blocked Completed/Pending proof before rerun, cleanup, delete, or another drain."
        : completedProofExact
          ? "Review exact Completed/Pending overlap as parked, stale, or recently drained output evidence."
          : "If an expected output is missing, empty Pending Publish alone is not proof that publish succeeded.",
      [
        "Proof order: Completed row -> exact output/source path -> pending row/state -> durable drain summary -> Run Logs.",
        "Same-leaf matches are duplicate-title hints only.",
      ],
      selectedRow,
    );
    add(
      "diagnostics-order",
      "Diagnostics read order",
      blockedConfidence.length || reviewConfidence.length || recoveryBlocked || recoveryReview || completedProofBlocked ? "Read-first" : "Read-only",
      "Read first: Pending Publish state, Last Stderr, Run Logs, Last Drain Summary, Completed Manifest.",
      "Use backend allowlisted diagnostics targets before pressing Drain Parked Outputs when any row is blocked, review, or unknown.",
      [
        "Open-next order: selected row manifest/payload/destination only through backend-selected targets.",
        "Do not paste arbitrary paths into the frontend.",
      ],
      selectedRow,
    );
    add(
      "decision-boundary",
      "Decision boundary",
      "Read-only",
      "This checklist is an operator handoff, not a publish action.",
      "Press Drain Parked Outputs only when the evidence is coherent enough for backend validation to run.",
      [
        PENDING_READ_ONLY_BOUNDARY,
      ],
    );
    return rowsOut;
  }

  function pendingDrainDecisionStatus(pending, rows, snapshot, entries) {
    const decisionRows = pendingDrainDecisionRows(pending, rows, snapshot, entries);
    if (decisionRows.some((row) => pendingDrainDecisionPostureStatus(row.posture) === "blocked")) return "Do not drain";
    if (decisionRows.some((row) => pendingDrainDecisionPostureStatus(row.posture) === "warning")) return "Review first";
    if (decisionRows.some((row) => pendingDrainDecisionPostureStatus(row.posture) === "changed")) return "Read evidence";
    if (decisionRows.some((row) => pendingDrainDecisionPostureStatus(row.posture) === "unknown")) return "Evidence incomplete";
    return decisionRows.length ? "Ready-looking" : "Not evaluated";
  }

  function pendingDrainDecisionStatusState(status) {
    const normalized = String(status || "").trim().toLowerCase();
    if (normalized === "do not drain") return "blocked";
    if (normalized === "review first") return "warning";
    if (normalized === "read evidence") return "changed";
    if (normalized === "evidence incomplete" || normalized === "not evaluated") return "unknown";
    if (normalized === "ready-looking") return "ready";
    return "unknown";
  }

  function pendingDrainDecisionSummaryLines(pending, rows, snapshot, entries) {
    const decisionRows = pendingDrainDecisionRows(pending, rows, snapshot, entries);
    const blocked = decisionRows.filter((row) => pendingDrainDecisionPostureStatus(row.posture) === "blocked").length;
    const review = decisionRows.filter((row) => pendingDrainDecisionPostureStatus(row.posture) === "warning").length;
    const readFirst = decisionRows.filter((row) => pendingDrainDecisionPostureStatus(row.posture) === "changed").length;
    const unknown = decisionRows.filter((row) => pendingDrainDecisionPostureStatus(row.posture) === "unknown").length;
    const outcome = blocked ? "Do not drain" : review ? "Review first" : readFirst ? "Read evidence" : unknown ? "Evidence incomplete" : decisionRows.length ? "Ready-looking" : "Not evaluated";
    const lines = [
      "Pending Publish drain decision checklist:",
      `Daily-use handoff: Pending Publish evidence decides whether it is sensible to press Drain Parked Outputs; only the backend drain can move files. Operator outcome: ${outcome}.`,
      `Checkpoints loaded: ${decisionRows.length}`,
      `Blocked/review/read-first/unknown: ${blocked}/${review}/${readFirst}/${unknown}`,
      "Decision rule: drain only after current parked rows, recovery dry-run, latest drain evidence, Completed/output proof, and diagnostics order agree.",
      "Scope boundary: Pending filters, selected rows, recovery dry-runs, and rendered row caps never narrow backend drain scope or publish files.",
    ];
    if (blocked) {
      lines.push("First action: do not press Drain Parked Outputs until blocked evidence is explained.");
    } else if (review || readFirst || unknown) {
      lines.push("First action: select review/read-first checkpoints, then use backend allowlisted diagnostics before publishing.");
    } else {
      lines.push("First action: no local blocker is visible, but backend Drain Parked Outputs still performs the authoritative validation and movement.");
    }
    lines.push(PENDING_READ_ONLY_BOUNDARY);
    return lines;
  }

  function pendingDrainGuardState(pending = getLastPendingPayload(), rows = getLastPendingRows(), snapshot = getLastPendingSnapshot(), entries) {
    const payload = pending || {};
    const rowList = Array.isArray(rows) ? rows : [];
    const snapshotPayload = snapshot || {};
    const entryList = Array.isArray(entries) ? entries : typeof getCommandHistory === "function" ? getCommandHistory() : [];
    const decision = pendingDrainDecisionStatus(payload, rowList, snapshotPayload, entryList);
    const normalized = String(decision || "").trim().toLowerCase();
    const blocked = normalized === "do not drain" || normalized === "evidence incomplete" || normalized === "not evaluated";
    const review = normalized === "review first" || normalized === "read evidence";
    const rowCount = payload.count || rowList.length || 0;
    const issueCount = payload.issue_count || 0;
    const missingPayloads = payload.missing_local_count || 0;
    const summaryStatus = pendingDrainSummaryStatus(payload);
    const latest = pendingDrainLatestCommand(entryList);
    const filterScope = pendingCurrentFilterScope(rowList);
    const message = blocked
      ? `WebView evidence advises against draining: ${decision}. The backend will make the authoritative decision.`
      : review
        ? `Drain Parked Outputs requires operator review: ${decision}.`
        : "Drain Parked Outputs can be submitted to backend validation.";
    return {
      allowed: true,
      advisory_blocked: blocked,
      review_required: blocked || review,
      decision_status: decision,
      message,
      confirm_message: [
        `${message}`,
        "",
        `Pending rows: ${rowCount}; issue rows: ${issueCount}; missing payload references: ${missingPayloads}.`,
        `Pending table filter: ${filterScope.active ? "active" : "inactive"}; visible ${filterScope.visibleCount}/${filterScope.totalCount}; hidden blocked/review ${filterScope.hiddenBlockedCount}/${filterScope.hiddenReviewCount}.`,
        `Durable drain summary: ${summaryStatus}.`,
        `Latest drain command: ${latest ? `${latest.command || "pending_publish.drain"} [${pendingDrainCommandResultText(latest)}] ${latest.message || ""}`.trim() : "none loaded"}.`,
        "",
        "The backend will still perform authoritative validation before moving files. Continue?",
      ].join("\n"),
      filter_scope: filterScope,
    };
  }

  function pendingDrainGuardLines(state) {
    const guard = state || pendingDrainGuardState();
    const lines = [
      "Pending Publish button guard:",
      `Decision: ${guard.decision_status || "unknown"}`,
      `Button action: ${guard.review_required ? "submit after explicit review confirmation" : "submit to backend validation"}`,
      guard.message || "",
    ].filter(Boolean);
    lines.push("The click uses /api/pipeline/start with mode=drain_pending_pushes; only backend validation can allow or refuse drain work.");
    if (guard.advisory_blocked) {
      lines.push("Advisory first action: review blocked checklist rows and recovery evidence before submitting; this WebView evidence does not decide eligibility.");
    }
    if (guard.filter_scope) {
      lines.push(`Pending table filter: ${guard.filter_scope.active ? "active" : "inactive"}; visible ${guard.filter_scope.visibleCount}/${guard.filter_scope.totalCount}; hidden blocked/review ${guard.filter_scope.hiddenBlockedCount}/${guard.filter_scope.hiddenReviewCount}.`);
      lines.push("Backend drain scope remains all loaded parked rows; local filters do not narrow publish scope.");
    }
    lines.push(PENDING_READ_ONLY_BOUNDARY);
    return lines;
  }

  function renderDiagnosticCallout(id, detailLines) {
    const root = byId(id);
    if (!root) return;
    root.classList.add("diagnostic-callout");
    root.textContent = "";

    const details = document.createElement("details");
    details.className = "diagnostic-callout-details";
    const summary = document.createElement("summary");
    summary.textContent = "Why?";
    details.appendChild(summary);
    const detailsBody = document.createElement("pre");
    detailsBody.className = "prose-block diagnostic-callout-body";
    detailsBody.textContent = (detailLines || []).filter(Boolean).join("\n");
    details.appendChild(detailsBody);
    root.appendChild(details);

    const advancedBody = document.createElement("pre");
    advancedBody.className = "prose-block diagnostic-callout-body diagnostic-callout-advanced";
    advancedBody.setAttribute("data-advanced", "");
    advancedBody.hidden = !document.body.classList.contains("advanced-mode");
    advancedBody.style.display = document.body.classList.contains("advanced-mode") ? "" : "none";
    advancedBody.textContent = (detailLines || []).filter(Boolean).join("\n");
    root.appendChild(advancedBody);
  }

  function renderPendingDrainGuard(pending = getLastPendingPayload(), rows = getLastPendingRows(), snapshot = getLastPendingSnapshot(), entries) {
    const state = pendingDrainGuardState(pending, rows, snapshot, entries);
    setText("pending-drain-guard-status", state.review_required ? "Review confirm" : "Backend check");
    const statusNode = byId("pending-drain-guard-status");
    if (statusNode) statusNode.dataset.state = state.review_required ? "warning" : "ready";
    renderDiagnosticCallout("pending-drain-guard-summary", pendingDrainGuardLines(state));
    const button = byId("pending-drain-button");
    if (button) {
      button.disabled = false;
      button.setAttribute("aria-disabled", "false");
      button.title = state.confirm_message;
      button.dataset.guardState = state.review_required ? "review" : "backend-check";
    }
    const actionButton = byId("pending-action-drain-button");
    if (actionButton) {
      actionButton.disabled = false;
      actionButton.setAttribute("aria-disabled", "false");
      actionButton.textContent = state.review_required ? "Submit Drain After Review" : "Drain Parked Outputs";
      actionButton.title = state.confirm_message;
      actionButton.dataset.state = state.review_required ? "warning" : "ok";
    }
    return state;
  }

  function pendingDrainDecisionDetailLines(item) {
    if (!item) {
      return [
        "Pending Publish drain decision checklist:",
        "Select a checkpoint before publishing parked outputs.",
        PENDING_READ_ONLY_BOUNDARY,
      ];
    }
    const lines = [
      "Pending Publish drain decision checklist:",
      `Checkpoint: ${item.checkpoint || "unknown"}`,
      `Posture: ${item.posture || "read-only"}`,
      `Evidence: ${item.evidence || ""}`,
      `Safe next step: ${item.action || ""}`,
    ];
    (Array.isArray(item.detail) ? item.detail : []).forEach((line) => lines.push(line));
    if (item.row) {
      lines.push("");
      lines.push("Associated pending row:");
      lines.push(`State: ${item.row.state || item.row.diagnostic_status || "unknown"}`);
      lines.push(`Drain recommendation: ${item.row.drain_recommendation || "review"}`);
      lines.push(`Local payload: ${item.row.local_file || "unknown"}`);
      lines.push(`Destination: ${item.row.server_out || "unknown"}`);
      lines.push(`Issue summary: ${item.row.issue_summary || item.row.error || "none loaded"}`);
    }
    lines.push("");
    lines.push("Guardrail: the checklist does not move files; only the backend drain command can publish parked outputs.");
    return lines;
  }

  function selectedPendingDrainDecisionRow(decisionRows) {
    const rows = Array.isArray(decisionRows) ? decisionRows : [];
    return rows.find((row) => row.key === getSelectedPendingDrainDecisionKey()) || rows[0] || null;
  }

  function selectPendingDrainDecisionRow(item) {
    const scrollSnapshot = capturePendingConfidenceSelectionScroll();
    setSelectedPendingDrainDecisionKey(item?.key || "");
    if (item?.row) {
      setSelectedPendingRowKey(pendingRowKey(item.row));
      renderPendingDetail(item.row);
      renderPendingRows();
      renderPendingReviewDigest(getLastPendingPayload(), getLastPendingRows());
      renderPendingDrainEvidence(getLastPendingPayload(), getLastPendingRows());
    }
    renderPendingDrainDecisionChecklist(getLastPendingPayload(), getLastPendingRows(), getLastPendingSnapshot(), typeof getCommandHistory === "function" ? getCommandHistory() : []);
    restorePendingConfidenceSelectionScroll(scrollSnapshot);
  }

  function renderPendingDrainDecisionChecklist(pending = getLastPendingPayload(), rows = getLastPendingRows(), snapshot = getLastPendingSnapshot(), entries) {
    const payload = pending || {};
    const rowList = Array.isArray(rows) ? rows : [];
    const entryList = Array.isArray(entries) ? entries : [];
    const decisionRows = pendingDrainDecisionRows(payload, rowList, snapshot || {}, entryList);
    if (getSelectedPendingDrainDecisionKey() && !decisionRows.some((row) => row.key === getSelectedPendingDrainDecisionKey())) {
      setSelectedPendingDrainDecisionKey("");
    }
    const selected = selectedPendingDrainDecisionRow(decisionRows);
    const decisionStatus = pendingDrainDecisionStatus(payload, rowList, snapshot || {}, entryList);
    setText("pending-drain-decision-status", decisionStatus);
    const statusNode = byId("pending-drain-decision-status");
    if (statusNode) statusNode.dataset.state = pendingDrainDecisionStatusState(decisionStatus);
    setText("pending-drain-decision-summary", pendingDrainDecisionSummaryLines(payload, rowList, snapshot || {}, entryList).join("\n"));
    setText("pending-drain-decision-detail", pendingDrainDecisionDetailLines(selected).join("\n"));
    const tbody = byId("pending-drain-decision-rows");
    if (!tbody) return;
    if (!decisionRows.length) {
      clearRows(tbody, 4, "No pending publish drain decision rows loaded.");
      updateTableStatusLegend("pending-drain-decision-legend", tbody, "Pending drain decision rows");
      return;
    }
    tbody.replaceChildren();
    decisionRows.forEach((item) => {
      const row = document.createElement("tr");
      row.dataset.status = pendingDrainDecisionPostureStatus(item.posture);
      appendCells(row, [item.checkpoint || "", item.posture || "Read-only", item.evidence || "", item.action || ""]);
      makeRowSelectable(row, () => selectPendingDrainDecisionRow(item), {
        selected: item.key === getSelectedPendingDrainDecisionKey(),
        label: `Pending drain decision checkpoint ${item.checkpoint || ""}`,
      });
      tbody.appendChild(row);
    });
    updateTableStatusLegend("pending-drain-decision-legend", tbody, "Pending drain decision rows");
  }
    const {
      pendingPostDrainTrustDetailLines,
      pendingPostDrainTrustPostureStatus,
      pendingPostDrainTrustRows,
      pendingPostDrainTrustStatus,
      pendingPostDrainTrustSummaryLines,
      renderPendingPostDrainTrust,
    } = pendingPostDrainTrustModule.createPendingPostDrainTrustModule({
      PENDING_READ_ONLY_BOUNDARY,
      appendCells,
      byId,
      capturePendingConfidenceSelectionScroll,
      clearRows,
      getCommandHistory,
      getLastPendingPayload,
      getLastPendingRows,
      getLastPendingSnapshot,
      getSelectedPendingPostDrainTrustKey,
      getSelectedPendingRow,
      makeRowSelectable,
      pendingCurrentRowCount,
      pendingDrainCommandIssueLevel,
      pendingDrainCommandResultText,
      pendingDrainDecisionCompletedProofRows,
      pendingDrainEventCounts,
      pendingDrainEventLeaf,
      pendingDrainEventRoute,
      pendingDrainEventStatus,
      pendingDrainEventsFromSnapshot,
      pendingDrainHistoryLine,
      pendingDrainLatestCommand,
      pendingDrainSummaryItems,
      pendingDrainSummaryLeaf,
      pendingDrainSummaryPayload,
      pendingDrainSummaryScopedIssueLevel,
      pendingDrainSummaryStartCount,
      pendingDrainSummaryMatchesCurrentRows,
      pendingDrainSummaryStatus,
      pendingEvidenceRows,
      pendingFormatCounts,
      pendingRowHasHealthIssue,
      pendingRowKey,
      pendingSampleValidationHandoffLines,
      renderPendingDetail,
      renderPendingReviewDigest,
      renderPendingRows,
      restorePendingConfidenceSelectionScroll,
      setSelectedPendingPostDrainTrustKey,
      setSelectedPendingRowKey,
      setText,
      updateTableStatusLegend,
    });

    return {
      pendingDrainConfidenceRows,
      pendingDrainConfidenceStatus,
      pendingDrainConfidenceSummaryLines,
      pendingDrainDecisionDetailLines,
      pendingDrainDecisionPostureStatus,
      pendingDrainDecisionRows,
      pendingDrainDecisionStatus,
      pendingDrainDecisionStatusState,
      pendingDrainDecisionSummaryLines,
      pendingDrainGuardLines,
      pendingDrainGuardState,
      pendingPostDrainTrustDetailLines,
      pendingPostDrainTrustPostureStatus,
      pendingPostDrainTrustRows,
      pendingPostDrainTrustStatus,
      pendingPostDrainTrustSummaryLines,
      renderPendingDrainActionConfidence,
      renderPendingDrainDecisionChecklist,
      renderPendingDrainGuard,
      renderPendingPostDrainTrust,
    };
  }

  window.__pendingPublishConfidenceModule = { createPendingPublishConfidenceModule };
})();
