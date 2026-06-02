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
        self.assertIn("Clear Retry Blockers only moves marker JSON through the backend command.", source)


if __name__ == "__main__":
    unittest.main()
