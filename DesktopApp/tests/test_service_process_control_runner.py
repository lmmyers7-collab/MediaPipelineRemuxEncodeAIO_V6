from __future__ import annotations

import json
import logging
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mediapipeline_desktop_app.models import ResolvedPaths
from mediapipeline_desktop_app.service_process_control_runner import (
    control_flag_age_seconds_for_service,
    prepare_pipeline_control_flags_for_service,
    read_control_flag_payload_for_service,
    toggle_pause_flag_for_service,
    write_flag_for_service,
)
from mediapipeline_desktop_app.service_processes import ProcessLifecycleServiceMixin


class DummyControlRunnerService(ProcessLifecycleServiceMixin):
    def __init__(self) -> None:
        self.logger = logging.getLogger("test_service_process_control_runner")

    def _parse_progress_datetime(self, raw: str) -> datetime | None:
        try:
            return datetime.fromisoformat(raw)
        except ValueError:
            return None


def _resolved(root: Path) -> ResolvedPaths:
    state = root / "State" / "Pipeline"
    return ResolvedPaths(
        app_root=root,
        workspace_root=root,
        pipeline_path=root / "pipeline.ps1",
        config_path=root / "config.psd1",
        audit_script_path=root / "audit.ps1",
        rerun_script_path=root / "rerun.ps1",
        powershell_host=None,
        pause_flag=state / "pipeline_pause.flag",
        stop_flag=state / "pipeline_stop.flag",
        rescan_flag=state / "pipeline_rescan.flag",
    )


class ProcessControlRunnerTests(unittest.TestCase):
    def test_toggle_pause_flag_writes_and_clears_contract_flag(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            service = DummyControlRunnerService()
            resolved = _resolved(Path(td))

            first = toggle_pause_flag_for_service(service, resolved)
            payload = json.loads(resolved.pause_flag.read_text(encoding="utf-8"))
            second = toggle_pause_flag_for_service(service, resolved)

        self.assertEqual(first, "Pause requested.")
        self.assertEqual(payload["schema_version"], "pipeline_control_flag.v1")
        self.assertEqual(payload["action"], "pause")
        self.assertEqual(second, "Pause flag cleared.")
        self.assertFalse(resolved.pause_flag.exists())

    def test_write_flag_rejects_unresolved_path(self) -> None:
        service = DummyControlRunnerService()

        with self.assertRaisesRegex(RuntimeError, "Stop flag is unavailable"):
            write_flag_for_service(service, None, "Stop")

    def test_prepare_pipeline_control_flags_removes_stale_pause_and_stop(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            service = DummyControlRunnerService()
            resolved = _resolved(Path(td))
            resolved.pause_flag.parent.mkdir(parents=True, exist_ok=True)
            for path, action, label in (
                (resolved.pause_flag, "pause", "Pause"),
                (resolved.stop_flag, "stop", "Stop"),
            ):
                path.write_text(
                    json.dumps(
                        {
                            "schema_version": "pipeline_control_flag.v1",
                            "action": action,
                            "label": label,
                            "request_id": f"{action}-old",
                            "created_at": "2000-01-01T00:00:00-04:00",
                        }
                    ),
                    encoding="utf-8",
                )

            messages = prepare_pipeline_control_flags_for_service(service, resolved, stale_after_seconds=1)

        self.assertFalse(resolved.pause_flag.exists())
        self.assertFalse(resolved.stop_flag.exists())
        self.assertTrue(any("stale pause" in message for message in messages))
        self.assertTrue(any("pre-existing stop" in message for message in messages))

    def test_read_and_age_wrappers_use_service_logger_and_datetime_parser(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            service = DummyControlRunnerService()
            flag_path = Path(td) / "pipeline_rescan.flag"
            flag_path.write_text(
                json.dumps(
                    {
                        "schema_version": "pipeline_control_flag.v1",
                        "action": "rescan",
                        "label": "Rescan",
                        "request_id": "rescan-old",
                        "created_at": "2000-01-01T00:00:00-04:00",
                    }
                ),
                encoding="utf-8",
            )

            payload = read_control_flag_payload_for_service(service, flag_path)
            age = control_flag_age_seconds_for_service(service, flag_path, payload)

        self.assertIsNotNone(payload)
        assert payload is not None
        self.assertEqual(payload["action"], "rescan")
        self.assertIsNotNone(age)
        self.assertGreater(float(age), 1.0)


if __name__ == "__main__":
    unittest.main()
