(function () {
  /* eslint-disable max-lines-per-function */
  function create(deps) {
    const {
      appendCells,
      byId,
      renderProgressBarsInto,
      setText,
    } = deps;

    function renameApplyResultLines(result) {
      const payload = result && typeof result === "object" ? result : {};
      const data = payload.data && typeof payload.data === "object" ? payload.data : {};
      const request = payload.request && typeof payload.request === "object" ? payload.request : {};
      const rows = Array.isArray(data.rows) ? data.rows : [];
      const selectedSources = Array.isArray(request.selected_sources) ? request.selected_sources : [];
      const lines = [
        `Command: ${payload.command || "rename.apply"}`,
        `Result: ${payload.ok ? "ok" : payload.severity || "error"}`,
        `Message: ${payload.message || ""}`,
        `Selected rows: ${data.selected ?? selectedSources.length ?? ""}`,
        `Applied rows: ${data.applied_count ?? rows.length}`,
        `Renamed media files: ${data.renamed ?? ""}`,
        `Unchanged media files: ${data.unchanged ?? ""}`,
        `Sidecar moves: ${data.sidecars ?? ""}`,
        `Media operations: ${data.media_operations ?? ""}`,
        `Sidecar operations: ${data.sidecar_operations ?? ""}`,
        `Undo manifest: ${data.undo_manifest || ""}`,
      ];
      const warnings = Array.isArray(payload.warnings) ? payload.warnings : [];
      const errors = Array.isArray(payload.errors) ? payload.errors : [];
      if (warnings.length) lines.push(`Warnings: ${warnings.join(" | ")}`);
      if (errors.length) lines.push(`Errors: ${errors.join(" | ")}`);
      if (rows.length) {
        lines.push("", "Rows:");
        rows.slice(0, 12).forEach((row) => {
          const sidecars = row.sidecar_count ?? row.sidecars ?? "";
          lines.push(`- ${row.source || ""} -> ${row.destination || ""} [${row.status || ""}; sidecars=${sidecars}]`);
        });
        if (rows.length > 12) lines.push(`...and ${rows.length - 12} more row(s)`);
      }
      lines.push("", "Backend rename preview/apply remains the source of truth for filesystem changes.");
      return lines;
    }

    function renameApplyOutcomePayload(result) {
      if (!result) return {};
      return result.raw && typeof result.raw === "object" ? result.raw : result;
    }

    function renameApplyOutcomeNumber(value, fallback = 0) {
      const numberValue = Number(value);
      return Number.isFinite(numberValue) ? numberValue : fallback;
    }

    function renameApplyOutcomeStatus(result) {
      const payload = renameApplyOutcomePayload(result);
      if (!payload || !Object.keys(payload).length) return "No apply";
      const data = payload.data && typeof payload.data === "object" ? payload.data : {};
      const rows = Array.isArray(data.rows) ? data.rows : [];
      const warnings = Array.isArray(payload.warnings) ? payload.warnings : [];
      const errors = Array.isArray(payload.errors) ? payload.errors : [];
      if (!payload.ok || errors.length) return "Failed";
      if (warnings.length) return "Review";
      const renamed = renameApplyOutcomeNumber(data.renamed, 0);
      const applied = renameApplyOutcomeNumber(data.applied_count, rows.length);
      const unchanged = renameApplyOutcomeNumber(data.unchanged, 0);
      if (renamed > 0 || applied > 0) return "Applied";
      if (unchanged > 0) return "No changes";
      return "Recorded";
    }

    function renameApplyOutcomeStatusState(status) {
      const normalized = String(status || "").toLowerCase();
      if (normalized.includes("fail")) return "blocked";
      if (normalized.includes("review")) return "warning";
      if (normalized.includes("applied")) return "ready";
      if (normalized.includes("recorded") || normalized.includes("no changes")) return "changed";
      return "unknown";
    }

    function renameApplyOutcomeRow(checkpoint, posture, evidence, action) {
      return { checkpoint, posture, evidence, action };
    }

    function renameApplyOutcomeRows(result) {
      const payload = renameApplyOutcomePayload(result);
      if (!payload || !Object.keys(payload).length) {
        return [
          renameApplyOutcomeRow(
            "Backend result",
            "waiting",
            "No rename.apply command result is loaded.",
            "Apply checked or selected rows only after preview/readiness agree.",
          ),
        ];
      }
      const data = payload.data && typeof payload.data === "object" ? payload.data : {};
      const request = payload.request && typeof payload.request === "object" ? payload.request : {};
      const rows = Array.isArray(data.rows) ? data.rows : [];
      const selectedSources = Array.isArray(request.selected_sources) ? request.selected_sources : [];
      const warnings = Array.isArray(payload.warnings) ? payload.warnings : [];
      const errors = Array.isArray(payload.errors) ? payload.errors : [];
      const selected = renameApplyOutcomeNumber(data.selected, selectedSources.length);
      const applied = renameApplyOutcomeNumber(data.applied_count, rows.length);
      const renamed = renameApplyOutcomeNumber(data.renamed, 0);
      const unchanged = renameApplyOutcomeNumber(data.unchanged, 0);
      const sidecars = renameApplyOutcomeNumber(data.sidecars, 0);
      const mediaOperations = renameApplyOutcomeNumber(data.media_operations, renamed);
      const sidecarOperations = renameApplyOutcomeNumber(data.sidecar_operations, sidecars);
      return [
        renameApplyOutcomeRow(
          "Backend result",
          payload.ok && !errors.length ? (warnings.length ? "review" : "ok") : "failed",
          `${payload.command || "rename.apply"} returned ${payload.ok ? "ok" : payload.severity || "error"}; message=${payload.message || "(none)"}.`,
          payload.ok && !errors.length ? "Compare row counts below and inspect command history for durable backend evidence." : "Do not assume any rename completed; inspect warnings/errors and backend command history.",
        ),
        renameApplyOutcomeRow(
          "Selected scope",
          selected ? "ok" : "review",
          `${selected} selected source(s) submitted; request mode=${request.mode || "(unknown)"}; confirmed=${request.confirm_apply === true ? "yes" : "not reported"}.`,
          "Confirm selected_sources matches the intended checked/selected preview scope.",
        ),
        renameApplyOutcomeRow(
          "Applied rows",
          applied ? "ok" : "review",
          `${applied} applied row(s); ${renamed} renamed media file(s); ${unchanged} unchanged/no-op file(s).`,
          applied ? "Spot-check renamed rows below and confirm expected no-op rows were intentional." : "If no rows applied, read backend message before retrying.",
        ),
        renameApplyOutcomeRow(
          "Sidecar operations",
          sidecarOperations || sidecars ? "review" : "ok",
          `${sidecars} sidecar move(s) reported; media operations=${mediaOperations}; sidecar operations=${sidecarOperations}.`,
          sidecarOperations || sidecars ? "Verify associated .pipeline.json/SRT sidecars followed the media file where expected." : "No sidecar move evidence reported.",
        ),
        renameApplyOutcomeRow(
          "Undo / rollback evidence",
          data.undo_manifest ? "ok" : "review",
          data.undo_manifest ? `Undo manifest: ${data.undo_manifest}` : "No undo manifest path reported in the backend result.",
          data.undo_manifest ? "Keep this path for manual recovery review if a later row looks wrong." : "Do not rely on WebView for undo; inspect backend logs before manual repair.",
        ),
        renameApplyOutcomeRow(
          "Warnings and errors",
          errors.length ? "failed" : warnings.length ? "review" : "ok",
          `${warnings.length} warning(s), ${errors.length} error(s).${warnings.length ? ` warnings=${warnings.slice(0, 3).join(" | ")}` : ""}${errors.length ? ` errors=${errors.slice(0, 3).join(" | ")}` : ""}`,
          errors.length || warnings.length ? "Resolve backend-reported issues before another batch apply." : "No backend warning/error evidence reported.",
        ),
        renameApplyOutcomeRow(
          "Paths textarea update",
          rows.length ? "ok" : "review",
          rows.length ? `${rows.length} backend result row(s) available for local Paths textarea replacement.` : "No backend rows available for local Paths textarea replacement.",
          "Treat updated textarea paths as local convenience only; backend command result remains source of truth.",
        ),
        renameApplyOutcomeRow(
          "Mutation boundary",
          "ok",
          "Only /api/rename/apply can mutate files. This outcome review cannot rename, undo, retry, delete, or touch files.",
          "For any doubt, compare preview, command history, output folders, and backend logs before applying another batch.",
        ),
      ];
    }

    function renameApplyOutcomeSummaryLines(result) {
      const payload = renameApplyOutcomePayload(result);
      const rows = renameApplyOutcomeRows(payload);
      const status = renameApplyOutcomeStatus(payload);
      if (!payload || !Object.keys(payload).length) {
        return [
          "Backend rename apply outcome review:",
          "Status: No apply",
          "Next step: run Preview, check intended rows, read Apply Readiness, then use backend-owned Apply Checked / Selected Rename.",
          "Mutation guardrail: this panel is read-only and cannot rename, undo, retry, or touch files.",
        ];
      }
      const data = payload.data && typeof payload.data === "object" ? payload.data : {};
      const blocked = rows.filter((row) => ["failed", "blocked"].includes(String(row.posture || "").toLowerCase())).length;
      const review = rows.filter((row) => String(row.posture || "").toLowerCase() === "review").length;
      return [
        "Backend rename apply outcome review:",
        `Status: ${status}; checkpoints needing review=${review}; failed/blocked=${blocked}`,
        `Applied: selected=${data.selected ?? ""}; applied=${data.applied_count ?? ""}; renamed=${data.renamed ?? ""}; unchanged=${data.unchanged ?? ""}; sidecars=${data.sidecars ?? ""}`,
        `Undo manifest: ${data.undo_manifest || "(not reported)"}`,
        "Next step: verify rows/sidecars on disk only after command result and history agree.",
        "Mutation guardrail: this panel is read-only and cannot rename, undo, retry, delete, or touch files.",
      ];
    }

    function renderRenameApplyOutcomeReview(result) {
      const payload = renameApplyOutcomePayload(result);
      const status = renameApplyOutcomeStatus(payload);
      setText("rename-apply-outcome-status", status);
      const statusNode = byId("rename-apply-outcome-status");
      if (statusNode) statusNode.dataset.state = renameApplyOutcomeStatusState(status);
      renderRenameApplyProgress(payload);
      setText("rename-apply-outcome-summary", renameApplyOutcomeSummaryLines(payload).join("\n"));
      const tbody = byId("rename-apply-outcome-rows");
      if (!tbody) return;
      const rows = renameApplyOutcomeRows(payload);
      tbody.replaceChildren();
      rows.forEach((item) => {
        const row = document.createElement("tr");
        row.dataset.status = item.posture || "";
        appendCells(row, [item.checkpoint, item.posture, item.evidence, item.action]);
        tbody.appendChild(row);
      });
      const counts = rows.reduce((acc, item) => {
        const key = String(item.posture || "unknown").toLowerCase();
        acc[key] = (acc[key] || 0) + 1;
        return acc;
      }, {});
      const countText = Object.keys(counts).sort().map((key) => `${key}=${counts[key]}`).join(", ");
      setText("rename-apply-outcome-legend", `Rename apply outcome review: ${countText || "none"}. Read-only; backend rename.apply remains the only filesystem mutation path.`);
    }

    function renameApplyProgressBars(payload) {
      const data = payload?.data && typeof payload.data === "object" ? payload.data : {};
      const progress = data.rename_progress && typeof data.rename_progress === "object" ? data.rename_progress : {};
      if (Array.isArray(progress.progress_bars)) return progress.progress_bars.filter(Boolean);
      if (Array.isArray(data.progress_bars)) return data.progress_bars.filter(Boolean);
      return [];
    }

    function renderRenameApplyProgress(payload) {
      if (typeof renderProgressBarsInto !== "function") return;
      const data = payload?.data && typeof payload.data === "object" ? payload.data : {};
      const progress = data.rename_progress && typeof data.rename_progress === "object" ? data.rename_progress : {};
      renderProgressBarsInto("rename-apply-progress-bars", renameApplyProgressBars(payload), progress, "No rename apply progress loaded.");
    }

    function renderRenameApplyResult(result) {
      if (!result) {
        setText("rename-last-apply-status", "No apply");
        setText("rename-last-apply-detail", "No rename apply result loaded.");
        renderRenameApplyOutcomeReview(null);
        return;
      }
      const payload = result.raw && typeof result.raw === "object" ? result.raw : result;
      const data = payload.data && typeof payload.data === "object" ? payload.data : {};
      const renamed = data.renamed ?? "";
      const applied = data.applied_count ?? (Array.isArray(data.rows) ? data.rows.length : "");
      setText("rename-last-apply-status", payload.ok ? `${renamed} renamed / ${applied} applied` : payload.severity || "failed");
      setText("rename-last-apply-detail", renameApplyResultLines(payload).join("\n"));
      renderRenameApplyOutcomeReview(payload);
    }

    return {
      renderRenameApplyOutcomeReview,
      renderRenameApplyProgress,
      renderRenameApplyResult,
      renameApplyOutcomeRows,
      renameApplyOutcomeStatus,
      renameApplyOutcomeStatusState,
      renameApplyOutcomeSummaryLines,
      renameApplyProgressBars,
      renameApplyResultLines,
    };
  }

  window.mediaPipelineRenameApplyResultSlice = { create };
})();
