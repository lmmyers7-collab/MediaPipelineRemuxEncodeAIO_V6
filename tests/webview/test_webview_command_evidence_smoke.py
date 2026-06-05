from __future__ import annotations

import json
import shutil
import subprocess
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
    from .test_webview_real_media_smoke import _get_text, _write_fixture_state
except ImportError:  # pragma: no cover - fallback for direct test execution
    from test_application_facade import DummyWorkflowFacadeService
    from test_webview_real_media_smoke import _get_text, _write_fixture_state


COMMAND_EVIDENCE_ASSETS = [
    "commandHistory/formatters.js",
    "commandHistory/diagnostics.js",
    "commandHistory.js",
    "settingsCommandHistory.js",
    "renameHistoryView.js",
    "launchHistoryView.js",
    "launch/risk/settingsAccess.js",
    "launch/risk/mediaPolicyValues.js",
    "launch/risk/riskRows.js",
    "launch/risk/policyPatch.js",
    "launch/risk/policyBoundary.js",
    "launchView.risk.js",
    "launchView.scope.js",
    "launchView.realmedia.js",
    "launchView.preflight.js",
    "launch/controllerState.js",
    "launch/statusRender.js",
    "launch/startRequest.js",
    "launch/scopeControls.js",
    "launch/commandButtons.js",
    "launchView.js",
    "pendingPublishView.recovery.js",
    "pendingPublishView.diagnostics.js",
    "pendingPublishView.drain.js",
    "pendingPublishView.confidence.js",
    "pendingPublish/summary.js",
    "pendingPublish/filters.js",
    "pendingPublish/details.js",
    "pendingPublishView.js",
    "queueView.summary.js",
    "queueView.review.js",
    "queueView.detail.js",
    "queueView.launch.js",
    "queue/selection.js",
    "queue/openActions.js",
    "queue/table.js",
    "queueView.js",
    "completed/evidence/commands.js",
    "completed/evidence/filterScope.js",
    "completed/evidence/acceptance.js",
    "completed/evidence/routeAgreement.js",
    "completedView.evidence.js",
    "completedView.proof.js",
    "completed/review/integrity.js",
    "completed/review/sizeReview.js",
    "completed/review/healthSignals.js",
    "completed/review/reviewRows.js",
    "completed/review/investigationFilters.js",
    "completedView.review.js",
    "completedView.diagnostics.js",
    "completed/statusBoards.js",
    "completed/promotionCommands.js",
    "completed/openActions.js",
    "completed/selection.js",
    "completed/filters.js",
    "completed/table.js",
    "completedView.js",
    "diagnosticsView.activejobs.js",
    "diagnosticsView.log.js",
    "diagnosticsView.investigation.js",
    "diagnosticsView.js",
    "reportsView.js",
    "networkView.js",
    "maintenanceView.js",
    "app/lifecycle.js",
    "app.js",
]


def _command_entries(root: Path) -> list[dict[str, object]]:
    source = root / "TV" / "Serial Experiments Lain" / "Season 02" / "Serial Experiments Lain S02E01 Weird.mkv"
    output = root / "Outsource" / "TV" / "Serial Experiments Lain" / "Season 02" / "Serial Experiments Lain - S02E01 - Weird.mkv"
    pending = root / "PendingServerPush" / output.name
    return [
        {
            "at": "2026-05-14T12:00:00-04:00",
            "command": "queue.open",
            "ok": True,
            "message": "Opened selected queue source.",
            "request": {"target": "source", "row_key": str(source)},
            "data": {"target": "source", "row_key": str(source), "opened_path": str(source)},
        },
        {
            "at": "2026-05-14T12:01:00-04:00",
            "command": "completed.open",
            "ok": True,
            "severity": "warning",
            "warnings": ["Completed row opened, but sidecar proof should still be checked."],
            "message": "Opened completed output.",
            "request": {"target": "output_file", "row_key": str(output)},
            "data": {"target": "output_file", "row_key": str(output), "path": str(output)},
        },
        {
            "at": "2026-05-14T12:02:00-04:00",
            "command": "pending_publish.drain",
            "ok": False,
            "severity": "error",
            "errors": ["One parked payload is missing."],
            "message": "Pending publish drain was blocked.",
            "request": {"mode": "drain_pending_pushes"},
            "data": {
                "mode": "drain_pending_pushes",
                "attempted_count": 1,
                "succeeded_count": 0,
                "error_count": 1,
                "remaining_count": 1,
                "blocker_count": 1,
                "rows": [{"local_file": str(pending), "planned_action": "manual_review", "operator_trust_state": "blocked"}],
            },
        },
        {
            "at": "2026-05-14T12:03:00-04:00",
            "command": "pending_publish.open",
            "ok": True,
            "message": "Opened backend-selected pending payload.",
            "request": {"target": "local_file", "row_key": str(pending)},
            "data": {"target": "local_file", "row_key": str(pending), "path": str(pending)},
        },
        {
            "at": "2026-05-14T12:04:00-04:00",
            "command": "pending_publish.recovery_plan_dry_run",
            "ok": True,
            "severity": "warning",
            "warnings": ["Recovery plan requires operator review."],
            "message": "Built dry-run recovery plan.",
            "request": {"scope": "selected"},
            "data": {"scope": "selected", "row_count": 1, "blocker_count": 0, "review_count": 1, "ready_count": 0},
        },
        {
            "at": "2026-05-14T12:05:00-04:00",
            "command": "diagnostics.open",
            "ok": True,
            "message": "Opened run logs.",
            "request": {"target": "run_logs"},
            "data": {"target": "run_logs", "opened_path": str(root / "RunLogs")},
        },
        {
            "at": "2026-05-14T12:06:00-04:00",
            "command": "diagnostics.open",
            "ok": True,
            "message": "Opened failure reports.",
            "request": {"target": "failed_reports"},
            "data": {"target": "failed_reports", "opened_path": str(root / "State" / "Failures" / "Reports")},
        },
        {
            "at": "2026-05-14T12:07:00-04:00",
            "command": "diagnostics.open",
            "ok": True,
            "message": "Opened network state.",
            "request": {"target": "state"},
            "data": {"target": "state", "opened_path": str(root / "State")},
        },
        {
            "at": "2026-05-14T12:08:00-04:00",
            "command": "maintenance.release_dry_run",
            "ok": True,
            "message": "Release dry-run completed.",
            "data": {"returncode": 0, "elapsed_seconds": 1.25, "manifest_exists": False, "zip_exists": False},
        },
        {
            "at": "2026-05-14T12:09:00-04:00",
            "command": "pipeline.control.pause",
            "ok": True,
            "message": "Pause flag written.",
            "request": {"action": "pause"},
            "data": {"action": "pause", "flag_path": str(root / "State" / "Pipeline" / "pipeline_pause.flag")},
            "refresh_hint": "snapshot",
        },
        {
            "at": "2026-05-14T12:10:00-04:00",
            "command": "backend.shutdown",
            "ok": False,
            "severity": "error",
            "message": "Backend shutdown blocked because active work may still be running.",
            "request": {"reason": "operator requested close"},
            "errors": ["Shell close blocked because the backend schedule-stop watcher is armed for PID 24680."],
            "data": {
                "safe_to_close": False,
                "state": "completed",
                "active_work": True,
                "reason": "Shell close blocked because the backend schedule-stop watcher is armed for PID 24680.",
                "continuous_watcher": {
                    "status": "armed",
                    "pid": 24680,
                    "deadline": "2026-05-14T13:00:00",
                    "stop_requested": False,
                    "message": "Backend schedule-stop watcher armed for PID 24680.",
                    "error": "",
                },
            },
            "refresh_hint": "shutdown",
        },
        {
            "at": "2026-05-14T12:11:00-04:00",
            "command": "rename.apply",
            "ok": True,
            "message": "Applied selected rename rows.",
            "request": {"selected_sources": [str(source)]},
            "data": {"applied_count": 1, "skipped_count": 0, "rollback_performed": False, "rows": [{"source": str(source)}]},
        },
        {
            "at": "2026-05-14T12:12:00-04:00",
            "command": "settings.preview_patch",
            "ok": True,
            "message": "Settings patch preview completed.",
            "request": {"changes": {"RoutingProfile": "plex_direct_stream"}},
            "data": {"changed_keys": ["RoutingProfile"], "writes_config": False},
        },
        {
            "at": "2026-05-14T12:13:00-04:00",
            "command": "pipeline.start",
            "ok": True,
            "message": "Started pipeline.",
            "request": {"mode": "validate", "schedule_override": "ignore"},
            "data": {"mode": "validate", "pid": 1234, "active_job_id": "job-1"},
        },
    ]


def _node_runner_source() -> str:
    return textwrap.dedent(
        r"""
        const fs = require("fs");
        const vm = require("vm");

        const payload = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
        const texts = {};
        const elements = new Map();
        const errors = [];

        function makeClassList() {
          const values = new Set();
          return {
            contains(value) { return values.has(value); },
            toggle(value, enabled) {
              if (enabled === false) values.delete(value);
              else values.add(value);
            },
            add(value) { values.add(value); },
            remove(value) { values.delete(value); },
          };
        }

        function makeElement(id = "") {
          const node = {
            id,
            textContent: "",
            value: "",
            checked: false,
            disabled: false,
            dataset: {},
            style: {},
            children: [],
            classList: makeClassList(),
            appendChild(child) { this.children.push(child); return child; },
            replaceChildren(...children) { this.children = children; },
            querySelectorAll() { return []; },
            querySelector() { return null; },
            closest() { return null; },
            addEventListener() {},
            setAttribute(name, value) { this[name] = String(value); },
            focus() {},
            click() {},
            scrollIntoView() {},
          };
          return node;
        }

        const context = {
          console: {
            log() {},
            warn(...args) { errors.push(`warn:${args.join(" ")}`); },
            error(...args) { errors.push(`error:${args.join(" ")}`); },
          },
          setTimeout,
          clearTimeout,
          setInterval() { return 1; },
          clearInterval() {},
          requestAnimationFrame(fn) { fn(); },
          confirm() { return true; },
          MEDIA_PIPELINE_BOOTSTRAP: { token: "smoke-token", url: "http://127.0.0.1", appVersion: "v5-test" },
        };
        context.window = context;
        context.globalThis = context;
        context.document = {
          getElementById(id) {
            if (!elements.has(id)) elements.set(id, makeElement(id));
            return elements.get(id);
          },
          createElement(tag) {
            const node = makeElement();
            node.tagName = String(tag || "").toUpperCase();
            return node;
          },
          querySelectorAll() { return []; },
          querySelector() { return null; },
          addEventListener() {},
        };
        context.byId = (id) => context.document.getElementById(id);
        context.setText = (id, value) => {
          texts[id] = String(value ?? "");
          context.document.getElementById(id).textContent = texts[id];
        };
        context.clearRows = (tbody, columns, message) => {
          if (tbody) tbody.replaceChildren(makeElement());
          texts[`table:${tbody?.id || "unknown"}`] = String(message || "");
        };
        context.appendCells = (row, values) => {
          (values || []).forEach((value) => {
            const cell = makeElement();
            cell.textContent = value === null || value === undefined ? "" : String(value);
            row.appendChild(cell);
          });
        };
        context.filterRows = (rows) => Array.isArray(rows) ? rows : [];
        context.makeRowSelectable = (row, onSelect, options = {}) => {
          if (!row) return;
          row.dataset.status = options.status || row.dataset.status || "";
          if (options.selected) row.classList.add("is-selected");
        };
        context.updateTableStatusLegend = (id) => { texts[id] = "mock table legend"; };
        context.tableStatusLegendText = () => "mock table legend";
        context.diagnosticsBridgeActions = () => [];
        context.diagnosticsBridgeHandoffLines = (label) => [`Diagnostics bridge: ${label}`];
        context.appendDiagnosticsBridgeGroupedButtons = () => {};
        context.requestCommandDiagnosticsAction = () => {};
        context.apiGet = async () => ({});
        context.apiPost = async () => ({ ok: false, message: "mocked" });

        vm.createContext(context);
        for (const asset of payload.assets) {
          vm.runInContext(asset.source, context, { filename: asset.name });
        }
        function promoteMediaPipelineNamespaces() {
          Object.keys(context)
            .filter((key) => key.startsWith("mediaPipeline"))
            .forEach((namespace) => {
              const namespaceExports = context[namespace];
              if (!namespaceExports || typeof namespaceExports !== "object") return;
              Object.entries(namespaceExports).forEach(([name, value]) => {
                if (context[name] === undefined) context[name] = value;
              });
            });
        }
        promoteMediaPipelineNamespaces();

        const queueOpen = payload.entries.find((entry) => entry.command === "queue.open") || {};
        const completedOpen = payload.entries.find((entry) => entry.command === "completed.open") || {};
        const pendingDrain = payload.entries.find((entry) => entry.command === "pending_publish.drain") || {};
        const queueRowKey = queueOpen.request?.row_key || queueOpen.data?.row_key || "";
        const completedRowKey = completedOpen.request?.row_key || completedOpen.data?.row_key || "";
        const pendingRow = (pendingDrain.data?.rows || [])[0] || {};
        context.getLastQueueRows = () => [{
          row_key: queueRowKey,
          display_name: "Serial Experiments Lain S02E01 Weird",
          source_path: queueRowKey,
          operator_trust_state: "ready",
        }];
        context.getLastQueuePayload = () => ({ produced_at: "2026-05-14T12:00:00-04:00", source: "queue_snapshot.json" });
        context.getLastCompletedRows = () => [{
          row_key: completedRowKey,
          lookup_title: "Serial Experiments Lain - S02E01 - Weird",
          output_path: completedRowKey,
          output_file: "Serial Experiments Lain - S02E01 - Weird.mkv",
          operator_trust_state: "review",
          output_exists: false,
          output_health: "missing output",
        }];
        context.getLastCompletedPayload = () => ({ source: "completed_jobs.jsonl", count: 1 });
        context.getLastPendingPublishPayload = () => ({
          pending_root: "PendingServerPush",
          rows: [{
            row_key: pendingRow.local_file || "pending-row",
            local_file: pendingRow.local_file || "",
            server_out: pendingRow.server_out || completedRowKey,
            manifest_path: pendingRow.manifest_path || "",
            source_path: queueRowKey,
            diagnostic_status: "blocked",
            operator_trust_state: "blocked",
          }],
          drain_summary: {
            items: [{
              server_out: completedRowKey,
              source_path: queueRowKey,
              local_file: pendingRow.local_file || "",
              status: "skipped",
              error: "Destination conflict during final placement.",
            }],
          },
        });
        context.pendingDrainGuardState = () => ({ status: "Do not drain", action: "Resolve missing payload before publishing." });
        context.getLastLaunchBackendPreflightPayloads = () => [{ target: "pipeline", status: "review" }];
        context.launchSettingsIntentStatus = () => "Review";
        context.queueLaunchDecisionStatus = () => "Read evidence";

        [
          "renderCommandHistoryPayload",
          "renderQueueOpenHistory",
          "renderCompletedOpenHistory",
          "renderPendingDrainHistory",
          "renderDiagnosticsOpenHistory",
          "renderPipelineControlHistory",
          "renderBackendLifecycleHistory",
        ].forEach((name) => {
          if (typeof context[name] !== "function") {
            const related = Object.keys(context).filter((key) => key.toLowerCase().includes(name.toLowerCase().replace("render", "")));
            throw new Error(`missing exported function ${name}; related=${related.join(",")}`);
          }
        });

        context.renderCommandHistoryPayload({ entries: payload.entries });
        const renderedHistory = context.getCommandHistory();
        [
          "renderQueueOpenHistory",
          "renderCompletedOpenHistory",
          "renderPendingDrainHistory",
          "renderPendingOpenHistory",
          "renderPendingRecoveryPlanHistory",
          "renderDiagnosticsOpenHistory",
          "renderReportOpenHistory",
          "renderNetworkOpenHistory",
          "renderMaintenanceDryRunHistory",
          "renderPipelineControlHistory",
          "renderRenameApplyHistory",
          "renderSettingsCommandHistory",
          "renderLaunchCommandHistory",
        ].forEach((name) => {
          if (typeof context[name] === "function") context[name](renderedHistory);
        });
        context.renderBackendLifecycleHistory(renderedHistory);
        const sampleValidationActions = context.commandHistoryDiagnosticsActions({
          command: "diagnostics.open",
          ok: true,
          severity: "info",
          raw: { data: { target: "sample_validation_log" } },
        });
        if (!sampleValidationActions.some((action) => action.target === "sample_validation_log")) {
          throw new Error("command diagnostics actions did not preserve sample_validation_log backend allowlist target");
        }

        function requireText(id, fragments) {
          const text = texts[id] || "";
          for (const fragment of fragments) {
            if (!text.includes(fragment)) {
              throw new Error(`${id} missing ${fragment}\nActual:\n${text}`);
            }
          }
        }

        requireText("queue-open-history", ["queue.open [ok; journal; owner=Queue; issue=ok]", "target=source"]);
        requireText("completed-open-history", ["completed.open [ok with warning; journal; owner=Completed; issue=warning]", "target=output_file", "opened="]);
        requireText("pending-drain-history", ["pending_publish.drain [error; journal; owner=Pending Publish; issue=error]", "remaining=1"]);
        requireText("pending-open-history", ["pending_publish.open [ok; journal; owner=Pending Publish; issue=ok]", "target=local_file", "opened="]);
        requireText("pending-recovery-plan-history", ["pending_publish.recovery_plan_dry_run [ok with warning; journal; owner=Pending Publish; issue=warning]", "review=1"]);
        requireText("diagnostics-open-history", ["diagnostics.open [ok; journal; owner=Diagnostics; issue=ok]", "target=run_logs"]);
        requireText("report-open-history", ["diagnostics.open [ok; journal; owner=Diagnostics; issue=ok]", "target=failed_reports"]);
        requireText("network-open-history", ["diagnostics.open [ok; journal; owner=Diagnostics; issue=ok]", "target=state"]);
        requireText("maintenance-dry-run-history", ["Release dry run [ok; journal; owner=Maintenance; issue=ok]", "return 0"]);
        requireText("control-history", ["pipeline.control.pause [ok; journal; owner=Launch; issue=ok]", "action=pause"]);
        requireText("backend-lifecycle-history", ["backend.shutdown [error; journal; owner=Diagnostics; issue=error]", "safe_to_close=no", "watcher=armed pid=24680"]);
        requireText("rename-apply-history", ["rename.apply [ok; journal; owner=Rename; issue=ok]", "applied=1"]);
        requireText("settings-command-history", ["Preview patch [ok; journal; owner=Settings; issue=ok]", "1 requested key(s)"]);
        requireText("launch-history", ["Pipeline [ok; journal; owner=Launch; issue=ok]", "pid=1234"]);
        requireText("command-summary", ["Results: 14", "Command issue digest:", "Owner pages:", "Final-placement proof: proof rows=2; still-pending=1; drain-proof=1"]);
        requireText("diagnostics-command-history", ["pipeline.start", "pending_publish.drain"]);
        const drainCommand = renderedHistory.find((entry) => entry.command === "pending_publish.drain");
        if (!drainCommand) throw new Error("missing pending_publish.drain command in rendered history");
        context.selectCommandEntry(drainCommand);
        requireText("command-detail", ["Owner page live state handoff:", "Owner page: Pending Publish", "Pending cached rows: 1", "Publish Button Guard: Do not drain", "Completed/Pending final-placement handoff:", "still-pending=1; drain-proof=1", "Treat as final-placement conflict", "Mutation guardrail: owner-state handoff is read-only"]);
        requireText("diagnostics-command-drilldown-detail", ["Owner page: Pending Publish", "Suggested next action:", "Read-first order: bounded tail targets before opening folders/files.", "Completed/Pending final-placement handoff:"]);
        requireText("diagnostics-command-evidence-summary", ["Command / diagnostics evidence correlation:", "Owner page live-state rows: 1", "Completed/Pending final-placement proof rows: 1", "final-placement proof is active", "Backend allowlist evidence targets:"]);
        requireText("diagnostics-command-resolution-summary", ["Command failure resolution checklist:", "owner state agree"]);
        const ownerLiveResolution = context.commandHistoryResolutionRows(renderedHistory).find((row) => row.key === "owner-live-state");
        if (!ownerLiveResolution) throw new Error("missing owner-live-state resolution checkpoint");
        const ownerLiveResolutionDetail = context.commandHistoryResolutionDetailLines(ownerLiveResolution).join("\\n");
        if (!ownerLiveResolutionDetail.includes("Owner page live state handoff:") || !ownerLiveResolutionDetail.includes("Pending cached rows: 1")) {
          throw new Error("owner live-state resolution detail missing expected evidence:\\n" + ownerLiveResolutionDetail);
        }
        const finalPlacementResolution = context.commandHistoryResolutionRows(renderedHistory).find((row) => row.key === "completed-pending-final-placement");
        if (!finalPlacementResolution) throw new Error("missing completed-pending-final-placement resolution checkpoint");
        const finalPlacementResolutionDetail = context.commandHistoryResolutionDetailLines(finalPlacementResolution).join("\\n");
        if (!finalPlacementResolutionDetail.includes("Completed/Pending final-placement handoff:") || !finalPlacementResolutionDetail.includes("drain-proof=1")) {
          throw new Error("final-placement resolution detail missing expected evidence:\\n" + finalPlacementResolutionDetail);
        }

        if (errors.length) {
          throw new Error(`console errors were recorded: ${errors.join("; ")}`);
        }
        console.log(JSON.stringify({ ok: true, captured_ids: Object.keys(texts).sort() }));
        """
    )


def _run_node_command_evidence_smoke(assets: list[dict[str, str]], entries: list[dict[str, object]]) -> dict[str, object]:
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("Node.js is required for the WebView command evidence runtime smoke.")
    with tempfile.TemporaryDirectory() as raw_tmp:
        tmp = Path(raw_tmp)
        payload_path = tmp / "command-evidence-payload.json"
        runner_path = tmp / "command-evidence-runner.cjs"
        payload_path.write_text(json.dumps({"assets": assets, "entries": entries}, ensure_ascii=False), encoding="utf-8")
        runner_path.write_text(_node_runner_source(), encoding="utf-8")
        result = subprocess.run(
            [node, str(runner_path), str(payload_path)],
            text=True,
            capture_output=True,
            timeout=30,
            check=False,
        )
    if result.returncode != 0:
        raise AssertionError(
            "WebView command evidence runtime smoke failed.\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
    return json.loads(result.stdout.strip().splitlines()[-1])


class WebViewCommandEvidenceSmokeTests(unittest.TestCase):
    def test_backend_served_webview_command_evidence_renders_owner_issue_lines(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved, _source, _output = _write_fixture_state(root)
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            server = LocalApiServer(
                facade,
                token="smoke-token",
                resolved_provider=lambda: resolved,
                audit_root_provider=lambda: str(root),
            )
            try:
                server.start()
                html_status, html, html_type = _get_text(f"{server.url}/")
                assets: list[dict[str, str]] = []
                for asset_name in COMMAND_EVIDENCE_ASSETS:
                    status, source, content_type = _get_text(f"{server.url}/assets/{asset_name}")
                    self.assertEqual(status, 200, asset_name)
                    self.assertIn("javascript", content_type, asset_name)
                    assets.append({"name": asset_name, "source": source})
            finally:
                server.stop()

            self.assertEqual(html_status, 200)
            self.assertIn("text/html", html_type)
            for fragment in (
                'id="queue-open-history"',
                'id="completed-open-history"',
                'id="pending-drain-history"',
                'id="diagnostics-open-history"',
                'id="command-summary"',
            ):
                self.assertIn(fragment, html)

            result = _run_node_command_evidence_smoke(assets, _command_entries(root))

        self.assertTrue(result["ok"])
        captured_ids = set(result["captured_ids"])
        for node_id in (
            "queue-open-history",
            "completed-open-history",
            "pending-drain-history",
            "diagnostics-open-history",
            "command-summary",
        ):
            self.assertIn(node_id, captured_ids)


if __name__ == "__main__":
    unittest.main()
