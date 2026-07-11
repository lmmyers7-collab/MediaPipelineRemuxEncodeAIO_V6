// Network configuration guidance, summaries, and role-dashboard visibility.
(function () {
  "use strict";

  function createNetworkConfigModule(deps = {}) {
    const {
      byId = () => null,
      networkCoordinatorConnectivityLines = () => [],
      updatePagePanelEmptyStates = () => {},
      visibleNetworkMode = () => "",
    } = deps;
    const documentRef = deps.documentRef || document;

  function obviousWorkerCoordinatorUrlIssue(value, { required = true } = {}) {
    const text = String(value || "").trim();
    if (!text) return required ? "Worker coordinator URL is required in Worker mode." : "";
    let parsed;
    try {
      parsed = new URL(text);
    } catch (_error) {
      return "Worker coordinator URL must include http:// or https:// and a reachable coordinator host.";
    }
    if (!["http:", "https:"].includes(parsed.protocol)) {
      return "Worker coordinator URL must start with http:// or https://.";
    }
    const host = String(parsed.hostname || "").replace(/^\[|\]$/g, "").toLowerCase();
    if (!host) return "Worker coordinator URL must include a coordinator host.";
    if (host === "0.0.0.0" || host === "::") {
      return "Use the coordinator machine name or LAN IP. 0.0.0.0 and :: are listen addresses, not worker targets.";
    }
    if (!parsed.port) {
      return "Worker coordinator URL must include the coordinator TCP port, for example http://coordinator-host:7830.";
    }
    const port = Number(parsed.port);
    if (!Number.isInteger(port) || port < 1 || port > 65535) {
      return "Worker coordinator URL port must be in 1..65535.";
    }
    if (parsed.pathname && parsed.pathname !== "/") {
      return "Worker coordinator URL must be the coordinator base URL only, without a path.";
    }
    if (parsed.search || parsed.hash) {
      return "Worker coordinator URL must not include query strings or fragments.";
    }
    if (parsed.username || parsed.password) {
      return "Worker coordinator URL must not embed userinfo; use the shared worker token instead.";
    }
    return "";
  }

  function networkGuidance(role, networkWorkers) {
    if (role === "coordinator") {
      return [
        "Saved role: coordinator",
        ...networkCoordinatorConnectivityLines(networkWorkers).slice(0, 3),
        "Saved coordinator config is controlled from Saved Distributed Mode Settings on this tab.",
        "Runtime lifecycle commands must be started from Network Lifecycle controls, not normal Launch.",
        "Worker claim evidence is read from persisted worker state after the coordinator queue is populated.",
      ];
    }
    if (role === "worker") {
      return [
        "Saved role: worker",
        "This worker polls the configured coordinator URL and launches backend-owned single-file pipeline jobs.",
        "Worker URL, name, poll interval, and path map are controlled from Saved Distributed Mode Settings on this tab; worker config overrides are backend-disabled.",
        "Use Diagnostics to inspect RunLogs and ActiveJobs when worker claims fail or are reclaimed.",
      ];
    }
    return [
      `Saved role: ${role || "standalone"}`,
      "Standalone mode keeps all processing local to this workstation.",
      "Use Saved Distributed Mode Settings on this tab to stage role changes through backend Settings Save.",
    ];
  }

  function networkModeModelLines(role) {
    return [
      `Current saved role: ${role || "standalone"}`,
      "Standalone: local queue work only on this workstation.",
      "Coordinator only: owns queue claims and worker registry state but does not process local files.",
      "Worker only: polls a coordinator and runs one claimed file at a time.",
      "Coordinator + local worker: coordinator mode with local worker processing enabled through Network lifecycle only.",
      "Runtime authority: backend routes own lifecycle commands; normal Launch is blocked in network modes.",
    ];
  }

  function renderNetworkSummaryRows(elementId, lines) {
    const target = documentRef.getElementById(elementId);
    if (!target) return;
    target.textContent = "";
    const normalizedLines = (Array.isArray(lines) ? lines : [lines])
      .map((line) => String(line || "").trim())
      .filter(Boolean);
    const displayLines = normalizedLines.length ? normalizedLines : ["No network summary loaded."];
    displayLines.forEach((line) => {
      const row = documentRef.createElement("div");
      row.className = "network-summary-row";
      row.setAttribute("role", "listitem");
      const separatorIndex = line.indexOf(":");
      if (separatorIndex > 0 && separatorIndex <= 36) {
        if (separatorIndex === line.length - 1) {
          const section = documentRef.createElement("span");
          section.className = "network-summary-row-section";
          section.textContent = line;
          row.appendChild(section);
          target.appendChild(row);
          return;
        }
        const label = documentRef.createElement("span");
        label.className = "network-summary-row-label";
        label.textContent = `${line.slice(0, separatorIndex)}: `;
        const value = documentRef.createElement("span");
        value.className = "network-summary-row-value";
        value.textContent = line.slice(separatorIndex + 1).trim();
        row.append(label, value);
      } else {
        const body = documentRef.createElement("span");
        body.className = "network-summary-row-body";
        body.textContent = line;
        row.appendChild(body);
      }
      target.appendChild(row);
    });
  }

  function networkRolePanelIds(config) {
    const mode = visibleNetworkMode(config);
    if (mode === "worker") return ["worker"];
    if (mode === "coordinator") return ["coordinator"];
    if (mode === "coordinator_local") return ["coordinator", "worker"];
    return [];
  }

  function syncNetworkRoleDashboards(config) {
    const visiblePanels = new Set(networkRolePanelIds(config));
    documentRef.querySelectorAll("[data-network-role-panel]").forEach((panel) => {
      const selected = visiblePanels.has(panel.dataset.networkRolePanel || "");
      panel.classList.toggle("is-active", selected);
      panel.hidden = !selected;
    });
    const container = byId("network-role-dashboards");
    if (container) {
      const hasVisiblePanels = visiblePanels.size > 0;
      container.hidden = !hasVisiblePanels;
      container.setAttribute("aria-hidden", hasVisiblePanels ? "false" : "true");
    }
    if (typeof updatePagePanelEmptyStates === "function") updatePagePanelEmptyStates();
  }
    return {
      obviousWorkerCoordinatorUrlIssue,
      networkGuidance,
      networkModeModelLines,
      renderNetworkSummaryRows,
      networkRolePanelIds,
      syncNetworkRoleDashboards,
    };
  }

  window.__networkConfigModule = { createNetworkConfigModule };
})();

