(function () {
  function createDiagnosticsTriageModule(deps = {}) {
    const {
      appendDiagnosticsActionGroup,
      byId,
      diagnosticsActionGroups,
      diagnosticsActionPlanLines,
      diagnosticsArtifactTargets,
      diagnosticsArtifactsForLine,
      diagnosticsLongRunReliabilityLines,
      diagnosticsMalformedStateLines,
      diagnosticsSeverityForLine,
      diagnosticsTextLines,
      compactedDiagnosticsTextLines,
      requestDiagnosticsOpen,
      requestDiagnosticsTail,
      setDiagnosticsPanelStatus,
      setText,
    } = deps;
  function diagnosticsSourceLines(diagnostics) {
    const groups = [
      ["Recent errors", diagnostics?.recent_errors],
      ["Recent events", diagnostics?.recent_events],
      ["ActiveJobs", diagnostics?.active_jobs],
      ["Warnings", diagnostics?.warnings],
      ["Pipeline log tail", diagnostics?.log_tail],
      ["Launch logs", diagnostics?.launch_logs],
    ];
    const entries = [];
    groups.forEach(([source, value]) => {
      const sourceLines = source === "Pipeline log tail" ? compactedDiagnosticsTextLines(value) : diagnosticsTextLines(value);
      sourceLines.slice(-50).forEach((line) => {
        entries.push({ source, line });
      });
    });
    return entries;
  }

  function diagnosticsArtifactMatches(diagnostics) {
    const entries = diagnosticsSourceLines(diagnostics || {});
    return diagnosticsArtifactTargets
      .map((artifact) => {
        const samples = [];
        let count = 0;
        entries.forEach((entry) => {
          if (!artifact.patterns.some((pattern) => pattern.test(entry.line))) return;
          count += 1;
          if (samples.length < 3) {
            samples.push(`${entry.source}: ${entry.line}`);
          }
        });
        return {
          ...artifact,
          count,
          samples,
        };
      })
      .filter((artifact) => artifact.count > 0)
      .sort((left, right) => right.count - left.count || left.name.localeCompare(right.name));
  }

  function renderDiagnosticsDrilldownActions(matches) {
    const actions = byId("diagnostics-drilldown-actions");
    if (!actions) return;
    actions.replaceChildren();
    matches.slice(0, 6).forEach((artifact) => {
      const openTarget = String(artifact.target || "").trim();
      if (openTarget) {
        const button = document.createElement("button");
        button.className = "secondary-button";
        button.type = "button";
        button.dataset.openDiagnostics = openTarget;
        button.textContent = `Open ${artifact.name}`;
        button.addEventListener("click", () => requestDiagnosticsOpen(openTarget, button));
        actions.appendChild(button);
      }
      if (artifact.tailTarget) {
        const tailButton = document.createElement("button");
        tailButton.className = "secondary-button";
        tailButton.type = "button";
        tailButton.dataset.readDiagnosticsTail = artifact.tailTarget;
        tailButton.textContent = `Read ${artifact.tailName || artifact.name}`;
        tailButton.addEventListener("click", () => requestDiagnosticsTail(artifact.tailTarget, tailButton));
        actions.appendChild(tailButton);
      }
    });
  }

  function renderDiagnosticsDrilldown(diagnostics) {
    const matches = diagnosticsArtifactMatches(diagnostics || {});
    renderDiagnosticsDrilldownActions(matches);
    const status = matches.length ? `${matches.length} artifact hint(s)` : "No artifacts";
    setDiagnosticsPanelStatus("diagnostics-drilldown-status", status, matches.length ? "warning" : "empty");
    const lines = [
      "Artifact drilldown is read-only. Open and Read buttons below use backend allowlists; the frontend never sends arbitrary paths.",
    ];
    if (!matches.length) {
      lines.push("No artifact-specific clues were found in the current diagnostics payload.");
      lines.push("Close Readiness remains the first stop before clearing state, closing the app, or deleting runtime files.");
      setText("diagnostics-drilldown-summary", lines.join("\n"));
      return;
    }
    matches.forEach((artifact) => {
      const openTarget = artifact.target || "none; use row guidance";
      lines.push("", `${artifact.name} (${artifact.count} clue${artifact.count === 1 ? "" : "s"}; open target: ${openTarget})`);
      lines.push(`Next step: ${artifact.hint}`);
      artifact.samples.forEach((sample) => lines.push(`- ${sample}`));
    });
    lines.push("", "Close Readiness remains the first stop before clearing state, closing the app, or deleting runtime files.");
    setText("diagnostics-drilldown-summary", lines.join("\n"));
  }

  function renderDiagnosticsTriage(diagnostics) {
    const recentErrors = diagnosticsTextLines(diagnostics?.recent_errors);
    const recentEvents = diagnosticsTextLines(diagnostics?.recent_events);
    const activeJobs = diagnosticsTextLines(diagnostics?.active_jobs);
    const warnings = diagnosticsTextLines(diagnostics?.warnings);
    const logLines = diagnosticsTextLines(diagnostics?.log_tail).slice(-20);
    const launchLines = diagnosticsTextLines(diagnostics?.launch_logs).slice(-20);
    const allLines = [
      ...recentErrors,
      ...recentEvents,
      ...activeJobs,
      ...warnings,
      ...logLines,
      ...launchLines,
    ];
    const counts = allLines.reduce((acc, line) => {
      const severity = diagnosticsSeverityForLine(line);
      acc[severity] = (acc[severity] || 0) + 1;
      return acc;
    }, {});
    const autonomyHealth = diagnostics?.autonomy_health && typeof diagnostics.autonomy_health === "object" ? diagnostics.autonomy_health : {};
    const longRunLines = diagnosticsLongRunReliabilityLines(autonomyHealth);
    const longRunStatus = String(autonomyHealth.overall_status || "").toLowerCase();
    const longRunBlocked = longRunStatus === "blocked" || Number(autonomyHealth.blocked_count || 0) > 0;
    const longRunReview = longRunStatus === "review" || Number(autonomyHealth.review_count || 0) > 0;
    const malformedLines = diagnosticsMalformedStateLines(allLines).slice(0, 8);
    const status = longRunBlocked
      ? "Blocked"
      : counts.error
      ? "Errors"
      : (counts.warning || longRunReview)
        ? "Warnings"
        : counts.active
          ? "Active"
          : allLines.length
            ? "Informational"
            : "No issues";
    setDiagnosticsPanelStatus(
      "diagnostics-triage-status",
      status,
      longRunBlocked || counts.error ? "blocked" : counts.warning || longRunReview ? "warning" : counts.active ? "running" : allLines.length || longRunLines.length ? "ready" : "empty",
    );
    const freshnessLines = window.mediaPipelineDom?.payloadFreshnessLines
      ? window.mediaPipelineDom.payloadFreshnessLines({
        payload: diagnostics,
        label: "Diagnostics",
        rowCount: allLines.length,
        artifactLine: `Readable lines: errors ${recentErrors.length}; events ${recentEvents.length}; ActiveJobs ${activeJobs.length}; warnings ${warnings.length}.`,
        refreshAction: "Use Refresh Diagnostics or topbar Refresh. This re-reads logs/state only and does not repair, clear, delete, rerun, publish, or move files.",
      })
      : [];
    const lines = [
      ...freshnessLines,
      `Recent errors: ${recentErrors.length}`,
      `Recent events: ${recentEvents.length}`,
      `ActiveJobs lines: ${activeJobs.length}`,
      `Warnings: ${warnings.length}`,
      `Severity groups: error ${counts.error || 0}; warning ${counts.warning || 0}; active ${counts.active || 0}; info ${counts.info || 0}`,
    ];
    if (longRunLines.length) {
      lines.push("", "Long-run reliability evidence:");
      longRunLines.forEach((line) => lines.push(`- ${line}`));
    }
    if (malformedLines.length) {
      lines.push("", "Malformed/stale runtime-state hint(s):");
      malformedLines.forEach((line) => lines.push(`- ${line}`));
      lines.push("Next step: Check Diagnostics > Overview > Shutdown Readiness first. If it is blocked, inspect Active Jobs, progress files, Run Logs, and State Folder before closing or clearing runtime files.");
    } else if (counts.error) {
      lines.push("", "Next step: Open Run Logs and Last Stderr, then review the newest failure/audit report if one exists.");
    } else if (counts.warning) {
      lines.push("", "Next step: Review warnings and refresh once; if the same warning persists, open the relevant state/log location below.");
    } else if (counts.active) {
      lines.push("", "Next step: Active work appears to be present. Use Diagnostics > Overview > Shutdown Readiness and Active Jobs before exiting.");
    } else {
      lines.push("", "Next step: No diagnostics issues are currently visible from the backend snapshot.");
    }
    setText("diagnostics-triage-summary", lines.join("\n"));
  }

  function diagnosticsFormatCounts(value) {
    const entries = value && typeof value === "object" ? Object.entries(value) : [];
    if (!entries.length) return "none";
    return entries
      .sort(([left], [right]) => String(left).localeCompare(String(right)))
      .map(([key, count]) => `${key || "unknown"}=${count}`)
      .join(", ");
  }

  function diagnosticsSafeRows(payload) {
    return Array.isArray(payload?.rows) ? payload.rows : [];
  }

  function diagnosticsFirstResponseAdd(rows, key, step, posture, evidence, action) {
    rows.push({ key, step, posture, evidence, action });
  }


    return {
      diagnosticsSourceLines,
      diagnosticsArtifactMatches,
      renderDiagnosticsDrilldownActions,
      renderDiagnosticsDrilldown,
      renderDiagnosticsTriage,
      diagnosticsFormatCounts,
      diagnosticsSafeRows,
      diagnosticsFirstResponseAdd,    };
  }

  window.__diagnosticsTriageModule = {
    createDiagnosticsTriageModule,
  };
})();
