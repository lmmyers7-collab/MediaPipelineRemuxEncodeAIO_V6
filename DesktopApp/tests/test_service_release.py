from __future__ import annotations

import tempfile
import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.paths.layout import first_existing
from app.maintenance.release import ReleasePackageServiceMixin


class DummyReleaseService(ReleasePackageServiceMixin):
    def __init__(self, root: Path) -> None:
        self.workspace_root = root
        self.app_root = root / "DesktopApp"

    def _first_existing(self, *paths: Path) -> Path:
        return first_existing(*paths)


class ReleasePackageServiceTests(unittest.TestCase):
    def test_default_release_builder_prefers_workspace_scripts_path(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            canonical = root / "scripts" / "release" / "build.ps1"
            canonical.parent.mkdir(parents=True)
            canonical.write_text("# canonical", encoding="utf-8")

            service = DummyReleaseService(root)

            self.assertEqual(service.default_release_builder_path(), canonical)

    def test_default_release_builder_uses_app_root_scripts_path_when_workspace_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            canonical = root / "DesktopApp" / "scripts" / "release" / "build.ps1"
            canonical.parent.mkdir(parents=True)
            canonical.write_text("# canonical", encoding="utf-8")

            service = DummyReleaseService(root)

            self.assertEqual(service.default_release_builder_path(), canonical)


if __name__ == "__main__":
    unittest.main()
