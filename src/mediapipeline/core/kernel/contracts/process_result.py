from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from .base import bool_field, int_field, require_mapping, require_schema_version, text_field


PROCESS_FILE_RESULT_SCHEMA_VERSION = "process_file_result.v1"


@dataclass(frozen=True)
class ProcessFileResult:
    schema_version: str
    success: bool
    status: str
    queue_terminal: bool
    retryable: bool
    reason: str
    error_code: str
    source_path: str
    source_name: str
    route: str
    route_reason_code: str
    route_reason: str
    publish_state: str
    publish_mode: str
    output_path: str
    output_size_bytes: int
    raw: Mapping[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any] | Any) -> ProcessFileResult:
        data = require_mapping(payload, "process file result")
        schema_version = require_schema_version(data, PROCESS_FILE_RESULT_SCHEMA_VERSION, key="SchemaVersion")
        return cls(
            schema_version=schema_version,
            success=bool_field(data, "Success"),
            status=text_field(data, "Status"),
            queue_terminal=bool_field(data, "QueueTerminal"),
            retryable=bool_field(data, "Retryable", default=True),
            reason=text_field(data, "Reason"),
            error_code=text_field(data, "ErrorCode"),
            source_path=text_field(data, "SourcePath"),
            source_name=text_field(data, "SourceName"),
            route=text_field(data, "Route"),
            route_reason_code=text_field(data, "RouteReasonCode"),
            route_reason=text_field(data, "RouteReason"),
            publish_state=text_field(data, "PublishState"),
            publish_mode=text_field(data, "PublishMode"),
            output_path=text_field(data, "OutputPath"),
            output_size_bytes=int_field(data, "OutputSizeBytes"),
            raw=data,
        )
