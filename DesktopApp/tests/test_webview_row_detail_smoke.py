from __future__ import annotations

import json
import shutil
import subprocess
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
    from .test_webview_real_media_smoke import _get_json, _get_text, _write_fixture_state
except ImportError:  # pragma: no cover - fallback for direct test execution
    from test_application_facade import DummyWorkflowFacadeService
    from test_webview_real_media_smoke import _get_json, _get_text, _write_fixture_state


ROW_DETAIL_ASSETS = [
    "domHelpers.js",
    "formatters.js",
    "commandHistory.js",
    "diagnosticsBridge.js",
    "queueView.summary.js",
    "queueView.review.js",
    "queueView.detail.js",
    "queueView.launch.js",
    "queueView.js",
    "completedView.evidence.js",
    "completedView.proof.js",
    "completedView.review.js",
    "completedView.diagnostics.js",
    "completedView.js",
    "pendingPublishView.recovery.js",
    "pendingPublishView.diagnostics.js",
    "pendingPublishView.drain.js",
    "pendingPublishView.confidence.js",
    "pendingPublishView.js",
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

        function makeElement(id = "") {
          let text = "";
          const node = {
            id,
            value: "",
            checked: false,
            disabled: false,
            dataset: {},
            style: {},
            children: [],
            classList: makeClassList(),
            appendChild(child) { this.children.push(child); return child; },
            append(...children) { this.children.push(...children); },
            replaceChildren(...children) { this.children = children; },
            querySelectorAll() { return []; },
            querySelector() { return null; },
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
          setInterval() { return 1; },
          clearInterval() {},
          requestAnimationFrame(fn) { if (typeof fn === "function") fn(); },
          confirm() { return true; },
          MEDIA_PIPELINE_BOOTSTRAP: { token: "smoke-token", url: "http://127.0.0.1", appVersion: "v5-test" },
          Headers: class Headers {},
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
            node.nodeName = node.tagName;
            return node;
          },
          createTextNode(text) {
            const node = makeElement();
            node.textContent = text;
            return node;
          },
          querySelectorAll() { return []; },
          querySelector() { return null; },
          addEventListener() {},
        };
        context.navigator = { userAgent: "node-row-detail-smoke" };
        context.apiGet = async () => ({});
        context.apiPost = async () => ({ ok: false, message: "mocked" });
        context.requestDiagnosticsTail = async (target) => { texts["mock-diagnostics-tail"] = String(target || ""); };
        context.requestDiagnosticsOpen = async (target) => { texts["mock-diagnostics-open"] = String(target || ""); };
        context.requestCommandDiagnosticsAction = () => {};
        context.showPage = () => true;

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
          "renderQueue",
          "selectQueueRow",
          "renderCompleted",
          "selectCompletedRow",
          "renderPendingPublish",
          "selectPendingRow",
          "resetQueueFilters",
          "resetCompletedFilters",
          "resetPendingFilters",
          "diagnosticsBridgeHandoffLines",
          "diagnosticsBridgeRowTrustLines",
        ].forEach((name) => {
          if (typeof context[name] !== "function") {
            const related = Object.keys(context).filter((key) => key.toLowerCase().includes(name.toLowerCase().replace("render", "")));
            throw new Error(`missing exported function ${name}; related=${related.join(",")}`);
          }
        });

        context.renderPendingPublish(payload.pending, {});
        context.renderQueue(payload.queue);
        context.renderCompleted(payload.completed);
        context.selectQueueRow(payload.queue.rows[0]);
        context.selectCompletedRow(payload.completed.rows[0]);
        context.selectPendingRow(payload.pending.rows[0]);

        function requireText(id, fragments) {
          const text = texts[id] || "";
          for (const fragment of fragments) {
            if (!text.includes(fragment)) {
              throw new Error(`${id} missing ${fragment}\nActual:\n${text}`);
            }
          }
        }

        requireText("queue-detail", [
          "Selected row quick signal:",
          "Current filter visibility:",
          "Selected row review checklist:",
          "Combined row review plan:",
          "Investigation view matches:",
          "Real-media sample trace: Queue",
          "Operator trust summary:",
          "Diagnostics handoff:",
          "Backend selected open targets:",
          "Open boundary: Queue buttons send only row_key, row_scope, and target.",
          "Route decision:",
          "Route reason:",
          "Mutation guardrail",
        ]);
        requireText("queue-diagnostics-guidance", [
          "Diagnostics actions below use backend allowlists",
          "Suggested order:",
          "Mutation guardrail",
          "Diagnostics bridge:",
        ]);

        requireText("completed-detail", [
          "Selected completed-row quick signal:",
          "Current filter visibility:",
          "Selected completed-row review checklist:",
          "Combined completed-row review plan:",
          "Investigation view matches:",
          "Real-media sample trace: Completed",
          "Operator trust summary:",
          "Diagnostics handoff:",
          "Backend selected open targets:",
          "Open boundary: Completed buttons send only row_key and target.",
          "Route:",
          "Audio decisions:",
          "Subtitle decisions:",
          "Mutation guardrail",
        ]);
        requireText("completed-diagnostics-guidance", [
          "Diagnostics actions below use backend allowlists",
          "Suggested order:",
          "Mutation guardrail",
          "Diagnostics bridge:",
        ]);
        requireText("completed-real-media-proof-summary", [
          "Real-media output proof ladder:",
          "Decision rule: output proof, sidecar proof, route/size/media decision, pending/drain posture, and diagnostics/runtime evidence must agree before trusting a sample.",
          "Phase boundary: Launch proof is pre-run intent only",
          "Mutation guardrail",
        ]);
        requireText("completed-real-media-proof-detail", [
          "Real-media output proof ladder:",
          "Associated completed row:",
          "Boundary: this is operator proof support only.",
        ]);
        const realMediaProofRows = context.completedRealMediaProofRows(
          payload.completed,
          payload.completed.rows,
          context.getLastCompletedPendingProofRows ? context.getLastCompletedPendingProofRows() : [],
          payload.pending,
        );
        const sampleValidationHandoffRow = realMediaProofRows.find((row) => row.checkpoint === "Sample validation handoff");
        if (!sampleValidationHandoffRow) throw new Error("expected completed sample-validation handoff proof row");
        const policyReconciliationRow = realMediaProofRows.find((row) => row.checkpoint === "Saved policy reconciliation");
        if (!policyReconciliationRow) throw new Error("expected completed saved-policy reconciliation proof row");
        const transitionProofRow = realMediaProofRows.find((row) => row.checkpoint === "Launch-to-output transition");
        if (!transitionProofRow) throw new Error("expected completed launch-to-output transition proof row");
        const transitionProofDetail = context.completedRealMediaProofDetailLines(transitionProofRow).join("\n");
        for (const fragment of [
          "Checkpoint: Launch-to-output transition",
          "Pre-run proof source: Launch real-media sample proof handoff",
          "Post-run proof source: Completed output/sidecar",
          "Transition rule: Launch can prove intent before start",
        ]) {
          if (!transitionProofDetail.includes(fragment)) throw new Error(`launch-to-output transition detail missing ${fragment}\nActual:\n${transitionProofDetail}`);
        }
        const sampleValidationHandoffDetail = context.completedRealMediaProofDetailLines(sampleValidationHandoffRow).join("\n");
        for (const fragment of [
          "Checkpoint: Sample validation handoff",
          "Sample Validation handoff is evidence-only.",
          "Use Preview Record first",
          "Home Sample Validation can write JSONL evidence notes only",
        ]) {
          if (!sampleValidationHandoffDetail.includes(fragment)) throw new Error(`sample-validation handoff detail missing ${fragment}\nActual:\n${sampleValidationHandoffDetail}`);
        }
        const policyReconciliationDetail = context.completedRealMediaProofDetailLines(policyReconciliationRow).join("\n");
        for (const fragment of [
          "Checkpoint: Saved policy reconciliation",
          "Completed policy reconciliation:",
          "Category comparison rows:",
          "No saved policy-alignment rows loaded.",
          "Post-run boundary: Completed can prove output-side evidence only",
        ]) {
          if (!policyReconciliationDetail.includes(fragment)) throw new Error(`policy reconciliation detail missing ${fragment}\nActual:\n${policyReconciliationDetail}`);
        }
        requireText("completed-pilot-evidence-summary", [
          "Selected pilot evidence packet:",
          "Purpose: copyable post-run proof for a selected Completed row after a real-media pilot run.",
          "Decision rule: do not append an accepted Sample Validation record",
          "Mutation guardrail",
        ]);
        requireText("completed-pilot-evidence-detail", [
          "Selected pilot evidence packet:",
          "Checkpoint:",
          "Associated completed row:",
          "Guardrail:",
        ]);
        requireText("completed-pilot-evidence-markdown", [
          "# Selected Completed Pilot Evidence Packet",
          "## Checklist",
          "Confirm Plex/client playback",
          "Backend mutation boundary:",
        ]);
        const pilotRows = context.completedPilotEvidencePacketRows(
          payload.completed,
          payload.completed.rows,
          context.getLastCompletedPendingProofRows ? context.getLastCompletedPendingProofRows() : [],
          payload.pending,
        );
        for (const checkpoint of [
          "1. Selected Completed output",
          "2. Output and sidecar proof",
          "3. Route, size, audio, subtitle proof",
          "3b. Saved policy reconciliation",
          "4. Pending/final placement proof",
          "5. Diagnostics/runtime proof",
          "6. Sample Validation readiness",
          "7. Manual playback checks",
          "8. Read-only mutation boundary",
        ]) {
          if (!pilotRows.some((row) => row.checkpoint === checkpoint)) {
            throw new Error(`missing pilot evidence checkpoint ${checkpoint}`);
          }
        }
        const pilotMarkdown = context.completedPilotEvidencePacketMarkdownLines(pilotRows).join("\n");
        for (const fragment of [
          "Title:",
          "Source:",
          "Output:",
          "- [ ] 6. Sample Validation readiness",
          "Home > Sample Validation evidence",
        ]) {
          if (!pilotMarkdown.includes(fragment)) throw new Error(`pilot evidence markdown missing ${fragment}\nActual:\n${pilotMarkdown}`);
        }

        requireText("pending-detail", [
          "Selected pending-row quick signal:",
          "Current filter visibility:",
          "Selected pending-row review checklist:",
          "Combined pending-row drain review plan:",
          "Investigation view matches:",
          "Real-media sample trace: Pending Publish",
          "Sample Validation handoff: Pending Publish",
          "Suggested pilot category: deferred-publish",
          "Home Sample Validation can write JSONL evidence notes only",
          "Operator trust summary:",
          "Diagnostics handoff:",
          "Backend selected open targets:",
          "Open boundary: Pending Publish buttons send only row_key and target.",
          "Drain recommendation:",
          "Ready to drain:",
          "Mutation guardrail",
        ]);
        requireText("pending-diagnostics-guidance", [
          "Diagnostics actions below use backend allowlists",
          "never sends arbitrary filesystem paths",
          "Selected-row diagnostic order:",
          "Diagnostics bridge:",
        ]);
        const readyPendingSampleValidationHandoff = context.pendingSampleValidationHandoffLines({
          drain_recommendation: "ready",
          ready_to_drain: true,
          local_exists: true,
          diagnostic_status: "ready",
          diagnostic_severity: "info",
        }).join("\n");
        for (const fragment of [
          "Sample Validation handoff: Pending Publish",
          "Suggested pilot category: deferred-publish",
          "Suggested evidence decision: accepted only after Completed output proof and durable drain summary agree",
          "Home Sample Validation can write JSONL evidence notes only",
        ]) {
          if (!readyPendingSampleValidationHandoff.includes(fragment)) {
            throw new Error(`ready pending sample-validation handoff missing ${fragment}\nActual:\n${readyPendingSampleValidationHandoff}`);
          }
        }
        const blockedPendingSampleValidationHandoff = context.pendingSampleValidationHandoffLines({
          drain_recommendation: "do_not_drain",
          ready_to_drain: false,
          local_exists: false,
          diagnostic_status: "invalid_manifest",
          diagnostic_severity: "error",
        }).join("\n");
        for (const fragment of [
          "Suggested evidence decision: hold_review until pending blockers are explained",
          "Do not append accepted sample evidence from this pending row",
          "cannot drain, publish, mark complete, accept output, rewrite manifests, or mutate media",
        ]) {
          if (!blockedPendingSampleValidationHandoff.includes(fragment)) {
            throw new Error(`blocked pending sample-validation handoff missing ${fragment}\nActual:\n${blockedPendingSampleValidationHandoff}`);
          }
        }
        [
          {
            name: "missing local payload",
            row: {
              drain_recommendation: "review",
              ready_to_drain: true,
              local_exists: false,
              diagnostic_status: "ready",
              diagnostic_severity: "info",
            },
          },
          {
            name: "invalid manifest status",
            row: {
              drain_recommendation: "review",
              ready_to_drain: true,
              local_exists: true,
              diagnostic_status: "invalid_manifest",
              diagnostic_severity: "warning",
            },
          },
          {
            name: "unreadable manifest state",
            row: {
              state: "unreadable_manifest",
              drain_recommendation: "review",
              ready_to_drain: true,
              local_exists: true,
              diagnostic_status: "review",
              diagnostic_severity: "warning",
            },
          },
          {
            name: "orphan payload state",
            row: {
              state: "orphan_payload",
              drain_recommendation: "review",
              ready_to_drain: true,
              local_exists: true,
              diagnostic_status: "review",
              diagnostic_severity: "warning",
            },
          },
          {
            name: "diagnostic error severity",
            row: {
              drain_recommendation: "ready",
              ready_to_drain: true,
              local_exists: true,
              diagnostic_status: "ready",
              diagnostic_severity: "error",
            },
          },
        ].forEach((fixture) => {
          const text = context.pendingSampleValidationHandoffLines(fixture.row).join("\n");
          for (const fragment of [
            "Suggested evidence decision: hold_review until pending blockers are explained",
            "Do not append accepted sample evidence from this pending row",
            "Home Sample Validation can write JSONL evidence notes only",
          ]) {
            if (!text.includes(fragment)) {
              throw new Error(`blocked pending sample-validation fixture ${fixture.name} missing ${fragment}\nActual:\n${text}`);
            }
          }
        });

        const unicodeLeaf = "Serial Experiments Lain - S02E01 - Épisode ✓.mkv";
        const pendingShareRoot = String.raw`\\LAYNE-SERVER\Users\Layne\Videos`;
        const completedShareRoot = "//LAYNE-SERVER/Users/Layne/Videos";
        const uncPending = {
          row_key: "pending-unc-unicode",
          server_out: `${pendingShareRoot}\\outsource\\Anime\\${unicodeLeaf}`,
          source_path: `${pendingShareRoot}\\Encode\\Anime\\${unicodeLeaf}`,
          local_file: `C:/Scratch/Pending/${unicodeLeaf}`,
          state: "ready",
          drain_recommendation: "ready",
          diagnostic_status: "ready",
          diagnostic_severity: "info",
        };
        const exactUnicodeCompleted = {
          row_key: "completed-unc-unicode-exact",
          lookup_title: "Exact UNC Unicode",
          output_path: `${completedShareRoot}/outsource/Anime/${unicodeLeaf}`,
          source_path: `${completedShareRoot}/Encode/Anime/${unicodeLeaf}`,
          output_file: unicodeLeaf,
          operator_trust_state: "consistent-looking",
        };
        const sameLeafUnicodeCompleted = {
          row_key: "completed-unc-unicode-same-leaf",
          lookup_title: "Same Leaf Different Folder",
          output_path: `D:/Different Library/${unicodeLeaf}`,
          source_path: `D:/Different Source/source-${unicodeLeaf}`,
          output_file: unicodeLeaf,
          operator_trust_state: "review",
        };
        const originalGetLastCompletedRows = context.getLastCompletedRows;
        context.getLastCompletedRows = () => [exactUnicodeCompleted, sameLeafUnicodeCompleted];
        const unicodeCorrelation = context.pendingSelectedCompletedCorrelationRows(uncPending);
        if (unicodeCorrelation.exactDestination.length !== 1) {
          throw new Error(`expected one exact UNC/Unicode destination match, got ${unicodeCorrelation.exactDestination.length}`);
        }
        if (unicodeCorrelation.exactSource.length !== 1) {
          throw new Error(`expected one exact UNC/Unicode source match, got ${unicodeCorrelation.exactSource.length}`);
        }
        if (unicodeCorrelation.sameLeaf.length !== 1) {
          throw new Error(`expected one same-leaf duplicate-title hint, got ${unicodeCorrelation.sameLeaf.length}`);
        }
        const unicodeCorrelationLines = context.pendingSelectedCompletedCorrelationLines(uncPending).join("\n");
        for (const fragment of [
          "Exact pending destination -> completed output: 1",
          "Exact pending source -> completed source: 1",
          "Same-leaf completed output hints: 1",
          "Exact destination matches:",
          "Same-leaf review hints:",
          "Boundary: same-leaf matches are duplicate-title hints only",
        ]) {
          if (!unicodeCorrelationLines.includes(fragment)) {
            throw new Error(`UNC/Unicode pending correlation missing ${fragment}\nActual:\n${unicodeCorrelationLines}`);
          }
        }
        if (originalGetLastCompletedRows) context.getLastCompletedRows = originalGetLastCompletedRows;

        const unicodeProofRows = context.completedPendingProofRows(
          { rows: [exactUnicodeCompleted, sameLeafUnicodeCompleted] },
          [exactUnicodeCompleted, sameLeafUnicodeCompleted],
          {
            rows: [uncPending],
            drain_summary: {
              items: [{
                status: "published",
                destination_path: `${completedShareRoot}/outsource/Anime/${unicodeLeaf}`,
                source_path: `${completedShareRoot}/Encode/Anime/${unicodeLeaf}`,
              }],
            },
          },
        );
        const exactDestinationProofRows = unicodeProofRows.filter((row) => row.signal === "pending-destination-overlap");
        const exactSourceProofRows = unicodeProofRows.filter((row) => row.signal === "completed-source-still-pending");
        const drainOutputProofRows = unicodeProofRows.filter((row) => row.signal === "drain-summary-output-proof");
        const duplicateLeafRows = unicodeProofRows.filter((row) => row.signal === "same-leaf-review");
        if (exactDestinationProofRows.length !== 1) throw new Error(`expected one exact pending destination proof row, got ${exactDestinationProofRows.length}`);
        if (exactSourceProofRows.length !== 1) throw new Error(`expected one exact pending source proof row, got ${exactSourceProofRows.length}`);
        if (drainOutputProofRows.length !== 1) throw new Error(`expected one exact durable drain output proof row, got ${drainOutputProofRows.length}`);
        if (duplicateLeafRows.length !== 2) throw new Error(`expected two same-leaf advisory proof rows from pending and drain evidence, got ${duplicateLeafRows.length}`);
        const duplicateLeafDetail = context.completedPendingProofDetailLines(duplicateLeafRows[0]).join("\n");
        for (const fragment of [
          "Signal: Same leaf review",
          "Only the filename leaf matches; full paths differ or are missing.",
          "Treat as a duplicate-title/path review only",
          "Boundary: same-leaf matches are duplicate-title hints only",
        ]) {
          if (!duplicateLeafDetail.includes(fragment)) {
            throw new Error(`same-leaf duplicate-title detail missing ${fragment}\nActual:\n${duplicateLeafDetail}`);
          }
        }

        if (payload.scenario === "adversarial") {
          const riskQueue = JSON.parse(JSON.stringify(payload.queue));
          const blockedVideoRow = Object.assign({}, riskQueue.rows[0], {
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
          });
          const hiddenSidecarRow = Object.assign({}, riskQueue.rows[0], {
            row_key: "hidden-sidecar-srt",
            source_path: "C:\\\\Source\\\\Movie.en.srt",
            relative_path: "C:\\\\Source\\\\Movie.en.srt",
            display_name: "Movie.en.srt",
            route_name: "",
            route_reason_code: "bad_extension",
            route_reason: "bad-extension: .srt",
            operator_status: "Blocked",
            operator_trust_state: "blocked",
            operator_severity: "warning",
            blocked_reason_code: "bad_extension",
            blocked_reason: "bad-extension: .srt",
            review_flags: ["blocked", "blocked:bad_extension"],
            proof_summary: ["subtitle sidecar", "bad-extension: .srt"],
          });
          riskQueue.rows = [blockedVideoRow, hiddenSidecarRow];
          riskQueue.runnable_count = 2;
          riskQueue.blocked_row_count = 2;
          context.renderQueue(riskQueue);
          context.selectQueueRow(riskQueue.rows[0]);
          requireText("queue-summary", [
            "Rows: 1",
            "Hidden subtitle sidecars: 1",
            ".srt=1",
            "Visible blocked rows: 1",
          ]);
          requireText("queue-breakdown", [
            "Rows loaded: 1",
            "Hidden subtitle sidecars: 1",
            "Visible blocked reason codes: tv_parse_unreliable=1",
          ]);
          requireText("queue-detail", [
            "Row state: blocked",
            "Blocker: tv_parse_unreliable - Episode/season parse was ambiguous; operator must review before launch.",
            "Runtime issue: source_locked - Source changed during probe.",
            "Runtime check note: source stability will be rechecked at backend launch",
            "Review flag explanations:",
            "blocked:tv_parse_unreliable: title/episode parsing is not trusted.",
            "Mutation guardrail: review-flag explanations translate Queue snapshot markers only",
            "Primary issue(s): blocked: tv_parse_unreliable - Episode/season parse was ambiguous; operator must review before launch.",
            "Combined row review plan:",
            "Signals: launch blocker; fresh runtime failure; deferred source/output checks; TV parse confidence",
            "Read first: Queue Snapshot -> Last Stderr -> Run Logs -> Latest Failure -> ActiveJobs",
            "Cross-check: Launch readiness -> Completed exclusions -> ActiveJobs -> Pending Publish if deferred publish is enabled",
            "Decision: do not start this source from Launch until the blocker/runtime/parse evidence is explained by backend artifacts.",
            "Table status: blocked",
            "Focused views: launch blockers, runtime failed, deferred checks, remux routes, TV parse review",
            "Selected row visible in table: yes",
            "- launch blockers: tv_parse_unreliable - Episode/season parse was ambiguous; operator must review before launch.",
            "- runtime failed: failed - source_locked - Source changed during probe.",
            "- deferred checks: source stability or output-path checks are deferred until backend launch.",
            "- TV parse review: tv_parse_unreliable - Episode/season parse was ambiguous; operator must review before launch.",
            "Safe next action: use Queue Diagnostics Cross-Links before launch",
            "investigation views are display filters only and do not alter backend launch scope",
            "Diagnostics handoff:",
            "Mutation guardrail",
          ]);
          requireText("queue-diagnostics-guidance", [
            "Selected route:",
            "Suggested order: open Queue Snapshot, read Last Stderr, then open Run Logs before launching or reprocessing.",
            "Diagnostics bridge:",
          ]);
          context.document.getElementById("queue-filter").value = "definitely-no-queue-match";
          context.renderQueueRows();
          requireText("queue-filter-summary", [
            "Queue filter: text=\"definitely-no-queue-match\"; status=all; view=all signals; showing 0 of 1 row.",
            "Hidden review rows: 1.",
            "clear or change this filter before launch decisions",
            "Mutation guardrail: filtering the Queue table does not change backend launch scope",
          ]);
          requireText("queue-detail", [
            "Selected row visible in table: no",
            "Hidden by current filters: text filter=\"definitely-no-queue-match\".",
            "selected-row detail remains visible for review",
          ]);
          context.document.getElementById("queue-filter").value = "";
          context.document.getElementById("queue-status-filter").value = "ready";
          context.renderQueueRows();
          requireText("queue-filter-summary", [
            "Queue filter: text=none; status=ready/healthy; view=all signals; showing 0 of 1 row.",
            "Hidden review rows: 1.",
            "clear or change this filter before launch decisions",
          ]);
          requireText("queue-detail", [
            "Hidden by current filters: status filter=ready/healthy.",
          ]);
          context.document.getElementById("queue-status-filter").value = "all";
          context.document.getElementById("queue-investigation-filter").value = "priority";
          context.renderQueueRows();
          requireText("queue-filter-summary", [
            "Queue filter: text=none; status=all; view=priority rows; showing 0 of 1 row.",
            "Hidden review rows: 1.",
            "clear or change this filter before launch decisions",
          ]);
          requireText("queue-detail", [
            "Hidden by current filters: investigation view=priority rows.",
          ]);
          context.resetQueueFilters();
          requireText("queue-filter-summary", [
            "Queue filter: text=none; status=all; view=all signals; showing 1 of 1 row.",
          ]);
          requireText("queue-detail", [
            "Selected row visible in table: yes",
            "no Queue display filter is hiding this selected row",
          ]);

          const riskCompleted = JSON.parse(JSON.stringify(payload.completed));
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
          context.renderCompleted(riskCompleted);
          context.selectCompletedRow(riskCompleted.rows[0]);
          requireText("completed-detail", [
            "Row state: broken-output",
            "Output health: missing output",
            "Consistency issues: missing_sidecar, output_path_missing",
            "Runtime issue: publish_missing_output - Completed manifest points at a missing file.",
            "Review flag explanations:",
            "missing_output: expected output proof is missing.",
            "consistency:missing_sidecar: sidecar or metadata proof is missing or inconsistent.",
            "Mutation guardrail: review-flag explanations translate Completed history markers only",
            "Primary issue(s): output missing or unhealthy; sidecar missing or inconsistent; output grew more than 5%",
            "Combined completed-row review plan:",
            "Signals: missing output; sidecar/metadata mismatch; size growth over policy; fresh runtime failure",
            "Read first: Completed Manifest -> Pending Publish -> Last Stderr -> Run Logs -> Latest Failure",
            "Cross-check: Output path -> Sidecar path -> Route/size proof -> Pending Publish parked-output proof -> Settings size policy and encoder route",
            "Decision: do not treat this completed row as output proof until manifest, output, sidecar, and pending-publish evidence agree.",
            "Table status: blocked",
            "Focused views: missing output, size growth, sidecar issues, runtime failed",
            "Selected row visible in table: yes",
            "- missing output: missing output",
            "- size growth: +110%",
            "- sidecar issues: missing_sidecar, output_path_missing",
            "- runtime failed: failed - publish_missing_output - Completed manifest points at a missing file.",
            "Size review: output is more than 5% larger than source.",
            "Safe next action: inspect Completed Manifest, Pending Publish, output folder, Run Logs, and Last Stderr before rerun.",
            "investigation views are display filters only and do not repair manifests",
            "Diagnostics handoff:",
            "Mutation guardrail",
          ]);
          requireText("completed-diagnostics-guidance", [
            "Selected output health: missing output",
            "Suggested order: open Completed Manifest, open Pending Publish, then read Last Stderr before rerun or cleanup.",
            "Diagnostics bridge:",
          ]);
          requireText("completed-real-media-proof-summary", [
            "Real-media output proof ladder:",
            "Blocked checkpoints:",
            "First action: stop treating this sample as proof",
            "Mutation guardrail",
          ]);
          requireText("completed-real-media-proof-detail", [
            "Checkpoint: Output and sidecar",
            "Posture: Blocked review",
            "Consistency issues: missing_sidecar, output_path_missing",
          ]);
          requireText("completed-pilot-evidence-summary", [
            "Selected pilot evidence packet:",
            "Blocked/review/manual:",
            "First action: stop before acceptance, cleanup, rerun, deletion, or another drain",
          ]);
          requireText("completed-pilot-evidence-detail", [
            "Selected pilot evidence packet:",
            "Posture: Blocked review",
            "Stop before sample acceptance",
          ]);
          requireText("completed-pilot-evidence-markdown", [
            "# Selected Completed Pilot Evidence Packet",
            "output=missing",
            "Do not append accepted Sample Validation evidence",
          ]);
          context.document.getElementById("completed-filter").value = "definitely-no-completed-match";
          context.renderCompletedRows();
          requireText("completed-filter-summary", [
            "Completed filter: text=\"definitely-no-completed-match\"; status=all; view=all signals; showing 0 of 1 row.",
            "Hidden review rows: 1.",
            "clear or change this filter before rerun, cleanup, or library decisions",
            "Mutation guardrail: filtering Completed history does not mark outputs accepted",
          ]);
          requireText("completed-detail", [
            "Selected row visible in table: no",
            "Hidden by current filters: text filter=\"definitely-no-completed-match\".",
            "selected-row detail remains visible for review",
          ]);
          context.document.getElementById("completed-filter").value = "";
          context.document.getElementById("completed-status-filter").value = "ready";
          context.renderCompletedRows();
          requireText("completed-filter-summary", [
            "Completed filter: text=none; status=ready/healthy; view=all signals; showing 0 of 1 row.",
            "Hidden review rows: 1.",
            "clear or change this filter before rerun, cleanup, or library decisions",
          ]);
          requireText("completed-detail", [
            "Hidden by current filters: status filter=ready/healthy.",
          ]);
          context.document.getElementById("completed-status-filter").value = "all";
          context.document.getElementById("completed-investigation-filter").value = "route_review";
          context.renderCompletedRows();
          requireText("completed-filter-summary", [
            "Completed filter: text=none; status=all; view=route review; showing 0 of 1 row.",
            "Hidden review rows: 1.",
            "clear or change this filter before rerun, cleanup, or library decisions",
          ]);
          requireText("completed-detail", [
            "Hidden by current filters: investigation view=route review.",
          ]);
          context.resetCompletedFilters();
          requireText("completed-filter-summary", [
            "Completed filter: text=none; status=all; view=all signals; showing 1 of 1 row.",
          ]);
          requireText("completed-detail", [
            "Selected row visible in table: yes",
            "no Completed display filter is hiding this selected row",
          ]);

          const riskPending = JSON.parse(JSON.stringify(payload.pending));
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
          context.renderPendingPublish(riskPending, {});
          context.selectPendingRow(riskPending.rows[0]);
          requireText("pending-detail", [
            "Row state: do-not-drain",
            "Diagnostic status: unreadable_manifest",
            "Diagnostic severity: error",
            "Drain recommendation: do_not_drain",
            "Health blockers: backend marked do_not_drain, diagnostic severity is error, local payload missing, 2 missing sidecars, manifest unreadable or invalid",
            "Operator action: Do not drain; repair or regenerate the pending manifest first.",
            "Recovery action: Repair the manifest and missing sidecars before backend drain.",
            "Combined pending-row drain review plan:",
            "Signals: backend do_not_drain; diagnostic error; missing payload; 2 missing sidecars; invalid/unreadable manifest; row error manifest parse failed",
            "Read first: Pending manifest -> Pending payload path -> Sidecar paths -> Last Stderr -> Run Logs",
            "Cross-check: Completed Manifest correlation -> Durable drain summary -> Queue/source route evidence before rerun -> Recovery class manifest_repair",
            "Decision: do not run Publish Parked Outputs for this row until pending artifacts and logs explain the blocker.",
            "Table status: failed",
            "Focused views: do not drain, missing payload, invalid manifest, missing sidecars",
            "Selected row visible in table: yes",
            "- do not drain: do_not_drain",
            "- missing payload:",
            "- invalid manifest:",
            "- missing sidecars: 2",
            "Drain boundary: do not drain this row until blockers are explained by pending diagnostics and logs.",
            "investigation views are display filters only and do not change backend drain scope",
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
          context.document.getElementById("pending-filter").value = "definitely-no-pending-match";
          context.renderPendingRows();
          requireText("pending-filter-summary", [
            "Pending publish filter: text=\"definitely-no-pending-match\"; status=all; view=all signals; showing 0 of 1 row.",
            "Hidden review rows: 1.",
            "clear or change this filter before publish/drain decisions",
            "Mutation guardrail: filtering Pending Publish rows does not change drain scope",
          ]);
          requireText("pending-detail", [
            "Selected row visible in table: no",
            "Hidden by current filters: text filter=\"definitely-no-pending-match\".",
            "selected-row detail remains visible for review",
          ]);
          context.document.getElementById("pending-filter").value = "";
          context.document.getElementById("pending-status-filter").value = "ready";
          context.renderPendingRows();
          requireText("pending-filter-summary", [
            "Pending publish filter: text=none; status=ready/healthy; view=all signals; showing 0 of 1 row.",
            "Hidden review rows: 1.",
            "clear or change this filter before publish/drain decisions",
          ]);
          requireText("pending-detail", [
            "Hidden by current filters: status filter=ready/healthy.",
          ]);
          context.document.getElementById("pending-status-filter").value = "all";
          context.document.getElementById("pending-investigation-filter").value = "ready_to_drain";
          context.renderPendingRows();
          requireText("pending-filter-summary", [
            "Pending publish filter: text=none; status=all; view=ready to drain; showing 0 of 1 row.",
            "Hidden review rows: 1.",
            "clear or change this filter before publish/drain decisions",
          ]);
          requireText("pending-detail", [
            "Hidden by current filters: investigation view=ready to drain.",
          ]);
          context.resetPendingFilters();
          requireText("pending-filter-summary", [
            "Pending publish filter: text=none; status=all; view=all signals; showing 1 of 1 row.",
          ]);
          requireText("pending-detail", [
            "Selected row visible in table: yes",
            "no Pending Publish display filter is hiding this selected row",
          ]);
        }

        if (errors.length) {
          throw new Error(`console errors were recorded: ${errors.join("; ")}`);
        }
        console.log(JSON.stringify({ ok: true, captured_ids: Object.keys(texts).sort() }));
        """
    )


def _run_node_row_detail_smoke(
    assets: list[dict[str, str]],
    queue: dict[str, object],
    completed: dict[str, object],
    pending: dict[str, object],
    *,
    scenario: str = "happy",
) -> dict[str, object]:
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("Node.js is required for the WebView row-detail runtime smoke.")
    with tempfile.TemporaryDirectory() as raw_tmp:
        tmp = Path(raw_tmp)
        payload_path = tmp / "row-detail-payload.json"
        runner_path = tmp / "row-detail-runner.cjs"
        payload_path.write_text(
            json.dumps(
                {"assets": assets, "queue": queue, "completed": completed, "pending": pending, "scenario": scenario},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
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
            "WebView row-detail runtime smoke failed.\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
    return json.loads(result.stdout.strip().splitlines()[-1])


def _fetch_row_detail_fixture() -> tuple[str, str, dict[str, object], dict[str, object], dict[str, object], list[dict[str, str]]]:
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
            queue_status, queue = _get_json(f"{server.url}/api/queue", token="smoke-token")
            completed_status, completed = _get_json(f"{server.url}/api/completed", token="smoke-token")
            pending_status, pending = _get_json(f"{server.url}/api/pending-publish", token="smoke-token")
            assets: list[dict[str, str]] = []
            for asset_name in ROW_DETAIL_ASSETS:
                status, source, content_type = _get_text(f"{server.url}/assets/{asset_name}")
                if status != 200:
                    raise AssertionError(f"{asset_name} returned HTTP {status}")
                if "javascript" not in content_type:
                    raise AssertionError(f"{asset_name} returned non-JavaScript content type {content_type!r}")
                assets.append({"name": asset_name, "source": source})
        finally:
            server.stop()

    if html_status != 200:
        raise AssertionError(f"WebView index returned HTTP {html_status}")
    if "text/html" not in html_type:
        raise AssertionError(f"WebView index returned non-HTML content type {html_type!r}")
    if queue_status != 200:
        raise AssertionError(f"Queue endpoint returned HTTP {queue_status}")
    if completed_status != 200:
        raise AssertionError(f"Completed endpoint returned HTTP {completed_status}")
    if pending_status != 200:
        raise AssertionError(f"Pending Publish endpoint returned HTTP {pending_status}")
    return html, html_type, queue, completed, pending, assets


class WebViewRowDetailSmokeTests(unittest.TestCase):
    def test_backend_served_webview_selected_row_details_render_diagnostics_handoff(self) -> None:
        html, _html_type, queue, completed, pending, assets = _fetch_row_detail_fixture()
        for fragment in (
            'id="queue-detail"',
            'id="queue-diagnostics-guidance"',
            'id="completed-detail"',
            'id="completed-diagnostics-guidance"',
            'id="completed-real-media-proof-summary"',
            'id="completed-real-media-proof-detail"',
            'id="completed-pilot-evidence-summary"',
            'id="completed-pilot-evidence-detail"',
            'id="completed-pilot-evidence-markdown"',
            'id="pending-detail"',
            'id="pending-diagnostics-guidance"',
        ):
            self.assertIn(fragment, html)
        self.assertGreaterEqual(len(queue["rows"]), 1)
        self.assertGreaterEqual(len(completed["rows"]), 1)
        self.assertGreaterEqual(len(pending["rows"]), 1)

        result = _run_node_row_detail_smoke(assets, queue, completed, pending)

        self.assertTrue(result["ok"])
        captured_ids = set(result["captured_ids"])
        for node_id in (
            "queue-detail",
            "queue-diagnostics-guidance",
            "completed-detail",
            "completed-diagnostics-guidance",
            "completed-real-media-proof-summary",
            "completed-real-media-proof-detail",
            "completed-pilot-evidence-summary",
            "completed-pilot-evidence-detail",
            "completed-pilot-evidence-markdown",
            "pending-detail",
            "pending-diagnostics-guidance",
        ):
            self.assertIn(node_id, captured_ids)

    def test_backend_served_webview_selected_row_details_explain_high_risk_states(self) -> None:
        _html, _html_type, queue, completed, pending, assets = _fetch_row_detail_fixture()

        result = _run_node_row_detail_smoke(assets, queue, completed, pending, scenario="adversarial")

        self.assertTrue(result["ok"])
        captured_ids = set(result["captured_ids"])
        for node_id in (
            "queue-detail",
            "queue-diagnostics-guidance",
            "completed-detail",
            "completed-diagnostics-guidance",
            "completed-real-media-proof-summary",
            "completed-real-media-proof-detail",
            "completed-pilot-evidence-summary",
            "completed-pilot-evidence-detail",
            "completed-pilot-evidence-markdown",
            "pending-detail",
            "pending-diagnostics-guidance",
        ):
            self.assertIn(node_id, captured_ids)


if __name__ == "__main__":
    unittest.main()
