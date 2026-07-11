(function () {
  function createQueueTableViewModule(deps = {}) {
    const {
      state = {},
      byId = () => null,
      clearRows = () => {},
      filterFields = [],
      filterResultSummaryLines = null,
      filterRows = (rows) => rows,
      filterRowsByInvestigation = (rows) => rows,
      filterRowsByStatus = (rows) => rows,
      getCommandHistory = () => [],
      getSelectedQueuePriorityRowKeys = () => [],
      getSelectedQueueRow = () => null,
      getSelectedQueueRowKey = () => "",
      queueDisplayRowStatus = () => "",
      queueInvestigationFilterLabel = () => "",
      queueManualOrderIsEnabled = () => false,
      queueMatchesInvestigationFilter = () => false,
      readOnlyBoundary = "",
      renderQueueAttentionSummary = () => {},
      renderQueueBackendLaunchScopePreview = () => {},
      renderQueueDecisionHeader = () => {},
      renderQueueDetail = () => {},
      renderQueueLaunchDecisionChecklist = () => {},
      renderQueueLoadingTable = () => {},
      renderQueueTableRows = () => {},
      renderLimit = 250,
      setRenderedQueueRows = () => {},
      setText = () => {},
      updateQueueManualOrderControls = () => {},
      wireManualOrderRow = () => {},
    } = deps;
    function queueClampScrollOffset(value, maxValue) {
      const numeric = Number(value);
      const maximum = Math.max(0, Number(maxValue) || 0);
      return Math.min(Math.max(0, Number.isFinite(numeric) ? numeric : 0), maximum);
    }

    function queueTableScrollSnapshot(tbody) {
      const target = tbody?.closest?.(".queue-table-wrap") || tbody?.closest?.(".table-wrap") || null;
      if (!target) return null;
      return {
        target,
        top: target.scrollTop,
        left: target.scrollLeft,
      };
    }

    function restoreQueueTableScroll(snapshot) {
      const target = snapshot?.target;
      if (!target) return;
      target.scrollTop = queueClampScrollOffset(snapshot.top, target.scrollHeight - target.clientHeight);
      target.scrollLeft = queueClampScrollOffset(snapshot.left, target.scrollWidth - target.clientWidth);
    }

    function updateQueueSelectionVisuals() {
      const tbody = byId("queue-rows");
      const selectedKeys = new Set(getSelectedQueuePriorityRowKeys());
      if (tbody && typeof tbody.querySelectorAll === "function") {
        tbody.querySelectorAll('tr[data-selectable-row="true"]').forEach((row) => {
          const key = String(row.dataset.rowKey || "");
          const selected = Boolean(key && selectedKeys.has(key));
          row.classList.toggle("is-selected", selected);
          row.setAttribute("aria-selected", selected ? "true" : "false");
          if (selected) row.dataset.prioritySelected = "true";
          else delete row.dataset.prioritySelected;
        });
      }
      updateQueueTableLegend(tbody);
      updateQueueManualOrderControls();
    }

    function hideQueueTableLegend() {
      const legend = byId("queue-table-legend");
      if (!legend) return;
      legend.textContent = "";
      legend.hidden = true;
      legend.setAttribute("aria-hidden", "true");
    }

    function updateQueueTableLegend() {
      hideQueueTableLegend();
    }

    function queueDisplayFilterSignature(filterText, statusFilter, investigationFilter) {
      return [
        String(filterText || ""),
        String(statusFilter || "all"),
        String(investigationFilter || "all"),
        String(state.rows.length),
      ].join("\u001f");
    }

    function queueClampPageStart(rowCount) {
      const count = Math.max(0, Number(rowCount) || 0);
      if (count <= renderLimit) return 0;
      const maxStart = Math.floor((count - 1) / renderLimit) * renderLimit;
      return Math.min(Math.max(0, state.pageStart), maxStart);
    }

    function updateQueuePaginationControls(rowCount, pageStart, renderedCount) {
      const container = byId("queue-table-pagination");
      const status = byId("queue-table-page-status");
      const previous = byId("queue-page-prev-btn");
      const next = byId("queue-page-next-btn");
      const total = Math.max(0, Number(rowCount) || 0);
      const hasPages = total > renderLimit;
      if (container) {
        container.hidden = !hasPages;
        container.setAttribute("aria-hidden", hasPages ? "false" : "true");
      }
      if (status) {
        if (hasPages) {
          const first = pageStart + 1;
          const last = pageStart + renderedCount;
          const page = Math.floor(pageStart / renderLimit) + 1;
          const pages = Math.ceil(total / renderLimit);
          status.textContent = `Rows ${first}-${last} of ${total}. Page ${page} of ${pages}. Display paging does not change backend Launch scope.`;
        } else {
          status.textContent = `Rows ${total ? `1-${total}` : "0"} of ${total}.`;
        }
      }
      if (previous) previous.disabled = !hasPages || pageStart <= 0;
      if (next) next.disabled = !hasPages || pageStart + renderLimit >= total;
    }

    function moveQueueTablePage(delta) {
      const rows = queueFilteredRowsForCurrentDisplay();
      const nextStart = queueClampScrollOffset(state.pageStart + (delta * renderLimit), Math.max(0, rows.length - 1));
      const normalized = Math.floor(nextStart / renderLimit) * renderLimit;
      state.pageStart = normalized;
      renderQueueRows({ preservePage: true });
    }

    function queueFilteredRowsForCurrentDisplay() {
      const filterText = byId("queue-filter")?.value || "";
      const statusFilter = byId("queue-status-filter")?.value || "all";
      const investigationFilter = byId("queue-investigation-filter")?.value || "all";
      const textRows = filterRows(state.rows, filterText, filterFields);
      const statusRows = typeof filterRowsByStatus === "function" ? filterRowsByStatus(textRows, statusFilter, queueDisplayRowStatus) : textRows;
      return typeof filterRowsByInvestigation === "function" ? filterRowsByInvestigation(statusRows, investigationFilter, queueMatchesInvestigationFilter) : statusRows;
    }

    function setQueueFilterSummary(lines) {
      const text = Array.isArray(lines) ? lines.join("\n") : String(lines || "");
      setText("queue-filter-summary", text || "Queue filter inactive. No rows loaded.");
      const summary = byId("queue-filter-summary");
      if (!summary) return;
      summary.hidden = true;
      summary.style.display = "none";
      summary.setAttribute("aria-hidden", "true");
      const normalized = text.toLowerCase();
      summary.dataset.tone = normalized.includes("hidden review rows")
        || normalized.includes("display cap")
        || normalized.includes("blocked/warning")
        ? "warning"
        : "info";
    }

    function renderQueueRows(options = {}) {
      const filterText = byId("queue-filter")?.value || "";
      const statusFilter = byId("queue-status-filter")?.value || "all";
      const investigationFilter = byId("queue-investigation-filter")?.value || "all";
      const rows = queueFilteredRowsForCurrentDisplay();
      const filterSignature = queueDisplayFilterSignature(filterText, statusFilter, investigationFilter);
      if (!options.preservePage && filterSignature !== state.filterSignature) {
        state.pageStart = 0;
      }
      state.filterSignature = filterSignature;
      state.pageStart = queueClampPageStart(rows.length);
      const visibleRows = rows.slice(state.pageStart, state.pageStart + renderLimit);
      const renderedCount = visibleRows.length;
      setText(
        "queue-status",
        rows.length > renderLimit
          ? (
            state.pageStart > 0
              ? `${state.pageStart + 1}-${state.pageStart + renderedCount} shown / ${rows.length} filtered / ${state.rows.length} rows`
              : `${renderedCount} shown / ${rows.length} filtered / ${state.rows.length} rows`
          )
          : `${rows.length} / ${state.rows.length} row${state.rows.length === 1 ? "" : "s"}`
      );
      const buildFilterSummary = typeof filterResultSummaryLines === "function"
        ? filterResultSummaryLines
        : window.mediaPipelineDom?.filterResultSummaryLines;
      if (typeof buildFilterSummary === "function") {
        const summaryLines = buildFilterSummary({
          label: "Queue display filter",
          allRows: state.rows,
          visibleRows: rows,
          filterText,
          statusFilter,
          investigationFilter,
          investigationLabel: queueInvestigationFilterLabel(investigationFilter),
          statusOf: queueDisplayRowStatus,
          limit: renderLimit,
          decisionName: "launch",
          guardrail: readOnlyBoundary,
        });
        if (rows.length > renderLimit) {
          const first = state.pageStart + 1;
          const last = state.pageStart + renderedCount;
          summaryLines.push(`Display page: showing filtered rows ${first}-${last} of ${rows.length}. Use Previous/Next to inspect more rows; display pages are not backend Launch scope.`);
        }
        setQueueFilterSummary(summaryLines);
      }
      const tbody = byId("queue-rows");
      const scrollSnapshot = queueTableScrollSnapshot(tbody);
      if (!rows.length) {
        setRenderedQueueRows([]);
        clearRows(tbody, 9, state.rows.length ? "No queue rows match the filter." : state.emptyMessage);
        updateQueuePaginationControls(rows.length, 0, 0);
        updateQueueTableLegend(tbody);
        updateQueueManualOrderControls();
        if (state.scanLoading) renderQueueLoadingTable();
        if (getSelectedQueueRowKey()) renderQueueDetail(getSelectedQueueRow());
        const commandHistory = typeof getCommandHistory === "function" ? getCommandHistory() : [];
        renderQueueBackendLaunchScopePreview(state.payload, state.rows, commandHistory);
        renderQueueLaunchDecisionChecklist(state.payload, state.rows, commandHistory);
        renderQueueDecisionHeader(state.payload, state.rows, commandHistory);
        renderQueueAttentionSummary(state.payload, state.rows);
        restoreQueueTableScroll(scrollSnapshot);
        return;
      }
      tbody.replaceChildren();
      setRenderedQueueRows(visibleRows);
      renderQueueTableRows({
        rows: visibleRows,
        tbody,
        manualOrderEnabled: queueManualOrderIsEnabled(),
        selectedQueuePriorityRowKeys: getSelectedQueuePriorityRowKeys(),
        selectedQueueRowKey: getSelectedQueueRowKey(),
        wireManualOrderRow,
      });
      updateQueuePaginationControls(rows.length, state.pageStart, renderedCount);
      updateQueueTableLegend(tbody);
      updateQueueManualOrderControls();
      if (getSelectedQueueRowKey()) renderQueueDetail(getSelectedQueueRow());
      const commandHistory = typeof getCommandHistory === "function" ? getCommandHistory() : [];
      renderQueueBackendLaunchScopePreview(state.payload, state.rows, commandHistory);
      renderQueueLaunchDecisionChecklist(state.payload, state.rows, commandHistory);
      renderQueueDecisionHeader(state.payload, state.rows, commandHistory);
      renderQueueAttentionSummary(state.payload, state.rows);
      if (state.scanLoading) renderQueueLoadingTable();
      restoreQueueTableScroll(scrollSnapshot);
    }

    function resetQueueFilters() {
      const filter = byId("queue-filter");
      const status = byId("queue-status-filter");
      const investigation = byId("queue-investigation-filter");
      if (filter) filter.value = "";
      if (status) status.value = "all";
      if (investigation) investigation.value = "all";
      state.pageStart = 0;
      state.filterSignature = "";
      renderQueueRows();
      setText("queue-open-status", "Queue display filters cleared. Backend launch scope is unchanged.");
    }

    return {
      queueClampScrollOffset, queueTableScrollSnapshot, restoreQueueTableScroll,
      updateQueueSelectionVisuals, hideQueueTableLegend, updateQueueTableLegend,
      queueDisplayFilterSignature, queueClampPageStart, updateQueuePaginationControls,
      moveQueueTablePage, queueFilteredRowsForCurrentDisplay, setQueueFilterSummary,
      renderQueueRows, resetQueueFilters,
    };
  }

  window.__queueTableViewModule = { createQueueTableViewModule };
})();
