(function () {
  function createNetworkEvidenceModule(deps = {}) {
    const { byId, setText, clearRows, appendCells, makeRowSelectable, updateTableStatusLegend, networkRuntimeStatus, networkLifecycleStateFor, networkLifecycleRelevantRoles, networkWorkerDriftPayload, networkWorkerDriftSummaryLines, networkWorkerPolicyDivergencePayload, networkWorkerPolicyDivergenceSummaryLines, networkDiagnosticLayerPosture, networkDiagnosticLayerLines, networkStateFilesDiagnosticStatus, networkStateFileCompactLines, networkStateFileSummaryLines, networkLifecycleControlLines, networkTokenPostureLines, networkCoordinatorConnectivityLines, networkWorkerStatusState, routeExists, networkLifecycleContracts, networkPathMapStatus, configuredStatus, coordinatorTarget, displayConfigValue, networkCoordinatorBindEndpoint, configFlagText, closeReadinessLine, snapshotStateLine, networkLifecycleContractSummary, networkLifecycleDryRunRouteCount, networkLifecycleMutationRouteCount, networkSetupMutationRouteRows, networkSetupMutationRouteSummary, getSelectedKey, setSelectedKey } = deps;
      function networkEvidenceCount(value) {
        const number = Number(value || 0);
        return Number.isFinite(number) ? Math.max(0, Math.round(number)) : 0;
      }

      function networkEvidencePostureStatus(posture) {
        const value = String(posture || "").toLowerCase();
        if (value.includes("blocked") || value.includes("unsafe") || value.includes("failed") || value.includes("pending report")) return "blocked";
        if (value.includes("review") || value.includes("warning") || value.includes("unknown") || value.includes("stale") || value.includes("not loaded")) return "warning";
        return "match";
      }

      function networkEvidenceStatus(rows = []) {
        if (!rows.length) return "Not loaded";
        if (rows.some((row) => networkEvidencePostureStatus(row.posture) === "blocked")) return "Blocked review";
        if (rows.some((row) => networkEvidencePostureStatus(row.posture) === "warning")) return "Review";
        return "Ready";
      }

      function networkEvidenceWorkerCounts(rows = []) {
        return (Array.isArray(rows) ? rows : []).reduce((counts, row) => {
          const state = networkWorkerStatusState(row) || "unknown";
          counts[state] = (counts[state] || 0) + 1;
          return counts;
        }, {});
      }

      function networkEvidenceRow(key, checkpoint, posture, evidence, action, detail = []) {
        return { key, checkpoint, posture, evidence, action, detail };
      }

      function networkEvidenceRows({ role, config, closeReadiness, snapshot, contract, networkWorkers } = {}) {
        const payload = networkWorkers && typeof networkWorkers === "object" ? networkWorkers : {};
        const rows = Array.isArray(payload.rows) ? payload.rows : [];
        const warnings = Array.isArray(payload.warnings) ? payload.warnings : [];
        const workerState = payload.worker_state && typeof payload.worker_state === "object" ? payload.worker_state : {};
        const workerCounts = networkEvidenceWorkerCounts(rows);
        const hasWorkerRoute = routeExists(contract, "/api/network/workers", "GET");
        const hasDiagnosticsOpen = routeExists(contract, "/api/diagnostics/open", "POST");
        const lifecycleContracts = networkLifecycleContracts(contract);
        const roleText = role || "standalone";
        const closeLoaded = closeReadiness && typeof closeReadiness === "object";
        const closeBlocked = closeLoaded && closeReadiness.safe_to_close === false;
        const pendingDone = Boolean(workerState.pending_done_report);
        const problemRows = networkEvidenceCount(workerCounts.blocked);
        const activeRows = networkEvidenceCount(workerCounts.warning);
        const idleRows = networkEvidenceCount(workerCounts.match);
        const unknownRows = networkEvidenceCount(workerCounts.unknown);
        const hasNetworkMode = roleText === "coordinator" || roleText === "worker";
        const pathMap = networkPathMapStatus(config);
        const overrides = configuredStatus(config, "WorkerConfigOverrides");
        const evidence = [];

        evidence.push(networkEvidenceRow(
          "role-settings",
          "Role / settings",
          hasNetworkMode ? "review" : "ready",
          `role=${roleText}; target=${coordinatorTarget(config, payload)}; worker poll=${displayConfigValue(config, "WorkerPollIntervalSecs", "not configured")}; path map=${pathMap}; overrides=${overrides}`,
          hasNetworkMode
            ? "Review Settings Network builder and backend Network diagnostics before trusting distributed work."
            : "Standalone mode has no worker lifecycle to start from WebView.",
          [
            `NetworkRole: ${roleText}`,
            `Worker coordinator URL: ${coordinatorTarget(config, payload)}`,
            `Coordinator bind endpoint: ${networkCoordinatorBindEndpoint(config, payload)}`,
            `Coordinator local encode: ${configFlagText(config, "CoordinatorAlsoEncodeLocally", "not configured")}`,
            `Worker URL: ${displayConfigValue(config, "WorkerCoordinatorUrl", "not configured")}`,
            `Worker source path map: ${pathMap}`,
            `Per-worker overrides: ${overrides} (backend-disabled)`,
          ],
        ));

        evidence.push(networkEvidenceRow(
          "lifecycle-boundary",
          "Lifecycle boundary",
          !closeLoaded ? "unknown" : closeBlocked ? "blocked" : "ready",
          `close=${closeLoaded ? (closeReadiness.safe_to_close ? "safe" : "active/blocked") : "not loaded"}; state=${snapshot?.pipeline_state || closeReadiness?.state || "unknown"}`,
          closeBlocked
            ? "Do not change NetworkRole or start/stop coordinator/worker work while close-readiness reports active work."
            : "Lifecycle controls remain backend-owned until backend command ownership is designed and tested.",
          [
            closeReadinessLine(closeReadiness),
            snapshotStateLine(snapshot),
            "WebView can inspect persisted state and logs only; it cannot start, stop, drain, reclaim, abort, or release network jobs.",
          ],
        ));

        evidence.push(networkEvidenceRow(
          "api-contract",
          "API contract",
          hasWorkerRoute && hasDiagnosticsOpen ? "ready" : "not loaded",
          `network workers route=${hasWorkerRoute ? "available" : "missing"}; diagnostics open=${hasDiagnosticsOpen ? "available" : "missing"}; routes=${Array.isArray(contract?.routes) ? contract.routes.length : 0}`,
          hasWorkerRoute
            ? "Use Network worker rows for persisted evidence; use Diagnostics opens/tails for logs and state."
            : "Refresh contract and Local API before trusting Network page state.",
          [
            "Route /api/network/workers is read-only and has effect=none in the backend contract.",
            networkLifecycleContractSummary(contract),
            "Diagnostics open actions use backend target allowlists, not frontend paths.",
          ],
        ));

        const diagnosticPosture = networkDiagnosticLayerPosture(payload);
        evidence.push(networkEvidenceRow(
          "diagnostic-layers",
          "Layer status",
          diagnosticPosture === "blocked" ? "blocked" : diagnosticPosture === "ready" ? "ready" : "review",
          networkDiagnosticLayerLines(payload).slice(0, 5).join("; "),
          diagnosticPosture === "blocked"
            ? "Resolve the blocked network layer before retrying distributed work."
            : "Use Test connection, Cluster Log, and worker row failure reasons to confirm layer evidence.",
          [
            ...networkDiagnosticLayerLines(payload),
            "Layer names are backend-owned evidence: url_reachable, auth_ok, paths_ok, queue_fresh, last_claim_result.",
          ],
        ));

        evidence.push(networkEvidenceRow(
          "persisted-worker-state",
          "Persisted worker state",
          payload.error ? "blocked" : problemRows ? "blocked" : warnings.length || (hasNetworkMode && !rows.length) || unknownRows ? "review" : "ready",
          `rows=${rows.length}; active=${activeRows}; idle=${idleRows}; problem=${problemRows}; unknown=${unknownRows}; warnings=${warnings.length}`,
          payload.error
            ? "Open Diagnostics and cluster.log before relying on network mode."
            : problemRows
              ? "Select problem worker rows, read Cluster Log / Last Stderr / ActiveJobs, and use backend lifecycle controls only after evidence agrees."
              : warnings.length || (hasNetworkMode && !rows.length)
                ? "Read warning text and compare backend Network diagnostics before starting distributed work."
                : "Persisted worker evidence has no visible blockers in this payload.",
          [
            `Source: ${payload.source || "runtime_state_files"}`,
            `Active/idle/session completed/session failed: ${payload.active_count || 0}/${payload.idle_count || 0}/${payload.session_completed || 0}/${payload.session_failed || 0}`,
            `Coordinator state file: ${payload.coordinator_inflight_path || "not resolved"}`,
            `Cluster log: ${payload.cluster_log_path || "not resolved"}`,
            ...networkStateFileCompactLines(payload.state_files || []),
            ...warnings.slice(0, 8).map((warning) => `Warning: ${warning}`),
          ],
        ));

        evidence.push(networkEvidenceRow(
          "local-worker-recovery",
          "Local worker recovery",
          pendingDone ? "pending report" : roleText === "worker" && !workerState.job_id && !workerState.source_file ? "review" : "ready",
          `job=${workerState.job_id || "none"}; file=${workerState.source_file || "none"}; pending done report=${pendingDone ? "yes" : "no"}`,
          pendingDone
            ? "Do not assume the last worker completion was accepted. Inspect worker_state, Cluster Log, and coordinator state from Diagnostics."
            : roleText === "worker" && !workerState.job_id && !workerState.source_file
              ? "Worker may be idle; compare with backend worker polling status and cluster.log before troubleshooting."
              : "No pending local worker recovery item is visible.",
          [
            `Worker state path: ${payload.worker_state_path || "not resolved"}`,
            `Job: ${workerState.job_id || "(none)"}`,
            `Source file: ${workerState.source_file || "(none)"}`,
            `Pending done report: ${pendingDone ? "yes" : "no"}`,
          ],
        ));

        evidence.push(networkEvidenceRow(
          "diagnostics-evidence",
          "Diagnostics evidence",
          hasDiagnosticsOpen ? "ready" : "review",
          `cluster log path=${payload.cluster_log_path || "not resolved"}; diagnostics open=${hasDiagnosticsOpen ? "available" : "missing"}`,
          hasDiagnosticsOpen
            ? "Read/open Cluster Log, Run Logs, ActiveJobs, and State before changing network role or retrying worker claims."
            : "Refresh Local API contract before using diagnostics actions.",
          [
            "Suggested read order: Cluster Log -> ActiveJobs -> Run Logs -> Last Stderr -> State Folder.",
            "Diagnostics target allowlists remain the source of truth for opening files/folders.",
          ],
        ));

        evidence.push(networkEvidenceRow(
          "mutation-boundary",
          "Mutation boundary",
          "ready",
            `Network page uses backend-owned lifecycle routes; lifecycle contracts=${lifecycleContracts.length}; dry-run routes=${networkLifecycleDryRunRouteCount(contract)}; confirmed lifecycle routes=${networkLifecycleMutationRouteCount(contract)}; setup write/secret routes=${networkSetupMutationRouteRows(contract).length}.`,
            "Use Network Lifecycle dry-runs before any confirmed coordinator/worker start or stop command.",
          [
            "This checklist cannot abort, reclaim, release, drain, publish, rename, save settings, rewrite state, or touch media files.",
            networkLifecycleContractSummary(contract),
            `Setup routes: ${networkSetupMutationRouteSummary(contract)}.`,
            "Changing network settings still requires Settings Save through backend-owned config routes.",
          ],
        ));

        return evidence;
      }

      function networkEvidenceSummaryLines(rows = []) {
        const counts = rows.reduce((acc, row) => {
          const key = networkEvidencePostureStatus(row.posture);
          acc[key] = (acc[key] || 0) + 1;
          return acc;
        }, {});
        const reviewRows = rows.filter((row) => networkEvidencePostureStatus(row.posture) !== "match");
        const lines = [
          "Network evidence checklist:",
          `Status: ${networkEvidenceStatus(rows)}`,
          `Rows: ${rows.length}; blocked=${counts.blocked || 0}; review=${counts.warning || 0}; ready=${counts.match || 0}.`,
          "Boundary: persisted worker state is visible through /api/network/workers; coordinator/worker lifecycle controls use backend-owned routes.",
        ];
        if (reviewRows.length) {
          lines.push("", "Rows needing attention:");
          reviewRows.slice(0, 6).forEach((row) => lines.push(`- ${row.checkpoint}: ${row.posture}; ${row.action}`));
        } else {
          lines.push("", "No network evidence review rows are visible in the loaded payload.");
        }
        return lines;
      }

      function getSelectedNetworkEvidenceRow(rows) {
        const selectedKey = getSelectedKey();
        if (!selectedKey) return null;
        return rows.find((row) => row.key === selectedKey) || null;
      }

      function renderNetworkEvidenceDetail(item) {
        if (!item) {
          setText("network-evidence-detail", "No network evidence row selected. Select a row to inspect role, persisted worker state, lifecycle boundary, diagnostics, and mutation guardrails.");
          return;
        }
        setText("network-evidence-detail", [
          `Checkpoint: ${item.checkpoint}`,
          `Posture: ${item.posture}`,
          `Evidence: ${item.evidence}`,
          `Safe next step: ${item.action}`,
          "",
          "Detail:",
          ...(Array.isArray(item.detail) && item.detail.length ? item.detail.map((line) => `- ${line}`) : ["- No additional detail."]),
        ].join("\n"));
      }

      function renderNetworkEvidenceChecklist(payload, role, config) {
        const rows = networkEvidenceRows({
          role,
          config,
          closeReadiness: payload.closeReadiness,
          snapshot: payload.snapshot,
          contract: payload.contract || {},
          networkWorkers: payload.networkWorkers || {},
        });
        setText("network-evidence-status", networkEvidenceStatus(rows));
        setText("network-evidence-summary", networkEvidenceSummaryLines(rows).join("\n"));
        const tbody = byId("network-evidence-rows");
        if (!tbody) return;
        if (!rows.length) {
          clearRows(tbody, 4, "No network evidence rows loaded.");
          updateTableStatusLegend("network-evidence-legend", tbody, "Network evidence rows");
          renderNetworkEvidenceDetail(null);
          return;
        }
        if (!rows.some((row) => row.key === getSelectedKey())) {
          setSelectedKey(rows[0].key);
        }
        tbody.replaceChildren();
        rows.forEach((item) => {
          const row = document.createElement("tr");
          row.dataset.rowKey = item.key;
          row.dataset.status = networkEvidencePostureStatus(item.posture);
          appendCells(row, [item.checkpoint, item.posture, item.evidence, item.action]);
          makeRowSelectable(row, () => {
            setSelectedKey(item.key);
            renderNetworkEvidenceChecklist(payload, role, config);
          }, {
            selected: item.key === getSelectedKey(),
            label: `Network evidence ${item.checkpoint}`,
          });
          tbody.appendChild(row);
        });
        updateTableStatusLegend("network-evidence-legend", tbody, "Network evidence rows");
        renderNetworkEvidenceDetail(getSelectedNetworkEvidenceRow(rows));
      }

    return { networkEvidenceRows, networkEvidenceStatus, networkEvidenceSummaryLines, renderNetworkEvidenceChecklist };
  }
  window.__networkEvidenceModule = { createNetworkEvidenceModule };
})();
