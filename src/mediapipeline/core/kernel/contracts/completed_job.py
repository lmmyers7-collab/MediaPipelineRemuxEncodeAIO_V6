from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from .base import require_mapping, require_schema_version, text_field


COMPLETED_JOB_SCHEMA_VERSIONS = {"completed_job.v1", "pipeline_sidecar.v1"}


@dataclass(frozen=True)
class CompletedJob:
    schema_version: str
    product_version: str
    pipeline_version: str
    created_at: str
    encoded_at: str
    logged_at: str
    job_id: str
    correlation_id: str
    route: str
    output_file: str
    output_path: str
    source_path: str
    source_identity_v2: str
    raw: Mapping[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any] | Any) -> CompletedJob:
        data = require_mapping(payload, "completed job")
        schema_version = require_schema_version(data, COMPLETED_JOB_SCHEMA_VERSIONS)
        return cls(
            schema_version=schema_version,
            product_version=text_field(data, "product_version"),
            pipeline_version=text_field(data, "pipeline_version"),
            created_at=text_field(data, "created_at"),
            encoded_at=text_field(data, "encoded_at"),
            logged_at=text_field(data, "logged_at"),
            job_id=text_field(data, "job_id"),
            correlation_id=text_field(data, "correlation_id"),
            route=text_field(data, "route"),
            output_file=text_field(data, "output_file"),
            output_path=text_field(data, "output_path"),
            source_path=text_field(data, "source_path"),
            source_identity_v2=text_field(data, "source_identity_v2"),
            raw=data,
        )
