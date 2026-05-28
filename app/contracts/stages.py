"""Canonical pipeline stage I/O contracts.

Defines the seven canonical stages of the media pipeline and the input
and output shape for each. ADR-0002 establishes that Python (`app/`)
orchestrates and PowerShell (`engine/entrypoint.ps1 <stage> <payload>`)
executes; this file is the wire contract between the two.

Today these are stdlib dataclasses. ADR-0004 will swap to pydantic so
JSON Schema generation and runtime validation become automatic, at which
point `schemas/<stage>.v1.schema.json` is generated from this file in CI.

Stage payloads carry an explicit `schema_version` string. The engine
rejects unknown versions. Breaking changes bump the version and ship a
new payload class alongside the old one; the orchestrator continues to
emit the version it understands.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal

STAGE_SCHEMA_VERSION = "v1"


class StageName(str, Enum):
    """Canonical stage names. The engine dispatches on these values."""

    ingest = "ingest"
    probe = "probe"
    decide = "decide"
    transcode = "transcode"
    subtitle_convert = "subtitle-convert"
    audio_mix = "audio-mix"
    publish = "publish"
    drain = "drain"
    rename = "rename"


# ----------------------------------------------------------------------
# Shared shapes
# ----------------------------------------------------------------------


@dataclass
class StagePayload:
    """Base payload. Every stage carries the orchestrator-assigned run id
    and an explicit schema version."""

    schema_version: Literal["v1"] = STAGE_SCHEMA_VERSION
    run_id: str = ""
    job_id: str = ""


@dataclass
class StageResult:
    """Base result. Stages always return success/failure plus a stable
    machine-readable code so the orchestrator can branch without parsing
    error strings."""

    schema_version: Literal["v1"] = STAGE_SCHEMA_VERSION
    ok: bool = False
    code: str = ""  # e.g. 'ok', 'remux.size_guard_strict_violation'
    message: str = ""
    duration_ms: int = 0


# ----------------------------------------------------------------------
# Stage-specific payloads
# ----------------------------------------------------------------------


@dataclass
class IngestPayload(StagePayload):
    source_path: str = ""
    scratch_root: str = ""


@dataclass
class IngestResult(StageResult):
    scratch_path: str = ""
    size_bytes: int = 0
    sha256: str = ""


@dataclass
class ProbePayload(StagePayload):
    scratch_path: str = ""


@dataclass
class StreamSummary:
    index: int = 0
    kind: Literal["video", "audio", "subtitle", "data", "attachment"] = "video"
    codec: str = ""
    language: str = ""
    bitrate_bps: int = 0
    width: int = 0
    height: int = 0
    channels: int = 0
    title: str = ""
    default: bool = False
    forced: bool = False


@dataclass
class ProbeResult(StageResult):
    container: str = ""
    duration_s: float = 0.0
    bitrate_bps: int = 0
    streams: list[StreamSummary] = field(default_factory=list)


@dataclass
class DecidePayload(StagePayload):
    probe: ProbeResult = field(default_factory=ProbeResult)
    is_tv: bool = False
    # Slice of resolved Config the engine needs. Sent as flat dict on the
    # wire; typed here for readability.
    routing_profile: str = "plex_direct_stream"
    encode_threshold_gb: float = 8
    tv_encode_threshold_gb: float = 3
    allow_h264_remux_if_plex_compatible: bool = True
    h264_remux_max_bitrate_mbps: int = 35
    h264_remux_max_height: int = 1080
    remux_safe_video_codecs: list[str] = field(default_factory=list)


@dataclass
class DecideResult(StageResult):
    route: Literal["remux", "encode", "skip"] = "remux"
    reason_code: str = ""
    encoder_profile: str = ""  # e.g. 'hevc_nvenc_p7_q22'


@dataclass
class TranscodePayload(StagePayload):
    scratch_path: str = ""
    output_path: str = ""
    decision: DecideResult = field(default_factory=DecideResult)
    video_codec: str = "hevc_nvenc"
    video_preset: str = "p7"
    video_quality: int = 22
    output_container: Literal["mkv", "mp4"] = "mkv"
    extra_video_flags: list[str] = field(default_factory=list)
    timeout_seconds: int = 21600


@dataclass
class TranscodeAttempt:
    attempt_no: int = 1
    encoder: str = ""
    started_at: str = ""
    ended_at: str = ""
    exit_code: int = 0
    log_path: str = ""


@dataclass
class TranscodeResult(StageResult):
    output_path: str = ""
    output_size_bytes: int = 0
    attempts: list[TranscodeAttempt] = field(default_factory=list)


@dataclass
class SubtitleConvertPayload(StagePayload):
    scratch_path: str = ""
    output_path: str = ""
    keep_languages: list[str] = field(default_factory=list)
    convert_tx3g_to_srt: bool = True
    convert_bdpgs_to_srt: bool = False
    bdpgs_ocr_tool_path: str = ""
    bdpgs_ocr_tessdata_path: str = ""


@dataclass
class SubtitleConvertResult(StageResult):
    tracks_kept: int = 0
    tracks_converted: int = 0
    sidecars_written: list[str] = field(default_factory=list)
    review_required: bool = False
    review_reason: str = ""


@dataclass
class AudioMixPayload(StagePayload):
    scratch_path: str = ""
    output_path: str = ""
    passthrough_profile: str = "plex_balanced"
    compatible_audio_codecs: list[str] = field(default_factory=list)
    preferred_default_languages: list[str] = field(default_factory=list)


@dataclass
class AudioMixResult(StageResult):
    tracks_passed_through: int = 0
    tracks_transcoded: int = 0
    tracks_downmixed: int = 0
    default_track_language: str = ""


@dataclass
class PublishPayload(StagePayload):
    output_path: str = ""
    final_root: str = ""
    is_tv: bool = False
    create_tv_subfolder: bool = True
    deferred_publish: bool = False
    robocopy_flags: list[str] = field(default_factory=list)
    min_free_space_gb: int = 50


@dataclass
class PublishResult(StageResult):
    final_path: str = ""
    parked: bool = False  # True when deferred_publish or final root unsafe
    pending_publish_id: str = ""
    manifest_path: str = ""


@dataclass
class DrainPayload(StagePayload):
    pending_publish_id: str = ""
    final_root: str = ""
    allow_overwrite: bool = False
    parallelism: int = 1


@dataclass
class DrainResult(StageResult):
    moved: int = 0
    skipped: int = 0
    failed: int = 0
    manifest_path: str = ""


@dataclass
class RenamePayload(StagePayload):
    target_path: str = ""
    proposed_name: str = ""
    aggressive_episode_parsing: bool = False
    is_tv: bool = False


@dataclass
class RenameResult(StageResult):
    final_path: str = ""
    sidecars_renamed: list[str] = field(default_factory=list)
    undo_record_path: str = ""


# ----------------------------------------------------------------------
# Stage registry: (payload_cls, result_cls) per stage.
# ----------------------------------------------------------------------


STAGE_REGISTRY: dict[StageName, tuple[type, type]] = {
    StageName.ingest: (IngestPayload, IngestResult),
    StageName.probe: (ProbePayload, ProbeResult),
    StageName.decide: (DecidePayload, DecideResult),
    StageName.transcode: (TranscodePayload, TranscodeResult),
    StageName.subtitle_convert: (SubtitleConvertPayload, SubtitleConvertResult),
    StageName.audio_mix: (AudioMixPayload, AudioMixResult),
    StageName.publish: (PublishPayload, PublishResult),
    StageName.drain: (DrainPayload, DrainResult),
    StageName.rename: (RenamePayload, RenameResult),
}


__all__ = [
    "STAGE_SCHEMA_VERSION",
    "StageName",
    "StagePayload",
    "StageResult",
    "IngestPayload", "IngestResult",
    "ProbePayload", "ProbeResult", "StreamSummary",
    "DecidePayload", "DecideResult",
    "TranscodePayload", "TranscodeResult", "TranscodeAttempt",
    "SubtitleConvertPayload", "SubtitleConvertResult",
    "AudioMixPayload", "AudioMixResult",
    "PublishPayload", "PublishResult",
    "DrainPayload", "DrainResult",
    "RenamePayload", "RenameResult",
    "STAGE_REGISTRY",
]
