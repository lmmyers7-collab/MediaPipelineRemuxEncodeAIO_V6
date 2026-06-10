"""Choice descriptions and table-column metadata for settings controls."""

from __future__ import annotations


ENCODE_TUNING_PRESET_DESCRIPTIONS = {
    "balanced_nvenc": "Default HEVC NVENC bundle: VBR, 60-frame lookahead, spatial and temporal AQ, full-resolution multipass, 4 B-frames, and HQ tune.",
    "quality_nvenc": "Cleaner NVENC output: keeps deep lookahead, AQ, full-resolution multipass, 4 B-frames, and raises AQ strength for larger/slower encodes.",
    "fast_nvenc": "Faster NVENC output: shorter 20-frame lookahead, temporal AQ off, lower AQ strength, disabled multipass, 2 B-frames, and low-latency tune.",
    "compatibility": "Conservative NVENC output: minimal VBR, spatial AQ, lower AQ strength, and 2 B-frames for fragile hardware or Plex compatibility.",
    "custom_legacy_flags": "Bypass the named bundles and pass raw ExtraVideoFlags to FFmpeg exactly as entered.",
}

ENCODE_LADDER_DESCRIPTIONS = {
    "auto": "Use TV balanced for TV sources and movie balanced for movie sources.",
    "tv_balanced": "TV-oriented default: one step smaller/softer than base quality, with 90M maxrate and 180M buffer.",
    "tv_space_saver": "Smallest TV target: two steps smaller/softer than base quality, with 80M maxrate and 160M buffer.",
    "movie_balanced": "Movie default: uses the configured base quality unchanged, with 120M maxrate and 240M buffer.",
    "movie_archive": "Cleaner movie target: one step cleaner/larger than base quality, with 160M maxrate and 320M buffer.",
    "plex_compat": "Compatibility target: one step smaller/softer than base quality, 80M maxrate, 160M buffer, and conservative encoder flags.",
}

AUDIO_TRANSCODE_CODEC_DESCRIPTIONS = {
    "eac3": "Dolby Digital Plus. Good default for Plex and 5.1/7.1 normalization.",
    "ac3": "Dolby Digital. Older compatibility target with lower practical bitrate.",
    "aac": "AAC. Broad stereo compatibility; use carefully for surround output.",
}

AUDIO_DOWNMIX_MODE_DESCRIPTIONS = {
    "max_channels": "Cap transcodes to Max Channels while preserving smaller sources.",
    "preserve": "Keep the source channel count when transcoding.",
    "stereo": "Force all transcoded audio to 2.0 stereo.",
}

AUDIO_MAX_CHANNEL_DESCRIPTIONS = {
    "2": "Stereo output cap.",
    "6": "5.1 output cap. Recommended default for Plex-style libraries.",
    "8": "7.1 output cap for receivers/players that handle it reliably.",
}

AUDIT_TREE_COLUMNS = (
    "PriorityScore",
    "PriorityFixLevel",
    "EffectiveBucket",
    "MediaType",
    "LookupTitle",
    "PrimaryIssueCode",
)

QUEUE_TREE_COLUMNS = (
    "GlobalOrder",
    "Phase",
    "MediaType",
    "QueuePosition",
    "Priority",
    "DisplayName",
    "RelativePath",
)

FAILURE_TREE_COLUMNS = (
    "Classification",
    "ErrorCode",
    "Stage",
    "MediaType",
    "LookupTitle",
    "Reason",
    "RecordedAt",
)
