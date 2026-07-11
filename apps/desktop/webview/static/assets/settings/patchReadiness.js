(function () {
  function createSettingsPatchReadinessModule(deps) {
    deps = deps || {};
    const appendCells = deps.appendCells || function () {};
    const byId = deps.byId || function () { return null; };
    const clearRows = deps.clearRows || function () {};
    const formatConfigValue = deps.formatConfigValue || function (value) { return String(value ?? ""); };
    const getCommandHistory = deps.getCommandHistory || function () { return []; };
    const getSelectedSettingsSaveReviewKey = deps.getSelectedSettingsSaveReviewKey || function () { return ""; };
    const isSettingsCommand = deps.isSettingsCommand || function () { return false; };
    const makeRowSelectable = deps.makeRowSelectable || function () {};
    const setSelectedSettingsSaveReviewKey = deps.setSelectedSettingsSaveReviewKey || function () {};
    const setText = deps.setText || function () {};
    const settingsBoolValue = deps.settingsBoolValue || function (value) { return value === true || String(value).toLowerCase() === "true"; };
    const settingsBuilderConfigValue = deps.settingsBuilderConfigValue || function (_key, fallback) { return fallback; };
    const settingsCommandHistoryLine = deps.settingsCommandHistoryLine || function () { return ""; };
    const settingsFieldAllowedValues = deps.settingsFieldAllowedValues || function () { return []; };
    const settingsFieldDefinition = deps.settingsFieldDefinition || function () { return null; };
    const settingsPatchCandidateValue = deps.settingsPatchCandidateValue || function () { return undefined; };
    const settingsPatchComplexBackendKeys = deps.settingsPatchComplexBackendKeys || new Set();
    const settingsPatchEffectiveChangedEntries = deps.settingsPatchEffectiveChangedEntries || function () { return []; };
    const settingsPatchListValue = deps.settingsPatchListValue || function () { return []; };
    const settingsRawConfigValue = deps.settingsRawConfigValue || function () { return undefined; };
    const settingsValuesEqual = deps.settingsValuesEqual || function (left, right) { return JSON.stringify(left) === JSON.stringify(right); };
    const updateTableStatusLegend = deps.updateTableStatusLegend || function () {};

    function settingsLocalValidationHint(severity, context, key, message) {
      return {
        severity,
        context,
        key,
        message,
      };
    }

    function settingsAllowedValueHint(field, key, value, context) {
      const allowedValues = settingsFieldAllowedValues(field);
      if (!allowedValues.length) return [];
      const allowedText = allowedValues.map((item) => String(item));
      const values = Array.isArray(value) ? value : [value];
      const badValues = values
        .filter((item) => item !== null && item !== undefined && item !== "")
        .map((item) => String(item))
        .filter((item) => !allowedText.includes(item));
      if (!badValues.length) return [];
      return [
        settingsLocalValidationHint(
          "warning",
          context,
          key,
          `${key} has value ${badValues.join(", ")} outside backend allowed_values (${allowedText.join(", ")}).`
        ),
      ];
    }

    function settingsNumericConstraintHints(field, key, value, context) {
      if (value === null || value === undefined || value === "" || Array.isArray(value) || typeof value === "object") return [];
      const valueType = String(field?.value_type || "");
      const kind = String(field?.kind || "");
      const numeric = ["integer", "number"].includes(valueType) || ["int", "optional_int", "combo_int", "optional_float"].includes(kind);
      if (!numeric) return [];
      const numberValue = Number(value);
      if (!Number.isFinite(numberValue)) {
        return [settingsLocalValidationHint("warning", context, key, `${key} should be numeric according to backend metadata.`)];
      }
      const hints = [];
      if (field.min !== null && field.min !== undefined && numberValue < Number(field.min)) {
        hints.push(settingsLocalValidationHint("warning", context, key, `${key} is below backend min ${field.min}.`));
      }
      if (field.max !== null && field.max !== undefined && numberValue > Number(field.max)) {
        hints.push(settingsLocalValidationHint("warning", context, key, `${key} is above backend max ${field.max}.`));
      }
      if (field.step !== null && field.step !== undefined && field.step !== "") {
        const step = Number(field.step);
        const base = Number.isFinite(Number(field.min)) ? Number(field.min) : 0;
        if (Number.isFinite(step) && step > 0) {
          const ratio = (numberValue - base) / step;
          if (Math.abs(ratio - Math.round(ratio)) > 1e-9) {
            hints.push(settingsLocalValidationHint("warning", context, key, `${key} does not align to backend step ${field.step}.`));
          }
        }
      }
      return hints;
    }

    function settingsPatchLocalValidationHintsForKey(key, value, context = "settings", options = {}) {
      const hints = [];
      const friendlyTarget = settingsFriendlyPersistedKeyAliases[key];
      if (friendlyTarget) {
        hints.push(settingsLocalValidationHint(
          "error",
          context,
          key,
          `${key} is a display label only; use persisted key ${friendlyTarget}.`
        ));
      }
      const field = settingsFieldDefinition(key);
      if (!field) {
        if (settingsHasBackendFieldDefinitions() && !settingsPatchComplexBackendKeys.has(key)) {
          hints.push(settingsLocalValidationHint(
            "warning",
            context,
            key,
            `${key} is not in backend field metadata loaded by this WebView. Backend Save remains authoritative.`
          ));
        }
        return hints;
      }
      if (options.libraryOverride === true) {
        const scope = String(field.scope || "");
        const overrideGroup = String(field.override_group || "");
        if (field.library_override_allowed !== true) {
          hints.push(settingsLocalValidationHint(
            "error",
            context,
            key,
            scope === "source_derived" || scope === "computed_only"
              ? `${key} is read-only source/effective metadata and cannot be saved as a library override.`
              : `${key} is global-only and cannot be saved as a library override.`
          ));
        } else if (options.overrideGroup && overrideGroup && overrideGroup !== options.overrideGroup) {
          hints.push(settingsLocalValidationHint(
            "error",
            context,
            key,
            `${key} belongs in overrides.${overrideGroup}, not overrides.${options.overrideGroup}.`
          ));
        }
      }
      hints.push(...settingsAllowedValueHint(field, key, value, context));
      hints.push(...settingsNumericConstraintHints(field, key, value, context));
      return hints;
    }

    function settingsPatchLibraryOverrideValidationHints(libraryProfiles) {
      if (!Array.isArray(libraryProfiles)) return [];
      const hints = [];
      libraryProfiles.forEach((profile, index) => {
        if (!profile || typeof profile !== "object") return;
        const profileLabel = String(profile.id || profile.name || `profile ${index + 1}`);
        const overrides = profile.overrides && typeof profile.overrides === "object" && !Array.isArray(profile.overrides)
          ? profile.overrides
          : {};
        ["editor", "video", "subtitles", "audio"].forEach((group) => {
          const groupValues = overrides[group];
          if (!groupValues || typeof groupValues !== "object" || Array.isArray(groupValues)) return;
          Object.entries(groupValues).forEach(([key, value]) => {
            hints.push(...settingsPatchLocalValidationHintsForKey(
              String(key),
              value,
              `LibraryProfiles.${profileLabel}.overrides.${group}`,
              { libraryOverride: true, overrideGroup: group }
            ));
          });
        });
        ["editor_overrides", "media_overrides"].forEach((legacyGroup) => {
          const groupValues = profile[legacyGroup];
          if (!groupValues || typeof groupValues !== "object" || Array.isArray(groupValues)) return;
          Object.entries(groupValues).forEach(([key, value]) => {
            hints.push(...settingsPatchLocalValidationHintsForKey(
              String(key),
              value,
              `LibraryProfiles.${profileLabel}.${legacyGroup}`,
              { libraryOverride: true }
            ));
          });
        });
      });
      return hints;
    }

    function settingsPatchLocalValidationHints(changes) {
      if (!changes || Array.isArray(changes) || typeof changes !== "object") return [];
      const hints = [];
      Object.entries(changes).forEach(([key, value]) => {
        hints.push(...settingsPatchLocalValidationHintsForKey(String(key), value, "settings"));
        if (key === "LibraryProfiles") {
          hints.push(...settingsPatchLibraryOverrideValidationHints(value));
        }
      });
      return hints;
    }

    function settingsPatchLocalValidationHintLines(changes) {
      const hints = settingsPatchLocalValidationHints(changes);
      if (!hints.length) return [];
      return [
        "Local validation hints (advisory only; backend Save remains authoritative):",
        ...hints.map((hint) => `- [${hint.severity}] ${hint.context}.${hint.key}: ${hint.message}`),
      ];
    }

    function settingsReadinessIssue(severity, message) {
      return { severity, message };
    }

    function settingsPatchSaveReadinessIssues(entries) {
      const changedEntries = entries.filter((entry) => entry.changed);
      const issues = [];
      const boolValue = (key) => settingsBoolValue(settingsPatchCandidateValue(entries, key));
      const listValue = (key) => settingsPatchListValue(settingsPatchCandidateValue(entries, key));
      const textValue = (key) => String(settingsPatchCandidateValue(entries, key) ?? "").trim();
      const changedKey = (key) => changedEntries.some((entry) => entry.key === key);

      entries.filter((entry) => !entry.field).forEach((entry) => {
        issues.push(settingsReadinessIssue("high", `Unknown key '${entry.key}' is not in the WebView schema; backend save validation must accept it before writing.`));
      });
      changedEntries.filter((entry) => entry.severity === "high" && entry.field).forEach((entry) => {
        issues.push(settingsReadinessIssue("review", `${entry.label} is a high-impact setting. Confirm the change before saving.`));
      });
      if (changedKey("DeleteSourceAfterProcessing") && boolValue("DeleteSourceAfterProcessing") === true) {
        issues.push(settingsReadinessIssue("critical", "DeleteSourceAfterProcessing would allow source deletion. This must stay an explicit, intentional source-safety decision."));
      }
      if (changedKey("SkipStabilityCheck") && boolValue("SkipStabilityCheck") === true) {
        issues.push(settingsReadinessIssue("high", "SkipStabilityCheck is enabled. Half-copied downloads, active torrents, and network-share writes can enter processing."));
      }
      if (changedKey("EnableIntegrityCheck") && boolValue("EnableIntegrityCheck") === false) {
        issues.push(settingsReadinessIssue("high", "EnableIntegrityCheck is disabled. Corrupt or partially-written sources may pass discovery."));
      }
      if (changedKey("AllowNoAudio") && boolValue("AllowNoAudio") === true) {
        issues.push(settingsReadinessIssue("high", "AllowNoAudio is enabled. Outputs without audio can be published and look broken in Plex."));
      }
      if (changedKey("ReprocessAll") && boolValue("ReprocessAll") === true) {
        issues.push(settingsReadinessIssue("medium", "ReprocessAll is enabled. A future run can reconsider already-completed outputs."));
      }
      if (changedKey("ExtraVideoFlags") && listValue("ExtraVideoFlags").length) {
        issues.push(settingsReadinessIssue("high", "ExtraVideoFlags contains legacy raw FFmpeg flags. Backend risk preview should review this before save."));
      }
      if (changedKey("ValidExtensions") && listValue("ValidExtensions").some((item) => !String(item).startsWith("."))) {
        issues.push(settingsReadinessIssue("medium", "ValidExtensions contains values without a leading dot. Backend preview should reject or normalize this."));
      }
      if (changedKey("ValidExtensions") && listValue("ValidExtensions").some((item) => [".part", ".tmp", ".crdownload", ".download"].includes(String(item).toLowerCase()))) {
        issues.push(settingsReadinessIssue("high", "ValidExtensions includes partial-download style extensions."));
      }
      if (changedKey("DropTx3gAfterConversion") && boolValue("DropTx3gAfterConversion") === true) {
        issues.push(settingsReadinessIssue("medium", "TX3G originals will be dropped after conversion. Keep disabled to preserve source subtitle tracks."));
      }
      if (changedKey("DropBdpgsAfterConversion") && boolValue("DropBdpgsAfterConversion") === true) {
        issues.push(settingsReadinessIssue("medium", "BDPGS originals will be dropped after OCR. Keep disabled when preserving image subtitle tracks matters."));
      }
      if (changedKey("DropVobSubAfterConversion") && boolValue("DropVobSubAfterConversion") === true) {
        issues.push(settingsReadinessIssue("medium", "Embedded VobSub originals will be dropped after OCR. External .idx/.sub source files are never deleted."));
      }
      if (changedKey("DropAssAfterConversion") && boolValue("DropAssAfterConversion") === true) {
        issues.push(settingsReadinessIssue("medium", "ASS/SSA originals will be dropped after conversion. Keep disabled to preserve styling."));
      }
      if ((changedKey("DropTx3gAfterConversion") || changedKey("ConvertTx3gToSrt")) && boolValue("DropTx3gAfterConversion") === true && boolValue("ConvertTx3gToSrt") === false) {
        issues.push(settingsReadinessIssue("high", "Drop TX3G is enabled while TX3G conversion is disabled."));
      }
      if ((changedKey("DropBdpgsAfterConversion") || changedKey("ConvertBdpgsToSrt")) && boolValue("DropBdpgsAfterConversion") === true && boolValue("ConvertBdpgsToSrt") === false) {
        issues.push(settingsReadinessIssue("high", "Drop BDPGS is enabled while BDPGS OCR is disabled."));
      }
      if ((changedKey("DropVobSubAfterConversion") || changedKey("ConvertVobSubToSrt")) && boolValue("DropVobSubAfterConversion") === true && boolValue("ConvertVobSubToSrt") === false) {
        issues.push(settingsReadinessIssue("high", "Drop VobSub is enabled while VobSub OCR is disabled."));
      }
      if (changedKey("SubKeepLanguages") && !listValue("SubKeepLanguages").length) {
        issues.push(settingsReadinessIssue("medium", "SubKeepLanguages is empty. Preferred-language subtitle routing may become unpredictable."));
      }
      if (changedKey("ConvertTx3gToSrt") && boolValue("ConvertTx3gToSrt") === false) {
        issues.push(settingsReadinessIssue("medium", "ConvertTx3gToSrt is disabled. Preferred-language TX3G/mov_text subtitles will not produce SRT copies."));
      }
      if (changedKey("ConvertBdpgsToSrt") && boolValue("ConvertBdpgsToSrt") === false) {
        issues.push(settingsReadinessIssue("medium", "ConvertBdpgsToSrt is disabled. Preferred-language PGS subtitles will not produce OCR SRT copies."));
      }
      if (changedKey("ConvertVobSubToSrt") && boolValue("ConvertVobSubToSrt") === false) {
        issues.push(settingsReadinessIssue("medium", "ConvertVobSubToSrt is disabled. Preferred-language VobSub subtitles will not produce OCR SRT copies."));
      }
      if (changedKey("PreferredDefaultAudioLanguages") && !listValue("PreferredDefaultAudioLanguages").length) {
        issues.push(settingsReadinessIssue("medium", "PreferredDefaultAudioLanguages is empty. Default audio selection will depend on source metadata."));
      }
      if ((changedKey("CompatibleAudioCodecs") || changedKey("AudioPassthroughProfile")) && !listValue("CompatibleAudioCodecs").length && textValue("AudioPassthroughProfile") === "custom_codec_list") {
        issues.push(settingsReadinessIssue("high", "AudioPassthroughProfile is custom_codec_list but CompatibleAudioCodecs is empty."));
      }
      if (changedKey("AudioPassthroughProfile") && textValue("AudioPassthroughProfile") === "custom_codec_list") {
        issues.push(settingsReadinessIssue("medium", "AudioPassthroughProfile uses a manual codec list. Preview should confirm copy-vs-transcode impact."));
      }
      if (changedKey("AudioPassthroughProfile") && textValue("AudioPassthroughProfile") === "lossless_passthrough") {
        issues.push(settingsReadinessIssue("medium", "AudioPassthroughProfile preserves lossless codecs. Some Plex clients may transcode those tracks."));
      }
      if (changedKey("AudioDownmixMode") && textValue("AudioDownmixMode") === "stereo") {
        issues.push(settingsReadinessIssue("medium", "AudioDownmixMode forces stereo. This improves compatibility but discards surround channels."));
      }
      if (changedKey("AudioMaxChannels") && Number(textValue("AudioMaxChannels") || 0) > 0 && Number(textValue("AudioMaxChannels") || 0) < 6) {
        issues.push(settingsReadinessIssue("medium", "AudioMaxChannels is below 6. Normal 5.1 tracks may be downmixed during normalization."));
      }
      if (changedKey("OutputContainer") && textValue("OutputContainer").toLowerCase() === "mp4") {
        issues.push(settingsReadinessIssue("medium", "OutputContainer is MP4. Verify subtitle and audio policies avoid muxing unsupported streams into MP4."));
      }
      if (changedKey("NetworkRole") && textValue("NetworkRole") && textValue("NetworkRole").toLowerCase() !== "standalone") {
        issues.push(settingsReadinessIssue("medium", "NetworkRole changes should be saved only when no local pipeline/coordinator/worker work is active."));
      }
      if (changedKey("DeferredPublish") && boolValue("DeferredPublish") === true) {
        issues.push(settingsReadinessIssue("review", "DeferredPublish is enabled. Pending Publish must be monitored and drained after output validation."));
      }
      if (changedKey("CleanupRemoteStaging") && boolValue("CleanupRemoteStaging") === true) {
        issues.push(settingsReadinessIssue("medium", "CleanupRemoteStaging is enabled. Remote staging cleanup should be reviewed against slow or unreliable publish shares."));
      }
      if (changedKey("TransientFailureRetryLimit") && Number(textValue("TransientFailureRetryLimit") || 0) > 8) {
        issues.push(settingsReadinessIssue("medium", "TransientFailureRetryLimit is high. Persistent publish or copy failures may wait too long for operator review."));
      }
      if (changedKey("RobocopyTimeoutSeconds")) {
        const timeoutSeconds = Number(textValue("RobocopyTimeoutSeconds") || 0);
        if (timeoutSeconds > 0 && timeoutSeconds < 300) {
          issues.push(settingsReadinessIssue("medium", "RobocopyTimeoutSeconds is below five minutes. Large media copies on slow disks or SMB shares may fail prematurely."));
        }
      }
      return issues;
    }

    function settingsPatchSaveReadinessStatus(entries) {
      if (!entries.length) return "No changes";
      const changedEntries = entries.filter((entry) => entry.changed);
      if (!changedEntries.length) return "No changes";
      const issues = settingsPatchSaveReadinessIssues(entries);
      if (issues.some((issue) => issue.severity === "critical")) return "Blocked";
      if (issues.some((issue) => issue.severity === "high")) return "High review";
      if (issues.some((issue) => issue.severity === "medium" || issue.severity === "review")) return "Review";
      return "Ready to preview";
    }

    function settingsSaveReviewPostureStatus(posture) {
      const value = String(posture || "").toLowerCase();
      if (value.includes("blocked") || value.includes("critical") || value.includes("high")) return "blocked";
      if (value.includes("review") || value.includes("staged") || value.includes("preview") || value.includes("medium") || value.includes("no history")) return "warning";
      return "match";
    }

    function settingsSaveReviewLatestCommand() {
      const history = getCommandHistory();
      if (!Array.isArray(history)) return null;
      return history.find(isSettingsCommand) || null;
    }

    function settingsSaveReviewRows(entries) {
      const rows = [];
      const changedEntries = entries.filter((entry) => entry.changed);
      const unknownEntries = entries.filter((entry) => !entry.field);
      const issues = settingsPatchSaveReadinessIssues(entries);
      const criticalIssues = issues.filter((issue) => issue.severity === "critical");
      const highIssues = issues.filter((issue) => issue.severity === "high");
      const reviewIssues = issues.filter((issue) => !["critical", "high"].includes(issue.severity));
      const groups = Array.from(new Set(changedEntries.map((entry) => entry.group?.name || "Unknown / custom")));
      const readinessStatus = settingsPatchSaveReadinessStatus(entries);

      rows.push({
        key: "patch-state",
        checkpoint: "Current changes",
        posture: changedEntries.length ? "ready for review" : entries.length ? "unchanged" : "idle",
        evidence: `${entries.length} candidate key(s); ${changedEntries.length} effective change(s); ${unknownEntries.length} unknown key(s).`,
        action: changedEntries.length
          ? "Use Save Settings to review these values before the backend writes the PSD1."
          : entries.length
            ? "No effective save is needed unless the JSON is being edited for a future change."
            : "Prepare Changes JSON with a builder or manual edit before saving.",
        detail: [
          `Readiness status: ${readinessStatus}`,
          groups.length ? `Impacted groups: ${groups.join(", ")}` : "Impacted groups: none",
          "Backend Save remains authoritative for schema validation, PSD1 serialization, backups, and reload.",
        ],
      });

      rows.push({
        key: "schema-coverage",
        checkpoint: "Schema coverage",
        posture: unknownEntries.length ? "blocked review" : "known keys",
        evidence: unknownEntries.length
          ? unknownEntries.slice(0, 8).map((entry) => entry.key).join(", ") + (unknownEntries.length > 8 ? `, +${unknownEntries.length - 8} more` : "")
          : "Every candidate key is present in the backend field definitions loaded by the WebView.",
        action: unknownEntries.length
          ? "Treat unknown keys as schema drift. Save Settings will send them through backend validation before any write."
          : "Use structured builders for routine edits; backend Save Settings still validates known keys.",
        detail: unknownEntries.length
          ? unknownEntries.map((entry) => `${entry.key}: staged=${formatConfigValue(entry.staged)}`)
          : ["No schema-drift keys were detected locally."],
      });

      rows.push({
        key: "safety-blockers",
        checkpoint: "Safety blockers",
        posture: criticalIssues.length ? "critical blocked" : highIssues.length ? "high review" : "clear",
        evidence: criticalIssues.concat(highIssues).slice(0, 4).map((issue) => `[${issue.severity}] ${issue.message}`).join(" | ") || "No critical/high local safety blocker detected.",
        action: criticalIssues.length
          ? "Do not save until critical source-safety or policy conflicts are deliberately resolved."
          : highIssues.length
            ? "Review each high-risk item before Save Settings."
            : "Continue to medium review and Save Settings.",
        detail: criticalIssues.concat(highIssues).length
          ? criticalIssues.concat(highIssues).map((issue) => `[${issue.severity}] ${issue.message}`)
          : ["Critical/high checks were clear in local review."],
      });

      rows.push({
        key: "medium-review",
        checkpoint: "Policy review",
        posture: reviewIssues.length ? "review" : "clear",
        evidence: reviewIssues.slice(0, 5).map((issue) => `[${issue.severity}] ${issue.message}`).join(" | ") || "No medium/review local issue detected.",
        action: reviewIssues.length
          ? "Confirm these are intentional before unattended processing; backend save validation may add stricter review items."
          : "No local policy-review item detected; Save Settings still runs backend validation before writing.",
        detail: reviewIssues.length
          ? reviewIssues.map((issue) => `[${issue.severity}] ${issue.message}`)
          : ["No medium/review local checks were triggered."],
      });

      const latestCommand = settingsSaveReviewLatestCommand();
      if (!latestCommand) {
        rows.push({
          key: "backend-command",
          checkpoint: "Backend evidence",
          posture: "no history",
          evidence: "No recent settings validate/reload/save command is available.",
          action: "Use Save Settings to review changes and send them through backend validation.",
          detail: [
            "No backend command evidence is visible in recent command history.",
            "This panel never writes the PSD1; Save Settings remains the backend-owned persistence command.",
          ],
        });
      } else {
        const command = String(latestCommand.command || latestCommand.raw?.command || "").toLowerCase();
        const ok = latestCommand.ok === true || latestCommand.result === "ok" || latestCommand.raw?.ok === true;
        const isSave = command === "settings.save_patch";
        const isPreview = command === "settings.preview_patch";
        rows.push({
          key: "backend-command",
          checkpoint: "Backend evidence",
          posture: ok && isSave ? "saved evidence" : ok && isPreview ? "preview only" : ok ? "ok" : "review",
          evidence: settingsCommandHistoryLine(latestCommand) || command || "settings command",
          action: ok && isSave
            ? "Refresh/reload and confirm Saved Settings Trust before relying on this config for Launch."
            : isPreview
              ? "Preview does not persist settings. Save Settings must succeed before Launch uses the candidate config."
              : "Resolve backend command review/error before saving or launching with these changes.",
          detail: [
            `Command: ${command || "unknown"}`,
            `Result: ${latestCommand.result || (ok ? "ok" : latestCommand.severity || "unknown")}`,
            latestCommand.message ? `Message: ${latestCommand.message}` : "Message: none",
            "Use Settings Commands Evidence and Home/Diagnostics command drilldown for full backend result data.",
          ],
        });
      }

      rows.push({
        key: "mutation-boundary",
        checkpoint: "Mutation boundary",
        posture: "backend-owned",
        evidence: "Local review is display-only; Save Settings remains the backend-owned command.",
        action: "Do not treat this table as persistence proof. Confirm backend result and saved trust summary after saving.",
        detail: [
          "This review table does not save settings, launch work, mutate queue state, rewrite PSD1 files, or touch media.",
          "Backend save owns validation, redacted diffs, backups, PSD1 serialization, reload, and command journaling.",
        ],
      });

      return rows;
    }

    function settingsSaveReviewStatus(rows = []) {
      if (!rows.length) return "No review";
      if (rows.some((row) => settingsSaveReviewPostureStatus(row.posture) === "blocked")) return "Blocked review";
      if (rows.some((row) => settingsSaveReviewPostureStatus(row.posture) === "warning")) return "Review";
      return "Ready";
    }

    function settingsSaveReviewDetailLines(row) {
      if (!row) {
        return [
          "No settings save review row selected.",
          "Select a row to inspect why current changes are blocked, need review, dry-run only, or safe to continue.",
          "Mutation guardrail: this detail view is read-only and cannot save settings, launch work, or touch media files.",
        ];
      }
      const lines = [
        `Checkpoint: ${row.checkpoint}`,
        `Posture: ${row.posture}`,
        `Evidence: ${row.evidence}`,
        `Safe next step: ${row.action}`,
      ];
      if (Array.isArray(row.detail) && row.detail.length) {
        lines.push("", "Detail:");
        row.detail.forEach((line) => lines.push(`- ${line}`));
      }
      lines.push("", "Mutation guardrail: Settings Save remains backend-owned; this row only explains local review posture.");
      return lines;
    }

    function selectedSettingsSaveReviewRow(rows) {
      const selectedKey = getSelectedSettingsSaveReviewKey();
      if (!selectedKey) return null;
      return rows.find((row) => row.key === selectedKey) || null;
    }

    function renderSettingsSaveReviewFromEntries(entries) {
      const rows = settingsSaveReviewRows(entries);
      const tbody = byId("settings-save-review-rows");
      if (!tbody) return;
      let selectedKey = getSelectedSettingsSaveReviewKey();
      if (selectedKey && !rows.some((row) => row.key === selectedKey)) {
        setSelectedSettingsSaveReviewKey("");
        selectedKey = "";
      }
      if (!rows.length) {
        clearRows(tbody, 4, "No settings save review rows loaded.");
        setText("settings-save-review-legend", "Settings save review rows: no selectable rows.");
        setText("settings-save-review-detail", settingsSaveReviewDetailLines(null).join("\n"));
        return;
      }
      tbody.replaceChildren();
      rows.forEach((item) => {
        const row = document.createElement("tr");
        row.dataset.status = settingsSaveReviewPostureStatus(item.posture);
        appendCells(row, [item.checkpoint, item.posture, item.evidence, item.action]);
        makeRowSelectable(row, () => {
          setSelectedSettingsSaveReviewKey(item.key);
          renderSettingsSaveReviewFromEntries(entries);
        }, {
          selected: selectedKey === item.key,
          label: `Settings save review ${item.checkpoint} ${item.posture}`,
        });
        tbody.appendChild(row);
      });
      updateTableStatusLegend("settings-save-review-legend", tbody, "Settings save review rows");
      setText("settings-save-review-detail", settingsSaveReviewDetailLines(selectedSettingsSaveReviewRow(rows)).join("\n"));
    }

    function renderSettingsPatchSaveReadinessFromEntries(entries) {
      const changedEntries = entries.filter((entry) => entry.changed);
      const status = settingsPatchSaveReadinessStatus(entries);
      const issues = settingsPatchSaveReadinessIssues(entries);
      setText("settings-save-readiness-status", status);
      const lines = [
        "Local save readiness checklist:",
        `Status: ${status}`,
        `Change keys: ${entries.length}; effective changes: ${changedEntries.length}; unknown keys: ${entries.filter((entry) => !entry.field).length}.`,
        "Required operator action: press Save Settings and review the change dialog before any non-trivial write.",
        "Backend save remains the source of truth for schema validation, risk policy, PSD1 serialization, backup creation, and config reload.",
      ];
      if (!entries.length) {
        lines.push("", "No change keys are ready.");
      } else if (!changedEntries.length) {
        lines.push("", "No effective changes were detected.");
      }
      const changedGroups = Array.from(new Set(changedEntries.map((entry) => entry.group?.name || "Unknown / custom")));
      if (changedGroups.length) lines.push("", `Impacted group(s): ${changedGroups.join(", ")}.`);
      if (issues.length) {
        lines.push("", "Review item(s):");
        issues.forEach((issue) => lines.push(`- [${issue.severity}] ${issue.message}`));
      } else if (changedEntries.length) {
        lines.push("", "No local blocker detected. Save Settings will run backend validation before writing.");
      }
      lines.push("", "Mutation guardrail: this checklist does not save settings, launch work, mutate queue state, or touch media files.");
      setText("settings-save-readiness", lines.join("\n"));
    }

    function renderSettingsPatchSaveReadinessForError(message) {
      setText("settings-save-readiness-status", "Invalid JSON");
      setText(
        "settings-save-readiness",
        `Local save readiness unavailable because Changes JSON is invalid.\n${message}\nSave Settings cannot run until this is valid JSON.`
      );
      clearRows(byId("settings-save-review-rows"), 4, "Settings save review unavailable because Changes JSON is invalid.");
      setText("settings-save-review-legend", "Settings save review rows: no selectable rows.");
      setText(
        "settings-save-review-detail",
        [
          "Settings save review unavailable because Changes JSON is invalid.",
          message,
          "Save Settings cannot run until this is valid JSON.",
          "Mutation guardrail: this detail view is read-only and cannot save settings, launch work, or touch media files.",
        ].join("\n")
      );
    }


    return {
      settingsPatchLocalValidationHintsForKey,
      settingsPatchLibraryOverrideValidationHints,
      settingsPatchLocalValidationHints,
      settingsPatchLocalValidationHintLines,
      settingsReadinessIssue,
      settingsPatchSaveReadinessIssues,
      settingsPatchSaveReadinessStatus,
      settingsSaveReviewPostureStatus,
      settingsSaveReviewLatestCommand,
      settingsSaveReviewRows,
      settingsSaveReviewStatus,
      settingsSaveReviewDetailLines,
      selectedSettingsSaveReviewRow,
      renderSettingsSaveReviewFromEntries,
      renderSettingsPatchSaveReadinessFromEntries,
      renderSettingsPatchSaveReadinessForError,
    };
  }

  window.__settingsPatchReadinessModule = {
    createSettingsPatchReadinessModule,
  };
}());
