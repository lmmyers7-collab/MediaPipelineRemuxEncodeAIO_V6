from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root
from unittest.mock import patch

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

try:
    from tests.webview import webview_browser_smoke_support as support
except ImportError:  # pragma: no cover - fallback for direct test execution
    from webview import webview_browser_smoke_support as support


class BrowserSmokeSupportTests(unittest.TestCase):
    def test_media_no_mutation_snapshot_hashes_only_media_and_sidecar_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            media = root / "Source" / "Sample.mkv"
            sidecar = root / "Pending" / "Sample.mkv.manifest.json"
            completed_manifest = root / "State" / "Completed" / "completed_jobs.jsonl"
            command_history = root / "RunLogs" / "local_api_command_history.json"
            media.parent.mkdir(parents=True, exist_ok=True)
            sidecar.parent.mkdir(parents=True, exist_ok=True)
            completed_manifest.parent.mkdir(parents=True, exist_ok=True)
            command_history.parent.mkdir(parents=True, exist_ok=True)
            media.write_bytes(b"media")
            sidecar.write_text('{"state":"parked"}', encoding="utf-8")
            completed_manifest.write_text('{"output":"sample"}\n', encoding="utf-8")
            command_history.write_text("[]", encoding="utf-8")

            snapshot = support.capture_media_no_mutation_snapshot(root)

            self.assertIn(str(media), snapshot)
            self.assertIn(str(sidecar), snapshot)
            self.assertIn(str(completed_manifest), snapshot)
            self.assertNotIn(str(command_history), snapshot)
            support.assert_media_no_mutation(self, snapshot)

    def test_media_no_mutation_assertion_detects_changes_deletes_and_creates(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            media = root / "Source" / "Sample.mkv"
            media.parent.mkdir(parents=True, exist_ok=True)
            media.write_bytes(b"media")
            snapshot = support.capture_media_no_mutation_snapshot(root)

            media.write_bytes(b"changed")
            with self.assertRaises(AssertionError):
                support.assert_media_no_mutation(self, snapshot)

        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            media = root / "Source" / "Sample.mkv"
            media.parent.mkdir(parents=True, exist_ok=True)
            media.write_bytes(b"media")
            snapshot = support.capture_media_no_mutation_snapshot(root)

            media.unlink()
            with self.assertRaises(AssertionError):
                support.assert_media_no_mutation(self, snapshot)

        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            media = root / "Source" / "Sample.mkv"
            media.parent.mkdir(parents=True, exist_ok=True)
            media.write_bytes(b"media")
            snapshot = support.capture_media_no_mutation_snapshot(root)

            (root / "Source" / "Sample.srt").write_text("subtitle", encoding="utf-8")
            with self.assertRaises(AssertionError):
                support.assert_media_no_mutation(self, snapshot)

    def test_fixture_backed_browser_smokes_assert_media_no_mutation(self) -> None:
        tests_dir = find_repo_root(Path(__file__)) / "tests" / "webview"
        missing = []
        for path in sorted(tests_dir.glob("test_webview_browser_*.py")):
            text = path.read_text(encoding="utf-8")
            if "capture_media_no_mutation_snapshot(" not in text or "assert_media_no_mutation(self" not in text:
                missing.append(path.name)

        self.assertEqual(missing, [])

    def test_retries_once_after_no_output_native_runner_crash(self) -> None:
        calls: list[list[str]] = []

        def fake_run(args: list[str], **_: object) -> subprocess.CompletedProcess[str]:
            calls.append(args)
            if len(calls) == 1:
                return subprocess.CompletedProcess(args, 3221226505, stdout="", stderr="")
            return subprocess.CompletedProcess(args, 0, stdout='{"ok": true, "attempt": 2}\n', stderr="")

        with patch.object(support.subprocess, "run", side_effect=fake_run), patch.object(
            support.time, "sleep"
        ) as sleep:
            result = support.run_node_browser_smoke(
                "browser support retry",
                node="node",
                runner_path=Path("runner.cjs"),
                payload_path=Path("payload.json"),
                timeout_seconds=5,
            )

        self.assertEqual(result, {"ok": True, "attempt": 2})
        self.assertEqual(len(calls), 2)
        sleep.assert_called_once_with(0.5)

    def test_does_not_retry_actionable_runner_failures_with_output(self) -> None:
        calls: list[list[str]] = []

        def fake_run(args: list[str], **_: object) -> subprocess.CompletedProcess[str]:
            calls.append(args)
            return subprocess.CompletedProcess(args, 1, stdout="", stderr="specific browser assertion failed")

        with patch.object(support.subprocess, "run", side_effect=fake_run), self.assertRaisesRegex(
            AssertionError, "specific browser assertion failed"
        ):
            support.run_node_browser_smoke(
                "browser support no retry",
                node="node",
                runner_path=Path("runner.cjs"),
                payload_path=Path("payload.json"),
                timeout_seconds=5,
            )

        self.assertEqual(len(calls), 1)

    def test_retries_once_after_transient_cdp_open_error_event(self) -> None:
        calls: list[list[str]] = []

        def fake_run(args: list[str], **_: object) -> subprocess.CompletedProcess[str]:
            calls.append(args)
            if len(calls) == 1:
                return subprocess.CompletedProcess(args, 1, stdout="", stderr="[object ErrorEvent]\n")
            return subprocess.CompletedProcess(args, 0, stdout='{"ok": true, "attempt": 2}\n', stderr="")

        with patch.object(support.subprocess, "run", side_effect=fake_run), patch.object(
            support.time, "sleep"
        ) as sleep:
            result = support.run_node_browser_smoke(
                "browser support cdp retry",
                node="node",
                runner_path=Path("runner.cjs"),
                payload_path=Path("payload.json"),
                timeout_seconds=5,
            )

        self.assertEqual(result, {"ok": True, "attempt": 2})
        self.assertEqual(len(calls), 2)
        sleep.assert_called_once_with(0.5)

    def test_retries_twice_after_transient_cdp_startup_failures(self) -> None:
        calls: list[list[str]] = []

        def fake_run(args: list[str], **_: object) -> subprocess.CompletedProcess[str]:
            calls.append(args)
            if len(calls) < 3:
                return subprocess.CompletedProcess(
                    args,
                    1,
                    stdout="",
                    stderr="CDP websocket error while opening ws://127.0.0.1/devtools/page/test\n",
                )
            return subprocess.CompletedProcess(args, 0, stdout='{"ok": true, "attempt": 3}\n', stderr="")

        with patch.object(support.subprocess, "run", side_effect=fake_run), patch.object(
            support.time, "sleep"
        ) as sleep:
            result = support.run_node_browser_smoke(
                "browser support repeated cdp retry",
                node="node",
                runner_path=Path("runner.cjs"),
                payload_path=Path("payload.json"),
                timeout_seconds=5,
            )

        self.assertEqual(result, {"ok": True, "attempt": 3})
        self.assertEqual(len(calls), 3)
        self.assertEqual(sleep.call_count, 2)


if __name__ == "__main__":
    unittest.main()
