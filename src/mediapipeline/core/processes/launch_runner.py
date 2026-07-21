from __future__ import annotations

from pathlib import Path
import subprocess
from typing import Any, Protocol

from .launch_plans import (
    ResolvedLaunchPaths,
    build_audit_launch_plan,
    build_pipeline_launch_plan,
    build_rerun_csv_launch_plan,
)


class ProcessLaunchService(Protocol):
    app_root: Path

    def _spawn(
        self,
        args: list[str],
        show_console: bool,
        *,
        resolved: ResolvedLaunchPaths | None = None,
        job_kind: str = "process",
        mode: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> subprocess.Popen[Any]: ...


def start_pipeline_for_service(
    service: ProcessLaunchService,
    resolved: ResolvedLaunchPaths,
    *,
    mode: str,
    show_config: bool,
    sleep_seconds: int,
    extra_args: str,
    extra_argv: list[str] | tuple[str, ...] | None = None,
    show_console: bool = False,
    single_file: str | None = None,
    expected_queue_plan_fingerprint: str = "",
    command_id: str = "",
    run_id: str = "",
) -> subprocess.Popen[Any]:
    plan = build_pipeline_launch_plan(
        resolved,
        mode=mode,
        show_config=show_config,
        sleep_seconds=sleep_seconds,
        extra_args=extra_args,
        extra_argv=extra_argv,
        single_file=single_file,
        expected_queue_plan_fingerprint=expected_queue_plan_fingerprint,
        command_id=command_id,
        run_id=run_id,
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
    service: ProcessLaunchService,
    resolved: ResolvedLaunchPaths,
    *,
    library_root: str,
    include_sidecars: bool,
    show_console: bool,
    library_roots: list[str] | None = None,
) -> subprocess.Popen[Any]:
    plan = build_audit_launch_plan(
        resolved,
        library_root=library_root,
        library_roots=library_roots,
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
    service: ProcessLaunchService,
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
    show_console: bool,
    plan_only: bool = False,
    command_id: str = "",
    launch_id: str = "",
    batch_id: str = "",
    enrollment_path: Path | None = None,
    manifest_path: Path | None = None,
) -> subprocess.Popen[Any]:
    plan = build_rerun_csv_launch_plan(
        resolved,
        csv_path,
        dry_run=dry_run,
        plan_only=plan_only,
        stage_mode=stage_mode,
        original_mode=original_mode,
        return_mode=return_mode,
        execution_mode=execution_mode,
        destination_mode=destination_mode,
        original_policy=original_policy,
        collision_policy=collision_policy,
        window_size=window_size,
        confirm_replace_final=confirm_replace_final,
        confirm_source_overwrite=confirm_source_overwrite,
        confirm_original_policy=confirm_original_policy,
        confirm_delete_original=confirm_delete_original,
        command_id=command_id,
        launch_id=launch_id,
        batch_id=batch_id,
        enrollment_path=enrollment_path,
        manifest_path=manifest_path,
    )
    return service._spawn(
        plan.args,
        show_console=show_console,
        resolved=resolved,
        job_kind=plan.job_kind,
        mode=plan.mode,
        metadata=plan.metadata,
    )
