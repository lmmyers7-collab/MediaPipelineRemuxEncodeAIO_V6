// Network lifecycle command construction, dry-run gates, and confirmation flow.
(function () {
  "use strict";

  function createNetworkLifecycleCommandsModule(deps = {}) {
    // The injected route adapters originate from the network_lifecycle_contracts schema.
    const {
      apiPost = async () => ({}),
      byId = () => null,
      coordinatorTarget = () => "",
      networkLifecycleCommandResultLines = () => [],
      networkLifecycleDryRunAllowsConfirmed = () => false,
      networkLifecycleDryRunRequirementLine = () => "",
      networkLifecycleRoutePath = () => "",
      networkLifecycleStateFor = () => ({ status: "unknown" }),
      networkTestConnectionResultLines = () => [],
      networkTokenPostureLines = () => [],
      networkWorkerTestConnectionRoute = () => "",
      obviousWorkerCoordinatorUrlIssue = () => "",
      rememberNetworkLifecycleDryRun = () => {},
      renderNetworkActionReadinessGates = () => {},
      renderNetworkLifecycleControls = () => {},
      refreshAll = () => {},
      setText = () => {},
      settingsConfig = () => ({}),
      state = {},
      visibleNetworkModeLabel = () => "",
    } = deps;

  function networkLifecycleConfirmationLines({ role, action, route, payload, config }) {
    const networkWorkers = payload.networkWorkers || {};
    const roleState = networkLifecycleStateFor(networkWorkers, role);
    const workerState = networkWorkers.worker_state && typeof networkWorkers.worker_state === "object"
      ? networkWorkers.worker_state
      : {};
    const currentClaim = workerState.job_id || workerState.source_file || "none";
    const dryRunLine = networkLifecycleDryRunRequirementLine(payload, config, role, action);
    const lastDryRun = byId("network-lifecycle-command-result")?.textContent || "No recent dry-run result on this page.";
    const stopImpact = action === "stop"
      ? "Stop polling/new claims; active work is preserved for done reporting. Verify active claims before confirming."
      : "Starting begins backend-owned coordinator or worker lifecycle work.";
    return [
      `Role: ${role}`,
      `Action: ${action}`,
      `Route: ${route}`,
      `Saved mode: ${visibleNetworkModeLabel(config)}`,
      `Current lifecycle state: ${roleState.status}`,
      `Coordinator URL: ${coordinatorTarget(config, networkWorkers) || "not configured"}`,
      ...networkTokenPostureLines(networkWorkers),
      `Active claim impact: ${currentClaim}`,
      `Impact: ${stopImpact}`,
      dryRunLine,
      "No-touch summary: this dialog only sets the backend confirmation field. The backend still owns provider checks, lifecycle lock, command journal, and preconditions.",
      "",
      "Recent dry-run/status:",
      lastDryRun.trim().slice(0, 1200) || "No recent dry-run result on this page.",
    ];
  }

  function confirmNetworkLifecycleCommand({ role, action, route, payload, config }) {
    if (!networkLifecycleDryRunAllowsConfirmed(payload, config, role, action)) {
      return Promise.resolve(false);
    }
    const dialog = byId("network-lifecycle-confirm-dialog");
    const submit = byId("network-lifecycle-confirm-submit");
    const cancel = byId("network-lifecycle-confirm-cancel");
    if (!dialog || !submit || !cancel) return Promise.resolve(false);
    setText("network-lifecycle-confirm-designation", `${role} ${action}`);
    setText("network-lifecycle-confirm-summary", "Confirmed lifecycle commands are backend-owned, confirmation-gated, provider-guarded, and command-journaled.");
    setText("network-lifecycle-confirm-detail", networkLifecycleConfirmationLines({ role, action, route, payload, config }).join("\n"));
    return new Promise((resolve) => {
      let settled = false;
      const finish = (value) => {
        if (settled) return;
        settled = true;
        submit.onclick = null;
        cancel.onclick = null;
        dialog.oncancel = null;
        if (dialog.open && dialog.close) dialog.close();
        else dialog.removeAttribute("open");
        resolve(value);
      };
      submit.onclick = () => finish(true);
      cancel.onclick = () => finish(false);
      dialog.oncancel = (event) => {
        event.preventDefault();
        finish(false);
      };
      if (dialog.showModal && !dialog.open) dialog.showModal();
      else if (!dialog.open) dialog.setAttribute("open", "open");
      cancel.focus?.();
    });
  }

  function confirmNetworkSetupCommand({ designation, summary, detailLines }) {
    const dialog = byId("network-lifecycle-confirm-dialog");
    const submit = byId("network-lifecycle-confirm-submit");
    const cancel = byId("network-lifecycle-confirm-cancel");
    if (!dialog || !submit || !cancel) return Promise.resolve(false);
    setText("network-lifecycle-confirm-designation", designation || "Network setup");
    setText("network-lifecycle-confirm-summary", summary || "Confirm the backend-owned Network setup command before submitting.");
    setText("network-lifecycle-confirm-detail", (Array.isArray(detailLines) ? detailLines : [detailLines]).filter(Boolean).join("\n"));
    return new Promise((resolve) => {
      let settled = false;
      const finish = (value) => {
        if (settled) return;
        settled = true;
        submit.onclick = null;
        cancel.onclick = null;
        dialog.oncancel = null;
        if (dialog.open && dialog.close) dialog.close();
        else dialog.removeAttribute("open");
        resolve(value);
      };
      submit.onclick = () => finish(true);
      cancel.onclick = () => finish(false);
      dialog.oncancel = (event) => {
        event.preventDefault();
        finish(false);
      };
      if (dialog.showModal && !dialog.open) dialog.showModal();
      else if (!dialog.open) dialog.setAttribute("open", "open");
      cancel.focus?.();
    });
  }

  async function postNetworkRoute(route, request) {
    if (route) return apiPost(route, request);
    throw new Error("Unsupported Network route.");
  }

  async function postNetworkLifecycleRoute(contract, role, action, dryRun, request) {
    const route = networkLifecycleRoutePath(contract, role, action, dryRun);
    return postNetworkRoute(route, request);
  }

  async function runGuidedNetworkLifecycleCommand(button) {
    const role = button?.dataset?.networkLifecycleRole || "";
    const action = button?.dataset?.networkLifecycleAction || "";
    const contract = state.lifecyclePayload.contract || {};
    const config = settingsConfig(state.lifecyclePayload.settings || {});
    const networkWorkers = state.lifecyclePayload.networkWorkers || {};
    const dryRunRoute = networkLifecycleRoutePath(contract, role, action, true);
    if (!dryRunRoute) {
      setText("network-lifecycle-control-status", "Route missing");
      setText("network-lifecycle-command-result", "Backend lifecycle dry-run route is not available in the loaded contract.");
      return;
    }
    const urlIssue = role === "worker"
      ? obviousWorkerCoordinatorUrlIssue(coordinatorTarget(config, networkWorkers, { raw: true }), { required: true })
      : "";
    if (urlIssue) {
      setText("network-lifecycle-control-status", "Blocked");
      setText("network-lifecycle-command-result", `Worker coordinator URL is blocked before lifecycle dry-run submission: ${urlIssue}`);
      return;
    }
    setText("network-lifecycle-control-status", "Dry-running");
    setText("network-lifecycle-command-result", `Submitting ${dryRunRoute}...`);
    try {
      const dryRunResult = await postNetworkLifecycleRoute(contract, role, action, true, {
        reason: "webview_network_lifecycle_guided_dry_run",
      });
      rememberNetworkLifecycleDryRun(state.lifecyclePayload, config, role, action, dryRunResult);
      setText("network-lifecycle-command-result", networkLifecycleCommandResultLines(dryRunResult).join("\n"));
      renderNetworkLifecycleControls(state.lifecyclePayload, role, config);
      renderNetworkActionReadinessGates(state.lifecyclePayload, config);
      if (!networkLifecycleDryRunAllowsConfirmed(state.lifecyclePayload, config, role, action)) {
        setText("network-lifecycle-control-status", dryRunResult.ok ? "Dry-run review" : "Dry-run blocked");
        return;
      }
      const confirmRoute = networkLifecycleRoutePath(contract, role, action, false);
      if (!confirmRoute) {
        setText("network-lifecycle-control-status", "Route missing");
        setText(
          "network-lifecycle-command-result",
          [
            ...networkLifecycleCommandResultLines(dryRunResult),
            "",
            "Confirmed backend lifecycle route is not available in the loaded contract.",
          ].join("\n")
        );
        return;
      }
      const confirmed = await confirmNetworkLifecycleCommand({
        role,
        action,
        route: confirmRoute,
        payload: state.lifecyclePayload,
        config,
      });
      if (!confirmed) {
        setText("network-lifecycle-control-status", "Cancelled");
        setText("network-lifecycle-command-result", "Guided lifecycle command stopped after dry-run; confirmation was cancelled before the backend confirmation field was sent.");
        return;
      }
      const request = { reason: "webview_network_lifecycle_guided_confirmed" };
      request[action === "start" ? "confirm_start" : "confirm_stop"] = true;
      setText("network-lifecycle-control-status", "Running");
      setText("network-lifecycle-command-result", `Submitting ${confirmRoute}...`);
      const result = await postNetworkLifecycleRoute(contract, role, action, false, request);
      setText("network-lifecycle-command-result", networkLifecycleCommandResultLines(result).join("\n"));
      setText("network-lifecycle-control-status", result.ok ? "Command returned" : "Command blocked");
      renderNetworkLifecycleControls(state.lifecyclePayload, role, config);
      renderNetworkActionReadinessGates(state.lifecyclePayload, config);
      if (typeof refreshAll === "function") refreshAll({ automatic: false });
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setText("network-lifecycle-control-status", "Command failed");
      setText("network-lifecycle-command-result", [`Command route: ${dryRunRoute}`, `Error: ${message}`].join("\n"));
    }
  }

  async function runNetworkLifecycleCommand(button) {
    if (button?.dataset?.networkLifecycleGuided === "true") {
      return runGuidedNetworkLifecycleCommand(button);
    }
    const role = button?.dataset?.networkLifecycleRole || "";
    const action = button?.dataset?.networkLifecycleAction || "";
    const dryRun = button?.dataset?.networkLifecycleDryRun === "true";
    const contract = state.lifecyclePayload.contract || {};
    const config = settingsConfig(state.lifecyclePayload.settings || {});
    const networkWorkers = state.lifecyclePayload.networkWorkers || {};
    const route = networkLifecycleRoutePath(contract, role, action, dryRun);
    if (!route) {
      setText("network-lifecycle-control-status", "Route missing");
      setText("network-lifecycle-command-result", "Backend lifecycle route is not available in the loaded contract.");
      return;
    }
    const urlIssue = role === "worker"
      ? obviousWorkerCoordinatorUrlIssue(coordinatorTarget(config, networkWorkers, { raw: true }), { required: true })
      : "";
    if (urlIssue) {
      setText("network-lifecycle-control-status", "Blocked");
      setText("network-lifecycle-command-result", `Worker coordinator URL is blocked before lifecycle command submission: ${urlIssue}`);
      return;
    }
    if (!dryRun) {
      if (!networkLifecycleDryRunAllowsConfirmed(state.lifecyclePayload, config, role, action)) {
        setText("network-lifecycle-control-status", "Blocked");
        setText("network-lifecycle-command-result", networkLifecycleDryRunRequirementLine(state.lifecyclePayload, config, role, action));
        renderNetworkLifecycleControls(state.lifecyclePayload, role, config);
        renderNetworkActionReadinessGates(state.lifecyclePayload, config);
        return;
      }
      const confirmed = await confirmNetworkLifecycleCommand({
        role,
        action,
        route,
        payload: state.lifecyclePayload,
        config,
      });
      if (!confirmed) {
        setText("network-lifecycle-control-status", "Cancelled");
        setText("network-lifecycle-command-result", "Confirmed lifecycle command was cancelled before the backend confirmation field was sent.");
        return;
      }
    }
    const request = {
      reason: dryRun ? "webview_network_lifecycle_dry_run" : "webview_network_lifecycle_confirmed",
    };
    if (!dryRun) request[action === "start" ? "confirm_start" : "confirm_stop"] = true;
    setText("network-lifecycle-control-status", dryRun ? "Dry-running" : "Running");
    setText("network-lifecycle-command-result", `Submitting ${route}...`);
    try {
      const result = await postNetworkLifecycleRoute(contract, role, action, dryRun, request);
      if (dryRun) rememberNetworkLifecycleDryRun(state.lifecyclePayload, config, role, action, result);
      setText("network-lifecycle-command-result", networkLifecycleCommandResultLines(result).join("\n"));
      setText("network-lifecycle-control-status", result.ok ? "Command returned" : "Command blocked");
      renderNetworkLifecycleControls(state.lifecyclePayload, role, config);
      renderNetworkActionReadinessGates(state.lifecyclePayload, config);
      if (!dryRun && typeof refreshAll === "function") refreshAll({ automatic: false });
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setText("network-lifecycle-control-status", "Command failed");
      setText("network-lifecycle-command-result", [`Command route: ${route}`, `Error: ${message}`].join("\n"));
    }
  }

  async function runNetworkWorkerTestConnection(options = {}) {
    const render = options.render !== false;
    const contract = state.lifecyclePayload.contract || {};
    const route = networkWorkerTestConnectionRoute(contract);
    if (!route) {
      const result = {
        ok: false,
        severity: "warning",
        message: "Backend worker test-connection route is not available in the loaded contract.",
        data: {},
      };
      if (render) {
        setText("network-lifecycle-control-status", "Route missing");
        setText("network-lifecycle-command-result", result.message);
      }
      return result;
    }
    if (render) {
      setText("network-lifecycle-control-status", "Testing");
      setText("network-lifecycle-command-result", "Submitting worker test-connection preflight...");
    }
    try {
      const result = await postNetworkRoute(route, {});
      if (render) {
        setText("network-lifecycle-command-result", networkTestConnectionResultLines(result).join("\n"));
        setText("network-lifecycle-control-status", result.ok ? "Connection passed" : "Connection review");
        if (typeof refreshAll === "function") refreshAll({ automatic: false });
      }
      return result;
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      const result = {
        ok: false,
        severity: "error",
        message,
        data: {},
      };
      if (render) {
        setText("network-lifecycle-control-status", "Test failed");
        setText("network-lifecycle-command-result", [`Command route: ${route}`, `Error: ${message}`].join("\n"));
      }
      return result;
    }
  }
    return {
      networkLifecycleConfirmationLines,
      confirmNetworkLifecycleCommand,
      confirmNetworkSetupCommand,
      postNetworkRoute,
      postNetworkLifecycleRoute,
      runGuidedNetworkLifecycleCommand,
      runNetworkLifecycleCommand,
      runNetworkWorkerTestConnection,
    };
  }

  window.__networkLifecycleCommandsModule = { createNetworkLifecycleCommandsModule };
})();
