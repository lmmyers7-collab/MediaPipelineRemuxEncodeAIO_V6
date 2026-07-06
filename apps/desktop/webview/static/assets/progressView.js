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
  let selectedProgressEvidenceKey = "";
  const STALE_DISPLAY_CONFIRMATION_COUNT = 2;
  const AUDIT_PROGRESS_ACTIVE_FRESH_MS = 10 * 60 * 1000;
  const progressStaleDisplayCounts = new Map();
  let progressStaleDisplayItemKey = "";
  const progressDisplayPercentCache = new Map();
  let progressDisplayPercentItemKey = "";

  function setProgressPanelStatus(id, message, state) {
    if (typeof setPanelStatus === "function") return setPanelStatus(id, message, state);
    if (typeof setTextState === "function") {
      setTextState(id, message, state);
      return state || "";
    }
    if (typeof setText === "function") setText(id, message);
    return state || "";
  }

  function progressBarStatusLabel(bar) {
    const status = String(bar?.status || "unknown").trim();
    const mode = String(bar?.mode || "determinate").trim();
    const percent = bar?.percent;
    if (mode === "indeterminate") return status === "active" ? `${status} · running` : status;
    if (percent === undefined || percent === null || percent === "") return status;
    const value = Number(percent);
    if (!Number.isFinite(value)) return status;
    return `${status} · ${Math.max(0, Math.min(100, value)).toFixed(value % 1 ? 1 : 0)}%`;
  }

  function progressBarPercent(bar) {
    const value = Number(bar?.percent);
    if (!Number.isFinite(value)) return 0;
    return Math.max(0, Math.min(100, value));
  }

  function formatProgressUpdatedAt(value) {
    if (!value) return "";
    if (value instanceof Date && !Number.isNaN(value.getTime())) {
      const year = value.getFullYear();
      const month = String(value.getMonth() + 1).padStart(2, "0");
      const day = String(value.getDate()).padStart(2, "0");
      const hours = String(value.getHours()).padStart(2, "0");
      const minutes = String(value.getMinutes()).padStart(2, "0");
      const seconds = String(value.getSeconds()).padStart(2, "0");
      return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`;
    }
    const text = String(value).trim();
    const match = text.match(/^(\d{4}-\d{2}-\d{2})[T\s]+(\d{2}:\d{2}(?::\d{2})?)(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?/i);
    if (match) return `${match[1]} ${match[2]}`;
    return text;
  }

  const homeProgressTimelineGroups = [
    { key: "primary", label: "Active work", ids: ["current_stage", "run_total"] },
    { key: "audio", label: "Audio", ids: ["audio_track"] },
    { key: "publish", label: "Publish", ids: ["publish_output", "publish_copy"] },
    { key: "subtitles", label: "Subtitles", ids: [] },
    { key: "completed", label: "Completed", ids: [] },
    { key: "other", label: "Other checks", ids: [] },
  ];

  function progressBarId(bar) {
    return String(bar?.id || "").toLowerCase();
  }

  function progressBarStatus(bar) {
    return String(bar?.status || "unknown").toLowerCase();
  }

  function progressBarMode(bar) {
    return String(bar?.mode || "determinate").toLowerCase();
  }

  const pendingDrainCompactLabels = {
    publish_output: "Publish",
    publish_copy: "Copy output",
    pending_drain: "Drain queue",
  };

  const pendingDrainCompactStepLabels = {
    "copy completed output": "Copy output",
    "write sidecars": "Sidecars",
    "reveal output": "Reveal",
    finalize: "Finish",
  };

  function progressUsePendingDrainCompactText(options = {}) {
    return Boolean(options && (options.compact === "pendingDrain" || options.compactPendingDrain));
  }

  function progressBarDisplayLabel(bar, options = {}) {
    const fallback = bar?.label || bar?.id || "Progress";
    if (!progressUsePendingDrainCompactText(options)) return fallback;
    return pendingDrainCompactLabels[progressBarId(bar)] || fallback;
  }

  function progressStepDisplayLabel(step, options = {}) {
    const label = String(step?.label || step?.id || "Step");
    if (!progressUsePendingDrainCompactText(options)) return label;
    return pendingDrainCompactStepLabels[label.toLowerCase()] || label;
  }

  function progressBarDisplayStatusLabel(bar, options = {}) {
    if (!progressUsePendingDrainCompactText(options)) return progressBarStatusLabel(bar);
    const value = Number(bar?.percent);
    if (Number.isFinite(value)) {
      const bounded = Math.max(0, Math.min(100, value));
      return `${bounded.toFixed(bounded % 1 ? 1 : 0)}%`;
    }
    const status = progressBarStatus(bar);
    if (progressBarMode(bar) === "indeterminate" && status === "active") return "running";
    if (status === "complete") return "done";
    return status;
  }

  function progressSnapshotItemKey(snapshot = null) {
    const progress = snapshot?.progress && typeof snapshot.progress === "object" ? snapshot.progress : {};
    const file = progress.CurrentFilePath
      || progress.CurrentFileDisplay
      || progress.CurrentFile
      || progress.InputFile
      || "";
    return [
      file,
      progress.CurrentQueueIndex ?? "",
      progress.CurrentQueueTotal ?? "",
    ].map((part) => String(part || "").trim()).join("|");
  }

  function resetProgressStaleDisplayCountsForItem(snapshot = null) {
    const itemKey = progressSnapshotItemKey(snapshot);
    if (itemKey === progressStaleDisplayItemKey) return;
    progressStaleDisplayCounts.clear();
    progressStaleDisplayItemKey = itemKey;
  }

  function resetProgressDisplayPercentForItem(snapshot = null) {
    const itemKey = progressSnapshotItemKey(snapshot);
    if (itemKey === progressDisplayPercentItemKey) return;
    progressDisplayPercentCache.clear();
    progressDisplayPercentItemKey = itemKey;
  }

  function progressBarStaleDisplayKey(bar, snapshot = null) {
    return [
      progressSnapshotItemKey(snapshot),
      progressBarId(bar) || String(bar?.label || "progress").trim().toLowerCase(),
    ].join("|");
  }

  function progressBarWithStaleDisplayHysteresis(bar, snapshot = null) {
    if (!bar || typeof bar !== "object") return bar;
    const key = progressBarStaleDisplayKey(bar, snapshot);
    if (!bar.stale) {
      progressStaleDisplayCounts.delete(key);
      return bar;
    }
    const count = (progressStaleDisplayCounts.get(key) || 0) + 1;
    progressStaleDisplayCounts.set(key, count);
    if (count >= STALE_DISPLAY_CONFIRMATION_COUNT) return bar;
    const displayBar = { ...bar, stale: false };
    if (progressBarStatus(displayBar) === "warning") displayBar.status = "active";
    return displayBar;
  }

  function progressBarsWithStaleDisplayHysteresis(bars = [], snapshot = null) {
    resetProgressStaleDisplayCountsForItem(snapshot);
    const items = Array.isArray(bars) ? bars.filter(Boolean) : [];
    if (!items.length) {
      progressStaleDisplayCounts.clear();
      return items;
    }
    if (!items.some((bar) => Boolean(bar?.stale))) {
      progressStaleDisplayCounts.clear();
      return items;
    }
    const seenKeys = new Set(items.map((bar) => progressBarStaleDisplayKey(bar, snapshot)));
    for (const key of progressStaleDisplayCounts.keys()) {
      if (!seenKeys.has(key)) progressStaleDisplayCounts.delete(key);
    }
    return items.map((bar) => progressBarWithStaleDisplayHysteresis(bar, snapshot));
  }

  function progressDisplayPercentKey(bar, snapshot = null) {
    const progress = snapshot?.progress && typeof snapshot.progress === "object" ? snapshot.progress : {};
    return [
      progressSnapshotItemKey(snapshot),
      progressBarId(bar) || String(bar?.label || "progress").trim().toLowerCase(),
      progress.CurrentStage || "",
      progress.CurrentRoute || progress.Route || "",
    ].map((part) => String(part || "").trim().toLowerCase()).join("|");
  }

  function progressBarForStableDisplay(bar, snapshot = null) {
    if (!bar || typeof bar !== "object") return bar;
    resetProgressDisplayPercentForItem(snapshot);
    const mode = progressBarMode(bar);
    if (mode === "indeterminate") return bar;
    const rawPercent = progressBarPercent(bar);
    const status = progressBarStatus(bar);
    const activeStatus = ["active", "running", "publishing", "warning", "unknown"].includes(status);
    const key = progressDisplayPercentKey(bar, snapshot);
    if (!activeStatus || status === "complete" || rawPercent >= 100) {
      progressDisplayPercentCache.set(key, rawPercent);
      return bar;
    }
    const previous = progressDisplayPercentCache.get(key);
    if (Number.isFinite(previous) && rawPercent + 0.05 < previous) {
      const held = { ...bar, percent: previous };
      const rawText = rawPercent % 1 === 0 ? `${rawPercent.toFixed(0)}%` : `${rawPercent.toFixed(1)}%`;
      const heldText = previous % 1 === 0 ? `${previous.toFixed(0)}%` : `${previous.toFixed(1)}%`;
      const detail = String(bar.detail || "").trim();
      held.detail = [
        detail,
        `backend percent now ${rawText}; display held at ${heldText} to avoid backward progress`,
      ].filter(Boolean).join(" | ");
      return held;
    }
    progressDisplayPercentCache.set(key, Math.max(rawPercent, Number.isFinite(previous) ? previous : rawPercent));
    return bar;
  }

  function progressBarsForStableDisplay(bars = [], snapshot = null) {
    const items = Array.isArray(bars) ? bars.filter(Boolean) : [];
    if (!items.length) {
      progressDisplayPercentCache.clear();
      return items;
    }
    return items.map((bar) => progressBarForStableDisplay(bar, snapshot));
  }

  function progressBarPercentLabel(bar) {
    const rawPercent = bar?.percent;
    const value = Number(rawPercent);
    if (Number.isFinite(value)) {
      const bounded = Math.max(0, Math.min(100, value));
      return `${bounded.toFixed(bounded % 1 ? 1 : 0)}%`;
    }
    const status = progressBarStatus(bar);
    if (progressBarMode(bar) === "indeterminate" && status === "active") return "running";
    return status;
  }

  function progressTimelineGroupKey(bar) {
    const id = progressBarId(bar);
    const source = String(bar?.source || "").toLowerCase();
    const label = String(bar?.label || "").toLowerCase();
    if (id === "operator_stop") return "primary";
    if (id === "current_stage" || id === "run_total") return "primary";
    if (id === "publish_copy" && progressBarStatus(bar) === "active") return "primary";
    if (id === "audio_track" || label.includes("audio")) return "audio";
    if (id === "publish_output" || id === "publish_copy" || id === "pending_drain") return "publish";
    if (id.startsWith("subtitle") || label.includes("subtitle")) return "subtitles";
    if (progressBarStatus(bar) === "complete" && (id === "audit_progress" || id === "audit_reports" || source.includes("audit_progress"))) {
      return "completed";
    }
    return "other";
  }

  function compactProgressUpdatedAt(value) {
    const full = formatProgressUpdatedAt(value);
    if (!full) return null;
    const match = full.match(/^\d{4}-\d{2}-\d{2}\s+(\d{2}:\d{2}(?::\d{2})?)$/);
    return {
      text: `updated ${match ? match[1] : full}`,
      title: `updated: ${full}`,
    };
  }

  function progressTimelineSortRank(bar) {
    const id = progressBarId(bar);
    if (id === "operator_stop") return 0;
    if (id === "publish_copy" && progressBarStatus(bar) === "active") return 0;
    if (id === "current_stage") return 10;
    if (id === "run_total") return 20;
    if (id === "audio_track") return 25;
    if (id === "pending_drain") return 30;
    if (id === "publish_output") return 35;
    if (id === "publish_copy") return 40;
    return 100;
  }

  function sortedProgressTimelineBars(bars) {
    return [...bars].sort((left, right) => {
      const rankDelta = progressTimelineSortRank(left) - progressTimelineSortRank(right);
      if (rankDelta) return rankDelta;
      return String(left?.label || left?.id || "").localeCompare(String(right?.label || right?.id || ""));
    });
  }

  function formatProgressBytes(value) {
    const bytes = Number(value);
    if (!Number.isFinite(bytes) || bytes < 0) return "";
    const units = ["B", "KB", "MB", "GB", "TB"];
    let size = bytes;
    for (const unit of units) {
      if (size < 1024 || unit === units[units.length - 1]) {
        return unit === "B" ? `${Math.round(size)} ${unit}` : `${size.toFixed(1)} ${unit}`;
      }
      size /= 1024;
    }
    return `${Math.round(bytes)} B`;
  }

  function formatProgressByteRate(value) {
    const text = formatProgressBytes(value);
    return text ? `${text}/s` : "";
  }

  function progressEtaRowForBar(bar, snapshot = null, diagnostics = null) {
    const id = progressBarId(bar);
    if (!id) return null;
    const rows = progressEtaRows(snapshot, diagnostics);
    return rows.find((row) => String(row?.worker_id || "").toLowerCase() === id)
      || (id === "publish_copy"
        ? rows.find((row) => String(row?.progress_source || "").toLowerCase() === "pipeline_progress.json")
        : null)
      || null;
  }

  function progressEtaTokensForBar(bar, snapshot = null, diagnostics = null) {
    const row = progressEtaRowForBar(bar, snapshot, diagnostics);
    if (!row) return [];
    const tokens = [];
    if (row.eta_seconds !== undefined && row.eta_seconds !== null) {
      tokens.push({ kind: "eta", text: `eta ${formatEtaSeconds(row.eta_seconds)}`, title: row.basis || "" });
    } else if (row.unavailable_reason) {
      tokens.push({ kind: "eta", text: "ETA unavailable", title: row.unavailable_reason });
    }
    const rate = formatProgressByteRate(row.bytes_per_second);
    if (rate) tokens.push({ kind: "rate", text: `write ${rate}` });
    const remaining = formatProgressBytes(row.bytes_remaining);
    if (remaining) tokens.push({ kind: "eta", text: `remaining ${remaining}` });
    if (row.confidence) tokens.push({ kind: "source", text: `confidence: ${row.confidence}` });
    return tokens;
  }

  function progressBarDetailTextParts(bar) {
    return String(bar?.detail || "")
      .split(/\s*\|\s*/)
      .map((part) => part.trim())
      .filter(Boolean);
  }

  function progressCompactFractionText(text, noun) {
    const match = String(text || "").trim().match(/^(\d+(?:\.\d+)?)\s*\/\s*(\d+(?:\.\d+)?)(?:\s+(.+))?$/);
    if (!match) return "";
    return `${match[1]} of ${match[2]} ${noun || match[3] || ""}`.trim();
  }

  function progressCompactPrefixedCount(text, prefix, suffix) {
    const match = String(text || "").trim().match(new RegExp(`^${prefix}\\s+(\\d+(?:\\.\\d+)?)$`, "i"));
    return match ? `${match[1]} ${suffix}` : "";
  }

  function progressCompactPendingDrainDetailPieces(bar, snapshot = null, diagnostics = null) {
    const id = progressBarId(bar);
    const detailParts = progressBarDetailTextParts(bar);
    const pieces = [];
    if (id === "publish_output") {
      const count = detailParts.find((part) => /\d+\s*\/\s*\d+\s+publish steps/i.test(part));
      const state = detailParts.find((part) => /^(copying|writing|revealing|finalizing|complete|done|pending)$/i.test(part));
      const compactCount = progressCompactFractionText(String(count || "").replace(/\s+publish steps/i, ""), "steps");
      if (compactCount) pieces.push(compactCount);
      if (state) pieces.push(state);
    } else if (id === "publish_copy") {
      const copied = detailParts.find((part) => /\d+(?:\.\d+)?\s+\w+\s*\/\s*\d+(?:\.\d+)?\s+\w+/i.test(part));
      if (copied) pieces.push(copied.replace(/\s*\/\s*/, " of "));
      const etaTokens = progressEtaTokensForBar(bar, snapshot, diagnostics).map((token) => token.text);
      const eta = etaTokens.find((token) => /^eta\s+/i.test(token));
      const remaining = etaTokens.find((token) => /^remaining\s+/i.test(token));
      if (eta) pieces.push(eta.replace(/^eta\s+/i, "ETA "));
      if (remaining) pieces.push(`${remaining.replace(/^remaining\s+/i, "")} left`);
    } else if (id === "pending_drain") {
      const count = detailParts.find((part) => /\d+\s*\/\s*\d+\s+manifests?/i.test(part));
      const compactCount = progressCompactFractionText(String(count || "").replace(/\s+manifests?/i, ""), "manifests");
      const succeeded = detailParts.map((part) => progressCompactPrefixedCount(part, "succeeded", "done")).find(Boolean);
      const remaining = detailParts.map((part) => progressCompactPrefixedCount(part, "remaining", "left")).find(Boolean);
      const errors = detailParts.map((part) => progressCompactPrefixedCount(part, "errors", "errors")).find(Boolean);
      const skipped = detailParts.map((part) => progressCompactPrefixedCount(part, "skipped", "skipped")).find(Boolean);
      if (compactCount) pieces.push(compactCount);
      if (succeeded) pieces.push(succeeded);
      if (remaining) pieces.push(remaining);
      if (errors) pieces.push(errors);
      if (skipped) pieces.push(skipped);
    }
    if (!pieces.length && detailParts.length) pieces.push(detailParts[0]);
    if (bar?.stale) pieces.push("review");
    return pieces;
  }

  function progressBarDetailPieces(bar, snapshot = null, diagnostics = null, options = {}) {
    if (progressUsePendingDrainCompactText(options)) {
      return progressCompactPendingDrainDetailPieces(bar, snapshot, diagnostics);
    }
    const etaTokens = progressEtaTokensForBar(bar, snapshot, diagnostics).map((token) => token.text);
    return [
      bar.detail,
      ...etaTokens,
      bar.source ? `source: ${bar.source}` : "",
      bar.updated_at ? `updated: ${formatProgressUpdatedAt(bar.updated_at)}` : "",
      bar.stale ? "stale/review" : "",
    ].filter(Boolean);
  }

  function progressTimelineTokens(bar, snapshot = null, diagnostics = null) {
    const tokens = [];
    String(bar?.detail || "")
      .split(/\s*\|\s*/)
      .map((part) => part.trim())
      .filter(Boolean)
      .forEach((part) => tokens.push({ kind: "detail", text: part }));
    tokens.push(...progressEtaTokensForBar(bar, snapshot, diagnostics));
    if (bar?.source) tokens.push({ kind: "source", text: `source: ${bar.source}` });
    const updated = compactProgressUpdatedAt(bar?.updated_at);
    if (updated) tokens.push({ kind: "updated", text: updated.text, title: updated.title });
    if (bar?.stale) tokens.push({ kind: "stale", text: "stale/review" });
    if (!tokens.length) tokens.push({ kind: "empty", text: "No progress detail reported." });
    return tokens;
  }

  function createProgressTrack(bar) {
    const mode = progressBarMode(bar);
    const track = document.createElement("div");
    track.className = "progress-track progress-timeline-track";
    track.setAttribute("role", "progressbar");
    track.setAttribute("aria-label", bar?.label || bar?.id || "Progress");
    track.setAttribute("aria-valuetext", progressBarStatusLabel(bar));
    if (mode === "determinate" || mode === "stepped") {
      const percent = progressBarPercent(bar);
      track.setAttribute("aria-valuemin", "0");
      track.setAttribute("aria-valuemax", "100");
      track.setAttribute("aria-valuenow", String(Math.round(percent)));
    }
    const fill = document.createElement("div");
    fill.className = "progress-fill";
    if (mode !== "indeterminate") fill.style.width = `${progressBarPercent(bar)}%`;
    track.appendChild(fill);
    return track;
  }

  function progressStepItems(bar, options = {}) {
    const steps = Array.isArray(bar?.steps) ? bar.steps.filter(Boolean) : [];
    return steps.map((step) => ({
      id: String(step?.id || ""),
      label: progressStepDisplayLabel(step, options),
      status: String(step?.status || "pending").toLowerCase(),
    }));
  }

  function createProgressStepList(bar, options = {}) {
    const steps = progressStepItems(bar, options);
    if (!steps.length) return null;
    const list = document.createElement("div");
    list.className = "progress-step-list";
    list.setAttribute("aria-label", `${progressBarDisplayLabel(bar, options)} steps`);
    steps.forEach((step, index) => {
      const item = document.createElement("span");
      item.className = "progress-step";
      item.dataset.status = step.status;
      item.textContent = step.label;
      item.title = `${index + 1}. ${step.label}: ${step.status}`;
      list.appendChild(item);
    });
    return list;
  }

  function renderHomeProgressTimelineRow(bar, snapshot = null) {
    const status = progressBarStatus(bar);
    const mode = progressBarMode(bar);
    const row = document.createElement("div");
    row.className = "progress-timeline-row";
    row.dataset.status = status;
    row.dataset.mode = mode;
    row.dataset.group = progressTimelineGroupKey(bar);

    const badge = document.createElement("div");
    badge.className = "progress-timeline-badge";
    badge.textContent = progressBarPercentLabel(bar);
    badge.title = progressBarStatusLabel(bar);

    const body = document.createElement("div");
    body.className = "progress-timeline-body";

    const header = document.createElement("div");
    header.className = "progress-timeline-header";
    const label = document.createElement("span");
    label.className = "progress-timeline-label";
    label.textContent = bar?.label || bar?.id || "Progress";
    const statusChip = document.createElement("span");
    statusChip.className = "progress-timeline-status";
    statusChip.textContent = status;
    header.append(label, statusChip);

    const metadata = document.createElement("div");
    metadata.className = "progress-timeline-metadata";
    progressTimelineTokens(bar, snapshot).forEach((token) => {
      const item = document.createElement("span");
      item.className = `progress-timeline-token progress-timeline-token-${token.kind}`;
      item.textContent = token.text;
      if (token.title) item.title = token.title;
      metadata.appendChild(item);
    });

    const steps = createProgressStepList(bar);
    body.append(header, createProgressTrack(bar));
    if (steps) body.appendChild(steps);
    body.appendChild(metadata);
    row.append(badge, body);
    return row;
  }

  function timelineText(...values) {
    for (const value of values) {
      const text = String(formatProgressValue(value)).trim();
      if (text) return text;
    }
    return "";
  }

  function timelineHasMeaningfulText(value) {
    const text = String(value || "").trim().toLowerCase();
    return Boolean(text) && !["n/a", "none", "not reported", "unknown"].includes(text);
  }

  function timelineMeaningfulText(...values) {
    for (const value of values) {
      const text = timelineText(value);
      if (timelineHasMeaningfulText(text)) return text;
    }
    return "";
  }

  function timelineLooksIdleWaiting(value) {
    const text = String(value || "").trim().toLowerCase();
    return !text
      || /^idle\b/.test(text)
      || text.includes("waiting for next item")
      || text.includes("no active work");
  }

  function timelineBarById(bars = [], ...ids) {
    const wanted = new Set(ids.map((id) => String(id || "").toLowerCase()));
    return (Array.isArray(bars) ? bars : []).find((bar) => wanted.has(progressBarId(bar))) || null;
  }

  function timelineBarMatching(bars = [], predicate = () => false) {
    return (Array.isArray(bars) ? bars : []).find((bar) => predicate(bar)) || null;
  }

  function runTimelineBarStatus(bar) {
    if (!bar) return "";
    const status = progressBarStatus(bar);
    if (bar.stale) return "review";
    if (["blocked", "failed", "error"].includes(status)) return "blocked";
    if (["warning", "review", "stale"].includes(status)) return "review";
    if (["active", "running", "processing"].includes(status)) return "active";
    if (["complete", "completed", "ok", "success"].includes(status)) return "complete";
    if (["pending", "idle", "empty"].includes(status)) return "pending";
    return status || "unknown";
  }

  function normalizeRunTimelineStatus(status) {
    const value = String(status || "").toLowerCase();
    if (["blocked", "failed", "error"].includes(value)) return "blocked";
    if (["warning", "review", "stale", "unknown"].includes(value)) return "review";
    if (["active", "running", "processing"].includes(value)) return "active";
    if (["complete", "completed", "ok", "success"].includes(value)) return "complete";
    if (["skipped", "empty"].includes(value)) return "pending";
    return value || "pending";
  }

  function runTimelineItem({ id, label, status = "pending", detail = "", bar = null, source = "", evidence = "" }) {
    const normalized = normalizeRunTimelineStatus(status || runTimelineBarStatus(bar));
    return {
      id,
      label,
      status: normalized,
      detail: String(detail || "").trim(),
      bar,
      source: String(source || bar?.source || "").trim(),
      evidence: String(evidence || "").trim(),
      current: false,
      next: false,
    };
  }

  function runTimelineProgressContext(context = {}) {
    const source = context && typeof context === "object" && !Array.isArray(context) ? context : {};
    const snapshot = source.snapshot && typeof source.snapshot === "object"
      ? source.snapshot
      : (source.progress || Array.isArray(source.progress_bars) ? source : null);
    const progress = snapshot?.progress && typeof snapshot.progress === "object" ? snapshot.progress : {};
    const currentWork = snapshot?.current_work && typeof snapshot.current_work === "object" ? snapshot.current_work : {};
    const rawBars = Array.isArray(source.bars)
      ? source.bars
      : (Array.isArray(snapshot?.progress_bars) ? snapshot.progress_bars : []);
    const bars = source.stableBars === true
      ? rawBars.filter(Boolean)
      : progressBarsForStableDisplay(
        progressBarsWithOperatorStop(progressBarsWithStaleDisplayHysteresis(rawBars, snapshot), snapshot),
        snapshot,
      );
    const csvRerun = csvRerunActivityEvidence({
      snapshot,
      diagnostics: source.diagnostics || null,
      closeReadiness: source.closeReadiness || null,
      stdoutTail: source.stdoutTail || null,
    });
    const stage = timelineText(currentWork.current_stage_label, currentWork.phase_label, progress.CurrentStage, progress.Status);
    const stageLower = stage.toLowerCase();
    const route = timelineText(progress.CurrentRoute, progress.Route, currentWork.route_label);
    const routeLower = route.toLowerCase();
    const file = timelineMeaningfulText(currentWork.item_label, progress.CurrentFileDisplay, progress.CurrentFile, progress.InputFile);
    const queueTotal = Number(progress.CurrentQueueTotal ?? snapshot?.counts?.queue_total ?? 0);
    const queueIndex = Number(progress.CurrentQueueIndex ?? snapshot?.counts?.queue_index ?? 0);
    const events = Array.isArray(snapshot?.recent_events) ? snapshot.recent_events : [];
    const hasSnapshotEvidence = Boolean(
      (snapshot && Object.keys(snapshot).length)
      || bars.length
      || Object.keys(progress).length
      || csvRerun.hasEvidence
    );
    return {
      ...source,
      snapshot,
      progress,
      currentWork,
      bars,
      csvRerun,
      stage,
      stageLower,
      route,
      routeLower,
      file,
      queueIndex: Number.isFinite(queueIndex) ? queueIndex : 0,
      queueTotal: Number.isFinite(queueTotal) ? queueTotal : 0,
      events,
      hasSnapshotEvidence,
    };
  }

  function stageMentions(stageLower, ...needles) {
    return needles.some((needle) => stageLower.includes(String(needle).toLowerCase()));
  }

  function publishOrParkBar(bars = []) {
    return timelineBarMatching(bars, (bar) => {
      const id = progressBarId(bar);
      return id === "publish_copy" && runTimelineBarStatus(bar) === "active";
    })
      || timelineBarById(bars, "publish_output")
      || timelineBarById(bars, "publish_copy")
      || timelineBarById(bars, "pending_drain");
  }

  function runTimelinePublishStatus(bar, progress = {}) {
    if (!bar) {
      return timelineText(progress.PushState, progress.SidecarState) ? "active" : "pending";
    }
    const id = progressBarId(bar);
    const status = runTimelineBarStatus(bar);
    if (id === "pending_drain") return status === "blocked" ? "blocked" : "review";
    return status;
  }

  function runTimelineCompletionStatus({ progress = {}, events = [], runTotalBar = null, publishBar = null }) {
    const statusText = timelineText(progress.Status, progress.CurrentStage).toLowerCase();
    const failed = /\b(failed|error|aborted)\b/.test(statusText)
      || events.some((event) => /\b(failed|error|aborted)\b/i.test(timelineText(event?.status, event?.data?.completion_status, event?.data?.error_code)));
    if (failed) return "blocked";
    const stopped = /\b(stopped|stop requested)\b/.test(statusText)
      || events.some((event) => /\b(stopped|stop_requested)\b/i.test(timelineText(event?.status, event?.data?.completion_status, event?.data?.error_code)));
    if (stopped) return "review";
    const completedEvent = events.some((event) => String(event?.event_type || event?.type || "").toLowerCase() === "job_completed");
    if (completedEvent || runTimelineBarStatus(runTotalBar) === "complete" || runTimelineBarStatus(publishBar) === "complete") return "complete";
    return "pending";
  }

  function runTimelineMarkFocus(items = [], hasSnapshotEvidence = false) {
    items.forEach((item) => {
      item.current = false;
      item.next = false;
    });
    if (!hasSnapshotEvidence || !items.length || items.every((item) => item.status === "complete")) return items;
    const currentIndex = items.findIndex((item) => ["blocked", "review", "active"].includes(item.status));
    const fallbackIndex = items.findIndex((item) => item.status === "pending");
    const index = currentIndex >= 0 ? currentIndex : fallbackIndex;
    if (index < 0) return items;
    items[index].current = true;
    const nextIndex = items.findIndex((item, itemIndex) => itemIndex > index && item.status !== "complete");
    if (nextIndex >= 0) items[nextIndex].next = true;
    return items;
  }

  function runTimelineItems(context = {}) {
    const source = runTimelineProgressContext(context);
    const {
      bars,
      progress,
      csvRerun,
      stage,
      stageLower,
      route,
      routeLower,
      file,
      queueIndex,
      queueTotal,
      events,
      currentWork,
    } = source;
    const currentStageBar = timelineBarById(bars, "current_stage");
    const runTotalBar = timelineBarById(bars, "run_total");
    const audioBar = timelineBarById(bars, "audio_track") || timelineBarMatching(bars, (bar) => String(bar?.label || "").toLowerCase().includes("audio"));
    const subtitleBar = timelineBarById(bars, "subtitle_track") || timelineBarMatching(bars, (bar) => {
      const id = progressBarId(bar);
      const label = String(bar?.label || "").toLowerCase();
      return id.startsWith("subtitle") || label.includes("subtitle");
    });
    const publishBar = publishOrParkBar(bars);
    const encodeActive = stageMentions(stageLower, "encode", "encoding", "remux", "transcode")
      || stageMentions(routeLower, "encode", "remux", "transcode");
    const hasPublishEvidence = Boolean(publishBar || timelineText(progress.PushState, progress.SidecarState));
    const hasRoute = timelineHasMeaningfulText(route);
    const hasFile = timelineHasMeaningfulText(file);
    const backendWorkSummary = timelineText(currentWork.summary_label, currentWork.latest_evidence_label, currentWork.current_stage_label);
    const backendWorkEvidence = timelineText(currentWork.latest_evidence_label, currentWork.missing_evidence_label);
    const backendWorkLower = backendWorkSummary.toLowerCase();
    const backendSpecificNonCsvWork = Boolean(backendWorkSummary)
      && !backendWorkLower.includes("csv")
      && !timelineLooksIdleWaiting(backendWorkSummary);
    const routeDisplay = hasRoute ? formatProgressValue(route) : "";
    const routeDecisionLabel = hasRoute ? `Route selected: ${routeDisplay}` : "Route decision pending";
    const routeDecisionDetail = hasRoute
      ? `${routeDisplay} route${progress.RouteReason ? ` | ${formatProgressValue(progress.RouteReason)}` : ""}`
      : "No backend route is selected yet; waiting for encode/remux decision evidence.";
    const routeLabel = routeLower.includes("remux") ? "Remux output" : routeLower.includes("encode") ? "Encode output" : "Encode/remux";
    const queueDetail = queueTotal > 0
      ? `Item ${Math.max(0, queueIndex)} of ${queueTotal}${file ? `: ${file}` : ""}`
      : (file ? `Current item: ${file}` : "Waiting for backend queue evidence.");

    const items = [];
    if (csvRerun.hasEvidence) {
      items.push(runTimelineItem({
        id: "csv_import",
        label: "CSV import",
        status: backendSpecificNonCsvWork
          ? "complete"
          : csvRerun.isActive || csvRerun.currentImport ? "active" : csvRerun.latestLine && csvRerunTerminalLine(csvRerun.latestLine) ? "complete" : "review",
        detail: csvRerunTimelineDetail(csvRerun, backendWorkEvidence),
        evidence: csvRerunTimelineEvidenceLine(csvRerun, backendWorkEvidence),
      }));
    }
    items.push(
      runTimelineItem({
        id: "queue_item",
        label: "Queue item",
        status: hasFile || queueTotal > 0 || runTimelineBarStatus(runTotalBar) === "complete" ? "complete" : runTimelineBarStatus(runTotalBar) || "pending",
        detail: queueDetail,
        bar: runTotalBar,
      }),
      runTimelineItem({
        id: "copy_to_scratch",
        label: "Copy to scratch",
        status: csvRerun.currentImport || stageMentions(stageLower, "copy", "scratch", "stage copy", "staged")
          ? "active"
          : hasRoute || encodeActive || hasPublishEvidence ? "complete" : "pending",
        detail: csvRerun.currentImport
          ? `Copying staged CSV source ${csvRerun.currentImport} to scratch; source media remains unchanged.`
          : hasRoute || encodeActive || hasPublishEvidence
            ? "Scratch copy stage is past or backend has route/output evidence."
            : "Waiting for backend scratch-copy evidence.",
      }),
      runTimelineItem({
        id: "route_selected",
        label: routeDecisionLabel,
        status: hasRoute ? "complete" : hasFile ? "active" : "pending",
        detail: routeDecisionDetail,
      }),
      runTimelineItem({
        id: "audio_policy",
        label: "Audio policy",
        status: audioBar ? runTimelineBarStatus(audioBar) : "pending",
        detail: audioBar?.detail || "Waiting for backend audio-policy evidence.",
        bar: audioBar,
      }),
      runTimelineItem({
        id: "subtitle_work",
        label: "Subtitle work",
        status: subtitleBar ? runTimelineBarStatus(subtitleBar) : backendWorkLower.includes("subtitle") ? "active" : "pending",
        detail: backendWorkLower.includes("subtitle") ? backendWorkSummary : subtitleBar?.detail || "Waiting for backend subtitle evidence.",
        bar: subtitleBar,
        evidence: backendWorkLower.includes("subtitle") ? backendWorkEvidence : "",
      }),
      runTimelineItem({
        id: "encode_remux",
        label: routeLabel,
        status: encodeActive ? "active" : hasPublishEvidence ? "complete" : hasRoute ? "pending" : "pending",
        detail: encodeActive
          ? [stage || routeLabel, progress.CurrentStagePercent !== undefined && progress.CurrentStagePercent !== null ? `${formatProgressValue(progress.CurrentStagePercent)}%` : ""].filter(Boolean).join(" | ")
          : hasPublishEvidence ? "Output step is past; backend is publishing, parking, or writing sidecars." : "Waiting for encode/remux stage evidence.",
        bar: encodeActive ? currentStageBar : null,
      }),
      runTimelineItem({
        id: "publish_or_park",
        label: "Publish or park",
        status: runTimelinePublishStatus(publishBar, progress),
        detail: publishBar?.detail || timelineText(progress.PushState, progress.SidecarState) || "Waiting for publish, park, or pending-drain evidence.",
        bar: publishBar,
      }),
      runTimelineItem({
        id: "run_evidence",
        label: "Run evidence",
        status: runTimelineCompletionStatus({ progress, events, runTotalBar, publishBar }),
        detail: events.length
          ? latestEventLine(null, { recent_events: events })
          : "Waiting for backend completion, review, or close-readiness evidence.",
      }),
    );
    return runTimelineMarkFocus(items, source.hasSnapshotEvidence);
  }

  function runTimelinePanelStatus(items = [], context = {}) {
    const source = runTimelineProgressContext(context);
    if (!source.hasSnapshotEvidence) return { message: "Waiting for backend snapshot", state: "empty" };
    if (!items.length) return { message: "Waiting for backend snapshot", state: "empty" };
    if (items.every((item) => item.status === "complete")) return { message: "Complete", state: "ready" };
    const current = items.find((item) => item.current) || items.find((item) => ["blocked", "review", "active"].includes(item.status));
    if (!current) return { message: "Waiting for backend snapshot", state: "empty" };
    if (current.status === "blocked") return { message: `Review: ${current.label}`, state: "blocked" };
    if (current.status === "review") return { message: `Review: ${current.label}`, state: "warning" };
    const next = items.find((item) => item.next);
    return { message: `Current: ${current.label}${next ? ` · Next: ${next.label}` : ""}`, state: "running" };
  }

  function createRunTimelineMeta(item, snapshot = null, diagnostics = null) {
    const metadata = document.createElement("div");
    metadata.className = "run-timeline-meta";
    const tokens = item.bar ? progressTimelineTokens(item.bar, snapshot, diagnostics) : [];
    if (item.evidence) tokens.push({ kind: "source", text: item.evidence });
    tokens.slice(0, item.current ? 6 : 3).forEach((token) => {
      const node = document.createElement("span");
      node.className = `run-timeline-token run-timeline-token-${token.kind || "detail"}`;
      node.textContent = token.text;
      if (token.title) node.title = token.title;
      metadata.appendChild(node);
    });
    return metadata;
  }

  function renderRunTimelineItem(item, index, context = {}) {
    const row = document.createElement("li");
    row.className = "run-timeline-item";
    row.dataset.status = item.status;
    row.dataset.current = item.current ? "true" : "false";
    row.dataset.next = item.next ? "true" : "false";
    if (item.current) row.setAttribute("aria-current", "step");

    const rail = document.createElement("span");
    rail.className = "run-timeline-rail";
    rail.setAttribute("aria-hidden", "true");
    const dot = document.createElement("span");
    dot.className = "run-timeline-dot";
    rail.appendChild(dot);

    const card = document.createElement("div");
    card.className = "run-timeline-card";
    const header = document.createElement("div");
    header.className = "run-timeline-header";
    const title = document.createElement("span");
    title.className = "run-timeline-title";
    title.textContent = item.label;
    const state = document.createElement("span");
    state.className = "run-timeline-state";
    state.textContent = item.current ? "current" : item.next ? "next" : item.status;
    header.append(title, state);

    const detail = document.createElement("p");
    detail.className = "run-timeline-detail";
    detail.textContent = item.detail || (item.current ? "Backend evidence is loading for this step." : "Waiting for backend evidence.");
    card.append(header, detail);
    if (item.current && item.bar) {
      card.appendChild(createProgressTrack(item.bar));
      const steps = createProgressStepList(item.bar);
      if (steps) card.appendChild(steps);
    }
    const meta = createRunTimelineMeta(item, context.snapshot, context.diagnostics);
    if (meta.children.length) card.appendChild(meta);
    row.append(rail, card);
    if (typeof row.style?.setProperty === "function") {
      row.style.setProperty("--run-timeline-index", String(index + 1));
    }
    return row;
  }

  function renderRunTimelineEvidence(bars = [], snapshot = null) {
    const details = document.createElement("details");
    details.className = "run-timeline-evidence";
    const summary = document.createElement("summary");
    summary.textContent = `Raw backend progress (${bars.length} ${bars.length === 1 ? "bar" : "bars"})`;
    const body = document.createElement("div");
    body.className = "run-timeline-evidence-body";
    details.append(summary, body);
    renderProgressBarsInto(body, bars, snapshot, "No raw backend progress bars loaded.");
    return details;
  }

  function renderHomeProgressTimeline(bars = [], snapshot = null, context = {}) {
    const container = byId("progress-bar-list");
    if (!container) return;
    const stableBars = progressBarsForStableDisplay(
      progressBarsWithOperatorStop(progressBarsWithStaleDisplayHysteresis(bars, snapshot), snapshot),
      snapshot,
    );
    container.classList.add("progress-timeline-list");
    container.classList.add("run-timeline-list");
    container.replaceChildren();
    const timelineContext = { ...context, bars: stableBars, snapshot, stableBars: true };
    const timelineItems = runTimelineItems(timelineContext);
    const status = runTimelinePanelStatus(timelineItems, timelineContext);
    setProgressPanelStatus("progress-detail-status", status.message, status.state);
    const list = document.createElement("ol");
    list.className = "run-timeline";
    timelineItems.forEach((item, index) => list.appendChild(renderRunTimelineItem(item, index, timelineContext)));
    container.appendChild(list);
    container.appendChild(renderRunTimelineEvidence(stableBars, snapshot));
  }

  function renderProgressBarsInto(containerOrId, bars = [], snapshot = null, emptyText = "", options = {}) {
    const container = typeof containerOrId === "string" ? byId(containerOrId) : containerOrId;
    if (!container) return;
    const items = progressBarsForStableDisplay(Array.isArray(bars) ? bars.filter(Boolean) : [], snapshot);
    container.replaceChildren();
    if (!items.length) {
      const empty = document.createElement("p");
      empty.className = "note";
      empty.textContent = emptyText || (snapshot?.progress || snapshot?.audit_progress
        ? "No active run progress from backend yet."
        : "Waiting for backend progress snapshot.");
      container.appendChild(empty);
      return;
    }
    items.forEach((bar) => {
      const mode = String(bar.mode || "determinate").toLowerCase();
      const status = String(bar.status || "unknown").toLowerCase();
      const row = document.createElement("div");
      row.className = "progress-bar-row";
      row.dataset.status = status;
      row.dataset.mode = mode;

      const header = document.createElement("div");
      header.className = "progress-bar-header";
      const label = document.createElement("span");
      label.className = "progress-bar-label";
      label.textContent = progressBarDisplayLabel(bar, options);
      const value = document.createElement("span");
      value.className = "progress-bar-value";
      value.textContent = progressBarDisplayStatusLabel(bar, options);
      header.append(label, value);

      const track = document.createElement("div");
      track.className = "progress-track";
      track.setAttribute("role", "progressbar");
      track.setAttribute("aria-label", progressBarDisplayLabel(bar, options));
      track.setAttribute("aria-valuetext", progressBarStatusLabel(bar));
      if (mode === "determinate" || mode === "stepped") {
        const percent = progressBarPercent(bar);
        track.setAttribute("aria-valuemin", "0");
        track.setAttribute("aria-valuemax", "100");
        track.setAttribute("aria-valuenow", String(Math.round(percent)));
      }
      const fill = document.createElement("div");
      fill.className = "progress-fill";
      if (mode !== "indeterminate") fill.style.width = `${progressBarPercent(bar)}%`;
      track.appendChild(fill);

      const detail = document.createElement("div");
      detail.className = "progress-bar-detail";
      const pieces = progressBarDetailPieces(bar, snapshot, null, options);
      detail.textContent = pieces.join(" · ") || "No progress detail reported.";

      const steps = createProgressStepList(bar, options);
      row.append(header, track);
      if (steps) row.appendChild(steps);
      row.appendChild(detail);
      container.appendChild(row);
    });
  }

  function renderProgressBars(bars = [], snapshot = null, context = {}) {
    renderHomeProgressTimeline(bars, snapshot, context);
  }

  function auditProgressPayload(snapshot = {}) {
    return snapshot?.audit_progress && typeof snapshot.audit_progress === "object" ? snapshot.audit_progress : {};
  }

  function rawAuditProgressBars(snapshot = {}) {
    const bars = Array.isArray(snapshot?.progress_bars) ? snapshot.progress_bars : [];
    return bars.filter((bar) => {
      const id = String(bar?.id || "").toLowerCase();
      const source = String(bar?.source || "").toLowerCase();
      return id === "audit_progress" || id === "audit_reports" || source.includes("audit_progress");
    });
  }

  function parseAuditProgressTimestamp(value) {
    if (!value) return 0;
    const timestamp = Date.parse(String(value));
    return Number.isFinite(timestamp) ? timestamp : 0;
  }

  function auditProgressSnapshotTimestampMs(snapshot = {}, bars = rawAuditProgressBars(snapshot)) {
    const auditProgress = auditProgressPayload(snapshot);
    const timestamps = [
      auditProgress.started_at,
      auditProgress.StartedAt,
      auditProgress.last_update,
      auditProgress.LastUpdate,
      auditProgress.updated_at,
      auditProgress.UpdatedAt,
      ...(Array.isArray(bars) ? bars.map((bar) => bar?.updated_at) : []),
    ].map(parseAuditProgressTimestamp).filter((value) => value > 0);
    return timestamps.length ? Math.max(...timestamps) : 0;
  }

  function auditProgressActiveState(snapshot = {}, bars = rawAuditProgressBars(snapshot)) {
    const auditProgress = auditProgressPayload(snapshot);
    if (auditProgress.completed === true || auditProgress.failed === true) return false;
    const status = String(auditProgress.status || auditProgress.Status || "").toLowerCase();
    if (["completed", "complete", "failed", "error", "blocked", "stopped", "idle"].includes(status)) return false;
    if (["starting", "scanning", "writing-reports", "running", "active", "audit", "auditing"].includes(status)) return true;
    return (Array.isArray(bars) ? bars : []).some((bar) => ["active", "running", "warning"].includes(String(bar?.status || "").toLowerCase()));
  }

  function auditProgressIsStaleForUi(snapshot = {}, bars = rawAuditProgressBars(snapshot)) {
    if (!auditProgressActiveState(snapshot, bars)) return false;
    const timestamp = auditProgressSnapshotTimestampMs(snapshot, bars);
    return Boolean(timestamp && Date.now() - timestamp > AUDIT_PROGRESS_ACTIVE_FRESH_MS);
  }

  function auditProgressBars(snapshot = {}) {
    const bars = rawAuditProgressBars(snapshot);
    if (!auditProgressIsStaleForUi(snapshot, bars)) return bars;
    return bars.map((bar) => {
      const status = String(bar?.status || "").toLowerCase();
      return {
        ...bar,
        status: ["active", "running"].includes(status) ? "warning" : bar.status,
        stale: true,
      };
    });
  }

  function auditProgressStatus(snapshot = {}, bars = auditProgressBars(snapshot)) {
    if (!snapshot) return "No snapshot";
    const auditProgress = auditProgressPayload(snapshot);
    const statuses = Array.isArray(bars) ? bars.map((bar) => String(bar?.status || "").toLowerCase()) : [];
    if (auditProgressIsStaleForUi(snapshot)) return "Audit stale";
    if (statuses.some((status) => status === "blocked")) return "Audit blocked";
    if (statuses.some((status) => status === "active")) return "Audit active";
    if (statuses.length && statuses.every((status) => status === "complete")) return "Audit complete";
    if (statuses.length) return "Audit progress loaded";
    return Object.keys(auditProgress).length ? "Audit fields loaded" : "No audit progress";
  }

  function auditProgressSummaryLines(snapshot = {}, bars = auditProgressBars(snapshot)) {
    const auditProgress = auditProgressPayload(snapshot);
    if (!Object.keys(auditProgress).length && (!Array.isArray(bars) || !bars.length)) {
      return [
        "Audit progress: no audit progress object is loaded.",
        "Next step: start Audit from Launch or refresh after an audit process has created audit_progress.json.",
        "Mutation guardrail: this view is read-only and cannot start, rerun, export, repair, or edit report files.",
      ];
    }
    const processed = auditProgress.processed_files ?? auditProgress.ProcessedFiles ?? "";
    const total = auditProgress.total_files ?? auditProgress.TotalFiles ?? "";
    const percent = auditProgress.percent_complete ?? auditProgress.PercentComplete ?? "";
    const reportIndex = auditProgress.report_step_index ?? auditProgress.ReportStepIndex ?? "";
    const reportTotal = auditProgress.report_step_total ?? auditProgress.ReportStepTotal ?? "";
    const reportStage = auditProgress.report_stage ?? auditProgress.ReportStage ?? "";
    const completedSteps = Array.isArray(auditProgress.report_completed_steps)
      ? auditProgress.report_completed_steps
      : Array.isArray(auditProgress.ReportCompletedSteps) ? auditProgress.ReportCompletedSteps : [];
    const lines = [
      `Audit status: ${formatProgressValue(auditProgress.status || auditProgress.Status || "unknown")}`,
      `Audit scan: ${processed !== "" && total !== "" ? `${processed} / ${total}` : "no scan count"}${percent !== "" ? ` (${percent}%)` : ""}`,
      auditProgress.current_operation ? `Current operation: ${formatProgressValue(auditProgress.current_operation)}` : "",
      reportTotal !== "" && Number(reportTotal) > 0
        ? `Report generation: ${reportIndex || 0} / ${reportTotal}${reportStage ? ` (${String(reportStage).replaceAll("_", " ")})` : ""}`
        : "Report generation: no stepped report progress loaded.",
      completedSteps.length ? `Completed report steps: ${completedSteps.map((step) => String(step).replaceAll("_", " ")).join(", ")}` : "",
      bars.length ? `Progress bars: ${bars.map((bar) => `${bar.label || bar.id}: ${progressBarStatusLabel(bar)}`).join(" | ")}` : "Progress bars: none emitted.",
    ].filter(Boolean);
    if (auditProgressIsStaleForUi(snapshot, bars)) {
      lines.push("Audit health: stale progress only; refresh or check ActiveJobs before treating it as active work.");
    }
    const written = [
      auditProgress.latest_json_path ? "JSON" : "",
      auditProgress.latest_csv_path ? "CSV" : "",
      auditProgress.latest_priority_csv_path ? "Priority CSV" : "",
      auditProgress.latest_text_path ? "Text" : "",
    ].filter(Boolean);
    if (written.length) lines.push(`Written reports: ${written.join(", ")}`);
    lines.push("Mutation guardrail: audit progress is runtime/report evidence only; report writing and launch remain backend-owned.");
    return lines;
  }

  function renderAuditProgressInto({ containerId, statusId, summaryId, snapshot = null, emptyText = "" } = {}) {
    const bars = auditProgressBars(snapshot || {});
    renderProgressBarsInto(containerId, bars, snapshot, emptyText || "No audit progress bars loaded.");
    if (statusId) setText(statusId, auditProgressStatus(snapshot || {}, bars));
    if (summaryId) setText(summaryId, auditProgressSummaryLines(snapshot || {}, bars).join("\n"));
  }

  function progressHasValue(value) {
    return value !== undefined && value !== null && value !== "";
  }

  function progressNumericValue(value, fallback = 0) {
    const number = Number(value);
    return Number.isFinite(number) ? number : fallback;
  }

  function progressBooleanValue(value) {
    if (typeof value === "boolean") return value;
    const text = String(value || "").trim().toLowerCase();
    return ["1", "true", "yes", "y"].includes(text);
  }

  function progressStoppedByRequest(payload) {
    const errorCode = String(payload?.ErrorCode || payload?.error_code || "").trim().toLowerCase();
    const reason = String(payload?.Reason || payload?.reason || "").trim().toLowerCase();
    const text = [
      payload?.Status,
      payload?.status,
      payload?.CurrentStage,
    ].filter(Boolean).join(" ").toLowerCase();
    return progressBooleanValue(payload?.StopRequested)
      || progressBooleanValue(payload?.stop_requested)
      || errorCode === "stop_requested"
      || (/\bstopped\b/.test(text) && reason.includes("stop") && reason.includes("operator"));
  }

  function progressEventData(event) {
    return event?.data && typeof event.data === "object" ? event.data : {};
  }

  function progressEventStoppedByRequest(event) {
    const data = progressEventData(event);
    const status = String(data.completion_status || event?.status || "").trim().toLowerCase();
    const errorCode = String(data.error_code || data.ErrorCode || "").trim().toLowerCase();
    const reason = String(data.reason || data.suggested_action || "").trim().toLowerCase();
    return status === "stopped" && (errorCode === "stop_requested" || (reason.includes("stop") && reason.includes("operator")));
  }

  function progressEventIsFailure(event) {
    const data = progressEventData(event);
    const status = String(data.completion_status || event?.status || data.classification || "").trim().toLowerCase();
    const errorCode = String(data.error_code || data.ErrorCode || "").trim().toLowerCase();
    return ["failed", "failure", "error", "blocked"].includes(status)
      || String(event?.event_type || "").toLowerCase() === "failure_recorded"
      || Boolean(errorCode && errorCode !== "stop_requested");
  }

  function progressLatestStopEvent(snapshot = {}) {
    const events = Array.isArray(snapshot?.recent_events) ? snapshot.recent_events : [];
    for (let index = events.length - 1; index >= 0; index -= 1) {
      const event = events[index];
      if (progressEventStoppedByRequest(event)) return event;
      if (progressEventIsFailure(event)) return null;
    }
    return null;
  }

  function progressSnapshotStoppedByRequest(snapshot = {}) {
    return Boolean(progressLatestStopEvent(snapshot) || progressStoppedByRequest(snapshot?.progress || {}));
  }

  function progressStopNextAction(snapshot = {}) {
    const stopEvent = progressLatestStopEvent(snapshot);
    const data = progressEventData(stopEvent);
    const publishState = String(data.publish_state || snapshot?.progress?.PublishState || "").trim().toLowerCase();
    const completionStatus = String(data.completion_status || "").trim().toLowerCase();
    const success = progressBooleanValue(data.success);
    if (["parked", "parked_recovered", "pending_move", "deferred"].includes(publishState) || publishState.includes("retry")) {
      return "Stop After Current was requested; output is waiting in Pending Publish. Drain when the final output root is safe.";
    }
    if (["published", "already_published", "succeeded"].includes(publishState)) {
      return "Stop After Current was requested; the current file completed and published. Launch when ready to continue.";
    }
    if (success || completionStatus === "processed") {
      return "Stop After Current was requested; the current file completed. Check Completed and Pending Publish, then Launch when ready.";
    }
    return "Stop After Current was requested. Check Completed and Pending Publish for the last item, then Launch when ready.";
  }

  function progressOperatorStopBar(snapshot = {}) {
    if (!progressSnapshotStoppedByRequest(snapshot)) return null;
    const stopEvent = progressLatestStopEvent(snapshot);
    const progress = snapshot?.progress && typeof snapshot.progress === "object" ? snapshot.progress : {};
    return {
      id: "operator_stop",
      label: "Stopped after current",
      status: "warning",
      mode: "determinate",
      percent: 100,
      detail: progressStopNextAction(snapshot),
      source: stopEvent ? "pipeline_events.json" : "pipeline_progress.json",
      updated_at: stopEvent?.timestamp || stopEvent?.created_at || progress.LastUpdate || progress.UpdatedAt || "",
    };
  }

  function progressBarsWithOperatorStop(bars = [], snapshot = null) {
    const items = Array.isArray(bars) ? bars.filter(Boolean) : [];
    const stopBar = progressOperatorStopBar(snapshot || {});
    if (!stopBar || items.some((bar) => progressBarId(bar) === "operator_stop")) return items;
    return [stopBar, ...items];
  }

  function progressIsEmptyText(value) {
    const text = String(value || "").trim().toLowerCase();
    return !text || text === "none" || text === "idle" || text === "unknown";
  }

  function progressTextFromKeys(payload, keys = []) {
    for (const key of keys) {
      const value = payload?.[key];
      if (!progressIsEmptyText(value)) return String(value).trim();
    }
    return "";
  }

  function progressMediaTypeLabel(value) {
    const text = String(value || "").trim();
    const normalized = text.toLowerCase();
    if (!normalized) return "";
    if (normalized === "tv" || normalized === "episode" || normalized === "episodes") return "TV";
    if (normalized === "movie" || normalized === "movies") return "Movies";
    if (normalized === "pending" || normalized === "pending_push") return "Pending publish";
    return text.replace(/_/g, " ");
  }

  function progressLibraryItem(payload) {
    const name = progressTextFromKeys(payload, [
      "CurrentLibraryName",
      "CurrentLibraryProfileName",
      "LibraryName",
      "library_name",
    ]);
    const id = progressTextFromKeys(payload, [
      "CurrentLibraryId",
      "CurrentLibraryProfileId",
      "LibraryId",
      "library_id",
    ]);
    const designation = progressTextFromKeys(payload, [
      "CurrentLibraryDesignation",
      "LibraryDesignation",
      "library_designation",
    ]);
    const sourceRoot = progressTextFromKeys(payload, [
      "CurrentLibrarySourceRoot",
      "LibrarySourceRoot",
      "library_source_root",
      "source_root",
    ]);
    const mediaType = progressMediaTypeLabel(payload.CurrentMediaType || payload.CurrentQueuePhase);
    const value = name || id || mediaType || "not reported";
    const hintParts = [];
    if (designation && designation !== value) hintParts.push(designation);
    if (id && id !== value) hintParts.push(`Profile: ${id}`);
    if (sourceRoot) hintParts.push(`Source: ${sourceRoot}`);
    if (!hintParts.length && mediaType && !name && !id) {
      hintParts.push("Progress file reports media type, not a library profile.");
    }
    return {
      label: "Library",
      value: formatProgressValue(value),
      hint: hintParts.join("; ") || "No library profile detail reported",
      status: name || id || sourceRoot ? "ok" : (mediaType ? "warning" : "empty"),
    };
  }

  function audioProgressLine(audio) {
    const payload = audio && typeof audio === "object" ? audio : {};
    if (!Object.keys(payload).length) return "";
    const action = formatProgressValue(payload.action || payload.Action || "audio");
    const status = formatProgressValue(payload.status || payload.Status || "unknown");
    const stream = payload.stream_index !== undefined && payload.stream_index !== null && payload.stream_index !== -1
      ? `stream ${formatProgressValue(payload.stream_index)}`
      : "";
    const source = payload.source_codec || payload.SourceCodec || "";
    const output = payload.output_codec || payload.OutputCodec || "";
    const codecs = [source, output].filter(Boolean).join(" -> ");
    const sourceChannels = payload.source_channels || payload.SourceChannels || "";
    const outputChannels = payload.output_channels || payload.OutputChannels || "";
    const channels = [sourceChannels, outputChannels].filter(Boolean).map((value) => `${formatProgressValue(value)}ch`).join(" -> ");
    const reason = payload.reason || payload.Reason || "";
    return [status, action, stream, codecs, channels, reason].filter(Boolean).join(" | ");
  }

  function audioProgressItem(payload) {
    const audio = payload?.AudioProgress && typeof payload.AudioProgress === "object" ? payload.AudioProgress : null;
    if (!audio) return null;
    const failed = progressBooleanValue(audio.failed || audio.Failed);
    const completed = progressBooleanValue(audio.completed || audio.Completed);
    return {
      label: "Audio",
      value: formatProgressValue(audio.action || audio.Action || audio.status || audio.Status || "loaded"),
      hint: audioProgressLine(audio) || "Backend audio policy progress loaded.",
      status: failed ? "blocked" : completed ? "ok" : "running",
    };
  }

  function pendingDrainProgressLine(pending) {
    const payload = pending && typeof pending === "object" ? pending : {};
    if (!Object.keys(payload).length) return "";
    const total = progressNumericValue(payload.manifest_count ?? payload.ManifestCount ?? payload.manifest_count_at_start ?? payload.ManifestCountAtStart);
    const attempted = progressNumericValue(payload.attempted_count ?? payload.AttemptedCount);
    const succeeded = progressNumericValue(payload.succeeded_count ?? payload.SucceededCount);
    const already = progressNumericValue(payload.already_published_count ?? payload.AlreadyPublishedCount);
    const errors = progressNumericValue(payload.error_count ?? payload.ErrorCount);
    const skipped = progressNumericValue(payload.skipped_count ?? payload.SkippedCount);
    const remaining = progressNumericValue(payload.remaining_count ?? payload.RemainingCount);
    const status = payload.status || payload.Status || "pending publish drain";
    const current = payload.current_item || payload.CurrentItem || payload.current_manifest || payload.CurrentManifest || "";
    return [
      formatProgressValue(status),
      total ? `${attempted} / ${total} manifests` : "",
      succeeded ? `succeeded ${succeeded}` : "",
      already ? `already published ${already}` : "",
      errors ? `errors ${errors}` : "",
      skipped ? `skipped ${skipped}` : "",
      remaining ? `remaining ${remaining}` : "",
      current ? `current ${formatProgressValue(current)}` : "",
    ].filter(Boolean).join(" | ");
  }

  function pendingDrainProgressItem(payload) {
    const pending = payload?.PendingDrainProgress && typeof payload.PendingDrainProgress === "object" ? payload.PendingDrainProgress : null;
    if (!pending) return null;
    const total = progressNumericValue(pending.manifest_count ?? pending.ManifestCount ?? pending.manifest_count_at_start ?? pending.ManifestCountAtStart);
    const attempted = progressNumericValue(pending.attempted_count ?? pending.AttemptedCount);
    const errors = progressNumericValue(pending.error_count ?? pending.ErrorCount);
    const deferred = progressBooleanValue(pending.deferred || pending.Deferred);
    return {
      label: "Drain",
      value: total ? `${attempted} / ${total}` : formatProgressValue(pending.status || pending.Status || "loaded"),
      hint: pendingDrainProgressLine(pending) || "Backend pending-publish drain progress loaded.",
      status: errors ? "blocked" : deferred ? "warning" : total && attempted >= total ? "ok" : "running",
    };
  }

  function progressDetailItems(progress) {
    const payload = progress && typeof progress === "object" ? progress : {};
    const route = payload.CurrentRoute || payload.Route || "";
    const reason = payload.RouteReason || payload.CurrentRouteReason || "";
    const queueIndex = payload.CurrentQueueIndex;
    const queueTotal = payload.CurrentQueueTotal;
    const remuxed = progressNumericValue(payload.Remuxed);
    const encoded = progressNumericValue(payload.Encoded);
    const failed = progressNumericValue(payload.Failed);
    const stopped = failed > 0 && progressStoppedByRequest(payload);
    const visibleFailed = stopped ? Math.max(0, failed - 1) : failed;
    const items = [];
    items.push(progressLibraryItem(payload));
    items.push(
      {
        label: "Queue",
        value: progressHasValue(queueIndex) || progressHasValue(queueTotal)
          ? `${formatProgressValue(queueIndex || 0)} / ${formatProgressValue(queueTotal || 0)}`
          : "none",
        hint: "Current item position",
        status: progressNumericValue(queueTotal) > 0 ? "running" : "empty",
      },
      {
        label: "Route",
        value: route ? formatProgressValue(route) : "none",
        hint: reason ? formatProgressValue(reason) : "No route reason",
        status: route ? "ok" : "empty",
      },
      audioProgressItem(payload),
      pendingDrainProgressItem(payload),
      {
        label: "Done",
        value: `${remuxed + encoded}`,
        hint: `Remuxed ${remuxed}; encoded ${encoded}`,
        status: remuxed + encoded > 0 ? "ok" : "empty",
      },
      {
        label: "Issues",
        value: String(visibleFailed),
        hint: visibleFailed ? "Failures need review" : stopped ? "Stop After Current is tracked in the progress bar." : "No failures reported",
        status: visibleFailed ? "blocked" : "ok",
      }
    );
    return items.filter(Boolean);
  }

  const progressDetailQuickLinks = {
    library: { page: "libraries", label: "Open Libraries" },
    queue: { page: "queue", label: "Open Queue" },
    route: { page: "queue", label: "Open Queue route evidence" },
    done: { page: "completed", label: "Open Completed Output" },
    issues: { page: "reports", reportsTab: "failures", label: "Open Reports failures" },
  };

  function progressDetailQuickLinkKey(item) {
    return String(item?.label || "").trim().toLowerCase();
  }

  function progressDetailQuickLink(item) {
    return progressDetailQuickLinks[progressDetailQuickLinkKey(item)] || null;
  }

  function progressDetailQuickLinkLabel(item, link) {
    const label = String(item?.label || "").trim();
    const value = String(item?.value || "").trim();
    const action = String(link?.label || "Open quick link").trim();
    return [action, [label, value].filter(Boolean).join(": ")].filter(Boolean).join(" - ");
  }

  function activateProgressDetailQuickLink(link) {
    if (!link?.page) return;
    if (typeof window.showPage === "function") window.showPage(link.page);
    if (link.page === "reports" && link.reportsTab) {
      const reportsView = window.mediaPipelineReportsView || {};
      reportsView.activateReportsTab?.(link.reportsTab);
    }
  }

  function renderProgressDetails(progress) {
    const payload = progress && typeof progress === "object" ? progress : {};
    const items = progressDetailItems(payload);
    const loaded = Object.keys(payload).length > 0;
    setProgressPanelStatus("progress-detail-status", loaded ? `${items.length} checks` : "No details", loaded ? "ready" : "empty");
    const container = byId("progress-detail-rows");
    if (!container) return;
    if (!loaded) {
      container.replaceChildren();
      const empty = document.createElement("p");
      empty.className = "note";
      empty.textContent = "No progress details loaded.";
      container.appendChild(empty);
      return;
    }
    container.replaceChildren();
    items.forEach((item) => {
      const link = progressDetailQuickLink(item);
      const card = document.createElement("div");
      card.className = "progress-fact";
      card.dataset.status = item.status || "unknown";
      card.setAttribute("role", "listitem");
      if (link) {
        card.dataset.hasLink = "true";
        card.dataset.progressQuickLink = progressDetailQuickLinkKey(item);
        card.dataset.crossPageTarget = link.page;
        if (link.reportsTab) card.dataset.crossPageReportsTab = link.reportsTab;
      }
      const icon = document.createElement("span");
      icon.className = "progress-fact-icon";
      icon.setAttribute("aria-hidden", "true");
      const body = document.createElement("span");
      body.className = "progress-fact-body";
      const label = document.createElement("span");
      label.className = "progress-fact-label";
      label.textContent = item.label;
      const value = document.createElement("strong");
      value.className = "progress-fact-value";
      value.textContent = item.value;
      const hint = document.createElement("span");
      hint.className = "progress-fact-hint";
      hint.textContent = item.hint;
      body.append(label, value, hint);
      if (link) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "progress-fact-link";
        button.dataset.crossPageTarget = link.page;
        if (link.reportsTab) button.dataset.crossPageReportsTab = link.reportsTab;
        button.setAttribute("aria-label", progressDetailQuickLinkLabel(item, link));
        button.title = [link.label, item.hint].filter(Boolean).join(". ");
        button.addEventListener("click", () => activateProgressDetailQuickLink(link));
        button.append(icon, body);
        card.appendChild(button);
      } else {
        card.append(icon, body);
      }
      container.appendChild(card);
    });
  }

  function renderPipelineEvents(events) {
    setProgressPanelStatus("pipeline-events-status", events.length ? `${events.length} event${events.length === 1 ? "" : "s"}` : "No events", events.length ? "changed" : "empty");
    const tbody = byId("pipeline-event-rows");
    if (!tbody) return;
    if (!events.length) {
      clearRows(tbody, 3, "No pipeline events loaded.");
      return;
    }
    tbody.replaceChildren();
    events.slice(-25).reverse().forEach((event) => {
      const row = document.createElement("tr");
      appendCells(row, [
        event.timestamp || event.created_at || "",
        event.event_type || event.type || "",
        formatProgressValue(event.data || event),
      ]);
      tbody.appendChild(row);
    });
  }

  function normalizedProgressState(snapshot, progress) {
    return String(snapshot?.pipeline_state || progress?.Status || progress?.status || "unknown").trim().toLowerCase();
  }

  function progressStateIsActive(state) {
    return /processing|running|active|publishing|copying|encoding|remuxing|probing|auditing/.test(String(state || "").toLowerCase());
  }

  function progressEvidencePostureStatus(posture) {
    const value = String(posture || "").toLowerCase();
    if (value.includes("blocked") || value.includes("active work") || value.includes("unsafe")) return "blocked";
    if (value.includes("review") || value.includes("unknown") || value.includes("stale") || value.includes("missing") || value.includes("paused") || value.includes("stop")) return "warning";
    return "match";
  }

  function progressLatestEvent(events) {
    const items = Array.isArray(events) ? events.filter(Boolean) : [];
    if (!items.length) return null;
    return items[items.length - 1] || null;
  }

  function progressEventLabel(event) {
    if (!event) return "none";
    const type = event.event_type || event.type || event.kind || "event";
    const time = event.timestamp || event.created_at || event.at || "";
    return `${time ? `${time} ` : ""}${type}`.trim();
  }

  function progressActiveJobRows(diagnostics) {
    const structuredRows = Array.isArray(diagnostics?.active_job_rows) ? diagnostics.active_job_rows.filter(Boolean) : [];
    if (structuredRows.length) return structuredRows;
    return Array.isArray(diagnostics?.active_jobs) ? diagnostics.active_jobs.filter(Boolean) : [];
  }

  function formatActiveJobEvidenceRow(row) {
    if (!row || typeof row !== "object") return formatProgressValue(row);
    return [
      row.job_kind || row.record_file || "ActiveJobs record",
      row.mode ? `mode=${formatProgressValue(row.mode)}` : "",
      row.status ? `status=${formatProgressValue(row.status)}` : "",
      row.status_state ? `state=${formatProgressValue(row.status_state)}` : "",
      row.launch_id ? `launch=${formatProgressValue(row.launch_id)}` : "",
      row.pid !== undefined && row.pid !== null ? `pid=${formatProgressValue(row.pid)}` : "",
      row.issue ? `issue=${formatProgressValue(row.issue)}` : "",
    ].filter(Boolean).join("; ");
  }

  function progressWorkerPayload(snapshot = null, diagnostics = null) {
    const fromSnapshot = snapshot?.worker_progress && typeof snapshot.worker_progress === "object" ? snapshot.worker_progress : null;
    const fromDiagnostics = diagnostics?.worker_progress && typeof diagnostics.worker_progress === "object" ? diagnostics.worker_progress : null;
    return fromDiagnostics || fromSnapshot || {};
  }

  function progressWorkerRows(snapshot = null, diagnostics = null) {
    const payload = progressWorkerPayload(snapshot, diagnostics);
    return Array.isArray(payload.rows) ? payload.rows.filter(Boolean) : [];
  }

  function progressWorkerSummaryLine(snapshot = null, diagnostics = null) {
    const payload = progressWorkerPayload(snapshot, diagnostics);
    const rows = Array.isArray(payload.rows) ? payload.rows : [];
    if (!payload.schema_version && !rows.length) return "Worker progress: no backend worker-progress contract loaded.";
    return `Worker progress: ${payload.status || "unknown"}; rows=${rows.length}; running=${payload.active_count || 0}; blocked=${payload.blocked_count || 0}; warning=${payload.warning_count || 0}.`;
  }

  function formatWorkerProgressRow(row) {
    return [
      row.worker_label || row.worker_id || "Local worker",
      row.stage ? `stage=${formatProgressValue(row.stage)}` : "",
      row.percent !== undefined && row.percent !== null ? `percent=${formatProgressValue(row.percent)}` : "",
      row.source ? `file=${formatProgressValue(row.source)}` : "",
      row.last_log_line ? `last=${formatProgressValue(row.last_log_line)}` : "",
    ].filter(Boolean).join("; ");
  }

  function stdoutTailText(stdoutTail = null) {
    if (typeof stdoutTail === "string") return stdoutTail;
    if (stdoutTail && typeof stdoutTail === "object") return String(stdoutTail.text || "");
    return "";
  }

  function stdoutTailLines(stdoutTail = null) {
    return stdoutTailText(stdoutTail)
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean);
  }

  function csvRerunLineMessage(line) {
    const text = String(line || "").trim();
    const match = text.match(/^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\s+\[[A-Z]+\]\s*(.*)$/);
    return (match ? match[1] : text).trim();
  }

  function csvRerunLeaf(value) {
    const text = String(value || "").trim().replace(/^["']|["']$/g, "");
    const parts = text.split(/[\\/]/).filter(Boolean);
    return (parts[parts.length - 1] || text || "").trim();
  }

  function csvRerunStageCopy(line) {
    const match = csvRerunLineMessage(line).match(/^STAGE COPY attempt\s+\d+\/\d+:\s*(.+?)\s+->\s+(.+)$/i);
    if (!match) return null;
    return {
      file: csvRerunLeaf(match[1]),
      destination: String(match[2] || "").trim(),
    };
  }

  function csvRerunStagedCopy(line) {
    const match = csvRerunLineMessage(line).match(/^STAGED copy:\s*(.+)$/i);
    return match ? csvRerunLeaf(match[1]) : "";
  }

  function csvRerunPlannedRows(line) {
    const match = csvRerunLineMessage(line).match(/^Rerun CSV rows listed:\s*(\d+);\s*enabled\/planned:\s*(\d+)/i);
    return match ? `${match[2]} enabled / ${match[1]} CSV rows` : "";
  }

  function csvRerunExplicitLine(line) {
    const message = csvRerunLineMessage(line);
    return /^(Rerun CSV rows listed|STAGE COPY attempt|STAGED copy:|CSV rerun workspace:|PLAN \[|PLAN ONLY complete)/i.test(message)
      || /\bCSV\s+rerun\b|\bRerun\s+CSV\b|RerunQueue|RerunWorkspace|RerunParked/i.test(message);
  }

  function csvRerunTerminalLine(line) {
    const message = csvRerunLineMessage(line);
    return /^(PLAN ONLY complete|DRY RUN complete|Rerun batch complete|No CSV rows are executable)\b/i.test(message)
      || /PIPELINE SHUTDOWN CLEANLY|ROUND COMPLETE|Single-pass mode complete/i.test(message)
      || /\b(CSV\s+rerun|Rerun\s+CSV|Rerun batch)\b.*\b(failed|failure|error|aborted)\b/i.test(message)
      || /\bnested pipeline\b.*\bexited with code\s*[1-9]\d*/i.test(message);
  }

  function csvRerunProcessingMessage(line) {
    const message = csvRerunLineMessage(line);
    if (!message) return "";
    if (/^(Rerun CSV rows listed|PLAN |STAGE COPY|STAGED copy|CSV rerun workspace)/i.test(message)) return "";
    if (/\b(nested pipeline|PIPELINE START|ffmpeg|mkvmerge|remux|encode|publish|processing)\b/i.test(message)) return message;
    return "";
  }

  function csvRerunTailEvidence(stdoutTail = null) {
    const lines = stdoutTailLines(stdoutTail);
    const hasExplicitCsvEvidence = lines.some(csvRerunExplicitLine);
    const evidence = {
      hasEvidence: false,
      plannedRows: "",
      currentImport: "",
      lastImported: "",
      processing: "",
      latestLine: "",
    };
    if (!lines.length) return evidence;

    let stageIndex = -1;
    let stagedIndex = -1;
    let processingIndex = -1;
    lines.forEach((line, index) => {
      const plannedRows = csvRerunPlannedRows(line);
      if (plannedRows) evidence.plannedRows = plannedRows;
      const stageCopy = csvRerunStageCopy(line);
      if (stageCopy?.file) {
        stageIndex = index;
        evidence.currentImport = stageCopy.file;
      }
      const stagedCopy = csvRerunStagedCopy(line);
      if (stagedCopy) {
        stagedIndex = index;
        evidence.lastImported = stagedCopy;
      }
      const processing = hasExplicitCsvEvidence ? csvRerunProcessingMessage(line) : "";
      if (processing) {
        processingIndex = index;
        evidence.processing = processing;
      }
    });

    if (stagedIndex >= stageIndex && stagedIndex >= 0) {
      evidence.currentImport = stageIndex >= 0 ? "Waiting for next copy" : "";
    }
    if (!evidence.processing) {
      evidence.processing = stageIndex >= 0 || stagedIndex >= 0
        ? "Not processing yet; importing staged CSV files"
        : "";
    }
    if (processingIndex >= 0 && processingIndex > Math.max(stageIndex, stagedIndex)) {
      evidence.currentImport = "";
    }
    evidence.latestLine = hasExplicitCsvEvidence ? csvRerunLineMessage(lines[lines.length - 1]) : "";
    evidence.hasEvidence = Boolean(hasExplicitCsvEvidence && (
      evidence.plannedRows
      || evidence.currentImport
      || evidence.lastImported
      || evidence.processing
      || evidence.latestLine
    ));
    return evidence;
  }

  function csvRerunWorkerText(row = {}) {
    return [
      row.job_kind,
      row.worker_label,
      row.worker_id,
      row.stage,
      row.status,
      row.status_state,
      row.source,
      row.last_log_line,
    ].map((value) => String(value || "").trim()).filter(Boolean).join(" ");
  }

  function csvRerunWorkerJobKind(row = {}) {
    return String(row.job_kind || row.kind || "").trim().toLowerCase();
  }

  function csvRerunWorkerIsActive(row = {}) {
    const status = [
      row.status_state,
      row.status,
      row.stage,
    ].map((value) => String(value || "").trim().toLowerCase()).join(" ");
    return /\b(running|active|warning|copying|staging|import|processing|remux|encode|publish)\b/.test(status);
  }

  function csvRerunActivePipelineWorkerPresent(rows = []) {
    return rows.some((row) => {
      const kind = csvRerunWorkerJobKind(row);
      const label = String(row.worker_label || "").trim().toLowerCase();
      return (kind === "pipeline" || label === "local pipeline") && csvRerunWorkerIsActive(row);
    });
  }

  function csvRerunWorkerLooksRelevant(row = {}) {
    const kind = csvRerunWorkerJobKind(row);
    if (kind === "rerun_csv" || kind === "csv_rerun") return true;
    if (kind === "pipeline" || String(row.worker_label || "").trim().toLowerCase() === "local pipeline") return false;
    return /\b(csv|rerun)\b|RerunQueue|STAGE COPY|STAGED copy|Rerun CSV/i.test(csvRerunWorkerText(row));
  }

  function csvRerunWorkerLooksActive(row = {}) {
    const lastLine = String(row.last_log_line || "");
    return /STAGE COPY|STAGED copy|Rerun CSV rows listed|CSV rerun workspace/i.test(lastLine)
      || csvRerunWorkerIsActive(row);
  }

  function csvRerunWorkerEvidence(context = {}) {
    const snapshot = context?.snapshot && typeof context.snapshot === "object" ? context.snapshot : null;
    const diagnostics = context?.diagnostics && typeof context.diagnostics === "object" ? context.diagnostics : null;
    const rows = progressWorkerRows(snapshot, diagnostics).filter(csvRerunWorkerLooksRelevant);
    const activeRow = rows.find(csvRerunWorkerLooksActive) || rows[0] || null;
    const lineText = rows.map((row) => row.last_log_line).filter(Boolean).join("\n");
    const lineEvidence = csvRerunTailEvidence({ text: lineText });
    const sourceLeaf = csvRerunLeaf(activeRow?.source || "");
    return {
      ...lineEvidence,
      hasWorkerEvidence: rows.length > 0,
      workerActive: rows.some(csvRerunWorkerLooksActive),
      currentImport: lineEvidence.currentImport || (csvRerunWorkerLooksActive(activeRow || {}) ? sourceLeaf : ""),
      latestLine: lineEvidence.latestLine || String(activeRow?.last_log_line || "").trim(),
    };
  }

  function csvRerunActivityEvidence(context = {}) {
    const source = context && typeof context === "object" && ("stdoutTail" in context || "snapshot" in context || "diagnostics" in context)
      ? context
      : { stdoutTail: context };
    const tail = csvRerunTailEvidence(source.stdoutTail);
    const allWorkerRows = progressWorkerRows(source.snapshot, source.diagnostics);
    const worker = csvRerunWorkerEvidence(source);
    const activePipelineWorker = csvRerunActivePipelineWorkerPresent(allWorkerRows);
    const tailAllowed = Boolean(tail.hasEvidence && (!activePipelineWorker || worker.hasWorkerEvidence));
    const isActive = Boolean(worker.workerActive)
      || (tailAllowed && !csvRerunTerminalLine(tail.latestLine || ""));
    return {
      hasEvidence: Boolean(tailAllowed || worker.hasEvidence || worker.hasWorkerEvidence),
      plannedRows: tail.plannedRows || worker.plannedRows || "",
      currentImport: tail.currentImport || worker.currentImport || "",
      lastImported: tail.lastImported || worker.lastImported || "",
      processing: tail.processing || worker.processing || "",
      latestLine: worker.latestLine || tail.latestLine || "",
      hasWorkerEvidence: Boolean(worker.hasWorkerEvidence),
      workerActive: Boolean(worker.workerActive),
      tailSuppressedByPipelineWorker: Boolean(tail.hasEvidence && activePipelineWorker && !worker.hasWorkerEvidence),
      isActive,
    };
  }

  function csvRerunActiveFile(evidence = {}) {
    const current = String(evidence.currentImport || "").trim();
    if (!current || /^waiting for next copy$/i.test(current)) return "";
    return current;
  }

  function csvRerunCompactEventLine(line) {
    const raw = String(line || "").trim();
    if (!raw) return "";
    const time = raw.match(/^\d{4}-\d{2}-\d{2}\s+(\d{2}:\d{2}:\d{2})\b/)?.[1] || "";
    let message = csvRerunLineMessage(raw).replace(/\s+/g, " ").replace(/\s*\.\.\.$/, "").trim();
    const statusMatch = message.match(/^(ENCODE|REMUX|PUBLISH|COPY|STAGE COPY|FFMPEG)\s*:?\s*(.+)$/i);
    if (statusMatch) {
      const label = statusMatch[1].toLowerCase().replace(/\b\w/g, (letter) => letter.toUpperCase());
      message = `${label} ${statusMatch[2]}`.trim();
    }
    if (/^Not processing yet; importing staged CSV files$/i.test(message)) message = "Importing staged files";
    return [time, message].filter(Boolean).join(" ");
  }

  function csvRerunTimelineWaitLine(evidence = {}, backendWorkEvidence = "") {
    const activeFile = csvRerunActiveFile(evidence);
    if (activeFile) return "Importing staged source";
    const activityText = [
      backendWorkEvidence,
      evidence.processing,
      evidence.latestLine,
    ].map((value) => String(value || "").toLowerCase()).join(" ");
    if (/\bencode|transcode|ffmpeg\b/.test(activityText)) return "Waiting for encode to finish";
    if (/\bremux|mkvmerge\b/.test(activityText)) return "Waiting for remux to finish";
    if (/\bpublish|park|sidecar|pending\b/.test(activityText)) return "Waiting for output placement";
    if (/\bnested pipeline\b/.test(activityText)) return "Waiting for nested pipeline";
    if (evidence.isActive) return "Waiting for next CSV item";
    if (evidence.latestLine && csvRerunTerminalLine(evidence.latestLine)) {
      const terminalText = csvRerunLineMessage(evidence.latestLine).toLowerCase();
      return /\b(failed|failure|error|aborted|exited with code\s*[1-9]\d*)\b/.test(terminalText)
        ? "CSV rerun needs review"
        : "CSV rerun complete";
    }
    if (evidence.processing) return csvRerunCompactEventLine(evidence.processing);
    return "";
  }

  function csvRerunTimelineDetail(evidence = {}, backendWorkEvidence = "") {
    const activeFile = csvRerunActiveFile(evidence);
    const primary = evidence.lastImported
      ? `Loaded ${evidence.lastImported}`
      : activeFile
        ? `Loading ${activeFile}`
        : evidence.plannedRows
          ? `CSV rows: ${evidence.plannedRows}`
          : "CSV rerun active";
    return [primary, csvRerunTimelineWaitLine(evidence, backendWorkEvidence)].filter(Boolean).join(". ");
  }

  function csvRerunTimelineEvidenceLine(evidence = {}, backendWorkEvidence = "") {
    const event = csvRerunCompactEventLine(evidence.latestLine || backendWorkEvidence || evidence.processing);
    return event ? `Last event: ${event}` : "";
  }

  function progressFfmpegPayload(snapshot = null, diagnostics = null) {
    const fromSnapshot = snapshot?.ffmpeg_progress && typeof snapshot.ffmpeg_progress === "object" ? snapshot.ffmpeg_progress : null;
    const fromDiagnostics = diagnostics?.ffmpeg_progress && typeof diagnostics.ffmpeg_progress === "object" ? diagnostics.ffmpeg_progress : null;
    return fromDiagnostics || fromSnapshot || {};
  }

  function progressFfmpegRows(snapshot = null, diagnostics = null) {
    const payload = progressFfmpegPayload(snapshot, diagnostics);
    return Array.isArray(payload.rows) ? payload.rows.filter(Boolean) : [];
  }

  function progressFfmpegSummaryLine(snapshot = null, diagnostics = null) {
    const payload = progressFfmpegPayload(snapshot, diagnostics);
    const rows = Array.isArray(payload.rows) ? payload.rows : [];
    if (!payload.schema_version && !rows.length) return "FFmpeg progress proof: no backend FFmpeg-progress contract loaded.";
    return `FFmpeg progress proof: ${payload.status || "unknown"}; rows=${rows.length}; parsed=${payload.parsed_count || 0}; parse_errors=${payload.parse_error_count || 0}.`;
  }

  function formatFfmpegProgressRow(row) {
    return [
      row.job_id ? `job=${formatProgressValue(row.job_id)}` : "",
      row.stage ? `stage=${formatProgressValue(row.stage)}` : "",
      row.source ? `file=${formatProgressValue(row.source)}` : "",
      row.frame !== undefined && row.frame !== null ? `frame=${formatProgressValue(row.frame)}` : "",
      row.fps !== undefined && row.fps !== null ? `fps=${formatProgressValue(row.fps)}` : "",
      row.time ? `time=${formatProgressValue(row.time)}` : "",
      row.speed ? `speed=${formatProgressValue(row.speed)}` : "",
      row.bitrate ? `bitrate=${formatProgressValue(row.bitrate)}` : "",
      row.parse_error ? `parse_error=${formatProgressValue(row.parse_error)}` : "",
    ].filter(Boolean).join("; ") || "No FFmpeg key/value progress fields parsed.";
  }

  function progressEtaPayload(snapshot = null, diagnostics = null) {
    const fromSnapshot = snapshot?.eta && typeof snapshot.eta === "object" ? snapshot.eta : null;
    const fromDiagnostics = diagnostics?.eta && typeof diagnostics.eta === "object" ? diagnostics.eta : null;
    return fromDiagnostics || fromSnapshot || {};
  }

  function progressEtaRows(snapshot = null, diagnostics = null) {
    const payload = progressEtaPayload(snapshot, diagnostics);
    return Array.isArray(payload.rows) ? payload.rows.filter(Boolean) : [];
  }

  function formatEtaSeconds(value) {
    const seconds = Number(value);
    if (!Number.isFinite(seconds) || seconds < 0) return "not available";
    const rounded = Math.round(seconds);
    const hours = Math.floor(rounded / 3600);
    const minutes = Math.floor((rounded % 3600) / 60);
    const remainingSeconds = rounded % 60;
    if (hours > 0) return `${hours}h ${String(minutes).padStart(2, "0")}m`;
    if (minutes > 0) return `${minutes}m ${String(remainingSeconds).padStart(2, "0")}s`;
    return `${remainingSeconds}s`;
  }

  function progressEtaSummaryLine(snapshot = null, diagnostics = null) {
    const payload = progressEtaPayload(snapshot, diagnostics);
    const rows = Array.isArray(payload.rows) ? payload.rows : [];
    if (!payload.schema_version && !rows.length) return "ETA: no backend ETA contract loaded.";
    const estimate = rows.find((row) => row && row.eta_seconds !== undefined && row.eta_seconds !== null);
    const estimateText = estimate ? `; next=${formatEtaSeconds(estimate.eta_seconds)}; confidence=${estimate.confidence || "unknown"}` : "";
    return `ETA: ${payload.status || "unknown"}; rows=${rows.length}; estimated=${payload.estimated_count || 0}; unavailable=${payload.unavailable_count || 0}${estimateText}.`;
  }

  function formatEtaRow(row) {
    return [
      row.job_id ? `job=${formatProgressValue(row.job_id)}` : "",
      row.stage ? `stage=${formatProgressValue(row.stage)}` : "",
      row.source ? `file=${formatProgressValue(row.source)}` : "",
      row.eta_seconds !== undefined && row.eta_seconds !== null ? `eta=${formatEtaSeconds(row.eta_seconds)}` : "",
      row.confidence ? `confidence=${formatProgressValue(row.confidence)}` : "",
      row.percent !== undefined && row.percent !== null ? `percent=${formatProgressValue(row.percent)}` : "",
      row.elapsed_seconds !== undefined && row.elapsed_seconds !== null ? `elapsed=${formatEtaSeconds(row.elapsed_seconds)}` : "",
      row.bytes_per_second !== undefined && row.bytes_per_second !== null ? `rate=${formatProgressByteRate(row.bytes_per_second)}` : "",
      row.bytes_remaining !== undefined && row.bytes_remaining !== null ? `remaining=${formatProgressBytes(row.bytes_remaining)}` : "",
      row.unavailable_reason ? `unavailable=${formatProgressValue(row.unavailable_reason)}` : "",
    ].filter(Boolean).join("; ") || "No ETA row details available.";
  }

  function progressEvidenceRows({ snapshot = null, closeReadiness = null, diagnostics = null } = {}) {
    const progress = snapshot?.progress && typeof snapshot.progress === "object" ? snapshot.progress : {};
    const auditProgress = snapshot?.audit_progress && typeof snapshot.audit_progress === "object" ? snapshot.audit_progress : {};
    const state = normalizedProgressState(snapshot, progress);
    const active = progressStateIsActive(state);
    const activeJobs = progressActiveJobRows(diagnostics);
    const workerRows = progressWorkerRows(snapshot, diagnostics);
    const workerPayload = progressWorkerPayload(snapshot, diagnostics);
    const ffmpegRows = progressFfmpegRows(snapshot, diagnostics);
    const ffmpegPayload = progressFfmpegPayload(snapshot, diagnostics);
    const ffmpegParseError = Number(ffmpegPayload.parse_error_count || 0) > 0;
    const etaRows = progressEtaRows(snapshot, diagnostics);
    const etaPayload = progressEtaPayload(snapshot, diagnostics);
    const etaEstimated = Number(etaPayload.estimated_count || 0) > 0;
    const etaUnavailable = Number(etaPayload.unavailable_count || 0) > 0;
    const events = Array.isArray(snapshot?.recent_events) ? snapshot.recent_events : [];
    const latest = progressLatestEvent(events);
    const route = activeWorkRouteLine(progress);
    const queue = activeWorkQueueLine(progress);
    const control = activeWorkControlLine(progress);
    const auditState = String(auditProgress.status || auditProgress.Status || "").trim().toLowerCase();
    const auditActive = progressStateIsActive(auditState);
    const rows = [];

    rows.push({
      key: "snapshot-state",
      checkpoint: "Snapshot state",
      posture: active ? "active" : state === "unknown" ? "unknown" : "idle",
      evidence: `${snapshot?.activity || "No activity text"}; state=${state}`,
      action: active
        ? "Monitor Progress Details and wait for close-readiness to report safe before closing or starting more work."
        : "Confirm Queue/Completed/Pending pages if you expected active work.",
      detail: [
        `Pipeline state: ${state}`,
        `Activity: ${snapshot?.activity || "not reported"}`,
        activeWorkProgressLine(progress) || "No active stage/file progress reported.",
      ],
    });

    rows.push({
      key: "close-readiness",
      checkpoint: "Close readiness",
      posture: closeReadiness ? (closeReadiness.safe_to_close ? "safe" : "active work") : "unknown",
      evidence: closeReadiness ? `${closeReadiness.state || "unknown"}; ${closeReadiness.reason || "no reason"}` : "Close-readiness payload has not loaded.",
      action: closeReadiness?.safe_to_close === false
        ? "Do not close unless intentionally interrupting work. Inspect ActiveJobs, Run Logs, Last Stderr, and progress fields first."
        : closeReadiness?.safe_to_close === true
          ? "Safe-to-close is reported, but still compare ActiveJobs and progress rows if state looks stale."
          : "Refresh before closing; unknown close-readiness is not proof that work is idle.",
      detail: [
        `Safe to close: ${closeReadiness ? (closeReadiness.safe_to_close ? "yes" : "no") : "unknown"}`,
        `Reason: ${closeReadiness?.reason || "not reported"}`,
        `Warnings: ${(closeReadiness?.warnings || []).join(" | ") || "none"}`,
      ],
    });

    rows.push({
      key: "active-jobs",
      checkpoint: "ActiveJobs",
      posture: activeJobs.length ? "active work" : "no active job rows",
      evidence: `${activeJobs.length} ActiveJobs row${activeJobs.length === 1 ? "" : "s"} loaded.`,
      action: activeJobs.length
        ? "Open Diagnostics > ActiveJobs or Runtime Artifacts before closing, relaunching, or clearing state."
        : "If progress says active but ActiveJobs is empty, inspect Run Logs and Last Stderr for stale progress state.",
      detail: activeJobs.length
        ? activeJobs.slice(0, 8).map(formatActiveJobEvidenceRow)
        : ["No ActiveJobs rows were loaded from Diagnostics."],
    });

    rows.push({
      key: "worker-progress",
      checkpoint: "Worker progress",
      posture: workerPayload.status || (workerRows.length ? "loaded" : "not loaded"),
      evidence: progressWorkerSummaryLine(snapshot, diagnostics),
      action: workerRows.length
        ? "Use worker progress as live telemetry only; compare it with ActiveJobs and Run Logs before close, stop, retry, or rerun decisions."
        : "Do not infer per-worker progress in the WebView until the backend worker-progress contract is present.",
      detail: workerRows.length
        ? workerRows.slice(0, 8).map(formatWorkerProgressRow)
        : ["No desktop_worker_progress.v1 rows were loaded."],
    });

    rows.push({
      key: "ffmpeg-progress",
      checkpoint: "FFmpeg progress proof",
      posture: ffmpegParseError ? "missing progress" : ffmpegRows.length ? (ffmpegPayload.status || "loaded") : ffmpegPayload.status === "unavailable" ? "missing progress" : ffmpegPayload.status || "idle",
      evidence: progressFfmpegSummaryLine(snapshot, diagnostics),
      action: ffmpegParseError || ffmpegPayload.status === "unavailable"
        ? "Open Run Logs and Last Stderr; active encode/remux work did not expose parseable FFmpeg key/value progress."
        : ffmpegRows.length
        ? "Use FFmpeg progress as runtime proof only; do not infer ETA, GPU use, or output integrity from it."
        : "No FFmpeg progress action is needed while encode/remux evidence is idle or absent.",
      detail: ffmpegRows.length
        ? ffmpegRows.slice(0, 8).map(formatFfmpegProgressRow)
        : Array.isArray(ffmpegPayload.summary_lines) && ffmpegPayload.summary_lines.length
          ? ffmpegPayload.summary_lines
          : ["No desktop_ffmpeg_progress.v1 rows were loaded."],
    });

    rows.push({
      key: "eta",
      checkpoint: "ETA",
      posture: etaEstimated ? "loaded" : etaUnavailable ? "missing progress" : etaPayload.status || "idle",
      evidence: progressEtaSummaryLine(snapshot, diagnostics),
      action: etaEstimated
        ? "Treat ETA as a rough current-stage estimate only; keep using progress, logs, and close-readiness for run decisions."
        : etaUnavailable
        ? "No ETA is shown until backend worker progress reports usable percent and elapsed-time evidence."
        : "No ETA action is needed while no active worker row is reported.",
      detail: etaRows.length
        ? etaRows.slice(0, 8).map(formatEtaRow)
        : Array.isArray(etaPayload.summary_lines) && etaPayload.summary_lines.length
          ? etaPayload.summary_lines
          : ["No desktop_eta.v1 rows were loaded."],
    });

    rows.push({
      key: "current-item",
      checkpoint: "Current item",
      posture: activeWorkProgressLine(progress) ? (active ? "active" : "loaded") : active ? "missing progress" : "idle",
      evidence: activeWorkProgressLine(progress) || "No current stage/file fields are present.",
      action: active && !activeWorkProgressLine(progress)
        ? "Inspect Run Logs and Last Stderr; active state without current-item detail may mean stale or malformed progress."
        : "Use this as live context only; Completed/Pending evidence remains the output proof.",
      detail: [
        activeWorkProgressLine(progress) || "No stage/file progress line available.",
        `Current file: ${formatProgressValue(progress.CurrentFileDisplay || progress.CurrentFile || progress.InputFile || "not reported")}`,
        `Updated at: ${formatProgressUpdatedAt(progress.UpdatedAt || progress.updated_at) || "not reported"}`,
      ],
    });

    rows.push({
      key: "route-queue",
      checkpoint: "Route / queue",
      posture: route || queue ? "loaded" : active ? "missing route" : "idle",
      evidence: [route, queue].filter(Boolean).join(" | ") || "No route or queue-position fields are present.",
      action: route || queue
        ? "Compare route/queue fields against Queue row route evidence before judging remux/encode behavior."
        : "Use Queue and Completed row details if route/queue fields are missing.",
      detail: [
        route || "Route: not reported",
        queue || "Queue position: not reported",
        `Route reason: ${formatProgressValue(progress.RouteReason || progress.CurrentRouteReason || "not reported")}`,
      ],
    });

    rows.push({
      key: "control-flags",
      checkpoint: "Control flags",
      posture: /yes/.test(control) ? "paused/stop requested" : control ? "clear" : "unknown",
      evidence: control || "Pause/stop request fields are not present.",
      action: /yes/.test(control)
        ? "Expect progress to slow, pause, or finish current item. Check Control command history and Run Logs before pressing another control."
        : "Use controls only when close-readiness and active-work summary agree work is running.",
      detail: [
        `Pause requested: ${progress.PauseRequested === undefined ? "not reported" : progress.PauseRequested ? "yes" : "no"}`,
        `Stop requested: ${progress.StopRequested === undefined ? "not reported" : progress.StopRequested ? "yes" : "no"}`,
      ],
    });

    rows.push({
      key: "recent-events",
      checkpoint: "Recent events",
      posture: events.length ? "events loaded" : active ? "missing events" : "no recent events",
      evidence: `${events.length} event${events.length === 1 ? "" : "s"}; latest=${progressEventLabel(latest)}`,
      action: events.length
        ? "Use Recent Pipeline Events as supporting context, not as output proof."
        : active
          ? "Open Run Logs and Last Stderr if active work has no recent events."
          : "No event history is expected when idle or after older events roll off.",
      detail: events.length
        ? events.slice(-8).reverse().map((event) => `${progressEventLabel(event)}: ${formatProgressValue(event.data || event)}`)
        : ["No recent pipeline events are loaded in the snapshot."],
    });

    rows.push({
      key: "audit-progress",
      checkpoint: "Audit progress",
      posture: auditActive ? "audit active" : Object.keys(auditProgress).length ? "audit loaded" : "no audit progress",
      evidence: auditProgress.status || auditProgress.Status || auditProgress.current_operation || "No audit progress fields are loaded.",
      action: auditActive
        ? "Use Diagnostics runtime progress and audit logs before closing or launching pipeline work."
        : "Audit progress is informational unless audit state is active or close-readiness blocks.",
      detail: Object.keys(auditProgress).length
        ? Object.keys(auditProgress).sort().slice(0, 12).map((key) => `${key}: ${formatProgressValue(auditProgress[key])}`)
        : ["No audit progress object is present in the snapshot."],
    });

    rows.push({
      key: "proof-boundary",
      checkpoint: "Proof boundary",
      posture: "read-only",
      evidence: "Progress explains current activity; it is not publish, completion, or output-integrity proof.",
      action: "Use Completed, Pending Publish, Queue, and Diagnostics proof panels before rerun, cleanup, drain, or trust decisions.",
      detail: [
        "This board does not launch, pause, stop, rescan, drain, publish, delete, repair, rewrite, or open arbitrary paths.",
        "Progress is runtime evidence only. Output proof belongs to Completed, Pending Publish, and durable drain/manifest artifacts.",
      ],
    });

    return rows;
  }

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
    if (!selectedProgressEvidenceKey) return null;
    return rows.find((row) => row.key === selectedProgressEvidenceKey) || null;
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
    if (selectedProgressEvidenceKey && !rows.some((row) => row.key === selectedProgressEvidenceKey)) {
      selectedProgressEvidenceKey = "";
    }
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
        selectedProgressEvidenceKey = item.key;
        renderProgressEvidence(context);
      }, {
        selected: selectedProgressEvidenceKey === item.key,
        label: `Progress evidence ${item.checkpoint} ${item.posture}`,
      });
      tbody.appendChild(row);
    });
    updateTableStatusLegend("progress-evidence-legend", tbody, "Progress evidence rows");
    setText("progress-evidence-detail", progressEvidenceDetailLines(selectedProgressEvidenceRow(rows)).join("\n"));
  }

  function progressRowsForSource(source, progress, preferred) {
    const payload = progress && typeof progress === "object" ? progress : {};
    const preferredRows = preferred.filter((key) => payload[key] !== undefined && payload[key] !== null && payload[key] !== "");
    const extraRows = Object.keys(payload).filter((key) => !preferred.includes(key)).sort((a, b) => a.localeCompare(b));
    return [...preferredRows, ...extraRows].slice(0, 40).map((key) => ({
      source,
      field: key,
      value: payload[key],
    }));
  }

  function diagnosticsProgressRows(snapshot, diagnostics = null) {
    const pipelinePreferred = [
      "Status",
      "CurrentStage",
      "CurrentStagePercent",
      "CurrentFileDisplay",
      "CurrentFile",
      "CurrentRoute",
      "RouteReason",
      "CurrentQueueIndex",
      "CurrentQueueTotal",
      "CurrentStageStartedAt",
      "CurrentItemStartedAt",
      "PushState",
      "CopyStartedAt",
      "CopyUpdatedAt",
      "PauseRequested",
      "StopRequested",
      "UpdatedAt",
    ];
    const auditPreferred = [
      "status",
      "current_operation",
      "current_file",
      "processed_files",
      "total_files",
      "percent_complete",
      "report_stage",
      "report_step_index",
      "report_step_total",
      "report_completed_steps",
      "started_at",
      "updated_at",
      "error",
    ];
    const progress = snapshot?.progress && typeof snapshot.progress === "object" ? snapshot.progress : {};
    const rows = [
      ...progressRowsForSource("Pipeline", progress, pipelinePreferred),
      ...progressRowsForSource("Audit", snapshot?.audit_progress, auditPreferred),
    ];
    if (progress.AudioProgress && typeof progress.AudioProgress === "object") {
      rows.push({ source: "Pipeline", field: "AudioProgress summary", value: audioProgressLine(progress.AudioProgress) });
    }
    if (progress.PendingDrainProgress && typeof progress.PendingDrainProgress === "object") {
      rows.push({ source: "Pipeline", field: "PendingDrainProgress summary", value: pendingDrainProgressLine(progress.PendingDrainProgress) });
    }
    const workerRows = progressWorkerRows(snapshot, diagnostics);
    workerRows.forEach((row) => {
      rows.push({ source: "Worker", field: row.worker_label || row.worker_id || "Local worker", value: formatWorkerProgressRow(row) });
      if (row.last_log_line) rows.push({ source: "Worker", field: "last_log_line", value: row.last_log_line });
    });
    const ffmpegRows = progressFfmpegRows(snapshot, diagnostics);
    ffmpegRows.forEach((row) => {
      rows.push({ source: "FFmpeg", field: "latest", value: formatFfmpegProgressRow(row) });
      [
        "job_id",
        "frame",
        "fps",
        "time",
        "speed",
        "bitrate",
        "progress_source",
        "updated_at",
        "parse_error",
      ].forEach((field) => {
        const value = row[field];
        if (value !== undefined && value !== null && value !== "") rows.push({ source: "FFmpeg", field, value });
      });
      if (row.last_log_line) rows.push({ source: "FFmpeg", field: "last_log_line", value: row.last_log_line });
    });
    const etaRows = progressEtaRows(snapshot, diagnostics);
    etaRows.forEach((row) => {
      rows.push({ source: "ETA", field: row.worker_label || row.worker_id || "estimate", value: formatEtaRow(row) });
      [
        "job_id",
        "eta_seconds",
        "confidence",
        "basis",
        "bytes_per_second",
        "bytes_remaining",
        "bytes_copied",
        "bytes_total",
        "updated_at",
        "unavailable_reason",
      ].forEach((field) => {
        const value = row[field];
        if (value !== undefined && value !== null && value !== "") rows.push({ source: "ETA", field, value });
      });
    });
    return rows;
  }

  function diagnosticsProgressStatus(snapshot, rows) {
    if (!snapshot) return "No snapshot";
    if (/stale progress/i.test(String(snapshot.activity || ""))) return "Stale progress review";
    const progress = snapshot.progress && typeof snapshot.progress === "object" ? snapshot.progress : {};
    const auditProgress = snapshot.audit_progress && typeof snapshot.audit_progress === "object" ? snapshot.audit_progress : {};
    const pipelineState = String(snapshot.pipeline_state || progress.Status || "").toLowerCase();
    const auditState = String(auditProgress.status || auditProgress.Status || "").toLowerCase();
    if (pipelineState && /processing|running|active|publishing/.test(pipelineState)) return "Pipeline active";
    if (auditProgressIsStaleForUi(snapshot)) return "Audit stale";
    if (auditState && /running|active|processing|scanning/.test(auditState)) return "Audit active";
    return rows.length ? "Progress loaded" : "No progress";
  }

  function diagnosticsProgressSummaryLines(snapshot, rows, diagnostics = null) {
    if (!snapshot) {
      return [
        "Snapshot: unavailable",
        "Next step: refresh the WebView or open Diagnostics > Run Logs if close-readiness is blocked.",
      ];
    }
    const progress = snapshot.progress && typeof snapshot.progress === "object" ? snapshot.progress : {};
    const auditProgress = snapshot.audit_progress && typeof snapshot.audit_progress === "object" ? snapshot.audit_progress : {};
    const staleProgress = /stale progress/i.test(String(snapshot.activity || ""));
    const lines = [
      `Pipeline state: ${snapshot.pipeline_state || progress.Status || "unknown"}`,
      activeWorkProgressLine(progress) || "Pipeline progress: no active progress fields reported.",
      activeWorkRouteLine(progress),
      activeWorkQueueLine(progress),
      activeWorkControlLine(progress),
      progressWorkerSummaryLine(snapshot, diagnostics),
      progressFfmpegSummaryLine(snapshot, diagnostics),
      progressEtaSummaryLine(snapshot, diagnostics),
    ].filter(Boolean);
    if (staleProgress) {
      lines.push(
        "",
        "Stale progress warning:",
        "Runtime progress looks older than the current backend state. Treat Progress as context only until Close Readiness, ActiveJobs, Run Logs, and Last Stderr agree.",
        "Safe next step: read ActiveJobs and bounded logs before clearing state, closing the app, rerunning, or starting new work."
      );
    }
    if (Object.keys(auditProgress).length) {
      lines.push(
        "",
        `Audit status: ${formatProgressValue(auditProgress.status || auditProgress.Status || "unknown")}`,
        auditProgress.current_operation ? `Audit operation: ${formatProgressValue(auditProgress.current_operation)}` : "",
        auditProgress.current_file ? `Audit file: ${formatProgressValue(auditProgress.current_file)}` : "",
        auditProgress.percent_complete !== undefined ? `Audit percent: ${formatProgressValue(auditProgress.percent_complete)}` : ""
      );
    }
    lines.push(
      "",
      `Structured fields: ${rows.length}`,
      "Next step: compare Runtime Progress with Worker Progress, Close Readiness, and ActiveJobs before closing the app or clearing runtime state.",
      "Mutation guardrail: this table is read-only; progress files are still backend/runtime-owned."
    );
    return lines.filter((line) => line !== "");
  }

  function renderDiagnosticsProgress(snapshot = null, diagnostics = null) {
    const rows = diagnosticsProgressRows(snapshot || {}, diagnostics);
    setText("diagnostics-progress-status", diagnosticsProgressStatus(snapshot, rows));
    renderProgressBarsInto(
      "diagnostics-progress-bars",
      [
        ...(Array.isArray(snapshot?.progress_bars) ? snapshot.progress_bars : []),
        ...(Array.isArray(progressWorkerPayload(snapshot, diagnostics).progress_bars) ? progressWorkerPayload(snapshot, diagnostics).progress_bars : []),
      ],
      snapshot,
      "No runtime progress bars loaded.",
    );
    const tbody = byId("diagnostics-progress-rows");
    if (tbody) {
      if (!rows.length) {
        clearRows(tbody, 3, "No runtime progress fields loaded.");
      } else {
        tbody.replaceChildren();
        rows.forEach((item) => {
          const row = document.createElement("tr");
          const source = String(item.source || "").toLowerCase();
          row.dataset.status = source === "audit" ? "warning" : "";
          appendCells(row, [item.source, item.field, formatProgressValue(item.value)]);
          tbody.appendChild(row);
        });
      }
    }
    setText("diagnostics-progress-detail", diagnosticsProgressSummaryLines(snapshot, rows, diagnostics).join("\n"));
  }

  function activeWorkProgressLine(progress) {
    const stage = progress?.CurrentStage || progress?.Status || "";
    const percent = progress?.CurrentStagePercent;
    const file = progress?.CurrentFileDisplay || progress?.CurrentFile || progress?.InputFile || "";
    const parts = [];
    if (stage) parts.push(`Stage: ${formatProgressValue(stage)}`);
    if (percent !== undefined && percent !== null && percent !== "") parts.push(`Stage percent: ${formatProgressValue(percent)}`);
    if (file) parts.push(`File: ${formatProgressValue(file)}`);
    return parts.join(" | ");
  }

  function activeWorkRouteLine(progress) {
    const route = progress?.CurrentRoute || progress?.Route || "";
    const reason = progress?.RouteReason || progress?.CurrentRouteReason || "";
    if (!route && !reason) return "";
    return `Route: ${formatProgressValue(route || "unknown")}${reason ? ` | Reason: ${formatProgressValue(reason)}` : ""}`;
  }

  function activeWorkQueueLine(progress) {
    const index = progress?.CurrentQueueIndex;
    const total = progress?.CurrentQueueTotal;
    if ((index === undefined || index === null || index === "") && (total === undefined || total === null || total === "")) return "";
    return `Queue position: ${formatProgressValue(index || 0)} / ${formatProgressValue(total || 0)}`;
  }

  function activeWorkControlLine(progress) {
    const flags = [];
    if (progress?.PauseRequested !== undefined) flags.push(`Pause requested: ${progress.PauseRequested ? "yes" : "no"}`);
    if (progress?.StopRequested !== undefined) flags.push(`Stop requested: ${progress.StopRequested ? "yes" : "no"}`);
    return flags.join(" | ");
  }

  function progressLooksFinalizing(progress = {}) {
    const stage = String(progress?.CurrentStage || progress?.Status || "").trim().toLowerCase();
    const percent = progressNumericValue(progress?.CurrentStagePercent, NaN);
    const pushState = String(progress?.PushState || "").trim().toLowerCase();
    const sidecarState = String(progress?.SidecarState || "").trim().toLowerCase();
    if (!Number.isFinite(percent) || percent < 95 || percent >= 100) return false;
    if (["encode", "encode_cpu", "encode_verify", "remux_av", "remux_verify"].includes(stage)) return true;
    return Boolean(pushState || sidecarState);
  }

  function activeWorkFinalizingLine(progress) {
    if (!progressLooksFinalizing(progress)) return "";
    const stage = String(progress?.CurrentStage || "").trim().toLowerCase();
    if (stage.includes("encode")) return "Stage note: encoding is near completion; backend may still be verifying output, writing sidecars, publishing, or parking.";
    if (stage.includes("remux")) return "Stage note: remux is near completion; backend may still be verifying output, writing sidecars, publishing, or parking.";
    return "Stage note: progress is near completion; wait for backend completion, parked-publish, or close-readiness evidence.";
  }

  function latestEventLine(diagnostics, snapshot) {
    const diagnosticEvents = Array.isArray(diagnostics?.recent_events) ? diagnostics.recent_events : [];
    if (diagnosticEvents.length) return `Latest diagnostic event: ${formatProgressValue(diagnosticEvents[0])}`;
    const snapshotEvents = Array.isArray(snapshot?.recent_events) ? snapshot.recent_events : [];
    if (!snapshotEvents.length) return "";
    const event = snapshotEvents[snapshotEvents.length - 1];
    return `Latest pipeline event: ${formatProgressValue(event?.event_type || event?.type || event)}`;
  }

  function liveRunStatus({ snapshot = null, diagnostics = null, closeReadiness = null, stdoutTail = null } = {}) {
    const activity = String(snapshot?.activity || snapshot?.current_activity || "").toLowerCase();
    const state = String(snapshot?.pipeline_state || closeReadiness?.state || "").toLowerCase();
    const currentWork = snapshot?.current_work && typeof snapshot.current_work === "object" ? snapshot.current_work : {};
    const activeWorkSummary = String(currentWork.summary_label || currentWork.latest_evidence_label || currentWork.current_stage_label || "").trim();
    const csvRerun = csvRerunActivityEvidence({ snapshot, diagnostics, closeReadiness, stdoutTail });
    if (activity.includes("stale progress")) return { label: "Stale/review", state: "warning" };
    if (activeWorkSummary && !activeWorkSummary.toLowerCase().includes("csv") && !timelineLooksIdleWaiting(activeWorkSummary)) {
      return { label: "Active work", state: "running" };
    }
    if (csvRerun.hasEvidence) return { label: "CSV rerun active", state: "running" };
    if (closeReadiness?.safe_to_close === false || ["processing", "running", "active", "publishing"].includes(state)) {
      return { label: "Active work", state: "running" };
    }
    if (closeReadiness?.safe_to_close === true) return { label: "Idle", state: "ok" };
    return { label: "Checking", state: "unknown" };
  }

  function compactUpdatedAgeText(value) {
    const updated = compactProgressUpdatedAt(value);
    return updated?.text || "";
  }

  function liveRunItem(label, value, hint = "", status = "") {
    return {
      label,
      value: String(value || "").trim() || "Not loaded",
      hint: String(hint || "").trim(),
      status: status || "unknown",
    };
  }

  function longRunReliabilityPayload(snapshot = null) {
    const counts = snapshot?.counts && typeof snapshot.counts === "object" ? snapshot.counts : {};
    return counts.long_run_reliability && typeof counts.long_run_reliability === "object" ? counts.long_run_reliability : {};
  }

  function longRunReliabilitySummary(snapshot = null) {
    const payload = longRunReliabilityPayload(snapshot);
    if (!Object.keys(payload).length) return "";
    const continuous = payload.continuous_round_state || {};
    const pending = payload.pending_publish_backpressure || {};
    const workers = payload.worker_slots || {};
    const stateDb = payload.state_db || {};
    return [
      `round_blocked=${Boolean(continuous.blocked)}`,
      `round_failures=${Number(continuous.consecutive_unexpected_round_failures || 0)}`,
      `pending_blocked=${Boolean(pending.blocked)}`,
      `pending_manifests=${Number(pending.manifest_count || 0)}`,
      `stale_workers=${Number(workers.stale_heartbeat_count || 0)}`,
      `wal_bytes=${Number(stateDb.wal_size_bytes || 0)}`,
    ].join("; ");
  }

  function longRunReliabilityStatus(snapshot = null) {
    const payload = longRunReliabilityPayload(snapshot);
    const continuous = payload.continuous_round_state || {};
    const pending = payload.pending_publish_backpressure || {};
    const workers = payload.worker_slots || {};
    if (continuous.blocked || pending.blocked || Number(workers.stale_heartbeat_count || 0) > 0) return "blocked";
    if (Number(continuous.consecutive_unexpected_round_failures || 0) > 0 || Number(payload?.state_db?.wal_size_bytes || 0) >= Number(payload?.state_db?.wal_review_bytes || 0)) return "warning";
    return Object.keys(payload).length ? "ok" : "unknown";
  }

  function liveRunStripItems({ snapshot = null, diagnostics = null, closeReadiness = null, stdoutTail = null } = {}) {
    const progress = snapshot?.progress && typeof snapshot.progress === "object" ? snapshot.progress : {};
    const currentWork = snapshot?.current_work && typeof snapshot.current_work === "object" ? snapshot.current_work : {};
    const workerRows = progressWorkerRows(snapshot, diagnostics);
    const etaRows = progressEtaRows(snapshot, diagnostics);
    const ffmpegPayload = progressFfmpegPayload(snapshot, diagnostics);
    const csvRerun = csvRerunActivityEvidence({ snapshot, diagnostics, stdoutTail });
    const state = snapshot?.pipeline_state || closeReadiness?.state || progress.Status || "unknown";
    const stage = currentWork.current_stage_label || currentWork.phase_label || progress.CurrentStage || progress.Status || "No active work";
    const percent = currentWork.percent_label || (progress.CurrentStagePercent !== undefined && progress.CurrentStagePercent !== null && progress.CurrentStagePercent !== "" ? `${formatProgressValue(progress.CurrentStagePercent)}%` : "");
    const file = currentWork.item_label || progress.CurrentFileDisplay || progress.CurrentFile || progress.InputFile || "";
    const route = currentWork.route_label || progress.CurrentRoute || progress.Route || "";
    const queue = currentWork.queue_position_label || activeWorkQueueLine(progress).replace(/^Queue position:\s*/i, "");
    const updated = compactUpdatedAgeText(progress.LastUpdate || progress.UpdatedAt || progress.updated_at);
    const eta = etaRows.find((row) => row && row.eta_seconds !== undefined && row.eta_seconds !== null);
    const activeWorker = workerRows.find((row) => ["running", "active", "warning"].includes(String(row.status_state || row.status || "").toLowerCase())) || workerRows[0];
    const reliabilitySummary = longRunReliabilitySummary(snapshot);
    const reliabilityStatus = longRunReliabilityStatus(snapshot);
    const nowValue = currentWork.summary_label || currentWork.latest_evidence_label || stage || "No active work";
    const nowHint = [
      file ? `Current item: ${file}` : "",
      currentWork.latest_event_label ? `Latest event: ${currentWork.latest_event_label}` : "",
      currentWork.next_stage_label ? `Next: ${currentWork.next_stage_label}` : "",
      currentWork.missing_evidence_label || "",
    ].filter(Boolean).join(" | ");
    const nowItem = liveRunItem("Now", nowValue, nowHint, currentWork.evidence_status === "waiting" ? "warning" : "running");
    const items = [
      liveRunItem("Stage", [formatProgressValue(stage), percent].filter(Boolean).join(" "), activeWorkFinalizingLine(progress), progressLooksFinalizing(progress) ? "warning" : "running"),
      liveRunItem("File", file || "No current file", file ? "Current backend-reported item." : "No current file evidence loaded.", file ? "running" : "empty"),
      liveRunItem("Route", route ? formatProgressValue(route) : "No route", progress.RouteReason || progress.CurrentRouteReason || "Backend route evidence only.", route ? "ok" : "empty"),
      liveRunItem("Queue", queue || "No queue position", "Display filters do not define Launch scope.", queue ? "ok" : "empty"),
      liveRunItem("ETA", eta ? formatEtaSeconds(eta.eta_seconds) : "Unavailable", eta?.basis || progressEtaSummaryLine(snapshot, diagnostics), eta ? "ok" : "warning"),
      liveRunItem("Last update", updated || "Not loaded", updated ? "Runtime progress update age." : "No runtime progress timestamp loaded.", updated ? "ok" : "unknown"),
      liveRunItem("FFmpeg", ffmpegPayload?.status || "idle", progressFfmpegSummaryLine(snapshot, diagnostics), ffmpegPayload?.status === "unavailable" ? "warning" : "ok"),
      liveRunItem("Worker", activeWorker ? formatWorkerProgressRow(activeWorker) : "No active worker", progressWorkerSummaryLine(snapshot, diagnostics), activeWorker ? "running" : "empty"),
      liveRunItem("Reliability", reliabilityStatus === "ok" ? "Ready" : reliabilityStatus === "blocked" ? "Blocked" : reliabilityStatus === "warning" ? "Review" : "Unknown", reliabilitySummary || "Long-run reliability counters are backend-owned and read-only.", reliabilityStatus),
      liveRunItem("Close", closeReadiness ? (closeReadiness.safe_to_close ? "Safe" : "Not safe") : "Unknown", closeReadiness?.reason || "Close-readiness is backend-owned.", closeReadiness?.safe_to_close ? "ok" : closeReadiness?.safe_to_close === false ? "blocked" : "unknown"),
    ];
    if (csvRerun.hasEvidence) {
      items.unshift(
        liveRunItem("CSV rows", csvRerun.plannedRows || "CSV rerun active", "From the bounded last stdout log.", csvRerun.plannedRows ? "ok" : "running"),
        liveRunItem(
          "Importing",
          csvRerun.currentImport || currentWork.latest_evidence_label || currentWork.missing_evidence_label || "Waiting for backend evidence",
          csvRerun.currentImport ? "Current CSV staging/import line." : "Backend active-work evidence replaces missing CSV import text.",
          csvRerun.currentImport || currentWork.latest_evidence_label ? "running" : "warning"
        ),
        liveRunItem("Last imported", csvRerun.lastImported || "No staged copy yet", "Most recent completed stage copy in the stdout tail.", csvRerun.lastImported ? "ok" : "empty"),
        liveRunItem("Processing", csvRerun.processing || "Waiting for processing evidence", "Processing starts after CSV staging/import completes.", csvRerun.processing && !csvRerun.processing.startsWith("Not processing yet") ? "running" : "warning"),
      );
    }
    items.unshift(nowItem);
    const status = liveRunStatus({ snapshot, diagnostics, closeReadiness, stdoutTail });
    if (status.state === "warning") {
      items.unshift(liveRunItem("Review", "Stale progress", "No update from runtime progress. Inspect Diagnostics, ActiveJobs, Run Logs, and Last Stderr before stopping or closing.", "warning"));
    }
    return items;
  }

  const liveRunStripTargets = [
    { statusId: "home-live-run-status", bodyId: "home-live-run-strip" },
    { statusId: "launch-live-run-status", bodyId: "launch-live-run-strip" },
    { statusId: "pending-live-run-status", bodyId: "pending-live-run-strip" },
    { statusId: "diagnostics-live-run-status", bodyId: "diagnostics-live-run-strip" },
  ];

  const liveRunQuickLinks = {
    stage: { page: "live", label: "Open Telemetry for live run stage" },
    file: { page: "live", label: "Open Telemetry for live run file" },
    eta: { page: "live", label: "Open Telemetry for live run ETA" },
    "last update": { page: "live", label: "Open Telemetry for last update" },
    state: { page: "live", label: "Open Telemetry for live state" },
    route: { page: "queue", label: "Open Queue route evidence" },
    queue: { page: "queue", label: "Open Queue" },
    ffmpeg: { page: "diagnostics", diagTab: "logs", label: "Open Diagnostics logs" },
    worker: { page: "network", label: "Open Network workers" },
    reliability: { page: "diagnostics", diagTab: "triage", label: "Open Diagnostics reliability evidence" },
    close: { page: "diagnostics", diagTab: "readiness", label: "Open Diagnostics readiness" },
  };

  const homeLiveRunSummaryLabels = ["Review", "Now", "Stage", "Processing", "CSV rows", "File"];
  const homeLiveRunFileLabels = ["File", "Processing", "Importing", "Last imported"];
  const homeLiveRunDefaultFacts = ["Route", "Queue", "ETA", "Last update", "Close"];
  const homeLiveRunCsvFacts = ["CSV rows", "Queue", "ETA", "Last update", "Close"];
  const homeLiveRunFallbackFacts = ["Processing", "Route", "FFmpeg", "Worker", "Reliability"];

  function liveRunQuickLink(item) {
    return liveRunQuickLinks[String(item?.label || "").trim().toLowerCase()] || null;
  }

  function createLiveRunChipNode(item, { compact = false } = {}) {
    const quickLink = liveRunQuickLink(item);
    const node = document.createElement("span");
    node.className = compact ? "live-run-chip live-run-chip-compact" : "live-run-chip";
    node.dataset.status = item.status;
    if (quickLink) {
      node.setAttribute("role", "button");
      node.setAttribute("tabindex", "0");
      node.dataset.uiQuickLink = "";
      node.dataset.quickLinkPage = quickLink.page;
      if (quickLink.diagTab) node.dataset.quickLinkDiagTab = quickLink.diagTab;
      const ariaLabel = `${quickLink.label}: ${item.label} ${item.value}`.trim();
      node.setAttribute("aria-label", ariaLabel);
      node.title = ariaLabel;
    }
    const label = document.createElement("span");
    label.className = "live-run-chip-label";
    label.textContent = item.label;
    const value = document.createElement("strong");
    value.className = "live-run-chip-value";
    value.textContent = item.value;
    node.append(label, value);
    if (item.hint) {
      const hint = document.createElement("span");
      hint.className = "live-run-chip-hint";
      hint.textContent = item.hint;
      if (!quickLink) node.title = item.hint;
      node.appendChild(hint);
    }
    return node;
  }

  function findLiveRunItem(items, labels) {
    const wanted = new Set(labels.map((label) => String(label).toLowerCase()));
    return items.find((item) => wanted.has(String(item?.label || "").toLowerCase())) || null;
  }

  function progressPercentFromText(value) {
    const match = String(value || "").match(/(\d+(?:\.\d+)?)\s*%/);
    if (!match) return null;
    const number = Number(match[1]);
    return Number.isFinite(number) ? Math.max(0, Math.min(100, number)) : null;
  }

  function homeLiveRunFactItems(items) {
    const hasCsv = items.some((item) => item.label === "CSV rows");
    const preferred = hasCsv ? homeLiveRunCsvFacts : homeLiveRunDefaultFacts;
    const selected = [];
    const addByLabel = (label) => {
      const item = findLiveRunItem(items, [label]);
      if (item && !selected.includes(item)) selected.push(item);
    };
    preferred.forEach(addByLabel);
    homeLiveRunFallbackFacts.forEach((label) => {
      if (selected.length < 5) addByLabel(label);
    });
    return selected.slice(0, 5);
  }

  function renderHomeLiveRunMonitor(body, status, items) {
    body.classList.add("live-run-monitor");
    const summaryItem = findLiveRunItem(items, homeLiveRunSummaryLabels) || items[0] || liveRunItem("State", status.label, "", status.state);
    const fileItem = findLiveRunItem(items, homeLiveRunFileLabels);
    const factItems = homeLiveRunFactItems(items);
    const percent = progressPercentFromText(summaryItem.value) ?? progressPercentFromText(findLiveRunItem(items, ["Processing"])?.value);

    const summary = document.createElement("section");
    summary.className = "live-run-monitor-summary";
    summary.dataset.state = status.state;
    summary.dataset.status = summaryItem.status || status.state || "unknown";

    const eyebrow = document.createElement("div");
    eyebrow.className = "live-run-monitor-eyebrow";
    const label = document.createElement("span");
    label.textContent = "Now";
    const state = document.createElement("strong");
    state.className = "live-run-monitor-state";
    state.dataset.state = status.state;
    state.textContent = status.label;
    eyebrow.append(label, state);

    const title = document.createElement("strong");
    title.className = "live-run-monitor-title";
    title.textContent = summaryItem.value;

    const subtitle = document.createElement("span");
    subtitle.className = "live-run-monitor-subtitle";
    subtitle.textContent = fileItem && fileItem !== summaryItem
      ? `${fileItem.label}: ${fileItem.value}`
      : summaryItem.hint || "Backend live-run state loaded.";

    summary.append(eyebrow, title, subtitle);
    if (percent !== null) {
      const meter = document.createElement("div");
      meter.className = "live-run-monitor-meter";
      meter.setAttribute("role", "progressbar");
      meter.setAttribute("aria-label", `${summaryItem.label} progress`);
      meter.setAttribute("aria-valuemin", "0");
      meter.setAttribute("aria-valuemax", "100");
      meter.setAttribute("aria-valuenow", String(Math.round(percent)));
      const fill = document.createElement("span");
      fill.style.width = `${percent}%`;
      meter.appendChild(fill);
      summary.appendChild(meter);
    }

    const facts = document.createElement("div");
    facts.className = "live-run-monitor-facts";
    factItems.forEach((item) => facts.appendChild(createLiveRunChipNode(item, { compact: true })));

    const details = document.createElement("details");
    details.className = "live-run-monitor-details";
    const detailsSummary = document.createElement("summary");
    detailsSummary.textContent = `Evidence details (${items.length})`;
    const detailGrid = document.createElement("div");
    detailGrid.className = "live-run-monitor-detail-grid";
    items.forEach((item) => detailGrid.appendChild(createLiveRunChipNode(item, { compact: true })));
    details.append(detailsSummary, detailGrid);

    body.replaceChildren(summary, facts, details);
  }

  function liveRunHandoffLines(context = {}, status = liveRunStatus(context), items = liveRunStripItems(context)) {
    const active = status.state === "running";
    const review = status.state === "warning";
    const stage = items.find((item) => item.label === "Stage")?.value || "No stage";
    const file = items.find((item) => item.label === "File")?.value || "No current file";
    const close = items.find((item) => item.label === "Close")?.value || "Unknown";
    const csvRerun = csvRerunActivityEvidence(context);
    const next = review
      ? "Open Diagnostics, Active Jobs, Run Logs, and Last Stderr before stopping or closing."
      : active
        ? "Monitor Run Progress and wait for close-readiness to report safe before closing."
        : "No active work is reported; refresh before starting a long unattended operation.";
    const csvLines = csvRerun.hasEvidence ? [
      `CSV rerun: ${csvRerun.plannedRows || "active"}.`,
      `Importing: ${csvRerun.currentImport || "no active copy line in stdout tail"}.`,
      `Last imported: ${csvRerun.lastImported || "none in stdout tail"}.`,
      `Processing: ${csvRerun.processing || "waiting for processing evidence"}.`,
      `Latest stdout: ${csvRerun.latestLine || "none"}.`,
    ] : [];
    return [
      `Run state: ${status.label}; stage=${stage}; file=${file}; close=${close}.`,
      ...csvLines,
      `Safe next step: ${next}`,
      "Mutation guardrail: this handoff is read-only and cannot start, stop, drain, publish, rename, or touch media.",
    ];
  }

  function renderLiveRunStrip(context = {}, targets = liveRunStripTargets) {
    const status = liveRunStatus(context);
    const items = liveRunStripItems(context);
    targets.forEach((target) => {
      const statusNode = byId(target.statusId);
      if (statusNode) {
        statusNode.textContent = status.label;
        statusNode.dataset.state = status.state;
      }
      const body = byId(target.bodyId);
      if (!body) return;
      body.classList.toggle("live-run-monitor", target.bodyId === "home-live-run-strip");
      if (target.bodyId === "home-live-run-strip") {
        renderHomeLiveRunMonitor(body, status, items);
        return;
      }
      body.replaceChildren();
      items.forEach((item) => body.appendChild(createLiveRunChipNode(item)));
    });
    setText("home-run-state-handoff", liveRunHandoffLines(context, status, items).join("\n"));
  }

  function activeWorkNextStep({ activeJobs, closeReadiness, state }) {
    if (activeJobs.length || closeReadiness?.safe_to_close === false) {
      return "Inspect Progress Details, Diagnostics > ActiveJobs, and Run Logs before closing or starting more work.";
    }
    const normalized = String(state || "").toLowerCase();
    if (["processing", "running", "active", "publishing"].includes(normalized)) {
      return "Monitor Progress Details and wait for close-readiness to report safe before exiting.";
    }
    return "No active work indicators are currently reported.";
  }

  function renderHomeActiveWork({ snapshot = null, diagnostics = null, closeReadiness = null, stdoutTail = null } = {}) {
    const activeJobs = Array.isArray(diagnostics?.active_jobs) ? diagnostics.active_jobs.filter(Boolean) : [];
    const workerRows = progressWorkerRows(snapshot, diagnostics);
    const progress = snapshot?.progress && typeof snapshot.progress === "object" ? snapshot.progress : {};
    const currentWork = snapshot?.current_work && typeof snapshot.current_work === "object" ? snapshot.current_work : {};
    const auditProgress = snapshot?.audit_progress && typeof snapshot.audit_progress === "object" ? snapshot.audit_progress : {};
    const state = snapshot?.pipeline_state || closeReadiness?.state || "unknown";
    const csvRerun = csvRerunActivityEvidence({ snapshot, diagnostics, stdoutTail });
    const stateActive = ["processing", "running", "active", "publishing"].includes(String(state || "").toLowerCase());
    const active = activeJobs.length > 0 || closeReadiness?.safe_to_close === false || stateActive || csvRerun.hasEvidence || Boolean(currentWork.summary_label || currentWork.latest_evidence_label);
    setProgressPanelStatus("home-active-work-status", active ? "Active work" : closeReadiness?.safe_to_close === true ? "Idle" : "Checking", active ? "running" : closeReadiness?.safe_to_close === true ? "ok" : "loading");
    const lines = [
      currentWork.summary_label ? `Now: ${currentWork.summary_label}` : "",
      currentWork.item_label ? `Current item: ${currentWork.item_label}` : "",
      currentWork.current_stage_label ? `Current stage: ${currentWork.current_stage_label}` : "",
      currentWork.latest_evidence_label ? `Latest evidence: ${currentWork.latest_evidence_label}` : "",
      currentWork.latest_event_label ? `Latest event: ${currentWork.latest_event_label}` : "",
      currentWork.missing_evidence_label ? `Missing evidence: ${currentWork.missing_evidence_label}` : "",
      currentWork.next_stage_label ? `Next stage: ${currentWork.next_stage_label}` : "",
      `Pipeline state: ${state}`,
      `Close readiness: ${closeReadiness ? (closeReadiness.safe_to_close ? "safe" : "active work") : "unknown"}`,
      closeReadiness?.reason ? `Close reason: ${closeReadiness.reason}` : "",
      `ActiveJobs: ${activeJobs.length || 0}`,
      progressWorkerSummaryLine(snapshot, diagnostics),
      progressEtaSummaryLine(snapshot, diagnostics),
      longRunReliabilitySummary(snapshot) ? `Long-run reliability: ${longRunReliabilitySummary(snapshot)}` : "",
      csvRerun.hasEvidence ? `CSV rerun: ${csvRerun.plannedRows || "active"}` : "",
      csvRerun.currentImport ? `Importing: ${csvRerun.currentImport}` : "",
      csvRerun.lastImported ? `Last imported: ${csvRerun.lastImported}` : "",
      csvRerun.processing ? `Processing: ${csvRerun.processing}` : "",
      csvRerun.latestLine ? `Latest stdout: ${csvRerun.latestLine}` : "",
      ...workerRows.slice(0, 4).map((row) => `- ${formatWorkerProgressRow(row)}`),
      ...activeJobs.slice(0, 5).map((item) => `- ${item}`),
      activeJobs.length > 5 ? `- and ${activeJobs.length - 5} more ActiveJobs row(s)` : "",
      activeWorkProgressLine(progress),
      activeWorkRouteLine(progress),
      activeWorkQueueLine(progress),
      activeWorkControlLine(progress),
      activeWorkFinalizingLine(progress),
      auditProgress.status || auditProgress.Status ? `Audit: ${formatProgressValue(auditProgress.status || auditProgress.Status)}` : "",
      latestEventLine(diagnostics, snapshot),
      "",
      `Next step: ${currentWork.next_stage_label || activeWorkNextStep({ activeJobs, closeReadiness, state })}`,
    ].filter((line) => line !== "");
    setText("home-active-work-summary", lines.join("\n"));
  }

  /**
   * Public namespace for the shared progress module.
   * Progress consumers should use this namespace; no flat window.* exports remain for this module.
   */
  window.mediaPipelineProgressView = {
    formatProgressUpdatedAt,
    renderProgressBarsInto,
    renderProgressBars,
    runTimelineItems,
    auditProgressBars,
    auditProgressStatus,
    auditProgressSummaryLines,
    renderAuditProgressInto,
    renderProgressDetails,
    renderPipelineEvents,
    renderProgressEvidence,
    progressWorkerPayload,
    progressWorkerRows,
    progressWorkerSummaryLine,
    progressFfmpegPayload,
    progressFfmpegRows,
    progressFfmpegSummaryLine,
    progressEtaPayload,
    progressEtaRows,
    progressEtaSummaryLine,
    csvRerunTailEvidence,
    csvRerunActivityEvidence,
    csvRerunTerminalLine,
    progressEvidenceRows,
    progressEvidenceStatus,
    progressEvidenceSummaryLines,
    progressEvidenceDetailLines,
    renderDiagnosticsProgress,
    renderLiveRunStrip,
    liveRunStripItems,
    liveRunStatus,
    diagnosticsProgressRows,
    diagnosticsProgressStatus,
    diagnosticsProgressSummaryLines,
    renderHomeActiveWork,
    activeWorkNextStep,
    activeWorkProgressLine,
    activeWorkRouteLine,
    activeWorkQueueLine,
    activeWorkControlLine,
    latestEventLine,
  };
})();
