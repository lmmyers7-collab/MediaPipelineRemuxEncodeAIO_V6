"""Deterministic, dependency-free metadata extraction for repository context."""

from __future__ import annotations

import ast
import hashlib
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath


SUMMARY_SCHEMA_VERSION = 2
_PARSER_CONTRACT = "|".join(
    (
        f"summary-schema:{SUMMARY_SCHEMA_VERSION}",
        "python:ast-imports-routes-state-v2",
        "javascript:functions-window-api-dom-v2",
        "powershell:functions-dot-source-stage-tool-state-v2",
        "rust:symbol-route-state-v2",
        "fallback:path-symbol-purpose-v2",
    )
)
SUMMARY_GENERATOR_FINGERPRINT = hashlib.sha256(_PARSER_CONTRACT.encode("utf-8")).hexdigest()

GENERATED_NAVIGATION_FILES = frozenset(
    {
        "docs/generated/DEPENDENCY_GRAPH.md",
        "docs/generated/FEATURE_FILE_MAP.md",
        "docs/generated/PROJECT_INDEX.jsonl",
        "docs/generated/PROJECT_INDEX.md",
    }
)
GENERATED_NAVIGATION_PREFIXES = (
    "docs/generated/feature-cards/",
    "docs/generated/summaries/",
)


@dataclass(frozen=True)
class ExtractedSource:
    file_type: str
    purpose: str
    public_symbols: tuple[str, ...] = ()
    dependencies: tuple[str, ...] = ()
    api_routes: tuple[str, ...] = ()
    state_files: tuple[str, ...] = ()
    dom_selectors: tuple[str, ...] = ()
    invoked_stages: tuple[str, ...] = ()
    invoked_tools: tuple[str, ...] = ()
    exports: tuple[str, ...] = ()
    parse_warning: str = ""


_FILE_TYPES = {
    ".bat": "Windows batch",
    ".css": "CSS",
    ".html": "HTML",
    ".js": "JavaScript",
    ".json": "JSON",
    ".jsonl": "JSON Lines",
    ".md": "Markdown",
    ".mjs": "JavaScript module",
    ".ps1": "PowerShell",
    ".psd1": "PowerShell data",
    ".psm1": "PowerShell module",
    ".py": "Python",
    ".rs": "Rust",
    ".toml": "TOML",
    ".yaml": "YAML",
    ".yml": "YAML",
}

_STATE_FILE_RE = re.compile(
    r"(?i)(?:[A-Za-z0-9_.-]*(?:state|manifest|journal|queue|pending|config|settings)[A-Za-z0-9_.-]*"
    r"\.(?:jsonl?|csv|db|sqlite(?:3)?|psd1)|[A-Za-z0-9_.-]+\.(?:db|sqlite(?:3)?))"
)
_API_ROUTE_RE = re.compile(r"(?i)(?:GET|POST|PUT|PATCH|DELETE)?\s*(/api/[A-Za-z0-9_?&=./:{}-]+)")


def _unique(values: list[str] | tuple[str, ...], limit: int) -> tuple[str, ...]:
    return tuple(sorted({value.strip() for value in values if value and value.strip()}, key=lambda value: (value.casefold(), value))[:limit])


def _first_line(text: str) -> str:
    return " ".join(text.strip().split()).strip()


def _human_words(value: str) -> str:
    value = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", value)
    value = re.sub(r"[_\-.]+", " ", value)
    return " ".join(value.split()).lower()


def fallback_purpose(rel_path: str, file_type: str, symbols: tuple[str, ...] = ()) -> str:
    """Build a compact deterministic purpose when source documentation is absent."""
    path = PurePosixPath(rel_path.replace("\\", "/"))
    stem = path.stem
    if stem.lower() in {"__init__", "index", "main", "mod", "service", "facade"} and path.parent.name:
        subject = f"{_human_words(path.parent.name)} {_human_words(stem)}"
    else:
        subject = _human_words(stem)
    subject = subject or _human_words(path.name) or "repository support"
    symbol_hint = f"; exposes {', '.join(symbols[:3])}" if symbols else ""
    return f"{file_type} implementation for {subject}{symbol_hint}."


def is_generated_navigation_output(path: str | Path) -> bool:
    normalized = str(path).replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized in GENERATED_NAVIGATION_FILES or any(
        normalized.startswith(prefix) for prefix in GENERATED_NAVIGATION_PREFIXES
    )


def _state_files(text: str) -> tuple[str, ...]:
    return _unique(_STATE_FILE_RE.findall(text), 20)


def _api_routes(text: str) -> tuple[str, ...]:
    return _unique([match.group(1) for match in _API_ROUTE_RE.finditer(text)], 24)


_ROUTE_DECORATOR_NAMES = {"route", "get", "post", "put", "delete", "patch", "websocket"}


def _python_route(dec: ast.expr) -> str | None:
    target = dec.func if isinstance(dec, ast.Call) else dec
    if isinstance(target, ast.Attribute):
        name = target.attr
    elif isinstance(target, ast.Name):
        name = target.id
    else:
        return None
    if name not in _ROUTE_DECORATOR_NAMES:
        return None
    if isinstance(dec, ast.Call) and dec.args:
        first = dec.args[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            return f"{name.upper()} {first.value}"
    return name.upper()


def _extract_python(text: str, rel_path: str) -> ExtractedSource:
    try:
        tree = ast.parse(text, filename=rel_path)
    except SyntaxError as exc:
        purpose = fallback_purpose(rel_path, "Python")
        return ExtractedSource(file_type="Python", purpose=purpose, parse_warning=f"syntax error: {exc.msg}")

    symbols: list[str] = []
    dependencies: list[str] = []
    routes: list[str] = list(_api_routes(text))
    for node in tree.body:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.name.startswith("_"):
                symbols.append(node.name)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                routes.extend(route for dec in node.decorator_list if (route := _python_route(dec)))
        elif isinstance(node, ast.Import):
            dependencies.extend(alias.name for alias in node.names if alias.name.startswith(("mediapipeline", "app")))
        elif isinstance(node, ast.ImportFrom):
            module = "." * node.level + (node.module or "")
            if node.level or module.startswith(("mediapipeline", "app")):
                dependencies.append(module or ".")

    public_symbols = _unique(symbols, 30)
    docstring = _first_line(ast.get_docstring(tree) or "")
    purpose = docstring or fallback_purpose(rel_path, "Python", public_symbols)
    return ExtractedSource(
        file_type="Python",
        purpose=purpose,
        public_symbols=public_symbols,
        dependencies=_unique(dependencies, 30),
        api_routes=_unique(routes, 24),
        state_files=_state_files(text),
    )


_JS_FUNCTION_RE = re.compile(
    r"(?m)\b(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(|"
    r"\b(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?(?:\([^)]*\)|[A-Za-z_$][\w$]*)\s*=>"
)
_JS_IMPORT_RE = re.compile(r"(?m)\b(?:import|export)\b[^'\"\n]*['\"]([^'\"]+)['\"]")
_JS_WINDOW_RE = re.compile(r"\bwindow\.([A-Za-z_$][\w$]*)")
_JS_WINDOW_EXPORT_RE = re.compile(r"\bwindow\.([A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)+)\s*=")
_JS_QUERY_RE = re.compile(r"\bquerySelector(?:All)?\(\s*['\"]([^'\"]+)['\"]\s*\)")
_JS_ID_RE = re.compile(r"\bgetElementById\(\s*['\"]([^'\"]+)['\"]\s*\)")


def _extract_javascript(text: str, rel_path: str, file_type: str) -> ExtractedSource:
    symbols = [left or right for left, right in _JS_FUNCTION_RE.findall(text)]
    window_names = [f"window.{name}" for name in _JS_WINDOW_RE.findall(text)]
    window_exports = [f"window.{name}" for name in _JS_WINDOW_EXPORT_RE.findall(text)]
    imports = list(_JS_IMPORT_RE.findall(text))
    selectors = list(_JS_QUERY_RE.findall(text)) + [f"#{value}" for value in _JS_ID_RE.findall(text)]
    public_symbols = _unique(symbols, 35)
    return ExtractedSource(
        file_type=file_type,
        purpose=fallback_purpose(rel_path, file_type, public_symbols),
        public_symbols=public_symbols,
        dependencies=_unique(imports + window_names, 35),
        api_routes=_api_routes(text),
        state_files=_state_files(text),
        dom_selectors=_unique(selectors, 30),
        exports=_unique(window_exports, 30),
    )


_PS_SYNOPSIS_RE = re.compile(r"\.SYNOPSIS\s*\r?\n\s*(.+?)(?:\r?\n\s*\.|\r?\n\s*#>)", re.IGNORECASE | re.DOTALL)
_PS_FUNCTION_RE = re.compile(r"(?im)^\s*function\s+([A-Za-z][A-Za-z0-9_-]*)")
_PS_DOT_SOURCE_RE = re.compile(r"(?im)^\s*\.\s+([^\r\n;]+?\.ps(?:m)?1)(?:\s|$)")
_PS_STAGE_RE = re.compile(r"(?i)(?:-Stage|Invoke-(?:Pipeline)?Stage\s+)\s*['\"]?([A-Za-z][A-Za-z0-9_-]*)")
_PS_TOOL_RE = re.compile(r"(?i)\b(ffmpeg|ffprobe|mkvmerge|mkvextract|mkvpropedit|pgstosrt)\b")


def _extract_powershell(text: str, rel_path: str, file_type: str) -> ExtractedSource:
    symbols = _unique(list(_PS_FUNCTION_RE.findall(text)), 35)
    synopsis_match = _PS_SYNOPSIS_RE.search(text)
    synopsis = _first_line(synopsis_match.group(1)) if synopsis_match else ""
    dependencies = [value.strip().strip("'\"") for value in _PS_DOT_SOURCE_RE.findall(text)]
    return ExtractedSource(
        file_type=file_type,
        purpose=synopsis or fallback_purpose(rel_path, file_type, symbols),
        public_symbols=symbols,
        dependencies=_unique(dependencies, 30),
        api_routes=_api_routes(text),
        state_files=_state_files(text),
        invoked_stages=_unique(list(_PS_STAGE_RE.findall(text)), 16),
        invoked_tools=_unique([value.lower() for value in _PS_TOOL_RE.findall(text)], 12),
    )


_RUST_SYMBOL_RE = re.compile(r"(?m)^\s*(?:pub(?:\([^)]*\))?\s+)?(?:async\s+)?(?:fn|struct|enum|trait)\s+([A-Za-z_][A-Za-z0-9_]*)")


def _extract_rust(text: str, rel_path: str) -> ExtractedSource:
    symbols = _unique(list(_RUST_SYMBOL_RE.findall(text)), 35)
    return ExtractedSource(
        file_type="Rust",
        purpose=fallback_purpose(rel_path, "Rust", symbols),
        public_symbols=symbols,
        api_routes=_api_routes(text),
        state_files=_state_files(text),
    )


def _extract_html(text: str, rel_path: str) -> ExtractedSource:
    ids = _unique([f"#{value}" for value in re.findall(r"\bid\s*=\s*['\"]([^'\"]+)['\"]", text, re.IGNORECASE)], 40)
    return ExtractedSource(
        file_type="HTML",
        purpose=fallback_purpose(rel_path, "HTML"),
        api_routes=_api_routes(text),
        state_files=_state_files(text),
        dom_selectors=ids,
    )


def extract_source(path: Path, rel_path: str) -> ExtractedSource:
    """Extract compact context metadata from one text source file."""
    suffix = path.suffix.lower()
    file_type = _FILE_TYPES.get(suffix, f"{suffix.lstrip('.').upper() or 'Text'} file")
    text = path.read_text(encoding="utf-8", errors="replace")
    if suffix == ".py":
        return _extract_python(text, rel_path)
    if suffix in {".js", ".mjs"}:
        return _extract_javascript(text, rel_path, file_type)
    if suffix in {".ps1", ".psm1"}:
        return _extract_powershell(text, rel_path, file_type)
    if suffix == ".rs":
        return _extract_rust(text, rel_path)
    if suffix == ".html":
        return _extract_html(text, rel_path)
    return ExtractedSource(
        file_type=file_type,
        purpose=fallback_purpose(rel_path, file_type),
        api_routes=_api_routes(text),
        state_files=_state_files(text),
    )


__all__ = [
    "ExtractedSource",
    "GENERATED_NAVIGATION_FILES",
    "GENERATED_NAVIGATION_PREFIXES",
    "SUMMARY_GENERATOR_FINGERPRINT",
    "SUMMARY_SCHEMA_VERSION",
    "extract_source",
    "fallback_purpose",
    "is_generated_navigation_output",
]
