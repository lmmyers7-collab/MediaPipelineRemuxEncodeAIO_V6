(function () {
  function createLaunchRerunPresentationModule(deps = {}) {
    const {
      appendCell,
      appendCommandResult,
      appendRerunText,
      byId,
      clearElement,
      collectRerunPreviewRequest,
      collectRerunStartRequest,
      launchCoordinatorState,
      nextLaunchCommandFrame,
      queueRerunRouteDispatcher,
      refreshAll,
      rejectLaunchCommandWhileBusy,
      renderJsonDetail,
      renderLaunchCommandResult,
      renderLaunchPreflight,
      renderRerunLifecycleEvidence,
      renderRerunPreview,
      renderRerunReviewHeader,
      rerunExecutionLabel,
      rerunExecutionTargetLabel,
      rerunHistoryData,
      rerunHistoryEntries,
      rerunHistoryRequestData,
      rerunIsNetworkMode,
      rerunPolicyChoice,
      rerunPreviewConflictLines,
      rerunPreviewCounts,
      rerunPreviewRouteName,
      rerunQueuePreflightLines,
      rerunSourceHandlingLine,
      rerunStatusSeverity,
      setLaunchCommandBusy,
      setText,
      state,
    } = deps;

    function renderRerunPreviewTiles(payload) {
      const container = byId("rerun-preview-tiles");
      if (!container) return;
      clearElement(container);
      const tiles = payload && Array.isArray(payload.tiles) ? payload.tiles : [];
      if (!tiles.length) {
        container.textContent = "No CSV rerun status tiles loaded.";
        return;
      }
      tiles.forEach((tile) => {
        const item = document.createElement("div");
        item.className = "command-history-entry";
        item.setAttribute("aria-label", `${tile.label || tile.key || "CSV rerun tile"} ${tile.value ?? ""}`);
        const label = document.createElement("strong");
        label.textContent = `${tile.label || tile.key || "Tile"} · ${tile.value ?? ""}`;
        item.appendChild(label);
        if (tile.detail) {
          const detail = document.createElement("span");
          detail.textContent = String(tile.detail);
          item.appendChild(detail);
        }
        container.appendChild(item);
      });
    }

    function rerunPreviewRowNumber(item) {
      const parsed = Number(item?.row_index);
      if (!Number.isFinite(parsed)) return "";
      return String(Math.max(0, Math.round(parsed)) + 1);
    }

    function rerunPreviewRowText(item = {}) {
      return [
        item.status,
        item.reason,
        item.blocking_reason,
        item.warning_reason,
        item.source_path,
        item.relative_path,
        item.rerun_rule_label,
        item.rerun_rule_reason,
        item.issue,
        item.bucket,
      ].map((value) => String(value || "").toLowerCase()).join(" ");
    }

    function pushRerunCategory(tokens, key, label, severity = "info") {
      if (tokens.some((item) => item.key === key)) return;
      tokens.push({ key, label, severity });
    }

    function rerunPreviewCategoryTokens(item = {}) {
      const tokens = [];
      const status = String(item.status || "unknown").toLowerCase();
      const text = rerunPreviewRowText(item);
      const sourcePath = String(item.source_path || "").trim();
      if (item.in_scope === false || /filtered|skipped/.test(status)) pushRerunCategory(tokens, "filtered", "filtered/skipped", "info");
      if (item.enabled === false || text.includes("disabled")) pushRerunCategory(tokens, "disabled", "disabled", "info");
      if (/blocked|failed|error/.test(status) || item.blocked || item.blocking_reason) pushRerunCategory(tokens, "blocked", "blocked", "high");
      if (/warning|review/.test(status) || item.warning || item.warning_reason) pushRerunCategory(tokens, "warning", "warning", "medium");
      if (item.duplicate_source === true || text.includes("duplicate source")) pushRerunCategory(tokens, "duplicate", "duplicate", "medium");
      if (!sourcePath || item.missing_source === true || item.source_missing === true || text.includes("missing source")) pushRerunCategory(tokens, "missing-source", "missing source", "high");
      if (sourcePath && !/^(?:[a-z]:[\\/]|\\\\|\/)/i.test(sourcePath)) pushRerunCategory(tokens, "relative-source", "relative source", "medium");
      if (item.source_exists === false || item.source_found === false || text.includes("source file not found") || text.includes("source not found")) pushRerunCategory(tokens, "source-not-found", "source not found", "high");
      if (item.already_completed === true || item.completed === true || text.includes("already completed")) pushRerunCategory(tokens, "already-completed", "already completed", "info");
      if (item.rerun_rule_blocked === true || String(item.rerun_rule_severity || "").toLowerCase() === "blocked") pushRerunCategory(tokens, "rule-blocked", "rule blocked", "high");
      if (item.rerun_rule_warning === true || String(item.rerun_rule_severity || "").toLowerCase() === "warning") pushRerunCategory(tokens, "rule-warning", "rule warning", "medium");
      if (!tokens.some((token) => ["blocked", "warning", "filtered", "disabled", "missing-source", "source-not-found"].includes(token.key))) {
        pushRerunCategory(tokens, "ready", "ready", "ok");
      }
      if (item.issue) pushRerunCategory(tokens, "issue", `issue: ${item.issue}`, rerunStatusSeverity(status));
      if (item.bucket) pushRerunCategory(tokens, "bucket", `bucket: ${item.bucket}`, "info");
      return tokens;
    }

    function renderRerunPreviewCategoryChips(cell, item = {}) {
      const strip = document.createElement("div");
      strip.className = "rerun-category-strip";
      rerunPreviewCategoryTokens(item).slice(0, 10).forEach((token) => {
        const chip = document.createElement("span");
        chip.className = "rerun-category-chip";
        chip.dataset.category = token.key;
        chip.dataset.severity = token.severity;
        chip.textContent = token.label;
        chip.title = `Backend preview category: ${token.label}`;
        strip.appendChild(chip);
      });
      cell.appendChild(strip);
    }

    function renderRerunPreviewIdentity(cell, item = {}) {
      const rowNumber = rerunPreviewRowNumber(item);
      const sourcePath = String(item.source_path || "").trim();
      const title = String(item.lookup_title || item.title || rerunCsvLeaf(sourcePath) || (rowNumber ? `Row ${rowNumber}` : "CSV row")).trim();
      const identity = document.createElement("div");
      identity.className = "rerun-row-identity";
      appendRerunText(identity, "rerun-row-title", title, title);
      if (item.relative_path) appendRerunText(identity, "rerun-row-relative-path", item.relative_path, item.relative_path);
      appendRerunText(identity, "rerun-row-source-path", sourcePath || "Source path missing", sourcePath || "Backend preview did not provide a source path.");
      appendRerunText(identity, "rerun-row-meta", [
        rowNumber ? `Row ${rowNumber}` : "",
        item.in_scope === false ? "filtered out" : "in scope",
        item.duplicate_source ? "duplicate source" : "",
      ].filter(Boolean).join(" · "));
      cell.appendChild(identity);
    }

    function renderRerunPreviewStatus(cell, item = {}) {
      const stack = document.createElement("div");
      stack.className = "rerun-preview-state-stack";
      const badge = document.createElement("span");
      badge.className = "rerun-state-badge";
      badge.dataset.severity = rerunStatusSeverity(item.status);
      badge.textContent = item.status || "unknown";
      stack.appendChild(badge);
      if (item.in_scope === false) {
        const scoped = document.createElement("span");
        scoped.className = "rerun-scope-chip";
        scoped.textContent = "filtered";
        stack.appendChild(scoped);
      }
      cell.appendChild(stack);
    }

    function renderRerunPreviewReason(cell, item = {}) {
      const lines = [
        item.reason || "",
        item.blocking_reason ? `Blocking detail: ${item.blocking_reason}` : "",
        item.warning_reason ? `Warning detail: ${item.warning_reason}` : "",
        item.rerun_rule_label ? `Rule: ${item.rerun_rule_label}` : "",
        item.rerun_rule_reason ? `Rule detail: ${item.rerun_rule_reason}` : "",
      ].filter(Boolean);
      if (!lines.length) {
        cell.textContent = "No row reason from backend preview.";
        return;
      }
      lines.forEach((line) => appendRerunText(cell, "rerun-row-reason-line", line, line));
    }

    function renderRerunPreviewDestination(cell, payload) {
      const stack = document.createElement("div");
      stack.className = "rerun-preview-destination-stack";
      const destination = rerunPolicyChoice("destination", (payload && payload.destination_mode) || "auto_replace_clean_else_pending_review").label;
      const execution = rerunExecutionLabel((payload && payload.execution_mode) || "one_at_a_time");
      appendRerunText(stack, "rerun-row-destination-line", destination, `Destination handling: ${destination}`);
      appendRerunText(stack, "rerun-row-meta", execution, `Execution: ${execution}`);
      cell.appendChild(stack);
    }

    function renderRerunPreviewRows(payload) {
      const tbody = byId("rerun-preview-rows");
      if (!tbody) return;
      clearElement(tbody);
      const rows = payload && Array.isArray(payload.rows) ? payload.rows : [];
      if (!rows.length) {
        const row = document.createElement("tr");
        appendCell(row, "No CSV rerun rows loaded.").colSpan = 6;
        tbody.appendChild(row);
        return;
      }
      rows.forEach((item) => {
        const row = document.createElement("tr");
        row.dataset.rowState = item.status || "unknown";
        const rowCell = appendCell(row, rerunPreviewRowNumber(item) || "");
        rowCell.dataset.label = "Row";
        const stateCell = appendCell(row, "", "rerun-preview-state-cell");
        stateCell.dataset.label = "State";
        renderRerunPreviewStatus(stateCell, item);
        const identityCell = appendCell(row, "", "rerun-preview-identity-cell");
        identityCell.dataset.label = "Identity";
        renderRerunPreviewIdentity(identityCell, item);
        const categoryCell = appendCell(row, "", "rerun-preview-category-cell");
        categoryCell.dataset.label = "Categories";
        renderRerunPreviewCategoryChips(categoryCell, item);
        const destinationCell = appendCell(row, "", "rerun-preview-destination-cell");
        destinationCell.dataset.label = "Destination";
        renderRerunPreviewDestination(destinationCell, payload);
        const reasonCell = appendCell(row, "", "rerun-preview-reason-cell");
        reasonCell.dataset.label = "Reason";
        renderRerunPreviewReason(reasonCell, item);
        tbody.appendChild(row);
      });
    }

    function renderRerunHistorySummary() {
      const entries = rerunHistoryEntries()
        .filter((entry) => {
          const command = String(entry.command || entry.raw?.command || "");
          return command === "rerun.start" || command === "rerun.network.start" || command === "rerun.network.start_dry_run";
        })
        .slice(0, 6);
      if (!entries.length) {
        setText("rerun-history-summary", "No CSV rerun history loaded.");
        return;
      }
      setText("rerun-history-summary", entries.map((entry) => {
        const data = rerunHistoryData(entry);
        const request = rerunHistoryRequestData(entry);
        return `${entry.started_at || entry.completed_at || entry.at || "recent"} | ${entry.ok ? "ok" : "failed"} | ${request.csv_path || data.csv_path || data.source_csv_path || ""} | ${entry.message || entry.raw?.message || ""}`;
      }).join("\n"));
    }

    function renderRerunPolicyPanel(payload) {
      const counts = rerunPreviewCounts(payload);
      const request = collectRerunStartRequest();
      const destination = rerunPolicyChoice("destination", (payload && payload.destination_mode) || request.destination_mode);
      const collision = rerunPolicyChoice("collision", (payload && payload.collision_policy) || request.collision_policy);
      const effectiveRequest = {
        ...request,
        destination_mode: (payload && payload.destination_mode) || request.destination_mode,
        collision_policy: (payload && payload.collision_policy) || request.collision_policy,
      };
      const lines = [
        `Execution: ${rerunExecutionLabel((payload && payload.execution_mode) || request.execution_mode)}; window=${(payload && payload.window_size) || request.window_size}.`,
        `Destination handling: ${destination.label}. ${destination.detail}`,
        `When output exists: ${collision.label}. ${collision.detail}`,
        rerunSourceHandlingLine(effectiveRequest),
        `Backend confirmations: replace final ${request.confirm_replace_final ? "included" : "not included"}; source overwrite ${request.confirm_source_overwrite ? "included" : "not included"}.`,
        `Blocked rows in preview: ${counts.blocked_mode_rows || 0}.`,
      ];
      setText("rerun-policy-panel", lines.join("\n"));
    }

    function selectedRerunCsvCandidate() {
      const current = String(byId("rerun-start-csv-path")?.value || "").trim().toLowerCase();
      const candidates = state.lastRerunPreviewPayload && Array.isArray(state.lastRerunPreviewPayload.recent_csvs)
        ? state.lastRerunPreviewPayload.recent_csvs
        : [];
      return candidates.find((item) => String(item.path || "").trim().toLowerCase() === current) || null;
    }

    function applyRerunOpenButtonState() {
      const selected = selectedRerunCsvCandidate();
      const canOpen = Boolean(selected?.csv_key);
      const typedHelp = "Typed CSV paths can be previewed, but Open CSV and Open Folder require a backend-known import or scoped CSV candidate.";
      [
        ["rerun-open-csv-button", canOpen ? "Open the selected backend-known CSV file." : typedHelp],
        ["rerun-open-csv-folder-button", canOpen ? "Open the folder for the selected backend-known CSV file." : typedHelp],
      ].forEach(([id, title]) => {
        const button = byId(id);
        if (!button) return;
        button.disabled = !canOpen;
        button.setAttribute("aria-disabled", canOpen ? "false" : "true");
        button.title = title;
      });
      const inspect = byId("rerun-inspect-csv-button");
      if (inspect) {
        inspect.title = "Inspect CSV by loading the backend read-only preview. Typed paths are allowed for preview.";
        inspect.setAttribute("aria-label", "Inspect selected or typed CSV using the backend preview");
      }
    }

    async function inspectSelectedRerunCsv() {
      const result = await refreshRerunPreview({ quiet: false });
      renderJsonDetail("rerun-queue-detail", {
        label: "CSV inspect",
        value: result,
        intro: "Backend read-only inspect of the selected rerun CSV.",
      });
    }

    async function openSelectedRerunCsv(target) {
      const selected = selectedRerunCsvCandidate();
      if (!selected || !selected.csv_key) {
        setText("rerun-queue-status", "CSV not in import list");
        setText("rerun-queue-detail", "Typed CSV paths can still be previewed. Open CSV and Open Folder require a backend-known import/scoped CSV candidate with csv_key.");
        applyRerunOpenButtonState();
        return;
      }
      const result = await queueRerunRouteDispatcher("postRerunOpen")({
        target,
        csv_key: selected.csv_key,
      });
      appendCommandResult(result);
      renderLaunchCommandResult("rerun-queue-status", "rerun-queue-detail", result, { target, csv_key: selected.csv_key });
    }

    function rerunResultCountsLine(manifest = {}) {
      const counts = manifest.row_status_counts && typeof manifest.row_status_counts === "object"
        ? manifest.row_status_counts
        : {};
      const entries = Object.keys(counts)
        .sort()
        .map((key) => `${key} ${counts[key]}`);
      return entries.length ? entries.join("; ") : "no row counts";
    }

    function rerunManifestTitle(manifest = {}) {
      return [
        manifest.batch_id || "rerun manifest",
        manifest.status || "unknown",
      ].filter(Boolean).join(" | ");
    }

    function renderRerunResults(payload) {
      state.lastRerunResultsPayload = payload && typeof payload === "object" ? payload : null;
      renderRerunLifecycleEvidence(state.lastRerunPreviewPayload, state.lastRerunCommandResult);
      const container = byId("rerun-results-panel");
      if (!container) return;
      clearElement(container);
      const manifests = state.lastRerunResultsPayload && Array.isArray(state.lastRerunResultsPayload.manifests)
        ? state.lastRerunResultsPayload.manifests
        : [];
      if (!manifests.length) {
        container.textContent = "No rerun results loaded.";
        return;
      }
      manifests.slice(0, 8).forEach((manifest) => {
        const item = document.createElement("div");
        item.className = "command-history-entry";
        const title = document.createElement("strong");
        title.textContent = rerunManifestTitle(manifest);
        item.appendChild(title);

        const lines = [
          `Rows: ${manifest.row_count || 0}; remaining pending ${manifest.remaining_pending_count || 0}; ${rerunResultCountsLine(manifest)}.`,
          `Mode: ${rerunExecutionLabel(manifest.execution_mode || "one_at_a_time")}; window=${manifest.window_size || 1}; destination=${manifest.destination_mode || "unknown"}; collision=${manifest.collision_policy || "unknown"}.`,
        ];
        if (manifest.current_chunk !== undefined && manifest.current_chunk !== null && manifest.current_chunk !== "") {
          lines.push(`Current chunk: ${manifest.current_chunk}.`);
        }
        if (manifest.stopped_at || manifest.stop_request_id) {
          lines.push(`Stop evidence: ${manifest.stopped_at || "not recorded"}; request ${manifest.stop_request_id || "not recorded"}.`);
        }
        if (manifest.safe_next_action) lines.push(manifest.safe_next_action);
        const detail = document.createElement("span");
        detail.textContent = lines.join(" ");
        item.appendChild(detail);

        const backendActions = Array.isArray(manifest.available_actions) ? manifest.available_actions : [];
        backendActions.slice(0, 3).forEach((action) => {
          const button = document.createElement("button");
          button.type = "button";
          button.className = "secondary-button rerun-continue-pending-button";
          button.dataset.manifestKey = manifest.manifest_key || "";
          button.dataset.rerunActionScope = String(action?.scope || "");
          button.textContent = String(action?.label || action?.action || "Run backend action");
          button.title = String(action?.confirmation_prompt || manifest.safe_next_action || "Run the backend-authored CSV rerun action.");
          button.addEventListener("click", () => {
            requestRerunContinue(action).catch(() => {});
          });
          item.appendChild(button);
        });
        container.appendChild(item);
      });
    }

    async function refreshRerunResults(options = {}) {
      try {
        const result = await queueRerunRouteDispatcher("getRerunResults")();
        renderRerunResults(result);
        return result;
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        if (!options.quiet) {
          setText("rerun-results-panel", `Rerun results failed to load: ${message}`);
        }
        return null;
      }
    }

    async function requestRerunContinue(actionOrManifestKey) {
      const action = actionOrManifestKey && typeof actionOrManifestKey === "object"
        ? actionOrManifestKey
        : {
            action: "continue_pending",
            label: "Continue Pending Rows",
            route: "/api/rerun/continue",
            request: { manifest_key: String(actionOrManifestKey || "").trim(), confirm_continue: true },
            confirmation_field: "confirm_continue",
            confirmation_prompt: "Continue pending CSV rerun rows only? Failed and review rows stay untouched.",
            request_id_required: true,
            requires_confirmation: false,
            scope: "batch_pending_only",
          };
      const request = action?.request && typeof action.request === "object" ? { ...action.request } : {};
      const key = String(request.manifest_key || "").trim();
      const actionLabel = String(action?.label || "CSV rerun action");
      if (rejectLaunchCommandWhileBusy("rerun.continue", "rerun-queue-status", "rerun-queue-detail")) return;
      if (!key) {
        const result = {
          command: "rerun.continue",
          ok: false,
          severity: "error",
          message: "No stopped rerun manifest was selected.",
        };
        appendCommandResult(result);
        renderLaunchCommandResult("rerun-queue-status", "rerun-queue-detail", result, {});
        return;
      }
      setText("rerun-queue-status", "Confirming");
      setText("rerun-queue-detail", String(action?.confirmation_prompt || actionLabel));
      await nextLaunchCommandFrame();
      setLaunchCommandBusy(true);
      setText("rerun-queue-status", `${actionLabel}...`);
      try {
        const result = await queueRerunRouteDispatcher("requestBackendRerunAction")(action);
        appendCommandResult(result);
        renderLaunchCommandResult("rerun-queue-status", "rerun-queue-detail", result, request);
        await refreshRerunResults({ quiet: true });
        if ((result.refresh_hint || "") === "snapshot") {
          await refreshAll();
        }
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        const result = {
          command: "rerun.continue",
          ok: false,
          severity: "error",
          message,
        };
        appendCommandResult(result);
        renderLaunchCommandResult("rerun-queue-status", "rerun-queue-detail", result, { manifest_key: key });
      } finally {
        setLaunchCommandBusy(false);
        applyRerunPreviewButtonState();
      }
    }

    function rerunPreviewBlockedReason(precollectedRequest = null) {
      const request = precollectedRequest && typeof precollectedRequest === "object"
        ? precollectedRequest
        : collectRerunStartRequest();
      if (!String(request.csv_path || "").trim()) return "CSV path is required before dry-run or live start.";
      if (["auto_replace_clean_else_pending_review", "publish_replace_final"].includes(request.destination_mode) && request.confirm_replace_final !== true) {
        return "Publish and replace requires backend confirmation.";
      }
      if (!state.lastRerunPreviewPayload) return "Backend CSV preview has not loaded yet.";
      const counts = rerunPreviewCounts(state.lastRerunPreviewPayload);
      if (state.lastRerunPreviewPayload.status === "blocked") {
        const conflicts = rerunPreviewConflictLines(state.lastRerunPreviewPayload);
        return conflicts[0] || state.lastRerunPreviewPayload.message || "CSV preview is blocked.";
      }
      if (Number(counts.effective_scoped_rows || 0) <= 0) return "No effective scoped rows are available.";
      return "";
    }

    function applyRerunPreviewButtonState() {
      const busy = Boolean(launchCoordinatorState.launchCommandInFlight);
      const reason = rerunPreviewBlockedReason();
      const button = byId("rerun-start-button");
      if (!button) {
        applyRerunOpenButtonState();
        renderRerunReviewHeader(state.lastRerunPreviewPayload);
        renderRerunLifecycleEvidence(state.lastRerunPreviewPayload, state.lastRerunCommandResult);
        return;
      }
      const disabled = busy || Boolean(reason);
      button.disabled = disabled;
      button.setAttribute("aria-disabled", disabled ? "true" : "false");
      button.title = disabled ? (reason || "CSV rerun command is already in progress.") : `Review backend preview and start ${rerunExecutionTargetLabel()}.`;
      button.textContent = rerunIsNetworkMode() ? "Start Network Batch" : "Review & Start";
      applyRerunOpenButtonState();
      renderRerunReviewHeader(state.lastRerunPreviewPayload);
      renderRerunLifecycleEvidence(state.lastRerunPreviewPayload, state.lastRerunCommandResult);
    }

    async function refreshRerunPreview(options = {}) {
      const request = collectRerunPreviewRequest();
      renderLaunchPreflight("rerun-queue-preflight", rerunQueuePreflightLines(collectRerunStartRequest({ dry_run: false })));
      if (!options.quiet) {
        setText("rerun-queue-status", "Reading CSV");
        setText("rerun-queue-detail", `Reading backend ${rerunExecutionTargetLabel()} preview.`);
      }
      try {
        const dispatcher = rerunIsNetworkMode() ? "postRerunNetworkPreview" : "postRerunPreview";
        const result = await queueRerunRouteDispatcher(dispatcher)(request);
        renderRerunPreview(result);
        if (!options.quiet) {
          setText("rerun-queue-status", result.status || (result.ok ? "Ready" : "Blocked"));
          renderJsonDetail("rerun-queue-detail", {
            label: "CSV rerun preview",
            value: result,
            intro: `Backend read-only CSV rerun preview from ${rerunPreviewRouteName()}.`,
          });
        }
        return result;
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        const result = {
          command: "rerun.preview",
          ok: false,
          severity: "error",
          status: "blocked",
          message,
          errors: [message],
          counts: {},
          rows: [],
          recent_csvs: [],
        };
        renderRerunPreview(result);
        if (!options.quiet) {
          setText("rerun-queue-status", "Error");
          setText("rerun-queue-detail", message);
        }
        return result;
      }
    }

    function scheduleRerunPreviewRefresh(delayMs = 350) {
      if (state.rerunPreviewRefreshTimer) window.clearTimeout(state.rerunPreviewRefreshTimer);
      state.rerunPreviewRefreshTimer = window.setTimeout(() => {
        state.rerunPreviewRefreshTimer = null;
        refreshRerunPreview({ quiet: true }).catch(() => {});
      }, Math.max(0, Number(delayMs) || 0));
    }

    function rerunCsvLeaf(value) {
      const text = String(value || "").trim();
      if (!text) return "";
      return text.split(/[\\/]/).filter(Boolean).pop() || text;
    }

    function renderRerunTopbarPending(request, actionLabel, statusLabel, waitLabel) {
      const csvLeaf = rerunCsvLeaf(request.csv_path);
      const activity = csvLeaf ? `${actionLabel} ${statusLabel}: ${csvLeaf}` : `${actionLabel} ${statusLabel}`;
      window.mediaPipelineAppTopbar?.renderTopbarActivity?.({
        activity,
        current_work: { phase_label: actionLabel },
        progress: { CurrentStage: "CSV rerun" },
      });
      window.setTopbarPendingLaunch?.({
        label: actionLabel,
        status_label: statusLabel,
        wait_label: waitLabel,
      });
    }

    function renderRerunTopbarFinished(request, actionLabel, message) {
      const csvLeaf = rerunCsvLeaf(request.csv_path);
      const activity = csvLeaf ? `${message}: ${csvLeaf}` : message;
      window.clearTopbarPendingLaunch?.();
      window.mediaPipelineAppTopbar?.renderTopbarActivity?.({
        activity,
        current_work: { phase_label: actionLabel },
        progress: { CurrentStage: "CSV rerun" },
      });
    }


    return {
      renderRerunPreviewTiles,
      rerunPreviewRowNumber,
      rerunPreviewRowText,
      pushRerunCategory,
      rerunPreviewCategoryTokens,
      renderRerunPreviewCategoryChips,
      renderRerunPreviewIdentity,
      renderRerunPreviewStatus,
      renderRerunPreviewReason,
      renderRerunPreviewDestination,
      renderRerunPreviewRows,
      renderRerunHistorySummary,
      renderRerunPolicyPanel,
      selectedRerunCsvCandidate,
      applyRerunOpenButtonState,
      inspectSelectedRerunCsv,
      openSelectedRerunCsv,
      rerunResultCountsLine,
      rerunManifestTitle,
      renderRerunResults,
      refreshRerunResults,
      requestRerunContinue,
      rerunPreviewBlockedReason,
      applyRerunPreviewButtonState,
      refreshRerunPreview,
      scheduleRerunPreviewRefresh,
      rerunCsvLeaf,
      renderRerunTopbarPending,
      renderRerunTopbarFinished,
    };
  }

  window.__launchRerunPresentationModule = { createLaunchRerunPresentationModule };
})();
