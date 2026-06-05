from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import shlex
from typing import Any, Protocol


class ResolvedLaunchPaths(Protocol):
    pipeline_path: Path
    config_path: Path
    audit_script_path: Path
    rerun_script_path: Path
    powershell_host: str | None
    audit_reports_path: Path | None
    audit_score_policy_path: Path | None
    audit_ignore_manifest_path: Path | None


@dataclass(frozen=True)
class ProcessLaunchPlan:
    args: list[str]
    job_kind: str
    mode: str
    metadata: dict[str, Any]


def build_pipeline_launch_plan(
    resolved: ResolvedLaunchPaths,
    *,
    mode: str,
    show_config: bool,
    sleep_seconds: int,
    extra_args: str,
    single_file: str | None = None,
) -> ProcessLaunchPlan:
    if not resolved.powershell_host:
        raise RuntimeError("PowerShell host could not be resolved.")
    if not resolved.pipeline_path.exists():
        raise FileNotFoundError(f"Pipeline script not found: {resolved.pipeline_path}")

    args = [
        resolved.powershell_host,
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(resolved.pipeline_path),
        "-ConfigPath",
        str(resolved.config_path),
        "-SleepSeconds",
        str(max(1, int(sleep_seconds))),
    ]
    if mode == "once":
        args.append("-Once")
    elif mode == "validate":
        args.append("-ValidateOnly")
    elif mode == "drain_pending_pushes":
        args.append("-DrainPendingPushes")
    if show_config:
        args.append("-ShowConfig")
    if single_file:
        args.extend(["-SingleFile", single_file])
    if extra_args.strip():
        try:
            parsed_extra_args = shlex.split(extra_args.strip(), posix=(os.name != "nt"))
        except ValueError as exc:
            raise RuntimeError(f"Extra arguments could not be parsed: {exc}") from exc
        args.extend(parsed_extra_args)

    return ProcessLaunchPlan(
        args=args,
        job_kind="pipeline",
        mode=mode,
        metadata={
            "show_config": bool(show_config),
            "sleep_seconds": max(1, int(sleep_seconds)),
            "extra_args": extra_args.strip(),
            "single_file": single_file or "",
        },
    )


def build_audit_launch_plan(
    resolved: ResolvedLaunchPaths,
    *,
    library_root: str,
    include_sidecars: bool,
    default_report_root: Path,
) -> ProcessLaunchPlan:
    if not resolved.powershell_host:
        raise RuntimeError("PowerShell host could not be resolved.")
    if not resolved.audit_script_path.exists():
        raise FileNotFoundError(f"Audit script not found: {resolved.audit_script_path}")

    report_root = resolved.audit_reports_path or default_report_root
    args = [
        resolved.powershell_host,
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(resolved.audit_script_path),
        "-LibraryRoot",
        library_root,
        "-ReportRoot",
        str(report_root),
    ]
    if resolved.config_path.exists():
        args.extend(["-ConfigPath", str(resolved.config_path)])
    if include_sidecars:
        args.append("-IncludeSidecars")
    if getattr(resolved, "audit_score_policy_path", None):
        args.extend(["-ScorePolicyPath", str(resolved.audit_score_policy_path)])
    if getattr(resolved, "audit_ignore_manifest_path", None):
        args.extend(["-IgnoreManifestPath", str(resolved.audit_ignore_manifest_path)])

    return ProcessLaunchPlan(
        args=args,
        job_kind="audit",
        mode="audit",
        metadata={
            "library_root": library_root,
            "report_root": str(report_root),
            "include_sidecars": bool(include_sidecars),
        },
    )


def build_rerun_csv_launch_plan(
    resolved: ResolvedLaunchPaths,
    csv_path: Path,
    *,
    dry_run: bool,
    stage_mode: str,
    original_mode: str,
    return_mode: str,
) -> ProcessLaunchPlan:
    if not resolved.powershell_host:
        raise RuntimeError("PowerShell host could not be resolved.")
    if not resolved.rerun_script_path.exists():
        raise FileNotFoundError(f"Rerun script not found: {resolved.rerun_script_path}")
    if not csv_path.exists():
        raise FileNotFoundError(f"Rerun CSV not found: {csv_path}")

    args = [
        resolved.powershell_host,
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(resolved.rerun_script_path),
        "-CsvPath",
        str(csv_path),
        "-ConfigPath",
        str(resolved.config_path),
        "-DefaultStageMode",
        stage_mode,
        "-DefaultOriginalMode",
        original_mode,
        "-DefaultReturnMode",
        return_mode,
    ]
    if dry_run:
        args.append("-DryRun")

    return ProcessLaunchPlan(
        args=args,
        job_kind="rerun_csv",
        mode="dry_run" if dry_run else "run",
        metadata={
            "csv_path": str(csv_path),
            "default_stage_mode": stage_mode,
            "default_original_mode": original_mode,
            "default_return_mode": return_mode,
        },
    )
