(function () {
  /**
   * Renders backend-provided Settings Wizard diagnostics and review evidence.
   * The facade retains command dispatch, readiness state, and save confirmation.
   */
  function createSettingsWizardPreviewRenderer(deps) {
    const byId = deps.byId;
    const setText = deps.setText;
    const clearRows = deps.clearRows;
    const appendCells = deps.appendCells;
    const updateReadiness = deps.updateReadiness;

    function validationText(data) {
      const errors = data.errors || [];
      const warnings = data.warnings || [];
      const lines = [
        errors.length ? `Blocked: ${errors.length} issue(s)` : "No hard blockers.",
        ...errors.map((item) => `- ${item}`),
        warnings.length ? `Warnings: ${warnings.length}` : "No warnings.",
        ...warnings.map((item) => `- ${item}`),
      ];
      if (data.path_validation?.rows) lines.push("", `Paths checked: ${data.path_validation.rows.length}`);
      return lines.join("\n");
    }

    function renderPathRows(rows) {
      const tbody = byId("settings-wizard-path-rows");
      if (!tbody) return;
      if (!rows.length) {
        clearRows(tbody, 4, "Path validation has not run.");
        return;
      }
      tbody.textContent = "";
      rows.forEach((item) => {
        const row = document.createElement("tr");
        appendCells(row, [
          item.label || "",
          item.status || "",
          `${item.path || "not configured"}${item.exists ? " (exists)" : ""}${item.is_dir ? " (folder)" : ""}`,
        ]);
        const actionCell = document.createElement("td");
        if (item.target) {
          const button = document.createElement("button");
          button.type = "button";
          button.className = "secondary-button";
          button.dataset.wizardFocusTarget = item.target;
          button.textContent = "Focus";
          actionCell.appendChild(button);
        }
        row.appendChild(actionCell);
        tbody.appendChild(row);
      });
    }

    function renderResultList(id, items) {
      const node = byId(id);
      if (!node) return;
      node.textContent = "";
      const rows = Array.isArray(items) ? items : [];
      if (!rows.length) {
        node.textContent = "No result loaded.";
        return;
      }
      rows.forEach((item) => {
        const row = document.createElement("div");
        row.className = "settings-wizard-result-row";
        if (typeof item === "string") {
          row.textContent = item;
        } else {
          row.dataset.state = String(item.state || item.status || "").toLowerCase();
          const label = document.createElement("strong");
          label.textContent = item.label || "";
          const status = document.createElement("span");
          status.textContent = item.status || "";
          const detail = document.createElement("span");
          detail.textContent = item.detail || "";
          row.append(label, status, detail);
        }
        node.appendChild(row);
      });
    }

    function listText(values, fallback = "none") {
      return (Array.isArray(values) ? values : []).filter(Boolean).join(", ") || fallback;
    }

    function capabilityFactsText(data) {
      const facts = data?.capability_facts || {};
      const codecs = listText(facts.supported_video_codecs);
      const backends = listText(facts.supported_encoder_backends);
      const scope = data?.capability_facts_scope || "unknown";
      return `video codecs=${codecs}; encoder backends=${backends}; scope=${scope}`;
    }

    function encoderBackendText(data, selectedBackends) {
      const wanted = new Set(selectedBackends || []);
      const rows = (Array.isArray(data?.encoder_backend_rows) ? data.encoder_backend_rows : [])
        .filter((row) => wanted.has(row.backend) && row.available);
      return rows.map((row) => `${row.backend}: ${listText(row.encoders)}`).join("; ") || "none";
    }

    function hardwareRecommendation(data) {
      const detected = new Set((data?.detected_encoders || []).map((value) => String(value || "").toLowerCase()));
      const choice = [
        ["hevc_nvenc", "HEVC NVENC", "Prefer NVENC with CPU fallback"],
        ["h264_nvenc", "H.264 NVENC", "Prefer NVENC with CPU fallback"],
        ["av1_nvenc", "AV1 NVENC", "Prefer NVENC with CPU fallback"],
        ["libx265", "CPU HEVC / libx265", "Use CPU fallback / CPU primary"],
        ["libx264", "CPU H.264 / libx264", "Use CPU fallback / CPU primary"],
      ].find(([codec]) => detected.has(codec));
      if (!choice) return "No compatible default was identified from this FFmpeg encoder list. Keep the existing setting and review the probe evidence before saving.";
      const [, label, strategy] = choice;
      return `Recommended compatible default: ${label}. Suggested strategy: ${strategy}. This is based only on FFmpeg's listed encoders; backend Save validates the final settings.`;
    }

    function focusTarget(target) {
      let node = null;
      const text = String(target || "");
      if (text.startsWith("library:")) {
        const [, indexText, field] = text.split(":");
        const index = Number.parseInt(indexText, 10) - 1;
        node = document.querySelector(`.settings-wizard-library-row[data-library-index="${index}"] [data-library-field="${field}"]`);
      } else if (text.startsWith("#") || text.startsWith(".")) {
        node = document.querySelector(text);
      }
      if (node) {
        node.focus();
        node.scrollIntoView({ block: "center", behavior: "smooth" });
      }
    }

    function renderSummaryRows(rows) {
      const tbody = byId("settings-wizard-summary-rows");
      if (!tbody) return;
      if (!rows.length) {
        clearRows(tbody, 3, "No summary loaded.");
        return;
      }
      tbody.textContent = "";
      rows.forEach((item) => {
        const row = document.createElement("tr");
        appendCells(row, [item.category || "", item.status || "", item.detail || ""]);
        tbody.appendChild(row);
      });
    }

    function renderPreview(result) {
      const data = result.data || {};
      const wizard = data.wizard || data;
      const changedKeys = data.changed_keys || wizard.changed_keys || Object.keys(wizard.changes || {});
      setText("settings-wizard-review-summary", [
        result.message || "Preview completed.",
        `Changed keys: ${changedKeys.join(", ") || "none"}`,
        "",
        "Warnings:",
        ...((result.warnings || wizard.warnings || []).length ? (result.warnings || wizard.warnings || []) : ["none"]),
        "",
        "Errors:",
        ...((result.errors || wizard.errors || []).length ? (result.errors || wizard.errors || []) : ["none"]),
      ].join("\n"));
      renderSummaryRows(wizard.summary?.categories || []);
      setText("settings-wizard-validation-summary", validationText(wizard));
      updateReadiness();
    }

    return {
      capabilityFactsText,
      encoderBackendText,
      focusTarget,
      hardwareRecommendation,
      renderPathRows,
      renderPreview,
      renderResultList,
      validationText,
    };
  }

  window.__settingsWizardPreviewRenderModule = createSettingsWizardPreviewRenderer;
})();
