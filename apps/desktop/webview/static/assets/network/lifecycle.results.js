// Network lifecycle, discovery, and join-result evidence presentation.
(function () {
  "use strict";

  function createNetworkLifecycleResultsModule(deps = {}) {
    const {
      byId = () => null,
      renderNetworkJoinControls = () => {},
      setText = () => {},
      settingsConfig = () => ({}),
      state = {},
      windowRef = window,
    } = deps;
    const documentRef = deps.documentRef || document;

  function networkLifecycleCommandResultLines(result) {
    const data = result?.data && typeof result.data === "object" ? result.data : {};
    const preconditions = Array.isArray(data.precondition_results) ? data.precondition_results : [];
    const blocked = preconditions.filter((row) => String(row?.status || "").toLowerCase() === "blocked");
    const passed = preconditions.filter((row) => String(row?.status || "").toLowerCase() === "pass");
    const isDryRun = data.dry_run_only === true;
    const stateAfterStatus = String(data.state_after?.status || "").toLowerCase();
    const activeWorkPreserved = data.active_work_preserved === true || stateAfterStatus === "active_work_preserved";
    const lines = isDryRun
      ? [
          "Check complete. This was a dry-run only.",
          "Effect: none.",
          "No files, queue, scratch, output, pending publish, or lifecycle state changed.",
        ]
      : [
          activeWorkPreserved
            ? "Stop requested. Active work is preserved for done reporting; backend command journal evidence was required before runtime state changed."
            : result?.ok
            ? "Confirmed command completed. Backend command journal evidence was required before runtime state changed."
            : "Confirmed command was blocked or failed. No fallback to normal Launch was attempted.",
        ];
    lines.push(
      `Command: ${result?.command || "network lifecycle"}`,
      `Result: ${result?.ok ? "ok" : "blocked"}`,
      `Severity: ${result?.severity || "unknown"}`,
      `Message: ${result?.message || "(none)"}`,
    );
    if (typeof data.safe_to_apply === "boolean") lines.push(`Safe to apply: ${data.safe_to_apply ? "yes" : "no"}`);
    if (data.effect) lines.push(`Backend effect: ${data.effect}`);
    if (data.schema_version) lines.push(`Data schema: ${data.schema_version}`);
    if (data.command_id) lines.push(`Command ID: ${data.command_id}`);
    if (passed.length) {
      lines.push("", "Passed preconditions:");
      passed.slice(0, 8).forEach((row) => lines.push(`- ${row.key || "precondition"}: ${row.evidence || ""}`));
    }
    if (blocked.length) {
      lines.push("", "Blocked preconditions:");
      blocked.slice(0, 8).forEach((row) => lines.push(`- ${row.key || "precondition"}: ${row.evidence || ""}`));
    }
    const activeWork = activeWorkPreserved
      ? data.post_action_active_work || data.state_after?.active_work || {}
      : {};
    if (activeWorkPreserved && activeWork && typeof activeWork === "object") {
      const activeJobs = Array.isArray(activeWork.active_jobs) ? activeWork.active_jobs : [];
      lines.push(
        "",
        "Active work preserved:",
        `- Active jobs: ${activeWork.active_job_count || activeJobs.length || 0}`,
        `- Local active jobs: ${activeWork.local_active_job_count || 0}`,
        `- Remote active claims: ${activeWork.remote_active_claim_count || 0}`,
        "- Effect: stopped polling/new claims; preserved active work must finish and report done through backend lifecycle."
      );
      activeJobs.slice(0, 5).forEach((job) => {
        const label = job.source_name || job.job_id || "active job";
        lines.push(`- ${label}: ${job.source || "backend evidence"}`);
      });
    }
    const errors = Array.isArray(result?.errors) ? result.errors : [];
    if (errors.length) {
      lines.push("", "Errors:");
      errors.slice(0, 8).forEach((error) => lines.push(`- ${error}`));
    }
    const noTouch = data.would_not_touch && typeof data.would_not_touch === "object" ? data.would_not_touch : {};
    const noTouchKeys = Object.keys(noTouch);
    if (noTouchKeys.length) {
      lines.push("", "Would not touch:");
      noTouchKeys.slice(0, 8).forEach((key) => lines.push(`- ${key}: ${noTouch[key]}`));
    }
    const redactedConfig = data.redacted_config_evidence && typeof data.redacted_config_evidence === "object"
      ? data.redacted_config_evidence
      : {};
    const configKeys = Object.keys(redactedConfig);
    if (configKeys.length) {
      lines.push("", "Redacted config evidence:");
      configKeys.slice(0, 10).forEach((key) => {
        const normalized = String(key).toLowerCase();
        const label = normalized.includes("authtoken")
          ? normalized.includes("worker") ? "Worker token" : "Coordinator token"
          : key;
        const rawValue = redactedConfig[key];
        const value = normalized.includes("authtoken")
          ? String(rawValue || "").replace("present_redacted", "present, hidden").replace("will_generate_on_start", "blank; coordinator can generate").replace("missing", "missing")
          : rawValue;
        lines.push(`- ${label}: ${value}`);
      });
    }
    if (data.state_before || data.state_after) {
      lines.push("", "Lifecycle state:");
      if (data.state_before) lines.push(`- Before: ${JSON.stringify(data.state_before)}`);
      if (data.state_after) lines.push(`- After: ${JSON.stringify(data.state_after)}`);
    }
    lines.push(
      "",
      result?.ok
        ? "Next action: refresh Network status and verify worker heartbeat/claim evidence before changing roles or running another lifecycle command."
        : "Next action: fix blocked preconditions, run the dry-run again, then use confirmed controls only when the backend reports safe_to_apply."
    );
    return lines;
  }

  function networkTestConnectionResultLines(result) {
    const data = result?.data && typeof result.data === "object" ? result.data : {};
    const layers = data.layers && typeof data.layers === "object" ? data.layers : {};
    const lines = [
      "Worker test-connection complete.",
      "Effect: none.",
      "No files, queue, scratch, output, pending publish, lifecycle state, or media policy changed.",
      `Result: ${result?.ok ? "ok" : "blocked"}`,
      `Severity: ${result?.severity || "unknown"}`,
      `Message: ${result?.message || "(none)"}`,
      `Coordinator URL: ${data.coordinator_url || "not configured"}`,
      `Data schema: ${data.schema_version || "unknown"}`,
    ];
    ["l1_tcp", "l2_auth", "l3_paths"].forEach((key) => {
      const layer = layers[key] && typeof layers[key] === "object" ? layers[key] : {};
      if (!Object.keys(layer).length) return;
      lines.push(
        "",
        `${layer.label || key}: ${layer.status || "unknown"}`,
        `- Detail: ${layer.detail || "(none)"}`
      );
      if (layer.status_code) lines.push(`- HTTP status: ${layer.status_code}`);
      if (key === "l3_paths" && Array.isArray(layer.paths)) {
        lines.push("- Paths:");
        layer.paths.slice(0, 12).forEach((row) => {
          lines.push(`  - ${row.library_id || "library"} ${row.path_kind || "path"}: ${row.status || "unknown"} (${row.path || ""})`);
        });
      }
    });
    const errors = Array.isArray(result?.errors) ? result.errors : [];
    if (errors.length) {
      lines.push("", "Blocked layer(s):");
      errors.slice(0, 8).forEach((error) => lines.push(`- ${error}`));
    }
    const noTouch = data.would_not_touch && typeof data.would_not_touch === "object" ? data.would_not_touch : {};
    const keys = Object.keys(noTouch);
    if (keys.length) {
      lines.push("", "Would not touch:");
      keys.slice(0, 10).forEach((key) => lines.push(`- ${key}: ${noTouch[key]}`));
    }
    lines.push(
      "",
      result?.ok
        ? "Next action: start or restart worker polling only after the Network status still matches saved settings."
        : "Next action: fix the failed TCP, auth, or path layer, then run Test worker connection again before starting worker polling."
    );
    return lines;
  }

  function networkCoordinatorDiscoveryResultLines(result) {
    const data = result?.data && typeof result.data === "object" ? result.data : {};
    const coordinators = Array.isArray(data.coordinators) ? data.coordinators : [];
    const lines = [
      "mDNS coordinator discovery complete.",
      "Effect: none.",
      "No files, queue, scratch, output, pending publish, lifecycle state, settings, or media policy changed.",
      `Result: ${result?.ok ? "ok" : "blocked"}`,
      `Severity: ${result?.severity || "unknown"}`,
      `Message: ${result?.message || "(none)"}`,
      `Selectable coordinators: ${coordinators.length}`,
      `Zeroconf available: ${data.zeroconf_available === false ? "no" : "yes"}`,
      `Data schema: ${data.schema_version || "unknown"}`,
    ];
    coordinators.slice(0, 8).forEach((row, index) => {
      lines.push(`- ${index + 1}. ${row.url || "unknown"} (${row.host || "host unknown"}:${row.port || "port unknown"})`);
    });
    const warnings = Array.isArray(result?.warnings) ? result.warnings : [];
    if (warnings.length) {
      lines.push("", "Warnings:");
      warnings.slice(0, 8).forEach((warning) => lines.push(`- ${warning}`));
    }
    const errors = Array.isArray(result?.errors) ? result.errors : [];
    if (errors.length) {
      lines.push("", "Errors:");
      errors.slice(0, 8).forEach((error) => lines.push(`- ${error}`));
    }
    lines.push(
      "",
      coordinators.length
        ? "Next action: choose Use for the intended coordinator, then preview/save Distributed Settings before starting worker polling."
        : "Next action: verify the coordinator is running on the LAN, firewall/mDNS is allowed, or use a join blob/manual WorkerCoordinatorUrl."
    );
    return lines;
  }

  function renderNetworkCoordinatorDiscoveryList(result) {
    const container = byId("network-worker-discovery-list");
    if (!container) return;
    container.textContent = "";
    const data = result?.data && typeof result.data === "object" ? result.data : {};
    const coordinators = Array.isArray(data.coordinators) ? data.coordinators : [];
    if (!coordinators.length) {
      const empty = documentRef.createElement("p");
      empty.className = "note";
      empty.textContent = "No mDNS coordinators discovered.";
      container.appendChild(empty);
      return;
    }
    coordinators.forEach((row) => {
      const url = String(row?.url || "").trim();
      if (!url) return;
      const item = documentRef.createElement("div");
      item.className = "network-discovery-row";
      item.setAttribute("role", "listitem");
      const detail = documentRef.createElement("div");
      detail.className = "network-discovery-url";
      detail.textContent = url;
      const button = documentRef.createElement("button");
      button.type = "button";
      button.className = "secondary-button";
      button.textContent = "Use";
      button.dataset.networkDiscoveryUrl = url;
      button.title = "Stage this discovered coordinator URL for WorkerCoordinatorUrl.";
      item.append(detail, button);
      container.appendChild(item);
    });
  }

  function stageDiscoveredCoordinatorUrl(url) {
    const text = String(url || "").trim();
    if (!text) return false;
    const roleSelect = byId("settings-network-role");
    if (roleSelect) {
      roleSelect.value = "worker";
      roleSelect.dispatchEvent(new Event("input", { bubbles: true }));
    }
    ["settings-network-worker-url", "network-role-setup-worker-url"].forEach((id) => {
      const input = byId(id);
      if (!input) return;
      input.value = text;
      input.dispatchEvent(new Event("input", { bubbles: true }));
    });
    const settingsView = windowRef.mediaPipelineSettingsView || {};
    settingsView.markNetworkSettingsBuilderDirty?.();
    const staged = settingsView.applyNetworkSettingsBuilderToPatch?.() !== false;
    setText("network-worker-discovery-status", staged ? "Coordinator staged" : "Review staged URL");
    setText(
      "network-worker-discovery-result",
      [
        `Selected coordinator: ${text}`,
        staged
          ? "WorkerCoordinatorUrl was staged into the Settings patch JSON."
          : "WorkerCoordinatorUrl was filled, but the network settings patch could not be staged.",
        "Preview/save Distributed Settings before starting worker polling.",
      ].join("\n")
    );
    renderNetworkJoinControls(state.lifecyclePayload, settingsConfig(state.lifecyclePayload.settings || {}));
    return staged;
  }

  function networkJoinBlobResultLines(result) {
    const data = result?.data && typeof result.data === "object" ? result.data : {};
    const lines = [
      "Coordinator join blob created.",
      "The blob contains a worker auth secret and is intentionally not written to command history.",
      `Result: ${result?.ok ? "ok" : "blocked"}`,
      `Severity: ${result?.severity || "unknown"}`,
      `Message: ${result?.message || "(none)"}`,
      `Coordinator URL: ${data.coordinator_url || "not configured"}`,
      `Token fingerprint: ${data.token_fingerprint || "hidden"}`,
      `Token source: ${data.token_source || "unknown"}`,
      `Libraries: ${data.library_count ?? 0}`,
      `Data schema: ${data.schema_version || "unknown"}`,
    ];
    const warnings = Array.isArray(result?.warnings) ? result.warnings : [];
    if (warnings.length) {
      lines.push("", "Warnings:");
      warnings.slice(0, 6).forEach((warning) => lines.push(`- ${warning}`));
    }
    const errors = Array.isArray(result?.errors) ? result.errors : [];
    if (errors.length) {
      lines.push("", "Errors:");
      errors.slice(0, 6).forEach((error) => lines.push(`- ${error}`));
    }
    lines.push("", "Next action: transfer the blob to the worker Join Cluster box, then import and verify test-connection.");
    return lines;
  }

  function networkJoinImportResultLines(result) {
    const data = result?.data && typeof result.data === "object" ? result.data : {};
    const settingsSave = data.settings_save && typeof data.settings_save === "object" ? data.settings_save : {};
    const joinPlan = data.join_plan && typeof data.join_plan === "object" ? data.join_plan : {};
    const testResult = data.test_connection && typeof data.test_connection === "object" ? data.test_connection : {};
    const lines = [
      "Worker join import complete.",
      "Effect: backend config-write through the Network join route; this is not staged-only Settings JSON.",
      "Lifecycle: worker polling was not started.",
      "The request blob contains a worker auth secret and is intentionally not written to command history.",
      `Result: ${result?.ok ? "ok" : "blocked"}`,
      `Severity: ${result?.severity || "unknown"}`,
      `Message: ${result?.message || "(none)"}`,
      `Coordinator URL: ${data.coordinator_url || "not configured"}`,
      `Token fingerprint: ${data.token_fingerprint || "hidden"}`,
      `Settings save: ${settingsSave.status || (settingsSave.ok ? "saved" : "blocked")}`,
      `Changed keys: ${Array.isArray(settingsSave.changed_keys) && settingsSave.changed_keys.length ? settingsSave.changed_keys.join(", ") : "none"}`,
      `Libraries advertised: ${data.library_count ?? joinPlan.library_count ?? 0}`,
      `Auto path-map entries: ${joinPlan.auto_path_map_entries ?? 0}`,
      `Effective path-map entries: ${joinPlan.effective_path_map_entries ?? 0}`,
      `Test connection: ${testResult.ok ? "passed" : "review"}`,
    ];
    const errors = Array.isArray(result?.errors) ? result.errors : [];
    if (errors.length) {
      lines.push("", "Errors:");
      errors.slice(0, 8).forEach((error) => lines.push(`- ${error}`));
    }
    if (testResult.data) {
      lines.push("", ...networkTestConnectionResultLines(testResult).slice(0, 18));
    }
    lines.push(
      "",
      result?.ok
        ? "Next action: refresh Network status, then start worker polling only after saved/running settings still match."
        : "Next action: fix the blocked settings, TCP, auth, or path layer before starting worker polling."
    );
    return lines;
  }
    return {
      networkLifecycleCommandResultLines,
      networkTestConnectionResultLines,
      networkCoordinatorDiscoveryResultLines,
      renderNetworkCoordinatorDiscoveryList,
      stageDiscoveredCoordinatorUrl,
      networkJoinBlobResultLines,
      networkJoinImportResultLines,
    };
  }

  window.__networkLifecycleResultsModule = { createNetworkLifecycleResultsModule };
})();

