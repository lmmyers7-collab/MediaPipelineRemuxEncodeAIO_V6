(function () {
  let lastSchedule = null;
  let selectedScheduleCoverageKey = "";
  let selectedScheduleDayName = "";
  let scheduleEditorDirty = false;
  let lastScheduleEditorResult = null;
  let scheduleEditorPreviewSignature = "";
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

  function scheduleWatcherData(schedule) {
    return schedule?.continuous_watcher && typeof schedule.continuous_watcher === "object"
      ? schedule.continuous_watcher
      : {};
  }

  function scheduleWatcherStatusValue(schedule) {
    const status = String(scheduleWatcherData(schedule).status || "unknown").toLowerCase();
    if (status === "error" || status === "unavailable") return "blocked";
    if (status === "armed" || status === "stop_requested") return "ready";
    if (status === "idle") return "ready";
    if (status === "completed" || status === "canceled") return "review";
    return "review";
  }

  function scheduleWatcherSummary(schedule) {
    const watcher = scheduleWatcherData(schedule);
    const status = String(watcher.status || "unknown");
    const deadline = watcher.deadline ? ` until ${scheduleDisplayValue(watcher.deadline)}` : "";
    const pid = Number(watcher.pid || 0) > 0 ? ` for PID ${watcher.pid}` : "";
    return `${status}${pid}${deadline}`;
  }

  function scheduleWatcherDetailLines(schedule) {
    const watcher = scheduleWatcherData(schedule);
    return [
      `Status: ${watcher.status || "unknown"}`,
      `PID: ${watcher.pid || "none"}`,
      `Generation: ${Number(watcher.generation || 0) > 0 ? watcher.generation : "none"}`,
      `Deadline: ${scheduleDisplayValue(watcher.deadline)}`,
      `Stop requested: ${watcher.stop_requested ? "yes" : "no"}`,
      `Message: ${watcher.message || "(not reported)"}`,
      `Error: ${watcher.error || "none"}`,
      "Lifecycle: Launch backend start arms this watcher only for scheduled Continuous runs with a stop boundary.",
      "Mutation guardrail: Schedule and Launch views only display watcher state; they cannot directly write stop flags or start work.",
    ];
  }

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
    const watcherStatus = scheduleWatcherStatusValue(schedule);
    const watcher = scheduleWatcherData(schedule);
    return [
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
        status: !enabled ? "ready" : (allowedNow ? "ready" : "blocked"),
        evidence: enabled ? `Allowed now: ${allowedNow ? "yes" : "no"}` : "Not watched while enforcement is off.",
        next_step: enabled && !allowedNow ? "Wait for the next allowed start or use an explicit Launch override." : "Still verify close-readiness, settings, queue, and pending-publish state.",
        detail: [
          `Status text: ${evaluation.status_text || "(not reported)"}`,
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
    if (blocks >= 48) return "match";
    return "ready";
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

  function scheduleWindowsTextForEditor(item) {
    const text = String(item?.windows_text || "").trim();
    if (!text || text.toLowerCase() === "none") return "";
    return text;
  }

  function scheduleDayKey(day) {
    return String(day || "").trim().toLowerCase();
  }

  function scheduleBlockLabel(index) {
    if (index >= SCHEDULE_BLOCKS_PER_DAY) return "24:00";
    const hour = Math.floor(Math.max(0, index) / 2);
    const minute = index % 2 ? 30 : 0;
    return `${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}`;
  }

  function scheduleBlockRangeLabel(index) {
    return `${scheduleBlockLabel(index)} - ${scheduleBlockLabel(index + 1)}`;
  }

  function scheduleTimeTextToBlock(value, allowDayEnd = false) {
    const text = String(value || "").trim();
    if (allowDayEnd && text === "24:00") return SCHEDULE_BLOCKS_PER_DAY;
    const match = text.match(/^(\d{1,2})(?::(\d{2}))?\s*(am|pm|a\.m\.|p\.m\.)?$/i);
    if (!match) return null;
    let hour = Number(match[1]);
    const minute = Number(match[2] || "0");
    const suffix = String(match[3] || "").replace(/\./g, "").toLowerCase();
    if (![0, 30].includes(minute)) return null;
    if (suffix) {
      if (hour < 1 || hour > 12) return null;
      if (suffix === "am") hour = hour === 12 ? 0 : hour;
      else hour = hour === 12 ? 12 : hour + 12;
    } else if (hour === 24 && minute === 0 && allowDayEnd) {
      return SCHEDULE_BLOCKS_PER_DAY;
    } else if (hour < 0 || hour > 23) {
      return null;
    }
    const block = hour * 2 + (minute === 30 ? 1 : 0);
    if (block >= SCHEDULE_BLOCKS_PER_DAY && !allowDayEnd) return null;
    return block;
  }

  function scheduleDraftBlocksFromText(value) {
    const text = String(value || "").trim();
    const blocks = Array.from({ length: SCHEDULE_BLOCKS_PER_DAY }, () => false);
    if (!text || ["none", "off", "closed"].includes(text.toLowerCase())) return blocks;
    if (["all", "all day", "*"].includes(text.toLowerCase())) {
      return blocks.map(() => true);
    }
    const parts = text.split(/[,;\n]+/).map((part) => part.trim()).filter(Boolean);
    parts.forEach((part) => {
      let startText = "";
      let endText = "";
      if (/\s+to\s+/i.test(part)) {
        [startText, endText] = part.split(/\s+to\s+/i, 2);
      } else {
        const dashIndex = part.indexOf("-");
        if (dashIndex < 0) return;
        startText = part.slice(0, dashIndex);
        endText = part.slice(dashIndex + 1);
      }
      const start = scheduleTimeTextToBlock(startText, false);
      const end = scheduleTimeTextToBlock(endText, true);
      if (start === null || end === null || end <= start) return;
      for (let index = start; index < end && index < SCHEDULE_BLOCKS_PER_DAY; index += 1) {
        blocks[index] = true;
      }
    });
    return blocks;
  }

  function scheduleWindowsTextFromBlocks(blockValues) {
    const blocks = Array.from({ length: SCHEDULE_BLOCKS_PER_DAY }, (_, index) => Boolean(blockValues?.[index]));
    const selected = blocks.filter(Boolean).length;
    if (!selected) return "";
    if (selected === SCHEDULE_BLOCKS_PER_DAY) return "all day";
    const windows = [];
    let start = null;
    blocks.concat([false]).forEach((allowed, index) => {
      if (allowed && start === null) {
        start = index;
      } else if (!allowed && start !== null) {
        windows.push(`${scheduleBlockLabel(start)} - ${scheduleBlockLabel(index)}`);
        start = null;
      }
    });
    return windows.join(", ");
  }

  function scheduleEditorSummaryText(text) {
    const value = String(text || "").trim();
    if (!value) return "No windows selected";
    if (["all", "all day", "*"].includes(value.toLowerCase())) return "All day";
    return value;
  }

  function scheduleEditorCountText(blockValues) {
    const count = Array.from({ length: SCHEDULE_BLOCKS_PER_DAY }, (_, index) => Boolean(blockValues?.[index]))
      .filter(Boolean).length;
    return `${count}/${SCHEDULE_BLOCKS_PER_DAY} blocks (${(count / 2).toFixed(1)} h)`;
  }

  function scheduleCoerceBlockValues(blockValues) {
    if (Array.isArray(blockValues) && blockValues.length === SCHEDULE_BLOCKS_PER_DAY && blockValues.every((item) => typeof item === "boolean")) {
      return blockValues.slice();
    }
    const selected = new Set(Array.isArray(blockValues) ? blockValues.map((item) => Number(item)) : []);
    return Array.from({ length: SCHEDULE_BLOCKS_PER_DAY }, (_, index) => selected.has(index));
  }

  function scheduleEditorBlocksForDay(day) {
    const key = scheduleDayKey(day);
    const values = Array.from({ length: SCHEDULE_BLOCKS_PER_DAY }, (_, index) => {
      const button = byId(`schedule-editor-${key}-block-${index}`);
      return button ? button.dataset.selected === "true" : false;
    });
    if (values.some(Boolean)) return values;
    const input = byId(`schedule-editor-${key}-windows`);
    return scheduleDraftBlocksFromText(input?.value || "");
  }

  function scheduleUpdateBlockButton(button, selected) {
    if (!button) return;
    const enabled = Boolean(selected);
    button.dataset.selected = enabled ? "true" : "false";
    button.setAttribute("aria-pressed", enabled ? "true" : "false");
    button.classList.toggle("is-selected", enabled);
  }

  function scheduleApplyEditorDayBlocks(day, blockValues, options = {}) {
    const key = scheduleDayKey(day);
    const values = scheduleCoerceBlockValues(blockValues);
    const text = scheduleWindowsTextFromBlocks(values);
    const input = byId(`schedule-editor-${key}-windows`);
    if (input) input.value = text;
    setText(`schedule-editor-${key}-summary`, scheduleEditorSummaryText(text));
    setText(`schedule-editor-${key}-count`, scheduleEditorCountText(values));
    values.forEach((selected, index) => {
      scheduleUpdateBlockButton(byId(`schedule-editor-${key}-block-${index}`), selected);
    });
    if (options.dirty !== false) setScheduleEditorDirty(true);
    return true;
  }

  function scheduleSetDayBlocks(day, blockValues, options = {}) {
    return scheduleApplyEditorDayBlocks(day, blockValues, options);
  }

  function scheduleToggleEditorBlock(day, index) {
    const values = scheduleEditorBlocksForDay(day);
    if (index >= 0 && index < SCHEDULE_BLOCKS_PER_DAY) {
      values[index] = !values[index];
    }
    scheduleApplyEditorDayBlocks(day, values);
  }

  function scheduleClearEditorDay(day) {
    scheduleApplyEditorDayBlocks(day, []);
  }

  function scheduleAllowAllEditorDay(day) {
    scheduleApplyEditorDayBlocks(
      day,
      Array.from({ length: SCHEDULE_BLOCKS_PER_DAY }, (_, index) => index)
    );
  }

  function scheduleEditorRowsFromPayload(schedule = lastSchedule) {
    const byDay = new Map((Array.isArray(schedule?.day_summaries) ? schedule.day_summaries : [])
      .map((row) => [String(row?.day || ""), row]));
    return SCHEDULE_DAYS.map((day) => {
      const row = byDay.get(day) || { day, windows_text: "" };
      return {
        day,
        current: String(row?.windows_text || "None"),
        draft: scheduleWindowsTextForEditor(row),
      };
    });
  }

  function scheduleEditorRequest() {
    const enabled = Boolean(byId("schedule-editor-enabled")?.checked);
    const dayWindows = {};
    SCHEDULE_DAYS.forEach((day) => {
      const input = byId(`schedule-editor-${day.toLowerCase()}-windows`);
      dayWindows[day] = String(input?.value || "").trim();
    });
    return {
      enabled,
      day_windows: dayWindows,
    };
  }

  function scheduleEditorRequestSignature(request = scheduleEditorRequest()) {
    const dayWindows = {};
    SCHEDULE_DAYS.forEach((day) => {
      dayWindows[day] = String(request?.day_windows?.[day] || "").trim();
    });
    return JSON.stringify({
      enabled: Boolean(request?.enabled),
      day_windows: dayWindows,
    });
  }

  function scheduleEditorPreviewIsCurrent() {
    return Boolean(
      scheduleEditorPreviewSignature &&
      !scheduleEditorDirty &&
      lastScheduleEditorResult?.ok &&
      lastScheduleEditorResult?.command === "schedule.preview" &&
      scheduleEditorPreviewSignature === scheduleEditorRequestSignature()
    );
  }

  function scheduleEditorSaveStateText() {
    if (scheduleEditorPreviewIsCurrent()) return "Preview accepted. Save Schedule is available.";
    if (scheduleEditorDirty) return "Draft changed. Preview required before save.";
    if (lastScheduleEditorResult?.command === "schedule.save" && lastScheduleEditorResult?.ok) return "Schedule saved. Preview again before another save.";
    if (lastScheduleEditorResult?.command === "schedule.preview" && !lastScheduleEditorResult?.ok) return "Preview failed. Fix the draft before save.";
    if (lastScheduleEditorResult?.command === "schedule.preview") return "Preview required before save.";
    return "Preview required before save.";
  }

  function updateScheduleEditorSaveGate() {
    const save = byId("schedule-editor-save-button");
    const canSave = scheduleEditorPreviewIsCurrent();
    if (save) {
      save.disabled = !canSave;
      save.dataset.state = canSave ? "ready" : "blocked";
      save.setAttribute("aria-disabled", canSave ? "false" : "true");
    }
    const saveState = byId("schedule-editor-save-state");
    if (saveState) saveState.dataset.state = canSave ? "ready" : "blocked";
    setText("schedule-editor-save-state", scheduleEditorSaveStateText());
  }

  function scheduleEditorImpactText(schedule = lastSchedule, request = scheduleCurrentLaunchSelection()) {
    const status = scheduleTimingTrustStatus(schedule || {}, request);
    const mode = schedulePipelineModeLabel(request?.mode || "validate");
    const override = scheduleOverrideLabel(request?.schedule_override || "");
    const base = `Launch impact: ${status}. Selected Launch mode: ${mode}; schedule override: ${override}.`;
    if (scheduleEditorDirty) return `${base} Draft changes are not saved yet; Launch still uses the current saved schedule.`;
    if (scheduleEditorPreviewIsCurrent()) return `${base} Preview accepted for this draft; Save Schedule will update future backend Launch preflight timing.`;
    if (lastScheduleEditorResult?.command === "schedule.save" && lastScheduleEditorResult?.ok) return `${base} Schedule saved; refresh or Launch preflight will use the updated windows.`;
    return `${base} Preview the draft before saving schedule changes.`;
  }

  function renderScheduleEditorImpact(schedule = lastSchedule, request = scheduleCurrentLaunchSelection()) {
    const text = scheduleEditorImpactText(schedule || {}, request);
    const node = byId("schedule-editor-impact");
    if (node) {
      node.dataset.state = String(scheduleTimingTrustStatus(schedule || {}, request)).toLowerCase().replace(/\s+/g, "-");
    }
    setText("schedule-editor-impact", text);
  }

  function scheduleEditorResultLines(result) {
    if (!result) {
      return [
        "No schedule preview or save result loaded.",
        "Use Preview Schedule before Save Schedule. Backend validation owns time parsing and app-state writes.",
      ];
    }
    const data = result.data || {};
    const lines = [
      `Command: ${result.command || "(unknown)"}`,
      `Result: ${result.ok ? "ok" : "not ok"} (${result.severity || "info"})`,
      `Message: ${result.message || "(none)"}`,
      `Writes app state: ${data.writes_app_state ? "yes" : "no"}`,
      `Enabled candidate: ${data.enabled ? "yes" : "no"}`,
      `Changed enabled: ${data.changed_enabled ? "yes" : "no"}`,
      `Changed day(s): ${Array.isArray(data.changed_days) && data.changed_days.length ? data.changed_days.join(", ") : "none"}`,
    ];
    const warnings = Array.isArray(result.warnings) ? result.warnings.filter(Boolean) : [];
    const errors = Array.isArray(result.errors) ? result.errors.filter(Boolean) : [];
    if (warnings.length) {
      lines.push("", "Warning(s):", ...warnings.map((item) => `- ${item}`));
    }
    if (errors.length) {
      lines.push("", "Error(s):", ...errors.map((item) => `- ${item}`));
    }
    lines.push("", "Mutation guardrail: schedule preview is read-only; schedule save writes only desktop app state through the backend service and cannot start work, override schedule gates, mutate queue state, or touch media files.");
    return lines;
  }

  function renderScheduleEditorResult(result) {
    lastScheduleEditorResult = result || null;
    setText("schedule-editor-status", result ? (result.ok ? "Result ready" : "Review result") : (scheduleEditorDirty ? "Unsaved edits" : "Ready"));
    setText("schedule-editor-result", scheduleEditorResultLines(result).join("\n"));
    updateScheduleEditorSaveGate();
    renderScheduleEditorImpact(lastSchedule || {});
  }

  function setScheduleEditorDirty(value) {
    scheduleEditorDirty = Boolean(value);
    if (scheduleEditorDirty) {
      scheduleEditorPreviewSignature = "";
    }
    updateScheduleEditorSaveGate();
    renderScheduleEditorImpact(lastSchedule || {});
    if (!scheduleEditorDirty) {
      setText("schedule-editor-status", "Ready");
      return;
    }
    setText("schedule-editor-status", "Unsaved edits");
  }

  function renderScheduleEditor(schedule = lastSchedule, options = {}) {
    const tbody = byId("schedule-editor-rows");
    if (!tbody) return;
    const force = Boolean(options.force);
    const loaded = schedulePayloadLoaded(schedule || {});
    if (!loaded && !force) {
      clearRows(tbody, 3, "No schedule editor loaded.");
      renderScheduleEditorResult(null);
      return;
    }
    if (scheduleEditorDirty && !force) {
      setText("schedule-editor-status", "Unsaved edits");
      return;
    }
    const enabledInput = byId("schedule-editor-enabled");
    if (enabledInput) enabledInput.checked = Boolean(schedule?.enabled);
    scheduleEditorPreviewSignature = "";
    tbody.replaceChildren();
    scheduleEditorRowsFromPayload(schedule || {}).forEach((item) => {
      const dayKey = scheduleDayKey(item.day);
      const row = document.createElement("tr");
      row.dataset.status = item.draft ? "ready" : "normal";
      const dayCell = document.createElement("td");
      dayCell.textContent = item.day;
      const inputCell = document.createElement("td");
      const blockShell = document.createElement("div");
      blockShell.className = "schedule-block-picker";
      const toolbar = document.createElement("div");
      toolbar.className = "schedule-block-toolbar";
      const summary = document.createElement("div");
      summary.className = "schedule-block-summary";
      summary.id = `schedule-editor-${dayKey}-summary`;
      const count = document.createElement("span");
      count.className = "schedule-block-count";
      count.id = `schedule-editor-${dayKey}-count`;
      const actions = document.createElement("div");
      actions.className = "schedule-block-actions";
      const clearDay = document.createElement("button");
      clearDay.type = "button";
      clearDay.className = "schedule-block-action";
      clearDay.id = `schedule-editor-${dayKey}-clear-day`;
      clearDay.textContent = "Clear Day";
      clearDay.addEventListener("click", () => scheduleClearEditorDay(item.day));
      const allowDay = document.createElement("button");
      allowDay.type = "button";
      allowDay.className = "schedule-block-action";
      allowDay.id = `schedule-editor-${dayKey}-allow-day`;
      allowDay.textContent = "All Day";
      allowDay.addEventListener("click", () => scheduleAllowAllEditorDay(item.day));
      actions.append(clearDay, allowDay);
      toolbar.append(summary, count, actions);
      const input = document.createElement("input");
      input.id = `schedule-editor-${dayKey}-windows`;
      input.type = "hidden";
      input.autocomplete = "off";
      input.spellcheck = false;
      input.placeholder = "Generated from selected 30-minute blocks";
      input.value = item.draft;
      input.addEventListener("input", () => {
        scheduleApplyEditorDayBlocks(item.day, scheduleDraftBlocksFromText(input.value));
      });
      const grid = document.createElement("div");
      grid.className = "schedule-block-grid";
      grid.id = `schedule-editor-${dayKey}-blocks`;
      grid.setAttribute("role", "group");
      grid.setAttribute("aria-label", `${item.day} 30-minute schedule blocks`);
      Array.from({ length: SCHEDULE_BLOCKS_PER_DAY }, (_, index) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "schedule-block-button";
        button.id = `schedule-editor-${dayKey}-block-${index}`;
        button.textContent = scheduleBlockLabel(index);
        button.title = `${item.day} ${scheduleBlockRangeLabel(index)}`;
        button.dataset.scheduleDay = item.day;
        button.dataset.blockIndex = String(index);
        button.addEventListener("click", () => scheduleToggleEditorBlock(item.day, index));
        grid.appendChild(button);
        return button;
      });
      blockShell.append(toolbar, input, grid);
      inputCell.appendChild(blockShell);
      const currentCell = document.createElement("td");
      currentCell.textContent = item.current || "None";
      row.append(dayCell, inputCell, currentCell);
      tbody.appendChild(row);
      scheduleApplyEditorDayBlocks(item.day, scheduleDraftBlocksFromText(item.draft), { dirty: false });
    });
    setScheduleEditorDirty(false);
    renderScheduleEditorResult(lastScheduleEditorResult);
  }

  function loadCurrentScheduleIntoEditor() {
    renderScheduleEditor(lastSchedule || {}, { force: true });
    lastScheduleEditorResult = null;
    scheduleEditorPreviewSignature = "";
    setText("schedule-editor-result", "Loaded current backend schedule payload into the editor.\nMutation guardrail: nothing was saved.");
    updateScheduleEditorSaveGate();
    renderScheduleEditorImpact(lastSchedule || {});
  }

  function clearScheduleEditorWeek() {
    if (typeof window.confirm === "function" && !window.confirm("Clear the full weekly schedule draft?\n\nThis only stages a draft. Use Preview Schedule and Save Schedule before backend app state changes.")) {
      return;
    }
    SCHEDULE_DAYS.forEach((day) => {
      scheduleApplyEditorDayBlocks(day, [], { dirty: false });
    });
    setScheduleEditorDirty(true);
  }

  function allowAllScheduleEditorWeek() {
    if (typeof window.confirm === "function" && !window.confirm("Allow every day and time in the weekly schedule draft?\n\nThis only stages a draft. Use Preview Schedule and Save Schedule before backend app state changes.")) {
      return;
    }
    const allBlocks = Array.from({ length: SCHEDULE_BLOCKS_PER_DAY }, (_, index) => index);
    SCHEDULE_DAYS.forEach((day) => {
      scheduleApplyEditorDayBlocks(day, allBlocks, { dirty: false });
    });
    setScheduleEditorDirty(true);
  }

  async function previewScheduleEditor() {
    setText("schedule-editor-status", "Previewing");
    scheduleEditorPreviewSignature = "";
    updateScheduleEditorSaveGate();
    const request = scheduleEditorRequest();
    const requestSignature = scheduleEditorRequestSignature(request);
    try {
      const result = await apiPost("/api/schedule/preview", request);
      appendCommandResult(result);
      if (result?.ok) {
        scheduleEditorPreviewSignature = requestSignature;
        scheduleEditorDirty = false;
      }
      renderScheduleEditorResult(result);
    } catch (error) {
      const result = {
        command: "schedule.preview",
        ok: false,
        severity: "error",
        message: `Schedule preview failed: ${error.message || error}`,
        errors: [String(error.message || error)],
        refresh_hint: "schedule",
      };
      appendCommandResult(result);
      renderScheduleEditorResult(result);
    }
  }

  async function saveScheduleEditor() {
    const request = scheduleEditorRequest();
    if (!scheduleEditorPreviewIsCurrent()) {
      const result = {
        command: "schedule.save",
        ok: false,
        severity: "warning",
        message: "Preview Schedule must succeed for the current draft before Save Schedule can write app state.",
        warnings: ["Draft has no current successful backend preview."],
        refresh_hint: "schedule",
      };
      appendCommandResult(result);
      renderScheduleEditorResult(result);
      return;
    }
    const confirmed = window.confirm(
      "Save Schedule?\n\nThis writes schedule_enabled and schedule_grid to desktop app state through the backend. It does not start work, bypass schedule gates, mutate queue state, or touch media files."
    );
    if (!confirmed) {
      const result = {
        command: "schedule.save",
        ok: false,
        severity: "warning",
        message: "Schedule save cancelled.",
        warnings: ["Operator cancelled before backend save."],
        refresh_hint: "schedule",
      };
      appendCommandResult(result);
      renderScheduleEditorResult(result);
      return;
    }
    setText("schedule-editor-status", "Saving");
    try {
      const result = await apiPost("/api/schedule/save", { ...request, confirm_save: true });
      appendCommandResult(result);
      scheduleEditorPreviewSignature = "";
      renderScheduleEditorResult(result);
      if (result.ok) {
        setScheduleEditorDirty(false);
        if (typeof refreshAllNow === "function") {
          await refreshAllNow();
        }
      }
    } catch (error) {
      const result = {
        command: "schedule.save",
        ok: false,
        severity: "error",
        message: `Schedule save failed: ${error.message || error}`,
        errors: [String(error.message || error)],
        refresh_hint: "schedule",
      };
      appendCommandResult(result);
      renderScheduleEditorResult(result);
    }
  }

  function initScheduleViewEvents() {
    const enabled = byId("schedule-editor-enabled");
    if (enabled) enabled.addEventListener("change", () => setScheduleEditorDirty(true));
    const load = byId("schedule-editor-load-current-button");
    if (load) load.addEventListener("click", loadCurrentScheduleIntoEditor);
    const clear = byId("schedule-editor-clear-button");
    if (clear) clear.addEventListener("click", clearScheduleEditorWeek);
    const allowAll = byId("schedule-editor-allow-all-button");
    if (allowAll) allowAll.addEventListener("click", allowAllScheduleEditorWeek);
    const preview = byId("schedule-editor-preview-button");
    if (preview) preview.addEventListener("click", previewScheduleEditor);
    const save = byId("schedule-editor-save-button");
    if (save) save.addEventListener("click", saveScheduleEditor);
  }

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
    if (allowedState) allowedState.dataset.state = lastSchedule.enabled && evaluation.allowed_now === false ? "blocked" : "ready";
    setText("schedule-status", warnings.length ? `${warnings.length} warning${warnings.length === 1 ? "" : "s"}` : "Read-only");
    const summary = [
      evaluation.status_text || "",
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
      row.dataset.status = scheduleDayRowStatus(item, lastSchedule);
      appendCells(row, [
        item.day || "",
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
  }

  /**
   * Public namespace for the Schedule page module.
   * Prefer this namespace from new code; flat window.* exports are transitional compatibility aliases when present.
   */
  window.mediaPipelineScheduleView = {
    renderSchedule,
    renderScheduleGuidance,
    renderScheduleTimingTrust,
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
  window.renderSchedule = renderSchedule;
  window.renderScheduleTimingTrust = renderScheduleTimingTrust;
  window.initScheduleViewEvents = initScheduleViewEvents;
  window.scheduleTimingTrustStatus = scheduleTimingTrustStatus;
  window.scheduleTimingTrustLines = scheduleTimingTrustLines;
  window.scheduleCurrentLaunchSelection = scheduleCurrentLaunchSelection;
  window.scheduleWatcherSummary = scheduleWatcherSummary;
  window.schedulePipelineModeLabel = schedulePipelineModeLabel;
  window.scheduleOverrideLabel = scheduleOverrideLabel;
  window.scheduleDisplayValue = scheduleDisplayValue;
})();
