(function () {
  function createSettingsBackendResultModule(deps) {
    deps = deps || {};
    const byId = deps.byId || function () { return null; };
    const setText = deps.setText || function () {};
    const clearRows = deps.clearRows || function () {};
    const appendCells = deps.appendCells || function () {};
    const makeRowSelectable = deps.makeRowSelectable || function () {};
    const updateTableStatusLegend = deps.updateTableStatusLegend || function () {};
    const formatConfigValue = deps.formatConfigValue || function (value) { return String(value ?? ""); };
    const jsonDetailText = deps.jsonDetailText || function (options = {}) {
      try {
        return `${options.label || "JSON detail"}:\n${JSON.stringify(options.value, null, 2)}`;
      } catch (error) {
        return `${options.label || "JSON detail"}:\nJSON render error: ${error instanceof Error ? error.message : String(error)}`;
      }
    };
    const renderProgressBarsInto = deps.renderProgressBarsInto;
    const settingsCommandHistoryLine = deps.settingsCommandHistoryLine || function () { return ""; };
    const parseSettingsPatchJson = deps.parseSettingsPatchJson || function () { return {}; };
    const settingsPatchImpactEntries = deps.settingsPatchImpactEntries || function () { return []; };
    const settingsCurrentPatchSignature = deps.settingsCurrentPatchSignature || function () { return ""; };
    const getSelectedSettingsBackendResultKey = deps.getSelectedSettingsBackendResultKey || function () { return ""; };
    const setSelectedSettingsBackendResultKey = deps.setSelectedSettingsBackendResultKey || function () {};
    const getLastSettingsPatchPreviewEvidence = deps.getLastSettingsPatchPreviewEvidence || function () { return null; };
    const getLastSettingsPatchSaveEvidence = deps.getLastSettingsPatchSaveEvidence || function () { return null; };
    const getLastSettingsReloadEvidence = deps.getLastSettingsReloadEvidence || function () { return null; };

    function settingsBackendCommandEvidenceLine(evidence) {
      if (!evidence || !evidence.result) return "No command result captured.";
      return settingsCommandHistoryLine(evidence.result) || evidence.result.message || evidence.command || "settings command";
    }

    function settingsBackendResultEvidence(kind) {
      if (kind === "preview") return getLastSettingsPatchPreviewEvidence();
      if (kind === "save") return getLastSettingsPatchSaveEvidence();
      if (kind === "reload") return getLastSettingsReloadEvidence();
      return null;
    }

    function settingsCommandProgressObject(result) {
      const data = result?.data && typeof result.data === "object" ? result.data : {};
      return data.settings_progress && typeof data.settings_progress === "object" ? data.settings_progress : {};
    }

    function settingsCommandProgressBars(result) {
      const progress = settingsCommandProgressObject(result);
      if (Array.isArray(progress.bars)) return progress.bars.filter(Boolean);
      if (Array.isArray(progress.progress_bars)) return progress.progress_bars.filter(Boolean);
      const data = result?.data && typeof result.data === "object" ? result.data : {};
      if (Array.isArray(data?.progress_bars)) return data.progress_bars.filter(Boolean);
      return [];
    }

    function settingsLatestProgressResult() {
      const candidates = [
        getLastSettingsPatchSaveEvidence()?.result,
        getLastSettingsReloadEvidence()?.result,
        getLastSettingsPatchPreviewEvidence()?.result,
      ];
      return candidates.find((result) => settingsCommandProgressBars(result).length) || null;
    }

    function renderSettingsSaveProgress(result = null) {
      if (typeof renderProgressBarsInto !== "function") return;
      const payload = result || settingsLatestProgressResult();
      const progress = settingsCommandProgressObject(payload);
      renderProgressBarsInto("settings-save-progress-bars", settingsCommandProgressBars(payload), progress, "No settings save/reload progress loaded.");
    }

    function settingsProgressDetailLines(progress) {
      if (!progress || typeof progress !== "object" || !Object.keys(progress).length) return [];
      const steps = Array.isArray(progress.steps) ? progress.steps.filter(Boolean) : [];
      const lines = [
        "",
        "Settings save/reload progress:",
        `Status: ${progress.status || "unknown"}`,
        progress.detail ? `Detail: ${progress.detail}` : "",
      ].filter(Boolean);
      if (steps.length) {
        lines.push("Steps:");
        steps.forEach((step) => {
          lines.push(`- ${step.label || step.key || "Step"}: ${step.status || "unknown"}${step.detail ? `; ${step.detail}` : ""}`);
        });
      }
      return lines;
    }

    function settingsBackendResultRowKey(row) {
      return String(row?.key || row?.signal || "backend-result").toLowerCase().replace(/[^a-z0-9]+/g, "-");
    }

    function settingsBackendResultRows(entries = []) {
      const rows = [];
      const changedEntries = entries.filter((entry) => entry.changed);
      const signature = settingsCurrentPatchSignature();
      const hasPatch = Boolean(signature && signature !== "{}");
      const preview = getLastSettingsPatchPreviewEvidence();
      const save = getLastSettingsPatchSaveEvidence();
      const previewMatches = Boolean(preview && signature && preview.signature === signature);
      const saveMatches = Boolean(save && signature && save.signature === signature);
      const previewResult = preview?.result || {};
      const saveResult = save?.result || {};
      const previewData = previewResult.data && typeof previewResult.data === "object" ? previewResult.data : {};
      const saveData = saveResult.data && typeof saveResult.data === "object" ? saveResult.data : {};

      rows.push({
        key: "current-staged-patch",
        signal: "Current staged patch",
        posture: !hasPatch ? "idle" : changedEntries.length ? "staged" : "unchanged",
        evidence: !hasPatch
          ? "Changes JSON is empty."
          : `${entries.length} staged key(s); ${changedEntries.length} effective change(s); signature=${signature.slice(0, 16)}...`,
        action: changedEntries.length
          ? "Run Preview Patch and confirm the backend result matches the current staged JSON before saving."
          : "No effective save is needed unless this JSON is being prepared for a future edit.",
      });

      rows.push({
        key: "backend-preview",
        signal: "Backend preview",
        evidence_ref: "preview",
        posture: !preview ? "missing" : previewMatches && previewResult.ok === true ? "fresh preview" : previewMatches ? "preview issue" : "stale preview",
        evidence: preview
          ? settingsBackendCommandEvidenceLine(preview)
          : "No backend Preview Patch result has been captured in this page session.",
        action: !preview
          ? "Use Preview Patch before Save Patch for any non-trivial change."
          : previewMatches && previewResult.ok === true
            ? "Preview matches the current staged JSON. Review warnings/errors and redacted diff before saving."
            : previewMatches
              ? "Resolve backend preview warnings/errors before saving."
              : "Patch JSON changed after the last preview. Preview again before saving.",
      });

      rows.push({
        key: "preview-risk-output",
        signal: "Preview risk output",
        evidence_ref: "preview",
        posture: !preview ? "missing" : Array.isArray(previewResult.errors) && previewResult.errors.length ? "blocked" : previewData.diff_truncated ? "review" : Array.isArray(previewResult.warnings) && previewResult.warnings.length ? "review" : "available",
        evidence: preview
          ? `changed=${Array.isArray(previewData.changed_keys) ? previewData.changed_keys.length : 0}; removed=${Array.isArray(previewData.removed_keys) ? previewData.removed_keys.length : 0}; diff_lines=${Array.isArray(previewData.redacted_diff_lines) ? previewData.redacted_diff_lines.length : 0}; truncated=${previewData.diff_truncated === true ? "yes" : "no"}`
          : "No backend redacted diff or risk summary is available.",
        action: preview
          ? "Use the redacted diff and risk summary as the backend-owned evidence for what would change."
          : "Run Preview Patch to get backend-owned redacted diff and risk classification.",
      });

      rows.push({
        key: "save-confirmation-boundary",
        signal: "Save confirmation boundary",
        posture: "explicit confirmation required",
        evidence: "The backend save command requires confirm_save=true and the WebView asks for confirmation before sending it.",
        action: "Cancel if the preview is stale, if warnings are unexplained, or if active pipeline work could observe a partially reviewed config change.",
      });

      rows.push({
        key: "backend-save",
        signal: "Backend save",
        evidence_ref: "save",
        posture: !save ? "not saved" : saveMatches && saveResult.ok === true ? "saved" : saveMatches ? "save issue" : "previous save",
        evidence: save
          ? settingsBackendCommandEvidenceLine(save)
          : "No backend Save Patch result has been captured in this page session.",
        action: !save
          ? "Save Patch must succeed before Launch can use these staged settings."
          : saveMatches && saveResult.ok === true
            ? "Confirm reload and Saved Settings Trust before launching unattended work."
            : saveMatches
              ? "Resolve backend save warnings/errors before relying on the patch."
              : "The last save was for different JSON. Do not treat it as proof for the current patch.",
      });

      rows.push({
        key: "reload-saved-state",
        signal: "Reload / saved state",
        evidence_ref: "save",
        posture: saveMatches && saveResult.ok === true && saveData.reloaded === true
          ? "reloaded"
          : saveMatches && saveResult.ok === true && saveData.reloaded === false
            ? "reload issue"
            : save && saveResult.ok === true
              ? "previous reload"
              : "not proven",
        evidence: saveMatches && saveResult.ok === true
          ? `writes_config=${saveData.writes_config === true ? "yes" : "no"}; reloaded=${saveData.reloaded === true ? "yes" : saveData.reloaded === false ? "no" : "n/a"}; config=${saveData.config_path || ""}`
          : save && saveResult.ok === true
            ? "The last successful save/reload evidence belongs to different staged JSON."
            : "No successful save/reload evidence is available for this staged patch.",
        action: saveMatches && saveResult.ok === true && saveData.reloaded === true
          ? "Refresh has backend proof that the active config was reloaded."
          : save && saveResult.ok === true && !saveMatches
            ? "Preview/save the current staged JSON before treating reload evidence as relevant."
            : "Use Reload From Disk or refresh after resolving save/reload issues; Launch uses saved backend settings only.",
      });

      rows.push({
        key: "mutation-boundary",
        signal: "Mutation boundary",
        posture: "backend-owned",
        evidence: "This table is read-only and cannot save settings, launch work, drain, rename, publish, or touch media files.",
        action: "Only backend command results count as persistence evidence.",
      });

      return rows;
    }

    function settingsBackendResultSelectedRow(rows) {
      const list = Array.isArray(rows) ? rows : [];
      const selectedKey = getSelectedSettingsBackendResultKey();
      if (selectedKey) {
        const selected = list.find((row) => settingsBackendResultRowKey(row) === selectedKey);
        if (selected) return selected;
      }
      return list.find((row) => {
        const posture = String(row?.posture || "").toLowerCase();
        return posture.includes("blocked") || posture.includes("issue") || posture.includes("stale");
      }) || list.find((row) => {
        const posture = String(row?.posture || "").toLowerCase();
        return posture.includes("missing") || posture.includes("not saved") || posture.includes("previous") || posture.includes("not proven") || posture.includes("review");
      }) || list[0] || null;
    }

    function settingsBackendResultListLines(label, values, limit = 8) {
      const list = Array.isArray(values) ? values.map((item) => String(item || "").trim()).filter(Boolean) : [];
      if (!list.length) return [`${label}: none`];
      const lines = [`${label}:`];
      list.slice(0, limit).forEach((item) => lines.push(`- ${item}`));
      if (list.length > limit) lines.push(`- ...${list.length - limit} more`);
      return lines;
    }

    function settingsBackendRiskSummaryLines(riskSummary) {
      if (!riskSummary || typeof riskSummary !== "object") return ["Risk summary: none"];
      const counts = riskSummary.counts && typeof riskSummary.counts === "object" ? riskSummary.counts : {};
      const items = Array.isArray(riskSummary.items) ? riskSummary.items : [];
      const lines = [
        "Risk summary:",
        `Highest severity: ${riskSummary.highest_severity || "unknown"}`,
        `Counts: critical ${counts.critical || 0}, high ${counts.high || 0}, medium ${counts.medium || 0}, low ${counts.low || 0}`,
      ];
      if (!items.length) {
        lines.push("- none");
        return lines;
      }
      items.slice(0, 8).forEach((item) => {
        lines.push(`- [${item?.severity || "unknown"}] ${item?.key || "(unknown key)"} (${item?.code || "risk"}): ${item?.message || ""}`);
      });
      if (items.length > 8) lines.push(`- ...${items.length - 8} more`);
      return lines;
    }

    function settingsBackendResultDetailLines(row) {
      if (!row) {
        return [
          "Backend preview/save result detail:",
          "Select a backend result row to inspect command evidence, warnings, errors, redacted diff, risk summary, and reload proof.",
          "Mutation guardrail: this detail panel is read-only and cannot save settings, launch work, drain, rename, publish, or touch media files.",
        ];
      }
      const evidence = settingsBackendResultEvidence(row.evidence_ref);
      const result = evidence?.result || null;
      const data = result?.data && typeof result.data === "object" ? result.data : {};
      const currentSignature = settingsCurrentPatchSignature();
      const evidenceSignature = evidence?.signature || "";
      const changedKeys = Array.isArray(data.changed_keys) ? data.changed_keys : [];
      const removedKeys = Array.isArray(data.removed_keys) ? data.removed_keys : [];
      const diffLines = Array.isArray(data.redacted_diff_lines) ? data.redacted_diff_lines : [];
      const lines = [
        "Backend preview/save result detail:",
        `Signal: ${row.signal || "unknown"}`,
        `Posture: ${row.posture || "unknown"}`,
        `Evidence: ${row.evidence || ""}`,
        `Operator action: ${row.action || ""}`,
        "",
        "Patch identity:",
        `Current staged signature: ${currentSignature ? `${currentSignature.slice(0, 48)}${currentSignature.length > 48 ? "..." : ""}` : "(invalid or empty)"}`,
        `Evidence signature: ${evidenceSignature ? `${evidenceSignature.slice(0, 48)}${evidenceSignature.length > 48 ? "..." : ""}` : "(none)"}`,
        `Evidence matches current JSON: ${evidenceSignature && currentSignature && evidenceSignature === currentSignature ? "yes" : "no"}`,
      ];
      if (evidence) {
        lines.push(`Captured at: ${evidence.captured_at || "unknown"}`);
        lines.push(`Captured command: ${evidence.command || result?.command || "unknown"}`);
      }
      if (result) {
        lines.push("");
        lines.push("Command result:");
        lines.push(`Command: ${result.command || "unknown"}`);
        lines.push(`OK: ${result.ok === true ? "yes" : "no"}`);
        lines.push(`Severity: ${result.severity || "unknown"}`);
        lines.push(`Message: ${result.message || ""}`);
        lines.push(...settingsBackendResultListLines("Warnings", result.warnings));
        lines.push(...settingsBackendResultListLines("Errors", result.errors));
      }
      if (Object.keys(data).length) {
        lines.push("");
        lines.push("Backend data:");
        lines.push(`Writes config: ${data.writes_config === true ? "yes" : data.writes_config === false ? "no" : "n/a"}`);
        lines.push(`Reloaded: ${data.reloaded === true ? "yes" : data.reloaded === false ? "no" : "n/a"}`);
        if (data.config_path) lines.push(`Config: ${data.config_path}`);
        if (data.backup_path) lines.push(`Backup: ${data.backup_path}`);
        lines.push(`Changed keys: ${changedKeys.join(", ") || "none"}`);
        lines.push(`Removed keys: ${removedKeys.join(", ") || "none"}`);
        lines.push(`Redacted diff lines: ${diffLines.length}; truncated=${data.diff_truncated === true ? "yes" : "no"}`);
        if (diffLines.length) {
          lines.push("Redacted diff:");
          diffLines.slice(0, 12).forEach((item) => lines.push(item));
          if (diffLines.length > 12) lines.push(`...${diffLines.length - 12} more diff line(s)`);
        }
        lines.push(...settingsBackendRiskSummaryLines(data.risk_summary));
        lines.push(...settingsProgressDetailLines(data.settings_progress));
        lines.push("");
        lines.push(jsonDetailText({
          label: "Backend data JSON",
          value: data,
          intro: "Read-only backend preview/save data for troubleshooting. Sensitive values are redacted before they reach this workspace.",
        }));
      }
      if (!evidence && row.key === "save-confirmation-boundary") {
        lines.push("");
        lines.push("Save boundary:");
        lines.push("The WebView sends Save Patch only after browser confirmation and includes confirm_save=true.");
        lines.push("The backend still rejects saves without confirmation and owns PSD1 serialization, backup creation, validation, and reload.");
      }
      if (!evidence && row.key === "current-staged-patch") {
        lines.push("");
        lines.push("Current staged patch:");
        try {
          const entries = settingsPatchImpactEntries(parseSettingsPatchJson());
          const changed = entries.filter((entry) => entry.changed);
          const unknown = entries.filter((entry) => !entry.field);
          lines.push(`Staged keys: ${entries.length}`);
          lines.push(`Effective changes: ${changed.length}`);
          lines.push(`Unknown keys: ${unknown.length}`);
          changed.slice(0, 10).forEach((entry) => lines.push(`- ${entry.key}: ${formatConfigValue(entry.current)} -> ${formatConfigValue(entry.staged)} (${entry.status})`));
          if (changed.length > 10) lines.push(`- ...${changed.length - 10} more change(s)`);
        } catch (error) {
          lines.push(`Patch JSON could not be parsed: ${error instanceof Error ? error.message : String(error)}`);
        }
      }
      lines.push("");
      lines.push("Mutation guardrail: selecting this row does not preview, save, reload, launch, drain, rename, publish, rewrite config, or touch media files.");
      return lines;
    }

    function settingsBackendResultStatus(rows = []) {
      const postures = rows.map((row) => String(row.posture || "").toLowerCase());
      if (postures.some((posture) => posture.includes("blocked") || posture.includes("issue"))) return "Blocked review";
      if (postures.some((posture) => posture.includes("stale") || posture.includes("missing") || posture.includes("not saved") || posture.includes("previous") || posture.includes("not proven") || posture.includes("review"))) return "Review";
      if (postures.some((posture) => posture.includes("saved") || posture.includes("reloaded"))) return "Saved evidence";
      return "No backend result";
    }

    function settingsBackendResultSummaryLines(rows) {
      const previewRow = rows.find((row) => row.signal === "Backend preview");
      const saveRow = rows.find((row) => row.signal === "Backend save");
      const reloadRow = rows.find((row) => row.signal === "Reload / saved state");
      const lines = [
        "Backend preview/save handoff:",
        `Status: ${settingsBackendResultStatus(rows)}`,
        `Preview: ${previewRow?.posture || "missing"}`,
        `Save: ${saveRow?.posture || "not saved"}`,
        `Reload: ${reloadRow?.posture || "not proven"}`,
        "Preview Patch is non-writing. Save Patch is the only persistence command and still requires explicit confirmation.",
        "Launch uses saved backend settings only; staged Changes JSON is not launch-active until save and reload succeed.",
      ];
      const reviewRows = rows.filter((row) => {
        const posture = String(row.posture || "").toLowerCase();
        return posture.includes("missing")
          || posture.includes("stale")
          || posture.includes("issue")
          || posture.includes("blocked")
          || posture.includes("not saved")
          || posture.includes("previous")
          || posture.includes("not proven")
          || posture.includes("review");
      });
      if (reviewRows.length) {
        lines.push("", "Rows needing attention:");
        reviewRows.slice(0, 6).forEach((row) => lines.push(`- ${row.signal}: ${row.action}`));
      } else {
        lines.push("", "No backend result contradiction detected for the current staged patch.");
      }
      lines.push("", "Mutation guardrail: this handoff is read-only and cannot save settings, launch work, or touch media files.");
      return lines;
    }

    function renderSettingsBackendResultFromEntries(entries) {
      const tbody = byId("settings-backend-result-rows");
      if (!tbody) return;
      const rows = settingsBackendResultRows(entries);
      let selectedKey = getSelectedSettingsBackendResultKey();
      if (selectedKey && !rows.some((row) => settingsBackendResultRowKey(row) === selectedKey)) {
        setSelectedSettingsBackendResultKey("");
        selectedKey = "";
      }
      const selected = settingsBackendResultSelectedRow(rows);
      if (!selectedKey && selected) {
        setSelectedSettingsBackendResultKey(settingsBackendResultRowKey(selected));
        selectedKey = getSelectedSettingsBackendResultKey();
      }
      setText("settings-backend-result-status", settingsBackendResultStatus(rows));
      setText("settings-backend-result-summary", settingsBackendResultSummaryLines(rows).join("\n"));
      renderSettingsSaveProgress();
      setText("settings-backend-result-legend", "Backend result rows are read-only; Preview Patch and Save Patch remain backend-owned commands.");
      setText("settings-backend-result-detail", settingsBackendResultDetailLines(selected).join("\n"));
      if (!rows.length) {
        clearRows(tbody, 4, "No backend settings result rows loaded.");
        return;
      }
      tbody.replaceChildren();
      rows.forEach((item) => {
        const row = document.createElement("tr");
        const posture = String(item.posture || "").toLowerCase();
        row.dataset.status = posture.includes("blocked") || posture.includes("issue")
          ? "blocked"
          : (posture.includes("stale") || posture.includes("missing") || posture.includes("not saved") || posture.includes("previous") || posture.includes("not proven") || posture.includes("review") ? "warning" : "match");
        appendCells(row, [item.signal, item.posture, item.evidence, item.action]);
        const key = settingsBackendResultRowKey(item);
        makeRowSelectable(row, () => {
          setSelectedSettingsBackendResultKey(key);
          renderSettingsBackendResultFromEntries(entries);
        }, {
          selected: selectedKey === key,
          label: `Inspect settings backend result ${item.signal || ""}`,
        });
        tbody.appendChild(row);
      });
      updateTableStatusLegend("settings-backend-result-legend", tbody, "Backend preview/save result rows");
    }

    function renderSettingsBackendResultForError(message) {
      setText("settings-backend-result-status", "Invalid JSON");
      setText(
        "settings-backend-result-summary",
        `Backend preview/save handoff unavailable because Changes JSON is invalid.\n${message}\nPreview Patch and Save Patch cannot run until this is valid JSON.`
      );
      clearRows(byId("settings-backend-result-rows"), 4, "Backend result handoff unavailable because Changes JSON is invalid.");
      renderSettingsSaveProgress(null);
      setText("settings-backend-result-legend", "Backend result rows are read-only; Preview Patch and Save Patch remain backend-owned commands.");
      setText("settings-backend-result-detail", [
        "Backend preview/save result detail:",
        `Patch JSON is invalid: ${message}`,
        "Fix Changes JSON before Preview Patch or Save Patch can run.",
        "Mutation guardrail: invalid JSON handling is local UI feedback only and does not write config.",
      ].join("\n"));
    }

    return {
      settingsBackendCommandEvidenceLine,
      settingsBackendResultEvidence,
      settingsCommandProgressObject,
      settingsCommandProgressBars,
      settingsLatestProgressResult,
      renderSettingsSaveProgress,
      settingsProgressDetailLines,
      settingsBackendResultRowKey,
      settingsBackendResultRows,
      settingsBackendResultSelectedRow,
      settingsBackendResultListLines,
      settingsBackendRiskSummaryLines,
      settingsBackendResultDetailLines,
      settingsBackendResultStatus,
      settingsBackendResultSummaryLines,
      renderSettingsBackendResultFromEntries,
      renderSettingsBackendResultForError,
    };
  }

  window.__settingsBackendResultModule = {
    createSettingsBackendResultModule,
  };
})();
