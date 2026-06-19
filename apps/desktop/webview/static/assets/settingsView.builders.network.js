(function () {
  function createNetworkSettingsBuilder(deps) {
    const {
      byId,
      formatSettingsChoiceLabel,
      networkSettingsBuilderFields,
      networkSettingsBuilderState,
      readSettingsBuilderNumber,
      refreshSettingsSelectChoices,
      setSettingsBuilderControl,
      setText,
      settingsBuilderConfigValue,
      settingsBuilderInputValue,
      settingsFieldDefinition,
      runNetworkWorkerTestConnection,
      writeSettingsPatchJson,
    } = deps;
    const roleSetupState = {
      bound: false,
      currentRole: "standalone",
      lastFocus: null,
    };
    const roleSetupConfig = {
      coordinator: {
        title: "Coordinator Setup",
        designation: "Coordinator",
        summary: "Coordinator setup defines the local coordinator endpoint and heartbeat policy. It stages saved settings only.",
      },
      worker: {
        title: "Worker Setup",
        designation: "Worker only",
        summary: "Worker setup connects this computer to a coordinator and stages worker-specific path and override settings.",
      },
      coordinator_local: {
        title: "Coordinator + Local Worker Setup",
        designation: "Coordinator + local worker",
        summary: "Coordinator + local worker setup defines the coordinator endpoint and marks this computer for local worker processing through Network lifecycle controls.",
      },
    };
    const pathMapEditors = {
      "settings-network-path-map": {
        textareaId: "settings-network-path-map",
        rowsId: "settings-network-path-map-rows",
        addButtonId: "settings-network-path-map-add-row",
        statusId: "settings-network-path-map-status",
        resultId: "settings-network-path-map-test-result",
      },
      "network-role-setup-path-map": {
        textareaId: "network-role-setup-path-map",
        rowsId: "network-role-setup-path-map-rows",
        addButtonId: "network-role-setup-path-map-add-row",
        statusId: "network-role-setup-path-map-status",
        resultId: "network-role-setup-path-map-test-result",
      },
    };
    const networkSettingTips = {
      "settings-network-role": "What it means: this computer's distributed processing designation. Suggested: keep Standalone for one-computer use; choose Coordinator only for the machine that assigns work; choose Worker only for machines that claim work; choose Coordinator + local worker when this coordinator should also process assigned local work.",
      "settings-network-coordinator-port": "What it means: TCP port used by the coordinator HTTP endpoint. Suggested: 7830 unless another local service already uses it.",
      "settings-network-bind-address": "What it means: network interface the coordinator listens on. Suggested: 0.0.0.0 for LAN workers; 127.0.0.1 for local-only tests.",
      "settings-network-heartbeat-timeout": "What it means: minutes before a quiet worker is treated as stale. Suggested: 5 to 10 minutes for normal local-network workers.",
      "settings-network-worker-url": "What it means: base URL this worker uses to reach the coordinator. Suggested: http://<coordinator-ip>:7830, matching the coordinator port. Do not use 0.0.0.0 or :: because those are listen addresses, not worker targets.",
      "settings-network-worker-name": "What it means: unique display name for this worker in coordinator state. Suggested: the Windows computer name or a short role name such as BEAST-PC.",
      "settings-network-worker-poll": "What it means: seconds between worker claim checks. Suggested: 10 to 15 seconds; use 5 only when you need faster pickup.",
      "settings-network-coordinator-local-encode": "What it means: lets the coordinator also process local encode work. Suggested: off for a dedicated coordinator; on when this computer should help encode.",
      "settings-network-path-map": "What it means: rows that rewrite coordinator source paths to paths visible on this worker, saved as the WorkerSourcePathMap JSON object. Suggested: {} when paths match; otherwise map each source root, for example From D:/Source to //SERVER/Source.",
      "settings-network-worker-encoder-map": "What it means: worker-owned hardware map from coordinator codec families to local encoders, for example {\"hevc\":\"hevc_nvenc\",\"h264\":\"h264_nvenc\",\"av1\":\"av1_nvenc\"}. Suggested: use supported local hardware encoders on this worker; leave blank only for CPU fallback.",
      "settings-network-honor-coordinator-policy": "What it means: makes this worker apply coordinator cluster-authoritative per-library codec family, quality tier, output container, routing, audio, and subtitle policy. Suggested: leave disabled until real-media validation proves this worker's encoder map and output policy.",
      "settings-network-worker-overrides": "What it means: JSON object with optional per-worker config overrides. Suggested: {} unless a specific worker needs tuning, for example {\"BEAST-PC\":{\"VideoPreset\":\"p4\"}}.",
    };

    function appendDescribedBy(element, tipId) {
      const current = new Set(String(element.getAttribute("aria-describedby") || "").split(/\s+/).filter(Boolean));
      current.add(tipId);
      element.setAttribute("aria-describedby", Array.from(current).join(" "));
    }

    function setNetworkSettingTip(element, tip) {
      if (!element || !tip) return;
      element.title = tip;
      const label = element.closest("label");
      if (label) label.title = tip;
      const editor = byId(`${element.id}-editor`);
      if (editor) editor.title = tip;
      const tipId = `${element.id}-tip`;
      let tipNode = byId(tipId);
      if (!tipNode) {
        tipNode = document.createElement("span");
        tipNode.id = tipId;
        tipNode.className = "visually-hidden";
        element.insertAdjacentElement("afterend", tipNode);
      }
      tipNode.textContent = tip;
      appendDescribedBy(element, tipId);
    }

    function applyNetworkSettingTips() {
      Object.entries(networkSettingTips).forEach(([id, tip]) => {
        setNetworkSettingTip(byId(id), tip);
      });
      roleSetupFields().forEach((field) => {
        const sourceId = field.dataset.roleSetupSource || "";
        setNetworkSettingTip(field, networkSettingTips[sourceId]);
      });
    }

    function workerCoordinatorUrlIssue(value, { required = true } = {}) {
      const text = String(value || "").trim();
      if (!text) return required ? "Worker coordinator URL is required in Worker mode." : "";
      let parsed;
      try {
        parsed = new URL(text);
      } catch (_error) {
        return "Worker coordinator URL must include http:// or https:// and a reachable coordinator host.";
      }
      if (!["http:", "https:"].includes(parsed.protocol)) {
        return "Worker coordinator URL must start with http:// or https://.";
      }
      const host = String(parsed.hostname || "").replace(/^\[|\]$/g, "").toLowerCase();
      if (!host) return "Worker coordinator URL must include a coordinator host.";
      if (host === "0.0.0.0" || host === "::") {
        return "Use the coordinator machine name or LAN IP. 0.0.0.0 and :: are listen addresses, not worker targets.";
      }
      if (!parsed.port) {
        return "Worker coordinator URL must include the coordinator TCP port, for example http://coordinator-host:7830.";
      }
      const port = Number(parsed.port);
      if (!Number.isInteger(port) || port < 1 || port > 65535) {
        return "Worker coordinator URL port must be in 1..65535.";
      }
      if (parsed.pathname && parsed.pathname !== "/") {
        return "Worker coordinator URL must be the coordinator base URL only, without a path.";
      }
      if (parsed.search || parsed.hash) {
        return "Worker coordinator URL must not include query strings or fragments.";
      }
      if (parsed.username || parsed.password) {
        return "Worker coordinator URL must not embed userinfo; use the shared worker token instead.";
      }
      return "";
    }

    function setNetworkUrlError(inputId, errorId, message) {
      const input = byId(inputId);
      const error = byId(errorId);
      if (error) error.textContent = message || "";
      if (!input) return;
      input.setAttribute("aria-invalid", message ? "true" : "false");
      if (typeof input.setCustomValidity === "function") input.setCustomValidity(message || "");
      if (errorId) appendDescribedBy(input, errorId);
    }

    function validateNetworkWorkerUrlFields({ includeSetup = false, show = true } = {}) {
      const role = normalizedNetworkRole();
      const mainRequired = role === "worker";
      const mainIssue = workerCoordinatorUrlIssue(settingsBuilderInputValue("settings-network-worker-url"), {
        required: mainRequired,
      });
      const setupRequired = includeSetup && roleSetupState.currentRole === "worker";
      const setupValue = byId("network-role-setup-worker-url")?.value || "";
      const setupIssue = workerCoordinatorUrlIssue(setupValue, { required: setupRequired });
      if (show) {
        setNetworkUrlError("settings-network-worker-url", "settings-network-worker-url-error", mainRequired ? mainIssue : "");
        setNetworkUrlError("network-role-setup-worker-url", "network-role-setup-worker-url-error", setupRequired ? setupIssue : "");
      }
      if (setupRequired) return setupIssue;
      return mainRequired ? mainIssue : "";
    }

    function setNetworkBuilderControl(id, key, kind, fallback) {
      const element = byId(id);
      if (!element) return;
      const value = settingsBuilderConfigValue(key, fallback);
      if (kind === "bool") {
        element.checked = value === true;
        return;
      }
      if (kind === "json_text" && value && typeof value === "object") {
        element.value = JSON.stringify(value, null, 2);
        return;
      }
      setSettingsBuilderControl(id, value);
    }

    function pathMapEntriesFromText(raw) {
      const text = String(raw || "").trim();
      if (!text) return [];
      const parsed = JSON.parse(text);
      if (!parsed || Array.isArray(parsed) || typeof parsed !== "object") {
        throw new Error("Source Path Map must be a JSON object.");
      }
      return Object.entries(parsed).map(([from, to]) => ({
        from: String(from || "").trim(),
        to: String(to || "").trim(),
        sample: "",
      }));
    }

    function pathMapEditorConfig(textareaId) {
      return pathMapEditors[textareaId] || null;
    }

    function pathMapRows(config) {
      return Array.from(byId(config.rowsId)?.querySelectorAll("[data-path-map-row]") || []);
    }

    function rowInput(row, field) {
      return row?.querySelector?.(`[data-path-map-field="${field}"]`) || null;
    }

    function pathMapRowValues(row) {
      return {
        from: String(rowInput(row, "from")?.value || "").trim(),
        to: String(rowInput(row, "to")?.value || "").trim(),
        sample: String(rowInput(row, "sample")?.value || "").trim(),
      };
    }

    function collectPathMapRowsStrict(textareaId) {
      const config = pathMapEditorConfig(textareaId);
      if (!config) return { entries: [], raw: "" };
      const rows = pathMapRows(config);
      const entries = [];
      const seen = new Set();
      rows.forEach((row, index) => {
        const values = pathMapRowValues(row);
        if (!values.from && !values.to) return;
        if (!values.from || !values.to) {
          throw new Error(`Source Path Map row ${index + 1} needs both From prefix and To prefix.`);
        }
        const key = values.from.toLowerCase();
        if (seen.has(key)) throw new Error(`Source Path Map row ${index + 1} duplicates From prefix ${values.from}.`);
        seen.add(key);
        entries.push({ from: values.from, to: values.to, sample: values.sample });
      });
      const map = {};
      entries.forEach((entry) => {
        map[entry.from] = entry.to;
      });
      return {
        entries,
        raw: entries.length ? JSON.stringify(map, null, 2) : "",
      };
    }

    function setPathMapEditorStatus(config, message) {
      setText(config.statusId, message);
    }

    function pathMapSummaryText(textareaId) {
      const config = pathMapEditorConfig(textareaId);
      if (!config) return settingsBuilderInputValue(textareaId) || "(not set)";
      try {
        const result = collectPathMapRowsStrict(textareaId);
        return result.entries.length
          ? `${result.entries.length} row${result.entries.length === 1 ? "" : "s"}`
          : "(not set)";
      } catch (error) {
        return error instanceof Error ? error.message : String(error);
      }
    }

    function createPathMapInput(field, value, placeholder, label) {
      const input = document.createElement("input");
      input.type = "text";
      input.autocomplete = "off";
      input.spellcheck = false;
      input.value = value || "";
      input.placeholder = placeholder;
      input.dataset.pathMapField = field;
      input.setAttribute("aria-label", label);
      return input;
    }

    function defaultPathMapSample(fromPrefix) {
      const from = String(fromPrefix || "").trim();
      if (!from) return "";
      const separator = from.includes("\\") ? "\\" : "/";
      return `${from.replace(/[\\/]+$/, "")}${separator}Sample.mkv`;
    }

    function createPathMapRow(config, entry = {}) {
      const row = document.createElement("tr");
      row.dataset.pathMapRow = "true";

      const fromCell = document.createElement("td");
      fromCell.dataset.label = "From prefix";
      fromCell.appendChild(createPathMapInput("from", entry.from, "C:\\Encode\\Movies", "From prefix"));

      const toCell = document.createElement("td");
      toCell.dataset.label = "To prefix";
      toCell.appendChild(createPathMapInput("to", entry.to, "\\\\SERVER\\Encode\\Movies", "To prefix"));

      const sampleCell = document.createElement("td");
      sampleCell.dataset.label = "Sample claimed path";
      sampleCell.appendChild(createPathMapInput("sample", entry.sample, defaultPathMapSample(entry.from), "Sample claimed path"));

      const resultCell = document.createElement("td");
      resultCell.dataset.label = "Test result";
      const output = document.createElement("output");
      output.className = "network-path-map-result";
      output.textContent = "Not tested";
      resultCell.appendChild(output);

      const actionsCell = document.createElement("td");
      actionsCell.dataset.label = "Actions";
      const testButton = document.createElement("button");
      testButton.type = "button";
      testButton.className = "secondary-button";
      testButton.dataset.pathMapAction = "test";
      testButton.textContent = "Test";
      testButton.title = "Resolve the sample path and run the backend worker path preflight.";
      const removeButton = document.createElement("button");
      removeButton.type = "button";
      removeButton.className = "secondary-button";
      removeButton.dataset.pathMapAction = "remove";
      removeButton.textContent = "Remove";
      removeButton.title = "Remove this path map row.";
      actionsCell.append(testButton, removeButton);

      row.append(fromCell, toCell, sampleCell, resultCell, actionsCell);
      return row;
    }

    function syncPathMapTextareaFromRows(textareaId, { strict = false } = {}) {
      const config = pathMapEditorConfig(textareaId);
      const textarea = byId(textareaId);
      if (!config || !textarea) return "";
      try {
        const result = collectPathMapRowsStrict(textareaId);
        textarea.value = result.raw;
        textarea.dataset.pathMapRowsInvalid = "";
        setPathMapEditorStatus(config, `${result.entries.length} row${result.entries.length === 1 ? "" : "s"}`);
        return result.raw;
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        textarea.dataset.pathMapRowsInvalid = message;
        setPathMapEditorStatus(config, "Rows need attention");
        if (strict) throw error;
        return textarea.value || "";
      }
    }

    function renderPathMapEditor(textareaId) {
      const config = pathMapEditorConfig(textareaId);
      const textarea = byId(textareaId);
      const tbody = config ? byId(config.rowsId) : null;
      if (!config || !textarea || !tbody) return;
      let entries = [];
      let parseError = "";
      try {
        entries = pathMapEntriesFromText(textarea.value);
      } catch (error) {
        parseError = error instanceof Error ? error.message : String(error);
      }
      tbody.textContent = "";
      const rows = entries.length ? entries : [{ from: "", to: "", sample: "" }];
      rows.forEach((entry) => tbody.appendChild(createPathMapRow(config, entry)));
      bindPathMapEditor(config);
      if (parseError) {
        textarea.dataset.pathMapRowsInvalid = parseError;
        setPathMapEditorStatus(config, "Saved JSON needs attention");
      } else {
        textarea.dataset.pathMapRowsInvalid = "";
        syncPathMapTextareaFromRows(textareaId);
      }
    }

    function addPathMapRow(textareaId, entry = {}) {
      const config = pathMapEditorConfig(textareaId);
      const tbody = config ? byId(config.rowsId) : null;
      if (!config || !tbody) return;
      tbody.appendChild(createPathMapRow(config, entry));
      syncPathMapTextareaFromRows(textareaId);
      markNetworkSettingsBuilderDirty();
    }

    function removePathMapRow(config, row) {
      row?.remove?.();
      if (!pathMapRows(config).length) {
        byId(config.rowsId)?.appendChild(createPathMapRow(config, {}));
      }
      syncPathMapTextareaFromRows(config.textareaId);
      markNetworkSettingsBuilderDirty();
    }

    function normalizedPathForMatch(value) {
      return String(value || "").replace(/\\/g, "/").replace(/\/+$/, "").toLowerCase();
    }

    function resolvePathMapSample(sample, fromPrefix, toPrefix) {
      const from = String(fromPrefix || "").trim();
      const to = String(toPrefix || "").trim();
      const samplePath = String(sample || "").trim() || defaultPathMapSample(from);
      if (!from || !to || !samplePath) {
        throw new Error("From prefix, To prefix, and a sample path are required.");
      }
      const normalizedSample = normalizedPathForMatch(samplePath);
      const normalizedFrom = normalizedPathForMatch(from);
      const matches = normalizedSample === normalizedFrom || normalizedSample.startsWith(`${normalizedFrom}/`);
      if (!matches) throw new Error("Sample claimed path does not start with the From prefix.");
      const sampleForward = samplePath.replace(/\\/g, "/");
      const fromForward = from.replace(/\\/g, "/").replace(/\/+$/, "");
      const suffix = sampleForward.slice(fromForward.length).replace(/^\/+/, "");
      const separator = to.includes("\\") ? "\\" : "/";
      const base = to.replace(/[\\/]+$/, "");
      return {
        samplePath,
        resolvedPath: suffix ? `${base}${separator}${suffix.replace(/[\\/]+/g, separator)}` : base,
      };
    }

    function pathLayerStatus(result) {
      const data = result?.data && typeof result.data === "object" ? result.data : {};
      const layers = data.layers && typeof data.layers === "object" ? data.layers : {};
      const l3 = layers.l3_paths && typeof layers.l3_paths === "object" ? layers.l3_paths : {};
      if (!Object.keys(l3).length) return "Backend saved-config preflight unavailable.";
      return `Backend saved-config preflight: path layer ${l3.ok ? "reported pass" : "reported review"} (${l3.status || "unknown"}).`;
    }

    async function testPathMapRow(config, row) {
      const output = row?.querySelector?.(".network-path-map-result");
      const values = pathMapRowValues(row);
      let resolved;
      try {
        resolved = resolvePathMapSample(values.sample, values.from, values.to);
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        if (output) output.textContent = `Blocked: ${message}`;
        setText(config.resultId, `Path map row test blocked: ${message}`);
        return;
      }
      const lines = [
        `Local staged rewrite sample: ${resolved.samplePath}`,
        `Local staged rewrite result: ${resolved.resolvedPath}`,
      ];
      if (output) output.textContent = "Testing backend path layer...";
      setText(config.resultId, [...lines, "Backend saved-config preflight: running..."].join("\n"));
      const runner = typeof runNetworkWorkerTestConnection === "function"
        ? runNetworkWorkerTestConnection
        : (options) => window.mediaPipelineNetworkView?.runNetworkWorkerTestConnection?.(options);
      try {
        const result = runner ? await runner({ render: false }) : null;
        lines.push(pathLayerStatus(result));
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        lines.push(`Backend saved-config preflight unavailable: ${message}`);
      }
      if (output) output.textContent = lines.slice(1).join("\n");
      setText(config.resultId, lines.join("\n"));
    }

    function bindPathMapEditor(config) {
      const tbody = byId(config.rowsId);
      const addButton = byId(config.addButtonId);
      if (tbody && tbody.dataset.pathMapEditorBound !== "true") {
        tbody.dataset.pathMapEditorBound = "true";
        tbody.addEventListener("input", (event) => {
          if (!event.target?.matches?.("[data-path-map-field]")) return;
          const row = event.target.closest("[data-path-map-row]");
          const sample = rowInput(row, "sample");
          const from = rowInput(row, "from")?.value || "";
          if (sample && !String(sample.value || "").trim()) sample.placeholder = defaultPathMapSample(from);
          syncPathMapTextareaFromRows(config.textareaId);
          markNetworkSettingsBuilderDirty();
        });
        tbody.addEventListener("click", (event) => {
          const button = event.target?.closest?.("[data-path-map-action]");
          if (!button) return;
          const row = button.closest("[data-path-map-row]");
          if (button.dataset.pathMapAction === "remove") {
            removePathMapRow(config, row);
          } else if (button.dataset.pathMapAction === "test") {
            testPathMapRow(config, row);
          }
        });
      }
      if (addButton && addButton.dataset.pathMapEditorBound !== "true") {
        addButton.dataset.pathMapEditorBound = "true";
        addButton.addEventListener("click", () => addPathMapRow(config.textareaId));
      }
    }

    function readNetworkPathMapEditorValue(id, label) {
      const config = pathMapEditorConfig(id);
      const textarea = byId(id);
      if (!config || !textarea) return readNetworkJsonText(id, label);
      const rows = pathMapRows(config);
      const hasVisibleRowValue = rows.some((row) => {
        const values = pathMapRowValues(row);
        return Boolean(values.from || values.to);
      });
      if (!hasVisibleRowValue && String(textarea.value || "").trim()) {
        return readNetworkJsonText(id, label);
      }
      const result = collectPathMapRowsStrict(id);
      textarea.value = result.raw;
      textarea.dataset.pathMapRowsInvalid = "";
      setPathMapEditorStatus(config, `${result.entries.length} row${result.entries.length === 1 ? "" : "s"}`);
      return result.raw;
    }

    function visibleNetworkRoleFromConfig() {
      const role = String(settingsBuilderConfigValue("NetworkRole", "standalone") || "standalone").trim().toLowerCase();
      const localEncode = settingsBuilderConfigValue("CoordinatorAlsoEncodeLocally", false);
      const localEnabled = localEncode === true;
      return role === "coordinator" && localEnabled ? "coordinator_local" : role;
    }

    function networkRolePersistsAs(visibleRole) {
      return visibleRole === "coordinator_local" ? "coordinator" : visibleRole;
    }

    function networkRoleLocalEncodeValue(visibleRole) {
      return visibleRole === "coordinator_local";
    }

    function networkSettingAppliesToVisibleRole(key, visibleRole) {
      const role = String(visibleRole || "standalone").toLowerCase();
      if (key === "NetworkRole" || key === "CoordinatorAlsoEncodeLocally") return true;
      if (role === "coordinator" || role === "coordinator_local") {
        return ["CoordinatorPort", "CoordinatorBindAddress", "CoordinatorHeartbeatTimeoutMins"].includes(key);
      }
      if (role === "worker") {
        return ["WorkerCoordinatorUrl", "WorkerName", "WorkerPollIntervalSecs", "WorkerSourcePathMap", "WorkerEncoderMap", "WorkerHonorCoordinatorPolicy"].includes(key);
      }
      return false;
    }

    function fieldContainer(id) {
      const element = byId(id);
      const editor = element?.id ? byId(`${element.id}-editor`) : null;
      if (editor) return editor;
      return element?.closest?.("label") || element;
    }

    function setNetworkFieldVisible(id, visible) {
      const container = fieldContainer(id);
      if (container) container.hidden = !visible;
    }

    function updateNetworkRoleVisibility() {
      const role = normalizedNetworkRole();
      const coordinatorMode = role === "coordinator" || role === "coordinator_local";
      const workerMode = role === "worker";
      setNetworkFieldVisible("settings-network-coordinator-port", coordinatorMode);
      setNetworkFieldVisible("settings-network-bind-address", coordinatorMode);
      setNetworkFieldVisible("settings-network-heartbeat-timeout", coordinatorMode);
      setNetworkFieldVisible("settings-network-coordinator-local-encode", false);
      setNetworkFieldVisible("settings-network-worker-url", workerMode);
      setNetworkFieldVisible("settings-network-worker-name", workerMode);
      setNetworkFieldVisible("settings-network-worker-poll", workerMode);
      setNetworkFieldVisible("settings-network-path-map", workerMode);
      setNetworkFieldVisible("settings-network-worker-encoder-map", workerMode);
      setNetworkFieldVisible("settings-network-honor-coordinator-policy", workerMode);
      setNetworkFieldVisible("settings-network-worker-overrides", false);
      validateNetworkWorkerUrlFields({ show: true });
    }

    function syncNetworkSettingsBuilderFromConfig() {
      refreshSettingsSelectChoices(networkSettingsBuilderFields);
      setSettingsBuilderControl("settings-network-role", visibleNetworkRoleFromConfig());
      setNetworkBuilderControl("settings-network-coordinator-port", "CoordinatorPort", "port", 7830);
      setNetworkBuilderControl("settings-network-bind-address", "CoordinatorBindAddress", "text", "0.0.0.0");
      setNetworkBuilderControl("settings-network-coordinator-local-encode", "CoordinatorAlsoEncodeLocally", "bool", false);
      setNetworkBuilderControl("settings-network-heartbeat-timeout", "CoordinatorHeartbeatTimeoutMins", "number_positive", 5);
      setNetworkBuilderControl("settings-network-worker-url", "WorkerCoordinatorUrl", "text", "");
      setNetworkBuilderControl("settings-network-worker-name", "WorkerName", "text", "");
      setNetworkBuilderControl("settings-network-worker-poll", "WorkerPollIntervalSecs", "number_positive", 10);
      setNetworkBuilderControl("settings-network-path-map", "WorkerSourcePathMap", "json_text", "");
      renderPathMapEditor("settings-network-path-map");
      setNetworkBuilderControl("settings-network-worker-encoder-map", "WorkerEncoderMap", "json_text", "");
      setNetworkBuilderControl("settings-network-honor-coordinator-policy", "WorkerHonorCoordinatorPolicy", "bool", false);
      setNetworkBuilderControl("settings-network-worker-overrides", "WorkerConfigOverrides", "json_text", "");
      networkSettingsBuilderState.initialized = true;
      networkSettingsBuilderState.dirty = false;
      roleSetupState.currentRole = normalizedNetworkRole();
      bindNetworkRoleSetupControls();
      applyNetworkSettingTips();
      updateNetworkRoleVisibility();
      setText("settings-network-builder-status", "Save Changes: none (saved values loaded)");
      renderNetworkSettingsBuilderGuidance();
      window.mediaPipelineNetworkView?.renderNetworkSettingsPatchHandoff?.("Saved Distributed Mode Settings loaded from saved backend settings.");
    }

    function markNetworkSettingsBuilderDirty() {
      networkSettingsBuilderState.initialized = true;
      networkSettingsBuilderState.dirty = true;
      setText("settings-network-builder-status", "Save Changes: dirty local edits");
      updateNetworkRoleVisibility();
      validateNetworkWorkerUrlFields({ show: true });
      renderNetworkSettingsBuilderGuidance();
      window.mediaPipelineNetworkView?.renderNetworkSettingsPatchHandoff?.("Saved Distributed Mode Settings changed locally. Stage, preview, and save before relying on them.");
    }

    function readNetworkJsonText(id, label) {
      const value = settingsBuilderInputValue(id);
      if (!value) return "";
      try {
        const parsed = JSON.parse(value);
        if (!parsed || Array.isArray(parsed) || typeof parsed !== "object") {
          throw new Error(`${label} must be a JSON object.`);
        }
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        throw new Error(`${label} must be valid JSON object text: ${message}`);
      }
      return value;
    }

    function readNetworkBuilderValue(id, kind, label) {
      const element = byId(id);
      if (!element) return kind === "bool" ? false : "";
      if (kind === "bool") return element.checked === true;
      if (kind === "port") {
        const port = readSettingsBuilderNumber(id, label);
        if (port < 1 || port > 65535) throw new Error(`${label} must be between 1 and 65535.`);
        return port;
      }
      if (kind === "number_positive") {
        const value = readSettingsBuilderNumber(id, label);
        if (value < 1) throw new Error(`${label} must be one or higher.`);
        return value;
      }
      if (id === "settings-network-path-map" || id === "network-role-setup-path-map") {
        return readNetworkPathMapEditorValue(id, label);
      }
      if (kind === "json_text") return readNetworkJsonText(id, label);
      return settingsBuilderInputValue(id);
    }

    function collectNetworkSettingsBuilderPatch() {
      const urlIssue = validateNetworkWorkerUrlFields({ show: true });
      if (urlIssue) throw new Error(urlIssue);
      const patch = {};
      const visibleRole = normalizedNetworkRole();
      networkSettingsBuilderFields.forEach(([key, id, kind]) => {
        if (!networkSettingAppliesToVisibleRole(key, visibleRole)) return;
        const field = settingsFieldDefinition(key);
        patch[key] = readNetworkBuilderValue(id, kind, field?.label || key);
      });
      patch.NetworkRole = networkRolePersistsAs(visibleRole);
      patch.CoordinatorAlsoEncodeLocally = networkRoleLocalEncodeValue(visibleRole);
      return patch;
    }

    function applyNetworkSettingsBuilderToPatch() {
      let patch;
      try {
        patch = collectNetworkSettingsBuilderPatch();
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        setText("settings-network-builder-status", "Save Changes: invalid network value");
        setText("settings-patch-status", "Builder invalid");
        setText("settings-patch-detail", message);
        return false;
      }
      writeSettingsPatchJson(patch, "Distributed mode settings prepared role, coordinator, worker, and path-map keys for Save Settings. Backend Save still validates before writing.");
      networkSettingsBuilderState.initialized = true;
      networkSettingsBuilderState.dirty = true;
      setText("settings-network-builder-status", `Save Changes: ${Object.keys(patch).length} network keys ready`);
      renderNetworkSettingsBuilderGuidance();
      window.mediaPipelineNetworkView?.renderNetworkSettingsPatchHandoff?.("Saved Distributed Mode Settings staged into the shared Settings patch JSON.");
      return true;
    }

    function normalizedNetworkRole() {
      return String(settingsBuilderInputValue("settings-network-role") || "standalone").trim().toLowerCase() || "standalone";
    }

    function isSetupRole(role) {
      return role === "coordinator" || role === "worker" || role === "coordinator_local";
    }

    function setControlValue(control, source) {
      if (!control || !source) return;
      if (control.type === "checkbox") {
        control.checked = source.checked === true;
      } else {
        control.value = source.value == null ? "" : String(source.value);
      }
    }

    function roleSetupFields() {
      return Array.from(document.querySelectorAll("[data-role-setup-source]"));
    }

    function copyNetworkMainFieldsToSetupDialog() {
      roleSetupFields().forEach((field) => {
        setControlValue(field, byId(field.dataset.roleSetupSource || ""));
      });
      renderPathMapEditor("network-role-setup-path-map");
    }

    function copyNetworkSetupDialogToMainFields() {
      const role = roleSetupState.currentRole;
      const roleSelect = byId("settings-network-role");
      if (roleSelect && isSetupRole(role)) roleSelect.value = role;
      roleSetupFields().forEach((field) => {
        setControlValue(byId(field.dataset.roleSetupSource || ""), field);
      });
      renderPathMapEditor("settings-network-path-map");
      const localEncode = byId("settings-network-coordinator-local-encode");
      if (localEncode) localEncode.checked = networkRoleLocalEncodeValue(role);
      markNetworkSettingsBuilderDirty();
    }

    function setRoleSetupSections(role) {
      const coordinator = byId("network-role-setup-coordinator-fields");
      const worker = byId("network-role-setup-worker-fields");
      if (coordinator) coordinator.hidden = role !== "coordinator" && role !== "coordinator_local";
      if (worker) worker.hidden = role !== "worker";
      const localEncode = byId("network-role-setup-local-encode");
      if (localEncode) localEncode.checked = networkRoleLocalEncodeValue(role);
      const localEncodeContainer = fieldContainer("network-role-setup-local-encode");
      if (localEncodeContainer) localEncodeContainer.hidden = true;
      const workerOverridesContainer = fieldContainer("network-role-setup-worker-overrides");
      if (workerOverridesContainer) workerOverridesContainer.hidden = true;
    }

    function focusRoleSetupDialog(role) {
      const firstInput = role === "coordinator" || role === "coordinator_local"
        ? byId("network-role-setup-coordinator-port")
        : byId("network-role-setup-worker-url");
      (firstInput || byId("network-role-setup-stage-button"))?.focus?.();
    }

    function openNetworkRoleSetup(role) {
      const normalizedRole = String(role || "").trim().toLowerCase();
      if (!isSetupRole(normalizedRole)) return;
      const roleSelect = byId("settings-network-role");
      if (roleSelect && roleSelect.value !== normalizedRole) {
        roleSelect.value = normalizedRole;
        markNetworkSettingsBuilderDirty();
      }
      roleSetupState.currentRole = normalizedRole;
      const config = roleSetupConfig[normalizedRole];
      setText("network-role-setup-title", config.title);
      setText("network-role-setup-designation", config.designation);
      setText("network-role-setup-summary", config.summary);
      setRoleSetupSections(normalizedRole);
      copyNetworkMainFieldsToSetupDialog();
      applyNetworkSettingTips();
      validateNetworkWorkerUrlFields({ includeSetup: normalizedRole === "worker", show: true });
      const dialog = byId("network-role-setup-dialog");
      roleSetupState.lastFocus = document.activeElement && document.activeElement.focus ? document.activeElement : null;
      if (dialog?.showModal && !dialog.open) {
        dialog.showModal();
      } else if (dialog && !dialog.open) {
        dialog.setAttribute("open", "open");
      }
      focusRoleSetupDialog(normalizedRole);
      window.mediaPipelineNetworkView?.renderNetworkSettingsPatchHandoff?.(`${config.title} opened. Stage settings, then preview and save through backend validation.`);
    }

    function closeNetworkRoleSetup() {
      const dialog = byId("network-role-setup-dialog");
      if (dialog?.close && dialog.open) {
        dialog.close();
      } else if (dialog) {
        dialog.removeAttribute("open");
      }
      roleSetupState.lastFocus?.focus?.();
    }

    function handleNetworkRoleChange() {
      const role = normalizedNetworkRole();
      roleSetupState.currentRole = role;
      updateNetworkRoleVisibility();
      if (isSetupRole(role)) openNetworkRoleSetup(role);
    }

    function stageNetworkRoleSetup() {
      if (!isSetupRole(roleSetupState.currentRole)) return false;
      const setupIssue = validateNetworkWorkerUrlFields({ includeSetup: roleSetupState.currentRole === "worker", show: true });
      if (setupIssue) {
        setText("settings-network-builder-status", "Save Changes: invalid worker URL");
        setText("settings-patch-status", "Builder invalid");
        setText("settings-patch-detail", setupIssue);
        return false;
      }
      copyNetworkSetupDialogToMainFields();
      return applyNetworkSettingsBuilderToPatch();
    }

    function previewNetworkRoleSetup() {
      if (stageNetworkRoleSetup() === false) return;
      byId("network-settings-preview-button")?.click?.();
    }

    function saveNetworkRoleSetup() {
      if (stageNetworkRoleSetup() === false) return;
      byId("network-settings-save-button")?.click?.();
    }

    function bindNetworkRoleSetupControls() {
      if (roleSetupState.bound) return;
      const roleSelect = byId("settings-network-role");
      const coordinatorButton = byId("network-role-coordinator-setup-button");
      const workerButton = byId("network-role-worker-setup-button");
      const stageButton = byId("network-role-setup-stage-button");
      const previewButton = byId("network-role-setup-preview-button");
      const saveButton = byId("network-role-setup-save-button");
      const closeButton = byId("network-role-setup-close-button");
      if (!roleSelect || !coordinatorButton || !workerButton || !stageButton || !previewButton || !saveButton || !closeButton) return;
      roleSetupState.bound = true;
      roleSelect.addEventListener("change", handleNetworkRoleChange);
      coordinatorButton.addEventListener("click", () => openNetworkRoleSetup("coordinator"));
      workerButton.addEventListener("click", () => openNetworkRoleSetup("worker"));
      stageButton.addEventListener("click", stageNetworkRoleSetup);
      previewButton.addEventListener("click", previewNetworkRoleSetup);
      saveButton.addEventListener("click", saveNetworkRoleSetup);
      closeButton.addEventListener("click", closeNetworkRoleSetup);
      byId("settings-network-worker-url")?.addEventListener("input", () => validateNetworkWorkerUrlFields({ show: true }));
      byId("network-role-setup-worker-url")?.addEventListener("input", () => validateNetworkWorkerUrlFields({ includeSetup: true, show: true }));
    }

    function renderNetworkSettingsBuilderGuidance() {
      const role = settingsBuilderInputValue("settings-network-role") || "standalone";
      const lines = [
        `Role: ${formatSettingsChoiceLabel(role)}`,
        "Purpose: this builder stages saved distributed-mode config values for standalone, coordinator, and worker behavior.",
        "Lifecycle guardrail: this builder only stages config values. Coordinator/worker runtime command controls remain backend-owned during the transition.",
        "Secret guardrail: coordinator and worker secrets are intentionally excluded from this builder to avoid accidental credential churn.",
      ];
      if (role === "coordinator") {
        lines.push("Coordinator only setup: confirm the port, bind address, and heartbeat timeout. This mode does not process local files through normal Launch.");
      } else if (role === "coordinator_local") {
        lines.push("Coordinator + local worker setup: confirm the coordinator endpoint and heartbeat timeout. Local work starts only from Network lifecycle controls.");
      } else if (role === "worker") {
        lines.push("Worker only setup: confirm the coordinator URL, worker name, poll interval, source path map, and worker-owned hardware encoder map.");
        const workerUrlIssue = validateNetworkWorkerUrlFields({ show: false });
        if (workerUrlIssue) lines.push(`Worker URL needs attention: ${workerUrlIssue}`);
      } else {
        lines.push("Standalone setup: no distributed-mode popup is required for the default local-only designation.");
      }
      networkSettingsBuilderFields.forEach(([key, id, kind]) => {
        if (!networkSettingAppliesToVisibleRole(key, role)) return;
        const field = settingsFieldDefinition(key);
        const label = field?.label || key;
        let valueText = "";
        if (kind === "bool") {
          valueText = byId(id)?.checked ? "enabled" : "disabled";
        } else if (key === "WorkerSourcePathMap") {
          valueText = pathMapSummaryText(id);
        } else if (key === "WorkerEncoderMap") {
          valueText = settingsBuilderInputValue(id) || "(not set; CPU fallback)";
        } else {
          valueText = settingsBuilderInputValue(id) || "(not set)";
        }
        lines.push(`${label}: ${valueText}`);
        if (field?.help) lines.push(`  ${field.help}`);
        if (key === "WorkerSourcePathMap" && valueText !== "(not set)") {
          lines.push("  Validate path rewrites on the worker before running unattended network claims.");
        }
        if (key === "WorkerHonorCoordinatorPolicy") {
          lines.push("  When enabled, coordinator policy wins for non-hardware encode, routing, audio, and subtitle settings.");
        }
        if (key === "WorkerEncoderMap") {
          lines.push("  This is the only worker-local encode policy input; unsupported or blank families fall back to CPU encoders.");
        }
      });
      setText("settings-network-guidance", lines.join("\n") || "No network guidance loaded.");
    }

    return {
      syncNetworkSettingsBuilderFromConfig,
      markNetworkSettingsBuilderDirty,
      collectNetworkSettingsBuilderPatch,
      applyNetworkSettingsBuilderToPatch,
      renderNetworkSettingsBuilderGuidance,
      openNetworkRoleSetup,
    };
  }

  window.__settingsViewNetworkBuilderModule = {
    createNetworkSettingsBuilder,
  };
})();
