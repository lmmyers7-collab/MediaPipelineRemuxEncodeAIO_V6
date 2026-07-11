// launch/scope/compactGate.js
// Read-only compact launch gate projection, quick-link navigation, and rendering.
(function () {
  function createLaunchCompactGateModule(deps = {}) {
    const {
      activateLaunchTab = null,
      appendCells = function () {},
      byId = function () { return null; },
      clearRows = function () {},
      collectPipelineStartRequest = function () { return {}; },
      getCommandHistory = function () { return []; },
      getLastLaunchBackendPreflightRefreshInfo = function () { return {}; },
      getLastQueuePayload = function () { return null; },
      getLastQueueRows = function () { return []; },
      isLaunchCommand = function () { return false; },
      launchBackendPreflightOverallStatus = function () { return "Unknown"; },
      launchBackendPreflightPayloadForTarget = function () { return null; },
      launchBackendPreflightRows = function () { return []; },
      launchBackendPreflightSummaryLines = function () { return []; },
      launchCommandReviewRows = null,
      launchCommandReviewSummaryLines = null,
      launchPolicyBoundaryRows = function () { return []; },
      launchPolicyBoundarySummaryLines = function () { return []; },
      launchReadinessLines = null,
      launchSettingsIntentPayload = function (payload) { return payload && typeof payload === "object" ? payload : {}; },
      launchSettingsIntentRows = function () { return []; },
      launchSettingsIntentSummaryLines = function () { return []; },
      launchSettingsWorkspace = function () { return {}; },
      launchTimingStatus = null,
      launchTimingTrustLines = null,
      queueLaunchDecisionPostureStatus = null,
      queueLaunchDecisionRows = null,
      queueLaunchDecisionStatus = null,
      queueLaunchDecisionSummaryLines = null,
      setText = function () {},
      showPage = null,
      state = {},
      updateTableStatusLegend = function () {},
    } = deps;
    const {
      launchStartDecisionAdvisoryPosture = function (posture) { return posture || "unknown"; },
      launchStartDecisionPostureFromStatus = function (status) { return status || "unknown"; },
      launchStartDecisionWorstPosture = function (postures) { return Array.isArray(postures) && postures[0] ? postures[0] : "unknown"; },
    } = deps.scopeApi || {};
  function launchCompactGateState(posture) {
    const normalized = String(posture || "").trim().toLowerCase();
    if (normalized === "blocked" || normalized === "failed" || normalized === "error" || normalized === "will fail" || normalized === "forced") return "blocked";
    if (normalized === "running" || normalized === "active" || normalized === "active work") return "running";
    if (normalized === "ready" || normalized === "ok" || normalized === "match" || normalized === "normal" || normalized === "all clear") return "ready";
    if (
      normalized === "unknown"
      || normalized === "neutral"
      || normalized === "not loaded"
      || normalized === "needs evidence"
      || normalized === "evidence incomplete"
      || normalized === "no history"
      || normalized === "no command history"
      || normalized === "loading"
      || normalized === "stale"
      || normalized === "stale evidence"
    ) return "unknown";
    return "warning";
  }

  function launchCompactGateValue(status) {
    const normalized = String(status || "").toLowerCase();
    if (normalized === "ready") return "OK";
    if (normalized === "blocked") return "Will Fail";
    if (normalized === "running") return "Active";
    if (normalized === "unknown") return "Needs Evidence";
    return "At Risk";
  }

  function launchCompactGateDefaultNote(status) {
    const normalized = String(status || "").toLowerCase();
    if (normalized === "ready") return "Clear";
    if (normalized === "blocked") return "Blocked";
    if (normalized === "running") return "Active";
    if (normalized === "unknown") return "Not loaded";
    return "At Risk";
  }

  function launchCompactGateRow(key, label, status, note, summary, detail = [], target = {}) {
    const stateValue = launchCompactGateState(status);
    const safeTarget = target && typeof target === "object" ? target : {};
    return {
      key,
      label,
      status: stateValue,
      value: launchCompactGateValue(stateValue),
      note: note || launchCompactGateDefaultNote(stateValue),
      summary,
      detail: Array.isArray(detail) ? detail.filter(Boolean) : [],
      target: safeTarget,
      required: safeTarget.required !== false,
    };
  }

  function launchCompactGateRequiredRows(rows = []) {
    return (Array.isArray(rows) ? rows : []).filter((row) => row?.required !== false);
  }

  function launchCompactGateHeaderState(status) {
    return launchCompactGateState(status);
  }

  function launchCompactGateActionLabel(row) {
    const target = row?.target || {};
    return target.label || "Select this gate to open and highlight its owner evidence.";
  }

  function launchCompactGateActivateTargetTab(pageId, tabId) {
    if (!tabId) return;
    if (pageId === "launch" && typeof activateLaunchTab === "function") {
      activateLaunchTab(tabId, { persist: false });
      return;
    }
    const page = Array.from(document.querySelectorAll("[data-page-panel]"))
      .find((node) => node.dataset?.pagePanel === pageId);
    if (!page) return;
    const tabDatasetKey = pageId === "diagnostics" ? "diagTab" : "";
    if (!tabDatasetKey) return;
    if (pageId === "diagnostics") {
      const buttons = Array.from(page.querySelectorAll(".settings-tab-btn[data-diag-tab]"));
      const panels = Array.from(page.querySelectorAll(".settings-tab-pane[data-diag-tab]"));
      if (!buttons.length || !panels.length) return;
      const selected = buttons.some((button) => button.dataset.diagTab === tabId) ? tabId : "triage";
      buttons.forEach((button) => {
        const active = button.dataset.diagTab === selected;
        button.setAttribute("aria-selected", String(active));
      });
      panels.forEach((panel) => {
        panel.classList.toggle("is-active", panel.dataset.diagTab === selected);
      });
      try { localStorage.setItem("mediapipeline-diag-tab", selected); } catch (_) {}
      if (typeof window.mediaPipelineAppLifecycle?.syncTabAccessibility === "function") window.mediaPipelineAppLifecycle.syncTabAccessibility();
      if (typeof updatePagePanelEmptyStates === "function") updatePagePanelEmptyStates();
      return;
    }
    const button = Array.from(page.querySelectorAll(".settings-tab-btn"))
      .find((node) => node.dataset?.[tabDatasetKey] === tabId);
    if (button && typeof button.click === "function") button.click();
  }

  function launchCompactGateQueryTarget(target = {}) {
    const selectors = [
      target.rowSelector,
      target.selector,
      target.fallbackSelector,
      target.focusSelector,
    ].filter(Boolean);
    for (const selector of selectors) {
      const node = document.querySelector(selector);
      if (node) return node;
    }
    if (target.focusId) return byId(target.focusId);
    return null;
  }

  function launchCompactGateRevealTarget(node) {
    if (!node) return;
    const advancedGate = node.closest("[data-advanced]") || node.closest("[data-panel-advanced]");
    if (advancedGate && !document.body.classList.contains("advanced-mode")) {
      advancedGate.classList.add("is-attention-reveal");
    }
    const evidenceGate = node.closest("[data-panel-type='evidence']");
    if (evidenceGate && document.body.classList.contains("evidence-hidden")) {
      evidenceGate.classList.add("is-attention-reveal");
    }
    const launchEvidenceBody = node.closest("#launch-evidence-body");
    if (launchEvidenceBody?.classList?.contains("is-collapsed")) {
      launchEvidenceBody.classList.add("is-attention-reveal");
    }
  }

  function launchCompactGateHighlightTarget(node) {
    if (!node || typeof node.classList === "undefined") return;
    launchCompactGateRevealTarget(node);
    document.querySelectorAll(".is-attention-target").forEach((item) => item.classList.remove("is-attention-target"));
    node.classList.add("is-attention-target");
    if (typeof node.scrollIntoView === "function") {
      try {
        node.scrollIntoView({ block: "center", inline: "nearest", behavior: "smooth" });
      } catch (_) {
        node.scrollIntoView(false);
      }
    }
    const hadTabIndex = node.hasAttribute("tabindex");
    if (!hadTabIndex) node.setAttribute("tabindex", "-1");
    if (typeof node.focus === "function") {
      try {
        node.focus({ preventScroll: true });
      } catch (_) {
        node.focus();
      }
    }
    window.setTimeout(() => {
      node.classList.remove("is-attention-target");
      document.querySelectorAll(".is-attention-reveal").forEach((item) => item.classList.remove("is-attention-reveal"));
      if (!hadTabIndex && node.getAttribute("tabindex") === "-1") node.removeAttribute("tabindex");
    }, 2400);
  }

  function launchCompactGateOpenTarget(row) {
    const target = row?.target || {};
    const showPageFn = typeof showPage === "function" ? showPage : window.showPage;
    if (target.page && typeof showPageFn === "function") showPageFn(target.page);
    launchCompactGateActivateTargetTab(target.page || "", target.tab || "");
    let node = launchCompactGateQueryTarget(target);
    launchCompactGateRevealTarget(node);
    if (node?.matches?.("tr[data-selectable-row='true']")) {
      node.click();
      node = launchCompactGateQueryTarget(target) || node;
      launchCompactGateRevealTarget(node);
    }
    if (node) {
      launchCompactGateHighlightTarget(node);
      setText("pipeline-compact-gate-detail", `${row.label}: ${row.value}. ${row.summary} ${launchCompactGateActionLabel(row)} Backend start remains authoritative.`);
    } else {
      setText("pipeline-compact-gate-detail", `${row?.label || "Gate"}: ${row?.value || "Needs Evidence"}. Target evidence is not rendered yet. Refresh and retry this gate. Backend start remains authoritative.`);
    }
  }

  function launchCompactGateNonReadyCount(rows = []) {
    return (Array.isArray(rows) ? rows : []).filter((row) => {
      const posture = String(row?.posture || row?.status || row?.launchState || "").toLowerCase();
      return posture && !["ready", "ok", "match", "same as saved", "launch-active"].includes(posture);
    }).length;
  }

  function launchCompactGateSettingsRows(rows = []) {
    const owned = new Set(["saved-settings", "staged-settings", "risk-handoff"]);
    return (Array.isArray(rows) ? rows : []).filter((row) => owned.has(row?.key));
  }

  function launchCompactGateSettingsPosture(settingsRows = [], policyRows = []) {
    const settingsPostures = (Array.isArray(settingsRows) ? settingsRows : []).map((row) => {
      const posture = row?.key === "staged-settings"
        ? launchStartDecisionAdvisoryPosture(row?.posture)
        : row?.posture;
      return String(posture || "unknown");
    });
    const policyPostures = (Array.isArray(policyRows) ? policyRows : []).map((row) => {
      const launchState = String(row?.launchState || "");
      const posture = launchStartDecisionPostureFromStatus(launchState);
      return launchState.toLowerCase().includes("blocked") ? launchStartDecisionAdvisoryPosture(posture) : posture;
    });
    return launchStartDecisionWorstPosture([...settingsPostures, ...policyPostures]);
  }

  function launchCompactGateBackendActiveWorkBlock(row) {
    const tokens = [
      row?.checkKey,
      row?.key,
      row?.check,
    ].map((item) => String(item || "").trim().toLowerCase()).filter(Boolean);
    return tokens.some((token) => (
      token === "active_work"
      || token.endsWith(":active_work")
      || token === "process_launch_lock"
      || token.endsWith(":process_launch_lock")
      || token.includes("active work")
      || token.includes("launch lock")
    ));
  }

  function launchCompactGateBackendActiveWorkOnly(rows = []) {
    const blockedRows = (Array.isArray(rows) ? rows : []).filter((row) => launchCompactGateState(row?.posture) === "blocked");
    return blockedRows.length > 0 && blockedRows.every(launchCompactGateBackendActiveWorkBlock);
  }

  function launchCompactGateQueueBlockedOnlyByActiveWork(queueRows = [], backendRows = []) {
    const blockedRows = (Array.isArray(queueRows) ? queueRows : []).filter((row) => {
      const posture = typeof queueLaunchDecisionPostureStatus === "function"
        ? queueLaunchDecisionPostureStatus(row?.posture)
        : String(row?.posture || "").toLowerCase();
      return launchCompactGateState(posture) === "blocked";
    });
    if (!blockedRows.length || !launchCompactGateBackendActiveWorkOnly(backendRows)) return false;
    return blockedRows.every((row) => String(row?.key || "").toLowerCase() === "backend-launch-preflight");
  }

  function launchCompactGateRows(request = collectPipelineStartRequest(), payload = launchSettingsIntentPayload()) {
    const context = launchSettingsIntentPayload(payload);
    const history = typeof getCommandHistory === "function" ? getCommandHistory() : [];
    const queueRows = typeof getLastQueueRows === "function" ? getLastQueueRows() : [];
    const queuePayload = typeof getLastQueuePayload === "function" ? getLastQueuePayload() : null;
    const pipelineBackendPreflight = launchBackendPreflightPayloadForTarget("pipeline");
    const pipelineBackendPayloads = pipelineBackendPreflight ? [pipelineBackendPreflight] : [];
    const backendRows = launchBackendPreflightRows(pipelineBackendPayloads);
    const backendFetchFailures = getLastLaunchBackendPreflightRefreshInfo().fetch_failure_count || 0;

    const rows = [];
    if (!pipelineBackendPreflight) {
      rows.push(launchCompactGateRow(
        "backend",
        "Backend",
        "unknown",
        "Refresh",
        "No cached Backend Preflight; routine Start can still submit and backend guards will re-check.",
        ["No cached Pipeline backend preflight is loaded for the current form state."],
        {
          page: "diagnostics",
          tab: "readiness",
          selector: "#launch-backend-preflight-refresh-button",
          fallbackSelector: "#launch-backend-preflight-summary",
          label: "Opened Diagnostics > Readiness > Backend Preflight. Refresh the backend preflight checks.",
        },
      ));
    } else {
      const backendStatus = launchBackendPreflightOverallStatus(pipelineBackendPayloads);
      const backendActiveWorkOnly = launchCompactGateBackendActiveWorkOnly(backendRows);
      const backendBlocked = !backendActiveWorkOnly && (pipelineBackendPreflight?.can_request_start === false
        || String(pipelineBackendPreflight?.status || "").toLowerCase() === "blocked"
        || backendRows.some((row) => launchCompactGateState(row?.posture) === "blocked"));
      const backendReviewRows = backendRows.filter((row) => launchCompactGateState(row?.posture) === "warning");
      const backendUnknownRows = backendRows.filter((row) => launchCompactGateState(row?.posture) === "unknown");
      const backendGateStatus = backendActiveWorkOnly && !backendReviewRows.length && !backendUnknownRows.length
        ? "running"
        : backendBlocked
        ? "blocked"
        : (backendReviewRows.length ? "warning" : launchStartDecisionPostureFromStatus(backendStatus));
      const backendGateState = launchCompactGateState(backendGateStatus);
      rows.push(launchCompactGateRow(
        "backend",
        "Backend",
        backendGateStatus,
        backendGateState === "running"
          ? "Active"
          : backendBlocked
          ? "Blocked"
          : (backendGateState === "warning" ? `At Risk ${backendReviewRows.length || 1}` : (backendGateState === "unknown" ? "Needs Evidence" : `${backendRows.length || 0} checks`)),
        backendGateState === "running"
          ? "Backend preflight is blocking duplicate starts because active work is already running; this is expected during normal processing."
          : backendBlocked
          ? "Backend preflight would reject normal Start Pipeline now; backend start remains authoritative."
          : (backendGateState === "warning"
            ? "Backend preflight has review checks that may affect launch; backend start remains authoritative."
            : (backendGateState === "unknown" || backendUnknownRows.length
              ? "Backend preflight evidence is incomplete; refresh before trusting the cached posture."
              : "Backend preflight is ready-looking; backend start still re-checks state at submission time.")),
        launchBackendPreflightSummaryLines(pipelineBackendPayloads),
        {
          page: "diagnostics",
          tab: "readiness",
          rowSelector: "#launch-backend-preflight-rows tr[data-selectable-row='true']:not([data-status='match'])",
          fallbackSelector: "#launch-backend-preflight-summary",
          label: "Opened Diagnostics > Readiness > Backend Preflight and selected the first non-ready check.",
        },
      ));
    }

    const queueStatus = typeof queueLaunchDecisionStatus === "function"
      ? queueLaunchDecisionStatus(queuePayload, queueRows, history)
      : (queueRows.length ? "Ready" : "Evidence incomplete");
    const queueDecisionRows = typeof queueLaunchDecisionRows === "function" ? queueLaunchDecisionRows(queuePayload, queueRows, history) : [];
    const queueNonReady = queueDecisionRows.filter((row) => {
      const posture = typeof queueLaunchDecisionPostureStatus === "function"
        ? queueLaunchDecisionPostureStatus(row.posture)
        : String(row.posture || "").toLowerCase();
      return !["ready", "normal", "match"].includes(posture);
    });
    const queueNonReadyStates = queueNonReady.map((row) => {
      const posture = typeof queueLaunchDecisionPostureStatus === "function"
        ? queueLaunchDecisionPostureStatus(row.posture)
        : row.posture;
      return launchCompactGateState(posture);
    });
    const queueBlocked = queueNonReadyStates.includes("blocked");
    const queueAtRisk = queueNonReadyStates.includes("warning");
    const queueNeedsEvidence = !queueRows.length || queueNonReadyStates.includes("unknown");
    const queueActiveWorkOnly = queueBlocked
      && !queueAtRisk
      && !queueNeedsEvidence
      && launchCompactGateQueueBlockedOnlyByActiveWork(queueNonReady, backendRows);
    const queueGateStatus = !queueRows.length
      ? "unknown"
      : (queueActiveWorkOnly ? "running" : (queueBlocked ? "blocked" : (queueAtRisk ? "warning" : (queueNeedsEvidence ? "unknown" : launchStartDecisionPostureFromStatus(queueStatus)))));
    const queueGateState = launchCompactGateState(queueGateStatus);
    const queueIssueCount = queueNonReady.length || 1;
    rows.push(launchCompactGateRow(
      "queue",
      "Queue",
      queueGateStatus,
      queueRows.length
        ? (queueGateState === "running" ? "Active" : (queueGateState === "blocked" ? "Blocked" : (queueGateState === "warning" ? `At Risk ${queueIssueCount}` : (queueGateState === "unknown" ? "Needs Evidence" : `Queue ${queueRows.length}`))))
        : "Not loaded",
      queueRows.length
        ? (queueGateState === "running"
          ? "Queue launch handoff is paused by active backend work; no queue-specific compact blocker is indicated."
          : (queueGateState === "blocked"
          ? `Queue has ${queueIssueCount} launch handoff item(s) that would block this launch scope.`
          : (queueGateState === "warning"
            ? `Queue has ${queueIssueCount} launch handoff item(s) likely to affect this start.`
            : (queueGateState === "unknown"
              ? "Queue handoff evidence is incomplete; refresh before trusting visible launch scope."
              : "Queue handoff is ready-looking; backend owns actual launch scope."))))
        : "Queue evidence is not loaded in this view. Use Refresh to update backend evidence before trusting visible launch scope.",
      typeof queueLaunchDecisionSummaryLines === "function" ? queueLaunchDecisionSummaryLines(queuePayload, queueRows, history) : [],
      {
        page: "queue",
        rowSelector: "#queue-launch-decision-rows tr[data-selectable-row='true']:not([data-status='match'])",
        fallbackSelector: "#queue-launch-decision-summary",
        label: "Opened Queue > Queue-to-Launch handoff and selected the first non-ready row.",
      },
    ));

    const settingsIntentRows = launchSettingsIntentRows(request, context);
    const compactSettingsRows = launchCompactGateSettingsRows(settingsIntentRows);
    const policyRows = launchPolicyBoundaryRows();
    const settingsPosture = launchCompactGateSettingsPosture(compactSettingsRows, policyRows);
    const settingsNonReady = launchCompactGateNonReadyCount(compactSettingsRows) + launchCompactGateNonReadyCount(policyRows);
    const settingsLoaded = Boolean(launchSettingsWorkspace()?.schema_version);
    const settingsGateState = settingsLoaded ? launchCompactGateState(settingsPosture) : "unknown";
    rows.push(launchCompactGateRow(
      "settings",
      "Settings",
      settingsGateState,
      settingsLoaded
        ? (settingsGateState === "blocked" ? "Blocked" : (settingsGateState === "unknown" ? "Needs Evidence" : (settingsGateState === "warning" ? `At Risk ${settingsNonReady || 1}` : "Saved")))
        : "Not loaded",
      settingsLoaded
        ? (settingsGateState === "blocked"
          ? "Saved settings or policy posture would block this start path."
          : (settingsGateState === "warning"
            ? "Saved settings or policy posture has review evidence likely to affect unattended starts."
            : (settingsGateState === "unknown"
              ? "Saved settings or policy posture evidence is incomplete; refresh before trusting settings posture."
              : "Saved settings and policy posture are ready-looking; backend start remains authoritative.")))
        : "Saved settings evidence is not loaded in this view. Use Refresh before trusting settings posture.",
      [
        ...launchSettingsIntentSummaryLines(compactSettingsRows),
        ...launchPolicyBoundarySummaryLines(policyRows),
      ],
      {
        page: "diagnostics",
        tab: "readiness",
        rowSelector: "#launch-settings-risk-rows tr[data-selectable-row='true'][data-status='blocked'], #launch-settings-risk-rows tr[data-selectable-row='true'][data-status='warning'], #launch-settings-intent-rows tr[data-selectable-row='true']:not([data-status='match']), #launch-policy-boundary-rows tr[data-selectable-row='true']:not([data-status='match'])",
        fallbackSelector: "#launch-settings-risk-summary",
        label: "Opened Diagnostics > Readiness > Settings Check and selected the first non-ready settings row.",
      },
    ));

    const timingStatus = typeof launchTimingStatus === "function" ? launchTimingStatus(context, request) : "Unknown";
    const timingPosture = String(timingStatus || "").toLowerCase().includes("active work")
      ? "running"
      : launchStartDecisionPostureFromStatus(timingStatus);
    const timingState = launchCompactGateState(timingPosture);
    rows.push(launchCompactGateRow(
      "schedule",
      "Schedule",
      timingPosture,
      request?.schedule_override
        ? "Override"
        : (timingState === "running" ? "Active" : (timingState === "ready" ? "Window" : (timingState === "blocked" ? "Blocked" : (timingState === "unknown" ? "Not loaded" : "At Risk")))),
      `Schedule status is ${timingStatus}; override=${request?.schedule_override || "none"}.`,
      typeof launchTimingTrustLines === "function" ? launchTimingTrustLines(context, request) : [],
      {
        page: "diagnostics",
        tab: "readiness",
        selector: "#launch-timing",
        fallbackSelector: "#pipeline-start-schedule-override",
        label: "Opened Diagnostics > Readiness > Schedule Alignment. Use the schedule evidence, wait for the window, or choose an intentional override.",
      },
    ));

    const closeReadiness = context.closeReadiness || null;
    const snapshot = context.snapshot || null;
    const snapshotState = String(snapshot?.pipeline_state || snapshot?.state || snapshot?.status || "").toLowerCase();
    const active = Boolean(closeReadiness?.active_work || closeReadiness?.pipeline_active || closeReadiness?.safe_to_close === false)
      || ["active", "running", "processing", "paused", "stopping"].some((term) => snapshotState.includes(term));
    rows.push(launchCompactGateRow(
      "active",
      "Active",
      active ? "running" : (closeReadiness || snapshot ? "ready" : "unknown"),
      active ? "Active" : (closeReadiness || snapshot ? "Idle" : "Not loaded"),
      active
        ? "Active backend work is in progress; Start controls remain disabled to prevent duplicate pipeline starts."
        : (closeReadiness || snapshot ? "No active backend work is visible in the latest loaded state." : "Backend state evidence is not loaded in this view; backend Start still re-checks active work."),
      typeof launchReadinessLines === "function"
        ? launchReadinessLines({ snapshot, closeReadiness, schedule: context.schedule || {}, settings: launchSettingsWorkspace(), backendPreflight: pipelineBackendPreflight })
        : [],
      {
        page: "launch",
        tab: "pipeline",
        selector: active ? "#launch-live-run-strip" : "#pipeline-controller-stage-summary",
        fallbackSelector: "#launch-readiness",
        label: active ? "Opened Launch > Pipeline Processor > Live Run for the active backend work." : "Opened Launch > Pipeline Processor state evidence.",
      },
    ));

    const commandRows = typeof launchCommandReviewRows === "function" ? launchCommandReviewRows(history) : [];
    const latestLaunch = commandRows[0] || history.find((entry) => isLaunchCommand(entry)) || null;
    rows.push(launchCompactGateRow(
      "last",
      "Last",
      latestLaunch ? "ready" : "unknown",
      latestLaunch ? "No issue" : "No history",
      latestLaunch
        ? "Recent launch history is visible; current backend preflight remains authoritative for start safety."
        : "No recent launch result is loaded; the next backend response will create command evidence.",
      typeof launchCommandReviewSummaryLines === "function" ? launchCommandReviewSummaryLines(history) : [],
      {
        page: "launch",
        tab: "history",
        rowSelector: "#launch-command-review-rows tr[data-selectable-row='true']",
        fallbackSelector: latestLaunch ? "#launch-history" : "#launch-latest-command-evidence",
        label: latestLaunch ? "Opened Launch > History for recent launch evidence." : "Opened Launch command history; no prior launch command evidence is available.",
        required: false,
      },
    ));

    if (backendFetchFailures) {
      const backend = rows.find((row) => row.key === "backend");
      if (backend && backend.status === "ready") {
        backend.status = "unknown";
        backend.value = launchCompactGateValue("unknown");
      }
      if (backend) {
        backend.note = `Fetch ${backendFetchFailures}`;
        backend.summary = `Backend preflight refresh reported ${backendFetchFailures} fetch failure(s); refresh before trusting the cached posture.`;
      }
    }
    return rows;
  }

  function launchCompactGateOverallStatus(rows = launchCompactGateRows()) {
    const source = launchCompactGateRequiredRows(rows);
    if (!source.length) return "Needs Evidence";
    if (source.some((row) => row.status === "blocked")) return "Will Fail";
    if (source.some((row) => row.status === "running")) return "Active";
    if (source.some((row) => row.status === "warning")) return "At Risk";
    if (source.some((row) => row.status === "unknown")) return "Needs Evidence";
    return "All Clear";
  }

  function selectedLaunchCompactGateRow(rows = []) {
    const source = Array.isArray(rows) ? rows : [];
    return source.find((row) => row.key === state.selectedLaunchCompactGateKey)
      || source.find((row) => row.status === "blocked")
      || source.find((row) => row.status === "running")
      || source.find((row) => row.status === "warning")
      || source.find((row) => row.required !== false && row.status === "unknown")
      || source[0]
      || null;
  }

  function selectLaunchCompactGate(row) {
    state.selectedLaunchCompactGateKey = row?.key || "";
    renderLaunchCompactGate();
  }

  function renderLaunchCompactGate(request = collectPipelineStartRequest(), payload = launchSettingsIntentPayload()) {
    const rows = launchCompactGateRows(request, payload);
    if (state.selectedLaunchCompactGateKey && !rows.some((row) => row.key === state.selectedLaunchCompactGateKey)) {
      state.selectedLaunchCompactGateKey = "";
    }
    const selected = selectedLaunchCompactGateRow(rows);
    const overall = launchCompactGateOverallStatus(rows);
    setText("pipeline-compact-gate-status", overall);
    const statusNode = byId("pipeline-compact-gate-status");
    if (statusNode) statusNode.dataset.state = launchCompactGateHeaderState(overall);
    rows.forEach((item) => {
      const button = byId(`pipeline-gate-${item.key}`);
      if (!button) return;
      const selectedState = item.key === selected?.key;
      button.dataset.status = item.status;
      button.classList.toggle("is-active", selectedState);
      button.setAttribute("aria-pressed", selectedState ? "true" : "false");
      button.setAttribute("aria-label", `${item.label} gate: ${item.value}. ${item.summary}`);
      button.title = item.summary;
      const label = button.querySelector(".pipeline-gate-label");
      const value = button.querySelector(".pipeline-gate-value");
      const note = button.querySelector(".pipeline-gate-note");
      if (label) label.textContent = item.label;
      if (value) value.textContent = item.value;
      if (note) note.textContent = item.note;
      button.onclick = () => {
        selectLaunchCompactGate(item);
        launchCompactGateOpenTarget(item);
      };
    });
    const detail = selected
      ? `${selected.label}: ${selected.value}. ${selected.summary} ${launchCompactGateActionLabel(selected)} Backend start remains authoritative.`
      : "Compact gate not evaluated. Routine Start can still submit; refresh Backend Preflight for current evidence if useful.";
    setText("pipeline-compact-gate-detail", detail);
    return rows;
  }


    return {
      launchCompactGateOverallStatus,
      launchCompactGateRows,
      renderLaunchCompactGate,
    };
  }

  window.__launchCompactGateModule = { createLaunchCompactGateModule };
})();
