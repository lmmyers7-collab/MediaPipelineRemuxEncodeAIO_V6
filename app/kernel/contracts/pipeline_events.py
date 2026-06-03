from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from .base import ContractError, dict_field, require_mapping, require_schema_version, text_field


PIPELINE_EVENT_SCHEMA_VERSION = "pipeline_event.v1"


@dataclass(frozen=True)
class PipelineEvent:
    schema_version: str
    event_id: str
    event_type: str
    timestamp: str
    created_at: str
    run_id: str
    correlation_id: str
    job_id: str
    product_version: str
    pipeline_version: str
    stage: str
    route: str
    status: str
    source_path: str
    data: dict[str, Any] = field(default_factory=dict)
    raw: Mapping[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any] | Any) -> "PipelineEvent":
        data = require_mapping(payload, "pipeline event")
        schema_version = require_schema_version(data, PIPELINE_EVENT_SCHEMA_VERSION)
        event_type = text_field(data, "event_type").strip()
        if not event_type:
            raise ContractError("event_type is required")
        event_id = text_field(data, "event_id").strip()
        if not event_id:
            raise ContractError("event_id is required")
        timestamp = text_field(data, "timestamp").strip() or text_field(data, "created_at").strip()
        if not timestamp:
            raise ContractError("timestamp or created_at is required")
        created_at = text_field(data, "created_at").strip() or timestamp
        return cls(
            schema_version=schema_version,
            event_id=event_id,
            event_type=event_type,
            timestamp=timestamp,
            created_at=created_at,
            run_id=text_field(data, "run_id"),
            correlation_id=text_field(data, "correlation_id"),
            job_id=text_field(data, "job_id"),
            product_version=text_field(data, "product_version"),
            pipeline_version=text_field(data, "pipeline_version"),
            stage=text_field(data, "stage"),
            route=text_field(data, "route"),
            status=text_field(data, "status"),
            source_path=text_field(data, "source_path"),
            data=dict_field(data, "data"),
            raw=data,
        )

    def to_mapping(self) -> dict[str, Any]:
        return {
            **dict(self.raw),
            "schema_version": self.schema_version,
            "event_id": self.event_id,
            "event_type": self.event_type,
            "timestamp": self.timestamp,
            "created_at": self.created_at,
            "run_id": self.run_id,
            "correlation_id": self.correlation_id,
            "job_id": self.job_id,
            "product_version": self.product_version,
            "pipeline_version": self.pipeline_version,
            "stage": self.stage,
            "route": self.route,
            "status": self.status,
            "source_path": self.source_path,
            "data": dict(self.data),
        }
