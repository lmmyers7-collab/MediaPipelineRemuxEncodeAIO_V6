from __future__ import annotations

import sys
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root


REPO_ROOT = find_repo_root(Path(__file__))
sys.path.insert(0, str(REPO_ROOT / "src" / "mediapipeline" / "tools" / "dev"))

import check_active_doc_references as docs_check  # noqa: E402


class ActiveDocReferenceTests(unittest.TestCase):
    def test_stale_moved_doc_reference_is_flagged(self) -> None:
        findings = docs_check.findings_for_text(
            "See docs/API_ROUTE_INVENTORY.md for old path.",
            "docs/CURRENT_PROJECT_STATE.md",
        )

        self.assertEqual([finding.rule_id for finding in findings], ["DOC001"])

    def test_archived_docs_are_not_collected_as_active_docs(self) -> None:
        self.assertTrue(docs_check._is_archive_path("docs/archive/old.md"))
        self.assertFalse(docs_check._is_archive_path("docs/audits/latest.md"))

    def test_removed_shell_terms_and_absolute_handoff_paths_are_flagged(self) -> None:
        findings = docs_check.findings_for_text(
            "Tk fallback path C:\\Users\\lmmye\\Downloads\\CurrentHandoff",
            "docs/CURRENT_PROJECT_STATE.md",
        )

        self.assertEqual({finding.rule_id for finding in findings}, {"DOC003", "DOC004"})

    def test_known_active_text_has_no_findings(self) -> None:
        findings = docs_check.findings_for_text(
            "Use docs/inventories/API_ROUTE_INVENTORY.md and the Tauri/WebView2 shell.",
            "docs/CURRENT_PROJECT_STATE.md",
        )

        self.assertEqual(findings, [])

    def test_active_version_line_labels_are_flagged(self) -> None:
        findings = docs_check.findings_for_text(
            "MediaPipelineRemuxEncodeAIO " + "V" + "6 with " + "V" + "5 fallback and " + "v" + "6.000 health.",
            "docs/CURRENT_PROJECT_STATE.md",
        )

        self.assertIn("DOC005", {finding.rule_id for finding in findings})

    def test_active_removed_quick_start_references_are_flagged(self) -> None:
        removed_name = "T" + "LDR"
        findings = docs_check.findings_for_text(
            f"See docs/{removed_name}.md and {removed_name}.md for removed quick-start content.",
            "docs/DOCS_INDEX.md",
        )

        self.assertEqual([finding.rule_id for finding in findings], ["DOC006"])

    def test_historical_removed_quick_start_references_are_allowed(self) -> None:
        removed_name = "T" + "LDR"
        for rel in (
            "docs/archive/old.md",
            "docs/REMEDIATION_CHANGELOG.md",
            "docs/change_control/CHANGELOG.md",
        ):
            findings = docs_check.findings_for_text(f"Historical reference to docs/{removed_name}.md.", rel)
            self.assertEqual(findings, [])

    def test_historical_change_logs_can_keep_version_line_labels(self) -> None:
        findings = docs_check.findings_for_text(
            "Historical " + "V" + "6.0.0 release notes.",
            "docs/change_control/CHANGELOG.md",
        )

        self.assertEqual(findings, [])

    def test_required_active_docs_are_checked(self) -> None:
        missing = docs_check.missing_required_active_docs(
            REPO_ROOT,
            required_docs=["README.md", "definitely_missing_required_doc.md"],
        )

        self.assertEqual(missing, ["definitely_missing_required_doc.md"])


if __name__ == "__main__":
    unittest.main()
