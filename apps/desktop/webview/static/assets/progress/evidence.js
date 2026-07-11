(function () {
  function createProgressEvidenceModule(deps) {
    deps = deps || {};
    const progressEvidenceRows = deps.progressEvidenceRows || (() => []);
    const progressEvidencePostureStatus = deps.progressEvidencePostureStatus || (() => "unknown");
    const getSelectedKey = deps.getSelectedKey || (() => "");
    const setSelectedKey = deps.setSelectedKey || (() => {});
    const setProgressPanelStatus = deps.setProgressPanelStatus || (() => {});
    const setText = deps.setText || (() => {});
    const byId = deps.byId || (() => null);
    const clearRows = deps.clearRows || (() => {});
    const updateTableStatusLegend = deps.updateTableStatusLegend || (() => {});
    const appendCells = deps.appendCells || (() => {});
    const makeRowSelectable = deps.makeRowSelectable || (() => {});

    function progressEvidenceStatus(rows = []) {
      if (!rows.length) return "No evidence";
      if (rows.some((row) => progressEvidencePostureStatus(row.posture) === "blocked")) return "Active/review";
      if (rows.some((row) => progressEvidencePostureStatus(row.posture) === "warning")) return "Review";
      return "Ready";
    }

    function progressEvidenceSummaryLines(rows = []) {
      const counts = rows.reduce((acc, row) => {
        const key = progressEvidencePostureStatus(row.posture);
        acc[key] = (acc[key] || 0) + 1;
        return acc;
      }, {});
      const reviewRows = rows.filter((row) => progressEvidencePostureStatus(row.posture) !== "match");
      const lines = [
        "Progress evidence board:",
        `Status: ${progressEvidenceStatus(rows)}`,
        `Rows: ${rows.length}; blocked=${counts.blocked || 0}; review=${counts.warning || 0}; ready=${counts.match || 0}.`,
      ];
      if (reviewRows.length) {
        lines.push("", "Rows needing attention:");
        reviewRows.slice(0, 6).forEach((row) => lines.push(`- ${row.checkpoint}: ${row.posture}; ${row.action}`));
      } else {
        lines.push("", "No local progress-evidence review rows are active.");
      }
      lines.push("", "Mutation guardrail: this board is read-only and does not control processes or touch media files.");
      return lines;
    }

    function selectedProgressEvidenceRow(rows) {
      const selectedKey = getSelectedKey();
      if (!selectedKey) return null;
      return rows.find((row) => row.key === selectedKey) || null;
    }

    function progressEvidenceDetailLines(row) {
      if (!row) {
        return [
          "No progress evidence row selected.",
          "Select a row to inspect progress, close-readiness, ActiveJobs, events, audit progress, or proof-boundary context.",
          "Mutation guardrail: this detail view is read-only and cannot control processes or touch media files.",
        ];
      }
      const lines = [
        `Checkpoint: ${row.checkpoint}`,
        `Posture: ${row.posture}`,
        `Evidence: ${row.evidence}`,
        `Safe next step: ${row.action}`,
      ];
      if (Array.isArray(row.detail) && row.detail.length) {
        lines.push("", "Detail:");
        row.detail.forEach((line) => lines.push(`- ${line}`));
      }
      lines.push("", "Mutation guardrail: progress evidence is read-only; backend process controls and diagnostics allowlists remain authoritative.");
      return lines;
    }

    function renderProgressEvidence(context = {}) {
      const rows = progressEvidenceRows(context || {});
      const status = progressEvidenceStatus(rows);
      setProgressPanelStatus("progress-evidence-status", status, status.includes("Blocked") ? "blocked" : status.includes("Review") ? "warning" : rows.length ? "ready" : "empty");
      setText("progress-evidence-summary", progressEvidenceSummaryLines(rows).join("\n"));
      const tbody = byId("progress-evidence-rows");
      if (!tbody) return;
      if (getSelectedKey() && !rows.some((row) => row.key === getSelectedKey())) setSelectedKey("");
      if (!rows.length) {
        clearRows(tbody, 4, "No progress evidence rows loaded.");
        updateTableStatusLegend("progress-evidence-legend", tbody, "Progress evidence rows");
        setText("progress-evidence-detail", progressEvidenceDetailLines(null).join("\n"));
        return;
      }
      tbody.replaceChildren();
      rows.forEach((item) => {
        const row = document.createElement("tr");
        row.dataset.status = progressEvidencePostureStatus(item.posture);
        appendCells(row, [item.checkpoint, item.posture, item.evidence, item.action]);
        makeRowSelectable(row, () => {
          setSelectedKey(item.key);
          renderProgressEvidence(context);
        }, {
          selected: getSelectedKey() === item.key,
          label: `Progress evidence ${item.checkpoint} ${item.posture}`,
        });
        tbody.appendChild(row);
      });
      updateTableStatusLegend("progress-evidence-legend", tbody, "Progress evidence rows");
      setText("progress-evidence-detail", progressEvidenceDetailLines(selectedProgressEvidenceRow(rows)).join("\n"));
    }

    return { progressEvidenceStatus, progressEvidenceSummaryLines, selectedProgressEvidenceRow, progressEvidenceDetailLines, renderProgressEvidence };
  }

  window.__progressEvidenceModule = { createProgressEvidenceModule };
}());
