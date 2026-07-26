from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from mediapipeline.tools.dev import remediation_changelog_archive as archive


SAMPLE_LEDGER = b"""# Remediation Changelog

## Navigation

[First entry](#2026-05-02---first-entry)

## 2026-05-02 - First entry

Evidence A.\n
## 2026-05-01 - Second entry (C-002)

Evidence B.\n
"""


class RemediationChangelogArchiveTests(unittest.TestCase):
    @staticmethod
    def _write_sample_ledger(root: Path) -> Path:
        source = root / archive.SOURCE_RELATIVE_PATH
        source.parent.mkdir(parents=True)
        source.write_bytes(SAMPLE_LEDGER)
        (root / "CHANGELOG.md").write_text("# Changelog\n", encoding="utf-8")
        (root / "docs/CURRENT_PROJECT_STATE.md").write_text("# State\n", encoding="utf-8")
        (root / "docs/OPEN_WORK_CHECKLIST.md").write_text("# Work\n", encoding="utf-8")
        return source

    def test_plan_preserves_history_in_contiguous_section_bands(self) -> None:
        plan = archive.build_archive_plan(SAMPLE_LEDGER, segment_size=1)

        self.assertEqual(len(plan.sections), 2)
        self.assertEqual(len(plan.segments), 2)
        self.assertEqual(
            b"".join(segment.preserved_bytes for segment in plan.segments),
            SAMPLE_LEDGER[plan.history_offset :],
        )
        self.assertEqual(plan.segments[0].start_ordinal, 1)
        self.assertEqual(plan.segments[1].end_ordinal, 2)

    def test_written_archive_verifies_links_order_and_preservation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = self._write_sample_ledger(root)

            archive.segment_archive(root, segment_size=1)
            report = archive.verify_archive(root)

            self.assertEqual(report.section_count, 2)
            self.assertEqual(report.segment_count, 2)
            self.assertGreater(report.index_bytes, 0)
            index = source.read_text(encoding="utf-8")
            self.assertIn('<a id="2026-05-02---first-entry"></a>', index)
            self.assertIn("entries-0001-0001.md#2026-05-02---first-entry", index)

    def test_verifier_rejects_dropped_historical_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_sample_ledger(root)
            archive.segment_archive(root, segment_size=1)

            segment_path = root / archive.ARCHIVE_RELATIVE_DIR / "entries-0001-0001.md"
            segment_path.write_bytes(segment_path.read_bytes().replace(b"Evidence A.", b""))

            with self.assertRaisesRegex(archive.ArchiveVerificationError, "byte count|hash"):
                archive.verify_archive(root)


if __name__ == "__main__":
    unittest.main()
