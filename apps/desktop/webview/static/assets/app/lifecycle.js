/* global THEME_STORAGE_KEY, _layoutRenderDrawer, backendShutdownInFlight, commandHistoryCompactEvidenceLine, getCommandHistory, homeProgressPercent, lastCloseReadiness, lastSnapshot, lastStartupProgress, lastTauriBackendLifecycleEvent, refreshAll */
(function () {

const lifecycleTopbarModule = window.__appLifecycleTopbarModule;
  if (!lifecycleTopbarModule?.createAppLifecycleTopbar) {
    throw new Error("app lifecycle topbar module must load before lifecycle.js");
  }
  const {
    formatProgressValue,
    topbarStageContext,
    renderTopbarActivity,
    renderTopbarEventTicker,
    setTopbarPendingLaunch,
    clearTopbarPendingLaunch,
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
  } = lifecycleTopbarModule.createAppLifecycleTopbar();
  delete window.__appLifecycleTopbarModule;

const lifecycleNavigationModule = window.__appLifecycleNavigationModule;
  if (!lifecycleNavigationModule?.createAppLifecycleNavigation) {
    throw new Error("app lifecycle navigation module must load before lifecycle.js");
  }
  const {
    updatePagePanelEmptyStates,
    syncTabAccessibility,
    showPage,
    applyDefaultActionTooltips,
    initSettingsTabNav,
    activateDiagnosticsTab,
    initDiagnosticsTabNav,
    activateCompletedTab,
    initCompletedTabNav,
    activateUiQuickLink,
    initUiQuickLinks,
    initNavigation,
    renderSparkline,
    initLaunchEvidenceToggle,
    initCollapsibleSummaries,
    initThemeToggle,
    applyThemePreference,
  } = lifecycleNavigationModule.createAppLifecycleNavigation({
    completedTabStorageKey: "mediapipeline-completed-tab",
  });
  delete window.__appLifecycleNavigationModule;

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
      lines.push("Next step: inspect Close Readiness, Progress, Run Logs, and Last Stderr before closing or retrying lifecycle actions.");
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
    clearTopbarPendingLaunch,
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
