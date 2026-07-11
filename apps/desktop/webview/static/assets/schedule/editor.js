(function () {
  function createScheduleEditorModule(deps = {}) {
    const {
      appendCells,
      appendCommandResult,
      apiPost,
      byId,
      clearRows,
      getSchedule,
      refreshAllNow,
      renderScheduleCoverage,
      scheduleCurrentLaunchSelection,
      schedulePayloadLoaded,
      schedulePipelineModeLabel,
      scheduleOverrideLabel,
      scheduleTimingTrustStatus,
      scheduleDays,
      scheduleBlocksPerDay,
      setText,    } = deps;
    const SCHEDULE_DAYS = scheduleDays;
    const SCHEDULE_BLOCKS_PER_DAY = scheduleBlocksPerDay;
    let scheduleEditorDirty = false;
    let lastScheduleEditorResult = null;
    let scheduleEditorPreviewSignature = "";
    let scheduleEditorDayClipboard = null;
    let scheduleEditorBusy = "";
    let scheduleEditorDrag = null;
    let scheduleEditorSuppressClick = false;
    let scheduleEditorDragEventsInitialized = false;
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
  function scheduleBlockCompactLabel(index) {
    const bounded = Math.max(0, Math.min(SCHEDULE_BLOCKS_PER_DAY, Number(index) || 0));
    const hour24 = bounded >= SCHEDULE_BLOCKS_PER_DAY ? 0 : Math.floor(bounded / 2);
    const minute = bounded % 2 ? 30 : 0;
    const suffix = hour24 >= 12 ? "PM" : "AM";
    const hour12 = hour24 % 12 || 12;
    return `${hour12}:${String(minute).padStart(2, "0")} ${suffix}`;
  }
  function scheduleTickLabel(index) {
    const hour = Math.floor(Math.max(0, index) / 2);
    if (hour === 0) return "12a";
    if (hour < 12) return `${hour}a`;
    if (hour === 12) return "12p";
    return `${hour - 12}p`;
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

  function scheduleCompactWindowsTextFromBlocks(blockValues) {
    const blocks = Array.from({ length: SCHEDULE_BLOCKS_PER_DAY }, (_, index) => Boolean(blockValues?.[index]));
    const selected = blocks.filter(Boolean).length;
    if (!selected) return "No windows selected";
    if (selected === SCHEDULE_BLOCKS_PER_DAY) return "All day";
    const windows = [];
    let start = null;
    blocks.concat([false]).forEach((allowed, index) => {
      if (allowed && start === null) {
        start = index;
      } else if (!allowed && start !== null) {
        windows.push(`${scheduleBlockCompactLabel(start)}-${scheduleBlockCompactLabel(index)}`);
        start = null;
      }
    });
    return windows.join(", ");
  }

  function scheduleResultGridBlocks(grid, day) {
    const raw = grid && typeof grid === "object" ? grid[day] : null;
    return Array.from({ length: SCHEDULE_BLOCKS_PER_DAY }, (_, index) => Boolean(Array.isArray(raw) ? raw[index] : false));
  }

  function scheduleWindowTextOrNone(blockValues) {
    return scheduleWindowsTextFromBlocks(blockValues) || "none";
  }

  function scheduleDiffWindowText(leftBlocks, rightBlocks, predicate) {
    const values = Array.from({ length: SCHEDULE_BLOCKS_PER_DAY }, (_, index) => {
      const left = Boolean(leftBlocks?.[index]);
      const right = Boolean(rightBlocks?.[index]);
      return predicate(left, right);
    });
    return scheduleWindowTextOrNone(values);
  }

  function scheduleResultDiffLines(data) {
    if (!data || typeof data !== "object") return [];
    const isScheduleResult = data.schema_version === "desktop_schedule_patch_preview.v1" || data.schema_version === "desktop_schedule_save_result.v1";
    const hasCurrentGrid = data.current_grid && typeof data.current_grid === "object";
    const hasProposedGrid = data.grid && typeof data.grid === "object";
    if (!isScheduleResult && !hasCurrentGrid && !hasProposedGrid) return [];

    const lines = [
      "",
      "Schedule diff:",
      `- Current enforcement: ${data.current_enabled ? "on" : "off"}`,
      `- Proposed enforcement: ${data.enabled ? "on" : "off"}`,
    ];
    if (data.changed_enabled) {
      lines.push("- Enforcement change: yes");
    }
    if (!hasCurrentGrid || !hasProposedGrid) {
      lines.push("- Exact day/window diff unavailable: backend result did not include both current_grid and grid.");
      return lines;
    }

    const changedDays = Array.isArray(data.changed_days)
      ? data.changed_days.filter((day) => SCHEDULE_DAYS.includes(String(day)))
      : [];
    const unchangedDays = SCHEDULE_DAYS.filter((day) => !changedDays.includes(day));
    lines.push(`- Changed day count: ${changedDays.length}`);
    lines.push(`- Unchanged day count: ${unchangedDays.length}`);
    if (!changedDays.length && !data.changed_enabled) {
      lines.push("- No effective schedule changes detected.");
      return lines;
    }

    changedDays.forEach((day) => {
      const currentBlocks = scheduleResultGridBlocks(data.current_grid, day);
      const proposedBlocks = scheduleResultGridBlocks(data.grid, day);
      lines.push(
        `${day}:`,
        `- Current: ${scheduleWindowTextOrNone(currentBlocks)}`,
        `- Proposed: ${scheduleWindowTextOrNone(proposedBlocks)}`,
        `- Added: ${scheduleDiffWindowText(currentBlocks, proposedBlocks, (current, proposed) => proposed && !current)}`,
        `- Removed: ${scheduleDiffWindowText(currentBlocks, proposedBlocks, (current, proposed) => current && !proposed)}`
      );
    });
    return lines;
  }

  function scheduleEditorSummaryText(text) {
    const value = String(text || "").trim();
    if (!value) return "No windows selected";
    const blocks = scheduleDraftBlocksFromText(value);
    return scheduleCompactWindowsTextFromBlocks(blocks);
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
    button.setAttribute(
      "aria-label",
      `${button.title || "Schedule time block"} ${enabled ? "allowed" : "blocked"}`
    );
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
    if (scheduleEditorBusy) return;
    const values = scheduleEditorBlocksForDay(day);
    if (index >= 0 && index < SCHEDULE_BLOCKS_PER_DAY) {
      values[index] = !values[index];
    }
    scheduleApplyEditorDayBlocks(day, values);
  }

  function scheduleHandleEditorBlockClick(day, index) {
    if (scheduleEditorSuppressClick) {
      scheduleEditorSuppressClick = false;
      return;
    }
    scheduleToggleEditorBlock(day, index);
  }

  function scheduleEndEditorDrag() {
    scheduleEditorDrag = null;
  }

  function scheduleApplyEditorDragRange(day, index) {
    if (!scheduleEditorDrag || scheduleEditorBusy) return;
    if (scheduleEditorDrag.day !== day) return;
    const start = Math.min(scheduleEditorDrag.startIndex, index);
    const end = Math.max(scheduleEditorDrag.startIndex, index);
    const values = scheduleEditorDrag.baseBlocks.slice();
    for (let block = start; block <= end && block < SCHEDULE_BLOCKS_PER_DAY; block += 1) {
      values[block] = scheduleEditorDrag.targetSelected;
    }
    scheduleApplyEditorDayBlocks(day, values);
  }

  function scheduleStartEditorDrag(day, index, event) {
    if (scheduleEditorBusy) return;
    if (event && typeof event.preventDefault === "function") event.preventDefault();
    const values = scheduleEditorBlocksForDay(day);
    const targetSelected = !Boolean(values[index]);
    scheduleEditorDrag = {
      day,
      startIndex: index,
      targetSelected,
      baseBlocks: values,
    };
    scheduleEditorSuppressClick = true;
    scheduleApplyEditorDragRange(day, index);
  }

  function scheduleContinueEditorDrag(day, index) {
    scheduleApplyEditorDragRange(day, index);
  }

  function initScheduleEditorDragEvents() {
    if (scheduleEditorDragEventsInitialized) return;
    scheduleEditorDragEventsInitialized = true;
    const targets = [window, document].filter((target) => target && typeof target.addEventListener === "function");
    targets.forEach((target) => {
      target.addEventListener("pointerup", scheduleEndEditorDrag);
      target.addEventListener("mouseup", scheduleEndEditorDrag);
      target.addEventListener("blur", scheduleEndEditorDrag);
    });
  }

  function scheduleClearEditorDay(day) {
    if (scheduleEditorBusy) return;
    scheduleApplyEditorDayBlocks(day, []);
  }

  function scheduleAllowAllEditorDay(day) {
    if (scheduleEditorBusy) return;
    scheduleApplyEditorDayBlocks(
      day,
      Array.from({ length: SCHEDULE_BLOCKS_PER_DAY }, (_, index) => index)
    );
  }

  function scheduleUpdatePasteDayButtons() {
    const hasClipboard = Boolean(scheduleEditorDayClipboard?.blocks);
    const sourceDay = scheduleEditorDayClipboard?.day || "";
    SCHEDULE_DAYS.forEach((day) => {
      const key = scheduleDayKey(day);
      const button = byId(`schedule-editor-${key}-paste-day`);
      if (!button) return;
      const disabled = !hasClipboard || Boolean(scheduleEditorBusy);
      button.disabled = disabled;
      button.setAttribute("aria-disabled", disabled ? "true" : "false");
      button.title = scheduleEditorBusy
        ? "Schedule preview/save is in progress"
        : hasClipboard
        ? `Paste copied ${sourceDay} blocks into ${day}`
        : "Copy a day before pasting";
    });
  }

  function scheduleCopyEditorDay(day) {
    if (scheduleEditorBusy) return false;
    const values = scheduleEditorBlocksForDay(day);
    scheduleEditorDayClipboard = {
      day,
      blocks: values.slice(),
    };
    scheduleUpdatePasteDayButtons();
    setText("schedule-editor-status", `Copied ${day}`);
    return true;
  }

  function schedulePasteEditorDay(day) {
    if (scheduleEditorBusy) return false;
    if (!scheduleEditorDayClipboard?.blocks) {
      setText("schedule-editor-status", "Copy a day before pasting");
      scheduleUpdatePasteDayButtons();
      return false;
    }
    const sourceDay = scheduleEditorDayClipboard.day || "copied day";
    scheduleApplyEditorDayBlocks(day, scheduleEditorDayClipboard.blocks);
    setText("schedule-editor-status", `Pasted ${sourceDay} into ${day}`);
    return true;
  }

  function scheduleEditorRowsFromPayload(schedule = getSchedule()) {
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

  function scheduleEditorDraftStats(request = scheduleEditorRequest()) {
    let totalBlocks = 0;
    let allowedDays = 0;
    let allDayDays = 0;
    let noWindowDays = 0;
    SCHEDULE_DAYS.forEach((day) => {
      const blocks = scheduleDraftBlocksFromText(request?.day_windows?.[day] || "");
      const count = blocks.filter(Boolean).length;
      totalBlocks += count;
      if (count > 0) allowedDays += 1;
      if (count >= SCHEDULE_BLOCKS_PER_DAY) allDayDays += 1;
      if (count <= 0) noWindowDays += 1;
    });
    return {
      enabled: Boolean(request?.enabled),
      totalBlocks,
      totalHours: totalBlocks / 2,
      allowedDays,
      allDayDays,
      noWindowDays,
      totalWeekBlocks: SCHEDULE_DAYS.length * SCHEDULE_BLOCKS_PER_DAY,
    };
  }

  function scheduleEditorDraftPosture() {
    if (scheduleEditorBusy === "preview") return "previewing";
    if (scheduleEditorBusy === "save") return "saving";
    if (scheduleEditorDirty) return "draft";
    if (scheduleEditorPreviewIsCurrent()) return "previewed";
    if (lastScheduleEditorResult?.command === "schedule.save" && lastScheduleEditorResult?.ok) return "saved";
    return "current";
  }

  function scheduleEditorDraftSummaryText(prefix = "") {
    const stats = scheduleEditorDraftStats();
    const posture = scheduleEditorDraftPosture();
    const stateLabel = {
      previewing: "backend preview in progress",
      saving: "backend save in progress",
      draft: "not saved",
      previewed: "preview accepted, not saved",
      saved: "saved result shown",
      current: "matches saved/current payload",
    }[posture] || "current";
    const lead = prefix ? `${prefix} ` : "Editor draft:";
    return `${lead} enforcement ${stats.enabled ? "on" : "off"}; ${stats.totalBlocks}/${stats.totalWeekBlocks} blocks staged (${stats.totalHours.toFixed(1)} h) across ${stats.allowedDays} day(s); all-day ${stats.allDayDays}; no-window ${stats.noWindowDays}; ${stateLabel}.`;
  }

  function scheduleEditorDraftCoverageRow() {
    const hasEditor = Boolean(byId("schedule-editor-monday-windows"));
    const shouldShow = hasEditor && (scheduleEditorDirty || scheduleEditorPreviewIsCurrent() || Boolean(scheduleEditorBusy));
    if (!shouldShow) return null;
    const stats = scheduleEditorDraftStats();
    const zeroWindowWhenEnabled = stats.enabled && stats.totalBlocks <= 0;
    const allWeek = stats.totalBlocks >= stats.totalWeekBlocks;
    const posture = scheduleEditorDraftPosture();
    return {
      key: "draft-coverage",
      check: "Draft coverage",
      status: zeroWindowWhenEnabled ? "blocked" : (allWeek ? "review" : "changed"),
      evidence: `${stats.allowedDays} staged day(s), ${stats.totalHours.toFixed(1)} staged hour(s); ${posture}.`,
      next_step: zeroWindowWhenEnabled
        ? "Preview will validate the draft, but enforcement with zero windows blocks normal scheduled starts."
        : "Preview Schedule validates this staged draft before any Save Schedule app-state write.",
      detail: [
        `Draft enabled: ${stats.enabled ? "yes" : "no"}`,
        `Staged allowed days: ${stats.allowedDays}`,
        `Staged half-hour blocks: ${stats.totalBlocks}`,
        `Staged allowed hours: ${stats.totalHours.toFixed(1)}`,
        `All-day day count: ${stats.allDayDays}`,
        `No-window day count: ${stats.noWindowDays}`,
        allWeek ? "Review: the draft allows every day and time." : "Draft does not allow every day and time.",
        "Draft coverage is local staging evidence only. Saved/current Schedule Trust and Launch Windows remain based on the backend payload until Save Schedule succeeds.",
      ],
    };
  }

  function renderScheduleDraftSummary(prefix = "") {
    const node = byId("schedule-editor-draft-summary");
    if (!node) return;
    const posture = scheduleEditorDraftPosture();
    node.dataset.state = posture;
    node.textContent = scheduleEditorDraftSummaryText(prefix);
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

  function scheduleSavedScopeText(base) {
    if (scheduleEditorDirty) return `${base}: saved/current payload; unsaved draft is staged above.`;
    if (scheduleEditorPreviewIsCurrent()) return `${base}: saved/current payload; previewed draft is not saved.`;
    if (scheduleEditorBusy === "save") return `${base}: saved/current payload while backend save is pending.`;
    if (lastScheduleEditorResult?.command === "schedule.save" && lastScheduleEditorResult?.ok) return `${base}: refreshed from saved/current payload after save.`;
    return `${base}: saved/current payload.`;
  }

  function renderScheduleSavedScopeNotes() {
    const state = scheduleEditorDirty || scheduleEditorPreviewIsCurrent() || scheduleEditorBusy ? "draft" : "saved";
    [
      ["schedule-current-scope", "Current Schedule"],
      ["schedule-day-scope", "Weekly View"],
      ["schedule-timing-scope", "Schedule Trust"],
      ["schedule-guidance-scope", "Launch Windows"],
      ["schedule-coverage-scope", "Coverage Review"],
    ].forEach(([id, label]) => {
      const node = byId(id);
      if (!node) return;
      node.dataset.state = state;
      node.textContent = scheduleSavedScopeText(label);
    });
  }

  function scheduleEditorSaveStateText() {
    if (scheduleEditorBusy === "preview") return "Previewing schedule with backend validation.";
    if (scheduleEditorBusy === "save") return "Saving schedule through backend app-state service.";
    if (scheduleEditorPreviewIsCurrent()) return "Preview accepted. Save Schedule is available.";
    if (scheduleEditorDirty) return "Draft changed. Preview required before save.";
    if (lastScheduleEditorResult?.command === "schedule.save" && lastScheduleEditorResult?.ok) return "Schedule saved. Preview again before another save.";
    if (lastScheduleEditorResult?.command === "schedule.preview" && !lastScheduleEditorResult?.ok) return "Preview failed. Fix the draft before save.";
    if (lastScheduleEditorResult?.command === "schedule.preview") return "Preview required before save.";
    return "Preview required before save.";
  }

  function updateScheduleEditorControlLocks() {
    const busy = Boolean(scheduleEditorBusy);
    const ids = [
      "schedule-editor-enabled",
      "schedule-editor-load-current-button",
      "schedule-editor-preview-button",
      "schedule-editor-clear-button",
      "schedule-editor-allow-all-button",
    ];
    ids.forEach((id) => {
      const node = byId(id);
      if (!node) return;
      node.disabled = busy;
      node.setAttribute("aria-disabled", busy ? "true" : "false");
    });
    document.querySelectorAll("#schedule-editor-rows button").forEach((button) => {
      button.disabled = busy;
      button.setAttribute("aria-disabled", busy ? "true" : "false");
    });
    scheduleUpdatePasteDayButtons();
  }

  function updateScheduleEditorSaveGate() {
    const save = byId("schedule-editor-save-button");
    const canSave = scheduleEditorPreviewIsCurrent() && !scheduleEditorBusy;
    const panel = byId("schedule-editor-panel");
    if (panel) {
      panel.setAttribute("aria-busy", scheduleEditorBusy ? "true" : "false");
      panel.dataset.state = scheduleEditorDraftPosture();
    }
    if (save) {
      save.disabled = !canSave;
      save.dataset.state = canSave ? "ready" : "blocked";
      save.setAttribute("aria-disabled", canSave ? "false" : "true");
    }
    const saveState = byId("schedule-editor-save-state");
    if (saveState) saveState.dataset.state = canSave ? "ready" : "blocked";
    setText("schedule-editor-save-state", scheduleEditorSaveStateText());
    updateScheduleEditorControlLocks();
    renderScheduleDraftSummary();
    renderScheduleSavedScopeNotes();
    if (schedulePayloadLoaded(getSchedule() || {})) renderScheduleCoverage(getSchedule() || {});
  }

  function setScheduleEditorBusy(value) {
    scheduleEditorBusy = value || "";
    const panel = byId("schedule-editor-panel");
    if (panel) {
      panel.setAttribute("aria-busy", scheduleEditorBusy ? "true" : "false");
      panel.dataset.state = scheduleEditorBusy || scheduleEditorDraftPosture();
    }
    updateScheduleEditorSaveGate();
  }

  function scheduleEditorImpactText(schedule = getSchedule(), request = scheduleCurrentLaunchSelection()) {
    const status = scheduleTimingTrustStatus(schedule || {}, request);
    const mode = schedulePipelineModeLabel(request?.mode || "validate");
    const override = scheduleOverrideLabel(request?.schedule_override || "");
    const base = `Launch impact: ${status}. Selected Launch mode: ${mode}; schedule override: ${override}.`;
    if (scheduleEditorDirty) return `${base} Draft changes are not saved yet; Launch still uses the current saved schedule.`;
    if (scheduleEditorPreviewIsCurrent()) return `${base} Preview accepted for this draft; Save Schedule will update future backend Launch preflight timing.`;
    if (lastScheduleEditorResult?.command === "schedule.save" && lastScheduleEditorResult?.ok) return `${base} Schedule saved; refresh or Launch preflight will use the updated windows.`;
    return `${base} Preview the draft before saving schedule changes.`;
  }

  function renderScheduleEditorImpact(schedule = getSchedule(), request = scheduleCurrentLaunchSelection()) {
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
    lines.push(...scheduleResultDiffLines(data));
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
    renderScheduleEditorImpact(getSchedule() || {});
  }

  function setScheduleEditorDirty(value) {
    scheduleEditorDirty = Boolean(value);
    if (scheduleEditorDirty) {
      scheduleEditorPreviewSignature = "";
    }
    updateScheduleEditorSaveGate();
    renderScheduleEditorImpact(getSchedule() || {});
    if (!scheduleEditorDirty) {
      setText("schedule-editor-status", "Ready");
      return;
    }
    setText("schedule-editor-status", "Unsaved edits");
  }

  function renderScheduleEditor(schedule = getSchedule(), options = {}) {
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
      dayCell.className = "schedule-editor-day-cell";
      const dayLabel = document.createElement("strong");
      dayLabel.className = "schedule-editor-day-label";
      dayLabel.textContent = item.day;
      dayCell.appendChild(dayLabel);
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
      toolbar.append(summary, count);
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
      const ticks = document.createElement("div");
      ticks.className = "schedule-time-ticks";
      ticks.setAttribute("aria-hidden", "true");
      for (let index = 0; index < SCHEDULE_BLOCKS_PER_DAY; index += 6) {
        const tick = document.createElement("span");
        tick.className = "schedule-time-tick";
        tick.style.gridColumn = `${index + 1} / span 4`;
        tick.textContent = scheduleTickLabel(index);
        ticks.appendChild(tick);
      }
      const grid = document.createElement("div");
      grid.className = "schedule-block-grid schedule-time-rail";
      grid.id = `schedule-editor-${dayKey}-blocks`;
      grid.setAttribute("role", "group");
      grid.setAttribute("aria-label", `${item.day} 30-minute schedule timeline`);
      Array.from({ length: SCHEDULE_BLOCKS_PER_DAY }, (_, index) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "schedule-block-button";
        button.id = `schedule-editor-${dayKey}-block-${index}`;
        button.title = `${item.day} ${scheduleBlockRangeLabel(index)}`;
        button.dataset.scheduleDay = item.day;
        button.dataset.blockIndex = String(index);
        button.addEventListener("pointerdown", (event) => scheduleStartEditorDrag(item.day, index, event));
        button.addEventListener("pointerenter", () => scheduleContinueEditorDrag(item.day, index));
        button.addEventListener("click", () => scheduleHandleEditorBlockClick(item.day, index));
        grid.appendChild(button);
        return button;
      });
      blockShell.append(toolbar, input, ticks, grid);
      inputCell.appendChild(blockShell);
      const currentCell = document.createElement("td");
      currentCell.className = "schedule-block-current-cell";
      const currentValue = document.createElement("div");
      currentValue.className = "schedule-block-current";
      const currentLabel = document.createElement("span");
      currentLabel.className = "metric-label";
      currentLabel.textContent = "Saved";
      const currentText = document.createElement("strong");
      currentText.className = "schedule-block-current-value";
      currentText.textContent = String(item.current || "").trim().toLowerCase() === "none"
        ? "None"
        : scheduleEditorSummaryText(item.current || "");
      currentValue.append(currentLabel, currentText);
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
      const copyDay = document.createElement("button");
      copyDay.type = "button";
      copyDay.className = "schedule-block-action";
      copyDay.id = `schedule-editor-${dayKey}-copy-day`;
      copyDay.textContent = "Copy Day";
      copyDay.title = `Copy ${item.day} selected blocks`;
      copyDay.addEventListener("click", () => scheduleCopyEditorDay(item.day));
      const pasteDay = document.createElement("button");
      pasteDay.type = "button";
      pasteDay.className = "schedule-block-action";
      pasteDay.id = `schedule-editor-${dayKey}-paste-day`;
      pasteDay.textContent = "Paste Day";
      pasteDay.addEventListener("click", () => schedulePasteEditorDay(item.day));
      actions.append(clearDay, allowDay, copyDay, pasteDay);
      currentCell.append(currentValue, actions);
      row.append(dayCell, inputCell, currentCell);
      tbody.appendChild(row);
      scheduleApplyEditorDayBlocks(item.day, scheduleDraftBlocksFromText(item.draft), { dirty: false });
    });
    setScheduleEditorDirty(false);
    renderScheduleEditorResult(lastScheduleEditorResult);
    scheduleUpdatePasteDayButtons();
  }

  function loadCurrentScheduleIntoEditor() {
    if (scheduleEditorBusy) return;
    renderScheduleEditor(getSchedule() || {}, { force: true });
    lastScheduleEditorResult = null;
    scheduleEditorPreviewSignature = "";
    scheduleEditorDayClipboard = null;
    scheduleUpdatePasteDayButtons();
    setText("schedule-editor-result", "Loaded current backend schedule payload into the editor.\nMutation guardrail: nothing was saved.");
    updateScheduleEditorSaveGate();
    renderScheduleEditorImpact(getSchedule() || {});
    renderScheduleDraftSummary("Loaded current:");
  }

  function clearScheduleEditorWeek() {
    if (scheduleEditorBusy) return;
    if (typeof window.confirm === "function" && !window.confirm("Clear the full weekly schedule draft?\n\nThis only stages a draft. Use Preview Schedule and Save Schedule before backend app state changes.")) {
      return;
    }
    SCHEDULE_DAYS.forEach((day) => {
      scheduleApplyEditorDayBlocks(day, [], { dirty: false });
    });
    setScheduleEditorDirty(true);
    const message = "Week cleared:";
    setText("schedule-editor-status", "Week cleared");
    setText("schedule-editor-result", `${scheduleEditorDraftSummaryText(message)}\nDraft is not saved. Use Preview Schedule before Save Schedule.`);
    renderScheduleDraftSummary(message);
  }

  function allowAllScheduleEditorWeek() {
    if (scheduleEditorBusy) return;
    if (typeof window.confirm === "function" && !window.confirm("Allow every day and time in the weekly schedule draft?\n\nThis only stages a draft. Use Preview Schedule and Save Schedule before backend app state changes.")) {
      return;
    }
    const allBlocks = Array.from({ length: SCHEDULE_BLOCKS_PER_DAY }, (_, index) => index);
    SCHEDULE_DAYS.forEach((day) => {
      scheduleApplyEditorDayBlocks(day, allBlocks, { dirty: false });
    });
    setScheduleEditorDirty(true);
    const message = "All week allowed:";
    setText("schedule-editor-status", "All week allowed");
    setText("schedule-editor-result", `${scheduleEditorDraftSummaryText(message)}\nDraft is not saved. Use Preview Schedule before Save Schedule.`);
    renderScheduleDraftSummary(message);
  }

  async function previewScheduleEditor() {
    if (scheduleEditorBusy) return;
    setText("schedule-editor-status", "Previewing");
    scheduleEditorPreviewSignature = "";
    setScheduleEditorBusy("preview");
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
    } finally {
      setScheduleEditorBusy("");
    }
  }

  async function saveScheduleEditor() {
    if (scheduleEditorBusy) return;
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
    setScheduleEditorBusy("save");
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
    } finally {
      setScheduleEditorBusy("");
    }
  }

  function initScheduleViewEvents() {
    initScheduleEditorDragEvents();
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

    return {
      scheduleBlockLabel,
      scheduleBlockRangeLabel,
      scheduleWindowsTextFromBlocks,
      scheduleDraftBlocksFromText,
      scheduleSetDayBlocks,
      scheduleEditorRequest,
      scheduleEditorResultLines,
      scheduleEditorDraftCoverageRow,
      renderScheduleDraftSummary,
      renderScheduleSavedScopeNotes,
      renderScheduleEditorImpact,
      renderScheduleEditorResult,
      renderScheduleEditor,
      loadCurrentScheduleIntoEditor,
      clearScheduleEditorWeek,
      allowAllScheduleEditorWeek,
      previewScheduleEditor,
      saveScheduleEditor,
      initScheduleViewEvents,    };
  }

  window.__scheduleEditorModule = {
    createScheduleEditorModule,
  };
})();
