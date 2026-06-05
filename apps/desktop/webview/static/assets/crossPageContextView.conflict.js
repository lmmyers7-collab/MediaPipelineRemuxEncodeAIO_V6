// crossPageContextView.conflict.js
// Split child of crossPageContextView.js — owns the cross-page conflict-detection
// engine and the conflict board render.  No mutation, no API calls.
//
// Loaded by index.html immediately BEFORE crossPageContextView.js so the parent
// IIFE can read window.__crossPageConflictModule, call the factory, then delete
// the stash.  After load, zero extra globals remain.
//
// All shared utilities (crossPageNormalizePath, crossPageLeaf, path accessors,
// DOM helpers) are injected by the parent factory call — this module never reads
// window.* for its own logic.

(function () {
  "use strict";

  function createCrossPageConflictModule({
    appendCells,
    byId,
    clearRows,
    crossPageCount,
    crossPageCompletedOutput,
    crossPageCompletedSource,
    crossPageLeaf,
    crossPageNormalizePath,
    crossPagePathLooksAbsolute,
    crossPagePendingDestination,
    crossPagePendingLocal,
    crossPagePendingSource,
    crossPageQueueRuntimeOutput,
    crossPageQueueSource,
    crossPageRowLabel,
    crossPageRows,
    makeRowSelectable,
    setText,
    updateTableStatusLegend,
  }) {

    // -------------------------------------------------------------------------
    // Pending-row conflict severity
    // -------------------------------------------------------------------------

    function crossPageConflictStatusForPending(row) {
      const severity = String(row?.diagnostic_severity || row?.operator_severity || "").toLowerCase();
      const status = String(row?.diagnostic_status || row?.state || row?.status || "").toLowerCase();
      const recommendation = String(row?.drain_recommendation || row?.operator_guidance || row?.issue_summary || "").toLowerCase();
      if (row?.do_not_drain || row?.error || severity === "error") return "blocked";
      if (["missing", "invalid", "blocked", "do not drain"].some((token) => status.includes(token) || recommendation.includes(token))) return "blocked";
      if (severity === "warning" || ["review", "warning", "orphan", "sidecar"].some((token) => status.includes(token) || recommendation.includes(token))) return "warning";
      return "warning";
    }

    // -------------------------------------------------------------------------
    // Path-index helpers (only used by crossPageConflictRows)
    // -------------------------------------------------------------------------

    function crossPageIndexAdd(map, key, record) {
      if (!key) return;
      if (!map.has(key)) map.set(key, []);
      map.get(key).push(record);
    }

    function crossPageBuildPathIndex(rows, kind, pathGetter, options = {}) {
      const exact = new Map();
      const leaf = new Map();
      (Array.isArray(rows) ? rows : []).forEach((row, index) => {
        const path = pathGetter(row);
        const normalized = crossPageNormalizePath(path);
        const pathLike = crossPagePathLooksAbsolute(path);
        const leafKey = crossPageLeaf(path).toLowerCase();
        const record = {
          kind,
          row,
          index,
          path,
          normalized,
          pathLike,
          label: crossPageRowLabel(row, kind),
        };
        if (pathLike && normalized) crossPageIndexAdd(exact, normalized, record);
        if (leafKey && (!options.leafRequiresPath || pathLike)) crossPageIndexAdd(leaf, leafKey, record);
      });
      return { exact, leaf };
    }

    // -------------------------------------------------------------------------
    // Conflict detection engine
    // -------------------------------------------------------------------------

    function crossPageConflictRows(context) {
      const queueRows = crossPageRows(context?.queue || {});
      const completedRows = crossPageRows(context?.completed || {});
      const pendingRows = crossPageRows(context?.pending || {});
      const queueSource = crossPageBuildPathIndex(queueRows, "queue", crossPageQueueSource);
      const queueRuntimeOutput = crossPageBuildPathIndex(queueRows, "queue", crossPageQueueRuntimeOutput, { leafRequiresPath: true });
      const completedSource = crossPageBuildPathIndex(completedRows, "completed", crossPageCompletedSource);
      const completedOutput = crossPageBuildPathIndex(completedRows, "completed", crossPageCompletedOutput);
      const pendingSource = crossPageBuildPathIndex(pendingRows, "pending", crossPagePendingSource);
      const pendingDestination = crossPageBuildPathIndex(pendingRows, "pending", crossPagePendingDestination);
      const pendingLocal = crossPageBuildPathIndex(pendingRows, "pending", crossPagePendingLocal);
      const conflicts = [];
      const seen = new Set();

      function addConflict(item) {
        const signature = [
          item.signal,
          item.left?.kind,
          item.left?.index,
          item.right?.kind,
          item.right?.index,
          item.path || "",
        ].join("|");
        if (seen.has(signature)) return;
        seen.add(signature);
        conflicts.push(item);
      }

      function exactPairs(leftIndex, rightIndex, signal, severity, action, pathLabel) {
        leftIndex.exact.forEach((leftRecords, key) => {
          const rightRecords = rightIndex.exact.get(key) || [];
          leftRecords.forEach((left) => {
            rightRecords.forEach((right) => {
              addConflict({
                signal,
                severity: typeof severity === "function" ? severity(right.row, left.row) : severity,
                confidence: "exact-path",
                left,
                right,
                path: left.path || right.path,
                evidence: `${pathLabel}: ${left.path || right.path}`,
                action,
                primary: left.kind === "queue" ? left : right,
              });
            });
          });
        });
      }

      function leafPairs(leftIndex, rightIndex, signal, action, pathLabel, limit = 80) {
        let added = 0;
        leftIndex.leaf.forEach((leftRecords, key) => {
          if (added >= limit) return;
          const rightRecords = rightIndex.leaf.get(key) || [];
          leftRecords.forEach((left) => {
            rightRecords.forEach((right) => {
              if (added >= limit) return;
              if (left.pathLike && right.pathLike && left.normalized && left.normalized === right.normalized) return;
              addConflict({
                signal,
                severity: "advisory",
                confidence: "same-leaf-review",
                left,
                right,
                path: left.path || right.path,
                evidence: `${pathLabel}: ${crossPageLeaf(left.path || right.path)}. Full paths differ or one side lacks a full path.`,
                action,
                primary: left.kind === "queue" ? left : right,
              });
              added += 1;
            });
          });
        });
      }

      exactPairs(
        queueSource,
        completedSource,
        "queued-source-completed-history",
        "warning",
        "Review Queue and Completed before Launch; this source appears in completed history.",
        "Exact queue source and completed source",
      );
      exactPairs(
        queueSource,
        pendingSource,
        "queued-source-pending-publish",
        (pendingRow) => crossPageConflictStatusForPending(pendingRow),
        "Review Pending Publish before Launch; the source has parked publish state.",
        "Exact queue source and pending source",
      );
      exactPairs(
        completedOutput,
        pendingDestination,
        "completed-output-pending-destination",
        (pendingRow) => crossPageConflictStatusForPending(pendingRow),
        "Review Completed and Pending Publish before retrying drain, rerun, cleanup, or deletion.",
        "Exact completed output and pending destination",
      );
      exactPairs(
        queueRuntimeOutput,
        pendingDestination,
        "queue-runtime-output-pending-destination",
        (pendingRow) => crossPageConflictStatusForPending(pendingRow),
        "Runtime output history overlaps pending destination; inspect Run Logs and Pending Publish before acting.",
        "Exact queue runtime output and pending destination",
      );
      leafPairs(
        queueSource,
        completedSource,
        "same-source-leaf-completed-history",
        "Filename-only match. Treat as duplicate-title review, not proof of the same file.",
        "Queue source and completed source leaf",
      );
      leafPairs(
        queueSource,
        pendingSource,
        "same-source-leaf-pending-publish",
        "Filename-only match. Compare folders before deciding whether the source is already parked.",
        "Queue source and pending source leaf",
      );
      leafPairs(
        completedOutput,
        pendingDestination,
        "same-output-leaf-pending-destination",
        "Filename-only output match. Compare full folders before treating it as publish proof.",
        "Completed output and pending destination leaf",
      );
      leafPairs(
        completedOutput,
        pendingLocal,
        "same-output-leaf-pending-local",
        "Filename-only payload match. Compare full folders and pending state before acting.",
        "Completed output and pending local payload leaf",
      );

      const severityWeight = { blocked: 0, warning: 1, advisory: 2 };
      return conflicts.sort((left, right) => (severityWeight[left.severity] ?? 3) - (severityWeight[right.severity] ?? 3));
    }

    // -------------------------------------------------------------------------
    // Conflict helpers
    // -------------------------------------------------------------------------

    function crossPageConflictSignalLabel(signal) {
      const labels = {
        "queued-source-completed-history": "Queued source in Completed",
        "queued-source-pending-publish": "Queued source in Pending",
        "completed-output-pending-destination": "Completed output in Pending",
        "queue-runtime-output-pending-destination": "Queue runtime output in Pending",
        "same-source-leaf-completed-history": "Same source filename in Completed",
        "same-source-leaf-pending-publish": "Same source filename in Pending",
        "same-output-leaf-pending-destination": "Same output filename in Pending",
        "same-output-leaf-pending-local": "Same payload filename in Pending",
      };
      return labels[signal] || signal || "Conflict review";
    }

    function crossPageConflictStatus(context) {
      const rows = crossPageConflictRows(context || {});
      if (!rows.length) return "No conflicts";
      if (rows.some((row) => row.severity === "blocked")) return "Blocked review";
      if (rows.some((row) => row.severity === "warning")) return "Review matches";
      return "Advisory matches";
    }

    function crossPageConflictSummary(context) {
      const rows = crossPageConflictRows(context || {});
      const blocked = rows.filter((row) => row.severity === "blocked").length;
      const warning = rows.filter((row) => row.severity === "warning").length;
      const advisory = rows.filter((row) => row.severity === "advisory").length;
      return `Cross-page conflict board: ${rows.length} row(s), blocked=${blocked}, warning=${warning}, advisory=${advisory}. Exact full paths are evidence; same-leaf rows are duplicate-title hints only.`;
    }

    function crossPageConflictScope(item) {
      return `${item.left?.kind || "left"}: ${item.left?.label || ""} | ${item.right?.kind || "right"}: ${item.right?.label || ""}`;
    }

    function crossPageSelectConflict(item) {
      const target = item?.primary;
      if (!target) return;
      if (target.kind === "queue" && typeof window.selectQueueRow === "function") {
        window.selectQueueRow(target.row);
        if (typeof window.showPage === "function") window.showPage("queue");
        return;
      }
      if (target.kind === "completed" && typeof window.selectCompletedRow === "function") {
        window.selectCompletedRow(target.row);
        if (typeof window.showPage === "function") window.showPage("completed");
        return;
      }
      if (target.kind === "pending" && typeof window.selectPendingRow === "function") {
        window.selectPendingRow(target.row);
        if (typeof window.showPage === "function") window.showPage("pending");
      }
    }

    // -------------------------------------------------------------------------
    // Conflict board render
    // -------------------------------------------------------------------------

    function renderCrossPageConflictBoard(context = {}) {
      const rows = crossPageConflictRows(context || {});
      setText("cross-page-conflict-status", crossPageConflictStatus(context || {}));
      const tbody = byId("cross-page-conflict-rows");
      if (!tbody) return;
      if (!rows.length) {
        clearRows(tbody, 4, "No cross-page conflicts in the loaded Queue, Completed, and Pending Publish payloads.");
        updateTableStatusLegend("cross-page-conflict-legend", tbody, "Cross-page conflict rows");
        return;
      }
      tbody.replaceChildren();
      rows.slice(0, 250).forEach((item) => {
        const row = document.createElement("tr");
        row.dataset.status = item.severity === "blocked" ? "blocked" : item.severity === "warning" ? "warning" : "changed";
        appendCells(row, [
          `${crossPageConflictSignalLabel(item.signal)} (${item.confidence})`,
          crossPageConflictScope(item),
          item.evidence || "",
          item.action || "Review owning pages before acting.",
        ]);
        makeRowSelectable(row, () => crossPageSelectConflict(item), {
          selected: false,
          label: `Review cross-page conflict ${crossPageConflictSignalLabel(item.signal)}`,
        });
        tbody.appendChild(row);
      });
      updateTableStatusLegend("cross-page-conflict-legend", tbody, "Cross-page conflict rows");
    }

    // -------------------------------------------------------------------------
    // Factory return
    // -------------------------------------------------------------------------

    return {
      crossPageConflictRows,
      crossPageConflictSignalLabel,
      crossPageConflictStatus,
      crossPageConflictSummary,
      crossPageConflictScope,
      crossPageSelectConflict,
      renderCrossPageConflictBoard,
    };
  }

  window.__crossPageConflictModule = { createCrossPageConflictModule };
})();
