(function () {
  function createLaunchRiskPolicyBoundaryModule(deps = {}) {
    const {
      launchPolicyAudioKeys = [],
      launchPolicyBoundaryRowsFallback = function () { return []; },
      launchPolicyCandidatePosture = function () { return "preview required"; },
      launchPolicyChangedKeys = function () { return []; },
      launchPolicyEntryMap = function () { return new Map(); },
      launchPolicyFormatAudio = function () { return { evidence: "" }; },
      launchPolicyFormatPublish = function () { return { evidence: "" }; },
      launchPolicyFormatSubtitle = function () { return { evidence: "" }; },
      launchPolicyPatchState = function () { return { touched: false, entries: [], error: "" }; },
      launchPolicyPublishKeys = [],
      launchPolicySubtitleKeys = [],
      launchSettingsWorkspace = function () { return {}; },
    } = deps;

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

    return {
      launchPolicyBoundaryRows,
      launchPolicyBoundaryStatus,
      launchPolicyBoundaryRowStatus,
      launchPolicyBoundarySummaryLines,
      launchPolicyBoundaryDetailLines,
    };
  }

  window.__launchRiskPolicyBoundaryModule = {
    createLaunchRiskPolicyBoundaryModule,
  };
})();
