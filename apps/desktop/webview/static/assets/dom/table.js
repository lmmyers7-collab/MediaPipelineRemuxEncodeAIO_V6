// dom/table.js
// Split child of domHelpers.js. Owns shared table primitives, row selection, scroll preservation, and open-target action group rendering.

/* eslint-disable max-lines-per-function */
(function () {
  "use strict";

  function createDomTableModule(deps = {}) {
    const byId = typeof deps.byId === "function" ? deps.byId : () => null;
    const DOCUMENT_SCROLL_TOLERANCE = 2;
    const tableUiStates = new WeakMap();
    let tableUiSequence = 0;
    const enhancedTableBodies = new Set([
      "active-job-detail-rows",
      "api-contract-rows",
      "api-contract-safety-rows",
      "audit-launch-log-rows",
      "audit-preview-rows",
      "command-rows",
      "completed-history-rows",
      "completed-rows",
      "diagnostics-log-rows",
      "diagnostics-first-response-rows",
      "diagnostics-state-triage-rows",
      "diagnostics-state-summary-rows",
      "diagnostics-owner-handoff-rows",
      "diagnostics-command-drilldown-rows",
      "diagnostics-command-owner-rows",
      "diagnostics-command-evidence-rows",
      "diagnostics-command-resolution-rows",
      "failure-rows",
      "maintenance-change-ledger-rows",
      "metrics-sources-rows",
      "metrics-worker-rows",
      "network-worker-rows",
      "pending-file-inventory-rows",
      "pending-rows",
      "queue-excluded-rows",
      "queue-review-rows",
      "queue-rows",
      "rename-rows",
      "sample-validation-records",
      "settings-patch-summary-rows",
      "settings-rows",
      "tdarr-matrix-audit-findings-rows",
      "tdarr-matrix-audit-bucket-rows",
      "tdarr-matrix-proof-pack-rows",
      "tdarr-matrix-run-compare-rows",
    ]);
    const stickyColumnCounts = {
      "api-contract-rows": 2,
      "api-contract-safety-rows": 1,
      "audit-launch-log-rows": 2,
      "audit-preview-rows": 2,
      "completed-history-rows": 2,
      "completed-rows": 2,
      "diagnostics-log-rows": 1,
      "diagnostics-first-response-rows": 1,
      "diagnostics-state-triage-rows": 2,
      "diagnostics-state-summary-rows": 1,
      "diagnostics-owner-handoff-rows": 2,
      "diagnostics-command-drilldown-rows": 2,
      "diagnostics-command-owner-rows": 1,
      "diagnostics-command-evidence-rows": 1,
      "diagnostics-command-resolution-rows": 1,
      "failure-rows": 2,
      "maintenance-change-ledger-rows": 1,
      "metrics-sources-rows": 1,
      "metrics-worker-rows": 1,
      "network-worker-rows": 1,
      "pending-file-inventory-rows": 2,
      "pending-rows": 1,
      "queue-excluded-rows": 2,
      "queue-rows": 3,
      "rename-rows": 2,
      "sample-validation-records": 2,
      "settings-patch-summary-rows": 2,
      "settings-rows": 1,
      "tdarr-matrix-audit-findings-rows": 2,
      "tdarr-matrix-audit-bucket-rows": 1,
      "tdarr-matrix-proof-pack-rows": 1,
      "tdarr-matrix-run-compare-rows": 1,
    };
    const tableEmptyStateObservers = new WeakMap();

    function clearRows(tbody, columns, message) {
      if (!tbody) return;
      tbody.replaceChildren();
      const row = document.createElement("tr");
      const cell = document.createElement("td");
      cell.colSpan = columns;
      cell.textContent = message;
      row.appendChild(cell);
      tbody.appendChild(row);
      syncTableEmptyState(tbody);
    }

    function appendCells(row, values, cellClasses) {
      values.forEach((value, i) => {
        const cell = document.createElement("td");
        cell.textContent = value === null || value === undefined ? "" : String(value);
        if (cellClasses && cellClasses[i]) cell.className = cellClasses[i];
        row.appendChild(cell);
      });
    }

    function deferDomWork(fn) {
      if (typeof window.requestAnimationFrame === "function") {
        window.requestAnimationFrame(fn);
      } else {
        window.setTimeout(fn, 0);
      }
    }

    function documentScrollElement() {
      return document.scrollingElement || document.documentElement || document.body || null;
    }

    function maxScrollableTop(node) {
      return Math.max(0, (Number(node?.scrollHeight) || 0) - (Number(node?.clientHeight) || 0));
    }

    function maxScrollableLeft(node) {
      return Math.max(0, (Number(node?.scrollWidth) || 0) - (Number(node?.clientWidth) || 0));
    }

    function scrollElementAllowsUserScroll(node) {
      if (!node) return false;
      if (node.scrollTop > 0 || node.scrollLeft > 0) return true;
      if (typeof window.getComputedStyle !== "function") return true;
      const style = window.getComputedStyle(node);
      if (!style || style.display === "none" || style.visibility === "hidden") return false;
      const values = [style.overflow, style.overflowX, style.overflowY]
        .map((value) => String(value || "").toLowerCase());
      return values.some((value) => value === "auto" || value === "scroll" || value === "overlay");
    }

    function isScrollableElement(node) {
      if (!node) return false;
      const top = Number(node.scrollTop) || 0;
      const left = Number(node.scrollLeft) || 0;
      const maxTop = maxScrollableTop(node);
      const maxLeft = maxScrollableLeft(node);
      return (top > 0 || left > 0 || maxTop > 1 || maxLeft > 1) && scrollElementAllowsUserScroll(node);
    }

    function siblingElementIndex(node) {
      const siblings = Array.from(node?.parentElement?.children || []);
      const index = siblings.indexOf(node);
      return index >= 0 ? index : 0;
    }

    function scrollElementKey(node, index) {
      if (!node) return `missing:${index}`;
      if (node === documentScrollElement() || node === document.documentElement || node === document.body) return "document";
      if (node.id) return `id:${node.id}`;
      if (node.dataset?.scrollPreserveKey) return `scroll-key:${node.dataset.scrollPreserveKey}`;
      const page = node.closest?.("[data-page-panel]")?.dataset?.pagePanel || "";
      const panel = node.closest?.("[data-panel-key]")?.dataset?.panelKey || "";
      const tag = String(node.tagName || "element").toLowerCase();
      const className = String(node.className || "").replace(/\s+/g, ".").slice(0, 80);
      return `path:${page}:${panel}:${tag}:${className}:${siblingElementIndex(node)}:${index}`;
    }

    function captureScrollablePositions(root = document) {
      const entries = [];
      const seen = new Set();
      const addEntry = (node, options = {}) => {
        if (!node || seen.has(node)) return;
        if (!options.force && !isScrollableElement(node)) return;
        seen.add(node);
        entries.push({
          key: scrollElementKey(node, entries.length),
          isDocument: Boolean(options.isDocument),
          node,
          top: Math.max(0, Number(node.scrollTop) || 0),
          left: Math.max(0, Number(node.scrollLeft) || 0),
          maxTop: maxScrollableTop(node),
          maxLeft: maxScrollableLeft(node),
        });
      };
      addEntry(documentScrollElement(), { force: true, isDocument: true });
      if (root?.querySelectorAll) {
        root.querySelectorAll("*").forEach((node) => addEntry(node));
      }
      return { entries };
    }

    function scrollNodeForEntry(entry) {
      if (!entry) return null;
      if (entry.isDocument || entry.key === "document") return documentScrollElement();
      if (entry.node && entry.node.isConnected !== false) return entry.node;
      if (String(entry.key || "").startsWith("id:")) return byId(String(entry.key).slice(3));
      return null;
    }

    function documentScrollMovedAfterRestore(node, entry, restoreState) {
      const lastDocumentPositions = restoreState?.lastDocumentPositions;
      if (!lastDocumentPositions) return false;
      const key = entry.key || "document";
      const last = lastDocumentPositions.get(key);
      if (!last) return false;
      const top = Math.max(0, Number(node.scrollTop) || 0);
      const left = Math.max(0, Number(node.scrollLeft) || 0);
      return Math.abs(top - last.top) > DOCUMENT_SCROLL_TOLERANCE
        || Math.abs(left - last.left) > DOCUMENT_SCROLL_TOLERANCE;
    }

    function rememberDocumentScrollRestore(entry, top, left, restoreState) {
      const lastDocumentPositions = restoreState?.lastDocumentPositions;
      if (!lastDocumentPositions) return;
      lastDocumentPositions.set(entry.key || "document", { top, left });
    }

    function restoreScrollEntry(entry, restoreState = null) {
      const node = scrollNodeForEntry(entry);
      if (!node) return;
      const maxTop = maxScrollableTop(node);
      const maxLeft = maxScrollableLeft(node);
      const requestedTop = Math.max(0, Number(entry.top) || 0);
      const requestedLeft = Math.max(0, Number(entry.left) || 0);
      const top = Math.min(requestedTop, maxTop);
      const left = Math.min(requestedLeft, maxLeft);
      if (entry.isDocument || entry.key === "document") {
        if (documentScrollMovedAfterRestore(node, entry, restoreState)) return;
        // Clamp to the nearest valid offset while refreshed content is shorter;
        // deferred passes can still restore the original position after it expands.
        if (typeof window.scrollTo === "function") {
          window.scrollTo(left, top);
        }
        node.scrollTop = top;
        node.scrollLeft = left;
        rememberDocumentScrollRestore(entry, top, left, restoreState);
        return;
      }
      node.scrollTop = top;
      node.scrollLeft = left;
    }

    function restoreScrollEntries(entries, restoreState) {
      entries.forEach((entry) => restoreScrollEntry(entry, restoreState));
    }

    function restoreScrollablePositions(snapshot) {
      const entries = Array.isArray(snapshot?.entries) ? snapshot.entries : [];
      if (!entries.length) return;
      const restoreState = { lastDocumentPositions: new Map() };
      const apply = () => restoreScrollEntries(entries, restoreState);
      apply();
      deferDomWork(() => {
        apply();
        deferDomWork(apply);
        window.setTimeout(apply, 0);
      });
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
      return Array.from(tbody.querySelectorAll('tr[data-selectable-row="true"]')).filter(selectableRowVisible);
    }

    function selectableRowVisible(row) {
      if (!row || row.hidden || row.getAttribute?.("aria-hidden") === "true") return false;
      const style = typeof window.getComputedStyle === "function" ? window.getComputedStyle(row) : row.style;
      if (!style) return true;
      return style.display !== "none" && style.visibility !== "hidden" && style.visibility !== "collapse";
    }

    function focusRowWithoutDocumentScroll(row) {
      if (typeof row?.focus !== "function") return;
      try {
        row.focus({ preventScroll: true });
      } catch (_) {
        row.focus();
      }
    }

    function moveSelectableRowFocus(row, delta) {
      const rows = selectableRowsFor(row);
      const index = rows.indexOf(row);
      const next = rows[index + delta];
      if (!next) return;
      focusRowWithoutDocumentScroll(next);
      next.click();
    }

    function selectRowInGroup(row) {
      if (!row) return;
      const rows = selectableRowsFor(row);
      rows.forEach((candidate) => {
        const selected = candidate === row;
        candidate.setAttribute("aria-selected", selected ? "true" : "false");
        candidate.classList.toggle("is-selected", selected);
      });
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
      const activate = (event) => {
        if (options.manageSelection !== false) selectRowInGroup(row);
        if (typeof onSelect === "function") onSelect(event);
      };
      row.addEventListener("click", activate);
      row.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          activate(event);
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

    function directEmptyStateForWrap(wrap) {
      return Array.from(wrap?.children || []).find((child) => child?.classList?.contains("empty-state")) || null;
    }

    function syncTableEmptyState(tbody) {
      const table = tbody?.closest?.("table");
      const wrap = table?.closest?.(".table-wrap");
      const empty = directEmptyStateForWrap(wrap);
      if (!empty) return false;
      const isEmpty = allTableDataRows(tbody).length === 0;
      empty.hidden = !isEmpty;
      empty.style.display = isEmpty ? "" : "none";
      empty.dataset.emptyState = isEmpty ? "visible" : "hidden";
      return isEmpty;
    }

    function installTableEmptyStateObserver(table, tbody, wrap) {
      if (!table || !tbody || !wrap || tableEmptyStateObservers.has(tbody)) return;
      syncTableEmptyState(tbody);
      if (typeof MutationObserver !== "function") return;
      const observer = new MutationObserver(() => syncTableEmptyState(tbody));
      observer.observe(tbody, { childList: true });
      tableEmptyStateObservers.set(tbody, observer);
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
            button.addEventListener("click", () => onTail(target, action, button));
          } else if (onOpen) {
            button.addEventListener("click", () => onOpen(target, action, button));
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

    function normalizedTableText(value) {
      return String(value || "").replace(/\s+/g, " ").trim();
    }

    function headerText(th, index) {
      const text = normalizedTableText(th?.textContent);
      return text || `Column ${index + 1}`;
    }

    function primaryHeaderRow(table) {
      return table?.tHead?.rows?.[0] || table?.querySelector?.("thead tr") || null;
    }

    function tableHeaders(table) {
      return Array.from(primaryHeaderRow(table)?.cells || []);
    }

    function firstTableBody(table) {
      return table?.tBodies?.[0] || table?.querySelector?.("tbody") || null;
    }

    function allTableDataRows(tbody) {
      return Array.from(tbody?.rows || []).filter((row) => {
        const cells = Array.from(row?.cells || []);
        return !(cells.length === 1 && Number(cells[0].colSpan) > 1 && row?.dataset?.selectableRow !== "true");
      });
    }

    function tableLabel(table, tbody) {
      const explicit = table?.getAttribute?.("aria-label") || table?.caption?.textContent || "";
      if (normalizedTableText(explicit)) return normalizedTableText(explicit);
      const id = tbody?.id || table?.id || "table";
      return id
        .replace(/-rows$/, "")
        .replace(/-/g, " ")
        .replace(/\b\w/g, (letter) => letter.toUpperCase());
    }

    function stableTableId(table, tbody) {
      if (table.id) return table.id;
      tableUiSequence += 1;
      const base = String(tbody?.id || `table-${tableUiSequence}`).replace(/[^a-zA-Z0-9_-]+/g, "-");
      table.id = `${base}-table`;
      return table.id;
    }

    function shouldEnhanceTable(table, tbody, headers) {
      if (!table || table.dataset.tableUi === "off") return false;
      if (table.closest?.("[data-table-ui='off']")) return false;
      if (table.classList.contains("workflow-table") || table.classList.contains("rename-table")) return true;
      if (enhancedTableBodies.has(tbody?.id || "")) return true;
      return headers.length >= 6;
    }

    function tableColumnCount(state) {
      return state.headers.length;
    }

    function tableVisibleColumnCount(state) {
      return tableColumnCount(state) - state.hiddenColumns.size;
    }

    function ensureTableColgroup(state) {
      let colgroup = state.table.querySelector("colgroup[data-table-ui-colgroup='true']");
      if (!colgroup) {
        colgroup = document.createElement("colgroup");
        colgroup.dataset.tableUiColgroup = "true";
        state.table.insertBefore(colgroup, state.table.firstChild);
      }
      while (colgroup.children.length < state.headers.length) {
        colgroup.appendChild(document.createElement("col"));
      }
      while (colgroup.children.length > state.headers.length) {
        colgroup.lastChild.remove();
      }
      state.colgroup = colgroup;
      return colgroup;
    }

    function cellText(row, index) {
      return normalizedTableText(row?.cells?.[index]?.textContent || "");
    }

    function cellSortValue(row, index) {
      const explicit = normalizedTableText(row?.cells?.[index]?.dataset?.sortValue || "");
      return explicit || cellText(row, index);
    }

    function sortableValue(text) {
      const raw = normalizedTableText(text);
      const lower = raw.toLowerCase();
      const statusRank = {
        blocked: 0,
        failed: 0,
        error: 0,
        warning: 1,
        review: 1,
        parked: 1,
        queued: 2,
        running: 2,
        publishing: 2,
        ready: 3,
        completed: 4,
        ok: 4,
        match: 4,
      };
      if (Object.prototype.hasOwnProperty.call(statusRank, lower)) {
        return { type: "status", value: statusRank[lower], text: lower };
      }
      if (/\d{4}-\d{2}-\d{2}|\d{1,2}\/\d{1,2}\/\d{2,4}/.test(raw)) {
        const parsedDate = Date.parse(raw);
        if (Number.isFinite(parsedDate)) return { type: "date", value: parsedDate, text: lower };
      }
      const numeric = Number(raw.replace(/,/g, "").match(/-?\d+(?:\.\d+)?/)?.[0]);
      if (Number.isFinite(numeric) && /\d/.test(raw)) {
        return { type: "number", value: numeric, text: lower };
      }
      return { type: "text", value: lower, text: lower };
    }

    function compareSortableText(leftText, rightText) {
      const left = sortableValue(leftText);
      const right = sortableValue(rightText);
      if (left.type === right.type && left.type !== "text") {
        if (left.value < right.value) return -1;
        if (left.value > right.value) return 1;
      }
      return left.text.localeCompare(right.text, undefined, { numeric: true, sensitivity: "base" });
    }

    function updateSortIndicators(state) {
      state.headers.forEach((th, index) => {
        const active = state.sortColumn === index;
        const direction = active ? state.sortDirection : "none";
        th.setAttribute("aria-sort", active ? (direction === "desc" ? "descending" : "ascending") : "none");
        const button = th.querySelector(".table-sort-button");
        if (button) {
          button.dataset.sortDirection = direction;
          button.setAttribute("aria-pressed", active ? "true" : "false");
        }
      });
    }

    function applyTableSort(state) {
      if (state.sortColumn < 0 || !state.tbody) return;
      const direction = state.sortDirection === "desc" ? -1 : 1;
      const rows = allTableDataRows(state.tbody);
      state.applying = true;
      rows
        .sort((left, right) => direction * compareSortableText(cellSortValue(left, state.sortColumn), cellSortValue(right, state.sortColumn)))
        .forEach((row) => state.tbody.appendChild(row));
      state.applying = false;
    }

    function statusSummary(rows) {
      const counts = new Map();
      rows.forEach((row) => {
        const status = normalizedTableText(row.dataset?.status || row.querySelector?.("[data-status]")?.dataset?.status || "");
        if (!status) return;
        counts.set(status, (counts.get(status) || 0) + 1);
      });
      return Array.from(counts.entries())
        .sort((left, right) => right[1] - left[1] || left[0].localeCompare(right[0]))
        .slice(0, 4)
        .map(([status, count]) => `${status}: ${count}`)
        .join(" | ");
    }

    function updateTableUiSummary(state) {
      const allRows = allTableDataRows(state.tbody);
      const visibleRows = allRows.filter((row) => !row.hidden);
      state.table.classList.toggle("has-many-rows", allRows.length >= 20);
      if (!state.summaryNode) return;
      const hiddenColumnCount = state.hiddenColumns.size;
      const countText = visibleRows.length === allRows.length
        ? `${allRows.length} rows`
        : `${visibleRows.length} shown / ${allRows.length} rows`;
      const statusText = statusSummary(visibleRows);
      const columnText = hiddenColumnCount ? ` | ${hiddenColumnCount} columns hidden` : "";
      state.summaryNode.textContent = statusText ? `${countText} | ${statusText}${columnText}` : `${countText}${columnText}`;
    }

    function applyColumnVisibility(state) {
      const hidden = state.hiddenColumns;
      const rowGroups = [
        ...Array.from(state.table.tHead?.rows || []),
        ...Array.from(state.tbody?.rows || []),
      ];
      rowGroups.forEach((row) => {
        const cells = Array.from(row.cells || []);
        if (cells.length === 1 && Number(cells[0].colSpan) > 1) return;
        cells.forEach((cell, index) => {
          cell.hidden = hidden.has(index);
        });
      });
      Array.from(state.colgroup?.children || []).forEach((col, index) => {
        col.hidden = hidden.has(index);
      });
      state.columnCheckboxes.forEach((checkbox, index) => {
        checkbox.checked = !hidden.has(index);
        checkbox.disabled = !hidden.has(index) && tableVisibleColumnCount(state) <= 1;
      });
    }

    function nodeWidth(node, fallback = 120) {
      const rectWidth = Number(node?.getBoundingClientRect?.().width) || 0;
      const offsetWidth = Number(node?.offsetWidth) || 0;
      return Math.max(0, rectWidth || offsetWidth || fallback);
    }

    function nodeHeight(node, fallback = 42) {
      const rectHeight = Number(node?.getBoundingClientRect?.().height) || 0;
      const offsetHeight = Number(node?.offsetHeight) || 0;
      return Math.max(0, rectHeight || offsetHeight || fallback);
    }

    function updateStickyColumnOffsets(state) {
      const stickyCount = Math.min(state.stickyColumns, state.headers.length);
      let left = 0;
      state.table.style.setProperty("--table-header-height", `${Math.max(32, nodeHeight(primaryHeaderRow(state.table), 42))}px`);
      for (let index = 0; index < state.headers.length; index += 1) {
        const sticky = index < stickyCount && !state.hiddenColumns.has(index);
        const cells = [
          ...Array.from(state.table.tHead?.rows || []).map((row) => row.cells[index]).filter(Boolean),
          ...Array.from(state.tbody?.rows || []).map((row) => {
            const rowCells = Array.from(row.cells || []);
            if (rowCells.length === 1 && Number(rowCells[0].colSpan) > 1) return null;
            return row.cells[index];
          }).filter(Boolean),
        ];
        cells.forEach((cell) => {
          if (sticky) {
            cell.dataset.stickyColumn = String(index + 1);
            cell.style.setProperty("--table-sticky-left", `${left}px`);
          } else {
            delete cell.dataset.stickyColumn;
            cell.style.removeProperty("--table-sticky-left");
          }
        });
        if (sticky) left += Math.max(64, nodeWidth(state.headers[index]));
      }
      state.table.classList.toggle("has-sticky-columns", stickyCount > 0);
    }

    function applyTableUiState(state) {
      applyColumnVisibility(state);
      applyTableSort(state);
      updateSortIndicators(state);
      updateStickyColumnOffsets(state);
      updateTableUiSummary(state);
    }

    function scheduleTableUiRefresh(state) {
      if (state.refreshScheduled) return;
      state.refreshScheduled = true;
      deferDomWork(() => {
        state.refreshScheduled = false;
        if (state.applying) return;
        applyTableUiState(state);
      });
    }

    function setColumnWidth(state, index, width) {
      const col = state.colgroup?.children?.[index];
      if (!col) return;
      col.style.width = `${Math.max(64, Math.round(width))}px`;
      updateStickyColumnOffsets(state);
    }

    function installColumnResizeHandle(state, th, index, label) {
      const handle = document.createElement("button");
      handle.type = "button";
      handle.className = "table-column-resizer";
      handle.setAttribute("aria-label", `Resize ${label} column`);
      handle.title = `Resize ${label}`;
      th.dataset.tableResizable = "true";
      const resizeFrom = (startWidth, delta) => setColumnWidth(state, index, startWidth + delta);
      handle.addEventListener("keydown", (event) => {
        if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
        event.preventDefault();
        const current = nodeWidth(th);
        resizeFrom(current, event.key === "ArrowRight" ? 24 : -24);
      });
      handle.addEventListener("pointerdown", (event) => {
        event.preventDefault();
        const startX = Number(event.clientX) || 0;
        const startWidth = nodeWidth(th);
        const onMove = (moveEvent) => resizeFrom(startWidth, (Number(moveEvent.clientX) || startX) - startX);
        const onUp = () => {
          document.removeEventListener("pointermove", onMove);
          document.removeEventListener("pointerup", onUp);
        };
        document.addEventListener("pointermove", onMove);
        document.addEventListener("pointerup", onUp);
      });
      th.appendChild(handle);
    }

    function installSortableHeaders(state) {
      state.headers.forEach((th, index) => {
        if (th.dataset.tableSortInstalled === "true") return;
        const label = headerText(th, index);
        th.dataset.tableColumnIndex = String(index);
        const sortButton = document.createElement("button");
        sortButton.type = "button";
        sortButton.className = "table-sort-button";
        sortButton.setAttribute("aria-label", `Sort by ${label}`);
        const text = document.createElement("span");
        text.className = "table-sort-label";
        text.textContent = label;
        const indicator = document.createElement("span");
        indicator.className = "table-sort-indicator";
        indicator.setAttribute("aria-hidden", "true");
        sortButton.append(text, indicator);
        sortButton.addEventListener("click", () => {
          if (state.sortColumn === index) {
            state.sortDirection = state.sortDirection === "asc" ? "desc" : "asc";
          } else {
            state.sortColumn = index;
            state.sortDirection = "asc";
          }
          applyTableUiState(state);
        });
        th.replaceChildren(sortButton);
        installColumnResizeHandle(state, th, index, label);
        th.dataset.tableSortInstalled = "true";
      });
    }

    function buildColumnMenu(state, label) {
      const details = document.createElement("details");
      details.className = "table-column-menu";
      const summary = document.createElement("summary");
      summary.textContent = "Columns";
      details.appendChild(summary);
      const list = document.createElement("div");
      list.className = "table-column-menu-list";
      state.headers.forEach((th, index) => {
        const item = document.createElement("label");
        item.className = "table-column-menu-item";
        const checkbox = document.createElement("input");
        checkbox.type = "checkbox";
        checkbox.checked = true;
        checkbox.setAttribute("aria-label", `Show ${headerText(th, index)} column in ${label}`);
        checkbox.addEventListener("change", () => {
          if (!checkbox.checked && tableVisibleColumnCount(state) <= 1) {
            checkbox.checked = true;
            return;
          }
          if (checkbox.checked) state.hiddenColumns.delete(index);
          else state.hiddenColumns.add(index);
          applyTableUiState(state);
        });
        state.columnCheckboxes.set(index, checkbox);
        item.append(checkbox, document.createTextNode(headerText(th, index)));
        list.appendChild(item);
      });
      details.appendChild(list);
      return details;
    }

    function ensureTableToolbar(state) {
      if (state.toolbar) return state.toolbar;
      const label = tableLabel(state.table, state.tbody);
      const toolbar = document.createElement("div");
      toolbar.className = "table-toolbar table-ui-toolbar";
      toolbar.dataset.tableToolbarFor = state.table.id;
      toolbar.setAttribute("role", "group");
      toolbar.setAttribute("aria-label", `${label} display controls`);

      const summary = document.createElement("span");
      summary.className = "table-ui-summary";
      summary.setAttribute("role", "status");
      summary.setAttribute("aria-live", "polite");
      state.summaryNode = summary;

      toolbar.append(
        buildColumnMenu(state, label),
        summary,
      );
      state.wrap.parentElement?.insertBefore(toolbar, state.wrap);
      state.toolbar = toolbar;
      return toolbar;
    }

    function stickyColumnsFor(table, tbody, headers) {
      if (table.dataset.stickyColumns) {
        return Math.max(0, Math.min(headers.length, Math.trunc(Number(table.dataset.stickyColumns)) || 0));
      }
      if (Object.prototype.hasOwnProperty.call(stickyColumnCounts, tbody?.id || "")) {
        return Math.min(headers.length, stickyColumnCounts[tbody.id] || 0);
      }
      return headers.length >= 6 ? 1 : 0;
    }

    function createTableUiState(table) {
      const tbody = firstTableBody(table);
      const headers = tableHeaders(table);
      const wrap = table.closest(".table-wrap");
      stableTableId(table, tbody);
      return {
        table,
        tbody,
        headers,
        wrap,
        colgroup: null,
        toolbar: null,
        summaryNode: null,
        hiddenColumns: new Set(),
        columnCheckboxes: new Map(),
        sortColumn: -1,
        sortDirection: "asc",
        stickyColumns: stickyColumnsFor(table, tbody, headers),
        applying: false,
        refreshScheduled: false,
        observer: null,
      };
    }

    function enhanceSingleTable(table) {
      if (!table || tableUiStates.has(table)) return null;
      const tbody = firstTableBody(table);
      const headers = tableHeaders(table);
      const wrap = table.closest(".table-wrap");
      if (!tbody || !headers.length || !wrap) return null;
      installTableEmptyStateObserver(table, tbody, wrap);
      table.classList.add("data-table");
      wrap.classList.add("data-table-wrap");
      if (!shouldEnhanceTable(table, tbody, headers)) {
        return null;
      }
      const state = createTableUiState(table);
      tableUiStates.set(table, state);
      table.classList.add("is-enhanced-table");
      table.style.minWidth = `${Math.max(840, headers.length * 138)}px`;
      ensureTableColgroup(state);
      installSortableHeaders(state);
      ensureTableToolbar(state);
      applyTableUiState(state);
      if (typeof MutationObserver === "function") {
        state.observer = new MutationObserver(() => {
          if (state.applying) return;
          scheduleTableUiRefresh(state);
        });
        state.observer.observe(tbody, { childList: true, subtree: true });
      }
      window.addEventListener?.("resize", () => scheduleTableUiRefresh(state));
      return state;
    }

    function enhanceDataTables(root = document) {
      const scope = root && typeof root.querySelectorAll === "function" ? root : document;
      const tables = Array.from(scope.querySelectorAll(".table-wrap table"));
      tables.forEach(enhanceSingleTable);
      return tables.length;
    }

    return {
      clearRows,
      appendCells,
      deferDomWork,
      documentScrollElement,
      scrollElementAllowsUserScroll,
      isScrollableElement,
      siblingElementIndex,
      scrollElementKey,
      captureScrollablePositions,
      scrollNodeForEntry,
      restoreScrollEntry,
      restoreScrollablePositions,
      scrollSelectedRowIntoView,
      selectableRowsFor,
      selectRowInGroup,
      moveSelectableRowFocus,
      makeRowSelectable,
      setOptionalDataset,
      renderOpenTargetActionGroups,
      enhanceDataTables,
    };
  }

  window.__domTableModule = {
    createDomTableModule,
  };
})();
