from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
import uuid
from pathlib import Path
from typing import Any
from unittest.mock import patch

from mediapipeline.core.orchestration.runner import RunnerOptions, run_subtitle_convert_stage


ASS_FIXTURE = """[Script Info]
ScriptType: v4.00+

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,20,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,0,2,10,10,10,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:01.00,0:00:02.00,Default,,0,0,0,,Hello from scratch
"""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class SubtitleConvertStageTests(unittest.TestCase):
    def _roots(self, root: Path) -> tuple[Path, Path, Path]:
        scratch = root / "Scratch"
        source_root = root / "Source"
        scratch.mkdir(parents=True)
        source_root.mkdir(parents=True)
        input_path = scratch / "sample.ass"
        input_path.write_text(ASS_FIXTURE, encoding="utf-8")
        return scratch, source_root, input_path

    def _options(self, scratch: Path, source_root: Path, **kwargs: Any) -> RunnerOptions:
        return RunnerOptions(
            allowed_scratch_roots=(scratch,),
            protected_source_roots=(source_root,),
            **kwargs,
        )

    def _payload(self, input_path: Path, scratch: Path, source_root: Path) -> dict[str, Any]:
        return {
            "input_ass_path": str(input_path),
            "scratch_root": str(scratch),
            "source_roots": [str(source_root)],
            "intent": "dry_run",
        }

    def test_dry_run_parses_ass_without_writing_srt(self) -> None:
        with tempfile.TemporaryDirectory(prefix="mediapipeline-stage-subtitle-dry-") as tmp:
            scratch, source_root, input_path = self._roots(Path(tmp))
            input_hash = _sha256(input_path)

            result = run_subtitle_convert_stage(
                self._payload(input_path, scratch, source_root),
                self._options(scratch, source_root),
            )

            self.assertTrue(result.ok, result)
            self.assertEqual(result.data["cues_written"], 1)
            self.assertEqual(result.data["encoding"], "utf-8")
            self.assertTrue(result.data["dry_run_fingerprint"])
            self.assertFalse((scratch / "sample.srt").exists())
            self.assertEqual(_sha256(input_path), input_hash)

    def test_missing_confirmation_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory(prefix="mediapipeline-stage-subtitle-confirm-") as tmp:
            scratch, source_root, input_path = self._roots(Path(tmp))
            result = run_subtitle_convert_stage(
                {
                    **self._payload(input_path, scratch, source_root),
                    "intent": "execute",
                    "operation_id": str(uuid.uuid4()),
                    "dry_run_fingerprint": "a" * 64,
                },
                self._options(scratch, source_root),
            )

            self.assertFalse(result.ok)
            self.assertEqual(result.error.code if result.error else "", "stage.invalid_payload")
            self.assertTrue(input_path.exists())
            self.assertFalse((scratch / "sample.srt").exists())

    def test_outside_scratch_and_source_overlap_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory(prefix="mediapipeline-stage-subtitle-boundary-") as tmp:
            root = Path(tmp)
            scratch, source_root, _ = self._roots(root)
            outside = root / "Outside"
            outside.mkdir()
            outside_input = outside / "outside.ass"
            outside_input.write_text(ASS_FIXTURE, encoding="utf-8")
            outside_result = run_subtitle_convert_stage(
                self._payload(outside_input, scratch, source_root),
                self._options(scratch, source_root),
            )
            self.assertFalse(outside_result.ok)
            self.assertEqual(outside_result.error.code if outside_result.error else "", "stage.path_boundary_violation")
            self.assertFalse(outside_input.with_suffix(".srt").exists())

        with tempfile.TemporaryDirectory(prefix="mediapipeline-stage-subtitle-source-") as tmp:
            root = Path(tmp)
            source_root = root / "Source"
            scratch = source_root / "Scratch"
            scratch.mkdir(parents=True)
            input_path = scratch / "source.ass"
            input_path.write_text(ASS_FIXTURE, encoding="utf-8")
            overlap_result = run_subtitle_convert_stage(
                self._payload(input_path, scratch, source_root),
                self._options(scratch, source_root),
            )
            self.assertFalse(overlap_result.ok)
            self.assertEqual(
                overlap_result.error.code if overlap_result.error else "",
                "stage.source_boundary_violation",
            )
            self.assertFalse(input_path.with_suffix(".srt").exists())

    def test_execute_writes_one_srt_with_journal_and_duplicate_replay(self) -> None:
        with tempfile.TemporaryDirectory(prefix="mediapipeline-stage-subtitle-execute-") as tmp:
            scratch, source_root, input_path = self._roots(Path(tmp))
            input_hash = _sha256(input_path)
            command_journal: list[dict[str, Any]] = []
            operation_state: dict[str, dict[str, Any]] = {}

            def operation_journal(payload: dict[str, Any]) -> dict[str, Any] | None:
                operation_id = str(payload["operation_id"])
                if payload["event"] == "accepted":
                    previous = operation_state.get(operation_id)
                    if previous is not None:
                        return previous
                    operation_state[operation_id] = {}
                    return None
                operation_state[operation_id] = {"result": payload["result"]}
                return None

            dry_run = run_subtitle_convert_stage(
                self._payload(input_path, scratch, source_root),
                self._options(scratch, source_root),
            )
            operation_id = str(uuid.uuid4())
            execute_payload = {
                **self._payload(input_path, scratch, source_root),
                "intent": "execute",
                "confirm_subtitle_convert": True,
                "operation_id": operation_id,
                "dry_run_fingerprint": dry_run.data["dry_run_fingerprint"],
            }
            options = self._options(
                scratch,
                source_root,
                journal_record=command_journal.append,
                operation_journal_record=operation_journal,
            )
            result = run_subtitle_convert_stage(execute_payload, options)

            self.assertTrue(result.ok, result)
            output_path = scratch / "sample.srt"
            self.assertTrue(output_path.exists())
            self.assertIn("Hello from scratch", output_path.read_text(encoding="utf-8"))
            self.assertEqual(_sha256(input_path), input_hash)
            self.assertEqual(result.data["tracks_converted"], 1)
            self.assertEqual(result.data["sidecars_written"], [str(output_path)])
            evidence_path = Path(result.data["evidence_path"])
            evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
            self.assertEqual(evidence["status"], "completed")
            self.assertEqual(evidence["source_media_mutation"], "forbidden")
            self.assertEqual(command_journal[-1]["command"], "stage.subtitle-convert")

            replay = run_subtitle_convert_stage(execute_payload, options)
            self.assertTrue(replay.ok)
            self.assertEqual(replay.data["operation_id"], operation_id)
            self.assertEqual(_sha256(output_path), result.data["output_sha256"])

    def test_stale_fingerprint_and_existing_output_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory(prefix="mediapipeline-stage-subtitle-stale-") as tmp:
            scratch, source_root, input_path = self._roots(Path(tmp))
            options = self._options(
                scratch,
                source_root,
                journal_record=lambda payload: None,
                operation_journal_record=lambda payload: None,
            )
            stale = run_subtitle_convert_stage(
                {
                    **self._payload(input_path, scratch, source_root),
                    "intent": "execute",
                    "confirm_subtitle_convert": True,
                    "operation_id": str(uuid.uuid4()),
                    "dry_run_fingerprint": "0" * 64,
                },
                options,
            )
            self.assertFalse(stale.ok)
            self.assertEqual(stale.error.code if stale.error else "", "stage.dry_run_fingerprint_mismatch")
            self.assertFalse(input_path.with_suffix(".srt").exists())

            input_path.with_suffix(".srt").write_text("existing", encoding="utf-8")
            existing = run_subtitle_convert_stage(
                self._payload(input_path, scratch, source_root),
                self._options(scratch, source_root),
            )
            self.assertFalse(existing.ok)
            self.assertEqual(existing.error.code if existing.error else "", "stage.destination_exists")
            self.assertEqual(input_path.with_suffix(".srt").read_text(encoding="utf-8"), "existing")

    def test_execute_requires_command_journal_before_output(self) -> None:
        with tempfile.TemporaryDirectory(prefix="mediapipeline-stage-subtitle-journal-") as tmp:
            scratch, source_root, input_path = self._roots(Path(tmp))
            dry_run = run_subtitle_convert_stage(
                self._payload(input_path, scratch, source_root),
                self._options(scratch, source_root),
            )
            result = run_subtitle_convert_stage(
                {
                    **self._payload(input_path, scratch, source_root),
                    "intent": "execute",
                    "confirm_subtitle_convert": True,
                    "operation_id": str(uuid.uuid4()),
                    "dry_run_fingerprint": dry_run.data["dry_run_fingerprint"],
                },
                self._options(
                    scratch,
                    source_root,
                    operation_journal_record=lambda payload: None,
                ),
            )
            self.assertFalse(result.ok)
            self.assertEqual(result.error.code if result.error else "", "stage.command_journal_required")
            self.assertFalse(input_path.with_suffix(".srt").exists())

    def test_terminal_evidence_failure_rolls_back_srt(self) -> None:
        from mediapipeline.core.subtitles import stage as subtitle_stage

        with tempfile.TemporaryDirectory(prefix="mediapipeline-stage-subtitle-rollback-") as tmp:
            scratch, source_root, input_path = self._roots(Path(tmp))
            dry_run = run_subtitle_convert_stage(
                self._payload(input_path, scratch, source_root),
                self._options(scratch, source_root),
            )
            real_write = subtitle_stage._write_manifest
            writes = 0

            def fail_terminal_write(path: Path, payload: dict[str, Any]) -> None:
                nonlocal writes
                writes += 1
                if writes == 2:
                    raise OSError("terminal evidence denied")
                real_write(path, payload)

            with patch.object(subtitle_stage, "_write_manifest", side_effect=fail_terminal_write):
                result = run_subtitle_convert_stage(
                    {
                        **self._payload(input_path, scratch, source_root),
                        "intent": "execute",
                        "confirm_subtitle_convert": True,
                        "operation_id": str(uuid.uuid4()),
                        "dry_run_fingerprint": dry_run.data["dry_run_fingerprint"],
                    },
                    self._options(
                        scratch,
                        source_root,
                        journal_record=lambda payload: None,
                        operation_journal_record=lambda payload: None,
                    ),
                )

            self.assertFalse(result.ok)
            self.assertEqual(result.error.code if result.error else "", "stage.recovery_required")
            self.assertTrue(input_path.exists())
            self.assertFalse(input_path.with_suffix(".srt").exists())

    def test_no_dialogue_routes_to_review_without_output(self) -> None:
        with tempfile.TemporaryDirectory(prefix="mediapipeline-stage-subtitle-review-") as tmp:
            scratch, source_root, input_path = self._roots(Path(tmp))
            input_path.write_text(ASS_FIXTURE.replace("Dialogue: 0,", "Comment: 0,"), encoding="utf-8")
            dry_run = run_subtitle_convert_stage(
                self._payload(input_path, scratch, source_root),
                self._options(scratch, source_root),
            )
            self.assertTrue(dry_run.ok)
            self.assertTrue(dry_run.data["review_required"])
            self.assertIn("no dialogue cues", dry_run.data["review_reason"])

            result = run_subtitle_convert_stage(
                {
                    **self._payload(input_path, scratch, source_root),
                    "intent": "execute",
                    "confirm_subtitle_convert": True,
                    "operation_id": str(uuid.uuid4()),
                    "dry_run_fingerprint": dry_run.data["dry_run_fingerprint"],
                },
                self._options(
                    scratch,
                    source_root,
                    journal_record=lambda payload: None,
                    operation_journal_record=lambda payload: None,
                ),
            )
            self.assertTrue(result.ok)
            self.assertTrue(result.data["review_required"])
            self.assertEqual(result.data["tracks_converted"], 0)
            self.assertFalse(input_path.with_suffix(".srt").exists())


if __name__ == "__main__":
    unittest.main()
