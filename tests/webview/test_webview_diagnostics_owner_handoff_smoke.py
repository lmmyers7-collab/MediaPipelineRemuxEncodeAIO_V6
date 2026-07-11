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


OWNER_HANDOFF_ASSETS = [
    "dom/query.js",
    "dom/text.js",
    "dom/status.js",
    "dom/filtering.js",
    "dom/table.js",
    "domHelpers.js",
    "formatters.js",
    "commandHistory/formatters.js",
    "commandHistory/diagnostics.js",
    "commandHistory/diagnosticEvidence.js",
    "commandHistory/resolutionChecklist.js",
    "commandHistory.js",
    "diagnosticsBridge.js",
    "queueView.summary.js",
    "queueView.review.js",
    "queueView.detail.js",
    "queueView.launch.js",
    "queue/selection.js",
    "queue/openActions.js",
    "queue/table.js",
    "queue/statusPanels.js",
    "queue/tableView.js",
    "queue/priority.js",
    "queue/manualOrder.js",
    "queue/strategy.js",
    "queue/controls.js",
    "queue/excluded.js",
    "queue/scan.js",
    "queueView.js",
    "completed/evidence/commands.js",
    "completed/evidence/filterScope.js",
    "completed/evidence/acceptance.js",
    "completed/evidence/routeAgreement.js",
    "completed/evidence/pendingProofModel.js",
    "completed/evidence/pendingProofView.js",
    "completedView.evidence.js",
    "completed/proof/pilotEvidence.js",
    "completedView.proof.js",
    "completed/review/integrity.js",
    "completed/review/workflowOverview.js",
    "completed/review/sizeReview.js",
    "completed/review/healthSignals.js",
    "completed/review/reviewRows.js",
    "completed/review/investigationFilters.js",
    "completed/review/tablePanels.js",
    "completed/review/metricsValidation.js",
    "completed/review/selectedAtAGlance.js",
    "completed/review/selectedEvidence.js",
    "completedView.review.js",
    "completedView.diagnostics.js",
    "completed/statusBoards.js",
    "completed/promotionCommands.js",
    "completed/openActions.js",
    "completed/selection.js",
    "completed/filters.js",
    "completed/table.js",
    "completed/sizeMode.js",
    "completed/presentation.js",
    "completedView.js",
    "pendingPublishView.recovery.js",
    "pendingPublishView.diagnostics.js",
    "pendingPublishView.drain.js",
    "pendingPublish/confidence/postDrainTrust.js",
    "pendingPublishView.confidence.js",
    "pendingPublishView.repair.js",
    "pendingPublish/tableSupport.js",
    "pendingPublish/defaultAdapters.js",
    "pendingPublish/summary.js",
    "pendingPublish/filters.js",
    "pendingPublish/details.js",
    "pendingPublish/actionCenter.js",
    "pendingPublish/rendering.js",
    "pendingPublishView.js",
    "diagnosticsView.activejobs.js",
    "diagnosticsView.log.js",
    "diagnosticsView.investigation.js",
    "diagnostics/matrixConsole.js",
    "diagnostics/triage.js",
    "diagnostics/firstResponse.js",
    "diagnosticsView.js",
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
            add(...items) { items.forEach((value) => values.add(value)); },
            remove(...items) { items.forEach((value) => values.delete(value)); },
          };
        }

        function queryDescendants(node, selector) {
          const matches = [];
          function visit(item) {
            if (!item) return;
            const wantsSelectable = selector === 'tr[data-selectable-row="true"]';
            if (wantsSelectable && item.tagName === "TR" && item.dataset.selectableRow === "true") {
              matches.push(item);
            }
            (item.children || []).forEach(visit);
          }
          visit(node);
          return matches;
        }

        function makeElement(id = "", tag = "") {
          let text = "";
          const node = {
            id,
            tagName: String(tag || "").toUpperCase(),
            nodeName: String(tag || "").toUpperCase(),
            value: "",
            checked: false,
            disabled: false,
            dataset: {},
            style: {},
            children: [],
            classList: makeClassList(),
            appendChild(child) { this.children.push(child); child.parentNode = this; return child; },
            append(...children) { children.forEach((child) => this.appendChild(child)); },
            replaceChildren(...children) { this.children = []; children.forEach((child) => this.appendChild(child)); },
            insertAdjacentElement(_position, child) { return this.appendChild(child); },
            querySelectorAll(selector) { return queryDescendants(this, selector); },
            querySelector(selector) { return queryDescendants(this, selector)[0] || null; },
            closest() { return null; },
            addEventListener() {},
            removeEventListener() {},
            setAttribute(name, value) { this[name] = String(value); },
            getAttribute(name) { return this[name] || ""; },
            focus() {},
            click() {},
            scrollIntoView() {},
          };
          Object.defineProperty(node, "textContent", {
            get() { return text; },
            set(value) {
              text = value === null || value === undefined ? "" : String(value);
              if (id) texts[id] = text;
            },
          });
          Object.defineProperty(node, "innerHTML", {
            get() { return text; },
            set(value) {
              text = value === null || value === undefined ? "" : String(value);
              if (id) texts[id] = text;
            },
          });
          return node;
        }

        const context = {
          console: {
            log() {},
            warn(...args) { errors.push(`warn:${args.join(" ")}`); },
            error(...args) { errors.push(`error:${args.join(" ")}`); },
          },
          setTimeout(fn) { if (typeof fn === "function") fn(); return 1; },
          clearTimeout() {},
          requestAnimationFrame(fn) { if (typeof fn === "function") fn(); },
          MEDIA_PIPELINE_BOOTSTRAP: { token: "smoke-token", url: "http://127.0.0.1", appVersion: "v5-test" },
          Headers: class Headers {},
        };
        context.window = context;
        context.globalThis = context;
        context.document = {
          body: makeElement("", "body"),
          getElementById(id) {
            if (!elements.has(id)) elements.set(id, makeElement(id));
            return elements.get(id);
          },
          createElement(tag) {
            return makeElement("", tag);
          },
          createTextNode(text) {
            const node = makeElement("", "#text");
            node.textContent = text;
            return node;
          },
          querySelectorAll() { return []; },
          querySelector() { return null; },
          addEventListener() {},
        };
        context.navigator = { userAgent: "node-diagnostics-owner-handoff-smoke" };
        context.apiGet = async () => ({});
        context.apiPost = async () => ({ ok: false, message: "mocked" });
        context.requestDiagnosticsTail = async (target) => { texts["mock-diagnostics-tail"] = String(target || ""); };
        context.requestDiagnosticsOpen = async (target) => { texts["mock-diagnostics-open"] = String(target || ""); };
        context.requestCommandDiagnosticsAction = () => {};
        context.showPage = (page) => { texts["mock-page"] = String(page || ""); return true; };

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

        [
          "diagnosticsOwnerHandoffRows",
          "renderDiagnosticsOwnerHandoff",
          "selectDiagnosticsOwnerHandoffRow",
          "getSelectedDiagnosticsOwnerHandoffRow",
          "navigateDiagnosticsOwnerHandoffRow",
        ].forEach((name) => {
          if (typeof context[name] !== "function") throw new Error(`missing exported function ${name}`);
        });

        const handoffContext = {
          queue: {
            rows: [{
              row_key: "queue-row-1",
              display_name: "Ambiguous Episode.mkv",
              operator_severity: "warning",
              blocked_reason_code: "tv_parse_unreliable",
              recommended_diagnostics_targets: ["queue_snapshot", "last_stderr_log"],
              available_open_targets: ["source_file", "source_folder"],
              safe_next_action: "Review Queue TV parse evidence before launch.",
            }],
          },
          completed: {
            rows: [{
              row_key: "completed-row-1",
              lookup_title: "Missing Output",
              output_file: "Missing Output.mkv",
              operator_severity: "error",
              output_exists: false,
              sidecar_exists: false,
              recommended_diagnostics_targets: ["completed_manifest", "last_stderr_log"],
              available_open_targets: ["output_folder", "sidecar"],
              safe_next_action: "Compare manifest and output folder before rerun.",
            }],
          },
          pending: {
            rows: [{
              row_key: "pending-row-1",
              local_file: "Pending Output.mkv",
              diagnostic_severity: "error",
              drain_recommendation: "do_not_drain",
              local_exists: false,
              recommended_diagnostics_targets: ["pending_publish", "last_stderr_log"],
              available_open_targets: ["local_file", "manifest"],
              operator_guidance: "Build recovery evidence before drain.",
            }],
          },
        };

        const rows = context.diagnosticsOwnerHandoffRows(handoffContext);
        if (rows.length !== 3) throw new Error(`expected 3 handoff rows, got ${rows.length}`);
        context.renderDiagnosticsOwnerHandoff(handoffContext);

        function text(id) {
          return texts[id] || "";
        }
        function requireText(id, fragments) {
          const actual = text(id);
          for (const fragment of fragments) {
            if (!actual.includes(fragment)) throw new Error(`${id} missing ${fragment}\nActual:\n${actual}`);
          }
        }

        requireText("diagnostics-owner-handoff-status", ["3 handoff rows", "blocked=3", "warning=0"]);
        requireText("diagnostics-owner-handoff", [
          "Owning-page evidence handoff:",
          "Queue=1; Completed=1; Pending Publish=1",
          "row_key plus target only",
          "Go To Owner Row is local UI selection",
          "this panel is read-only",
        ]);

        const queueItem = rows.find((row) => row.owner === "Queue");
        context.selectDiagnosticsOwnerHandoffRow(queueItem);
        requireText("diagnostics-owner-handoff-detail", [
          "Selected owning-page handoff:",
          "Owner page: Queue",
          "Row key: queue-row-1",
          "Diagnostics targets: queue_snapshot, last_stderr_log",
          "Backend selected open targets: source_file, source_folder",
          "Sample Validation context for this Diagnostics handoff:",
          "Loaded records: 0; matching this owner row: 0",
          "Diagnostics next action: use the owning page row plus Home > Sample Validation Preview Record",
          "Go To Owner Row is local UI selection",
          "Row file/folder opens belong to the owning page",
          "does not launch, rerun, drain, repair, rewrite, move, delete, publish, accept, or mutate media files",
        ]);

        const actions = elements.get("diagnostics-owner-handoff-actions");
        if (!actions || actions.children.length < 2) {
          throw new Error("expected read-first diagnostics actions for selected Queue handoff row");
        }
        const selected = context.getSelectedDiagnosticsOwnerHandoffRow();
        if (!selected || selected.owner !== "Queue") throw new Error("selected handoff row was not preserved");

        context.renderQueue(handoffContext.queue);
        const navigated = context.navigateDiagnosticsOwnerHandoffRow(queueItem);
        if (!navigated) throw new Error("expected Queue owner navigation to succeed");
        if (texts["mock-page"] !== "queue") throw new Error(`expected queue page navigation, got ${texts["mock-page"]}`);
        requireText("queue-detail", ["Row key: queue-row-1", "Ambiguous Episode.mkv"]);
        requireText("diagnostics-owner-handoff-nav-status", [
          "Opened Queue",
          "row_key=queue-row-1",
          "No backend command was sent",
          "no file paths were opened",
        ]);

        const completedItem = rows.find((row) => row.owner === "Completed");
        context.mediaPipelineCompletedView.renderCompleted(handoffContext.completed);
        if (!context.navigateDiagnosticsOwnerHandoffRow(completedItem)) {
          throw new Error("expected Completed owner navigation to succeed");
        }
        if (texts["mock-page"] !== "completed") throw new Error(`expected completed page navigation, got ${texts["mock-page"]}`);
        requireText("completed-detail", ["Row key: completed-row-1", "Missing Output"]);
        requireText("diagnostics-owner-handoff-nav-status", ["Opened Completed", "row_key=completed-row-1", "No backend command was sent"]);

        const pendingItem = rows.find((row) => row.owner === "Pending Publish");
        context.renderPendingPublish(handoffContext.pending, {});
        if (!context.navigateDiagnosticsOwnerHandoffRow(pendingItem)) {
          throw new Error("expected Pending Publish owner navigation to succeed");
        }
        if (texts["mock-page"] !== "pending") throw new Error(`expected pending page navigation, got ${texts["mock-page"]}`);
        requireText("pending-detail", ["Row key: pending-row-1", "Pending Output.mkv"]);
        requireText("diagnostics-owner-handoff-nav-status", ["Opened Pending Publish", "row_key=pending-row-1", "No backend command was sent"]);

        if (errors.length) throw new Error(`console errors were recorded: ${errors.join("; ")}`);
        console.log(JSON.stringify({ ok: true, row_count: rows.length, captured_ids: Object.keys(texts).sort() }));
        """
    )


def _run_node_owner_handoff_smoke(assets: list[dict[str, str]]) -> dict[str, object]:
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("Node.js is required for the diagnostics owner handoff runtime smoke.")
    with tempfile.TemporaryDirectory() as raw_tmp:
        tmp = Path(raw_tmp)
        payload_path = tmp / "diagnostics-owner-handoff-payload.json"
        runner_path = tmp / "diagnostics-owner-handoff-runner.cjs"
        payload_path.write_text(json.dumps({"assets": assets}, ensure_ascii=False), encoding="utf-8")
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
            "WebView diagnostics owner handoff smoke failed.\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
    return json.loads(result.stdout.strip().splitlines()[-1])


class WebViewDiagnosticsOwnerHandoffSmoke(unittest.TestCase):
    def test_diagnostics_owner_handoff_summarizes_queue_completed_pending_review_rows(self) -> None:
        static_root = find_repo_root(Path(__file__)) / "apps" / "desktop" / "webview" / "static" / "assets"
        assets = [
            {
                "name": name,
                "source": (static_root / name).read_text(encoding="utf-8"),
            }
            for name in OWNER_HANDOFF_ASSETS
        ]
        result = _run_node_owner_handoff_smoke(assets)
        self.assertTrue(result["ok"])
        self.assertEqual(result["row_count"], 3)


if __name__ == "__main__":
    unittest.main()
