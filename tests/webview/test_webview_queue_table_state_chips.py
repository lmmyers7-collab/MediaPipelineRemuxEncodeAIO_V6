from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root


QUEUE_TABLE_JS = (
    find_repo_root(Path(__file__))
    / "apps"
    / "desktop"
    / "webview"
    / "static"
    / "assets"
    / "queue"
    / "table.js"
)


def _run_queue_state_chip_smoke() -> dict[str, object]:
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("Node.js is required for the queue table state chip smoke.")

    script = textwrap.dedent(
        f"""
        const fs = require("fs");
        const vm = require("vm");

        function makeElement(tag = "span") {{
          return {{
            tagName: String(tag || "span").toUpperCase(),
            className: "",
            dataset: {{}},
            children: [],
            _text: "",
            appendChild(child) {{ this.children.push(child); return child; }},
            set textContent(value) {{ this._text = String(value); }},
            get textContent() {{
              return this._text || this.children.map((child) => child.textContent || "").join("");
            }},
          }};
        }}

        const context = {{
          window: {{}},
          document: {{
            createElement(tag) {{ return makeElement(tag); }},
          }},
        }};
        context.window.window = context.window;
        context.window.document = context.document;

        vm.createContext(context);
        vm.runInContext(fs.readFileSync({str(QUEUE_TABLE_JS)!r}, "utf8"), context);

        const table = context.window.__queueTableModule.createQueueTableModule();
        function chip(status, row = {{}}) {{
          const node = table.makeQueueStateChip(row, status);
          return {{ text: node.textContent, state: node.dataset.state }};
        }}

        process.stdout.write(JSON.stringify({{
          parked: chip("parked"),
          pendingPublish: chip("pending_publish"),
          reviewWorkspace: chip("review_workspace"),
          warning: chip("warning", {{ operator_severity: "warning" }}),
          blocked: chip("blocked"),
        }}));
        """
    )

    with tempfile.TemporaryDirectory() as raw_tmp:
        runner = Path(raw_tmp) / "queue-state-chip-smoke.cjs"
        runner.write_text(script, encoding="utf-8")
        result = subprocess.run(
            [node, str(runner)],
            text=True,
            capture_output=True,
            timeout=20,
            check=False,
        )
    if result.returncode != 0:
        raise AssertionError(
            "Queue table state chip smoke failed.\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
    return json.loads(result.stdout)


class WebViewQueueTableStateChipTests(unittest.TestCase):
    def test_parked_csv_rerun_states_do_not_render_as_review(self) -> None:
        result = _run_queue_state_chip_smoke()

        self.assertEqual(result["parked"], {"text": "Parked", "state": "parked"})
        self.assertEqual(result["pendingPublish"], {"text": "Pending Publish", "state": "parked"})
        self.assertEqual(result["reviewWorkspace"], {"text": "Parked", "state": "parked"})
        self.assertEqual(result["warning"], {"text": "Review", "state": "review"})
        self.assertEqual(result["blocked"], {"text": "Blocked", "state": "blocked"})


if __name__ == "__main__":
    unittest.main()
