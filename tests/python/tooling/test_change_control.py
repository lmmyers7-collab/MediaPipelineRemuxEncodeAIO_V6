from __future__ import annotations

import contextlib
import io
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from mediapipeline.tools.dev import audit_checks
from mediapipeline.tools.paths import find_repo_root
from mediapipeline.tools.change_control import (
    build_change_index,
    build_changelog,
    build_release_manifest,
    finalize_release,
    packet_coverage,
    prepare_release,
    record_change_touch,
    validate_changes,
)
from typing import Any


REPO_ROOT = find_repo_root(Path(__file__))
CHANGE_CONTROL_DIR = REPO_ROOT / "src" / "mediapipeline" / "tools" / "change_control"


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
        "files_touched": ["src/mediapipeline/tools/change_control/build_release_manifest.py"],
        "tests_added": ["tests/python/tooling/test_change_control.py"],
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
        self.module.UNRELEASED_DIR = self.root / "ops" / "release" / "changes" / "unreleased"
        if hasattr(self.module, "RELEASED_DIR"):
            self.old_values["RELEASED_DIR"] = self.module.RELEASED_DIR
            self.module.RELEASED_DIR = self.root / "ops" / "release" / "changes" / "released"
        if hasattr(self.module, "VERSION_FILE"):
            self.old_values["VERSION_FILE"] = self.module.VERSION_FILE
            self.module.VERSION_FILE = self.root / "ops" / "release" / "metadata" / "VERSION"
        if hasattr(self.module, "RELEASE_HISTORY_DIR"):
            self.old_values["RELEASE_HISTORY_DIR"] = self.module.RELEASE_HISTORY_DIR
            self.module.RELEASE_HISTORY_DIR = self.root / "ops" / "release" / "metadata" / "history"

    def __exit__(self, *_exc: object) -> None:
        for name, value in self.old_values.items():
            setattr(self.module, name, value)


class ChangePacketCoverageTests(unittest.TestCase):
    def test_worktree_paths_covered_by_unreleased_packet_pass(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            packet = _packet("MP-CHANGE-2026-0604-001", "0.1.0-dev")
            packet["files_touched"] = ["src/mediapipeline/core/maintenance/change_ledger.py"]
            _write_packet(root, "ops/release/changes/unreleased/MP-CHANGE-2026-0604-001.json", packet)

            result = packet_coverage.coverage_for_paths(
                root=root,
                scope="test",
                changed_files=["src\\mediapipeline\\core\\maintenance\\change_ledger.py"],
            )

        self.assertEqual(result.covered_files, ("src/mediapipeline/core/maintenance/change_ledger.py",))
        self.assertEqual(result.uncovered_files, ())

    def test_docs_root_case_is_canonicalized_for_windows_git_status_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            packet = _packet("MP-CHANGE-2026-0604-001", "0.1.0-dev")
            packet["files_touched"] = ["docs/DOCS_INDEX.md"]
            _write_packet(root, "ops/release/changes/unreleased/MP-CHANGE-2026-0604-001.json", packet)

            result = packet_coverage.coverage_for_paths(
                root=root,
                scope="worktree",
                changed_files=["Docs\\DOCS_INDEX.md"],
                allow_directory_coverage=False,
            )

        self.assertEqual(result.covered_files, ("docs/DOCS_INDEX.md",))
        self.assertEqual(result.uncovered_files, ())

    def test_generated_summary_source_root_case_is_canonicalized(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            packet = _packet("MP-CHANGE-2026-0604-001", "0.1.0-dev")
            packet["files_touched"] = ["docs/generated/summaries/docs/DOCS_INDEX.md.md"]
            _write_packet(root, "ops/release/changes/unreleased/MP-CHANGE-2026-0604-001.json", packet)

            result = packet_coverage.coverage_for_paths(
                root=root,
                scope="worktree",
                changed_files=["Docs\\generated\\summaries\\Docs\\DOCS_INDEX.md.md"],
                allow_directory_coverage=False,
            )

        self.assertEqual(result.covered_files, ("docs/generated/summaries/docs/DOCS_INDEX.md.md",))
        self.assertEqual(result.uncovered_files, ())

    def test_missing_changed_file_reports_exact_uncovered_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            packet = _packet("MP-CHANGE-2026-0604-001", "0.1.0-dev")
            packet["files_touched"] = ["README.md"]
            _write_packet(root, "ops/release/changes/unreleased/MP-CHANGE-2026-0604-001.json", packet)

            result = packet_coverage.coverage_for_paths(
                root=root,
                scope="test",
                changed_files=["src/mediapipeline/tools/change_control/validate_changes.py"],
            )

        self.assertEqual(result.uncovered_files, ("src/mediapipeline/tools/change_control/validate_changes.py",))

    def test_directory_entries_cover_descendant_changed_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            packet = _packet("MP-CHANGE-2026-0604-001", "0.1.0-dev")
            packet["files_touched"] = ["src/mediapipeline", "DesktopApp"]
            _write_packet(root, "ops/release/changes/unreleased/MP-CHANGE-2026-0604-001.json", packet)

            result = packet_coverage.coverage_for_paths(
                root=root,
                scope="test",
                changed_files=[
                    "src/mediapipeline/tools/change_control/validate_changes.py",
                    "DesktopApp/old_module.py",
                    "src/other.py",
                ],
            )

        self.assertEqual(
            result.covered_files,
            (
                "DesktopApp/old_module.py",
                "src/mediapipeline/tools/change_control/validate_changes.py",
            ),
        )
        self.assertEqual(result.uncovered_files, ("src/other.py",))

    def test_directory_entries_do_not_cover_worktree_paths_when_strict_exact_mode_is_used(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            packet = _packet("MP-CHANGE-2026-0604-001", "0.1.0-dev")
            packet["files_touched"] = ["docs"]
            _write_packet(root, "ops/release/changes/unreleased/MP-CHANGE-2026-0604-001.json", packet)

            result = packet_coverage.coverage_for_paths(
                root=root,
                scope="worktree",
                changed_files=["docs/archive/root-artifacts/CON.txt"],
                allow_directory_coverage=False,
            )

        self.assertEqual(result.covered_files, ())
        self.assertEqual(result.uncovered_files, ("docs/archive/root-artifacts/CON.txt",))

    def test_released_packets_do_not_satisfy_current_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            released_packet = _packet("MP-CHANGE-2026-0601-001", "1.0.0")
            released_packet["files_touched"] = ["src/mediapipeline/core/released.py"]
            _write_packet(root, "ops/release/changes/released/1.0.0/MP-CHANGE-2026-0601-001.json", released_packet)

            result = packet_coverage.coverage_for_paths(
                root=root,
                scope="test",
                changed_files=["src/mediapipeline/core/released.py"],
            )

        self.assertEqual(result.covered_files, ())
        self.assertEqual(result.uncovered_files, ("src/mediapipeline/core/released.py",))

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
            packet["files_touched"] = ["ops/release/changes/unreleased/MP-CHANGE-2026-0604-001.json"]
            packet_path = _write_packet(root, "ops/release/changes/unreleased/MP-CHANGE-2026-0604-001.json", packet)
            _run_git(root, "add", "ops/release/changes/unreleased/MP-CHANGE-2026-0604-001.json")
            staged_file = root / "src" / "mediapipeline" / "core" / "maintenance" / "change_ledger.py"
            staged_file.parent.mkdir(parents=True)
            staged_file.write_text("print('ledger')\n", encoding="utf-8")
            _run_git(root, "add", "src/mediapipeline/core/maintenance/change_ledger.py")

            packet["files_touched"].append("src/mediapipeline/core/maintenance/change_ledger.py")
            packet_path.write_text(json.dumps(packet, indent=2) + "\n", encoding="utf-8")

            result = packet_coverage.coverage_for_staged(root)

        self.assertIn("src/mediapipeline/core/maintenance/change_ledger.py", result.uncovered_files)

    def test_diff_mode_checks_files_changed_since_base_ref(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _init_git(root)
            (root / "ops" / "release" / "metadata").mkdir(parents=True)
            (root / "ops" / "release" / "metadata" / "VERSION").write_text("0.1.0-dev\n", encoding="utf-8")
            _write_packet(root, "ops/release/changes/unreleased/MP-CHANGE-2026-0604-001.json", _packet("MP-CHANGE-2026-0604-001", "0.1.0-dev"))
            _run_git(root, "add", ".")
            _run_git(root, "commit", "-m", "baseline")

            packet = _packet("MP-CHANGE-2026-0604-002", "0.1.0-dev")
            packet["files_touched"] = [
                "src/mediapipeline/core/maintenance/change_ledger.py",
                "ops/release/changes/unreleased/MP-CHANGE-2026-0604-002.json",
            ]
            _write_packet(root, "ops/release/changes/unreleased/MP-CHANGE-2026-0604-002.json", packet)
            changed = root / "src" / "mediapipeline" / "core" / "maintenance" / "change_ledger.py"
            changed.parent.mkdir(parents=True, exist_ok=True)
            changed.write_text("print('ledger')\n", encoding="utf-8")
            _run_git(root, "add", ".")
            _run_git(root, "commit", "-m", "covered change")

            result = packet_coverage.coverage_for_diff(root, "HEAD~1")

        self.assertEqual(result.uncovered_files, ())
        self.assertIn("src/mediapipeline/core/maintenance/change_ledger.py", result.covered_files)


class ValidateChangesCoverageTests(unittest.TestCase):
    def test_default_validation_does_not_require_worktree_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "ops" / "release" / "metadata").mkdir(parents=True)
            (root / "ops" / "release" / "metadata" / "VERSION").write_text("0.1.0-dev\n", encoding="utf-8")
            _write_packet(root, "ops/release/changes/unreleased/MP-CHANGE-2026-0604-001.json", _packet("MP-CHANGE-2026-0604-001", "0.1.0-dev"))

            with _PatchedChangeControl(validate_changes, root):
                result = validate_changes.main([])

        self.assertEqual(result, 0)

    def test_worktree_strict_coverage_failure_includes_path_and_helper_hint(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _init_git(root)
            (root / "ops" / "release" / "metadata").mkdir(parents=True)
            (root / "ops" / "release" / "metadata" / "VERSION").write_text("0.1.0-dev\n", encoding="utf-8")
            packet = _packet("MP-CHANGE-2026-0604-001", "0.1.0-dev")
            packet["files_touched"] = ["ops/release/changes/unreleased/MP-CHANGE-2026-0604-001.json"]
            _write_packet(root, "ops/release/changes/unreleased/MP-CHANGE-2026-0604-001.json", packet)
            missing = root / "src" / "mediapipeline" / "tools" / "change_control" / "validate_changes.py"
            missing.parent.mkdir(parents=True)
            missing.write_text("# changed\n", encoding="utf-8")

            stderr = io.StringIO()
            with _PatchedChangeControl(validate_changes, root), contextlib.redirect_stderr(stderr):
                result = validate_changes.main(["--require-worktree-coverage"])

        self.assertEqual(result, 1)
        output = stderr.getvalue()
        self.assertIn("src/mediapipeline/tools/change_control/validate_changes.py", output)
        self.assertIn("ops/scripts/dev/run-python-tool.py mediapipeline.tools.change_control.record_change_touch MP-CHANGE-YYYY-MMDD-### <path>", output)

    def test_git_unavailable_strict_mode_fails_actionably(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "ops" / "release" / "metadata").mkdir(parents=True)
            (root / "ops" / "release" / "metadata" / "VERSION").write_text("0.1.0-dev\n", encoding="utf-8")
            _write_packet(root, "ops/release/changes/unreleased/MP-CHANGE-2026-0604-001.json", _packet("MP-CHANGE-2026-0604-001", "0.1.0-dev"))

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
            _write_packet(root, f"ops/release/changes/unreleased/{change_id}.json", _packet(change_id, "0.1.0-dev"))

            with _PatchedChangeControl(record_change_touch, root):
                result = record_change_touch.main(
                    [
                        change_id,
                        "src\\mediapipeline\\core\\maintenance\\change_ledger.py",
                        "--area",
                        "maintenance",
                        "--test",
                        "tests/python/desktop/test_maintenance_change_ledger.py",
                        "--validation",
                        "unit tests - passed",
                        "--note",
                        "Python impact captured in files_touched.",
                        "--complete",
                    ]
                )

            packet = json.loads((root / f"ops/release/changes/unreleased/{change_id}.json").read_text(encoding="utf-8"))

        self.assertEqual(result, 0)
        self.assertEqual(packet["status"], "complete")
        self.assertRegex(packet["date_completed"], r"^\d{4}-\d{2}-\d{2}$")
        self.assertIn("src/mediapipeline/core/maintenance/change_ledger.py", packet["files_touched"])
        self.assertIn(f"ops/release/changes/unreleased/{change_id}.json", packet["files_touched"])
        self.assertIn("maintenance", packet["affected_areas"])
        self.assertIn("tests/python/desktop/test_maintenance_change_ledger.py", packet["tests_added"])
        self.assertIn("unit tests - passed", packet["manual_validation"])
        self.assertIn("Python impact captured", packet["notes"])

    def test_helper_rejects_invalid_change_id_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            change_id = "MP-CHANGE-2026-0604-001"
            packet_path = _write_packet(root, f"ops/release/changes/unreleased/{change_id}.json", _packet(change_id, "0.1.0-dev"))
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
            _write_packet(root, f"ops/release/changes/unreleased/{change_id}.json", _packet(change_id, "0.1.0-dev"))
            staged = root / "staged.py"
            unstaged = root / "unstaged.py"
            staged.write_text("print('staged')\n", encoding="utf-8")
            unstaged.write_text("print('unstaged')\n", encoding="utf-8")
            _run_git(root, "add", "staged.py")

            with _PatchedChangeControl(record_change_touch, root):
                record_change_touch.main([change_id, "--from-staged"])

            packet = json.loads((root / f"ops/release/changes/unreleased/{change_id}.json").read_text(encoding="utf-8"))

        self.assertIn("staged.py", packet["files_touched"])
        self.assertNotIn("unstaged.py", packet["files_touched"])


class ChangeControlWorkflowStaticTests(unittest.TestCase):
    def test_pre_commit_includes_staged_change_packet_coverage_hook(self) -> None:
        text = (REPO_ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8")
        checks = {check.id: check for check in audit_checks.suite_checks("precommit")}

        self.assertIn("mediapipeline-audit-check-suite", text)
        self.assertIn("mediapipeline.tools.dev.audit_checks run precommit", text)
        self.assertIn("change-packet-staged-coverage", checks)
        coverage_check = checks["change-packet-staged-coverage"]
        self.assertEqual(coverage_check.module, "mediapipeline.tools.change_control.validate_changes")
        self.assertEqual(coverage_check.arguments, ("--require-staged-coverage",))

    def test_github_workflow_includes_pr_diff_change_packet_coverage(self) -> None:
        workflow = REPO_ROOT / ".github" / "workflows" / "phase1-drift.yml"
        if not workflow.is_file():
            self.skipTest("GitHub workflow metadata is omitted from release packages.")
        text = workflow.read_text(encoding="utf-8")

        self.assertIn("Check change packet coverage", text)
        self.assertIn("Unsafe pull request base ref", text)
        self.assertIn('git fetch origin "$baseRef`:$remoteRef" --depth=1', text)
        self.assertIn("mediapipeline.tools.change_control.validate_changes --require-diff-coverage $remoteRef", text)
        self.assertIn("python -m mediapipeline.tools.change_control.validate_changes", text)


class ChangeControlToolingTests(unittest.TestCase):
    def test_generated_change_outputs_normalize_legacy_packet_paths(self) -> None:
        legacy_packet = "ops/ops/release/metadata/changes/unreleased/MP-CHANGE-2026-0604-001.json"
        legacy_summary = (
            "docs/generated/summaries/ops/ops/release/metadata/changes/unreleased/"
            "MP-CHANGE-2026-0604-001.json.md"
        )

        index_text = build_change_index._list_text([legacy_packet, legacy_summary])
        changelog_lines = "\n".join(build_changelog._list_lines("Files touched", [legacy_packet, legacy_summary]))
        manifest_values = build_release_manifest._list_values(
            [{"files_touched": [legacy_packet, legacy_summary]}],
            "files_touched",
            normalize_paths=True,
        )

        for text in (index_text, changelog_lines, "\n".join(manifest_values)):
            self.assertIn("ops/release/changes/unreleased/MP-CHANGE-2026-0604-001.json", text)
            self.assertIn(
                "docs/generated/summaries/ops/release/changes/unreleased/MP-CHANGE-2026-0604-001.json.md",
                text,
            )
            self.assertNotIn("ops/ops/release/metadata/changes", text)

    def test_release_manifest_filters_removed_active_artifacts(self) -> None:
        removed_name = "T" + "LDR"
        manifest_values = build_release_manifest._list_values(
            [
                {
                    "files_touched": [
                        f"docs/{removed_name}.md",
                        f"docs/generated/summaries/Docs/{removed_name}.md.md",
                        "docs/CURRENT_PROJECT_STATE.md",
                    ]
                }
            ],
            "files_touched",
            normalize_paths=True,
        )

        self.assertEqual(manifest_values, ["docs/CURRENT_PROJECT_STATE.md"])

    def test_local_channel_supported_for_portable_release_metadata(self) -> None:
        self.assertIn("local", build_release_manifest.CHANNELS)
        self.assertIn("local", prepare_release.CHANNELS)
        self.assertIn("local", finalize_release.CHANNELS)

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            unreleased = root / "ops" / "release" / "changes" / "unreleased"
            released = root / "ops" / "release" / "changes" / "released"
            version_file = root / "ops" / "release" / "metadata" / "VERSION"
            manifest_path = root / "ops" / "release" / "metadata" / "RELEASE_MANIFEST.json"
            unreleased.mkdir(parents=True)
            version_file.parent.mkdir(parents=True)
            version_file.write_text("2026.06.04.001\n", encoding="utf-8")
            packet_path = unreleased / "MP-CHANGE-2026-0604-001.json"
            packet_path.write_text(
                json.dumps(_packet(packet_path.stem, "2026.06.04.001"), indent=2) + "\n",
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

                manifest = build_release_manifest.build_manifest(
                    version="2026.06.04.001",
                    channel="local",
                    output_path=manifest_path,
                )
            finally:
                (
                    build_release_manifest.REPO_ROOT,
                    build_release_manifest.UNRELEASED_DIR,
                    build_release_manifest.RELEASED_DIR,
                    build_release_manifest.VERSION_FILE,
                    build_release_manifest.DEFAULT_MANIFEST_PATH,
                ) = old_values

        self.assertEqual(manifest["version"], "2026.06.04.001")
        self.assertEqual(manifest["version_scheme"], "calendar-build")
        self.assertEqual(manifest["build_id"], "2026.06.04.001")
        self.assertIn("source_revision", manifest)
        self.assertIn("source_dirty", manifest)
        self.assertIn("tool_semver", manifest)
        self.assertEqual(manifest["release_channel"], "local")
        self.assertEqual(manifest["included_changes"], [packet_path.stem])

    def test_finalize_release_rolls_back_when_generator_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            unreleased = root / "ops" / "release" / "changes" / "unreleased"
            released = root / "ops" / "release" / "changes" / "released"
            version_file = root / "ops" / "release" / "metadata" / "VERSION"
            manifest_path = root / "ops" / "release" / "metadata" / "RELEASE_MANIFEST.json"
            changelog_path = root / "docs" / "change_control" / "CHANGELOG.md"
            index_path = root / "docs" / "change_control" / "CHANGE_INDEX.md"
            history_root = root / "ops" / "release" / "metadata" / "history"
            version_file.parent.mkdir(parents=True)
            changelog_path.parent.mkdir(parents=True)
            version_file.write_text("0.1.0-dev\n", encoding="utf-8")
            manifest_path.write_text('{"version":"0.1.0-dev"}\n', encoding="utf-8")
            changelog_path.write_text("# old changelog\n", encoding="utf-8")
            index_path.write_text("# old index\n", encoding="utf-8")
            packet = _packet("MP-CHANGE-2026-0604-001", "0.1.0-dev")
            packet["date_completed"] = ""
            packet_path = _write_packet(root, "ops/release/changes/unreleased/MP-CHANGE-2026-0604-001.json", packet)
            original_packet_text = packet_path.read_text(encoding="utf-8")

            calls: list[str] = []

            def failing_run_script(name: str, *_args: str) -> None:
                calls.append(name)
                if name == "build_changelog.py":
                    raise RuntimeError("generator failed")

            old_values = (
                finalize_release.REPO_ROOT,
                finalize_release.UNRELEASED_DIR,
                finalize_release.RELEASED_DIR,
                finalize_release.VERSION_FILE,
                finalize_release.MANIFEST_PATH,
                finalize_release.CHANGELOG_PATH,
                finalize_release.INDEX_PATH,
                finalize_release.HISTORY_ROOT,
                finalize_release.ARCHIVE_FILES,
                finalize_release._run_script,
            )
            try:
                finalize_release.REPO_ROOT = root
                finalize_release.UNRELEASED_DIR = unreleased
                finalize_release.RELEASED_DIR = released
                finalize_release.VERSION_FILE = version_file
                finalize_release.MANIFEST_PATH = manifest_path
                finalize_release.CHANGELOG_PATH = changelog_path
                finalize_release.INDEX_PATH = index_path
                finalize_release.HISTORY_ROOT = history_root
                finalize_release.ARCHIVE_FILES = [version_file, manifest_path, changelog_path, index_path]
                finalize_release._run_script = failing_run_script

                with self.assertRaisesRegex(RuntimeError, "generator failed"):
                    finalize_release._finalize("1.0.0", "local", [(packet_path, packet)])
            finally:
                (
                    finalize_release.REPO_ROOT,
                    finalize_release.UNRELEASED_DIR,
                    finalize_release.RELEASED_DIR,
                    finalize_release.VERSION_FILE,
                    finalize_release.MANIFEST_PATH,
                    finalize_release.CHANGELOG_PATH,
                    finalize_release.INDEX_PATH,
                    finalize_release.HISTORY_ROOT,
                    finalize_release.ARCHIVE_FILES,
                    finalize_release._run_script,
                ) = old_values

            self.assertEqual(calls, ["build_change_index.py", "build_changelog.py"])
            self.assertEqual(packet_path.read_text(encoding="utf-8"), original_packet_text)
            self.assertFalse((released / "1.0.0" / packet_path.name).exists())
            self.assertEqual(version_file.read_text(encoding="utf-8"), "0.1.0-dev\n")
            self.assertEqual(manifest_path.read_text(encoding="utf-8"), '{"version":"0.1.0-dev"}\n')
            self.assertEqual(changelog_path.read_text(encoding="utf-8"), "# old changelog\n")
            self.assertEqual(index_path.read_text(encoding="utf-8"), "# old index\n")
            self.assertFalse((history_root / "1.0.0").exists())

    def test_manifest_can_preview_dev_placeholder_packets_for_target_version(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            unreleased = root / "ops" / "release" / "changes" / "unreleased"
            released = root / "ops" / "release" / "changes" / "released"
            version_file = root / "ops" / "release" / "metadata" / "VERSION"
            manifest_path = root / "ops" / "release" / "metadata" / "RELEASE_MANIFEST.json"
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
                build_release_manifest.UNRELEASED_DIR = root / "ops" / "release" / "changes" / "unreleased"
                build_release_manifest.RELEASED_DIR = root / "ops" / "release" / "changes" / "released"
                build_release_manifest.VERSION_FILE = root / "ops" / "release" / "metadata" / "VERSION"

                with self.assertRaisesRegex(SystemExit, "ops/release/metadata/VERSION is missing"):
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
