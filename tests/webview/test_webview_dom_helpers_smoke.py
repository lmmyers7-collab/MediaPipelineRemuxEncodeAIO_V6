from __future__ import annotations

import shutil
import subprocess
import tempfile
import textwrap
import unittest
import json
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root


ROOT = find_repo_root(Path(__file__))
ASSETS_ROOT = ROOT / "apps" / "desktop" / "webview" / "static" / "assets"
DOM_HELPER_ASSETS = [
    "dom/query.js",
    "dom/text.js",
    "dom/status.js",
    "dom/filtering.js",
    "dom/table.js",
    "domHelpers.js",
]


def _run_node_dom_helper_smoke() -> dict[str, object]:
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("Node.js is required for the WebView DOM helper smoke.")

    script = textwrap.dedent(
        f"""
        const fs = require("fs");
        const vm = require("vm");

        const source = {DOM_HELPER_ASSETS!r}
          .map((name) => fs.readFileSync({str(ASSETS_ROOT)!r} + "/" + name, "utf8"))
          .join("\\n");
        const rafCallbacks = [];
        let scrollCalls = 0;
        let focusCalls = 0;
        let selectedByKeyboard = false;
        let queryAllNodes = [];

        class FakeClassList {{
          constructor(owner = null, initial = []) {{
            this.owner = owner;
            this.values = new Set(initial);
          }}
          contains(name) {{ return this.values.has(name); }}
          toggle(name, force) {{
            const enabled = force === undefined ? !this.values.has(name) : Boolean(force);
            if (enabled) this.values.add(name);
            else this.values.delete(name);
            this.syncOwner();
          }}
          add(...names) {{
            names.forEach((name) => this.values.add(name));
            this.syncOwner();
          }}
          remove(...names) {{
            names.forEach((name) => this.values.delete(name));
            this.syncOwner();
          }}
          setFromClassName(className) {{
            this.values = new Set(String(className || "").split(/\\s+/).filter(Boolean));
          }}
          syncOwner() {{
            if (this.owner) this.owner._className = Array.from(this.values).join(" ");
          }}
        }}

        function datasetKey(name) {{
          return String(name || "")
            .replace(/^data-/, "")
            .replace(/-([a-z])/g, (_, letter) => letter.toUpperCase());
        }}

        function makeElement(id = "", tag = "div", initialClass = "") {{
          let text = "";
          const listeners = {{}};
          const node = {{
            id,
            tagName: String(tag || "div").toUpperCase(),
            nodeName: String(tag || "div").toUpperCase(),
            dataset: {{}},
            style: {{}},
            attributes: [],
            children: [],
            parentNode: null,
            parentElement: null,
            isConnected: true,
            scrollTop: 0,
            scrollLeft: 0,
            scrollHeight: 0,
            clientHeight: 0,
            scrollWidth: 0,
            clientWidth: 0,
            textWriteCount: 0,
            replaceChildren(...children) {{
              this.children = [];
              children.forEach((child) => this.appendChild(child));
            }},
            appendChild(child) {{
              this.children.push(child);
              child.parentNode = this;
              child.parentElement = this;
              return child;
            }},
            append(...children) {{
              children.forEach((child) => this.appendChild(child));
            }},
            replaceWith(replacement) {{
              if (this.id && !replacement.id) replacement.id = this.id;
              if (replacement.id) elements.set(replacement.id, replacement);
              this.isConnected = false;
            }},
            querySelectorAll(selector) {{
              return queryDescendants(this, selector);
            }},
            querySelector(selector) {{
              return queryDescendants(this, selector)[0] || null;
            }},
            setAttribute(name, value) {{
              const stringValue = String(value);
              const existing = this.attributes.find((attr) => attr.name === name);
              if (existing) existing.value = stringValue;
              else this.attributes.push({{ name, value: stringValue }});
              if (name === "id") {{
                this.id = stringValue;
                elements.set(stringValue, this);
              }} else if (name === "class") {{
                this.className = stringValue;
              }} else if (name.startsWith("data-")) {{
                this.dataset[datasetKey(name)] = stringValue;
              }}
            }},
            getAttribute(name) {{
              const found = this.attributes.find((attr) => attr.name === name);
              return found ? found.value : "";
            }},
            addEventListener(key, fn) {{ listeners[key] = fn; }},
            removeEventListener() {{}},
            closest() {{ return null; }},
          }};
          node.classList = new FakeClassList(node);
          Object.defineProperty(node, "className", {{
            get() {{ return this._className || ""; }},
            set(value) {{
              this._className = String(value || "");
              this.classList.setFromClassName(this._className);
            }},
          }});
          Object.defineProperty(node, "textContent", {{
            get() {{
              if (this.children.length) return this.children.map((child) => child.textContent || "").join("");
              return text;
            }},
            set(value) {{
              text = value === null || value === undefined ? "" : String(value);
              this.children = [];
              this.scrollTop = 0;
              this.textWriteCount += 1;
            }},
          }});
          node.className = initialClass;
          if (id) node.setAttribute("id", id);
          if (initialClass) node.setAttribute("class", initialClass);
          return node;
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

        const elements = new Map();
        const documentScroller = makeElement("document-scroller", "html");
        documentScroller.scrollTop = 120;
        documentScroller.scrollLeft = 8;
        documentScroller.scrollHeight = 700;
        documentScroller.clientHeight = 300;
        documentScroller.scrollWidth = 500;
        documentScroller.clientWidth = 250;

        function queryDescendants(node, selector) {{
          const matches = [];
          function visit(item) {{
            if (!item) return;
            const wantsDiagnosticBody = selector === '[data-diagnostic-callout-body="true"]';
            if (wantsDiagnosticBody && item.dataset?.diagnosticCalloutBody === "true") {{
              matches.push(item);
            }}
            (item.children || []).forEach(visit);
          }}
          visit(node);
          return matches;
        }}

        const context = {{
          window: {{
            requestAnimationFrame(fn) {{ rafCallbacks.push(fn); }},
            setTimeout(fn) {{ fn(); }},
            scrollTo(left, top) {{
              documentScroller.scrollLeft = left;
              documentScroller.scrollTop = top;
            }},
            getComputedStyle(node) {{
              return node.style || {{}};
            }},
          }},
          document: {{
            scrollingElement: documentScroller,
            documentElement: documentScroller,
            body: documentScroller,
            getElementById(id) {{ return elements.get(id) || null; }},
            createElement(tag) {{ return makeElement("", tag); }},
            querySelectorAll(selector) {{ return selector === "*" ? queryAllNodes : []; }},
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

        const detail = makeElement("scroll-detail", "pre", "prose-block");
        elements.set("scroll-detail", detail);
        const handoffText = [
          "Diagnostics handoff:",
          "Selected owning-page handoff detail.",
          "Mutation guardrail: this detail is read-only and cannot launch, drain, publish, mutate, or touch files.",
        ].join("\\n");
        context.window.setText("scroll-detail", handoffText);
        const renderedRoot = elements.get("scroll-detail");
        const calloutBody = renderedRoot.querySelector('[data-diagnostic-callout-body="true"]');
        if (!calloutBody) {{
          throw new Error("expected diagnostic callout body to render for prose detail");
        }}
        calloutBody.scrollTop = 48;
        const bodyWritesBeforeRefresh = calloutBody.textWriteCount;
        context.window.setText("scroll-detail", handoffText);
        const afterRefreshRoot = elements.get("scroll-detail");
        const afterRefreshBody = afterRefreshRoot.querySelector('[data-diagnostic-callout-body="true"]');
        if (afterRefreshBody !== calloutBody) {{
          throw new Error("refresh with unchanged text should not replace the scrollable callout body");
        }}
        if (afterRefreshBody.scrollTop !== 48) {{
          throw new Error("refresh with unchanged text should preserve callout scrollTop; got " + afterRefreshBody.scrollTop);
        }}
        if (afterRefreshBody.textWriteCount !== bodyWritesBeforeRefresh) {{
          throw new Error("refresh with unchanged text should not rewrite callout textContent");
        }}

        const stableWrap = makeElement("stable-scroll-wrap", "div", "table-wrap");
        stableWrap.scrollTop = 90;
        stableWrap.scrollLeft = 12;
        stableWrap.scrollHeight = 420;
        stableWrap.clientHeight = 120;
        stableWrap.scrollWidth = 520;
        stableWrap.clientWidth = 220;
        stableWrap.style = {{ overflow: "auto", overflowX: "auto", overflowY: "auto", display: "block", visibility: "visible" }};
        const replacedDetail = makeElement("replaceable-scroll-detail", "pre", "prose-block");
        replacedDetail.scrollTop = 70;
        replacedDetail.scrollHeight = 360;
        replacedDetail.clientHeight = 120;
        replacedDetail.scrollWidth = 220;
        replacedDetail.clientWidth = 220;
        replacedDetail.style = {{ overflow: "auto", overflowX: "auto", overflowY: "auto", display: "block", visibility: "visible" }};
        queryAllNodes = [stableWrap, replacedDetail];
        documentScroller.scrollTop = 120;
        documentScroller.scrollLeft = 8;
        const snapshot = context.window.mediaPipelineDom.captureScrollablePositions();
        stableWrap.scrollTop = 0;
        stableWrap.scrollLeft = 0;
        documentScroller.scrollTop = 0;
        documentScroller.scrollLeft = 0;
        replacedDetail.isConnected = false;
        const replacementDetail = makeElement("replaceable-scroll-detail", "pre", "prose-block");
        replacementDetail.scrollHeight = 360;
        replacementDetail.clientHeight = 120;
        replacementDetail.scrollWidth = 220;
        replacementDetail.clientWidth = 220;
        replacementDetail.style = {{ overflow: "auto", overflowX: "auto", overflowY: "auto", display: "block", visibility: "visible" }};
        context.window.mediaPipelineDom.restoreScrollablePositions(snapshot);
        while (rafCallbacks.length) rafCallbacks.shift()();
        if (stableWrap.scrollTop !== 90 || stableWrap.scrollLeft !== 12) {{
          throw new Error("stable scrollable wrapper was not restored");
        }}
        if (replacementDetail.scrollTop !== 70) {{
          throw new Error("replaced scrollable detail was not restored by id");
        }}
        if (documentScroller.scrollTop !== 120 || documentScroller.scrollLeft !== 8) {{
          throw new Error("document scroll was not restored");
        }}

        console.log(JSON.stringify({{
          ok: true,
          scrollCalls,
          focusCalls,
          selectedByKeyboard,
          calloutScrollTop: afterRefreshBody.scrollTop,
          stableWrapTop: stableWrap.scrollTop,
          replacementDetailTop: replacementDetail.scrollTop,
          documentTop: documentScroller.scrollTop,
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


class WebViewDomHelpersSmoke(unittest.TestCase):
    def test_selected_rows_do_not_scroll_page_during_normal_render(self) -> None:
        result = _run_node_dom_helper_smoke()

        self.assertTrue(result["ok"])
        self.assertEqual(result["scrollCalls"], 1)
        self.assertEqual(result["focusCalls"], 1)
        self.assertTrue(result["selectedByKeyboard"])
        self.assertEqual(result["calloutScrollTop"], 48)
        self.assertEqual(result["stableWrapTop"], 90)
        self.assertEqual(result["replacementDetailTop"], 70)
        self.assertEqual(result["documentTop"], 120)


if __name__ == "__main__":
    unittest.main()
