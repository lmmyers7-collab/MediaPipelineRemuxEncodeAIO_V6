from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.core.config.load import serialize_psd1_document
from mediapipeline.core.kernel.models import ResolvedPaths
from mediapipeline.desktop.application.network_lifecycle_provider import NetworkLifecycleProviderMixin
from mediapipeline.desktop.network.processing_policy import (
    COORDINATOR_PROCESSING_POLICY_KEY,
    COORDINATOR_PROCESSING_POLICY_SCHEMA_VERSION,
    build_coordinator_processing_policy,
    build_worker_effective_config,
)
from mediapipeline.desktop.network.encode_config_snapshot import snapshot_encode_config


def _coordinator_config(root: Path) -> dict[str, object]:
    return {
        "SourceMovies": str(root / "Coordinator" / "Movies"),
        "SourceTV": str(root / "Coordinator" / "TV"),
        "Outsource": str(root / "Coordinator" / "Out"),
        "VideoCodec": "h264_nvenc",
        "VideoPreset": "p7",
        "VideoQuality": 24,
        "OutputContainer": "mkv",
        "RoutingProfile": "plex_direct_stream",
        "RouteThresholdMode": "compatibility_advisory",
        "Route1080pMaxVideoBitrateMbps": 18,
        "AllowH264RemuxIfPlexCompatible": True,
        "H264RemuxMaxBitrateMbps": 35,
        "H264RemuxMaxHeight": 1080,
        "SizeGuardMode": "advisory",
        "MaxEncodeGrowthPercent": 5,
        "CompatibilityEncodeGrowthPercent": 15,
        "EncodeTuningPreset": "balanced_nvenc",
        "EncodeLadder": "auto",
        "AudioPassthroughProfile": "plex_balanced",
        "AudioTranscodeCodec": "eac3",
        "AudioTranscodeBitrate": "640k",
        "AudioDownmixMode": "max_channels",
        "AudioMaxChannels": 6,
        "AllowNoAudio": False,
        "SubKeepLanguages": ["eng"],
        "ConvertTx3gToSrt": True,
        "DropTx3gAfterConversion": False,
        "CreateExternalTx3gSrtSidecars": False,
        "LibraryProfiles": [
            {
                "id": "movies",
                "name": "Movies",
                "source_path": str(root / "Coordinator" / "Movies"),
                "output_path": str(root / "Coordinator" / "Out" / "Movies"),
                "overrides": {
                    "editor": {
                        "RoutingProfile": "movie_archive",
                        "Route1080pMaxVideoBitrateMbps": 30,
                        "VideoCodec": "libx265",
                        "OutputContainer": "mp4",
                    },
                    "video": {
                        "VideoQuality": 20,
                    },
                    "audio": {
                        "AudioTranscodeCodec": "aac",
                        "AudioMaxChannels": 2,
                    },
                    "subtitles": {
                        "ConvertTx3gToSrt": False,
                    },
                },
            }
        ],
    }


class NetworkCoordinatorProcessingPolicyPhaseETests(unittest.TestCase):
    def test_coordinator_policy_is_library_resolved_and_hardware_neutral(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_path = root / "Coordinator" / "Movies" / "Feature.mkv"
            record = SimpleNamespace(
                source_path=str(source_path),
                library_id="movies",
                relative_path="Feature.mkv",
            )

            policy = build_coordinator_processing_policy(_coordinator_config(root), record)

        self.assertEqual(policy["policy_schema_version"], COORDINATOR_PROCESSING_POLICY_SCHEMA_VERSION)
        self.assertEqual(policy["library_id"], "movies")
        self.assertEqual(policy["relative_path"], "Feature.mkv")
        self.assertEqual(policy["target_codec_family"], "hevc")
        self.assertNotEqual(policy.get("target_codec_family"), "libx265")
        self.assertEqual(policy["quality_tier"], "high")
        self.assertEqual(policy["output_container"], "mp4")
        self.assertEqual(policy["routing_profile"], "movie_archive")
        self.assertEqual(policy["route_thresholds"]["Route1080pMaxVideoBitrateMbps"], 30)
        self.assertEqual(policy["audio_policy"]["AudioTranscodeCodec"], "aac")
        self.assertEqual(policy["audio_policy"]["AudioMaxChannels"], 2)
        self.assertIs(policy["subtitle_policy"]["ConvertTx3gToSrt"], False)

    def test_worker_effective_config_maps_family_quality_and_policy_fields(self) -> None:
        worker_config = {
            "VideoCodec": "h264_nvenc",
            "VideoPreset": "p7",
            "VideoQuality": 28,
            "OutputContainer": "mp4",
            "RoutingProfile": "worker_local",
            "AudioTranscodeCodec": "ac3",
            "ConvertTx3gToSrt": False,
            "WorkerEncoderMap": '{"hevc": "hevc_nvenc"}',
            "WorkerHonorCoordinatorPolicy": True,
        }
        policy = {
            "policy_schema_version": COORDINATOR_PROCESSING_POLICY_SCHEMA_VERSION,
            "target_codec_family": "hevc",
            "quality_tier": "standard",
            "output_container": "mkv",
            "routing_profile": "movie_archive",
            "route_thresholds": {"Route1080pMaxVideoBitrateMbps": 22},
            "size_guards": {"SizeGuardMode": "strict"},
            "audio_policy": {"AudioTranscodeCodec": "eac3"},
            "subtitle_policy": {"ConvertTx3gToSrt": True},
            "coordinator_literal_encoder": "libx265",
        }

        effective, evidence = build_worker_effective_config(
            worker_config,
            {COORDINATOR_PROCESSING_POLICY_KEY: policy},
        )

        self.assertEqual(evidence["status"], "applied")
        self.assertEqual(evidence["target_codec_family"], "hevc")
        self.assertEqual(effective["VideoCodec"], "hevc_nvenc")
        self.assertEqual(effective["VideoPreset"], "p7")
        self.assertEqual(effective["VideoQuality"], 21)
        self.assertEqual(effective["OutputContainer"], "mkv")
        self.assertEqual(effective["RoutingProfile"], "movie_archive")
        self.assertEqual(effective["Route1080pMaxVideoBitrateMbps"], 22)
        self.assertEqual(effective["SizeGuardMode"], "strict")
        self.assertEqual(effective["AudioTranscodeCodec"], "eac3")
        self.assertIs(effective["ConvertTx3gToSrt"], True)
        self.assertNotEqual(effective["VideoCodec"], policy["coordinator_literal_encoder"])

    def test_worker_encoder_map_invalid_entry_falls_back_to_cpu_with_warning(self) -> None:
        worker_config = {
            "WorkerEncoderMap": '{"hevc": "definitely_not_an_encoder"}',
            "WorkerHonorCoordinatorPolicy": True,
        }
        policy = {
            "policy_schema_version": COORDINATOR_PROCESSING_POLICY_SCHEMA_VERSION,
            "target_codec_family": "hevc",
            "quality_tier": "standard",
        }

        with self.assertLogs("mediapipeline.desktop.network.processing_policy", level="WARNING") as logs:
            effective, evidence = build_worker_effective_config(
                worker_config,
                {COORDINATOR_PROCESSING_POLICY_KEY: policy},
            )

        self.assertEqual(effective["VideoCodec"], "libx265")
        self.assertEqual(effective["VideoQuality"], 22)
        self.assertEqual(evidence["encoder_source"], "cpu_fallback")
        self.assertIn("falling back to CPU encoder libx265", "\n".join(logs.output))

    def test_snapshot_encode_config_attaches_coordinator_policy_for_record(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            record = SimpleNamespace(
                source_path=str(root / "Coordinator" / "Movies" / "Feature.mkv"),
                library_id="movies",
                relative_path="Feature.mkv",
            )

            snapshot = snapshot_encode_config(_coordinator_config(root), worker_name="GamingPC", record=record)

        self.assertIn(COORDINATOR_PROCESSING_POLICY_KEY, snapshot)
        policy = snapshot[COORDINATOR_PROCESSING_POLICY_KEY]
        self.assertEqual(policy["policy_schema_version"], COORDINATOR_PROCESSING_POLICY_SCHEMA_VERSION)
        self.assertEqual(policy["target_codec_family"], "hevc")
        self.assertEqual(policy["quality_tier"], "high")
        self.assertNotEqual(policy.get("target_codec_family"), policy.get("coordinator_literal_encoder"))

    def test_quality_tiers_translate_to_cpu_and_hardware_values(self) -> None:
        policy = {
            "policy_schema_version": COORDINATOR_PROCESSING_POLICY_SCHEMA_VERSION,
            "target_codec_family": "hevc",
            "quality_tier": "very_high",
        }
        hardware_effective, hardware_evidence = build_worker_effective_config(
            {"WorkerHonorCoordinatorPolicy": True, "WorkerEncoderMap": '{"hevc":"hevc_nvenc"}'},
            {COORDINATOR_PROCESSING_POLICY_KEY: policy},
        )
        cpu_effective, cpu_evidence = build_worker_effective_config(
            {"WorkerHonorCoordinatorPolicy": True, "WorkerEncoderMap": ""},
            {COORDINATOR_PROCESSING_POLICY_KEY: {**policy, "quality_tier": "compact"}},
        )

        self.assertEqual(hardware_effective["VideoCodec"], "hevc_nvenc")
        self.assertEqual(hardware_effective["VideoQuality"], 17)
        self.assertEqual(hardware_evidence["quality_tier"], "very_high")
        self.assertEqual(cpu_effective["VideoCodec"], "libx265")
        self.assertEqual(cpu_effective["VideoQuality"], 26)
        self.assertEqual(cpu_evidence["quality_tier"], "compact")


class _FakeStartService:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        self.prepared: list[object] = []

    def prepare_pipeline_runtime_for_launch(self, resolved: object) -> None:
        self.prepared.append(resolved)

    def prepare_pipeline_control_flags_for_launch(self, resolved: object) -> None:
        self.prepared.append(resolved)

    def start_pipeline(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        return SimpleNamespace(pid=12345)


class _NetworkLifecycleHarness(NetworkLifecycleProviderMixin):
    def __init__(self, service: _FakeStartService) -> None:
        self.service = service
        self.released = False

    def _acquire_process_launch_lock(self, _label: str) -> tuple[object, str]:
        return object(), ""

    def _release_process_launch_lock(self, _lock: object) -> None:
        self.released = True

    def _active_work_block_message(self, _resolved: object, _label: str) -> str:
        return ""


def _resolved(root: Path, config: dict[str, object]) -> ResolvedPaths:
    config_path = root / "MediaPipeline_config.psd1"
    config_path.write_text(serialize_psd1_document(config), encoding="utf-8")
    return ResolvedPaths(
        app_root=root,
        workspace_root=root,
        pipeline_path=root / "MediaPipeline.ps1",
        config_path=config_path,
        audit_script_path=root / "Audit.ps1",
        rerun_script_path=root / "Rerun.ps1",
        powershell_host="pwsh",
        state_root=root / "State",
        local_base=root / "LocalBase",
        config_data=dict(config),
    )


class NetworkWorkerPolicyLaunchPhaseETests(unittest.TestCase):
    def test_network_worker_policy_flag_off_keeps_original_resolved_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            resolved = _resolved(
                root,
                {
                    "WorkerHonorCoordinatorPolicy": False,
                    "WorkerEncoderMap": '{"hevc": "hevc_nvenc"}',
                    "VideoCodec": "h264_nvenc",
                },
            )
            service = _FakeStartService()
            harness = _NetworkLifecycleHarness(service)
            job = SimpleNamespace(
                job_id="job-flag-off",
                record=SimpleNamespace(source_path=str(root / "Movie.mkv")),
                encode_config={
                    COORDINATOR_PROCESSING_POLICY_KEY: {
                        "policy_schema_version": COORDINATOR_PROCESSING_POLICY_SCHEMA_VERSION,
                        "target_codec_family": "hevc",
                        "quality_tier": "standard",
                    }
                },
            )

            harness._start_network_claimed_job(SimpleNamespace(resolved=resolved), SimpleNamespace(), job)

        self.assertTrue(harness.released)
        self.assertEqual(service.calls[0]["resolved"], resolved)
        self.assertEqual(service.calls[0]["resolved"].config_path, resolved.config_path)  # type: ignore[union-attr]

    def test_network_worker_policy_flag_on_materializes_per_job_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            resolved = _resolved(
                root,
                {
                    "WorkerHonorCoordinatorPolicy": True,
                    "WorkerEncoderMap": '{"hevc": "hevc_nvenc"}',
                    "VideoCodec": "h264_nvenc",
                    "VideoPreset": "p7",
                    "VideoQuality": 28,
                    "OutputContainer": "mp4",
                    "RoutingProfile": "worker_local",
                },
            )
            service = _FakeStartService()
            harness = _NetworkLifecycleHarness(service)
            job = SimpleNamespace(
                job_id="job-flag-on",
                record=SimpleNamespace(source_path=str(root / "Movie.mkv")),
                encode_config={
                    COORDINATOR_PROCESSING_POLICY_KEY: {
                        "policy_schema_version": COORDINATOR_PROCESSING_POLICY_SCHEMA_VERSION,
                        "target_codec_family": "hevc",
                        "quality_tier": "standard",
                        "output_container": "mkv",
                        "routing_profile": "movie_archive",
                    }
                },
            )

            harness._start_network_claimed_job(SimpleNamespace(resolved=resolved), SimpleNamespace(), job)
            launched_resolved = service.calls[0]["resolved"]
            self.assertNotEqual(launched_resolved.config_path, resolved.config_path)  # type: ignore[union-attr]
            self.assertTrue(launched_resolved.config_path.is_file())  # type: ignore[union-attr]
            self.assertEqual(launched_resolved.config_data["VideoCodec"], "hevc_nvenc")  # type: ignore[union-attr]
            self.assertEqual(launched_resolved.config_data["VideoQuality"], 21)  # type: ignore[union-attr]
            self.assertEqual(launched_resolved.config_data["OutputContainer"], "mkv")  # type: ignore[union-attr]
            text = launched_resolved.config_path.read_text(encoding="utf-8")  # type: ignore[union-attr]
            self.assertIn("VideoCodec = 'hevc_nvenc'", text)
            self.assertIn("OutputContainer = 'mkv'", text)


if __name__ == "__main__":
    unittest.main()
