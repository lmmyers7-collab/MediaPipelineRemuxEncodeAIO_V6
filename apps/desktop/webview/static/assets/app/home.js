/* global commandHistoryIssueLevel, getCommandHistory, lastRefreshCompletedAt, lastRefreshDurationMs, refreshTimeLabel, renderProgressBarsInto, settingsOperatorTrustStatus, settingsRawActionPlanRows, settingsRawActionPlanStatus, shortenPath */
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

  function setHomePanelStatus(id, message, state) {
    if (typeof setPanelStatus === "function") return setPanelStatus(id, message, state);
    if (typeof setTextState === "function") {
      setTextState(id, message, state);
      return state || "";
    }
    setText(id, message);
    return state || "";
  }

  function homePanelStateFromStatus(value) {
    const text = String(value || "").trim().toLowerCase();
    if (!text || text === "no data" || text === "not loaded" || text.startsWith("no ")) return "empty";
    if (text.includes("block") || text.includes("fail") || text.includes("error")) return "blocked";
    if (text.includes("review") || text.includes("warning") || text.includes("limited") || text.includes("unknown")) return "warning";
    if (text.includes("active") || text.includes("running") || text.includes("check")) return "loading";
    if (text.includes("ready") || text.includes("ok") || text.includes("item") || text.includes("total")) return "ready";
    return "unknown";
  }

  function selectHomeListItem(item) {
    const siblings = Array.from(item?.parentElement?.children || []);
    siblings.forEach((candidate) => {
      const selected = candidate === item;
      candidate.classList.toggle("is-selected", selected);
      candidate.setAttribute("aria-selected", selected ? "true" : "false");
    });
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
    setHomePanelStatus("home-readiness-status", status, status === "Ready" ? "ok" : status === "Checking" ? "loading" : status === "Backend issue" ? "blocked" : "warning");
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

  function homeNetworkDriftPayload(networkWorkers = {}) {
    const drift = networkWorkers?.running_vs_saved;
    return drift && typeof drift === "object" ? drift : {};
  }

  function homeNetworkDriftFieldsText(drift = {}) {
    const labels = Array.isArray(drift.drift_field_labels) ? drift.drift_field_labels : [];
    const fields = Array.isArray(drift.drift_fields) ? drift.drift_fields : [];
    const values = (labels.length ? labels : fields)
      .map((item) => String(item || "").trim())
      .filter(Boolean);
    return values.length ? values.join(", ") : "none";
  }

  function homeNetworkPolicyDivergencePayload(drift = {}) {
    const payload = drift?.policy_divergence;
    return payload && typeof payload === "object" ? payload : {};
  }

  function homeNetworkPolicyDivergenceFieldsText(drift = {}) {
    const payload = homeNetworkPolicyDivergencePayload(drift);
    const labels = Array.isArray(payload.field_labels) ? payload.field_labels : [];
    const fields = Array.isArray(payload.fields) ? payload.fields : [];
    const values = (labels.length ? labels : fields)
      .map((item) => String(item || "").trim())
      .filter(Boolean);
    return values.length ? values.join(", ") : "none";
  }

  function homeNetworkPolicyDivergenceStatusText(drift = {}) {
    const payload = homeNetworkPolicyDivergencePayload(drift);
    const status = String(payload.status || "not_loaded").trim().toLowerCase();
    if (status === "review") return `review (${homeNetworkPolicyDivergenceFieldsText(drift)})`;
    if (status === "ready") return "ready";
    return status || "not loaded";
  }

  function homeNetworkPolicyDivergenceActive(drift = {}) {
    return String(homeNetworkPolicyDivergencePayload(drift).status || "").trim().toLowerCase() === "review";
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
      `rows=${Array.isArray(queue.rows) ? queue.rows.length : 0}; runnable=${dailyDriverCount(Object.prototype.hasOwnProperty.call(queue, "runnable_count") ? queue.runnable_count : (Array.isArray(queue.rows) ? queue.rows.length : 0))}; stale=${queue.snapshot_file_freshness_status || "unknown"}; blocked=${dailyDriverCount(queue.blocked_row_count)}; invalid=${dailyDriverCount(queue.invalid_row_count)}`,
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
    const workerDrift = homeNetworkDriftPayload(networkWorkers);
    const workerDriftStatus = String(workerDrift.status || "not_loaded").toLowerCase();
    const workerDriftActive = workerDriftStatus === "drift";
    const workerDriftFields = homeNetworkDriftFieldsText(workerDrift);
    const workerPolicyReviewActive = homeNetworkPolicyDivergenceActive(workerDrift);
    const workerPolicyStatus = homeNetworkPolicyDivergenceStatusText(workerDrift);
    const workerPolicyFields = homeNetworkPolicyDivergenceFieldsText(workerDrift);
    rows.push(dailyDriverRow(
      "Network visibility",
      workerDriftActive || workerPolicyReviewActive || (role && role !== "standalone") ? "review" : "ready",
      `role=${role}; persisted worker rows=${workerRows}; running_vs_saved=${workerDriftStatus}; drift_fields=${workerDriftFields}; policy_authority=${workerPolicyStatus}`,
      workerDriftActive
        ? `Open Network Workers and restart worker polling so the live dispatcher uses saved settings (${workerDriftFields}).`
        : workerPolicyReviewActive
        ? `Open Network Workers and decide WorkerHonorCoordinatorPolicy plus WorkerEncoderMap before policy-authoritative network claims (${workerPolicyFields}).`
        : role && role !== "standalone"
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

  function homeProgressPercent(value) {
    const number = Number(value);
    if (!Number.isFinite(number)) return "";
    const bounded = Math.max(0, Math.min(100, number));
    return `${bounded.toFixed(bounded % 1 ? 1 : 0)}%`;
  }

  function homeCompactShortValue(value, maxChars = 64) {
    const text = formatProgressValue(value || "");
    if (!text) return "";
    if (typeof shortenPath === "function") return shortenPath(text, maxChars);
    return text.length > maxChars ? `...${text.slice(-(maxChars - 3))}` : text;
  }

  function homeQueueLeaf(value) {
    const text = String(value || "").trim();
    if (!text) return "";
    const parts = text.split(/[\\/]+/);
    return parts[parts.length - 1] || text;
  }

  function homeQueuePathSegments(value) {
    return String(value || "")
      .replace(/\\/g, "/")
      .split("/")
      .map((part) => part.trim())
      .filter(Boolean);
  }

  function homeQueueStem(value) {
    return String(value || "").trim().replace(/\.[A-Za-z0-9]{2,5}$/, "").trim();
  }

  function homeQueueNumberToken(value) {
    const match = String(value ?? "").match(/\d{1,3}/);
    return match ? Number(match[0]) : 0;
  }

  function homeQueueSeasonEpisodeFromText(value) {
    const match = homeQueueStem(value).match(/\bS(?<season>\d{1,2})E(?<episode>\d{1,3})(?:[-_]?E\d{1,3})?\b/i);
    if (!match?.groups) return "";
    const season = Number(match.groups.season);
    const episode = Number(match.groups.episode);
    if (!Number.isFinite(season) || !Number.isFinite(episode) || episode <= 0) return "";
    return `S${String(season).padStart(2, "0")}E${String(episode).padStart(2, "0")}`;
  }

  function homeQueueSeasonEpisodeCode(item = {}) {
    const seasonValue = item.season_number ?? item.season ?? item.season_value;
    const episodeValue = item.episode_number ?? item.episode ?? item.start_episode ?? item.start_episode_value;
    const hasSeasonValue = seasonValue !== undefined && seasonValue !== null && String(seasonValue).trim() !== "";
    const hasEpisodeValue = episodeValue !== undefined && episodeValue !== null && String(episodeValue).trim() !== "";
    const season = homeQueueNumberToken(seasonValue);
    const episode = homeQueueNumberToken(episodeValue);
    if (hasSeasonValue && hasEpisodeValue && Number.isFinite(season) && Number.isFinite(episode) && episode > 0) {
      return `S${String(season).padStart(2, "0")}E${String(episode).padStart(2, "0")}`;
    }
    return [
      item.display_name,
      item.lookup_title,
      item.title,
      item.relative_path,
      item.source_path,
      item.source_file_name,
      item.source_file,
      item.path,
      item.input_path,
      item.file,
    ].map(homeQueueSeasonEpisodeFromText).find(Boolean) || "";
  }

  function homeQueueLooksTv(item = {}) {
    const mediaType = String(item.media_type || item.media_kind || item.phase || "").trim().toLowerCase();
    const haystack = [
      item.display_name,
      item.lookup_title,
      item.title,
      item.relative_path,
      item.source_path,
      item.source_file_name,
      item.source_file,
      item.path,
      item.input_path,
      item.file,
    ].join(" ");
    return mediaType.includes("tv")
      || mediaType.includes("show")
      || mediaType.includes("episode")
      || Boolean(homeQueueSeasonEpisodeCode(item))
      || /(?:^|[\\/])season\s*\d{1,2}(?:[\\/]|$)/i.test(haystack);
  }

  function homeQueueRejectSeriesLabel(value) {
    const text = String(value || "").trim();
    return !text
      || /^(?:tv|tv safe|shows?|episodes?|movies?|source|sources|outsource|videos?|media|season\s*\d{1,2}|s\d{1,2})$/i.test(text);
  }

  function homeQueueSeriesCandidateFromText(value) {
    let text = homeQueueStem(value).replace(/[._]+/g, " ").replace(/\s+/g, " ").trim();
    if (!text) return "";
    const episodeMatch = text.match(/\bS\d{1,2}E\d{1,3}(?:[-_]?E\d{1,3})?\b/i);
    if (episodeMatch) text = text.slice(0, episodeMatch.index).replace(/[\s._-]+$/g, "").trim();
    text = text.replace(/\s*\((?:season\s*|s)\d{1,2}\)\s*$/i, "").trim();
    return homeQueueRejectSeriesLabel(text) ? "" : text;
  }

  function homeQueueSeriesCandidateFromPath(value) {
    const parts = homeQueuePathSegments(value).filter((part) => !/^[A-Za-z]:$/.test(part));
    if (parts.length < 2) return "";
    for (let index = parts.length - 2; index >= 1; index -= 1) {
      if (/^(?:season\s*\d{1,2}|s\d{1,2})$/i.test(parts[index])) {
        const candidate = homeQueueSeriesCandidateFromText(parts[index - 1]);
        if (candidate) return candidate;
      }
    }
    const parent = homeQueueSeriesCandidateFromText(parts[parts.length - 2]);
    return parent || "";
  }

  // Release-style movie filenames ("Hoppers.2026.2160p.WEB-DL...") collapse to
  // "Title (Year)". Picks the release year (a 1900-2099 token that is
  // parenthesized, last, or immediately followed by a quality/source tag) so a
  // year inside the title (e.g. "Blade Runner 2049 2017") is not mistaken for it.
  function homeMovieTitleYear(value) {
    let text = String(value || "").trim();
    if (!text) return "";
    text = text.replace(/\.(mkv|mp4|m4v|avi|mov|ts|webm)$/i, "");
    const spaced = text.replace(/[._]+/g, " ").replace(/\s+/g, " ").trim();
    const junk = /^(480p|576p|720p|1080p|2160p|4k|uhd|web|webdl|web-dl|webrip|web-rip|bluray|blu-ray|brrip|bdrip|hdrip|dvdrip|remux|remaster|remastered|unrated|extended|proper|repack|imax|hdr|hdr10|dv|dovi|hevc|avc|x264|x265|h264|h265|10bit|8bit|aac|ac3|eac3|dd5|ddp5|dts|atmos|truehd|flac|dual|multi)$/i;
    const tokens = spaced.split(" ");
    const yearRe = /^\(?((?:19|20)\d{2})\)?$/;
    for (let i = 0; i < tokens.length; i += 1) {
      const match = tokens[i].match(yearRe);
      if (!match) continue;
      const parenthesized = /^\(.*\)$/.test(tokens[i]);
      const next = (tokens[i + 1] || "").replace(/[()]/g, "");
      if (parenthesized || i === tokens.length - 1 || junk.test(next)) {
        const title = tokens.slice(0, i).join(" ").replace(/[\s-]+$/g, "").trim();
        if (title) return `${title} (${match[1]})`;
        break;
      }
    }
    return spaced;
  }

  function homeNormalizeQueueTitle(rawValue, item = {}) {
    const raw = String(rawValue || "").trim();
    if (!raw) return "";
    const mediaType = String(item.media_type || item.media_kind || "").trim().toLowerCase();
    if (mediaType === "movie" || mediaType === "movies") {
      const leaf = homeQueueLeaf(raw);
      return homeMovieTitleYear(leaf) || leaf;
    }
    return raw;
  }

  function homeQueueTitle(item = {}) {
    const raw = item.lookup_title
      || item.display_name
      || item.title
      || item.source_file_name
      || item.source_file
      || item.source_path
      || item.path
      || item.input_path
      || item.file
      || "";
    return homeNormalizeQueueTitle(raw, item);
  }

  function homeQueueDisplayLabel(item = {}) {
    const rawTitle = homeQueueTitle(item);
    if (!homeQueueLooksTv(item)) {
      return {
        main: rawTitle || "Untitled queue item",
        episode: "",
        accessibleText: rawTitle || "Untitled queue item",
      };
    }
    const episode = homeQueueSeasonEpisodeCode(item);
    const series = [
      item.show_name,
      item.series_name,
      item.series_title,
      item.show_title,
      homeQueueSeriesCandidateFromPath(item.relative_path),
      homeQueueSeriesCandidateFromPath(item.source_path),
      homeQueueSeriesCandidateFromPath(item.path),
      homeQueueSeriesCandidateFromText(item.lookup_title),
      homeQueueSeriesCandidateFromText(item.display_name),
      homeQueueSeriesCandidateFromText(item.title),
      homeQueueSeriesCandidateFromText(item.source_file_name),
      homeQueueSeriesCandidateFromText(item.source_file),
      homeQueueSeriesCandidateFromText(rawTitle),
    ].map((value) => homeQueueSeriesCandidateFromText(value)).find(Boolean);
    const main = series || "TV series";
    return {
      main,
      episode,
      accessibleText: [main, episode].filter(Boolean).join(" "),
    };
  }

  function homeQueueRoute(item = {}) {
    const route = formatProgressValue(item.route_name || item.route || item.mode || "");
    if (/remux/i.test(route) && /codec check pending/i.test(route)) return "REMUX";
    return /^[a-z_]+$/.test(route) ? route.replace(/_/g, " ").toUpperCase() : route;
  }

  function homeQueueMeta(item = {}) {
    return [
      homeQueueRoute(item),
      item.operator_status || item.status || item.decision || "",
      item.queue_position || (item.queue_index || item.queue_total ? `${item.queue_index || "?"}/${item.queue_total || "?"}` : ""),
    ].filter(Boolean).map(formatProgressValue).join(" · ");
  }

  function homeQueueDetailLines(item = {}) {
    const route = homeQueueRoute(item) || "route not reported";
    const status = formatProgressValue(item.operator_status || item.status || item.decision || "unknown");
    const source = homeCompactShortValue(item.source_path || item.path || item.input_path || item.file || "", 120) || "source path not loaded";
    const output = homeCompactShortValue(item.output_path || item.library_output_root || item.destination_path || "", 120) || "output evidence not loaded";
    const label = homeQueueDisplayLabel(item);
    return [
      `Selected queue item: ${label.accessibleText || "Untitled queue item"}`,
      `Route/status: ${route}; ${status}.`,
      `Source: ${source}`,
      `Output evidence: ${output}`,
      "Safe next step: open Queue for full backend-owned row evidence before launching or rerunning.",
    ];
  }

  function homeQueueRowIsRunnable(item = {}) {
    const status = String(item.operator_status || "").trim().toLowerCase();
    return status === "ready" || status === "priority ready";
  }

  function homeQueueGlobalOrder(item = {}) {
    const value = Number(item.global_order);
    return Number.isFinite(value) ? value : 0;
  }

  function homeQueueSourceKey(value) {
    return String(value || "").trim().replace(/[\\/]+/g, "/").toLowerCase();
  }

  // Live processing position as a 1-based global order. The queue snapshot is the
  // full static plan in execution order (global_order 1..N), so the panel must
  // skip everything up to the current point; otherwise it shows already-finished
  // items. Resolution order:
  //   1. Anchor to the file currently being processed (exact global_order).
  //   2. Otherwise max(CurrentQueueIndex, TotalProcessed). CurrentQueueIndex
  //      resets to 0 between items while TotalProcessed (counts.processed) does
  //      not, so max() keeps the panel from reverting to finished items in the gap.
  function homeCurrentQueueOrder(context = {}, rows = []) {
    const snapshot = context && typeof context.snapshot === "object" ? context.snapshot : {};
    const counts = snapshot && typeof snapshot.counts === "object" ? snapshot.counts : {};
    const progress = snapshot && typeof snapshot.progress === "object" ? snapshot.progress : {};
    const currentKey = homeQueueSourceKey(progress.CurrentFilePath || progress.current_file_path || progress.CurrentFile);
    if (currentKey) {
      const list = Array.isArray(rows) ? rows : [];
      const match = list.find((item) => item && homeQueueSourceKey(item.source_path) === currentKey);
      const matchOrder = match ? homeQueueGlobalOrder(match) : 0;
      if (matchOrder > 0) return matchOrder;
    }
    const index = Math.trunc(Number(counts.queue_index) || 0);
    const processed = Math.trunc(Number(counts.processed) || 0);
    return Math.max(index > 0 ? index : 0, processed > 0 ? processed : 0);
  }

  function homeNextQueueRows(queue = {}, currentOrder = 0) {
    const rows = Array.isArray(queue.rows) ? queue.rows.filter(Boolean) : [];
    const runnable = rows.filter(homeQueueRowIsRunnable);
    const cutoff = Math.trunc(Number(currentOrder) || 0);
    if (cutoff > 0) {
      // Genuinely upcoming items sit after the live position in global order.
      const upcoming = runnable
        .filter((item) => homeQueueGlobalOrder(item) > cutoff)
        .sort((left, right) => homeQueueGlobalOrder(left) - homeQueueGlobalOrder(right));
      // Only apply the offset when it yields rows. If nothing is upcoming (run
      // near its end, or a payload without global_order), fall back to the first
      // runnable rows so the panel never blanks out.
      if (upcoming.length) return upcoming.slice(0, 5);
    }
    return runnable.slice(0, 5);
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

  function homeStorageRows(settings = {}) {
    const pathHealth = settings?.path_health && typeof settings.path_health === "object" ? settings.path_health : {};
    return Array.isArray(pathHealth.rows) ? pathHealth.rows.filter(Boolean) : [];
  }

  function normalizeStoragePath(value) {
    return String(value || "").trim().replace(/[\\/]+$/g, "").replace(/\\/g, "/").toLowerCase();
  }

  function homeStoragePath(row = {}) {
    return String(row?.path || row?.storage_probe?.path || "").trim();
  }

  function homeStorageRowForPath(settings = {}, pathValue = "", role = "") {
    const target = normalizeStoragePath(pathValue);
    if (!target) return null;
    const normalizedRole = String(role || "").toLowerCase();
    return homeStorageRows(settings).find((row) => {
      const rowRole = String(row?.role || "").toLowerCase();
      const rowPath = normalizeStoragePath(homeStoragePath(row));
      return (!normalizedRole || rowRole === normalizedRole) && rowPath && (target === rowPath || target.startsWith(`${rowPath}/`));
    }) || null;
  }

  function homeFirstStorageRow(settings = {}, role = "", keys = []) {
    const normalizedRole = String(role || "").toLowerCase();
    const normalizedKeys = keys.map((key) => String(key || "").toLowerCase()).filter(Boolean);
    const rows = homeStorageRows(settings);
    return rows.find((row) => normalizedKeys.includes(String(row?.key || "").toLowerCase()))
      || rows.find((row) => String(row?.role || "").toLowerCase() === normalizedRole)
      || null;
  }

  function homeActiveOutputPath(context = {}) {
    const progress = context?.snapshot?.progress && typeof context.snapshot.progress === "object" ? context.snapshot.progress : {};
    const activeOutput = String(progress.CurrentLibraryOutputRoot || progress.current_library_output_root || "").trim();
    if (activeOutput) return activeOutput;
    const rows = Array.isArray(context?.queue?.rows) ? context.queue.rows : [];
    const queueRow = rows.find((row) => String(row?.library_output_root || "").trim());
    if (queueRow) return String(queueRow.library_output_root || "").trim();
    const settingsOutput = String(context?.settings?.config?.Outsource || "").trim();
    return settingsOutput;
  }

  function homeStorageUnknownRow(label, pathValue, message) {
    return {
      label,
      role: "",
      path: pathValue || "",
      storage_status: "unknown",
      storage_status_state: "warning",
      free_space_gb: null,
      total_space_gb: null,
      reserve_gb: null,
      storage_probe: {
        status: "unknown",
        status_state: "warning",
        message,
        free_gb: null,
        total_gb: null,
        reserve_gb: null,
      },
    };
  }

  function homeScratchStorageRow(context = {}) {
    return homeFirstStorageRow(context.settings || {}, "scratch", ["local_base"])
      || homeStorageUnknownRow("LocalBase scratch/state root", "", "No scratch storage evidence was loaded from backend path health.");
  }

  function homeOutputStorageRow(context = {}) {
    const settings = context.settings || {};
    const activeOutput = homeActiveOutputPath(context);
    if (activeOutput) {
      return homeStorageRowForPath(settings, activeOutput, "output")
        || homeStorageUnknownRow("Active library output root", activeOutput, "Active library output was not present in backend path-health evidence.");
    }
    return homeFirstStorageRow(settings, "output", ["outsource"])
      || homeStorageUnknownRow("Library output root", "", "No output storage evidence was loaded from backend path health.");
  }

  function homeStorageNumber(value) {
    const number = Number(value);
    return Number.isFinite(number) ? number : null;
  }

  function homeStorageStatus(row = {}) {
    const probe = row?.storage_probe && typeof row.storage_probe === "object" ? row.storage_probe : {};
    const status = String(row.storage_status || probe.status || "").toLowerCase();
    if (status === "ready") return { text: "OK", state: "ok" };
    if (status === "low") return { text: "Low", state: "blocked" };
    if (status === "blocked") return { text: "Blocked", state: "blocked" };
    if (status === "unknown") return { text: "Unknown", state: "warning" };
    return { text: "Not checked", state: "empty" };
  }

  function homeStorageGbText(value) {
    const number = homeStorageNumber(value);
    if (number === null) return "";
    return `${number.toFixed(number % 1 ? 1 : 0)} GB`;
  }

  function homeStorageDetail(row = {}) {
    const probe = row?.storage_probe && typeof row.storage_probe === "object" ? row.storage_probe : {};
    const free = homeStorageGbText(row.free_space_gb ?? probe.free_gb);
    const reserve = homeStorageGbText(row.reserve_gb ?? probe.reserve_gb);
    const message = String(probe.message || row.message || "").trim();
    if (free && reserve) return `${free} free / ${reserve} reserve`;
    if (free) return `${free} free`;
    return message || "No free-space evidence loaded.";
  }

  function setHomeStorageMetric(statusId, detailId, row = {}) {
    const status = homeStorageStatus(row);
    setTextState(statusId, status.text, status.state);
    const detail = byId(detailId);
    if (!detail) return;
    detail.textContent = homeStorageDetail(row);
    detail.title = [
      row.label || "",
      homeStoragePath(row) || "",
      row?.storage_probe?.message || row.message || "",
    ].filter(Boolean).join("\n");
  }

  function renderHomeStorageHealth(context = {}) {
    setHomeStorageMetric("home-scratch-storage-status", "home-scratch-storage-detail", homeScratchStorageRow(context));
    setHomeStorageMetric("home-output-storage-status", "home-output-storage-detail", homeOutputStorageRow(context));
  }

  function renderHomeQueueSnapshot(queue) {
    queue = queue && typeof queue === "object" ? queue : {};
    const rows = Array.isArray(queue.rows) ? queue.rows : [];
    const runnable = queue.runnable_count !== undefined ? queue.runnable_count : rows.length;
    const blocked = queue.blocked_row_count || 0;
    const priority = queue.priority_count || rows.filter((r) => r?.is_priority).length || 0;
    const encodeRows = rows.filter((r) => String(r?.route_name || "").toLowerCase().includes("encode")).length;
    const remuxRows = rows.filter((r) => String(r?.route_name || "").toLowerCase().includes("remux")).length;
    const lines = [
      `Rows: ${rows.length} | Runnable: ${runnable} | Blocked: ${blocked}`,
      priority ? `Priority: ${priority}` : "",
      encodeRows || remuxRows ? `Route mix: ${encodeRows} encode / ${remuxRows} remux` : "",
      queue.error ? `Error: ${queue.error}` : "",
      ...(Array.isArray(queue.warnings) ? queue.warnings.slice(0, 2) : []),
    ].filter(Boolean);
    setHomePanelStatus("home-queue-snapshot-status", rows.length ? `${rows.length} items` : "Empty", rows.length ? "ready" : "empty");
    const pre = byId("home-queue-snapshot");
    if (pre) pre.textContent = lines.join("\n") || "No queue data loaded.";
  }

  function homeCompletedText(value) {
    return String(value ?? "").trim();
  }

  function homeCompletedPathSegments(value) {
    return homeCompletedText(value).replace(/\\/g, "/").split("/").map((part) => part.trim()).filter(Boolean);
  }

  function homeCompletedPathLeaf(value) {
    const parts = homeCompletedPathSegments(value);
    return parts.length ? parts[parts.length - 1] : homeCompletedText(value);
  }

  function homeCompletedStem(value) {
    return homeCompletedText(value).replace(/\.[A-Za-z0-9]{2,5}$/, "").trim();
  }

  function homeCompletedSeasonOnlyText(value) {
    const text = homeCompletedStem(value);
    return /^(?:season\s*\d{1,2}|s\d{1,2})(?:\s*\((?:season\s*|s)\d{1,2}\))?$/i.test(text)
      || /^(?:tv|show|episode)\s*\((?:season\s*|s)\d{1,2}\)$/i.test(text);
  }

  function homeCompletedLooksTv(row = {}) {
    const mediaType = homeCompletedText(row.media_type).toLowerCase();
    const lookup = homeCompletedText(row.lookup_title);
    const haystack = [
      row.relative_path,
      row.output_file,
      row.output_path,
      row.source_path,
      lookup,
    ].map(homeCompletedText).join(" ");
    return mediaType.includes("tv")
      || mediaType.includes("episode")
      || /\bs\d{1,2}e\d{1,3}\b/i.test(haystack)
      || /(?:^|[\\/])season\s*\d{1,2}(?:[\\/]|$)/i.test(haystack)
      || homeCompletedSeasonOnlyText(lookup);
  }

  function homeCompletedUnique(values) {
    const seen = new Set();
    const result = [];
    values.map(homeCompletedText).filter(Boolean).forEach((value) => {
      const key = value.toLowerCase();
      if (seen.has(key)) return;
      seen.add(key);
      result.push(value);
    });
    return result;
  }

  function homeCompletedSpecificFileLabel(row = {}) {
    const candidates = homeCompletedUnique([
      row.output_file,
      homeCompletedPathLeaf(row.output_path),
      homeCompletedPathLeaf(row.source_path),
      homeCompletedPathLeaf(row.relative_path),
      row.output_path,
      row.source_path,
      row.relative_path,
    ]);
    if (!candidates.length) return "";
    const episodeCandidate = candidates.find((value) => /\bs\d{1,2}e\d{1,3}\b/i.test(value));
    if (episodeCandidate) return episodeCandidate;
    const concrete = candidates.find((value) => !homeCompletedSeasonOnlyText(value));
    return concrete || candidates[0];
  }

  function homeCompletedParentContext(row = {}) {
    const candidates = [row.relative_path, row.output_path, row.source_path];
    for (const candidate of candidates) {
      const parts = homeCompletedPathSegments(candidate);
      if (parts.length <= 1) continue;
      const contextParts = parts.slice(0, -1).filter((part) => !/^[A-Za-z]:$/.test(part));
      if (!contextParts.length) continue;
      return contextParts.slice(-2).join(" / ");
    }
    return "";
  }

  function homeCompletedRouteLabel(row = {}) {
    const raw = homeCompletedText(row.route_label || row.route_name || row.route || row.mode);
    if (!raw) return "-";
    const normalized = raw.toLowerCase();
    if (normalized === "remux") return "REMUX";
    if (normalized === "encode") return "ENCODE";
    return raw;
  }

  function homeCompletedRowModel(row = {}) {
    const lookupTitle = homeCompletedText(row.lookup_title);
    const outputFile = homeCompletedText(row.output_file || homeCompletedPathLeaf(row.output_path));
    const specificFile = homeCompletedSpecificFileLabel(row);
    const isTv = homeCompletedLooksTv(row);
    const titleRaw = isTv
      ? (specificFile || outputFile || lookupTitle || row.output_path || row.source_path || "-")
      : (lookupTitle || outputFile || row.output_path || row.source_path || "-");
    const parentContext = homeCompletedParentContext(row);
    const metaCandidates = isTv
      ? [parentContext, lookupTitle]
      : [outputFile && outputFile !== titleRaw ? outputFile : ""];
    const metaDisplay = homeCompletedUnique(metaCandidates)
      .find((value) => value && value.toLowerCase() !== homeCompletedText(titleRaw).toLowerCase()) || "";
    const tooltip = homeCompletedUnique([
      lookupTitle ? `Title: ${lookupTitle}` : "",
      row.relative_path ? `Relative: ${row.relative_path}` : "",
      row.output_path ? `Output: ${row.output_path}` : "",
      row.source_path ? `Source: ${row.source_path}` : "",
    ]).join("\n");
    return {
      titleDisplay: homeCompactShortValue(titleRaw, 96) || "-",
      metaDisplay: homeCompactShortValue(metaDisplay, 96),
      tooltip: tooltip || homeCompletedText(titleRaw),
    };
  }

  function renderHomeCompletedFileCell(cell, model) {
    if (!cell) return;
    cell.textContent = "";
    cell.classList.add("home-completed-file-cell");
    const title = document.createElement("span");
    title.className = "home-completed-title-main";
    title.textContent = model.titleDisplay;
    cell.appendChild(title);
    if (model.metaDisplay) {
      const meta = document.createElement("span");
      meta.className = "home-completed-title-meta";
      meta.textContent = model.metaDisplay;
      cell.appendChild(meta);
    }
    if (model.tooltip) cell.title = model.tooltip;
  }

  function renderHomeRecentCompleted(completed) {
    completed = completed && typeof completed === "object" ? completed : {};
    const rows = Array.isArray(completed.rows) ? completed.rows : [];
    const tbody = byId("home-recent-completed-tbody");
    if (!tbody) return;
    setHomePanelStatus("home-recent-completed-status", rows.length ? `${completed.count || rows.length} total` : "No data", rows.length ? "ready" : "empty");
    tbody.textContent = "";
    const recent = rows.slice(0, 5);
    if (!recent.length) {
      const tr = document.createElement("tr");
      if (typeof appendCells === "function") appendCells(tr, ["No completed files loaded.", "", ""]);
      tbody.appendChild(tr);
      setText("home-recent-completed-detail", "No completed output rows loaded. Run the pipeline or refresh Completed evidence.");
      return;
    }
    recent.forEach((row) => {
      const model = homeCompletedRowModel(row);
      const route = homeCompletedRouteLabel(row);
      const finished = homeCompletedText(row.completed_at || row.manifest_recorded_at) || "-";
      const tr = document.createElement("tr");
      tr.dataset.status = "completed";
      if (typeof appendCells === "function") appendCells(tr, [model.titleDisplay, route, finished]);
      renderHomeCompletedFileCell(tr.cells[0], model);
      if (typeof makeRowSelectable === "function") {
        makeRowSelectable(tr, () => setText("home-recent-completed-detail", homeRecentCompletedDetailLines(row, model).join("\n")), {
          selected: recent.indexOf(row) === 0,
          label: `Review completed output ${model.titleDisplay || recent.indexOf(row) + 1}`,
        });
      }
      tbody.appendChild(tr);
    });
    setText("home-recent-completed-detail", homeRecentCompletedDetailLines(recent[0], homeCompletedRowModel(recent[0])).join("\n"));
  }

  function homeRecentCompletedDetailLines(row = {}, model = homeCompletedRowModel(row)) {
    const route = homeCompletedRouteLabel(row);
    const finished = homeCompletedText(row.completed_at || row.manifest_recorded_at) || "finish time not loaded";
    const output = homeCompactShortValue(row.output_path || row.output_file || row.relative_path || "", 120) || "output path not loaded";
    const source = homeCompactShortValue(row.source_path || "", 120) || "source evidence not loaded";
    return [
      `Selected completed output: ${model.titleDisplay || "Untitled output"}`,
      `Route/finished: ${route}; ${finished}.`,
      `Output: ${output}`,
      `Source: ${source}`,
      "Safe next step: open Completed for sidecar, pending-publish, diagnostics, and acceptance evidence before trusting output.",
    ];
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
    const message = !enabled
      ? "Completed Output unavailable: Final Library Promotion is disabled in Settings."
      : active
        ? "Completed Output unavailable: a final-library promotion run is already active."
        : eligible > 0
          ? `Completed Output ready: ${eligible} reviewed file${eligible === 1 ? "" : "s"} eligible for promotion review.`
          : "Completed Output unavailable: no reviewed files are currently eligible for final-library promotion.";
    buttons.forEach((button) => {
      button.disabled = disabled;
      button.setAttribute("aria-disabled", String(disabled));
      button.textContent = "Open Completed Output";
      button.title = title;
    });
    setText("home-promotion-entry-message", message);
  }

  function externalDependencyRows(context = {}) {
    const payload = context || {};
    const settings = payload.settings || {};
    const stateSummary = payload.stateSummary || payload.diagnosticsStateSummary || {};
    const maintenance = payload.maintenance || window.mediaPipelineMaintenanceView?.getLastMaintenance?.() || {};
    const rows = [];
    const bdpgs = settings?.tool_path_evidence?.bdpgs_ocr;
    if (bdpgs && typeof bdpgs === "object") {
      const status = dependencyStatusLabel(bdpgs.operator_status || (bdpgs.enabled ? "unknown" : "ready"));
      const attention = Boolean(bdpgs.enabled) && status !== "ready";
      rows.push({
        area: "Settings BDPGS OCR paths",
        status: attention ? status : "ready",
        evidence: `enabled=${bdpgs.enabled ? "yes" : "no"}; blocked=${bdpgs.blocked_count || 0}; review=${bdpgs.review_count || 0}`,
        nextStep: attention ? "Open Settings > Media Output and fix saved OCR tool/tessdata path evidence or disable OCR intentionally before rerunning PGS subtitle conversion." : "Saved BDPGS OCR path evidence is not blocking in the loaded Settings payload."
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
        nextStep: attention ? "Open Settings > Media Output and fix saved Subtitle Edit/Tesseract path evidence or disable OCR intentionally before rerunning VobSub subtitle conversion." : "Saved VobSub OCR path evidence is not blocking in the loaded Settings payload."
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
        nextStep: "Use Diagnostics State Artifact Summary read order, then return to Settings > Media Output before rerun or manual-review decisions."
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
          nextStep: blockedRows.length ? "Open Settings > Raw-key action plan before save, launch, rerun, or OCR decisions; schema drift and blocked raw keys need backend Save evidence." : highRows.length ? "Open Settings > Raw-key action plan and verify OCR path evidence or advanced settings before unattended processing." : "Raw-key action plan has no blocking/high-review row in the loaded Settings workspace; subtitle keyword builder coverage and auth-token exclusions remain read-only guidance."
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
    setHomePanelStatus("home-external-dependencies-status", status === "blocked" ? "Blocked" : status === "review" ? "Review" : status === "ready" ? "Ready" : "Unknown", dependencyStatusLabel(status) === "blocked" ? "blocked" : dependencyStatusLabel(status) === "review" ? "warning" : "ready");
    setText("home-external-dependencies-summary", externalDependencySummaryLines(context).join("\n"));
  }
  function renderHomeNextQueue(context = {}) {
    const queue = context?.queue && typeof context.queue === "object" ? context.queue : {};
    const list = byId("home-next-queue-list");
    if (!list) return;
    list.setAttribute("role", "listbox");
    list.replaceChildren();
    const rows = homeNextQueueRows(queue, homeCurrentQueueOrder(context, queue.rows));
    setHomePanelStatus("home-next-queue-status", rows.length ? `${rows.length} ready` : "No runnable", rows.length ? "ready" : "empty");
    if (!rows.length) {
      const empty = document.createElement("li");
      empty.textContent = "No runnable queue items loaded.";
      list.appendChild(empty);
      setText("home-next-queue-detail", "No runnable queue items loaded. Open Queue for the full backend-owned snapshot.");
      return;
    }
    rows.forEach((item, index) => {
      const li = document.createElement("li");
      li.tabIndex = 0;
      li.setAttribute("role", "option");
      li.setAttribute("aria-selected", index === 0 ? "true" : "false");
      li.classList.toggle("is-selected", index === 0);
      const label = homeQueueDisplayLabel(item);
      li.setAttribute("aria-label", `Review queue item ${label.accessibleText || index + 1}`);
      const title = document.createElement("span");
      title.className = "home-next-queue-title";
      const titleMain = document.createElement("span");
      titleMain.className = "home-next-queue-title-main";
      titleMain.textContent = label.main || "Untitled queue item";
      title.appendChild(titleMain);
      if (label.episode) {
        const episode = document.createElement("span");
        episode.className = "home-next-queue-episode";
        episode.textContent = label.episode;
        title.appendChild(episode);
      }
      title.title = label.accessibleText || "";
      const meta = document.createElement("span");
      meta.className = "home-next-queue-meta";
      meta.textContent = homeQueueMeta(item) || "queued";
      li.append(title, meta);
      const activate = () => {
        selectHomeListItem(li);
        setText("home-next-queue-detail", homeQueueDetailLines(item).join("\n"));
      };
      li.addEventListener("click", activate);
      li.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          activate();
        }
      });
      list.appendChild(li);
    });
    setText("home-next-queue-detail", homeQueueDetailLines(rows[0]).join("\n"));
  }
  function renderDailyDriverReadiness(context = {}) {
    const rows = dailyDriverRows(context);
    const overall = dailyDriverOverallStatus(rows);
    setHomePanelStatus("daily-driver-status", overall, homePanelStateFromStatus(overall));
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
    renderHomeNextQueue,
    renderDailyDriverReadiness,
    renderHomeReadiness,
    dailyDriverRows,
    dailyDriverStatusClass,
    dailyDriverSummaryLines,
    dependencyStatusLabel,
    homeProgressPercent,
    homeQueueTitle,
    homeNormalizeQueueTitle,
    homeMovieTitleYear,
    homeQueueRoute,
    homeQueueMeta,
    homeQueueRowIsRunnable,
    homeQueueGlobalOrder,
    homeCurrentQueueOrder,
    homeNextQueueRows,
    renderHomePendingCount,
    renderHomeNetworkRole,
    renderHomeStorageHealth,
    renderHomeQueueSnapshot,
    renderHomeRecentCompleted,
    homePromotionRunActive,
    renderHomePromotionEntry
  };
})();
