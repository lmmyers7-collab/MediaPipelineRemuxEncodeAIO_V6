"""Policy and enum-like static metadata for settings controls."""

from __future__ import annotations

LOG_LEVEL_VALUES = ("", "ERROR", "WARN", "INFO", "DEBUG")
AUDIO_PASSTHROUGH_PROFILE_DEFAULT = "plex_balanced"
AUDIO_PASSTHROUGH_PROFILE_NAMES = (
    "plex_balanced",
    "compatibility",
    "lossless_passthrough",
    "custom_codec_list",
)
AUDIO_PASSTHROUGH_PROFILE_DESCRIPTIONS = {
    "plex_balanced": "Copy common Plex-friendly audio plus TrueHD/MLP; normalize DTS, FLAC, PCM, and unknown codecs.",
    "compatibility": "Copy only AAC/AC3/EAC3/MP3/Opus/Vorbis; normalize lossless and DTS-style tracks.",
    "lossless_passthrough": "Copy common lossy, lossless, DTS, and FLAC tracks; still normalize PCM-like tracks.",
    "custom_codec_list": "Use the custom Audio Passthrough codec list exactly as entered.",
}
ROUTING_PROFILE_DEFAULT = "plex_direct_stream"
ROUTING_PROFILE_NAMES = (
    "plex_direct_stream",
    "plex_direct_play",
    "archive_shrink",
    "archive_quality",
    "manual",
)
ROUTING_PROFILE_DESCRIPTIONS = {
    "plex_direct_stream": "Default Plex-first routing. Copy compatible H.264/HEVC sources and encode only when bitrate, resolution, codec, or policy needs it.",
    "plex_direct_play": "Stricter Plex direct-play target. More willing to encode when compatibility scoring falls below the direct-play floor.",
    "archive_shrink": "Size-focused archive routing. Large files may encode even when already Plex-compatible.",
    "archive_quality": "Preserve quality first; keep compatible sources as copy/remux unless policy requires encode.",
    "manual": "Operator-driven routing. Folder force/prefer rules and explicit settings matter most.",
}
ROUTE_THRESHOLD_MODE_DEFAULT = "compatibility_advisory"
ROUTE_THRESHOLD_MODE_NAMES = (
    "compatibility_advisory",
    "size",
    "bitrate",
    "size_or_bitrate",
)
ROUTE_THRESHOLD_MODE_DESCRIPTIONS = {
    "compatibility_advisory": "Current behavior: bitrate is hard, while size is compatibility/profile-aware.",
    "size": "Use movie/TV GB thresholds as the hard route filter; bitrate still informs compatibility scoring.",
    "bitrate": "Use movie/TV Mbps ceilings as the hard route filter; size thresholds stay advisory.",
    "size_or_bitrate": "Encode when either the GB threshold or Mbps ceiling is exceeded.",
}
SIZE_GUARD_MODE_DEFAULT = "advisory"
SIZE_GUARD_MODE_NAMES = ("advisory", "strict", "off")
SIZE_GUARD_MODE_DESCRIPTIONS = {
    "advisory": "Warn and record when an encode grows past the configured size limit, but still publish if verification passes.",
    "strict": "Reject oversized encodes for manual review instead of publishing them.",
    "off": "Disable post-encode size growth checks.",
}
