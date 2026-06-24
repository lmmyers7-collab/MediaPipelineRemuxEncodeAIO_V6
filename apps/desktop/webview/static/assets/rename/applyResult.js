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
      const counts = renameApplyOutcomeCounts(data, rows);
      const lines = [
        `Command: ${payload.command || "rename.apply"}`,
        `Result: ${payload.ok ? "ok" : payload.severity || "error"}`,
        `Message: ${payload.message || ""}`,
        `Selected rows: ${data.selected ?? selectedSources.length ?? ""}`,
        `Applied rows: ${data.applied_count ?? rows.length}`,
        `Renamed media files: ${counts.renamed}`,
        `Unchanged media files: ${counts.unchanged}`,
        `Skipped rows: ${counts.skipped}`,
        `Protected rows: ${counts.protected}`,
        `Failed rows: ${counts.failed}`,
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

    function renameApplyOutcomeCounts(data, rows) {
      const sourceRows = Array.isArray(rows) ? rows : [];
      const explicit = {
        renamed: Number.isFinite(Number(data.renamed)),
        unchanged: Number.isFinite(Number(data.unchanged)),
        skipped: Number.isFinite(Number(data.skipped_count ?? data.skipped)),
        protected: Number.isFinite(Number(data.protected_count ?? data.protected)),
        failed: Number.isFinite(Number(data.failed_count)),
      };
      const counts = {
        renamed: explicit.renamed ? renameApplyOutcomeNumber(data.renamed, 0) : 0,
        unchanged: explicit.unchanged ? renameApplyOutcomeNumber(data.unchanged, 0) : 0,
        skipped: explicit.skipped ? renameApplyOutcomeNumber(data.skipped_count ?? data.skipped, 0) : 0,
        protected: explicit.protected ? renameApplyOutcomeNumber(data.protected_count ?? data.protected, 0) : 0,
        failed: explicit.failed ? renameApplyOutcomeNumber(data.failed_count, 0) : 0,
      };
      sourceRows.forEach((row) => {
        const status = String(row.status || row.outcome || "").toLowerCase();
        if (!explicit.renamed && (status === "success" || status === "renamed" || row.renamed === true)) counts.renamed += 1;
        else if (!explicit.unchanged && (status === "match" || status === "unchanged" || status === "noop" || status === "no-op" || row.unchanged === true)) counts.unchanged += 1;
        else if (!explicit.protected && (status === "protected" || row.protected === true)) counts.protected += 1;
        else if (!explicit.skipped && (status === "skipped" || row.skipped === true)) counts.skipped += 1;
        else if (!explicit.failed && (status === "failed" || status === "error" || row.failed === true)) counts.failed += 1;
      });
      return counts;
    }

    function renameApplyOutcomeStatus(result) {
      const payload = renameApplyOutcomePayload(result);
      if (!payload || !Object.keys(payload).length) return "No apply";
      const data = payload.data && typeof payload.data === "object" ? payload.data : {};
      const rows = Array.isArray(data.rows) ? data.rows : [];
      const warnings = Array.isArray(payload.warnings) ? payload.warnings : [];
      const errors = Array.isArray(payload.errors) ? payload.errors : [];
      if (!payload.ok || errors.length) return "Failed";
      const counts = renameApplyOutcomeCounts(data, rows);
      const mediaOperations = renameApplyOutcomeNumber(data.media_operations, counts.renamed);
      const sidecarOperations = renameApplyOutcomeNumber(data.sidecar_operations, data.sidecars || 0);
      if (warnings.length || counts.skipped || counts.protected) return "Review";
      if (counts.renamed > 0 || mediaOperations > 0 || sidecarOperations > 0) return "Applied";
      if (counts.unchanged > 0) return "No changes";
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
            "Apply checked rows only after preview/readiness agree.",
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
      const counts = renameApplyOutcomeCounts(data, rows);
      const sidecars = renameApplyOutcomeNumber(data.sidecars, 0);
      const mediaOperations = renameApplyOutcomeNumber(data.media_operations, counts.renamed);
      const sidecarOperations = renameApplyOutcomeNumber(data.sidecar_operations, sidecars);
      return [
        renameApplyOutcomeRow(
          "Backend result",
          payload.ok && !errors.length ? (warnings.length ? "review" : "ready") : "blocked",
          `${payload.command || "rename.apply"} returned ${payload.ok ? "ok" : payload.severity || "error"}; message=${payload.message || "(none)"}.`,
          payload.ok && !errors.length ? "Compare row counts below and inspect command history for durable backend evidence." : "Do not assume any rename completed; inspect warnings/errors and backend command history.",
        ),
        renameApplyOutcomeRow(
          "Selected scope",
          selected ? "ready" : "review",
          `${selected} selected source(s) submitted; request mode=${request.mode || "(unknown)"}; confirmed=${request.confirm_apply === true ? "yes" : "not reported"}.`,
          "Confirm selected_sources matches the checked preview rows.",
        ),
        renameApplyOutcomeRow(
          "Applied rows",
          counts.renamed || mediaOperations ? "changed" : applied ? "review" : "review",
          `${applied} applied row(s); ${counts.renamed} renamed media file(s); ${counts.unchanged} unchanged/no-op file(s).`,
          counts.renamed || mediaOperations ? "Spot-check renamed rows below and confirm expected no-op rows were intentional." : "If no files changed, read backend message before retrying.",
        ),
        renameApplyOutcomeRow(
          "Skipped / protected rows",
          counts.failed ? "blocked" : (counts.skipped || counts.protected ? "review" : "ready"),
          `${counts.skipped} skipped row(s); ${counts.protected} protected row(s); ${counts.failed} failed row(s).`,
          counts.skipped || counts.protected || counts.failed ? "Inspect backend reasons before another batch apply." : "No skipped, protected, or failed row evidence reported.",
        ),
        renameApplyOutcomeRow(
          "Sidecar operations",
          sidecarOperations || sidecars ? "review" : "ready",
          `${sidecars} sidecar move(s) reported; media operations=${mediaOperations}; sidecar operations=${sidecarOperations}.`,
          sidecarOperations || sidecars ? "Verify associated .pipeline.json/SRT sidecars followed the media file where expected." : "No sidecar move evidence reported.",
        ),
        renameApplyOutcomeRow(
          "Undo / rollback evidence",
          data.undo_manifest ? "ready" : "review",
          data.undo_manifest ? `Undo manifest: ${data.undo_manifest}` : "No undo manifest path reported in the backend result.",
          data.undo_manifest ? "Use Undo Last Apply for this result if the batch needs to be reversed." : "Inspect backend logs before manual repair.",
        ),
        renameApplyOutcomeRow(
          "Warnings and errors",
          errors.length ? "blocked" : warnings.length ? "review" : "ready",
          `${warnings.length} warning(s), ${errors.length} error(s).${warnings.length ? ` warnings=${warnings.slice(0, 3).join(" | ")}` : ""}${errors.length ? ` errors=${errors.slice(0, 3).join(" | ")}` : ""}`,
          errors.length || warnings.length ? "Resolve backend-reported issues before another batch apply." : "No backend warning/error evidence reported.",
        ),
        renameApplyOutcomeRow(
          "Paths textarea update",
          rows.length ? "changed" : "review",
          rows.length ? `${rows.length} backend result row(s) available for local Paths textarea replacement.` : "No backend rows available for local Paths textarea replacement.",
          "Treat updated textarea paths as local convenience only; backend command result remains source of truth.",
        ),
        renameApplyOutcomeRow(
          "Mutation boundary",
          "ready",
          "Only /api/rename/apply and /api/rename/undo can mutate rename paths. This outcome review cannot rename, retry, delete, or touch files.",
          "For any doubt, compare preview, command history, output folders, and backend logs before another mutation.",
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
          "Mutation guardrail: this panel is read-only until Apply or Undo is explicitly confirmed.",
        ];
      }
      const data = payload.data && typeof payload.data === "object" ? payload.data : {};
      const blocked = rows.filter((row) => ["failed", "blocked"].includes(String(row.posture || "").toLowerCase())).length;
      const review = rows.filter((row) => String(row.posture || "").toLowerCase() === "review").length;
      const counts = renameApplyOutcomeCounts(data, Array.isArray(data.rows) ? data.rows : []);
      return [
        "Backend rename apply outcome review:",
        `Status: ${status}; checkpoints needing review=${review}; failed/blocked=${blocked}`,
        `Applied: selected=${data.selected ?? ""}; applied=${data.applied_count ?? ""}; renamed=${counts.renamed}; unchanged=${counts.unchanged}; skipped=${counts.skipped}; protected=${counts.protected}; failed=${counts.failed}; sidecars=${data.sidecars ?? ""}`,
        `Undo manifest: ${data.undo_manifest || "(not reported)"}`,
        "Next step: verify rows/sidecars on disk only after command result and history agree.",
        "Mutation guardrail: use Undo Last Apply only when this backend result reports an undo manifest.",
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
      if (payload && typeof payload === "object" && Object.keys(payload).length) {
        const rows = Array.isArray(data.rows) ? data.rows : [];
        const counts = renameApplyOutcomeCounts(data, rows);
        const applied = renameApplyOutcomeNumber(data.applied_count, rows.length);
        const sidecars = renameApplyOutcomeNumber(data.sidecars, 0);
        const failed = !payload.ok || counts.failed > 0;
        const detail = failed
          ? String(payload.message || "Backend rename apply failed.")
          : `${counts.renamed} renamed / ${applied} applied${sidecars ? `; ${sidecars} sidecar${sidecars === 1 ? "" : "s"} followed` : ""}`;
        return [{
          id: "rename.apply",
          label: "Rename apply",
          mode: "determinate",
          percent: 100,
          status: failed ? "failed" : "complete",
          detail,
          source: payload.command || "rename.apply",
        }];
      }
      return [];
    }

    function renderRenameApplyProgress(payload) {
      if (typeof renderProgressBarsInto !== "function") return;
      const data = payload?.data && typeof payload.data === "object" ? payload.data : {};
      const progress = data.rename_progress && typeof data.rename_progress === "object" ? data.rename_progress : {};
      renderProgressBarsInto("rename-apply-progress-bars", renameApplyProgressBars(payload), progress, "No rename apply progress loaded.");
    }

    function renameApplyInFlightRows(selectedCount) {
      const planned = Math.max(0, renameApplyOutcomeNumber(selectedCount, 0));
      const countText = `${planned} checked rename${planned === 1 ? "" : "s"}`;
      return [
        renameApplyOutcomeRow(
          "Backend result",
          "active",
          `rename.apply is running for ${countText}.`,
          "Wait for the backend command result before changing checked rows or retrying apply.",
        ),
        renameApplyOutcomeRow(
          "Mutation boundary",
          "ready",
          "Filesystem mutation is still owned by /api/rename/apply; this panel is rendering request progress only.",
          "Use the final backend result and command history as durable evidence.",
        ),
      ];
    }

    function renderRenameApplyInFlight(selectedCount) {
      const planned = Math.max(0, renameApplyOutcomeNumber(selectedCount, 0));
      setText("rename-last-apply-status", `Applying ${planned} checked rename${planned === 1 ? "" : "s"}`);
      const lastStatusNode = byId("rename-last-apply-status");
      if (lastStatusNode) lastStatusNode.dataset.state = "active";
      setText("rename-last-apply-detail", "Rename apply request has been submitted to the backend. Waiting for backend result evidence.");
      setText("rename-apply-outcome-status", "Applying");
      const statusNode = byId("rename-apply-outcome-status");
      if (statusNode) statusNode.dataset.state = "active";
      setText(
        "rename-apply-outcome-summary",
        [
          "Backend rename apply outcome review:",
          `Status: Applying; selected=${planned}`,
          "Next step: wait for the backend rename.apply result before retrying, undoing, or changing scope.",
          "Mutation guardrail: this in-flight progress does not prove any file was renamed.",
        ].join("\n"),
      );
      const tbody = byId("rename-apply-outcome-rows");
      if (tbody) {
        tbody.replaceChildren();
        renameApplyInFlightRows(planned).forEach((item) => {
          const row = document.createElement("tr");
          row.dataset.status = item.posture || "";
          appendCells(row, [item.checkpoint, item.posture, item.evidence, item.action]);
          tbody.appendChild(row);
        });
      }
      setText("rename-apply-outcome-legend", "Rename apply outcome review: active=1, ready=1. Waiting for backend rename.apply result.");
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
      const counts = renameApplyOutcomeCounts(data, Array.isArray(data.rows) ? data.rows : []);
      const applied = data.applied_count ?? (Array.isArray(data.rows) ? data.rows.length : "");
      const status = renameApplyOutcomeStatus(payload);
      setText("rename-last-apply-status", payload.ok ? `${status}: ${counts.renamed} renamed / ${counts.unchanged} unchanged / ${applied} applied` : payload.severity || "failed");
      const statusNode = byId("rename-last-apply-status");
      if (statusNode) statusNode.dataset.state = renameApplyOutcomeStatusState(status);
      setText("rename-last-apply-detail", renameApplyResultLines(payload).join("\n"));
      renderRenameApplyOutcomeReview(payload);
    }

    return {
      renderRenameApplyOutcomeReview,
      renderRenameApplyInFlight,
      renderRenameApplyProgress,
      renderRenameApplyResult,
      renameApplyOutcomeCounts,
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
