"""Shared stage contract base models."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

STAGE_SCHEMA_VERSION: Literal["v1"] = "v1"

MutationIntent = Literal["dry_run", "execute"]

class StageName(StrEnum):
    """Canonical stage names accepted by the Python dispatcher and PowerShell compatibility entrypoint."""

    ingest = "ingest"
    probe = "probe"
    decide = "decide"
    transcode = "transcode"
    subtitle_convert = "subtitle-convert"
    audio_mix = "audio-mix"
    publish = "publish"
    drain = "drain"
    rename = "rename"

class StageContractModel(BaseModel):
    """Strict base for JSON-wire stage models."""

    model_config = ConfigDict(extra="forbid")

class StagePayload(StageContractModel):
    """Base request payload fields shared by every stage."""

    run_id: str = ""
    job_id: str = ""

class StageData(StageContractModel):
    """Base stage data model returned inside StageResult.data."""

class StageError(StageContractModel):
    """Structured error returned when a stage fails."""

    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    details: dict[str, Any] = Field(default_factory=dict)

class StreamSummary(StageContractModel):
    index: int = Field(ge=0)
    kind: Literal["video", "audio", "subtitle", "data", "attachment"]
    codec: str = ""
    language: str = ""
    bitrate_bps: int = Field(default=0, ge=0)
    width: int = Field(default=0, ge=0)
    height: int = Field(default=0, ge=0)
    channels: int = Field(default=0, ge=0)
    title: str = ""
    default: bool = False
    forced: bool = False
