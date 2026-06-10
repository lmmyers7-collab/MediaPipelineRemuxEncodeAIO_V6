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
              const classes = new Set();
              const node = {
                tagName: String(tag || "").toUpperCase(),
                children: [],
                dataset: {},
                className: "",
                classList: {
                  add(...names) {
                    names.forEach((name) => {
                      if (name) classes.add(String(name));
                    });
                    node.className = Array.from(classes).join(" ");
                  },
                  contains(name) {
                    return classes.has(String(name));
                  },
                },
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
            const state = { completedSizeColumnMode: "size" };
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
              state,
            });
            if (!module?.renderCompletedTableRows) throw new Error("Completed table renderer is missing");

            const movieRow = {
              row_key: "row-1",
              completed_at: "Jun 4 12:58 AM",
              lookup_title: "Legally Blonde (2001)",
              output_file: "Legally Blonde (2001).mkv",
              output_path: "D:/Outsource/Movies/Legally Blonde (2001)/Legally Blonde (2001).mkv",
              media_type: "Movie",
              route: "REMUX",
              output_exists: true,
              consistency_status: "Consistent",
              source_size_bytes: 4294967296,
              output_size_bytes: 2147483648,
              size_reduction_text: "-50.0%  (4.00 -> 2.00 GB)",
              bitrate_text: "9.5 Mbps",
              output_bitrate_text: "9.5 Mbps",
              source_bitrate_text: "19.1 Mbps",
              bitrate_threshold_text: "20 Mbps",
              bitrate_over_threshold: false,
              duration_seconds: 1800,
            };

            module.renderCompletedTableRows({
              tbodyId: "completed-rows",
              legendId: "completed-table-legend",
              rows: [movieRow],
              sourceRows: [],
              emptyMessage: "No rows",
              legendLabel: "Current output rows",
              rowLabel: "Current output row",
            });

            const row = tbody.children[0];
            if (row.children.length !== 8) {
              throw new Error(`Expected 8 completed table cells after state/health removal, got ${row.children.length}`);
            }
            const titleCell = row.children[1];
            const evidenceCell = row.children[4];
            const measureCell = row.children[5];
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
            if (evidenceCell.textContent !== "Current") {
              throw new Error(`Normal current evidence should only render placement chip text, got: ${evidenceCell.textContent}`);
            }
            if (measureCell.textContent !== "-50.0%  (4.00 -> 2.00 GB)") {
              throw new Error(`Size mode did not render size text: ${measureCell.textContent}`);
            }
            if (measureCell.dataset.measureMode !== "size") {
              throw new Error(`Size mode marker was not set: ${measureCell.dataset.measureMode}`);
            }
            if (row.textContent.includes("Healthy") || row.textContent.includes("Consistent")) {
              throw new Error(`Redundant health/consistency text rendered: ${row.textContent}`);
            }

            state.completedSizeColumnMode = "bitrate";
            module.renderCompletedTableRows({
              tbodyId: "completed-rows",
              legendId: "completed-table-legend",
              rows: [movieRow],
              sourceRows: [],
              emptyMessage: "No rows",
              legendLabel: "Current output rows",
              rowLabel: "Current output row",
            });
            const bitrateCell = tbody.children[0].children[5];
            if (bitrateCell.textContent !== "9.5 Mbps") {
              throw new Error(`Bitrate mode did not render bitrate text: ${bitrateCell.textContent}`);
            }
            if (bitrateCell.dataset.measureMode !== "bitrate") {
              throw new Error(`Bitrate mode marker was not set: ${bitrateCell.dataset.measureMode}`);
            }
            if (!bitrateCell.title.includes("Output bitrate: 9.5 Mbps") || !bitrateCell.title.includes("Threshold: 20 Mbps")) {
              throw new Error(`Bitrate tooltip omitted evidence: ${bitrateCell.title}`);
            }

            state.completedSizeColumnMode = "size";
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

            const tvTitleCell = tbody.children[0].children[1];
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

