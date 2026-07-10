"""CSV rerun launch request and result policy helpers."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mediapipeline.core.kernel.dto_commands import CommandResult

CSV_RERUN_START_COMMAND = "rerun.start"
CSV_RERUN_PATH_ERROR = "CSV path is required."
CSV_RERUN_MODE_ERROR = (
    "Executable CSV rerun starts require supported destination/collision lifecycle fields; "
    "source mutation policy is not part of CSV rerun launch, and final replacement requires strict confirmation."
)
CSV_RERUN_PLAN_MODE_ERROR = "dry_run and plan_only cannot both be true."

RERUN_EXECUTION_MODES = ("one_at_a_time", "windowed", "batch_stage_all")
RERUN_DESTINATION_MODES = (
    "auto_replace_clean_else_pending_review",
    "review_workspace",
    "pending_publish",
    "publish_non_overlap",
    "publish_replace_final",
)
RERUN_ORIGINAL_POLICIES = (
    "keep",
)
RERUN_COLLISION_POLICIES = ("suffix", "fail", "replace_final")
RERUN_DEFAULT_EXECUTION_MODE = "one_at_a_time"
RERUN_DEFAULT_DESTINATION_MODE = "auto_replace_clean_else_pending_review"
RERUN_DEFAULT_ORIGINAL_POLICY = "keep"
RERUN_DEFAULT_COLLISION_POLICY = "replace_final"
RERUN_DEFAULT_WINDOW_SIZE = 1
RERUN_MAX_WINDOW_SIZE = 100
RERUN_REPLACE_FINAL_DESTINATION_MODES = (
    "auto_replace_clean_else_pending_review",
    "publish_replace_final",
)
RERUN_FINAL_OUTPUT_OVERRIDE_FIELDS = (
    "plex_planned_path",
    "PlexPlannedPath",
    "planned_final_path",
    "PlannedFinalPath",
    "final_output_path",
    "FinalOutputPath",
    "server_out",
    "ServerOut",
    "completed_output_path",
    "CompletedOutputPath",
    "completed_path",
    "CompletedPath",
    "PlannedOutputPath",
    "planned_output_path",
    "OutputPath",
    "output_path",
)
RERUN_FINAL_OUTPUT_ROOT_ERROR = "final output destination resolves outside configured output root"
RERUN_FINAL_OUTPUT_ROOT_UNAVAILABLE = "configured output root is unavailable for final output destination validation"


@dataclass(frozen=True)
class RerunLifecyclePolicy:
    execution_mode: str
    destination_mode: str
    original_policy: str
    collision_policy: str
    window_size: int
    confirm_replace_final: bool
    confirm_source_overwrite: bool
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
            "confirm_source_overwrite": self.confirm_source_overwrite,
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


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _mapping_value(mapping: Mapping[str, Any], *names: str) -> Any:
    lowered = {str(key).casefold(): value for key, value in mapping.items()}
    for name in names:
        key = name.casefold()
        if key in lowered:
            return lowered[key]
    return None


def _object_value(value: Any, *names: str) -> Any:
    if isinstance(value, Mapping):
        return _mapping_value(value, *names)
    for name in names:
        if hasattr(value, name):
            return getattr(value, name)
    return None


def _object_text(value: Any, *names: str) -> str:
    raw = _object_value(value, *names)
    return _clean_text(raw)


def _config_text(config: Mapping[str, Any], *names: str) -> str:
    return _clean_text(_mapping_value(config, *names))


def _profile_enabled(profile: Any) -> bool:
    raw = _object_value(profile, "enabled", "Enabled")
    if raw is None:
        return True
    if isinstance(raw, bool):
        return raw
    text = _clean_text(raw).casefold()
    return text not in {"0", "false", "no", "off", "disabled"}


def _library_profiles(config: Mapping[str, Any]) -> tuple[Any, ...]:
    raw = _mapping_value(config, "LibraryProfiles", "library_profiles")
    if raw is None:
        return ()
    if isinstance(raw, Mapping):
        values = tuple(raw.values())
        if any(isinstance(item, Mapping) for item in values):
            return values
        return (raw,)
    if isinstance(raw, (list, tuple, set)):
        return tuple(raw)
    return ()


def _windows_path_under(path: str, root: str) -> bool:
    try:
        path_obj = PureWindowsPath(path)
        root_obj = PureWindowsPath(root)
        path_obj.relative_to(root_obj)
        return True
    except (TypeError, ValueError):
        return False


def rerun_path_resolves_under_root(path: Any, root: Any) -> bool:
    path_text = _clean_text(path)
    root_text = _clean_text(root)
    if not path_text or not root_text:
        return False
    try:
        Path(path_text).resolve(strict=False).relative_to(Path(root_text).resolve(strict=False))
        return True
    except (OSError, RuntimeError, ValueError):
        return _windows_path_under(path_text, root_text)


def rerun_paths_resolve_same(left: Any, right: Any) -> bool:
    left_text = _clean_text(left)
    right_text = _clean_text(right)
    if not left_text or not right_text:
        return False
    try:
        return Path(left_text).resolve(strict=False) == Path(right_text).resolve(strict=False)
    except (OSError, RuntimeError, ValueError):
        return str(PureWindowsPath(left_text)).rstrip("\\/").casefold() == str(PureWindowsPath(right_text)).rstrip("\\/").casefold()


def rerun_final_output_override(row: Mapping[str, Any]) -> tuple[str, str]:
    for field in RERUN_FINAL_OUTPUT_OVERRIDE_FIELDS:
        text = _clean_text(_mapping_value(row, field))
        if text:
            return field, text
    return "", ""


def rerun_final_output_for_row(
    row: Mapping[str, Any],
    *,
    source_path: Any = "",
    source_path_destination: bool = False,
    planned_output_path: Any = "",
) -> tuple[str, str]:
    """Return the explicit final-output override, falling back to planned output."""
    if source_path_destination and _clean_text(source_path):
        return "source_path", _clean_text(source_path)
    field, value = rerun_final_output_override(row)
    return (field, value) if value else ("planned_output_path", _clean_text(planned_output_path))


def rerun_destination_replaces_final(destination_mode: str, collision_policy: str) -> bool:
    return destination_mode in {"auto_replace_clean_else_pending_review", "publish_replace_final"} and collision_policy == "replace_final"


def rerun_source_path_destination_requested(lifecycle: RerunLifecyclePolicy) -> bool:
    return lifecycle.confirm_source_overwrite is True


def rerun_effective_output_root_for_source(resolved: Any, source_path: Any) -> Path | None:
    config = getattr(resolved, "config_data", {}) if resolved is not None else {}
    if not isinstance(config, Mapping):
        return None
    fallback_root = _config_text(config, "Outsource", "outsource")
    source_text = _clean_text(source_path)
    if source_text:
        for profile in _library_profiles(config):
            if not _profile_enabled(profile):
                continue
            profile_source = _object_text(profile, "source_path", "SourcePath", "sourceRoot", "SourceRoot")
            profile_output = _object_text(profile, "output_path", "OutputPath", "outputRoot", "OutputRoot")
            if not profile_source or not rerun_path_resolves_under_root(source_text, profile_source):
                continue
            return Path(profile_output or fallback_root) if (profile_output or fallback_root) else None
    return Path(fallback_root) if fallback_root else None


def rerun_final_output_root_violation(
    resolved: Any,
    row: Mapping[str, Any],
    *,
    source_path: Any = "",
    final_output_path: Any = "",
    final_output_field: str = "",
    confirm_source_overwrite: bool = False,
) -> str:
    field = final_output_field
    target = _clean_text(final_output_path)
    if not target:
        field, target = rerun_final_output_override(row)
    if not target:
        return ""
    source_text = _clean_text(source_path or _mapping_value(row, "source_path", "Path", "SourcePath"))
    if confirm_source_overwrite and source_text and rerun_paths_resolve_same(target, source_text):
        return ""
    root = rerun_effective_output_root_for_source(resolved, source_text)
    if root is None:
        return RERUN_FINAL_OUTPUT_ROOT_UNAVAILABLE
    if rerun_path_resolves_under_root(target, root):
        return ""
    field_detail = f" from {field}" if field else ""
    return f"{RERUN_FINAL_OUTPUT_ROOT_ERROR}{field_detail}: {target}"


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
    if return_mode in {
        "auto_replace_clean_else_pending_review",
        "auto_replace_clean",
        "clean_replace_else_pending",
        "normal_remediation",
    }:
        return "auto_replace_clean_else_pending_review"
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
    if destination_mode == "auto_replace_clean_else_pending_review":
        return "replace_original"
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


def rerun_original_policy_from_destination(destination_mode: str, collision_policy: str) -> str:
    _ = (destination_mode, collision_policy)
    return RERUN_DEFAULT_ORIGINAL_POLICY


def rerun_lifecycle_from_request(request: dict[str, Any]) -> RerunLifecyclePolicy:
    stage_mode, _original_mode_alias, return_mode_alias = rerun_modes_from_request(request)
    compatibility_aliases_used = any(key in request for key in ("stage_mode", "original_mode", "return_mode"))
    execution_mode = normalize_rerun_lifecycle_value(
        request.get("execution_mode"),
        RERUN_DEFAULT_EXECUTION_MODE,
    )
    destination_mode = normalize_rerun_lifecycle_value(
        request.get("destination_mode"),
        _destination_mode_from_alias(return_mode_alias) if compatibility_aliases_used else RERUN_DEFAULT_DESTINATION_MODE,
    )
    collision_policy = normalize_rerun_lifecycle_value(
        request.get("collision_policy"),
        "replace_final" if destination_mode in RERUN_REPLACE_FINAL_DESTINATION_MODES else "suffix",
    )
    original_policy = rerun_original_policy_from_destination(destination_mode, collision_policy)
    window_size = _bounded_window_size(request.get("window_size"), execution_mode)
    return RerunLifecyclePolicy(
        execution_mode=execution_mode,
        destination_mode=destination_mode,
        original_policy=original_policy,
        collision_policy=collision_policy,
        window_size=window_size,
        confirm_replace_final=rerun_bool_from_request(request, "confirm_replace_final"),
        confirm_source_overwrite=rerun_bool_from_request(request, "confirm_source_overwrite"),
        confirm_original_policy=False,
        confirm_delete_original=False,
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
    if lifecycle.collision_policy not in RERUN_COLLISION_POLICIES:
        errors.append(f"collision_policy must be one of: {', '.join(RERUN_COLLISION_POLICIES)}.")
    if lifecycle.stage_mode != "copy":
        errors.append("stage_mode compatibility alias only supports copy; source-moving staging is not accepted.")
    if (
        lifecycle.destination_mode in RERUN_REPLACE_FINAL_DESTINATION_MODES
        and lifecycle.confirm_replace_final is not True
    ):
        errors.append(f"{lifecycle.destination_mode} requires confirm_replace_final=true.")
    if lifecycle.destination_mode == "auto_replace_clean_else_pending_review" and lifecycle.collision_policy != "replace_final":
        errors.append("auto_replace_clean_else_pending_review requires collision_policy=replace_final.")
    if lifecycle.confirm_source_overwrite is True and lifecycle.confirm_replace_final is not True:
        errors.append("confirm_source_overwrite=true requires confirm_replace_final=true.")
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
    confirm_replace_final: bool = False,
    confirm_source_overwrite: bool = False,
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
        "confirm_replace_final": bool(confirm_replace_final),
        "confirm_source_overwrite": bool(confirm_source_overwrite),
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
        message="CSV rerun execution is limited to backend-owned review, pending-publish, and confirmed replacement policies; source-mutating and in-place modes are blocked.",
        severity="error",
        errors=[CSV_RERUN_MODE_ERROR],
    )


def rerun_lifecycle_error_result(errors: list[str]) -> CommandResult:
    detail = "; ".join(str(error) for error in errors if str(error).strip())
    message = "CSV rerun lifecycle policy is blocked until required confirmations and supported modes are selected."
    if detail:
        message = f"{message} {detail}"
    return _command_result(
        command=CSV_RERUN_START_COMMAND,
        ok=False,
        message=message,
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
    confirm_replace_final: bool = False,
    confirm_source_overwrite: bool = False,
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
            confirm_replace_final=confirm_replace_final,
            confirm_source_overwrite=confirm_source_overwrite,
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
    "RERUN_FINAL_OUTPUT_OVERRIDE_FIELDS",
    "RERUN_FINAL_OUTPUT_ROOT_ERROR",
    "RERUN_FINAL_OUTPUT_ROOT_UNAVAILABLE",
    "RerunLifecyclePolicy",
    "normalize_rerun_csv_path",
    "rerun_path_resolves_under_root",
    "rerun_paths_resolve_same",
    "rerun_final_output_override",
    "rerun_effective_output_root_for_source",
    "rerun_final_output_root_violation",
    "rerun_csv_path_from_request",
    "normalize_rerun_mode",
    "normalize_rerun_lifecycle_value",
    "rerun_modes_from_request",
    "rerun_original_policy_from_destination",
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
