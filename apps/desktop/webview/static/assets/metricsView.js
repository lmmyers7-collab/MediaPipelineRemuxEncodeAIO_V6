(function () {
  let lastMetricsPayload = {};
  let metricsTabNavInitialized = false;
  let metricsSourceEventsInitialized = false;
  let metricsSourceCommandInFlight = false;
  const SVG_NS = "http://www.w3.org/2000/svg";
  const METRICS_TAB_STORAGE_KEY = "mediapipeline-metrics-tab";
  const countFormatter = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });

  function metricsTabIds() {
    return ["overview", "routes", "storage", "production", "workers"];
  }

  function activateMetricsTab(tabId) {
    const page = document.querySelector('[data-page-panel="metrics"]');
    if (!page) return;
    const selected = metricsTabIds().includes(tabId) ? tabId : "overview";
    const buttons = Array.from(page.querySelectorAll(".settings-tab-btn[data-metrics-tab]"));
    const panels = Array.from(page.querySelectorAll(":scope > .metrics-tab-panel[data-metrics-tab-panel]"));
    buttons.forEach((button) => {
      const active = button.dataset.metricsTab === selected;
      button.setAttribute("aria-selected", String(active));
    });
    panels.forEach((panel) => {
      panel.classList.toggle("is-active", panel.dataset.metricsTabPanel === selected);
    });
    try { localStorage.setItem(METRICS_TAB_STORAGE_KEY, selected); } catch (_error) {}
    if (typeof updatePagePanelEmptyStates === "function") updatePagePanelEmptyStates();
  }

  function initMetricsTabNav() {
    const page = document.querySelector('[data-page-panel="metrics"]');
    if (!page) return;
    const buttons = Array.from(page.querySelectorAll(".settings-tab-btn[data-metrics-tab]"));
    const panels = Array.from(page.querySelectorAll(":scope > .metrics-tab-panel[data-metrics-tab-panel]"));
    if (!buttons.length || !panels.length) return;
    if (!metricsTabNavInitialized) {
      buttons.forEach((button) => {
        button.addEventListener("click", () => activateMetricsTab(button.dataset.metricsTab || "overview"));
      });
      metricsTabNavInitialized = true;
    }
    let stored = "overview";
    try { stored = localStorage.getItem(METRICS_TAB_STORAGE_KEY) || "overview"; } catch (_error) {}
    activateMetricsTab(stored);
  }

  function initMetricsViewEvents() {
    initMetricsTabNav();
    if (metricsSourceEventsInitialized) return;
    const addButton = byId("metrics-source-add-button");
    const backfillButton = byId("metrics-backfill-button");
    const sourceRows = byId("metrics-sources-rows");
    if (addButton) addButton.addEventListener("click", requestMetricsSourceAdd);
    if (backfillButton) backfillButton.addEventListener("click", () => requestMetricsBackfill({ scope: "enabled" }));
    if (sourceRows) {
      sourceRows.addEventListener("click", (event) => {
        const button = event.target?.closest?.("[data-metrics-source-action]");
        if (!button) return;
        const action = button.dataset.metricsSourceAction || "";
        const sourceId = button.dataset.sourceId || "";
        if (action === "scan") {
          requestMetricsBackfill({ source_id: sourceId });
        } else if (["enable", "disable", "remove"].includes(action)) {
          requestMetricsSourceAction(action, { source_id: sourceId });
        }
      });
    }
    metricsSourceEventsInitialized = true;
  }

  function numberValue(value) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : 0;
  }

  function integerText(value) {
    return countFormatter.format(Math.round(numberValue(value)));
  }

  function percentText(value) {
    if (value === null || value === undefined || value === "") return "-";
    const parsed = Number(value);
    return Number.isFinite(parsed) ? `${parsed.toFixed(1)}%` : "-";
  }

  function textValue(value, fallback = "") {
    const text = String(value ?? "").trim();
    return text || fallback;
  }

  function countLabel(count, singular, plural = `${singular}s`) {
    const value = Math.round(numberValue(count));
    return `${integerText(value)} ${value === 1 ? singular : plural}`;
  }

  function fixedText(value, digits = 1) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed.toFixed(digits) : "0.0";
  }

  function gbText(value) {
    return `${fixedText(value, 1)} GB`;
  }

  function gbhText(value) {
    return `${fixedText(value, 1)} GB/h`;
  }

  function timeText(value) {
    return textValue(value, "not available");
  }

  function postMetricsCommand(path, payload, options = {}) {
    const post = typeof apiPost === "function" ? apiPost : window.apiPost;
    if (typeof post !== "function") return Promise.reject(new Error("apiPost is not available."));
    return post(path, payload, options);
  }

  function appendMetricsCommandResult(result) {
    const append = typeof appendCommandResult === "function" ? appendCommandResult : window.appendCommandResult;
    if (typeof append === "function") append(result);
  }

  function refreshMetricsAfterCommand(reason) {
    const refresh = typeof refreshAllNow === "function" ? refreshAllNow : window.refreshAllNow;
    if (typeof refresh === "function") {
      return refresh({ reason }).catch(() => {});
    }
    return Promise.resolve();
  }

  function setMetricsSourceControlsBusy(busy) {
    metricsSourceCommandInFlight = Boolean(busy);
    [
      byId("metrics-source-add-button"),
      byId("metrics-backfill-button"),
      ...Array.from(document.querySelectorAll("[data-metrics-source-action]")),
    ].forEach((button) => {
      if (!button) return;
      button.disabled = metricsSourceCommandInFlight;
      button.setAttribute("aria-busy", String(metricsSourceCommandInFlight));
    });
  }

  function entriesFromCounts(counts) {
    return Object.entries(counts || {})
      .map(([label, value]) => ({ label, value: numberValue(value), text: integerText(value) }))
      .sort((left, right) => right.value - left.value || String(left.label).localeCompare(String(right.label)));
  }

  function toneForLabel(label) {
    const normalized = String(label || "").toLowerCase();
    if (normalized.includes("encode")) return "encode";
    if (normalized.includes("saved") || normalized.includes("remux")) return "storage";
    if (normalized.includes("growth") || normalized.includes("fail")) return "failed";
    if (normalized.includes("pending")) return "pending";
    if (normalized.includes("worker") || normalized.includes("active") || normalized.includes("done")) return "worker";
    return "";
  }

  function renderMetricChart(containerId, rows, emptyText) {
    const container = byId(containerId);
    if (!container) return;
    const entries = Array.isArray(rows) ? rows.filter((row) => row && String(row.label || "").trim()) : [];
    container.replaceChildren();
    if (!entries.length) {
      const note = document.createElement("p");
      note.className = "note";
      note.textContent = emptyText || "No metrics loaded.";
      container.appendChild(note);
      return;
    }
    const chartEntries = entries.filter((row) => !row.valueOnly);
    const maxValue = Math.max(1, ...chartEntries.map((row) => Math.abs(numberValue(row.value))));
    entries.forEach((entry) => {
      const labelText = textValue(entry.label, "Metric");
      const valueText = textValue(entry.text, String(entry.value ?? ""));
      const row = document.createElement("div");
      row.className = "metrics-chart-row";
      const label = document.createElement("span");
      label.className = "metrics-chart-label";
      label.textContent = labelText;
      const valueLabel = document.createElement("span");
      valueLabel.className = "metrics-chart-value";
      valueLabel.textContent = valueText;
      if (entry.valueOnly) {
        const spacer = document.createElement("span");
        spacer.setAttribute("aria-hidden", "true");
        row.classList.add("metrics-chart-row--value-only");
        row.append(label, spacer, valueLabel);
        container.appendChild(row);
        return;
      }
      const value = Math.abs(numberValue(entry.value));
      const percent = Math.max(0, Math.min(100, (value / maxValue) * 100));
      const tone = entry.tone || toneForLabel(entry.label);
      const image = document.createElementNS(SVG_NS, "svg");
      image.classList.add("metrics-chart-image");
      image.setAttribute("viewBox", "0 0 100 14");
      image.setAttribute("preserveAspectRatio", "none");
      image.setAttribute("role", "img");
      image.setAttribute("aria-label", `${labelText}: ${valueText}`);
      image.dataset.metricPercent = percent.toFixed(1);
      if (tone) image.dataset.metricTone = tone;
      const title = document.createElementNS(SVG_NS, "title");
      title.textContent = `${labelText}: ${valueText}`;
      const track = document.createElementNS(SVG_NS, "rect");
      track.classList.add("metrics-chart-svg-track");
      track.setAttribute("x", "0");
      track.setAttribute("y", "1");
      track.setAttribute("width", "100");
      track.setAttribute("height", "12");
      track.setAttribute("rx", "2");
      const fill = document.createElementNS(SVG_NS, "rect");
      fill.classList.add("metrics-chart-svg-fill");
      fill.setAttribute("x", "0");
      fill.setAttribute("y", "1");
      fill.setAttribute("width", percent.toFixed(1));
      fill.setAttribute("height", "12");
      fill.setAttribute("rx", "2");
      if (tone) fill.dataset.metricTone = tone;
      image.append(title, track, fill);
      row.append(label, image, valueLabel);
      container.appendChild(row);
    });
  }

  function renderCountRows(tbodyId, counts, emptyText) {
    const tbody = byId(tbodyId);
    if (!tbody) return;
    const entries = entriesFromCounts(counts);
    if (!entries.length) {
      clearRows(tbody, 2, emptyText || "No rows loaded.");
      return;
    }
    tbody.replaceChildren();
    entries.forEach((entry) => {
      const row = document.createElement("tr");
      appendCells(row, [entry.label, entry.text], [null, "num"]);
      tbody.appendChild(row);
    });
  }

  function renderAttentionRows(items) {
    const tbody = byId("metrics-attention-rows");
    const rows = Array.isArray(items) ? items : [];
    setText("metrics-attention-status", rows.length ? countLabel(rows.length, "item") : "Clear");
    if (!tbody) return;
    if (!rows.length) {
      clearRows(tbody, 5, "No attention items in the loaded metrics.");
      return;
    }
    tbody.replaceChildren();
    rows.forEach((item) => {
      const row = document.createElement("tr");
      appendCells(row, [
        textValue(item.severity, "info"),
        textValue(item.label, "Attention item"),
        textValue(item.value, "Review"),
        textValue(item.detail, "not available"),
        textValue(item.target_subtab, "overview"),
      ], [null, null, "num", null, null]);
      tbody.appendChild(row);
    });
  }

  function renderCoverageRows(coverage) {
    const tbody = byId("metrics-coverage-rows");
    const payload = coverage || {};
    setText("metrics-coverage-status", `${percentText(payload.measurement_percent)} measured`);
    if (!tbody) return;
    const rows = [
      ["Completed rows", integerText(payload.completed_rows), "Completed manifest rows included in Metrics."],
      ["Measured rows", integerText(payload.measured_rows), "Rows with source and output byte measurements."],
      ["Excluded rows", integerText(payload.excluded_rows), "Rows excluded from storage savings math."],
      ["Measurement coverage", percentText(payload.measurement_percent), "Measured rows divided by completed rows."],
      ["Sources enabled", `${integerText(payload.enabled_source_count)}/${integerText(payload.source_count)}`, "Configured Metrics sidecar source roots."],
      ["Cached backfill", integerText(payload.cached_backfill_count), "Enabled source sidecar records loaded into Metrics cache."],
      ["Last backfill", textValue(payload.last_backfill_status, "not run"), `Loaded ${integerText(payload.last_backfill_loaded_count)}; sidecars ${integerText(payload.last_backfill_sidecar_count)}; errors ${integerText(payload.last_backfill_error_count)}.`],
    ];
    tbody.replaceChildren();
    rows.forEach((item) => {
      const row = document.createElement("tr");
      appendCells(row, item, [null, "num", null]);
      tbody.appendChild(row);
    });
  }

  function renderReasonGroupRows(reasonGroups) {
    const tbody = byId("metrics-reason-group-rows");
    const rows = Array.isArray(reasonGroups) ? reasonGroups : [];
    setText("metrics-reason-group-status", rows.length ? countLabel(rows.length, "group") : "No groups");
    if (!tbody) return;
    if (!rows.length) {
      clearRows(tbody, 5, "No route reason groups loaded.");
      return;
    }
    tbody.replaceChildren();
    rows.forEach((item) => {
      const row = document.createElement("tr");
      appendCells(row, [
        textValue(item.label, "Unknown decision reason"),
        integerText(item.count),
        percentText(item.percent),
        textValue(item.severity, "info"),
        (item.codes || []).join(", ") || "unknown",
      ], [null, "num", "num", null, null]);
      tbody.appendChild(row);
    });
  }

  function renderThroughputRows(throughput) {
    const payload = throughput || {};
    const series = Array.isArray(payload.recent_daily_completion_series) ? payload.recent_daily_completion_series : [];
    const tbody = byId("metrics-throughput-rows");
    setText(
      "metrics-throughput-status",
      `${integerText(payload.recent_completed_count)} recent; ${textValue(payload.recent_output_per_day_text, "0 B")}/day`
    );
    if (tbody) {
      if (!series.length) {
        clearRows(tbody, 5, "No recent completion series loaded.");
      } else {
        tbody.replaceChildren();
        series.forEach((item) => {
          const row = document.createElement("tr");
          appendCells(row, [
            textValue(item.date, "unknown"),
            integerText(item.completed_count),
            textValue(item.output_text, "0 B"),
            integerText(item.remux),
            integerText(item.encode),
          ], [null, "num", "num", "num", "num"]);
          tbody.appendChild(row);
        });
      }
    }
    setText("metrics-throughput-detail", [
      `Jobs/day: ${fixedText(payload.recent_jobs_per_day, 1)}`,
      `GB/day: ${textValue(payload.recent_output_per_day_text, "0 B")}`,
      `Last completed: ${timeText(payload.last_completed_at)}`,
      `Recent window: ${integerText(payload.recent_day_count)} day(s), ${integerText(payload.recent_completed_count)} completed, ${textValue(payload.recent_output_text, "0 B")} output.`,
    ].join("\n"));
  }

  function renderWorkerPosture(workers) {
    const posture = workers?.posture || {};
    setText("metrics-worker-posture", [
      `Posture: ${textValue(posture.posture, "not loaded")}`,
      `Role: ${textValue(posture.role, "standalone")}`,
      `Active/idle/problem: ${integerText(posture.active_count)}/${integerText(posture.idle_count)}/${integerText(posture.problem_count)}`,
      `Warnings: ${integerText(posture.warning_count)}; failed sessions: ${integerText(posture.failed_session_count)}`,
      `Handoff: ${textValue(posture.handoff_label, "Open Workers")} -> ${textValue(posture.handoff_target, "network")}`,
      textValue(posture.detail, "not available"),
    ].join("\n"));
  }

  function sourceEvidenceLines(payload) {
    const evidence = payload?.source_evidence || {};
    const completed = evidence.completed_manifest || {};
    const pending = evidence.pending_publish || {};
    const workers = evidence.workers || {};
    const finalLibrary = evidence.final_library || {};
    const backfill = evidence.metrics_backfill || {};
    return [
      `Authority: ${evidence.evidence_authority || "backend"}`,
      `Completed manifest: ${completed.source || "(not resolved)"}`,
      `Completed records: ${completed.record_count || 0}; proof mode=${completed.proof_mode || "summary"}`,
      `Metrics backfill: ${backfill.enabled_source_count || 0}/${backfill.source_count || 0} source(s) enabled; cached=${backfill.enabled_cache_record_count || 0}; cache=${backfill.cache_path || "(not configured)"}`,
      `Pending publish: ${pending.row_count || 0} row(s); payloads=${pending.payload_count || 0}; source=${pending.source || "(not resolved)"}`,
      `Workers: ${workers.row_count || 0} row(s); source=${workers.source || "runtime_state_files"}`,
      `Final library: enabled=${finalLibrary.enabled ? "yes" : "no"}; count limit=${finalLibrary.count_limit || 0}`,
      `Generated: ${payload.generated_at || ""}`,
    ];
  }

  function sourceBackfillRows(sourceBackfill) {
    return Array.isArray(sourceBackfill?.roots) ? sourceBackfill.roots : [];
  }

  function sourceCachedCount(row) {
    return numberValue(row.last_scan_loaded_count || 0);
  }

  function sourceStateText(row) {
    if (!row.enabled) return "Disabled";
    if (row.is_directory) return "Ready";
    if (row.exists === false) return "Offline";
    return "Needs review";
  }

  function appendSourceActionButton(container, label, action, sourceId) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "metrics-source-row-action";
    button.dataset.metricsSourceAction = action;
    button.dataset.sourceId = sourceId || "";
    button.textContent = label;
    button.disabled = metricsSourceCommandInFlight;
    button.setAttribute("aria-busy", String(metricsSourceCommandInFlight));
    container.appendChild(button);
  }

  function renderMetricsSourceRows(rows) {
    const tbody = byId("metrics-sources-rows");
    if (!tbody) return;
    if (!rows.length) {
      clearRows(tbody, 5, "No Metrics source roots configured.");
      return;
    }
    tbody.replaceChildren();
    rows.forEach((item) => {
      const row = document.createElement("tr");
      const sourceCell = document.createElement("td");
      sourceCell.textContent = `${textValue(item.label, "Source")} - ${textValue(item.path, "(path missing)")}`;
      const stateCell = document.createElement("td");
      stateCell.textContent = sourceStateText(item);
      const cachedCell = document.createElement("td");
      cachedCell.className = "num";
      cachedCell.textContent = integerText(sourceCachedCount(item));
      const scanCell = document.createElement("td");
      scanCell.textContent = textValue(item.last_scan_at, "Never");
      const actionsCell = document.createElement("td");
      const actions = document.createElement("div");
      actions.className = "metrics-source-actions";
      appendSourceActionButton(actions, "Scan", "scan", item.source_id);
      appendSourceActionButton(actions, item.enabled ? "Disable" : "Enable", item.enabled ? "disable" : "enable", item.source_id);
      appendSourceActionButton(actions, "Remove", "remove", item.source_id);
      actionsCell.appendChild(actions);
      row.append(sourceCell, stateCell, cachedCell, scanCell, actionsCell);
      tbody.appendChild(row);
    });
  }

  function renderSourceBackfill(payload) {
    const sourceBackfill = payload?.source_backfill || {};
    const rows = sourceBackfillRows(sourceBackfill);
    const sourceCount = numberValue(sourceBackfill.source_count);
    const enabledCount = numberValue(sourceBackfill.enabled_source_count);
    const cachedCount = numberValue(sourceBackfill.enabled_cache_record_count ?? sourceBackfill.cache_record_count);
    setText("metrics-sources-status", `${enabledCount}/${sourceCount} enabled`);
    renderMetricsSourceRows(rows);
    const lastBackfill = sourceBackfill.last_backfill || {};
    setText("metrics-backfill-detail", [
      `Registry: ${sourceBackfill.registry_path || "(not configured)"}`,
      `Cache: ${sourceBackfill.cache_path || "(not configured)"}`,
      `Configured sources: ${sourceCount}; enabled: ${enabledCount}; cached records: ${cachedCount}`,
      `Last backfill status: ${lastBackfill.status || "never"}`,
      `Last backfill loaded: ${lastBackfill.loaded_count || 0}; sidecars seen: ${lastBackfill.sidecar_count || 0}; errors: ${lastBackfill.error_count || 0}`,
    ].join("\n"));
    setMetricsSourceControlsBusy(metricsSourceCommandInFlight);
  }

  async function requestMetricsSourceAdd() {
    if (metricsSourceCommandInFlight) return;
    const pathInput = byId("metrics-source-path");
    const labelInput = byId("metrics-source-label");
    const path = textValue(pathInput?.value);
    const label = textValue(labelInput?.value);
    if (!path) {
      appendMetricsCommandResult({
        command: "metrics.sources",
        ok: false,
        severity: "error",
        message: "Metrics source path is required.",
      });
      return;
    }
    await requestMetricsSourceAction("add", { path, label, enabled: true });
    if (pathInput) pathInput.value = "";
    if (labelInput) labelInput.value = "";
  }

  async function requestMetricsSourceAction(action, payload) {
    if (metricsSourceCommandInFlight) return;
    setMetricsSourceControlsBusy(true);
    try {
      const result = await postMetricsCommand("/api/metrics/sources", { action, ...(payload || {}) }, { timeoutMs: 15000 });
      appendMetricsCommandResult(result);
      await refreshMetricsAfterCommand("metrics-source-update");
    } catch (error) {
      appendMetricsCommandResult({
        command: "metrics.sources",
        ok: false,
        severity: "error",
        message: `Metrics source update failed: ${error?.message || error}`,
      });
    } finally {
      setMetricsSourceControlsBusy(false);
    }
  }

  async function requestMetricsBackfill(payload) {
    if (metricsSourceCommandInFlight) return;
    setMetricsSourceControlsBusy(true);
    try {
      const result = await postMetricsCommand("/api/metrics/backfill", payload || { scope: "enabled" }, { timeoutMs: 0 });
      appendMetricsCommandResult(result);
      await refreshMetricsAfterCommand("metrics-backfill");
    } catch (error) {
      appendMetricsCommandResult({
        command: "metrics.backfill",
        ok: false,
        severity: "error",
        message: `Metrics backfill failed: ${error?.message || error}`,
      });
    } finally {
      setMetricsSourceControlsBusy(false);
    }
  }

  function renderOverview(payload) {
    const overview = payload.overview || {};
    const routeMix = payload.route_mix || {};
    const storage = payload.storage || {};
    setText("metrics-total-jobs", integerText(overview.total_jobs));
    setText("metrics-remux-count", integerText(overview.remux_count));
    setText("metrics-encode-count", integerText(overview.encode_count));
    setText("metrics-storage-saved", textValue(overview.net_storage_saved_text, "0 B"));
    setText("metrics-data-produced", textValue(overview.total_data_produced_text, "0 B"));
    setText("metrics-pending-bytes", textValue(overview.pending_publish_text, "0 B"));
    setText("metrics-overview-status", countLabel(overview.total_jobs, "job"));
    setText("metrics-evidence-status", payload.generated_at ? "Loaded" : "No sources");
    setText("metrics-summary", (payload.summary_lines || []).join("\n") || "No metrics loaded.");
    setText("metrics-source-evidence", sourceEvidenceLines(payload).join("\n"));
    renderAttentionRows(payload.attention_items || []);
    renderCoverageRows(payload.coverage || {});
    renderSourceBackfill(payload);
    renderMetricChart("metrics-overview-bars", [
      { label: "Remux", value: overview.remux_count, text: `${integerText(overview.remux_count)} (${percentText(routeMix.remux_percent)})`, tone: "storage" },
      { label: "Encode", value: overview.encode_count, text: `${integerText(overview.encode_count)} (${percentText(routeMix.encode_percent)})`, tone: "encode" },
      { label: "Other", value: overview.other_route_count, text: `${integerText(overview.other_route_count)} (${percentText(routeMix.other_route_percent)})` },
    ], "No route metrics loaded.");
    setText("metrics-storage-status", `${integerText(storage.measurement_row_count)} measured`);
  }

  function renderRouteSeries(rows) {
    const tbody = byId("metrics-route-series-rows");
    const series = Array.isArray(rows) ? rows : [];
    if (!tbody) return;
    if (!series.length) {
      clearRows(tbody, 5, "No route series loaded.");
      return;
    }
    tbody.replaceChildren();
    series.forEach((item) => {
      const row = document.createElement("tr");
      appendCells(row, [
        item.date || "unknown",
        integerText(item.remux),
        integerText(item.encode),
        integerText(item.other),
        integerText(item.total),
      ], [null, "num", "num", "num", "num"]);
      tbody.appendChild(row);
    });
  }

  function renderRoutes(payload) {
    const routeMix = payload.route_mix || {};
    setText("metrics-route-status", countLabel(routeMix.total_jobs, "job"));
    const groupCounts = routeMix.route_group_counts || {};
    renderMetricChart("metrics-route-bars", [
      { label: "Remux", value: groupCounts.remux || 0, text: `${integerText(groupCounts.remux)} (${percentText(routeMix.remux_percent)})`, tone: "storage" },
      { label: "Encode", value: groupCounts.encode || 0, text: `${integerText(groupCounts.encode)} (${percentText(routeMix.encode_percent)})`, tone: "encode" },
      { label: "Other", value: groupCounts.other || 0, text: `${integerText(groupCounts.other)} (${percentText(routeMix.other_route_percent)})` },
    ], "No route metrics loaded.");
    renderReasonGroupRows(routeMix.reason_groups || []);
    renderRouteSeries(routeMix.series || []);
    const reasonLines = entriesFromCounts(routeMix.route_reason_code_counts || {})
      .slice(0, 8)
      .map((entry) => `${entry.label}: ${entry.text}`);
    const encoderLines = entriesFromCounts(routeMix.encoder_counts || {})
      .slice(0, 8)
      .map((entry) => `${entry.label}: ${entry.text}`);
    setText("metrics-route-detail", [
      "Route counts:",
      ...entriesFromCounts(routeMix.route_counts || {}).map((entry) => `- ${entry.label}: ${entry.text}`),
      "",
      "Reason codes:",
      ...(reasonLines.length ? reasonLines.map((line) => `- ${line}`) : ["- none"]),
      "",
      "Encoders:",
      ...(encoderLines.length ? encoderLines.map((line) => `- ${line}`) : ["- none"]),
    ].join("\n"));
  }

  function renderStorageBreakdown(rows) {
    const tbody = byId("metrics-storage-breakdown-rows");
    const entries = Array.isArray(rows) ? rows : [];
    if (!tbody) return;
    if (!entries.length) {
      clearRows(tbody, 8, "No storage breakdown loaded.");
      return;
    }
    tbody.replaceChildren();
    entries.forEach((item) => {
      const row = document.createElement("tr");
      appendCells(row, [
        item.route_group || "unknown",
        integerText(item.count),
        integerText(item.measured_count),
        integerText(item.excluded_count),
        item.source_size_text || "0 B",
        item.output_size_text || "0 B",
        item.net_storage_saved_text || "0 B",
        percentText(item.net_storage_saved_percent),
      ], [null, "num", "num", "num", "num", "num", "num", "num"]);
      tbody.appendChild(row);
    });
  }

  function renderStorageTopRows(tbodyId, statusId, rows, emptyText, valueKey) {
    const tbody = byId(tbodyId);
    const entries = Array.isArray(rows) ? rows : [];
    setText(statusId, entries.length ? countLabel(entries.length, "row") : "No rows");
    if (!tbody) return;
    if (!entries.length) {
      clearRows(tbody, 3, emptyText);
      return;
    }
    tbody.replaceChildren();
    entries.forEach((item) => {
      const row = document.createElement("tr");
      appendCells(row, [
        item.title || item.row_key || "",
        item.route_label || item.route || "",
        item[valueKey] || item.storage_saved_text || item.size_delta_text || "",
      ], [null, null, "num"]);
      tbody.appendChild(row);
    });
  }

  function renderStorage(payload) {
    const storage = payload.storage || {};
    setText("metrics-storage-status", `${integerText(storage.measurement_row_count)} measured`);
    renderMetricChart("metrics-storage-bars", [
      { label: "Net saved", value: storage.net_storage_saved_bytes || 0, text: storage.net_storage_saved_text || "0 B", tone: "storage" },
      { label: "Gross saved", value: storage.gross_storage_saved_bytes || 0, text: storage.gross_storage_saved_text || "0 B", tone: "storage" },
      { label: "Output growth", value: storage.output_growth_bytes || 0, text: storage.output_growth_text || "+0 B", tone: "growth" },
      { label: "Output written", value: storage.output_written_bytes || 0, text: storage.output_written_text || "0 B", tone: "pending", valueOnly: true },
      { label: "Pending parked output", value: storage.pending_parked_output_bytes || 0, text: storage.pending_parked_output_text || "0 B", tone: "pending", valueOnly: true },
    ], "No storage metrics loaded.");
    renderStorageBreakdown(storage.breakdown || []);
    renderStorageTopRows("metrics-top-savings-rows", "metrics-top-savings-status", storage.top_savings || [], "No savings rows loaded.", "storage_saved_text");
    renderStorageTopRows("metrics-top-growth-rows", "metrics-top-growth-status", storage.top_growth || [], "No growth rows loaded.", "size_delta_text");
  }

  function renderProduction(payload) {
    const production = payload.production || {};
    const pending = production.pending_publish || {};
    const finalLibrary = production.final_library || {};
    setText("metrics-production-status", countLabel(production.completed_count, "completed job"));
    setText("metrics-pending-status", `${integerText(production.pending_publish_count)} pending`);
    setText("metrics-final-library-status", finalLibrary.enabled ? "Enabled" : "Disabled");
    renderThroughputRows(production.throughput || {});
    renderMetricChart("metrics-production-bars", [
      { label: "Completed output", value: production.completed_output_bytes || 0, text: production.completed_output_text || "0 B", tone: "storage" },
      { label: "Pending publish", value: production.pending_publish_bytes || 0, text: production.pending_publish_text || "0 B", tone: "pending" },
      { label: "Known total", value: production.known_output_plus_pending_bytes || 0, text: production.known_output_plus_pending_text || "0 B" },
    ], "No production metrics loaded.");
    renderCountRows("metrics-pending-state-rows", pending.state_counts || {}, "No pending publish metrics loaded.");
    renderCountRows("metrics-final-library-rows", finalLibrary.counts || {}, "No final-library metrics loaded.");
    setText("metrics-production-detail", [
      `Completed output: ${production.completed_output_text || "0 B"}`,
      `Pending publish: ${integerText(production.pending_publish_count)} row(s), ${production.pending_publish_text || "0 B"}`,
      `Pending issues: ${integerText(pending.issue_count)}; ready: ${integerText(pending.ready_count)}; missing local: ${integerText(pending.missing_local_count)}`,
      `Known output plus pending: ${production.known_output_plus_pending_text || "0 B"}`,
      `Final library pause state: ${finalLibrary.pause_state || "unknown"}`,
    ].join("\n"));
  }

  function renderWorkers(payload) {
    const workers = payload.workers || {};
    const coordinator = workers.coordinator || {};
    const rows = Array.isArray(workers.rows) ? workers.rows : [];
    const posture = workers.posture || {};
    setText("metrics-worker-status", `${integerText(workers.worker_count)} worker row(s)`);
    setText("metrics-worker-role", workers.role || "standalone");
    setText("metrics-worker-count", integerText(workers.worker_count));
    setText("metrics-worker-active", integerText(workers.active_count));
    setText("metrics-worker-session-completed", integerText(workers.session_completed));
    setText("metrics-worker-session-failed", integerText(workers.session_failed));
    setText("metrics-worker-encoded-gb", gbText(workers.worker_encoded_gb_total));
    setText("metrics-worker-average-gbh", gbhText(workers.average_speed_gbh));
    setText("metrics-worker-warnings", integerText(posture.warning_count));
    renderWorkerPosture(workers);
    renderMetricChart("metrics-worker-bars", [
      { label: "Active workers", value: workers.active_count || 0, text: integerText(workers.active_count), tone: "worker" },
      { label: "Idle workers", value: workers.idle_count || 0, text: integerText(workers.idle_count) },
      { label: "Problem workers", value: posture.problem_count || 0, text: integerText(posture.problem_count), tone: "failed" },
      { label: "Session done", value: workers.session_completed || 0, text: integerText(workers.session_completed), tone: "storage" },
      { label: "Session failed", value: workers.session_failed || 0, text: integerText(workers.session_failed), tone: "failed" },
      { label: "Average speed", value: workers.average_speed_gbh || 0, text: gbhText(workers.average_speed_gbh), tone: "worker", valueOnly: true },
    ], "No worker metrics loaded.");
    setText("metrics-worker-coordinator", [
      `Role: ${workers.role || "standalone"}`,
      `Coordinator in-flight: ${coordinator.inflight_path || "(not resolved)"}`,
      `Cluster log: ${coordinator.cluster_log_path || "(not resolved)"}`,
      `Worker state: ${coordinator.worker_state_path || "(not resolved)"}`,
      `Active claims: ${integerText(coordinator.active_claims)}`,
      `Idle workers: ${integerText(coordinator.idle_workers)}`,
      `Session completed: ${integerText(coordinator.session_completed)}`,
      `Session failed: ${integerText(coordinator.session_failed)}`,
      `Unavailable counts: ${(coordinator.unavailable_counts || []).join(", ") || "none"}`,
    ].join("\n"));
    renderWorkerRows(rows);
  }

  function renderWorkerRows(rows) {
    const tbody = byId("metrics-worker-rows");
    const entries = Array.isArray(rows) ? rows : [];
    if (!tbody) return;
    if (!entries.length) {
      clearRows(tbody, 6, "No worker metrics loaded.");
      return;
    }
    tbody.replaceChildren();
    entries.forEach((item) => {
      const row = document.createElement("tr");
      appendCells(row, [
        item.worker_name || item.worker_id || "",
        item.status || "",
        integerText(item.files_completed),
        gbText(item.total_gb_encoded),
        gbhText(item.avg_speed_gbh),
        item.current_stage || "",
      ], [null, null, "num", "num", "num", null]);
      tbody.appendChild(row);
    });
  }

  function renderMetrics(metrics) {
    initMetricsTabNav();
    const payload = metrics && typeof metrics === "object" ? metrics : {};
    lastMetricsPayload = payload;
    renderOverview(payload);
    renderRoutes(payload);
    renderStorage(payload);
    renderProduction(payload);
    renderWorkers(payload);
  }

  /**
   * Public namespace for the Metrics page module.
   * Prefer this namespace from new code; flat window.* exports are intentionally not provided for this read-only page.
   */
  window.mediaPipelineMetricsView = {
    activateMetricsTab,
    initMetricsTabNav,
    initMetricsViewEvents,
    renderSourceBackfill,
    requestMetricsBackfill,
    requestMetricsSourceAction,
    renderMetrics,
    lastMetricsPayload: () => lastMetricsPayload,
  };
})();
