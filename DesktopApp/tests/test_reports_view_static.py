from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
REPORTS_VIEW = (
    REPO_ROOT
    / "DesktopApp"
    / "mediapipeline_desktop_app"
    / "ui_web"
    / "static"
    / "assets"
    / "reportsView.js"
)
REPORTS_PAGE = (
    REPO_ROOT
    / "DesktopApp"
    / "mediapipeline_desktop_app"
    / "ui_web"
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

    def test_audit_review_status_is_case_normalized_for_investigation_gate(self) -> None:
        source = REPORTS_VIEW.read_text(encoding="utf-8")

        self.assertIn("const auditStatus = auditReviewStatus();", source)
        self.assertIn('auditStatus.toLowerCase().includes("review")', source)

    def test_reports_guardrail_copy_names_backend_marker_clear_exception(self) -> None:
        source = REPORTS_VIEW.read_text(encoding="utf-8")

        self.assertNotIn("Reports remains read-only", source)
        self.assertIn("Reports triage is read-only", source)
        self.assertIn("Clear Errors, which only moves marker JSON through the backend command.", source)
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
        self.assertIn('clearRows(tbody, 7, lastAuditRows.length ? "No audit rows match the filter." : lastAuditEmptyMessage)', source)
        self.assertIn("function renderAuditControls", source)
        self.assertIn("let selectedAuditRowKeys = new Set();", source)
        self.assertIn('apiPost("/api/audit/score-policy", request)', source)
        self.assertIn('apiPost("/api/audit/ignore", request)', source)
        self.assertIn('apiPost("/api/audit/export-rerun-csv", request)', source)
        self.assertIn("row_keys: selectedAuditRowKeysList()", source)
        self.assertIn("window.mediaPipelineReportsView = {", source)
        self.assertIn("renderAuditControls,", source)


if __name__ == "__main__":
    unittest.main()
