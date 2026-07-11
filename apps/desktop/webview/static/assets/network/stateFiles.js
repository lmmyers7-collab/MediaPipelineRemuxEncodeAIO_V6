(function () {
  function createNetworkStateFilesModule(deps = {}) {
    const { byId, setText, clearRows, appendCells, makeRowSelectable, updateTableStatusLegend, networkStateFilesDiagnosticStatus, getSelectedKey, setSelectedKey } = deps;
      function networkStateFileRows(networkWorkers) {
        return Array.isArray(networkWorkers?.state_files) ? networkWorkers.state_files : [];
      }

      function networkStateFileStatus(item) {
        const status = String(item?.status || "").toLowerCase();
        if (status.includes("unreadable")) return "blocked";
        if (status.includes("missing")) return "warning";
        if (status.includes("present")) return "match";
        return "warning";
      }

      function networkStateFileStatusText(rows = []) {
        if (!rows.length) return "Not loaded";
        if (rows.some((item) => networkStateFileStatus(item) === "blocked")) return "Blocked review";
        if (rows.some((item) => networkStateFileStatus(item) === "warning")) return "Review";
        return "Ready";
      }

      function networkStateFileKey(item) {
        return String(item?.key || item?.label || item?.path || "").toLowerCase();
      }

      function networkStateFileAgeText(item) {
        if (!item || item.exists === false || String(item.status || "").toLowerCase() === "missing") return "-";
        const age = item.age_seconds;
        if (age === null || age === undefined || age === "") return "unknown age";
        const numeric = Number(age);
        if (!Number.isFinite(numeric)) return "unknown age";
        if (numeric < 60) return `${Math.max(0, Math.round(numeric))}s old`;
        if (numeric < 3600) return `${Math.round(numeric / 60)}m old`;
        if (numeric < 86400) return `${Math.round(numeric / 3600)}h old`;
        return `${Math.round(numeric / 86400)}d old`;
      }

      function networkStateFileCompactLines(rows = []) {
        const files = Array.isArray(rows) ? rows : [];
        if (!files.length) return ["State files: not loaded"];
        return [
          `State files: ${files.length}; present=${files.filter((item) => networkStateFileStatus(item) === "match").length}; missing=${files.filter((item) => networkStateFileStatus(item) === "warning").length}; unreadable=${files.filter((item) => networkStateFileStatus(item) === "blocked").length}`,
          ...files.slice(0, 4).map((item) => `${item.label || item.key || "state file"}: ${item.status || "unknown"}; age=${networkStateFileAgeText(item)}`),
        ];
      }

      function networkStateFileSummaryLines(rows = []) {
        const files = Array.isArray(rows) ? rows : [];
        const present = files.filter((item) => networkStateFileStatus(item) === "match").length;
        const missing = files.filter((item) => networkStateFileStatus(item) === "warning").length;
        const unreadable = files.filter((item) => networkStateFileStatus(item) === "blocked").length;
        const lines = [
          "Network runtime state file evidence:",
          `Status: ${networkStateFileStatusText(files)}`,
          `Files: ${files.length}; present=${present}; missing=${missing}; unreadable=${unreadable}.`,
          "Read order: Cluster log -> Coordinator in-flight registry -> Local worker state -> ActiveJobs / Run Logs when a row is active or failed.",
          "Mutation guardrail: this panel only reads backend-authored state-file metadata; it cannot open arbitrary paths or start/stop network work.",
        ];
        if (!files.length) {
          lines.push("No state-file metadata is loaded from the backend network worker payload.");
        } else {
          const review = files.filter((item) => networkStateFileStatus(item) !== "match");
          if (review.length) {
            lines.push("", "Rows needing attention:");
            review.forEach((item) => lines.push(`- ${item.label || item.key || "state file"}: ${item.status || "unknown"}; ${item.path || "path not resolved"}`));
          } else {
            lines.push("", "All expected network runtime state files are present in the loaded payload.");
          }
        }
        return lines;
      }

      function getSelectedNetworkStateFileRow(rows) {
        const selectedKey = getSelectedKey();
        if (!selectedKey) return null;
        return (Array.isArray(rows) ? rows : []).find((item) => networkStateFileKey(item) === selectedKey) || null;
      }

      function networkStateFileDetailLines(item) {
        if (!item) {
          return [
            "No network runtime state file selected.",
            "Select a state file row to inspect backend-resolved path, status, size, age, and safe read order.",
            "This detail is read-only metadata from /api/network/workers; Diagnostics remains responsible for backend-allowlisted opens and tails.",
          ];
        }
        const lines = [
          `File: ${item.label || item.key || "state file"}`,
          `Key: ${item.key || "(none)"}`,
          `Status: ${item.status || "unknown"}`,
          `Exists: ${item.exists === true ? "yes" : "no"}`,
          `Path: ${item.path || "not resolved"}`,
          `Size: ${item.size_bytes === undefined || item.size_bytes === null ? "-" : item.size_bytes} bytes`,
          `Modified: ${item.modified_at || "-"}`,
          `Age: ${networkStateFileAgeText(item)}`,
          `Purpose: ${item.purpose || "No purpose loaded."}`,
        ];
        if (item.error) lines.push(`Error: ${item.error}`);
        lines.push(
          "",
          "Safe next step: use Diagnostics allowlisted open/tail controls for cluster.log, ActiveJobs, Run Logs, or State before changing role, retrying worker claims, or trusting pending done reports.",
          "Mutation guardrail: this panel cannot start/stop coordinator or workers, reclaim jobs, rewrite state, save settings, or touch media files."
        );
        return lines;
      }

      function renderNetworkStateFileDetail(item) {
        setText("network-state-files-detail", networkStateFileDetailLines(item).join("\n"));
      }

      function renderNetworkStateFiles(networkWorkers) {
        const rows = networkStateFileRows(networkWorkers);
        setText("network-state-files-status", networkStateFileStatusText(rows));
        setText("network-state-files-summary", networkStateFileSummaryLines(rows).join("\n"));
        const tbody = byId("network-state-files-rows");
        if (!tbody) return;
        if (!rows.length) {
          setSelectedKey("");
          clearRows(tbody, 4, "No network runtime state file evidence loaded.");
          updateTableStatusLegend("network-state-files-legend", tbody, "Network runtime state file rows");
          renderNetworkStateFileDetail(null);
          return;
        }
        if (!rows.some((item) => networkStateFileKey(item) === getSelectedKey())) {
          setSelectedKey(networkStateFileKey(rows[0]));
        }
        tbody.replaceChildren();
        rows.forEach((item) => {
          const row = document.createElement("tr");
          const key = networkStateFileKey(item);
          row.dataset.rowKey = key;
          row.dataset.status = networkStateFileStatus(item);
          row.title = item.path || "";
          appendCells(row, [
            item.label || item.key || "",
            item.status || "",
            networkStateFileAgeText(item),
            item.purpose || "",
          ], [null, null, "num", null]);
          makeRowSelectable(row, () => {
            setSelectedKey(key);
            renderNetworkStateFiles(networkWorkers);
          }, {
            selected: Boolean(key && key === getSelectedKey()),
            label: `Network runtime state file ${item.label || item.key || ""}`,
          });
          tbody.appendChild(row);
        });
        updateTableStatusLegend("network-state-files-legend", tbody, "Network runtime state file rows");
        renderNetworkStateFileDetail(getSelectedNetworkStateFileRow(rows));
      }

    return {
      networkStateFileCompactLines,
      networkStateFileDetailLines,
      networkStateFileRows,
      networkStateFileStatus,
      networkStateFileSummaryLines,
      renderNetworkStateFiles,
    };
  }
  window.__networkStateFilesModule = { createNetworkStateFilesModule };
})();
