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

      function networkRerunEvidenceLines(row = {}) {
        const reducer = row.network_reducer_result && typeof row.network_reducer_result === "object" ? row.network_reducer_result : {};
        const worker = row.network_worker_result && typeof row.network_worker_result === "object" ? row.network_worker_result : {};
        const destination = networkRerunDestinationResult(row);
        return [
          reducer.classification ? `Reducer: ${reducer.classification}` : "",
          reducer.accepted === true ? "Reducer accepted" : reducer.accepted === false ? "Reducer rejected" : "",
          worker.worker_id || worker.worker_name ? `Worker: ${worker.worker_id || worker.worker_name}` : "",
          destination.status || destination.action ? `Destination: ${[destination.status, destination.action].filter(Boolean).join(" / ")}` : "",
          destination.pending_publish_manifest_path || row.pending_publish_manifest_path ? `Pending: ${networkRerunLeaf(destination.pending_publish_manifest_path || row.pending_publish_manifest_path)}` : "",
          destination.published_path || row.published_path ? `Published: ${networkRerunLeaf(destination.published_path || row.published_path)}` : "",
          row.claim_status ? `Claim: ${row.claim_status}` : "",
        ].filter(Boolean);
      }

      function renderNetworkRerunRows(rerunResults = {}) {
        const tbody = byId("network-rerun-rows");
        if (!tbody) return;
        const rows = networkRerunRows(rerunResults);
        setText("network-rerun-status", rows.length ? `${rows.length} row${rows.length === 1 ? "" : "s"}` : "No rows");
        const counts = rerunResults?.queue_state?.status_counts && typeof rerunResults.queue_state.status_counts === "object"
          ? rerunResults.queue_state.status_counts
          : {};
        const countText = Object.keys(counts).sort().map((key) => `${key} ${counts[key]}`).join("; ");
        setText("network-rerun-summary", [
          "Network CSV rerun read model: backend-owned /api/rerun/results.",
          `Batches: ${Array.isArray(rerunResults.network_manifests) ? rerunResults.network_manifests.length : 0}; rows: ${rows.length}.`,
          countText ? `Queue-state counts: ${countText}.` : "No Network CSV rerun status counts loaded.",
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
