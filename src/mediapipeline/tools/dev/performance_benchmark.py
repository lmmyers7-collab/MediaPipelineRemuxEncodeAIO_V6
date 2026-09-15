"""Repeatable, read-only performance baselines for the active workspace."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from mediapipeline.core.observability.performance import (
    append_performance_records,
    performance_record,
    summarize_duration_samples,
)
from mediapipeline.core.paths.contracts import ResolvedPaths
from mediapipeline.core.queue.source_inventory import build_queue_source_inventory
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


def _queue_benchmark_resolved(workspace: Path, source_root: Path, state_root: Path) -> ResolvedPaths:
    return ResolvedPaths(
        app_root=workspace / "apps" / "desktop",
        workspace_root=workspace,
        pipeline_path=workspace / "ops" / "pipeline" / "entrypoints" / "MediaPipeline.ps1",
        config_path=workspace / "config" / "MediaPipeline.psd1",
        audit_script_path=workspace / "ops" / "scripts" / "audit.ps1",
        rerun_script_path=workspace / "ops" / "scripts" / "rerun.ps1",
        powershell_host=None,
        local_base=state_root.parent,
        state_root=state_root,
        source_movies=source_root,
        source_tv=None,
        queue_snapshot_path=state_root / "Progress" / "queue_snapshot.json",
        config_data={"SourceMovies": str(source_root), "SourceTV": "", "LibraryProfiles": []},
    )


def _create_generated_queue_library(root: Path, *, file_count: int) -> None:
    for index in range(file_count):
        season = index % 12 + 1
        directory = root / f"Library-{index % 8:02d}" / f"Season {season:02d}"
        directory.mkdir(parents=True, exist_ok=True)
        (directory / f"Generated - S{season:02d}E{index + 1:04d}.mkv").write_bytes(b"queue-benchmark")
        if index % 5 == 0:
            (directory / f"Generated - S{season:02d}E{index + 1:04d}.srt").write_text(
                "1\n00:00:00,000 --> 00:00:01,000\nbenchmark\n",
                encoding="utf-8",
            )


def _queue_inventory_sample(resolved: ResolvedPaths, *, scan_id: str, row_limit: int) -> tuple[float, str, int, int]:
    started = time.perf_counter()
    inventory = build_queue_source_inventory(resolved, scan_id=scan_id, row_limit=row_limit)
    elapsed_ms = (time.perf_counter() - started) * 1000
    fingerprint_source = "\n".join(
        sorted(str(row.get("source_path") or "").replace("\\", "/").casefold() for row in inventory.get("rows") or [])
    )
    fingerprint = hashlib.sha256(fingerprint_source.encode("utf-8")).hexdigest()
    return (
        elapsed_ms,
        fingerprint,
        int(inventory.get("candidate_count") or 0),
        int(inventory.get("directory_count") or 0),
    )


def benchmark_queue_source_inventory(
    workspace: Path,
    *,
    repeat: int,
    benchmark_root: Path | None = None,
    generated_file_count: int = 400,
) -> list[dict[str, Any]]:
    """Measure five comparable read-only full scans and warm normal scans."""

    temporary: tempfile.TemporaryDirectory[str] | None = None
    if benchmark_root is None:
        temporary = tempfile.TemporaryDirectory(prefix="mediapipeline-queue-benchmark-")
        scenario_root = Path(temporary.name)
        source_root = scenario_root / "Source"
        _create_generated_queue_library(source_root, file_count=generated_file_count)
        storage_kind = "generated_disposable"
    else:
        source_root = benchmark_root.expanduser().resolve()
        if not source_root.is_dir():
            raise ValueError(f"Queue benchmark root is not an accessible directory: {source_root}")
        temporary = tempfile.TemporaryDirectory(prefix="mediapipeline-queue-benchmark-state-")
        scenario_root = Path(temporary.name)
        storage_kind = "operator_supplied_read_only"

    try:
        resolved = _queue_benchmark_resolved(workspace, source_root, scenario_root / "State")
        row_limit = max(generated_file_count + 1, 100_000)
        groups: list[dict[str, Any]] = []
        expected_fingerprint = ""
        for run_kind in ("cold_full_scan", "warm_normal_scan"):
            durations: list[float] = []
            fingerprints: list[str] = []
            candidate_counts: list[int] = []
            directory_counts: list[int] = []
            for index in range(repeat):
                elapsed_ms, fingerprint, candidates, directories = _queue_inventory_sample(
                    resolved,
                    scan_id=f"benchmark-{run_kind}-{index + 1}",
                    row_limit=row_limit,
                )
                durations.append(elapsed_ms)
                fingerprints.append(fingerprint)
                candidate_counts.append(candidates)
                directory_counts.append(directories)
                expected_fingerprint = expected_fingerprint or fingerprint
            groups.append(
                {
                    "operation": f"queue_source_inventory:{run_kind}",
                    "correct": bool(fingerprints) and all(value == expected_fingerprint for value in fingerprints),
                    "summary": summarize_duration_samples(durations),
                    "samples_ms": [round(value, 3) for value in durations],
                    "queue_fingerprint": expected_fingerprint,
                    "candidate_count": candidate_counts[0] if candidate_counts else 0,
                    "directory_count": directory_counts[0] if directory_counts else 0,
                    "storage_kind": storage_kind,
                    "source_mutation": False,
                }
            )
        return groups
    finally:
        if temporary is not None:
            temporary.cleanup()


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
            "candidate_count",
            "directory_count",
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


def build_payload(
    root: Path,
    *,
    repeat: int,
    timeout_seconds: int,
    audit_suite: str = "",
    queue_scenario: bool = False,
    benchmark_root: Path | None = None,
    generated_file_count: int = 400,
) -> dict[str, Any]:
    measured_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    results = [
        benchmark_backend_import(root, repeat=repeat, timeout_seconds=timeout_seconds),
        benchmark_static_shell(root),
        benchmark_pipeline_module_graph(root),
    ]
    if audit_suite:
        results.append(benchmark_audit_suite(root, audit_suite, timeout_seconds=timeout_seconds))
    if queue_scenario:
        results.extend(
            benchmark_queue_source_inventory(
                root,
                repeat=repeat,
                benchmark_root=benchmark_root,
                generated_file_count=generated_file_count,
            )
        )
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
    parser.add_argument(
        "--queue-scenario",
        action="store_true",
        help="Run cold/full and warm/normal queue source-inventory baselines.",
    )
    parser.add_argument(
        "--benchmark-root",
        default="",
        help="Optional representative source root. It is read only; generated disposable media is used by default.",
    )
    parser.add_argument(
        "--generated-file-count",
        type=int,
        default=400,
        help="Generated queue candidate count when --benchmark-root is omitted (1-100000).",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    repeat = int(args.repeat)
    timeout_seconds = int(args.timeout_seconds)
    if repeat < 1 or repeat > MAX_REPEAT:
        raise SystemExit(f"--repeat must be between 1 and {MAX_REPEAT}")
    if timeout_seconds < 1 or timeout_seconds > MAX_TIMEOUT_SECONDS:
        raise SystemExit(f"--timeout-seconds must be between 1 and {MAX_TIMEOUT_SECONDS}")
    if int(args.generated_file_count) < 1 or int(args.generated_file_count) > 100_000:
        raise SystemExit("--generated-file-count must be between 1 and 100000")
    root = find_repo_root(Path(__file__))
    benchmark_root = Path(args.benchmark_root) if str(args.benchmark_root or "").strip() else None
    payload = build_payload(
        root,
        repeat=repeat,
        timeout_seconds=timeout_seconds,
        audit_suite=str(args.audit_suite or ""),
        queue_scenario=bool(args.queue_scenario),
        benchmark_root=benchmark_root,
        generated_file_count=int(args.generated_file_count),
    )
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
    "benchmark_queue_source_inventory",
    "benchmark_static_shell",
    "build_payload",
    "main",
    "records_for_payload",
    "run_command_samples",
]
