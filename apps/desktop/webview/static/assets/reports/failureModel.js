// reports/failureModel.js
// Pure and state-backed failure helpers for reportsView.js. Rendering and
// backend command flows remain in reportsView.js.

(function () {
  "use strict";

  function noop() {}

  function createReportsFailureModelModule(deps = {}) {
    const reportsState = deps.state && typeof deps.state === "object" ? deps.state : {};
    const failureMarkerModeActive = typeof deps.failureMarkerModeActive === "function" ? deps.failureMarkerModeActive : function () { return false; };
    const reportAddDiagnosticsAction = typeof deps.reportAddDiagnosticsAction === "function" ? deps.reportAddDiagnosticsAction : noop;
    const reportCountLabel = typeof deps.reportCountLabel === "function" ? deps.reportCountLabel : function (count, singular, plural = `${singular}s`) {
      const numeric = Number(count || 0) || 0;
      return `${numeric} ${numeric === 1 ? singular : plural}`;
    };
    const reportCompactCountPairs = typeof deps.reportCompactCountPairs === "function" ? deps.reportCompactCountPairs : function () { return "None"; };
    const reportCountBy = typeof deps.reportCountBy === "function" ? deps.reportCountBy : function () { return {}; };
    const reportFormatCounts = typeof deps.reportFormatCounts === "function" ? deps.reportFormatCounts : function () { return "none"; };
    const reportHumanLabel = typeof deps.reportHumanLabel === "function" ? deps.reportHumanLabel : function (value, fallback = "None") { return value || fallback; };
    const reportNumber = typeof deps.reportNumber === "function" ? deps.reportNumber : function (value) { const numeric = Number(value); return Number.isFinite(numeric) ? numeric : 0; };
    const reportOwnerPage = typeof deps.reportOwnerPage === "function" ? deps.reportOwnerPage : function () { return null; };
    const reportPreviewLoaded = typeof deps.reportPreviewLoaded === "function" ? deps.reportPreviewLoaded : function (_payload, rows) { return Array.isArray(rows) && rows.length > 0; };
    const reportSortedCountEntries = typeof deps.reportSortedCountEntries === "function" ? deps.reportSortedCountEntries : function () { return []; };
    const selectedFailureGroupMarkerPaths = typeof deps.selectedFailureGroupMarkerPaths === "function" ? deps.selectedFailureGroupMarkerPaths : function () { return []; };

  function failureEmptyStateMessage(failures, rows) {
      if (failures.error) {
        return `Failure preview unavailable: ${failures.error}. Open Diagnostics > Failure Reports or Failure Markers.`;
      }
      const warnings = Array.isArray(failures.warnings) ? failures.warnings.filter(Boolean) : [];
      if (warnings.length) {
        return `Failure preview loaded with warning: ${warnings.join(" | ")}`;
      }
      if (!rows.length) {
        return "No failure rows found for the selected source. If a job failed recently, check marker source mode and Run Logs.";
      }
      return "No failure rows available.";
    }

  function failureRowKey(item) {
      if (item?.row_key) return String(item.row_key).toLowerCase();
      return [
        item?.source_json || "",
        item?.source_path || "",
        item?.stage || "",
        item?.error_code || "",
        item?.recorded_at || "",
      ].join("\u001f").toLowerCase();
    }

  function failureResolutionGroupKey(group) {
      return String(group?.group_key || "").toLowerCase();
    }

  function failureGroupJournalKey(group) {
      return String(group?.journal_key || group?.group_key || "").trim();
    }

  function failureGroupLifecycleState(group) {
      return String(group?.lifecycle_state || "new").toLowerCase();
    }

  function failureGroupSearchText(group) {
      return [
        group?.status_label,
        group?.lifecycle_label,
        group?.lifecycle_state,
        group?.error_code,
        group?.stage,
        group?.owner,
        group?.suggested_action,
        group?.cause,
        group?.safe_next_action,
        ...(Array.isArray(group?.evidence_lines) ? group.evidence_lines : []),
      ].filter(Boolean).join(" ").toLowerCase();
    }

  function failureResolutionGroupForRow(item) {
      const rowKey = failureRowKey(item);
      if (!rowKey) return null;
      return reportsState.lastFailureResolutionGroups.find((group) => {
        const keys = Array.isArray(group?.affected_row_keys) ? group.affected_row_keys : [];
        return keys.map((key) => String(key || "").toLowerCase()).includes(rowKey);
      }) || null;
    }

  function failureResolutionFallbackGroups(rows) {
      const groups = new Map();
      (Array.isArray(rows) ? rows : []).forEach((row) => {
        const owner = failureActionOwner(row);
        const suggested = failureSuggestedActionText(row);
        const key = [
          String(row?.error_code || "NO_CODE").toLowerCase(),
          String(row?.stage || "unknown-stage").toLowerCase(),
          owner.toLowerCase(),
          suggested.toLowerCase(),
        ].join("\u001f");
        const markerPaths = failureClearMarkerPathsForRow(row);
        const existing = groups.get(key) || {
          schema_version: "desktop_failure_resolution_group.v1",
          group_key: key,
          status_label: failureStatusLabel(row),
          severity: failureSeverity(row),
          error_code: row?.error_code || "NO_CODE",
          stage: row?.stage || "unknown-stage",
          owner,
          owner_page: reportOwnerPage(owner)?.page || "",
          suggested_action: suggested,
          cause: failurePlainSummaryText(row),
          safe_next_action: row?.retry_safe_next_action || suggested,
          row_count: 0,
          affected_row_keys: [],
          affected_sources: [],
          sample_rows: [],
          clearable_marker_paths: [],
          clearable_count: 0,
          marker_count: 0,
          blocking_count: 0,
          retryable_count: 0,
          operator_required_count: 0,
          permanent_count: 0,
          transient_count: 0,
          diagnostic_targets: failureDiagnosticsActionsForRow(row),
          primary_action: {},
          journal_key: key,
          lifecycle_state: "new",
          lifecycle_label: "New",
          verification: {},
          playbook_steps: [],
          timeline: [],
          available_transitions: [],
          evidence_lines: [],
        };
        existing.row_count += 1;
        const rowKey = failureRowKey(row);
        if (rowKey && !existing.affected_row_keys.includes(rowKey)) existing.affected_row_keys.push(rowKey);
        const source = row?.lookup_title || row?.source_path || row?.source_json || "";
        if (source && !existing.affected_sources.includes(source)) existing.affected_sources.push(source);
        if (existing.sample_rows.length < 5) existing.sample_rows.push(row);
        failureEvidenceProofLines(row).forEach((line) => {
          if (existing.evidence_lines.length < 10 && !existing.evidence_lines.includes(line)) existing.evidence_lines.push(line);
        });
        markerPaths.forEach((markerPath) => {
          if (!existing.clearable_marker_paths.includes(markerPath)) existing.clearable_marker_paths.push(markerPath);
        });
        existing.clearable_count = existing.clearable_marker_paths.length;
        existing.marker_count = existing.clearable_marker_paths.length;
        const classification = String(row?.classification || "").toLowerCase();
        if (classification === "operator_required") existing.operator_required_count += 1;
        if (classification === "permanent") existing.permanent_count += 1;
        if (classification === "transient") existing.transient_count += 1;
        if (classification === "operator_required" || classification === "permanent" || String(row?.retry_status_state || "").toLowerCase() === "blocked") existing.blocking_count += 1;
        if (row?.retry_allowed === true || failureRetryStateForRow(row)?.retry_allowed) existing.retryable_count += 1;
        groups.set(key, existing);
      });
      return Array.from(groups.values()).map((group) => {
        const ownerPage = reportOwnerPage(group.owner);
        if (group.retryable_count > 0) {
          group.primary_action = { kind: "wait_for_backend_retry", label: "Wait for backend retry", page: "" };
        } else if (ownerPage) {
          group.primary_action = { kind: "open_owner_page", label: ownerPage.label === "Diagnostics" ? "Review in Diagnostics" : `Open ${ownerPage.label}`, page: ownerPage.page, owner: group.owner };
        } else if (group.clearable_count > 0) {
          group.primary_action = { kind: "clear_marker", label: "Clear errors", page: "" };
        } else {
          group.primary_action = { kind: "review_details", label: "Review details", page: "diagnostics" };
        }
        group.primary_action_label = group.primary_action.label;
        group.verification = {
          schema_version: "failure_resolution_verification.v1",
          active_marker_count: group.clearable_count,
          active_failure_row_count: group.row_count,
          blocking_count: group.blocking_count,
          retryable_count: group.retryable_count,
          clearable: group.clearable_count > 0,
          safe_to_resolve: group.clearable_count === 0,
          blockers: group.clearable_count > 0 ? ["Active backend error records still block retry."] : [],
        };
        group.playbook_steps = [
          { id: "review_evidence", label: "Review evidence", detail: "Read why it stopped and compare failure evidence.", status: "current" },
          { id: "primary_action", label: group.primary_action.label, detail: group.safe_next_action || "", status: "not_started" },
          { id: "verify_markers", label: "Verify active errors", detail: "Confirm whether backend error records still block retry.", status: group.clearable_count ? "blocked" : "done" },
        ];
        group.available_transitions = [
          { transition: "acknowledge", label: "Acknowledge", preview_required: false, disabled: false },
          { transition: "start_work", label: "Start work", preview_required: false, disabled: false },
        ];
        return group;
      });
    }

  function failureResolutionGroupsFromPayload(failures, rows) {
      const payloadGroups = Array.isArray(failures?.resolution_groups) ? failures.resolution_groups : [];
      if (payloadGroups.length) return payloadGroups;
      return failureResolutionFallbackGroups(rows);
    }

  function failureRowsForGroup(group) {
      const keys = new Set((Array.isArray(group?.affected_row_keys) ? group.affected_row_keys : []).map((key) => String(key || "").toLowerCase()));
      if (!keys.size) return Array.isArray(group?.sample_rows) ? group.sample_rows : [];
      return reportsState.lastFailureRows.filter((row) => keys.has(failureRowKey(row)));
    }

  function failureDisplayValue(value, fallback) {
      const text = String(value || "").trim();
      return text || fallback;
    }

  function failureClassificationText(item) {
      return failureDisplayValue(item?.classification || item?.class, "review");
    }

  function failureStageText(item) {
      return failureDisplayValue(item?.stage || item?.failure_stage || item?.error_stage, "review");
    }

  function failureReasonText(item) {
      return failureDisplayValue(item?.reason || item?.message || item?.error_message || item?.error, "Review failure evidence.");
    }

  function failureSuggestedActionText(item) {
      const triageFix = failureDisplayValue(item?.triage?.suggested_fix, "");
      if (triageFix) return triageFix;
      const explicit = failureDisplayValue(item?.suggested_action || item?.recommended_action || item?.next_step, "");
      if (explicit) return explicit;
      const classification = String(item?.classification || "").toLowerCase();
      if (classification === "transient") return "Clear errors, then rerun after confirming logs.";
      if (classification === "operator_required" || classification === "permanent") return "Open diagnostics and review the source before retry.";
      return "Review diagnostics before retry.";
    }

  function failureTriage(item) {
      return item?.triage && typeof item.triage === "object" ? item.triage : {};
    }

  function failureClearError(item) {
      return item?.clear_error && typeof item.clear_error === "object" ? item.clear_error : {};
    }

  function failureStatusLabel(item) {
      const triage = failureTriage(item);
      const label = failureDisplayValue(triage.status_label, "");
      if (label) return label;
      const retryState = failureRetryStateForRow(item);
      const classification = String(item?.classification || "").toLowerCase();
      if (retryState?.status_state === "blocked" || classification === "operator_required" || classification === "permanent") return "Needs operator";
      if (retryState?.retry_allowed) return "Will retry";
      if (item?.reason || item?.error_code) return "Review";
      return "Recorded";
    }

  function failureSeverity(item) {
      const triage = failureTriage(item);
      const severity = String(triage.severity || "").toLowerCase();
      if (["blocked", "error", "failed", "critical", "danger", "fatal"].includes(severity)) return "error";
      if (["warning", "warn", "retrying", "review", "stale"].includes(severity)) return "warning";
      if (["ok", "ready", "match", "completed"].includes(severity)) return "match";
      if (severity) return "unknown";
      const retryState = failureRetryStateForRow(item);
      if (retryState?.status_state === "blocked") return "blocked";
      if (retryState?.retry_allowed || item?.reason || item?.error_code) return "warning";
      return "info";
    }

  function failurePlainSummaryText(item) {
      return failureDisplayValue(failureTriage(item).plain_summary, failureReasonText(item));
    }

  function failureFileText(item) {
      return failureDisplayValue(item?.lookup_title || item?.source_path, "Unknown file");
    }

  function normalizeFailureMarkerPaths(paths) {
      const seen = new Set();
      const result = [];
      (Array.isArray(paths) ? paths : []).forEach((path) => {
        const markerPath = String(path || "").trim();
        const key = markerPath.toLowerCase();
        if (markerPath && !seen.has(key)) {
          seen.add(key);
          result.push(markerPath);
        }
      });
      return result;
    }

  function failureClearMarkerPathsForRow(item) {
      const clear = failureClearError(item);
      const markerPaths = normalizeFailureMarkerPaths([
        ...(Array.isArray(clear.marker_paths) ? clear.marker_paths : []),
        clear.marker_path,
      ]);
      if (markerPaths.length) return markerPaths;
      if (failureMarkerModeActive()) return normalizeFailureMarkerPaths([failureMarkerPath(item)]);
      return [];
    }

  function failureClearMarkerPath(item) {
      return failureClearMarkerPathsForRow(item)[0] || "";
    }

  function failureClearUnavailableReason(item) {
      return failureDisplayValue(
        failureClearError(item).unavailable_reason,
        "No active error record is available for this row."
      );
    }

  function failureRetryStatePayload(failures = reportsState.lastFailurePreviewPayload) {
      const payload = failures && typeof failures === "object" ? failures.retry_state : null;
      if (payload && typeof payload === "object" && payload.schema_version === "desktop_retry_state.v1") {
        return payload;
      }
      const rows = Array.isArray(failures?.rows) ? failures.rows : reportsState.lastFailureRows;
      const retryRows = (Array.isArray(rows) ? rows : []).map((row) => failureRetryStateFromRow(row));
      const retryable = retryRows.filter((row) => row.retry_allowed).length;
      const blocked = retryRows.filter((row) => row.status_state === "blocked").length;
      return {
        schema_version: "desktop_retry_state.v1",
        read_only: true,
        status_state: retryable ? "retrying" : blocked ? "blocked" : retryRows.length ? "warning" : "idle",
        row_count: retryRows.length,
        retryable_count: retryable,
        blocked_count: blocked,
        warning_count: retryRows.filter((row) => row.status_state === "warning").length,
        unavailable_count: retryRows.filter((row) => row.unavailable_reason).length,
        rows: retryRows,
        operator_guidance: "Retry state was derived from loaded failure rows because the backend retry_state payload was absent.",
      };
    }

  function failureRetryRows(failures = reportsState.lastFailurePreviewPayload) {
      const retry = failureRetryStatePayload(failures);
      return Array.isArray(retry.rows) ? retry.rows : [];
    }

  function failureRetryStateFromRow(item) {
      const classification = String(item?.classification || item?.class || "").toLowerCase();
      const attempt = Number(item?.retry_count || item?.RetryCount || 0) || 0;
      const maxAttempts = Number(item?.retry_limit || item?.RetryLimit || 0) || 0;
      const exhausted = maxAttempts > 0 && attempt >= maxAttempts;
      const retryable = item?.retryable === false || String(item?.retryable || "").toLowerCase() === "false" ? false : classification === "transient";
      const retryAllowed = Boolean(classification === "transient" && retryable && !exhausted);
      const status = retryAllowed ? (maxAttempts > 0 ? "retrying" : "warning") : (classification === "operator_required" || classification === "permanent" || exhausted || retryable === false) ? "blocked" : "warning";
      return {
        schema_version: "desktop_retry_state.v1",
        job_id: item?.job_id || item?.JobId || "",
        source_path: item?.source_path || "",
        source_json: item?.source_json || "",
        stage: item?.stage || "",
        error_code: item?.error_code || "",
        classification,
        attempt,
        max_attempts: maxAttempts,
        last_failure_reason: failureReasonText(item),
        retry_allowed: retryAllowed,
        retry_route_or_command: retryAllowed ? "automatic_next_queue_pass" : "none_exposed",
        safe_next_action: item?.retry_safe_next_action || failureSuggestedActionText(item),
        status_state: item?.retry_status_state || status,
        unavailable_reason: retryAllowed && maxAttempts === 0 ? "Retry limit was not reported." : "",
        read_only: true,
      };
    }

  function failureRetryStateForRow(item) {
      if (!item) return null;
      const itemKey = failureRowKey(item);
      const rows = failureRetryRows();
      const matched = rows.find((row) => {
        const candidate = {
          source_json: row.source_json || item.source_json || "",
          source_path: row.source_path || "",
          stage: row.stage || "",
          error_code: row.error_code || "",
          recorded_at: item.recorded_at || "",
        };
        return failureRowKey(candidate) === itemKey
          || (
            (!row.source_json || row.source_json === item.source_json)
            && (!row.source_path || row.source_path === item.source_path)
            && (!row.stage || row.stage === item.stage)
            && (!row.error_code || row.error_code === item.error_code)
          );
      });
      return matched || failureRetryStateFromRow(item);
    }

  function failureRetryPreviewSummaryLine(failures = reportsState.lastFailurePreviewPayload) {
      const retry = failureRetryStatePayload(failures);
      if (!retry || retry.status_state === "idle") return "Retry state: no failure rows.";
      return `Retry state: ${retry.status_state || "unknown"}; retryable=${retry.retryable_count || 0}; blocked=${retry.blocked_count || 0}; warning=${retry.warning_count || 0}.`;
    }

  function failureRetrySummaryText(item) {
      const retry = failureRetryStateForRow(item);
      if (!retry) return "No retry evidence";
      const attempt = Number(retry.attempt || 0);
      const maxAttempts = Number(retry.max_attempts || 0);
      const attemptText = maxAttempts > 0 ? `${attempt}/${maxAttempts}` : attempt > 0 ? `${attempt}/limit unknown` : "limit unknown";
      if (retry.retry_allowed) return `Auto retry (${attemptText})`;
      if (retry.status_state === "blocked") return `Blocked (${attemptText})`;
      return retry.unavailable_reason ? `Review (${retry.unavailable_reason})` : `Review (${attemptText})`;
    }

  function failureRetryDetailLines(item) {
      const retry = failureRetryStateForRow(item);
      if (!retry) {
        return [
          "Retry status: unavailable",
          "Retry evidence: no backend retry_state row matched this failure.",
        ];
      }
      return [
        `Retry status: ${retry.status_state || "unknown"}`,
        `Retry allowed: ${retry.retry_allowed ? "yes" : "no"}`,
        `Retry attempts: ${Number(retry.attempt || 0)}/${Number(retry.max_attempts || 0) || "limit unknown"}`,
        `Retry route/command: ${retry.retry_route_or_command || "none_exposed"}`,
        retry.job_id ? `Job ID: ${retry.job_id}` : "",
        retry.unavailable_reason ? `Retry evidence gap: ${retry.unavailable_reason}` : "",
        `Retry next action: ${retry.safe_next_action || failureSuggestedActionText(item)}`,
      ].filter(Boolean);
    }

  function failureEvidenceDetails(item) {
      const details = item?.evidence_details;
      return details && typeof details === "object" ? details : {};
    }

  function failureEvidenceStreamLine(row) {
      if (!row || typeof row !== "object") return "";
      if (row.label) return String(row.label);
      const source = String(row.source || "source");
      const index = row.index === undefined || row.index === null || String(row.index) === "-1" ? "video" : `v:${row.index}`;
      const codec = String(row.codec || "unknown");
      const width = Number(row.width || 0);
      const height = Number(row.height || 0);
      const resolution = width > 0 && height > 0 ? ` ${width}x${height}` : "";
      const attached = row.attached_picture === true ? " attached-picture" : "";
      return `${source} ${index} ${codec}${resolution}${attached}`.trim();
    }

  function failureEvidenceProofLines(item, options = {}) {
      const details = failureEvidenceDetails(item);
      const structured = details.structured === true;
      if (!structured && !options.includeFallback) return [];
      const lines = [];
      (Array.isArray(details.summary_lines) ? details.summary_lines : []).forEach((line) => {
        const text = String(line || "").trim();
        if (text) lines.push(text);
      });
      (Array.isArray(details.stream_rows) ? details.stream_rows : []).forEach((row) => {
        const text = failureEvidenceStreamLine(row);
        if (text) lines.push(text);
      });
      (Array.isArray(details.proof_fields) ? details.proof_fields : []).forEach((field) => {
        const label = String(field?.label || "").trim();
        const value = String(field?.value || "").trim();
        if (label && value) lines.push(`${label}: ${value}`);
      });
      const seen = new Set();
      return lines.filter((line) => {
        const key = line.toLowerCase();
        if (seen.has(key)) return false;
        seen.add(key);
        return true;
      }).slice(0, 10);
    }

  function failureRowSearchText(item) {
      return [
        item?.stage,
        item?.error_code,
        item?.classification,
        item?.reason,
        item?.suggested_action,
        item?.retry_safe_next_action,
        item?.lookup_title,
        item?.source_path,
        item?.media_type,
        ...failureEvidenceProofLines(item),
      ].filter(Boolean).join(" ").toLowerCase();
    }

  function failureActionOwner(item) {
      const text = failureRowSearchText(item);
      const classification = String(item?.classification || "").toLowerCase();
      if (text.includes("publish") || text.includes("pending")) return "Pending Publish";
      if (text.includes("queue")) return "Queue";
      if (text.includes("subtitle") || text.includes("bdpgs") || text.includes("tx3g") || text.includes("vobsub") || text.includes("ocr")) return "Settings";
      if (text.includes("audio") || text.includes("commentary") || text.includes("language")) return "Settings";
      if (text.includes("completed") || text.includes("output") || text.includes("manifest")) return "Completed";
      if (classification === "transient" || failureRetryStateForRow(item)?.retry_allowed) return "Launch";
      if (classification === "operator_required" || classification === "permanent") return "Manual review";
      return "Diagnostics";
    }

  function failureTableEvidenceText(item) {
      return [
        `Stage: ${failureStageText(item)}`,
        `Code: ${item?.error_code || "no-code"}`,
        `Class: ${failureClassificationText(item)}`,
        `Retry: ${failureRetrySummaryText(item)}`,
        `Error record: ${failureClearMarkerPathsForRow(item).length ? "available" : "not active"}`,
        ...failureEvidenceProofLines(item).slice(0, 8),
      ].join("\n");
    }

  function failureMatchesChip(item, chip) {
      const selected = String(chip || "all");
      if (selected === "all") return true;
      const text = failureRowSearchText(item);
      const retry = failureRetryStateForRow(item);
      const classification = String(item?.classification || "").toLowerCase();
      const group = failureResolutionGroupForRow(item);
      const lifecycle = failureGroupLifecycleState(group);
      if (selected === "needs_action") return ["operator_required", "permanent"].includes(classification) || retry?.status_state === "blocked" || ["new", "reopened"].includes(lifecycle);
      if (selected === "working") return lifecycle === "working" || lifecycle === "acknowledged";
      if (selected === "waiting_retry") return Boolean(retry?.retry_allowed) || lifecycle === "waiting_backend";
      if (selected === "ready_to_clear") return lifecycle === "ready_to_clear" || failureClearMarkerPathsForRow(item).length > 0;
      if (selected === "resolved_recently") return lifecycle === "resolved";
      if (selected === "needs_operator") return ["operator_required", "permanent"].includes(classification);
      if (selected === "will_retry") return Boolean(retry?.retry_allowed);
      if (selected === "blocked") return retry?.status_state === "blocked" || ["operator_required", "permanent"].includes(classification);
      if (selected === "warnings") return failureSeverity(item) === "warning" || retry?.status_state === "warning";
      return text.includes(selected);
    }

  function failureGroupMatchesChip(group, chip) {
      const selected = String(chip || "all");
      if (selected === "all") return true;
      const lifecycle = failureGroupLifecycleState(group);
      const retryable = Number(group?.retryable_count || 0) > 0;
      const blocked = Number(group?.blocking_count || 0) > 0;
      const clearable = Number(group?.clearable_count || 0) > 0;
      if (selected === "needs_action") return ["new", "reopened"].includes(lifecycle) || blocked;
      if (selected === "working") return ["acknowledged", "working"].includes(lifecycle);
      if (selected === "waiting_retry") return lifecycle === "waiting_backend" || retryable;
      if (selected === "ready_to_clear") return lifecycle === "ready_to_clear" || (clearable && !retryable);
      if (selected === "resolved_recently") return lifecycle === "resolved";
      return failureGroupSearchText(group).includes(selected);
    }

  function failureRecordedText(value) {
      const raw = String(value || "").trim();
      if (!raw) return "not recorded";
      const match = raw.match(/^(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2})/);
      if (match) return `${match[1]} ${match[2]}`;
      return raw.length > 22 ? raw.slice(0, 19).replace("T", " ") : raw;
    }

  function failureMarkerPath(item) {
      return String(item?.source_json || "").trim();
    }

  function failureCountsForRows(rows) {
      const counts = {
        operator_required_count: 0,
        permanent_count: 0,
        transient_count: 0,
      };
      (Array.isArray(rows) ? rows : []).forEach((item) => {
        const classification = String(item?.classification || item?.class || "").toLowerCase();
        if (classification === "operator_required") counts.operator_required_count += 1;
        if (classification === "permanent") counts.permanent_count += 1;
        if (classification === "transient") counts.transient_count += 1;
      });
      return counts;
    }

  function failureResolutionSummaryPayload() {
      const payload = reportsState.lastFailurePreviewPayload?.resolution_summary;
      if (payload && typeof payload === "object") return payload;
      const groups = Array.isArray(reportsState.lastFailureResolutionGroups) ? reportsState.lastFailureResolutionGroups : [];
      const primary = groups[0] || {};
      const clearable = normalizeFailureMarkerPaths(groups.flatMap((group) => group?.clearable_marker_paths || []));
      const blocking = groups.reduce((total, group) => total + Number(group?.blocking_count || 0), 0);
      const retryable = groups.reduce((total, group) => total + Number(group?.retryable_count || 0), 0);
      return {
        schema_version: "desktop_failure_resolution.v1",
        status: reportsState.lastFailureRows.length ? (blocking ? "blocked" : retryable ? "retrying" : "review") : "empty",
        status_label: reportsState.lastFailureRows.length ? (blocking ? "Needs operator" : retryable ? "Will retry" : "Review") : "No active failures",
        source_kind: reportsState.lastFailurePreviewPayload?.source_kind || "latest_json",
        source_mode_label: failureMarkerModeActive() ? "Active errors" : "Latest failure JSON",
        refresh_state: reportsState.lastFailureRows.length ? "loaded" : "empty",
        row_count: reportsState.lastFailureRows.length,
        group_count: groups.length,
        primary_group_key: primary?.group_key || "",
        primary_owner: primary?.owner || "Reports",
        primary_action: primary?.primary_action || {},
        primary_action_label: primary?.primary_action_label || primary?.primary_action?.label || "Review details",
        safe_next_action: primary?.safe_next_action || "Review grouped failure evidence.",
        blocking_count: blocking,
        retryable_count: retryable,
        clearable_count: clearable.length,
        warning_count: Array.isArray(reportsState.lastFailurePreviewPayload?.warnings) ? reportsState.lastFailurePreviewPayload.warnings.length : 0,
        lifecycle_counts: groups.reduce((counts, group) => {
          const state = failureGroupLifecycleState(group);
          counts[state] = (counts[state] || 0) + 1;
          return counts;
        }, {}),
        working_count: groups.filter((group) => ["acknowledged", "working"].includes(failureGroupLifecycleState(group))).length,
      };
    }

  function failureDiagnosticsActionsForRow(item) {
      const actions = [];
      reportAddDiagnosticsAction(actions, "tail", "latest_failure_report", "Read Latest Failure", "Read the backend failure report before rerun or cleanup decisions.");
      reportAddDiagnosticsAction(actions, "open", "latest_failure_json", "Open Failure JSON", "Inspect the structured failure payload behind this report row.");
      reportAddDiagnosticsAction(actions, "open", "failed_reports", "Open Failure Reports", "Open the backend-selected failure report folder.");
      reportAddDiagnosticsAction(actions, "open", "run_logs", "Open Run Logs", "Compare the failure row with pipeline logs before retrying.");
      if (!item) return actions;
      const classification = String(item.classification || "").toLowerCase();
      if (classification === "operator_required" || classification === "permanent") {
        reportAddDiagnosticsAction(actions, "open", "failed_markers", "Open Error Records", "Inspect source-level error records before rerun.");
      }
      if (String(item.stage || "").toLowerCase().includes("publish")) {
        reportAddDiagnosticsAction(actions, "open", "pending_publish", "Open Pending Publish", "Compare failure state with parked output state.");
      }
      if (String(item.stage || "").toLowerCase().includes("queue")) {
        reportAddDiagnosticsAction(actions, "open", "queue_snapshot", "Open Queue Snapshot", "Compare the failure with the latest queue snapshot.");
      }
      return actions;
    }

  function failureDiagnosticsActionsForGroup(group) {
      const groupActions = Array.isArray(group?.diagnostic_targets) ? group.diagnostic_targets : [];
      if (groupActions.length) return groupActions;
      const rows = failureRowsForGroup(group);
      return failureDiagnosticsActionsForRow(rows[0] || null);
    }

  function failureResolutionPrimaryAction(group) {
      const action = group?.primary_action && typeof group.primary_action === "object" ? group.primary_action : {};
      const label = String(action.label || group?.primary_action_label || "").trim();
      if (label) return action;
      const owner = String(group?.owner || "").trim();
      const target = reportOwnerPage(owner);
      if (target) return { kind: "open_owner_page", label: target.label === "Diagnostics" ? "Review in Diagnostics" : `Open ${target.label}`, page: target.page, owner };
      if (selectedFailureGroupMarkerPaths().length) return { kind: "clear_marker", label: "Clear errors" };
      return { kind: "review_details", label: "Review details", page: "diagnostics" };
    }

  function failureRootCauseLabel(errorCode) {
      const code = String(errorCode || "").trim();
      const upper = code.toUpperCase();
      if (!code) return "No error code";
      if (upper.includes("OCR_TOOL_MISSING")) return "OCR tool missing";
      if (upper.includes("TOOL_MISSING")) return "Tool missing";
      if (upper.includes("SUBTITLE")) return "Subtitle review";
      if (upper.includes("AUDIO")) return "Audio review";
      if (upper.includes("PUBLISH")) return "Publish review";
      if (upper.includes("QUEUE")) return "Queue review";
      if (upper.includes("SOURCE")) return "Source review";
      return reportHumanLabel(code, "Unknown error");
    }

  function failureRootCauseTone(errorCode) {
      const upper = String(errorCode || "").toUpperCase();
      if (!upper) return "muted";
      if (upper.includes("TOOL_MISSING") || upper.includes("BLOCK") || upper.includes("LOCK")) return "warning";
      if (upper.includes("PERMANENT") || upper.includes("FATAL")) return "danger";
      return "info";
    }

  function failureReviewNextStep({ failures, loaded, operatorRows, transientRows, rows, rootCauseCode }) {
      const upperCause = String(rootCauseCode || "").toUpperCase();
      if (failures.error) {
        return {
          value: "Open Diagnostics",
          detail: "Inspect Failure Reports and Run Logs before rerun.",
          tone: "danger",
        };
      }
      if (!loaded) {
        return {
          value: "Refresh Reports",
          detail: "Load the failure preview before triage.",
          tone: "muted",
        };
      }
      if (operatorRows.length) {
        return {
          value: "Inspect holds",
          detail: "Resolve operator/permanent rows before retry.",
          tone: "warning",
        };
      }
      if (upperCause.includes("OCR_TOOL_MISSING")) {
        return {
          value: "Fix OCR path",
          detail: transientRows.length ? "Then run Retry review." : "Then refresh failure evidence.",
          tone: "warning",
        };
      }
      if (transientRows.length) {
        return {
          value: "Compare logs",
          detail: "Check Run Logs and queue state before retry.",
          tone: "info",
        };
      }
      if (rows.length) {
        return {
          value: "Select row",
          detail: "Confirm classification and owner handoff.",
          tone: "info",
        };
      }
      return {
        value: "No failure rows",
        detail: "Use Audit or Diagnostics if a failure was expected.",
        tone: "success",
      };
    }

  function failureReviewStatus() {
      const failures = reportsState.lastFailurePreviewPayload || {};
      if (failures.error) return "Unavailable";
      if (!reportPreviewLoaded(failures, reportsState.lastFailureRows)) return "Not loaded";
      if (reportNumber(failures.operator_required_count) > 0 || reportNumber(failures.permanent_count) > 0) return "Action needed";
      if (reportNumber(failures.transient_count) > 0) return "Retry review";
      if (reportsState.lastFailureRows.length) return "Loaded";
      return "No rows";
    }

  function failureReviewBoardLines() {
      const failures = reportsState.lastFailurePreviewPayload || {};
      const rows = Array.isArray(reportsState.lastFailureRows) ? reportsState.lastFailureRows : [];
      const warnings = Array.isArray(failures.warnings) ? failures.warnings.filter(Boolean) : [];
      if (failures.error) {
        return [
          "Failure review board: unavailable.",
          `Error: ${failures.error}`,
          "First action: open Latest Failure, Failure Reports, and Run Logs from Diagnostics before deciding whether a rerun is safe.",
          "Boundary: backend commands own cleanup and rerun decisions; media files are not touched here.",
        ];
      }
      if (!reportPreviewLoaded(failures, rows)) {
        return [
          "Failure review board: no failure preview has loaded yet.",
          "First action: refresh Reports or open Failure Reports if you expected recent failures.",
          "Boundary: backend commands own cleanup and rerun decisions; media files are not touched here.",
        ];
      }
      const operatorRows = rows.filter((row) => ["operator_required", "permanent"].includes(String(row.classification || "").toLowerCase()));
      const transientRows = rows.filter((row) => String(row.classification || "").toLowerCase() === "transient");
      const retryState = failureRetryStatePayload(failures);
      const reviewRows = [...operatorRows, ...transientRows, ...rows.filter((row) => !operatorRows.includes(row) && !transientRows.includes(row))];
      const lines = [
        "Failure review board:",
        `Rows: ${reportNumber(failures.count || rows.length)}`,
        `Classification counts: ${reportFormatCounts(reportCountBy(rows, "classification"))}`,
        `Stage counts: ${reportFormatCounts(reportCountBy(rows, "stage"))}`,
        `Error-code counts: ${reportFormatCounts(reportCountBy(rows, "error_code"))}`,
        `Media counts: ${reportFormatCounts(reportCountBy(rows, "media_type"))}`,
        `Operator/permanent rows: ${operatorRows.length}`,
        `Transient retry rows: ${transientRows.length}`,
        `Retry state: ${retryState.status_state || "unknown"}; retryable=${retryState.retryable_count || 0}; blocked=${retryState.blocked_count || 0}; warning=${retryState.warning_count || 0}.`,
      ];
      if (warnings.length) {
        lines.push("", "Warning(s):");
        warnings.slice(0, 5).forEach((warning) => lines.push(`- ${warning}`));
      }
      if (reviewRows.length) {
        lines.push("", "First rows to inspect:");
        reviewRows.slice(0, 6).forEach((row) => {
          const title = row.lookup_title || row.source_path || row.source_json || "unknown source";
          const classification = row.classification || "unknown";
          const code = row.error_code || "no-code";
          const stage = row.stage || "unknown-stage";
          const action = row.suggested_action || row.reason || "review failure record";
          lines.push(`- ${classification} / ${stage} / ${code}: ${title} -> ${action}`);
        });
      }
      lines.push("");
      if (operatorRows.length) {
        lines.push("Next step: inspect operator/permanent rows before rerun; they may require rename, source replacement, manual subtitle review, or config changes.");
      } else if (transientRows.length) {
        lines.push("Next step: compare transient rows with Run Logs and pending/queue state before retrying.");
      } else if (rows.length) {
        lines.push("Next step: select a row to confirm classification, proof paths, and Diagnostics handoff.");
      } else {
        lines.push("Next step: no failure rows are present; use Audit rows or Diagnostics if you expected a recent failure.");
      }
      lines.push("Boundary: backend commands own cleanup and rerun decisions; media files are not touched here.");
      return lines;
    }

  function failureReviewBoardTiles() {
      const failures = reportsState.lastFailurePreviewPayload || {};
      const rows = Array.isArray(reportsState.lastFailureRows) ? reportsState.lastFailureRows : [];
      const loaded = reportPreviewLoaded(failures, rows);
      const operatorRows = rows.filter((row) => ["operator_required", "permanent"].includes(String(row.classification || "").toLowerCase()));
      const transientRows = rows.filter((row) => String(row.classification || "").toLowerCase() === "transient");
      const retryState = failureRetryStatePayload(failures);
      const rowCount = reportNumber(failures.count || rows.length);
      const stageCounts = reportCountBy(rows, "stage");
      const stageEntries = reportSortedCountEntries(stageCounts, 1);
      const errorCounts = reportCountBy(rows, "error_code");
      const errorEntries = reportSortedCountEntries(errorCounts, 2);
      const mediaCounts = reportCountBy(rows, "media_type");
      const rootCauseCode = errorEntries[0]?.[0] || "";
      const retryableCount = reportNumber(retryState.retryable_count || transientRows.length);
      const blockedCount = reportNumber(retryState.blocked_count);
      const warningCount = reportNumber(retryState.warning_count);
      const nextStep = failureReviewNextStep({ failures, loaded, operatorRows, transientRows, rows, rootCauseCode });
      let reviewState = failureReviewStatus();
      let reviewTone = "muted";
      let reviewDetail = loaded ? `${transientRows.length} transient / ${operatorRows.length} operator-permanent` : "No failure preview has loaded.";
      if (failures.error) {
        reviewTone = "danger";
        reviewDetail = "Failure preview is unavailable.";
      } else if (operatorRows.length) {
        reviewTone = "warning";
        reviewState = "Action needed";
      } else if (transientRows.length) {
        reviewTone = "info";
        reviewState = "Retryable";
      } else if (loaded && !rows.length) {
        reviewTone = "success";
        reviewState = "Clear";
        reviewDetail = "No failure rows in the preview.";
      } else if (loaded) {
        reviewTone = "info";
      }
      const rootCauseDetail = errorEntries.length
        ? errorEntries.map(([key, value]) => `${key}: ${value}`).join(" / ")
        : "No error-code evidence.";
      const stageDetail = stageEntries.length
        ? reportCountLabel(stageEntries[0][1], "failure")
        : "No stage evidence.";
      const retryDetail = [
        reportCountLabel(transientRows.length, "transient row"),
        blockedCount ? reportCountLabel(blockedCount, "blocked row") : "",
        warningCount ? reportCountLabel(warningCount, "warning") : "",
      ].filter(Boolean).join(" / ") || "No retry candidates.";
      return [
        {
          label: "Review State",
          value: reviewState,
          detail: reviewDetail,
          tone: reviewTone,
        },
        {
          label: "Failed Rows",
          value: String(rowCount),
          detail: rows.length ? "All loaded failure rows." : "No loaded failure rows.",
          tone: rowCount ? "danger" : "success",
        },
        {
          label: "Primary Stage",
          value: stageEntries.length ? reportHumanLabel(stageEntries[0][0], "Unknown stage") : "No stage",
          detail: stageDetail,
          tone: stageEntries.length ? "info" : "muted",
        },
        {
          label: "Retry Candidates",
          value: String(retryableCount),
          detail: retryDetail,
          tone: retryableCount ? "info" : "muted",
        },
        {
          label: "Root Cause",
          value: failureRootCauseLabel(rootCauseCode),
          detail: rootCauseDetail,
          tone: failureRootCauseTone(rootCauseCode),
          wide: true,
        },
        {
          label: "Media Impact",
          value: reportCompactCountPairs(mediaCounts, 2, "None"),
          detail: reportCountLabel(rowCount, "total file"),
          tone: rowCount ? "info" : "muted",
        },
        {
          label: "Operator Holds",
          value: String(operatorRows.length),
          detail: "Permanent/manual rows.",
          tone: operatorRows.length ? "warning" : "success",
        },
        {
          label: "Next Step",
          value: nextStep.value,
          detail: nextStep.detail,
          tone: nextStep.tone,
          wide: true,
        },
      ];
    }

    return {
      failureActionOwner,
      failureClassificationText,
      failureClearError,
      failureClearMarkerPath,
      failureClearMarkerPathsForRow,
      failureClearUnavailableReason,
      failureCountsForRows,
      failureDiagnosticsActionsForGroup,
      failureDiagnosticsActionsForRow,
      failureDisplayValue,
      failureEmptyStateMessage,
      failureEvidenceDetails,
      failureEvidenceProofLines,
      failureEvidenceStreamLine,
      failureFileText,
      failureGroupJournalKey,
      failureGroupLifecycleState,
      failureGroupMatchesChip,
      failureGroupSearchText,
      failureMarkerPath,
      failureMatchesChip,
      failurePlainSummaryText,
      failureReasonText,
      failureRecordedText,
      failureResolutionFallbackGroups,
      failureResolutionGroupForRow,
      failureResolutionGroupKey,
      failureResolutionGroupsFromPayload,
      failureResolutionPrimaryAction,
      failureResolutionSummaryPayload,
      failureRetryDetailLines,
      failureRetryPreviewSummaryLine,
      failureRetryRows,
      failureRetryStateForRow,
      failureRetryStateFromRow,
      failureRetryStatePayload,
      failureRetrySummaryText,
      failureReviewBoardLines,
      failureReviewBoardTiles,
      failureReviewNextStep,
      failureReviewStatus,
      failureRootCauseLabel,
      failureRootCauseTone,
      failureRowKey,
      failureRowSearchText,
      failureRowsForGroup,
      failureSeverity,
      failureStageText,
      failureStatusLabel,
      failureSuggestedActionText,
      failureTableEvidenceText,
      failureTriage,
      normalizeFailureMarkerPaths,
    };
  }

  window.__reportsViewFailureModelModule = {
    createReportsFailureModelModule,
  };
})();
