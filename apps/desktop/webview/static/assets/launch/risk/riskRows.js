/* eslint-disable complexity, max-lines-per-function */
(function () {
  function createLaunchRiskRowsModule(deps = {}) {
    const {
      collectPipelineStartRequest = function () { return {}; },
      launchRouteHeightBoundaries = function () { return {}; },
      launchSettingsBool = function (value, fallback = false) { return fallback; },
      launchSettingsConfigValue = function () { return undefined; },
      launchSettingsWorkspace = function () { return {}; },
      pipelineModeLabel = function (mode) { return mode || "Pipeline"; },
      settingsLaunchImpactRows = null,
      settingsLaunchImpactStatus = null,
      settingsPatchEffectiveChangedEntries = null,
      settingsPatchIsTouched = null,
      settingsPolicyDeltaRows = null,
      settingsPolicyDeltaStatus = null,
    } = deps;

  function launchBackendPolicyImpact(settings = launchSettingsWorkspace()) {
    const impact = settings?.policy_impact || {};
    if (!impact || impact.schema_version !== "settings_policy_impact.v1") return null;
    return impact;
  }

  function launchSettingsNormalizeBackendRiskRow(row, request = collectPipelineStartRequest()) {
    const mode = request?.mode || "unknown";
    const launchModeLabel = pipelineModeLabel(mode);
    const context = row?.launch_context && typeof row.launch_context === "object"
      ? (row.launch_context[mode] || row.launch_context.default || null)
      : null;
    const replaceLaunchContext = (value) => String(value || "").split("{launch_mode}").join(launchModeLabel);
    return {
      key: String(row?.key || row?.area || "risk-row").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "") || "risk-row",
      area: row?.area || "Policy risk",
      impact: context?.impact || row?.impact || "review",
      evidence: replaceLaunchContext(row?.evidence),
      action: replaceLaunchContext(context?.action || row?.action),
      detail: Array.isArray(row?.detail) ? row.detail.map(replaceLaunchContext) : [],
      source: row?.source || "backend",
    };
  }

  function launchSettingsBackendRiskRows(settings = launchSettingsWorkspace(), request = collectPipelineStartRequest()) {
    const handoff = launchBackendPolicyImpact(settings)?.launch_risk_handoff || {};
    if (!handoff || handoff.schema_version !== "settings_launch_risk_handoff.v1") return [];
    const sourceRows = Array.isArray(handoff.rows) ? handoff.rows : [];
    const rows = sourceRows.map((row) => launchSettingsNormalizeBackendRiskRow(row, request));
    if (request?.mode === "continuous" && rows.some((row) => row.impact !== "ready")) {
      const continuousRow = handoff.continuous_mode_row && typeof handoff.continuous_mode_row === "object"
        ? launchSettingsNormalizeBackendRiskRow(handoff.continuous_mode_row, request)
        : null;
      if (continuousRow && !rows.some((row) => row.key === continuousRow.key)) rows.push(continuousRow);
    }
    return rows.sort((left, right) => launchSettingsSeverityRank(left.impact) - launchSettingsSeverityRank(right.impact));
  }

  const LAUNCH_ATTENTION_RISK_CODES = new Set([
    "custom_video_flags_enabled",
    "fallback_remux_size_guard",
    "quality_block_review_enabled",
    "short_copy_timeout",
    "strict_size_guard",
  ]);

  function launchRawVideoFlagsActive(encodeTuning, extraVideoFlags = []) {
    return String(encodeTuning || "").trim().toLowerCase() === "custom_legacy_flags" && extraVideoFlags.length > 0;
  }

  function launchRiskItemNeedsAttention(item, options = {}) {
    const severity = String(item?.severity || "").toLowerCase();
    const code = String(item?.code || "").toLowerCase();
    if (severity === "critical" || severity === "high") return true;
    if (code === "raw_video_flags_present" && options.rawVideoFlagsActive) return true;
    return LAUNCH_ATTENTION_RISK_CODES.has(code);
  }

  function launchAttentionRiskItems(riskItems = [], options = {}) {
    return riskItems.filter((item) => launchRiskItemNeedsAttention(item, options));
  }

  function launchAttentionImpact(attentionItems = [], errors = []) {
    if (errors.length) return "blocked";
    if (attentionItems.some((item) => String(item?.severity || "").toLowerCase() === "critical")) return "blocked";
    if (attentionItems.some((item) => String(item?.severity || "").toLowerCase() === "high")) return "high review";
    return attentionItems.length ? "review" : "ready";
  }

  function launchSettingsTrustStatus(settings = launchSettingsWorkspace()) {
    if (!settings || typeof settings !== "object" || !settings.schema_version) return "Not loaded";
    const errors = Array.isArray(settings.errors) ? settings.errors : [];
    if (errors.length) return "Invalid";
    const rows = launchSettingsRiskRows(settings, collectPipelineStartRequest());
    return rows.length ? launchSettingsRiskStatus(rows) : "Ready";
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
      reasons.push("saved settings contain high-impact launch rows");
    } else if (normalized.includes("review")) {
      decision = "review";
      reasons.push("saved settings contain launch-affecting review rows");
    }
    if (decision === "review" && mode === "continuous") {
      reasons.push("continuous mode is unattended-sensitive");
    }
    let guidance = "Saved settings look ready for this launch mode.";
    if (decision === "blocked") {
      guidance = "Do not start media work until Settings > Validate / Reload is clean.";
    } else if (decision === "review" && mode === "continuous") {
      guidance = "Prefer Validate or Run Once until highlighted launch-affecting settings are understood.";
    } else if (decision === "review") {
      guidance = "Review highlighted launch-affecting settings before unattended work.";
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
      "Launch settings evidence snapshot:",
      `- Evidence posture: ${decision.decision}`,
      `- Saved settings status: ${decision.status}`,
      `- Launch mode: ${pipelineModeLabel(decision.mode)}`,
    ];
    if (decision.reasons.length) {
      lines.push(`- Reason: ${decision.reasons.join("; ")}`);
    } else {
      lines.push("- Reason: no launch-affecting saved-settings rows are currently highlighted.");
    }
    lines.push(`- Evidence guidance: ${decision.guidance}`);
    lines.push("- Evidence owner: Settings page edits/save; Launch page displays saved posture only.");
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
        "Unsaved Settings changes:",
        `- Unsaved keys: ${keys.slice(0, 8).join(", ")}${keys.length > 8 ? `, +${keys.length - 8} more` : ""}`,
        `- Settings handoff status: ${status}`,
        `- Save-candidate media-policy delta: ${deltaStatus}`,
        "- Launch uses saved backend settings only. Unsaved settings changes will not affect this launch until Save Settings succeeds and settings reload/refresh completes.",
      ];
      if (deltaReviewRows.length) {
        lines.push(`- First save-candidate delta review row: ${deltaReviewRows[0].area} (${deltaReviewRows[0].posture}) - ${deltaReviewRows[0].check}`);
      }
      return lines;
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      return [
        "",
        "Unsaved Settings changes:",
        `- Settings Changes JSON is invalid: ${message}`,
        "- Launch will continue using saved backend settings; Save Settings cannot run until Changes JSON is valid.",
      ];
    }
  }

  function launchSettingsRiskLines(request = null) {
    const settings = launchSettingsWorkspace();
    const config = settings.config || {};
    const risk = settings.risk_summary || {};
    const warnings = Array.isArray(settings.warnings) ? settings.warnings : [];
    const errors = Array.isArray(settings.errors) ? settings.errors : [];
    const lines = ["Saved settings evidence:"];
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
      lines.push("- Operator guidance: save settings or use Diagnostics before launching if high-risk items are unexpected.");
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
    lines.push(`- If encoded output is too large: ${sizeGuard}`);
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
    const backendRows = launchSettingsBackendRiskRows(settings, request);
    if (backendRows.length) return backendRows;

    // Frontend advisory fallback only for older/missing backend DTOs; backend
    // policy_impact.launch_risk_handoff is preferred when available.
    const config = settings?.config || {};
    const risk = settings?.risk_summary || {};
    const warnings = Array.isArray(settings?.warnings) ? settings.warnings : [];
    const errors = Array.isArray(settings?.errors) ? settings.errors : [];
    const riskItems = Array.isArray(risk.items) ? risk.items : [];
    const mediaReadiness = settings?.media_policy_readiness || {};
    const mediaReadinessRows = Array.isArray(mediaReadiness.rows) ? mediaReadiness.rows : [];
    const mediaReadinessCounts = mediaReadiness.counts || {};
    const mediaReadinessStatus = String(mediaReadiness.operator_status || "not evaluated").toLowerCase();
    const total = Number(risk.total_count || 0);
    const mode = request?.mode || "unknown";
    const deferred = launchSettingsBool(launchSettingsConfigValue(config, "DeferredPublish"), false);
    const stabilitySkipped = launchSettingsBool(launchSettingsConfigValue(config, "SkipStabilityCheck"), false);
    const integrity = launchSettingsBool(launchSettingsConfigValue(config, "EnableIntegrityCheck"), true);
    const allowNoAudio = launchSettingsBool(launchSettingsConfigValue(config, "AllowNoAudio"), false);
    const allowSystemTools = launchSettingsBool(launchSettingsConfigValue(config, "AllowSystemTools"), false);
    const convertTx3g = launchSettingsBool(launchSettingsConfigValue(config, "ConvertTx3gToSrt"), true);
    const dropTx3g = launchSettingsBool(launchSettingsConfigValue(config, "DropTx3gAfterConversion"), false);
    const convertBdpgs = launchSettingsBool(launchSettingsConfigValue(config, "ConvertBdpgsToSrt"), false);
    const dropBdpgs = launchSettingsBool(launchSettingsConfigValue(config, "DropBdpgsAfterConversion"), false);
    const convertVobSub = launchSettingsBool(launchSettingsConfigValue(config, "ConvertVobSubToSrt"), false);
    const dropVobSub = launchSettingsBool(launchSettingsConfigValue(config, "DropVobSubAfterConversion"), false);
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
    const movie1080pTarget = launchSettingsConfigValue(config, "MovieRoute1080pTargetSizeGB") ?? "8";
    const movie1440pTarget = launchSettingsConfigValue(config, "MovieRoute1440pTargetSizeGB") ?? "8";
    const movie4kTarget = launchSettingsConfigValue(config, "MovieRoute4KTargetSizeGB") ?? "8";
    const tv1080pTarget = launchSettingsConfigValue(config, "TVRoute1080pTargetSizeGB") ?? "3";
    const tv1440pTarget = launchSettingsConfigValue(config, "TVRoute1440pTargetSizeGB") ?? "3";
    const tv4kTarget = launchSettingsConfigValue(config, "TVRoute4KTargetSizeGB") ?? "3";
    const routeBoundaries = launchRouteHeightBoundaries(config);
    const route1080pMaxBitrate = launchSettingsConfigValue(config, "Route1080pMaxVideoBitrateMbps") ?? "20";
    const route1440pMaxBitrate = launchSettingsConfigValue(config, "Route1440pMaxVideoBitrateMbps") ?? "35";
    const route4kMaxBitrate = launchSettingsConfigValue(config, "Route4KMaxVideoBitrateMbps") ?? "35";
    const encodeTuning = launchSettingsConfigValue(config, "EncodeTuningPreset") || "default";
    const encodeLadder = launchSettingsConfigValue(config, "EncodeLadder") || "default";
    const videoCodec = launchSettingsConfigValue(config, "VideoCodec") || "default";
    const extraVideoFlagsValue = launchSettingsConfigValue(config, "ExtraVideoFlags") || [];
    const extraVideoFlags = Array.isArray(extraVideoFlagsValue) ? extraVideoFlagsValue : String(extraVideoFlagsValue).split(/[,;]/).map((item) => item.trim()).filter(Boolean);
    const rawVideoFlagsActive = launchRawVideoFlagsActive(encodeTuning, extraVideoFlags);
    const extraFlagsState = rawVideoFlagsActive ? "active custom passthrough" : extraVideoFlags.length ? "inactive with structured preset" : "none";
    const launchAttentionItems = launchAttentionRiskItems(riskItems, { rawVideoFlagsActive });
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
      launchAttentionImpact(launchAttentionItems, errors),
      `highest=${risk.highest_severity || "none"}; risk items=${total}; launch attention=${launchAttentionItems.length}; warnings=${warnings.length}; errors=${errors.length}`,
      errors.length || launchAttentionItems.some((item) => String(item?.severity || "").toLowerCase() === "critical")
        ? "Use Settings > Validate / Reload and resolve critical settings before launch."
        : launchAttentionItems.length
          ? "Review launch-affecting settings before unattended starts; backend launch validation still has final authority."
          : total || warnings.length
            ? "Non-blocking settings notes are present; Launch highlights only settings that can block launch, fail work, or weaken safety gates."
          : "No saved-settings risk items currently reported.",
      [
        "Proof source: backend settings workspace and risk summary loaded into the WebView.",
        "Operator proof: Settings Validate/Preview responses should agree with this row before unattended starts.",
        "Boundary: this Launch page row cannot save settings or modify the active PSD1.",
      ],
    );
    add(
      "Backend media-policy readiness",
      mediaReadinessStatus.includes("blocked") ? "blocked" : mediaReadinessRows.length ? "ready" : "review",
      `schema=${mediaReadiness.schema_version || "missing"}; rows=${mediaReadinessRows.length}; coherent=${mediaReadinessCounts.coherent || 0}; review=${mediaReadinessCounts.review || 0}; blocked=${mediaReadinessCounts.blocked || 0}`,
      mediaReadinessStatus.includes("blocked")
        ? "Resolve blocked saved media-policy rows before launching unattended work."
        : mediaReadinessStatus.includes("review")
          ? "Non-blocking media-policy notes remain available in Settings; Launch highlights only blocked media-policy contradictions."
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
      "ready",
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
      sizeGuard === "strict" || sizeGuard === "fallback_remux" || rawVideoFlagsActive ? "review" : "ready",
      `routing=${routingProfile}; if encoded output is too large=${sizeGuard}; normal growth=${maxGrowth}%; compatibility growth=${compatGrowth}%; targets 1080p movie/TV=${movie1080pTarget}/${tv1080pTarget}GB, 1440p movie/TV=${movie1440pTarget}/${tv1440pTarget}GB, 4K movie/TV=${movie4kTarget}/${tv4kTarget}GB; unknown height uses the 1080p movie/TV targets and ${route1080pMaxBitrate}Mbps cap; bitrate caps 1080p<=${routeBoundaries.route1080pMaxHeight}p ${route1080pMaxBitrate}Mbps, 1440p ${routeBoundaries.route1440pMinHeight}-${routeBoundaries.route1440pMaxHeight}p ${route1440pMaxBitrate}Mbps, 4K>=${routeBoundaries.route4kMinHeight}p ${route4kMaxBitrate}Mbps; codec=${videoCodec}; tuning=${encodeTuning}; ladder=${encodeLadder}; extra flags=${extraVideoFlags.length} (${extraFlagsState})`,
      rawVideoFlagsActive
        ? "Raw ExtraVideoFlags are active through custom_legacy_flags; confirm the FFmpeg/NVENC flags before unattended encodes."
        : sizeGuard === "strict" || sizeGuard === "fallback_remux"
          ? "Output Size Check can fail or reroute oversized encodes; confirm this is intentional before unattended runs."
          : "Saved route, growth-limit, encoder, and container settings are launch-normal; use Settings Preview only when changing policy.",
      [
        "Proof source: saved routing profile, output-size guard, thresholds, encoder choice, ladder, and extra video flags.",
        "Operator proof: compare Completed source/output size evidence after the first sample file.",
        "Boundary: this is not a media-policy change and does not force remux or encode.",
      ],
    );
    add(
      "H.264 copy / remux precision",
      "ready",
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
      outputContainer === "mp4" && (!dropBdpgs || !dropVobSub || !dropAss) ? "review" : "ready",
      `container=${outputContainer}; TX3G drop=${dropTx3g ? "on" : "off"}; BDPGS drop=${dropBdpgs ? "on" : "off"}; VobSub drop=${dropVobSub ? "on" : "off"}; ASS drop=${dropAss ? "on" : "off"}`,
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
      (dropTx3g && !convertTx3g) || (dropBdpgs && !convertBdpgs) || (dropVobSub && !convertVobSub) ? "blocked" : "ready",
      `TX3G convert=${convertTx3g ? "on" : "off"} drop=${dropTx3g ? "on" : "off"}; BDPGS OCR=${convertBdpgs ? "on" : "off"} drop=${dropBdpgs ? "on" : "off"}; VobSub OCR=${convertVobSub ? "on" : "off"} drop=${dropVobSub ? "on" : "off"}`,
      (dropTx3g && !convertTx3g) || (dropBdpgs && !convertBdpgs) || (dropVobSub && !convertVobSub)
        ? "Do not launch media work with drop-without-convert subtitle contradictions."
        : "Preferred-language non-SRT subtitles should create SRT while originals stay unless drop toggles are intentional.",
      [
        "Proof source: saved TX3G/BDPGS/VobSub conversion and drop toggles.",
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
      "ready",
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
      "ready",
      "Preview/build/release gates do not prove FFmpeg, subtitle, audio, sidecar, size, or publish behavior on a specific media file.",
      mode === "validate"
        ? "Validate mode checks config posture; follow with a small real Run Once before treating WebView as daily-driver ready."
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
        "Launch mode is Continuous and at least one saved setting row can block, fail, or weaken safety gates.",
        "Prefer Validate or Run Once until launch-affecting settings risk is understood.",
        [
          "Proof source: selected Continuous mode plus at least one non-ready launch risk row.",
          "Operator proof: resolve or intentionally accept launch-affecting rows before unattended continuous processing.",
          "Boundary: backend launch validation still has final authority over whether Continuous can start.",
        ],
      );
    }
    launchAttentionItems.slice(0, 3).forEach((item) => {
      const severity = String(item?.severity || "review").toLowerCase();
      add(
        `Risk item: ${item?.key || item?.code || "setting"}`,
        severity === "critical" ? "blocked" : severity === "high" ? "high review" : "review",
        `${item?.code || "risk"}: ${item?.message || "Review saved setting."}`,
        "Use Save Settings or Diagnostics before launch if this risk is unexpected.",
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
      "Backend launch validation, process locks, and Settings Save remain the source of truth.",
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

    return {
      launchBackendPolicyImpact,
      launchSettingsNormalizeBackendRiskRow,
      launchSettingsBackendRiskRows,
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
    };
  }

  window.__launchRiskRowsModule = {
    createLaunchRiskRowsModule,
  };
})();
