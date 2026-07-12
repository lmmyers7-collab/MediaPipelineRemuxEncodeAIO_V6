// Network role-dashboard tile, quick-link, and table rendering.
(function () {
  "use strict";

  function createNetworkRoleDashboardModule(deps = {}) {
    const {
      byId = () => null,
      clearRows = () => {},
      networkCoordinatorOverviewModel = () => ({ activeRows: [], onDeckRows: [], tiles: [], summaryLines: [], status: "Not loaded" }),
      networkWorkerOverviewModel = () => ({ claimRows: [], tiles: [], summaryLines: [], status: "Not loaded" }),
      renderOverviewTiles = () => {},
      renderNetworkWorkerRows = () => {},
      setText = () => {},
      state = {},
      syncNetworkWorkerViewPresetButtons = () => {},
    } = deps;
    const documentRef = deps.documentRef || document;

  function focusNetworkQuickLink(selector) {
    const target = selector ? documentRef.querySelector(selector) : null;
    if (!target) return false;
    target.scrollIntoView?.({ block: "center", inline: "nearest" });
    if (!target.matches?.("a[href], button, input, select, textarea, summary, [tabindex]")) {
      target.setAttribute("tabindex", "-1");
    }
    target.focus?.({ preventScroll: true });
    return true;
  }

  function activateQuickLink(action) {
    const normalized = String(action || "").trim().toLowerCase();
    const presetMap = {
      "worker-attention": "attention",
      "worker-active": "active",
      "worker-idle": "idle",
      "worker-stale": "stale",
      "worker-path-auth": "path-auth",
      "worker-problem": "attention",
    };
    if (Object.prototype.hasOwnProperty.call(presetMap, normalized)) {
      state.workerViewPreset = presetMap[normalized];
      syncNetworkWorkerViewPresetButtons();
      renderNetworkWorkerRows(state.workersPayload);
      return focusNetworkQuickLink("#network-worker-rows");
    }
    return true;
  }

  function networkTileTone(tone) {
    const value = String(tone || "").toLowerCase();
    if (value === "blocked" || value === "failed" || value === "danger") return "danger";
    if (value === "warning" || value === "review" || value === "active") return "warning";
    if (value === "match" || value === "ready" || value === "success") return "success";
    if (value === "info") return "info";
    return "muted";
  }

  function networkStatusChip(text, state = "") {
    const chip = documentRef.createElement("span");
    chip.className = "status-chip";
    chip.textContent = text || "-";
    if (state) chip.dataset.status = state;
    return chip;
  }

  function networkRouteChip(text, state = "") {
    const chip = documentRef.createElement("span");
    chip.className = "route-chip";
    chip.textContent = text || "Unknown";
    if (state) chip.dataset.route = state;
    return chip;
  }

  function networkAppendCell(row, content, className = "") {
    const cell = documentRef.createElement("td");
    if (className) cell.className = className;
    if (content instanceof Node) {
      cell.appendChild(content);
    } else {
      cell.textContent = content === undefined || content === null ? "" : String(content);
    }
    row.appendChild(cell);
    return cell;
  }

  function renderCoordinatorActiveRows(model) {
    const tbody = byId("network-coordinator-active-rows");
    if (!tbody) return;
    setText("network-coordinator-active-status", model.activeRows.length ? `${model.activeRows.length} active` : "No active claims");
    if (!model.activeRows.length) {
      clearRows(tbody, 6, "No active claimed worker files are visible in the loaded persisted state.");
      return;
    }
    tbody.replaceChildren();
    model.activeRows.forEach((item) => {
      const row = documentRef.createElement("tr");
      row.dataset.status = item.status;
      networkAppendCell(row, item.worker);
      networkAppendCell(row, item.file, "network-overview-table-file");
      if (item.route) {
        networkAppendCell(row, networkRouteChip(item.route, item.routeTone));
      } else {
        const missing = documentRef.createElement("span");
        missing.className = "network-overview-route-missing";
        missing.textContent = "unknown/backend evidence missing";
        missing.title = "No normalized queue-row match exists for this active worker claim.";
        networkAppendCell(row, missing);
      }
      networkAppendCell(row, networkStatusChip(item.stage, item.status));
      networkAppendCell(row, item.progress, "num");
      networkAppendCell(row, item.heartbeat, "num");
      tbody.appendChild(row);
    });
  }

  function renderCoordinatorQueueRows(model) {
    const tbody = byId("network-coordinator-queue-rows");
    if (!tbody) return;
    setText("network-coordinator-queue-status", model.onDeckRows.length ? `${model.onDeckRows.length} on deck` : "No on-deck rows");
    if (!model.onDeckRows.length) {
      clearRows(tbody, 6, "No unclaimed queue/on-deck files are visible in the loaded queue payload.");
      return;
    }
    tbody.replaceChildren();
    model.onDeckRows.forEach((item) => {
      const row = documentRef.createElement("tr");
      networkAppendCell(row, item.order, "num");
      networkAppendCell(row, item.file, "network-overview-table-file");
      networkAppendCell(row, networkRouteChip(item.route, item.routeTone));
      networkAppendCell(row, item.priority);
      networkAppendCell(row, item.size, "num");
      networkAppendCell(row, item.evidence);
      tbody.appendChild(row);
    });
  }

  function renderWorkerClaimRows(model) {
    const tbody = byId("network-worker-claim-rows");
    if (!tbody) return;
    setText("network-worker-claim-status", model.pendingDone ? "Pending done report" : model.status);
    tbody.replaceChildren();
    model.claimRows.forEach(([field, evidence]) => {
      const row = documentRef.createElement("tr");
      networkAppendCell(row, field);
      networkAppendCell(row, evidence);
      tbody.appendChild(row);
    });
  }

  function renderNetworkRoleDashboards({ queue, networkWorkers, config, contract } = {}) {
    const coordinatorModel = networkCoordinatorOverviewModel({ queue, networkWorkers });
    setText("network-coordinator-overview-status", coordinatorModel.status);
    setText("network-coordinator-overview-summary", coordinatorModel.summaryLines.join("\n"));
    renderOverviewTiles("network-coordinator-overview-tiles", coordinatorModel.tiles);
    renderCoordinatorActiveRows(coordinatorModel);
    renderCoordinatorQueueRows(coordinatorModel);

    const workerModel = networkWorkerOverviewModel({ config: config || {}, contract: contract || {}, networkWorkers, queue });
    setText("network-worker-overview-status", workerModel.status);
    setText("network-worker-overview-summary", workerModel.summaryLines.join("\n"));
    setText("network-worker-remote-queue-status", "Phase 2");
    setText("network-worker-remote-queue-summary", workerModel.remoteQueueSummary);
    renderOverviewTiles("network-worker-overview-tiles", workerModel.tiles);
    renderWorkerClaimRows(workerModel);
  }
    return {
      focusNetworkQuickLink,
      activateQuickLink,
      networkTileTone,
      networkStatusChip,
      networkRouteChip,
      networkAppendCell,
      renderCoordinatorActiveRows,
      renderCoordinatorQueueRows,
      renderWorkerClaimRows,
      renderNetworkRoleDashboards,
    };
  }

  window.__networkRoleDashboardModule = { createNetworkRoleDashboardModule };
})();
