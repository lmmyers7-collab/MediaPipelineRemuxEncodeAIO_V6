"""CSV rerun launch request and result policy helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mediapipeline.core.kernel.dto_commands import CommandResult

CSV_RERUN_START_COMMAND = "rerun.start"
CSV_RERUN_PATH_ERROR = "CSV path is required."
CSV_RERUN_MODE_ERROR = (
    "Executable CSV rerun starts require supported lifecycle fields; source mutation "
    "policies are disabled, and final replacement requires strict confirmation."
)
CSV_RERUN_PLAN_MODE_ERROR = "dry_run and plan_only cannot both be true."

RERUN_EXECUTION_MODES = ("one_at_a_time", "windowed", "batch_stage_all")
RERUN_DESTINATION_MODES = (
    "review_workspace",
    "pending_publish",
    "publish_non_overlap",
    "publish_replace_final",
)
RERUN_ORIGINAL_POLICIES = (
    "keep",
    "rename_after_publish",
    "move_to_hold_after_publish",
    "hold_then_delete_after_publish",
)
RERUN_COLLISION_POLICIES = ("suffix", "fail", "replace_final")
RERUN_DEFAULT_EXECUTION_MODE = "one_at_a_time"
RERUN_DEFAULT_DESTINATION_MODE = "review_workspace"
RERUN_DEFAULT_ORIGINAL_POLICY = "keep"
RERUN_DEFAULT_COLLISION_POLICY = "suffix"
RERUN_DEFAULT_WINDOW_SIZE = 1
RERUN_MAX_WINDOW_SIZE = 100


@dataclass(frozen=True)
class RerunLifecyclePolicy:
    execution_mode: str
    destination_mode: str
    original_policy: str
    collision_policy: str
    window_size: int
    confirm_replace_final: bool
    confirm_original_policy: bool
    confirm_delete_original: bool
    stage_mode: str
    original_mode: str
    return_mode: str
    compatibility_aliases_used: bool = False

    def to_mapping(self) -> dict[str, Any]:
        return {
            "execution_mode": self.execution_mode,
            "destination_mode": self.destination_mode,
            "original_policy": self.original_policy,
            "collision_policy": self.collision_policy,
            "window_size": self.window_size,
            "confirm_replace_final": self.confirm_replace_final,
            "confirm_original_policy": self.confirm_original_policy,
            "confirm_delete_original": self.confirm_delete_original,
            "stage_mode": self.stage_mode,
            "original_mode": self.original_mode,
            "return_mode": self.return_mode,
            "compatibility_aliases_used": self.compatibility_aliases_used,
        }


def _command_result(**kwargs: Any) -> CommandResult:
    from mediapipeline.core.kernel.dto_commands import CommandResult

    return CommandResult(**kwargs)


def normalize_rerun_csv_path(value: Any) -> str:
    return str(value or "").strip()


def rerun_csv_path_from_request(request: dict[str, Any]) -> Path | None:
    raw_csv_path = normalize_rerun_csv_path(request.get("csv_path"))
    if not raw_csv_path:
        return None
    return Path(raw_csv_path)


def normalize_rerun_mode(value: Any, default: str) -> str:
    return str(value or default).strip().casefold()


def normalize_rerun_lifecycle_value(value: Any, default: str) -> str:
    text = str(value or default).strip().casefold().replace("-", "_").replace(" ", "_")
    return text or default


def _bounded_window_size(value: Any, execution_mode: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = RERUN_DEFAULT_WINDOW_SIZE
    parsed = min(RERUN_MAX_WINDOW_SIZE, max(1, parsed))
    if execution_mode == "one_at_a_time":
        return 1
    return parsed


def rerun_modes_from_request(request: dict[str, Any]) -> tuple[str, str, str]:
    return (
        normalize_rerun_mode(request.get("stage_mode"), "copy"),
        normalize_rerun_mode(request.get("original_mode"), "keep"),
        normalize_rerun_mode(request.get("return_mode"), "park"),
    )


def _destination_mode_from_alias(return_mode: str) -> str:
    if return_mode in {"park", "review", "review_workspace"}:
        return "review_workspace"
    if return_mode in {"queue", "pending", "pending_publish", "publish"}:
        return "pending_publish"
    if return_mode in {"publish_non_overlap", "non_overlap"}:
        return "publish_non_overlap"
    if return_mode in {"replace", "replace_final", "replace_original", "publish_replace_final"}:
        return "publish_replace_final"
    return RERUN_DEFAULT_DESTINATION_MODE


def _return_mode_from_destination(destination_mode: str) -> str:
    if destination_mode == "review_workspace":
        return "park"
    if destination_mode == "pending_publish":
        return "pending_publish"
    if destination_mode == "publish_non_overlap":
        return "publish_non_overlap"
    if destination_mode == "publish_replace_final":
        return "replace_original"
    return "park"


def _original_policy_from_alias(original_mode: str) -> str:
    if original_mode in {"", "keep"}:
        return "keep"
    if original_mode in {"rename", "rename_after_publish"}:
        return "rename_after_publish"
    if original_mode in {"move", "hold", "move_to_hold", "move_to_hold_after_publish"}:
        return "move_to_hold_after_publish"
    if original_mode in {"delete", "hold_then_delete", "hold_then_delete_after_publish"}:
        return "hold_then_delete_after_publish"
    return RERUN_DEFAULT_ORIGINAL_POLICY


def _original_mode_from_policy(original_policy: str) -> str:
    if original_policy == "keep":
        return "keep"
    if original_policy == "rename_after_publish":
        return "rename_after_publish"
    if original_policy == "move_to_hold_after_publish":
        return "move_to_hold_after_publish"
    if original_policy == "hold_then_delete_after_publish":
        return "delete"
    return "keep"


def rerun_lifecycle_from_request(request: dict[str, Any]) -> RerunLifecyclePolicy:
    stage_mode, original_mode_alias, return_mode_alias = rerun_modes_from_request(request)
    compatibility_aliases_used = any(key in request for key in ("stage_mode", "original_mode", "return_mode"))
    execution_mode = normalize_rerun_lifecycle_value(
        request.get("execution_mode"),
        RERUN_DEFAULT_EXECUTION_MODE,
    )
    destination_mode = normalize_rerun_lifecycle_value(
        request.get("destination_mode"),
        _destination_mode_from_alias(return_mode_alias) if compatibility_aliases_used else RERUN_DEFAULT_DESTINATION_MODE,
    )
    original_policy = normalize_rerun_lifecycle_value(
        request.get("original_policy"),
        _original_policy_from_alias(original_mode_alias) if compatibility_aliases_used else RERUN_DEFAULT_ORIGINAL_POLICY,
    )
    collision_policy = normalize_rerun_lifecycle_value(
        request.get("collision_policy"),
        "replace_final" if destination_mode == "publish_replace_final" else RERUN_DEFAULT_COLLISION_POLICY,
    )
    window_size = _bounded_window_size(request.get("window_size"), execution_mode)
    return RerunLifecyclePolicy(
        execution_mode=execution_mode,
        destination_mode=destination_mode,
        original_policy=original_policy,
        collision_policy=collision_policy,
        window_size=window_size,
        confirm_replace_final=rerun_bool_from_request(request, "confirm_replace_final"),
        confirm_original_policy=rerun_bool_from_request(request, "confirm_original_policy"),
        confirm_delete_original=rerun_bool_from_request(request, "confirm_delete_original"),
        stage_mode=stage_mode,
        original_mode="keep",
        return_mode=_return_mode_from_destination(destination_mode),
        compatibility_aliases_used=compatibility_aliases_used,
    )


def rerun_lifecycle_errors(lifecycle: RerunLifecyclePolicy) -> list[str]:
    errors: list[str] = []
    if lifecycle.execution_mode not in RERUN_EXECUTION_MODES:
        errors.append(f"execution_mode must be one of: {', '.join(RERUN_EXECUTION_MODES)}.")
    if lifecycle.destination_mode not in RERUN_DESTINATION_MODES:
        errors.append(f"destination_mode must be one of: {', '.join(RERUN_DESTINATION_MODES)}.")
    if lifecycle.original_policy not in RERUN_ORIGINAL_POLICIES:
        errors.append(f"original_policy must be one of: {', '.join(RERUN_ORIGINAL_POLICIES)}.")
    if lifecycle.collision_policy not in RERUN_COLLISION_POLICIES:
        errors.append(f"collision_policy must be one of: {', '.join(RERUN_COLLISION_POLICIES)}.")
    if lifecycle.stage_mode != "copy":
        errors.append("stage_mode compatibility alias only supports copy; source-moving staging is not accepted.")
    if lifecycle.destination_mode == "publish_replace_final" and lifecycle.confirm_replace_final is not True:
        errors.append("publish_replace_final requires confirm_replace_final=true.")
    if lifecycle.original_policy != "keep":
        errors.append("CSV rerun original source policies are disabled until final-output proof is recorded by a separate cleanup flow.")
    return errors


def rerun_modes_are_supported(stage_mode: str, original_mode: str, return_mode: str) -> bool:
    return stage_mode == "copy" and original_mode == "keep" and return_mode == "park"


def rerun_bool_from_request(request: dict[str, Any], key: str) -> bool:
    return request.get(key) is True


def rerun_dry_run_from_request(request: dict[str, Any]) -> bool:
    return rerun_bool_from_request(request, "dry_run")


def rerun_plan_only_from_request(request: dict[str, Any]) -> bool:
    return rerun_bool_from_request(request, "plan_only")


def rerun_plan_flags_are_supported(dry_run: bool, plan_only: bool) -> bool:
    return not (dry_run and plan_only)


def rerun_run_label(dry_run: bool, plan_only: bool = False) -> str:
    if plan_only:
        return "plan-only check"
    return "dry run" if dry_run else "run"


def rerun_start_success_message(pid: int, dry_run: bool, plan_only: bool = False) -> str:
    return f"Started CSV rerun {rerun_run_label(dry_run, plan_only)} via PID {pid}."


def rerun_start_success_data(
    *,
    csv_path: Path,
    dry_run: bool,
    plan_only: bool,
    stage_mode: str,
    original_mode: str,
    return_mode: str,
    pid: int,
    launch_logs: str,
    execution_mode: str = RERUN_DEFAULT_EXECUTION_MODE,
    destination_mode: str = RERUN_DEFAULT_DESTINATION_MODE,
    original_policy: str = RERUN_DEFAULT_ORIGINAL_POLICY,
    collision_policy: str = RERUN_DEFAULT_COLLISION_POLICY,
    window_size: int = RERUN_DEFAULT_WINDOW_SIZE,
    source_csv_path: Path | None = None,
    scoped_csv_path: Path | None = None,
    scope: dict[str, Any] | None = None,
    preview_counts: dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = {
        "csv_path": str(csv_path),
        "dry_run": dry_run,
        "plan_only": plan_only,
        "stage_mode": stage_mode,
        "original_mode": original_mode,
        "return_mode": return_mode,
        "execution_mode": execution_mode,
        "destination_mode": destination_mode,
        "original_policy": original_policy,
        "collision_policy": collision_policy,
        "window_size": window_size,
        "pid": pid,
        "logs": launch_logs,
    }
    if source_csv_path is not None:
        data["source_csv_path"] = str(source_csv_path)
    if scoped_csv_path is not None:
        data["scoped_csv_path"] = str(scoped_csv_path)
    if scope is not None:
        data["scope"] = dict(scope)
    if preview_counts is not None:
        data["preview_counts"] = dict(preview_counts)
    return data


def rerun_csv_path_missing_result() -> CommandResult:
    return _command_result(
        command=CSV_RERUN_START_COMMAND,
        ok=False,
        message="CSV rerun start requires csv_path.",
        severity="error",
        errors=[CSV_RERUN_PATH_ERROR],
    )


def rerun_mode_error_result() -> CommandResult:
    return _command_result(
        command=CSV_RERUN_START_COMMAND,
        ok=False,
        message="CSV rerun execution is limited to copy/keep/park; source-mutating and in-place modes are blocked.",
        severity="error",
        errors=[CSV_RERUN_MODE_ERROR],
    )


def rerun_lifecycle_error_result(errors: list[str]) -> CommandResult:
    return _command_result(
        command=CSV_RERUN_START_COMMAND,
        ok=False,
        message="CSV rerun lifecycle policy is blocked until required confirmations and supported modes are selected.",
        severity="error",
        errors=list(errors) or [CSV_RERUN_MODE_ERROR],
    )


def rerun_plan_mode_error_result() -> CommandResult:
    return _command_result(
        command=CSV_RERUN_START_COMMAND,
        ok=False,
        message="CSV rerun accepts either dry_run or plan_only, not both.",
        severity="error",
        errors=[CSV_RERUN_PLAN_MODE_ERROR],
    )


def rerun_start_active_work_result(block_message: str) -> CommandResult:
    return _command_result(
        command=CSV_RERUN_START_COMMAND,
        ok=False,
        message=block_message,
        severity="warning",
        warnings=[block_message],
        refresh_hint="snapshot",
    )


def rerun_start_config_blocked_result(message: str, data: dict[str, Any]) -> CommandResult:
    return _command_result(
        command=CSV_RERUN_START_COMMAND,
        ok=False,
        message=message,
        severity="error",
        errors=[message],
        refresh_hint="settings",
        data=data,
    )


def rerun_start_exception_result(exc: Exception) -> CommandResult:
    return _command_result(
        command=CSV_RERUN_START_COMMAND,
        ok=False,
        message=f"CSV rerun start failed: {exc}",
        severity="error",
        errors=[str(exc)],
        refresh_hint="snapshot",
    )


def rerun_start_success_result(
    *,
    csv_path: Path,
    dry_run: bool,
    plan_only: bool,
    stage_mode: str,
    original_mode: str,
    return_mode: str,
    pid: int,
    launch_logs: str,
    execution_mode: str = RERUN_DEFAULT_EXECUTION_MODE,
    destination_mode: str = RERUN_DEFAULT_DESTINATION_MODE,
    original_policy: str = RERUN_DEFAULT_ORIGINAL_POLICY,
    collision_policy: str = RERUN_DEFAULT_COLLISION_POLICY,
    window_size: int = RERUN_DEFAULT_WINDOW_SIZE,
    source_csv_path: Path | None = None,
    scoped_csv_path: Path | None = None,
    scope: dict[str, Any] | None = None,
    preview_counts: dict[str, Any] | None = None,
) -> CommandResult:
    return _command_result(
        command=CSV_RERUN_START_COMMAND,
        ok=True,
        message=rerun_start_success_message(pid, dry_run, plan_only),
        severity="info",
        refresh_hint="snapshot",
        data=rerun_start_success_data(
            csv_path=csv_path,
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
            pid=pid,
            launch_logs=launch_logs,
            source_csv_path=source_csv_path,
            scoped_csv_path=scoped_csv_path,
            scope=scope,
            preview_counts=preview_counts,
        ),
    )

__all__ = [
    "CSV_RERUN_START_COMMAND",
    "CSV_RERUN_PATH_ERROR",
    "CSV_RERUN_MODE_ERROR",
    "CSV_RERUN_PLAN_MODE_ERROR",
    "RERUN_EXECUTION_MODES",
    "RERUN_DESTINATION_MODES",
    "RERUN_ORIGINAL_POLICIES",
    "RERUN_COLLISION_POLICIES",
    "RERUN_DEFAULT_EXECUTION_MODE",
    "RERUN_DEFAULT_DESTINATION_MODE",
    "RERUN_DEFAULT_ORIGINAL_POLICY",
    "RERUN_DEFAULT_COLLISION_POLICY",
    "RerunLifecyclePolicy",
    "normalize_rerun_csv_path",
    "rerun_csv_path_from_request",
    "normalize_rerun_mode",
    "normalize_rerun_lifecycle_value",
    "rerun_modes_from_request",
    "rerun_lifecycle_from_request",
    "rerun_lifecycle_errors",
    "rerun_modes_are_supported",
    "rerun_bool_from_request",
    "rerun_dry_run_from_request",
    "rerun_plan_only_from_request",
    "rerun_plan_flags_are_supported",
    "rerun_run_label",
    "rerun_start_success_message",
    "rerun_start_success_data",
    "rerun_csv_path_missing_result",
    "rerun_mode_error_result",
    "rerun_lifecycle_error_result",
    "rerun_plan_mode_error_result",
    "rerun_start_active_work_result",
    "rerun_start_config_blocked_result",
    "rerun_start_exception_result",
    "rerun_start_success_result",
]
