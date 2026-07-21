from __future__ import annotations

import json
import os
import shutil
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
    def _invoke_browser_wrapper_fixture(
        self,
        *,
        allow_skipped_tests: bool,
        fixture_source: str | None = None,
        module: str = "browser_smoke_skip_fixture",
        wrapper_timeout_seconds: int = 30,
    ) -> tuple[subprocess.CompletedProcess[str], dict[str, object]]:
        powershell = shutil.which("powershell") or shutil.which("pwsh")
        if not powershell:
            self.skipTest("PowerShell is required for the browser wrapper contract test.")
        project_root = find_repo_root(Path(__file__))
        common_path = project_root / "ops" / "scripts" / "smoke" / "webview_browser_smoke_common.ps1"
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            (root / f"{module}.py").write_text(
                fixture_source
                or (
                    "import unittest\n\n"
                    "class BrowserSmokeSkipFixture(unittest.TestCase):\n"
                    "    def test_missing_prerequisite(self):\n"
                    "        self.skipTest('injected prerequisite failure')\n"
                ),
                encoding="utf-8",
            )
            def quote(value: object) -> str:
                return str(value).replace("'", "''")

            allow_argument = " -AllowSkippedTests" if allow_skipped_tests else ""
            driver = root / "invoke-wrapper.ps1"
            driver.write_text(
                f". '{quote(common_path)}'\n"
                f"Invoke-WebViewBrowserSmokeUnittest -ProjectRoot '{quote(project_root)}' "
                f"-Module '{quote(module)}' -TimeoutSeconds {wrapper_timeout_seconds}{allow_argument}\n",
                encoding="utf-8",
            )
            environment = os.environ.copy()
            environment["PYTHONPATH"] = str(root)
            result = subprocess.run(
                [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(driver)],
                text=True,
                capture_output=True,
                check=False,
                env=environment,
                timeout=max(30, wrapper_timeout_seconds + 10),
            )

        json_results = []
        for line in result.stdout.splitlines():
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict) and parsed.get("kind") == "webview_browser_smoke":
                json_results.append(parsed)
        self.assertEqual(len(json_results), 1, result.stdout + result.stderr)
        return result, json_results[0]

    def test_namespace_promotion_respects_sticky_test_global_masks(self) -> None:
        node = shutil.which("node")
        if not node:
            self.skipTest("node is required for the browser namespace promotion test.")
        promotion = support.browser_namespace_promotion_script()
        script = f"""
        globalThis.window = {{
          mediaPipelineFixture: {{ faultedDependency: () => "restored" }},
        }};
        const promotion = {json.dumps(promotion)};
        eval(promotion);
        if (typeof window.faultedDependency !== "function") throw new Error("initial promotion failed");
        window.__mediaPipelineBrowserSmokeMaskGlobal("faultedDependency");
        if (window.faultedDependency !== undefined) throw new Error("mask did not delete global");
        eval(promotion);
        if (window.faultedDependency !== undefined) throw new Error("promotion restored masked global");
        console.log(JSON.stringify(window.__mediaPipelineBrowserSmokeMaskedGlobals));
        """

        result = subprocess.run(
            [node, "-e", script],
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), ["faultedDependency"])

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

    def test_media_no_mutation_assertion_watches_image_subtitle_sidecars(self) -> None:
        for suffix in (".idx", ".sub", ".sup"):
            with self.subTest(suffix=suffix, mutation="modify"):
                with tempfile.TemporaryDirectory() as raw_root:
                    root = Path(raw_root)
                    sidecar = root / "Source" / f"Sample{suffix}"
                    sidecar.parent.mkdir(parents=True, exist_ok=True)
                    sidecar.write_bytes(b"subtitle")
                    snapshot = support.capture_media_no_mutation_snapshot(root)

                    self.assertIn(str(sidecar), snapshot)
                    sidecar.write_bytes(b"changed")
                    with self.assertRaises(AssertionError):
                        support.assert_media_no_mutation(self, snapshot)

            with self.subTest(suffix=suffix, mutation="delete"):
                with tempfile.TemporaryDirectory() as raw_root:
                    root = Path(raw_root)
                    sidecar = root / "Source" / f"Sample{suffix}"
                    sidecar.parent.mkdir(parents=True, exist_ok=True)
                    sidecar.write_bytes(b"subtitle")
                    snapshot = support.capture_media_no_mutation_snapshot(root)

                    sidecar.unlink()
                    with self.assertRaises(AssertionError):
                        support.assert_media_no_mutation(self, snapshot)

            with self.subTest(suffix=suffix, mutation="create"):
                with tempfile.TemporaryDirectory() as raw_root:
                    root = Path(raw_root)
                    source_dir = root / "Source"
                    source_dir.mkdir(parents=True, exist_ok=True)
                    snapshot = support.capture_media_no_mutation_snapshot(root)

                    (source_dir / f"Sample{suffix}").write_bytes(b"subtitle")
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

    def test_runner_failure_still_executes_media_no_mutation_finalizer(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            media = root / "Source" / "Sample.mkv"
            media.parent.mkdir(parents=True, exist_ok=True)
            media.write_bytes(b"before")
            support.capture_media_no_mutation_snapshot(root)

            def fake_run(args: list[str], **_: object) -> subprocess.CompletedProcess[str]:
                media.write_bytes(b"mutated by injected runner failure")
                return subprocess.CompletedProcess(args, 1, stdout="", stderr="injected runner failure")

            with patch.object(support.subprocess, "run", side_effect=fake_run), self.assertRaisesRegex(
                AssertionError, "injected runner failure"
            ) as raised:
                support.run_node_browser_smoke(
                    "browser support mutation finalizer",
                    node="node",
                    runner_path=Path("runner.cjs"),
                    payload_path=Path("payload.json"),
                    timeout_seconds=5,
                )

        notes = getattr(raised.exception, "__notes__", [])
        self.assertTrue(any("No-mutation finalizer failed" in note for note in notes), notes)
        self.assertEqual(support._PENDING_MEDIA_NO_MUTATION_SNAPSHOTS.get(), ())

    def test_successful_runner_fails_closed_when_media_finalizer_detects_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            media = root / "Source" / "Sample.mkv"
            media.parent.mkdir(parents=True, exist_ok=True)
            media.write_bytes(b"before")
            support.capture_media_no_mutation_snapshot(root)

            def fake_run(args: list[str], **_: object) -> subprocess.CompletedProcess[str]:
                media.write_bytes(b"mutated by successful runner")
                return subprocess.CompletedProcess(args, 0, stdout='{"ok": true}\n', stderr="")

            with patch.object(support.subprocess, "run", side_effect=fake_run), self.assertRaisesRegex(
                AssertionError, "No-mutation finalizer failed"
            ):
                support.run_node_browser_smoke(
                    "browser support successful runner mutation",
                    node="node",
                    runner_path=Path("runner.cjs"),
                    payload_path=Path("payload.json"),
                    timeout_seconds=5,
                )

        self.assertEqual(support._PENDING_MEDIA_NO_MUTATION_SNAPSHOTS.get(), ())

    def test_browser_wrapper_emits_strict_machine_readable_skip_result(self) -> None:
        result, payload = self._invoke_browser_wrapper_fixture(allow_skipped_tests=False)

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["outcome"], "skipped_disallowed")
        self.assertEqual(payload["wrapper_exit_code"], 1)
        self.assertEqual(payload["test_exit_code"], 0)
        self.assertEqual(payload["tests_run"], 1)
        self.assertEqual(payload["skipped_count"], 1)
        self.assertFalse(payload["allow_skipped_tests"])
        self.assertTrue(payload["prerequisites"]["python"]["available"])
        self.assertIn("node", payload["prerequisites"])
        self.assertIn("browser", payload["prerequisites"])
        expected_missing = sorted(
            name
            for name, prerequisite in payload["prerequisites"].items()
            if not prerequisite["available"]
        )
        self.assertEqual(sorted(payload["missing_prerequisites"]), expected_missing)
        self.assertEqual(
            payload["reason_category"],
            "missing_browser_prerequisite" if expected_missing else "test_reported_skip",
        )
        self.assertTrue(payload["reason"])

    def test_browser_wrapper_emits_machine_readable_missing_python_prerequisite(self) -> None:
        powershell = shutil.which("powershell") or shutil.which("pwsh")
        if not powershell:
            self.skipTest("PowerShell is required for the browser wrapper contract test.")
        project_root = find_repo_root(Path(__file__))
        common_path = project_root / "ops" / "scripts" / "smoke" / "webview_browser_smoke_common.ps1"
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            driver = root / "invoke-wrapper.ps1"
            quoted_common = str(common_path).replace("'", "''")
            quoted_root = str(root).replace("'", "''")
            driver.write_text(
                f". '{quoted_common}'\n"
                f"Invoke-WebViewBrowserSmokeUnittest -ProjectRoot '{quoted_root}' -Module 'not_started'\n",
                encoding="utf-8",
            )
            environment = os.environ.copy()
            environment["PATH"] = ""
            result = subprocess.run(
                [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(driver)],
                text=True,
                capture_output=True,
                check=False,
                env=environment,
                timeout=30,
            )

        json_results = []
        for line in result.stdout.splitlines():
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict) and parsed.get("kind") == "webview_browser_smoke":
                json_results.append(parsed)
        self.assertEqual(len(json_results), 1, result.stdout + result.stderr)
        payload = json_results[0]
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(payload["outcome"], "prerequisite_failed")
        self.assertEqual(payload["wrapper_exit_code"], 1)
        self.assertIsNone(payload["test_exit_code"])
        self.assertEqual(payload["tests_run"], 0)
        self.assertFalse(payload["prerequisites"]["python"]["available"])
        self.assertFalse(payload["prerequisites"]["node"]["available"])
        self.assertEqual(payload["reason_category"], "missing_browser_prerequisite")
        self.assertIn("python", payload["missing_prerequisites"])
        self.assertIn("node", payload["missing_prerequisites"])
        self.assertTrue(payload["reason"])

    def test_browser_wrapper_allows_skips_only_when_explicit_and_reports_them(self) -> None:
        result, payload = self._invoke_browser_wrapper_fixture(allow_skipped_tests=True)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(payload["outcome"], "skipped_allowed")
        self.assertEqual(payload["wrapper_exit_code"], 0)
        self.assertEqual(payload["test_exit_code"], 0)
        self.assertEqual(payload["tests_run"], 1)
        self.assertEqual(payload["skipped_count"], 1)
        self.assertTrue(payload["allow_skipped_tests"])
        self.assertIn(payload["reason_category"], {"missing_browser_prerequisite", "test_reported_skip"})
        self.assertTrue(payload["reason"])

    def test_browser_wrapper_drains_chatty_stderr_without_deadlock(self) -> None:
        result, payload = self._invoke_browser_wrapper_fixture(
            allow_skipped_tests=False,
            module="browser_smoke_chatty_fixture",
            wrapper_timeout_seconds=10,
            fixture_source=(
                "import sys\n"
                "import unittest\n\n"
                "sys.stderr.write('fixture-noise-' * 32768)\n"
                "sys.stderr.flush()\n\n"
                "class BrowserSmokeChattyFixture(unittest.TestCase):\n"
                "    def test_passes(self):\n"
                "        self.assertTrue(True)\n"
            ),
        )

        self.assertEqual(result.returncode, 0, result.stdout[-8000:] + result.stderr[-8000:])
        self.assertEqual(payload["outcome"], "passed")
        self.assertEqual(payload["tests_run"], 1)
        self.assertEqual(payload["timeout_seconds"], 10)
        self.assertFalse(payload["process_timed_out"])

    def test_browser_wrapper_timeout_is_bounded_and_machine_readable(self) -> None:
        result, payload = self._invoke_browser_wrapper_fixture(
            allow_skipped_tests=False,
            module="browser_smoke_timeout_fixture",
            wrapper_timeout_seconds=1,
            fixture_source=(
                "import time\n"
                "import unittest\n\n"
                "class BrowserSmokeTimeoutFixture(unittest.TestCase):\n"
                "    def test_times_out(self):\n"
                "        time.sleep(10)\n"
            ),
        )

        self.assertEqual(result.returncode, 124, result.stdout + result.stderr)
        self.assertEqual(payload["outcome"], "timed_out")
        self.assertEqual(payload["wrapper_exit_code"], 124)
        self.assertEqual(payload["test_exit_code"], 124)
        self.assertEqual(payload["reason_category"], "harness_timeout")
        self.assertEqual(payload["timeout_seconds"], 1)
        self.assertTrue(payload["process_timed_out"])
        self.assertIn("bounded 1-second timeout", payload["reason"])

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

    def test_retries_once_when_browser_never_opens_its_cdp_readiness_port(self) -> None:
        calls: list[list[str]] = []

        def fake_run(args: list[str], **_: object) -> subprocess.CompletedProcess[str]:
            calls.append(args)
            if len(calls) == 1:
                return subprocess.CompletedProcess(
                    args,
                    1,
                    stdout="",
                    stderr=(
                        "Timed out waiting for browser page websocket. "
                        "Last error: connect ECONNREFUSED 127.0.0.1:56046\n"
                    ),
                )
            return subprocess.CompletedProcess(args, 0, stdout='{"ok": true, "attempt": 2}\n', stderr="")

        with patch.object(support.subprocess, "run", side_effect=fake_run), patch.object(
            support.time, "sleep"
        ) as sleep:
            result = support.run_node_browser_smoke(
                "browser support cdp readiness retry",
                node="node",
                runner_path=Path("runner.cjs"),
                payload_path=Path("payload.json"),
                timeout_seconds=5,
            )

        self.assertEqual(result, {"ok": True, "attempt": 2})
        self.assertEqual(len(calls), 2)
        sleep.assert_called_once_with(0.5)

    def test_stops_after_single_retry_for_repeated_transient_cdp_startup_failures(self) -> None:
        calls: list[list[str]] = []

        def fake_run(args: list[str], **_: object) -> subprocess.CompletedProcess[str]:
            calls.append(args)
            return subprocess.CompletedProcess(
                args,
                1,
                stdout="",
                stderr="CDP websocket error while opening ws://127.0.0.1/devtools/page/test\n",
            )

        with patch.object(support.subprocess, "run", side_effect=fake_run), patch.object(support.time, "sleep") as sleep:
            with self.assertRaisesRegex(AssertionError, "Retried 1 time"):
                support.run_node_browser_smoke(
                    "browser support repeated cdp retry",
                    node="node",
                    runner_path=Path("runner.cjs"),
                    payload_path=Path("payload.json"),
                    timeout_seconds=5,
                )

        self.assertEqual(len(calls), 2)
        sleep.assert_called_once_with(0.5)

    def test_retries_exactly_once_after_transient_cdp_startup_failure(self) -> None:
        calls: list[list[str]] = []

        def fake_run(args: list[str], **_: object) -> subprocess.CompletedProcess[str]:
            calls.append(args)
            if len(calls) == 1:
                return subprocess.CompletedProcess(
                    args,
                    1,
                    stdout="",
                    stderr="CDP websocket error while opening ws://127.0.0.1/devtools/page/test\n",
                )
            return subprocess.CompletedProcess(args, 0, stdout='{"ok": true, "attempt": 2}\n', stderr="")

        with patch.object(support.subprocess, "run", side_effect=fake_run), patch.object(support.time, "sleep") as sleep:
            result = support.run_node_browser_smoke(
                "browser support repeated cdp retry",
                node="node",
                runner_path=Path("runner.cjs"),
                payload_path=Path("payload.json"),
                timeout_seconds=5,
            )

        self.assertEqual(result, {"ok": True, "attempt": 2})
        self.assertEqual(len(calls), 2)
        sleep.assert_called_once_with(0.5)


if __name__ == "__main__":
    unittest.main()
