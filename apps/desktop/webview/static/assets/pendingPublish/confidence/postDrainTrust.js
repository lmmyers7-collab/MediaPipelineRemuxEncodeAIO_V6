(function () {
  function createPendingPostDrainTrustModule(deps = {}) {
    const {
      PENDING_READ_ONLY_BOUNDARY = "Mutation guardrail: read-only evidence; backend routes own pending-publish changes.",
      appendCells = function () {},
      byId = function () { return null; },
      capturePendingConfidenceSelectionScroll = function () { return null; },
      clearRows = function () {},
      getCommandHistory = function () { return []; },
      getLastPendingPayload = function () { return {}; },
      getLastPendingRows = function () { return []; },
      getLastPendingSnapshot = function () { return {}; },
      getSelectedPendingPostDrainTrustKey = function () { return ""; },
      getSelectedPendingRow = function () { return null; },
      makeRowSelectable = function () {},
      pendingCurrentRowCount = function () { return 0; },
      pendingDrainCommandIssueLevel = function () { return "none"; },
      pendingDrainCommandResultText = function () { return "unknown"; },
      pendingDrainDecisionCompletedProofRows = function () { return []; },
      pendingDrainEventCounts = function () { return "none"; },
      pendingDrainEventLeaf = function () { return "unknown"; },
      pendingDrainEventRoute = function () { return "unknown"; },
      pendingDrainEventStatus = function () { return "unknown"; },
      pendingDrainEventsFromSnapshot = function () { return []; },
      pendingDrainHistoryLine = function () { return ""; },
      pendingDrainLatestCommand = function () { return null; },
      pendingDrainSummaryItems = function () { return []; },
      pendingDrainSummaryLeaf = function () { return "unknown"; },
      pendingDrainSummaryPayload = function () { return {}; },
      pendingDrainSummaryScopedIssueLevel = function () { return "none"; },
      pendingDrainSummaryStartCount = function () { return null; },
      pendingDrainSummaryMatchesCurrentRows = function () { return true; },
      pendingDrainSummaryStatus = function () { return "Not loaded"; },
      pendingEvidenceRows = function () { return []; },
      pendingFormatCounts = function () { return "none"; },
      pendingRowHasHealthIssue = function () { return false; },
      pendingRowKey = function () { return ""; },
      pendingSampleValidationHandoffLines = function () { return []; },
      renderPendingDetail = function () {},
      renderPendingReviewDigest = function () {},
      renderPendingRows = function () {},
      restorePendingConfidenceSelectionScroll = function () {},
      setSelectedPendingPostDrainTrustKey = function () {},
      setSelectedPendingRowKey = function () {},
      setText = function () {},
      updateTableStatusLegend = function () {},
    } = deps;
  function pendingPostDrainTrustPostureStatus(posture) {
    const normalized = String(posture || "").toLowerCase();
    if (normalized.includes("blocked") || normalized.includes("do not")) return "blocked";
    if (normalized.includes("review")) return "warning";
    if (normalized.includes("read-first")) return "changed";
    if (normalized.includes("unknown") || normalized.includes("incomplete") || normalized.includes("not run")) return "unknown";
    if (normalized.includes("ready") || normalized.includes("verified") || normalized.includes("current")) return "match";
    return "warning";
  }

  function pendingPostDrainTrustRows(pending, rows, snapshot, entries) {
    const payload = pending || {};
    const rowList = Array.isArray(rows) ? rows : [];
    const entryList = Array.isArray(entries) ? entries : [];
    const summary = pendingDrainSummaryPayload(payload);
    const currentRowCount = pendingCurrentRowCount(payload, rowList);
    const summaryStartCount = pendingDrainSummaryStartCount(summary);
    const summaryMatchesCurrent = pendingDrainSummaryMatchesCurrentRows(summary, currentRowCount);
    const summaryLevel = pendingDrainSummaryScopedIssueLevel(summary, currentRowCount);
    const latest = pendingDrainLatestCommand(entryList);
    const events = pendingDrainEventsFromSnapshot(snapshot || {});
    const completedProofRows = pendingDrainDecisionCompletedProofRows(payload);
    const completedProofBlocked = completedProofRows.filter((row) => row.status === "blocked").length;
    const completedProofExact = completedProofRows.filter((row) => row.signal === "pending-destination-overlap" || row.signal === "completed-source-still-pending" || row.signal === "drain-summary-output-proof" || row.signal === "drain-summary-source-proof" || row.signal === "completed-missing-output-still-pending" || row.signal === "completed-missing-output-with-drain-proof").length;
    const completedProofLeaf = completedProofRows.filter((row) => row.signal === "same-leaf-review").length;
    const issueRows = rowList.filter(pendingRowHasHealthIssue);
    const evidenceRows = pendingEvidenceRows(rowList);
    const blockingEvidence = evidenceRows.filter((entry) => ["do-not-drain", "diagnostic-error", "missing-payload", "manifest-invalid"].includes(entry.evidenceClass));
    const reviewEvidence = evidenceRows.filter((entry) => !["do-not-drain", "diagnostic-error", "missing-payload", "manifest-invalid"].includes(entry.evidenceClass));
    const selectedRow = getSelectedPendingRow();
    const succeeded = Number(summary.succeeded_count || 0) + Number(summary.already_published_count || 0);
    const rowsOut = [];
    const add = (key, checkpoint, posture, evidence, action, detail = [], row = null) => {
      rowsOut.push({ key, checkpoint, posture, evidence, action, detail, row });
    };

    if (payload.error) {
      add(
        "pending-scan-unavailable",
        "Current Pending Publish state",
        "Blocked review",
        `Pending Publish scan unavailable: ${payload.error}`,
        "Open Diagnostics > Pending Publish, Run Logs, and Last Stderr before trusting any drain result.",
        [
          "Post-drain trust review:",
          "A readable current Pending Publish scan is required before treating parked outputs as drained or still waiting.",
        ],
      );
      return rowsOut;
    }

    add(
      "current-pending-state",
      "Current parked state",
      rowList.length ? (blockingEvidence.length ? "Blocked review" : issueRows.length || reviewEvidence.length ? "Review" : "Read-first") : "Verified-looking",
      `current parked rows=${payload.count || rowList.length || 0}; ready=${payload.ready_count || 0}; issues=${payload.issue_count || issueRows.length}; health=${payload.health_count || 0}; blocking=${blockingEvidence.length}; review=${reviewEvidence.length}`,
      blockingEvidence.length
        ? "Do not trust this drain outcome yet. Select the blocked parked row and inspect diagnostics before rerun, cleanup, validation acceptance, or another drain."
        : rowList.length
          ? "Parked rows still exist. Select row detail and compare drain summary before rerun, cleanup, or another drain."
        : "No parked rows are currently loaded. Cross-check Completed, durable drain summary, and logs before assuming all expected outputs published.",
      [
        "Current Pending Publish state is the source of truth for what is still parked.",
        "An empty Pending Publish page is not by itself proof that a specific output reached the final library path.",
        `Blocking evidence rows: ${blockingEvidence.length}; review evidence rows: ${reviewEvidence.length}.`,
      ],
      selectedRow,
    );

    add(
      "durable-drain-summary",
      "Durable drain summary",
      summaryLevel === "blocked"
        ? "Blocked review"
        : summaryLevel === "review"
          ? "Review"
          : summaryLevel === "ok"
            ? "Verified-looking"
            : "Not run",
      `status=${pendingDrainSummaryStatus(payload)}; summary rows=${summaryStartCount ?? "unknown"}; current rows=${currentRowCount}; attempted=${summary.attempted_count || 0}; succeeded=${summary.succeeded_count || 0}; already=${summary.already_published_count || 0}; errors=${summary.error_count || 0}; remaining=${summary.remaining_count || 0}`,
      summary.read_error
        ? "Open Diagnostics > State and Run Logs; do not retry blindly while the durable drain summary is unreadable."
        : !summaryMatchesCurrent
          ? "The last drain summary covers a different parked-row count; review it as stale evidence while relying on current rows and backend validation."
        : summaryLevel === "blocked" || summaryLevel === "review"
          ? "Inspect summary items, current parked rows, and Last Stderr before accepting or retrying publish."
          : summaryLevel === "ok"
            ? "Use as supporting post-drain evidence, then verify Completed/output proof for the expected sample."
            : "No durable summary is loaded yet; run or review backend-owned Drain Parked Outputs before post-drain trust.",
      [
        `Summary path: ${summary.path || "not reported"}`,
        `Started/completed: ${summary.started_at || "unknown"} / ${summary.completed_at || "unknown"}`,
        `Summary rows/current rows: ${summaryStartCount ?? "unknown"} / ${currentRowCount}`,
        `Status counts: ${pendingFormatCounts(summary.status_counts)}`,
        `Route counts: ${pendingFormatCounts(summary.route_counts)}`,
        "Latest summary items:",
        ...pendingDrainSummaryItems(summary).slice(-5).reverse().map((item) => `- [${item.status || "unknown"}] ${pendingDrainSummaryLeaf(item)}${item.error ? ` - ${item.error}` : ""}`),
      ],
    );

    add(
      "recent-drain-events",
      !Array.isArray(snapshot?.recent_events)
        ? "Evidence incomplete"
        : events.some((event) => !["succeeded", "already_published"].includes(pendingDrainEventStatus(event).toLowerCase()))
          ? "Review"
          : events.length
            ? "Verified-looking"
            : "Evidence incomplete",
      Array.isArray(snapshot?.recent_events) ? `events=${events.length}${events.length ? `; statuses=${pendingDrainEventCounts(events, pendingDrainEventStatus)}` : ""}` : "snapshot events unavailable",
      events.length
        ? "Use events as bounded context only; confirm current pending state and durable summary agree."
        : "Refresh Diagnostics/Pipeline Events or read Run Logs if a drain command reported success without recent publish events.",
      [
        "Recent drain events are runtime evidence, not final output acceptance.",
        ...events.slice(-5).reverse().map((event) => `- ${pendingDrainEventStatus(event)} ${pendingDrainEventLeaf(event)} (${pendingDrainEventRoute(event)})`),
      ],
    );

    add(
      "completed-output-correlation",
      completedProofBlocked
        ? "Blocked review"
        : completedProofExact
          ? "Review"
          : completedProofLeaf
            ? "Review"
            : rowList.length
              ? "Read-first"
              : succeeded
                ? "Read-first"
                : "Evidence incomplete",
      `Completed/Pending proof rows=${completedProofRows.length}; blocked=${completedProofBlocked}; exact=${completedProofExact}; same-leaf=${completedProofLeaf}`,
      completedProofBlocked
        ? "Resolve blocked Completed/Pending proof before rerun, cleanup, delete, or another drain."
        : completedProofExact
          ? "Review exact overlaps; a Completed row still matching Pending can mean parked output, stale state, or recent drain evidence."
          : completedProofLeaf
            ? "Treat same-leaf matches as duplicate-title hints only; compare full paths."
            : "Open Completed and compare exact source/output paths before accepting that a drained file reached final output.",
      [
        "Proof order: Completed row -> exact output/source path -> pending row/state -> durable drain summary -> Run Logs.",
        "Same-leaf matches are duplicate-title hints only.",
      ],
      selectedRow,
    );

    add(
      "sample-validation-deferred-publish",
      rowList.some((row) => pendingSampleValidationHandoffLines(row).join("\n").includes("hold_review"))
        ? "Review"
        : rowList.length
          ? "Read-first"
          : succeeded
            ? "Verified-looking"
            : "Evidence incomplete",
      "Pilot category=deferred-publish; accepted evidence requires Completed output proof and durable drain summary agreement.",
      rowList.length
        ? "Keep pending-row Sample Validation evidence at hold/review until post-drain proof is coherent."
        : "After a successful drain, use Home Sample Validation only after Completed, durable summary, logs, and playback/output evidence agree.",
      [
        ...(selectedRow ? pendingSampleValidationHandoffLines(selectedRow) : [
          "Sample Validation handoff: Pending Publish",
          "Suggested pilot category: deferred-publish",
          "Suggested evidence decision: accepted only after Completed output proof and durable drain summary agree",
          "Home Sample Validation can write JSONL evidence notes only; backend routes own pending-publish changes.",
        ]),
      ],
      selectedRow,
    );

    add(
      "latest-drain-command",
      pendingDrainCommandIssueLevel(latest) === "blocked"
        ? "Blocked review"
        : pendingDrainCommandIssueLevel(latest) === "review"
          ? "Review"
          : latest
            ? "Read-first"
            : "Not run",
      latest ? `${latest.command || "drain"} [${pendingDrainCommandResultText(latest)}] ${latest.message || ""}`.trim() : "no drain command in loaded history",
      latest
        ? "Compare command result with durable summary and current parked rows before another drain or sample acceptance."
        : "No loaded command history proves a drain attempt; this is normal before first publish.",
      [
        `Latest command: ${latest ? pendingDrainHistoryLine(latest) : "none loaded"}`,
        "Command history is explanatory only; durable summary/current pending rows remain stronger post-drain evidence.",
      ],
    );

    add(
      "post-drain-boundary",
      "Decision boundary",
      "Read-only",
      "This review explains post-drain trust; it does not publish, mark complete, or accept sample evidence.",
      "Trust a drained sample only when current pending state, durable summary, recent events/logs, Completed output proof, and playback/Sample Validation agree.",
      [
        PENDING_READ_ONLY_BOUNDARY,
      ],
    );
    return rowsOut;
  }

  function pendingPostDrainTrustStatus(pending, rows, snapshot, entries) {
    const trustRows = pendingPostDrainTrustRows(pending, rows, snapshot, entries);
    if (trustRows.some((row) => pendingPostDrainTrustPostureStatus(row.posture) === "blocked")) return "Blocked review";
    if (trustRows.some((row) => pendingPostDrainTrustPostureStatus(row.posture) === "warning")) return "Review";
    if (trustRows.some((row) => pendingPostDrainTrustPostureStatus(row.posture) === "unknown")) return "Evidence incomplete";
    if (trustRows.some((row) => pendingPostDrainTrustPostureStatus(row.posture) === "changed")) return "Read evidence";
    return trustRows.length ? "Verified-looking" : "Not evaluated";
  }

  function pendingPostDrainTrustSummaryLines(pending, rows, snapshot, entries) {
    const trustRows = pendingPostDrainTrustRows(pending, rows, snapshot, entries);
    const blocked = trustRows.filter((row) => pendingPostDrainTrustPostureStatus(row.posture) === "blocked").length;
    const review = trustRows.filter((row) => pendingPostDrainTrustPostureStatus(row.posture) === "warning").length;
    const readFirst = trustRows.filter((row) => pendingPostDrainTrustPostureStatus(row.posture) === "changed").length;
    const unknown = trustRows.filter((row) => pendingPostDrainTrustPostureStatus(row.posture) === "unknown").length;
    const lines = [
      "Pending Publish post-drain trust review:",
      `Checkpoints loaded: ${trustRows.length}`,
      `Blocked/review/read-first/unknown: ${blocked}/${review}/${readFirst}/${unknown}`,
      "Decision rule: a drain is trusted only when current parked rows, durable drain summary, recent drain events/logs, Completed output proof, and Sample Validation deferred-publish evidence agree.",
    ];
    if (blocked) {
      lines.push("First action: stop treating this drain as trusted and inspect blocked checkpoints before rerun, cleanup, delete, or another drain.");
    } else if (review || readFirst || unknown) {
      lines.push("First action: select review/read-first checkpoints and compare Completed, Pending Publish, Diagnostics, Last Drain Summary, and Sample Validation before accepting the sample.");
    } else {
      lines.push("First action: evidence is ready-looking, but playback/output inspection and backend-authored records remain authoritative.");
    }
    lines.push(PENDING_READ_ONLY_BOUNDARY);
    return lines;
  }

  function pendingPostDrainTrustDetailLines(item) {
    if (!item) {
      return [
        "Pending Publish post-drain trust review:",
        "Select a checkpoint after running or reviewing Drain Parked Outputs.",
        PENDING_READ_ONLY_BOUNDARY,
      ];
    }
    const lines = [
      "Pending Publish post-drain trust review:",
      `Checkpoint: ${item.checkpoint || "unknown"}`,
      `Posture: ${item.posture || "read-only"}`,
      `Evidence: ${item.evidence || ""}`,
      `Operator action: ${item.action || ""}`,
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
    lines.push("Guardrail: this review cannot move files or mark publish complete; it only explains what proof still needs operator review.");
    return lines;
  }

  function selectedPendingPostDrainTrustRow(trustRows) {
    const rows = Array.isArray(trustRows) ? trustRows : [];
    return rows.find((row) => row.key === getSelectedPendingPostDrainTrustKey())
      || rows.find((row) => pendingPostDrainTrustPostureStatus(row.posture) === "blocked")
      || rows.find((row) => pendingPostDrainTrustPostureStatus(row.posture) === "warning")
      || rows[0]
      || null;
  }

  function selectPendingPostDrainTrustRow(item) {
    const scrollSnapshot = capturePendingConfidenceSelectionScroll();
    setSelectedPendingPostDrainTrustKey(item?.key || "");
    if (item?.row) {
      setSelectedPendingRowKey(pendingRowKey(item.row));
      renderPendingDetail(item.row);
      renderPendingRows();
      renderPendingReviewDigest(getLastPendingPayload(), getLastPendingRows());
    }
    renderPendingPostDrainTrust(getLastPendingPayload(), getLastPendingRows(), getLastPendingSnapshot(), typeof getCommandHistory === "function" ? getCommandHistory() : []);
    restorePendingConfidenceSelectionScroll(scrollSnapshot);
  }

  function renderPendingPostDrainTrust(pending, rows, snapshot, entries) {
    const payload = pending || {};
    const rowList = Array.isArray(rows) ? rows : [];
    const entryList = Array.isArray(entries) ? entries : [];
    const trustRows = pendingPostDrainTrustRows(payload, rowList, snapshot || {}, entryList);
    if (getSelectedPendingPostDrainTrustKey() && !trustRows.some((row) => row.key === getSelectedPendingPostDrainTrustKey())) {
      setSelectedPendingPostDrainTrustKey("");
    }
    const selected = selectedPendingPostDrainTrustRow(trustRows);
    setText("pending-post-drain-trust-status", pendingPostDrainTrustStatus(payload, rowList, snapshot || {}, entryList));
    const statusNode = byId("pending-post-drain-trust-status");
    if (statusNode) statusNode.dataset.state = pendingPostDrainTrustPostureStatus(selected?.posture || pendingPostDrainTrustStatus(payload, rowList, snapshot || {}, entryList));
    setText("pending-post-drain-trust-summary", pendingPostDrainTrustSummaryLines(payload, rowList, snapshot || {}, entryList).join("\n"));
    setText("pending-post-drain-trust-detail", pendingPostDrainTrustDetailLines(selected).join("\n"));
    setText("pending-post-drain-trust-legend", "Post-drain trust rows are read-only evidence; backend routes own pending-publish changes.");
    const tbody = byId("pending-post-drain-trust-rows");
    if (!tbody) return;
    if (!trustRows.length) {
      clearRows(tbody, 4, "No post-drain trust rows loaded.");
      updateTableStatusLegend("pending-post-drain-trust-legend", tbody, "Post-drain trust rows");
      return;
    }
    tbody.replaceChildren();
    trustRows.forEach((item) => {
      const row = document.createElement("tr");
      row.dataset.status = pendingPostDrainTrustPostureStatus(item.posture);
      appendCells(row, [item.checkpoint || "", item.posture || "Read-only", item.evidence || "", item.action || ""]);
      makeRowSelectable(row, () => selectPendingPostDrainTrustRow(item), {
        selected: item.key === selected?.key,
        label: `Pending post-drain trust checkpoint ${item.checkpoint || ""}`,
      });
      tbody.appendChild(row);
    });
    updateTableStatusLegend("pending-post-drain-trust-legend", tbody, "Post-drain trust rows");
  }


    return {
      pendingPostDrainTrustDetailLines,
      pendingPostDrainTrustPostureStatus,
      pendingPostDrainTrustRows,
      pendingPostDrainTrustStatus,
      pendingPostDrainTrustSummaryLines,
      renderPendingPostDrainTrust,
    };
  }

  window.__pendingPostDrainTrustModule = { createPendingPostDrainTrustModule };
})();
