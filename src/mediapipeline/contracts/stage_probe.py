"""Probe-stage request and result models."""

from __future__ import annotations

from pydantic import Field

from .stage_base import StageData, StagePayload, StreamSummary

class ProbePayload(StagePayload):
    scratch_path: str = Field(min_length=1)

class ProbeResult(StageData):
    probe_ok: bool = False
    probe_error: str = ""
    tool_path: str = ""
    container: str = ""
    duration_seconds: float = Field(default=0.0, ge=0)
    bitrate_bps: int = Field(default=0, ge=0)
    video_codec: str = "unknown"
    width: int = Field(default=0, ge=0)
    height: int = Field(default=0, ge=0)
    is_hdr: bool = False
    color_transfer: str = ""
    container_bitrate_mbps: float = Field(default=0.0, ge=0)
    estimated_bitrate_mbps: float = Field(default=0.0, ge=0)
    size_bytes: int = Field(default=0, ge=0)
    streams: list[StreamSummary] = Field(default_factory=list)
