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
from mediapipeline.tools.dev.tdarr_matrix_operations import *  # noqa: F403
from mediapipeline.tools.dev.tdarr_matrix_audits import *  # noqa: F403

def required_input_findings(*, manifest_path: Path, config_path: Path, queue_snapshot_path: Path) -> list[Finding]:
    findings: list[Finding] = []
    for label, path in (("manifest", manifest_path), ("config", config_path), ("queue snapshot", queue_snapshot_path)):
        if not path.exists():
            findings.append(
                Finding(
                    severity="critical",
                    code="required_input_unreadable",
                    message=f"Required {label} input is missing or unreadable.",
                    evidence={"path": str(path), "label": label},
                )
            )
    return findings


def report_paths(audit_dir: Path) -> tuple[Path, Path, Path]:
    return (
        audit_dir / "tdarr_matrix_audit_report.json",
        audit_dir / "tdarr_matrix_audit_summary.md",
        audit_dir / "tdarr_matrix_findings.csv",
    )


def write_reports(
    *,
    library_root: Path,
    audit_dir: Path,
    rows: Sequence[ManifestRow],
    findings: Sequence[Finding],
    queue_snapshot_path: Path | None = None,
    effective_config_path: Path | None = None,
    mode: str = "report",
) -> dict[str, Any]:
    audit_dir.mkdir(parents=True, exist_ok=True)
    severity_counts = Counter(finding.severity for finding in findings)
    code_counts = Counter(finding.code for finding in findings)
    report = {
        "schema_version": AUDIT_SCHEMA,
        "generated_at_utc": utc_now(),
        "mode": mode,
        "library_root": str(library_root),
        "manifest_count": len(rows),
        "queue_snapshot_path": str(queue_snapshot_path or ""),
        "effective_config_path": str(effective_config_path or ""),
        "severity_counts": dict(sorted(severity_counts.items())),
        "code_counts": dict(sorted(code_counts.items())),
        "findings": [finding.to_dict() for finding in findings],
    }
    json_path, markdown_path, csv_path = report_paths(audit_dir)
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_lines = [
        "# Tdarr Matrix Audit Summary",
        "",
        f"- Schema: `{AUDIT_SCHEMA}`",
        f"- Mode: `{mode}`",
        f"- Library root: `{library_root}`",
        f"- Manifest rows: `{len(rows)}`",
        f"- Findings: `{len(findings)}`",
        "",
        "## Severity Counts",
        "",
    ]
    for severity in ("critical", "error", "warning", "info"):
        markdown_lines.append(f"- {severity}: `{severity_counts.get(severity, 0)}`")
    markdown_lines.extend(["", "## Top Finding Codes", ""])
    if code_counts:
        for code, count in code_counts.most_common(20):
            markdown_lines.append(f"- `{code}`: `{count}`")
    else:
        markdown_lines.append("- none")
    markdown_path.write_text("\n".join(markdown_lines) + "\n", encoding="utf-8")
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        fieldnames = [
            "severity",
            "code",
            "message",
            "case_id",
            "view",
            "diagnostic_bucket",
            "generated_path",
            "source_path",
            "evidence",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for finding in findings:
            row = finding.to_dict()
            row["evidence"] = json.dumps(row["evidence"], sort_keys=True)
            writer.writerow(row)
    return report


def exit_code_for_findings(findings: Sequence[Finding], *, strict: bool) -> int:
    if not strict:
        return 0
    return 1 if any(finding.severity in FAIL_SEVERITIES for finding in findings) else 0


def audit_existing_library(
    *,
    library_root: Path,
    manifest_path: Path,
    config_path: Path,
    queue_snapshot_path: Path,
    effective_config_path: Path | None = None,
    audit_dir: Path | None = None,
    hash_sources: bool = False,
    mode: str = "report",
    ffprobe: str = "ffprobe",
    fixture_probe_timeout_seconds: int = DEFAULT_FIXTURE_PROBE_TIMEOUT_SECONDS,
) -> tuple[list[ManifestRow], list[Finding], dict[str, Any]]:
    audit_dir = audit_dir or default_audit_dir(library_root)
    findings = required_input_findings(manifest_path=manifest_path, config_path=config_path, queue_snapshot_path=queue_snapshot_path)
    rows: list[ManifestRow] = []
    if manifest_path.exists():
        try:
            rows = load_manifest_rows(manifest_path, library_root=library_root)
        except Exception as exc:
            findings.append(Finding(severity="critical", code="required_input_unreadable", message=f"Could not read materialized manifest: {exc}", evidence={"path": str(manifest_path)}))
    snapshot: dict[str, Any] = {}
    if queue_snapshot_path.exists():
        try:
            snapshot = load_json_object(queue_snapshot_path)
        except Exception as exc:
            findings.append(Finding(severity="critical", code="required_input_unreadable", message=f"Could not read queue snapshot: {exc}", evidence={"path": str(queue_snapshot_path)}))
    if rows and snapshot:
        findings.extend(audit_queue_snapshot(rows, snapshot))
    if rows and hash_sources:
        findings.extend(audit_source_hashes(rows))
    if rows:
        findings.extend(audit_existing_worker_evidence(rows, library_root=library_root, audit_dir=audit_dir))
        _, fixture_probe_findings = audit_fixture_video_probes(rows, ffprobe=ffprobe, timeout_seconds=fixture_probe_timeout_seconds)
        findings.extend(fixture_probe_findings)
        findings.extend(audit_bucket_classification(rows))
    findings.extend(audit_path_containment(library_root))
    report = write_reports(
        library_root=library_root,
        audit_dir=audit_dir,
        rows=rows,
        findings=findings,
        queue_snapshot_path=queue_snapshot_path,
        effective_config_path=effective_config_path,
        mode=mode,
    )
    return rows, findings, report


def run_id_default() -> str:
    return datetime.now(UTC).strftime("run-%Y%m%d-%H%M%S")


def command_report(args: argparse.Namespace) -> int:
    library_root = resolve_path(args.library_root)
    manifest_path = resolve_path(args.manifest_csv or library_root / "manifests" / "materialized_library.csv")
    config_path = resolve_path(args.config_path or default_config_path(library_root))
    queue_snapshot_path = resolve_path(args.queue_snapshot or default_queue_snapshot_path(library_root))
    effective_config_path = resolve_path(args.effective_config or default_effective_config_path(library_root))
    audit_dir = resolve_path(args.audit_dir or default_audit_dir(library_root))
    prepare_findings: list[Finding] = []
    if args.prepare_evidence:
        effective_config_path, queue_snapshot_path, prepare_findings = prepare_pipeline_evidence(
            library_root=library_root,
            config_path=config_path,
            powershell=args.powershell,
            entrypoint=resolve_path(args.entrypoint),
            timeout_seconds=args.prepare_timeout_seconds,
        )
    rows, findings, report = audit_existing_library(
        library_root=library_root,
        manifest_path=manifest_path,
        config_path=config_path,
        queue_snapshot_path=queue_snapshot_path,
        effective_config_path=effective_config_path,
        audit_dir=audit_dir,
        hash_sources=args.hash_sources,
        mode="report",
        ffprobe=args.ffprobe,
        fixture_probe_timeout_seconds=args.fixture_probe_timeout_seconds,
    )
    findings = [*prepare_findings, *findings]
    if prepare_findings:
        write_reports(
            library_root=library_root,
            audit_dir=audit_dir,
            rows=rows,
            findings=findings,
            queue_snapshot_path=queue_snapshot_path,
            effective_config_path=effective_config_path,
            mode="report",
        )
    print(json.dumps({"manifest_count": len(rows), "finding_count": len(findings), "report_path": str(report_paths(audit_dir)[0])}, indent=2, sort_keys=True))
    return exit_code_for_findings(findings, strict=not args.report_only)


def command_run_samples(args: argparse.Namespace) -> int:
    source_library_root = resolve_path(args.library_root)
    source_manifest_path = source_library_root / "manifests" / "materialized_library.csv"
    source_rows = load_manifest_rows(source_manifest_path, library_root=source_library_root)
    fixture_probe_findings: list[Finding] = []
    if getattr(args, "case_key", None):
        selected_rows = select_case_key_rows(source_rows, args.case_key)
        _, fixture_probe_findings = audit_fixture_video_probes(
            selected_rows,
            ffprobe=args.ffprobe,
            timeout_seconds=args.fixture_probe_timeout_seconds,
        )
    elif bool(getattr(args, "all_samples", False)):
        selected_rows = select_all_sample_rows(source_rows)
        _, fixture_probe_findings = audit_fixture_video_probes(
            selected_rows,
            ffprobe=args.ffprobe,
            timeout_seconds=args.fixture_probe_timeout_seconds,
        )
    else:
        if bool(getattr(args, "balanced_selection", False)):
            selected_rows = select_balanced_sample_rows(source_rows, samples_per_bucket=args.samples_per_bucket)
            fixture_probe_results, fixture_probe_findings = audit_fixture_video_probes(
                selected_rows,
                ffprobe=args.ffprobe,
                timeout_seconds=args.fixture_probe_timeout_seconds,
            )
            selected_rows = filter_auto_sample_probe_mismatches(selected_rows, fixture_probe_results)
        else:
            selected_rows, fixture_probe_findings, _fixture_probe_results = select_sample_rows_with_fixture_probe_filter(
                source_rows,
                samples_per_bucket=args.samples_per_bucket,
                ffprobe=args.ffprobe,
                timeout_seconds=args.fixture_probe_timeout_seconds,
            )
    run_id = args.run_id or run_id_default()
    runs_root = resolve_path(args.runs_root)
    run_root = resolve_path(args.run_root or runs_root / run_id)
    materialize_run_subset(
        rows=selected_rows,
        run_root=run_root,
        repo_root=REPO_ROOT,
        template_path=resolve_path(args.template),
        rebuild=args.rebuild_run,
    )
    run_rows = load_manifest_rows(run_root / "manifests" / "materialized_library.csv", library_root=run_root)
    config_path = run_root / "config" / CONFIG_NAME
    effective_config_path, queue_snapshot_path, findings = prepare_pipeline_evidence(
        library_root=run_root,
        config_path=config_path,
        powershell=args.powershell,
        entrypoint=resolve_path(args.entrypoint),
        timeout_seconds=args.prepare_timeout_seconds,
    )
    findings = [*fixture_probe_findings, *findings]
    if queue_snapshot_path.exists():
        try:
            findings.extend(audit_queue_snapshot(run_rows, load_json_object(queue_snapshot_path)))
        except Exception as exc:
            findings.append(Finding(severity="critical", code="required_input_unreadable", message=f"Could not read queue snapshot: {exc}", evidence={"path": str(queue_snapshot_path)}))
    findings.extend(audit_source_hashes(run_rows))
    findings.extend(
        run_sample_processing(
            rows=run_rows,
            library_root=run_root,
            config_path=config_path,
            powershell=args.powershell,
            entrypoint=resolve_path(args.entrypoint),
            run_id=run_id,
            timeout_seconds=args.sample_timeout_seconds,
        )
    )
    findings.extend(audit_source_hashes(run_rows))
    findings.extend(audit_bucket_classification(run_rows))
    findings.extend(audit_path_containment(run_root))
    write_reports(
        library_root=run_root,
        audit_dir=default_audit_dir(run_root),
        rows=run_rows,
        findings=findings,
        queue_snapshot_path=queue_snapshot_path,
        effective_config_path=effective_config_path,
        mode="run-samples",
    )
    summary: dict[str, Any] = {
        "run_root": str(run_root),
        "selected_count": len(run_rows),
        "finding_count": len(findings),
        "report_path": str(report_paths(default_audit_dir(run_root))[0]),
    }
    if getattr(args, "case_key", None):
        summary["case_keys"] = [manifest_case_key(row) for row in run_rows]
    if bool(getattr(args, "all_samples", False)):
        summary["all_samples"] = True
    if args.keep_last >= 1:
        summary["pruned"] = prune_run_roots(runs_root, keep_last=args.keep_last, dry_run=args.prune_dry_run)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return exit_code_for_findings(findings, strict=not args.report_only)


def add_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--library-root", default=str(DEFAULT_LIBRARY_ROOT))
    parser.add_argument("--powershell", default=resolve_default_powershell())
    parser.add_argument("--entrypoint", default=str(DEFAULT_PIPELINE_ENTRYPOINT))
    parser.add_argument("--prepare-timeout-seconds", type=int, default=DEFAULT_PREPARE_TIMEOUT_SECONDS)
    parser.add_argument("--ffprobe", default="ffprobe")
    parser.add_argument("--fixture-probe-timeout-seconds", type=int, default=DEFAULT_FIXTURE_PROBE_TIMEOUT_SECONDS)
    parser.add_argument("--report-only", action="store_true", help="Write findings but exit zero unless inputs crash the tool.")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit the generated Tdarr Matrix scratch test library.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    report = subparsers.add_parser("report", help="Audit existing Tdarr Matrix evidence.")
    add_common_arguments(report)
    report.add_argument("--manifest-csv", default="")
    report.add_argument("--config-path", default="")
    report.add_argument("--queue-snapshot", default="")
    report.add_argument("--effective-config", default="")
    report.add_argument("--audit-dir", default="")
    report.add_argument("--prepare-evidence", action="store_true")
    report.add_argument("--hash-sources", action="store_true", help="Hash every generated source path during report mode.")

    samples = subparsers.add_parser("run-samples", help="Create an isolated sample run and process selected files.")
    add_common_arguments(samples)
    samples.add_argument("--runs-root", default=str(DEFAULT_RUNS_ROOT))
    samples.add_argument("--run-root", default="")
    samples.add_argument("--run-id", default="")
    samples.add_argument("--samples-per-bucket", type=int, default=DEFAULT_SAMPLES_PER_BUCKET)
    samples.add_argument("--sample-timeout-seconds", type=int, default=DEFAULT_SAMPLE_TIMEOUT_SECONDS)
    samples.add_argument("--all-samples", action="store_true", help="Select every manifest row for a full-library proof run.")
    samples.add_argument(
        "--balanced-selection",
        action="store_true",
        help="Keep every available codec/container pair before filling bucket quotas; may select more than the nominal bucket quota.",
    )
    samples.add_argument(
        "--case-key",
        action="append",
        default=[],
        help="Materialize and process an exact manifest case key, formatted as '<case_id>:<view>'. May be repeated.",
    )
    samples.add_argument("--rebuild-run", action="store_true")
    samples.add_argument("--template", default=str(DEFAULT_TEMPLATE))
    samples.add_argument(
        "--keep-last",
        type=int,
        default=0,
        help="If >=1, prune older sentinel-marked run roots after a successful run, keeping the newest N. 0 disables pruning.",
    )
    samples.add_argument(
        "--prune-dry-run",
        action="store_true",
        help="With --keep-last, preview which run roots would be removed without deleting them.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.command == "report":
        return command_report(args)
    if args.command == "run-samples":
        return command_run_samples(args)
    raise ValueError(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())

__all__ = [
    "required_input_findings",
    "report_paths",
    "write_reports",
    "exit_code_for_findings",
    "audit_existing_library",
    "run_id_default",
    "command_report",
    "command_run_samples",
    "add_common_arguments",
    "parse_args",
    "main",
]
