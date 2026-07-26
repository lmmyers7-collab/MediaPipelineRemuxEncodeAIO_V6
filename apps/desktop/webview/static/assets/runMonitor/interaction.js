(function () {
  "use strict";

  let state;
  let text;
  let array;
  let object;
  let byId;
  let renderItems;
const TERMINAL_LINK_PAGES = Object.freeze({
    completed: "completed",
    pending_publish: "pending",
    failure: "reports",
    review: "reports",
    report: "reports",
    sidecar: "completed",
  });
const TERMINAL_PATH_FIELDS = Object.freeze({
    completed: ["manifest_path", "completed_manifest_path", "output_path", "source_json", "sidecar_path"],
    pending: ["manifest_path", "local_file", "server_out", "source_path", "parked_path", "intended_final_path"],
    reports: ["source_json", "artifact_path", "report_path", "source_path", "marker_path"],
  });

function cssEscape(value) {
    if (window.CSS && typeof window.CSS.escape === "function") return window.CSS.escape(String(value));
    return String(value).replace(/(["\\])/g, "\\$1");
  }

function captureDynamicMonitorFocus() {
    const active = document.activeElement;
    if (!active || active === document.body || typeof active.closest !== "function") return null;
    const worker = active.closest("[data-run-monitor-worker-id]");
    if (worker) {
      return {
        kind: "worker",
        key: text(worker.getAttribute("data-run-monitor-worker-id")),
        jobId: text(worker.getAttribute("data-run-monitor-job-id")),
      };
    }
    const terminal = active.closest("[data-run-monitor-terminal-key]");
    if (terminal) {
      return {
        kind: "terminal",
        key: text(terminal.getAttribute("data-run-monitor-terminal-key")),
        jobId: state.selectedJobId,
      };
    }
    const lastKnownItem = active.closest("[data-last-known-job-id]");
    if (lastKnownItem) {
      return {
        kind: "last-known-item",
        key: text(lastKnownItem.getAttribute("data-last-known-job-id")),
        jobId: text(lastKnownItem.getAttribute("data-last-known-job-id")),
      };
    }
    return null;
  }

function restoreDynamicMonitorFocus(context) {
    const record = object(context);
    if (!text(record.kind) || !text(record.key)) return;
    window.setTimeout(() => {
      const active = document.activeElement;
      if (active && active !== document.body && active !== document.documentElement && active.isConnected) return;
      const attribute = record.kind === "worker"
        ? "data-run-monitor-worker-id"
        : record.kind === "last-known-item"
          ? "data-last-known-job-id"
          : "data-run-monitor-terminal-key";
      const exact = document.querySelector(`[${attribute}="${cssEscape(record.key)}"]`);
      const fileButton = text(record.jobId)
        ? byId("run-monitor-items")?.querySelector(`[data-run-monitor-job-id="${cssEscape(record.jobId)}"]`)
        : null;
      const fallback = record.kind === "terminal" ? byId("run-monitor-detail") : fileButton || byId("run-monitor-detail");
      const target = exact || fallback;
      if (!target || typeof target.focus !== "function") return;
      target.scrollIntoView?.({ block: "nearest", inline: "nearest" });
      target.focus({ preventScroll: true });
    }, 0);
  }

function handleItemKeydown(event) {
    if (!["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) return;
    const buttons = Array.from(byId("run-monitor-items")?.querySelectorAll(".run-monitor-item-button") || []);
    const index = buttons.indexOf(event.currentTarget);
    if (index < 0 || !buttons.length) return;
    let nextIndex = index;
    if (event.key === "ArrowDown") nextIndex = Math.min(buttons.length - 1, index + 1);
    if (event.key === "ArrowUp") nextIndex = Math.max(0, index - 1);
    if (event.key === "Home") nextIndex = 0;
    if (event.key === "End") nextIndex = buttons.length - 1;
    event.preventDefault();
    const next = buttons[nextIndex];
    selectJob(next.getAttribute("data-run-monitor-job-id") || "", { focusDetail: false, focusButton: true });
  }

function selectJob(jobId, options = {}) {
    const normalized = text(jobId);
    if (!normalized || !array(state.payload?.items).some((item) => text(item.job_id) === normalized)) return false;
    state.selectedJobId = normalized;
    state.focusedJobId = normalized;
    if (options.focusButton) state.workloadExpanded = true;
    const freshnessState = text(state.payload?.freshness?.state, "unavailable");
    renderItems(state.payload, freshnessState);
    const selector = `[data-run-monitor-job-id="${cssEscape(normalized)}"]`;
    if (options.focusButton) {
      window.setTimeout(() => byId("run-monitor-items")?.querySelector(selector)?.focus({ preventScroll: true }), 0);
    }
    if (options.focusDetail) {
      window.setTimeout(() => byId("run-monitor-detail")?.focus({ preventScroll: false }), 0);
    }
    return true;
  }

function terminalLinkPage(reference, item) {
    const kind = text(reference?.kind);
    if (kind === "manifest") return text(item?.lifecycle_state) === "parked" ? "pending" : "completed";
    if (kind === "sidecar") {
      const lifecycleState = text(item?.lifecycle_state);
      if (lifecycleState === "parked") return "pending";
      if (["failed", "blocked", "review"].includes(lifecycleState)) return "reports";
      return "completed";
    }
    return TERMINAL_LINK_PAGES[kind] || "";
  }

function terminalFocusKey(page, reference) {
    return [page, text(reference?.kind), text(reference?.reference), text(reference?.path)].join("\u241f");
  }

function focusSelectorForPage(page) {
    return `[data-page-panel="${page}"] h1`;
  }

function normalizedTerminalKey(value) {
    return text(value).toLocaleLowerCase();
  }

function normalizedTerminalPath(value) {
    return text(value).replace(/\//g, "\\").toLocaleLowerCase();
  }

function terminalDestinationAdapter(page) {
    if (page === "completed") {
      const view = window.mediaPipelineCompletedView || {};
      return {
        getRows: view.getLastCompletedRows,
        rowKey: (row) => text(row?.row_key),
        select: view.selectCompletedRow,
        detailSelector: "#completed-selected-summary",
        rowSelector: "#completed-rows tr[data-row-key]",
      };
    }
    if (page === "pending") {
      const view = window.mediaPipelinePendingPublishView || {};
      return {
        getRows: view.getLastPendingPublishRows,
        rowKey: typeof view.pendingRowKey === "function" ? view.pendingRowKey : (row) => text(row?.row_key),
        select: view.selectPendingRow,
        detailSelector: "#pending-selected-summary",
        rowSelector: "#pending-rows tr[data-row-key]",
      };
    }
    if (page === "reports") {
      const view = window.mediaPipelineReportsView || {};
      return {
        getRows: view.getLastFailureRows,
        rowKey: typeof view.failureRowKey === "function" ? view.failureRowKey : (row) => text(row?.row_key),
        select: view.selectFailureRow,
        detailSelector: "#failure-detail",
        rowSelector: "#failure-rows tr[data-row-key]",
      };
    }
    return null;
  }

function terminalRowPathValues(page, row) {
    const values = array(TERMINAL_PATH_FIELDS[page]).map((field) => row?.[field]);
    if (page === "completed") {
      array(row?.sidecars).forEach((sidecar) => values.push(sidecar?.path));
      array(row?.sidecar_paths).forEach((path) => values.push(path));
    }
    return values.map(normalizedTerminalPath).filter(Boolean);
  }

function terminalReferenceMatch(page, adapter, row, reference) {
    const stableReference = normalizedTerminalKey(reference?.reference);
    const artifactPath = normalizedTerminalPath(reference?.path);
    const stableRowKey = normalizedTerminalKey(adapter.rowKey(row));
    if (stableReference && stableRowKey && stableReference === stableRowKey) return "stable_row_key";
    if (artifactPath && terminalRowPathValues(page, row).includes(artifactPath)) return "artifact_path";
    return "";
  }

function focusTerminalHeading(page) {
    const heading = document.querySelector(focusSelectorForPage(page));
    if (!heading || typeof heading.focus !== "function") return false;
    if (!heading.matches("button, a, input, select, textarea, [tabindex]")) heading.setAttribute("tabindex", "-1");
    heading.focus({ preventScroll: false });
    return document.activeElement === heading;
  }

function terminalPageIsVisible(page) {
    return document.querySelector(`[data-page-panel="${page}"].is-visible`) !== null;
  }

function clearTerminalHandoff() {
    if (state.terminalHandoffObserver) state.terminalHandoffObserver.disconnect();
    if (state.terminalHandoffApplyTimer !== null) window.clearTimeout(state.terminalHandoffApplyTimer);
    if (state.terminalHandoffExpiryTimer !== null) window.clearTimeout(state.terminalHandoffExpiryTimer);
    state.terminalHandoff = null;
    state.terminalHandoffObserver = null;
    state.terminalHandoffApplyTimer = null;
    state.terminalHandoffExpiryTimer = null;
    state.terminalHandoffApplying = false;
    state.terminalHandoffTarget = null;
  }

function focusTerminalDestination(page, reference) {
    const adapter = terminalDestinationAdapter(page);
    if (!adapter || typeof adapter.getRows !== "function" || typeof adapter.select !== "function") return false;
    const rows = array(adapter.getRows());
    const match = rows.map((row) => ({ row, kind: terminalReferenceMatch(page, adapter, row, reference) }))
      .find((entry) => entry.kind);
    if (!match) return false;
    state.terminalHandoffApplying = true;
    adapter.select(match.row);
    const selectedKey = normalizedTerminalKey(adapter.rowKey(match.row));
    window.setTimeout(() => {
      const exactRow = Array.from(document.querySelectorAll(adapter.rowSelector))
        .find((row) => normalizedTerminalKey(row.dataset.rowKey) === selectedKey);
      const target = exactRow || document.querySelector(adapter.detailSelector);
      if (target && typeof target.focus === "function") {
        if (!target.matches("button, a, input, select, textarea, [tabindex]")) target.setAttribute("tabindex", "-1");
        target.dataset.terminalReferenceMatch = match.kind;
        target.focus({ preventScroll: false });
        // A detail panel is only a temporary landing while an asynchronous
        // destination render catches up. Only an exact row can satisfy the
        // handoff and suppress another correlated re-apply.
        state.terminalHandoffTarget = exactRow || null;
      }
      state.terminalHandoffApplying = false;
    }, 0);
    return true;
  }

function applyTerminalHandoff() {
    const handoff = state.terminalHandoff;
    if (!handoff || state.terminalHandoffApplying) return false;
    if (!terminalPageIsVisible(handoff.page)) {
      clearTerminalHandoff();
      return false;
    }
    const matched = focusTerminalDestination(handoff.page, handoff.reference);
    if (!matched) {
      state.terminalHandoffTarget = null;
      focusTerminalHeading(handoff.page);
    }
    return matched;
  }

function scheduleTerminalHandoffApply(delay = 0) {
    if (!state.terminalHandoff || state.terminalHandoffApplyTimer !== null) return;
    state.terminalHandoffApplyTimer = window.setTimeout(() => {
      state.terminalHandoffApplyTimer = null;
      applyTerminalHandoff();
    }, delay);
  }

function beginTerminalHandoff(page, reference) {
    clearTerminalHandoff();
    state.terminalHandoff = { page, reference: { ...object(reference) } };
    const panel = document.querySelector(`[data-page-panel="${page}"]`);
    if (panel && typeof window.MutationObserver === "function") {
      state.terminalHandoffObserver = new window.MutationObserver(() => {
        if (state.terminalHandoffApplying) return;
        if (!terminalPageIsVisible(page)) {
          clearTerminalHandoff();
          return;
        }
        if (state.terminalHandoffTarget?.isConnected) return;
        scheduleTerminalHandoffApply();
      });
      state.terminalHandoffObserver.observe(panel, { childList: true, subtree: true });
    }
    state.terminalHandoffExpiryTimer = window.setTimeout(() => {
      if (state.terminalHandoff?.page !== page) return;
      if (terminalPageIsVisible(page) && !state.terminalHandoffTarget?.isConnected) focusTerminalHeading(page);
      clearTerminalHandoff();
    }, 30000);
  }

function reapplyTerminalHandoff(page) {
    const handoff = state.terminalHandoff;
    if (!handoff || text(handoff.page) !== text(page)) return false;
    if (!terminalPageIsVisible(handoff.page)) {
      clearTerminalHandoff();
      return false;
    }
    if (state.terminalHandoffTarget?.isConnected) return true;
    applyTerminalHandoff();
    return true;
  }

function navigateToTerminalReference(reference, item) {
    const page = terminalLinkPage(reference, item);
    if (!page) return;
    if (page === "reports") window.mediaPipelineReportsView?.activateReportsTab?.("failures");
    beginTerminalHandoff(page, reference);
    const navigation = window.mediaPipelineAppLifecycle || {};
    if (typeof navigation.navigateToPage === "function") {
      navigation.navigateToPage(page, { focusSelector: focusSelectorForPage(page), restoreFocus: false });
    } else {
      window.showPage?.(page);
      window.setTimeout(() => focusTerminalHeading(page), 0);
    }
    applyTerminalHandoff();
  }

function focusSelectedFile(options = {}) {
    const jobId = state.selectedJobId;
    if (!jobId) return false;
    if (options.detail !== true && !state.workloadExpanded) {
      state.workloadExpanded = true;
      renderItems(state.payload, text(state.payload?.freshness?.state, "unavailable"));
    }
    const button = byId("run-monitor-items")?.querySelector(`[data-run-monitor-job-id="${cssEscape(jobId)}"]`);
    const target = options.detail === true ? byId("run-monitor-detail") : button;
    if (!target || typeof target.focus !== "function") return false;
    target.scrollIntoView?.({ block: "center", inline: "nearest" });
    target.focus({ preventScroll: true });
    return true;
  }

  window.__runMonitorInteractionModule = function createRunMonitorInteraction(deps) {
    ({ state, text, array, object, byId, renderItems } = deps);
    return {
      cssEscape,
      captureDynamicMonitorFocus,
      restoreDynamicMonitorFocus,
      handleItemKeydown,
      selectJob,
      terminalLinkPage,
      terminalFocusKey,
      focusSelectorForPage,
      normalizedTerminalKey,
      normalizedTerminalPath,
      terminalDestinationAdapter,
      terminalRowPathValues,
      terminalReferenceMatch,
      focusTerminalHeading,
      terminalPageIsVisible,
      clearTerminalHandoff,
      focusTerminalDestination,
      applyTerminalHandoff,
      scheduleTerminalHandoffApply,
      beginTerminalHandoff,
      reapplyTerminalHandoff,
      navigateToTerminalReference,
      focusSelectedFile
    };
  };
})();
