// Network status, topology, diagnostics, drift, and operator-attention projections.
(function () {
  "use strict";

  function createNetworkStatusModule(deps = {}) {
    const {
      byId = () => null,
      closeReadinessIsSafe = () => false,
      coordinatorTarget = () => "",
      networkDiagnosticLayerByKey = () => null,
      networkDiagnosticLayerPosture = () => "",
      networkDiagnosticLayers = () => ({ layers: [] }),
      networkLifecycleDryRunRecord = () => null,
      networkLifecycleRelevantRoles = () => [],
      networkRuntimeStatus = () => ({ label: "Not loaded" }),
      networkStateFileCompactLines = () => [],
      networkStateFileRows = () => [],
      networkStateFileStatus = () => "",
      networkStateFilesDiagnosticStatus = () => "",
      networkStatusTone = () => "",
      networkWorkerStatusState = () => "unknown",
      renderNetworkDiagnosticRail = () => {},
      setText = () => {},
      visibleNetworkMode = () => "",
      visibleNetworkModeLabel = () => "",
      workerHeartbeatText = () => "-",
    } = deps;
    const documentRef = deps.documentRef || document;

  function networkAttentionItems(networkWorkers = {}) {
    const items = [];
    const workerState = networkWorkers?.worker_state && typeof networkWorkers.worker_state === "object" ? networkWorkers.worker_state : {};
    if (workerState.pending_done_report) {
      items.push({
        key: "pending-done-report",
        label: "Pending done report",
        detail: `Local worker has pending_done_report for job ${workerState.job_id || "unknown"}.`,
        status: "blocked",
        source: "worker_state",
      });
    }
    const rows = Array.isArray(networkWorkers?.rows) ? networkWorkers.rows : [];
    rows.forEach((row) => {
      const status = networkWorkerStatusState(row);
      if (status === "blocked" || status === "warning") {
        const name = row.worker_name || row.worker_id || "Worker";
        items.push({
          key: `worker-${name}`,
          label: `${name}: ${status === "blocked" ? "blocked" : "review"}`,
          detail: row.last_failure_reason || row.last_failure_reason_code || row.error || row.current_stage || "Worker row needs review.",
          status,
          source: "worker row",
        });
      }
    });
    const drift = networkWorkerDriftPayload(networkWorkers);
    if (String(drift.status || "").toLowerCase() === "drift") {
      items.push({
        key: "running-vs-saved-drift",
        label: "Worker settings drift",
        detail: networkWorkerDriftSummaryLines(drift).join(" ") || "Running worker settings differ from saved config.",
        status: "warning",
        source: "running_vs_saved",
      });
    }
    networkStateFileRows(networkWorkers).forEach((row) => {
      const status = networkStateFileStatus(row);
      if (status === "blocked" || status === "warning") {
        items.push({
          key: `state-file-${row.key || row.label}`,
          label: `${row.label || row.key || "State file"}: ${row.status || "review"}`,
          detail: row.error || row.purpose || "State-file evidence needs review.",
          status,
          source: "state_files",
        });
      }
    });
    const warnings = Array.isArray(networkWorkers?.warnings) ? networkWorkers.warnings : [];
    warnings.slice(0, 6).forEach((warning, index) => {
      items.push({
        key: `warning-${index}`,
        label: "Network warning",
        detail: String(warning || ""),
        status: "warning",
        source: "warnings",
      });
    });
    const diagnostic = networkDiagnosticLayers(networkWorkers);
    (Array.isArray(diagnostic.layers) ? diagnostic.layers : []).forEach((layer) => {
      if (["blocked", "review", "warning"].includes(String(layer?.status || "").toLowerCase())) {
        items.push({
          key: `diagnostic-${layer.key || layer.label}`,
          label: layer.label || layer.key || "Diagnostic",
          detail: layer.detail || "Diagnostic layer needs review.",
          status: layer.status || "warning",
          source: "diagnostic_layers",
        });
      }
    });
    return items;
  }

  function renderNetworkAttentionStack(networkWorkers = {}) {
    const target = byId("network-attention-stack");
    if (!target) return;
    const items = networkAttentionItems(networkWorkers);
    target.replaceChildren();
    if (!items.length) {
      const item = documentRef.createElement("div");
      item.className = "network-attention-item";
      item.dataset.status = "match";
      item.innerHTML = "<strong>No attention items</strong><span>Worker state, diagnostics, drift, and state files have no loaded blockers.</span>";
      target.appendChild(item);
      return;
    }
    items.slice(0, 3).forEach((entry) => {
      const item = documentRef.createElement("div");
      item.className = "network-attention-item";
      item.dataset.status = networkStatusTone(entry.status);
      const heading = documentRef.createElement("strong");
      heading.textContent = entry.label || entry.key || "Attention item";
      const detail = documentRef.createElement("span");
      detail.textContent = entry.detail || entry.action_hint || "Inspect Network evidence before lifecycle action.";
      item.title = [entry.source, entry.action_hint].filter(Boolean).join(" - ");
      item.append(heading, detail);
      target.appendChild(item);
    });
    if (items.length > 3) {
      const overflow = documentRef.createElement("div");
      overflow.className = "network-attention-overflow";
      overflow.textContent = `+${items.length - 3} more in Advanced Evidence`;
      target.appendChild(overflow);
    }
  }

  function networkTopologyNodes(config = {}, networkWorkers = {}) {
    const nodes = [];
    const mode = visibleNetworkMode(config);
    const runtime = networkRuntimeStatus(networkWorkers, config);
    nodes.push({
      label: "Coordinator",
      value: coordinatorTarget(config, networkWorkers) || "not configured",
      status: mode === "standalone" ? "not_applicable" : runtime.severity || "unknown",
      detail: networkWorkers.cluster_log_path || "cluster log not resolved",
    });
    const workerState = networkWorkers?.worker_state && typeof networkWorkers.worker_state === "object" ? networkWorkers.worker_state : {};
    if (mode === "worker" || mode === "coordinator_local" || workerState.job_id || workerState.pending_done_report) {
      nodes.push({
        label: mode === "coordinator_local" ? "Local worker" : "Worker",
        value: workerState.job_id || workerState.source_file || "idle",
        status: workerState.pending_done_report ? "blocked" : workerState.job_id ? "running" : "ready",
        detail: workerState.source_file || networkWorkers.worker_state_path || "",
      });
    }
    const rows = Array.isArray(networkWorkers?.rows) ? networkWorkers.rows : [];
    rows.slice(0, 6).forEach((row) => {
      nodes.push({
        label: row.worker_name || row.worker_id || "Worker",
        value: row.current_file_name || row.current_stage || row.status || "idle",
        status: networkWorkerStatusState(row),
        detail: workerHeartbeatText(row),
      });
    });
    if (rows.length > 6) {
      nodes.push({ label: "More workers", value: `+${rows.length - 6}`, status: "unknown", detail: "Additional workers are visible in the Worker Board." });
    }
    return nodes;
  }

  function renderNetworkTopologyStrip(config = {}, networkWorkers = {}) {
    const target = byId("network-topology-strip");
    if (!target) return;
    target.replaceChildren();
    networkTopologyNodes(config, networkWorkers).forEach((entry) => {
      const node = documentRef.createElement("div");
      node.className = "network-topology-node";
      node.dataset.status = networkStatusTone(entry.status);
      node.title = entry.detail || "";
      const label = documentRef.createElement("span");
      label.textContent = entry.label || "Node";
      const value = documentRef.createElement("strong");
      value.textContent = entry.value || "-";
      node.append(label, value);
      target.appendChild(node);
    });
  }

  function setNetworkGate(label, status, detail = "") {
    const target = byId("network-action-readiness-gates");
    if (!target) return;
    const chip = documentRef.createElement("span");
    chip.dataset.status = networkStatusTone(status);
    chip.textContent = `${label}: ${status || "unknown"}`;
    chip.title = detail || `${label} readiness: ${status || "unknown"}`;
    target.appendChild(chip);
  }

  function renderNetworkActionReadinessGates(payload = {}, config = {}) {
    const target = byId("network-action-readiness-gates");
    if (!target) return;
    target.replaceChildren();
    const networkWorkers = payload.networkWorkers || {};
    const tcp = networkDiagnosticLayerByKey(networkWorkers, "url_reachable");
    const auth = networkDiagnosticLayerByKey(networkWorkers, "auth_ok");
    const paths = networkDiagnosticLayerByKey(networkWorkers, "paths_ok");
    const queue = networkDiagnosticLayerByKey(networkWorkers, "queue_fresh");
    setNetworkGate("TCP", tcp?.status || "unknown", tcp?.detail);
    setNetworkGate("Auth", auth?.status || "unknown", auth?.detail);
    setNetworkGate("Paths", paths?.status || "unknown", paths?.detail);
    setNetworkGate("State", networkStateFilesDiagnosticStatus(networkWorkers), networkStateFileCompactLines(networkStateFileRows(networkWorkers)).join("\n"));
    setNetworkGate("Queue", queue?.status || "unknown", queue?.detail);
    setNetworkGate("Close", closeReadinessIsSafe(payload.closeReadiness) ? "ready" : "blocked", payload.closeReadiness?.reason || payload.closeReadiness?.message || "");
    const roles = networkLifecycleRelevantRoles(config);
    const hasDryRun = roles.some((role) => ["start", "stop"].some((action) => networkLifecycleDryRunRecord(role, action)?.safeToApply === true));
    setNetworkGate("Dry-run", hasDryRun ? "ready" : "review", hasDryRun ? "A matching dry-run is cached for this session." : "Run Check & Start or Request Stop to cache backend dry-run evidence.");
  }

  function networkWorkerDriftPayload(networkWorkers) {
    const drift = networkWorkers?.running_vs_saved;
    return drift && typeof drift === "object" ? drift : {};
  }

  function networkWorkerDriftFieldText(drift) {
    const labels = Array.isArray(drift?.drift_field_labels) ? drift.drift_field_labels : [];
    const fields = Array.isArray(drift?.drift_fields) ? drift.drift_fields : [];
    const values = (labels.length ? labels : fields)
      .map((item) => String(item || "").trim())
      .filter(Boolean);
    return values.length ? values.join(", ") : "none";
  }

  function networkWorkerDriftStatusText(drift) {
    const status = String(drift?.status || "").trim().toLowerCase();
    if (status === "drift") return `Drift (${networkWorkerDriftFieldText(drift)})`;
    if (status === "match") return "Matches saved settings";
    if (status === "not_running") return "Worker not running";
    if (status === "unknown") return "Unknown";
    return status || "Not loaded";
  }

  function networkWorkerDriftSummaryLines(drift) {
    if (Array.isArray(drift?.summary_lines) && drift.summary_lines.length) {
      return drift.summary_lines.map((line) => String(line || "").trim()).filter(Boolean);
    }
    return [networkWorkerDriftStatusText(drift)];
  }

  function networkWorkerPolicyDivergencePayload(drift) {
    const payload = drift?.policy_divergence;
    return payload && typeof payload === "object" ? payload : {};
  }

  function networkWorkerPolicyDivergenceText(drift) {
    const payload = networkWorkerPolicyDivergencePayload(drift);
    const labels = Array.isArray(payload.field_labels) ? payload.field_labels : [];
    const fields = Array.isArray(payload.fields) ? payload.fields : [];
    const values = (labels.length ? labels : fields)
      .map((item) => String(item || "").trim())
      .filter(Boolean);
    return values.length ? values.join(", ") : "ready";
  }

  function networkWorkerPolicyDivergenceStatusText(drift) {
    const payload = networkWorkerPolicyDivergencePayload(drift);
    const status = String(payload.status || "").trim().toLowerCase();
    if (status === "review") return `Review (${networkWorkerPolicyDivergenceText(drift)})`;
    if (status === "ready") return "Ready";
    return status || "Not loaded";
  }

  function networkWorkerPolicyDivergenceActive(drift) {
    const status = String(networkWorkerPolicyDivergencePayload(drift).status || "").trim().toLowerCase();
    return status === "review" || status === "warning" || status === "blocked";
  }

  function networkWorkerPolicyDivergenceSummaryLines(drift) {
    const payload = networkWorkerPolicyDivergencePayload(drift);
    if (Array.isArray(payload.summary_lines) && payload.summary_lines.length) {
      return payload.summary_lines.map((line) => String(line || "").trim()).filter(Boolean);
    }
    return [networkWorkerPolicyDivergenceStatusText(drift)];
  }

  function renderNetworkStatusBanner(payload = {}, config = {}) {
    const networkWorkers = payload.networkWorkers || {};
    const runtime = networkRuntimeStatus(networkWorkers, config);
    const drift = networkWorkerDriftPayload(networkWorkers);
    const driftActive = String(drift.status || "").toLowerCase() === "drift";
    const policyReviewActive = networkWorkerPolicyDivergenceActive(drift);
    const modeLabel = visibleNetworkModeLabel(config);
    const target = coordinatorTarget(config, networkWorkers);
    const mode = visibleNetworkMode(config);
    const warnings = Array.isArray(networkWorkers.warnings) ? networkWorkers.warnings : [];
    const diagnosticPosture = networkDiagnosticLayerPosture(networkWorkers);
    const activeCount = Number(networkWorkers.active_count || 0);
    const idleCount = Number(networkWorkers.idle_count || 0);
    const launchReason = mode === "standalone"
      ? "Normal Launch available"
      : "Normal Launch blocked; use Network Lifecycle";
    const banner = byId("network-health-strip");
    const stripStatus = runtime.severity === "blocked" || diagnosticPosture === "blocked"
      ? "blocked"
      : (driftActive || policyReviewActive || diagnosticPosture === "review") ? "warning" : (runtime.severity || "unknown");
    if (banner) banner.dataset.status = stripStatus;
    const bannerStatus = driftActive ? "Running settings drift" : policyReviewActive ? "Coordinator policy review" : runtime.label;
    setText("network-status-banner-title", `${modeLabel} - ${bannerStatus}`);
    setText("network-health-drift", driftActive ? networkWorkerDriftStatusText(drift) : networkWorkerPolicyDivergenceStatusText(drift));
    setText("network-health-workers", `${Number.isFinite(activeCount) ? activeCount : 0} active / ${Number.isFinite(idleCount) ? idleCount : 0} idle`);
    const attentionCount = networkAttentionItems(networkWorkers).length;
    const alertCount = attentionCount || warnings.length
      + (driftActive ? 1 : 0)
      + (policyReviewActive ? 1 : 0)
      + (["review", "blocked"].includes(diagnosticPosture) ? 1 : 0);
    setText("network-health-alerts", alertCount ? `${alertCount} review` : "0");
    setText(
      "network-status-banner-detail",
      driftActive
        ? `${launchReason}. Running worker differs from saved: ${networkWorkerDriftFieldText(drift)}.`
        : policyReviewActive
          ? `${launchReason}. Coordinator policy authority needs review: ${networkWorkerPolicyDivergenceText(drift)}.`
        : `${launchReason}. Coordinator target: ${target || "not configured"}.`
    );
    const summaryLines = Array.isArray(networkWorkers.operator_summary_lines)
      ? networkWorkers.operator_summary_lines.map((line) => String(line || "").trim()).filter(Boolean)
      : [
          `Mode: ${modeLabel}.`,
          `Runtime: ${runtime.label}.`,
          `${launchReason}.`,
          `Coordinator target: ${target || "not configured"}.`,
        ];
    if (driftActive && !summaryLines.some((line) => line.toLowerCase().includes("worker settings drift"))) {
      summaryLines.push(...networkWorkerDriftSummaryLines(drift));
    }
    if (policyReviewActive && !summaryLines.some((line) => line.toLowerCase().includes("coordinator policy authority"))) {
      summaryLines.push(...networkWorkerPolicyDivergenceSummaryLines(drift));
    }
    setText("network-status-banner-lines", summaryLines.join("\n"));
    renderNetworkDiagnosticRail(networkWorkers);
    renderNetworkAttentionStack(networkWorkers);
  }
    return {
      networkAttentionItems,
      renderNetworkAttentionStack,
      networkTopologyNodes,
      renderNetworkTopologyStrip,
      setNetworkGate,
      renderNetworkActionReadinessGates,
      networkWorkerDriftPayload,
      networkWorkerDriftFieldText,
      networkWorkerDriftStatusText,
      networkWorkerDriftSummaryLines,
      networkWorkerPolicyDivergencePayload,
      networkWorkerPolicyDivergenceText,
      networkWorkerPolicyDivergenceStatusText,
      networkWorkerPolicyDivergenceActive,
      networkWorkerPolicyDivergenceSummaryLines,
      renderNetworkStatusBanner,
    };
  }

  window.__networkStatusModule = { createNetworkStatusModule };
})();

