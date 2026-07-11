from __future__ import annotations

import re

LOG_LEVEL_VALUES = ("", "ERROR", "WARN", "INFO", "DEBUG")
PROFILE_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,80}$")

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
AUDIO_PASSTHROUGH_PROFILE_CODECS = {
    "plex_balanced": ("aac", "ac3", "eac3", "mp3", "opus", "vorbis", "truehd", "mlp"),
    "compatibility": ("aac", "ac3", "eac3", "mp3", "opus", "vorbis"),
    "lossless_passthrough": ("aac", "ac3", "eac3", "mp3", "opus", "vorbis", "truehd", "mlp", "dts", "dts_hd_ma", "dts-hd", "flac", "alac"),
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
    "compatibility_advisory": "Bitrate is strict; target output size stays profile-aware and flexible before processing.",
    "size": "Use movie/TV GB target output sizes as the hard route gate; bitrate still informs compatibility scoring.",
    "bitrate": "Use movie/TV Mbps max bitrate for direct copy as the hard route gate; GB size budgets stay flexible.",
    "size_or_bitrate": "Encode when either the GB target output size or Mbps direct-copy cap is exceeded.",
}

SIZE_GUARD_MODE_DEFAULT = "advisory"
SIZE_GUARD_MODE_NAMES = ("advisory", "strict", "fallback_remux", "off")
SIZE_GUARD_MODE_DESCRIPTIONS = {
    "advisory": "Warns but does not block when an encode grows past the configured size budget; publish can continue if verification passes.",
    "strict": "Blocks publish when an encode grows past the configured size budget and routes the result to manual review.",
    "fallback_remux": "For automatic size/bitrate-threshold encodes that grow past the configured size budget, attempts a safe remux fallback. Forced route overrides warn only and do not fallback.",
    "off": "Disable post-encode size growth checks.",
}

ENCODE_WASTE_GUARD_MODE_DEFAULT = "off"
ENCODE_WASTE_GUARD_MODE_NAMES = ("off", "dry_run", "enforce")
ENCODE_WASTE_GUARD_MODE_DESCRIPTIONS = {
    "off": "Disable live encode waste projections.",
    "dry_run": "Record preflight/live projected-oversize evidence without aborting the encode.",
    "enforce": "For eligible fallback-remux encodes, abort projected-oversize GPU work and try remux fallback.",
}

ENCODER_BACKEND_DEFAULT = "auto"
ENCODER_BACKEND_NAMES = ("auto", "nvenc", "qsv", "amf", "cpu")
ENCODER_BACKEND_DESCRIPTIONS = {
    "auto": "Let the encoder policy choose from the configured video codec and available hardware.",
    "nvenc": "Prefer NVIDIA NVENC encoders when descriptor activation is enabled.",
    "qsv": "Prefer Intel Quick Sync encoders when descriptor activation is enabled.",
    "amf": "Prefer AMD AMF encoders when descriptor activation is enabled.",
    "cpu": "Prefer CPU encoders when descriptor activation is enabled.",
}

DYNAMIC_HDR_POLICY_DEFAULT = "preserve_or_review"
DYNAMIC_HDR_POLICY_NAMES = ("off", "warn", "preserve_or_remux", "preserve_or_review")
DYNAMIC_HDR_POLICY_DESCRIPTIONS = {
    "off": "Disable dynamic HDR preservation diagnostics beyond normal probe data.",
    "warn": "Compatibility mode: continue with known Dynamic-HDR loss warnings. This is intentionally lossy and never HDR-safe readiness.",
    "preserve_or_remux": "Prefer a safe remux route when Dynamic HDR cannot be preserved by encode.",
    "preserve_or_review": "Default: block unsafe Dynamic-HDR encode and route it to review when preservation cannot be proven.",
}
