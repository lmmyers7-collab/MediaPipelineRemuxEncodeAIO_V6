from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from mediapipeline.tools.dev import generate_duplicate_test_name_report
from mediapipeline.tools.paths import find_repo_root


REPO_ROOT = find_repo_root(Path(__file__))


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


class DuplicateTestNameReportTests(unittest.TestCase):
    def test_duplicate_names_are_grouped_across_files_with_qualnames(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write(
                root / "tests/python/desktop/test_alpha.py",
                """
class AlphaTests:
    def test_shared_name(self):
        pass

    def test_unique_alpha(self):
        pass
""".lstrip(),
            )
            _write(
                root / "tests/webview/test_beta.py",
                """
def test_shared_name():
    pass

def test_unique_beta():
    pass
""".lstrip(),
            )

            definitions = generate_duplicate_test_name_report.collect_test_definitions(root)
            groups = generate_duplicate_test_name_report.duplicate_groups(definitions)
            rendered = generate_duplicate_test_name_report.render_duplicate_test_name_report(root)

        self.assertEqual(sorted(groups), ["test_shared_name"])
        entries = groups["test_shared_name"]
        self.assertEqual({entry.path for entry in entries}, {"tests/python/desktop/test_alpha.py", "tests/webview/test_beta.py"})
        self.assertIn("AlphaTests.test_shared_name", {entry.qualname for entry in entries})
        self.assertIn("### `test_shared_name`", rendered)

    def test_same_file_repeated_name_is_not_cross_file_overlap(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write(
                root / "tests/python/desktop/test_alpha.py",
                """
class AlphaTests:
    def test_same_file_only(self):
        pass

class BetaTests:
    def test_same_file_only(self):
        pass
""".lstrip(),
            )

            definitions = generate_duplicate_test_name_report.collect_test_definitions(root)
            groups = generate_duplicate_test_name_report.duplicate_groups(definitions)

        self.assertEqual(groups, {})

    @unittest.skipIf(
        (REPO_ROOT / "release_manifest.json").is_file(),
        "The committed report describes the full source-checkout test tree, not the package test subset.",
    )
    def test_current_generated_report_is_current(self) -> None:
        expected = generate_duplicate_test_name_report.render_duplicate_test_name_report(REPO_ROOT)
        actual = generate_duplicate_test_name_report.OUTPUT_PATH.read_text(encoding="utf-8")

        self.assertEqual(actual, expected)
        self.assertIn("test_success_message_and_payload_are_stable", actual)


if __name__ == "__main__":
    unittest.main()
