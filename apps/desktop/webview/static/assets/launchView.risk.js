(function () {
  function createLaunchRiskModule(deps = {}) {
    const {
      appendCells = function () {},
      byId = function () { return null; },
      clearRows = function () {},
      collectPipelineStartRequest = function () { return {}; },
      formatSettingsChoiceLabel = null,
      getCommandHistory = function () { return []; },
      getLastLaunchReadinessPayload = function () { return {}; },
      getLastQueueRows = function () { return []; },
      getLastSettings = function () { return {}; },
      isLaunchCommand = function () { return false; },
      launchHistoryLine = null,
      makeRowSelectable = null,
      pipelineModeLabel = function (mode) { return mode || "Pipeline"; },
      queueCurrentFilterScope = null,
      queueFilterScopeDetailLines = null,
      scheduleDisplayValue = null,
      setText = function () {},
      settingsCommandHistoryLine = null,
      settingsLaunchImpactRows = null,
      settingsLaunchImpactStatus = null,
      settingsOperatorTrustStatus = null,
      settingsPatchEffectiveChangedEntries = null,
      settingsPatchIsTouched = null,
      settingsPolicyDeltaRows = null,
      settingsPolicyDeltaStatus = null,
      state = {},
      updateTableStatusLegend = function () {},
    } = deps;
    if (!Object.prototype.hasOwnProperty.call(state, "selectedLaunchSettingsRiskKey")) state.selectedLaunchSettingsRiskKey = "";
    if (!Object.prototype.hasOwnProperty.call(state, "selectedLaunchPolicyBoundaryKey")) state.selectedLaunchPolicyBoundaryKey = "";
    if (!Object.prototype.hasOwnProperty.call(state, "selectedLaunchSettingsIntentKey")) state.selectedLaunchSettingsIntentKey = "";

    const launchRiskSettingsAccessModule = window.__launchRiskSettingsAccessModule || {};
    delete window.__launchRiskSettingsAccessModule;
    const launchRiskSettingsAccess = typeof launchRiskSettingsAccessModule.createLaunchRiskSettingsAccessModule === "function"
      ? launchRiskSettingsAccessModule.createLaunchRiskSettingsAccessModule({ getLastSettings })
      : {};
    const {
      launchSettingsWorkspace = function () { return {}; },
      launchSettingsConfigValue = function () { return undefined; },
    } = launchRiskSettingsAccess;

    const launchRiskMediaPolicyValuesModule = window.__launchRiskMediaPolicyValuesModule || {};
    delete window.__launchRiskMediaPolicyValuesModule;
    const launchRiskMediaPolicyValues = typeof launchRiskMediaPolicyValuesModule.createLaunchRiskMediaPolicyValuesModule === "function"
      ? launchRiskMediaPolicyValuesModule.createLaunchRiskMediaPolicyValuesModule({
        formatSettingsChoiceLabel,
        launchSettingsConfigValue,
      })
      : {};
    const {
      launchSettingsBool = function (value, fallback = false) { return fallback; },
      launchSettingsNumber = function (value, fallback = 0) { return fallback; },
      launchRouteMaxHeightFromUpperTolerance = function (baseHeight) { return Math.round(Number(baseHeight)); },
      launchRouteMinHeightFromLowerTolerance = function (baseHeight) { return Math.round(Number(baseHeight)); },
      launchRouteHeightBoundaries = function () { return {}; },
      launchSettingsList = function (value, fallback = []) { return Array.isArray(fallback) ? fallback : []; },
      launchPolicyChoiceLabel = function (value) { return String(value || "").replace(/[_-]+/g, " ").replace(/\s+/g, " ").trim() || "(not set)"; },
      launchPolicyBoolText = function (value) { return value ? "on" : "off"; },
    } = launchRiskMediaPolicyValues;

    const launchRiskRowsModule = window.__launchRiskRowsModule || {};
    delete window.__launchRiskRowsModule;
    const launchRiskRows = typeof launchRiskRowsModule.createLaunchRiskRowsModule === "function"
      ? launchRiskRowsModule.createLaunchRiskRowsModule({
        collectPipelineStartRequest,
        launchRouteHeightBoundaries,
        launchSettingsBool,
        launchSettingsConfigValue,
        launchSettingsNumber,
        launchSettingsWorkspace,
        pipelineModeLabel,
        settingsLaunchImpactRows,
        settingsLaunchImpactStatus,
        settingsOperatorTrustStatus,
        settingsPatchEffectiveChangedEntries,
        settingsPatchIsTouched,
        settingsPolicyDeltaRows,
        settingsPolicyDeltaStatus,
      })
      : {};
    const {
      launchSettingsTrustStatus = function () { return "Unknown"; },
      launchSettingsDecision = function () { return { decision: "unknown", status: "Unknown", mode: "unknown", reasons: [], guidance: "Launch settings risk module is unavailable." }; },
      launchSettingsDecisionLines = function () { return []; },
      launchUnsavedSettingsPatchLines = function () { return []; },
      launchSettingsRiskLines = function () { return []; },
      launchSettingsSeverityRank = function () { return 3; },
      launchRealMediaReadinessLines = function () { return []; },
      launchSettingsRiskRows = function () { return []; },
      launchSettingsRiskStatus = function () { return "Unknown"; },
      launchSettingsRiskSummaryLines = function () { return []; },
      launchSettingsRiskDetailLines = function () { return []; },
    } = launchRiskRows;

  function selectedLaunchSettingsRiskRow(rows = []) {
    const source = Array.isArray(rows) ? rows : [];
    return source.find((row) => row.key === state.selectedLaunchSettingsRiskKey) || source.find((row) => row.impact !== "ready") || source[0] || null;
  }


  function selectLaunchSettingsRiskRow(row) {
    state.selectedLaunchSettingsRiskKey = row?.key || "";
    renderLaunchSettingsRiskHandoff();
  }


    const launchRiskPolicyPatchModule = window.__launchRiskPolicyPatchModule || {};
    delete window.__launchRiskPolicyPatchModule;
    const launchRiskPolicyPatch = typeof launchRiskPolicyPatchModule.createLaunchRiskPolicyPatchModule === "function"
      ? launchRiskPolicyPatchModule.createLaunchRiskPolicyPatchModule({
        launchPolicyBoolText,
        launchPolicyChoiceLabel,
        launchSettingsBool,
        launchSettingsConfigValue,
        launchSettingsList,
        launchSettingsNumber,
        settingsPatchEffectiveChangedEntries,
        settingsPatchIsTouched,
      })
      : {};
    const {
      launchPolicySubtitleKeys = [],
      launchPolicyAudioKeys = [],
      launchPolicyPublishKeys = [],
      launchPolicyPatchState = function () { return { touched: false, entries: [], error: "" }; },
      launchPolicyEntryMap = function () { return new Map(); },
      launchPolicyChangedKeys = function () { return []; },
      launchPolicyCurrentValue = function (config, key, fallback) { return fallback; },
      launchPolicyCandidateValue = function (config, entryMap, key, fallback) { return fallback; },
      launchPolicyFormatSubtitle = function () { return { evidence: "" }; },
      launchPolicyFormatAudio = function () { return { evidence: "" }; },
      launchPolicyFormatPublish = function () { return { evidence: "" }; },
      launchPolicyCandidatePosture = function () { return "preview required"; },
    } = launchRiskPolicyPatch;

    const launchRiskPolicyBoundaryModule = window.__launchRiskPolicyBoundaryModule || {};
    delete window.__launchRiskPolicyBoundaryModule;
    const launchRiskPolicyBoundary = typeof launchRiskPolicyBoundaryModule.createLaunchRiskPolicyBoundaryModule === "function"
      ? launchRiskPolicyBoundaryModule.createLaunchRiskPolicyBoundaryModule({
        launchPolicyAudioKeys,
        launchPolicyCandidatePosture,
        launchPolicyChangedKeys,
        launchPolicyEntryMap,
        launchPolicyFormatAudio,
        launchPolicyFormatPublish,
        launchPolicyFormatSubtitle,
        launchPolicyPatchState,
        launchPolicyPublishKeys,
        launchPolicySubtitleKeys,
        launchSettingsWorkspace,
      })
      : {};
    const {
      launchPolicyBoundaryRows = function () { return []; },
      launchPolicyBoundaryStatus = function () { return "Unknown"; },
      launchPolicyBoundaryRowStatus = function () { return "unknown"; },
      launchPolicyBoundarySummaryLines = function () { return []; },
      launchPolicyBoundaryDetailLines = function () { return []; },
    } = launchRiskPolicyBoundary;

  function selectedLaunchPolicyBoundaryRow(rows) {
    const list = Array.isArray(rows) ? rows : [];
    return list.find((row) => row.key === state.selectedLaunchPolicyBoundaryKey)
      || list.find((row) => !["ready", "launch-active", "same as saved"].includes(row.launchState))
      || list[0]
      || null;
  }


  function selectLaunchPolicyBoundaryRow(row) {
    state.selectedLaunchPolicyBoundaryKey = row?.key || "";
    renderLaunchPolicyBoundary();
  }

  function renderLaunchPolicyBoundary(settings = launchSettingsWorkspace()) {
    const rows = launchPolicyBoundaryRows(settings);
    if (state.selectedLaunchPolicyBoundaryKey && !rows.some((row) => row.key === state.selectedLaunchPolicyBoundaryKey)) {
      state.selectedLaunchPolicyBoundaryKey = "";
    }
    const selected = selectedLaunchPolicyBoundaryRow(rows);
    setText("launch-policy-boundary-status", launchPolicyBoundaryStatus(rows));
    setText("launch-policy-boundary-summary", launchPolicyBoundarySummaryLines(rows).join("\n"));
    setText("launch-policy-boundary-detail", launchPolicyBoundaryDetailLines(selected).join("\n"));
    const tbody = byId("launch-policy-boundary-rows");
    if (!tbody) return;
    if (!rows.length) {
      clearRows(tbody, 4, "No launch media-policy boundary rows loaded.");
      updateTableStatusLegend("launch-policy-boundary-legend", tbody, "Launch media-policy boundary rows");
      return;
    }
    tbody.replaceChildren();
    rows.forEach((item) => {
      const row = document.createElement("tr");
      row.dataset.status = launchPolicyBoundaryRowStatus(item.launchState);
      appendCells(row, [item.area, item.launchState, item.evidence, item.action]);
      makeRowSelectable(row, () => selectLaunchPolicyBoundaryRow(item), {
        selected: item.key === state.selectedLaunchPolicyBoundaryKey,
        label: `Inspect launch policy boundary ${item.area || ""}`,
      });
      tbody.appendChild(row);
    });
    updateTableStatusLegend("launch-policy-boundary-legend", tbody, "Launch media-policy boundary rows");
  }

  function renderLaunchSettingsRiskHandoff(request = collectPipelineStartRequest()) {
    const rows = launchSettingsRiskRows(launchSettingsWorkspace(), request);
    if (state.selectedLaunchSettingsRiskKey && !rows.some((row) => row.key === state.selectedLaunchSettingsRiskKey)) {
      state.selectedLaunchSettingsRiskKey = "";
    }
    const selected = selectedLaunchSettingsRiskRow(rows);
    setText("launch-settings-risk-status", launchSettingsRiskStatus(rows));
    setText("launch-settings-risk-summary", launchSettingsRiskSummaryLines(rows).join("\n"));
    setText("launch-settings-risk-detail", launchSettingsRiskDetailLines(selected).join("\n"));
    setText("launch-settings-risk-legend", "Launch risk rows are selectable for read-only details and do not change backend launch validation.");
    const tbody = byId("launch-settings-risk-rows");
    if (!rows.length) {
      clearRows(tbody, 4, "No launch settings risk rows loaded.");
      setText("launch-settings-risk-detail", launchSettingsRiskDetailLines(null).join("\n"));
      return;
    }
    tbody.replaceChildren();
    rows.forEach((item) => {
      const row = document.createElement("tr");
      row.dataset.status = item.impact === "blocked" ? "blocked" : (item.impact === "high review" || item.impact === "review" ? "warning" : "match");
      appendCells(row, [item.area, item.impact, item.evidence, item.action]);
      if (typeof makeRowSelectable === "function") {
        makeRowSelectable(row, () => selectLaunchSettingsRiskRow(item), {
          selected: item.key === selected?.key,
          label: `Launch risk ${item.area || ""} ${item.impact || ""}`,
        });
      }
      tbody.appendChild(row);
    });
    updateTableStatusLegend("launch-settings-risk-legend", tbody, "Launch risk rows");
  }

  function launchSettingsIntentPayload(payload = null) {
    if (payload && typeof payload === "object") return payload;
    try {
      if (typeof getLastLaunchReadinessPayload === "function") return getLastLaunchReadinessPayload() || {};
    } catch {
      return {};
    }
    return {};
  }

  function launchSettingsIntentLatestCommand(predicate) {
    const history = typeof getCommandHistory === "function" ? getCommandHistory() : [];
    if (!Array.isArray(history)) return null;
    return history.find(predicate) || null;
  }

  function launchSettingsIntentCommandLine(entry) {
    if (!entry) return "No matching command is visible in recent command history.";
    if (typeof launchHistoryLine === "function" && isLaunchCommand(entry)) return launchHistoryLine(entry);
    if (typeof settingsCommandHistoryLine === "function" && String(entry.command || "").toLowerCase().startsWith("settings.")) {
      return settingsCommandHistoryLine(entry);
    }
    return `${entry.at || ""} ${entry.command || "unknown"} [${entry.result || (entry.ok ? "ok" : entry.severity || "unknown")}] ${entry.message || ""}`.trim();
  }

  function launchSettingsIntentStagedPatchStatus() {
    if (typeof settingsPatchIsTouched !== "function" || settingsPatchIsTouched() !== true) {
      return {
        posture: "ready",
        evidence: "Settings Changes JSON has not been touched in this WebView session.",
        action: "Launch will use saved backend settings.",
        detail: ["No staged settings patch is visible in the current WebView session."],
      };
    }
    if (typeof settingsPatchEffectiveChangedEntries !== "function") {
      return {
        posture: "review",
        evidence: "Settings patch was touched, but patch-impact helpers are unavailable.",
        action: "Use Settings Preview/Save before relying on changed settings.",
        detail: ["The Launch page cannot inspect staged settings changes, so saved backend settings remain the only launch input."],
      };
    }
    try {
      const entries = settingsPatchEffectiveChangedEntries();
      if (!entries.length) {
        return {
          posture: "ready",
          evidence: "Settings Changes JSON was touched, but no effective saved-value changes are staged.",
          action: "Launch can continue to rely on saved backend settings.",
          detail: ["Staged keys either match saved values or no effective changed keys were detected."],
        };
      }
      const rows = typeof settingsLaunchImpactRows === "function" ? settingsLaunchImpactRows(entries) : [];
      const status = typeof settingsLaunchImpactStatus === "function" ? settingsLaunchImpactStatus(rows) : "Review";
      const deltaRows = typeof settingsPolicyDeltaRows === "function" ? settingsPolicyDeltaRows(entries) : [];
      const deltaStatus = typeof settingsPolicyDeltaStatus === "function" && deltaRows.length
        ? settingsPolicyDeltaStatus(deltaRows)
        : "Not evaluated";
      const deltaReviewRows = deltaRows.filter((row) => {
        const posture = String(row.posture || "").toLowerCase();
        return posture.includes("blocked") || posture.includes("critical") || posture.includes("review") || posture.includes("staged") || posture.includes("preview");
      });
      const policyRows = typeof launchPolicyBoundaryRows === "function" ? launchPolicyBoundaryRows(launchSettingsWorkspace()) : [];
      const policyReviewRows = policyRows.filter((row) => !["ready", "launch-active", "same as saved"].includes(row.launchState));
      return {
        posture: String(status).toLowerCase().includes("blocked") ? "blocked" : String(status).toLowerCase().includes("high") ? "high review" : "review",
        evidence: `${entries.length} unsaved effective change(s): ${entries.map((entry) => entry.key).slice(0, 8).join(", ")}${entries.length > 8 ? `, +${entries.length - 8} more` : ""}.`,
        action: "Save Patch must succeed and settings must reload/refresh before Launch uses these changes.",
        detail: [
          `Settings handoff status: ${status}`,
          `Staged media-policy delta: ${deltaStatus}`,
          `Launch active policy boundary: ${typeof launchPolicyBoundaryStatus === "function" ? launchPolicyBoundaryStatus(policyRows) : "not evaluated"}`,
          policyReviewRows.length
            ? `First launch policy boundary row: ${policyReviewRows[0].area} (${policyReviewRows[0].launchState}) - ${policyReviewRows[0].action}`
            : "No launch policy boundary review rows detected locally.",
          deltaReviewRows.length
            ? `First staged delta review row: ${deltaReviewRows[0].area} (${deltaReviewRows[0].posture}) - ${deltaReviewRows[0].check}`
            : "No staged media-policy delta review rows detected locally.",
          "Unsaved Changes JSON does not change backend launch input.",
          "Use Settings > Preview Patch, then Save Patch, then refresh before treating these changes as launch-active.",
        ],
      };
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      return {
        posture: "review",
        evidence: `Settings Changes JSON is invalid: ${message}`,
        action: "Fix Settings Changes JSON before preview/save; Launch still uses saved backend settings.",
        detail: [
          `JSON error: ${message}`,
          "Invalid staged JSON cannot be previewed or saved by Settings.",
          "The backend launch route will still evaluate the saved config on disk.",
        ],
      };
    }
  }

  function launchSettingsIntentRows(request = collectPipelineStartRequest(), payload = launchSettingsIntentPayload()) {
    const context = launchSettingsIntentPayload(payload);
    const settings = launchSettingsWorkspace();
    const schedule = context.schedule || {};
    const closeReadiness = context.closeReadiness || null;
    const snapshot = context.snapshot || null;
    const launchDecision = launchSettingsDecision(settings, request);
    const riskRows = launchSettingsRiskRows(settings, request);
    const blockedRiskRows = riskRows.filter((row) => row.impact === "blocked");
    const reviewRiskRows = riskRows.filter((row) => row.impact !== "ready");
    const mode = String(request?.mode || "validate");
    const override = String(request?.schedule_override || "");
    const evaluation = schedule.evaluation || {};
    const watchedMode = mode === "once" || mode === "continuous";
    const outsideWindow = Boolean(schedule.enabled && evaluation.allowed_now === false && watchedMode && !override);
    const rows = [];
    const add = (key, checkpoint, posture, evidence, action, detail = []) => rows.push({ key, checkpoint, posture, evidence, action, detail });

    add(
      "backend-authority",
      "Backend launch authority",
      "ready",
      "Pipeline, audit, rerun, and pending-drain starts call backend-owned routes.",
      "Use these controls only as requests; backend validation, schedule gates, and launch locks remain authoritative.",
      [
        "Frontend checklist rows are read-only and cannot start, retry, drain, save settings, rewrite queue state, or touch files.",
        "Backend command routes still own acceptance, rejection, process launch, command journaling, and refresh hints.",
      ],
    );

    add(
      "saved-settings",
      launchDecision.decision === "blocked" ? "Saved settings block" : "Saved settings posture",
      launchDecision.decision === "blocked" ? "blocked" : launchDecision.decision === "review" ? "review" : "ready",
      `Saved settings status=${launchDecision.status}; mode=${pipelineModeLabel(mode)}.`,
      launchDecision.guidance,
      launchSettingsDecisionLines(settings, request),
    );

    const patchStatus = launchSettingsIntentStagedPatchStatus();
    add(
      "staged-settings",
      "Staged Settings patch",
      patchStatus.posture,
      patchStatus.evidence,
      patchStatus.action,
      patchStatus.detail,
    );

    add(
      "mode-override",
      "Selected launch intent",
      mode === "continuous" && override === "ignore" ? "high review" : mode === "continuous" ? "review" : "ready",
      `mode=${pipelineModeLabel(mode)}; sleep=${request?.sleep_seconds || 30}s; schedule override=${override || "none"}.`,
      mode === "continuous"
        ? "Continuous runs are unattended-sensitive; verify schedule, settings, and close-readiness before confirming."
        : "Confirm the selected mode matches the current operator intent before starting.",
      [
        `Show config: ${request?.show_config ? "yes" : "no"}`,
        `Show console: ${request?.show_console ? "yes" : "no"}`,
        `Single file: ${request?.single_file ? "operator-provided backend request" : "not requested"}`,
        override === "ignore" ? "Ignore Schedule bypasses schedule-window protection for this launch request." : "No full schedule bypass is selected.",
      ],
    );

    add(
      "active-work",
      "Active work / close-readiness",
      closeReadiness?.safe_to_close === false || closeReadiness?.active_work === true ? "blocked" : closeReadiness ? "ready" : "unknown",
      `snapshot=${snapshot ? (snapshot.pipeline_state || "loaded") : "missing"}; close=${closeReadiness ? (closeReadiness.safe_to_close ? "safe" : "active/blocked") : "unknown"}.`,
      closeReadiness?.safe_to_close === false || closeReadiness?.active_work === true
        ? "Do not start another media run until active work is complete or backend-owned controls intentionally stop/pause it."
        : closeReadiness
          ? "Close-readiness does not report an active-work block."
          : "Refresh before launch if close-readiness has not loaded.",
      [
        `Close reason: ${closeReadiness?.reason || "none reported"}`,
        `Activity: ${snapshot?.activity || "none reported"}`,
      ],
    );

    add(
      "schedule-gate",
      "Schedule gate",
      outsideWindow ? "blocked" : (schedule.enabled && watchedMode && override ? "review" : schedule.enabled ? "ready" : "unknown"),
      `schedule=${schedule.enabled ? "enabled" : "off/unavailable"}; allowed_now=${evaluation.allowed_now === false ? "no" : "yes/unknown"}; override=${override || "none"}.`,
      outsideWindow
        ? "Run Once and Continuous should wait for the allowed window or use an intentional override."
        : override
          ? "Override is intentional-looking; confirm it before submitting."
          : "No schedule-window block is visible for the selected intent.",
      [
        `Next allowed start: ${typeof scheduleDisplayValue === "function" ? scheduleDisplayValue(evaluation.next_allowed_start) : (evaluation.next_allowed_start || "None")}`,
        `Current/next window end: ${typeof scheduleDisplayValue === "function" ? scheduleDisplayValue(evaluation.current_window_end || evaluation.next_allowed_end) : (evaluation.current_window_end || evaluation.next_allowed_end || "None")}`,
      ],
    );

    const queueRows = typeof getLastQueueRows === "function" ? getLastQueueRows() : [];
    const queueScope = typeof queueCurrentFilterScope === "function" ? queueCurrentFilterScope(queueRows) : null;
    add(
      "queue-filter-scope",
      "Queue display scope",
      queueScope ? (queueScope.active ? "review" : "ready") : "unknown",
      queueScope
        ? `filters=${queueScope.active ? "active" : "inactive"}; visible=${queueScope.visibleRows}/${queueScope.totalRows}; hidden blocked=${queueScope.hiddenBlocked}; hidden review=${queueScope.hiddenReview}.`
        : "Queue display filter state is unavailable in this WebView session.",
      queueScope
        ? queueScope.active
          ? "Do not treat the visible Queue table as launch scope; clear filters or inspect hidden review rows before starting."
          : "No Queue display filter is active, but backend Launch still owns the actual processing scope."
        : "Refresh Queue before launch if the launch decision depends on queue display filters.",
      queueScope && typeof queueFilterScopeDetailLines === "function"
        ? queueFilterScopeDetailLines(queueScope)
        : [
          "Launch start requests do not include Queue filter text, status filters, investigation filters, selected table rows, or visible-row subsets.",
          "Backend Launch remains authoritative for queue scope, schedule checks, process locks, saved settings, and runtime validation.",
        ],
    );

    add(
      "risk-handoff",
      "Saved-settings risk handoff",
      blockedRiskRows.length ? "blocked" : reviewRiskRows.length ? "review" : "ready",
      `${riskRows.length} launch risk row(s); ${blockedRiskRows.length} blocked; ${reviewRiskRows.length} non-ready.`,
      blockedRiskRows.length
        ? "Resolve blocked Launch Risk Handoff rows before starting media work."
        : reviewRiskRows.length
          ? "Read Launch Risk Handoff rows before unattended runs."
          : "Launch Risk Handoff has no local non-ready rows.",
      reviewRiskRows.slice(0, 8).map((row) => `${row.area}: ${row.impact}; ${row.action}`),
    );

    const latestLaunch = launchSettingsIntentLatestCommand(isLaunchCommand);
    const latestSettings = launchSettingsIntentLatestCommand((entry) => String(entry?.command || "").toLowerCase().startsWith("settings."));
    add(
      "command-evidence",
      "Recent command evidence",
      latestLaunch || latestSettings ? "review" : "unknown",
      `latest launch=${latestLaunch ? latestLaunch.command : "none"}; latest settings=${latestSettings ? latestSettings.command : "none"}.`,
      latestLaunch || latestSettings
        ? "Use command detail/Diagnostics if recent commands warn or disagree with visible state."
        : "Recent command history has no launch/settings evidence yet.",
      [
        `Launch: ${launchSettingsIntentCommandLine(latestLaunch)}`,
        `Settings: ${launchSettingsIntentCommandLine(latestSettings)}`,
      ],
    );

    add(
      "decision-boundary",
      "Decision boundary",
      "ready",
      "This checklist explains launch intent; it is not a backend preflight result.",
      "Submit only after the checklist, Launch preflight, Queue/Reports context, and Diagnostics evidence agree.",
      [
        "Backend launch validation, process locks, schedule enforcement, and command journaling remain the source of truth.",
        "This panel cannot mutate media, queue state, config, pending-publish state, reports, or diagnostics files.",
      ],
    );

    return rows.sort((left, right) => launchSettingsSeverityRank(left.posture) - launchSettingsSeverityRank(right.posture));
  }

  function launchSettingsIntentStatus(rows = launchSettingsIntentRows()) {
    if (!rows.length) return "Not evaluated";
    if (rows.some((row) => row.posture === "blocked")) return "Blocked";
    if (rows.some((row) => row.posture === "high review")) return "High review";
    if (rows.some((row) => row.posture === "review")) return "Review";
    if (rows.some((row) => row.posture === "unknown")) return "Evidence incomplete";
    return "Ready";
  }

  function launchSettingsIntentStatusState(status) {
    const normalized = String(status || "").toLowerCase();
    if (normalized === "blocked") return "blocked";
    if (normalized === "high review" || normalized === "review") return "warning";
    if (normalized === "evidence incomplete" || normalized === "not evaluated") return "unknown";
    if (normalized === "ready") return "ready";
    return "unknown";
  }

  function launchSettingsIntentRowStatus(posture) {
    const normalized = String(posture || "").toLowerCase();
    if (normalized === "blocked") return "blocked";
    if (normalized === "high review" || normalized === "review") return "warning";
    if (normalized === "unknown") return "unknown";
    return "match";
  }

  function launchSettingsIntentSummaryLines(rows = launchSettingsIntentRows()) {
    const counts = rows.reduce((acc, row) => {
      const key = row.posture || "unknown";
      acc[key] = (acc[key] || 0) + 1;
      return acc;
    }, {});
    const reviewRows = rows.filter((row) => row.posture !== "ready");
    const stagedSettingsRow = rows.find((row) => row.key === "staged-settings");
    const lines = [
      "Saved settings vs launch intent checklist:",
      `Rows: ${rows.length}; ready=${counts.ready || 0}; review=${counts.review || 0}; high review=${counts["high review"] || 0}; blocked=${counts.blocked || 0}; unknown=${counts.unknown || 0}.`,
      "Decision rule: Launch uses saved backend settings and selected form intent only; staged Settings JSON does not count until backend Save Patch succeeds and refresh/reload completes.",
    ];
    if (stagedSettingsRow && stagedSettingsRow.posture !== "ready") {
      lines.push(`Staged settings patch: ${stagedSettingsRow.evidence} ${stagedSettingsRow.action}`);
    }
    if (reviewRows.length) {
      lines.push("First action: select non-ready checkpoints and resolve blocked/review evidence before confirming a start.");
      reviewRows.slice(0, 8).forEach((row) => lines.push(`- ${row.checkpoint}: ${row.posture}; ${row.action}`));
      if (reviewRows.length > 8) lines.push(`- ${reviewRows.length - 8} more checkpoint(s) need review.`);
    } else {
      lines.push("First action: no local launch-intent blockers are visible; backend launch validation still has final authority.");
    }
    lines.push("Mutation guardrail: this checklist is read-only and cannot launch, save settings, drain, rename, repair, delete, publish, or touch media files.");
    return lines;
  }

  function selectedLaunchSettingsIntentRow(rows) {
    const source = Array.isArray(rows) ? rows : [];
    return source.find((row) => row.key === state.selectedLaunchSettingsIntentKey) || source.find((row) => row.posture !== "ready") || source[0] || null;
  }

  function launchSettingsIntentDetailLines(row) {
    if (!row) {
      return [
        "Saved settings vs launch intent:",
        "No checklist checkpoint is selected.",
        "Mutation guardrail: this detail panel is read-only.",
      ];
    }
    const lines = [
      "Saved settings vs launch intent:",
      `Checkpoint: ${row.checkpoint || "unknown"}`,
      `Posture: ${row.posture || "unknown"}`,
      `Evidence: ${row.evidence || ""}`,
      `Operator action: ${row.action || ""}`,
    ];
    const detail = Array.isArray(row.detail) ? row.detail : [];
    if (detail.length) {
      lines.push("", "Detail:");
      detail.forEach((line) => lines.push(`- ${line}`));
    }
    lines.push("", "Guardrail: submit launch commands only from backend-owned buttons after visible evidence agrees.");
    return lines;
  }

  function selectLaunchSettingsIntentRow(row) {
    state.selectedLaunchSettingsIntentKey = row?.key || "";
    renderLaunchSettingsIntentChecklist();
  }

  function renderLaunchSettingsIntentChecklist(request = collectPipelineStartRequest(), payload = launchSettingsIntentPayload()) {
    const rows = launchSettingsIntentRows(request, payload);
    if (state.selectedLaunchSettingsIntentKey && !rows.some((row) => row.key === state.selectedLaunchSettingsIntentKey)) {
      state.selectedLaunchSettingsIntentKey = "";
    }
    const selected = selectedLaunchSettingsIntentRow(rows);
    const status = launchSettingsIntentStatus(rows);
    setText("launch-settings-intent-status", status);
    const statusNode = byId("launch-settings-intent-status");
    if (statusNode) statusNode.dataset.state = launchSettingsIntentStatusState(status);
    setText("launch-settings-intent-summary", launchSettingsIntentSummaryLines(rows).join("\n"));
    setText("launch-settings-intent-detail", launchSettingsIntentDetailLines(selected).join("\n"));
    const tbody = byId("launch-settings-intent-rows");
    if (!tbody) return;
    if (!rows.length) {
      clearRows(tbody, 4, "No saved-settings launch-intent rows loaded.");
      updateTableStatusLegend("launch-settings-intent-legend", tbody, "Saved-settings launch-intent rows");
      return;
    }
    tbody.replaceChildren();
    rows.forEach((item) => {
      const row = document.createElement("tr");
      row.dataset.status = launchSettingsIntentRowStatus(item.posture);
      appendCells(row, [item.checkpoint, item.posture, item.evidence, item.action]);
      if (typeof makeRowSelectable === "function") {
        makeRowSelectable(row, () => selectLaunchSettingsIntentRow(item), {
          selected: item.key === selected?.key,
          label: `Launch-intent checkpoint ${item.checkpoint} ${item.posture}`,
        });
      }
      tbody.appendChild(row);
    });
    updateTableStatusLegend("launch-settings-intent-legend", tbody, "Saved-settings launch-intent rows");
  }

    return {
      launchSettingsWorkspace,
      launchSettingsTrustStatus,
      launchSettingsDecision,
      launchSettingsDecisionLines,
      launchUnsavedSettingsPatchLines,
      launchSettingsRiskLines,
      launchSettingsSeverityRank,
      launchRealMediaReadinessLines,
      launchSettingsRiskRows,
      launchSettingsRiskStatus,
      launchSettingsRiskSummaryLines,
      launchSettingsRiskDetailLines,
      renderLaunchSettingsRiskHandoff,
      launchPolicyBoundaryRows,
      launchPolicyBoundaryStatus,
      launchPolicyBoundarySummaryLines,
      launchPolicyBoundaryDetailLines,
      renderLaunchPolicyBoundary,
      launchSettingsIntentPayload,
      launchSettingsIntentLatestCommand,
      launchSettingsIntentCommandLine,
      launchSettingsIntentRows,
      launchSettingsIntentStatus,
      launchSettingsIntentSummaryLines,
      launchSettingsIntentDetailLines,
      renderLaunchSettingsIntentChecklist,
    };
  }

  window.__launchViewRiskModule = {
    createLaunchRiskModule,
  };
})();
