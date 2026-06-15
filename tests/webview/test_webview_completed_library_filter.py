from __future__ import annotations

import json
import shutil
import subprocess
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FILTERS_ASSET = ROOT / "apps" / "desktop" / "webview" / "static" / "assets" / "completed" / "filters.js"


class WebViewCompletedLibraryFilterTests(unittest.TestCase):
    def test_completed_library_filter_falls_back_to_movie_tv_media_kind(self) -> None:
        node = shutil.which("node")
        if not node:
            raise unittest.SkipTest("Node.js is required for the Completed library filter smoke.")

        script = textwrap.dedent(
            f"""
            const fs = require("fs");
            const vm = require("vm");

            const source = fs.readFileSync({json.dumps(str(FILTERS_ASSET))}, "utf8");
            const context = {{
              window: {{}},
              document: {{}},
              console,
            }};
            vm.createContext(context);
            vm.runInContext(source, context, {{ filename: "completed/filters.js" }});

            const select = {{
              value: "all",
              children: [],
              ownerDocument: {{
                createElement(tag) {{
                  return {{
                    tagName: String(tag || "").toUpperCase(),
                    value: "",
                    textContent: "",
                  }};
                }},
              }},
              replaceChildren(...children) {{
                this.children = children;
              }},
            }};

            const module = context.window.__completedViewFiltersModule.createCompletedFiltersModule({{
              byId(id) {{ return id === "completed-library-filter" ? select : null; }},
              filterRows(rows) {{ return rows; }},
              state: {{}},
            }});

            const rows = [
              {{
                row_key: "movie-row",
                media_type: "movie",
                output_exists: true,
              }},
              {{
                row_key: "tv-row",
                media_kind: "episode",
                media_type: "episode",
                output_exists: true,
              }},
              {{
                row_key: "anime-row",
                library_id: "anime",
                library_name: "Anime Library",
                media_type: "tv",
                output_exists: true,
              }},
            ];

            module.syncCompletedLibraryFilterOptions(rows);
            const labels = select.children.map((option) => option.textContent);
            if (!labels.includes("Movie") || !labels.includes("TV") || !labels.includes("Anime Library")) {{
              throw new Error(`expected Movie, TV, and Anime Library options; got ${{labels.join(", ")}}`);
            }}
            if (labels.includes("Unknown library")) {{
              throw new Error(`did not expect Unknown library with media kind evidence; got ${{labels.join(", ")}}`);
            }}

            const tvOption = select.children.find((option) => option.textContent === "TV");
            select.value = tvOption.value;
            const tvRows = module.completedFilteredRows(rows, "", "all", "all", select.value);
            if (tvRows.length !== 1 || tvRows[0].row_key !== "tv-row") {{
              throw new Error(`expected only tv-row for TV fallback filter; got ${{tvRows.map((row) => row.row_key).join(",")}}`);
            }}
            if (module.completedLibraryFilterLabel(select.value) !== "TV") {{
              throw new Error("TV fallback filter label was not preserved");
            }}

            const animeOption = select.children.find((option) => option.textContent === "Anime Library");
            select.value = animeOption.value;
            const animeRows = module.completedFilteredRows(rows, "", "all", "all", select.value);
            if (animeRows.length !== 1 || animeRows[0].row_key !== "anime-row") {{
              throw new Error(`explicit library identity should win over media type; got ${{animeRows.map((row) => row.row_key).join(",")}}`);
            }}

            console.log(JSON.stringify({{ ok: true, labels }}));
            """
        )

        result = subprocess.run(
            [node, "-e", script],
            text=True,
            capture_output=True,
            timeout=30,
            check=False,
        )
        if result.returncode != 0:
            raise AssertionError(
                "Completed library filter smoke failed.\n"
                f"stdout:\n{result.stdout}\n"
                f"stderr:\n{result.stderr}"
            )

        self.assertTrue(json.loads(result.stdout.strip().splitlines()[-1])["ok"])


if __name__ == "__main__":
    unittest.main()
