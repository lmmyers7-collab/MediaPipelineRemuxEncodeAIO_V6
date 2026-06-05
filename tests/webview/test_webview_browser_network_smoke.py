from __future__ import annotations

import json
import shutil
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.desktop.api import LocalApiServer
from mediapipeline.desktop.application import MediaPipelineApplicationFacade

try:  # unittest discovery can import tests as top-level modules or package modules.
    from .test_application_facade import DummyWorkflowFacadeService
    from .test_webview_real_media_smoke import _write_fixture_state
    from .webview_browser_smoke_support import (
        assert_media_no_mutation,
        browser_cdp_runner_prelude,
        capture_media_no_mutation_snapshot,
        find_browser as _find_browser,
        free_port as _free_port,
        run_node_browser_smoke,
    )
except ImportError:  # pragma: no cover - fallback for direct test execution
    from test_application_facade import DummyWorkflowFacadeService
    from test_webview_real_media_smoke import _write_fixture_state
    from webview_browser_smoke_support import (
        assert_media_no_mutation,
        browser_cdp_runner_prelude,
        capture_media_no_mutation_snapshot,
        find_browser as _find_browser,
        free_port as _free_port,
        run_node_browser_smoke,
    )


def _browser_network_runner_source() -> str:
    return browser_cdp_runner_prelude() + textwrap.dedent(
        r"""
        function networkScript(data) {
          return `
          (async () => {
            const payload = ${JSON.stringify(data)};
            const posted = [];
            const opened = [];
            function byId(id) { return document.getElementById(id); }
            function text(id) { const node = byId(id); return node ? node.textContent || "" : ""; }
            function requireText(id, fragments) {
              const actual = text(id);
              for (const fragment of fragments) {
                if (!actual.includes(fragment)) throw new Error(id + " missing " + fragment + "\\nActual:\\n" + actual);
              }
            }
            function requireFunction(name) {
              if (typeof window[name] !== "function") throw new Error("missing global function " + name);
            }
            function setSelect(id, value) {
              const node = byId(id);
              if (!node) throw new Error("missing select " + id);
              node.value = value;
              node.dispatchEvent(new Event("change", { bubbles: true }));
            }
            function setInput(id, value) {
              const node = byId(id);
              if (!node) throw new Error("missing input " + id);
              node.value = value;
              node.dispatchEvent(new Event("input", { bubbles: true }));
            }
            function click(selector, label) {
              const node = document.querySelector(selector);
              if (!node) throw new Error("missing " + label + " selector " + selector);
              node.click();
            }
            [
              "showPage",
              "renderNetworkView",
              "renderNetworkLifecycleHandoff",
              "networkLifecycleRows",
              "renderNetworkStateFiles",
              "initNetworkViewEvents",
            ].forEach(requireFunction);

            window.apiPost = async (url, body) => {
              posted.push({ url: String(url || ""), body });
              return { ok: true, command: "diagnostics.open", message: "browser smoke mocked diagnostics open", data: { target: body?.target || "" } };
            };
            window.open = (url) => {
              opened.push(String(url || ""));
              return null;
            };

            window.showPage("network");
            window.mediaPipelineNetworkView.renderNetworkView(payload);
            requireText("network-status", ["Read-only"]);
            requireText("network-readiness-summary", ["Lifecycle owner: backend Network diagnostics / Python dispatcher.", "WebView status: read-only"]);
            requireText("network-lifecycle-summary", [
              "Network lifecycle handoff:",
              "Decision rule: WebView Network can be trusted for read-only evidence only",
              "Mutation guardrail",
            ]);
            requireText("network-evidence-summary", ["Network evidence checklist:", "persisted worker state is visible through /api/network/workers"]);
            requireText("network-state-files-summary", ["Network runtime state file evidence:", "Files: 3; present=2; missing=1; unreadable=0", "Read order: Cluster log -> Coordinator in-flight registry -> Local worker state"]);
            requireText("network-worker-summary", ["Lifecycle controls remain backend-owned", "Warning(s):", "coordinator persisted state may be stale"]);
            requireText("network-worker-progress-summary", ["Worker progress:", "Active worker bars:", "Mutation guardrail: this panel does not start/stop workers"]);
            requireText("network-worker-progress-bars", ["worker-active", "42%", "worker-failed"]);
            requireText("network-worker-filter-summary", ["Showing 3/3 persisted worker rows", "No active/problem worker rows are hidden", "Mutation guardrail"]);

            const lifecycleRows = Array.from(document.querySelectorAll('#network-lifecycle-rows tr[data-selectable-row="true"]'));
            if (lifecycleRows.length < 6) throw new Error("expected network lifecycle handoff rows, saw " + lifecycleRows.length);
            const claimHealthRow = lifecycleRows.find((row) => (row.textContent || "").includes("Claim and worker health"));
            if (!claimHealthRow) throw new Error("missing claim health lifecycle row");
            claimHealthRow.click();
            requireText("network-lifecycle-detail", [
              "Gate: Claim and worker health",
              "Failed/stale/offline rows: 1",
              "Pending done report",
              "Mutation guardrail",
            ]);

            click('#network-state-files-rows tr[data-selectable-row="true"]', "network state file row");
            requireText("network-state-files-detail", ["File:", "Status:", "Safe next step:", "Mutation guardrail"]);

            click('#network-worker-rows tr[data-selectable-row="true"]', "network worker row");
            requireText("network-worker-detail", ["Worker:", "Lifecycle controls remain backend-owned"]);

            setSelect("network-worker-status-filter", "idle");
            requireText("network-worker-filter-summary", ["Showing 1/3 persisted worker rows", "2 active/problem worker rows are hidden", "Clear or change filters before lifecycle decisions"]);

            setSelect("network-worker-status-filter", "");
            setInput("network-worker-filter", "failed-job");
            requireText("network-worker-filter-summary", ["Showing 1/3 persisted worker rows", "1 active/problem worker row is hidden", "Mutation guardrail"]);
            requireText("network-worker-detail", ["failed-job", "Error: ffmpeg exited 1"]);

            setInput("network-worker-filter", "no-match-filter");
            requireText("network-worker-filter-summary", ["Showing 0/3 persisted worker rows", "2 active/problem worker rows are hidden"]);
            requireText("network-worker-detail", ["No network worker row selected."]);

            if (posted.some((entry) => !String(entry.url).includes("/api/diagnostics/open"))) {
              throw new Error("Network smoke observed unexpected POST target: " + JSON.stringify(posted));
            }
            return {
              ok: true,
              filterSummary: text("network-worker-filter-summary"),
              lifecycleStatus: text("network-lifecycle-status"),
              lifecycleSummary: text("network-lifecycle-summary"),
              evidenceStatus: text("network-evidence-status"),
              stateFilesStatus: text("network-state-files-status"),
              stateFilesSummary: text("network-state-files-summary"),
              workerStatus: text("network-worker-status"),
              posted,
              opened,
            };
          })()
          `;
        }

        async function main() {
          const userDataDir = fs.mkdtempSync(`${payload.tmpRoot.replace(/\\/g, "/")}/chrome-profile-`);
          const browser = launchBrowser([
            "--headless=new",
            "--disable-gpu",
            "--disable-background-networking",
            "--disable-default-apps",
            "--disable-extensions",
            "--disable-sync",
            "--metrics-recording-only",
            "--no-first-run",
            "--no-default-browser-check",
            `--remote-debugging-port=${payload.port}`,
            `--user-data-dir=${userDataDir}`,
            payload.url,
          ]);
          let client = null;
          try {
            const wsUrl = await waitForPageWebSocket(payload.port, payload.url);
            client = createCdpClient(wsUrl);
            await client.send("Runtime.enable");
            await client.send("Log.enable");
            await client.send("Page.enable");
            const deadline = Date.now() + 20000;
            while (Date.now() < deadline) {
              const ready = await client.send("Runtime.evaluate", {
                expression: `Boolean(document.getElementById("network-worker-filter-summary") && document.getElementById("network-state-files-summary") && document.getElementById("network-lifecycle-summary") && typeof window.mediaPipelineNetworkView.renderNetworkView === "function" && typeof window.mediaPipelineNetworkView.renderNetworkLifecycleHandoff === "function" && typeof window.mediaPipelineNetworkView.networkLifecycleRows === "function" && typeof window.mediaPipelineNetworkView.renderNetworkStateFiles === "function" && typeof window.showPage === "function")`,
                returnByValue: true,
              });
              if (ready.result?.value === true) break;
              await sleep(150);
            }
            const ready = await client.send("Runtime.evaluate", {
              expression: `Boolean(document.getElementById("network-worker-filter-summary") && document.getElementById("network-state-files-summary") && document.getElementById("network-lifecycle-summary") && typeof window.mediaPipelineNetworkView.renderNetworkView === "function" && typeof window.mediaPipelineNetworkView.renderNetworkLifecycleHandoff === "function" && typeof window.mediaPipelineNetworkView.networkLifecycleRows === "function" && typeof window.mediaPipelineNetworkView.renderNetworkStateFiles === "function" && typeof window.showPage === "function")`,
              returnByValue: true,
            });
            if (ready.result?.value !== true) throw new Error("Network WebView globals or DOM nodes did not become ready.");
            const result = await client.send("Runtime.evaluate", {
              expression: networkScript(payload.networkPayload),
              awaitPromise: true,
              returnByValue: true,
            });
            if (result.exceptionDetails) {
              const details = result.exceptionDetails;
              throw new Error(details.exception?.description || details.exception?.value || details.text || "browser evaluation failed");
            }
            await sleep(750);
            const errorEvents = client.consoleEvents.filter((entry) => entry.startsWith("error:") || entry.startsWith("warning:"));
            if (client.exceptions.length || errorEvents.length) {
              throw new Error(`Browser console/exception noise: ${client.exceptions.concat(errorEvents).join("; ")}`);
            }
            console.log(JSON.stringify({ ok: true, result: result.result?.value || {} }));
          } finally {
            if (client) client.close();
            await terminateBrowser(browser);
          }
        }

        main().catch((error) => {
          console.error(error.stack || error.message || String(error));
          process.exit(1);
        });
        """
    )


def _run_browser_network_smoke(*, browser_path: str, url: str, network_payload: dict[str, object]) -> dict[str, object]:
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("Node.js is required for the browser-backed WebView Network smoke.")
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as raw_tmp:
        tmp = Path(raw_tmp)
        port = _free_port()
        payload_path = tmp / "browser-network-payload.json"
        runner_path = tmp / "browser-network-runner.cjs"
        payload_path.write_text(
            json.dumps(
                {
                    "browserPath": browser_path,
                    "port": port,
                    "tmpRoot": str(tmp),
                    "url": url,
                    "networkPayload": network_payload,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        runner_path.write_text(_browser_network_runner_source(), encoding="utf-8")
        return run_node_browser_smoke(
            "Browser-backed WebView Network smoke",
            node=node,
            runner_path=runner_path,
            payload_path=payload_path,
            timeout_seconds=60,
        )


def _network_payload(root: Path) -> dict[str, object]:
    return {
        "settings": {
            "config": {
                "NetworkRole": "coordinator",
                "CoordinatorPort": 7830,
                "CoordinatorBindAddress": "0.0.0.0",
                "CoordinatorAlsoEncodeLocally": False,
                "CoordinatorHeartbeatTimeoutMins": 5,
                "WorkerPollIntervalSecs": 10,
            },
            "field_definitions": [],
        },
        "contract": {
            "schema_version": "local_api_contract.v1",
            "auth": {"public_routes": ["/api/health"]},
            "routes": [
                {"path": "/api/network/workers", "method": "GET", "effect": "none", "auth_required": True},
                {"path": "/api/diagnostics/open", "method": "POST", "effect": "open-path", "auth_required": True},
            ],
        },
        "closeReadiness": {"safe_to_close": True, "reason": "idle"},
        "snapshot": {"pipeline_state": "idle", "queue_depth": 0},
        "networkWorkers": {
            "source": "runtime_state_files",
            "role": "coordinator",
            "active_count": 1,
            "idle_count": 1,
            "session_completed": 12,
            "session_failed": 1,
            "coordinator_inflight_path": str(root / "State" / "Network" / "coordinator_inflight.json"),
            "worker_state_path": str(root / "State" / "Network" / "worker_state.json"),
            "cluster_log_path": str(root / "RunLogs" / "cluster.log"),
            "state_files": [
                {
                    "key": "coordinator_inflight",
                    "label": "Coordinator in-flight registry",
                    "path": str(root / "State" / "Network" / "coordinator_inflight.json"),
                    "purpose": "Tracks active and idle worker rows persisted by the coordinator dispatcher.",
                    "exists": True,
                    "status": "present",
                    "size_bytes": 512,
                    "modified_at": "2026-05-15T20:00:00+00:00",
                    "age_seconds": 120,
                    "error": "",
                },
                {
                    "key": "worker_state",
                    "label": "Local worker state",
                    "path": str(root / "State" / "Network" / "worker_state.json"),
                    "purpose": "Tracks the current local worker claim and any pending done report.",
                    "exists": True,
                    "status": "present",
                    "size_bytes": 128,
                    "modified_at": "2026-05-15T20:01:00+00:00",
                    "age_seconds": 60,
                    "error": "",
                },
                {
                    "key": "cluster_log",
                    "label": "Cluster log",
                    "path": str(root / "RunLogs" / "cluster.log"),
                    "purpose": "Records coordinator/worker network lifecycle and claim events.",
                    "exists": False,
                    "status": "missing",
                    "size_bytes": 0,
                    "modified_at": "",
                    "age_seconds": None,
                    "error": "",
                },
            ],
            "warnings": ["coordinator persisted state may be stale"],
            "worker_state": {},
            "worker_progress": {
                "schema_version": "desktop_network_worker_progress.v1",
                "mode": "worker_progress",
                "status": "blocked",
                "active_count": 1,
                "blocked_count": 1,
                "warning_count": 0,
                "bar_count": 3,
                "summary_lines": [
                    "Worker progress: blocked",
                    "Role: coordinator",
                    "Progress bars: 3",
                    "Active worker bars: 1",
                    "Blocked/stale worker bars: 1",
                    "Warning worker bars: 0",
                    "Mutation guardrail: Network progress is read-only persisted runtime evidence; WebView does not start/stop workers, reclaim jobs, release claims, send done reports, mutate queue state, or touch media files.",
                ],
                "progress_bars": [
                    {
                        "id": "network_mode",
                        "label": "Network mode",
                        "mode": "determinate",
                        "percent": 100,
                        "status": "active",
                        "detail": "role=coordinator; worker_rows=3; warnings=1",
                        "source": "desktop_network_workers.v1",
                    },
                    {
                        "id": "network_worker_worker_a_active_job",
                        "label": "worker-active",
                        "mode": "determinate",
                        "percent": 42,
                        "status": "active",
                        "detail": "file=Episode 01.mkv; stage=encoding; heartbeat_age=12s; job=active-job",
                        "source": "coordinator_inflight",
                    },
                    {
                        "id": "network_worker_worker_b_failed_job",
                        "label": "worker-failed",
                        "mode": "determinate",
                        "percent": 63,
                        "status": "blocked",
                        "detail": "file=Episode 02.mkv; stage=failed; heartbeat_age=900s; job=failed-job; error=ffmpeg exited 1",
                        "source": "coordinator_inflight",
                        "stale": True,
                    },
                ],
                "read_only": True,
            },
            "rows": [
                {
                    "worker_name": "worker-active",
                    "worker_id": "worker-a",
                    "status": "active",
                    "job_id": "active-job",
                    "current_file_name": "Episode 01.mkv",
                    "current_stage": "encoding",
                    "progress_percent": 42,
                    "heartbeat_age_seconds": 12,
                    "files_completed": 3,
                    "total_gb_encoded": 15.2,
                    "avg_speed_gbh": 48.1,
                },
                {
                    "worker_name": "worker-failed",
                    "worker_id": "worker-b",
                    "status": "failed",
                    "job_id": "failed-job",
                    "current_file_name": "Episode 02.mkv",
                    "current_stage": "failed",
                    "progress_percent": 63,
                    "heartbeat_age_seconds": 900,
                    "return_code": 1,
                    "error": "ffmpeg exited 1",
                },
                {
                    "worker_name": "worker-idle",
                    "worker_id": "worker-c",
                    "status": "idle",
                    "job_id": "",
                    "current_file_name": "",
                    "current_stage": "idle",
                    "files_completed": 9,
                    "total_gb_encoded": 88.0,
                    "avg_speed_gbh": 52.0,
                },
            ],
        },
    }


class WebViewBrowserNetworkSmoke(unittest.TestCase):
    def test_real_browser_network_worker_filters_warn_when_hiding_review_rows(self) -> None:
        browser_path = _find_browser()
        if not browser_path:
            raise unittest.SkipTest("Chrome or Edge is required for the browser-backed WebView Network smoke.")

        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved, _source, _output = _write_fixture_state(root)
            media_snapshot = capture_media_no_mutation_snapshot(root)
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v6-test")
            server = LocalApiServer(
                facade,
                token="browser-network-smoke-token",
                resolved_provider=lambda: resolved,
                audit_root_provider=lambda: str(root),
            )
            try:
                server.start()
                result = _run_browser_network_smoke(
                    browser_path=browser_path,
                    url=f"{server.url}/",
                    network_payload=_network_payload(root),
                )
            finally:
                server.stop()
            assert_media_no_mutation(self, media_snapshot)

        self.assertTrue(result["ok"])
        browser_result = result["result"]
        self.assertEqual(browser_result["lifecycleStatus"], "Blocked review")
        self.assertIn("Network lifecycle handoff:", browser_result["lifecycleSummary"])
        self.assertEqual(browser_result["evidenceStatus"], "Blocked review")
        self.assertEqual(browser_result["stateFilesStatus"], "Review")
        self.assertIn("Network runtime state file evidence:", browser_result["stateFilesSummary"])
        self.assertIn("Showing 0/3 persisted worker rows", browser_result["filterSummary"])
        self.assertEqual(browser_result["posted"], [])




