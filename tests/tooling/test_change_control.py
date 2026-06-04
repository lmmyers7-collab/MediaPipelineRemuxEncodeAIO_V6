from __future__ import annotations

import importlib.util
import contextlib
import io
import json
import shutil
import subprocess
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
packet_coverage = _load_module(
    "change_control_packet_coverage_for_tests",
    CHANGE_CONTROL_DIR / "packet_coverage.py",
)
validate_changes = _load_module(
    "change_control_validate_changes_for_tests",
    CHANGE_CONTROL_DIR / "validate_changes.py",
)
record_change_touch = _load_module(
    "change_control_record_change_touch_for_tests",
    CHANGE_CONTROL_DIR / "record_change_touch.py",
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


def _write_packet(root: Path, relative: str, packet: dict[str, Any]) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(packet, indent=2) + "\n", encoding="utf-8")
    return path


def _run_git(root: Path, *args: str) -> str:
    if not shutil.which("git"):
        raise unittest.SkipTest("git is required for staged/diff change-control coverage tests.")
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(result.stderr.strip() or result.stdout.strip() or f"git {' '.join(args)} failed")
    return result.stdout


def _init_git(root: Path) -> None:
    _run_git(root, "init")
    _run_git(root, "config", "user.email", "change-control-tests@example.invalid")
    _run_git(root, "config", "user.name", "Change Control Tests")


class _PatchedChangeControl:
    def __init__(self, module: Any, root: Path) -> None:
        self.module = module
        self.root = root
        self.old_values: dict[str, Any] = {}

    def __enter__(self) -> None:
        self.old_values = {
            "REPO_ROOT": self.module.REPO_ROOT,
            "UNRELEASED_DIR": self.module.UNRELEASED_DIR,
        }
        self.module.REPO_ROOT = self.root
        self.module.UNRELEASED_DIR = self.root / "changes" / "unreleased"
        if hasattr(self.module, "RELEASED_DIR"):
            self.old_values["RELEASED_DIR"] = self.module.RELEASED_DIR
            self.module.RELEASED_DIR = self.root / "changes" / "released"
        if hasattr(self.module, "VERSION_FILE"):
            self.old_values["VERSION_FILE"] = self.module.VERSION_FILE
            self.module.VERSION_FILE = self.root / "release" / "VERSION"
        if hasattr(self.module, "RELEASE_HISTORY_DIR"):
            self.old_values["RELEASE_HISTORY_DIR"] = self.module.RELEASE_HISTORY_DIR
            self.module.RELEASE_HISTORY_DIR = self.root / "release" / "history"

    def __exit__(self, *_exc: object) -> None:
        for name, value in self.old_values.items():
            setattr(self.module, name, value)


class ChangePacketCoverageTests(unittest.TestCase):
    def test_worktree_paths_covered_by_unreleased_packet_pass(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            packet = _packet("MP-CHANGE-2026-0604-001", "0.1.0-dev")
            packet["files_touched"] = ["app/maintenance/change_ledger.py"]
            _write_packet(root, "changes/unreleased/MP-CHANGE-2026-0604-001.json", packet)

            result = packet_coverage.coverage_for_paths(
                root=root,
                scope="test",
                changed_files=["app\\maintenance\\change_ledger.py"],
            )

        self.assertEqual(result.covered_files, ("app/maintenance/change_ledger.py",))
        self.assertEqual(result.uncovered_files, ())

    def test_missing_changed_file_reports_exact_uncovered_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            packet = _packet("MP-CHANGE-2026-0604-001", "0.1.0-dev")
            packet["files_touched"] = ["README.md"]
            _write_packet(root, "changes/unreleased/MP-CHANGE-2026-0604-001.json", packet)

            result = packet_coverage.coverage_for_paths(
                root=root,
                scope="test",
                changed_files=["scripts/change_control/validate_changes.py"],
            )

        self.assertEqual(result.uncovered_files, ("scripts/change_control/validate_changes.py",))

    def test_released_packets_do_not_satisfy_current_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            released_packet = _packet("MP-CHANGE-2026-0601-001", "1.0.0")
            released_packet["files_touched"] = ["app/released.py"]
            _write_packet(root, "changes/released/1.0.0/MP-CHANGE-2026-0601-001.json", released_packet)

            result = packet_coverage.coverage_for_paths(
                root=root,
                scope="test",
                changed_files=["app/released.py"],
            )

        self.assertEqual(result.covered_files, ())
        self.assertEqual(result.uncovered_files, ("app/released.py",))

    def test_status_parser_includes_untracked_deleted_and_renamed_paths(self) -> None:
        parsed = packet_coverage.parse_git_status_short(
            "?? scratch/new.py\n"
            " D old/deleted.py\n"
            "R  old/name.py -> new/name.py\n"
        )

        self.assertEqual(parsed, ["new/name.py", "old/deleted.py", "scratch/new.py"])

    def test_name_status_parser_normalizes_deleted_and_renamed_paths(self) -> None:
        parsed = packet_coverage.parse_git_name_status(
            "D\told/deleted.py\n"
            "R100\told/name.py\tnew/name.py\n"
        )

        self.assertEqual(parsed, ["new/name.py", "old/deleted.py"])

    def test_staged_mode_reads_staged_packet_json_not_unstaged_edits(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _init_git(root)
            packet = _packet("MP-CHANGE-2026-0604-001", "0.1.0-dev")
            packet["files_touched"] = ["changes/unreleased/MP-CHANGE-2026-0604-001.json"]
            packet_path = _write_packet(root, "changes/unreleased/MP-CHANGE-2026-0604-001.json", packet)
            _run_git(root, "add", "changes/unreleased/MP-CHANGE-2026-0604-001.json")
            staged_file = root / "app" / "maintenance" / "change_ledger.py"
            staged_file.parent.mkdir(parents=True)
            staged_file.write_text("print('ledger')\n", encoding="utf-8")
            _run_git(root, "add", "app/maintenance/change_ledger.py")

            packet["files_touched"].append("app/maintenance/change_ledger.py")
            packet_path.write_text(json.dumps(packet, indent=2) + "\n", encoding="utf-8")

            result = packet_coverage.coverage_for_staged(root)

        self.assertIn("app/maintenance/change_ledger.py", result.uncovered_files)

    def test_diff_mode_checks_files_changed_since_base_ref(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _init_git(root)
            (root / "release").mkdir()
            (root / "release" / "VERSION").write_text("0.1.0-dev\n", encoding="utf-8")
            _write_packet(root, "changes/unreleased/MP-CHANGE-2026-0604-001.json", _packet("MP-CHANGE-2026-0604-001", "0.1.0-dev"))
            _run_git(root, "add", ".")
            _run_git(root, "commit", "-m", "baseline")

            packet = _packet("MP-CHANGE-2026-0604-002", "0.1.0-dev")
            packet["files_touched"] = [
                "app/maintenance/change_ledger.py",
                "changes/unreleased/MP-CHANGE-2026-0604-002.json",
            ]
            _write_packet(root, "changes/unreleased/MP-CHANGE-2026-0604-002.json", packet)
            changed = root / "app" / "maintenance" / "change_ledger.py"
            changed.parent.mkdir(parents=True, exist_ok=True)
            changed.write_text("print('ledger')\n", encoding="utf-8")
            _run_git(root, "add", ".")
            _run_git(root, "commit", "-m", "covered change")

            result = packet_coverage.coverage_for_diff(root, "HEAD~1")

        self.assertEqual(result.uncovered_files, ())
        self.assertIn("app/maintenance/change_ledger.py", result.covered_files)


class ValidateChangesCoverageTests(unittest.TestCase):
    def test_default_validation_does_not_require_worktree_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "release").mkdir()
            (root / "release" / "VERSION").write_text("0.1.0-dev\n", encoding="utf-8")
            _write_packet(root, "changes/unreleased/MP-CHANGE-2026-0604-001.json", _packet("MP-CHANGE-2026-0604-001", "0.1.0-dev"))

            with _PatchedChangeControl(validate_changes, root):
                result = validate_changes.main([])

        self.assertEqual(result, 0)

    def test_worktree_strict_coverage_failure_includes_path_and_helper_hint(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _init_git(root)
            (root / "release").mkdir()
            (root / "release" / "VERSION").write_text("0.1.0-dev\n", encoding="utf-8")
            packet = _packet("MP-CHANGE-2026-0604-001", "0.1.0-dev")
            packet["files_touched"] = ["changes/unreleased/MP-CHANGE-2026-0604-001.json"]
            _write_packet(root, "changes/unreleased/MP-CHANGE-2026-0604-001.json", packet)
            missing = root / "scripts" / "change_control" / "validate_changes.py"
            missing.parent.mkdir(parents=True)
            missing.write_text("# changed\n", encoding="utf-8")

            stderr = io.StringIO()
            with _PatchedChangeControl(validate_changes, root), contextlib.redirect_stderr(stderr):
                result = validate_changes.main(["--require-worktree-coverage"])

        self.assertEqual(result, 1)
        output = stderr.getvalue()
        self.assertIn("scripts/change_control/validate_changes.py", output)
        self.assertIn("record_change_touch.py MP-CHANGE-YYYY-MMDD-### <path>", output)

    def test_git_unavailable_strict_mode_fails_actionably(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "release").mkdir()
            (root / "release" / "VERSION").write_text("0.1.0-dev\n", encoding="utf-8")
            _write_packet(root, "changes/unreleased/MP-CHANGE-2026-0604-001.json", _packet("MP-CHANGE-2026-0604-001", "0.1.0-dev"))

            stderr = io.StringIO()
            with _PatchedChangeControl(validate_changes, root), contextlib.redirect_stderr(stderr):
                result = validate_changes.main(["--require-worktree-coverage"])

        self.assertEqual(result, 1)
        self.assertIn("Git metadata is unavailable", stderr.getvalue())
        self.assertIn("Run strict coverage from a Git checkout", stderr.getvalue())


class RecordChangeTouchTests(unittest.TestCase):
    def test_helper_adds_paths_evidence_notes_and_completion(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            change_id = "MP-CHANGE-2026-0604-001"
            _write_packet(root, f"changes/unreleased/{change_id}.json", _packet(change_id, "0.1.0-dev"))

            with _PatchedChangeControl(record_change_touch, root):
                result = record_change_touch.main(
                    [
                        change_id,
                        "app\\maintenance\\change_ledger.py",
                        "--area",
                        "maintenance",
                        "--test",
                        "DesktopApp/tests/test_maintenance_change_ledger.py",
                        "--validation",
                        "unit tests - passed",
                        "--note",
                        "Python impact captured in files_touched.",
                        "--complete",
                    ]
                )

            packet = json.loads((root / f"changes/unreleased/{change_id}.json").read_text(encoding="utf-8"))

        self.assertEqual(result, 0)
        self.assertEqual(packet["status"], "complete")
        self.assertRegex(packet["date_completed"], r"^\d{4}-\d{2}-\d{2}$")
        self.assertIn("app/maintenance/change_ledger.py", packet["files_touched"])
        self.assertIn(f"changes/unreleased/{change_id}.json", packet["files_touched"])
        self.assertIn("maintenance", packet["affected_areas"])
        self.assertIn("DesktopApp/tests/test_maintenance_change_ledger.py", packet["tests_added"])
        self.assertIn("unit tests - passed", packet["manual_validation"])
        self.assertIn("Python impact captured", packet["notes"])

    def test_helper_rejects_invalid_change_id_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            change_id = "MP-CHANGE-2026-0604-001"
            packet_path = _write_packet(root, f"changes/unreleased/{change_id}.json", _packet(change_id, "0.1.0-dev"))
            before = packet_path.read_text(encoding="utf-8")

            with _PatchedChangeControl(record_change_touch, root):
                with self.assertRaises(SystemExit):
                    record_change_touch.main(["bad-id", "README.md"])

            after = packet_path.read_text(encoding="utf-8")

        self.assertEqual(after, before)

    def test_helper_from_staged_adds_only_staged_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _init_git(root)
            change_id = "MP-CHANGE-2026-0604-001"
            _write_packet(root, f"changes/unreleased/{change_id}.json", _packet(change_id, "0.1.0-dev"))
            staged = root / "staged.py"
            unstaged = root / "unstaged.py"
            staged.write_text("print('staged')\n", encoding="utf-8")
            unstaged.write_text("print('unstaged')\n", encoding="utf-8")
            _run_git(root, "add", "staged.py")

            with _PatchedChangeControl(record_change_touch, root):
                record_change_touch.main([change_id, "--from-staged"])

            packet = json.loads((root / f"changes/unreleased/{change_id}.json").read_text(encoding="utf-8"))

        self.assertIn("staged.py", packet["files_touched"])
        self.assertNotIn("unstaged.py", packet["files_touched"])


class ChangeControlWorkflowStaticTests(unittest.TestCase):
    def test_pre_commit_includes_staged_change_packet_coverage_hook(self) -> None:
        text = (REPO_ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8")

        self.assertIn("mediapipeline-change-packet-staged-coverage", text)
        self.assertIn("validate_changes.py --require-staged-coverage", text)

    def test_github_workflow_includes_pr_diff_change_packet_coverage(self) -> None:
        text = (REPO_ROOT / ".github" / "workflows" / "phase1-drift.yml").read_text(encoding="utf-8")

        self.assertIn("Check change packet coverage", text)
        self.assertIn('validate_changes.py --require-diff-coverage "origin/${{ github.base_ref }}"', text)
        self.assertIn("python scripts/change_control/validate_changes.py", text)


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
