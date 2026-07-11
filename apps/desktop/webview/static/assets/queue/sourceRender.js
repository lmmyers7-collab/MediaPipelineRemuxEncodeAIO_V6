(function () {
  function createQueueSourceRenderModule(deps = {}) {
    const { byId, queueSourceMeterLabel, queueSourceTileTitle, queueSourceInventoryLines, queueSourceInventoryTileModel, queueScanIsRunning, getLastQueuePayload } = deps;
      function appendQueueSourceChips(card, chips) {
        const visibleChips = (Array.isArray(chips) ? chips : []).filter(Boolean);
        if (!visibleChips.length) return;
        const row = document.createElement("div");
        row.className = "queue-source-chip-row";
        visibleChips.forEach((chip) => {
          const item = document.createElement("span");
          item.className = "queue-source-chip";
          item.dataset.tone = chip.tone || "muted";
          item.textContent = chip.label || "";
          if (chip.title) item.title = chip.title;
          row.appendChild(item);
        });
        card.appendChild(row);
      }

      function appendQueueSourceMeter(card, segments) {
        const visibleSegments = (Array.isArray(segments) ? segments : []).filter((segment) => Number(segment?.count || 0) > 0);
        if (!visibleSegments.length) return;
        const meter = document.createElement("div");
        meter.className = "queue-source-meter";
        meter.setAttribute("role", "img");
        meter.setAttribute("aria-label", queueSourceMeterLabel(visibleSegments));
        visibleSegments.forEach((segment) => {
          const item = document.createElement("span");
          const count = Math.max(0, Number(segment.count || 0));
          item.className = "queue-source-meter-segment";
          item.dataset.tone = segment.tone || "info";
          item.style.flexGrow = String(count || 1);
          item.title = `${segment.label} ${count}`;
          meter.appendChild(item);
        });
        card.appendChild(meter);
      }

      function appendQueueSourcePaths(card, paths) {
        const visiblePaths = (Array.isArray(paths) ? paths : []).filter((path) => path?.label);
        if (!visiblePaths.length) return;
        const row = document.createElement("div");
        row.className = "queue-source-path-list";
        visiblePaths.forEach((path) => {
          const item = document.createElement("span");
          item.className = "queue-source-path";
          item.title = path.title || path.label;
          const label = document.createElement("span");
          label.textContent = path.label || "";
          const count = document.createElement("strong");
          count.textContent = String(path.count || 0);
          item.append(label, count);
          row.appendChild(item);
        });
        card.appendChild(row);
      }

      function appendQueueSourceTile(board, tile) {
        const card = document.createElement("section");
        card.className = "queue-source-tile";
        card.dataset.tone = tile.tone || "muted";
        if (String(tile.label || "").trim().toLowerCase() === "scan freshness") {
          card.setAttribute("role", "button");
          card.setAttribute("tabindex", "0");
          card.dataset.uiQuickLink = "";
          card.dataset.quickLinkPage = "queue";
          card.dataset.quickLinkFocus = "[data-queue-refresh-button]";
          card.setAttribute("aria-label", "Focus Scan Sources button");
        }
        const title = tile.title || queueSourceTileTitle(tile);
        if (title) {
          card.title = title;
          if (typeof card.hasAttribute !== "function" || !card.hasAttribute("aria-label")) card.setAttribute("aria-label", title);
        }
        const header = document.createElement("div");
        header.className = "queue-source-tile-header";
        const label = document.createElement("span");
        label.className = "queue-source-tile-label";
        label.textContent = tile.label || "";
        header.appendChild(label);
        if (tile.meta) {
          const meta = document.createElement("span");
          meta.className = "queue-source-tile-meta";
          meta.textContent = tile.meta;
          header.appendChild(meta);
        }
        const value = document.createElement("strong");
        value.className = "queue-source-tile-value";
        value.textContent = tile.value || "";
        card.append(header, value);
        appendQueueSourceMeter(card, tile.meter);
        appendQueueSourceChips(card, tile.chips);
        appendQueueSourcePaths(card, tile.paths);
        const detail = document.createElement("span");
        detail.className = "queue-source-tile-detail";
        detail.textContent = tile.detail || "";
        card.appendChild(detail);
        board.appendChild(card);
      }

      function renderQueueSourceInventoryMessage(lines, tone = "info") {
        const root = byId("queue-source-inventory");
        if (!root) return;
        root.replaceChildren();
        const card = document.createElement("section");
        card.className = "queue-source-tile queue-source-message-tile";
        card.dataset.tone = tone;
        card.setAttribute("role", "button");
        card.setAttribute("tabindex", "0");
        card.dataset.uiQuickLink = "";
        card.dataset.quickLinkPage = "queue";
        card.dataset.quickLinkFocus = "[data-queue-refresh-button]";
        card.setAttribute("aria-label", "Focus Scan Sources button");
        card.title = "Focus Scan Sources button";
        const value = document.createElement("strong");
        value.className = "queue-source-tile-value";
        value.textContent = lines[0] || "Queue source inventory";
        const detail = document.createElement("span");
        detail.className = "queue-source-tile-detail";
        detail.textContent = lines.slice(1).join(" ");
        card.append(value, detail);
        root.appendChild(card);
      }

      function renderQueueScanArtifacts(queue = getLastQueuePayload()) {
        const root = byId("queue-source-inventory");
        if (root) {
          const lines = queueSourceInventoryLines(queue);
          const board = document.createElement("div");
          board.className = "queue-source-tile-board";
          queueSourceInventoryTileModel(queue).forEach((tile) => appendQueueSourceTile(board, tile));

          const details = document.createElement("details");
          details.className = "queue-source-detail-disclosure";
          const summary = document.createElement("summary");
          summary.textContent = "Source inventory details";
          const body = document.createElement("pre");
          body.className = "prose-block";
          body.textContent = lines.join("\n");
          details.append(summary, body);

          root.replaceChildren(board, details);
        }
        window.mediaPipelineAppRefresh?.setQueueRefreshButtonBusy?.(queueScanIsRunning(queue));
      }

    return { renderQueueSourceInventoryMessage, renderQueueScanArtifacts };
  }
  window.__queueSourceRenderModule = { createQueueSourceRenderModule };
})();
