from __future__ import annotations

import logging
import sys
import tempfile
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.core.config.document_runner import (
    load_config_data_for_service,
    validate_config_document_for_save_for_service,
)
from mediapipeline.desktop.subprocess_runner import CapturedCommandResult


class DummyConfigDocumentRunnerService:
    def __init__(self) -> None:
        self.logger = logging.getLogger("test_service_config_document_runner")
        self.logger.addHandler(logging.NullHandler())
        self.validated_values: dict[str, object] | None = None

    def _subprocess_kwargs_hidden(self) -> dict[str, int]:
        return {"creationflags": 1}

    def validate_config_values(self, values: dict[str, object]) -> tuple[list[str], list[str]]:
        self.validated_values = values
        return [], ["value warning"] if values.get("Warn") else []

    def resolve_powershell_host(self) -> str | None:
        return "resolved-pwsh"


class ConfigDocumentRunnerTests(unittest.TestCase):
    def test_load_config_data_runs_import_with_hidden_kwargs_and_parses_json(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            config = Path(td) / "MediaPipeline_config.psd1"
            config.write_text("@{ VideoCodec = 'hevc_nvenc' }", encoding="utf-8")
            service = DummyConfigDocumentRunnerService()

            def fake_run(args, **kwargs):
                self.assertEqual(args[0], "pwsh")
                self.assertEqual(kwargs["timeout_seconds"], 30)
                self.assertEqual(kwargs["extra_popen_kwargs"], {"creationflags": 1})
                self.assertEqual(kwargs["label"], "config import")
                return CapturedCommandResult(args=args, returncode=0, stdout='{"VideoCodec":"hevc_nvenc"}', stderr="")

            data = load_config_data_for_service(service, config, "pwsh", run_capture_func=fake_run)

        self.assertEqual(data, {"VideoCodec": "hevc_nvenc"})

    def test_load_config_data_returns_empty_without_host_or_file(self) -> None:
        service = DummyConfigDocumentRunnerService()

        self.assertEqual(load_config_data_for_service(service, Path("missing.psd1"), None, run_capture_func=lambda *_a, **_k: None), {})
        self.assertEqual(load_config_data_for_service(service, Path("missing.psd1"), "pwsh", run_capture_func=lambda *_a, **_k: None), {})

    def test_validate_config_document_uses_resolved_host_and_reports_subprocess_failure(self) -> None:
        service = DummyConfigDocumentRunnerService()
        calls: list[list[str]] = []

        def fake_run(args, **kwargs):
            calls.append(args)
            self.assertEqual(args[0], "resolved-pwsh")
            self.assertEqual(kwargs["timeout_seconds"], 15)
            self.assertEqual(kwargs["extra_popen_kwargs"], {"creationflags": 1})
            self.assertEqual(kwargs["label"], "config syntax validation")
            return CapturedCommandResult(args=args, returncode=1, stdout="", stderr="bad psd1")

        errors, warnings = validate_config_document_for_save_for_service(
            service,
            "@{ Warn = $true }",
            config_values={"Warn": True},
            powershell_host=None,
            run_capture_func=fake_run,
        )

        self.assertEqual(len(calls), 1)
        self.assertEqual(warnings, ["value warning"])
        self.assertEqual(service.validated_values, {"Warn": True})
        self.assertEqual(errors, ["Config syntax validation failed: bad psd1"])

    def test_validate_config_document_requires_powershell_host(self) -> None:
        class NoHostService(DummyConfigDocumentRunnerService):
            def resolve_powershell_host(self) -> str | None:
                return None

        errors, warnings = validate_config_document_for_save_for_service(
            NoHostService(),
            "@{}",
            config_values=None,
            powershell_host=None,
            run_capture_func=lambda *_a, **_k: None,
        )

        self.assertEqual(warnings, [])
        self.assertEqual(errors, ["PowerShell is required to validate config syntax before saving."])


if __name__ == "__main__":
    unittest.main()
