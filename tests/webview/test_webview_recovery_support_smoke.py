from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root


ROOT = find_repo_root(Path(__file__))
WEBVIEW_ROOT = ROOT / "apps" / "desktop" / "webview" / "static"
RECOVERY_SOURCE = WEBVIEW_ROOT / "assets" / "recoverySupportView.js"
DIAGNOSTICS_PARTIAL = WEBVIEW_ROOT / "partials" / "page-diagnostics.html"


def _run_recovery_support_smoke() -> dict[str, object]:
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("Node.js is required for the WebView recovery-support smoke.")

    runner = textwrap.dedent(
        r"""
        const fs = require("fs");
        const vm = require("vm");

        const source = fs.readFileSync(process.argv[2], "utf8");
        const elements = new Map();
        const posts = [];
        const commandResults = [];
        let confirmCalls = 0;
        let refreshCalls = 0;
        let previewCallCount = 0;
        let pendingPreviewResolve = null;
        let pendingApplyResolve = null;

        function makeElement(id) {
          const listeners = {};
          return {
            id,
            textContent: "",
            value: "",
            checked: false,
            disabled: false,
            hidden: false,
            dataset: {},
            attributes: {},
            addEventListener(type, callback) {
              if (!listeners[type]) listeners[type] = [];
              listeners[type].push(callback);
            },
            setAttribute(name, value) {
              this.attributes[name] = String(value);
            },
            click() {
              if (this.disabled) return;
              for (const callback of listeners.click || []) {
                callback({ type: "click", target: this, preventDefault() {} });
              }
            },
          };
        }

        function byId(id) {
          if (!elements.has(id)) elements.set(id, makeElement(id));
          return elements.get(id);
        }

        function unsafePreviewResult() {
          return {
            command: "backend.lifecycle.reconcile_dry_run",
            ok: true,
            severity: "warning",
            message: "Lifecycle evidence is not safe to reconcile.",
            data: {
              classification: "blocked",
              safe_to_apply: false,
              dry_run_fingerprint: "unsafe-fingerprint",
              preconditions: [{ key: "process_correlation", status: "blocked" }],
            },
          };
        }

        function safePreviewResult() {
          return {
            command: "backend.lifecycle.reconcile_dry_run",
            ok: true,
            severity: "info",
            message: "One stale lifecycle record can be reconciled.",
            data: {
              classification: "stale_evidence_only",
              safe_to_apply: true,
              dry_run_fingerprint: "safe-fingerprint",
              preconditions: [{ key: "process_correlation", status: "passed" }],
              process_record_correlation: { active_process_count: 0, stale_record_count: 1 },
            },
          };
        }

        async function apiPost(path, body = {}) {
          posts.push({ path: String(path || ""), body: { ...body } });
          if (path === "/api/backend/lifecycle/reconcile-dry-run") {
            previewCallCount += 1;
            if (previewCallCount === 1) {
              return new Promise((resolve) => { pendingPreviewResolve = resolve; });
            }
            return safePreviewResult();
          }
          if (path === "/api/backend/lifecycle/reconcile") {
            return new Promise((resolve) => { pendingApplyResolve = resolve; });
          }
          throw new Error(`Unexpected apiPost route: ${path}`);
        }

        const context = {
          console,
          setTimeout,
          clearTimeout,
          document: {
            getElementById: byId,
          },
          apiPost,
          appendCommandResult(result) { commandResults.push(result); },
          async refreshAll() { refreshCalls += 1; },
          confirm() {
            confirmCalls += 1;
            throw new Error("Lifecycle reconcile must not add a browser confirmation prompt.");
          },
        };
        context.window = context;
        context.globalThis = context;
        context.mediaPipelineApi = { apiPost };

        vm.createContext(context);
        vm.runInContext(source, context, { filename: "recoverySupportView.js" });

        function requireValue(condition, message) {
          if (!condition) throw new Error(message);
        }

        async function waitFor(predicate, label) {
          const deadline = Date.now() + 1500;
          while (Date.now() < deadline) {
            if (predicate()) return;
            await new Promise((resolve) => setTimeout(resolve, 5));
          }
          throw new Error(`Timed out waiting for ${label}`);
        }

        function sortedKeys(value) {
          return Object.keys(value || {}).sort();
        }

        function forbiddenPayloadKeys(value, path = "request") {
          const forbidden = [];
          const forbiddenNames = new Set([
            "path", "paths", "source_path", "destination_path", "lock_path",
            "record_path", "archive_path", "pid", "process_id", "delete",
            "clear", "force", "patch", "lifecycle_record",
          ]);
          if (!value || typeof value !== "object") return forbidden;
          for (const [key, child] of Object.entries(value)) {
            if (forbiddenNames.has(String(key).toLowerCase())) forbidden.push(`${path}.${key}`);
            forbidden.push(...forbiddenPayloadKeys(child, `${path}.${key}`));
          }
          return forbidden;
        }

        (async () => {
          const view = context.mediaPipelineRecoverySupportView;
          requireValue(view && typeof view.initRecoverySupportEvents === "function", "missing recovery support namespace/init");
          view.initRecoverySupportEvents();

          const previewButton = byId("diagnostics-recovery-preview-button");
          const reconcileButton = byId("diagnostics-recovery-reconcile-button");
          requireValue(reconcileButton.disabled === true, "reconcile must start disabled until a safe preview exists");

          previewButton.click();
          previewButton.click();
          await waitFor(() => posts.length === 1 && typeof pendingPreviewResolve === "function", "deduplicated pending preview");
          requireValue(previewButton.disabled === true, "preview button must be disabled while preview is pending");
          requireValue(reconcileButton.disabled === true, "reconcile must stay disabled while preview is pending");
          pendingPreviewResolve(unsafePreviewResult());
          await waitFor(() => previewButton.disabled === false, "unsafe preview completion");
          requireValue(reconcileButton.disabled === true, "unsafe preview must not enable reconcile");

          previewButton.click();
          await waitFor(() => posts.length === 2 && reconcileButton.disabled === false, "safe preview enables reconcile");
          requireValue(
            JSON.stringify(sortedKeys(posts[1].body)) === JSON.stringify(["reason"]),
            `dry-run request keys were not strict: ${JSON.stringify(sortedKeys(posts[1].body))}`,
          );

          reconcileButton.click();
          reconcileButton.click();
          await waitFor(() => posts.length === 3 && typeof pendingApplyResolve === "function", "deduplicated pending reconcile");
          requireValue(reconcileButton.disabled === true, "reconcile must disable immediately while apply is pending");
          requireValue(
            JSON.stringify(sortedKeys(posts[2].body)) === JSON.stringify(["confirm_apply", "dry_run_fingerprint", "reason"]),
            `apply request keys were not strict: ${JSON.stringify(sortedKeys(posts[2].body))}`,
          );
          requireValue(posts[2].body.confirm_apply === true, "apply request must send strict confirm_apply=true");
          requireValue(posts[2].body.dry_run_fingerprint === "safe-fingerprint", "apply request must reuse the safe preview fingerprint");
          requireValue(forbiddenPayloadKeys(posts[1].body).length === 0, `dry-run request exposed forbidden keys: ${forbiddenPayloadKeys(posts[1].body).join(", ")}`);
          requireValue(forbiddenPayloadKeys(posts[2].body).length === 0, `apply request exposed forbidden keys: ${forbiddenPayloadKeys(posts[2].body).join(", ")}`);

          pendingApplyResolve({
            command: "backend.lifecycle.reconcile",
            ok: true,
            severity: "info",
            message: "Stale lifecycle evidence was archived.",
            data: {
              applied: true,
              archive_transaction: { transaction_id: "fixture-transaction" },
              recovery_status_after: { status: "complete", classification: "completed" },
            },
          });
          await waitFor(() => refreshCalls === 1, "post-apply refresh");
          requireValue(reconcileButton.disabled === true, "apply must consume the preview and require a new preview");
          requireValue(confirmCalls === 0, `browser confirm was called ${confirmCalls} time(s)`);
          requireValue(commandResults.length >= 3, "preview/apply outcomes must append command evidence");

          process.stdout.write(JSON.stringify({
            posts,
            confirmCalls,
            refreshCalls,
            commandResultCount: commandResults.length,
            actionStatus: byId("diagnostics-recovery-action-status").textContent,
            actionDetail: byId("diagnostics-recovery-action-detail").textContent,
          }));
        })().catch((error) => {
          console.error(error && error.stack ? error.stack : error);
          process.exitCode = 1;
        });
        """
    )

    with tempfile.TemporaryDirectory() as raw:
        script_path = Path(raw) / "recovery-support-smoke.cjs"
        script_path.write_text(runner, encoding="utf-8")
        completed = subprocess.run(
            [node, str(script_path), str(RECOVERY_SOURCE)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    if completed.returncode != 0:
        raise AssertionError(
            "WebView recovery-support smoke failed.\n"
            f"stdout:\n{completed.stdout}\n"
            f"stderr:\n{completed.stderr}"
        )
    return json.loads(completed.stdout)


class WebViewRecoverySupportSmoke(unittest.TestCase):
    def test_diagnostics_startup_recovery_exposes_minimal_preview_gated_controls(self) -> None:
        html = DIAGNOSTICS_PARTIAL.read_text(encoding="utf-8")
        source = RECOVERY_SOURCE.read_text(encoding="utf-8")

        self.assertIn('id="diagnostics-recovery-preview-button"', html)
        self.assertIn('id="diagnostics-recovery-reconcile-button"', html)
        self.assertIn('id="diagnostics-recovery-action-status"', html)
        self.assertIn('id="diagnostics-recovery-action-detail"', html)
        self.assertIn("Preview Lifecycle Reconcile", html)
        self.assertIn("Reconcile Stale Lifecycle Evidence", html)
        self.assertRegex(
            html,
            r'id="diagnostics-recovery-reconcile-button"[^>]*class="danger-button"[^>]*disabled',
        )
        self.assertIn('"/api/backend/lifecycle/reconcile-dry-run"', source)
        self.assertIn('"/api/backend/lifecycle/reconcile"', source)
        self.assertIn("confirm_apply: true", source)
        self.assertIn("dry_run_fingerprint", source)
        self.assertNotIn("window.confirm", source)

    def test_reconcile_click_path_is_strict_preview_gated_and_duplicate_safe(self) -> None:
        result = _run_recovery_support_smoke()

        self.assertEqual(
            [post["path"] for post in result["posts"]],
            [
                "/api/backend/lifecycle/reconcile-dry-run",
                "/api/backend/lifecycle/reconcile-dry-run",
                "/api/backend/lifecycle/reconcile",
            ],
        )
        self.assertEqual(result["confirmCalls"], 0)
        self.assertEqual(result["refreshCalls"], 1)
        self.assertGreaterEqual(result["commandResultCount"], 3)
        self.assertTrue(str(result["actionStatus"]).strip())
        self.assertIn("Stale lifecycle evidence was archived", str(result["actionDetail"]))


if __name__ == "__main__":
    unittest.main()
