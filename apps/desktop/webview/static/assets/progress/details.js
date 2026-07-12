(function () {
  function createProgressDetailsModule({
    formatProgressValue,
    progressBarId,
    setProgressPanelStatus,
    byId,
    clearRows,
    appendCells,
  } = {}) {
      function progressHasValue(value) {
        return value !== undefined && value !== null && value !== "";
      }

      function progressNumericValue(value, fallback = 0) {
        const number = Number(value);
        return Number.isFinite(number) ? number : fallback;
      }

      function progressBooleanValue(value) {
        if (typeof value === "boolean") return value;
        const text = String(value || "").trim().toLowerCase();
        return ["1", "true", "yes", "y"].includes(text);
      }

      function progressStoppedByRequest(payload) {
        const errorCode = String(payload?.ErrorCode || payload?.error_code || "").trim().toLowerCase();
        const reason = String(payload?.Reason || payload?.reason || "").trim().toLowerCase();
        const text = [
          payload?.Status,
          payload?.status,
          payload?.CurrentStage,
        ].filter(Boolean).join(" ").toLowerCase();
        return progressBooleanValue(payload?.StopRequested)
          || progressBooleanValue(payload?.stop_requested)
          || errorCode === "stop_requested"
          || (/\bstopped\b/.test(text) && reason.includes("stop") && reason.includes("operator"));
      }

      function progressEventData(event) {
        return event?.data && typeof event.data === "object" ? event.data : {};
      }

      function progressEventStoppedByRequest(event) {
        const data = progressEventData(event);
        const status = String(data.completion_status || event?.status || "").trim().toLowerCase();
        const errorCode = String(data.error_code || data.ErrorCode || "").trim().toLowerCase();
        const reason = String(data.reason || data.suggested_action || "").trim().toLowerCase();
        return status === "stopped" && (errorCode === "stop_requested" || (reason.includes("stop") && reason.includes("operator")));
      }

      function progressEventIsFailure(event) {
        const data = progressEventData(event);
        const status = String(data.completion_status || event?.status || data.classification || "").trim().toLowerCase();
        const errorCode = String(data.error_code || data.ErrorCode || "").trim().toLowerCase();
        return ["failed", "failure", "error", "blocked"].includes(status)
          || String(event?.event_type || "").toLowerCase() === "failure_recorded"
          || Boolean(errorCode && errorCode !== "stop_requested");
      }

      function progressLatestStopEvent(snapshot = {}) {
        const events = Array.isArray(snapshot?.recent_events) ? snapshot.recent_events : [];
        for (let index = events.length - 1; index >= 0; index -= 1) {
          const event = events[index];
          if (progressEventStoppedByRequest(event)) return event;
          if (progressEventIsFailure(event)) return null;
        }
        return null;
      }

      function progressSnapshotStoppedByRequest(snapshot = {}) {
        return Boolean(progressLatestStopEvent(snapshot) || progressStoppedByRequest(snapshot?.progress || {}));
      }

      function progressStopNextAction(snapshot = {}) {
        const stopEvent = progressLatestStopEvent(snapshot);
        const data = progressEventData(stopEvent);
        const publishState = String(data.publish_state || snapshot?.progress?.PublishState || "").trim().toLowerCase();
        const completionStatus = String(data.completion_status || "").trim().toLowerCase();
        const success = progressBooleanValue(data.success);
        if (["parked", "parked_recovered", "pending_move", "deferred"].includes(publishState) || publishState.includes("retry")) {
          return "Stop After Current was requested; output is waiting in Pending Publish. Drain when the final output root is safe.";
        }
        if (["published", "already_published", "succeeded"].includes(publishState)) {
          return "Stop After Current was requested; the current file completed and published. Launch when ready to continue.";
        }
        if (success || completionStatus === "processed") {
          return "Stop After Current was requested; the current file completed. Check Completed and Pending Publish, then Launch when ready.";
        }
        return "Stop After Current was requested. Check Completed and Pending Publish for the last item, then Launch when ready.";
      }

      function progressOperatorStopBar(snapshot = {}) {
        if (!progressSnapshotStoppedByRequest(snapshot)) return null;
        const stopEvent = progressLatestStopEvent(snapshot);
        const progress = snapshot?.progress && typeof snapshot.progress === "object" ? snapshot.progress : {};
        return {
          id: "operator_stop",
          label: "Stopped after current",
          status: "warning",
          mode: "determinate",
          percent: 100,
          detail: progressStopNextAction(snapshot),
          source: stopEvent ? "pipeline_events.json" : "pipeline_progress.json",
          updated_at: stopEvent?.timestamp || stopEvent?.created_at || progress.LastUpdate || progress.UpdatedAt || "",
        };
      }

      function progressBarsWithOperatorStop(bars = [], snapshot = null) {
        const items = Array.isArray(bars) ? bars.filter(Boolean) : [];
        const stopBar = progressOperatorStopBar(snapshot || {});
        if (!stopBar || items.some((bar) => progressBarId(bar) === "operator_stop")) return items;
        return [stopBar, ...items];
      }

      function progressIsEmptyText(value) {
        const text = String(value || "").trim().toLowerCase();
        return !text || text === "none" || text === "idle" || text === "unknown";
      }

      function progressTextFromKeys(payload, keys = []) {
        for (const key of keys) {
          const value = payload?.[key];
          if (!progressIsEmptyText(value)) return String(value).trim();
        }
        return "";
      }

      function progressMediaTypeLabel(value) {
        const text = String(value || "").trim();
        const normalized = text.toLowerCase();
        if (!normalized) return "";
        if (normalized === "tv" || normalized === "episode" || normalized === "episodes") return "TV";
        if (normalized === "movie" || normalized === "movies") return "Movies";
        if (normalized === "pending" || normalized === "pending_push") return "Pending publish";
        return text.replace(/_/g, " ");
      }

      function progressLibraryItem(payload) {
        const name = progressTextFromKeys(payload, [
          "CurrentLibraryName",
          "CurrentLibraryProfileName",
          "LibraryName",
          "library_name",
        ]);
        const id = progressTextFromKeys(payload, [
          "CurrentLibraryId",
          "CurrentLibraryProfileId",
          "LibraryId",
          "library_id",
        ]);
        const designation = progressTextFromKeys(payload, [
          "CurrentLibraryDesignation",
          "LibraryDesignation",
          "library_designation",
        ]);
        const sourceRoot = progressTextFromKeys(payload, [
          "CurrentLibrarySourceRoot",
          "LibrarySourceRoot",
          "library_source_root",
          "source_root",
        ]);
        const mediaType = progressMediaTypeLabel(payload.CurrentMediaType || payload.CurrentQueuePhase);
        const value = name || id || mediaType || "not reported";
        const hintParts = [];
        if (designation && designation !== value) hintParts.push(designation);
        if (id && id !== value) hintParts.push(`Profile: ${id}`);
        if (sourceRoot) hintParts.push(`Source: ${sourceRoot}`);
        if (!hintParts.length && mediaType && !name && !id) {
          hintParts.push("Progress file reports media type, not a library profile.");
        }
        return {
          label: "Library",
          value: formatProgressValue(value),
          hint: hintParts.join("; ") || "No library profile detail reported",
          status: name || id || sourceRoot ? "ok" : (mediaType ? "warning" : "empty"),
        };
      }

      function audioProgressLine(audio) {
        const payload = audio && typeof audio === "object" ? audio : {};
        if (!Object.keys(payload).length) return "";
        const action = formatProgressValue(payload.action || payload.Action || "audio");
        const status = formatProgressValue(payload.status || payload.Status || "unknown");
        const stream = payload.stream_index !== undefined && payload.stream_index !== null && payload.stream_index !== -1
          ? `stream ${formatProgressValue(payload.stream_index)}`
          : "";
        const source = payload.source_codec || payload.SourceCodec || "";
        const output = payload.output_codec || payload.OutputCodec || "";
        const codecs = [source, output].filter(Boolean).join(" -> ");
        const sourceChannels = payload.source_channels || payload.SourceChannels || "";
        const outputChannels = payload.output_channels || payload.OutputChannels || "";
        const channels = [sourceChannels, outputChannels].filter(Boolean).map((value) => `${formatProgressValue(value)}ch`).join(" -> ");
        const reason = payload.reason || payload.Reason || "";
        return [status, action, stream, codecs, channels, reason].filter(Boolean).join(" | ");
      }

      function audioProgressItem(payload) {
        const audio = payload?.AudioProgress && typeof payload.AudioProgress === "object" ? payload.AudioProgress : null;
        if (!audio) return null;
        const failed = progressBooleanValue(audio.failed || audio.Failed);
        const completed = progressBooleanValue(audio.completed || audio.Completed);
        return {
          label: "Audio",
          value: formatProgressValue(audio.action || audio.Action || audio.status || audio.Status || "loaded"),
          hint: audioProgressLine(audio) || "Backend audio policy progress loaded.",
          status: failed ? "blocked" : completed ? "ok" : "running",
        };
      }

      function pendingDrainProgressLine(pending) {
        const payload = pending && typeof pending === "object" ? pending : {};
        if (!Object.keys(payload).length) return "";
        const total = progressNumericValue(payload.manifest_count ?? payload.ManifestCount ?? payload.manifest_count_at_start ?? payload.ManifestCountAtStart);
        const attempted = progressNumericValue(payload.attempted_count ?? payload.AttemptedCount);
        const succeeded = progressNumericValue(payload.succeeded_count ?? payload.SucceededCount);
        const already = progressNumericValue(payload.already_published_count ?? payload.AlreadyPublishedCount);
        const errors = progressNumericValue(payload.error_count ?? payload.ErrorCount);
        const skipped = progressNumericValue(payload.skipped_count ?? payload.SkippedCount);
        const remaining = progressNumericValue(payload.remaining_count ?? payload.RemainingCount);
        const status = payload.status || payload.Status || "pending publish drain";
        const current = payload.current_item || payload.CurrentItem || payload.current_manifest || payload.CurrentManifest || "";
        return [
          formatProgressValue(status),
          total ? `${attempted} / ${total} manifests` : "",
          succeeded ? `succeeded ${succeeded}` : "",
          already ? `already published ${already}` : "",
          errors ? `errors ${errors}` : "",
          skipped ? `skipped ${skipped}` : "",
          remaining ? `remaining ${remaining}` : "",
          current ? `current ${formatProgressValue(current)}` : "",
        ].filter(Boolean).join(" | ");
      }

      function pendingDrainProgressItem(payload) {
        const pending = payload?.PendingDrainProgress && typeof payload.PendingDrainProgress === "object" ? payload.PendingDrainProgress : null;
        if (!pending) return null;
        const total = progressNumericValue(pending.manifest_count ?? pending.ManifestCount ?? pending.manifest_count_at_start ?? pending.ManifestCountAtStart);
        const attempted = progressNumericValue(pending.attempted_count ?? pending.AttemptedCount);
        const errors = progressNumericValue(pending.error_count ?? pending.ErrorCount);
        const deferred = progressBooleanValue(pending.deferred || pending.Deferred);
        return {
          label: "Drain",
          value: total ? `${attempted} / ${total}` : formatProgressValue(pending.status || pending.Status || "loaded"),
          hint: pendingDrainProgressLine(pending) || "Backend pending-publish drain progress loaded.",
          status: errors ? "blocked" : deferred ? "warning" : total && attempted >= total ? "ok" : "running",
        };
      }

      function progressDetailItems(progress) {
        const payload = progress && typeof progress === "object" ? progress : {};
        const route = payload.CurrentRoute || payload.Route || "";
        const reason = payload.RouteReason || payload.CurrentRouteReason || "";
        const queueIndex = payload.CurrentQueueIndex;
        const queueTotal = payload.CurrentQueueTotal;
        const remuxed = progressNumericValue(payload.Remuxed);
        const encoded = progressNumericValue(payload.Encoded);
        const failed = progressNumericValue(payload.Failed);
        const stopped = failed > 0 && progressStoppedByRequest(payload);
        const visibleFailed = stopped ? Math.max(0, failed - 1) : failed;
        const items = [];
        items.push(progressLibraryItem(payload));
        items.push(
          {
            label: "Queue",
            value: progressHasValue(queueIndex) || progressHasValue(queueTotal)
              ? `${formatProgressValue(queueIndex || 0)} / ${formatProgressValue(queueTotal || 0)}`
              : "none",
            hint: "Current item position",
            status: progressNumericValue(queueTotal) > 0 ? "running" : "empty",
          },
          {
            label: "Route",
            value: route ? formatProgressValue(route) : "none",
            hint: reason ? formatProgressValue(reason) : "No route reason",
            status: route ? "ok" : "empty",
          },
          audioProgressItem(payload),
          pendingDrainProgressItem(payload),
          {
            label: "Done",
            value: `${remuxed + encoded}`,
            hint: `Remuxed ${remuxed}; encoded ${encoded}`,
            status: remuxed + encoded > 0 ? "ok" : "empty",
          },
          {
            label: "Issues",
            value: String(visibleFailed),
            hint: visibleFailed ? "Failures need review" : stopped ? "Stop After Current is tracked in the progress bar." : "No failures reported",
            status: visibleFailed ? "blocked" : "ok",
          }
        );
        return items.filter(Boolean);
      }

      const progressDetailQuickLinks = {
        library: { page: "libraries", label: "Open Libraries" },
        queue: { page: "queue", label: "Open Queue" },
        route: { page: "queue", label: "Open Queue route evidence" },
        done: { page: "completed", label: "Open Completed Output" },
        issues: { page: "reports", reportsTab: "failures", label: "Open Reports failures" },
      };

      function progressDetailQuickLinkKey(item) {
        return String(item?.label || "").trim().toLowerCase();
      }

      function progressDetailQuickLink(item) {
        return progressDetailQuickLinks[progressDetailQuickLinkKey(item)] || null;
      }

      function progressDetailQuickLinkLabel(item, link) {
        const label = String(item?.label || "").trim();
        const value = String(item?.value || "").trim();
        const action = String(link?.label || "Open quick link").trim();
        return [action, [label, value].filter(Boolean).join(": ")].filter(Boolean).join(" - ");
      }

      function activateProgressDetailQuickLink(link) {
        if (!link?.page) return;
        if (typeof window.showPage === "function") window.showPage(link.page);
        if (link.page === "reports" && link.reportsTab) {
          const reportsView = window.mediaPipelineReportsView || {};
          reportsView.activateReportsTab?.(link.reportsTab);
        }
      }

      function renderProgressDetails(progress) {
        const payload = progress && typeof progress === "object" ? progress : {};
        const items = progressDetailItems(payload);
        const loaded = Object.keys(payload).length > 0;
        setProgressPanelStatus("progress-detail-status", loaded ? `${items.length} checks` : "No details", loaded ? "ready" : "empty");
        const container = byId("progress-detail-rows");
        if (!container) return;
        if (!loaded) {
          container.replaceChildren();
          const empty = document.createElement("p");
          empty.className = "note";
          empty.textContent = "No progress details loaded.";
          container.appendChild(empty);
          return;
        }
        container.replaceChildren();
        items.forEach((item) => {
          const link = progressDetailQuickLink(item);
          const card = document.createElement("div");
          card.className = "progress-fact";
          card.dataset.status = item.status || "unknown";
          card.setAttribute("role", "listitem");
          if (link) {
            card.dataset.hasLink = "true";
            card.dataset.progressQuickLink = progressDetailQuickLinkKey(item);
            card.dataset.crossPageTarget = link.page;
            if (link.reportsTab) card.dataset.crossPageReportsTab = link.reportsTab;
          }
          const icon = document.createElement("span");
          icon.className = "progress-fact-icon";
          icon.setAttribute("aria-hidden", "true");
          const body = document.createElement("span");
          body.className = "progress-fact-body";
          const label = document.createElement("span");
          label.className = "progress-fact-label";
          label.textContent = item.label;
          const value = document.createElement("strong");
          value.className = "progress-fact-value";
          value.textContent = item.value;
          const hint = document.createElement("span");
          hint.className = "progress-fact-hint";
          hint.textContent = item.hint;
          body.append(label, value, hint);
          if (link) {
            const button = document.createElement("button");
            button.type = "button";
            button.className = "progress-fact-link";
            button.dataset.crossPageTarget = link.page;
            if (link.reportsTab) button.dataset.crossPageReportsTab = link.reportsTab;
            button.setAttribute("aria-label", progressDetailQuickLinkLabel(item, link));
            button.title = [link.label, item.hint].filter(Boolean).join(". ");
            button.addEventListener("click", () => activateProgressDetailQuickLink(link));
            button.append(icon, body);
            card.appendChild(button);
          } else {
            card.append(icon, body);
          }
          container.appendChild(card);
        });
      }

      function renderPipelineEvents(events) {
        setProgressPanelStatus("pipeline-events-status", events.length ? `${events.length} event${events.length === 1 ? "" : "s"}` : "No events", events.length ? "changed" : "empty");
        const tbody = byId("pipeline-event-rows");
        if (!tbody) return;
        if (!events.length) {
          clearRows(tbody, 3, "No pipeline events loaded.");
          return;
        }
        tbody.replaceChildren();
        events.slice(-25).reverse().forEach((event) => {
          const row = document.createElement("tr");
          appendCells(row, [
            event.timestamp || event.created_at || "",
            event.event_type || event.type || "",
            formatProgressValue(event.data || event),
          ]);
          tbody.appendChild(row);
        });
      }

      function normalizedProgressState(snapshot, progress) {
        return String(snapshot?.pipeline_state || progress?.Status || progress?.status || "unknown").trim().toLowerCase();
      }

      function progressStateIsActive(state) {
        return /processing|running|active|publishing|copying|encoding|remuxing|probing|auditing/.test(String(state || "").toLowerCase());
      }

      function progressEvidencePostureStatus(posture) {
        const value = String(posture || "").toLowerCase();
        if (value.includes("blocked") || value.includes("active work") || value.includes("unsafe")) return "blocked";
        if (value.includes("review") || value.includes("unknown") || value.includes("stale") || value.includes("missing") || value.includes("paused") || value.includes("stop")) return "warning";
        return "match";
      }

      function progressLatestEvent(events) {
        const items = Array.isArray(events) ? events.filter(Boolean) : [];
        if (!items.length) return null;
        return items[items.length - 1] || null;
      }

      function progressEventLabel(event) {
        if (!event) return "none";
        const type = event.event_type || event.type || event.kind || "event";
        const time = event.timestamp || event.created_at || event.at || "";
        return `${time ? `${time} ` : ""}${type}`.trim();
      }

      function progressActiveJobRows(diagnostics) {
        const structuredRows = Array.isArray(diagnostics?.active_job_rows) ? diagnostics.active_job_rows.filter(Boolean) : [];
        if (structuredRows.length) return structuredRows;
        return Array.isArray(diagnostics?.active_jobs) ? diagnostics.active_jobs.filter(Boolean) : [];
      }

      function formatActiveJobEvidenceRow(row) {
        if (!row || typeof row !== "object") return formatProgressValue(row);
        return [
          row.job_kind || row.record_file || "ActiveJobs record",
          row.mode ? `mode=${formatProgressValue(row.mode)}` : "",
          row.status ? `status=${formatProgressValue(row.status)}` : "",
          row.status_state ? `state=${formatProgressValue(row.status_state)}` : "",
          row.launch_id ? `launch=${formatProgressValue(row.launch_id)}` : "",
          row.pid !== undefined && row.pid !== null ? `pid=${formatProgressValue(row.pid)}` : "",
          row.issue ? `issue=${formatProgressValue(row.issue)}` : "",
        ].filter(Boolean).join("; ");
      }

    return {
      progressNumericValue,
      progressBarsWithOperatorStop,
      audioProgressLine,
      pendingDrainProgressLine,
      renderProgressDetails,
      renderPipelineEvents,
      normalizedProgressState,
      progressStateIsActive,
      progressEvidencePostureStatus,
      progressLatestEvent,
      progressEventLabel,
      progressActiveJobRows,
      formatActiveJobEvidenceRow,
    };
  }

  window.__progressDetailsModule = { createProgressDetailsModule };
})();
