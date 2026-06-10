from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any


MP4_COMPATIBILITY_PRESET_ID = "mp4_compatibility"

_MP4_OVERRIDES: dict[str, dict[str, Any]] = {
    "editor": {
        "OutputContainer": "mp4",
        "VideoCodec": "hevc_nvenc",
        "EncodeLadder": "plex_compat",
    },
    "video": {
        "AllowH264RemuxIfPlexCompatible": True,
        "RemuxSafeVideoCodecs": ["hevc", "h265", "h.265", "h264", "h.264", "avc", "avc1"],
        "ExtraVideoFlags": [],
    },
    "subtitles": {
        "SubKeepLanguages": ["eng", "en", "und"],
        "ConvertTx3gToSrt": True,
        "DropTx3gAfterConversion": True,
        "CreateExternalTx3gSrtSidecars": True,
        "DropAssAfterConversion": True,
        "StripFormatting": True,
        "RemoveKaraoke": True,
        "KeepSignsAndSongs": False,
        "TreatAssSignsSongsAsForced": False,
        "TreatTx3gSignsSongsAsForced": False,
        "TreatBdpgsSignsSongsAsForced": False,
        "TreatVobSubSignsSongsAsForced": False,
    },
    "audio": {
        "AudioPassthroughProfile": "custom_codec_list",
        "CompatibleAudioCodecs": ["eac3"],
        "PreferredDefaultAudioLanguages": ["eng", "en", "und"],
        "AudioTranscodeCodec": "eac3",
        "AudioDownmixMode": "max_channels",
        "AudioMaxChannels": 6,
        "AllowNoAudio": False,
    },
}

_FORCED_FIELD_REASONS: dict[str, dict[str, str]] = {
    "editor": {
        "OutputContainer": "MP4 compatibility forces the output container to MP4.",
        "VideoCodec": "MP4 compatibility uses a Plex-oriented H.265 encoder by default.",
        "EncodeLadder": "MP4 compatibility uses the Plex compatibility encode ladder.",
    },
    "video": {
        "AllowH264RemuxIfPlexCompatible": "H.264 direct-copy is allowed only when the backend compatibility checks pass.",
        "RemuxSafeVideoCodecs": "MP4 compatibility limits direct-copy video to H.264/H.265 families.",
        "ExtraVideoFlags": "Freeform FFmpeg flags are cleared for predictable MP4 muxing.",
    },
    "subtitles": {
        "SubKeepLanguages": "MP4 compatibility selects one preferred-language SRT sidecar candidate.",
        "ConvertTx3gToSrt": "MP4 timed text is converted to external SRT instead of embedded in the MP4.",
        "DropTx3gAfterConversion": "Embedded TX3G/mov_text is dropped after SRT sidecar conversion.",
        "CreateExternalTx3gSrtSidecars": "MP4 compatibility writes external SRT sidecars for converted TX3G/mov_text.",
        "DropAssAfterConversion": "Styled ASS/SSA is not embedded in MP4; only converted SRT sidecars are kept.",
        "StripFormatting": "SRT sidecars are plain text for compatibility.",
        "RemoveKaraoke": "Karaoke timing/formatting is stripped for SRT compatibility.",
        "KeepSignsAndSongs": "Supplemental subtitle tracks are not kept in MP4 compatibility mode.",
        "TreatAssSignsSongsAsForced": "Signs/songs tracks are not split into extra MP4 subtitle tracks.",
        "TreatTx3gSignsSongsAsForced": "Signs/songs tracks are not split into extra MP4 subtitle tracks.",
        "TreatBdpgsSignsSongsAsForced": "Signs/songs tracks are not split into extra MP4 subtitle tracks.",
        "TreatVobSubSignsSongsAsForced": "Signs/songs tracks are not split into extra MP4 subtitle tracks.",
    },
    "audio": {
        "AudioPassthroughProfile": "MP4 compatibility uses a custom one-codec passthrough policy.",
        "CompatibleAudioCodecs": "Only EAC3 audio is retained without transcode in MP4 compatibility mode.",
        "PreferredDefaultAudioLanguages": "One preferred-language audio track is selected; all other audio is dropped.",
        "AudioTranscodeCodec": "Non-EAC3 selected audio is transcoded to EAC3.",
        "AudioDownmixMode": "Surround audio is capped by AudioMaxChannels before EAC3 transcode.",
        "AudioMaxChannels": "MP4 compatibility caps transcoded audio at 5.1 by default.",
        "AllowNoAudio": "MP4 compatibility does not permit silent output by default.",
    },
}

_CONSEQUENCES: tuple[dict[str, str], ...] = (
    {
        "severity": "high",
        "code": "mp4_forces_lossy_compatibility_profile",
        "message": "MP4 compatibility is intentionally lossy and rewrites the library profile for playback compatibility.",
    },
    {
        "severity": "high",
        "code": "mp4_single_eac3_audio",
        "message": "Only one preferred-language audio track remains; it is EAC3 or transcoded to EAC3.",
    },
    {
        "severity": "high",
        "code": "mp4_external_srt_only",
        "message": "Embedded subtitles are omitted; one preferred-language external SRT sidecar is required when subtitles are selected.",
    },
    {
        "severity": "medium",
        "code": "mp4_strips_metadata_attachments",
        "message": "Fonts, attachments, chapters, source metadata, and stream titles are stripped for maximum MP4 compatibility.",
    },
)


def mp4_compatibility_preset() -> dict[str, Any]:
    return {
        "id": MP4_COMPATIBILITY_PRESET_ID,
        "label": "MP4 Compatibility",
        "scope": "library",
        "severity": "high",
        "summary": "Lossy per-library MP4 compatibility mode for Plex-oriented H.264/H.265 video, one EAC3 audio track, and one external SRT sidecar.",
        "warning": (
            "MP4 compatibility rewrites this library profile and discards media features MKV can preserve: "
            "extra audio, embedded subtitles, fonts, attachments, chapters, and source metadata."
        ),
        "overrides": deepcopy(_MP4_OVERRIDES),
        "forced_fields": deepcopy(_MP4_OVERRIDES),
        "disabled_reasons": deepcopy(_FORCED_FIELD_REASONS),
        "hidden_fields": {
            "subtitles": ["IncludeSubtitleStyles", "ExcludeSubtitleStyles"],
            "video": ["ExtraVideoFlags"],
        },
        "consequences": deepcopy(list(_CONSEQUENCES)),
    }


def library_compatibility_presets() -> list[dict[str, Any]]:
    return [mp4_compatibility_preset()]


def mp4_compatibility_forced_fields() -> dict[str, dict[str, Any]]:
    return deepcopy(_MP4_OVERRIDES)


def mp4_compatibility_applied(overrides: Mapping[str, Any] | None) -> bool:
    if not isinstance(overrides, Mapping):
        return False
    editor = overrides.get("editor")
    if not isinstance(editor, Mapping):
        return False
    return str(editor.get("OutputContainer") or "").strip().casefold() == "mp4"


__all__ = [
    "MP4_COMPATIBILITY_PRESET_ID",
    "library_compatibility_presets",
    "mp4_compatibility_applied",
    "mp4_compatibility_forced_fields",
    "mp4_compatibility_preset",
]
