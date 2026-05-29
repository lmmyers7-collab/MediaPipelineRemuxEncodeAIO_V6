from __future__ import annotations

import json
import shutil
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mediapipeline_desktop_app.api import LocalApiServer
from mediapipeline_desktop_app.application import MediaPipelineApplicationFacade

try:  # unittest discovery can import tests as top-level modules or package modules.
    from .test_application_facade import DummyWorkflowFacadeService
    from .test_webview_real_media_smoke import _get_json, _write_fixture_state
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
    from test_webview_real_media_smoke import _get_json, _write_fixture_state
    from webview_browser_smoke_support import (
        assert_media_no_mutation,
        browser_cdp_runner_prelude,
        capture_media_no_mutation_snapshot,
        find_browser as _find_browser,
        free_port as _free_port,
        run_node_browser_smoke,
    )


def _browser_pending_drain_guard_runner_source() -> str:
    return browser_cdp_runner_prelude() + textwrap.dedent(
        r"""
        function pendingDrainGuardScript(data) {
          return `
          (async () => {
            const payload = ${JSON.stringify(data)};
            const posts = [];
            let confirmCalls = 0;
            function byId(id) { return document.getElementById(id); }
            function text(id) { const node = byId(id); return node ? node.textContent || "" : ""; }
            function requireFunction(name) {
              if (typeof window[name] !== "function") throw new Error("missing global function " + name);
            }
            function requireText(id, fragments) {
              const actual = text(id);
              for (const fragment of fragments) {
                if (!actual.includes(fragment)) throw new Error(id + " missing " + fragment + "\\nActual:\\n" + actual);
              }
            }
            async function waitFor(predicate, label) {
              const deadline = Date.now() + 8000;
              let lastError = null;
              while (Date.now() < deadline) {
                try {
                  if (predicate()) return;
                } catch (error) {
                  lastError = error;
                }
                await new Promise((resolve) => setTimeout(resolve, 100));
              }
              throw new Error("Timed out waiting for " + label + (lastError ? ": " + lastError.message : "") + "\\nPending state:\\n" + [
                "guardStatus=" + text("pending-drain-guard-status"),
                "guardSummary=" + text("pending-drain-guard-summary"),
                "drainStatus=" + text("pending-drain-status"),
                "drainDetail=" + text("pending-drain-detail"),
                "postDrainTrustStatus=" + text("pending-post-drain-trust-status"),
                "postDrainTrustSummary=" + text("pending-post-drain-trust-summary"),
                "recoveryStatus=" + text("pending-recovery-plan-status"),
                "recoveryDetail=" + text("pending-recovery-plan-detail"),
              ].join("\\n"));
            }
            [
              "renderPendingPublish",
              "renderPendingRecoveryPlanResult",
              "renderPendingDrainGuard",
              "renderPendingPostDrainTrust",
              "pendingPostDrainTrustRows",
              "startPendingPublishDrain",
              "pendingDrainGuardState",
              "getCommandHistory"
            ].forEach(requireFunction);

            window.confirm = () => {
              confirmCalls += 1;
              return true;
            };
            window.apiPost = async (path, body) => {
              posts.push({ path, body });
              return { ok: true, message: "unexpected mocked post", data: { path, body } };
            };

            window.renderPendingPublish(payload.pending, {});
            await waitFor(
              () => ["Allowed", "Review confirm", "Blocked"].includes(text("pending-drain-guard-status")),
              "initial guard render",
            );
            const initialGuardStatus = text("pending-drain-guard-status");
            if (initialGuardStatus === "Blocked") {
              throw new Error("fixture unexpectedly started blocked; cannot prove recovery-plan guard refresh");
            }
            requireText("pending-post-drain-trust-summary", [
              "Pending Publish post-drain trust review:",
              "Decision rule: a drain is trusted only when current parked rows",
              "Mutation guardrail: this review is read-only",
            ]);
            requireText("pending-post-drain-trust-rows", [
              "Current parked state",
              "blocking=",
              "Durable drain summary",
              "Completed/Pending proof rows",
              "Decision boundary",
            ]);

            const row = Array.isArray(payload.pending.rows) && payload.pending.rows.length ? payload.pending.rows[0] : {};
            const mixedPending = JSON.parse(JSON.stringify(payload.pending));
            mixedPending.rows = [
              Object.assign({}, row, {
                row_key: "ready-filter-visible-row",
                state: "ready",
                diagnostic_status: "ok",
                diagnostic_severity: "info",
                drain_recommendation: "ready",
                ready_to_drain: true,
                issue_summary: "",
              }),
              Object.assign({}, row, {
                row_key: "hidden-blocked-pending-row",
                state: "unreadable_manifest",
                diagnostic_status: "unreadable_manifest",
                diagnostic_severity: "error",
                drain_recommendation: "do_not_drain",
                ready_to_drain: false,
                local_file: "PendingServerPush/hidden-blocked.mkv",
                server_out: "Out/hidden-blocked.mkv",
                issue_summary: "Hidden blocked row should still control backend drain scope.",
              }),
            ];
            mixedPending.count = 2;
            mixedPending.ready_count = 1;
            mixedPending.issue_count = 1;
            mixedPending.health_count = 1;
            byId("pending-investigation-filter").value = "ready_to_drain";
            window.renderPendingPublish(mixedPending, {});
            window.mediaPipelinePendingPublishView.renderPendingRows();
            await waitFor(
              () => text("pending-drain-guard-status") === "Review confirm"
                && text("pending-drain-guard-summary").includes("Pending table filter: active;")
                && text("pending-drain-guard-summary").includes("Backend drain scope remains all loaded parked rows")
                && text("pending-drain-confidence-summary").includes("Display filter / drain scope"),
              "guard reports active filter scope before drain",
            );
            requireText("pending-drain-confidence-summary", [
              "Display filter / drain scope",
            ]);
            requireText("pending-backend-scope-summary", [
              "Backend drain scope preview:",
              "visible after filters:",
              "hidden blocked/review rows:",
              "Backend drain route: /api/pipeline/start with mode=drain_pending_pushes",
            ]);
            requireText("pending-backend-scope-rows", [
              "Backend drain authority",
              "Display filter vs drain scope",
              "Recovery dry-run evidence",
            ]);
            requireText("pending-post-drain-trust-summary", [
              "Pending Publish post-drain trust review:",
              "First action:",
              "Mutation guardrail: this review is read-only",
            ]);
            requireText("pending-post-drain-trust-rows", [
              "Current parked state",
              "blocking=",
              "Parked rows still exist",
              "Sample Validation",
            ]);
            const filterScopeDecisionRow = Array.from(document.querySelectorAll("#pending-drain-decision-rows tr"))
              .find((candidate) => candidate.textContent.includes("Display filter / backend drain scope"));
            if (!filterScopeDecisionRow) throw new Error("missing Display filter / backend drain scope row");
            filterScopeDecisionRow.click();
            requireText("pending-drain-decision-detail", [
              "Checkpoint: Display filter / backend drain scope",
              "Publish Parked Outputs does not drain only the visible table subset.",
              "Backend validation sees current parked payloads/manifests, not the filtered WebView table.",
            ]);
            if (posts.some((entry) => entry.path === "/api/pipeline/start")) {
              throw new Error("active-filter scope check attempted /api/pipeline/start: " + JSON.stringify(posts));
            }
            if (confirmCalls !== 0) {
              throw new Error("active-filter scope check should not ask for confirmation before click; confirm calls=" + confirmCalls);
            }
            window.renderPendingPublish(payload.pending, {});
            window.mediaPipelinePendingPublishView.resetPendingFilters();
            await waitFor(
              () => ["Allowed", "Review confirm"].includes(text("pending-drain-guard-status")),
              "guard restored after filter-scope scenario",
            );

            window.mediaPipelinePendingPublishView.renderPendingRecoveryPlanResult({
              ok: true,
              severity: "warning",
              message: "Dry-run plan found a blocked recovery action.",
              data: {
                schema_version: "pending_publish_recovery_plan.v1",
                scope: "all",
                row_count: 1,
                blocker_count: 1,
                review_count: 0,
                ready_count: 0,
                action_counts: { manual_review_with_pending_diagnostics: 1 },
                dry_run_only: true,
                would_mutate: false,
                mutation_guardrail: "Mutation guardrail: dry-run only; no files are moved.",
                summary_lines: ["Blocked row found by recovery dry-run."],
                rows: [{
                  row_key: "blocked-recovery-plan-row",
                  local_file: row.local_file || "PendingServerPush/sample.mkv",
                  server_out: row.server_out || "Out/sample.mkv",
                  manifest_path: row.manifest_path || "PendingServerPush/sample.mkv.manifest.json",
                  recovery_class: "manifest_repair",
                  planned_action: "manual_review_with_pending_diagnostics",
                  drain_recommendation: "do_not_drain",
                  diagnostic_severity: "error",
                  primary_concern: "Recovery dry-run found blocker evidence.",
                  issue_summary: "Dry-run says do not drain.",
                  safe_next_action: "Do not drain; read Pending Publish diagnostics first.",
                  evidence_fields: ["manifest_path", "local_file"],
                  proof_summary: ["dry-run reported blocker"],
                  recommended_open_targets: ["manifest", "pending_root"],
                }],
              },
            });
            await waitFor(
              () => text("pending-drain-guard-status") === "Blocked" && text("pending-drain-guard-summary").includes("Decision: Do not drain") && text("pending-drain-decision-summary").includes("Blocked/review/read-first/unknown:"),
              "guard refresh after blocked recovery plan",
            );
            requireText("pending-drain-guard-summary", [
              "Publish Parked Outputs blocked by WebView evidence: Do not drain.",
              "First action: select blocked/review checklist rows",
              "Mutation guardrail",
            ]);

            await window.mediaPipelineLaunchView.startPendingPublishDrain();
            await waitFor(
              () => text("pending-drain-status") === "Blocked" && text("pending-drain-detail").includes("Publish Parked Outputs blocked by WebView evidence: Do not drain."),
              "blocked drain click handled locally",
            );
            const history = window.getCommandHistory().filter((entry) => entry.command === "pending_publish.drain");
            if (!history.length) throw new Error("blocked drain click did not append local command result");
            if (!history.some((entry) => entry.local && entry.raw?.data?.frontend_guard === true)) {
              throw new Error("blocked drain command history did not include frontend_guard evidence: " + JSON.stringify(history));
            }
            if (posts.some((entry) => entry.path === "/api/pipeline/start")) {
              throw new Error("blocked drain attempted /api/pipeline/start: " + JSON.stringify(posts));
            }
            if (confirmCalls !== 0) {
              throw new Error("blocked drain should not ask for confirmation; confirm calls=" + confirmCalls);
            }
            requireText("pending-drain-history", [
              "pending_publish.drain",
              "frontend_guard",
            ]);
            requireText("pending-post-drain-trust-summary", [
              "Blocked/review/read-first/unknown:",
              "First action: stop treating this drain as trusted",
              "Mutation guardrail: this review is read-only",
            ]);
            return {
              ok: true,
              initialGuardStatus,
              guardStatus: text("pending-drain-guard-status"),
              guardSummary: text("pending-drain-guard-summary"),
              drainStatus: text("pending-drain-status"),
              drainDetail: text("pending-drain-detail"),
              postDrainTrustStatus: text("pending-post-drain-trust-status"),
              postDrainTrustSummary: text("pending-post-drain-trust-summary"),
              historyText: text("pending-drain-history"),
              postCount: posts.length,
              confirmCalls,
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
                expression: `Boolean(document.getElementById("pending-drain-guard-status") && document.getElementById("pending-post-drain-trust-status") && typeof window.renderPendingPublish === "function" && typeof window.mediaPipelinePendingPublishView.renderPendingPostDrainTrust === "function" && typeof window.mediaPipelineLaunchView.startPendingPublishDrain === "function")`,
                returnByValue: true,
              });
              if (ready.result?.value === true) break;
              await sleep(150);
            }
            const ready = await client.send("Runtime.evaluate", {
              expression: `Boolean(document.getElementById("pending-drain-guard-status") && document.getElementById("pending-post-drain-trust-status") && typeof window.renderPendingPublish === "function" && typeof window.mediaPipelinePendingPublishView.renderPendingPostDrainTrust === "function" && typeof window.mediaPipelineLaunchView.startPendingPublishDrain === "function")`,
              returnByValue: true,
            });
            if (ready.result?.value !== true) {
              throw new Error("WebView Pending Publish globals or guard DOM nodes did not become ready.");
            }
            const result = await client.send("Runtime.evaluate", {
              expression: pendingDrainGuardScript(payload.data),
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


def _run_browser_pending_drain_guard_smoke(
    *,
    browser_path: str,
    url: str,
    pending: dict[str, object],
) -> dict[str, object]:
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("Node.js is required for the browser-backed Pending Publish drain guard smoke.")
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as raw_tmp:
        tmp = Path(raw_tmp)
        port = _free_port()
        payload_path = tmp / "browser-pending-drain-guard-payload.json"
        runner_path = tmp / "browser-pending-drain-guard-runner.cjs"
        payload_path.write_text(
            json.dumps(
                {
                    "browserPath": browser_path,
                    "port": port,
                    "tmpRoot": str(tmp),
                    "url": url,
                    "data": {"pending": pending},
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        runner_path.write_text(_browser_pending_drain_guard_runner_source(), encoding="utf-8")
        return run_node_browser_smoke(
            "Browser-backed WebView Pending Publish drain guard smoke",
            node=node,
            runner_path=runner_path,
            payload_path=payload_path,
            timeout_seconds=45,
        )


class WebViewBrowserPendingDrainGuardSmokeTests(unittest.TestCase):
    def test_real_browser_refreshes_guard_after_blocked_recovery_plan_and_blocks_drain_post(self) -> None:
        browser_path = _find_browser()
        if not browser_path:
            raise unittest.SkipTest("Chrome or Edge is required for the browser-backed Pending Publish drain guard smoke.")

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
                pending_status, pending = _get_json(f"{server.url}/api/pending-publish", token="browser-smoke-token")
                self.assertEqual(pending_status, 200)
                self.assertGreaterEqual(len(pending.get("rows", [])), 1)
                result = _run_browser_pending_drain_guard_smoke(
                    browser_path=browser_path,
                    url=f"{server.url}/",
                    pending=pending,
                )
            finally:
                server.stop()
            assert_media_no_mutation(self, media_snapshot)

        self.assertTrue(result["ok"])
        browser_result = result["result"]
        self.assertIn(browser_result["initialGuardStatus"], {"Allowed", "Review confirm"})
        self.assertEqual(browser_result["guardStatus"], "Blocked")
        self.assertIn("Decision: Do not drain", browser_result["guardSummary"])
        self.assertEqual(browser_result["drainStatus"], "Blocked")
        self.assertIn("frontend_guard", browser_result["historyText"])
        self.assertEqual(browser_result["postCount"], 0)
        self.assertEqual(browser_result["confirmCalls"], 0)


if __name__ == "__main__":
    unittest.main()




