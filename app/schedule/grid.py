from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from app.shared.constants import SCHEDULE_DAY_NAMES


def default_schedule_grid() -> dict[str, list[bool]]:
    return {day: [False] * 48 for day in SCHEDULE_DAY_NAMES}


def normalize_schedule_grid(raw: Any) -> dict[str, list[bool]]:
    normalized = default_schedule_grid()
    if not isinstance(raw, dict):
        return normalized

    lower_lookup = {str(key).casefold(): value for key, value in raw.items()}
    for day in SCHEDULE_DAY_NAMES:
        values = lower_lookup.get(day.casefold())
        if not isinstance(values, list):
            continue
        cleaned = [bool(item) for item in values[:48]]
        if len(cleaned) < 48:
            cleaned.extend([False] * (48 - len(cleaned)))
        normalized[day] = cleaned
    return normalized


def block_label(index: int) -> str:
    hour = index // 2
    minute = 30 if index % 2 else 0
    suffix = "AM" if hour < 12 else "PM"
    display_hour = hour % 12
    if display_hour == 0:
        display_hour = 12
    return f"{display_hour}:{minute:02d} {suffix}"


def format_schedule_datetime(value: datetime | None) -> str:
    if value is None:
        return ""
    day = SCHEDULE_DAY_NAMES[value.weekday()]
    hour = value.strftime("%I").lstrip("0") or "12"
    return f"{day} {hour}:{value.strftime('%M')} {value.strftime('%p')}"


def evaluate_schedule(
    schedule_enabled: bool,
    schedule_grid: dict[str, list[bool]],
    now: datetime | None = None,
) -> dict[str, Any]:
    if now is None:
        now = datetime.now()
    grid = normalize_schedule_grid(schedule_grid)
    block_start = now.replace(minute=30 if now.minute >= 30 else 0, second=0, microsecond=0)
    current_day_index = now.weekday()
    current_block_index = now.hour * 2 + (1 if now.minute >= 30 else 0)

    if not schedule_enabled:
        return {
            "enabled": False,
            "allowed_now": True,
            "current_window_end": None,
            "next_allowed_start": None,
            "next_allowed_end": None,
            "next_transition": None,
            "status_text": "Schedule: Off",
        }

    def block_value(offset: int) -> bool:
        absolute = current_day_index * 48 + current_block_index + offset
        day_index = (absolute // 48) % 7
        block_index = absolute % 48
        return grid[SCHEDULE_DAY_NAMES[day_index]][block_index]

    def block_start_at(offset: int) -> datetime:
        return block_start + timedelta(minutes=30 * offset)

    allowed_now = block_value(0)
    next_transition = None
    for offset in range(1, 7 * 48 + 1):
        if block_value(offset) != allowed_now:
            next_transition = block_start_at(offset)
            break

    current_window_end = next_transition if allowed_now else None
    next_allowed_start = None
    next_allowed_end = None

    if allowed_now:
        next_allowed_start = block_start
        next_allowed_end = current_window_end
    else:
        first_allowed_offset = None
        for offset in range(1, 7 * 48 + 1):
            if block_value(offset):
                first_allowed_offset = offset
                next_allowed_start = block_start_at(offset)
                break
        if first_allowed_offset is not None:
            for offset in range(first_allowed_offset + 1, 7 * 48 + 1):
                if not block_value(offset):
                    next_allowed_end = block_start_at(offset)
                    break

    if allowed_now:
        if current_window_end:
            status_text = f"Schedule: Allowed now until {format_schedule_datetime(current_window_end)}"
        else:
            status_text = "Schedule: Allowed now"
    else:
        if next_allowed_start:
            status_text = f"Schedule: Waiting | next allowed {format_schedule_datetime(next_allowed_start)}"
        else:
            status_text = "Schedule: Waiting | no allowed window scheduled"

    return {
        "enabled": True,
        "allowed_now": allowed_now,
        "current_window_end": current_window_end,
        "next_allowed_start": next_allowed_start,
        "next_allowed_end": next_allowed_end,
        "next_transition": next_transition,
        "status_text": status_text,
    }


def next_scheduled_stop(
    schedule_enabled: bool,
    schedule_grid: dict[str, list[bool]],
    now: datetime | None = None,
) -> datetime | None:
    evaluation = evaluate_schedule(schedule_enabled, schedule_grid, now=now)
    if not evaluation.get("enabled"):
        return None
    if evaluation.get("allowed_now"):
        return evaluation.get("current_window_end")
    return evaluation.get("next_allowed_end")
