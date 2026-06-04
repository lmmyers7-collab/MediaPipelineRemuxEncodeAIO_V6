from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.contracts.stages import DecideResult, ProbeResult, StageResult


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENTRYPOINT = PROJECT_ROOT / "engine" / "entrypoint.ps1"
BUNDLED_PWSH = PROJECT_ROOT / "Pipeline" / "PowerShell-7.6.0-win-x64" / "pwsh.exe"
BUNDLED_FFMPEG = PROJECT_ROOT / "Pipeline" / "Tools" / "ffmpeg" / "bin" / "ffmpeg.exe"


def _pwsh() -> str | None:
    if BUNDLED_PWSH.exists():
        return str(BUNDLED_PWSH)
    return shutil.which("pwsh")


def _ffmpeg() -> str | None:
    if BUNDLED_FFMPEG.exists():
        return str(BUNDLED_FFMPEG)
    return shutil.which("ffmpeg")


class StageEntrypointTests(unittest.TestCase):
    def run_entrypoint(self, stage: str, payload: dict) -> subprocess.CompletedProcess[str]:
        powershell = _pwsh()
        if powershell is None:
            self.skipTest("PowerShell is not available")
        return subprocess.run(
            [
                powershell,
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(ENTRYPOINT),
                "-Stage",
                stage,
                "-PayloadJson",
                json.dumps(payload),
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )

    def test_unknown_stage_returns_single_structured_json_result(self) -> None:
        completed = self.run_entrypoint("unknown-stage", {})

        self.assertNotEqual(completed.returncode, 0)
        result = StageResult.model_validate(json.loads(completed.stdout))
        self.assertFalse(result.ok)
        self.assertEqual(result.stage, "unknown-stage")
        self.assertEqual(result.error.code if result.error else "", "stage.unknown")

    def test_invalid_payload_returns_single_structured_json_result(self) -> None:
        completed = self.run_entrypoint("decide", {"schema_version": "v1", "stage": "decide", "payload": {}})

        self.assertNotEqual(completed.returncode, 0)
        result = StageResult.model_validate(json.loads(completed.stdout))
        self.assertFalse(result.ok)
        self.assertEqual(result.stage, "decide")
        self.assertEqual(result.error.code if result.error else "", "stage.invalid_payload")

    def test_unknown_envelope_fields_are_rejected_before_dispatch(self) -> None:
        completed = self.run_entrypoint(
            "decide",
            {
                "schema_version": "v1",
                "stage": "decide",
                "payload": {"file_size_bytes": 1024},
                "unexpected": True,
            },
        )

        self.assertNotEqual(completed.returncode, 0)
        result = StageResult.model_validate(json.loads(completed.stdout))
        self.assertFalse(result.ok)
        self.assertEqual(result.error.code if result.error else "", "stage.invalid_payload")
        self.assertIn("unknown stage request envelope field 'unexpected'", result.error.message if result.error else "")

    def test_decide_stage_rejects_unknown_payload_fields(self) -> None:
        completed = self.run_entrypoint(
            "decide",
            {
                "schema_version": "v1",
                "stage": "decide",
                "payload": {"file_size_bytes": 1024, "unexpected": True},
            },
        )

        self.assertNotEqual(completed.returncode, 0)
        result = StageResult.model_validate(json.loads(completed.stdout))
        self.assertFalse(result.ok)
        self.assertEqual(result.error.code if result.error else "", "stage.invalid_payload")
        self.assertIn("unknown decide payload field 'unexpected'", result.error.message if result.error else "")

    def test_decide_stage_rejects_string_boolean_payload_fields(self) -> None:
        completed = self.run_entrypoint(
            "decide",
            {
                "schema_version": "v1",
                "stage": "decide",
                "payload": {
                    "file_size_bytes": 1024,
                    "is_tv": "false",
                },
            },
        )

        self.assertNotEqual(completed.returncode, 0)
        result = StageResult.model_validate(json.loads(completed.stdout))
        self.assertFalse(result.ok)
        self.assertEqual(result.error.code if result.error else "", "stage.invalid_payload")
        self.assertIn("payload field 'is_tv' must be a JSON boolean", result.error.message if result.error else "")

    def test_decide_stage_round_trip_uses_existing_routing_module(self) -> None:
        completed = self.run_entrypoint(
            "decide",
            {
                "schema_version": "v1",
                "stage": "decide",
                "payload": {
                    "file_size_bytes": 1024 * 1024,
                    "is_tv": False,
                    "duration_seconds": 3600,
                    "video_codec": "hevc",
                    "video_height": 1080,
                },
            },
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = StageResult.model_validate(json.loads(completed.stdout))
        self.assertTrue(result.ok)
        data = DecideResult.model_validate(result.data)
        self.assertEqual(data.route, "remux")
        self.assertEqual(data.reason_code, "size_within_threshold")
        self.assertEqual(data.bitrate_threshold_mbps, 20.0)
        self.assertFalse(data.size_over_threshold)
        self.assertFalse(data.bitrate_over_threshold)
        self.assertGreaterEqual(len(data.decision_trace), 1)

    def test_decide_stage_uses_movie_tv_bitrate_filters_and_folder_override(self) -> None:
        base_payload = {
            "schema_version": "v1",
            "stage": "decide",
            "payload": {
                "file_size_bytes": 20 * 1024 * 1024 * 1024,
                "duration_seconds": 3600,
                "video_codec": "hevc",
                "video_height": 1080,
                "encode_threshold_gb": 50,
                "tv_encode_threshold_gb": 50,
                "movie_route_max_video_bitrate_mbps": 35,
                "tv_route_max_video_bitrate_mbps": 18,
            },
        }

        movie_over = self.run_entrypoint("decide", base_payload)
        self.assertEqual(movie_over.returncode, 0, movie_over.stderr)
        movie_data = DecideResult.model_validate(StageResult.model_validate(json.loads(movie_over.stdout)).data)
        self.assertEqual(movie_data.route, "encode")
        self.assertEqual(movie_data.reason_code, "bitrate_over_threshold")
        self.assertEqual(movie_data.bitrate_threshold_mbps, 20)

        tv_payload = json.loads(json.dumps(base_payload))
        tv_payload["payload"]["is_tv"] = True
        tv_payload["payload"]["video_height"] = 0
        tv_payload["payload"]["tv_route_max_video_bitrate_mbps"] = 60
        tv_under = self.run_entrypoint("decide", tv_payload)
        self.assertEqual(tv_under.returncode, 0, tv_under.stderr)
        tv_data = DecideResult.model_validate(StageResult.model_validate(json.loads(tv_under.stdout)).data)
        self.assertEqual(tv_data.route, "remux")
        self.assertEqual(tv_data.bitrate_threshold_mbps, 60)

        override_payload = json.loads(json.dumps(base_payload))
        override_payload["payload"]["movie_route_max_video_bitrate_mbps"] = 50
        override_payload["payload"]["route_hints"] = {"max_video_bitrate_mbps": 60}
        override = self.run_entrypoint("decide", override_payload)
        self.assertEqual(override.returncode, 0, override.stderr)
        override_data = DecideResult.model_validate(StageResult.model_validate(json.loads(override.stdout)).data)
        self.assertEqual(override_data.route, "remux")
        self.assertEqual(override_data.bitrate_threshold_mbps, 60)

    def test_decide_stage_route_threshold_mode_selects_size_bitrate_or_both(self) -> None:
        base_payload = {
            "schema_version": "v1",
            "stage": "decide",
            "payload": {
                "file_size_bytes": 10 * 1024 * 1024 * 1024,
                "duration_seconds": 7200,
                "video_codec": "hevc",
                "video_height": 1080,
                "encode_threshold_gb": 8,
                "tv_encode_threshold_gb": 3,
                "movie_route_max_video_bitrate_mbps": 35,
                "tv_route_max_video_bitrate_mbps": 18,
            },
        }

        advisory = self.run_entrypoint("decide", base_payload)
        self.assertEqual(advisory.returncode, 0, advisory.stderr)
        advisory_data = DecideResult.model_validate(StageResult.model_validate(json.loads(advisory.stdout)).data)
        self.assertEqual(advisory_data.route, "remux")
        self.assertEqual(advisory_data.reason_code, "plex_compatible_size_advisory")
        self.assertEqual(advisory_data.route_threshold_mode, "compatibility_advisory")
        self.assertEqual(advisory_data.threshold_gb, 8)
        self.assertEqual(advisory_data.bitrate_threshold_mbps, 20)
        self.assertTrue(advisory_data.size_over_threshold)
        self.assertFalse(advisory_data.bitrate_over_threshold)

        size_payload = json.loads(json.dumps(base_payload))
        size_payload["payload"]["route_threshold_mode"] = "size"
        size_only = self.run_entrypoint("decide", size_payload)
        self.assertEqual(size_only.returncode, 0, size_only.stderr)
        size_data = DecideResult.model_validate(StageResult.model_validate(json.loads(size_only.stdout)).data)
        self.assertEqual(size_data.route, "encode")
        self.assertEqual(size_data.reason_code, "size_over_threshold")

        bitrate_payload = json.loads(json.dumps(base_payload))
        bitrate_payload["payload"]["route_threshold_mode"] = "bitrate"
        bitrate_only = self.run_entrypoint("decide", bitrate_payload)
        self.assertEqual(bitrate_only.returncode, 0, bitrate_only.stderr)
        bitrate_data = DecideResult.model_validate(StageResult.model_validate(json.loads(bitrate_only.stdout)).data)
        self.assertEqual(bitrate_data.route, "remux")
        self.assertEqual(bitrate_data.reason_code, "size_threshold_ignored")

        both_payload = json.loads(json.dumps(base_payload))
        both_payload["payload"]["route_threshold_mode"] = "size_or_bitrate"
        both = self.run_entrypoint("decide", both_payload)
        self.assertEqual(both.returncode, 0, both.stderr)
        both_data = DecideResult.model_validate(StageResult.model_validate(json.loads(both.stdout)).data)
        self.assertEqual(both_data.route, "encode")
        self.assertEqual(both_data.reason_code, "size_over_threshold")

        hint_payload = json.loads(json.dumps(base_payload))
        hint_payload["payload"]["route_threshold_mode"] = "bitrate"
        hint_payload["payload"]["route_hints"] = {"route_threshold_mode": "size"}
        hint_override = self.run_entrypoint("decide", hint_payload)
        self.assertEqual(hint_override.returncode, 0, hint_override.stderr)
        hint_data = DecideResult.model_validate(StageResult.model_validate(json.loads(hint_override.stdout)).data)
        self.assertEqual(hint_data.route, "encode")
        self.assertEqual(hint_data.reason_code, "size_over_threshold")
        self.assertEqual(hint_data.route_threshold_mode, "size")

    def test_decide_stage_size_only_mode_ignores_bitrate_as_hard_filter(self) -> None:
        completed = self.run_entrypoint(
            "decide",
            {
                "schema_version": "v1",
                "stage": "decide",
                "payload": {
                    "file_size_bytes": 20 * 1024 * 1024 * 1024,
                    "duration_seconds": 3600,
                    "video_codec": "hevc",
                    "video_height": 1080,
                    "encode_threshold_gb": 50,
                    "movie_route_max_video_bitrate_mbps": 35,
                    "route_threshold_mode": "size",
                },
            },
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        data = DecideResult.model_validate(StageResult.model_validate(json.loads(completed.stdout)).data)
        self.assertEqual(data.route, "remux")
        self.assertEqual(data.reason_code, "size_within_threshold")
        self.assertEqual(data.route_threshold_mode, "size")
        self.assertEqual(data.bitrate_threshold_mbps, 20)
        self.assertTrue(data.bitrate_over_threshold)

    def test_decide_stage_missing_duration_does_not_fall_back_to_probe_estimated_bitrate(self) -> None:
        completed = self.run_entrypoint(
            "decide",
            {
                "schema_version": "v1",
                "stage": "decide",
                "payload": {
                    "file_size_bytes": 4 * 1024 * 1024 * 1024,
                    "duration_seconds": 0,
                    "video_codec": "hevc",
                    "video_height": 1080,
                    "encode_threshold_gb": 8,
                    "movie_route_max_video_bitrate_mbps": 35,
                    "route_threshold_mode": "bitrate",
                    "source_media_profile": {"estimated_bitrate_mbps": 80.0, "duration_seconds": 0},
                },
            },
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        data = DecideResult.model_validate(StageResult.model_validate(json.loads(completed.stdout)).data)
        self.assertEqual(data.route, "remux")
        self.assertEqual(data.reason_code, "size_within_threshold")
        self.assertEqual(data.estimated_bitrate_mbps, 0)
        self.assertEqual(data.bitrate_threshold_mbps, 20)
        self.assertFalse(data.bitrate_over_threshold)
        trace_codes = {str(item.get("code") or "") for item in data.decision_trace}
        self.assertNotIn("bitrate_over_threshold", trace_codes)
        self.assertNotIn("bitrate_estimated", trace_codes)

    def test_decide_stage_h264_ceiling_is_stricter_than_general_bitrate_filter(self) -> None:
        completed = self.run_entrypoint(
            "decide",
            {
                "schema_version": "v1",
                "stage": "decide",
                "payload": {
                    "file_size_bytes": 10 * 1024 * 1024 * 1024,
                    "duration_seconds": 3600,
                    "video_codec": "h264",
                    "video_height": 1080,
                    "encode_threshold_gb": 20,
                    "movie_route_max_video_bitrate_mbps": 35,
                    "h264_remux_max_bitrate_mbps": 10,
                    "allow_h264_remux_if_plex_compatible": True,
                },
            },
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        data = DecideResult.model_validate(StageResult.model_validate(json.loads(completed.stdout)).data)
        self.assertEqual(data.route, "encode")
        self.assertEqual(data.reason_code, "bitrate_over_threshold")

    def test_probe_stage_round_trip_uses_existing_media_probe_module(self) -> None:
        completed = self.run_entrypoint(
            "probe",
            {
                "schema_version": "v1",
                "stage": "probe",
                "payload": {
                    "scratch_path": str(PROJECT_ROOT / "missing-stage-probe-input.mkv"),
                },
            },
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = StageResult.model_validate(json.loads(completed.stdout))
        self.assertTrue(result.ok)
        data = ProbeResult.model_validate(result.data)
        self.assertFalse(data.probe_ok)
        self.assertEqual(data.probe_error, "file_missing")
        self.assertTrue(data.tool_path)

    def test_probe_stage_reports_generated_media_streams(self) -> None:
        ffmpeg = _ffmpeg()
        if ffmpeg is None:
            self.skipTest("FFmpeg is not available")

        with tempfile.TemporaryDirectory(prefix="mediapipeline-stage-probe-") as tmp:
            media_path = Path(tmp) / "probe-source.mkv"
            generated = subprocess.run(
                [
                    ffmpeg,
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-y",
                    "-f",
                    "lavfi",
                    "-i",
                    "testsrc2=size=128x72:rate=1:duration=1",
                    "-f",
                    "lavfi",
                    "-i",
                    "sine=frequency=1000:duration=1",
                    "-c:v",
                    "mpeg4",
                    "-c:a",
                    "aac",
                    "-shortest",
                    str(media_path),
                ],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
            )
            self.assertEqual(generated.returncode, 0, generated.stderr)

            completed = self.run_entrypoint(
                "probe",
                {
                    "schema_version": "v1",
                    "stage": "probe",
                    "payload": {"scratch_path": str(media_path)},
                },
            )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = StageResult.model_validate(json.loads(completed.stdout))
        self.assertTrue(result.ok)
        data = ProbeResult.model_validate(result.data)
        self.assertTrue(data.probe_ok)
        self.assertEqual(data.probe_error, "")
        self.assertTrue(data.tool_path)
        self.assertEqual(data.video_codec, "mpeg4")
        self.assertEqual(data.width, 128)
        self.assertEqual(data.height, 72)
        self.assertGreater(data.duration_seconds, 0)
        self.assertGreater(data.size_bytes, 0)
        self.assertGreaterEqual(len(data.streams), 2)
        self.assertIn("video", {stream.kind for stream in data.streams})
        self.assertIn("audio", {stream.kind for stream in data.streams})

    def test_probe_stage_fails_closed_when_bundled_ffprobe_is_missing(self) -> None:
        powershell = _pwsh()
        if powershell is None:
            self.skipTest("PowerShell is not available")

        with tempfile.TemporaryDirectory(prefix="mediapipeline-stage-missing-tool-") as tmp:
            temp_root = Path(tmp)
            temp_engine = temp_root / "engine"
            shutil.copytree(PROJECT_ROOT / "engine", temp_engine)
            env = os.environ.copy()
            env.pop("MEDIAPIPELINE_ALLOW_SYSTEM_STAGE_TOOLS", None)
            completed = subprocess.run(
                [
                    powershell,
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(temp_engine / "entrypoint.ps1"),
                    "-Stage",
                    "probe",
                    "-PayloadJson",
                    json.dumps(
                        {
                            "schema_version": "v1",
                            "stage": "probe",
                            "payload": {"scratch_path": str(temp_root / "missing.mkv")},
                        }
                    ),
                ],
                cwd=temp_root,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
                env=env,
            )

        self.assertNotEqual(completed.returncode, 0)
        result = StageResult.model_validate(json.loads(completed.stdout))
        self.assertFalse(result.ok)
        self.assertEqual(result.error.code if result.error else "", "stage.tool_missing")
        self.assertIn(
            "Set MEDIAPIPELINE_ALLOW_SYSTEM_STAGE_TOOLS=1",
            result.error.message if result.error else "",
        )


if __name__ == "__main__":
    unittest.main()
