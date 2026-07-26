from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from .base import bool_field, int_field, list_field, require_mapping, require_schema_version, text_field


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
    published_path: str
    parked_path: str
    intended_final_path: str
    manifest_path: str
    pipeline_sidecar_path: str
    sidecar_paths: list[str]
    publish_transaction_id: str
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
            published_path=text_field(data, "PublishedPath"),
            parked_path=text_field(data, "ParkedPath"),
            intended_final_path=text_field(data, "IntendedFinalPath"),
            manifest_path=text_field(data, "ManifestPath"),
            pipeline_sidecar_path=text_field(data, "PipelineSidecarPath"),
            sidecar_paths=[str(item) for item in list_field(data, "SidecarPaths")],
            publish_transaction_id=text_field(data, "PublishTransactionId"),
            raw=data,
        )
