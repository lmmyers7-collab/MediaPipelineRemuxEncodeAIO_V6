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


class LocalApiDiagnosticsTests(LocalApiHttpTestMixin, unittest.TestCase):
    def test_local_api_diagnostics_tail_reads_allowlisted_file(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v6-test")
            resolved = _resolved(root)
            resolved.log_file = root / "pipeline_debug.log"
            resolved.log_file.write_text("pipeline raw line\npipeline raw line\n", encoding="utf-8")
            (root / "cluster.log").write_text("coordinator started\nworker warning\n", encoding="utf-8")
            server = LocalApiServer(facade, token="test-token", resolved_provider=lambda: resolved)
            try:
                server.start()
                status, payload = self._get_json(f"{server.url}/api/diagnostics/tail?target=cluster_log&max_bytes=4096", token="test-token")
                pipeline_status, pipeline_payload = self._get_json(f"{server.url}/api/diagnostics/tail?target=pipeline_log&max_bytes=4096", token="test-token")
                rejected_status, rejected = self._get_json(f"{server.url}/api/diagnostics/tail?target=C%3A%5Csecret.txt", token="test-token")
            finally:
                server.stop()

        self.assertEqual(status, 200)
        self.assertEqual(payload["schema_version"], "desktop_diagnostics_tail.v1")
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["target"], "cluster_log")
        self.assertIn("worker warning", payload["text"])
        self.assertEqual(payload["evidence"]["evidence_authority"], "backend")
        self.assertEqual(payload["evidence"]["operator_status"], "review")
        self.assertEqual(payload["evidence"]["warning_count"], 1)
        self.assertEqual(pipeline_status, 200)
        self.assertTrue(pipeline_payload["ok"])
        self.assertEqual(pipeline_payload["target"], "pipeline_log")
        self.assertEqual(pipeline_payload["text"].count("pipeline raw line"), 2)
        self.assertEqual(rejected_status, 200)
        self.assertFalse(rejected["ok"])
        self.assertIn("not allowed", "\n".join(rejected["errors"]))
        self.assertEqual(rejected["evidence"]["operator_status"], "blocked")

    def test_local_api_diagnostics_state_summary_reads_backend_allowlist(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v6-test")
            resolved = _resolved(root)
            resolved.queue_snapshot_path = root / "State" / "Progress" / "queue_snapshot.json"
            resolved.pending_push_path = root / "State" / "PendingPublish"
            assert resolved.queue_snapshot_path is not None
            assert resolved.pending_push_path is not None
            resolved.queue_snapshot_path.parent.mkdir(parents=True)
            resolved.pending_push_path.mkdir(parents=True)
            resolved.queue_snapshot_path.write_text(json.dumps({"queue": [1, 2]}), encoding="utf-8")
            (resolved.pending_push_path / "parked.json").write_text("{}", encoding="utf-8")
            server = LocalApiServer(facade, token="test-token", resolved_provider=lambda: resolved)
            try:
                server.start()
                status, payload = self._get_json(f"{server.url}/api/diagnostics/state-summary", token="test-token")
            finally:
                server.stop()

        self.assertEqual(status, 200)
        self.assertEqual(payload["schema_version"], "desktop_diagnostics_state_summary.v1")
        self.assertEqual(payload["autonomy_health"]["schema_version"], "desktop_autonomy_health.v1")
        self.assertIn("arbitrary paths", payload["guardrail"])
        rows = {row["target"]: row for row in payload["targets"]}
        self.assertEqual(rows["queue_snapshot"]["status"], "ok")
        self.assertEqual(rows["pending_publish"]["kind"], "directory")
        self.assertTrue(rows["pending_publish"]["recent_entries"])


if __name__ == "__main__":
    unittest.main()
