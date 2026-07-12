// Network diagnostics-open command-history projection.
(function () {
  "use strict";

  function createNetworkOpenHistoryModule(deps = {}) {
    const {
      commandHistoryCompactEvidenceLine = null,
      networkOpenCommandTarget = () => "",
      networkOpenTargets = () => [],
      setText = () => {},
    } = deps;

  function isNetworkOpenCommand(entry) {
    if (String(entry?.command || "").toLowerCase() !== "diagnostics.open") return false;
    return networkOpenTargets().includes(networkOpenCommandTarget(entry));
  }

  function networkOpenHistoryLine(entry) {
    const raw = entry?.raw && typeof entry.raw === "object" ? entry.raw : {};
    const data = raw.data && typeof raw.data === "object" ? raw.data : {};
    const request = raw.request && typeof raw.request === "object"
      ? raw.request
      : raw.submitted_request && typeof raw.submitted_request === "object"
        ? raw.submitted_request
        : {};
    const bits = [];
    if (data.target || request.target) bits.push(`target=${data.target || request.target}`);
    if (data.opened_path) bits.push(`opened=${data.opened_path}`);
    if (typeof commandHistoryCompactEvidenceLine === "function") {
      return commandHistoryCompactEvidenceLine(entry, {
        label: "diagnostics.open",
        detail: bits.length ? ` (${bits.join("; ")})` : "",
      });
    }
    const status = entry?.result || (entry?.ok ? "ok" : entry?.severity || "unknown");
    const local = entry?.local ? "local" : "journal";
    return `${entry?.at || ""} diagnostics.open [${status}; ${local}] ${entry?.message || ""}${bits.length ? ` (${bits.join("; ")})` : ""}`.trim();
  }

  function renderNetworkOpenHistory(history = []) {
    const entries = Array.isArray(history) ? history.filter(isNetworkOpenCommand).slice(0, 6) : [];
    setText("network-open-history-status", entries.length ? `${entries.length} recent` : "No opens");
    if (!Array.isArray(history) || !history.length) {
      setText("network-open-history", "No network diagnostics open command history loaded. Open a network diagnostics location to see backend results here after refresh.");
      return;
    }
    if (!entries.length) {
      setText("network-open-history", "No network diagnostics open commands found in recent command history.");
      return;
    }
    setText("network-open-history", [
      `Last ${entries.length} network diagnostics open command${entries.length === 1 ? "" : "s"}:`,
      ...entries.map(networkOpenHistoryLine),
      "Backend diagnostics target allowlists remain the source of truth.",
    ].join("\n"));
  }
    return { isNetworkOpenCommand, networkOpenHistoryLine, renderNetworkOpenHistory };
  }

  window.__networkOpenHistoryModule = { createNetworkOpenHistoryModule };
})();
