from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
CHANGE_CONTROL_DIR = REPO_ROOT / "scripts" / "change_control"
if str(CHANGE_CONTROL_DIR) not in sys.path:
    sys.path.insert(0, str(CHANGE_CONTROL_DIR))


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


build_release_manifest = _load_module(
    "change_control_build_release_manifest_for_tests",
    CHANGE_CONTROL_DIR / "build_release_manifest.py",
)


def _packet(change_id: str, version_target: str) -> dict[str, Any]:
    return {
        "id": change_id,
        "title": "Test change",
        "version_target": version_target,
        "status": "complete",
        "type": "tooling",
        "risk_level": "low",
        "date_started": "2026-06-02",
        "date_completed": "2026-06-02",
        "summary": "Test summary.",
        "reason": "Test reason.",
        "affected_areas": ["change_control"],
        "behavior_before": "Before.",
        "behavior_after": "After.",
        "files_touched": ["scripts/change_control/build_release_manifest.py"],
        "tests_added": ["tests/tooling/test_change_control.py"],
        "manual_validation": ["unit test"],
        "rollback_plan": "Revert the test change.",
        "related_changes": [],
        "notes": "",
    }


class ChangeControlToolingTests(unittest.TestCase):
    def test_manifest_can_preview_dev_placeholder_packets_for_target_version(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            unreleased = root / "changes" / "unreleased"
            released = root / "changes" / "released"
            version_file = root / "release" / "VERSION"
            manifest_path = root / "release" / "RELEASE_MANIFEST.json"
            unreleased.mkdir(parents=True)
            version_file.parent.mkdir(parents=True)
            version_file.write_text("0.1.0-dev\n", encoding="utf-8")
            packet_path = unreleased / "MP-CHANGE-2026-0602-001.json"
            packet_path.write_text(
                json.dumps(_packet(packet_path.stem, "0.1.0-dev"), indent=2) + "\n",
                encoding="utf-8",
            )

            old_values = (
                build_release_manifest.REPO_ROOT,
                build_release_manifest.UNRELEASED_DIR,
                build_release_manifest.RELEASED_DIR,
                build_release_manifest.VERSION_FILE,
                build_release_manifest.DEFAULT_MANIFEST_PATH,
            )
            try:
                build_release_manifest.REPO_ROOT = root
                build_release_manifest.UNRELEASED_DIR = unreleased
                build_release_manifest.RELEASED_DIR = released
                build_release_manifest.VERSION_FILE = version_file
                build_release_manifest.DEFAULT_MANIFEST_PATH = manifest_path

                without_placeholder = build_release_manifest.build_manifest(
                    version="1.0.0",
                    output_path=manifest_path,
                )
                with_placeholder = build_release_manifest.build_manifest(
                    version="1.0.0",
                    output_path=manifest_path,
                    include_dev_placeholders=True,
                )
            finally:
                (
                    build_release_manifest.REPO_ROOT,
                    build_release_manifest.UNRELEASED_DIR,
                    build_release_manifest.RELEASED_DIR,
                    build_release_manifest.VERSION_FILE,
                    build_release_manifest.DEFAULT_MANIFEST_PATH,
                ) = old_values

        self.assertEqual(without_placeholder["included_changes"], [])
        self.assertEqual(with_placeholder["included_changes"], [packet_path.stem])
        self.assertEqual(with_placeholder["change_source"], "unreleased")

    def test_release_version_rejects_path_like_values(self) -> None:
        for value in ["../outside", "1.0.0/evil", "1.0.0 evil", "C:bad"]:
            with self.subTest(value=value):
                with self.assertRaises(SystemExit):
                    build_release_manifest.validate_version_label(value)

    def test_missing_version_file_has_actionable_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            old_values = (
                build_release_manifest.REPO_ROOT,
                build_release_manifest.UNRELEASED_DIR,
                build_release_manifest.RELEASED_DIR,
                build_release_manifest.VERSION_FILE,
            )
            try:
                build_release_manifest.REPO_ROOT = root
                build_release_manifest.UNRELEASED_DIR = root / "changes" / "unreleased"
                build_release_manifest.RELEASED_DIR = root / "changes" / "released"
                build_release_manifest.VERSION_FILE = root / "release" / "VERSION"

                with self.assertRaisesRegex(SystemExit, "release/VERSION is missing"):
                    build_release_manifest.build_manifest()
            finally:
                (
                    build_release_manifest.REPO_ROOT,
                    build_release_manifest.UNRELEASED_DIR,
                    build_release_manifest.RELEASED_DIR,
                    build_release_manifest.VERSION_FILE,
                ) = old_values


if __name__ == "__main__":
    unittest.main()
