(function () {
  function createCompletedRepairModule(deps = {}) {
    const {
      apiPost = async function () { throw new Error("apiPost unavailable"); },
      appendCommandResult = function () {},
      byId = function () { return null; },
      commandHistoryCompactEvidenceLine = null,
      getCommandHistory = function () { return []; },
      getSelectedCompletedRow = function () { return null; },
      renderCompactCommandHistoryBlock = null,
      setText = function () {},
    } = deps;

    const ACTIONS = {
      manifest: {
        label: "Completed manifest reconciliation",
        command: "completed.reconcile_manifest",
        dryRunCommand: "completed.reconcile_manifest_dry_run",
        dryRunButtonId: "completed-reconcile-manifest-dry-run-button",
        applyButtonId: "completed-reconcile-manifest-apply-button",
        statusId: "completed-repair-manifest-status",
      },
      sidecar: {
        label: "Completed sidecar metadata repair",
        command: "completed.repair_sidecar_metadata",
        dryRunCommand: "completed.repair_sidecar_metadata_dry_run",
        dryRunButtonId: "completed-repair-sidecar-dry-run-button",
        applyButtonId: "completed-repair-sidecar-apply-button",
        statusId: "completed-repair-sidecar-status",
      },
    };
    let eventsInitialized = false;
    let inFlight = false;
    const dryRunResults = { manifest: null, sidecar: null };
    const dryRunRowKeys = { manifest: "", sidecar: "" };
    let lastDisplayKind = null;
    let lastDisplayResult = null;

    function actionConfig(kind) {
      return ACTIONS[kind] || ACTIONS.manifest;
    }

    function selectedRowKey(row = getSelectedCompletedRow()) {
      return String(row?.row_key || "").trim();
    }

    function repairResultData(result) {
      return result?.data && typeof result.data === "object" ? result.data : {};
    }

    function selectedKeys(data) {
      return Array.isArray(data?.selected_row_keys) ? data.selected_row_keys.map((item) => String(item || "").trim()).filter(Boolean) : [];
    }

    function clearStaleDryRunIfSelectionChanged(kind, row = getSelectedCompletedRow()) {
      const rowKey = selectedRowKey(row);
      if (dryRunResults[kind] && dryRunRowKeys[kind] !== rowKey) {
        dryRunResults[kind] = null;
        dryRunRowKeys[kind] = "";
        if (lastDisplayKind === kind) {
          lastDisplayKind = null;
          lastDisplayResult = null;
        }
      }
    }

    function repairDryRunIsSafeForSelection(kind, row = getSelectedCompletedRow()) {
      const config = actionConfig(kind);
      const rowKey = selectedRowKey(row);
      const data = repairResultData(dryRunResults[kind]);
      const keys = selectedKeys(data);
      return Boolean(
        rowKey
        && dryRunRowKeys[kind] === rowKey
        && data.candidate_command === config.command
        && data.safe_to_apply === true
        && data.dry_run_fingerprint
        && (!keys.length || keys.includes(rowKey))
      );
    }

    function mutationGuardrailLine() {
      return "Mutation guardrail: Completed repair controls send only backend route intent. They never send paths, patches, sidecar JSON, raw manifests, rename requests, rerun requests, delete requests, publish/drain requests, or source-media actions.";
    }

    function defaultLines(kind, row = getSelectedCompletedRow()) {
      const config = actionConfig(kind);
      const rowKey = selectedRowKey(row);
      if (!rowKey) {
        return [
          `${config.label}: no Completed row selected.`,
          "Select one Completed row, then run the backend dry-run.",
          "Apply remains disabled until the backend returns safe_to_apply=true with a matching dry_run_fingerprint.",
          mutationGuardrailLine(),
        ];
      }
      return [
        `${config.label}:`,
        `Row key: ${rowKey}`,
        "Step 1: run the backend dry-run for this selected row.",
        "Step 2: apply only when the current dry-run reports safe_to_apply=true and supplies a matching dry_run_fingerprint.",
        mutationGuardrailLine(),
        "No repair result is loaded for this selection yet.",
      ];
    }

    function diffSummaryLines(diff) {
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

    function wouldNotTouchLines(data) {
      const evidence = data?.would_not_touch && typeof data.would_not_touch === "object" ? data.would_not_touch : {};
      const keys = Object.keys(evidence).sort();
      if (!keys.length) return ["Source/output/scratch unchanged evidence: not reported"];
      return [
        "Source/output/scratch unchanged evidence:",
        ...keys.slice(0, 8).map((key) => `- ${key}: ${String(evidence[key])}`),
        keys.length > 8 ? `- ${keys.length - 8} more field(s) not shown.` : "",
      ].filter(Boolean);
    }

    function resultLines(kind, result) {
      const config = actionConfig(kind);
      const data = repairResultData(result || {});
      const warnings = Array.isArray(result?.warnings) ? result.warnings.filter(Boolean) : [];
      const errors = Array.isArray(result?.errors) ? result.errors.filter(Boolean) : [];
      const lines = [
        result?.message || `No ${config.label} result.`,
        `Schema: ${data.schema_version || "not reported"}`,
        `Command: ${data.candidate_command || result?.command || config.command}`,
        `Effect: ${data.effect || "not reported"}`,
        `Scope: ${data.scope || "unknown"}`,
        `Selected row keys: ${selectedKeys(data).join(", ") || "not reported"}`,
        `Safe to apply: ${data.safe_to_apply === true ? "yes" : "no"}`,
        `Applied: ${data.applied === true ? "yes" : data.applied === false ? "no" : "not reported"}`,
        `Blocked: ${data.blocked === true ? "yes" : data.blocked === false ? "no" : "not reported"}`,
        `Dry-run fingerprint: ${data.dry_run_fingerprint || "not reported"}`,
        `Expected fingerprint: ${data.expected_dry_run_fingerprint || "not reported"}`,
        "",
        ...diffSummaryLines(data.diff_summary),
        "",
        ...wouldNotTouchLines(data),
        "",
        mutationGuardrailLine(),
      ];
      if (warnings.length) lines.push("", "Warning(s):", ...warnings.slice(0, 5).map((warning) => `- ${warning}`));
      if (errors.length) lines.push("", "Error(s):", ...errors.slice(0, 5).map((error) => `- ${error}`));
      return lines;
    }

    function statusText(kind, result = dryRunResults[kind]) {
      if (inFlight) return "Repair request running";
      if (!selectedRowKey()) return "No row selected";
      const data = repairResultData(result || {});
      if (!result) return "Dry-run required";
      if (data.applied === true) return "Applied";
      if (data.blocked === true || result?.ok === false) return "Blocked";
      if (repairDryRunIsSafeForSelection(kind)) return "Dry-run safe";
      return "Review dry-run";
    }

    function setBusy(isBusy) {
      inFlight = Boolean(isBusy);
      renderCompletedRepairControls();
    }

    function renderAction(kind) {
      const config = actionConfig(kind);
      const row = getSelectedCompletedRow();
      clearStaleDryRunIfSelectionChanged(kind, row);
      const rowKey = selectedRowKey(row);
      const safe = repairDryRunIsSafeForSelection(kind, row);
      const dryRunButton = byId(config.dryRunButtonId);
      const applyButton = byId(config.applyButtonId);
      if (dryRunButton) {
        dryRunButton.disabled = inFlight || !rowKey;
        dryRunButton.title = rowKey ? `Run backend dry-run for ${config.label}.` : "Select a Completed row before running repair dry-run.";
      }
      if (applyButton) {
        applyButton.disabled = inFlight || !safe;
        applyButton.title = safe ? `Apply backend-validated ${config.label}.` : "Run a safe backend dry-run for the selected row before applying.";
      }
      setText(config.statusId, statusText(kind));
    }

    function renderCompletedRepairControls(resultKind = null, result = null) {
      renderAction("manifest");
      renderAction("sidecar");
      if (resultKind && result) {
        lastDisplayKind = resultKind;
        lastDisplayResult = result;
      }
      const statuses = ["manifest", "sidecar"].map((kind) => statusText(kind));
      const overall = statuses.includes("Applied")
        ? "Applied"
        : statuses.includes("Dry-run safe")
          ? "Dry-run safe"
          : statuses.includes("Blocked")
            ? "Blocked"
            : statuses.includes("Repair request running")
              ? "Repair request running"
              : statuses.every((status) => status === "No row selected")
                ? "No row selected"
                : "Dry-run required";
      setText("completed-repair-overall-status", overall);
      const row = getSelectedCompletedRow();
      const displayKind = lastDisplayKind;
      const displayResult = lastDisplayResult;
      const lines = [
        "Completed repair/reconcile controls:",
        `Selected row key: ${selectedRowKey(row) || "none"}`,
        "",
        "Manifest reconciliation:",
        ...(displayKind === "manifest" && displayResult ? resultLines("manifest", displayResult) : defaultLines("manifest", row)),
        "",
        "Sidecar metadata repair:",
        ...(displayKind === "sidecar" && displayResult ? resultLines("sidecar", displayResult) : defaultLines("sidecar", row)),
      ];
      setText("completed-repair-detail", lines.join("\n"));
    }

    function dryRunRequest(kind) {
      const rowKey = selectedRowKey();
      if (!rowKey) return null;
      return {
        scope: "selected",
        row_key: rowKey,
        limit: 1,
        reason: `${actionConfig(kind).label} WebView selected-row dry-run`,
      };
    }

    function applyRequest(kind) {
      const data = repairResultData(dryRunResults[kind] || {});
      const fingerprint = String(data.dry_run_fingerprint || "").trim();
      const base = dryRunRequest(kind);
      if (!base || !fingerprint) return null;
      return {
        ...base,
        reason: `${actionConfig(kind).label} WebView selected-row apply`,
        dry_run_fingerprint: fingerprint,
        confirm_apply: true,
      };
    }

    async function postDryRun(kind, request) {
      if (kind === "sidecar") {
        return typeof window.apiPost === "function"
          ? window.apiPost("/api/completed/repair-sidecar-metadata-dry-run", request)
          : apiPost("/api/completed/repair-sidecar-metadata-dry-run", request);
      }
      return typeof window.apiPost === "function"
        ? window.apiPost("/api/completed/reconcile-manifest-dry-run", request)
        : apiPost("/api/completed/reconcile-manifest-dry-run", request);
    }

    async function postApply(kind, request) {
      if (kind === "sidecar") {
        return typeof window.apiPost === "function"
          ? window.apiPost("/api/completed/repair-sidecar-metadata", request)
          : apiPost("/api/completed/repair-sidecar-metadata", request);
      }
      return typeof window.apiPost === "function"
        ? window.apiPost("/api/completed/reconcile-manifest", request)
        : apiPost("/api/completed/reconcile-manifest", request);
    }

    async function requestCompletedRepairDryRun(kind = "manifest") {
      const config = actionConfig(kind);
      const request = dryRunRequest(kind);
      if (!request) {
        const result = {
          command: config.dryRunCommand,
          ok: false,
          severity: "warning",
          message: "Select a Completed row before running repair dry-run.",
          data: { scope: "selected", dry_run_only: true, safe_to_apply: false },
        };
        appendCommandResult(result);
        renderCompletedRepairControls(kind, result);
        return result;
      }
      setBusy(true);
      setText(config.statusId, "Running dry-run");
      try {
        const result = await postDryRun(kind, request);
        dryRunResults[kind] = result;
        dryRunRowKeys[kind] = request.row_key;
        appendCommandResult(result);
        renderCompletedRepairControls(kind, result);
        return result;
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        const result = {
          command: config.dryRunCommand,
          ok: false,
          severity: "error",
          message,
          data: { scope: "selected", selected_row_keys: [request.row_key], safe_to_apply: false },
        };
        dryRunResults[kind] = result;
        dryRunRowKeys[kind] = request.row_key;
        appendCommandResult(result);
        renderCompletedRepairControls(kind, result);
        return result;
      } finally {
        setBusy(false);
        renderCompletedRepairHistory(getCommandHistory());
      }
    }

    async function requestCompletedRepairApply(kind = "manifest") {
      const config = actionConfig(kind);
      if (!repairDryRunIsSafeForSelection(kind)) {
        const result = {
          command: config.command,
          ok: false,
          severity: "warning",
          message: "Run a safe selected-row Completed repair dry-run before applying.",
          data: { scope: "selected", safe_to_apply: false, confirm_apply: false },
        };
        appendCommandResult(result);
        renderCompletedRepairControls(kind, result);
        return result;
      }
      const request = applyRequest(kind);
      if (!request) return null;
      if (typeof window.confirm === "function") {
        const confirmed = window.confirm(`Apply backend-validated ${config.label} for the selected Completed row? This writes only backend-approved state and does not rename, rerun, delete, publish, drain, or touch media files.`);
        if (!confirmed) {
          setText(config.statusId, "Apply cancelled");
          return null;
        }
      }
      setBusy(true);
      setText(config.statusId, "Applying");
      try {
        const result = await postApply(kind, request);
        dryRunResults[kind] = result;
        dryRunRowKeys[kind] = request.row_key;
        appendCommandResult(result);
        renderCompletedRepairControls(kind, result);
        return result;
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        const result = {
          command: config.command,
          ok: false,
          severity: "error",
          message,
          data: { scope: "selected", selected_row_keys: [request.row_key], dry_run_fingerprint: request.dry_run_fingerprint, safe_to_apply: false },
        };
        dryRunResults[kind] = result;
        dryRunRowKeys[kind] = request.row_key;
        appendCommandResult(result);
        renderCompletedRepairControls(kind, result);
        return result;
      } finally {
        setBusy(false);
        renderCompletedRepairHistory(getCommandHistory());
      }
    }

    function isCompletedRepairCommand(entry) {
      const command = String(entry?.command || entry?.raw?.command || "").toLowerCase();
      return Object.values(ACTIONS).some((config) => command === config.command || command === config.dryRunCommand);
    }

    function historyLine(entry) {
      const raw = entry?.raw && typeof entry.raw === "object" ? entry.raw : {};
      const data = raw.data && typeof raw.data === "object" ? raw.data : {};
      const detail = ` (scope=${data.scope || raw.request?.scope || "unknown"}; safe=${data.safe_to_apply === true ? "yes" : "no"}; applied=${data.applied === true ? "yes" : "no"})`;
      if (typeof commandHistoryCompactEvidenceLine === "function") {
        return commandHistoryCompactEvidenceLine(entry, {
          label: String(raw.command || entry?.command || "completed repair"),
          detail,
        });
      }
      const status = entry?.result || (entry?.ok ? "ok" : entry?.severity || "unknown");
      const local = entry?.local ? "local" : "journal";
      return `${entry?.at || ""} ${raw.command || entry?.command || "completed repair"} [${status}; ${local}] ${entry?.message || ""}${detail}`.trim();
    }

    function renderCompletedRepairHistory(entries = getCommandHistory()) {
      if (typeof renderCompactCommandHistoryBlock === "function") {
        renderCompactCommandHistoryBlock({
          history: entries,
          filter: isCompletedRepairCommand,
          limit: 5,
          targetId: "completed-repair-history",
          itemLabel: "Completed repair/reconcile",
          emptyHistoryText: "No Completed repair/reconcile history loaded. Run a dry-run before applying backend repair.",
          emptyMatchText: "No Completed repair/reconcile commands found in command history.",
          lineFor: historyLine,
          footer: "Dry-runs are unjournaled backend evidence; applies are backend-owned confirmed mutation routes.",
        });
        return;
      }
      const history = Array.isArray(entries) ? entries.filter(isCompletedRepairCommand).slice(0, 5) : [];
      setText(
        "completed-repair-history",
        history.length
          ? [
            `Last ${history.length} Completed repair command${history.length === 1 ? "" : "s"}:`,
            ...history.map(historyLine),
            "Dry-runs are unjournaled backend evidence; applies are backend-owned confirmed mutation routes.",
          ].join("\n")
          : "No Completed repair/reconcile history loaded. Run a dry-run before applying backend repair.",
      );
    }

    function initCompletedRepairEvents() {
      if (eventsInitialized) return;
      const manifestDryRun = byId(ACTIONS.manifest.dryRunButtonId);
      if (manifestDryRun) manifestDryRun.addEventListener("click", () => requestCompletedRepairDryRun("manifest"));
      const manifestApply = byId(ACTIONS.manifest.applyButtonId);
      if (manifestApply) manifestApply.addEventListener("click", () => requestCompletedRepairApply("manifest"));
      const sidecarDryRun = byId(ACTIONS.sidecar.dryRunButtonId);
      if (sidecarDryRun) sidecarDryRun.addEventListener("click", () => requestCompletedRepairDryRun("sidecar"));
      const sidecarApply = byId(ACTIONS.sidecar.applyButtonId);
      if (sidecarApply) sidecarApply.addEventListener("click", () => requestCompletedRepairApply("sidecar"));
      eventsInitialized = true;
      renderCompletedRepairControls();
      renderCompletedRepairHistory(getCommandHistory());
    }

    return {
      initCompletedRepairEvents,
      isCompletedRepairCommand,
      repairDryRunIsSafeForSelection,
      renderCompletedRepairControls,
      renderCompletedRepairHistory,
      requestCompletedRepairApply,
      requestCompletedRepairDryRun,
      setCompletedRepairBusy: setBusy,
    };
  }

  window.__completedViewRepairModule = { createCompletedRepairModule };
})();
