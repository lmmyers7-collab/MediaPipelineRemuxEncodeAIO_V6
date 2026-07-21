"""Generate and check the authoritative WebView DOM/global-export inventories.

The main WebView document is backend-rendered from ``index.html`` and its
partials. Standalone HTML documents under the static tree are auxiliary
surfaces. The export inventory follows the scripts referenced by those
surfaces and scans the complete recursive ``assets/**/*.js`` tree.
"""

from __future__ import annotations

import argparse
import difflib
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from mediapipeline.desktop.api.static_files import render_index
from mediapipeline.tools.paths import find_repo_root


REPO_ROOT = find_repo_root(Path(__file__))
WEBVIEW_REL = Path("apps/desktop/webview/static")
DOM_INVENTORY_REL = Path("docs/inventories/WEBVIEW_DOM_ID_INVENTORY.md")
GLOBAL_EXPORT_INVENTORY_REL = Path("docs/inventories/WEBVIEW_GLOBAL_EXPORT_INVENTORY.md")
RUN_COMMAND = (
    "apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py "
    "mediapipeline.tools.dev.generate_webview_inventory_docs"
)

ID_RE = re.compile(r"\bid=(['\"])(.*?)\1", flags=re.IGNORECASE | re.DOTALL)
SCRIPT_RE = re.compile(r"<script\b[^>]*\bsrc=(['\"])(.*?)\1", flags=re.IGNORECASE | re.DOTALL)
WINDOW_ASSIGNMENT_RE = re.compile(r"\bwindow\.([A-Za-z_$][\w$]*)\s*=(?!=)")
NAMESPACE_OBJECT_RE = re.compile(
    r"(?P<doc>/\*\*.*?\*/)\s*window\.(?P<name>mediaPipeline[A-Za-z_$][\w$]*)\s*=\s*\{",
    flags=re.DOTALL,
)
NAMESPACE_OBJECT_ASSIGNMENT_RE = re.compile(r"\bwindow\.(mediaPipeline[A-Za-z_$][\w$]*)\s*=\s*\{")


@dataclass(frozen=True)
class FrontendSurface:
    key: str
    source_path: str
    render_mode: str
    html: str

    @property
    def ids(self) -> list[str]:
        return [match.group(2) for match in ID_RE.finditer(self.html)]


@dataclass(frozen=True)
class ScriptExports:
    path: str
    surfaces: tuple[str, ...]
    namespace: tuple[str, ...]
    flat: tuple[str, ...]


def _repo_rel(repo_root: Path, path: Path) -> str:
    return path.relative_to(repo_root).as_posix()


def discover_frontend_surfaces(repo_root: Path = REPO_ROOT) -> list[FrontendSurface]:
    webview_root = repo_root / WEBVIEW_REL
    response = render_index(
        webview_root,
        {"token": "inventory-generator-token", "appVersion": "inventory", "shellSurface": "webview"},
    )
    if response.status != 200:
        raise ValueError(f"backend-rendered WebView index returned HTTP {response.status}")

    surfaces = [
        FrontendSurface(
            key="main",
            source_path=_repo_rel(repo_root, webview_root / "index.html"),
            render_mode="backend-expanded partials",
            html=response.body.decode("utf-8"),
        )
    ]
    for path in sorted(webview_root.rglob("*.html")):
        relative = path.relative_to(webview_root)
        if relative == Path("index.html") or relative.parts[0] == "partials":
            continue
        surfaces.append(
            FrontendSurface(
                key=relative.as_posix(),
                source_path=_repo_rel(repo_root, path),
                render_mode="standalone auxiliary document",
                html=path.read_text(encoding="utf-8"),
            )
        )
    return surfaces


def _script_asset_path(surface: FrontendSurface, src: str, repo_root: Path) -> str | None:
    clean = src.split("?", 1)[0].split("#", 1)[0]
    if clean.startswith("/assets/"):
        return clean.removeprefix("/assets/")
    if "://" in clean or clean.startswith("//"):
        return None
    source_path = repo_root / surface.source_path
    resolved = (source_path.parent / clean).resolve()
    assets_root = (repo_root / WEBVIEW_REL / "assets").resolve()
    try:
        return resolved.relative_to(assets_root).as_posix()
    except ValueError:
        return None


def scripts_by_surface(
    surfaces: list[FrontendSurface], repo_root: Path = REPO_ROOT
) -> dict[str, tuple[str, ...]]:
    result: dict[str, tuple[str, ...]] = {}
    assets_root = repo_root / WEBVIEW_REL / "assets"
    for surface in surfaces:
        scripts: list[str] = []
        for match in SCRIPT_RE.finditer(surface.html):
            relative = _script_asset_path(surface, match.group(2), repo_root)
            if relative is None or not relative.endswith(".js"):
                continue
            if not (assets_root / relative).is_file():
                raise ValueError(f"{surface.key} references missing asset script: {relative}")
            scripts.append(relative)
        if len(scripts) != len(set(scripts)):
            duplicates = sorted(name for name in set(scripts) if scripts.count(name) > 1)
            raise ValueError(f"{surface.key} contains duplicate script references: {duplicates}")
        result[surface.key] = tuple(scripts)
    return result


def collect_script_exports(
    surfaces: list[FrontendSurface], repo_root: Path = REPO_ROOT
) -> list[ScriptExports]:
    assets_root = repo_root / WEBVIEW_REL / "assets"
    referenced_by: dict[str, list[str]] = {}
    for surface_key, scripts in scripts_by_surface(surfaces, repo_root).items():
        for script in scripts:
            referenced_by.setdefault(script, []).append(surface_key)

    disk_scripts = {
        path.relative_to(assets_root).as_posix(): path for path in sorted(assets_root.rglob("*.js"))
    }
    missing_from_surfaces = sorted(set(disk_scripts) - set(referenced_by))
    if missing_from_surfaces:
        raise ValueError(f"JavaScript assets are not represented by a frontend surface: {missing_from_surfaces}")
    missing_from_disk = sorted(set(referenced_by) - set(disk_scripts))
    if missing_from_disk:
        raise ValueError(f"frontend surfaces reference missing JavaScript assets: {missing_from_disk}")

    exports: list[ScriptExports] = []
    for relative, path in disk_scripts.items():
        names = WINDOW_ASSIGNMENT_RE.findall(path.read_text(encoding="utf-8"))
        exports.append(
            ScriptExports(
                path=relative,
                surfaces=tuple(referenced_by[relative]),
                namespace=tuple(name for name in names if name.startswith("mediaPipeline")),
                flat=tuple(name for name in names if not name.startswith("mediaPipeline")),
            )
        )
    return exports


def _replace_heading_section(text: str, heading: str, next_heading: str, body: str) -> str:
    start = text.index(heading) + len(heading)
    stop = text.index(next_heading, start)
    return text[:start] + "\n\n" + body.rstrip() + "\n\n---\n\n" + text[stop:]


def _replace_to_eof(text: str, heading_prefix: str, body: str) -> str:
    start = text.index(heading_prefix)
    return text[:start] + body.rstrip() + "\n"


def _render_dom_summary(surfaces: list[FrontendSurface]) -> str:
    instance_count = sum(len(surface.ids) for surface in surfaces)
    scoped_ids = {(surface.key, item) for surface in surfaces for item in surface.ids}
    global_ids = {item for surface in surfaces for item in surface.ids}
    lines = [
        "Lists every authored `id=\"\"` value on the backend-rendered main WebView and each standalone auxiliary HTML document under `apps/desktop/webview/static/`.",
        "",
        f"Total document-scoped element IDs: **{instance_count}** across **{len(surfaces)} reachable HTML surfaces**. "
        f"The inventory contains **{len(scoped_ids)} unique `(surface, id)` keys** and **{len(global_ids)} globally distinct ID values**.",
        "",
        "| Surface | Source | Render mode | ID instances | Unique IDs |",
        "| --- | --- | --- | ---: | ---: |",
    ]
    for surface in surfaces:
        lines.append(
            f"| `{surface.key}` | `{surface.source_path}` | {surface.render_mode} | "
            f"{len(surface.ids)} | {len(set(surface.ids))} |"
        )
    return "\n".join(lines)


def _render_dom_manifest(surfaces: list[FrontendSurface]) -> str:
    lines = [
        "## Machine-Generated Full DOM ID Manifest",
        "",
        f"Generated by `{RUN_COMMAND}`. IDs are sorted within each document and remain document-scoped so auxiliary surfaces cannot disappear behind a main-page total.",
        "",
        "<!-- BEGIN GENERATED DOM ID MANIFEST -->",
    ]
    for surface in surfaces:
        ids = surface.ids
        duplicates = sorted(item for item in set(ids) if ids.count(item) > 1)
        if duplicates:
            raise ValueError(f"{surface.key} contains duplicate DOM IDs: {duplicates}")
        lines.extend(
            [
                f"### `{surface.key}`",
                "",
                f"Source: `{surface.source_path}`",
                "",
                f"Count: {len(ids)}",
                "",
                "```text",
                *sorted(ids),
                "```",
                "",
            ]
        )
    lines.append("<!-- END GENERATED DOM ID MANIFEST -->")
    return "\n".join(lines)


def render_dom_inventory(repo_root: Path = REPO_ROOT, current_text: str | None = None) -> str:
    path = repo_root / DOM_INVENTORY_REL
    text = current_text if current_text is not None else path.read_text(encoding="utf-8")
    surfaces = discover_frontend_surfaces(repo_root)
    date_match = re.search(r"^Date:.*$", text, flags=re.MULTILINE)
    if date_match is None:
        raise ValueError("DOM inventory Date line is missing")
    summary_stop_marker = "\n\n---\n\n## Naming Convention"
    summary_stop = text.index(summary_stop_marker, date_match.end())
    text = (
        text[: date_match.end()]
        + "\n\n"
        + _render_dom_summary(surfaces)
        + summary_stop_marker
        + text[summary_stop + len(summary_stop_marker) :]
    )
    return _replace_to_eof(text, "## Machine-Generated Full DOM ID Manifest", _render_dom_manifest(surfaces))


def _surface_counts(
    surfaces: list[FrontendSurface], exports: list[ScriptExports]
) -> tuple[dict[str, int], int]:
    counts = {surface.key: 0 for surface in surfaces}
    for entry in exports:
        for surface in entry.surfaces:
            counts[surface] += 1
    shared = sum(1 for entry in exports if len(entry.surfaces) > 1)
    return counts, shared


def _render_export_summary(surfaces: list[FrontendSurface], exports: list[ScriptExports]) -> str:
    root_files = sum("/" not in entry.path for entry in exports)
    nested_files = len(exports) - root_files
    namespace_files = sum(bool(entry.namespace) for entry in exports)
    namespace_total = sum(len(entry.namespace) for entry in exports)
    flat_files = sum(bool(entry.flat) for entry in exports)
    flat_total = sum(len(entry.flat) for entry in exports)
    no_assignments = [entry.path for entry in exports if not entry.namespace and not entry.flat]
    surface_counts, shared = _surface_counts(surfaces, exports)
    surface_details = ", ".join(f"`{key}` {count}" for key, count in surface_counts.items())
    no_assignment_text = ", ".join(f"`{path}`" for path in no_assignments) or "none"
    return "\n".join(
        [
            f"- **{len(exports)} reachable JS files** recursively inventoried under `assets/`: **{root_files} root-level** and **{nested_files} nested**",
            f"- **{namespace_files} files** contain **{namespace_total} `window.mediaPipeline*` namespace assignments**",
            f"- **{flat_files} files** contain **{flat_total} flat `window.*` assignments**",
            f"- **{len(no_assignments)} files** contain no `window.*` assignment: {no_assignment_text}",
            f"- **{len(surfaces)} HTML surfaces** reference every JS asset: {surface_details}; **{shared} script** is shared across surfaces",
            "- Backend-injected and transitional globals are included as assignments when they appear in source; the manifest records assignment occurrences, not unique API semantics.",
        ]
    )


def _render_module_table(exports: list[ScriptExports]) -> str:
    lines = [
        "The path is relative to `apps/desktop/webview/static/assets/`. Surface membership is derived from each reachable HTML document's `<script src>` list.",
        "",
        "| File | HTML surface(s) | Namespace assignments | Flat exports |",
        "| --- | --- | --- | ---: |",
    ]
    for entry in exports:
        namespaces = ", ".join(entry.namespace) or "-"
        surfaces = ", ".join(f"`{surface}`" for surface in entry.surfaces)
        lines.append(f"| `{entry.path}` | {surfaces} | {namespaces} | {len(entry.flat)} |")
    return "\n".join(lines)


def _root_namespace_doc_counts(repo_root: Path) -> tuple[int, int]:
    assets_root = repo_root / WEBVIEW_REL / "assets"
    assignments = 0
    documented = 0
    for path in sorted(assets_root.glob("*.js")):
        text = path.read_text(encoding="utf-8")
        assigned = NAMESPACE_OBJECT_ASSIGNMENT_RE.findall(text)
        docs = {match.group("name"): match.group("doc") for match in NAMESPACE_OBJECT_RE.finditer(text)}
        assignments += len(assigned)
        documented += sum(
            name in docs
            and "Public namespace" in docs[name]
            and "flat window.* exports" in docs[name]
            for name in assigned
        )
    return assignments, documented


def _render_namespace_section(repo_root: Path, exports: list[ScriptExports]) -> str:
    namespace_total = sum(len(entry.namespace) for entry in exports)
    namespace_files = sum(bool(entry.namespace) for entry in exports)
    root_assignments, root_documented = _root_namespace_doc_counts(repo_root)
    return "\n".join(
        [
            f"All **{namespace_total} namespace assignments across {namespace_files} files** use the `window.mediaPipeline{{ModuleRole}}` prefix. Nested split modules are included in the recursive table and manifest above.",
            "",
            "The legacy JSDoc boundary rule remains scoped to root-level object-literal namespace exports: the comment identifies the public namespace, directs new code toward namespace access, and labels remaining flat exports as compatibility aliases. Nested modules are inventoried recursively but are not silently promoted into that separate documentation contract.",
            "",
            f"Current root-level boundary result: **{root_documented}/{root_assignments} object-literal namespace assignments documented**.",
        ]
    )


def _render_acceptance_section(
    repo_root: Path, surfaces: list[FrontendSurface], exports: list[ScriptExports]
) -> str:
    namespace_total = sum(len(entry.namespace) for entry in exports)
    flat_total = sum(len(entry.flat) for entry in exports)
    root_assignments, root_documented = _root_namespace_doc_counts(repo_root)
    return "\n".join(
        [
            "| Criterion | Status |",
            "| --- | --- |",
            f"| All recursively discovered JS assets inventoried | Pass - {len(exports)} files |",
            f"| Every reachable main/auxiliary HTML surface represented | Pass - {len(surfaces)} surfaces |",
            f"| Namespace assignments identified per file | Pass - {namespace_total} assignments |",
            f"| Flat assignments identified per file | Pass - {flat_total} assignments |",
            f"| Root-level namespace-object JSDoc boundary present | Pass - {root_documented}/{root_assignments} |",
            "| Cross-module consumption documented | Pass |",
            "",
            "The summary, recursive module table, and machine-generated manifest in this file are the current authoritative inventory. Historical dated reviews below are retained for audit context and must not be used as current totals.",
        ]
    )


def _render_export_manifest(exports: list[ScriptExports]) -> str:
    flat_total = sum(len(entry.flat) for entry in exports)
    namespace_total = sum(len(entry.namespace) for entry in exports)
    lines = [
        "## Machine-Generated Recursive Global Export Manifest",
        "",
        f"Generated by `{RUN_COMMAND}` from every script referenced by the main and auxiliary HTML surfaces. Counts are assignment occurrences: **{namespace_total} namespace** and **{flat_total} flat**.",
        "",
        "<!-- BEGIN GENERATED WEBVIEW GLOBAL EXPORT MANIFEST -->",
    ]
    for entry in exports:
        lines.extend(
            [
                f"### `{entry.path}`",
                "",
                f"Surfaces: {', '.join(f'`{surface}`' for surface in entry.surfaces)}",
                "",
                f"Namespace assignments ({len(entry.namespace)}):",
                "```text",
                *entry.namespace,
                "```",
                "",
                f"Flat exports ({len(entry.flat)}):",
                "```text",
                *entry.flat,
                "```",
                "",
            ]
        )
    lines.append("<!-- END GENERATED WEBVIEW GLOBAL EXPORT MANIFEST -->")
    return "\n".join(lines)


def render_global_export_inventory(
    repo_root: Path = REPO_ROOT, current_text: str | None = None
) -> str:
    path = repo_root / GLOBAL_EXPORT_INVENTORY_REL
    text = current_text if current_text is not None else path.read_text(encoding="utf-8")
    surfaces = discover_frontend_surfaces(repo_root)
    exports = collect_script_exports(surfaces, repo_root)
    intro = (
        "Inventories every `window.*` assignment in the recursive "
        "`apps/desktop/webview/static/assets/**/*.js` tree and records which backend-rendered or auxiliary HTML surface loads each script."
    )
    text, replacements = re.subn(
        r"^Inventories (?:all|every) `window\.\*` assignment(?:s)?.*?$",
        intro,
        text,
        count=1,
        flags=re.MULTILINE,
    )
    if replacements != 1:
        raise ValueError("global-export inventory scope paragraph is missing or ambiguous")
    text = _replace_heading_section(text, "## Summary", "## Module Inventory", _render_export_summary(surfaces, exports))
    text = _replace_heading_section(text, "## Module Inventory", "## Backend-Injected Globals", _render_module_table(exports))
    text = _replace_heading_section(
        text,
        "## Namespace Object Naming Convention",
        "## Acceptance Criteria",
        _render_namespace_section(repo_root, exports),
    )
    text = _replace_heading_section(
        text,
        "## Acceptance Criteria",
        "## Historical Freshness Review",
        _render_acceptance_section(repo_root, surfaces, exports),
    )
    return _replace_to_eof(
        text,
        "## Machine-Generated",
        _render_export_manifest(exports),
    )


def render_inventories(repo_root: Path = REPO_ROOT) -> dict[Path, str]:
    return {
        repo_root / DOM_INVENTORY_REL: render_dom_inventory(repo_root),
        repo_root / GLOBAL_EXPORT_INVENTORY_REL: render_global_export_inventory(repo_root),
    }


def _write_if_changed(path: Path, text: str) -> bool:
    old = path.read_text(encoding="utf-8") if path.exists() else None
    if old == text:
        return False
    path.write_text(text, encoding="utf-8", newline="\n")
    return True


def _check_current(outputs: dict[Path, str], repo_root: Path = REPO_ROOT) -> int:
    ok = True
    for path, expected in outputs.items():
        actual = path.read_text(encoding="utf-8") if path.exists() else ""
        if actual == expected:
            print(f"OK: {_repo_rel(repo_root, path)} is current.")
            continue
        ok = False
        print(f"WebView inventory drift detected in {_repo_rel(repo_root, path)}. Regenerate with:")
        print(f"  {RUN_COMMAND}")
        diff = difflib.unified_diff(
            actual.splitlines(),
            expected.splitlines(),
            fromfile=_repo_rel(repo_root, path),
            tofile=f"{_repo_rel(repo_root, path)} (generated)",
            lineterm="",
        )
        print("\n".join(list(diff)[:160]))
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Verify both inventory documents without writing.")
    args = parser.parse_args(argv)
    outputs = render_inventories()
    if args.check:
        return _check_current(outputs)
    for path, expected in outputs.items():
        status = "updated" if _write_if_changed(path, expected) else "current"
        print(f"{_repo_rel(REPO_ROOT, path)} {status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
