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


class LocalApiRepairTests(LocalApiHttpTestMixin, unittest.TestCase):
    def test_local_api_repair_reconcile_dry_run_routes_return_schema_and_suppress_journal(self) -> None:
        from tests.python.desktop.test_repair_reconcile_dry_run import (
            _assert_dry_run_shape,
            _assert_startup_reconciliation_shape,
            _completed_fixture,
            _pending_fixture,
        )

        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            completed_resolved, _completed_files = _completed_fixture(root)
            pending_resolved, _pending_files = _pending_fixture(root, orphan_payload=True)
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v6-test")

            def resolved_provider() -> ResolvedPaths:
                completed_resolved.pending_push_path = pending_resolved.pending_push_path
                completed_resolved.state_root = pending_resolved.state_root
                return completed_resolved

            completed_preview = facade.get_completed_preview(completed_resolved).to_mapping()
            pending_preview = facade.get_pending_publish_preview(pending_resolved).to_mapping()
            completed_row_key = completed_preview["rows"][0]["row_key"]
            pending_row_key = pending_preview["rows"][0]["row_key"]
            server = LocalApiServer(facade, token="test-token", resolved_provider=resolved_provider)
            try:
                server.start()
                route_payloads = {
                    "/api/completed/reconcile-manifest-dry-run": (
                        {"scope": "selected", "row_key": completed_row_key},
                        "completed.reconcile_manifest",
                    ),
                    "/api/completed/repair-sidecar-metadata-dry-run": (
                        {"scope": "selected", "row_key": completed_row_key},
                        "completed.repair_sidecar_metadata",
                    ),
                    "/api/pending-publish/repair-manifest-dry-run": (
                        {"scope": "all", "limit": 25},
                        "pending_publish.repair_manifest",
                    ),
                    "/api/pending-publish/reconcile-orphan-payloads-dry-run": (
                        {"scope": "selected", "row_key": pending_row_key},
                        "pending_publish.reconcile_orphan_payloads",
                    ),
                    "/api/startup/reconcile-dry-run": (
                        {"scope": "all", "limit": 25},
                        "startup.reconcile_state",
                    ),
                }
                responses = {}
                for route, (body, _candidate) in route_payloads.items():
                    status, payload = self._post_json(f"{server.url}{route}", body, token="test-token")
                    self.assertEqual(status, 200, route)
                    self.assertTrue(payload["ok"], route)
                    responses[route] = payload
                commands_status, commands = self._get_json(f"{server.url}/api/commands?limit=10", token="test-token")
            finally:
                server.stop()

        for route, (_body, candidate) in route_payloads.items():
            with self.subTest(route=route):
                if candidate == "startup.reconcile_state":
                    _assert_startup_reconciliation_shape(self, responses[route]["data"])
                else:
                    _assert_dry_run_shape(self, responses[route]["data"], candidate)
        self.assertEqual(commands_status, 200)
        self.assertEqual(commands["entries"], [])


if __name__ == "__main__":
    unittest.main()
