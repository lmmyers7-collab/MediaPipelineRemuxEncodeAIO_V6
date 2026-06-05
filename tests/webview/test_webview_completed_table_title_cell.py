from __future__ import annotations

import shutil
import subprocess
import textwrap
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root


class WebViewCompletedTableTitleCellTests(unittest.TestCase):
    def test_completed_table_title_cell_omits_duplicate_meta_and_prefers_tv_episode(self) -> None:
        node = shutil.which("node")
        if not node:
            raise unittest.SkipTest("Node.js is required for the Completed table static smoke.")
        repo_root = find_repo_root(Path(__file__))
        script = textwrap.dedent(
            r"""
            const fs = require("fs");
            const vm = require("vm");
            const path = require("path");
            const tablePath = path.join(
              process.cwd(),
              "apps/desktop/webview/static/assets/completed/table.js"
            );
            const source = fs.readFileSync(tablePath, "utf8");

            function makeElement(tag) {
              const node = {
                tagName: String(tag || "").toUpperCase(),
                children: [],
                dataset: {},
                className: "",
                title: "",
                attributes: {},
                appendChild(child) {
                  this.children.push(child);
                  return child;
                },
                replaceChildren(...items) {
                  this.children = [];
                  items.forEach((item) => this.appendChild(item));
                },
                setAttribute(name, value) {
                  this.attributes[name] = String(value);
                },
                querySelectorAll(selector) {
                  const matches = [];
                  const wanted = selector.toUpperCase();
                  function visit(item) {
                    if (item.tagName === wanted) matches.push(item);
                    (item.children || []).forEach(visit);
                  }
                  visit(this);
                  return matches;
                },
                _textContent: "",
              };
              Object.defineProperty(node, "textContent", {
                get() {
                  return this._textContent || this.children.map((child) => child.textContent || "").join("");
                },
                set(value) {
                  this._textContent = String(value ?? "");
                  this.children = [];
                },
              });
              return node;
            }

            const tbody = makeElement("tbody");
            const context = {
              window: {},
              document: { createElement: makeElement },
              console,
            };
            context.window = context;
            vm.createContext(context);
            vm.runInContext(source, context, { filename: tablePath });
            const module = context.window.__completedViewTableModule?.createCompletedTableModule({
              appendCells(row, values, classes) {
                values.forEach((value, index) => {
                  const cell = makeElement("td");
                  cell.textContent = value;
                  if (classes?.[index]) cell.className = classes[index];
                  row.appendChild(cell);
                });
              },
              byId(id) {
                return id === "completed-rows" ? tbody : null;
              },
              makeRowSelectable() {},
              updateTableStatusLegend() {},
              finalLibraryPromotionStatusText() {
                return "";
              },
            });
            if (!module?.renderCompletedTableRows) throw new Error("Completed table renderer is missing");

            module.renderCompletedTableRows({
              tbodyId: "completed-rows",
              legendId: "completed-table-legend",
              rows: [{
                row_key: "row-1",
                completed_at: "Jun 4 12:58 AM",
                lookup_title: "Legally Blonde (2001)",
                output_file: "Legally Blonde (2001).mkv",
                output_path: "D:/Outsource/Movies/Legally Blonde (2001)/Legally Blonde (2001).mkv",
                media_type: "Movie",
                route: "REMUX",
                output_exists: false,
              }],
              sourceRows: [],
              emptyMessage: "No rows",
              legendLabel: "Current output rows",
              rowLabel: "Current output row",
            });

            const row = tbody.children[0];
            const titleCell = row.children[2];
            const titleChildren = titleCell.children.map((child) => child.className);
            if (titleCell.textContent !== "Legally Blonde (2001)") {
              throw new Error(`Unexpected title cell text: ${titleCell.textContent}`);
            }
            if (titleChildren.includes("completed-title-meta")) {
              throw new Error(`Duplicate filename meta line rendered: ${titleChildren.join(",")}`);
            }
            if (!titleCell.title.includes("Legally Blonde (2001).mkv")) {
              throw new Error(`Expected full output path tooltip, got: ${titleCell.title}`);
            }

            module.renderCompletedTableRows({
              tbodyId: "completed-rows",
              legendId: "completed-table-legend",
              rows: [{
                row_key: "row-2",
                completed_at: "Jun 4 3:56 AM",
                lookup_title: "TV (Season 02)",
                output_file: "TV (Season 02).mkv",
                output_path: "D:/Outsource/TV/Serial Experiments Lain/Season 02/TV (Season 02).mkv",
                source_path: "D:/Source/TV/Serial Experiments Lain/Season 02/Serial Experiments Lain E01 Weird.mkv",
                relative_path: "Serial Experiments Lain/Season 02/Serial Experiments Lain E01 Weird.mkv",
                media_type: "TV",
                route: "REMUX",
                output_exists: false,
              }],
              sourceRows: [],
              emptyMessage: "No rows",
              legendLabel: "Current output rows",
              rowLabel: "Current output row",
            });

            const tvTitleCell = tbody.children[0].children[2];
            if (tvTitleCell.textContent !== "Serial Experiments Lain - S02E01 - Weird") {
              throw new Error(`TV title did not include season/episode detail: ${tvTitleCell.textContent}`);
            }
            if (tvTitleCell.textContent.includes(".mkv")) {
              throw new Error(`TV title leaked filename extension: ${tvTitleCell.textContent}`);
            }
          """
        )
        result = subprocess.run(
            [node, "-e", script],
            cwd=repo_root,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

