from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from app.schedule.file_io import atomic_write_text, read_json_file
from app.schedule.grid import (
    block_label as schedule_block_label,
    default_schedule_grid as default_schedule_grid_helper,
    evaluate_schedule as evaluate_schedule_helper,
    format_schedule_datetime as format_schedule_datetime_helper,
    next_scheduled_stop as next_scheduled_stop_helper,
    normalize_schedule_grid as normalize_schedule_grid_helper,
)


class AppStateScheduleServiceMixin:
    def default_schedule_grid(self) -> dict[str, list[bool]]:
        return default_schedule_grid_helper()

    def normalize_schedule_grid(self, raw: Any) -> dict[str, list[bool]]:
        return normalize_schedule_grid_helper(raw)

    # Keys that receive structured normalisation in load/save.
    _APP_STATE_STRUCTURED_KEYS = frozenset({
        "schema_version", "created_at",
        "schedule_enabled", "schedule_grid",
        "queue_quick_view", "audit_quick_view",
    })

    def load_app_state(self) -> dict[str, Any]:
        default_state: dict[str, Any] = {
            "schedule_enabled": False,
            "schedule_grid": self.default_schedule_grid(),
            "queue_quick_view": "All Items",
            "audit_quick_view": "All Audit Items",
        }
        if not self.app_state_path.exists():
            return default_state
        try:
            raw = read_json_file(self.app_state_path) or {}
        except Exception as exc:
            self.logger.warning("App state load failed: %s", exc)
            return default_state

        state: dict[str, Any] = {
            "schedule_enabled": bool(raw.get("schedule_enabled", False)),
            "schedule_grid": self.normalize_schedule_grid(raw.get("schedule_grid")),
            "queue_quick_view": str(raw.get("queue_quick_view", "All Items") or "All Items"),
            "audit_quick_view": str(raw.get("audit_quick_view", "All Audit Items") or "All Audit Items"),
        }
        # Pass through any extra keys the app layer stored (e.g. machine_id,
        # coordinator_auth_token, tree_col_widths).
        for key, value in raw.items():
            if key not in self._APP_STATE_STRUCTURED_KEYS:
                state.setdefault(key, value)
        return state

    def save_app_state(self, state: dict[str, Any]) -> None:
        # Load-merge: read whatever is currently on disk first, so that callers
        # passing partial state (e.g. persist_view_state passing only schedule
        # + quick-view keys) don't clobber unrelated keys like machine_id,
        # coordinator_auth_token, or tree_col_widths.
        existing: dict[str, Any] = {}
        if self.app_state_path.exists():
            try:
                existing = read_json_file(self.app_state_path) or {}
            except Exception as exc:
                self.logger.warning("App state load-merge failed: %s", exc)
                existing = {}

        # Merge: new state wins over existing values for the same key,
        # but unrelated keys in the existing file are preserved.
        merged: dict[str, Any] = dict(existing)
        for key, value in state.items():
            merged[key] = value

        # Start with structured/normalised keys (always rewritten fresh).
        payload: dict[str, Any] = {
            "schema_version": "desktop_app_state.v1",
            "created_at": datetime.now().isoformat(),
            "schedule_enabled": bool(merged.get("schedule_enabled", False)),
            "schedule_grid": self.normalize_schedule_grid(merged.get("schedule_grid")),
            "queue_quick_view": str(merged.get("queue_quick_view", "All Items") or "All Items"),
            "audit_quick_view": str(merged.get("audit_quick_view", "All Audit Items") or "All Audit Items"),
        }
        # Carry every other merged key forward (machine_id, auth tokens, UI prefs).
        # Structured keys above always win; never overwrite schema_version / created_at.
        for key, value in merged.items():
            if key not in payload:
                payload[key] = value
        atomic_write_text(self.app_state_path, json.dumps(payload, indent=2))

    def block_label(self, index: int) -> str:
        return schedule_block_label(index)

    def format_schedule_datetime(self, value: datetime | None) -> str:
        return format_schedule_datetime_helper(value)

    def evaluate_schedule(
        self,
        schedule_enabled: bool,
        schedule_grid: dict[str, list[bool]],
        now: datetime | None = None,
    ) -> dict[str, Any]:
        return evaluate_schedule_helper(schedule_enabled, schedule_grid, now=now)

    def next_scheduled_stop(
        self,
        schedule_enabled: bool,
        schedule_grid: dict[str, list[bool]],
        now: datetime | None = None,
    ) -> datetime | None:
        return next_scheduled_stop_helper(schedule_enabled, schedule_grid, now=now)
