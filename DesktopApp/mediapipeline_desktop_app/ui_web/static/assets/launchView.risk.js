(function () {
  function createLaunchRiskModule(deps = {}) {
    const {
      appendCells = function () {},
      byId = function () { return null; },
      clearRows = function () {},
      collectPipelineStartRequest = function () { return {}; },
      formatSettingsChoiceLabel = null,
      getCommandHistory = function () { return []; },
      getLastLaunchReadinessPayload = function () { return {}; },
      getLastQueueRows = function () { return []; },
      getLastSettings = function () { return {}; },
      isLaunchCommand = function () { return false; },
      launchHistoryLine = null,
      makeRowSelectable = null,
      pipelineModeLabel = function (mode) { return mode || "Pipeline"; },
      queueCurrentFilterScope = null,
      queueFilterScopeDetailLines = null,
      scheduleDisplayValue = null,
      setText = function () {},
      settingsCommandHistoryLine = null,
      settingsLaunchImpactRows = null,
      settingsLaunchImpactStatus = null,
      settingsOperatorTrustStatus = null,
      settingsPatchEffectiveChangedEntries = null,
      settingsPatchIsTouched = null,
      settingsPolicyDeltaRows = null,
      settingsPolicyDeltaStatus = null,
      state = {},
      updateTableStatusLegend = function () {},
    } = deps;
    if (!Object.prototype.hasOwnProperty.call(state, "selectedLaunchSettingsRiskKey")) state.selectedLaunchSettingsRiskKey = "";
    if (!Object.prototype.hasOwnProperty.call(state, "selectedLaunchPolicyBoundaryKey")) state.selectedLaunchPolicyBoundaryKey = "";
    if (!Object.prototype.hasOwnProperty.call(state, "selectedLaunchSettingsIntentKey")) state.selectedLaunchSettingsIntentKey = "";

  function launchSettingsWorkspace() {
    try {
      if (typeof getLastSettings === "function") return getLastSettings() || {};
    } catch {
      return {};
    }
    return {};
  }

  function launchSettingsConfigValue(config, key) {
    if (!config || typeof config !== "object") return undefined;
    if (Object.prototype.hasOwnProperty.call(config, key)) return config[key];
    const match = Object.keys(config).find((item) => item.toLowerCase() === String(key).toLowerCase());
    return match ? config[match] : undefined;
  }

  function launchSettingsBool(value, fallback = false) {
    if (typeof value === "boolean") return value;
    if (value === undefined || value === null || value === "") return fallback;
    return ["1", "true", "yes", "on", "enabled"].includes(String(value).trim().toLowerCase());
  }

  function launchSettingsNumber(value, fallback = 0) {
    const number = Number(value);
    return Number.isFinite(number) ? number : fallback;
  }

  function launchSettingsList(value, fallback = []) {
    if (Array.isArray(value)) return value.map((item) => String(item).trim()).filter(Boolean);
    if (value === undefined || value === null || value === "") return Array.isArray(fallback) ? fallback : [];
    return String(value).split(/[,;]/).map((item) => item.trim()).filter(Boolean);
  }

  function launchPolicyChoiceLabel(value) {
    if (typeof formatSettingsChoiceLabel === "function") return formatSettingsChoiceLabel(value);
    return String(value || "").replace(/[_-]+/g, " ").replace(/\s+/g, " ").trim() || "(not set)";
  }

  function launchPolicyBoolText(value) {
    return launchSettingsBool(value, false) ? "on" : "off";
  }

  function launchSettingsTrustStatus(settings = launchSettingsWorkspace()) {
    if (!settings || typeof settings !== "object" || !settings.schema_version) return "Not loaded";
    try {
      if (typeof settingsOperatorTrustStatus === "function") return settingsOperatorTrustStatus(settings);
    } catch {
      // Keep Launch preflight usable even if the Settings summary helper is unavailable.
    }
    const errors = Array.isArray(settings.errors) ? settings.errors : [];
    if (errors.length) return "Invalid";
    const risk = settings.risk_summary || {};
    const highest = String(risk.highest_severity || "none").toLowerCase();
    if (highest === "critical") return "Critical risk";
    if (highest === "high") return "High risk";
    if (Number(risk.total_count || 0) > 0) return "Review";
    const warnings = Array.isArray(settings.warnings) ? settings.warnings : [];
    if (warnings.length) return "Review";
    return "Ready";
  }

  function launchSettingsDecision(settings = launchSettingsWorkspace(), request = null) {
    const status = launchSettingsTrustStatus(settings);
    const normalized = String(status || "").toLowerCase();
    const mode = request?.mode || "unknown";
    const reasons = [];
    let decision = "ready";
    if (!settings || !settings.schema_version) {
      decision = "blocked";
      reasons.push("saved settings workspace has not loaded");
    }
    if (normalized.includes("invalid") || normalized.includes("critical")) {
      decision = "blocked";
      reasons.push("saved settings contain invalid or critical-risk items");
    } else if (normalized.includes("high")) {
      decision = "review";
      reasons.push("saved settings contain high-risk items");
    } else if (normalized.includes("review")) {
      decision = "review";
      reasons.push("saved settings contain warnings or lower-risk items");
    }
    if (decision === "review" && mode === "continuous") {
      reasons.push("continuous mode is unattended-sensitive");
    }
    let guidance = "Saved settings look ready for this launch mode.";
    if (decision === "blocked") {
      guidance = "Do not start media work until Settings > Validate / Reload is clean.";
    } else if (decision === "review" && mode === "continuous") {
      guidance = "Prefer Validate or Run Once until the saved settings risks are understood.";
    } else if (decision === "review") {
      guidance = "Review saved settings risk items before launching unattended work.";
    }
    return {
      decision,
      status,
      mode,
      reasons,
      guidance,
    };
  }

  function launchSettingsDecisionLines(settings = launchSettingsWorkspace(), request = null) {
    const decision = launchSettingsDecision(settings, request);
    const lines = [
      "Launch settings decision:",
      `- Decision: ${decision.decision}`,
      `- Saved settings status: ${decision.status}`,
      `- Launch mode: ${pipelineModeLabel(decision.mode)}`,
    ];
    if (decision.reasons.length) {
      lines.push(`- Reason: ${decision.reasons.join("; ")}`);
    } else {
      lines.push("- Reason: no saved-settings risks are currently reported.");
    }
    lines.push(`- Start guidance: ${decision.guidance}`);
    lines.push("- Preflight owner: Settings page edits/preview/save; Launch page displays saved posture only.");
    return lines;
  }

  function launchUnsavedSettingsPatchLines() {
    if (typeof settingsPatchIsTouched !== "function" || settingsPatchIsTouched() !== true) return [];
    if (typeof settingsPatchEffectiveChangedEntries !== "function") return [];
    try {
      const changedEntries = settingsPatchEffectiveChangedEntries();
      if (!changedEntries.length) return [];
      const keys = changedEntries.map((entry) => entry.key).filter(Boolean);
      const status = typeof settingsLaunchImpactRows === "function" && typeof settingsLaunchImpactStatus === "function"
        ? settingsLaunchImpactStatus(settingsLaunchImpactRows(changedEntries))
        : "Review";
      const deltaRows = typeof settingsPolicyDeltaRows === "function" ? settingsPolicyDeltaRows(changedEntries) : [];
      const deltaStatus = typeof settingsPolicyDeltaStatus === "function" && deltaRows.length
        ? settingsPolicyDeltaStatus(deltaRows)
        : "Not evaluated";
      const deltaReviewRows = deltaRows.filter((row) => {
        const posture = String(row.posture || "").toLowerCase();
        return posture.includes("blocked") || posture.includes("critical") || posture.includes("review") || posture.includes("staged") || posture.includes("preview");
      });
      const lines = [
        "",
        "Unsaved Settings patch warning:",
        `- Staged but unsaved keys: ${keys.slice(0, 8).join(", ")}${keys.length > 8 ? `, +${keys.length - 8} more` : ""}`,
        `- Settings handoff status: ${status}`,
        `- Staged media-policy delta: ${deltaStatus}`,
        "- Launch uses saved backend settings only. Staged Changes JSON will not affect this launch until backend Save Patch succeeds and settings reload/refresh completes.",
      ];
      if (deltaReviewRows.length) {
        lines.push(`- First staged delta review row: ${deltaReviewRows[0].area} (${deltaReviewRows[0].posture}) - ${deltaReviewRows[0].check}`);
      }
      return lines;
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      return [
        "",
        "Unsaved Settings patch warning:",
        `- Settings Changes JSON is invalid: ${message}`,
        "- Launch will continue using saved backend settings; backend Preview Patch/Save cannot run until Changes JSON is valid.",
      ];
    }
  }

  function launchSettingsRiskLines(request = null) {
    const settings = launchSettingsWorkspace();
    const config = settings.config || {};
    const risk = settings.risk_summary || {};
    const warnings = Array.isArray(settings.warnings) ? settings.warnings : [];
    const errors = Array.isArray(settings.errors) ? settings.errors : [];
    const lines = ["Saved settings preflight:"];
    lines.push(...launchSettingsDecisionLines(settings, request));
    lines.push(...launchUnsavedSettingsPatchLines());
    if (!settings.schema_version) {
      lines.push("- Settings workspace has not loaded yet; refresh before launching if the config was just edited.");
      return lines;
    }
    const total = Number(risk.total_count || 0);
    const highest = risk.highest_severity || "none";
    const counts = risk.counts || {};
    lines.push(`- Backend risk summary: ${highest}${total ? ` (${total} item${total === 1 ? "" : "s"})` : ""}`);
    if (total) {
      lines.push(`- Risk counts: critical ${counts.critical || 0}, high ${counts.high || 0}, medium ${counts.medium || 0}, low ${counts.low || 0}`);
      (risk.items || []).slice(0, 8).forEach((item) => {
        lines.push(`  - [${item.severity || "unknown"}] ${item.key || "setting"} (${item.code || "risk"}): ${item.message || ""}`);
      });
      if ((risk.items || []).length > 8) lines.push(`  - ${(risk.items || []).length - 8} more risk item(s).`);
      lines.push("- Operator guidance: preview/save settings or use Diagnostics before launching if high-risk items are unexpected.");
    }
    if (errors.length) {
      lines.push(`- Settings validation errors: ${errors.length}`);
      errors.slice(0, 5).forEach((error) => lines.push(`  - ${error}`));
    }
    if (warnings.length) {
      lines.push(`- Settings validation warnings: ${warnings.length}`);
      warnings.slice(0, 5).forEach((warning) => lines.push(`  - ${warning}`));
    }
    const deferred = launchSettingsBool(launchSettingsConfigValue(config, "DeferredPublish"), false);
    const stabilitySkipped = launchSettingsBool(launchSettingsConfigValue(config, "SkipStabilityCheck"), false);
    const integrity = launchSettingsBool(launchSettingsConfigValue(config, "EnableIntegrityCheck"), true);
    const allowNoAudio = launchSettingsBool(launchSettingsConfigValue(config, "AllowNoAudio"), false);
    const allowSystemTools = launchSettingsBool(launchSettingsConfigValue(config, "AllowSystemTools"), false);
    const sizeGuard = String(launchSettingsConfigValue(config, "SizeGuardMode") || "advisory");
    const outputContainer = String(launchSettingsConfigValue(config, "OutputContainer") || "mkv");
    lines.push(`- Deferred publish: ${deferred ? "enabled; monitor and drain Pending Publish" : "disabled"}`);
    lines.push(`- Stability check: ${stabilitySkipped ? "disabled" : "enabled"}`);
    lines.push(`- Integrity check: ${integrity ? "enabled" : "disabled"}`);
    lines.push(`- Size guard: ${sizeGuard}`);
    lines.push(`- Output container: ${outputContainer}`);
    lines.push(`- No-audio outputs: ${allowNoAudio ? "allowed" : "blocked"}`);
    lines.push(`- PATH tool fallback: ${allowSystemTools ? "allowed" : "disabled"}`);
    lines.push("- Backend settings workspace remains the source of truth.");
    return lines;
  }

  function launchSettingsSeverityRank(impact) {
    const normalized = String(impact || "").toLowerCase();
    if (normalized === "blocked") return 0;
    if (normalized === "high review") return 1;
    if (normalized === "review") return 2;
    return 3;
  }

  function launchRealMediaReadinessLines(flowLabel = "pipeline") {
    return [
      "",
      "Real-media validation boundary:",
      `- This ${flowLabel} preflight can show saved settings, launch intent, backend preflight, process locks, and cached state; it is not proof that a specific media file will remux, encode, subtitle-convert, publish, or stay under size limits correctly.`,
      "- Preview/build/release checks prove shell/package readiness only. They do not prove FFmpeg routing, subtitle OCR/SRT output, audio selection, copy-to-scratch behavior, source locking, output sidecars, or pending-publish completion for a real file.",
      "- First daily-driver proof should be a small known media batch: compare Queue route/subtitle/audio evidence, Diagnostics Last Stderr and Run Logs, Completed output proof/size growth, and Pending Publish drain summary before trusting unattended runs.",
      "- Backend launch validation remains authoritative at submit time; this WebView guidance is read-only.",
    ];
  }

  function launchSettingsRiskRows(settings = launchSettingsWorkspace(), request = collectPipelineStartRequest()) {
    const config = settings?.config || {};
    const risk = settings?.risk_summary || {};
    const warnings = Array.isArray(settings?.warnings) ? settings.warnings : [];
    const errors = Array.isArray(settings?.errors) ? settings.errors : [];
    const riskItems = Array.isArray(risk.items) ? risk.items : [];
    const mediaReadiness = settings?.media_policy_readiness || {};
    const mediaReadinessRows = Array.isArray(mediaReadiness.rows) ? mediaReadiness.rows : [];
    const mediaReadinessCounts = mediaReadiness.counts || {};
    const mediaReadinessStatus = String(mediaReadiness.operator_status || "not evaluated").toLowerCase();
    const highest = String(risk.highest_severity || "none").toLowerCase();
    const total = Number(risk.total_count || 0);
    const mode = request?.mode || "unknown";
    const deferred = launchSettingsBool(launchSettingsConfigValue(config, "DeferredPublish"), false);
    const stabilitySkipped = launchSettingsBool(launchSettingsConfigValue(config, "SkipStabilityCheck"), false);
    const integrity = launchSettingsBool(launchSettingsConfigValue(config, "EnableIntegrityCheck"), true);
    const allowNoAudio = launchSettingsBool(launchSettingsConfigValue(config, "AllowNoAudio"), false);
    const allowSystemTools = launchSettingsBool(launchSettingsConfigValue(config, "AllowSystemTools"), false);
    const convertTx3g = launchSettingsBool(launchSettingsConfigValue(config, "ConvertTx3gToSrt"), true);
    const dropTx3g = launchSettingsBool(launchSettingsConfigValue(config, "DropTx3gAfterConversion"), false);
    const convertBdpgs = launchSettingsBool(launchSettingsConfigValue(config, "ConvertBdpgsToSrt"), true);
    const dropBdpgs = launchSettingsBool(launchSettingsConfigValue(config, "DropBdpgsAfterConversion"), false);
    const dropAss = launchSettingsBool(launchSettingsConfigValue(config, "DropAssAfterConversion"), false);
    const sizeGuard = String(launchSettingsConfigValue(config, "SizeGuardMode") || "advisory").toLowerCase();
    const outputContainer = String(launchSettingsConfigValue(config, "OutputContainer") || "mkv").toLowerCase();
    const routingProfile = String(launchSettingsConfigValue(config, "RoutingProfile") || "default");
    const allowH264Copy = launchSettingsBool(launchSettingsConfigValue(config, "AllowH264RemuxIfPlexCompatible"), true);
    const h264MaxBitrate = launchSettingsConfigValue(config, "H264RemuxMaxBitrateMbps") || "default";
    const h264MaxHeight = launchSettingsConfigValue(config, "H264RemuxMaxHeight") || "default";
    const remuxSafeCodecsValue = launchSettingsConfigValue(config, "RemuxSafeVideoCodecs") || [];
    const remuxSafeCodecs = Array.isArray(remuxSafeCodecsValue) ? remuxSafeCodecsValue : String(remuxSafeCodecsValue).split(/[,;]/).map((item) => item.trim()).filter(Boolean);
    const maxGrowth = launchSettingsConfigValue(config, "MaxEncodeGrowthPercent") ?? "default";
    const compatGrowth = launchSettingsConfigValue(config, "CompatibilityEncodeGrowthPercent") ?? "default";
    const movieThreshold = launchSettingsConfigValue(config, "EncodeThresholdGB") ?? "default";
    const tvThreshold = launchSettingsConfigValue(config, "TVEncodeThresholdGB") ?? "default";
    const encodeTuning = launchSettingsConfigValue(config, "EncodeTuningPreset") || "default";
    const encodeLadder = launchSettingsConfigValue(config, "EncodeLadder") || "default";
    const videoCodec = launchSettingsConfigValue(config, "VideoCodec") || "default";
    const extraVideoFlagsValue = launchSettingsConfigValue(config, "ExtraVideoFlags") || [];
    const extraVideoFlags = Array.isArray(extraVideoFlagsValue) ? extraVideoFlagsValue : String(extraVideoFlagsValue).split(/[,;]/).map((item) => item.trim()).filter(Boolean);
    const sourceMovies = launchSettingsConfigValue(config, "SourceMovies") || "";
    const sourceTv = launchSettingsConfigValue(config, "SourceTV") || "";
    const scratch = launchSettingsConfigValue(config, "LocalBase") || "";
    const output = launchSettingsConfigValue(config, "Outsource") || "";
    const rows = [];
    const add = (area, impact, evidence, action, detail = []) => rows.push({
      key: String(area || "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "") || `risk-${rows.length + 1}`,
      area,
      impact,
      evidence,
      action,
      detail,
    });
    if (!settings || !settings.schema_version) {
      add("Settings workspace", "blocked", "No schema/version data loaded", "Refresh the WebView or open Settings before starting pipeline, CSV rerun, or audit work.");
      return rows;
    }
    add(
      "Backend settings risk",
      errors.length || highest === "critical" ? "blocked" : highest === "high" ? "high review" : (total || warnings.length ? "review" : "ready"),
      `highest=${risk.highest_severity || "none"}; risk items=${total}; warnings=${warnings.length}; errors=${errors.length}`,
      errors.length || highest === "critical"
        ? "Use Settings > Validate / Reload and resolve critical settings before launch."
        : total || warnings.length
          ? "Review backend risk preview before unattended starts; backend launch validation still has final authority."
          : "No saved-settings risk items currently reported.",
      [
        "Proof source: backend settings workspace and risk summary loaded into the WebView.",
        "Operator proof: Settings Validate/Preview responses should agree with this row before unattended starts.",
        "Boundary: this Launch page row cannot save settings or modify the active PSD1.",
      ],
    );
    add(
      "Backend media-policy readiness",
      mediaReadinessStatus.includes("blocked") ? "blocked" : mediaReadinessStatus.includes("review") ? "review" : mediaReadinessRows.length ? "ready" : "review",
      `schema=${mediaReadiness.schema_version || "missing"}; rows=${mediaReadinessRows.length}; coherent=${mediaReadinessCounts.coherent || 0}; review=${mediaReadinessCounts.review || 0}; blocked=${mediaReadinessCounts.blocked || 0}`,
      mediaReadinessStatus.includes("blocked")
        ? "Resolve blocked saved media-policy rows before launching unattended work."
        : mediaReadinessStatus.includes("review")
          ? "Review backend-authored media-policy readiness rows in Settings before long runs."
          : "Saved media-policy readiness is clean in the backend workspace.",
      [
        "Proof source: backend media_policy_readiness payload from the Settings workspace.",
        "Operator proof: compare Settings media-policy readiness with Launch Active Media Policy Boundary.",
        "Boundary: this is a pre-launch posture check, not proof of a specific media route.",
      ],
    );
    add(
      "Source / scratch / output roots",
      !sourceMovies && !sourceTv ? "review" : (!scratch || !output ? "review" : "ready"),
      `movies=${sourceMovies || "(empty)"}; tv=${sourceTv || "(empty)"}; scratch=${scratch || "(empty)"}; output=${output || "(empty)"}`,
      "Confirm nested source folders, scratch, and output roots are intentional. Launch never owns source mutation; pipeline should copy to scratch.",
      [
        "Proof source: saved path settings only.",
        "Operator proof: verify queue discovery and scratch-copy evidence during the first real-media sample run.",
        "Boundary: source/output/scratch validation and copy behavior remain backend-owned.",
      ],
    );
    add(
      "Stability / integrity gates",
      stabilitySkipped || !integrity ? "high review" : "ready",
      `stability=${stabilitySkipped ? "skipped" : "enabled"}; integrity=${integrity ? "enabled" : "disabled"}`,
      stabilitySkipped || !integrity
        ? "Avoid active torrent/download folders and network shares until this is intentional."
        : "Stability and integrity gates are visible as enabled for launch posture.",
      [
        "Proof source: saved stability and integrity settings.",
        "Operator proof: watch Diagnostics and Queue row evidence for locked, partial, or still-writing files.",
        "Boundary: this row does not probe files or override backend stability checks.",
      ],
    );
    add(
      "Publish / pending-drain posture",
      deferred ? "review" : "ready",
      `deferred publish=${deferred ? "enabled" : "disabled"}; launch mode=${pipelineModeLabel(mode)}`,
      deferred
        ? "Expect completed outputs to park for Pending Publish; monitor Pending Publish and drain evidence after processing."
        : "Completed outputs are not expected to park because deferred publish is disabled.",
      [
        "Proof source: saved DeferredPublish setting and selected launch mode.",
        "Operator proof: verify Pending Publish table and Completed row proof after a sample run.",
        "Boundary: this row cannot drain, publish, or clean pending-publish artifacts.",
      ],
    );
    add(
      "Remux / encode size posture",
      sizeGuard === "off" || sizeGuard === "disabled" || sizeGuard === "strict" || extraVideoFlags.length ? "review" : "ready",
      `routing=${routingProfile}; size guard=${sizeGuard}; normal growth=${maxGrowth}%; compatibility growth=${compatGrowth}%; movie>${movieThreshold}GB; TV>${tvThreshold}GB; codec=${videoCodec}; tuning=${encodeTuning}; ladder=${encodeLadder}; legacy flags=${extraVideoFlags.length}`,
      sizeGuard === "off" || sizeGuard === "disabled"
        ? "Size-growth guard is not enforcing or warning normally; confirm this before testing low-bitrate sources that can balloon."
        : "Use Settings Preview before long runs if route, growth limits, encoder, or output container differs from the intended Plex direct/stream profile.",
      [
        "Proof source: saved routing profile, size guard, thresholds, encoder choice, ladder, and legacy flags.",
        "Operator proof: compare Completed source/output size evidence after the first sample file.",
        "Boundary: this is not a media-policy change and does not force remux or encode.",
      ],
    );
    add(
      "H.264 copy / remux precision",
      !allowH264Copy || !remuxSafeCodecs.length ? "review" : "ready",
      `H.264 copy=${allowH264Copy ? "enabled" : "disabled"} <=${h264MaxBitrate}Mbps/${h264MaxHeight}p; remux-safe codecs=${remuxSafeCodecs.join(", ") || "(empty)"}`,
      allowH264Copy
        ? "Plex-compatible H.264 sources should remain copy/remux candidates when bitrate, height, and codec policy allow it."
        : "Compatible H.264 sources may encode instead of copy; review this before large batches or low-bitrate release groups.",
      [
        "Proof source: saved H.264 copy/remux limits and safe codec list.",
        "Operator proof: inspect Queue route evidence for low-bitrate H.264 samples before trusting a large batch.",
        "Boundary: route calculation remains backend/PowerShell-owned.",
      ],
    );
    add(
      "Container / original subtitle preservation",
      outputContainer === "mp4" && (!dropBdpgs || !dropAss) ? "review" : "ready",
      `container=${outputContainer}; TX3G drop=${dropTx3g ? "on" : "off"}; BDPGS drop=${dropBdpgs ? "on" : "off"}; ASS drop=${dropAss ? "on" : "off"}`,
      outputContainer === "mp4"
        ? "MP4 cannot carry every original subtitle format. Confirm backend routing externalizes or drops unsupported tracks deliberately instead of misboxing them."
        : "MKV remains the safer container for preserving original subtitle/audio streams while adding Plex-friendly SRT.",
      [
        "Proof source: saved output container and original-subtitle drop toggles.",
        "Operator proof: validate output container, subtitle streams, and sidecar SRT evidence on a real sample.",
        "Boundary: this row cannot mux, externalize, or drop streams.",
      ],
    );
    add(
      "Subtitle SRT routing",
      (dropTx3g && !convertTx3g) || (dropBdpgs && !convertBdpgs) ? "blocked" : (!convertTx3g || !convertBdpgs || dropTx3g || dropBdpgs ? "review" : "ready"),
      `TX3G convert=${convertTx3g ? "on" : "off"} drop=${dropTx3g ? "on" : "off"}; BDPGS OCR=${convertBdpgs ? "on" : "off"} drop=${dropBdpgs ? "on" : "off"}`,
      (dropTx3g && !convertTx3g) || (dropBdpgs && !convertBdpgs)
        ? "Do not launch media work with drop-without-convert subtitle contradictions."
        : "Preferred-language non-SRT subtitles should create SRT while originals stay unless drop toggles are intentional.",
      [
        "Proof source: saved TX3G/BDPGS conversion and drop toggles.",
        "Operator proof: confirm SRT creation and original subtitle preservation on a known subtitle sample.",
        "Boundary: subtitle OCR/conversion failures still require backend manual-review classification.",
      ],
    );
    add(
      "Audio predictability",
      allowNoAudio ? "blocked" : "ready",
      `allow no-audio=${allowNoAudio ? "enabled" : "disabled"}; passthrough=${launchSettingsConfigValue(config, "AudioPassthroughProfile") || "default"}; max channels=${launchSettingsConfigValue(config, "AudioMaxChannels") || "default"}`,
      allowNoAudio
        ? "No-audio output is unsafe for normal Plex publishing; review Settings before launch."
        : "No-audio output is not allowed by saved settings.",
      [
        "Proof source: saved audio passthrough and no-audio settings.",
        "Operator proof: inspect Completed audio proof and Plex playback behavior for the first sample output.",
        "Boundary: this row cannot select, transcode, downmix, or publish audio tracks.",
      ],
    );
    add(
      "Tool resolution",
      allowSystemTools ? "review" : "ready",
      `PATH fallback=${allowSystemTools ? "enabled" : "disabled"}`,
      allowSystemTools
        ? "PATH fallback can use non-bundled tools; confirm this before unattended runs."
        : "Bundled tool preference remains visible; backend launch validation still resolves executables.",
      [
        "Proof source: saved tool-resolution policy.",
        "Operator proof: backend launch validation and Diagnostics should show resolved tool paths if a tool issue occurs.",
        "Boundary: this row cannot change PATH or select executables.",
      ],
    );
    add(
      "Real-media validation boundary",
      mode === "validate" ? "review" : "ready",
      "Preview/build/release gates do not prove FFmpeg, subtitle, audio, sidecar, size, or publish behavior on a specific media file.",
      mode === "validate"
        ? "Validate mode is useful for config posture only; follow with a small real Run Once before treating WebView as daily-driver ready."
        : "After start, confirm real output proof in Diagnostics, Completed, and Pending Publish before trusting unattended batches.",
      [
        "Proof source: selected launch mode and visible shell readiness only.",
        "Operator proof: complete a small known batch and compare route, subtitle, audio, sidecar, size, and publish evidence.",
        "Boundary: WebView preview/build/smoke success is not proof of media processing correctness.",
      ],
    );
    if (mode === "continuous" && rows.some((row) => row.impact !== "ready")) {
      add(
        "Continuous-mode sensitivity",
        "high review",
        "Launch mode is Continuous and at least one saved setting row needs review.",
        "Prefer Validate or Run Once until saved settings risk is understood.",
        [
          "Proof source: selected Continuous mode plus at least one non-ready launch risk row.",
          "Operator proof: resolve or intentionally accept review rows before unattended continuous processing.",
          "Boundary: backend launch validation still has final authority over whether Continuous can start.",
        ],
      );
    }
    riskItems.slice(0, 3).forEach((item) => {
      const severity = String(item?.severity || "review").toLowerCase();
      add(
        `Risk item: ${item?.key || item?.code || "setting"}`,
        severity === "critical" ? "blocked" : severity === "high" ? "high review" : "review",
        `${item?.code || "risk"}: ${item?.message || "Review saved setting."}`,
        "Use Settings Preview/Save or Diagnostics before launch if this risk is unexpected.",
        [
          `Backend risk code: ${item?.code || "unknown"}`,
          `Setting key: ${item?.key || "unknown"}`,
          "Proof source: backend settings risk item.",
          "Boundary: this row explains backend risk; it does not suppress or accept the risk.",
        ],
      );
    });
    return rows.sort((left, right) => launchSettingsSeverityRank(left.impact) - launchSettingsSeverityRank(right.impact));
  }

  function launchSettingsRiskStatus(rows = launchSettingsRiskRows()) {
    if (rows.some((row) => row.impact === "blocked")) return "Blocked review";
    if (rows.some((row) => row.impact === "high review")) return "High review";
    if (rows.some((row) => row.impact === "review")) return "Review";
    return rows.length ? "Ready" : "No settings";
  }

  function launchSettingsRiskSummaryLines(rows = launchSettingsRiskRows()) {
    const counts = rows.reduce((acc, row) => {
      const key = row.impact || "review";
      acc[key] = (acc[key] || 0) + 1;
      return acc;
    }, {});
    const lines = [
      "Launch settings risk handoff:",
      `Rows: ${rows.length}; ready=${counts.ready || 0}; review=${counts.review || 0}; high review=${counts["high review"] || 0}; blocked=${counts.blocked || 0}.`,
      "This panel translates saved settings posture into launch-specific operator checks.",
      "Backend launch validation, process locks, and settings preview/save remain the source of truth.",
      "Real-media proof still requires a completed sample run with route, subtitle/audio, output, sidecar, size-growth, and pending-publish evidence.",
    ];
    const reviewRows = rows.filter((row) => row.impact !== "ready");
    if (reviewRows.length) {
      lines.push("", "Rows needing attention:");
      reviewRows.slice(0, 8).forEach((row) => lines.push(`- ${row.area}: ${row.action}`));
      if (reviewRows.length > 8) lines.push(`- ${reviewRows.length - 8} more row(s) need review.`);
    } else {
      lines.push("", "No local saved-settings launch blockers detected.");
    }
    return lines;
  }

  function selectedLaunchSettingsRiskRow(rows = []) {
    const source = Array.isArray(rows) ? rows : [];
    return source.find((row) => row.key === state.selectedLaunchSettingsRiskKey) || source.find((row) => row.impact !== "ready") || source[0] || null;
  }

  function launchSettingsRiskDetailLines(row) {
    if (!row) {
      return [
        "Launch Risk Handoff detail:",
        "No launch risk row is selected.",
        "Select a row to inspect evidence source, operator proof requirements, and mutation boundaries.",
        "Mutation guardrail: this detail panel is read-only and cannot save settings, launch work, drain, publish, rename, delete, or touch media files.",
      ];
    }
    const lines = [
      "Launch Risk Handoff detail:",
      `Area: ${row.area || "unknown"}`,
      `Impact: ${row.impact || "unknown"}`,
      `Evidence: ${row.evidence || "none"}`,
      `Operator check: ${row.action || "review before launch"}`,
    ];
    const detail = Array.isArray(row.detail) ? row.detail : [];
    if (detail.length) {
      lines.push("", "Proof chain:");
      detail.forEach((line) => lines.push(`- ${line}`));
    }
    lines.push(
      "",
      "Daily-driver rule: resolve blocked rows, deliberately accept review rows, then prove the behavior with a small real-media run before trusting unattended batches.",
      "Mutation guardrail: this detail panel is read-only; backend launch validation remains authoritative.",
    );
    return lines;
  }

  function selectLaunchSettingsRiskRow(row) {
    state.selectedLaunchSettingsRiskKey = row?.key || "";
    renderLaunchSettingsRiskHandoff();
  }

  const launchPolicySubtitleKeys = [
    "OutputContainer",
    "SubKeepLanguages",
    "Tx3gExtractLanguages",
    "BdpgsExtractLanguages",
    "ConvertTx3gToSrt",
    "DropTx3gAfterConversion",
    "CreateExternalTx3gSrtSidecars",
    "ConvertBdpgsToSrt",
    "DropBdpgsAfterConversion",
    "DropAssAfterConversion",
    "StripFormatting",
    "RemoveKaraoke",
    "KeepSignsAndSongs",
  ];
  const launchPolicyAudioKeys = [
    "AudioPassthroughProfile",
    "CompatibleAudioCodecs",
    "PreferredDefaultAudioLanguages",
    "AudioTranscodeCodec",
    "AudioTranscodeBitrate",
    "AudioTranscodeAutoBitrateByChannels",
    "AudioDownmixMode",
    "AudioMaxChannels",
    "AllowNoAudio",
  ];
  const launchPolicyPublishKeys = [
    "DeferredPublish",
    "CleanupRemoteStaging",
    "SkipStabilityCheck",
    "EnableIntegrityCheck",
    "DeleteSourceAfterProcessing",
    "TransientFailureRetryLimit",
    "RobocopyTimeoutSeconds",
    "OutsourceMinFreeSpaceGB",
    "OutputSizeMultiplier",
  ];

  // Frontend advisory only: backend launch validation remains authoritative for
  // queue scope, route safety, publish/drain safety, and source-deletion policy.
  function launchPolicyPatchState() {
    if (typeof settingsPatchIsTouched !== "function" || settingsPatchIsTouched() !== true) {
      return { touched: false, entries: [], error: "" };
    }
    if (typeof settingsPatchEffectiveChangedEntries !== "function") {
      return { touched: true, entries: [], error: "Settings patch impact helper is unavailable." };
    }
    try {
      return { touched: true, entries: settingsPatchEffectiveChangedEntries(), error: "" };
    } catch (error) {
      return {
        touched: true,
        entries: [],
        error: error instanceof Error ? error.message : String(error),
      };
    }
  }

  function launchPolicyEntryMap(entries) {
    const map = new Map();
    (Array.isArray(entries) ? entries : []).forEach((entry) => {
      if (entry?.key) map.set(entry.key, entry);
    });
    return map;
  }

  function launchPolicyChangedKeys(entries, keys) {
    const allowed = new Set(keys);
    return (Array.isArray(entries) ? entries : []).filter((entry) => entry?.changed && allowed.has(entry.key)).map((entry) => entry.key);
  }

  function launchPolicyCurrentValue(config, key, fallback) {
    const value = launchSettingsConfigValue(config, key);
    return value === undefined ? fallback : value;
  }

  function launchPolicyCandidateValue(config, entryMap, key, fallback) {
    const entry = entryMap.get(key);
    return entry ? entry.staged : launchPolicyCurrentValue(config, key, fallback);
  }

  function launchPolicyFormatSubtitle(config, entryMap = new Map()) {
    const container = String(launchPolicyCandidateValue(config, entryMap, "OutputContainer", "mkv")).toLowerCase();
    const keep = launchSettingsList(launchPolicyCandidateValue(config, entryMap, "SubKeepLanguages", ["eng", "und"]), ["eng", "und"]);
    const tx3gLang = launchSettingsList(launchPolicyCandidateValue(config, entryMap, "Tx3gExtractLanguages", ["eng", "und"]), ["eng", "und"]);
    const bdpgsLang = launchSettingsList(launchPolicyCandidateValue(config, entryMap, "BdpgsExtractLanguages", ["eng", "und"]), ["eng", "und"]);
    const convertTx3g = launchSettingsBool(launchPolicyCandidateValue(config, entryMap, "ConvertTx3gToSrt", true), true);
    const dropTx3g = launchSettingsBool(launchPolicyCandidateValue(config, entryMap, "DropTx3gAfterConversion", false), false);
    const convertBdpgs = launchSettingsBool(launchPolicyCandidateValue(config, entryMap, "ConvertBdpgsToSrt", true), true);
    const dropBdpgs = launchSettingsBool(launchPolicyCandidateValue(config, entryMap, "DropBdpgsAfterConversion", false), false);
    const dropAss = launchSettingsBool(launchPolicyCandidateValue(config, entryMap, "DropAssAfterConversion", false), false);
    const strip = launchSettingsBool(launchPolicyCandidateValue(config, entryMap, "StripFormatting", true), true);
    return {
      container,
      keep,
      tx3gLang,
      bdpgsLang,
      convertTx3g,
      dropTx3g,
      convertBdpgs,
      dropBdpgs,
      dropAss,
      strip,
      evidence: `container=${launchPolicyChoiceLabel(container)}; keep=${keep.join(", ") || "(empty)"}; TX3G lang=${tx3gLang.join(", ") || "(empty)"} convert/drop=${launchPolicyBoolText(convertTx3g)}/${launchPolicyBoolText(dropTx3g)}; BDPGS lang=${bdpgsLang.join(", ") || "(empty)"} OCR/drop=${launchPolicyBoolText(convertBdpgs)}/${launchPolicyBoolText(dropBdpgs)}; ASS drop=${launchPolicyBoolText(dropAss)}; strip ASS=${launchPolicyBoolText(strip)}`,
    };
  }

  function launchPolicyFormatAudio(config, entryMap = new Map()) {
    const profile = String(launchPolicyCandidateValue(config, entryMap, "AudioPassthroughProfile", "plex_balanced"));
    const codecs = launchSettingsList(launchPolicyCandidateValue(config, entryMap, "CompatibleAudioCodecs", ["aac", "ac3", "eac3", "mp3", "opus", "vorbis"]), ["aac", "ac3", "eac3", "mp3", "opus", "vorbis"]);
    const languages = launchSettingsList(launchPolicyCandidateValue(config, entryMap, "PreferredDefaultAudioLanguages", ["english"]), ["english"]);
    const transcodeCodec = String(launchPolicyCandidateValue(config, entryMap, "AudioTranscodeCodec", "eac3"));
    const transcodeBitrate = String(launchPolicyCandidateValue(config, entryMap, "AudioTranscodeBitrate", "640k"));
    const autoBitrate = launchSettingsBool(launchPolicyCandidateValue(config, entryMap, "AudioTranscodeAutoBitrateByChannels", false), false);
    const downmix = String(launchPolicyCandidateValue(config, entryMap, "AudioDownmixMode", "max_channels"));
    const maxChannels = launchSettingsNumber(launchPolicyCandidateValue(config, entryMap, "AudioMaxChannels", 6), 6);
    const allowNoAudio = launchSettingsBool(launchPolicyCandidateValue(config, entryMap, "AllowNoAudio", false), false);
    return {
      profile,
      codecs,
      languages,
      transcodeCodec,
      transcodeBitrate,
      autoBitrate,
      downmix,
      maxChannels,
      allowNoAudio,
      evidence: `profile=${launchPolicyChoiceLabel(profile)}; codecs=${codecs.join(", ") || "(empty)"}; default languages=${languages.join(", ") || "(empty)"}; transcode=${transcodeCodec}/${transcodeBitrate}${autoBitrate ? " auto-by-channel" : ""}; downmix=${launchPolicyChoiceLabel(downmix)}; max channels=${maxChannels}; no-audio=${launchPolicyBoolText(allowNoAudio)}`,
    };
  }

  function launchPolicyFormatPublish(config, entryMap = new Map()) {
    const deferred = launchSettingsBool(launchPolicyCandidateValue(config, entryMap, "DeferredPublish", false), false);
    const cleanupRemote = launchSettingsBool(launchPolicyCandidateValue(config, entryMap, "CleanupRemoteStaging", false), false);
    const skipStability = launchSettingsBool(launchPolicyCandidateValue(config, entryMap, "SkipStabilityCheck", false), false);
    const integrity = launchSettingsBool(launchPolicyCandidateValue(config, entryMap, "EnableIntegrityCheck", true), true);
    const deleteSource = launchSettingsBool(launchPolicyCandidateValue(config, entryMap, "DeleteSourceAfterProcessing", false), false);
    const retries = launchSettingsNumber(launchPolicyCandidateValue(config, entryMap, "TransientFailureRetryLimit", 3), 3);
    const robocopyTimeout = launchSettingsNumber(launchPolicyCandidateValue(config, entryMap, "RobocopyTimeoutSeconds", 14400), 14400);
    const minFree = launchSettingsNumber(launchPolicyCandidateValue(config, entryMap, "OutsourceMinFreeSpaceGB", 20), 20);
    return {
      deferred,
      cleanupRemote,
      skipStability,
      integrity,
      deleteSource,
      retries,
      robocopyTimeout,
      minFree,
      evidence: `deferred=${launchPolicyBoolText(deferred)}; cleanup remote=${launchPolicyBoolText(cleanupRemote)}; stability=${skipStability ? "skipped" : "enabled"}; integrity=${integrity ? "enabled" : "disabled"}; delete source=${launchPolicyBoolText(deleteSource)}; retries=${retries}; copy timeout=${robocopyTimeout}s; min free=${minFree}GB`,
    };
  }

  function launchPolicyCandidatePosture(area, candidate, changedCount) {
    if (!changedCount) return "same as saved";
    if (area === "subtitle") {
      if ((candidate.dropTx3g && !candidate.convertTx3g) || (candidate.dropBdpgs && !candidate.convertBdpgs)) return "blocked";
      if (candidate.container === "mp4" || candidate.dropTx3g || candidate.dropBdpgs || candidate.dropAss || !candidate.convertTx3g || !candidate.convertBdpgs) return "review";
      return "preview required";
    }
    if (area === "audio") {
      if (candidate.allowNoAudio || (candidate.profile === "custom_codec_list" && !candidate.codecs.length)) return "blocked";
      if (!candidate.languages.length || candidate.profile === "lossless_passthrough" || candidate.profile === "custom_codec_list" || candidate.maxChannels < 6 || String(candidate.downmix || "").toLowerCase() === "stereo") return "review";
      return "preview required";
    }
    if (area === "publish") {
      if (candidate.deleteSource) return "blocked";
      if (candidate.skipStability || !candidate.integrity || candidate.cleanupRemote || candidate.deferred || candidate.retries > 5 || candidate.robocopyTimeout < 1800) return "review";
      return "preview required";
    }
    return "preview required";
  }

  function launchPolicyBoundaryRows(settings = launchSettingsWorkspace()) {
    const config = settings?.config || {};
    const rows = [];
    const add = (key, area, launchState, evidence, action, detail = []) => rows.push({ key, area, launchState, evidence, action, detail });
    if (!settings || !settings.schema_version) {
      add(
        "settings-not-loaded",
        "Settings workspace",
        "blocked",
        "Saved settings workspace has not loaded.",
        "Refresh Settings before launch so saved active policy is visible.",
        ["Launch cannot compare active saved policy against staged Changes JSON until Settings has loaded."],
      );
      return rows;
    }

    const patch = launchPolicyPatchState();
    const entries = patch.entries || [];
    const entryMap = launchPolicyEntryMap(entries);
    const subtitleChanged = launchPolicyChangedKeys(entries, launchPolicySubtitleKeys);
    const audioChanged = launchPolicyChangedKeys(entries, launchPolicyAudioKeys);
    const publishChanged = launchPolicyChangedKeys(entries, launchPolicyPublishKeys);
    const savedSubtitle = launchPolicyFormatSubtitle(config);
    const stagedSubtitle = launchPolicyFormatSubtitle(config, entryMap);
    const savedAudio = launchPolicyFormatAudio(config);
    const stagedAudio = launchPolicyFormatAudio(config, entryMap);
    const savedPublish = launchPolicyFormatPublish(config);
    const stagedPublish = launchPolicyFormatPublish(config, entryMap);

    add(
      "active-subtitle",
      "Active saved subtitle policy",
      "launch-active",
      savedSubtitle.evidence,
      "Launch uses these saved subtitle/container settings if submitted now.",
      [
        "Preferred-language non-SRT subtitles should add SRT while originals stay unless saved drop toggles are on.",
        "MP4 needs deliberate backend handling for unsupported original subtitle streams.",
      ],
    );
    add(
      "staged-subtitle",
      "Staged subtitle candidate",
      patch.error ? "review" : launchPolicyCandidatePosture("subtitle", stagedSubtitle, subtitleChanged.length),
      patch.error ? `Staged Changes JSON cannot be parsed: ${patch.error}` : stagedSubtitle.evidence,
      subtitleChanged.length
        ? "Not launch-active until backend Preview Patch, Save Patch, and settings reload/refresh succeed."
        : "No effective staged subtitle/container change is currently pending.",
      [
        `Changed staged subtitle keys: ${subtitleChanged.join(", ") || "none"}`,
        "Launch will continue using the active saved subtitle policy above until the staged candidate is saved and reloaded.",
      ],
    );
    add(
      "active-audio",
      "Active saved audio policy",
      "launch-active",
      savedAudio.evidence,
      "Launch uses these saved audio settings if submitted now.",
      [
        "Default-language selection, passthrough profile, downmix, and no-audio safety should be predictable before unattended processing.",
      ],
    );
    add(
      "staged-audio",
      "Staged audio candidate",
      patch.error ? "review" : launchPolicyCandidatePosture("audio", stagedAudio, audioChanged.length),
      patch.error ? `Staged Changes JSON cannot be parsed: ${patch.error}` : stagedAudio.evidence,
      audioChanged.length
        ? "Not launch-active until backend Preview Patch, Save Patch, and settings reload/refresh succeed."
        : "No effective staged audio change is currently pending.",
      [
        `Changed staged audio keys: ${audioChanged.join(", ") || "none"}`,
        "Launch will continue using the active saved audio policy above until the staged candidate is saved and reloaded.",
      ],
    );
    add(
      "active-publish",
      "Active saved publish/source safety",
      "launch-active",
      savedPublish.evidence,
      "Launch uses these saved pending-publish and source-safety settings if submitted now.",
      [
        "Normal processing should preserve source files, copy to scratch, and park/drain outputs according to saved pending-publish policy.",
      ],
    );
    add(
      "staged-publish",
      "Staged publish/source candidate",
      patch.error ? "review" : launchPolicyCandidatePosture("publish", stagedPublish, publishChanged.length),
      patch.error ? `Staged Changes JSON cannot be parsed: ${patch.error}` : stagedPublish.evidence,
      publishChanged.length
        ? "Not launch-active until backend Preview Patch, Save Patch, and settings reload/refresh succeed."
        : "No effective staged pending-publish/source-safety change is currently pending.",
      [
        `Changed staged publish/source keys: ${publishChanged.join(", ") || "none"}`,
        "Source deletion must remain explicit and should not appear as a routine staged setting.",
      ],
    );
    add(
      "policy-boundary",
      "Mutation boundary",
      patch.touched && entries.length ? "review" : "ready",
      patch.touched
        ? `${entries.length} effective staged setting change(s) exist, but none are launch-active yet.`
        : "No touched Changes JSON is visible in this WebView session.",
      "Backend Save Patch is the only path that can make staged settings active for Launch.",
      [
        "This panel is read-only. It cannot save settings, launch work, run FFmpeg, publish, drain, rename, or touch media.",
        "After saving, refresh/reload Settings before relying on the saved active policy.",
      ],
    );

    return rows;
  }

  function launchPolicyBoundaryStatus(rows = launchPolicyBoundaryRows()) {
    if (!rows.length) return "Not loaded";
    if (rows.some((row) => row.launchState === "blocked")) return "Blocked staged policy";
    if (rows.some((row) => row.launchState === "review")) return "Review staged policy";
    if (rows.some((row) => row.launchState === "preview required")) return "Preview required";
    if (rows.some((row) => row.launchState === "launch-active")) return "Saved active";
    return "Ready";
  }

  function launchPolicyBoundaryRowStatus(state) {
    const normalized = String(state || "").toLowerCase();
    if (normalized.includes("blocked")) return "blocked";
    if (normalized.includes("review") || normalized.includes("preview")) return "warning";
    if (normalized.includes("launch-active") || normalized.includes("ready")) return "match";
    return "unknown";
  }

  function launchPolicyBoundarySummaryLines(rows = launchPolicyBoundaryRows()) {
    const counts = rows.reduce((acc, row) => {
      const key = row.launchState || "unknown";
      acc[key] = (acc[key] || 0) + 1;
      return acc;
    }, {});
    const reviewRows = rows.filter((row) => !["ready", "launch-active", "same as saved"].includes(row.launchState));
    const lines = [
      "Launch active media-policy boundary:",
      `Rows: ${rows.length}; launch-active=${counts["launch-active"] || 0}; same-as-saved=${counts["same as saved"] || 0}; preview-required=${counts["preview required"] || 0}; review=${counts.review || 0}; blocked=${counts.blocked || 0}.`,
      "Decision rule: Launch uses the active saved subtitle, audio, and pending-publish/source-safety policy. Staged candidates are not launch-active until backend Save Patch succeeds and Settings reload/refresh completes.",
      "High-impact areas: SRT creation/original subtitle preservation, audio default/passthrough/downmix/no-audio behavior, pending publish, stability/integrity checks, and source deletion.",
    ];
    if (reviewRows.length) {
      lines.push("", "Rows needing attention before launch:");
      reviewRows.slice(0, 8).forEach((row) => lines.push(`- ${row.area}: ${row.launchState}; ${row.action}`));
    } else {
      lines.push("", "No staged media-policy candidate currently changes launch-active behavior.");
    }
    lines.push("", "Mutation guardrail: this boundary is read-only and cannot save, launch, drain, publish, rename, or touch media.");
    return lines;
  }

  function selectedLaunchPolicyBoundaryRow(rows) {
    const list = Array.isArray(rows) ? rows : [];
    return list.find((row) => row.key === state.selectedLaunchPolicyBoundaryKey)
      || list.find((row) => !["ready", "launch-active", "same as saved"].includes(row.launchState))
      || list[0]
      || null;
  }

  function launchPolicyBoundaryDetailLines(row) {
    if (!row) {
      return [
        "Launch active media-policy boundary:",
        "No policy row selected.",
        "Mutation guardrail: this detail view is read-only.",
      ];
    }
    const lines = [
      "Launch active media-policy boundary:",
      `Area: ${row.area || "unknown"}`,
      `Launch state: ${row.launchState || "unknown"}`,
      `Evidence: ${row.evidence || ""}`,
      `Operator check: ${row.action || ""}`,
    ];
    const detail = Array.isArray(row.detail) ? row.detail : [];
    if (detail.length) {
      lines.push("", "Detail:");
      detail.forEach((line) => lines.push(`- ${line}`));
    }
    lines.push("", "Guardrail: backend Preview/Save and backend Launch remain authoritative; this panel only compares visible saved/staged policy.");
    return lines;
  }

  function selectLaunchPolicyBoundaryRow(row) {
    state.selectedLaunchPolicyBoundaryKey = row?.key || "";
    renderLaunchPolicyBoundary();
  }

  function renderLaunchPolicyBoundary(settings = launchSettingsWorkspace()) {
    const rows = launchPolicyBoundaryRows(settings);
    if (state.selectedLaunchPolicyBoundaryKey && !rows.some((row) => row.key === state.selectedLaunchPolicyBoundaryKey)) {
      state.selectedLaunchPolicyBoundaryKey = "";
    }
    const selected = selectedLaunchPolicyBoundaryRow(rows);
    setText("launch-policy-boundary-status", launchPolicyBoundaryStatus(rows));
    setText("launch-policy-boundary-summary", launchPolicyBoundarySummaryLines(rows).join("\n"));
    setText("launch-policy-boundary-detail", launchPolicyBoundaryDetailLines(selected).join("\n"));
    const tbody = byId("launch-policy-boundary-rows");
    if (!tbody) return;
    if (!rows.length) {
      clearRows(tbody, 4, "No launch media-policy boundary rows loaded.");
      updateTableStatusLegend("launch-policy-boundary-legend", tbody, "Launch media-policy boundary rows");
      return;
    }
    tbody.replaceChildren();
    rows.forEach((item) => {
      const row = document.createElement("tr");
      row.dataset.status = launchPolicyBoundaryRowStatus(item.launchState);
      appendCells(row, [item.area, item.launchState, item.evidence, item.action]);
      makeRowSelectable(row, () => selectLaunchPolicyBoundaryRow(item), {
        selected: item.key === state.selectedLaunchPolicyBoundaryKey,
        label: `Inspect launch policy boundary ${item.area || ""}`,
      });
      tbody.appendChild(row);
    });
    updateTableStatusLegend("launch-policy-boundary-legend", tbody, "Launch media-policy boundary rows");
  }

  function renderLaunchSettingsRiskHandoff(request = collectPipelineStartRequest()) {
    const rows = launchSettingsRiskRows(launchSettingsWorkspace(), request);
    if (state.selectedLaunchSettingsRiskKey && !rows.some((row) => row.key === state.selectedLaunchSettingsRiskKey)) {
      state.selectedLaunchSettingsRiskKey = "";
    }
    const selected = selectedLaunchSettingsRiskRow(rows);
    setText("launch-settings-risk-status", launchSettingsRiskStatus(rows));
    setText("launch-settings-risk-summary", launchSettingsRiskSummaryLines(rows).join("\n"));
    setText("launch-settings-risk-detail", launchSettingsRiskDetailLines(selected).join("\n"));
    setText("launch-settings-risk-legend", "Launch risk rows are selectable for read-only details and do not change backend launch validation.");
    const tbody = byId("launch-settings-risk-rows");
    if (!rows.length) {
      clearRows(tbody, 4, "No launch settings risk rows loaded.");
      setText("launch-settings-risk-detail", launchSettingsRiskDetailLines(null).join("\n"));
      return;
    }
    tbody.replaceChildren();
    rows.forEach((item) => {
      const row = document.createElement("tr");
      row.dataset.status = item.impact === "blocked" ? "blocked" : (item.impact === "high review" || item.impact === "review" ? "warning" : "match");
      appendCells(row, [item.area, item.impact, item.evidence, item.action]);
      if (typeof makeRowSelectable === "function") {
        makeRowSelectable(row, () => selectLaunchSettingsRiskRow(item), {
          selected: item.key === selected?.key,
          label: `Launch risk ${item.area || ""} ${item.impact || ""}`,
        });
      }
      tbody.appendChild(row);
    });
    updateTableStatusLegend("launch-settings-risk-legend", tbody, "Launch risk rows");
  }

  function launchSettingsIntentPayload(payload = null) {
    if (payload && typeof payload === "object") return payload;
    try {
      if (typeof getLastLaunchReadinessPayload === "function") return getLastLaunchReadinessPayload() || {};
    } catch {
      return {};
    }
    return {};
  }

  function launchSettingsIntentLatestCommand(predicate) {
    const history = typeof getCommandHistory === "function" ? getCommandHistory() : [];
    if (!Array.isArray(history)) return null;
    return history.find(predicate) || null;
  }

  function launchSettingsIntentCommandLine(entry) {
    if (!entry) return "No matching command is visible in recent command history.";
    if (typeof launchHistoryLine === "function" && isLaunchCommand(entry)) return launchHistoryLine(entry);
    if (typeof settingsCommandHistoryLine === "function" && String(entry.command || "").toLowerCase().startsWith("settings.")) {
      return settingsCommandHistoryLine(entry);
    }
    return `${entry.at || ""} ${entry.command || "unknown"} [${entry.result || (entry.ok ? "ok" : entry.severity || "unknown")}] ${entry.message || ""}`.trim();
  }

  function launchSettingsIntentStagedPatchStatus() {
    if (typeof settingsPatchIsTouched !== "function" || settingsPatchIsTouched() !== true) {
      return {
        posture: "ready",
        evidence: "Settings Changes JSON has not been touched in this WebView session.",
        action: "Launch will use saved backend settings.",
        detail: ["No staged settings patch is visible in the current WebView session."],
      };
    }
    if (typeof settingsPatchEffectiveChangedEntries !== "function") {
      return {
        posture: "review",
        evidence: "Settings patch was touched, but patch-impact helpers are unavailable.",
        action: "Use Settings Preview/Save before relying on changed settings.",
        detail: ["The Launch page cannot inspect staged settings changes, so saved backend settings remain the only launch input."],
      };
    }
    try {
      const entries = settingsPatchEffectiveChangedEntries();
      if (!entries.length) {
        return {
          posture: "ready",
          evidence: "Settings Changes JSON was touched, but no effective saved-value changes are staged.",
          action: "Launch can continue to rely on saved backend settings.",
          detail: ["Staged keys either match saved values or no effective changed keys were detected."],
        };
      }
      const rows = typeof settingsLaunchImpactRows === "function" ? settingsLaunchImpactRows(entries) : [];
      const status = typeof settingsLaunchImpactStatus === "function" ? settingsLaunchImpactStatus(rows) : "Review";
      const deltaRows = typeof settingsPolicyDeltaRows === "function" ? settingsPolicyDeltaRows(entries) : [];
      const deltaStatus = typeof settingsPolicyDeltaStatus === "function" && deltaRows.length
        ? settingsPolicyDeltaStatus(deltaRows)
        : "Not evaluated";
      const deltaReviewRows = deltaRows.filter((row) => {
        const posture = String(row.posture || "").toLowerCase();
        return posture.includes("blocked") || posture.includes("critical") || posture.includes("review") || posture.includes("staged") || posture.includes("preview");
      });
      const policyRows = typeof launchPolicyBoundaryRows === "function" ? launchPolicyBoundaryRows(launchSettingsWorkspace()) : [];
      const policyReviewRows = policyRows.filter((row) => !["ready", "launch-active", "same as saved"].includes(row.launchState));
      return {
        posture: String(status).toLowerCase().includes("blocked") ? "blocked" : String(status).toLowerCase().includes("high") ? "high review" : "review",
        evidence: `${entries.length} unsaved effective change(s): ${entries.map((entry) => entry.key).slice(0, 8).join(", ")}${entries.length > 8 ? `, +${entries.length - 8} more` : ""}.`,
        action: "Save Patch must succeed and settings must reload/refresh before Launch uses these changes.",
        detail: [
          `Settings handoff status: ${status}`,
          `Staged media-policy delta: ${deltaStatus}`,
          `Launch active policy boundary: ${typeof launchPolicyBoundaryStatus === "function" ? launchPolicyBoundaryStatus(policyRows) : "not evaluated"}`,
          policyReviewRows.length
            ? `First launch policy boundary row: ${policyReviewRows[0].area} (${policyReviewRows[0].launchState}) - ${policyReviewRows[0].action}`
            : "No launch policy boundary review rows detected locally.",
          deltaReviewRows.length
            ? `First staged delta review row: ${deltaReviewRows[0].area} (${deltaReviewRows[0].posture}) - ${deltaReviewRows[0].check}`
            : "No staged media-policy delta review rows detected locally.",
          "Unsaved Changes JSON does not change backend launch input.",
          "Use Settings > Preview Patch, then Save Patch, then refresh before treating these changes as launch-active.",
        ],
      };
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      return {
        posture: "review",
        evidence: `Settings Changes JSON is invalid: ${message}`,
        action: "Fix Settings Changes JSON before preview/save; Launch still uses saved backend settings.",
        detail: [
          `JSON error: ${message}`,
          "Invalid staged JSON cannot be previewed or saved by Settings.",
          "The backend launch route will still evaluate the saved config on disk.",
        ],
      };
    }
  }

  function launchSettingsIntentRows(request = collectPipelineStartRequest(), payload = launchSettingsIntentPayload()) {
    const context = launchSettingsIntentPayload(payload);
    const settings = launchSettingsWorkspace();
    const schedule = context.schedule || {};
    const closeReadiness = context.closeReadiness || null;
    const snapshot = context.snapshot || null;
    const launchDecision = launchSettingsDecision(settings, request);
    const riskRows = launchSettingsRiskRows(settings, request);
    const blockedRiskRows = riskRows.filter((row) => row.impact === "blocked");
    const reviewRiskRows = riskRows.filter((row) => row.impact !== "ready");
    const mode = String(request?.mode || "validate");
    const override = String(request?.schedule_override || "");
    const evaluation = schedule.evaluation || {};
    const watchedMode = mode === "once" || mode === "continuous";
    const outsideWindow = Boolean(schedule.enabled && evaluation.allowed_now === false && watchedMode && !override);
    const rows = [];
    const add = (key, checkpoint, posture, evidence, action, detail = []) => rows.push({ key, checkpoint, posture, evidence, action, detail });

    add(
      "backend-authority",
      "Backend launch authority",
      "ready",
      "Pipeline, audit, rerun, and pending-drain starts call backend-owned routes.",
      "Use these controls only as requests; backend validation, schedule gates, and launch locks remain authoritative.",
      [
        "Frontend checklist rows are read-only and cannot start, retry, drain, save settings, rewrite queue state, or touch files.",
        "Backend command routes still own acceptance, rejection, process launch, command journaling, and refresh hints.",
      ],
    );

    add(
      "saved-settings",
      launchDecision.decision === "blocked" ? "Saved settings block" : "Saved settings posture",
      launchDecision.decision === "blocked" ? "blocked" : launchDecision.decision === "review" ? "review" : "ready",
      `Saved settings status=${launchDecision.status}; mode=${pipelineModeLabel(mode)}.`,
      launchDecision.guidance,
      launchSettingsDecisionLines(settings, request),
    );

    const patchStatus = launchSettingsIntentStagedPatchStatus();
    add(
      "staged-settings",
      "Staged Settings patch",
      patchStatus.posture,
      patchStatus.evidence,
      patchStatus.action,
      patchStatus.detail,
    );

    add(
      "mode-override",
      "Selected launch intent",
      mode === "continuous" && override === "ignore" ? "high review" : mode === "continuous" ? "review" : "ready",
      `mode=${pipelineModeLabel(mode)}; sleep=${request?.sleep_seconds || 30}s; schedule override=${override || "none"}.`,
      mode === "continuous"
        ? "Continuous runs are unattended-sensitive; verify schedule, settings, and close-readiness before confirming."
        : "Confirm the selected mode matches the current operator intent before starting.",
      [
        `Show config: ${request?.show_config ? "yes" : "no"}`,
        `Show console: ${request?.show_console ? "yes" : "no"}`,
        `Single file: ${request?.single_file ? "operator-provided backend request" : "not requested"}`,
        override === "ignore" ? "Ignore Schedule bypasses schedule-window protection for this launch request." : "No full schedule bypass is selected.",
      ],
    );

    add(
      "active-work",
      "Active work / close-readiness",
      closeReadiness?.safe_to_close === false || closeReadiness?.active_work === true ? "blocked" : closeReadiness ? "ready" : "unknown",
      `snapshot=${snapshot ? (snapshot.pipeline_state || "loaded") : "missing"}; close=${closeReadiness ? (closeReadiness.safe_to_close ? "safe" : "active/blocked") : "unknown"}.`,
      closeReadiness?.safe_to_close === false || closeReadiness?.active_work === true
        ? "Do not start another media run until active work is complete or backend-owned controls intentionally stop/pause it."
        : closeReadiness
          ? "Close-readiness does not report an active-work block."
          : "Refresh before launch if close-readiness has not loaded.",
      [
        `Close reason: ${closeReadiness?.reason || "none reported"}`,
        `Activity: ${snapshot?.activity || "none reported"}`,
      ],
    );

    add(
      "schedule-gate",
      "Schedule gate",
      outsideWindow ? "blocked" : (schedule.enabled && watchedMode && override ? "review" : schedule.enabled ? "ready" : "unknown"),
      `schedule=${schedule.enabled ? "enabled" : "off/unavailable"}; allowed_now=${evaluation.allowed_now === false ? "no" : "yes/unknown"}; override=${override || "none"}.`,
      outsideWindow
        ? "Run Once and Continuous should wait for the allowed window or use an intentional override."
        : override
          ? "Override is intentional-looking; confirm it before submitting."
          : "No schedule-window block is visible for the selected intent.",
      [
        `Next allowed start: ${typeof scheduleDisplayValue === "function" ? scheduleDisplayValue(evaluation.next_allowed_start) : (evaluation.next_allowed_start || "None")}`,
        `Current/next window end: ${typeof scheduleDisplayValue === "function" ? scheduleDisplayValue(evaluation.current_window_end || evaluation.next_allowed_end) : (evaluation.current_window_end || evaluation.next_allowed_end || "None")}`,
      ],
    );

    const queueRows = typeof getLastQueueRows === "function" ? getLastQueueRows() : [];
    const queueScope = typeof queueCurrentFilterScope === "function" ? queueCurrentFilterScope(queueRows) : null;
    add(
      "queue-filter-scope",
      "Queue display scope",
      queueScope ? (queueScope.active ? "review" : "ready") : "unknown",
      queueScope
        ? `filters=${queueScope.active ? "active" : "inactive"}; visible=${queueScope.visibleRows}/${queueScope.totalRows}; hidden blocked=${queueScope.hiddenBlocked}; hidden review=${queueScope.hiddenReview}.`
        : "Queue display filter state is unavailable in this WebView session.",
      queueScope
        ? queueScope.active
          ? "Do not treat the visible Queue table as launch scope; clear filters or inspect hidden review rows before starting."
          : "No Queue display filter is active, but backend Launch still owns the actual processing scope."
        : "Refresh Queue before launch if the launch decision depends on queue display filters.",
      queueScope && typeof queueFilterScopeDetailLines === "function"
        ? queueFilterScopeDetailLines(queueScope)
        : [
          "Launch start requests do not include Queue filter text, status filters, investigation filters, selected table rows, or visible-row subsets.",
          "Backend Launch remains authoritative for queue scope, schedule checks, process locks, saved settings, and runtime validation.",
        ],
    );

    add(
      "risk-handoff",
      "Saved-settings risk handoff",
      blockedRiskRows.length ? "blocked" : reviewRiskRows.length ? "review" : "ready",
      `${riskRows.length} launch risk row(s); ${blockedRiskRows.length} blocked; ${reviewRiskRows.length} non-ready.`,
      blockedRiskRows.length
        ? "Resolve blocked Launch Risk Handoff rows before starting media work."
        : reviewRiskRows.length
          ? "Read Launch Risk Handoff rows before unattended runs."
          : "Launch Risk Handoff has no local non-ready rows.",
      reviewRiskRows.slice(0, 8).map((row) => `${row.area}: ${row.impact}; ${row.action}`),
    );

    const latestLaunch = launchSettingsIntentLatestCommand(isLaunchCommand);
    const latestSettings = launchSettingsIntentLatestCommand((entry) => String(entry?.command || "").toLowerCase().startsWith("settings."));
    add(
      "command-evidence",
      "Recent command evidence",
      latestLaunch || latestSettings ? "review" : "unknown",
      `latest launch=${latestLaunch ? latestLaunch.command : "none"}; latest settings=${latestSettings ? latestSettings.command : "none"}.`,
      latestLaunch || latestSettings
        ? "Use command detail/Diagnostics if recent commands warn or disagree with visible state."
        : "Recent command history has no launch/settings evidence yet.",
      [
        `Launch: ${launchSettingsIntentCommandLine(latestLaunch)}`,
        `Settings: ${launchSettingsIntentCommandLine(latestSettings)}`,
      ],
    );

    add(
      "decision-boundary",
      "Decision boundary",
      "ready",
      "This checklist explains launch intent; it is not a backend preflight result.",
      "Submit only after the checklist, Launch preflight, Queue/Reports context, and Diagnostics evidence agree.",
      [
        "Backend launch validation, process locks, schedule enforcement, and command journaling remain the source of truth.",
        "This panel cannot mutate media, queue state, config, pending-publish state, reports, or diagnostics files.",
      ],
    );

    return rows.sort((left, right) => launchSettingsSeverityRank(left.posture) - launchSettingsSeverityRank(right.posture));
  }

  function launchSettingsIntentStatus(rows = launchSettingsIntentRows()) {
    if (!rows.length) return "Not evaluated";
    if (rows.some((row) => row.posture === "blocked")) return "Blocked";
    if (rows.some((row) => row.posture === "high review")) return "High review";
    if (rows.some((row) => row.posture === "review")) return "Review";
    if (rows.some((row) => row.posture === "unknown")) return "Evidence incomplete";
    return "Ready";
  }

  function launchSettingsIntentStatusState(status) {
    const normalized = String(status || "").toLowerCase();
    if (normalized === "blocked") return "blocked";
    if (normalized === "high review" || normalized === "review") return "warning";
    if (normalized === "evidence incomplete" || normalized === "not evaluated") return "unknown";
    if (normalized === "ready") return "ready";
    return "unknown";
  }

  function launchSettingsIntentRowStatus(posture) {
    const normalized = String(posture || "").toLowerCase();
    if (normalized === "blocked") return "blocked";
    if (normalized === "high review" || normalized === "review") return "warning";
    if (normalized === "unknown") return "unknown";
    return "match";
  }

  function launchSettingsIntentSummaryLines(rows = launchSettingsIntentRows()) {
    const counts = rows.reduce((acc, row) => {
      const key = row.posture || "unknown";
      acc[key] = (acc[key] || 0) + 1;
      return acc;
    }, {});
    const reviewRows = rows.filter((row) => row.posture !== "ready");
    const stagedSettingsRow = rows.find((row) => row.key === "staged-settings");
    const lines = [
      "Saved settings vs launch intent checklist:",
      `Rows: ${rows.length}; ready=${counts.ready || 0}; review=${counts.review || 0}; high review=${counts["high review"] || 0}; blocked=${counts.blocked || 0}; unknown=${counts.unknown || 0}.`,
      "Decision rule: Launch uses saved backend settings and selected form intent only; staged Settings JSON does not count until backend Save Patch succeeds and refresh/reload completes.",
    ];
    if (stagedSettingsRow && stagedSettingsRow.posture !== "ready") {
      lines.push(`Staged settings patch: ${stagedSettingsRow.evidence} ${stagedSettingsRow.action}`);
    }
    if (reviewRows.length) {
      lines.push("First action: select non-ready checkpoints and resolve blocked/review evidence before confirming a start.");
      reviewRows.slice(0, 8).forEach((row) => lines.push(`- ${row.checkpoint}: ${row.posture}; ${row.action}`));
      if (reviewRows.length > 8) lines.push(`- ${reviewRows.length - 8} more checkpoint(s) need review.`);
    } else {
      lines.push("First action: no local launch-intent blockers are visible; backend launch validation still has final authority.");
    }
    lines.push("Mutation guardrail: this checklist is read-only and cannot launch, save settings, drain, rename, repair, delete, publish, or touch media files.");
    return lines;
  }

  function selectedLaunchSettingsIntentRow(rows) {
    const source = Array.isArray(rows) ? rows : [];
    return source.find((row) => row.key === state.selectedLaunchSettingsIntentKey) || source.find((row) => row.posture !== "ready") || source[0] || null;
  }

  function launchSettingsIntentDetailLines(row) {
    if (!row) {
      return [
        "Saved settings vs launch intent:",
        "No checklist checkpoint is selected.",
        "Mutation guardrail: this detail panel is read-only.",
      ];
    }
    const lines = [
      "Saved settings vs launch intent:",
      `Checkpoint: ${row.checkpoint || "unknown"}`,
      `Posture: ${row.posture || "unknown"}`,
      `Evidence: ${row.evidence || ""}`,
      `Operator action: ${row.action || ""}`,
    ];
    const detail = Array.isArray(row.detail) ? row.detail : [];
    if (detail.length) {
      lines.push("", "Detail:");
      detail.forEach((line) => lines.push(`- ${line}`));
    }
    lines.push("", "Guardrail: submit launch commands only from backend-owned buttons after visible evidence agrees.");
    return lines;
  }

  function selectLaunchSettingsIntentRow(row) {
    state.selectedLaunchSettingsIntentKey = row?.key || "";
    renderLaunchSettingsIntentChecklist();
  }

  function renderLaunchSettingsIntentChecklist(request = collectPipelineStartRequest(), payload = launchSettingsIntentPayload()) {
    const rows = launchSettingsIntentRows(request, payload);
    if (state.selectedLaunchSettingsIntentKey && !rows.some((row) => row.key === state.selectedLaunchSettingsIntentKey)) {
      state.selectedLaunchSettingsIntentKey = "";
    }
    const selected = selectedLaunchSettingsIntentRow(rows);
    const status = launchSettingsIntentStatus(rows);
    setText("launch-settings-intent-status", status);
    const statusNode = byId("launch-settings-intent-status");
    if (statusNode) statusNode.dataset.state = launchSettingsIntentStatusState(status);
    setText("launch-settings-intent-summary", launchSettingsIntentSummaryLines(rows).join("\n"));
    setText("launch-settings-intent-detail", launchSettingsIntentDetailLines(selected).join("\n"));
    const tbody = byId("launch-settings-intent-rows");
    if (!tbody) return;
    if (!rows.length) {
      clearRows(tbody, 4, "No saved-settings launch-intent rows loaded.");
      updateTableStatusLegend("launch-settings-intent-legend", tbody, "Saved-settings launch-intent rows");
      return;
    }
    tbody.replaceChildren();
    rows.forEach((item) => {
      const row = document.createElement("tr");
      row.dataset.status = launchSettingsIntentRowStatus(item.posture);
      appendCells(row, [item.checkpoint, item.posture, item.evidence, item.action]);
      if (typeof makeRowSelectable === "function") {
        makeRowSelectable(row, () => selectLaunchSettingsIntentRow(item), {
          selected: item.key === selected?.key,
          label: `Launch-intent checkpoint ${item.checkpoint} ${item.posture}`,
        });
      }
      tbody.appendChild(row);
    });
    updateTableStatusLegend("launch-settings-intent-legend", tbody, "Saved-settings launch-intent rows");
  }

    return {
      launchSettingsWorkspace,
      launchSettingsTrustStatus,
      launchSettingsDecision,
      launchSettingsDecisionLines,
      launchUnsavedSettingsPatchLines,
      launchSettingsRiskLines,
      launchSettingsSeverityRank,
      launchRealMediaReadinessLines,
      launchSettingsRiskRows,
      launchSettingsRiskStatus,
      launchSettingsRiskSummaryLines,
      launchSettingsRiskDetailLines,
      renderLaunchSettingsRiskHandoff,
      launchPolicyBoundaryRows,
      launchPolicyBoundaryStatus,
      launchPolicyBoundarySummaryLines,
      launchPolicyBoundaryDetailLines,
      renderLaunchPolicyBoundary,
      launchSettingsIntentPayload,
      launchSettingsIntentLatestCommand,
      launchSettingsIntentCommandLine,
      launchSettingsIntentRows,
      launchSettingsIntentStatus,
      launchSettingsIntentSummaryLines,
      launchSettingsIntentDetailLines,
      renderLaunchSettingsIntentChecklist,
    };
  }

  window.__launchViewRiskModule = {
    createLaunchRiskModule,
  };
})();
