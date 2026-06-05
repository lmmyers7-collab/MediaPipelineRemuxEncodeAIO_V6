from __future__ import annotations

from dataclasses import dataclass, field

from .dto_base import JsonMap, dto_mapping


@dataclass(frozen=True)
class CommandResult:
    command: str
    ok: bool
    message: str
    severity: str = "info"
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    job_id: str = ""
    refresh_hint: str = ""
    log_paths: dict[str, str] = field(default_factory=dict)
    data: JsonMap = field(default_factory=dict)
    schema_version: str = "desktop_command_result.v1"

    def to_mapping(self) -> JsonMap:
        return dto_mapping(self)

__all__ = [
    "CommandResult",
]
