(function () {
  function createCompletedReviewSelectedAtAGlanceModule(deps = {}) {
    const {
      backendRowStatusState, byId, captureSelectionScroll, completedFilterVisibilityLines,
      completedPrimaryConcernIsBenign, completedReviewFlagIsBenign,
      completedRowHasBenignAlreadyProcessedOutcome, completedRowLooksHealthy,
      completedValidationProofLabel, completedValidationStatusLabel, restoreSelectionScroll,
      setText, state, readOnlyBoundary = "Mutation guardrail: read-only evidence; backend routes own output and manifest changes.",
    } = deps;
    const COMPLETED_READ_ONLY_BOUNDARY = readOnlyBoundary;
    function completedSelectedAtAGlanceState(item) {
      if (!item) return "unknown";
      const backendState = typeof backendRowStatusState === "function" ? backendRowStatusState(item) : "";
      const benignAlreadyProcessed = completedRowHasBenignAlreadyProcessedOutcome(item);
      if (["blocked", "failed"].includes(backendState)) return "blocked";
      if (completedRowLooksHealthy(item) && ["", "normal", "warning", "changed", "unknown"].includes(backendState)) return "ready";
      if (benignAlreadyProcessed && ["", "normal", "warning", "changed", "unknown"].includes(backendState)) return "ready";
      if (["warning", "running", "skipped", "parked", "publishing", "health-check"].includes(backendState)) return "warning";
      if (["match", "ready", "completed"].includes(backendState)) return "ready";
      const reviewFlags = Array.isArray(item.review_flags) ? item.review_flags.filter((flag) => !completedReviewFlagIsBenign(flag, item)) : [];
      const consistencyIssues = Array.isArray(item.consistency_issues) ? item.consistency_issues.filter(Boolean) : [];
      const runtimeStatus = String(item.runtime_outcome_status || "").toLowerCase();
      const runtimeFreshness = String(item.runtime_outcome_freshness_status || "").toLowerCase();
      const missingOutput = item.output_exists === false || String(item.output_health || "").toLowerCase().includes("missing");
      const missingSidecar = item.sidecar_exists === false || consistencyIssues.some((issue) => String(issue).toLowerCase().includes("sidecar"));
      const recentRuntimeIssue = runtimeFreshness === "fresh" && ["failed", "error", "skipped"].some((value) => runtimeStatus.includes(value));
      if (missingOutput) return "blocked";
      if (missingSidecar || item.size_growth_over_5 || recentRuntimeIssue || reviewFlags.length || consistencyIssues.length) return "warning";
      return "ready";
    }

    function completedSelectedOutputUnavailable(item) {
      if (!item) return false;
      const outputHealth = String(item.output_health || "").toLowerCase();
      return item.output_exists === false
        || outputHealth.includes("missing")
        || outputHealth.includes("unavailable")
        || outputHealth.includes("without media");
    }

    function completedSelectedAtAGlanceStatus(item) {
      const state = completedSelectedAtAGlanceState(item);
      if (state === "blocked") return completedSelectedOutputUnavailable(item) ? "Output unavailable" : "Needs review";
      if (state === "warning") return "Review";
      if (state === "ready") return "Consistent-looking";
      return "No selection";
    }

    function completedSelectedVisibilitySummary(item) {
      const lines = completedFilterVisibilityLines(item);
      return lines
        .filter((line) => /^Selected row visible|^Active filters|^Hidden by current filters/.test(String(line || "")))
        .join(" ");
    }

    function completedSelectedLabel(item) {
      if (!item) return "No completed row selected";
      return item.output_file || item.lookup_title || item.output_path || item.source_path || "(unnamed row)";
    }

    function completedSelectedConcern(item) {
      if (!item) return "No row selected.";
      const healthy = completedRowLooksHealthy(item);
      return healthy && completedPrimaryConcernIsBenign(item)
        ? "row has no output, sidecar, size, or runtime blocker in the loaded completed manifest"
        : item.primary_concern
        || (item.output_exists === false ? "completed row points to a missing output" : "")
        || (item.size_growth_over_5 ? "output grew beyond policy threshold" : "")
        || item.operator_guidance
        || "no primary concern reported";
    }

    function completedSelectedSafeAction(item) {
      if (!item) return "Select a completed row to review output, sidecar, route, size, pending-publish, and diagnostics evidence.";
      return item.safe_next_action
        || item.operator_guidance
        || (completedSelectedAtAGlanceState(item) === "ready"
          ? "Compare output/sidecar proof and Pending Publish state before treating this as accepted."
          : "Read Completed Manifest, Pending Publish, Run Logs, and Last Stderr before rerun or cleanup.");
    }

    function completedSelectedTrustStatus(item) {
      if (!item) return "not selected";
      if (completedSelectedOutputUnavailable(item)) return "output unavailable";
      return completedRowLooksHealthy(item)
        ? "consistent-looking"
        : item.operator_trust_state || item.output_health || item.consistency_status || "not reported";
    }

    function completedSelectedRouteLabel(item) {
      if (!item) return "not reported";
      return item.route_decision_summary || item.route_label || item.route || "not reported";
    }

    function completedSelectedSizeLabel(item) {
      if (!item) return "unknown";
      return item.size_delta_label || item.size_reduction_text || "unknown";
    }

    function completedSelectedFormatBytes(value) {
      const number = Number(value);
      if (!Number.isFinite(number) || number < 0) return "";
      if (number === 0) return "0 B";
      const units = ["B", "KB", "MB", "GB", "TB"];
      let size = number;
      let unitIndex = 0;
      while (size >= 1024 && unitIndex < units.length - 1) {
        size /= 1024;
        unitIndex += 1;
      }
      const precision = unitIndex === 0 ? 0 : size >= 10 ? 1 : 2;
      return `${size.toFixed(precision).replace(/\.0+$/, "").replace(/(\.\d*[1-9])0+$/, "$1")} ${units[unitIndex]}`;
    }

    function completedSelectedSizeText(value, fallback) {
      return completedSelectedFormatBytes(value) || fallback || "not reported";
    }

    function completedSelectedRuntimeLabel(item) {
      if (!item) return "none reported";
      return [
        item.runtime_outcome_status,
        item.runtime_outcome_error_code,
        item.runtime_outcome_reason,
        item.runtime_outcome_freshness_status,
      ].filter(Boolean).join(" - ") || "none reported";
    }

    function completedSelectedPolicyLabel(item) {
      if (!item) return "not reported";
      return [item.route_reason_code, item.route_reason, item.route_decision_summary].filter(Boolean).join(" - ") || "not reported";
    }

    function completedSelectedSignalLine(label, value) {
      const text = value === null || value === undefined ? "" : String(value).trim();
      return text ? `${label}: ${text}` : "";
    }

    function completedSelectedRouteEvidenceLines(item) {
      return Array.isArray(item?.route_evidence_lines) ? item.route_evidence_lines.filter(Boolean).map(String) : [];
    }

    function completedSelectedDecisionRows(item, key, previewKey) {
      const details = Array.isArray(item?.[key]) ? item[key].filter((entry) => entry && typeof entry === "object") : [];
      if (details.length) {
        return details.map((entry) => {
          const parts = [
            entry.summary,
            !entry.summary && entry.track_label ? entry.track_label : "",
            !entry.summary && entry.language ? entry.language : "",
            !entry.summary && entry.source_codec ? entry.source_codec : "",
            !entry.summary && entry.action ? `-> ${entry.action}` : "",
            !entry.summary && entry.reason ? `(${entry.reason})` : "",
          ].filter(Boolean);
          return parts.join(" ").replace(/\s+/g, " ").trim();
        }).filter(Boolean);
      }
      return Array.isArray(item?.[previewKey]) ? item[previewKey].filter(Boolean).map(String) : [];
    }

    function completedSelectedSizeDetailLines(item) {
      if (!item) return ["Select a completed row to see source size, output size, and delta evidence."];
      const sourceSize = completedSelectedSizeText(item.source_size_bytes);
      const outputSize = item.output_size_text || completedSelectedSizeText(item.output_size_bytes);
      const sourceBytes = item.source_size_bytes !== null && item.source_size_bytes !== undefined ? `${item.source_size_bytes} bytes` : "";
      const outputBytes = item.output_size_bytes !== null && item.output_size_bytes !== undefined ? `${item.output_size_bytes} bytes` : "";
      const lines = [
        `Source to output: ${sourceSize} -> ${outputSize}`,
        sourceBytes || outputBytes ? `Bytes: source=${sourceBytes || "not reported"}; output=${outputBytes || "not reported"}` : "",
        completedSelectedSignalLine("Delta", completedSelectedSizeLabel(item)),
        completedSelectedSignalLine("Reduction text", item.size_reduction_text),
        completedSelectedSignalLine("Size bucket", item.size_bucket),
        completedSelectedSignalLine("Output health", item.output_health || (item.output_exists === false ? "missing output" : "")),
      ].filter(Boolean);
      return lines.length ? lines : ["No source/output size evidence was reported for this row."];
    }

    function completedSelectedRouteDetailLines(item) {
      if (!item) return ["Select a completed row to see route and encoder evidence."];
      const evidence = completedSelectedRouteEvidenceLines(item);
      const lines = [
        completedSelectedSignalLine("Route", completedSelectedRouteLabel(item)),
        completedSelectedSignalLine("Route decision", item.route_decision_summary),
        completedSelectedSignalLine("Encoder", item.encoder || item.encoder_kind),
        completedSelectedSignalLine("GPU", item.gpu_device),
        completedSelectedSignalLine("Publish", item.publish || item.publish_state),
        evidence.length ? "Route evidence:" : "",
        ...evidence.map((line) => `- ${line}`),
      ].filter(Boolean);
      return lines.length ? lines : ["No route evidence was reported for this row."];
    }

    function completedSelectedTriggerDetailLines(item) {
      if (!item) return ["Select a completed row to see route trigger evidence."];
      const lines = [
        completedSelectedSignalLine("Reason code", item.route_reason_code),
        completedSelectedSignalLine("Reason", item.route_reason),
        completedSelectedSignalLine("Decision summary", item.route_decision_summary),
      ].filter(Boolean);
      return lines.length ? lines : ["No route reason was reported for this row."];
    }

    function completedSelectedSizePolicyDetailLines(item) {
      if (!item) return ["Select a completed row to see size-policy evidence."];
      const lines = [
        completedSelectedSignalLine("Policy", completedSelectedSizePolicyLabel(item)),
        completedSelectedSignalLine("Status", item.size_policy_status),
        completedSelectedSignalLine("Mode", item.size_policy_mode),
        completedSelectedSignalLine("Routing profile", item.size_policy_routing_profile),
        completedSelectedSignalLine("Route reason code", item.size_policy_route_reason_code),
        item.size_policy_max_growth_percent !== null && item.size_policy_max_growth_percent !== undefined
          ? `Max growth: +${item.size_policy_max_growth_percent}%`
          : "",
        item.size_policy_limit_ratio !== null && item.size_policy_limit_ratio !== undefined
          ? `Limit ratio: ${item.size_policy_limit_ratio}x`
          : "",
        item.size_policy_ratio !== null && item.size_policy_ratio !== undefined
          ? `Observed ratio: ${item.size_policy_ratio}x`
          : "",
        item.size_policy_delta_vs_limit_percent !== null && item.size_policy_delta_vs_limit_percent !== undefined
          ? `Delta versus limit: ${item.size_policy_delta_vs_limit_percent}%`
          : "",
        item.size_policy_enforced ? "Enforcement: strict/blocking" : "",
        completedSelectedSignalLine("Message", item.size_policy_message),
      ].filter(Boolean);
      return lines.length ? lines : ["No backend size_policy was recorded for this row."];
    }

    function completedSelectedRuntimeDetailLines(item) {
      if (!item) return ["Select a completed row to see runtime/log evidence."];
      const lines = [
        completedSelectedSignalLine("Status", item.runtime_outcome_status),
        completedSelectedSignalLine("Event type", item.runtime_outcome_event_type),
        completedSelectedSignalLine("Event at", item.runtime_outcome_at),
        item.runtime_outcome_age_text || item.runtime_outcome_freshness_status
          ? `History age: ${item.runtime_outcome_age_text || "unknown"} (${item.runtime_outcome_freshness_status || "unknown"})`
          : "",
        item.runtime_outcome_stage || item.runtime_outcome_route
          ? `Stage/route: ${item.runtime_outcome_stage || "unknown"} / ${item.runtime_outcome_route || "unknown"}`
          : "",
        completedSelectedSignalLine("Error code", item.runtime_outcome_error_code),
        completedSelectedSignalLine("Reason", item.runtime_outcome_reason),
        item.runtime_outcome_publish_state || item.runtime_outcome_publish_mode
          ? `Publish: ${item.runtime_outcome_publish_state || "unknown"} / ${item.runtime_outcome_publish_mode || "unknown"}`
          : "",
        completedSelectedSignalLine("Runtime output", item.runtime_outcome_output_path),
        completedSelectedSignalLine("Runtime match", item.runtime_outcome_match),
      ].filter(Boolean);
      return lines.length ? lines : ["No runtime outcome was reported for this row."];
    }

    function completedSelectedAudioSubtitleDetailLines(item) {
      if (!item) return ["Select a completed row to see audio and subtitle decision evidence."];
      const audioRows = completedSelectedDecisionRows(item, "audio_decision_details", "audio_decision_preview");
      const subtitleRows = completedSelectedDecisionRows(item, "subtitle_decision_details", "subtitle_decision_preview");
      const verifierMismatches = Array.isArray(item.media_track_verification_mismatches)
        ? item.media_track_verification_mismatches
        : [];
      const lines = [
        `Audio decisions: ${item.audio_decision_count || 0}`,
        ...(audioRows.length ? audioRows.map((line) => `audio: ${line}`) : ["audio: no decision rows reported"]),
        `Subtitle decisions: ${item.subtitle_decision_count || 0}`,
        ...(subtitleRows.length ? subtitleRows.map((line) => `subtitle: ${line}`) : ["subtitle: no decision rows reported"]),
        `Output track verifier: ${item.media_track_verification_status || "unknown"}`,
        item.media_track_verification_reason ? `verifier: ${item.media_track_verification_reason}` : "verifier: no backend result reported",
        ...verifierMismatches.map((mismatch) => `verifier mismatch: ${mismatch.kind || "track"} ${mismatch.property || "difference"}; expected=${mismatch.expected ?? "unknown"}; actual=${mismatch.actual ?? "unknown"}`),
      ];
      return lines;
    }

    function completedSelectedSignalDetailLines(signalKey, item) {
      const key = String(signalKey || "");
      if (key === "route") return completedSelectedRouteDetailLines(item);
      if (key === "trigger-route-reason") return completedSelectedTriggerDetailLines(item);
      if (key === "size-policy") return completedSelectedSizePolicyDetailLines(item);
      if (key === "runtime-log-evidence") return completedSelectedRuntimeDetailLines(item);
      if (key === "audio-subtitles") return completedSelectedAudioSubtitleDetailLines(item);
      return completedSelectedSizeDetailLines(item);
    }

    function completedSelectedSizeDeltaPercent(item) {
      if (typeof item?.size_delta_percent === "number") return Number(item.size_delta_percent);
      const parsed = Number.parseFloat(String(item?.size_delta_label || "").replace("%", ""));
      return Number.isFinite(parsed) ? parsed : null;
    }

    function completedSelectedPositiveGrowth(item) {
      const delta = completedSelectedSizeDeltaPercent(item);
      return delta !== null && delta > 0;
    }

    function completedSelectedRouteLooksEncode(item) {
      return [item?.route_decision_summary, item?.route_label, item?.route]
        .filter(Boolean)
        .join(" ")
        .toLowerCase()
        .includes("encode");
    }

    function completedSelectedSizePolicyLabel(item) {
      if (!item) return "not evaluated";
      const evidence = item.size_policy_limit_label || item.size_policy_message || item.size_policy_status || "";
      if (item.size_policy_exceeded) return evidence ? `exceeded recorded policy (${evidence})` : "exceeded recorded policy";
      if (item.size_policy_available && completedSelectedPositiveGrowth(item)) return evidence ? `within recorded policy (${evidence})` : "within recorded policy";
      if (item.size_policy_available) return evidence ? `recorded (${evidence})` : "recorded";
      if (item.size_growth_over_5) return "not recorded; legacy +5% review";
      return "not recorded";
    }

    function completedSelectedDiagnosisLine(item) {
      if (!item) return "Select a completed row to see the key evidence behind route, size, runtime, and output-health differences.";
      const sizeLabel = completedSelectedSizeLabel(item);
      if (completedSelectedOutputUnavailable(item)) {
        return "Output is unavailable; resolve final placement or pending-publish proof before judging size or route differences.";
      }
      if (item.size_policy_exceeded) {
        return `Output grew ${sizeLabel} and exceeded a recorded backend size_policy.`;
      }
      if (item.size_growth_over_5 && !item.size_policy_available) {
        return `Output grew ${sizeLabel} and no backend size_policy was recorded for that growth.`;
      }
      if (completedSelectedPositiveGrowth(item) && item.size_policy_available) {
        return `Output grew ${sizeLabel}, but the recorded backend size_policy says the growth stayed within limit.`;
      }
      if (completedSelectedPositiveGrowth(item)) {
        return `Output grew ${sizeLabel}; route reason and logs are the key evidence to check.`;
      }
      if (completedRowLooksHealthy(item)) {
        return "No output, sidecar, size, or runtime blocker is visible in the loaded completed evidence.";
      }
      return completedSelectedConcern(item);
    }

    function completedSelectedWhyItMatters(item) {
      if (!item) return "The selected-row summary is read-only and only formats already-loaded backend evidence.";
      if (completedSelectedOutputUnavailable(item)) {
        return "Size and route evidence cannot prove success until Completed, Pending Publish, and final-placement proof agree about where the output is.";
      }
      if (item.size_policy_exceeded) {
        return "A recorded size_policy exists and says this output crossed the configured limit, so route metadata and logs decide whether the result is acceptable.";
      }
      if (item.size_growth_over_5 && !item.size_policy_available) {
        return completedSelectedRouteLooksEncode(item)
          ? "This was an encode result with growth beyond the legacy threshold, but no recorded size_policy explains why that growth is acceptable."
          : "The output grew beyond the legacy threshold, but no recorded size_policy explains why that growth is acceptable.";
      }
      if (completedSelectedPositiveGrowth(item) && item.size_policy_available) {
        return "Positive growth can be expected for compatibility, subtitle, or audio choices when backend size_policy records it as within limit.";
      }
      if (completedSelectedRouteLooksEncode(item)) {
        return "The route reason is the strongest available explanation for why this file behaved differently; check encoder/log evidence if the size is surprising.";
      }
      return "This panel highlights the row facts that are most useful while flipping between completed outputs; raw detail remains available below.";
    }

    function completedSelectedEvidenceGaps(item) {
      if (!item) return [];
      const gaps = [];
      if (completedSelectedOutputUnavailable(item)) gaps.push("Output placement proof is missing or unavailable.");
      if (!item.size_policy_available) gaps.push("No backend size_policy recorded.");
      if (!item.runtime_outcome_status && !item.runtime_outcome_reason) gaps.push("No runtime outcome reported.");
      if (item.sidecar_exists === false) gaps.push("Sidecar proof is missing.");
      else if (item.sidecar_exists !== true && !item.sidecar_path && !item.expected_sidecar_path) gaps.push("Sidecar proof not reported.");
      if (completedSelectedPolicyLabel(item) === "not reported") gaps.push("Route reason not reported.");
      return gaps;
    }

    function completedSelectedNextChecks(item) {
      if (!item) return ["Select a completed row.", "Review route and size evidence.", "Open raw detail only when needed."];
      const checks = [];
      const add = (value) => {
        if (value && !checks.includes(value)) checks.push(value);
      };
      if (completedSelectedOutputUnavailable(item)) {
        add("Check Pending Publish and final placement proof.");
        add("Open Completed Manifest and sidecar/output evidence.");
        add("Read Run Logs or Last Stderr before rerun.");
      }
      if (item.size_policy_exceeded || item.size_growth_over_5 || completedSelectedPositiveGrowth(item)) {
        add("Open route metadata.");
        add("Read Run Logs or Last Stderr.");
        add("Check encoder settings or output bitrate.");
      }
      if (completedSelectedPolicyLabel(item) === "not reported") add("Open route metadata.");
      if (!item.runtime_outcome_status && !item.runtime_outcome_reason) add("Read Run Logs or Last Stderr.");
      add(completedSelectedSafeAction(item));
      return checks.slice(0, 3);
    }

    function completedSelectedSignalTone(label, item) {
      if (!item) return "muted";
      if (label === "Size change") {
        if (completedSelectedOutputUnavailable(item) || item.size_policy_exceeded) return "danger";
        if (item.size_growth_over_5 || completedSelectedPositiveGrowth(item)) return "warning";
        return "success";
      }
      if (label === "Size policy") {
        if (item.size_policy_exceeded) return "danger";
        if (!item.size_policy_available) return "warning";
        return "success";
      }
      if (label === "Runtime/log evidence") {
        const runtime = completedSelectedRuntimeLabel(item).toLowerCase();
        if (runtime === "none reported") return "warning";
        if (["failed", "error", "skipped"].some((value) => runtime.includes(value))) return "danger";
        if (["ok", "succeeded", "success"].some((value) => runtime.includes(value))) return "success";
      }
      return "info";
    }

    function completedSelectedKeySignals(item) {
      return [
        { key: "size-change", label: "Size change", value: completedSelectedSizeLabel(item) },
        { key: "route", label: "Route", value: completedSelectedRouteLabel(item) },
        { key: "trigger-route-reason", label: "Trigger / route reason", value: completedSelectedPolicyLabel(item) },
        { key: "size-policy", label: "Size policy", value: completedSelectedSizePolicyLabel(item) },
        { key: "runtime-log-evidence", label: "Runtime/log evidence", value: completedSelectedRuntimeLabel(item) },
        { key: "audio-subtitles", label: "Audio/Subtitles", value: `${item?.audio_decision_count || 0} audio / ${item?.subtitle_decision_count || 0} subtitle tracks` },
      ];
    }

    function completedSelectedNode(tagName, className, text) {
      const node = document.createElement(tagName);
      if (className) node.className = className;
      if (text !== undefined && text !== null) node.textContent = String(text);
      return node;
    }

    function completedSelectedSignalItem(signal, selected, rowItem) {
      const item = completedSelectedNode("button", "completed-selected-signal");
      item.type = "button";
      item.dataset.tone = signal.tone || "info";
      item.dataset.signalKey = signal.key;
      item.setAttribute("aria-pressed", selected ? "true" : "false");
      item.setAttribute("aria-controls", "completed-selected-signal-detail");
      item.title = `Show ${signal.label} details`;
      if (selected) item.classList.add("is-selected");
      item.addEventListener("click", () => {
        selectCompletedSignal(signal.key, rowItem);
      });
      item.appendChild(completedSelectedNode("span", "completed-selected-label", signal.label));
      item.appendChild(completedSelectedNode("strong", "completed-selected-signal-value", signal.value || "not reported"));
      return item;
    }

    function completedSelectedActiveSignal(signals) {
      if (!signals.length) return null;
      const selectedKey = String(state.selectedCompletedSignalKey || "");
      const selected = signals.find((signal) => signal.key === selectedKey) || signals[0];
      state.selectedCompletedSignalKey = selected.key;
      return selected;
    }

    function selectCompletedSignal(signalKey, item) {
      const scrollSnapshot = captureSelectionScroll();
      state.selectedCompletedSignalKey = signalKey || "size-change";
      renderCompletedSelectedAtAGlance(item || null);
      const summary = byId("completed-selected-summary");
      const selectedButton = summary
        ? Array.from(summary.querySelectorAll("[data-signal-key]")).find((node) => node.dataset.signalKey === state.selectedCompletedSignalKey)
        : null;
      if (selectedButton && typeof selectedButton.focus === "function") {
        selectedButton.focus({ preventScroll: true });
      }
      restoreSelectionScroll(scrollSnapshot);
    }

    function completedSelectedSignalDetailPanel(signal, item) {
      const panel = completedSelectedNode("section", "completed-selected-signal-detail");
      panel.id = "completed-selected-signal-detail";
      panel.dataset.signalKey = signal?.key || "size-change";
      panel.setAttribute("role", "region");
      panel.setAttribute("aria-live", "polite");
      panel.setAttribute("aria-label", `${signal?.label || "Size change"} detail`);
      panel.appendChild(completedSelectedNode("span", "completed-selected-label", `${signal?.label || "Size change"} detail`));
      const list = completedSelectedNode("ul", "completed-selected-signal-detail-list");
      completedSelectedSignalDetailLines(signal?.key || "size-change", item).forEach((line) => {
        list.appendChild(completedSelectedNode("li", "", line));
      });
      panel.appendChild(list);
      return panel;
    }

    function completedSelectedListBlock(title, items, className) {
      const block = completedSelectedNode("div", className || "completed-selected-list-card");
      block.appendChild(completedSelectedNode("span", "completed-selected-label", title));
      const list = completedSelectedNode("ol", "completed-selected-list");
      items.forEach((item) => {
        list.appendChild(completedSelectedNode("li", "", item));
      });
      block.appendChild(list);
      return block;
    }

    function completedSelectedPaths(item) {
      const details = completedSelectedNode("details", "completed-selected-paths");
      details.appendChild(completedSelectedNode("summary", "", "Paths"));
      const list = completedSelectedNode("div", "completed-selected-path-list");
      const paths = [
        ["Output", item?.output_path],
        ["Source", item?.source_path],
        ["Sidecar", item?.sidecar_path],
      ].filter((entry) => entry[1]);
      if (!paths.length) {
        list.appendChild(completedSelectedNode("p", "completed-selected-path-empty", "No output, source, or sidecar path is reported for this row."));
      } else {
        paths.forEach(([label, value]) => {
          const row = completedSelectedNode("div", "completed-selected-path-row");
          row.appendChild(completedSelectedNode("span", "completed-selected-label", label));
          row.appendChild(completedSelectedNode("code", "completed-selected-path-value", value));
          list.appendChild(row);
        });
      }
      details.appendChild(list);
      return details;
    }

    function completedSelectedSummaryNodes(item, status, statusState) {
      const strip = completedSelectedNode("div", "completed-selected-decision-strip");
      const titleWrap = completedSelectedNode("div", "completed-selected-title-wrap");
      titleWrap.appendChild(completedSelectedNode("span", "completed-selected-label", "File/title"));
      titleWrap.appendChild(completedSelectedNode("strong", "completed-selected-title", completedSelectedLabel(item)));
      titleWrap.appendChild(completedSelectedNode("span", "completed-selected-trust", `Trust state: ${completedSelectedTrustStatus(item)}`));
      strip.appendChild(titleWrap);

      const badge = completedSelectedNode("strong", "completed-selected-status-chip", status);
      badge.dataset.state = statusState;
      strip.appendChild(badge);

      const diagnosis = completedSelectedNode("section", "completed-selected-diagnosis-card");
      diagnosis.appendChild(completedSelectedNode("span", "completed-selected-label", "Why this output looks different"));
      diagnosis.appendChild(completedSelectedNode("p", "completed-selected-diagnosis-text", completedSelectedDiagnosisLine(item)));

      const evidenceGrid = completedSelectedNode("div", "completed-selected-signal-grid");
      const signals = completedSelectedKeySignals(item).map((signal) => ({
        ...signal,
        tone: completedSelectedSignalTone(signal.label, item),
      }));
      const activeSignal = completedSelectedActiveSignal(signals);
      signals.forEach((signal) => {
        evidenceGrid.appendChild(completedSelectedSignalItem(signal, activeSignal?.key === signal.key, item));
      });

      const why = completedSelectedNode("div", "completed-selected-meaning");
      why.appendChild(completedSelectedNode("span", "completed-selected-label", "Why it matters"));
      why.appendChild(completedSelectedNode("p", "completed-selected-priority-text", completedSelectedWhyItMatters(item)));

      const gaps = completedSelectedEvidenceGaps(item);
      const gapBlock = gaps.length
        ? completedSelectedListBlock("Evidence gaps", gaps, "completed-selected-list-card completed-selected-gap-card")
        : null;
      const checks = completedSelectedListBlock("What to check next", completedSelectedNextChecks(item), "completed-selected-list-card completed-selected-check-card");

      const authority = completedSelectedNode(
        "p",
        "completed-selected-authority",
        COMPLETED_READ_ONLY_BOUNDARY,
      );

      return [strip, diagnosis, evidenceGrid, completedSelectedSignalDetailPanel(activeSignal, item), why, gapBlock, checks, completedSelectedPaths(item), authority].filter(Boolean);
    }

    function completedSelectedAtAGlanceLines(item) {
      const sharedSummary = window.mediaPipelineDom?.selectedRowAtAGlanceLines;
      const authority = COMPLETED_READ_ONLY_BOUNDARY;
      if (!item) {
        return typeof sharedSummary === "function"
          ? sharedSummary({
            title: "Selected Completed row",
            item: null,
            emptyNextStep: "Next step: select a completed row to review output, sidecar, route, size, pending-publish, and diagnostics evidence.",
            authority: COMPLETED_READ_ONLY_BOUNDARY,
          })
          : [
            "Selected Completed row: none",
            "Next step: select a completed row to review output, sidecar, route, size, pending-publish, and diagnostics evidence.",
            COMPLETED_READ_ONLY_BOUNDARY,
          ];
      }
      const concern = completedSelectedConcern(item);
      const safeAction = completedSelectedSafeAction(item);
      const outputReview = `${item.output_path || "output not reported"}; ${completedSelectedRouteLabel(item) || "route not reported"}; size=${completedSelectedSizeLabel(item)}; audio=${item.audio_decision_count || 0}; subtitles=${item.subtitle_decision_count || 0}; health=${item.output_health || "unknown"}`;
      const trustStatus = completedSelectedTrustStatus(item);
      if (typeof sharedSummary === "function") {
        return sharedSummary({
          title: "Selected Completed row",
          item,
          label: completedSelectedLabel(item),
          trustStatus,
          atAGlanceStatus: completedSelectedAtAGlanceStatus(item),
          proofLabel: "Output review",
          proof: outputReview,
          primaryConcern: concern,
          safeNextStep: safeAction,
          filterVisibility: completedSelectedVisibilitySummary(item) || "not evaluated",
          authority,
        });
      }
      return [
        `Selected Completed row: ${completedSelectedLabel(item)}`,
        `Trust/status: ${trustStatus}; at-a-glance=${completedSelectedAtAGlanceStatus(item)}`,
        `Output review: ${outputReview}`,
        `Primary concern: ${concern}`,
        `Safe next step: ${safeAction}`,
        `Filter visibility: ${completedSelectedVisibilitySummary(item) || "not evaluated"}`,
        authority,
      ];
    }

    function renderCompletedSelectedAtAGlance(item) {
      const status = completedSelectedAtAGlanceStatus(item);
      const statusState = completedSelectedAtAGlanceState(item);
      setText("completed-selected-status", status);
      const statusNode = byId("completed-selected-status");
      if (statusNode) statusNode.dataset.state = statusState;
      const summaryNode = byId("completed-selected-summary");
      if (!summaryNode || typeof summaryNode.replaceChildren !== "function") {
        setText("completed-selected-summary", completedSelectedAtAGlanceLines(item).join("\n"));
        return;
      }
      summaryNode.className = `completed-selected-summary${item ? "" : " is-empty"}`;
      summaryNode.dataset.state = statusState;
      summaryNode.replaceChildren(...completedSelectedSummaryNodes(item, status, statusState));
    }

    return {
      completedSelectedAtAGlanceState, completedSelectedOutputUnavailable, completedSelectedAtAGlanceStatus,
      completedSelectedVisibilitySummary, completedSelectedLabel, completedSelectedConcern,
      completedSelectedSafeAction, completedSelectedTrustStatus, completedSelectedRouteLabel,
      completedSelectedSizeLabel, completedSelectedFormatBytes, completedSelectedSizeText,
      completedSelectedRuntimeLabel, completedSelectedPolicyLabel, completedSelectedSignalLine,
      completedSelectedRouteEvidenceLines, completedSelectedDecisionRows, completedSelectedSizeDetailLines,
      completedSelectedRouteDetailLines, completedSelectedTriggerDetailLines, completedSelectedSizePolicyDetailLines,
      completedSelectedRuntimeDetailLines, completedSelectedAudioSubtitleDetailLines, completedSelectedSignalDetailLines,
      completedSelectedSizeDeltaPercent, completedSelectedPositiveGrowth, completedSelectedRouteLooksEncode,
      completedSelectedSizePolicyLabel, completedSelectedDiagnosisLine, completedSelectedWhyItMatters,
      completedSelectedEvidenceGaps, completedSelectedNextChecks, completedSelectedSignalTone,
      completedSelectedKeySignals, completedSelectedNode, completedSelectedSignalItem,
      completedSelectedActiveSignal, selectCompletedSignal, completedSelectedSignalDetailPanel,
      completedSelectedListBlock, completedSelectedPaths, completedSelectedSummaryNodes,
      completedSelectedAtAGlanceLines, renderCompletedSelectedAtAGlance,    };
  }

  window.__completedReviewSelectedAtAGlanceModule = {
    createCompletedReviewSelectedAtAGlanceModule,
  };
})();
