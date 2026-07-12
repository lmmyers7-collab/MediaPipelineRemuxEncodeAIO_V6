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
from mediapipeline.desktop.models import Snapshot

try:  # unittest discovery can import tests as top-level modules or package modules.
    from .test_application_facade import DummyWorkflowFacadeService
    from .test_webview_real_media_smoke import _get_json, _write_high_risk_fixture_state
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
    from test_webview_real_media_smoke import _get_json, _write_high_risk_fixture_state
    from webview_browser_smoke_support import (
        assert_media_no_mutation,
        browser_cdp_runner_prelude,
        capture_media_no_mutation_snapshot,
        find_browser as _find_browser,
        free_port as _free_port,
        run_node_browser_smoke,
    )


def _browser_diagnostics_handoff_runner_source() -> str:
    return browser_cdp_runner_prelude() + textwrap.dedent(
        r"""
        function diagnosticsHandoffScript(data) {
          return `
          (async () => {
            const payload = ${JSON.stringify(data)};
            function byId(id) { return document.getElementById(id); }
            function text(id) { const node = byId(id); return node ? node.textContent || "" : ""; }
            function value(id) { const node = byId(id); return node ? node.value || "" : ""; }
            function state(id) { const node = byId(id); return node ? node.dataset.state || "" : ""; }
            function inlineStatus(selector) {
              const node = document.querySelector(selector);
              const status = node?.nextElementSibling;
              return status?.classList?.contains("inline-action-status") ? status.textContent || "" : "";
            }
            function inlineActionText(node) {
              const status = node?.nextElementSibling;
              return status?.classList?.contains("inline-action-status") ? status.textContent || "" : "";
            }
            function selectorText(selector) {
              const node = document.querySelector(selector);
              return node ? node.innerText || node.textContent || "" : "";
            }
            function tdarrButton(action) {
              const node = document.querySelector('[data-tdarr-matrix-audit-action="' + action + '"]');
              if (!node) throw new Error("missing Tdarr Matrix action " + action);
              return node;
            }
            function tdarrGate(action) {
              const node = tdarrButton(action);
              return {
                action,
                disabled: Boolean(node.disabled),
                gateState: node.dataset.gateState || "",
                severity: node.dataset.severity || "",
                title: node.title || "",
                inline: inlineActionText(node),
              };
            }
            function assertTdarrGate(action, disabled, label) {
              const gate = tdarrGate(action);
              if (gate.disabled !== disabled) {
                throw new Error(label + " expected " + action + " disabled=" + disabled + " but saw " + JSON.stringify(gate));
              }
              return gate;
            }
            function requireText(id, fragments) {
              const actual = text(id);
              for (const fragment of fragments) {
                if (!actual.includes(fragment)) throw new Error(id + " missing " + fragment + "\\nActual:\\n" + actual);
              }
            }
            function requireFunction(name) {
              if (typeof window[name] !== "function") throw new Error("missing global function " + name);
            }
            function tableText(id) { const node = byId(id); return node ? node.innerText || node.textContent || "" : ""; }
            function clickActiveJobRow(fragment) {
              const rows = Array.from(document.querySelectorAll('#active-job-detail-rows tr[data-selectable-row="true"]'));
              const row = rows.find((candidate) => (candidate.innerText || candidate.textContent || "").includes(fragment));
              if (!row) throw new Error("missing ActiveJobs row for " + fragment + "\\nActual:\\n" + tableText("active-job-detail-rows"));
              row.click();
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
              throw new Error("Timed out waiting for " + label + (lastError ? ": " + lastError.message : "") + "\\nDiagnostics state:\\n" + [
                "queue=" + text("queue-diagnostics-status"),
                "completed=" + text("completed-diagnostics-status"),
                "pending=" + text("pending-diagnostics-status"),
                "pendingFilter=" + text("pending-filter-summary"),
                "tailStatus=" + text("diagnostics-tail-status"),
                "tailTarget=" + value("diagnostics-tail-target"),
                "tailDetail=" + text("diagnostics-tail-detail"),
                "tailText=" + text("diagnostics-tail-text"),
              ].join("\\n"));
            }
            function click(selector, label) {
              const node = document.querySelector(selector);
              if (!node) throw new Error("missing " + label + " selector " + selector);
              node.click();
            }
            function clickOwnerHandoffRow(owner) {
              const rows = Array.from(document.querySelectorAll('#diagnostics-owner-handoff-rows tr[data-selectable-row="true"]'));
              const row = rows.find((candidate) => String(candidate.children?.[0]?.textContent || "").trim() === owner);
              if (!row) throw new Error("missing Diagnostics owner handoff row for " + owner);
              row.click();
            }
            function clickStateSummaryRow(target) {
              const rows = Array.from(document.querySelectorAll('#diagnostics-state-summary-rows tr[data-selectable-row="true"]'));
              const row = rows.find((candidate) => String(candidate.children?.[0]?.textContent || "").trim() === target);
              if (!row) throw new Error("missing Diagnostics state artifact row for " + target);
              row.click();
            }
            function clickStateTriageRow(target) {
              const rows = Array.from(document.querySelectorAll('#diagnostics-state-triage-rows tr[data-selectable-row="true"]'));
              const row = rows.find((candidate) => String(candidate.children?.[1]?.textContent || "").trim() === target);
              if (!row) throw new Error("missing Diagnostics state triage row for " + target);
              row.click();
            }
            function setInput(selector, valueText, label) {
              const node = document.querySelector(selector);
              if (!node) throw new Error("missing " + label + " selector " + selector);
              node.value = valueText;
              node.dispatchEvent(new Event("input", { bubbles: true }));
            }
            function setSelect(selector, valueText, label) {
              const node = document.querySelector(selector);
              if (!node) throw new Error("missing " + label + " selector " + selector);
              node.value = valueText;
              node.dispatchEvent(new Event("change", { bubbles: true }));
            }
            function visiblePage(page) {
              return Boolean(document.querySelector('[data-page-panel="' + page + '"]')?.classList.contains("is-visible"));
            }
            function historyHasTarget(target) {
              const entries = typeof window.getCommandHistory === "function" ? window.getCommandHistory() : [];
              return entries.some((entry) => {
                const raw = entry.raw || {};
                const request = raw.request || {};
                const data = raw.data || {};
                return entry.command === "diagnostics.open" && (request.target === target || data.target === target);
              });
            }
            function checkPanelStatus(id, expectedText, expectedState, label) {
              const actualText = text(id);
              const actualState = state(id);
              if (!actualText.includes(expectedText) || actualState !== expectedState) {
                throw new Error(label + " expected " + expectedText + "/" + expectedState + " but saw " + actualText + "/" + actualState);
              }
              return { id, text: actualText, state: actualState };
            }
            function checkReadBeforeOpen(groupText, readLabel, openLabel, label) {
              const readIndex = groupText.indexOf(readLabel);
              const openIndex = groupText.indexOf(openLabel);
              if (readIndex < 0 || openIndex < 0 || readIndex > openIndex) {
                throw new Error(label + " expected " + readLabel + " before " + openLabel + "\\nActual:\\n" + groupText);
              }
            }
            function delay(ms) {
              return new Promise((resolve) => setTimeout(resolve, ms));
            }
            async function runDiagnosticsHardeningChecks() {
              const checks = {
                groupedAccess: {},
                commandEvidence: {},
                duplicateSuppression: {},
                staleRefresh: {},
                logStates: [],
                tailStates: [],
                tdarr: {},
              };

              window.showPage("diagnostics");
              const groupedText = selectorText(".diagnostics-open-target-groups");
              ["Logs", "Config / Workspace", "State Artifacts", "Failure Evidence", "Validation Evidence"].forEach((label) => {
                if (!groupedText.includes(label)) throw new Error("missing grouped allowlisted file access section " + label);
              });
              checkReadBeforeOpen(groupedText, "Read Last Stderr", "Open Run Logs", "Logs group read/open order");
              checkReadBeforeOpen(groupedText, "Read Queue Snapshot", "Open Queue Snapshot", "State Artifacts group read/open order");
              checks.groupedAccess = { groupsPresent: true, readBeforeOpen: true };

              const commandDetail = document.getElementById("diagnostics-command-drilldown-summary");
              const commandRaw = document.getElementById("diagnostics-command-history");
              if (!commandDetail || !commandRaw || !(commandDetail.compareDocumentPosition(commandRaw) & Node.DOCUMENT_POSITION_FOLLOWING)) {
                throw new Error("Command Detail must appear before raw Commands Evidence.");
              }
              checks.commandEvidence.commandDetailBeforeRaw = true;
              checks.commandEvidence.rawEvidenceNote = selectorText("#diagnostics-command-history").includes("Structured command drilldown above");
              if (!text("api-contract-safety-summary").includes("route presence is evidence only")) {
                throw new Error("contract safety summary must distinguish route presence from safe action");
              }
              checks.commandEvidence.contractRoutePresenceBoundary = true;

              const originalApiGet = window.mediaPipelineApi.apiGet;
              const originalApiPost = window.mediaPipelineApi.apiPost;
              const originalConfirm = window.confirm;
              try {
                const duplicateTailButton = document.createElement("button");
                duplicateTailButton.id = "diagnostics-duplicate-tail-button";
                duplicateTailButton.type = "button";
                duplicateTailButton.textContent = "Duplicate Tail Fixture";
                document.body.appendChild(duplicateTailButton);
                let finishTail = null;
                window.mediaPipelineApi.apiGet = async (path) => {
                  if (!String(path || "").includes("/api/diagnostics/tail")) throw new Error("unexpected duplicate tail path " + path);
                  return new Promise((resolve) => {
                    finishTail = () => resolve({
                      ok: true,
                      target: "last_stderr_log",
                      label: "Last Stderr",
                      exists: true,
                      is_file: true,
                      text: "duplicate fixture tail",
                      max_bytes: 65536,
                    });
                  });
                };
                const firstTail = window.requestDiagnosticsTail("last_stderr_log", duplicateTailButton);
                await waitFor(() => inlineActionText(duplicateTailButton).includes("Reading"), "duplicate tail first busy");
                await window.requestDiagnosticsTail("last_stderr_log", duplicateTailButton);
                checks.duplicateSuppression.tail = inlineActionText(duplicateTailButton);
                if (!checks.duplicateSuppression.tail.includes("already in progress")) {
                  throw new Error("duplicate tail click did not show in-place suppression feedback: " + checks.duplicateSuppression.tail);
                }
                finishTail();
                await firstTail;

                const duplicateOpenButton = document.createElement("button");
                duplicateOpenButton.id = "diagnostics-duplicate-open-button";
                duplicateOpenButton.type = "button";
                duplicateOpenButton.textContent = "Duplicate Open Fixture";
                document.body.appendChild(duplicateOpenButton);
                let finishOpen = null;
                window.mediaPipelineApi.apiPost = async (path, body) => {
                  if (path !== "/api/diagnostics/open") throw new Error("unexpected duplicate open path " + path);
                  return new Promise((resolve) => {
                    finishOpen = () => resolve({
                      command: "diagnostics.open",
                      ok: true,
                      message: "Fixture open completed.",
                      request: body || {},
                    });
                  });
                };
                const firstOpen = window.requestDiagnosticsOpen("queue_snapshot", duplicateOpenButton);
                await waitFor(() => inlineActionText(duplicateOpenButton).includes("Opening"), "duplicate open first busy");
                await window.requestDiagnosticsOpen("queue_snapshot", duplicateOpenButton);
                checks.duplicateSuppression.open = inlineActionText(duplicateOpenButton);
                if (!checks.duplicateSuppression.open.includes("already in progress")) {
                  throw new Error("duplicate open click did not show in-place suppression feedback: " + checks.duplicateSuppression.open);
                }
                finishOpen();
                await firstOpen;
              } finally {
                window.mediaPipelineApi.apiGet = originalApiGet;
                window.mediaPipelineApi.apiPost = originalApiPost;
                window.confirm = originalConfirm;
              }

              window.mediaPipelineDiagnosticsView.renderDiagnosticsRefreshFailures([
                { name: "diagnostics", message: "fixture diagnostics refresh failed" },
                { name: "diagnostics state summary", message: "fixture state refresh failed" },
                { name: "commands", message: "fixture command refresh failed" },
                { name: "contract", message: "fixture contract refresh failed" },
              ]);
              checks.staleRefresh.diagnostics = checkPanelStatus("diagnostics-pipeline-log-status", "showing stale data", "warning", "diagnostics stale marker");
              checks.staleRefresh.state = checkPanelStatus("diagnostics-state-summary-status", "showing stale data", "warning", "state stale marker");
              checks.staleRefresh.commands = checkPanelStatus("diagnostics-command-status", "showing stale data", "warning", "commands stale marker");
              checks.staleRefresh.contract = checkPanelStatus("api-contract-status", "showing stale data", "warning", "contract stale marker");

              [
                [{ log_tail: "pipeline loaded", launch_logs: "launch loaded" }, "Loaded", "ready", "loaded"],
                [{ log_tail: "", launch_logs: "" }, "Empty", "empty", "empty"],
                [{ log_tail: "", log_tail_missing: true, launch_logs: "", launch_logs_missing: true }, "Missing", "warning", "missing"],
                [{ log_tail: "", log_tail_unavailable: true, launch_logs: "", launch_logs_unavailable: true }, "Unavailable", "warning", "unavailable"],
                [{ log_tail: "pipeline partial", log_tail_truncated: true, launch_logs: "launch partial", launch_logs_truncated: true }, "Loaded truncated", "warning", "truncated"],
                [{ log_tail: "", log_tail_error: "fixture read failed", launch_logs: "", launch_logs_error: "fixture launch read failed" }, "Read error", "blocked", "read-error"],
              ].forEach(([payloadCase, expectedText, expectedState, label]) => {
                window.renderDiagnostics(payloadCase);
                checks.logStates.push({
                  label,
                  pipeline: checkPanelStatus("diagnostics-pipeline-log-status", expectedText, expectedState, "pipeline log " + label),
                  launch: checkPanelStatus("diagnostics-launch-log-status", expectedText, expectedState, "launch log " + label),
                });
              });

              [
                [{ ok: true, target: "last_stderr_log", label: "Last Stderr", exists: true, is_file: true, text: "tail loaded" }, "Loaded", "ready", "loaded"],
                [{ ok: true, target: "last_stderr_log", label: "Last Stderr", exists: true, is_file: true, text: "" }, "Empty", "empty", "empty"],
                [{ ok: false, target: "last_stderr_log", label: "Last Stderr", warnings: ["No path is configured for Last Stderr."] }, "Missing", "warning", "missing"],
                [{ ok: false, target: "active_jobs", label: "Active Jobs", warnings: ["Target resolved to a non-regular file."] }, "Unavailable", "warning", "unavailable"],
                [{ ok: true, target: "cluster_log", label: "Cluster Log", exists: true, is_file: true, text: "tail partial", truncated: true }, "Loaded truncated", "warning", "truncated"],
                [{ ok: false, target: "cluster_log", label: "Cluster Log", errors: ["fixture read failed"] }, "Read error", "blocked", "read-error"],
              ].forEach(([payloadCase, expectedText, expectedState, label]) => {
                window.mediaPipelineDiagnosticsView.renderDiagnosticsTail(payloadCase);
                checks.tailStates.push({
                  label,
                  fileLog: checkPanelStatus("diagnostics-tail-status", expectedText, expectedState, "file log " + label),
                });
              });

              const latestTdarrPayload = {
                latest_run_id: "tdarr-fixture-run-1",
                run: { run_id: "tdarr-fixture-run-1", report_exists: true },
                runs: [{ run_id: "tdarr-fixture-run-1" }, { run_id: "tdarr-fixture-run-0" }],
                findings: [{
                  finding_key: "fixture-finding",
                  run_id: "tdarr-fixture-run-1",
                  severity: "error",
                  diagnostic_bucket: "video",
                  route: "encode",
                  message: "fixture proof failure",
                  evidence_targets: ["report"],
                }],
                finding_count: 1,
                proof_pack_rows: [{
                  test_name: "fixture proof",
                  pack: "proof-pack",
                  diagnostic_bucket: "video",
                  view: "encode",
                  status: "passed",
                  run_id: "tdarr-fixture-run-1",
                  evidence: "fixture proof evidence",
                }],
                smoke_pack_rows: [{
                  test_name: "fixture smoke",
                  pack: "smoke-pack",
                  diagnostic_bucket: "startup",
                  view: "smoke",
                  status: "passed",
                  run_id: "tdarr-fixture-run-1",
                  evidence: "fixture smoke evidence",
                }],
                bucket_summary: [{ diagnostic_bucket: "video", finding_count: 1, severity: "error" }],
              };
              window.mediaPipelineDiagnosticsView.renderTdarrMatrixConsole({ latest_run_id: "", run: {}, runs: [], findings: [], proof_pack_rows: [], smoke_pack_rows: [], bucket_summary: [] });
              checks.tdarr.initial = {
                prepare: assertTdarrGate("prepare-proof-pack", false, "initial Tdarr gate"),
                proof: assertTdarrGate("proof-pack", true, "initial Tdarr gate"),
                strict: assertTdarrGate("strict-report", true, "initial Tdarr gate"),
                cleanupPlan: assertTdarrGate("cleanup-plan", true, "initial Tdarr gate"),
                cleanupArchive: assertTdarrGate("cleanup-archive", true, "initial Tdarr gate"),
                delete: assertTdarrGate("cleanup-delete", true, "initial Tdarr gate"),
              };
              if (checks.tdarr.initial.strict.severity !== "warning" || tdarrGate("cleanup-delete").gateState !== "blocked") {
                throw new Error("initial Tdarr severity/gate states are not explicit enough: " + JSON.stringify(checks.tdarr.initial));
              }

              const tdarrPosts = [];
              let tdarrLatestCalls = 0;
              try {
                window.mediaPipelineApi.apiGet = async (path) => {
                  const route = String(path || "");
                  if (route.includes("/api/diagnostics/tdarr-matrix/latest")) {
                    tdarrLatestCalls += 1;
                    return latestTdarrPayload;
                  }
                  if (route.includes("/api/diagnostics/tdarr-matrix/compare")) {
                    return { counts: { new: 1, resolved: 0, repeated: 0, changed: 0 }, rows: [] };
                  }
                  throw new Error("unexpected Tdarr apiGet " + route);
                };
                window.mediaPipelineApi.apiPost = async (path, body) => {
                  if (path !== "/api/diagnostics/tdarr-matrix-audit") throw new Error("unexpected Tdarr apiPost " + path);
                  tdarrPosts.push({ path, body: body || {} });
                  if (body?.action === "cleanup-delete") {
                    return {
                      command: "diagnostics.tdarr_matrix_audit",
                      ok: false,
                      severity: "Failed",
                      message: "Backend rejected fixture delete.",
                      data: { action: "cleanup-delete", finding_count: 0, manifest_count: 0 },
                    };
                  }
                  return {
                    command: "diagnostics.tdarr_matrix_audit",
                    ok: true,
                    message: "Fixture " + body?.action + " completed.",
                    data: { action: body?.action || "unknown", finding_count: 1, manifest_count: 1, run_id: "tdarr-fixture-run-1" },
                  };
                };

                click("#tdarr-matrix-audit-load-latest", "tdarr load latest");
                await waitFor(() => text("tdarr-matrix-audit-status").includes("Latest loaded"), "tdarr latest loaded");
                checks.tdarr.afterLatest = {
                  proof: assertTdarrGate("proof-pack", false, "after latest Tdarr gate"),
                  strict: assertTdarrGate("strict-report", false, "after latest Tdarr gate"),
                  cleanupPlan: assertTdarrGate("cleanup-plan", false, "after latest Tdarr gate"),
                  cleanupArchive: assertTdarrGate("cleanup-archive", true, "after latest Tdarr gate"),
                  delete: assertTdarrGate("cleanup-delete", true, "after latest Tdarr gate"),
                  latestCalls: tdarrLatestCalls,
                };

                click('[data-tdarr-matrix-audit-action="cleanup-plan"]', "tdarr cleanup plan");
                await waitFor(() => tdarrPosts.some((entry) => entry.body.action === "cleanup-plan") && !tdarrButton("cleanup-archive").disabled, "tdarr cleanup plan enables archive");
                checks.tdarr.afterCleanupPlan = { cleanupArchive: assertTdarrGate("cleanup-archive", false, "after cleanup plan Tdarr gate") };

                click('[data-tdarr-matrix-audit-action="cleanup-archive"]', "tdarr cleanup archive");
                await waitFor(
                  () => tdarrPosts.some((entry) => entry.body.action === "cleanup-archive")
                    && tdarrButton("cleanup-delete").disabled
                    && tdarrGate("cleanup-delete").gateState === "blocked",
                  "tdarr cleanup archive keeps delete typed-gated",
                );
                checks.tdarr.afterArchive = { deleteBeforeText: assertTdarrGate("cleanup-delete", true, "after archive Tdarr delete gate") };
                setInput("#tdarr-matrix-delete-confirm", "WRONG", "tdarr delete confirm");
                checks.tdarr.afterWrongText = { delete: assertTdarrGate("cleanup-delete", true, "wrong delete text Tdarr gate") };
                setInput("#tdarr-matrix-delete-confirm", "DELETE VERIFIED MATRIX", "tdarr delete confirm");
                checks.tdarr.afterTypedText = { delete: assertTdarrGate("cleanup-delete", false, "typed delete text Tdarr gate") };

                window.confirm = () => false;
                click('[data-tdarr-matrix-audit-action="cleanup-delete"]', "tdarr cleanup delete cancel");
                await waitFor(() => text("tdarr-matrix-audit-status").includes("Cancelled"), "tdarr delete cancellation");
                if (tdarrPosts.some((entry) => entry.body.action === "cleanup-delete")) {
                  throw new Error("cancelled Tdarr delete still posted to backend fixture");
                }
                checks.tdarr.cancelledDelete = text("tdarr-matrix-audit-detail");

                window.confirm = () => true;
                click('[data-tdarr-matrix-audit-action="cleanup-delete"]', "tdarr cleanup delete backend rejection");
                await waitFor(() => text("tdarr-matrix-audit-status").includes("Failed") && text("tdarr-matrix-audit-detail").includes("Backend rejected fixture delete."), "tdarr delete backend rejection");
                const deletePost = tdarrPosts.find((entry) => entry.body.action === "cleanup-delete");
                if (!deletePost?.body?.confirm_delete_full_matrix) {
                  throw new Error("Tdarr delete backend request did not carry confirm_delete_full_matrix: " + JSON.stringify(deletePost));
                }
                checks.tdarr.backendRejectedDelete = {
                  status: checkPanelStatus("tdarr-matrix-audit-status", "Failed", "blocked", "tdarr delete rejection status"),
                  detail: text("tdarr-matrix-audit-detail"),
                  posts: tdarrPosts.map((entry) => entry.body.action),
                };
              } finally {
                window.mediaPipelineApi.apiGet = originalApiGet;
                window.mediaPipelineApi.apiPost = originalApiPost;
                window.confirm = originalConfirm;
              }
              return checks;
            }
            [
              "renderQueue", "selectQueueRow",
              "renderPendingPublish", "selectPendingRow",
              "requestDiagnosticsTail", "requestDiagnosticsOpen",
              "renderDiagnosticsOwnerHandoff", "navigateDiagnosticsOwnerHandoffRow",
              "renderDiagnosticsStateSummary",
              "renderDiagnostics", "renderDiagnosticsProgress",
              "renderDiagnosticsFirstResponse", "diagnosticsFirstResponseDetailLines",
              "diagnosticsSamplePolicyReconciliation", "diagnosticsCompletedPolicyReconciliationLines",
              "externalDependencyRows",
              "renderContract", "contractSafetyReviewRows", "renderContractSafetyReview",
              "getCommandHistory", "showPage"
            ].forEach(requireFunction);
            if (typeof window.mediaPipelineSettingsView?.renderSettings !== "function") {
              throw new Error("missing mediaPipelineSettingsView.renderSettings");
            }
            if (typeof window.mediaPipelineCompletedView?.renderCompleted !== "function") {
              throw new Error("missing mediaPipelineCompletedView.renderCompleted");
            }
            if (typeof window.mediaPipelineCompletedView?.selectCompletedRow !== "function") {
              throw new Error("missing mediaPipelineCompletedView.selectCompletedRow");
            }

            const queueRow = payload.queue.rows[0];
            window.renderQueue(payload.queue);
            if (payload.tableClickRows) {
              click('#queue-rows tr[data-row-key]', "queue table row");
              await waitFor(
                () => text("queue-detail").includes("Row state: blocked") && text("queue-detail").includes("tv_parse_unreliable") && text("queue-detail").includes("Selected row quick signal:") && text("queue-detail").includes("Combined row review plan:") && text("queue-detail").includes("Investigation view matches:"),
                "queue table row selection",
              );
              setInput("#queue-filter", "definitely-no-queue-match", "queue filter");
              await waitFor(
                () => text("queue-filter-summary").includes("Hidden review rows: 1.") && text("queue-filter-summary").includes("clear or change this filter before launch decisions"),
                "queue filter hidden review guardrail",
              );
              setInput("#queue-filter", "", "queue filter");
              setSelect("#queue-status-filter", "ready", "queue status filter");
              await waitFor(
                () => text("queue-filter-summary").includes("status=ready/healthy") && text("queue-filter-summary").includes("Hidden review rows: 1."),
                "queue status filter hidden review guardrail",
              );
              setSelect("#queue-status-filter", "all", "queue status filter");
              setSelect("#queue-investigation-filter", "priority", "queue investigation filter");
              await waitFor(
                () => text("queue-filter-summary").includes("view=priority rows") && text("queue-filter-summary").includes("Hidden review rows: 1."),
                "queue investigation filter hidden review guardrail",
              );
              await waitFor(
                () => text("queue-detail").includes("Selected row visible in table: no") && text("queue-detail").includes("Hidden by current filters: investigation view=priority rows."),
                "queue selected row hidden by investigation filter detail",
              );
              click("#queue-clear-filters-button", "queue clear filters");
              await waitFor(
                () => text("queue-detail").includes("Selected row visible in table: yes") && text("queue-filter-summary").includes("view=all signals"),
                "queue clear filters restores selected row visibility",
              );
            } else {
              window.selectQueueRow(queueRow);
            }
            click('#queue-diagnostics-actions [data-diagnostics-bridge-target="last_stderr_log"]', "queue diagnostics bridge");
            await waitFor(
              () => visiblePage("diagnostics") && value("diagnostics-tail-target") === "last_stderr_log" && text("diagnostics-tail-detail").includes("Bridge source: Queue selected row"),
              "queue diagnostics bridge handoff",
            );
            requireText("diagnostics-tail-detail", [
              "Bridge source: Queue selected row",
              "Target: last_stderr_log",
              "Guardrail: bridge selection does not read files, open paths, mutate queue state, or publish outputs.",
            ]);
            window.showPage("queue");
            click('#queue-diagnostics-actions [data-queue-diagnostics-action="tail"][data-queue-diagnostics-target="last_stderr_log"]', "queue stderr tail");
            await waitFor(
              () => text("diagnostics-tail-status").includes("Loaded") && text("diagnostics-tail-text").includes("source_locked"),
              "queue stderr tail read",
            );
            requireText("diagnostics-tail-text", ["source_locked", "publish_missing_output"]);
            requireText("diagnostics-tail-evidence", [
              "Tail posture (backend): blocked",
              "Evidence authority: backend",
              "errors=1",
              "warnings=1",
              "Safe next action:",
              "Diagnostics tail evidence is read-only",
              "Latest issue lines:",
              "source_locked",
              "Latest warning lines:",
              "publish_missing_output",
            ]);
            click('#queue-diagnostics-actions [data-queue-diagnostics-action="open"][data-queue-diagnostics-target="queue_snapshot"]', "queue snapshot open");
            await waitFor(
              () => historyHasTarget("queue_snapshot"),
              "queue diagnostics open command result",
            );

            const completedRow = payload.completed.rows[0];
            window.showPage("completed");
            window.mediaPipelineCompletedView.renderCompleted(payload.completed);
            if (payload.tableClickRows) {
              click('#completed-history-rows tr[data-row-key]', "completed history table row");
              await waitFor(
                () => text("completed-detail").includes("Row state: broken-output") && text("completed-detail").includes("publish_missing_output") && text("completed-detail").includes("Selected completed-row quick signal:") && text("completed-detail").includes("Combined completed-row review plan:") && text("completed-detail").includes("Investigation view matches:"),
                "completed table row selection",
              );
              setInput("#completed-history-filter", "definitely-no-completed-match", "completed history filter");
              await waitFor(
                () => text("completed-history-filter-summary").includes("Hidden review rows: 1.") && text("completed-history-filter-summary").includes("clear or change this filter before rerun, cleanup, or library decisions"),
                "completed history filter hidden review guardrail",
              );
              setInput("#completed-history-filter", "", "completed history filter");
              setSelect("#completed-history-status-filter", "ready", "completed history status filter");
              await waitFor(
                () => text("completed-history-filter-summary").includes("status=ready/healthy") && text("completed-history-filter-summary").includes("Hidden review rows: 1."),
                "completed history status filter hidden review guardrail",
              );
              setSelect("#completed-history-status-filter", "all", "completed history status filter");
              setSelect("#completed-history-investigation-filter", "route_review", "completed history investigation filter");
              await waitFor(
                () => text("completed-history-filter-summary").includes("view=route review") && text("completed-history-filter-summary").includes("Hidden review rows: 1."),
                "completed history investigation filter hidden review guardrail",
              );
              await waitFor(
                () => text("completed-detail").includes("Selected row visible in table: no") && text("completed-detail").includes("not present in Current Output Status table"),
                "completed selected row absent from current-output detail",
              );
              click("#completed-history-clear-filters-button", "completed history clear filters");
              await waitFor(
                () => text("completed-history-filter-summary").includes("view=all signals") && text("completed-detail").includes("not present in Current Output Status table"),
                "completed history clear filters restores history table",
              );
            } else {
              window.mediaPipelineCompletedView.selectCompletedRow(completedRow);
            }
            click('#completed-diagnostics-actions [data-diagnostics-bridge-target="last_stderr_log"]', "completed diagnostics bridge");
            await waitFor(
              () => visiblePage("diagnostics") && value("diagnostics-tail-target") === "last_stderr_log" && text("diagnostics-tail-detail").includes("Bridge source: Completed selected row"),
              "completed diagnostics bridge handoff",
            );
            window.showPage("completed");
            click('#completed-diagnostics-actions [data-completed-diagnostics-action="tail"][data-completed-diagnostics-target="last_stderr_log"]', "completed stderr tail");
            await waitFor(
              () => text("diagnostics-tail-status").includes("Loaded") && text("diagnostics-tail-text").includes("publish_missing_output"),
              "completed stderr tail read",
            );
            click('#completed-diagnostics-actions [data-completed-diagnostics-action="open"][data-completed-diagnostics-target="completed_manifest"]', "completed manifest open");
            await waitFor(
              () => historyHasTarget("completed_manifest"),
              "completed diagnostics open command result",
            );

            const pendingRow = payload.pending.rows[0];
            window.showPage("pending");
            window.renderPendingPublish(payload.pending, {});
            if (payload.tableClickRows) {
              click('#pending-rows tr[data-row-key]', "pending table row");
              await waitFor(
                () => text("pending-detail").includes("Row state: do-not-drain") && text("pending-detail").includes("unreadable_manifest") && text("pending-detail").includes("Selected pending-row quick signal:") && text("pending-detail").includes("Combined pending-row drain review plan:") && text("pending-detail").includes("Investigation view matches:"),
                "pending table row selection",
              );
              setInput("#pending-filter", "definitely-no-pending-match", "pending filter");
              await waitFor(
                () => text("pending-filter-summary").includes("Hidden review rows: 1.") && text("pending-filter-summary").includes("clear or change this filter before publish/drain decisions"),
                "pending filter hidden review guardrail",
              );
              setInput("#pending-filter", "", "pending filter");
              setSelect("#pending-status-filter", "ready", "pending status filter");
              await waitFor(
                () => text("pending-filter-summary").includes("status=ready/healthy") && text("pending-filter-summary").includes("Hidden review rows: 1."),
                "pending status filter hidden review guardrail",
              );
              setSelect("#pending-status-filter", "all", "pending status filter");
              setSelect("#pending-investigation-filter", "ready_to_drain", "pending investigation filter");
              await waitFor(
                () => text("pending-filter-summary").includes("view=ready to drain") && text("pending-filter-summary").includes("Hidden review rows: 1."),
                "pending investigation filter hidden review guardrail",
              );
              await waitFor(
                () => text("pending-detail").includes("Selected row visible in table: no") && text("pending-detail").includes("Hidden by current filters: investigation view=ready to drain."),
                "pending selected row hidden by investigation filter detail",
              );
              click("#pending-clear-filters-button", "pending clear filters");
              await waitFor(
                () => text("pending-detail").includes("Selected row visible in table: yes") && text("pending-filter-summary").includes("view=all signals"),
                "pending clear filters restores selected row visibility",
              );
            } else {
              window.selectPendingRow(pendingRow);
            }
            click('#pending-diagnostics-actions [data-pending-diagnostics-action="open"][data-pending-diagnostics-target="pending_publish"]', "pending publish open");
            await waitFor(
              () => historyHasTarget("pending_publish"),
              "pending diagnostics open command result",
            );

            window.showPage("diagnostics");
            window.renderDiagnostics(payload.diagnostics || {});
            window.mediaPipelineProgressView.renderDiagnosticsProgress(payload.snapshot || {});
            await waitFor(
              () => text("active-job-detail-status").includes("2 rows")
                && text("active-job-detail-status").includes("review=2")
                && tableText("active-job-detail-rows").includes("launch-active.json")
                && tableText("active-job-detail-rows").includes("broken-active-job.json")
                && text("diagnostics-progress-status").includes("Stale progress review"),
              "Diagnostics ActiveJobs table and stale progress guidance",
            );
            requireText("diagnostics-progress-detail", [
              "Stale progress warning:",
              "Runtime progress looks older than the current backend state",
              "Safe next step: read ActiveJobs and bounded logs",
              "Mutation guardrail: this table is read-only",
            ]);
            clickActiveJobRow("launch-active.json");
            await waitFor(
              () => text("active-job-detail").includes("Record: launch-active.json") && text("active-job-detail").includes("Status: active"),
              "Diagnostics ActiveJobs active row detail",
            );
            requireText("active-job-detail", [
              "Record: launch-active.json",
              "Job: pipeline",
              "Mode: continuous",
              "Status: active",
              "Next evidence stop: while active",
              "Diagnostics action plan:",
              "Mutation guardrail: this trace is read-only",
            ]);
            clickActiveJobRow("broken-active-job.json");
            await waitFor(
              () => text("active-job-detail").includes("Record: broken-active-job.json") && text("active-job-detail").includes("Source: unreadable"),
              "Diagnostics malformed ActiveJobs row detail",
            );
            requireText("active-job-detail", [
              "Record: broken-active-job.json",
              "Source: unreadable",
              "Status: unreadable",
              "Issue: unreadable:",
              "Read Last Stderr",
              "Open ActiveJobs",
              "Guardrail: action targets are backend allowlist identifiers",
            ]);
            window.mediaPipelineDiagnosticsStateSummaryView.renderDiagnosticsStateSummary(payload.stateSummary || {});
            if (payload.settings) window.mediaPipelineSettingsView.renderSettings(payload.settings);
            window.mediaPipelineDiagnosticsView.renderDiagnosticsFirstResponse({
              snapshot: payload.snapshot || {},
              closeReadiness: payload.closeReadiness || {},
              diagnostics: payload.diagnostics || {},
              stateSummary: payload.stateSummary || {},
              commands: payload.commands || {},
              queue: payload.queue || {},
              completed: payload.completed || {},
              pending: payload.pending || {},
              settings: payload.settings || {},
              sampleValidation: payload.sampleValidation || {},
              failures: [],
            });
            await waitFor(
              () => text("diagnostics-state-summary-status").includes("artifact") && text("diagnostics-state-triage-status").includes("read-order row"),
              "diagnostics state artifact summary",
            );
            requireText("diagnostics-first-response-summary", [
              "Diagnostics first-response checklist:",
              "Read order: bounded text first",
              "Mutation guardrail: this checklist cannot launch",
            ]);
            requireText("diagnostics-first-response-rows", [
              "ActiveJobs / progress",
              "State artifacts / read order",
              "External dependency readiness",
              "Sample Validation policy reconciliation",
              "Settings raw-key action plan",
              "Owning page handoff",
              "Logs and malformed-state clues",
            ]);
            click('#diagnostics-first-response-rows tr[data-row-key="sample-policy-reconciliation"]', "diagnostics first-response sample-policy row");
            await waitFor(
              () => text("diagnostics-first-response-detail").includes("First-response step: Sample Validation policy reconciliation") && text("diagnostics-first-response-detail").includes("Completed saved-policy reconciliation"),
              "diagnostics first-response sample policy detail",
            );
            requireText("diagnostics-first-response-detail", [
              "First-response step: Sample Validation policy reconciliation",
              "Saved policy alignment:",
              "Completed saved-policy reconciliation",
              "Read order: Home > Sample Validation Completed Evidence Handoff",
              "Owner pages: Home owns Preview/Append evidence; Completed owns post-run output proof; Settings owns saved policy.",
              "Mutation guardrail: this detail cannot launch",
            ]);
            click('#diagnostics-first-response-rows tr[data-row-key="state-artifacts"]', "diagnostics first-response state-artifacts row");
            await waitFor(
              () => text("diagnostics-first-response-detail").includes("First-response step: State artifacts / read order") && text("diagnostics-first-response-detail").includes("State artifact issue rows:"),
              "diagnostics first-response detail",
            );
            requireText("diagnostics-first-response-detail", [
              "First-response step: State artifacts / read order",
              "Why this gate matters: malformed, stale, or missing state can make ready-looking tables lie.",
              "Backend read-order rows:",
              "Mutation guardrail: this detail cannot launch",
            ]);
            requireText("diagnostics-state-summary", [
              "Read-only backend summary",
              "Operator status:",
              "Next step: select a row for details",
            ]);
            requireText("diagnostics-state-recovery", [
              "State artifact recovery checklist:",
              "Close Readiness is the authority",
              "Mutation guardrail: this checklist does not repair",
            ]);
            requireText("diagnostics-state-triage-summary", [
              "Backend read order:",
              "Read order starts with",
              "Guardrail: the frontend receives target keys only",
            ]);
            clickStateTriageRow("last_stderr_log");
            await waitFor(
              () => text("diagnostics-state-triage-detail").includes("Backend read-order detail:") && text("diagnostics-state-triage-detail").includes("Target: last_stderr_log"),
              "diagnostics state triage detail",
            );
            requireText("diagnostics-state-triage-detail", [
              "Backend read-order detail:",
              "Target: last_stderr_log",
              "Read first:",
              "Open next:",
              "Mutation guardrail: this read-order detail cannot repair",
              "Diagnostics triage JSON:",
              "JSON valid: yes",
            ]);
            click('[data-diagnostics-state-triage-action="tail"][data-diagnostics-state-triage-target="last_stderr_log"]', "state triage stderr tail");
            await waitFor(
              () => text("diagnostics-tail-status").includes("Loaded") && text("diagnostics-tail-text").includes("source_locked") && inlineStatus('[data-diagnostics-state-triage-action="tail"][data-diagnostics-state-triage-target="last_stderr_log"]').includes("Tail loaded"),
              "diagnostics state triage tail read",
            );
            click('[data-diagnostics-state-triage-action="open"][data-diagnostics-state-triage-target="last_stderr_log"]', "state triage stderr open");
            await waitFor(
              () => historyHasTarget("last_stderr_log") && inlineStatus('[data-diagnostics-state-triage-action="open"][data-diagnostics-state-triage-target="last_stderr_log"]').includes("Opened"),
              "diagnostics state triage open command result",
            );
            clickStateSummaryRow("queue_snapshot");
            await waitFor(
              () => text("diagnostics-state-summary-detail").includes("Target: queue_snapshot") && text("diagnostics-state-summary-detail").includes("Queue source/route evidence"),
              "diagnostics state artifact detail",
            );
            requireText("diagnostics-state-summary-detail", [
              "Target: queue_snapshot",
              "Operational interpretation:",
              "Recommended first action:",
              "Recovery stage:",
              "Unsafe if ignored:",
              "Diagnostics action plan:",
              "Guardrail: this view is read-only",
              "Diagnostics artifact JSON:",
              "JSON valid: yes",
            ]);
            window.showPage("diagnostics");
            window.mediaPipelineDiagnosticsView.renderDiagnosticsOwnerHandoff({
              queue: payload.queue,
              completed: payload.completed,
              pending: payload.pending,
              sampleValidation: payload.sampleValidation || {},
              settings: payload.settings || {},
            });
            await waitFor(
              () => text("diagnostics-owner-handoff-status").includes("3 handoff rows") && text("diagnostics-owner-handoff").includes("Queue=1; Completed=1; Pending Publish=1"),
              "diagnostics owner handoff rows",
            );
            requireText("diagnostics-owner-handoff", [
              "Owning-page evidence handoff:",
              "Go To Owner Row is local UI selection",
              "this panel is read-only",
            ]);

            clickOwnerHandoffRow("Queue");
            await waitFor(
              () => text("diagnostics-owner-handoff-detail").includes("Owner page: Queue") && document.querySelector('[data-diagnostics-owner-navigate="queue"]'),
              "queue owner handoff selected",
            );
            click('[data-diagnostics-owner-navigate="queue"]', "queue owner navigate");
            await waitFor(
              () => visiblePage("queue") && text("queue-detail").includes("Row state: blocked") && text("queue-detail").includes("tv_parse_unreliable") && text("diagnostics-owner-handoff-nav-status").includes("No backend command was sent"),
              "queue owner row navigation",
            );

            window.showPage("diagnostics");
            clickOwnerHandoffRow("Completed");
            await waitFor(
              () => text("diagnostics-owner-handoff-detail").includes("Owner page: Completed") && document.querySelector('[data-diagnostics-owner-navigate="completed"]'),
              "completed owner handoff selected",
            );
            requireText("diagnostics-owner-handoff-detail", [
              "Completed final trust handoff:",
              "Final trust step: 2. Output and sidecar on disk",
              "After Go To Owner Row, read Completed > Final Output Trust Walkthrough",
              "Diagnostics points to the owning Completed proof step only",
              "Completed saved-policy reconciliation handoff:",
              "Saved policy alignment:",
              "After Go To Owner Row, read Completed > Selected Pilot Evidence Packet > Saved policy reconciliation",
            ]);
            click('[data-diagnostics-owner-navigate="completed"]', "completed owner navigate");
            await waitFor(
              () => visiblePage("completed") && text("completed-detail").includes("Row state: broken-output") && text("completed-detail").includes("publish_missing_output") && text("diagnostics-owner-handoff-nav-status").includes("No backend command was sent") && text("diagnostics-owner-handoff-nav-status").includes("Selected Completed > Final Output Trust Walkthrough step"),
              "completed owner row navigation",
            );
            requireText("completed-final-trust-detail", [
              "Completed final output trust walkthrough:",
              "Step: 2. Output and sidecar on disk",
              "Open Completed Manifest, output folder, sidecar, Run Logs, and Last Stderr",
            ]);

            window.showPage("diagnostics");
            clickOwnerHandoffRow("Pending Publish");
            await waitFor(
              () => text("diagnostics-owner-handoff-detail").includes("Owner page: Pending Publish") && document.querySelector('[data-diagnostics-owner-navigate="pending"]'),
              "pending owner handoff selected",
            );
            click('[data-diagnostics-owner-navigate="pending"]', "pending owner navigate");
            await waitFor(
              () => visiblePage("pending") && text("pending-detail").includes("Row state: do-not-drain") && text("pending-detail").includes("unreadable_manifest") && text("diagnostics-owner-handoff-nav-status").includes("No backend command was sent") && text("pending-diagnostics-status").includes("Diagnostics handoff selected this row locally"),
              "pending owner row navigation",
            );

            window.showPage("diagnostics");
            window.mediaPipelineContractView.renderContract(payload.contract || {});
            await waitFor(
              () => text("api-contract-safety-summary").includes("Contract safety review:") && text("api-contract-safety-summary").includes("Mutation guardrail: this panel is read-only"),
              "api contract safety review",
            );
            click('#api-contract-safety-rows tr[data-row-key="mutation-boundary"]', "api contract mutation-boundary safety row");
            await waitFor(
              () => text("api-contract-safety-detail").includes("Mutation boundary:") && text("api-contract-safety-detail").includes("Frontend code stages intent and displays results only"),
              "api contract safety detail",
            );
            click("#api-contract-rows tr", "api contract route row");
            await waitFor(
              () => text("api-contract-detail").includes("Route contract JSON:") && text("api-contract-detail").includes("JSON valid: yes") && text("api-contract-detail").includes("Operator safety:"),
              "api contract route JSON detail",
            );

            const history = window.getCommandHistory().filter((entry) => entry.command === "diagnostics.open");
            const historyTargets = history.map((entry) => entry.raw?.request?.target || entry.raw?.data?.target || "").filter(Boolean);
            if (history.length < 3) throw new Error("Expected at least three diagnostics.open command results; got " + history.length);
            if (history.some((entry) => !entry.ok)) throw new Error("Expected diagnostics.open commands to succeed: " + JSON.stringify(history));
            requireText("diagnostics-command-history", [
              "diagnostics.open",
              "Opened queue snapshot file.",
              "Opened completed manifest file.",
              "Opened pending publish folder.",
            ]);
            const resultPayload = {
              ok: true,
              queueStatus: text("queue-diagnostics-status"),
              completedStatus: text("completed-diagnostics-status"),
              pendingStatus: text("pending-diagnostics-status"),
              tailStatus: text("diagnostics-tail-status"),
              tailStatusState: state("diagnostics-tail-status"),
              tailEvidence: text("diagnostics-tail-evidence"),
              stateTriageTailInlineStatus: inlineStatus('[data-diagnostics-state-triage-action="tail"][data-diagnostics-state-triage-target="last_stderr_log"]'),
              stateTriageOpenInlineStatus: inlineStatus('[data-diagnostics-state-triage-action="open"][data-diagnostics-state-triage-target="last_stderr_log"]'),
              historyTargets,
              tableClickRows: Boolean(payload.tableClickRows),
              queueFilterSummary: text("queue-filter-summary"),
              completedFilterSummary: text("completed-filter-summary"),
              pendingFilterSummary: text("pending-filter-summary"),
              queueDetail: text("queue-detail"),
              completedDetail: text("completed-detail"),
              pendingDetail: text("pending-detail"),
              activeJobStatus: text("active-job-detail-status"),
              activeJobDetail: text("active-job-detail"),
              diagnosticsProgressStatus: text("diagnostics-progress-status"),
              diagnosticsProgressDetail: text("diagnostics-progress-detail"),
              ownerHandoffStatus: text("diagnostics-owner-handoff-status"),
              ownerHandoffDetail: text("diagnostics-owner-handoff-detail"),
              ownerHandoffNavStatus: text("diagnostics-owner-handoff-nav-status"),
              pendingDiagnosticsStatus: text("pending-diagnostics-status"),
              stateSummaryStatus: text("diagnostics-state-summary-status"),
              stateSummaryText: text("diagnostics-state-summary"),
              firstResponseSummary: text("diagnostics-first-response-summary"),
              firstResponseDetail: text("diagnostics-first-response-detail"),
              stateRecoveryText: text("diagnostics-state-recovery"),
              stateTriageStatus: text("diagnostics-state-triage-status"),
              stateTriageDetail: text("diagnostics-state-triage-detail"),
              stateArtifactDetail: text("diagnostics-state-summary-detail"),
              contractSafetySummary: text("api-contract-safety-summary"),
              contractSafetyDetail: text("api-contract-safety-detail"),
              commandHistoryCount: history.length,
            };
            resultPayload.hardeningChecks = await runDiagnosticsHardeningChecks();
            return resultPayload;
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
                expression: `Boolean(document.getElementById("queue-detail") && document.getElementById("diagnostics-first-response-detail") && typeof window.renderQueue === "function" && typeof window.externalDependencyRows === "function" && typeof window.requestDiagnosticsTail === "function" && typeof window.requestDiagnosticsOpen === "function" && typeof window.mediaPipelineDiagnosticsView.renderDiagnosticsFirstResponse === "function" && typeof window.mediaPipelineDiagnosticsView.diagnosticsFirstResponseDetailLines === "function")`,
                returnByValue: true,
              });
              if (ready.result?.value === true) break;
              await sleep(150);
            }
            const ready = await client.send("Runtime.evaluate", {
              expression: `Boolean(document.getElementById("queue-detail") && document.getElementById("diagnostics-first-response-detail") && typeof window.renderQueue === "function" && typeof window.externalDependencyRows === "function" && typeof window.requestDiagnosticsTail === "function" && typeof window.requestDiagnosticsOpen === "function" && typeof window.mediaPipelineDiagnosticsView.renderDiagnosticsFirstResponse === "function" && typeof window.mediaPipelineDiagnosticsView.diagnosticsFirstResponseDetailLines === "function")`,
              returnByValue: true,
            });
            if (ready.result?.value !== true) {
              throw new Error("WebView diagnostics handoff globals or DOM nodes did not become ready.");
            }
            const result = await client.send("Runtime.evaluate", {
              expression: diagnosticsHandoffScript(payload.data),
              awaitPromise: true,
              returnByValue: true,
            });
            if (result.exceptionDetails) {
              const details = result.exceptionDetails;
              const exception = details.exception || {};
              throw new Error(exception.description || exception.value || details.text || "browser evaluation failed");
            }
            const resultValue = result.result?.value || {};
            const responsiveChecks = [];
            for (const width of [375, 768, 1440]) {
              await client.send("Emulation.setDeviceMetricsOverride", {
                width,
                height: 1000,
                deviceScaleFactor: 1,
                mobile: width <= 375,
              });
              await sleep(150);
              const responsive = await client.send("Runtime.evaluate", {
                expression: `
                  (function () {
                    if (typeof window.showPage === "function") window.showPage("diagnostics");
                    const tabs = ["triage", "readiness", "investigation", "logs", "progress", "advanced"];
                    const panels = [];
                    for (const tab of tabs) {
                      const button = document.querySelector('button.settings-tab-btn[data-diag-tab="' + tab + '"]');
                      if (button) button.click();
                      const panel = document.querySelector('div.settings-tab-pane[data-diag-tab="' + tab + '"]') || document;
                      const badWraps = Array.from(panel.querySelectorAll(".table-wrap, .detail-table-wrap")).filter((node) => {
                        const style = window.getComputedStyle(node);
                        return node.scrollWidth > node.clientWidth + 4 && style.overflowX === "visible";
                      }).map((node) => node.id || node.className || node.tagName).slice(0, 6);
                      const badActionButtons = Array.from(panel.querySelectorAll(".action-row button, .diagnostics-open-target-group button")).filter((node) => {
                        if (node.closest(".table-wrap, .detail-table-wrap")) return false;
                        const rect = node.getBoundingClientRect();
                        return rect.width > 0 && (rect.left < -4 || rect.right > window.innerWidth + 4);
                      }).map((node) => (node.textContent || node.id || "").trim()).filter(Boolean).slice(0, 6);
                      panels.push({ tab, badWraps, badActionButtons });
                    }
                    return { width: window.innerWidth, panels };
                  })()
                `,
                returnByValue: true,
              });
              if (responsive.exceptionDetails) {
                const detail = responsive.exceptionDetails.exception?.description
                  || responsive.exceptionDetails.exception?.value
                  || responsive.exceptionDetails.text
                  || "responsive evaluation failed";
                throw new Error(detail);
              }
              const value = responsive.result?.value || {};
              const failures = (value.panels || []).filter((panel) => (panel.badWraps || []).length || (panel.badActionButtons || []).length);
              if (failures.length) {
                throw new Error(`Diagnostics responsive assertion failed at ${width}px: ${JSON.stringify(failures)}`);
              }
              responsiveChecks.push(value);
            }
            resultValue.responsiveChecks = responsiveChecks;
            await sleep(750);
            const errorEvents = client.consoleEvents.filter((entry) => entry.startsWith("error:") || entry.startsWith("warning:"));
            if (client.exceptions.length || errorEvents.length) {
              throw new Error(`Browser console/exception noise: ${client.exceptions.concat(errorEvents).join("; ")}`);
            }
            console.log(JSON.stringify({ ok: true, result: resultValue }));
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


def _run_browser_diagnostics_handoff_smoke(
    *,
    browser_path: str,
    url: str,
    queue: dict[str, object],
    completed: dict[str, object],
    pending: dict[str, object],
    diagnostics: dict[str, object],
    snapshot: dict[str, object],
    state_summary: dict[str, object],
    contract: dict[str, object],
    settings: dict[str, object] | None = None,
    sample_validation: dict[str, object] | None = None,
    table_click_rows: bool = False,
) -> dict[str, object]:
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("Node.js is required for the browser-backed diagnostics handoff smoke.")
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as raw_tmp:
        tmp = Path(raw_tmp)
        port = _free_port()
        payload_path = tmp / "browser-diagnostics-handoff-payload.json"
        runner_path = tmp / "browser-diagnostics-handoff-runner.cjs"
        payload_path.write_text(
            json.dumps(
                {
                    "browserPath": browser_path,
                    "port": port,
                    "tmpRoot": str(tmp),
                    "url": url,
                    "data": {
                        "queue": queue,
                        "completed": completed,
                        "pending": pending,
                        "diagnostics": diagnostics,
                        "snapshot": snapshot,
                        "stateSummary": state_summary,
                        "contract": contract,
                        "settings": settings or {},
                        "sampleValidation": sample_validation or {},
                        "tableClickRows": table_click_rows,
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        runner_path.write_text(_browser_diagnostics_handoff_runner_source(), encoding="utf-8")
        return run_node_browser_smoke(
            "Browser-backed WebView diagnostics handoff smoke",
            node=node,
            runner_path=runner_path,
            payload_path=payload_path,
            timeout_seconds=60,
        )


def _install_runtime_diagnostics_fixture(root: Path, resolved: object, service: DummyWorkflowFacadeService) -> None:
    active_jobs = getattr(resolved, "active_jobs_path", None) or (root / "State" / "ActiveJobs")
    active_jobs.mkdir(parents=True, exist_ok=True)
    (active_jobs / "launch-active.json").write_text(
        json.dumps(
            {
                "schema_version": "desktop_active_job.v1",
                "launch_id": "launch-active",
                "job_kind": "pipeline",
                "mode": "continuous",
                "status": "active",
                "pid": None,
                "app_pid": None,
                "command_line": "pwsh -File Pipeline.ps1",
                "args": ["pwsh", "-File", "Pipeline.ps1"],
                "cwd": str(root),
                "stdout_log": str(root / "RunLogs" / "run.stdout.log"),
                "stderr_log": str(root / "RunLogs" / "run.stderr.log"),
                "show_console": False,
                "metadata": {"source": "browser-diagnostics-handoff-smoke"},
                "launched_at": "2026-05-15T02:00:00Z",
                "last_update": "2026-05-15T02:04:00Z",
                "completed_at": "",
                "return_code": None,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    (active_jobs / "broken-active-job.json").write_text("{not json", encoding="utf-8")
    progress = {
        "ProgressVersion": 2,
        "Status": "Processing",
        "CurrentStage": "Encoding",
        "CurrentStagePercent": 88.0,
        "CurrentFileDisplay": "Stale Runtime Fixture.mkv",
        "CurrentRoute": "encode",
        "RouteReason": "stale-progress diagnostics fixture",
        "CurrentQueueIndex": 3,
        "CurrentQueueTotal": 9,
        "PauseRequested": False,
        "StopRequested": False,
        "UpdatedAt": "2026-05-15T01:00:00Z",
    }
    service.snapshot = Snapshot(
        resolved=resolved,
        current_activity="Stale progress from previous run; latest event: Encoding Stale Runtime Fixture.mkv.",
        status_summary="Status OK with stale progress fixture.",
        log_tail="source_locked\npublish_missing_output\n",
        progress=progress,
        audit_progress=None,
        latest_failure_report=getattr(resolved, "workspace_root", root) / "failures.txt",
        latest_failure_json=getattr(resolved, "workspace_root", root) / "failures.json",
        latest_audit_csv=None,
        latest_priority_csv=None,
        pipeline_events=[
            {
                "schema_version": "pipeline_event.v1",
                "event_id": "evt-stale-progress",
                "event_type": "job_progress",
                "timestamp": "2026-05-15T01:00:00Z",
                "created_at": "2026-05-15T01:00:00Z",
                "data": {"display_name": "Stale Runtime Fixture.mkv", "percent": 88.0},
            }
        ],
    )
    service._format_active_job_summary = lambda _resolved: [  # type: ignore[method-assign]
        "pipeline continuous: active (pid unknown) launched 2026-05-15T02:00:00Z",
        "broken-active-job.json: unreadable (malformed JSON)",
    ]


def _assert_diagnostics_hardening_checks(testcase: unittest.TestCase, browser_result: dict[str, object]) -> None:
    checks = browser_result["hardeningChecks"]
    assert isinstance(checks, dict)
    grouped = checks["groupedAccess"]
    command = checks["commandEvidence"]
    duplicates = checks["duplicateSuppression"]
    stale = checks["staleRefresh"]
    tdarr = checks["tdarr"]
    assert isinstance(grouped, dict)
    assert isinstance(command, dict)
    assert isinstance(duplicates, dict)
    assert isinstance(stale, dict)
    assert isinstance(tdarr, dict)

    testcase.assertTrue(grouped["groupsPresent"])
    testcase.assertTrue(grouped["readBeforeOpen"])
    testcase.assertTrue(command["commandDetailBeforeRaw"])
    testcase.assertTrue(command["contractRoutePresenceBoundary"])
    testcase.assertIn("already in progress", duplicates["tail"])
    testcase.assertIn("already in progress", duplicates["open"])
    testcase.assertEqual(stale["diagnostics"]["state"], "warning")
    testcase.assertEqual(stale["state"]["state"], "warning")
    testcase.assertEqual(stale["commands"]["state"], "warning")
    testcase.assertEqual(stale["contract"]["state"], "warning")

    log_states = checks["logStates"]
    tail_states = checks["tailStates"]
    assert isinstance(log_states, list)
    assert isinstance(tail_states, list)
    testcase.assertEqual([item["label"] for item in log_states], ["loaded", "empty", "missing", "unavailable", "truncated", "read-error"])
    testcase.assertEqual([item["label"] for item in tail_states], ["loaded", "empty", "missing", "unavailable", "truncated", "read-error"])
    testcase.assertEqual(log_states[-1]["pipeline"]["state"], "blocked")
    testcase.assertEqual(tail_states[-1]["fileLog"]["state"], "blocked")

    testcase.assertTrue(tdarr["initial"]["proof"]["disabled"])
    testcase.assertTrue(tdarr["initial"]["cleanupArchive"]["disabled"])
    testcase.assertTrue(tdarr["initial"]["delete"]["disabled"])
    testcase.assertEqual(tdarr["initial"]["strict"]["severity"], "warning")
    testcase.assertFalse(tdarr["afterLatest"]["proof"]["disabled"])
    testcase.assertFalse(tdarr["afterLatest"]["strict"]["disabled"])
    testcase.assertFalse(tdarr["afterLatest"]["cleanupPlan"]["disabled"])
    testcase.assertTrue(tdarr["afterLatest"]["cleanupArchive"]["disabled"])
    testcase.assertFalse(tdarr["afterCleanupPlan"]["cleanupArchive"]["disabled"])
    testcase.assertTrue(tdarr["afterArchive"]["deleteBeforeText"]["disabled"])
    testcase.assertTrue(tdarr["afterWrongText"]["delete"]["disabled"])
    testcase.assertFalse(tdarr["afterTypedText"]["delete"]["disabled"])
    testcase.assertIn("cancelled before any backend request", tdarr["cancelledDelete"])
    testcase.assertIn("Backend rejected fixture delete.", tdarr["backendRejectedDelete"]["detail"])
    testcase.assertIn("cleanup-delete", tdarr["backendRejectedDelete"]["posts"])

    responsive = browser_result["responsiveChecks"]
    assert isinstance(responsive, list)
    testcase.assertEqual(len(responsive), 3)
    testcase.assertEqual(len(responsive[0]["panels"]), 6)


class WebViewBrowserDiagnosticsHandoffSmoke(unittest.TestCase):
    def test_real_browser_clicks_read_only_diagnostics_handoffs_for_backend_risk_rows(self) -> None:
        browser_path = _find_browser()
        if not browser_path:
            raise unittest.SkipTest("Chrome or Edge is required for the browser-backed diagnostics handoff smoke.")

        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved, events = _write_high_risk_fixture_state(root)
            media_snapshot = capture_media_no_mutation_snapshot(root)
            service = DummyWorkflowFacadeService(root)
            service.read_pipeline_events_tail = lambda _resolved, line_count=300: events  # type: ignore[method-assign]
            service._last_spawn_stderr_log = root / "RunLogs" / "run.stderr.log"  # noqa: SLF001 - fixture wiring.
            _install_runtime_diagnostics_fixture(root, resolved, service)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            server = LocalApiServer(
                facade,
                token="browser-diagnostics-token",
                resolved_provider=lambda: resolved,
                audit_root_provider=lambda: str(root),
            )
            try:
                server.start()
                queue_status, queue = _get_json(f"{server.url}/api/queue", token="browser-diagnostics-token")
                completed_status, completed = _get_json(f"{server.url}/api/completed", token="browser-diagnostics-token")
                pending_status, pending = _get_json(f"{server.url}/api/pending-publish", token="browser-diagnostics-token")
                diagnostics_status, diagnostics = _get_json(f"{server.url}/api/diagnostics", token="browser-diagnostics-token")
                snapshot_status, snapshot = _get_json(f"{server.url}/api/snapshot", token="browser-diagnostics-token")
                state_status, state_summary = _get_json(f"{server.url}/api/diagnostics/state-summary", token="browser-diagnostics-token")
                contract_status, contract = _get_json(f"{server.url}/api/contract", token="browser-diagnostics-token")
                settings_status, settings = _get_json(f"{server.url}/api/settings/workspace", token="browser-diagnostics-token")
                sample_validation_status, sample_validation = _get_json(f"{server.url}/api/sample-validation?limit=10", token="browser-diagnostics-token")
                self.assertEqual(queue_status, 200)
                self.assertEqual(completed_status, 200)
                self.assertEqual(pending_status, 200)
                self.assertEqual(diagnostics_status, 200)
                self.assertEqual(snapshot_status, 200)
                self.assertEqual(state_status, 200)
                self.assertEqual(contract_status, 200)
                self.assertEqual(settings_status, 200)
                self.assertEqual(sample_validation_status, 200)
                self.assertEqual(queue["rows"][0]["operator_trust_state"], "blocked")
                self.assertEqual(completed["rows"][0]["operator_trust_state"], "broken-output")
                self.assertEqual(pending["rows"][0]["operator_trust_state"], "do-not-drain")
                result = _run_browser_diagnostics_handoff_smoke(
                    browser_path=browser_path,
                    url=f"{server.url}/",
                    queue=queue,
                    completed=completed,
                    pending=pending,
                    diagnostics=diagnostics,
                    snapshot=snapshot,
                    state_summary=state_summary,
                    contract=contract,
                    settings=settings,
                    sample_validation=sample_validation,
                )
            finally:
                server.stop()
            assert_media_no_mutation(self, media_snapshot)

        self.assertTrue(result["ok"])
        browser_result = result["result"]
        self.assertIn("Loaded", browser_result["tailStatus"])
        self.assertEqual(browser_result["tailStatusState"], "ready")
        self.assertIn("Tail loaded", browser_result["stateTriageTailInlineStatus"])
        self.assertIn("Opened", browser_result["stateTriageOpenInlineStatus"])
        self.assertIn("Tail posture (backend): blocked", browser_result["tailEvidence"])
        self.assertIn("Evidence authority: backend", browser_result["tailEvidence"])
        self.assertIn("Diagnostics tail evidence is read-only", browser_result["tailEvidence"])
        self.assertIn("queue_snapshot", browser_result["historyTargets"])
        self.assertIn("completed_manifest", browser_result["historyTargets"])
        self.assertIn("pending_publish", browser_result["historyTargets"])
        self.assertIn("last_stderr_log", browser_result["historyTargets"])
        self.assertGreaterEqual(browser_result["commandHistoryCount"], 3)
        self.assertIn("review=2", browser_result["activeJobStatus"])
        self.assertIn("Record: broken-active-job.json", browser_result["activeJobDetail"])
        self.assertIn("Stale progress warning:", browser_result["diagnosticsProgressDetail"])
        self.assertIn("artifact", browser_result["stateSummaryStatus"])
        self.assertIn("Read-only backend summary", browser_result["stateSummaryText"])
        self.assertIn("State artifact recovery checklist:", browser_result["stateRecoveryText"])
        self.assertIn("read-order row", browser_result["stateTriageStatus"])
        self.assertIn("Target: last_stderr_log", browser_result["stateTriageDetail"])
        self.assertIn("Mutation guardrail", browser_result["stateTriageDetail"])
        self.assertIn("Target: queue_snapshot", browser_result["stateArtifactDetail"])
        self.assertIn("Queue source/route evidence", browser_result["stateArtifactDetail"])
        self.assertIn("3 handoff rows", browser_result["ownerHandoffStatus"])
        self.assertIn("Owner page: Pending Publish", browser_result["ownerHandoffDetail"])
        self.assertIn("Opened Pending Publish", browser_result["ownerHandoffNavStatus"])
        self.assertIn("No backend command was sent", browser_result["ownerHandoffNavStatus"])
        self.assertIn("Diagnostics handoff selected this row locally", browser_result["pendingDiagnosticsStatus"])
        self.assertIn("Contract safety review:", browser_result["contractSafetySummary"])
        self.assertIn("Mutation guardrail: this panel is read-only", browser_result["contractSafetySummary"])
        self.assertIn("Mutation boundary:", browser_result["contractSafetyDetail"])
        self.assertIn("Frontend code stages intent and displays results only", browser_result["contractSafetyDetail"])
        _assert_diagnostics_hardening_checks(self, browser_result)

    def test_real_browser_clicks_table_rows_before_read_only_diagnostics_handoffs(self) -> None:
        browser_path = _find_browser()
        if not browser_path:
            raise unittest.SkipTest("Chrome or Edge is required for the browser-backed diagnostics handoff smoke.")

        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved, events = _write_high_risk_fixture_state(root)
            media_snapshot = capture_media_no_mutation_snapshot(root)
            service = DummyWorkflowFacadeService(root)
            service.read_pipeline_events_tail = lambda _resolved, line_count=300: events  # type: ignore[method-assign]
            service._last_spawn_stderr_log = root / "RunLogs" / "run.stderr.log"  # noqa: SLF001 - fixture wiring.
            _install_runtime_diagnostics_fixture(root, resolved, service)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            server = LocalApiServer(
                facade,
                token="browser-table-diagnostics-token",
                resolved_provider=lambda: resolved,
                audit_root_provider=lambda: str(root),
            )
            try:
                server.start()
                queue_status, queue = _get_json(f"{server.url}/api/queue", token="browser-table-diagnostics-token")
                completed_status, completed = _get_json(f"{server.url}/api/completed", token="browser-table-diagnostics-token")
                pending_status, pending = _get_json(f"{server.url}/api/pending-publish", token="browser-table-diagnostics-token")
                diagnostics_status, diagnostics = _get_json(f"{server.url}/api/diagnostics", token="browser-table-diagnostics-token")
                snapshot_status, snapshot = _get_json(f"{server.url}/api/snapshot", token="browser-table-diagnostics-token")
                state_status, state_summary = _get_json(f"{server.url}/api/diagnostics/state-summary", token="browser-table-diagnostics-token")
                contract_status, contract = _get_json(f"{server.url}/api/contract", token="browser-table-diagnostics-token")
                settings_status, settings = _get_json(f"{server.url}/api/settings/workspace", token="browser-table-diagnostics-token")
                sample_validation_status, sample_validation = _get_json(f"{server.url}/api/sample-validation?limit=10", token="browser-table-diagnostics-token")
                self.assertEqual(queue_status, 200)
                self.assertEqual(completed_status, 200)
                self.assertEqual(pending_status, 200)
                self.assertEqual(diagnostics_status, 200)
                self.assertEqual(snapshot_status, 200)
                self.assertEqual(state_status, 200)
                self.assertEqual(contract_status, 200)
                self.assertEqual(settings_status, 200)
                self.assertEqual(sample_validation_status, 200)
                result = _run_browser_diagnostics_handoff_smoke(
                    browser_path=browser_path,
                    url=f"{server.url}/",
                    queue=queue,
                    completed=completed,
                    pending=pending,
                    diagnostics=diagnostics,
                    snapshot=snapshot,
                    state_summary=state_summary,
                    contract=contract,
                    settings=settings,
                    sample_validation=sample_validation,
                    table_click_rows=True,
                )
            finally:
                server.stop()
            assert_media_no_mutation(self, media_snapshot)

        self.assertTrue(result["ok"])
        browser_result = result["result"]
        self.assertTrue(browser_result["tableClickRows"])
        self.assertIn("Tail posture (backend): blocked", browser_result["tailEvidence"])
        self.assertEqual(browser_result["tailStatusState"], "ready")
        self.assertIn("Tail loaded", browser_result["stateTriageTailInlineStatus"])
        self.assertIn("Opened", browser_result["stateTriageOpenInlineStatus"])
        self.assertIn("Evidence authority: backend", browser_result["tailEvidence"])
        self.assertIn("Row state: blocked", browser_result["queueDetail"])
        self.assertIn("tv_parse_unreliable", browser_result["queueDetail"])
        self.assertIn("Combined row review plan:", browser_result["queueDetail"])
        self.assertIn("Read first: Queue Snapshot", browser_result["queueDetail"])
        self.assertIn("Row state: broken-output", browser_result["completedDetail"])
        self.assertIn("publish_missing_output", browser_result["completedDetail"])
        self.assertIn("Combined completed-row review plan:", browser_result["completedDetail"])
        self.assertIn("Read first: Completed Manifest", browser_result["completedDetail"])
        self.assertIn("Row state: do-not-drain", browser_result["pendingDetail"])
        self.assertIn("unreadable_manifest", browser_result["pendingDetail"])
        self.assertIn("Combined pending-row drain review plan:", browser_result["pendingDetail"])
        self.assertIn("Read first: Pending manifest", browser_result["pendingDetail"])
        self.assertIn("queue_snapshot", browser_result["historyTargets"])
        self.assertIn("completed_manifest", browser_result["historyTargets"])
        self.assertIn("pending_publish", browser_result["historyTargets"])
        self.assertIn("last_stderr_log", browser_result["historyTargets"])
        self.assertGreaterEqual(browser_result["commandHistoryCount"], 3)
        self.assertIn("review=2", browser_result["activeJobStatus"])
        self.assertIn("Record: broken-active-job.json", browser_result["activeJobDetail"])
        self.assertIn("Stale progress warning:", browser_result["diagnosticsProgressDetail"])
        self.assertIn("State artifact recovery checklist:", browser_result["stateRecoveryText"])
        self.assertIn("Target: last_stderr_log", browser_result["stateTriageDetail"])
        self.assertIn("Target: queue_snapshot", browser_result["stateArtifactDetail"])
        self.assertIn("3 handoff rows", browser_result["ownerHandoffStatus"])
        self.assertIn("Owner page: Pending Publish", browser_result["ownerHandoffDetail"])
        self.assertIn("Opened Pending Publish", browser_result["ownerHandoffNavStatus"])
        self.assertIn("No backend command was sent", browser_result["ownerHandoffNavStatus"])
        self.assertIn("Diagnostics handoff selected this row locally", browser_result["pendingDiagnosticsStatus"])
        self.assertIn("Contract safety review:", browser_result["contractSafetySummary"])
        self.assertIn("Mutation boundary:", browser_result["contractSafetyDetail"])
        _assert_diagnostics_hardening_checks(self, browser_result)


if __name__ == "__main__":
    unittest.main()
