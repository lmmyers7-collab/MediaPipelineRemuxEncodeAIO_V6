from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from mediapipeline.tools.dev.release_package_scope import (
    is_release_excluded_path,
    release_excluded_prefixes,
)


class ReleasePackageScopeTests(unittest.TestCase):
    def _write_manifest(self, root: Path, *, tests_included) -> None:
        manifest = {"summary": {"tests_included": tests_included}}
        (root / "release_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    def test_no_manifest_returns_no_prefixes(self) -> None:
        # A normal source tree has no root manifest, so behavior is unchanged.
        with TemporaryDirectory() as tmp:
            self.assertEqual(release_excluded_prefixes(Path(tmp)), ())

    def test_tests_excluded_returns_test_roots(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_manifest(root, tests_included=False)
            self.assertEqual(
                release_excluded_prefixes(root),
                ("tests/", "ops/pipeline/tests/"),
            )

    def test_tests_included_returns_no_prefixes(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_manifest(root, tests_included=True)
            self.assertEqual(release_excluded_prefixes(root), ())

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
        # A non-test source under ops/pipeline must NOT be treated as excluded.
        self.assertFalse(is_release_excluded_path("ops/pipeline/engine/process/dynamic_hdr.ps1", prefixes))
        self.assertFalse(is_release_excluded_path("src/mediapipeline/core/metrics/facade.py", prefixes))

    def test_is_release_excluded_path_empty_prefixes_never_matches(self) -> None:
        self.assertFalse(is_release_excluded_path("tests/python/desktop/test_x.py", ()))


if __name__ == "__main__":
    unittest.main()
