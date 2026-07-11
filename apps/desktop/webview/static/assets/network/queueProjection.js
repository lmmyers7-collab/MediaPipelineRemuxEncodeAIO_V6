// Network queue/worker evidence normalization and matching. Loaded before networkView.js.
(function () {
  function createNetworkQueueProjectionModule() {

  function networkDisplayValue(value, fallback = "-") {
    if (value === undefined || value === null || value === "") return fallback;
    if (typeof value === "object") {
      try {
        return JSON.stringify(value);
      } catch (_error) {
        return fallback;
      }
    }
    return String(value);
  }

  function networkNumber(value, fallback = 0) {
    const numeric = Number(value);
    return Number.isFinite(numeric) ? numeric : fallback;
  }

  function networkNormalizePathKey(value) {
    return String(value || "")
      .trim()
      .replace(/\\/g, "/")
      .replace(/\/+/g, "/")
      .toLowerCase();
  }

  function networkBasename(value) {
    const normalized = String(value || "").trim().replace(/\\/g, "/");
    const parts = normalized.split("/").filter(Boolean);
    return parts.length ? parts[parts.length - 1] : normalized;
  }

  function networkAddSourceKey(keys, value) {
    const normalized = networkNormalizePathKey(value);
    if (!normalized) return;
    keys.add(normalized);
    const leaf = networkNormalizePathKey(networkBasename(normalized));
    if (leaf) keys.add(leaf);
  }

  function networkSourceKeysFromRow(row) {
    const keys = new Set();
    if (!row || typeof row !== "object") return keys;
    [
      row.source_path,
      row.source_file,
      row.source,
      row.current_file,
      row.current_file_name,
      row.file,
      row.file_name,
      row.path,
      row.display_name,
      row.name,
      row.input_path,
      row.media_path,
    ].forEach((value) => networkAddSourceKey(keys, value));
    return keys;
  }

  function networkSourcePathKeysFromRow(row) {
    const keys = new Set();
    if (!row || typeof row !== "object") return keys;
    [
      row.source_path,
      row.source_file,
      row.source,
      row.current_file,
      row.path,
      row.input_path,
      row.media_path,
    ].forEach((value) => {
      const normalized = networkNormalizePathKey(value);
      if (normalized && normalized.includes("/")) keys.add(normalized);
    });
    return keys;
  }

  function networkQueueRows(queue) {
    if (Array.isArray(queue?.rows)) return queue.rows;
    if (Array.isArray(queue?.queue_rows)) return queue.queue_rows;
    if (Array.isArray(queue?.items)) return queue.items;
    return [];
  }

  function networkQueueMatchMaps(queueRows) {
    const byPath = new Map();
    (Array.isArray(queueRows) ? queueRows : []).forEach((row) => {
      networkSourcePathKeysFromRow(row).forEach((key) => {
        if (!key) return;
        if (!byPath.has(key)) byPath.set(key, row);
      });
    });
    return { byPath };
  }

  function networkMatchedQueueRow(row, maps) {
    if (!row || !maps) return null;
    const keys = Array.from(networkSourcePathKeysFromRow(row));
    for (const key of keys) {
      if (key.includes("/") && maps.byPath?.has(key)) return maps.byPath.get(key);
    }
    return null;
  }

  function networkQueueFileLabel(row) {
    return networkDisplayValue(
      row?.display_name || row?.current_file_name || row?.file_name || networkBasename(row?.source_path || row?.source_file || row?.current_file || row?.path || row?.name),
      "Unknown file"
    );
  }

  function networkRouteName(row) {
    const route = row?.route_name || row?.route || row?.route_action || row?.action || row?.decision || row?.operation;
    return String(route || "").trim();
  }

  function networkRouteLabel(row) {
    const route = networkRouteName(row);
    if (!route) return "";
    return route.replace(/[_-]+/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
  }

  function networkRouteTone(row) {
    const route = networkRouteName(row).toLowerCase();
    if (route.includes("remux")) return "remux";
    if (route.includes("encode") || route.includes("transcode")) return "encode";
    if (route.includes("skip") || route.includes("copy")) return "skip";
    return "review";
  }

  function networkRouteEvidence(row) {
    return networkDisplayValue(row?.route_reason_code || row?.route_decision_summary || row?.reason || row?.decision_reason || row?.operator_status, "queue row");
  }

  function networkPriorityText(row) {
    if (row?.manifest_priority_level !== undefined && row.manifest_priority_level !== null && row.manifest_priority_level !== "") return String(row.manifest_priority_level);
    if (row?.priority !== undefined && row.priority !== null && row.priority !== "") return String(row.priority);
    if (row?.manual_order !== undefined && row.manual_order !== null && row.manual_order !== "") return `manual ${row.manual_order}`;
    if (row?.is_priority === true || row?.priority_flag === true) return "priority";
    return "normal";
  }

  function networkSizeText(row) {
    const gb = Number(row?.size_gb ?? row?.source_size_gb ?? row?.file_size_gb);
    if (Number.isFinite(gb) && gb > 0) return `${gb.toFixed(gb >= 10 ? 1 : 2)} GB`;
    const bytes = Number(row?.size_bytes ?? row?.source_size_bytes ?? row?.file_size_bytes);
    if (Number.isFinite(bytes) && bytes > 0) return `${(bytes / (1024 ** 3)).toFixed(2)} GB`;
    return "-";
  }

  function networkQueueOrder(row, index) {
    const value = row?.global_order ?? row?.queue_index ?? row?.order ?? row?.index;
    const numeric = Number(value);
    return Number.isFinite(numeric) && numeric > 0 ? Math.round(numeric) : index + 1;
  }

  function networkQueueStatus(queue, queueRows) {
    const status = String(queue?.produced_freshness_status || queue?.snapshot_file_freshness_status || queue?.freshness_status || queue?.status || "").trim();
    if (status) return status.charAt(0).toUpperCase() + status.slice(1);
    return queueRows.length ? "Loaded" : "Not loaded";
  }

  function networkWorkerHasClaimEvidence(row) {
    if (!row || typeof row !== "object") return false;
    return Boolean(row.job_id || row.current_file || row.current_file_name || row.source_file || row.source_path || row.pending_done_report);
  }

  function networkWorkerLooksCompleteOrIdle(row) {
    const status = String(row?.status || "").toLowerCase();
    const stage = String(row?.current_stage || "").toLowerCase();
    return status.includes("idle")
      || status.includes("done")
      || status.includes("complete")
      || status.includes("ready")
      || stage.includes("idle")
      || stage.includes("done")
      || stage.includes("complete");
  }

  function networkClaimIsActive(row) {
    if (!networkWorkerHasClaimEvidence(row)) return false;
    if (row?.pending_done_report) return true;
    const status = String(row?.status || "").toLowerCase();
    const stage = String(row?.current_stage || "").toLowerCase();
    if (status.includes("fail") || status.includes("error") || status.includes("offline") || status.includes("stale") || stage.includes("fail")) {
      return false;
    }
    return !networkWorkerLooksCompleteOrIdle(row);
  }

  function networkClaimedKeySet(networkWorkers) {
    const keys = new Set();
    const rows = Array.isArray(networkWorkers?.rows) ? networkWorkers.rows : [];
    rows.filter(networkClaimIsActive).forEach((row) => {
      networkSourcePathKeysFromRow(row).forEach((key) => keys.add(key));
    });
    const workerState = networkWorkers?.worker_state && typeof networkWorkers.worker_state === "object" ? networkWorkers.worker_state : {};
    if (workerState.job_id || workerState.source_file || workerState.source_path || workerState.current_file || workerState.pending_done_report) {
      networkSourcePathKeysFromRow(workerState).forEach((key) => keys.add(key));
    }
    return keys;
  }

  function networkQueueRowClaimed(row, claimedKeys) {
    for (const key of networkSourcePathKeysFromRow(row)) {
      if (claimedKeys.has(key)) return true;
    }
    return false;
  }

  function networkReviewTile(label, value, detail = "", tone = "") {
    return { label, value, detail, tone };
  }


    return { networkDisplayValue, networkNumber, networkNormalizePathKey, networkBasename, networkSourceKeysFromRow, networkSourcePathKeysFromRow, networkQueueRows, networkQueueMatchMaps, networkMatchedQueueRow, networkQueueFileLabel, networkRouteName, networkRouteLabel, networkRouteTone, networkRouteEvidence, networkPriorityText, networkSizeText, networkQueueOrder, networkQueueStatus, networkWorkerHasClaimEvidence, networkWorkerLooksCompleteOrIdle, networkClaimIsActive, networkClaimedKeySet, networkQueueRowClaimed, networkReviewTile };
  }
  window.__networkQueueProjectionModule = { createNetworkQueueProjectionModule };
})();

