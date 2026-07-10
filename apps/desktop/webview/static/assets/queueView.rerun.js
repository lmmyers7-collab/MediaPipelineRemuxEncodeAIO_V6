(function () {
  const RERUN_PREVIEW_ROUTE = "/api/rerun/preview";
  const RERUN_NETWORK_PREVIEW_ROUTE = "/api/rerun/network-preview";
  const RERUN_NETWORK_START_DRY_RUN_ROUTE = "/api/rerun/network/start-dry-run";
  const RERUN_NETWORK_START_ROUTE = "/api/rerun/network/start";
  const RERUN_START_ROUTE = "/api/rerun/start";
  const RERUN_RESULTS_ROUTE = "/api/rerun/results?limit=24";
  const RERUN_CONTROL_ROUTE = "/api/rerun/control";
  const RERUN_CONTINUE_ROUTE = "/api/rerun/continue";
  const RERUN_OPEN_ROUTE = "/api/rerun/open";
  const RERUN_PROMOTE_DRY_RUN_ROUTE = "/api/rerun/promote-dry-run";
  const RERUN_PROMOTE_ROUTE = "/api/rerun/promote";
  const DIAGNOSTICS_OPEN_ROUTE = "/api/diagnostics/open";
  const COMMAND_HISTORY_ROUTE = "/api/commands?limit=20";
  const RERUN_DIAGNOSTICS_TARGETS = new Set(["run_logs", "last_stdout_log", "last_stderr_log", "active_jobs"]);

  function createQueueRerunModule(deps = {}) {
    const byId = typeof deps.byId === "function" ? deps.byId : window.byId;
    const setText = typeof deps.setText === "function" ? deps.setText : window.setText;
    const apiGet = typeof deps.apiGet === "function" ? deps.apiGet : window.apiGet;
    const apiPost = typeof deps.apiPost === "function" ? deps.apiPost : window.apiPost;
    let queueRerunBusy = false;
    let queueRerunPreviewRefreshTimer = null;
    let lastRerunResultsPayload = null;

    function rerunWorkflowHelpers() {
      return window.mediaPipelineCsvRerunWorkflow || window.mediaPipelineLaunchView || {};
    }

    function statusText(id, message) {
      if (typeof setText === "function") setText(id, message);
      else {
        const node = typeof byId === "function" ? byId(id) : document.getElementById(id);
        if (node) node.textContent = message;
      }
    }

    function unavailableResult(routeName, fnName) {
      const message = `CSV rerun ${fnName} is unavailable until the backend route bridge is loaded. Route remains ${routeName}.`;
      statusText("rerun-queue-status", "Unavailable");
      statusText("rerun-queue-detail", message);
      return {
        command: "rerun.unavailable",
        ok: false,
        severity: "error",
        message,
        data: {
          route: routeName,
          queue_owned_surface: true,
          uses_pipeline_start: false,
        },
      };
    }

    function callRerunWorkflowHelper(fnName, routeName, args = []) {
      const fn = rerunWorkflowHelpers()[fnName];
      if (typeof fn !== "function") return Promise.resolve(unavailableResult(routeName, fnName));
      try {
        return Promise.resolve(fn(...args));
      } catch (error) {
        return Promise.reject(error);
      }
    }

    function currentApiPost() {
      return typeof window.apiPost === "function" ? window.apiPost : apiPost;
    }

    function currentApiGet() {
      return typeof window.apiGet === "function" ? window.apiGet : apiGet;
    }

    function requireApiPost(routeName) {
      const post = currentApiPost();
      if (typeof post === "function") return post;
      throw new Error(`CSV rerun backend route dispatcher is unavailable for ${routeName}.`);
    }

    function requireApiGet(routeName) {
      const get = currentApiGet();
      if (typeof get === "function") return get;
      throw new Error(`CSV rerun backend route dispatcher is unavailable for ${routeName}.`);
    }

    async function postRerunPreview(request) {
      return requireApiPost(RERUN_PREVIEW_ROUTE)("/api/rerun/preview", request);
    }

    async function postRerunNetworkPreview(request) {
      return requireApiPost(RERUN_NETWORK_PREVIEW_ROUTE)("/api/rerun/network-preview", request);
    }

    async function postRerunNetworkStartDryRun(request) {
      return requireApiPost(RERUN_NETWORK_START_DRY_RUN_ROUTE)("/api/rerun/network/start-dry-run", request);
    }

    async function postRerunNetworkStart(request) {
      return requireApiPost(RERUN_NETWORK_START_ROUTE)("/api/rerun/network/start", request);
    }

    async function postRerunStart(request) {
      return requireApiPost(RERUN_START_ROUTE)("/api/rerun/start", request);
    }

    async function postRerunControlStopAfterCurrent() {
      return requireApiPost(RERUN_CONTROL_ROUTE)("/api/rerun/control", { action: "stop_after_current", confirm_stop: true });
    }

    async function postRerunControlPause() {
      return requireApiPost(RERUN_CONTROL_ROUTE)("/api/rerun/control", { action: "pause", confirm_pause: true });
    }

    async function postRerunContinue(request) {
      return requireApiPost(RERUN_CONTINUE_ROUTE)("/api/rerun/continue", request);
    }

    async function postRerunOpen(request) {
      return requireApiPost(RERUN_OPEN_ROUTE)("/api/rerun/open", request);
    }

    async function postDiagnosticsOpen(target) {
      return requireApiPost(DIAGNOSTICS_OPEN_ROUTE)("/api/diagnostics/open", { target });
    }

    async function postRerunPromoteDryRun(rowKey) {
      return requireApiPost(RERUN_PROMOTE_DRY_RUN_ROUTE)("/api/rerun/promote-dry-run", { row_key: rowKey });
    }

    async function postRerunPromote(request) {
      return requireApiPost(RERUN_PROMOTE_ROUTE)("/api/rerun/promote", request);
    }

    async function getRerunResults() {
      return requireApiGet(RERUN_RESULTS_ROUTE)("/api/rerun/results?limit=24", { timeoutMs: 15000 });
    }

    async function getCommandHistory() {
      return requireApiGet(COMMAND_HISTORY_ROUTE)("/api/commands?limit=20", { timeoutMs: 15000 });
    }

    function nodeById(id) {
      return typeof byId === "function" ? byId(id) : document.getElementById(id);
    }

    function clearNode(node) {
      if (!node) return;
      while (node.firstChild) node.removeChild(node.firstChild);
    }

    function appendCell(row, text, className = "") {
      const cell = document.createElement("td");
      if (className) cell.className = className;
      cell.textContent = text == null ? "" : String(text);
      row.appendChild(cell);
      return cell;
    }

    function leaf(value) {
      const text = String(value || "").trim();
      if (!text) return "";
      return text.split(/[\\/]/).filter(Boolean).pop() || text;
    }

    function compactPath(value) {
      const text = String(value || "").trim();
      if (!text) return "";
      const short = leaf(text);
      return short && short !== text ? `${short}\n${text}` : text;
    }

    function listValues(value) {
      if (Array.isArray(value)) return value.flatMap(listValues);
      const text = String(value || "").trim();
      if (!text) return [];
      return text.split(/[,\n;]+/).map((item) => item.trim()).filter(Boolean);
    }

    function uniqueValues(values) {
      const seen = new Set();
      const result = [];
      values.forEach((value) => {
        const text = String(value || "").trim();
        const key = text.toLowerCase();
        if (!text || seen.has(key)) return;
        seen.add(key);
        result.push(text);
      });
      return result;
    }

    function rerunIssueTokens(item = {}) {
      return uniqueValues([
        ...listValues(item.audit_issue_code_list),
        ...listValues(item.audit_issue_codes),
        ...listValues(item.issue_code_list),
        ...listValues(item.issue_codes),
        ...listValues(item.issue_code),
        ...listValues(item.issue),
        ...listValues(item.issues),
        ...listValues(item.bucket),
      ]);
    }

    function rerunIssueFamily(issue) {
      const text = String(issue || "").toLowerCase();
      if (/(subtitle|subtitles|vobsub|ocr|srt|pgs|tx3g|caption)/.test(text)) return "subtitle";
      if (/(audio|channel|track-title|track_title|language)/.test(text)) return "audio";
      if (/(video|image|hdr|codec|resolution)/.test(text)) return "video";
      if (/(publish|pending|manifest|destination|final|output|replace)/.test(text)) return "publish";
      if (/(source|path|csv|file)/.test(text)) return "file";
      return "other";
    }

    function rerunIssueSymbol(family) {
      return {
        audio: "A",
        subtitle: "S",
        video: "V",
        publish: "P",
        file: "F",
        other: "I",
      }[family] || "I";
    }

    function rerunIssueLabel(issue) {
      const text = String(issue || "").trim();
      const lower = text.toLowerCase();
      if (!text) return "issue";
      if (lower.includes("default-policy")) return "default policy";
      if (lower.includes("track-title")) return "track titles";
      if (lower.includes("ocr")) return "ocr candidate";
      if (lower.includes("image-only")) return "image only";
      if (lower.includes("default-image")) return "default image";
      if (lower.includes("pending-publish")) return "pending publish";
      if (lower.includes("destination")) return "destination";
      if (lower.includes("manifest")) return "manifest";
      if (lower.includes("missing")) return "missing";
      const words = lower
        .replace(/[_-]+/g, " ")
        .split(/\s+/)
        .filter((word) => word && !["audio", "subtitle", "subtitles", "issue", "issues"].includes(word));
      return (words.slice(0, 2).join(" ") || text).trim();
    }

    function rerunStatusKey(item = {}) {
      return String(item.queue_status || item.status || "unknown")
        .trim()
        .toLowerCase()
        .replace(/\s+/g, "_");
    }

    function rerunSeverity(item = {}) {
      const status = rerunStatusKey(item);
      if (/(failed|blocked|error)/.test(status)) return "high";
      if (/(warning|awaiting_review|review|pending_publish)/.test(status)) return "medium";
      if (/(completed|replaced_returned|done|ok|success)/.test(status)) return "ok";
      if (/(active|running|pending|stopped|skipped)/.test(status)) return "info";
      return "info";
    }

    function rerunIssueDetailLines(item = {}, issue = "") {
      const family = rerunIssueFamily(issue);
      const severity = rerunSeverity(item);
      const destination = item.destination_state && typeof item.destination_state === "object" ? item.destination_state : {};
      const destinationResult = item.network_destination_policy_result && typeof item.network_destination_policy_result === "object"
        ? item.network_destination_policy_result
        : destination.destination_policy_result && typeof destination.destination_policy_result === "object"
        ? destination.destination_policy_result
        : {};
      const reducer = item.network_reducer_result && typeof item.network_reducer_result === "object" ? item.network_reducer_result : {};
      const worker = item.network_worker_result && typeof item.network_worker_result === "object" ? item.network_worker_result : {};
      return [
        `Issue: ${issue || "uncategorized"}`,
        `Label: ${rerunIssueLabel(issue)}`,
        `Family: ${family}`,
        `Severity: ${severity}`,
        item.queue_source === "network_csv_rerun" ? `Network batch: ${item.batch_id || item.manifest_status || "unknown"}` : "",
        item.queue_source === "network_csv_rerun" ? `Worker: ${worker.worker_id || worker.worker_name || item.active_claim?.worker_id || "not recorded"}` : "",
        item.queue_source === "network_csv_rerun" ? `Reducer: ${reducer.classification || item.queue_status || "not reduced"}` : "",
        destinationResult.status || destinationResult.action
          ? `Destination policy: ${[destinationResult.status, destinationResult.action].filter(Boolean).join(" / ")}`
          : "",
        destinationResult.message ? `Destination detail: ${destinationResult.message}` : "",
        item.rerun_rule_label ? `Rule: ${item.rerun_rule_label}` : "",
        item.rerun_rule_reason ? `Rule detail: ${item.rerun_rule_reason}` : "",
        item.blocking_reason ? `Blocking detail: ${item.blocking_reason}` : "",
        item.warning_reason ? `Warning detail: ${item.warning_reason}` : "",
        item.reason ? `Row detail: ${item.reason}` : "",
        item.destination_state?.auto_destination_decision ? `Decision: ${item.destination_state.auto_destination_decision}` : "",
        item.rerun_rule_destination_behavior ? `Rule destination: ${item.rerun_rule_destination_behavior}` : "",
        item.manifest_status ? `Manifest: ${item.manifest_status}` : "",
        item.original_source_path || item.source_path ? `Source: ${item.original_source_path || item.source_path}` : "",
        item.output_path || item.verified_output_path || item.stage_path ? `Output: ${item.output_path || item.verified_output_path || item.stage_path}` : "",
        item.final_output_path || item.destination_path ? `Final: ${item.final_output_path || item.destination_path}` : "",
        item.pending_publish_manifest_path ? `Pending manifest: ${item.pending_publish_manifest_path}` : "",
        item.published_path ? `Published: ${item.published_path}` : "",
      ].filter(Boolean);
    }

    function showRerunIssueDetail(item, issue) {
      statusText("rerun-queue-detail", rerunIssueDetailLines(item, issue).join("\n"));
    }

    function renderRerunStateBadge(cell, item) {
      const badge = document.createElement("span");
      badge.className = "rerun-state-badge";
      badge.dataset.severity = rerunSeverity(item);
      badge.textContent = String(item.queue_status_label || item.queue_status || item.status || "Unknown");
      cell.appendChild(badge);
    }

    function renderRerunIssueChips(cell, item) {
      const issues = rerunIssueTokens(item);
      cell.className = "rerun-issues-cell";
      if (!issues.length) {
        const empty = document.createElement("span");
        empty.className = "rerun-issue-empty";
        empty.textContent = "None";
        cell.appendChild(empty);
        return;
      }
      const strip = document.createElement("div");
      strip.className = "rerun-issue-strip";
      const severity = rerunSeverity(item);
      issues.slice(0, 8).forEach((issue) => {
        const family = rerunIssueFamily(issue);
        const button = document.createElement("button");
        button.type = "button";
        button.className = "rerun-issue-chip";
        button.dataset.issueFamily = family;
        button.dataset.severity = severity;
        button.title = `Show details for ${issue}`;
        button.setAttribute("aria-label", `Show CSV rerun issue details for ${issue}`);
        const symbol = document.createElement("span");
        symbol.className = "rerun-issue-symbol";
        symbol.textContent = rerunIssueSymbol(family);
        const label = document.createElement("span");
        label.className = "rerun-issue-label";
        label.textContent = rerunIssueLabel(issue);
        button.appendChild(symbol);
        button.appendChild(label);
        button.addEventListener("click", () => showRerunIssueDetail(item, issue));
        strip.appendChild(button);
      });
      if (issues.length > 8) {
        const overflow = document.createElement("span");
        overflow.className = "rerun-issue-overflow";
        overflow.textContent = `+${issues.length - 8}`;
        strip.appendChild(overflow);
      }
      cell.appendChild(strip);
    }

    function queueStateRows(payload = lastRerunResultsPayload) {
      const stateRows = payload?.queue_state && Array.isArray(payload.queue_state.rows) ? payload.queue_state.rows : null;
      if (stateRows) return stateRows;
      return Array.isArray(payload?.rows) ? payload.rows : [];
    }

    function queueStatusFilter() {
      const select = nodeById("rerun-state-status-filter");
      return String(select?.value || "all");
    }

    function setQueueStatusFilterOptions(payload) {
      const select = nodeById("rerun-state-status-filter");
      if (!select || select.dataset.rerunStatusOptionsBound === "true") return;
      const statuses = Array.isArray(payload?.queue_state?.available_statuses)
        ? payload.queue_state.available_statuses
        : [];
      if (!statuses.length) return;
      const current = select.value || "all";
      clearNode(select);
      const all = document.createElement("option");
      all.value = "all";
      all.textContent = "All statuses";
      select.appendChild(all);
      statuses.forEach((status) => {
        const key = String(status?.key || "").trim();
        if (!key) return;
        const option = document.createElement("option");
        option.value = key;
        option.textContent = String(status?.label || key);
        select.appendChild(option);
      });
      select.value = Array.from(select.options).some((option) => option.value === current) ? current : "all";
      select.dataset.rerunStatusOptionsBound = "true";
    }

    function filteredQueueStateRows(payload = lastRerunResultsPayload) {
      const filter = queueStatusFilter();
      const rows = queueStateRows(payload);
      if (filter === "all") return rows;
      return rows.filter((row) => String(row?.queue_status || "").trim() === filter);
    }

    function rerunDestinationSummaryLines(manifest) {
      const summary = manifest?.destination_summary && typeof manifest.destination_summary === "object"
        ? manifest.destination_summary
        : {};
      const lines = [];
      const detail = String(summary.detail || "").trim();
      if (detail) lines.push(detail);
      const samples = Array.isArray(summary.sample_destinations) ? summary.sample_destinations : [];
      if (samples.length) {
        lines.push(`Completed targets: ${samples.map((sample) => leaf(sample?.path || sample)).filter(Boolean).join("; ")}.`);
      }
      return lines;
    }

    function firstManifestRowKey(manifest) {
      const rows = Array.isArray(manifest?.rows) ? manifest.rows : [];
      const row = rows.find((item) => String(item?.row_key || "").trim());
      return String(row?.row_key || "").trim();
    }

    function queueRowSourceLines(item = {}) {
      const lines = [compactPath(item.original_source_path || item.source_path)];
      if (item.queue_source === "network_csv_rerun") {
        lines.push(
          [
            "Network CSV rerun",
            item.batch_id ? `batch ${item.batch_id}` : "",
            item.network_rerun_row_key ? `row ${item.network_rerun_row_key}` : "",
          ].filter(Boolean).join(" | ")
        );
      }
      return lines.filter(Boolean).join("\n");
    }

    function queueRowOutputLines(item = {}) {
      const destination = item.destination_state && typeof item.destination_state === "object" ? item.destination_state : {};
      const destinationResult = item.network_destination_policy_result && typeof item.network_destination_policy_result === "object"
        ? item.network_destination_policy_result
        : destination.destination_policy_result && typeof destination.destination_policy_result === "object"
        ? destination.destination_policy_result
        : {};
      const lines = [
        compactPath(item.output_path || item.verified_output_path || item.stage_path),
        compactPath(item.final_output_path || item.destination_path),
      ];
      if (item.queue_source === "network_csv_rerun") {
        const policy = [destinationResult.status, destinationResult.action].filter(Boolean).join(" / ");
        if (policy) lines.push(`Destination policy: ${policy}`);
        if (destinationResult.message) lines.push(destinationResult.message);
        if (item.pending_publish_manifest_path || destinationResult.pending_publish_manifest_path) {
          lines.push(`Pending manifest: ${compactPath(item.pending_publish_manifest_path || destinationResult.pending_publish_manifest_path)}`);
        }
        if (item.published_path || destinationResult.published_path) {
          lines.push(`Published: ${compactPath(item.published_path || destinationResult.published_path)}`);
        }
      }
      return lines.filter(Boolean).join("\n\n");
    }

    function latestManifestRowKey(payload = lastRerunResultsPayload) {
      const manifests = Array.isArray(payload?.manifests) ? payload.manifests : [];
      for (const manifest of manifests) {
        const rowKey = firstManifestRowKey(manifest);
        if (rowKey) return rowKey;
      }
      return "";
    }

    function renderRerunManifestCards(payload) {
      const container = nodeById("rerun-results-panel");
      if (!container) return;
      clearNode(container);
      const manifests = Array.isArray(payload?.manifests) ? payload.manifests : [];
      if (!manifests.length) {
        container.textContent = "No rerun manifests loaded.";
        return;
      }
      manifests.slice(0, 8).forEach((manifest) => {
        const item = document.createElement("div");
        item.className = "command-history-entry";
        const title = document.createElement("strong");
        title.textContent = [manifest.batch_id || "rerun manifest", manifest.status || "unknown"].filter(Boolean).join(" | ");
        item.appendChild(title);
        const counts = manifest.queue_status_counts && typeof manifest.queue_status_counts === "object"
          ? Object.keys(manifest.queue_status_counts).sort().map((key) => `${key} ${manifest.queue_status_counts[key]}`)
          : [];
        const detail = document.createElement("span");
        detail.textContent = [
          `Rows: ${manifest.row_count || 0}; remaining pending ${manifest.remaining_pending_count || 0}.`,
          counts.length ? `Queue state: ${counts.join("; ")}.` : "",
          `Mode: ${manifest.execution_mode || "one_at_a_time"}; destination=${manifest.destination_mode || "unknown"}; collision=${manifest.collision_policy || "unknown"}.`,
          ...rerunDestinationSummaryLines(manifest),
          manifest.safe_next_action || "",
        ].filter(Boolean).join(" ");
        item.appendChild(detail);
        const actionRow = document.createElement("div");
        actionRow.className = "rerun-manifest-actions";
        const rowKey = firstManifestRowKey(manifest);
        if (rowKey) {
          const button = document.createElement("button");
          button.type = "button";
          button.className = "secondary-button rerun-open-manifest-button";
          button.dataset.rerunTarget = "manifest";
          button.textContent = "Open Manifest";
          button.title = "Open this CSV rerun manifest through the backend rerun open policy.";
          button.addEventListener("click", () => {
            openRerunRowTarget(rowKey, "manifest").catch((error) => {
              statusText("rerun-queue-detail", error instanceof Error ? error.message : String(error));
            });
          });
          actionRow.appendChild(button);
        }
        if (manifest.can_continue_pending) {
          const button = document.createElement("button");
          button.type = "button";
          button.className = "secondary-button rerun-continue-pending-button";
          button.dataset.manifestKey = manifest.manifest_key || "";
          button.textContent = "Continue Pending Rows";
          button.title = "Start a backend-owned CSV rerun scoped to pending rows only.";
          button.addEventListener("click", () => {
            requestRerunContinue(manifest.manifest_key || "").catch(() => {});
          });
          actionRow.appendChild(button);
        }
        if (actionRow.childNodes.length) {
          item.appendChild(actionRow);
        }
        container.appendChild(item);
      });
    }

    function commandHistoryTarget(entry) {
      const candidates = [
        entry?.request?.target,
        entry?.data?.target,
        entry?.raw?.request?.target,
        entry?.raw?.data?.target,
      ];
      const value = candidates.find((item) => String(item || "").trim());
      return String(value || "").trim();
    }

    function isRerunEvidenceCommand(entry) {
      const command = String(entry?.command || "").toLowerCase();
      if (command.includes("rerun")) return true;
      if (command !== "diagnostics.open") return false;
      return RERUN_DIAGNOSTICS_TARGETS.has(commandHistoryTarget(entry));
    }

    function compactCommandMessage(entry) {
      const message = String(entry?.message || "").replace(/\s+/g, " ").trim();
      if (!message) return "";
      return message.length > 180 ? `${message.slice(0, 177)}...` : message;
    }

    function rerunCommandHistoryLine(entry) {
      const status = entry?.ok === false ? "failed" : String(entry?.severity || "ok");
      const target = commandHistoryTarget(entry);
      const parts = [
        String(entry?.at || "").trim(),
        String(entry?.command || "unknown").trim(),
        status,
        target ? `target=${target}` : "",
      ].filter(Boolean);
      const message = compactCommandMessage(entry);
      return `${parts.join(" | ")}${message ? ` - ${message}` : ""}`;
    }

    function renderRerunRowActions(cell, row) {
      const rowKey = String(row?.row_key || "");
      const actions = Array.isArray(row?.available_actions) ? row.available_actions : [];
      if (!rowKey || !actions.length) {
        cell.textContent = "No actions";
        return;
      }
      actions.slice(0, 4).forEach((action) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "secondary-button";
        button.textContent = String(action?.label || action?.action || "Open");
        button.dataset.rerunAction = String(action?.action || "");
        button.addEventListener("click", () => {
          const actionName = String(action?.action || "");
          if (actionName === "promote_to_pending_publish") {
            promoteRerunRowToPending(rowKey).catch((error) => {
              statusText("rerun-queue-detail", error instanceof Error ? error.message : String(error));
            });
            return;
          }
          const target = String(action?.target || "manifest");
          openRerunRowTarget(rowKey, target).catch((error) => {
            statusText("rerun-queue-detail", error instanceof Error ? error.message : String(error));
          });
        });
        cell.appendChild(button);
      });
    }

    function renderRerunQueueStateRows(payload = lastRerunResultsPayload) {
      const body = nodeById("rerun-state-rows");
      if (!body) return;
      clearNode(body);
      const rows = filteredQueueStateRows(payload);
      if (!rows.length) {
        const empty = document.createElement("tr");
        appendCell(empty, "No CSV rerun queue-state rows match the current filter.", "empty-cell").colSpan = 5;
        body.appendChild(empty);
        return;
      }
      rows.slice(0, 200).forEach((item) => {
        const row = document.createElement("tr");
        row.dataset.queueSource = String(item.queue_source || "csv_rerun");
        row.dataset.rerunStatus = String(item.queue_status || "");
        row.dataset.rerunSeverity = rerunSeverity(item);
        row.dataset.status = rerunStatusKey(item);
        renderRerunStateBadge(appendCell(row, ""), item);
        appendCell(row, queueRowSourceLines(item));
        appendCell(row, queueRowOutputLines(item));
        const issueCell = document.createElement("td");
        renderRerunIssueChips(issueCell, item);
        row.appendChild(issueCell);
        const actionCell = document.createElement("td");
        renderRerunRowActions(actionCell, item);
        row.appendChild(actionCell);
        body.appendChild(row);
      });
    }

    function renderRerunResults(payload) {
      lastRerunResultsPayload = payload && typeof payload === "object" ? payload : null;
      setQueueStatusFilterOptions(lastRerunResultsPayload);
      renderRerunManifestCards(lastRerunResultsPayload);
      renderRerunQueueStateRows(lastRerunResultsPayload);
      const counts = lastRerunResultsPayload?.queue_state?.status_counts || {};
      const countText = Object.keys(counts).sort().map((key) => `${key} ${counts[key]}`).join("; ");
      statusText("rerun-history-summary", [
        "CSV rerun queue-state is backend-owned and rendered from /api/rerun/results.",
        "Local and Network CSV rerun rows shown here are not normal /api/pipeline/start queue rows.",
        countText ? `Status counts: ${countText}.` : "No CSV rerun rows loaded.",
        lastRerunResultsPayload?.queue_state?.contains_network_csv_rerun ? "Network CSV rerun reducer and destination-policy evidence is backend-authored." : "",
      ].join("\n"));
    }

    function setQueueRerunBusy(isBusy) {
      queueRerunBusy = Boolean(isBusy);
      const button = typeof byId === "function" ? byId("rerun-start-button") : null;
      if (button && queueRerunBusy) {
        button.disabled = true;
        button.setAttribute("aria-disabled", "true");
        button.dataset.commandState = "running";
        button.title = "CSV rerun command is already in progress.";
      }
      if (!queueRerunBusy) updateQueueRerunButtonState();
    }

    function updateQueueRerunButtonState() {
      const update = rerunWorkflowHelpers().applyRerunPreviewButtonState;
      if (typeof update === "function") {
        update();
        return;
      }
      const button = typeof byId === "function" ? byId("rerun-start-button") : null;
      if (!button) return;
      const csvPath = String((typeof byId === "function" ? byId("rerun-start-csv-path")?.value : "") || "").trim();
      const disabled = queueRerunBusy || !csvPath;
      button.disabled = disabled;
      button.setAttribute("aria-disabled", disabled ? "true" : "false");
      button.dataset.commandState = queueRerunBusy ? "running" : disabled ? "blocked" : "ready";
      button.title = disabled ? "CSV path and backend preview are required before start." : "Review backend preview and start CSV rerun.";
    }

    function applyQueueRerunPolicyRules(event = null) {
      const applyRules = rerunWorkflowHelpers().applyRerunPolicySelectionRules;
      if (typeof applyRules === "function") applyRules(event);
    }

    function renderQueueRerunHandlingSummary() {
      const renderSummary = rerunWorkflowHelpers().renderRerunHandlingSummary;
      if (typeof renderSummary === "function") renderSummary();
    }

    function renderQueueRerunPreflight() {
      const renderPreflight = rerunWorkflowHelpers().renderRerunQueuePreflight;
      if (typeof renderPreflight === "function") {
        renderPreflight();
        return;
      }
      statusText("rerun-queue-preflight", [
        "CSV rerun preflight is backend-owned.",
        `Preview route: ${RERUN_PREVIEW_ROUTE}`,
        `Start route: ${RERUN_START_ROUTE}`,
        "Normal pipeline start route is not used for CSV rerun rows.",
      ].join("\n"));
    }

    function refreshQueueRerunControlsForInput(event = null) {
      applyQueueRerunPolicyRules(event);
      renderQueueRerunHandlingSummary();
      renderQueueRerunPreflight();
      updateQueueRerunButtonState();
      if (String(event?.target?.id || "").startsWith("rerun-")) {
        scheduleQueueRerunPreviewRefresh();
      }
    }

    function scheduleQueueRerunPreviewRefresh(delayMs = 350) {
      if (queueRerunPreviewRefreshTimer) window.clearTimeout(queueRerunPreviewRefreshTimer);
      queueRerunPreviewRefreshTimer = window.setTimeout(() => {
        queueRerunPreviewRefreshTimer = null;
        refreshRerunPreview({ quiet: true }).catch(() => {});
      }, Math.max(0, Number(delayMs) || 0));
    }

    async function refreshRerunPreview(options = {}) {
      const result = await callRerunWorkflowHelper("refreshRerunPreview", RERUN_PREVIEW_ROUTE, [options]);
      updateQueueRerunButtonState();
      return result;
    }

    async function selectRerunCsvPathForPreview(csvPath, options = {}) {
      const input = nodeById("rerun-start-csv-path");
      const path = String(csvPath || "").trim();
      if (!path) {
        const result = {
          command: "rerun.audit_handoff",
          ok: false,
          severity: "blocked",
          message: "Audit export did not return a CSV path for Queue CSV Rerun.",
          data: { uses_pipeline_start: false },
        };
        statusText("rerun-queue-status", "Blocked");
        statusText("rerun-queue-detail", result.message);
        return result;
      }
      if (!input) {
        const result = {
          command: "rerun.audit_handoff",
          ok: false,
          severity: "error",
          message: "Queue CSV Rerun path input is unavailable.",
          data: { csv_path: path, uses_pipeline_start: false },
        };
        statusText("rerun-queue-status", "Unavailable");
        statusText("rerun-queue-detail", result.message);
        return result;
      }
      if (queueRerunPreviewRefreshTimer) {
        window.clearTimeout(queueRerunPreviewRefreshTimer);
        queueRerunPreviewRefreshTimer = null;
      }
      input.value = path;
      applyQueueRerunPolicyRules({ target: input });
      renderQueueRerunHandlingSummary();
      renderQueueRerunPreflight();
      updateQueueRerunButtonState();
      const handoff = options?.handoff && typeof options.handoff === "object" ? options.handoff : {};
      const rowCount = Number(options?.rowCount || options?.row_count || handoff.row_count || 0);
      const countText = Number.isFinite(rowCount) && rowCount > 0 ? ` (${rowCount} row(s))` : "";
      statusText("rerun-queue-status", "CSV selected");
      statusText(
        "rerun-queue-detail",
        `Audit export selected ${path}${countText}. Backend preview route: ${RERUN_PREVIEW_ROUTE}.`
      );
      if (options?.preview === false) {
        return {
          command: "rerun.audit_handoff",
          ok: true,
          severity: "ok",
          status: "selected",
          message: "Audit rerun CSV selected in Queue.",
          data: { csv_path: path, uses_pipeline_start: false },
        };
      }
      return refreshRerunPreview({ quiet: false, source: options?.source || "audit_handoff" });
    }

    async function refreshRerunResults(options = {}) {
      try {
        const result = await getRerunResults();
        renderRerunResults(result);
        return result;
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        if (!options.quiet) {
          statusText("rerun-results-panel", `Rerun state failed to load: ${message}`);
        }
        return null;
      }
    }

    async function inspectSelectedRerunCsv() {
      return callRerunWorkflowHelper("inspectSelectedRerunCsv", RERUN_PREVIEW_ROUTE);
    }

    async function openSelectedRerunCsv(target) {
      return callRerunWorkflowHelper("openSelectedRerunCsv", RERUN_OPEN_ROUTE, [target]);
    }

    async function openRerunRowTarget(rowKey, target) {
      const request = { row_key: rowKey, target };
      const result = await postRerunOpen(request);
      statusText("rerun-queue-detail", result?.message || `Rerun ${target} open request finished.`);
      return result;
    }

    async function openLatestRerunManifest() {
      let rowKey = latestManifestRowKey();
      if (!rowKey) {
        const refreshed = await refreshRerunResults({ quiet: true });
        rowKey = latestManifestRowKey(refreshed);
      }
      if (!rowKey) {
        const message = "No CSV rerun manifest row key is loaded yet. Refresh State after a CSV rerun writes a manifest, then try again.";
        statusText("rerun-queue-detail", message);
        return { command: "rerun.open", ok: false, severity: "info", message };
      }
      return openRerunRowTarget(rowKey, "manifest");
    }

    async function openRerunDiagnosticsTarget(target) {
      const result = await postDiagnosticsOpen(target);
      statusText("rerun-queue-detail", result?.message || `Diagnostics ${target} open request finished.`);
      return result;
    }

    async function showRerunCommandHistory() {
      const result = await getCommandHistory();
      const history = Array.isArray(result?.entries) ? result.entries : [];
      const entries = history.filter(isRerunEvidenceCommand).slice(0, 8);
      if (!history.length) {
        statusText("rerun-queue-detail", "No command history is loaded yet. CSV rerun starts, controls, row opens, and diagnostics opens will appear here after they run.");
        return result;
      }
      if (!entries.length) {
        statusText("rerun-queue-detail", "No CSV rerun or rerun evidence open commands were found in recent command history.");
        return result;
      }
      statusText("rerun-queue-detail", [
        `Last ${entries.length} CSV rerun evidence command${entries.length === 1 ? "" : "s"}:`,
        ...entries.map(rerunCommandHistoryLine),
      ].join("\n"));
      return result;
    }

    async function promoteRerunRowToPending(rowKey) {
      const key = String(rowKey || "").trim();
      if (!key) throw new Error("No CSV rerun row was selected for promotion.");
      const dryRun = await postRerunPromoteDryRun(key);
      if (!dryRun || dryRun.ok === false) {
        statusText("rerun-queue-detail", dryRun?.message || "Rerun promote dry-run failed.");
        return dryRun;
      }
      const fingerprint = String(dryRun?.data?.dry_run_fingerprint || "").trim();
      if (!fingerprint) throw new Error("Rerun promote dry-run did not return a fingerprint.");
      if (!window.confirm("Promote this CSV rerun review output into Pending Publish?")) {
        const canceled = { command: "rerun.promote", ok: false, severity: "info", message: "Rerun promote canceled." };
        statusText("rerun-queue-detail", canceled.message);
        return canceled;
      }
      const request = { row_key: key, dry_run_fingerprint: fingerprint, confirm_promote: true };
      const result = await postRerunPromote(request);
      statusText("rerun-queue-detail", result?.message || "Rerun promote request finished.");
      await refreshRerunResults({ quiet: true });
      return result;
    }

    async function requestRerunContinue(manifestKey) {
      setQueueRerunBusy(true);
      try {
          return await callRerunWorkflowHelper("requestRerunContinue", RERUN_CONTINUE_ROUTE, [manifestKey]);
      } finally {
        setQueueRerunBusy(false);
        refreshRerunResults({ quiet: true }).catch(() => {});
      }
    }

    async function stopRerunAfterCurrent() {
      if (!window.confirm("Request CSV rerun Stop After Current? The backend writes only the rerun stop marker.")) {
        const canceled = { command: "rerun.control", ok: false, severity: "info", message: "Stop After Current canceled." };
        statusText("rerun-queue-detail", canceled.message);
        return canceled;
      }
      setQueueRerunBusy(true);
      try {
        const result = await postRerunControlStopAfterCurrent();
        statusText("rerun-queue-detail", result?.message || "Stop After Current request finished.");
        await refreshRerunResults({ quiet: true });
        return result;
      } finally {
        setQueueRerunBusy(false);
      }
    }

    async function checkNetworkRerunStartDryRun() {
      return callRerunWorkflowHelper("checkNetworkRerunStartDryRunFromForm", RERUN_NETWORK_START_DRY_RUN_ROUTE);
    }

    async function startRerunFromForm(options = {}) {
      if (queueRerunBusy) {
        statusText("rerun-queue-status", "Busy");
        statusText("rerun-queue-detail", "CSV rerun command is already in progress.");
        return null;
      }
      setQueueRerunBusy(true);
      try {
        return await callRerunWorkflowHelper("startRerunFromForm", RERUN_START_ROUTE, [options]);
      } finally {
        setQueueRerunBusy(false);
        refreshRerunResults({ quiet: true }).catch(() => {});
      }
    }

    function wireClick(id, handler) {
      const button = typeof byId === "function" ? byId(id) : null;
      if (!button || button.dataset.queueRerunBound === "true") return;
      button.dataset.queueRerunBound = "true";
      button.addEventListener("click", handler);
    }

    function initQueueRerunEvents() {
      if (!document || document.__queueRerunEventsBound === true) return;
      document.__queueRerunEventsBound = true;
      [
        "rerun-start-csv-path",
        "rerun-start-target-mode",
        "rerun-network-minimum-workers",
        "rerun-start-execution-mode",
        "rerun-start-window-size",
        "rerun-start-destination-mode",
        "rerun-start-collision-policy",
        "rerun-start-confirm-source-overwrite",
        "rerun-scope-enabled-only",
        "rerun-scope-skip-blocked",
        "rerun-scope-skip-warning-rows",
        "rerun-scope-first-n",
        "rerun-scope-issue-filter",
        "rerun-scope-bucket-filter",
        "rerun-preview-limit",
      ].forEach((id) => {
        const element = typeof byId === "function" ? byId(id) : null;
        if (!element) return;
        element.addEventListener("input", refreshQueueRerunControlsForInput);
        element.addEventListener("change", refreshQueueRerunControlsForInput);
      });
      wireClick("rerun-inspect-csv-button", () => inspectSelectedRerunCsv().catch((error) => {
        statusText("rerun-queue-detail", error instanceof Error ? error.message : String(error));
      }));
      wireClick("rerun-open-csv-button", () => openSelectedRerunCsv("import_csv").catch((error) => {
        statusText("rerun-queue-detail", error instanceof Error ? error.message : String(error));
      }));
      wireClick("rerun-open-csv-folder-button", () => openSelectedRerunCsv("csv_folder").catch((error) => {
        statusText("rerun-queue-detail", error instanceof Error ? error.message : String(error));
      }));
      wireClick("rerun-open-latest-manifest-button", () => openLatestRerunManifest().catch((error) => {
        statusText("rerun-queue-detail", error instanceof Error ? error.message : String(error));
      }));
      wireClick("rerun-open-run-logs-button", () => openRerunDiagnosticsTarget("run_logs").catch((error) => {
        statusText("rerun-queue-detail", error instanceof Error ? error.message : String(error));
      }));
      wireClick("rerun-open-last-stdout-button", () => openRerunDiagnosticsTarget("last_stdout_log").catch((error) => {
        statusText("rerun-queue-detail", error instanceof Error ? error.message : String(error));
      }));
      wireClick("rerun-open-last-stderr-button", () => openRerunDiagnosticsTarget("last_stderr_log").catch((error) => {
        statusText("rerun-queue-detail", error instanceof Error ? error.message : String(error));
      }));
      wireClick("rerun-open-active-jobs-button", () => openRerunDiagnosticsTarget("active_jobs").catch((error) => {
        statusText("rerun-queue-detail", error instanceof Error ? error.message : String(error));
      }));
      wireClick("rerun-show-command-history-button", () => showRerunCommandHistory().catch((error) => {
        statusText("rerun-queue-detail", error instanceof Error ? error.message : String(error));
      }));
      wireClick("rerun-start-button", () => startRerunFromForm({ dry_run: false }));
      wireClick("rerun-network-start-dry-run-button", () => checkNetworkRerunStartDryRun().catch((error) => {
        statusText("rerun-queue-detail", error instanceof Error ? error.message : String(error));
      }));
      wireClick("rerun-results-refresh-button", () => refreshRerunResults().catch((error) => {
        statusText("rerun-queue-detail", error instanceof Error ? error.message : String(error));
      }));
      wireClick("rerun-stop-after-current-button", () => stopRerunAfterCurrent().catch((error) => {
        statusText("rerun-queue-detail", error instanceof Error ? error.message : String(error));
      }));
      const stateFilter = nodeById("rerun-state-status-filter");
      if (stateFilter && stateFilter.dataset.queueRerunBound !== "true") {
        stateFilter.dataset.queueRerunBound = "true";
        stateFilter.addEventListener("change", () => renderRerunQueueStateRows(lastRerunResultsPayload));
      }
      applyQueueRerunPolicyRules();
      renderQueueRerunHandlingSummary();
      renderQueueRerunPreflight();
      refreshRerunPreview({ quiet: true }).catch(() => {});
      refreshRerunResults({ quiet: true }).catch(() => {});
      updateQueueRerunButtonState();
    }

    return {
      RERUN_PREVIEW_ROUTE,
      RERUN_NETWORK_PREVIEW_ROUTE,
      RERUN_NETWORK_START_DRY_RUN_ROUTE,
      RERUN_NETWORK_START_ROUTE,
      RERUN_START_ROUTE,
      RERUN_RESULTS_ROUTE,
      RERUN_CONTROL_ROUTE,
      RERUN_CONTINUE_ROUTE,
      RERUN_OPEN_ROUTE,
      RERUN_PROMOTE_DRY_RUN_ROUTE,
      RERUN_PROMOTE_ROUTE,
      DIAGNOSTICS_OPEN_ROUTE,
      COMMAND_HISTORY_ROUTE,
      postRerunPreview,
      postRerunNetworkPreview,
      postRerunNetworkStartDryRun,
      postRerunNetworkStart,
      postRerunStart,
      postRerunControlStopAfterCurrent,
      postRerunControlPause,
      postRerunContinue,
      postRerunOpen,
      postDiagnosticsOpen,
      postRerunPromoteDryRun,
      postRerunPromote,
      getRerunResults,
      getCommandHistory,
      renderRerunResults,
      renderRerunQueueStateRows,
      initQueueRerunEvents,
      refreshQueueRerunControlsForInput,
      scheduleQueueRerunPreviewRefresh,
      refreshRerunPreview,
      selectRerunCsvPathForPreview,
      refreshRerunResults,
      inspectSelectedRerunCsv,
      openSelectedRerunCsv,
      openRerunRowTarget,
      openLatestRerunManifest,
      openRerunDiagnosticsTarget,
      showRerunCommandHistory,
      promoteRerunRowToPending,
      requestRerunContinue,
      stopRerunAfterCurrent,
      checkNetworkRerunStartDryRun,
      startRerunFromForm,
      setQueueRerunBusy,
      updateQueueRerunButtonState,
    };
  }

  window.__queueRerunModule = {
    createQueueRerunModule,
  };
})();
