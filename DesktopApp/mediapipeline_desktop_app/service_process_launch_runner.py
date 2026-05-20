from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from .models import ResolvedPaths
from .service_process_launch_plans import (
    build_audit_launch_plan,
    build_pipeline_launch_plan,
    build_rerun_csv_launch_plan,
)
from .service_runner_protocols import ProcessLaunchServiceProtocol


def start_pipeline_for_service(
    service: ProcessLaunchServiceProtocol,
    resolved: ResolvedPaths,
    *,
    mode: str,
    show_config: bool,
    sleep_seconds: int,
    extra_args: str,
    show_console: bool,
    single_file: str | None = None,
) -> subprocess.Popen[Any]:
    plan = build_pipeline_launch_plan(
        resolved,
        mode=mode,
        show_config=show_config,
        sleep_seconds=sleep_seconds,
        extra_args=extra_args,
        single_file=single_file,
    )
    return service._spawn(
        plan.args,
        show_console=show_console,
        resolved=resolved,
        job_kind=plan.job_kind,
        mode=plan.mode,
        metadata=plan.metadata,
    )


def start_audit_for_service(
    service: ProcessLaunchServiceProtocol,
    resolved: ResolvedPaths,
    *,
    library_root: str,
    include_sidecars: bool,
    show_console: bool,
) -> subprocess.Popen[Any]:
    plan = build_audit_launch_plan(
        resolved,
        library_root=library_root,
        include_sidecars=include_sidecars,
        default_report_root=service.app_root / "AuditReports",
    )
    return service._spawn(
        plan.args,
        show_console=show_console,
        resolved=resolved,
        job_kind=plan.job_kind,
        mode=plan.mode,
        metadata=plan.metadata,
    )


def start_rerun_csv_for_service(
    service: ProcessLaunchServiceProtocol,
    resolved: ResolvedPaths,
    csv_path: Path,
    *,
    dry_run: bool,
    stage_mode: str,
    original_mode: str,
    return_mode: str,
    show_console: bool,
) -> subprocess.Popen[Any]:
    plan = build_rerun_csv_launch_plan(
        resolved,
        csv_path,
        dry_run=dry_run,
        stage_mode=stage_mode,
        original_mode=original_mode,
        return_mode=return_mode,
    )
    return service._spawn(
        plan.args,
        show_console=show_console,
        resolved=resolved,
        job_kind=plan.job_kind,
        mode=plan.mode,
        metadata=plan.metadata,
    )
