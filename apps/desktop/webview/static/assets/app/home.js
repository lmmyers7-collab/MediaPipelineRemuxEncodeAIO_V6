/* global getCommandHistory, lastRefreshCompletedAt, lastRefreshDurationMs, refreshTimeLabel */
(function () {
  const formatters = window.mediaPipelineFormatters || {};
  const formatProgressValue = typeof formatters.formatProgressValue === "function"
    ? formatters.formatProgressValue
    : (value) => {
        if (value === null || value === undefined) return "";
        if (Array.isArray(value)) return value.join(", ");
        if (value && typeof value === "object") return JSON.stringify(value);
        return String(value);
      };
  const shortenPath = typeof formatters.shortenPath === "function" ? formatters.shortenPath : null;
  const settingsOverview = window.mediaPipelineSettingsOverview || {};
  const settingsView = window.mediaPipelineSettingsView || {};
  const settingsOperatorTrustStatus = typeof settingsOverview.settingsOperatorTrustStatus === "function" ? settingsOverview.settingsOperatorTrustStatus : null;
  const commandHistoryView = window.mediaPipelineCommandHistory || {};

  function homeReadinessNextStep({ snapshot, closeReadiness, failures }) {
    const items = Array.isArray(failures) ? failures : [];
    const requiredFailure = items.find((item) => item.required);
    if (requiredFailure) {
      return `Refresh the page or open Diagnostics; required backend read failed: ${requiredFailure.name}.`;
    }
    if (!snapshot) {
      return "Refresh the page. If the desktop session has expired, reopen the desktop app to establish a new session; otherwise open Diagnostics.";
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
        candidate.setAttribute("aria-pressed", selected ? "true" : "false");
      });
  }

  function renderHomeReadiness({ snapshot = null, closeReadiness = null, failures = [] } = {}) {
    const items = Array.isArray(failures) ? failures : [];
    const requiredFailures = items.filter((item) => item.required);
    const optionalFailures = items.filter((item) => !item.required);
    const safe = closeReadiness && typeof closeReadiness.safe_to_close === "boolean"
      ? closeReadiness.safe_to_close === true
      : null;
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
    const nextStep = homeReadinessNextStep({ snapshot, closeReadiness, failures: items });
    setHomePanelStatus("home-control-readiness-status", status, status === "Ready" ? "ok" : status === "Checking" ? "loading" : status === "Backend issue" ? "blocked" : "warning");
    setText("home-health-banner", `${status}: ${nextStep}`);
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
    lines.push("", `Next step: ${nextStep}`);
    setText("home-readiness-summary", lines.join("\n"));
  }

  const homeDailyDriverModule = window.__homeDailyDriverModule;
  if (!homeDailyDriverModule?.createHomeDailyDriverModule) throw new Error("Missing Home daily-driver module");
  delete window.__homeDailyDriverModule;
  const homeDailyDriver = homeDailyDriverModule.createHomeDailyDriverModule({
    appendCells, byId, clearRows, commandHistoryView,
    externalDependencyOverallStatus: (...args) => externalDependencyOverallStatus(...args),
    externalDependencyEvidenceText: (...args) => externalDependencyEvidenceText(...args),
    setHomePanelStatus, setText, settingsOperatorTrustStatus,
  });
  const {
    dailyDriverStatusClass,
    dailyDriverRows,
    dailyDriverSummaryLines,
    dailyDriverOverallStatus,
    dependencyStatusRank,
    dependencyStatusLabel,
  } = homeDailyDriver;
  const homeQueueProjectionModule = window.__homeQueueProjectionModule;
  if (!homeQueueProjectionModule?.createHomeQueueProjectionModule) throw new Error("Missing Home queue projection module");
  delete window.__homeQueueProjectionModule;
  const homeQueueProjection = homeQueueProjectionModule.createHomeQueueProjectionModule({ byId, clearRows, formatProgressValue, makeRowSelectable, selectHomeListItem, setText, shortenPath });
  const {
    homeProgressPercent, homeQueueTitle, homeQueueDisplayLabel, homeNormalizeQueueTitle, homeMovieTitleYear, homeQueueRoute, homeQueueMeta,
    homeQueueRowIsRunnable, homeQueueGlobalOrder, homeCurrentQueueOrder, homeNextQueueRows, homeCsvRerunEvidence,
    homeCsvRerunActive, homeCsvRerunQueueContext, homeCsvRerunRows, renderHomeCsvRerunQueue,
    renderHomeCsvRerunCompletion, homeActiveWork, homeActiveWorkLine, homeQueueItemMatchesActiveWork,
    renderHomeQueueDetail, renderHomeQueueDetailMessage,
  } = homeQueueProjection;
  function renderHomePendingCount(pending) {
    pending = pending && typeof pending === "object" ? pending : {};
    const loaded = Object.prototype.hasOwnProperty.call(pending, "count");
    setText("home-pending-count", loaded ? String(pending.count || 0) : "—");
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

  function homeStorageCapacitySource(row = {}) {
    const probe = row?.storage_probe && typeof row.storage_probe === "object" ? row.storage_probe : {};
    return String(row.capacity_source || probe.capacity_source || "").trim();
  }

  function homeStorageCapacitySourceText(row = {}) {
    const source = homeStorageCapacitySource(row).toLowerCase();
    if (!source || source === "configured_path" || source === "not_checked") return "";
    if (source === "share_root_fallback") return "via share root";
    if (source === "not_trusted") return "capacity not trusted";
    if (source === "unavailable") return "capacity unavailable";
    return `via ${source.replace(/_/g, " ")}`;
  }

  function homeStoragePhaseTimingText(row = {}) {
    const timings = row?.phase_timings_ms && typeof row.phase_timings_ms === "object" ? row.phase_timings_ms : {};
    const entries = Object.entries(timings)
      .filter(([, value]) => Number.isFinite(Number(value)))
      .map(([key, value]) => `${key}=${Number(value)}ms`);
    return entries.length ? `phase_timings=${entries.join(", ")}` : "";
  }

  function homeStorageLastCapacityText(row = {}) {
    const last = row?.last_successful_capacity && typeof row.last_successful_capacity === "object"
      ? row.last_successful_capacity
      : null;
    if (!last) return "";
    const free = homeStorageGbText(last.free_space_gb);
    const source = String(last.capacity_source || "").trim();
    const sourceText = source ? ` via ${source.replace(/_/g, " ")}` : "";
    return free ? `last_successful_capacity=${free}${sourceText}; evidence_only=yes` : "last_successful_capacity=evidence_only";
  }

  function homeStorageDetail(row = {}) {
    const probe = row?.storage_probe && typeof row.storage_probe === "object" ? row.storage_probe : {};
    const free = homeStorageGbText(row.free_space_gb ?? probe.free_gb);
    const reserve = homeStorageGbText(row.reserve_gb ?? probe.reserve_gb);
    const message = String(probe.message || row.message || "").trim();
    const sourceText = homeStorageCapacitySourceText(row);
    const suffix = sourceText ? ` (${sourceText})` : "";
    if (free && reserve) return `${free} free / ${reserve} reserve${suffix}`;
    if (free) return `${free} free${suffix}`;
    return message || "No free-space evidence loaded.";
  }

  function homeFailureArtifactSummary(context = {}) {
    const summary = context.failureArtifacts || context.failure_artifacts || context.failureArtifactSummary || {};
    return summary && typeof summary === "object" ? summary : {};
  }

  function homeFailureArtifactSizeText(summary = {}) {
    if (summary.total_size_text) return String(summary.total_size_text);
    const totalGb = homeStorageNumber(summary.total_gb);
    if (totalGb !== null) return `${totalGb.toFixed(totalGb % 1 ? 1 : 0)} GB`;
    return "Not loaded";
  }

  function homeFailureArtifactDateText(value) {
    const text = String(value || "").trim();
    if (!text) return "";
    const date = new Date(text);
    if (Number.isNaN(date.getTime())) return text;
    return date.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
  }

  function setHomeFailureArtifactMetric(summary = homeFailureArtifactSummary()) {
    const statusText = summary.schema_version ? homeFailureArtifactSizeText(summary) : "Not loaded";
    const scanErrors = Array.isArray(summary.scan_errors) ? summary.scan_errors.filter(Boolean) : [];
    const state = summary.warning ? "warning" : scanErrors.length ? "warning" : summary.schema_version ? "ok" : "empty";
    setTextState("home-failure-artifact-storage-status", statusText, state);
    const detail = byId("home-failure-artifact-storage-detail");
    if (!detail) return;
    if (!summary.schema_version) {
      detail.textContent = "No artifact evidence loaded.";
      detail.title = "";
      return;
    }
    const fileCount = Number(summary.file_count || 0);
    const threshold = Number(summary.threshold_gb);
    const thresholdLabel = Number.isInteger(threshold) ? String(threshold) : threshold.toFixed(1);
    const thresholdText = Number.isFinite(threshold) && threshold > 0 ? `${thresholdLabel} GB threshold` : "toast disabled";
    const oldest = homeFailureArtifactDateText(summary.oldest_modified_at);
    detail.textContent = [
      `${fileCount} file${fileCount === 1 ? "" : "s"}`,
      oldest ? `oldest ${oldest}` : "",
      thresholdText,
    ].filter(Boolean).join("; ");
    const roots = Array.isArray(summary.root_paths) ? summary.root_paths : [];
    detail.title = [
      `total_bytes=${summary.total_bytes || 0}`,
      `threshold_gb=${summary.threshold_gb}`,
      `warning=${summary.warning ? "yes" : "no"}`,
      `touches_media=${summary.touches_media ? "yes" : "no"}`,
      `cleanup_route_available=${summary.cleanup_route_available ? "yes" : "no"}`,
      ...roots.map((root) => `${root.role || "root"}=${root.path || ""}; files=${root.file_count || 0}`),
      ...scanErrors.map((error) => `scan_error=${error}`),
    ].filter(Boolean).join("\n");
  }

  function setHomeStorageMetric(statusId, detailId, row = {}) {
    const status = homeStorageStatus(row);
    setTextState(statusId, status.text, status.state);
    const detail = byId(detailId);
    if (!detail) return;
    const probe = row?.storage_probe && typeof row.storage_probe === "object" ? row.storage_probe : {};
    const attempts = Array.isArray(row.probe_attempts) ? row.probe_attempts : [];
    detail.textContent = homeStorageDetail(row);
    detail.title = [
      row.label || "",
      homeStoragePath(row) || "",
      row.health_code ? `health_code=${row.health_code}` : "",
      homeStorageCapacitySource(row) ? `capacity_source=${homeStorageCapacitySource(row)}` : "",
      row.capacity_path || probe.capacity_path ? `capacity_path=${row.capacity_path || probe.capacity_path}` : "",
      row.capacity_error || probe.capacity_error ? `capacity_error=${row.capacity_error || probe.capacity_error}` : "",
      attempts.length ? `probe_attempts=${attempts.length}` : "",
      homeStoragePhaseTimingText(row),
      homeStorageLastCapacityText(row),
      probe.message || row.message || "",
    ].filter(Boolean).join("\n");
  }

  function renderHomeStorageHealth(context = {}) {
    setHomeStorageMetric("home-scratch-storage-status", "home-scratch-storage-detail", homeScratchStorageRow(context));
    setHomeStorageMetric("home-output-storage-status", "home-output-storage-detail", homeOutputStorageRow(context));
    setHomeFailureArtifactMetric(homeFailureArtifactSummary(context));
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
    if (typeof settingsView.settingsRawActionPlanRows === "function") {
      const rawActionRows = settingsView.settingsRawActionPlanRows();
      if (rawActionRows.length) {
        const rawStatus = typeof settingsView.settingsRawActionPlanStatus === "function" ? settingsView.settingsRawActionPlanStatus(rawActionRows) : "Review";
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
    list.setAttribute("role", "list");
    list.replaceChildren();
    if (renderHomeCsvRerunCompletion(context)) return;
    const rows = homeNextQueueRows(queue, homeCurrentQueueOrder(context, queue.rows), context);
    const csvRerunQueue = homeCsvRerunQueueContext(context, queue, rows);
    if (!rows.length && renderHomeCsvRerunQueue(context)) return;
    setHomePanelStatus(
      "home-next-queue-status",
      rows.length ? `${csvRerunQueue.csvRerunQueue ? "CSV rerun queue · " : ""}${rows.length} ${csvRerunQueue.csvRerunQueue ? "queued" : "ready"}` : "No runnable",
      rows.length ? "ready" : "empty"
    );
    if (!rows.length) {
      const empty = document.createElement("li");
      empty.textContent = "No runnable queue items loaded.";
      list.appendChild(empty);
      renderHomeQueueDetailMessage("No runnable queue items loaded. Open Queue for the full backend-owned snapshot.");
      return;
    }
    rows.forEach((item, index) => {
      const isCurrent = homeQueueItemMatchesActiveWork(item, context);
      const activeWork = isCurrent ? homeActiveWork(context) : {};
      const rowOptions = { ...csvRerunQueue, activeWork };
      const li = document.createElement("li");
      li.tabIndex = 0;
      li.setAttribute("role", "button");
      li.setAttribute("aria-pressed", index === 0 ? "true" : "false");
      li.classList.toggle("is-selected", index === 0);
      li.dataset.current = isCurrent ? "true" : "false";
      if (isCurrent) li.dataset.status = "running";
      const label = homeQueueDisplayLabel(item);
      li.setAttribute("aria-label", `${isCurrent ? "Current queue item" : "Review queue item"} ${label.accessibleText || index + 1}`);
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
      meta.textContent = [
        isCurrent ? "Current" : "",
        csvRerunQueue.csvRerunQueue ? "CSV rerun" : "",
        homeQueueMeta(item) || "queued",
        isCurrent ? homeActiveWorkLine(activeWork) : "",
      ].filter(Boolean).join(" · ");
      li.append(title, meta);
      const activate = () => {
        selectHomeListItem(li);
        renderHomeQueueDetail(item, rowOptions);
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
    renderHomeQueueDetail(rows[0], {
      ...csvRerunQueue,
      activeWork: homeQueueItemMatchesActiveWork(rows[0], context) ? homeActiveWork(context) : {},
    });
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
    homeCsvRerunEvidence,
    homeCsvRerunActive,
    homeCsvRerunQueueContext,
    homeCsvRerunRows,
    renderHomeCsvRerunQueue,
    renderHomeCsvRerunCompletion,
    renderHomePendingCount,
    renderHomeNetworkRole,
    renderHomeStorageHealth,
    renderHomeQueueSnapshot,
    renderHomeRecentCompleted,
    homePromotionRunActive,
    renderHomePromotionEntry
  };
})();
