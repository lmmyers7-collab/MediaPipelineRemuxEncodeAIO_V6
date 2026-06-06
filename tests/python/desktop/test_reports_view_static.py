from __future__ import annotations

import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root


REPO_ROOT = find_repo_root(Path(__file__))
REPORTS_VIEW = (
    REPO_ROOT
    / "apps"
    / "desktop"
    / "webview"
    / "static"
    / "assets"
    / "reportsView.js"
)
REPORTS_PAGE = (
    REPO_ROOT
    / "apps"
    / "desktop"
    / "webview"
    / "static"
    / "partials"
    / "page-reports.html"
)


class ReportsViewStaticTests(unittest.TestCase):
    def test_all_marker_clear_lets_backend_enumerate_marker_folder(self) -> None:
        source = REPORTS_VIEW.read_text(encoding="utf-8")

        self.assertIn('return { scope: "all_markers", marker_paths: []', source)
        self.assertIn("all_markers: true", source)
        self.assertIn("if (!request.all_markers) payload.marker_paths = request.marker_paths;", source)
        self.assertIn("all backend failure markers", source)
        self.assertIn("function setFailureMarkerSourceMode(enabled)", source)
        self.assertIn("setFailureMarkerSourceMode(true);", source)

    def test_audit_review_status_is_case_normalized_for_investigation_gate(self) -> None:
        source = REPORTS_VIEW.read_text(encoding="utf-8")

        self.assertIn("const auditStatus = auditReviewStatus();", source)
        self.assertIn('auditStatus.toLowerCase().includes("review")', source)

    def test_reports_guardrail_copy_names_backend_marker_clear_exception(self) -> None:
        source = REPORTS_VIEW.read_text(encoding="utf-8")

        self.assertNotIn("Reports remains read-only", source)
        self.assertIn("Reports triage is read-only", source)
        self.assertIn("Marker Cleanup, which only moves marker JSON through the backend command.", source)
        self.assertIn("Clear this error?", source)

    def test_row_keys_use_locale_invariant_lowercase(self) -> None:
        source = REPORTS_VIEW.read_text(encoding="utf-8")

        self.assertNotIn("toLocaleLowerCase", source)
        self.assertIn('].join("\\u001f").toLowerCase();', source)

    def test_reports_audit_controls_are_backend_owned(self) -> None:
        source = REPORTS_VIEW.read_text(encoding="utf-8")
        html = REPORTS_PAGE.read_text(encoding="utf-8")

        self.assertIn("report-audit-score-policy-status", html)
        self.assertIn("report-audit-score-policy-save-button", html)
        self.assertIn("report-audit-score-policy-reset-button", html)
        self.assertIn("report-audit-ignore-selected-button", html)
        self.assertIn("report-audit-export-rerun-csv-button", html)
        self.assertIn("report-audit-export-detail", html)
        self.assertIn("<th scope=\"col\">Select</th>", html)
        self.assertIn("<summary>Advanced score controls</summary>", html)
        self.assertIn("<th scope=\"col\">Point issue</th>", html)
        self.assertIn("High issue-code marker", html)
        self.assertIn("Medium issue-code marker", html)
        self.assertNotIn("High issue: <code>ffprobe-open-failed</code>", html)
        self.assertNotIn("audio-default-policy-mismatch", html)
        self.assertNotIn('data-audit-score-policy-mirror="high_issue"', html)
        self.assertIn("data-advanced", html)
        self.assertIn('clearRows(tbody, 8, lastAuditRows.length ? "No audit rows match the filter." : lastAuditEmptyMessage)', source)
        self.assertIn("function renderAuditControls", source)
        self.assertIn("let selectedAuditRowKeys = new Set();", source)
        self.assertIn('apiPost("/api/audit/score-policy", request)', source)
        self.assertIn('apiPost("/api/audit/ignore", request)', source)
        self.assertIn('apiPost("/api/audit/export-rerun-csv", request)', source)
        self.assertIn("policy.issue_code_weights = {};", source)
        self.assertIn("data-audit-score-issue-code", source)
        self.assertIn('renderReportAuditIssueRows(score, "high", "rerun_bucket")', source)
        self.assertIn('renderReportAuditIssueRows(score, "medium", "review_bucket")', source)
        self.assertIn("row_keys: selectedAuditRowKeysList()", source)
        self.assertIn("window.mediaPipelineReportsView = {", source)
        self.assertIn("renderAuditControls,", source)

    def test_reports_ia_refresh_surface_is_discoverable_without_new_overview_tab(self) -> None:
        source = REPORTS_VIEW.read_text(encoding="utf-8")
        html = REPORTS_PAGE.read_text(encoding="utf-8")

        self.assertIn("<h2>Report Triage</h2>", html)
        self.assertIn("report-triage-next-action", html)
        self.assertIn("report-triage-action-owner", html)
        self.assertIn("report-triage-report-state", html)
        self.assertIn('data-reports-tab="files" aria-selected="false">Locations</button>', html)
        self.assertNotIn('data-reports-tab="overview"', html)
        self.assertNotIn("report-go-rerun-button", html)
        self.assertNotIn("report-go-audit-button", html)
        self.assertNotIn("report-go-diagnostics-button", html)
        self.assertIn("function renderReportTriageBand", source)
        self.assertIn("reportTriageBandNextAction", source)

    def test_reports_filters_and_row_owner_context_are_static_guarded(self) -> None:
        source = REPORTS_VIEW.read_text(encoding="utf-8")
        html = REPORTS_PAGE.read_text(encoding="utf-8")

        for chip in [
            "needs_operator",
            "will_retry",
            "blocked",
            "publish",
            "queue",
            "subtitle",
            "audio",
            "warnings",
        ]:
            self.assertIn(f'data-failure-filter-chip="{chip}"', html)
        for chip in ["rerun", "redownload", "review", "high", "subtitle", "audio", "duplicates"]:
            self.assertIn(f'data-audit-filter-chip="{chip}"', html)
        self.assertIn("<th scope=\"col\">Evidence</th>", html)
        self.assertIn("<th scope=\"col\">Owner</th>", html)
        self.assertIn('clearRows(tbody, 7, lastFailureRows.length ? "No failure rows match the filter." : lastFailureEmptyMessage)', source)
        self.assertIn("function failureTableEvidenceText", source)
        self.assertIn("function failureActionOwner", source)
        self.assertIn("function auditActionOwner", source)
        self.assertIn("Action owner:", source)

    def test_reports_warnings_and_locations_are_actionable_support_evidence(self) -> None:
        source = REPORTS_VIEW.read_text(encoding="utf-8")
        html = REPORTS_PAGE.read_text(encoding="utf-8")

        self.assertIn("<h2>Actionable Warnings</h2>", html)
        self.assertIn("report-warning-rows", html)
        self.assertIn("<th scope=\"col\">Next Action</th>", html)
        self.assertIn("<h2>Latest Report Paths</h2>", html)
        self.assertIn("<h2>Report Roots</h2>", html)
        self.assertIn("report-open-history-disclosure", html)
        self.assertIn("function collectReportWarnings", source)
        self.assertIn("function renderReportWarnings", source)
        self.assertIn("reportCompactPath(item.path)", source)
        self.assertIn("warningRows.length ? \"Review\" : \"Ready\"", source)


if __name__ == "__main__":
    unittest.main()
