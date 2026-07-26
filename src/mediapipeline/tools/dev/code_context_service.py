"""Read-only repository context, catalog, search, and ranged-read service."""

from __future__ import annotations

import atexit
import functools
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import weakref
from collections import OrderedDict
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Iterable

from mediapipeline.tools.dev.context_records import (
    RETRIEVAL_TIER_ACTIVE,
    ContextRecord,
    normalize_retrieval_text,
    normalize_retrieval_tier,
    record_is_retrievable,
    records_from_jsonl,
    retrieval_terms_for,
)
from mediapipeline.tools.dev.context_slice import budget_tolerance, build_context_capsule, estimate_tokens, render_capsule
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
MAX_CONTEXT_CACHE_ENTRIES = 256
MAX_LOOKUP_CACHE_ENTRIES = 256
MIN_BUNDLE_BUDGET = 800
MAX_BUNDLE_FILES = 8
METRICS_EMIT_INTERVAL = 100
LATENCY_BUCKETS_MS = (10, 25, 50, 100, 250, 500, 1000)

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
    "localbase/",
    "ops/pipeline/config/backups/",
    "ops/pipeline/runtime/",
    "ops/pipeline/tools/",
)
OPT_IN_PREFIXES = (
    "docs/archive/",
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
    "docs/generated/**",
)


@dataclass(frozen=True)
class ResolvedCodePath:
    relative: str
    absolute: Path


@dataclass(frozen=True)
class BundleFileRequest:
    path: str
    start_line: int = 1
    end_line: int | None = None


_LIVE_SERVICES: weakref.WeakSet[CodeContextService] = weakref.WeakSet()


def _emit_live_metrics() -> None:
    for service in list(_LIVE_SERVICES):
        service.emit_metrics()


atexit.register(_emit_live_metrics)


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


def _measured(
    tool_name: str,
) -> Callable[[Callable[..., dict[str, Any]]], Callable[..., dict[str, Any]]]:
    def decorate(function: Callable[..., dict[str, Any]]) -> Callable[..., dict[str, Any]]:
        @functools.wraps(function)
        def wrapped(self: CodeContextService, *args: Any, **kwargs: Any) -> dict[str, Any]:
            started = time.perf_counter()
            if tool_name in {"repo_context", "code_lookup"}:
                with self._lock:
                    result = function(self, *args, **kwargs)
            else:
                result = function(self, *args, **kwargs)
            self._record_metric(tool_name, result, (time.perf_counter() - started) * 1000)
            return result

        return wrapped

    return decorate


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
        self._lock = threading.RLock()
        self.index_error = ""
        self.reload_error = ""
        self.index_revision: str | None = None
        self._observed_index_signature: tuple[int, int] | None = None
        self.records: list[ContextRecord] = []
        self.records_by_path: dict[str, ContextRecord] = {}
        self._context_cache: OrderedDict[tuple[str, str, int, str], dict[str, Any]] = OrderedDict()
        self._lookup_cache: OrderedDict[tuple[object, ...], dict[str, Any]] = OrderedDict()
        self._started = time.monotonic()
        self._metrics: dict[str, Any] = {
            "requests": {},
            "errors": {},
            "latency_buckets_ms": {},
            "cache_hits": {"context": 0, "lookup": 0},
            "cache_misses": {"context": 0, "lookup": 0},
            "response_tokens_total": 0,
            "response_tokens_max": 0,
            "truncations": 0,
            "stale_records": 0,
            "reloads": {"attempted": 0, "succeeded": 0, "failed": 0},
        }
        self._load_index(initial=True)
        _LIVE_SERVICES.add(self)

    def _index_signature(self) -> tuple[int, int]:
        stat = self.index_path.stat()
        return (stat.st_mtime_ns, stat.st_size)

    def _read_index_snapshot(self) -> tuple[bytes, tuple[int, int]]:
        for _ in range(2):
            before = self._index_signature()
            raw = self.index_path.read_bytes()
            after = self._index_signature()
            if before == after:
                return raw, after
        raise OSError("generated context index changed while it was being read")

    @staticmethod
    def _validate_records(records: list[ContextRecord]) -> None:
        if not records:
            raise ValueError("generated context index contains no records")
        paths = [record.path for record in records]
        if len(paths) != len(set(paths)):
            raise ValueError("generated context index contains duplicate paths")
        folded = [path.casefold() for path in paths]
        if len(folded) != len(set(folded)):
            raise ValueError("generated context index contains case-colliding paths")

    def _load_index(self, *, initial: bool = False) -> None:
        if not initial:
            self._metrics["reloads"]["attempted"] += 1
        try:
            raw, signature = self._read_index_snapshot()
            records = records_from_jsonl(raw.decode("utf-8"))
            self._validate_records(records)
            revision = hashlib.sha256(raw).hexdigest()
        except (OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError) as exc:
            message = str(exc)
            if initial:
                self.index_error = message
                self.records = []
                self.records_by_path = {}
            else:
                self.reload_error = message
                self._metrics["reloads"]["failed"] += 1
                try:
                    self._observed_index_signature = self._index_signature()
                except OSError:
                    self._observed_index_signature = None
            return
        self.records = records
        self.records_by_path = {record.path: record for record in records}
        self.index_revision = revision
        self._observed_index_signature = signature
        self.index_error = ""
        self.reload_error = ""
        self._context_cache.clear()
        self._lookup_cache.clear()
        if not initial:
            self._metrics["reloads"]["succeeded"] += 1

    def _refresh_index_if_changed(self) -> None:
        with self._lock:
            try:
                signature = self._index_signature()
            except OSError as exc:
                self.reload_error = str(exc)
                return
            if signature != self._observed_index_signature:
                self._load_index()

    def _metrics_snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "schema_version": "mediapipeline_code_mcp_metrics.v1",
                "uptime_seconds": round(max(0.0, time.monotonic() - self._started), 3),
                **deepcopy(self._metrics),
            }

    def emit_metrics(self) -> None:
        if sum(self._metrics["requests"].values()) == 0:
            return
        print("mediapipeline-code-metrics " + json.dumps(self._metrics_snapshot(), sort_keys=True), file=sys.stderr, flush=True)

    def _record_metric(self, tool_name: str, result: dict[str, Any], elapsed_ms: float) -> None:
        with self._lock:
            requests = self._metrics["requests"]
            requests[tool_name] = requests.get(tool_name, 0) + 1
            buckets = self._metrics["latency_buckets_ms"].setdefault(
                tool_name,
                {str(limit): 0 for limit in LATENCY_BUCKETS_MS} | {"overflow": 0},
            )
            bucket = next((str(limit) for limit in LATENCY_BUCKETS_MS if elapsed_ms <= limit), "overflow")
            buckets[bucket] += 1
            if not result.get("ok"):
                code = str(result.get("error", {}).get("code", "unknown"))
                errors = self._metrics["errors"]
                errors[code] = errors.get(code, 0) + 1
            if result.get("truncated") or any(item.get("truncated") for item in result.get("items", ())):
                self._metrics["truncations"] += 1
            self._metrics["stale_records"] += len(result.get("health", {}).get("stale_paths", ()))
            tokens = estimate_tokens(json.dumps(result, ensure_ascii=False, separators=(",", ":"), sort_keys=True))
            self._metrics["response_tokens_total"] += tokens
            self._metrics["response_tokens_max"] = max(self._metrics["response_tokens_max"], tokens)
            total = sum(requests.values())
        if total % METRICS_EMIT_INTERVAL == 0:
            self.emit_metrics()

    def health(self, *, stale_paths: Iterable[str] = ()) -> dict[str, Any]:
        stale = sorted(set(stale_paths), key=lambda value: (value.casefold(), value))
        with self._lock:
            return {
                "index": "available" if self.records else "unavailable",
                "record_count": len(self.records),
                "index_error": self.index_error or None,
                "index_revision": self.index_revision,
                "reload_status": "degraded" if self.reload_error else ("ok" if self.records else "unavailable"),
                "reload_error": self.reload_error or None,
                "stale_paths": stale,
                "search_backend": "rg" if shutil.which("rg") else "python",
            }

    def _is_allowed_relative(self, relative: str, *, include_opt_in: bool = False) -> bool:
        lowered = relative.casefold()
        parts = {part.casefold() for part in PurePosixPath(relative).parts}
        if lowered in DENIED_EXACT:
            return False
        if any(lowered == prefix.rstrip("/") or lowered.startswith(prefix) for prefix in DENIED_PREFIXES):
            return False
        if not include_opt_in and any(
            lowered == prefix.rstrip("/") or lowered.startswith(prefix)
            for prefix in OPT_IN_PREFIXES
        ):
            return False
        if parts.intersection(DENIED_PARTS):
            return False
        name = PurePosixPath(relative).name.casefold()
        if name in DENIED_SECRET_NAMES or name.endswith(DENIED_SECRET_SUFFIXES):
            return False
        if include_opt_in and any(
            lowered == prefix.rstrip("/") or lowered.startswith(prefix)
            for prefix in OPT_IN_PREFIXES
        ):
            return True
        return relative in ALLOWED_ROOT_FILES or any(
            lowered == prefix.rstrip("/").casefold() or lowered.startswith(prefix.casefold()) for prefix in ALLOWED_PREFIXES
        )

    def resolve_path(
        self,
        path: str,
        *,
        require_file: bool = True,
        include_opt_in: bool = False,
    ) -> ResolvedCodePath:
        if not path or not path.strip():
            raise CodeContextError("invalid_path", "path must not be empty")
        candidate = Path(path)
        if candidate.is_absolute():
            raise CodeContextError("absolute_path", "absolute paths are not allowed")
        relative = _canonical(path.strip())
        if ".." in PurePosixPath(relative).parts or not self._is_allowed_relative(
            relative,
            include_opt_in=include_opt_in,
        ):
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

    @_measured("repo_context")
    def repo_context(
        self,
        task: str,
        *,
        budget: int = DEFAULT_CONTEXT_BUDGET,
        include_history: bool = False,
        retrieval_tier: str = RETRIEVAL_TIER_ACTIVE,
    ) -> dict[str, Any]:
        try:
            self._refresh_index_if_changed()
            if not task or not task.strip():
                raise CodeContextError("invalid_task", "task must not be empty")
            if len(task) > MAX_QUERY_LENGTH:
                raise CodeContextError("task_too_long", f"task must be at most {MAX_QUERY_LENGTH} characters")
            if not 200 <= budget <= MAX_CONTEXT_BUDGET:
                raise CodeContextError("invalid_budget", f"budget must be between 200 and {MAX_CONTEXT_BUDGET}")
            if not self.records:
                raise CodeContextError("index_unavailable", "generated context index is unavailable; use the context_slice fallback after regeneration")
            try:
                tier = normalize_retrieval_tier(retrieval_tier, include_history=include_history)
            except ValueError as exc:
                raise CodeContextError("invalid_retrieval_tier", str(exc)) from exc
            cache_key = (self.index_revision or "", normalize_retrieval_text(task), budget, tier)
            with self._lock:
                cached = self._context_cache.get(cache_key)
                if cached is not None:
                    self._context_cache.move_to_end(cache_key)
                    self._metrics["cache_hits"]["context"] += 1
                    payload = deepcopy(cached)
                else:
                    self._metrics["cache_misses"]["context"] += 1
            if cached is None:
                capsule = build_context_capsule(
                    self.records,
                    task=task.strip(),
                    budget=budget,
                    retrieval_tier=tier,
                    output_format="json",
                )
                payload = json.loads(render_capsule(capsule, output_format="json"))
                with self._lock:
                    self._context_cache[cache_key] = deepcopy(payload)
                    if len(self._context_cache) > MAX_CONTEXT_CACHE_ENTRIES:
                        self._context_cache.popitem(last=False)
            payload["task"] = task.strip()
            paths = [item["path"] for item in payload.get("items", [])]
            payload.update({"ok": True, "health": self.health(stale_paths=self._stale_paths(paths))})
            return payload
        except CodeContextError as exc:
            return {**_error(exc), "health": self.health()}

    @_measured("code_lookup")
    def code_lookup(
        self,
        query: str,
        *,
        feature_id: str | None = None,
        owner_domain: str | None = None,
        file_type: str | None = None,
        limit: int = 20,
        retrieval_tier: str = RETRIEVAL_TIER_ACTIVE,
    ) -> dict[str, Any]:
        try:
            self._refresh_index_if_changed()
            if not query or not query.strip():
                raise CodeContextError("invalid_query", "query must not be empty")
            if len(query) > MAX_QUERY_LENGTH:
                raise CodeContextError("query_too_long", f"query must be at most {MAX_QUERY_LENGTH} characters")
            if not 1 <= limit <= MAX_LOOKUP_RESULTS:
                raise CodeContextError("invalid_limit", f"limit must be between 1 and {MAX_LOOKUP_RESULTS}")
            if not self.records:
                raise CodeContextError("index_unavailable", "generated context index is unavailable")
            try:
                tier = normalize_retrieval_tier(retrieval_tier)
            except ValueError as exc:
                raise CodeContextError("invalid_retrieval_tier", str(exc)) from exc
            normalized_query = _canonical(query.strip())
            cache_key = (
                self.index_revision or "",
                normalize_retrieval_text(query),
                normalize_retrieval_text(feature_id or ""),
                normalize_retrieval_text(owner_domain or ""),
                normalize_retrieval_text(file_type or ""),
                limit,
                tier,
            )
            with self._lock:
                cached = self._lookup_cache.get(cache_key)
                if cached is not None:
                    self._lookup_cache.move_to_end(cache_key)
                    self._metrics["cache_hits"]["lookup"] += 1
                    payload = deepcopy(cached)
                else:
                    self._metrics["cache_misses"]["lookup"] += 1
            if cached is not None:
                selected_paths = (
                    (payload["item"]["path"],)
                    if payload.get("exact")
                    else tuple(item["path"] for item in payload.get("items", ()))
                )
                payload["query"] = query
                payload["health"] = self.health(stale_paths=self._stale_paths(selected_paths))
                return payload
            exact = self.records_by_path.get(normalized_query)
            if exact:
                stale = self._stale_paths((exact.path,))
                payload = {
                    "ok": True,
                    "exact": True,
                    "query": query,
                    "item": _record_dict(exact, full=True),
                    "health": self.health(stale_paths=stale),
                }
                with self._lock:
                    self._lookup_cache[cache_key] = deepcopy(payload)
                    if len(self._lookup_cache) > MAX_LOOKUP_CACHE_ENTRIES:
                        self._lookup_cache.popitem(last=False)
                return payload

            query_terms = set(retrieval_terms_for(query))
            query_folded = normalize_retrieval_text(query)
            ranked: list[tuple[int, ContextRecord]] = []
            for record in self.records:
                exact_symbol = any(
                    query_folded == normalize_retrieval_text(symbol)
                    for symbol in record.public_symbols
                )
                if not exact_symbol and not record_is_retrievable(record, tier):
                    continue
                if feature_id and feature_id not in {record.feature_group, *record.feature_groups}:
                    continue
                if owner_domain and record.owner_domain.casefold() != owner_domain.casefold():
                    continue
                if file_type and record.file_type.casefold() != file_type.casefold():
                    continue
                haystack = normalize_retrieval_text(
                    record.path,
                    record.purpose,
                    record.public_symbols,
                    record.api_routes,
                    record.state_files,
                )
                overlap = query_terms.intersection(record.relevance_terms)
                score = len(overlap) * 10
                if query_folded in haystack:
                    score += 30
                if query_folded in normalize_retrieval_text(record.path):
                    score += 20
                score += len(query_terms.intersection(retrieval_terms_for(record.path))) * 8
                score += len(query_terms.intersection(retrieval_terms_for(record.public_symbols))) * 12
                score += len(query_terms.intersection(retrieval_terms_for(record.api_routes, record.state_files))) * 9
                if any(query_folded == normalize_retrieval_text(symbol) for symbol in record.public_symbols):
                    score += 60
                if score:
                    ranked.append((score, record))
            ranked.sort(key=lambda item: (-item[0], item[1].path.casefold(), item[1].path))
            selected = ranked[:limit]
            payload = {
                "ok": True,
                "exact": False,
                "query": query,
                "retrieval_tier": tier,
                "items": [{**_record_dict(record), "score": score} for score, record in selected],
                "omitted_count": max(0, len(ranked) - len(selected)),
                "health": self.health(stale_paths=self._stale_paths(record.path for _, record in selected)),
            }
            with self._lock:
                self._lookup_cache[cache_key] = deepcopy(payload)
                if len(self._lookup_cache) > MAX_LOOKUP_CACHE_ENTRIES:
                    self._lookup_cache.popitem(last=False)
            return payload
        except CodeContextError as exc:
            return {**_error(exc), "health": self.health()}

    def _search_targets(self, path_prefix: str | None) -> list[ResolvedCodePath]:
        if path_prefix:
            return [self.resolve_path(path_prefix, require_file=False, include_opt_in=True)]
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
        include_opt_in = any(
            any(target.relative.casefold() == prefix.rstrip("/") or target.relative.casefold().startswith(prefix) for prefix in OPT_IN_PREFIXES)
            for target in targets
        )
        include_generated = any(target.relative.casefold().startswith("docs/generated") for target in targets)
        command = [
            "rg",
            "--json",
            "--line-number",
            "--column",
            "--color",
            "never",
            "--hidden",
            "--no-ignore",
            "--max-filesize",
            str(MAX_SOURCE_BYTES),
        ]
        deny_globs = [
            "!**/.env",
            "!**/credentials.json",
            "!**/secrets.json",
            "!**/*.key",
            "!**/*.p12",
            "!**/*.pem",
            "!**/*.pfx",
            "!**/.mypy_cache/**",
            "!**/.pytest_cache/**",
            "!**/__pycache__/**",
            "!**/node_modules/**",
            "!**/target/**",
            "!ops/pipeline/config/backups/**",
            "!ops/pipeline/config/MediaPipeline_config.psd1",
            "!ops/pipeline/config/MediaPipeline_config_chatgpt.psd1",
        ]
        if not include_opt_in:
            deny_globs.extend(("!docs/archive/**", "!ops/release/changes/**"))
        if not include_generated:
            deny_globs.append("!docs/generated/**")
        for pattern in deny_globs:
            command.extend(("--iglob", pattern))
        if not regex:
            command.append("--fixed-strings")
        if not case_sensitive:
            command.append("--ignore-case")
        command.extend(("--", query))
        command.extend(str(target.absolute) for target in targets)
        try:
            completed = subprocess.run(
                command,
                cwd=self.root,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=SEARCH_TIMEOUT_SECONDS,
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
            raw_path = Path(data["path"]["text"])
            absolute_path = raw_path if raw_path.is_absolute() else self.root / raw_path
            try:
                relative = _canonical(absolute_path.resolve().relative_to(self.root))
            except (OSError, ValueError):
                continue
            excluded = not include_generated and any(PurePosixPath(relative).match(pattern) for pattern in DEFAULT_SEARCH_EXCLUDES)
            if excluded or not self._is_allowed_relative(relative, include_opt_in=include_opt_in):
                continue
            submatches = data.get("submatches") or []
            column = int(submatches[0].get("start", 0)) + 1 if submatches else 1
            preview = data.get("lines", {}).get("text", "").rstrip("\r\n")[:MAX_PREVIEW_CHARS]
            results.append({"path": relative, "line": int(data["line_number"]), "column": column, "preview": preview})
        results.sort(
            key=lambda item: (
                item["path"].casefold().startswith(("docs/", ".github/")),
                item["path"].casefold(),
                item["path"],
                item["line"],
                item["column"],
            )
        )
        return results[:max_results]

    def _iter_python_search_files(self, targets: Iterable[ResolvedCodePath]) -> Iterable[Path]:
        for target in targets:
            target_lower = target.relative.casefold()
            include_opt_in = any(
                target_lower == prefix.rstrip("/") or target_lower.startswith(prefix)
                for prefix in OPT_IN_PREFIXES
            )
            apply_default_excludes = not target_lower.startswith("docs/generated")
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
                    default_excluded = apply_default_excludes and (
                        relative.casefold() == "docs/generated"
                        or relative.casefold().startswith("docs/generated/")
                    )
                    if not default_excluded and self._is_allowed_relative(
                        relative,
                        include_opt_in=include_opt_in,
                    ):
                        allowed_directories.append(child)
                child_directories[:] = sorted(allowed_directories, key=str.casefold)
                for filename in sorted(filenames, key=str.casefold):
                    candidate = directory_path / filename
                    try:
                        relative = _canonical(candidate.resolve().relative_to(self.root))
                    except (OSError, ValueError):
                        continue
                    excluded = apply_default_excludes and (
                        relative.casefold().startswith("docs/generated/")
                        or any(PurePosixPath(relative).match(pattern) for pattern in DEFAULT_SEARCH_EXCLUDES)
                    )
                    if self._is_allowed_relative(relative, include_opt_in=include_opt_in) and not excluded:
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

    @_measured("code_search")
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
            self._refresh_index_if_changed()
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

    @_measured("code_read")
    def code_read(self, path: str, *, start_line: int = 1, end_line: int | None = None, detail: str = "compact") -> dict[str, Any]:
        try:
            self._refresh_index_if_changed()
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

    @_measured("code_bundle")
    def code_bundle(self, files: list[BundleFileRequest | dict[str, Any]], *, budget: int = 3000) -> dict[str, Any]:
        try:
            self._refresh_index_if_changed()
            if not 1 <= len(files) <= MAX_BUNDLE_FILES:
                raise CodeContextError("invalid_files", f"files must contain between 1 and {MAX_BUNDLE_FILES} entries")
            if not MIN_BUNDLE_BUDGET <= budget <= MAX_CONTEXT_BUDGET:
                raise CodeContextError(
                    "invalid_budget",
                    f"budget must be between {MIN_BUNDLE_BUDGET} and {MAX_CONTEXT_BUDGET}",
                )
            requests: list[BundleFileRequest] = []
            for item in files:
                try:
                    request = item if isinstance(item, BundleFileRequest) else BundleFileRequest(**item)
                except (TypeError, ValueError) as exc:
                    raise CodeContextError("invalid_files", f"invalid bundle file request: {exc}") from exc
                if request.start_line < 1:
                    raise CodeContextError("invalid_range", "start_line must be at least 1")
                if request.end_line is not None and request.end_line < request.start_line:
                    raise CodeContextError("invalid_range", "end_line must be greater than or equal to start_line")
                requests.append(request)

            prepared: list[dict[str, Any]] = []
            seen: set[str] = set()
            for request in requests:
                resolved = self.resolve_path(request.path)
                duplicate_key = resolved.relative.casefold()
                if duplicate_key in seen:
                    raise CodeContextError("duplicate_path", f"duplicate bundle path: {resolved.relative}")
                seen.add(duplicate_key)
                if resolved.absolute.stat().st_size > MAX_SOURCE_BYTES:
                    raise CodeContextError("file_too_large", f"{resolved.relative} exceeds the {MAX_SOURCE_BYTES}-byte read limit")
                raw = resolved.absolute.read_bytes()
                if b"\x00" in raw:
                    raise CodeContextError("binary_file", f"binary file cannot be returned: {resolved.relative}")
                try:
                    text = raw.decode("utf-8")
                except UnicodeDecodeError as exc:
                    raise CodeContextError("invalid_encoding", f"file is not UTF-8 text: {resolved.relative}") from exc
                lines = text.splitlines()
                requested_end = request.end_line if request.end_line is not None else request.start_line + MAX_READ_LINES - 1
                actual_end = min(requested_end, len(lines), request.start_line + MAX_READ_LINES - 1)
                candidates: list[str] = []
                candidate_bytes = 0
                for number in range(request.start_line, actual_end + 1):
                    content = lines[number - 1]
                    encoded_size = len(content.encode("utf-8")) + 1
                    if candidates and candidate_bytes + encoded_size > MAX_READ_BYTES:
                        break
                    candidates.append(content)
                    candidate_bytes += encoded_size
                prepared.append(
                    {
                        "path": resolved.relative,
                        "start_line": request.start_line,
                        "requested_end": min(requested_end, len(lines)),
                        "total_lines": len(lines),
                        "candidates": candidates,
                        "selected": [],
                        "source_hash": hashlib.sha256(raw).hexdigest(),
                    }
                )

            stale = self._stale_paths(item["path"] for item in prepared)

            def render_result() -> dict[str, Any]:
                items: list[dict[str, Any]] = []
                for item in prepared:
                    count = len(item["selected"])
                    returned_end = item["start_line"] + count - 1
                    truncated = returned_end < item["requested_end"]
                    items.append(
                        {
                            "path": item["path"],
                            "start_line": item["start_line"],
                            "end_line": returned_end,
                            "total_lines": item["total_lines"],
                            "text": "\n".join(item["selected"]),
                            "truncated": truncated,
                            "next_start_line": returned_end + 1 if truncated else None,
                            "source_hash": item["source_hash"],
                            "index_stale": item["path"] in stale,
                        }
                    )
                payload: dict[str, Any] = {
                    "ok": True,
                    "requested_budget": budget,
                    "estimated_tokens": 0,
                    "items": items,
                    "truncated": any(item["truncated"] for item in items),
                    "health": self.health(stale_paths=stale),
                }
                for _ in range(4):
                    token_estimate = estimate_tokens(
                        json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
                    )
                    if token_estimate == payload["estimated_tokens"]:
                        break
                    payload["estimated_tokens"] = token_estimate
                return payload

            empty_result = render_result()
            byte_ceiling = (budget + budget_tolerance(budget)) * 4
            metadata_bytes = len(
                json.dumps(empty_result, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
            )
            remaining_bytes = max(0, byte_ceiling - metadata_bytes)
            equal_share = remaining_bytes // len(prepared)
            used_bytes = 0
            positions = [0] * len(prepared)
            for index, item in enumerate(prepared):
                while positions[index] < len(item["candidates"]):
                    line = item["candidates"][positions[index]]
                    line_size = len(line.encode("utf-8")) + 1
                    current_size = sum(len(value.encode("utf-8")) + 1 for value in item["selected"])
                    if current_size + line_size > equal_share:
                        break
                    item["selected"].append(line)
                    positions[index] += 1
                    used_bytes += line_size
            leftover = max(0, remaining_bytes - used_bytes)
            while leftover:
                progressed = False
                for index, item in enumerate(prepared):
                    if positions[index] >= len(item["candidates"]):
                        continue
                    line = item["candidates"][positions[index]]
                    line_size = len(line.encode("utf-8")) + 1
                    if line_size > leftover:
                        continue
                    item["selected"].append(line)
                    positions[index] += 1
                    leftover -= line_size
                    progressed = True
                if not progressed:
                    break

            result = render_result()
            tolerance = budget_tolerance(budget)
            while result["estimated_tokens"] > budget + tolerance:
                trimmed = False
                for item in reversed(prepared):
                    if item["selected"]:
                        item["selected"].pop()
                        trimmed = True
                        break
                if not trimmed:
                    raise CodeContextError("budget_too_small", "bundle metadata exceeds the requested token budget")
                result = render_result()
            return result
        except (OSError, CodeContextError) as exc:
            structured = exc if isinstance(exc, CodeContextError) else CodeContextError("read_failed", str(exc))
            return {**_error(structured), "health": self.health()}


__all__ = [
    "CodeContextError",
    "CodeContextService",
    "BundleFileRequest",
    "DEFAULT_CONTEXT_BUDGET",
    "DEFAULT_INDEX_PATH",
    "REPO_ROOT",
]
