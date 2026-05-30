(function () {
  function createPendingPublishConfidenceModule(deps = {}) {
    const {
      appendCells = function () {},
      byId = function () { return null; },
      clearRows = function () {},
      getCommandHistory = function () { return []; },
      getLastPendingPayload = function () { return {}; },
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
      pendingDrainSummaryIssueLevel(summary) === "blocked"
        ? "Blocked review"
        : pendingDrainSummaryIssueLevel(summary) === "review"
          ? "Review"
          : pendingDrainSummaryIssueLevel(summary) === "ok"
            ? "Verified-looking"
            : "Not run",
      `status=${pendingDrainSummaryStatus(payload)}; attempted=${summary.attempted_count || 0}; succeeded=${summary.succeeded_count || 0}; already=${summary.already_published_count || 0}; errors=${summary.error_count || 0}; remaining=${summary.remaining_count || 0}`,
      summary.read_error
        ? "Open Diagnostics > State and Run Logs; do not retry blindly while the durable drain summary is unreadable."
        : pendingDrainSummaryIssueLevel(summary) === "blocked" || pendingDrainSummaryIssueLevel(summary) === "review"
          ? "Inspect summary items, current parked rows, and Last Stderr before accepting or retrying publish."
          : pendingDrainSummaryIssueLevel(summary) === "ok"
            ? "Use as supporting post-drain evidence, then verify Completed/output proof for the expected sample."
            : "No durable summary is loaded yet; run or review backend-owned Publish Parked Outputs before post-drain trust.",
      [
        `Summary path: ${summary.path || "not reported"}`,
        `Started/completed: ${summary.started_at || "unknown"} / ${summary.completed_at || "unknown"}`,
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
          "Home Sample Validation can write JSONL evidence notes only; it cannot drain, publish, mark complete, accept output, rewrite manifests, or mutate media.",
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
        "Mutation guardrail: this panel cannot drain, repair, rewrite, move, delete, publish, mark outputs complete, append Sample Validation records, or touch media.",
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
    lines.push("Mutation guardrail: this review is read-only and cannot drain, repair, rewrite, move, delete, publish, mark outputs complete, append validation records, or touch media.");
    return lines;
  }

  function pendingPostDrainTrustDetailLines(item) {
    if (!item) {
      return [
        "Pending Publish post-drain trust review:",
        "Select a checkpoint after running or reviewing Publish Parked Outputs.",
        "Mutation guardrail: this detail panel is read-only.",
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
    setSelectedPendingPostDrainTrustKey(item?.key || "");
    if (item?.row) {
      setSelectedPendingRowKey(pendingRowKey(item.row));
      renderPendingDetail(item.row);
      renderPendingRows();
      renderPendingReviewDigest(getLastPendingPayload(), getLastPendingRows());
    }
    renderPendingPostDrainTrust(getLastPendingPayload(), getLastPendingRows(), getLastPendingSnapshot(), typeof getCommandHistory === "function" ? getCommandHistory() : []);
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
    setText("pending-post-drain-trust-legend", "Post-drain trust rows are read-only and do not move, publish, repair, delete, rewrite, mark outputs complete, or append validation records.");
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

  function pendingDrainConfidenceRank(confidence) {
    const normalized = String(confidence || "").toLowerCase();
    if (normalized === "blocked") return 0;
    if (normalized === "review") return 1;
    if (normalized === "unknown") return 2;
    if (normalized === "ready") return 3;
    return 4;
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
    const latest = pendingDrainLatestCommand(entryList);
    const events = pendingDrainEventsFromSnapshot(snapshot || {});
    const evidenceRows = pendingEvidenceRows(rowList);
    const blockingEvidence = evidenceRows.filter((entry) => ["do-not-drain", "diagnostic-error", "missing-payload", "manifest-invalid"].includes(entry.evidenceClass));
    const reviewEvidence = evidenceRows.filter((entry) => !["do-not-drain", "diagnostic-error", "missing-payload", "manifest-invalid"].includes(entry.evidenceClass));
    const selectedRow = getSelectedPendingRow();
    const recoveryRows = getLastPendingRecoveryPlanRows();
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
        : "Review row-level evidence below before pressing Publish Parked Outputs.",
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
      recoveryRows.length ? `planned rows=${recoveryRows.length}; blocked=${recoveryBlocked}; review=${recoveryReview}` : "no recovery plan loaded",
      recoveryRows.length
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
      pendingDrainSummaryIssueLevel(summary) === "blocked" ? "blocked" : pendingDrainSummaryIssueLevel(summary) === "review" ? "review" : pendingDrainSummaryIssueLevel(summary) === "ok" ? "ready" : "unknown",
      `status=${pendingDrainSummaryStatus(payload)}; attempted=${summary.attempted_count || 0}; errors=${summary.error_count || 0}; remaining=${summary.remaining_count || 0}`,
      "Treat the durable summary as last-attempt evidence; the current pending rows remain the source of truth for what is still parked.",
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
      "This is the final read-only operator handoff before Publish Parked Outputs.",
      "Backend Publish Parked Outputs remains the only authority that can validate and move parked files.",
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
    lines.push("Mutation guardrail: this panel cannot drain, repair, rewrite, move, delete, publish, or bypass backend validation.");
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
    setText("pending-drain-confidence-legend", "Drain confidence rows are read-only and do not move, publish, repair, delete, rewrite, or bypass backend validation.");
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
    if (
      typeof window.completedPendingProofRows === "function"
      && typeof window.getLastCompletedPayload === "function"
      && typeof window.getLastCompletedRows === "function"
    ) {
      return window.completedPendingProofRows(window.getLastCompletedPayload(), window.getLastCompletedRows(), pending || {});
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
    const latest = pendingDrainLatestCommand(entryList);
    const events = pendingDrainEventsFromSnapshot(snapshot || {});
    const recoveryRows = getLastPendingRecoveryPlanRows();
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
          "A readable pending scan is required before Publish Parked Outputs is trustworthy.",
        ],
      );
      return rowsOut;
    }

    add(
      "backend-authority",
      "Backend movement authority",
      "Read-only",
      "Publish Parked Outputs remains the only authority that can validate and move parked files.",
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
        "Publish Parked Outputs does not drain only the visible table subset.",
        "Backend validation sees current parked payloads/manifests, not the filtered WebView table.",
      ],
      selectedRow,
    );
    add(
      "recovery-plan",
      "Recovery dry-run",
      recoveryBlocked ? "Blocked review" : recoveryReview ? "Review" : recoveryRows.length ? "Ready-looking" : rowList.length ? "Read-first" : "Read-only",
      recoveryRows.length ? `planned rows=${recoveryRows.length}; blocked=${recoveryBlocked}; review=${recoveryReview}` : "no recovery dry-run plan loaded",
      recoveryRows.length
        ? "Use recovery-plan row drilldown for blocked/review planned actions before drain."
        : rowList.length
          ? "Build a selected-row or all-rows recovery dry-run before risky drains."
          : "No parked rows loaded; recovery dry-run is optional.",
      [
        "Recovery plan is dry-run only.",
        "It should explain what the backend would do without moving, deleting, repairing, or publishing files.",
      ],
      selectedRow,
    );
    add(
      "drain-command-summary-events",
      "Command, summary, and event agreement",
      pendingDrainCommandIssueLevel(latest) === "blocked" || pendingDrainSummaryIssueLevel(summary) === "blocked"
        ? "Blocked review"
        : pendingDrainCommandIssueLevel(latest) === "review" || pendingDrainSummaryIssueLevel(summary) === "review"
          ? "Review"
          : latest || pendingDrainSummaryIssueLevel(summary) === "ok" || events.length
            ? "Read-first"
            : "Read-only",
      `latest=${latest ? `${latest.command || "drain"} [${pendingDrainCommandResultText(latest)}]` : "none"}; summary=${pendingDrainSummaryStatus(payload)}; events=${events.length}`,
      "Compare latest drain command, durable drain summary, recent drain events, and current parked rows before another drain.",
      [
        `Latest command: ${latest ? pendingDrainHistoryLine(latest) : "none loaded"}`,
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
      "Use backend allowlisted diagnostics targets before pressing Publish Parked Outputs when any row is blocked, review, or unknown.",
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
      "Press Publish Parked Outputs only when the evidence is coherent enough for backend validation to run.",
      [
        "Mutation guardrail: this checklist cannot drain, repair, rewrite, move, delete, publish, accept outputs, write manifests, or bypass backend validation.",
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
      `Daily-use handoff: Pending Publish evidence decides whether it is sensible to press Publish Parked Outputs; only the backend drain can move files. Operator outcome: ${outcome}.`,
      `Checkpoints loaded: ${decisionRows.length}`,
      `Blocked/review/read-first/unknown: ${blocked}/${review}/${readFirst}/${unknown}`,
      "Decision rule: drain only after current parked rows, recovery dry-run, latest drain evidence, Completed/output proof, and diagnostics order agree.",
      "Scope boundary: Pending filters, selected rows, recovery dry-runs, and rendered row caps never narrow backend drain scope or publish files.",
    ];
    if (blocked) {
      lines.push("First action: do not press Publish Parked Outputs until blocked evidence is explained.");
    } else if (review || readFirst || unknown) {
      lines.push("First action: select review/read-first checkpoints, then use backend allowlisted diagnostics before publishing.");
    } else {
      lines.push("First action: no local blocker is visible, but backend Publish Parked Outputs still performs the authoritative validation and movement.");
    }
    lines.push("Mutation guardrail: this checklist cannot drain, repair, rewrite, move, delete, publish, accept outputs, write manifests, or bypass backend validation.");
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
      ? `Publish Parked Outputs blocked by WebView evidence: ${decision}.`
      : review
        ? `Publish Parked Outputs requires operator review: ${decision}.`
        : "Publish Parked Outputs can be submitted to backend validation.";
    return {
      allowed: !blocked,
      review_required: review,
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
      `Button action: ${guard.allowed ? (guard.review_required ? "allowed after explicit review confirmation" : "allowed") : "blocked locally"}`,
      guard.message || "",
    ].filter(Boolean);
    if (guard.allowed) {
      lines.push("The click still uses /api/pipeline/start with mode=drain_pending_pushes; frontend evidence does not move files.");
    } else {
      lines.push("First action: select blocked/review checklist rows, build a recovery dry-run if parked rows exist, and read Pending Publish diagnostics before retrying.");
    }
    if (guard.filter_scope) {
      lines.push(`Pending table filter: ${guard.filter_scope.active ? "active" : "inactive"}; visible ${guard.filter_scope.visibleCount}/${guard.filter_scope.totalCount}; hidden blocked/review ${guard.filter_scope.hiddenBlockedCount}/${guard.filter_scope.hiddenReviewCount}.`);
      lines.push("Backend drain scope remains all loaded parked rows; local filters do not narrow publish scope.");
    }
    lines.push("Mutation guardrail: this guard cannot drain, repair, rewrite, move, delete, publish, accept outputs, write manifests, or bypass backend validation.");
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
    advancedBody.textContent = (detailLines || []).filter(Boolean).join("\n");
    root.appendChild(advancedBody);
  }

  function renderPendingDrainGuard(pending = getLastPendingPayload(), rows = getLastPendingRows(), snapshot = getLastPendingSnapshot(), entries) {
    const state = pendingDrainGuardState(pending, rows, snapshot, entries);
    setText("pending-drain-guard-status", state.allowed ? (state.review_required ? "Review confirm" : "Allowed") : "Blocked");
    const statusNode = byId("pending-drain-guard-status");
    if (statusNode) statusNode.dataset.state = state.allowed ? (state.review_required ? "warning" : "ready") : "blocked";
    renderDiagnosticCallout("pending-drain-guard-summary", pendingDrainGuardLines(state));
    const button = byId("pending-drain-button");
    if (button) {
      button.title = state.allowed ? state.confirm_message : state.message;
      button.dataset.guardState = state.allowed ? (state.review_required ? "review" : "allowed") : "blocked";
    }
    return state;
  }

  function pendingDrainDecisionDetailLines(item) {
    if (!item) {
      return [
        "Pending Publish drain decision checklist:",
        "Select a checkpoint before publishing parked outputs.",
        "Mutation guardrail: this detail panel is read-only.",
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
    setSelectedPendingDrainDecisionKey(item?.key || "");
    if (item?.row) {
      setSelectedPendingRowKey(pendingRowKey(item.row));
      renderPendingDetail(item.row);
      renderPendingRows();
      renderPendingReviewDigest(getLastPendingPayload(), getLastPendingRows());
      renderPendingDrainEvidence(getLastPendingPayload(), getLastPendingRows());
    }
    renderPendingDrainDecisionChecklist(getLastPendingPayload(), getLastPendingRows(), getLastPendingSnapshot(), typeof getCommandHistory === "function" ? getCommandHistory() : []);
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
