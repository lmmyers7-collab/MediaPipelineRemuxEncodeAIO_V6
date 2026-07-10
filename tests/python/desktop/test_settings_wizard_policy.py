from __future__ import annotations

import sys
import tempfile
import unittest
import logging
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from mediapipeline.tools.paths import find_repo_root


REPO_ROOT = find_repo_root(Path(__file__))
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from mediapipeline.core.config.settings_wizard import (  # noqa: E402
    probe_ffmpeg_hardware,
    preview_settings_wizard,
    save_settings_wizard,
    settings_wizard_defaults,
    tool_candidates,
    validate_ffmpeg_tools,
    validate_wizard_paths,
    validate_wizard_payload,
    validate_worker_settings,
    wizard_changes,
)
from mediapipeline.core.config.load import serialize_psd1_document  # noqa: E402
from mediapipeline.core.config.validation import validate_config_values  # noqa: E402
from mediapipeline.contracts.config import Config  # noqa: E402
from mediapipeline.desktop.application import MediaPipelineApplicationFacade  # noqa: E402
from mediapipeline.desktop.application.dto_commands import CommandResult  # noqa: E402
from mediapipeline.desktop.models import ConfigSaveResult, ResolvedPaths  # noqa: E402


def _path_key(path: Path) -> str:
    return str(path).rstrip("\\/").casefold()


def _path_within_root(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=False))
        return True
    except ValueError:
        return False


def _resolved(root: Path) -> ResolvedPaths:
    return ResolvedPaths(
        app_root=root / "DesktopApp",
        workspace_root=root,
        pipeline_path=root / "Pipeline" / "MediaPipeline.ps1",
        config_path=root / "Pipeline" / "MediaPipeline_config.psd1",
        audit_script_path=root / "Pipeline" / "Audit-MediaLibrary.ps1",
        rerun_script_path=root / "Pipeline" / "Invoke-RerunCsv.ps1",
        powershell_host="pwsh.exe",
        local_base=root / "LocalBase",
        state_root=root / "State",
        source_movies=root / "SourceMovies",
        source_tv=root / "SourceTV",
        pending_push_path=root / "PendingServerPush",
        queue_snapshot_path=root / "State" / "Queue" / "snapshot.json",
        active_jobs_path=root / "State" / "ActiveJobs",
        failed_reports_path=root / "State" / "Failed" / "Reports",
        failed_markers_path=root / "State" / "Failed" / "Markers",
        audit_reports_path=root / "AuditReports",
        completed_manifest_path=root / "State" / "Completed" / "completed_jobs.jsonl",
    )


def _first_run_wizard(root: Path) -> dict[str, object]:
    movies = root / "Encode" / "Movies"
    tv = root / "Encode" / "TV"
    movies.mkdir(parents=True, exist_ok=True)
    tv.mkdir(parents=True, exist_ok=True)
    output = root / "Outsource"
    return {
        "mode": "first_run",
        "output_container": "mkv",
        "libraries": [
            {
                "id": "movies",
                "name": "Movies",
                "designation": "movie",
                "media_kind": "movie",
                "default_source_role": "source_movies",
                "source_path": str(movies),
                "output_path": str(output / "Movies"),
                "enabled": True,
            },
            {
                "id": "tv",
                "name": "TV",
                "designation": "tv",
                "media_kind": "tv",
                "default_source_role": "source_tv",
                "source_path": str(tv),
                "output_path": str(output / "TV"),
                "enabled": True,
            },
        ],
        "output": {"root": str(output), "publish_mode": "staged_pending", "existing_policy": "skip_existing"},
        "scratch": {"path": str(root / "Scratch")},
        "hardware": {"strategy": "remux_when_possible", "preferred_codec": "hevc_nvenc"},
        "audio": {"transcode_codec": "eac3"},
        "subtitles": {"languages": ["eng", "en"]},
        "workers": {"max_parallel_encodes": 1, "parallel_encode_mode": "single"},
        "safety": {
            "integrity_check": True,
            "file_stability_checks": True,
            "pending_publish": True,
            "skip_already_processed": True,
            "retry_limit": 3,
            "danger_ack": [],
        },
        "min_free_space_gb": 50,
        "outsource_min_free_space_gb": 50,
    }


class WizardFirstRunService:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.logger = logging.getLogger("test_settings_wizard_policy")
        self.saved_config_calls: list[dict[str, object]] = []
        self.state: dict[str, object] = {}

    def load_config_data(self, config_path: Path, powershell_host: str | None) -> dict[str, object]:
        _ = powershell_host
        if config_path.name != "MediaPipeline_config_template.psd1":
            return {}
        return Config().model_dump(mode="json")

    def validate_config_values(self, values: dict[str, object]) -> tuple[list[str], list[str]]:
        return validate_config_values(values, normalized_path_key=_path_key, path_within_root=_path_within_root)

    def serialize_psd1_document(self, values: dict[str, object]) -> str:
        return serialize_psd1_document(values)

    def save_config_document(
        self,
        output_path: Path,
        document_text: str,
        create_backup: bool,
        *,
        config_values: dict[str, object] | None = None,
        powershell_host: str | None = None,
    ) -> ConfigSaveResult:
        self.saved_config_calls.append(
            {
                "output_path": output_path,
                "document_text": document_text,
                "create_backup": create_backup,
                "config_values": dict(config_values or {}),
                "powershell_host": powershell_host,
            }
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(document_text, encoding="utf-8")
        return ConfigSaveResult(output_path=output_path, backup_path=None)

    def load_app_state(self) -> dict[str, object]:
        return dict(self.state)

    def save_app_state(self, state: dict[str, object]) -> None:
        self.state = dict(state)


class SettingsWizardPolicyTests(unittest.TestCase):
    def test_validate_wizard_paths_reports_malformed_library_rows(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            source = root / "Movies"
            source.mkdir()
            result = validate_wizard_paths(
                {
                    "libraries": [
                        "not-a-library-object",
                        {"name": "Movies", "source_path": str(source), "output_path": str(root / "Output")},
                    ],
                    "output": {"root": str(root / "Output")},
                    "scratch": {"path": str(root / "Scratch")},
                }
            )

        self.assertFalse(result["ok"])
        self.assertIn("Wizard library row 1 must be a JSON object.", result["errors"])
        self.assertTrue(any(row["label"] == "Library Movies" for row in result["rows"]))
        self.assertTrue(any(row["target"] == "library:2:source_path" for row in result["rows"]))

    def test_validate_wizard_payload_reports_malformed_worker_settings(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            result = validate_wizard_payload(
                {
                    "libraries": [],
                    "output": {"root": str(root / "Output")},
                    "scratch": {"path": str(root / "Scratch")},
                    "workers": ["not-a-worker-object"],
                }
            )

        self.assertFalse(result["ok"])
        self.assertIn("Wizard workers must be a JSON object.", result["errors"])
        self.assertFalse(result["worker_validation"]["ok"])

    def test_validate_wizard_payload_warns_for_unacknowledged_reprocess_all(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            result = validate_wizard_payload(
                {
                    "libraries": [],
                    "output": {"root": str(root / "Output"), "existing_policy": "reprocess_all_once"},
                    "scratch": {"path": str(root / "Scratch")},
                    "workers": {"max_parallel_encodes": 1, "parallel_encode_mode": "single"},
                    "safety": {"danger_ack": []},
                }
            )

        self.assertTrue(result["ok"])
        self.assertIn(
            "ReprocessAll is enabled; acknowledge it on the Save step before relying on this config.",
            result["warnings"],
        )

    def test_validate_wizard_payload_reports_non_object_payload(self) -> None:
        result = validate_wizard_payload(["not-a-wizard-object"])

        self.assertFalse(result["ok"])
        self.assertIn("Settings Wizard payload must be a JSON object.", result["errors"])
        self.assertFalse(result["path_validation"]["ok"])

    def test_validate_worker_settings_reports_non_object_payload(self) -> None:
        result = validate_worker_settings(["not-a-worker-object"])

        self.assertFalse(result["ok"])
        self.assertEqual(result["errors"], ["Wizard workers must be a JSON object."])
        self.assertEqual(result["max_parallel_encodes"], 1)
        self.assertEqual(result["parallel_encode_mode"], "single")

    def test_wizard_changes_ignores_non_array_libraries_without_crashing(self) -> None:
        changes = wizard_changes(
            {
                "libraries": 42,
                "output": {"root": r"C:\Processed"},
                "scratch": {"path": r"C:\Scratch"},
            }
        )

        self.assertEqual(changes["Outsource"], r"C:\Processed")
        self.assertEqual(changes["LocalBase"], r"C:\Scratch")
        self.assertNotIn("SourceMovies", changes)
        self.assertNotIn("SourceTV", changes)

    def test_validate_ffmpeg_tools_reports_missing_or_non_file_paths(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            result = validate_ffmpeg_tools(
                _resolved(root),
                {
                    "wizard": {
                        "tools": {
                            "ffmpeg_path": str(root / "missing-ffmpeg.exe"),
                            "ffprobe_path": str(root),
                        }
                    }
                },
            )

        self.assertFalse(result["ok"])
        self.assertIn("FFmpeg: tool path not found", result["errors"])
        self.assertIn("ffprobe: tool path is not a file", result["errors"])
        self.assertFalse(result["blocks_unrelated_settings_save"])

    def test_validate_ffmpeg_tools_accepts_file_paths(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            ffmpeg = root / "ffmpeg.exe"
            ffprobe = root / "ffprobe.exe"
            ffmpeg.write_text("fake", encoding="utf-8")
            ffprobe.write_text("fake", encoding="utf-8")
            result = validate_ffmpeg_tools(
                _resolved(root),
                {"wizard": {"tools": {"ffmpeg_path": str(ffmpeg), "ffprobe_path": str(ffprobe)}}},
            )

        self.assertTrue(result["ok"])
        self.assertEqual(result["errors"], [])
        self.assertTrue(result["ffmpeg"]["ok"])
        self.assertTrue(result["ffprobe"]["ok"])

    def test_validate_ffmpeg_tools_accepts_quoted_file_paths(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            ffmpeg = root / "ffmpeg with spaces.exe"
            ffprobe = root / "ffprobe with spaces.exe"
            ffmpeg.write_text("fake", encoding="utf-8")
            ffprobe.write_text("fake", encoding="utf-8")
            result = validate_ffmpeg_tools(
                _resolved(root),
                {"wizard": {"tools": {"ffmpeg_path": f'"{ffmpeg}"', "ffprobe_path": f'"{ffprobe}"'}}},
            )

        self.assertTrue(result["ok"])
        self.assertEqual(result["ffmpeg"]["path"], str(ffmpeg))
        self.assertEqual(result["ffprobe"]["path"], str(ffprobe))
        self.assertEqual(result["errors"], [])

    def test_probe_ffmpeg_hardware_enumerates_configured_ffmpeg_encoders(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            ffmpeg = root / "ffmpeg.exe"
            ffmpeg.write_text("fake", encoding="utf-8")
            encoder_output = "\n".join(
                [
                    " V..... h264_nvenc           NVIDIA NVENC H.264 encoder (codec h264)",
                    " V..... hevc_nvenc           NVIDIA NVENC hevc encoder (codec hevc)",
                    " V..... av1_nvenc            NVIDIA NVENC av1 encoder (codec av1)",
                    " V..... hevc_qsv             Intel Quick Sync Video HEVC encoder (codec hevc)",
                    " V..... hevc_amf             AMD AMF HEVC encoder (codec hevc)",
                    " V..... libx265              libx265 H.265 / HEVC (codec hevc)",
                    " V..... libaom-av1           libaom AV1 (codec av1)",
                ]
            )
            with patch(
                "mediapipeline.core.config.settings_wizard._run_ffmpeg_encoder_listing",
                create=True,
                return_value=SimpleNamespace(returncode=0, stdout=encoder_output, stderr=""),
            ):
                result = probe_ffmpeg_hardware(_resolved(root), {"wizard": {"tools": {"ffmpeg_path": str(ffmpeg)}}})

        self.assertTrue(result["ok"], "\n".join(result["errors"]))
        self.assertEqual(
            result["detected_encoders"],
            ["h264_nvenc", "hevc_nvenc", "av1_nvenc", "hevc_qsv", "hevc_amf", "libx265", "libaom-av1"],
        )
        self.assertEqual(result["nvenc_encoders"], ["h264_nvenc", "hevc_nvenc", "av1_nvenc"])
        self.assertEqual(result["cpu_fallback_encoders"], ["libx265", "libaom-av1"])
        self.assertEqual(result["capability_facts_scope"], "video_encoder_names_only")
        self.assertEqual(result["capability_facts"]["supported_video_codecs"], ["av1", "h264", "h265", "hevc"])
        self.assertEqual(
            result["capability_facts"]["supported_encoder_backends"],
            ["amf", "copy", "libaom", "nvenc", "qsv", "x265"],
        )
        backend_rows = {row["backend"]: row for row in result["encoder_backend_rows"]}
        self.assertEqual(backend_rows["nvenc"]["encoders"], ["h264_nvenc", "hevc_nvenc", "av1_nvenc"])
        self.assertEqual(backend_rows["qsv"]["encoders"], ["hevc_qsv"])
        self.assertEqual(backend_rows["amf"]["encoders"], ["hevc_amf"])
        self.assertEqual(backend_rows["libaom"]["encoders"], ["libaom-av1"])
        warning_text = "\n".join(result["warnings"])
        self.assertIn("normal queue evidence", warning_text)
        self.assertIn("does not run a real encode", warning_text)

    def test_probe_ffmpeg_hardware_blocks_missing_configured_ffmpeg(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            result = probe_ffmpeg_hardware(
                _resolved(root),
                {"wizard": {"tools": {"ffmpeg_path": str(root / "missing-ffmpeg.exe")}}},
            )

        self.assertFalse(result["ok"])
        self.assertIn("FFmpeg:", "\n".join(result["errors"]))

    def test_tool_candidates_find_promoted_ops_pipeline_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            bundle_bin = root / "ops" / "pipeline" / "tools" / "ffmpeg" / "bin"
            bundle_bin.mkdir(parents=True)
            ffmpeg = bundle_bin / "ffmpeg.exe"
            ffprobe = bundle_bin / "ffprobe.exe"
            ffmpeg.write_text("fake", encoding="utf-8")
            ffprobe.write_text("fake", encoding="utf-8")
            resolved = _resolved(root)
            resolved.pipeline_path = root / "ops" / "pipeline" / "entrypoints" / "MediaPipeline.ps1"

            candidates = tool_candidates(resolved)
            defaults = settings_wizard_defaults(resolved, service=None)

        self.assertEqual(candidates["ffmpeg"][0]["path"], str(ffmpeg))
        self.assertEqual(candidates["ffprobe"][0]["path"], str(ffprobe))
        self.assertTrue(candidates["ffmpeg"][0]["exists"])
        self.assertTrue(candidates["ffprobe"][0]["exists"])
        self.assertEqual(defaults["wizard"]["tools"]["ffmpeg_path"], str(ffmpeg))
        self.assertEqual(defaults["wizard"]["tools"]["ffprobe_path"], str(ffprobe))

    def test_validate_wizard_paths_accepts_quoted_windows_explorer_paths(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            source = root / "Movies With Spaces"
            source.mkdir()
            output = root / "Processed Movies"
            scratch = root / "Local Scratch"
            result = validate_wizard_paths(
                {
                    "libraries": [{"name": "Movies", "source_path": f'"{source}"', "output_path": f'"{output}"'}],
                    "output": {"root": f'"{output}"'},
                    "scratch": {"path": f'"{scratch}"'},
                }
            )

        self.assertTrue(result["ok"])
        self.assertNotIn('"', "\n".join(row["path"] for row in result["rows"]))
        self.assertTrue(any(row["path"] == str(source) and row["status"] == "ready" for row in result["rows"]))

    def test_validate_wizard_paths_marks_missing_runtime_paths_as_will_create(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            source = root / "Movies"
            source.mkdir()
            output = root / "Processed"
            scratch = root / "Scratch"

            result = validate_wizard_paths(
                {
                    "libraries": [{"name": "Movies", "source_path": str(source), "output_path": str(output / "Movies")}],
                    "output": {"root": str(output)},
                    "scratch": {"path": str(scratch)},
                }
            )

        self.assertTrue(result["ok"], "\n".join(result["errors"]))
        self.assertFalse(output.exists())
        self.assertFalse(scratch.exists())
        warning_text = "\n".join(result["warnings"])
        self.assertIn("will be created during first-run save", warning_text)
        runtime_rows = {row["label"]: row for row in result["rows"] if row["label"] in {"Final output", "Scratch / LocalBase"}}
        self.assertEqual(runtime_rows["Final output"]["status"], "will_create")
        self.assertTrue(runtime_rows["Final output"]["will_create"])
        self.assertEqual(runtime_rows["Scratch / LocalBase"]["status"], "will_create")
        self.assertTrue(runtime_rows["Scratch / LocalBase"]["will_create"])

    def test_validate_wizard_paths_blocks_final_output_matching_source(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            source = root / "Movies"
            source.mkdir()
            result = validate_wizard_paths(
                {
                    "libraries": [{"name": "Movies", "source_path": str(source)}],
                    "output": {"root": str(source)},
                    "scratch": {"path": str(root / "Scratch")},
                }
            )

        self.assertFalse(result["ok"])
        self.assertIn("Final output root cannot be the same folder as enabled source library Movies.", result["errors"])

    def test_validate_wizard_paths_blocks_library_output_matching_any_enabled_source(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            movies = root / "Movies"
            tv = root / "TV"
            movies.mkdir()
            tv.mkdir()
            result = validate_wizard_paths(
                {
                    "libraries": [
                        {"name": "Movies", "source_path": str(movies), "output_path": str(tv)},
                        {"name": "TV", "source_path": str(tv), "output_path": str(root / "OutTV")},
                    ],
                    "output": {"root": str(root / "Out")},
                    "scratch": {"path": str(root / "Scratch")},
                }
            )

        self.assertFalse(result["ok"])
        self.assertIn("Library Movies output cannot be the same folder as enabled source library TV.", result["errors"])

    def test_validate_wizard_paths_blocks_promotion_destination_matching_source(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            source = root / "Movies"
            source.mkdir()
            result = validate_wizard_paths(
                {
                    "libraries": [
                        {
                            "name": "Movies",
                            "source_path": str(source),
                            "output_path": str(root / "Out"),
                            "promotion_enabled": True,
                            "promotion_destination": str(source),
                        }
                    ],
                    "output": {"root": str(root / "Out")},
                    "scratch": {"path": str(root / "Scratch")},
                }
            )

        self.assertFalse(result["ok"])
        self.assertIn(
            "Library Movies promotion destination cannot be the same folder as enabled source library Movies.",
            result["errors"],
        )

    def test_wizard_changes_strips_wrapping_quotes_from_paths(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            source = root / "Movies"
            output = root / "Processed"
            scratch = root / "Scratch"
            changes = wizard_changes(
                {
                    "libraries": [
                        {
                            "name": "Movies",
                            "source_path": f'"{source}"',
                            "output_path": f'"{output}"',
                            "default_source_role": "source_movies",
                        }
                    ],
                    "output": {"root": f'"{output}"'},
                    "scratch": {"path": f'"{scratch}"'},
                }
            )

        self.assertEqual(changes["SourceMovies"], str(source))
        self.assertEqual(changes["Outsource"], str(output))
        self.assertEqual(changes["LocalBase"], str(scratch))
        self.assertEqual(changes["LibraryProfiles"][0]["source_path"], str(source))

    def test_wizard_changes_preserves_final_output_root_with_library_subfolders(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            wizard = _first_run_wizard(root)

            changes = wizard_changes(wizard)

        self.assertEqual(changes["Outsource"], str(root / "Outsource"))
        profiles = {profile["id"]: profile for profile in changes["LibraryProfiles"]}
        self.assertEqual(profiles["movies"]["output_path"], str(root / "Outsource" / "Movies"))
        self.assertEqual(profiles["tv"]["output_path"], str(root / "Outsource" / "TV"))

    def test_preview_settings_wizard_summary_uses_guided_setup_phases(self) -> None:
        class Facade:
            def preview_settings_patch(self, _resolved: ResolvedPaths, request: dict[str, object]) -> CommandResult:
                changes = request["changes"]
                return CommandResult(
                    command="settings.preview_patch",
                    ok=True,
                    message="preview ok",
                    severity="info",
                    data={"changed_keys": sorted(changes)},
                )

        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            source = root / "Movies"
            source.mkdir()
            request = {
                "wizard": {
                    "mode": "first_run",
                    "output_container": "mkv",
                    "libraries": [{"name": "Movies", "source_path": str(source), "output_path": str(root / "Output")}],
                    "output": {"root": str(root / "Output"), "existing_policy": "skip_existing"},
                    "scratch": {"path": str(root / "Scratch")},
                    "workers": {"max_parallel_encodes": 1, "parallel_encode_mode": "single"},
                    "safety": {},
                }
            }
            result = preview_settings_wizard(Facade(), _resolved(root), request)

        categories = result.data["wizard"]["summary"]["categories"]
        self.assertEqual(
            [row["category"] for row in categories],
            ["Start", "Paths", "Toolchain", "Policy", "Review & Save"],
        )
        self.assertEqual(categories[-1]["status"], "warning")
        self.assertFalse(result.data["wizard"]["touches_media"])

    def test_preview_settings_wizard_review_phase_includes_backend_blockers(self) -> None:
        class Facade:
            def preview_settings_patch(self, _resolved: ResolvedPaths, request: dict[str, object]) -> CommandResult:
                changes = request["changes"]
                return CommandResult(
                    command="settings.preview_patch",
                    ok=False,
                    message="preview blocked",
                    severity="error",
                    errors=["Backend preview blocker"],
                    data={"changed_keys": sorted(changes)},
                )

        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            request = {"wizard": _first_run_wizard(root)}
            result = preview_settings_wizard(Facade(), _resolved(root), request)

        categories = result.data["wizard"]["summary"]["categories"]
        self.assertFalse(result.ok)
        self.assertEqual(categories[-1]["status"], "blocked")
        self.assertIn("Backend preview blocker", result.data["wizard"]["errors"])

    def test_preview_settings_wizard_first_run_uses_template_base_config(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            template = root / "ops" / "pipeline" / "config" / "MediaPipeline_config_template.psd1"
            template.parent.mkdir(parents=True)
            template.write_text("@{}\n", encoding="utf-8")
            service = WizardFirstRunService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.config_path = root / "AppData" / "MediaPipeline_config.psd1"
            resolved.config_data = {}
            result = preview_settings_wizard(facade, resolved, {"wizard": _first_run_wizard(root)})

        self.assertTrue(result.ok, "\n".join(result.errors))
        self.assertGreaterEqual(result.data["base_key_count"], 80)
        self.assertGreaterEqual(result.data["preview_key_count"], 80)
        self.assertEqual(result.data["wizard"]["candidate"]["Outsource"], str(root / "Outsource"))
        self.assertNotIn("MergeThresholdMs must be an integer.", "\n".join(result.errors))

    def test_save_settings_wizard_first_run_creates_missing_config_from_template_base(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            template = root / "ops" / "pipeline" / "config" / "MediaPipeline_config_template.psd1"
            template.parent.mkdir(parents=True)
            template.write_text("@{}\n", encoding="utf-8")
            service = WizardFirstRunService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.config_path = root / "AppData" / "MediaPipeline_config.psd1"
            resolved.config_data = {}
            wizard = _first_run_wizard(root)
            output_root = root / "Outsource"
            movie_output = output_root / "Movies"
            tv_output = output_root / "TV"
            scratch = root / "Scratch"

            self.assertFalse(output_root.exists())
            self.assertFalse(movie_output.exists())
            self.assertFalse(tv_output.exists())
            self.assertFalse(scratch.exists())

            preview = preview_settings_wizard(facade, resolved, {"wizard": wizard})
            missing_confirmation = save_settings_wizard(facade, resolved, {"wizard": wizard, "confirm_save": True})
            result = save_settings_wizard(
                facade,
                resolved,
                {
                    "wizard": wizard,
                    "confirm_save": True,
                    "review_confirmation": preview.data["review_confirmation"],
                },
            )

            self.assertFalse(missing_confirmation.ok)
            self.assertIn("review_confirmation", missing_confirmation.message)
            self.assertTrue(result.ok, "\n".join(result.errors))
            self.assertTrue(resolved.config_path.exists())
            self.assertTrue(output_root.is_dir())
            self.assertTrue(movie_output.is_dir())
            self.assertTrue(tv_output.is_dir())
            self.assertTrue(scratch.is_dir())
            self.assertTrue(any("Created Final output folder" in warning for warning in result.warnings))
            self.assertTrue(any("Created Scratch / LocalBase folder" in warning for warning in result.warnings))
            self.assertEqual(len(service.saved_config_calls), 1)
            saved = service.saved_config_calls[0]
            values = saved["config_values"]
            self.assertFalse(saved["create_backup"])
            self.assertGreaterEqual(len(values), 80)
            self.assertEqual(values["SourceMovies"], str(root / "Encode" / "Movies"))
            self.assertEqual(values["SourceTV"], str(root / "Encode" / "TV"))
            self.assertEqual(values["Outsource"], str(root / "Outsource"))
            self.assertEqual(values["LocalBase"], str(root / "Scratch"))
            self.assertTrue(result.data["writes_config"])
            self.assertTrue(result.data["wizard_completion"]["wizard_completed"])

    def test_save_settings_wizard_first_run_blocks_runtime_file_path_without_config_write(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            template = root / "ops" / "pipeline" / "config" / "MediaPipeline_config_template.psd1"
            template.parent.mkdir(parents=True)
            template.write_text("@{}\n", encoding="utf-8")
            service = WizardFirstRunService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.config_path = root / "AppData" / "MediaPipeline_config.psd1"
            resolved.config_data = {}
            wizard = _first_run_wizard(root)
            output_file = root / "Outsource"
            output_file.write_text("not a directory", encoding="utf-8")

            result = save_settings_wizard(facade, resolved, {"wizard": wizard, "confirm_save": True})

            self.assertFalse(result.ok)
            self.assertIn("Final output path is not a folder", "\n".join(result.errors))
            self.assertFalse(resolved.config_path.exists())
            self.assertEqual(service.saved_config_calls, [])
            self.assertTrue(output_file.is_file())

    def test_save_settings_wizard_does_not_bypass_blocked_existing_config(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = WizardFirstRunService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.config_path = root / "AppData" / "MediaPipeline_config.psd1"
            resolved.config_path.parent.mkdir(parents=True)
            resolved.config_path.write_text("@{ SourceMovies = 'C:\\Existing' }\n", encoding="utf-8")
            resolved.config_data = {}
            resolved.config_identity = {
                "schema_version": "desktop_config_identity.v1",
                "blocks_operations": True,
                "operator_status": "Config requires recovery",
                "reasons": ["Config PSD1 did not load into backend settings data."],
            }

            result = save_settings_wizard(facade, resolved, {"wizard": _first_run_wizard(root), "confirm_save": True})

        self.assertFalse(result.ok)
        self.assertIn("not a verified operator config", result.message)
        self.assertEqual(service.saved_config_calls, [])

    def test_save_settings_wizard_blocks_missing_danger_ack_without_saving(self) -> None:
        class Facade:
            def save_settings_patch(self, _resolved: ResolvedPaths, _request: dict[str, object]) -> CommandResult:
                raise AssertionError("save_settings_patch must not be called when danger acknowledgements are missing")

        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            request = {
                "wizard": {
                    "output": {"root": str(root / "Output"), "existing_policy": "reprocess_all_once"},
                    "scratch": {"path": str(root / "Scratch")},
                    "workers": {"max_parallel_encodes": 1, "parallel_encode_mode": "single"},
                    "safety": {
                        "allow_system_tools": True,
                        "allow_no_audio": True,
                        "cleanup_remote_staging": True,
                        "danger_ack": [],
                    },
                },
                "confirm_save": True,
            }
            result = save_settings_wizard(Facade(), _resolved(root), request)

        self.assertFalse(result.ok)
        self.assertEqual(result.command, "settings.wizard.save")
        self.assertEqual(result.severity, "error")
        error_text = "\n".join(result.errors)
        for key in ("AllowSystemTools", "AllowNoAudio", "CleanupRemoteStaging", "ReprocessAll"):
            self.assertIn(key, error_text)
        self.assertIn("acknowledgement", result.message)

    def test_save_settings_wizard_allows_acknowledged_danger_keys(self) -> None:
        class Facade:
            def __init__(self) -> None:
                self.requests: list[dict[str, object]] = []

            def preview_settings_patch(self, _resolved: ResolvedPaths, request: dict[str, object]) -> CommandResult:
                return CommandResult(
                    command="settings.preview_patch",
                    ok=True,
                    message="previewed",
                    severity="info",
                    data={
                        "changed_keys": sorted(request["changes"]),
                        "review_confirmation": {"preview_id": "wizard-preview-1"},
                    },
                )

            def save_settings_patch(self, _resolved: ResolvedPaths, request: dict[str, object]) -> CommandResult:
                self.requests.append(request)
                return CommandResult(
                    command="settings.save_patch",
                    ok=True,
                    message="saved",
                    severity="info",
                    data={"writes_config": True, "changed_keys": sorted(request["changes"])},
                )

        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            facade = Facade()
            resolved = _resolved(root)
            resolved.config_data = {"RoutingProfile": "plex_direct_stream"}
            request = {
                "wizard": {
                    "output": {"root": str(root / "Output"), "existing_policy": "reprocess_all_once"},
                    "scratch": {"path": str(root / "Scratch")},
                    "workers": {"max_parallel_encodes": 1, "parallel_encode_mode": "single"},
                    "safety": {
                        "allow_system_tools": True,
                        "allow_no_audio": True,
                        "cleanup_remote_staging": True,
                        "danger_ack": ["AllowSystemTools", "AllowNoAudio", "CleanupRemoteStaging", "ReprocessAll"],
                    },
                },
                "confirm_save": True,
                "review_confirmation": {"preview_id": "wizard-preview-1"},
            }
            result = save_settings_wizard(facade, resolved, request)

        self.assertTrue(result.ok)
        self.assertEqual(len(facade.requests), 1)
        self.assertTrue(facade.requests[0]["confirm_save"])
        changes = facade.requests[0]["changes"]
        self.assertEqual(changes["AllowSystemTools"], True)
        self.assertEqual(changes["AllowNoAudio"], True)
        self.assertEqual(changes["CleanupRemoteStaging"], True)
        self.assertEqual(changes["ReprocessAll"], True)


if __name__ == "__main__":
    unittest.main()
