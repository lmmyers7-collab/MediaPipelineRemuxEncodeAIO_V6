from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import textwrap
import unittest


REPO_ROOT = Path(__file__).resolve().parents[2]


class PriorityQueueExportWebViewTests(unittest.TestCase):
    def _read(self, relative_path: str) -> str:
        return (REPO_ROOT / relative_path).read_text(encoding="utf-8")

    def test_queue_prepares_export_without_launching_pipeline(self) -> None:
        source = self._read("apps/desktop/webview/static/assets/queue/priority.js")
        self.assertIn('apiPost("/api/queue/priority-export", {})', source)
        self.assertNotIn('apiPost("/api/pipeline/start"', source)
        self.assertIn("data.count", source)
        self.assertIn("data.export_id", source)

    def test_launch_submits_backend_export_id_and_never_browser_rows(self) -> None:
        source = self._read("apps/desktop/webview/static/assets/launch/startRequest.js")
        self.assertIn('queue_scope: selectedScope === "priority_export" ? "priority_export" : "backend_queue"', source)
        self.assertIn('byId("pipeline-priority-export-id")', source)
        self.assertIn("request.priority_export_id = exportId", source)
        self.assertNotIn("selectedRows", source)
        self.assertNotIn("visibleRows", source)

    def test_queue_and_launch_expose_export_count_and_readiness(self) -> None:
        queue_markup = self._read("apps/desktop/webview/static/partials/page-queue.html")
        launch_markup = self._read("apps/desktop/webview/static/partials/page-launch.html")
        scope_source = self._read("apps/desktop/webview/static/assets/launch/scopeControls.js")
        self.assertIn('id="queue-priority-export-btn"', queue_markup)
        self.assertIn('data-pipeline-scope-preset="priority_export"', launch_markup)
        self.assertIn('id="pipeline-priority-export-status"', launch_markup)
        self.assertIn('apiGet("/api/queue/priority-export")', scope_source)
        self.assertIn("exported item", scope_source)

    def test_priority_export_scope_forces_run_once_in_the_ui(self) -> None:
        source = self._read("apps/desktop/webview/static/assets/launch/scopeControls.js")
        self.assertIn('modeSelect.value = "once"', source)
        self.assertIn('selectedScope === "priority_export"', source)

    def test_modules_send_only_empty_export_request_then_export_id(self) -> None:
        node = shutil.which("node")
        if not node:
            self.skipTest("Node.js is not available")
        script = textwrap.dedent(
            r"""
            const fs = require("fs");
            const vm = require("vm");
            global.window = {};
            vm.runInThisContext(fs.readFileSync(process.argv[1], "utf8"));
            const calls = [];
            const priority = window.__queuePriorityModule.createQueuePriorityModule({
              apiPost: async (route, payload) => {
                calls.push({ route, payload });
                return { ok: true, data: { count: 2, export_id: "priority-export-runtime-test" } };
              },
              appendCommandResult: () => {},
              byId: () => ({ disabled: false }),
              getScanLoading: () => false,
              setText: () => {},
            });
            (async () => {
              await priority.exportPriorityQueue();
              global.window = {};
              vm.runInThisContext(fs.readFileSync(process.argv[2], "utf8"));
              const values = {
                "pipeline-start-sleep": { value: "30" },
                "pipeline-start-mode": { value: "once" },
                "pipeline-start-schedule-override": { value: "" },
                "pipeline-start-single-file": { value: "" },
                "pipeline-start-show-config": { checked: false },
                "pipeline-start-show-console": { checked: false },
                "pipeline-priority-export-id": { value: "priority-export-runtime-test" },
              };
              const request = window.__launchStartRequestModule.createLaunchStartRequestModule({
                byId: (id) => values[id] || null,
                getPipelineStartScope: () => "priority_export",
              }).collectPipelineStartRequest();
              process.stdout.write(JSON.stringify({ calls, request }));
            })().catch((error) => { console.error(error); process.exit(1); });
            """
        )
        result = subprocess.run(
            [
                node,
                "-e",
                script,
                str(REPO_ROOT / "apps/desktop/webview/static/assets/queue/priority.js"),
                str(REPO_ROOT / "apps/desktop/webview/static/assets/launch/startRequest.js"),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["calls"], [{"route": "/api/queue/priority-export", "payload": {}}])
        self.assertEqual(
            payload["request"]["priority_export_id"],
            "priority-export-runtime-test",
        )
        self.assertEqual(payload["request"]["queue_scope"], "priority_export")
        self.assertNotIn("rows", payload["request"])
        self.assertNotIn("selected_rows", payload["request"])


if __name__ == "__main__":
    unittest.main()
