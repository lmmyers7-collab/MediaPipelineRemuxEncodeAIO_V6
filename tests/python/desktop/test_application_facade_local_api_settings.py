from __future__ import annotations

import contextlib
import csv
from datetime import datetime, timedelta
import io
import json
import logging
import os
import re
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root
from urllib.parse import quote
from unittest.mock import patch

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.desktop.api import LocalApiServer
from mediapipeline.core.api.commands_process import LocalApiProcessCommandPayloadMixin
from mediapipeline.core.api.commands_settings import LocalApiSettingsCommandPayloadMixin
from mediapipeline.desktop.api.handler import build_local_api_handler_class
from mediapipeline.desktop.application import MediaPipelineApplicationFacade
from mediapipeline.desktop.local_api_main import BOOTSTRAP_SCHEMA_VERSION, bootstrap_payload, build_backend, main as local_api_main
from mediapipeline.desktop.models import ResolvedPaths, Snapshot
from tests.python.desktop.application_facade_test_support import (
    COMMAND_HISTORY_ASSET_ORDER,
    DummyFacadeService,
    DummyProc,
    DummyWorkflowFacadeService,
    LocalApiHttpTestMixin,
    served_webview_static_contract_bundle,
    assert_namespace_export as _assert_namespace_export,
    _render_static_index_html,
    _resolved,
)


class LocalApiSettingsTests(LocalApiHttpTestMixin, unittest.TestCase):
    def test_idempotent_settings_save_does_not_reload_or_claim_a_write(self) -> None:
        reload_calls = 0

        class Result:
            def to_mapping(self) -> dict[str, object]:
                return {
                    "schema_version": "desktop_command_result.v1",
                    "command": "settings.save_patch",
                    "ok": True,
                    "warnings": [],
                    "data": {
                        "writes_config": False,
                        "idempotent_replay": True,
                        "save_verification": {},
                    },
                }

        class Facade:
            def save_settings_patch(self, resolved: object, request: dict[str, object]) -> Result:
                _ = resolved, request
                return Result()

        class Harness(LocalApiSettingsCommandPayloadMixin):
            def __init__(self) -> None:
                self.facade = Facade()
                self.logger = logging.getLogger("test.local_api.settings_idempotent")
                self.resolved_reload = self._reload

            def _resolved(self) -> object:
                return object()

            def _reload(self) -> object:
                nonlocal reload_calls
                reload_calls += 1
                return object()

        payload = Harness()._settings_save_patch_payload({"confirm_save": True})

        self.assertTrue(payload["ok"])
        self.assertFalse(payload["data"]["writes_config"])
        self.assertFalse(payload["data"]["reloaded"])
        self.assertEqual(reload_calls, 0)
        self.assertIn("no settings artifact was written", payload["data"]["save_verification"]["verification_reason"])
        self.assertEqual(payload["warnings"], [])

    def test_local_api_settings_reload_failure_is_logged(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v6-test")
            logger_name = "test.local_api.settings_reload"
            long_error = "reload broke " + ("x" * 2500)

            def fail_reload() -> ResolvedPaths:
                raise RuntimeError(long_error)

            server = LocalApiServer(
                facade,
                token="test-token",
                resolved_reload=fail_reload,
                logger=logging.getLogger(logger_name),
            )
            try:
                server.start()
                with self.assertLogs(logger_name, level="ERROR") as logs:
                    status, payload = self._post_json(
                        f"{server.url}/api/settings/reload",
                        {},
                        token="test-token",
                    )
            finally:
                server.stop()

        self.assertEqual(status, 200)
        self.assertEqual(payload["command"], "settings.reload")
        self.assertFalse(payload["ok"])
        self.assertIn("reload broke", payload["message"])
        self.assertLessEqual(len(payload["errors"][0]), 2000)
        self.assertIn("local API settings reload failed", "\n".join(logs.output))


if __name__ == "__main__":
    unittest.main()
