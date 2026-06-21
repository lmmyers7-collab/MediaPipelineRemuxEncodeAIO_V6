"""Data-driven encoder and filter capability validation for presets."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field, field_validator

from mediapipeline.core.config.preset_policy import FiltersPolicy, PresetV2, PresetValidationIssue

_ENCODER_BACKEND_ALIASES_BY_NAME: dict[str, tuple[str, ...]] = {
    "libx264": ("x264",),
    "libx265": ("x265",),
    "libaom-av1": ("libaom",),
    "libsvtav1": ("svt_av1", "svtav1"),
}

_ENCODER_CODECS_BY_NAME: dict[str, str] = {
    "h264_nvenc": "h264",
    "h264_qsv": "h264",
    "libx264": "h264",
    "hevc_nvenc": "hevc",
    "hevc_qsv": "hevc",
    "hevc_amf": "hevc",
    "libx265": "hevc",
    "av1_nvenc": "av1",
    "av1_qsv": "av1",
    "av1_amf": "av1",
    "libaom-av1": "av1",
    "libsvtav1": "av1",
}


def _normalized_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip().lower()


def _normalized_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = _normalized_text(value)
        return [text] if text else []
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [text for item in value if (text := _normalized_text(item))]
    text = _normalized_text(value)
    return [text] if text else []


class EncodingCapabilityFacts(BaseModel):
    """Encoder/filter support as reported by the execution layer.

    PowerShell and FFmpeg remain the authority for actual executable support.
    This model lets Python validate a requested preset against supplied facts
    without probing tools or duplicating command-generation logic.
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    supported_video_codecs: list[str] = Field(default_factory=lambda: ["h264", "h265", "hevc"])
    supported_encoder_backends: list[str] = Field(default_factory=lambda: ["nvenc", "x264", "x265", "copy"])
    supported_video_filters: list[str] = Field(
        default_factory=lambda: ["detelecine", "deinterlace", "decomb", "yadif"]
    )
    supported_audio_transcode_codecs: list[str] = Field(default_factory=lambda: ["eac3", "ac3", "aac"])
    supported_subtitle_converters: list[str] = Field(default_factory=lambda: ["tx3g_srt", "ass_srt"])
    supported_containers: list[str] = Field(default_factory=lambda: ["mkv", "mp4"])

    @field_validator(
        "supported_video_codecs",
        "supported_encoder_backends",
        "supported_video_filters",
        "supported_audio_transcode_codecs",
        "supported_subtitle_converters",
        "supported_containers",
        mode="before",
    )
    @classmethod
    def _coerce_capability_list(cls, value: Any) -> list[str]:
        return _normalized_list(value)


def active_video_filter_names(filters: FiltersPolicy) -> list[str]:
    """Return video filters that force a video encode when enabled."""

    names: list[str] = []
    if filters.detelecine != "off":
        names.append("detelecine")
    if filters.deinterlace != "off":
        names.append("deinterlace" if filters.deinterlace == "auto" else filters.deinterlace)
    for name in ("denoise", "sharpen", "deblock"):
        if getattr(filters, name) != "off":
            names.append(name)
    if filters.chroma_smooth != "off":
        names.append("chroma_smooth")
    if filters.colorspace != "source":
        names.append("colorspace")
    return names


def encoding_capability_facts_from_encoder_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    available_only: bool = True,
) -> EncodingCapabilityFacts:
    """Build video capability facts from descriptor capability report rows."""

    codecs: set[str] = set()
    backends: set[str] = {"copy"}
    for row in rows:
        if available_only and not _row_is_available(row):
            continue
        codec = _encoder_row_codec(row)
        if codec:
            codecs.add(codec)
            if codec == "hevc":
                codecs.add("h265")
        for backend in _encoder_row_backends(row):
            backends.add(backend)
    return EncodingCapabilityFacts(
        supported_video_codecs=sorted(codecs),
        supported_encoder_backends=sorted(backends),
    )


def _row_is_available(row: Mapping[str, Any]) -> bool:
    value = row.get("available")
    if isinstance(value, bool):
        return value
    return _normalized_text(value) in {"1", "true", "yes", "available", "ok", "ready"}


def _encoder_row_codec(row: Mapping[str, Any]) -> str:
    family = _normalized_text(row.get("family"))
    if family in {"h264", "h265", "hevc", "av1", "copy"}:
        return "hevc" if family == "h265" else family
    return _ENCODER_CODECS_BY_NAME.get(_normalized_text(row.get("encoder_name")), "")


def _encoder_row_backends(row: Mapping[str, Any]) -> list[str]:
    backends: set[str] = set()
    backend = _normalized_text(row.get("backend"))
    if backend:
        backends.add(backend)
    name = _normalized_text(row.get("encoder_name"))
    if name.endswith("_nvenc"):
        backends.add("nvenc")
    elif name.endswith("_qsv"):
        backends.add("qsv")
    elif name.endswith("_amf"):
        backends.add("amf")
    backends.update(_ENCODER_BACKEND_ALIASES_BY_NAME.get(name, ()))
    return sorted(backends)


def validate_encoding_capabilities(
    preset: PresetV2 | Mapping[str, Any],
    capabilities: EncodingCapabilityFacts | Mapping[str, Any] | None = None,
) -> list[PresetValidationIssue]:
    """Return safe validation errors for preset requests unsupported by facts."""

    parsed_preset = preset if isinstance(preset, PresetV2) else PresetV2.model_validate(preset)
    facts = (
        capabilities
        if isinstance(capabilities, EncodingCapabilityFacts)
        else EncodingCapabilityFacts.model_validate(capabilities or {})
    )
    issues: list[PresetValidationIssue] = []
    _check_video(parsed_preset, facts, issues)
    _check_filters(parsed_preset, facts, issues)
    _check_audio(parsed_preset, facts, issues)
    _check_subtitles(parsed_preset, facts, issues)
    _check_container(parsed_preset, facts, issues)
    return issues


def _issue(section: str, path: str, message: str) -> PresetValidationIssue:
    return PresetValidationIssue(section=section, path=path, message=message)


def _check_video(preset: PresetV2, facts: EncodingCapabilityFacts, issues: list[PresetValidationIssue]) -> None:
    codec_family = _normalized_text(preset.video.codec_family)
    if codec_family != "copy" and codec_family not in facts.supported_video_codecs:
        issues.append(_issue("Video", "video.codecFamily", f"Video codec '{codec_family}' is not advertised by encoder capabilities."))

    backend = _normalized_text(preset.video.encoder_backend)
    if backend not in {"auto", "copy"} and backend not in facts.supported_encoder_backends:
        issues.append(_issue("Video", "video.encoderBackend", f"Encoder backend '{backend}' is not advertised by encoder capabilities."))

    legacy_encoder = _normalized_text(preset.video.codec)
    if "nvenc" in legacy_encoder and "nvenc" not in facts.supported_encoder_backends:
        issues.append(_issue("Video", "video.codec", f"Encoder '{legacy_encoder}' requires NVENC capability facts."))
    if legacy_encoder.startswith(("av1", "libsvtav1", "svt_av1")) and "av1" not in facts.supported_video_codecs:
        issues.append(_issue("Video", "video.codec", f"Encoder '{legacy_encoder}' requires AV1 capability facts."))


def _check_filters(preset: PresetV2, facts: EncodingCapabilityFacts, issues: list[PresetValidationIssue]) -> None:
    for name in active_video_filter_names(preset.filters):
        if name not in facts.supported_video_filters:
            issues.append(_issue("Filters", f"filters.{name}", f"Video filter '{name}' is not advertised by encoder capabilities."))


def _check_audio(preset: PresetV2, facts: EncodingCapabilityFacts, issues: list[PresetValidationIssue]) -> None:
    codec = _normalized_text(preset.audio.transcode_codec)
    if codec not in facts.supported_audio_transcode_codecs:
        issues.append(_issue("Audio", "audio.transcodeCodec", f"Audio transcode codec '{codec}' is not advertised by encoder capabilities."))


def _check_subtitles(preset: PresetV2, facts: EncodingCapabilityFacts, issues: list[PresetValidationIssue]) -> None:
    if preset.subtitles.convert_tx3g_to_srt and "tx3g_srt" not in facts.supported_subtitle_converters:
        issues.append(_issue("Subtitles", "subtitles.convertTx3gToSrt", "TX3G to SRT conversion is not advertised by capability facts."))
    if preset.subtitles.convert_bdpgs_to_srt and "bdpgs_ocr" not in facts.supported_subtitle_converters:
        issues.append(_issue("Subtitles", "subtitles.convertBdpgsToSrt", "BDPGS OCR conversion is not advertised by capability facts."))
    if preset.subtitles.convert_vobsub_to_srt and "vobsub_ocr" not in facts.supported_subtitle_converters:
        issues.append(_issue("Subtitles", "subtitles.convertVobSubToSrt", "VobSub OCR conversion is not advertised by capability facts."))


def _check_container(preset: PresetV2, facts: EncodingCapabilityFacts, issues: list[PresetValidationIssue]) -> None:
    container = _normalized_text(preset.container.format)
    if container not in facts.supported_containers:
        issues.append(_issue("Container", "container.format", f"Container '{container}' is not advertised by capability facts."))


__all__ = [
    "EncodingCapabilityFacts",
    "active_video_filter_names",
    "encoding_capability_facts_from_encoder_rows",
    "validate_encoding_capabilities",
]
