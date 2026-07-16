from __future__ import annotations

import shutil
import subprocess
import textwrap
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root


class WebViewRerunLifecycleContractTests(unittest.TestCase):
    def _run_node(self, script: str) -> None:
        node = shutil.which("node")
        if not node:
            raise unittest.SkipTest("Node.js is required for WebView lifecycle contract tests.")
        repo_root = find_repo_root(Path(__file__))
        result = subprocess.run(
            [node, "-e", textwrap.dedent(script)],
            cwd=repo_root,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_network_page_refresh_requests_backend_rerun_results(self) -> None:
        self._run_node(
            r"""
            const fs = require("fs");
            const vm = require("vm");
            const source = fs.readFileSync(
              "apps/desktop/webview/static/assets/app/refreshCoordinator.js",
              "utf8"
            );
            const context = {
              window: {},
              document: { querySelector: () => null },
              console,
              Date,
            };
            context.window = context;
            vm.createContext(context);
            vm.runInContext(source, context, { filename: "refreshCoordinator.js" });
            const included = vm.runInContext(
              'refreshRequestIncluded("rerun results", "network", {})',
              context
            );
            if (included !== true) {
              throw new Error("Network page refresh omitted /api/rerun/results.");
            }
            """
        )

    def test_rerun_start_success_labels_are_accepted_not_started(self) -> None:
        self._run_node(
            r"""
            const fs = require("fs");
            const vm = require("vm");
            const source = fs.readFileSync(
              "apps/desktop/webview/static/assets/launch/statusRender.js",
              "utf8"
            );
            const context = { window: {}, console };
            context.window = context;
            vm.createContext(context);
            vm.runInContext(source, context, { filename: "statusRender.js" });
            const view = context.__launchStatusRenderModule.createLaunchStatusRenderModule();
            for (const command of ["rerun.start", "rerun.network.start", "rerun.continue"]) {
              const label = view.launchCommandStatusLabel({ ok: true, severity: "info", command });
              if (label !== "Accepted") {
                throw new Error(`${command} success label was ${JSON.stringify(label)}, expected "Accepted".`);
              }
            }
            const rerunDetail = view.formatLaunchCommandDetail({
              ok: true,
              severity: "info",
              command: "rerun.start",
              message: "Started CSV rerun run via PID 1234.",
            });
            if (!rerunDetail.includes("Accepted CSV rerun run via PID 1234.") || rerunDetail.includes("Started CSV rerun")) {
              throw new Error(`rerun detail retained a started claim: ${JSON.stringify(rerunDetail)}`);
            }
            const pipelineLabel = view.launchCommandStatusLabel({
              ok: true,
              severity: "info",
              command: "pipeline.start",
            });
            if (pipelineLabel !== "Started") {
              throw new Error(`pipeline.start label changed unexpectedly: ${JSON.stringify(pipelineLabel)}`);
            }
            """
        )

    def test_network_rerun_rows_render_backend_retry_timeline_and_network_only_counts(self) -> None:
        self._run_node(
            r"""
            const fs = require("fs");
            const vm = require("vm");
            const source = fs.readFileSync(
              "apps/desktop/webview/static/assets/network/rerunEvidence.js",
              "utf8"
            );
            const rendered = {};
            const tbody = {
              rows: [],
              replaceChildren() { this.rows = []; },
              appendChild(row) { this.rows.push(row); },
            };
            const context = {
              window: {},
              console,
              document: { createElement: () => ({ dataset: {}, cells: [] }) },
            };
            context.window = context;
            vm.createContext(context);
            vm.runInContext(source, context, { filename: "network/rerunEvidence.js" });
            const view = context.__networkRerunEvidenceModule.createNetworkRerunEvidenceModule({
              byId(id) { return id === "network-rerun-rows" ? tbody : {}; },
              setText(id, value) { rendered[id] = String(value); },
              clearRows() {},
              networkAppendCell(row, value) { row.cells.push(String(value || "")); },
              networkStatusChip(value) { return String(value || ""); },
              networkRerunLeaf(value) { return String(value || "").split(/[\\/]/).pop(); },
              networkRerunCompactPath(value) { return String(value || ""); },
            });
            view.renderNetworkRerunRows({
              network_manifests: [{
                batch_id: "batch-1",
                status: "retry_exhausted",
                rows: [{
                  network_rerun_row_key: "row-1",
                  queue_source: "network_csv_rerun",
                  queue_status: "failed",
                  queue_status_label: "Retry Exhausted",
                  source_path: "C:\\Media\\Movie.mkv",
                  attempt_count: 3,
                  retry_count: 3,
                  retry_limit: 3,
                  reason_code: "SOURCE_UNAVAILABLE",
                  last_error: "Source remained unavailable.",
                  what: "Automatic Network CSV rerun retry stopped.",
                  why: "The configured retry limit was exhausted.",
                  when: "2026-07-13T20:00:30Z",
                  next_action: "Wait for an operator retry request.",
                  operator_action: "Request one explicit manual retry after restoring the source.",
                  network_reducer_result: { classification: "failed_retryable", accepted: false },
                }],
              }],
              counts: {
                network_queue_status_counts: { failed: 1 },
                queue_status_counts: { failed: 1, completed: 99 },
                network_retry_exhausted_count: 1,
              },
              queue_state: { status_counts: { failed: 1, completed: 99 } },
            });
            const evidence = tbody.rows[0]?.cells?.[5] || "";
            for (const expected of [
              "Attempts: 3 / 3",
              "Reason code: SOURCE_UNAVAILABLE",
              "What: Automatic Network CSV rerun retry stopped.",
              "Why: The configured retry limit was exhausted.",
              "When: 2026-07-13T20:00:30Z",
              "Next: Wait for an operator retry request.",
              "Operator action: Request one explicit manual retry after restoring the source.",
            ]) {
              if (!evidence.includes(expected)) {
                throw new Error(`missing backend-authored evidence ${JSON.stringify(expected)}: ${JSON.stringify(evidence)}`);
              }
            }
            const summary = rendered["network-rerun-summary"] || "";
            if (!summary.includes("failed 1") || summary.includes("completed 99")) {
              throw new Error(`Network summary used combined/local counts: ${JSON.stringify(summary)}`);
            }
            """
        )

    def test_launch_continue_requires_backend_authored_action_without_legacy_fallback(self) -> None:
        repo_root = find_repo_root(Path(__file__))
        source = (repo_root / "apps/desktop/webview/static/assets/launch/rerunPresentation.js").read_text(
            encoding="utf-8"
        )
        function_start = source.index("async function requestRerunContinue")
        function_end = source.index("function rerunPreviewBlockedReason", function_start)
        function_source = source[function_start:function_end]

        self.assertIn("backend-authored available_actions entry", function_source)
        self.assertIn('queueRerunRouteDispatcher("requestBackendRerunAction")(action)', function_source)
        self.assertNotIn('route: "/api/rerun/continue"', function_source)
        self.assertNotIn("confirm_continue: true", function_source)

    def test_backend_authored_local_and_network_retry_actions_dispatch_without_redundant_modals(self) -> None:
        self._run_node(
            r"""
            const fs = require("fs");
            const vm = require("vm");
            const posted = [];
            const confirmations = [];
            const prompts = [];
            let promptResult = "Source share restored.";
            global.window = {
              apiPost: async (route, request) => {
                posted.push({ route, request });
                return { ok: true, message: "accepted" };
              },
              confirm: (message) => { confirmations.push(message); return true; },
              prompt: (message) => { prompts.push(message); return promptResult; },
            };
            global.document = { getElementById: () => null };
            vm.runInThisContext(fs.readFileSync(
              "apps/desktop/webview/static/assets/queue/rerunApi.js", "utf8"
            ));
            vm.runInThisContext(fs.readFileSync(
              "apps/desktop/webview/static/assets/queueView.rerun.js", "utf8"
            ));
            const view = window.__queueRerunModule.createQueueRerunModule({
              apiPost: window.apiPost,
              apiGet: async () => ({}),
              byId: () => null,
              setText: () => {},
            });
            (async () => {
              await view.requestBackendRerunAction({
                action: "retry",
                label: "Request manual retry",
                route: "/api/rerun/network/retry",
                confirmation_field: "confirm_retry",
                confirmation_prompt: "Retry restored Network row?",
                requires_confirmation: false,
                request: {
                  batch_id: "batch-1",
                  row_key: "row-1",
                  confirm_retry: true,
                  reason: "operator_requested_retry_after_source_restore",
                },
                request_id_required: true,
                reason_required: true,
                reason_prompt: "Why is retry safe?",
              });
              if (posted[0]?.route !== "/api/rerun/network/retry") throw new Error("Network retry route not dispatched");
              if (posted[0]?.request?.confirm_retry !== true) throw new Error("strict Network confirmation was not preserved");
              if (!posted[0]?.request?.request_id || posted[0]?.request?.reason !== "operator_requested_retry_after_source_restore") {
                throw new Error(`Network retry identity/reason missing: ${JSON.stringify(posted[0])}`);
              }
              await view.requestBackendRerunAction({
                action: "retry",
                label: "Retry Exhausted Rows (1)",
                route: "/api/rerun/continue",
                confirmation_field: "confirm_continue",
                confirmation_prompt: "Retry backend-qualified exhausted rows?",
                requires_confirmation: false,
                request: { manifest_key: "manifest-1", confirm_continue: true },
                request_id_required: true,
              });
              if (posted[1]?.route !== "/api/rerun/continue" || posted[1]?.request?.confirm_continue !== true || !posted[1]?.request?.request_id) {
                throw new Error(`Local retry action not dispatched: ${JSON.stringify(posted[1])}`);
              }
              let rejectedMissingConfirmation = false;
              try {
                await view.requestBackendRerunAction({
                  action: "retry",
                  route: "/api/rerun/continue",
                  confirmation_field: "confirm_continue",
                  requires_confirmation: false,
                  request: { manifest_key: "manifest-1" },
                  request_id_required: true,
                });
              } catch (_error) {
                rejectedMissingConfirmation = true;
              }
              if (!rejectedMissingConfirmation || posted.length !== 2) throw new Error("Missing strict local confirmation was not rejected before POST");
              if (confirmations.length !== 0) throw new Error(`Safe retry/continue opened redundant confirmation modal: ${JSON.stringify(confirmations)}`);
              if (prompts.length !== 0) throw new Error(`Backend-authored Network reason unexpectedly prompted: ${JSON.stringify(prompts)}`);
            })().catch((error) => { console.error(error); process.exitCode = 1; });
            """
        )


if __name__ == "__main__":
    unittest.main()
