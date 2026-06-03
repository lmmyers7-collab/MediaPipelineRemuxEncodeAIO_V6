from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mediapipeline_desktop_app.models import ResolvedPaths, TelemetrySnapshot
from app.telemetry.health import (
    ass_to_srt_exception_row,
    ass_to_srt_missing_row,
    ass_to_srt_result_row,
    bundled_tool_health_rows,
    find_ass_to_srt_script,
    find_bundled_or_system_tool,
    nvidia_smi_health_row,
    powershell_health_row,
    subtitle_tool_health_rows,
)
from app.telemetry.nvidia import (
    apply_nvidia_smi_rows_to_snapshot,
    parse_nvidia_smi_encoder_rows,
    select_active_gpu_row,
)
from app.telemetry.gpu_usage import GPU_ENCODER_USAGE_SCHEMA_VERSION, gpu_encoder_usage_payload
from app.telemetry.system_metrics import apply_system_metrics_to_snapshot, prime_cpu_sampler
from mediapipeline_desktop_app.services import DesktopAppService
from mediapipeline_desktop_app.subprocess_runner import CapturedCommandResult


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
            ffmpeg = root / "Pipeline" / "Tools" / "ffmpeg" / "bin" / "ffmpeg.exe"
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
                    root / "DesktopApp",
                    "ffmpeg.exe",
                    "ffmpeg",
                    ("Pipeline/Tools/ffmpeg/bin/ffmpeg.exe",),
                    which=lambda _name: None,
                ),
                str(ffmpeg),
            )

            rows = bundled_tool_health_rows(root, root / "DesktopApp", which=lambda _name: None)

        self.assertEqual(rows[0], ("ffmpeg", True, str(ffmpeg)))
        self.assertEqual(rows[1], ("ffprobe", False, "Not found in bundled Tools or system PATH"))
        self.assertEqual(rows[2], ("mkvmerge", False, "Not found in bundled Tools or system PATH"))
        self.assertEqual(rows[3], ("mkvextract", False, "Not found in bundled Tools or system PATH"))

    def test_subtitle_tool_health_rows_cover_bdpgs_and_vobsub_helpers(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            app_root = root / "DesktopApp"
            pgs = root / "Pipeline" / "Tools" / "PgsToSrt" / "PgsToSrt.exe"
            pgs_tessdata = pgs.parent / "tessdata"
            subtitle_edit = root / "Pipeline" / "Tools" / "SubtitleEditLegacy" / "SubtitleEdit.exe"
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
            pipeline = root / "Pipeline"
            pipeline.mkdir()
            fallback = pipeline / "ass_to_srt.py"
            fallback.write_text("", encoding="utf-8")
            preferred = pipeline / "ass_to_srt.py"
            preferred.write_text("", encoding="utf-8")

            script = find_ass_to_srt_script(root, root / "DesktopApp")

        self.assertEqual(script, preferred)
        self.assertEqual(ass_to_srt_missing_row(), ("ass_to_srt (subtitle converter)", False, "Script not found in Pipeline/"))
        self.assertEqual(ass_to_srt_result_row(preferred, 2, ""), ("ass_to_srt (subtitle converter)", True, str(preferred)))
        self.assertEqual(
            ass_to_srt_result_row(preferred, 1, "Import failed\nmore detail"),
            ("ass_to_srt (subtitle converter)", False, "Import failed"),
        )
        self.assertEqual(
            ass_to_srt_exception_row(RuntimeError("boom")),
            ("ass_to_srt (subtitle converter)", False, "boom"),
        )

    def test_check_environment_health_uses_helper_rows_and_subprocess_probe(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            app_root = root / "DesktopApp"
            app_root.mkdir()
            for rel in (
                "Pipeline/Tools/ffmpeg/bin/ffmpeg.exe",
                "Pipeline/Tools/ffmpeg/bin/ffprobe.exe",
                "Pipeline/Tools/MKVToolNix/mkvmerge.exe",
                "Pipeline/Tools/MKVToolNix/mkvextract.exe",
                "Pipeline/Tools/PgsToSrt/PgsToSrt.exe",
                "Pipeline/Tools/PgsToSrt/tessdata/eng.traineddata",
                "Pipeline/Tools/SubtitleEditLegacy/SubtitleEdit.exe",
                "Pipeline/Tools/SubtitleEditLegacy/Tesseract302/tesseract.exe",
                "Pipeline/Tools/SubtitleEditLegacy/Tesseract302/tessdata/eng.traineddata",
            ):
                path = root / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("", encoding="utf-8")
            script = root / "Pipeline" / "ass_to_srt.py"
            script.parent.mkdir(parents=True, exist_ok=True)
            script.write_text("", encoding="utf-8")
            service = DesktopAppService(app_root)
            service._nvidia_smi_checked = True
            service._nvidia_smi_path = None
            resolved = ResolvedPaths(
                app_root=app_root,
                workspace_root=root,
                pipeline_path=root / "Pipeline" / "pipeline.ps1",
                config_path=root / "config.psd1",
                audit_script_path=root / "audit.ps1",
                rerun_script_path=root / "rerun.ps1",
                powershell_host="pwsh.exe",
                config_data={
                    "ConvertBdpgsToSrt": True,
                    "ConvertVobSubToSrt": True,
                    "BdpgsExtractLanguages": ["eng"],
                    "VobSubExtractLanguages": ["eng"],
                },
            )

            def fake_run(*_args, **_kwargs):
                return CapturedCommandResult(args=[], returncode=2, stdout="", stderr="")

            progress_events: list[dict[str, object]] = []
            with patch("app.telemetry.service.run_capture", fake_run):
                rows = service.check_environment_health(resolved, progress_callback=progress_events.append)

            for handler in list(service.logger.handlers):
                base_filename = getattr(handler, "baseFilename", "")
                if base_filename and str(base_filename).startswith(str(app_root)):
                    service.logger.removeHandler(handler)
                    handler.close()

        by_name = {row[0]: row for row in rows}
        self.assertEqual(by_name["PowerShell (pwsh)"], ("PowerShell (pwsh)", True, "pwsh.exe"))
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
        self.assertTrue(any(event["active_step_id"] == "pending_publish_path" for event in progress_events))
        self.assertTrue(all(isinstance(event["rows"], list) for event in progress_events))

    def test_nvidia_smi_parser_keeps_idle_na_encoder_rows_visible(self) -> None:
        rows, failures = parse_nvidia_smi_encoder_rows(
            "0, NVIDIA RTX Idle, N/A, 44, 1024, 8192\n"
            "1, NVIDIA RTX Busy, 21, 55, 2048, 8192\n"
            "bad,row\n"
        )

        self.assertEqual(failures, 1)
        self.assertEqual(rows[0]["encoder_percent"], 0.0)
        self.assertEqual(rows[1]["encoder_percent"], 21.0)
        self.assertEqual(rows[1]["temperature_c"], 55.0)

    def test_nvidia_smi_snapshot_uses_max_encoder_gpu_and_memory(self) -> None:
        rows, _failures = parse_nvidia_smi_encoder_rows(
            "0, NVIDIA RTX Idle, 0, 44, 1024, 8192\n"
            "1, NVIDIA RTX Busy, 21, 55, 2048, 8192\n"
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
        self.assertEqual(snapshot.gpu_percent, 21.0)
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
                    "temperature_c": 44.0,
                    "memory_used_mb": 1024.0,
                    "memory_total_mb": 8192.0,
                },
                {
                    "index": "1",
                    "name": "NVIDIA RTX Busy",
                    "encoder_percent": 21.0,
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
                    stdout="0, NVIDIA RTX Test, N/A, 44, 1024, 8192\n",
                    stderr="",
                )

            with patch("app.telemetry.service.run_capture", fake_run):
                snapshot = service.sample_system_telemetry()

            self.assertEqual(snapshot.gpu_encoder_percent, 0.0)
            self.assertEqual(snapshot.gpu_index, "0")
            self.assertEqual(snapshot.gpu_count, 1)
            self.assertEqual(snapshot.gpu_rows[0]["encoder_percent"], 0.0)
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

            with patch("app.telemetry.service.psutil", FakePsutil), patch("app.telemetry.service.run_capture", fake_run):
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

            with patch("app.telemetry.service.psutil", FakePsutil), patch("app.telemetry.service.run_capture", fake_run):
                snapshot = service.sample_system_telemetry()

            self.assertEqual(snapshot.error, "nvidia-smi exited with code 9")
            for handler in list(service.logger.handlers):
                base_filename = getattr(handler, "baseFilename", "")
                if base_filename and str(base_filename).startswith(str(Path(td))):
                    service.logger.removeHandler(handler)
                    handler.close()


if __name__ == "__main__":
    unittest.main()
