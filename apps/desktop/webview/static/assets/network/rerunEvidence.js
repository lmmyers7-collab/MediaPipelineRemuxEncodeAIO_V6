(function () {
  function createNetworkRerunEvidenceModule(deps = {}) {
    const { byId, setText, clearRows, networkAppendCell, networkStatusChip, networkRerunLeaf, networkRerunCompactPath } = deps;
      function networkRerunStatusState(row = {}) {
        const text = String(row.queue_status || row.status || "").toLowerCase();
        if (/(failed|blocked|error)/.test(text)) return "blocked";
        if (/(warning|review|pending_publish|pending_reduction|destination_policy_applying)/.test(text)) return "warning";
        if (/(completed|published|replaced|done|success|ok)/.test(text)) return "match";
        if (/(active|running|claimed|pending|stopped|skipped)/.test(text)) return "unknown";
        return "unknown";
      }

      function networkRerunRows(rerunResults = {}) {
        const manifests = Array.isArray(rerunResults.network_manifests) ? rerunResults.network_manifests : [];
        const fromManifests = manifests.flatMap((manifest) => {
          const rows = Array.isArray(manifest.rows) ? manifest.rows : [];
          return rows.map((row) => ({
            ...row,
            batch_id: row.batch_id || manifest.batch_id,
            manifest_status: row.manifest_status || manifest.status,
            manifest_path: row.manifest_path || manifest.path,
          }));
        });
        if (fromManifests.length) return fromManifests;
        const queueRows = Array.isArray(rerunResults?.queue_state?.rows) ? rerunResults.queue_state.rows : [];
        return queueRows.filter((row) => row?.queue_source === "network_csv_rerun");
      }

      function networkRerunDestinationResult(row = {}) {
        if (row.network_destination_policy_result && typeof row.network_destination_policy_result === "object") {
          return row.network_destination_policy_result;
        }
        const destination = row.destination_state && typeof row.destination_state === "object" ? row.destination_state : {};
        return destination.destination_policy_result && typeof destination.destination_policy_result === "object"
          ? destination.destination_policy_result
          : {};
      }

      function networkRerunOptionalLine(label, value) {
        return value ? `${label}: ${value}` : "";
      }

      function networkRerunAttemptLine(attemptCount, retryLimit) {
        if (attemptCount === null) return "";
        return `Attempts: ${attemptCount}${retryLimit !== null ? ` / ${retryLimit}` : ""}`;
      }

      function networkRerunReducerLine(accepted) {
        if (accepted === true) return "Reducer accepted";
        if (accepted === false) return "Reducer rejected";
        return "";
      }

      function networkRerunPathLine(label, value) {
        return value ? `${label}: ${networkRerunLeaf(value)}` : "";
      }

      function networkRerunEvidenceLines(row = {}) {
        const reducer = row.network_reducer_result && typeof row.network_reducer_result === "object" ? row.network_reducer_result : {};
        const worker = row.network_worker_result && typeof row.network_worker_result === "object" ? row.network_worker_result : {};
        const destination = networkRerunDestinationResult(row);
        const attemptCount = Number.isInteger(row.attempt_count) ? row.attempt_count : null;
        const retryLimit = Number.isInteger(row.retry_limit) ? row.retry_limit : null;
        const retryCount = Number.isInteger(row.retry_count) ? row.retry_count : null;
        const timeline = Array.isArray(row.timeline) ? row.timeline : [];
        return [
          networkRerunAttemptLine(attemptCount, retryLimit),
          retryCount !== null ? `Retries: ${retryCount}` : "",
          networkRerunOptionalLine("Next retry", row.next_retry_at_utc),
          networkRerunOptionalLine("Reason code", row.reason_code),
          networkRerunOptionalLine("Error", row.last_error),
          networkRerunOptionalLine("What", row.what),
          networkRerunOptionalLine("Why", row.why),
          networkRerunOptionalLine("When", row.when),
          networkRerunOptionalLine("Next", row.next_action),
          networkRerunOptionalLine("Operator action", row.operator_action),
          timeline.length ? `Timeline events: ${timeline.length}` : "",
          networkRerunOptionalLine("Reducer", reducer.classification),
          networkRerunReducerLine(reducer.accepted),
          networkRerunOptionalLine("Worker", worker.worker_id || worker.worker_name),
          networkRerunOptionalLine("Destination", [destination.status, destination.action].filter(Boolean).join(" / ")),
          networkRerunPathLine("Pending", destination.pending_publish_manifest_path || row.pending_publish_manifest_path),
          networkRerunPathLine("Published", destination.published_path || row.published_path),
          networkRerunOptionalLine("Claim", row.claim_status),
        ].filter(Boolean);
      }

      function renderNetworkRerunRows(rerunResults = {}) {
        const tbody = byId("network-rerun-rows");
        if (!tbody) return;
        const rows = networkRerunRows(rerunResults);
        setText("network-rerun-status", rows.length ? `${rows.length} row${rows.length === 1 ? "" : "s"}` : "No rows");
        const counts = rerunResults?.counts?.network_queue_status_counts && typeof rerunResults.counts.network_queue_status_counts === "object"
          ? rerunResults.counts.network_queue_status_counts
          : {};
        const countText = Object.keys(counts).sort().map((key) => `${key} ${counts[key]}`).join("; ");
        setText("network-rerun-summary", [
          "Network CSV rerun read model: backend-owned /api/rerun/results.",
          `Batches: ${Array.isArray(rerunResults.network_manifests) ? rerunResults.network_manifests.length : 0}; rows: ${rows.length}.`,
          countText ? `Network status counts: ${countText}.` : "No Network CSV rerun status counts loaded.",
        ].join(" "));
        if (!rows.length) {
          clearRows(tbody, 6, "No Network CSV rerun rows loaded.");
          setText("network-rerun-detail", "No Network CSV rerun batch state is visible in the loaded backend read model.");
          return;
        }
        tbody.replaceChildren();
        rows.slice(0, 100).forEach((item) => {
          const row = document.createElement("tr");
          row.dataset.status = networkRerunStatusState(item);
          networkAppendCell(row, item.batch_id || item.manifest_status || "unknown");
          networkAppendCell(row, item.network_rerun_row_key || item.row_key || "");
          networkAppendCell(row, networkStatusChip(item.queue_status_label || item.queue_status || item.status || "unknown", networkRerunStatusState(item)));
          networkAppendCell(row, networkRerunCompactPath(item.original_source_path || item.source_path), "network-overview-table-file");
          networkAppendCell(row, [
            networkRerunCompactPath(item.output_path || item.verified_output_path || item.review_output_path),
            networkRerunCompactPath(item.final_output_path || item.destination_path),
          ].filter(Boolean).join("\n\n"), "network-overview-table-file");
          networkAppendCell(row, networkRerunEvidenceLines(item).join("\n") || "No reducer or destination-policy evidence loaded.");
          tbody.appendChild(row);
        });
        setText("network-rerun-detail", [
          "Rows are read-only backend evidence from /api/rerun/results.",
          "Start controls live in Queue > CSV Rerun and use backend dry-run plus confirmed start routes.",
          "WebView does not author claims, row status, destination policy, Pending Publish paths, or final output paths.",
        ].join("\n"));
      }

    return { renderNetworkRerunRows };
  }
  window.__networkRerunEvidenceModule = { createNetworkRerunEvidenceModule };
})();
