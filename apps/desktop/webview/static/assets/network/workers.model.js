// Network worker state projection, filtering, and detail-model helpers.
(function () {
  "use strict";

  function createNetworkWorkersModelModule(deps = {}) {
    const {
      appendCells = () => {},
      byId = () => null,
      clearRows = () => {},
      networkRows = () => [],
      networkWorkerHasClaimEvidence = () => false,
      networkWorkerLooksCompleteOrIdle = () => false,
      setText = () => {},
      state = {},
      workerHeartbeatText = () => "-",
      workerProgressText = () => "-",
    } = deps;
    const documentRef = deps.documentRef || document;

  function renderNetworkSettingsRows(settings) {
    const rows = networkRows(settings);
    setText("network-settings-status", `${rows.length} setting${rows.length === 1 ? "" : "s"}`);
    const tbody = byId("network-settings-rows");
    if (!tbody) return;
    if (!rows.length) {
      clearRows(tbody, 4, "No network settings loaded.");
      return;
    }
    tbody.replaceChildren();
    rows.forEach((item) => {
      const row = documentRef.createElement("tr");
      row.title = item.key;
      appendCells(row, [item.section, item.label, item.value, item.purpose]);
      tbody.appendChild(row);
    });
  }

  function workerDisplayValue(value, fallback = "-") {
    if (value === undefined || value === null || value === "") return fallback;
    if (typeof value === "object") {
      try {
        return JSON.stringify(value);
      } catch (error) {
        return fallback;
      }
    }
    return String(value);
  }

  function networkWorkerRowKey(item) {
    if (!item || typeof item !== "object") return "";
    const parts = [
      item.worker_id,
      item.worker_name,
      item.job_id,
      item.source_file,
      item.current_file,
      item.current_file_name,
    ].filter((value) => value !== undefined && value !== null && String(value).trim());
    return parts.join("\u001f").toLowerCase();
  }

  function getSelectedNetworkWorkerRow() {
    if (!state.selectedWorkerKey) return null;
    return state.workerRows.find((item) => networkWorkerRowKey(item) === state.selectedWorkerKey) || null;
  }

  function networkWorkerStatusState(item) {
    const status = String(item?.status || "").toLowerCase();
    const stage = String(item?.current_stage || "").toLowerCase();
    const looksActive = status.includes("active")
      || status.includes("running")
      || status.includes("working")
      || status.includes("claimed")
      || status.includes("busy")
      || stage.includes("active")
      || stage.includes("running")
      || stage.includes("working")
      || stage.includes("claimed")
      || stage.includes("busy")
      || stage.includes("encode")
      || stage.includes("remux")
      || stage.includes("poll");
    if (status.includes("fail") || status.includes("error") || status.includes("offline") || status.includes("stale") || stage.includes("fail")) return "blocked";
    if (item?.worker_misconfigured_reason_code) return "blocked";
    if (looksActive && networkWorkerHasClaimEvidence(item)) return "running";
    if (looksActive) return "warning";
    if (item?.last_failure_reason_code || item?.last_failure_reason) return "warning";
    if (networkWorkerLooksCompleteOrIdle(item)) return "match";
    return "unknown";
  }

  function networkWorkerFilterText(item) {
    if (!item || typeof item !== "object") return "";
    return Object.keys(item)
      .sort()
      .map((key) => `${key} ${workerDisplayValue(item[key], "")}`)
      .join(" ")
      .toLowerCase();
  }

  function networkWorkerMatchesStatusFilter(item) {
    const filter = state.workerStatusFilter;
    if (!filter) return true;
    const workerState = networkWorkerStatusState(item);
    if (filter === "active") return workerState === "running";
    if (filter === "idle") return workerState === "match";
    if (filter === "problem") return workerState === "blocked" || workerState === "warning";
    if (filter === "unknown") return workerState === "unknown" || !workerState;
    return true;
  }

  function networkWorkerMatchesViewPreset(item) {
    const preset = String(state.workerViewPreset || "").trim().toLowerCase();
    if (!preset) return true;
    const workerState = networkWorkerStatusState(item);
    const text = networkWorkerFilterText(item);
    if (preset === "attention") return workerState === "running" || workerState === "blocked" || workerState === "warning";
    if (preset === "active") return workerState === "running";
    if (preset === "idle") return workerState === "match";
    if (preset === "stale") return workerState === "blocked" || workerState === "warning" || text.includes("fail") || text.includes("stale");
    if (preset === "path-auth") return text.includes("path") || text.includes("auth") || text.includes("source_not_found") || text.includes("misconfigured");
    return true;
  }

  function filteredNetworkWorkerRows(rows) {
    const query = state.workerSearchText.trim().toLowerCase();
    return (Array.isArray(rows) ? rows : []).filter((item) => {
      if (!networkWorkerMatchesViewPreset(item)) return false;
      if (!networkWorkerMatchesStatusFilter(item)) return false;
      return !query || networkWorkerFilterText(item).includes(query);
    });
  }

  function networkWorkerViewPresetLabel() {
    const labels = {
      attention: "Needs Attention",
      active: "Active Work",
      idle: "Idle",
      stale: "Stale/Failed",
      "path-auth": "Path/Auth",
    };
    return labels[state.workerViewPreset] || "All";
  }

  function networkWorkerFilterLabel() {
    const parts = [];
    if (state.workerViewPreset) parts.push(`view=${networkWorkerViewPresetLabel()}`);
    if (state.workerStatusFilter) parts.push(`status=${state.workerStatusFilter}`);
    if (state.workerSearchText.trim()) parts.push(`search="${state.workerSearchText.trim()}"`);
    return parts.length ? parts.join("; ") : "none";
  }

  function networkWorkerRowsNeedingReview(rows) {
    return (Array.isArray(rows) ? rows : []).filter((item) => {
      const state = networkWorkerStatusState(item);
      return state === "running" || state === "blocked" || state === "warning";
    });
  }

  function renderNetworkWorkerFilterSummary(rows, visibleRows) {
    const allRows = Array.isArray(rows) ? rows : [];
    const shownRows = Array.isArray(visibleRows) ? visibleRows : [];
    if (!allRows.length) {
      setText(
        "network-worker-filter-summary",
        "No persisted worker rows are loaded. Open Cluster Log, ActiveJobs, or State before troubleshooting worker lifecycle."
      );
      return;
    }
    const visibleKeys = new Set(shownRows.map(networkWorkerRowKey));
    const hiddenReviewRows = networkWorkerRowsNeedingReview(allRows)
      .filter((row) => !visibleKeys.has(networkWorkerRowKey(row)));
    const reviewText = hiddenReviewRows.length
      ? `${hiddenReviewRows.length} active/problem/review hidden; clear filters before lifecycle decisions.`
      : "No active/problem/review rows hidden.";
    setText(
      "network-worker-filter-summary",
      `Showing ${shownRows.length}/${allRows.length}. Filter: ${networkWorkerFilterLabel()}. ${reviewText} Filters are visual only.`
    );
  }

  function networkWorkerDetailLines(item) {
    if (!item || typeof item !== "object") {
      return [
        "No network worker row selected.",
        "Select a worker row to inspect persisted coordinator/worker state, current file, progress, heartbeat, and available row fields.",
        "Lifecycle controls remain backend-owned. This detail pane is read-only persisted state.",
      ];
    }
    const knownKeys = new Set([
      "worker_name",
      "worker_id",
      "status",
      "job_id",
      "current_file",
      "current_file_name",
      "source_file",
      "current_stage",
      "progress_percent",
      "heartbeat_age_seconds",
      "last_heartbeat",
      "files_completed",
      "total_gb_encoded",
      "avg_speed_gbh",
      "current_speed_gbh",
      "return_code",
      "error",
      "last_failure_reason_code",
      "last_failure_reason",
      "last_failure_job_id",
      "last_failure_source_path",
      "last_failure_at",
      "failure_streak_reason_code",
      "failure_streak_count",
      "worker_misconfigured_reason_code",
      "worker_misconfigured_at",
      "accessible_library_ids",
    ]);
    const lines = [
      `Worker: ${workerDisplayValue(item.worker_name || item.worker_id)}`,
      `Worker ID: ${workerDisplayValue(item.worker_id)}`,
      `Status: ${workerDisplayValue(item.status)}`,
      `Accessible libraries: ${workerLibraryCapabilityText(item)}`,
      `Job: ${workerDisplayValue(item.job_id)}`,
      `Current file: ${workerDisplayValue(item.current_file_name || item.current_file)}`,
      `Source file: ${workerDisplayValue(item.source_file)}`,
      `Stage: ${workerDisplayValue(item.current_stage)}`,
      `Progress: ${workerProgressText(item)}`,
      `Heartbeat age: ${workerHeartbeatText(item)}`,
      `Last heartbeat: ${workerDisplayValue(item.last_heartbeat)}`,
      `Files completed: ${workerDisplayValue(item.files_completed)}`,
      `Total GB encoded: ${workerDisplayValue(item.total_gb_encoded)}`,
      `Average GB/h: ${workerDisplayValue(item.avg_speed_gbh)}`,
      `Current GB/h: ${workerDisplayValue(item.current_speed_gbh)}`,
      `Return code: ${workerDisplayValue(item.return_code)}`,
      `Last failure code: ${workerDisplayValue(item.last_failure_reason_code)}`,
      `Last failure reason: ${workerDisplayValue(item.last_failure_reason)}`,
      `Last failure job: ${workerDisplayValue(item.last_failure_job_id)}`,
      `Last failure source: ${workerDisplayValue(item.last_failure_source_path)}`,
      `Last failure at: ${workerDisplayValue(item.last_failure_at)}`,
      `Failure streak: ${workerDisplayValue(item.failure_streak_count)} ${workerDisplayValue(item.failure_streak_reason_code)}`,
      `Worker misconfigured code: ${workerDisplayValue(item.worker_misconfigured_reason_code)}`,
      `Worker misconfigured at: ${workerDisplayValue(item.worker_misconfigured_at)}`,
    ];
    if (item.error) lines.push(`Error: ${workerDisplayValue(item.error)}`);
    const extraKeys = Object.keys(item)
      .filter((key) => !knownKeys.has(key) && workerDisplayValue(item[key], "") !== "")
      .sort()
      .slice(0, 12);
    if (extraKeys.length) {
      lines.push("", "Additional row fields:");
      extraKeys.forEach((key) => lines.push(`- ${key}: ${workerDisplayValue(item[key])}`));
    }
    lines.push("", "Lifecycle controls remain backend-owned. This detail pane is read-only persisted state.");
    return lines;
  }

  function workerLibraryCapabilityText(item) {
    const ids = Array.isArray(item?.accessible_library_ids)
      ? item.accessible_library_ids
        .map((value) => String(value || "").trim())
        .filter(Boolean)
      : [];
    return ids.length ? ids.join(", ") : "unknown/not reported";
  }

  function workerPendingDoneReportText(item) {
    if (item?.pending_done_report === true || item?.done_report_pending === true) return "yes";
    if (item?.pending_done_report === false || item?.done_report_pending === false) return "no";
    return "-";
  }

  function workerLastResultText(item) {
    if (!item || typeof item !== "object") return "-";
    if (item.worker_misconfigured_reason_code) return `Misconfigured: ${workerDisplayValue(item.worker_misconfigured_reason_code)}`;
    if (item.last_failure_reason_code) return `Failed: ${workerDisplayValue(item.last_failure_reason_code)}`;
    if (item.last_failure_reason) return `Failed: ${workerDisplayValue(item.last_failure_reason)}`;
    if (item.error) return `Error: ${workerDisplayValue(item.error)}`;
    if (item.return_code !== undefined && item.return_code !== null && item.return_code !== "") return `Exit ${item.return_code}`;
    if (item.files_completed !== undefined && item.files_completed !== null && item.files_completed !== "") return `${item.files_completed} done`;
    if (networkWorkerLooksCompleteOrIdle(item)) return workerDisplayValue(item.status || "idle");
    return "-";
  }

  function workerThroughputText(item) {
    if (!item || typeof item !== "object") return "-";
    if (item.current_speed_gbh !== undefined && item.current_speed_gbh !== null && item.current_speed_gbh !== "") {
      return `${item.current_speed_gbh} GB/h current`;
    }
    if (item.avg_speed_gbh !== undefined && item.avg_speed_gbh !== null && item.avg_speed_gbh !== "") {
      return `${item.avg_speed_gbh} GB/h avg`;
    }
    if (item.total_gb_encoded !== undefined && item.total_gb_encoded !== null && item.total_gb_encoded !== "") {
      return `${item.total_gb_encoded} GB encoded`;
    }
    return "-";
  }
    return {
      renderNetworkSettingsRows,
      workerDisplayValue,
      networkWorkerRowKey,
      getSelectedNetworkWorkerRow,
      networkWorkerStatusState,
      networkWorkerFilterText,
      networkWorkerMatchesStatusFilter,
      networkWorkerMatchesViewPreset,
      filteredNetworkWorkerRows,
      networkWorkerViewPresetLabel,
      networkWorkerFilterLabel,
      networkWorkerRowsNeedingReview,
      renderNetworkWorkerFilterSummary,
      networkWorkerDetailLines,
      workerLibraryCapabilityText,
      workerPendingDoneReportText,
      workerLastResultText,
      workerThroughputText,
    };
  }

  window.__networkWorkersModelModule = { createNetworkWorkersModelModule };
})();
