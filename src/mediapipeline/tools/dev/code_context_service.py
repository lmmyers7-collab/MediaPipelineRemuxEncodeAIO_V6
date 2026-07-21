"""Read-only repository context, catalog, search, and ranged-read service."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
from collections import OrderedDict
from copy import deepcopy
from dataclasses import dataclass
from itertools import islice
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

from mediapipeline.tools.dev.context_records import (
    DEFAULT_EXCLUDED_EVIDENCE,
    ContextRecord,
    load_records,
    terms_for,
)
from mediapipeline.tools.dev.context_slice import build_context_capsule, render_capsule
from mediapipeline.tools.dev.refresh_summaries import sha256_of
from mediapipeline.tools.paths import find_repo_root


REPO_ROOT = find_repo_root(Path(__file__))
DEFAULT_INDEX_PATH = REPO_ROOT / "docs" / "generated" / "PROJECT_INDEX.jsonl"
DEFAULT_CONTEXT_BUDGET = 2000
MAX_CONTEXT_BUDGET = 8000
MAX_QUERY_LENGTH = 512
MAX_LOOKUP_RESULTS = 50
MAX_SEARCH_RESULTS = 100
DEFAULT_SEARCH_RESULTS = 40
MAX_READ_LINES = 400
MAX_READ_BYTES = 64 * 1024
MAX_SOURCE_BYTES = 2 * 1024 * 1024
SEARCH_TIMEOUT_SECONDS = 3
MAX_PREVIEW_CHARS = 500
MAX_CONTEXT_CACHE_ENTRIES = 64
RG_FILE_BATCH_SIZE = 96

ALLOWED_PREFIXES = (
    "src/mediapipeline/",
    "apps/desktop/webview/static/",
    "apps/desktop/tauri/",
    "ops/pipeline/engine/",
    "ops/pipeline/entrypoints/",
    "ops/pipeline/config/",
    "ops/pipeline/tests/",
    "ops/scripts/",
    "tests/",
    "docs/",
    ".github/",
)
ALLOWED_ROOT_FILES = frozenset(
    {
        ".gitignore",
        ".pre-commit-config.yaml",
        "AGENTS.md",
        "CHANGELOG.md",
        "README.md",
        "package.json",
        "pyproject.toml",
    }
)
DENIED_PREFIXES = (
    ".codex-remote-attachments/",
    ".git/",
    "apps/desktop/runtime/",
    "docs/archive/",
    "localbase/",
    "ops/pipeline/config/backups/",
    "ops/pipeline/runtime/",
    "ops/pipeline/tools/",
    "ops/release/changes/",
)
DENIED_PARTS = frozenset({".mypy_cache", ".pytest_cache", "__pycache__", "gen", "node_modules", "target"})
DENIED_EXACT = frozenset(
    {
        ".claude/settings.local.json",
        "ops/pipeline/config/mediapipeline_config.psd1",
        "ops/pipeline/config/mediapipeline_config_chatgpt.psd1",
    }
)
DENIED_SECRET_NAMES = frozenset({".env", "credentials.json", "secrets.json"})
DENIED_SECRET_SUFFIXES = (".key", ".p12", ".pem", ".pfx")
DEFAULT_SEARCH_EXCLUDES = (
    "docs/generated/summaries/**",
    "docs/generated/PROJECT_INDEX.jsonl",
    "docs/generated/PROJECT_INDEX.md",
)


@dataclass(frozen=True)
class ResolvedCodePath:
    relative: str
    absolute: Path


class CodeContextError(ValueError):
    """Expected, structured code-context request error."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _canonical(value: str | Path) -> str:
    text = str(value).replace("\\", "/")
    while text.startswith("./"):
        text = text[2:]
    return PurePosixPath(text).as_posix()


def _error(exc: CodeContextError) -> dict[str, Any]:
    return {"ok": False, "error": {"code": exc.code, "message": exc.message}}


def _record_dict(record: ContextRecord, *, full: bool = False) -> dict[str, Any]:
    result: dict[str, Any] = {
        "path": record.path,
        "purpose": record.purpose,
        "file_type": record.file_type,
        "owner_domain": record.owner_domain,
        "feature_group": record.feature_group,
        "layer": record.layer,
        "authority": record.authority,
        "risk_tier": record.risk_tier,
        "validation": record.validation_rung,
        "public_symbols": list(record.public_symbols[:12]),
    }
    if full:
        result.update(
            {
                "dependencies": list(record.outbound_dependencies),
                "dependents": list(record.inbound_dependents),
                "tests": list(record.associated_tests),
                "api_routes": list(record.api_routes),
                "state_files": list(record.state_files),
                "feature_groups": list(record.feature_groups),
                "source_hash": record.source_hash,
            }
        )
    return result


class CodeContextService:
    """Serve bounded, read-only repository context without owning index generation."""

    def __init__(self, *, root: Path = REPO_ROOT, index_path: Path | None = None) -> None:
        self.root = root.resolve()
        self.index_path = (index_path or (self.root / "docs" / "generated" / "PROJECT_INDEX.jsonl")).resolve()
        self.index_error = ""
        self.records: list[ContextRecord] = []
        self.records_by_path: dict[str, ContextRecord] = {}
        self._context_cache: OrderedDict[tuple[str, int, bool], dict[str, Any]] = OrderedDict()
        self._load_index()

    def _load_index(self) -> None:
        try:
            self.records = load_records(self.index_path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            self.index_error = str(exc)
            self.records = []
        self.records_by_path = {record.path: record for record in self.records}

    def health(self, *, stale_paths: Iterable[str] = ()) -> dict[str, Any]:
        stale = sorted(set(stale_paths), key=lambda value: (value.casefold(), value))
        return {
            "index": "available" if self.records else "unavailable",
            "record_count": len(self.records),
            "index_error": self.index_error or None,
            "stale_paths": stale,
            "search_backend": "rg" if shutil.which("rg") else "python",
        }

    def _is_allowed_relative(self, relative: str) -> bool:
        lowered = relative.casefold()
        parts = {part.casefold() for part in PurePosixPath(relative).parts}
        if lowered in DENIED_EXACT:
            return False
        if any(lowered == prefix.rstrip("/") or lowered.startswith(prefix) for prefix in DENIED_PREFIXES):
            return False
        if parts.intersection(DENIED_PARTS):
            return False
        name = PurePosixPath(relative).name.casefold()
        if name in DENIED_SECRET_NAMES or name.endswith(DENIED_SECRET_SUFFIXES):
            return False
        return relative in ALLOWED_ROOT_FILES or any(
            lowered == prefix.rstrip("/").casefold() or lowered.startswith(prefix.casefold()) for prefix in ALLOWED_PREFIXES
        )

    def resolve_path(self, path: str, *, require_file: bool = True) -> ResolvedCodePath:
        if not path or not path.strip():
            raise CodeContextError("invalid_path", "path must not be empty")
        candidate = Path(path)
        if candidate.is_absolute():
            raise CodeContextError("absolute_path", "absolute paths are not allowed")
        relative = _canonical(path.strip())
        if ".." in PurePosixPath(relative).parts or not self._is_allowed_relative(relative):
            raise CodeContextError("path_denied", "path is outside the active read-only repository surface")
        absolute = (self.root / Path(relative)).resolve()
        try:
            absolute.relative_to(self.root)
        except ValueError as exc:
            raise CodeContextError("path_escape", "resolved path escapes the repository") from exc
        if require_file and not absolute.is_file():
            raise CodeContextError("not_found", "requested repository file does not exist")
        if not require_file and not absolute.exists():
            raise CodeContextError("not_found", "requested repository path does not exist")
        return ResolvedCodePath(relative=relative, absolute=absolute)

    def _stale_paths(self, paths: Iterable[str]) -> list[str]:
        stale: list[str] = []
        for path in paths:
            record = self.records_by_path.get(path)
            if not record:
                continue
            try:
                if sha256_of(self.root / path) != record.source_hash:
                    stale.append(path)
            except OSError:
                stale.append(path)
        return stale

    def repo_context(self, task: str, *, budget: int = DEFAULT_CONTEXT_BUDGET, include_history: bool = False) -> dict[str, Any]:
        try:
            if not task or not task.strip():
                raise CodeContextError("invalid_task", "task must not be empty")
            if len(task) > MAX_QUERY_LENGTH:
                raise CodeContextError("task_too_long", f"task must be at most {MAX_QUERY_LENGTH} characters")
            if not 200 <= budget <= MAX_CONTEXT_BUDGET:
                raise CodeContextError("invalid_budget", f"budget must be between 200 and {MAX_CONTEXT_BUDGET}")
            if not self.records:
                raise CodeContextError("index_unavailable", "generated context index is unavailable; use the context_slice fallback after regeneration")
            cache_key = (task.strip(), budget, include_history)
            cached = self._context_cache.get(cache_key)
            if cached is not None:
                self._context_cache.move_to_end(cache_key)
                payload = deepcopy(cached)
            else:
                capsule = build_context_capsule(
                    self.records,
                    task=task.strip(),
                    budget=budget,
                    include_history=include_history,
                    output_format="json",
                )
                payload = json.loads(render_capsule(capsule, output_format="json"))
                self._context_cache[cache_key] = deepcopy(payload)
                if len(self._context_cache) > MAX_CONTEXT_CACHE_ENTRIES:
                    self._context_cache.popitem(last=False)
            paths = [item["path"] for item in payload.get("items", [])]
            payload.update({"ok": True, "health": self.health(stale_paths=self._stale_paths(paths))})
            return payload
        except CodeContextError as exc:
            return {**_error(exc), "health": self.health()}

    def code_lookup(
        self,
        query: str,
        *,
        feature_id: str | None = None,
        owner_domain: str | None = None,
        file_type: str | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        try:
            if not query or not query.strip():
                raise CodeContextError("invalid_query", "query must not be empty")
            if len(query) > MAX_QUERY_LENGTH:
                raise CodeContextError("query_too_long", f"query must be at most {MAX_QUERY_LENGTH} characters")
            if not 1 <= limit <= MAX_LOOKUP_RESULTS:
                raise CodeContextError("invalid_limit", f"limit must be between 1 and {MAX_LOOKUP_RESULTS}")
            if not self.records:
                raise CodeContextError("index_unavailable", "generated context index is unavailable")
            normalized_query = _canonical(query.strip())
            exact = self.records_by_path.get(normalized_query)
            if exact:
                stale = self._stale_paths((exact.path,))
                return {"ok": True, "exact": True, "item": _record_dict(exact, full=True), "health": self.health(stale_paths=stale)}

            query_terms = set(terms_for(query))
            query_folded = query.casefold()
            ranked: list[tuple[int, ContextRecord]] = []
            for record in self.records:
                if record.evidence_category in DEFAULT_EXCLUDED_EVIDENCE:
                    continue
                if feature_id and feature_id not in {record.feature_group, *record.feature_groups}:
                    continue
                if owner_domain and record.owner_domain.casefold() != owner_domain.casefold():
                    continue
                if file_type and record.file_type.casefold() != file_type.casefold():
                    continue
                haystack = " ".join((record.path, record.purpose, *record.public_symbols, *record.api_routes, *record.state_files)).casefold()
                overlap = query_terms.intersection(record.relevance_terms)
                score = len(overlap) * 10
                if query_folded in haystack:
                    score += 30
                if query_folded in record.path.casefold():
                    score += 20
                if score:
                    ranked.append((score, record))
            ranked.sort(key=lambda item: (-item[0], item[1].path.casefold(), item[1].path))
            selected = ranked[:limit]
            return {
                "ok": True,
                "exact": False,
                "query": query,
                "items": [{**_record_dict(record), "score": score} for score, record in selected],
                "omitted_count": max(0, len(ranked) - len(selected)),
                "health": self.health(stale_paths=self._stale_paths(record.path for _, record in selected)),
            }
        except CodeContextError as exc:
            return {**_error(exc), "health": self.health()}

    def _search_targets(self, path_prefix: str | None) -> list[ResolvedCodePath]:
        if path_prefix:
            return [self.resolve_path(path_prefix, require_file=False)]
        targets: list[ResolvedCodePath] = []
        for prefix in ALLOWED_PREFIXES:
            absolute = self.root / prefix
            if absolute.exists() and self._is_allowed_relative(prefix.rstrip("/")):
                targets.append(ResolvedCodePath(prefix.rstrip("/"), absolute))
        for filename in ALLOWED_ROOT_FILES:
            absolute = self.root / filename
            if absolute.is_file():
                targets.append(ResolvedCodePath(filename, absolute))
        return targets

    def _search_with_rg(
        self,
        query: str,
        *,
        targets: list[ResolvedCodePath],
        regex: bool,
        case_sensitive: bool,
        max_results: int,
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        deadline = time.monotonic() + SEARCH_TIMEOUT_SECONDS
        files = iter(self._iter_python_search_files(targets))
        while batch := list(islice(files, RG_FILE_BATCH_SIZE)):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise CodeContextError("search_timeout", f"code search exceeded {SEARCH_TIMEOUT_SECONDS} seconds")
            command = ["rg", "--json", "--line-number", "--column", "--color", "never", "--hidden"]
            if not regex:
                command.append("--fixed-strings")
            if not case_sensitive:
                command.append("--ignore-case")
            command.extend(("--", query))
            command.extend(str(path) for path in batch)
            try:
                completed = subprocess.run(
                    command,
                    cwd=self.root,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=remaining,
                    check=False,
                )
            except subprocess.TimeoutExpired as exc:
                raise CodeContextError("search_timeout", f"code search exceeded {SEARCH_TIMEOUT_SECONDS} seconds") from exc
            if completed.returncode not in {0, 1}:
                detail = completed.stderr.strip().splitlines()[-1] if completed.stderr.strip() else "ripgrep failed"
                raise CodeContextError("search_failed", detail[:MAX_PREVIEW_CHARS])
            for line in completed.stdout.splitlines():
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if event.get("type") != "match":
                    continue
                data = event["data"]
                absolute_path = Path(data["path"]["text"])
                try:
                    relative = _canonical(absolute_path.resolve().relative_to(self.root))
                except (OSError, ValueError):
                    continue
                submatches = data.get("submatches") or []
                column = int(submatches[0].get("start", 0)) + 1 if submatches else 1
                preview = data.get("lines", {}).get("text", "").rstrip("\r\n")[:MAX_PREVIEW_CHARS]
                results.append({"path": relative, "line": int(data["line_number"]), "column": column, "preview": preview})
                if len(results) >= max_results:
                    return results
        return results

    def _iter_python_search_files(self, targets: Iterable[ResolvedCodePath]) -> Iterable[Path]:
        for target in targets:
            if target.absolute.is_file():
                yield target.absolute
                continue
            for directory, child_directories, filenames in os.walk(target.absolute, followlinks=False):
                directory_path = Path(directory)
                allowed_directories: list[str] = []
                for child in child_directories:
                    try:
                        relative = _canonical((directory_path / child).resolve().relative_to(self.root))
                    except (OSError, ValueError):
                        continue
                    if self._is_allowed_relative(relative):
                        allowed_directories.append(child)
                child_directories[:] = sorted(allowed_directories, key=str.casefold)
                for filename in sorted(filenames, key=str.casefold):
                    candidate = directory_path / filename
                    try:
                        relative = _canonical(candidate.resolve().relative_to(self.root))
                    except (OSError, ValueError):
                        continue
                    if self._is_allowed_relative(relative) and not any(
                        PurePosixPath(relative).match(pattern) for pattern in DEFAULT_SEARCH_EXCLUDES
                    ):
                        yield candidate

    def _search_with_python(
        self,
        query: str,
        *,
        targets: list[ResolvedCodePath],
        regex: bool,
        case_sensitive: bool,
        max_results: int,
    ) -> list[dict[str, Any]]:
        flags = 0 if case_sensitive else re.IGNORECASE
        try:
            pattern = re.compile(query if regex else re.escape(query), flags)
        except re.error as exc:
            raise CodeContextError("invalid_regex", str(exc)) from exc
        results: list[dict[str, Any]] = []
        deadline = time.monotonic() + SEARCH_TIMEOUT_SECONDS
        for path in self._iter_python_search_files(targets):
            if time.monotonic() > deadline:
                raise CodeContextError("search_timeout", f"code search exceeded {SEARCH_TIMEOUT_SECONDS} seconds")
            try:
                if path.stat().st_size > MAX_SOURCE_BYTES:
                    continue
                raw = path.read_bytes()
                if b"\x00" in raw:
                    continue
                text = raw.decode("utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            relative = _canonical(path.resolve().relative_to(self.root))
            for line_number, line in enumerate(text.splitlines(), start=1):
                if time.monotonic() > deadline:
                    raise CodeContextError("search_timeout", f"code search exceeded {SEARCH_TIMEOUT_SECONDS} seconds")
                match = pattern.search(line)
                if not match:
                    continue
                results.append({"path": relative, "line": line_number, "column": match.start() + 1, "preview": line[:MAX_PREVIEW_CHARS]})
                if len(results) >= max_results:
                    return results
        return results

    def code_search(
        self,
        query: str,
        *,
        path_prefix: str | None = None,
        regex: bool = False,
        case_sensitive: bool = False,
        max_results: int = DEFAULT_SEARCH_RESULTS,
    ) -> dict[str, Any]:
        try:
            if not query or not query.strip():
                raise CodeContextError("invalid_query", "query must not be empty")
            if len(query) > MAX_QUERY_LENGTH:
                raise CodeContextError("query_too_long", f"query must be at most {MAX_QUERY_LENGTH} characters")
            if not 1 <= max_results <= MAX_SEARCH_RESULTS:
                raise CodeContextError("invalid_limit", f"max_results must be between 1 and {MAX_SEARCH_RESULTS}")
            if regex:
                try:
                    re.compile(query)
                except re.error as exc:
                    raise CodeContextError("invalid_regex", str(exc)) from exc
            targets = self._search_targets(path_prefix)
            backend = "rg" if shutil.which("rg") else "python"
            if backend == "rg":
                results = self._search_with_rg(
                    query,
                    targets=targets,
                    regex=regex,
                    case_sensitive=case_sensitive,
                    max_results=max_results,
                )
            else:
                results = self._search_with_python(
                    query,
                    targets=targets,
                    regex=regex,
                    case_sensitive=case_sensitive,
                    max_results=max_results,
                )
            return {
                "ok": True,
                "query": query,
                "backend": backend,
                "items": results,
                "truncated": len(results) >= max_results,
                "health": self.health(stale_paths=self._stale_paths(item["path"] for item in results)),
            }
        except CodeContextError as exc:
            return {**_error(exc), "health": self.health()}

    def code_read(self, path: str, *, start_line: int = 1, end_line: int | None = None, detail: str = "compact") -> dict[str, Any]:
        try:
            if detail not in {"compact", "full"}:
                raise CodeContextError("invalid_detail", "detail must be compact or full")
            if start_line < 1:
                raise CodeContextError("invalid_range", "start_line must be at least 1")
            if end_line is not None and end_line < start_line:
                raise CodeContextError("invalid_range", "end_line must be greater than or equal to start_line")
            resolved = self.resolve_path(path)
            if resolved.absolute.stat().st_size > MAX_SOURCE_BYTES:
                raise CodeContextError("file_too_large", f"file exceeds the {MAX_SOURCE_BYTES}-byte read limit")
            raw = resolved.absolute.read_bytes()
            if b"\x00" in raw:
                raise CodeContextError("binary_file", "binary files cannot be returned")
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise CodeContextError("invalid_encoding", "file is not UTF-8 text") from exc
            lines = text.splitlines()
            requested_end = end_line if end_line is not None else min(len(lines), start_line + MAX_READ_LINES - 1)
            actual_end = min(requested_end, len(lines), start_line + MAX_READ_LINES - 1)
            selected: list[dict[str, Any]] = []
            byte_count = 0
            for number in range(start_line, actual_end + 1):
                content = lines[number - 1] if number <= len(lines) else ""
                encoded_size = len(content.encode("utf-8")) + 16
                if selected and byte_count + encoded_size > MAX_READ_BYTES:
                    break
                selected.append({"line": number, "text": content})
                byte_count += encoded_size
            returned_end = selected[-1]["line"] if selected else min(start_line - 1, len(lines))
            record = self.records_by_path.get(resolved.relative)
            stale = self._stale_paths((resolved.relative,))
            result: dict[str, Any] = {
                "ok": True,
                "path": resolved.relative,
                "start_line": start_line,
                "end_line": returned_end,
                "total_lines": len(lines),
                "lines": selected,
                "truncated": returned_end < min(requested_end, len(lines)),
                "source_hash": sha256_of(resolved.absolute),
                "index_stale": bool(stale),
                "health": self.health(stale_paths=stale),
            }
            if detail == "full" and record:
                result["catalog"] = _record_dict(record, full=True)
            return result
        except (OSError, CodeContextError) as exc:
            structured = exc if isinstance(exc, CodeContextError) else CodeContextError("read_failed", str(exc))
            return {**_error(structured), "health": self.health()}


__all__ = [
    "CodeContextError",
    "CodeContextService",
    "DEFAULT_CONTEXT_BUDGET",
    "DEFAULT_INDEX_PATH",
    "REPO_ROOT",
]
