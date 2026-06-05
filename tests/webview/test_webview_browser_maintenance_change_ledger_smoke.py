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


def _change_ledger_payload(root: Path) -> dict[str, object]:
    return {
        "schema_version": "desktop_change_ledger.v1",
        "read_only": True,
        "counts": {
            "total": 2,
            "unreleased": 1,
            "released": 1,
            "planned": 0,
            "in_progress": 1,
            "complete": 1,
            "high_or_critical_risk": 1,
        },
        "python_impact": {
            "file_count": 3,
            "summary": "3 Python file(s) across 3 group(s).",
            "groups": [
                {
                    "group": "core_maintenance",
                    "summary": "core_maintenance: 1 Python file(s)",
                    "files": ["src/mediapipeline/core/maintenance/change_ledger.py"],
                },
                {
                    "group": "desktop_api",
                    "summary": "desktop_api: 1 Python file(s)",
                    "files": ["src/mediapipeline/desktop/api/read_payloads_workspace.py"],
                },
                {"group": "tests", "summary": "tests: 1 Python file(s)", "files": ["tests/python/desktop/test_fixture.py"]},
            ],
        },
        "coverage": {
            "scope": "worktree",
            "available": True,
            "changed_count": 0,
            "covered_count": 0,
            "uncovered_count": 0,
            "changed_paths": [],
            "covered_paths": [],
            "uncovered_paths": [],
            "packet_paths_considered": ["ops/release/changes/unreleased/MP-CHANGE-SMOKE-001.json"],
            "errors": [],
        },
        "summary_lines": [
            "Change ledger: 2 packet(s)",
            "Unreleased: 1; released: 1",
            "Open: 1; complete: 1",
            "High/critical risk: 1",
        ],
        "source_paths": [
            {"path": "CHANGELOG.md", "exists": True, "stale": False},
            {"path": "docs/change_control/CHANGELOG.md", "exists": True, "stale": False},
            {"path": "docs/change_control/CHANGE_INDEX.md", "exists": True, "stale": False},
            {"path": "ops/release/changes/unreleased", "exists": True, "stale": False},
            {"path": "ops/release/changes/released", "exists": True, "stale": False},
        ],
        "hygiene": {
            "schema_version": "desktop_change_ledger_hygiene.v1",
            "read_only": True,
            "operator_status": "ready",
            "issue_count": 0,
            "issues": [],
            "unlogged_change_count": 0,
            "unlogged_changes": [],
            "summary_lines": [
                "Unrecorded changed files: 0",
                "Change ledger hygiene: ready",
                "Loaded packets: 2",
                "Issues: 0",
                "Coverage scope: worktree",
                "Mutation guardrail: this ledger is read-only.",
            ],
        },
        "rows": [
            {
                "id": "MP-CHANGE-SMOKE-001",
                "title": "Add Maintenance Change Ledger",
                "version_target": "0.1.0-dev",
                "status": "complete",
                "type": "feature",
                "risk_level": "medium",
                "location": "unreleased",
                "release_version": "",
                "validation_status": "complete",
                "source_path": "ops/release/changes/unreleased/MP-CHANGE-SMOKE-001.json",
                "summary": "Read-only ledger panels display project change history.",
                "reason": "Operators need a definitive Maintenance view for issue and feature execution evidence.",
                "affected_areas": ["maintenance", "local_api", "webview"],
                "files_touched": [
                    "src/mediapipeline/core/maintenance/change_ledger.py",
                    "src/mediapipeline/desktop/api/read_payloads_workspace.py",
                ],
                "python_impact": {
                    "file_count": 2,
                    "summary": "2 Python file(s) across 2 group(s).",
                    "groups": [
                        {
                            "group": "core_maintenance",
                            "summary": "core_maintenance: 1 Python file(s)",
                            "files": ["src/mediapipeline/core/maintenance/change_ledger.py"],
                        },
                        {
                            "group": "desktop_api",
                            "summary": "desktop_api: 1 Python file(s)",
                            "files": ["src/mediapipeline/desktop/api/read_payloads_workspace.py"],
                        },
                    ],
                },
                "behavior_before": "Maintenance did not show structured change history.",
                "behavior_after": "Maintenance renders change packets and changelog hygiene read-only.",
                "manual_validation": ["Browser ledger smoke fixture passed."],
                "rollback_plan": "Revert the ledger route, UI panels, and tests.",
                "related_changes": [],
                "notes": f"Fixture root: {root}",
            },
            {
                "id": "MP-CHANGE-SMOKE-002",
                "title": "Plan Queue Strategy Audit",
                "version_target": "0.1.0-dev",
                "status": "in_progress",
                "type": "issue",
                "risk_level": "high",
                "location": "released",
                "release_version": "0.0.9",
                "validation_status": "incomplete",
                "source_path": "ops/release/changes/released/0.0.9/MP-CHANGE-SMOKE-002.json",
                "summary": "Fixture row proving status, risk, and search filters.",
                "reason": "Browser smoke needs a second row for filtering.",
                "affected_areas": ["queue", "tests"],
                "files_touched": ["tests/python/desktop/test_fixture.py"],
                "python_impact": {
                    "file_count": 1,
                    "summary": "1 Python file(s) across 1 group(s).",
                    "groups": [
                        {"group": "tests", "summary": "tests: 1 Python file(s)", "files": ["tests/python/desktop/test_fixture.py"]}
                    ],
                },
                "behavior_before": "No second fixture row.",
                "behavior_after": "Filters can hide and reveal rows.",
                "manual_validation": [],
                "rollback_plan": "Remove the fixture row.",
                "related_changes": [],
                "notes": "High-risk fixture row only.",
            },
        ],
        "warnings": [],
    }


def _browser_change_ledger_runner_source() -> str:
    return browser_cdp_runner_prelude() + textwrap.dedent(
        r"""
        function changeLedgerScript(data) {
          return `
          (async () => {
            const payload = ${JSON.stringify(data)};
            const posts = [];
            const gets = [];
            function byId(id) { return document.getElementById(id); }
            function text(id) { const node = byId(id); return node ? node.textContent || "" : ""; }
            function visiblePage(page) {
              return Boolean(document.querySelector('[data-page-panel="' + page + '"]')?.classList.contains("is-visible"));
            }
            function requireText(id, fragments) {
              const actual = text(id);
              for (const fragment of fragments) {
                if (!actual.includes(fragment)) throw new Error(id + " missing " + fragment + "\\nActual:\\n" + actual);
              }
            }
            function setValue(id, value) {
              const node = byId(id);
              if (!node) throw new Error("missing control " + id);
              node.value = value;
              node.dispatchEvent(new Event("input", { bubbles: true }));
              node.dispatchEvent(new Event("change", { bubbles: true }));
            }
            async function waitFor(predicate, label) {
              let lastError = null;
              const deadline = Date.now() + 5000;
              while (Date.now() < deadline) {
                try {
                  if (predicate()) return;
                } catch (error) {
                  lastError = error;
                }
                await new Promise((resolve) => setTimeout(resolve, 100));
              }
              throw new Error("Timed out waiting for " + label + (lastError ? ": " + lastError.message : ""));
            }
            function rowCount() {
              return Array.from(document.querySelectorAll('#maintenance-change-ledger-rows tr[data-selectable-row="true"]')).length;
            }
            function clickRowContaining(fragment) {
              const rows = Array.from(document.querySelectorAll('#maintenance-change-ledger-rows tr[data-selectable-row="true"]'));
              const row = rows.find((candidate) => (candidate.textContent || "").includes(fragment));
              if (!row) throw new Error("missing ledger row containing " + fragment);
              row.click();
            }
            window.apiGet = async (url) => {
              gets.push(String(url || ""));
              if (String(url || "") === "/api/maintenance/change-ledger") return payload;
              return {};
            };
            window.apiPost = async (url, body) => {
              posts.push({ url: String(url || ""), body });
              throw new Error("unexpected mutation POST " + url);
            };

            if (typeof window.showPage !== "function") throw new Error("missing showPage");
            if (typeof window.mediaPipelineMaintenanceView?.refreshChangeLedger !== "function") throw new Error("missing refreshChangeLedger");
            if (typeof window.mediaPipelineMaintenanceView?.renderChangeLedgerRows !== "function") throw new Error("missing renderChangeLedgerRows");

            window.showPage("maintenance");
            if (!visiblePage("maintenance")) throw new Error("Maintenance page did not become visible.");
            await waitFor(() => text("maintenance-change-ledger-status") !== "Loading...", "initial ledger refresh to settle");
            await window.mediaPipelineMaintenanceView.refreshChangeLedger();
            await waitFor(() => text("maintenance-change-ledger-status").includes("ready (2)"), "fixture ledger refresh");
            requireText("maintenance-change-ledger-status", ["ready (2)"]);
            requireText("maintenance-change-ledger-summary", ["Change ledger: 2 packet(s)", "Affected Python scripts:", "read-only"]);
            requireText("maintenance-change-ledger-hygiene", ["Unrecorded changed files: 0", "Change ledger hygiene: ready", "No changelog hygiene issues reported.", "never writes packets"]);
            requireText("maintenance-change-ledger-detail", ["Add Maintenance Change Ledger", "Affected Python scripts:", "src/mediapipeline/core/maintenance/change_ledger.py"]);
            if (rowCount() !== 2) throw new Error("expected 2 ledger rows, saw " + rowCount());

            clickRowContaining("Plan Queue Strategy Audit");
            requireText("maintenance-change-ledger-detail", ["Plan Queue Strategy Audit", "Risk: high", "Validation status: incomplete"]);

            setValue("maintenance-change-ledger-status-filter", "complete");
            window.mediaPipelineMaintenanceView.renderChangeLedgerRows();
            requireText("maintenance-change-ledger-table-status", ["1/2 shown"]);
            if (rowCount() !== 1) throw new Error("status filter expected 1 row, saw " + rowCount());

            setValue("maintenance-change-ledger-status-filter", "");
            setValue("maintenance-change-ledger-search", "src/mediapipeline/core/maintenance/change_ledger.py");
            window.mediaPipelineMaintenanceView.renderChangeLedgerRows();
            requireText("maintenance-change-ledger-table-status", ["1/2 shown"]);
            requireText("maintenance-change-ledger-rows", ["MP-CHANGE-SMOKE-001"]);

            setValue("maintenance-change-ledger-search", "no-match-filter");
            window.mediaPipelineMaintenanceView.renderChangeLedgerRows();
            requireText("maintenance-change-ledger-table-status", ["0/2 shown"]);
            requireText("maintenance-change-ledger-rows", ["No change packets match"]);

            setValue("maintenance-change-ledger-search", "");
            window.mediaPipelineMaintenanceView.renderChangeLedgerRows();
            if (rowCount() !== 2) throw new Error("cleared filters expected 2 rows, saw " + rowCount());

            const forbiddenPosts = posts.filter((entry) =>
              ["/api/media", "/api/queue", "/api/settings", "/api/pending-publish", "/api/rename"].some((prefix) => entry.url.startsWith(prefix))
            );
            if (forbiddenPosts.length) throw new Error("ledger smoke posted mutation routes: " + JSON.stringify(forbiddenPosts));
            return {
              ok: true,
              gets,
              posts,
              status: text("maintenance-change-ledger-status"),
              tableStatus: text("maintenance-change-ledger-table-status"),
              detail: text("maintenance-change-ledger-detail"),
              hygiene: text("maintenance-change-ledger-hygiene"),
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
            const readyExpression = `Boolean(document.getElementById("maintenance-change-ledger-summary") && document.getElementById("maintenance-change-ledger-rows") && typeof window.mediaPipelineMaintenanceView?.renderChangeLedger === "function" && typeof window.mediaPipelineMaintenanceView?.refreshChangeLedger === "function" && typeof window.showPage === "function")`;
            const deadline = Date.now() + 20000;
            while (Date.now() < deadline) {
              const ready = await client.send("Runtime.evaluate", { expression: readyExpression, returnByValue: true });
              if (ready.result?.value === true) break;
              await sleep(150);
            }
            const ready = await client.send("Runtime.evaluate", { expression: readyExpression, returnByValue: true });
            if (ready.result?.value !== true) throw new Error("Maintenance change ledger WebView globals or DOM nodes did not become ready.");
            const result = await client.send("Runtime.evaluate", {
              expression: changeLedgerScript(payload.changeLedgerPayload),
              awaitPromise: true,
              returnByValue: true,
            });
            if (result.exceptionDetails) {
              const details = result.exceptionDetails;
              throw new Error(details.exception?.description || details.exception?.value || details.text || "browser evaluation failed");
            }
            await sleep(500);
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


def _run_browser_change_ledger_smoke(*, browser_path: str, url: str, change_ledger_payload: dict[str, object]) -> dict[str, object]:
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("Node.js is required for the browser-backed WebView Maintenance change ledger smoke.")
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as raw_tmp:
        tmp = Path(raw_tmp)
        port = _free_port()
        payload_path = tmp / "browser-maintenance-change-ledger-payload.json"
        runner_path = tmp / "browser-maintenance-change-ledger-runner.cjs"
        payload_path.write_text(
            json.dumps(
                {
                    "browserPath": browser_path,
                    "port": port,
                    "tmpRoot": str(tmp),
                    "url": url,
                    "changeLedgerPayload": change_ledger_payload,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        runner_path.write_text(_browser_change_ledger_runner_source(), encoding="utf-8")
        return run_node_browser_smoke(
            "Browser-backed WebView Maintenance change ledger smoke",
            node=node,
            runner_path=runner_path,
            payload_path=payload_path,
            timeout_seconds=60,
        )


class WebViewBrowserMaintenanceChangeLedgerSmoke(unittest.TestCase):
    def test_real_browser_renders_maintenance_change_ledger_without_mutation_posts(self) -> None:
        browser_path = _find_browser()
        if not browser_path:
            raise unittest.SkipTest("Chrome or Edge is required for the browser-backed WebView Maintenance change ledger smoke.")

        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved, _source, _output = _write_fixture_state(root)
            media_snapshot = capture_media_no_mutation_snapshot(root)
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v6-test")
            server = LocalApiServer(
                facade,
                token="browser-maintenance-change-ledger-smoke-token",
                resolved_provider=lambda: resolved,
                audit_root_provider=lambda: str(root),
            )
            try:
                server.start()
                result = _run_browser_change_ledger_smoke(
                    browser_path=browser_path,
                    url=f"{server.url}/",
                    change_ledger_payload=_change_ledger_payload(root),
                )
            finally:
                server.stop()
            assert_media_no_mutation(self, media_snapshot)

        self.assertTrue(result["ok"])
        browser_result = result["result"]
        self.assertEqual(browser_result["status"], "ready (2)")
        self.assertEqual(browser_result["posts"], [])
        self.assertIn("/api/maintenance/change-ledger", browser_result["gets"])
        self.assertIn("Plan Queue Strategy Audit", browser_result["detail"])
        self.assertIn("Change ledger hygiene: ready", browser_result["hygiene"])
