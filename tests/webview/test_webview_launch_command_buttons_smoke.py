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
        const launchModule = factory({{
          collectPipelineStartRequest() {{
            return {{ mode: "continuous", sleep_seconds: 30, schedule_override: "", single_file: "", pipeline_only_blocker: true }};
          }},
          collectAuditStartRequest() {{ return {{ library_root: "C:/Library", include_sidecars: true }}; }},
          collectRerunStartRequest() {{
            return {{ csv_path: "C:/rerun.csv", stage_mode: "copy", original_mode: "keep", return_mode: "queue" }};
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
        const rerunGate = launchModule.launchButtonGate("rerun-start-button");
        process.stdout.write(JSON.stringify({{
          pipelineGate,
          auditGate,
          rerunGate,
          decisionRequestCount: decisionRequests.length,
          decisionRequests,
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


class WebViewLaunchCommandButtonsSmoke(unittest.TestCase):
    def test_audit_and_rerun_gates_ignore_pipeline_only_start_decision_blockers(self) -> None:
        result = _run_launch_command_buttons_smoke()

        self.assertTrue(result["pipelineGate"]["blocked"])
        self.assertFalse(result["auditGate"]["blocked"])
        self.assertFalse(result["rerunGate"]["blocked"])
        self.assertEqual(result["decisionRequestCount"], 1)
        self.assertTrue(result["decisionRequests"][0]["pipeline_only_blocker"])


if __name__ == "__main__":
    unittest.main()
