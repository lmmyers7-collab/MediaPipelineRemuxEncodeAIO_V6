from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.desktop.application import MediaPipelineApplicationFacade
from tests.python.desktop.test_application_facade import DummyWorkflowFacadeService, _resolved


class ApplicationFacadeProcessControlTests(unittest.TestCase):
    def test_pipeline_control_uses_existing_control_flag_contracts(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)

            pause = facade.request_pipeline_control(resolved, "pause").to_mapping()
            rescan = facade.request_pipeline_control(resolved, "rescan").to_mapping()
            invalid = facade.request_pipeline_control(resolved, "launch-everything").to_mapping()
            pause_payload = json.loads(resolved.pause_flag.read_text(encoding="utf-8"))  # type: ignore[union-attr]
            rescan_payload = json.loads(resolved.rescan_flag.read_text(encoding="utf-8"))  # type: ignore[union-attr]

        self.assertTrue(pause["ok"])
        self.assertEqual(pause["command"], "pipeline.control.pause")
        self.assertEqual(pause_payload["action"], "pause")
        self.assertTrue(rescan["ok"])
        self.assertEqual(rescan_payload["action"], "rescan")
        self.assertFalse(invalid["ok"])
        self.assertIn("pause, stop, rescan, or kill", invalid["errors"][0])

    def test_pipeline_control_commands_share_backend_control_lock(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)

            self.assertTrue(facade._process_control_lock.acquire(blocking=False))  # type: ignore[attr-defined]
            try:
                pause = facade.request_pipeline_control(resolved, "pause").to_mapping()
                stop = facade.request_pipeline_control(resolved, "stop").to_mapping()
                rescan = facade.request_pipeline_control(resolved, "rescan").to_mapping()
            finally:
                facade._process_control_lock.release()  # type: ignore[attr-defined]
            pause_flag_exists = resolved.pause_flag.exists()  # type: ignore[union-attr]
            stop_flag_exists = resolved.stop_flag.exists()  # type: ignore[union-attr]
            rescan_flag_exists = resolved.rescan_flag.exists()  # type: ignore[union-attr]

        self.assertFalse(pause["ok"])
        self.assertFalse(stop["ok"])
        self.assertFalse(rescan["ok"])
        self.assertEqual(pause["severity"], "warning")
        self.assertIn("another pipeline control command is already in progress", pause["message"])
        self.assertIn("another pipeline control command is already in progress", stop["message"])
        self.assertIn("another pipeline control command is already in progress", rescan["message"])
        self.assertFalse(pause_flag_exists)
        self.assertFalse(stop_flag_exists)
        self.assertFalse(rescan_flag_exists)
