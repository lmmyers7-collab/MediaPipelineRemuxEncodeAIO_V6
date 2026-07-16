(function () {
  function createQueueSourceModelModule(deps = {}) {
    const { shortenPath, queueBlockerEvidence, queueDisplayRowStatus, queueFilteredRowsForCurrentDisplay, queuePathExtension, getLastQueuePayload, getLastQueueRows } = deps;
      function queueScanStatus(queue = getLastQueuePayload()) {
        const payload = queue && typeof queue === "object" ? queue : {};
        const status = payload.queue_scan_status;
        return status && typeof status === "object" ? status : {};
      }

      function queueScanIsRunning(queue = getLastQueuePayload()) {
        const status = queueScanStatus(queue);
        return Boolean(status.running) || String(status.status || "").toLowerCase() === "running";
      }

      function queueSourceInventory(queue = getLastQueuePayload()) {
        const payload = queue && typeof queue === "object" ? queue : {};
        const inventory = payload.source_inventory;
        return inventory && typeof inventory === "object" ? inventory : {};
      }

      function queueScanStatusLines(queue = getLastQueuePayload()) {
        const status = queueScanStatus(queue);
        if (!status.schema_version && !status.status) {
          return ["Queue source scan: not requested in this session."];
        }
        const lines = [
          `Queue source scan: ${status.status || "unknown"}${status.phase ? ` (${status.phase})` : ""}.`,
          status.message || "Latest scan status loaded from backend state.",
        ];
        if (status.scan_id) lines.push(`Scan id: ${status.scan_id}`);
        if (status.inventory_count || status.curated_row_count) {
          lines.push(`Inventory candidates: ${status.inventory_count || 0}; curated queue rows: ${status.curated_row_count || 0}.`);
        }
        if (status.updated_at_utc) lines.push(`Updated: ${status.updated_at_utc}`);
        if (status.inventory_path) lines.push(`Inventory artifact: ${status.inventory_path}`);
        if (status.queue_snapshot_path) lines.push(`Queue snapshot: ${status.queue_snapshot_path}`);
        const warnings = Array.isArray(status.warnings) ? status.warnings : [];
        const errors = Array.isArray(status.errors) ? status.errors : [];
        warnings.slice(0, 3).forEach((warning) => lines.push(`Warning: ${warning}`));
        errors.slice(0, 3).forEach((error) => lines.push(`Error: ${error}`));
        return lines;
      }

      function queueSourceInventoryLines(queue = getLastQueuePayload()) {
        const inventory = queueSourceInventory(queue);
        const rows = Array.isArray(inventory.rows) ? inventory.rows : [];
        const lines = [
          ...queueScanStatusLines(queue),
          "",
          `Fast source inventory: ${inventory.row_count || inventory.available_row_count || rows.length || 0} candidate file(s).`,
          "Inventory candidates are not launchable queue rows. Wait for backend curation before Launch decisions.",
        ];
        const summary = Array.isArray(inventory.summary_lines) ? inventory.summary_lines : [];
        summary.slice(0, 4).forEach((line) => lines.push(String(line)));
        if (inventory.preview_truncated) {
          lines.push(`Preview truncated: showing ${rows.length} of ${inventory.available_row_count || inventory.row_count || rows.length} inventory rows.`);
        }
        if (rows.length) {
          lines.push("", "Newest inventory candidates:");
          rows.slice(0, 12).forEach((row) => {
            const kind = String(row.media_kind || "media").toUpperCase();
            const name = row.relative_path || row.display_name || row.source_path || "";
            const size = Number(row.size_gb);
            const sizeText = Number.isFinite(size) && size > 0 ? `${size.toFixed(3)} GB` : `${row.size_bytes || 0} bytes`;
            lines.push(`- [${kind}] ${name} (${sizeText})`);
          });
        }
        return lines;
      }

      function queueSourceInventorySizeGb(row) {
        const sizeGb = Number(row?.size_gb);
        if (Number.isFinite(sizeGb) && sizeGb > 0) return sizeGb;
        const sizeBytes = Number(row?.size_bytes);
        return Number.isFinite(sizeBytes) && sizeBytes > 0 ? sizeBytes / (1024 ** 3) : 0;
      }

      function queueFormatSizeGb(sizeGb) {
        const value = Number(sizeGb);
        if (!Number.isFinite(value) || value <= 0) return "0 GB";
        if (value >= 10) return `${value.toFixed(1)} GB`;
        return `${value.toFixed(3)} GB`;
      }

      function queueFirstPositiveNumber(values) {
        const match = values.map((value) => Number(value)).find((value) => Number.isFinite(value) && value > 0);
        return match || 0;
      }

      function queueFirstCountEntry(counts) {
        if (!counts || typeof counts !== "object") return null;
        return Object.entries(counts)
          .map(([label, count]) => ({ label: String(label || "unknown"), count: Number(count || 0) }))
          .filter((entry) => entry.count > 0)
          .sort((a, b) => b.count - a.count || a.label.localeCompare(b.label))[0] || null;
      }

      function queueFormatTopCounts(counts, limit = 3) {
        const entries = queueTopCountEntries(counts, limit);
        return entries.length ? entries.map((entry) => `${entry.label} ${entry.count}`).join("; ") : "No counts loaded";
      }

      function queueTopCountEntries(counts, limit = 3) {
        if (!counts || typeof counts !== "object") return [];
        return Object.entries(counts)
          .map(([label, count]) => ({ label: String(label || "unknown"), count: Number(count || 0) }))
          .filter((entry) => entry.count > 0)
          .sort((a, b) => b.count - a.count || a.label.localeCompare(b.label))
          .slice(0, limit);
      }

      function queuePlural(count, singular, plural = `${singular}s`) {
        return `${count} ${count === 1 ? singular : plural}`;
      }

      function queueSourceChip(label, tone = "muted", title = "") {
        const text = String(label || "").trim();
        return text ? { label: text, tone, title: String(title || text) } : null;
      }

      function queueSourceCompactStatus(value, fallback = "not scanned") {
        return String(value || fallback)
          .trim()
          .replace(/[_-]+/g, " ")
          .replace(/\s+/g, " ")
          .toLowerCase();
      }

      function queueSourceCompactTimestamp(value) {
        const text = String(value || "").trim();
        if (!text) return "";
        const compact = text
          .replace("T", " ")
          .replace(/\.\d+Z?$/i, "Z")
          .replace(/Z$/i, "Z");
        return compact.length > 16 ? compact.slice(0, 16) : compact;
      }

      function queueSourceCompactPath(value, maxChars = 46) {
        const text = String(value || "").trim();
        if (!text) return "";
        if (shortenPath) return shortenPath(text, maxChars);
        if (text.length <= maxChars) return text;
        const parts = text.split(/[\\/]+/).filter(Boolean);
        const leaf = parts[parts.length - 1] || text;
        const root = parts[0] || "";
        const compact = root && root !== leaf ? `${root}/.../${leaf}` : `.../${leaf}`;
        return compact.length <= maxChars ? compact : compact.slice(0, Math.max(0, maxChars - 3)) + "...";
      }

      function queueSourceEntryLabel(entry, maxChars = 34) {
        return queueSourceCompactPath(entry?.label, maxChars);
      }

      function queueSourceMeterSegments(entries, toneByLabel = {}) {
        return (Array.isArray(entries) ? entries : [])
          .map((entry) => ({
            label: String(entry?.label || "unknown"),
            count: Number(entry?.count || 0),
            tone: toneByLabel[String(entry?.label || "").toLowerCase()] || entry?.tone || "info",
          }))
          .filter((entry) => entry.count > 0);
      }

      function queueSourceMeterLabel(segments) {
        return (Array.isArray(segments) ? segments : [])
          .map((segment) => `${segment.label} ${segment.count}`)
          .join("; ");
      }

      function queueSourcePrimaryCounts(entries, limit = 2) {
        const visible = (Array.isArray(entries) ? entries : []).slice(0, limit);
        return visible.length ? visible.map((entry) => `${entry.label} ${entry.count}`).join(" / ") : "No counts";
      }

      function queueCountBy(rows, keyFn) {
        return (Array.isArray(rows) ? rows : []).reduce((counts, row) => {
          const key = String(keyFn(row) || "unknown").trim() || "unknown";
          counts[key] = Number(counts[key] || 0) + 1;
          return counts;
        }, {});
      }

      function queueRowReadinessCounts(rows) {
        return (Array.isArray(rows) ? rows : []).reduce((counts, row) => {
          const status = String(queueDisplayRowStatus(row) || "").toLowerCase();
          const blocker = typeof queueBlockerEvidence === "function" ? queueBlockerEvidence(row) : { blocked: false };
          if (blocker.blocked || status.includes("blocked") || status.includes("failed") || status.includes("error")) {
            counts.blocked += 1;
          } else if (
            status.includes("warning")
            || status.includes("review")
            || status.includes("validation")
            || status.includes("unknown")
            || status.includes("parked")
            || status.includes("paused")
            || status.includes("retry")
          ) {
            counts.warning += 1;
          } else {
            counts.ready += 1;
          }
          return counts;
        }, { ready: 0, warning: 0, blocked: 0 });
      }

      function queueScanStatusTone(status) {
        const text = String(status?.status || "").toLowerCase();
        const errors = Array.isArray(status?.errors) ? status.errors : [];
        const warnings = Array.isArray(status?.warnings) ? status.warnings : [];
        if (errors.length || text.includes("fail") || text.includes("error")) return "danger";
        if (warnings.length || text.includes("warning")) return "warning";
        if (Boolean(status?.running) || text.includes("running") || text.includes("scan")) return "info";
        if (text.includes("complete") || text.includes("success") || text === "ok") return "success";
        return "muted";
      }

      function queueSourceInventoryLargestRow(rows) {
        return (Array.isArray(rows) ? rows : []).reduce((largest, row) => {
          const sizeGb = queueSourceInventorySizeGb(row);
          return sizeGb > largest.sizeGb ? { row, sizeGb } : largest;
        }, { row: null, sizeGb: 0 });
      }

      function queueSourceInventoryTileModel(queue = getLastQueuePayload()) {
        const payload = queue && typeof queue === "object" ? queue : {};
        const inventory = queueSourceInventory(payload);
        const inventoryRows = Array.isArray(inventory.rows) ? inventory.rows : [];
        const queueRows = Array.isArray(getLastQueueRows()) ? getLastQueueRows() : [];
        const filteredRows = typeof queueFilteredRowsForCurrentDisplay === "function" ? queueFilteredRowsForCurrentDisplay() : queueRows;
        const status = queueScanStatus(payload);
        const candidateCount = queueFirstPositiveNumber([inventory.row_count, inventory.available_row_count, inventoryRows.length, status.inventory_count]);
        const curatedCount = queueFirstPositiveNumber([status.curated_row_count, queueRows.length]);
        const totalSizeGb = inventoryRows.reduce((total, row) => total + queueSourceInventorySizeGb(row), 0);
        const readiness = queueRowReadinessCounts(queueRows);
        const topBlocker = queueFirstCountEntry(payload.blocked_reason_counts) || queueFirstCountEntry(payload.blocked_reason_code_counts);
        const routeCounts = payload.route_counts && typeof payload.route_counts === "object"
          ? payload.route_counts
          : queueCountBy(queueRows, (row) => row.route_name || row.route || row.route_decision || "unknown");
        const sourceRootCounts = payload.source_root_counts && typeof payload.source_root_counts === "object"
          ? payload.source_root_counts
          : inventory.source_root_counts;
        const sourceRootTotal = sourceRootCounts && typeof sourceRootCounts === "object" ? Object.keys(sourceRootCounts).length : 0;
        const largest = queueSourceInventoryLargestRow(inventoryRows);
        const largestName = largest.row?.relative_path || largest.row?.display_name || largest.row?.source_path || "No preview item loaded";
        const visibleCount = Array.isArray(filteredRows) ? filteredRows.length : queueRows.length;
        const hiddenByFilterCount = Math.max(0, queueRows.length - visibleCount);
        const scanUpdated = queueSourceCompactTimestamp(status.updated_at_utc);
        const routeEntries = queueTopCountEntries(routeCounts, 3);
        const sourceRootEntries = queueTopCountEntries(sourceRootCounts, 2);
        const readinessSegments = queueSourceMeterSegments([
          { label: "ready", count: readiness.ready },
          { label: "warning", count: readiness.warning },
          { label: "blocked", count: readiness.blocked },
        ], { ready: "success", warning: "warning", blocked: "danger" });
        const routeSegments = queueSourceMeterSegments(routeEntries, {});
        const filterSegments = queueSourceMeterSegments([
          { label: "visible", count: visibleCount, tone: visibleCount === queueRows.length ? "success" : "info" },
          { label: "hidden", count: hiddenByFilterCount, tone: "warning" },
        ]);
        const largestKind = queueSourceCompactStatus(largest.row?.media_kind || largest.row?.media_type || "", "");
        const largestExt = queuePathExtension(largestName) || queuePathExtension(largest.row?.source_path || "");
        return [
          {
            label: "Scan Freshness",
            value: queueSourceCompactStatus(status.status, "not scanned"),
            meta: scanUpdated || "",
            chips: [
              queueSourceChip(candidateCount ? queuePlural(candidateCount, "candidate") : "", "info"),
              queueSourceChip(curatedCount ? queuePlural(curatedCount, "curated row") : "", "muted"),
            ].filter(Boolean),
            detail: status.message || (status.updated_at_utc ? `Updated ${status.updated_at_utc}` : "No backend scan status loaded."),
            tone: queueScanStatusTone(status),
          },
          {
            label: "Queue Size",
            value: `${curatedCount} row${curatedCount === 1 ? "" : "s"}`,
            meta: queueFormatSizeGb(totalSizeGb),
            chips: [
              queueSourceChip(queuePlural(candidateCount, "candidate"), "info"),
              queueSourceChip(`preview ${queueFormatSizeGb(totalSizeGb)}`, "muted"),
            ],
            detail: `${candidateCount} inventory candidate${candidateCount === 1 ? "" : "s"}; preview size ${queueFormatSizeGb(totalSizeGb)}.`,
            tone: curatedCount ? "info" : "muted",
          },
          {
            label: "Launch Readiness",
            value: `Ready ${readiness.ready}`,
            meter: readinessSegments,
            chips: [
              queueSourceChip(`blocked ${readiness.blocked}`, readiness.blocked ? "danger" : "muted"),
              queueSourceChip(`warning ${readiness.warning}`, readiness.warning ? "warning" : "muted"),
            ],
            detail: `Blocked ${readiness.blocked}; Warning ${readiness.warning}.`,
            tone: readiness.blocked ? "danger" : (readiness.warning ? "warning" : (queueRows.length ? "success" : "muted")),
          },
          {
            label: "Top Blocker",
            value: topBlocker ? topBlocker.label : "No blockers",
            chips: [
              queueSourceChip(topBlocker ? queuePlural(topBlocker.count, "row") : "clear", topBlocker ? "danger" : "success"),
            ],
            detail: topBlocker ? `${topBlocker.count} row${topBlocker.count === 1 ? "" : "s"} affected.` : "No blocked reason count in the loaded queue.",
            tone: topBlocker ? "danger" : "success",
          },
          {
            label: "Work Mix",
            value: queueSourcePrimaryCounts(routeEntries, 2),
            meter: routeSegments,
            chips: routeEntries.slice(0, 3).map((entry) => queueSourceChip(`${entry.label} ${entry.count}`, "info")),
            detail: "Highest route counts in the curated queue.",
            tone: queueRows.length ? "info" : "muted",
          },
          {
            label: "Largest Preview",
            value: largest.sizeGb ? queueFormatSizeGb(largest.sizeGb) : "No size",
            chips: [
              queueSourceChip(largestKind, "muted"),
              queueSourceChip(largestExt, "muted"),
            ].filter(Boolean),
            detail: queueSourceCompactPath(largestName, 58),
            fullDetail: largestName,
            tone: largest.sizeGb ? "warning" : "muted",
          },
          {
            label: "Filter Impact",
            value: `${visibleCount}/${queueRows.length}`,
            meter: filterSegments,
            chips: [
              queueSourceChip("view only", "info"),
              queueSourceChip(hiddenByFilterCount ? `${hiddenByFilterCount} hidden` : "all visible", hiddenByFilterCount ? "warning" : "success"),
            ],
            detail: "Visible rows only; backend Launch scope is unchanged.",
            tone: visibleCount === queueRows.length ? "success" : "warning",
          },
          {
            label: "Source Roots",
            value: sourceRootTotal ? `${sourceRootTotal} root${sourceRootTotal === 1 ? "" : "s"}` : "Not reported",
            paths: sourceRootEntries.map((entry) => ({
              label: queueSourceEntryLabel(entry),
              count: entry.count,
              title: entry.label,
            })),
            detail: sourceRootTotal ? queueFormatTopCounts(sourceRootCounts, 2) : "Refresh source inventory to load root evidence.",
            tone: sourceRootTotal ? "info" : "muted",
          },
        ];
      }

    return { queueScanStatus, queueScanIsRunning, queueSourceInventory, queueScanStatusLines, queueSourceInventoryLines, queueSourceInventoryTileModel, queueSourceMeterLabel };
  }
  window.__queueSourceModelModule = { createQueueSourceModelModule };
})();
