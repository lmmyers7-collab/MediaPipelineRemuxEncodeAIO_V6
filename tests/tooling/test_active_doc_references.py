from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "dev"))

import check_active_doc_references as docs_check  # noqa: E402


class ActiveDocReferenceTests(unittest.TestCase):
    def test_stale_moved_doc_reference_is_flagged(self) -> None:
        findings = docs_check.findings_for_text(
            "See Docs/API_ROUTE_INVENTORY.md for old path.",
            "Docs/CURRENT_PROJECT_STATE.md",
        )

        self.assertEqual([finding.rule_id for finding in findings], ["DOC001"])

    def test_archived_docs_are_not_collected_as_active_docs(self) -> None:
        self.assertTrue(docs_check._is_archive_path("Docs/archive/old.md"))
        self.assertFalse(docs_check._is_archive_path("Docs/audits/latest.md"))

    def test_removed_shell_terms_and_absolute_handoff_paths_are_flagged(self) -> None:
        findings = docs_check.findings_for_text(
            "Tk fallback path C:\\Users\\lmmye\\Downloads\\CurrentHandoff",
            "Docs/CURRENT_PROJECT_STATE.md",
        )

        self.assertEqual({finding.rule_id for finding in findings}, {"DOC003", "DOC004"})

    def test_known_active_text_has_no_findings(self) -> None:
        findings = docs_check.findings_for_text(
            "Use Docs/inventories/API_ROUTE_INVENTORY.md and the Tauri/WebView2 shell.",
            "Docs/CURRENT_PROJECT_STATE.md",
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
