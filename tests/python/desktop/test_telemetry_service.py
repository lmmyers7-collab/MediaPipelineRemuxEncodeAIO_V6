from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root
from unittest.mock import patch

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.desktop.models import ResolvedPaths, TelemetrySnapshot
from mediapipeline.core.telemetry.health import (
    api_contract_health_rows,
    ass_to_srt_exception_row,
    ass_to_srt_missing_row,
    ass_to_srt_result_row,
    bundle_layout_health_rows,
    bundled_tool_health_rows,
    config_schema_health_rows,
    configured_root_health_rows,
    find_ass_to_srt_script,
    find_bundled_or_system_tool,
    library_output_health_rows,
    nvidia_smi_health_row,
    process_guard_health_rows,
    powershell_health_row,
    runtime_state_health_rows,
    subtitle_tool_health_rows,
)
from mediapipeline.core.telemetry.nvidia import (
    apply_nvidia_smi_rows_to_snapshot,
    parse_nvidia_smi_encoder_rows,
    select_active_gpu_row,
)
from mediapipeline.core.telemetry.gpu_usage import GPU_ENCODER_USAGE_SCHEMA_VERSION, gpu_encoder_usage_payload
from mediapipeline.core.telemetry.system_metrics import (
    apply_system_metrics_to_snapshot,
    prime_cpu_sampler,
    WINDOWS_PROCESSOR_TIME_COUNTER,
    WindowsProcessorUtilitySampler,
)
from mediapipeline.desktop.services import DesktopAppService
from mediapipeline.desktop.subprocess_runner import CapturedCommandResult


class TelemetryServiceTests(unittest.TestCase):
    def test_system_metric_helpers_prime_and_apply_cpu_memory(self) -> None:
        class Vm:
            percent = 61.5
            used = 3 * 1024 ** 3
            total = 8 * 1024 ** 3

        class FakePsutil:
            calls = 0

            @classmethod
            def cpu_percent(cls, interval=None):
                self.assertIsNone(interval)
                cls.calls += 1
                return 12.5

            @staticmethod
            def virtual_memory():
                return Vm()

        snapshot = TelemetrySnapshot()

        prime_cpu_sampler(FakePsutil)
        apply_system_metrics_to_snapshot(snapshot, FakePsutil)

        self.assertEqual(FakePsutil.calls, 2)
        self.assertEqual(snapshot.cpu_percent, 12.5)
        self.assertEqual(snapshot.memory_percent, 61.5)
        self.assertEqual(snapshot.memory_used_gb, 3.0)
        self.assertEqual(snapshot.memory_total_gb, 8.0)
        self.assertEqual(snapshot.error, "")

    def test_system_metric_helper_prefers_cpu_sampler_over_psutil_cpu(self) -> None:
        class Vm:
            percent = 61.5
            used = 3 * 1024 ** 3
            total = 8 * 1024 ** 3

        class FakePsutil:
            calls = 0

            @classmethod
            def cpu_percent(cls, interval=None):
                self.assertIsNone(interval)
                cls.calls += 1
                return 99.0

            @staticmethod
            def virtual_memory():
                return Vm()

        class FakeCpuSampler:
            calls: list[str] = []

            @classmethod
            def prime(cls):
                cls.calls.append("prime")

            @classmethod
            def sample(cls):
                cls.calls.append("sample")
                return 33.6

        snapshot = TelemetrySnapshot()

        prime_cpu_sampler(FakePsutil, FakeCpuSampler)
        apply_system_metrics_to_snapshot(snapshot, FakePsutil, FakeCpuSampler)

        self.assertEqual(FakeCpuSampler.calls, ["prime", "sample"])
        self.assertEqual(FakePsutil.calls, 1)
        self.assertEqual(snapshot.cpu_percent, 33.6)
        self.assertEqual(snapshot.memory_percent, 61.5)
        self.assertEqual(snapshot.error, "")

    def test_system_metric_helper_falls_back_when_cpu_sampler_has_no_sample(self) -> None:
        class Vm:
            percent = 50.0
            used = 2 * 1024 ** 3
            total = 4 * 1024 ** 3

        class FakePsutil:
            @staticmethod
            def cpu_percent(interval=None):
                self.assertIsNone(interval)
                return 14.0

            @staticmethod
            def virtual_memory():
                return Vm()

        class EmptyCpuSampler:
            @staticmethod
            def sample():
                return None

        snapshot = TelemetrySnapshot()

        apply_system_metrics_to_snapshot(snapshot, FakePsutil, EmptyCpuSampler)

        self.assertEqual(snapshot.cpu_percent, 14.0)
        self.assertEqual(snapshot.memory_percent, 50.0)
        self.assertEqual(snapshot.error, "")

    def test_cpu_counter_uses_processor_time_basis_not_turbo_utility(self) -> None:
        # "% Processor Utility" is scaled by the turbo frequency ratio and
        # saturates the 0-100% bar at 100% on turbo-capable CPUs. The CPU
        # telemetry basis must be the true-utilization "% Processor Time" counter.
        self.assertEqual(
            WINDOWS_PROCESSOR_TIME_COUNTER,
            r"\Processor Information(_Total)\% Processor Time",
        )
        self.assertEqual(
            WindowsProcessorUtilitySampler()._counter_path,
            WINDOWS_PROCESSOR_TIME_COUNTER,
        )

    def test_system_metric_helper_clamps_task_manager_cpu_utility(self) -> None:
        class Vm:
            percent = 50.0
            used = 2 * 1024 ** 3
            total = 4 * 1024 ** 3

        class FakePsutil:
            @staticmethod
            def cpu_percent(interval=None):
                return 14.0

            @staticmethod
            def virtual_memory():
                return Vm()

        class TurboCpuSampler:
            @staticmethod
            def sample():
                return 112.5

        snapshot = TelemetrySnapshot()

        apply_system_metrics_to_snapshot(snapshot, FakePsutil, TurboCpuSampler)

        self.assertEqual(snapshot.cpu_percent, 100.0)
        self.assertEqual(snapshot.memory_percent, 50.0)
        self.assertEqual(snapshot.error, "")

    def test_system_metric_helper_marks_psutil_unavailable(self) -> None:
        snapshot = TelemetrySnapshot()

        prime_cpu_sampler(None)
        apply_system_metrics_to_snapshot(snapshot, None)

        self.assertEqual(snapshot.error, "psutil unavailable")
        self.assertIsNone(snapshot.cpu_percent)
        self.assertIsNone(snapshot.memory_percent)

    def test_system_metric_helper_preserves_memory_when_cpu_fails(self) -> None:
        class Vm:
            percent = 50.0
            used = 2 * 1024 ** 3
            total = 4 * 1024 ** 3

        class BadCpuPsutil:
            @staticmethod
            def cpu_percent(interval=None):
                raise RuntimeError("cpu unavailable")

            @staticmethod
            def virtual_memory():
                return Vm()

        snapshot = TelemetrySnapshot()

        apply_system_metrics_to_snapshot(snapshot, BadCpuPsutil)

        self.assertEqual(snapshot.error, "psutil error: cpu unavailable")
        self.assertIsNone(snapshot.cpu_percent)
        self.assertEqual(snapshot.memory_percent, 50.0)
        self.assertEqual(snapshot.memory_used_gb, 2.0)
        self.assertEqual(snapshot.memory_total_gb, 4.0)

    def test_system_metric_helper_reports_memory_failure(self) -> None:
        class BadMemoryPsutil:
            @staticmethod
            def cpu_percent(interval=None):
                return 14.0

            @staticmethod
            def virtual_memory():
                raise RuntimeError("memory unavailable")

        snapshot = TelemetrySnapshot()

        apply_system_metrics_to_snapshot(snapshot, BadMemoryPsutil)

        self.assertEqual(snapshot.cpu_percent, 14.0)
        self.assertIsNone(snapshot.memory_percent)
        self.assertEqual(snapshot.error, "psutil memory error: memory unavailable")

    def test_system_metric_helper_combines_cpu_and_memory_failures(self) -> None:
        class BadPsutil:
            @staticmethod
            def cpu_percent(interval=None):
                raise RuntimeError("cpu unavailable")

            @staticmethod
            def virtual_memory():
                raise RuntimeError("memory unavailable")

        snapshot = TelemetrySnapshot()

        apply_system_metrics_to_snapshot(snapshot, BadPsutil)

        self.assertEqual(
            snapshot.error,
            "psutil error: cpu unavailable; psutil memory error: memory unavailable",
        )

    def test_environment_health_helpers_shape_tool_rows(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            ffmpeg = root / "ops" / "pipeline" / "tools" / "ffmpeg" / "bin" / "ffmpeg.exe"
            ffmpeg.parent.mkdir(parents=True)
            ffmpeg.write_text("", encoding="utf-8")

            self.assertEqual(powershell_health_row("pwsh.exe"), ("PowerShell (pwsh)", True, "pwsh.exe"))
            self.assertEqual(powershell_health_row(None), ("PowerShell (pwsh)", False, "Not found in bundled path or system PATH"))
            self.assertEqual(nvidia_smi_health_row("nvidia-smi.exe"), ("nvidia-smi (optional)", True, "nvidia-smi.exe"))
            self.assertEqual(
                nvidia_smi_health_row(None),
                ("nvidia-smi (optional)", False, "Not found - GPU encoder telemetry unavailable"),
            )
            self.assertEqual(
                find_bundled_or_system_tool(
                    root,
                    root / "apps" / "desktop",
                    "ffmpeg.exe",
                    "ffmpeg",
                    ("ops/pipeline/tools/ffmpeg/bin/ffmpeg.exe",),
                    which=lambda _name: None,
                ),
                str(ffmpeg),
            )

            rows = bundled_tool_health_rows(root, root / "apps" / "desktop", which=lambda _name: None)

        self.assertEqual(rows[0], ("ffmpeg", True, str(ffmpeg)))
        self.assertEqual(rows[1], ("ffprobe", False, "Not found in bundled Tools or system PATH"))
        self.assertEqual(rows[2], ("mkvmerge", False, "Not found in bundled Tools or system PATH"))
        self.assertEqual(rows[3], ("mkvextract", False, "Not found in bundled Tools or system PATH"))

    def test_subtitle_tool_health_rows_cover_bdpgs_and_vobsub_helpers(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            app_root = root / "apps" / "desktop"
            pgs = root / "ops" / "pipeline" / "tools" / "PgsToSrt" / "PgsToSrt.exe"
            pgs_tessdata = pgs.parent / "tessdata"
            subtitle_edit = root / "ops" / "pipeline" / "tools" / "SubtitleEditLegacy" / "SubtitleEdit.exe"
            vobsub_tesseract = subtitle_edit.parent / "Tesseract302" / "tesseract.exe"
            vobsub_tessdata = vobsub_tesseract.parent / "tessdata"
            for path in (pgs, subtitle_edit, vobsub_tesseract):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("", encoding="utf-8")
            for directory in (pgs_tessdata, vobsub_tessdata):
                directory.mkdir(parents=True, exist_ok=True)
                (directory / "eng.traineddata").write_text("", encoding="utf-8")

            rows = subtitle_tool_health_rows(
                root,
                app_root,
                {
                    "ConvertBdpgsToSrt": True,
                    "ConvertVobSubToSrt": True,
                    "BdpgsExtractLanguages": ["eng"],
                    "VobSubExtractLanguages": ["eng"],
                },
                which=lambda _name: None,
            )
            missing_language_rows = subtitle_tool_health_rows(
                root,
                app_root,
                {
                    "ConvertBdpgsToSrt": True,
                    "ConvertVobSubToSrt": True,
                    "BdpgsExtractLanguages": ["jpn"],
                    "VobSubExtractLanguages": ["jpn"],
                },
                which=lambda _name: None,
            )

        by_name = {row[0]: row for row in rows}
        self.assertEqual(by_name["PgsToSrt (BDPGS OCR)"][1], True)
        self.assertEqual(by_name["PgsToSrt tessdata (BDPGS OCR)"][1], True)
        self.assertEqual(by_name["SubtitleEdit.exe (VobSub OCR)"][1], True)
        self.assertEqual(by_name["Tesseract OCR (VobSub OCR)"][1], True)
        self.assertIn("tessdata=", by_name["Tesseract OCR (VobSub OCR)"][2])

        by_missing_name = {row[0]: row for row in missing_language_rows}
        self.assertEqual(by_missing_name["PgsToSrt tessdata (BDPGS OCR)"][1], False)
        self.assertIn("jpn", by_missing_name["PgsToSrt tessdata (BDPGS OCR)"][2])
        self.assertEqual(by_missing_name["Tesseract OCR (VobSub OCR)"][1], False)
        self.assertIn("jpn", by_missing_name["Tesseract OCR (VobSub OCR)"][2])

    def test_ass_to_srt_health_helpers_find_script_and_shape_results(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            preferred = root / "src" / "mediapipeline" / "pipeline" / "ass_to_srt_cli.py"
            preferred.parent.mkdir(parents=True)
            preferred.write_text("", encoding="utf-8")

            script = find_ass_to_srt_script(root, root / "apps" / "desktop")

        self.assertEqual(script, preferred)
        self.assertEqual(ass_to_srt_missing_row(), ("ass_to_srt (subtitle converter)", False, "Script not found under src/mediapipeline/pipeline/"))
        self.assertEqual(ass_to_srt_result_row(preferred, 2, ""), ("ass_to_srt (subtitle converter)", True, str(preferred)))
        self.assertEqual(
            ass_to_srt_result_row(preferred, 1, "Import failed\nmore detail"),
            ("ass_to_srt (subtitle converter)", False, "Import failed"),
        )
        self.assertEqual(
            ass_to_srt_exception_row(RuntimeError("boom")),
            ("ass_to_srt (subtitle converter)", False, "boom"),
        )

    def test_expanded_environment_health_helpers_cover_config_paths_state_contract_process_and_layout(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            app_root = root / "apps" / "desktop"
            state_root = root / "LocalBase" / "State"
            active_jobs = state_root / "ActiveJobs"
            for path in (
                app_root,
                root / "Movies",
                root / "TV",
                root / "Out",
                root / "LocalBase",
                root / "LibraryOut",
                root / "PromotionDest",
                state_root,
                active_jobs,
            ):
                path.mkdir(parents=True, exist_ok=True)
            config_path = root / "ops" / "pipeline" / "config" / "MediaPipeline_config.psd1"
            config_path.parent.mkdir(parents=True, exist_ok=True)
            config_path.write_text("@{}\n", encoding="utf-8")
            progress_file = state_root / "progress.json"
            progress_file.write_text('{"CurrentStage":"idle"}\n', encoding="utf-8")

            for rel in (
                "ops/scripts/dev/start-local-api.bat",
                "ops/scripts/dev/start-tauri-preview.bat",
                "ops/scripts/dev/start-api-and-browser.bat",
                "ops/scripts/dev/run.bat",
                "ops/scripts/dev/verify-env.bat",
                "ops/scripts/dev/verify-env.ps1",
                "apps/desktop/runtime/Python/python.exe",
                "ops/pipeline/runtime/PowerShell-7.6.0-win-x64/pwsh.exe",
                "apps/desktop/webview/static/index.html",
            ):
                path = root / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("", encoding="utf-8")

            config = {
                "SourceMovies": str(root / "Movies"),
                "SourceTV": str(root / "TV"),
                "Outsource": str(root / "Out"),
                "LocalBase": str(root / "LocalBase"),
                "VideoCodec": "hevc_nvenc",
                "LibraryProfiles": [
                    {
                        "id": "custom",
                        "name": "Custom",
                        "enabled": True,
                        "source_path": str(root / "Movies"),
                        "output_path": str(root / "LibraryOut"),
                        "promotion_enabled": True,
                        "promotion_destination": str(root / "PromotionDest"),
                    }
                ],
            }
            resolved = ResolvedPaths(
                app_root=app_root,
                workspace_root=root,
                pipeline_path=root / "ops" / "pipeline" / "entrypoints" / "MediaPipeline.ps1",
                config_path=config_path,
                audit_script_path=root / "audit.ps1",
                rerun_script_path=root / "rerun.ps1",
                powershell_host=str(root / "ops" / "pipeline" / "runtime" / "PowerShell-7.6.0-win-x64" / "pwsh.exe"),
                local_base=root / "LocalBase",
                state_root=state_root,
                active_jobs_path=active_jobs,
                progress_file=progress_file,
                config_data=config,
            )
            service = DesktopAppService(app_root)

            rows = (
                config_schema_health_rows(resolved)
                + configured_root_health_rows(resolved)
                + library_output_health_rows(resolved)
                + runtime_state_health_rows(resolved)
                + api_contract_health_rows()
                + process_guard_health_rows(resolved, service)
                + bundle_layout_health_rows(root, app_root)
            )

            for handler in list(service.logger.handlers):
                base_filename = getattr(handler, "baseFilename", "")
                if base_filename and str(base_filename).startswith(str(app_root)):
                    service.logger.removeHandler(handler)
                    handler.close()

        by_name = {row[0]: row for row in rows}
        self.assertTrue(by_name["Config schema"][1])
        self.assertTrue(by_name["Configured root: SourceMovies"][1])
        self.assertTrue(by_name["Library output root: Custom"][1])
        self.assertTrue(by_name["Library promotion destination: Custom"][1])
        self.assertTrue(by_name["Runtime state files"][1])
        self.assertTrue(by_name["SQLite mirror (optional)"][1])
        self.assertTrue(by_name["API contract"][1])
        self.assertTrue(by_name["Process guard"][1])
        self.assertTrue(by_name["Bundle layout"][1])
        self.assertIn("/api/status is not an active route", by_name["API contract"][2])

    def test_expanded_environment_health_helpers_report_invalid_state_and_layout(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            state_root = root / "LocalBase" / "State"
            state_root.mkdir(parents=True)
            bad_json = state_root / "progress.json"
            bad_json.write_text("{not json", encoding="utf-8")
            bad_sqlite = state_root / "mediapipeline_state.sqlite3"
            bad_sqlite.write_text("not sqlite", encoding="utf-8")
            resolved = ResolvedPaths(
                app_root=root / "apps" / "desktop",
                workspace_root=root,
                pipeline_path=root / "ops" / "pipeline" / "entrypoints" / "MediaPipeline.ps1",
                config_path=root / "missing.psd1",
                audit_script_path=root / "audit.ps1",
                rerun_script_path=root / "rerun.ps1",
                powershell_host=None,
                local_base=root / "LocalBase",
                state_root=state_root,
                progress_file=bad_json,
                config_data={},
            )

            state_rows = runtime_state_health_rows(resolved)
            layout_rows = bundle_layout_health_rows(root, root / "apps" / "desktop")

        self.assertFalse({row[0]: row for row in state_rows}["Runtime state files"][1])
        self.assertIn("progress.json parse failed", {row[0]: row for row in state_rows}["Runtime state files"][2])
        self.assertFalse({row[0]: row for row in state_rows}["SQLite mirror (optional)"][1])
        self.assertIn("read-only open failed", {row[0]: row for row in state_rows}["SQLite mirror (optional)"][2])
        self.assertFalse(layout_rows[0][1])
        self.assertIn("Missing expected current layout", layout_rows[0][2])

    def test_check_environment_health_uses_helper_rows_and_subprocess_probe(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            app_root = root / "apps" / "desktop"
            app_root.mkdir(parents=True)
            for rel in (
                "ops/pipeline/tools/ffmpeg/bin/ffmpeg.exe",
                "ops/pipeline/tools/ffmpeg/bin/ffprobe.exe",
                "ops/pipeline/tools/MKVToolNix/mkvmerge.exe",
                "ops/pipeline/tools/MKVToolNix/mkvextract.exe",
                "ops/pipeline/tools/PgsToSrt/PgsToSrt.exe",
                "ops/pipeline/tools/PgsToSrt/tessdata/eng.traineddata",
                "ops/pipeline/tools/SubtitleEditLegacy/SubtitleEdit.exe",
                "ops/pipeline/tools/SubtitleEditLegacy/Tesseract302/tesseract.exe",
                "ops/pipeline/tools/SubtitleEditLegacy/Tesseract302/tessdata/eng.traineddata",
                "ops/pipeline/runtime/PowerShell-7.6.0-win-x64/pwsh.exe",
                "ops/scripts/dev/start-local-api.bat",
                "ops/scripts/dev/start-tauri-preview.bat",
                "ops/scripts/dev/start-api-and-browser.bat",
                "ops/scripts/dev/run.bat",
                "ops/scripts/dev/verify-env.bat",
                "ops/scripts/dev/verify-env.ps1",
                "apps/desktop/runtime/Python/python.exe",
                "apps/desktop/webview/static/index.html",
            ):
                path = root / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("", encoding="utf-8")
            for directory in (root / "Movies", root / "TV", root / "Outsource", root / "LocalBase" / "State" / "ActiveJobs"):
                directory.mkdir(parents=True, exist_ok=True)
            script = root / "src" / "mediapipeline" / "pipeline" / "ass_to_srt_cli.py"
            script.parent.mkdir(parents=True, exist_ok=True)
            script.write_text("", encoding="utf-8")
            config_path = root / "ops" / "pipeline" / "config" / "MediaPipeline_config.psd1"
            config_path.parent.mkdir(parents=True, exist_ok=True)
            config_path.write_text("@{}\n", encoding="utf-8")
            service = DesktopAppService(app_root)
            service._nvidia_smi_checked = True
            service._nvidia_smi_path = None
            resolved = ResolvedPaths(
                app_root=app_root,
                workspace_root=root,
                pipeline_path=root / "ops" / "pipeline" / "entrypoints" / "pipeline.ps1",
                config_path=config_path,
                audit_script_path=root / "audit.ps1",
                rerun_script_path=root / "rerun.ps1",
                powershell_host=str(root / "ops" / "pipeline" / "runtime" / "PowerShell-7.6.0-win-x64" / "pwsh.exe"),
                local_base=root / "LocalBase",
                state_root=root / "LocalBase" / "State",
                active_jobs_path=root / "LocalBase" / "State" / "ActiveJobs",
                config_data={
                    "SourceMovies": str(root / "Movies"),
                    "SourceTV": str(root / "TV"),
                    "Outsource": str(root / "Outsource"),
                    "LocalBase": str(root / "LocalBase"),
                    "VideoCodec": "hevc_nvenc",
                    "ConvertBdpgsToSrt": True,
                    "ConvertVobSubToSrt": True,
                    "BdpgsExtractLanguages": ["eng"],
                    "VobSubExtractLanguages": ["eng"],
                },
            )

            def fake_run(args, **_kwargs):
                arg_text = " ".join(str(item) for item in args)
                if "ass_to_srt_cli.py" in arg_text:
                    return CapturedCommandResult(args=list(args), returncode=2, stdout="", stderr="")
                if "-encoders" in arg_text:
                    return CapturedCommandResult(args=list(args), returncode=0, stdout=" V..... hevc_nvenc\n", stderr="")
                return CapturedCommandResult(args=list(args), returncode=0, stdout="probe ok", stderr="")

            progress_events: list[dict[str, object]] = []
            with patch("mediapipeline.core.telemetry.service.run_capture", fake_run):
                rows = service.check_environment_health(resolved, progress_callback=progress_events.append)

            for handler in list(service.logger.handlers):
                base_filename = getattr(handler, "baseFilename", "")
                if base_filename and str(base_filename).startswith(str(app_root)):
                    service.logger.removeHandler(handler)
                    handler.close()

        by_name = {row[0]: row for row in rows}
        self.assertTrue(by_name["Config schema"][1])
        self.assertTrue(by_name["Configured root: SourceMovies"][1])
        self.assertTrue(by_name["Runtime state files"][1])
        self.assertTrue(by_name["API contract"][1])
        self.assertTrue(by_name["Process guard"][1])
        self.assertTrue(by_name["Bundle layout"][1])
        self.assertEqual(by_name["PowerShell (pwsh)"][1], True)
        self.assertEqual(by_name["ffmpeg"][1], True)
        self.assertEqual(by_name["ffprobe"][1], True)
        self.assertEqual(by_name["mkvmerge"][1], True)
        self.assertEqual(by_name["mkvextract"][1], True)
        self.assertEqual(by_name["nvidia-smi (optional)"][1], False)
        self.assertEqual(by_name["ass_to_srt (subtitle converter)"], ("ass_to_srt (subtitle converter)", True, str(script)))
        self.assertEqual(by_name["PgsToSrt (BDPGS OCR)"][1], True)
        self.assertEqual(by_name["PgsToSrt tessdata (BDPGS OCR)"][1], True)
        self.assertEqual(by_name["SubtitleEdit.exe (VobSub OCR)"][1], True)
        self.assertEqual(by_name["Tesseract OCR (VobSub OCR)"][1], True)
        self.assertTrue(any(event["active_step_id"] == "subtitle_helper" for event in progress_events))
        self.assertTrue(any(event["active_step_id"] == "subtitle_bdpgs_ocr" for event in progress_events))
        self.assertTrue(any(event["active_step_id"] == "subtitle_vobsub_ocr" for event in progress_events))
        self.assertTrue(any(event["active_step_id"] == "api_contract" for event in progress_events))
        self.assertTrue(any(event["active_step_id"] == "process_guard" for event in progress_events))
        self.assertTrue(any(event["active_step_id"] == "bundle_layout" for event in progress_events))
        self.assertTrue(any(event["active_step_id"] == "pending_publish_path" for event in progress_events))
        self.assertTrue(all(isinstance(event["rows"], list) for event in progress_events))

    def test_nvidia_smi_parser_keeps_idle_na_encoder_rows_visible(self) -> None:
        rows, failures = parse_nvidia_smi_encoder_rows(
            "0, NVIDIA RTX Idle, N/A, 1, 44, 1024, 8192\n"
            "1, NVIDIA RTX Busy, 21, 64, 55, 2048, 8192\n"
            "bad,row\n"
        )

        self.assertEqual(failures, 1)
        self.assertEqual(rows[0]["encoder_percent"], 0.0)
        self.assertEqual(rows[0]["gpu_percent"], 1.0)
        self.assertEqual(rows[1]["encoder_percent"], 21.0)
        self.assertEqual(rows[1]["gpu_percent"], 64.0)
        self.assertEqual(rows[1]["temperature_c"], 55.0)

    def test_nvidia_smi_snapshot_uses_max_encoder_gpu_and_memory(self) -> None:
        rows, _failures = parse_nvidia_smi_encoder_rows(
            "0, NVIDIA RTX Idle, 0, 1, 44, 1024, 8192\n"
            "1, NVIDIA RTX Busy, 21, 64, 55, 2048, 8192\n"
        )
        snapshot = TelemetrySnapshot()

        apply_nvidia_smi_rows_to_snapshot(snapshot, rows)

        active = select_active_gpu_row(rows)
        self.assertIsNotNone(active)
        assert active is not None
        self.assertEqual(active["index"], "1")
        self.assertEqual(snapshot.gpu_index, "1")
        self.assertEqual(snapshot.gpu_count, 2)
        self.assertEqual(snapshot.gpu_encoder_percent, 21.0)
        self.assertEqual(snapshot.gpu_percent, 64.0)
        self.assertEqual(snapshot.gpu_temperature_c, 55.0)
        self.assertAlmostEqual(snapshot.gpu_memory_used_gb, 2.0)
        self.assertIn("max of 2", snapshot.gpu_name)

    def test_gpu_encoder_usage_payload_exposes_read_only_contract_without_faking_sessions(self) -> None:
        snapshot = TelemetrySnapshot(
            collected_at=datetime(2026, 5, 29, 12, 0, 0),
            gpu_rows=[
                {
                    "index": "0",
                    "name": "NVIDIA RTX Idle",
                    "encoder_percent": 0.0,
                    "gpu_percent": 1.0,
                    "temperature_c": 44.0,
                    "memory_used_mb": 1024.0,
                    "memory_total_mb": 8192.0,
                },
                {
                    "index": "1",
                    "name": "NVIDIA RTX Busy",
                    "encoder_percent": 21.0,
                    "gpu_percent": 64.0,
                    "temperature_c": 55.0,
                    "memory_used_mb": 2048.0,
                    "memory_total_mb": 8192.0,
                },
            ],
            source="nvidia-smi",
        )

        payload = gpu_encoder_usage_payload(snapshot)

        self.assertEqual(payload["schema_version"], GPU_ENCODER_USAGE_SCHEMA_VERSION)
        self.assertEqual(payload["status"], "loaded")
        self.assertEqual(payload["row_count"], 2)
        self.assertEqual(payload["active_encoder_count"], 1)
        self.assertEqual(payload["missing_session_count"], 2)
        self.assertTrue(payload["read_only"])
        self.assertEqual(payload["rows"][1]["adapter"], "NVIDIA RTX Busy")
        self.assertEqual(payload["rows"][1]["utilization_percent"], 21.0)
        self.assertEqual(payload["rows"][1]["gpu_utilization_percent"], 64.0)
        self.assertEqual(payload["rows"][1]["memory_used"], 2048.0)
        self.assertIsNone(payload["rows"][1]["encoder_sessions"])
        self.assertIn("Encoder sessions are not reported", "\n".join(payload["summary_lines"]))

    def test_nvidia_smi_na_encoder_row_remains_visible_as_zero_percent(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            service = DesktopAppService(Path(td))
            service._nvidia_smi_checked = True
            service._nvidia_smi_path = r"C:\NVIDIA\nvidia-smi.exe"

            def fake_run(*_args, **_kwargs):
                return CapturedCommandResult(
                    args=[],
                    returncode=0,
                    stdout="0, NVIDIA RTX Test, N/A, 1, 44, 1024, 8192\n",
                    stderr="",
                )

            with patch("mediapipeline.core.telemetry.service.run_capture", fake_run):
                snapshot = service.sample_system_telemetry()

            self.assertEqual(snapshot.gpu_encoder_percent, 0.0)
            self.assertEqual(snapshot.gpu_percent, 1.0)
            self.assertEqual(snapshot.gpu_index, "0")
            self.assertEqual(snapshot.gpu_count, 1)
            self.assertEqual(snapshot.gpu_rows[0]["encoder_percent"], 0.0)
            self.assertEqual(snapshot.gpu_rows[0]["gpu_percent"], 1.0)
            self.assertIn("NVIDIA RTX Test", snapshot.gpu_name)
            for handler in list(service.logger.handlers):
                base_filename = getattr(handler, "baseFilename", "")
                if base_filename and str(base_filename).startswith(str(Path(td))):
                    service.logger.removeHandler(handler)
                    handler.close()

    def test_nvidia_smi_malformed_output_reports_malformed_warning(self) -> None:
        class Vm:
            percent = 33.0
            used = 2 * 1024 ** 3
            total = 8 * 1024 ** 3

        class FakePsutil:
            @staticmethod
            def cpu_percent(interval=None):
                return 10.0

            @staticmethod
            def virtual_memory():
                return Vm()

        with tempfile.TemporaryDirectory() as td:
            service = DesktopAppService(Path(td))
            service._nvidia_smi_checked = True
            service._nvidia_smi_path = r"C:\NVIDIA\nvidia-smi.exe"

            def fake_run(*_args, **_kwargs):
                return CapturedCommandResult(
                    args=[],
                    returncode=0,
                    stdout="bad,row\n0, NVIDIA RTX Test, not-a-number, 44, 1024, 8192\n",
                    stderr="",
                )

            with patch("mediapipeline.core.telemetry.service.psutil", FakePsutil), patch("mediapipeline.core.telemetry.service.run_capture", fake_run):
                snapshot = service.sample_system_telemetry()

            self.assertEqual(snapshot.error, "nvidia-smi returned malformed encoder telemetry")
            self.assertEqual(snapshot.gpu_rows, [])
            for handler in list(service.logger.handlers):
                base_filename = getattr(handler, "baseFilename", "")
                if base_filename and str(base_filename).startswith(str(Path(td))):
                    service.logger.removeHandler(handler)
                    handler.close()

    def test_nvidia_smi_nonzero_without_stderr_reports_exit_code(self) -> None:
        class Vm:
            percent = 33.0
            used = 2 * 1024 ** 3
            total = 8 * 1024 ** 3

        class FakePsutil:
            @staticmethod
            def cpu_percent(interval=None):
                return 10.0

            @staticmethod
            def virtual_memory():
                return Vm()

        with tempfile.TemporaryDirectory() as td:
            service = DesktopAppService(Path(td))
            service._nvidia_smi_checked = True
            service._nvidia_smi_path = r"C:\NVIDIA\nvidia-smi.exe"

            def fake_run(*_args, **_kwargs):
                return CapturedCommandResult(
                    args=[],
                    returncode=9,
                    stdout="",
                    stderr="",
                )

            with patch("mediapipeline.core.telemetry.service.psutil", FakePsutil), patch("mediapipeline.core.telemetry.service.run_capture", fake_run):
                snapshot = service.sample_system_telemetry()

            self.assertEqual(snapshot.error, "nvidia-smi exited with code 9")
            for handler in list(service.logger.handlers):
                base_filename = getattr(handler, "baseFilename", "")
                if base_filename and str(base_filename).startswith(str(Path(td))):
                    service.logger.removeHandler(handler)
                    handler.close()


if __name__ == "__main__":
    unittest.main()
