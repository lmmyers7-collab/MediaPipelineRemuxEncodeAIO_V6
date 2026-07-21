(function () {
  "use strict";

  const STAGE_LABELS = Object.freeze({
    accepted: "Accepted into run",
    source_discovery: "Source discovery / scanning",
    copy_to_scratch: "Copy to scratch",
    probe: "Probe",
    route_decision: "Route decision",
    audio: "Audio policy",
    subtitles: "Subtitle policy / work",
    transcode: "Encode or remux",
    mux: "Mux",
    verification: "Verification",
    sidecar_writing: "Sidecar writing",
    publish: "Direct publish or park",
    final_evidence: "Final run evidence",
  });
  const object = (value) => value && typeof value === "object" && !Array.isArray(value) ? value : {};

function text(value, fallback = "") {
    const normalized = value === null || value === undefined ? "" : String(value).trim();
    return normalized || fallback;
  }

function humanize(value, fallback = "Unknown") {
    const normalized = text(value);
    if (!normalized) return fallback;
    return normalized
      .replace(/[_-]+/g, " ")
      .replace(/\s+/g, " ")
      .trim()
      .replace(/\b\w/g, (letter) => letter.toUpperCase());
  }

function stageLabel(stageId) {
    return STAGE_LABELS[text(stageId)] || humanize(stageId, "Unknown stage");
  }

function formatTimestamp(value, fallback = "—") {
    const normalized = text(value);
    if (!normalized) return fallback;
    const parsed = Date.parse(normalized);
    if (!Number.isFinite(parsed)) return normalized;
    try {
      return new Date(parsed).toLocaleString([], {
        year: "numeric",
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      });
    } catch (_error) {
      return normalized;
    }
  }

function formatAge(value) {
    const seconds = Number(value);
    if (!Number.isFinite(seconds) || seconds < 0) return "age unknown";
    if (seconds < 1) return "just now";
    if (seconds < 60) return `${Math.floor(seconds)}s ago`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${Math.floor(seconds % 60)}s ago`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m ago`;
    return `${Math.floor(seconds / 86400)}d ago`;
  }

function formatDurationSeconds(value) {
    const seconds = Number(value);
    if (!Number.isFinite(seconds) || seconds < 0) return "";
    const whole = Math.floor(seconds);
    if (whole < 60) return `${whole}s`;
    if (whole < 3600) return `${Math.floor(whole / 60)}m ${whole % 60}s`;
    return `${Math.floor(whole / 3600)}h ${Math.floor((whole % 3600) / 60)}m`;
  }

function trackTimingLabel(track) {
    const startedAt = Date.parse(text(track?.started_at));
    if (!Number.isFinite(startedAt)) return "";
    const completedAt = Date.parse(text(track?.completed_at));
    const end = Number.isFinite(completedAt) ? completedAt : Date.now();
    if (end < startedAt) return "";
    const duration = formatDurationSeconds((end - startedAt) / 1000);
    if (!duration) return "";
    return Number.isFinite(completedAt) ? `Duration ${duration}` : `Elapsed ${duration}`;
  }

function trackTimelineLabel(track) {
    return [
      text(track?.started_at) ? `Started ${formatTimestamp(track.started_at)}` : "",
      text(track?.updated_at) ? `Updated ${formatTimestamp(track.updated_at)}` : "",
      text(track?.completed_at) ? `Completed ${formatTimestamp(track.completed_at)}` : "",
      trackTimingLabel(track),
    ].filter(Boolean).join(" · ");
  }

function collectionStateLabel(collection) {
    const record = object(collection);
    return [
      humanize(record.state),
      record.policy_final === true ? "Terminal policy evidence" : "Policy evidence not terminal",
    ].join(" · ");
  }

function progressUnitLabel(value) {
    const normalized = text(value).toLowerCase();
    if (!normalized || normalized === "unknown") return "";
    const known = new Set(["items", "pages", "cues", "frames", "seconds", "bytes", "percent"]);
    return known.has(normalized) ? normalized : "";
  }

function progressLabel(progress, unit = "") {
    const evidence = object(progress);
    const kind = text(evidence.kind, "none");
    const unitLabel = progressUnitLabel(unit);
    if (kind === "indeterminate") return `Working${unitLabel ? ` (${unitLabel})` : ""} · progress is indeterminate`;
    if (kind !== "determinate") return "";
    const numerator = Number(evidence.numerator);
    const denominator = Number(evidence.denominator);
    if (!Number.isFinite(numerator) || !Number.isFinite(denominator) || denominator <= 0 || numerator < 0 || numerator > denominator) {
      return "Progress evidence invalid";
    }
    const percent = (numerator / denominator) * 100;
    return `${numerator} / ${denominator}${unitLabel ? ` ${unitLabel}` : ""} · ${Math.round(percent * 10) / 10}%`;
  }

function subtitleStepLabel(track) {
    const stepIndex = Number(track?.step_index);
    const stepTotal = Number(track?.step_total);
    const stepName = text(track?.step_name);
    const position = Number.isInteger(stepIndex) && Number.isInteger(stepTotal) && stepTotal > 0 && stepIndex >= 0 && stepIndex <= stepTotal
      ? `Step ${stepIndex} of ${stepTotal}`
      : "";
    return [position, stepName ? humanize(stepName) : ""].filter(Boolean).join(" · ");
  }

function subtitleCueLabel(track) {
    if (track?.cue_count === null || track?.cue_count === undefined || track?.cue_count === "") return "";
    const count = Number(track.cue_count);
    return Number.isInteger(count) && count >= 0 ? `Cues ${count}` : "Cue count evidence invalid";
  }

function evidenceLabel(evidence) {
    const record = object(evidence);
    return [
      text(record.source) ? `Source: ${record.source}` : "Source: unknown",
      text(record.provenance) ? `Provenance: ${humanize(record.provenance)}` : "Provenance: unknown",
      text(record.recorded_at) ? `Recorded: ${formatTimestamp(record.recorded_at)}` : "Timestamp: unknown",
    ].join(" · ");
  }

function routeDisplay(route, fallbackLabel, fallbackReasonLabel) {
    const record = object(route);
    const stateValue = text(record.state, "unknown");
    const available = stateValue === "available" && Boolean(text(record.value));
    const explainsUnavailable = stateValue === "unknown" || stateValue === "not_applicable";
    return {
      label: text(record.label, fallbackLabel),
      reasonLabel: text(record.reason_label, fallbackReasonLabel),
      state: stateValue,
      value: available ? text(record.value) : "",
      reason: available || explainsUnavailable ? text(record.reason) : "",
      reasonCode: available || explainsUnavailable ? text(record.reason_code) : "",
      evidence: object(record.evidence),
    };
  }

function routeUnavailableLabel(route) {
    if (route.state === "awaiting_evidence") return "Awaiting backend evidence";
    if (route.state === "not_applicable") return "Not applicable";
    return "Unknown";
  }

  window.__runMonitorFormatters = Object.freeze({
    text,
    humanize,
    stageLabel,
    formatTimestamp,
    formatAge,
    formatDurationSeconds,
    trackTimingLabel,
    trackTimelineLabel,
    collectionStateLabel,
    progressUnitLabel,
    progressLabel,
    subtitleStepLabel,
    subtitleCueLabel,
    evidenceLabel,
    routeDisplay,
    routeUnavailableLabel
  });
})();
