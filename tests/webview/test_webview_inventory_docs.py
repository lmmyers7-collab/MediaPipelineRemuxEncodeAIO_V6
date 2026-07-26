from __future__ import annotations

import re
import unittest
from pathlib import Path

from mediapipeline.tools.dev import generate_webview_inventory_docs
from mediapipeline.tools.paths import find_repo_root


REPO_ROOT = find_repo_root(Path(__file__))
WEBVIEW_ROOT = REPO_ROOT / "apps" / "desktop" / "webview" / "static"
ASSETS_ROOT = WEBVIEW_ROOT / "assets"
DOM_INVENTORY = REPO_ROOT / "docs" / "inventories" / "WEBVIEW_DOM_ID_INVENTORY.md"
GLOBAL_EXPORT_INVENTORY = REPO_ROOT / "docs" / "inventories" / "WEBVIEW_GLOBAL_EXPORT_INVENTORY.md"

NAMESPACE_OBJECT_RE = re.compile(
    r"(?P<doc>/\*\*.*?\*/)\s*window\.(?P<name>mediaPipeline[A-Za-z_$][\w$]*)\s*=\s*\{",
    flags=re.DOTALL,
)
NAMESPACE_OBJECT_ASSIGNMENT_RE = re.compile(r"\bwindow\.(mediaPipeline[A-Za-z_$][\w$]*)\s*=\s*\{")


def _extract_block(text: str, begin: str, end: str) -> str:
    start = text.index(begin) + len(begin)
    stop = text.index(end, start)
    return text[start:stop]


def _lines(block: str) -> list[str]:
    return [line.strip() for line in block.splitlines() if line.strip()]


def _generated_dom_manifest(text: str) -> dict[str, dict[str, object]]:
    block = _extract_block(
        text,
        "<!-- BEGIN GENERATED DOM ID MANIFEST -->",
        "<!-- END GENERATED DOM ID MANIFEST -->",
    )
    manifest: dict[str, dict[str, object]] = {}
    section_re = re.compile(
        r"^### `(?P<surface>[^`]+)`\n\n"
        r"Source: `(?P<source>[^`]+)`\n\n"
        r"Count: (?P<count>\d+)\n\n"
        r"```text\n(?P<ids>.*?)```",
        flags=re.MULTILINE | re.DOTALL,
    )
    for match in section_re.finditer(block):
        ids = _lines(match.group("ids"))
        if int(match.group("count")) != len(ids):
            raise AssertionError(f"{match.group('surface')} manifest count does not match its ID block")
        manifest[match.group("surface")] = {
            "source": match.group("source"),
            "ids": ids,
        }
    return manifest


def _generated_export_manifest(text: str) -> dict[str, dict[str, object]]:
    block = _extract_block(
        text,
        "<!-- BEGIN GENERATED WEBVIEW GLOBAL EXPORT MANIFEST -->",
        "<!-- END GENERATED WEBVIEW GLOBAL EXPORT MANIFEST -->",
    )
    manifest: dict[str, dict[str, object]] = {}
    section_re = re.compile(
        r"^### `(?P<file>[^`]+)`\n\n"
        r"Surfaces: (?P<surfaces>[^\n]+)\n\n"
        r"Namespace assignments \((?P<namespace_count>\d+)\):\n"
        r"```text\n(?P<namespace>.*?)```\n\n"
        r"Flat exports \((?P<flat_count>\d+)\):\n"
        r"```text\n(?P<flat>.*?)```",
        flags=re.MULTILINE | re.DOTALL,
    )
    for match in section_re.finditer(block):
        namespace = _lines(match.group("namespace"))
        flat = _lines(match.group("flat"))
        if int(match.group("namespace_count")) != len(namespace):
            raise AssertionError(f"{match.group('file')} namespace count does not match its block")
        if int(match.group("flat_count")) != len(flat):
            raise AssertionError(f"{match.group('file')} flat count does not match its block")
        manifest[match.group("file")] = {
            "surfaces": re.findall(r"`([^`]+)`", match.group("surfaces")),
            "namespace": namespace,
            "flat": flat,
        }
    return manifest


class WebViewInventoryDocsTests(unittest.TestCase):
    def test_generated_inventory_documents_are_current(self) -> None:
        self.assertEqual(
            DOM_INVENTORY.read_text(encoding="utf-8"),
            generate_webview_inventory_docs.render_dom_inventory(REPO_ROOT),
        )
        self.assertEqual(
            GLOBAL_EXPORT_INVENTORY.read_text(encoding="utf-8"),
            generate_webview_inventory_docs.render_global_export_inventory(REPO_ROOT),
        )

    def test_dom_inventory_represents_every_main_and_auxiliary_surface(self) -> None:
        surfaces = generate_webview_inventory_docs.discover_frontend_surfaces(REPO_ROOT)
        manifest = _generated_dom_manifest(DOM_INVENTORY.read_text(encoding="utf-8"))
        expected = {
            surface.key: {"source": surface.source_path, "ids": sorted(surface.ids)}
            for surface in surfaces
        }

        self.assertEqual(manifest, expected)
        self.assertEqual(surfaces[0].key, "main")
        self.assertTrue(any(surface.render_mode == "standalone auxiliary document" for surface in surfaces))
        for surface in surfaces:
            with self.subTest(surface=surface.key):
                self.assertEqual(
                    len(surface.ids),
                    len(set(surface.ids)),
                    f"{surface.key} must not contain duplicate DOM IDs",
                )

    def test_dom_summary_count_drift_is_rewritten_by_generator(self) -> None:
        current = DOM_INVENTORY.read_text(encoding="utf-8")
        stale = re.sub(
            r"Total document-scoped element IDs: \*\*\d+\*\*",
            "Total document-scoped element IDs: **0**",
            current,
            count=1,
        )
        self.assertNotEqual(stale, current)
        self.assertEqual(generate_webview_inventory_docs.render_dom_inventory(REPO_ROOT, stale), current)

    def test_recursive_global_export_manifest_matches_every_reachable_script(self) -> None:
        surfaces = generate_webview_inventory_docs.discover_frontend_surfaces(REPO_ROOT)
        exports = generate_webview_inventory_docs.collect_script_exports(surfaces, REPO_ROOT)
        manifest = _generated_export_manifest(GLOBAL_EXPORT_INVENTORY.read_text(encoding="utf-8"))
        expected = {
            entry.path: {
                "surfaces": list(entry.surfaces),
                "namespace": list(entry.namespace),
                "flat": list(entry.flat),
            }
            for entry in exports
        }

        self.assertEqual(manifest, expected)
        self.assertEqual(
            set(manifest),
            {path.relative_to(ASSETS_ROOT).as_posix() for path in ASSETS_ROOT.rglob("*.js")},
        )
        self.assertTrue(any("/" in path for path in manifest), "nested asset scripts must be explicit")
        self.assertTrue(all(values["surfaces"] for values in manifest.values()))

    def test_global_export_summary_count_drift_is_rewritten_by_generator(self) -> None:
        current = GLOBAL_EXPORT_INVENTORY.read_text(encoding="utf-8")
        stale = re.sub(r"\*\*\d+ reachable JS files\*\*", "**0 reachable JS files**", current, count=1)
        self.assertNotEqual(stale, current)
        self.assertEqual(generate_webview_inventory_docs.render_global_export_inventory(REPO_ROOT, stale), current)

    def test_root_webview_namespace_object_exports_have_boundary_jsdoc(self) -> None:
        for script in sorted(ASSETS_ROOT.glob("*.js")):
            text = script.read_text(encoding="utf-8")
            namespace_assignments = NAMESPACE_OBJECT_ASSIGNMENT_RE.findall(text)
            documented = {
                match.group("name"): match.group("doc")
                for match in NAMESPACE_OBJECT_RE.finditer(text)
            }
            with self.subTest(script=script.name):
                self.assertEqual(
                    sorted(documented),
                    sorted(namespace_assignments),
                    f"{script.name} has undocumented root namespace object exports",
                )
                for name, doc in documented.items():
                    self.assertIn("Public namespace", doc, f"{script.name} {name} missing public namespace wording")
                    self.assertIn(
                        "flat window.* exports",
                        doc,
                        f"{script.name} {name} missing compatibility-export boundary",
                    )

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
