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
COMMAND_BUTTONS_JS = ROOT / "apps" / "desktop" / "webview" / "static" / "assets" / "launch" / "commandButtons.js"
START_REQUEST_JS = ROOT / "apps" / "desktop" / "webview" / "static" / "assets" / "launch" / "startRequest.js"


def _run_launch_command_buttons_smoke() -> dict[str, object]:
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("Node.js is required for the launch command buttons smoke.")

    script = textwrap.dedent(
        f"""
        const fs = require("fs");
        const vm = require("vm");

        const source = fs.readFileSync({str(COMMAND_BUTTONS_JS)!r}, "utf8");
        const context = {{
          window: {{}},
          document: {{ querySelectorAll() {{ return []; }} }},
        }};
        context.window.window = context.window;
        context.window.document = context.document;
        vm.createContext(context);
        vm.runInContext(source, context);

        const factory = context.window.__launchCommandButtonsModule.createLaunchCommandButtonsModule;
        const decisionRequests = [];
        const payloads = {{
          pipeline: {{
            target: "pipeline",
            status: "ready",
            request: {{ mode: "continuous", sleep_seconds: 30, schedule_override: "", single_file: "" }},
          }},
          audit: {{
            target: "audit",
            status: "ready",
            request: {{ library_root: "C:/Library", include_sidecars: true }},
          }},
          rerun: {{
            target: "rerun",
            status: "ready",
            request: {{ csv_path: "C:/rerun.csv", stage_mode: "copy", original_mode: "keep", return_mode: "queue" }},
          }},
        }};
        function valuesMatch(left, right) {{
          return JSON.stringify(left) === JSON.stringify(right);
        }}
        const rerunRequests = [];
        const launchModule = factory({{
          collectPipelineStartRequest() {{
            return {{ mode: "continuous", sleep_seconds: 30, schedule_override: "", single_file: "", pipeline_only_blocker: true }};
          }},
          collectAuditStartRequest() {{ return {{ library_root: "C:/Library", include_sidecars: true }}; }},
          collectRerunStartRequest(options = {{}}) {{
            const request = {{ csv_path: "C:/rerun.csv", dry_run: Boolean(options.dry_run), stage_mode: "copy", original_mode: "keep", return_mode: "queue" }};
            rerunRequests.push(request);
            return request;
          }},
          launchBackendPreflightPayloadForTarget(target) {{ return payloads[target] || null; }},
          launchBackendPreflightOverallStatus(items) {{
            return items.some((item) => String(item.status || "").toLowerCase() === "blocked") ? "Blocked" : "Ready";
          }},
          launchPreflightRequestMatches(payload, request, keys) {{
            return keys.every((key) => valuesMatch(payload.request?.[key], request?.[key]));
          }},
          launchStartDecisionRows(request) {{
            decisionRequests.push(request);
            return [{{ posture: "blocked", signal: "Injected pipeline-only blocker" }}];
          }},
          launchStartDecisionStatus(rows) {{
            return rows.some((row) => row.posture === "blocked") ? "Blocked" : "Ready";
          }},
          launchStartDecisionPostureFromStatus(status) {{
            return String(status || "").toLowerCase().includes("blocked") ? "blocked" : "ready";
          }},
          launchStartDecisionWorstPosture(postures) {{
            return postures.includes("blocked") ? "blocked" : "ready";
          }},
        }});

        const pipelineGate = launchModule.launchButtonGate("pipeline-start-button");
        const auditGate = launchModule.launchButtonGate("audit-start-button");
        const rerunDryRunGate = launchModule.launchButtonGate("rerun-dry-run-button");
        const rerunGate = launchModule.launchButtonGate("rerun-start-button");
        process.stdout.write(JSON.stringify({{
          pipelineGate,
          auditGate,
          rerunDryRunGate,
          rerunGate,
          decisionRequestCount: decisionRequests.length,
          decisionRequests,
          rerunRequests,
        }}));
        """
    )
    with tempfile.TemporaryDirectory() as raw_tmp:
        runner = Path(raw_tmp) / "launch-command-buttons-smoke.cjs"
        runner.write_text(script, encoding="utf-8")
        result = subprocess.run(
            [node, str(runner)],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=20,
            check=False,
        )
    if result.returncode != 0:
        raise AssertionError(
            "Launch command buttons smoke failed.\n"
            f"returncode={result.returncode}\nstdout={result.stdout}\nstderr={result.stderr}"
        )
    return json.loads(result.stdout)


def _run_launch_start_request_smoke() -> dict[str, object]:
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("Node.js is required for the launch start request smoke.")

    script = textwrap.dedent(
        f"""
        const fs = require("fs");
        const vm = require("vm");

        const source = fs.readFileSync({str(START_REQUEST_JS)!r}, "utf8");
        const fields = {{
          "pipeline-start-mode": {{ value: "continuous" }},
          "pipeline-start-single-file": {{ value: "C:/Source/Movie.mkv" }},
          "pipeline-start-sleep": {{ value: "7" }},
          "pipeline-start-schedule-override": {{ value: "run_once" }},
          "pipeline-start-show-config": {{ checked: true }},
          "pipeline-start-show-console": {{ checked: false }},
          "rerun-start-csv-path": {{ value: "C:/rerun.csv" }},
          "rerun-start-show-console": {{ checked: true }},
          "queue-filter-text": {{ value: "visible-only" }},
          "queue-selected-row": {{ value: "C:/Other/Selected.mkv" }},
        }};
        const context = {{ window: {{}} }};
        context.window.window = context.window;
        vm.createContext(context);
        vm.runInContext(source, context);

        const startRequestModule = context.window.__launchStartRequestModule.createLaunchStartRequestModule({{
          byId(id) {{ return fields[id] || null; }},
        }});
        const pipelineRequest = startRequestModule.collectPipelineStartRequest();
        const rerunDryRun = startRequestModule.collectRerunStartRequest({{ dry_run: true }});
        const rerunLive = startRequestModule.collectRerunStartRequest({{ dry_run: false }});
        process.stdout.write(JSON.stringify({{ pipelineRequest, rerunDryRun, rerunLive }}));
        """
    )
    with tempfile.TemporaryDirectory() as raw_tmp:
        runner = Path(raw_tmp) / "launch-start-request-smoke.cjs"
        runner.write_text(script, encoding="utf-8")
        result = subprocess.run(
            [node, str(runner)],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=20,
            check=False,
        )
    if result.returncode != 0:
        raise AssertionError(
            "Launch start request smoke failed.\n"
            f"returncode={result.returncode}\nstdout={result.stdout}\nstderr={result.stderr}"
        )
    return json.loads(result.stdout)


class WebViewLaunchCommandButtonsSmoke(unittest.TestCase):
    def test_audit_and_rerun_gates_ignore_pipeline_only_start_decision_blockers(self) -> None:
        result = _run_launch_command_buttons_smoke()

        self.assertTrue(result["pipelineGate"]["blocked"])
        self.assertFalse(result["auditGate"]["blocked"])
        self.assertFalse(result["rerunDryRunGate"]["blocked"])
        self.assertFalse(result["rerunGate"]["blocked"])
        self.assertEqual(result["decisionRequestCount"], 1)
        self.assertTrue(result["decisionRequests"][0]["pipeline_only_blocker"])
        self.assertTrue(any(item["dry_run"] for item in result["rerunRequests"]))
        self.assertTrue(any(not item["dry_run"] for item in result["rerunRequests"]))

    def test_start_request_collectors_keep_queue_scope_out_and_support_rerun_dry_run(self) -> None:
        result = _run_launch_start_request_smoke()
        pipeline_request = result["pipelineRequest"]

        self.assertEqual(pipeline_request["mode"], "continuous")
        self.assertEqual(pipeline_request["single_file"], "C:/Source/Movie.mkv")
        self.assertEqual(pipeline_request["sleep_seconds"], 7)
        self.assertEqual(pipeline_request["schedule_override"], "run_once")
        self.assertNotIn("queue_filter", pipeline_request)
        self.assertNotIn("selected_row", pipeline_request)
        self.assertNotIn("selected_path", pipeline_request)
        self.assertTrue(result["rerunDryRun"]["dry_run"])
        self.assertFalse(result["rerunLive"]["dry_run"])
        self.assertEqual(result["rerunDryRun"]["stage_mode"], "copy")
        self.assertEqual(result["rerunDryRun"]["original_mode"], "keep")
        self.assertEqual(result["rerunDryRun"]["return_mode"], "park")


if __name__ == "__main__":
    unittest.main()
