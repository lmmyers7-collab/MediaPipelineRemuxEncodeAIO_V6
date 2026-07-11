"""Repeatable, read-only performance baselines for the active workspace."""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from mediapipeline.core.observability.performance import (
    append_performance_records,
    performance_record,
    summarize_duration_samples,
)
from mediapipeline.tools.paths import find_repo_root


BENCHMARK_SCHEMA_VERSION = "mediapipeline_performance_benchmark.v1"
DEFAULT_REPEAT = 5
MAX_REPEAT = 20
MAX_TIMEOUT_SECONDS = 600


@dataclass(frozen=True)
class CommandSample:
    elapsed_ms: float
    returncode: int


def run_command_samples(
    command: Sequence[str],
    *,
    cwd: Path,
    repeat: int,
    timeout_seconds: int,
    env: dict[str, str] | None = None,
) -> list[CommandSample]:
    samples: list[CommandSample] = []
    for _ in range(repeat):
        started = time.perf_counter()
        result = subprocess.run(
            list(command),
            cwd=cwd,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=timeout_seconds,
            check=False,
        )
        samples.append(CommandSample(elapsed_ms=(time.perf_counter() - started) * 1000, returncode=result.returncode))
    return samples


def benchmark_backend_import(root: Path, *, repeat: int, timeout_seconds: int) -> dict[str, Any]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPATH"] = str(root / "src")
    samples = run_command_samples(
        [sys.executable, "-c", "import mediapipeline.desktop.local_api_main"],
        cwd=root,
        repeat=repeat,
        timeout_seconds=timeout_seconds,
        env=env,
    )
    durations = [sample.elapsed_ms for sample in samples]
    return {
        "operation": "backend_import",
        "correct": all(sample.returncode == 0 for sample in samples),
        "summary": summarize_duration_samples(durations),
        "samples_ms": [round(value, 3) for value in durations],
        "returncodes": [sample.returncode for sample in samples],
    }


def benchmark_static_shell(root: Path) -> dict[str, Any]:
    static_root = root / "apps" / "desktop" / "webview" / "static"
    index_path = static_root / "index.html"
    started = time.perf_counter()
    index_text = index_path.read_text(encoding="utf-8")
    sources = re.findall(r"<script\b[^>]*\bsrc=[\"']([^\"']+)[\"']", index_text, flags=re.IGNORECASE)
    deferred_sources = re.findall(
        r"<script\b[^>]*\bdefer\b[^>]*\bsrc=[\"']([^\"']+)[\"']",
        index_text,
        flags=re.IGNORECASE,
    )
    asset_paths = [static_root / source.split("?", 1)[0].lstrip("/") for source in sources]
    missing = [str(path.relative_to(root)) for path in asset_paths if not path.is_file()]
    asset_bytes = sum(path.stat().st_size for path in asset_paths if path.is_file())
    elapsed_ms = (time.perf_counter() - started) * 1000
    return {
        "operation": "static_shell_inventory",
        "correct": not missing,
        "summary": summarize_duration_samples([elapsed_ms]),
        "external_script_count": len(sources),
        "deferred_external_script_count": len(deferred_sources),
        "external_script_bytes": asset_bytes,
        "missing_assets": missing,
    }


def benchmark_pipeline_module_graph(root: Path) -> dict[str, Any]:
    loader_path = root / "ops" / "pipeline" / "entrypoints" / "MediaPipeline" / "module_loader.ps1"
    started = time.perf_counter()
    loader_text = loader_path.read_text(encoding="utf-8")
    relative_paths = re.findall(r"Join-Path \$repoRootForModules '([^']+\.ps1)'", loader_text)
    module_paths = [root / relative.replace("\\", "/") for relative in relative_paths]
    missing = [str(path.relative_to(root)) for path in module_paths if not path.is_file()]
    module_bytes = sum(path.stat().st_size for path in module_paths if path.is_file())
    elapsed_ms = (time.perf_counter() - started) * 1000
    return {
        "operation": "pipeline_module_graph_inventory",
        "correct": not missing and bool(module_paths),
        "summary": summarize_duration_samples([elapsed_ms]),
        "module_count": len(module_paths),
        "module_bytes": module_bytes,
        "missing_modules": missing,
    }


def benchmark_audit_suite(root: Path, suite: str, *, timeout_seconds: int) -> dict[str, Any]:
    samples = run_command_samples(
        [sys.executable, "-m", "mediapipeline.tools.dev.audit_checks", "run", suite],
        cwd=root,
        repeat=1,
        timeout_seconds=timeout_seconds,
        env={**os.environ, "PYTHONPATH": str(root / "src"), "PYTHONDONTWRITEBYTECODE": "1"},
    )
    return {
        "operation": f"audit_suite:{suite}",
        "correct": samples[0].returncode == 0,
        "summary": summarize_duration_samples([samples[0].elapsed_ms]),
        "returncodes": [samples[0].returncode],
    }


def records_for_payload(payload: dict[str, Any], *, variant: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for result in payload.get("results", []):
        operation = str(result.get("operation") or "unknown")
        correct = bool(result.get("correct"))
        summary = dict(result.get("summary") or {})
        for metric in ("min_ms", "median_ms", "p95_ms", "max_ms"):
            if metric in summary:
                records.append(
                    performance_record(
                        operation=operation,
                        metric=metric,
                        value=float(summary[metric]),
                        unit="ms",
                        correct=correct,
                        variant=variant,
                        tags={"sample_count": int(summary.get("count") or 0)},
                        measured_at=str(payload["measured_at"]),
                    )
                )
        for metric in (
            "external_script_count",
            "deferred_external_script_count",
            "external_script_bytes",
            "module_count",
            "module_bytes",
        ):
            if metric in result:
                records.append(
                    performance_record(
                        operation=operation,
                        metric=metric,
                        value=int(result[metric]),
                        unit="count" if metric.endswith("count") else "bytes",
                        correct=correct,
                        variant=variant,
                        measured_at=str(payload["measured_at"]),
                    )
                )
    return records


def build_payload(root: Path, *, repeat: int, timeout_seconds: int, audit_suite: str = "") -> dict[str, Any]:
    measured_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    results = [
        benchmark_backend_import(root, repeat=repeat, timeout_seconds=timeout_seconds),
        benchmark_static_shell(root),
        benchmark_pipeline_module_graph(root),
    ]
    if audit_suite:
        results.append(benchmark_audit_suite(root, audit_suite, timeout_seconds=timeout_seconds))
    return {
        "schema_version": BENCHMARK_SCHEMA_VERSION,
        "measured_at": measured_at,
        "workspace": str(root),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "repeat": repeat,
        "timeout_seconds": timeout_seconds,
        "correct": all(bool(result.get("correct")) for result in results),
        "results": results,
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeat", type=int, default=DEFAULT_REPEAT, help=f"Backend import samples (1-{MAX_REPEAT}).")
    parser.add_argument("--timeout-seconds", type=int, default=120, help=f"Per-command timeout (1-{MAX_TIMEOUT_SECONDS}).")
    parser.add_argument("--audit-suite", default="", help="Optional audit_checks suite to time once.")
    parser.add_argument("--variant", default="baseline", help="Variant label stored in JSONL records.")
    parser.add_argument("--ledger", default="", help="Optional JSONL ledger path. No ledger is written by default.")
    parser.add_argument("--output", default="", help="Optional full JSON result path.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    repeat = int(args.repeat)
    timeout_seconds = int(args.timeout_seconds)
    if repeat < 1 or repeat > MAX_REPEAT:
        raise SystemExit(f"--repeat must be between 1 and {MAX_REPEAT}")
    if timeout_seconds < 1 or timeout_seconds > MAX_TIMEOUT_SECONDS:
        raise SystemExit(f"--timeout-seconds must be between 1 and {MAX_TIMEOUT_SECONDS}")
    root = find_repo_root(Path(__file__))
    payload = build_payload(root, repeat=repeat, timeout_seconds=timeout_seconds, audit_suite=str(args.audit_suite or ""))
    if args.output:
        output_path = Path(args.output).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.ledger:
        append_performance_records(
            Path(args.ledger).expanduser().resolve(),
            records_for_payload(payload, variant=str(args.variant or "baseline")),
        )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["correct"] else 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "BENCHMARK_SCHEMA_VERSION",
    "CommandSample",
    "benchmark_audit_suite",
    "benchmark_backend_import",
    "benchmark_pipeline_module_graph",
    "benchmark_static_shell",
    "build_payload",
    "main",
    "records_for_payload",
    "run_command_samples",
]
