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
            function requireNamespaceFunction(namespaceName, name) {
              const namespace = window[namespaceName];
              if (!namespace || typeof namespace[name] !== "function") {
                throw new Error("missing namespace function " + namespaceName + "." + name);
              }
            }
            function requireText(id, fragments) {
              const actual = text(id);
              for (const fragment of fragments) {
                if (!actual.includes(fragment)) throw new Error(id + " missing " + fragment + "\\nActual:\\n" + actual);
              }
            }
            function diagnosticRegexText(value) {
              return /(^|\\n).*(mutation|lifecycle|auth-token)?\\s*guardrail:/i.test(value)
                || /(^|\\n).*button guard:/i.test(value)
                || /(^|\\n).*selected-row diagnostic order:/i.test(value)
                || /(^|\\n).*diagnostics? (handoff|order|allowlist|actions|links|bridge):/i.test(value)
                || /read-only.*cannot\\s+(launch|drain|save|rename|repair|delete|publish|mutate|touch)/i.test(value)
                || /cannot\\s+(launch|drain|save|rename|repair|delete|publish|mutate|touch).*files?/i.test(value);
            }
            function nodeVisible(node) {
              if (!node) return false;
              const style = getComputedStyle(node);
              return style.display !== "none" && style.visibility !== "hidden" && node.getClientRects().length > 0;
            }
            async function scanVisibleDiagnosticCallouts() {
              document.body.classList.remove("advanced-mode");
              localStorage.setItem("mediapipeline-advanced-mode", "0");
              const findings = [];
              const pageButtons = Array.from(document.querySelectorAll("button[data-page]"));
              for (const pageButton of pageButtons) {
                pageButton.click();
                await new Promise((resolve) => setTimeout(resolve, 25));
                const page = pageButton.dataset.page || "unknown";
                const tabButtons = Array.from(document.querySelectorAll(".page.is-visible button[role='tab']"));
                const buttons = tabButtons.length ? tabButtons : [null];
                for (const tabButton of buttons) {
                  if (tabButton) {
                    tabButton.click();
                    await new Promise((resolve) => setTimeout(resolve, 25));
                  }
                  const tab = tabButton
                    ? (tabButton.dataset.settingsTab || tabButton.dataset.launchTab || tabButton.dataset.completedTab || tabButton.dataset.diagTab || tabButton.dataset.reportsTab || tabButton.textContent || "tab")
                    : "page";
                  document.querySelectorAll(".page.is-visible pre.prose-block").forEach((node) => {
                    if (node.closest(".diagnostic-callout")) return;
                    if (nodeVisible(node) && diagnosticRegexText(node.textContent || "")) {
                      findings.push(page + "/" + tab + ": raw prose " + (node.id || "(no id)"));
                    }
                  });
                  document.querySelectorAll(".page.is-visible .diagnostic-callout-body").forEach((node) => {
                    const details = node.closest("details");
                    if (details && !details.open) return;
                    if (nodeVisible(node) && !node.closest("details[open]")) {
                      const owner = node.closest(".diagnostic-callout");
                      findings.push(page + "/" + tab + ": visible diagnostic body " + (owner?.id || "(no id)"));
                    }
                  });
                }
              }
              const pendingButton = document.querySelector("button.nav-button[data-page='pending']");
              if (pendingButton) pendingButton.click();
              return findings;
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
              "renderPendingDrainOverview",
              "getCommandHistory"
            ].forEach(requireFunction);
            [
              "renderPendingRepairManifestControls",
              "renderPendingRepairOrphanControls",
              "requestPendingRepairManifestDryRun",
              "requestPendingRepairManifestApply",
              "requestPendingRepairOrphanDryRun",
              "requestPendingRepairOrphanApply"
            ].forEach((name) => requireNamespaceFunction("mediaPipelinePendingPublishView", name));

            window.confirm = () => {
              confirmCalls += 1;
              return true;
            };
            window.apiPost = async (path, body) => {
              posts.push({ path, body });
              if (path === "/api/pending-publish/repair-manifest-dry-run") {
                return {
                  ok: true,
                  severity: "info",
                  message: "Pending manifest repair dry-run safe.",
                  command: "pending_publish.repair_manifest_dry_run",
                  data: {
                    schema_version: "desktop_repair_reconcile_dry_run.v1",
                    candidate_command: "pending_publish.repair_manifest",
                    dry_run_only: true,
                    effect: "none",
                    scope: body.scope,
                    selected_row_keys: [body.row_key],
                    precondition_results: [{ name: "selected row", ok: true }],
                    diff_summary: {
                      schema_version: "desktop_repair_reconcile_diff_summary.v1",
                      candidate_count: 1,
                      would_write_count: 1,
                      would_move_count: 0,
                      would_delete_count: 0,
                    },
                    would_write_paths: ["backend-selected-pending-manifest"],
                    would_move_paths: [],
                    would_delete_paths: [],
                    would_not_touch: {
                      source_media: "hash unchanged",
                      payload_files: "hash unchanged",
                      output_media: "hash unchanged",
                    },
                    safe_to_apply: true,
                    mutation_route_available: true,
                    apply_route_available: true,
                    dry_run_fingerprint: "browser-dry-run-fingerprint",
                    operator_confirmation_scope: "selected row only",
                    suppress_command_journal: true,
                  },
                };
              }
              if (path === "/api/pending-publish/repair-manifest") {
                return {
                  ok: true,
                  severity: "info",
                  message: "Pending manifest repair applied.",
                  command: "pending_publish.repair_manifest",
                  data: {
                    schema_version: "desktop_repair_reconcile_apply.v1",
                    candidate_command: "pending_publish.repair_manifest",
                    effect: "pending-manifest-write",
                    selected_row_keys: [body.row_key],
                    applied: true,
                    blocked: false,
                    written_paths: ["backend-selected-pending-manifest"],
                    backup_paths: ["backend-selected-pending-manifest.backup"],
                    transaction_id: "browser-smoke",
                    rollback_status: "not_needed",
                    dry_run_fingerprint: body.dry_run_fingerprint,
                    expected_dry_run_fingerprint: body.dry_run_fingerprint,
                    source_payload_output_unchanged: true,
                  },
                };
              }
              if (path === "/api/pending-publish/reconcile-orphan-payloads-dry-run") {
                return {
                  ok: true,
                  severity: "info",
                  message: "Orphan payload reconcile dry-run safe.",
                  command: "pending_publish.reconcile_orphan_payloads_dry_run",
                  data: {
                    schema_version: "desktop_repair_reconcile_dry_run.v1",
                    candidate_command: "pending_publish.reconcile_orphan_payloads",
                    dry_run_only: true,
                    effect: "none",
                    scope: body.scope,
                    selected_row_keys: [body.row_key],
                    precondition_results: [{ name: "selected orphan row", ok: true }],
                    diff_summary: {
                      schema_version: "desktop_repair_reconcile_diff_summary.v1",
                      candidate_count: 1,
                      would_write_count: 1,
                      would_move_count: 0,
                      would_delete_count: 0,
                    },
                    would_write_paths: ["backend-proposed-pending-manifest"],
                    would_move_paths: [],
                    would_delete_paths: [],
                    would_not_touch: {
                      source_media: "hash unchanged",
                      payload_files: "hash unchanged",
                      output_media: "hash unchanged",
                    },
                    proposal_schema_version: "pending_push_manifest.v1",
                    safe_to_apply: true,
                    mutation_route_available: true,
                    apply_route_available: true,
                    dry_run_fingerprint: "browser-orphan-dry-run-fingerprint",
                    operator_confirmation_scope: "selected orphan row only",
                    suppress_command_journal: true,
                  },
                };
              }
              if (path === "/api/pending-publish/reconcile-orphan-payloads") {
                return {
                  ok: true,
                  severity: "info",
                  message: "Orphan payload reconcile applied.",
                  command: "pending_publish.reconcile_orphan_payloads",
                  data: {
                    schema_version: "desktop_repair_reconcile_apply.v1",
                    candidate_command: "pending_publish.reconcile_orphan_payloads",
                    effect: "pending-orphan-manifest-write",
                    selected_row_keys: [body.row_key],
                    applied: true,
                    blocked: false,
                    written_paths: ["backend-proposed-pending-manifest"],
                    backup_paths: [],
                    transaction_id: "browser-smoke-orphan",
                    rollback_status: "not_needed",
                    dry_run_fingerprint: body.dry_run_fingerprint,
                    expected_dry_run_fingerprint: body.dry_run_fingerprint,
                    source_payload_output_unchanged: true,
                  },
                };
              }
              return { ok: true, message: "unexpected mocked post", data: { path, body } };
            };

            window.renderPendingPublish(payload.pending, {});
            await waitFor(
              () => ["Backend check", "Review confirm"].includes(text("pending-drain-guard-status")),
              "initial guard render",
            );
            const initialGuardStatus = text("pending-drain-guard-status");
            requireText("pending-drain-overview", [
              "Pending Publish drain decision:",
              "Operator outcome:",
              "Button guard:",
              "Command boundary:",
            ]);
            const firstPendingRow = Array.isArray(payload.pending.rows) && payload.pending.rows.length ? payload.pending.rows[0] : null;
            if (!firstPendingRow) throw new Error("missing pending row for repair controls");
            window.selectPendingRow(firstPendingRow);
            await waitFor(
              () => !byId("pending-repair-manifest-dry-run-button").disabled && byId("pending-repair-manifest-apply-button").disabled,
              "pending manifest repair dry-run ready and apply disabled",
            );
            byId("pending-repair-manifest-dry-run-button").click();
            await waitFor(
              () => text("pending-repair-manifest-status") === "Dry-run safe"
                && !byId("pending-repair-manifest-apply-button").disabled,
              "pending manifest repair dry-run completed",
            );
            const repairDryRunPost = posts.find((entry) => entry.path === "/api/pending-publish/repair-manifest-dry-run");
            if (!repairDryRunPost) throw new Error("missing pending repair dry-run post: " + JSON.stringify(posts));
            const dryRunKeys = Object.keys(repairDryRunPost.body).sort();
            if (JSON.stringify(dryRunKeys) !== JSON.stringify(["limit", "reason", "row_key", "scope"])) {
              throw new Error("pending repair dry-run sent unexpected keys: " + JSON.stringify(repairDryRunPost.body));
            }
            for (const forbiddenKey of ["manifest_path", "local_file", "server_out", "source_path", "payload_path", "patch", "sidecar_json"]) {
              if (Object.prototype.hasOwnProperty.call(repairDryRunPost.body, forbiddenKey)) {
                throw new Error("pending repair dry-run sent forbidden key " + forbiddenKey + ": " + JSON.stringify(repairDryRunPost.body));
              }
            }
            byId("pending-repair-manifest-apply-button").click();
            await waitFor(
              () => text("pending-repair-manifest-status") === "Applied",
              "pending manifest repair apply completed",
            );
            const repairApplyPost = posts.find((entry) => entry.path === "/api/pending-publish/repair-manifest");
            if (!repairApplyPost) throw new Error("missing pending repair apply post: " + JSON.stringify(posts));
            if (repairApplyPost.body.confirm_apply !== true) throw new Error("pending repair apply omitted confirm_apply=true");
            if (repairApplyPost.body.dry_run_fingerprint !== "browser-dry-run-fingerprint") {
              throw new Error("pending repair apply used wrong fingerprint: " + JSON.stringify(repairApplyPost.body));
            }
            const applyKeys = Object.keys(repairApplyPost.body).sort();
            if (JSON.stringify(applyKeys) !== JSON.stringify(["confirm_apply", "dry_run_fingerprint", "limit", "reason", "row_key", "scope"])) {
              throw new Error("pending repair apply sent unexpected keys: " + JSON.stringify(repairApplyPost.body));
            }
            requireText("pending-repair-manifest-detail", [
              "Source/payload/output unchanged evidence",
              "Mutation guardrail",
            ]);
            await waitFor(
              () => !byId("pending-reconcile-orphan-dry-run-button").disabled && byId("pending-reconcile-orphan-apply-button").disabled,
              "orphan reconcile dry-run ready and apply disabled",
            );
            byId("pending-reconcile-orphan-dry-run-button").click();
            await waitFor(
              () => text("pending-reconcile-orphan-status") === "Dry-run safe"
                && !byId("pending-reconcile-orphan-apply-button").disabled,
              "orphan reconcile dry-run completed",
            );
            const orphanDryRunPost = posts.find((entry) => entry.path === "/api/pending-publish/reconcile-orphan-payloads-dry-run");
            if (!orphanDryRunPost) throw new Error("missing orphan reconcile dry-run post: " + JSON.stringify(posts));
            const orphanDryRunKeys = Object.keys(orphanDryRunPost.body).sort();
            if (JSON.stringify(orphanDryRunKeys) !== JSON.stringify(["limit", "reason", "row_key", "scope"])) {
              throw new Error("orphan reconcile dry-run sent unexpected keys: " + JSON.stringify(orphanDryRunPost.body));
            }
            for (const forbiddenKey of ["manifest_path", "local_file", "server_out", "source_path", "payload_path", "patch", "sidecar_json"]) {
              if (Object.prototype.hasOwnProperty.call(orphanDryRunPost.body, forbiddenKey)) {
                throw new Error("orphan reconcile dry-run sent forbidden key " + forbiddenKey + ": " + JSON.stringify(orphanDryRunPost.body));
              }
            }
            byId("pending-reconcile-orphan-apply-button").click();
            await waitFor(
              () => text("pending-reconcile-orphan-status") === "Applied",
              "orphan reconcile apply completed",
            );
            const orphanApplyPost = posts.find((entry) => entry.path === "/api/pending-publish/reconcile-orphan-payloads");
            if (!orphanApplyPost) throw new Error("missing orphan reconcile apply post: " + JSON.stringify(posts));
            if (orphanApplyPost.body.confirm_apply !== true) throw new Error("orphan reconcile apply omitted confirm_apply=true");
            if (orphanApplyPost.body.dry_run_fingerprint !== "browser-orphan-dry-run-fingerprint") {
              throw new Error("orphan reconcile apply used wrong fingerprint: " + JSON.stringify(orphanApplyPost.body));
            }
            const orphanApplyKeys = Object.keys(orphanApplyPost.body).sort();
            if (JSON.stringify(orphanApplyKeys) !== JSON.stringify(["confirm_apply", "dry_run_fingerprint", "limit", "reason", "row_key", "scope"])) {
              throw new Error("orphan reconcile apply sent unexpected keys: " + JSON.stringify(orphanApplyPost.body));
            }
            requireText("pending-reconcile-orphan-detail", [
              "Source/payload/output unchanged evidence",
              "Mutation guardrail",
            ]);
            if (confirmCalls !== 2) throw new Error("pending repair and orphan apply should ask for two confirmations; confirm calls=" + confirmCalls);
            posts.length = 0;
            confirmCalls = 0;
            requireText("pending-drain-decision-chips", [
              "Blocked",
              "Review",
              "Need evidence",
              "Ready",
            ]);
            requireText("pending-file-inventory-summary", [
              "Pending parked file inventory:",
              "Files scanned:",
              "Evidence boundary: directory listing only",
            ]);
            requireText("pending-file-inventory-rows", [
              "manifest",
              "referenced_payload",
              "pending manifest",
            ]);
            const emptyPending = JSON.parse(JSON.stringify(payload.pending));
            emptyPending.rows = [];
            emptyPending.count = 0;
            emptyPending.payload_count = 0;
            emptyPending.ready_count = 0;
            emptyPending.issue_count = 0;
            emptyPending.file_inventory = {
              schema_version: "desktop_pending_publish_file_inventory.v1",
              pending_root: payload.pending.pending_root || "PendingServerPush",
              exists: true,
              status: "complete",
              rows: [],
              total_count: 0,
              shown_count: 0,
              manifest_count: 0,
              payload_like_count: 0,
              referenced_payload_count: 0,
              orphan_payload_count: 0,
              total_size_text: "0 B",
              summary_lines: [
                "Pending parked file inventory:",
                "Files scanned: 0",
                "Rows shown: 0",
                "Evidence boundary: directory listing only; file bytes were not read and no files were changed.",
              ],
            };
            window.renderPendingPublish(emptyPending, {});
            await waitFor(
              () => text("pending-file-inventory-status") === "No parked files"
                && document.querySelectorAll("#pending-file-inventory-rows tr").length >= 1
                && text("pending-file-inventory-rows").includes("No parked files were reported"),
              "empty parked file inventory table stays visible",
            );
            window.renderPendingPublish(payload.pending, {});
            requireText("pending-post-drain-trust-summary", [
              "Pending Publish post-drain trust review:",
              "Decision rule: a drain is trusted only when current parked rows",
              "Mutation guardrail: read-only evidence",
              "backend routes own pending-publish changes",
            ]);
            requireText("pending-post-drain-trust-rows", [
              "Current parked state",
              "blocking=",
              "Durable drain summary",
              "Completed/Pending proof rows",
              "Decision boundary",
            ]);

            const staleSummaryPending = JSON.parse(JSON.stringify(payload.pending));
            const staleCurrentRows = Number(staleSummaryPending.count || (Array.isArray(staleSummaryPending.rows) ? staleSummaryPending.rows.length : 0) || 1);
            staleSummaryPending.drain_summary = {
              exists: true,
              schema_version: "pending_drain_summary.v1",
              started_at: "2026-07-02T23:38:13-04:00",
              completed_at: "2026-07-02T23:38:17-04:00",
              manifest_count_at_start: Math.max(0, staleCurrentRows - 1),
              attempted_count: Math.max(1, staleCurrentRows - 1),
              error_count: 1,
              remaining_count: Math.max(1, staleCurrentRows - 1),
              status_counts: { invalid_manifest: 1 },
              items: [{ status: "invalid_manifest", error: "previous stale drain failure" }],
            };
            delete staleSummaryPending.drain_confidence;
            window.renderPendingPublish(staleSummaryPending, {});
            await waitFor(
              () => ["Backend check", "Review confirm"].includes(text("pending-drain-guard-status"))
                && text("pending-drain-confidence-summary").includes("Durable drain summary")
                && text("pending-drain-confidence-summary").includes("different parked-row count")
                && text("pending-drain-decision-summary").includes("Review first"),
              "stale failed durable summary downgraded to review evidence",
            );

            const pressureSourceRow = Array.isArray(payload.pending.rows) && payload.pending.rows.length ? payload.pending.rows[0] : {};
            const pressurePending = Object.assign({}, payload.pending, {
              rows: [
                Object.assign({}, pressureSourceRow, {
                  row_key: "ready-row-under-pending-byte-pressure",
                  state: "parked",
                  diagnostic_status: "ok",
                  diagnostic_severity: "info",
                  drain_recommendation: "ready",
                  ready_to_drain: true,
                  local_exists: true,
                  missing_sidecar_count: 0,
                  issue_summary: "",
                  error: "",
                }),
              ],
              count: 1,
              payload_count: 1,
              ready_count: 1,
              issue_count: 0,
              health_count: 1,
              missing_local_count: 0,
              missing_sidecar_count: 0,
              total_bytes: 300 * 1024 * 1024 * 1024,
              warnings: ["Pending publish parked bytes exceed the autonomy review budget."],
              operator_trust_state_counts: { ready: 1 },
              recovery_class_counts: { ready_to_validate: 1 },
              drain_confidence: undefined,
            });
            window.renderPendingPublish(pressurePending, {});
            await waitFor(
              () => text("pending-drain-guard-status") === "Review confirm"
                && text("pending-drain-confidence-rows").includes("validation=Review; health=1")
                && text("pending-drain-decision-summary").includes("Review first"),
              "high pending byte pressure remains a review-only drain guard",
            );
            const pressureDrainButton = byId("pending-drain-button");
            if (!pressureDrainButton || pressureDrainButton.disabled) {
              throw new Error("pending byte pressure must not disable a drain-ready row");
            }
            const pressureActionDrainButton = byId("pending-action-drain-button");
            if (!pressureActionDrainButton || pressureActionDrainButton.disabled || pressureActionDrainButton.textContent.trim() === "Drain Blocked") {
              throw new Error("action center drain button treated pending byte pressure as a hard block");
            }
            requireText("pending-drain-guard-summary", [
              "Decision: Review first",
              "Button action: submit after explicit review confirmation",
            ]);

            window.renderPendingPublish(payload.pending, {});
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
              "Mutation guardrail: read-only evidence",
              "backend routes own pending-publish changes",
            ]);
            requireText("pending-post-drain-trust-rows", [
              "Current parked state",
              "blocking=",
              "Do not trust this drain outcome yet",
              "Sample Validation",
            ]);
            const filterScopeDecisionRow = Array.from(document.querySelectorAll("#pending-drain-decision-rows tr"))
              .find((candidate) => candidate.textContent.includes("Display filter / backend drain scope"));
            if (!filterScopeDecisionRow) throw new Error("missing Display filter / backend drain scope row");
            filterScopeDecisionRow.click();
            requireText("pending-drain-decision-detail", [
              "Checkpoint: Display filter / backend drain scope",
              "Drain Parked Outputs does not drain only the visible table subset.",
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
              () => ["Backend check", "Review confirm"].includes(text("pending-drain-guard-status")),
              "guard restored after filter-scope scenario",
            );

            const blockedRecoveryPlanResult = {
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
            };
            window.mediaPipelinePendingPublishView.renderPendingRecoveryPlanResult(blockedRecoveryPlanResult);
            await waitFor(
              () => text("pending-drain-guard-status") === "Review confirm" && text("pending-drain-guard-summary").includes("Decision: Do not drain") && text("pending-drain-decision-summary").includes("Blocked/review/read-first/unknown:"),
              "guard refresh after blocked recovery plan",
            );
            const staleReloadRow = Object.assign({}, row, {
              row_key: "fresh-current-ready-row",
              state: "ready",
              ready_to_drain: true,
              diagnostic_status: "ready",
              diagnostic_severity: "info",
              drain_recommendation: "ready",
              operator_trust_state: "ready",
              issue_summary: "",
              error: "",
              safe_next_action: "Safe next action: row looks ready, but use only the backend-owned Drain Parked Outputs command to move files.",
            });
            const staleReloadPending = Object.assign({}, payload.pending, {
              rows: [staleReloadRow],
              count: 1,
              payload_count: 1,
              ready_count: 1,
              issue_count: 0,
              health_count: 0,
              missing_local_count: 0,
              missing_sidecar_count: 0,
              operator_trust_state_counts: { ready: 1 },
              drain_confidence: undefined,
            });
            window.renderPendingPublish(staleReloadPending, {});
            await waitFor(
              () => text("pending-recovery-plan-status").includes("Recovery dry-run cleared because Pending Publish evidence changed.")
                && ["Backend check", "Review confirm"].includes(text("pending-drain-guard-status"))
                && !text("pending-drain-guard-summary").includes("Decision: Do not drain")
                && text("pending-drain-decision-summary").includes("Blocked/review/read-first/unknown: 0/"),
              "stale blocked recovery dry-run clears after changed pending payload",
            );
            requireText("pending-drain-decision-rows", [
              "Recovery dry-run",
              "no recovery dry-run plan loaded",
            ]);
            const staleGuardStatusAfterReload = text("pending-drain-guard-status");
            const staleGuardSummaryAfterReload = text("pending-drain-guard-summary");
            const staleRecoveryStatusAfterReload = text("pending-recovery-plan-status");
            const staleDecisionSummaryAfterReload = text("pending-drain-decision-summary");
            window.renderPendingPublish(payload.pending, {});
            window.mediaPipelinePendingPublishView.renderPendingRecoveryPlanResult(blockedRecoveryPlanResult);
            await waitFor(
              () => text("pending-drain-guard-status") === "Review confirm" && text("pending-drain-guard-summary").includes("Decision: Do not drain"),
              "guard restored after stale recovery regression check",
            );
            if (typeof window.applyAdvancedModePreference === "function") {
              window.applyAdvancedModePreference(false);
            } else {
              document.body.classList.remove("advanced-mode");
              localStorage.setItem("mediapipeline-advanced-mode", "0");
            }
            const blockedDrainButton = byId("pending-drain-button");
            if (!blockedDrainButton || blockedDrainButton.disabled || blockedDrainButton.getAttribute("aria-disabled") !== "false") {
              throw new Error("advisory evidence must leave the backend Drain Parked Outputs submission enabled");
            }
            const blockedActionDrainButton = byId("pending-action-drain-button");
            if (!blockedActionDrainButton || blockedActionDrainButton.disabled || blockedActionDrainButton.getAttribute("aria-disabled") !== "false") {
              throw new Error("advisory evidence must leave the visible Action Center drain submission enabled");
            }
            if (blockedActionDrainButton.textContent.trim() !== "Submit Drain After Review") {
              throw new Error("Action Center drain button did not show the advisory review label: " + blockedActionDrainButton.textContent);
            }
            const normalGuardBrief = document.querySelector("#pending-drain-guard-summary .diagnostic-callout-brief");
            const normalGuardDetails = document.querySelector("#pending-drain-guard-summary .diagnostic-callout-details");
            const normalGuardAdvanced = document.querySelector("#pending-drain-guard-summary .diagnostic-callout-advanced");
            if (normalGuardBrief || !normalGuardDetails || !normalGuardAdvanced) {
              throw new Error("normal mode guard did not render the compact Why-only diagnostic callout");
            }
            if (!normalGuardDetails.textContent.includes("Why?") || normalGuardDetails.open) {
              throw new Error("normal mode guard Why disclosure missing or open by default");
            }
            if (getComputedStyle(normalGuardAdvanced).display !== "none") {
              throw new Error("normal mode guard advanced diagnostics were visible"
                + "; display=" + getComputedStyle(normalGuardAdvanced).display
                + "; bodyClass=" + document.body.className
                + "; matchesDataAdvanced=" + normalGuardAdvanced.matches("[data-advanced]")
                + "; closestAdvanced=" + Boolean(normalGuardAdvanced.closest(".advanced-mode"))
                + "; attr=" + normalGuardAdvanced.getAttribute("data-advanced"));
            }
            const visibleDiagnosticFindings = await scanVisibleDiagnosticCallouts();
            if (visibleDiagnosticFindings.length) {
              throw new Error("normal mode exposed diagnostic callouts across pages/tabs:\\n" + visibleDiagnosticFindings.join("\\n"));
            }
            requireText("pending-drain-guard-summary", [
              "WebView evidence advises against draining: Do not drain.",
              "only backend validation can allow or refuse drain work",
              "Mutation guardrail",
            ]);
            byId("advanced-toggle").click();
            await waitFor(
              () => document.body.classList.contains("advanced-mode")
                && getComputedStyle(document.querySelector("#pending-drain-guard-summary .diagnostic-callout-advanced")).display !== "none"
                && text("pending-drain-guard-summary").includes("Mutation guardrail")
                && text("pending-drain-guard-summary").includes("Pending table filter:"),
              "advanced mode shows full pending drain guard diagnostics",
            );

            await window.mediaPipelineLaunchView.startPendingPublishDrain();
            await waitFor(
              () => text("pending-drain-status") !== "Confirming"
                && window.getCommandHistory().some((entry) => entry.command === "pending_publish.drain"),
              "advisory drain submitted to backend",
            );
            const history = window.getCommandHistory().filter((entry) => entry.command === "pending_publish.drain");
            if (!history.length) throw new Error("backend drain result was not added to command history");
            if (confirmCalls !== 1) {
              throw new Error("advisory drain should ask for one operator confirmation; confirm calls=" + confirmCalls);
            }
            requireText("pending-drain-history", [
              "pending_publish.drain",
              "pending_publish.drain",
            ]);
            requireText("pending-post-drain-trust-summary", [
              "Blocked/review/read-first/unknown:",
              "First action: stop treating this drain as trusted",
              "Mutation guardrail: read-only evidence",
              "backend routes own pending-publish changes",
            ]);
            const blockedGuardStatusBeforeStaleReload = text("pending-drain-guard-status");
            const blockedGuardSummaryBeforeStaleReload = text("pending-drain-guard-summary");
            const blockedPostDrainTrustStatusBeforeStaleReload = text("pending-post-drain-trust-status");
            const blockedPostDrainTrustSummaryBeforeStaleReload = text("pending-post-drain-trust-summary");
            const blockedDrainStatusBeforeStaleReload = text("pending-drain-status");
            const blockedDrainDetailBeforeStaleReload = text("pending-drain-detail");
            const blockedHistoryTextBeforeStaleReload = text("pending-drain-history");
            return {
              ok: true,
              initialGuardStatus,
              guardStatus: blockedGuardStatusBeforeStaleReload,
              guardSummary: blockedGuardSummaryBeforeStaleReload,
              drainStatus: blockedDrainStatusBeforeStaleReload,
              drainDetail: blockedDrainDetailBeforeStaleReload,
              postDrainTrustStatus: blockedPostDrainTrustStatusBeforeStaleReload,
              postDrainTrustSummary: blockedPostDrainTrustSummaryBeforeStaleReload,
              historyText: blockedHistoryTextBeforeStaleReload,
              staleGuardStatus: staleGuardStatusAfterReload,
              staleGuardSummary: staleGuardSummaryAfterReload,
              staleRecoveryStatus: staleRecoveryStatusAfterReload,
              staleDecisionSummary: staleDecisionSummaryAfterReload,
              postPaths: posts.map((entry) => entry.path),
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


class WebViewBrowserPendingDrainGuardSmoke(unittest.TestCase):
    def test_real_browser_refreshes_advisory_and_submits_drain_to_backend(self) -> None:
        browser_path = _find_browser()
        if not browser_path:
            raise unittest.SkipTest("Chrome or Edge is required for the browser-backed Pending Publish drain guard smoke.")

        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved, _source, _output = _write_fixture_state(root)
            resolved.config_data["NetworkRole"] = "standalone"
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
            self.assertIsNotNone(service.started_pipeline)
            self.assertEqual(service.started_pipeline["mode"], "drain_pending_pushes")
            assert_media_no_mutation(self, media_snapshot)

        self.assertTrue(result["ok"])
        browser_result = result["result"]
        self.assertIn(browser_result["initialGuardStatus"], {"Backend check", "Review confirm"})
        self.assertEqual(browser_result["guardStatus"], "Review confirm")
        self.assertIn("Decision: Do not drain", browser_result["guardSummary"])
        self.assertNotEqual(browser_result["drainStatus"], "Blocked")
        self.assertIn("pending_publish.drain", browser_result["historyText"])
        self.assertIn(browser_result["staleGuardStatus"], {"Backend check", "Review confirm"})
        self.assertIn("Recovery dry-run cleared because Pending Publish evidence changed.", browser_result["staleRecoveryStatus"])
        self.assertNotIn("Decision: Do not drain", browser_result["staleGuardSummary"])
        self.assertIn("Blocked/review/read-first/unknown: 0/", browser_result["staleDecisionSummary"])
        self.assertEqual(browser_result["confirmCalls"], 1)


if __name__ == "__main__":
    unittest.main()
