(function () {
  function createScheduleWatchFolderModule(deps = {}) {
    const {
      appendCells,
      byId,
      scheduleDisplayValue,
      setText,    } = deps;
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

  function watchFolderActionLabel(value) {
    const labels = {
      enqueue_only: "Enqueue only",
      enqueue_and_launch: "Enqueue and launch",
    };
    const key = String(value || "enqueue_only").toLowerCase();
    return labels[key] || key || "Enqueue only";
  }

  function watchFolderReachability(row) {
    if (!row || typeof row !== "object" || row.reachable === undefined || row.reachable === null) {
      return {
        status: "unknown",
        status_text: "Unknown",
        evidence: "Backend did not report reachability for this root.",
      };
    }
    return row.reachable
      ? {
        status: "ready",
        status_text: "Reachable",
        evidence: "Backend can see this root.",
      }
      : {
        status: "blocked",
        status_text: "Unreachable",
        evidence: "Backend reports this root is not reachable.",
      };
  }

  function watchFolderLaunchOutcome(row) {
    const outcome = String(row?.outcome || "").trim();
    const normalized = outcome.toLowerCase();
    if (!normalized) {
      return { status: "unknown", status_text: "Unknown" };
    }
    if (/(fail|error|blocked|refus|reject|denied|cancel|abort)/.test(normalized)) {
      return { status: "blocked", status_text: outcome };
    }
    if (/(success|started|running|launched|queued|accepted|ok)/.test(normalized)) {
      return { status: "ready", status_text: outcome };
    }
    return { status: "review", status_text: outcome };
  }

  function watchFolderStatusLabel(payload) {
    if (!payload || typeof payload !== "object" || !payload.schema_version) return "Not loaded";
    const status = String(payload.status || "unknown").toLowerCase();
    if (!payload.enabled) return "Disabled";
    if (payload.pending_work) return "Pending";
    if (status === "degraded") return "Degraded";
    if (status === "error") return "Error";
    if (payload.running) return "Running";
    return payload.status || "Unknown";
  }

  function watchFolderStatusValue(payload) {
    if (!payload || typeof payload !== "object" || !payload.schema_version) return "blocked";
    const status = String(payload.status || "unknown").toLowerCase();
    if (status === "degraded" || status === "error") return "blocked";
    if (payload.pending_work || !payload.enabled) return "review";
    if (payload.running || status === "running") return "ready";
    return "review";
  }

  function watchFolderRecentLines(payload) {
    const rows = Array.isArray(payload?.recent_detections) ? payload.recent_detections : [];
    if (!rows.length) {
      return [
        "No recent stable detections.",
        "Mutation guardrail: this card is read-only; watch-folder scanning and launch decisions remain backend-owned.",
      ];
    }
    const lines = ["Recent stable detections:"];
    rows.slice(-8).reverse().forEach((item) => {
      const detected = scheduleDisplayValue(item?.detected_utc);
      lines.push(`- ${detected}: ${item?.path || "(path not reported)"}`);
    });
    lines.push("", "Mutation guardrail: this card is read-only; watch-folder scanning and launch decisions remain backend-owned.");
    return lines;
  }

  function watchFolderSummaryLines(payload) {
    if (!payload || typeof payload !== "object" || !payload.schema_version) {
      return [
        "Watch-folder state is not loaded.",
        "Mutation guardrail: Schedule only displays watch-folder status; backend configuration and lifecycle own scanner behavior.",
      ];
    }
    const roots = Array.isArray(payload.roots) ? payload.roots : [];
    const lastLaunch = payload.last_launch && typeof payload.last_launch === "object" ? payload.last_launch : null;
    const lastRefusal = payload.last_refusal && typeof payload.last_refusal === "object" ? payload.last_refusal : null;
    const rootText = roots.length
      ? roots.map((root) => {
        const reachability = watchFolderReachability(root);
        return `${reachability.status_text.toLowerCase()}: ${root.path || "(path not reported)"}${root.last_error ? ` (${root.last_error})` : ""}`;
      })
      : ["none"];
    const lines = [
      "Watch-folder manager:",
      `Status: ${payload.status || "unknown"}`,
      `Enabled: ${payload.enabled ? "yes" : "no"}`,
      `Running: ${payload.running ? "yes" : "no"}`,
      `Action: ${watchFolderActionLabel(payload.effective_action)}`,
      `Network role: ${payload.network_role || "standalone"}`,
      `Roots: ${roots.length}${payload.derived_roots_from_library_profiles ? " (from source/library profile roots)" : ""}`,
      `Debounce: ${Number(payload.debounce_seconds || 0) || "unknown"} second(s)`,
      `Pending work: ${payload.pending_work ? "yes" : "no"}`,
      `Last cycle: ${scheduleDisplayValue(payload.last_cycle_completed_utc)}`,
      `Reason: ${payload.reason || "(not reported)"}`,
      `Last error: ${payload.last_error || "none"}`,
      "",
      "Roots:",
      ...rootText.map((line) => `- ${line}`),
    ];
    if (lastLaunch) {
      lines.push(
        "",
        "Last launch:",
        `- Outcome: ${lastLaunch.outcome || "(not reported)"}`,
        `- Requested: ${scheduleDisplayValue(lastLaunch.requested_utc)}`,
        `- PID: ${lastLaunch.pid || "none"}`,
        `- Message: ${lastLaunch.message || "(not reported)"}`
      );
    }
    if (lastRefusal) {
      lines.push(
        "",
        "Last refusal:",
        `- Time: ${scheduleDisplayValue(lastRefusal.utc)}`,
        `- Reason: ${lastRefusal.reason || "(not reported)"}`
      );
    }
    return lines;
  }

  function watchFolderRootRows(payload) {
    const roots = Array.isArray(payload?.roots) ? payload.roots : [];
    if (!roots.length) {
      return [{
        root: "No roots reported",
        status: "review",
        status_text: payload?.enabled ? "Review" : "Disabled",
        evidence: payload?.derived_roots_from_library_profiles
          ? "Backend derives roots from source/library profile settings."
          : "No watch-folder roots loaded from the backend.",
      }];
    }
    return roots.map((root) => {
      const reachability = watchFolderReachability(root);
      return {
        root: root?.path || "(path not reported)",
        status: reachability.status,
        status_text: reachability.status_text,
        evidence: root?.last_error || reachability.evidence,
      };
    });
  }

  function watchFolderEventRows(payload) {
    const rows = [];
    const lastLaunch = payload?.last_launch && typeof payload.last_launch === "object" ? payload.last_launch : null;
    const lastRefusal = payload?.last_refusal && typeof payload.last_refusal === "object" ? payload.last_refusal : null;
    const detections = Array.isArray(payload?.recent_detections) ? payload.recent_detections : [];
    if (lastRefusal) {
      rows.push({
        event: "Last refusal",
        status: "review",
        status_text: "Review",
        evidence: `${scheduleDisplayValue(lastRefusal.utc)}; ${lastRefusal.reason || "(reason not reported)"}`,
      });
    }
    if (lastLaunch) {
      const outcome = watchFolderLaunchOutcome(lastLaunch);
      rows.push({
        event: "Last launch",
        status: outcome.status,
        status_text: outcome.status_text,
        evidence: `${scheduleDisplayValue(lastLaunch.requested_utc)}; PID ${lastLaunch.pid || "none"}; ${lastLaunch.message || "(message not reported)"}`,
      });
    }
    detections.slice(-5).reverse().forEach((item) => {
      rows.push({
        event: "Stable detection",
        status: "ready",
        status_text: "Detected",
        evidence: `${scheduleDisplayValue(item?.detected_utc)}; ${item?.path || "(path not reported)"}`,
      });
    });
    if (!rows.length) {
      rows.push({
        event: "No recent events",
        status: payload?.pending_work ? "review" : "normal",
        status_text: payload?.pending_work ? "Pending" : "Idle",
        evidence: payload?.pending_work ? "Backend reports pending watch-folder work." : "No launch, refusal, or detection rows reported.",
      });
    }
    return rows;
  }

  function renderWatchFolderTables(payload) {
    const rootBody = byId("schedule-watch-folder-root-rows");
    if (rootBody) {
      rootBody.replaceChildren();
      watchFolderRootRows(payload || {}).forEach((item) => {
        const row = document.createElement("tr");
        row.dataset.status = item.status || "normal";
        appendCells(row, [item.root, item.status_text, item.evidence]);
        rootBody.appendChild(row);
      });
    }
    const eventBody = byId("schedule-watch-folder-event-rows");
    if (eventBody) {
      eventBody.replaceChildren();
      watchFolderEventRows(payload || {}).forEach((item) => {
        const row = document.createElement("tr");
        row.dataset.status = item.status || "normal";
        appendCells(row, [item.event, item.status_text, item.evidence]);
        eventBody.appendChild(row);
      });
    }
  }

  function renderWatchFolderStatus(payload) {
    const status = byId("schedule-watch-folder-status");
    if (status) {
      status.textContent = watchFolderStatusLabel(payload);
      status.dataset.state = watchFolderStatusValue(payload);
    }
    const scope = byId("schedule-watch-folder-scope");
    if (scope) {
      scope.dataset.state = "saved";
      scope.textContent = "Watch Folders: backend-owned scanner state.";
    }
    setText("schedule-watch-folder-summary", watchFolderSummaryLines(payload || {}).join("\n"));
    setText("schedule-watch-folder-recent", watchFolderRecentLines(payload || {}).join("\n"));
    renderWatchFolderTables(payload || {});
  }

    return {
      scheduleWatcherData,
      scheduleWatcherStatusValue,
      scheduleWatcherSummary,
      scheduleWatcherDetailLines,
      watchFolderActionLabel,
      watchFolderReachability,
      watchFolderLaunchOutcome,
      watchFolderStatusLabel,
      watchFolderStatusValue,
      watchFolderRecentLines,
      watchFolderSummaryLines,
      watchFolderRootRows,
      watchFolderEventRows,
      renderWatchFolderTables,
      renderWatchFolderStatus,    };
  }

  window.__scheduleWatchFolderModule = {
    createScheduleWatchFolderModule,
  };
})();
