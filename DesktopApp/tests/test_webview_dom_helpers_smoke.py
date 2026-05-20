from __future__ import annotations

import shutil
import subprocess
import tempfile
import textwrap
import unittest
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOM_HELPERS = ROOT / "mediapipeline_desktop_app" / "ui_web" / "static" / "assets" / "domHelpers.js"


def _run_node_dom_helper_smoke() -> dict[str, object]:
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("Node.js is required for the WebView DOM helper smoke.")

    script = textwrap.dedent(
        f"""
        const fs = require("fs");
        const vm = require("vm");

        const source = fs.readFileSync({str(DOM_HELPERS)!r}, "utf8");
        const rafCallbacks = [];
        let scrollCalls = 0;
        let focusCalls = 0;
        let selectedByKeyboard = false;

        class FakeClassList {{
          constructor() {{ this.values = new Set(); }}
          contains(name) {{ return this.values.has(name); }}
          toggle(name, force) {{
            if (force) this.values.add(name);
            else this.values.delete(name);
          }}
        }}

        function rowFactory(name, tbody) {{
          const listeners = {{}};
          const row = {{
            name,
            dataset: {{}},
            classList: new FakeClassList(),
            attributes: {{}},
            tabIndex: -1,
            parent: tbody,
            setAttribute(key, value) {{ this.attributes[key] = String(value); }},
            addEventListener(key, fn) {{ listeners[key] = fn; }},
            closest(selector) {{ return selector === "tbody" ? this.parent : null; }},
            focus() {{ focusCalls += 1; }},
            click() {{ if (listeners.click) listeners.click({{ type: "click" }}); }},
            keydown(key) {{
              if (listeners.keydown) {{
                listeners.keydown({{
                  key,
                  preventDefault() {{}},
                }});
              }}
            }},
            scrollIntoView() {{ scrollCalls += 1; }},
          }};
          return row;
        }}

        const tbody = {{
          rows: [],
          querySelectorAll(selector) {{
            if (selector !== 'tr[data-selectable-row="true"]') return [];
            return this.rows.filter((row) => row.dataset.selectableRow === "true");
          }},
        }};

        const context = {{
          window: {{
            requestAnimationFrame(fn) {{ rafCallbacks.push(fn); }},
            setTimeout(fn) {{ fn(); }},
          }},
          document: {{
            getElementById() {{ return null; }},
          }},
        }};
        context.window.window = context.window;
        context.window.document = context.document;
        vm.createContext(context);
        vm.runInContext(source, context);

        const first = rowFactory("first", tbody);
        const second = rowFactory("second", tbody);
        tbody.rows.push(first, second);

        context.window.makeRowSelectable(first, () => {{}}, {{ selected: true }});
        while (rafCallbacks.length) rafCallbacks.shift()();
        if (scrollCalls !== 0) {{
          throw new Error("selected rows should not scroll on normal render; calls=" + scrollCalls);
        }}

        context.window.makeRowSelectable(second, () => {{}}, {{
          selected: true,
          scrollOnRender: true,
        }});
        while (rafCallbacks.length) rafCallbacks.shift()();
        if (scrollCalls !== 1) {{
          throw new Error("explicit scrollOnRender should scroll once; calls=" + scrollCalls);
        }}

        context.window.makeRowSelectable(second, () => {{ selectedByKeyboard = true; }}, {{ selected: false }});
        first.keydown("ArrowDown");
        if (focusCalls !== 1 || !selectedByKeyboard) {{
          throw new Error("keyboard row movement should still focus and select the next row");
        }}

        console.log(JSON.stringify({{
          ok: true,
          scrollCalls,
          focusCalls,
          selectedByKeyboard,
        }}));
        """
    )
    with tempfile.TemporaryDirectory() as raw_tmp:
        runner = Path(raw_tmp) / "dom-helper-scroll-smoke.cjs"
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
            "WebView DOM helper smoke failed.\n"
            f"returncode={result.returncode}\nstdout={result.stdout}\nstderr={result.stderr}"
        )
    return json.loads(result.stdout)


class WebViewDomHelpersSmokeTests(unittest.TestCase):
    def test_selected_rows_do_not_scroll_page_during_normal_render(self) -> None:
        result = _run_node_dom_helper_smoke()

        self.assertTrue(result["ok"])
        self.assertEqual(result["scrollCalls"], 1)
        self.assertEqual(result["focusCalls"], 1)
        self.assertTrue(result["selectedByKeyboard"])


if __name__ == "__main__":
    unittest.main()
