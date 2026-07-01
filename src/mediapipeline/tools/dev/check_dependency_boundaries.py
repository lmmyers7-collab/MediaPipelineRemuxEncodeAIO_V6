"""Check Python backend dependency boundary rules."""

from __future__ import annotations

import argparse
import ast
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root
from typing import Iterable


REPO_ROOT = find_repo_root(Path(__file__))
DEFAULT_ALLOWLIST_PATH = REPO_ROOT / "docs" / "architecture" / "dependency_boundary_allowlist.txt"

CONFIG_FORBIDDEN_TARGET_PACKAGES = {
    "mediapipeline.core.api",
    "mediapipeline.core.decide",
    "mediapipeline.core.observability",
    "mediapipeline.core.orchestration",
    "mediapipeline.core.processes",
    "mediapipeline.core.publish",
    "mediapipeline.core.queue",
    "mediapipeline.core.rename",
    "mediapipeline.core.status",
    "mediapipeline.core.telemetry",
    "mediapipeline.core.ui",
}
FORBIDDEN_EXTERNAL_PREFIXES = (
    "mediapipeline.desktop",
)

HARD_RULE_IDS = {
    "NO_PACKAGE_CYCLES",
    "NO_MODULE_CYCLES",
    "NO_CORE_TO_DESKTOP",
    "NO_CONFIG_TO_ORCHESTRATION",
    "NO_CONFIG_TO_DECIDE",
    "NO_CONFIG_TO_HIGHER_LEVEL",
    "NO_API_TO_UI",
    "NO_OBSERVABILITY_TO_STATUS",
    "NO_TELEMETRY_TO_OBSERVABILITY",
    "NO_TELEMETRY_TO_STATUS",
    "NO_DIRECT_APP_SHARED_IMPORTS",
    "PYTHON_PARSE_ERRORS",
}
PERMANENTLY_ENFORCED_RULE_IDS = {
    "NO_CORE_TO_DESKTOP",
}

@dataclass(frozen=True)
class ImportEdge:
    source_module: str
    target_module: str
    source_path: str
    line: int
    import_text: str


@dataclass(frozen=True)
class ParseError:
    path: str
    detail: str


@dataclass(frozen=True)
class DependencyReport:
    app_imports: list[ImportEdge]
    module_cycles: list[list[str]]
    package_cycles: list[list[str]]
    forbidden_core_desktop_imports: list[ImportEdge]
    direct_app_shared_imports: list[ImportEdge]
    direct_app_shared_utils_imports: list[ImportEdge]
    direct_app_shared_constants_imports: list[ImportEdge]
    direct_app_shared_protocols_imports: list[ImportEdge]
    forbidden_config_imports: list[ImportEdge]
    forbidden_api_ui_imports: list[ImportEdge]
    forbidden_observability_status_imports: list[ImportEdge]
    forbidden_telemetry_observability_imports: list[ImportEdge]
    forbidden_telemetry_status_imports: list[ImportEdge]
    parse_errors: list[ParseError]


@dataclass(frozen=True)
class AllowlistEntry:
    importing_module: str
    imported_module: str
    rule_id: str
    reason: str
    target: str
    line: int


@dataclass(frozen=True)
class AllowlistError:
    path: str
    line: int
    detail: str


@dataclass(frozen=True)
class RuleFinding:
    rule_id: str
    importing_module: str
    imported_module: str
    detail: str

    @property
    def key(self) -> tuple[str, str, str]:
        return (self.importing_module, self.imported_module, self.rule_id)


@dataclass(frozen=True)
class EnforcementReport:
    hard_findings: list[RuleFinding]
    warning_findings: list[RuleFinding]
    allowlisted_findings: list[RuleFinding]
    unallowlisted_findings: list[RuleFinding]
    unused_allowlist_entries: list[AllowlistEntry]
    allowlist_errors: list[AllowlistError]


def display_path(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def module_name_for_path(path: Path, package_root: Path, package_name: str) -> str:
    rel = path.relative_to(package_root).with_suffix("")
    parts = list(rel.parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join([package_name, *parts]) if parts else package_name


def iter_backend_modules(root: Path = REPO_ROOT) -> dict[str, Path]:
    root = root.resolve()
    package_root = root / "src" / "mediapipeline" / "core"
    package_name = "mediapipeline.core"
    modules: dict[str, Path] = {}
    for path in sorted(package_root.rglob("*.py")):
        modules[module_name_for_path(path, package_root, package_name)] = path
    return modules


def source_package_for(source_module: str, source_path: Path) -> str:
    if source_path.name == "__init__.py":
        return source_module
    return source_module.rsplit(".", 1)[0]


def resolve_known_module(name: str, known_modules: set[str]) -> str | None:
    if not (name == "mediapipeline.core" or name.startswith("mediapipeline.core.")):
        return None
    parts = name.split(".")
    while parts:
        candidate = ".".join(parts)
        if candidate in known_modules:
            return candidate
        parts.pop()
    return None


def resolve_forbidden_external_module(name: str) -> str | None:
    for prefix in FORBIDDEN_EXTERNAL_PREFIXES:
        if name == prefix or name.startswith(prefix + "."):
            return name
    return None


def resolve_import_from_base(
    node: ast.ImportFrom,
    source_module: str,
    source_path: Path,
) -> str | None:
    if node.level:
        source_package = source_package_for(source_module, source_path)
        package_parts = source_package.split(".")
        if node.level > len(package_parts):
            return None
        base_parts = package_parts[: len(package_parts) - node.level + 1]
        if node.module:
            base_parts.extend(node.module.split("."))
        return ".".join(base_parts)
    return node.module


def import_targets(
    tree: ast.AST,
    source_module: str,
    source_path: Path,
    known_modules: set[str],
) -> list[ImportEdge]:
    edges: list[ImportEdge] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                target = resolve_known_module(alias.name, known_modules)
                if target is None:
                    target = resolve_forbidden_external_module(alias.name)
                if target is None:
                    continue
                edges.append(
                    ImportEdge(
                        source_module=source_module,
                        target_module=target,
                        source_path=source_path.as_posix(),
                        line=node.lineno,
                        import_text=f"import {alias.name}",
                    )
                )
        elif isinstance(node, ast.ImportFrom):
            base = resolve_import_from_base(node, source_module, source_path)
            if not base:
                continue
            base_target = resolve_known_module(base, known_modules)
            external_base_target = resolve_forbidden_external_module(base)
            if base_target is None and external_base_target is None:
                continue
            for alias in node.names:
                if external_base_target is not None:
                    if base == "mediapipeline.desktop" and alias.name != "*":
                        target = resolve_forbidden_external_module(f"{base}.{alias.name}") or external_base_target
                    else:
                        target = external_base_target
                elif alias.name == "*":
                    target = base_target
                else:
                    target = resolve_known_module(f"{base}.{alias.name}", known_modules)
                    if target is None:
                        target = base_target
                if target is None:
                    continue
                edges.append(
                    ImportEdge(
                        source_module=source_module,
                        target_module=target,
                        source_path=source_path.as_posix(),
                        line=node.lineno,
                        import_text=f"from {'.' * node.level}{node.module or ''} import {alias.name}",
                    )
                )
    return edges


def package_name(module_name: str) -> str:
    parts = module_name.split(".")
    if parts[:2] == ["mediapipeline", "core"] and len(parts) > 2:
        return ".".join(parts[:3])
    if len(parts) <= 1:
        return module_name
    return ".".join(parts[:2])


def graph_from_edges(edges: Iterable[tuple[str, str]]) -> dict[str, set[str]]:
    graph: dict[str, set[str]] = {}
    for source, target in edges:
        graph.setdefault(source, set()).add(target)
        graph.setdefault(target, set())
    return graph


def strongly_connected_components(graph: dict[str, set[str]]) -> list[list[str]]:
    index = 0
    stack: list[str] = []
    indexes: dict[str, int] = {}
    lowlinks: dict[str, int] = {}
    on_stack: set[str] = set()
    components: list[list[str]] = []

    def visit(node: str) -> None:
        nonlocal index
        indexes[node] = index
        lowlinks[node] = index
        index += 1
        stack.append(node)
        on_stack.add(node)

        for target in graph.get(node, set()):
            if target not in indexes:
                visit(target)
                lowlinks[node] = min(lowlinks[node], lowlinks[target])
            elif target in on_stack:
                lowlinks[node] = min(lowlinks[node], indexes[target])

        if lowlinks[node] == indexes[node]:
            component: list[str] = []
            while True:
                target = stack.pop()
                on_stack.remove(target)
                component.append(target)
                if target == node:
                    break
            components.append(sorted(component))

    for node in sorted(graph):
        if node not in indexes:
            visit(node)
    return components


def cycles_from_graph(graph: dict[str, set[str]]) -> list[list[str]]:
    cycles: list[list[str]] = []
    for component in strongly_connected_components(graph):
        if len(component) > 1:
            cycles.append(component)
        elif component and component[0] in graph.get(component[0], set()):
            cycles.append(component)
    return sorted(cycles, key=lambda cycle: (len(cycle), cycle))


def module_cycle_edges(report: DependencyReport) -> list[tuple[str, str]]:
    pairs: set[tuple[str, str]] = set()
    for cycle in report.module_cycles:
        cycle_modules = set(cycle)
        for edge in report.app_imports:
            if edge.source_module in cycle_modules and edge.target_module in cycle_modules:
                pairs.add((edge.source_module, edge.target_module))
    return sorted(pairs)


def package_cycle_edges(report: DependencyReport) -> list[tuple[str, str]]:
    pairs: set[tuple[str, str]] = set()
    for cycle in report.package_cycles:
        cycle_packages = set(cycle)
        for edge in report.app_imports:
            source_package = package_name(edge.source_module)
            target_package = package_name(edge.target_module)
            if (
                source_package != target_package
                and source_package in cycle_packages
                and target_package in cycle_packages
            ):
                pairs.add((source_package, target_package))
    return sorted(pairs)


def collect_backend_imports(root: Path = REPO_ROOT) -> tuple[list[ImportEdge], list[ParseError]]:
    root = root.resolve()
    modules = iter_backend_modules(root)
    known_modules = set(modules)
    edges: list[ImportEdge] = []
    parse_errors: list[ParseError] = []
    for source_module, path in sorted(modules.items()):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except Exception as exc:  # pragma: no cover - malformed source reporting
            parse_errors.append(ParseError(display_path(path, root), str(exc)))
            continue
        for edge in import_targets(tree, source_module, path.relative_to(root), known_modules):
            if edge.source_module == edge.target_module:
                continue
            edges.append(edge)
    return sorted(edges, key=lambda edge: (edge.source_module, edge.line, edge.target_module)), parse_errors


def filter_target(edges: Iterable[ImportEdge], target_module: str) -> list[ImportEdge]:
    return [edge for edge in edges if edge.target_module == target_module]


def filter_package_edge(edges: Iterable[ImportEdge], source_package: str, target_package: str) -> list[ImportEdge]:
    return [
        edge
        for edge in edges
        if package_name(edge.source_module) == source_package and package_name(edge.target_module) == target_package
    ]


def analyze(root: Path = REPO_ROOT) -> DependencyReport:
    root = root.resolve()
    app_imports, parse_errors = collect_backend_imports(root)

    module_graph = graph_from_edges((edge.source_module, edge.target_module) for edge in app_imports)
    package_edges = {
        (package_name(edge.source_module), package_name(edge.target_module))
        for edge in app_imports
        if package_name(edge.source_module) != package_name(edge.target_module)
    }
    package_graph = graph_from_edges(package_edges)

    forbidden_config_imports = [
        edge
        for edge in app_imports
        if package_name(edge.source_module) == "mediapipeline.core.config"
        and package_name(edge.target_module) in CONFIG_FORBIDDEN_TARGET_PACKAGES
    ]
    forbidden_core_desktop_imports = [
        edge
        for edge in app_imports
        if (
            edge.source_module == "mediapipeline.core"
            or edge.source_module.startswith("mediapipeline.core.")
        )
        and (
            edge.target_module == "mediapipeline.desktop"
            or edge.target_module.startswith("mediapipeline.desktop.")
        )
    ]

    return DependencyReport(
        app_imports=app_imports,
        module_cycles=cycles_from_graph(module_graph),
        package_cycles=cycles_from_graph(package_graph),
        forbidden_core_desktop_imports=forbidden_core_desktop_imports,
        direct_app_shared_imports=filter_target(app_imports, "mediapipeline.core.shared"),
        direct_app_shared_utils_imports=filter_target(app_imports, "mediapipeline.core.shared.utils"),
        direct_app_shared_constants_imports=filter_target(app_imports, "mediapipeline.core.shared.constants"),
        direct_app_shared_protocols_imports=filter_target(app_imports, "mediapipeline.core.shared.protocols"),
        forbidden_config_imports=forbidden_config_imports,
        forbidden_api_ui_imports=filter_package_edge(app_imports, "mediapipeline.core.api", "mediapipeline.core.ui"),
        forbidden_observability_status_imports=filter_package_edge(
            app_imports, "mediapipeline.core.observability", "mediapipeline.core.status"
        ),
        forbidden_telemetry_observability_imports=filter_package_edge(
            app_imports, "mediapipeline.core.telemetry", "mediapipeline.core.observability"
        ),
        forbidden_telemetry_status_imports=filter_package_edge(app_imports, "mediapipeline.core.telemetry", "mediapipeline.core.status"),
        parse_errors=parse_errors,
    )


def config_rule_id(edge: ImportEdge) -> str:
    target_package = package_name(edge.target_module)
    if target_package == "mediapipeline.core.orchestration":
        return "NO_CONFIG_TO_ORCHESTRATION"
    if target_package == "mediapipeline.core.decide":
        return "NO_CONFIG_TO_DECIDE"
    return "NO_CONFIG_TO_HIGHER_LEVEL"


def hard_rule_findings(report: DependencyReport) -> list[RuleFinding]:
    findings: list[RuleFinding] = []
    findings.extend(
        RuleFinding(
            "NO_MODULE_CYCLES",
            source,
            target,
            "Module-level cycle edge. Remove the cycle or add a specific temporary allowlist entry.",
        )
        for source, target in module_cycle_edges(report)
    )
    findings.extend(
        RuleFinding(
            "NO_PACKAGE_CYCLES",
            source,
            target,
            "Package-level cycle edge. Remove the cycle or add a specific temporary allowlist entry.",
        )
        for source, target in package_cycle_edges(report)
    )
    findings.extend(
        RuleFinding(
            "NO_CORE_TO_DESKTOP",
            edge.source_module,
            edge.target_module,
            f"Backend core must not import desktop adapters; import found at {edge.source_path}:{edge.line}.",
        )
        for edge in report.forbidden_core_desktop_imports
    )
    findings.extend(
        RuleFinding(
            "NO_DIRECT_APP_SHARED_IMPORTS",
            edge.source_module,
            edge.target_module,
            f"Direct mediapipeline.core.shared import at {edge.source_path}:{edge.line}.",
        )
        for edge in report.direct_app_shared_imports
    )
    findings.extend(
        RuleFinding(
            config_rule_id(edge),
            edge.source_module,
            edge.target_module,
            f"mediapipeline.core.config must stay low-level; import found at {edge.source_path}:{edge.line}.",
        )
        for edge in report.forbidden_config_imports
    )
    findings.extend(
        RuleFinding(
            "NO_API_TO_UI",
            edge.source_module,
            edge.target_module,
            f"mediapipeline.core.api must not import mediapipeline.core.ui; import found at {edge.source_path}:{edge.line}.",
        )
        for edge in report.forbidden_api_ui_imports
    )
    findings.extend(
        RuleFinding(
            "NO_OBSERVABILITY_TO_STATUS",
            edge.source_module,
            edge.target_module,
            f"mediapipeline.core.observability must not import mediapipeline.core.status; import found at {edge.source_path}:{edge.line}.",
        )
        for edge in report.forbidden_observability_status_imports
    )
    findings.extend(
        RuleFinding(
            "NO_TELEMETRY_TO_OBSERVABILITY",
            edge.source_module,
            edge.target_module,
            f"mediapipeline.core.telemetry must not import mediapipeline.core.observability; import found at {edge.source_path}:{edge.line}.",
        )
        for edge in report.forbidden_telemetry_observability_imports
    )
    findings.extend(
        RuleFinding(
            "NO_TELEMETRY_TO_STATUS",
            edge.source_module,
            edge.target_module,
            f"mediapipeline.core.telemetry must not import mediapipeline.core.status; import found at {edge.source_path}:{edge.line}.",
        )
        for edge in report.forbidden_telemetry_status_imports
    )
    findings.extend(
        RuleFinding("PYTHON_PARSE_ERRORS", error.path, "<parse>", error.detail)
        for error in report.parse_errors
    )
    return sorted(findings, key=lambda finding: finding.key)


def warning_rule_findings(report: DependencyReport) -> list[RuleFinding]:
    findings: list[RuleFinding] = []
    findings.extend(
        RuleFinding(
            "NO_SHARED_UTILS_IMPORTS",
            edge.source_module,
            edge.target_module,
            f"Shared utils import remains at {edge.source_path}:{edge.line}.",
        )
        for edge in report.direct_app_shared_utils_imports
    )
    findings.extend(
        RuleFinding(
            "NO_SHARED_CONSTANTS_IMPORTS",
            edge.source_module,
            edge.target_module,
            f"Shared constants import remains at {edge.source_path}:{edge.line}.",
        )
        for edge in report.direct_app_shared_constants_imports
    )
    findings.extend(
        RuleFinding(
            "NO_SHARED_PROTOCOLS_IMPORTS",
            edge.source_module,
            edge.target_module,
            f"Shared protocols import remains at {edge.source_path}:{edge.line}.",
        )
        for edge in report.direct_app_shared_protocols_imports
    )
    findings.extend(
        RuleFinding(
            "NO_DOMAIN_IMPORTS_FROM_SHARED_CONSTANTS",
            edge.source_module,
            edge.target_module,
            f"Domain shared-constants import remains at {edge.source_path}:{edge.line}.",
        )
        for edge in report.direct_app_shared_constants_imports
        if package_name(edge.source_module) != "mediapipeline.core.shared"
    )
    findings.extend(
        RuleFinding(
            "NO_BARREL_INIT_REEXPORTS",
            edge.source_module,
            edge.target_module,
            f"Package __init__ re-export remains at {edge.source_path}:{edge.line}.",
        )
        for edge in report.app_imports
        if Path(edge.source_path).name == "__init__.py"
    )
    return sorted(findings, key=lambda finding: finding.key)


def load_allowlist(path: Path) -> tuple[list[AllowlistEntry], list[AllowlistError]]:
    if not path.exists():
        return [], []
    entries: list[AllowlistEntry] = []
    errors: list[AllowlistError] = []
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        fields = [field.strip() for field in line.split("|")]
        if len(fields) != 5:
            errors.append(
                AllowlistError(
                    path.as_posix(),
                    line_number,
                    "Expected 5 pipe-delimited fields: importing module | imported module | rule id | reason | target removal phase or owner.",
                )
            )
            continue
        importing_module, imported_module, rule_id, reason, target = fields
        if not all(fields):
            errors.append(AllowlistError(path.as_posix(), line_number, "Allowlist fields must not be empty."))
            continue
        if rule_id not in HARD_RULE_IDS:
            errors.append(
                AllowlistError(path.as_posix(), line_number, f"Unknown or non-hard rule id {rule_id!r}.")
            )
            continue
        if rule_id in PERMANENTLY_ENFORCED_RULE_IDS:
            errors.append(
                AllowlistError(
                    path.as_posix(),
                    line_number,
                    f"{rule_id} is permanently enforced and cannot be allowlisted.",
                )
            )
            continue
        entries.append(
            AllowlistEntry(
                importing_module=importing_module,
                imported_module=imported_module,
                rule_id=rule_id,
                reason=reason,
                target=target,
                line=line_number,
            )
        )
    seen: set[tuple[str, str, str]] = set()
    for entry in entries:
        key = (entry.importing_module, entry.imported_module, entry.rule_id)
        if key in seen:
            errors.append(
                AllowlistError(
                    path.as_posix(),
                    entry.line,
                    f"Duplicate allowlist entry for {entry.importing_module} -> {entry.imported_module} ({entry.rule_id}).",
                )
            )
        seen.add(key)
    return entries, errors


def enforce_rules(report: DependencyReport, allowlist_path: Path = DEFAULT_ALLOWLIST_PATH) -> EnforcementReport:
    allowlist_entries, allowlist_errors = load_allowlist(allowlist_path)
    allowed_keys = {
        (entry.importing_module, entry.imported_module, entry.rule_id): entry
        for entry in allowlist_entries
    }
    hard_findings = hard_rule_findings(report)
    allowlisted_findings = [finding for finding in hard_findings if finding.key in allowed_keys]
    unallowlisted_findings = [finding for finding in hard_findings if finding.key not in allowed_keys]
    finding_keys = {finding.key for finding in hard_findings}
    unused_allowlist_entries = [
        entry
        for entry in allowlist_entries
        if (entry.importing_module, entry.imported_module, entry.rule_id) not in finding_keys
    ]
    return EnforcementReport(
        hard_findings=hard_findings,
        warning_findings=warning_rule_findings(report),
        allowlisted_findings=allowlisted_findings,
        unallowlisted_findings=unallowlisted_findings,
        unused_allowlist_entries=unused_allowlist_entries,
        allowlist_errors=allowlist_errors,
    )


def format_edge(edge: ImportEdge, root: Path) -> str:
    path = Path(edge.source_path)
    try:
        rel = path.relative_to(root)
    except ValueError:
        rel = path
    return (
        f"- {edge.source_module} -> {edge.target_module} "
        f"({rel.as_posix()}:{edge.line}; {edge.import_text})"
    )


def render_cycle(cycle: list[str]) -> str:
    if not cycle:
        return "- <empty cycle>"
    return f"- {' -> '.join(cycle)} -> {cycle[0]}"


def render_edge_section(title: str, edges: list[ImportEdge], root: Path, max_rows: int) -> list[str]:
    lines = [f"{title}: {len(edges)}"]
    if not edges:
        lines.append("- none")
        return lines
    visible = edges if max_rows <= 0 else edges[:max_rows]
    lines.extend(format_edge(edge, root) for edge in visible)
    if max_rows > 0 and len(edges) > max_rows:
        lines.append(f"- ... {len(edges) - max_rows} more")
    return lines


def render_finding(finding: RuleFinding) -> str:
    return (
        f"- {finding.rule_id}: {finding.importing_module} -> {finding.imported_module} "
        f"({finding.detail})"
    )


def render_allowlist_error(error: AllowlistError) -> str:
    return f"- {error.path}:{error.line}: {error.detail}"


def render_enforcement(enforcement: EnforcementReport) -> list[str]:
    lines = [
        "Hard Rule Enforcement:",
        f"- hard findings: {len(enforcement.hard_findings)}",
        f"- allowlisted hard findings: {len(enforcement.allowlisted_findings)}",
        f"- unallowlisted hard findings: {len(enforcement.unallowlisted_findings)}",
        f"- warning findings: {len(enforcement.warning_findings)}",
        f"- allowlist errors: {len(enforcement.allowlist_errors)}",
        f"- unused allowlist entries: {len(enforcement.unused_allowlist_entries)}",
    ]
    if enforcement.unallowlisted_findings:
        lines.append("")
        lines.append("Unallowlisted Hard Findings:")
        lines.extend(render_finding(finding) for finding in enforcement.unallowlisted_findings)
    if enforcement.allowlist_errors:
        lines.append("")
        lines.append("Allowlist Errors:")
        lines.extend(render_allowlist_error(error) for error in enforcement.allowlist_errors)
    if enforcement.unused_allowlist_entries:
        lines.append("")
        lines.append("Unused Allowlist Entries:")
        lines.extend(
            f"- {entry.rule_id}: {entry.importing_module} -> {entry.imported_module} "
            f"({entry.target}; line {entry.line})"
            for entry in enforcement.unused_allowlist_entries
        )
    return lines


def render_report(
    report: DependencyReport,
    root: Path = REPO_ROOT,
    max_internal_imports: int = 0,
    enforcement: EnforcementReport | None = None,
) -> str:
    lines = [
        "Dependency boundary check",
        "Convention: A -> B means A imports B.",
        "",
        f"Internal backend imports: {len(report.app_imports)}",
        f"Module-level cycles: {len(report.module_cycles)}",
        f"Package-level cycles: {len(report.package_cycles)}",
        f"Parse errors: {len(report.parse_errors)}",
        "",
        "Module-Level Cycles:",
    ]
    lines.extend(render_cycle(cycle) for cycle in report.module_cycles)
    if not report.module_cycles:
        lines.append("- none")

    lines.append("")
    lines.append("Package-Level Cycles:")
    lines.extend(render_cycle(cycle) for cycle in report.package_cycles)
    if not report.package_cycles:
        lines.append("- none")

    sections = [
        ("Forbidden mediapipeline.core to mediapipeline.desktop imports", report.forbidden_core_desktop_imports),
        ("Direct mediapipeline.core.shared imports", report.direct_app_shared_imports),
        ("Direct mediapipeline.core.shared.utils imports", report.direct_app_shared_utils_imports),
        ("Direct mediapipeline.core.shared.constants imports", report.direct_app_shared_constants_imports),
        ("Direct mediapipeline.core.shared.protocols imports", report.direct_app_shared_protocols_imports),
        ("Forbidden mediapipeline.core.config higher-level imports", report.forbidden_config_imports),
        ("Forbidden mediapipeline.core.api to mediapipeline.core.ui imports", report.forbidden_api_ui_imports),
        ("Forbidden mediapipeline.core.observability to mediapipeline.core.status imports", report.forbidden_observability_status_imports),
        (
            "Forbidden mediapipeline.core.telemetry to mediapipeline.core.observability imports",
            report.forbidden_telemetry_observability_imports,
        ),
        ("Forbidden mediapipeline.core.telemetry to mediapipeline.core.status imports", report.forbidden_telemetry_status_imports),
    ]
    for title, edges in sections:
        lines.append("")
        lines.extend(render_edge_section(title, edges, root, max_rows=0))

    if report.parse_errors:
        lines.append("")
        lines.append("Parse Errors:")
        lines.extend(f"- {error.path}: {error.detail}" for error in report.parse_errors)

    lines.append("")
    lines.extend(render_edge_section("Internal Backend Import Edges", report.app_imports, root, max_internal_imports))
    if enforcement is not None:
        lines.append("")
        lines.extend(render_enforcement(enforcement))
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=REPO_ROOT, help="Repository root to scan.")
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format.",
    )
    parser.add_argument(
        "--max-internal-imports",
        type=int,
        default=0,
        help="Maximum internal app import rows to print; 0 means all rows.",
    )
    parser.add_argument(
        "--fail-on-violations",
        action="store_true",
        help="Deprecated compatibility flag. Hard-rule enforcement is now the default.",
    )
    parser.add_argument(
        "--report-only",
        action="store_true",
        help="Print findings but exit 0 even when unallowlisted hard findings exist.",
    )
    parser.add_argument(
        "--allowlist",
        type=Path,
        default=DEFAULT_ALLOWLIST_PATH,
        help="Pipe-delimited hard-rule allowlist path.",
    )
    args = parser.parse_args(argv)

    report = analyze(args.root)
    enforcement = enforce_rules(report, args.allowlist)
    if args.format == "json":
        print(
            json.dumps(
                {
                    "report": asdict(report),
                    "enforcement": asdict(enforcement),
                },
                indent=2,
                sort_keys=True,
            )
        )
    else:
        print(render_report(report, args.root, args.max_internal_imports, enforcement))

    if args.report_only:
        return 0
    if enforcement.allowlist_errors or enforcement.unallowlisted_findings or enforcement.unused_allowlist_entries:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
