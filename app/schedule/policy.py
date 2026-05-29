"""Schedule grid, preview, and save result policy helpers."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mediapipeline_desktop_app.application.dto_commands import CommandResult

from app.shared.constants import SCHEDULE_DAY_NAMES


ScheduleLabelFormatter = Callable[[int], str]
SCHEDULE_PREVIEW_COMMAND = "schedule.preview"
SCHEDULE_SAVE_COMMAND = "schedule.save"
SCHEDULE_REFRESH_HINT = "schedule"
SCHEDULE_TIME_RE = re.compile(
    r"^\s*(?P<hour>\d{1,2})(?::(?P<minute>\d{2}))?\s*(?P<suffix>am|pm|a\.m\.|p\.m\.)?\s*$",
    re.IGNORECASE,
)


def _command_result(**kwargs: Any) -> "CommandResult":
    from mediapipeline_desktop_app.application.dto_commands import CommandResult

    return CommandResult(**kwargs)


def schedule_block_label(index: int, formatter: ScheduleLabelFormatter | None = None) -> str:
    if index >= 48:
        return "12:00 AM"
    if callable(formatter):
        try:
            return str(formatter(index))
        except Exception:
            pass
    hour = index // 2
    minute = 30 if index % 2 else 0
    return f"{hour:02d}:{minute:02d}"


def schedule_bool_values(raw_values: Iterable[Any]) -> list[bool]:
    return [bool(item) for item in list(raw_values)[:48]]


def schedule_grid_rows(grid: Mapping[str, Iterable[Any]]) -> dict[str, list[bool]]:
    return {str(day): schedule_bool_values(values) for day, values in grid.items()}


def schedule_day_windows(
    values: Iterable[Any],
    *,
    formatter: ScheduleLabelFormatter | None = None,
) -> list[str]:
    bool_values = schedule_bool_values(values)
    windows: list[str] = []
    start: int | None = None
    for index, allowed in enumerate([*bool_values, False]):
        if allowed and start is None:
            start = index
        elif not allowed and start is not None:
            end = index
            windows.append(
                "All day"
                if start == 0 and end >= 48
                else f"{schedule_block_label(start, formatter)} - {schedule_block_label(end, formatter)}"
            )
            start = None
    return windows


def schedule_day_summaries(
    grid: Mapping[str, Iterable[Any]],
    *,
    formatter: ScheduleLabelFormatter | None = None,
) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for day, raw_values in grid.items():
        values = schedule_bool_values(raw_values)
        allowed_blocks = sum(1 for item in values if item)
        windows = schedule_day_windows(values, formatter=formatter)
        summaries.append(
            {
                "day": str(day),
                "allowed_blocks": allowed_blocks,
                "allowed_hours": allowed_blocks / 2,
                "windows": windows,
                "windows_text": ", ".join(windows) if windows else "None",
            }
        )
    return summaries


def _schedule_day_lookup() -> dict[str, str]:
    lookup: dict[str, str] = {}
    for day in SCHEDULE_DAY_NAMES:
        lookup[day.casefold()] = day
        lookup[day[:3].casefold()] = day
    return lookup


def schedule_day_name(value: Any) -> str | None:
    return _schedule_day_lookup().get(str(value or "").strip().casefold())


def schedule_time_to_block(value: str, *, allow_day_end: bool = False) -> int:
    text = str(value or "").strip()
    if text == "24:00" and allow_day_end:
        return 48
    match = SCHEDULE_TIME_RE.match(text)
    if not match:
        raise ValueError(f"Unsupported time {text!r}; use HH:MM, HH:MM AM, or HH:MM PM.")
    hour = int(match.group("hour"))
    minute = int(match.group("minute") or "0")
    suffix = (match.group("suffix") or "").replace(".", "").lower()
    if minute not in (0, 30):
        raise ValueError(f"Unsupported time {text!r}; schedule windows must align to 30-minute blocks.")
    if suffix:
        if hour < 1 or hour > 12:
            raise ValueError(f"Unsupported time {text!r}; 12-hour times must use hours 1..12.")
        if suffix == "am":
            hour = 0 if hour == 12 else hour
        else:
            hour = 12 if hour == 12 else hour + 12
    elif hour < 0 or hour > 23:
        if hour == 24 and minute == 0 and allow_day_end:
            return 48
        raise ValueError(f"Unsupported time {text!r}; 24-hour times must use hours 0..23.")
    block = hour * 2 + (1 if minute == 30 else 0)
    if block == 48 and not allow_day_end:
        raise ValueError(f"Unsupported start time {text!r}; use 00:00 for midnight starts.")
    return block


def parse_schedule_day_windows(value: Any) -> tuple[list[bool], list[str]]:
    text = str(value or "").strip()
    if not text or text.casefold() in {"none", "off", "closed"}:
        return [False] * 48, []
    if text.casefold() in {"all", "all day", "*"}:
        return [True] * 48, []
    values = [False] * 48
    errors: list[str] = []
    parts = [part.strip() for part in re.split(r"[,;\n]+", text) if part.strip()]
    if not parts:
        return values, []
    for part in parts:
        if re.search(r"\s+to\s+", part, flags=re.IGNORECASE):
            start_text, end_text = re.split(r"\s+to\s+", part, maxsplit=1, flags=re.IGNORECASE)
        elif "-" in part:
            start_text, end_text = part.split("-", 1)
        else:
            errors.append(f"Window {part!r} is missing '-' or 'to'.")
            continue
        try:
            start = schedule_time_to_block(start_text, allow_day_end=False)
            end = schedule_time_to_block(end_text, allow_day_end=True)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        if end <= start:
            errors.append(f"Window {part!r} crosses midnight or is empty; split it across adjacent days.")
            continue
        for index in range(start, end):
            values[index] = True
    return values, errors


def schedule_grid_from_day_windows(raw_windows: Mapping[str, Any]) -> tuple[dict[str, list[bool]], list[str]]:
    grid = {day: [False] * 48 for day in SCHEDULE_DAY_NAMES}
    errors: list[str] = []
    seen_days: set[str] = set()
    for raw_day, raw_value in raw_windows.items():
        day = schedule_day_name(raw_day)
        if day is None:
            errors.append(f"Unknown schedule day {raw_day!r}.")
            continue
        seen_days.add(day)
        values, day_errors = parse_schedule_day_windows(raw_value)
        grid[day] = values
        errors.extend(f"{day}: {error}" for error in day_errors)
    for day in SCHEDULE_DAY_NAMES:
        if day not in seen_days:
            grid[day] = [False] * 48
    return grid, errors


def schedule_grid_from_request(
    request: Mapping[str, Any],
    *,
    normalizer: Callable[[Any], dict[str, list[bool]]] | None = None,
) -> tuple[dict[str, list[bool]], list[str], str]:
    if isinstance(request.get("day_windows"), Mapping):
        grid, errors = schedule_grid_from_day_windows(request["day_windows"])  # type: ignore[index]
        return grid, errors, "day_windows"
    if "grid" in request:
        if callable(normalizer):
            return normalizer(request.get("grid")), [], "grid"
        return schedule_grid_rows(request.get("grid") if isinstance(request.get("grid"), Mapping) else {}), [], "grid"
    return {day: [False] * 48 for day in SCHEDULE_DAY_NAMES}, ["Schedule request requires day_windows or grid."], "missing"


def schedule_grid_changed_days(left: Mapping[str, Iterable[Any]], right: Mapping[str, Iterable[Any]]) -> list[str]:
    left_grid = schedule_grid_rows(left)
    right_grid = schedule_grid_rows(right)
    changed: list[str] = []
    for day in SCHEDULE_DAY_NAMES:
        if left_grid.get(day, []) != right_grid.get(day, []):
            changed.append(day)
    return changed


def schedule_grid_allowed_blocks(grid: Mapping[str, Iterable[Any]]) -> int:
    return sum(1 for values in schedule_grid_rows(grid).values() for item in values if item)


def schedule_patch_warnings(*, enabled: bool, grid: Mapping[str, Iterable[Any]]) -> list[str]:
    warnings: list[str] = []
    total_blocks = schedule_grid_allowed_blocks(grid)
    if enabled and total_blocks == 0:
        warnings.append("Schedule enforcement is enabled with zero allowed windows; normal scheduled starts will be blocked.")
    if enabled and total_blocks == 7 * 48:
        warnings.append("Schedule enforcement is enabled but every block is allowed; this is effectively always-on.")
    for summary in schedule_day_summaries(grid):
        if int(summary["allowed_blocks"]) == 48:
            warnings.append(f"{summary['day']} is allowed all day.")
    return warnings


def schedule_command_severity(errors: list[str], warnings: list[str]) -> str:
    return "error" if errors else "warning" if warnings else "info"


def schedule_preview_result(
    *,
    enabled: bool,
    current_enabled: bool,
    grid: Mapping[str, Iterable[Any]],
    current_grid: Mapping[str, Iterable[Any]],
    source: str,
    errors: list[str],
    warnings: list[str],
    app_state_path: str,
    formatter: ScheduleLabelFormatter | None = None,
) -> "CommandResult":
    changed_days = schedule_grid_changed_days(current_grid, grid)
    changed_enabled = bool(enabled) != bool(current_enabled)
    return _command_result(
        command=SCHEDULE_PREVIEW_COMMAND,
        ok=not errors,
        message=(
            f"Schedule preview failed with {len(errors)} error(s)."
            if errors else
            f"Schedule preview has {len(changed_days) + (1 if changed_enabled else 0)} change area(s)."
        ),
        severity=schedule_command_severity(errors, warnings),
        errors=errors,
        warnings=warnings,
        refresh_hint=SCHEDULE_REFRESH_HINT,
        data={
            "schema_version": "desktop_schedule_patch_preview.v1",
            "source": source,
            "enabled": bool(enabled),
            "current_enabled": bool(current_enabled),
            "changed_enabled": changed_enabled,
            "changed_days": changed_days,
            "day_summaries": schedule_day_summaries(grid, formatter=formatter),
            "grid": schedule_grid_rows(grid),
            "current_grid": schedule_grid_rows(current_grid),
            "app_state_path": app_state_path,
            "writes_app_state": False,
        },
    )


def schedule_save_confirmation_required_result() -> "CommandResult":
    return _command_result(
        command=SCHEDULE_SAVE_COMMAND,
        ok=False,
        message="Schedule save requires explicit confirmation.",
        severity="warning",
        warnings=["confirm_save must be true."],
        refresh_hint=SCHEDULE_REFRESH_HINT,
    )


def schedule_save_busy_result(message: str) -> "CommandResult":
    return _command_result(
        command=SCHEDULE_SAVE_COMMAND,
        ok=False,
        message=message,
        severity="warning",
        warnings=[message],
        refresh_hint=SCHEDULE_REFRESH_HINT,
    )


def schedule_save_validation_error_result(errors: list[str], warnings: list[str]) -> "CommandResult":
    return _command_result(
        command=SCHEDULE_SAVE_COMMAND,
        ok=False,
        message=f"Schedule save failed validation with {len(errors)} error(s).",
        severity="error",
        errors=errors,
        warnings=warnings,
        refresh_hint=SCHEDULE_REFRESH_HINT,
    )


def schedule_save_no_changes_result(warnings: list[str]) -> "CommandResult":
    return _command_result(
        command=SCHEDULE_SAVE_COMMAND,
        ok=False,
        message="Schedule save has no changes to write.",
        severity="warning",
        warnings=warnings or ["No schedule changes were proposed."],
        refresh_hint=SCHEDULE_REFRESH_HINT,
    )


def schedule_save_service_unavailable_result() -> "CommandResult":
    return _command_result(
        command=SCHEDULE_SAVE_COMMAND,
        ok=False,
        message="Schedule app-state save service is not available.",
        severity="error",
        errors=["save_app_state is required."],
        refresh_hint=SCHEDULE_REFRESH_HINT,
    )


def schedule_save_exception_result(exc: Exception, warnings: list[str]) -> "CommandResult":
    return _command_result(
        command=SCHEDULE_SAVE_COMMAND,
        ok=False,
        message=f"Schedule save failed: {exc}",
        severity="error",
        errors=[str(exc)],
        warnings=warnings,
        refresh_hint=SCHEDULE_REFRESH_HINT,
    )


def schedule_save_success_result(
    *,
    enabled: bool,
    current_enabled: bool,
    grid: Mapping[str, Iterable[Any]],
    current_grid: Mapping[str, Iterable[Any]],
    source: str,
    warnings: list[str],
    app_state_path: str,
    formatter: ScheduleLabelFormatter | None = None,
) -> "CommandResult":
    changed_days = schedule_grid_changed_days(current_grid, grid)
    changed_enabled = bool(enabled) != bool(current_enabled)
    return _command_result(
        command=SCHEDULE_SAVE_COMMAND,
        ok=True,
        message="Schedule saved to app state.",
        severity="warning" if warnings else "info",
        warnings=warnings,
        refresh_hint=SCHEDULE_REFRESH_HINT,
        data={
            "schema_version": "desktop_schedule_save_result.v1",
            "source": source,
            "enabled": bool(enabled),
            "current_enabled": bool(current_enabled),
            "changed_enabled": changed_enabled,
            "changed_days": changed_days,
            "day_summaries": schedule_day_summaries(grid, formatter=formatter),
            "grid": schedule_grid_rows(grid),
            "app_state_path": app_state_path,
            "writes_app_state": True,
        },
    )

__all__ = [
    "SCHEDULE_PREVIEW_COMMAND",
    "SCHEDULE_SAVE_COMMAND",
    "SCHEDULE_REFRESH_HINT",
    "SCHEDULE_TIME_RE",
    "schedule_block_label",
    "schedule_bool_values",
    "schedule_grid_rows",
    "schedule_day_windows",
    "schedule_day_summaries",
    "schedule_day_name",
    "schedule_time_to_block",
    "parse_schedule_day_windows",
    "schedule_grid_from_day_windows",
    "schedule_grid_from_request",
    "schedule_grid_changed_days",
    "schedule_grid_allowed_blocks",
    "schedule_patch_warnings",
    "schedule_command_severity",
    "schedule_preview_result",
    "schedule_save_confirmation_required_result",
    "schedule_save_busy_result",
    "schedule_save_validation_error_result",
    "schedule_save_no_changes_result",
    "schedule_save_service_unavailable_result",
    "schedule_save_exception_result",
    "schedule_save_success_result",
]
