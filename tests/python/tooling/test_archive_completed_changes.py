from __future__ import annotations

import contextlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mediapipeline.tools.change_control import (
    archive_completed,
    build_change_index,
    build_release_manifest,
    finalize_release,
    validate_changes,
)


def _packet(change_id: str, *, status: str = "complete", completed: str | None = "2026-06-02") -> dict[str, object]:
    return {
        "id": change_id,
        "title": "Archive test",
        "version_target": "2026.06.04.001",
        "status": status,
        "type": "tooling",
        "risk_level": "low",
        "date_started": "2026-06-02",
        "date_completed": completed,
        "summary": "Validated archive evidence.",
        "reason": "Keep active packets small.",
        "affected_areas": ["change_control"],
        "behavior_before": "Completed evidence stayed active.",
        "behavior_after": "Completed evidence is archived.",
        "files_touched": ["README.md"],
        "tests_added": [],
        "manual_validation": ["unit test"],
        "rollback_plan": "Move the packet back to unreleased.",
        "related_changes": [],
        "notes": "",
    }


def _write(root: Path, relative: str, packet: dict[str, object]) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(packet, indent=2) + "\n", encoding="utf-8")
    return path


@contextlib.contextmanager
def _patched_archive(root: Path):
    archived = root / "ops" / "release" / "changes" / "archived"
    unreleased = root / "ops" / "release" / "changes" / "unreleased"
    released = root / "ops" / "release" / "changes" / "released"
    with (
        patch.object(archive_completed, "REPO_ROOT", root),
        patch.object(archive_completed, "UNRELEASED_DIR", unreleased),
        patch.object(archive_completed, "ARCHIVED_DIR", archived),
        patch.object(archive_completed, "RELEASED_DIR", released),
        patch.object(archive_completed, "SUMMARY_ROOT", root / "docs" / "generated" / "summaries"),
        patch.object(
            archive_completed,
            "REGENERATED_OUTPUTS",
            (
                root / "docs" / "change_control" / "CHANGE_INDEX.md",
                root / "docs" / "change_control" / "CHANGELOG.md",
            ),
        ),
        patch.object(validate_changes, "REPO_ROOT", root),
        patch.object(validate_changes, "UNRELEASED_DIR", unreleased),
        patch.object(validate_changes, "RELEASED_DIR", released),
    ):
        yield


class ArchiveCompletedChangeTests(unittest.TestCase):
    def test_plan_selects_only_valid_complete_packets(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            _write(root, "ops/release/changes/unreleased/MP-CHANGE-2026-0602-001.json", _packet("MP-CHANGE-2026-0602-001"))
            _write(root, "ops/release/changes/unreleased/MP-CHANGE-2026-0602-002.json", _packet("MP-CHANGE-2026-0602-002", status="planned", completed=None))
            _write(root, "ops/release/changes/unreleased/MP-CHANGE-2026-0602-003.json", _packet("MP-CHANGE-2026-0602-003", status="in_progress", completed=None))
            _write(root, "ops/release/changes/unreleased/MP-CHANGE-2026-0602-004.json", _packet("MP-CHANGE-2026-0602-004", completed=None))

            with _patched_archive(root):
                plan = archive_completed.build_plan()

        self.assertEqual([item.change_id for item in plan.moves], ["MP-CHANGE-2026-0602-001"])
        self.assertEqual(plan.active_open_count, 2)
        self.assertEqual(len(plan.invalid_skipped), 1)

    def test_explicit_active_packet_is_refused(self) -> None:
        change_id = "MP-CHANGE-2026-0602-001"
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            _write(root, f"ops/release/changes/unreleased/{change_id}.json", _packet(change_id, status="planned", completed=None))
            with _patched_archive(root):
                plan = archive_completed.build_plan(packet_ids=(change_id,))

        self.assertFalse(plan.moves)
        self.assertIn("status=planned", plan.refusals[0])

    def test_existing_archive_target_is_refused_during_preview(self) -> None:
        change_id = "MP-CHANGE-2026-0602-001"
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            _write(root, f"ops/release/changes/unreleased/{change_id}.json", _packet(change_id))
            _write(root, f"ops/release/changes/archived/2026-06/{change_id}.json", _packet(change_id))
            with _patched_archive(root):
                plan = archive_completed.build_plan(packet_ids=(change_id,))

        self.assertFalse(plan.moves)
        self.assertIn("refusing existing archive target", plan.refusals[0])

    def test_apply_moves_packet_prunes_summary_and_exact_retry_is_idempotent(self) -> None:
        change_id = "MP-CHANGE-2026-0602-001"
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            source = _write(root, f"ops/release/changes/unreleased/{change_id}.json", _packet(change_id))
            summary = root / "docs" / "generated" / "summaries" / "ops" / "release" / "changes" / "unreleased" / f"{change_id}.json.md"
            summary.parent.mkdir(parents=True)
            summary.write_text("generated\n", encoding="utf-8")
            with _patched_archive(root), patch.object(archive_completed, "_run_regeneration"):
                plan = archive_completed.build_plan(packet_ids=(change_id,))
                archive_completed.apply_plan(plan)
                retry = archive_completed.build_plan(packet_ids=(change_id,))

            target = root / "ops" / "release" / "changes" / "archived" / "2026-06" / source.name
            self.assertTrue(target.is_file())
            self.assertFalse(source.exists())
            self.assertFalse(summary.exists())

        self.assertFalse(retry.moves)
        self.assertIn(change_id, retry.already_archived[0])

    def test_generator_failure_rolls_back_packet_and_summary(self) -> None:
        change_id = "MP-CHANGE-2026-0602-001"
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            source = _write(root, f"ops/release/changes/unreleased/{change_id}.json", _packet(change_id))
            summary = root / "docs" / "generated" / "summaries" / "ops" / "release" / "changes" / "unreleased" / f"{change_id}.json.md"
            summary.parent.mkdir(parents=True)
            summary.write_text("generated\n", encoding="utf-8")
            with _patched_archive(root), patch.object(archive_completed, "_run_regeneration", side_effect=RuntimeError("failed")):
                plan = archive_completed.build_plan(packet_ids=(change_id,))
                with self.assertRaisesRegex(RuntimeError, "failed"):
                    archive_completed.apply_plan(plan)

            self.assertTrue(source.is_file())
            self.assertTrue(summary.is_file())
            self.assertFalse((root / "ops" / "release" / "changes" / "archived" / "2026-06" / source.name).exists())

    def test_archived_packets_remain_in_index_manifest_and_finalization_input(self) -> None:
        change_id = "MP-CHANGE-2026-0602-001"
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            _write(root, f"ops/release/changes/archived/2026-06/{change_id}.json", _packet(change_id))
            unreleased = root / "ops" / "release" / "changes" / "unreleased"
            released = root / "ops" / "release" / "changes" / "released"
            version_file = root / "ops" / "release" / "metadata" / "VERSION"
            version_file.parent.mkdir(parents=True)
            version_file.write_text("2026.06.04.001\n", encoding="utf-8")
            manifest_path = root / "manifest.json"
            with (
                patch.object(build_change_index, "REPO_ROOT", root),
                patch.object(build_change_index, "UNRELEASED_DIR", unreleased),
                patch.object(build_change_index, "RELEASED_DIR", released),
                patch.object(build_release_manifest, "REPO_ROOT", root),
                patch.object(build_release_manifest, "UNRELEASED_DIR", unreleased),
                patch.object(build_release_manifest, "RELEASED_DIR", released),
                patch.object(build_release_manifest, "VERSION_FILE", version_file),
                patch.object(finalize_release, "UNRELEASED_DIR", unreleased),
            ):
                index = build_change_index.build_index()
                manifest = build_release_manifest.build_manifest(
                    version="2026.06.04.001", output_path=manifest_path
                )
                finalize_paths = finalize_release._packet_paths()

        self.assertIn("Archived completed packets", index)
        self.assertIn(f"ops/release/changes/archived/2026-06/{change_id}.json", index)
        self.assertEqual(manifest["included_changes"], [change_id])
        self.assertEqual([path.name for path in finalize_paths], [f"{change_id}.json"])

    def test_archive_validation_requires_complete_status_and_matching_bucket(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            path = _write(
                root,
                "ops/release/changes/archived/2026-07/MP-CHANGE-2026-0602-001.json",
                _packet("MP-CHANGE-2026-0602-001"),
            )
            with patch.object(validate_changes, "REPO_ROOT", root), patch.object(
                validate_changes,
                "UNRELEASED_DIR",
                root / "ops" / "release" / "changes" / "unreleased",
            ):
                errors = validate_changes._validate_archived_packet(path, _packet(path.stem))

        self.assertIn("date_completed must match archive folder", errors[0])

    def test_planned_high_risk_skeleton_can_be_created_before_execution_detail(self) -> None:
        packet = _packet(
            "MP-CHANGE-2026-0602-001",
            status="planned",
            completed=None,
        )
        packet["risk_level"] = "high"
        packet["notes"] = ""
        packet["rollback_plan"] = ""
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            path = _write(
                root,
                "ops/release/changes/unreleased/MP-CHANGE-2026-0602-001.json",
                packet,
            )
            with patch.object(validate_changes, "REPO_ROOT", root):
                errors = validate_changes.packet_validation_errors(
                    path,
                    packet,
                    repo_root=root,
                )

        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
