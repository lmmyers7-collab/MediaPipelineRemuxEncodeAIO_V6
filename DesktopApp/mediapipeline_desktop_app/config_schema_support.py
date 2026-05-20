from __future__ import annotations


ENCODE_TUNING_PRESET_DESCRIPTIONS = {
    "balanced_nvenc": "Balanced NVENC quality, speed, and compression.",
    "quality_nvenc": "Higher-quality NVENC flags for larger, cleaner output.",
    "fast_nvenc": "Faster NVENC flags for quicker batch processing.",
    "compatibility": "Conservative NVENC flags for fragile hardware or Plex compatibility.",
    "custom_legacy_flags": "Use raw ExtraVideoFlags exactly as entered.",
}

ENCODE_LADDER_DESCRIPTIONS = {
    "auto": "Use TV or movie defaults based on source type.",
    "tv_balanced": "TV-oriented quality and bitrate limits.",
    "tv_space_saver": "Smaller TV output with tighter bitrate limits.",
    "movie_balanced": "Movie-oriented balanced output.",
    "movie_archive": "Higher-quality movie archival profile.",
    "plex_compat": "Conservative target for broad Plex direct-play compatibility.",
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
