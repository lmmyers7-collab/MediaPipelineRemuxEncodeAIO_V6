// Network overview tile renderer. Loaded before networkView.js.
(function () {
  function createNetworkOverviewTilesModule(deps = {}) {
    const byId = typeof deps.byId === "function" ? deps.byId : () => null;
    const networkTileTone = typeof deps.networkTileTone === "function" ? deps.networkTileTone : () => "muted";
    const document = deps.documentRef || window.document;

  function renderOverviewTiles(elementId, tiles) {
    const target = byId(elementId);
    if (!target) return;
    target.replaceChildren();
    (Array.isArray(tiles) ? tiles : []).forEach((tile) => {
      const item = document.createElement("div");
      item.className = "review-tile";
      if (tile.tone) item.dataset.tone = networkTileTone(tile.tone);
      const labelText = String(tile.label || "").trim().toLowerCase();
      const isCoordinator = elementId === "network-coordinator-overview-tiles";
      const focusSelector = isCoordinator
        ? (labelText.includes("queue") || labelText.includes("priority")
          ? "#network-coordinator-queue-rows"
          : "#network-coordinator-active-rows")
        : "#network-worker-claim-rows";
      item.setAttribute("role", "button");
      item.setAttribute("tabindex", "0");
      item.dataset.uiQuickLink = "";
      item.dataset.quickLinkPage = "network";
      item.dataset.quickLinkFocus = focusSelector;
      item.setAttribute("aria-label", `Focus ${tile.label || "network"} evidence`);
      item.title = `Focus ${tile.label || "network"} evidence`;
      const label = document.createElement("span");
      label.className = "review-tile-label";
      label.textContent = tile.label || "";
      const value = document.createElement("strong");
      value.className = "review-tile-value";
      value.textContent = tile.value || "";
      const detail = document.createElement("span");
      detail.className = "review-tile-detail";
      detail.textContent = tile.detail || "";
      item.append(label, value, detail);
      target.appendChild(item);
    });
  }


    return { renderOverviewTiles };
  }
  window.__networkOverviewTilesModule = { createNetworkOverviewTilesModule };
})();

