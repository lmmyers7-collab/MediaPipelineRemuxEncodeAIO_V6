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

  function statusChipState(status, label) {
    const raw = normalizedTableStatus(status || label);
    if (["ok", "ready", "safe", "healthy", "match", "new", "completed", "complete"].includes(raw)) return "ok";
    if (["blocked", "failed", "failure", "error", "missing", "do_not_drain"].includes(raw)) return "blocked";
    if (["warning", "review", "unknown", "limited", "hold", "held"].includes(raw)) return "warning";
    if (["changed", "active", "processing", "running"].includes(raw)) return "changed";
    if (raw.includes("fail") || raw.includes("block") || raw.includes("missing")) return "blocked";
    if (raw.includes("warning") || raw.includes("review") || raw.includes("unknown")) return "warning";
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
  };
  window.byId = byId;
  window.setText = setText;
  window.setTextState = setTextState;
  window.clearRows = clearRows;
  window.appendCells = appendCells;
  window.filterRows = filterRows;
  window.makeRowSelectable = makeRowSelectable;
  window.updateTableStatusLegend = updateTableStatusLegend;
  window.formatStatusCounts = formatStatusCounts;
  window.tableStatusFilterLabel = tableStatusFilterLabel;
  window.tableStatusMatchesFilter = tableStatusMatchesFilter;
  window.filterRowsByStatus = filterRowsByStatus;
  window.filterRowsByInvestigation = filterRowsByInvestigation;
})();
