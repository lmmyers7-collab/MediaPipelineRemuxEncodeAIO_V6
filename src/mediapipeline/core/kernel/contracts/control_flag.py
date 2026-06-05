from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from .base import ContractError, int_field, require_mapping, require_schema_version, text_field


CONTROL_FLAG_SCHEMA_VERSION = "pipeline_control_flag.v1"
CONTROL_FLAG_ACTIONS = frozenset({"pause", "stop", "rescan"})


def _nullable_nonnegative_int_field(payload: Mapping[str, Any], key: str) -> int | None:
    value = payload.get(key)
    if value is None or value == "":
        return None
    result = int_field(payload, key)
    if result < 0:
        raise ContractError(f"{key} must be greater than or equal to 0")
    return result


@dataclass(frozen=True)
class ControlFlagRecord:
    schema_version: str
    action: str
    label: str
    request_id: str
    created_at: str
    app_pid: int | None = None
    raw: Mapping[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any] | Any) -> "ControlFlagRecord":
        data = require_mapping(payload, "control flag")
        schema_version = require_schema_version(data, CONTROL_FLAG_SCHEMA_VERSION)
        action = text_field(data, "action").strip().casefold()
        if action not in CONTROL_FLAG_ACTIONS:
            allowed = ", ".join(sorted(CONTROL_FLAG_ACTIONS))
            raise ContractError(f"action must be one of {allowed}; got {action or '<missing>'}")
        label = text_field(data, "label").strip()
        if not label:
            raise ContractError("label is required")
        request_id = text_field(data, "request_id").strip()
        if not request_id:
            raise ContractError("request_id is required")
        created_at = text_field(data, "created_at").strip()
        if not created_at:
            raise ContractError("created_at is required")
        return cls(
            schema_version=schema_version,
            action=action,
            label=label,
            request_id=request_id,
            created_at=created_at,
            app_pid=_nullable_nonnegative_int_field(data, "app_pid"),
            raw=data,
        )

    def to_mapping(self) -> dict[str, Any]:
        return {
            **dict(self.raw),
            "schema_version": self.schema_version,
            "action": self.action,
            "label": self.label,
            "request_id": self.request_id,
            "created_at": self.created_at,
            "app_pid": self.app_pid,
        }
