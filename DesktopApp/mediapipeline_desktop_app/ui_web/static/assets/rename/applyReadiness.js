(function () {
  /* eslint-disable max-lines-per-function */
  function create(deps) {
    const {
      RENAME_PREVIEW_RENDER_LIMIT,
      appendCells,
      byId,
      collectRenameRequest,
      getCheckedRenameRows,
      getLastRenameRows,
      getRenameFinalOverrides,
      getSelectedRenameRow,
      renameConfidenceExplanation,
      renameConfidenceLabel,
      renameDuplicateTargets,
      renameRenderedRowsCount,
      renameRowCanApply,
      renameSourceKey,
      renameStatusExplanation,
      setText,
    } = deps;

    function renameApplyScopeRows() {
      const checked = getCheckedRenameRows();
      if (checked.length) return { rows: checked, source: "checked rows" };
      const selected = getSelectedRenameRow();
      return selected ? { rows: [selected], source: "selected row" } : { rows: [], source: "none" };
    }

    function renameSelectionAuditStatus(rows) {
      if (!rows.length) return "No selection";
      const blocked = rows.filter((row) => !renameRowCanApply(row)).length;
      const warning = rows.filter((row) => String(row.status || "").toLowerCase() === "warning").length;
      const match = rows.filter((row) => String(row.status || "").toLowerCase() === "match").length;
      if (blocked) return "Blocked";
      if (warning) return "Review warnings";
      if (match === rows.length) return "All match";
      return "Ready";
    }

    function renameSelectionDuplicateTargets(rows) {
      return renameDuplicateTargets(rows);
    }

    function renameApplyScopeBlockers(rows) {
      const scopedRows = Array.isArray(rows) ? rows : [];
      const duplicateTargets = renameDuplicateTargets(scopedRows);
      const destinationExistsRows = scopedRows.filter((row) => Boolean(row.destination_exists) && !row.matches_target);
      const blockers = [];
      if (duplicateTargets.length) {
        blockers.push(`duplicate destination target(s): ${duplicateTargets.slice(0, 3).join(" | ")}`);
      }
      if (destinationExistsRows.length) {
        blockers.push(`${destinationExistsRows.length} existing destination path(s) outside match/no-op rows`);
      }
      return blockers;
    }

    function renderRenameSelectionAudit() {
      const lastRenameRows = getLastRenameRows();
      const scope = renameApplyScopeRows();
      const rows = scope.rows;
      const renderedRows = renameRenderedRowsCount();
      setText("rename-selection-audit-status", renameSelectionAuditStatus(rows));
      if (!rows.length) {
        setText("rename-selection-audit", [
          "Apply scope: none",
          "Next step: check one or more applicable rows, or select a single row, before applying.",
          "Mutation guardrail: Apply still rebuilds the selected plan through the backend.",
        ].join("\n"));
        return;
      }
      const counts = rows.reduce((acc, row) => {
        const status = String(row.status || "unknown").toLowerCase();
        const change = String(row.change_kind || "unknown").toLowerCase();
        acc.status[status] = (acc.status[status] || 0) + 1;
        acc.change[change] = (acc.change[change] || 0) + 1;
        if (row.force_pipeline_name) acc.force += 1;
        acc.sidecars += Number(row.sidecar_count || 0);
        return acc;
      }, { status: {}, change: {}, force: 0, sidecars: 0 });
      const duplicates = renameSelectionDuplicateTargets(rows);
      const warnings = rows.flatMap((row) => Array.isArray(row.warnings) ? row.warnings : []);
      const errors = rows.flatMap((row) => Array.isArray(row.errors) ? row.errors : []);
      const lines = [
        `Apply scope: ${scope.source}`,
        `Rows in scope: ${rows.length}`,
        `Rendered rows: ${renderedRows} of ${lastRenameRows.length}`,
        `Statuses: ready ${counts.status.ready || 0}, match ${counts.status.match || 0}, warning ${counts.status.warning || 0}, blocked ${counts.status.blocked || 0}`,
        `Actions: rename ${counts.change.rename || 0}, case-only ${counts.change.case_only || 0}, unchanged ${counts.change.unchanged || 0}, blocked ${counts.change.blocked || 0}`,
        `Sidecar moves planned: ${counts.sidecars}`,
        `Force pipeline override rows: ${counts.force}`,
        `First source: ${rows[0]?.source_name || rows[0]?.source || ""}`,
        `Last source: ${rows[rows.length - 1]?.source_name || rows[rows.length - 1]?.source || ""}`,
      ];
      if (duplicates.length) lines.push(`Duplicate destination(s) in scope: ${duplicates.length}`);
      if (errors.length) lines.push(`Errors: ${errors.slice(0, 4).join(" | ")}`);
      if (warnings.length) lines.push(`Warnings: ${warnings.slice(0, 4).join(" | ")}`);
      if (lastRenameRows.length > RENAME_PREVIEW_RENDER_LIMIT) {
        lines.push("Render cap note: checked scope may include rows not currently rendered; Apply uses backend selected_sources for checked rows, not visible table rows only.");
      }
      lines.push("Next step: if the audit looks correct, Apply sends only this scope as backend selected_sources.");
      lines.push("Mutation guardrail: no frontend filesystem mutation is performed.");
      setText("rename-selection-audit", lines.join("\n"));
    }

    function renameApplyReadinessRow(checkpoint, posture, evidence, operatorCheck) {
      return {
        checkpoint,
        posture,
        evidence,
        operator_check: operatorCheck,
      };
    }

    function renameApplyReadinessRows() {
      const request = collectRenameRequest();
      const lastRenameRows = getLastRenameRows();
      const scope = renameApplyScopeRows();
      const rows = scope.rows;
      const previewCount = lastRenameRows.length;
      const renderedCount = renameRenderedRowsCount();
      const blockedRows = rows.filter((row) => !renameRowCanApply(row));
      const warningRows = rows.filter((row) => String(row.status || "").toLowerCase() === "warning");
      const matchRows = rows.filter((row) => String(row.status || "").toLowerCase() === "match");
      const duplicateTargets = renameDuplicateTargets(rows);
      const destinationExistsRows = rows.filter((row) => Boolean(row.destination_exists) && !row.matches_target);
      const sidecarMoves = rows.reduce((acc, row) => acc + Number(row.sidecar_count || 0), 0);
      const forceRows = rows.filter((row) => Boolean(row.force_pipeline_name)).length;
      const finalOverrides = getRenameFinalOverrides();
      const finalOverrideRows = rows.filter((row) => Boolean(row.final_name_override || finalOverrides[renameSourceKey(row)])).length;
      const firstTarget = rows[0]?.target_name || rows[0]?.destination || "";
      const lastTarget = rows[rows.length - 1]?.target_name || rows[rows.length - 1]?.destination || "";
      const readinessRows = [];

      readinessRows.push(renameApplyReadinessRow(
        "Backend preview",
        previewCount ? "ready" : "waiting",
        previewCount ? `${previewCount} backend preview row(s) loaded.` : "No backend preview rows loaded.",
        previewCount ? "Review Current, Scrubbed / Pipeline, Final, confidence, and status before apply." : "Add paths and run Preview before applying any rename.",
      ));
      readinessRows.push(renameApplyReadinessRow(
        "Render cap visibility",
        previewCount > RENAME_PREVIEW_RENDER_LIMIT ? "review" : (previewCount ? "ready" : "waiting"),
        previewCount ? `${renderedCount} of ${previewCount} preview row(s) are rendered; ${getCheckedRenameRows().length} checked row(s).` : "No preview rows are rendered.",
        previewCount > RENAME_PREVIEW_RENDER_LIMIT ? "Use Selection Audit and checked count; applying checked rows can include unrendered backend preview rows after Check Applicable Rows." : "All backend preview rows are visible in the current table render.",
      ));
      readinessRows.push(renameApplyReadinessRow(
        "Apply scope",
        rows.length ? "ready" : "blocked",
        `${scope.source}; ${rows.length} row(s) would be submitted as backend selected_sources.`,
        rows.length ? "Confirm this is the intended batch. Checked rows win; otherwise the selected row is used." : "Check applicable rows or select one row before applying.",
      ));
      readinessRows.push(renameApplyReadinessRow(
        "Blocked rows",
        blockedRows.length ? "blocked" : "ready",
        `${blockedRows.length} blocked/non-applicable row(s) in current apply scope.`,
        blockedRows.length ? "Fix preview errors before applying. Blocked rows are not safe to send to rename.apply." : "No blocked rows in the selected apply scope.",
      ));
      readinessRows.push(renameApplyReadinessRow(
        "Duplicate destinations",
        duplicateTargets.length ? "blocked" : "ready",
        duplicateTargets.length ? `${duplicateTargets.length} duplicate target(s): ${duplicateTargets.slice(0, 3).join(" | ")}` : "No duplicate destinations inside the current apply scope.",
        duplicateTargets.length ? "Change row order, overrides, or template before applying to avoid collisions." : "Batch destinations are unique within this preview scope.",
      ));
      readinessRows.push(renameApplyReadinessRow(
        "Existing destinations",
        destinationExistsRows.length ? "blocked" : "ready",
        `${destinationExistsRows.length} target path(s) already exist outside a match/no-op row.`,
        destinationExistsRows.length ? "Inspect row errors/warnings and choose a unique final name before applying." : "No existing destination collision is reported in the current scope.",
      ));
      readinessRows.push(renameApplyReadinessRow(
        "Warnings and matches",
        warningRows.length ? "review" : "ready",
        `${warningRows.length} warning row(s), ${matchRows.length} match/no-op row(s).`,
        warningRows.length ? "Open selected-row detail and review warning text before applying." : "Warnings are not present in the current apply scope.",
      ));
      const outsideRootRows = rows.filter((row) => row.path_authority === "outside_configured_roots");
      readinessRows.push(renameApplyReadinessRow(
        "Path authority",
        outsideRootRows.length ? "review" : "ready",
        outsideRootRows.length
          ? `${outsideRootRows.length} selected row(s) are outside configured SourceMovies, SourceTV, or output roots.`
          : "Selected rows are inside configured media roots or no backend root scope was reported.",
        outsideRootRows.length
          ? "Browser confirmation must include outside-root review before backend rename.apply accepts standalone paths."
          : "Continue comparing exact source and destination paths before applying.",
      ));

      if (request.mode === "movie") {
        readinessRows.push(renameApplyReadinessRow(
          "Movie scrub review",
          rows.length ? "review" : "waiting",
          `Movie seed title='${request.movie_title || "(scrub/backend)"}', year='${request.movie_year || "(scrub/backend)"}'.`,
          "Compare source name, scrubbed/pipeline guess, and final name before forcing pipeline names.",
        ));
      } else {
        readinessRows.push(renameApplyReadinessRow(
          "TV ordering review",
          rows.length > 1 ? "review" : rows.length ? "ready" : "waiting",
          `TV seed show='${request.show_name || "(auto/backend)"}', season='${request.season || "(auto/backend)"}', start='${request.start_episode || "(auto/backend)"}'; first='${firstTarget || "(none)"}'; last='${lastTarget || "(none)"}'.`,
          rows.length > 1 ? "Verify row order before apply because backend numbering follows the Paths textarea order." : "Single-row TV apply has no batch-order numbering risk.",
        ));
      }

      readinessRows.push(renameApplyReadinessRow(
        "Sidecars and pipeline force",
        sidecarMoves || forceRows || finalOverrideRows || !request.rename_sidecars ? "review" : "ready",
        `${sidecarMoves} sidecar move(s); ${forceRows} force-pipeline row(s); ${finalOverrideRows} final-name override row(s); sidecar preview ${request.rename_sidecars ? "enabled" : "disabled"}.`,
        "Confirm sidecar and force settings match pre/post-processing intent before mutation.",
      ));
      readinessRows.push(renameApplyReadinessRow(
        "Mutation boundary",
        "ready",
        "Apply posts confirm_apply plus selected_sources to /api/rename/apply; the frontend does not rename files.",
        "Use the browser confirmation and Last Apply Result/command history to verify backend outcome.",
      ));
      return readinessRows;
    }

    function renameApplyReadinessStatus(rows) {
      const lastRenameRows = getLastRenameRows();
      const items = Array.isArray(rows) ? rows : renameApplyReadinessRows();
      if (!lastRenameRows.length || !renameApplyScopeRows().rows.length) return "No scope";
      const postures = new Set(items.map((row) => String(row.posture || "").toLowerCase()));
      if (postures.has("blocked")) return "Blocked";
      if (postures.has("waiting")) return "No scope";
      if (postures.has("review")) return "Review";
      return "Ready";
    }

    function renderRenameApplyReadiness() {
      const rows = renameApplyReadinessRows();
      const tbody = byId("rename-apply-readiness-rows");
      setText("rename-apply-readiness-status", renameApplyReadinessStatus(rows));
      if (!tbody) return;
      tbody.replaceChildren();
      rows.forEach((item) => {
        const row = document.createElement("tr");
        row.dataset.status = item.posture || "";
        appendCells(row, [item.checkpoint, item.posture, item.evidence, item.operator_check]);
        tbody.appendChild(row);
      });
      const counts = rows.reduce((acc, item) => {
        const key = String(item.posture || "unknown").toLowerCase();
        acc[key] = (acc[key] || 0) + 1;
        return acc;
      }, {});
      const countText = Object.keys(counts).sort().map((key) => `${key}=${counts[key]}`).join(", ");
      setText("rename-apply-readiness-legend", `Rename apply readiness: ${countText || "none"}. Read-only; backend rename.apply remains the only filesystem mutation path.`);
    }

    function renderRenameDetail(item) {
      if (!item) {
        setText("rename-detail", "No rename row selected. Select a preview row to inspect confidence, source logic, warnings, sidecar moves, and exact destination.");
        return;
      }
      const warnings = Array.isArray(item.warnings) ? item.warnings : [];
      const errors = Array.isArray(item.errors) ? item.errors : [];
      const confidenceReasons = Array.isArray(item.confidence_reasons) ? item.confidence_reasons : [];
      const sidecarMoves = Array.isArray(item.sidecar_moves) ? item.sidecar_moves : [];
      const detail = [
        `Source: ${item.source || ""}`,
        `Destination: ${item.destination || ""}`,
        `Source folder: ${item.source_parent || ""}`,
        `Destination folder: ${item.destination_parent || ""}`,
        `Pipeline guess: ${item.pipeline_guess || ""}`,
        `Final: ${item.target_name || ""}`,
        `Template: ${item.template_preset || ""}`,
        `Change kind: ${item.change_kind || ""}`,
        `Status: ${item.status || ""}`,
        `Status meaning: ${renameStatusExplanation(item.status)}`,
        `Confidence: ${renameConfidenceLabel(item) || "not reported"}`,
        `Confidence meaning: ${renameConfidenceExplanation(item.confidence)}`,
        confidenceReasons.length ? `Confidence reason(s): ${confidenceReasons.join(" | ")}` : "",
        `Path authority: ${item.path_authority || "not reported"} (${item.path_authority_message || "no backend authority note"})`,
        `Force pipeline name: ${item.force_pipeline_name ? "yes" : "no"}`,
        `Matches current name: ${item.matches_target ? "yes" : "no"}`,
        `Sidecar moves: ${item.sidecar_count ?? sidecarMoves.length}`,
        warnings.length ? `Warnings: ${warnings.join(" | ")}` : "",
        errors.length ? `Errors: ${errors.join(" | ")}` : "",
      ].filter(Boolean);
      setText("rename-detail", detail.join("\n"));
    }

    return {
      renderRenameApplyReadiness,
      renderRenameDetail,
      renderRenameSelectionAudit,
      renameApplyReadinessRows,
      renameApplyReadinessStatus,
      renameApplyScopeBlockers,
      renameApplyScopeRows,
      renameSelectionAuditStatus,
      renameSelectionDuplicateTargets,
    };
  }

  window.mediaPipelineRenameApplyReadinessSlice = { create };
})();
