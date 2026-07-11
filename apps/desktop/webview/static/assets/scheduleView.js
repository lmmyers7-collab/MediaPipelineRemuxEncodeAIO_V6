(function () {
  let lastSchedule = null;
  let selectedScheduleCoverageKey = "";
  let selectedScheduleDayName = "";

  const SCHEDULE_DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
  const SCHEDULE_BLOCKS_PER_DAY = 48;

  function scheduleDisplayValue(value) {
    if (!value) return "None";
    const text = String(value);
    const parsed = new Date(text);
    if (!Number.isNaN(parsed.getTime())) {
      return parsed.toLocaleString();
    }
    return text;
  }

  function scheduleGuidanceStatus(schedule) {
    const evaluation = schedule?.evaluation || {};
    if ((schedule?.warnings || []).length) return "Warnings";
    if (!schedule?.enabled) return "Schedule off";
    return evaluation.allowed_now === false ? "Outside window" : "Inside window";
  }

  const scheduleWatchFolderModule = window.__scheduleWatchFolderModule;
  if (!scheduleWatchFolderModule?.createScheduleWatchFolderModule) throw new Error("Missing Schedule watch-folder module");
  delete window.__scheduleWatchFolderModule;
  const {
    scheduleWatcherData, scheduleWatcherStatusValue, scheduleWatcherSummary, scheduleWatcherDetailLines,
    watchFolderStatusLabel, watchFolderStatusValue, watchFolderSummaryLines, watchFolderRecentLines,
    renderWatchFolderStatus,
  } = scheduleWatchFolderModule.createScheduleWatchFolderModule({ appendCells, byId, scheduleDisplayValue, setText });
  function scheduleLaunchGuidanceLines(schedule) {
    const evaluation = schedule?.evaluation || {};
    const enabled = Boolean(schedule?.enabled);
    const allowed = evaluation.allowed_now !== false;
    const nextStart = scheduleDisplayValue(evaluation.next_allowed_start);
    const windowEnd = scheduleDisplayValue(evaluation.current_window_end || evaluation.next_allowed_end);
    const lines = [
      `Current state: ${enabled ? (allowed ? "inside an allowed window" : "outside the allowed window") : "schedule enforcement is off"}`,
      `Next allowed start: ${nextStart}`,
      `Relevant window end: ${windowEnd}`,
      `Backend continuous watcher: ${scheduleWatcherSummary(schedule)}`,
    ];
    if (!enabled) {
      lines.push(
        "Pipeline launch guidance: Run Once and Continuous are not schedule-blocked while enforcement is off.",
        "Validate and Publish Parked are not schedule-watched modes."
      );
    } else if (allowed) {
      lines.push(
        "Pipeline launch guidance: Run Once can launch now.",
        "Continuous from the WebView must pass Backend Preflight; backend start arms the schedule-stop watcher when a current window end is reported.",
        "Validate and Publish Parked are not schedule-watched modes."
      );
    } else {
      lines.push(
        "Pipeline launch guidance: normal Run Once/Continuous starts are blocked outside the allowed window.",
        "Use Run Once Outside Window for a one-shot launch, or Ignore Schedule only when you intentionally want to bypass enforcement.",
        "Validate and Publish Parked are not schedule-watched modes."
      );
    }
    if ((schedule?.warnings || []).length) {
      lines.push("", "Schedule warnings:", ...schedule.warnings.map((item) => `- ${item}`));
    }
    lines.push("Backend launch gating remains the source of truth.");
    return lines;
  }

  function schedulePipelineModeLabel(mode) {
    const labels = {
      validate: "Validate",
      once: "Run Once",
      continuous: "Continuous",
      drain_pending_pushes: "Publish Parked",
    };
    return labels[mode] || mode || "Pipeline";
  }

  function scheduleOverrideLabel(value) {
    const labels = {
      "": "None",
      run_once: "Run Once Outside Window",
      ignore: "Ignore Schedule",
    };
    return Object.prototype.hasOwnProperty.call(labels, value) ? labels[value] : (value || "None");
  }

  function scheduleCurrentLaunchSelection() {
    return {
      mode: byId("pipeline-start-mode")?.value || "validate",
      schedule_override: byId("pipeline-start-schedule-override")?.value || "",
    };
  }

  function schedulePayloadLoaded(schedule) {
    return Boolean(
      schedule &&
      typeof schedule === "object" &&
      (
        schedule.schema_version ||
        schedule.evaluation ||
        schedule.enabled !== undefined ||
        Array.isArray(schedule.day_summaries) ||
        Array.isArray(schedule.warnings)
      )
    );
  }

  function scheduleTotalAllowedBlocks(schedule) {
    return (Array.isArray(schedule?.day_summaries) ? schedule.day_summaries : [])
      .reduce((total, row) => total + Number(row?.allowed_blocks || 0), 0);
  }

  function scheduleAllowedDayCount(schedule) {
    return (Array.isArray(schedule?.day_summaries) ? schedule.day_summaries : [])
      .filter((row) => Number(row?.allowed_blocks || 0) > 0).length;
  }

  function scheduleCurrentDayName(schedule) {
    const evaluation = schedule?.evaluation || {};
    const explicit = evaluation.current_day || evaluation.day || schedule?.current_day;
    return explicit ? String(explicit) : "";
  }

  function scheduleCurrentDayEvidence(schedule) {
    const evaluation = schedule?.evaluation || {};
    const currentDay = scheduleCurrentDayName(schedule);
    if (!schedulePayloadLoaded(schedule || {})) return "Backend current day: not loaded.";
    if (!currentDay) return "Backend current day: not reported.";
    const block = Number.isFinite(Number(evaluation.current_block_index))
      ? `; block ${Number(evaluation.current_block_index)}`
      : "";
    const start = evaluation.current_block_start
      ? `; block start ${scheduleDisplayValue(evaluation.current_block_start)}`
      : "";
    return `Backend current day: ${currentDay}${block}${start}.`;
  }

  function scheduleIsCurrentDayRow(item, schedule = lastSchedule) {
    if (!item || !schedule?.enabled || schedule?.evaluation?.allowed_now === false) return false;
    const currentDay = scheduleCurrentDayName(schedule);
    return Boolean(currentDay && String(item.day || "").toLowerCase() === String(currentDay).toLowerCase());
  }

  function scheduleCoverageStatus(schedule) {
    if (!schedulePayloadLoaded(schedule)) return "Not loaded";
    if ((schedule?.warnings || []).length) return "Review";
    if (!schedule?.enabled) return "Schedule off";
    if (scheduleTotalAllowedBlocks(schedule) <= 0) return "Blocked";
    return schedule?.evaluation?.allowed_now === false ? "Outside window" : "Ready";
  }

  function scheduleCoverageRows(schedule) {
    const loaded = schedulePayloadLoaded(schedule);
    const enabled = Boolean(schedule?.enabled);
    const evaluation = schedule?.evaluation || {};
    const warnings = Array.isArray(schedule?.warnings) ? schedule.warnings.filter(Boolean) : [];
    const rows = Array.isArray(schedule?.day_summaries) ? schedule.day_summaries : [];
    const totalBlocks = scheduleTotalAllowedBlocks(schedule);
    const allowedDays = scheduleAllowedDayCount(schedule);
    const totalHours = totalBlocks / 2;
    const allowedNow = evaluation.allowed_now !== false;
    const backendCurrentDay = scheduleCurrentDayName(schedule);
    const currentDayKnown = !enabled || Boolean(backendCurrentDay);
    const watcherStatus = scheduleWatcherStatusValue(schedule);
    const watcher = scheduleWatcherData(schedule);
    const coverageRows = [
      {
        key: "payload",
        check: "Schedule payload",
        status: loaded ? (warnings.length ? "review" : "ready") : "blocked",
        evidence: loaded ? `${rows.length} day row(s); ${warnings.length} warning(s)` : "No schedule payload loaded.",
        next_step: loaded ? "Compare coverage before schedule-sensitive starts." : "Refresh before trusting schedule-sensitive Launch decisions.",
        detail: [
          `Schema: ${schedule?.schema_version || "(missing)"}`,
          `App state path: ${schedule?.app_state_path || "(not reported)"}`,
          `Warnings: ${warnings.length ? warnings.join("; ") : "none"}`,
        ],
      },
      {
        key: "enforcement",
        check: "Enforcement",
        status: enabled ? "ready" : "review",
        evidence: enabled ? "Schedule enforcement is on." : "Schedule enforcement is off.",
        next_step: enabled ? "Use Timing Trust for window-sensitive start choices." : "Starts are not schedule-blocked; backend launch checks still apply.",
        detail: [
          `Enabled: ${enabled ? "yes" : "no"}`,
          enabled
            ? "Schedule edits are backend-owned; scheduled continuous starts are guarded by Launch backend preflight/start and the backend schedule-stop watcher."
            : "Schedule off is allowed, but it removes the time-window safety net for app-started runs.",
        ],
      },
      {
        key: "current-window",
        check: "Current window",
        status: !enabled ? "ready" : (!currentDayKnown ? "review" : (allowedNow ? "ready" : "blocked")),
        evidence: enabled
          ? `Allowed now: ${allowedNow ? "yes" : "no"}; ${scheduleCurrentDayEvidence(schedule)}`
          : "Not watched while enforcement is off.",
        next_step: enabled && !currentDayKnown
          ? "Refresh or inspect backend schedule evaluation before trusting the current-window marker."
          : (enabled && !allowedNow ? "Wait for the next allowed start or use an explicit Launch override." : "Still verify close-readiness, settings, queue, and pending-publish state."),
        detail: [
          `Status text: ${evaluation.status_text || "(not reported)"}`,
          scheduleCurrentDayEvidence(schedule),
          `Next allowed start: ${scheduleDisplayValue(evaluation.next_allowed_start)}`,
          `Relevant window end: ${scheduleDisplayValue(evaluation.current_window_end || evaluation.next_allowed_end)}`,
        ],
      },
      {
        key: "continuous-watcher",
        check: "Continuous watcher",
        status: watcherStatus,
        evidence: `Backend watcher: ${scheduleWatcherSummary(schedule)}`,
        next_step: watcherStatus === "blocked"
          ? "Use Launch Backend Preflight before trusting scheduled Continuous starts."
          : "For Continuous, refresh after Start to confirm the watcher changes from idle to armed when a stop boundary exists.",
        detail: scheduleWatcherDetailLines(schedule),
      },
      {
        key: "weekly-coverage",
        check: "Weekly coverage",
        status: !enabled ? "review" : (totalBlocks > 0 ? "ready" : "blocked"),
        evidence: `${allowedDays} day(s), ${totalHours.toFixed(1)} allowed hour(s) per week.`,
        next_step: totalBlocks > 0 ? "Select a day row to inspect exact windows." : "Use the Schedule Editor panel to define at least one allowed window before relying on enforcement.",
        detail: [
          `Allowed days: ${allowedDays}`,
          `Allowed half-hour blocks: ${totalBlocks}`,
          `Allowed hours: ${totalHours.toFixed(1)}`,
          "A grid with zero allowed windows blocks normal scheduled starts when enforcement is on.",
        ],
      },
      {
        key: "mutation-boundary",
        check: "Save boundary",
        status: "ready",
        evidence: "Schedule edits are staged locally, previewed by the backend, then saved through the backend app-state service.",
        next_step: "Use Preview Schedule before Save Schedule; use Launch Backend Preflight to inspect continuous schedule-stop watcher readiness.",
        detail: [
          "Mutation guardrail: WebView Schedule can preview and save schedule_enabled/schedule_grid only through backend command routes.",
          "It cannot start work, bypass schedule gates, mutate queue state, touch media files, or directly arm the continuous-run schedule-stop watcher; Launch backend start owns that lifecycle.",
          "Backend launch gating remains the source of truth.",
        ],
      },
    ];
    const draftRow = scheduleEditorDraftCoverageRow();
    if (draftRow) {
      coverageRows.splice(Math.max(coverageRows.length - 1, 0), 0, draftRow);
    }
    return coverageRows;
  }

  function scheduleCoverageDetailLines(row, schedule = lastSchedule) {
    if (!row) {
      return [
        "No schedule coverage row selected.",
        "Select a coverage row to see the exact evidence and safe next step.",
        "Mutation guardrail: coverage detail is evidence-only. Use Schedule Editor for backend-owned preview/save; no Schedule view action can start pipeline work.",
      ];
    }
    return [
      `Coverage check: ${row.check || "(unknown)"}`,
      `Status: ${row.status || "normal"}`,
      `Evidence: ${row.evidence || "(none)"}`,
      `Next step: ${row.next_step || "(none)"}`,
      "",
      ...((Array.isArray(row.detail) ? row.detail : []).map((line) => String(line || ""))),
      "",
      `Overall schedule status: ${scheduleCoverageStatus(schedule || {})}`,
      "Mutation guardrail: coverage detail is evidence-only. Use Schedule Editor for backend-owned preview/save; no Schedule view action can start pipeline work.",
    ];
  }

  function selectScheduleCoverageRow(row) {
    selectedScheduleCoverageKey = row?.key || "";
    renderScheduleCoverage(lastSchedule || {});
  }

  function renderScheduleCoverage(schedule) {
    const rows = scheduleCoverageRows(schedule || {});
    setText("schedule-coverage-status", scheduleCoverageStatus(schedule || {}));
    const tbody = byId("schedule-coverage-rows");
    if (!tbody) return;
    tbody.replaceChildren();
    const selected = rows.find((row) => row.key === selectedScheduleCoverageKey) || rows[0] || null;
    selectedScheduleCoverageKey = selected?.key || "";
    rows.forEach((item) => {
      const row = document.createElement("tr");
      row.dataset.status = item.status || "normal";
      appendCells(row, [item.check, item.status, item.evidence, item.next_step]);
      makeRowSelectable(row, () => selectScheduleCoverageRow(item), {
        selected: item.key === selectedScheduleCoverageKey,
        label: `Schedule coverage ${item.check || item.key}`,
      });
      tbody.appendChild(row);
    });
    setText("schedule-coverage-detail", scheduleCoverageDetailLines(selected, schedule || {}).join("\n"));
  }

  function scheduleDayRowStatus(item, schedule = lastSchedule) {
    const blocks = Number(item?.allowed_blocks || 0);
    if (!schedulePayloadLoaded(schedule || {})) return "blocked";
    if (blocks <= 0) return schedule?.enabled ? "review" : "normal";
    if (scheduleIsCurrentDayRow(item, schedule || {})) return blocks >= 48 ? "current-match" : "current";
    if (blocks >= 48) return "match";
    return "ready";
  }

  function scheduleDayCurrentMarkerText(item, schedule = lastSchedule) {
    if (!schedule?.enabled) return "not watched because schedule enforcement is off";
    const currentDay = scheduleCurrentDayName(schedule);
    if (!currentDay) return "unknown because backend current day was not reported";
    if (schedule?.evaluation?.allowed_now === false) return "not current because schedule is outside the allowed window";
    return scheduleIsCurrentDayRow(item, schedule || {}) ? "current saved window" : "not current";
  }

  function scheduleDayDetailLines(item, schedule = lastSchedule) {
    if (!item) {
      return [
        "No schedule day selected.",
        "Select a day row to inspect exact allowed windows and schedule-edit ownership.",
        "Mutation guardrail: this day detail is read-only and cannot edit the weekly schedule.",
      ];
    }
    const blocks = Number(item.allowed_blocks || 0);
    const hours = Number(item.allowed_hours || (blocks / 2));
    const windows = Array.isArray(item.windows) ? item.windows : [];
    const enabled = Boolean(schedule?.enabled);
    const status = scheduleDayRowStatus(item, schedule || {});
    const lines = [
      `Day: ${item.day || "(unknown)"}`,
      `Status: ${status}`,
      `Allowed blocks: ${blocks} (${hours.toFixed(1)} hour(s))`,
      `Windows: ${windows.length ? windows.join("; ") : "None"}`,
      `Current window marker: ${scheduleDayCurrentMarkerText(item, schedule || {})}`,
      scheduleCurrentDayEvidence(schedule || {}),
      "",
    ];
    if (blocks <= 0 && enabled) {
      lines.push("Operator note: this day has no allowed window. Normal scheduled starts on this day require another day/window or an explicit Launch override.");
    } else if (blocks <= 0) {
      lines.push("Operator note: this day has no allowed window, but enforcement is currently off.");
    } else if (blocks >= 48) {
      lines.push("Operator note: this day is allowed all day. Verify this is intentional for unattended operation.");
    } else {
      lines.push("Operator note: starts outside these windows should be schedule-blocked unless an explicit Launch override is selected.");
    }
    lines.push("Mutation guardrail: WebView day rows are evidence rows; use the Schedule Editor panel for backend-owned preview/save.");
    return lines;
  }

  function selectScheduleDay(item) {
    selectedScheduleDayName = item?.day || "";
    renderSchedule(lastSchedule || {});
  }

  function renderScheduleDayDetail(item, schedule = lastSchedule) {
    setText("schedule-day-detail", scheduleDayDetailLines(item, schedule || {}).join("\n"));
  }

  const scheduleEditorModule = window.__scheduleEditorModule;
  if (!scheduleEditorModule?.createScheduleEditorModule) throw new Error("Missing Schedule editor module");
  delete window.__scheduleEditorModule;
  const {
    scheduleBlockLabel, scheduleBlockRangeLabel, scheduleWindowsTextFromBlocks, scheduleDraftBlocksFromText,
    scheduleSetDayBlocks, scheduleEditorRequest, scheduleEditorResultLines, scheduleEditorDraftCoverageRow, renderScheduleDraftSummary,
    renderScheduleSavedScopeNotes, renderScheduleEditorImpact, renderScheduleEditorResult, renderScheduleEditor,
    loadCurrentScheduleIntoEditor, clearScheduleEditorWeek, allowAllScheduleEditorWeek,
    previewScheduleEditor, saveScheduleEditor, initScheduleViewEvents,
  } = scheduleEditorModule.createScheduleEditorModule({
    appendCells,
    appendCommandResult: (...args) => window["appendCommandResult"](...args),
    apiPost: (...args) => window["apiPost"](...args),
    byId,
    clearRows,
    getSchedule: () => lastSchedule,
    refreshAllNow: (...args) => window["refreshAllNow"](...args),
    renderScheduleCoverage,
    scheduleCurrentLaunchSelection,
    schedulePayloadLoaded,
    schedulePipelineModeLabel,
    scheduleOverrideLabel,
    scheduleTimingTrustStatus: (...args) => scheduleTimingTrustStatus(...args),
    scheduleDays: SCHEDULE_DAYS,
    scheduleBlocksPerDay: SCHEDULE_BLOCKS_PER_DAY,
    setText,
  });
  function scheduleTimingTrustStatus(schedule, request = scheduleCurrentLaunchSelection()) {
    const evaluation = schedule?.evaluation || {};
    const mode = String(request?.mode || "validate");
    const override = String(request?.schedule_override || "");
    if (!schedulePayloadLoaded(schedule)) return "Not loaded";
    if ((schedule?.warnings || []).length) return "Review";
    if (mode === "validate" || mode === "drain_pending_pushes") return "Not watched";
    if (!schedule?.enabled) return "Schedule off";
    if (override === "ignore") return "Bypassed";
    if (override === "run_once") return "One-shot override";
    if (!scheduleCurrentDayName(schedule)) return "Review";
    if (evaluation.allowed_now === false) return "Blocked";
    if (mode === "continuous") return "Ready";
    return "Ready";
  }

  function scheduleTimingTrustLines(schedule, request = scheduleCurrentLaunchSelection()) {
    const evaluation = schedule?.evaluation || {};
    const mode = String(request?.mode || "validate");
    const override = String(request?.schedule_override || "");
    if (!schedulePayloadLoaded(schedule)) {
      return [
        "Schedule timing trust:",
        `Selected pipeline mode: ${schedulePipelineModeLabel(mode)}`,
        `Selected schedule override: ${scheduleOverrideLabel(override)}`,
        "Schedule payload: not loaded",
        "Next step: refresh before using schedule-sensitive launch decisions.",
        "Mutation guardrail: this trust panel is read-only; schedule editing and launch acceptance remain backend-owned.",
      ];
    }
    const enabled = Boolean(schedule?.enabled);
    const allowed = evaluation.allowed_now !== false;
    const nextStart = scheduleDisplayValue(evaluation.next_allowed_start);
    const windowEnd = scheduleDisplayValue(evaluation.current_window_end || evaluation.next_allowed_end);
    const lines = [
      "Schedule timing trust:",
      `Selected pipeline mode: ${schedulePipelineModeLabel(mode)}`,
      `Selected schedule override: ${scheduleOverrideLabel(override)}`,
      `Schedule enforcement: ${enabled ? "on" : "off"}`,
      scheduleCurrentDayEvidence(schedule),
      `Allowed now: ${allowed ? "yes" : "no"}`,
      `Next allowed start: ${nextStart}`,
      `Relevant window end: ${windowEnd}`,
      `Backend continuous watcher: ${scheduleWatcherSummary(schedule)}`,
      "",
      "Backend expected decision:",
    ];
    if (mode === "validate" || mode === "drain_pending_pushes") {
      lines.push("- Validate and Publish Parked are not schedule-watched modes.");
      lines.push("- Backend validation/publish checks still own acceptance and drain safety.");
    } else if (!enabled) {
      lines.push("- Schedule enforcement is off; backend launch validation still owns start acceptance.");
    } else if (override === "ignore") {
      lines.push("- Ignore Schedule bypasses the configured window by explicit operator choice.");
      if (mode === "continuous") {
        lines.push("- Continuous + Ignore Schedule is the broadest unattended choice; verify settings, pending publish, and close-readiness first.");
      }
    } else if (override === "run_once") {
      lines.push("- Run Once Outside Window allows a one-shot start even when the current window is closed.");
      if (mode === "continuous") {
        lines.push("- The override resolves Continuous to a one-shot run, so no continuous schedule-stop watcher is needed.");
      }
    } else if (!scheduleCurrentDayName(schedule)) {
      lines.push("- Backend did not report current day/block timing identity; refresh before trusting current-window highlighting.");
    } else if (!allowed) {
      lines.push("- Normal Run Once/Continuous starts should be blocked outside the configured window.");
      lines.push("- Use Run Once Outside Window for a single intentional run, or wait for the next allowed start.");
    } else if (mode === "continuous") {
      lines.push("- Continuous is inside the current window. Backend preflight should show the schedule-stop watcher row as ready when a stop boundary exists.");
      lines.push("- Backend start arms the watcher and will request Stop After Current at the schedule boundary if the process is still running.");
      lines.push(`- Current watcher state: ${scheduleWatcherSummary(schedule)}.`);
    } else {
      lines.push("- Run Once is inside the current window and should be launchable if all other backend checks pass.");
    }
    const warnings = Array.isArray(schedule?.warnings) ? schedule.warnings.filter(Boolean) : [];
    if (warnings.length) {
      lines.push("", "Schedule warning(s):");
      warnings.slice(0, 5).forEach((warning) => lines.push(`- ${warning}`));
    }
    lines.push("", "Mutation guardrail: this trust panel is read-only; schedule editing and launch acceptance remain backend-owned.");
    return lines;
  }

  function renderScheduleGuidance(schedule) {
    setText("schedule-guidance-status", scheduleGuidanceStatus(schedule || {}));
    setText("schedule-guidance", scheduleLaunchGuidanceLines(schedule || {}).join("\n"));
  }

  function renderScheduleTimingTrust(schedule = lastSchedule, request = scheduleCurrentLaunchSelection()) {
    setText("schedule-timing-status", scheduleTimingTrustStatus(schedule || {}, request));
    setText("schedule-timing", scheduleTimingTrustLines(schedule || {}, request).join("\n"));
    renderScheduleEditorImpact(schedule || {}, request);
  }

  function renderSchedule(schedule) {
    lastSchedule = schedule || {};
    const evaluation = lastSchedule.evaluation || {};
    const warnings = Array.isArray(lastSchedule.warnings) ? lastSchedule.warnings : [];
    setText("schedule-enabled-state", lastSchedule.enabled ? "On" : "Off");
    setText("schedule-allowed-state", evaluation.allowed_now === false ? "No" : "Yes");
    setText("schedule-next-start", scheduleDisplayValue(evaluation.next_allowed_start));
    setText("schedule-window-end", scheduleDisplayValue(evaluation.current_window_end || evaluation.next_allowed_end));
    const enabledState = byId("schedule-enabled-state");
    if (enabledState) enabledState.dataset.state = lastSchedule.enabled ? "ready" : "review";
    const allowedState = byId("schedule-allowed-state");
    if (allowedState) {
      allowedState.dataset.state = lastSchedule.enabled && !scheduleCurrentDayName(lastSchedule)
        ? "review"
        : (lastSchedule.enabled && evaluation.allowed_now === false ? "blocked" : "ready");
    }
    setText("schedule-status", warnings.length ? `${warnings.length} warning${warnings.length === 1 ? "" : "s"}` : "Read-only");
    const summary = [
      evaluation.status_text || "",
      scheduleCurrentDayEvidence(lastSchedule),
      lastSchedule.app_state_path ? `App state: ${lastSchedule.app_state_path}` : "",
      ...warnings,
    ].filter(Boolean);
    setText("schedule-summary", summary.join("\n") || "No schedule state loaded.");
    renderScheduleGuidance(lastSchedule);
    renderScheduleTimingTrust(lastSchedule);
    renderScheduleCoverage(lastSchedule);
    renderScheduleEditor(lastSchedule);
    const rows = Array.isArray(lastSchedule.day_summaries) ? lastSchedule.day_summaries : [];
    setText("schedule-day-status", `${rows.length} day${rows.length === 1 ? "" : "s"}`);
    const tbody = byId("schedule-day-rows");
    if (!tbody) return;
    if (!rows.length) {
      clearRows(tbody, 3, "No schedule grid loaded.");
      setText("schedule-day-legend", "Weekly windows table: no selectable rows.");
      renderScheduleDayDetail(null, lastSchedule);
      return;
    }
    tbody.replaceChildren();
    const selected = rows.find((item) => item?.day === selectedScheduleDayName) || rows[0] || null;
    selectedScheduleDayName = selected?.day || "";
    rows.forEach((item) => {
      const row = document.createElement("tr");
      const dayStatus = scheduleDayRowStatus(item, lastSchedule);
      row.dataset.status = dayStatus;
      appendCells(row, [
        scheduleIsCurrentDayRow(item, lastSchedule) ? `${item.day || ""} (current)` : (item.day || ""),
        Number(item.allowed_hours || 0).toFixed(1),
        item.windows_text || "",
      ]);
      makeRowSelectable(row, () => selectScheduleDay(item), {
        selected: item?.day === selectedScheduleDayName,
        label: `Schedule day ${item.day || ""}`,
      });
      tbody.appendChild(row);
    });
    updateTableStatusLegend("schedule-day-legend", tbody, "Weekly windows table");
    renderScheduleDayDetail(selected, lastSchedule);
    renderScheduleDraftSummary();
    renderScheduleSavedScopeNotes();
  }

  /**
   * Public namespace for the Schedule page module.
   * Schedule consumers should use this namespace; no flat window.* exports remain for this module.
   */
  window.mediaPipelineScheduleView = {
    renderSchedule,
    renderScheduleGuidance,
    renderScheduleTimingTrust,
    renderWatchFolderStatus,
    renderScheduleCoverage,
    renderScheduleDayDetail,
    renderScheduleEditor,
    renderScheduleEditorResult,
    initScheduleViewEvents,
    loadCurrentScheduleIntoEditor,
    clearScheduleEditorWeek,
    allowAllScheduleEditorWeek,
    scheduleSetDayBlocks,
    previewScheduleEditor,
    saveScheduleEditor,
    scheduleEditorRequest,
    scheduleEditorResultLines,
    scheduleLaunchGuidanceLines,
    scheduleTimingTrustStatus,
    scheduleTimingTrustLines,
    scheduleCoverageStatus,
    scheduleCoverageRows,
    scheduleCoverageDetailLines,
    scheduleDayRowStatus,
    scheduleDayDetailLines,
    scheduleCurrentLaunchSelection,
    schedulePayloadLoaded,
    scheduleWatcherData,
    scheduleWatcherStatusValue,
    scheduleWatcherSummary,
    scheduleWatcherDetailLines,
    watchFolderStatusLabel,
    watchFolderStatusValue,
    watchFolderSummaryLines,
    watchFolderRecentLines,
    scheduleTotalAllowedBlocks,
    scheduleAllowedDayCount,
    scheduleBlockLabel,
    scheduleBlockRangeLabel,
    scheduleWindowsTextFromBlocks,
    scheduleDraftBlocksFromText,
    selectScheduleCoverageRow,
    selectScheduleDay,
    schedulePipelineModeLabel,
    scheduleOverrideLabel,
    scheduleDisplayValue,
  };
})();
