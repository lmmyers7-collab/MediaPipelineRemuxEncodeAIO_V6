(function () {
  function createLaunchRerunEvidenceModule(deps = {}) {
    const {
      applyRerunPreviewButtonState,
      byId,
      collectRerunScopeRequest,
      collectRerunStartRequest,
      launchCoordinatorState,
      renderAllLaunchPreflights,
      RERUN_EXECUTION_LABELS,
      RERUN_POLICY_CHOICES,
      rerunExecutionTargetLabel,
      rerunPreviewBlockedReason,
      rerunStartRouteName,
      scheduleRerunPreviewRefresh,
      setText,
      state,
      updateLaunchCommandButtonStates,
    } = deps;

    function rerunPreviewCounts(payload) {
      return payload && typeof payload === "object" && payload.counts && typeof payload.counts === "object" ? payload.counts : {};
    }
  
    function rerunPreviewScope(payload) {
      return payload && typeof payload === "object" && payload.scope && typeof payload.scope === "object" ? payload.scope : collectRerunScopeRequest();
    }
  
    function rerunCount(value) {
      const parsed = Number(value || 0);
      return Number.isFinite(parsed) ? parsed : 0;
    }
  
    function rerunLabelFromChoice(kind, value) {
      return rerunPolicyChoice(kind, value).label || String(value || "");
    }
  
    function rerunPreviewConflictLines(payload) {
      if (!payload || typeof payload !== "object") return [];
      const counts = rerunPreviewCounts(payload);
      const scope = rerunPreviewScope(payload);
      const lines = [];
      const safeModes = payload.safe_modes === true;
      const blockedModes = rerunCount(counts.blocked_mode_rows);
      const blockedScoped = rerunCount(counts.blocked_scoped_rows);
      const effectiveScoped = rerunCount(counts.effective_scoped_rows);
      const affectedRows = blockedScoped || blockedModes || rerunCount(counts.blocked_rows);
  
      if (!safeModes || blockedModes > 0) {
        const affectedText = affectedRows > 0 ? `${affectedRows} row(s)` : "The selected row scope";
        lines.push(`${affectedText} are blocked by the rerun lifecycle policy, not by a CSV read error.`);
        const conflicts = [];
        if (payload.destination_mode && payload.destination_mode !== "review_workspace") {
          conflicts.push(`Destination is ${rerunLabelFromChoice("destination", payload.destination_mode)}`);
        }
        if (payload.collision_policy === "replace_final") {
          conflicts.push(`Destination collision is ${rerunLabelFromChoice("collision", payload.collision_policy)}`);
        }
        if (payload.stage_mode && payload.stage_mode !== "copy") {
          conflicts.push(`stage_mode=${payload.stage_mode}`);
        }
        if (payload.return_mode && payload.return_mode !== "park") {
          conflicts.push(`return_mode=${payload.return_mode}`);
        }
        if (conflicts.length) {
          lines.push(`Selected policy conflict: ${conflicts.join("; ")}.`);
        }
        lines.push("Executable CSV rerun currently supports scratch-copy staging, backend-owned destination handling, and explicit source-path overwrite confirmation.");
        lines.push("Change Destination and Destination Collision to a supported pairing, then inspect the CSV again.");
      }
  
      if (effectiveScoped > 0 && blockedScoped >= effectiveScoped) {
        lines.push("Every effective scoped row is blocked, so the current execution mode stages 0 rows.");
      } else if (scope.skip_blocked && blockedModes > 0) {
        lines.push("Skip Blocked can remove blocked rows from the scoped CSV only when at least one non-blocked scoped row remains.");
      }
  
      if (rerunCount(counts.missing_source_rows) > 0) {
        lines.push(`${rerunCount(counts.missing_source_rows)} row(s) are missing source_path values.`);
      }
      return Array.from(new Set(lines));
    }
  
    function rerunSummaryLines(payload) {
      if (!payload || typeof payload !== "object") return ["No CSV rerun preview loaded."];
      const counts = rerunPreviewCounts(payload);
      const scope = rerunPreviewScope(payload);
      const lines = [
        `Status: ${payload.status || "unknown"} - ${payload.message || ""}`.trim(),
        `CSV: ${payload.csv_path || "not selected"}`,
        `Rows: total ${counts.total_rows || 0}; enabled ${counts.enabled_rows || 0}; disabled ${counts.disabled_rows || 0}; effective scoped ${counts.effective_scoped_rows || 0}`,
        `Blockers: blocked rows ${counts.blocked_rows || 0}; blocked modes ${counts.blocked_mode_rows || 0}; blocked scoped ${counts.blocked_scoped_rows || 0}; missing source ${counts.missing_source_rows || 0}; duplicate source ${counts.duplicate_source_rows || 0}`,
        `Warnings: ${counts.warning_rows || 0}`,
        `Scope: enabled only ${scope.enabled_only ? "yes" : "no"}; skip blocked ${scope.skip_blocked ? "yes" : "no"}; skip warnings ${scope.skip_warning_rows ? "yes" : "no"}; first rows ${scope.first_n || 0}; issue "${scope.issue_filter || ""}"; bucket "${scope.bucket_filter || ""}"`,
      ];
      const conflicts = rerunPreviewConflictLines(payload);
      if (conflicts.length) lines.push("", "Why blocked:", ...conflicts.map((item) => `- ${item}`));
      const warnings = Array.isArray(payload.warnings) ? payload.warnings : [];
      if (warnings.length) lines.push("", "Warnings:", ...warnings.map((item) => `- ${item}`));
      return lines;
    }
  
    function clearElement(element) {
      if (!element) return;
      while (element.firstChild) element.removeChild(element.firstChild);
    }
  
    function appendCell(row, text, className = "") {
      const cell = document.createElement("td");
      if (className) cell.className = className;
      cell.textContent = text == null ? "" : String(text);
      row.appendChild(cell);
      return cell;
    }
  
    function appendRerunText(parent, className, text, title = "") {
      const node = document.createElement("div");
      node.className = className;
      node.textContent = String(text || "");
      if (title) node.title = title;
      parent.appendChild(node);
      return node;
    }
  
    function rerunStatusSeverity(status) {
      const text = String(status || "").toLowerCase();
      if (/(blocked|failed|error|missing|not_found)/.test(text)) return "high";
      if (/(warning|review|partial|pending)/.test(text)) return "medium";
      if (/(ready|completed|ok|success|accepted)/.test(text)) return "ok";
      return "info";
    }
  
    function setRerunReviewCount(key, value, state = "") {
      const node = document.querySelector(`[data-rerun-review-count="${key}"]`);
      if (!node) return;
      node.textContent = String(value ?? 0);
      const tile = node.closest(".rerun-review-metric");
      if (tile && state) tile.dataset.state = state;
    }
  
    function rerunCurrentPhase(payload = state.lastRerunPreviewPayload) {
      if (launchCoordinatorState.launchCommandInFlight) return "Running";
      if (state.lastRerunCommandResult) {
        if (state.lastRerunCommandResult.ok) return "Submitted";
        return state.lastRerunCommandResult.severity === "blocked" ? "Blocked" : "Failed";
      }
      if (!payload) return "Idle";
      const status = String(payload.status || "").trim();
      if (!status) return "Preview";
      return status === "blocked" ? "Preview blocked" : `Preview ${status}`;
    }
  
    function rerunReviewNextAction(payload = state.lastRerunPreviewPayload) {
      const request = collectRerunStartRequest({ dry_run: false, plan_only: false });
      if (!String(request.csv_path || "").trim()) return "Enter or browse to a CSV path, then Inspect CSV.";
      if (!payload) return "Inspect CSV submits a read-only backend preview. Open actions require a backend-known recent CSV.";
      if (state.lastRerunCommandResult?.ok) return "Refresh State to review backend queue-state and command evidence.";
      const reason = rerunPreviewBlockedReason(request);
      if (reason) return `Resolve preview block: ${reason}`;
      const counts = rerunPreviewCounts(payload);
      const route = rerunStartRouteName();
      return `Review & Start submits ${route} to the backend for ${rerunCount(counts.effective_scoped_rows)} scoped row(s).`;
    }
  
    function renderRerunReviewHeader(payload = state.lastRerunPreviewPayload) {
      const header = byId("rerun-review-header");
      if (!header) return;
      const counts = rerunPreviewCounts(payload);
      const request = collectRerunStartRequest({ dry_run: false, plan_only: false });
      const csvPath = String(payload?.csv_path || request.csv_path || "").trim();
      const phase = rerunCurrentPhase(payload);
      header.dataset.phase = phase.toLowerCase().replace(/\s+/g, "-");
      setText("rerun-review-status", payload ? `${payload.status || "preview"}${payload.message ? ` - ${payload.message}` : ""}` : "No CSV preview loaded");
      setText("rerun-review-csv", `CSV: ${csvPath || "not selected"}`);
      setRerunReviewCount("total", rerunCount(counts.total_rows), "neutral");
      setRerunReviewCount("scoped", rerunCount(counts.effective_scoped_rows), "neutral");
      setRerunReviewCount("blocked", rerunCount(counts.blocked_rows) || rerunCount(counts.blocked_scoped_rows), "blocked");
      setRerunReviewCount("warnings", rerunCount(counts.warning_rows), "warning");
      setRerunReviewCount("phase", phase, rerunStatusSeverity(phase));
      setText("rerun-review-next-action", rerunReviewNextAction(payload));
    }
  
    function rerunHistoryEntries() {
      const history = typeof window.getCommandHistory === "function"
        ? window.getCommandHistory()
        : typeof window.mediaPipelineCommandHistory?.getCommandHistory === "function"
        ? window.mediaPipelineCommandHistory.getCommandHistory()
        : [];
      return Array.isArray(history) ? history : [];
    }
  
    function rerunHistoryRequestData(entry = {}) {
      const rawRequest = entry.raw?.request && typeof entry.raw.request === "object" ? entry.raw.request : null;
      const rawSubmitted = entry.raw?.submitted_request && typeof entry.raw.submitted_request === "object" ? entry.raw.submitted_request : null;
      const request = entry.request && typeof entry.request === "object" ? entry.request : null;
      const dataRequest = entry.data?.request && typeof entry.data.request === "object" ? entry.data.request : null;
      return rawRequest || rawSubmitted || request || dataRequest || {};
    }
  
    function rerunHistoryData(entry = {}) {
      if (entry.raw?.data && typeof entry.raw.data === "object") return entry.raw.data;
      if (entry.data && typeof entry.data === "object") return entry.data;
      return {};
    }
  
    function rerunLatestStartHistoryEntry() {
      return rerunHistoryEntries().find((entry) => {
        const command = String(entry.command || entry.raw?.command || "");
        return command === "rerun.start" || command === "rerun.network.start";
      }) || null;
    }
  
    function rerunResultRequestData(result = {}) {
      if (result.request && typeof result.request === "object") return result.request;
      if (result.raw?.request && typeof result.raw.request === "object") return result.raw.request;
      if (result.submitted_request && typeof result.submitted_request === "object") return result.submitted_request;
      if (result.data?.request && typeof result.data.request === "object") return result.data.request;
      return {};
    }
  
    function rerunResultData(result = {}) {
      if (result.data && typeof result.data === "object") return result.data;
      if (result.raw?.data && typeof result.raw.data === "object") return result.raw.data;
      return {};
    }
  
    function rerunEvidencePid(result = {}) {
      const data = rerunResultData(result);
      const candidates = [result.pid, result.process_id, data.pid, data.process_id];
      const found = candidates.find((value) => value !== undefined && value !== null && String(value).trim());
      if (found !== undefined) return String(found);
      const match = String(result.message || result.raw?.message || "").match(/\bPID\s*(\d+)\b/i);
      return match ? match[1] : "";
    }
  
    function rerunSafeNextAction(payload, result, request) {
      if (launchCoordinatorState.launchCommandInFlight) return "Wait for backend queue-state refresh, or use Stop After Current if the active rerun needs to wind down.";
      if (result?.ok) return "Refresh State to load backend queue-state, run manifest, and command journal evidence.";
      if (result && result.ok === false) return "Review the backend command result, adjust the request or CSV, then inspect again.";
      const reason = rerunPreviewBlockedReason(request);
      if (reason) return `Resolve the preview block before submitting: ${reason}`;
      if (payload) return "Review row identity, categories, and reasons, then use Review & Start to submit the backend command.";
      return "Inspect CSV to load the backend preview before starting work.";
    }
  
    function renderRerunLifecycleEvidence(payload = state.lastRerunPreviewPayload, commandResult = state.lastRerunCommandResult) {
      const card = byId("rerun-lifecycle-evidence");
      if (!card) return;
      const latestEntry = rerunLatestStartHistoryEntry();
      const historyRequest = latestEntry ? rerunHistoryRequestData(latestEntry) : {};
      const result = commandResult || (latestEntry ? { ...latestEntry.raw, ...latestEntry } : null);
      const resultRequest = result ? rerunResultRequestData(result) : {};
      const request = Object.keys(resultRequest).length
        ? resultRequest
        : Object.keys(historyRequest).length
        ? historyRequest
        : collectRerunStartRequest({ dry_run: false, plan_only: false });
      const data = result ? rerunResultData(result) : {};
      const counts = rerunPreviewCounts(payload);
      const phase = rerunCurrentPhase(payload);
      const pid = result ? rerunEvidencePid(result) : "";
      const csvPath = String(result?.request?.csv_path || request.csv_path || payload?.csv_path || data.csv_path || "").trim();
      const destination = rerunPolicyChoice("destination", payload?.destination_mode || request.destination_mode || data.destination_mode || "auto_replace_clean_else_pending_review");
      const collision = rerunPolicyChoice("collision", payload?.collision_policy || request.collision_policy || data.collision_policy || "suffix");
      const execution = rerunExecutionLabel(payload?.execution_mode || request.execution_mode || data.execution_mode || "one_at_a_time");
      const targetLabel = data.candidate_command === "rerun.network.start" || result?.command === "rerun.network.start" ? "Network CSV rerun" : rerunExecutionTargetLabel();
      const scopedRowCount = rerunCount(data.scoped_row_count ?? data.effective_scoped_rows ?? data.row_count ?? counts.effective_scoped_rows);
      const phaseNode = byId("rerun-lifecycle-phase");
      if (phaseNode) {
        phaseNode.textContent = phase;
        phaseNode.dataset.severity = rerunStatusSeverity(phase);
      }
      const commandStatus = result
        ? `${result.command || latestEntry?.command || "rerun.start"} ${result.ok ? "accepted" : "not accepted"}${pid ? `; PID ${pid}` : ""}`
        : "No submitted rerun command evidence.";
      setText("rerun-lifecycle-summary", [
        `Phase: ${phase}.`,
        `CSV: ${csvPath || "not selected"}.`,
        payload ? `Preview rows: total ${rerunCount(counts.total_rows)}, scoped ${rerunCount(counts.effective_scoped_rows)}, blocked ${rerunCount(counts.blocked_rows)}, warnings ${rerunCount(counts.warning_rows)}.` : "Preview rows: not loaded.",
        `Target: ${targetLabel}.`,
        `Command: ${commandStatus}`,
      ].join(" "));
      setText("rerun-lifecycle-detail", [
        `Execution: ${execution}; destination ${destination.label}; collision ${collision.label}.`,
        `Request CSV: ${request.csv_path || "not recorded"}.`,
        `Scoped row count: ${scopedRowCount}.`,
        `Safe next action: ${rerunSafeNextAction(payload, result, request)}`,
      ].join("\n"));
    }
  
    function renderRerunRecentCsvs(payload) {
      const tbody = byId("rerun-recent-csv-rows");
      if (!tbody) return;
      clearElement(tbody);
      const rows = payload && Array.isArray(payload.recent_csvs) ? payload.recent_csvs : [];
      if (!rows.length) {
        const row = document.createElement("tr");
        appendCell(row, "No recent CSV evidence loaded.").colSpan = 4;
        tbody.appendChild(row);
        return;
      }
      rows.forEach((item) => {
        const row = document.createElement("tr");
        appendCell(row, item.label || item.path || "CSV");
        appendCell(row, item.source || "");
        appendCell(row, item.modified_at || "");
        const action = document.createElement("td");
        const button = document.createElement("button");
        button.type = "button";
        button.className = "secondary-button";
        button.textContent = "Use";
        button.title = item.path || "";
        button.addEventListener("click", () => {
          const input = byId("rerun-start-csv-path");
          if (input) input.value = item.path || "";
          scheduleRerunPreviewRefresh(0);
          renderAllLaunchPreflights();
          updateLaunchCommandButtonStates();
          applyRerunPreviewButtonState();
        });
        action.appendChild(button);
        row.appendChild(action);
        tbody.appendChild(row);
      });
    }
  
    function rerunPolicyChoice(kind, value) {
      const key = String(value || "");
      const choices = RERUN_POLICY_CHOICES[kind] || {};
      if (choices[key]) return choices[key];
      return {
        label: key || "Unknown",
        detail: "Backend will apply the selected policy when the request is accepted.",
        state: "review",
      };
    }
  
    function rerunExecutionLabel(value) {
      const key = String(value || "one_at_a_time");
      return RERUN_EXECUTION_LABELS[key] || key;
    }
  
    function setRerunHandlingText(selector, value) {
      const node = document.querySelector(selector);
      if (node) node.textContent = value;
    }
  
    function renderRerunHandlingCard(kind, choice) {
      const card = document.querySelector(`[data-rerun-policy-card="${kind}"]`);
      if (card) card.dataset.state = choice.state || "review";
      setRerunHandlingText(`[data-rerun-policy-summary="${kind}"]`, choice.label);
      setRerunHandlingText(`[data-rerun-policy-detail="${kind}"]`, choice.detail);
    }
  
    function rerunFinalReplacementSelected(request) {
      return request?.destination_mode === "auto_replace_clean_else_pending_review" || request?.destination_mode === "publish_replace_final" || request?.collision_policy === "replace_final";
    }
  
    function rerunPolicySelectId(kind) {
      return {
        destination: "rerun-start-destination-mode",
        collision: "rerun-start-collision-policy",
      }[kind] || "";
    }
  
    function rerunPolicyRequestKey(kind) {
      return {
        destination: "destination_mode",
        collision: "collision_policy",
      }[kind] || "";
    }
  
    function rerunPolicyKindFromElement(element) {
      const id = String(element?.id || "");
      if (id === "rerun-start-destination-mode") return "destination";
      if (id === "rerun-start-collision-policy") return "collision";
      return "";
    }
  
    function rerunRawPolicySelection() {
      return {
        destination_mode: byId("rerun-start-destination-mode")?.value || "auto_replace_clean_else_pending_review",
        collision_policy: byId("rerun-start-collision-policy")?.value || "replace_final",
      };
    }
  
    function rerunPolicyConflictReason(kind, value, raw = rerunRawPolicySelection()) {
      const selected = String(value || "");
      if (!selected || selected === "auto") return "";
      const destination = kind === "destination" ? selected : String(raw.destination_mode || "auto_replace_clean_else_pending_review");
      const collision = kind === "collision" ? selected : String(raw.collision_policy || "suffix");
      const collisionFixed = collision !== "auto";
      const destinationFixed = destination !== "auto";
  
      if (kind === "destination") {
        if (selected === "publish_non_overlap" && collision === "replace_final") {
          return "Non-overlap destination cannot also replace final output; auto will use suffix collision.";
        }
        if (selected === "publish_replace_final" && collisionFixed && collision !== "replace_final") {
          return "Final replacement requires replace-final collision; auto will align collision handling.";
        }
      }
  
      if (kind === "collision") {
        if (selected === "replace_final" && destinationFixed && !["auto_replace_clean_else_pending_review", "pending_publish", "publish_replace_final"].includes(destination)) {
          return "Replace-final collision needs a replacement-capable destination; auto will use the clean-replace/Pending Publish policy.";
        }
        if (selected !== "replace_final" && ["auto_replace_clean_else_pending_review", "publish_replace_final"].includes(destination)) {
          return "Publish-and-replace destination requires replace-final collision; auto will align destination handling.";
        }
      }
  
      return "";
    }
  
    function setRerunPolicySelectAuto(kind) {
      const select = byId(rerunPolicySelectId(kind));
      if (!select) return;
      const hasAuto = Array.from(select.options || []).some((option) => option.value === "auto");
      if (hasAuto) select.value = "auto";
    }
  
    function updateRerunPolicyOptionStates() {
      const raw = rerunRawPolicySelection();
      ["destination", "collision"].forEach((kind) => {
        const select = byId(rerunPolicySelectId(kind));
        if (!select || !select.options) return;
        let conflictCount = 0;
        Array.from(select.options).forEach((option) => {
          const baseLabel = option.dataset.rerunBaseLabel || option.textContent || option.value;
          option.dataset.rerunBaseLabel = baseLabel;
          const reason = rerunPolicyConflictReason(kind, option.value, raw);
          if (reason) conflictCount += 1;
          option.dataset.rerunConflict = reason ? "true" : "false";
          option.setAttribute("aria-disabled", reason ? "true" : "false");
          option.title = reason;
          option.textContent = reason ? `${baseLabel} (auto adjusts)` : baseLabel;
        });
        select.dataset.rerunHasConflicts = conflictCount > 0 ? "true" : "false";
        select.dataset.rerunAuto = select.value === "auto" ? "true" : "false";
      });
    }
  
    function applyRerunPolicySelectionRules(event = null) {
      const kind = rerunPolicyKindFromElement(event?.target);
      if (!kind) {
        updateRerunPolicyOptionStates();
        return;
      }
      const raw = rerunRawPolicySelection();
      const key = rerunPolicyRequestKey(kind);
      const reason = rerunPolicyConflictReason(kind, raw[key], raw);
      if (reason) {
        ["destination", "collision"].forEach((candidate) => {
          if (candidate !== kind) setRerunPolicySelectAuto(candidate);
        });
        setText("rerun-mode-policy-note", `Auto-adjusted ${kind} pairing. ${reason} Backend still receives concrete policy values after auto resolution.`);
      }
      updateRerunPolicyOptionStates();
    }
  
    function rerunPolicyChoiceForSummary(kind, rawValue, resolvedValue) {
      const resolved = resolvedValue || rawValue;
      const choice = { ...rerunPolicyChoice(kind, resolved) };
      if (rawValue === "auto") {
        choice.label = `Auto: ${choice.label}`;
        choice.detail = `${choice.detail} Auto resolved from the current destination/collision policy before backend submit.`;
      }
      return choice;
    }
  
    function rerunSourceHandlingLine(request) {
      if (rerunFinalReplacementSelected(request)) {
        return request && request.confirm_source_overwrite
          ? "Source handling: source-path overwrite is explicitly confirmed; replace-final destinations use the CSV source path."
          : "Source handling: source files stay untouched unless source-path overwrite is explicitly confirmed.";
      }
      return "Source handling: source files stay untouched; destination/collision only control verified output placement.";
    }
  
    function renderRerunHandlingSummary(request = collectRerunStartRequest()) {
      const raw = rerunRawPolicySelection();
      renderRerunHandlingCard("destination", rerunPolicyChoiceForSummary("destination", raw.destination_mode, request.destination_mode || "auto_replace_clean_else_pending_review"));
      renderRerunHandlingCard("collision", rerunPolicyChoiceForSummary("collision", raw.collision_policy, request.collision_policy || "suffix"));
      updateRerunPolicyOptionStates();
    }
  
    function rerunStartPolicySummary(request) {
      const execution = rerunExecutionLabel(request.execution_mode);
      const windowSize = Number(request.window_size || 1);
      const raw = rerunRawPolicySelection();
      const destination = rerunPolicyChoiceForSummary("destination", raw.destination_mode, request.destination_mode || "auto_replace_clean_else_pending_review");
      const collision = rerunPolicyChoiceForSummary("collision", raw.collision_policy, request.collision_policy || "suffix");
      return `${execution} (window ${Number.isFinite(windowSize) ? Math.max(1, Math.round(windowSize)) : 1}); destination: ${destination.label}; collision: ${collision.label}; source overwrite ${request.confirm_source_overwrite ? "confirmed" : "not confirmed"}`;
    }
  
    function selectedOptionValues(select) {
      if (!select || !select.options) return [];
      return Array.from(select.options).filter((option) => option.selected).map((option) => option.value);
    }
  
    function renderRerunSelectOptions(id, options) {
      const select = byId(id);
      if (!select || !Array.isArray(options)) return;
      const selected = new Set(selectedOptionValues(select));
      clearElement(select);
      options.forEach((item) => {
        const value = String(item.value || item.label || "");
        if (!value) return;
        const option = document.createElement("option");
        option.value = value;
        option.textContent = item.count ? `${item.label || value} (${item.count})` : (item.label || value);
        option.selected = selected.has(value);
        select.appendChild(option);
      });
    }
  
    function renderRerunFilterOptions(payload) {
      const options = payload && typeof payload.filter_options === "object" ? payload.filter_options : {};
      renderRerunSelectOptions("rerun-scope-issue-filter", options.issue_filters || []);
      renderRerunSelectOptions("rerun-scope-bucket-filter", options.bucket_filters || []);
    }
  

    return {
      rerunPreviewCounts,
      rerunPreviewScope,
      rerunCount,
      rerunLabelFromChoice,
      rerunPreviewConflictLines,
      rerunSummaryLines,
      clearElement,
      appendCell,
      appendRerunText,
      rerunStatusSeverity,
      setRerunReviewCount,
      rerunCurrentPhase,
      rerunReviewNextAction,
      renderRerunReviewHeader,
      rerunHistoryEntries,
      rerunHistoryRequestData,
      rerunHistoryData,
      rerunLatestStartHistoryEntry,
      rerunResultRequestData,
      rerunResultData,
      rerunEvidencePid,
      rerunSafeNextAction,
      renderRerunLifecycleEvidence,
      renderRerunRecentCsvs,
      rerunPolicyChoice,
      rerunExecutionLabel,
      setRerunHandlingText,
      renderRerunHandlingCard,
      rerunFinalReplacementSelected,
      rerunPolicySelectId,
      rerunPolicyRequestKey,
      rerunPolicyKindFromElement,
      rerunRawPolicySelection,
      rerunPolicyConflictReason,
      setRerunPolicySelectAuto,
      updateRerunPolicyOptionStates,
      applyRerunPolicySelectionRules,
      rerunPolicyChoiceForSummary,
      rerunSourceHandlingLine,
      renderRerunHandlingSummary,
      rerunStartPolicySummary,
      selectedOptionValues,
      renderRerunSelectOptions,
      renderRerunFilterOptions,
    };
  }

  window.__launchRerunEvidenceModule = { createLaunchRerunEvidenceModule };
})();
