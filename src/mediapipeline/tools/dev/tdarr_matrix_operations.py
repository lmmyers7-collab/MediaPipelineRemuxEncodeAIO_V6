"""Audit and sample-run harness for the generated Tdarr Matrix test library."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import subprocess
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, UTC
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any
from collections.abc import Iterable, Mapping, Sequence

from mediapipeline.tools.dev import materialize_tdarr_test_library as tdarr_matrix
from mediapipeline.tools.paths import find_repo_root
from mediapipeline.core.diagnostics.tdarr_matrix_proof import (
    tdarr_policy_proof_runs_root,
    tdarr_proof_pack_root,
    tdarr_proof_runs_root,
)
from mediapipeline.tools.dev.tdarr_matrix_models import *  # noqa: F403

def assert_allowed_run_root(run_root: Path, *, repo_root: Path) -> None:
    allowed_roots = (
        (repo_root / "LocalBase" / "Scratch" / "TestLibraries" / "TdarrMatrixRuns").resolve(),
        tdarr_proof_runs_root(repo_root).resolve(),
        tdarr_policy_proof_runs_root(repo_root).resolve(),
    )
    if any(is_under(run_root, allowed_root) for allowed_root in allowed_roots):
        return
    rendered = ", ".join(str(root) for root in allowed_roots)
    raise ValueError(f"Audit run root must be under one of: {rendered}")


def prepare_run_root(run_root: Path, *, repo_root: Path = REPO_ROOT, rebuild: bool = False) -> None:
    assert_allowed_run_root(run_root, repo_root=repo_root)
    sentinel = run_root / AUDIT_RUN_SENTINEL
    existing_children = list(run_root.iterdir()) if run_root.exists() else []
    if existing_children and not rebuild:
        raise FileExistsError(f"{run_root} already has content; pass --rebuild-run to regenerate it.")
    if existing_children and rebuild and not sentinel.exists():
        raise FileExistsError(f"{run_root} has no {AUDIT_RUN_SENTINEL}; refusing destructive rebuild.")
    if existing_children and rebuild:
        shutil.rmtree(run_root)
    run_root.mkdir(parents=True, exist_ok=True)


def allowed_materialize_source_roots(row: ManifestRow, *, repo_root: Path) -> tuple[Path, ...]:
    return (
        row.library_root,
        repo_root / "LocalBase" / "TestFixtures" / "TdarrSamples",
    )


def resolve_materialize_source(row: ManifestRow, *, repo_root: Path) -> Path:
    source_path = row.source_path
    if not source_path.is_absolute():
        source_path = repo_root / source_path
    source_path = source_path.resolve(strict=False)
    allowed_roots = allowed_materialize_source_roots(row, repo_root=repo_root)
    if not any(is_under(source_path, allowed_root) for allowed_root in allowed_roots):
        rendered_roots = ", ".join(str(root.resolve(strict=False)) for root in allowed_roots)
        raise ValueError(f"source_path must resolve under an approved fixture/materialized-library root ({rendered_roots}): {source_path}")
    if not source_path.exists():
        raise FileNotFoundError(f"Source sample is missing: {source_path}")
    return source_path


def plan_run_materialization(
    rows: Sequence[ManifestRow],
    *,
    run_root: Path,
    repo_root: Path,
) -> list[tuple[ManifestRow, Path, Path]]:
    planned: list[tuple[ManifestRow, Path, Path]] = []
    for row in rows:
        _generated_path, destination = contained_manifest_child(
            run_root,
            row.generated_path,
            field_name="generated_path",
        )
        source_path = resolve_materialize_source(row, repo_root=repo_root)
        planned.append((row, destination, source_path))
    return planned


def materialize_run_subset(
    *,
    rows: Sequence[ManifestRow],
    run_root: Path,
    repo_root: Path = REPO_ROOT,
    template_path: Path = DEFAULT_TEMPLATE,
    rebuild: bool = False,
) -> dict[str, Any]:
    run_root = resolve_path(run_root, repo_root=repo_root)
    template_path = resolve_path(template_path, repo_root=repo_root)
    planned_links = plan_run_materialization(rows, run_root=run_root, repo_root=repo_root)
    prepare_run_root(run_root, repo_root=repo_root, rebuild=rebuild)
    for path in (
        run_root / "source" / "Movies",
        run_root / "source" / "TV",
        run_root / "output" / "Movies",
        run_root / "output" / "TV",
        run_root / "scratch",
        run_root / "config",
        run_root / "manifests",
    ):
        path.mkdir(parents=True, exist_ok=True)
    for _row, destination, source_path in planned_links:
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            raise FileExistsError(f"Generated target already exists: {destination}")
        os.link(source_path, destination)
    write_materialized_manifest(run_root, rows, link_mode="hardlink")
    config_path = run_root / "config" / CONFIG_NAME
    config_path.write_text(tdarr_matrix.render_config(template_path, run_root), encoding="utf-8", newline="\n")
    sentinel = {
        "schema_version": AUDIT_SCHEMA,
        "generated_at_utc": utc_now(),
        "source_library_root": "",
        "run_root": str(run_root),
        "selected_count": len(rows),
        "link_mode": "hardlink",
    }
    (run_root / AUDIT_RUN_SENTINEL).write_text(json.dumps(sentinel, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "run_root": str(run_root),
        "config_path": str(config_path),
        "manifest_csv": str(run_root / "manifests" / "materialized_library.csv"),
        "selected_count": len(rows),
    }


def discover_run_roots(runs_root: Path) -> list[Path]:
    """Sentinel-marked run directories directly under ``runs_root``, oldest first."""
    if not runs_root.exists():
        return []
    marked = [
        child
        for child in runs_root.iterdir()
        if child.is_dir() and (child / AUDIT_RUN_SENTINEL).exists()
    ]
    return sorted(marked, key=lambda path: path.stat().st_mtime)


def prune_run_roots(runs_root: Path, *, keep_last: int, repo_root: Path = REPO_ROOT, dry_run: bool = False) -> dict[str, Any]:
    """Retain the newest ``keep_last`` sentinel-marked run roots and remove older ones (G4).

    Safety rails: ``keep_last`` must be >= 1 (so the just-created run, always the newest, is
    never deleted); only directories that sit directly under the canonical TdarrMatrixRuns root
    and carry ``AUDIT_RUN_SENTINEL`` are eligible; non-sentinel directories are never touched.
    Pass ``dry_run=True`` to preview removals without deleting.
    """
    runs_root = resolve_path(runs_root, repo_root=repo_root)
    allowed_root = (repo_root / "LocalBase" / "Scratch" / "TestLibraries" / "TdarrMatrixRuns").resolve()
    if runs_root != allowed_root:
        raise ValueError(f"Run prune root must be {allowed_root}")
    if keep_last < 1:
        raise ValueError("keep_last must be >= 1 so the newest run is always retained")
    candidates = discover_run_roots(runs_root)
    to_remove = candidates[:-keep_last]
    removed: list[str] = []
    for run_dir in to_remove:
        if not (run_dir / AUDIT_RUN_SENTINEL).exists():
            continue
        if run_dir.resolve().parent != runs_root:
            continue
        if not dry_run:
            shutil.rmtree(run_dir)
        removed.append(str(run_dir))
    return {
        "runs_root": str(runs_root),
        "kept": [str(path) for path in candidates[len(candidates) - keep_last :]],
        "removed": removed,
        "dry_run": dry_run,
    }


def build_powershell_file_command(powershell: str, entrypoint: Path) -> list[str]:
    return [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(entrypoint)]


def build_validate_command(powershell: str, entrypoint: Path, config_path: Path) -> list[str]:
    return [*build_powershell_file_command(powershell, entrypoint), "-ConfigPath", str(config_path), "-ValidateOnly"]


def build_effective_config_command(powershell: str, entrypoint: Path, config_path: Path, output_path: Path) -> list[str]:
    return [
        *build_powershell_file_command(powershell, entrypoint),
        "-ConfigPath",
        str(config_path),
        "-DumpEffectiveConfigPath",
        str(output_path),
    ]


def build_queue_snapshot_command(powershell: str, entrypoint: Path, config_path: Path, output_path: Path) -> list[str]:
    return [
        *build_powershell_file_command(powershell, entrypoint),
        "-ConfigPath",
        str(config_path),
        "-EmitQueuePlan",
        "-QueuePlanOutPath",
        str(output_path),
    ]


def build_single_file_command(
    powershell: str,
    entrypoint: Path,
    config_path: Path,
    source_path: Path,
    worker_result_path: Path,
    *,
    run_id: str,
    claim_id: str,
) -> list[str]:
    return [
        *build_powershell_file_command(powershell, entrypoint),
        "-ConfigPath",
        str(config_path),
        "-SingleFile",
        str(source_path),
        "-WorkerChild",
        "-WorkerSlotId",
        "1",
        "-WorkerRunId",
        run_id,
        "-WorkerClaimId",
        claim_id,
        "-WorkerResultPath",
        str(worker_result_path),
    ]


def text_from_timeout(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def terminate_process_tree(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            capture_output=True,
            text=True,
            check=False,
        )
        return
    process.kill()


def run_subprocess_capture(command: list[str], *, cwd: Path, timeout_seconds: int, stdout_path: Path, stderr_path: Path) -> ProcessOutcome:
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    stderr_path.parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    process = subprocess.Popen(
        command,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        creationflags=creationflags,
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout_seconds)
    except subprocess.TimeoutExpired as exc:
        terminate_process_tree(process)
        try:
            stdout, stderr = process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            stdout = text_from_timeout(exc.stdout)
            stderr = text_from_timeout(exc.stderr)
        duration = time.monotonic() - started
        stdout_path.write_text(stdout or "", encoding="utf-8")
        stderr_path.write_text(stderr or "", encoding="utf-8")
        return ProcessOutcome(command=command, returncode=None, timed_out=True, duration_seconds=duration, stdout_path=stdout_path, stderr_path=stderr_path)
    duration = time.monotonic() - started
    stdout_path.write_text(stdout or "", encoding="utf-8")
    stderr_path.write_text(stderr or "", encoding="utf-8")
    return ProcessOutcome(
        command=command,
        returncode=process.returncode,
        timed_out=False,
        duration_seconds=duration,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
    )


def default_audit_dir(library_root: Path) -> Path:
    return library_root / "manifests" / AUDIT_DIR_NAME


def default_config_path(library_root: Path) -> Path:
    return library_root / "config" / CONFIG_NAME


def default_queue_snapshot_path(library_root: Path) -> Path:
    return default_audit_dir(library_root) / "queue_snapshot.json"


def default_effective_config_path(library_root: Path) -> Path:
    return default_audit_dir(library_root) / "effective_config.json"


def load_json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON payload is not an object: {path}")
    return payload


def command_failure_finding(label: str, outcome: ProcessOutcome) -> Finding | None:
    if outcome.timed_out:
        return Finding(
            severity="critical",
            code="subprocess_timeout",
            message=f"{label} timed out.",
            evidence=outcome.to_dict(),
        )
    if outcome.returncode not in (0, None):
        return Finding(
            severity="critical",
            code="subprocess_failed",
            message=f"{label} exited with code {outcome.returncode}.",
            evidence=outcome.to_dict(),
        )
    return None


def prepare_pipeline_evidence(
    *,
    library_root: Path,
    config_path: Path,
    powershell: str,
    entrypoint: Path,
    cwd: Path = REPO_ROOT,
    timeout_seconds: int = DEFAULT_PREPARE_TIMEOUT_SECONDS,
) -> tuple[Path, Path, list[Finding]]:
    audit_dir = default_audit_dir(library_root)
    command_dir = audit_dir / "commands"
    audit_dir.mkdir(parents=True, exist_ok=True)
    effective_config_path = default_effective_config_path(library_root)
    queue_snapshot_path = default_queue_snapshot_path(library_root)
    steps = [
        ("validate", build_validate_command(powershell, entrypoint, config_path)),
        ("effective-config", build_effective_config_command(powershell, entrypoint, config_path, effective_config_path)),
        ("queue-snapshot", build_queue_snapshot_command(powershell, entrypoint, config_path, queue_snapshot_path)),
    ]
    findings: list[Finding] = []
    outcomes: list[dict[str, Any]] = []
    for label, command in steps:
        outcome = run_subprocess_capture(
            command,
            cwd=cwd,
            timeout_seconds=timeout_seconds,
            stdout_path=command_dir / f"{label}.stdout.log",
            stderr_path=command_dir / f"{label}.stderr.log",
        )
        outcomes.append({"label": label, **outcome.to_dict()})
        finding = command_failure_finding(label, outcome)
        if finding:
            findings.append(finding)
    (audit_dir / "prepare_evidence_results.json").write_text(json.dumps(outcomes, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return effective_config_path, queue_snapshot_path, findings



__all__ = [
    "assert_allowed_run_root",
    "prepare_run_root",
    "allowed_materialize_source_roots",
    "resolve_materialize_source",
    "plan_run_materialization",
    "materialize_run_subset",
    "discover_run_roots",
    "prune_run_roots",
    "build_powershell_file_command",
    "build_validate_command",
    "build_effective_config_command",
    "build_queue_snapshot_command",
    "build_single_file_command",
    "text_from_timeout",
    "terminate_process_tree",
    "run_subprocess_capture",
    "default_audit_dir",
    "default_config_path",
    "default_queue_snapshot_path",
    "default_effective_config_path",
    "load_json_object",
    "command_failure_finding",
    "prepare_pipeline_evidence",
]
