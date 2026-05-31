/* global commandHistoryIssueLevel, getCommandHistory, getLastMaintenance, lastRefreshCompletedAt, lastRefreshDurationMs, refreshTimeLabel, renderProgressBarsInto, settingsOperatorTrustStatus, settingsRawActionPlanRows, settingsRawActionPlanStatus, shortenPath */
(function () {
  function homeReadinessNextStep({ snapshot, closeReadiness, failures }) {
    const items = Array.isArray(failures) ? failures : [];
    const requiredFailure = items.find((item) => item.required);
    if (requiredFailure) {
      return `Refresh the page or open Diagnostics; required backend read failed: ${requiredFailure.name}.`;
    }
    if (!snapshot) {
      return "Refresh the page or open Diagnostics; no backend snapshot is available.";
    }
    if (!closeReadiness) {
      return "Close-readiness has not loaded yet. Wait for the next refresh before closing the app.";
    }
    if (closeReadiness.safe_to_close === false) {
      return "Do not close unless intentionally interrupting active work. Check Home progress, ActiveJobs, and Run Logs.";
    }
    const optionalFailures = items.filter((item) => !item.required);
    if (optionalFailures.length) {
      return "Core snapshot is available, but one or more supporting panels failed. Use Diagnostics for the failed read(s).";
    }
    const state = String(snapshot.pipeline_state || "").toLowerCase();
    if (["processing", "running", "active", "publishing"].includes(state)) {
      return "Pipeline appears active. Monitor progress and avoid closing until close-readiness reports safe.";
    }
    return "Ready for normal operation.";
  }

  function renderHomeReadiness({ snapshot = null, closeReadiness = null, failures = [] } = {}) {
    const items = Array.isArray(failures) ? failures : [];
    const requiredFailures = items.filter((item) => item.required);
    const optionalFailures = items.filter((item) => !item.required);
    const safe = closeReadiness ? Boolean(closeReadiness.safe_to_close) : null;
    const state = snapshot?.pipeline_state || closeReadiness?.state || "unknown";
    const status = requiredFailures.length
      ? "Backend issue"
      : safe === false
        ? "Active work"
        : optionalFailures.length
          ? "Limited"
          : safe === true
            ? "Ready"
            : "Checking";
    setTextState("home-readiness-status", status, status === "Ready" ? "ok" : status === "Checking" ? "loading" : status === "Backend issue" ? "blocked" : "warning");
    const lines = [
      `Backend snapshot: ${snapshot ? "ok" : "unavailable"}`,
      `Refresh health: ${items.length ? `${items.length} issue${items.length === 1 ? "" : "s"}` : "ok"}`,
      `Close readiness: ${safe === null ? "unknown" : safe ? "safe" : "active work"}`,
      `Pipeline state: ${state}`,
    ];
    if (closeReadiness?.reason) lines.push(`Close reason: ${closeReadiness.reason}`);
    if (requiredFailures.length) {
      lines.push("", "Required read failure(s):");
      requiredFailures.forEach((item) => lines.push(`- ${item.name}: ${item.message}`));
    }
    if (optionalFailures.length) {
      lines.push("", "Supporting read issue(s):");
      optionalFailures.forEach((item) => lines.push(`- ${item.name}: ${item.message}`));
    }
    const warnings = Array.isArray(closeReadiness?.warnings) ? closeReadiness.warnings : [];
    if (warnings.length) {
      lines.push("", "Close-readiness warning(s):");
      warnings.slice(0, 5).forEach((warning) => lines.push(`- ${warning}`));
    }
    lines.push("", `Next step: ${homeReadinessNextStep({ snapshot, closeReadiness, failures: items })}`);
    setText("home-readiness-summary", lines.join("\n"));
  }

  function dailyDriverCount(value) {
    const number = Number(value || 0);
    return Number.isFinite(number) ? Math.max(0, Math.round(number)) : 0;
  }

  function dailyDriverRow(area, status, evidence, nextStep) {
    return { area, status, evidence, nextStep };
  }

  function dailyDriverStatusRank(status) {
    const normalized = String(status || "").toLowerCase();
    if (normalized === "blocked") return 0;
    if (normalized === "review" || normalized === "unknown") return 1;
    if (normalized === "ready") return 2;
    return 3;
  }

  function dailyDriverOverallStatus(rows) {
    if (!rows.length) return "Not evaluated";
    if (rows.some((row) => row.status === "blocked")) return "Blocked review";
    if (rows.some((row) => row.status === "review" || row.status === "unknown")) return "Review";
    return "Ready";
  }

  function dailyDriverStatusClass(status) {
    const normalized = String(status || "").toLowerCase();
    if (normalized === "blocked") return "blocked";
    if (normalized === "review" || normalized === "unknown") return "warning";
    return "match";
  }

  function dailyDriverSettingsStatus(settings) {
    if (!settings || typeof settings !== "object" || !settings.schema_version) return "unknown";
    let trustStatus = "";
    try {
      trustStatus = typeof settingsOperatorTrustStatus === "function" ? settingsOperatorTrustStatus(settings) : "";
    } catch {
      trustStatus = "";
    }
    const errors = Array.isArray(settings.errors) ? settings.errors : [];
    const highest = String(settings.risk_summary?.highest_severity || "").toLowerCase();
    const normalized = String(trustStatus || "").toLowerCase();
    if (errors.length || highest === "critical" || normalized.includes("critical") || normalized.includes("invalid")) return "blocked";
    if (highest === "high" || dailyDriverCount(settings.risk_summary?.total_count) || (settings.warnings || []).length || normalized.includes("review") || normalized.includes("high")) return "review";
    return "ready";
  }

  function dependencyStatusRank(status) {
    const normalized = String(status || "").toLowerCase();
    if (normalized.includes("block") || normalized.includes("missing") || normalized.includes("error")) return 0;
    if (normalized.includes("review") || normalized.includes("warning") || normalized.includes("unknown") || normalized.includes("not loaded")) return 1;
    if (normalized.includes("ready") || normalized.includes("ok")) return 2;
    return 1;
  }

  function dependencyStatusLabel(status) {
    const rank = dependencyStatusRank(status);
    if (rank === 0) return "blocked";
    if (rank === 1) return "review";
    return "ready";
  }

  function dailyDriverDiagnosticsCounts(diagnostics) {
    const view = window.mediaPipelineCrossPageContextView || {};
    if (typeof view.crossPageDiagnosticsCounts === "function") return view.crossPageDiagnosticsCounts(diagnostics || {});
    return {};
  }

  function dailyDriverCommandIssues() {
    const history = typeof getCommandHistory === "function" ? getCommandHistory() : [];
    if (!Array.isArray(history)) return [];
    return history.filter((entry) => {
      const level = typeof commandHistoryIssueLevel === "function" ? commandHistoryIssueLevel(entry) : (entry?.ok ? "ok" : (entry?.severity || "error"));
      return !["ok", "info", "none"].includes(String(level || "").toLowerCase());
    });
  }

  function dailyDriverRealMediaProofRow({ queue = {}, completed = {}, pending = {}, diagnosticCounts = {} } = {}) {
    const queueRows = Array.isArray(queue.rows) ? queue.rows.length : 0;
    const completedList = Array.isArray(completed.rows) ? completed.rows : [];
    const completedRows = completedList.length;
    const pendingRows = Array.isArray(pending.rows) ? pending.rows.length : 0;
    const missingOutputs = dailyDriverCount(completed.missing_output_count);
    const sizePolicyExceededRows = dailyDriverCount(completed.size_policy_exceeded_count);
    const legacySizeGrowthRows = completedList.filter((row) => row?.size_growth_over_5 && !row?.size_policy_available).length;
    const pendingIssues = dailyDriverCount(pending.issue_count) + dailyDriverCount(pending.health_count);
    const diagnosticsErrors = dailyDriverCount(diagnosticCounts.error);
    const diagnosticsWarnings = dailyDriverCount(diagnosticCounts.warning);
    const blocked = missingOutputs > 0 || pendingIssues > 0 || diagnosticsErrors > 0;
    const sizeNeedsReview = sizePolicyExceededRows > 0 || legacySizeGrowthRows > 0;
    const hasProofSources = completedRows > 0;
    const status = blocked || sizeNeedsReview ? "review" : hasProofSources ? "ready" : "review";
    const evidence = `queue rows=${queueRows}; completed rows=${completedRows}; pending rows=${pendingRows}; missing outputs=${missingOutputs}; size policy exceeded=${sizePolicyExceededRows}; legacy growth >5% without policy=${legacySizeGrowthRows}; pending issues=${pendingIssues}; diagnostics errors=${diagnosticsErrors}; diagnostics warnings=${diagnosticsWarnings}`;
    const nextStep = completedRows <= 0
      ? "Before treating WebView as daily-driver ready, process a small known batch and compare Queue route, subtitle/audio evidence, Completed output proof, Diagnostics logs, and Pending Publish drain state."
      : blocked
        ? "Use the real-media validation playbook before rerun, cleanup, drain, or acceptance; visible output/publish/diagnostics issues still need review."
        : "Loaded proof sources exist; inspect a known completed sample row and verify route, subtitle/audio, sidecar, size-growth, and publish evidence agree.";
    return dailyDriverRow("Real-media sample proof", status, evidence, nextStep);
  }

  function dailyDriverRows(context = {}) {
    const failures = Array.isArray(context.failures) ? context.failures : [];
    const requiredFailures = failures.filter((item) => item.required);
    const optionalFailures = failures.filter((item) => !item.required);
    const snapshot = context.snapshot || null;
    const closeReadiness = context.closeReadiness || null;
    const settings = context.settings || {};
    const queue = context.queue || {};
    const completed = context.completed || {};
    const pending = context.pending || {};
    const diagnostics = context.diagnostics || {};
    const dependencyStatus = externalDependencyOverallStatus(context);
    const schedule = context.schedule || {};
    const networkWorkers = context.networkWorkers || {};
    const commandIssues = dailyDriverCommandIssues();
    const diagnosticCounts = dailyDriverDiagnosticsCounts(diagnostics);
    const rows = [];
  
    rows.push(dailyDriverRow(
      "Refresh payloads",
      requiredFailures.length ? "blocked" : optionalFailures.length ? "review" : "ready",
      `required failures=${requiredFailures.length}; supporting failures=${optionalFailures.length}; completed=${refreshTimeLabel(lastRefreshCompletedAt)}${Number.isFinite(lastRefreshDurationMs) ? `; duration=${lastRefreshDurationMs}ms` : ""}`,
      requiredFailures.length
        ? "Open Diagnostics and resolve required backend reads before trusting the WebView."
        : optionalFailures.length
          ? "Use Diagnostics for supporting read issues; avoid unattended runs until important panels refresh cleanly."
          : "Core payload refresh is clean.",
    ));
  
    rows.push(dailyDriverRow(
      "Close / active work",
      !snapshot || !closeReadiness ? "unknown" : closeReadiness.safe_to_close === false || closeReadiness.active_work ? "review" : "ready",
      `snapshot=${snapshot ? "loaded" : "missing"}; close=${closeReadiness ? (closeReadiness.safe_to_close ? "safe" : "active") : "unknown"}; state=${snapshot?.pipeline_state || closeReadiness?.state || "unknown"}`,
      closeReadiness?.safe_to_close === false || closeReadiness?.active_work
        ? "Monitor progress, ActiveJobs, and logs before closing or starting more work."
        : "No active-work block is currently reported.",
    ));
  
    const settingsStatus = dailyDriverSettingsStatus(settings);
    rows.push(dailyDriverRow(
      "Saved settings",
      settingsStatus,
      settings?.schema_version
        ? `risk=${settings.risk_summary?.highest_severity || "none"}; warnings=${(settings.warnings || []).length}; errors=${(settings.errors || []).length}`
        : "settings workspace not loaded",
      settingsStatus === "blocked"
        ? "Use Settings > Validate / Reload and resolve critical settings before launch."
        : settingsStatus === "review"
          ? "Review Settings trust and staged patch handoff before unattended work."
          : "Saved settings posture is clean in the loaded workspace.",
    ));
  
    rows.push(dailyDriverRow(
      "External dependencies",
      dependencyStatus === "blocked" ? "blocked" : dependencyStatus === "review" || dependencyStatus === "unknown" ? "review" : "ready",
      externalDependencyEvidenceText(context),
      dependencyStatus === "blocked"
        ? "Resolve blocked Settings OCR or Maintenance toolchain evidence before launch/rerun decisions."
        : dependencyStatus === "review" || dependencyStatus === "unknown"
          ? "Review Settings OCR and Maintenance toolchain evidence before long unattended processing."
          : "No external dependency blocker is visible in loaded Settings/Diagnostics/Maintenance evidence.",
    ));
  
    rows.push(dailyDriverRow(
      "Queue",
      queue.error ? "review" : String(queue.snapshot_file_freshness_status || "").toLowerCase() === "stale" || dailyDriverCount(queue.invalid_row_count) || dailyDriverCount(queue.blocked_row_count) ? "review" : "ready",
      `rows=${Array.isArray(queue.rows) ? queue.rows.length : 0}; runnable=${dailyDriverCount(queue.runnable_count || (Array.isArray(queue.rows) ? queue.rows.length : 0))}; stale=${queue.snapshot_file_freshness_status || "unknown"}; blocked=${dailyDriverCount(queue.blocked_row_count)}; invalid=${dailyDriverCount(queue.invalid_row_count)}`,
      queue.error
        ? "Open Queue and Diagnostics; queue payload reported an error."
        : String(queue.snapshot_file_freshness_status || "").toLowerCase() === "stale"
          ? "Refresh Queue before Launch because stale snapshots can disagree with current state."
          : "Use Launch only after Queue row guidance and schedule/settings preflight look correct.",
    ));
  
    rows.push(dailyDriverRow(
      "Completed proof",
      completed.error || dailyDriverCount(completed.missing_output_count) ? "review" : dailyDriverCount(completed.size_policy_exceeded_count) ? "review" : "ready",
      `rows=${Array.isArray(completed.rows) ? completed.rows.length : 0}; missing outputs=${dailyDriverCount(completed.missing_output_count)}; size policy exceeded=${dailyDriverCount(completed.size_policy_exceeded_count)}; within policy=${dailyDriverCount(completed.size_policy_within_limit_count)}`,
      dailyDriverCount(completed.missing_output_count)
        ? "Review Completed Output Proof, Pending Publish, Run Logs, and Last Stderr before rerun or cleanup."
        : dailyDriverCount(completed.size_policy_exceeded_count)
          ? "Review rows that exceeded recorded backend size_policy before treating recent encodes as intentional."
          : "Completed proof has no loaded blocker.",
    ));
  
    rows.push(dailyDriverRow(
      "Pending Publish",
      pending.error || dailyDriverCount(pending.issue_count) || dailyDriverCount(pending.health_count) ? "review" : "ready",
      `rows=${Array.isArray(pending.rows) ? pending.rows.length : 0}; issues=${dailyDriverCount(pending.issue_count)}; health=${dailyDriverCount(pending.health_count)}; ready=${dailyDriverCount(pending.ready_count)}`,
      dailyDriverCount(pending.issue_count) || dailyDriverCount(pending.health_count)
        ? "Review Pending Publish diagnostics/recovery before draining, rerunning, or cleaning outputs."
        : "Pending Publish has no loaded drain blocker.",
    ));
  
    rows.push(dailyDriverRealMediaProofRow({ queue, completed, pending, diagnosticCounts }));
  
    rows.push(dailyDriverRow(
      "Diagnostics",
      dailyDriverCount(diagnosticCounts.error) ? "review" : dailyDriverCount(diagnosticCounts.warning) ? "review" : "ready",
      `errors=${dailyDriverCount(diagnosticCounts.error)}; warnings=${dailyDriverCount(diagnosticCounts.warning)}; info=${dailyDriverCount(diagnosticCounts.info)}`,
      dailyDriverCount(diagnosticCounts.error) || dailyDriverCount(diagnosticCounts.warning)
        ? "Open Diagnostics Investigation Trail and inspect read-first evidence before unattended operation."
        : "No warning/error diagnostics are visible in the loaded payload.",
    ));
  
    rows.push(dailyDriverRow(
      "Recent commands",
      commandIssues.length ? "review" : "ready",
      `recent command issues=${commandIssues.length}`,
      commandIssues.length
        ? "Inspect Command Results or Diagnostics Command Result Drilldown before repeating actions."
        : "Recent command history has no visible warning/error result.",
    ));
  
    const scheduleEnabled = Boolean(schedule.enabled);
    const allowedNow = schedule.evaluation?.allowed_now !== false;
    rows.push(dailyDriverRow(
      "Schedule / launch",
      scheduleEnabled && !allowedNow ? "review" : "ready",
      `schedule=${scheduleEnabled ? "enabled" : "off"}; allowed now=${allowedNow ? "yes" : "no"}`,
      scheduleEnabled && !allowedNow
        ? "Use Launch timing trust before outside-window testing; schedule bypass must be deliberate."
        : "Launch timing does not show a schedule-window block in the loaded payload.",
    ));
  
    const role = String(settings?.config?.NetworkRole || "").trim().toLowerCase() || "standalone";
    const workerRows = Array.isArray(networkWorkers?.rows) ? networkWorkers.rows.length : 0;
    rows.push(dailyDriverRow(
      "Network visibility",
      role && role !== "standalone" ? "review" : "ready",
      `role=${role}; persisted worker rows=${workerRows}`,
      role && role !== "standalone"
        ? "Network mode remains read-only in WebView; use backend-owned coordinator/worker lifecycle controls."
        : "Standalone mode is visible; Network page remains read-only.",
    ));
  
    return rows.sort((left, right) => dailyDriverStatusRank(left.status) - dailyDriverStatusRank(right.status));
  }

  function dailyDriverSummaryLines(rows) {
    const counts = rows.reduce((acc, row) => {
      const key = row.status || "unknown";
      acc[key] = (acc[key] || 0) + 1;
      return acc;
    }, {});
    const firstAction = rows.find((row) => row.status === "blocked" || row.status === "review" || row.status === "unknown");
    const lines = [
      "Daily-driver readiness checklist:",
      `Status: ${dailyDriverOverallStatus(rows)}`,
      `Rows: ${rows.length}; blocked=${counts.blocked || 0}; review=${counts.review || 0}; unknown=${counts.unknown || 0}; ready=${counts.ready || 0}.`,
      `Refresh evidence: completed ${refreshTimeLabel(lastRefreshCompletedAt)}${Number.isFinite(lastRefreshDurationMs) ? ` in ${lastRefreshDurationMs} ms` : ""}.`,
      "Real-media boundary: WebView readiness is not proof by itself. Daily-driver confidence still requires a known sample run whose Queue, Completed, Diagnostics, and Pending Publish evidence agree.",
    ];
    lines.push("", `Next operator action: ${firstAction ? `${firstAction.area}: ${firstAction.nextStep}` : "No checklist blocker is visible; refresh once before long unattended operation."}`);
    lines.push("Mutation guardrail: this checklist is read-only and does not launch, repair, drain, save, rename, delete, publish, or touch media files.");
    return lines;
  }

  function homeAtAGlanceStatusState(label) {
    const normalized = String(label || "").toLowerCase();
    if (normalized === "blocked") return "blocked";
    if (normalized === "review") return "warning";
    if (normalized === "active") return "changed";
    if (normalized === "idle" || normalized === "ready") return "ok";
    return "loading";
  }

  function homeAtAGlancePercent(value) {
    const number = Number(value);
    if (!Number.isFinite(number)) return "";
    const bounded = Math.max(0, Math.min(100, number));
    return `${bounded.toFixed(bounded % 1 ? 1 : 0)}%`;
  }

  function homeAtAGlanceShortValue(value, maxChars = 64) {
    const text = formatProgressValue(value || "");
    if (!text) return "";
    if (typeof shortenPath === "function") return shortenPath(text, maxChars);
    return text.length > maxChars ? `...${text.slice(-(maxChars - 3))}` : text;
  }

  function homeAtAGlanceCurrentFile(progress = {}) {
    return progress.CurrentFileDisplay
      || progress.CurrentFile
      || progress.CurrentFilePath
      || progress.SourceFile
      || progress.SourcePath
      || progress.InputPath
      || progress.OutputPath
      || "";
  }

  function homeAtAGlanceQueuePosition(progress = {}) {
    const index = progress.CurrentQueueIndex;
    const total = progress.CurrentQueueTotal;
    if ((index === undefined || index === null || index === "") && (total === undefined || total === null || total === "")) return "";
    return `${formatProgressValue(index || 0)} / ${formatProgressValue(total || 0)}`;
  }

  function homeAtAGlanceQueueTitle(item = {}) {
    return item.lookup_title
      || item.display_name
      || item.title
      || item.source_file_name
      || item.source_file
      || item.source_path
      || item.path
      || item.input_path
      || item.file
      || "";
  }

  function homeAtAGlanceQueueMeta(item = {}) {
    return [
      item.route_name || item.route || item.mode || "",
      item.status || item.operator_status || item.decision || "",
      item.queue_position || (item.queue_index || item.queue_total ? `${item.queue_index || "?"}/${item.queue_total || "?"}` : ""),
    ].filter(Boolean).map(formatProgressValue).join(" · ");
  }

  function homeAtAGlanceProgressNumber(value) {
    const number = Number(value);
    if (!Number.isFinite(number)) return null;
    return Math.max(0, Math.min(100, number));
  }

  function homeAtAGlancePushStatus(value) {
    const state = String(value || "").toLowerCase();
    if (state.includes("fail") || state.includes("error") || state.includes("blocked")) return "blocked";
    if (state.includes("complete") || state.includes("deferred") || state.includes("published")) return "complete";
    if (state.includes("copy") || state.includes("push") || state.includes("reveal")) return "active";
    return state ? "unknown" : "";
  }

  function homeAtAGlanceBarStatusLabel(bar) {
    const status = String(bar?.status || "unknown").trim();
    const mode = String(bar?.mode || "determinate").trim();
    const percent = bar?.percent;
    if (mode === "indeterminate") return status === "active" ? `${status} · running` : status;
    const value = Number(percent);
    if (!Number.isFinite(value)) return status;
    const bounded = Math.max(0, Math.min(100, value));
    return `${status} · ${bounded.toFixed(bounded % 1 ? 1 : 0)}%`;
  }

  void [homeAtAGlanceBarStatusLabel];

  function homeAtAGlancePerFilePushBar(snapshot = null, progress = {}) {
    const bars = Array.isArray(snapshot?.progress_bars) ? snapshot.progress_bars.filter(Boolean) : [];
    const backendBar = bars.find((bar) => String(bar?.id || "").toLowerCase() === "publish_copy");
    if (backendBar) {
      return {
        ...backendBar,
        id: "home_push_file",
        label: "Push file",
      };
    }
    const pushState = progress.PushState || progress.push_state || "";
    const status = homeAtAGlancePushStatus(pushState);
    if (!status || status === "complete") return null;
    const copyPercent = homeAtAGlanceProgressNumber(progress.CopyPercent ?? progress.copy_percent);
    const copied = progress.CopyBytesCopied ?? progress.copy_bytes_copied ?? "";
    const total = progress.CopyTotalBytes ?? progress.copy_total_bytes ?? "";
    const file = homeAtAGlanceShortValue(homeAtAGlanceCurrentFile(progress), 88);
    const detail = [
      pushState ? `Push ${formatProgressValue(pushState)}` : "",
      copied !== "" && total !== "" ? `${formatProgressValue(copied)} / ${formatProgressValue(total)} bytes` : "",
      file ? `File ${file}` : "",
    ].filter(Boolean).join(" · ");
    return {
      id: "home_push_file",
      label: "Push file",
      mode: copyPercent === null ? "indeterminate" : "determinate",
      percent: copyPercent === null ? 0 : copyPercent,
      status,
      detail: detail || "Per-file push is active.",
      source: "pipeline_progress.json",
      updated_at: progress.CopyUpdatedAt || progress.LastUpdate || progress.UpdatedAt || "",
      stale: false,
    };
  }

  function homeAtAGlanceUpcomingRows(queue = {}, progress = {}) {
    const rows = Array.isArray(queue.rows) ? queue.rows.filter(Boolean) : [];
    if (!rows.length) return [];
    const currentIndex = Number(progress.CurrentQueueIndex);
    const startIndex = Number.isFinite(currentIndex) && currentIndex > 0 && currentIndex < rows.length
      ? Math.floor(currentIndex)
      : 0;
    return rows.slice(startIndex, startIndex + 4);
  }

  function homeAtAGlanceModel(context = {}) {
    const snapshot = context.snapshot || null;
    const closeReadiness = context.closeReadiness || null;
    const diagnostics = context.diagnostics || {};
    const queue = context.queue || {};
    const progress = snapshot?.progress && typeof snapshot.progress === "object" ? snapshot.progress : {};
    const activeJobs = Array.isArray(diagnostics?.active_jobs) ? diagnostics.active_jobs.filter(Boolean) : [];
    const workerProgress = window.mediaPipelineProgressView?.progressWorkerPayload?.(snapshot, diagnostics) || {};
    const workerRows = window.mediaPipelineProgressView?.progressWorkerRows?.(snapshot, diagnostics) || [];
    const activeWorkerRows = workerRows.filter((row) => ["running", "warning", "blocked"].includes(String(row?.status_state || "").toLowerCase()));
    const pipelineState = snapshot?.pipeline_state || closeReadiness?.state || "unknown";
    const stateActive = ["processing", "running", "active", "publishing", "audit"].includes(String(pipelineState || "").toLowerCase());
    const active = activeJobs.length > 0 || activeWorkerRows.length > 0 || closeReadiness?.safe_to_close === false || stateActive;
    const primaryWorker = activeWorkerRows[0] || workerRows[0] || {};
    const stage = progress.CurrentStage || primaryWorker.stage || progress.Status || "";
    const percent = homeAtAGlancePercent(progress.CurrentStagePercent);
    const percentNumber = Number(progress.CurrentStagePercent);
    const rawFile = homeAtAGlanceCurrentFile(progress) || primaryWorker.source || "";
    const file = homeAtAGlanceShortValue(rawFile, 88);
    const queuePosition = homeAtAGlanceQueuePosition(progress);
    const route = progress.CurrentRoute || progress.Route || "";
    const detail = [
      stage ? `Stage ${formatProgressValue(stage)}` : "",
      percent ? percent : "",
      route ? `Route ${formatProgressValue(route)}` : "",
      queuePosition ? `Queue ${queuePosition}` : "",
      workerProgress.status ? `Workers ${formatProgressValue(workerProgress.status)}` : "",
      activeJobs.length ? `${activeJobs.length} ActiveJobs` : "",
    ].filter(Boolean).join(" · ");
    const status = !snapshot && !closeReadiness
      ? "Checking"
      : active
        ? "Active"
        : Object.keys(progress).length
          ? "Idle"
          : "Ready";
    return {
      active,
      status,
      pipelineState,
      file,
      rawFile,
      stage,
      percent,
      percentNumber,
      route,
      queuePosition,
      pushBar: homeAtAGlancePerFilePushBar(snapshot, progress),
      detail: detail || `Pipeline ${pipelineState}; close ${closeReadiness ? (closeReadiness.safe_to_close ? "safe" : "active work") : "unknown"}.`,
      currentText: file ? `${stage ? formatProgressValue(stage) : "Processing"}: ${file}` : active ? "Backend work is active." : "No active item.",
      upcoming: homeAtAGlanceUpcomingRows(queue, progress),
    };
  }

  function homeAtAGlanceProgressBar(model) {
    const bars = [];
    if (!model.active && !Number.isFinite(model.percentNumber)) return model.pushBar ? [model.pushBar] : [];
    const percent = Number.isFinite(model.percentNumber) ? model.percentNumber : 0;
    bars.push({
      id: "home_current_item",
      label: "Current item",
      mode: Number.isFinite(model.percentNumber) ? "determinate" : "indeterminate",
      percent,
      status: model.active ? "active" : percent >= 100 ? "complete" : "unknown",
      detail: model.detail || "No progress detail reported.",
      source: "snapshot progress",
    });
    if (model.pushBar) bars.push(model.pushBar);
    return bars;
  }

  function renderHomePendingCount(pending) {
    pending = pending && typeof pending === "object" ? pending : {};
    setText("home-pending-count", String(pending.count || 0));
  }

  function renderHomeNetworkRole(settings) {
    settings = settings && typeof settings === "object" ? settings : {};
    const role = String(settings?.config?.NetworkRole || "").trim().toLowerCase() || "standalone";
    setText("home-network-role", role);
  }

  function renderHomeQueueSnapshot(queue) {
    queue = queue && typeof queue === "object" ? queue : {};
    const rows = Array.isArray(queue.rows) ? queue.rows : [];
    const runnable = queue.runnable_count !== undefined ? queue.runnable_count : rows.length;
    const blocked = queue.blocked_row_count || 0;
    const priority = queue.priority_count || rows.filter((r) => r?.is_priority).length || 0;
    const encodeRows = rows.filter((r) => String(r?.route_name || "").toLowerCase().includes("encode")).length;
    const remuxRows = rows.filter((r) => String(r?.route_name || "").toLowerCase().includes("remux")).length;
    // Drive the dashboard "Queue" metric tile from the real snapshot data so
    // it shows the actual queue size (runnable / total rows) rather than the
    // active run's batch position (CurrentQueueIndex/Total), which was always
    // 0/0 when the pipeline was idle.
    setText("queue-count", `${runnable} / ${rows.length}`);
    const lines = [
      `Rows: ${rows.length} | Runnable: ${runnable} | Blocked: ${blocked}`,
      priority ? `Priority: ${priority}` : "",
      encodeRows || remuxRows ? `Route mix: ${encodeRows} encode / ${remuxRows} remux` : "",
      queue.error ? `Error: ${queue.error}` : "",
      ...(Array.isArray(queue.warnings) ? queue.warnings.slice(0, 2) : []),
    ].filter(Boolean);
    const statusEl = byId("home-queue-snapshot-status");
    if (statusEl) statusEl.textContent = rows.length ? `${rows.length} items` : "Empty";
    const pre = byId("home-queue-snapshot");
    if (pre) pre.textContent = lines.join("\n") || "No queue data loaded.";
  }

  function renderHomeRecentCompleted(completed) {
    completed = completed && typeof completed === "object" ? completed : {};
    const rows = Array.isArray(completed.rows) ? completed.rows : [];
    const tbody = byId("home-recent-completed-tbody");
    if (!tbody) return;
    const statusEl = byId("home-recent-completed-status");
    if (statusEl) statusEl.textContent = rows.length ? `${completed.count || rows.length} total` : "No data";
    tbody.textContent = "";
    const recent = rows.slice(0, 5);
    if (!recent.length) {
      const tr = document.createElement("tr");
      if (typeof appendCells === "function") appendCells(tr, ["No completed files loaded.", "", ""]);
      tbody.appendChild(tr);
      return;
    }
    recent.forEach((row) => {
      const title = String(row.lookup_title || row.output_file || row.output_path || "—");
      const shortTitle = title.length > 48 ? "…" + title.slice(-47) : title;
      const route = String(row.route_name || row.mode || "—");
      const finished = String(row.completed_at || row.manifest_recorded_at || "—");
      const tr = document.createElement("tr");
      if (typeof appendCells === "function") appendCells(tr, [shortTitle, route, finished]);
      const firstCell = tr.cells[0];
      if (firstCell) firstCell.title = title;
      tbody.appendChild(tr);
    });
  }

  function homePromotionRunActive(status = {}) {
    const active = status?.active_run && typeof status.active_run === "object" ? status.active_run : {};
    const state = String(active.status || "").toLowerCase();
    return Boolean(active.run_id && ["running", "pausing", "paused"].includes(state));
  }

  function renderHomePromotionEntry(status = {}) {
    const payload = status && typeof status === "object" ? status : {};
    const buttons = Array.from(document.querySelectorAll("[data-home-promotion-entry]"));
    if (!buttons.length) return;
    const counts = payload.counts && typeof payload.counts === "object" ? payload.counts : {};
    const enabled = Boolean(payload.enabled);
    const eligible = Number(counts.eligible || 0);
    const active = homePromotionRunActive(payload);
    const disabled = !enabled || active || eligible <= 0;
    const title = !enabled
      ? "Final Library Promotion is disabled in Settings."
      : active
        ? "A final-library promotion run is already active."
        : eligible > 0
          ? `Open Output to promote ${eligible} reviewed file${eligible === 1 ? "" : "s"} to the final library.`
          : "No reviewed files are currently eligible for final-library promotion.";
    buttons.forEach((button) => {
      button.disabled = disabled;
      button.setAttribute("aria-disabled", String(disabled));
      button.textContent = "Promote Files";
      button.title = title;
    });
  }

  function externalDependencyRows(context = {}) {
    const payload = context || {};
    const settings = payload.settings || {};
    const stateSummary = payload.stateSummary || payload.diagnosticsStateSummary || {};
    const maintenance = payload.maintenance || (typeof getLastMaintenance === "function" ? getLastMaintenance() : {});
    const rows = [];
    const bdpgs = settings?.tool_path_evidence?.bdpgs_ocr;
    if (bdpgs && typeof bdpgs === "object") {
      const status = dependencyStatusLabel(bdpgs.operator_status || (bdpgs.enabled ? "unknown" : "ready"));
      const attention = Boolean(bdpgs.enabled) && status !== "ready";
      rows.push({
        area: "Settings BDPGS OCR paths",
        status: attention ? status : "ready",
        evidence: `enabled=${bdpgs.enabled ? "yes" : "no"}; blocked=${bdpgs.blocked_count || 0}; review=${bdpgs.review_count || 0}`,
        nextStep: attention ? "Open Settings > Subtitles and fix saved OCR tool/tessdata path evidence or disable OCR intentionally before rerunning PGS subtitle conversion." : "Saved BDPGS OCR path evidence is not blocking in the loaded Settings payload."
      });
    } else {
      rows.push({
        area: "Settings BDPGS OCR paths",
        status: "unknown",
        evidence: "settings tool-path evidence not loaded",
        nextStep: "Refresh Settings before diagnosing OCR path failures."
      });
    }
    const vobsub = settings?.tool_path_evidence?.vobsub_ocr;
    if (vobsub && typeof vobsub === "object") {
      const status = dependencyStatusLabel(vobsub.operator_status || (vobsub.enabled ? "unknown" : "ready"));
      const attention = Boolean(vobsub.enabled) && status !== "ready";
      rows.push({
        area: "Settings VobSub OCR paths",
        status: attention ? status : "ready",
        evidence: `enabled=${vobsub.enabled ? "yes" : "no"}; blocked=${vobsub.blocked_count || 0}; review=${vobsub.review_count || 0}`,
        nextStep: attention ? "Open Settings > Subtitles and fix saved Subtitle Edit/Tesseract path evidence or disable OCR intentionally before rerunning VobSub subtitle conversion." : "Saved VobSub OCR path evidence is not blocking in the loaded Settings payload."
      });
    } else {
      rows.push({
        area: "Settings VobSub OCR paths",
        status: "unknown",
        evidence: "settings tool-path evidence not loaded",
        nextStep: "Refresh Settings before diagnosing OCR path failures."
      });
    }
    const settingsIssues = Array.isArray(stateSummary?.settings_tool_path_issues) ? stateSummary.settings_tool_path_issues : [];
    if (settingsIssues.length) {
      const blocked = settingsIssues.filter(item => dependencyStatusLabel(item?.operator_status || item?.status) === "blocked").length;
      rows.push({
        area: "Diagnostics settings handoff",
        status: blocked ? "blocked" : "review",
        evidence: `settings dependency issue rows=${settingsIssues.length}; blocked=${blocked}`,
        nextStep: "Use Diagnostics State Artifact Summary read order, then return to Settings > Subtitles before rerun or manual-review decisions."
      });
    }
    if (typeof settingsRawActionPlanRows === "function") {
      const rawActionRows = settingsRawActionPlanRows();
      if (rawActionRows.length) {
        const rawStatus = typeof settingsRawActionPlanStatus === "function" ? settingsRawActionPlanStatus(rawActionRows) : "Review";
        const blockedRows = rawActionRows.filter(row => String(row.posture || "").toLowerCase().includes("blocked"));
        const highRows = rawActionRows.filter(row => String(row.posture || "").toLowerCase().includes("high"));
        const reviewRows = rawActionRows.filter(row => String(row.posture || "").toLowerCase().includes("review") || String(row.posture || "").toLowerCase().includes("exclusion"));
        const schemaRow = rawActionRows.find(row => row.key === "schema-drift");
        const ocrRows = rawActionRows.filter(row => row.key === "bdpgs-ocr-paths" || row.key === "vobsub-ocr-paths");
        const ocrPosture = ocrRows.map(row => row.posture || "unknown").join(" / ") || "unknown";
        rows.push({
          area: "Settings raw-key action plan",
          status: blockedRows.length ? "blocked" : highRows.length ? "review" : "ready",
          evidence: `status=${rawStatus}; rows=${rawActionRows.length}; blocked=${blockedRows.length}; high=${highRows.length}; review/exclusion=${reviewRows.length}; schema=${schemaRow?.posture || "unknown"}; OCR=${ocrPosture}`,
          nextStep: blockedRows.length ? "Open Settings > Raw-Key Action Plan before save, launch, rerun, or OCR decisions; schema drift and blocked raw keys need backend Preview Patch evidence." : highRows.length ? "Open Settings > Raw-Key Action Plan and verify OCR path evidence or advanced settings before unattended processing." : "Raw-key action plan has no blocking/high-review row in the loaded Settings workspace; subtitle keyword builder coverage and auth-token exclusions remain read-only guidance."
        });
      } else {
        rows.push({
          area: "Settings raw-key action plan",
          status: "review",
          evidence: "raw-key action-plan rows not loaded",
          nextStep: "Open Settings and refresh the workspace before diagnosing schema drift, OCR path keys, or network auth-token boundaries."
        });
      }
    }
    const toolchain = maintenance?.toolchain_evidence;
    if (toolchain && typeof toolchain === "object" && toolchain.schema_version) {
      const status = dependencyStatusLabel(toolchain.operator_status);
      const rowsList = Array.isArray(toolchain.rows) ? toolchain.rows : [];
      const blockedNames = rowsList.filter(row => row?.required && dependencyStatusLabel(row?.operator_status || row?.status) !== "ready").map(row => row.name || row.tool_kind || "tool").slice(0, 5);
      const reviewNames = rowsList.filter(row => row?.optional && dependencyStatusLabel(row?.operator_status || row?.status) !== "ready").map(row => row.name || row.tool_kind || "tool").slice(0, 5);
      rows.push({
        area: "Maintenance toolchain",
        status,
        evidence: `tools=${toolchain.tool_count || rowsList.length || 0}; required missing=${toolchain.required_missing_count || 0}; optional review=${toolchain.optional_review_count || 0}${blockedNames.length ? `; blocking=${blockedNames.join(", ")}` : ""}${reviewNames.length ? `; optional=${reviewNames.join(", ")}` : ""}`,
        nextStep: status === "blocked" ? "Open Maintenance, fix required toolchain rows, rerun Environment Health, then return to Queue/Launch/Diagnostics." : status === "review" ? "Open Maintenance and decide whether optional toolchain warnings are acceptable for this run." : "Maintenance toolchain evidence is ready in the loaded health payload."
      });
    } else {
      rows.push({
        area: "Maintenance toolchain",
        status: "review",
        evidence: "maintenance health/toolchain evidence not loaded in this WebView session",
        nextStep: "Open Maintenance and run Environment Health before trusting long unattended processing or packaging/backfill dry runs."
      });
    }
    return rows.sort((left, right) => dependencyStatusRank(left.status) - dependencyStatusRank(right.status));
  }
  function externalDependencyOverallStatus(context = {}) {
    const rows = externalDependencyRows(context);
    if (!rows.length) return "unknown";
    if (rows.some(row => dependencyStatusLabel(row.status) === "blocked")) return "blocked";
    if (rows.some(row => dependencyStatusLabel(row.status) === "review")) return "review";
    return "ready";
  }
  function externalDependencySummaryLines(context = {}) {
    const rows = externalDependencyRows(context);
    const status = externalDependencyOverallStatus(context);
    const counts = rows.reduce((acc, row) => {
      const key = dependencyStatusLabel(row.status);
      acc[key] = (acc[key] || 0) + 1;
      return acc;
    }, {});
    const first = rows.find(row => dependencyStatusLabel(row.status) !== "ready") || rows[0];
    const lines = ["External dependency digest:", `Status: ${status}; rows=${rows.length}; blocked=${counts.blocked || 0}; review=${counts.review || 0}; ready=${counts.ready || 0}.`, "Scope: saved Settings OCR evidence, Settings raw-key action plan, Diagnostics settings handoff, and already-loaded Maintenance toolchain evidence."];
    rows.slice(0, 6).forEach(row => {
      lines.push(`- ${row.area}: ${row.status}; ${row.evidence}`);
    });
    if (rows.length > 6) lines.push(`- ${rows.length - 6} more dependency row(s).`);
    lines.push("", `Next step: ${first ? `${first.area}: ${first.nextStep}` : "Refresh Settings, Diagnostics, and Maintenance evidence."}`);
    lines.push("Real-media boundary: dependency readiness does not prove route correctness, subtitle/audio output, output size, sidecars, or pending-publish completion for a real media file.");
    lines.push("Mutation guardrail: this digest is read-only and cannot install tools, edit PATH, stage or save settings, edit secrets, run OCR, launch FFmpeg, drain publish, repair manifests, or mutate files.");
    return lines;
  }
  function externalDependencyEvidenceText(context = {}) {
    const rows = externalDependencyRows(context);
    if (!rows.length) return "external dependency evidence not loaded";
    return rows.slice(0, 4).map(row => `${row.area}=${row.status}`).join("; ");
  }
  function renderExternalDependencyDigest(context = {}) {
    const status = externalDependencyOverallStatus(context);
    setTextState("home-external-dependencies-status", status === "blocked" ? "Blocked" : status === "review" ? "Review" : status === "ready" ? "Ready" : "Unknown");
    setText("home-external-dependencies-summary", externalDependencySummaryLines(context).join("\n"));
  }
  function renderHomeAtAGlanceQueue(items = []) {
    const list = byId("home-at-a-glance-up-next");
    if (!list) return;
    list.replaceChildren();
    const rows = Array.isArray(items) ? items : [];
    if (!rows.length) {
      const empty = document.createElement("li");
      empty.textContent = "No queue items loaded.";
      list.appendChild(empty);
      return;
    }
    rows.forEach(item => {
      const li = document.createElement("li");
      const title = document.createElement("span");
      title.className = "home-up-next-title";
      const rawTitle = homeAtAGlanceQueueTitle(item);
      title.textContent = homeAtAGlanceShortValue(rawTitle, 70) || "Untitled queue item";
      if (rawTitle) title.title = rawTitle;
      const meta = document.createElement("span");
      meta.className = "home-up-next-meta";
      meta.textContent = homeAtAGlanceQueueMeta(item) || "queued";
      li.append(title, meta);
      list.appendChild(li);
    });
  }
  function renderHomeAtAGlance(context = {}) {
    const model = homeAtAGlanceModel(context);
    setTextState("home-at-a-glance-status", model.status, homeAtAGlanceStatusState(model.status));
    setText("home-at-a-glance-current", model.currentText);
    setText("home-at-a-glance-detail", model.detail);
    if (typeof renderProgressBarsInto === "function") {
      renderProgressBarsInto("home-at-a-glance-progress-bars", homeAtAGlanceProgressBar(model), context.snapshot || {}, "No active progress loaded.");
    }
    renderHomeAtAGlanceQueue(model.upcoming);
  }
  function renderDailyDriverReadiness(context = {}) {
    const rows = dailyDriverRows(context);
    setTextState("daily-driver-status", dailyDriverOverallStatus(rows));
    setText("daily-driver-summary", dailyDriverSummaryLines(rows).join("\n"));
    setText("daily-driver-legend", "Daily-driver checklist rows are read-only and do not launch, repair, drain, save, rename, or mutate files.");
    const tbody = byId("daily-driver-rows");
    if (!tbody) return;
    if (!rows.length) {
      clearRows(tbody, 4, "No daily-driver readiness rows loaded.");
      return;
    }
    tbody.replaceChildren();
    rows.forEach(item => {
      const row = document.createElement("tr");
      row.dataset.status = dailyDriverStatusClass(item.status);
      appendCells(row, [item.area, item.status, item.evidence, item.nextStep]);
      tbody.appendChild(row);
    });
  }

  /**
   * Public namespace for Home page render helpers.
   * Flat window.* exports remain owned by app.js compatibility wrappers.
   */
  window.mediaPipelineAppHome = {
    externalDependencyRows,
    externalDependencyOverallStatus,
    externalDependencySummaryLines,
    externalDependencyEvidenceText,
    renderExternalDependencyDigest,
    renderHomeAtAGlanceQueue,
    renderHomeAtAGlance,
    renderDailyDriverReadiness,
    renderHomeReadiness,
    dailyDriverRows,
    dailyDriverStatusClass,
    dailyDriverSummaryLines,
    dependencyStatusLabel,
    homeAtAGlancePercent,
    homeAtAGlanceStatusState,
    homeAtAGlanceQueueTitle,
    homeAtAGlanceQueueMeta,
    homeAtAGlanceModel,
    homeAtAGlanceProgressBar,
    renderHomePendingCount,
    renderHomeNetworkRole,
    renderHomeQueueSnapshot,
    renderHomeRecentCompleted,
    homePromotionRunActive,
    renderHomePromotionEntry
  };
})();
