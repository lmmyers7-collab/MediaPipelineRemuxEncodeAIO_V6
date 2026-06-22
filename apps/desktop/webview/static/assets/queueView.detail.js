(function () {
  function createQueueDetailModule(deps) {
    deps = deps || {};
    const byId = deps.byId || function () { return null; };
    const setText = deps.setText || function () {};
    const queueListText = deps.queueListText || function (value) { return Array.isArray(value) && value.length ? value.join(", ") : "none"; };
    const queueRowKey = deps.queueRowKey || function () { return ""; };
    const queueSelectedQuickSignalLines = deps.queueSelectedQuickSignalLines || function () { return []; };
    const queueSelectedAtAGlanceLines = deps.queueSelectedAtAGlanceLines || function () { return []; };
    const queueInvestigationSignalLines = deps.queueInvestigationSignalLines || function () { return []; };
    const queueSelectedOpenTargetLines = deps.queueSelectedOpenTargetLines || function () { return []; };
    const renderQueueSelectedAtAGlance = deps.renderQueueSelectedAtAGlance || function () {};
    const requestQueueDiagnosticsAction = deps.requestQueueDiagnosticsAction || async function () {};
    const diagnosticsBridge = window.mediaPipelineDiagnosticsBridge || {};
    const appendDiagnosticsBridgeGroupedButtons = deps.appendDiagnosticsBridgeGroupedButtons || diagnosticsBridge.appendDiagnosticsBridgeGroupedButtons;
    const appendDiagnosticsBridgeButton = deps.appendDiagnosticsBridgeButton || diagnosticsBridge.appendDiagnosticsBridgeButton;
    const diagnosticsBridgeHandoffLines = deps.diagnosticsBridgeHandoffLines || diagnosticsBridge.diagnosticsBridgeHandoffLines;
    const diagnosticsBridgeRowTrustLines = deps.diagnosticsBridgeRowTrustLines || diagnosticsBridge.diagnosticsBridgeRowTrustLines;
    const commandHistoryCompactEvidenceLine = deps.commandHistoryCompactEvidenceLine || window.commandHistoryCompactEvidenceLine;

    function queueRowReviewChecklistLines(item) {
      if (!item) {
        return [
          "Selected row review checklist:",
          "Select a queue row to see launch readiness, route evidence, runtime history, and safe next steps.",
        ];
      }
      const reviewFlags = Array.isArray(item.review_flags) ? item.review_flags.filter(Boolean) : [];
      const runtimeNotes = Array.isArray(item.runtime_check_notes) ? item.runtime_check_notes.filter(Boolean) : [];
      const runtimeStatus = String(item.runtime_outcome_status || "").toLowerCase();
      const runtimeFreshness = String(item.runtime_outcome_freshness_status || "").toLowerCase();
      const blocked = Boolean(item.blocked_reason || item.blocked_reason_code || String(item.status || "").toLowerCase().includes("blocked") || item.error);
      const recentRuntimeIssue = runtimeFreshness === "fresh" && ["failed", "error", "skipped"].some((value) => runtimeStatus.includes(value));
      const needsReview = blocked || recentRuntimeIssue || reviewFlags.length > 0 || String(item.operator_severity || "").toLowerCase() === "warning";
      const backendTrustState = String(item.operator_trust_state || "").trim();
      const lines = [
        "Selected row review checklist:",
        `Row state: ${backendTrustState || (blocked ? "blocked" : needsReview ? "review" : "ready-looking")}`,
        `Operator status: ${item.operator_status || "not reported"}`,
        `Route decision: ${item.route_decision_summary || item.route_name || "not reported"}`,
        `Runtime history: ${item.runtime_outcome_status || "none"}${item.runtime_outcome_freshness_status ? ` (${item.runtime_outcome_freshness_status})` : ""}`,
        `Runtime checks: ${item.runtime_checks_deferred ? "deferred until processing start" : "no deferred checks reported"}`,
        `Review flags: ${reviewFlags.length ? reviewFlags.join(", ") : "none"}`,
      ];
      const reviewFlagExplanations = typeof window.mediaPipelineDom?.reviewFlagExplanationLines === "function"
        ? window.mediaPipelineDom.reviewFlagExplanationLines(reviewFlags, {
          title: "Review flag explanations:",
          emptyMessage: "No Queue review flags were reported for this row.",
          guardrail: "Mutation guardrail: review-flag explanations translate Queue snapshot markers only; they cannot launch, reorder, drop, or rewrite queue entries.",
        })
        : [];
      lines.push(...reviewFlagExplanations);
      if (item.blocked_reason_code || item.blocked_reason) {
        lines.push(`Blocker: ${[item.blocked_reason_code, item.blocked_reason].filter(Boolean).join(" - ")}`);
      }
      if (item.runtime_outcome_error_code || item.runtime_outcome_reason) {
        lines.push(`Runtime issue: ${[item.runtime_outcome_error_code, item.runtime_outcome_reason].filter(Boolean).join(" - ")}`);
      }
      runtimeNotes.slice(0, 3).forEach((note) => lines.push(`Runtime check note: ${note}`));
      if (item.operator_guidance) {
        lines.push(`Operator action: ${item.operator_guidance}`);
      } else if (blocked) {
        lines.push("Operator action: inspect the blocker and Diagnostics before launching or reprocessing this source.");
      } else if (recentRuntimeIssue) {
        lines.push("Operator action: recent runtime failure is fresh; inspect Run Logs and Last Stderr before launching again.");
      } else if (item.runtime_checks_deferred) {
        lines.push("Operator action: row can remain queued, but stability/output checks will run only when processing starts.");
      } else {
        lines.push("Operator action: row looks ready from the current queue snapshot; launch remains backend-owned.");
      }
      lines.push("Mutation guardrail: selected-row detail is read-only and cannot launch, reorder, drop, or rewrite queue entries.");
      return lines;
    }

    function queueRowIssueDigestLines(item) {
      if (!item) return [];
      const reviewFlags = Array.isArray(item.review_flags) ? item.review_flags.filter(Boolean) : [];
      const issues = [];
      const blocked = Boolean(item.blocked_reason || item.blocked_reason_code || String(item.status || "").toLowerCase().includes("blocked") || item.error);
      const runtimeStatus = String(item.runtime_outcome_status || "").toLowerCase();
      const runtimeFreshness = String(item.runtime_outcome_freshness_status || "").toLowerCase();
      const recentRuntimeIssue = runtimeFreshness === "fresh" && ["failed", "error", "skipped"].some((value) => runtimeStatus.includes(value));
      if (blocked) issues.push(`blocked: ${[item.blocked_reason_code, item.blocked_reason, item.error].filter(Boolean).join(" - ") || "reason not reported"}`);
      if (recentRuntimeIssue) issues.push(`fresh runtime issue: ${[item.runtime_outcome_error_code, item.runtime_outcome_reason, item.runtime_outcome_status].filter(Boolean).join(" - ") || "failed/skipped"}`);
      if (item.runtime_checks_deferred) issues.push("source/output runtime checks are deferred until launch");
      reviewFlags.forEach((flag) => issues.push(`review flag: ${flag}`));
      const level = blocked ? "blocked" : recentRuntimeIssue || reviewFlags.length ? "review" : item.runtime_checks_deferred ? "launch-check-needed" : "ready-looking";
      const backendTrustState = String(item.operator_trust_state || "").trim();
      const lines = [
        "Selected queue issue digest:",
        `Issue level: ${backendTrustState || level}`,
        `Primary issue(s): ${issues.length ? issues.join("; ") : "none reported by the queue snapshot"}`,
        `Proof to inspect: route=${item.route_decision_summary || item.route_name || "not reported"}; source=${item.source_path || "not reported"}`,
        `Runtime proof: ${item.runtime_outcome_status || "none"}${item.runtime_outcome_freshness_status ? ` (${item.runtime_outcome_freshness_status})` : ""}`,
      ];
      if (blocked || recentRuntimeIssue) {
        lines.push("Safe next action: use Queue Diagnostics Cross-Links before launch; check Queue Snapshot, Last Stderr, Run Logs, and Latest Failure if present.");
      } else if (item.runtime_checks_deferred) {
        lines.push("Safe next action: launch remains backend-owned; expect source stability and output-path checks to happen only when processing starts.");
      } else {
        lines.push("Safe next action: row is coherent in the current snapshot; use Launch only after page-level readiness and schedule checks agree.");
      }
      return lines;
    }

    function queueRowCombinedReviewPlanLines(item) {
      if (!item) return [];
      const reviewFlags = Array.isArray(item.review_flags) ? item.review_flags.filter(Boolean) : [];
      const runtimeStatus = String(item.runtime_outcome_status || "").toLowerCase();
      const runtimeFreshness = String(item.runtime_outcome_freshness_status || "").toLowerCase();
      const blocked = Boolean(item.blocked_reason || item.blocked_reason_code || String(item.status || "").toLowerCase().includes("blocked") || item.error);
      const recentRuntimeIssue = runtimeFreshness === "fresh" && ["failed", "error", "skipped"].some((value) => runtimeStatus.includes(value));
      const parseReview = [item.blocked_reason_code, item.blocked_reason, item.error, ...reviewFlags].some((value) => /tv_parse|season|episode|parse/i.test(String(value || "")));
      const signals = [];
      if (blocked) signals.push("launch blocker");
      if (recentRuntimeIssue) signals.push("fresh runtime failure");
      if (item.runtime_checks_deferred) signals.push("deferred source/output checks");
      if (parseReview) signals.push("TV parse confidence");
      reviewFlags.forEach((flag) => {
        if (!signals.some((existing) => String(flag).toLowerCase().includes(existing.toLowerCase()))) {
          signals.push(`review flag ${flag}`);
        }
      });
      const readFirst = ["Queue Snapshot"];
      if (blocked || recentRuntimeIssue || parseReview) readFirst.push("Last Stderr", "Run Logs");
      if (blocked || recentRuntimeIssue) readFirst.push("Latest Failure");
      if (item.runtime_checks_deferred) readFirst.push("ActiveJobs");
      const crossCheck = ["Launch readiness", "Completed exclusions"];
      if (item.runtime_checks_deferred || recentRuntimeIssue) crossCheck.push("ActiveJobs");
      crossCheck.push("Pending Publish if deferred publish is enabled");
      const lines = [
        "Combined row review plan:",
        `Signal count: ${signals.length}`,
        `Signals: ${signals.length ? signals.join("; ") : "none reported by the selected queue row"}`,
        `Read first: ${[...new Set(readFirst)].join(" -> ")}`,
        `Cross-check: ${[...new Set(crossCheck)].join(" -> ")}`,
      ];
      if (blocked || recentRuntimeIssue || parseReview) {
        lines.push("Decision: do not start this source from Launch until the blocker/runtime/parse evidence is explained by backend artifacts.");
      } else if (item.runtime_checks_deferred) {
        lines.push("Decision: launch may still be reasonable, but expect backend runtime checks to be the authority when processing starts.");
      } else {
        lines.push("Decision: row is ready-looking in the current snapshot; page-level Launch readiness still owns start safety.");
      }
      lines.push("Guardrail: this combined plan is read-only and cannot change queue order, launch scope, completed exclusions, or source files.");
      return lines;
    }

    function queueRealMediaTraceLines(item) {
      if (!item) return [];
      const routeEvidence = Array.isArray(item.route_evidence_lines) ? item.route_evidence_lines.filter(Boolean) : [];
      const runtimeProof = item.runtime_outcome_status || item.runtime_outcome_reason
        ? [item.runtime_outcome_status, item.runtime_outcome_error_code, item.runtime_outcome_reason, item.runtime_outcome_freshness_status].filter(Boolean).join(" - ")
        : "none loaded yet";
      const lines = [
        "Real-media sample trace: Queue",
        `Trace key: source=${item.source_path || "not reported"}; relative=${item.relative_path || "not reported"}`,
        `Queue proof: route=${item.route_decision_summary || item.route_name || "not reported"}; reason=${[item.route_reason_code, item.route_reason].filter(Boolean).join(" - ") || "not reported"}`,
        `Runtime proof: ${runtimeProof}`,
        "What this proves: the backend queue snapshot can see the source and has made a route/readiness decision for it.",
        "What remains unproven: FFmpeg execution, subtitle/audio result, completed output/sidecar, size-growth policy result, and pending-publish/drain outcome.",
      ];
      if (routeEvidence.length) {
        lines.push("Route evidence to compare after the run:");
        routeEvidence.slice(0, 6).forEach((line) => lines.push(`  ${line}`));
      }
      if (item.runtime_checks_deferred) {
        lines.push("Runtime-check boundary: source stability and output-path capability are deferred until backend processing starts.");
      }
      lines.push("Next evidence stop: after processing, find the same source/output in Completed; if deferred publish is enabled, also inspect Pending Publish and drain summary.");
      lines.push("Mutation guardrail: this trace is read-only and cannot launch, reorder, drop, rewrite, rerun, or mutate files.");
      return lines;
    }

    function queueRowTrustSummaryLines(item) {
      if (!item || typeof diagnosticsBridgeRowTrustLines !== "function") return [];
      const reviewFlags = Array.isArray(item.review_flags) ? item.review_flags.filter(Boolean) : [];
      const blocked = Boolean(item.blocked_reason || item.blocked_reason_code || String(item.status || "").toLowerCase().includes("blocked") || item.error);
      const runtimeStatus = String(item.runtime_outcome_status || "").toLowerCase();
      const runtimeFreshness = String(item.runtime_outcome_freshness_status || "").toLowerCase();
      const recentRuntimeIssue = runtimeFreshness === "fresh" && ["failed", "error", "skipped"].some((value) => runtimeStatus.includes(value));
      const backendTrustState = String(item.operator_trust_state || "").trim();
      const trustState = backendTrustState || (blocked
        ? "blocked"
        : recentRuntimeIssue || reviewFlags.length || item.runtime_checks_deferred
          ? "review-before-launch"
          : "ready-looking");
      const concern = item.primary_concern || (blocked
        ? [item.blocked_reason_code, item.blocked_reason, item.error].filter(Boolean).join(" - ") || "blocked row"
        : recentRuntimeIssue
          ? [item.runtime_outcome_status, item.runtime_outcome_error_code, item.runtime_outcome_reason].filter(Boolean).join(" - ") || "fresh runtime issue"
          : item.runtime_checks_deferred
            ? "source stability and output-path checks are deferred until backend launch"
            : reviewFlags.length
              ? reviewFlags.join(", ")
              : "row has no blocker in the loaded queue snapshot");
      const proofSummary = Array.isArray(item.proof_summary) ? item.proof_summary.filter(Boolean) : [];
      return diagnosticsBridgeRowTrustLines("Queue selected row", queueDiagnosticsActionsForRow(item), {
        trustState,
        primaryConcern: concern,
        evidence: proofSummary.length ? proofSummary : [
          item.route_decision_summary || item.route_name ? `route=${item.route_decision_summary || item.route_name}` : "",
          item.operator_status || item.status ? `status=${item.operator_status || item.status}` : "",
          item.source_path ? `source=${item.source_path}` : "",
          item.runtime_outcome_status || item.runtime_outcome_reason ? `runtime=${[item.runtime_outcome_status, item.runtime_outcome_error_code, item.runtime_outcome_reason].filter(Boolean).join(" - ")}` : "",
        ],
        safeAction: item.safe_next_action || (blocked || recentRuntimeIssue ? "inspect Queue Snapshot, Last Stderr, Run Logs, and Latest Failure before launch." : "use Launch only after page-level readiness and schedule checks agree."),
        unsafeAction: item.unsafe_if_ignored || "launch, rerun, reorder, drop, or rewrite queue entries based only on this selected row.",
        owningPages: "Queue owns source readiness; Completed owns skip/collision proof; Pending Publish owns parked output safety; Diagnostics owns artifact/log evidence.",
      });
    }

    function queueDiagnosticsActionsForRow(item) {
      const actions = [];
      queueAddDiagnosticsAction(actions, "open", "queue_snapshot", "Open Queue Snapshot", "Inspect the backend-authored queue snapshot that produced this row.");
      queueAddDiagnosticsAction(actions, "open", "run_logs", "Open Run Logs", "Inspect recent pipeline logs before launching or reprocessing.");
      queueAddDiagnosticsAction(actions, "tail", "last_stderr_log", "Read Last Stderr", "Read the newest bounded stderr tail for FFmpeg, probe, subtitle, copy, or publish errors.");
      if (!item) {
        queueAddDiagnosticsAction(actions, "open", "state", "Open State Folder", "Inspect runtime state only when close-readiness says it is safe.");
        return actions;
      }
      const hasRuntimeIssue = Boolean(item.runtime_outcome_error_code || item.runtime_outcome_reason || String(item.runtime_outcome_status || "").toLowerCase().includes("fail"));
      const blocked = Boolean(item.blocked_reason || item.blocked_reason_code || item.error);
      if (blocked || hasRuntimeIssue) {
        queueAddDiagnosticsAction(actions, "tail", "latest_failure_report", "Read Latest Failure", "Review the newest failure report when a queue row is blocked or recently failed.");
      }
      if (item.runtime_checks_deferred) {
        queueAddDiagnosticsAction(actions, "open", "active_jobs", "Open Active Jobs", "Compare active process state before interpreting deferred source/output checks.");
      }
      return actions;
    }

    function queueAddDiagnosticsAction(actions, kind, target, label, reason) {
      if (!target || actions.some((item) => item.kind === kind && item.target === target)) return;
      actions.push({ kind, target, label, reason });
    }

    function queueDiagnosticsGuidanceLines(item) {
      const lines = [
        "Diagnostics actions below use backend allowlists. The Queue page never sends arbitrary filesystem paths.",
      ];
      if (!item) {
        lines.push("Select a row to tailor diagnostics actions to blockers, deferred runtime checks, or recent runtime failures.");
      } else {
        lines.push(`Selected route: ${item.route_name || item.route_decision_summary || "not reported"}`);
        lines.push(`Selected status: ${item.operator_status || item.status || "not reported"}`);
        lines.push(`Runtime outcome: ${item.runtime_outcome_status || "none"}${item.runtime_outcome_freshness_status ? ` (${item.runtime_outcome_freshness_status})` : ""}`);
        if (item.blocked_reason || item.blocked_reason_code || item.error) {
          lines.push("Suggested order: open Queue Snapshot, read Last Stderr, then open Run Logs before launching or reprocessing.");
        } else if (item.runtime_outcome_error_code || item.runtime_outcome_reason) {
          lines.push("Suggested order: read Last Stderr and Latest Failure first, then compare Queue Snapshot route evidence.");
        } else if (item.runtime_checks_deferred) {
          lines.push("Suggested order: open Queue Snapshot, then Active Jobs if the row appears stuck or stale.");
        } else {
          lines.push("Suggested order: Queue Snapshot first for route evidence; Run Logs only if the row conflicts with disk state.");
        }
      }
      lines.push("Mutation guardrail: diagnostics cross-links open or read backend-selected artifacts only; they do not launch, reorder, drop, or rewrite queue entries.");
      lines.push("Diagnostics bridge: Review in Diagnostics switches to the Diagnostics page and selects an allowlisted target without opening or reading it.");
      return lines;
    }

    function queueDiagnosticsActionStatusText(actions) {
      const openCount = actions.filter((item) => item.kind === "open").length;
      const tailCount = actions.filter((item) => item.kind === "tail").length;
      return `${actions.length} action${actions.length === 1 ? "" : "s"} (${openCount} open, ${tailCount} read)`;
    }

    function renderQueueDiagnosticsLinks(item) {
      const actions = queueDiagnosticsActionsForRow(item);
      setText("queue-diagnostics-status", queueDiagnosticsActionStatusText(actions));
      setText("queue-diagnostics-guidance", queueDiagnosticsGuidanceLines(item).join("\n"));
      const container = byId("queue-diagnostics-actions");
      if (!container) return;
      container.replaceChildren();
      if (typeof appendDiagnosticsBridgeGroupedButtons === "function") {
        appendDiagnosticsBridgeGroupedButtons(container, actions, {
          datasetPrefix: "queueDiagnostics",
          onAction: requestQueueDiagnosticsAction,
        });
      } else {
        actions.forEach((action) => {
          const button = document.createElement("button");
          button.className = "secondary-button";
          button.type = "button";
          button.textContent = action.label || `${action.kind === "tail" ? "Read" : "Open"} ${action.target}`;
          button.title = action.reason || "";
          button.dataset.queueDiagnosticsAction = action.kind;
          button.dataset.queueDiagnosticsTarget = action.target;
          button.addEventListener("click", () => requestQueueDiagnosticsAction(action));
          container.appendChild(button);
        });
      }
      if (typeof appendDiagnosticsBridgeButton === "function") {
        appendDiagnosticsBridgeButton(container, actions, item ? "Queue selected row" : "Queue page");
      }
    }

    function queueRouteReasoningLines(item) {
      if (!item) return [];
      const route = String(item.route_name || item.route || "").trim();
      if (!route) return [];
      const lines = ["Route Reasoning:"];
      lines.push(`  Route: ${item.route_decision_summary || route}`);
      // route_plan — structured object from the backend (e.g. {reason, contributing_factors, expected_size_note})
      const plan = item.route_plan && typeof item.route_plan === "object" ? item.route_plan : null;
      if (plan) {
        if (plan.reason) lines.push(`  Reason: ${plan.reason}`);
        const factors = Array.isArray(plan.contributing_factors)
          ? plan.contributing_factors.filter(Boolean)
          : typeof plan.contributing_factors === "string" && plan.contributing_factors
          ? [plan.contributing_factors]
          : [];
        if (factors.length) lines.push(`  Contributing factors: ${factors.join(", ")}`);
        if (plan.expected_size_note) lines.push(`  Expected output size: ${plan.expected_size_note}`);
        if (plan.policy_note) lines.push(`  Policy: ${plan.policy_note}`);
      } else {
        // Flat field fallback
        if (item.route_reason_code) lines.push(`  Reason code: ${item.route_reason_code}`);
        if (item.route_reason) lines.push(`  Reason: ${item.route_reason}`);
      }
      // route_evidence_lines — array of evidence lines
      const evidence = Array.isArray(item.route_evidence_lines) ? item.route_evidence_lines.filter(Boolean) : [];
      evidence.slice(0, 4).forEach((line) => lines.push(`  ${line}`));
      return lines;
    }

    function queueSubtitleQaLines(item) {
      const qa = item && typeof item.subtitle_qa === "object" ? item.subtitle_qa : null;
      if (!qa) return [];
      const inventory = qa.inventory && typeof qa.inventory === "object" ? qa.inventory : {};
      const srt = qa.srt_validity && typeof qa.srt_validity === "object" ? qa.srt_validity : {};
      const conversion = qa.conversion_evidence && typeof qa.conversion_evidence === "object" ? qa.conversion_evidence : {};
      const sync = qa.sync_review && typeof qa.sync_review === "object" ? qa.sync_review : {};
      const reasons = Array.isArray(qa.reasons) ? qa.reasons.filter(Boolean) : [];
      const languages = Array.isArray(inventory.subtitle_languages) ? inventory.subtitle_languages.filter(Boolean).join(", ") : "";
      const lines = [
        "Subtitle QA evidence:",
        `  Posture: ${qa.posture || "unknown"}`,
        `  Summary: ${qa.summary || "not reported"}`,
        `  Inventory: ${inventory.status || "unknown"}; tracks=${inventory.embedded_subtitle_count ?? "unknown"}; languages=${languages || "not reported"}; forced=${inventory.has_forced_subtitles ? "yes" : "no"}`,
        `  SRT validity: ${srt.status || "not_checked"} (${srt.reason || "no detail"})`,
        `  Conversion/OCR: ${conversion.status || "not_checked"} (${conversion.reason || "no detail"})`,
        `  Sync risk: ${sync.risk || "unknown"} (${sync.reason || "heuristic only"})`,
        `  Safe next action: ${qa.safe_next_action || "inspect Completed and Diagnostics evidence before trust decisions"}`,
      ];
      reasons.slice(0, 4).forEach((reason) => lines.push(`  Reason: ${reason}`));
      if (qa.guardrail) lines.push(`  ${qa.guardrail}`);
      return lines;
    }

    function renderQueueDetail(item) {
      renderQueueSelectedAtAGlance(item || null);
      const detailDrawer = window.mediaPipelineDom?.selectedRowDetailDrawerLines;
      if (!item) {
        const bodyLines = queueRowReviewChecklistLines(null);
        const detailLines = typeof detailDrawer === "function"
          ? detailDrawer({
            title: "Queue selected-row detail",
            summaryLines: queueSelectedAtAGlanceLines(null),
            bodyLines,
            guardrail: "Mutation guardrail: selected-row detail is read-only and cannot launch, reorder, drop, rewrite queue entries, or touch source files.",
          })
          : bodyLines;
        setText("queue-detail", detailLines.join("\n"));
        renderQueueDiagnosticsLinks(null);
        return;
      }
      const priorityReasons = Array.isArray(item.priority_reasons) ? item.priority_reasons.join(" | ") : "";
      const reviewFlags = Array.isArray(item.review_flags) ? item.review_flags.join(", ") : "";
      const routeEvidence = Array.isArray(item.route_evidence_lines) ? item.route_evidence_lines : [];
      const proofSummary = Array.isArray(item.proof_summary) ? item.proof_summary : [];
      const diagnosticTargets = Array.isArray(item.recommended_diagnostics_targets) ? item.recommended_diagnostics_targets.join(", ") : "";
      const runtimeCodes = Array.isArray(item.runtime_check_codes) ? item.runtime_check_codes.join(", ") : "";
      const runtimeNotes = Array.isArray(item.runtime_check_notes) ? item.runtime_check_notes : [];
      const runtimeOutcome = item.runtime_outcome_status || "";
      const handoffLines = typeof diagnosticsBridgeHandoffLines === "function"
        ? diagnosticsBridgeHandoffLines("Queue selected row", queueDiagnosticsActionsForRow(item), {
          evidence: [
            item.route_decision_summary || item.route_name ? `route=${item.route_decision_summary || item.route_name}` : "",
            item.blocked_reason_code || item.blocked_reason ? `blocker=${[item.blocked_reason_code, item.blocked_reason].filter(Boolean).join(" - ")}` : "",
            item.runtime_outcome_status || item.runtime_outcome_reason ? `runtime=${[item.runtime_outcome_status, item.runtime_outcome_error_code, item.runtime_outcome_reason].filter(Boolean).join(" - ")}` : "",
            item.source_path ? `source=${item.source_path}` : "",
          ],
          safeAction: "compare Queue Snapshot, Last Stderr, Run Logs, and Active Jobs before launch or rerun decisions.",
        })
        : [];
      const routeReasoningSection = queueRouteReasoningLines(item);
      const subtitleQaSection = queueSubtitleQaLines(item);
      const detail = [
        ...queueSelectedQuickSignalLines(item),
        "",
        ...(routeReasoningSection.length ? [...routeReasoningSection, ""] : []),
        ...(subtitleQaSection.length ? [...subtitleQaSection, ""] : []),
        ...queueRowReviewChecklistLines(item),
        "",
        ...queueRowIssueDigestLines(item),
        "",
        ...queueRowCombinedReviewPlanLines(item),
        "",
        ...queueInvestigationSignalLines(item),
        "",
        ...queueRealMediaTraceLines(item),
        "",
        ...queueRowTrustSummaryLines(item),
        "",
        ...handoffLines,
        "",
        ...queueSelectedOpenTargetLines(item),
        "",
        `Name: ${item.display_name || item.relative_path || item.source_path || ""}`,
        item.operator_trust_state ? `Backend trust state: ${item.operator_trust_state}` : "",
        item.primary_concern ? `Primary concern: ${item.primary_concern}` : "",
        item.safe_next_action ? `Safe next action: ${item.safe_next_action}` : "",
        item.unsafe_if_ignored ? `Unsafe if ignored: ${item.unsafe_if_ignored}` : "",
        proofSummary.length ? "Backend proof summary:" : "",
        ...proofSummary.map((line) => `  ${line}`),
        diagnosticTargets ? `Recommended diagnostics targets: ${diagnosticTargets}` : "",
        item.operator_status ? `Operator status: ${item.operator_status}` : "",
        item.operator_guidance ? `Next step: ${item.operator_guidance}` : "",
        reviewFlags ? `Review flags: ${reviewFlags}` : "",
        item.route_decision_summary ? `Route decision: ${item.route_decision_summary}` : "",
        routeEvidence.length ? "Route evidence:" : "",
        ...routeEvidence.map((line) => `  ${line}`),
        item.has_file_override ? `File override: ${item.file_override_scope || "unknown"} (${item.file_override_path || "path unavailable"})` : "",
        item.file_override_origin ? `File override origin: ${item.file_override_origin}` : "",
        item.file_override_batch_id ? `Series batch ID: ${item.file_override_batch_id}` : "",
        item.file_override_batch_label ? `Series batch label: ${item.file_override_batch_label}` : "",
        item.file_override_batch_scope ? `Series batch scope: ${item.file_override_batch_scope}` : "",
        item.status ? `Status: ${item.status}` : "",
        item.error ? `Error: ${item.error}` : "",
        `Media: ${item.media_type || ""}`,
        `Route: ${item.route_name || ""}`,
        `Route reason code: ${item.route_reason_code || ""}`,
        `Route reason: ${item.route_reason || ""}`,
        item.blocked_reason_code ? `Blocked reason code: ${item.blocked_reason_code}` : "",
        item.blocked_reason ? `Blocked reason: ${item.blocked_reason}` : "",
        item.runtime_checks_deferred ? `Runtime checks deferred: ${runtimeCodes || "yes"}` : "",
        ...runtimeNotes.slice(0, 4).map((note) => `Runtime note: ${note}`),
        runtimeOutcome ? `Last runtime outcome: ${runtimeOutcome}` : "",
        item.runtime_outcome_event_type ? `Runtime event type: ${item.runtime_outcome_event_type}` : "",
        item.runtime_outcome_at ? `Runtime event at: ${item.runtime_outcome_at}` : "",
        item.runtime_outcome_age_text || item.runtime_outcome_freshness_status ? `Runtime history age: ${item.runtime_outcome_age_text || "unknown"} (${item.runtime_outcome_freshness_status || "unknown"})` : "",
        item.runtime_outcome_stage || item.runtime_outcome_route ? `Runtime stage/route: ${item.runtime_outcome_stage || "unknown"} / ${item.runtime_outcome_route || "unknown"}` : "",
        item.runtime_outcome_error_code ? `Runtime error code: ${item.runtime_outcome_error_code}` : "",
        item.runtime_outcome_reason ? `Runtime reason: ${item.runtime_outcome_reason}` : "",
        item.runtime_outcome_publish_state || item.runtime_outcome_publish_mode ? `Runtime publish: ${item.runtime_outcome_publish_state || "unknown"} / ${item.runtime_outcome_publish_mode || "unknown"}` : "",
        item.runtime_outcome_output_path ? `Runtime output: ${item.runtime_outcome_output_path}` : "",
        item.runtime_outcome_match ? `Runtime match: ${item.runtime_outcome_match}` : "",
        `Queue position: ${item.queue_position || `${item.queue_index || ""}/${item.queue_total || ""}`}`,
        `Global order: ${item.global_order || ""}`,
        `Phase: ${item.phase || ""}`,
        `Priority: ${item.is_priority ? "yes" : "no"}`,
        `Priority rank: ${item.priority_rank || ""}`,
        priorityReasons ? `Priority reasons: ${priorityReasons}` : "",
        `Size GB: ${item.size_gb || ""}`,
        `Last write UTC: ${item.last_write_utc || ""}`,
        `Source: ${item.source_path || ""}`,
        `Source root: ${item.source_root || ""}`,
        `Relative: ${item.relative_path || ""}`,
        `Show folder: ${item.show_folder || ""}`,
        `Season folder: ${item.season_folder || ""}`,
        `Season: ${item.season_number || ""}`,
        `Episode: ${item.episode_number || ""}`,
      ].filter(Boolean);
      const detailLines = typeof detailDrawer === "function"
        ? detailDrawer({
          title: "Queue selected-row detail",
          summaryLines: queueSelectedAtAGlanceLines(item),
          bodyLines: detail,
          guardrail: "Mutation guardrail: selected-row detail is read-only and cannot launch, reorder, drop, rewrite queue entries, or touch source files.",
        })
        : detail;
      setText("queue-detail", detailLines.join("\n"));
      renderQueueDiagnosticsLinks(item);
    }

    function renderQueueExcludedDetail(item) {
      if (!item) {
        setText("queue-excluded-detail", "No excluded source row selected. Select an excluded row to inspect why it is hidden from the runnable queue.");
        return;
      }
      const priorityReasons = Array.isArray(item.priority_reasons) ? item.priority_reasons.join(" | ") : "";
      const detail = [
        `Name: ${item.display_name || item.relative_path || item.source_path || ""}`,
        `Reason code: ${item.reason_code || "excluded"}`,
        item.reason ? `Reason: ${item.reason}` : "",
        `Media: ${item.media_type || item.media_kind || ""}`,
        `Phase: ${item.phase || ""}`,
        `Source order: ${item.source_order || ""}`,
        `Queue position before filter: ${item.queue_index || ""}/${item.queue_total || ""}`,
        `Priority: ${item.is_priority ? "yes" : "no"}`,
        priorityReasons ? `Priority reasons: ${priorityReasons}` : "",
        `Size GB: ${item.size_gb || ""}`,
        `Last write UTC: ${item.last_write_utc || ""}`,
        `Source: ${item.source_path || ""}`,
        `Source root: ${item.source_root || ""}`,
        `Relative: ${item.relative_path || ""}`,
        `Show folder: ${item.show_folder || ""}`,
        `Season folder: ${item.season_folder || ""}`,
        `Season: ${item.season_number || ""}`,
        `Episode: ${item.episode_number || ""}`,
        "Mutation guardrail: excluded-row opens use backend-selected snapshot paths; completed reconciliation and rerun remain backend-owned.",
      ].filter(Boolean);
      setText("queue-excluded-detail", detail.join("\n"));
    }

    function isQueueOpenCommand(entry) {
      return String(entry?.command || "").toLowerCase() === "queue.open";
    }

    function queueOpenHistoryLine(entry) {
      const raw = entry?.raw && typeof entry.raw === "object" ? entry.raw : {};
      const data = raw.data && typeof raw.data === "object" ? raw.data : {};
      const request = raw.request && typeof raw.request === "object" ? raw.request : {};
      const bits = [];
      if (data.target || request.target) bits.push(`target=${data.target || request.target}`);
      if (data.row_scope || request.row_scope) bits.push(`scope=${data.row_scope || request.row_scope}`);
      if (data.row_key || request.row_key) bits.push(`row=${data.row_key || request.row_key}`);
      if (data.path || data.opened_path) bits.push(`path=${data.path || data.opened_path}`);
      if (typeof commandHistoryCompactEvidenceLine === "function") {
        return commandHistoryCompactEvidenceLine(entry, {
          label: "queue.open",
          detail: bits.length ? ` (${bits.join("; ")})` : "",
        });
      }
      const status = entry?.result || (entry?.ok ? "ok" : entry?.severity || "unknown");
      const local = entry?.local ? "local" : "journal";
      return `${entry?.at || ""} queue.open [${status}; ${local}] ${entry?.message || ""}${bits.length ? ` (${bits.join("; ")})` : ""}`.trim();
    }

    function renderQueueOpenHistory(history = []) {
      const entries = Array.isArray(history) ? history.filter(isQueueOpenCommand).slice(0, 5) : [];
      if (!Array.isArray(history) || !history.length) {
        setText("queue-open-history", "No queue open command history loaded. Open a selected queue source location to see backend results here after refresh.");
        return;
      }
      if (!entries.length) {
        setText("queue-open-history", "No queue open commands found in recent command history.");
        return;
      }
      setText("queue-open-history", [
        `Last ${entries.length} queue open command${entries.length === 1 ? "" : "s"}:`,
        ...entries.map(queueOpenHistoryLine),
        "Backend queue snapshot row keys and target allowlists remain the source of truth.",
      ].join("\n"));
    }

    return {
      queueRowReviewChecklistLines,
      queueRowIssueDigestLines,
      queueRowCombinedReviewPlanLines,
      queueRealMediaTraceLines,
      queueRowTrustSummaryLines,
      queueDiagnosticsActionsForRow,
      queueAddDiagnosticsAction,
      queueDiagnosticsGuidanceLines,
      queueDiagnosticsActionStatusText,
      renderQueueDiagnosticsLinks,
      queueRouteReasoningLines,
      renderQueueDetail,
      renderQueueExcludedDetail,
      isQueueOpenCommand,
      queueOpenHistoryLine,
      renderQueueOpenHistory,
    };
  }

  window.__queueDetailModule = { createQueueDetailModule };
})();
