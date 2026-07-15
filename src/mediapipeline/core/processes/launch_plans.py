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
    extra_argv: list[str] | tuple[str, ...] | None = None,
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
    if extra_argv:
        args.extend(str(item) for item in extra_argv)

    return ProcessLaunchPlan(
        args=args,
        job_kind="pipeline",
        mode=mode,
        metadata={
            "show_config": bool(show_config),
            "sleep_seconds": max(1, int(sleep_seconds)),
            "extra_args": extra_args.strip(),
            "extra_argv": [str(item) for item in (extra_argv or [])],
            "single_file": single_file or "",
        },
    )


def build_audit_launch_plan(
    resolved: ResolvedLaunchPaths,
    *,
    library_root: str,
    include_sidecars: bool,
    default_report_root: Path,
    library_roots: list[str] | None = None,
) -> ProcessLaunchPlan:
    if not resolved.powershell_host:
        raise RuntimeError("PowerShell host could not be resolved.")
    if not resolved.audit_script_path.exists():
        raise FileNotFoundError(f"Audit script not found: {resolved.audit_script_path}")

    report_root = resolved.audit_reports_path or default_report_root
    selected_roots = [str(item).strip() for item in (library_roots or []) if str(item).strip()]
    if not selected_roots and library_root:
        selected_roots = [library_root]

    args = [
        resolved.powershell_host,
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(resolved.audit_script_path),
        "-ReportRoot",
        str(report_root),
    ]
    if len(selected_roots) > 1:
        args.extend(["-LibraryRoots", *selected_roots])
    else:
        args.extend(["-LibraryRoot", selected_roots[0] if selected_roots else library_root])
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
            "library_roots": selected_roots,
            "library_root_count": len(selected_roots),
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
    execution_mode: str = "one_at_a_time",
    destination_mode: str = "auto_replace_clean_else_pending_review",
    original_policy: str = "keep",
    collision_policy: str = "replace_final",
    window_size: int = 1,
    confirm_replace_final: bool = False,
    confirm_source_overwrite: bool = False,
    confirm_original_policy: bool = False,
    confirm_delete_original: bool = False,
    plan_only: bool = False,
    command_id: str = "",
    launch_id: str = "",
    batch_id: str = "",
    enrollment_path: Path | None = None,
    manifest_path: Path | None = None,
) -> ProcessLaunchPlan:
    if not resolved.powershell_host:
        raise RuntimeError("PowerShell host could not be resolved.")
    if not resolved.rerun_script_path.exists():
        raise FileNotFoundError(f"Rerun script not found: {resolved.rerun_script_path}")
    if not csv_path.exists():
        raise FileNotFoundError(f"Rerun CSV not found: {csv_path}")
    if dry_run and plan_only:
        raise ValueError("CSV rerun launch accepts either dry_run or plan_only, not both.")
    original_policy = "keep"
    confirm_original_policy = False
    confirm_delete_original = False

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
        "-ExecutionMode",
        execution_mode,
        "-DestinationMode",
        destination_mode,
        "-CollisionPolicy",
        collision_policy,
        "-WindowSize",
        str(max(1, int(window_size))),
    ]
    if plan_only:
        args.append("-PlanOnly")
    if dry_run:
        args.append("-DryRun")
    if confirm_replace_final:
        args.append("-ConfirmReplaceFinal")
    if confirm_source_overwrite:
        args.append("-ConfirmSourceOverwrite")
    if command_id:
        args.extend(["-CommandId", command_id])
    if launch_id:
        args.extend(["-LaunchId", launch_id])
    if batch_id:
        args.extend(["-BatchId", batch_id])
    if enrollment_path is not None:
        args.extend(["-EnrollmentPath", str(enrollment_path)])
    if manifest_path is not None:
        args.extend(["-ManifestPath", str(manifest_path)])
    mode = "plan_only" if plan_only else "dry_run" if dry_run else "run"

    return ProcessLaunchPlan(
        args=args,
        job_kind="rerun_csv",
        mode=mode,
        metadata={
            "csv_path": str(csv_path),
            "dry_run": bool(dry_run),
            "plan_only": bool(plan_only),
            "default_stage_mode": stage_mode,
            "default_original_mode": original_mode,
            "default_return_mode": return_mode,
            "execution_mode": execution_mode,
            "destination_mode": destination_mode,
            "original_policy": original_policy,
            "collision_policy": collision_policy,
            "window_size": max(1, int(window_size)),
            "confirm_replace_final": bool(confirm_replace_final),
            "confirm_source_overwrite": bool(confirm_source_overwrite),
            "confirm_original_policy": bool(confirm_original_policy),
            "confirm_delete_original": bool(confirm_delete_original),
            "command_id": command_id,
            "launch_id": launch_id,
            "batch_id": batch_id,
            "enrollment_path": str(enrollment_path) if enrollment_path is not None else "",
            "manifest_path": str(manifest_path) if manifest_path is not None else "",
        },
    )
