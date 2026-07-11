from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from mediapipeline.tools.dev.release_package_scope import (
    is_release_excluded_path,
    release_package_omits_path,
    release_excluded_prefixes,
)


class ReleasePackageScopeTests(unittest.TestCase):
    def _write_manifest(
        self,
        root: Path,
        *,
        tests_included=True,
        dev_docs_included=True,
        optional_tools_included=True,
        tool_docs_included=True,
    ) -> None:
        manifest = {
            "summary": {
                "tests_included": tests_included,
                "dev_docs_included": dev_docs_included,
                "optional_tools_included": optional_tools_included,
                "tool_docs_included": tool_docs_included,
            }
        }
        (root / "release_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    def test_no_manifest_returns_no_prefixes(self) -> None:
        # A normal source tree has no root manifest, so behavior is unchanged.
        with TemporaryDirectory() as tmp:
            self.assertEqual(release_excluded_prefixes(Path(tmp)), ())

    def test_tests_excluded_returns_test_roots(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_manifest(root, tests_included=False)
            prefixes = release_excluded_prefixes(root)
            self.assertIn("tests/", prefixes)
            self.assertIn("ops/pipeline/tests/", prefixes)

    def test_manifest_returns_always_omitted_package_roots(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_manifest(root, tests_included=True)
            prefixes = release_excluded_prefixes(root)
            self.assertIn("docs/PG3CleanMachineReports/", prefixes)
            self.assertIn("docs/reviews/", prefixes)
            self.assertNotIn("tests/", prefixes)

    def test_manifest_flags_return_optional_package_omissions(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_manifest(
                root,
                tests_included=False,
                dev_docs_included=False,
                optional_tools_included=False,
                tool_docs_included=False,
            )
            prefixes = release_excluded_prefixes(root)
            for expected in (
                "tests/",
                "ops/pipeline/tests/",
                "docs/archive/docs-housekeeping/",
                "ops/pipeline/tools/ffmpeg/bin/ffplay.exe",
                "ops/pipeline/tools/MKVToolNix/tools/",
                "ops/pipeline/tools/MKVToolNix/doc/",
                "ops/pipeline/tools/MKVToolNix/examples/",
            ):
                self.assertIn(expected, prefixes)
            self.assertNotIn("docs/RealMediaValidationRuns/", prefixes)

    def test_malformed_manifest_returns_no_prefixes(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "release_manifest.json").write_text("{ not json", encoding="utf-8")
            self.assertEqual(release_excluded_prefixes(root), ())

    def test_is_release_excluded_path_matches_only_listed_roots(self) -> None:
        prefixes = ("tests/", "ops/pipeline/tests/")
        self.assertTrue(is_release_excluded_path("tests/python/desktop/test_x.py", prefixes))
        self.assertTrue(is_release_excluded_path("ops/pipeline/tests/Unit/Invoke-X.ps1", prefixes))
        self.assertTrue(is_release_excluded_path("ops\\pipeline\\tests\\Unit\\Invoke-X.ps1", prefixes))
        self.assertTrue(
            is_release_excluded_path(
                "ops/pipeline/tools/ffmpeg/bin/ffplay.exe",
                ("ops/pipeline/tools/ffmpeg/bin/ffplay.exe",),
            )
        )
        # A non-test source under ops/pipeline must NOT be treated as excluded.
        self.assertFalse(is_release_excluded_path("ops/pipeline/engine/process/dynamic_hdr.ps1", prefixes))
        self.assertFalse(is_release_excluded_path("src/mediapipeline/core/metrics/facade.py", prefixes))

    def test_is_release_excluded_path_empty_prefixes_never_matches(self) -> None:
        self.assertFalse(is_release_excluded_path("tests/python/desktop/test_x.py", ()))

    def test_release_package_omits_path_requires_valid_manifest_and_missing_excluded_path(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertFalse(release_package_omits_path(root, ".github/workflows"))

            (root / "release_manifest.json").write_text(
                json.dumps({"schema_version": "not-a-release-package", "summary": {}}),
                encoding="utf-8",
            )
            self.assertFalse(release_package_omits_path(root, ".github/workflows"))

            (root / "release_manifest.json").write_text(
                json.dumps({"schema_version": "mediapipeline_release_manifest.v1", "summary": {}}),
                encoding="utf-8",
            )
            self.assertTrue(release_package_omits_path(root, ".github/workflows"))
            self.assertFalse(release_package_omits_path(root, "src/mediapipeline"))

            (root / ".github" / "workflows").mkdir(parents=True)
            self.assertFalse(release_package_omits_path(root, ".github/workflows"))


if __name__ == "__main__":
    unittest.main()
