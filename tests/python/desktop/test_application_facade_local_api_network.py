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


class LocalApiNetworkTests(LocalApiHttpTestMixin, unittest.TestCase):
    def test_local_api_network_lifecycle_dry_run_does_not_write_command_journal(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v6-test")
            resolved = _resolved(root)
            resolved.config_data = {
                "NetworkRole": "coordinator",
                "CoordinatorPort": 7830,
                "CoordinatorBindAddress": "127.0.0.1",
                "CoordinatorHeartbeatTimeoutMins": 5,
            }
            server = LocalApiServer(
                facade,
                token="test-token",
                resolved_provider=lambda: resolved,
            )
            try:
                server.start()
                status, payload = self._post_json(
                    f"{server.url}/api/network/coordinator/start-dry-run",
                    {"reason": "operator check"},
                    token="test-token",
                )
                commands_status, commands = self._get_json(f"{server.url}/api/commands?limit=10", token="test-token")
            finally:
                server.stop()

        self.assertEqual(status, 200)
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["data"]["dry_run_only"])
        self.assertEqual(payload["data"]["effect"], "none")
        self.assertTrue(payload["data"]["suppress_command_journal"])
        self.assertEqual(commands_status, 200)
        self.assertEqual(commands["entries"], [])


if __name__ == "__main__":
    unittest.main()
