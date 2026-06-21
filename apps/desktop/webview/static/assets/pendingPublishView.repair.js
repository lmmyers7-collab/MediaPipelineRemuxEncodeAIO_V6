(function () {
  function createPendingPublishRepairModule(deps = {}) {
    const {
      apiPost = async function () { throw new Error("apiPost unavailable"); },
      appendCommandResult = function () {},
      byId = function () { return null; },
      commandHistoryCompactEvidenceLine = null,
      getCommandHistory = function () { return []; },
      getSelectedPendingRow = function () { return null; },
      pendingRowKey = function (row) { return row?.row_key || ""; },
      renderCompactCommandHistoryBlock = null,
      setText = function () {},
    } = deps;

    const COMMAND = "pending_publish.repair_manifest";
    const DRY_RUN_COMMAND = "pending_publish.repair_manifest_dry_run";
    const ORPHAN_COMMAND = "pending_publish.reconcile_orphan_payloads";
    const ORPHAN_DRY_RUN_COMMAND = "pending_publish.reconcile_orphan_payloads_dry_run";
    let eventsInitialized = false;
    let inFlight = false;
    let lastDryRunResult = null;
    let lastDryRunRowKey = "";
    let orphanInFlight = false;
    let lastOrphanDryRunResult = null;
    let lastOrphanDryRunRowKey = "";

    function selectedRowKey(row = getSelectedPendingRow()) {
      const direct = String(row?.row_key || "").trim();
      if (direct) return direct;
      return String(pendingRowKey(row) || "").trim();
    }

    function repairResultData(result) {
      return result?.data && typeof result.data === "object" ? result.data : {};
    }

    function repairSelectedKeys(data) {
      return Array.isArray(data?.selected_row_keys) ? data.selected_row_keys.map((item) => String(item || "").trim()).filter(Boolean) : [];
    }

    function dryRunIsSafeForSelection(result, resultRowKey, command, row = getSelectedPendingRow()) {
      const rowKey = selectedRowKey(row);
      const data = repairResultData(result);
      const selectedKeys = repairSelectedKeys(data);
      return Boolean(
        rowKey
        && resultRowKey === rowKey
        && data.candidate_command === command
        && data.safe_to_apply === true
        && data.dry_run_fingerprint
        && (!selectedKeys.length || selectedKeys.includes(rowKey))
      );
    }

    function pendingRepairDryRunIsSafeForSelection(row = getSelectedPendingRow()) {
      return dryRunIsSafeForSelection(lastDryRunResult, lastDryRunRowKey, COMMAND, row);
    }

    function pendingOrphanDryRunIsSafeForSelection(row = getSelectedPendingRow()) {
      return dryRunIsSafeForSelection(lastOrphanDryRunResult, lastOrphanDryRunRowKey, ORPHAN_COMMAND, row);
    }

    function setPendingRepairManifestBusy(isBusy) {
      inFlight = Boolean(isBusy);
      renderPendingRepairManifestControls();
    }

    function setPendingRepairOrphanBusy(isBusy) {
      orphanInFlight = Boolean(isBusy);
      renderPendingRepairOrphanControls();
    }

    function clearStaleDryRunIfSelectionChanged(row = getSelectedPendingRow()) {
      const rowKey = selectedRowKey(row);
      if (lastDryRunResult && lastDryRunRowKey !== rowKey) {
        lastDryRunResult = null;
        lastDryRunRowKey = "";
      }
      if (lastOrphanDryRunResult && lastOrphanDryRunRowKey !== rowKey) {
        lastOrphanDryRunResult = null;
        lastOrphanDryRunRowKey = "";
      }
    }

    function repairMutationGuardrailLine() {
      return "Mutation guardrail: this control sends only backend route intent. It never sends paths, patches, raw manifests, payload movement, delete requests, drain requests, publish requests, or source-media actions.";
    }

    function repairDefaultLines(row) {
      const rowKey = selectedRowKey(row);
      if (!rowKey) {
        return [
          "No pending publish row selected.",
          "Select one pending row, then run the backend pending manifest repair dry-run.",
          "Apply remains disabled until the backend returns a matching safe dry-run fingerprint.",
          repairMutationGuardrailLine(),
          "Orphan-payload reconciliation remains blocked here until backend evidence supplies complete manifest fields.",
        ];
      }
      return [
        "Selected-row pending manifest repair:",
        `Row key: ${rowKey}`,
        "Step 1: run the backend dry-run for this selected row.",
        "Step 2: apply only when the current dry-run reports safe_to_apply=true and supplies a matching dry_run_fingerprint.",
        repairMutationGuardrailLine(),
        "No repair result is loaded for this selection yet.",
      ];
    }

    function orphanDefaultLines(row) {
      const rowKey = selectedRowKey(row);
      if (!rowKey) {
        return [
          "No pending publish row selected.",
          "Select one orphan payload row, then run the backend orphan-payload reconcile dry-run.",
          "Apply remains disabled until the backend returns a complete manifest proposal and matching safe dry-run fingerprint.",
          repairMutationGuardrailLine(),
        ];
      }
      return [
        "Selected-row orphan payload reconcile:",
        `Row key: ${rowKey}`,
        "Step 1: run the backend dry-run for this selected orphan payload row.",
        "Step 2: apply only when the current dry-run reports safe_to_apply=true and supplies a matching dry_run_fingerprint.",
        "Backend dry-runs may report blocked when pending_push_manifest.v1 source or destination evidence is missing.",
        repairMutationGuardrailLine(),
        "No orphan reconcile result is loaded for this selection yet.",
      ];
    }

    function repairDiffSummaryLines(diff) {
      if (!diff || typeof diff !== "object") return ["Diff summary: not reported"];
      return [
        "Diff summary:",
        `- Schema: ${diff.schema_version || "not reported"}`,
        `- Candidate rows: ${diff.candidate_count ?? diff.row_count ?? "not reported"}`,
        `- Would write paths: ${diff.would_write_count ?? "not reported"}`,
        `- Would move paths: ${diff.would_move_count ?? "not reported"}`,
        `- Would delete paths: ${diff.would_delete_count ?? "not reported"}`,
      ];
    }

    function repairWouldNotTouchLines(data) {
      const evidence = data?.would_not_touch && typeof data.would_not_touch === "object" ? data.would_not_touch : {};
      const keys = Object.keys(evidence).sort();
      if (!keys.length) return ["Source/payload/output unchanged evidence: not reported"];
      return [
        "Source/payload/output unchanged evidence:",
        ...keys.slice(0, 8).map((key) => `- ${key}: ${String(evidence[key])}`),
        keys.length > 8 ? `- ${keys.length - 8} more field(s) not shown.` : "",
      ].filter(Boolean);
    }

    function pendingRepairManifestResultLines(result) {
      const data = repairResultData(result || {});
      const selectedKeys = repairSelectedKeys(data);
      const warnings = Array.isArray(result?.warnings) ? result.warnings.filter(Boolean) : [];
      const errors = Array.isArray(result?.errors) ? result.errors.filter(Boolean) : [];
      const lines = [
        result?.message || "No pending manifest repair result.",
        `Schema: ${data.schema_version || "not reported"}`,
        `Command: ${data.candidate_command || result?.command || "not reported"}`,
        `Effect: ${data.effect || "not reported"}`,
        `Scope: ${data.scope || "unknown"}`,
        `Selected row keys: ${selectedKeys.join(", ") || "not reported"}`,
        `Safe to apply: ${data.safe_to_apply === true ? "yes" : "no"}`,
        `Applied: ${data.applied === true ? "yes" : data.applied === false ? "no" : "not reported"}`,
        `Blocked: ${data.blocked === true ? "yes" : data.blocked === false ? "no" : "not reported"}`,
        `Dry-run fingerprint: ${data.dry_run_fingerprint || "not reported"}`,
        `Expected fingerprint: ${data.expected_dry_run_fingerprint || "not reported"}`,
        "",
        ...repairDiffSummaryLines(data.diff_summary),
        "",
        ...repairWouldNotTouchLines(data),
        "",
        repairMutationGuardrailLine(),
      ];
      if (warnings.length) lines.push("", "Warning(s):", ...warnings.slice(0, 5).map((warning) => `- ${warning}`));
      if (errors.length) lines.push("", "Error(s):", ...errors.slice(0, 5).map((error) => `- ${error}`));
      return lines;
    }

    function pendingRepairManifestStatus(result = lastDryRunResult) {
      if (inFlight) return "Repair request running";
      const row = getSelectedPendingRow();
      if (!selectedRowKey(row)) return "No row selected";
      const data = repairResultData(result || {});
      if (!result) return "Dry-run required";
      if (data.applied === true) return "Applied";
      if (data.blocked === true || result?.ok === false) return "Blocked";
      if (pendingRepairDryRunIsSafeForSelection(row)) return "Dry-run safe";
      return "Review dry-run";
    }

    function pendingRepairOrphanStatus(result = lastOrphanDryRunResult) {
      if (orphanInFlight) return "Reconcile request running";
      const row = getSelectedPendingRow();
      if (!selectedRowKey(row)) return "No row selected";
      const data = repairResultData(result || {});
      if (!result) return "Dry-run required";
      if (data.applied === true) return "Applied";
      if (data.blocked === true || result?.ok === false) return "Blocked";
      if (pendingOrphanDryRunIsSafeForSelection(row)) return "Dry-run safe";
      return "Review dry-run";
    }

    function renderPendingRepairManifestControls(result = lastDryRunResult) {
      const row = getSelectedPendingRow();
      clearStaleDryRunIfSelectionChanged(row);
      const rowKey = selectedRowKey(row);
      const dryRunButton = byId("pending-repair-manifest-dry-run-button");
      const applyButton = byId("pending-repair-manifest-apply-button");
      const safeToApply = pendingRepairDryRunIsSafeForSelection(row);
      if (dryRunButton) {
        dryRunButton.disabled = inFlight || !rowKey;
        dryRunButton.title = rowKey
          ? "Run backend pending manifest repair dry-run for the selected row."
          : "Select a pending publish row before running repair dry-run.";
      }
      if (applyButton) {
        applyButton.disabled = inFlight || !safeToApply;
        applyButton.title = safeToApply
          ? "Apply backend-validated pending manifest repair for the selected row."
          : "Run a safe backend dry-run for the selected row before applying.";
      }
      setText("pending-repair-manifest-status", pendingRepairManifestStatus(result));
      setText(
        "pending-repair-manifest-detail",
        result ? pendingRepairManifestResultLines(result).join("\n") : repairDefaultLines(row).join("\n"),
      );
    }

    function renderPendingRepairOrphanControls(result = lastOrphanDryRunResult) {
      const row = getSelectedPendingRow();
      clearStaleDryRunIfSelectionChanged(row);
      const rowKey = selectedRowKey(row);
      const dryRunButton = byId("pending-reconcile-orphan-dry-run-button");
      const applyButton = byId("pending-reconcile-orphan-apply-button");
      const safeToApply = pendingOrphanDryRunIsSafeForSelection(row);
      if (dryRunButton) {
        dryRunButton.disabled = orphanInFlight || !rowKey;
        dryRunButton.title = rowKey
          ? "Run backend orphan-payload reconcile dry-run for the selected row."
          : "Select an orphan payload row before running reconcile dry-run.";
      }
      if (applyButton) {
        applyButton.disabled = orphanInFlight || !safeToApply;
        applyButton.title = safeToApply
          ? "Apply backend-validated orphan payload manifest reconcile for the selected row."
          : "Run a safe backend orphan-payload reconcile dry-run for the selected row before applying.";
      }
      setText("pending-reconcile-orphan-status", pendingRepairOrphanStatus(result));
      setText(
        "pending-reconcile-orphan-detail",
        result ? pendingRepairManifestResultLines(result).join("\n") : orphanDefaultLines(row).join("\n"),
      );
    }

    function isPendingRepairManifestCommand(entry) {
      const command = String(entry?.command || entry?.raw?.command || "").toLowerCase();
      return command === DRY_RUN_COMMAND || command === COMMAND;
    }

    function isPendingRepairOrphanCommand(entry) {
      const command = String(entry?.command || entry?.raw?.command || "").toLowerCase();
      return command === ORPHAN_DRY_RUN_COMMAND || command === ORPHAN_COMMAND;
    }

    function pendingRepairManifestHistoryLine(entry) {
      const raw = entry?.raw && typeof entry.raw === "object" ? entry.raw : {};
      const data = raw.data && typeof raw.data === "object" ? raw.data : {};
      const detail = ` (scope=${data.scope || raw.request?.scope || "unknown"}; safe=${data.safe_to_apply === true ? "yes" : "no"}; applied=${data.applied === true ? "yes" : "no"})`;
      if (typeof commandHistoryCompactEvidenceLine === "function") {
        return commandHistoryCompactEvidenceLine(entry, {
          label: String(raw.command || entry?.command || COMMAND),
          detail,
        });
      }
      const status = entry?.result || (entry?.ok ? "ok" : entry?.severity || "unknown");
      const local = entry?.local ? "local" : "journal";
      return `${entry?.at || ""} ${raw.command || entry?.command || COMMAND} [${status}; ${local}] ${entry?.message || ""}${detail}`.trim();
    }

    function renderPendingRepairManifestHistory(entries = getCommandHistory()) {
      if (typeof renderCompactCommandHistoryBlock === "function") {
        renderCompactCommandHistoryBlock({
          history: entries,
          filter: isPendingRepairManifestCommand,
          limit: 5,
          targetId: "pending-repair-manifest-history",
          itemLabel: "pending manifest repair",
          emptyHistoryText: "No pending manifest repair history loaded. Run a dry-run before applying backend manifest repair.",
          emptyMatchText: "No pending manifest repair commands found in command history.",
          lineFor: pendingRepairManifestHistoryLine,
          footer: "Dry-runs are unjournaled backend evidence; applies are backend-owned confirmed mutation routes.",
        });
        return;
      }
      const history = Array.isArray(entries) ? entries.filter(isPendingRepairManifestCommand).slice(0, 5) : [];
      setText(
        "pending-repair-manifest-history",
        history.length
          ? [
            `Last ${history.length} pending manifest repair command${history.length === 1 ? "" : "s"}:`,
            ...history.map(pendingRepairManifestHistoryLine),
            "Dry-runs are unjournaled backend evidence; applies are backend-owned confirmed mutation routes.",
          ].join("\n")
          : "No pending manifest repair history loaded. Run a dry-run before applying backend manifest repair.",
      );
    }

    function renderPendingRepairOrphanHistory(entries = getCommandHistory()) {
      if (typeof renderCompactCommandHistoryBlock === "function") {
        renderCompactCommandHistoryBlock({
          history: entries,
          filter: isPendingRepairOrphanCommand,
          limit: 5,
          targetId: "pending-reconcile-orphan-history",
          itemLabel: "orphan payload reconcile",
          emptyHistoryText: "No orphan payload reconcile history loaded. Run a dry-run before applying backend manifest-only reconcile.",
          emptyMatchText: "No orphan payload reconcile commands found in command history.",
          lineFor: pendingRepairManifestHistoryLine,
          footer: "Dry-runs are unjournaled backend evidence; applies are backend-owned confirmed mutation routes.",
        });
        return;
      }
      const history = Array.isArray(entries) ? entries.filter(isPendingRepairOrphanCommand).slice(0, 5) : [];
      setText(
        "pending-reconcile-orphan-history",
        history.length
          ? [
            `Last ${history.length} orphan payload reconcile command${history.length === 1 ? "" : "s"}:`,
            ...history.map(pendingRepairManifestHistoryLine),
            "Dry-runs are unjournaled backend evidence; applies are backend-owned confirmed mutation routes.",
          ].join("\n")
          : "No orphan payload reconcile history loaded. Run a dry-run before applying backend manifest-only reconcile.",
      );
    }

    function pendingRepairManifestDryRunRequest() {
      const row = getSelectedPendingRow();
      const rowKey = selectedRowKey(row);
      if (!rowKey) return null;
      return {
        scope: "selected",
        row_key: rowKey,
        limit: 1,
        reason: "WebView selected-row pending manifest repair dry-run",
      };
    }

    function pendingRepairManifestApplyRequest() {
      const data = repairResultData(lastDryRunResult || {});
      const fingerprint = String(data.dry_run_fingerprint || "").trim();
      const base = pendingRepairManifestDryRunRequest();
      if (!base || !fingerprint) return null;
      return {
        ...base,
        reason: "WebView selected-row pending manifest repair apply",
        dry_run_fingerprint: fingerprint,
        confirm_apply: true,
      };
    }

    function pendingRepairOrphanDryRunRequest() {
      const row = getSelectedPendingRow();
      const rowKey = selectedRowKey(row);
      if (!rowKey) return null;
      return {
        scope: "selected",
        row_key: rowKey,
        limit: 1,
        reason: "WebView selected-row orphan payload reconcile dry-run",
      };
    }

    function pendingRepairOrphanApplyRequest() {
      const data = repairResultData(lastOrphanDryRunResult || {});
      const fingerprint = String(data.dry_run_fingerprint || "").trim();
      const base = pendingRepairOrphanDryRunRequest();
      if (!base || !fingerprint) return null;
      return {
        ...base,
        reason: "WebView selected-row orphan payload reconcile apply",
        dry_run_fingerprint: fingerprint,
        confirm_apply: true,
      };
    }

    async function requestPendingRepairManifestDryRun() {
      const request = pendingRepairManifestDryRunRequest();
      if (!request) {
        const result = {
          command: DRY_RUN_COMMAND,
          ok: false,
          severity: "warning",
          message: "Select a pending publish row before running pending manifest repair dry-run.",
          data: { scope: "selected", dry_run_only: true, safe_to_apply: false },
        };
        appendCommandResult(result);
        renderPendingRepairManifestControls(result);
        return;
      }
      setPendingRepairManifestBusy(true);
      setText("pending-repair-manifest-status", "Running dry-run");
      try {
        const result = typeof window.apiPost === "function"
          ? await window.apiPost("/api/pending-publish/repair-manifest-dry-run", request)
          : await apiPost("/api/pending-publish/repair-manifest-dry-run", request);
        lastDryRunResult = result;
        lastDryRunRowKey = request.row_key;
        appendCommandResult(result);
        renderPendingRepairManifestControls(result);
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        const result = {
          command: DRY_RUN_COMMAND,
          ok: false,
          severity: "error",
          message,
          data: { scope: "selected", selected_row_keys: [request.row_key], safe_to_apply: false },
        };
        lastDryRunResult = result;
        lastDryRunRowKey = request.row_key;
        appendCommandResult(result);
        renderPendingRepairManifestControls(result);
      } finally {
        setPendingRepairManifestBusy(false);
        renderPendingRepairManifestHistory(getCommandHistory());
      }
    }

    async function requestPendingRepairManifestApply() {
      if (!pendingRepairDryRunIsSafeForSelection()) {
        const result = {
          command: COMMAND,
          ok: false,
          severity: "warning",
          message: "Run a safe selected-row pending manifest repair dry-run before applying.",
          data: { scope: "selected", safe_to_apply: false, confirm_apply: false },
        };
        appendCommandResult(result);
        renderPendingRepairManifestControls(result);
        return;
      }
      const request = pendingRepairManifestApplyRequest();
      if (!request) return;
      if (typeof window.confirm === "function") {
        const confirmed = window.confirm("Apply backend-validated pending manifest repair for the selected row? This writes only backend-approved pending manifest fields and does not drain, publish, move, delete, or touch media files.");
        if (!confirmed) {
          setText("pending-repair-manifest-status", "Apply cancelled");
          return;
        }
      }
      setPendingRepairManifestBusy(true);
      setText("pending-repair-manifest-status", "Applying");
      try {
        const result = typeof window.apiPost === "function"
          ? await window.apiPost("/api/pending-publish/repair-manifest", request)
          : await apiPost("/api/pending-publish/repair-manifest", request);
        lastDryRunResult = result;
        lastDryRunRowKey = request.row_key;
        appendCommandResult(result);
        renderPendingRepairManifestControls(result);
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        const result = {
          command: COMMAND,
          ok: false,
          severity: "error",
          message,
          data: { scope: "selected", selected_row_keys: [request.row_key], dry_run_fingerprint: request.dry_run_fingerprint, safe_to_apply: false },
        };
        lastDryRunResult = result;
        lastDryRunRowKey = request.row_key;
        appendCommandResult(result);
        renderPendingRepairManifestControls(result);
      } finally {
        setPendingRepairManifestBusy(false);
        renderPendingRepairManifestHistory(getCommandHistory());
      }
    }

    async function requestPendingRepairOrphanDryRun() {
      const request = pendingRepairOrphanDryRunRequest();
      if (!request) {
        const result = {
          command: ORPHAN_DRY_RUN_COMMAND,
          ok: false,
          severity: "warning",
          message: "Select an orphan payload row before running orphan reconcile dry-run.",
          data: { scope: "selected", dry_run_only: true, safe_to_apply: false },
        };
        appendCommandResult(result);
        renderPendingRepairOrphanControls(result);
        return;
      }
      setPendingRepairOrphanBusy(true);
      setText("pending-reconcile-orphan-status", "Running dry-run");
      try {
        const result = typeof window.apiPost === "function"
          ? await window.apiPost("/api/pending-publish/reconcile-orphan-payloads-dry-run", request)
          : await apiPost("/api/pending-publish/reconcile-orphan-payloads-dry-run", request);
        lastOrphanDryRunResult = result;
        lastOrphanDryRunRowKey = request.row_key;
        appendCommandResult(result);
        renderPendingRepairOrphanControls(result);
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        const result = {
          command: ORPHAN_DRY_RUN_COMMAND,
          ok: false,
          severity: "error",
          message,
          data: { scope: "selected", selected_row_keys: [request.row_key], safe_to_apply: false },
        };
        lastOrphanDryRunResult = result;
        lastOrphanDryRunRowKey = request.row_key;
        appendCommandResult(result);
        renderPendingRepairOrphanControls(result);
      } finally {
        setPendingRepairOrphanBusy(false);
        renderPendingRepairOrphanHistory(getCommandHistory());
      }
    }

    async function requestPendingRepairOrphanApply() {
      if (!pendingOrphanDryRunIsSafeForSelection()) {
        const result = {
          command: ORPHAN_COMMAND,
          ok: false,
          severity: "warning",
          message: "Run a safe selected-row orphan payload reconcile dry-run before applying.",
          data: { scope: "selected", safe_to_apply: false, confirm_apply: false },
        };
        appendCommandResult(result);
        renderPendingRepairOrphanControls(result);
        return;
      }
      const request = pendingRepairOrphanApplyRequest();
      if (!request) return;
      if (typeof window.confirm === "function") {
        const confirmed = window.confirm("Apply backend-validated orphan payload reconcile for the selected row? This writes only a backend-proposed pending manifest and does not drain, publish, move, delete, or touch media files.");
        if (!confirmed) {
          setText("pending-reconcile-orphan-status", "Apply cancelled");
          return;
        }
      }
      setPendingRepairOrphanBusy(true);
      setText("pending-reconcile-orphan-status", "Applying");
      try {
        const result = typeof window.apiPost === "function"
          ? await window.apiPost("/api/pending-publish/reconcile-orphan-payloads", request)
          : await apiPost("/api/pending-publish/reconcile-orphan-payloads", request);
        lastOrphanDryRunResult = result;
        lastOrphanDryRunRowKey = request.row_key;
        appendCommandResult(result);
        renderPendingRepairOrphanControls(result);
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        const result = {
          command: ORPHAN_COMMAND,
          ok: false,
          severity: "error",
          message,
          data: { scope: "selected", selected_row_keys: [request.row_key], dry_run_fingerprint: request.dry_run_fingerprint, safe_to_apply: false },
        };
        lastOrphanDryRunResult = result;
        lastOrphanDryRunRowKey = request.row_key;
        appendCommandResult(result);
        renderPendingRepairOrphanControls(result);
      } finally {
        setPendingRepairOrphanBusy(false);
        renderPendingRepairOrphanHistory(getCommandHistory());
      }
    }

    function initPendingRepairManifestEvents() {
      if (eventsInitialized) return;
      const dryRunButton = byId("pending-repair-manifest-dry-run-button");
      if (dryRunButton) dryRunButton.addEventListener("click", requestPendingRepairManifestDryRun);
      const applyButton = byId("pending-repair-manifest-apply-button");
      if (applyButton) applyButton.addEventListener("click", requestPendingRepairManifestApply);
      const orphanDryRunButton = byId("pending-reconcile-orphan-dry-run-button");
      if (orphanDryRunButton) orphanDryRunButton.addEventListener("click", requestPendingRepairOrphanDryRun);
      const orphanApplyButton = byId("pending-reconcile-orphan-apply-button");
      if (orphanApplyButton) orphanApplyButton.addEventListener("click", requestPendingRepairOrphanApply);
      eventsInitialized = true;
      renderPendingRepairManifestControls();
      renderPendingRepairOrphanControls();
      renderPendingRepairManifestHistory(getCommandHistory());
      renderPendingRepairOrphanHistory(getCommandHistory());
    }

    return {
      initPendingRepairManifestEvents,
      isPendingRepairManifestCommand,
      isPendingRepairOrphanCommand,
      pendingOrphanDryRunIsSafeForSelection,
      pendingRepairDryRunIsSafeForSelection,
      pendingRepairManifestApplyRequest,
      pendingRepairManifestDryRunRequest,
      pendingRepairManifestHistoryLine,
      pendingRepairManifestResultLines,
      pendingRepairOrphanApplyRequest,
      pendingRepairOrphanDryRunRequest,
      renderPendingRepairManifestControls,
      renderPendingRepairManifestHistory,
      renderPendingRepairOrphanControls,
      renderPendingRepairOrphanHistory,
      requestPendingRepairManifestApply,
      requestPendingRepairManifestDryRun,
      requestPendingRepairOrphanApply,
      requestPendingRepairOrphanDryRun,
      setPendingRepairManifestBusy,
      setPendingRepairOrphanBusy,
    };
  }

  window.__pendingPublishRepairModule = { createPendingPublishRepairModule };
})();
