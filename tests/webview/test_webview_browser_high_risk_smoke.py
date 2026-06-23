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
    from .test_webview_real_media_smoke import _get_json, _write_fixture_state, _write_high_risk_fixture_state
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
    from test_webview_real_media_smoke import _get_json, _write_fixture_state, _write_high_risk_fixture_state
    from webview_browser_smoke_support import (
        assert_media_no_mutation,
        browser_cdp_runner_prelude,
        capture_media_no_mutation_snapshot,
        find_browser as _find_browser,
        free_port as _free_port,
        run_node_browser_smoke,
    )


def _browser_runner_source() -> str:
    return browser_cdp_runner_prelude() + textwrap.dedent(
        r"""
        function highRiskScript(data) {
          return `
          (() => {
            const payload = ${JSON.stringify(data)};
            const errors = [];
            function requireText(id, fragments) {
              const node = document.getElementById(id);
              const text = node ? node.textContent || "" : "";
              for (const fragment of fragments) {
                if (!text.includes(fragment)) {
                  throw new Error(id + " missing " + fragment + "\\nActual:\\n" + text);
                }
              }
            }
            function clone(value) {
              return JSON.parse(JSON.stringify(value));
            }
            function requireFunction(name) {
              if (typeof window[name] !== "function") throw new Error("missing global function " + name);
            }
            [
              "renderQueue", "selectQueueRow",
              "renderPendingPublish", "selectPendingRow"
            ].forEach(requireFunction);
            if (typeof window.mediaPipelineCompletedView?.renderCompleted !== "function") {
              throw new Error("missing mediaPipelineCompletedView.renderCompleted");
            }
            if (typeof window.mediaPipelineCompletedView?.selectCompletedRow !== "function") {
              throw new Error("missing mediaPipelineCompletedView.selectCompletedRow");
            }

            const riskQueue = clone(payload.queue);
            riskQueue.rows = [Object.assign({}, riskQueue.rows[0], {
              status: "invalid",
              operator_status: "blocked by source parse",
              operator_trust_state: "blocked",
              blocked_reason_code: "tv_parse_unreliable",
              blocked_reason: "Episode/season parse was ambiguous; operator must review before launch.",
              runtime_outcome_status: "failed",
              runtime_outcome_freshness_status: "fresh",
              runtime_outcome_error_code: "source_locked",
              runtime_outcome_reason: "Source changed during probe.",
              runtime_checks_deferred: true,
              runtime_check_notes: ["source stability will be rechecked at backend launch"],
              review_flags: ["blocked:tv_parse_unreliable"],
              route_evidence_lines: ["parse confidence below launch threshold"],
              proof_summary: ["source path is visible", "season/episode parse is not trusted"],
            })];
            window.renderQueue(riskQueue);
            window.selectQueueRow(riskQueue.rows[0]);
            requireText("queue-detail", [
              "Row state: blocked",
              "Blocker: tv_parse_unreliable - Episode/season parse was ambiguous; operator must review before launch.",
              "Runtime issue: source_locked - Source changed during probe.",
              "Safe next action: use Queue Diagnostics Cross-Links before launch",
              "Diagnostics handoff:",
              "Mutation guardrail",
            ]);
            requireText("queue-diagnostics-guidance", [
              "Suggested order: open Queue Snapshot, read Last Stderr, then open Run Logs before launching or reprocessing.",
              "Diagnostics bridge:",
            ]);

            const riskCompleted = clone(payload.completed);
            riskCompleted.rows = [Object.assign({}, riskCompleted.rows[0], {
              output_exists: false,
              output_health: "missing output",
              sidecar_exists: false,
              consistency_status: "broken",
              consistency_issues: ["missing_sidecar", "output_path_missing"],
              size_growth_over_5: true,
              size_delta_label: "+110%",
              operator_status: "completed proof conflict",
              operator_trust_state: "broken-output",
              review_flags: ["missing_output", "missing_sidecar", "size_growth_over_5"],
              runtime_outcome_status: "failed",
              runtime_outcome_freshness_status: "fresh",
              runtime_outcome_error_code: "publish_missing_output",
              runtime_outcome_reason: "Completed manifest points at a missing file.",
              proof_summary: ["completed manifest row exists", "output file is missing", "sidecar proof is missing"],
            })];
            window.mediaPipelineCompletedView.renderCompleted(riskCompleted);
            window.mediaPipelineCompletedView.selectCompletedRow(riskCompleted.rows[0]);
            requireText("completed-detail", [
              "Row state: broken-output",
              "Output health: missing output",
              "Consistency issues: missing_sidecar, output_path_missing",
              "Runtime issue: publish_missing_output - Completed manifest points at a missing file.",
              "Size review: output is more than 5% larger than source.",
              "Safe next action: inspect Completed Manifest, Pending Publish, output folder, Run Logs, and Last Stderr before rerun.",
              "Diagnostics handoff:",
              "Mutation guardrail",
            ]);
            requireText("completed-diagnostics-guidance", [
              "Selected output health: missing output",
              "Suggested order: open Completed Manifest, open Pending Publish, then read Last Stderr before rerun or cleanup.",
              "Diagnostics bridge:",
            ]);

            const riskPending = clone(payload.pending);
            riskPending.rows = [Object.assign({}, riskPending.rows[0], {
              state: "unreadable_manifest",
              diagnostic_status: "unreadable_manifest",
              diagnostic_severity: "error",
              drain_recommendation: "do_not_drain",
              ready_to_drain: false,
              local_exists: false,
              missing_sidecar_count: 2,
              operator_trust_state: "do-not-drain",
              operator_guidance: "Do not drain; repair or regenerate the pending manifest first.",
              recovery_class: "manifest_repair",
              recovery_action: "Repair the manifest and missing sidecars before backend drain.",
              issue_summary: "Unreadable manifest, missing payload, and missing sidecars.",
              evidence_fields: ["manifest_path", "local_file", "server_out", "source_path"],
              recommended_open_targets: ["manifest", "local_file", "pending_root"],
              proof_summary: ["manifest unreadable", "payload missing", "sidecars missing"],
              error: "manifest parse failed",
            })];
            window.renderPendingPublish(riskPending, {});
            window.selectPendingRow(riskPending.rows[0]);
            requireText("pending-detail", [
              "Row state: do-not-drain",
              "Diagnostic status: unreadable_manifest",
              "Diagnostic severity: error",
              "Drain recommendation: do_not_drain",
              "Health blockers: backend marked do_not_drain, diagnostic severity is error, local payload missing, 2 missing sidecars, manifest unreadable or invalid",
              "Operator action: Do not drain; repair or regenerate the pending manifest first.",
              "Recovery action: Repair the manifest and missing sidecars before backend drain.",
              "Drain boundary: do not drain this row until blockers are explained by pending diagnostics and logs.",
              "Diagnostics handoff:",
              "Mutation guardrail",
            ]);
            requireText("pending-diagnostics-guidance", [
              "Selected diagnostic status: unreadable_manifest",
              "Drain recommendation: do_not_drain",
              "Recovery class: manifest_repair",
              "Selected-row diagnostic order: open the row manifest, read Last Stderr, then open Run Logs before another drain attempt.",
              "Diagnostics bridge:",
            ]);
            return {
              ok: true,
              queueDetail: document.getElementById("queue-detail").textContent,
              completedDetail: document.getElementById("completed-detail").textContent,
              pendingDetail: document.getElementById("pending-detail").textContent,
            };
          })()
          `;
        }

        function backendProducedHighRiskScript(data) {
          return `
          (() => {
            const payload = ${JSON.stringify(data)};
            function requireText(id, fragments) {
              const node = document.getElementById(id);
              const text = node ? node.textContent || "" : "";
              for (const fragment of fragments) {
                if (!text.includes(fragment)) {
                  throw new Error(id + " missing " + fragment + "\\nActual:\\n" + text);
                }
              }
            }
            function firstRow(payloadName) {
              const rows = Array.isArray(payload[payloadName]?.rows) ? payload[payloadName].rows : [];
              if (!rows.length) throw new Error(payloadName + " did not contain backend-produced rows");
              return rows[0];
            }
            function requireFunction(name) {
              if (typeof window[name] !== "function") throw new Error("missing global function " + name);
            }
            [
              "renderQueue", "selectQueueRow",
              "renderPendingPublish", "selectPendingRow"
            ].forEach(requireFunction);
            if (typeof window.mediaPipelineCompletedView?.renderCompleted !== "function") {
              throw new Error("missing mediaPipelineCompletedView.renderCompleted");
            }
            if (typeof window.mediaPipelineCompletedView?.selectCompletedRow !== "function") {
              throw new Error("missing mediaPipelineCompletedView.selectCompletedRow");
            }

            const queueRow = firstRow("queue");
            window.renderQueue(payload.queue);
            window.selectQueueRow(queueRow);
            requireText("queue-detail", [
              "Row state: blocked",
              "Blocker: tv_parse_unreliable - tv-parse: missing season/episode",
              "Runtime issue: source_locked - Source changed during probe.",
              "Safe next action: use Queue Diagnostics Cross-Links before launch",
              "Diagnostics handoff:",
              "Mutation guardrail",
            ]);
            requireText("queue-diagnostics-guidance", [
              "Suggested order: open Queue Snapshot, read Last Stderr, then open Run Logs before launching or reprocessing.",
              "Diagnostics bridge:",
            ]);

            const completedRow = firstRow("completed");
            window.mediaPipelineCompletedView.renderCompleted(payload.completed);
            window.mediaPipelineCompletedView.selectCompletedRow(completedRow);
            requireText("completed-detail", [
              "Row state: broken-output",
              "Output health: completed metadata without media",
              "Consistency issues: missing_output, missing_sidecar",
              "Runtime issue: publish_missing_output - Completed manifest points at a missing file.",
              "Size review: output is more than 5% larger than source.",
              "Safe next action: inspect Completed Manifest, Pending Publish, output folder, Run Logs, and Last Stderr before rerun.",
              "Diagnostics handoff:",
              "Mutation guardrail",
            ]);
            requireText("completed-diagnostics-guidance", [
              "Selected output health: completed metadata without media",
              "Suggested order: open Completed Manifest, open Pending Publish, then read Last Stderr before rerun or cleanup.",
              "Diagnostics bridge:",
            ]);

            const pendingRow = firstRow("pending");
            window.renderPendingPublish(payload.pending, {});
            window.selectPendingRow(pendingRow);
            requireText("pending-detail", [
              "Row state: do-not-drain",
              "Diagnostic status: unreadable_manifest",
              "Diagnostic severity: error",
              "Drain recommendation: do_not_drain",
              "Health blockers: backend marked do_not_drain, diagnostic severity is error, local payload missing, manifest unreadable or invalid, row error",
              "Operator action: Manifest could not be read. Check file locking, permissions, and JSON validity before drain.",
              "Recovery action: Check locking, permissions, and JSON validity before another drain attempt.",
              "Drain boundary: do not drain this row until blockers are explained by pending diagnostics and logs.",
              "Diagnostics handoff:",
              "Mutation guardrail",
            ]);
            requireText("pending-diagnostics-guidance", [
              "Selected diagnostic status: unreadable_manifest",
              "Drain recommendation: do_not_drain",
              "Recovery class: manifest_repair",
              "Selected-row diagnostic order: open the row manifest, read Last Stderr, then open Run Logs before another drain attempt.",
              "Diagnostics bridge:",
            ]);
            return {
              ok: true,
              queueDetail: document.getElementById("queue-detail").textContent,
              completedDetail: document.getElementById("completed-detail").textContent,
              pendingDetail: document.getElementById("pending-detail").textContent,
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
                expression: `Boolean(document.getElementById("queue-detail") && typeof window.renderQueue === "function" && typeof window.mediaPipelineCompletedView?.renderCompleted === "function" && typeof window.renderPendingPublish === "function")`,
                returnByValue: true,
              });
              if (ready.result?.value === true) break;
              await sleep(150);
            }
            const ready = await client.send("Runtime.evaluate", {
              expression: `Boolean(document.getElementById("queue-detail") && typeof window.renderQueue === "function" && typeof window.mediaPipelineCompletedView?.renderCompleted === "function" && typeof window.renderPendingPublish === "function")`,
              returnByValue: true,
            });
            if (ready.result?.value !== true) {
              throw new Error("WebView globals or detail DOM nodes did not become ready.");
            }
            const result = await client.send("Runtime.evaluate", {
              expression: payload.mutateRows === false
                ? backendProducedHighRiskScript(payload.data)
                : highRiskScript(payload.data),
              awaitPromise: true,
              returnByValue: true,
            });
            if (result.exceptionDetails) {
              const details = result.exceptionDetails;
              const exception = details.exception || {};
              throw new Error(exception.description || exception.value || details.text || "browser evaluation failed");
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


def _run_browser_high_risk_smoke(
    *,
    browser_path: str,
    url: str,
    queue: dict[str, object],
    completed: dict[str, object],
    pending: dict[str, object],
    mutate_rows: bool = True,
) -> dict[str, object]:
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("Node.js is required for the browser-backed WebView high-risk smoke.")
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as raw_tmp:
        tmp = Path(raw_tmp)
        port = _free_port()
        payload_path = tmp / "browser-high-risk-payload.json"
        runner_path = tmp / "browser-high-risk-runner.cjs"
        payload_path.write_text(
            json.dumps(
                {
                    "browserPath": browser_path,
                    "port": port,
                    "tmpRoot": str(tmp),
                    "url": url,
                    "mutateRows": mutate_rows,
                    "data": {"queue": queue, "completed": completed, "pending": pending},
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        runner_path.write_text(_browser_runner_source(), encoding="utf-8")
        return run_node_browser_smoke(
            "Browser-backed WebView high-risk row smoke",
            node=node,
            runner_path=runner_path,
            payload_path=payload_path,
            timeout_seconds=45,
        )


class WebViewBrowserHighRiskSmoke(unittest.TestCase):
    def test_real_browser_renders_high_risk_selected_row_guidance(self) -> None:
        browser_path = _find_browser()
        if not browser_path:
            raise unittest.SkipTest("Chrome or Edge is required for the browser-backed WebView high-risk smoke.")

        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved, _source, _output = _write_fixture_state(root)
            media_snapshot = capture_media_no_mutation_snapshot(root)
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            server = LocalApiServer(
                facade,
                token="browser-smoke-token",
                resolved_provider=lambda: resolved,
                audit_root_provider=lambda: str(root),
            )
            try:
                server.start()
                queue_status, queue = _get_json(f"{server.url}/api/queue", token="browser-smoke-token")
                completed_status, completed = _get_json(f"{server.url}/api/completed", token="browser-smoke-token")
                pending_status, pending = _get_json(f"{server.url}/api/pending-publish", token="browser-smoke-token")
                self.assertEqual(queue_status, 200)
                self.assertEqual(completed_status, 200)
                self.assertEqual(pending_status, 200)
                result = _run_browser_high_risk_smoke(
                    browser_path=browser_path,
                    url=f"{server.url}/",
                    queue=queue,
                    completed=completed,
                    pending=pending,
                )
            finally:
                server.stop()
            assert_media_no_mutation(self, media_snapshot)

        self.assertTrue(result["ok"])
        browser_result = result["result"]
        self.assertIn("Row state: blocked", browser_result["queueDetail"])
        self.assertIn("Row state: broken-output", browser_result["completedDetail"])
        self.assertIn("Row state: do-not-drain", browser_result["pendingDetail"])

    def test_real_browser_renders_backend_produced_high_risk_rows(self) -> None:
        browser_path = _find_browser()
        if not browser_path:
            raise unittest.SkipTest("Chrome or Edge is required for the browser-backed WebView high-risk smoke.")

        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved, events = _write_high_risk_fixture_state(root)
            media_snapshot = capture_media_no_mutation_snapshot(root)
            service = DummyWorkflowFacadeService(root)
            service.read_pipeline_events_tail = lambda _resolved, line_count=300: events  # type: ignore[method-assign]
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            server = LocalApiServer(
                facade,
                token="browser-smoke-token",
                resolved_provider=lambda: resolved,
                audit_root_provider=lambda: str(root),
            )
            try:
                server.start()
                queue_status, queue = _get_json(f"{server.url}/api/queue", token="browser-smoke-token")
                completed_status, completed = _get_json(f"{server.url}/api/completed", token="browser-smoke-token")
                pending_status, pending = _get_json(f"{server.url}/api/pending-publish", token="browser-smoke-token")
                self.assertEqual(queue_status, 200)
                self.assertEqual(completed_status, 200)
                self.assertEqual(pending_status, 200)
                self.assertEqual(queue["rows"][0]["operator_trust_state"], "blocked")
                self.assertEqual(queue["rows"][0]["runtime_outcome_error_code"], "source_locked")
                self.assertEqual(completed["rows"][0]["operator_trust_state"], "broken-output")
                self.assertIn("missing_output", completed["rows"][0]["consistency_issues"])
                self.assertEqual(completed["rows"][0]["runtime_outcome_error_code"], "publish_missing_output")
                self.assertEqual(pending["rows"][0]["operator_trust_state"], "do-not-drain")
                self.assertEqual(pending["rows"][0]["diagnostic_status"], "unreadable_manifest")
                self.assertEqual(pending["rows"][0]["drain_recommendation"], "do_not_drain")
                result = _run_browser_high_risk_smoke(
                    browser_path=browser_path,
                    url=f"{server.url}/",
                    queue=queue,
                    completed=completed,
                    pending=pending,
                    mutate_rows=False,
                )
            finally:
                server.stop()
            assert_media_no_mutation(self, media_snapshot)

        self.assertTrue(result["ok"])
        browser_result = result["result"]
        self.assertIn("Row state: blocked", browser_result["queueDetail"])
        self.assertIn("Runtime issue: source_locked", browser_result["queueDetail"])
        self.assertIn("Row state: broken-output", browser_result["completedDetail"])
        self.assertIn("Runtime issue: publish_missing_output", browser_result["completedDetail"])
        self.assertIn("Row state: do-not-drain", browser_result["pendingDetail"])


if __name__ == "__main__":
    unittest.main()
