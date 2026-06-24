from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.desktop.api.static_files import render_index

REPO_ROOT = find_repo_root(Path(__file__))
WEBVIEW_ROOT = REPO_ROOT / "apps" / "desktop" / "webview" / "static"
INDEX_HTML = WEBVIEW_ROOT / "index.html"
ASSETS_ROOT = WEBVIEW_ROOT / "assets"
DOM_INVENTORY = REPO_ROOT / "docs" / "inventories" / "WEBVIEW_DOM_ID_INVENTORY.md"
GLOBAL_EXPORT_INVENTORY = REPO_ROOT / "docs" / "inventories" / "WEBVIEW_GLOBAL_EXPORT_INVENTORY.md"

WINDOW_ASSIGNMENT_RE = re.compile(r"\bwindow\.([A-Za-z_$][\w$]*)\s*=(?!=)")
NAMESPACE_OBJECT_RE = re.compile(
    r"(?P<doc>/\*\*.*?\*/)\s*window\.(?P<name>mediaPipeline[A-Za-z_$][\w$]*)\s*=\s*\{",
    flags=re.DOTALL,
)
NAMESPACE_OBJECT_ASSIGNMENT_RE = re.compile(r"\bwindow\.(mediaPipeline[A-Za-z_$][\w$]*)\s*=\s*\{")


def _extract_block(text: str, begin: str, end: str) -> str:
    start = text.index(begin) + len(begin)
    stop = text.index(end, start)
    return text[start:stop]


def _manifest_lines(text: str, begin: str, end: str) -> list[str]:
    block = _extract_block(text, begin, end)
    return [
        line.strip()
        for line in block.splitlines()
        if line.strip() and not line.strip().startswith("```")
    ]


def _dom_ids_from_html() -> list[str]:
    response = render_index(
        WEBVIEW_ROOT,
        {"token": "inventory-test-token", "appVersion": "v5-test", "shellSurface": "webview"},
    )
    if response.status != 200:
        raise AssertionError(f"index render failed with status {response.status}: {response.body!r}")
    text = response.body.decode("utf-8")
    return [match.group(2) for match in re.finditer(r"\bid=(['\"])(.*?)\1", text)]


def _window_exports_by_file() -> dict[str, dict[str, list[str]]]:
    exports: dict[str, dict[str, list[str]]] = {}
    for script in sorted(ASSETS_ROOT.glob("*.js")):
        names = WINDOW_ASSIGNMENT_RE.findall(script.read_text(encoding="utf-8"))
        exports[script.name] = {
            "namespace": [name for name in names if name.startswith("mediaPipeline")],
            "flat": [name for name in names if not name.startswith("mediaPipeline")],
        }
    return exports


def _namespace_object_docs_by_file() -> dict[str, dict[str, str]]:
    docs: dict[str, dict[str, str]] = {}
    for script in sorted(ASSETS_ROOT.glob("*.js")):
        text = script.read_text(encoding="utf-8")
        docs[script.name] = {
            match.group("name"): match.group("doc")
            for match in NAMESPACE_OBJECT_RE.finditer(text)
        }
    return docs


def _module_table_flat_counts(text: str) -> dict[str, int]:
    table = _extract_block(text, "## Module Inventory", "---\n\n## Backend-Injected Globals")
    counts: dict[str, int] = {}
    for line in table.splitlines():
        if not line.startswith("| `"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 4 or not cells[0].endswith(".js`"):
            continue
        counts[cells[0].strip("`")] = int(cells[2])
    return counts


def _generated_export_manifest(text: str) -> dict[str, dict[str, list[str]]]:
    block = _extract_block(
        text,
        "<!-- BEGIN GENERATED WEBVIEW GLOBAL EXPORT MANIFEST -->",
        "<!-- END GENERATED WEBVIEW GLOBAL EXPORT MANIFEST -->",
    )
    manifest: dict[str, dict[str, list[str]]] = {}
    section_re = re.compile(
        r"^### (?P<file>[^\n]+)\n\n"
        r"Namespace objects: (?P<namespace>[^\n]*)\n\n"
        r"Flat exports \((?P<count>\d+)\):\n"
        r"```text\n(?P<flat>.*?)```",
        flags=re.MULTILINE | re.DOTALL,
    )
    for match in section_re.finditer(block):
        namespace_text = match.group("namespace").strip()
        flat_exports = [
            line.strip()
            for line in match.group("flat").splitlines()
            if line.strip()
        ]
        manifest[match.group("file").strip()] = {
            "namespace": [] if namespace_text == "none" else [item.strip() for item in namespace_text.split(",")],
            "flat": flat_exports,
        }
        assert int(match.group("count")) == len(flat_exports)
    return manifest


class WebViewInventoryDocsTests(unittest.TestCase):
    def test_dom_inventory_manifest_matches_index_html(self) -> None:
        ids = _dom_ids_from_html()
        unique_ids = sorted(set(ids))
        doc = DOM_INVENTORY.read_text(encoding="utf-8")
        header_count = int(re.search(r"Total unique element IDs:\s*(\d+)", doc).group(1))
        manifest_count = int(re.search(r"Machine-Generated Full DOM ID Manifest.*?\nCount:\s*(\d+)", doc, flags=re.DOTALL).group(1))
        manifest_ids = _manifest_lines(
            doc,
            "<!-- BEGIN GENERATED DOM ID MANIFEST -->",
            "<!-- END GENERATED DOM ID MANIFEST -->",
        )

        self.assertEqual(len(ids), len(unique_ids), "index.html must not contain duplicate DOM IDs")
        self.assertEqual(header_count, len(unique_ids))
        self.assertEqual(manifest_count, len(unique_ids))
        self.assertEqual(manifest_ids, unique_ids)

    def test_global_export_inventory_summary_and_table_match_assets(self) -> None:
        exports = _window_exports_by_file()
        doc = GLOBAL_EXPORT_INVENTORY.read_text(encoding="utf-8")
        table_counts = _module_table_flat_counts(doc)
        expected_counts = {file_name: len(values["flat"]) for file_name, values in exports.items()}
        namespace_files = sum(1 for values in exports.values() if values["namespace"])
        flat_files = sum(1 for values in exports.values() if values["flat"])
        flat_total = sum(expected_counts.values())

        self.assertEqual(table_counts, expected_counts)
        self.assertIn(f"**{len(exports)} JS files** total in `assets/`", doc)
        self.assertIn(f"**{namespace_files} files** export a primary namespace object", doc)
        self.assertIn(f"**{flat_files} files** also export flat functions directly onto `window`", doc)
        self.assertIn(f"**Flat export total:** {flat_total}", doc)

    def test_generated_global_export_manifest_matches_assets(self) -> None:
        exports = _window_exports_by_file()
        doc = GLOBAL_EXPORT_INVENTORY.read_text(encoding="utf-8")
        manifest = _generated_export_manifest(doc)
        expected = {
            file_name: {
                "namespace": values["namespace"],
                "flat": values["flat"],
            }
            for file_name, values in exports.items()
        }

        self.assertEqual(manifest, expected)
        self.assertNotIn("Latest addendum:", doc)
        self.assertIn("Historical dated reviews below are retained for audit context", doc)

    def test_webview_namespace_object_exports_have_boundary_jsdoc(self) -> None:
        documented = _namespace_object_docs_by_file()
        for script in sorted(ASSETS_ROOT.glob("*.js")):
            text = script.read_text(encoding="utf-8")
            namespace_assignments = NAMESPACE_OBJECT_ASSIGNMENT_RE.findall(text)
            with self.subTest(script=script.name):
                self.assertEqual(
                    sorted(documented.get(script.name, {})),
                    sorted(namespace_assignments),
                    f"{script.name} has undocumented mediaPipeline namespace object exports",
                )
                for name, doc in documented.get(script.name, {}).items():
                    self.assertIn("Public namespace", doc, f"{script.name} {name} missing public namespace wording")
                    self.assertIn("flat window.* exports", doc, f"{script.name} {name} missing compatibility-export boundary")

    def test_queue_scan_helpers_are_namespace_only(self) -> None:
        source = (ASSETS_ROOT / "queueView.js").read_text(encoding="utf-8")
        match = re.search(r"window\.mediaPipelineQueueView\s*=\s*\{(?P<body>.*?)\n  \};", source, flags=re.DOTALL)
        self.assertIsNotNone(match)
        namespace_body = match.group("body") if match else ""
        namespace_only_helpers = [
            "requestQueueScan",
            "queueScanIsRunning",
            "queueScanStatusLines",
            "queueSourceInventoryLines",
            "renderQueueScanArtifacts",
        ]

        for helper in namespace_only_helpers:
            with self.subTest(helper=helper):
                self.assertIn(f"    {helper},", namespace_body)
                self.assertNotIn(f"window.{helper} =", source)


if __name__ == "__main__":
    unittest.main()
