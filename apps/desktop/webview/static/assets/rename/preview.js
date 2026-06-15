(function () {
  /* eslint-disable max-lines-per-function */
  function create(deps) {
    const {
      RENAME_PREVIEW_RENDER_LIMIT,
      collectRenameRequest,
      getCheckedRenameRows,
      getLastRenameEmptyMessage,
      getLastSettings,
      getRenameFinalOverrides,
      getRenameForceOverrides,
      renamePreviewSourceLabel,
      renameRenderedRowsCount,
      renameSourceKey,
      setText,
    } = deps;

    function renamePreviewAggregateObject(preview, aggregateKey, rowKey) {
      const aggregate = preview?.[aggregateKey];
      if (aggregate && typeof aggregate === "object" && !Array.isArray(aggregate) && Object.keys(aggregate).length) {
        return aggregate;
      }
      const rows = Array.isArray(preview?.rows) ? preview.rows : [];
      return rows.reduce((acc, row) => {
        const key = String(row?.[rowKey] || "unknown").trim() || "unknown";
        acc[key] = (acc[key] || 0) + 1;
        return acc;
      }, {});
    }

    function renameFormatCounts(counts, labeler = null) {
      if (!counts || typeof counts !== "object") return "none";
      const parts = Object.keys(counts)
        .sort()
        .map((key) => `${labeler ? labeler(key) : key}: ${counts[key]}`);
      return parts.length ? parts.join(", ") : "none";
    }

    function renameTemplateLabel(preview, key) {
      const catalog = Array.isArray(preview?.template_catalog) ? preview.template_catalog : [];
      const match = catalog.find((item) => item && item.key === key);
      return match ? `${match.label || match.key}: ${match.description || ""}`.trim() : (key || "Backend default");
    }

    function renameDuplicateTargets(rows) {
      const seen = {};
      rows.forEach((row) => {
        const key = String(row.destination || row.target_name || "").trim().toLowerCase();
        if (!key) return;
        seen[key] = (seen[key] || 0) + 1;
      });
      return Object.keys(seen).filter((key) => seen[key] > 1);
    }

    function renameReviewBoardStatus(preview) {
      const rows = Array.isArray(preview?.rows) ? preview.rows : [];
      if (!rows.length) return "No preview";
      const counts = preview?.counts || {};
      const confidenceCounts = renamePreviewAggregateObject(preview, "confidence_counts", "confidence");
      if ((counts.blocked || 0) > 0) return "Blocked";
      if ((counts.warning || 0) > 0) return "Review warnings";
      if ((confidenceCounts.blocked || 0) > 0 || (confidenceCounts.low || 0) > 0 || (confidenceCounts.unknown || 0) > 0) return "Review confidence";
      if ((confidenceCounts.medium || 0) > 0) return "Verify";
      return "Ready";
    }

    function renameReviewBoardLines(preview) {
      const request = collectRenameRequest();
      const rows = Array.isArray(preview?.rows) ? preview.rows : [];
      const counts = preview?.counts || {};
      if (!rows.length) {
        return [
          "No rename preview rows loaded.",
          "Next step: add one file path per line and run Preview.",
          "Mutation guardrail: this board is read-only; Apply uses checked rows, or all applicable safe preview rows when none are checked, through the backend selected_sources command.",
        ];
      }
      const confidenceCounts = renamePreviewAggregateObject(preview, "confidence_counts", "confidence");
      const sourceCounts = renamePreviewAggregateObject(preview, "preview_source_counts", "preview_source");
      const changeCounts = renamePreviewAggregateObject(preview, "change_kind_counts", "change_kind");
      const warningRows = rows.filter((row) => Array.isArray(row.warnings) && row.warnings.length).length;
      const errorRows = rows.filter((row) => Array.isArray(row.errors) && row.errors.length).length;
      const sidecarMoves = rows.reduce((acc, row) => acc + Number(row.sidecar_count || 0), 0);
      const forcedRows = rows.filter((row) => Boolean(row.force_pipeline_name)).length;
      const finalOverrides = getRenameFinalOverrides();
      const overrideRows = rows.filter((row) => Boolean(row.final_name_override || finalOverrides[renameSourceKey(row)])).length;
      const duplicates = renameDuplicateTargets(rows);
      const firstTarget = rows[0]?.target_name || rows[0]?.destination || "";
      const lastTarget = rows[rows.length - 1]?.target_name || rows[rows.length - 1]?.destination || "";
      const lines = [
        "Preview-wide review board. This is read-only; Apply uses checked rows, or all applicable safe preview rows when none are checked, through the backend rename.apply command.",
        `Template: ${renameTemplateLabel(preview, preview?.active_template || request.template_preset || "")}`,
        `Rows/status: ${counts.total || rows.length} total; ready ${counts.ready || 0}, match ${counts.match || 0}, warning ${counts.warning || 0}, blocked ${counts.blocked || 0}`,
        `Confidence mix: ${renameFormatCounts(confidenceCounts)}`,
        `Source-of-truth signals: ${renameFormatCounts(sourceCounts, renamePreviewSourceLabel)}`,
        `Change kinds: ${renameFormatCounts(changeCounts)}`,
        `Review flags: ${warningRows} row(s) with warnings, ${errorRows} row(s) with errors, ${duplicates.length} duplicate destination target(s)`,
        `Sidecars/forcing: ${sidecarMoves} sidecar move(s) planned, ${forcedRows} force-pipeline row(s), ${overrideRows} final-name override row(s)`,
      ];
      if (request.mode === "movie") {
        lines.push(
          `Movie seeds: title '${request.movie_title || "(scrub/backend)"}', year '${request.movie_year || "(scrub/backend)"}'`,
          "Movie review: compare Current, Scrubbed / Pipeline, and Final before forcing a pipeline name."
        );
      } else {
        lines.push(
          `TV seeds: show '${request.show_name || "(auto/backend)"}', season '${request.season || "(auto/backend)"}', start '${request.start_episode || "(auto/backend)"}'`,
          `TV range: first target '${firstTarget || "(none)"}'; last target '${lastTarget || "(none)"}'`,
          "TV review: verify row order before applying because numbering follows the current Paths textarea order."
        );
      }
      if (duplicates.length) {
        lines.push(`Duplicate target examples: ${duplicates.slice(0, 3).join(" | ")}`);
      }
      if (Array.isArray(preview?.warnings) && preview.warnings.length) {
        lines.push(`Preview warnings: ${preview.warnings.join(" | ")}`);
      }
      lines.push("Backend rename preview/apply remains the source of truth for filesystem changes.");
      return lines;
    }

    function renderRenameReviewBoard(preview) {
      setText("rename-review-board-status", renameReviewBoardStatus(preview || {}));
      setText("rename-review-board", renameReviewBoardLines(preview || {}).join("\n"));
    }

    function renderRenameSummary(preview) {
      const rows = Array.isArray(preview?.rows) ? preview.rows : [];
      if (!rows.length) {
        const warning = Array.isArray(preview?.warnings) && preview.warnings.length ? `\nWarnings: ${preview.warnings.join(" | ")}` : "";
        setText("rename-summary", `${getLastRenameEmptyMessage()}${warning}`);
        renderRenameBatchSafety(preview);
        renderRenamePipelineHandoff(preview);
        renderRenameReviewBoard(preview);
        return;
      }
      const counts = preview.counts || {};
      const confidenceCounts = renamePreviewAggregateObject(preview, "confidence_counts", "confidence");
      const sourceCounts = renamePreviewAggregateObject(preview, "preview_source_counts", "preview_source");
      const guidance = [
        `Rows: ${counts.total || rows.length}; ready: ${counts.ready || 0}; match: ${counts.match || 0}; warning: ${counts.warning || 0}; blocked: ${counts.blocked || 0}`,
        `Confidence: ${renameFormatCounts(confidenceCounts)}`,
        `Preview source: ${renameFormatCounts(sourceCounts, renamePreviewSourceLabel)}`,
        "Select a row to inspect confidence reasons, warnings, sidecar moves, and force-pipeline behavior before applying.",
        "Checked-row apply still rebuilds the plan through the backend and mutates only explicit selected_sources.",
      ];
      if (Array.isArray(preview.warnings) && preview.warnings.length) {
        guidance.push(`Preview warnings: ${preview.warnings.join(" | ")}`);
      }
      setText("rename-summary", guidance.join("\n"));
      renderRenameBatchSafety(preview);
      renderRenamePipelineHandoff(preview);
      renderRenameReviewBoard(preview);
    }

    function renameBatchSafetyLines(preview) {
      const request = collectRenameRequest();
      const rows = Array.isArray(preview?.rows) ? preview.rows : [];
      const counts = preview?.counts || {};
      const overrides = Object.keys(getRenameFinalOverrides()).length;
      const forceOverrides = Object.keys(getRenameForceOverrides()).filter((key) => getRenameForceOverrides()[key]).length;
      const lines = [
        `Mode: ${request.mode === "movie" ? "Movie" : "TV"}`,
        `Input paths: ${request.paths.length}; preview rows: ${rows.length}`,
        `Rendered preview rows: ${renameRenderedRowsCount(rows)} of ${rows.length}`,
        `Apply scope: checked rows are sent as selected_sources; if none are checked, Apply sends all applicable safe preview rows.`,
        `Sidecars: ${request.rename_sidecars ? "rename sidecar preview enabled" : "sidecar rename preview disabled"}`,
        `Pipeline naming preview: ${request.use_pipeline_naming_preview ? "preferred when backend can provide it" : "disabled"}`,
        `Global force pipeline name: ${request.force_pipeline_name ? "enabled" : "disabled"}`,
        `Overrides staged: ${overrides} final-name override(s), ${forceOverrides} force-through-pipeline override(s)`,
        `Status counts: ready ${counts.ready || 0}, match ${counts.match || 0}, warning ${counts.warning || 0}, blocked ${counts.blocked || 0}`,
        `Checked rows: ${getCheckedRenameRows().length}`,
      ];
      if (request.mode !== "movie") {
        lines.push(
          `TV sequence seed: show '${request.show_name || "(auto/backend)"}', season '${request.season || "(auto/backend)"}', start '${request.start_episode || "(auto/backend)"}'`,
          "TV ordering: backend preview follows the current Paths textarea order. Verify SxxEyy rows before checking and applying batch renames."
        );
      } else {
        lines.push(
          `Movie seed: title '${request.movie_title || "(scrub/backend)"}', year '${request.movie_year || "(scrub/backend)"}'`,
          "Movie safety: forced names should be reviewed against the scrubbed/pipeline guess before applying."
        );
      }
      if ((counts.blocked || 0) > 0) {
        lines.push("Blocked rows will not apply until backend errors are fixed.");
      }
      if ((counts.warning || 0) > 0) {
        lines.push("Warning rows can apply, but inspect row details before changing files.");
      }
      if (!rows.length) {
        lines.push("No preview rows are available yet. Add paths and run Preview.");
      } else if (rows.length > RENAME_PREVIEW_RENDER_LIMIT) {
        lines.push(`Display cap: only ${RENAME_PREVIEW_RENDER_LIMIT} rows are rendered, but Check Applicable Rows and Apply scope use the full backend preview row set.`);
      }
      lines.push("Backend rename preview/apply remains the source of truth for filesystem changes.");
      return lines;
    }

    function renderRenameBatchSafety(preview) {
      setText("rename-batch-safety", renameBatchSafetyLines(preview || {}).join("\n"));
    }

    function renameSavedSettingsConfig() {
      const settings = getLastSettings();
      return settings && typeof settings.config === "object" && settings.config ? settings.config : {};
    }

    function renameConfigValue(config, key, fallback = "(not set)") {
      const value = config && Object.prototype.hasOwnProperty.call(config, key) ? config[key] : undefined;
      if (Array.isArray(value)) return value.join(", ") || fallback;
      if (value === true) return "true";
      if (value === false) return "false";
      if (value === null || value === undefined || value === "") return fallback;
      return String(value);
    }

    function renameExtensionName(name) {
      const value = String(name || "").trim();
      const dotIndex = value.lastIndexOf(".");
      return dotIndex >= 0 ? value.slice(dotIndex).toLowerCase() : "";
    }

    function renamePipelineHandoffStatus(preview) {
      const rows = Array.isArray(preview?.rows) ? preview.rows : [];
      if (!rows.length) return "No preview";
      const config = renameSavedSettingsConfig();
      if (!Object.keys(config).length) return "Settings not loaded";
      const request = collectRenameRequest();
      const confidenceCounts = renamePreviewAggregateObject(preview, "confidence_counts", "confidence");
      const forceRows = rows.filter((row) => Boolean(row.force_pipeline_name)).length;
      const finalOverrides = getRenameFinalOverrides();
      const overrideRows = rows.filter((row) => Boolean(row.final_name_override || finalOverrides[renameSourceKey(row)])).length;
      const targetExtensions = new Set(rows.map((row) => renameExtensionName(row.target_name || row.destination || "")).filter(Boolean));
      if ((preview?.counts || {}).blocked > 0) return "Blocked";
      if (forceRows || overrideRows || !request.rename_sidecars) return "Review";
      if ((confidenceCounts.low || 0) || (confidenceCounts.unknown || 0) || (confidenceCounts.medium || 0)) return "Review confidence";
      if (targetExtensions.size > 1) return "Mixed extensions";
      return "Ready";
    }

    function renamePipelineHandoffLines(preview) {
      const rows = Array.isArray(preview?.rows) ? preview.rows : [];
      const request = collectRenameRequest();
      const config = renameSavedSettingsConfig();
      if (!rows.length) {
        return [
          "No rename preview rows loaded.",
          "Run Preview to compare target names against saved pipeline routing and sidecar/force-name behavior.",
          "Mutation guardrail: this handoff is read-only and cannot rename, save settings, launch work, remux, encode, publish, rewrite sidecars, or touch media files.",
        ];
      }
      const counts = preview?.counts || {};
      const confidenceCounts = renamePreviewAggregateObject(preview, "confidence_counts", "confidence");
      const sourceCounts = renamePreviewAggregateObject(preview, "preview_source_counts", "preview_source");
      const forceRows = rows.filter((row) => Boolean(row.force_pipeline_name)).length;
      const finalOverrides = getRenameFinalOverrides();
      const finalOverrideRows = rows.filter((row) => Boolean(row.final_name_override || finalOverrides[renameSourceKey(row)])).length;
      const sidecarMoves = rows.reduce((acc, row) => acc + Number(row.sidecar_count || 0), 0);
      const sourceExtensions = new Set(rows.map((row) => renameExtensionName(row.source_name || row.source || "")).filter(Boolean));
      const targetExtensions = new Set(rows.map((row) => renameExtensionName(row.target_name || row.destination || "")).filter(Boolean));
      const lines = [
        "Rename-to-pipeline handoff:",
        `Preview rows: ${rows.length}; ready=${counts.ready || 0}; match=${counts.match || 0}; warning=${counts.warning || 0}; blocked=${counts.blocked || 0}`,
        `Mode/template: ${request.mode === "movie" ? "Movie" : "TV"} / ${renameTemplateLabel(preview, preview?.active_template || request.template_preset || "")}`,
        `Confidence mix: ${renameFormatCounts(confidenceCounts)}`,
        `Source-of-truth signals: ${renameFormatCounts(sourceCounts, renamePreviewSourceLabel)}`,
        `Saved routing profile: ${renameConfigValue(config, "RoutingProfile")}; Output Size Check: ${renameConfigValue(config, "SizeGuardMode")}; output container: ${renameConfigValue(config, "OutputContainer")}`,
        `Saved subtitle posture: TX3G convert=${renameConfigValue(config, "ConvertTx3gToSrt")}, drop=${renameConfigValue(config, "DropTx3gAfterConversion")}; BDPGS convert=${renameConfigValue(config, "ConvertBdpgsToSrt")}, drop=${renameConfigValue(config, "DropBdpgsAfterConversion")}; VobSub convert=${renameConfigValue(config, "ConvertVobSubToSrt")}, drop=${renameConfigValue(config, "DropVobSubAfterConversion")}; ASS drop=${renameConfigValue(config, "DropAssAfterConversion")}`,
        `Saved publish posture: deferred publish=${renameConfigValue(config, "DeferredPublish")}; source delete=${renameConfigValue(config, "DeleteSourceAfterProcessing", "false")}`,
        `Filename extensions: source=${Array.from(sourceExtensions).join(", ") || "unknown"}; target=${Array.from(targetExtensions).join(", ") || "unknown"}`,
        `Sidecar/force state: sidecar preview ${request.rename_sidecars ? "enabled" : "disabled"}; planned sidecar move(s) ${sidecarMoves}; force-pipeline row(s) ${forceRows}; final-name override row(s) ${finalOverrideRows}`,
      ];
      lines.push("");
      if (!Object.keys(config).length) {
        lines.push("Operator check: saved settings are not loaded in this WebView session. Refresh before trusting routing/container/subtitle handoff text.");
      } else {
        lines.push("Operator check: renaming changes filenames only. It does not convert containers, change codecs, remux, encode, OCR subtitles, publish, or make staged Settings JSON active.");
      }
      if (String(config.OutputContainer || "").toLowerCase() === "mp4") {
        lines.push("Container note: saved OutputContainer is MP4. MP4 cannot preserve every subtitle format, so subtitle drop/convert settings matter during pipeline processing even if rename preview looks clean.");
      } else {
        lines.push("Container note: filename extension here is not proof of final mux container; the pipeline output container is governed by saved backend settings at processing time.");
      }
      if (forceRows) {
        lines.push("Force-name note: force-pipeline rows can affect future pipeline destination planning through backend sidecar/override behavior. Confirm Final names are Plex-ready before applying.");
      }
      if (finalOverrideRows) {
        lines.push("Override note: final-name overrides are explicit operator choices. Compare them with Scrubbed / Pipeline before applying.");
      }
      if (!request.rename_sidecars) {
        lines.push("Sidecar note: sidecar rename preview is disabled. Post-processing renames may leave associated sidecars behind unless the backend apply request is intentionally scoped that way.");
      }
      if ((confidenceCounts.low || 0) || (confidenceCounts.unknown || 0) || (confidenceCounts.medium || 0)) {
        lines.push("Confidence note: one or more rows are below high confidence. Inspect row detail before applying to avoid bad Plex naming or wrong TV numbering.");
      }
      lines.push("Mutation guardrail: this handoff is read-only. Apply uses checked rows, or all applicable safe preview rows when none are checked, and mutates files only through backend rename.apply selected_sources.");
      return lines;
    }

    function renderRenamePipelineHandoff(preview) {
      setText("rename-pipeline-handoff-status", renamePipelineHandoffStatus(preview || {}));
      setText("rename-pipeline-handoff", renamePipelineHandoffLines(preview || {}).join("\n"));
    }

    return {
      renderRenameBatchSafety,
      renderRenamePipelineHandoff,
      renderRenameReviewBoard,
      renderRenameSummary,
      renameBatchSafetyLines,
      renameDuplicateTargets,
      renameFormatCounts,
      renamePipelineHandoffLines,
      renamePipelineHandoffStatus,
      renamePreviewAggregateObject,
      renameReviewBoardLines,
      renameReviewBoardStatus,
      renameSavedSettingsConfig,
      renameTemplateLabel,
    };
  }

  window.mediaPipelineRenamePreviewSlice = { create };
})();
