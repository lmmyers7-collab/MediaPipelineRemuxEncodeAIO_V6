"""Generate a readable Python dependency atlas for current navigation.

The atlas intentionally avoids raw module-level output as the first view.
It parses local imports with `ast`, groups modules into package/domain nodes,
renders a major-edge overview with Graphviz, and writes drill-down diagrams
plus CSV exports under `docs/generated/dependency-atlas/assets/`.
"""

from __future__ import annotations

import argparse
import ast
import csv
import html
import shutil
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

SOURCE_ROOT = Path(__file__).resolve().parents[3]
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from mediapipeline.tools.paths import find_repo_root
from typing import Iterable

REPO_ROOT = find_repo_root(Path(__file__))

DEFAULT_PACKAGE_ROOTS = (
    ("mediapipeline.core", REPO_ROOT / "src" / "mediapipeline" / "core"),
    ("mediapipeline.contracts", REPO_ROOT / "src" / "mediapipeline" / "contracts"),
    ("mediapipeline.desktop", REPO_ROOT / "src" / "mediapipeline" / "desktop"),
    ("mediapipeline.pipeline", REPO_ROOT / "src" / "mediapipeline" / "pipeline"),
    ("mediapipeline.tools", REPO_ROOT / "src" / "mediapipeline" / "tools"),
)

ROOT_OUTPUT_PREFIX = "docs/generated/dependency-atlas"
OUTPUT_STEM = "dependency-atlas"
OUTPUT_ROOT = REPO_ROOT / ROOT_OUTPUT_PREFIX
ROOT_HTML = OUTPUT_ROOT / f"{OUTPUT_STEM}.html"
ROOT_PNG = OUTPUT_ROOT / f"{OUTPUT_STEM}.png"
ROOT_SVG = OUTPUT_ROOT / f"{OUTPUT_STEM}.svg"
ROOT_DOT = OUTPUT_ROOT / f"{OUTPUT_STEM}.dot"
ASSET_ROOT = OUTPUT_ROOT / "assets"
LEGACY_ASSET_ROOT = REPO_ROOT / f"{ROOT_OUTPUT_PREFIX}_assets"

SUMMARY_CSV = ASSET_ROOT / "dependency_summary.csv"
DOMAIN_EDGE_CSV = ASSET_ROOT / "dependency_edges.csv"
MODULE_EDGE_CSV = ASSET_ROOT / "dependency_module_edges.csv"

GRAPHVIZ_FALLBACKS = (
    Path(r"C:\Program Files\Graphviz\bin\dot.exe"),
    Path(r"C:\Program Files (x86)\Graphviz\bin\dot.exe"),
)


@dataclass(frozen=True)
class ModuleIndex:
    module_paths: dict[str, Path]
    path_modules: dict[Path, str]
    package_names: set[str]


@dataclass(frozen=True)
class AtlasData:
    module_index: ModuleIndex
    module_edges: Counter[tuple[str, str]]
    category_files: dict[str, list[str]]
    category_edges: Counter[tuple[str, str]]
    incoming_edges: Counter[str]
    outgoing_edges: Counter[str]
    internal_edges: Counter[str]
    parse_errors: list[tuple[str, str]]


@dataclass(frozen=True)
class DetailRecord:
    category: str
    svg_path: Path
    png_path: Path
    node_count: int
    edge_count: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate docs/generated/dependency-atlas HTML, images, and CSV exports."
    )
    parser.add_argument(
        "--min-overview-edge-count",
        type=int,
        default=4,
        help="Minimum source-module count for a cross-domain edge in the root overview.",
    )
    parser.add_argument(
        "--min-overview-files",
        type=int,
        default=12,
        help="Keep domains with at least this many files in the root overview.",
    )
    parser.add_argument(
        "--dot",
        type=Path,
        default=None,
        help="Path to Graphviz dot.exe. Defaults to PATH, then common Windows install paths.",
    )
    return parser.parse_args()


def display_path(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def slug(text: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in text).strip("_") or "root"


def dot_quote(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'


def resolve_dot(explicit_path: Path | None) -> Path:
    if explicit_path is not None:
        if explicit_path.exists():
            return explicit_path
        raise FileNotFoundError(f"Graphviz dot not found at {explicit_path}")

    path_dot = shutil.which("dot")
    if path_dot:
        return Path(path_dot)

    for candidate in GRAPHVIZ_FALLBACKS:
        if candidate.exists():
            return candidate

    raise FileNotFoundError(
        "Graphviz dot was not found. Install Graphviz or pass --dot C:\\path\\to\\dot.exe."
    )


def clean_outputs() -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    ASSET_ROOT.mkdir(parents=True, exist_ok=True)
    for pattern in (
        "*dependency_detail_*.dot",
        "*dependency_detail_*.png",
        "*dependency_detail_*.svg",
        "dependency_*.csv",
    ):
        for path in ASSET_ROOT.glob(pattern):
            path.unlink(missing_ok=True)
    for path in (ROOT_HTML, ROOT_PNG, ROOT_SVG, ROOT_DOT):
        path.unlink(missing_ok=True)
    nested_legacy_root = OUTPUT_ROOT / "docs"
    if nested_legacy_root.exists() and nested_legacy_root.is_dir():
        resolved_nested = nested_legacy_root.resolve()
        if resolved_nested.parent != OUTPUT_ROOT.resolve():
            raise RuntimeError(f"Refusing to remove unexpected nested atlas output path: {resolved_nested}")
        shutil.rmtree(nested_legacy_root)
    for path in (
        REPO_ROOT / f"{ROOT_OUTPUT_PREFIX}.html",
        REPO_ROOT / f"{ROOT_OUTPUT_PREFIX}.png",
        REPO_ROOT / f"{ROOT_OUTPUT_PREFIX}.svg",
        REPO_ROOT / f"{ROOT_OUTPUT_PREFIX}.dot",
    ):
        path.unlink(missing_ok=True)
    if LEGACY_ASSET_ROOT.exists() and LEGACY_ASSET_ROOT.is_dir():
        legacy_asset_root = LEGACY_ASSET_ROOT.resolve()
        if legacy_asset_root.parent != REPO_ROOT.resolve():
            raise RuntimeError(f"Refusing to remove unexpected atlas asset path: {legacy_asset_root}")
        shutil.rmtree(legacy_asset_root)

    # Remove earlier one-off dependency graph names from the manual setup pass.
    for stale_pattern in (
        "*python_dependencies.png",
        "*python_dependencies.svg",
        "*dependency_domains.png",
        "*dependency_domains.svg",
    ):
        for path in REPO_ROOT.glob(stale_pattern):
            path.unlink(missing_ok=True)


def iter_python_modules(package_roots: Iterable[tuple[str, Path]]) -> ModuleIndex:
    module_paths: dict[str, Path] = {}
    path_modules: dict[Path, str] = {}
    package_names: set[str] = set()

    for package_name, package_root in package_roots:
        package_names.add(package_name.split(".", maxsplit=1)[0])
        if not package_root.exists():
            continue
        for path in package_root.rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            relative = path.relative_to(package_root)
            parts = list(relative.parts)
            parts[-1] = parts[-1][:-3]
            if parts[-1] == "__init__":
                parts = parts[:-1]
            module_name = ".".join([package_name] + parts) if parts else package_name
            module_paths[module_name] = path
            path_modules[path] = module_name

    return ModuleIndex(
        module_paths=module_paths,
        path_modules=path_modules,
        package_names=package_names,
    )


def resolve_local_module(name: str, index: ModuleIndex) -> str | None:
    if not name:
        return None
    parts = name.split(".")
    if not parts or parts[0] not in index.package_names:
        return None
    for stop in range(len(parts), 0, -1):
        candidate = ".".join(parts[:stop])
        if candidate in index.module_paths:
            return candidate
    return None


def current_package_parts(module_name: str, path: Path) -> list[str]:
    parts = module_name.split(".")
    if path.name == "__init__.py":
        return parts
    return parts[:-1]


def import_targets(tree: ast.AST, source_module: str, source_path: Path, index: ModuleIndex) -> set[str]:
    targets: set[str] = set()
    package_parts = current_package_parts(source_module, source_path)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                resolved = resolve_local_module(alias.name, index)
                if resolved and resolved != source_module:
                    targets.add(resolved)
            continue

        if not isinstance(node, ast.ImportFrom):
            continue

        if node.level:
            keep = len(package_parts) - (node.level - 1)
            if keep < 0:
                continue
            base_parts = package_parts[:keep]
            if node.module:
                base_parts += node.module.split(".")
        else:
            if not node.module:
                continue
            base_parts = node.module.split(".")

        base_name = ".".join(base_parts)
        base_resolved = resolve_local_module(base_name, index)
        for alias in node.names:
            if alias.name == "*":
                resolved = base_resolved
            else:
                candidate = ".".join(base_parts + [alias.name])
                resolved = resolve_local_module(candidate, index) or base_resolved
            if resolved and resolved != source_module:
                targets.add(resolved)

    return targets


def category_for_module(module_name: str) -> str:
    parts = module_name.split(".")
    if parts[:2] == ["mediapipeline", "core"]:
        return "core/" + (parts[2] if len(parts) > 2 else "root")
    if parts[:2] == ["mediapipeline", "contracts"]:
        return "contracts/" + (parts[2] if len(parts) > 2 else "root")
    if parts[:2] == ["mediapipeline", "desktop"]:
        return "desktop/" + (parts[2] if len(parts) > 2 else "root")
    if parts[:2] == ["mediapipeline", "pipeline"]:
        return "pipeline/" + (parts[2] if len(parts) > 2 else "root")
    if parts[:2] == ["mediapipeline", "tools"]:
        return "tools/" + (parts[2] if len(parts) > 2 else "root")
    return parts[0]


def module_label(module_name: str, index: ModuleIndex) -> str:
    path = index.module_paths[module_name]
    package_roots = {
        "mediapipeline.core": REPO_ROOT / "src" / "mediapipeline" / "core",
        "mediapipeline.contracts": REPO_ROOT / "src" / "mediapipeline" / "contracts",
        "mediapipeline.desktop": REPO_ROOT / "src" / "mediapipeline" / "desktop",
        "mediapipeline.pipeline": REPO_ROOT / "src" / "mediapipeline" / "pipeline",
        "mediapipeline.tools": REPO_ROOT / "src" / "mediapipeline" / "tools",
    }
    for package_name, package_root in package_roots.items():
        if module_name == package_name or module_name.startswith(package_name + "."):
            return path.relative_to(package_root).as_posix()
    return display_path(path)


def collect_data(package_roots: Iterable[tuple[str, Path]]) -> AtlasData:
    index = iter_python_modules(package_roots)
    module_edges: Counter[tuple[str, str]] = Counter()
    parse_errors: list[tuple[str, str]] = []

    for path, source_module in sorted(index.path_modules.items(), key=lambda item: item[1]):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except Exception as exc:  # pragma: no cover - rare malformed source reporting
            parse_errors.append((display_path(path), str(exc)))
            continue
        for target in import_targets(tree, source_module, path, index):
            module_edges[(source_module, target)] += 1

    category_files: defaultdict[str, list[str]] = defaultdict(list)
    for module_name in sorted(index.module_paths):
        category_files[category_for_module(module_name)].append(module_name)

    category_edges: Counter[tuple[str, str]] = Counter()
    incoming_edges: Counter[str] = Counter()
    outgoing_edges: Counter[str] = Counter()
    internal_edges: Counter[str] = Counter()

    for source, target in module_edges:
        source_category = category_for_module(source)
        target_category = category_for_module(target)
        if source_category == target_category:
            internal_edges[source_category] += 1
            continue
        category_edges[(source_category, target_category)] += 1
        outgoing_edges[source_category] += 1
        incoming_edges[target_category] += 1

    return AtlasData(
        module_index=index,
        module_edges=module_edges,
        category_files=dict(category_files),
        category_edges=category_edges,
        incoming_edges=incoming_edges,
        outgoing_edges=outgoing_edges,
        internal_edges=internal_edges,
        parse_errors=parse_errors,
    )


def run_dot(dot_path: Path, source_dot: Path, output_path: Path, output_type: str) -> None:
    subprocess.run(
        [str(dot_path), f"-T{output_type}", str(source_dot), "-o", str(output_path)],
        check=True,
    )


def render_overview_dot(data: AtlasData, min_edge_count: int, min_files: int) -> str:
    major_edges = {
        edge: count for edge, count in data.category_edges.items() if count >= min_edge_count
    }
    major_nodes = {category for edge in major_edges for category in edge}
    major_nodes.update(
        category
        for category, modules in data.category_files.items()
        if len(modules) >= min_files
    )

    lines = [
        "digraph G {",
        '  graph [rankdir=LR, bgcolor="white", overlap=false, splines=polyline, '
        'concentrate=true, nodesep=0.5, ranksep=1.0, pad=0.2];',
        '  node [shape=box, style="rounded,filled", fontname="Segoe UI", fontsize=15, '
        'margin="0.11,0.07", penwidth=1.2, color="#334155", fontcolor="#111827"];',
        '  edge [fontname="Segoe UI", fontsize=10, color="#64748b", '
        'fontcolor="#475569", arrowsize=0.75, penwidth=1.1];',
        f'  label="Python dependency atlas: major package/domain edges '
        f'({min_edge_count}+ source modules)"; labelloc=t; fontsize=22; fontname="Segoe UI";',
    ]

    for category in sorted(major_nodes):
        fill = "#dbeafe" if category.startswith("core/") else "#dcfce7"
        label = (
            f"{category}\n{len(data.category_files[category])} files\n"
            f"out {data.outgoing_edges[category]} / in {data.incoming_edges[category]}"
        )
        lines.append(
            f"  {dot_quote(slug(category))} "
            f"[label={dot_quote(label)}, fillcolor={dot_quote(fill)}];"
        )

    for (source, target), count in sorted(major_edges.items(), key=lambda item: (-item[1], item[0])):
        penwidth = min(6.0, 1.1 + count / 2.5)
        lines.append(
            f"  {dot_quote(slug(source))} -> {dot_quote(slug(target))} "
            f"[label={dot_quote(str(count))}, penwidth={penwidth:.2f}];"
        )

    lines.append("}")
    return "\n".join(lines) + "\n"


def write_overview_images(data: AtlasData, dot_path: Path, min_edge_count: int, min_files: int) -> None:
    source_dot = ROOT_DOT
    source_dot.write_text(
        render_overview_dot(data, min_edge_count=min_edge_count, min_files=min_files),
        encoding="utf-8",
    )
    run_dot(dot_path, source_dot, ROOT_PNG, "png")
    run_dot(dot_path, source_dot, ROOT_SVG, "svg")
    source_dot.unlink(missing_ok=True)


def write_csvs(data: AtlasData) -> None:
    with SUMMARY_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "category",
                "files",
                "internal_module_edges",
                "outgoing_domain_edges",
                "incoming_domain_edges",
            ]
        )
        for category in sorted(data.category_files, key=lambda item: (-len(data.category_files[item]), item)):
            writer.writerow(
                [
                    category,
                    len(data.category_files[category]),
                    data.internal_edges[category],
                    data.outgoing_edges[category],
                    data.incoming_edges[category],
                ]
            )

    with DOMAIN_EDGE_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "source_category",
                "target_category",
                "source_files_importing_target_category",
            ]
        )
        for (source, target), count in sorted(
            data.category_edges.items(), key=lambda item: (-item[1], item[0])
        ):
            writer.writerow([source, target, count])

    with MODULE_EDGE_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["source_module", "target_module", "source_path", "target_path"])
        for source, target in sorted(data.module_edges):
            writer.writerow(
                [
                    source,
                    target,
                    display_path(data.module_index.module_paths[source]),
                    display_path(data.module_index.module_paths[target]),
                ]
            )


def render_detail_dot(data: AtlasData, category: str) -> tuple[str, int, int]:
    focus_modules = set(data.category_files[category])
    used_focus_modules = set(focus_modules)
    external_categories: set[str] = set()
    internal_module_edges: Counter[tuple[str, str]] = Counter()
    outgoing_module_edges: Counter[tuple[str, str]] = Counter()
    incoming_module_edges: Counter[tuple[str, str]] = Counter()

    for (source, target), count in data.module_edges.items():
        source_category = category_for_module(source)
        target_category = category_for_module(target)
        if source_category == category and target_category == category:
            internal_module_edges[(source, target)] += count
            used_focus_modules.update((source, target))
        elif source_category == category:
            outgoing_module_edges[(source, target_category)] += count
            used_focus_modules.add(source)
            external_categories.add(target_category)
        elif target_category == category:
            incoming_module_edges[(source_category, target)] += count
            used_focus_modules.add(target)
            external_categories.add(source_category)

    lines = [
        "digraph G {",
        '  graph [rankdir=LR, bgcolor="white", overlap=false, splines=true, '
        'nodesep=0.35, ranksep=0.78, pad=0.2];',
        '  node [shape=box, style="rounded,filled", fontname="Segoe UI", fontsize=12, '
        'margin="0.09,0.06", penwidth=1.1, color="#334155", fontcolor="#111827"];',
        '  edge [fontname="Segoe UI", fontsize=9, arrowsize=0.65, penwidth=1.05];',
        f"  label={dot_quote(category + ' module detail')}; "
        'labelloc=t; fontsize=20; fontname="Segoe UI";',
        "  subgraph cluster_focus {",
        f"    label={dot_quote(category + ' modules')}; "
        'color="#93c5fd"; penwidth=1.2; style="rounded";',
    ]

    for module_name in sorted(used_focus_modules):
        lines.append(
            f"    {dot_quote(slug(module_name))} "
            f"[label={dot_quote(module_label(module_name, data.module_index))}, fillcolor=\"#eff6ff\"];"
        )
    lines.append("  }")

    for external_category in sorted(external_categories):
        fill = "#f8fafc" if external_category.startswith("core/") else "#f0fdf4"
        lines.append(
            f"  {dot_quote('external_' + slug(external_category))} "
            f"[label={dot_quote(external_category)}, shape=box, "
            f"style=\"rounded,dashed,filled\", fillcolor={dot_quote(fill)}, color=\"#64748b\"];"
        )

    for (source, target), count in sorted(
        internal_module_edges.items(),
        key=lambda item: (
            module_label(item[0][0], data.module_index),
            module_label(item[0][1], data.module_index),
        ),
    ):
        label = str(count) if count > 1 else ""
        lines.append(
            f"  {dot_quote(slug(source))} -> {dot_quote(slug(target))} "
            f"[label={dot_quote(label)}, color=\"#2563eb\", fontcolor=\"#1d4ed8\"];"
        )

    for (source, target_category), count in sorted(
        outgoing_module_edges.items(),
        key=lambda item: (module_label(item[0][0], data.module_index), item[0][1]),
    ):
        lines.append(
            f"  {dot_quote(slug(source))} -> {dot_quote('external_' + slug(target_category))} "
            f"[label={dot_quote(str(count))}, color=\"#9333ea\", fontcolor=\"#7e22ce\"];"
        )

    for (source_category, target), count in sorted(
        incoming_module_edges.items(),
        key=lambda item: (item[0][0], module_label(item[0][1], data.module_index)),
    ):
        lines.append(
            f"  {dot_quote('external_' + slug(source_category))} -> {dot_quote(slug(target))} "
            f"[label={dot_quote(str(count))}, color=\"#64748b\", "
            f"fontcolor=\"#475569\", style=\"dashed\"];"
        )

    lines.append("}")
    edge_count = len(internal_module_edges) + len(outgoing_module_edges) + len(incoming_module_edges)
    return "\n".join(lines) + "\n", len(used_focus_modules), edge_count


def write_detail_images(data: AtlasData, dot_path: Path) -> list[DetailRecord]:
    detail_categories = [
        category
        for category in data.category_files
        if len(data.category_files[category]) >= 2
        or data.incoming_edges[category]
        or data.outgoing_edges[category]
        or data.internal_edges[category]
    ]

    detail_records: list[DetailRecord] = []
    for category in sorted(
        detail_categories,
        key=lambda item: (not item.startswith("core/"), -len(data.category_files[item]), item),
    ):
        source_dot_text, node_count, edge_count = render_detail_dot(data, category)
        file_slug = slug(category)
        source_dot = ASSET_ROOT / f"dependency_detail_{file_slug}.dot"
        png_path = ASSET_ROOT / f"dependency_detail_{file_slug}.png"
        svg_path = ASSET_ROOT / f"dependency_detail_{file_slug}.svg"
        source_dot.write_text(source_dot_text, encoding="utf-8")
        run_dot(dot_path, source_dot, png_path, "png")
        run_dot(dot_path, source_dot, svg_path, "svg")
        source_dot.unlink(missing_ok=True)
        detail_records.append(
            DetailRecord(
                category=category,
                svg_path=svg_path,
                png_path=png_path,
                node_count=node_count,
                edge_count=edge_count,
            )
        )
    return detail_records


def html_link(path: Path) -> str:
    return html.escape(path.relative_to(ROOT_HTML.parent).as_posix())


def render_html(
    data: AtlasData,
    detail_records: list[DetailRecord],
    min_overview_edge_count: int,
) -> str:
    top_edges = sorted(data.category_edges.items(), key=lambda item: (-item[1], item[0]))[:80]
    summary_categories = sorted(
        data.category_files,
        key=lambda category: (-len(data.category_files[category]), category),
    )
    open_categories = {
        "core/config",
        "core/api",
        "core/publish",
        "desktop/application",
        "desktop/api",
    }

    lines = [
        "<!doctype html>",
        '<html lang="en"><head><meta charset="utf-8"><title>Dependency Atlas</title>',
        "<style>"
        "body{font-family:Segoe UI,Arial,sans-serif;margin:24px;color:#111827;background:#fff}"
        "h1{margin:0 0 6px}h2{margin-top:32px}p{max-width:980px;line-height:1.45}"
        ".meta{color:#475569}.links a{margin-right:16px}"
        "img{max-width:100%;height:auto;border:1px solid #cbd5e1;border-radius:6px;background:white}"
        "table{border-collapse:collapse;margin:12px 0 24px;width:100%;font-size:13px}"
        "th,td{border:1px solid #d7dde5;padding:6px 8px;text-align:left;vertical-align:top}"
        "th{background:#f1f5f9}"
        "details{border:1px solid #d7dde5;border-radius:8px;margin:12px 0;padding:10px 12px;background:#fbfdff}"
        "summary{cursor:pointer;font-weight:650}"
        ".legend span{margin-right:14px}"
        ".swatch{display:inline-block;width:12px;height:12px;border-radius:2px;border:1px solid #64748b;"
        "vertical-align:-1px;margin-right:4px}"
        "</style>",
        "</head><body>",
        "<h1>Dependency Atlas</h1>",
        '<p class="meta">Generated from Python AST imports in <code>src/mediapipeline/</code>. Counts are source-module '
        "import relationships, not runtime call counts.</p>",
        '<p class="links">'
        '<a href="dependency-atlas.png">Root PNG overview</a>'
        '<a href="dependency-atlas.svg">Root SVG overview</a>'
        '<a href="assets/dependency_summary.csv">Summary CSV</a>'
        '<a href="assets/dependency_edges.csv">Domain edge CSV</a>'
        '<a href="assets/dependency_module_edges.csv">Module edge CSV</a>'
        "</p>",
        '<p class="legend">'
        '<span><i class="swatch" style="background:#dbeafe"></i>core domain</span>'
        '<span><i class="swatch" style="background:#dcfce7"></i>other source domain</span>'
        '<span><i class="swatch" style="background:#eff6ff"></i>focus modules</span>'
        '<span><i class="swatch" style="background:#f8fafc"></i>external local domains</span>'
        "</p>",
        "<h2>Overview</h2>",
        f"<p>The root overview intentionally shows only major cross-domain relationships "
        f"with {min_overview_edge_count} or more source modules. Use the tables and focused "
        "diagrams below for the full detail.</p>",
        '<img src="dependency-atlas.svg" alt="dependency overview">',
        "<h2>Domain Summary</h2>",
        "<table><thead><tr><th>Domain</th><th>Files</th><th>Internal module edges</th>"
        "<th>Outgoing domain edges</th><th>Incoming domain edges</th></tr></thead><tbody>",
    ]

    for category in summary_categories:
        lines.append(
            f"<tr><td>{html.escape(category)}</td>"
            f"<td>{len(data.category_files[category])}</td>"
            f"<td>{data.internal_edges[category]}</td>"
            f"<td>{data.outgoing_edges[category]}</td>"
            f"<td>{data.incoming_edges[category]}</td></tr>"
        )

    lines.extend(
        [
            "</tbody></table>",
            "<h2>Top Cross-Domain Edges</h2>",
            "<table><thead><tr><th>From</th><th>To</th><th>Source modules</th>"
            "</tr></thead><tbody>",
        ]
    )

    for (source, target), count in top_edges:
        lines.append(
            f"<tr><td>{html.escape(source)}</td><td>{html.escape(target)}</td>"
            f"<td>{count}</td></tr>"
        )

    lines.extend(["</tbody></table>", "<h2>Focused Module Diagrams</h2>"])
    for record in detail_records:
        open_attr = " open" if record.category in open_categories else ""
        lines.append(
            f"<details{open_attr}><summary>{html.escape(record.category)} - "
            f"{len(data.category_files[record.category])} files, "
            f"{record.edge_count} shown edges</summary>"
        )
        lines.append(
            f'<p><a href="{html_link(record.png_path)}">PNG</a> '
            f'<a href="{html_link(record.svg_path)}">SVG</a></p>'
        )
        lines.append(
            f'<img src="{html_link(record.svg_path)}" '
            f'alt="{html.escape(record.category)} dependency detail">'
        )
        lines.append("</details>")

    if data.parse_errors:
        lines.append("<h2>Parse Warnings</h2>")
        lines.append("<table><thead><tr><th>Path</th><th>Error</th></tr></thead><tbody>")
        for path, error in data.parse_errors:
            lines.append(f"<tr><td>{html.escape(path)}</td><td>{html.escape(error)}</td></tr>")
        lines.append("</tbody></table>")

    lines.append("</body></html>")
    return "\n".join(lines) + "\n"


def write_html(data: AtlasData, detail_records: list[DetailRecord], min_edge_count: int) -> None:
    ROOT_HTML.write_text(
        render_html(data, detail_records, min_overview_edge_count=min_edge_count),
        encoding="utf-8",
    )


def validate_html_links() -> int:
    text = ROOT_HTML.read_text(encoding="utf-8")
    links: list[str] = []
    for attribute in ('href="', 'src="'):
        offset = 0
        while True:
            start = text.find(attribute, offset)
            if start == -1:
                break
            value_start = start + len(attribute)
            value_end = text.find('"', value_start)
            if value_end == -1:
                break
            links.append(html.unescape(text[value_start:value_end]))
            offset = value_end + 1

    for link in links:
        if link.startswith(("http://", "https://", "#")):
            continue
        path = ROOT_HTML.parent / Path(link)
        if not path.exists():
            raise FileNotFoundError(f"Atlas link does not resolve: {link}")
    return len(links)


def main() -> int:
    args = parse_args()
    try:
        dot_path = resolve_dot(args.dot)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        print("Install Graphviz or pass --dot C:\\path\\to\\dot.exe.", file=sys.stderr)
        return 2
    clean_outputs()

    data = collect_data(DEFAULT_PACKAGE_ROOTS)
    write_overview_images(
        data,
        dot_path=dot_path,
        min_edge_count=args.min_overview_edge_count,
        min_files=args.min_overview_files,
    )
    write_csvs(data)
    detail_records = write_detail_images(data, dot_path=dot_path)
    write_html(data, detail_records, min_edge_count=args.min_overview_edge_count)
    checked_links = validate_html_links()

    print(f"Graphviz dot: {dot_path}")
    print(f"Modules: {len(data.module_index.module_paths)}")
    print(f"Module edges: {len(data.module_edges)}")
    print(f"Domains: {len(data.category_files)}")
    print(f"Domain edges: {len(data.category_edges)}")
    print(f"Detail diagrams: {len(detail_records)}")
    print(f"HTML local links checked: {checked_links}")
    print(f"Open: {display_path(ROOT_HTML)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
