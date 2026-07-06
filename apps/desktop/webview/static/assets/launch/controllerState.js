(function () {
  function createLaunchControllerStateModule(deps = {}) {
    const {
      state = { lastLaunchCommandState: { snapshot: null, closeReadiness: null } },
      getCommandHistory = function () { return []; },
    } = deps;

  function launchPipelineIsActive(snapshot = state.lastLaunchCommandState.snapshot, closeReadiness = state.lastLaunchCommandState.closeReadiness) {
    if (closeReadiness?.safe_to_close === false || closeReadiness?.active_work === true) return true;
    const state = String(snapshot?.pipeline_state || closeReadiness?.state || "").trim().toLowerCase();
    return ["processing", "running", "active", "publishing", "audit", "rerun", "stopping", "paused"].includes(state);
  }

  function activeJobRows(snapshot = state.lastLaunchCommandState.snapshot, closeReadiness = state.lastLaunchCommandState.closeReadiness) {
    const rows = [];
    [
      snapshot?.worker_progress?.rows,
      snapshot?.workers,
      snapshot?.active_jobs,
      snapshot?.diagnostics?.active_jobs,
      closeReadiness?.active_jobs,
    ].forEach((source) => {
      if (Array.isArray(source)) rows.push(...source.filter((row) => row && typeof row === "object"));
    });
    return rows;
  }

  function launchActiveJobKind(snapshot = state.lastLaunchCommandState.snapshot, closeReadiness = state.lastLaunchCommandState.closeReadiness) {
    const rows = activeJobRows(snapshot, closeReadiness);
    const activeRows = rows.filter((row) => {
      const status = String(row.status || row.status_state || "").trim().toLowerCase();
      return !status || ["launching", "active", "running", "processing"].includes(status);
    });
    const match = (activeRows.length ? activeRows : rows).find((row) => {
      const kind = String(row.job_kind || row.kind || "").trim().replace(/-/g, "_").toLowerCase();
      return kind === "rerun_csv" || kind === "csv_rerun";
    });
    if (match) return "rerun_csv";
    const reason = String(closeReadiness?.reason || snapshot?.active_work_reason || "").trim().toLowerCase();
    if (/\bcsv\b.*\brerun\b|\brerun\b.*\bcsv\b/.test(reason)) return "rerun_csv";
    const first = (activeRows[0] || rows[0]) || null;
    return String(first?.job_kind || first?.kind || "").trim().replace(/-/g, "_").toLowerCase();
  }

  function launchRerunCsvIsActive(snapshot = state.lastLaunchCommandState.snapshot, closeReadiness = state.lastLaunchCommandState.closeReadiness) {
    return launchActiveJobKind(snapshot, closeReadiness) === "rerun_csv";
  }

  function pipelineProgressIsStuck(snapshot = state.lastLaunchCommandState.snapshot) {
    const progress = snapshot?.progress && typeof snapshot.progress === "object" ? snapshot.progress : {};
    const stage = String(progress.CurrentStage || progress.current_stage || "").toLowerCase().trim();
    const status = String(progress.Status || progress.status || progress.Message || progress.message || "").toLowerCase().trim();
    if (!stage || stage === "idle" || stage === "startup") return false;
    if (progress.Stuck === true || progress.stuck === true || progress.IsStuck === true || progress.is_stuck === true) return true;
    return /\bstuck\b|\borphan\b|\bno active\b/.test(status);
  }

  function pipelineProgressIsStale(snapshot = state.lastLaunchCommandState.snapshot) {
    const progress = snapshot?.progress && typeof snapshot.progress === "object" ? snapshot.progress : {};
    const stage = String(progress.CurrentStage || progress.current_stage || "").toLowerCase().trim();
    if (!stage || stage === "idle" || stage === "startup") return false;
    return !pipelineProgressIsStuck(snapshot);
  }

  function launchPauseRequested(snapshot = state.lastLaunchCommandState.snapshot) {
    const progress = snapshot?.progress && typeof snapshot.progress === "object" ? snapshot.progress : {};
    return Boolean(progress.PauseRequested || progress.pause_requested || progress.Paused || progress.paused);
  }


  function commandHistoryEntries() {
    const history = getCommandHistory();
    return Array.isArray(history) ? history : [];
  }

  function latestCommandEntry(predicate) {
    const history = commandHistoryEntries();
    return Array.isArray(history) ? history.find(predicate) || null : null;
  }

  function commandEntryState(entry) {
    if (!entry) return "";
    const severity = String(entry.severity || entry.result || "").toLowerCase();
    if (entry.ok === true && !["warning", "error", "blocked"].some((token) => severity.includes(token))) return "ok";
    if (severity.includes("warning")) return "warning";
    if (severity.includes("error") || severity.includes("blocked") || entry.ok === false) return "blocked";
    return "review";
  }

  function commandEntrySummary(entry, emptyText) {
    if (!entry) return emptyText;
    const message = String(entry.message || entry.command || "").replace(/\s+/g, " ").trim();
    const prefix = entry.at ? `${entry.at} - ` : "";
    return `${prefix}${message || entry.command || "Command recorded."}`.slice(0, 220);
  }

  function pipelineControllerState(snapshot, closeReadiness, active, stuck) {
    if (stuck) return "stuck";
    if (active) return "active";
    if (pipelineProgressIsStale(snapshot)) return "stale";
    const state = String(snapshot?.pipeline_state || closeReadiness?.state || "idle").trim().toLowerCase();
    if (["failed", "blocked", "error"].includes(state)) return "blocked";
    if (["completed", "idle", ""].includes(state)) return "idle";
    return "review";
  }

  function pipelineControllerStageSummary(snapshot, closeReadiness, active, stuck) {
    const progress = snapshot?.progress && typeof snapshot.progress === "object" ? snapshot.progress : {};
    const stage = String(progress.CurrentStage || progress.current_stage || "").trim();
    const status = String(progress.Status || progress.status || "").trim();
    if (stuck) return stage ? `Progress reports ${stage}; no matching active work is confirmed.` : "Progress appears stuck; review Diagnostics before forcing stop.";
    if (active) return [stage ? `Stage: ${stage}` : "Backend work is active.", status].filter(Boolean).join(" - ");
    if (pipelineProgressIsStale(snapshot)) return stage ? `Stale progress evidence: ${stage}. Review Diagnostics before using emergency controls.` : "Stale progress evidence needs Diagnostics review.";
    if (closeReadiness?.reason) return `Close-readiness: ${closeReadiness.reason}`;
    return "No active backend work.";
  }

    return {
      launchPipelineIsActive,
      activeJobRows,
      launchActiveJobKind,
      launchRerunCsvIsActive,
      pipelineProgressIsStuck,
      pipelineProgressIsStale,
      launchPauseRequested,
      commandHistoryEntries,
      latestCommandEntry,
      commandEntryState,
      commandEntrySummary,
      pipelineControllerState,
      pipelineControllerStageSummary,
    };
  }

  window.__launchControllerStateModule = {
    createLaunchControllerStateModule,
  };
})();
