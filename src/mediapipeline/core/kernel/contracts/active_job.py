from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from .base import ContractError, bool_field, dict_field, list_field, require_mapping, require_schema_version, text_field


ACTIVE_JOB_SCHEMA_VERSION = "desktop_active_job.v1"
ACTIVE_JOB_STATUSES = frozenset(
    {
        "launching",
        "active",
        "completed",
        "failed",
        "completed_immediate",
        "failed_immediate",
        "killed",
        "orphaned",
    }
)


def _nullable_int_field(payload: Mapping[str, Any], key: str) -> int | None:
    value = payload.get(key)
    if value is None or value == "":
        return None
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise ContractError(f"{key} must be an integer or null") from exc
    return result


def _nullable_nonnegative_int_field(payload: Mapping[str, Any], key: str) -> int | None:
    value = _nullable_int_field(payload, key)
    if value is not None and value < 0:
        raise ContractError(f"{key} must be greater than or equal to 0")
    return value


def _string_list_field(payload: Mapping[str, Any], key: str) -> list[str]:
    return [str(item) for item in list_field(payload, key)]


@dataclass(frozen=True)
class ActiveJobRecord:
    schema_version: str
    launch_id: str
    job_kind: str
    status: str
    mode: str = ""
    pid: int | None = None
    app_pid: int | None = None
    command_line: str = ""
    args: list[str] = field(default_factory=list)
    cwd: str = ""
    stdout_log: str = ""
    stderr_log: str = ""
    show_console: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)
    launched_at: str = ""
    last_update: str = ""
    completed_at: str = ""
    return_code: int | None = None
    raw: Mapping[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any] | Any) -> ActiveJobRecord:
        data = require_mapping(payload, "active job record")
        schema_version = require_schema_version(data, ACTIVE_JOB_SCHEMA_VERSION)
        launch_id = text_field(data, "launch_id").strip()
        if not launch_id:
            raise ContractError("launch_id is required")
        job_kind = text_field(data, "job_kind", "job").strip()
        if not job_kind:
            raise ContractError("job_kind is required")
        status = text_field(data, "status").strip()
        if not status:
            raise ContractError("status is required")
        if status not in ACTIVE_JOB_STATUSES:
            allowed = ", ".join(sorted(ACTIVE_JOB_STATUSES))
            raise ContractError(f"status must be one of {allowed}; got {status}")
        return cls(
            schema_version=schema_version,
            launch_id=launch_id,
            job_kind=job_kind,
            status=status,
            mode=text_field(data, "mode").strip(),
            pid=_nullable_nonnegative_int_field(data, "pid"),
            app_pid=_nullable_nonnegative_int_field(data, "app_pid"),
            command_line=text_field(data, "command_line"),
            args=_string_list_field(data, "args"),
            cwd=text_field(data, "cwd"),
            stdout_log=text_field(data, "stdout_log"),
            stderr_log=text_field(data, "stderr_log"),
            show_console=bool_field(data, "show_console"),
            metadata=dict_field(data, "metadata"),
            launched_at=text_field(data, "launched_at").strip(),
            last_update=text_field(data, "last_update").strip(),
            completed_at=text_field(data, "completed_at").strip(),
            return_code=_nullable_int_field(data, "return_code"),
            raw=data,
        )

    def to_mapping(self) -> dict[str, Any]:
        return {
            **dict(self.raw),
            "schema_version": self.schema_version,
            "launch_id": self.launch_id,
            "job_kind": self.job_kind,
            "mode": self.mode,
            "status": self.status,
            "pid": self.pid,
            "app_pid": self.app_pid,
            "command_line": self.command_line,
            "args": list(self.args),
            "cwd": self.cwd,
            "stdout_log": self.stdout_log,
            "stderr_log": self.stderr_log,
            "show_console": self.show_console,
            "metadata": dict(self.metadata),
            "launched_at": self.launched_at,
            "last_update": self.last_update,
            "completed_at": self.completed_at,
            "return_code": self.return_code,
        }
