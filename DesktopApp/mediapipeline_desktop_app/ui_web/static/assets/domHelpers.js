(function () {
  function byId(id) {
    return document.getElementById(id);
  }

  function setText(id, value) {
    const node = byId(id);
    if (node) node.textContent = value;
  }

  function clearRows(tbody, columns, message) {
    if (!tbody) return;
    tbody.replaceChildren();
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = columns;
    cell.textContent = message;
    row.appendChild(cell);
    tbody.appendChild(row);
  }

  /**
   * appendCells(row, values[, cellClasses])
   *
   * Appends <td> elements to a <tr>.
   *
   * @param {HTMLTableRowElement} row
   * @param {Array} values  — cell text values (null/undefined → "")
   * @param {Array|null} cellClasses  — optional; per-cell class string or null/""
   *   e.g. ["", "num", "", "num"] applies "num" to columns 1 and 3.
   *   Callers that don't need per-cell classes can omit this argument entirely —
   *   all existing call sites are unaffected.
   */
  function appendCells(row, values, cellClasses) {
    values.forEach((value, i) => {
      const cell = document.createElement("td");
      cell.textContent = value === null || value === undefined ? "" : String(value);
      if (cellClasses && cellClasses[i]) cell.className = cellClasses[i];
      row.appendChild(cell);
    });
  }

  function filterRows(rows, filterText, fields) {
    const needle = String(filterText || "").trim().toLowerCase();
    if (!needle) return rows;
    return rows.filter((item) => fields.some((field) => String(item[field] || "").toLowerCase().includes(needle)));
  }

  function deferDomWork(fn) {
    if (typeof window.requestAnimationFrame === "function") {
      window.requestAnimationFrame(fn);
    } else {
      window.setTimeout(fn, 0);
    }
  }

  function scrollSelectedRowIntoView(row) {
    if (!row || !row.classList.contains("is-selected")) return;
    deferDomWork(() => {
      try {
        row.scrollIntoView({ block: "nearest", inline: "nearest" });
      } catch (_) {
        row.scrollIntoView(false);
      }
    });
  }

  function selectableRowsFor(row) {
    const tbody = row?.closest ? row.closest("tbody") : null;
    if (!tbody) return [];
    return Array.from(tbody.querySelectorAll('tr[data-selectable-row="true"]'));
  }

  function moveSelectableRowFocus(row, delta) {
    const rows = selectableRowsFor(row);
    const index = rows.indexOf(row);
    const next = rows[index + delta];
    if (!next) return;
    next.focus();
    next.click();
  }

  function makeRowSelectable(row, onSelect, options = {}) {
    if (!row) return;
    const selected = Boolean(options.selected);
    row.dataset.selectableRow = "true";
    row.tabIndex = 0;
    row.setAttribute("role", "row");
    row.setAttribute("aria-selected", selected ? "true" : "false");
    row.classList.toggle("is-selected", selected);
    if (options.label) row.setAttribute("aria-label", options.label);
    row.addEventListener("click", () => onSelect());
    row.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        onSelect();
      } else if (event.key === "ArrowDown") {
        event.preventDefault();
        moveSelectableRowFocus(row, 1);
      } else if (event.key === "ArrowUp") {
        event.preventDefault();
        moveSelectableRowFocus(row, -1);
      }
    });
    if (options.scrollOnRender === true) {
      scrollSelectedRowIntoView(row);
    }
  }

  function normalizedTableStatus(value) {
    return String(value || "").trim().toLowerCase() || "normal";
  }

  function normalizeBackendStatusState(value) {
    const raw = normalizedTableStatus(value);
    const aliases = {
      error: "failed",
      failure: "failed",
      healthy: "match",
      ok: "match",
      complete: "completed",
      done: "completed",
      published: "completed",
      pending_publish: "publishing",
      pending: "publishing",
      validation_needed: "validation-needed",
      health_check: "health-check",
      do_not_drain: "failed",
      do_not_launch: "blocked",
      review: "warning",
      active: "running",
      unavailable: "unknown",
      "not available": "unknown",
      not_available: "unknown",
    };
    const normalized = aliases[raw] || raw;
    return [
      "blocked",
      "failed",
      "warning",
      "ready",
      "match",
      "completed",
      "skipped",
      "parked",
      "publishing",
      "validation-needed",
      "health-check",
      "running",
      "paused",
      "retrying",
      "changed",
      "unknown",
      "empty",
      "normal",
    ].includes(normalized) ? normalized : "";
  }

  function backendRowStatusState(row, fallback) {
    const input = row && typeof row === "object" ? row : {};
    const operatorSeverity = normalizedTableStatus(input.operator_severity || "");
    const diagnosticSeverity = normalizedTableStatus(input.diagnostic_severity || "");
    const drainRecommendation = normalizedTableStatus(input.drain_recommendation || "");
    if (drainRecommendation === "do_not_drain" || diagnosticSeverity === "error" || diagnosticSeverity === "critical" || input.local_exists === false) return "failed";
    if (operatorSeverity === "error" || operatorSeverity === "critical" || input.output_exists === false || input.blocked_reason || input.blocked_reason_code) return "blocked";
    const candidates = [
      input.operator_status_state,
      input.diagnostic_status_state,
      input.status_state,
      input.table_status_state,
      input.ui_status_state,
      fallback,
    ];
    for (const candidate of candidates) {
      const state = normalizeBackendStatusState(candidate);
      if ((state === "match" || state === "ready") && (operatorSeverity === "warning" || diagnosticSeverity === "warning")) return "warning";
      if (state && state !== "normal") return state;
    }
    return "";
  }

  function statusChipState(status, label) {
    const raw = normalizedTableStatus(status || label);
    if (["ok", "safe", "healthy", "match", "new"].includes(raw)) return "ok";
    if (["ready"].includes(raw)) return "ready";
    if (["completed", "complete", "done", "published"].includes(raw)) return "completed";
    if (["skipped", "skip", "excluded"].includes(raw)) return "skipped";
    if (["parked", "park"].includes(raw)) return "warning";
    if (["health-check", "health_check", "health check"].includes(raw)) return "validation-needed";
    if (["failed", "failure", "error"].includes(raw)) return "failed";
    if (["blocked", "missing", "do_not_drain"].includes(raw)) return "blocked";
    if (["validation_needed", "validation-needed", "needs_validation"].includes(raw)) return "validation-needed";
    if (["warning", "review", "unknown", "limited", "hold", "held"].includes(raw)) return "warning";
    if (["changed"].includes(raw)) return "changed";
    if (["active", "processing", "running", "encoding", "remuxing", "copying", "scanning", "validating"].includes(raw)) return "running";
    if (["paused", "pause_pending", "paused_pending"].includes(raw)) return "paused";
    if (["retrying", "retry"].includes(raw)) return "retrying";
    if (["publishing", "draining"].includes(raw)) return "publishing";
    if (raw.includes("fail") || raw.includes("error")) return "failed";
    if (raw.includes("block") || raw.includes("missing")) return "blocked";
    if (raw.includes("warning") || raw.includes("review") || raw.includes("unknown")) return "warning";
    if (raw.includes("validation")) return "validation-needed";
    if (raw.includes("retry")) return "retrying";
    if (raw.includes("publish") || raw.includes("drain")) return "publishing";
    if (raw.includes("pause")) return "paused";
    if (raw.includes("running") || raw.includes("processing") || raw.includes("active")) return "running";
    if (raw.includes("skip") || raw.includes("exclude")) return "skipped";
    if (raw.includes("complete") || raw.includes("done")) return "completed";
    if (raw.includes("ready") || raw.includes("healthy") || raw.includes("ok")) return "ok";
    return "normal";
  }

  function makeStatusChip(label, status) {
    const span = document.createElement("span");
    const text = String(label || status || "unknown").trim() || "unknown";
    span.className = "status-chip";
    span.dataset.status = statusChipState(status, text);
    span.textContent = text;
    span.tabIndex = 0;
    span.title = `Status: ${text}. Color meaning: ${span.dataset.status}.`;
    span.setAttribute("aria-label", span.title);
    return span;
  }

  function setCellStatusChip(cell, label, status) {
    if (!cell) return;
    const text = String(label || status || "unknown").trim() || "unknown";
    cell.textContent = text;
    cell.replaceChildren(makeStatusChip(text, status));
  }

  function tableStatusLegendText(tbody, label = "Table") {
    const rows = tbody ? Array.from(tbody.querySelectorAll('tr[data-selectable-row="true"]')) : [];
    if (!rows.length) return `${label}: no selectable rows.`;
    const counts = {};
    rows.forEach((row) => {
      const status = normalizedTableStatus(row.dataset.status);
      counts[status] = (counts[status] || 0) + 1;
    });
    const selectedCount = rows.filter((row) => row.classList.contains("is-selected")).length;
    const statusText = Object.keys(counts).sort().map((key) => `${key}=${counts[key]}`).join(", ");
    return `${label}: ${rows.length} selectable row${rows.length === 1 ? "" : "s"}, ${selectedCount} selected. Status mix: ${statusText}. Keyboard: Enter/Space selects focused row; Up/Down moves selection.`;
  }

  function updateTableStatusLegend(id, tbody, label = "Table") {
    setText(id, tableStatusLegendText(tbody, label));
  }

  function countRowsByStatus(rows, statusOf) {
    const counts = {};
    const rowList = Array.isArray(rows) ? rows : [];
    const resolve = typeof statusOf === "function" ? statusOf : (row) => row?.status;
    rowList.forEach((row) => {
      const status = normalizedTableStatus(resolve(row));
      counts[status] = (counts[status] || 0) + 1;
    });
    return counts;
  }

  function formatStatusCounts(counts) {
    const entries = counts && typeof counts === "object" ? Object.entries(counts) : [];
    if (!entries.length) return "none";
    return entries
      .sort(([left], [right]) => String(left).localeCompare(String(right)))
      .map(([status, count]) => `${status || "normal"}=${count}`)
      .join(", ");
  }

  function tableStatusFilterLabel(value) {
    const normalized = normalizedTableStatus(value);
    if (normalized === "review") return "review only";
    if (normalized === "blocked") return "blocked/failed";
    if (normalized === "warning") return "warning";
    if (normalized === "ready") return "ready/healthy";
    return "all";
  }

  function tableStatusMatchesFilter(status, filterValue) {
    const normalized = normalizedTableStatus(status);
    const filter = normalizedTableStatus(filterValue);
    if (!filter || filter === "all" || filter === "normal") return true;
    if (filter === "review") return ["blocked", "failed", "warning", "unknown"].includes(normalized);
    if (filter === "blocked") return ["blocked", "failed"].includes(normalized);
    if (filter === "ready") return ["ready", "match"].includes(normalized);
    return normalized === filter;
  }

  function filterRowsByStatus(rows, statusFilter, statusOf) {
    const rowList = Array.isArray(rows) ? rows : [];
    const resolve = typeof statusOf === "function" ? statusOf : (row) => row?.status;
    return rowList.filter((row) => tableStatusMatchesFilter(resolve(row), statusFilter));
  }

  function tableInvestigationFilterLabel(value) {
    const normalized = normalizedTableStatus(value);
    if (!normalized || normalized === "all" || normalized === "normal") return "all";
    return normalized.replace(/_/g, " ");
  }

  function filterRowsByInvestigation(rows, investigationFilter, matchesFilter) {
    const rowList = Array.isArray(rows) ? rows : [];
    const filter = normalizedTableStatus(investigationFilter);
    if (!filter || filter === "all" || typeof matchesFilter !== "function") return rowList;
    return rowList.filter((row) => matchesFilter(row, filter));
  }

  /**
   * stateFromStatusText(text) → state string
   *
   * Infers a data-state value from a human-readable status string using
   * lightweight keyword matching.  Call sites that know the state explicitly
   * should pass it directly to setTextState() rather than relying on inference.
   *
   * Returns one of: "blocked" | "warning" | "ok" | "loading" | "empty" | ""
   */
  function stateFromStatusText(text) {
    const t = String(text || "").trim().toLowerCase();
    if (!t) return "empty";
    if (t === "not loaded" || t === "not selected" || t === "not available"
        || t === "idle" || t === "none" || t === "no rows" || t === "not evaluated"
        || t.startsWith("no ") || t === "unknown") return "empty";
    if (t === "loading" || t === "loading..." || t === "checking"
        || t === "updating" || t === "requesting") return "loading";
    if (t.includes("blocked") || t.includes("failed") || t.includes("error")
        || t === "missing" || t.includes("unavailable")) return "blocked";
    if (t.includes("warning") || t.includes("review") || t === "limited"
        || t === "active work" || t === "active controls") return "warning";
    if (t === "ready" || t === "safe" || t === "ok" || t === "pass"
        || t === "enabled" || t === "aligned" || t.startsWith("ready")
        || t.includes("complete")) return "ok";
    return "";
  }

  /**
   * setTextState(id, text[, state])
   *
   * Sets `textContent` via setText() and simultaneously writes `dataset.state`
   * on the element.  If `state` is omitted, it is inferred from `text` by
   * stateFromStatusText().  Pass an explicit empty string to clear the state.
   */
  function setTextState(id, text, state) {
    setText(id, text);
    const node = byId(id);
    if (!node) return;
    node.dataset.state = state !== undefined ? String(state) : stateFromStatusText(text);
  }

  function filterResultSummaryLines(options = {}) {
    const label = options.label || "Filter";
    const allRows = Array.isArray(options.allRows) ? options.allRows : [];
    const visibleRows = Array.isArray(options.visibleRows) ? options.visibleRows : [];
    const filterText = String(options.filterText || "").trim();
    const statusFilter = String(options.statusFilter || "all").trim() || "all";
    const investigationFilter = String(options.investigationFilter || "all").trim() || "all";
    const investigationLabel = options.investigationLabel || tableInvestigationFilterLabel(investigationFilter);
    const statusOf = typeof options.statusOf === "function" ? options.statusOf : (row) => row?.status;
    const reviewStatuses = new Set(
      (Array.isArray(options.reviewStatuses) ? options.reviewStatuses : ["blocked", "failed", "warning"])
        .map((value) => normalizedTableStatus(value)),
    );
    const visibleSet = new Set(visibleRows);
    const hiddenReviewRows = allRows.filter((row) => {
      return !visibleSet.has(row) && reviewStatuses.has(normalizedTableStatus(statusOf(row)));
    }).length;
    const decisionName = options.decisionName || "operator";
    const lines = [
      `${label}: text=${filterText ? `"${filterText}"` : "none"}; status=${tableStatusFilterLabel(statusFilter)}; view=${investigationLabel}; showing ${visibleRows.length} of ${allRows.length} row${allRows.length === 1 ? "" : "s"}.`,
      `Visible status mix: ${formatStatusCounts(countRowsByStatus(visibleRows, statusOf))}.`,
    ];
    if (filterText || normalizedTableStatus(statusFilter) !== "all" || normalizedTableStatus(investigationFilter) !== "all") {
      lines.push(`Hidden review rows: ${hiddenReviewRows}.`);
      if (hiddenReviewRows > 0) {
        lines.push(`Operator note: clear or change this filter before ${decisionName} decisions; blocked/warning rows are currently hidden.`);
      } else {
        lines.push(`Operator note: this filter is not hiding blocked/warning rows in the loaded payload.`);
      }
    } else {
      lines.push("Operator note: no text filter is hiding rows.");
    }
    const limit = Number(options.limit || 0);
    if (limit > 0 && visibleRows.length > limit) {
      lines.push(`Display cap: only the first ${limit} filtered rows are rendered. Refine the filter or use backend diagnostics before acting on row counts.`);
    }
    lines.push(options.guardrail || "Mutation guardrail: filters are display-only and never change backend command scope.");
    return lines;
  }

  function selectedRowAtAGlanceLines(options = {}) {
    const item = options.item || null;
    const title = options.title || "Selected row";
    const authority = options.authority || "Authority: this summary is read-only.";
    if (!item) {
      return [
        `${title}: none`,
        options.emptyNextStep || "Next step: select a row to review backend evidence.",
        authority,
      ];
    }
    return [
      `${title}: ${options.label || "(unnamed row)"}`,
      `Trust/status: ${options.trustStatus || "not reported"}; at-a-glance=${options.atAGlanceStatus || "No selection"}`,
      `${options.proofLabel || "Proof"}: ${options.proof || "not reported"}`,
      `Primary concern: ${options.primaryConcern || "no primary concern reported"}`,
      `Safe next step: ${options.safeNextStep || "Review backend evidence before acting."}`,
      `Filter visibility: ${options.filterVisibility || "not evaluated"}`,
      authority,
    ];
  }

  function humanizeReviewFlagToken(value) {
    return String(value || "")
      .replace(/^consistency:/i, "")
      .replace(/^runtime:/i, "")
      .replace(/^runtime_error:/i, "")
      .replace(/^runtime_outcome:/i, "")
      .replace(/^blocked:/i, "")
      .replace(/[_:.-]+/g, " ")
      .replace(/\s+/g, " ")
      .trim()
      .toLowerCase();
  }

  function reviewFlagExplanation(flag) {
    const raw = String(flag || "").trim();
    if (!raw) return "";
    const normalized = raw.toLowerCase();
    const readable = humanizeReviewFlagToken(raw);
    if (/tv_parse|season|episode|parse/.test(normalized)) {
      return `- ${raw}: title/episode parsing is not trusted. Read the blocker, Queue Snapshot, Last Stderr, and Run Logs before launch.`;
    }
    if (/bad_extension|unsupported|codec|format/.test(normalized)) {
      return `- ${raw}: this source or stream may not be supported by the current route. Check route evidence and diagnostics before processing.`;
    }
    if (/already_processed|duplicate/.test(normalized)) {
      return `- ${raw}: backend evidence suggests duplicate work or an existing output. Compare Completed, Pending Publish, and sidecar proof before reprocessing.`;
    }
    if (/missing_output|output_path_missing|output_missing|publish_missing_output/.test(normalized)) {
      return `- ${raw}: expected output proof is missing. Check Completed Manifest, Pending Publish, output folder, Run Logs, and Last Stderr before rerun or cleanup.`;
    }
    if (/missing_sidecar|sidecar/.test(normalized)) {
      return `- ${raw}: sidecar or metadata proof is missing or inconsistent. Inspect sidecar state before cleanup, rerun, library decisions, or output acceptance.`;
    }
    if (/size_growth|growth_over_5|oversize|larger/.test(normalized)) {
      return `- ${raw}: output grew beyond the size-review threshold. Compare route, encoder, settings, and logs before accepting the larger file as intentional.`;
    }
    if (normalized === "runtime_checks_deferred") {
      return `- ${raw}: backend source/output checks run only when processing starts. The queue snapshot cannot prove launch-time file stability yet.`;
    }
    if (normalized.startsWith("runtime_error:")) {
      return `- ${raw}: previous runtime error ${readable || "not reported"} is attached to this row. Read Last Stderr and Latest Failure before retry, rerun, or cleanup.`;
    }
    if (normalized.startsWith("runtime_outcome:")) {
      return `- ${raw}: previous runtime outcome was ${readable || "not reported"}. Treat it as run-history evidence and compare logs before acting.`;
    }
    if (normalized === "runtime_outcome_stale") {
      return `- ${raw}: runtime history is stale. Use it as context only; current disk/log proof still needs review.`;
    }
    if (normalized.startsWith("runtime:")) {
      return `- ${raw}: backend runtime check ${readable || "not reported"} happens at processing time, not from this read-only table view.`;
    }
    if (/remux/.test(normalized)) {
      return `- ${raw}: route/output uses remux. Compare container and stream compatibility proof before trusting that no encode is needed.`;
    }
    if (/encode|encoded/.test(normalized)) {
      return `- ${raw}: route/output uses encode. Compare size, audio, subtitle, and log proof before treating the result as accepted.`;
    }
    if (/blocked/.test(normalized)) {
      return `- ${raw}: backend marked this row blocked or review-only. Resolve the backend reason before launch, rerun, cleanup, or acceptance decisions.`;
    }
    return `- ${raw}: backend review marker "${readable || raw}". Use the row guidance and diagnostics before acting.`;
  }

  function reviewFlagExplanationLines(flags, options = {}) {
    const rawFlags = Array.isArray(flags) ? flags : [flags];
    const title = options.title || "Review flag explanations:";
    const emptyMessage = options.emptyMessage || "No backend review flags were reported for this row.";
    const guardrail = options.guardrail || "Mutation guardrail: these explanations only translate already-loaded backend markers and cannot change queue, output, publish, or file state.";
    const limit = Number(options.limit || 8);
    const seen = new Set();
    const explanations = [];
    rawFlags.forEach((flag) => {
      const raw = String(flag || "").trim();
      if (!raw || seen.has(raw)) return;
      seen.add(raw);
      const explanation = reviewFlagExplanation(raw);
      if (explanation) explanations.push(explanation);
    });
    if (!explanations.length) {
      return [title, emptyMessage, guardrail];
    }
    const visible = limit > 0 ? explanations.slice(0, limit) : explanations;
    const lines = [title, ...visible];
    if (limit > 0 && explanations.length > limit) {
      lines.push(`Additional backend markers: ${explanations.length - limit} not shown here; inspect the raw Review flags line for the full list.`);
    }
    lines.push(guardrail);
    return lines;
  }

  function selectedRowDetailDrawerLines(options = {}) {
    const title = options.title || "Selected row detail";
    const summaryLines = Array.isArray(options.summaryLines) ? options.summaryLines.filter(Boolean) : [];
    const bodyLines = Array.isArray(options.bodyLines) ? options.bodyLines.filter((line) => line !== undefined && line !== null) : [];
    const guardrail = options.guardrail || "Mutation guardrail: selected-row detail is read-only and cannot submit backend commands.";
    const lines = [`${title}:`];
    if (summaryLines.length) {
      lines.push("At a glance:", ...summaryLines);
    } else {
      lines.push("At a glance: no selected-row summary available.");
    }
    if (bodyLines.length) {
      lines.push("", "Detail:", ...bodyLines);
    }
    lines.push("", guardrail);
    return lines.filter((line, index, array) => line !== "" || array[index - 1] !== "");
  }

  function formatRefreshTimestamp(value) {
    if (!value) return "not reported";
    const date = value instanceof Date ? value : new Date(value);
    if (Number.isNaN(date.getTime())) return String(value);
    try {
      return date.toLocaleString([], {
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      });
    } catch {
      return date.toISOString();
    }
  }

  function payloadRefreshMeta(payload) {
    return payload && typeof payload === "object" && payload.__mediaPipelineRefreshMeta
      ? payload.__mediaPipelineRefreshMeta
      : {};
  }

  function payloadFreshnessLines(options = {}) {
    const payload = options.payload && typeof options.payload === "object" ? options.payload : {};
    const meta = payloadRefreshMeta(payload);
    const label = options.label || "Payload";
    const rowCount = options.rowCount !== undefined
      ? options.rowCount
      : Array.isArray(payload.rows)
        ? payload.rows.length
        : payload.count;
    const refreshAction = options.refreshAction || "Use Refresh to reload backend state.";
    const lines = [
      `${label} refresh: WebView loaded ${formatRefreshTimestamp(meta.fetched_at)}${meta.name ? ` from ${meta.name}` : ""}; rows=${rowCount ?? "not reported"}.`,
    ];
    if (options.artifactLine) lines.push(options.artifactLine);
    if (options.sourceLine) lines.push(options.sourceLine);
    if (options.readError) lines.push(`Read issue: ${options.readError}`);
    lines.push(`Refresh action: ${refreshAction}`);
    return lines;
  }

  function jsonDetailText(options = {}) {
    const label = options.label || "JSON detail";
    const value = options.value;
    const intro = options.intro || "Read-only structured detail. Select this block to copy it for troubleshooting.";
    const guardrail = options.guardrail || "Mutation guardrail: this viewer only formats already-loaded backend data and does not submit commands.";
    const lines = [
      `${label}:`,
      intro,
      guardrail,
    ];
    if (value === undefined || value === null || value === "") {
      lines.push("", options.emptyMessage || "No JSON payload available.");
      return lines.join("\n");
    }
    try {
      lines.push("", "JSON valid: yes", JSON.stringify(value, null, 2));
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      lines.push("", "JSON valid: no", `Render error: ${message}`);
    }
    return lines.join("\n");
  }

  function renderJsonDetail(id, options = {}) {
    setText(id, jsonDetailText(options));
  }

  function setOptionalDataset(node, key, value) {
    if (!node || !key) return;
    node.dataset[key] = value;
  }

  function renderOpenTargetActionGroups(container, groups, options = {}) {
    if (!container) return { readFirst: 0, openNext: 0 };
    if (!options.append) container.replaceChildren();
    const readFirst = Array.isArray(groups?.readFirst) ? groups.readFirst : [];
    const openNext = Array.isArray(groups?.openNext) ? groups.openNext : [];
    const labelFor = typeof options.labelFor === "function" ? options.labelFor : (action) => action?.label || action?.target || "Open target";
    const titleFor = typeof options.titleFor === "function" ? options.titleFor : (action) => action?.hint || "";
    const classFor = typeof options.classFor === "function" ? options.classFor : () => "secondary-button";
    const onTail = typeof options.onTail === "function" ? options.onTail : null;
    const onOpen = typeof options.onOpen === "function" ? options.onOpen : null;
    const groupDataset = options.groupDataset || "";
    const actionDataset = options.actionDataset || "";
    const targetDataset = options.targetDataset || "";
    const emptyLabel = options.emptyLabel || "No allowlisted action";
    const appendGroup = (labelText, actionRows) => {
      if (!actionRows.length) return;
      const label = document.createElement("span");
      label.className = "action-group-label";
      label.textContent = labelText;
      container.appendChild(label);
      actionRows.forEach((action) => {
        const kind = String(action?.kind || "").trim();
        const target = String(action?.target || "").trim();
        const button = document.createElement("button");
        button.className = classFor(action) || "secondary-button";
        button.type = "button";
        button.textContent = labelFor(action);
        button.title = titleFor(action);
        const groupValue = labelText.toLowerCase().replace(/\s+/g, "-");
        button.dataset.openTargetActionGroup = groupValue;
        button.dataset.openTargetAction = kind;
        button.dataset.openTarget = target;
        setOptionalDataset(button, groupDataset, groupValue);
        setOptionalDataset(button, actionDataset, kind);
        setOptionalDataset(button, targetDataset, target);
        if (kind === "tail" && onTail) {
          button.addEventListener("click", () => onTail(target, action));
        } else if (onOpen) {
          button.addEventListener("click", () => onOpen(target, action));
        }
        container.appendChild(button);
      });
    };
    appendGroup("Read first", readFirst);
    appendGroup("Open next", openNext);
    if (!readFirst.length && !openNext.length && options.showEmpty !== false) {
      const button = document.createElement("button");
      button.className = "secondary-button";
      button.type = "button";
      button.textContent = emptyLabel;
      button.disabled = true;
      button.dataset.openTargetAction = "none";
      container.appendChild(button);
    }
    return { readFirst: readFirst.length, openNext: openNext.length };
  }

  /**
   * Public namespace for shared DOM helpers.
   * Prefer this namespace from new code; flat window.* exports are transitional compatibility aliases when present.
   */
  window.mediaPipelineDom = {
    byId,
    setText,
    stateFromStatusText,
    setTextState,
    clearRows,
    appendCells,
    filterRows,
    makeRowSelectable,
    scrollSelectedRowIntoView,
    normalizeBackendStatusState,
    backendRowStatusState,
    makeStatusChip,
    setCellStatusChip,
    tableStatusLegendText,
    updateTableStatusLegend,
    countRowsByStatus,
    formatStatusCounts,
    tableStatusFilterLabel,
    tableStatusMatchesFilter,
    filterRowsByStatus,
    tableInvestigationFilterLabel,
    filterRowsByInvestigation,
    filterResultSummaryLines,
    selectedRowAtAGlanceLines,
    reviewFlagExplanationLines,
    selectedRowDetailDrawerLines,
    payloadFreshnessLines,
    jsonDetailText,
    renderJsonDetail,
    renderOpenTargetActionGroups,
  };
  window.byId = byId;
  window.setText = setText;
  window.setTextState = setTextState;
  window.clearRows = clearRows;
  window.appendCells = appendCells;
  window.filterRows = filterRows;
  window.makeRowSelectable = makeRowSelectable;
  window.normalizeBackendStatusState = normalizeBackendStatusState;
  window.backendRowStatusState = backendRowStatusState;
  window.updateTableStatusLegend = updateTableStatusLegend;
  window.formatStatusCounts = formatStatusCounts;
  window.tableStatusFilterLabel = tableStatusFilterLabel;
  window.tableStatusMatchesFilter = tableStatusMatchesFilter;
  window.filterRowsByStatus = filterRowsByStatus;
  window.filterRowsByInvestigation = filterRowsByInvestigation;
})();
