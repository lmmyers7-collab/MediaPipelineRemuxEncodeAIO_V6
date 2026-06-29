/* global THEME_STORAGE_KEY, _layoutRenderDrawer, backendShutdownInFlight, commandHistoryCompactEvidenceLine, getCommandHistory, homeProgressPercent, lastCloseReadiness, lastSnapshot, lastStartupProgress, lastTauriBackendLifecycleEvent, refreshAll */
(function () {
  const TOPBAR_PENDING_LAUNCH_TTL_MS = 120000;
  const TOPBAR_IDLE_PENDING_GRACE_MS = 45000;
  const COMPLETED_TAB_STORAGE_KEY = "mediapipeline-completed-tab";
  const formatters = window.mediaPipelineFormatters || {};
  const formatProgressValue = typeof formatters.formatProgressValue === "function"
    ? formatters.formatProgressValue
    : (value) => {
        if (value === null || value === undefined) return "";
        if (Array.isArray(value)) return value.join(", ");
        if (value && typeof value === "object") return JSON.stringify(value);
        return String(value);
      };
  const scheduleView = window.mediaPipelineScheduleView || {};
  const scheduleDisplayValue = typeof scheduleView.scheduleDisplayValue === "function" ? scheduleView.scheduleDisplayValue : null;
  let topbarPendingLaunch = null;
  let uiQuickLinkEventsInitialized = false;

  function topbarPathLeaf(value) {
    const text = formatProgressValue(value || "").trim();
    if (!text) return "";
    return text.split(/[\\/]/).filter(Boolean).pop() || text;
  }

  function topbarCleanCurrentName(progress = {}, currentWork = {}) {
    return formatProgressValue(
      currentWork.item_label
        || progress.CurrentDisplayName
        || progress.CleanDisplayName
        || progress.CleanedName
        || progress.CurrentFileDisplay
        || "",
    ).trim();
  }

  function topbarStageContext(progress = {}) {
    const stage = formatProgressValue(progress.CurrentStage || progress.Status || "").trim();
    const percent = homeProgressPercent(progress.CurrentStagePercent);
    const route = formatProgressValue(progress.CurrentRoute || progress.Route || "").trim();
    return [
      stage,
      percent,
      route ? `Route ${route}` : "",
    ].filter(Boolean).join(" · ");
  }

  function topbarCurrentWorkMeta(currentWork = {}, progress = {}) {
    const library = formatProgressValue(currentWork.library_label || "").trim();
    const queue = formatProgressValue(currentWork.queue_label || "").trim();
    const queuePosition = formatProgressValue(currentWork.queue_position_label || "").trim();
    const route = formatProgressValue(currentWork.route_label || "").trim();
    const percent = formatProgressValue(currentWork.percent_label || "").trim() || homeProgressPercent(progress.CurrentStagePercent);
    const parts = [];
    if (library) parts.push(library);
    if (queue && queue.toLowerCase() !== library.toLowerCase()) parts.push(queue);
    if (queuePosition) parts.push(queuePosition);
    if (route) parts.push(route);
    if (percent) parts.push(percent);
    return parts.join(" · ");
  }

  function renderTopbarActivity(snapshot = {}) {
    const node = byId("activity");
    if (!node) return;
    const payload = snapshot && typeof snapshot === "object" ? snapshot : {};
    const progress = payload.progress && typeof payload.progress === "object" ? payload.progress : {};
    const currentWork = payload.current_work && typeof payload.current_work === "object" ? payload.current_work : {};
    const activity = formatProgressValue(payload.activity || "No active work reported.").trim();
    const cleanName = topbarCleanCurrentName(progress, currentWork);
    const phaseLabel = formatProgressValue(currentWork.phase_label || "").trim();
    const metaText = topbarCurrentWorkMeta(currentWork, progress) || topbarStageContext(progress);
    const primaryText = cleanName || activity || "No active work reported.";

    const primary = document.createElement("span");
    primary.className = "activity-primary";
    primary.textContent = primaryText;
    primary.title = primaryText;
    const meta = document.createElement("span");
    meta.className = "activity-meta";
    meta.textContent = metaText;
    if (metaText) meta.title = metaText;
    node.replaceChildren(primary, meta);
    node.title = [phaseLabel, primaryText, metaText].filter(Boolean).join("\n");
  }

  function topbarTickerCompactText(value, maxLength = 96) {
    const text = formatProgressValue(value || "").replace(/\s+/g, " ").trim();
    if (!text) return "";
    return text.length > maxLength ? `${text.slice(0, Math.max(0, maxLength - 1))}…` : text;
  }

  function topbarEventData(event = {}) {
    return event && typeof event.data === "object" && event.data && !Array.isArray(event.data) ? event.data : {};
  }

  function topbarEventTimestampMs(event = {}) {
    const value = event.timestamp || event.created_at || event.recorded_at || event.time || "";
    if (!value) return null;
    const parsed = Date.parse(String(value));
    return Number.isFinite(parsed) ? parsed : null;
  }

  function topbarLatestEvent(events) {
    const items = Array.isArray(events) ? events.filter(Boolean) : [];
    if (!items.length) return null;
    let latest = items[items.length - 1];
    let latestTimestamp = topbarEventTimestampMs(latest);
    items.forEach((item) => {
      const timestamp = topbarEventTimestampMs(item);
      if (timestamp !== null && (latestTimestamp === null || timestamp >= latestTimestamp)) {
        latest = item;
        latestTimestamp = timestamp;
      }
    });
    return latest;
  }

  function topbarEventKey(event) {
    if (!event || typeof event !== "object") return "";
    const data = topbarEventData(event);
    return [
      event.event_id,
      event.timestamp,
      event.created_at,
      event.event_type || event.type || event.kind,
      event.stage,
      event.route,
      event.status,
      event.source_path || data.source_path || data.local_file || data.input_file,
    ].map((value) => String(value || "").trim()).join("|");
  }

  function topbarEventDisplayName(event = {}) {
    const data = topbarEventData(event);
    return topbarPathLeaf(
      data.display_name
        || data.current_file
        || data.currentFile
        || data.source_path
        || data.local_file
        || data.input_file
        || event.source_path
        || event.SourcePath
        || "",
    );
  }

  function topbarEventTickerLine(event) {
    if (!event || typeof event !== "object") return "";
    const type = topbarTickerCompactText(event.event_type || event.type || event.kind || "event", 48);
    const stage = topbarTickerCompactText(event.stage || "", 44);
    const route = topbarTickerCompactText(event.route || "", 44);
    const status = topbarTickerCompactText(event.status || "", 44);
    const display = topbarTickerCompactText(topbarEventDisplayName(event), 96);
    const parts = [type, stage, route, status, display].filter(Boolean);
    return parts.length ? `Latest event: ${parts.join(" · ")}` : "Latest event: backend event received";
  }

  function topbarPendingLaunchLine(pending) {
    const pid = pending?.pid ? ` · PID ${pending.pid}` : "";
    return `Latest event: pipeline.start accepted${pid} · waiting for backend event`;
  }

  function topbarPipelineState(snapshot = {}) {
    return String(snapshot?.pipeline_state || snapshot?.progress?.Status || "").trim().toLowerCase();
  }

  function topbarPendingLaunchIsValid(snapshot = {}, latestEvent = null) {
    if (!topbarPendingLaunch) return false;
    const now = Date.now();
    if (now > Number(topbarPendingLaunch.expiresAt || 0)) {
      topbarPendingLaunch = null;
      return false;
    }
    const latestKey = topbarEventKey(latestEvent);
    if (latestKey && latestKey !== topbarPendingLaunch.baselineEventKey) {
      topbarPendingLaunch = null;
      return false;
    }
    const elapsed = now - Number(topbarPendingLaunch.acceptedAt || now);
    if (elapsed > TOPBAR_IDLE_PENDING_GRACE_MS && topbarPipelineState(snapshot) === "idle") {
      topbarPendingLaunch = null;
      return false;
    }
    return true;
  }

  function renderTopbarEventTicker(snapshot = {}) {
    const node = byId("topbar-event-ticker");
    if (!node) return;
    const payload = snapshot && typeof snapshot === "object" ? snapshot : {};
    const events = Array.isArray(payload.recent_events) ? payload.recent_events : [];
    const latestEvent = topbarLatestEvent(events);
    let text = "";
    let state = "empty";
    if (topbarPendingLaunchIsValid(payload, latestEvent)) {
      text = topbarPendingLaunchLine(topbarPendingLaunch);
      state = "pending";
    } else if (latestEvent) {
      text = topbarEventTickerLine(latestEvent);
      state = "event";
    } else {
      text = "Latest event: no backend pipeline events reported yet";
    }
    node.textContent = text;
    node.title = text;
    node.dataset.state = state;
  }

  function setTopbarPendingLaunch(payload = {}) {
    const latestEvent = topbarLatestEvent(Array.isArray(lastSnapshot?.recent_events) ? lastSnapshot.recent_events : []);
    const acceptedAt = Date.now();
    topbarPendingLaunch = {
      acceptedAt,
      baselineEventKey: topbarEventKey(latestEvent),
      expiresAt: acceptedAt + TOPBAR_PENDING_LAUNCH_TTL_MS,
      pid: topbarTickerCompactText(payload.pid || "", 24),
    };
    renderTopbarEventTicker(lastSnapshot || {});
  }

  function formatCloseReadiness(closeReadiness) {
    if (!closeReadiness) return "Close readiness has not loaded yet.";
    const warnings = Array.isArray(closeReadiness.warnings) ? closeReadiness.warnings : [];
    const watcher = closeReadinessWatcherData(closeReadiness);
    const lines = [
      `Safe to close: ${closeReadiness.safe_to_close ? "yes" : "no"}`,
      `State: ${closeReadiness.state || "unknown"}`,
      `Active work: ${closeReadiness.active_work ? "yes" : "no"}`,
      `Reason: ${closeReadiness.reason || "No reason reported."}`,
      `Continuous watcher: ${closeReadinessWatcherSummary(closeReadiness)}`,
    ];
    if (Object.keys(watcher).length) {
      lines.push(
        `Watcher generation: ${Number(watcher.generation || 0) > 0 ? watcher.generation : "none"}`,
        `Watcher stop requested: ${watcher.stop_requested ? "yes" : "no"}`,
        `Watcher message: ${watcher.message || "(not reported)"}`,
        `Watcher error: ${watcher.error || "none"}`
      );
    }
    if (warnings.length) {
      lines.push("", "Warnings:");
      warnings.forEach((warning) => lines.push(`- ${warning}`));
    }
    return lines.join("\n");
  }

  function closeReadinessWatcherData(closeReadiness = lastCloseReadiness) {
    return closeReadiness?.continuous_watcher && typeof closeReadiness.continuous_watcher === "object"
      ? closeReadiness.continuous_watcher
      : {};
  }

  function closeReadinessWatcherSummary(closeReadiness = lastCloseReadiness) {
    const watcher = closeReadinessWatcherData(closeReadiness);
    const status = String(watcher.status || "unknown");
    const pid = Number(watcher.pid || 0) > 0 ? ` for PID ${watcher.pid}` : "";
    const deadline = watcher.deadline ? ` until ${typeof scheduleDisplayValue === "function" ? scheduleDisplayValue(watcher.deadline) : watcher.deadline}` : "";
    return `${status}${pid}${deadline}`;
  }

  function closeReadinessWatcherIsArmed(closeReadiness = lastCloseReadiness) {
    return String(closeReadinessWatcherData(closeReadiness).status || "").toLowerCase() === "armed";
  }

  function backendLifecycleState(closeReadiness = lastCloseReadiness) {
    if (!closeReadiness) {
      return {
        label: "Waiting",
        state: "unknown",
        canShutdown: false,
        reason: "Close-readiness has not loaded yet.",
      };
    }
    if (closeReadiness.safe_to_close === true) {
      return {
        label: "Safe to request",
        state: "ready",
        canShutdown: true,
        reason: closeReadiness.reason || "Close-readiness reports that no active work is blocking backend shutdown.",
      };
    }
    if (closeReadinessWatcherIsArmed(closeReadiness)) {
      return {
        label: "Watcher armed",
        state: "blocked",
        canShutdown: false,
        reason: closeReadiness.reason || "Backend schedule-stop watcher is armed; keep the local backend running or use backend-owned stop controls first.",
      };
    }
    return {
      label: "Blocked",
      state: "blocked",
      canShutdown: false,
      reason: closeReadiness.reason || "Active work, stale runtime state, or unverifiable close-readiness is blocking shutdown.",
    };
  }

  function startupProgressLines(progress = lastStartupProgress) {
    const payload = progress && typeof progress === "object" ? progress : null;
    if (!payload || !Array.isArray(payload.steps)) {
      return ["Startup progress: not reported by backend bootstrap."];
    }
    const steps = payload.steps;
    const status = payload.status || "unknown";
    const completed = Number(payload.completed_steps || 0);
    const total = Number(payload.total_steps || steps.length || 0);
    const percent = Number(payload.percent);
    const summary = `Startup progress: ${status}; ${completed} / ${total} step${total === 1 ? "" : "s"}${Number.isFinite(percent) ? `; ${percent.toFixed(1)}%` : ""}`;
    const recent = steps.slice(-5).map((step) => {
      const detail = step.detail ? ` - ${step.detail}` : "";
      return `- ${step.label || step.id || "startup step"}: ${step.status || "unknown"}${detail}`;
    });
    return [summary, ...recent];
  }

  function normalizeTauriBackendLifecycleEvent(payload) {
    const source = payload && typeof payload === "object" && payload.payload && typeof payload.payload === "object"
      ? payload.payload
      : payload && typeof payload === "object"
        ? payload
        : {};
    return {
      schema_version: source.schema_version || "unknown",
      status: String(source.status || "unknown"),
      detail: String(source.detail || "No lifecycle detail was reported."),
      consecutive_failures: Number(source.consecutive_failures || 0),
      emitted_at_unix_seconds: Number(source.emitted_at_unix_seconds || 0),
    };
  }

  function tauriBackendLifecycleStatusLabel(status) {
    if (status === "backend_exited") return "Backend exited";
    if (status === "backend_health_failed") return "Backend health failed";
    if (status === "monitor_error") return "Lifecycle monitor error";
    return "Backend lifecycle warning";
  }

  function tauriBackendLifecycleLines(event = lastTauriBackendLifecycleEvent) {
    if (!event) return [];
    return [
      "",
      "Tauri lifecycle monitor:",
      `Status: ${tauriBackendLifecycleStatusLabel(event.status)} (${event.status})`,
      `Detail: ${event.detail}`,
      `Consecutive health failures: ${event.consecutive_failures}`,
      `Schema: ${event.schema_version}`,
      "Recovery: refresh once, then inspect Diagnostics run logs, close-readiness, ActiveJobs, and backend stderr before launching, draining, saving settings, renaming, publishing, or closing the shell.",
    ];
  }

  function renderTauriBackendLifecycleAlert(event = lastTauriBackendLifecycleEvent) {
    const topbar = document.querySelector(".topbar");
    if (!topbar || !event) return;
    let node = document.querySelector(".tauri-lifecycle-alert");
    if (!node) {
      node = document.createElement("div");
      node.className = "tauri-lifecycle-alert";
      node.setAttribute("role", "alert");
      topbar.insertAdjacentElement("afterend", node);
    }
    node.dataset.state = event.status === "backend_health_failed" ? "warning" : "blocked";
    const title = document.createElement("strong");
    title.textContent = tauriBackendLifecycleStatusLabel(event.status);
    const detail = document.createElement("span");
    detail.textContent = event.detail;
    const hint = document.createElement("span");
    hint.textContent = "Open Diagnostics before starting, draining, saving, renaming, publishing, or closing.";
    node.replaceChildren(title, detail, hint);
  }

  function pipelineControlReadinessStatus(snapshot, closeReadiness) {
    if (!snapshot) return "No snapshot";
    if (closeReadiness?.safe_to_close === false || closeReadiness?.active_work) return "Active controls";
    const state = String(snapshot.pipeline_state || closeReadiness?.state || "").toLowerCase();
    if (["processing", "running", "active", "publishing", "audit"].includes(state)) return "Active controls";
    if (["idle", "completed", "failed"].includes(state)) return "Idle";
    return "Review state";
  }

  function pipelineControlReadinessLines(snapshot, closeReadiness) {
    if (!snapshot) {
      return [
        "Snapshot: unavailable",
        "Control guidance: wait for snapshot refresh before sending pipeline controls.",
        "Mutation guardrail: control buttons send backend-owned control flags through /api/pipeline/control.",
      ];
    }
    const state = snapshot.pipeline_state || closeReadiness?.state || "unknown";
    const progress = snapshot.progress && typeof snapshot.progress === "object" ? snapshot.progress : {};
    const active = closeReadiness?.safe_to_close === false || closeReadiness?.active_work === true;
    const lines = [
      `Pipeline state: ${state}`,
      `Active work: ${active ? "yes" : "no"}`,
      `Close readiness: ${closeReadiness ? (closeReadiness.safe_to_close ? "safe" : "active/blocked") : "unknown"}`,
      progress.CurrentStage ? `Current backend stage: ${progress.CurrentStage}` : "",
      progress.Status ? `Progress status: ${progress.Status}` : "",
    ].filter(Boolean);
    if (closeReadiness?.reason) lines.push(`Close reason: ${closeReadiness.reason}`);
    lines.push("");
    if (active) {
      lines.push("Pause / Resume: meaningful while backend work is active.");
      lines.push("Rescan: request only when the running pipeline should refresh queue state.");
      lines.push("Stop After Current: request when current work should finish but no new item should start.");
    } else {
      lines.push("Pause / Resume: normally unnecessary while no active work is reported.");
      lines.push("Rescan: normally unnecessary while idle; refresh Queue or launch a fresh preview instead.");
      lines.push("Stop After Current: normally unnecessary while close-readiness reports safe.");
    }
    lines.push("Mutation guardrail: control buttons send backend-owned control flags through /api/pipeline/control and backend locks remain the source of truth.");
    return lines;
  }

  function renderControlReadiness(snapshot = lastSnapshot, closeReadiness = lastCloseReadiness) {
    setTextState("control-readiness-status", pipelineControlReadinessStatus(snapshot, closeReadiness));
    setTextState("home-control-readiness-status", pipelineControlReadinessStatus(snapshot, closeReadiness));
    setText("control-readiness", pipelineControlReadinessLines(snapshot, closeReadiness).join("\n"));
    window.mediaPipelineLaunchView?.updateLaunchCommandButtonStates?.(snapshot, closeReadiness);
  }

  function visiblePagePanel() {
    return document.querySelector(".page.is-visible[data-page-panel]");
  }
  void [visiblePagePanel];

  function panelVisibilityEmptyState(page) {
    let node = page.querySelector(':scope > [data-page-empty-state="panel-visibility"]');
    if (node) return node;

    node = document.createElement("section");
    node.className = "page-panel-empty-window";
    node.dataset.pageEmptyState = "panel-visibility";
    node.setAttribute("role", "status");
    node.setAttribute("aria-live", "polite");
    node.setAttribute("aria-hidden", "true");

    const title = document.createElement("strong");
    title.textContent = "No boxes are visible on this tab.";
    const detail = document.createElement("p");
    detail.className = "page-panel-empty-detail";
    detail.textContent = "Boxes may be hidden by Advanced, Evidence, or Customize settings.";

    const actions = document.createElement("div");
    actions.className = "inline-actions page-panel-empty-actions";
    const showEvidence = document.createElement("button");
    showEvidence.type = "button";
    showEvidence.className = "secondary-button";
    showEvidence.textContent = "Show Evidence";
    showEvidence.addEventListener("click", () => {
      if (document.body.classList.contains("evidence-hidden")) {
        byId("evidence-toggle")?.click();
      } else {
        updatePagePanelEmptyStates();
      }
    });
    const showAdvanced = document.createElement("button");
    showAdvanced.type = "button";
    showAdvanced.className = "secondary-button";
    showAdvanced.textContent = "Show Advanced";
    showAdvanced.addEventListener("click", () => {
      if (!document.body.classList.contains("advanced-mode")) {
        byId("advanced-toggle")?.click();
      } else {
        updatePagePanelEmptyStates();
      }
    });
    const customize = document.createElement("button");
    customize.type = "button";
    customize.className = "secondary-button";
    customize.textContent = "Customize";
    customize.addEventListener("click", () => {
      if (!document.body.classList.contains("layout-editor-open")) {
        byId("customize-layout-btn")?.click();
      } else {
        if (typeof _layoutRenderDrawer === "function") _layoutRenderDrawer({ preserveStatus: true });
        updatePagePanelEmptyStates();
      }
    });
    actions.append(showEvidence, showAdvanced, customize);
    node.append(title, detail, actions);
    page.appendChild(node);
    return node;
  }

  function panelIsCurrentlyVisible(panel) {
    return Boolean(panel.offsetWidth || panel.offsetHeight || panel.getClientRects().length);
  }

  function panelHiddenByAdvancedGate(panel) {
    if (document.body.classList.contains("advanced-mode")) return false;
    return panel.hasAttribute("data-panel-advanced") || panel.hasAttribute("data-advanced") || Boolean(panel.closest("[data-advanced]"));
  }

  function panelHiddenByEvidenceGate(panel) {
    if (!document.body.classList.contains("evidence-hidden")) return false;
    if (panel.dataset.evidenceToggleExempt === "true") return false;
    return panel.dataset.panelType === "evidence";
  }

  function pagePanelHiddenReasonLines(page, panels) {
    const reasons = [];
    if (panels.some(panelHiddenByAdvancedGate)) reasons.push("Advanced is off.");
    if (panels.some(panelHiddenByEvidenceGate)) reasons.push("Evidence is hidden.");
    if (panels.some((panel) => panel.hasAttribute("data-panel-hidden"))) reasons.push("Customize has hidden panel(s).");
    if (!reasons.length) reasons.push("A display filter is hiding this tab's panels.");
    return `Boxes may be hidden by ${reasons.join(" ")} Use the controls above to restore them.`;
  }

  function updatePagePanelEmptyState(page) {
    if (!page) return;
    const empty = panelVisibilityEmptyState(page);
    const panels = Array.from(page.querySelectorAll(".panel")).filter((panel) => !panel.closest("[data-page-empty-state]"));
    const hasVisiblePanel = panels.some(panelIsCurrentlyVisible);
    const shouldShow = page.classList.contains("is-visible") && panels.length > 0 && !hasVisiblePanel;
    empty.classList.toggle("is-visible", shouldShow);
    empty.setAttribute("aria-hidden", String(!shouldShow));
    if (shouldShow) {
      const detail = empty.querySelector(".page-panel-empty-detail");
      if (detail) detail.textContent = pagePanelHiddenReasonLines(page, panels);
    }
  }

  function updatePagePanelEmptyStates() {
    document.querySelectorAll(".page[data-page-panel]").forEach(updatePagePanelEmptyState);
  }

  function kebabCase(value) {
    return String(value || "").replace(/[A-Z]/g, (match) => `-${match.toLowerCase()}`);
  }

  function ensureElementId(element, prefix, suffix) {
    if (element.id) return element.id;
    const cleanPrefix = String(prefix || "tab").replace(/[^a-z0-9_-]+/gi, "-").toLowerCase();
    const cleanSuffix = String(suffix || "panel").replace(/[^a-z0-9_-]+/gi, "-").toLowerCase();
    element.id = `${cleanPrefix}-${cleanSuffix}`;
    return element.id;
  }

  function tabDatasetKey(button) {
    return Object.keys(button?.dataset || {}).find((key) => key.endsWith("Tab") && !key.endsWith("TabPanel")) || "";
  }

  function tabPanelDatasetKey(page, buttonKey) {
    const candidates = [`${buttonKey}Panel`, buttonKey];
    return candidates.find((key) => page.querySelector(`.settings-tab-pane[data-${kebabCase(key)}]`)) || "";
  }

  function syncTabAccessibility() {
    document.querySelectorAll('[role="tablist"]').forEach((tablist) => {
      const buttons = Array.from(tablist.querySelectorAll('[role="tab"]'));
      if (!buttons.length) return;
      const page = tablist.closest("[data-page-panel]") || document;
      const buttonKey = tabDatasetKey(buttons[0]);
      const panelKey = tabPanelDatasetKey(page, buttonKey);
      if (!buttonKey || !panelKey) return;
      const pageName = page.dataset?.pagePanel || "page";
      const panels = Array.from(page.querySelectorAll(`.settings-tab-pane[data-${kebabCase(panelKey)}]`));
      buttons.forEach((button) => {
        const tabValue = button.dataset[buttonKey] || "";
        const active = button.getAttribute("aria-selected") === "true";
        const buttonId = ensureElementId(button, `${pageName}-tab`, tabValue || "button");
        const controlledPanels = panels.filter((panel) => panel.dataset[panelKey] === tabValue);
        const panelIds = controlledPanels.map((panel, index) => ensureElementId(panel, `${pageName}-tabpanel-${tabValue || "pane"}`, String(index + 1)));
        if (panelIds.length) button.setAttribute("aria-controls", panelIds.join(" "));
        button.tabIndex = active ? 0 : -1;
        controlledPanels.forEach((panel) => {
          panel.setAttribute("role", "tabpanel");
          panel.setAttribute("aria-labelledby", buttonId);
          panel.hidden = !active;
        });
      });
      if (!tablist.dataset.tabKeyboardBound) {
        tablist.dataset.tabKeyboardBound = "true";
        tablist.addEventListener("keydown", (event) => {
          const current = event.target?.closest?.('[role="tab"]');
          if (!current || !tablist.contains(current)) return;
          const index = buttons.indexOf(current);
          if (index < 0) return;
          const lastIndex = buttons.length - 1;
          let nextIndex = -1;
          if (event.key === "ArrowRight" || event.key === "ArrowDown") nextIndex = index === lastIndex ? 0 : index + 1;
          if (event.key === "ArrowLeft" || event.key === "ArrowUp") nextIndex = index === 0 ? lastIndex : index - 1;
          if (event.key === "Home") nextIndex = 0;
          if (event.key === "End") nextIndex = lastIndex;
          if (nextIndex < 0) return;
          event.preventDefault();
          buttons[nextIndex].focus();
          buttons[nextIndex].click();
        });
        tablist.addEventListener("click", () => window.setTimeout(syncTabAccessibility, 0));
      }
    });
  }

  const resetWorkspaceScroll = function () {
    const workspace = document.querySelector(".workspace");
    if (workspace && typeof workspace.scrollTo === "function") {
      workspace.scrollTo(0, 0);
    }
    const scroller = document.scrollingElement || document.documentElement || document.body;
    if (scroller) {
      scroller.scrollTop = 0;
      scroller.scrollLeft = 0;
    }
    if (typeof window.scrollTo === "function") {
      window.scrollTo(0, 0);
    }
  };

  function showPage(page) {
    const normalized = String(page || "").trim();
    if (!normalized) return;
    const buttons = Array.from(document.querySelectorAll(".nav-button"));
    const panels = Array.from(document.querySelectorAll("[data-page-panel]"));
    const current = panels.find((panel) => panel.classList.contains("is-visible"))?.dataset.pagePanel || "";
    buttons.forEach((item) => {
      const active = item.dataset.page === normalized;
      item.classList.toggle("is-active", active);
      if (active) item.setAttribute("aria-current", "page");
      else item.removeAttribute("aria-current");
    });
    panels.forEach((panel) => panel.classList.toggle("is-visible", panel.dataset.pagePanel === normalized));
    if (current && current !== normalized) resetWorkspaceScroll();
    updatePagePanelEmptyStates();
    if (document.body.classList.contains("layout-editor-open")) _layoutRenderDrawer();
    const maintenanceView = window.mediaPipelineMaintenanceView || {};
    if (normalized === "maintenance" && typeof maintenanceView.hasMaintenanceLoaded === "function" && !maintenanceView.hasMaintenanceLoaded()) {
      maintenanceView.refreshMaintenance?.();
    }
  }

  function applyDefaultActionTooltips() {
    const tooltips = [
      ["#pipeline-start-button", "Start is disabled while active work is reported. Backend start routes re-check queue, schedule, settings, and process locks at submission time."],
      ["#home-refresh-button", "Refreshes dashboard state from backend snapshots without starting or mutating media work."],
      ["#rerun-plan-only-button", "Reads CSV rerun summary, scope, recent CSVs, and preview rows through the backend without launching work or writing scoped CSVs."],
      ["#rerun-dry-run-button", "Previews backend CSV rerun as a dry run. Review dry-run evidence before starting a live copy / keep / park rerun."],
      ["#rerun-start-button", "Starts backend CSV rerun with copy / keep / park policy. Review the CSV path and preflight before starting."],
      ["#rerun-open-audit-tool-button", "Opens Reports > Audit for audit rows, score policy, and backend-owned rerun CSV export controls."],
      ["#pending-drain-button", "Requests backend pending-publish drain. Drain safety remains backend-owned and requires parked payload evidence."],
      ['[data-control-action="pause"]', "Pause or resume the active backend pipeline. Disabled while no active work is reported."],
      ['[data-control-action="rescan"]', "Request a backend queue rescan flag for the running pipeline. Disabled while no active work is reported."],
      ['[data-control-action="stop"]', "Request graceful Stop After Current. The current file may finish; no new item should start."],
      ['[data-control-action="kill"]', "Emergency force stop. Requires confirmation and asks the backend to terminate related pipeline, audit, and CSV rerun process trees."],
      ["#backend-shutdown-button", "Request backend shutdown only when close-readiness reports safe."],
      ["#maintenance-refresh-button", "Runs backend maintenance probes. Tool checks can take several seconds on portable bundles."],
      ["#release-dry-run-button", "Plans a deployment package without writing files. Review dry-run evidence before creating a deployment."],
      ["#release-build-button", "Creates a deployment package through the backend release builder after confirmation."],
      ["#backfill-dry-run-button", "Dry-run completed-manifest backfill. No manifest writes should occur during dry-run."],
      ["#dependency-atlas-button", "Regenerates dependency atlas HTML, images, and CSV exports through backend tooling."],
      ["#completed-refresh-current-output-button", "Rereads completed history and rechecks destination existence. It does not accept, delete, rerun, publish, drain, or move media."],
      ['[data-home-promotion-entry]', "Opens Completed Output when Final Library Promotion has reviewed files ready for delivery."],
      ['[data-completed-promote-selected]', "Promotes the selected reviewed file through the backend after confirmation. It never sends raw filesystem paths."],
      ["#diagnostics-tail-refresh-button", "Reads a bounded backend-allowlisted log tail. It cannot open arbitrary paths."],
      ["#sample-validation-append-button", "Appends backend-authored sample validation evidence only after preview/review. It does not accept output or publish media."],
      ["#sample-validation-preview-button", "Previews the sample validation record before any append."],
      ["#rename-apply-selected-button", "Submits selected rename rows to the backend transaction. Blocked rows cannot be applied."],
      ["#rename-preview-button", "Builds a backend rename preview. It does not rename files."],
      ["#rename-preview-top-button", "Builds a backend rename preview. It does not rename files."],
      ["#rename-use-selected-queue-button", "Copies the selected Queue source path into Rename paths. It does not rename files."],
      ["#rename-use-loaded-queue-button", "Copies loaded Queue source paths into Rename paths. It does not rename files."],
      ["#rename-browse-files-button", "Opens the Windows file browser and stages selected paths. It does not preview or rename files."],
      ["#rename-browse-folder-button", "Opens the Windows folder browser and stages the selected folder path. It does not preview or rename files."],
      ["#rename-add-path-button", "Adds the typed source path to Rename paths. It does not inspect or rename files."],
      ["#rename-clear-paths-button", "Clears staged Rename paths and preview rows. It does not touch source files."],
      ["#settings-network-apply-button", "Stages standalone/coordinator/worker settings into the shared Settings patch JSON. It does not start or stop workers."],
      ["#settings-network-reset-button", "Reloads the Network Workers tab mode controls from current saved backend settings."],
      ["#network-settings-preview-button", "Previews staged Distributed Mode Settings through the backend settings route. It does not save the PSD1."],
      ["#network-settings-save-button", "Saves staged Distributed Mode Settings through backend validation and config backup. It does not start or stop workers."],
      ["#settings-library-add-button", "Adds a new editable library profile tab. It does not scan, move, publish, promote, or delete media files."],
      ["#settings-library-delete-button", "Deletes the selected custom library profile from the staged editor only. Save Library Profile is required before config changes persist."],
      ["#settings-library-defaults-button", "Clears all Editor, Video/Media, Subtitle, and Audio overrides for the selected library."],
      ["#settings-library-build-patch-button", "Stages LibraryProfiles into the shared Settings patch JSON. It does not scan, move, publish, promote, or delete media files."],
      ["#settings-library-preview-button", "Previews staged LibraryProfiles through backend settings validation without saving the PSD1."],
      ["#settings-library-save-button", "Saves the selected Library Profile state through backend validation and config backup. It does not scan, move, publish, promote, or delete media files."],
      ["#settings-library-reset-button", "Reloads library cards from current saved backend settings."],
      ['[data-settings-path-key]', "Opens a backend-owned Windows folder picker and stages this Settings field. It does not save the PSD1 or touch media files."],
      ['[data-path-picker-target]', "Opens a backend-owned Windows picker and stages this path field only. It does not save settings, launch work, or touch media files."],
      ["#settings-save-patch-button", "Saves staged settings through backend validation. Raw WebView fields never write directly to the PSD1."],
    ];
    tooltips.forEach(([selector, title]) => {
      document.querySelectorAll(selector).forEach((node) => {
        if (!node.title) node.title = title;
      });
    });
  }

  function initSettingsTabNav() {
    const STORAGE_KEY = "mediapipeline-settings-section";
    const LEGACY_STORAGE_KEY = "mediapipeline-settings-tab";
    const page = document.querySelector('[data-page-panel="settings"]');
    if (!page) return;
    const btns = Array.from(page.querySelectorAll(".settings-section-nav-btn[data-settings-tab]"));
    const panes = Array.from(page.querySelectorAll(".settings-tab-pane[data-settings-tab]"));
    if (!btns.length || !panes.length) return;

    function activateSection(tabId) {
      btns.forEach((b) => {
        const active = b.dataset.settingsTab === tabId;
        if (active) b.setAttribute("aria-current", "location");
        else b.removeAttribute("aria-current");
      });
      panes.forEach((p) => {
        p.classList.toggle("is-active", p.dataset.settingsTab === tabId);
      });
      try { localStorage.setItem(STORAGE_KEY, tabId); } catch (_) {}
      updatePagePanelEmptyStates();
    }

    btns.forEach((btn) => {
      btn.addEventListener("click", () => activateSection(btn.dataset.settingsTab));
    });

    let stored = "status";
    try { stored = localStorage.getItem(STORAGE_KEY) || localStorage.getItem(LEGACY_STORAGE_KEY) || "status"; } catch (_) {}
    // Validate stored value is a real section, fall back to status.
    if (!btns.some((b) => b.dataset.settingsTab === stored)) stored = "status";
    activateSection(stored);
  }

  function activateDiagnosticsTab(tabId) {
    const STORAGE_KEY = "mediapipeline-diag-tab";
    const page = document.querySelector('[data-page-panel="diagnostics"]');
    if (!page) return false;
    const btns = Array.from(page.querySelectorAll(".settings-tab-btn[data-diag-tab]"));
    const panes = Array.from(page.querySelectorAll(".settings-tab-pane[data-diag-tab]"));
    if (!btns.length || !panes.length) return false;

    let selected = String(tabId || "triage").trim();
    if (!btns.some((b) => b.dataset.diagTab === selected)) selected = "triage";
    btns.forEach((b) => {
      const active = b.dataset.diagTab === selected;
      b.setAttribute("aria-selected", String(active));
    });
    panes.forEach((p) => {
      p.classList.toggle("is-active", p.dataset.diagTab === selected);
    });
    try { localStorage.setItem(STORAGE_KEY, selected); } catch (_) {}
    syncTabAccessibility();
    updatePagePanelEmptyStates();
    return true;
  }

  function initDiagnosticsTabNav() {
    const STORAGE_KEY = "mediapipeline-diag-tab";
    const page = document.querySelector('[data-page-panel="diagnostics"]');
    if (!page) return;
    const btns = Array.from(page.querySelectorAll(".settings-tab-btn[data-diag-tab]"));
    const panes = Array.from(page.querySelectorAll(".settings-tab-pane[data-diag-tab]"));
    if (!btns.length || !panes.length) return;

    btns.forEach((btn) => {
      btn.addEventListener("click", () => activateDiagnosticsTab(btn.dataset.diagTab));
    });

    let stored = "triage";
    try { stored = localStorage.getItem(STORAGE_KEY) || "triage"; } catch (_) {}
    // Validate stored value is a real tab, fall back to Overview.
    if (!btns.some((b) => b.dataset.diagTab === stored)) stored = "triage";
    activateDiagnosticsTab(stored);
  }

  function activateCompletedTab(tabId) {
    const page = document.querySelector('[data-page-panel="completed"]');
    if (!page) return false;
    const btns = Array.from(page.querySelectorAll(".settings-tab-btn[data-completed-tab]"));
    const panes = Array.from(page.querySelectorAll(".settings-tab-pane[data-completed-tab]"));
    if (!btns.length || !panes.length) return false;

    let normalized = String(tabId || "overview").trim() || "overview";
    if (normalized === "advanced" || normalized === "proof") normalized = "evidence";
    if (!btns.some((b) => b.dataset.completedTab === normalized)) normalized = "overview";
    btns.forEach((b) => {
      const active = b.dataset.completedTab === normalized;
      b.setAttribute("aria-selected", String(active));
    });
    panes.forEach((p) => {
      p.classList.toggle("is-active", p.dataset.completedTab === normalized);
    });
    try { localStorage.setItem(COMPLETED_TAB_STORAGE_KEY, normalized); } catch (_) {}
    syncTabAccessibility();
    updatePagePanelEmptyStates();
    return true;
  }

  function showCompletedOutputTab(tabId) {
    activateCompletedTab(tabId);
    showPage("completed");
  }

  function activateCrossPageTarget(button) {
    const target = button?.dataset?.crossPageTarget || "";
    if (!target) return;
    showPage(target);
    if (target === "reports" && button.dataset.crossPageReportsTab) {
      const reportsView = window.mediaPipelineReportsView || {};
      reportsView.activateReportsTab?.(button.dataset.crossPageReportsTab);
    }
  }

  function focusUiQuickLinkTarget(selector) {
    const target = selector ? document.querySelector(selector) : null;
    if (!target) return false;
    if (typeof target.scrollIntoView === "function") {
      target.scrollIntoView({ block: "center", inline: "nearest" });
    }
    const focusable = typeof target.matches === "function"
      && target.matches("a[href], button, input, select, textarea, summary, [tabindex]");
    if (!focusable && typeof target.setAttribute === "function") target.setAttribute("tabindex", "-1");
    if (typeof target.focus === "function") target.focus({ preventScroll: true });
    return true;
  }

  function activateUiQuickLinkModule(moduleName, action, trigger) {
    const modules = {
      completed: window.mediaPipelineCompletedView,
      pending: window.mediaPipelinePendingPublishView,
      reports: window.mediaPipelineReportsView,
      network: window.mediaPipelineNetworkView,
      maintenance: window.mediaPipelineMaintenanceView,
      schedule: window.mediaPipelineScheduleView,
    };
    const module = modules[String(moduleName || "").trim().toLowerCase()];
    if (!module || typeof module.activateQuickLink !== "function") return false;
    return module.activateQuickLink(action, trigger) !== false;
  }

  function activateUiQuickLink(trigger) {
    const dataset = trigger?.dataset || {};
    const page = String(dataset.quickLinkPage || "").trim();
    if (page) showPage(page);
    if (dataset.quickLinkReportsTab) {
      window.mediaPipelineReportsView?.activateReportsTab?.(dataset.quickLinkReportsTab);
    }
    if (dataset.quickLinkDiagTab) activateDiagnosticsTab(dataset.quickLinkDiagTab);
    if (dataset.quickLinkMetricsTab) {
      window.mediaPipelineMetricsView?.activateMetricsTab?.(dataset.quickLinkMetricsTab);
    }
    if (dataset.quickLinkLaunchTab) {
      window.mediaPipelineLaunchView?.activateLaunchTab?.(dataset.quickLinkLaunchTab);
    }
    if (dataset.quickLinkCompletedTab) activateCompletedTab(dataset.quickLinkCompletedTab);
    if (dataset.quickLinkModule || dataset.quickLinkAction) {
      activateUiQuickLinkModule(dataset.quickLinkModule, dataset.quickLinkAction, trigger);
    }
    if (dataset.quickLinkFocus) {
      window.setTimeout(() => focusUiQuickLinkTarget(dataset.quickLinkFocus), 0);
    }
  }

  function initUiQuickLinks() {
    if (uiQuickLinkEventsInitialized) return;
    uiQuickLinkEventsInitialized = true;
    document.addEventListener("click", (event) => {
      const trigger = event.target?.closest?.("[data-ui-quick-link]");
      if (!trigger) return;
      event.preventDefault();
      activateUiQuickLink(trigger);
    });
    document.addEventListener("keydown", (event) => {
      if (event.key !== "Enter" && event.key !== " ") return;
      const trigger = event.target?.closest?.("[data-ui-quick-link]");
      if (!trigger) return;
      event.preventDefault();
      activateUiQuickLink(trigger);
    });
  }

  function initCompletedTabNav() {
    const page = document.querySelector('[data-page-panel="completed"]');
    if (!page) return;
    const btns = Array.from(page.querySelectorAll(".settings-tab-btn[data-completed-tab]"));
    const panes = Array.from(page.querySelectorAll(".settings-tab-pane[data-completed-tab]"));
    if (!btns.length || !panes.length) return;

    btns.forEach((btn) => {
      btn.addEventListener("click", () => activateCompletedTab(btn.dataset.completedTab));
    });

    let stored = "overview";
    try { stored = localStorage.getItem(COMPLETED_TAB_STORAGE_KEY) || "overview"; } catch (_) {}
    activateCompletedTab(stored);
  }

  function initNavigation() {
    const buttons = Array.from(document.querySelectorAll(".nav-button"));
    buttons.forEach((button) => {
      button.addEventListener("click", () => {
        showPage(button.dataset.page);
      });
    });
    document.querySelectorAll("[data-cross-page-target]").forEach((button) => {
      button.addEventListener("click", () => activateCrossPageTarget(button));
    });
    initUiQuickLinks();
    syncTabAccessibility();
    // S15: topbar health/readiness buttons navigate to Diagnostics.
    const refreshHealthBadge = byId("refresh-health");
    if (refreshHealthBadge) refreshHealthBadge.addEventListener("click", () => showPage("diagnostics"));
    const closeReadinessBadge = byId("close-readiness");
    if (closeReadinessBadge) closeReadinessBadge.addEventListener("click", () => showPage("diagnostics"));
  }

  function sparkKind(event) {
    const t = String(event.event_type || event.type || event.Status || event.status || event || "").toLowerCase();
    if (/complet|done|accept|success|ok\b|publish|pass/.test(t))       return "success";
    if (/process|encod|remux|copy|audit|running|active|launch/.test(t)) return "active";
    if (/fail|error|block|reject/.test(t))                             return "failed";
    if (/pause|stop|skip|stale|warn|unknown/.test(t))                  return "warning";
    return "skip";
  }

  function renderSparkline(events) {
    const el = byId("pipeline-sparkline");
    if (!el) return;
    const items = Array.isArray(events) ? events.slice(-20) : [];
    if (!items.length) { el.replaceChildren(); return; }
    el.replaceChildren();
    items.forEach((ev) => {
      const sq = document.createElement("span");
      sq.className = "spark";
      sq.dataset.kind = sparkKind(ev);
      sq.title = String(ev.event_type || ev.type || "event");
      el.appendChild(sq);
    });
  }

  function initLaunchEvidenceToggle() {
    const STORAGE_KEY = "mediapipeline-launch-evidence-expanded";
    const body = byId("launch-evidence-body");
    const btn  = byId("launch-evidence-toggle");
    if (!body || !btn) return;

    function applyCollapsed(collapsed) {
      body.classList.toggle("is-collapsed", collapsed);
      btn.textContent = collapsed ? "Expand" : "Collapse";
      btn.setAttribute("aria-expanded", String(!collapsed));
      try { localStorage.setItem(STORAGE_KEY, collapsed ? "0" : "1"); } catch (_) {}
    }

    // Restore persisted preference (default: expanded)
    let stored = true;
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw !== null) stored = raw === "1";
    } catch (_) {}
    applyCollapsed(!stored);

    btn.addEventListener("click", () => applyCollapsed(!body.classList.contains("is-collapsed")));
  }

  function initCollapsibleSummaries() {
    document.querySelectorAll("pre.prose-block").forEach((pre) => {
      const next = pre.nextElementSibling;
      if (!next || !next.classList.contains("table-wrap")) return;

      const id = pre.id || "";
      const STORAGE_KEY = id ? `mediapipeline-summary-${id}` : null;

      // Default: collapsed (table first). Restore to expanded only if stored as "1".
      let isExpanded = false;
      if (STORAGE_KEY) {
        try {
          const raw = localStorage.getItem(STORAGE_KEY);
          if (raw === "1") isExpanded = true;
        } catch (_) {}
      }

      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "tertiary-button summary-toggle";
      if (id) btn.setAttribute("aria-controls", id);

      function applyState(expanded) {
        isExpanded = expanded;
        pre.hidden = !expanded;
        btn.textContent = expanded ? "Hide summary" : "Show summary";
        btn.setAttribute("aria-expanded", String(expanded));
        if (STORAGE_KEY) {
          try { localStorage.setItem(STORAGE_KEY, expanded ? "1" : "0"); } catch (_) {}
        }
      }

      btn.addEventListener("click", () => applyState(!isExpanded));
      pre.parentNode.insertBefore(btn, pre);
      applyState(isExpanded);
    });
  }

  function initThemeToggle() {
    applyThemePreference(false);
  }

  function applyThemePreference(_light) {
    const btn = byId("theme-toggle");
    if (btn && typeof btn.remove === "function") btn.remove();
    document.body.classList.remove("light-mode");
    try { localStorage.setItem(THEME_STORAGE_KEY, "dark"); } catch (_) {}
    window.mediaPipelineTelemetryView?.redrawTelemetryCharts?.();
  }

  function lifecycleDisplayText(value, fallback = "Unknown") {
    const text = formatProgressValue(value || "").trim();
    return text || fallback;
  }

  function lifecycleStateToken(value) {
    const state = String(value || "").trim().toLowerCase();
    if (["ready", "safe", "ok", "success", "completed"].includes(state)) return "ready";
    if (["blocked", "error", "failed", "danger"].includes(state)) return "blocked";
    if (["warning", "review", "stale", "unknown"].includes(state)) return "warning";
    if (["changed", "running", "requesting", "queued", "pending"].includes(state)) return "changed";
    return "unknown";
  }

  function lifecycleFactNode(label, value, state = "unknown") {
    const node = document.createElement("div");
    node.className = "lifecycle-fact";
    node.dataset.state = lifecycleStateToken(state);
    const term = document.createElement("dt");
    term.textContent = label;
    const detail = document.createElement("dd");
    detail.textContent = lifecycleDisplayText(value);
    node.appendChild(term);
    node.appendChild(detail);
    return node;
  }

  function renderLifecycleFacts(id, facts = []) {
    const node = byId(id);
    if (!node) return;
    node.replaceChildren(...facts.map((fact) => lifecycleFactNode(fact.label, fact.value, fact.state)));
  }

  function renderLifecycleCallout(id, state, title, detail) {
    const node = byId(id);
    if (!node) return;
    node.dataset.state = lifecycleStateToken(state);
    const heading = document.createElement("strong");
    heading.textContent = lifecycleDisplayText(title);
    const body = document.createElement("span");
    body.textContent = lifecycleDisplayText(detail, "No detail reported.");
    node.replaceChildren(heading, body);
  }

  function lifecycleWatcherStatus(closeReadiness) {
    const watcher = closeReadinessWatcherData(closeReadiness);
    return lifecycleDisplayText(watcher.status, closeReadiness ? "Unknown" : "Not loaded");
  }

  function lifecycleStopRequestedText(closeReadiness) {
    if (!closeReadiness) return "Unknown";
    const watcher = closeReadinessWatcherData(closeReadiness);
    if (!Object.keys(watcher).length) return "No watcher";
    return watcher.stop_requested ? "Yes" : "No";
  }

  function lifecycleGenerationText(closeReadiness) {
    if (!closeReadiness) return "Unknown";
    const watcher = closeReadinessWatcherData(closeReadiness);
    const generation = Number(watcher.generation || 0);
    return generation > 0 ? String(watcher.generation) : "None";
  }

  function lifecycleCloseReadinessLabel(closeReadiness) {
    if (!closeReadiness) return "Not loaded";
    return closeReadiness.safe_to_close ? "Safe" : "Blocked";
  }

  function renderDiagnosticsCloseReadinessOverview(closeReadiness = lastCloseReadiness) {
    const watcher = closeReadinessWatcherData(closeReadiness);
    const state = lifecycleDisplayText(closeReadiness?.state, closeReadiness ? "Unknown" : "Not loaded");
    const safe = closeReadiness?.safe_to_close === true;
    const blocked = closeReadiness?.safe_to_close === false;
    const watcherArmed = closeReadinessWatcherIsArmed(closeReadiness);
    let calloutState = "unknown";
    let title = "Close readiness has not loaded.";
    let detail = "Refresh Diagnostics before treating shutdown as safe.";

    if (safe) {
      calloutState = "ready";
      title = "Close readiness is safe.";
      detail = closeReadiness.reason || "No active backend work is blocking shutdown.";
    } else if (watcherArmed) {
      calloutState = "blocked";
      title = "Close blocked: schedule watcher armed.";
      detail = closeReadiness.reason || "Keep the backend alive until the schedule boundary requests Stop, or use backend-owned stop controls first.";
    } else if (blocked) {
      calloutState = "blocked";
      title = `Close blocked: ${state}.`;
      detail = closeReadiness.reason || "Active work, stale runtime state, or unverifiable close-readiness is blocking shutdown.";
    }

    renderLifecycleCallout("diagnostics-close-readiness-overview", calloutState, title, detail);
    renderLifecycleFacts("diagnostics-close-readiness-facts", [
      { label: "Safe to close", value: safe ? "Yes" : blocked ? "No" : "Unknown", state: safe ? "ready" : blocked ? "blocked" : "unknown" },
      { label: "State", value: state, state: blocked ? "blocked" : safe ? "ready" : "unknown" },
      { label: "Active work", value: closeReadiness ? closeReadiness.active_work ? "Yes" : "No" : "Unknown", state: closeReadiness?.active_work ? "blocked" : safe ? "ready" : "unknown" },
      { label: "Watcher", value: closeReadiness ? closeReadinessWatcherSummary(closeReadiness) : "Not loaded", state: watcherArmed ? "blocked" : safe ? "ready" : "unknown" },
      { label: "Stop requested", value: lifecycleStopRequestedText(closeReadiness), state: watcher.stop_requested ? "ready" : watcherArmed ? "blocked" : "unknown" },
      { label: "Reason", value: closeReadiness?.reason || "No reason reported.", state: blocked ? "blocked" : safe ? "ready" : "unknown" },
    ]);
  }

  function renderBackendLifecycleOverview(lifecycle, closeReadiness, snapshot, warnings, watcher) {
    const state = backendShutdownInFlight ? "changed" : lifecycle.state;
    const pipelineState = lifecycleDisplayText(snapshot?.pipeline_state || closeReadiness?.state);
    let title = "Backend lifecycle has not loaded.";
    let detail = "Refresh Diagnostics before requesting backend shutdown.";

    if (backendShutdownInFlight) {
      title = "Backend shutdown request is in progress.";
      detail = "The Local API command is running; wait for the backend-owned result before retrying.";
    } else if (lifecycle.canShutdown) {
      title = "Backend shutdown can be requested.";
      detail = "Close-readiness reports safe. Use this only when you are done with the WebView/local backend session.";
    } else if (closeReadinessWatcherIsArmed(closeReadiness)) {
      title = "Backend shutdown blocked: watcher armed.";
      detail = lifecycle.reason;
    } else if (closeReadiness) {
      title = "Backend shutdown blocked.";
      detail = lifecycle.reason;
    }

    renderLifecycleCallout("backend-lifecycle-callout", state, title, detail);
    renderLifecycleFacts("backend-lifecycle-facts", [
      { label: "Request status", value: backendShutdownInFlight ? "Requesting" : lifecycle.label, state },
      { label: "Close-readiness", value: lifecycleCloseReadinessLabel(closeReadiness), state: closeReadiness?.safe_to_close ? "ready" : closeReadiness ? "blocked" : "unknown" },
      { label: "Pipeline state", value: pipelineState, state: closeReadiness?.safe_to_close ? "ready" : closeReadiness ? "blocked" : "unknown" },
      { label: "Watcher", value: lifecycleWatcherStatus(closeReadiness), state: closeReadinessWatcherIsArmed(closeReadiness) ? "blocked" : closeReadiness?.safe_to_close ? "ready" : "unknown" },
      { label: "Stop requested", value: lifecycleStopRequestedText(closeReadiness), state: watcher.stop_requested ? "ready" : closeReadinessWatcherIsArmed(closeReadiness) ? "blocked" : "unknown" },
      { label: "Generation", value: lifecycleGenerationText(closeReadiness), state: Number(watcher.generation || 0) > 0 ? "changed" : "unknown" },
      { label: "Warnings", value: warnings.length ? String(warnings.length) : "None", state: warnings.length ? "warning" : "ready" },
    ]);
  }

  function backendLifecycleCommandData(entry) {
    const raw = entry?.raw && typeof entry.raw === "object" ? entry.raw : {};
    const data = raw.data && typeof raw.data === "object" ? raw.data : {};
    const request = raw.request && typeof raw.request === "object"
      ? raw.request
      : raw.submitted_request && typeof raw.submitted_request === "object"
        ? raw.submitted_request
        : {};
    return { raw, data, request };
  }

  function backendLifecycleCommandResultLabel(entry) {
    const { raw } = backendLifecycleCommandData(entry);
    const severity = String(entry?.severity || raw.severity || "").trim().toLowerCase();
    const result = String(entry?.result || raw.result || "").trim();
    const ok = entry?.ok ?? raw.ok;
    if (ok === true && severity === "warning") return "OK with warning";
    if (ok === true) return "OK";
    if (ok === false && severity === "warning") return "Warning";
    if (ok === false) return "Error";
    return result || severity || "Unknown";
  }

  function backendLifecycleCommandResultState(entry) {
    const label = backendLifecycleCommandResultLabel(entry).toLowerCase();
    if (label.includes("warning")) return "warning";
    if (label.includes("error") || label.includes("blocked") || label.includes("failed")) return "error";
    if (label === "ok" || label.includes("success")) return "ready";
    return "unknown";
  }

  function backendLifecycleCommandTime(entry) {
    const { raw } = backendLifecycleCommandData(entry);
    return lifecycleDisplayText(entry?.at || raw.at || entry?.time || raw.time || raw.timestamp || raw.recorded_at, "Unknown");
  }

  function backendLifecycleCommandSummary(entry) {
    const { raw, data, request } = backendLifecycleCommandData(entry);
    const bits = [];
    if (data.safe_to_close !== undefined) bits.push(`safe_to_close=${data.safe_to_close ? "yes" : "no"}`);
    if (data.state) bits.push(`state=${data.state}`);
    if (data.reason) bits.push(`close_reason=${data.reason}`);
    if (data.continuous_watcher && typeof data.continuous_watcher === "object" && data.continuous_watcher.status) {
      const watcherBits = [`watcher=${data.continuous_watcher.status}`];
      if (data.continuous_watcher.pid) watcherBits.push(`pid=${data.continuous_watcher.pid}`);
      if (data.continuous_watcher.deadline) watcherBits.push(`deadline=${data.continuous_watcher.deadline}`);
      bits.push(watcherBits.join(" "));
    }
    if (request.reason) bits.push(`reason=${request.reason}`);
    const message = String(entry?.message || raw.message || "").trim() || "No command message reported.";
    return bits.length ? `${message} (${bits.join("; ")})` : message;
  }

  function appendLifecycleTableCell(row, child, className = "") {
    const cell = document.createElement("td");
    if (className) cell.className = className;
    if (child && typeof child === "object" && typeof child.nodeType === "number") cell.append(child);
    else cell.textContent = lifecycleDisplayText(child);
    row.appendChild(cell);
    return cell;
  }

  function lifecycleResultChip(entry) {
    const chip = document.createElement("span");
    chip.className = "status-chip lifecycle-result-chip";
    chip.dataset.status = backendLifecycleCommandResultState(entry);
    chip.textContent = backendLifecycleCommandResultLabel(entry);
    return chip;
  }

  function renderBackendLifecycleHistoryRows(entries = []) {
    const body = byId("backend-lifecycle-history-rows");
    if (!body) return;
    if (!entries.length) {
      const row = document.createElement("tr");
      const cell = document.createElement("td");
      cell.colSpan = 4;
      cell.textContent = "No backend shutdown command history loaded.";
      row.appendChild(cell);
      body.replaceChildren(row);
      return;
    }
    const rows = entries.map((entry) => {
      const row = document.createElement("tr");
      appendLifecycleTableCell(row, backendLifecycleCommandTime(entry), "lifecycle-history-time");
      appendLifecycleTableCell(row, lifecycleResultChip(entry), "lifecycle-history-result");
      appendLifecycleTableCell(row, "backend.shutdown", "lifecycle-history-command");
      appendLifecycleTableCell(row, backendLifecycleCommandSummary(entry), "lifecycle-history-summary");
      return row;
    });
    body.replaceChildren(...rows);
  }

  function renderBackendLifecycle(closeReadiness = lastCloseReadiness, snapshot = lastSnapshot) {
    const lifecycle = backendLifecycleState(closeReadiness);
    const status = byId("backend-lifecycle-status");
    if (status) {
      status.textContent = backendShutdownInFlight ? "Requesting" : lifecycle.label;
      status.dataset.state = backendShutdownInFlight ? "changed" : lifecycle.state;
    }
    const warnings = Array.isArray(closeReadiness?.warnings) ? closeReadiness.warnings : [];
    const watcher = closeReadinessWatcherData(closeReadiness);
    renderDiagnosticsCloseReadinessOverview(closeReadiness);
    renderBackendLifecycleOverview(lifecycle, closeReadiness, snapshot, warnings, watcher);
    const lines = ["Backend lifecycle handoff:", `Request status: ${backendShutdownInFlight ? "shutdown command in progress" : lifecycle.label}`, `Close-readiness: ${closeReadiness ? closeReadiness.safe_to_close ? "safe" : "blocked" : "not loaded"}`, `Pipeline state: ${snapshot?.pipeline_state || closeReadiness?.state || "unknown"}`, `Reason: ${lifecycle.reason}`, `Continuous watcher: ${closeReadinessWatcherSummary(closeReadiness)}`, `Watcher generation: ${Number(watcher.generation || 0) > 0 ? watcher.generation : "none"}`, `Watcher stop requested: ${watcher.stop_requested ? "yes" : "no"}`, `Warnings: ${warnings.length ? warnings.slice(0, 5).join(" | ") : "none"}`, "", ...startupProgressLines(), ...tauriBackendLifecycleLines(), "", "Guardrail: WebView exposes backend shutdown only when the loaded close-readiness payload reports safe.", "Backend authority: /api/backend/shutdown remains token-protected and performs the actual lifecycle request.", "Scope: this does not launch, pause, stop media, drain pending publish, rename files, save settings, delete files, or touch source/output/scratch media."];
    if (!lifecycle.canShutdown) {
      lines.push("Next step: inspect Close Readiness, ActiveJobs, Progress, Run Logs, and Last Stderr before closing or retrying lifecycle actions.");
      if (closeReadinessWatcherIsArmed(closeReadiness)) {
        lines.push("Watcher note: keep the backend alive until the schedule boundary requests Stop, or use backend-owned Stop After Current before shutting down.");
      }
    } else {
      lines.push("Next step: use this only when you are done with the WebView/local backend session. Closing the Tauri window also owns backend shutdown.");
    }
    setText("backend-lifecycle-summary", lines.join("\n"));
    const button = byId("backend-shutdown-button");
    if (button) {
      button.disabled = backendShutdownInFlight || !lifecycle.canShutdown;
      button.title = lifecycle.canShutdown ? "Request backend-owned graceful shutdown. This is enabled only because close-readiness reports safe." : "Disabled until close-readiness reports safe.";
    }
    if (typeof getCommandHistory === "function") renderBackendLifecycleHistory(getCommandHistory());
  }
  function backendLifecycleCommandEntries(history) {
    const entries = Array.isArray(history) ? history : [];
    return entries.filter(entry => {
      const raw = entry?.raw && typeof entry.raw === "object" ? entry.raw : {};
      return String(entry?.command || raw.command || "").trim().toLowerCase() === "backend.shutdown";
    });
  }
  function backendLifecycleCommandLine(entry) {
    const { raw, data, request } = backendLifecycleCommandData(entry);
    const result = entry?.result || (entry?.ok ? "ok" : entry?.severity || "unknown");
    const bits = [];
    if (data.safe_to_close !== undefined) bits.push(`safe_to_close=${data.safe_to_close ? "yes" : "no"}`);
    if (data.state) bits.push(`state=${data.state}`);
    if (data.reason) bits.push(`close_reason=${data.reason}`);
    if (data.continuous_watcher && typeof data.continuous_watcher === "object" && data.continuous_watcher.status) {
      const watcherBits = [`watcher=${data.continuous_watcher.status}`];
      if (data.continuous_watcher.pid) watcherBits.push(`pid=${data.continuous_watcher.pid}`);
      if (data.continuous_watcher.deadline) watcherBits.push(`deadline=${data.continuous_watcher.deadline}`);
      bits.push(watcherBits.join(" "));
    }
    if (request.reason) bits.push(`reason=${request.reason}`);
    const message = String(entry?.message || raw.message || "").trim();
    if (typeof commandHistoryCompactEvidenceLine === "function") {
      return commandHistoryCompactEvidenceLine(entry, {
        label: "backend.shutdown",
        detail: bits.length ? ` (${bits.join("; ")})` : ""
      });
    }
    return `${entry?.at || ""} backend.shutdown [${result}] ${message}${bits.length ? ` (${bits.join("; ")})` : ""}`.trim();
  }
  function renderBackendLifecycleHistory(history = []) {
    const entries = backendLifecycleCommandEntries(history).slice(0, 5);
    renderBackendLifecycleHistoryRows(entries);
    if (!entries.length) {
      setText("backend-lifecycle-history", "No backend shutdown command history loaded. Safe WebView shutdown requests will appear here after the backend responds.");
      return;
    }
    setText("backend-lifecycle-history", [`Last ${entries.length} backend lifecycle command${entries.length === 1 ? "" : "s"}:`, ...entries.map(backendLifecycleCommandLine), "Lifecycle command history is evidence only; close-readiness remains the authority before any new shutdown attempt."].join("\n"));
  }

  // Keyboard shortcuts are local UI affordances only. They may refresh read-only
  // payloads, change visible filters, move focus/selection, and navigate pages;
  // they must not submit pipeline, publish, rename, settings-save, or file-open
  // mutation commands.
  const KEYBOARD_PAGE_KEYS = {
    "1": { page: "home", label: "Home" },
    "2": { page: "queue", label: "Queue" },
    "3": { page: "completed", label: "Completed Output" },
    "4": { page: "pending", label: "Pending Publish" },
    "5": { page: "launch", label: "Launch" },
    "6": { page: "reports", label: "Reports" },
    "7": { page: "diagnostics", label: "Diagnostics" },
    "8": { page: "settings", label: "Settings" },
    "9": { page: "maintenance", label: "Maintenance" },
  };

  const KEYBOARD_PRIMARY_FILTER_IDS = {
    queue: "queue-filter",
    completed: "completed-filter",
    pending: "pending-filter",
    reports: "failure-filter",
    diagnostics: "diagnostics-log-filter",
    settings: "settings-filter",
    network: "network-worker-filter",
  };

  const KEYBOARD_DETAIL_IDS = {
    queue: "queue-detail",
    completed: "completed-detail",
    pending: "pending-detail",
    reports: "failure-detail",
    diagnostics: "diagnostics-first-response-detail",
    settings: "settings-detail",
    network: "network-worker-detail",
  };

  function activeKeyboardPage() {
    return document.querySelector("[data-page-panel].is-visible")?.dataset.pagePanel || "home";
  }

  function activeKeyboardPanel() {
    return document.querySelector("[data-page-panel].is-visible");
  }

  function shortcutTypingTarget(target) {
    const tag = target ? String(target.tagName || "").toUpperCase() : "";
    return ["INPUT", "TEXTAREA", "SELECT"].includes(tag) || Boolean(target?.isContentEditable);
  }

  function shortcutElementVisible(node) {
    if (!node) return false;
    const style = typeof window.getComputedStyle === "function" ? window.getComputedStyle(node) : null;
    return (!style || (style.display !== "none" && style.visibility !== "hidden"))
      && Boolean(node.offsetWidth || node.offsetHeight || node.getClientRects().length);
  }

  function focusActivePageSearch() {
    const page = activeKeyboardPage();
    const panel = activeKeyboardPanel();
    const configured = byId(KEYBOARD_PRIMARY_FILTER_IDS[page] || "");
    const target = configured || panel?.querySelector('input[type="search"], input[id*="filter"]');
    if (!target || typeof target.focus !== "function" || !shortcutElementVisible(target)) return false;
    target.focus();
    if (typeof target.select === "function") target.select();
    return true;
  }

  function dispatchShortcutInputChange(node) {
    node.dispatchEvent(new Event("input", { bubbles: true }));
    node.dispatchEvent(new Event("change", { bubbles: true }));
  }

  function clearActivePageFilters() {
    const page = activeKeyboardPage();
    const panel = activeKeyboardPanel();
    if (!panel) return false;
    if (page === "queue" && window.mediaPipelineQueueView?.resetQueueFilters) {
      window.mediaPipelineQueueView.resetQueueFilters();
      return true;
    }
    if (page === "completed" && window.mediaPipelineCompletedView?.resetCompletedFilters) {
      window.mediaPipelineCompletedView.resetCompletedFilters();
      return true;
    }
    if (page === "pending" && window.mediaPipelinePendingPublishView?.resetPendingFilters) {
      window.mediaPipelinePendingPublishView.resetPendingFilters();
      return true;
    }
    let changed = false;
    panel.querySelectorAll("input, select").forEach((node) => {
      const searchable = /filter|search/i.test([node.id, node.name, node.placeholder, node.getAttribute("aria-label")].filter(Boolean).join(" "));
      if (!searchable) return;
      if (node.tagName === "SELECT") {
        const nextValue = Array.from(node.options || []).some((option) => option.value === "all") ? "all" : (node.options?.[0]?.value || "");
        if (node.value !== nextValue) {
          node.value = nextValue;
          changed = true;
          dispatchShortcutInputChange(node);
        }
      } else if (node.type === "checkbox" || node.type === "radio") {
        return;
      } else if (node.value) {
        node.value = "";
        changed = true;
        dispatchShortcutInputChange(node);
      }
    });
    return changed;
  }

  function activePageSelectableRows() {
    const panel = activeKeyboardPanel();
    if (!panel) return [];
    return Array.from(panel.querySelectorAll('tr[data-selectable-row="true"]')).filter(shortcutElementVisible);
  }

  function moveActivePageSelection(delta) {
    const rows = activePageSelectableRows();
    if (!rows.length) return false;
    const currentIndex = rows.findIndex((row) => row.classList.contains("is-selected") || row.getAttribute("aria-selected") === "true" || row === document.activeElement);
    const baseIndex = currentIndex >= 0 ? currentIndex : (delta > 0 ? -1 : rows.length);
    const nextIndex = Math.max(0, Math.min(rows.length - 1, baseIndex + delta));
    const next = rows[nextIndex];
    if (!next) return false;
    next.click();
    if (typeof next.focus === "function") next.focus({ preventScroll: true });
    if (typeof next.scrollIntoView === "function") next.scrollIntoView({ block: "nearest", inline: "nearest" });
    return true;
  }

  function focusActivePageDetail() {
    const page = activeKeyboardPage();
    const panel = activeKeyboardPanel();
    const target = byId(KEYBOARD_DETAIL_IDS[page] || "") || panel?.querySelector('pre[id$="-detail"]');
    if (page === "completed" && target?.id === "completed-detail") {
      activateCompletedTab("overview");
      const rawDetail = target.closest("details");
      if (rawDetail && !rawDetail.open) rawDetail.open = true;
    }
    if (!target || !shortcutElementVisible(target)) return false;
    if (!target.hasAttribute("tabindex")) target.setAttribute("tabindex", "-1");
    if (typeof target.focus === "function") target.focus({ preventScroll: true });
    if (typeof target.scrollIntoView === "function") target.scrollIntoView({ block: "nearest", inline: "nearest" });
    return true;
  }

  function keyboardShortcutRegistry(toggleHelp) {
    const pageShortcuts = Object.entries(KEYBOARD_PAGE_KEYS).map(([key, item]) => ({
      key,
      label: key,
      description: `Go to ${item.label}`,
      run: () => showPage(item.page),
    }));
    return [
      { key: "r", label: "R", description: "Refresh read-only backend state", run: () => refreshAll() },
      { key: "/", label: "/", description: "Focus search/filter on this page", run: focusActivePageSearch },
      { key: "c", label: "C", description: "Clear filters on this page", run: clearActivePageFilters },
      { key: "j", label: "J", description: "Select next visible row", run: () => moveActivePageSelection(1) },
      { key: "k", label: "K", description: "Select previous visible row", run: () => moveActivePageSelection(-1) },
      { key: "d", label: "D", description: "Focus selected-row detail", run: focusActivePageDetail },
      { key: "a", label: "A", description: "Toggle Advanced mode", run: () => byId("advanced-toggle")?.click() },
      ...pageShortcuts,
      { key: "?", label: "?", description: "Show or hide keyboard shortcuts", run: toggleHelp },
    ];
  }

  function keyboardShortcutHelpText(registry) {
    const lines = [
      "Keyboard shortcuts",
      "------------------",
      "Read-only shortcuts. They navigate, refresh, filter, focus, or select rows; they do not launch, publish, rename, save settings, open files, or delete sources.",
      "",
    ];
    registry.forEach((item) => lines.push(`${String(item.label || item.key).padStart(2, " ")}  ${item.description}`));
    return lines.join("\n");
  }

  function initKeyboardShortcuts() {
    let helpEl = null;
    let registry = [];

    function toggleHelp() {
      if (helpEl) {
        helpEl.remove();
        helpEl = null;
        return true;
      }
      helpEl = document.createElement("div");
      helpEl.className = "keyboard-shortcut-help";
      helpEl.setAttribute("role", "dialog");
      helpEl.setAttribute("aria-label", "Keyboard shortcuts");
      helpEl.textContent = keyboardShortcutHelpText(registry);
      document.body.appendChild(helpEl);
      window.setTimeout(() => {
        if (helpEl) {
          helpEl.remove();
          helpEl = null;
        }
      }, 6000);
      return true;
    }

    registry = keyboardShortcutRegistry(toggleHelp);

    document.addEventListener("keydown", (event) => {
      if (shortcutTypingTarget(event.target)) return;
      if (event.ctrlKey || event.altKey || event.metaKey) return;
      const key = String(event.key || "").length === 1 ? String(event.key || "").toLowerCase() : String(event.key || "");
      const shortcut = registry.find((item) => item.key === key);
      if (!shortcut) return;
      const handled = shortcut.run(event);
      if (handled === false) return;
      event.preventDefault();
    });
  }


  /**
   * Public namespace for app lifecycle rendering helpers.
   * Flat window.* exports remain owned by app.js compatibility wrappers.
   */
  window.mediaPipelineAppLifecycle = {
    renderBackendLifecycle,
    backendLifecycleCommandEntries,
    backendLifecycleCommandLine,
    renderBackendLifecycleHistory,
    topbarStageContext,
    renderTopbarActivity,
    renderTopbarEventTicker,
    setTopbarPendingLaunch,
    topbarEventTickerLine,
    formatCloseReadiness,
    closeReadinessWatcherData,
    closeReadinessWatcherSummary,
    closeReadinessWatcherIsArmed,
    backendLifecycleState,
    startupProgressLines,
    normalizeTauriBackendLifecycleEvent,
    tauriBackendLifecycleLines,
    renderTauriBackendLifecycleAlert,
    renderControlReadiness,
    updatePagePanelEmptyStates,
    syncTabAccessibility,
    showPage,
    applyDefaultActionTooltips,
    initSettingsTabNav,
    activateDiagnosticsTab,
    initDiagnosticsTabNav,
    initCompletedTabNav,
    activateUiQuickLink,
    initUiQuickLinks,
    initNavigation,
    renderSparkline,
    initLaunchEvidenceToggle,
    initCollapsibleSummaries,
    initThemeToggle,
    applyThemePreference,
    activeKeyboardPage,
    activeKeyboardPanel,
    shortcutTypingTarget,
    shortcutElementVisible,
    focusActivePageSearch,
    dispatchShortcutInputChange,
    clearActivePageFilters,
    activePageSelectableRows,
    moveActivePageSelection,
    focusActivePageDetail,
    keyboardShortcutRegistry,
    keyboardShortcutHelpText,
    initKeyboardShortcuts
  };
})();
