// Read-only Network coordinator and worker overview view-models. Loaded before networkView.js.
(function () {
  function createNetworkOverviewModelModule(deps = {}) {
    const { networkQueueRows, networkQueueMatchMaps, networkMatchedQueueRow, networkQueueFileLabel, networkRouteLabel, networkRouteTone, networkRouteEvidence, networkClaimIsActive, networkClaimedKeySet, networkQueueRowClaimed, networkQueueOrder, networkPriorityText, networkSizeText, networkQueueStatus, networkNumber, networkReviewTile, workerProgressText, workerHeartbeatText, networkWorkerStatusState, networkLifecycleRouteAvailable, networkWorkerDriftPayload, networkWorkerDriftStatusText, networkWorkerDriftFieldText, networkWorkerPolicyDivergenceStatusText, networkWorkerPolicyDivergenceActive, networkWorkerPolicyDivergenceText, rawConfigValue, networkStateFileStatus, visibleNetworkModeLabel, coordinatorTarget, displayConfigValue, networkBasename, networkWorkerProgressStatus } = deps;

  function networkCoordinatorOverviewModel({ queue, networkWorkers } = {}) {
    const payload = networkWorkers && typeof networkWorkers === "object" ? networkWorkers : {};
    const rows = Array.isArray(payload.rows) ? payload.rows : [];
    const queueRows = networkQueueRows(queue);
    const queueMaps = networkQueueMatchMaps(queueRows);
    const activeRows = rows.filter(networkClaimIsActive).map((row) => {
      const queueRow = networkMatchedQueueRow(row, queueMaps);
      return {
        row,
        worker: row.worker_name || row.worker_id || "worker",
        file: row.current_file_name || row.current_file || row.source_file || networkQueueFileLabel(queueRow || row),
        route: queueRow ? networkRouteLabel(queueRow) : "",
        routeTone: queueRow ? networkRouteTone(queueRow) : "warning",
        routeEvidence: queueRow ? networkRouteEvidence(queueRow) : "backend evidence missing",
        stage: row.current_stage || row.status || "unknown",
        progress: workerProgressText(row),
        heartbeat: workerHeartbeatText(row),
        status: networkWorkerStatusState(row) || "warning",
      };
    });
    const claimedKeys = networkClaimedKeySet(payload);
    const onDeckRows = queueRows
      .filter((row) => !networkQueueRowClaimed(row, claimedKeys))
      .map((row, index) => ({
        row,
        order: networkQueueOrder(row, index),
        file: networkQueueFileLabel(row),
        route: networkRouteLabel(row) || "Unknown",
        routeTone: networkRouteTone(row),
        priority: networkPriorityText(row),
        size: networkSizeText(row),
        evidence: networkRouteEvidence(row),
      }))
      .sort((left, right) => left.order - right.order)
      .slice(0, 10);
    const warnings = Array.isArray(payload.warnings) ? payload.warnings : [];
    const reviewRows = rows.filter((row) => ["blocked", "warning"].includes(networkWorkerStatusState(row)));
    const blockedCount = reviewRows.filter((row) => networkWorkerStatusState(row) === "blocked").length;
    const issueCount = warnings.length + reviewRows.length;
    const runnableCount = networkNumber(queue?.runnable_count ?? queue?.queue_depth ?? queueRows.length, queueRows.length);
    const priorityCount = networkNumber(queue?.priority_count ?? queueRows.filter((row) => networkPriorityText(row).toLowerCase() !== "normal").length, 0);
    const status = blockedCount ? "Blocked review" : activeRows.length ? "Active" : onDeckRows.length ? "Queued" : issueCount ? "Review" : "Idle";
    return {
      status,
      activeRows,
      onDeckRows,
      tiles: [
        networkReviewTile("Active Claims", String(activeRows.length), `${reviewRows.length} worker rows need review`, blockedCount ? "blocked" : activeRows.length ? "warning" : "match"),
        networkReviewTile("Queue On Deck", String(onDeckRows.length), `${runnableCount} runnable in queue payload`, onDeckRows.length ? "warning" : "match"),
        networkReviewTile("Priority", String(priorityCount), "from queue evidence", priorityCount ? "warning" : "match"),
        networkReviewTile("Session Done", String(payload.session_completed || 0), `${payload.session_failed || 0} failed`, payload.session_failed ? "blocked" : "match"),
        networkReviewTile("Freshness", networkQueueStatus(queue, queueRows), "queue and state-file evidence", String(networkQueueStatus(queue, queueRows)).toLowerCase().includes("stale") ? "warning" : "match"),
        networkReviewTile("Issues", String(issueCount), "worker warnings or blocked claims", issueCount ? "blocked" : "match"),
      ],
      summaryLines: [
        "Coordinator overview:",
        `Active claimed work: ${activeRows.length}; worker rows needing review=${reviewRows.length}; blocked=${blockedCount}; worker warnings=${warnings.length}.`,
        `Queue on deck: ${onDeckRows.length}; total queue rows=${queueRows.length}; runnable=${runnableCount}; priority=${priorityCount}.`,
        `Session completed/failed: ${payload.session_completed || 0}/${payload.session_failed || 0}.`,
        `State freshness: workers=${payload.source || "runtime_state_files"}; queue=${networkQueueStatus(queue, queueRows)}.`,
        "Mutation guardrail: this dashboard reads queue and worker evidence only; it cannot claim, reclaim, release, retry, drain, publish, rename, save settings, or touch media files.",
      ],
    };
  }

  function networkLifecycleRouteSummary(contract, role) {
    if (!role) return "not applicable";
    const dryRunReady = ["start", "stop"].every((action) => networkLifecycleRouteAvailable(contract, role, action, true));
    const confirmedReady = ["start", "stop"].every((action) => networkLifecycleRouteAvailable(contract, role, action, false));
    if (dryRunReady && confirmedReady) return "dry-run and confirmed routes available";
    if (dryRunReady) return "dry-run routes available";
    return "routes missing";
  }

  function networkWorkerCurrentFile(workerState) {
    return workerState?.source_file || workerState?.source_path || workerState?.current_file || workerState?.current_file_name || "";
  }

  function networkWorkerOverviewModel({ config, contract, networkWorkers, queue } = {}) {
    const payload = networkWorkers && typeof networkWorkers === "object" ? networkWorkers : {};
    const workerState = payload.worker_state && typeof payload.worker_state === "object" ? payload.worker_state : {};
    const progress = payload.worker_progress && typeof payload.worker_progress === "object" ? payload.worker_progress : {};
    const drift = networkWorkerDriftPayload(payload);
    const driftActive = String(drift.status || "").toLowerCase() === "drift";
    const queueMaps = networkQueueMatchMaps(networkQueueRows(queue));
    const routeRow = networkMatchedQueueRow(workerState, queueMaps);
    const currentFile = networkWorkerCurrentFile(workerState);
    const pendingDone = Boolean(workerState.pending_done_report);
    const hasClaim = Boolean(workerState.job_id || currentFile || pendingDone);
    const role = String(rawConfigValue(config, "NetworkRole", "standalone") || "standalone").toLowerCase();
    const routeStatus = networkLifecycleRouteSummary(contract || {}, role === "coordinator" ? "coordinator" : "worker");
    const blockedProgress = String(progress.status || "").toLowerCase().includes("block") || pendingDone;
    const status = pendingDone ? "Pending done report" : blockedProgress ? "Blocked review" : hasClaim ? "Active" : role === "worker" ? "Idle" : "Coordinator view";
    const stateFiles = Array.isArray(payload.state_files) ? payload.state_files : [];
    const presentFiles = stateFiles.filter((item) => networkStateFileStatus(item) === "match").length;
    const problemFiles = stateFiles.filter((item) => networkStateFileStatus(item) !== "match").length;
    const claimRows = [
      ["Worker role", visibleNetworkModeLabel(config)],
      ["Worker coordinator URL", coordinatorTarget(config, payload)],
      ["Running vs saved", networkWorkerDriftStatusText(drift)],
      ["Drift fields", networkWorkerDriftFieldText(drift)],
      ["Coordinator policy authority", networkWorkerPolicyDivergenceStatusText(drift)],
      ["Poll interval", `${displayConfigValue(config, "WorkerPollIntervalSecs", "not configured")} second(s)`],
      ["Lifecycle routes", routeStatus],
      ["Current job", workerState.job_id || "(none)"],
      ["Current file", currentFile ? networkBasename(currentFile) : "(none)"],
      ["Route", routeRow ? networkRouteLabel(routeRow) : "unknown/backend evidence missing"],
      ["Route evidence", routeRow ? networkRouteEvidence(routeRow) : "no normalized queue-row match"],
      ["Progress", progress.status ? `${networkWorkerProgressStatus(progress)}; active=${progress.active_count || 0}; blocked=${progress.blocked_count || 0}` : "not loaded"],
      ["Pending done report", pendingDone ? "yes" : "no"],
      ["Worker state file", payload.worker_state_path || "not resolved"],
    ];
    return {
      status,
      claimRows,
      routeRow,
      pendingDone,
      tiles: [
        networkReviewTile("Local Claim", hasClaim ? "Active" : "Idle", currentFile ? networkBasename(currentFile) : "no local claim", pendingDone ? "blocked" : hasClaim ? "warning" : "match"),
        networkReviewTile("Pending Done", pendingDone ? "Yes" : "No", "from worker_state", pendingDone ? "blocked" : "match"),
        networkReviewTile("Coordinator", coordinatorTarget(config, payload), "backend/saved target evidence", role === "worker" ? "warning" : "match"),
        networkReviewTile("Settings Drift", driftActive ? "Drift" : "OK", networkWorkerDriftFieldText(drift), driftActive ? "warning" : "match"),
        networkReviewTile("Policy Authority", networkWorkerPolicyDivergenceActive(drift) ? "Review" : "Ready", networkWorkerPolicyDivergenceText(drift), networkWorkerPolicyDivergenceActive(drift) ? "warning" : "match"),
        networkReviewTile("Poll", `${displayConfigValue(config, "WorkerPollIntervalSecs", "not configured")}s`, "saved worker interval", "match"),
        networkReviewTile("Lifecycle", routeStatus, "contract evidence", routeStatus.includes("missing") ? "warning" : "match"),
        networkReviewTile("State Files", `${presentFiles}/${stateFiles.length}`, problemFiles ? `${problemFiles} review` : "present", problemFiles ? "warning" : "match"),
      ],
      summaryLines: [
        "Worker overview:",
        `Local claim: ${hasClaim ? "present" : "none"}; pending done report=${pendingDone ? "yes" : "no"}; file=${currentFile ? networkBasename(currentFile) : "none"}.`,
        `Worker coordinator URL: ${coordinatorTarget(config, payload)}; poll interval=${displayConfigValue(config, "WorkerPollIntervalSecs", "not configured")} second(s).`,
        `Running vs saved: ${networkWorkerDriftStatusText(drift)}.`,
        `Coordinator policy authority: ${networkWorkerPolicyDivergenceStatusText(drift)}.`,
        `Lifecycle route status: ${routeStatus}; state-file evidence=${presentFiles}/${stateFiles.length} present.`,
        "Remote coordinator queue: Phase 2. Worker-side full coordinator queue visibility requires a read-only backend coordinator queue contract and is not inferred by this WebView.",
        "Mutation guardrail: this dashboard uses backend-owned Network lifecycle routes only; it does not send done reports, mutate queue state, rewrite state files, or touch media files.",
      ],
      remoteQueueSummary: [
        "Phase 2 placeholder:",
        "Remote coordinator queue rows are intentionally not displayed from worker mode in Phase 1.",
        "Requirement: add a backend-owned, read-only coordinator queue reporting contract before the worker tab can show remote queued files.",
        "Current evidence: local worker_state, worker_progress, saved coordinator target, lifecycle contract, and state-file metadata only.",
      ].join("\n"),
    };
  }

  function networkOverviewTileTone(tone) {
    const value = String(tone || "").toLowerCase();
    if (value === "blocked" || value === "failed" || value === "danger") return "danger";
    if (value === "warning" || value === "review" || value === "active") return "warning";
    if (value === "match" || value === "ready" || value === "success") return "success";
    if (value === "info") return "info";
    return "muted";
  }

  const __networkOverviewTilesMod = window.__networkOverviewTilesModule || {};
  delete window.__networkOverviewTilesModule;
  const _networkOverviewTiles = typeof __networkOverviewTilesMod.createNetworkOverviewTilesModule === "function"
    ? __networkOverviewTilesMod.createNetworkOverviewTilesModule({
      byId: typeof byId === "function" ? byId : window.byId,
      documentRef: document,
      networkTileTone: networkOverviewTileTone,
    })
    : {};
  const { renderOverviewTiles = function () {} } = _networkOverviewTiles;


    return { networkCoordinatorOverviewModel, networkWorkerOverviewModel };
  }
  window.__networkOverviewModelModule = { createNetworkOverviewModelModule };
})();
