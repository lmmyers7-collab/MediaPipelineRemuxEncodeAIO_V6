// reports/auditModel.js
// Pure audit row classification and review helpers for reportsView.js.

(function () {
  "use strict";

  function createReportsAuditModelModule(deps = {}) {
    const reportsState = deps.state && typeof deps.state === "object" ? deps.state : {};
    const reportAddDiagnosticsAction = typeof deps.reportAddDiagnosticsAction === "function" ? deps.reportAddDiagnosticsAction : function () {};
    const reportCountBy = typeof deps.reportCountBy === "function" ? deps.reportCountBy : function () { return {}; };
    const reportFormatCounts = typeof deps.reportFormatCounts === "function" ? deps.reportFormatCounts : function () { return "none"; };
    const reportNumber = typeof deps.reportNumber === "function" ? deps.reportNumber : function (value) {
      const numeric = Number(value);
      return Number.isFinite(numeric) ? numeric : 0;
    };
    const reportPreviewLoaded = typeof deps.reportPreviewLoaded === "function" ? deps.reportPreviewLoaded : function (_payload, rows) {
      return Array.isArray(rows) && rows.length > 0;
    };

    function auditRowSearchText(item) {
      return [
        item?.effective_bucket,
        item?.priority_fix_level,
        item?.primary_issue_code,
        item?.primary_suggested_action,
        item?.issue_messages,
        item?.lookup_title,
        item?.relative_path,
        item?.path,
        item?.media_type,
      ].filter(Boolean).join(" ").toLowerCase();
    }

    function auditActionOwner(item) {
      const bucket = String(item?.effective_bucket || "").toUpperCase();
      const text = auditRowSearchText(item);
      if (bucket === "REDOWNLOAD_CANDIDATE") return "Manual source review";
      if (bucket === "RERUN_PIPELINE") return "Launch CSV Rerun";
      if (text.includes("subtitle") || text.includes("bdpgs") || text.includes("tx3g") || text.includes("vobsub") || text.includes("ocr")) return "Settings policy review";
      if (text.includes("audio") || text.includes("commentary") || text.includes("language")) return "Settings policy review";
      if (text.includes("completed") || text.includes("manifest") || text.includes("output")) return "Completed evidence review";
      if (bucket === "OK") return "No action";
      return "Completed evidence review";
    }

    function auditMatchesChip(item, chip) {
      const selected = String(chip || "all");
      if (selected === "all") return true;
      const bucket = String(item?.effective_bucket || "").toUpperCase();
      const priority = String(item?.priority_fix_level || "").toUpperCase();
      const text = auditRowSearchText(item);
      if (selected === "rerun") return bucket === "RERUN_PIPELINE";
      if (selected === "redownload") return bucket === "REDOWNLOAD_CANDIDATE";
      if (selected === "review") return bucket === "REVIEW" || text.includes("review");
      if (selected === "high") return priority === "HIGH" || Number(item?.priority_score || 0) >= 80;
      if (selected === "duplicates") return text.includes("duplicate") || Boolean(item?.duplicate_group || item?.duplicate_group_key || item?.duplicate_group_size);
      return text.includes(selected);
    }

    function auditDiagnosticsActionsForRow(item) {
      const actions = [];
      reportAddDiagnosticsAction(actions, "tail", "latest_audit_csv", "Read Latest Audit CSV", "Read the bounded latest audit CSV tail.");
      reportAddDiagnosticsAction(actions, "open", "audit_reports", "Open Audit Reports", "Open the backend-selected audit report folder.");
      reportAddDiagnosticsAction(actions, "open", "completed_manifest", "Open Completed Manifest", "Compare audit row state with completed history.");
      reportAddDiagnosticsAction(actions, "open", "queue_snapshot", "Open Queue Snapshot", "Compare audit row state with current queue visibility.");
      if (!item) return actions;
      const bucket = String(item.effective_bucket || "").toUpperCase();
      if (bucket === "REDOWNLOAD_CANDIDATE") {
        reportAddDiagnosticsAction(actions, "open", "failed_reports", "Open Failure Reports", "Check whether prior failures explain the redownload recommendation.");
      }
      if (bucket === "RERUN_PIPELINE") {
        reportAddDiagnosticsAction(actions, "open", "run_logs", "Open Run Logs", "Compare rerun recommendation with recent runtime evidence.");
      }
      return actions;
    }

    function auditEmptyStateMessage(audit, rows) {
      if (audit.error) {
        return `Audit preview unavailable: ${audit.error}. Open Diagnostics > Audit Reports and run a new audit if needed.`;
      }
      const warnings = Array.isArray(audit.warnings) ? audit.warnings.filter(Boolean) : [];
      if (warnings.length) {
        return `Audit preview loaded with warning: ${warnings.join(" | ")}`;
      }
      if (!rows.length) {
        return "No audit rows found. Run Audit from Launch, or disable priority-only mode if you expected non-priority rows.";
      }
      return "No audit rows available.";
    }

    function auditRowKey(item) {
      if (item?.row_key) return String(item.row_key);
      return [
        item?.source_csv || "",
        item?.path || "",
        item?.relative_path || "",
        item?.primary_issue_code || "",
        item?.priority_score || "",
      ].join("\u001f").toLowerCase();
    }

    function auditReviewStatus() {
      const audit = reportsState.lastAuditPreviewPayload || {};
      if (audit.error) return "Unavailable";
      if (!reportPreviewLoaded(audit, reportsState.lastAuditRows)) return "Not loaded";
      if (reportNumber(audit.redownload_count) > 0) return "Redownload review";
      if (reportNumber(audit.rerun_count) > 0 || reportNumber(audit.high_priority_count) > 0) return "Rerun review";
      if (reportNumber(audit.review_count) > 0 || reportNumber(audit.duplicate_group_count) > 0) return "Review";
      if (reportsState.lastAuditRows.length) return "Loaded";
      return "No rows";
    }

    function auditReviewBoardLines() {
      const audit = reportsState.lastAuditPreviewPayload || {};
      const rows = Array.isArray(reportsState.lastAuditRows) ? reportsState.lastAuditRows : [];
      const warnings = Array.isArray(audit.warnings) ? audit.warnings.filter(Boolean) : [];
      if (audit.error) {
        return [
          "Audit review board: unavailable.",
          `Error: ${audit.error}`,
          "First action: open Latest Audit CSV and Audit Reports, then run a fresh Audit if the CSV cannot be parsed.",
          "Mutation guardrail: Reports triage is read-only; CSV rerun must be launched through backend-owned Launch controls.",
        ];
      }
      if (!reportPreviewLoaded(audit, rows)) {
        return [
          "Audit review board: no audit preview has loaded yet.",
          "First action: refresh Reports, run Audit from Launch, or turn off priority-only mode if needed.",
          "Mutation guardrail: Reports triage is read-only; it does not write CSVs, rerun rows, or change library files.",
        ];
      }
      const redownloadRows = rows.filter((row) => String(row.effective_bucket || "").toUpperCase() === "REDOWNLOAD_CANDIDATE");
      const rerunRows = rows.filter((row) => String(row.effective_bucket || "").toUpperCase() === "RERUN_PIPELINE");
      const highRows = rows.filter((row) => String(row.priority_fix_level || "").toUpperCase() === "HIGH");
      const reviewRows = [...redownloadRows, ...rerunRows, ...highRows.filter((row) => !redownloadRows.includes(row) && !rerunRows.includes(row)), ...rows.filter((row) => !redownloadRows.includes(row) && !rerunRows.includes(row) && !highRows.includes(row))];
      const lines = [
        "Audit review board:",
        `Rows: ${reportNumber(audit.count || rows.length)}`,
        `Priority CSV mode: ${audit.priority_only ? "yes" : "no"}`,
        `Bucket counts: ${reportFormatCounts(reportCountBy(rows, "effective_bucket"))}`,
        `Priority counts: ${reportFormatCounts(reportCountBy(rows, "priority_fix_level"))}`,
        `Issue-code counts: ${reportFormatCounts(reportCountBy(rows, "primary_issue_code"))}`,
        `Media counts: ${reportFormatCounts(reportCountBy(rows, "media_type"))}`,
        `Redownload rows: ${redownloadRows.length}`,
        `Rerun rows: ${rerunRows.length}`,
        `High-priority rows: ${highRows.length}`,
        `Duplicate groups: ${reportNumber(audit.duplicate_group_count)}`,
      ];
      if (warnings.length) {
        lines.push("", "Warning(s):");
        warnings.slice(0, 5).forEach((warning) => lines.push(`- ${warning}`));
      }
      if (reviewRows.length) {
        lines.push("", "First rows to inspect:");
        reviewRows.slice(0, 6).forEach((row) => {
          const title = row.lookup_title || row.relative_path || row.path || "unknown source";
          const bucket = row.effective_bucket || "unknown";
          const priority = row.priority_fix_level || row.priority_score || "no-priority";
          const issue = row.primary_issue_code || row.issue_messages || "no-issue-code";
          const action = row.primary_suggested_action || "review audit row";
          lines.push(`- ${bucket} / ${priority} / ${issue}: ${title} -> ${action}`);
        });
      }
      lines.push("");
      if (redownloadRows.length) {
        lines.push("Next step: redownload candidates should be checked manually; WebView does not auto-redownload or delete media.");
      } else if (rerunRows.length || highRows.length) {
        lines.push("Next step: inspect rows, then use backend-owned Launch > CSV Rerun with the intended CSV path.");
      } else if (rows.length) {
        lines.push("Next step: select a row to verify the bucket, issue proof, and Diagnostics handoff.");
      } else {
        lines.push("Next step: no audit rows are present; run Audit from Launch if you expected recommendations.");
      }
      lines.push("Mutation guardrail: Reports triage is read-only; CSV rerun/export decisions must stay backend-owned.");
      return lines;
    }

    return {
      auditActionOwner,
      auditDiagnosticsActionsForRow,
      auditEmptyStateMessage,
      auditMatchesChip,
      auditReviewBoardLines,
      auditReviewStatus,
      auditRowKey,
      auditRowSearchText,
    };
  }

  window.__reportsViewAuditModelModule = {
    createReportsAuditModelModule,
  };
})();
