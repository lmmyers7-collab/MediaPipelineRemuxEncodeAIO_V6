from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from mediapipeline.tools.dev import scan_archive_doc_candidates as scanner


def _write(root: Path, relative: str, text: str = "") -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _result_by_path(results: list[scanner.DocumentScanResult], path: str) -> scanner.DocumentScanResult:
    for result in results:
        if result.path == path:
            return result
    raise AssertionError(f"missing result for {path}")


class ArchiveDocCandidateScanTests(unittest.TestCase):
    def test_architecture_references_are_reported_before_archive(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write(
                root,
                "docs/architecture/ARCHITECTURE.md",
                "Historical review: `../reviews/network-2026-06-01/08-final-review-summary.md`.",
            )
            _write(
                root,
                "docs/reviews/network-2026-06-01/08-final-review-summary.md",
                "# Final Review Summary\n\nClosed and completed.",
            )

            result = _result_by_path(
                scanner.scan_documents(root, as_of="2026-06-16"),
                "docs/reviews/network-2026-06-01/08-final-review-summary.md",
            )

        self.assertEqual(result.status, "archive-candidate")
        self.assertTrue(result.architecture_update_required)
        self.assertEqual(result.update_required_paths, ("docs/architecture/ARCHITECTURE.md",))
        self.assertEqual(result.confidence, "low")

    def test_required_active_docs_are_kept_even_when_they_contain_archive_language(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write(root, "docs/CURRENT_PROJECT_STATE.md", "Completed historical context.")

            result = _result_by_path(
                scanner.scan_documents(root, as_of="2026-06-16"),
                "docs/CURRENT_PROJECT_STATE.md",
            )

        self.assertEqual(result.status, "keep-active")
        self.assertIn("required active", result.reasons[0])

    def test_archive_and_generated_summary_trees_are_not_candidate_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write(root, "docs/archive/old.md", "Completed.")
            _write(root, "docs/generated/summaries/docs/DOCS_INDEX.md.md", "Generated.")
            _write(root, "LocalBase/Scratch/transient.md", "Runtime scratch.")
            _write(root, "docs/reviews/closed-2026-06-01/09-implementation-ledger.md", "Closed.")

            paths = {result.path for result in scanner.scan_documents(root, as_of="2026-06-16")}

        self.assertNotIn("docs/archive/old.md", paths)
        self.assertNotIn("docs/generated/summaries/docs/DOCS_INDEX.md.md", paths)
        self.assertNotIn("LocalBase/Scratch/transient.md", paths)
        self.assertIn("docs/reviews/closed-2026-06-01/09-implementation-ledger.md", paths)

    def test_markdown_output_lists_candidate_destinations_and_update_sources(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write(
                root,
                "docs/DOCS_INDEX.md",
                "Review packet: `reviews/source-2026-06-01/09-implementation-ledger.md`.",
            )
            _write(
                root,
                "docs/reviews/source-2026-06-01/09-implementation-ledger.md",
                "# Implementation Ledger\n\nCompleted.",
            )
            results = scanner.scan_documents(root, as_of="2026-06-16")

            markdown = scanner.render_markdown(
                results,
                root=root,
                statuses={"archive-candidate"},
            )

        self.assertIn("docs/reviews/source-2026-06-01/09-implementation-ledger.md", markdown)
        self.assertIn("docs/archive/docs-housekeeping/2026-06-16-active-doc-archive-scan/reviews/source-2026-06-01/09-implementation-ledger.md", markdown)
        self.assertIn("docs/DOCS_INDEX.md", markdown)


if __name__ == "__main__":
    unittest.main()
