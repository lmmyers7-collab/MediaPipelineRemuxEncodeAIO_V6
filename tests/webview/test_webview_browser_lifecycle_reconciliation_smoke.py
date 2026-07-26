from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

from mediapipeline.core.processes.lifecycle_lease import LifecycleLeaseStore
from mediapipeline.core.processes.recovery import LifecycleRecoveryCoordinator
from mediapipeline.desktop.api import LocalApiServer
from mediapipeline.desktop.application import MediaPipelineApplicationFacade
from mediapipeline.tools.paths import find_repo_root

try:  # unittest discovery can import tests as top-level modules or package modules.
    from .test_application_facade import DummyWorkflowFacadeService
    from .test_webview_real_media_smoke import _get_json, _write_fixture_state
    from .webview_browser_smoke_support import (
        assert_media_no_mutation,
        browser_cdp_runner_prelude,
        capture_media_no_mutation_snapshot,
        find_browser,
        free_port,
        run_node_browser_smoke,
    )
except ImportError:  # pragma: no cover - fallback for direct test execution
    from test_application_facade import DummyWorkflowFacadeService
    from test_webview_real_media_smoke import _get_json, _write_fixture_state
    from webview_browser_smoke_support import (
        assert_media_no_mutation,
        browser_cdp_runner_prelude,
        capture_media_no_mutation_snapshot,
        find_browser,
        free_port,
        run_node_browser_smoke,
    )


ROOT = find_repo_root(Path(__file__))
RECOVERY_REASON = "Automatic recovery did not produce a successful terminal result."


def _child_env() -> dict[str, str]:
    env = dict(os.environ)
    source_root = str(ROOT / "src")
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = os.pathsep.join(item for item in (source_root, existing) if item)
    return env


def _wait_for_file(path: Path, *, timeout_seconds: float = 10.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if path.is_file():
            return
        time.sleep(0.02)
    raise AssertionError(f"Timed out waiting for helper evidence: {path}")


def _start_interrupted_audit_helper(state_root: Path, ready_path: Path) -> subprocess.Popen[str]:
    source = textwrap.dedent(
        """
        import os
        import sys
        import time
        from pathlib import Path

        from mediapipeline.core.processes.lifecycle_lease import LifecycleLeaseStore

        state_root = Path(sys.argv[1])
        ready_path = Path(sys.argv[2])
        store = LifecycleLeaseStore(state_root)
        lease = store.acquire(scope="Audit start", command_id="audit-command-1")
        lease.set_recovery_descriptor(
            route="/api/audit/start",
            request={
                "library_root": str(state_root.parent / "Outsource"),
                "include_sidecars": True,
                "show_console": False,
            },
        )
        lease.activate(os.getpid())
        ready_path.parent.mkdir(parents=True, exist_ok=True)
        ready_path.write_text(str(os.getpid()), encoding="utf-8")
        while True:
            lease.heartbeat()
            time.sleep(0.1)
        """
    )
    proc = subprocess.Popen(
        [sys.executable, "-c", source, str(state_root), str(ready_path)],
        cwd=ROOT,
        env=_child_env(),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    _wait_for_file(ready_path)
    if proc.poll() is not None:
        stdout, stderr = proc.communicate(timeout=2)
        raise AssertionError(f"Interrupted-audit helper exited early.\nstdout:\n{stdout}\nstderr:\n{stderr}")
    return proc


def _run_failed_recovery_helper(
    state_root: Path,
    result_path: Path,
) -> tuple[subprocess.Popen[str], dict[str, object]]:
    source = textwrap.dedent(
        """
        import json
        import sys
        from pathlib import Path
        from types import SimpleNamespace

        from mediapipeline.core.processes.lifecycle_lease import LifecycleLeaseStore
        from mediapipeline.core.processes.recovery import LifecycleRecoveryCoordinator

        state_root = Path(sys.argv[1])
        result_path = Path(sys.argv[2])

        def fail_replay(route, request, original_command_id):
            store = LifecycleLeaseStore(state_root)
            attempt = store.acquire(
                scope="Audit start",
                command_id=f"{original_command_id}-recovery",
                resource_claims=[str(request.get("library_root") or "")],
            )
            attempt.set_recovery_descriptor(route=route, request=request)
            attempt.release(outcome="launch_failed")
            return {
                "ok": False,
                "message": "Automatic recovery did not produce a successful terminal result.",
            }

        status = LifecycleRecoveryCoordinator().run(
            SimpleNamespace(state_root=state_root),
            resume=fail_replay,
        )
        result_path.parent.mkdir(parents=True, exist_ok=True)
        result_path.write_text(json.dumps(status, sort_keys=True), encoding="utf-8")
        """
    )
    proc = subprocess.Popen(
        [sys.executable, "-c", source, str(state_root), str(result_path)],
        cwd=ROOT,
        env=_child_env(),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stdout, stderr = proc.communicate(timeout=20)
    if proc.returncode != 0:
        raise AssertionError(
            "Failed-recovery helper did not complete.\n"
            f"stdout:\n{stdout}\n"
            f"stderr:\n{stderr}"
        )
    _wait_for_file(result_path)
    # Keep the Popen object alive until the test ends. On Windows its retained
    # process handle prevents immediate PID reuse while production liveness
    # checks and the browser exercise the recorded terminal PID.
    return proc, json.loads(result_path.read_text(encoding="utf-8"))


def _action_script(scenario: str, stale_fingerprint: str) -> str:
    return textwrap.dedent(
        f"""
        (async () => {{
          const scenario = {json.dumps(scenario)};
          const staleFingerprint = {json.dumps(stale_fingerprint)};
          const byId = (id) => document.getElementById(id);
          const text = (id) => String(byId(id)?.textContent || "");
          const waitFor = async (predicate, label) => {{
            const deadline = Date.now() + 15000;
            while (Date.now() < deadline) {{
              if (predicate()) return;
              await new Promise((resolve) => setTimeout(resolve, 100));
            }}
            throw new Error("Timed out waiting for " + label + "\\nstatus=" + text("diagnostics-recovery-action-status") + "\\ndetail=" + text("diagnostics-recovery-action-detail"));
          }};
          window.showPage("diagnostics");
          window.mediaPipelineRecoverySupportView?.initRecoverySupportEvents?.();
          const previewButton = byId("diagnostics-recovery-preview-button");
          const applyButton = byId("diagnostics-recovery-reconcile-button");
          if (!previewButton || !applyButton) throw new Error("Lifecycle reconciliation controls are missing.");

          if (scenario === "stale") {{
            const result = await window.apiPost("/api/backend/lifecycle/reconcile", {{
              confirm_apply: true,
              dry_run_fingerprint: staleFingerprint,
              reason: "Operator-reviewed terminal stale lifecycle recovery evidence",
            }});
            if (result?.ok === true || result?.data?.applied === true) {{
              throw new Error("Stale lifecycle fingerprint was accepted: " + JSON.stringify(result));
            }}
            const evidence = JSON.stringify(result);
            if (!evidence.includes("changed after preview")) {{
              throw new Error("Stale fingerprint rejection was not explicit: " + evidence);
            }}
            return {{ scenario, result }};
          }}

          const originalApiPost = window.apiPost;
          const posts = [];
          window.apiPost = async (path, body, options) => {{
            const result = await originalApiPost(path, body, options);
            posts.push({{ path, body: body || {{}}, result }});
            return result;
          }};
          try {{
            previewButton.click();
            await waitFor(
              () => posts.some((entry) => entry.path === "/api/backend/lifecycle/reconcile-dry-run")
                && !text("diagnostics-recovery-action-status").includes("Verifying"),
              "lifecycle preview",
            );
            const preview = posts.find((entry) => entry.path === "/api/backend/lifecycle/reconcile-dry-run")?.result;
            if (!preview) throw new Error("Lifecycle preview response was not captured.");
            if (scenario === "blocked") {{
              if (preview?.data?.safe_to_apply === true || applyButton.disabled !== true) {{
                throw new Error("Live helper PID did not keep lifecycle reconcile fail-closed: " + JSON.stringify(preview));
              }}
              if (!text("diagnostics-recovery-action-detail").includes("PID") || !text("diagnostics-recovery-action-detail").includes("Blocker:")) {{
                throw new Error("Blocked preview did not render PID evidence: " + text("diagnostics-recovery-action-detail"));
              }}
              return {{ scenario, posts, preview, applyDisabled: applyButton.disabled }};
            }}
            if (preview?.ok !== true || preview?.data?.safe_to_apply !== true || applyButton.disabled) {{
              throw new Error("Terminal lifecycle evidence did not produce a safe preview: " + JSON.stringify(preview));
            }}
            if (scenario === "preview") {{
              return {{ scenario, posts, preview, fingerprint: preview.data.dry_run_fingerprint }};
            }}
            applyButton.click();
            await waitFor(
              () => posts.some((entry) => entry.path === "/api/backend/lifecycle/reconcile")
                && text("diagnostics-recovery-action-status").includes("reconciled"),
              "lifecycle reconcile apply",
            );
            const applyPosts = posts.filter((entry) => entry.path === "/api/backend/lifecycle/reconcile");
            if (applyPosts.length !== 1 || applyPosts[0].body.confirm_apply !== true) {{
              throw new Error("Lifecycle reconcile apply was not exactly-once and strictly confirmed: " + JSON.stringify(applyPosts));
            }}
            if (applyPosts[0].result?.ok !== true || applyPosts[0].result?.data?.applied !== true) {{
              throw new Error("Lifecycle reconciliation was not applied: " + JSON.stringify(applyPosts[0].result));
            }}
            return {{ scenario, posts, preview, applied: applyPosts[0].result }};
          }} finally {{
            window.apiPost = originalApiPost;
          }}
        }})()
        """
    )


def _post_reload_script() -> str:
    return textwrap.dedent(
        """
        (async () => {
          const byId = (id) => document.getElementById(id);
          const text = (id) => String(byId(id)?.textContent || "");
          const waitFor = async (predicate, label) => {
            const deadline = Date.now() + 15000;
            while (Date.now() < deadline) {
              if (predicate()) return;
              await new Promise((resolve) => setTimeout(resolve, 100));
            }
            throw new Error("Timed out waiting for " + label
              + "\\nrecovery=" + text("diagnostics-recovery-status")
              + "\\nreadiness=" + text("diagnostics-close-readiness")
              + "\\nshutdownDisabled=" + String(byId("backend-shutdown-button")?.disabled));
          };
          window.showPage("diagnostics");
          await window.refreshAll();
          await waitFor(
            () => text("diagnostics-recovery-status").includes("reconciled (complete)")
              && text("diagnostics-close-readiness").includes("Safe to close: yes")
              && byId("backend-shutdown-button")?.disabled === false,
            "reloaded reconciled close-readiness",
          );
          const history = await window.apiGet("/api/commands?limit=20");
          const successful = (history?.entries || []).filter((entry) => entry.command === "backend.lifecycle.reconcile" && entry.data?.applied === true);
          if (successful.length !== 1) {
            throw new Error("Reloaded command journal did not contain exactly one successful reconcile: " + JSON.stringify(history));
          }
          const originalConfirm = window.confirm;
          window.confirm = () => true;
          try {
            await window.requestBackendShutdown();
          } finally {
            window.confirm = originalConfirm;
          }
          await waitFor(() => text("backend-shutdown-status").includes("Backend shutdown requested"), "safe close request");
          return {
            recoveryStatus: text("diagnostics-recovery-status"),
            closeReadiness: text("diagnostics-close-readiness"),
            shutdownStatus: text("backend-shutdown-status"),
            successfulReconcileCount: successful.length,
          };
        })()
        """
    )


def _runner_source() -> str:
    return browser_cdp_runner_prelude() + textwrap.dedent(
        r"""
        async function runtimeValue(client, expression) {
          const result = await client.send("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true });
          if (result.exceptionDetails) {
            throw new Error(result.exceptionDetails.exception?.description || result.exceptionDetails.exception?.value || result.exceptionDetails.text || "browser evaluation failed");
          }
          return result.result?.value;
        }

        async function waitUntilReady(client) {
          const expression = `Boolean(
            document.getElementById("diagnostics-recovery-preview-button")
            && document.getElementById("diagnostics-recovery-reconcile-button")
            && document.getElementById("backend-shutdown-button")
            && typeof window.showPage === "function"
            && typeof window.apiPost === "function"
            && typeof window.apiGet === "function"
            && typeof window.refreshAll === "function"
            && typeof window.requestBackendShutdown === "function"
            && typeof window.mediaPipelineRecoverySupportView?.initRecoverySupportEvents === "function"
          )`;
          const deadline = Date.now() + 20000;
          while (Date.now() < deadline) {
            const ready = await runtimeValue(client, expression);
            if (ready === true) return;
            await sleep(150);
          }
          throw new Error("Lifecycle reconciliation WebView controls did not become ready.");
        }

        async function main() {
          const userDataDir = fs.mkdtempSync(`${payload.tmpRoot.replace(/\\/g, "/")}/chrome-profile-`);
          const browser = launchBrowser([
            "--headless=new", "--disable-gpu", "--disable-background-networking", "--disable-default-apps",
            "--disable-extensions", "--disable-sync", "--metrics-recording-only", "--no-first-run",
            "--no-default-browser-check", `--remote-debugging-port=${payload.port}`,
            `--user-data-dir=${userDataDir}`, payload.url,
          ]);
          let client = null;
          try {
            const wsUrl = await waitForPageWebSocket(payload.port, payload.url);
            client = createCdpClient(wsUrl);
            await client.send("Runtime.enable");
            await client.send("Log.enable");
            await client.send("Page.enable");
            await waitUntilReady(client);
            const action = await runtimeValue(client, payload.actionScript);
            let postReload = null;
            if (payload.scenario === "apply") {
              await client.send("Page.reload", { ignoreCache: true });
              await sleep(750);
              await waitUntilReady(client);
              postReload = await runtimeValue(client, payload.postReloadScript);
            }
            await sleep(300);
            const errorEvents = client.consoleEvents.filter((entry) =>
              (entry.startsWith("error:") || entry.startsWith("warning:"))
              && !entry.includes("Blocked attempt to show a 'beforeunload' confirmation panel")
            );
            if (client.exceptions.length || errorEvents.length) {
              throw new Error(`Browser console/exception noise: ${client.exceptions.concat(errorEvents).join("; ")}`);
            }
            console.log(JSON.stringify({ ok: true, result: { action, postReload } }));
          } finally {
            if (client) client.close();
            await terminateBrowser(browser);
          }
        }
        main().catch((error) => { console.error(error.stack || error.message || String(error)); process.exit(1); });
        """
    )


def _run_browser(
    *,
    browser_path: str,
    url: str,
    scenario: str,
    stale_fingerprint: str = "",
) -> dict[str, object]:
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("Node.js is required for the browser-backed lifecycle reconciliation smoke.")
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as raw_tmp:
        tmp = Path(raw_tmp)
        payload_path = tmp / "lifecycle-reconcile-payload.json"
        runner_path = tmp / "lifecycle-reconcile-runner.cjs"
        payload_path.write_text(
            json.dumps(
                {
                    "browserPath": browser_path,
                    "port": free_port(),
                    "tmpRoot": str(tmp),
                    "url": url,
                    "scenario": scenario,
                    "actionScript": _action_script(scenario, stale_fingerprint),
                    "postReloadScript": _post_reload_script(),
                }
            ),
            encoding="utf-8",
        )
        runner_path.write_text(_runner_source(), encoding="utf-8")
        return run_node_browser_smoke(
            f"Browser-backed lifecycle reconciliation smoke ({scenario})",
            node=node,
            runner_path=runner_path,
            payload_path=payload_path,
            timeout_seconds=70,
        )


class WebViewBrowserLifecycleReconciliationSmoke(unittest.TestCase):
    def test_real_browser_recovers_abnormal_exit_once_then_reloads_safe_close(self) -> None:
        browser_path = find_browser()
        if not browser_path:
            raise unittest.SkipTest("Chrome or Edge is required for the browser-backed lifecycle reconciliation smoke.")

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as raw_root:
            root = Path(raw_root)
            resolved, _source, _output = _write_fixture_state(root)
            resolved.state_root = root / "State"
            state_root = Path(resolved.state_root)
            media_snapshot = capture_media_no_mutation_snapshot(root)
            helper = _start_interrupted_audit_helper(state_root, root / "TestSignals" / "lease.ready")
            service = DummyWorkflowFacadeService(root)
            snapshot = service.build_snapshot(resolved, str(root))
            if snapshot.progress is None:
                snapshot.progress = {}
            snapshot.progress["Status"] = "Completed"
            service.snapshot = snapshot
            service.find_related_pipeline_processes = lambda _resolved: []
            service.read_progress = lambda _resolved: {}
            service.is_progress_stale = lambda _progress: True
            service.read_audit_progress = lambda _resolved: {}
            service.is_audit_progress_stale = lambda _progress: True
            facade = MediaPipelineApplicationFacade(service, app_version="v6-test")
            shutdown_event = threading.Event()
            server = LocalApiServer(
                facade,
                token="browser-lifecycle-reconcile-token",
                resolved_provider=lambda: resolved,
                audit_root_provider=lambda: str(root),
                shutdown_request=shutdown_event.set,
            )
            try:
                server.start()
                before_status, before_history = _get_json(
                    f"{server.url}/api/commands?limit=20",
                    token=server.token,
                )
                self.assertEqual(before_status, 200)
                blocked = _run_browser(
                    browser_path=browser_path,
                    url=f"{server.url}/",
                    scenario="blocked",
                )
                blocked_status, blocked_history = _get_json(
                    f"{server.url}/api/commands?limit=20",
                    token=server.token,
                )
                self.assertEqual(blocked_status, 200)
                self.assertEqual(blocked_history["entries"], before_history["entries"])
                self.assertTrue(blocked["result"]["action"]["applyDisabled"])

                helper_pid = helper.pid
                helper.terminate()
                helper.communicate(timeout=10)
                self.assertEqual(
                    LifecycleLeaseStore(state_root).status()["status"],
                    "stale",
                    f"PID {helper_pid} was still live or reused; recovery must remain fail-closed.",
                )

                recovery_helper, recovery_status = _run_failed_recovery_helper(
                    state_root,
                    root / "TestSignals" / "recovery-result.json",
                )
                self.assertIsNotNone(recovery_helper.returncode)
                self.assertEqual(recovery_status["status"], "blocked")
                self.assertEqual(recovery_status["classification"], "parked")
                facade.set_recovery_status(recovery_status)

                safe_preview = _run_browser(
                    browser_path=browser_path,
                    url=f"{server.url}/",
                    scenario="preview",
                )
                stale_fingerprint = str(safe_preview["result"]["action"]["fingerprint"])
                self.assertTrue(stale_fingerprint)

                LifecycleLeaseStore(state_root).mark_indeterminate(
                    command_id="audit-command-1",
                    route="/api/audit/start",
                    reason="Backend lifecycle state is recovering after stale-preview mutation.",
                )
                stale = _run_browser(
                    browser_path=browser_path,
                    url=f"{server.url}/",
                    scenario="stale",
                    stale_fingerprint=stale_fingerprint,
                )
                self.assertFalse(stale["result"]["action"]["result"]["ok"])

                LifecycleLeaseStore(state_root).mark_indeterminate(
                    command_id="audit-command-1",
                    route="/api/audit/start",
                    reason=RECOVERY_REASON,
                )
                applied = _run_browser(
                    browser_path=browser_path,
                    url=f"{server.url}/",
                    scenario="apply",
                )
                self.assertTrue(shutdown_event.wait(2.0))
                self.assertTrue(applied["result"]["action"]["applied"]["ok"])
                self.assertEqual(applied["result"]["postReload"]["successfulReconcileCount"], 1)
                self.assertIn("reconciled (complete)", applied["result"]["postReload"]["recoveryStatus"])
                self.assertIn("Safe to close: yes", applied["result"]["postReload"]["closeReadiness"])

                history_status, history = _get_json(
                    f"{server.url}/api/commands?limit=20",
                    token=server.token,
                )
                self.assertEqual(history_status, 200)
                reconcile_entries = [
                    entry for entry in history["entries"] if entry.get("command") == "backend.lifecycle.reconcile"
                ]
                terminal_entries = [
                    entry
                    for entry in reconcile_entries
                    if isinstance(entry.get("data"), dict) and "applied" in entry["data"]
                ]
                self.assertEqual(sum(entry["data"].get("applied") is True for entry in terminal_entries), 1)
                self.assertEqual(sum(entry["data"].get("applied") is False for entry in terminal_entries), 1)
                self.assertEqual(len({entry["data"].get("command_id") for entry in terminal_entries}), 2)
                self.assertFalse(state_root.joinpath("Lifecycle").exists())
                archive_manifests = list(state_root.joinpath("LifecycleArchive").glob("*/reconciliation-manifest.json"))
                self.assertEqual(len(archive_manifests), 1)
                archive_manifest = json.loads(archive_manifests[0].read_text(encoding="utf-8"))
                self.assertEqual(archive_manifest["status"], "completed")
                self.assertEqual(len(archive_manifest["archived_paths"]), 3)
                self.assertEqual(
                    LifecycleLeaseStore(state_root).status()["status"],
                    "idle",
                )
                replay_calls: list[tuple[str, dict[str, object], str]] = []
                fresh_recovery = LifecycleRecoveryCoordinator().run(
                    SimpleNamespace(state_root=state_root),
                    resume=lambda route, request, command_id: replay_calls.append((route, request, command_id))
                    or {"ok": True},
                )
                self.assertEqual(fresh_recovery["status"], "complete")
                self.assertEqual(fresh_recovery["classification"], "completed")
                self.assertEqual(replay_calls, [])
            finally:
                if helper.poll() is None:
                    helper.kill()
                    helper.communicate(timeout=10)
                server.stop()
            assert_media_no_mutation(self, media_snapshot)


if __name__ == "__main__":
    unittest.main()
