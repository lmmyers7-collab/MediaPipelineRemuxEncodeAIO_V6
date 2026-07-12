(function () {
  function createMaintenanceChangeLedger(deps) {
    const {
      state,
      setMaintenanceStatusText,
      maintenanceTableRowStatus,
    } = deps;
  function changeLedgerRows() {
    return Array.isArray(state.lastChangeLedger?.rows) ? state.lastChangeLedger.rows : [];
  }

  function changeLedgerRowKey(item) {
    return String(item?.row_key || item?.id || "").trim();
  }

  function getSelectedChangeLedgerRow() {
    const rows = changeLedgerRows();
    return rows.find((item) => changeLedgerRowKey(item) === state.selectedChangeLedgerRowKey) || null;
  }


  function changeLedgerCounts(ledger) {
    return ledger?.counts && typeof ledger.counts === "object" ? ledger.counts : {};
  }

  function changeLedgerSummaryLines(ledger) {
    const payload = ledger || {};
    const counts = changeLedgerCounts(payload);
    const coverage = changeLedgerCoverage(payload);
    const lines = Array.isArray(payload.summary_lines) && payload.summary_lines.length
      ? payload.summary_lines.map((line) => String(line || ""))
      : [
        `Change ledger: ${counts.total || 0} packet(s)`,
        `Unreleased: ${counts.unreleased || 0}; released: ${counts.released || 0}`,
        `Open: ${(counts.planned || 0) + (counts.in_progress || 0)}; complete: ${counts.complete || 0}`,
        `High/critical risk: ${counts.high_or_critical_risk || 0}`,
      ];
    const impact = payload.python_impact && typeof payload.python_impact === "object" ? payload.python_impact : {};
    lines.push(
      "",
      `Coverage: ${coverage.uncovered_count || 0} unrecorded changed file(s) in ${coverage.scope || "worktree"} scope.`,
      "",
      `Affected Python scripts: ${impact.summary || "No Python impact loaded."}`,
      "",
      "Source boundary:",
      "- Root CHANGELOG.md remains the canonical human changelog.",
      "- Structured change packets under ops/release/changes/unreleased/ and ops/release/changes/released/ feed this Maintenance ledger and generated change-control docs.",
      "- This panel is read-only; agents update packet/changelog files during development, not from the WebView."
    );
    return lines;
  }

  function changeLedgerCoverage(ledger) {
    return ledger?.coverage && typeof ledger.coverage === "object" ? ledger.coverage : {};
  }

  function changeLedgerUnrecordedPaths(ledger) {
    const coverage = changeLedgerCoverage(ledger || {});
    const hygiene = ledger?.hygiene && typeof ledger.hygiene === "object" ? ledger.hygiene : {};
    if (Array.isArray(coverage.uncovered_paths)) return coverage.uncovered_paths;
    if (Array.isArray(hygiene.unrecorded_changes)) return hygiene.unrecorded_changes;
    if (Array.isArray(hygiene.unlogged_changes)) return hygiene.unlogged_changes;
    return [];
  }

  function renderChangeLedgerSummary(ledger) {
    const payload = ledger || {};
    const counts = changeLedgerCounts(payload);
    const hygiene = payload.hygiene && typeof payload.hygiene === "object" ? payload.hygiene : {};
    const coverage = changeLedgerCoverage(payload);
    const status = Number(coverage.uncovered_count || 0) > 0
      ? `Coverage review (${coverage.uncovered_count})`
      : hygiene.operator_status
      ? `${hygiene.operator_status} (${counts.total || 0})`
      : payload.schema_version ? `Loaded (${counts.total || 0})` : "Not loaded";
    setMaintenanceStatusText("maintenance-change-ledger-status", status);
    setText("maintenance-change-ledger-summary", changeLedgerSummaryLines(payload).join("\n"));
  }

  function changeLedgerHygieneStatus(hygiene) {
    const status = String(hygiene?.operator_status || "").trim();
    if (!status) return "Not loaded";
    return status.charAt(0).toUpperCase() + status.slice(1);
  }

  function changeLedgerHygieneLines(ledger) {
    const payload = ledger || {};
    const hygiene = payload.hygiene && typeof payload.hygiene === "object" ? payload.hygiene : {};
    const coverage = changeLedgerCoverage(payload);
    const unrecorded = changeLedgerUnrecordedPaths(payload);
    const lines = Array.isArray(hygiene.summary_lines) && hygiene.summary_lines.length
      ? hygiene.summary_lines.map((line) => String(line || ""))
      : [
        `Unrecorded changed files: ${coverage.uncovered_count || hygiene.unrecorded_change_count || hygiene.unlogged_change_count || 0}`,
        `Change ledger hygiene: ${hygiene.operator_status || "not loaded"}`,
        `Issues: ${hygiene.issue_count || 0}`,
      ];
    if (unrecorded.length) {
      lines.push("", "Unrecorded changed files:");
      unrecorded.slice(0, 25).forEach((path) => lines.push(`- ${path}`));
      if (unrecorded.length > 25) lines.push(`- ${unrecorded.length - 25} more file(s).`);
    }
    const sourcePaths = Array.isArray(payload.source_paths) ? payload.source_paths : [];
    if (sourcePaths.length) {
      lines.push("", "Canonical/generator source paths:");
      sourcePaths.forEach((item) => {
        lines.push(`- ${item.path || ""}: ${item.exists ? "present" : "missing"}${item.stale ? "; stale" : ""}`);
      });
    }
    const issues = Array.isArray(hygiene.issues) ? hygiene.issues : [];
    if (issues.length) {
      lines.push("", "Hygiene issues:");
      issues.slice(0, 12).forEach((issue) => {
        lines.push(`- ${issue.severity || "warning"} ${issue.source_path || ""}: ${issue.message || ""}`);
      });
      if (issues.length > 12) lines.push(`- ${issues.length - 12} more issue(s).`);
    } else {
      lines.push("", "No changelog hygiene issues reported.");
    }
    lines.push("", "Mutation guardrail: this panel never writes packets, regenerates changelogs, edits AGENTS.md, runs tests, or touches media.");
    return lines;
  }

  function renderChangeLedgerHygiene(ledger) {
    const hygiene = ledger?.hygiene && typeof ledger.hygiene === "object" ? ledger.hygiene : {};
    setMaintenanceStatusText("maintenance-change-ledger-hygiene-status", changeLedgerHygieneStatus(hygiene));
    setText("maintenance-change-ledger-hygiene", changeLedgerHygieneLines(ledger || {}).join("\n"));
  }

  function changeLedgerFilterValue(id) {
    return String(byId(id)?.value || "").trim().toLowerCase();
  }

  function changeLedgerSearchText(row) {
    return [
      row?.id,
      row?.title,
      row?.status,
      row?.type,
      row?.risk_level,
      row?.summary,
      row?.reason,
      ...(Array.isArray(row?.affected_areas) ? row.affected_areas : []),
      ...(Array.isArray(row?.files_touched) ? row.files_touched : []),
      row?.python_impact?.summary,
    ].map((item) => String(item || "").toLowerCase()).join(" ");
  }

  function filteredChangeLedgerRows() {
    const status = changeLedgerFilterValue("maintenance-change-ledger-status-filter");
    const type = changeLedgerFilterValue("maintenance-change-ledger-type-filter");
    const risk = changeLedgerFilterValue("maintenance-change-ledger-risk-filter");
    const search = changeLedgerFilterValue("maintenance-change-ledger-search");
    return changeLedgerRows().filter((row) => {
      if (status && String(row?.status || "").toLowerCase() !== status) return false;
      if (type && String(row?.type || "").toLowerCase() !== type) return false;
      if (risk && String(row?.risk_level || "").toLowerCase() !== risk) return false;
      if (search && !changeLedgerSearchText(row).includes(search)) return false;
      return true;
    });
  }

  function changeLedgerTableStatus(rows) {
    const all = changeLedgerRows();
    if (!state.lastChangeLedger) return "Not loaded";
    if (!all.length) return "No packets";
    if (rows.length !== all.length) return `${rows.length}/${all.length} shown`;
    return `${all.length} packet${all.length === 1 ? "" : "s"}`;
  }

  function selectChangeLedgerRow(item) {
    state.selectedChangeLedgerRowKey = changeLedgerRowKey(item);
    renderChangeLedgerDetail(item || null);
    renderChangeLedgerRows();
  }

  function renderChangeLedgerRows() {
    const tbody = byId("maintenance-change-ledger-rows");
    if (!tbody) return;
    const rows = filteredChangeLedgerRows();
    const selectedVisible = rows.some((item) => changeLedgerRowKey(item) === state.selectedChangeLedgerRowKey);
    if (!selectedVisible) {
      state.selectedChangeLedgerRowKey = rows.length ? changeLedgerRowKey(rows[0]) : "";
    }
    setMaintenanceStatusText("maintenance-change-ledger-table-status", changeLedgerTableStatus(rows), rows.length ? "ok" : "empty");
    if (!rows.length) {
      clearRows(tbody, 6, state.lastChangeLedger ? "No change packets match the current filters." : "No change ledger loaded.");
      updateTableStatusLegend("maintenance-change-ledger-table-legend", tbody, "Change ledger rows");
      renderChangeLedgerDetail(null);
      return;
    }
    tbody.replaceChildren();
    rows.forEach((item) => {
      const row = document.createElement("tr");
      const risk = String(item?.risk_level || "").toLowerCase();
      const validation = String(item?.validation_status || "").toLowerCase();
      row.dataset.status = validation === "invalid" || risk === "critical" ? "blocked" : validation === "incomplete" || risk === "high" ? "warning" : "match";
      appendCells(row, [
        item.id || "",
        item.status || "",
        item.type || "",
        item.risk_level || "",
        item.title || "",
        item.python_impact?.file_count ? `${item.python_impact.file_count} file(s)` : "none",
      ]);
      makeRowSelectable(row, () => selectChangeLedgerRow(item), {
        selected: Boolean(changeLedgerRowKey(item) && changeLedgerRowKey(item) === state.selectedChangeLedgerRowKey),
        label: `Change ledger entry ${item.id || item.title || ""}`,
      });
      tbody.appendChild(row);
    });
    updateTableStatusLegend("maintenance-change-ledger-table-legend", tbody, "Change ledger rows");
    renderChangeLedgerDetail(getSelectedChangeLedgerRow());
  }

  function changeLedgerDetailLines(item) {
    if (!item) {
      return [
        "No change selected.",
        "Select a ledger row to inspect the issue/feature summary, affected Python scripts, validation evidence, rollback plan, and notes.",
        "Guardrail: row selection is local/read-only and does not edit changelog packets or generated docs.",
      ];
    }
    const impact = item.python_impact && typeof item.python_impact === "object" ? item.python_impact : {};
    const groups = Array.isArray(impact.groups) ? impact.groups : [];
    const lines = [
      `Change: ${item.id || ""} - ${item.title || ""}`,
      `Status: ${item.status || ""}`,
      `Type: ${item.type || ""}`,
      `Risk: ${item.risk_level || ""}`,
      `Version target: ${item.version_target || ""}`,
      `Location: ${item.location || ""}${item.release_version ? ` (${item.release_version})` : ""}`,
      `Validation status: ${item.validation_status || ""}`,
      `Source packet: ${item.source_path || ""}`,
      "",
      `Summary: ${item.summary || ""}`,
      `Reason: ${item.reason || ""}`,
      "",
      `Affected areas: ${(item.affected_areas || []).join(", ") || "none listed"}`,
      `Affected Python scripts: ${impact.summary || "No Python scripts touched."}`,
    ];
    if (groups.length) {
      lines.push("Python groups:");
      groups.forEach((group) => {
        lines.push(`- ${group.summary || group.group || ""}`);
        (group.files || []).slice(0, 8).forEach((path) => lines.push(`  ${path}`));
      });
    }
    lines.push(
      "",
      `Behavior before: ${item.behavior_before || ""}`,
      `Behavior after: ${item.behavior_after || ""}`,
      "",
      "Files touched:",
      ...((item.files_touched || []).length ? item.files_touched.slice(0, 18).map((path) => `- ${path}`) : ["- none listed"])
    );
    if ((item.files_touched || []).length > 18) lines.push(`- ${(item.files_touched || []).length - 18} more file(s).`);
    lines.push(
      "",
      "Tests/manual validation:",
      ...((item.manual_validation || []).length ? item.manual_validation.map((line) => `- ${line}`) : ["- none listed"]),
      "",
      `Rollback plan: ${item.rollback_plan || ""}`,
      `Related changes: ${(item.related_changes || []).join(", ") || "none"}`,
      `Notes: ${item.notes || ""}`,
      "",
      "Mutation guardrail: Maintenance displays this packet only. Agents must update change packets and generated changelog outputs in the repository during implementation."
    );
    return lines;
  }

  function renderChangeLedgerDetail(item) {
    setMaintenanceStatusText("maintenance-change-ledger-detail-status", item ? (item.validation_status || item.status || "selected") : "No selection");
    setText("maintenance-change-ledger-detail", changeLedgerDetailLines(item || null).join("\n"));
  }

  function renderChangeLedger(ledger) {
    state.lastChangeLedger = ledger || {};
    const rows = changeLedgerRows();
    if (!rows.some((item) => changeLedgerRowKey(item) === state.selectedChangeLedgerRowKey)) {
      state.selectedChangeLedgerRowKey = rows.length ? changeLedgerRowKey(rows[0]) : "";
    }
    renderChangeLedgerSummary(state.lastChangeLedger);
    renderChangeLedgerRows();
    renderChangeLedgerDetail(getSelectedChangeLedgerRow());
    renderChangeLedgerHygiene(state.lastChangeLedger);
  }

    return {
      changeLedgerRows,
      changeLedgerRowKey,
      getSelectedChangeLedgerRow,
      changeLedgerSummaryLines,
      changeLedgerCoverage,
      changeLedgerUnrecordedPaths,
      changeLedgerHygieneLines,
      renderChangeLedgerSummary,
      renderChangeLedgerHygiene,
      filteredChangeLedgerRows,
      renderChangeLedgerRows,
      changeLedgerDetailLines,
      renderChangeLedgerDetail,
      renderChangeLedger,
    };
  }

  window.__maintenanceChangeLedgerModule = { createMaintenanceChangeLedger };
})();
